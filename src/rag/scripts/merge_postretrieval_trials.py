"""Merge arm-split post-retrieval trials into one combined results directory.

Since 2026-08-20 the post-retrieval stage is run one model arm per invocation, so a
failure in the slow local arm cannot discard completed paid API calls. That produces
one trial directory per arm instead of one per study. This script recombines them.

    python -m scripts.merge_postretrieval_trials \\
        --sources experiment/results/postretrieval-trial-15 \\
                  experiment/results/postretrieval-trial-16 \\
                  experiment/results/postretrieval-trial-17 \\
                  experiment/results/postretrieval-trial-18 \\
        --output  experiment/results/postretrieval-combined-15-18

The merge is only valid if the arms ran the SAME protocol, so that is checked rather
than assumed: every protocol field in the manifests must agree across sources, and no
cell (task, format, condition, model, trial) may appear twice. Either condition fails
the run loudly instead of producing a quietly wrong combined set.

Derived tables are RECOMPUTED from the merged raw rows, never concatenated. Scored
rows, variance, diagnostics and the cost summary are all pure functions of the raw
rows, so recomputing them is what makes the combined directory equivalent to the
single directory an unsplit run would have written -- concatenating per-arm summaries
would instead average already-averaged values and silently change the numbers.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

# Raw rows carry the full prompt in ``user_content``; the default field size limit
# is far below that.
csv.field_size_limit(1 << 30)

# Fields that describe the PROTOCOL rather than the arm. All must agree for a merge
# to be meaningful. ``models``, ``n_calls``, ``cost_summary`` and the timestamp are
# deliberately absent -- those are expected to differ per arm and are recombined.
PROTOCOL_FIELDS = [
    "stage", "formats", "conditions", "task_types", "task_ids", "n_tasks",
    "n_trials", "seeds", "seed", "temperature", "embedding_model", "retrieval_k",
    "system_prompts", "loader_versions", "task_file", "task_file_sha256",
    "trial_seed_map", "oracle_pad_seed", "oracle_pad_strategy",
    "oracle_pad_entity_ids", "oracle_padded_condition", "elot_ancestor_format",
    "floor_format_sentinel", "floor_conditions_run", "floor_only_run",
    "floor_retrieval_metrics", "retrieval_index_filter_version",
    "retrieval_index_excluded_entity_ids", "retrieval_index_excluded_entity_types",
    "retrieval_index_excludes_elot_sections", "postretrieval_loop_order",
    "anthropic_cache_corpus", "ollama_num_ctx", "ollama_num_ctx_whole_context",
    "ollama_kv_cache_type", "seed_policy",
    "pricing_snapshot_date", "cache_pricing_snapshot_date",
]

# Per-model maps keyed by model name. These SHOULD differ between arms -- each arm
# only describes its own model -- so they are unioned rather than required to match.
PER_MODEL_FIELDS = ["seed_determinism"]


def _cell(row: dict) -> tuple:
    return (row["task_id"], row["format"], row["condition"], row["model"], row["trial_idx"])


def _load(source: Path) -> tuple[list[dict], dict]:
    raw_path = source / "postretrieval_raw.csv"
    manifest_path = source / "manifest.json"
    if not raw_path.exists():
        raise SystemExit(f"{source}: no postretrieval_raw.csv (did the run finish?)")
    if not manifest_path.exists():
        raise SystemExit(f"{source}: no manifest.json")
    with raw_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows, json.loads(manifest_path.read_text(encoding="utf-8"))


def _check_protocol(manifests: dict[str, dict]) -> list[str]:
    problems: list[str] = []
    reference_name = next(iter(manifests))
    reference = manifests[reference_name]
    for field in PROTOCOL_FIELDS:
        values = {
            name: json.dumps(manifest.get(field), sort_keys=True)
            for name, manifest in manifests.items()
        }
        if len(set(values.values())) > 1:
            detail = "; ".join(f"{name}={value[:60]}" for name, value in values.items())
            problems.append(f"protocol field {field!r} differs across sources: {detail}")
    if reference.get("stage") != "postretrieval":
        problems.append(
            f"{reference_name}: stage is {reference.get('stage')!r}, expected 'postretrieval'"
        )
    return problems


def _restore_types(rows: list[dict]) -> list[dict]:
    """Undo the CSV round-trip for the columns the summarisers read numerically.

    ``write_csv`` stringifies everything, so a merged set re-read from CSV would
    otherwise summarise strings. Only the fields the summarisers actually consume are
    converted; everything else stays as written so the raw CSV round-trips verbatim.
    """
    booleans = {"parse_ok"}
    integers = {"trial_idx"}
    for row in rows:
        for key in booleans:
            if key in row:
                row[key] = row[key] in ("True", "true", "1")
        for key in integers:
            if key in row and row[key] not in (None, ""):
                row[key] = int(row[key])
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--note", default=None, help="free-text note recorded in the merged manifest"
    )
    args = parser.parse_args(argv)

    from experiment import diagnostics, postretrieval, pricing
    from experiment.config import TASKS_PATH
    from experiment.run_experiment import write_csv
    from experiment.schemas import load_tasks

    sources = [Path(s) for s in args.sources]
    if len(sources) < 2:
        raise SystemExit("--sources needs at least two trial directories")

    per_source_rows: dict[str, list[dict]] = {}
    manifests: dict[str, dict] = {}
    for source in sources:
        rows, manifest = _load(source)
        per_source_rows[source.name] = rows
        manifests[source.name] = manifest
        models = sorted({row["model"] for row in rows})
        print(f"  {source.name}: {len(rows)} rows, models={models}")

    problems = _check_protocol(manifests)

    merged: list[dict] = []
    for rows in per_source_rows.values():
        merged.extend(rows)

    duplicates = [cell for cell, n in Counter(_cell(r) for r in merged).items() if n > 1]
    if duplicates:
        problems.append(
            f"{len(duplicates)} cell(s) appear in more than one source, e.g. "
            f"{duplicates[:3]}; the sources overlap and must not be merged"
        )
    if problems:
        raise SystemExit("refusing to merge:\n  - " + "\n  - ".join(problems))

    _restore_types(merged)
    # Deterministic order, independent of the order the arms happened to be run in.
    merged.sort(key=_cell)

    # Manifests written on Windows record ``task_file`` with backslash separators.
    # On POSIX a backslash is an ordinary filename character, not a separator, so
    # resolving the recorded value verbatim looks for a single file literally named
    # "experiment\\benchmark\\tasks_60.yaml" and the merge dies. Normalising first
    # makes those runs re-mergeable off Windows; a value recorded with forward
    # slashes is unchanged, and so is the merge output either way.
    recorded_task_file = manifests[sources[0].name].get("task_file") or TASKS_PATH
    task_file = Path(str(recorded_task_file).replace("\\", "/"))
    if not task_file.is_absolute():
        task_file = RAG_DIR / task_file
    tasks = load_tasks(task_file)

    scored = postretrieval._summarise_raw_rows(merged)
    variance = postretrieval.summarise_variance(scored)
    diagnostics_report = diagnostics.build_report(merged, tasks)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    write_csv(merged, output / "postretrieval_raw.csv")
    write_csv(scored, output / "postretrieval_scored.csv")
    write_csv(variance, output / "postretrieval_variance.csv")
    (output / "postretrieval_diagnostics.json").write_text(
        json.dumps(diagnostics_report, indent=2), encoding="utf-8"
    )

    reference = manifests[sources[0].name]
    manifest = {key: reference.get(key) for key in PROTOCOL_FIELDS}
    manifest["stage"] = "postretrieval (MERGED)"
    manifest["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["note"] = args.note or (
        "Merge of arm-split post-retrieval runs, same protocol/tasks/formats. "
        "Scored, variance, diagnostics and cost are recomputed from the merged raw "
        "rows, not concatenated."
    )
    manifest["source_trials"] = {
        name: sorted({row["model"] for row in rows})
        for name, rows in per_source_rows.items()
    }
    manifest["source_git_commits"] = {
        name: m.get("git_commit") for name, m in manifests.items()
    }
    for field in PER_MODEL_FIELDS:
        union: dict = {}
        for source_manifest in manifests.values():
            value = source_manifest.get(field)
            if isinstance(value, dict):
                union.update(value)
        manifest[field] = union or None
    manifest["models"] = sorted({row["model"] for row in merged})
    manifest["n_calls"] = len(merged)
    try:
        manifest["cost_summary"] = pricing.summarise_cost(merged)
    except Exception as exc:  # pragma: no cover - pricing shape varies by version
        manifest["cost_summary"] = {"error": f"could not recompute: {exc}"}
        manifest["per_arm_cost_summary"] = {
            name: m.get("cost_summary") for name, m in manifests.items()
        }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        f"\nwrote {output}: {len(merged)} raw rows, {len(scored)} scored rows, "
        f"{len(manifest['models'])} arms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
