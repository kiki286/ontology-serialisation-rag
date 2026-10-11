"""Phase 0 audit: oracle undetermined-label degeneracy. No API calls."""
import json, re, sys
from pathlib import Path
import pandas as pd

RES = Path("experiment/results/postretrieval-combined-15-18")
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

GPT = ["gpt-4o-2024-11-20", "gpt-4o-mini-2024-07-18"]
COLS = ["trial_idx","task_id","task_type","format","condition","model","finish_reason",
        "parse_ok","parse_error","pred_label","grade_gold_label","raw_response",
        "context_char_len","n_context_chunks","completion_tokens"]

df = pd.read_csv(RES/"postretrieval_raw.csv", usecols=COLS, low_memory=False)
print(f"rows total: {len(df)}")
ver = df[df.task_type == "verification"].copy()
print(f"verification rows: {len(ver)}")
print("models:", sorted(ver.model.unique()))
print("conditions:", sorted(ver.condition.unique()))

# --- Check 1: confirm the count -------------------------------------------
aff = ver[(ver.condition == "oracle") & (ver.model.isin(GPT))]
n_und = (aff.pred_label == "undetermined").sum()
print(f"\n[CHECK 1] affected rows = {len(aff)}; parsed 'undetermined' = {n_und}")

# --- Check 2: string-level audit of raw completions -----------------------
PATTERNS = {
    "undetermined": r"undetermined",
    "undecided": r"undecided",
    "cannot be determined": r"cannot\s+be\s+determined",
    "insufficient": r"insufficient",
    "not enough information": r"not\s+enough\s+information",
    "unknown": r"unknown",
    "neither": r"neither",
    "abstain": r"abstain",
}
raw = aff.raw_response.fillna("")
rows = []
for name, pat in PATTERNS.items():
    m = raw.str.contains(pat, case=False, regex=True, na=False)
    rows.append({"pattern": name, "rows_matching": int(m.sum()),
                 "share_of_630x2": round(m.sum()/len(aff), 4)})
pat_df = pd.DataFrame(rows)
print("\n[CHECK 2] raw-string patterns in affected cells:")
print(pat_df.to_string(index=False))
pat_df.to_csv(OUT/"p0_raw_string_patterns.csv", index=False)

# Same, split by model, and split by whether the string is in the label field
def label_field(s):
    try:
        return json.loads(s).get("label")
    except Exception:
        return None
aff = aff.assign(json_label=raw.map(label_field))
print("\n[CHECK 2b] label field recovered directly from raw JSON:")
print(aff.groupby("model").json_label.value_counts(dropna=False).to_string())
print("\njson_label vs parsed pred_label disagreement:",
      int((aff.json_label.fillna("<none>") != aff.pred_label.fillna("<none>")).sum()))

# --- Check 3: dump completions containing a pattern but parsed otherwise ---
anyp = raw.str.contains("|".join(PATTERNS.values()), case=False, regex=True, na=False)
h1 = aff[anyp & (aff.pred_label != "undetermined")]
print(f"\n[CHECK 3] H1 candidates (pattern present, not parsed undetermined): {len(h1)}")
samp = h1.groupby("format", group_keys=False).apply(
    lambda g: g.head(max(1, 50 // max(1, h1.format.nunique())))).head(50)
with (OUT/"p0_h1_dump.txt").open("w", encoding="utf-8") as f:
    for _, r in samp.iterrows():
        f.write(f"--- {r.task_id} | {r.format} | {r.model} | trial {r.trial_idx} | "
                f"gold={r.grade_gold_label} | parsed={r.pred_label}\n{r.raw_response}\n\n")
print(f"  dumped {len(samp)} to p0_h1_dump.txt")

# --- Check 4: parser fallback behaviour -----------------------------------
print("\n[CHECK 4] parse_ok in affected cells:")
print(aff.parse_ok.value_counts(dropna=False).to_string())
bad = aff[~aff.parse_ok.astype(bool)]
print(f"  parse failures: {len(bad)}; their pred_label values: "
      f"{bad.pred_label.value_counts(dropna=False).to_dict()}")

# --- Check 5/6/7: label distributions -------------------------------------
def dist(frame, by):
    t = (frame.groupby(by).pred_label.value_counts(dropna=False)
         .unstack(fill_value=0))
    for c in ["supported","contradicted","undetermined"]:
        if c not in t.columns: t[c] = 0
    keep = ["supported","contradicted","undetermined"]
    extra = [c for c in t.columns if c not in keep]
    t = t[keep+extra]
    t["n"] = t.sum(axis=1)
    return t

print("\n[CHECK 5] affected cells x format:")
d5 = dist(aff, ["model","format"]); print(d5.to_string()); d5.to_csv(OUT/"p0_gpt_oracle_by_format.csv")
print("\n[CHECK 5b] affected cells x gold stratum:")
d5b = dist(aff, ["model","grade_gold_label"]); print(d5b.to_string()); d5b.to_csv(OUT/"p0_gpt_oracle_by_gold.csv")

print("\n[CHECK 6+7] all models x condition (verification):")
d7 = dist(ver, ["model","condition"]); print(d7.to_string()); d7.to_csv(OUT/"p0_all_models_by_condition.csv")

print("\n[CHECK 7b] all models x condition x gold stratum:")
d7b = dist(ver, ["model","condition","grade_gold_label"])
print(d7b.to_string()); d7b.to_csv(OUT/"p0_all_by_condition_gold.csv")
