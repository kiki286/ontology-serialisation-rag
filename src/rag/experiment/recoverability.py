"""Per-candidate licensing-axiom recoverability across ontology formats."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import yaml

from experiment.config import FORMATS
from experiment.schemas import Task

ChunkProvider = Callable[[str, list[str]], Sequence[str]]

_ELOT_MARKERS = {
    "rdf:type": "Characteristics",
    "rdfs:subClassOf": "SubClassOf",
    "rdfs:domain": "Domain",
    "rdfs:range": "Range",
    "rdfs:subPropertyOf": "SubPropertyOf",
    "owl:inverseOf": "InverseOf",
    "owl:equivalentClass": "EquivalentTo",
    "owl:equivalentProperty": "EquivalentTo",
    "owl:disjointWith": "DisjointWith",
}

_OFN_FUNCTORS = {
    "rdf:type": {"FunctionalObjectProperty", "FunctionalDataProperty"},
    "rdfs:subClassOf": {"SubClassOf"},
    "rdfs:domain": {"ObjectPropertyDomain", "DataPropertyDomain"},
    "rdfs:range": {"ObjectPropertyRange", "DataPropertyRange"},
    "rdfs:subPropertyOf": {"SubObjectPropertyOf", "SubDataPropertyOf"},
    "owl:inverseOf": {"InverseObjectProperties", "InverseDataProperties"},
    "owl:equivalentClass": {"EquivalentClasses"},
    "owl:equivalentProperty": {"EquivalentObjectProperties", "EquivalentDataProperties"},
    "owl:disjointWith": {"DisjointClasses"},
}


def _json_value_matches(value: Any, object_id: str) -> bool:
    if isinstance(value, Mapping):
        return value.get("@id") == object_id or any(
            _json_value_matches(child, object_id) for child in value.values()
        )
    if isinstance(value, list):
        return any(_json_value_matches(item, object_id) for item in value)
    return value == object_id


def _structured_chunk_has_axiom(
    chunk: str, subject: str, predicate: str, object_id: str, *, yaml_ld: bool
) -> bool:
    try:
        payload = yaml.safe_load(chunk) if yaml_ld else json.loads(chunk)
    except (TypeError, ValueError, yaml.YAMLError):
        return False

    if predicate == "rdf:type":
        def contains_typed_subject(value: Any) -> bool:
            if isinstance(value, Mapping):
                if value.get("@id") == subject and _json_value_matches(
                    value.get("@type"), object_id
                ):
                    return True
                return any(contains_typed_subject(child) for child in value.values())
            if isinstance(value, list):
                return any(contains_typed_subject(item) for item in value)
            return False

        return contains_typed_subject(payload)

    def contains_subject_node(value: Any) -> bool:
        if isinstance(value, Mapping):
            if value.get("@id") == subject and predicate in value:
                return _json_value_matches(value[predicate], object_id)
            return any(contains_subject_node(child) for child in value.values())
        if isinstance(value, list):
            return any(contains_subject_node(child) for child in value)
        return False

    return contains_subject_node(payload)


def _turtle_chunk_has_axiom(chunk: str, subject: str, predicate: str, object_id: str) -> bool:
    compact = re.sub(r"\s+", " ", chunk)
    direct = rf"(?<![\w:]){re.escape(subject)}\s+{re.escape(predicate)}\s+{re.escape(object_id)}(?=\s*(?:[;,.]|$))"
    continued = rf"(?<![\w:]){re.escape(subject)}[^.]*?;\s*{re.escape(predicate)}\s+{re.escape(object_id)}(?=\s*(?:[;,.]|$))"
    nested = rf"(?<![\w:]){re.escape(subject)}[^.]*?{re.escape(predicate)}\s+[^.]*?{re.escape(object_id)}(?=\s*(?:[;,.]|\]|\)|$))"
    pattern = rf"(?:{direct}|{continued}|{nested})"
    return re.search(pattern, compact) is not None


def _elot_chunk_has_axiom(chunk: str, subject: str, predicate: str, object_id: str) -> bool:
    if predicate == "rdf:type" and object_id == "owl:FunctionalProperty":
        return bool(
            re.search(
                rf"\({re.escape(subject)}\)[\s\S]*?-\s*Characteristics\s*::\s*Functional\b",
                chunk,
            )
        )
    marker = _ELOT_MARKERS.get(predicate)
    if marker is None:
        return False
    subject_start = re.search(rf"\({re.escape(subject)}\)", chunk)
    if subject_start is None:
        return False
    subject_text = chunk[subject_start.end():]
    for match in re.finditer(
        rf"^\s*-\s*{marker}\s*::\s*(?P<expression>.*?)\s*$",
        subject_text,
        re.MULTILINE,
    ):
        expression = match.group("expression")
        members = [member.strip() for member in expression.split(" or ")]
        if members and all(member == object_id for member in members if member == object_id):
            if object_id in members:
                return True
    return False


def _omn_chunk_has_axiom(chunk: str, subject: str, predicate: str, object_id: str) -> bool:
    if predicate == "rdf:type" and object_id == "owl:FunctionalProperty":
        return bool(
            re.search(
                rf"(?:^|\n)(?:ObjectProperty|DataProperty):\s*{re.escape(subject)}[\s\S]*?\n\s*Characteristics:\s*Functional\b",
                chunk,
            )
        )
    marker = _ELOT_MARKERS.get(predicate)
    if marker is None:
        return False
    pattern = rf"(?:^|\n)(?:Class|ObjectProperty|DataProperty):\s*{re.escape(subject)}[\s\S]*?\n\s*{marker}:\s*[^\n]*\b{re.escape(object_id)}\b"
    return re.search(pattern, chunk) is not None


def _ofn_chunk_has_axiom(chunk: str, subject: str, predicate: str, object_id: str) -> bool:
    from app.document_loaders import ofn_parse_axiom

    expected_functors = _OFN_FUNCTORS.get(predicate, set())
    for line in chunk.splitlines():
        line = line.strip()
        if not line or "(" not in line or not line.endswith(")"):
            continue
        try:
            functor, args = ofn_parse_axiom(line)
        except (ValueError, IndexError):
            continue
        if functor not in expected_functors:
            continue
        if predicate == "rdf:type" and object_id == "owl:FunctionalProperty":
            if args and args[0] == subject:
                return True
        if predicate in {"owl:equivalentClass", "owl:equivalentProperty", "owl:disjointWith"}:
            if subject in args and object_id in args:
                return True
        elif args and args[0] == subject and len(args) > 1:
            expression = args[1]
            if expression == object_id:
                return True
            if predicate in {"rdfs:domain", "rdfs:range"}:
                try:
                    expression_functor, expression_args = ofn_parse_axiom(expression)
                except (ValueError, IndexError):
                    continue
                if expression_functor in {"ObjectUnionOf", "DataUnionOf"} and object_id in expression_args:
                    return True
    return False


def licensing_axiom_recoverable(
    corpus_format: str,
    licensing_axiom: tuple[str, str, str],
    chunks: Sequence[str],
) -> bool:
    """Return whether one direct axiom occurs in the supplied chunk union.

    Ancestor headings and other structural context are deliberately not accepted;
    the predicate/object relation must be directly serialized in a gold chunk.
    ``owl:disjointWith`` is symmetric in OWL, so either serialized direction
    satisfies a licensing pair when both class chunks are supplied as gold.
    """
    subject, predicate, object_id = licensing_axiom
    directions = [(subject, object_id)]
    if predicate == "owl:disjointWith":
        directions.append((object_id, subject))
    for chunk in chunks:
        for direction_subject, direction_object in directions:
            if corpus_format == "turtle" and _turtle_chunk_has_axiom(
                chunk, direction_subject, predicate, direction_object
            ):
                return True
            if corpus_format in {"jsonld", "yaml-ld"} and _structured_chunk_has_axiom(
                chunk,
                direction_subject,
                predicate,
                direction_object,
                yaml_ld=corpus_format == "yaml-ld",
            ):
                return True
            if corpus_format in {"elot-org", "elot-org-ancestors"} and _elot_chunk_has_axiom(
                chunk, direction_subject, predicate, direction_object
            ):
                return True
            if corpus_format == "omn" and _omn_chunk_has_axiom(
                chunk, direction_subject, predicate, direction_object
            ):
                return True
            if corpus_format == "ofn" and _ofn_chunk_has_axiom(
                chunk, direction_subject, predicate, direction_object
            ):
                return True
    return False


def _assess_axiom_profiles(
    licensing_axioms: Sequence[tuple[str, str, str]],
    chunks_for_format: ChunkProvider,
    *,
    formats: Sequence[str],
) -> dict[str, object]:
    """Run the direct matcher for explicit links against each format's chunks."""
    profile: dict[str, bool | None] = {fmt: None for fmt in formats}
    errors: list[str] = []
    per_link = [
        {"link": list(link), "profile": {fmt: None for fmt in formats}}
        for link in licensing_axioms
    ]
    for fmt in formats:
        try:
            chunks = chunks_for_format(fmt, [])
            link_values = [
                licensing_axiom_recoverable(fmt, link, chunks) for link in licensing_axioms
            ]
            for result, value in zip(per_link, link_values):
                result["profile"][fmt] = value
            profile[fmt] = all(link_values)
        except (KeyError, ValueError, OSError) as exc:
            errors.append(f"{fmt}: {exc}")

    values = [value for value in profile.values() if value is not None]
    complete = not errors and len(values) == len(profile)
    return {
        "profile": profile,
        "fully_recoverable": complete and all(values),
        "uniform": complete and len(set(values)) == 1,
        "errors": errors,
        "per_link": per_link,
    }


