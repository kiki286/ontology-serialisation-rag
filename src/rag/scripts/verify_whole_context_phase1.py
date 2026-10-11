"""Run the Phase 1 whole-context measurement and runtime gates."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from experiment.config import (  # noqa: E402
    FORMATS,
    MODELS,
    OLLAMA_NUM_CTX_WHOLE_CONTEXT,
    SYSTEM_PROMPTS,
    WHOLE_CONTEXT_GENERATION_HEADROOM,
    ontology_path,
)


CANARY = "ZZQX-ONTOLOGY-CANARY-7741"
LLAMA_MODEL = next(model for model in MODELS if "llama" in model.lower())


def _source_text(corpus_format: str) -> str:
    with ontology_path(corpus_format).open("r", encoding="utf-8", newline="") as source:
        return source.read()


def measure_sources() -> dict:
    import tiktoken

    from experiment.llm_call import _get_llama_tokenizer, count_llama_prompt_tokens
    from experiment.postretrieval import build_user_content
    from experiment.schemas import load_tasks

    cl100k = tiktoken.get_encoding("cl100k_base")
    tasks = {task.task_id: task for task in load_tasks() if task.task_id in {"T02", "T04"}}
    measurements = {}
    max_prompt = 0
    max_prompt_format = None
    max_prompt_task = None
    for corpus_format in FORMATS:
        source = _source_text(corpus_format)
        prompts = {}
        for task_id, task in tasks.items():
            system = SYSTEM_PROMPTS[task.task_type].read_text(encoding="utf-8")
            prompt_tokens = count_llama_prompt_tokens(
                system, build_user_content(task, source, "whole_context")
            )
            prompts[task_id] = prompt_tokens
            if prompt_tokens > max_prompt:
                max_prompt = prompt_tokens
                max_prompt_format = corpus_format
                max_prompt_task = task_id
        measurements[corpus_format] = {
            "source_chars": len(source),
            "source_cl100k_tokens": len(cl100k.encode(source)),
            "source_llama_tokens": len(_get_llama_tokenizer().encode(source).ids),
            "t02_t04_prompt_llama_tokens": prompts,
        }

    derived_num_ctx = max_prompt + WHOLE_CONTEXT_GENERATION_HEADROOM
    if derived_num_ctx != OLLAMA_NUM_CTX_WHOLE_CONTEXT:
        raise AssertionError(
            "OLLAMA_NUM_CTX_WHOLE_CONTEXT is stale: "
            f"expected {derived_num_ctx} from {max_prompt_format}/{max_prompt_task}, "
            f"got {OLLAMA_NUM_CTX_WHOLE_CONTEXT}"
        )
    return {
        "formats": measurements,
        "max_prompt_llama_tokens": max_prompt,
        "max_prompt_format": max_prompt_format,
        "max_prompt_task": max_prompt_task,
        "generation_headroom": WHOLE_CONTEXT_GENERATION_HEADROOM,
        "derived_num_ctx": derived_num_ctx,
    }


def run_graph_gate() -> str:
    from scripts.verify_ontology_chunkers import verify_source_graph_equality

    verify_source_graph_equality()
    return "passed for in-repo deserialisable arms; ELOT requires external ELOT/Emacs"


def run_canary_gate() -> dict:
    from experiment.llm_call import call_model

    source = _source_text("jsonld")
    system = "Return JSON with exactly one key, canary, whose value is the canary token."
    user = f"{CANARY}\n\nOntology content:\n\n{source}\n\nReturn the canary token."
    result = call_model(LLAMA_MODEL, system, user, condition="whole_context")
    content = result.get("content", "")
    if CANARY not in content:
        raise AssertionError(f"whole-context canary did not round-trip: {content!r}")
    return {
        "model": LLAMA_MODEL,
        "prompt_eval_count": result["usage"]["prompt_eval_count"],
        "canary": CANARY,
        "response": content,
    }


def check_gpu_residency() -> str:
    process = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
    output = process.stdout.strip()
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "ollama ps failed")
    model_line = next((line for line in output.splitlines() if LLAMA_MODEL in line), "")
    if "100% GPU" not in model_line:
        raise AssertionError(f"{LLAMA_MODEL} is not 100% GPU-resident:\n{output}")
    context_match = re.search(r"\s(\d+)\s+Forever\s*$", model_line)
    if context_match and int(context_match.group(1)) < OLLAMA_NUM_CTX_WHOLE_CONTEXT:
        raise AssertionError(f"Ollama context is below the Phase 1 window:\n{output}")
    return output


def main() -> int:
    measurements = measure_sources()
    graph_status = run_graph_gate()
    canary = run_canary_gate()
    ollama_ps = check_gpu_residency()
    evidence = {
        "phase": "spec6-phase1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "condition": "whole_context",
        "construction": "mapped source file read verbatim; no chunk scaffolding or prefix prepending",
        "graph_equality": graph_status,
        "ollama_kv_cache_type": "q8_0",
        "measurements": measurements,
        "canary": canary,
        "ollama_ps": ollama_ps,
    }
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())