"""Phase 3 analysis for Probe B2. Reads only — no API calls.

Emits the Section 7 table: probe arm x model x recovery rate of ``undetermined``,
with the frozen-run baseline as row zero, plus the side-effect check on
determinate items that the probe spec requires.

Run from ``src/rag``:
    ./.venv/Scripts/python.exe -m scripts.diagnostics.probe_b2_analyse
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from experiment.config import RESULTS_DIR

# Windows console defaults to cp1252; probe output is ASCII-safe but
# force UTF-8 so any future non-ASCII does not abort the analysis.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

pd.set_option("display.width", 220)

PROBE_DIR = RESULTS_DIR / "probe_b2_openworld"
BASELINE_RUN = RESULTS_DIR / "postretrieval-combined-15-18"
OUT_DIR = Path("../../docs/findings/oracle-undetermined-degeneracy")

SHORT = {
    "claude-sonnet-4-5-20250929": "sonnet",
    "gpt-4o-2024-11-20": "gpt-4o",
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini",
}
COLS = [
    "trial_idx", "task_id", "task_type", "format", "condition", "model",
    "system_prompt", "parse_ok", "pred_label", "grade_gold_label",
    "grade_correct", "prompt_tokens", "completion_tokens", "raw_response",
]


def load(path: Path, arm: str, keep: dict) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=COLS, low_memory=False)
    for col, vals in keep.items():
        df = df[df[col].isin(vals)]
    df = df.copy()
    df["arm"] = arm
    df["m"] = df.model.map(SHORT)
    df["is_und"] = (df.pred_label == "undetermined").astype(int)
    return df


def main() -> None:
    manifest = json.loads((PROBE_DIR / "manifest.json").read_text(encoding="utf-8"))
    items, formats = manifest["item_ids"], manifest["formats"]
    conditions = manifest["conditions"]
    # Compare like with like: the baseline is filtered to the arms the probe actually
    # ran, so a partial probe is never scored against a fuller baseline.
    models = manifest.get("models_run") or manifest.get("models_design") or manifest["models"]
    keep = {"task_id": items, "format": formats, "model": models, "condition": conditions}

    if not manifest.get("probe_complete", True):
        print("!! PARTIAL PROBE — arms not run: "
              f"{manifest.get('models_not_run')}")
        print("!! H2 concerns the GPT arms; a run without them cannot decide it.\n")

    probe = load(PROBE_DIR / "postretrieval_raw.csv", "B2 open-world", keep)
    base = load(BASELINE_RUN / "postretrieval_raw.csv", "frozen (row zero)", keep)
    both = pd.concat([base, probe], ignore_index=True)

    print(f"rows — baseline {len(base)}, probe {len(probe)}")
    print(f"probe prompt(s) on disk: {sorted(probe.system_prompt.unique())}")
    print(f"baseline prompt(s):      {sorted(base.system_prompt.unique())}")
    print(f"parse_ok: baseline {base.parse_ok.mean():.3f}  probe {probe.parse_ok.mean():.3f}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Section 7 headline table -----------------------------------------
    print("\n[T1] RECOVERY — undetermined rate, all 20 items pooled")
    t1 = both.pivot_table(index="arm", columns="m", values="is_und", aggfunc="mean").round(3)
    print(t1.to_string())
    t1.to_csv(OUT_DIR / "probe_b2_t1_recovery_pooled.csv")

    print("\n[T2] RECOVERY on the 10 undetermined-gold items (the target stratum)")
    ug = both[both.grade_gold_label == "undetermined"]
    t2 = ug.groupby(["arm", "m"]).is_und.agg(["mean", "sum", "count"])
    t2.columns = ["und_rate", "n_und", "n"]
    t2["und_rate"] = t2["und_rate"].round(3)
    print(t2.to_string())
    t2.to_csv(OUT_DIR / "probe_b2_t2_recovery_target.csv")

    print("\n[T3] SIDE EFFECT — undetermined false-alarm rate on the 10 determinate controls")
    det = both[both.grade_gold_label != "undetermined"]
    t3 = det.groupby(["arm", "m"]).is_und.agg(["mean", "sum", "count"])
    t3.columns = ["false_und_rate", "n_und", "n"]
    t3["false_und_rate"] = t3["false_und_rate"].round(3)
    print(t3.to_string())
    t3.to_csv(OUT_DIR / "probe_b2_t3_side_effect.csv")

    print("\n[T4] ACCURACY — does the variant cost accuracy on determinate items?")
    t4 = det.pivot_table(index="arm", columns="m", values="grade_correct", aggfunc="mean").round(3)
    print(t4.to_string())
    print("\n  ...and accuracy on the undetermined-gold items:")
    t4b = ug.pivot_table(index="arm", columns="m", values="grade_correct", aggfunc="mean").round(3)
    print(t4b.to_string())
    pd.concat([t4.assign(stratum="determinate"), t4b.assign(stratum="undetermined")]).to_csv(
        OUT_DIR / "probe_b2_t4_accuracy.csv"
    )

    print("\n[T5] by format (undetermined-gold items only)")
    t5 = ug.pivot_table(index=["arm", "m"], columns="format", values="is_und", aggfunc="mean").round(3)
    print(t5.to_string())
    t5.to_csv(OUT_DIR / "probe_b2_t5_by_format.csv")

    print("\n[T6] full label distribution, undetermined-gold items")
    t6 = ug.groupby(["arm", "m"]).pred_label.value_counts().unstack(fill_value=0)
    print(t6.to_string())
    t6.to_csv(OUT_DIR / "probe_b2_t6_label_dist.csv")

    # --- cell-level paired comparison --------------------------------------
    # 90 rows per arm on the target stratum are 30 (item x format) cells x 3 trials,
    # not 90 independent observations. Pair on the cell and report the paired
    # difference with a bootstrap over cells. This is a pooled statistic over cells,
    # NOT a significance test on any individual cell.
    print("\n[T8] cell-level paired comparison, undetermined-gold stratum")
    cell = (ug.groupby(["arm", "m", "task_id", "format"]).is_und.mean()
              .unstack("arm"))
    for m in sorted(ug.m.unique()):
        c = cell.xs(m, level="m").dropna()
        if c.shape[1] < 2:
            continue
        d = c["B2 open-world"] - c["frozen (row zero)"]
        up = int((d > 0).sum())
        down = int((d < 0).sum())
        same = int((d == 0).sum())
        rng = pd.Series(d.values)
        boot = [rng.sample(len(rng), replace=True, random_state=s).mean()
                for s in range(20000)]
        lo, hi = pd.Series(boot).quantile([0.025, 0.975])
        print(f"  {m}: {len(d)} cells — mean paired delta = {d.mean():+.3f} "
              f"[{lo:+.3f}, {hi:+.3f}]  (up {up} / down {down} / unchanged {same})")
        c.assign(delta=d).to_csv(OUT_DIR / f"probe_b2_t8_paired_{m}.csv")

    # --- sample of recovered rows -----------------------------------------
    rec = probe[(probe.grade_gold_label == "undetermined") & (probe.is_und == 1)]
    print(f"\n[T7] recovered rows in probe: {len(rec)}")
    if len(rec):
        def reason(s):
            try:
                return json.loads(s).get("reasoning", "")
            except Exception:
                return ""
        samp = rec.assign(reasoning=rec.raw_response.map(reason))
        samp = samp.groupby(["m", "task_id"], group_keys=False).head(1).head(12)
        with (OUT_DIR / "probe_b2_recovered_sample.txt").open("w", encoding="utf-8") as f:
            for _, r in samp.iterrows():
                line = f"[{r.m} | {r.task_id} | {r.format}] {r.reasoning}"
                f.write(line + "\n\n")
                print("  -", line[:200])

    print(f"\ncost (probe, uncached): {json.dumps(manifest.get('cost'), indent=2)[:400]}")


if __name__ == "__main__":
    main()
