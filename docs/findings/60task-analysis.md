# 60-task benchmark — analysis

**Date:** 2026-08-20 · **Scope:** analysis only, zero API and zero Ollama calls · **Graders unchanged.**

**Inputs.** `experiment/results/postretrieval-combined-15-18/` (the merged 4-arm run: 10,080 raw
rows, 3,360 scored cells) and `experiment/results/retrieval-trial-14/` (420 rows). Both carry
`task_file_sha256 = 36cb27c1…8bd1148`, which matches `experiment/benchmark/tasks_60.yaml` as
committed. The five-task pilot and `tasks.yaml` (`31db3256…`) are used for **contrast only** and are
never pooled.

**Reading order.** §1 must be read before any result, because the spec's stop condition 3 fires: two
of the four arms show a label collapse on verification under `oracle`, reported in §6.1 before any of
their results are interpreted. §2 and §3 are the headline results.
§4 is where the study's one resolvable format effect actually lives — and it is not where the
benchmark was designed to look for it.

---

## 0. The one-line result

**No format contrast in this study is both statistically resolvable and larger than one graded
field.** Across the three headline families (RQ1 recall@5, RQ2 verification accuracy, RQ2
slot-filling partial credit), 0 of 21 paired format contrasts per family reach nominal p < 0.05 on
the pooled 60 items, 0 survive Holm correction, and 0 clear the resolution threshold. The largest
spread across seven formats on any headline metric is **0.033** (verification accuracy) and
**0.024** (slot-filling partial credit).

One effect does clear everything, and it is a **local, mechanism-specific** one: on the two items
whose licensing axiom is a *directly asserted* one-hop `rdfs:subClassOf`, `elot-org-ancestors` — the
only arm that does not serialise that axiom as an explicit statement — scores **0.313 against 0.747**
for the other six formats, ranks last of seven on both items, and loses on 30 of 48 cells while
winning 0. On the eight *entailed multi-hop* items of the same stratum the gap is **+0.055**
[−0.084, +0.171] — gone. §4.1 develops this.

Everything else that matters in these results is a **condition** effect, not a format effect:
oracle-versus-retrieved is worth **0.32–0.37** on slot-filling partial credit, an order of magnitude
larger than any format difference.

---

## 1. Integrity checks

| # | Check | Result |
|---|---|---|
| 1 | Row completeness | **PASS** |
| 2 | Manifest / task-file hash | **PASS** |
| 3 | Truncation guard | **PASS** (0 trips) |
| 4 | Parse failures | **PASS** (2 / 10,080, both explained) |
| 5 | Cost reconciliation | **PASS against the caching-on projection**; provider-export reconciliation outstanding |
| 6 | Graded stability | **Materially different from the pilot — 96.3% vs 81%.** Stop condition 5 fires; see §1.6 |
| — | Degenerate label behaviour | **STOP CONDITION 3 FIRES** — see §6.1 |

### 1.1 Row completeness — PASS

Expected 60 × 7 × 2 × 3 × 4 = **10,080**; observed **10,080**. 3,360 unique
`(task, format, condition, model)` cells, every one with exactly 3 trials. Zero missing cells, zero
unexpected cells, zero duplicate call keys `(task, format, condition, model, trial_idx)`.

### 1.2 Manifest — PASS

Both the retrieval and post-retrieval manifests record `task_file: experiment\benchmark\tasks_60.yaml`
**and** `task_file_sha256: 36cb27c19043accafe6d7e1ea3294eb0c98dee812b760d51d61d2bdac8bd1148`, which
is the live hash of that file. The five-task pilot file hashes to `31db3256…`, so the run is
unambiguously attributable. `trial_seed_map` = {0: 20260529, 1: 20260530, 2: 20260531}; pricing
snapshot `2026-06-07` with cache snapshot `2026-08-13`; `cached_prompt_tokens` present on every row;
`ollama_num_ctx: 16384`, `ollama_kv_cache_type: q8_0`; all four provider/model pins recorded; all four
source trials at git commit `2902414`.

**One manifest field is wrong and must not be cited.** `seed_determinism` labels the Anthropic arm
`pinned` although the Anthropic API has no seed parameter, and labels both GPT-4o arms `pinned`
although CHANGELOG 2026-08-04 (e) retracted exactly that claim. This is already flagged in
CHANGELOG 2026-08-20 (b) as recorded-not-fixed. §1.6 supplies the measured replacement.

### 1.3 Truncation guard — PASS, 0 trips

`llm_call._call_ollama` raises on any deviation greater than 64 tokens between the returned
`prompt_eval_count` and the locally computed count, so a trip aborts the run. All 2,520 Llama rows
are present, therefore the guard never fired. Independently: the maximum Llama prompt in the run is
**6,864 tokens** against `num_ctx = 16,384` — 2.39× headroom, and **zero** rows exceed `num_ctx / 2`,
which is the threshold at which Ollama's silent-halving behaviour would bite.

### 1.4 Parse failures — 2 of 10,080 (0.02%)

| task | format | condition | trial | model | finish_reason | completion tokens |
|---|---|---|---|---|---|---|
| T18 | ofn | oracle | 0 | llama3.1:8b | `length` | 1024 |
| T22 | elot-org-ancestors | retrieved | 0 | llama3.1:8b | `length` | 1024 |

Both are the `OLLAMA_NUM_PREDICT = 1024` cap firing on a degenerate JSON loop, exactly as CHANGELOG
2026-08-20 predicted and intended: a degenerate response is now *recorded* as a parse error rather
than killing the run. Neither is a context-window truncation. Every other arm returned a clean stop
(`stop` for both OpenAI arms, `tool_use` for all 2,520 Anthropic rows).

Both failures are graded conservatively as non-answers: `answered = 0`, `correct = 0`,
`pred_label = (unparsed)`. They affect one trial each of two cells, and both cells retain two clean
trials.

**The JSON-LD emission fix held.** Zero of 10,080 raw responses contain `@context`.

### 1.5 Cost reconciliation

The manifest's `$50.71` is the **uncached** ledger — `summarise_cost` bills every input token at the
full rate by contract. The cache-aware ledger, computed from the recorded `cached_prompt_tokens`, is
**$29.31**.

| arm | prompt tokens | cached | cached share | naive USD | cache-aware USD | saving |
|---|---:|---:|---:|---:|---:|---:|
| claude-sonnet-4-5 | 9,116,448 | 6,295,392 | **69.1%** | 33.08 | **16.08** | 51.4% |
| gpt-4o-2024-11-20 | 5,846,502 | 3,280,896 | **56.1%** | 16.65 | **12.55** | 24.6% |
| gpt-4o-mini | 5,846,502 | 4,068,736 | **69.6%** | 0.98 | **0.68** | 31.0% |
| llama3.1:8b (local) | 5,905,674 | — | n/a | 0.00 | 0.00 | — |
| **total** | | | | **50.71** | **29.31** | **42.2%** |

Per-trial the mechanism is exactly as designed: trial 0 writes the prefix (10–24% cached), trials 1
and 2 read it — sonnet **98.6% / 98.6%**, gpt-4o-mini **91.6% / 93.1%**, gpt-4o **78.8% / 77.4%**.

**Against the pre-run projection** (checklist §B5: $48.36 caching-off, **$28.75 caching-on**), actual
cache-aware spend of $29.31 is **+1.9%** over the caching-on figure. **Stop condition 4 does not
fire.** The gpt-4o arm is the one that underperformed its projected cache rate (77–79% rather than
the ~93% seen in the B7 probe), and it is also the arm whose absolute saving is smallest, so the
shortfall is contained.

**Outstanding, unchanged from B5:** no provider usage export was available, so reconciliation against
actual billing has not been done. The figures above are derived from recorded token counts and the
pinned price tables, not from an invoice.

### 1.6 Graded stability — 96.3%, materially higher than the pilot's 81%

