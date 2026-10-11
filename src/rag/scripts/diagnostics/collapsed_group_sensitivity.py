"""Collapsed-group sensitivity bootstrap for the slot-filling headline (methods.tex
"Items are not fully independent" / results §3.6/§4.5).

Two groups of slot-filling items share a gold answer by construction: T40/T41/T55/T56
(quantity chain, mean pairwise r = 0.807) and T42/T43/T57/T58 (quality chain, r = 0.944).
The pre-registered headline bootstrap treats all 30 slot-filling items as independent
resampling units. This script re-runs the same paired-format bootstrap with each
duplicate-shape group collapsed to its group mean first (30 items -> 24 pseudo-items)
and checks the three pre-registered agreement criteria from methods.tex: sign of each
of the 21 pairwise format contrasts, whether its 95% CI excludes zero, and whether its
point estimate clears the resolution threshold (0.167, the six-field/more conservative
bound). Analysis-only: reads the already-scored postretrieval CSV, makes no API calls.
"""

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

SCORED_CSV = Path(__file__).resolve().parents[2] / "experiment" / "results" / \
    "postretrieval-combined-15-18" / "postretrieval_scored.csv"
OUT_DIR = Path(__file__).resolve().parent / "results" / "collapsed_group_sensitivity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FORMATS = ["turtle", "elot-org", "elot-org-ancestors", "omn", "jsonld", "yaml-ld", "ofn"]
QUANTITY_GROUP = ["T40", "T41", "T55", "T56"]
QUALITY_GROUP = ["T42", "T43", "T57", "T58"]
RESOLUTION_THRESHOLD = 0.167  # six-field items; the more conservative (smaller) bound
SEED_BASE = 20260529  # experiment.config.SEED
B = 10_000


def item_format_table() -> pd.DataFrame:
    """30 slot-filling items x 7 formats, each cell pooled over condition and model."""
    df = pd.read_csv(SCORED_CSV)
    sf = df[df.task_type == "slot_filling"]
    pooled = (sf.groupby(["task_id", "format"]).mean_partial_credit_mean.mean()
                .unstack("format"))
    return pooled[FORMATS]


def collapse_groups(table: pd.DataFrame) -> pd.DataFrame:
    """30 items -> 24 pseudo-items: each duplicate-shape group replaced by its mean."""
    remaining = table.drop(index=QUANTITY_GROUP + QUALITY_GROUP)
    quantity_mean = table.loc[QUANTITY_GROUP].mean(axis=0).to_frame("quantity_group").T
    quality_mean = table.loc[QUALITY_GROUP].mean(axis=0).to_frame("quality_group").T
    collapsed = pd.concat([remaining, quantity_mean, quality_mean])
    return collapsed


def bootstrap_contrasts(table: pd.DataFrame, b: int = B, seed_base: int = SEED_BASE):
    """Paired item bootstrap over the given item population.

    Returns point estimates (dict[(f1,f2)] -> delta) and 95% percentile CIs, resampling
    items (rows) with replacement, B times, and taking the per-format mean each time.
    """
    n = len(table)
    idx = table.index.to_numpy()
    point = {}
    for f1, f2 in itertools.combinations(FORMATS, 2):
        point[(f1, f2)] = table[f1].mean() - table[f2].mean()

    boot_deltas = {pair: np.empty(b) for pair in point}
    for i in range(b):
        rng = np.random.RandomState(seed_base + i)
        sample_idx = rng.choice(idx, size=n, replace=True)
        sample = table.loc[sample_idx]
        means = sample.mean(axis=0)
        for f1, f2 in point:
            boot_deltas[(f1, f2)][i] = means[f1] - means[f2]

    ci = {}
    for pair, arr in boot_deltas.items():
        lo, hi = np.percentile(arr, [2.5, 97.5])
        ci[pair] = (lo, hi)
    return point, ci


def summarise(table: pd.DataFrame, point, ci) -> pd.DataFrame:
    rows = []
    for (f1, f2), delta in point.items():
        lo, hi = ci[(f1, f2)]
        rows.append({
            "format_a": f1, "format_b": f2, "delta": delta,
            "ci_lo": lo, "ci_hi": hi,
            "excludes_zero": (lo > 0) or (hi < 0),
            "clears_threshold": abs(delta) >= RESOLUTION_THRESHOLD,
            "sign": "+" if delta > 0 else ("-" if delta < 0 else "0"),
        })
    marg = table.mean(axis=0)
    spread = marg.max() - marg.min()
    print(f"  n_items={len(table)}  format marginals: "
          + ", ".join(f"{f}={marg[f]:.3f}" for f in FORMATS))
    print(f"  spread = {spread:.4f}")
    return pd.DataFrame(rows)


def main():
    headline_table = item_format_table()
    assert len(headline_table) == 30, f"expected 30 slot-filling items, got {len(headline_table)}"
    collapsed_table = collapse_groups(headline_table)
    assert len(collapsed_table) == 24, f"expected 24 collapsed pseudo-items, got {len(collapsed_table)}"

    print(f"[headline] item bootstrap, n=30, B={B}")
    h_point, h_ci = bootstrap_contrasts(headline_table)
    h_summary = summarise(headline_table, h_point, h_ci)

    print(f"\n[collapsed] item bootstrap, n=24 (duplicate-shape groups collapsed), B={B}")
    c_point, c_ci = bootstrap_contrasts(collapsed_table)
    c_summary = summarise(collapsed_table, c_point, c_ci)

    merged = h_summary.merge(
        c_summary, on=["format_a", "format_b"], suffixes=("_headline", "_collapsed")
    )
    merged["sign_agrees"] = merged.sign_headline == merged.sign_collapsed
    merged["excludes_zero_agrees"] = merged.excludes_zero_headline == merged.excludes_zero_collapsed
    merged["clears_threshold_agrees"] = merged.clears_threshold_headline == merged.clears_threshold_collapsed
    merged["all_three_agree"] = (
        merged.sign_agrees & merged.excludes_zero_agrees & merged.clears_threshold_agrees
    )

    n_pairs = len(merged)
    n_agree = int(merged.all_three_agree.sum())
    print(f"\n[agreement] {n_agree} of {n_pairs} pairwise format contrasts agree on all "
          f"three pre-registered criteria (sign, CI excludes zero, clears {RESOLUTION_THRESHOLD} threshold).")
    if n_agree < n_pairs:
        print("  Disagreements:")
        print(merged[~merged.all_three_agree][
            ["format_a", "format_b", "delta_headline", "delta_collapsed",
             "excludes_zero_headline", "excludes_zero_collapsed"]
        ].to_string(index=False))
    newly_excludes = merged[(~merged.excludes_zero_headline) & (merged.excludes_zero_collapsed)]
    print(f"\n[manufactured-effect check] {len(newly_excludes)} pairs newly exclude zero "
          f"under collapse that did not under the headline bootstrap "
          f"(methods.tex predicts 0; collapsing can only widen, never manufacture).")

    merged.to_csv(OUT_DIR / "collapsed_group_sensitivity_contrasts.csv", index=False)
    headline_table.to_csv(OUT_DIR / "headline_item_format_table.csv")
    collapsed_table.to_csv(OUT_DIR / "collapsed_item_format_table.csv")
    print(f"\nWrote {OUT_DIR / 'collapsed_group_sensitivity_contrasts.csv'}")


if __name__ == "__main__":
    main()
