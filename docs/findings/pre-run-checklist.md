# Pre-run checklist — B1–B8 status and go/no-go

**Date:** 2026-08-19 · **Scope:** Part B of the functional-property / pre-run spec.
**Benchmark state:** `tasks_60.yaml` at commit `34e87b5` — **53 of 60 items**.
**Spend this session:** **USD 0.652** against the USD 3.00 cap (112-call smoke + 46-call
contamination floor + two retrieval stages). Cap not approached.

> **Updated after pulling `34e87b5` ("feat: second slot-filling batch").** That commit
> completed the slot-filling half (T44–T58) **and** independently implemented the B2
> reorder. Its ordering was kept and mine discarded; every measurement below was re-run
> against the merged state. See §Integration.

---

## GO / NO-GO: **NO-GO**, on two narrow author decisions

Both are decisions, not defects. The harness is ready and every implementation item is
done and verified.

**Blocker 1 — 7 items short.** The slot-filling half is now **complete**; the only gap left
is the Batch-5 contradicted set, which Part A has just unblocked.

| | present | target | missing |
|---|---:|---:|---:|
| verification | 23 | 30 | **7** — all `contradicted` |
| slot-filling | **30** | 30 | **0 ✅** |
| **total** | **53** | **60** | **7** |

Verification currently sits at 10 supported / 10 undetermined / **3** contradicted; the 7
missing items take the contradicted class to 10 and the set to the intended 10/10/10.

**Blocker 2 — stop condition 5 fires.** The caching-off projection, which the spec
designates as the number to budget against, is **AUD 73.51 against ~AUD 63 remaining —
over by AUD 10.51**. With caching realised it is AUD 43.70, comfortably inside. Caching is
verified working (B7: 93–98% of prompt cached), so the run is affordable *in practice*, but
the figure the spec nominates exceeds budget. Reducing the run shape is explicitly an
author decision.

---

## Integration with `34e87b5`

The incoming commit touched `postretrieval.py`, which I had also modified. Resolution:

- **Their loop reorder was kept, mine discarded.** Theirs nests
  `condition → format → model → task → trial`; mine nested `format → model → condition →
  task → trial`. Both put format and model above task and trial with **trial innermost**,
  which is the property that matters, and theirs keeps the WI2 floor collapse inline. Their
  committed version is now the only implementation.
- **My B1 wiring was re-applied on top** of their version: `build_user_content_segments`,
  the `call_kwargs` block in `run_one`, and the Anthropic `cached_prompt_tokens`
  normalisation. No other file in the commit overlapped my changes.
- **One loose end closed.** The comment their commit added to `run_postretrieval` cites
  `tests/test_postretrieval_loop_order.py` as the verification for its order-only claim,
  but **that file was not in the commit**. I have written it
  (`experiment/tests/test_postretrieval_loop_order.py`, 4 tests, all passing) so the cited
  evidence exists. It asserts the multiset equality, trial contiguity, Llama
  non-interleaving, and the floor-sentinel collapse.

Their comment also notes the stop-condition-2 check "must still be run once the providers
are provisioned". The providers are now provisioned and the enumeration proof is below;
the remaining real-call confirmation is listed under *What must happen next*.

Test suites after integration: **34/34** (`test_harness_changes`) and **4/4**
(`test_postretrieval_loop_order`).

---

## B1 — Anthropic provider branch · **DONE**

`llm_call.detect_provider` routes `llama` → Ollama, `claude` → Anthropic, else OpenAI.
`_call_anthropic` implements a Messages-shaped request with:

- **Structured output via tool use** (WI-9 option (a)), `tool_choice` forcing
  `submit_verification` / `submit_slot_filling`. Schemas mirror `VerificationResponse` /
  `SlotFillingResponse` exactly, and the tool input is dumped back to a JSON string so
  `parse_response` stays the single shared parsing path — the Anthropic arm is graded by the
  same code as every other arm. No JSON-mode instruction was added to the prompt.
- **The corpus as its own content block** with a `cache_control: ephemeral` breakpoint after
  it. `build_user_content_segments` splits the user prompt at the corpus boundary, and
  `build_user_content` is now *defined as* `"".join(segments)`, so the two cannot drift.
  `_call_anthropic` additionally raises if the segments do not reassemble to the shared
  `user_content`.
- No `seed` parameter (absent from the Anthropic API; recorded as absence, per CHANGELOG
  2026-08-04 (d)).

