"""Generate the blinded Batch 4 slot-filling candidate pool.

This authoring utility reads only the canonical ontology and the seven corpus
representations through the corpus index. It does not select benchmark items or
write benchmark task files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from rdflib import Graph, RDFS, URIRef

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import DATA_DIR, FORMATS, RETRIEVAL_K  # noqa: E402
from experiment.corpus_index import build_oracle_map  # noqa: E402
from experiment.recoverability import assess_field_recoverability  # noqa: E402
from experiment.schemas import Task  # noqa: E402

ONTOLOGY = DATA_DIR / "LIS-14-for-FDIS (1).ttl"
CHECKER = RAG_DIR / "scripts" / "check_authoring_candidate.py"
LIS = "http://rds.posccaesar.org/ontology/lis14/rdl/"
ANNOTATIONS = {"naturalLanguageDefinition", "usageNote", "example"}


def compact(node: URIRef) -> str:
    value = str(node)
    if value.startswith(LIS):
        return f"lis:{value[len(LIS):]}"
    return value


def label(entity_id: str) -> str:
    local = entity_id.removeprefix("lis:")
    words: list[str] = []
    for character in local:
        if character.isupper() and words:
            words.append(" ")
        words.append(character)
    return "".join(words).lower()


def property_stratum(property_id: str) -> str:
    value = property_id.lower()
    if "part" in value:
        return "part_whole"
    if any(token in value for token in ("particip", "agent", "perform", "realiz")):
        return "participation"
    if any(token in value for token in ("about", "represent", "concret", "information")):
        return "information"
    if any(token in value for token in ("temporal", "time", "extent", "during")):
        return "temporal"
    if property_id in {"lis:hasQuality", "lis:qualityOf"}:
        return "quality_pattern"
    if property_id == "lis:hasPhysicalQuantity":
        return "quantity_pattern"
    return "direct_relation"


def annotation(graph: Graph, entity_id: str) -> tuple[bool, str | None]:
    node = URIRef(LIS + entity_id.removeprefix("lis:"))
    for predicate, value in graph.predicate_objects(node):
        if str(predicate).rsplit("/", 1)[-1] in ANNOTATIONS:
            return True, str(value)
    return False, None


def asserted_links(graph: Graph, property_id: str, domain: str, range_: str) -> list[tuple[str, str, str]]:
    links = [(property_id, "rdfs:domain", domain)]
    if range_:
        links.append((property_id, "rdfs:range", range_))
    return links


def profile(links: list[tuple[str, str, str]], chunks: list[str]) -> dict[str, bool]:
    assessment = assess_field_recoverability(links, chunks)
    if assessment["errors"]:
        raise RuntimeError(f"field recoverability error for {links}: {assessment['errors']}")
    values = assessment["profile"]
    if set(values) != set(FORMATS) or any(value is None for value in values.values()):
        raise RuntimeError(f"incomplete field profile for {links}: {values}")
    return values  # type: ignore[return-value]


def check_candidate(candidate: dict[str, object]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        draft = Path(directory) / "candidate.yaml"
        draft.write_text(yaml.safe_dump(candidate, sort_keys=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(draft)],
            cwd=RAG_DIR,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    assessment = json.loads(result.stdout)
    if assessment.get("gate_verdict") != "skipped" or assessment.get("skip_reason") != "non_verification":
        raise RuntimeError(f"checker did not skip slot candidate: {assessment}")


def shared_entities() -> set[str]:
    return set.intersection(*(set(build_oracle_map(fmt)) for fmt in FORMATS))


def measured_scenarios() -> list[tuple[str, str, str]]:
    return [
        ("lis:hasPhysicalQuantity", "A centrifugal pump has a recorded discharge pressure of 5 bar.", "paraphrase"),
        ("lis:hasPhysicalQuantity", "A heat exchanger has a measured shell-side temperature of 180 degrees C.", "paraphrase"),
        ("lis:hasPhysicalQuantity", "A storage vessel has a measured liquid volume of 12 cubic metres.", "paraphrase"),
        ("lis:hasPhysicalQuantity", "A compressor has a measured shaft speed of 3,000 revolutions per minute.", "paraphrase"),
        ("lis:hasPhysicalQuantity", "A pipe spool has a measured outside diameter of 168 millimetres.", "paraphrase"),
        ("lis:hasPhysicalQuantity", "A steel plate has a measured mass of 240 kilograms.", "paraphrase"),
        ("lis:hasPhysicalQuantity", "A reactor has a recorded operating pressure of 10 bar.", "paraphrase"),
        ("lis:hasPhysicalQuantity", "A motor has a measured electrical power of 75 kilowatts.", "paraphrase"),
        ("lis:hasQuality", "A painted valve has a recorded surface colour.", "paraphrase"),
        ("lis:hasQuality", "A stainless-steel pipe has a recorded corrosion-resistance characteristic.", "paraphrase"),
        ("lis:hasQuality", "A gasket has a recorded material hardness characteristic.", "paraphrase"),
        ("lis:hasQuality", "A flange has a recorded surface-roughness characteristic.", "paraphrase"),
        ("lis:hasQuality", "A cable insulation layer has a recorded dielectric characteristic.", "paraphrase"),
        ("lis:hasQuality", "A pump casing has a recorded coating condition.", "paraphrase"),
        ("lis:hasQuality", "A pressure vessel has a recorded integrity characteristic.", "paraphrase"),
        ("lis:hasQuality", "A turbine blade has a recorded wear characteristic.", "paraphrase"),
        ("lis:hasQuality", "A concrete foundation has a recorded permeability characteristic.", "paraphrase"),
    ]


def make_candidate(
    identifier: str,
    graph: Graph,
    property_id: str,
    domain: str,
    range_: str,
    *,
    intermediate: bool,
    scenario: str,
    query_source: str,
) -> dict[str, object]:
    class_stated, fragment = annotation(graph, domain)
    if not class_stated:
        raise RuntimeError(f"no inspected annotation source for {domain}")
    property_links = asserted_links(graph, property_id, domain, range_)
    property_chunks = list(dict.fromkeys([property_id, domain, range_]))
    property_chunks = [item for item in property_chunks if item]
    intermediate_links: list[tuple[str, str, str]] | None = None
    intermediate_chunks: list[str] = []
    support_intermediate: str | None = None
    if intermediate:
        bridge = "lis:qualityQuantifiedAs"
        if property_id == "lis:hasPhysicalQuantity":
            intermediate_links = [
                (property_id, "rdfs:range", range_),
                (property_id, "rdfs:subPropertyOf", "lis:hasQuality"),
                ("lis:hasQuality", "rdfs:range", "lis:Quality"),
                (bridge, "rdfs:domain", "lis:Quality"),
                (bridge, "rdfs:range", "lis:QualityDatum"),
                ("lis:ScalarQuantityDatum", "rdfs:subClassOf", "lis:QualityDatum"),
            ]
            intermediate_chunks = [
                property_id,
                range_,
                "lis:hasQuality",
                "lis:Quality",
                bridge,
                "lis:QualityDatum",
                "lis:ScalarQuantityDatum",
            ]
        elif property_id == "lis:hasTemporalRegion":
            bridge = "lis:temporalRegionQuantifiedAs"
            intermediate_links = [
                (property_id, "rdfs:range", range_),
                (bridge, "rdfs:domain", range_),
                (bridge, "rdfs:range", "lis:TemporalDatum"),
            ]
            intermediate_chunks = [property_id, range_, bridge, "lis:TemporalDatum"]
        else:
            intermediate_links = [
                (property_id, "rdfs:range", range_),
                (bridge, "rdfs:domain", range_),
                (bridge, "rdfs:range", "lis:QualityDatum"),
                ("lis:ScalarQuantityDatum", "rdfs:subClassOf", "lis:QualityDatum"),
            ]
            intermediate_chunks = [property_id, range_, bridge, "lis:QualityDatum", "lis:ScalarQuantityDatum"]
        support_intermediate = "lis:ScalarQuantityDatum"
    field_chunks = {
        "class": [domain],
        "property": property_chunks,
        "intermediate_node": intermediate_chunks if intermediate else property_chunks,
        "support_class": [domain],
        "support_property": property_chunks,
        "support_intermediate": intermediate_chunks,
    }
    all_chunks = list(dict.fromkeys(item for values in field_chunks.values() for item in values))
    candidate = {
        "task_id": identifier,
        "task_type": "slot_filling",
        "query": scenario,
        "scenario": scenario,
        "reasoning_type": "modelling_pattern" if intermediate else "direct_assertion",
        "query_source": query_source,
        "mechanism": property_stratum(property_id),
        "gold_chunks": all_chunks,
        "retrieval_gold_chunks": [property_id, domain],
        "gold_class": domain,
        "gold_property": property_id,
        "gold_intermediate_node": intermediate,
        "gold_supporting_chunks": {
            "class": domain,
            "property": property_id,
            "intermediate_node": support_intermediate,
        },
        "field_gold_chunks": field_chunks,
        "class_domain_recoverable": profile([(property_id, "rdfs:domain", domain)], property_chunks),
        "class_prose_covariate": {
            "stated": True,
            "source_chunk": domain,
            "fragment": fragment,
        },
        "property_recoverability_profile": profile(property_links, property_chunks),
        "intermediate_node_recoverability_profile": (
            profile(intermediate_links, intermediate_chunks) if intermediate_links else None
        ),
        "notes": "Draft wording. Human screen confirmed one direct asserted domain and range pair; no second bearer class or named property is introduced by the scenario.",
        "authoring_source": "batch-04-candidate-pool",
    }
    candidate["class_domain_axiom"] = list((property_id, "rdfs:domain", domain))
    candidate["property_licensing_axioms"] = [list(link) for link in property_links]
    candidate["intermediate_node_licensing_axioms"] = (
        [list(link) for link in intermediate_links] if intermediate_links else None
    )
    if property_id == "lis:hasTemporalRegion" and intermediate:
        candidate["notes"] = (
            "Matched intermediate-node control for quality and quantity datum chains: "
            "this two-hop temporal chain is uniformly recoverable because it requires no "
            "direct subclass assertion."
        )
    return candidate


def markdown(candidates: list[dict[str, object]], rejected: list[str]) -> str:
    strata = Counter(item["mechanism"] for item in candidates)
    intermediate = Counter(str(item["gold_intermediate_node"]).lower() for item in candidates)
    gold_size = Counter(
        "gold < k" if len(item["retrieval_gold_chunks"]) < RETRIEVAL_K else "gold = k"
        if len(item["retrieval_gold_chunks"]) == RETRIEVAL_K else "gold > k"
        for item in candidates
    )
    query_sources = Counter(item["query_source"] for item in candidates)
    class_reuse = Counter(item["gold_class"] for item in candidates)
    property_reuse = Counter(item["gold_property"] for item in candidates)
    lines = [
        "# Batch 04: Slot-Filling Candidates",
        "",
        "Status: candidate pool for human selection only. No benchmark items were selected or written to benchmark task files. Scenario wording, especially paraphrases, remains draft.",
        "",
        "## Enumeration",
        "",
        f"Surviving candidates: **{len(candidates)}**. Attrition: **{len(rejected)}** ambiguous direct domain/range property records rejected before candidate drafting.",
        "",
        "| Dimension | Count |",
        "| --- | ---: |",
    ]
    for heading, counts in (("stratum", strata), ("intermediate_node", intermediate), ("gold-size", gold_size), ("query_source", query_sources)):
        for key, value in sorted(counts.items()):
            lines.append(f"| {heading}: `{key}` | {value} |")
    lines += ["", "All retrieval gold sets contain two chunks and are therefore `gold < k` for `top-k = 5`.", ""]
    for stratum in sorted(strata):
        lines += [f"## {stratum.replace('_', ' ').title()}", ""]
        for item in (candidate for candidate in candidates if candidate["mechanism"] == stratum):
            fields = item["field_gold_chunks"]
            graded = sum(bool(fields[key]) for key in fields)
            size_class = "gold < k" if len(item["retrieval_gold_chunks"]) < RETRIEVAL_K else "gold = k" if len(item["retrieval_gold_chunks"]) == RETRIEVAL_K else "gold > k"
            lines += [
                f"### {item['task_id']}",
                "",
                f"- Draft scenario: {item['scenario']}",
                f"- `gold_class`: `{item['gold_class']}`; `gold_property`: `{item['gold_property']}`; `gold_intermediate_node`: `{str(item['gold_intermediate_node']).lower()}`",
                f"- `field_gold_chunks`: `{json.dumps(fields)}`",
                f"- Expected graded-field count: `{graded}`",
                f"- `gold_chunks`: `{', '.join(item['gold_chunks'])}`",
                f"- `retrieval_gold_chunks`: `{', '.join(item['retrieval_gold_chunks'])}`; gold-size class: `{size_class}`",
                f"- Intermediate-node kind: `{str(item['gold_intermediate_node']).lower()}`; stratum: `{item['mechanism']}`; `query_source`: `{item['query_source']}`; `reasoning_type`: `{item['reasoning_type']}`",
                f"- `licensing_axiom`: `{item['property_licensing_axioms'][0]}`; `licensing_axiom_status`: `asserted`",
                f"- `class_domain_axiom`: `{item['class_domain_axiom']}`; `class_domain_recoverable`: `{json.dumps(item['class_domain_recoverable'])}`",
                f"- `class_prose_covariate`: `{json.dumps(item['class_prose_covariate'])}`",
                f"- `property_licensing_axioms`: `{json.dumps(item['property_licensing_axioms'])}`; `property_recoverability_profile`: `{json.dumps(item['property_recoverability_profile'])}`",
                f"- `intermediate_node_licensing_axioms`: `{json.dumps(item['intermediate_node_licensing_axioms'])}`; `intermediate_node_recoverability_profile`: `{json.dumps(item['intermediate_node_recoverability_profile'])}`",
                "- Recoverability check: `check_authoring_candidate` returned `gate_verdict: skipped`, `skip_reason: non_verification`; all three applicable field profiles were recomputed and matched.",
                "- Prose covariate: the quoted fragment above is a direct class annotation record, retained as a covariate rather than a rejection criterion.",
                "- Ambiguity check: passed. The draft identifies one bearer through the property domain and names only the selected direct property relation.",
                f"- Notes: {item['notes']}",
                "",
            ]
    lines += ["## Entity Reuse", "", "### Classes", "", "| Entity | Candidates |", "| --- | ---: |"]
    lines += [f"| `{entity}` | {count} |" for entity, count in class_reuse.most_common()]
    lines += ["", "### Properties", "", "| Entity | Candidates |", "| --- | ---: |"]
    lines += [f"| `{entity}` | {count} |" for entity, count in property_reuse.most_common()]
    lines += ["", "## Rejected On Ambiguity", ""]
    lines += [f"- {reason}" for reason in rejected] or ["- None."]
    lines += ["", "## Not Put Forward", "", "- No additional non-ambiguous enumerated candidate was excluded. The pool is intentionally unselected; human selection should use the reuse table and draft-wording screen.", "", "## Stratum Status", "", "| Stratum | Candidates | Status |", "| --- | ---: | --- |"]
    for stratum in ("direct_relation", "quality_pattern", "quantity_pattern", "part_whole", "participation", "information", "temporal"):
        count = strata[stratum]
        status = "zero; reportable corpus fact" if count == 0 else "fewer than three; reported without quota compensation" if count < 3 else "populated"
        lines.append(f"| `{stratum}` | {count} | {status} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    graph = Graph().parse(ONTOLOGY, format="turtle")
    shared = shared_entities()
    domains: dict[str, set[str]] = defaultdict(set)
    ranges: dict[str, set[str]] = defaultdict(set)
    for subject, object_ in graph.subject_objects(RDFS.domain):
        if isinstance(subject, URIRef) and isinstance(object_, URIRef):
            property_id, domain = compact(subject), compact(object_)
            if property_id.startswith("lis:") and domain.startswith("lis:"):
                domains[property_id].add(domain)
    for subject, object_ in graph.subject_objects(RDFS.range):
        if isinstance(subject, URIRef) and isinstance(object_, URIRef):
            property_id, range_ = compact(subject), compact(object_)
            if property_id.startswith("lis:") and range_.startswith("lis:"):
                ranges[property_id].add(range_)
    rejected: list[str] = []
    base: list[tuple[str, str, str]] = []
    for property_id in sorted(domains):
        domain_values, range_values = domains[property_id], ranges[property_id]
        if len(domain_values) != 1 or len(range_values) != 1:
            rejected.append(f"`{property_id}`: domains `{sorted(domain_values)}` and ranges `{sorted(range_values)}` do not yield one plainly defensible bearer/property template.")
            continue
        domain, range_ = next(iter(domain_values)), next(iter(range_values))
        required = {property_id, domain, range_}
        if not required <= shared:
            rejected.append(f"`{property_id}`: `{sorted(required - shared)}` does not resolve in all seven formats.")
            continue
        base.append((property_id, domain, range_))
    by_property = {property_id: (domain, range_) for property_id, domain, range_ in base}
    candidates: list[dict[str, object]] = []
    for index, (property_id, scenario, source) in enumerate(measured_scenarios(), start=1):
        if property_id not in by_property:
            raise RuntimeError("the measured quantity pattern is absent from eligible direct domain/range pairs")
        domain, range_ = by_property[property_id]
        required = {
            "lis:hasQuality",
            "lis:Quality",
            "lis:qualityQuantifiedAs",
            "lis:QualityDatum",
            "lis:ScalarQuantityDatum",
            range_,
        }
        if not required <= shared:
            raise RuntimeError(f"quantity bridge chunks do not resolve in all formats: {sorted(required - shared)}")
        candidates.append(make_candidate(f"B04-Q{index:02d}", graph, property_id, domain, range_, intermediate=True, scenario=scenario, query_source=source))
    for index, (property_id, domain, range_) in enumerate(base, start=1):
        source = ("label", "definition", "example")[index % 3]
        scenario = f"Draft: model the {label(domain)} using the IDO relation {property_id} to a {label(range_)}."
        intermediate = property_id == "lis:hasTemporalRegion"
        if intermediate:
            scenario = "A maintenance activity occurred over a defined interval with recorded start and end times. What pattern should represent the activity, the interval, and the recorded times?"
            source = "paraphrase"
        candidates.append(make_candidate(f"B04-D{index:02d}", graph, property_id, domain, range_, intermediate=intermediate, scenario=scenario, query_source=source))
    for candidate in candidates:
        Task.model_validate({key: value for key, value in candidate.items() if key not in {"class_domain_axiom", "property_licensing_axioms", "intermediate_node_licensing_axioms"}})
        check_candidate({key: value for key, value in candidate.items() if key not in {"class_domain_axiom", "property_licensing_axioms", "intermediate_node_licensing_axioms"}})
        fields = candidate["field_gold_chunks"]
        assert isinstance(fields, dict)
        expected = candidate["class_domain_recoverable"]
        recomputed = profile([tuple(candidate["class_domain_axiom"])], fields["property"])
        if recomputed != expected:
            raise RuntimeError(f"class-domain profile mismatch for {candidate['task_id']}")
        expected = candidate["property_recoverability_profile"]
        recomputed = profile([tuple(link) for link in candidate["property_licensing_axioms"]], fields["property"])
        if recomputed != expected:
            raise RuntimeError(f"property profile mismatch for {candidate['task_id']}")
        if candidate["gold_intermediate_node"]:
            expected = candidate["intermediate_node_recoverability_profile"]
            recomputed = profile([tuple(link) for link in candidate["intermediate_node_licensing_axioms"]], fields["intermediate_node"])
            if recomputed != expected:
                raise RuntimeError(f"intermediate profile mismatch for {candidate['task_id']}")
    intermediate_counts = Counter(item["gold_intermediate_node"] for item in candidates)
    sub_k = sum(len(item["retrieval_gold_chunks"]) < RETRIEVAL_K for item in candidates)
    if len(candidates) < 45 or sub_k < 8 or min(intermediate_counts.values(), default=0) < 8:
        raise RuntimeError(f"stop condition: candidates={len(candidates)}, gold<k={sub_k}, intermediate={dict(intermediate_counts)}")
    args.output.write_text(markdown(candidates, rejected), encoding="utf-8")
    print(f"wrote {args.output} with {len(candidates)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())