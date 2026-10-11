"""Pricing helpers for post-retrieval cost analysis.

Prices are standard OpenAI API text-token rates per 1M tokens, as listed on
the OpenAI pricing page on the snapshot date below:
https://platform.openai.com/docs/pricing

The helper derives USD cost from recorded tokens at analysis time so raw trial
records remain valid if pricing changes later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRICING_SNAPSHOT_DATE = "2026-06-07"
PRICING_SOURCE_URL = "https://platform.openai.com/docs/pricing"


@dataclass(frozen=True)
class TokenPrice:
    input_per_million: float
    output_per_million: float


MODEL_PRICES: dict[str, TokenPrice] = {
    "gpt-4o": TokenPrice(input_per_million=2.50, output_per_million=10.00),
    "gpt-4o-2024-11-20": TokenPrice(input_per_million=2.50, output_per_million=10.00),
    "gpt-4o-2024-08-06": TokenPrice(input_per_million=2.50, output_per_million=10.00),
    "gpt-4o-mini": TokenPrice(input_per_million=0.15, output_per_million=0.60),
    "gpt-4o-mini-2024-07-18": TokenPrice(input_per_million=0.15, output_per_million=0.60),
    # The pricing page lists this older dated snapshot separately.
    "gpt-4o-2024-05-13": TokenPrice(input_per_million=5.00, output_per_million=15.00),
    # Local inference has zero API cost, but token counts still matter.
    "llama-3.1-8b": TokenPrice(input_per_million=0.0, output_per_million=0.0),
    "llama3.1-8b": TokenPrice(input_per_million=0.0, output_per_million=0.0),
    "meta-llama-3.1-8b-instruct": TokenPrice(
        input_per_million=0.0, output_per_million=0.0
    ),
}


def resolve_model_price(model: str) -> TokenPrice:
    """Return pricing for a requested or returned model string."""
    normalized = model.strip().lower()
    if normalized in MODEL_PRICES:
        return MODEL_PRICES[normalized]
    if normalized.startswith("gpt-4o-mini-"):
        return MODEL_PRICES["gpt-4o-mini"]
    if normalized.startswith("gpt-4o-"):
        return MODEL_PRICES["gpt-4o"]
    if "llama" in normalized and "3.1" in normalized and "8b" in normalized:
        return MODEL_PRICES["llama-3.1-8b"]
    # Arms adopted AFTER the 2026-06-07 snapshot (the Anthropic arm, D2) are priced
    # from the later cache-aware table rather than being back-dated into
    # MODEL_PRICES. Writing them into the pinned snapshot would silently restate
    # what that date covers, and every existing manifest cites it; delegating here
    # leaves those manifests reproducing byte-identically while still giving the
    # newer arm a base rate. The cache columns are dropped on purpose -- this
    # function is the UNCACHED path by contract.
    try:
        cached = resolve_cached_model_price(model)
    except KeyError:
        pass
    else:
        return TokenPrice(
            input_per_million=cached.input_per_million,
            output_per_million=cached.output_per_million,
        )
    raise KeyError(
        f"No pricing configured for model {model!r}; update experiment/pricing.py"
    )


def _tokens(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def compute_cost(
    model: str,
    prompt_tokens: int | str | None,
    completion_tokens: int | str | None,
) -> float:
    """Compute USD cost from recorded token counts."""
    price = resolve_model_price(model)
    return (
        (_tokens(prompt_tokens) * price.input_per_million)
        + (_tokens(completion_tokens) * price.output_per_million)
    ) / 1_000_000


def summarise_cost(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise per-call token counts and derived cost for a trial manifest."""
    total_prompt_tokens = sum(_tokens(row.get("prompt_tokens")) for row in rows)
    total_completion_tokens = sum(_tokens(row.get("completion_tokens")) for row in rows)
    total_tokens = sum(_tokens(row.get("total_tokens")) for row in rows)
    total_cost = sum(
        compute_cost(
            str(row.get("model_returned") or row.get("model") or ""),
            row.get("prompt_tokens"),
            row.get("completion_tokens"),
        )
        for row in rows
    )
    return {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_calls": len(rows),
        "cost_usd_at_pricing_date": round(total_cost, 6),
        "pricing_snapshot_date": PRICING_SNAPSHOT_DATE,
        "pricing_source_url": PRICING_SOURCE_URL,
    }