`graded_stability_rate` is not computed anywhere in the harness (checklist §B6 left it outstanding),
so it is computed here with the pilot probe's own definition: **a cell is graded-stable when the full
grade dict is identical across all three trials.**

| arm | cells | graded-stable | rate | raw-stable rate | pilot probe (slot-filling only) |
|---|---:|---:|---:|---:|---:|
| claude-sonnet-4-5 | 840 | 827 | **0.985** | 0.513 | 11/12 = 0.917 |
| gpt-4o-2024-11-20 | 840 | 819 | **0.975** | 0.313 | 9/12 = 0.750 |
| llama3.1:8b | 840 | 800 | **0.952** | 0.735 | not probed |
| gpt-4o-mini | 840 | 790 | **0.941** | 0.346 | 11/12 = 0.917 |
| **all** | **3,360** | **3,236** | **0.963** | **0.477** | **39/48 = 0.813** |

By task type: verification **0.983**, slot-filling **0.943**. Like-for-like against the probe (which
was slot-filling only), 0.943 versus 0.813.

**Stop condition 5 fires — the rate differs materially from the pilot's — but in the safe
direction.** §0's thresholds were set against an assumed "roughly one cell in five" instability; the
measured rate here is roughly **one cell in twenty-seven**. Higher stability makes the stated
resolution thresholds *conservative*, not unsafe, so no threshold is relaxed. Two further facts
support keeping them:

- **Instability magnitude is bounded.** Of 1,680 slot-filling cells, 91 show any within-cell spread
  in partial credit. Of those, 83 (91%) have spread ≤ 0.333 and the maximum is 0.600. So a
  cell-level difference of 0.333 remains inside observed trial noise.
- **The unstable field is still a citation field.** Per-field instability counts:
  `intermediate_correct` 40, `support_property_correct` 33, `support_class_correct` 15,
  `support_intermediate_correct` 14, `class_correct` 10, `property_correct` 10. The answer slots
  `class` and `property` are the most stable in the set, exactly as the probe found.

The correct manifest label to replace `seed_determinism` is therefore a measured
`graded_stability_rate` per arm, from the table above.

---

## 2. RQ1 — Retrieval

Single-trial and deterministic; no trial variance to pool. Recall@5 is against the narrow
`retrieval_gold_chunks` (headline); `gold_recall_at_k` is the broad `gold_chunks` sensitivity check.

### 2.1 Marginals

| format | recall@5 (narrow) | recall@5 (broad) | MRR | nDCG@5 |
|---|---:|---:|---:|---:|
| omn | **0.667** | 0.663 | 0.621 | 0.579 |
| ofn | 0.659 | 0.654 | 0.632 | 0.581 |
| elot-org-ancestors | 0.659 | 0.651 | 0.614 | 0.573 |
| jsonld | 0.653 | 0.660 | **0.671** | 0.594 |
| elot-org | 0.652 | 0.641 | 0.629 | 0.572 |
| turtle | 0.641 | 0.641 | 0.669 | **0.598** |
| yaml-ld | 0.623 | 0.639 | 0.642 | 0.566 |

Spread 0.044 on the headline. Broad recall reorders the middle of the table but not its ends, and no
conclusion below depends on which gold set is used.

By task type the split is large and format-independent: verification **0.779–0.868**, slot-filling
**0.433–0.500**. Slot-filling queries are scenario prose; verification queries mostly name their
classes.

### 2.2 Paired contrasts over items — nothing survives

*Resolution note: retrieval is scored per item with narrow gold sets of 2–5 chunks, so one gold chunk
is 0.200–0.500 of an item's recall.*

Headline family (recall@5, narrow, 21 format pairs, all 60 items, paired bootstrap over items,
B = 20,000):

- **0 of 21** contrasts reach nominal p < 0.05. Expected by chance: ~1.05.
- **0 of 21** survive Holm correction.

Split by task type (a pre-registered breakout):

| subset | nominal p < 0.05 | Holm-significant |
|---|---:|---:|
| verification (30 items) | 3 / 21 | **0** |
| slot-filling (30 items) | 0 / 21 | **0** |

The three nominal verification contrasts are turtle > yaml-ld (+0.071, p = 0.026, p_holm = 0.52),
omn > yaml-ld (+0.089, p = 0.014, p_holm = 0.29), omn > elot-org (+0.064, p = 0.046,
p_holm = 0.88). They point the same way — yaml-ld weakest, omn strongest on verification retrieval —
but none is defensible after multiplicity control, and all are smaller than one gold chunk on a
2-chunk item.

A broader exploratory sweep (336 contrasts across 4 metrics × 4 subsets) produced 24 nominally
significant results — 7.1%, against 5% expected by chance from correlated tests. That ratio is the
correct way to read them: **as a family they are indistinguishable from noise**, and they are
reported here only so that no one mistakes an individually striking cell for a finding.

### 2.3 Format × query_source

Items were authored `label` (29), `paraphrase` (19), `example` (7), `definition` (5). Only paraphrase
requires lexical matching rather than string lookup, so it is where format could plausibly matter
most.

| query_source | n | turtle | elot-org | elot-anc | omn | jsonld | yaml-ld | ofn | spread |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| label | 29 | 0.839 | 0.786 | 0.834 | 0.840 | 0.810 | 0.783 | 0.806 | 0.057 |
| definition | 5 | 0.600 | 0.700 | 0.700 | 0.600 | 0.700 | 0.600 | 0.600 | 0.100 |
| example | 7 | 0.429 | 0.500 | 0.500 | 0.429 | 0.429 | 0.429 | 0.429 | 0.071 |
| **paraphrase** | 19 | 0.430 | 0.491 | 0.439 | 0.509 | 0.483 | 0.456 | **0.535** | **0.105** |

The interaction is in the predicted direction — the format spread is roughly twice as large on
paraphrase as on label, and turtle (the arm with the most punctuation-dense surface) is weakest
there while ofn is strongest. **It is not resolvable, and the subset is not clean.** At n = 19, 0.105
is two items' worth of a single gold chunk, and no paraphrase-subset contrast survives Holm. Worse,
**10 of the 19 paraphrase items are exactly the subclass-omission block** (T35, T40–T43, T44,
T55–T58), which by §4.6 collapses to roughly two effective observations. The paraphrase stratum is
therefore closer to n ≈ 11 than n = 19 and is entangled with a single authored design. Report as a
direction worth a purpose-built benchmark, not as a result.

### 2.4 Gold-set size

All 30 slot-filling items have narrow gold = 2, i.e. `gold < k` throughout, so **gold size cannot
serve as a covariate within slot-filling**, as recorded. Verification varies: 17 items at 2, 10 at 3,
2 at 4, 1 at 5. That single `gold = k` item is the only one where recall@5 requires a perfect ranked
list, and it is too thin to break out.

### 2.5 Replication of the two pilot mechanisms

Both replicate at scale. **Both are format-invariant, which is the finding.**

**Mechanism 1 — property-chunk crowding.** Operationalised on the 23 class-pair items (every narrow
gold chunk is an `owl:Class`; all 23 are verification items): count non-gold object/datatype-property
chunks occupying top-5 slots, and count items where a gold class chunk is missed while ≥ 1 non-gold
property chunk is present.

| format | mean non-gold property chunks in top-5 | crowd-out items / 23 | rate |
|---|---:|---:|---:|
| elot-org | 1.70 | 8 | 0.348 |
| ofn | 1.43 | 7 | 0.304 |
| yaml-ld | 1.43 | 7 | 0.304 |
| jsonld | 1.04 | 6 | 0.261 |
| elot-org-ancestors | 1.22 | 5 | 0.217 |
| turtle | 1.13 | 5 | 0.217 |
| omn | 1.35 | 4 | 0.174 |

