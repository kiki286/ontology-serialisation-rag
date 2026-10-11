"""Per-class precision, recall and F1 on the verification labels, with item-bootstrap intervals.

The dissertation does not report per-class precision, recall or F1 on the three
verification labels, because at ten items per class the intervals are too wide:
the precision intervals for `contradicted` and `undetermined` are 0.40 and 0.49
wide, comparable to or larger than their point estimates of 0.43 and 0.30
(method.tex, "What is not reportable"; results.tex, section 4.2). This script
computes the table those numbers come from (first recorded in
docs/findings/60task-analysis.md, section 3.1), and check_thesis_numbers pins
them from its output.

Method, as the methods chapter specifies for every interval in the study: a
bootstrap over items. All 5,040 verification rows (30 items, ten per gold
label, pooled over serialisations, conditions, arms and trials) are reduced to
per-item counts; each of B = 10,000 resamples draws the 30 items with
replacement (unstratified, so a resample need not hold ten of each class) and
recomputes the pooled per-class statistics from the drawn items' rows. The
interval is the 2.5th to 97.5th percentile of the resampled statistic; the
width is upper minus lower. The two unparsed rows have no predicted label:
each counts against recall (a row of its gold class not predicted as that
class) and is absent from every precision denominator, as in the confusion
matrix.

Analysis-only; reads the frozen raw CSV, no API calls.

Usage (from src/rag/, after step 0 of the README rebuilds the merged raw CSV):
    python -m scripts.diagnostics.verification_per_class_intervals
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "experiment" / "results" / "postretrieval-combined-15-18" / "postretrieval_raw.csv"
OUT = Path(__file__).resolve().parent / "results" / "verification_per_class_intervals"

SEED = 20260529  # experiment.config.SEED
B = 10_000
LABELS = ["supported", "contradicted", "undetermined"]
STATS = ["precision", "recall", "f1"]


def per_class(counts):
    """Pooled per-class precision, recall and F1 from summed per-item counts."""
    out = {}
    for c in LABELS:
        tp, pred, gold = counts[f"tp_{c}"], counts[f"pred_{c}"], counts[f"gold_{c}"]
        p = tp / pred if pred else 0.0
        r = tp / gold if gold else 0.0
        out[(c, "precision")] = p
        out[(c, "recall")] = r
        out[(c, "f1")] = 2 * p * r / (p + r) if p + r else 0.0
    return out


def main():
    raw = pd.read_csv(RAW, low_memory=False)
    ver = raw[raw.task_type == "verification"]
    assert len(ver) == 5040, len(ver)
    gold_items = ver.groupby("task_id").grade_gold_label.first()
    assert gold_items.value_counts().to_dict() == {c: 10 for c in LABELS}

    items = sorted(ver.task_id.unique())
    cols = {}
    for c in LABELS:
        pred = ver.grade_pred_label == c
        gold = ver.grade_gold_label == c
        cols[f"tp_{c}"] = (pred & gold).groupby(ver.task_id).sum()
        cols[f"pred_{c}"] = pred.groupby(ver.task_id).sum()
        cols[f"gold_{c}"] = gold.groupby(ver.task_id).sum()
    item_counts = pd.DataFrame(cols).reindex(items)
    matrix = item_counts.to_numpy()

    point = per_class(item_counts.sum())
    rng = np.random.default_rng(SEED)
    n = len(items)
    boots = np.empty((B, len(point)))
    for b in range(B):
        sample = matrix[rng.integers(0, n, n)].sum(axis=0)
        boots[b] = list(per_class(dict(zip(item_counts.columns, sample))).values())
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)

    rows = [{"label": c, "statistic": s, "point": point[(c, s)],
             "lo": lo[k], "hi": hi[k], "width": hi[k] - lo[k]}
            for k, (c, s) in enumerate(point)]
    table = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "per_class_intervals.csv", index=False)

    print(f"per-class verification statistics, {n} items (10 per gold label), "
          f"bootstrap over items, B = {B:,}, seed {SEED}:\n")
    print(f"  {'label':<13} {'statistic':<10} {'point':>6}  {'95% interval':<17} {'width':>6}")
    for r in rows:
        print(f"  {r['label']:<13} {r['statistic']:<10} {r['point']:6.3f}  "
              f"[{r['lo']:.3f}, {r['hi']:.3f}]   {r['width']:6.3f}")
    print(f"\nwrote {OUT / 'per_class_intervals.csv'}")


if __name__ == "__main__":
    main()
