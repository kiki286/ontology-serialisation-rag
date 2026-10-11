"""Per-format corpus access: chunk loading, oracle lookup, and FAISS retrieval.

Reuses the real entity-based chunkers from ``app.document_loaders``. Plain
(flat) ELOT uses verbatim single-entity slices with a 1-hop
``- SubClassOf :: <parent>`` line appended to class chunks; the
``elot-org-ancestors`` variant instead prefixes entity chunks with the full
ancestor heading path. Indexes are experiment-scoped (``experiment/indexes/``)
so they never collide with the assistant's, and are cached by a content
checksum.
"""

from __future__ import annotations

import hashlib
import json
import random
from functools import lru_cache

from langchain_core.documents import Document

from app.document_loaders import (
    EntityBasedElotOrgLoader,
    EntityBasedJsonLdLoader,
    EntityBasedOfnLoader,
    EntityBasedOmnLoader,
    EntityBasedSchemaConceptLoader,
    EntityBasedTurtleLoader,
    EntityBasedYamlLdLoader,
    RETRIEVAL_INDEX_FILTER_VERSION,
    filter_retrieval_index_documents,
)
from experiment.config import (
    ELOT_ANCESTOR_FORMAT,
    EMBEDDING_MODEL,
    FORMATS,
    INDEX_DIR,
    RETRIEVAL_K,
    SEED,
    ontology_path,
)

# FAISS + embeddings are imported lazily inside the retrieval functions so the
# oracle/validation paths (smoke 1a/1b) do not require the vector stack.
_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_openai import OpenAIEmbeddings

        _embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return _embeddings


@lru_cache(maxsize=None)
def load_format_chunks(corpus_format: str) -> list[Document]:
    """Load the entity-based chunks for a format."""
    path = str(ontology_path(corpus_format))
    if corpus_format == "turtle":
        return EntityBasedTurtleLoader(path, include_external_vocab=True).load()
    if corpus_format == "elot-org":
        return EntityBasedElotOrgLoader(
            path,
            include_ancestor_headings=False,
            format_name=corpus_format,
        ).load()
    if corpus_format == ELOT_ANCESTOR_FORMAT:
        return EntityBasedElotOrgLoader(
            path,
            include_ancestor_headings=True,
            format_name=corpus_format,
        ).load()
    if corpus_format == "omn":
        return EntityBasedOmnLoader(path).load()
    if corpus_format == "jsonld":
        return EntityBasedJsonLdLoader(path).load()
    if corpus_format == "yaml-ld":
        return EntityBasedYamlLdLoader(path).load()
    if corpus_format == "ofn":
        return EntityBasedOfnLoader(path).load()
    if corpus_format == "schema-concept":
        return EntityBasedSchemaConceptLoader(path).load()
    raise ValueError(f"unknown format {corpus_format!r}")


@lru_cache(maxsize=None)
def build_oracle_map(corpus_format: str) -> dict[str, Document]:
    """Map entity_id -> chunk Document for oracle context assembly."""
    out: dict[str, Document] = {}
    for doc in filter_retrieval_index_documents(load_format_chunks(corpus_format)):
        entity_id = doc.metadata.get("entity_id")
        if entity_id and entity_id not in out:
            out[entity_id] = doc
    return out


def entity_ids_by_format(formats: list[str] | None = None) -> dict[str, set[str]]:
    """Set of entity_ids each format emits (for gold-resolution validation).

    Iterates ``formats`` (default: the core ``FORMATS``) so that whatever the
    caller actually runs -- including an exploratory format not in ``FORMATS`` --
    is the thing whose gold resolution gets validated, rather than silently
    checking only the seven core serialisations.
    """
    return {
        fmt: {
            doc.metadata["entity_id"]
            for doc in load_format_chunks(fmt)
            if doc.metadata.get("entity_id")
        }
        for fmt in (formats or FORMATS)
    }


def retrieval_entity_ids_by_format(formats: list[str] | None = None) -> dict[str, set[str]]:
    """Set of entity ids eligible for retrieval and oracle context assembly."""
    return {fmt: set(build_oracle_map(fmt)) for fmt in (formats or FORMATS)}


def get_oracle_chunks(corpus_format: str, entity_ids: list[str]) -> list[tuple[str, str]]:
    """Ordered (entity_id, page_content) for the gold set; raises if any missing."""
    oracle = build_oracle_map(corpus_format)
    chunks: list[tuple[str, str]] = []
    missing: list[str] = []
    for entity_id in entity_ids:
        doc = oracle.get(entity_id)
        if doc is None:
            missing.append(entity_id)
        else:
            chunks.append((entity_id, doc.page_content))
    if missing:
        raise KeyError(f"{corpus_format}: gold entities not found: {missing}")
    return chunks


def get_all_chunks(corpus_format: str) -> list[tuple[str, str]]:
    """Return every emitted chunk in source order for whole-context probes."""
    return [
        (doc.metadata.get("entity_id") or "", doc.page_content)
        for doc in load_format_chunks(corpus_format)
    ]


