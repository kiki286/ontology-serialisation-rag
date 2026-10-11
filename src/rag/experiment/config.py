"""Fixed experiment configuration.

Everything here is pinned for the dissertation so a single source of truth can
be cited in the methods chapter and recorded in each trial's ``manifest.json``.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
EXPERIMENT_DIR = Path(__file__).resolve().parent
RAG_DIR = EXPERIMENT_DIR.parent
SRC_DIR = RAG_DIR.parent
DATA_DIR = RAG_DIR / "data"
PROMPTS_DIR = EXPERIMENT_DIR / "prompts"
BENCHMARK_DIR = EXPERIMENT_DIR / "benchmark"
TASKS_PATH = BENCHMARK_DIR / "tasks.yaml"
RESULTS_DIR = EXPERIMENT_DIR / "results"
INDEX_DIR = EXPERIMENT_DIR / "indexes"  # experiment-scoped FAISS indexes
ENV_PATH = SRC_DIR / ".env"

# ---------------------------------------------------------------------------
# Formats under test. Each maps to its source ontology file in DATA_DIR.
# The same underlying ontology is compared across serialisations/encodings.
# ---------------------------------------------------------------------------
FORMATS = ["turtle", "elot-org", "elot-org-ancestors", "omn", "jsonld", "yaml-ld", "ofn"]

ONTOLOGY_FILES = {
    "turtle": "LIS-14-for-FDIS (1).ttl",
    "elot-org": "LIS-14-for-FDIS (1).org",
    "elot-org-ancestors": "LIS-14-for-FDIS (1).org",
    "omn": "LIS-14-for-FDIS (1).omn",
    "jsonld": "LIS-14-for-FDIS (1).jsonld",
    "yaml-ld": "LIS-14-for-FDIS (1).yamlld",
    "ofn": "LIS-14-for-FDIS (1).ofn",
    # schema-concept is an exploratory condition, NOT a member of FORMATS (see
    # EXPLORATORY_FORMATS below). It parses the canonical Turtle directly.
    "schema-concept": "LIS-14-for-FDIS (1).ttl",
}

# Exploratory conditions that are selectable on the CLI but deliberately excluded
# from the headline "same ontology, N serialisations" comparison. schema-concept
# is a lossy, curated schema-first indexing baseline (Voicebox-style): it does not
# satisfy whole-graph isomorphism or the 155-entity full-serialisation parity that
# FORMATS members share, so keeping it out of FORMATS ensures a default --formats
# run (and the RQ1/RQ2 headline) stays the 7-serialisation comparison. Opt in with
# ``--formats schema-concept`` (optionally alongside a serialisation like turtle).
EXPLORATORY_FORMATS = ["schema-concept"]
ALL_SELECTABLE_FORMATS = FORMATS + EXPLORATORY_FORMATS

# ELOT ancestor chunks preserve the ancestor heading PATH (heading lines only,
# not ancestor bodies). Plain (flat) ELOT is the verbatim single-entity slice
# plus a single 1-hop ``- SubClassOf :: <parent>`` line on class chunks, so it
# carries the same immediate superclass that Turtle/OMN state natively.
ELOT_ANCESTOR_FORMAT = "elot-org-ancestors"

# ---------------------------------------------------------------------------
# Models (explicit dated snapshots, temperature 0)
# ---------------------------------------------------------------------------
# Every arm is a dated/quantised pin, never a floating alias, so each can be cited
# exactly in the methods chapter. ``llm_call.detect_provider`` routes on the model
# string: "llama" -> Ollama, "claude" -> Anthropic, everything else -> OpenAI.
#
# Determinism is NOT uniform across arms and must not be described as pinned (see
# CHANGELOG 2026-08-13 (c), which retracts the assumed determinism of the GPT-4o
# baseline). ``SEED`` is sent where the provider accepts it and is best-effort
# everywhere: OpenAI documents ``seed`` as best-effort, the Anthropic API has no
# seed parameter at all, and Ollama seeds are subject to GPU nondeterminism. The
# defensible claim is graded-field stability, not reproducible raw output.
#
# ``claude-sonnet-4-5-20250929`` is the cross-vendor arm adopted by CHANGELOG
# 2026-08-13 (b) decision D2, in preference to gpt-5.5/gpt-5.6 (no dated snapshot,
# temperature=0 rejected). It honours temperature=0 and uses tool-use structured
# output, which keeps the prompt byte-identical across arms. Keep it AFTER the two
# GPT snapshots: run_experiment picks ``MODELS[1]`` (gpt-4o-mini) as the cheap
# single-model default for --stage smoke.
MODELS = [
    "gpt-4o-2024-11-20",
    "gpt-4o-mini-2024-07-18",
    "claude-sonnet-4-5-20250929",
    "llama3.1:8b-instruct-q8_0",
]
TEMPERATURE = 0.0
SEED = 20260529  # fixed; document in methods chapter
DEFAULT_POSTRETRIEVAL_N_TRIALS = 3
POSTRETRIEVAL_SEEDS = [20260529, 20260530, 20260531]
EMBEDDING_MODEL = "text-embedding-3-large"  # matches the production assistant

# Local inference (Ollama, OpenAI-compatible endpoint). Keep the existing pin
# unchanged for the oracle and retrieved conditions; whole-context uses its own
# larger window and is opt-in.
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_NUM_CTX = 16384
WHOLE_CONTEXT_GENERATION_HEADROOM = 512
# Phase 1 measurement: the largest T02 source-file prompt is JSON-LD at 55,734
# Llama tokens with source newlines preserved; this leaves 512-token headroom.
OLLAMA_NUM_CTX_WHOLE_CONTEXT = 56246

# Generation cap for the Ollama arm. Ollama's default is unbounded -- it decodes
# until the context window is full -- and on 2026-08-20 that ended an overnight run:
# one Llama call degenerated into a runaway JSON loop, decoded 12,753 tokens at a
# healthy ~46 tok/s, and was still going when the 300s client timeout fired. The
# failure is structural, not bad luck: with a ~2k prompt in a 16,384 window the model
# needs ~14,400 tokens (~313s) to self-terminate on context exhaustion, which is
# LONGER than the client timeout, so any degenerate response is guaranteed to kill
# the run rather than return.
#
# 1024 matches the Anthropic arm's max_tokens, so the two capped arms are
# comparable. It cannot truncate a legitimate answer: across all 2,788 recorded
# post-retrieval calls the longest completion is 477 tokens and none exceeds 1024.
# Capping converts a degenerate response from a crash into a truncated response that
# fails parsing and is RECORDED as a parse error -- data, which is the correct
# scientific outcome -- and bounds the worst-case call to ~22s.
OLLAMA_NUM_PREDICT = 1024

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
RETRIEVAL_K = 5
# Run retrieval/oracle over the ontology only so shared markdown docs do not
# confound the format comparison.
CORPUS_MODE = "ontology"

# ---------------------------------------------------------------------------
# Oracle padding (WI7). ``oracle_padded`` is a THIRD condition, added alongside the
# unpadded ``oracle`` upper bound rather than replacing it: padding turns the oracle
# from "given exactly the right chunks" into "given the right chunks plus noise",
# which depresses scores for reasons unrelated to retrieval, so both are kept.
# ``oracle_padded`` pads sub-k gold contexts up to k with NON-gold chunks so window
# size stops confounding the oracle/retrieved contrast. Oracle sets that already
# exceed k are never truncated (dropping gold defeats the condition); the over-k
# discrepancy is recorded instead.
#   - "random" (default): padding entity ids are sampled ONCE PER TASK with a pinned
#     per-task seed from the shared retrieval-eligible pool, then the SAME entities
#     are serialised into every format. Sampling per format would reintroduce the
#     entity-set variation random padding exists to avoid. Fully offline.
#   - "retrieved": top-ranked non-gold chunks for the task query (needs embeddings);
#     intentionally per-format (realistic distractors), NOT entity-controlled.
# Which source is the right control is a research decision, surfaced not decided here.
ORACLE_PAD_SEED = SEED
ORACLE_PAD_STRATEGIES = ["random", "retrieved"]

# ---------------------------------------------------------------------------
# Context block assembly (locked-down decisions)
# ---------------------------------------------------------------------------
CHUNK_DELIMITER = "# --- chunk boundary ---"
CHUNK_LABEL = "# Chunk: {entity_id}"

# ---------------------------------------------------------------------------
# Prompt versions (filenames carry the version; cite these exactly)
# ---------------------------------------------------------------------------
SYSTEM_PROMPTS = {
    "verification": PROMPTS_DIR / "verification_system_v1.txt",
    "slot_filling": PROMPTS_DIR / "slot_filling_system_v4.txt",
}

# ``oracle`` is the headline upper bound; ``retrieved`` is the realistic condition.
# ``oracle_padded`` is a selectable robustness-appendix condition, NOT in the default:
# the trial-5 pilot showed the length confound is empirically negligible on the strong
# models (oracle vs oracle_padded slot MPC differed by <=0.03, and padding slightly
# HELPED Llama), so padding is not part of standard runs. Select it explicitly with
# --conditions if reproducing the appendix.
CONDITIONS = ["oracle", "retrieved"]

# ---------------------------------------------------------------------------
# No-context floor (WI2). Establishes what each model scores with NO ontology
# context, so context-conditioned scores can be read against a baseline rather
# than in absolute terms. Two conditions, deliberately kept as a pair:
#   * ``no_context``    - the task input alone; no context block, no header.
#   * ``empty_context`` - the same context SCAFFOLDING (the "Ontology content:"
#     header) with zero chunks inside its body.
# The pair separates "the model knows this from pretraining" from "the model
# responds to an empty context block differently than to no block at all".
#
# The floor is FORMAT-INDEPENDENT BY CONSTRUCTION: with no corpus there is no
# serialisation, so there is no format arm. Cells are model x task x trial. The
# harness therefore collapses the format loop to a single sentinel row rather
# than emitting N identical rows per format. Note this also excludes the prefix
# block: prefix blocks are per-format, so including one would silently
# reintroduce a format arm (and leak ontology namespaces into a "no ontology
# context" condition).
FLOOR_CONDITIONS = ["no_context", "empty_context"]

# Sentinel written to the ``format`` column of floor rows. A literal sentinel is
# used instead of an empty cell because an empty CSV field is indistinguishable
# from a missing value; this is greppable and unambiguous in downstream joins.
FLOOR_FORMAT_SENTINEL = "__no_corpus__"

# ---------------------------------------------------------------------------
# Anthropic prompt caching (B1/B2). The Sonnet arm marks the corpus content block
# with a ``cache_control`` breakpoint so the trials of a cell reuse the prefix.
#
# This is only worth doing if the post-retrieval loop runs a cell's calls
# back-to-back: Anthropic bills a cache WRITE at 1.25x the base input rate, so a
# prefix that is evicted before its next hit costs MORE than not caching at all.
# ``run_postretrieval`` nests format -> model -> condition -> task -> trial for
# exactly this reason. Set to False if that ordering is ever changed back.
# ---------------------------------------------------------------------------
ANTHROPIC_CACHE_CORPUS = True

ALL_CONDITIONS = ["oracle", "oracle_padded", "retrieved", "whole_context"] + FLOOR_CONDITIONS
TASK_TYPES = ["verification", "slot_filling"]


def ollama_num_ctx_for_condition(condition: str) -> int:
    """Return the Ollama context window for a post-retrieval condition."""
    return OLLAMA_NUM_CTX_WHOLE_CONTEXT if condition == "whole_context" else OLLAMA_NUM_CTX


def is_floor_condition(condition: str) -> bool:
    """True for the no-corpus floor conditions (no format arm, no retrieval)."""
    return condition in FLOOR_CONDITIONS


def ontology_path(corpus_format: str) -> Path:
    """Absolute path to the source ontology file for a format."""
    if corpus_format not in ONTOLOGY_FILES:
        raise ValueError(
            f"Unknown format '{corpus_format}'. Expected one of {FORMATS}."
        )
    return DATA_DIR / ONTOLOGY_FILES[corpus_format]