**Prompt-identity assertion (stop condition 6): NOT tripped.** Re-run against the merged
HEAD (`34e87b5`): today's `build_user_content` compared with the committed implementation
across **1,484 prompts** (53 tasks × 7 formats × 4 conditions) — **0 mismatches**. The
OpenAI and Ollama branches read `user_content` and nothing else, so their payloads are
byte-identical to before.

One incidental fix was required: `pricing.resolve_model_price` had no Anthropic entry and
raised `KeyError`, which would have crashed `summarise_cost` at manifest write. It now falls
back to the cache-aware table for arms adopted after the 2026-06-07 snapshot, leaving
`MODEL_PRICES` and that snapshot untouched so existing manifests still reproduce.

## B2 — Loop reorder · **DONE (theirs), verified order-only**

Re-verified against the merged implementation by stubbing `run_one` and enumerating the
full **9,540-call** sweep (53 tasks × 4 models × 15 cells × 3 trials):

| check | result |
|---|---|
| identical call multiset `(task, format, condition, model, trial_idx, seed)` | **True** |
| same call count (9,540) | **True** |
| order actually changed | **True** |
| no duplicated calls | **True** |
| **trials of a cell run back-to-back** | **True — 0 violations** |
| Llama never interleaved between API calls of a cell | **True** — contiguous blocks of 159 |
| floor collapses to one sentinel cell | **True** |

**Stop condition 2 does not fire:** the reorder changes call order only.

A note on *what* is cacheable, which the spec's framing understates: in the chunked
conditions the corpus block is **task-specific**, so there is no shared prefix across tasks
within a cell. The only cacheable repetition is the **3 trials of one prompt**, differing
solely by seed. Trial-innermost is therefore the whole mechanism.

`config.ANTHROPIC_CACHE_CORPUS = True` gates the breakpoint and documents that it must be
set `False` if the ordering is ever reverted.

## B3 — Retrieval stage · **RUN (53 tasks)** → `superseded/retrieval-trial-13`

Single-trial, deterministic, all seven format indexes. FAISS indexes were already cached by
content checksum, so the only spend was query embeddings (negligible, as predicted).

Recall@5: elot-org-ancestors 0.645 · omn 0.642 · ofn 0.633 · jsonld 0.632 · elot-org 0.631 ·
turtle 0.613 · yaml-ld 0.592. *(Lower across the board than the 38-task run — the 15 new
slot-filling items are harder to retrieve for. Reported, not interpreted.)*

**Index-composition check — the spec's assumption needs correcting.** The retrieval index is
*not* restricted to `owl:Class` / `owl:ObjectProperty` / `owl:DataProperty`:

| format | eligible | named entities | non-named (disjointness axiom chunks) |
|---|---:|---:|---|
| turtle, jsonld, yaml-ld, ofn, omn | 158 | 155 | **3** |
| elot-org, elot-org-ancestors | 156 | 155 | **1** |

- **Named-entity parity is exact**: all seven formats expose the identical 155 named entities
  (50 classes, 102 object properties, 3 datatype properties). `owl:DatatypeProperty` is
  simply the RDF spelling of the spec's "owl:DataProperty" — not a discrepancy.
- The 156-vs-158 gap is entirely the **disjointness-materialisation asymmetry**: ELOT
  collapses all disjointness into one `elot-axiom:Disjointness-clauses` chunk where every
  other format carries 3. Now quantified at the index level — the ELOT arms retrieve *one*
  chunk where other arms must find the right *one of three*. Directly relevant to the 7
  remaining bare-disjointness / domain-range contradicted items.
- **No gold-bearing field in the 53 references an excluded chunk** (Phase 0.3 guard: clean).

## B4 — Llama prompt-length assertion · **PASS**

`num_ctx = 16384` unchanged. Measured over all 53 tasks × 7 formats using the harness's own
context assembly and the Llama tokenizer.

- **Maximum = 6,850 tokens**, in cell **T55 / jsonld / oracle** (slot-filling, 8 gold chunks).
- Headroom **9,534 tokens**; margin **2.39×**.
- **Stop condition 3 (any cell within 2× of 16,384): NOT tripped.**
- The new Batch-5 items land where expected: T55/T56/T57 join T40/T41 at the top of the
  distribution, all JSON-LD/YAML-LD oracle cells with 6–8 gold chunks. They did not move the
  maximum materially (6,848 → 6,850).
- System prompts: verification 137 tokens, slot-filling **614** (spec said 613; off by one).
- `retrieved` is bounded above by the k=5 largest *retrieval-eligible* chunks: worst case
  **6,013 tokens** (jsonld). Oracle is the binding case, as the spec anticipated — though the
  peak is JSON-LD rather than an ELOT arm, because ELOT's largest chunks are the
  retrieval-excluded section chunks.
