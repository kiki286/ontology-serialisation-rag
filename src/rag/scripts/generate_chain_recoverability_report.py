"""Measure chain-aware recoverability for every Batch 02 supported subsumption.

This is an authoring-time measurement only. It does not select candidates or
write benchmark task files, and it makes no network, API, or model calls.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from rdflib import Graph

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import BENCHMARK_DIR, FORMATS  # noqa: E402
from experiment.recoverability import assess_draft_recoverability  # noqa: E402
from experiment.schemas import load_tasks  # noqa: E402
from scripts.generate_supported_subsumption_candidates import (  # noqa: E402
    CANONICAL_TURTLE,
    EXPECTED_PROFILE,
    draft,
    enumerate_candidates,
    screen_prose,
)


def profile_text(profile: dict[str, object]) -> str:
    return ", ".join(f"{fmt}={str(profile[fmt]).lower()}" for fmt in FORMATS)


def link_text(link: list[str]) -> str:
    return f"{link[0]} -> {link[2]}"


def measure_candidates(graph: Graph) -> list[dict[str, object]]:
    candidates = enumerate_candidates(graph)
    counters = Counter(candidate["source"] for candidate in candidates)
    seen = Counter()
    for candidate in candidates:
        source = candidate["source"]
        seen[source] += 1
        candidate_id = f"B02-{source[0].upper()}{seen[source]:02d}"
        subject, object_ = candidate["subject"], candidate["object"]
        path = candidate["path"]
        chain_path = path if source == "entailed" else None
        task = draft(subject, object_, path=chain_path)
        assessment = assess_draft_recoverability(task)
        if assessment["errors"]:
            raise RuntimeError(f"{subject} -> {object_}: {assessment['errors']}")
        link_prose = [screen_prose(graph, child, parent) for child, parent in zip(path, path[1:])]
        leaked = sum(screen["direction"] == "states_axiom" for screen in link_prose)
        candidate.update(
            {
                "id": candidate_id,
                "gold_chunks": task["gold_chunks"],
                "assessment": assessment,
                "link_prose": link_prose,
                "chain_prose": (
                    "fully leaked" if leaked == len(link_prose)
                    else "clean" if leaked == 0
                    else "partially leaked"
                ),
                "states_axiom_links": leaked,
                # Batch 02 used a direct triple and only endpoint gold for entailed items.
                "changed_from_batch_02": source == "entailed" or candidate_id == "B02-A41",
            }
        )
    if sum(counters.values()) != 93:
        raise RuntimeError(f"expected 93 candidates, found {sum(counters.values())}")
    return candidates


def stored_profile_diffs() -> tuple[int, list[tuple[str, dict[str, bool], dict[str, bool]]]]:
    diffs = []
    profiled = 0
    for path in (BENCHMARK_DIR / "tasks.yaml", BENCHMARK_DIR / "tasks_60.yaml"):
        if not path.is_file():
            continue
        for task in load_tasks(path):
            if task.recoverability_profile is None:
                continue
            profiled += 1
            recomputed = assess_draft_recoverability(task)["profile"]
            if recomputed != task.recoverability_profile:
                diffs.append((task.task_id, task.recoverability_profile, recomputed))
    return profiled, diffs


def prose_cell(candidate: dict[str, object]) -> str:
    cells = []
    for link, screen in zip(candidate["assessment"]["per_link"], candidate["link_prose"]):
        cells.append(f"{link_text(link['link'])}: {screen['direction']}")
    return "<br>".join(cells)


def recovery_cell(candidate: dict[str, object]) -> str:
    return "<br>".join(
        f"{link_text(result['link'])}: {profile_text(result['profile'])}"
        for result in candidate["assessment"]["per_link"]
    )


def build_report(candidates: list[dict[str, object]], profiled: int, diffs: list[tuple[str, dict[str, bool], dict[str, bool]]]) -> str:
    chains = [candidate for candidate in candidates if candidate["source"] == "entailed"]
    prose_counts = Counter(candidate["chain_prose"] for candidate in chains)
    deviations = [
        candidate for candidate in candidates
        if candidate["assessment"]["profile"] != EXPECTED_PROFILE
    ]
    at_least_five = [candidate for candidate in chains if len(candidate["gold_chunks"]) >= 5]

    lines = [
        "# Chain-Aware Recoverability Extension",
        "",
        "Status: local implementation and measurement completed. No API or Ollama call was made. This report does not select or author benchmark items and does not modify `tasks.yaml` or `tasks_60.yaml`.",
        "",
        "## W1: Matcher Correction and Stored Profiles",
        "",
        "The OFN matcher now compares complete named expressions (and explicit union members) rather than substrings. The ELOT matcher accepts a named superclass or named disjunction member, but rejects restriction fillers such as `hasFunctionalPart some FunctionalObject`.",
        "",
        f"Recomputed **{profiled}** stored verification profiles across `tasks.yaml` and `tasks_60.yaml`: **{len(diffs)}** differences.",
        "",
    ]
    if diffs:
        lines += ["| Task | Stored | Corrected |", "| --- | --- | --- |"]
        lines += [f"| {task_id} | {profile_text(stored)} | {profile_text(recomputed)} |" for task_id, stored, recomputed in diffs]
    else:
        lines += ["No stored profile changed. In particular, T04 retains `elot-org-ancestors=false, else true`."]

    lines += [
        "",
        "## W2: Chain Representation and Gold Completeness",
        "",
        "`licensing_axiom` now accepts either one triple or an ordered, connected list of triples. The assessor reports every link profile and computes the candidate profile as their conjunction. A chain item fails model validation when any link subject or object is absent from `gold_chunks`; this is an authoring-time assertion and does not alter retrieval or oracle behavior.",
        "",
        "## W3: Per-Link Prose Screening",
        "",
        "Each entailed candidate was screened at every direct chain link using its link subject's definition/usage-note prose. `states_axiom` denotes a subject whose prose names the link parent genus.",
        "",
        f"Entailed chains: **{len(chains)}**. Fully leaked: **{prose_counts['fully leaked']}**. Partially leaked: **{prose_counts['partially leaked']}**. Clean: **{prose_counts['clean']}**.",
        "",
        "| ID | Chain | Per-link prose screen | `states_axiom` links | Chain classification |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for candidate in chains:
        lines.append(
            f"| {candidate['id']} | {' -> '.join(candidate['path'])} | {prose_cell(candidate)} | "
            f"{candidate['states_axiom_links']} | {candidate['chain_prose']} |"
        )

    lines += [
        "",
        "## W4: Revised 93-Candidate Profiles",
        "",
        "All profiles below use the corrected matcher. Entailed candidates use every direct link in their canonical path and include all path classes in `gold_chunks`. `Changed from Batch 02` marks chain candidates whose prior direct-triple result was replaced and the corrected ELOT false-positive item B02-A41.",
        "",
        "| ID | Source | Statement | Gold chunks | Corrected profile | Per-link recovery | Chain prose | Changed from Batch 02 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidates:
        assessment = candidate["assessment"]
        statement = f"{candidate['subject']} SubClassOf {candidate['object']}"
        lines.append(
            f"| {candidate['id']} | {candidate['source']} | `{statement}` | {', '.join(candidate['gold_chunks'])} | "
            f"{profile_text(assessment['profile'])} | {recovery_cell(candidate)} | "
            f"{candidate['chain_prose']} ({candidate['states_axiom_links']}/{len(candidate['path']) - 1}) | "
            f"{'yes' if candidate['changed_from_batch_02'] else 'no'} |"
        )

    lines += [
        "",
        f"Profile deviations from `elot-org-ancestors=false, else true`: **{len(deviations)}**.",
    ]
    if deviations:
        lines.append("| ID | Profile | Notes |")
        lines.append("| --- | --- | --- |")
        for candidate in deviations:
            lines.append(
                f"| {candidate['id']} | {profile_text(candidate['assessment']['profile'])} | "
                "Investigate before selection. |"
            )
    else:
        lines.append("No deviations remain after the matcher correction and chain-aware assessment.")

    lines += [
        "",
        "## W5: Chain Length and Retrieval Gold",
        "",
        "| ID | Links | Gold-chunk count | Gold chunks |",
        "| --- | ---: | ---: | --- |",
    ]
    for candidate in chains:
        lines.append(
            f"| {candidate['id']} | {len(candidate['path']) - 1} | {len(candidate['gold_chunks'])} | "
            f"{', '.join(candidate['gold_chunks'])} |"
        )
    lines += [
        "",
        "Gold set size >= 5: "
        + (", ".join(candidate["id"] for candidate in at_least_five) if at_least_five else "none")
        + ". With `top-k = 5`, these items require the retriever to return the entire gold set for `recall@5 = 1.0`; this is reported as a selection consideration, not an exclusion rule.",
        "",
        "## Open Decisions",
        "",
        "- Whether prose-leaked chains are excluded from selection or retained as a deliberate contrast class.",
        "- Whether chain items with gold sets of five or more are acceptable given `top-k = 5`.",
        "- Whether the corpus-level `states_axiom` result warrants revisiting mechanism strata.",
        "",
        "## Candidate Methodology Log Entries (Not Written)",
        "",
        "- Corrected unsound substring matching, the same defect class as property-chunk crowding.",
        "- Defined chain-aware recoverability as conjunction of direct-link recoverability across the gold-chunk union.",
        "- Measured genus-differentia prose leakage per chain link as a corpus property independent of experimental results.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=RAG_DIR.parents[1] / "docs" / "findings" / "chain-recoverability-extension.md",
    )
    args = parser.parse_args(argv)

    graph = Graph().parse(CANONICAL_TURTLE, format="turtle")
    candidates = measure_candidates(graph)
    profiled, diffs = stored_profile_diffs()
    args.output.write_text(build_report(candidates, profiled, diffs), encoding="utf-8")
    print(f"wrote {args.output} for {len(candidates)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())