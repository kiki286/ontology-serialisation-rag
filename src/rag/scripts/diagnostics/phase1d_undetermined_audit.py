import json, sys
from pathlib import Path
import pandas as pd, yaml
RES=Path("experiment/results/postretrieval-combined-15-18")
tasks={t["task_id"]:t for t in yaml.safe_load(Path("experiment/benchmark/tasks_60.yaml").read_text(encoding="utf-8"))}
df=pd.read_csv(RES/"postretrieval_raw.csv",usecols=["task_type","task_id","condition","model","format",
    "pred_label","grade_gold_label","context_chunk_ids","n_context_chunks","context_char_len"],low_memory=False)
v=df[df.task_type=="verification"].copy()
def stats(r):
    g=set(tasks[r.task_id].get("retrieval_gold_chunks") or [])
    try: ctx=set(json.loads(r.context_chunk_ids))
    except Exception: return pd.Series({"ngold":len(g),"nhit":0,"nnon":0})
    return pd.Series({"ngold":len(g),"nhit":len(g&ctx),"nnon":len(ctx-g)})
v=v.join(v.apply(stats,axis=1))
v["gold_all"]=(v.nhit==v.ngold).astype(int)
print("verification retrieval_gold_chunks size distribution:")
print(v.drop_duplicates("task_id").ngold.value_counts().sort_index().to_string())
print("\nnon-gold ('distractor') chunks in context, by condition (gold fully present rows only):")
print(v[v.gold_all==1].groupby("condition").agg(
    n_rows=("nnon","size"), mean_nongold=("nnon","mean"),
    mean_chunks=("n_context_chunks","mean"), mean_chars=("context_char_len","mean")).round(2).to_string())
print("\nGPT arms, retrieved, gold fully present, >=1 non-gold chunk — undetermined count:")
sub=v[(v.condition=="retrieved")&(v.gold_all==1)&(v.nnon>=1)&
      (v.model.isin(["gpt-4o-2024-11-20","gpt-4o-mini-2024-07-18"]))]
print(sub.groupby("model").agg(n=("pred_label","size"),
   n_und=("pred_label",lambda s:(s=="undetermined").sum())).to_string())
print("\n  ...undetermined-gold items only:")
s2=sub[sub.grade_gold_label=="undetermined"]
print(s2.groupby("model").agg(n=("pred_label","size"),
   n_und=("pred_label",lambda s:(s=="undetermined").sum())).to_string())
print("\nDistinct undetermined-gold verification items:", 
      v[v.grade_gold_label=="undetermined"].task_id.nunique(),
      sorted(v[v.grade_gold_label=="undetermined"].task_id.unique()))
