# Oracle `undetermined` degeneracy — determination

**Date:** 2026-08-27 · **Scope:** Phases 0–3, complete.
**Inputs:** `experiment/results/postretrieval-combined-15-18/postretrieval_raw.csv`
(10,080 rows; 5,040 verification), `experiment/benchmark/tasks_60.yaml`
(`36cb27c1…8bd1148`), and the diagnostic sub-study
`experiment/results/probe_b2_openworld/` (540 rows, $2.47). Phases 0 and 1 made **zero API
calls**. Nothing was regraded, and nothing was written to the frozen benchmark.

> **RESOLVED. All four pre-registered hypotheses are rejected; all four resolution criteria
> are met.** H1 (parser loss), H3 (closed-world reading of oracle context) and H4
> (condition-invariant family behaviour) fall on existing data (§2). **H2 (prompt-induced
> suppression) falls on Probe B2** (§9): told explicitly that absence of an entailing axiom
> does not establish contradiction, **gpt-4o changed 0 of 90 rows and 0 of 30 cells**, while
> Sonnet moved **+0.111 [+0.022, +0.222]** on the same items as a positive control.
>
> **The surviving account is the gating rule in §1.1** — the GPT arms abstain on
> *non-retrieval* and never on *non-entailment*. This is a model-behaviour finding, not a
> harness defect. **Per the §8 pre-commitment: no re-run. The frozen run stands as run.**

---

## 1. Headline

The blocker as stated — "GPT arms never emit `undetermined` under `oracle`" — is true but
is **not the right cut of the data**. The label is not gated on the `oracle` condition. It
is gated on **whether the gold chunks are in the context at all**.

| GPT arms, verification | n | `undetermined` |
|---|---:|---:|
| gold chunks fully present, `oracle` | 1,260 | **0** |
| gold chunks fully present, `retrieved` | 774 | **2** (0.3%) |
| gold chunks **not** fully present, `retrieved` | 486 | **106** (21.8%) |

Both GPT arms abstain readily — 21.8% of the time — when retrieval misses. When the
licensing material is in front of them they abstain **twice in 2,034 rows**, and never on
an undetermined-gold item. `oracle` guarantees gold presence by construction, which is the
whole of why the count there is exactly zero.

### 1.1 All four arms, split by gold presence and by stratum

The gating rule is not a GPT peculiarity, and the four arms are not merely at different
points on one scale. Undetermined rate, both conditions pooled:

| arm | **gold ABSENT** determinate | **gold ABSENT** undet-gold | **gold PRESENT** determinate | **gold PRESENT** undet-gold |
|---|---:|---:|---:|---:|
| gpt-4o | 0.356 | 0.182 | 0.000 | **0.000** |
| gpt-4o-mini | 0.147 | 0.076 | 0.003 | **0.000** |
| llama3.1:8b | 0.497 | 0.318 | 0.142 | **0.014** |
| claude-sonnet-4-5 | 0.475 | 0.333 | 0.000 | **0.251** |
| *n per cell* | *177* | *66* | *663* | *354* |

Two things fall out, and they are different things.

**The missing-material response is universal.** Every arm abstains when the licensing
chunks are absent — 0.128 to 0.449 pooled. So the rule in §1 is not specific to the GPT
family; the arms differ in degree there.

**Abstention on non-entailment is not universal, and that is the real contrast.** With the
licensing material fully in context, only Sonnet abstains, and only on the stratum where
abstention is correct: **0.251 on undetermined-gold against 0.000 on determinate items**.
The GPT arms are flat zero on both. Llama abstains with material present but in the wrong
place — 0.142 on determinate against 0.014 on undetermined-gold.

So the finding is **not** "one gating rule, four degrees". It is that abstention has two
distinct triggers, and the arms possess different subsets of them:

