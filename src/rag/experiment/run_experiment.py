"""CLI entry point for the format x task comparison study.

Stages:
  smoke         - validate tasks + prefix equivalence, then run the two gating
                  single calls (1a verification, 1b slot-filling) on Turtle/oracle.
  retrieval     - RQ1: Recall@k / secondary gold Recall@k / MRR / nDCG@k per format.
  postretrieval - RQ2: both task types x formats x conditions x models, graded.

Run from src/rag:  python -m experiment.run_experiment --stage smoke
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `app` and `experiment` importable regardless of CWD.
RAG_DIR = Path(__file__).resolve().parent.parent
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

import argparse
import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

from dotenv import load_dotenv

from experiment.config import (
    ANTHROPIC_CACHE_CORPUS,
    TASKS_PATH,
    ALL_CONDITIONS,
    ALL_SELECTABLE_FORMATS,
    CONDITIONS,
    DEFAULT_POSTRETRIEVAL_N_TRIALS,
    ELOT_ANCESTOR_FORMAT,
    EMBEDDING_MODEL,
    ENV_PATH,
    FLOOR_CONDITIONS,
    FLOOR_FORMAT_SENTINEL,
    FORMATS,
    MODELS,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_CTX_WHOLE_CONTEXT,
    ORACLE_PAD_SEED,
    ORACLE_PAD_STRATEGIES,
    RESULTS_DIR,
    RETRIEVAL_K,
    SEED,
    POSTRETRIEVAL_SEEDS,
    SYSTEM_PROMPTS,
    TASK_TYPES,
    TEMPERATURE,
)
from experiment.context_block import assert_prefix_equivalence, extract_prefix_block
from experiment import corpus_index, retrieval
from experiment.pricing import CACHE_PRICING_SNAPSHOT_DATE, PRICING_SNAPSHOT_DATE
from experiment.schemas import Task, load_tasks, validate_gold_chunks_resolve

load_dotenv(dotenv_path=ENV_PATH)

from app.document_loaders import (  # noqa: E402  (after path setup)
    RETRIEVAL_INDEX_EXCLUDED_ENTITY_IDS,
    RETRIEVAL_INDEX_EXCLUDED_ENTITY_TYPES,
    RETRIEVAL_INDEX_FILTER_VERSION,
    get_loader_version,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_next_trial_dir(stage: str) -> Path:
    """Next results/<stage>-trial-N directory (mirrors eval/main.py)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    existing = [
        int(d.name.rsplit("-", 1)[-1])
        for d in RESULTS_DIR.iterdir()
        if d.is_dir() and d.name.startswith(f"{stage}-trial-") and d.name.rsplit("-", 1)[-1].isdigit()
    ]
    n = (max(existing) + 1) if existing else 1
    trial_dir = RESULTS_DIR / f"{stage}-trial-{n}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    return trial_dir


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(RAG_DIR), stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return None


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))

    def _csv_value(value):
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def write_manifest(trial_dir: Path, stage: str, args, tasks: list[Task], extra: dict) -> None:
    task_file = _task_file(args)
    manifest = {
        "stage": stage,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        # B6: WHICH benchmark file this run read, and its exact content. Two task
        # files now exist (the 5-task pilot and the 60-task set), and a run that
        # records neither cannot be attributed to a benchmark version afterwards.
        # The hash is the load-bearing half: the path can be reused while the
        # contents change underneath it.
        "task_file": str(task_file),
        "task_file_sha256": hashlib.sha256(task_file.read_bytes()).hexdigest(),
        # B5/B6: the rates any cost figure derived from this run must be read against.
        "pricing_snapshot_date": PRICING_SNAPSHOT_DATE,
        "cache_pricing_snapshot_date": CACHE_PRICING_SNAPSHOT_DATE,
        "seed": SEED,
        "temperature": TEMPERATURE,
        "embedding_model": EMBEDDING_MODEL,
        "retrieval_k": args.k,
        "formats": args.formats,
        "models": args.models,
        "conditions": args.conditions,
        "task_types": args.task_types,
        "n_tasks": len(tasks),
        "task_ids": [t.task_id for t in tasks],
        "elot_ancestor_format": ELOT_ANCESTOR_FORMAT,
        "retrieval_index_filter_version": RETRIEVAL_INDEX_FILTER_VERSION,
        "retrieval_index_excluded_entity_types": sorted(
            RETRIEVAL_INDEX_EXCLUDED_ENTITY_TYPES
        ),
        "retrieval_index_excluded_entity_ids": sorted(
            RETRIEVAL_INDEX_EXCLUDED_ENTITY_IDS
        ),
        "retrieval_index_excludes_elot_sections": True,
        "system_prompts": {tt: SYSTEM_PROMPTS[tt].name for tt in TASK_TYPES},
        # The floor sentinel is not a real format and has no chunker to version.
        "loader_versions": {
            fmt: get_loader_version("entity-based", fmt)
            for fmt in args.formats
            if fmt != FLOOR_FORMAT_SENTINEL
        },
        **extra,
    }
    (trial_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _task_file(args) -> Path:
    """The benchmark file this run reads. Explicit because TWO now exist."""
    return Path(getattr(args, "task_file", None) or TASKS_PATH)


def select_tasks(args) -> list[Task]:
    tasks = load_tasks(_task_file(args))
    if args.task_types:
        tasks = [t for t in tasks if t.task_type in args.task_types]
    if args.tasks:
        wanted = set(args.tasks)
        tasks = [t for t in tasks if t.task_id in wanted]
    if not tasks:
        raise SystemExit("No tasks selected after filtering.")
    return tasks


def check_prefix_equivalence(formats: list[str]) -> dict:
    blocks = {fmt: extract_prefix_block(fmt) for fmt in formats}
    shared = assert_prefix_equivalence(blocks)
    print(f"  prefix equivalence OK: {len(shared)} shared prefixes across {formats}")
    return shared


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def stage_smoke(args) -> int:
    from experiment import grading, postretrieval

    print("=== Stage 1: smoke ===")
    tasks = load_tasks()
    print(f"  loaded + validated {len(tasks)} tasks")

    check_prefix_equivalence(FORMATS)
    validate_gold_chunks_resolve(
        tasks,
        corpus_index.entity_ids_by_format(args.formats),
        corpus_index.retrieval_entity_ids_by_format(args.formats),
    )
    print("  gold_chunks resolve in all formats")
    grading.validate_slot_gradeability(tasks)
    print("  slot gradeability OK (no unsatisfiable graded field)")

    # NOTE: smoke hard-asserts the model returns the exact gold label below. An
    # 8B local model (Ollama) may not, which would lock Stage 2. Smoke defaults
    # to gpt-4o-mini; run local models via --stage postretrieval, not smoke.
    model = args.models[0]
    verif = next((t for t in tasks if t.task_type == "verification"), None)
    slot = next((t for t in tasks if t.task_type == "slot_filling"), None)
    if verif is None or slot is None:
        raise SystemExit("smoke needs at least one verification and one slot_filling task")

    # 1a: verification
    print(f"\n  [1a] {verif.task_id} verification, oracle, turtle, {model}")
    row_a, grade_a = postretrieval.run_one(verif, "turtle", "oracle", model)
    print(f"      response: {row_a['raw_response']}")
    assert row_a["parse_ok"], f"1a response did not parse: {row_a['parse_error']}"
    assert grade_a["pred_label"] == verif.gold_label, (
        f"1a expected label {verif.gold_label!r}, got {grade_a['pred_label']!r}"
    )
    print(f"      OK: label == {verif.gold_label}")

    # 1b: slot-filling (harder response schema)
    print(f"\n  [1b] {slot.task_id} slot_filling, oracle, turtle, {model}")
    row_b, grade_b = postretrieval.run_one(slot, "turtle", "oracle", model)
    print(f"      response: {row_b['raw_response']}")
    assert row_b["parse_ok"], f"1b response did not parse/validate: {row_b['parse_error']}"
    print(
        f"      OK: parsed + graded (exact_match={grade_b['exact_match']}, "
        f"partial_credit={grade_b['partial_credit']:.2f})"
    )

    print("\n  Smoke passed. Stage 2 unlocked.")
    return 0


def stage_retrieval(args) -> int:
    print("=== RQ1: retrieval ===")
    tasks = select_tasks(args)
    validate_gold_chunks_resolve(
        tasks,
        corpus_index.entity_ids_by_format(args.formats),
        corpus_index.retrieval_entity_ids_by_format(args.formats),
    )

    rows = retrieval.run_retrieval(tasks, args.formats, args.k)
    scored = retrieval.aggregate_retrieval(rows)

    trial_dir = get_next_trial_dir("retrieval")
    write_csv(rows, trial_dir / "retrieval_raw.csv")
    write_csv(scored, trial_dir / "retrieval_scored.csv")
    write_manifest(trial_dir, "retrieval", args, tasks, {"n_calls": len(rows)})

    print(f"\n  Per-format means (task_type=ALL):")
    for s in scored:
        if s["task_type"] == "ALL":
            print(
                f"    {s['format']:>9}: recall@{args.k}={s['recall_at_k']:.3f} "
                f"gold_recall@{args.k}={s['gold_recall_at_k']:.3f} "
                f"mrr={s['mrr']:.3f} ndcg@{args.k}={s['ndcg_at_k']:.3f}  (n={s['n']})"
            )
    print(f"\n  Results: {trial_dir}")
    return 0


def stage_postretrieval(args) -> int:
    from experiment import diagnostics, grading, postretrieval, pricing

    from experiment import floor as floor_mod

    print("=== RQ2: post-retrieval ===")
    tasks = select_tasks(args)

    # WI2: a floor-only run consults no corpus, so the format arms are not merely
    # unused — they are undefined. Skip corpus/gold validation (and the loader
    # version record) so the floor stays runnable and interpretable independently
    # of any format's availability.
    floor_conditions = [c for c in args.conditions if c in FLOOR_CONDITIONS]
    context_conditions = [c for c in args.conditions if c not in FLOOR_CONDITIONS]
    floor_only = bool(floor_conditions) and not context_conditions
    if floor_only:
        args.formats = [FLOOR_FORMAT_SENTINEL]
        print(f"  floor-only run: conditions={floor_conditions}, no corpus consulted")
    else:
        validate_gold_chunks_resolve(
            tasks,
            corpus_index.entity_ids_by_format(args.formats),
            corpus_index.retrieval_entity_ids_by_format(args.formats),
        )
    grading.validate_slot_gradeability(tasks)

    if args.n_trials < 1:
        raise SystemExit("--n-trials must be >= 1")
    if args.n_trials > len(POSTRETRIEVAL_SEEDS):
        raise SystemExit(
            f"--n-trials={args.n_trials} requested, but only "
            f"{len(POSTRETRIEVAL_SEEDS)} post-retrieval seeds are configured."
        )
    seeds = POSTRETRIEVAL_SEEDS[: args.n_trials]
    _padded = "oracle_padded" in args.conditions

    # The trial directory is created BEFORE the loop so the checkpoint has
    # somewhere to live from the first call onward. Previously it was created
    # after run_postretrieval returned, which meant an exception anywhere in the
    # loop discarded every completed row -- rows were held only in memory and no
    # directory existed yet. --resume points at an existing directory to continue
    # into its checkpoint instead of starting a new trial.
    if args.resume is not None:
        trial_dir = Path(args.resume)
        if not trial_dir.is_dir():
            raise SystemExit(f"--resume: {trial_dir} is not an existing directory")
        print(f"  resuming into {trial_dir}")
    else:
        trial_dir = get_next_trial_dir("postretrieval")
    checkpoint_path = trial_dir / postretrieval.CHECKPOINT_NAME

    raw_rows, scored = postretrieval.run_postretrieval(
        tasks,
        args.formats,
        args.conditions,
        args.models,
        args.k,
        seeds=seeds,
        pad_strategy=args.pad_strategy,
        checkpoint_path=checkpoint_path,
    )
    variance = postretrieval.summarise_variance(scored)

    # WI6: response-bias / degeneracy diagnostics, emitted on every scoring run.
    diagnostics_report = diagnostics.build_report(raw_rows, tasks)

    # WI2: floor tables. Written whenever a floor condition ran, alongside the
    # standard outputs rather than instead of them, so a mixed run stays readable.
    floor_summary = floor_mod.build_floor_summary(raw_rows)
    floor_by_task = floor_mod.build_floor_by_task(raw_rows)

    write_csv(raw_rows, trial_dir / "postretrieval_raw.csv")
    write_csv(scored, trial_dir / "postretrieval_scored.csv")
    write_csv(variance, trial_dir / "postretrieval_variance.csv")
    if floor_summary:
        write_csv(floor_summary, trial_dir / "floor_summary.csv")
        write_csv(floor_by_task, trial_dir / "floor_by_task.csv")
    (trial_dir / "postretrieval_diagnostics.json").write_text(
        json.dumps(diagnostics_report, indent=2), encoding="utf-8"
    )
    write_manifest(
        trial_dir,
        "postretrieval",
        args,
        tasks,
        {
            "n_calls": len(raw_rows),
            "n_trials": args.n_trials,
            "seeds": seeds,
            "trial_seed_map": {str(i): seed for i, seed in enumerate(seeds)},
            "seed_policy": "different seed per trial",
            "seed_determinism": {
                # OpenAI honours the pinned seed; Ollama seed support is weaker
                # (GPU nondeterminism), so its trials are best-effort only.
                m: ("best-effort" if "llama" in m.lower() else "pinned")
                for m in args.models
            },
            "ollama_num_ctx": OLLAMA_NUM_CTX,
            "ollama_num_ctx_whole_context": OLLAMA_NUM_CTX_WHOLE_CONTEXT,
            # B6: the KV cache quantisation the local arm ran under. Ollama reads
            # this from the environment of `ollama serve`, NOT from our request, so
            # it is recorded as observed-or-default rather than as a pinned value.
            "ollama_kv_cache_type": os.getenv("OLLAMA_KV_CACHE_TYPE", "f16 (default; unset)"),
            # B1/B2: caching is only sound while the loop runs a cell back-to-back.
            "anthropic_cache_corpus": ANTHROPIC_CACHE_CORPUS,
            "postretrieval_loop_order": "format -> model -> condition -> task -> trial",
            # WI2: floor provenance. ``floor_format_sentinel`` documents the value
            # written to the format column of floor rows; the floor is format-
            # independent by construction (no corpus => no serialisation).
            "floor_conditions_run": floor_conditions,
            "floor_only_run": floor_only,
            "floor_format_sentinel": FLOOR_FORMAT_SENTINEL if floor_conditions else None,
            "floor_retrieval_metrics": "null (undefined without a corpus)",
            "oracle_padded_condition": _padded,
            "oracle_pad_strategy": args.pad_strategy if _padded else None,
            "oracle_pad_seed": ORACLE_PAD_SEED if _padded else None,
            # WI7: reproducibility record of the per-task padding entities sampled for
            # the 'oracle_padded' condition (same set across formats; representative
            # count taken for the first selected format).
            "oracle_pad_entity_ids": (
                {t.task_id: postretrieval.task_padding_ids(t, args.formats[0], args.k) for t in tasks}
                if _padded and args.pad_strategy == "random"
                else None
            ),
            "cost_summary": pricing.summarise_cost(raw_rows),
        },
    )

    print(f"\n  Scored groups:")
    for s in scored:
        if s["task_type"] == "verification":
            print(
                f"    {s['task_id']:>4} {s['format']:>9} {s['condition']:>9} {s['model']:>12}: "
                f"acc={s.get('accuracy_mean', 0):.3f}+/-{s.get('accuracy_std', 0):.3f} "
                f"parse_err={s.get('parse_errors_mean', 0):.3f}+/-{s.get('parse_errors_std', 0):.3f}"
            )
        else:
            print(
                f"    {s['task_id']:>4} {s['format']:>9} {s['condition']:>9} {s['model']:>12}: "
                f"exact={s.get('exact_match_rate_mean', 0):.3f}+/-"
                f"{s.get('exact_match_rate_std', 0):.3f} "
                f"partial={s.get('mean_partial_credit_mean', 0):.3f}+/-"
                f"{s.get('mean_partial_credit_std', 0):.3f}"
            )
    print(f"\n  Variance summary:")
    for row in variance:
        print(
            f"    {row['metric']}: median_std={row['median_std']:.3f} "
            f"mean_std={row['mean_std']:.3f} max_std={row['max_std']:.3f} "
            f"nonzero={row['nonzero_std_cells']}/{row['n_cells']}"
        )
    print()
    diagnostics.print_report(diagnostics_report)
    if floor_summary:
        print()
        floor_mod.print_floor_summary(floor_summary)
    print(f"\n  Results: {trial_dir}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Format x task comparison study harness")
    parser.add_argument("--stage", required=True, choices=["smoke", "retrieval", "postretrieval"])
    parser.add_argument(
        "--formats",
        nargs="+",
        default=FORMATS,
        choices=ALL_SELECTABLE_FORMATS,
        help=(
            "default: the 7 core serialisations. Exploratory formats "
            f"({[f for f in ALL_SELECTABLE_FORMATS if f not in FORMATS]}) are "
            "selectable but excluded from the default headline comparison."
        ),
    )
    parser.add_argument("--models", nargs="+", default=None, help=f"default: {MODELS}")
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=CONDITIONS,
        choices=ALL_CONDITIONS,
        help=(
            "default: oracle retrieved. 'oracle_padded' is a robustness-appendix "
            "condition, off by default (select explicitly to reproduce it). "
            f"The floor conditions {FLOOR_CONDITIONS} run with no corpus at all and "
            "ignore --formats (the floor has no format arm)."
        ),
    )
    parser.add_argument("--task-types", nargs="+", default=TASK_TYPES, choices=TASK_TYPES, dest="task_types")
    parser.add_argument(
        "--task-file",
        type=Path,
        default=TASKS_PATH,
        dest="task_file",
        help=f"benchmark YAML to run; default: {TASKS_PATH.name}",
    )
    parser.add_argument("--tasks", nargs="+", default=None, help="restrict to these task_ids")
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help=(
            "postretrieval only: continue into an EXISTING results/postretrieval-trial-N "
            "directory, replaying calls already recorded in its checkpoint instead of "
            "re-issuing them. Re-run the identical command with this flag added after a "
            "crash. Without it a new trial directory is created."
        ),
    )
    parser.add_argument("--k", type=int, default=RETRIEVAL_K)
    parser.add_argument(
        "--n-trials",
        type=int,
        default=DEFAULT_POSTRETRIEVAL_N_TRIALS,
        help=(
            "number of seeded repetitions for --stage postretrieval; "
            f"default: {DEFAULT_POSTRETRIEVAL_N_TRIALS}"
        ),
    )
    # WI7: 'oracle_padded' is a condition (see --conditions), not a flag. This only
    # selects HOW that condition sources its padding chunks.
    parser.add_argument(
        "--pad-strategy",
        default="random",
        choices=ORACLE_PAD_STRATEGIES,
        dest="pad_strategy",
        help=(
            "oracle_padded padding source: 'random' (per-task shared sample, offline; "
            "default) or 'retrieved' (per-format top-ranked non-gold, needs embeddings)"
        ),
    )
    args = parser.parse_args(argv)

    if args.models is None:
        # smoke is a cheap single-model gate by default; full stages use all models.
        args.models = [MODELS[1]] if args.stage == "smoke" else MODELS

    if args.stage == "smoke":
        return stage_smoke(args)
    if args.stage == "retrieval":
        return stage_retrieval(args)
    return stage_postretrieval(args)


if __name__ == "__main__":
    raise SystemExit(main())
