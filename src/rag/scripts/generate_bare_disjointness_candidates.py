"""Generate the Batch 1 bare-disjointness authoring candidate report."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from itertools import combinations
from pathlib import Path

import yaml
from rdflib import BNode, Graph, OWL, RDF, RDFS, URIRef

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import FORMATS, TASKS_PATH  # noqa: E402
from experiment.schemas import load_tasks  # noqa: E402
from scripts.tangle_ofn import _robot_command  # noqa: E402
from scripts.verify_undetermined_items import _prefix_args  # noqa: E402

CANONICAL_TURTLE = RAG_DIR / "data" / "LIS-14-for-FDIS (1).ttl"
CHECKER = RAG_DIR / "scripts" / "check_authoring_candidate.py"
LIS = "http://rds.posccaesar.org/ontology/lis14/rdl/"
UNSATISFIABLE_RE = re.compile(r"unsatisfiable:\s+(\S+)")


def compact(graph: Graph, node: URIRef) -> str:
    value = str(node)
    for prefix, namespace in graph.namespaces():
        base = str(namespace)
        if value.startswith(base):
            return f"{prefix}:{value[len(base):]}"
    return value


def term_for(graph: Graph, entity_id: str) -> URIRef:
    prefix, local = entity_id.split(":", 1)
    for known_prefix, namespace in graph.namespaces():
        if known_prefix == prefix:
            return URIRef(f"{namespace}{local}")
    raise ValueError(f"unknown prefix in {entity_id}")


def list_members(graph: Graph, head: URIRef | BNode) -> list[URIRef]:
    return [member for member in graph.items(head) if isinstance(member, URIRef)]


def direct_pairs(graph: Graph) -> dict[tuple[str, str], str]:
    pairs: dict[tuple[str, str], str] = {}
    for subject, object_ in graph.subject_objects(OWL.disjointWith):
        if isinstance(subject, URIRef) and isinstance(object_, URIRef):
            pair = tuple(sorted((compact(graph, subject), compact(graph, object_))))
            pairs[pair] = f"{pair[0]} owl:disjointWith {pair[1]}"
    for group in graph.subjects(RDF.type, OWL.AllDisjointClasses):
        head = graph.value(group, OWL.members)
        if head is None:
            continue
        members = sorted(compact(graph, member) for member in list_members(graph, head))
        axiom = f"AllDisjointClasses({', '.join(members)})"
        for pair in combinations(members, 2):
            pairs.setdefault(pair, axiom)
    return pairs


def annotation_fragments(graph: Graph, entity_id: str) -> list[str]:
    entity = term_for(graph, entity_id)
    fragments: list[str] = []
    for predicate, value in graph.predicate_objects(entity):
        local = str(predicate).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        if local in {"naturalLanguageDefinition", "usageNote"}:
            fragments.append(f"{entity_id} {local}: {str(value)}")
    return fragments


def inherited_candidate_count(graph: Graph, direct: set[tuple[str, str]]) -> int:
    subclasses: dict[str, set[str]] = {}
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef) and isinstance(parent, URIRef):
            child_id = compact(graph, child)
            parent_id = compact(graph, parent)
            subclasses.setdefault(child_id, set()).add(parent_id)

    closure: dict[str, set[str]] = {}
    for child in subclasses:
        seen: set[str] = set()
        pending = list(subclasses[child])
        while pending:
            parent = pending.pop()
            if parent not in seen:
                seen.add(parent)
                pending.extend(subclasses.get(parent, ()))
        closure[child] = seen

    inherited: set[tuple[str, str]] = set()
    for left, right in direct:
        for child, ancestors in closure.items():
            if left in ancestors and child != left:
                inherited.add((child, right))
            if right in ancestors and child != right:
                inherited.add((child, left))
    return len(inherited)


def draft_candidate(index: int, subject: str, object_: str) -> dict[str, object]:
    return {
        "task_id": f"B01-C{index:02d}",
        "task_type": "verification",
        "query": f"Is every {subject} a {object_} in IDO?",
        "reasoning_type": "structural",
        "query_source": "label",
        "mechanism": "bare_disjointness",
        "gold_chunks": [subject, object_],
        "retrieval_gold_chunks": [subject, object_],
        "statement": f"Every {subject} is a {object_}.",
        "gold_label": "contradicted",
        # The checker measures direct-pair recoverability. The report records the
        # actual AllDisjointClasses membership axiom separately.
        "licensing_axiom": [subject, "owl:disjointWith", object_],
        "annotation_prose_screen": "neutral",
    }


def run_checker(draft: dict[str, object]) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        draft_path = Path(directory) / "candidate.yaml"
        draft_path.write_text(yaml.safe_dump(draft, sort_keys=False), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, str(CHECKER), str(draft_path)],
            cwd=RAG_DIR,
            capture_output=True,
            text=True,
        )
    if not process.stdout.strip():
        raise RuntimeError(process.stderr.strip() or "candidate checker returned no assessment")
    assessment = json.loads(process.stdout)
    if assessment.get("errors"):
        raise RuntimeError(f"candidate checker errors: {assessment['errors']}")
    return assessment


def check_pilot_profiles() -> None:
    for task in load_tasks(TASKS_PATH):
        if task.task_type != "verification" or task.recoverability_profile is None:
            continue
        assessment = run_checker(task.model_dump(exclude_none=True))
        if assessment["profile"] != task.recoverability_profile:
            raise RuntimeError(
                f"stored pilot profile mismatch for {task.task_id}: "
                f"stored={task.recoverability_profile}, recomputed={assessment['profile']}"
            )


def robot_unsatisfiable_classes(ontology_path: Path) -> set[str]:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "reasoned.ttl"
        command = _robot_command() + [
            "reason",
            "--input",
            str(ontology_path),
            "--input-format",
            "ttl",
            "--reasoner",
            "HermiT",
            *_prefix_args(CANONICAL_TURTLE),
            "--output",
            str(output),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
    detail = "\n".join(
        part for part in (process.stdout.strip(), process.stderr.strip()) if part
    )
    unsatisfiable = {
        f"lis:{iri[len(LIS):]}" for iri in UNSATISFIABLE_RE.findall(detail) if iri.startswith(LIS)
    }
    if process.returncode != 0 and not unsatisfiable:
        raise RuntimeError(f"ROBOT reason failed for {ontology_path}: {detail}")
    return unsatisfiable


def robot_unsatisfiable_class(
    subject: str, object_: str, baseline_unsatisfiable: set[str]
) -> str:
    with tempfile.TemporaryDirectory() as directory:
        directory_path = Path(directory)
        asserted = directory_path / "asserted.ttl"
        asserted.write_text(
            CANONICAL_TURTLE.read_text(encoding="utf-8")
            + f"\n{subject} rdfs:subClassOf {object_} .\n",
            encoding="utf-8",
        )
        unsatisfiable = robot_unsatisfiable_classes(asserted)
    if subject not in unsatisfiable or subject in baseline_unsatisfiable:
        raise RuntimeError(
            f"ROBOT did not establish that {subject} becomes unsatisfiable after asserting "
            f"{subject} SubClassOf {object_}; baseline={sorted(baseline_unsatisfiable)}, "
            f"asserted={sorted(unsatisfiable)}"
        )
    return subject


def markdown(candidates: list[dict[str, object]], inherited_count: int) -> str:
    lines = [
        "# Batch 01: Bare-Disjointness Contradicted Candidates",
        "",
        "## Enumeration",
        "",
        f"The canonical graph contains **{len(candidates) // 2}** directly asserted unordered disjoint class pairs and therefore **{len(candidates)}** directional candidate statements. It contains 15 named `owl:disjointWith` triples and three `owl:AllDisjointClasses` groups whose 12 membership pairs are already covered by those pairwise assertions.",
        "",
        f"Separately, there are **{inherited_count}** directional inherited-disjointness candidates, counted by propagating each direct pair through asserted `rdfs:subClassOf` ancestry and excluding the direct pairs. They are not included in this batch.",
        "",
        "## Semantic Convention Flag",
        "",
        "Every candidate below diverges under the two readings described in the brief: adding `X SubClassOf Y` to a graph with directly asserted `DisjointClasses(X Y)` makes `X` unsatisfiable, but the disjointness axiom alone does not entail strict `not (X SubClassOf Y)` under OWL's open-world semantics because `X` may be empty. ROBOT/HermiT operationally confirmed the stated subject class as unsatisfiable for every candidate. This report retains the benchmark's unsatisfiability-based `contradicted` convention; whether that convention should instead require strict negation is a benchmark-wide definitional decision for the author and supervisors.",
        "",
        "## Candidate Table",
        "",
        "Sorted non-uniform profiles first. `gold_chunks` and `retrieval_gold_chunks` use format-stable entity IDs; the authoring checker resolves them in each of the seven corpora. The checker treats `owl:disjointWith` symmetrically across the supplied gold-chunk union, while the licensing column records the canonical direct pairwise axiom.",
        "",
        "| ID | Draft statement | Formal axiom | Licensing axiom | Unsatisfiable class (ROBOT) | Gold chunks / retrieval gold | Recoverability profile | Uniform | Prose direction and quoted annotation | Reasoning type | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    ordered = sorted(candidates, key=lambda candidate: (candidate["uniform"], candidate["id"]))
    for candidate in ordered:
        profile = ", ".join(
            f"{format_name}={str(candidate['profile'][format_name]).lower()}"
            for format_name in FORMATS
        )
        fragments = candidate["fragments"]
        direction = "away" if any("disjointness" in fragment.lower() for fragment in fragments) else "neutral"
        prose = (
            "neutral; no naturalLanguageDefinition or usageNote on either gold chunk"
            if not fragments
            else f"{direction}; " + " / ".join(f'“{fragment}”' for fragment in fragments)
        )
        lines.append(
            "| {id} | {statement} | `{subject} SubClassOf {object}` | `{licensing}` | `{unsatisfiable}` | `{gold}` / `{retrieval}` | {profile} | `{uniform}` | {prose} | `{reasoning}` | {notes} |".format(
                id=candidate["id"],
                statement=candidate["statement"],
                subject=candidate["subject"],
                object=candidate["object"],
                licensing=candidate["licensing"],
                unsatisfiable=candidate["unsatisfiable"],
                gold=", ".join(candidate["gold_chunks"]),
                retrieval=", ".join(candidate["retrieval_gold_chunks"]),
                profile=profile,
                uniform=str(candidate["uniform"]).lower(),
                prose=prose.replace("|", "\\|"),
                reasoning=candidate["reasoning_type"],
                notes=candidate["notes"],
            )
        )
    lines.extend(
        [
            "",
            "## Candidates Not Put Forward",
            "",
            "None are excluded by this generation pass. The author should make the final selection after reviewing the table, including the annotation excerpts and the semantic-convention flag above.",
            "",
            "## Verification Record",
            "",
            "The generator recomputed each stored pilot verification profile with `check_authoring_candidate` before processing this batch; all matched their stored structural metadata. It then ran that checker once for every candidate and ran ROBOT/HermiT once for every directional assertion.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    graph = Graph().parse(CANONICAL_TURTLE, format="turtle")
    pairs = direct_pairs(graph)
    check_pilot_profiles()
    baseline_unsatisfiable = robot_unsatisfiable_classes(CANONICAL_TURTLE)
    candidates: list[dict[str, object]] = []
    for index, ((left, right), licensing) in enumerate(sorted(pairs.items()), start=1):
        for subject, object_ in ((left, right), (right, left)):
            draft = draft_candidate(len(candidates) + 1, subject, object_)
            assessment = run_checker(draft)
            candidates.append(
                {
                    "id": draft["task_id"],
                    "subject": subject,
                    "object": object_,
                    "statement": draft["statement"],
                    "licensing": licensing,
                    "unsatisfiable": robot_unsatisfiable_class(
                        subject, object_, baseline_unsatisfiable
                    ),
                    "gold_chunks": draft["gold_chunks"],
                    "retrieval_gold_chunks": draft["retrieval_gold_chunks"],
                    "profile": assessment["profile"],
                    "uniform": assessment["uniform"],
                    "fragments": annotation_fragments(graph, subject)
                    + annotation_fragments(graph, object_),
                    "reasoning_type": "structural",
                    "notes": "Directly asserted pairwise disjointness; also present in an AllDisjointClasses group where applicable.",
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown(candidates, inherited_candidate_count(graph, set(pairs))), encoding="utf-8")
    print(f"wrote {args.output} with {len(candidates)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())