# ---------------------------------------------------------------------------
# Whole-context projection (Spec 05). ADDITIVE ONLY.
#
# Nothing below alters ``MODEL_PRICES``, ``PRICING_SNAPSHOT_DATE``, or any
# function above: the 2026-06-07 snapshot stays pinned so every existing trial
# manifest keeps reproducing byte-identically. The projection needs two things
# that snapshot does not carry -- cached-input rates and the Anthropic arm --
# so they live in a SECOND, separately dated snapshot below.
#
# Verified 2026-08-13 against the provider pricing pages: the gpt-4o and
# gpt-4o-mini base rates are UNCHANGED from the 2026-06-07 snapshot (2.50/10.00
# and 0.15/0.60). Only the cache columns are new information.
# ---------------------------------------------------------------------------
CACHE_PRICING_SNAPSHOT_DATE = "2026-08-13"
CACHE_PRICING_SOURCE_URLS = {
    "openai": "https://developers.openai.com/api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
}


@dataclass(frozen=True)
class CachedTokenPrice:
    """Per-1M-token rates including the prefix-cache columns.

    ``cache_write_per_million`` is the cost of the FIRST call that stores the
    prefix. OpenAI charges no write premium on the gpt-4o family (it equals the
    base input rate); Anthropic charges 1.25x (5m TTL) or 2x (1h TTL).
    ``cache_read_per_million`` is what a subsequent hit costs.
    """

    input_per_million: float
    output_per_million: float
    cache_write_per_million: float
    cache_read_per_million: float


# Rates per 1M tokens, USD, as published on the snapshot date above.
#
# Note the cached-input rate is NOT a single multiplier across OpenAI: the
# gpt-4o family gets 0.5x (50% off), while GPT-5.x gets 0.1x (90% off). The
# "90%" headline in OpenAI's caching guide does not apply to our pinned arms.
CACHE_MODEL_PRICES: dict[str, CachedTokenPrice] = {
    # OpenAI gpt-4o family: caching automatic, no write premium, 0.5x read.
    "gpt-4o-2024-11-20": CachedTokenPrice(2.50, 10.00, 2.50, 1.25),
    "gpt-4o-mini-2024-07-18": CachedTokenPrice(0.15, 0.60, 0.15, 0.075),
    # UNADOPTED-BUT-BILLED. gpt-5.5 is not a study arm -- it was exercised by the
    # WI-10 capability probe, whose calls live outside results/*/ and so never
    # reach summarise_cost. Its rate is recorded here ONLY so reconciliation
    # against the provider's usage export can account for that spend. Adding it
    # to MODEL_PRICES would put an unadopted arm inside the pinned 2026-06-07
    # snapshot, so it is deliberately kept out of there. 0.1x cached read.
    "gpt-5.5": CachedTokenPrice(5.00, 30.00, 5.00, 0.50),
    # Anthropic: explicit cache_control breakpoints; 5-minute TTL assumed.
    "claude-sonnet-4-5-20250929": CachedTokenPrice(3.00, 15.00, 3.75, 0.30),
    # Local inference: no API cost, but tokens still bound context feasibility.
    "llama3.1:8b-instruct-q8_0": CachedTokenPrice(0.0, 0.0, 0.0, 0.0),
}

# Arms that appear in billing but are NOT study arms. Kept explicit so a
# reconciliation can separate "spend the study incurred" from "spend the study
# will report", rather than silently folding probe spend into the trial ledger.
UNADOPTED_BUT_BILLED = frozenset({"gpt-5.5"})


