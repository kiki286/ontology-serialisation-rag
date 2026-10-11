"""Thin Chat Completions wrapper for the experiment.

Uses the OpenAI SDK directly (not LangChain) for precise control over the pinned
knobs the study requires: model, temperature=0, fixed seed, and JSON-object
response format. Returns the raw content plus reproducibility metadata
(returned model, system_fingerprint, usage) for the manifest/audit log.

Two providers are supported, detected from the model string:
  * ``openai`` - the hosted API (default).
  * ``ollama`` - a local server exposing an OpenAI-compatible endpoint. Used for
    local models (e.g. ``llama3.1:8b-instruct-q8_0``). Retrieval/embeddings stay
    on OpenAI; only post-retrieval generation can target Ollama.
"""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic
from openai import OpenAI, OpenAIError
import requests

from experiment.config import (
    OLLAMA_BASE_URL,
    OLLAMA_NUM_PREDICT,
    SEED,
    TEMPERATURE,
    ollama_num_ctx_for_condition,
)

_client: OpenAI | None = None
_ollama_client: OpenAI | None = None
_anthropic_client: Anthropic | None = None
_llama_tokenizer = None
_PROMPT_TOKEN_TOLERANCE = 64


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from env
    return _client


def _get_ollama_client() -> OpenAI:
    global _ollama_client
    if _ollama_client is None:
        # api_key is required by the SDK but ignored by the local server.
        _ollama_client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    return _ollama_client


def _get_anthropic_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _anthropic_client


def detect_provider(model: str) -> str:
    """Route by model string; llama -> Ollama, claude -> Anthropic, else OpenAI."""
    lowered = model.lower()
    if "llama" in lowered:
        return "ollama"
    if "claude" in lowered:
        return "anthropic"
    return "openai"


# ---------------------------------------------------------------------------
# Anthropic structured output (WI-9 option (a): tool use).
#
# The Anthropic arm cannot use the OpenAI ``response_format={"type":
# "json_object"}`` switch, and with the shared prompt verbatim Sonnet wraps its
# JSON in a markdown fence, which fails ``json.loads`` at char 0 (CHANGELOG
# 2026-08-04 (d)). The two alternatives -- a per-model prompt line, or
# fence-stripping in the shared parser -- both change what is compared: the
# first makes the prompt a per-model variable, the second alters the parsing
# path for arms that are already reported. Tool use is the only route that
# leaves the prompt BYTE-IDENTICAL across arms; only the API mechanism differs.
#
# The schemas below mirror ``schemas.VerificationResponse`` /
# ``SlotFillingResponse`` exactly. The tool input is dumped back to a JSON
# string so ``parse_response`` stays the single, shared parsing path -- the
# Anthropic arm is graded by the same code as every other arm.
# ---------------------------------------------------------------------------
_CITATION_FIELD = {
    "type": ["string", "null"],
    "description": "entity_id of the chunk supporting this decision, or null",
}

ANTHROPIC_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "verification": {
        "name": "submit_verification",
        "description": "Submit the verification judgement for the candidate statement.",
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "enum": ["supported", "contradicted", "undetermined"],
                },
                "reasoning": {"type": "string", "description": "one sentence"},
            },
            "required": ["label", "reasoning"],
        },
    },
    "slot_filling": {
        "name": "submit_slot_filling",
        "description": "Submit the filled modelling slots for the scenario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "class": {"type": "string"},
                "property": {"type": "string"},
                "intermediate_node": {"type": "boolean"},
                "supporting_chunks": {
                    "type": "object",
                    "properties": {
                        "class": dict(_CITATION_FIELD),
                        "property": dict(_CITATION_FIELD),
                        "intermediate_node": dict(_CITATION_FIELD),
                    },
                    "required": ["class", "property", "intermediate_node"],
                },
                "reasoning": {"type": "string", "description": "one sentence"},
            },
            "required": [
                "class",
                "property",
                "intermediate_node",
                "supporting_chunks",
                "reasoning",
            ],
        },
    },
}


def _get_llama_tokenizer():
    global _llama_tokenizer
    if _llama_tokenizer is None:
        from tokenizers import Tokenizer

        tokenizer_path = os.getenv("LLAMA_TOKENIZER_PATH")
        _llama_tokenizer = (
            Tokenizer.from_file(tokenizer_path)
            if tokenizer_path
            else Tokenizer.from_pretrained("NousResearch/Meta-Llama-3.1-8B-Instruct")
        )
    return _llama_tokenizer


def count_llama_prompt_tokens(system_prompt: str, user_content: str) -> int:
    """Count the harness prompt with the tokenizer matched to the Ollama model."""
    return len(_get_llama_tokenizer().encode(system_prompt + user_content).ids)


