"""Offline regrade + covariate backfill for an existing post-retrieval run (WI1, WI5).

Decouples grading from generation: this reads a ``postretrieval_raw.csv``, rebuilds
the typed prediction from the stored ``pred_*`` columns, re-runs the *pure* graders,
and recomputes covariates — with **no network access on this path**. Regrading a
completed run therefore costs nothing and can be repeated freely.

What it (re)computes per row:
  * grade_* (per-field, with N/A for excluded fields), grade_n_fields,
    grade_exact_match, grade_partial_credit  — the WI2 gold-driven denominator.
  * context_chunk_ids (JSON), context_char_len                 — WI5/WI7 covariates.
  * covered_<field>, coverage_all, coverage_frac               — WI5 coverage.

Chunk ids are recovered exactly from the ``# Chunk: <id>`` labels already present in
each stored ``user_content``, so the pilot needs no retrieval re-run and there is no
chunker-drift risk. A hard integrity check asserts the recovered chunk count matches
the stored ``n_context_chunks`` for every row.

Run from src/rag:
    python -m experiment.rescore experiment/results/superseded/postretrieval-trial-4/postretrieval_raw.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from experiment.coverage import (
    compute_coverage,
    context_block_from_user_content,
    context_chunk_ids_from_content,
    coverage_columns,
)
from experiment.grading import (
    SLOT_FIELDS,
    grade_slot_filling,
    grade_slot_filling_missing,
    grade_verification,
)
from experiment.schemas import (
    ParseError,
    SlotFillingResponse,
    Task,
    VerificationResponse,
    load_tasks,
    parse_response,
)


# ---------------------------------------------------------------------------
# CSV value coercion (stored strings -> typed prediction)
# ---------------------------------------------------------------------------
def _truthy(value: object) -> bool:
    return str(value).strip().lower() == "true"


def _blank_to_none(value: object) -> str | None:
    s = "" if value is None else str(value).strip()
    return s or None


def rebuild_verification_pred(row: dict) -> VerificationResponse | None:
    """Reconstruct the verification prediction from stored columns (None if missing)."""
    if not _truthy(row.get("parse_ok")):
        return None
    label = _blank_to_none(row.get("pred_label"))
    if label is None:
        return None
    return VerificationResponse.model_validate({"label": label})


def rebuild_slot_pred(row: dict) -> SlotFillingResponse | None:
    """Reconstruct the slot-filling prediction from stored columns (None if missing)."""
    if not _truthy(row.get("parse_ok")):
        return None
    return SlotFillingResponse.model_validate(
        {
            "class": row.get("pred_class"),
            "property": row.get("pred_property"),
            "intermediate_node": _truthy(row.get("pred_intermediate_node")),
            "supporting_chunks": {
                "class": _blank_to_none(row.get("pred_support_class")),
                "property": _blank_to_none(row.get("pred_support_property")),
                "intermediate_node": _blank_to_none(row.get("pred_support_intermediate")),
            },
        }
    )


def _reparse_failed_row(row: dict):
    """Re-parse a previously-failed row's stored raw_response with the CURRENT schema.

    Offline. Heals rows that failed under an earlier, buggier parser (e.g. the
    SupportingChunks 'Field required [type=missing]' bug): the real answer is in
    raw_response even though pred_* are blank. Returns None if it still will not parse.
    """
    raw = row.get("raw_response")
    if not raw:
        return None
    try:
        return parse_response(row["task_type"], raw)
    except ParseError:
        return None


# ---------------------------------------------------------------------------
# Per-row regrade + covariate backfill (pure, no network)
# ---------------------------------------------------------------------------
def regrade_row(row: dict, task: Task) -> dict:
    """Return a new row: original columns + regraded grade_* + backfilled covariates."""
    out = dict(row)
    # WI3: carry the answer taxonomy + query wording (older raw CSVs lack the columns).
    out["reasoning_type"] = task.reasoning_type
    out["query_source"] = task.query_source
    out["mechanism"] = task.mechanism

    if task.task_type == "verification":
        pred = rebuild_verification_pred(row)
        if pred is None:
            pred = _reparse_failed_row(row)  # heal rows failed by an earlier parser bug
            if pred is not None:
                out["pred_label"] = pred.label
                out["parse_ok"], out["parse_error"] = True, "recovered by rescore re-parse"
        if pred is not None:
            grade = grade_verification(task, pred)
        else:
            grade = {
                "gold_label": task.gold_label,
                "pred_label": None,
                "correct": 0,
                "answered": 0,
                "selective_correct": 0,
            }
        for key, value in grade.items():
            out[f"grade_{key}"] = value
    else:
        pred = rebuild_slot_pred(row)
        if pred is None:
            pred = _reparse_failed_row(row)
            if pred is not None:
                out.update(
                    {
                        "pred_class": pred.cls,
                        "pred_property": pred.prop,
                        "pred_intermediate_node": pred.intermediate_node,
                        "pred_support_class": pred.supporting_chunks.cls,
                        "pred_support_property": pred.supporting_chunks.prop,
                        "pred_support_intermediate": pred.supporting_chunks.intermediate_node,
                        "parse_ok": True,
                        "parse_error": "recovered by rescore re-parse",
                    }
                )
        grade = grade_slot_filling(task, pred) if pred is not None else grade_slot_filling_missing(task)
        for key, value in grade.items():
            out[f"grade_{key}"] = value

    # WI5/WI7 covariates, recovered offline from the stored user_content.
    user_content = row.get("user_content") or ""
    chunk_ids = context_chunk_ids_from_content(user_content)
    declared = int(row["n_context_chunks"]) if row.get("n_context_chunks") not in (None, "") else None
    if declared and not user_content:
        raise ValueError(
            f"{task.task_id}/{row.get('format')}/{row.get('condition')}: user_content is empty. "
            "The committed run outputs withhold the prompt text because it carries the "
            "licensed ontology, so rescore cannot recover the context covariates from them."
        )
    if declared is not None and len(chunk_ids) != declared:
        raise ValueError(
            f"{task.task_id}/{row.get('format')}/{row.get('condition')}: recovered "
            f"{len(chunk_ids)} chunk labels but n_context_chunks={declared}"
        )
    out["context_chunk_ids"] = chunk_ids
    out["context_char_len"] = len(context_block_from_user_content(user_content, task))
    out.update(compute_coverage(task, chunk_ids))
    return out


def rescore_rows(rows: list[dict], tasks: list[Task] | None = None) -> list[dict]:
    """Regrade + backfill every row. Pure function of (rows, task definitions)."""
    task_map = {t.task_id: t for t in (tasks if tasks is not None else load_tasks())}
    out: list[dict] = []
    for row in rows:
        task = task_map.get(row["task_id"])
        if task is None:
            raise KeyError(f"row references unknown task_id {row['task_id']!r}")
        out.append(regrade_row(row, task))
    return out


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def load_raw_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _csv_value(value: object) -> object:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return "" if value is None else value


# Covariate columns appended to the raw schema (order after the originals).
_NEW_COLUMNS = [
    "reasoning_type",
    "query_source",
    "mechanism",
    "grade_n_fields",
    "context_char_len",
    "context_chunk_ids",
    *coverage_columns(),
]


def write_scored_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    for col in _NEW_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline regrade + covariate backfill of a postretrieval_raw.csv (no network)."
    )
    parser.add_argument("raw_csv", type=Path, help="path to an existing postretrieval_raw.csv")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output path (default: <raw_dir>/postretrieval_rescored.csv)",
    )
    parser.add_argument(
        "--no-diagnostics",
        action="store_true",
        help="skip writing the diagnostics report",
    )
    args = parser.parse_args(argv)

    if not args.raw_csv.exists():
        raise SystemExit(f"no such file: {args.raw_csv}")
    out_path = args.out or (args.raw_csv.parent / "postretrieval_rescored.csv")

    tasks = load_tasks()
    rows = load_raw_csv(args.raw_csv)
    scored = rescore_rows(rows, tasks)
    write_scored_csv(scored, out_path)
    print(f"  rescored {len(scored)} rows -> {out_path}")

    if not args.no_diagnostics:
        from experiment import diagnostics

        report = diagnostics.build_report(scored, tasks)
        diag_path = args.raw_csv.parent / "postretrieval_diagnostics.json"
        diag_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        diagnostics.print_report(report)
        print(f"\n  diagnostics -> {diag_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