| trigger | gpt-4o | gpt-4o-mini | llama | sonnet |
|---|:--:|:--:|:--:|:--:|
| material missing from context | ✓ | ✓ | ✓ | ✓ |
| material present, statement not entailed | ✗ | ✗ | ✗ | **✓** |

Only Sonnet's abstention behaviour responds to **non-entailment** as opposed to
**non-retrieval**. The GPT arms implement a retrieval-failure heuristic and nothing more;
on this evidence they are not implementing open-world semantics at all, and the frozen
prompt's definition of `undetermined` ("neither entails nor contradicts it") is not
reaching their decision.

One caution on reading the gold-absent columns as competence: for **every** arm, including
Sonnet, the gold-absent abstention rate is *higher* on determinate items (0.475) than on
undetermined-gold ones (0.333). When the material is missing, everything looks
unanswerable. Gold-absent abstention is a response to an empty-handed context, not
evidence that any arm has understood the task's semantics.

---

## 2. Verdicts against the pre-registered hypotheses

### H1 — parser or schema loss: **REJECTED**

Across all 1,260 affected rows:

| pattern searched (case-insensitive, whole raw completion) | rows matching |
|---|---:|
| `undetermined`, `undecided`, `cannot be determined`, `insufficient`, `not enough information`, `unknown`, `neither`, `abstain` | **0** |

- `parse_ok` is `True` on **1,260 / 1,260**. No affected row took the failure path.
- The `label` field read straight out of the raw JSON disagrees with the harness's
  `pred_label` on **0** rows.
