"""Response-bias and degeneracy diagnostics (WI6).

The pilot's verification results were dominated by a response bias no existing output
would have surfaced: GPT-4o-mini answered "supported" on 123/126 verification calls,
scoring 0.643 — at or below the 0.667 majority-class baseline. This module makes that
kind of degeneracy impossible to miss. It is emitted on every scoring run.

Reported (with flags):
  1. Majority-class baseline over the verification set — overall, per model, per
     reasoning_type — and each model's verification accuracy relative to it. A model
     whose accuracy is at or below the baseline is flagged.
  2. Predicted-label distribution per model; a model whose modal label exceeds 90% of
     its verification answers is flagged (response bias).
  3. Gold-label balance per reasoning_type; a reasoning_type missing a label class is
     flagged, and label classes absent from the whole set are called out.
  4. Ceiling/floor detection: an item (task) whose cells are >=90% at 1.0 is flagged
     ceiling (>=90% at 0.0 -> floor), with the count of exception cells reported. A
     cell is a (task, format, condition, model) mean over trials.
  5. Text-level determinism: count of cells whose N trials produced an identical
     raw_response, plus the number of distinct system_fingerprints.

Pure and offline: a function of the (rescored) rows and the task definitions.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from experiment.grading import DETERMINATE_VERIFICATION_LABELS, VERIFICATION_LABELS
from experiment.schemas import Task

CEILING_FLOOR_THRESHOLD = 0.9  # WI6 (corrected): >=90% of cells at the extreme


def _int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def _cell_key(row: dict) -> tuple:
    return (row["task_id"], row["format"], row["condition"], row["model"])


def _row_score(row: dict) -> int:
    """The binary correctness a cell aggregates: verification accuracy or slot exact-match."""
    if row["task_type"] == "verification":
        return _int(row.get("grade_correct"))
    return _int(row.get("grade_exact_match"))


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def _majority_baseline(gold_labels: list[str]) -> tuple[float, str | None]:
    if not gold_labels:
        return 0.0, None
    counts = Counter(gold_labels)
    label, count = counts.most_common(1)[0]
    return count / len(gold_labels), label


def _verification_section(rows: list[dict], task_map: dict[str, Task]) -> dict:
    verif = [r for r in rows if r["task_type"] == "verification"]
    n = len(verif)
    flags: list[str] = []
    if n == 0:
        return {"n": 0, "flags": flags}

    gold_labels = [str(r.get("grade_gold_label") or "") for r in verif]
    baseline, majority_label = _majority_baseline(gold_labels)
    answered = [
        r for r in verif
        if r.get("pred_label") in DETERMINATE_VERIFICATION_LABELS
    ]
    selective_accuracy = (
        sum(r.get("pred_label") == r.get("grade_gold_label") for r in answered)
        / len(answered)
        if answered else 0.0
    )

    # Per model: accuracy vs baseline, and predicted-label distribution.
    per_model: dict[str, dict] = {}
    for model in sorted({r["model"] for r in verif}):
        mrows = [r for r in verif if r["model"] == model]
        acc = sum(_int(r.get("grade_correct")) for r in mrows) / len(mrows)
        m_answered = [
            r for r in mrows
            if r.get("pred_label") in DETERMINATE_VERIFICATION_LABELS
        ]
        m_baseline, _ = _majority_baseline([str(r.get("grade_gold_label") or "") for r in mrows])
        pred_counts = Counter(str(r.get("pred_label") or "(none)") for r in mrows)
        modal_label, modal_count = pred_counts.most_common(1)[0]
        modal_frac = modal_count / len(mrows)
        model_flags: list[str] = []
        if acc <= m_baseline:
            model_flags.append(
                f"verification accuracy {acc:.3f} <= majority baseline {m_baseline:.3f}"
            )
        if modal_frac > 0.9:
            model_flags.append(
                f"modal predicted label {modal_label!r} is {modal_frac:.3f} of answers (>90%)"
            )
        per_model[model] = {
            "n": len(mrows),
            "accuracy": acc,
            "n_answered": len(m_answered),
            "coverage": len(m_answered) / len(mrows),
            "accuracy_on_answered": (
                sum(r.get("pred_label") == r.get("grade_gold_label") for r in m_answered)
                / len(m_answered)
                if m_answered else 0.0
            ),
            "majority_class_baseline": m_baseline,
            "modal_pred_label": modal_label,
            "modal_pred_frac": modal_frac,
            "pred_label_counts": dict(pred_counts),
            "flags": model_flags,
        }
        flags.extend(f"[{model}] {m}" for m in model_flags)

    # Per reasoning_type: baseline + gold-label balance.
    per_reasoning: dict[str, dict] = {}
    by_rt: dict[str, list[dict]] = defaultdict(list)
    for r in verif:
        rt = task_map[r["task_id"]].reasoning_type
        by_rt[rt].append(r)
    for rt, rtrows in sorted(by_rt.items()):
        rt_gold = [str(r.get("grade_gold_label") or "") for r in rtrows]
        rt_baseline, _ = _majority_baseline(rt_gold)
        present = set(rt_gold)
        missing = [lab for lab in VERIFICATION_LABELS if lab not in present]
        per_reasoning[rt] = {
            "n": len(rtrows),
            "majority_class_baseline": rt_baseline,
            "gold_label_counts": dict(Counter(rt_gold)),
            "missing_label_classes": missing,
        }
        if missing:
            flags.append(f"[reasoning_type={rt}] gold missing label classes {missing}")

    labels_absent_everywhere = [lab for lab in VERIFICATION_LABELS if lab not in set(gold_labels)]
    if labels_absent_everywhere:
        flags.append(f"gold label class(es) absent from the whole set: {labels_absent_everywhere}")

    return {
        "n": n,
        "majority_class_baseline": baseline,
        "majority_label": majority_label,
        "n_answered": len(answered),
        "coverage": len(answered) / n,
        "accuracy_on_answered": selective_accuracy,
        "gold_label_counts": dict(Counter(gold_labels)),
        "per_model": per_model,
        "per_reasoning_type": per_reasoning,
        "labels_absent_everywhere": labels_absent_everywhere,
        "flags": flags,
    }


def _ceiling_floor_section(rows: list[dict]) -> dict:
    # Cell = (task, format, condition, model); value = mean row score over trials.
    cell_scores: dict[tuple, list[int]] = defaultdict(list)
    cell_task: dict[tuple, str] = {}
    for r in rows:
        key = _cell_key(r)
        cell_scores[key].append(_row_score(r))
        cell_task[key] = r["task_id"]

    by_task: dict[str, list[float]] = defaultdict(list)
    for key, scores in cell_scores.items():
        by_task[cell_task[key]].append(sum(scores) / len(scores))

    out: dict[str, dict] = {}
    flags: list[str] = []
    for task_id, means in sorted(by_task.items()):
        n_cells = len(means)
        at_1 = sum(1 for m in means if m == 1.0)
        at_0 = sum(1 for m in means if m == 0.0)
        ceiling = n_cells > 0 and at_1 / n_cells >= CEILING_FLOOR_THRESHOLD
        floor = n_cells > 0 and at_0 / n_cells >= CEILING_FLOOR_THRESHOLD
        out[task_id] = {
            "n_cells": n_cells,
            "cells_at_1.0": at_1,
            "cells_at_0.0": at_0,
            "ceiling": ceiling,
            "floor": floor,
            "exception_cells": (n_cells - at_1) if ceiling else (n_cells - at_0) if floor else None,
        }
        if ceiling:
            flags.append(f"[{task_id}] CEILING: {at_1}/{n_cells} cells at 1.0 ({n_cells - at_1} exceptions)")
        if floor:
            flags.append(f"[{task_id}] FLOOR: {at_0}/{n_cells} cells at 0.0 ({n_cells - at_0} exceptions)")
    return {"threshold": CEILING_FLOOR_THRESHOLD, "per_task": out, "flags": flags}


def _floor_citation_section(rows: list[dict]) -> dict:
    """Fabricated chunk citations under the no-corpus floor conditions (WI2).

    ``citation_hallucinated`` is only populated on floor rows (null elsewhere), so
    this section is empty for a standard oracle/retrieved run. A non-zero rate is a
    hallucination signal, not a grading error: with no context there is no chunk to
    cite, so any citation was invented.
    """
    floor = [r for r in rows if r.get("citation_hallucinated") not in (None, "")]
    if not floor:
        return {"n_floor_rows": 0, "flags": []}

    per_model: dict[str, dict] = {}
    flags: list[str] = []
    for model in sorted({r["model"] for r in floor}):
        mrows = [r for r in floor if r["model"] == model]
        n_hallucinated = sum(_int(r.get("citation_hallucinated")) for r in mrows)
        rate = n_hallucinated / len(mrows)
        per_model[model] = {
            "n_floor_rows": len(mrows),
            "n_hallucinated_citations": n_hallucinated,
            "hallucinated_citation_rate": rate,
        }
        if n_hallucinated:
            flags.append(
                f"[{model}] fabricated a chunk citation on {n_hallucinated}/{len(mrows)} "
                f"no-context rows ({rate:.3f})"
            )
    return {
        "n_floor_rows": len(floor),
        "per_model": per_model,
        "flags": flags,
    }


def _determinism_section(rows: list[dict]) -> dict:
    by_cell: dict[tuple, list[str]] = defaultdict(list)
    for r in rows:
        by_cell[_cell_key(r)].append(r.get("raw_response") or "")
    identical = sum(1 for responses in by_cell.values() if len(set(responses)) == 1)
    fingerprints = sorted({str(r.get("system_fingerprint") or "") for r in rows})
    return {
        "n_cells": len(by_cell),
        "identical_raw_cells": identical,
        "identical_frac": identical / len(by_cell) if by_cell else 0.0,
        "distinct_system_fingerprints": len(fingerprints),
        "system_fingerprints": fingerprints,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_report(rows: list[dict], tasks: list[Task]) -> dict:
    task_map = {t.task_id: t for t in tasks}
    verification = _verification_section(rows, task_map)
    ceiling_floor = _ceiling_floor_section(rows)
    determinism = _determinism_section(rows)
    floor_citations = _floor_citation_section(rows)
    all_flags = (
        list(verification.get("flags", []))
        + list(ceiling_floor.get("flags", []))
        + list(floor_citations.get("flags", []))
    )
    return {
        "n_rows": len(rows),
        "verification": verification,
        "ceiling_floor": ceiling_floor,
        "determinism": determinism,
        "floor_citations": floor_citations,
        "flags": all_flags,
    }


def print_report(report: dict) -> None:
    v = report.get("verification", {})
    print("=== Diagnostics ===")
    if v.get("n"):
        print(
            f"  verification set: n={v['n']} majority-class baseline="
            f"{v['majority_class_baseline']:.3f} (label={v['majority_label']!r})"
        )
        for model, m in v["per_model"].items():
            print(
                f"    {model}: acc={m['accuracy']:.3f} (baseline {m['majority_class_baseline']:.3f}) "
                f"modal={m['modal_pred_label']!r} {m['modal_pred_frac']:.3f}"
            )
        if v.get("labels_absent_everywhere"):
            print(f"    gold labels absent everywhere: {v['labels_absent_everywhere']}")
    cf = report.get("ceiling_floor", {})
    ceil = [t for t, d in cf.get("per_task", {}).items() if d["ceiling"]]
    flr = [t for t, d in cf.get("per_task", {}).items() if d["floor"]]
    print(f"  ceiling items: {ceil or 'none'}   floor items: {flr or 'none'}")
    d = report.get("determinism", {})
    print(
        f"  determinism: {d.get('identical_raw_cells')}/{d.get('n_cells')} cells identical "
        f"across trials; {d.get('distinct_system_fingerprints')} distinct fingerprints"
    )
    if report.get("flags"):
        print("  FLAGS:")
        for flag in report["flags"]:
            print(f"    - {flag}")