**Between one and one-and-a-half of the five retrieved slots** go to property chunks that merely
name the queried class labels. T11 and T28 crowd out in **all seven** formats; eight further items
(T13, T14, T16, T18, T22, T23, T25, T26) crowd out in some. The rate spans 0.174–0.348 across
formats, on 23 items — well inside noise for a per-format claim.

**Mechanism 2 — lexical mismatch from incidental `skos:example` content.** A retrieved non-gold chunk
is counted as example-attributable when the query shares a content word with that entity's
`skos:example` text that appears **nowhere else** in the entity's annotations, label, or local name.
Example text is identical across all seven formats by whole-graph equality, so any format difference
here is about ranking, not content.

| format | non-gold slots | example-attributable | rate | slot-filling rate | verification rate |
|---|---:|---:|---:|---:|---:|
| yaml-ld | 215 | 54 | 0.251 | 0.410 | 0.043 |
| jsonld | 210 | 48 | 0.229 | 0.361 | 0.046 |
| omn | 208 | 47 | 0.226 | 0.361 | 0.035 |
| ofn | 209 | 47 | 0.225 | 0.353 | 0.046 |
| turtle | 210 | 47 | 0.224 | 0.363 | 0.023 |
| elot-org-ancestors | 208 | 44 | 0.212 | 0.336 | 0.035 |
| elot-org | 211 | 43 | 0.204 | 0.325 | 0.044 |

**330 of 1,471 non-gold retrieved slots (22.4%)** are attributable to example-only vocabulary,
affecting **28 of 60 items**. The concentration is entirely in slot-filling (32.5–41.0%) versus
verification (2.3–4.6%), which is exactly what the mechanism predicts: scenario prose collides with
worked examples, class-name queries do not. Repeat offenders are `lis:profileQuantityDatum` (32
events), `lis:PhysicalQuantity` (23), `lis:IntervalRegion` (21), `lis:qualityQuantifiedAs` (19).
Clear instances: every format retrieves `lis:hasTemporalExtent` on T13 because its example contains
"interval"; six of seven retrieve `lis:Object` on T15 because its example contains "person".

**Both mechanisms are properties of entity-based chunking and dense retrieval, not of serialisation.**
That is the transferable claim, and it is stronger than a per-format ranking would have been.

### 2.6 Disjointness materialisation — a real asymmetry with no measurable effect

The pre-run checklist (§B3) flagged that ELOT collapses all disjointness into a single
`elot-axiom:Disjointness-clauses` chunk where every other format carries three, giving the ELOT arms
156 retrieval-eligible chunks against 158, and called this "directly relevant to the bare-disjointness
items". The asymmetry is visible in the retrieved lists: on T07 and T08, five of seven formats
surface a standalone disjointness-axiom chunk in the top-5 (`ttl-axiom-AllDisjointClasses-…`,
`DisjointClasses:…`, `jsonld-axiom-…`, `yamlld-axiom-…`, `ofn-axiom-…`) and **neither ELOT arm ever
does**.

**It changes nothing, and the reason is worth recording.** Every format — ELOT included — also
carries the disjointness *inline on the participating class chunks*, so both the oracle context (the
two class chunks) and the retrieved context recover the axiom regardless. All seven formats score
recall@5 = 1.000 on T06–T08 and accuracy 0.982–1.000. The `uniform_true` recoverability profiles for
those items are correct.

**This is an expected null, not a failure to find an effect.** A serialiser's decision about *where*
to materialise an axiom only matters when it is the sole carrier of that axiom — which is exactly the
condition that distinguishes this null from §4.1, where the ancestors arm removes the explicit
subsumption statement and nothing else replaces it.

---

## 3. RQ2 — Post-retrieval

### 3.1 Verification (30 items, 5,040 rows)

*Resolution: a verification item is a single binary label, so the task-level resolution is one full
label. No cell-level difference is claimable.*

Overall accuracy **0.556**, coverage **0.898**, against a majority-class baseline of 0.333 on a
balanced 10/10/10 gold.

| format | accuracy | coverage | accuracy-on-answered (all classes) |
|---|---:|---:|---:|
| omn | 0.574 | 0.932 | 0.602 |
| turtle | 0.567 | 0.914 | 0.594 |
| elot-org-ancestors | 0.558 | 0.879 | 0.589 |
| ofn | 0.557 | 0.908 | 0.590 |
| jsonld | 0.553 | 0.896 | 0.578 |
| elot-org | 0.542 | 0.896 | 0.572 |
| yaml-ld | 0.540 | 0.863 | 0.565 |

Spread 0.033 on accuracy, 0.069 on coverage. **0 of 21 paired contrasts nominally significant, 0
Holm-significant, 0 clearing the one-label threshold.** An exploratory sweep (168 contrasts:
21 pairs × {accuracy, coverage} × {all, oracle, retrieved, subsumption}) returns 21 nominal hits
(12.5%), maximum effect 0.188 — still well under one label. Eight of the 21 fall in the
`subsumption` subset, which is §4.1 showing through.

**Selective prediction, corrected.** The stored `accuracy_on_answered` divides `selective_correct`
by `answered`, and `selective_correct` requires `answered` — a determinate label. On an
`undetermined`-gold item, being right means abstaining, so `selective_correct` is **structurally
zero**. Pooling all three classes therefore reports 0.585 for a quantity that a third of the items
cannot contribute to. Recomputed on the 20 determinate items, where selective prediction is defined:

| arm | coverage | accuracy-on-answered | accuracy (all rows) |
|---|---:|---:|---:|
| claude-sonnet-4-5 | 0.900 | **1.000** | 0.900 |
| gpt-4o-2024-11-20 | 0.925 | 0.923 | 0.854 |
| gpt-4o-mini | 0.967 | 0.819 | 0.792 |
| llama3.1:8b | 0.782 | 0.775 | 0.606 |
| **all** | **0.894** | **0.882** | **0.788** |

Sonnet is **never wrong when it answers a determinate item** — 0 errors in 756 answered rows — and
buys that with the lowest coverage of the three API arms. That is textbook selective prediction and
is the cleanest single result in the verification half.

Abstention behaviour on the 10 genuinely undetermined items, where `undetermined` is correct:

| arm | abstention rate (correct) | called `contradicted` | called `supported` |
|---|---:|---:|---:|
| claude-sonnet-4-5 | **0.264** | 0.736 | 0.000 |
| llama3.1:8b | 0.062 | 0.936 | 0.000 |
| gpt-4o-2024-11-20 | 0.029 | 0.971 | 0.000 |
| gpt-4o-mini | 0.012 | 0.988 | 0.000 |

**3-way confusion, pooled (rows):**

| gold ↓ / pred → | supported | contradicted | undetermined | unparsed |
|---|---:|---:|---:|---:|
| supported | 1252 | 327 | 100 | 1 |
| contradicted | 28 | 1395 | 257 | 0 |
| undetermined | **0** | **1525** | 154 | 1 |

The dominant error in the entire study is one cell: **90.8% of undetermined-gold rows are called
`contradicted`**. Not one is called `supported`. Models treat "the ontology does not assert this" as
"the ontology denies this" — an open-world/closed-world confusion, and the single most reportable
behavioural finding here.

**Per-class precision / recall / F1** (bootstrap over items, B = 10,000, n = 10 gold items per class):

| class | precision [95% CI] | recall [95% CI] | F1 [95% CI] |
|---|---|---|---|
| supported | 0.978 [0.922, 1.000] | 0.745 [0.640, 0.840] | 0.846 [0.769, 0.905] |
| contradicted | 0.430 **[0.229, 0.634]** | 0.830 [0.715, 0.931] | 0.566 **[0.357, 0.725]** |
| undetermined | 0.301 **[0.083, 0.577]** | 0.092 [0.032, 0.164] | 0.141 [0.048, 0.236] |

