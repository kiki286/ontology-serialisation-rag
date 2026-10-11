"""RQ2: post-retrieval task execution and grading.

For each (task, format, condition, model, trial) it assembles the four per-call inputs
(system prompt, context block, task input, JSON response instruction), calls the
model, parses the structured response, and grades it. Returns per-call raw rows
plus scored rows reporting mean/std across trials grouped by
(task_id, format, condition, model).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from statistics import mean, median, stdev

from experiment.config import (
    FLOOR_FORMAT_SENTINEL,
    FORMATS,
    ANTHROPIC_CACHE_CORPUS,
    ORACLE_PAD_SEED,
    POSTRETRIEVAL_SEEDS,
    RETRIEVAL_K,
    SYSTEM_PROMPTS,
    is_floor_condition,
)
from experiment.context_block import assemble_context_block
from experiment import corpus_index
from experiment.coverage import (
    compute_coverage,
    context_chunk_ids_from_chunks,
    coverage_columns,
)
from experiment.grading import (
    SLOT_FIELDS,
    grade_slot_filling,
    grade_slot_filling_missing,
    grade_verification,
)
from experiment.llm_call import call_model
from experiment.schemas import ParseError, Task, parse_response


@lru_cache(maxsize=None)
def _system_prompt(task_type: str) -> str:
    return SYSTEM_PROMPTS[task_type].read_text(encoding="utf-8")


def _task_input(task: Task) -> str:
    if task.task_type == "verification":
        return f"Statement: {task.statement.strip()}"
    return f"Scenario: {task.scenario.strip()}"


def build_user_content(
    task: Task, context_block: str, condition: str = "oracle"
) -> str:
    """Context block + the task input (statement or scenario).

    The two floor conditions (WI2) differ ONLY in the scaffolding:
      * ``no_context``    - the task input alone; the "Ontology content:" header is
        omitted entirely, so the prompt never mentions a corpus.
      * ``empty_context`` - the header is present with an empty body, i.e. exactly
        the scaffolding the context-bearing conditions use, minus the chunks.
    Keeping the difference to the scaffolding alone is what makes the contrast
    interpretable: any score gap between them is attributable to the empty block.
    """
    task_input = _task_input(task)
    if condition == "no_context":
        return task_input
    return "".join(build_user_content_segments(task, context_block, condition))


def build_user_content_segments(
    task: Task, context_block: str, condition: str = "oracle"
) -> list[str]:
    """The user prompt split at the corpus boundary; ``"".join(...)`` is the prompt.

    The Anthropic arm needs the corpus in its own content block so it can carry a
    ``cache_control`` breakpoint, which a single string cannot express. Splitting
    here -- rather than rebuilding a separate Anthropic prompt -- is what keeps the
    assembled text byte-identical across arms: ``build_user_content`` is defined AS
    the join of these segments, so the two cannot drift apart. Segment 0 is the
    corpus (the cacheable prefix); segment 1 is the per-task input.
    """
    task_input = _task_input(task)
    if condition == "no_context":
        return [task_input]
    return [f"Ontology content:\n\n{context_block}", f"\n\n{task_input}"]


def task_gold_union(task: Task) -> list[str]:
    """The task's gold entity ids across all formats (never eligible as padding)."""
    union: set[str] = set()
    for fmt in FORMATS:
        union.update(task.gold_chunks_for(fmt))
    return sorted(union)


def task_padding_ids(
    task: Task, corpus_format: str, k: int, *, pad_seed: int = ORACLE_PAD_SEED
) -> list[str]:
    """Padding entity ids for a (task, format) under the random strategy.

    Sampled once per task (format-neutral ordering); each format takes the same prefix
    sized to reach k, so the padding entity SET is identical across formats.
    """
    need = k - len(task.gold_chunks_for(corpus_format))
    if need <= 0:
        return []
    ordering = corpus_index.padding_pool_for_task(
        task.task_id, task_gold_union(task), seed=pad_seed
    )
    return ordering[:need]


def _cited_chunk_ids(pred) -> list[str]:
    """Non-empty chunk citations in a parsed slot-filling response (else empty)."""
    citations = getattr(pred, "supporting_chunks", None)
    if citations is None:
        return []
    values = [citations.cls, citations.prop, citations.intermediate_node]
    return [str(v).strip() for v in values if v is not None and str(v).strip()]


