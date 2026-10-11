"""Phase 1c: discriminativeness + mechanism read of the reasoning text. No API calls."""
import json, sys, re
from pathlib import Path
import pandas as pd, yaml
pd.set_option("display.width", 220)
RES = Path("experiment/results/postretrieval-combined-15-18")
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
tasks = {t["task_id"]: t for t in yaml.safe_load(
    Path("experiment/benchmark/tasks_60.yaml").read_text(encoding="utf-8"))}
COLS=["trial_idx","task_id","task_type","format","condition","model","pred_label",
      "grade_gold_label","context_chunk_ids","raw_response"]
df=pd.read_csv(RES/"postretrieval_raw.csv",usecols=COLS,low_memory=False)
ver=df[df.task_type=="verification"].copy()
SHORT={"claude-sonnet-4-5-20250929":"sonnet","gpt-4o-2024-11-20":"gpt-4o",
       "gpt-4o-mini-2024-07-18":"gpt-4o-mini","llama3.1:8b-instruct-q8_0":"llama"}
ver["m"]=ver.model.map(SHORT); ver["is_und"]=(ver.pred_label=="undetermined").astype(int)
def gf(r):
    g=set(tasks[r.task_id].get("retrieval_gold_chunks") or [])
    try: return len(g&set(json.loads(r.context_chunk_ids)))/len(g)
    except Exception: return None
ver["gold_all"]=(ver.apply(gf,axis=1)==1.0).astype(int)

print("[P1c.1] Is the label used DISCRIMINATIVELY? (gold-present rows only, both conditions)")
gp=ver[ver.gold_all==1].copy(); gp["und_gold"]=(gp.grade_gold_label=="undetermined")
t=gp.groupby(["m","und_gold"]).is_und.agg(["mean","sum","count"])
t.columns=["und_rate","n_und","n"]; t["und_rate"]=t["und_rate"].round(3)
print(t.to_string())
piv=gp.pivot_table(index="m",columns="und_gold",values="is_und",aggfunc="mean").round(3)
piv.columns=["gold_determinate","gold_undetermined"]
piv["discrimination"]=(piv.gold_undetermined-piv.gold_determinate).round(3)
print("\n  discrimination = P(und|gold=und) - P(und|gold determinate):")
print(piv.to_string()); piv.to_csv(OUT/"p1c_discrimination.csv")

print("\n[P1c.2] Mechanism read — reasoning on undetermined-gold rows answered 'contradicted'")
sub=ver[(ver.grade_gold_label=="undetermined")&(ver.pred_label=="contradicted")].copy()
def reason(s):
    try: return json.loads(s).get("reasoning","")
    except Exception: return ""
sub["reasoning"]=sub.raw_response.map(reason)
CUES={
 "explicit-negation claim (disjoint/not a/never)": r"disjoint|is not a|are not|cannot be|never",
 "absence-as-refutation (no axiom/not stated/does not state)": r"no\s+(axiom|statement|assertion|relation|evidence)|not\s+(stated|asserted|declared|defined|specified)|does not (state|assert|define|specify|indicate)|nothing in",
 "hierarchy mismatch (subclass/superclass/hierarchy)": r"subclass|superclass|hierarch|taxonom",
 "domain/range": r"domain|range",
}
rows=[]
for m,g in sub.groupby("m"):
    d={"model":m,"n_rows":len(g)}
    for k,p in CUES.items():
        d[k]=round(g.reasoning.str.contains(p,case=False,regex=True,na=False).mean(),3)
    rows.append(d)
mech=pd.DataFrame(rows)
print(mech.to_string(index=False)); mech.to_csv(OUT/"p1c_mechanism_cues.csv",index=False)

print("\n[P1c.3] verbatim sample — GPT arms, oracle, undetermined-gold, answered contradicted")
s=sub[(sub.condition=="oracle")&(sub.m.isin(["gpt-4o","gpt-4o-mini"]))]
samp=s.groupby(["m","task_id"],group_keys=False).head(1).head(12)
with (OUT/"p1c_reasoning_sample.txt").open("w",encoding="utf-8") as f:
    for _,r in samp.iterrows():
        line=f"[{r.m} | {r.task_id} | {r.format}] {r.reasoning}"
        f.write(line+"\n\n"); print("  -",line[:230])
