"""Assert every quantitative claim in the dissertation against the frozen run outputs.

Companion to `scripts/make_thesis_figures.py`, which pins the six results-chapter
figures to the same CSVs. This script does the same job for the prose, the tables
and the captions of the abstract and Chapters 1, 3, 4 and 5: each documented value
below is transcribed from a chapter .tex file (file and line noted), recomputed
here from
`experiment/results/postretrieval-combined-15-18/`,
`experiment/results/retrieval-trial-14/`,
`experiment/results/probe_b2_openworld/`, the frozen indexes under
`experiment/indexes/`, the benchmark instrument under `experiment/benchmark/`
and the frozen contrast CSVs under `scripts/diagnostics/results/`, and compared.
The script exits non-zero and lists every mismatch rather than stopping at the
first.

The ontology corpus is licensed and not redistributed, and the FAISS indexes
embed its text, so neither is in the repository. The three check groups that
read them (`check_corpus`, `check_crowding`, `check_appendix_b`) skip with a
"needs the licensed ontology" message when they are absent; see the README,
"The ontology corpus", for where a licensed copy goes.

Read-only: it never writes to the results trees.

Usage (from src/rag/):
    python -m scripts.diagnostics.check_thesis_numbers
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import re

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMBINED = ROOT / "experiment" / "results" / "postretrieval-combined-15-18"
RAW_PATH = COMBINED / "postretrieval_raw.csv"
SCORED_PATH = COMBINED / "postretrieval_scored.csv"
VARIANCE_PATH = COMBINED / "postretrieval_variance.csv"
RETRIEVAL_PATH = ROOT / "experiment" / "results" / "retrieval-trial-14" / "retrieval_raw.csv"
PROBE_RAW = ROOT / "experiment" / "results" / "probe_b2_openworld" / "postretrieval_raw.csv"
CONTRASTS = ROOT / "scripts" / "diagnostics" / "results" / "verification_headline_selective" / "paired_contrasts.csv"
PER_FORMAT = ROOT / "scripts" / "diagnostics" / "results" / "verification_headline_selective" / "per_format_selective.csv"
COLLAPSED = ROOT / "scripts" / "diagnostics" / "results" / "collapsed_group_sensitivity" / "collapsed_group_sensitivity_contrasts.csv"
PER_CLASS = ROOT / "scripts" / "diagnostics" / "results" / "verification_per_class_intervals" / "per_class_intervals.csv"
TASKS = ROOT / "experiment" / "benchmark" / "tasks_60.yaml"
AUTHORING_MEASUREMENTS = ROOT / "experiment" / "benchmark" / "authoring_constraint_measurements.json"
INDEXES = ROOT / "experiment" / "indexes"
REPO = ROOT.parents[1]
DETERMINISM_PATH = ROOT / "experiment" / "results" / "determinism-probe-1" / "determinism_raw.csv"
PILOT_COMBINED = ROOT / "experiment" / "results" / "postretrieval-combined-8-9"
WHOLE_CONTEXT = ROOT / "experiment" / "results" / "postretrieval-trial-12"
PILOT_RETRIEVAL = (ROOT / "experiment" / "results" / "superseded"
                   / "retrieval-trial-11" / "retrieval_scored.csv")
TURTLE_SOURCE = ROOT / "data" / "LIS-14-for-FDIS (1).ttl"

FORMATS = [
    ("turtle", "Turtle"),
    ("omn", "OMN"),
    ("ofn", "OFN"),
    ("jsonld", "JSON-LD"),
    ("yaml-ld", "YAML-LD"),
    ("elot-org", "ELOT-flat"),
    ("elot-org-ancestors", "ELOT-nested"),
]
FMT_IDS = [f for f, _ in FORMATS]

ARMS = {
    "claude-sonnet-4-5-20250929": "Sonnet",
    "gpt-4o-2024-11-20": "GPT-4o",
    "gpt-4o-mini-2024-07-18": "GPT-4o-mini",
    "llama3.1:8b-instruct-q8_0": "Llama",
}

ANSWER_FIELDS = ["grade_class_correct", "grade_property_correct",
                 "grade_intermediate_correct"]
CITATION_FIELDS = ["grade_support_class_correct", "grade_support_property_correct",
                   "grade_support_intermediate_correct"]

FAILURES = []
SKIPS = []
PASSES = 0


class NeedsOntology(Exception):
    """A check group reads the licensed ontology or the indexes built from it."""


def check(where, name, got, want, tol=0.001):
    """Compare a recomputed value against the value documented in the chapters."""
    global PASSES
    if got is None or (isinstance(got, float) and np.isnan(got)):
        FAILURES.append(f"{where}  {name}: could not compute (documented {want})")
        return
    if abs(float(got) - float(want)) > tol:
        FAILURES.append(f"{where}  {name}: computed {float(got):.4f}, "
                        f"chapter says {float(want)}")
        return
    PASSES += 1
    print(f"  ok  {where}  {name}: {float(got):.4f}")


def section(title):
    print(f"\n{title}")


# ------------------------------------------------------------------ loaders
def load():
    raw = pd.read_csv(RAW_PATH)
    scored = pd.read_csv(SCORED_PATH)
    retrieval = pd.read_csv(RETRIEVAL_PATH)
    tasks = pd.DataFrame(yaml.safe_load(TASKS.read_text(encoding="utf-8")))
    return raw, scored, retrieval, tasks


def determinate(raw):
    """Verification rows on the 20 items whose gold label is not undetermined."""
    return raw[(raw.task_type == "verification")
               & (raw.grade_gold_label != "undetermined")]


# ------------------------------------------------- 4.1 integrity and cost
def check_integrity(raw, scored):
    section("4.1 Run integrity, trial stability and cost (results.tex L17-L61)")
    check("results L17", "model calls", len(raw), 10080, tol=0)
    check("results L17", "scored cells", len(scored), 3360, tol=0)
    check("results L19", "parse failures", (~raw.parse_ok.astype(bool)).sum(), 2, tol=0)
    check("results L20", "parse failure rate pct",
          100 * (~raw.parse_ok.astype(bool)).sum() / len(raw), 0.02, tol=0.005)
    # no missing or duplicate cells
    cell = raw.groupby(["task_id", "format", "condition", "model"]).size()
    check("results L18", "cells with exactly 3 trials", (cell == 3).sum(), 3360, tol=0)
    check("results L18", "distinct cells", len(cell), 3360, tol=0)

    # postretrieval_variance.csv is per-metric, so graded-field stability is
    # recomputed here: a cell is stable when its full grade dictionary is
    # identical across all three trials.
    grade_cols = [c for c in raw.columns if c.startswith("grade_")]
    stable = (raw.groupby(["task_id", "format", "condition", "model"])[grade_cols]
                 .apply(lambda d: int(d.astype(str).drop_duplicates().shape[0] == 1)))
    check("results L24", "overall graded-field stability", stable.mean(), 0.963,
          tol=0.001)
    documented = {"claude-sonnet-4-5-20250929": 0.985,
                  "gpt-4o-2024-11-20": 0.975,
                  "llama3.1:8b-instruct-q8_0": 0.952,
                  "gpt-4o-mini-2024-07-18": 0.941}
    by_arm = stable.reset_index().groupby("model")[0].mean()
    for mid, want in documented.items():
        check("tab:integrity", f"stability {ARMS[mid]}", by_arm.get(mid), want,
              tol=0.001)
    # 0.963 is roughly one unstable cell in twenty-seven
    check("results L25", "cells per unstable cell", 1 / (1 - stable.mean()), 27,
          tol=0.6)


# ---------------------------------------- 4.2 verification and the collapse
def check_collapse(raw):
    section("4.2 Verification and the undetermined collapse (results.tex L66-L235)")
    ver = raw[raw.task_type == "verification"]
    check("results L67", "verification items", ver.task_id.nunique(), 30, tol=0)
    check("results L83", "verification rows", len(ver), 5040, tol=0)
    check("results L67", "three-way accuracy, all items",
          ver.grade_correct.mean(), 0.556, tol=0.001)
    check("results L67", "coverage, all items",
          ver.grade_answered.mean(), 0.898, tol=0.001)

    und = ver[ver.grade_gold_label == "undetermined"]
    check("results L84", "undetermined-gold rows", len(und), 1680, tol=0)
    check("results L84", "pct undetermined-gold answered contradicted",
          100 * (und.grade_pred_label == "contradicted").mean(), 90.8, tol=0.05)
    check("results L85", "undetermined-gold answered supported",
          (und.grade_pred_label == "supported").sum(), 0, tol=0)

    # per-class intervals the chapters cite as too wide to report
    # (scripts/diagnostics/verification_per_class_intervals.py)
    per_class = pd.read_csv(PER_CLASS).set_index(["label", "statistic"])
    for where in ("results L75-L76", "method L542-L543"):
        check(where, "contradicted precision interval width",
              per_class.loc[("contradicted", "precision"), "width"], 0.40, tol=0.005)
        check(where, "undetermined precision interval width",
              per_class.loc[("undetermined", "precision"), "width"], 0.49, tol=0.005)
    check("results L76", "contradicted precision point estimate",
          per_class.loc[("contradicted", "precision"), "point"], 0.43, tol=0.005)
    check("results L76", "undetermined precision point estimate",
          per_class.loc[("undetermined", "precision"), "point"], 0.30, tol=0.005)

    det = determinate(raw)
    check("results L67", "determinate items", det.task_id.nunique(), 20, tol=0)

    # selective prediction by arm, determinate items only (tab:verification-models)
    documented = {
        "claude-sonnet-4-5-20250929": (0.900, 1.000, 0.900, 0.264),
        "gpt-4o-2024-11-20": (0.925, 0.923, 0.854, 0.029),
        "gpt-4o-mini-2024-07-18": (0.967, 0.819, 0.792, 0.012),
        "llama3.1:8b-instruct-q8_0": (0.783, 0.775, 0.606, 0.062),
    }
    for mid, (cov, acc_ans, acc_all, abst) in documented.items():
        d = det[det.model == mid]
        check("tab:verification-models", f"coverage {ARMS[mid]}",
              d.grade_answered.mean(), cov, tol=0.001)
        check("tab:verification-models", f"acc on answered {ARMS[mid]}",
              d.grade_selective_correct.sum() / d.grade_answered.sum(), acc_ans,
              tol=0.001)
        check("tab:verification-models", f"acc all rows {ARMS[mid]}",
              d.grade_selective_correct.mean(), acc_all, tol=0.001)
        u = und[und.model == mid]
        check("tab:verification-models", f"correct abstention {ARMS[mid]}",
              (u.grade_pred_label == "undetermined").mean(), abst, tol=0.001)

    check("tab:verification-models", "pooled coverage, determinate",
          det.grade_answered.mean(), 0.894, tol=0.001)
    check("tab:verification-models", "pooled acc on answered",
          det.grade_selective_correct.sum() / det.grade_answered.sum(), 0.882,
          tol=0.001)
    check("tab:verification-models", "pooled acc all rows",
          det.grade_selective_correct.mean(), 0.788, tol=0.001)

    sonnet = det[det.model == "claude-sonnet-4-5-20250929"]
    check("results L98", "Sonnet answered rows, determinate",
          sonnet.grade_answered.sum(), 756, tol=0)
    check("results L98", "Sonnet errors on answered determinate rows",
          sonnet.grade_answered.sum() - sonnet.grade_selective_correct.sum(), 0,
          tol=0)

    # gold gating (tab:gold-gating): gold presence is gold chunks subset of the
    # context, as in scripts/diagnostics/phase1e_undetermined_audit.py
    tasks = {t["task_id"]: t for t in
             yaml.safe_load(TASKS.read_text(encoding="utf-8"))}

    def gold_present(row):
        gold = set(tasks[row.task_id].get("retrieval_gold_chunks") or [])
        try:
            return gold <= set(json.loads(row.context_chunk_ids))
        except Exception:
            return False

    gated = ver.copy()
    gated["gold_present"] = gated.apply(gold_present, axis=1)
    gated["determ"] = gated.grade_gold_label != "undetermined"
    gated["said_und"] = gated.pred_label == "undetermined"
    table = {
        "gpt-4o-2024-11-20": (0.356, 0.182, 0.000, 0.000),
        "gpt-4o-mini-2024-07-18": (0.147, 0.076, 0.003, 0.000),
        "llama3.1:8b-instruct-q8_0": (0.497, 0.318, 0.142, 0.014),
        "claude-sonnet-4-5-20250929": (0.475, 0.333, 0.000, 0.251),
    }
    for mid, (ad, au, pd_, pu) in table.items():
        g = gated[gated.model == mid]
        for present, determ, want, label in (
                (False, True, ad, "gold-absent determinate"),
                (False, False, au, "gold-absent undetermined"),
                (True, True, pd_, "gold-present determinate"),
                (True, False, pu, "gold-present undetermined")):
            sub = g[(g.gold_present == present) & (g.determ == determ)]
            check("tab:gold-gating", f"{ARMS[mid]} {label}",
                  sub.said_und.mean(), want, tol=0.001)

    # n per cell footnote: 177, 66, 663, 354 (identical for every arm)
    for present, determ, want, label in (
            (False, True, 177, "gold-absent determinate"),
            (False, False, 66, "gold-absent undetermined"),
            (True, True, 663, "gold-present determinate"),
            (True, False, 354, "gold-present undetermined")):
        per_arm = {len(gated[(gated.model == m) & (gated.gold_present == present)
                             & (gated.determ == determ)]) for m in ARMS}
        check("tab:gold-gating", f"n per cell, {label}",
              per_arm.pop() if len(per_arm) == 1 else -1, want, tol=0)

    # discrimination: gold-present undetermined rate on the undetermined stratum
    # minus the same rate on the determinate stratum
    gp = gated[gated.gold_present]
    disc = {"claude-sonnet-4-5-20250929": 0.251, "gpt-4o-2024-11-20": 0.000,
            "gpt-4o-mini-2024-07-18": -0.003, "llama3.1:8b-instruct-q8_0": -0.128}
    for mid, want in disc.items():
        g = gp[gp.model == mid]
        got = (g[~g.determ].said_und.mean() - g[g.determ].said_und.mean())
        check("results L106", f"discrimination {ARMS[mid]}", got, want, tol=0.001)

    # Sonnet still answers contradicted on three-quarters of the undetermined rows
    son_und = und[und.model == "claude-sonnet-4-5-20250929"]
    check("results L113", "Sonnet contradicted rate on undetermined-gold rows",
          (son_und.grade_pred_label == "contradicted").mean(), 0.75, tol=0.03)

    # pooled gold-absent abstention range across arms, 0.128 to 0.449
    pooled = gated[~gated.gold_present].groupby("model").said_und.mean()
    check("results L148", "gold-absent abstention, min arm", pooled.min(), 0.128,
          tol=0.001)
    check("results L148", "gold-absent abstention, max arm", pooled.max(), 0.449,
          tol=0.001)

    # GPT-4o undetermined rate under retrieved, 11.9%
    g4 = ver[(ver.model == "gpt-4o-2024-11-20") & (ver.condition == "retrieved")]
    check("results L184", "GPT-4o undetermined rate under retrieved (pct)",
          100 * (g4.grade_pred_label == "undetermined").mean(), 11.9, tol=0.05)


# --------------------------------------------------- 4.3 citation vs answer
def check_citation(raw):
    section("4.3 Citation versus answer (results.tex L241-L305)")
    sf = raw[raw.task_type == "slot_filling"]
    check("results L246", "slot-filling items", sf.task_id.nunique(), 30, tol=0)

    ans = sf[ANSWER_FIELDS].mean(axis=1)
    cit = sf[CITATION_FIELDS].mean(axis=1)
    sf = sf.assign(_ans=ans, _cit=cit)
    documented = {
        "llama3.1:8b-instruct-q8_0": (0.807, 0.266),
        "gpt-4o-2024-11-20": (0.844, None),
        "claude-sonnet-4-5-20250929": (0.840, None),
    }
    for mid, (a, c) in documented.items():
        m = sf[sf.model == mid]
        check("results L248", f"answer fields {ARMS[mid]}", m._ans.mean(), a,
              tol=0.001)
        if c is not None:
            check("results L249", f"citation fields {ARMS[mid]}", m._cit.mean(), c,
                  tol=0.001)

    for cond, a, c in (("oracle", 0.953, 0.789), ("retrieved", 0.661, 0.346)):
        s = sf[sf.condition == cond]
        check("results L254", f"answer fields under {cond}", s._ans.mean(), a,
              tol=0.001)
        check("results L254", f"citation fields under {cond}", s._cit.mean(), c,
              tol=0.001)

    # tab:citation-fields
    grades = {"support_class": "grade_support_class_correct",
              "support_property": "grade_support_property_correct",
              "support_intermediate": "grade_support_intermediate_correct"}
    table = {"support_class": (0.562, 0.864, 0.260),
             "support_property": (0.637, 0.867, 0.408),
             "support_intermediate": (0.183, 0.123, 0.243)}
    for field, (overall, oracle, retrieved) in table.items():
        col = grades[field]
        vals = sf[col].dropna()
        check("tab:citation-fields", f"{field} overall", vals.mean(), overall,
              tol=0.001)
        check("tab:citation-fields", f"{field} oracle",
              sf.loc[sf.condition == "oracle", col].dropna().mean(), oracle,
              tol=0.001)
        check("tab:citation-fields", f"{field} retrieved",
              sf.loc[sf.condition == "retrieved", col].dropna().mean(), retrieved,
              tol=0.001)

    si = sf[sf.grade_support_intermediate_correct.notna()]
    check("tab:citation-fields", "support_intermediate graded items",
          si.task_id.nunique(), 10, tol=0)
    per_item = (si.groupby(["task_id", "condition"])
                  .grade_support_intermediate_correct.mean().unstack("condition"))
    diff = (per_item["oracle"] - per_item["retrieved"])
    check("results L296", "support_intermediate oracle minus retrieved",
          diff.mean(), -0.120, tol=0.002)
    # RESOLVED: the chapter now reads "four of the ten items score zero under
    # both conditions and four of the remaining six belong to one duplicate-shape
    # group". The four zero-under-both items are T42, T43, T57, T58; the
    # duplicate-shape group among the remaining six is T40, T41, T55, T56.
    check("results L299", "support_intermediate items zero under both",
          int(((per_item["oracle"] == 0) & (per_item["retrieved"] == 0)).sum()), 4,
          tol=0)


# ----------------------------------------------------------- 4.4 retrieval
def check_retrieval(retrieval, raw):
    section("4.4 Retrieval, RQ1 (results.tex L316-L378)")
    # retrieval_raw.csv carries no query_source; take it from the item metadata
    # in the post-retrieval raw, keyed on task_id
    meta = raw.drop_duplicates("task_id").set_index("task_id").query_source
    retrieval = retrieval.assign(query_source=retrieval.task_id.map(meta))
    check("tab:retrieval-formats", "retrieval rows", len(retrieval), 420, tol=0)
    check("results L358", "retrieval items", retrieval.task_id.nunique(), 60, tol=0)

    narrow = retrieval.groupby("format").recall_at_k.mean().reindex(FMT_IDS)
    broad = retrieval.groupby("format").gold_recall_at_k.mean().reindex(FMT_IDS)
    mrr = retrieval.groupby("format").mrr.mean().reindex(FMT_IDS)
    ndcg = retrieval.groupby("format").ndcg_at_k.mean().reindex(FMT_IDS)

    check("results L319", "recall@5 min", narrow.min(), 0.623, tol=0.001)
    check("results L319", "recall@5 max", narrow.max(), 0.667, tol=0.001)
    check("results L320", "recall@5 spread", narrow.max() - narrow.min(), 0.044,
          tol=0.001)
    check("results L325", "MRR spread", mrr.max() - mrr.min(), 0.057, tol=0.001)
    check("results L325", "nDCG@5 spread", ndcg.max() - ndcg.min(), 0.032, tol=0.001)
    check("results L326", "broad recall spread", broad.max() - broad.min(), 0.024,
          tol=0.001)

    table = {
        "omn": (0.667, 0.663, 0.621, 0.579),
        "ofn": (0.659, 0.654, 0.632, 0.581),
        "elot-org-ancestors": (0.659, 0.651, 0.614, 0.573),
        "jsonld": (0.653, 0.660, 0.671, 0.594),
        "elot-org": (0.652, 0.641, 0.629, 0.572),
        "turtle": (0.641, 0.641, 0.669, 0.598),
        "yaml-ld": (0.623, 0.639, 0.642, 0.566),
    }
    label = dict(FORMATS)
    for fid, (n, b, m, d) in table.items():
        check("tab:retrieval-formats", f"{label[fid]} recall narrow", narrow[fid], n,
              tol=0.001)
        check("tab:retrieval-formats", f"{label[fid]} recall broad", broad[fid], b,
              tol=0.001)
        check("tab:retrieval-formats", f"{label[fid]} MRR", mrr[fid], m, tol=0.001)
        check("tab:retrieval-formats", f"{label[fid]} nDCG@5", ndcg[fid], d, tol=0.001)

    by_type = retrieval.groupby(["task_type", "format"]).recall_at_k.mean()
    ver = by_type.loc["verification"]
    sf = by_type.loc["slot_filling"]
    check("results L341", "verification recall min", ver.min(), 0.779, tol=0.001)
    check("results L341", "verification recall max", ver.max(), 0.868, tol=0.001)
    check("results L342", "slot-filling recall min", sf.min(), 0.433, tol=0.001)
    check("results L342", "slot-filling recall max", sf.max(), 0.500, tol=0.001)

    # tab:query-source
    qs_n = {"label": 29, "definition": 5, "example": 7, "paraphrase": 19}
    per_fmt_item = retrieval.drop_duplicates(["task_id", "format"])
    for src, want_n in qs_n.items():
        sub = per_fmt_item[per_fmt_item.query_source == src]
        check("tab:query-source", f"{src} n", sub.task_id.nunique(), want_n, tol=0)
    qs_table = {
        "label": dict(zip(["turtle", "elot-org", "elot-org-ancestors", "omn",
                           "jsonld", "yaml-ld", "ofn"],
                          [0.839, 0.786, 0.834, 0.840, 0.810, 0.783, 0.806])),
        "definition": dict(zip(["turtle", "elot-org", "elot-org-ancestors", "omn",
                                "jsonld", "yaml-ld", "ofn"],
                               [0.600, 0.700, 0.700, 0.600, 0.700, 0.600, 0.600])),
        "example": dict(zip(["turtle", "elot-org", "elot-org-ancestors", "omn",
                             "jsonld", "yaml-ld", "ofn"],
                            [0.429, 0.500, 0.500, 0.429, 0.429, 0.429, 0.429])),
        "paraphrase": dict(zip(["turtle", "elot-org", "elot-org-ancestors", "omn",
                                "jsonld", "yaml-ld", "ofn"],
                               [0.430, 0.491, 0.439, 0.509, 0.483, 0.456, 0.535])),
    }
    spreads = {"label": 0.057, "definition": 0.100, "example": 0.071,
               "paraphrase": 0.105}
    for src, row in qs_table.items():
        sub = retrieval[retrieval.query_source == src]
        got = sub.groupby("format").recall_at_k.mean()
        for fid, want in row.items():
            check("tab:query-source", f"{src} {label[fid]}", got.get(fid), want,
                  tol=0.001)
        check("tab:query-source", f"{src} spread", got.max() - got.min(),
              spreads[src], tol=0.001)


# ---------------------------------------------- 4.5 post-retrieval effects
def check_format_effects(raw, scored, retrieval):
    section("4.5 Post-retrieval format effects, RQ2 (results.tex L385-L500)")
    det = determinate(raw)
    cov = det.groupby("format").grade_answered.mean().reindex(FMT_IDS)
    acc = (det.groupby("format").grade_selective_correct.sum()
           / det.groupby("format").grade_answered.sum()).reindex(FMT_IDS)
    sf = scored[scored.task_type == "slot_filling"]
    pc = sf.groupby("format").mean_partial_credit_mean.mean().reindex(FMT_IDS)
    rec = retrieval.groupby("format").recall_at_k.mean().reindex(FMT_IDS)

    check("results L393", "recall@5 spread", rec.max() - rec.min(), 0.044, tol=0.001)
    check("results L393", "coverage spread", cov.max() - cov.min(), 0.044, tol=0.001)
    check("results L394", "acc-on-answered spread", acc.max() - acc.min(), 0.080,
          tol=0.001)
    check("results L394", "slot-filling PC spread", pc.max() - pc.min(), 0.024,
          tol=0.001)

    table = {
        "omn": (0.667, 0.917, 0.918, 0.706),
        "ofn": (0.659, 0.896, 0.900, 0.705),
        "elot-org-ancestors": (0.659, 0.881, 0.882, 0.684),
        "jsonld": (0.653, 0.896, 0.867, 0.708),
        "elot-org": (0.652, 0.887, 0.866, 0.703),
        "turtle": (0.641, 0.906, 0.899, 0.685),
        "yaml-ld": (0.623, 0.873, 0.838, 0.702),
    }
    label = dict(FORMATS)
    for fid, (r, c, a, p) in table.items():
        check("tab:headline-formats", f"{label[fid]} recall@5", rec[fid], r, tol=0.001)
        check("tab:headline-formats", f"{label[fid]} verif coverage", cov[fid], c,
              tol=0.001)
        check("tab:headline-formats", f"{label[fid]} verif acc ans", acc[fid], a,
              tol=0.001)
        check("tab:headline-formats", f"{label[fid]} slot-fill PC", pc[fid], p,
              tol=0.001)

    # 84 headline contrasts = 4 families x 21 pairs
    check("results L386", "headline contrasts", 4 * 21, 84, tol=0)

    if CONTRASTS.exists():
        con = pd.read_csv(CONTRASTS)
        aoa = con[con.metric == "acc_on_answered"]
        check("results L400", "acc-on-answered paired contrasts", len(aoa), 21, tol=0)
        check("results L400", "acc-on-answered nominal hits",
              int((aoa.p < 0.05).sum()), 5, tol=0)
        check("results L401", "acc-on-answered Holm survivors",
              int((aoa.p_holm < 0.05).sum()), 3, tol=0)

        def delta(a, b):
            row = aoa[(aoa.a == a) & (aoa.b == b)]
            if len(row):
                return float(row.delta.iloc[0]), float(row.lo.iloc[0]), float(row.hi.iloc[0])
            row = aoa[(aoa.a == b) & (aoa.b == a)]
            if len(row):
                return (-float(row.delta.iloc[0]), -float(row.hi.iloc[0]),
                        -float(row.lo.iloc[0]))
            return None

        d = delta("omn", "yaml-ld")
        if d is None:
            FAILURES.append("results L402  OMN over YAML-LD: contrast not in "
                            "paired_contrasts.csv")
        else:
            check("results L402", "OMN over YAML-LD delta", d[0], 0.074, tol=0.001)
            check("results L402", "OMN over YAML-LD CI lo", d[1], 0.030, tol=0.001)
            check("results L402", "OMN over YAML-LD CI hi", d[2], 0.126, tol=0.001)
        for other, want in (("jsonld", 0.047), ("elot-org", 0.048)):
            d = delta("omn", other)
            if d is None:
                FAILURES.append(f"results L403  OMN over {other}: contrast missing")
            else:
                check("results L403", f"OMN over {label[other]} delta", d[0], want,
                      tol=0.001)

    # duplicate-shape group correlations
    groups = {("T40", "T41", "T55", "T56"): 0.807, ("T42", "T43", "T57", "T58"): 0.944}
    item = (scored[scored.task_type == "slot_filling"]
            .groupby(["task_id", "format", "condition", "model"])
            .mean_partial_credit_mean.mean().unstack("task_id"))
    for members, want in groups.items():
        sub = item[list(members)]
        corr = sub.corr()
        vals = [corr.iloc[i, j] for i in range(len(members))
                for j in range(i + 1, len(members))]
        check("results L423", f"mean pairwise r {'/'.join(members)}",
              float(np.mean(vals)), want, tol=0.005)

    # oracle minus retrieved, per format
    sf_item = (scored[scored.task_type == "slot_filling"]
               .groupby(["task_id", "format", "condition"])
               .mean_partial_credit_mean.mean().unstack("condition"))
    deltas = (sf_item["oracle"] - sf_item["retrieved"]).unstack("format")[FMT_IDS]
    check("results L437", "min context effect, slot-filling", deltas.mean().min(),
          0.320, tol=0.002)
    check("results L437", "max context effect, slot-filling", deltas.mean().max(),
          0.374, tol=0.002)
    check("results L437", "slot-filling paired items", len(deltas), 30, tol=0)

    ver_all = raw[raw.task_type == "verification"]
    v_item = (ver_all.groupby(["task_id", "format", "condition"])
                     .grade_correct.mean().unstack("condition"))
    v_delta = (v_item["oracle"] - v_item["retrieved"]).unstack("format")[FMT_IDS]
    check("results L444", "min context effect, verification", v_delta.mean().min(),
          0.067, tol=0.001)
    check("results L444", "max context effect, verification", v_delta.mean().max(),
          0.136, tol=0.001)

    if COLLAPSED.exists():
        col = pd.read_csv(COLLAPSED)
        print(f"  .. collapsed_group_sensitivity_contrasts.csv columns: "
              f"{list(col.columns)}")


# ---------------------------------------------- 4.6 mechanisms and corpus
def check_mechanisms(raw, retrieval):
    section("4.6 Mechanism effects and corpus findings (results.tex L506-L595)")
    ver = raw[raw.task_type == "verification"]
    by_mech = ver.groupby("mechanism").grade_correct.mean()
    check("results L508", "bare_disjointness accuracy",
          by_mech.get("bare_disjointness"), 0.994, tol=0.001)
    check("results L509", "unasserted_class_relation accuracy",
          by_mech.get("unasserted_class_relation"), 0.092, tol=0.001)

    for tid, want, n in (("T06", 1.000, 168), ("T08", 1.000, 168),
                         ("T62", 0.738, None), ("T61", 0.685, None)):
        sub = ver[ver.task_id == tid]
        check("tab:depth", f"{tid} accuracy", sub.grade_correct.mean(), want,
              tol=0.001)
        if n is not None:
            check("tab:depth", f"{tid} rows", len(sub), n, tol=0)
    check("results L511", "bare_disjointness and functional_property items",
          ver[ver.mechanism.isin(["bare_disjointness", "functional_property"])]
          .task_id.nunique(), 5, tol=0)
    check("results L515", "T61 accuracy penalty vs T06",
          1.0 - ver[ver.task_id == "T61"].grade_correct.mean(), 0.32, tol=0.005)
    check("results L515", "T62 accuracy penalty vs T06",
          1.0 - ver[ver.task_id == "T62"].grade_correct.mean(), 0.26, tol=0.005)

    # RESOLVED: the chapter now reads "answered correctly in 336 of 336 rows",
    # which counts the T06/T08 pair rather than one item's 168 rows.
    t06t08 = ver[ver.task_id.isin(["T06", "T08"])]
    check("results L515", "T06+T08 correct rows", int(t06t08.grade_correct.sum()),
          336, tol=0)
    check("results L515", "T06+T08 total rows", len(t06t08), 336, tol=0)


# --------------------------------------------- 4.7 the one local effect
ONE_HOP = ["T09", "T10"]          # subsumption resting on one asserted axiom
MULTI_HOP = ["T11", "T12", "T13", "T14", "T15", "T16", "T17", "T18"]
NESTED = "elot-org-ancestors"


def check_local_effect(raw):
    section("4.7 The one local format effect (results.tex L601-L660)")
    ver = raw[raw.task_type == "verification"]
    one = ver[ver.task_id.isin(ONE_HOP)]
    multi = ver[ver.task_id.isin(MULTI_HOP)]

    nested = one[one.format == NESTED]
    others = one[one.format != NESTED]
    check("results L602", "one-hop items", one.task_id.nunique(), 2, tol=0)
    check("results L603", "ELOT-nested accuracy, one-hop",
          nested.grade_correct.mean(), 0.313, tol=0.001)
    check("results L603", "other six accuracy, one-hop",
          others.grade_correct.mean(), 0.747, tol=0.001)
    check("results L611", "gap",
          others.grade_correct.mean() - nested.grade_correct.mean(), 0.434,
          tol=0.001)
    check("results L610", "ELOT-nested rows on the one-hop pair", len(nested), 48,
          tol=0)
    # "losing 30 of the 48 rows and winning none" is head to head against the
    # mean of the other six formats in the same (item, arm, condition, trial) cell
    cells = one.pivot_table(index=["task_id", "model", "condition", "trial_idx"],
                            columns="format", values="grade_correct")
    rest = [c for c in cells.columns if c != NESTED]
    check("results L610", "cells on the one-hop pair", len(cells), 48, tol=0)
    check("results L610", "rows ELOT-nested loses head to head",
          int((cells[NESTED] < cells[rest].mean(axis=1)).sum()), 30, tol=0)
    check("results L610", "rows ELOT-nested wins head to head",
          int((cells[NESTED] > cells[rest].mean(axis=1)).sum()), 0, tol=0)

    m_nested = multi[multi.format == NESTED].grade_correct.mean()
    m_others = multi[multi.format != NESTED].grade_correct.mean()
    check("results L614", "multi-hop ELOT-nested minus others", m_nested - m_others,
          0.055, tol=0.001)

    check("results L629", "ELOT-nested contradicted rate, one-hop",
          100 * (nested.grade_pred_label == "contradicted").mean(), 62.5, tol=0.05)
    sup = (others.grade_pred_label == "supported").groupby(others["format"]).mean()
    check("results L630", "other six supported rate, min", 100 * sup.min(), 56,
          tol=0.5)
    check("results L630", "other six supported rate, max", 100 * sup.max(), 88,
          tol=0.5)

    # tab:format-by-model
    table = {"claude-sonnet-4-5-20250929": (1.000, 1.000),
             "gpt-4o-2024-11-20": (0.250, 1.000),
             "gpt-4o-mini-2024-07-18": (0.000, 0.708),
             "llama3.1:8b-instruct-q8_0": (0.000, 0.278)}
    for mid, (nested_acc, other_acc) in table.items():
        d = one[one.model == mid]
        check("tab:format-by-model", f"{ARMS[mid]} ELOT-nested",
              d[d.format == NESTED].grade_correct.mean(), nested_acc, tol=0.001)
        check("tab:format-by-model", f"{ARMS[mid]} other six",
              d[d.format != NESTED].grade_correct.mean(), other_acc, tol=0.001)
        check("tab:format-by-model", f"{ARMS[mid]} penalty",
              d[d.format == NESTED].grade_correct.mean()
              - d[d.format != NESTED].grade_correct.mean(),
              nested_acc - other_acc, tol=0.001)



# ---------------------------------------------------------------- helpers
def load_chunks(fmt_id):
    """The indexed chunks for one format, straight out of the frozen FAISS store."""
    path = INDEXES / fmt_id / "index.pkl"
    if not path.exists():
        raise NeedsOntology(f"the FAISS indexes built from it ({path.relative_to(ROOT)} is missing)")
    with open(path, "rb") as handle:
        store, _ = pickle.load(handle)
    return list(store._dict.values())


def context_effect_by_format(scored):
    """Oracle minus retrieved slot-filling partial credit, per format."""
    item = (scored[scored.task_type == "slot_filling"]
            .groupby(["task_id", "format", "condition"])
            .mean_partial_credit_mean.mean().unstack("condition"))
    return (item["oracle"] - item["retrieved"]).unstack("format")[FMT_IDS].mean()


def one_hop_gap(raw, model=None):
    """Accuracy ELOT-nested loses to the other six on the one-hop pair (4.7)."""
    one = raw[(raw.task_type == "verification") & raw.task_id.isin(ONE_HOP)]
    if model is not None:
        one = one[one.model == model]
    return (one[one.format != NESTED].grade_correct.mean()
            - one[one.format == NESTED].grade_correct.mean())


# --------------------------------- 3.2 the ontology, its exports and chunks
def check_corpus():
    section("3.2 Ontology, serialisations and chunking (method.tex L67-L201)")
    import rdflib
    from rdflib.namespace import OWL, RDF

    if not TURTLE_SOURCE.exists():
        raise NeedsOntology(f"the canonical Turtle ({TURTLE_SOURCE.relative_to(ROOT)} is missing)")
    graph = rdflib.Graph()
    graph.parse(TURTLE_SOURCE, format="turtle")
    check("method L75", "canonical Turtle triples", len(graph), 2214, tol=0)
    counts = {}
    for kind in ["Class", "ObjectProperty", "DatatypeProperty", "AnnotationProperty"]:
        counts[kind] = len({s for s in graph.subjects(RDF.type, getattr(OWL, kind))
                            if isinstance(s, rdflib.URIRef)})
    check("method L75", "named classes", counts["Class"], 50, tol=0)
    check("method L75", "object properties", counts["ObjectProperty"], 102, tol=0)
    check("method L75", "data properties", counts["DatatypeProperty"], 3, tol=0)
    check("method L76", "annotation properties", counts["AnnotationProperty"], 42,
          tol=0)
    check("method L76", "named classes and properties",
          counts["Class"] + counts["ObjectProperty"] + counts["DatatypeProperty"],
          155, tol=0)

    # tab:corpus. Each index holds exactly the retrievable chunks, and the
    # token_count metadata is the cl100k_base count written at index time. The
    # p90 column is the lower-observation percentile.
    documented = {
        # format: (retrievable, mean, median, p90, max, total)
        "turtle": (158, 266, 234, 496, 1102, 42063),
        "elot-org": (156, 195, 165, 356, 775, 30440),
        "elot-org-ancestors": (156, 205, 174, 365, 774, 32007),
        "omn": (158, 235, 197, 421, 881, 37192),
        "jsonld": (158, 325, 272, 638, 1473, 51314),
        "yaml-ld": (158, 277, 234, 552, 1265, 43736),
        "ofn": (158, 239, 204, 415, 835, 37702),
    }
    named_ids = {}
    means = {}
    for fid, (n_retr, mean, median, p90, mx, total) in documented.items():
        docs = load_chunks(fid)
        toks = np.array([d.metadata["token_count"] for d in docs])
        check("tab:corpus", f"{fid} retrievable chunks", len(docs), n_retr, tol=0)
        check("tab:corpus", f"{fid} mean tokens", round(toks.mean()), mean, tol=0)
        check("tab:corpus", f"{fid} median tokens", round(np.median(toks)),
              median, tol=0)
        check("tab:corpus", f"{fid} p90 tokens",
              np.percentile(toks, 90, method="lower"), p90, tol=0)
        check("tab:corpus", f"{fid} max tokens", toks.max(), mx, tol=0)
        check("tab:corpus", f"{fid} total tokens", toks.sum(), total, tol=0)
        means[fid] = toks.mean()
        named_ids[fid] = frozenset(
            d.metadata["entity_id"] for d in docs
            if d.metadata["entity_type"] in ("owl:Class", "owl:ObjectProperty",
                                             "owl:DatatypeProperty"))

    for fid, ids in named_ids.items():
        check("method L144", f"{fid} named entities exposed", len(ids), 155, tol=0)
    check("method L175", "named entity sets identical across formats",
          len(set(named_ids.values())), 1, tol=0)
    check("tab:corpus caption", "mean chunk length span ratio",
          max(means.values()) / min(means.values()), 1.7, tol=0.05)

    # fig:seven-formats-b caption quotes the chunk the seven panels print, which
    # is lis:PhysicalArtefact as each chunker emits it.
    panel_tokens = {"turtle": 216, "elot-org": 169, "elot-org-ancestors": 175,
                    "omn": 191, "jsonld": 217, "yaml-ld": 194, "ofn": 224}
    for fid, want in panel_tokens.items():
        docs = load_chunks(fid)
        got = [d.metadata["token_count"] for d in docs
               if d.metadata["entity_id"] == "lis:PhysicalArtefact"]
        check("fig:seven-formats-b caption", f"{fid} panel chunk tokens",
              got[0] if len(got) == 1 else -1, want, tol=0)


# --------------------------------------------- 3.3 the benchmark instrument
def check_benchmark(tasks):
    section("3.3 Benchmark instrument (method.tex L213-L262, L409-L462)")
    check("method L16", "benchmark items", len(tasks), 60, tol=0)
    check("method L213", "first item id", int(tasks.task_id.min()[1:]), 6, tol=0)
    check("method L213", "last item id", int(tasks.task_id.max()[1:]), 65, tol=0)
    check("method L213", "distinct item ids", tasks.task_id.nunique(), 60, tol=0)
    for kind, want in [("verification", 30), ("slot_filling", 30)]:
        check("method L213", f"{kind} items", (tasks.task_type == kind).sum(), want,
              tol=0)

    labels = tasks.gold_label.value_counts()
    for lab in ["supported", "contradicted", "undetermined"]:
        check("method L216", f"{lab} gold items", labels.get(lab, 0), 10, tol=0)
    check("method L216", "majority-class baseline",
          labels.max() / (tasks.task_type == "verification").sum(), 0.333, tol=0.001)
    check("method L409", "determinate verification items",
          ((tasks.task_type == "verification")
           & (tasks.gold_label != "undetermined")).sum(), 20, tol=0)

    rows = {
        ("verification", "subsumption"): 10,
        ("verification", "bare_disjointness"): 3,
        ("verification", "composed_domain_range_disjointness"): 5,
        ("verification", "functional_property"): 2,
        ("verification", "unasserted_class_relation"): 10,
        ("slot_filling", "direct_relation"): 10,
        ("slot_filling", "part_whole"): 7,
        ("slot_filling", "quality_pattern"): 4,
        ("slot_filling", "quantity_pattern"): 4,
        ("slot_filling", "temporal"): 3,
        ("slot_filling", "participation"): 1,
        ("slot_filling", "modelling_pattern"): 1,
    }
    grouped = tasks.groupby(["task_type", "mechanism"]).size()
    for key, want in rows.items():
        check("tab:benchmark", f"{key[0]} {key[1]}", grouped.get(key, 0), want, tol=0)
    check("tab:benchmark", "total items", sum(rows.values()), 60, tol=0)

    for src, want in [("label", 29), ("paraphrase", 19), ("example", 7),
                      ("definition", 5)]:
        check("method L254", f"query_source {src}",
              (tasks.query_source == src).sum(), want, tol=0)

    # fig:m3-scoring caption: ten items score on a five-field shape and ten on a
    # six-field shape, so a field is worth 0.200 or 0.167.
    check("fig:m3-scoring", "five-field weight", 1 / 5, 0.200, tol=0.001)
    check("fig:m3-scoring", "six-field weight", 1 / 6, 0.167, tol=0.001)


# -------------------------------- the annotation prose screen (4.7 and 5.3)
def check_prose_screen():
    section("Annotation prose screen (results.tex L582, discussion.tex L137)")
    data = json.loads(AUTHORING_MEASUREMENTS.read_text(encoding="utf-8"))
    tiers = dict(data["tiers"])
    tiers["bare_disjointness"] = data["bare_disjointness_prose_screen"]
    check("results L582", "mechanism tiers screened", len(tiers), 6, tol=0)
    check("results L582", "sampled candidates",
          sum(t["sampled"] for t in tiers.values()), 97, tol=0)
    check("results L582", "candidates screened neutral",
          sum(t["prose_screens"]["neutral"] for t in tiers.values()), 96, tol=0)
    check("results L582", "candidates whose prose states the axiom",
          sum(t["prose_screens"]["states_axiom"] for t in tiers.values()), 1, tol=0)
    for direction in ["toward", "away"]:
        check("results L582", f"candidates screened {direction}",
              sum(t["prose_screens"][direction] for t in tiers.values()), 0, tol=0)


# ---------------------------------------- run cost and the generation cap
def check_cost(raw):
    section("Run cost and generation cap (results.tex L30-L34, method.tex L371-L383)")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from experiment.pricing import (PRICING_SNAPSHOT_DATE, compute_cost,
                                    compute_cost_cache_aware)

    check("method L383", "pricing snapshot pinned at 7 June 2026",
          1 if PRICING_SNAPSHOT_DATE == "2026-06-07" else 0, 1, tol=0)

    returned = raw.model_returned.fillna("").astype(str)
    returned = returned.where(returned.str.len() > 0, raw.model.astype(str))
    uncached = np.array([compute_cost(m, p, c) for m, p, c in
                         zip(returned, raw.prompt_tokens, raw.completion_tokens)])
    cached = np.array([compute_cost_cache_aware(m, p, c, k) for m, p, c, k in
                       zip(returned, raw.prompt_tokens, raw.completion_tokens,
                           raw.cached_prompt_tokens.fillna(0))])
    check("results L30", "run cost, every input token at full price",
          uncached.sum(), 50.71, tol=0.005)
    check("results L32", "run cost with prompt caching credited", cached.sum(),
          29.31, tol=0.005)
    per_arm = pd.Series(uncached).groupby(raw.model.values).sum()
    for mid, want in [("claude-sonnet-4-5-20250929", 33.08),
                      ("gpt-4o-2024-11-20", 16.65),
                      ("gpt-4o-mini-2024-07-18", 0.98),
                      ("llama3.1:8b-instruct-q8_0", 0.00)]:
        check("results L33", f"cost {ARMS[mid]}", per_arm.get(mid), want, tol=0.005)

    # The generation cap is 1,024 tokens. It fired twice, both times on a runaway
    # that was recorded as a parse failure, and 477 is the longest completion in
    # any post-retrieval run once those two rows are set aside.
    capped = raw[raw.completion_tokens >= 1024]
    check("method L376", "rows that hit the generation cap", len(capped), 2, tol=0)
    check("method L376", "capped rows that parsed",
          capped.parse_ok.astype(bool).sum(), 0, tol=0)
    # Recursive so the archived pilots under results/superseded/ still count:
    # the chapter's claim is over every post-retrieval run ever made.
    longest = 0
    for path in sorted((ROOT / "experiment" / "results")
                       .glob("**/postretrieval_raw.csv")):
        under_cap = pd.read_csv(path, usecols=["completion_tokens"])
        under_cap = under_cap[under_cap.completion_tokens < 1024].completion_tokens
        if len(under_cap):
            longest = max(longest, int(under_cap.max()))
    check("method L378", "longest completion in any post-retrieval run", longest, 477,
          tol=0)


# ----------------------------------------- abstract and introduction (ch 1)
def check_front_matter(raw, scored, retrieval):
    section("Abstract and introduction (dissertation.tex L44-L65, "
            "introduction.tex L111-L163)")
    check("intro L112", "graded calls", len(raw), 10080, tol=0)
    check("intro L112", "cells",
          raw.groupby(["task_id", "format", "condition", "model"]).ngroups, 3360,
          tol=0)
    check("intro L113", "ranked lists scored for retrieval", len(retrieval), 420,
          tol=0)
    check("intro L111", "benchmark items", raw.task_id.nunique(), 60, tol=0)
    check("intro L111", "serialisations", raw.format.nunique(), 7, tol=0)
    check("intro L111", "arms", raw.model.nunique(), 4, tol=0)
    check("intro L111", "conditions", raw.condition.nunique(), 2, tol=0)
    check("intro L111", "trials per cell",
          raw.groupby(["task_id", "format", "condition", "model"]).size().max(), 3,
          tol=0)
    check("intro L124", "paired format contrasts over the headline families",
          4 * 21, 84, tol=0)

    ver = raw[raw.task_type == "verification"]
    check("intro L139", "verification items", ver.task_id.nunique(), 30, tol=0)
    check("intro L140", "three-way accuracy over all verification items",
          ver.grade_correct.mean(), 0.556, tol=0.001)
    check("intro L140", "coverage over all verification items",
          ver.grade_answered.mean(), 0.898, tol=0.001)
    check("intro L141", "majority-class baseline", 10 / 30, 0.333, tol=0.001)
    check("intro L142", "graded verification rows", len(ver), 5040, tol=0)
    und = ver[ver.grade_gold_label == "undetermined"]
    check("intro L144", "undetermined-gold rows", len(und), 1680, tol=0)
    check("intro L143", "pct of undetermined-gold rows answered contradicted",
          100 * (und.grade_pred_label == "contradicted").mean(), 90.8, tol=0.05)
    check("intro L144", "undetermined-gold rows answered supported",
          (und.grade_pred_label == "supported").sum(), 0, tol=0)

    # "worth roughly fifteen times the largest gap between formats": the
    # slot-filling context effect against the slot-filling format spread.
    effect = context_effect_by_format(scored)
    sf = raw[raw.task_type == "slot_filling"]
    spread = sf.groupby("format").grade_partial_credit.mean()
    spread = spread.max() - spread.min()
    ratio_lo = effect.min() / spread
    ratio_hi = effect.max() / spread
    check("intro L158", "fifteen lies inside the context/format ratio range",
          1 if ratio_lo <= 15 <= ratio_hi else 0, 1, tol=0)
    check("abstract L59", "context effect over format spread, low end", ratio_lo,
          13.3, tol=0.3)
    check("abstract L59", "context effect over format spread, high end", ratio_hi,
          15.6, tol=0.3)

    check("intro L163", "accuracy ELOT-nested loses on the one-hop pair",
          one_hop_gap(raw), 0.434, tol=0.001)


# ------------------------------------------------------- 5.x discussion
def check_discussion(raw, scored, retrieval, tasks):
    section("Discussion (discussion.tex L18-L274)")
    ver = raw[raw.task_type == "verification"]
    und = ver[ver.grade_gold_label == "undetermined"]
    check("discussion L18", "pct undetermined-gold answered contradicted",
          100 * (und.grade_pred_label == "contradicted").mean(), 90.8, tol=0.05)
    check("discussion L19", "undetermined-gold rows", len(und), 1680, tol=0)
    check("discussion L44", "accuracy on the unasserted-class stratum",
          und.grade_correct.mean(), 0.092, tol=0.001)
    check("discussion L44", "majority-class baseline", 10 / 30, 0.333, tol=0.001)
    sonnet = und[und.model == "claude-sonnet-4-5-20250929"]
    check("discussion L48", "Sonnet contradicted rate on undetermined-gold rows",
          (sonnet.grade_pred_label == "contradicted").mean(), 0.75, tol=0.03)

    narrow = retrieval.groupby("format").recall_at_k.mean()
    check("discussion L66", "recall@5 spread", narrow.max() - narrow.min(), 0.044,
          tol=0.001)

    det = ver[ver.grade_gold_label != "undetermined"]
    cov = det.groupby("format").grade_answered.mean()
    answered = det[det.grade_answered.astype(bool)]
    acc = answered.groupby("format").grade_correct.mean()
    sf = raw[raw.task_type == "slot_filling"]
    partial = sf.groupby("format").grade_partial_credit.mean()
    check("discussion L71", "verification coverage spread", cov.max() - cov.min(),
          0.044, tol=0.001)
    check("discussion L71", "accuracy-on-answered spread", acc.max() - acc.min(),
          0.080, tol=0.001)
    check("discussion L72", "slot-filling partial-credit spread",
          partial.max() - partial.min(), 0.024, tol=0.001)
    check("discussion L103", "cells",
          raw.groupby(["task_id", "format", "condition", "model"]).ngroups, 3360,
          tol=0)
    check("discussion L274", "paired contrasts over the headline families", 4 * 21,
          84, tol=0)

    effect = context_effect_by_format(scored)
    check("discussion L148", "context effect on slot-filling, low end", effect.min(),
          0.320, tol=0.001)
    check("discussion L148", "context effect on slot-filling, high end", effect.max(),
          0.374, tol=0.001)

    # 5.4, answering against citing: the same figures as 4.3, transcribed.
    ans = sf[ANSWER_FIELDS].mean(axis=1)
    cit = sf[CITATION_FIELDS].mean(axis=1)
    sf = sf.assign(_ans=ans, _cit=cit)
    for mid, want in [("llama3.1:8b-instruct-q8_0", 0.807),
                      ("gpt-4o-2024-11-20", 0.844),
                      ("claude-sonnet-4-5-20250929", 0.840)]:
        check("discussion L189", f"answer fields {ARMS[mid]}",
              sf[sf.model == mid]._ans.mean(), want, tol=0.001)
    check("discussion L190", "citation fields Llama",
          sf[sf.model == "llama3.1:8b-instruct-q8_0"]._cit.mean(), 0.266, tol=0.001)
    for cond, want_ans, want_cit in [("oracle", 0.953, 0.789),
                                     ("retrieved", 0.661, 0.346)]:
        s = sf[sf.condition == cond]
        check("discussion L191", f"answer fields under {cond}", s._ans.mean(),
              want_ans, tol=0.001)
        check("discussion L192", f"citation fields under {cond}", s._cit.mean(),
              want_cit, tol=0.001)

    si = sf[sf.grade_support_intermediate_correct.notna()]
    per_item = (si.groupby(["task_id", "condition"])
                  .grade_support_intermediate_correct.mean().unstack("condition"))
    check("discussion L199", "support_intermediate oracle minus retrieved",
          (per_item["oracle"] - per_item["retrieved"]).mean(), -0.120, tol=0.002)
    check("discussion L200", "support_intermediate graded items",
          si.task_id.nunique(), 10, tol=0)

    check("discussion L171", "accuracy ELOT-nested loses on the one-hop pair",
          one_hop_gap(raw), 0.434, tol=0.001)
    check("discussion L175", "ELOT-nested cost to GPT-4o on the one-hop pair",
          one_hop_gap(raw, "gpt-4o-2024-11-20"), 0.750, tol=0.001)

    if CONTRASTS.exists():
        con = pd.read_csv(CONTRASTS)
        aoa = con[con.metric == "acc_on_answered"]
        check("discussion L97", "contrasts surviving Holm",
              int((aoa.p_holm < 0.05).sum()), 3, tol=0)
        row = aoa[(aoa.a == "omn") & (aoa.b == "yaml-ld")]
        if len(row):
            check("discussion L97", "OMN over YAML-LD", float(row.delta.iloc[0]),
                  0.074, tol=0.001)
        else:
            row = aoa[(aoa.a == "yaml-ld") & (aoa.b == "omn")]
            check("discussion L97", "OMN over YAML-LD", -float(row.delta.iloc[0]),
                  0.074, tol=0.001)

    # 5.7 names the paraphrase row of tab:query-source as the unresolved signal.
    para_items = set(tasks.loc[tasks.query_source == "paraphrase", "task_id"])
    para = retrieval[retrieval.task_id.isin(para_items)]
    by_fmt = para.groupby("format").recall_at_k.mean()
    check("discussion L246", "spread on the paraphrase-worded queries",
          by_fmt.max() - by_fmt.min(), 0.105, tol=0.001)

    # 5.5 limitations: the duplicate-shape groups behind "eleven effective items"
    for members, want in [(("T40", "T41", "T55", "T56"), 0.807),
                          (("T42", "T43", "T57", "T58"), 0.944)]:
        item = (scored[scored.task_type == "slot_filling"]
                .groupby(["task_id", "format", "condition", "model"])
                .mean_partial_credit_mean.mean().unstack("task_id"))[list(members)]
        corr = item.corr()
        vals = [corr.iloc[i, j] for i in range(len(members))
                for j in range(i + 1, len(members))]
        check("discussion L219", f"mean pairwise r {'/'.join(members)}",
              float(np.mean(vals)), want, tol=0.005)


# ------------------------------ 4.7 retrieval failure mechanism denominators
def check_retrieval_slots(retrieval):
    section("4.7 Retrieval failure mechanisms (results.tex L541-L548)")
    def split(value):
        return [c for c in str(value).split(";") if c]

    retrieved = retrieval.retrieved_ids.map(split)
    gold = retrieval.retrieval_gold_chunks.map(split)
    check("results L546", "retrieved slots over the 420 lists",
          sum(len(r) for r in retrieved), 2100, tol=0)
    check("results L546", "non-gold retrieved slots",
          sum(len([c for c in r if c not in set(g)])
              for r, g in zip(retrieved, gold)), 1471, tol=0)


# ------------------------------------ tab:retrieval-mechanisms, mechanism 1
def check_crowding(retrieval):
    """Property-chunk crowding, defined as in docs/findings/60task-analysis.md:
    on the class-pair items, count non-gold property chunks holding a top-5 slot,
    and count items where a gold class chunk is missed while such a chunk is there.
    """
    section("4.7 Property-chunk crowding (results.tex L544, tab:retrieval-mechanisms)")
    prop_types = ("owl:ObjectProperty", "owl:DatatypeProperty")
    types = {}
    for fid in FMT_IDS:
        types[fid] = {d.metadata["entity_id"]: d.metadata["entity_type"]
                      for d in load_chunks(fid)}

    def split(value):
        return [c for c in str(value).split(";") if c]

    # Class-pair items: every narrow gold chunk is an owl:Class and there are at
    # least two of them. The format does not matter for this selection.
    one = retrieval[retrieval.format == "turtle"]
    class_pair = [r.task_id for _, r in one.iterrows()
                  if len(split(r.retrieval_gold_chunks)) >= 2
                  and all(types["turtle"].get(g) == "owl:Class"
                          for g in split(r.retrieval_gold_chunks))]
    check("results L544", "class-pair items", len(class_pair), 23, tol=0)
    check("results L544", "class-pair items are all verification",
          int(set(one[one.task_id.isin(class_pair)].task_type) == {"verification"}),
          1, tol=0)

    means, rates = {}, {}
    for fid in FMT_IDS:
        sub = retrieval[(retrieval.format == fid)
                        & retrieval.task_id.isin(class_pair)]
        counts, crowded = [], 0
        for _, r in sub.iterrows():
            gold = set(split(r.retrieval_gold_chunks))
            got = split(r.retrieved_ids)
            props = [c for c in got
                     if c not in gold and types[fid].get(c) in prop_types]
            counts.append(len(props))
            if props and not gold.issubset(set(got)):
                crowded += 1
        means[fid] = sum(counts) / len(counts)
        rates[fid] = crowded / len(sub)

    check("tab:retrieval-mechanisms", "non-gold property chunks in top-5, min",
          min(means.values()), 1.043, tol=0.001)
    check("tab:retrieval-mechanisms", "non-gold property chunks in top-5, max",
          max(means.values()), 1.696, tol=0.001)
    check("tab:retrieval-mechanisms", "gold class chunk displaced, min rate",
          min(rates.values()), 0.174, tol=0.001)
    check("tab:retrieval-mechanisms", "gold class chunk displaced, max rate",
          max(rates.values()), 0.348, tol=0.001)
    check("results L545", "crowding range printed in prose, low", min(means.values()),
          1.04, tol=0.005)
    check("results L545", "crowding range printed in prose, high",
          max(means.values()), 1.70, tol=0.005)


# ------------------------------------ tab:retrieval-mechanisms, mechanism 2
def check_example_mismatch(retrieval):
    """The skos:example lexical-mismatch cells.

    Attribution needs the exact content-word rule the original analysis used, and
    that rule lives only in docs/findings/60task-analysis.md, so these cells are
    pinned to that frozen note rather than recomputed. The denominators the note
    divides by are recomputed, so a wrong denominator would still surface.
    """
    section("4.7 Example-driven mismatch (results.tex L546, "
            "tab:retrieval-mechanisms)")
    note = (REPO / "docs" / "findings" / "60task-analysis.md").read_text(
        encoding="utf-8")
    rows = {}
    for line in note.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0] in FMT_IDS:
            try:
                rows[cells[0]] = [float(c) for c in cells[1:]]
            except ValueError:
                continue
    check("60task-analysis", "formats in the example-mismatch table", len(rows), 7,
          tol=0)

    nongold = [r[0] for r in rows.values()]
    attributable = [r[1] for r in rows.values()]
    overall = [r[2] for r in rows.values()]
    slot = [r[3] for r in rows.values()]
    verif = [r[4] for r in rows.values()]

    check("results L546", "non-gold slots summed over the seven formats",
          sum(nongold), 1471, tol=0)
    check("results L546", "example-attributable slots", sum(attributable), 330,
          tol=0)
    check("results L546", "example-attributable share",
          sum(attributable) / sum(nongold), 0.224, tol=0.001)
    check("tab:retrieval-mechanisms", "example-attributable rate, min", min(overall),
          0.204, tol=0.001)
    check("tab:retrieval-mechanisms", "example-attributable rate, max", max(overall),
          0.251, tol=0.001)
    check("tab:retrieval-mechanisms", "slot-filling rate, min", min(slot), 0.325,
          tol=0.001)
    check("tab:retrieval-mechanisms", "slot-filling rate, max", max(slot), 0.410,
          tol=0.001)
    check("tab:retrieval-mechanisms", "verification rate, min", min(verif), 0.023,
          tol=0.001)
    check("tab:retrieval-mechanisms", "verification rate, max", max(verif), 0.046,
          tol=0.001)

    # The affected-item count the prose quotes, read back out of the note.
    hit = re.search(r'affecting[^0-9]*([0-9]+) of 60 items', note)
    check("results L546", "items showing example-driven mismatch",
          int(hit.group(1)) if hit else -1, 28, tol=0)


# ------------------------------------------- Appendix B, the instrument
def check_appendix_b(tasks):
    section("Appendix B, instrument and run settings (appendix-b-instrument.tex)")
    documented = {"direct_assertion": 20, "structural": 21, "modelling_pattern": 10,
                  "definitional": 9}
    counts = tasks.reasoning_type.value_counts()
    for kind, want in documented.items():
        check("appendix B L80", f"reasoning_type {kind}", counts.get(kind, 0), want,
              tol=0)
    check("appendix B L80", "reasoning_type values", counts.size, 4, tol=0)
    check("appendix B L80", "items covered by reasoning_type", counts.sum(), 60,
          tol=0)

    # "byte-identical raw output in only 2 of 12 cells" on the baseline arm
    probe = pd.read_csv(DETERMINISM_PATH)
    base = probe[probe.model == "gpt-4o-2024-11-20"]
    cells = base.groupby(["task_id", "format", "condition"]).raw_response.nunique()
    check("appendix B L108", "determinism probe cells on the baseline arm",
          len(cells), 12, tol=0)
    check("appendix B L108", "cells reproducing byte-identical output",
          int((cells == 1).sum()), 2, tol=0)

    # the index-reading checks come last: they skip without the licensed ontology
    check("appendix B L33", "named entities exposed by every chunker",
          len({frozenset(d.metadata["entity_id"] for d in load_chunks(fid)
                         if d.metadata["entity_type"] in
                         ("owl:Class", "owl:ObjectProperty", "owl:DatatypeProperty"))
               for fid in FMT_IDS}), 1, tol=0)
    surplus = {len(load_chunks(fid)) for fid in FMT_IDS}
    check("appendix B L62", "retrievable chunk counts across formats",
          len(surplus), 2, tol=0)
    check("appendix B L62", "smaller retrievable chunk count", min(surplus), 156,
          tol=0)
    check("appendix B L62", "larger retrievable chunk count", max(surplus), 158,
          tol=0)

def check_outside_factorial():
    """Results 4.8 'Two conditions outside the factorial' (results.tex L654-L697)
    and the appendix D/E tables that carry the detail."""
    section("4.8 Two conditions outside the factorial + appendices D and E")

    pilot = pd.read_csv(PILOT_COMBINED / "postretrieval_raw.csv", low_memory=False)
    wc = pd.read_csv(WHOLE_CONTEXT / "postretrieval_raw.csv", low_memory=False)
    pilot_ret = pd.read_csv(PILOT_RETRIEVAL, low_memory=False)

    # --- schema-concept pilot design (results L666-L667)
    check("results L666", "pilot raw rows", len(pilot), 720, tol=0)
    check("results L666", "pilot corpus conditions", pilot.format.nunique(), 8, tol=0)
    check("results L666", "pilot arms", pilot.model.nunique(), 3, tol=0)
    check("results L667", "pilot context conditions", pilot.condition.nunique(), 2,
          tol=0)
    check("results L666", "pilot items", pilot.task_id.nunique(), 5, tol=0)
    pilot_cells = pilot.groupby(["task_id", "format", "condition", "model"]).size()
    check("results L667", "pilot trials per cell", pilot_cells.max(), 3, tol=0)

    # --- verification with schema-concept included (results L667-L668):
    # per (task, model, condition) cell, schema-concept never scores below Turtle
    ver = pilot[pilot.task_type == "verification"]
    piv = (ver.groupby(["task_id", "model", "condition", "format"])
              .grade_correct.mean().unstack("format"))
    check("results L668", "verification cells", len(piv), 18, tol=0)
    check("results L668", "verification cells schema-concept below Turtle",
          int((piv["schema-concept"] < piv["turtle"]).sum()), 0, tol=0)

    # --- schema-concept retrieval ordering (results L668-L670, tab D)
    ret = pilot_ret[pilot_ret.task_type == "ALL"].set_index("format")
    check("results L669", "schema-concept MRR", ret.loc["schema-concept", "mrr"],
          1.000)
    check("results L669", "schema-concept nDCG@5",
          ret.loc["schema-concept", "ndcg_at_k"], 0.828)
    check("results L669", "schema-concept MRR is best",
          ret.mrr.idxmax() == "schema-concept", 1, tol=0)
    check("results L669", "schema-concept nDCG@5 is best",
          ret.ndcg_at_k.idxmax() == "schema-concept", 1, tol=0)
    check("results L670", "schema-concept recall@5",
          ret.loc["schema-concept", "recall_at_k"], 0.800)
    verbatim = ret.drop("schema-concept")
    check("results L670", "best verbatim recall@5", verbatim.recall_at_k.max(),
          0.933)

    # --- tab:schema-concept-pilot (appendix D)
    pilot_sf = pilot[(pilot.task_type == "slot_filling")
                     & (pilot.condition == "oracle")]
    oracle_pc = pilot_sf.groupby("format").grade_partial_credit.mean()
    tab_d = {
        "turtle": (0.867, 0.767, 0.793, 0.694),
        "omn": (0.867, 0.900, 0.820, 0.719),
        "ofn": (0.933, 0.767, 0.795, 0.572),
        "jsonld": (0.800, 0.800, 0.714, 0.728),
        "yaml-ld": (0.867, 0.750, 0.753, 0.743),
        "elot-org": (0.700, 0.617, 0.599, 0.656),
        "elot-org-ancestors": (0.633, 0.800, 0.641, 0.620),
        "schema-concept": (0.800, 1.000, 0.828, 0.644),
    }
    for fid, (r, m, d, pc) in tab_d.items():
        check("tab:schema-concept-pilot", f"{fid} recall@5",
              ret.loc[fid, "recall_at_k"], r)
        check("tab:schema-concept-pilot", f"{fid} MRR", ret.loc[fid, "mrr"], m)
        check("tab:schema-concept-pilot", f"{fid} nDCG@5",
              ret.loc[fid, "ndcg_at_k"], d)
        check("tab:schema-concept-pilot", f"{fid} oracle slot-filling",
              oracle_pc[fid], pc)
    # schema-concept sits below the strongest verbatim formats under oracle
    check("results L671", "schema-concept oracle slot-filling below best verbatim",
          int(oracle_pc["schema-concept"] < oracle_pc.drop("schema-concept").max()),
          1, tol=0)

    # --- whole-context design (results L682-L683, appendix E)
    check("results L683", "whole-context calls", len(wc), 126, tol=0)
    check("results L682", "whole-context formats", wc.format.nunique(), 7, tol=0)
    check("results L683", "whole-context arms", wc.model.nunique(), 3, tol=0)
    check("results L682", "whole-context items", wc.task_id.nunique(), 2, tol=0)
    wc_cells = wc.groupby(["task_id", "format", "model"]).size()
    check("results L683", "whole-context trials per cell", wc_cells.max(), 3, tol=0)
    manifest = json.loads((WHOLE_CONTEXT / "manifest.json").read_text())
    check("appendix E L9", "whole-context pinned cost USD",
          manifest["cost_summary"]["cost_usd_at_pricing_date"], 4.71, tol=0.005)

    # --- T02 decomposition (results L684-L687, tab:whole-context-t02)
    core = pilot[(pilot.task_id == "T02") & (pilot.format != "schema-concept")]
    t02_wc = wc[wc.task_id == "T02"]
    t02_answer = {c: g[ANSWER_FIELDS].mean().mean()
                  for c, g in core.groupby("condition")}
    t02_cit_fields = ["grade_support_class_correct",
                      "grade_support_property_correct"]
    t02_cit = {c: g[t02_cit_fields].mean().mean()
               for c, g in core.groupby("condition")}
    t02_answer["whole_context"] = t02_wc[ANSWER_FIELDS].mean().mean()
    t02_cit["whole_context"] = t02_wc[t02_cit_fields].mean().mean()
    documented = {"oracle": (0.683, 0.704, 0.651),
                  "retrieved": (0.524, 0.646, 0.341),
                  "whole_context": (0.486, 0.646, 0.246)}
    for cond, (comb, ans, cit) in documented.items():
        check("tab:whole-context-t02", f"T02 {cond} answer fields",
              t02_answer[cond], ans)
        check("tab:whole-context-t02", f"T02 {cond} citation fields",
              t02_cit[cond], cit)
        check("tab:whole-context-t02", f"T02 {cond} combined",
              (3 * t02_answer[cond] + 2 * t02_cit[cond]) / 5, comb)

    # --- OFN answer-field deltas retrieved -> whole-context (results L690-L692)
    ret_t02 = core[core.condition == "retrieved"]
    deltas = {}
    for fid in wc.format.unique():
        deltas[fid] = [
            t02_wc[(t02_wc.format == fid) & (t02_wc.model == m)]
            [ANSWER_FIELDS].mean().mean()
            - ret_t02[(ret_t02.format == fid) & (ret_t02.model == m)]
            [ANSWER_FIELDS].mean().mean()
            for m in sorted(wc.model.unique())]
    for got, want, m in zip(deltas["ofn"], (0.222, 0.222, 0.667),
                            sorted(wc.model.unique())):
        check("results L691", f"OFN answer delta {ARMS[m]}", got, want)
    check("results L690", "formats improving on answer fields for all three arms",
          sum(all(d > 0 for d in ds) for ds in deltas.values()), 1, tol=0)
    check("appendix E L21", "OFN retrieved answer-field mean",
          ret_t02[ret_t02.format == "ofn"][ANSWER_FIELDS].mean().mean(), 0.296)


def run(fn, *args):
    """Run one section, recording a crash as a failure instead of aborting."""
    try:
        fn(*args)
    except NeedsOntology as exc:
        SKIPS.append(f"{fn.__name__}: needs the licensed ontology, {exc}")
        print(f"  -- {fn.__name__} skipped: needs the licensed ontology, {exc}")
    except Exception as exc:  # noqa: BLE001 - a crash here is a finding, not a bug
        FAILURES.append(f"{fn.__name__} crashed: {type(exc).__name__}: {exc}")
        print(f"  !! {fn.__name__} crashed: {type(exc).__name__}: {exc}")


def main():
    raw, scored, retrieval, tasks = load()
    run(check_corpus)
    run(check_benchmark, tasks)
    run(check_integrity, raw, scored)
    run(check_cost, raw)
    run(check_collapse, raw)
    run(check_citation, raw)
    run(check_retrieval, retrieval, raw)
    run(check_format_effects, raw, scored, retrieval)
    run(check_mechanisms, raw, retrieval)
    run(check_local_effect, raw)
    run(check_outside_factorial)
    run(check_retrieval_slots, retrieval)
    run(check_crowding, retrieval)
    run(check_example_mismatch, retrieval)
    run(check_prose_screen)
    run(check_front_matter, raw, scored, retrieval)
    run(check_discussion, raw, scored, retrieval, tasks)
    run(check_appendix_b, tasks)

    print(f"\n{'=' * 70}")
    print(f"{PASSES} checks passed, {len(FAILURES)} mismatches")
    if SKIPS:
        print(f"{len(SKIPS)} check groups skipped because they need the licensed ontology:")
        for s in SKIPS:
            print(f"  SKIPPED   {s}")
    if FAILURES:
        print(f"{'=' * 70}")
        for f in FAILURES:
            print(f"  MISMATCH  {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