def resolve_cached_model_price(model: str) -> CachedTokenPrice:
    """Return cache-aware pricing for a model string (exact or prefix match)."""
    normalized = model.strip().lower()
    if normalized in CACHE_MODEL_PRICES:
        return CACHE_MODEL_PRICES[normalized]
    if normalized.startswith("gpt-4o-mini"):
        return CACHE_MODEL_PRICES["gpt-4o-mini-2024-07-18"]
    if normalized.startswith("gpt-4o"):
        return CACHE_MODEL_PRICES["gpt-4o-2024-11-20"]
    if normalized.startswith("claude-sonnet-4-5"):
        return CACHE_MODEL_PRICES["claude-sonnet-4-5-20250929"]
    if "llama" in normalized:
        return CACHE_MODEL_PRICES["llama3.1:8b-instruct-q8_0"]
    raise KeyError(
        f"No cache pricing configured for model {model!r}; "
        f"update CACHE_MODEL_PRICES in experiment/pricing.py"
    )


def compute_cost_cache_aware(
    model: str,
    prompt_tokens: int | str | None,
    completion_tokens: int | str | None,
    cached_prompt_tokens: int | str | None = None,
) -> float:
    """USD cost that prices the cached share of the prompt at the cache-read rate.

    ``compute_cost`` above bills every input token at the uncached rate, which
    overstates real spend wherever a prefix repeated (the study's trials differ
    only by seed, so trials 2 and 3 of each cell re-send an identical prefix).
    That function is left untouched so existing manifests still reproduce.

    ``cached_prompt_tokens`` is the ``cached_prompt_tokens`` column written by
    ``postretrieval.run_one``. It is ``None`` for every row recorded before that
    column existed and for providers that do not report it; in that case this
    falls back to the uncached rate and the result equals ``compute_cost``.
    Historical rows therefore CANNOT be corrected by this function -- the cached
    count was never written and is unrecoverable. Use the provider's usage
    export for spend already incurred.
    """
    price = resolve_cached_model_price(model)
    total_in = _tokens(prompt_tokens)
    cached = _tokens(cached_prompt_tokens)
    cached = max(0, min(cached, total_in))
    uncached = total_in - cached
    return (
        uncached * price.input_per_million
        + cached * price.cache_read_per_million
        + _tokens(completion_tokens) * price.output_per_million
    ) / 1_000_000


