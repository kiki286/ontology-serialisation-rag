"""Four-model gold-present x gold-stratum split. Reads only."""
import json, sys
from pathlib import Path
import pandas as pd, yaml
pd.set_option("display.width", 240)
RES=Path("experiment/results/postretrieval-combined-15-18")
OUT=Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
tasks={t["task_id"]:t for t in yaml.safe_load(Path("experiment/benchmark/tasks_60.yaml").read_text(encoding="utf-8"))}
df=pd.read_csv(RES/"postretrieval_raw.csv",usecols=["task_type","task_id","condition","model",
    "format","pred_label","grade_gold_label","context_chunk_ids"],low_memory=False)
v=df[df.task_type=="verification"].copy()
SHORT={"claude-sonnet-4-5-20250929":"sonnet","gpt-4o-2024-11-20":"gpt-4o",
       "gpt-4o-mini-2024-07-18":"gpt-4o-mini","llama3.1:8b-instruct-q8_0":"llama"}
v["m"]=v.model.map(SHORT); v["is_und"]=(v.pred_label=="undetermined").astype(int)
def gp(r):
    g=set(tasks[r.task_id].get("retrieval_gold_chunks") or [])
    try: return int(g <= set(json.loads(r.context_chunk_ids)))
    except Exception: return 0
v["gold_present"]=v.apply(gp,axis=1)
v["stratum"]=v.grade_gold_label.map(lambda s:"undetermined-gold" if s=="undetermined" else "determinate")

print("[E1] undetermined rate by model x gold_present x stratum (both conditions pooled)")
t=v.groupby(["m","gold_present","stratum"]).is_und.agg(["mean","sum","count"])
t.columns=["und_rate","n_und","n"]; t["und_rate"]=t["und_rate"].round(3)
print(t.to_string()); t.to_csv(OUT/"p1e_four_model_gating.csv")

print("\n[E2] the decisive contrast — GOLD PRESENT only, does abstention track non-entailment?")
gpres=v[v.gold_present==1]
p=gpres.pivot_table(index="m",columns="stratum",values="is_und",aggfunc="mean").round(3)
p["discrimination"]=(p["undetermined-gold"]-p["determinate"]).round(3)
n=gpres.pivot_table(index="m",columns="stratum",values="is_und",aggfunc="count")
p["n_det"]=n["determinate"]; p["n_und"]=n["undetermined-gold"]
print(p.to_string()); p.to_csv(OUT/"p1e_gold_present_discrimination.csv")

print("\n[E3] GOLD ABSENT (retrieved misses) — does abstention track missing material?")
gabs=v[v.gold_present==0]
q=gabs.pivot_table(index="m",columns="stratum",values="is_und",aggfunc="mean").round(3)
nq=gabs.pivot_table(index="m",columns="stratum",values="is_und",aggfunc="count")
q["n_det"]=nq["determinate"]; q["n_und"]=nq["undetermined-gold"]
print(q.to_string()); q.to_csv(OUT/"p1e_gold_absent.csv")

print("\n[E4] headline 2x2 per model: und rate by gold_present (all strata)")
h=v.pivot_table(index="m",columns="gold_present",values="is_und",aggfunc=["mean","count"]).round(3)
print(h.to_string())

print("\n[E5] accuracy on the undetermined-gold stratum, gold present (how right is 'discriminative'?)")
a=gpres[gpres.stratum=="undetermined-gold"].groupby("m").is_und.agg(["mean","sum","count"])
a.columns=["acc_on_undetermined_stratum","n_correct","n"]
a["acc_on_undetermined_stratum"]=a["acc_on_undetermined_stratum"].round(3)
a["n_wrong"]=a["n"]-a["n_correct"]
print(a.to_string()); a.to_csv(OUT/"p1e_undetermined_stratum_accuracy.csv")
