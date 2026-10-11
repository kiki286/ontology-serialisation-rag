"""Rebuild the paper allocation with measured, non-authoring candidate metadata."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import BENCHMARK_DIR, TASKS_PATH  # noqa: E402
from experiment.schemas import load_tasks  # noqa: E402

MEASUREMENTS_PATH = BENCHMARK_DIR / "authoring_constraint_measurements.json"
DEFAULT_OUTPUT = BENCHMARK_DIR / "authoring_allocation.yaml"


def apply_measurement(row: dict[str, object], measured: dict[str, object]) -> None:
    row["gold_chunks"] = measured["gold_chunks"]
    row.pop("gold_chunks_by_format", None)
    row["licensing_axiom"] = measured["licensing_axiom"]
    row["licensing_axiom_status"] = _determinate_status(measured["licensing_axiom"])
    row["recoverability_profile"] = measured["profile"]
    if row["gold_label"] == "contradicted":
        row["annotation_prose_screen"] = measured["prose_screen"]


def _determinate_status(licensing_axiom: object) -> str:
    """asserted for a single directly-serialized triple, entailed_chain for a chain.

    Mirrors Task.derived_licensing_axiom_status for the supported/contradicted rows.
    Undetermined rows keep the ``hypothetical`` status already in the template.
    """
    is_chain = isinstance(licensing_axiom, list) and bool(licensing_axiom) and isinstance(
        licensing_axiom[0], list
    )
    return "entailed_chain" if is_chain else "asserted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = yaml.safe_load(args.template.read_text(encoding="utf-8"))
    measurements = yaml.safe_load(MEASUREMENTS_PATH.read_text(encoding="utf-8"))
    pilot = {task.task_id: task.model_dump(exclude_none=True) for task in load_tasks(TASKS_PATH)}
    tiers = measurements["tiers"]

    split_subsumption = [
        item for item in tiers["subsumption"]["candidates"] if not item["uniform"]
    ]
    supported_rows = [row for row in rows if row.get("gold_label") == "supported"]
    for index, row in enumerate(supported_rows):
        apply_measurement(row, split_subsumption[index % len(split_subsumption)])
        row["mechanism"] = "subsumption" if index < len(supported_rows) - 1 else "explicit_axiom"

    bare = measurements["bare_disjointness_prose_screen"]["candidates"]
    domain_range = tiers["direct_domain_range"]["candidates"]
    composed = tiers["composed_domain_range_disjointness"]["candidates"]
    functional = tiers["functional_property"]["candidates"]
    groups = {
        "bare_disjointness": iter(bare[:3]),
        "direct_domain_range": iter(domain_range[:3]),
        "composed_domain_range_disjointness": iter(composed[:1]),
        "functional_property": iter(functional),
    }
    for row in (row for row in rows if row.get("gold_label") == "contradicted"):
        if row["mechanism"] == "composed_domain_range_disjointness" and row["task_id"] == "C07":
            source = copy.deepcopy(pilot["T03"])
            row["gold_chunks"] = source["gold_chunks"]
            row["licensing_axiom"] = source["licensing_axiom"]
            row["licensing_axiom_status"] = _determinate_status(source["licensing_axiom"])
            row["recoverability_profile"] = source["recoverability_profile"]
            row["annotation_prose_screen"] = source["annotation_prose_screen"]
            continue
        apply_measurement(row, next(groups[row["mechanism"]]))

    header = (
        "# Paper allocation only. Placeholder wording is not a benchmark item.\n"
        "# Profile, prose-screen, gold-chunk, and licensing-axiom fields are measured local candidates.\n"
        "# Run: python -m scripts.verify_authoring_constraints --tasks experiment/benchmark/authoring_allocation.yaml\n\n"
    )
    args.output.write_text(header + yaml.safe_dump(rows, sort_keys=False), encoding="utf-8")
    print(f"wrote {args.output} with measured candidate metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())