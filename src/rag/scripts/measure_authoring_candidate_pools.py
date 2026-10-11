"""Measure local authoring candidate pools without selecting benchmark items."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from rdflib import BNode, Graph, OWL, RDF, RDFS, URIRef

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import DATA_DIR, FORMATS  # noqa: E402
from experiment.recoverability import assess_draft_recoverability  # noqa: E402

CANONICAL_TURTLE = DATA_DIR / "LIS-14-for-FDIS (1).ttl"
SAMPLE_SIZE = 20


def compact(graph: Graph, node: URIRef) -> str:
    value = str(node)
    for prefix, namespace in graph.namespaces():
        if value.startswith(str(namespace)):
            return f"{prefix}:{value[len(str(namespace)):]}"
    return value


def is_lis_id(entity_id: str) -> bool:
    return entity_id.startswith("lis:")


def annotation_fragments(graph: Graph, entity_ids: list[str]) -> list[str]:
    fragments: list[str] = []
    by_id = {
        compact(graph, node): node
        for node in graph.all_nodes()
        if isinstance(node, URIRef) and is_lis_id(compact(graph, node))
    }
    for entity_id in entity_ids:
        entity = by_id.get(entity_id)
        if entity is None:
            continue
        for predicate, value in graph.predicate_objects(entity):
            if str(predicate).rsplit("/", 1)[-1] in {"naturalLanguageDefinition", "usageNote"}:
                fragments.append(f"{entity_id}: {value}")
    return fragments


def classify_prose(fragments: list[str]) -> str:
    """Make licensing-axiom leakage visible; direction remains a human screen."""
    text = " ".join(fragments).lower()
    if re.search(r"\b(disjointness axiom|disjoint classes?|functional property)\b", text):
        return "states_axiom"
    return "neutral"


def candidate(
    identifier: str, mechanism: str, gold_chunks: list[str], licensing_axiom: tuple[str, str, str]
) -> dict[str, object]:
    assessment = assess_draft_recoverability(
        {
            "task_id": identifier,
            "task_type": "verification",
            "query": "measurement placeholder",
            "reasoning_type": "structural",
            "query_source": "label",
            "mechanism": mechanism,
            "gold_chunks": gold_chunks,
            "statement": "measurement placeholder",
            "gold_label": "contradicted",
            "annotation_prose_screen": "neutral",
            "licensing_axiom": licensing_axiom,
        }
    )
    return {
        "id": identifier,
        "mechanism": mechanism,
        "gold_chunks": gold_chunks,
        "licensing_axiom": list(licensing_axiom),
        "profile": assessment["profile"],
        "uniform": assessment["uniform"],
        "gate_verdict": assessment["gate_verdict"],
    }


def direct_disjoint_pairs(graph: Graph) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for left, right in graph.subject_objects(OWL.disjointWith):
        if isinstance(left, URIRef) and isinstance(right, URIRef):
            pair = tuple(sorted((compact(graph, left), compact(graph, right))))
            if all(is_lis_id(entity_id) for entity_id in pair):
                pairs.add(pair)
    for group in graph.subjects(RDF.type, OWL.AllDisjointClasses):
        members = graph.value(group, OWL.members)
        if members is not None:
            ids = sorted(compact(graph, member) for member in graph.items(members) if isinstance(member, URIRef))
            pairs.update(pair for pair in combinations(ids, 2) if all(is_lis_id(entity_id) for entity_id in pair))
    return pairs


def subclass_closure(graph: Graph) -> dict[str, set[str]]:
    parents: dict[str, set[str]] = defaultdict(set)
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef) and isinstance(parent, URIRef):
            child_id, parent_id = compact(graph, child), compact(graph, parent)
            if is_lis_id(child_id) and is_lis_id(parent_id):
                parents[child_id].add(parent_id)
    closure: dict[str, set[str]] = {}
    for child in parents:
        seen: set[str] = set()
        pending = list(parents[child])
        while pending:
            parent = pending.pop()
            if parent not in seen:
                seen.add(parent)
                pending.extend(parents.get(parent, ()))
        closure[child] = seen
    return closure


def asserted_subclass_pairs(graph: Graph) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef) and isinstance(parent, URIRef):
            child_id, parent_id = compact(graph, child), compact(graph, parent)
            if is_lis_id(child_id) and is_lis_id(parent_id):
                pairs.append((child_id, parent_id))
    return sorted(set(pairs))


def attach_prose(graph: Graph, candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    for item in candidates:
        fragments = annotation_fragments(graph, list(item["gold_chunks"]))
        item["annotation_fragments"] = fragments
        item["prose_screen"] = classify_prose(fragments)
    return candidates


def summarize(candidates: list[dict[str, object]]) -> dict[str, object]:
    false_formats = sorted(
        {
            fmt
            for item in candidates
            for fmt, value in item["profile"].items()
            if value is False
        }
    )
    return {
        "sampled": len(candidates),
        "uniform": sum(item["uniform"] is True for item in candidates),
        "non_uniform": sum(item["uniform"] is False for item in candidates),
        "false_formats": false_formats,
        "prose_screens": {
            label: sum(item["prose_screen"] == label for item in candidates)
            for label in ("toward", "away", "neutral", "states_axiom")
        },
        "candidates": candidates,
    }


def measure(graph: Graph) -> dict[str, object]:
    pairs = direct_disjoint_pairs(graph)
    closure = subclass_closure(graph)
    inherited: list[dict[str, object]] = []
    for left, right in sorted(pairs):
        for child, ancestors in sorted(closure.items()):
            if left in ancestors and child != left:
                inherited.append(candidate(f"I-{len(inherited) + 1:02d}", "inherited_disjointness", [child, left, right], (left, "owl:disjointWith", right)))
            if right in ancestors and child != right:
                inherited.append(candidate(f"I-{len(inherited) + 1:02d}", "inherited_disjointness", [child, left, right], (left, "owl:disjointWith", right)))

    domain_range: list[dict[str, object]] = []
    property_axioms: list[tuple[str, str, str]] = []
    for predicate, mechanism in ((RDFS.domain, "direct_domain_range"), (RDFS.range, "direct_domain_range")):
        for subject, object_id in graph.subject_objects(predicate):
            if isinstance(subject, URIRef) and isinstance(object_id, URIRef):
                subject_id, object_compact = compact(graph, subject), compact(graph, object_id)
                if is_lis_id(subject_id) and is_lis_id(object_compact):
                    property_axioms.append((subject_id, compact(graph, predicate), object_compact))
    for subject, predicate, object_id in sorted(property_axioms)[:SAMPLE_SIZE]:
        domain_range.append(candidate(f"D-{len(domain_range) + 1:02d}", "direct_domain_range", [subject, object_id], (subject, predicate, object_id)))

    composed: list[dict[str, object]] = []
    for subject, predicate, typed_class in sorted(property_axioms):
        for left, right in sorted(pairs):
            if typed_class == left or typed_class == right:
                other = right if typed_class == left else left
                composed.append(candidate(f"C-{len(composed) + 1:02d}", "composed_domain_range_disjointness", [subject, typed_class, other], (subject, predicate, typed_class)))
                break
        if len(composed) == SAMPLE_SIZE:
            break

    functional = [
        candidate(f"F-{index:02d}", "functional_property", [property_id], (property_id, "rdf:type", "owl:FunctionalProperty"))
        for index, property_id in enumerate(("lis:datumUOM", "lis:datumValue"), start=1)
    ]

    subsumption: list[dict[str, object]] = []
    for child, parent in asserted_subclass_pairs(graph)[:SAMPLE_SIZE]:
        subsumption.append(
            candidate(
                f"S-{len(subsumption) + 1:02d}",
                "subsumption",
                [child, parent],
                (child, "rdfs:subClassOf", parent),
            )
        )

    tiers = {
        "inherited_disjointness": attach_prose(graph, inherited[:SAMPLE_SIZE]),
        "direct_domain_range": attach_prose(graph, domain_range),
        "composed_domain_range_disjointness": attach_prose(graph, composed),
        "functional_property": attach_prose(graph, functional),
        "subsumption": attach_prose(graph, subsumption),
    }
    bare_disjointness = attach_prose(
        graph,
        [
            candidate(
                f"B-{index:02d}",
                "bare_disjointness",
                [left, right],
                (left, "owl:disjointWith", right),
            )
            for index, (left, right) in enumerate(sorted(pairs), start=1)
        ],
    )
    return {
        "method": "Deterministic local samples (maximum 20 per tier); no benchmark items selected.",
        "formats": FORMATS,
        "tiers": {name: summarize(items) for name, items in tiers.items()},
        "bare_disjointness_prose_screen": summarize(bare_disjointness),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    measurements = measure(Graph().parse(CANONICAL_TURTLE, format="turtle"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(measurements, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())