# Scripts

Every script runs from `src/rag/` as a module, for example
`python -m scripts.verify_ontology_chunkers`. Each one's docstring gives its exact
inputs, outputs and usage. Nothing here calls a paid API except where noted.

## Checking the dissertation

| Script | What it does |
|---|---|
| `diagnostics/check_thesis_numbers.py` | Asserts every quantitative claim in the dissertation against the frozen CSVs (518 checks). Needs README step 0; three groups also need the FAISS indexes. |
| `make_thesis_figures.py` | Regenerates the six results-chapter figures (Figures 4.1-4.6) and asserts their plotted values; `--slide` writes the seminar versions. |
| `make_methods_figures.py` | Regenerates the methods diagrams (Figures 1.1, 3.1, 3.3, 3.4); `--slide` writes the seminar versions. |

## Analysis behind the chapters (`diagnostics/`)

All read the frozen results and make no API calls unless stated. Outputs that
`check_thesis_numbers` pins are committed under `diagnostics/results/`.

| Script | What it computes |
|---|---|
| `verification_headline_selective.py` | The verification headline family: per-serialisation coverage and accuracy on answered over the 20 determinate items, 21 paired contrasts, item bootstrap, Holm. |
| `collapsed_group_sensitivity.py` | The slot-filling sensitivity analysis that collapses the two duplicate-shape item groups before resampling (30 to 24 items). |
| `verification_per_class_intervals.py` | Per-class precision, recall and F1 on the verification labels with item-bootstrap intervals (the 0.40 and 0.49 widths the chapters cite). |
| `phase0_undetermined_audit.py` ... `phase1e_undetermined_audit.py` | The staged audit of why models rarely answer `undetermined` (writeup: `docs/findings/oracle-undetermined-degeneracy.md`). |
| `probe_b2_openworld.py` | Runs Probe B2, the explicit open-world instruction (paid API calls; output in `experiment/results/probe_b2_openworld/`). |
| `probe_b2_analyse.py` | Tabulates Probe B2 (Table 4.4) into `docs/findings/oracle-undetermined-degeneracy/`. |

## Building and verifying the corpus

| Script | What it does |
|---|---|
| `tangle_jsonld.py`, `tangle_yamlld.py`, `tangle_ofn.py` | Generate the JSON-LD, YAML-LD and OFN serialisations from the canonical Turtle (OFN needs ROBOT 1.9.10). |
| `verify_ontology_chunkers.py` | Verifies every chunker and the parity, isomorphism and checksum gates across serialisations. |
| `verify_whole_context_phase1.py` | Measurement and runtime gates for the whole-context condition. |

## Running and merging

The experiment itself runs through `python -m experiment.run_experiment` (see the root
README). One script here post-processes runs:

| Script | What it does |
|---|---|
| `merge_postretrieval_trials.py` | Merges the per-model post-retrieval trials into one combined results directory (README step 0). |

## Authoring the benchmark

Used while the 60 items were written; kept as the record of how candidates were
enumerated and gated (Appendix B).

| Script | What it does |
|---|---|
| `generate_bare_disjointness_candidates.py` | Batch 1: bare-disjointness candidate report. |
| `generate_supported_subsumption_candidates.py` | Batch 2: supported-subsumption candidate report. |
| `generate_chain_recoverability_report.py` | Chain-aware recoverability for every Batch 2 supported subsumption. |
| `generate_slotfilling_candidates.py` | Batch 4: blinded slot-filling candidate pool. |
| `measure_authoring_candidate_pools.py` | Measures the candidate pools per stratum without selecting items. |
| `regenerate_authoring_allocation.py` | Rebuilds `experiment/benchmark/authoring_allocation.yaml` from measured metadata. |
| `check_authoring_candidate.py` | Assesses one draft item against the authoring constraints. |
| `verify_authoring_constraints.py` | Runs the full authoring constraints over the complete benchmark. |
| `verify_undetermined_items.py` | Verifies two-sided non-entailment for the `undetermined` items. |

## Utility

| Script | What it does |
|---|---|
| `count_tokens.py` | Counts the `cl100k_base` tokens in one file. |