**Decision, per §0: the per-class table is not reportable as numbers.** Precision intervals for
`contradicted` and `undetermined` are 0.40 and 0.49 wide — wider than the point estimates they
surround. **Fall back to the 3-way confusion matrix plus overall accuracy**, which is what the
paragraphs above do. The one exception worth stating in prose is that `supported` precision is high
and `undetermined` recall is near zero; both are visible directly in the matrix.

**By mechanism** — the strata differ enormously, and this is where the verification signal is:

| mechanism | items | rows | accuracy | coverage |
|---|---:|---:|---:|---:|
| bare_disjointness | 3 | 504 | **0.994** | 0.994 |
| functional_property | 2 | 336 | **0.952** | 0.952 |
| subsumption (supported) | 10 | 1680 | 0.745 | 0.940 |
| composed_domain_range_disjointness | 5 | 840 | 0.683 | 0.717 |
| unasserted_class_relation (undetermined) | 10 | 1680 | **0.092** | 0.908 |

Both uniform-by-construction contradicted strata sit at ceiling, as CHANGELOG 2026-08-19 predicted;
they contribute label balance and carry no format signal. The `unasserted_class_relation` figure is
the undetermined collapse restated.

**Ceiling / floor.** 5 items at ceiling (T06, T07, T08, T16, T64) and 6 verification items at floor
(T19, T20, T21, T22, T25, T27) — the floor items are all undetermined, so the floor *is* the
collapse, not an item defect. Seven slot-filling items are flagged at floor, but the flag scores
slot-filling on **exact match** (all 5 or 6 fields) rather than the headline partial credit; each
still earns 0.435–0.657 partial credit. They are floors on the conjunction, not on the headline
metric, and should not be described as failed items.

### 3.2 Slot-filling (30 items, 5,040 rows)

*Resolution: 20 items grade five fields (one field = 0.200), 10 grade six (one field = 0.167); the
three answer fields alone give 0.333.*

Headline strict combined partial credit **0.699**; exact match 0.323. Parse rate 1.000.

**Answer fields versus citation fields — they move independently, as the pilot established:**

| | partial credit | answer fields (3) | citation fields |
|---|---:|---:|---:|
| **overall** | 0.699 | **0.807** | **0.568** |
| oracle | 0.874 | 0.953 | 0.789 |
| retrieved | 0.524 | 0.661 | 0.346 |
| claude-sonnet-4-5 | 0.764 | 0.840 | 0.673 |
| gpt-4o | 0.769 | 0.844 | 0.681 |
| gpt-4o-mini | 0.693 | 0.736 | 0.652 |
| llama3.1:8b | 0.570 | **0.807** | **0.266** |

Llama is the decisive case: its **answer** fields (0.807) are level with gpt-4o (0.844) and sonnet
(0.840), while its **citation** fields (0.266) are less than half theirs. Reported as a single
combined number, Llama looks like a much weaker modeller than it is; the decomposition shows it
understands the pattern and cannot name the chunk it came from. **This is the strongest argument in
the study for never reporting the combined metric alone.**

**Per format:**

| format | partial credit | answer fields | citation fields | class | property | intermediate |
|---|---:|---:|---:|---:|---:|---:|
| jsonld | **0.708** | 0.805 | **0.590** | 0.796 | 0.764 | 0.856 |
| omn | 0.706 | **0.823** | 0.563 | 0.814 | 0.778 | **0.878** |
| ofn | 0.705 | 0.813 | 0.575 | 0.803 | 0.782 | 0.853 |
| elot-org | 0.703 | 0.815 | 0.568 | **0.819** | 0.785 | 0.840 |
| yaml-ld | 0.702 | 0.807 | 0.574 | 0.779 | 0.782 | 0.861 |
| turtle | 0.685 | 0.785 | 0.564 | 0.767 | 0.764 | 0.824 |
| elot-org-ancestors | 0.684 | 0.800 | 0.541 | 0.783 | 0.771 | 0.846 |

Spread 0.024 on the headline. **0 of 21 paired contrasts nominally significant, 0 Holm-significant,
0 clearing 0.200.**

An exploratory sweep (378 contrasts: 21 pairs × 6 metrics × {all, oracle, retrieved}) yields **33**
nominal hits — 8.7%, against 5% expected from correlated tests — with effect sizes spanning
**0.017 to 0.078**. Every one is **below one graded field** and none is claimable on its own. But
their distribution is not random: **19 of the 33 involve `elot-org-ancestors`, and all 19 put it on
the losing side**; 17 of those 19 are under `oracle`, where the corpus is guaranteed to contain the
gold chunks and any deficit must be an encoding effect rather than a retrieval one. The affected
metrics are partial credit (6), citation fields (5) and the property slot (4). That pattern agrees
with §4.1's direction, and it is the right way to use these contrasts: as convergent support for an
effect established elsewhere, never as a finding in themselves.

**Citation decomposition — the failure is one slot:**

| | support_class | support_property | support_intermediate |
|---|---:|---:|---:|
| overall | 0.562 | 0.637 | **0.183** |
| oracle | 0.864 | 0.867 | **0.123** |
| retrieved | 0.260 | 0.408 | 0.243 |

`support_intermediate` is graded on only the 10 items that have an intermediate node, and it is the
single worst-performing field in the study — **and it is worse under oracle than under retrieved**,
which is the reverse of every other field. That inversion is a strong hint the field is measuring
citation surface form rather than comprehension, consistent with the pilot's citation-surface finding
(CHANGELOG 2026-08-13). Flagged for the methodology log; not regraded here.

**`intermediate_node` against its correct baseline.** Gold is 20 false / 10 true, so answering
`false` always scores **0.667**. Observed 0.851 overall — above baseline. But per arm:

| arm | intermediate acc | predicts `false` | acc on true items | acc on false items |
|---|---:|---:|---:|---:|
| claude-sonnet-4-5 | 0.940 | 0.641 | 0.948 | 0.936 |
| gpt-4o | 0.939 | 0.610 | 0.993 | 0.912 |
| llama3.1:8b | 0.866 | 0.563 | 0.955 | 0.821 |
| **gpt-4o-mini** | **0.660** | 0.326 | 1.000 | **0.489** |

**gpt-4o-mini sits below the always-false baseline.** It predicts `true` on two thirds of items,
gets every genuinely-true item right, and fails half the false ones — it is not discriminating, it is
biased toward positing an intermediate node. Reported against the 0.667 baseline as required, not
against chance.

### 3.3 Oracle versus retrieved — the retrieval bottleneck

**Slot-filling** (paired over 30 items, bootstrap B = 10,000):

| format | oracle | retrieved | oracle − retrieved | 95% CI |
|---|---:|---:|---:|---|
| turtle | 0.872 | 0.498 | **+0.374** | [0.295, 0.453] |
| omn | 0.889 | 0.522 | **+0.367** | [0.282, 0.455] |
| jsonld | 0.887 | 0.529 | **+0.358** | [0.272, 0.445] |
| yaml-ld | 0.879 | 0.525 | **+0.354** | [0.269, 0.441] |
| ofn | 0.879 | 0.531 | **+0.349** | [0.265, 0.438] |
| elot-org-ancestors | 0.846 | 0.522 | **+0.324** | [0.255, 0.391] |
| elot-org | 0.863 | 0.543 | **+0.320** | [0.239, 0.400] |

Every interval excludes zero and every effect is larger than one graded field — **1.5× to 2× the
resolution threshold, and roughly 15× the largest format spread.** Retrieval, not serialisation, is
the binding constraint on slot-filling quality. The gap is remarkably uniform across formats (0.320
to 0.374), which says the bottleneck is the retrieval stage itself and not any format's interaction
with it.

**Verification** is a different story: +0.065 to +0.136, and only omn (+0.136, CI [0.044, 0.242]) and
turtle (+0.106, CI [0.017, 0.200]) exclude zero. All are below one label. Verification is bounded by
the undetermined collapse, not by retrieval — perfect context does not fix a labelling prior.

