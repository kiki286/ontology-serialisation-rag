# RAG Service: IDO Assistant

This folder contains the Retrieval-Augmented Generation (RAG) component of the IDO Assistant.

## Contents

- `Dockerfile` - Dockerfile for building the RAG service.
- `app/` - Application code (FastAPI app, RAG chain, document loaders).
- `data/` - Documents and special context files used for embedding and retrieval.
- `eval/` - Gold questions/answers, and experiment results.
- `experiment/` - The serialisation study's experiment harness (see the root README).
- `prompts/` - Prompt templates used by the RAG chain.
- `scripts/` - Corpus generation, verification, analysis and figure scripts.

## /app

The `app` package implements the RAG service and helpers:

- `document_loaders.py` - helpers for loading and chunking documents prior to embedding.
- `rag_chain.py` - code that builds and runs the RAG retrieval + generation chain.
- `embeddings/` - directory containing FAISS index files (embeddings) and the index checksum.
- `main.py` - Entrypoint that deploys the FastAPI application and exposes the HTTP routes used by the backend.

### RAG Steps

- loads conversation memory
- rewrites the user's query to make it explicit
- breaks down the rewritten query into retrieval units
- retrieves relevant chunks per retrieval unit
- generates response
- saves conversation memory

### API routes

- `/healthz` - health check
- `/answer_query` - accepts a user query, runs the RAG pipeline, and returns an answer together with supporting source snippets and metadata
- `/clear_rag_memory` - clears in-memory conversational state

## /data

The `data` directory holds the documents that are embedded and indexed for retrieval. Preferred formats are `.md`, `.ttl`, and `.tex`. Plain `.txt` files are supported but are not chunked as intelligently as the other formats.

The ontology corpus (the six `LIS-14-for-FDIS (1).*` files) is licensed and not redistributed, so in this repository `data/` holds only `SHA256SUMS`, the checksums of the files the study used. The root README's "The ontology corpus" section says where a licensed copy goes and how to regenerate the derived serialisations.

Ontology corpus experiments can be controlled with:

- `CORPUS_FORMAT=turtle|elot-org|elot-org-ancestors|omn` - selects which ontology representation to index. `elot-org` (flat) emits verbatim single-entity slices and appends the 1-hop `- SubClassOf :: <parent>` axiom to each class chunk, so class chunks carry the immediate superclass that Turtle/OMN state natively. `elot-org-ancestors` uses the same `.org` source but instead prefixes entity chunks with their full ancestor heading path.
- `ASSISTANT_CORPUS_MODE=full|ontology` - `full` loads the selected ontology plus shared assistant documents, while `ontology` loads only the selected ontology representation for controlled retrieval experiments.

Retrieval indexes exclude ontology declaration chunks, annotation property declaration chunks, ELOT/OMN prefix and document-structure chunks, ELOT structural `elot:section:*` chunks, and the empty standard datatype declarations in the IDO corpus. The underlying loaders still emit those chunks for inspection and oracle lookup.

### Special folder: `do-not-embed`

Documents in `do-not-embed` are not chunked or embedded. They are always included as
context to the LLM (`load_always_include_documents` in `app/document_loaders.py`). No
such folder is present in this repository, so that path currently contributes nothing.

### Source material not redistributed

`data/` previously also held a `do-not-include/` folder of ISO and POSC Caesar source
material: the ISO 15926-14 and ISO 23726-1 documents, LIS-14 prose, OBI training
session transcripts and related notes. **That material is not redistributed with this
work and has been removed.** It was never part of the retrieval corpus: the corpus walk
in `app/document_loaders.py` lists `data/` without recursing, so the folder was skipped
because it was a directory.

Historical documents in this repository still reference those files by name, in
particular `docs/ido-assistant/phase-one-report.md`, the methodology log at
`experiment/CHANGELOG.MD`, and the frozen `eval/results/trial-*` outputs, which record
them as the retrieval sources actually used at the time. Those records are deliberately
left as written: they describe what was true when those runs were made. The retrieved
context those runs recorded (`actual_context` in `eval/results/*/results_raw.csv`) is
blank, because it carried that material and the licensed ontology.

## /eval

Contains gold competency questions and answers, experimental results, and scripts used to run evaluation trials against the RAG system.

## /experiment

Contains the controlled format x task experiment harness.

Run from `src/rag`:

```bash
python -m experiment.run_experiment --stage postretrieval
```

The default OpenAI models are explicit dated snapshots:
`gpt-4o-2024-11-20` and `gpt-4o-mini-2024-07-18`. Avoid replacing these
with bare aliases such as `gpt-4o` or `gpt-4o-mini` for dissertation runs,
because aliases can resolve to newer snapshots over time.

The post-retrieval stage defaults to `--n-trials 3`. Trial seeds are configured
in `experiment/config.py` as `POSTRETRIEVAL_SEEDS = [20260529, 20260530,
20260531]`; each task-format-condition-model cell is run once per seed. Trial
indices are zero-based, so `trial_idx=0` maps to `20260529`, `trial_idx=1` maps
to `20260530`, and `trial_idx=2` maps to `20260531`. The raw CSV includes
`trial_idx`, `prompt_tokens`, `completion_tokens`, `total_tokens`,
`system_fingerprint`, and `model_returned`. The manifest records the seed list,
`trial_seed_map`, and a `cost_summary` derived from the recorded token counts.
The scored CSV reports per-task mean and sample standard deviation across
trials, and `postretrieval_variance.csv` summarises variability across cells.

Post-retrieval API cost is derived at analysis time with
`experiment/pricing.py`. Its pricing snapshot is dated in the module so token
records can be recomputed against a later OpenAI pricing snapshot if needed.

## /prompts

Holds prompt templates used by the RAG chain. Historical/archived prompt versions live in the `archive/` subfolders.

## /scripts

Corpus generation, verification, analysis and figure scripts; [`scripts/README.md`](scripts/README.md)
says what each one is for.