def summarise_cost_cache_aware(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Cache-aware counterpart to ``summarise_cost``.

    Reports the naive total alongside, so the gap between them is visible rather
    than silently absorbed.
    """
    naive = 0.0
    aware = 0.0
    cached_total = 0
    rows_with_cache_data = 0
    for row in rows:
        model = str(row.get("model_returned") or row.get("model") or "")
        naive += compute_cost(model, row.get("prompt_tokens"), row.get("completion_tokens"))
        cached = row.get("cached_prompt_tokens")
        if cached not in (None, ""):
            rows_with_cache_data += 1
            cached_total += _tokens(cached)
        aware += compute_cost_cache_aware(
            model, row.get("prompt_tokens"), row.get("completion_tokens"), cached
        )
    return {
        "total_calls": len(rows),
        "rows_with_cache_data": rows_with_cache_data,
        "total_cached_prompt_tokens": cached_total,
        "cost_usd_naive": round(naive, 6),
        "cost_usd_cache_aware": round(aware, 6),
        "cache_saving_usd": round(naive - aware, 6),
        "pricing_snapshot_date": CACHE_PRICING_SNAPSHOT_DATE,
    }


def project_whole_context_cell(
    model: str,
    *,
    corpus_tokens: int,
    overhead_tokens: int,
    output_tokens: float,
    n_calls: int,
    caching: bool,
    cache_hit_fraction: float = 1.0,
) -> dict[str, Any]:
    """Project USD cost for ONE (format, model) whole-context cell.

    A cell is ``n_calls`` requests that all inject the SAME corpus and differ
    only in the task text, so the corpus is the shared cacheable prefix.

    ``overhead_tokens``  system prompt + task input + JSON scaffolding: the part
                         of the prompt that is NOT the shared corpus prefix, and
                         is therefore billed at the full input rate every call.
    ``cache_hit_fraction`` share of the post-first calls that actually hit cache.
                         Kept explicit rather than assumed to be 1.0 because the
                         W2 probe observed a real cold-start miss on gpt-4o: the
                         provider caches are best-effort, not contractual.
    """
    if n_calls <= 0:
        raise ValueError("n_calls must be positive")
    if not 0.0 <= cache_hit_fraction <= 1.0:
        raise ValueError("cache_hit_fraction must be in [0, 1]")

    price = resolve_cached_model_price(model)
    out_cost = (output_tokens * n_calls * price.output_per_million) / 1_000_000
    overhead_cost = (overhead_tokens * n_calls * price.input_per_million) / 1_000_000

    if not caching:
        corpus_cost = (corpus_tokens * n_calls * price.input_per_million) / 1_000_000
        n_hits = 0
    else:
        # Call 1 writes the prefix; the remaining calls hit it (or miss and pay
        # the write rate again, per cache_hit_fraction).
        followers = n_calls - 1
        n_hits = followers * cache_hit_fraction
        n_misses = followers - n_hits
        corpus_cost = (
            corpus_tokens
            * (
                price.cache_write_per_million * (1 + n_misses)
                + price.cache_read_per_million * n_hits
            )
        ) / 1_000_000

    total = corpus_cost + overhead_cost + out_cost
    return {
        "model": model,
        "n_calls": n_calls,
        "caching": caching,
        "corpus_tokens": corpus_tokens,
        "cache_hits": round(n_hits, 2),
        "corpus_cost_usd": round(corpus_cost, 6),
        "overhead_cost_usd": round(overhead_cost, 6),
        "output_cost_usd": round(out_cost, 6),
        "total_usd": round(total, 6),
        "pricing_snapshot_date": CACHE_PRICING_SNAPSHOT_DATE,
    }


def project_whole_context_scenario(
    *,
    models: list[str],
    corpus_tokens_by_format: dict[str, int],
    overhead_tokens: int,
    output_tokens: float,
    n_tasks: int,
    n_trials: int,
    caching: bool,
    cache_hit_fraction: float = 1.0,
    usd_to_aud: float | None = None,
) -> dict[str, Any]:
    """Project a full whole-context scenario across formats x models.

    ``corpus_tokens_by_format`` is the EXACT per-format token count (from the
    W1 measurement), so a scenario is priced on the formats actually selected
    rather than on an average that hides the 2x spread between them.
    """
    n_calls = n_tasks * n_trials
    cells = [
        project_whole_context_cell(
            model,
            corpus_tokens=tokens,
            overhead_tokens=overhead_tokens,
            output_tokens=output_tokens,
            n_calls=n_calls,
            caching=caching,
            cache_hit_fraction=cache_hit_fraction,
        )
        for model in models
        for tokens in corpus_tokens_by_format.values()
    ]
    total_usd = sum(c["total_usd"] for c in cells)
    out: dict[str, Any] = {
        "formats": sorted(corpus_tokens_by_format),
        "models": list(models),
        "n_tasks": n_tasks,
        "n_trials": n_trials,
        "caching": caching,
        "calls_per_cell": n_calls,
        "total_calls": n_calls * len(cells),
        "total_usd": round(total_usd, 4),
        "cells": cells,
        "pricing_snapshot_date": CACHE_PRICING_SNAPSHOT_DATE,
    }
    if usd_to_aud is not None:
        out["total_aud"] = round(total_usd * usd_to_aud, 4)
        out["usd_to_aud"] = usd_to_aud
    return out
