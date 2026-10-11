"""Coverage covariate (WI5) and context-length covariate (WI7).

The headline finding is that format effects are mediated by whether the required
entity actually reached the context. This module makes that a first-class, ID-based
computation instead of fragile substring matching on prose.

Two entry points share one definition so the live harness (``postretrieval.run_one``)
and the offline backfill (``rescore``) compute identical columns:

  * ``context_chunk_ids`` — the ordered entity ids in a context block. Recoverable
    exactly and offline from the ``# Chunk: <id>`` labels ``assemble_context_block``
    writes, so the pilot needs no retrieval re-run to backfill.
  * ``covered_<field>`` / ``coverage_all`` / ``coverage_frac`` — per graded slot field,
    whether any licensing chunk in ``field_gold_chunks[field]`` is present, by set
    membership on ids. Fields that require no entity (empty licensing set, e.g.
    intermediate_node when gold has no intermediate node) are N/A and excluded from
    the coverage_all / coverage_frac summary — coverage judges only fields that need
    an entity present.
"""

from __future__ import annotations

import re

from experiment.config import CHUNK_LABEL
from experiment.grading import FIELD_GOLD_CHUNK_KEY, SLOT_FIELDS, _norm, graded_slot_fields
from experiment.schemas import Task

# The chunk label is "# Chunk: {entity_id}"; capture the id that follows it.
_CHUNK_LABEL_RE = re.compile(
    "^" + re.escape(CHUNK_LABEL).replace(r"\{entity_id\}", r"(.+)") + r"\s*$",
    re.MULTILINE,
)

_USER_CONTENT_PREFIX = "Ontology content:\n\n"


def context_chunk_ids_from_content(user_content: str) -> list[str]:
    """Ordered entity ids parsed from the ``# Chunk:`` labels in a user message."""
    return [m.strip() for m in _CHUNK_LABEL_RE.findall(user_content or "")]


def context_chunk_ids_from_chunks(chunks: list[tuple[str, str]]) -> list[str]:
    """Ordered entity ids straight from the assembled (entity_id, content) tuples."""
    return [entity_id for entity_id, _content in chunks]


def _task_input(task: Task) -> str:
    """Mirror of ``postretrieval.build_user_content``'s task-input line."""
    if task.task_type == "verification":
        return f"Statement: {(task.statement or '').strip()}"
    return f"Scenario: {(task.scenario or '').strip()}"


def context_block_from_user_content(user_content: str, task: Task) -> str:
    """Recover the assembled context block from a stored ``user_content`` string.

    ``build_user_content`` wraps the block as
    ``"Ontology content:\\n\\n{block}\\n\\n{task_input}"``; strip both ends back off so
    ``context_char_len`` measures exactly the block the model saw, matching what the
    live harness records via ``len(context)``.
    """
    body = user_content or ""
    if body.startswith(_USER_CONTENT_PREFIX):
        body = body[len(_USER_CONTENT_PREFIX):]
    suffix = "\n\n" + _task_input(task)
    if body.endswith(suffix):
        body = body[: -len(suffix)]
    return body


def compute_coverage(task: Task, context_chunk_ids: list[str]) -> dict:
    """Per-field and summary coverage for a slot-filling row.

    Verification tasks have no graded slot fields, so every coverage column is N/A.
    """
    out: dict = {f"covered_{FIELD_GOLD_CHUNK_KEY[f]}": None for f in SLOT_FIELDS}
    out["coverage_all"] = None
    out["coverage_frac"] = None
    if task.task_type != "slot_filling":
        return out

    ctx = {_norm(cid) for cid in context_chunk_ids}
    graded = set(graded_slot_fields(task))
    flags: list[bool] = []
    for field in SLOT_FIELDS:
        key = FIELD_GOLD_CHUNK_KEY[field]
        licensing = task.field_gold_chunks_for(key)
        if field in graded and licensing:
            covered = any(_norm(x) in ctx for x in licensing)
            out[f"covered_{key}"] = int(covered)
            flags.append(covered)
        # else: excluded field, or a graded field that needs no entity -> N/A.
    if flags:
        out["coverage_all"] = int(all(flags))
        out["coverage_frac"] = sum(flags) / len(flags)
    return out


def coverage_columns() -> list[str]:
    """Stable ordered list of the coverage column names this module emits."""
    cols = [f"covered_{FIELD_GOLD_CHUNK_KEY[f]}" for f in SLOT_FIELDS]
    cols += ["coverage_all", "coverage_frac"]
    return cols