def _context_chunks(
    task: Task,
    corpus_format: str,
    condition: str,
    k: int,
    *,
    pad_strategy: str = "random",
    pad_seed: int = ORACLE_PAD_SEED,
) -> tuple[list[tuple[str, str]], dict]:
    """Return (chunks, context_meta). ``context_meta`` records padding provenance."""
    meta = {"n_pad_chunks": 0, "oracle_over_k": False, "pad_strategy": None}

    # Floor conditions (WI2): no corpus is consulted at all. Returning an empty
    # chunk list here is what makes the floor format-independent — no loader, no
    # index, and no prefix block is touched.
    if is_floor_condition(condition):
        return [], meta

    if condition == "oracle":
        return corpus_index.get_oracle_chunks(
            corpus_format, task.gold_chunks_for(corpus_format)
        ), meta

    if condition == "oracle_padded":
        chunks = corpus_index.get_oracle_chunks(
            corpus_format, task.gold_chunks_for(corpus_format)
        )
        if len(chunks) > k:
            # Never truncate: dropping gold defeats the condition. Record the over-k
            # discrepancy and leave the oversize oracle set intact (WI7).
            meta["oracle_over_k"] = True
            return chunks, meta
        need = k - len(chunks)
        if need > 0:
            if pad_strategy == "random":
                pad = corpus_index.get_oracle_chunks(
                    corpus_format, task_padding_ids(task, corpus_format, k, pad_seed=pad_seed)
                )
            else:  # "retrieved": per-format, not entity-controlled
                existing = {cid for cid, _ in chunks}
                pad = corpus_index.get_padding_chunks(
                    corpus_format, existing, need, query=task.query
                )
            chunks = chunks + pad
            meta["n_pad_chunks"] = len(pad)
            meta["pad_strategy"] = pad_strategy
        return chunks, meta

    if condition == "whole_context":
        # Whole-context is a source-file condition, not a k=infinity chunk
        # condition. The caller reads the serialisation verbatim below.
        return [], meta

    if condition == "retrieved":
        hits = corpus_index.retrieve(corpus_format, task.query, k=k)
        return [(h.metadata.get("entity_id") or "", h.page_content) for h in hits], meta

    raise ValueError(f"unknown condition {condition!r}")