- `prompt_eval_count` guard is active on **every** Ollama call (`llm_call._call_ollama` raises
  if the returned count deviates from the locally-computed count by more than 64 tokens). It
  stayed silent across all 28 Llama smoke calls.

⚠️ Re-run once the final 7 items are authored. They are verification items, which are the
*shorter* type, so the maximum is unlikely to move — but the check is free.

## B5 — Cost projection · **STOP CONDITION 5 FIRES**

Projected on the **target 30/30 mix**. Prompt tokens are exact: oracle contexts assembled
offline, `retrieved` contexts rebuilt from `superseded/retrieval-trial-13`'s recorded `retrieved_ids`,
so no embedding spend was repeated. The slot-filling mean is now measured on all **30** items
(420 cells); verification still rests on 23 of 30. Output tokens are observed pilot means
(verification 49.3, slot-filling 98.0).

Run shape: 60 × 7 × 2 × 3 = 2,520 calls/model; 7,560 API + 2,520 local.

| model | caching OFF | caching ON | saving |
|---|---:|---:|---:|
| gpt-4o-2024-11-20 | $16.12 | $11.37 | 29% |
| gpt-4o-mini-2024-07-18 | $0.97 | $0.68 | 29% |
| claude-sonnet-4-5-20250929 | $31.27 | $16.70 | 47% |
| llama3.1:8b-instruct-q8_0 (local) | $0.00 | $0.00 | — |
| **TOTAL API** | **$48.36** | **$28.75** | **41%** |

- **Budget against: USD 48.36 = AUD 73.51 → exceeds ~AUD 63 by AUD 10.51.**
- **The B2 reorder buys: USD 19.61 = AUD 29.81.** With caching, AUD 43.70 — AUD 19.30 headroom.

**A measured correction that changes the answer.** Sonnet was initially projected using
OpenAI token counts. Across 28 identical smoke prompts, **Anthropic's tokenizer counts
1.664× what `o200k_base` does** on this ontology text (range 1.46–1.89; Llama is 1.008×,
i.e. equivalent). Pricing Sonnet on OpenAI counts understates it by ~66%. The table applies
the measured multiplier. Worth recording independently: it makes Sonnet the **most expensive
arm despite a lower headline rate than gpt-4o**.

**Two caveats on the AUD figures.** (i) The FX rate 1.52 AUD/USD is my assumption — no rate is
pinned anywhere in the repo. (ii) The ~AUD 63 remaining comes from the spec itself, which says
to recompute from the provider export rather than the ledger; I have no access to that export,
so the reconciliation is outstanding and the comparison inherits its uncertainty.

## B6 — Manifest completeness · **GAPS FOUND AND CLOSED (one outstanding)**

Present before this session: `trial_seed_map`, `cached_prompt_tokens` per row,
`ollama_num_ctx`, provider/model pins. Added:

| field | note |
|---|---|
| `task_file` + **`task_file_sha256`** | was **missing entirely** — the spec's own reason for asking. Path alone is insufficient: `tasks_60.yaml` gained 15 items this session under an unchanged path, which is exactly the drift a hash catches. |
| `pricing_snapshot_date`, `cache_pricing_snapshot_date` | were only in `pricing.py`, never recorded |
| `ollama_kv_cache_type` | read from env; recorded as observed-or-default, since Ollama takes it from the `ollama serve` environment, not from our request |
| `anthropic_cache_corpus`, `postretrieval_loop_order` | so a run records whether caching was on and under which nesting |

**Blocking gap also fixed:** there was **no way to run `tasks_60.yaml` at all.** `select_tasks`
called `load_tasks()` with no argument, always loading the 5-task pilot. A `--task-file` flag
now exists (default unchanged: `tasks.yaml`).

⚠️ **Still outstanding: `graded_stability_rate` per arm is not computed anywhere.** The string
appears in `postretrieval-trial-12/manifest.json` but in **no source file**, so the harness
never produced it. Required per arm by the spec. Not implemented here — which fields and what
denominator is a methodology choice, not a mechanical one.

## B7 — Smoke test · **PASS** (112 calls, USD 0.47)

2 tasks (T06 verification, T29 slot-filling) × 7 formats × 2 conditions × 4 models × N=1 →
`superseded/postretrieval-trial-13` *(pre-pull; the plumbing it exercises is unchanged by the merge —
the Anthropic branch and segment split were re-applied verbatim and re-verified above)*.

