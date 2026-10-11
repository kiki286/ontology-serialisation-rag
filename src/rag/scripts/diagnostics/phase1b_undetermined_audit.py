"""Phase 1b: the free H3 test — is undetermined conditioned on gold-chunk absence?"""
import json, sys
from pathlib import Path
import pandas as pd, yaml
pd.set_option("display.width", 220)

RES = Path("experiment/results/postretrieval-combined-15-18")
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)

tasks = {t["task_id"]: t for t in yaml.safe_load(
    Path("experiment/benchmark/tasks_60.yaml").read_text(encoding="utf-8"))}

COLS = ["trial_idx","task_id","task_type","format","condition","model","pred_label",
        "grade_gold_label","context_chunk_ids","context_char_len","n_context_chunks"]
df = pd.read_csv(RES/"postretrieval_raw.csv", usecols=COLS, low_memory=False)
ver = df[df.task_type=="verification"].copy()
SHORT={"claude-sonnet-4-5-20250929":"sonnet","gpt-4o-2024-11-20":"gpt-4o",
       "gpt-4o-mini-2024-07-18":"gpt-4o-mini","llama3.1:8b-instruct-q8_0":"llama"}
ver["m"]=ver.model.map(SHORT); ver["is_und"]=(ver.pred_label=="undetermined").astype(int)

def gold_frac(r):
    g = set(tasks[r.task_id].get("retrieval_gold_chunks") or [])
    if not g: return None
    try: ctx = set(json.loads(r.context_chunk_ids))
    except Exception: return None
    return len(g & ctx)/len(g)
ver["gold_frac"] = ver.apply(gold_frac, axis=1)
ver["gold_all"] = (ver.gold_frac==1.0).astype(int)

print("[P1b.0] sanity — gold_frac by condition (should be 1.0 for oracle):")
print(ver.groupby("condition").gold_frac.agg(["mean","min","max"]).round(3).to_string())

print("\n[P1b.H3] RETRIEVED — undetermined rate by whether ALL gold chunks reached context:")
r = ver[ver.condition=="retrieved"]
h = r.groupby(["m","gold_all"]).is_und.agg(["mean","sum","count"])
h.columns=["und_rate","n_und","n"]; h["und_rate"]=h["und_rate"].round(3)
print(h.to_string()); h.to_csv(OUT/"p1b_h3_gold_presence.csv")

print("\n[P1b.H3b] GPT arms only, retrieved, by gold stratum x gold_all:")
g = r[r.m.isin(["gpt-4o","gpt-4o-mini"])]
hb = g.groupby(["m","grade_gold_label","gold_all"]).is_und.agg(["mean","sum","count"])
hb.columns=["und_rate","n_und","n"]; hb["und_rate"]=hb["und_rate"].round(3)
print(hb.to_string()); hb.to_csv(OUT/"p1b_h3_gpt_detail.csv")

print("\n[P1b.H3c] The decisive contrast — GPT arms, gold_all==1 in BOTH conditions:")
both = ver[(ver.m.isin(["gpt-4o","gpt-4o-mini"])) & (ver.gold_all==1)]
hc = both.groupby(["m","condition"]).is_und.agg(["mean","sum","count"])
hc.columns=["und_rate","n_und","n"]; hc["und_rate"]=hc["und_rate"].round(3)
print(hc.to_string()); hc.to_csv(OUT/"p1b_h3_decisive.csv")
print("\n  ...and same restricted to undetermined-gold items:")
hd = both[both.grade_gold_label=="undetermined"].groupby(["m","condition"]).is_und.agg(["mean","sum","count"])
hd.columns=["und_rate","n_und","n"]; hd["und_rate"]=hd["und_rate"].round(3)
print(hd.to_string())

print("\n[P1b.H3d] all four models, gold_all==1, both conditions (undetermined-gold items only):")
he = ver[(ver.gold_all==1)&(ver.grade_gold_label=="undetermined")].groupby(["m","condition"]).is_und.agg(["mean","sum","count"])
he.columns=["und_rate","n_und","n"]; he["und_rate"]=he["und_rate"].round(3)
print(he.to_string()); he.to_csv(OUT/"p1b_h3_all_models_goldpresent.csv")

print("\n[P1b.4] context size when gold is fully present, by condition (verification):")
print(ver[ver.gold_all==1].groupby("condition")
      .agg(chars=("context_char_len","mean"), chunks=("n_context_chunks","mean")).round(1).to_string())
