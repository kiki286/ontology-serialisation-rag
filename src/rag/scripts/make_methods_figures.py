"""Generate the methods-chapter diagrams as PDF figures.

Replaces the in-file TikZ pipeline (methods.tex could not be compiled or
previewed locally) with committed, viewable matplotlib drawings, and adds
diagrams that carry structure the prose otherwise spells out:

- fig_m0_assistant.pdf : the IDO Assistant and its index (introduction,
                         Figure 1.1; redrawn here because its original script
                         was lost, with the format chips widened to fit their
                         labels)
- fig_m1_pipeline.pdf  : the experimental pipeline (supersedes the TikZ figure)
- fig_m2_design.pdf    : the fully crossed factorial and what sits outside it
- fig_m3_scoring.pdf   : the two scoring schemes (selective prediction;
                         six strict fields with the gold-driven denominator)

Style follows the flat-design conceptual-diagram register used in the group's
past theses: saturated Material fills with black outlines, stage tabs, shape
semantics declared in a legend (rectangle = data, stadium = process,
diamond = gate), dashed boxes for grouping, sans-serif labels. Data charts
(the results chapter) deliberately use a quieter register; see
make_thesis_figures.py.

Every number drawn here restates a value fixed in methods.tex (design counts,
seeds, k, field worths). Nothing is computed; if the chapter changes, change
this script to match.

With --slide the script writes fig_m0_assistant_slide.pdf and
fig_m2_design_slide.pdf instead, the two diagrams the seminar deck shows.
Each is drawn at the size it is placed on the 16:9 beamer frame
(\\includegraphics[width=\\textwidth]), so its 9pt labels land at 9pt, and at
the same 3.5pt drawing unit as the thesis canvases, so line weights, corner
radii, tabs and arrowheads are identical in points. The slide design figure
keeps only the five factor cards (the deck trimmed the rest) and uses the
dissertation's wording and display names (serialisations, gold, arms; ELOT-nested,
Claude Sonnet 4.5, ...).

Usage (from src/rag/):
    python -m scripts.make_methods_figures --out <figures-dir> [--slide]
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

# Material palette, sampled from the exemplar thesis diagrams.
TEAL = "#00897B"
TEAL_T = "#B2DFDB"
SLATE = "#607D8B"
SLATE_T = "#CFD8DC"
AMBER = "#FFB300"
AMBER_T = "#FFECB3"
PURPLE = "#8E24AA"
PURPLE_T = "#E1BEE7"
GREEN = "#43A047"
GREEN_T = "#C8E6C9"
INK = "#1A1A1A"
NOTE = "#555555"

FONT = ["Segoe UI", "Arial", "DejaVu Sans"]

plt.rcParams.update({
    "font.family": FONT,
    "text.color": INK,
    "pdf.fonttype": 42,
})


# ---------------------------------------------------------------- primitives

def rbox(ax, x, y, w, h, fc, text, tc=INK, fs=7, lw=1.3, rounding=0.9,
         ls="-", ec="black", weight="normal"):
    """Rounded rectangle = data artifact."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rounding}",
        fc=fc, ec=ec, lw=lw, ls=ls, mutation_aspect=1.0, zorder=3))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, color=tc, zorder=4, weight=weight, linespacing=1.25)