**A confound to state.** The run used plain `oracle`, not `oracle_padded`. Oracle contexts therefore
carry 2–8 chunks (verification median 2, slot-filling median 3) while `retrieved` is always exactly
5. For most verification items **the oracle is the smaller context**. The oracle-versus-retrieved
contrast therefore varies context precision *and* context size together. `oracle_padded` exists to
equalise this and was not run; `oracle_over_k` is `False` on all 10,080 rows only because it is set
exclusively under that unrun condition, so it is a null field, not evidence.

---

## 4. Designed contrasts

### 4.1 Subclass omission — the effect is real, and it is in the *wrong task type*

**Where the benchmark looked (slot-filling): null at claimable magnitude.**
Treatment T40–T43, T55–T58 (chains routing through `ScalarQuantityDatum ⊑ QualityDatum`, which
`elot-org-ancestors` does not serialise) against controls T35, T44 (same two-hop demand, no subclass
link). Gap = `elot-org-ancestors` minus the mean of the other six formats, per item:

| | n items | anc − others (partial credit) | 95% CI |
|---|---:|---:|---|
| treatment | 8 | −0.042 | [−0.099, +0.011] |
| control | 2 | −0.026 | — |
| **difference-in-differences** | | **−0.016** | |

−0.016 is **one twelfth of a graded field**. Not claimable. Worse for the hypothesis, the treatment
effect is not even sign-consistent: the quantity-chain items go the predicted way (T40 −0.197,
T56 −0.110, T55 −0.069, T41 −0.050) while the quality-chain items go the *other* way (T42 +0.067,
T43 +0.048, T57 −0.005, T58 −0.019).

**On the 2:8 control ratio, specifically.** The spec asks for an explicit statement about control
noise. The controls are clean: T35 shows within-cell trial spread in **1 of 56** cells and T44 in
**0 of 56**, against 2–6 cells for each treatment item. So the attribution is *not* limited by
control noise here — it is limited by the treatment effect being absent. Had the treatment effect
been large, 2 controls would have supported it adequately. The 2:8 ratio remains a design limitation
for any future item that does show an effect.

**Where the effect actually is: one-hop asserted subsumption in verification.**
The subsumption stratum (T09–T18) splits cleanly by whether the licensing axiom is a single asserted
`rdfs:subClassOf` or a multi-link entailed chain:

| | items | `elot-org-ancestors` | other six formats | gap | 95% CI |
|---|---|---:|---:|---:|---|
| **asserted, 1 hop** | T09, T10 | **0.313** | **0.747** | **−0.434** | [−0.451, −0.417] |
| entailed, 2–4 hops | T11–T18 | 0.807 | 0.753 | +0.055 | [−0.084, +0.171] |

Per item, all seven formats:

| item | turtle | elot-org | **elot-anc** | omn | jsonld | yaml-ld | ofn | gap | rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T09 | 0.750 | 0.625 | **0.250** | 0.875 | 0.625 | 0.500 | 0.833 | −0.451 | **7/7** |
| T10 | 0.875 | 0.625 | **0.375** | 0.875 | 0.875 | 0.625 | 0.875 | −0.417 | **7/7** |

**The n = 2 caveat is stated plainly: a bootstrap over two items is not an inferential statement, and
the interval above should not be read as one.** The evidence is convergent rather than inferential,
and it is strong on four independent counts:

1. Both items move the same way, by **more than twice** the one-label threshold.
2. `elot-org-ancestors` ranks **last of seven on both**.
3. Over the 48 `(item, model, condition, trial)` cells, it is worse on **30**, tied on 18, and
   better on **0**.
4. The effect **disappears** on the eight multi-hop items of the same stratum, which is the
   dissociation the recoverability profile predicts and which noise would not produce.

**The label evidence identifies the mechanism.** On T09/T10, `elot-org-ancestors` predicts
`contradicted` on 62.5% of rows while every other format predicts `supported` on 56–88%. The arm is
not failing to find the axiom and abstaining; it is concluding the subsumption is *denied*. Removing
the explicit `SubClassOf` statement and leaving only heading indentation does not merely hide
information — it flips the answer.

**And it is model-conditional:**

| arm | anc (1-hop) | others (1-hop) | gap |
|---|---:|---:|---:|
| claude-sonnet-4-5 | 1.000 | 1.000 | **0.000** |
| gpt-4o-2024-11-20 | 0.250 | 1.000 | −0.750 |
| gpt-4o-mini | 0.000 | 0.708 | −0.708 |
| llama3.1:8b | 0.000 | 0.278 | −0.278 |

Sonnet reads the ancestor-heading encoding correctly and is unaffected. This is the format × model
interaction the secondary hypothesis predicted, in its sharpest available form.

**Scope limit, carried forward from CHANGELOG 2026-08-04 (c):** `elot-org-ancestors` differs from
flat `elot-org` in **two** ways at once — ancestor path added *and* explicit axiom removed. The
flat/ancestors pair isolates the encoding change but confounds those two variables. The flat arm
scores 0.625 on the 1-hop items against ancestors' 0.313, so the direction survives within the ELOT
family, but the contrast cannot separate the two changes.

### 4.2 Bare versus composed on identical entities

Same disjointness axiom read bare, then reached through a property's range. **The spec describes this
as "one hop vs three"; the committed routes are one link versus two** — `[residesIn rdfs:range Site]`
+ `[Site ⊥ SpatialLocation]`, and `[representedIn rdfs:range InformationObject]` +
`[InformationObject ⊥ PhysicalObject]`. Both links are directly asserted, so `entailed_chain` here
means a two-link asserted route, as CHANGELOG 2026-08-19 records.

| pair | bare item | composed item | shared axiom | bare acc | composed acc | Δ |
|---|---|---|---|---:|---:|---:|
| 1 | T06 | **T62** (B05-R01) | `Site ⊥ SpatialLocation` | **1.000** | 0.738 | −0.262 |
| 2 | T08 | T61 (B05-R09) | `InformationObject ⊥ PhysicalObject` | **1.000** | 0.685 | −0.315 |

Both bare items are answered correctly in **168 of 168 rows** — every format, every model, every
condition, every trial. Composing the same axiom through a domain/range link costs **0.26–0.32** of
accuracy and, on T61, drives coverage from 1.000 to 0.685. **Inference depth, not serialisation, is
what the models find hard.** These are matched pairs by construction (CHANGELOG 2026-08-19) and are
counted as two observations, not four.

### 4.3 Prose-versus-axiom disagreement — replicates, on the weakest arm only

T62 is IDO's only genuine prose/axiom disagreement: `lis:residesIn`'s
`naturalLanguageDefinition` reads *"If x 'resides in' y, then x is a 'physical object', y is a
'location', and x is located entirely within y"* — naming the weaker filler `location`, where the
axiom's range is `lis:Site`, which is asserted `owl:disjointWith lis:SpatialLocation`. The prose
positively licenses the false statement.

| arm | accuracy | called `supported` | called `undetermined` | oracle | retrieved |
|---|---:|---:|---:|---:|---:|
| gpt-4o-mini | 0.952 | 0.000 | 0.048 | 1.000 | 0.905 |
| gpt-4o-2024-11-20 | 0.857 | 0.000 | 0.143 | 1.000 | 0.714 |
| claude-sonnet-4-5 | 0.857 | 0.000 | 0.143 | 1.000 | 0.714 |
| **llama3.1:8b** | **0.286** | **0.500** | 0.214 | 0.571 | **0.000** |

The three API arms never once answer `supported`. Llama does so on half its rows and is **0.000
under `retrieved`**. Its stated reasoning, reproduced verbatim and identically across all three
trials of `elot-org`/`oracle`:

