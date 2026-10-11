# Superseded runs (archive)

These directories are earlier pilots and shakeout runs kept for provenance. None of them
feeds a thesis number, table or figure; the frozen, load-bearing runs are documented in
[`../README.md`](../README.md). The methodology log
(`../../CHANGELOG.MD`) records why each run was made and what was learned from it, and its
historical entries still refer to these directories by their original (unprefixed) names.

Dates are the `timestamp_utc` recorded in each directory's `manifest.json`.

## Retrieval stage pilots (RQ1)

All superseded by `../retrieval-trial-14` (2026-08-19, all 60 items, 7 formats, the frozen
retrieval headline).

| directory | date | what it was |
|---|---|---|
| `retrieval-trial-1` | 2026-05-29 | first pipeline shakeout: 2 tasks (T01-T02), 3 formats (turtle, elot-org, omn), unpinned gpt-4o/gpt-4o-mini |
| `retrieval-trial-2` | 2026-06-06 | 2 tasks, 4 formats (adds elot-org-ancestors), unpinned models |
| `retrieval-trial-3` | 2026-06-07 | repeat of the 2-task, 4-format shape |
| `retrieval-trial-4` | 2026-06-07 | repeat of the 2-task, 4-format shape |
| `retrieval-trial-5` | 2026-06-07 | 5 tasks (T01-T05), 4 formats, pinned GPT snapshots |
| `retrieval-trial-6` | 2026-06-07 | repeat of the 5-task, 4-format shape |
| `retrieval-trial-7` | 2026-06-28 | repeat of the 5-task, 4-format shape |
| `retrieval-trial-8` | 2026-07-17 | 5 tasks, all 7 factorial formats |
| `retrieval-trial-9` | 2026-07-30 | turtle vs schema-concept, 5 tasks, 3 models (exploratory condition) |
| `retrieval-trial-10` | 2026-07-30 | turtle vs schema-concept repeat, 5 tasks, 3 models |
| `retrieval-trial-11` | 2026-07-30 | 8 formats (7 factorial + schema-concept), 5 tasks, 3 models |
| `retrieval-trial-12` | 2026-08-19 | 38 tasks (T06-T43), 7 formats, during 60-item benchmark authoring |
| `retrieval-trial-13` | 2026-08-19 | 53 tasks, 7 formats; the pre-run checklist B3 run (see `docs/findings/pre-run-checklist.md`) |

## Post-retrieval stage pilots (RQ2)

All superseded by `../postretrieval-combined-15-18` (2026-08-20, the frozen 60-item, 7-format,
4-arm headline merged from `../postretrieval-trial-15..18`), except where a directory served a
one-off purpose noted below.

| directory | date | what it was |
|---|---|---|
| `postretrieval-trial-1` | 2026-06-07 | 5 tasks, 4 formats, 2 GPT arms, N=3: first post-retrieval pilot |
| `postretrieval-trial-2` | 2026-06-28 | 5 tasks, 4 formats, Llama arm, N=3 |
| `postretrieval-trial-3` | 2026-07-16 | T05 only, oracle only, 5 formats, Llama: jsonld loader debug probe |
| `postretrieval-trial-4` | 2026-07-17 | 5 tasks, 7 formats, 2 GPT arms, N=3: the 420-call pilot. Still read by `experiment/tests/test_harness_changes.py` as the pinned ground truth for the offline regrader acceptance tests |
| `postretrieval-trial-5` | 2026-07-23 | 5 tasks, 7 formats, 3 arms, N=3, plus the abandoned `oracle_padded` condition |
| `postretrieval-trial-6` | 2026-07-30 | turtle vs schema-concept, 2 GPT arms, N=1: first schema-concept pilot (drove the CHUNK ID prompt fix in `app/document_loaders.py`) |
| `postretrieval-trial-7` | 2026-07-30 | turtle vs schema-concept repeat, 2 GPT arms, N=1 |
| `postretrieval-trial-8` | 2026-07-30 | 8 formats (7 + schema-concept), Llama arm, N=3: merged into `../postretrieval-combined-8-9` |
| `postretrieval-trial-9` | 2026-07-30 | 8 formats, 2 GPT arms, N=3: merged into `../postretrieval-combined-8-9` |
| `postretrieval-trial-10` | 2026-08-04 | no-context / empty-context floor, 5 tasks, 3 arms, N=3 (5-task-era floor; the 60-item floors live inside the headline run) |
| `postretrieval-trial-11` | 2026-08-13 | whole-context, 2 formats, 3 arms, T02/T04, N=1: superseded by `../postretrieval-trial-12` |
| `postretrieval-trial-13` | 2026-08-19 | smoke for the 60-item run: T06+T29, 7 formats, 4 arms, N=1; the pre-run checklist B7 run |
| `postretrieval-trial-14` | 2026-08-19 | Sonnet contamination floor: 23 verification items, no-context / empty-context, N=1; the pre-run checklist B8 run |