def _call_ollama(
    model: str,
    system_prompt: str,
    user_content: str,
    *,
    temperature: float,
    seed: int,
    condition: str,
    num_ctx: int | None,
) -> dict[str, Any]:
    url = OLLAMA_BASE_URL.removesuffix("/v1") + "/api/chat"
    selected_num_ctx = num_ctx or ollama_num_ctx_for_condition(condition)
    response = requests.post(
        url,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "num_ctx": selected_num_ctx,
                "temperature": temperature,
                "seed": seed,
                # Bounded generation. Without this Ollama decodes until the context
                # window fills, which takes longer than this request's own timeout,
                # so a degenerate response kills the run instead of returning one
                # (see OLLAMA_NUM_PREDICT in config.py). No effect on a response
                # that stops on its own; the longest ever recorded is 477 tokens.
                "num_predict": OLLAMA_NUM_PREDICT,
            },
        },
        timeout=300,
    )
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Ollama call failed for model {model!r} at {url}. "
            "Is `ollama serve` running and the model pulled?"
        ) from exc

    body = response.json()
    actual_prompt_tokens = body.get("prompt_eval_count")
    if actual_prompt_tokens is None:
        raise AssertionError("Ollama response omitted prompt_eval_count")
    expected_prompt_tokens = count_llama_prompt_tokens(system_prompt, user_content)
    if abs(actual_prompt_tokens - expected_prompt_tokens) > _PROMPT_TOKEN_TOLERANCE:
        raise AssertionError(
            "Ollama prompt was truncated or token-counted unexpectedly: "
            f"expected about {expected_prompt_tokens}, got {actual_prompt_tokens} "
            f"for condition={condition!r}"
        )

    completion_tokens = body.get("eval_count")
    return {
        "provider": "ollama",
        "content": (body.get("message") or {}).get("content", ""),
        "finish_reason": body.get("done_reason"),
        "model": body.get("model", model),
        "model_returned": body.get("model", model),
        "system_fingerprint": None,
        "usage": {
            "prompt_tokens": actual_prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": (
                actual_prompt_tokens + completion_tokens
                if completion_tokens is not None
                else None
            ),
            "prompt_eval_count": actual_prompt_tokens,
        },
    }


def _call_anthropic(
    model: str,
    system_prompt: str,
    user_content: str,
    *,
    temperature: float,
    task_type: str,
    user_segments: list[str] | None,
    cache_corpus: bool,
) -> dict[str, Any]:
    """Messages-shaped call with tool-use structured output and a cache breakpoint.

    ``user_segments`` splits the SAME user string into content blocks so the
    corpus can carry its own ``cache_control`` breakpoint; their concatenation is
    asserted to equal ``user_content`` so the Anthropic arm sends byte-identical
    prompt text to the OpenAI arms. There is no ``seed`` parameter in the
    Anthropic API (recorded as absence, not failure -- CHANGELOG 2026-08-04 (d)).
    """
    tool = ANTHROPIC_TOOL_SCHEMAS.get(task_type)
    if tool is None:
        raise ValueError(
            f"no Anthropic tool schema for task_type {task_type!r}; "
            f"expected one of {sorted(ANTHROPIC_TOOL_SCHEMAS)}"
        )

    if user_segments is None:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": user_content}]
    else:
        joined = "".join(user_segments)
        if joined != user_content:
            raise AssertionError(
                "Anthropic user_segments do not reassemble to the shared user_content; "
                "the Anthropic arm would send different prompt text than the OpenAI arms "
                f"(segments={len(joined)} chars, user_content={len(user_content)} chars)"
            )
        blocks = [{"type": "text", "text": segment} for segment in user_segments if segment]
        # Breakpoint after the corpus block: everything up to and including it is
        # the cacheable prefix. Only set when the loop actually runs a cell's calls
        # back-to-back -- Anthropic writes cost 1.25x, so caching a prefix that is
        # evicted before the next hit is strictly worse than not caching (B2).
        if cache_corpus and len(blocks) > 1:
            blocks[0]["cache_control"] = {"type": "ephemeral"}

    response = _get_anthropic_client().messages.create(
        model=model,
        max_tokens=1024,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": blocks}],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
    )

    payload = next(
        (block.input for block in response.content if block.type == "tool_use"), None
    )
    if payload is None:
        raise RuntimeError(
            f"Anthropic returned no tool_use block for {model!r}; "
            f"stop_reason={response.stop_reason}"
        )

    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", None) or 0
    # Anthropic's input_tokens EXCLUDES cached and cache-write tokens; the other
    # arms report a prompt total that includes them, so add them back here to keep
    # the prompt_tokens column comparable across providers.
    prompt_tokens = usage.input_tokens + cache_read + cache_write
    return {
        "provider": "anthropic",
        "content": json.dumps(payload),
        "finish_reason": response.stop_reason,
        "model": response.model,
        "model_returned": response.model,
        "system_fingerprint": None,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": usage.output_tokens,
            "total_tokens": prompt_tokens + usage.output_tokens,
            "cached_tokens": cache_read,
            "cache_creation_input_tokens": cache_write,
        },
    }


def call_model(
    model: str,
    system_prompt: str,
    user_content: str,
    *,
    temperature: float = TEMPERATURE,
    seed: int = SEED,
    condition: str = "oracle",
    num_ctx: int | None = None,
    task_type: str | None = None,
    user_segments: list[str] | None = None,
    cache_corpus: bool = False,
) -> dict[str, Any]:
    """Call the model with pinned settings; return content + metadata.

    ``task_type``/``user_segments``/``cache_corpus`` are consumed by the Anthropic
    branch only. The OpenAI and Ollama branches below read ``user_content`` and
    nothing else, so their request payloads are unchanged by this addition.
    """
    provider = detect_provider(model)
    if provider == "anthropic":
        return _call_anthropic(
            model,
            system_prompt,
            user_content,
            temperature=temperature,
            task_type=task_type or "",
            user_segments=user_segments,
            cache_corpus=cache_corpus,
        )
    if provider == "ollama":
        return _call_ollama(
            model,
            system_prompt,
            user_content,
            temperature=temperature,
            seed=seed,
            condition=condition,
            num_ctx=num_ctx,
        )

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "seed": seed,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    client = _get_client()

    try:
        resp = client.chat.completions.create(**kwargs)
    except OpenAIError as exc:
        raise

    choice = resp.choices[0]
    usage = resp.usage.model_dump() if resp.usage else None
    return {
        "provider": provider,
        "content": choice.message.content or "",
        "finish_reason": choice.finish_reason,
        "model": resp.model,
        "model_returned": resp.model,
        "system_fingerprint": getattr(resp, "system_fingerprint", None),
        "usage": usage,
    }
