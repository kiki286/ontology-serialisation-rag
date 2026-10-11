"""Generate the six results-chapter figures from the frozen run outputs.

Recreates (and supersedes) the previously uncommitted plotting code behind
figures/fig1..fig6 in the Overleaf repo. Every number is computed from
`experiment/results/postretrieval-combined-15-18/` and
`experiment/results/retrieval-trial-14/`, then checked against the values
frozen in `docs/findings/60task-analysis.md`; the script fails loudly on any
mismatch rather than drawing a figure that disagrees with the text.

Changes from the original figures, per the 2026-09-02 figure review:
- "smallest detectable difference" is renamed "resolution threshold" everywhere
  (the chapter's committed term; methods ch. 3 disavows SDD as a power term).
- Embedded bottom captions are dropped: the LaTeX \\caption owns that text.
- Serif/STIX fonts to match the Computer Modern body text.
- fig2 gains a second panel showing per-format oracle-minus-retrieved deltas
  with 95% bootstrap intervals over items, and the legend no longer collides
  with the annotation.
- fig4's axis label no longer collides with a footnote; tick labels horizontal.
- fig5 gains a by-condition panel and paints Llama's citation bar red, so
  red = the broken thing across all figures.
- fig6's baseline is labelled with its value and no longer sits on the axis;
  its title no longer claims a format comparison the panel does not show.
- No em dashes in any figure text.

Restyled 2026-09-03 to match the register of the group's past theses: quiet
sans-serif data charts with no in-figure claim titles (the LaTeX caption owns
the claim), lettered panels, boxed legends, and a muted teal palette shared
with the methods-chapter diagrams (make_methods_figures.py). Red still marks
the broken thing, and every plotted number is still asserted.

With --slide the script writes <name>_slide.pdf versions for the seminar
deck instead. Each is drawn at the width the deck places it on the 16:9
beamer frame (seminar.tex: \\textwidth = 435pt), so tick and label text lands
at 9-10pt instead of about 4pt, and keeps the thesis versions' palette, line
weights and marker sizes in points. Slide versions use the dissertation's
wording: "serialisation" for "format" (including "serialisation spread"),
"gold" for "oracle" (including "gold label" for "correct answer"), and
"arm" for the model factor, as the dissertation's figures and tables do. The
same assertions run.

Usage (from src/rag/):
    python -m scripts.make_thesis_figures --out <figures-dir> [--slide]
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from matplotlib.patches import Patch, Rectangle
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCORED = ROOT / "experiment" / "results" / "postretrieval-combined-15-18" / "postretrieval_scored.csv"
RAW = ROOT / "experiment" / "results" / "postretrieval-combined-15-18" / "postretrieval_raw.csv"
RETRIEVAL = ROOT / "experiment" / "results" / "retrieval-trial-14" / "retrieval_raw.csv"

SEED = 20260529  # experiment.config.SEED
B = 10_000

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
FMT_NAMES = [n for _, n in FORMATS]

ARMS = [
    ("claude-sonnet-4-5-20250929", "Sonnet 4.5"),
    ("gpt-4o-2024-11-20", "GPT-4o"),
    ("gpt-4o-mini-2024-07-18", "GPT-4o-mini"),
    ("llama3.1:8b-instruct-q8_0", "Llama 3.1 8B"),
]

BLUE = "#00796B"
BLUE_SOFT = "#7FBFB6"
BAND = "#DFECEA"
RED = "#8E24AA"
RED_SOFT = "#CE93D8"
GREY = "#555555"

ONE_HOP = ["T09", "T10"]
MULTI_HOP = ["T11", "T12", "T13", "T14", "T15", "T16", "T17", "T18"]

ANSWER_FIELDS = ["grade_class_correct", "grade_property_correct", "grade_intermediate_correct"]
CITATION_FIELDS = ["grade_support_class_correct", "grade_support_property_correct",
                   "grade_support_intermediate_correct"]


def style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 11,
        "axes.labelsize": 10.5,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9.5,
        "legend.edgecolor": "#AAAAAA",
        "legend.framealpha": 1.0,
    })


def slide_style():
    """Slide sizes in points, for figures placed on the deck at 1:1."""
    plt.rcParams.update({
        "axes.titlesize": 10,
        "axes.labelsize": 10,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 9,
    })


def slide_fig(width_pt, height_pt, **kw):
    """A figure exactly as large as its place on the slide."""
    fig, axes = plt.subplots(figsize=(width_pt / 72, height_pt / 72),
                             layout="constrained", **kw)
    fig.get_layout_engine().set(w_pad=2 / 72, h_pad=2 / 72)
    return fig, axes


def slide_save(fig, out, name):
    fig.savefig(out / f"{name}_slide.pdf")  # no tight bbox: keep the exact size
    plt.close(fig)


def check(name, got, want, tol=0.001):
    if abs(got - want) > tol:
        raise SystemExit(f"MISMATCH {name}: computed {got:.4f}, documented {want:.4f}")
    print(f"  ok {name}: {got:.4f} (documented {want:.3f})")


def fmt_marginals(scored, task_type, col):
    sub = scored[scored.task_type == task_type]
    return sub.groupby("format")[col].mean().reindex(FMT_IDS)


# ---------------------------------------------------------------- fig 1
def fig1(scored, raw, retrieval, out, slide=False):
    rec = retrieval.groupby("format").recall_at_k.mean().reindex(FMT_IDS)
    det = raw[(raw.task_type == "verification")
              & (raw.grade_gold_label != "undetermined")]
    ver = (det.groupby("format").grade_selective_correct.sum()
           / det.groupby("format").grade_answered.sum()).reindex(FMT_IDS)
    slt = fmt_marginals(scored, "slot_filling", "mean_partial_credit_mean")

    check("fig1 recall spread", rec.max() - rec.min(), 0.044)
    check("fig1 verification acc-on-answered spread", ver.max() - ver.min(), 0.080)
    check("fig1 slot-filling spread", slt.max() - slt.min(), 0.024)
    if slide:
        return fig1_slide(rec, ver, slt, out)

    # minimum effect of interest: one item's worth on each marginal scale
    panels = [
        (rec, "(A) Retrieval: recall@5\nHolm 0/21", 0.0083,
         "one item, one chunk\n(0.003-0.008)"),
        (ver, "(B) Verification: accuracy on answered\nHolm 3/21, one at or above one item",
         0.050, "one item's worth (0.050)"),
        (slt, "(C) Slot-filling: partial credit\nHolm 0/21", 0.0067,
         "one field, one item (0.007)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 4.2))
    y = np.arange(len(FMT_IDS))[::-1]
    for i, (ax, (vals, title, mei, mei_label)) in enumerate(zip(axes, panels)):
        lo, hi = vals.min(), vals.max()
        ax.axvspan(lo, hi, color=BAND, zorder=0)
        ax.scatter(vals.values, y, s=110, color=BLUE, zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels(FMT_NAMES)
        ax.set_title(f"{title}\nformat spread = {hi - lo:.3f}", fontsize=9.5)
        # grey MEI marker, drawn to the data scale
        ax.plot([lo, lo + mei], [-1.0, -1.0], color=GREY, lw=3,
                solid_capstyle="butt", zorder=3)
        ax.text(lo, -1.55, mei_label, color=GREY, ha="left", va="top",
                fontsize=8.5)
        ax.grid(axis="x", color="#eeeeee", zorder=0)
        ax.set_ylim(-2.6, len(FMT_IDS) - 0.4)
        pad = (hi - lo) * 0.55
        ax.set_xlim(lo - pad, hi + pad)
    # panel B: bracket the one contrast that passes both reporting gates
    axB = axes[1]
    x_omn, x_yaml = ver["omn"], ver["yaml-ld"]
    y_omn = y[FMT_IDS.index("omn")]
    y_yaml = y[FMT_IDS.index("yaml-ld")]
    xb = max(x_omn, x_yaml) + (ver.max() - ver.min()) * 0.28
    axB.plot([x_omn + 0.004, xb], [y_omn, y_omn], color=GREY, lw=1.0)
    axB.plot([x_yaml + 0.004, xb], [y_yaml, y_yaml], color=GREY, lw=1.0)
    axB.plot([xb, xb], [y_yaml, y_omn], color=GREY, lw=1.0)
    axB.text(xb + 0.004, (y_omn + y_yaml) / 2, "+0.074\n(both gates)",
             fontsize=8.5, color=GREY, va="center", ha="left")
    fig.tight_layout()
    fig.savefig(out / "fig1_format_null.pdf", bbox_inches="tight")
    plt.close(fig)


def fig1_slide(rec, ver, slt, out):
    """Slide 9, 0.92 of the frame width. One shared serialisation axis."""
    panels = [
        (rec, "(A) Retrieval\nrecall@5", "Holm 0/21", 0.0083,
         "one item, one chunk\n(0.003-0.008)"),
        (ver, "(B) Verification\naccuracy on answered", "Holm 3/21", 0.050,
         "one item's worth\n(0.050)"),
        (slt, "(C) Slot-filling\npartial credit", "Holm 0/21", 0.0067,
         "one field,\none item (0.007)"),
    ]
    fig, axes = slide_fig(400, 195, ncols=3, sharey=True,
                          gridspec_kw={"width_ratios": [1.0, 1.3, 1.0]})
    y = np.arange(len(FMT_IDS))[::-1]
    for ax, (vals, title, holm, mei, mei_label) in zip(axes, panels):
        lo, hi = vals.min(), vals.max()
        ax.axvspan(lo, hi, color=BAND, zorder=0)
        ax.scatter(vals.values, y, s=70, color=BLUE, zorder=3)
        ax.set_title(f"{title}\nserialisation spread\n{hi - lo:.3f}, {holm}")
        ax.plot([lo, lo + mei], [-1.0, -1.0], color=GREY, lw=3,
                solid_capstyle="butt", zorder=3)
        ax.text(lo, -1.5, mei_label, color=GREY, ha="left", va="top",
                fontsize=9)
        ax.grid(axis="x", color="#eeeeee", zorder=0)
        pad = (hi - lo) * 0.55
        ax.set_xlim(lo - pad, hi + pad)
        ax.xaxis.set_major_locator(MaxNLocator(3))
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(FMT_NAMES)
    axes[0].set_ylim(-3.1, len(FMT_IDS) - 0.4)
    # panel B: bracket the one contrast that passes both reporting gates
    axB = axes[1]
    x_omn, x_yaml = ver["omn"], ver["yaml-ld"]
    y_omn = y[FMT_IDS.index("omn")]
    y_yaml = y[FMT_IDS.index("yaml-ld")]
    spread = ver.max() - ver.min()
    xb = max(x_omn, x_yaml) + spread * 0.28
    axB.plot([x_omn + 0.004, xb], [y_omn, y_omn], color=GREY, lw=1.0)
    axB.plot([x_yaml + 0.004, xb], [y_yaml, y_yaml], color=GREY, lw=1.0)
    axB.plot([xb, xb], [y_yaml, y_omn], color=GREY, lw=1.0)
    axB.text(xb + 0.004, (y_omn + y_yaml) / 2, "+0.074\n(both gates)",
             fontsize=9, color=GREY, va="center", ha="left")
    axB.set_xlim(ver.min() - spread * 0.55, xb + spread * 0.85)
    slide_save(fig, out, "fig1_format_null")


# ---------------------------------------------------------------- fig 2
def fig2(scored, out, slide=False):
    sf = scored[scored.task_type == "slot_filling"]
    item = (sf.groupby(["task_id", "format", "condition"]).mean_partial_credit_mean
              .mean().unstack("condition"))
    per_fmt = item.groupby(level="format").mean().reindex(FMT_IDS)
    deltas = (item["oracle"] - item["retrieved"]).unstack("format")[FMT_IDS]  # 30 x 7

    point = deltas.mean()
    check("fig2 min context effect", point.min(), 0.320, tol=0.002)
    check("fig2 max context effect", point.max(), 0.374, tol=0.002)

    n = len(deltas)
    idx = deltas.index.to_numpy()
    boots = np.empty((B, len(FMT_IDS)))
    for b in range(B):
        rng = np.random.RandomState(SEED + b)
        sample = deltas.loc[rng.choice(idx, size=n, replace=True)]
        boots[b] = sample.mean().values
    lo_ci = np.percentile(boots, 2.5, axis=0)
    hi_ci = np.percentile(boots, 97.5, axis=0)
    assert (lo_ci > 0).all(), "an oracle-retrieved interval includes zero"
    if slide:
        return fig2_slide(per_fmt, point, lo_ci, hi_ci, out)

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(9.6, 4.2),
                                   gridspec_kw={"width_ratios": [1.5, 1.0]})
    y = np.arange(len(FMT_IDS))[::-1]
    for yi, fid in zip(y, FMT_IDS):
        r, o = per_fmt.loc[fid, "retrieved"], per_fmt.loc[fid, "oracle"]
        axL.plot([r, o], [yi, yi], color="#9DBBB6", lw=2.5, zorder=2)
        axL.scatter([r], [yi], s=110, color=BLUE_SOFT, zorder=3)
        axL.scatter([o], [yi], s=110, color=BLUE, zorder=3)
    axL.set_yticks(y)
    axL.set_yticklabels(FMT_NAMES)
    axL.set_xlabel("Slot-filling partial credit")
    axL.set_title("(A) Scores under each condition", fontsize=10.5)
    rmin, omax = per_fmt["retrieved"].min(), per_fmt["oracle"].max()
    axL.annotate("", xy=(omax, -0.9), xytext=(rmin, -0.9),
                 arrowprops=dict(arrowstyle="<->", color=RED, lw=1.8))
    axL.text((rmin + omax) / 2, -1.25, "context effect: +0.320 to +0.374",
             color=RED, ha="center", va="top", fontsize=10.5, fontweight="bold")
    handles = [Line2D([], [], marker="o", ls="", ms=10, color=BLUE_SOFT,
                      label="Retrieved context"),
               Line2D([], [], marker="o", ls="", ms=10, color=BLUE,
                      label="Oracle context")]
    axL.legend(handles=handles, loc="upper left", frameon=True)
    axL.set_ylim(-2.0, len(FMT_IDS) + 1.6)
    axL.grid(axis="x", color="#eeeeee", zorder=0)

    axR.axvline(0, color=GREY, lw=1)
    axR.errorbar(point.values, y, xerr=[point.values - lo_ci, hi_ci - point.values],
                 fmt="o", color=BLUE, ecolor=BLUE, ms=8, capsize=4, lw=2)
    axR.set_yticks(y)
    axR.set_yticklabels([])
    axR.set_xlabel("oracle - retrieved (95% CI over 30 items)")
    axR.set_title("(B) Per-format context effect", fontsize=10.5)
    axR.set_xlim(-0.05, 0.48)
    spread_y = len(FMT_IDS) + 0.4
    axR.errorbar([0.012], [spread_y], xerr=[0.012], color=GREY,
                 capsize=3, elinewidth=1.6, capthick=1.6)
    axR.text(0.034, spread_y, "format spread (0.024), same scale", fontsize=9.5,
             color=GREY, ha="left", va="center")
    axR.grid(axis="x", color="#eeeeee", zorder=0)
    axR.set_ylim(-2.0, len(FMT_IDS) + 1.6)

    fig.tight_layout()
    fig.savefig(out / "fig2_context_vs_format.pdf", bbox_inches="tight")
    plt.close(fig)


def fig2_slide(per_fmt, point, lo_ci, hi_ci, out):
    """Slide 10, 0.9 of the frame width."""
    fig, (axL, axR) = slide_fig(392, 190, ncols=2,
                                gridspec_kw={"width_ratios": [1.5, 1.0]})
    y = np.arange(len(FMT_IDS))[::-1]
    for yi, fid in zip(y, FMT_IDS):
        r, o = per_fmt.loc[fid, "retrieved"], per_fmt.loc[fid, "oracle"]
        axL.plot([r, o], [yi, yi], color="#9DBBB6", lw=2.5, zorder=2)
        axL.scatter([r], [yi], s=70, color=BLUE_SOFT, zorder=3)
        axL.scatter([o], [yi], s=70, color=BLUE, zorder=3)
    axL.set_yticks(y)
    axL.set_yticklabels(FMT_NAMES)
    axL.set_xlabel("Slot-filling partial credit")
    axL.set_title("(A) Scores under each condition")
    rmin, omax = per_fmt["retrieved"].min(), per_fmt["oracle"].max()
    axL.annotate("", xy=(omax, -0.9), xytext=(rmin, -0.9),
                 arrowprops=dict(arrowstyle="<->", color=RED, lw=1.8))
    axL.text((rmin + omax) / 2, -1.3, "context effect: +0.320 to +0.374",
             color=RED, ha="center", va="top", fontsize=10, fontweight="bold")
    handles = [Line2D([], [], marker="o", ls="", ms=8, color=BLUE_SOFT,
                      label="Retrieved context"),
               Line2D([], [], marker="o", ls="", ms=8, color=BLUE,
                      label="Gold context")]
    axL.legend(handles=handles, loc="upper center", ncol=2, frameon=True,
               handletextpad=0.3, columnspacing=1.0)
    axL.set_ylim(-2.6, len(FMT_IDS) + 1.6)
    axL.grid(axis="x", color="#eeeeee", zorder=0)

    axR.axvline(0, color=GREY, lw=1)
    axR.errorbar(point.values, y, xerr=[point.values - lo_ci, hi_ci - point.values],
                 fmt="o", color=BLUE, ecolor=BLUE, ms=7, capsize=3, lw=2)
    axR.set_yticks(y)
    axR.set_yticklabels([])
    axR.set_xlabel("gold - retrieved\n(95% CI over 30 items)")
    axR.set_title("(B) Context effect")
    axR.set_xlim(-0.05, 0.48)
    spread_y = len(FMT_IDS) + 0.5
    axR.errorbar([0.012], [spread_y], xerr=[0.012], color=GREY,
                 capsize=3, elinewidth=1.6, capthick=1.6)
    axR.text(0.04, spread_y, "serialisation spread\n(0.024), same scale",
             fontsize=9, color=GREY, ha="left", va="center")
    axR.grid(axis="x", color="#eeeeee", zorder=0)
    axR.set_ylim(-2.6, len(FMT_IDS) + 1.6)

    slide_save(fig, out, "fig2_context_vs_format")


# ---------------------------------------------------------------- fig 3
def fig3(scored, out, slide=False):
    ver = scored[scored.task_type == "verification"]
    one = (ver[ver.task_id.isin(ONE_HOP)].groupby("format").accuracy_mean
           .mean().reindex(FMT_IDS))
    multi = (ver[ver.task_id.isin(MULTI_HOP)].groupby("format").accuracy_mean
             .mean().reindex(FMT_IDS))
    anc = "elot-org-ancestors"
    others_1hop = one.drop(anc).mean()
    check("fig3 anc 1-hop", one[anc], 0.313, tol=0.002)
    check("fig3 others 1-hop", others_1hop, 0.747, tol=0.002)
    if slide:
        return fig3_slide(one, multi, others_1hop, out)

    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    x = np.arange(len(FMT_IDS))
    w = 0.38
    for i, fid in enumerate(FMT_IDS):
        solid = RED if fid == anc else BLUE
        hatchc = RED_SOFT if fid == anc else "#BFDCD8"
        ax.bar(i - w / 2, one[fid], w, color=solid, zorder=3)
        ax.bar(i + w / 2, multi[fid], w, color=hatchc,
               edgecolor=RED if fid == anc else "#4A8078", lw=0.8, zorder=3)
    ax.axhline(others_1hop, ls=":", color="#333333", lw=1.3, zorder=2)
    ai = FMT_IDS.index(anc)
    ax.annotate("", xy=(ai - w / 2, one[anc]), xytext=(ai - w / 2, others_1hop),
                arrowprops=dict(arrowstyle="<->", color=RED, lw=1.8))
    ax.text(ai - 0.02, others_1hop + 0.035, f"-{others_1hop - one[anc]:.3f}",
            color=RED, fontsize=11.5, fontweight="bold", ha="right", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels(FMT_NAMES, rotation=20, ha="right")
    ax.set_ylabel("Verification accuracy")
    ax.set_ylim(0, 1.08)
    handles = [Patch(facecolor=BLUE, label="Directly asserted, 1 hop (n = 2)"),
               Patch(facecolor="#BFDCD8", edgecolor="#4A8078", lw=0.8,
                     label="Entailed chain, 2-4 hops (n = 8)"),
               Line2D([], [], ls=":", color="#333333",
                      label=f"other six formats, 1 hop = {others_1hop:.3f}")]
    ax.legend(handles=handles, loc="upper left", frameon=True)
    ax.grid(axis="y", color="#eeeeee", zorder=0)
    fig.tight_layout()
    fig.savefig(out / "fig3_subclass_omission.pdf", bbox_inches="tight")
    plt.close(fig)


def fig3_slide(one, multi, others_1hop, out):
    """Slide 13, the 0.64-width column. Legend above the bars."""
    anc = "elot-org-ancestors"
    fig, ax = slide_fig(278.6, 205)
    x = np.arange(len(FMT_IDS))
    w = 0.38
    for i, fid in enumerate(FMT_IDS):
        solid = RED if fid == anc else BLUE
        hatchc = RED_SOFT if fid == anc else "#BFDCD8"
        ax.bar(i - w / 2, one[fid], w, color=solid, zorder=3)
        ax.bar(i + w / 2, multi[fid], w, color=hatchc,
               edgecolor=RED if fid == anc else "#4A8078", lw=0.8, zorder=3)
    ax.axhline(others_1hop, ls=":", color="#333333", lw=1.3, zorder=2)
    ai = FMT_IDS.index(anc)
    ax.annotate("", xy=(ai - w / 2, one[anc]), xytext=(ai - w / 2, others_1hop),
                arrowprops=dict(arrowstyle="<->", color=RED, lw=1.8))
    # above the ELOT-flat bars, ending short of the light ELOT-nested bar
    top = max(others_1hop, one["elot-org"], multi["elot-org"])
    ax.text(ai - 0.1, top + 0.03, f"-{others_1hop - one[anc]:.3f}", color=RED,
            fontsize=10, fontweight="bold", ha="right", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels(FMT_NAMES, rotation=30, ha="right",
                       rotation_mode="anchor")
    ax.set_ylabel("Verification accuracy")
    ax.set_ylim(0, 1.05)
    ax.set_xlim(-0.6, len(FMT_IDS) - 0.4)
    handles = [Patch(facecolor=BLUE, label="Directly asserted, 1 hop (n = 2)"),
               Patch(facecolor="#BFDCD8", edgecolor="#4A8078", lw=0.8,
                     label="Entailed chain, 2-4 hops (n = 8)"),
               Line2D([], [], ls=":", color="#333333",
                      label=f"other six serialisations, 1 hop = {others_1hop:.3f}")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.02),
              frameon=True, borderaxespad=0)
    ax.grid(axis="y", color="#eeeeee", zorder=0)
    slide_save(fig, out, "fig3_subclass_omission")


# ---------------------------------------------------------------- fig 4
def fig4(raw, out, slide=False):
    ver = raw[(raw.task_type == "verification") & raw.parse_ok]
    labels = ["supported", "contradicted", "undetermined"]
    mat = pd.crosstab(ver.grade_gold_label, ver.grade_pred_label).reindex(
        index=labels, columns=labels).fillna(0)
    pct = mat.div(mat.sum(axis=1), axis=0) * 100

    check("fig4 und->contradicted", pct.loc["undetermined", "contradicted"], 90.8, tol=0.05)
    assert mat.loc["undetermined", "supported"] == 0
    if slide:
        return fig4_slide(pct, labels, out)

    fig, ax = plt.subplots(figsize=(7.6, 6.6))
    ax.imshow(pct.values, cmap="BuGn", vmin=0, vmax=100)
    for i in range(3):
        for j in range(3):
            v = pct.values[i, j]
            bold = (i == 2 and j == 1)
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center",
                    fontsize=14, fontweight="bold" if bold else "normal",
                    color="white" if v > 55 else "#222222")
    ax.add_patch(Rectangle((0.5, 1.5), 1, 1, fill=False, edgecolor=RED, lw=3))
    ax.set_xticks(range(3))
    ax.set_xticklabels(labels)
    ax.set_yticks(range(3))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Model answered", labelpad=10)
    ax.set_ylabel("Correct answer")
    ax.spines[:].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "fig4_undetermined_collapse.pdf", bbox_inches="tight")
    plt.close(fig)


def fig4_slide(pct, labels, out):
    """Slide 11, the 0.46-width column."""
    fig, ax = slide_fig(200, 190)
    ax.imshow(pct.values, cmap="BuGn", vmin=0, vmax=100)
    for i in range(3):
        for j in range(3):
            v = pct.values[i, j]
            bold = (i == 2 and j == 1)
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center",
                    fontsize=11, fontweight="bold" if bold else "normal",
                    color="white" if v > 55 else "#222222")
    ax.add_patch(Rectangle((0.5, 1.5), 1, 1, fill=False, edgecolor=RED, lw=3))
    ax.set_xticks(range(3))
    ax.set_xticklabels(labels, rotation=30, ha="right", rotation_mode="anchor")
    ax.set_yticks(range(3))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Model answered")
    ax.set_ylabel("Gold label")
    ax.spines[:].set_visible(False)
    slide_save(fig, out, "fig4_undetermined_collapse")


# ---------------------------------------------------------------- fig 5
def fig5(raw, out, slide=False):
    sf = raw[(raw.task_type == "slot_filling")].copy()
    for c in ANSWER_FIELDS + CITATION_FIELDS:
        sf[c] = pd.to_numeric(sf[c], errors="coerce")
    sf["answer_score"] = sf[ANSWER_FIELDS].mean(axis=1)
    sf["citation_score"] = sf[CITATION_FIELDS].mean(axis=1)

    by_arm = sf.groupby("model")[["answer_score", "citation_score"]].mean()
    by_cond = sf.groupby("condition")[["answer_score", "citation_score"]].mean()

    documented = {"claude-sonnet-4-5-20250929": (0.840, 0.673),
                  "gpt-4o-2024-11-20": (0.844, 0.681),
                  "gpt-4o-mini-2024-07-18": (0.736, 0.652),
                  "llama3.1:8b-instruct-q8_0": (0.807, 0.266)}
    for arm, (a, c) in documented.items():
        check(f"fig5 answer {arm}", by_arm.loc[arm, "answer_score"], a, tol=0.002)
        check(f"fig5 citation {arm}", by_arm.loc[arm, "citation_score"], c, tol=0.002)
    check("fig5 oracle answer", by_cond.loc["oracle", "answer_score"], 0.953, tol=0.002)
    check("fig5 oracle citation", by_cond.loc["oracle", "citation_score"], 0.789, tol=0.002)
    check("fig5 retrieved answer", by_cond.loc["retrieved", "answer_score"], 0.661, tol=0.002)
    check("fig5 retrieved citation", by_cond.loc["retrieved", "citation_score"], 0.346, tol=0.002)
    if slide:
        return fig5_slide(by_arm, by_cond, out)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(9.6, 4.4),
                                   gridspec_kw={"width_ratios": [2.0, 1.0]})
    w = 0.38
    x = np.arange(len(ARMS))
    for i, (arm_id, _) in enumerate(ARMS):
        a = by_arm.loc[arm_id, "answer_score"]
        c = by_arm.loc[arm_id, "citation_score"]
        llama = arm_id.startswith("llama")
        axA.bar(i - w / 2, a, w, color=BLUE, zorder=3)
        axA.bar(i + w / 2, c, w, color=RED if llama else BLUE_SOFT, zorder=3)
        axA.text(i - w / 2, a + 0.015, f"{a:.3f}", ha="center", fontsize=10)
        axA.text(i + w / 2, c + 0.015, f"{c:.3f}", ha="center", fontsize=10,
                 color=RED if llama else "#222222",
                 fontweight="bold" if llama else "normal")
    axA.set_xticks(x)
    axA.set_xticklabels([n for _, n in ARMS])
    axA.set_ylim(0, 1.05)
    axA.set_ylabel("Score")
    axA.set_title("(A) By arm", fontsize=10.5)
    handles = [Patch(facecolor=BLUE, label="Answer fields (is the modelling right?)"),
               Patch(facecolor=BLUE_SOFT, label="Citation fields (can it name the source?)")]
    axA.legend(handles=handles, loc="upper right", frameon=True, fontsize=9)
    axA.grid(axis="y", color="#eeeeee", zorder=0)

    xc = np.arange(2)
    for i, cond in enumerate(["oracle", "retrieved"]):
        a = by_cond.loc[cond, "answer_score"]
        c = by_cond.loc[cond, "citation_score"]
        axB.bar(i - w / 2, a, w, color=BLUE, zorder=3)
        axB.bar(i + w / 2, c, w, color=BLUE_SOFT, zorder=3)
        axB.text(i - w / 2, a + 0.015, f"{a:.3f}", ha="center", fontsize=10)
        axB.text(i + w / 2, c + 0.015, f"{c:.3f}", ha="center", fontsize=10)
    axB.set_xticks(xc)
    axB.set_xticklabels(["Oracle", "Retrieved"])
    axB.set_ylim(0, 1.05)
    axB.set_title("(B) By condition", fontsize=10.5)
    axB.grid(axis="y", color="#eeeeee", zorder=0)

    fig.tight_layout()
    fig.savefig(out / "fig5_answer_vs_citation.pdf", bbox_inches="tight")
    plt.close(fig)


def fig5_slide(by_arm, by_cond, out):
    """Slide 12, 0.86 of the frame width. Legend above both panels."""
    fig, (axA, axB) = slide_fig(374.3, 195, ncols=2, sharey=True,
                                gridspec_kw={"width_ratios": [2.75, 1.15]})
    w = 0.42
    x = np.arange(len(ARMS))
    for i, (arm_id, _) in enumerate(ARMS):
        a = by_arm.loc[arm_id, "answer_score"]
        c = by_arm.loc[arm_id, "citation_score"]
        llama = arm_id.startswith("llama")
        axA.bar(i - w / 2, a, w, color=BLUE, zorder=3)
        axA.bar(i + w / 2, c, w, color=RED if llama else BLUE_SOFT, zorder=3)
        axA.text(i - w / 2, a + 0.015, f"{a:.3f}", ha="center", fontsize=9)
        axA.text(i + w / 2, c + 0.015, f"{c:.3f}", ha="center", fontsize=9,
                 color=RED if llama else "#222222",
                 fontweight="bold" if llama else "normal")
    axA.set_xticks(x)
    # two lines, or the two right-hand labels run together at slide size
    axA.set_xticklabels([{"GPT-4o-mini": "GPT-4o\nmini",
                          "Llama 3.1 8B": "Llama 3.1\n8B"}.get(n, n) for _, n in ARMS])
    axA.set_ylim(0, 1.05)
    axA.set_ylabel("Score")
    axA.set_title("(A) By arm")
    axA.grid(axis="y", color="#eeeeee", zorder=0)

    xc = np.arange(2)
    for i, cond in enumerate(["oracle", "retrieved"]):
        a = by_cond.loc[cond, "answer_score"]
        c = by_cond.loc[cond, "citation_score"]
        axB.bar(i - w / 2, a, w, color=BLUE, zorder=3)
        axB.bar(i + w / 2, c, w, color=BLUE_SOFT, zorder=3)
        axB.text(i - w / 2, a + 0.015, f"{a:.3f}", ha="center", fontsize=9)
        axB.text(i + w / 2, c + 0.015, f"{c:.3f}", ha="center", fontsize=9)
    axB.set_xticks(xc)
    axB.set_xticklabels(["Gold", "Retrieved"])
    axB.set_ylim(0, 1.05)
    axB.set_title("(B) By condition")
    axB.grid(axis="y", color="#eeeeee", zorder=0)

    handles = [Patch(facecolor=BLUE, label="Answer fields (is the modelling right?)"),
               Patch(facecolor=BLUE_SOFT, label="Citation fields (can it name the source?)")]
    fig.legend(handles=handles, loc="outside upper center", ncol=2, frameon=True,
               handlelength=1.2, columnspacing=1.0)
    slide_save(fig, out, "fig5_answer_vs_citation")


# ---------------------------------------------------------------- fig 6
def fig6(scored, out, slide=False):
    ver = scored[scored.task_type == "verification"]
    mechs = [
        ("bare_disjointness", "Bare disjointness"),
        ("functional_property", "Functional property"),
        ("subsumption", "Supported subsumption"),
        ("composed_domain_range_disjointness", "Composed domain/range"),
        ("unasserted_class_relation", "Undetermined"),
    ]
    acc, names = [], []
    for mid, label in mechs:
        sub = ver[ver.mechanism == mid]
        n = sub.task_id.nunique()
        acc.append(sub.accuracy_mean.mean())
        names.append(f"{label}\n({n} items)")
    documented = [0.994, 0.952, 0.745, 0.683, 0.092]
    for (mid, _), got, want in zip(mechs, acc, documented):
        check(f"fig6 {mid}", got, want, tol=0.002)
    if slide:
        return fig6_slide(acc, names, out)

    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    y = np.arange(len(mechs))[::-1]
    colors = [BLUE] * 4 + [RED]
    ax.barh(y, acc, color=colors, height=0.62, zorder=3)
    for yi, v in zip(y, acc):
        ax.text(v + 0.012, yi, f"{v:.3f}", va="center", fontsize=11.5)
    ax.axvline(1 / 3, ls="--", color="#333333", lw=1.3, zorder=2)
    ax.text(1 / 3 + 0.012, 0, "majority-class baseline (0.333)",
            fontsize=10, color="#333333", ha="left", va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlabel("Verification accuracy")
    ax.set_xlim(0, 1.1)
    ax.grid(axis="x", color="#eeeeee", zorder=0)
    fig.tight_layout()
    fig.savefig(out / "fig6_mechanism.pdf", bbox_inches="tight")
    plt.close(fig)


def fig6_slide(acc, names, out):
    """Backup slide A2, the 0.57-width column."""
    fig, ax = slide_fig(248, 175)
    y = np.arange(len(acc))[::-1]
    colors = [BLUE] * 4 + [RED]
    ax.barh(y, acc, color=colors, height=0.62, zorder=3)
    for yi, v in zip(y, acc):
        # 9pt, as on the other slides: at 10pt "0.092" ran into the baseline
        ax.text(v + 0.012, yi, f"{v:.3f}", va="center", fontsize=9)
    ax.axvline(1 / 3, ls="--", color="#333333", lw=1.3, zorder=2)
    ax.text(1 / 3 + 0.03, 0, "majority-class\nbaseline (0.333)",
            fontsize=9, color="#333333", ha="left", va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlabel("Verification accuracy")
    ax.set_xlim(0, 1.24)
    ax.set_xticks([0, 0.5, 1.0])
    ax.grid(axis="x", color="#eeeeee", zorder=0)
    slide_save(fig, out, "fig6_mechanism")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True,
                    help="directory to write the six PDF figures into")
    ap.add_argument("--slide", action="store_true",
                    help="write the seminar-deck versions (<name>_slide.pdf)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    style()
    if args.slide:
        slide_style()
    out, slide = args.out, args.slide
    scored = pd.read_csv(SCORED)
    raw = pd.read_csv(RAW, low_memory=False)
    retrieval = pd.read_csv(RETRIEVAL)

    print("[fig1]"); fig1(scored, raw, retrieval, out, slide)
    print("[fig2]"); fig2(scored, out, slide)
    print("[fig3]"); fig3(scored, out, slide)
    print("[fig4]"); fig4(raw, out, slide)
    print("[fig5]"); fig5(raw, out, slide)
    print("[fig6]"); fig6(scored, out, slide)
    print(f"\nWrote 6 {'slide ' if slide else ''}figures to {out}")


if __name__ == "__main__":
    main()