> "The ontology content states that lis:residesIn is a subproperty of lis:containedBy, and the domain
> of lis:residesIn is lis:PhysicalObject, and the range of lis:residesIn is lis:Site, **which is a
> subclass of lis:SpatialLocation**."

and on `ofn`/`retrieved`:

> "The statement is supported by the ObjectPropertyRange axiom that states lis:residesIn has a range
> of lis:Site, **which is a subclass of lis:SpatialLocation**."

The asserted relation between those two classes is `owl:disjointWith`. The model reads the axiom
correctly, then fabricates a subsumption between the two classes the ontology declares disjoint —
the relation the prose's looser "location" wording invites. **The pilot's finding replicates, but as
a model-capability effect at the bottom of the range, not a general one.** The three stronger arms
resolve the disagreement in the axiom's favour without exception.

The prose-screen strata within the contradicted class point the same way, though weakly (n = 1 for
`away`): accuracy `toward` 0.881 > `neutral` 0.813 > `away` 0.786, with Llama at 0.548–0.635 across
all three strata against 0.786–1.000 for the other arms.

### 4.4 Depth ladder — the ladder does not exist as specified

The spec asks for 2-hop, 3-hop and 4-hop items on the
`Function → Capability → Disposition → Potential → Dependent` chain. **The committed benchmark has
only one item on that chain (T18, 4 hops).** Depth in the subsumption stratum varies *across*
chains, so it is confounded with which chain the item rides:

| depth | items | accuracy | coverage |
|---:|---|---:|---:|
| 1 | T09, T10 | 0.685 | 0.991 |
| 2 | T11, T12, T14, T15, T16 | 0.794 | 0.963 |
| 3 | T13, T17 | 0.860 | 0.944 |
| 4 | T18 | **0.393** | 0.714 |

The relation is **non-monotonic**: depth 1 scores lower than depths 2 and 3. Depth 1 is depressed
entirely by the `elot-org-ancestors` arm (§4.1); excluding it, the depth-1 items score 0.747. Depth 4
is a single item and cannot carry a trend. **Report as a limitation, not as a depth result**: this
benchmark cannot isolate composition depth within a chain. §4.2's bare-versus-composed pairs are the
study's valid depth contrast, because they hold the entities fixed.

### 4.5 Matched local route — T52 / T53

T52 partial credit 0.857, T53 0.806. Correlation across the 56 shared cells: **r = 0.862**. Adjacent
links on one asserted route, correlated as expected — **one observation, not two.**

### 4.6 Duplicate-shape groups

| group | items | per-item means | mean pairwise r | group mean | effective n |
|---|---|---|---:|---:|---:|
| quantity chain | T40, T41, T55, T56 | 0.592 / 0.550 / 0.532 / 0.657 | **0.807** | 0.583 | **1** |
| quality chain | T42, T43, T57, T58 | 0.505 / 0.487 / 0.476 / 0.495 | **0.944** | 0.491 | **1** |

The quality group's r = 0.944 is near-total redundancy. Both groups are counted as **one observation
each** everywhere in this document, which is why §4.1's treatment set is 8 items but carries the
weight of roughly 2.

### 4.7 Functional-property pair — T64 / T65

T64 accuracy **1.000** (168/168, every format and arm); T65 **0.905**, with the entire deficit in
Llama (0.619; the other three arms are at 1.000). Correlation across cells is undefined because T64
has zero variance — itself a symptom of the shared `usageNote` making both items easy. One fragment,
two items: **treat as a matched pair with a correlated failure mode**, as the log records. The
stratum is uniform by construction (`rdf:type owl:FunctionalProperty` materialises in all seven
serialisations) and correctly shows no format effect.

---

## 5. Covariate crossings

Reported as covariates. **No per-cell effect is claimed anywhere in this section.**

### 5.1 `recoverability_profile` — confirms the mechanism-level result, and its own limit

**Every split profile in the benchmark is split at exactly one format and nowhere else:
`elot-org-ancestors`.** So "split versus uniform" *is* "does the ancestors arm carry the axiom" — it
is not a general recoverability covariate, and it cannot be.

| verification stratum | items | accuracy | anc | others | gap |
|---|---:|---:|---:|---:|---:|
| uniform_true (contradicted) | 10 | 0.830 | 0.846 | 0.828 | +0.018 |
| split (supported subsumption) | 10 | 0.745 | 0.708 | 0.751 | **−0.043** |
| none / hypothetical (undetermined) | 10 | 0.092 | 0.121 | 0.087 | +0.034 |

The pooled split-stratum gap is only −0.043 — because it averages the −0.434 one-hop effect over
eight multi-hop items where the gap is positive. **Pooling by profile hides the effect that the
profile predicts.** The finer hop-class split in §4.1 is the correct resolution, and this is a
concrete argument for stratifying by *axiom form* rather than by profile flag.

Slot-filling `intermediate_node` recoverability: split items 0.537, uniform 0.636, none 0.770;
anc-versus-others gap −0.042 (split), −0.026 (uniform), −0.007 (none). Directionally ordered, all far
below 0.200.

### 5.2 `annotation_prose_screen` — the covariate is not what the spec expected

The spec anticipated `toward` / `away` / `neutral` / `states_axiom`. The committed distribution is:

| screen | items | gold label | accuracy |
|---|---:|---|---:|
| passed | 10 | **all undetermined** | 0.092 |
| neutral | 6 | all contradicted | 0.813 |
| toward | 3 | all contradicted | 0.881 |
| away | **1** | contradicted | 0.786 |

Three findings, all limiting:

- **Only 20 of 30 verification items carry the field at all.** The 10 supported items have none.
- **It is nested inside `gold_label`, not crossed with it.** `passed` ⟺ undetermined; the other
  three ⟺ contradicted. Any prose-screen contrast is therefore also a label contrast, and the
  headline 0.092-versus-0.8 gap is the undetermined collapse wearing a different name.
- **`states_axiom` never occurs, and `away` is n = 1.**

Within the contradicted class — the only place the comparison is legitimate — accuracy runs
`toward` 0.881 > `neutral` 0.813 > `away` 0.786. That ordering is *backwards* from the naive
prediction (prose pointing toward the false statement should hurt), and n = 1 on `away` means it
should not be interpreted at all. The spec's expectation that this would be "the covariate most
likely to carry signal" is **not borne out**; the prose effect that does exist is item-specific
(T62, §4.3), not stratum-level.

The slot-filling `class_prose_covariate` is `stated: true` on **all 30** items — no contrast
available.

### 5.3 `reasoning_type` — collinear, as the spec anticipated

| reasoning_type | task_type | items | dominant mechanism |
|---|---|---:|---|
| structural | verification | 21 | disjointness + subsumption |
| definitional | verification | 9 | unasserted_class_relation |
| direct_assertion | slot_filling | 20 | direct_relation, part_whole |
| modelling_pattern | slot_filling | 10 | quantity/quality pattern |

Four populated cells, each mapping nearly one-to-one onto `(task_type, stratum)`. `definitional` is
9 of the 10 undetermined items; `structural` is the other 21 verification items. **The
"does format matter more for structural than for direct-assertion reasoning" question cannot be
answered by this design** — the crossing the 60 items were sized to enable does not exist in the
committed distribution. Stated as a limitation, per §5 of the spec; no crossing is reported.

### 5.4 `query_source`, `sub_kind`, `licensing_axiom_status`

- **`query_source`** — RQ1 breakout in §2.3. On RQ2, verification accuracy is **0.605** (label, 21
  items) versus **0.440** (paraphrase, 9). Slot-filling partial credit is label 0.826 (8),
  definition 0.777 (5), example 0.702 (7), paraphrase **0.557** (10).
  **Both splits are confounded and neither is a wording effect.** The 9 paraphrase verification items
  are disproportionately the composed contradicted ones — T60, T62 and T64 were paraphrase-worded
  precisely to break a different confound (CHANGELOG 2026-08-19). Worse, the 10 paraphrase
  slot-filling items are **exactly** the subclass-omission block: T35, T40–T43, T44, T55–T58. That is
  the 8 treatments plus the 2 controls, and by §4.6 it collapses to roughly two effective
  observations. `query_source = paraphrase` in slot-filling therefore *is* that block's difficulty
  and carries no independent information.