- The parser cannot silently coerce: `Label` is a pydantic `Literal` ([schemas.py:20](../../src/rag/experiment/schemas.py#L20)),
  so an out-of-vocabulary label raises `ParseError` and lands as `pred_label = None`
  ([postretrieval.py:303-312](../../src/rag/experiment/postretrieval.py#L303-L312)) — visible, never
  defaulted to a valid label.

Nothing is being lost. The models do not write the word.

### H3 — closed-world reading of *oracle* context: **REJECTED**

H3 predicted the label returns when the apparent completeness of the oracle extract is
perturbed. **The frozen run already contains that condition, 387 times per GPT arm**, and
it does not return.

| | oracle | retrieved, gold fully present |
|---|---:|---:|
| chunks in context | 2.7 | **5.0** |
| non-gold chunks | 0.13 | **2.73** |
| context chars | 4,816 | **7,500** |
| gpt-4o `undetermined` | 0 / 630 | **0 / 387** |
| gpt-4o-mini `undetermined` | 0 / 630 | **2 / 387** |

Every one of those 387 rows per arm carries at least one non-gold chunk. A context that is
larger and carries additional non-gold material recovers the label **zero times**.
Context length is not the trigger, and neither is the presence of material beyond the gold
chunks.

**This is a weaker instrument than Probe C would have been, and the wording matters.** The
non-gold chunks here are top-*k* nearest neighbours, so they are the *most* similar
non-gold chunks in the index — closer to plausible near-misses than to irrelevant padding,
and arguably they make the context read as *more* topically complete rather than less. So
this cell does not test "apparent incompleteness" the way Probe C's random padding would
have. The rejection of H3 rests on the recovery count being **exactly zero across 774
rows**, not marginal: a mechanism that survives only under padding drawn from a different
distribution, while producing no detectable signal at all under 2.73 near-miss chunks per
row, is not a mechanism this study can or should pursue.

**Consequence: Probe C (oracle padding) is falsified before it is run and should not be
run.** It is a re-derivation of a cell the frozen run already contains. The §7 limitation
that `oracle_padded` was never run stands as a design limitation, but it is no longer a
live confound for *this* blocker.

### H4 — model-family behaviour, condition-invariant: **REJECTED as stated**

H4 predicted no occurrences under `retrieved` either. There are 75 (gpt-4o) and 33 (mini).

| model | oracle | retrieved | Δ |
|---|---:|---:|---:|
| gpt-4o | 0.000 | 0.119 | +0.119 |
| gpt-4o-mini | 0.000 | 0.052 | +0.052 |
| llama3.1:8b | 0.100 | 0.230 | +0.130 |
| claude-sonnet-4-5 | 0.089 | 0.221 | +0.132 |

The label is fully reachable through the prompt, schema and parser for the GPT arms. What
is invariant is not the family's use of the label but the **gating rule** (§1).

### H2 — prompt-induced suppression: **REJECTED (Probe B2, §9)**

The strong form of H2 was already dead on existing data: the prompt is byte-identical
across conditions (`verification_system_v1.txt` on all 5,040 verification rows), so the
prompt alone cannot produce a contrast between conditions.

The surviving form — that the prompt supplies a mapping permissive enough for
*not entailed* to reach `contradicted`, which §3 gives direct evidence for — was tested by
Probe B2 and **falsified**. Adding an explicit statement that absence of an entailing axiom
does not establish contradiction changed **0 of 90 gpt-4o rows and 0 of 30 cells**, and 1
of 90 mini rows. Sonnet, on the same items, moved +0.111 with a CI excluding zero, so the
variant is demonstrably not inert. Full result in §9.

---

## 3. The mechanism, from the models' own reasoning

On undetermined-gold rows answered `contradicted`, the reasoning text was scanned for
cue phrases:

| model | n rows | absence-as-refutation | explicit-negation claim | hierarchy language |
|---|---:|---:|---:|---:|
| gpt-4o | 408 | **0.272** | 0.172 | 0.831 |
| gpt-4o-mini | 415 | **0.202** | 0.181 | 0.672 |
| llama3.1:8b | 393 | 0.094 | 0.257 | 0.875 |
| claude-sonnet-4-5 | 309 | 0.126 | 0.175 | 0.913 |

Verbatim, `oracle`, undetermined-gold, answered `contradicted`:

> **gpt-4o / T22:** "…both subclasses of `lis:InformationObject`, **but there is no
> indication that** `lis:UnitOfMeasure` is a subclass of `lis:QualityDatum`."

> **gpt-4o-mini / T20:** "…`ActivityProfile` is a subclass of `Activity` **but not stated
> to be** a subclass of `Event`, **thus contradicting the statement**."

> **gpt-4o / T24:** "…`lis:Feature` is a subclass of `lis:PhysicalObject`, **but it does
> not state** that it is a subclass of `lis:PhysicalArtefact`."

This is not a reasoning failure. In roughly a quarter of these rows the model **performs
the undetermined analysis correctly** — it identifies that no entailing axiom is present —
and then files that conclusion under `contradicted`. The mini/T20 row makes the invalid
step explicit: *not stated* → *thus contradicting*.

The failure is a **label-mapping error under a closed-world default**, not an inability to
detect underdetermination. That is what makes H2 still worth one probe: the prompt is what
supplies the mapping, and the mapping is the thing that is wrong.

---

## 4. A correction to §6.1 of `60task-analysis.md`

§6.1 states that "Sonnet and Llama use all three labels in every cell and are unaffected."
**Llama is affected.** Its label support passes the check while being *negatively*
informative. On gold-present rows:

| model | P(und \| gold determinate) | P(und \| gold = undetermined) | discrimination |
|---|---:|---:|---:|
| claude-sonnet-4-5 | 0.000 | **0.251** | **+0.251** |
| gpt-4o | 0.000 | 0.000 | 0.000 |
| gpt-4o-mini | 0.003 | 0.000 | −0.003 |
| llama3.1:8b | **0.142** | 0.014 | **−0.128** |

Llama emits `undetermined` ten times more often on items where it is *wrong* than on items
where it is right. **Sonnet is the only arm of the four that uses the label
discriminatively.** The label-support check in §6.1 is the wrong instrument; the
discrimination column above is the right one, and it should replace it.

**"Discriminative" is a comparative claim, not a pass mark.** On the gold-present
undetermined-gold stratum, accuracy is:

| arm | correct | n | accuracy |
|---|---:|---:|---:|
| claude-sonnet-4-5 | 89 | 354 | **0.251** |
| llama3.1:8b | 5 | 354 | 0.014 |
| gpt-4o | 0 | 354 | 0.000 |
| gpt-4o-mini | 0 | 354 | 0.000 |

Sonnet gets **265 of 354 wrong** — it answers `contradicted` on three quarters of the
stratum, with the licensing material in front of it. The correct statement is that Sonnet
is the only arm whose abstention responds to non-entailment *at all*, not that Sonnet
handles the stratum acceptably. **No arm in this study does.** The 90.8% cross-model
`contradicted` rate on undetermined-gold rows reported in `60task-analysis.md` is a
finding about all four arms, and §4 here does not soften it.

---

## 5. Trial stability

Whole cells, not trials, decide the label. Of 210 GPT `oracle` cells per arm, **210 are
`never(0/3)`** — zero split cells. Under `retrieved` the label is also mostly a cell-level
property (gpt-4o: 24 always, 184 never, 2 split; mini: 7 always, 196 never, 7 split).
The degeneracy is not seed noise.

---

## 6. Which cells of the frozen run remain interpretable

**Three of the four arms are ruled out for three-label verification reporting.** Only
Sonnet's verification results can be read across all three labels, and even then §4's
caveat applies. This is a real narrowing of what the results chapter can claim — but it is
itself the finding, and a more substantial one than the format contrast the benchmark was
built to detect: **the study's largest headline format spread is 0.033, while the gap
between arms that can represent underdetermination and arms that cannot is total.**
It should be reported as a result, not carried as an apology for a null.


- **GPT-arm `oracle` verification accuracy must not be reported as a three-label figure.**
  It is capped at 2/3 by construction; accuracy on the undetermined class is exactly 0.000
  in 630/630 rows per arm. §6.1's existing prohibition on drawing format contrasts from
  these cells **stands and is strengthened** — the spread there is between two labels.
- **The correct restatement is broader than `oracle`.** The cap applies to every
  GPT-arm verification cell in which the gold chunks reached the context, `retrieved`
  included (774 further rows, 2 abstentions). Reporting `retrieved` as the
  "uncapped" comparison arm is wrong: its abstentions come almost entirely from the
  retrieval-miss subset.
- **The 20 determinate verification items remain fully interpretable for all four arms.**
  Selective prediction on those, as §3.1 already reports, is unaffected.
- **Sonnet `oracle` verification is interpretable across all three labels.**
- **Llama verification should not be reported as three-label either**, on the §4 grounds —
  a different defect from the GPT arms, but the same consequence.
- The oracle-vs-retrieved verification contrast (§3.3) is confounded for the GPT arms, as
  §6.1 says — but the confound is **gold-chunk presence**, not context precision or size,
  and the §7.10 framing should be corrected accordingly.

---

## 7. What Phase 2 should now be

Two of the four pre-registered probe designs are dead on Phase 0/1 evidence:

- **Probe C (oracle padding) — drop.** Falsified by §2/H3. The frozen run already contains
  387 padded-gold rows per arm at 0 recovery.
- **Probe B3 (label definitions) — drop.** It is already the frozen condition.
  `verification_system_v1.txt` defines all three labels, including
  `"undetermined": the ontology content neither entails nor contradicts it`. Running it
  would re-run the baseline.

Three remain, and the mechanism in §3 says which one matters:

| probe | targets | cost (3 models, 180 calls each, uncached) |
|---|---|---:|
| **B2 — explicit open-world statement** | the exact failure in §3: *not entailed* → `contradicted` | $3.01 |
| **A — logprobs on the frozen prompt** | knife-edge suppression vs hard collapse | $3.01 + harness change |
| **B1 — label order permutation** (×2) | ordering artefact | $6.02 |
| **B4 — abstention permission** | abstention framed as failure | $3.01 |

Per-arm split: gpt-4o $0.98, gpt-4o-mini $0.06, sonnet $1.98 — Sonnet is two thirds of the
bill and is only a control. Costed against the pinned `2026-06-07` snapshot at measured
token means (1,967 prompt / ~52 completion per GPT verification call). Caching should take
30–50% off.

**Probe A needs a harness change**: [llm_call.py:365-374](../../src/rag/experiment/llm_call.py#L365-L374)
does not pass `logprobs`/`top_logprobs`. It would be added as an opt-in kwarg defaulting to
off, so the frozen call path stays byte-identical.

**Decision taken: B2 alone.** It targets the documented mechanism directly, and its outcome
determines whether anything else is worth running.

**Outcome (§9): B2 did not recover the label on either GPT arm.** H2 is dead and the
determination is the gating rule in §1.1 — a model-behaviour finding, not a harness defect,
and no re-run of the frozen benchmark is warranted.

**Probes A, B1 and B4 are therefore not run, and that is a deliberate stop rather than an
omission.** B2 was the strongest of the three: it names the exact inferential error the
models make in their own reasoning (§3), and it is the only variant whose content the
models are demonstrably capable of acting on, since Sonnet acted on it. A label-order
permutation (B1) or an abstention-permission sentence (B4) is a weaker intervention than
the one that just produced a flat zero across 30 cells. Probe A (logprobs) would still
answer a genuinely different question — whether the label carries non-trivial probability
mass and loses, or near-zero mass — and it remains the one probe with residual value if the
knife-edge-versus-hard-collapse distinction is wanted for the write-up. It is not needed
for the determination.

---

## 8. What B2 is — pre-committed before the run

**B2 is a prompt-sensitivity probe, not a defect test. Neither outcome triggers a re-run.**
This is committed here, before the probe executes, so that the result is read against a
fixed interpretation rather than one chosen after seeing it.

**The reasoning.** `verification_system_v1.txt` already defines the label correctly:
*"undetermined": the ontology content neither entails nor contradicts it*. That is a
complete and accurate statement of the semantics, and it is exactly why Probe B3 was
dropped as redundant. B2 does not repair a missing instruction — it adds a redundant
open-world nudge on top of a definition that is already right. So:

- **If B2 recovers the label**, the finding is that the GPT arms need the correct semantics
  restated in a second, more explicit form before they will act on them. That is
  **brittleness under paraphrase of an already-correct instruction** — a sensitivity
  result, and a publishable one. It is not evidence that the frozen prompt was defective,
  and therefore not grounds for re-running the benchmark under a "corrected" prompt.
- **If B2 does not recover the label**, the closed-world mapping is robust to explicit
  instruction against it, which is a stronger version of the same finding.

Either way the frozen run stands as run, and the headline numbers are unchanged.

**Where it lands in the write-up.** Next to the prompt-sensitivity literature — Sclar et
al. on formatting/spurious-feature sensitivity — as a measurement of how much a correct
instruction has to be restated before a model acts on it. Not in an erratum, and not as a
harness-defect narrative.

**What is explicitly *not* proposed:** the 5,040-row verification re-run (30 items × 7
formats × 2 conditions × 4 models × 3 trials) that an earlier draft of this section held
open as a conditional. It is off the table under both outcomes. H1 and H3 — the two
hypotheses that would have made this a harness defect — are rejected on the evidence in
§2, and no prompt-sensitivity result reclassifies a correct instruction as a broken one.

**The one thing B2 could still change** is the §6 interpretability list: a recovery would
mean the 2/3 cap is a property of *this prompt* with these models rather than of the
models alone, and §6 would need to say so. That is a change to how the cap is described,
not to which cells are reportable.

---

## 9. Phase 2 execution record — Probe B2, COMPLETE

**Decision taken (2026-08-27):** run Probe B2 alone. Probes A, B1 and B4 not run; Probe C
and Probe B3 dropped as falsified/redundant per §7. Interpretation pre-committed in §8
**before** the run.

**Design as executed** — 20 items (T19–T28 undetermined-gold + T06–T13, T59, T60 controls)
× turtle/elot-org/jsonld × 3 models × 3 trials (seeds 20260529/30/31), `oracle`, **540
calls, complete, $2.47** against the pinned `2026-06-07` snapshot (1,026,233 tokens). Row
zero is the same 540 cells read from the frozen run — no baseline calls re-billed.
`parse_ok` 1.000 in both arms. Every probe row carries `system_prompt =
verification_system_v1_probe_b2.txt`; the post-run assertion passed.

### 9.1 Result — H2 is REJECTED for the GPT arms

Recovery of `undetermined` on the 10 undetermined-gold items (90 rows = 30 item×format
cells × 3 trials per arm):

| arm | frozen | B2 open-world | paired Δ over 30 cells [95% CI] | cells up / down / same |
|---|---:|---:|---|---|
| gpt-4o | 0 / 90 · 0.000 | 0 / 90 · **0.000** | **+0.000 [+0.000, +0.000]** | 0 / 0 / 30 |
| gpt-4o-mini | 0 / 90 · 0.000 | 1 / 90 · **0.011** | +0.011 [+0.000, +0.033] | 1 / 0 / 29 |
| claude-sonnet-4-5 | 20 / 90 · 0.222 | 30 / 90 · **0.333** | **+0.111 [+0.022, +0.222]** | 5 / 0 / 25 |

*(Paired on the cell and bootstrapped over cells, B = 20,000 — 90 rows per arm are 30 cells
× 3 trials, not 90 independent observations. This is a pooled statistic over cells, not a
test on any individual cell.)*

**Told explicitly that the content may be incomplete and that absence of an entailing axiom
does not establish contradiction, gpt-4o changed not one row of 90.** Every one of its 30
cells is unchanged. gpt-4o-mini moved a single cell.

### 9.2 Sonnet is the within-probe positive control, and it rules out an inert prompt

The obvious alternative reading — "the variant does nothing to anybody" — is excluded by
the design. On the **same items, same formats, same trials, same call path**, Sonnet moves
**+0.111, five cells up and none down, CI excluding zero**, at **zero cost**: false
abstention on the determinate controls stays 0.000 and determinate accuracy stays 1.000.

The variant works. It does not work **on the GPT arms**. That is an arm-specific null, not
a null probe.

### 9.3 The variant actively harms gpt-4o-mini

| gpt-4o-mini | frozen | B2 |
|---|---:|---:|
| accuracy, determinate items | 0.889 | **0.800** |
| false `undetermined` on determinate controls | 0.000 | **0.033** (3/90) |
| recovery on undetermined-gold | 0.000 | 0.011 (1/90) |

Mini pays 8.9 points of determinate accuracy and three false abstentions to buy one correct
abstention. The one row it did recover carries the right analysis — *"does not provide
enough information to determine whether every `lis:Feature` is a `lis:PhysicalArtefact`"* —
but the arm as a whole is made worse, not better, by being told the correct semantics more
explicitly. Report the trade, not the single recovered row.

### 9.4 Determination

**H2 is rejected.** The closed-world mapping in the GPT arms survives an explicit,
meaning-preserving instruction against it. Combined with §2, all four pre-registered
hypotheses are now resolved:

| hypothesis | verdict | decisive evidence |
|---|---|---|
| H1 parser/schema loss | **rejected** | 0 abstention strings in 1,260 raw completions; `parse_ok` 1.000 |
| H2 prompt-induced suppression | **rejected** | Probe B2: gpt-4o +0.000 over 30 cells, mini +0.011, with Sonnet +0.111 as positive control |
| H3 closed-world reading of oracle context | **rejected** | 0 recoveries across 774 gold-present `retrieved` rows |
| H4 condition-invariant family behaviour | **rejected as stated** | 75 and 33 `undetermined` rows under `retrieved` |

**The surviving account is the gating rule in §1.1**, and it is a model-behaviour finding,
not a harness defect: the GPT arms abstain on *non-retrieval* and never on *non-entailment*;
Sonnet is the only arm whose abstention responds to non-entailment, and even then it is
wrong on two thirds of the stratum. **Resolution criterion 3 is now met.**

**Per §8, pre-committed: no re-run.** The frozen run stands as run, and the headline numbers
are unchanged. Non-recovery is the stronger branch — the closed-world mapping is robust to
being instructed against, which is a more substantial claim than "the prompt was
suboptimal" would have been.

**§6 is unchanged by this result.** A recovery would have meant the 2/3 cap was a property
of this prompt with these models; non-recovery means the cap belongs to the models. Every
interpretability restriction in §6 stands as written.

### 9.5 Operational notes

- The account was funded mid-investigation. The first two attempts failed on
  `429 insufficient_quota` (no credits, 0 rows, nothing billed); the third hit
  `429 rate_limit_exceeded` — the tier-1 **30,000 TPM** cap on the `gpt-4o` limit group —
  after 42 calls. At ~2.4k tokens per verification call that ceiling allows roughly a dozen
  gpt-4o calls per minute.
- A retry-on-429 with provider-hinted backoff and jitter is installed **in the probe script
  only** (`install_rate_limit_retry`). `llm_call.py` still re-raises, which is correct for a
  paid benchmark run where a silent retry could mask a real fault. The wrapper re-raises
  immediately on `insufficient_quota`, so an out-of-credit state can never be absorbed as
  throttling. Retrying re-sends a byte-identical request with the same seed; only wall-clock
  spacing differs, so nothing measured is affected.
- `src/.env` contains **two** `OPENAI_API_KEY` lines. python-dotenv keeps the **first**.
  Harmless here — the first is the funded key — but it is a live footgun and should be
  deduplicated.


## Artefacts

`p0_raw_string_patterns.csv`, `p0_gpt_oracle_by_format.csv`, `p0_gpt_oracle_by_gold.csv`,
`p0_all_models_by_condition.csv`, `p0_all_by_condition_gold.csv`,
`p1_rate_by_model_cond_gold.csv`, `p1_rate_by_model_cond_format.csv`,
`p1_oracle_vs_retrieved.csv`, `p1_trial_stability.csv`, `p1_context_len.csv`,
`p1b_h3_gold_presence.csv`, `p1b_h3_gpt_detail.csv`, `p1b_h3_decisive.csv`,
`p1b_h3_all_models_goldpresent.csv`, `p1c_discrimination.csv`, `p1c_mechanism_cues.csv`,
`p1c_reasoning_sample.txt`, `p1e_four_model_gating.csv`,
`p1e_gold_present_discrimination.csv`, `p1e_gold_absent.csv`,
`p1e_undetermined_stratum_accuracy.csv`.

Probe B2: `probe_b2_t1_recovery_pooled.csv`, `probe_b2_t2_recovery_target.csv`,
`probe_b2_t3_side_effect.csv`, `probe_b2_t4_accuracy.csv`, `probe_b2_t5_by_format.csv`,
`probe_b2_t6_label_dist.csv`, `probe_b2_t8_paired_{gpt-4o,gpt-4o-mini,sonnet}.csv`,
`probe_b2_recovered_sample.txt`. Raw rows and manifest:
`src/rag/experiment/results/probe_b2_openworld/`.

Scripts: `src/rag/scripts/diagnostics/phase{0,1,1b,1c,1d,1e}_undetermined_audit.py`,
`probe_b2_openworld.py`, `probe_b2_analyse.py`.
