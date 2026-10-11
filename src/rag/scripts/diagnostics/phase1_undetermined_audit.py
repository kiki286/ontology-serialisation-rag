"""Phase 1: characterise the degeneracy. No API calls."""
import sys
from pathlib import Path
import pandas as pd
pd.set_option("display.width", 200)

RES = Path("experiment/results/postretrieval-combined-15-18")
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
COLS = ["trial_idx","task_id","task_type","format","condition","model","system_prompt",
        "parse_ok","pred_label","grade_gold_label","context_char_len","n_context_chunks",
        "coverage_all","coverage_frac","grade_correct"]
df = pd.read_csv(RES/"postretrieval_raw.csv", usecols=COLS, low_memory=False)
ver = df[df.task_type == "verification"].copy()
ver["is_und"] = (ver.pred_label == "undetermined").astype(int)
SHORT = {"claude-sonnet-4-5-20250929":"sonnet","gpt-4o-2024-11-20":"gpt-4o",
         "gpt-4o-mini-2024-07-18":"gpt-4o-mini","llama3.1:8b-instruct-q8_0":"llama"}
ver["m"] = ver.model.map(SHORT)

print("[P1.0] system prompt files used, by condition:")
print(ver.groupby("condition").system_prompt.value_counts().to_string())

print("\n[P1.1] undetermined rate by (model, condition, gold stratum) — rate (n_und/n):")
t = ver.groupby(["m","condition","grade_gold_label"]).is_und.agg(["mean","sum","count"])
t.columns = ["rate","n_und","n"]; t["rate"] = t["rate"].round(3)
print(t.to_string()); t.to_csv(OUT/"p1_rate_by_model_cond_gold.csv")

print("\n[P1.1b] undetermined rate by (model, condition, format), all strata pooled:")
t2 = ver.pivot_table(index=["m","condition"], columns="format", values="is_und", aggfunc="mean").round(3)
print(t2.to_string()); t2.to_csv(OUT/"p1_rate_by_model_cond_format.csv")

print("\n[P1.2] oracle vs retrieved undetermined rate, per model (pooled):")
t3 = ver.pivot_table(index="m", columns="condition", values="is_und", aggfunc="mean").round(3)
t3["delta_retr_minus_oracle"] = (t3["retrieved"]-t3["oracle"]).round(3)
print(t3.to_string()); t3.to_csv(OUT/"p1_oracle_vs_retrieved.csv")

# --- H3 direct test: is undetermined conditioned on gold coverage? ---------
print("\n[P1.H3] RETRIEVED only — undetermined rate split by whether gold chunk reached context:")
r = ver[ver.condition=="retrieved"].copy()
r["gold_present"] = r.coverage_all.fillna(0).astype(int)
h3 = r.groupby(["m","gold_present"]).is_und.agg(["mean","sum","count"])
h3.columns=["rate","n_und","n"]; h3["rate"]=h3["rate"].round(3)
print(h3.to_string()); h3.to_csv(OUT/"p1_h3_coverage_split.csv")

print("\n[P1.H3b] same, restricted to undetermined-gold items:")
h3b = r[r.grade_gold_label=="undetermined"].groupby(["m","gold_present"]).is_und.agg(["mean","sum","count"])
h3b.columns=["rate","n_und","n"]; h3b["rate"]=h3b["rate"].round(3)
print(h3b.to_string())

print("\n[P1.H3c] GPT arms, retrieved: coverage_all distribution of the undetermined rows")
g = r[r.m.isin(["gpt-4o","gpt-4o-mini"])]
print(g.groupby(["m","is_und"]).coverage_all.agg(["mean","count"]).round(3).to_string())

# --- Trial stability -------------------------------------------------------
print("\n[P1.3] trial-level stability of the undetermined label:")
cell = ver.groupby(["m","condition","format","task_id"]).is_und.agg(["sum","count"])
cell = cell[cell["count"]==3]
def cls(s): return "never(0/3)" if s==0 else ("always(3/3)" if s==3 else f"split({s}/3)")
cell["k"] = cell["sum"].map(cls)
st = cell.groupby(["m","condition"]).k.value_counts().unstack(fill_value=0)
print(st.to_string()); st.to_csv(OUT/"p1_trial_stability.csv")

# --- Context length --------------------------------------------------------
print("\n[P1.4] verification context_char_len, mean by (format, condition):")
c = ver.pivot_table(index="format", columns="condition", values="context_char_len", aggfunc="mean").round(0)
c["oracle_minus_retrieved"] = (c["oracle"]-c["retrieved"]).round(0)
print(c.to_string()); c.to_csv(OUT/"p1_context_len.csv")
print("\n[P1.4b] n_context_chunks by condition (verification):")
print(ver.groupby("condition").n_context_chunks.describe()[["mean","min","50%","max"]].round(2).to_string())
print("\n[P1.4c] oracle context_char_len by gold stratum:")
print(ver[ver.condition=="oracle"].groupby("grade_gold_label")
      .agg(chars=("context_char_len","mean"), chunks=("n_context_chunks","mean")).round(1).to_string())
