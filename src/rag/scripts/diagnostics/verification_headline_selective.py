"""Verification headline family recomputed as selective prediction.

The methods chapter commits to selective prediction on the 20 determinate items
as the verification scoring; the first draft of the results chapter reported
pooled three-way accuracy over all 30 items instead, which both dilutes the
metric with the undetermined stratum and draws a format comparison through the
GPT oracle cells the same chapter rules out. This script computes the headline
family the way the methods chapter defines it: per-format coverage and accuracy
on answered over the 20 determinate items, each with 21 paired format contrasts,
bootstrap intervals over items, and Holm correction within the metric.

Analysis-only; reads the frozen raw CSV, no API calls.
"""

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "experiment" / "results" / "postretrieval-combined-15-18" / "postretrieval_raw.csv"
OUT = Path(__file__).resolve().parent / "results" / "verification_headline_selective"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 20260529
B = 20_000
FORMATS = ["turtle", "omn", "ofn", "jsonld", "yaml-ld", "elot-org", "elot-org-ancestors"]


def holm(pvals):
    order = np.argsort(pvals)
    adj = np.empty_like(pvals, dtype=float)
    m = len(pvals)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pvals[idx])
        adj[idx] = min(running, 1.0)
    return adj


def contrasts(item_table, label):
    """21 paired contrasts over items for one metric. item_table: items x formats."""
    idx = item_table.index.to_numpy()
    n = len(idx)
    pairs = list(itertools.combinations(FORMATS, 2))
    boots = {p: np.empty(B) for p in pairs}
    for b in range(B):
        rng = np.random.RandomState(SEED + b)
        sample = item_table.loc[rng.choice(idx, size=n, replace=True)]
        means = sample.mean()
        for f1, f2 in pairs:
            boots[(f1, f2)][b] = means[f1] - means[f2]
    rows = []
    for f1, f2 in pairs:
        delta = item_table[f1].mean() - item_table[f2].mean()
        arr = boots[(f1, f2)]
        lo, hi = np.percentile(arr, [2.5, 97.5])
        p = 2 * min((arr <= 0).mean(), (arr >= 0).mean())
        p = min(max(p, 1.0 / B), 1.0)
        rows.append({"metric": label, "a": f1, "b": f2, "delta": delta,
                     "lo": lo, "hi": hi, "p": p})
    df = pd.DataFrame(rows)
    df["p_holm"] = holm(df.p.values)
    return df


def main():
    raw = pd.read_csv(RAW, low_memory=False)
    ver = raw[raw.task_type == "verification"].copy()
    det = ver[ver.grade_gold_label != "undetermined"]
    n_items = det.task_id.nunique()
    assert n_items == 20, n_items

    grp = det.groupby(["task_id", "format"])
    item_cov = grp.grade_answered.mean().unstack("format")[FORMATS]
    item_acc = (grp.grade_selective_correct.sum() / grp.grade_answered.sum()) \
        .unstack("format")[FORMATS]
    print("item-format cells with zero answered rows:", int(item_acc.isna().sum().sum()))

    fmt_cov = det.groupby("format").grade_answered.mean().reindex(FORMATS)
    fmt_acc = (det.groupby("format").grade_selective_correct.sum()
               / det.groupby("format").grade_answered.sum()).reindex(FORMATS)

    overall_cov = det.grade_answered.mean()
    overall_acc = det.grade_selective_correct.sum() / det.grade_answered.sum()
    print(f"\noverall (20 determinate items): coverage {overall_cov:.4f} "
          f"(doc 0.894), acc-on-answered {overall_acc:.4f} (doc 0.882)")

    table = pd.DataFrame({"coverage": fmt_cov, "acc_on_answered": fmt_acc})
    table.loc["spread"] = table.max() - table.min()
    print("\nper-format selective prediction, 20 determinate items:")
    print(table.round(4).to_string())
    table.to_csv(OUT / "per_format_selective.csv")

    all_c = pd.concat([contrasts(item_acc.fillna(item_acc.mean()), "acc_on_answered"),
                       contrasts(item_cov, "coverage")])
    all_c.to_csv(OUT / "paired_contrasts.csv", index=False)
    for metric in ["acc_on_answered", "coverage"]:
        sub = all_c[all_c.metric == metric]
        nom = int((sub.p < 0.05).sum())
        hol = int((sub.p_holm < 0.05).sum())
        big = int((sub.delta.abs() >= 1.0).sum())
        print(f"\n{metric}: {nom} of 21 nominal p<0.05, {hol} survive Holm, "
              f"{big} clear the one-label threshold; "
              f"max |delta| {sub.delta.abs().max():.4f}")


if __name__ == "__main__":
    main()