def pill(ax, x, y, w, h, fc, text, tc="white", fs=7, lw=1.3):
    """Stadium shape = process."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={h / 2}",
        fc=fc, ec="black", lw=lw, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc, zorder=4, weight="bold", linespacing=1.25)


def diamond(ax, cx, cy, w, h, fc, text, tc="white", fs=7, lw=1.3):
    """Diamond = gate / filter."""
    ax.add_patch(Polygon(
        [(cx - w / 2, cy), (cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2)],
        closed=True, fc=fc, ec="black", lw=lw, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=tc,
            zorder=4, weight="bold", linespacing=1.2)


def tab(ax, x, y, fc, label, fs=7, tc="white", w=None, h=3.4):
    """Stage tab chip, sits on the top-left corner of a group box."""
    if w is None:
        w = 0.14 * fs * len(label) + 5.0
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.5",
        fc=fc, ec="black", lw=1.1, zorder=5))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=fs, color=tc, weight="bold", zorder=6)


def group(ax, x, y, w, h, ec=NOTE):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
        fc="none", ec=ec, lw=1.0, ls=(0, (4, 2.5)), zorder=1))


def arrow(ax, p1, p2, lw=1.3, style="-|>", color="black", ls="-",
          connectionstyle=None):
    ax.add_patch(FancyArrowPatch(
        p1, p2, arrowstyle=style, mutation_scale=9, lw=lw, color=color,
        ls=ls, shrinkA=1.5, shrinkB=1.5, zorder=2,
        connectionstyle=connectionstyle))


def note(ax, x, y, text, fs=6.2, ha="left", style="italic"):
    ax.text(x, y, text, fontsize=fs, color=NOTE, ha=ha, va="center",
            style=style, linespacing=1.3)


def canvas(w_in, h_in, w_units, h_units):
    fig, ax = plt.subplots(figsize=(w_in, h_in))
    ax.set_xlim(0, w_units)
    ax.set_ylim(0, h_units)
    ax.invert_yaxis()
    ax.set_aspect("auto")
    ax.axis("off")
    return fig, ax


# ------------------------------------------------------------- slide versions

# The thesis canvases draw about 3.5pt per unit; slide canvases use exactly
# that, filling the figure edge to edge so the PDF is the size it is placed at.
SLIDE_UNIT_PT = 3.5
SLIDE_W_PT = 435.2    # \textwidth of the 16:9 beamer frame in seminar.tex
SLIDE_FS = 9          # matches the deck's own \small TikZ diagram labels


def slide_canvas(w_pt, h_pt, top_pt=0):
    """Slide canvas; top_pt adds blank margin above the drawing's y = 0."""
    fig = plt.figure(figsize=(w_pt / 72, (h_pt + top_pt) / 72))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, w_pt / SLIDE_UNIT_PT)
    ax.set_ylim(-top_pt / SLIDE_UNIT_PT, h_pt / SLIDE_UNIT_PT)
    ax.invert_yaxis()
    ax.axis("off")
    return fig, ax


def text_width(ax, text, fs, weight="normal"):
    """Rendered width of a (possibly multi-line) label, in data units."""
    t = ax.text(0, 0, text, fontsize=fs, weight=weight)
    bb = t.get_window_extent(ax.figure.canvas.get_renderer())
    t.remove()
    return bb.width * 72 / ax.figure.dpi / SLIDE_UNIT_PT


def slide_tab(ax, x, y, fc, label, tc="white"):
    """tab() sized to its label at the slide font size."""
    tab(ax, x, y, fc, label, fs=SLIDE_FS, tc=tc,
        w=text_width(ax, label, SLIDE_FS, "bold") + 3.0, h=4.0)


# ----------------------------------------------------------- fig_m0_assistant

ASSISTANT_STEPS = [  # (shape, fill, label), left to right
    ("box", "white", "question"),
    ("pill", SLATE, "retriever"),
    ("box", AMBER_T, "top five\nchunks"),
    ("pill", PURPLE, "language\nmodel"),
    ("box", GREEN_T, "answer with\ncited chunks"),
]
SERIALISATIONS = ["Turtle", "ELOT\nflat", "ELOT\nnested", "OMN", "OFN",
                  "JSON-LD", "YAML-LD"]


