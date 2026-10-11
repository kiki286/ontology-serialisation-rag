"""Probe B2 — explicit open-world statement. Diagnostic sub-study, NOT the benchmark.

Tests hypothesis H2 for the oracle ``undetermined`` degeneracy: do the GPT arms
recover the label when the verification prompt states explicitly that absence of
an entailing axiom does not establish contradiction?

This is a SEPARATE diagnostic sub-study. It reads ``tasks_60.yaml`` and writes
nothing to it. Its results live in ``results/probe_b2_openworld/`` with their own
manifest and are never pooled with the frozen 60-item run.

The frozen harness is not modified. The prompt swap repoints the
``SYSTEM_PROMPTS["verification"]`` entry at the probe file **in this process
only** — no committed file changes. Repointing the mapping rather than patching
``_system_prompt`` is deliberate: ``run_one`` records provenance as
``SYSTEM_PROMPTS[task_type].name``, so this keeps the ``system_prompt`` column
honest. A row that says ``verification_system_v1.txt`` would be a mislabelled
probe row, and the post-run assertion below fails the run if one appears.

Baseline (row zero) is read from the frozen run on disk — the same 20 items x 3
formats x 3 models x 3 trials under ``oracle`` already exist there, so no
baseline calls are re-billed.

Run from ``src/rag``:
    ./.venv/Scripts/python.exe -m scripts.diagnostics.probe_b2_openworld
    ./.venv/Scripts/python.exe -m scripts.diagnostics.probe_b2_openworld --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from experiment import postretrieval
from experiment.config import (
    ENV_PATH,
    POSTRETRIEVAL_SEEDS,
    PROMPTS_DIR,
    RESULTS_DIR,
    SYSTEM_PROMPTS,
)
from experiment.pricing import PRICING_SNAPSHOT_DATE, compute_cost, summarise_cost
from experiment.postretrieval import run_postretrieval
from experiment.run_experiment import write_csv
from experiment.schemas import load_tasks

load_dotenv(dotenv_path=ENV_PATH)

PROBE_ID = "probe_b2_openworld"
PROBE_PROMPT = PROMPTS_DIR / "verification_system_v1_probe_b2.txt"
BASELINE_RUN = RESULTS_DIR / "postretrieval-combined-15-18"
OUT_DIR = RESULTS_DIR / PROBE_ID

FORMATS = ["turtle", "elot-org", "jsonld"]
MODELS = [
    "gpt-4o-2024-11-20",
    "gpt-4o-mini-2024-07-18",
    "claude-sonnet-4-5-20250929",  # reference arm: must keep using the label
]
CONDITIONS = ["oracle"]
N_CONTROLS_PER_LABEL = 5


def select_items(tasks):
    """10 undetermined-gold verification items + 5 supported + 5 contradicted.

    Deterministic: controls are the first N by task_id within each gold label, so
    the item set is reproducible without recording it separately.
    """
    ver = [t for t in tasks if t.task_type == "verification"]
    by_label = {}
    for t in sorted(ver, key=lambda t: t.task_id):
        by_label.setdefault(t.gold_label, []).append(t)
    chosen = list(by_label.get("undetermined", []))
    for label in ("supported", "contradicted"):
        chosen += by_label.get(label, [])[:N_CONTROLS_PER_LABEL]
    return sorted(chosen, key=lambda t: t.task_id)


def install_rate_limit_retry(max_attempts: int = 8) -> None:
    """Wrap ``call_model`` with retry-on-429, in this process only.

    The account is tier-1 (30,000 TPM on the gpt-4o limit group) and a gpt-4o
    verification call is ~2.4k tokens, so a back-to-back loop saturates the bucket
    after roughly a dozen calls. The frozen harness re-raises on ``OpenAIError``,
    which is correct for a paid benchmark run -- a silent retry there could mask a
    real fault -- so the retry is installed here rather than in ``llm_call.py``.

    This does not change what is measured. A retry re-sends a byte-identical
    request with the same seed; only the wall-clock spacing differs. Anything that
    is not a rate limit still propagates immediately.
    """
    import random
    import re
    import time

    from openai import RateLimitError

    inner = postretrieval.call_model

    def wrapper(*a, **kw):
        for attempt in range(max_attempts):
            try:
                return inner(*a, **kw)
            except RateLimitError as exc:
                msg = str(exc)
                # a genuine out-of-credit 429 is NOT transient -- fail loudly
                if "insufficient_quota" in msg or "credit_balance_exhausted" in msg:
                    raise
                if attempt == max_attempts - 1:
                    raise
                m = re.search(r"try again in ([0-9.]+)s", msg)
                # provider hint when offered, else exponential backoff; jitter so
                # retries do not re-collide in lockstep
                delay = float(m.group(1)) + 0.5 if m else min(2 ** attempt, 30)
                time.sleep(delay + random.uniform(0, 0.75))
        raise RuntimeError("unreachable")

    postretrieval.call_model = wrapper


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def baseline_rows(item_ids: list[str]) -> pd.DataFrame:
    """Row-zero baseline, read from the frozen run. No calls."""
    df = pd.read_csv(
        BASELINE_RUN / "postretrieval_raw.csv",
        usecols=[
            "trial_idx", "task_id", "task_type", "format", "condition", "model",
            "pred_label", "grade_gold_label", "prompt_tokens", "completion_tokens",
        ],
        low_memory=False,
    )
    return df[
        (df.task_id.isin(item_ids))
        & (df.format.isin(FORMATS))
        & (df.condition.isin(CONDITIONS))
        & (df.model.isin(MODELS))
    ].copy()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and the costed projection; make no calls")
    ap.add_argument("--models", nargs="+", choices=MODELS, default=MODELS,
                    help="subset of the design's models to run in THIS invocation. The "
                         "design is unchanged; the checkpoint is keyed by model, so a "
                         "later invocation fills the remaining arms without re-billing "
                         "the ones already on disk.")
    args = ap.parse_args()
    models = [m for m in MODELS if m in args.models]  # keep design order

    tasks = load_tasks(Path("experiment/benchmark/tasks_60.yaml"))
    items = select_items(tasks)
    item_ids = [t.task_id for t in items]
    per_model = len(items) * len(FORMATS) * len(POSTRETRIEVAL_SEEDS)
    n_calls = per_model * len(models)

    print(f"probe: {PROBE_ID}")
    print(f"prompt: {PROBE_PROMPT.name}  sha256={_sha256(PROBE_PROMPT)[:16]}…")
    print(f"items ({len(items)}): {', '.join(item_ids)}")
    by_gold: dict[str, int] = {}
    for t in items:
        by_gold[t.gold_label] = by_gold.get(t.gold_label, 0) + 1
    print(f"  gold split: {by_gold}")
    print(f"formats: {FORMATS}")
    print(f"models (design):    {MODELS}")
    print(f"models (this run):  {models}")
    if models != MODELS:
        missing = [m for m in MODELS if m not in models]
        print(f"  PARTIAL RUN — not run here: {missing}")
        print("  manifest will record probe_complete=false; resume fills these in.")
    print(f"conditions: {CONDITIONS}  seeds: {POSTRETRIEVAL_SEEDS}")
    print(f"calls this run: {n_calls}  (full design: {per_model * len(MODELS)})")

    base = baseline_rows(item_ids)
    print(f"\nrow-zero baseline from frozen run: {len(base)} rows (0 new calls)")
    if not base.empty:
        proj = base.groupby("model")[["prompt_tokens", "completion_tokens"]].mean()
        total = 0.0
        for model, r in proj.iterrows():
            if model not in models:
                continue
            usd = compute_cost(
                model, int(r.prompt_tokens * per_model), int(r.completion_tokens * per_model)
            )
            total += usd
            print(f"  projected {model:32s} {per_model:4d} calls  ${usd:.2f}")
        print(f"  projected THIS RUN (uncached, snapshot {PRICING_SNAPSHOT_DATE}): ${total:.2f}")

    if args.dry_run:
        print("\n--dry-run: no calls made.")
        return

    # --- prompt swap, this process only ------------------------------------
    frozen_text = postretrieval._system_prompt("verification")
    probe_text = PROBE_PROMPT.read_text(encoding="utf-8")
    assert probe_text != frozen_text, "probe prompt is identical to the frozen prompt"

    SYSTEM_PROMPTS["verification"] = PROBE_PROMPT
    postretrieval._system_prompt.cache_clear()  # drop the frozen text from the lru_cache
    assert postretrieval._system_prompt("verification") == probe_text

    install_rate_limit_retry()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rows, scored_rows = run_postretrieval(
        items,
        FORMATS,
        CONDITIONS,
        models,
        checkpoint_path=OUT_DIR / "postretrieval_checkpoint.jsonl",
    )

    # every row must carry the probe prompt, not the frozen one
    bad = {r.get("system_prompt") for r in raw_rows} - {PROBE_PROMPT.name}
    assert not bad, f"rows written under unexpected prompt(s): {bad}"

    write_csv(raw_rows, OUT_DIR / "postretrieval_raw.csv")
    write_csv(scored_rows, OUT_DIR / "postretrieval_scored.csv")

    manifest = {
        "probe_id": PROBE_ID,
        "probe_label": "B2 — explicit open-world statement",
        "is_diagnostic_substudy": True,
        "never_pool_with": "postretrieval-combined-15-18",
        "hypothesis_tested": "H2 (prompt-induced suppression of `undetermined`)",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "task_file": "experiment/benchmark/tasks_60.yaml",
        "task_file_sha256": _sha256(Path("experiment/benchmark/tasks_60.yaml")),
        "task_file_read_only": True,
        "system_prompt_file": PROBE_PROMPT.name,
        "system_prompt_sha256": _sha256(PROBE_PROMPT),
        "frozen_prompt_file": "verification_system_v1.txt",
        "frozen_prompt_sha256": _sha256(PROMPTS_DIR / "verification_system_v1.txt"),
        "item_ids": item_ids,
        "item_gold_split": by_gold,
        "formats": FORMATS,
        # The design is always all three arms. ``models_run`` is what THIS invocation
        # produced; a partial manifest that claimed the full design would misdescribe
        # the file next to it. ``probe_complete`` gates any reading of the result.
        "models_design": MODELS,
        "models_run": sorted({r["model"] for r in raw_rows}),
        "probe_complete": sorted({r["model"] for r in raw_rows}) == sorted(MODELS),
        "models_not_run": [m for m in MODELS if m not in {r["model"] for r in raw_rows}],
        "conditions": CONDITIONS,
        "trial_seed_map": dict(enumerate(POSTRETRIEVAL_SEEDS)),
        "n_calls": len(raw_rows),
        "baseline_source": str(BASELINE_RUN.name),
        "baseline_rows": int(len(base)),
        "pricing_snapshot_date": PRICING_SNAPSHOT_DATE,
        "cost": summarise_cost(raw_rows),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {len(raw_rows)} rows -> {OUT_DIR}")


if __name__ == "__main__":
    main()