def run_one(
    task: Task,
    corpus_format: str,
    condition: str,
    model: str,
    k: int = RETRIEVAL_K,
    *,
    trial_idx: int | None = None,
    seed: int | None = None,
    pad_strategy: str = "random",
    pad_seed: int = ORACLE_PAD_SEED,
) -> tuple[dict, dict]:
    """Run a single call; return (raw_row, grade_item)."""
    floor = is_floor_condition(condition)
    if floor:
        # The floor has no format arm; normalise whatever the caller passed so the
        # sentinel is the single value that ever reaches the ``format`` column.
        corpus_format = FLOOR_FORMAT_SENTINEL

    chunks, ctx_meta = _context_chunks(
        task,
        corpus_format,
        condition,
        k,
        pad_strategy=pad_strategy,
        pad_seed=pad_seed,
    )
    # No corpus => no prefix block and no chunks; assemble_context_block would
    # otherwise need a real format to read a prefix block from.
    if condition == "whole_context":
        context = corpus_index.get_source_file_context(corpus_format)
    else:
        context = "" if floor else assemble_context_block(corpus_format, chunks)
    system = _system_prompt(task.task_type)
    segments = build_user_content_segments(task, context, condition)
    user = "".join(segments)
    call_kwargs = {
        "condition": condition,
        "task_type": task.task_type,
        "user_segments": segments,
        "cache_corpus": ANTHROPIC_CACHE_CORPUS,
    }

    if seed is None:
        result = call_model(model, system, user, **call_kwargs)
    else:
        result = call_model(model, system, user, seed=seed, **call_kwargs)
    raw = result["content"]
    usage = result.get("usage") or {}

    context_chunk_ids = context_chunk_ids_from_chunks(chunks)
    row: dict = {
        "trial_idx": trial_idx,
        "task_id": task.task_id,
        "task_type": task.task_type,
        # carry the answer taxonomy + query wording onto every row so they can be
        # crossed with results directly in the CSV
        "reasoning_type": task.reasoning_type,
        "query_source": task.query_source,
        "mechanism": task.mechanism,
        "format": corpus_format,
        "condition": condition,
        "model": model,
        "provider": result.get("provider"),
        "model_returned": result.get("model_returned") or result.get("model"),
        "system_prompt": SYSTEM_PROMPTS[task.task_type].name,
        "n_context_chunks": len(chunks),
        "context_construction": (
            "source_file_verbatim" if condition == "whole_context" else "chunk_block"
        ),
        # length + membership covariates, recorded on every row.
        "context_char_len": len(context),
        "context_chunk_ids": context_chunk_ids,
        "n_pad_chunks": ctx_meta["n_pad_chunks"],
        "oracle_over_k": ctx_meta["oracle_over_k"],
        "pad_strategy": ctx_meta["pad_strategy"],
        "finish_reason": result.get("finish_reason"),
        "system_fingerprint": result.get("system_fingerprint"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        # Cache accounting. Without this the ledger bills every input token at the
        # uncached rate; reconciliation against the provider's usage export showed
        # that overstates gpt-4o-family spend by ~24%, because trials differ only by
        # seed and so re-send byte-identical prefixes. The value was previously
        # present in ``usage`` but discarded here, making the error unrecoverable
        # after the fact. Null on providers that do not report it (Ollama).
        # OpenAI nests this under prompt_tokens_details; the Anthropic branch
        # normalises cache_read_input_tokens to a top-level "cached_tokens".
        # Null on Ollama, which reports no cache accounting at all.
        "cached_prompt_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        )
        if usage.get("prompt_tokens_details")
        else usage.get("cached_tokens"),
        "raw_response": raw,
        "user_content": user,
    }
    # Coverage asks "did a licensing chunk reach the context?". With no context the
    # question is undefined, not answered-in-the-negative, so every coverage column
    # is emitted as null rather than 0 — a 0 would read as a real miss and pollute
    # any aggregate that averages over conditions (WI2).
    if condition == "whole_context":
        # The source file contains the complete serialisation by construction;
        # chunk-level coverage is therefore defined as complete for this arm.
        row.update({col: 1.0 for col in coverage_columns()})
    elif floor:
        row.update({col: None for col in coverage_columns()})
    else:
        row.update(compute_coverage(task, context_chunk_ids))

    try:
        pred = parse_response(task.task_type, raw, allow_missing_citations=floor)
        row["parse_ok"] = True
        row["parse_error"] = ""
    except ParseError as exc:
        pred = None
        row["parse_ok"] = False
        row["parse_error"] = str(exc)

    if task.task_type == "verification":
        if pred is not None:
            grade = grade_verification(task, pred)
            row["pred_label"] = pred.label
        else:
            grade = {"gold_label": task.gold_label, "pred_label": None, "correct": 0}
            row["pred_label"] = None
    else:
        if pred is not None:
            grade = grade_slot_filling(task, pred)
            row.update(
                {
                    "pred_class": pred.cls,
                    "pred_property": pred.prop,
                    "pred_intermediate_node": pred.intermediate_node,
                    "pred_support_class": pred.supporting_chunks.cls,
                    "pred_support_property": pred.supporting_chunks.prop,
                    "pred_support_intermediate": pred.supporting_chunks.intermediate_node,
                }
            )
        else:
            grade = grade_slot_filling_missing(task)

    # WI2: under a floor condition the context is empty, so every chunk citation is
    # fabricated by definition. Recorded per row (never fatal) and counted in the
    # diagnostics report. Null outside the floor, where citing IS the expected
    # behaviour and correctness is already judged by the support_* grades. Also null
    # on verification rows, whose response schema has no citation field at all — the
    # question is undefined there, and a 0 would dilute the hallucination rate.
    cites_applicable = floor and task.task_type == "slot_filling"
    row["citation_hallucinated"] = (
        int(bool(_cited_chunk_ids(pred))) if cites_applicable else None
    )
    row["hallucinated_citation_ids"] = (
        _cited_chunk_ids(pred) if cites_applicable else None
    )

    for key, value in grade.items():
        row[f"grade_{key}"] = value
    return row, grade


def _sample_std(values: list[float]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def _metrics_from_raw_row(row: dict) -> dict[str, float]:
    if row["task_type"] == "verification":
        return {
            "accuracy": float(row.get("grade_correct") or 0),
            "answered": float(row.get("grade_answered") or 0),
            "selective_correct": float(row.get("grade_selective_correct") or 0),
            "parse_errors": 0.0 if row.get("parse_ok") else 1.0,
        }
    metrics = {
        "exact_match_rate": float(row.get("grade_exact_match") or 0),
        "mean_partial_credit": float(row.get("grade_partial_credit") or 0.0),
    }
    # Excluded (N/A) fields are absent from the per-field means, never counted as 0.
    for field in SLOT_FIELDS:
        value = row.get(f"grade_{field}")
        if value is None or value == "":
            continue
        metrics[f"field_accuracy_{field}"] = float(value)
    return metrics


def _summarise_raw_rows(raw_rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for row in raw_rows:
        key = (row["task_id"], row["format"], row["condition"], row["model"])
        groups.setdefault(key, []).append(row)

    scored: list[dict] = []
    for (task_id, corpus_format, condition, model), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r: r["trial_idx"])
        trial_values: dict[str, list[float]] = {}
        for row in rows:
            for metric, value in _metrics_from_raw_row(row).items():
                trial_values.setdefault(metric, []).append(value)

        summary: dict = {
            "task_id": task_id,
            "task_type": rows[0]["task_type"],
            "reasoning_type": rows[0].get("reasoning_type"),
            "query_source": rows[0].get("query_source"),
            "mechanism": rows[0].get("mechanism"),
            "format": corpus_format,
            "condition": condition,
            "model": model,
            "n_trials": len(rows),
            "trial_indices": [row["trial_idx"] for row in rows],
        }
        for metric, values in trial_values.items():
            summary[f"{metric}_mean"] = mean(values)
            summary[f"{metric}_std"] = _sample_std(values)
        if rows[0]["task_type"] == "verification":
            answered = trial_values.get("answered", [])
            selective_correct = trial_values.get("selective_correct", [])
            summary["coverage_mean"] = mean(answered) if answered else 0.0
            summary["accuracy_on_answered_mean"] = (
                sum(selective_correct) / sum(answered) if sum(answered) else 0.0
            )

        summary["trial_values"] = trial_values
        scored.append(summary)
    return scored


def summarise_variance(scored_rows: list[dict]) -> list[dict]:
    """Summarise trial-to-trial variability across post-retrieval cells."""
    std_groups: dict[str, list[tuple[float, dict]]] = {}
    for row in scored_rows:
        for key, value in row.items():
            if not key.endswith("_std") or not isinstance(value, (int, float)):
                continue
            metric = key.removesuffix("_std")
            std_groups.setdefault(metric, []).append((float(value), row))

    out: list[dict] = []
    for metric, values_and_rows in sorted(std_groups.items()):
        values = [value for value, _row in values_and_rows]
        max_std, max_row = max(values_and_rows, key=lambda item: item[0])
        out.append(
            {
                "metric": metric,
                "n_cells": len(values),
                "median_std": median(values),
                "mean_std": mean(values),
                "max_std": max_std,
                "nonzero_std_cells": sum(1 for value in values if value > 0),
                "max_std_task_id": max_row["task_id"],
                "max_std_task_type": max_row["task_type"],
                "max_std_format": max_row["format"],
                "max_std_condition": max_row["condition"],
                "max_std_model": max_row["model"],
            }
        )
    return out


CHECKPOINT_NAME = "postretrieval_checkpoint.jsonl"


def _cell_key(row: dict) -> tuple:
    """Identity of one call. Matches the arguments ``run_one`` is pure in.

    ``trial_idx`` is included because it selects the seed; the other four are the
    grouping key ``_summarise_raw_rows`` already uses. Nothing derived from the
    RESPONSE is part of the key, so a replayed row is indistinguishable from a
    freshly-called one.
    """
    return (
        row["task_id"],
        row["format"],
        row["condition"],
        row["model"],
        row["trial_idx"],
    )


def load_checkpoint(path: Path) -> dict[tuple, dict]:
    """Read completed rows from a checkpoint, keyed by cell.

    A truncated final line is dropped rather than raising: the process may have
    been killed mid-write, and one lost row is re-called on resume. Later
    duplicates of a key win, so a row re-called after a partial write is the one
    that survives.
    """
    if not path.exists():
        return {}
    done: dict[tuple, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[_cell_key(row)] = row
    return done


def _append_checkpoint(path: Path | None, row: dict) -> None:
    """Append one row and flush it to the OS before the next call is made."""
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
        handle.flush()


def run_postretrieval(
    tasks: list[Task],
    formats: list[str],
    conditions: list[str],
    models: list[str],
    k: int = RETRIEVAL_K,
    seeds: list[int] | None = None,
    *,
    pad_strategy: str = "random",
    pad_seed: int = ORACLE_PAD_SEED,
    checkpoint_path: Path | None = None,
) -> tuple[list[dict], list[dict]]:
    """Run every cell, optionally checkpointing each row as it completes.

    ``checkpoint_path`` makes the loop crash-tolerant: each row is appended and
    flushed the moment its call returns, and any row already present for a cell is
    replayed from disk instead of being re-called. This is what stops one failure
    in the slow local arm from discarding a night of paid API calls (the run that
    prompted it died on an Ollama read timeout in cell 4 of 56, losing ~540 billed
    calls that were held only in memory).

    Resume is NOT an approximation of the interrupted run -- it reproduces it.
    ``run_one`` is a pure function of (task, format, condition, model, seed,
    pad_*), all of which are in the checkpoint key, so a replayed row is the row
    the call would have produced. ``_summarise_raw_rows`` groups and sorts its
    input, so the emitted rows are also independent of how the work was split
    across attempts.
    """
    raw_rows: list[dict] = []
    if seeds is None:
        seeds = POSTRETRIEVAL_SEEDS

    done = load_checkpoint(checkpoint_path) if checkpoint_path is not None else {}
    if done:
        print(f"  resuming: {len(done)} completed call(s) replayed from checkpoint")
    replayed = 0

    # Loop order (Spec 05 / B2): condition -> format -> model -> task -> trial.
    # ``format`` and ``model`` are hoisted ABOVE ``task`` and ``trial`` so a
    # (condition, format, model) cell's calls run back-to-back. Concretely the
    # three seeded trials of one (condition, format, model, task) are now
    # consecutive, and they re-send a byte-identical prompt (trials differ only by
    # seed), so their shared prefix stays inside the provider prefix-cache window
    # -- OpenAI's 5-10 min eviction and Anthropic's 5 min TTL. Under the previous
    # trial-outermost order the same prefix recurred only once per full inner
    # sweep (24-48 intervening calls), straddling those windows, so Anthropic cache
    # writes at 1.25x were worse than no caching. Keeping a cell's calls contiguous
    # also stops Llama calls interleaving between an API cell's calls and evicting
    # its cache.
    #
    # This is an ORDER-ONLY change. Each ``run_one`` is a pure function of
    # (task, format, condition, model, seed, pad_*), and ``_summarise_raw_rows``
    # groups by (task_id, format, condition, model) and sorts each group by
    # trial_idx, so neither the set of calls nor any grade depends on iteration
    # order. Verified by enumeration in
    # tests/test_postretrieval_loop_order.py (multiset of call tuples identical to
    # the previous nesting). The stop-condition-2 check -- identical REAL results
    # for a fixed seed on the verification subset -- must still be run once the
    # providers are provisioned.
    for condition in conditions:
        # WI2: the floor has no format arm, so it is run ONCE per
        # (task, condition, model, trial) under the sentinel rather than once per
        # requested format -- N identical rows differing only in a label would
        # inflate the call count and fake per-format variance.
        cond_formats = (
            [FLOOR_FORMAT_SENTINEL] if is_floor_condition(condition) else formats
        )
        for corpus_format in cond_formats:
            for model in models:
                for task in tasks:
                    for trial_idx, seed in enumerate(seeds):
                        cached = done.get(
                            (
                                task.task_id,
                                FLOOR_FORMAT_SENTINEL
                                if is_floor_condition(condition)
                                else corpus_format,
                                condition,
                                model,
                                trial_idx,
                            )
                        )
                        if cached is not None:
                            raw_rows.append(cached)
                            replayed += 1
                            continue
                        row, _grade = run_one(
                            task,
                            corpus_format,
                            condition,
                            model,
                            k,
                            trial_idx=trial_idx,
                            seed=seed,
                            pad_strategy=pad_strategy,
                            pad_seed=pad_seed,
                        )
                        # Persist BEFORE the next call, so a crash in the next call
                        # cannot lose this one.
                        _append_checkpoint(checkpoint_path, row)
                        raw_rows.append(row)
    if checkpoint_path is not None:
        print(
            f"  checkpoint: {len(raw_rows)} row(s) total "
            f"({replayed} replayed, {len(raw_rows) - replayed} newly called)"
        )
    return raw_rows, _summarise_raw_rows(raw_rows)
