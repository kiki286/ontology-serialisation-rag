"""No-context floor summaries (WI2).

The floor answers "what does this model score with no ontology context at all?",
so context-conditioned scores can be read against a baseline instead of in
absolute terms. A high floor on a task means that task is not measuring what the
study claims to measure — it is measuring pretraining recall.

Two tables are emitted:
  * ``floor_summary.csv``  - one row per (model, condition), the headline table.
  * ``floor_by_task.csv``  - one row per (model, condition, task), for spotting
    which individual tasks the model already knows.

Verification accuracy is ALWAYS reported next to the majority-class baseline for
the same label distribution. Reporting raw floor accuracy alone would be
misleading here for two documented reasons: the benchmark's verification golds
contain no ``undetermined`` class, and gpt-4o-mini has a known "supported"
response bias (CHANGELOG WI6 - 123/126 "supported", scoring 0.643 against a
0.667 baseline, i.e. BELOW chance-by-majority). A model can therefore post a
respectable-looking floor accuracy purely by answering one label every time, and
only the baseline delta exposes it.

Pure and offline: a function of the raw rows and the task definitions.
"""

from __future__ import annotations

from collections import Counter

from experiment.config import FLOOR_CONDITIONS
from experiment.schemas import Task


def _int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def _float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def floor_rows(rows: list[dict]) -> list[dict]:
    """The subset of raw rows belonging to a floor condition."""
    return [r for r in rows if r.get("condition") in FLOOR_CONDITIONS]


def _majority_baseline(gold_labels: list[str]) -> tuple[float, str | None]:
    """Accuracy obtainable by always answering the single most frequent gold label."""
    labels = [lab for lab in gold_labels if lab]
    if not labels:
        return 0.0, None
    label, count = Counter(labels).most_common(1)[0]
    return count / len(labels), label


def _summarise(subset: list[dict]) -> dict:
    """Metrics shared by the per-(model, condition) and per-task tables."""
    verif = [r for r in subset if r.get("task_type") == "verification"]
    slot = [r for r in subset if r.get("task_type") == "slot_filling"]

    out: dict = {
        "n_calls": len(subset),
        "n_verification_calls": len(verif),
        "n_slot_calls": len(slot),
        "parse_error_rate": (
            sum(1 for r in subset if not _truthy(r.get("parse_ok"))) / len(subset)
            if subset
            else None
        ),
    }

    if verif:
        gold = [str(r.get("grade_gold_label") or "") for r in verif]
        baseline, majority_label = _majority_baseline(gold)
        accuracy = sum(_int(r.get("grade_correct")) for r in verif) / len(verif)
        pred_counts = Counter(str(r.get("pred_label") or "(none)") for r in verif)
        modal_label, modal_count = pred_counts.most_common(1)[0]
        out.update(
            {
                "verification_accuracy": accuracy,
                "majority_class_baseline": baseline,
                "majority_label": majority_label,
                # THE number to read. <= 0 means the floor beats nothing: the model
                # is at or below what always-answer-the-modal-label would score.
                "accuracy_minus_baseline": accuracy - baseline,
                "beats_majority_baseline": accuracy > baseline,
                "modal_pred_label": modal_label,
                "modal_pred_frac": modal_count / len(verif),
                "pred_label_counts": dict(pred_counts),
            }
        )
    else:
        out.update(
            {
                "verification_accuracy": None,
                "majority_class_baseline": None,
                "majority_label": None,
                "accuracy_minus_baseline": None,
                "beats_majority_baseline": None,
                "modal_pred_label": None,
                "modal_pred_frac": None,
                "pred_label_counts": None,
            }
        )

    if slot:
        out.update(
            {
                "slot_exact_match_rate": sum(
                    _int(r.get("grade_exact_match")) for r in slot
                )
                / len(slot),
                "slot_mean_partial_credit": sum(
                    _float(r.get("grade_partial_credit")) for r in slot
                )
                / len(slot),
                # A citation under a floor condition is fabricated by construction.
                "citation_hallucination_rate": sum(
                    _int(r.get("citation_hallucinated")) for r in slot
                )
                / len(slot),
            }
        )
    else:
        out.update(
            {
                "slot_exact_match_rate": None,
                "slot_mean_partial_credit": None,
                "citation_hallucination_rate": None,
            }
        )

    # Retrieval/coverage metrics are undefined with no corpus. Emitted explicitly
    # as null so a downstream aggregate cannot silently average a 0 into them.
    out.update({"recall_at_k": None, "mrr": None, "ndcg_at_k": None, "coverage_frac": None})
    return out


def build_floor_summary(rows: list[dict]) -> list[dict]:
    """Per (model, condition) floor table."""
    subset = floor_rows(rows)
    keys = sorted({(r["model"], r["condition"]) for r in subset})
    out: list[dict] = []
    for model, condition in keys:
        cells = [r for r in subset if r["model"] == model and r["condition"] == condition]
        out.append({"model": model, "condition": condition, **_summarise(cells)})
    return out


def build_floor_by_task(rows: list[dict]) -> list[dict]:
    """Per (model, condition, task) floor table."""
    subset = floor_rows(rows)
    keys = sorted({(r["model"], r["condition"], r["task_id"]) for r in subset})
    out: list[dict] = []
    for model, condition, task_id in keys:
        cells = [
            r
            for r in subset
            if r["model"] == model
            and r["condition"] == condition
            and r["task_id"] == task_id
        ]
        out.append(
            {
                "model": model,
                "condition": condition,
                "task_id": task_id,
                "task_type": cells[0].get("task_type"),
                "reasoning_type": cells[0].get("reasoning_type"),
                **_summarise(cells),
            }
        )
    return out


def print_floor_summary(summary: list[dict]) -> None:
    if not summary:
        return
    print("=== No-context floor (WI2) ===")
    print("  verification accuracy is only interpretable against the majority baseline")
    for row in summary:
        acc = row.get("verification_accuracy")
        base = row.get("majority_class_baseline")
        line = f"    {row['model']:>26} {row['condition']:>14}: n={row['n_calls']:>3}"
        if acc is not None:
            delta = row["accuracy_minus_baseline"]
            verdict = "ABOVE" if delta > 0 else ("AT" if delta == 0 else "BELOW")
            line += (
                f" verif_acc={acc:.3f} baseline={base:.3f} "
                f"delta={delta:+.3f} ({verdict} baseline)"
                f" modal={row['modal_pred_label']!r} {row['modal_pred_frac']:.2f}"
            )
        print(line)
        if row.get("slot_exact_match_rate") is not None:
            print(
                f"    {'':>26} {'':>14}  slot_exact={row['slot_exact_match_rate']:.3f} "
                f"slot_partial={row['slot_mean_partial_credit']:.3f} "
                f"hallucinated_citations={row['citation_hallucination_rate']:.3f}"
            )