def assess_field_recoverability(
    licensing_axioms: Sequence[tuple[str, str, str]],
    field_gold_chunks: list[str],
    *,
    formats: Sequence[str] = FORMATS,
    chunk_provider: ChunkProvider | None = None,
) -> dict[str, object]:
    """Assess one slot's asserted licensing links across all corpus formats.

    This authoring-time helper intentionally operates on explicit links and the
    field's own chunks. It does not interpret task type, modify scoring, or
    assign a profile to definition-licensed scenario-to-class matching.
    """
    if chunk_provider is None:
        from experiment.corpus_index import get_oracle_chunks

        def chunk_provider(fmt: str, _unused: list[str]) -> Sequence[str]:
            return [
                content
                for _entity_id, content in get_oracle_chunks(fmt, field_gold_chunks)
            ]

    return _assess_axiom_profiles(licensing_axioms, chunk_provider, formats=formats)


def assess_draft_recoverability(
    candidate: Task | Mapping[str, object],
    *,
    formats: Sequence[str] = FORMATS,
    chunk_provider: ChunkProvider | None = None,
) -> dict[str, object]:
    """Compute an authoring-time profile without loading a benchmark set.

    A split profile is valid and informative: it identifies a candidate whose
    direct licensing surface varies by format. Items whose licensing axiom is
    ``hypothetical`` explicitly skip this gate: the axiom is not in the graph, so
    trying to recover it from the gold chunks would treat a not-asserted relation
    as asserted. The skip branches on ``licensing_axiom_status``, never on the gold
    label or a null test.
    """
    task = candidate if isinstance(candidate, Task) else Task.model_validate(candidate)
    profile: dict[str, bool | None] = {fmt: None for fmt in formats}
    if task.task_type != "verification":
        return {
            "task_id": task.task_id,
            "gate_verdict": "skipped",
            "skip_reason": "non_verification",
            "profile": profile,
            "fully_recoverable": None,
            "uniform": None,
            "errors": [],
        }
    if task.licensing_axiom_status == "hypothetical":
        return {
            "task_id": task.task_id,
            "gate_verdict": "skipped",
            "skip_reason": "hypothetical_licensing_axiom",
            "profile": profile,
            "fully_recoverable": None,
            "uniform": None,
            "errors": [],
        }
    if task.licensing_axiom is None:
        return {
            "task_id": task.task_id,
            "gate_verdict": "failed",
            "skip_reason": None,
            "profile": profile,
            "fully_recoverable": False,
            "uniform": None,
            "errors": ["verification item has no licensing_axiom"],
        }

    if chunk_provider is None:
        from experiment.corpus_index import get_oracle_chunks

        def chunk_provider(fmt: str, _unused: list[str]) -> Sequence[str]:
            return [
                content
                for _entity_id, content in get_oracle_chunks(fmt, task.gold_chunks_for(fmt))
            ]

    assessment = _assess_axiom_profiles(task.licensing_links, chunk_provider, formats=formats)
    profile = assessment["profile"]
    errors = assessment["errors"]
    values = [value for value in profile.values() if value is not None]
    complete = not errors and len(values) == len(profile)
    gate_verdict = "pass" if complete and any(values) else "failed"
    return {
        "task_id": task.task_id,
        "gate_verdict": gate_verdict,
        "skip_reason": None,
        "profile": profile,
        "fully_recoverable": assessment["fully_recoverable"],
        "uniform": assessment["uniform"],
        "errors": errors,
        "per_link": assessment["per_link"],
    }