def fig_m0(out: Path):
    fig, ax = canvas(6.3, 2.75, 100, 44)

    # ---- the assistant: one retrieve-then-generate pass
    group(ax, 1, 4, 98, 18)
    tab(ax, 3, 2.3, SLATE, "THE IDO ASSISTANT")
    for x, w, (shape, fc, label) in zip((3, 24, 43, 63, 82), (17, 15, 16, 15, 16),
                                        ASSISTANT_STEPS):
        if shape == "pill":
            pill(ax, x, 9.75, w, 6.5, fc, label)
        else:
            rbox(ax, x, 9, w, 8, fc, label)
    for x in (20, 39, 59, 78):
        arrow(ax, (x, 13), (x + 4, 13))

    # ---- its index: built from one serialisation of IDO at a time
    group(ax, 1, 27, 98, 16)
    tab(ax, 3, 25.3, TEAL, "ITS INDEX")
    rbox(ax, 26.4, 31.5, 10.2, 8, SLATE_T, "index")  # centred under the retriever
    arrow(ax, (31.5, 31.5), (31.5, 16.25))
    # the chips are wide enough for "JSON-LD" and "YAML-LD" at 4.9pt
    cw, step, x0 = 6.6, 7.0, 40.6
    for i, fmt in enumerate(SERIALISATIONS):
        rbox(ax, x0 + i * step, 32, cw, 7, TEAL_T, fmt, fs=4.9)
    x1 = x0 + 6 * step + cw
    arrow(ax, (x0, 35.5), (36.6, 35.5))
    rbox(ax, 92.7, 31, 5.1, 9, TEAL, "IDO", tc="white", weight="bold")
    arrow(ax, (92.7, 35.5), (x1, 35.5))
    note(ax, (x0 + x1) / 2, 41.1, "one serialisation at a time", ha="center")

    fig.savefig(out / "fig_m0_assistant.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_m0_slide(out: Path):
    """Seminar slide 2: the same diagram at 9pt. The seven chips cannot share
    one row with the index and IDO at that size, so they sit four over three."""
    # the top margin keeps the first tab off the frame title bar
    fig, ax = slide_canvas(SLIDE_W_PT, 162, top_pt=1.5)
    W = SLIDE_W_PT / SLIDE_UNIT_PT
    fs = SLIDE_FS

    # ---- the assistant
    group(ax, 1, 2.5, W - 2, 15.5)
    slide_tab(ax, 3, 0.5, SLATE, "THE IDO ASSISTANT")
    widths = [21, 19, 20, 19, 22]
    gap = (W - 6 - sum(widths)) / 4
    x, centres = 3, []
    for w, (shape, fc, label) in zip(widths, ASSISTANT_STEPS):
        if shape == "pill":
            pill(ax, x, 7.0, w, 7.5, fc, label, fs=fs)
        else:
            rbox(ax, x, 6.25, w, 9, fc, label, fs=fs)
        if centres:
            arrow(ax, (x - gap, 10.75), (x, 10.75))
        centres.append(x + w / 2)
        x += w + gap
    retriever = centres[1]

    # ---- its index
    group(ax, 1, 22, W - 2, 23.4)
    slide_tab(ax, 3, 20, TEAL, "ITS INDEX")
    ch, rgap = 7.5, 0.4                  # chip height, gap between chips
    gy = 25.5                            # top of the chip grid
    mid = gy + ch + rgap / 2             # vertical centre of the grid
    iw = 12
    rbox(ax, retriever - iw / 2, mid - 4.5, iw, 9, SLATE_T, "index", fs=fs)
    arrow(ax, (retriever, mid - 4.5), (retriever, 14.5))
    dw = 7
    dx = W - 2.5 - dw
    rbox(ax, dx, gy - 0.5, dw, 2 * ch + rgap + 1, TEAL, "IDO", tc="white",
         weight="bold", fs=fs)
    gx0, gx1 = retriever + iw / 2 + 4, dx - 4
    cw = (gx1 - gx0 - 3 * rgap) / 4
    for i, fmt in enumerate(SERIALISATIONS):
        row, col = divmod(i, 4)
        x = gx0 + col * (cw + rgap) + row * (cw + rgap) / 2
        rbox(ax, x, gy + row * (ch + rgap), cw, ch, TEAL_T, fmt, fs=fs)
    arrow(ax, (gx0, mid), (gx0 - 4, mid))
    arrow(ax, (dx, mid), (gx1, mid))
    note(ax, (gx0 + gx1) / 2, 43.0, "one serialisation at a time", fs=fs,
         ha="center")

    fig.savefig(out / "fig_m0_assistant_slide.pdf")
    plt.close(fig)


# ------------------------------------------------------------ fig_m1_pipeline

def fig_m1(out: Path):
    fig, ax = canvas(6.3, 8.8, 100, 140)

    # ---- stage 1: corpus
    group(ax, 1, 3.5, 98, 27.5)
    tab(ax, 3, 1.8, TEAL, "1 · CORPUS: one ontology, seven serialisations")

    rbox(ax, 30, 8, 40, 6.5, TEAL, "canonical Turtle\nLIS-14 v4.2 FDIS",
         tc="white", weight="bold")

    chips = [
        (".ttl", "hand-authored"), (".org", "ELOT flat"), (".org", "ELOT nested"),
        (".omn", "ELOT"), (".jsonld", "RDFLib"), (".yamlld", "RDFLib"),
        (".ofn", "ROBOT"),
    ]
    cw, gap, x0, cy = 12.6, 0.85, 2.9, 21.5
    chip_cx = []
    for i, (ext, gen) in enumerate(chips):
        x = x0 + i * (cw + gap)
        rbox(ax, x, cy, cw, 7.5, TEAL_T, f"{ext}\n{gen}", fs=6.0)
        chip_cx.append(x + cw / 2)
        arrow(ax, (50 + (chip_cx[i] - 50) * 0.55, 14.5), (chip_cx[i], cy))

    # ---- stage 2: chunk and filter
    group(ax, 1, 35, 98, 29)
    tab(ax, 3, 33.3, SLATE, "2 · CHUNK & FILTER")

    pill(ax, 28, 39.5, 44, 5.5, SLATE, "entity-level chunker, per format", fs=7)
    note(ax, 74, 42.2, "one policy,\nformat-native boundaries")
    for cx in chip_cx:
        arrow(ax, (cx, 29), (50 + (cx - 50) * 0.42, 39.5))

    diamond(ax, 50, 51.5, 46, 11, SLATE,
            "exclusion filter\nkeep class, property and\nstandalone disjointness chunks", fs=6.0)
    note(ax, 25.5, 51.5, "excluded chunks are\nprovenance and structure,\nnever gold",
         ha="right")
    arrow(ax, (50, 45), (50, 46))

    rbox(ax, 30, 58.5, 40, 5, SLATE_T, "filtered chunk set, per format", fs=7)
    arrow(ax, (50, 57), (50, 58.5))

    # ---- stage 3: context conditions
    group(ax, 1, 67.5, 98, 29)
    tab(ax, 3, 65.8, AMBER, "3 · CONTEXT: the two conditions", tc=INK)

    rbox(ax, 6, 71.5, 40, 5.5, SLATE_T,
         "FAISS index per format\ntext-embedding-3-large", fs=6.5)
    arrow(ax, (40, 63.5), (28, 71.5))

    rbox(ax, 6, 81.5, 40, 8, AMBER_T,
         "retrieved\ntop $k=5$ by similarity\nalways exactly 5 chunks", fs=6.5,
         weight="normal")
    ax.text(8, 82.9, "", fontsize=1)
    arrow(ax, (26, 77), (26, 81.5))

    rbox(ax, 54, 81.5, 40, 8, AMBER_T,
         "oracle\nexactly the item's gold chunks\n2–8 chunks, no distractors",
         fs=6.5)
    # the asymmetry: oracle bypasses the index entirely
    arrow(ax, (62, 63.5), (74, 81.5))
    note(ax, 79, 77.5, "bypasses the index", ha="left")

    rbox(ax, 14, 92, 72, 4.5, "white",
         "context block: prefix block, then chunk-boundary + id markers, then chunks",
         fs=6.3)
    arrow(ax, (26, 89.5), (38, 92))
    arrow(ax, (74, 89.5), (62, 92))

    # ---- stage 4: generation
    group(ax, 1, 100, 98, 25.5)
    tab(ax, 3, 98.3, PURPLE, "4 · GENERATION")

    rbox(ax, 25, 103.5, 50, 4.5, PURPLE_T,
         "system prompt: verification v1  |  slot-filling v4", fs=6.5)
    arrow(ax, (50, 96.5), (50, 103.5))

    arms = ["gpt-4o", "gpt-4o-mini", "sonnet-4-5", "llama3.1:8b"]
    aw, agap, ax0 = 21.5, 2.6, 2.9
    arm_cx = []
    for i, a in enumerate(arms):
        x = ax0 + i * (aw + agap)
        rbox(ax, x, 111.5, aw, 4.5, PURPLE_T, a, fs=6.5)
        arm_cx.append(x + aw / 2)
        arrow(ax, (50 + (arm_cx[i] - 50) * 0.45, 108), (arm_cx[i], 111.5))

    rbox(ax, 25, 119.5, 50, 4.5, "white",
         "3 trials per cell · seeds 20260529 / 30 / 31", fs=6.5)
    for cx in arm_cx:
        arrow(ax, (cx, 116), (50 + (cx - 50) * 0.45, 119.5))

    # ---- stage 5: grading
    group(ax, 1, 128, 98, 10.5)
    tab(ax, 3, 126.3, GREEN, "5 · GRADING")
    rbox(ax, 8, 130.5, 84, 7, GREEN_T,
         "strict schema parse, then graders\nverification: selective prediction · "
         "slot-filling: six strict fields, answer / citation split",
         fs=6.3)
    arrow(ax, (50, 124), (50, 130.5))

    # ---- legend
    lx, ly = 74.5, 6.5
    rbox(ax, lx, ly, 23, 12.5, "white", "", lw=1.0, rounding=0.6)
    rbox(ax, lx + 1.5, ly + 1.5, 4, 2.2, "white", "", lw=1.0, rounding=0.4)
    ax.text(lx + 6.5, ly + 2.6, "data", fontsize=6, va="center")
    pill(ax, lx + 1.5, ly + 4.6, 4, 2.2, SLATE, "", fs=1)
    ax.text(lx + 6.5, ly + 5.7, "process", fontsize=6, va="center")
    diamond(ax, lx + 3.5, ly + 8.9, 4, 2.4, SLATE, "", fs=1)
    ax.text(lx + 6.5, ly + 8.9, "gate", fontsize=6, va="center")
    ax.text(lx + 13.5, ly + 2.6, "▢ stage", fontsize=6, va="center", color=NOTE)
    ax.text(lx + 13.5, ly + 5.7, "flow ↓", fontsize=6, va="center", color=NOTE)

    fig.savefig(out / "fig_m1_pipeline.pdf", bbox_inches="tight")
    plt.close(fig)


# -------------------------------------------------------------- fig_m2_design

def fig_m2(out: Path):
    fig, ax = canvas(6.3, 4.3, 100, 68)

    # factor cards
    cards = [
        ("ITEMS", "60", SLATE, SLATE_T,
         "30 verification\n(20 determinate,\n10 undetermined)\n30 slot-filling"),
        ("FORMATS", "7", TEAL, TEAL_T,
         "turtle · elot-org\nelot-org-ancestors\nomn · jsonld\nyaml-ld · ofn"),
        ("CONDITIONS", "2", AMBER, AMBER_T, "oracle\nretrieved\n($k=5$)"),
        ("ARMS", "4", PURPLE, PURPLE_T,
         "gpt-4o\ngpt-4o-mini\nsonnet-4-5\nllama3.1:8b"),
        ("TRIALS", "3", GREEN, GREEN_T, "seeds\n20260529\n20260530\n20260531"),
    ]
    cw, gap, x0, y0, chh = 16.4, 3.6, 1.5, 4, 24
    centers = []
    for i, (name, n, col, tint, body) in enumerate(cards):
        x = x0 + i * (cw + gap)
        rbox(ax, x, y0, cw, chh, tint, "", lw=1.3)
        rbox(ax, x, y0, cw, 5.2, col, f"{name} ({n})", tc="white" if col != AMBER else INK,
             fs=6.6, weight="bold", rounding=0.9)
        ax.text(x + cw / 2, y0 + 5.2 + (chh - 5.2) / 2, body, ha="center",
                va="center", fontsize=6.0, linespacing=1.45)
        centers.append(x + cw / 2)
        if i < 4:
            ax.text(x + cw + gap / 2, y0 + chh / 2, "×", ha="center",
                    va="center", fontsize=13, weight="bold")

    # product
    arrow(ax, (50, y0 + chh + 1), (50, y0 + chh + 5))
    rbox(ax, 22, 34, 56, 6.5, "white",
         "3,360 cells  ·  10,080 model calls, each graded\ncell = (item, format, condition, arm), a mean over its 3 trials",
         fs=6.6, weight="normal")
    rbox(ax, 22, 43, 56, 5.5, GREEN_T,
         "unit of analysis: the item\nintervals and contrasts resample the 60 items, not the 3,360 cells",
         fs=6.4)
    arrow(ax, (50, 40.5), (50, 43))

    # retrieval track
    rbox(ax, 1.5, 53, 44, 6.5, TEAL_T,
         "Retrieval, scored separately and once:\n60 items × 7 formats = 420 ranked lists",
         fs=6.4)
    # outside the factorial
    rbox(ax, 50, 52, 48.5, 14, "white", "", ls=(0, (4, 2.5)), ec=NOTE, lw=1.0)
    ax.text(52, 54.6, "outside the factorial, never pooled with it:", fontsize=6.4,
            color=NOTE, style="italic", va="center")
    ax.text(52, 60.2,
            "schema-concept (lossy eighth condition) · whole-context\n"
            "five-item pilot T01–T05 (frozen) · no-context floor\n"
            "oracle_padded (selectable, not run on the 60 items)",
            fontsize=6.2, color=INK, va="center", linespacing=1.5)

    fig.savefig(out / "fig_m2_design.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_m2_slide(out: Path):
    """Seminar slide 5: the five factor cards only, in the deck's wording
    (serialisation, gold, model). Each card is as wide as its longest line
    needs at 9pt; the counts sit under the factor names so that
    "SERIALISATIONS" still leaves room for the × signs between the cards."""
    cards = [
        ("ITEMS", "60", SLATE, SLATE_T,
         "30 verification\n(20 determinate,\n10 undetermined)\n30 slot-filling"),
        ("SERIALISATIONS", "7", TEAL, TEAL_T,
         "Turtle · ELOT-flat\nELOT-nested\nOMN · JSON-LD\nYAML-LD · OFN"),
        ("CONDITIONS", "2", AMBER, AMBER_T, "gold\nretrieved\n($k=5$)"),
        ("ARMS", "4", PURPLE, PURPLE_T,
         "GPT-4o\nGPT-4o-mini\nClaude Sonnet 4.5\nLlama 3.1 8B"),
        ("TRIALS", "3", GREEN, GREEN_T, "seeds\n20260529\n20260530\n20260531"),
    ]
    fig, ax = slide_canvas(SLIDE_W_PT, 105)
    W = SLIDE_W_PT / SLIDE_UNIT_PT
    fs = SLIDE_FS
    widths = [max(text_width(ax, f"{name}\n({n})", fs, "bold") + 1.6,
                  text_width(ax, body, fs) + 2.2)
              for name, n, _, _, body in cards]
    gap = (W - 1.4 - sum(widths)) / 4
    y0, chh, hh = 0.7, 28.6, 8.5
    x = 0.7
    for i, ((name, n, col, tint, body), cw) in enumerate(zip(cards, widths)):
        rbox(ax, x, y0, cw, chh, tint, "", lw=1.3)
        rbox(ax, x, y0, cw, hh, col, f"{name}\n({n})",
             tc="white" if col != AMBER else INK, fs=fs, weight="bold")
        ax.text(x + cw / 2, y0 + hh + (chh - hh) / 2, body, ha="center",
                va="center", fontsize=fs, linespacing=1.45)
        if i < 4:
            ax.text(x + cw + gap / 2, y0 + chh / 2, "×", ha="center",
                    va="center", fontsize=12, weight="bold")
        x += cw + gap

    fig.savefig(out / "fig_m2_design_slide.pdf")
    plt.close(fig)


# ------------------------------------------------------------- fig_m3_scoring

def fig_m3(out: Path):
    fig, ax = canvas(6.3, 4.6, 100, 72)

    # ---- panel A: verification
    group(ax, 1, 4, 47.5, 66, ec=INK)
    tab(ax, 3, 2.3, TEAL, "A · VERIFICATION: selective prediction")

    rbox(ax, 5, 8.5, 39.5, 6.5, TEAL_T,
         "30 items: 20 determinate\n+ 10 undetermined-gold", fs=6.5)
    rbox(ax, 5, 19, 39.5, 6.5, "white",
         "model label:\nsupported / contradicted / undetermined", fs=6.3)
    arrow(ax, (24.75, 15), (24.75, 19))
    note(ax, 24.75, 29, "undetermined = abstention", ha="center")

    rbox(ax, 5, 33, 18.5, 13, TEAL_T,
         "20 determinate\nitems\n\ncoverage +\naccuracy on\nanswered", fs=6.0)
    rbox(ax, 26, 33, 18.5, 13, "white",
         "10 undetermined\nitems\n\nabstention rate,\nreported\nseparately", fs=6.0)
    arrow(ax, (17, 25.5), (14, 33))
    arrow(ax, (32, 25.5), (35, 33))

    diamond(ax, 24.75, 55, 45, 13, TEAL,
            "screen, per arm:\ndoes abstention track\nunderdetermination?", fs=5.8)
    arrow(ax, (14, 46), (20, 50.5))
    arrow(ax, (35, 46), (29.5, 50.5))
    note(ax, 24.75, 64.5,
         "P(und | gold und) − P(und | gold determinate) > 0,\n"
         "else that arm's three-label results are not interpreted", ha="center")

    # ---- panel B: slot-filling
    group(ax, 51.5, 4, 47.5, 66, ec=INK)
    tab(ax, 53.5, 2.3, PURPLE, "B · SLOT-FILLING: six strict fields")

    rbox(ax, 54, 8.5, 42.5, 6.5, PURPLE_T,
         "3 answer fields: class, property, intermediate\n"
         "3 citation fields: one chunk id per answer", fs=6.0)
    rbox(ax, 54, 19, 42.5, 6.5, "white",
         "strict exact match on entity_id\nno accept-lists on either slot", fs=6.3)
    arrow(ax, (75.25, 15), (75.25, 19))

    diamond(ax, 75.25, 34.5, 44, 13, PURPLE,
            "gold-driven denominator:\ndoes gold name a chunk\nfor this citation?",
            fs=5.8)
    arrow(ax, (75.25, 25.5), (75.25, 29))

    rbox(ax, 55.5, 44, 18.5, 11, PURPLE_T,
         "20 items grade\n5 fields\n(one field\n= 0.200)", fs=6.0)
    rbox(ax, 76.5, 44, 18.5, 11, PURPLE_T,
         "10 items grade\n6 fields\n(one field\n= 0.167)", fs=6.0)
    arrow(ax, (72, 39.5), (64.75, 44))
    arrow(ax, (78.5, 39.5), (85.75, 44))

    rbox(ax, 53.5, 59, 43.5, 8, "white",
         "partial credit = correct / graded fields\n"
         "exact match = all graded fields correct\n"
         "answer and citation families also reported separately", fs=6.0)
    arrow(ax, (64.75, 55), (68, 59))
    arrow(ax, (85.75, 55), (83, 59))

    fig.savefig(out / "fig_m3_scoring.pdf", bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--slide", action="store_true",
                    help="write the seminar-deck versions (<name>_slide.pdf)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.slide:
        fig_m0_slide(args.out)
        fig_m2_slide(args.out)
        print(f"wrote fig_m0_assistant_slide.pdf, fig_m2_design_slide.pdf -> {args.out}")
        return
    fig_m0(args.out)
    fig_m1(args.out)
    fig_m2(args.out)
    fig_m3(args.out)
    print("wrote fig_m0_assistant.pdf, fig_m1_pipeline.pdf, fig_m2_design.pdf, "
          f"fig_m3_scoring.pdf -> {args.out}")


if __name__ == "__main__":
    main()