- **`sub_kind`** — `co_hyponym` 9 items, `cross_branch` 1, all within the undetermined class.
  Abstention 0.098 versus 0.036. Directionally sensible (a cross-branch pair looks more clearly
  unrelated, so the model commits more readily) but n = 1 on `cross_branch`.
- **`licensing_axiom_status`** — `asserted` 37 items, `entailed_chain` 13, `hypothetical` 10.
  Slot-filling is **entirely `asserted`** (all 30), so no contrast exists there. On verification:
  `asserted` 0.894 (7 items), `entailed_chain` 0.731 (13), `hypothetical` 0.092 (10).
  **The 0.16 asserted-versus-entailed gap is not an axiom-form effect.** The 7 asserted items are
  T06/T07/T08 (bare disjointness, at ceiling), T64/T65 (functional property, at ceiling) and T09/T10
  — so `asserted` is mostly "the two uniform-by-construction ceiling strata". `hypothetical` is
  exactly the 10 undetermined items, so its 0.092 is the §3.1 collapse again. Note the log's caveat
  that `entailed_chain` on the five composed items describes a **two-link asserted route**, not a
  reasoner-derived entailment.

---

## 6. Model interaction

### 6.1 Degeneracy check — STOP CONDITION 3 FIRES

**Read this before interpreting any verification result.**

The spec's rule — flag any arm whose modal label exceeds ~80% — catches almost nothing here: across
56 `(model × condition × format)` cells the maximum modal share is **0.833**, and only 2 cells exceed
0.80. Pooled per arm, modal shares are sonnet 0.529, gpt-4o 0.674, Llama 0.615, gpt-4o-mini 0.760 —
all under threshold.

**The rule misses a real collapse.** A label-support check — does the arm ever emit each of the three
labels — flags **16 of 56 cells**:

| arm | condition | cells with a never-predicted label | never predicted |
|---|---|---:|---|
| gpt-4o-2024-11-20 | **oracle** | **7 of 7** | `undetermined` |
| gpt-4o-mini | **oracle** | **7 of 7** | `undetermined` |
| gpt-4o-mini | retrieved | 2 of 7 (ofn, omn) | `undetermined` |
| claude-sonnet-4-5 | either | 0 of 14 | — |
| llama3.1:8b | either | 0 of 14 | — |

**Under `oracle`, both GPT arms never once predict `undetermined` — 630 rows each, in all seven
formats.** Their oracle accuracy is therefore capped at 2/3 by construction, and their accuracy on
the undetermined class is exactly 0.000. This is a two-label collapse in a three-label task, and the
modal-share rule cannot see it because the remaining two labels split roughly 70/30.

**Consequences, applied throughout this document:**

- The oracle-versus-retrieved verification contrast (§3.3) is partly an artefact for these two arms:
  giving them the correct chunks removes their only route to abstention. Their `undetermined` rate
  goes 0.000 → 0.119 (gpt-4o) and 0.000 → 0.052 (mini) when context degrades.
- Any pooled verification accuracy that includes the undetermined class mixes a measurement with a
  prior. That is why §3.1 reports selective prediction on the 20 determinate items separately.
- **No format comparison should be drawn from GPT-arm oracle verification cells.** The format spread
  there is a spread between two labels, not three.

**Correction (2026-08-27, see `oracle-undetermined-degeneracy.md` §4 and the CHANGELOG entry of the
same date):** the line originally here read "Sonnet and Llama use all three labels in every cell and
are unaffected." That is wrong for Llama. Label support is the wrong instrument - it only checks
whether a label is ever emitted, not whether it tracks the truth. The right instrument is
discrimination, P(`undetermined` | gold = undetermined) − P(`undetermined` | gold determinate), on
gold-present rows: sonnet +0.251, gpt-4o 0.000, gpt-4o-mini −0.003, llama3.1:8b **−0.128**. A negative
score means the label is anti-correlated with being right: Llama emits `undetermined` roughly ten
times more often on items where it is wrong than on items where it is right, so its label support
passes the §6.1 check while being actively misleading.

Sonnet is the only arm of the four whose abstention responds to non-entailment at all, and even that
is a comparative claim, not a pass mark: on the undetermined-gold stratum Sonnet answers
`contradicted` on three quarters of the rows (accuracy 0.251), so it does not handle the stratum
acceptably either. No arm in this study does. The 90.8% cross-model `contradicted` rate on
undetermined-gold rows reported in §3.1 is a finding about all four arms, and this correction does not
soften it.

### 6.2 Format spread by model

The secondary hypothesis — narrative context compensates for weak parametric knowledge, so the
format × model interaction should be larger on weaker arms:

| arm | verification: mean / spread | slot-filling: mean / spread |
|---|---|---|
| claude-sonnet-4-5 | 0.688 / **0.089** | 0.764 / **0.028** |
| gpt-4o-2024-11-20 | 0.579 / **0.083** | 0.769 / **0.035** |
| gpt-4o-mini | 0.532 / **0.172** | 0.693 / **0.033** |
| llama3.1:8b | 0.425 / **0.094** | 0.570 / **0.091** |

The two weakest arms carry the two largest spreads — mini on verification (0.172, more than double
the top two arms) and Llama on slot-filling (0.091, roughly three times the others). **Directionally
consistent with the hypothesis; not resolvable.** Of 168 within-model paired format contrasts,
16 (9.5%) are nominally significant and **0 clear the resolution threshold** (one label for
verification, 0.200 for slot-filling). Mini's verification spread is itself partly the §6.1 artefact.

The one place the interaction *is* resolvable is §4.1: on 1-hop asserted subsumption, the
ancestors-arm penalty is 0.000 for sonnet and −0.28 to −0.75 for the other three. **A format's
encoding choice costs nothing to a model strong enough to decode it, and a great deal to models that
are not.** That is the study's cleanest statement about format × model.

### 6.3 Context length does not explain anything

If narrative bulk were the mechanism, longer contexts should score better. They do not:
Pearson r between mean context length and score across the seven formats is **0.153** (verification)
and **0.153** (slot-filling). jsonld carries the longest contexts (9,725 chars slot-filling) and
elot-org the shortest (6,504) for a 0.005 difference in partial credit.

### 6.4 Contamination floor

All four arms were established as having near-zero parametric IDO knowledge — WI-6 for the GPT and
Llama arms (CHANGELOG 2026-08-04 (b)) and checklist §B8 for Sonnet, whose above-baseline `no_context`
figure was fully explained by an abstention prior meeting an undetermined-heavy item set. **Every
effect reported here is therefore an in-context effect**, not recall of a memorised ontology. The
§B8 caveat stands: that floor was measured at n = 23, N = 1, on an unbalanced 10/10/3 set, and is
worth re-running on the balanced 60.

---

## 7. Limitations

*Written before any discussion is drafted, as required.*

**Carried forward from the design record:**

1. **Duplicate-shape groups.** T40/T41/T55/T56 share one gold answer (mean pairwise r = 0.807);
   T42/T43/T57/T58 share another (r = 0.944). Eight slot-filling items carry the evidential weight of
   roughly two. Solving one solves its group.
2. **2:8 control ratio on the subclass-omission contrast.** Two controls (T35, T44) against eight
   treatments. The controls proved stable in this run (1/56 and 0/56 cells with trial spread), so
   attribution was not limited by control noise — but the ratio remains a structural weakness for any
   future item that does show an effect.
