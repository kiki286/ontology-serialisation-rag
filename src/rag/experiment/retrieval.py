"""RQ1: retrieval scoring per format (Recall@k, MRR, nDCG@k).

Headline gold relevance is membership of a retrieved chunk's ``entity_id`` in
the task's narrow ``retrieval_gold_chunks`` set. Secondary recall is also
reported against the broader oracle ``gold_chunks`` set. If a format returns
fewer than k chunks, the ranked list is padded to k with ``None`` placeholders
(documented choice): padding cannot match any gold entity, so it never helps a
format, and it keeps the positional denominators consistent at k. The actual
returned count is recorded per row.
"""

from __future__ import annotations

import math

from experiment.config import RETRIEVAL_K
from experiment.schemas import Task

METRICS = ["recall_at_k", "gold_recall_at_k", "mrr", "ndcg_at_k"]


def _recall_at_k(gold_chunks: list[str], padded_ids: list[str | None]) -> float:
    gold = set(gold_chunks)
    found = {eid for eid in padded_ids if eid in gold}
    return len(found) / len(gold) if gold else 0.0


def score_retrieval(
    retrieval_gold_chunks: list[str],
    retrieved_ids: list[str | None],
    k: int,
    broad_gold_chunks: list[str] | None = None,
) -> dict:
    """Compute retrieval metrics for one ranked list.

    ``recall_at_k`` is the headline score against the narrow retrieval target.
    ``gold_recall_at_k`` is the secondary score against the broader oracle
    context set.
    """
    padded = list(retrieved_ids[:k]) + [None] * max(0, k - len(retrieved_ids))
    gold = set(retrieval_gold_chunks)

    recall = _recall_at_k(retrieval_gold_chunks, padded)
    broad_recall = _recall_at_k(
        retrieval_gold_chunks if broad_gold_chunks is None else broad_gold_chunks,
        padded,
    )

    mrr = 0.0
    for rank, eid in enumerate(padded, start=1):
        if eid in gold:
            mrr = 1.0 / rank
            break

    dcg = sum(
        (1.0 if eid in gold else 0.0) / math.log2(rank + 1)
        for rank, eid in enumerate(padded, start=1)
    )
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg else 0.0

    return {
        "recall_at_k": recall,
        "gold_recall_at_k": broad_recall,
        "mrr": mrr,
        "ndcg_at_k": ndcg,
    }


def run_task_format(task: Task, corpus_format: str, k: int = RETRIEVAL_K) -> dict:
    from experiment import corpus_index  # lazy: pulls in FAISS/embeddings only here

    hits = corpus_index.retrieve(corpus_format, task.query, k=k)
    retrieved_ids = [h.metadata.get("entity_id") for h in hits]
    retrieval_gold = task.retrieval_gold_chunks_for(corpus_format)
    broad_gold = task.gold_chunks_for(corpus_format)
    scores = score_retrieval(retrieval_gold, retrieved_ids, k, broad_gold_chunks=broad_gold)
    primary_rank = None
    if task.primary_answer_chunk:
        for rank, entity_id in enumerate(retrieved_ids[:k], start=1):
            if entity_id == task.primary_answer_chunk:
                primary_rank = rank
                break
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "format": corpus_format,
        "query": task.query,
        "k": k,
        "n_retrieved": len(retrieved_ids),
        "retrieval_gold_chunks": ";".join(retrieval_gold),
        "gold_chunks": ";".join(broad_gold),
        "retrieved_ids": ";".join("" if x is None else x for x in retrieved_ids),
        "primary_answer_chunk": task.primary_answer_chunk or "",
        "primary_answer_hit": int(primary_rank is not None) if task.primary_answer_chunk else "",
        "primary_answer_rank": primary_rank or "",
        **scores,
    }


def run_retrieval(tasks: list[Task], formats: list[str], k: int = RETRIEVAL_K) -> list[dict]:
    rows: list[dict] = []
    for task in tasks:
        for corpus_format in formats:
            rows.append(run_task_format(task, corpus_format, k))
    return rows


def aggregate_retrieval(rows: list[dict]) -> list[dict]:
    """Mean of each metric grouped by format (then format x task_type)."""
    out: list[dict] = []

    def _mean(subset: list[dict], metric: str) -> float:
        return sum(r[metric] for r in subset) / len(subset) if subset else 0.0

    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault((row["format"], "ALL"), []).append(row)
        groups.setdefault((row["format"], row["task_type"]), []).append(row)

    for (corpus_format, task_type), subset in sorted(groups.items()):
        out.append(
            {
                "format": corpus_format,
                "task_type": task_type,
                "n": len(subset),
                **{metric: _mean(subset, metric) for metric in METRICS},
            }
        )
    return out
