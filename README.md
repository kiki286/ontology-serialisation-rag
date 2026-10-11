# Ontology Serialisation and RAG over the Industrial Data Ontology

This repository holds the code, benchmark and frozen results behind the honours
dissertation *Ontology Serialisation Effects on Retrieval and Post-Retrieval Task
Performance in LLM-Assisted Industrial Ontology Modelling* (Malachy McGrath, 2026).

The study asks whether the serialisation of an ontology changes what a
retrieval-augmented generation (RAG) system retrieves and how well a language model
answers from it. One ontology, the Industrial Data Ontology (LIS-14 / IDO), is written
in seven serialisations, and the same 60-item benchmark is run against every one under
identical conditions:

- **RQ1 (retrieval):** does serialisation affect which ontology entities a dense
  retriever finds?
- **RQ2 (answer quality):** does serialisation affect the correctness of answers
  grounded in the retrieved or the gold context?

If you are reading this alongside the dissertation, start with
[the evidence map](#where-the-dissertations-evidence-lives): every figure, table,
benchmark, configuration and path the dissertation cites is listed there with where it
lives in this repository and how to check it.

## Contents

1. [The study in one page](#the-study-in-one-page)
2. [Where the dissertation's evidence lives](#where-the-dissertations-evidence-lives)
3. [Repository layout](#repository-layout)
4. [The ontology corpus (not included)](#the-ontology-corpus)
5. [How to check and reproduce](#how-to-check-and-reproduce)
6. [Regenerating the figures](#regenerating-the-figures)
7. [Provenance notes](#provenance-notes)
8. [The web application (the original IDO Assistant)](#the-web-application-the-original-ido-assistant)

## The study in one page

**Seven serialisations, one ontology.** All seven serialisations carry the *same*
ontology (the canonical Turtle, 2214 triples, 155 named retrievable entities); a
verification suite enforces whole-graph equality and per-entity parity. They live in
six files, because `elot-org` and `elot-org-ancestors` are two chunkings of the same
`.org` source. The ontology is licensed, so these files are not included: see
[the ontology corpus](#the-ontology-corpus) for where a licensed copy goes. Each
serialisation has its own entity-based chunker (one chunk per class or property) in
[`src/rag/app/document_loaders.py`](src/rag/app/document_loaders.py):

| Serialisation | File ext | Chunker class | How the file was generated |
|---|---|---|---|
| `turtle` | `.ttl` | `EntityBasedTurtleLoader` | canonical: the FDIS release file (source of truth) |
| `elot-org` (ELOT-flat) | `.org` | `EntityBasedElotOrgLoader` (flat) | externally, via ELOT/Emacs |
| `elot-org-ancestors` (ELOT-nested) | `.org` | `EntityBasedElotOrgLoader` (nested) | same file, ancestor-path chunking |
| `omn` | `.omn` | `EntityBasedOmnLoader` | externally, via ELOT/Emacs tangle |
| `jsonld` | `.jsonld` | `EntityBasedJsonLdLoader` | [`scripts/tangle_jsonld.py`](src/rag/scripts/tangle_jsonld.py) (rdflib) |
| `yaml-ld` | `.yamlld` | `EntityBasedYamlLdLoader` | [`scripts/tangle_yamlld.py`](src/rag/scripts/tangle_yamlld.py) (same object, YAML emit) |
| `ofn` | `.ofn` | `EntityBasedOfnLoader` | [`scripts/tangle_ofn.py`](src/rag/scripts/tangle_ofn.py) (ROBOT/OWLAPI) |

**Four models** (the code calls them *arms*), pinned in
[`src/rag/experiment/config.py`](src/rag/experiment/config.py), all at temperature 0
with dated or quantised snapshots: `gpt-4o-2024-11-20`, `gpt-4o-mini-2024-07-18`,
`claude-sonnet-4-5-20250929`, and `llama3.1:8b-instruct-q8_0` (local, via Ollama).

**Two context conditions.** *Gold context* (named `oracle` in the code, the manifests
and the result CSVs): the model receives exactly the item's gold chunks. *Retrieved
context* (`retrieved`): the model receives the top k = 5 chunks from FAISS dense
retrieval (`text-embedding-3-large`) over that serialisation's index.

**The benchmark.** 60 items in
[`tasks_60.yaml`](src/rag/experiment/benchmark/tasks_60.yaml) (ids T06-T65; T01-T05 are
the earlier five-item pilot in [`tasks.yaml`](src/rag/experiment/benchmark/tasks.yaml)):
30 statement-verification items (gold label `supported`, `contradicted` or
`undetermined`, ten each) and 30 slot-filling items, each with gold chunk ids that
resolve in every serialisation. Field-by-field schema:
[`schema.md`](src/rag/experiment/benchmark/schema.md).

**The design.** 60 items x 7 serialisations x 2 conditions x 4 models, every cell run
three times (seeds 20260529, 20260530, 20260531): 10,080 graded responses. Retrieval is
scored separately and once: 420 ranked lists. The item is the unit of analysis; every
interval resamples items.

**The headline result.** Serialisation has little effect on either stage. Retrieval
does not differ measurably between serialisations, and of 84 pairwise post-retrieval
comparisons only one is both Holm-significant and larger than one item's worth (OMN
over YAML-LD on verification accuracy, +0.074). Supplying the gold context improves
slot-filling by +0.320 to +0.374, about fifteen times the largest serialisation spread.
When the ontology is silent, models call the statement `contradicted` 90.8% of the
time. The one large serialisation effect is local: ELOT-nested, which shows a subclass
relation only through heading depth, loses 0.434 accuracy on the items that depend on
it.

## Where the dissertation's evidence lives

Almost every number below is asserted against the committed data by
[`check_thesis_numbers.py`](src/rag/scripts/diagnostics/check_thesis_numbers.py)
(518 checks, each tagged with the chapter, line or table label it pins), and every
generated figure is redrawn from the same CSVs by the two figure scripts, which assert
their plotted values too. Unless stated otherwise, paths are under `src/rag/`.

**Headline data.** RQ2 (post-retrieval) is
[`experiment/results/postretrieval-combined-15-18/`](src/rag/experiment/results/postretrieval-combined-15-18/);
RQ1 (retrieval) is
[`experiment/results/retrieval-trial-14/`](src/rag/experiment/results/retrieval-trial-14/).
What each results directory and CSV holds:
[`experiment/results/README.md`](src/rag/experiment/results/README.md).

### Figures

| Dissertation | Generated by | Data |
|---|---|---|
| Figure 1.1, the IDO assistant | `scripts/make_methods_figures.py` (`fig_m0_assistant`) | diagram |
| Figure 3.1, factorial design | `scripts/make_methods_figures.py` (`fig_m2_design`) | diagram |
| Figure 3.2, two benchmark items with model responses | typeset in the dissertation source, not generated here | verbatim responses to T19 and T35 from `postretrieval-combined-15-18/postretrieval_raw.csv` (oracle, turtle, trial 0) |
| Figure 3.3, scoring schemes | `scripts/make_methods_figures.py` (`fig_m3_scoring`) | diagram of [`experiment/grading.py`](src/rag/experiment/grading.py) |
| Figure 3.4, experimental pipeline | `scripts/make_methods_figures.py` (`fig_m1_pipeline`) | diagram |
| Figures 3.5-3.6, the same class in all seven serialisations | typeset in the dissertation source | the `lis:PhysicalArtefact` chunk from each loader in `app/document_loaders.py` (needs the licensed ontology) |
| Figure 4.1, three-way verification confusion matrix | `scripts/make_thesis_figures.py` (`fig4_undetermined_collapse`) | `postretrieval-combined-15-18` |
| Figure 4.2, slot-filling answer vs citation fields | `scripts/make_thesis_figures.py` (`fig5_answer_vs_citation`) | `postretrieval-combined-15-18` |
| Figure 4.3, effects of serialisation on the three headline measures | `scripts/make_thesis_figures.py` (`fig1_format_null`) | `retrieval-trial-14`, `postretrieval-combined-15-18` |
| Figure 4.4, gold vs retrieved context on slot-filling | `scripts/make_thesis_figures.py` (`fig2_context_vs_format`) | `postretrieval-combined-15-18` |
| Figure 4.5, verification accuracy by statement mechanism | `scripts/make_thesis_figures.py` (`fig6_mechanism`) | `postretrieval-combined-15-18` |
| Figure 4.6, the supported-subsumption stratum | `scripts/make_thesis_figures.py` (`fig3_subclass_omission`) | `postretrieval-combined-15-18` |

### Tables and in-text numbers

| Dissertation | Source | Pinned by `check_thesis_numbers` section |
|---|---|---|
| Table 3.1, derivation and chunk boundary of the seven serialisations | `app/document_loaders.py`, `scripts/tangle_*.py`, [the corpus](#the-ontology-corpus) | 3.2 |
| Table 3.2, corpus statistics per serialisation | the chunkers and the FAISS indexes (needs the licensed ontology; indexes built by [step 5](#how-to-check-and-reproduce)) | 3.2 (`tab:corpus`) |
| Table 3.3, benchmark composition | `experiment/benchmark/tasks_60.yaml` | 3.3 (`tab:benchmark`) |
| Chapter 3 analysis plan: bootstrap over items, Holm, minimum effect of interest | `scripts/diagnostics/verification_headline_selective.py`, `scripts/diagnostics/collapsed_group_sensitivity.py`; frozen outputs in `scripts/diagnostics/results/` | 4.5 |
| Chapter 3 "What is not reportable": per-class intervals 0.40 to 0.49 wide | `scripts/diagnostics/verification_per_class_intervals.py` | 4.2 |
| Table 4.1, run integrity and trial stability | `postretrieval-combined-15-18` (raw, variance) | 4.1 (`tab:integrity`) |
| Table 4.2, verification performance by model | `postretrieval-combined-15-18` | 4.2 (`tab:verification-models`) |
| Table 4.3, abstention split by gold presence | `postretrieval-combined-15-18`; analysis in [`docs/findings/oracle-undetermined-degeneracy.md`](docs/findings/oracle-undetermined-degeneracy.md) | 4.2 (`tab:gold-gating`) |
| Table 4.4, Probe B2 (explicit open-world instruction) | `experiment/results/probe_b2_openworld/`, run by `scripts/diagnostics/probe_b2_openworld.py`; tabulated by `scripts/diagnostics/probe_b2_analyse.py` into `docs/findings/oracle-undetermined-degeneracy/probe_b2_*.csv` | not covered; see the analysis script |
| Table 4.5, citation fields by condition | `postretrieval-combined-15-18` | 4.3 (`tab:citation-fields`) |
| Tables 4.6-4.7, retrieval by serialisation and by query wording | `retrieval-trial-14` | 4.4 (`tab:retrieval-formats`, `tab:query-source`) |
| Table 4.8, headline results by serialisation | `retrieval-trial-14`, `postretrieval-combined-15-18`, `scripts/diagnostics/results/` | 4.5 (`tab:headline-formats`) |
| Table 4.9, inference depth vs presentation | `postretrieval-combined-15-18` | 4.6 (`tab:depth`) |
| Table 4.10, retrieval failure mechanisms | `retrieval-trial-14` and the FAISS indexes (needs the licensed ontology) | 4.7 (`tab:retrieval-mechanisms`) |
| Table 4.11, the resolvable serialisation effect, by model | `postretrieval-combined-15-18` | 4.7 (`tab:format-by-model`) |
| Section 4.8 and Table D.1, the schema-concept condition | `experiment/results/postretrieval-combined-8-9/`, `experiment/results/superseded/retrieval-trial-11/`; method: [`experiment/voicebox_style_lis14_schema_concept_chunking.md`](src/rag/experiment/voicebox_style_lis14_schema_concept_chunking.md) | 4.8 (`tab:schema-concept-pilot`) |
| Section 4.8 and Table E.1, the whole-context condition | `experiment/results/postretrieval-trial-12/`; the 2026-08-13 entry of `experiment/CHANGELOG.MD` | 4.8 (`tab:whole-context-t02`) |
| Abstract, Chapter 1 and Chapter 5 numbers | the headline data above | "Abstract and introduction", "Discussion" |

### Instrument, configuration and appendices

| Dissertation | Where it is |
|---|---|
| Models, temperature, seeds, k, embedding model, context and generation caps | [`src/rag/experiment/config.py`](src/rag/experiment/config.py); recorded per run in each results directory's `manifest.json` |
| Appendix A, system prompts | [`experiment/prompts/verification_system_v1.txt`](src/rag/experiment/prompts/verification_system_v1.txt), [`experiment/prompts/slot_filling_system_v4.txt`](src/rag/experiment/prompts/slot_filling_system_v4.txt) (earlier versions alongside) |
| Appendix B, derived-serialisation generation | `scripts/tangle_jsonld.py`, `scripts/tangle_yamlld.py`, `scripts/tangle_ofn.py`; gates in `scripts/verify_ontology_chunkers.py` |
| Appendix B, benchmark authoring record | `experiment/benchmark/authoring_constraint_measurements.json`, `experiment/benchmark/authoring_allocation.yaml`, [`docs/authoring/`](docs/authoring/); the authoring scripts are listed in [`src/rag/scripts/README.md`](src/rag/scripts/README.md) |
| Appendix B, prompt version history and every methodological decision | [`src/rag/experiment/CHANGELOG.MD`](src/rag/experiment/CHANGELOG.MD), the contemporaneous log, kept exactly as written |
| Appendix B, determinism probe | `experiment/results/determinism-probe-1/` |
| Appendix B, the unrun `oracle_padded` condition | `experiment/config.py` (selectable, never run on the 60 items) |
| Appendix C, release: the benchmark and its SHA-256 | `experiment/benchmark/tasks_60.yaml`; why the digest only matches with CRLF line endings: [`experiment/results/README.md`](src/rag/experiment/results/README.md#checking-task_file_sha256) |
| Analysis writeups the chapters were written from | [`docs/findings/`](docs/findings/README.md), starting with [`60task-analysis.md`](docs/findings/60task-analysis.md) |

## Repository layout

```
README.md                       this file
docs/
  findings/                     analysis writeups built on the frozen CSVs
  authoring/                    benchmark authoring record (candidate pools)
  ido-assistant/                requirements, architecture, phase-one report and demos
                                of the original web application
src/
  rag/                          the study (and the web app's RAG service)
    data/                       where a licensed copy of the ontology goes (SHA256SUMS)
    app/                        chunkers (document_loaders.py) and the RAG service
    experiment/                 the experiment harness
      config.py                 every pinned setting
      benchmark/                tasks_60.yaml, its schema and authoring measurements
      prompts/                  system prompts, all versions
      results/                  frozen run outputs (see its README)
      tests/                    pytest suite for the harness
      CHANGELOG.MD              contemporaneous methodology log
    scripts/                    corpus generation, verification, merging, figures
      diagnostics/              thesis-number check and the analysis behind the chapters
    eval/                       the web app's earlier competency-question evaluation
  frontend/, backend/           the original IDO Assistant web application
```

[`src/rag/scripts/README.md`](src/rag/scripts/README.md) says what each script is for.

## The ontology corpus

The corpus is the Industrial Data Ontology at its FDIS stage (LIS-14, in the ISO process
as ISO 23726-3), identified by `owl:versionIRI
<http://rds.posccaesar.org/ontology/lis14/ont/core/4.2>` and `owl:versionInfo` "4.2 FDIS
proposal submitted April 2026", downloaded on 1 May 2026 from the POSC Caesar
announcement of the FDIS release. It is licensed material and is **not redistributed
here**, and neither is anything that carries its text:

- The six corpus files are absent from `src/rag/data/`;
  [`src/rag/data/SHA256SUMS`](src/rag/data/SHA256SUMS) records the SHA-256 of each file
  the study used.
- The `user_content` column (the full prompt, which embeds the context chunks) is blank
  in every committed `postretrieval_raw.csv` and `*rescored.csv`, and `actual_context`
  is blank in the web app's `eval/results/*/results_raw.csv`. Every other column,
  including the chunk ids, model responses, grades, token counts and costs, is unchanged.
- In `experiment/benchmark/authoring_constraint_measurements.json`, each quoted
  annotation (`annotation_fragments`) keeps its entity id but its text is withheld; the
  screen outcomes and counts are unchanged.
- The FAISS indexes, which embed the chunk text, are not committed.

Short quotations remain where the analysis needs them: a definition quoted in a writeup,
the prose fragment a benchmark item records, a model's answer.

### With a licensed copy

1. Put the canonical Turtle at `src/rag/data/LIS-14-for-FDIS (1).ttl` (that exact
   name) and confirm it is the study's copy:

   ```bash
   cd src/rag/data && sha256sum -c SHA256SUMS --ignore-missing
   ```

2. Regenerate the derived serialisations beside it. Three come from scripts here and
   reproduce the study's files byte for byte:

   ```bash
   cd src/rag
   python -m scripts.tangle_jsonld                             # .jsonld (rdflib)
   python -m scripts.tangle_yamlld                             # .yamlld (same object, YAML emit)
   ROBOT_JAR=/path/to/robot.jar python -m scripts.tangle_ofn   # .ofn (ROBOT 1.9.10, Java 11+)
   ```

   The `.org` file (both ELOT serialisations) and the `.omn` file come from the ELOT
   toolchain in Emacs (exporter 0.10.1), outside this repository: export the canonical
   Turtle to Org with ELOT, tangle that Org file to Manchester syntax, and delete the
   `rdfs:label "core ontology"` that ELOT injects on the ontology frame of the `.omn`
   (the canonical graph does not carry it). Save them as `LIS-14-for-FDIS (1).org` and
   `LIS-14-for-FDIS (1).omn`. `sha256sum -c SHA256SUMS` then checks all six; if an ELOT
   build differs in bytes, `verify_ontology_chunkers` checks the content (step 3 below).

3. The chunks are not stored anywhere: the loaders in `app/document_loaders.py` cut them
   from these files on every run. The FAISS indexes are built by the retrieval stage
   (step 5 below, which makes paid embedding calls) into `src/rag/experiment/indexes/`.

`.gitignore` keeps the corpus files out of commits.

### What needs the licensed copy

| Check or tool | On a fresh clone | With the licensed copy |
|---|---|---|
| `check_thesis_numbers` (step 1) | 442 of 518 checks run and pass; `check_corpus`, `check_crowding` and the index-reading part of `check_appendix_b` (76 checks) skip with "needs the licensed ontology" | `check_corpus`'s Turtle checks run; with the FAISS indexes as well, all 518 pass |
| harness tests (step 2) | 31 pass; 6 skip for the corpus files and 7 for the withheld prompt text | 37 pass; the 7 that regrade a stored run from its prompt text still skip, because that text is not in this release |
| `verify_ontology_chunkers` (step 3) | skips, naming the missing files | runs every gate |
| merge (step 0), figures, `verification_per_class_intervals` | unaffected | unaffected |
| experiment stages (steps 4-6), `tangle_*.py`, the benchmark authoring scripts, `verify_undetermined_items.py`, `verify_whole_context_phase1.py`, the web app | need the corpus | run |
| `experiment/rescore.py` | stops with an explanation on the committed outputs, which carry no prompt text | works on run outputs you produce yourself |

## How to check and reproduce

Everything runs from `src/rag/` in a Python **3.13** virtual environment, the version
[`src/rag/Dockerfile`](src/rag/Dockerfile) pins and the study ran on. The requirements
are pinned to exact versions, and several have no wheels for 3.14 (the install fails
building `pydantic_core` and `scikit-network` from source).

```bash
cd src/rag
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Steps 0-2 run on a fresh clone, offline and free. Step 3 needs the
[licensed ontology](#the-ontology-corpus); steps 4-6 need it too and call paid APIs.

```bash
# 0. Rebuild the one result file that is not committed (~1 min).
#    The merged postretrieval_raw.csv of the RQ2 headline directory (80MB) is
#    regenerated from the committed per-model trials rather than stored twice.
#    Merge into a scratch directory, then move only that file into place, so the
#    committed scored/variance/diagnostics tables are left untouched:
python -m scripts.merge_postretrieval_trials \
    --sources experiment/results/postretrieval-trial-15 \
              experiment/results/postretrieval-trial-16 \
              experiment/results/postretrieval-trial-17 \
              experiment/results/postretrieval-trial-18 \
    --output  /tmp/combined-15-18
mv /tmp/combined-15-18/postretrieval_raw.csv \
   experiment/results/postretrieval-combined-15-18/
#    The scratch copy also shows the merge reproduces the committed tables. The
#    originals were written on Windows, so strip CRs before comparing:
#      tr -d '\r' < experiment/results/postretrieval-combined-15-18/postretrieval_scored.csv | sha256sum
#      tr -d '\r' < /tmp/combined-15-18/postretrieval_scored.csv | sha256sum

# 1. Check every number in the dissertation against the frozen CSVs:
python -m scripts.diagnostics.check_thesis_numbers
#    On a fresh clone 442 of the 518 checks run and pass; the 76 that read the ontology
#    or the FAISS indexes built from it skip with "needs the licensed ontology". With a
#    licensed copy and the indexes (step 5), all 518 pass.

# 2. Run the harness test suite (tests that need the licensed ontology skip, saying so):
python -m pytest experiment/tests -rs

# 3. Verify the chunkers and serialisation parity (needs the licensed ontology):
python -m scripts.verify_ontology_chunkers
#    Set ROBOT_JAR=/path/to/robot.jar (ROBOT v1.9.10, Java 11+) to also run the
#    ofn/omn whole-graph equality checks; without it they skip.

# 4. Smoke gate (2 API calls, must pass before the stages unlock):
python -m experiment.run_experiment --stage smoke

# 5. RQ1 retrieval stage (builds the seven FAISS indexes; embedding calls):
python -m experiment.run_experiment --stage retrieval --task-file experiment/benchmark/tasks_60.yaml

# 6. RQ2 post-retrieval stage (graded LLM calls):
python -m experiment.run_experiment --stage postretrieval --task-file experiment/benchmark/tasks_60.yaml
```

Requirements and costs for steps 4-6:

- `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` in `src/.env` (copy
  [`src/.env.example`](src/.env.example)). **These stages cost money**: the full
  60-item post-retrieval factorial is thousands of calls, and each run writes its exact
  cost into its `manifest.json`.
- The Llama arm needs [Ollama](https://ollama.com) on `localhost:11434` with
  `llama3.1:8b-instruct-q8_0` pulled (free, local, slow).
- Every run writes a trial-numbered directory under
  [`src/rag/experiment/results/`](src/rag/experiment/results/) with a `manifest.json`
  pinning serialisations, models, seeds, task-file SHA-256 and cost. The FAISS indexes
  go to `experiment/indexes/` (not committed: they are binaries rebuilt by step 5).

## Regenerating the figures

Both figure scripts run from `src/rag/`, read only the committed CSVs (plus the step-0
merged file), and fail loudly if a plotted value disagrees with the documented one:

```bash
python -m scripts.make_thesis_figures  --out <dir>          # Figures 4.1-4.6
python -m scripts.make_methods_figures --out <dir>          # Figures 1.1, 3.1, 3.3, 3.4
python -m scripts.make_thesis_figures  --out <dir> --slide  # seminar versions, <name>_slide.pdf
python -m scripts.make_methods_figures --out <dir> --slide
```

The `--slide` versions are drawn at the size the seminar deck places them, and use the
dissertation's prose terms "serialisation" and "gold" where the thesis versions keep
the code's `format` and `oracle`; both say "arm" for the model factor, as the
dissertation's figures and tables do.

To reproduce the dissertation's PDFs **pixel for pixel**, two things matter beyond the
data:

- **matplotlib 3.11.2.** `requirements.txt` pins 3.10.7 for the harness; 3.10 lays the
  figures out a few pixels differently. Install 3.11.2 into a separate environment for
  the figures (`pip install matplotlib==3.11.2 numpy==2.3.3 pandas==2.3.3`).
- **The Segoe UI font.** Without it, text falls back to Arial or DejaVu Sans and every
  figure shifts. On Linux or WSL with a Windows font directory available, expose it
  through fontconfig:

  ```bash
  cat > /tmp/fonts.conf <<'EOF'
  <?xml version="1.0"?>
  <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
  <fontconfig>
    <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
    <dir>/mnt/c/Windows/Fonts</dir>
  </fontconfig>
  EOF
  export FONTCONFIG_FILE=/tmp/fonts.conf
  ```

With both in place and `SOURCE_DATE_EPOCH=0` set, the output is byte-identical from
run to run and pixel-identical to the figures in the dissertation.

## Provenance notes

- **Frozen results are never edited.** Each results directory is the output of one run
  (or a recorded merge of runs); superseded pilots are archived under
  [`results/superseded/`](src/rag/experiment/results/superseded/README.md), not
  deleted.
- **This is a history-free release.** The study was developed in a private repository;
  this public repository is a snapshot of it without the commit history. Commit hashes
  quoted in the methodology log, the findings and the test comments refer to that
  development history.
- **The benchmark digest.** Manifests record the SHA-256 of `tasks_60.yaml` as it was on
  disk on Windows, with CRLF line endings; hashing a Linux or macOS checkout gives a
  different digest for the same content. The one-line check is in
  [`experiment/results/README.md`](src/rag/experiment/results/README.md#checking-task_file_sha256).
- **Licensed material not redistributed.** Neither the ontology corpus nor any output
  carrying its text is included ([the ontology corpus](#the-ontology-corpus)), and the
  ISO and POSC Caesar standards documents used while building the original web
  application are not either; see
  [`src/rag/README.md`](src/rag/README.md#source-material-not-redistributed).

## The web application (the original IDO Assistant)

The study grew out of the IDO Assistant, a RAG web application that introduces the
Industrial Data Ontology to businesses without ontology expertise. Its design documents,
phase-one report and demo videos are in [`docs/ido-assistant/`](docs/ido-assistant/).
It is split into four docker-compose services
([`src/docker-compose.yml`](src/docker-compose.yml)):

- **`frontend`** (Next.js + TailwindCSS): query input, responses, history, and
  expandable retrieval sources; calls the backend API.
- **`backend`** (Django API): relays queries from the frontend to the rag service.
- **`rag`** (LangChain + FastAPI): performs the retrieval-augmented generation; see
  [`src/rag/README.md`](src/rag/README.md). The experiment harness reuses this
  service's chunkers.
- **`postgres`**: reserved for future users/history storage (currently unused).

To run it: put a licensed copy of the ontology in `src/rag/data/`
([the ontology corpus](#the-ontology-corpus)); install Docker, Python 3.13 and Node.js
18+; copy
[`src/.env.example`](src/.env.example) to `src/.env` and fill in `OPENAI_API_KEY`
(and `LANGSMITH_API_KEY` if using tracing); then from `src/` run `docker-compose up`
and visit http://localhost:3000. The web app's earlier competency-question evaluation
lives in [`src/rag/eval/`](src/rag/eval/) (`python -m eval.main`).
