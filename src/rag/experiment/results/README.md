# Experiment results (frozen, load-bearing runs)

Every directory here is read by a committed script or cited by the dissertation.
Earlier pilots are archived under [`superseded/`](superseded/README.md). Each run
directory carries a `manifest.json` recording the exact formats, models, conditions,
task file (with SHA-256), seeds and pricing snapshot for that run.

**Prompt text withheld.** The `user_content` column of every `postretrieval_raw.csv`
and `*rescored.csv` here is blank: it held the full prompt, which embeds the licensed
ontology's chunks (see the root README, "The ontology corpus"). Every other column,
including `context_chunk_ids`, `context_char_len`, the model's `raw_response`, the
grades, token counts and costs, is exactly as the run wrote it.

Two scripts pin the thesis to these files and fail loudly on any mismatch
(run both from `src/rag/`):

- `python -m scripts.diagnostics.check_thesis_numbers` asserts every quantitative
  claim in the abstract and Chapters 1, 3, 4 and 5 against these CSVs.
- `python -m scripts.make_thesis_figures --out <dir>` regenerates the six
  results-chapter figures from the same CSVs (`--slide` writes the seminar-deck
  versions instead, under the same assertions).

## Checking `task_file_sha256`

The runs were executed on Windows, so each manifest records the SHA-256 of the task
file *as it was on disk there*, with CRLF line endings. Hashing a checkout on Linux
or macOS gives a different digest for the same committed bytes, which looks like a
mismatch and is not one. To reproduce the recorded digest from any platform:

```bash
# from src/rag/ -- prints the digest the manifests record
sed 's/$/\r/' experiment/benchmark/tasks_60.yaml | sha256sum
```

For the current benchmark that is `36cb27c1...`, the value in every 60-item run's
manifest. Two superseded runs record `96b79238...` and `692faa9c...`, which are the
same file at its 38-item and 53-item stages in the study's development history
(this public release carries no git history).

## The headline runs (the 60-item factorial: 7 formats x 2 conditions x 4 arms)

### `postretrieval-combined-15-18` (2026-08-20): the RQ2 headline

The frozen 60-item answer-quality run, merged by `scripts/merge_postretrieval_trials.py`
from the four single-arm runs `postretrieval-trial-15` (gpt-4o), `-16` (gpt-4o-mini),
`-17` (claude-sonnet-4-5) and `-18` (llama3.1:8b), which are kept alongside as the
merge inputs. 60 items x 7 formats x 2 conditions (oracle, retrieved) x 4 arms x 3 trials.

- `postretrieval_raw.csv`: one row per LLM call: full prompt/response, token counts,
  cost, parse status. Source for the token and cost numbers and for every offline regrade.
- `postretrieval_scored.csv`: the graded rows (per-field grades, coverage covariates).
  Feeds the RQ2 accuracy figures and tables and almost all of `check_thesis_numbers`.
- `postretrieval_variance.csv`: per-cell across-trial agreement. Feeds the stability
  reporting.
- `postretrieval_diagnostics.json`: automated flags (ceilings, degenerate cells)
  computed at run time.

### `retrieval-trial-14` (2026-08-19): the RQ1 headline

The frozen retrieval run: all 60 items x 7 formats, k=5, deterministic (no
generation). `retrieval_raw.csv` (per task x format: retrieved chunk ids, recall@k,
gold recall@k, MRR, nDCG) feeds the recall figures and the RQ1 sections;
`retrieval_scored.csv` is the per-format aggregation.

## Exploratory conditions (outside the factorial)

- `postretrieval-combined-8-9` (2026-07-30): the schema-concept pilot: 5 items,
  8 formats (the 7 factorial formats plus `schema-concept`), 3 arms, N=3, merged from
  trials 8 and 9. `postretrieval_rescored.csv` is the offline strict regrade of the
  same rows. Feeds the short schema-concept results section.
- `postretrieval-trial-12` (2026-08-13): the whole-context pilot: T02 and T04, all
  7 formats, 3 arms, N=3, condition `whole_context` (entire serialisation in the
  prompt instead of retrieved chunks). Feeds the short whole-context results section.

## Appendix probes

- `probe_b2_openworld` (2026-09-02): the open-world reprompt probe behind the
  oracle-undetermined degeneracy analysis (`docs/findings/oracle-undetermined-degeneracy.md`);
  read by `check_thesis_numbers` and `scripts/diagnostics/probe_b2_analyse.py`.
- `determinism-probe-1` (2026-08-13): repeat-call determinism measurement
  (`determinism_raw.csv`, `determinism_summary.csv`); read by `check_thesis_numbers`
  for the determinism appendix numbers.

## Related evidence elsewhere

- `../CHANGELOG.MD`: the contemporaneous methodology log (why each run was made).
  Deliberately untidied; its entries refer to archived runs by their original names.
- `docs/findings/`: the analysis writeups built on these CSVs.
- `../../scripts/diagnostics/results/`: frozen derived CSVs (paired contrasts,
  collapsed-group sensitivity) computed from the headline run and pinned by
  `check_thesis_numbers`.