| check | result |
|---|---|
| all four providers return parseable structured output | **112/112 `parse_ok`**, zero parse errors |
| providers routed correctly | `anthropic`, `openai`, `ollama` all present |
| **Sonnet tool-use path** | **28/28 parsed** — the WI-9 markdown-fence failure does not occur |
| truncation guard silent | **yes**, no trip across 28 Llama calls |
| cost per call within 20% of projection | **yes: −9% (Sonnet), −16% (gpt-4o), −17% (mini)** — all under |

**Cache-hit fraction.** The spec's own smoke shape cannot demonstrate this: at **N=1**,
consecutive calls in a cell have *different* prompts, so no corpus prefix can be reused. The
smoke duly showed ~0 cached tokens — and on Anthropic that means every call paid the 1.25×
**write** premium with no read, i.e. the "worse than no caching" case the spec warns about.
This is a flaw in the specified smoke shape, not in the implementation.

A dedicated N=3 probe (the real run's configuration, trials innermost, back-to-back) on
T29/jsonld/oracle:

| model | prompt | cache read | fraction cached |
|---|---:|---:|---:|
| claude-sonnet-4-5-20250929 | 3,156 | 3,107 | **98.4%** |
| gpt-4o-2024-11-20 | 1,921 | 1,792 | **93.3%** |

Hits on **every** call of both cells. **Stop condition 4 does not fire**: the reorder pays, at
a higher cached fraction than the B5 projection assumed.

*Per the spec: smoke results are not interpreted. N=1, two tasks. The diagnostics flags in
trial-13 (ceiling, single-label) are artefacts of a one-verification-task smoke.*

## B8 — Sonnet contamination floor · **RUN** (46 calls, USD 0.18) → `superseded/postretrieval-trial-14`

23 verification items, no-context and empty-context, N=1.

| condition | accuracy | majority baseline | delta | modal prediction |
|---|---:|---:|---:|---|
| `empty_context` | 0.391 | 0.435 | **−0.043** (below) | `undetermined` (87%) |
| `no_context` | 0.522 | 0.435 | +0.087 (above) | `undetermined` (61%) |

**No contamination signal.** Sonnet abstains heavily without context, and the above-baseline
`no_context` figure is explained by that abstention prior meeting a set in which 10 of 23
items are genuinely `undetermined` — not by knowledge of IDO. Consistent with WI-6's
~zero-parametric-knowledge result on the other arms, and it converts the pre-FDIS-by-dates
argument into a direct measurement, which was WI-6's principle. Caveat: n=23, N=1, and the
current 23 items are unbalanced (10/10/3), which inflates the baseline relative to the
intended 10/10/10. Worth re-running once the 7 contradicted items land.

---

## What must happen before the main run

1. **Author the final 7 contradicted verification items.** Part A clears the functional-property
   stratum (2 of the 7); the other 5 are 3 direct domain/range + 2 composed domain/range.
   This is now the *only* authoring work outstanding.
2. **Decide the budget question** (author): accept the run on the strength of verified caching
   (AUD 43.70), reduce the run shape, or top up. The caching-off figure exceeds remaining budget.
3. **Implement `graded_stability_rate`** per arm — definition needed.
4. **Run the real-call stop-condition-2 check** on a small verification subset: identical
   results for a fixed seed under the new ordering. The enumeration proof is done; their own
   comment asks for the live confirmation, and the providers are now provisioned.
5. **Re-run B4, B5 and the retrieval stage** on the completed 60.

## Methodology-log entries to write (flagged, not written)

1. **Anthropic arm implemented via tool use with a corpus cache breakpoint**; prompt-identity
   verified byte-identical against HEAD over 1,484 prompts.
2. **Loop reorder verified order-only by enumeration** over the full 9,540-call sweep, with the
   test the `run_postretrieval` comment cites now committed.
3. **Anthropic tokenizer counts 1.664× OpenAI's on this ontology text** (measured, n=28) —
   makes Sonnet the most expensive arm despite a lower headline rate.
4. **Retrieval index contains disjointness axiom chunks**, 3 per format but **1** for ELOT;
   named-entity parity (155) is exact across all seven.
5. **Manifest provenance extended** (task-file hash, pricing snapshot dates, KV cache type,
   cache/loop-order flags) and a `--task-file` flag added; the 60-task set was previously
   unrunnable from the CLI.
6. **Sonnet contamination floor measured directly** — no signal beyond an abstention prior.