3. **The `information` mechanism stratum is empty.** `hasContentPart` was classified `part_whole` by
   the stratifier and the zero-information stratum was never filled. No conclusions about
   information-object modelling are available.
4. **All 30 slot-filling items are `gold < k`** (narrow gold = 2 throughout). Gold-set size cannot
   serve as a retrieval-difficulty covariate within slot-filling.
5. **`reasoning_type` is collinear with task type and stratum** (§5.3). Four populated cells, each
   nearly one-to-one. The structural-versus-direct-assertion question is unanswerable in this design.
6. **Uniform-by-construction mechanisms carry no format signal.** `bare_disjointness` (3 items) and
   `functional_property` (2 items) materialise identically in all seven serialisations. Their nulls
   are expected and must not be read as evidence of format irrelevance.
7. **Agent-assisted authoring.** 47 of 60 items are `agent_candidate_human_selected`. The
   human-authored five-task pilot is the control, but it ran under a superseded harness
   configuration, so the comparison is qualitative only.

**Established by this analysis:**

8. **Two of four arms are label-degenerate on verification under `oracle`** (§6.1). GPT-4o and
   GPT-4o-mini never emit `undetermined` there. Their oracle verification results measure a two-label
   task.
9. **`accuracy_on_answered` is undefined on undetermined-gold items** and structurally zero, because
   `selective_correct` requires a determinate label. Any pooled figure across all three classes is
   diluted by a third of the items. §3.1 reports it on the 20 determinate items instead. This is a
   grader-semantics issue, not a grader defect, and nothing was regraded.
10. **The oracle-versus-retrieved contrast confounds context precision with context size** (§3.3).
    Plain `oracle` supplies 2–8 chunks; `retrieved` always supplies exactly 5. For most verification
    items the oracle is the *smaller* context. `oracle_padded` equalises this and was not run.
11. **`annotation_prose_screen` is nested inside `gold_label`, not crossed with it** (§5.2); only 20
    of 30 verification items carry it; `states_axiom` never occurs and `away` is n = 1. It cannot
    function as the independent covariate the spec anticipated.
12. **`recoverability_profile` is not a general covariate** (§5.1). Every split profile splits at
    `elot-org-ancestors` and nowhere else, and pooling by it *hides* the effect it predicts.
13. **The depth ladder does not exist as specified** (§4.4). No chain carries items at more than one
    depth; depth is confounded with chain identity, and the observed depth relation is non-monotonic.
14. **The one resolvable format effect rests on two items** (§4.1). T09 and T10. The supporting
    evidence is convergent (both last of seven, 30/48 cells lost and 0 won, dissociation from the
    multi-hop items, and a label flip identifying the mechanism) rather than inferential, and it must
    be reported that way. A replication set of one-hop asserted subsumption items is the single
    highest-value addition to this benchmark.
15. **`elot-org-ancestors` versus `elot-org` confounds two changes at once** — ancestor path added,
    explicit axiom removed (CHANGELOG 2026-08-04 (c)). Every ancestors finding inherits this.
16. **Multiplicity.** Only three families were treated as headline and Holm-corrected. The broader
    exploratory sweeps return nominal hit rates barely above chance: RQ1 24/336 (7.1%), RQ2
    verification 21/168 (12.5%), RQ2 slot-filling 33/378 (8.7%), within-model 16/168 (9.5%). Every
    hit in all four sweeps is below its resolution threshold. They are used in this document only as
    convergent support for effects established elsewhere.
17. **`elot-org` is not verifiable in-repo.** Whole-graph set equality is checked for jsonld,
    yaml-ld, ofn and omn, but the ELOT arms are externally tangled and cannot be checked. Their
    parity rests on named-entity counts only.
18. **Cost is reconciled against projections, not against an invoice.** No provider usage export was
    available.
19. **`query_source = paraphrase` is confounded with the subclass-omission block in slot-filling**
    (§5.4). All 10 paraphrase slot-filling items are T35, T40–T43, T44, T55–T58 — the 8 treatments
    plus the 2 controls — which by limitation 1 collapse to roughly two effective observations. Any
    paraphrase-versus-label contrast on slot-filling, in RQ1 or RQ2, inherits this and cannot be read
    as a query-wording effect.
20. **`licensing_axiom_status = asserted` is confounded with the ceiling strata in verification**
    (§5.4). Five of its seven items are the uniform-by-construction `bare_disjointness` and
    `functional_property` items, both at ceiling. The asserted-versus-entailed gap is therefore
    mostly a stratum difference. Slot-filling is entirely `asserted`, so the covariate does not vary
    there at all.

---

## 8. Methodology-log entries to write (flagged, not written)

1. **`graded_stability_rate` measured on the full run: 0.963 overall** (sonnet 0.985, gpt-4o 0.975,
   llama 0.952, mini 0.941; verification 0.983, slot-filling 0.943), against the pilot probe's 0.813.
   This is the measured replacement for the retracted `seed_determinism` manifest label, and it
   supersedes the "roughly one cell in five" instability assumption that the analysis thresholds were
   set against. Thresholds retained unchanged, as the change is in the conservative direction.
2. **Label-support degeneracy check added to the diagnostics contract.** The `>80% modal label` rule
   misses a two-label collapse: gpt-4o and gpt-4o-mini never emit `undetermined` in any of their 7
   oracle cells (14 of 56 cells), at modal shares of only 0.67–0.83. Recommend the diagnostics report
   flag *never-predicted label classes* per `(model, condition, format)` cell alongside modal share.
3. **`accuracy_on_answered` is structurally zero on undetermined-gold items.** Selective-prediction
   metrics must be reported on the determinate subset, with abstention behaviour on the undetermined
   items reported separately. Affects how D1 option C is described in the methods chapter.
4. **The `oracle` condition is size-unequal to `retrieved`** (2–8 chunks versus a fixed 5), so the
   headline retrieval-bottleneck contrast varies size and precision together. Either run
   `oracle_padded` or state the confound wherever the contrast appears.
5. **Both pilot retrieval mechanisms replicate at 60 items and are format-invariant**:
   property-chunk crowding (23 class-pair items, 0.174–0.348 crowd-out rate, 1.0–1.7 of 5 slots) and
   `skos:example` lexical mismatch (22.4% of non-gold retrieved slots, 28 of 60 items,
   32.5–41.0% on slot-filling versus 2.3–4.6% on verification). Both are properties of entity-based
   chunking and dense retrieval, not of serialisation — which strengthens the cross-cutting claim
   already recorded in the thesis drafting notes (not part of this repository).
6. **The subsumption-omission effect is in verification on one-hop asserted axioms, not in
   slot-filling.** Record the dissociation (−0.434 at 1 hop, +0.055 at 2–4 hops), the label flip
   (ancestors predicts `contradicted` where every other format predicts `supported`), and the model
   conditionality (0.000 penalty for Sonnet). Record also that the slot-filling treatment/control
   design returned a null at −0.016 DiD with inconsistent signs, and that the controls were clean, so
   the null is about the effect, not the controls.
7. **`reasoning_type` collinearity and the empty `information` stratum** should be recorded as design
   outcomes of the 60-item build, since both close off analyses the item count was chosen to enable.

---

## Appendix — reproduction

All figures derive from the two committed result directories plus `tasks_60.yaml`, with no API or
Ollama calls and no change to any grader. Analysis scripts (integrity, cost, stability, RQ1, the two
mechanism replications, RQ2, designed contrasts, covariates, model interaction, multiplicity) are in
the session scratchpad; each writes a JSON table that the sections above quote directly. Bootstraps
resample **items**, never cells, and use fixed seeds (20260529–20260605) with B = 10,000–20,000.
`postretrieval-combined-15-18/postretrieval_raw.csv` is gitignored but md5-reproducible from the four
committed per-arm directories via `scripts/merge_postretrieval_trials.py`.