@lru_cache(maxsize=None)
def get_source_file_context(corpus_format: str) -> str:
    """Return the mapped source serialisation verbatim for whole-context."""
    with ontology_path(corpus_format).open("r", encoding="utf-8", newline="") as source:
        return source.read()


# ---------------------------------------------------------------------------
# Retrieval (RQ1 + retrieved condition)
# ---------------------------------------------------------------------------
def _checksum(corpus_format: str, docs: list[Document]) -> str:
    h = hashlib.sha256()
    h.update(
        f"{corpus_format}:{EMBEDDING_MODEL}:{RETRIEVAL_INDEX_FILTER_VERSION}".encode()
    )
    for doc in docs:
        h.update((doc.metadata.get("chunk_id", "") + "\n").encode())
        h.update((doc.page_content + "\n").encode())
    return h.hexdigest()


def build_or_load_index(corpus_format: str):
    """Build (or load cached) a FAISS index over a format's ontology chunks."""
    import faiss
    from langchain_community.docstore.in_memory import InMemoryDocstore
    from langchain_community.vectorstores import FAISS

    loaded_docs = load_format_chunks(corpus_format)
    docs = filter_retrieval_index_documents(loaded_docs)
    embeddings = _get_embeddings()
    index_path = INDEX_DIR / corpus_format
    checksum_path = INDEX_DIR / f"checksum_{corpus_format}.json"
    checksum = _checksum(corpus_format, docs)

    if index_path.exists() and checksum_path.exists():
        prev = json.loads(checksum_path.read_text()).get("checksum")
        if prev == checksum:
            return FAISS.load_local(
                str(index_path), embeddings, allow_dangerous_deserialization=True
            )

    dim = len(embeddings.embed_query("hello world"))
    vector_store = FAISS(
        embedding_function=embeddings,
        index=faiss.IndexFlatL2(dim),
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )
    vector_store.add_documents(docs)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(index_path))
    checksum_path.write_text(json.dumps({"checksum": checksum}, indent=2))
    return vector_store


def retrieve(corpus_format: str, query: str, k: int = RETRIEVAL_K) -> list[Document]:
    """Top-k chunks for a query over a format's index (may return < k)."""
    vector_store = build_or_load_index(corpus_format)
    return vector_store.similarity_search(query, k=k)


# ---------------------------------------------------------------------------
# Oracle padding (WI7)
# ---------------------------------------------------------------------------
def retrieval_pool(corpus_format: str) -> list[Document]:
    """Retrieval-eligible chunks (same filter the FAISS index uses)."""
    return filter_retrieval_index_documents(load_format_chunks(corpus_format))


@lru_cache(maxsize=1)
def shared_retrieval_entity_ids() -> tuple[str, ...]:
    """Entity ids retrievable in EVERY format (the shared, format-neutral pad pool).

    The intersection guarantees a sampled id serialises into every format's oracle
    map, so padding is the same entity set across formats (domain entity chunks only,
    consistent with the retrieval-index exclusion policy).
    """
    per_format = [
        {d.metadata.get("entity_id") for d in retrieval_pool(fmt) if d.metadata.get("entity_id")}
        for fmt in FORMATS
    ]
    return tuple(sorted(set.intersection(*per_format)))


def _task_pad_seed(task_id: str, base_seed: int) -> int:
    """Deterministic, pinned per-task seed (Python's hash() is salted; sha256 is not)."""
    digest = hashlib.sha256(f"{base_seed}:{task_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def padding_pool_for_task(
    task_id: str, exclude_ids: set[str] | list[str], *, seed: int = SEED
) -> list[str]:
    """Deterministic shuffled ordering of pad-eligible ids for a task (sampled ONCE).

    Format-independent by construction: the ordering depends only on the task and the
    pinned seed, so every format takes the same prefix and therefore the same padding
    entities. Excludes ``exclude_ids`` (the task's gold across all formats).
    """
    exclude = set(exclude_ids)
    pool = [eid for eid in shared_retrieval_entity_ids() if eid not in exclude]
    random.Random(_task_pad_seed(task_id, seed)).shuffle(pool)
    return pool


def get_padding_chunks(
    corpus_format: str,
    exclude_ids: set[str],
    n: int,
    *,
    query: str | None = None,
) -> list[tuple[str, str]]:
    """Up to ``n`` top-ranked non-gold (entity_id, page_content) chunks for a query.

    Per-format by nature (each format retrieves its own distractors); used only by the
    ``retrieved`` pad strategy, which is intentionally NOT entity-controlled.
    """
    if n <= 0:
        return []
    if query is None:
        raise ValueError("get_padding_chunks requires a query")
    picked = []
    for hit in retrieve(corpus_format, query, k=len(retrieval_pool(corpus_format))):
        entity_id = hit.metadata.get("entity_id")
        if entity_id and entity_id not in exclude_ids:
            picked.append(hit)
            if len(picked) >= n:
                break
    return [(d.metadata.get("entity_id") or "", d.page_content) for d in picked]
