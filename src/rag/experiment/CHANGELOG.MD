# Methodology log

Tracks design decisions and changes to the experimental harness, schema,
and prompts. Each entry: date, what changed, why.

## 2026-08-27 - Oracle `undetermined` degeneracy RESOLVED: all four hypotheses rejected

Resolves analysis stop condition 3 (`docs/findings/60task-analysis.md` 6.1) in full. Full write-up: `docs/findings/oracle-undetermined-degeneracy.md`.
Phases 0 and 1 made **zero API and zero Ollama calls**; nothing was regraded and nothing
was written to the frozen benchmark.

**The blocker was cut on the wrong variable.** `undetermined` is not gated on the `oracle`
condition; it is gated on whether the gold chunks are in context. GPT arms, verification:
0/1,260 with gold present under `oracle`, 2/774 with gold present under `retrieved`, but
**106/486 (21.8%) when retrieval misses**. `oracle` guarantees gold presence by
construction, which is the whole of why its count is exactly zero.

**Hypotheses.** H1 (parser/schema loss) **rejected**: zero occurrences of `undetermined`,
`undecided`, `cannot be determined`, `insufficient`, `not enough information`, `unknown`,
`neither` or `abstain` in any of the 1,260 raw completions; `parse_ok` 1,260/1,260; raw
JSON `label` agrees with `pred_label` on every row; `Label` is a pydantic `Literal`, so
silent coercion is structurally impossible. H3 (closed-world reading of a clean oracle
extract) **rejected**: the frozen run already contains 387 rows per GPT arm at
`retrieved` + gold-present -- 5 chunks, 2.73 non-gold distractors, 7,500 chars, i.e. a
larger and visibly padded context -- with 0 recoveries. H4 (condition-invariant family
behaviour) **rejected**: 75 and 33 `undetermined` rows under `retrieved`. **H2 (prompt-induced suppression) rejected by Probe B2 -- see below.**

**Mechanism.** On undetermined-gold rows answered `contradicted`, 27.2% (gpt-4o) and 20.2%
(mini) of reasoning strings contain absence-as-refutation language -- the model states that
no entailing axiom is present and then files that under `contradicted`. One mini row makes
the invalid step explicit: "not stated to be a subclass of Event, thus contradicting the
statement". This is a label-mapping error under a closed-world default, not a failure to
detect underdetermination.

**Two pre-registered probes dropped.** Probe C (oracle padding) is falsified by the
`retrieved` + gold-present cells above. Probe B3 (label definitions) is already the frozen
condition -- `verification_system_v1.txt` defines all three labels.

**Correction to `60task-analysis.md` 6.1.** "Sonnet and Llama use all three labels and are
unaffected" is wrong about Llama. On gold-present rows, discrimination
P(und|gold=und) - P(und|gold determinate) is sonnet **+0.251**, gpt-4o 0.000, mini -0.003,
**llama -0.128** -- Llama emits the label ten times more often where it is wrong than where
it is right. Sonnet is the only arm using it discriminatively. The label-support check is
the wrong instrument; discrimination replaces it.

**Interpretability.** The 2/3 cap on GPT verification applies to every cell where gold
reached the context, not only `oracle`, so `retrieved` is not the uncapped comparison arm.
Llama verification should likewise not be reported as three-label. The 20 determinate items
and all Sonnet cells are unaffected.

**Abstention has two triggers, and the arms hold different subsets.** The missing-material
response is universal (gold-absent undetermined rate 0.128-0.449 across all four arms), so
the gating rule is not a GPT peculiarity. But with the licensing material fully in context,
only Sonnet abstains and only where it should -- **0.251 on undetermined-gold against 0.000
on determinate**. gpt-4o and mini are flat zero on both; Llama abstains in the wrong place
(0.142 determinate / 0.014 undetermined-gold). Only Sonnet's abstention responds to
non-entailment rather than non-retrieval; the GPT arms implement a retrieval-failure
heuristic and the frozen prompt's definition of `undetermined` is not reaching their
decision. Caveat recorded: for every arm including Sonnet, gold-absent abstention is
*higher* on determinate items (0.475) than undetermined-gold (0.333) -- an empty-handed
context makes everything look unanswerable, so that column is not evidence of competence.

**Sonnet is comparatively, not absolutely, competent.** Accuracy on the gold-present
undetermined-gold stratum is sonnet 0.251 (265 of 354 **wrong**), llama 0.014, both GPT arms
0.000. "Only arm using the label discriminatively" means only arm whose abstention responds
to non-entailment at all -- not that any arm handles the stratum acceptably. None does.

**H3's rejection rests on a zero count, not on the padding argument.** The `retrieved` +
gold-present cells carry 2.73 non-gold chunks per row, but those are top-k nearest
neighbours -- the most similar non-gold chunks available, closer to plausible near-misses
than to irrelevant padding, and arguably making the context read as more topically complete
rather than less. So they do not test "apparent incompleteness" the way Probe C's random
padding would have. The rejection holds because recovery is **exactly zero across 774
rows** rather than marginal. Wording corrected in the findings doc accordingly.

**B2 is pre-committed as a sensitivity probe, not a defect test -- neither outcome triggers
a re-run.** Recorded before execution. `verification_system_v1.txt` already defines the
label correctly, which is why B3 was dropped; B2 therefore adds a redundant open-world
nudge on top of a correct definition. Recovery would show the GPT arms need correct
semantics restated in a second explicit form before acting on them -- brittleness under
paraphrase of an already-correct instruction, a publishable sensitivity result that belongs
next to Sclar et al. in the prompt-sensitivity literature, not in an erratum. Non-recovery
shows the closed-world mapping is robust to explicit instruction against it. Either way the
frozen run stands as run. **The 5,040-row verification re-run an earlier draft held open as
a conditional is explicitly off the table under both outcomes.** The only thing a recovery
changes is whether the 2/3 cap is described as a property of this prompt with these models
or of the models alone.

**Three of four arms are ruled out for three-label verification reporting.** Only Sonnet
can be read across all three labels. That narrows the results chapter, but it is the
finding: the largest headline format spread in the study is 0.033, while the gap between
arms that can represent underdetermination and arms that cannot is total.

**Probe B2 built, run, COMPLETE -- H2 rejected.** `prompts/verification_system_v1_probe_b2.txt`
plus `scripts/diagnostics/probe_b2_openworld.py` (runner) and `probe_b2_analyse.py` (tables).
20 items x 3 formats x 3 models x 3 trials = **540 calls under `oracle`, $2.47**, 1,026,233
tokens, pricing snapshot 2026-06-07. Row zero read free from the frozen run; `parse_ok` 1.000
in both arms. The runner repoints `SYSTEM_PROMPTS["verification"]` **in-process only**, so the
`system_prompt` column records the probe file and a post-run assertion fails the run if any
row carries the frozen prompt name -- no committed harness file modified.

Recovery of `undetermined` on the 10 undetermined-gold items (90 rows = 30 item x format
cells x 3 trials per arm; paired on the cell, bootstrapped over cells, B = 20,000):

| arm | frozen | B2 | paired delta [95% CI] | cells up/down/same |
|---|---|---|---|---|
| gpt-4o | 0/90 | **0/90** | **+0.000 [+0.000, +0.000]** | 0 / 0 / 30 |
| gpt-4o-mini | 0/90 | 1/90 | +0.011 [+0.000, +0.033] | 1 / 0 / 29 |
| claude-sonnet-4-5 | 20/90 | **30/90** | **+0.111 [+0.022, +0.222]** | 5 / 0 / 25 |

**gpt-4o changed not one row of 90.** Sonnet is the within-probe positive control and rules
out an inert prompt: same items, formats, trials and call path, +0.111 with CI excluding
zero, at zero cost (false abstention on determinate controls stays 0.000, determinate
accuracy stays 1.000). The variant works; it does not work on the GPT arms. That is an
arm-specific null, not a null probe.

**The variant actively harms gpt-4o-mini**: determinate accuracy 0.889 -> 0.800, false
`undetermined` on determinate controls 0.000 -> 0.033 (3/90), to buy one correct abstention.
Report the trade, not the single recovered row.

**All four hypotheses now resolved: H1, H2, H3, H4 all rejected. Resolution criterion 3 is
met.** The surviving account is the gating rule -- the GPT arms abstain on *non-retrieval*
and never on *non-entailment*. Model behaviour, not harness defect. **Per the pre-commitment:
no re-run; the frozen run stands as run, headline numbers unchanged, and every §6
interpretability restriction stands.** Non-recovery is the stronger branch: the closed-world
mapping is robust to being instructed against it.

**Probes A, B1 and B4 not run** -- a deliberate stop. B2 was the strongest of the three and
produced a flat zero across 30 cells; a label-order permutation or abstention-permission
sentence is a weaker intervention than the one that just failed. Probe A (logprobs) retains
residual value only for the knife-edge-versus-hard-collapse distinction, which the
determination does not need.

**Operational.** Account funded mid-investigation; two attempts failed on
`429 insufficient_quota` (0 rows, nothing billed), the third on `429 rate_limit_exceeded` --
the tier-1 **30,000 TPM** cap on the `gpt-4o` limit group -- after 42 calls, since a ~2.4k-token
verification call allows ~12 gpt-4o calls/min. A retry-on-429 with provider-hinted backoff and
jitter is installed **in the probe script only** (`install_rate_limit_retry`); `llm_call.py`
still re-raises, which is correct for a paid benchmark run where a silent retry could mask a
real fault. The wrapper re-raises immediately on `insufficient_quota` so an out-of-credit state
can never be absorbed as throttling; retries re-send byte-identical requests with the same seed,
so nothing measured is affected. **Note: `src/.env` holds two `OPENAI_API_KEY` lines and
python-dotenv keeps the first** -- harmless here, but a live footgun worth deduplicating.

## 2026-08-20 (b) - Merged combined directory for the arm-split run

`scripts/merge_postretrieval_trials.py` recombines arm-split trials into one
directory: `postretrieval-combined-15-18` (10,080 raw rows, 3,360 scored rows,
4 arms, $50.71). The previous combine (`postretrieval-combined-8-9`, 2026-07-30) was
done ad hoc; this is the reusable version.

**Derived tables are recomputed from the merged raw rows, never concatenated.**
Scored, variance, diagnostics and cost are pure functions of the raw rows, so
recomputing them makes the combined directory equivalent to what an unsplit run
would have written. Concatenating per-arm summaries would instead average
already-averaged values and silently change the numbers. Verified: each arm's scored
rows in the merged set are identical to that arm's own standalone scored file, and
the merged cost equals the sum of the four arms exactly.

**The merge is guarded, not assumed.** Every protocol field in the source manifests
must agree and no cell may appear in two sources; either condition aborts the merge.
This caught a real misclassification on first run -- `seed_determinism` is keyed per
MODEL, so it legitimately differs per arm and is unioned rather than compared.

`postretrieval-combined-*/postretrieval_raw.csv` is gitignored: it is byte-for-byte
reproducible from the committed per-arm directories (md5-verified), so committing it
would duplicate ~80MB of already-archived raw data. The merged scored/variance/
diagnostics/manifest tables, which is what analysis reads, are committed.

**Flagged, not fixed: `seed_determinism` in every manifest is wrong for two arms.**
`run_experiment.py` derives it as `"best-effort" if "llama" in model else "pinned"`,
so the Anthropic arm is labelled `pinned` even though the Anthropic API has **no seed
parameter at all**, and the GPT-4o arms are labelled `pinned` even though
CHANGELOG 2026-08-13 (c) explicitly retracted that claim (the baseline reproduced raw
output in 2/12 cells). Adding Sonnet to `MODELS` widened an existing defect rather
than creating one. The correct replacement label is a methods-chapter decision, so it
is recorded here rather than changed silently.

## 2026-08-20 - Ollama generation cap, post-retrieval checkpointing, Sonnet arm wired in

**Three harness changes, all forced by one failed overnight run.** The 4-arm 60-task
post-retrieval run died after ~540 completed calls with an Ollama `ReadTimeout`, and
lost every one of them.

**1. `OLLAMA_NUM_PREDICT = 1024`.** Root cause of the failure, from Ollama's own log:
one Llama call degenerated into a runaway JSON loop and decoded 12,753 tokens at a
healthy ~46 tok/s -- the GPU was never stuck -- and was still generating when the 300s
client timeout fired. `_call_ollama` set no `num_predict`, so Ollama's default is to
decode until the context window fills. With a ~2k prompt in a 16,384 window that needs
~14,400 tokens (~313s) to self-terminate, which is LONGER than the client timeout: any
degenerate Llama response was structurally guaranteed to kill the run rather than
return. The cap matches the Anthropic arm's existing `max_tokens=1024`, so the two
capped arms are comparable. It cannot truncate a legitimate answer -- across the 2,788
post-retrieval calls recorded before this change the longest completion is 477 tokens
and none exceeds 1024. A degenerate response is now a truncated response that fails
parsing and is RECORDED as a parse error, which is the correct scientific outcome, and
the worst-case call is bounded to ~22s. In the re-run this fired exactly twice
(T18/ofn/oracle, T22/elot-org-ancestors/retrieved, both `finish_reason=length`,
2 parse failures in 2,520 Llama calls); without it the run would have died twice more.

**2. Post-retrieval checkpointing + `--resume`.** Rows were accumulated in memory and
the trial directory was not created until `run_postretrieval` RETURNED, so any
exception in the loop discarded everything completed. Each row is now appended and
flushed to `postretrieval_checkpoint.jsonl` the moment its call returns, the trial
directory is created before the loop, and `--resume <dir>` replays completed calls
instead of re-issuing them. Resume reproduces rather than approximates the interrupted
run: `run_one` is a pure function of (task, format, condition, model, seed, pad_*),
every component of which is in the checkpoint key, and `_summarise_raw_rows` groups
and sorts its input, so the output does not depend on how the work was split across
attempts. Asserted by enumeration in `tests/test_postretrieval_checkpoint.py`: a
simulated crash then resume yields raw and scored output identical to an uninterrupted
run, with no duplicated call (double spend) and no gap (missing data). The checkpoint
is gitignored -- its surviving rows are copied verbatim into `postretrieval_raw.csv`.

**3. `claude-sonnet-4-5-20250929` added to `config.MODELS`.** D2 (2026-08-13) adopted it
as a study arm and the provider branch, tool schemas, cache breakpoint and pricing were
all in place, but the arm was never added to `MODELS`, so `--models` defaulted to three
arms and silently dropped it. Placed after the two GPT snapshots to keep `MODELS[1]`
(gpt-4o-mini) as the smoke default. The surrounding comment previously claimed "fixed
seeds" and referenced a non-existent `llm_call._provider_for`; determinism is not
uniform across arms (CHANGELOG 2026-08-13 (c) retracts it for the GPT-4o baseline, and
the Anthropic API has no seed parameter at all), so it now records seeds as best-effort
per provider and points at `detect_provider`.

**Run split by arm.** The 4 arms were run as 4 separate invocations into
`postretrieval-trial-15` (gpt-4o), `-16` (gpt-4o-mini), `-17` (sonnet) and `-18`
(llama), so a failure in the slow local arm can no longer discard paid API results.
This is order-only in the same sense as B2: identical call tuples, identical grades,
four manifests instead of one. 2,520 rows per arm, 2,520 unique cells, 10,080 total.
Cost $50.71 (gpt-4o $16.65, sonnet $33.08, gpt-4o-mini $0.98, llama $0). RQ1 was
re-run as `retrieval-trial-14` because the previous retrieval trial covered only the
53 pre-Batch-05 tasks.

## 2026-08-19 - Selected Batch-05 contradicted items; benchmark complete at 60

Added T59-T65 from the human-selected Batch-05 pool, completing the fixed design:
60 tasks, 30 verification / 30 slot-filling, 10 supported / 10 contradicted /
10 undetermined. Five composed domain/range + disjointness items (T59-T63) and two
functional-property items (T64/T65) join the three bare-disjointness items T06-T08.

`direct_domain_range` was allocated 3 items and yielded **zero** candidates. This is
a property of LIS-14, not of the search: with all `owl:disjointWith` triples and
`owl:AllDisjointClasses` groups stripped, all 108 zero-hop object-property assertions
reason satisfiable, and the ontology contains no other contradiction-inducing
construct - no `owl:complementOf`, `owl:disjointUnionOf`, `owl:propertyDisjointWith`,
max-cardinality, asymmetric/irreflexive property, faceted datatype range, or named
individual. `rdfs:domain`/`rdfs:range` only add types; on their own they never clash.
So every domain/range contradiction in this ontology is composed, and the §3.2/§3.3
split was never a real split here. The 3 slots were reallocated to
`composed_domain_range_disjointness`, which is why that stratum carries 5.

`functional_property` stays at 2. LIS-14 declares exactly two functional properties
(`lis:datumUOM`, `lis:datumValue`), and every `lis:ScalarQuantityDatum` phrasing is a
`states_axiom` rejection - its usageNote states the functionality consequence verbatim -
so both items must take `lis:QualityDatum` as subject. B05-F05 was rejected as a
qualified-cardinality rephrasing of T64 on the same licensing axiom, not an independent
item. Treat T64/T65 as a matched pair.

Partial per-link prose leakage is accepted in the composed stratum, as for T11/T12/T13.
IDO annotates properties with a fixed template that restates domain and range in prose,
so link 1 is stated in prose for 22 of the 26 composed candidates; link 2, the
disjointness axiom, is never in prose except for the rejected B05-R15. Prose alone
therefore settles no selected item. Three of the five composed items (T59, T60, T61)
are drawn from the four candidates with no prose leak on either link, so a stricter
per-link reading would cost only T62 and T63.

`licensing_axiom_status` is `entailed_chain` on the five composed items because the
schema derives status structurally from chain length, but **both links of each chain are
directly asserted in the canonical graph; neither is entailed**. `benchmark/schema.md`
lists `contradicted` only under `asserted` and describes `entailed_chain` as a
ROBOT/HermiT explanation chain, so this is a combination the schema documentation did
not anticipate. Accepted with the widened meaning recorded here rather than changing the
schema or truncating the recorded route to a single link. Report it in the methods
chapter as a two-link asserted route.

All seven have uniform all-true recoverability profiles. The functional-property items
are uniform by construction (`rdf:type owl:FunctionalProperty` is materialised in every
serialisation), as bare disjointness was. The contradicted block therefore carries no
format-effect signal; it contributes label balance and mechanism variety, and the
format contrast rests on the supported and slot-filling halves. Every selected item is
**non-vacuous**: the conjunction `X and (P some Y)` is entailed empty on the unmodified
canonical graph while `X` alone is not, so the open-world vacuity caveat carried by
T06-T08 does not apply, making these strictly stronger contradicted items.

T60, T62 and T64 are paraphrase-worded to break what would otherwise be a complete
confound: without them all ten contradicted items would be `query_source: label` and
`reasoning_type: structural`, so any contradicted-versus-supported effect would be
indistinguishable from a query-wording effect. The paraphrase subset is small and
non-randomised, so it weakens rather than removes the confound.

Two deliberate axiom reuses: T61 rides the T08 InformationObject/PhysicalObject axiom
and T62 rides the T06 Site/SpatialLocation axiom. Both are matched pairs - the same
disjointness read bare in the committed item and through a domain/range axiom in the
new one - not independent evidence. T62 is the batch's only genuine prose-versus-axiom
disagreement and the contradicted-side analogue of pilot T03.

Two gate gaps found and reported, not fixed (authoring brief §7 forbids touching
`recoverability.py` and the gate scripts):

1. `_turtle_chunk_has_axiom` misses every non-final member of an `owl:unionOf` list. Its
   `nested` pattern ends with a lookahead that only matches the union member immediately
   before the closing paren, so across all five union-valued domain/range axioms in IDO
   the last member reads `true` in turtle and every earlier member reads `false`, while
   all six other formats read `true`. **Pilot T03 is live-exposed**: its licensing axiom
   is `[lis:concretizes, rdfs:domain, lis:PhysicalObject]` and its stored all-true profile
   survives only because `lis:PhysicalObject` happens to be the last union member. Had
   `lis:Activity` been recorded - equally correct - T03 would carry a spurious
   `turtle=false`. Candidate B05-D08 was dropped on this basis: its non-uniform profile
   was a matcher artefact, not a serialisation difference.
2. A connected `licensing_axiom` chain cannot express a union-domain route. B05-D08 needs
   `lis:Organization` shown disjoint from both disjuncts of
   `(lis:Location or lis:PhysicalObject)`, which branches rather than chains; the recorded
   chain would capture only one disjunct and understate the route. Second reason to drop
   it, and a general limitation for any future union-domain item.

Verification: `robot reason` on all 32 candidates (unsatisfiable on the canonical graph,
satisfiable with disjointness stripped, 0 unsatisfiable at baseline, ontology consistent
throughout); `check_authoring_candidate` gate pass on all 32; all 16 previously stored
recoverability profiles recomputed and matched. After the commit,
`verify_authoring_constraints --tasks experiment/benchmark/tasks_60.yaml` passes at 60
tasks with live profile recomputation, and gold chunks for all 60 resolve in all seven
formats. Zero API calls. Note that ROBOT exits with return code 1 when it finds an
unsatisfiable class, which is the success case here.

## 2026-08-15 - Selected Batch-04 slot-filling items

Added T29-T43 from the human-selected Batch-04 pool: ten direct/no-intermediate
items and five intermediate-node patterns. The 10/5 split was not forced toward
evenness because further quality/quantity candidates repeat existing gold answers.
Record T35/T39 as a one-hop versus two-hop temporal-datum contrast; T40/T41 as a
duplicate-shape quantity pair; and T42/T43 as measured-property versus assessed-
condition quality routes. T35 is the all-format temporal-chain control for the
T40-T43 subclass-omission effect. All fifteen have `gold < k`, so gold-set size
cannot vary as a slot-filling retrieval-difficulty covariate.
T40/T41 share a gold answer, as do T42/T43; the 10/5 intermediate split gives a
0.67 always-false baseline (the pool has 18 true of 45); and T35 is the sole
recoverability control, so a second temporal-chain item in the next fifteen
would strengthen the contrast.

The residual pool contains no second or third temporal intermediate-chain row:
`B04-D17` is its only `Activity -> TemporalRegion -> TemporalDatum` pattern.
Any second control must therefore be a separately screened composition candidate
with the same bearer-property pair and a distinct scenario. IDO explicitly
licenses multiple temporal datums for one temporal region, including observed
and estimated duration values, so plural datum wording does not create an
additional graded field or require a second datum type in the gold set.

The proposed second selection would yield two temporal controls (`T35` and a
new counterpart) against eight subclass-dependent quality/quantity treatments
(`T40`-`T43` and four proposed counterparts). No third temporal control exists
in the measured pool; retain the resulting 2:8 ratio as a limitation rather
than add redundant quantity or quality variants. Its proposed
`ActivityProfile -> profileOfQuality -> Quality -> qualityQuantifiedAs ->
QualityDatum` rows are an adjacent matched route and should be analysed as such,
not as independent evidence.

`hasContentPart` remains an asserted `InformationObject -> InformationObject`
domain/range pair. It is classified as `part_whole`, not `information`, because
the candidate stratifier assigns part relations before information surfaces; the
zero information stratum is unchanged.

Completed the slot-filling half by adding T44-T58: ten direct/no-intermediate
items and five intermediate-node patterns, for 30 slot-filling tasks overall
(20 false, 10 true). T44 (`B04-T01`) is the second computed temporal-chain
control, paired with T35; these two controls stand against the eight
subclass-dependent treatments T40-T43/T55-T58, so either control being noisy
materially weakens attribution at `elot-org-ancestors`. T47 retains B04-D08,
not the inverse-side B04-D25 swap: it supplies a distinct pair and its explicit
role-free wording keeps generic participation gradeable. T52/T53 are adjacent
pump-vibration links, not independent evidence. T40/T41/T55/T56 share one
quantity-chain answer and T42/T43/T57/T58 share one quality-chain answer;
all 30 retrieval gold sets are `gold < k`, so gold size cannot vary and
`oracle_padded` applies throughout.

## 2026-08-15 - Batch-04 temporal intermediate-node control

Re-profiled Batch-04's quantity/datum intermediate-node chain after correcting
its invalid `qualityQuantifiedAs` domain link. The valid chain is recoverable in
six formats and false only in `elot-org-ancestors`, where the direct
`ScalarQuantityDatum rdfs:subClassOf QualityDatum` assertion is not serialized.
The same explicit-subclass omission already produces the measured split in
verification subsumption items, so the effect is a cross-task format mechanism,
not an item-specific recoverability caveat.

Added `B04-D17` to the candidate pool as a matched slot-filling control: an
Activity -> TemporalRegion -> TemporalDatum intermediate-node pattern. It has
the same two-hop modelling demand but no subclass link, and is recoverable in
all seven formats. Its candidate metadata records that control role explicitly.

## 2026-08-14 (d) - Selected undetermined items

Added T19-T28 from the Batch-03b human selection, with hypothetical licensing
axioms and null recoverability profiles. Reasoning type is recorded per item and thin cells warn rather than fail.

## 2026-08-14 (c) - Chain-aware Batch-02 supported subsumption set

Added T09-T18 to `benchmark/tasks_60.yaml` from the measured Batch-02 pool.
T09 and T10 are the only prose-neutral, direct formal-axiom-legibility controls:
Feature -> PhysicalObject and Interval -> IntervalRegion. The eight entailed
items carry ordered `licensing_axiom` chains and complete chain gold sets; their
stored profiles are the conjunction of direct-link recovery and split only at
`elot-org-ancestors`.

The clean-to-leakage gradient is entity-concentrated: T09/T11 share Feature and
T10/T12/T13 share Interval. This prevents interpreting between-item differences
as leakage effects independently of entity familiarity. Those same overlaps are
explicit within-subject matched sets: T09/T11 varies Feature hierarchy depth and
leakage; T10/T12/T13 varies Interval depth and leakage. Treat them as such in
analysis.

Formal-axiom legibility and prose recovery are not separable for entailed
subsumption in this IDO corpus: every chain is fully or partially prose-leaked.
The selected eight chains are composition-depth items, not independent
formal-legibility items. This is a measured corpus limitation, not a validator
constraint; selection retains the distinction in per-item notes.

## 2026-08-14 (b) - Correction: T04 ELOT failure is encoding-invariant

Supersedes the 2026-08-13 "ancestor-depth misattribution" reading. Reading the
raw rationales, GPT-4o-mini's T04 `contradicted` errors are the same across both
`elot-org` and `elot-org-ancestors` (all 3 trials each): definitional-gloss
contradiction, or "Function ⊑ Potential, distinct from Capability" sibling-
distinctness. Both patterns occur under the explicit arm too, so this is not a
heading-depth artefact but an encoding-invariant subsumption error; whole-context
turned the oracle abstention into a confident false negative. Not evidence for the
explicit-vs-structural encoding discussion.

## 2026-08-14 - Authoring-constraint recalibration

Recomputed the pilot recoverability profiles after symmetric
`owl:disjointWith` matching; T01, T03, and T04 matched their stored values,
including T04's `elot-org-ancestors=false`. Measured deterministic local pools
across the remaining mechanisms. Differential direct-axiom recoverability is a
mechanism-level property in this ontology: all 20 sampled asserted subsumption
pairs split only at `elot-org-ancestors`, while inherited disjointness, direct
domain/range, composed domain/range plus disjointness, and the two functional
properties were uniform by construction.

Dropped the global uniform-profile cap. `recoverability_profile` remains a
required, live-verified covariate; `mechanism` records the design distinction.
Dropped the contradicted-prose distribution quota as well: the measured pool
does not establish multiple `toward` examples, so direction is descriptive.
Added `states_axiom` to expose prose that directly states a licensing axiom.

The first subsumption sampler used transitive closure, then was corrected to
asserted `rdfs:subClassOf` pairs before final measurement. This was material:
closure would have admitted multi-hop relations such as `Function` to `Potential`,
which are not T04's direct `Function SubClassOf Capability` mechanism.

Added T06-T08 to `benchmark/tasks_60.yaml` from measured Batch-01
bare-disjointness candidates. They are outside the five-task pilot, each with a
fully recoverable profile and neutral prose.

## 2026-08-13 (b) - D1 and D2 resolved

**D2 - model arms.** Adopt `claude-sonnet-4-5-20250929` as the third arm alongside
`gpt-4o-2024-11-20` and `gpt-4o-mini-2024-07-18`. Do not adopt `gpt-5.5-2026-04-23`
or the `gpt-5.6-*` family. Sonnet is pinned, honours `temperature=0`, predates the
April 2026 FDIS release, and uses tool-use structured output, preserving
byte-identical prompts across arms; no separate contamination-floor rerun is needed.

**D1 - verification labels.** Adopt C immediately: report coverage (the fraction
answered determinately) alongside accuracy on answered items; abstention on a
determined item is a non-answer, not an error. Apply this retroactively to the pilot
with `rescore.py`. Adopt A2 for the 30-task set: undetermined items must reflect
ontological silence, not context insufficiency. Gold is defined against ontology-level
truth, while retrieval failures remain wrong under the existing prompt and are now
also visible through coverage. The prompt is unchanged for pilot comparability.

Non-entailment is checked two-sided on the canonical graph (`KB` entails neither
`phi` nor `not phi`) with ROBOT/HermiT, wired into `verify_ontology_chunkers.py` as a
standing gate. This prevents rendering differences, such as ELOT's explicit versus
ancestor-only subclass encoding, from changing a gold label.

The 15 verification items are balanced 5/5/5 across labels (majority baseline
0.333) and stratified by mechanism within each class. Contradicted items include
two bare disjointness cases, two composed domain/range violations, and one
functional-property violation; undetermined items cover unstated domain/range,
cross-branch subsumption, an unasserted inverse, and unstated cardinality. T03 is
unchanged and remains entailed under the new criterion in all seven formats.

Report per-class precision/recall/F1 with bootstrap CIs resampled over items, not
cells. If intervals are uninformative at five items per class, use the three-way
confusion matrix and overall accuracy instead. Open checks: screen undetermined
candidates against annotation prose, and confirm that the functional-property item
fits the existing T-Box statement schema.

## 2026-08-13 - Whole-context reference condition added (trial-12); citation-surface confound; Spec 06b interpretation superseded

Added a third, opt-in post-retrieval condition and recorded how its diagnostics
change the reading of existing results. Relevant specs: 05/05b (feasibility and
validation), 06 (design and execution), and 06b/06c (diagnostics).

### Whole-context condition

`whole_context` is in `ALL_CONDITIONS`, but not the default `CONDITIONS`
(`[oracle, retrieved]`), following the `oracle_padded` precedent. It ran as
`postretrieval-trial-12`: T02 and T04 x 7 core formats x 3 models x N=3 = 126
calls, at approximately USD 5. `schema-concept` is excluded because it has no
source file of its own.

The condition injects each format's **source file**, not reassembled chunks.
For this condition, the Llama arm has a separate pinned
`OLLAMA_NUM_CTX_WHOLE_CONTEXT`; the `OLLAMA_NUM_CTX=16384` setting for all other
conditions is unchanged. `OLLAMA_FLASH_ATTENTION=1` and
`OLLAMA_KV_CACHE_TYPE=q8_0` keep the model fully GPU-resident. q8_0 and f16 were
byte-identical on one 45,345-token cell, so that is the relevant evidence, not
the non-discriminative graded result (all six fields scored 0).

Every native Ollama call now asserts `prompt_eval_count` against the expected
token count. Without this guard, Ollama silently truncates prompts larger than
`num_ctx`.

### T02: citation-surface confound

T02's five graded fields decompose into three answer fields and two citation
fields:

| condition | combined | answer fields | citation fields |
|---|---:|---:|---:|
| oracle | 0.683 | 0.704 | 0.651 |
| retrieved | 0.524 | 0.646 | 0.341 |
| whole-context | 0.486 | 0.646 | 0.246 |

`(3 * answer + 2 * citation) / 5` reproduces the headline. The pooled answer
spread across all three conditions is 0.058, below one answer-field resolution
of 0.333. Every pooled T02 difference, including the whole-context drop and the
oracle-to-retrieved gap, is in the citation fields.

The source-file construction has no `# Chunk: <entity_id>` labels, so the model
has no expected citation form. Stored whole-context citations included full
IRIs, source headings such as `core-class-hierarchy`, JSON-LD blank nodes,
literal `# Chunk:` strings, and nulls. This is the schema-concept `CHUNK ID:`
confound from 2026-07-30 in another form. Source-file conditions must therefore
report answer and citation fields separately alongside strict combined partial
credit.

The retrieval-bottleneck claim needs one qualification: T02's
oracle-to-retrieved answer-field gap is below one-field resolution, so T02 alone
is not evidence of a comprehension gap without this decomposition. This does
not retract the five-task bottleneck finding or the T05 coverage mediation
(`grade_property_correct` 0.89 when `covered_property` is true, 0.00 when false).


### Other results


The defensible claim is no systematic direction detectable, with pooled
marginals only.

OFN is the one exception worth retaining: all three models improve on answer
fields from retrieved to whole-context (+0.222 / +0.222 / +0.667). It also had
the lowest retrieved answer-field mean (0.296) despite the highest pilot recall@5
(0.93), so this is not a simple retrieval failure. The mechanism needs separate
investigation.

- **T04, ELOT-ancestor:** the predicted GPT-4o-mini rescue did not occur. Under
  oracle it abstained; under whole-context it committed to `contradicted`,
  reasoning that `lis:Function` is a subclass of `lis:Potential`, the outermost
  ancestor in a four-deep path rather than the immediate parent. Heading depth
  preserves ancestry but not which level carries the licensing edge. This
  survives whole-context and is not a chunking artefact; scope is one model x
  format x condition cell, three trials, found nowhere else in the stored
  rationales.
- **Abstention:** T04 `undetermined` counts are 3/63 (oracle), 0/63 (retrieved),
  and 0/63 (whole-context). All oracle abstentions are the mini/ELOT-ancestor
  cell. 
- **Prefix reuse:** not confirmed. Three consecutive Llama calls sharing a
  corpus re-evaluated the full prompt. The Spec 05 loop reorder is therefore
  justified by OpenAI caching only.

### Cost ledger corrections

`postretrieval.py` now records `cached_prompt_tokens`; `pricing.py` adds
`compute_cost_cache_aware` and `summarise_cost_cache_aware`, plus a
`CACHE_MODEL_PRICES` snapshot dated 2026-08-13. The pinned 2026-06-07
`MODEL_PRICES` is unchanged.

Existing manifest costs are overstated because `summarise_cost` bills all input
at the uncached rate. Aggregate overstatement is approximately 24%, but the
cache hits were incidental and `cached_tokens` was discarded at write time, so
the error is heterogeneous and unrecoverable per manifest. Manifests are not
rewritten: they correctly record the pinned calculation, not actual spend. The
methods chapter must use provider export for incurred spend: USD 7.93 across
2,584 OpenAI completion requests as at 2026-08-13. 

### Discussion implications

1. The citation-grading result is a methodological contribution: strict chunk-ID
  grading measures citability alongside answer selection, and the two can move
  independently. Report the answer/citation decomposition for any such
  evaluation.
2. Whole-context does not dominate retrieval. T02 retrieved and whole-context
  have identical pooled answer fields (0.646), while T04 has no stable ranking
  at one-label resolution. Scope: these two tasks.
3. OFN merits one precise paragraph as the only sign-consistent format effect in
  the run.
4. The ancestor-depth misattribution is an illustrative example for the
  explicit-versus-structural encoding discussion, not independent evidence
  (`n=1` cell).

## 2026-08-04 (f) - WI-10 cost projection for `gpt-5.5-2026-04-23`

No API calls. Projection from **observed** token counts (36 real gpt-5.5 calls in
`determinism-probe-1`, plus the WI-4 acceptance call) against published rates.

**Rates read 2026-08-04** from `https://developers.openai.com/api/docs/pricing`
(the old `platform.openai.com/docs/pricing` now 301s there):

| model | input /1M | output /1M |
|---|---|---|
| **gpt-5.5** (<272K context) | **$5.00** | **$30.00** |
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |

**Not written into `pricing.py`** — the arm is not adopted, and pinning a rate for
a model the study may not use would put an unverified constant in the methods
chapter. Two caveats on the rate itself: the page lists **no dated snapshot**, so
the `gpt-5.5` rate is applied to `gpt-5.5-2026-04-23`; and the quoted tier is
`<272K` context, which all our prompts (2.4k-8.3k tokens) sit far inside.

**Reasoning tokens are already inside `completion_tokens`** — the WI-4 call showed
913 reasoning within 1015 completion. Billing on `completion_tokens` is therefore
correct and complete; **adding `reasoning_tokens` on top would double-count.**

### Measured basis

One pass = 32 calls (8 formats x {T02,T05} x {oracle,retrieved}). Prompt tokens
are the real per-cell counts from the archived 8-format runs (validated: for
byte-identical prompts gpt-5.5 = gpt-4o - 1 token/call, exactly, in all 12
overlapping cells). Completion tokens are the observed gpt-5.5 per-(task,
condition) means.

| | prompt/pass | completion/pass | mean completion/call |
|---|---|---|---|
| gpt-5.5 | 118,393 | **24,480** | **765** |
| gpt-4o | 118,393 | 3,287 | 103 |

**`gpt-5.5` emits 7.45x the output tokens of gpt-4o on identical prompts.** That
is the reasoning-token inflation, measured rather than assumed.

### Projections

| scenario | calls | **gpt-5.5** | gpt-4o | ratio |
|---|---|---|---|---|
| **(b) T02+T05 column, N=3** | 96 | **$3.98** | $0.99 | 4.0x |
| **(a) T02+T05 column, N=5** | 160 | **$6.63** | $1.64 | 4.0x |
| **(c) 30-task run, N=3** | 1,440 | **$59.69** | $14.80 | 4.0x |
| **(c) 30-task run, N=5** | 2,400 | **$99.48** | $24.66 | 4.0x |

Sensitivity: `T05/retrieved` completion ranged 270-3,189 tokens (mean 1,460), so
the reasoning budget is highly variable. At the observed per-cell **maximum**
(1.73x the mean): T02+T05 N=5 = **$9.33**; 30-task N=5 = **$139.96**.

### What this means for the decisions

1. **The WI-7 column is cheap and is NOT a blocker.** At N=5 — the rate the spec
   mandates for a `determinism_mode != seeded` arm — it is **$6.63**, comfortably
   inside the original ~$25 stop condition even at the $9.33 worst case. On cost
   grounds alone there is no reason to refuse this arm for T02+T05.
2. **The 30-task run is a different decision entirely.** At N=3 it is **$59.69**
   and at N=5 **$99.48** (worst case $140) — **2.4x to 5.6x over the ~$25 ceiling**
   that governed this work package. That ceiling was written for a 414-call
   package; it does not transfer to a 2,400-call one, and the 30-task budget needs
   setting explicitly rather than inherited.
3. **The cost structure inverts between the arms.** On gpt-4o, output is ~10% of
   spend; on gpt-5.5 it is **~55%**, because reasoning tokens dominate. Anything
   that lengthens generation (more tasks with long gold contexts, higher
   `reasoning_effort`) scales 5.5's cost far faster than gpt-4o's. The steady 4.0x
   headline ratio conceals a 22x ratio on the output side.

### Scope limit

The 30-task figure extrapolates from T02 and T05, **both slot-filling**. If the
30-task set is weighted toward verification (shorter answers) this over-estimates;
if it contains tasks with larger gold sets than T05's, the prompt side grows. It
is an order-of-magnitude upper bound for budgeting, not a quote.

## 2026-08-04 (e) - Graded-field stability measured on ALL arms; baseline determinism claim retracted

144 calls, 0 errors, $0.45 on the priced arms. Raw + summary:
`experiment/results/determinism-probe-1/`.

**Byte-stability was the wrong criterion.** The study never grades the `reasoning`
string, so the question that matters is whether the *scored* fields reproduce.
Earlier entries judged arms inconsistently on this (5.5 on byte-stability, Sonnet
on graded stability). This measures every arm on the same criterion.

**Design.** Replicate the exact call the study makes, 3x per cell, compare raw
text and the full grade dict. 4 models x 3 formats (turtle, omn, jsonld) x
{oracle, retrieved} x {T02, T05} x 3 repeats. Prompts byte-identical across arms;
each arm called as the study would call it (gpt-4o* temperature=0 + seed; 5.5 seed
only, temperature 0 being 400-rejected; Sonnet temperature=0 + tool-use). Both
tasks are slot-filling, so every comparison spans **6 graded fields, not 1 label**.

### Result

| model | raw-stable | graded-stable |
|---|---|---|
| gpt-4o-mini-2024-07-18 | 4/12 | **11/12** |
| claude-sonnet-4-5-20250929 | 2/12 | **11/12** |
| gpt-4o-2024-11-20 (baseline) | **2/12** | **9/12** |
| gpt-5.5-2026-04-23 | 0/12 | 8/12 |
| **all cells** | **8/48 (17%)** | **39/48 (81%)** |

**1. RETRACTION — the baseline's determinism was assumed, never verified, and is
false.** `gpt-4o-2024-11-20` at temperature=0 with a pinned seed reproduced its
raw output in only **2 of 12** cells. OpenAI has never guaranteed seeded
reproducibility — `seed` is best-effort and `system_fingerprint` exists precisely
because it is not a guarantee. Any statement in the methods chapter that the
GPT-4o arms are deterministic, or that `seed` pins the output, must be removed.
The defensible claim is **graded-field stability in 9/12 cells**, not determinism.
This supersedes the `seed_determinism: "pinned"` label written into every
post-retrieval manifest, which overstates what the parameter delivers.

**2. Sonnet is ABOVE the baseline, not a tier below.** 11/12 vs 9/12 graded-stable.
The earlier framing — that Sonnet's non-byte-stability made it weaker on
reproducibility — was an artefact of applying a stricter criterion to it than to
the incumbent. On the criterion the study actually uses, the cross-vendor arm is
the *more* stable of the two.

**3. The pinned-but-stochastic objection to 5.5 largely dissolves.** 8/12 vs the
baseline's 9/12 — within one cell. It is the least stable arm and has the widest
single divergence (0.400 on T02/jsonld/retrieved, where `class_correct` flipped),
which is consistent with a reasoning model having more room to diverge. But it is
not disqualifying relative to an incumbent that scores 9/12.

**4. Instability is localised to CELLS, not models.** `T05/omn/oracle` and
`T05/jsonld/oracle` are each unstable for **3 of 4 models**. That is a property of
those items, not model flakiness — those cells sit on a genuine decision boundary.

**5. Instability is localised to ONE FIELD.** `support_intermediate_correct` — the
intermediate-node *citation* on T05 — accounts for **6 of the 9** unstable cells,
across all four models. `exact_match` then flips as a downstream conjunction. Only
**3 of 48 cells** show a *decision*-field flip (`intermediate_correct` x2,
`class_correct` x1). So the noise is overwhelmingly in one citation field on one
task, and the answer slots are considerably more stable than the headline 81%
suggests.

**6. Magnitude is bounded and small.** Eight of nine divergences are exactly
0.167 = one field of six flipping; the outlier is 0.400. **Actionable threshold:
no format difference of <= 0.167 within a single cell can be claimed — it is
inside observed within-cell noise.** This applies to the existing GPT-4o results,
not only to future arms.

### Scope limits (stated so they are not over-read)

- **This is a LOWER bound on the study's real trial-to-trial variance.** The
  OpenAI arms were repeated with the *same* seed to isolate serving
  nondeterminism; the study's actual N=3 uses three *different* seeds
  (20260529/30/31), which can only produce at least as much variation.
- **Slot-filling only.** T02/T05 were chosen for sensitivity (6 graded fields vs
  a single verification label). The verification arm (T01/T03/T04) is **not**
  covered and should not be assumed equally stable.
- n=3 repeats, 3 of 8 formats, 2 of 5 tasks. Sufficient to rank arms and to
  retract the determinism claim; not sufficient for a per-cell noise model.

### Consequence for `determinism_mode`

The seeded | temperature_only | none taxonomy assumed byte-reproducibility was
achievable by *some* arm. No arm achieves it (best: 4/12). Recommend the manifest
record **`graded_stability_rate`** — measured, per arm — instead of, or alongside,
a categorical mode. Not applied; this is a methods decision that travels with D2.

## 2026-08-04 (d) - WI-9 `claude-sonnet-4-5-20250929` probe

Same protocol as WI-4, adjusted for the Anthropic API. No adapter code, no
pricing constants. **`determinism_mode = temperature_only`** — the first probed
arm where the *graded* output is reproducible.

> **[SUPERSEDED 2026-08-04 — see the 2026-08-04 (e) entry.]** Two corrections to
> this entry. (i) The "not measured" cell for 5.5's graded stability has been
> filled: **8/12**, within one cell of the GPT-4o baseline's 9/12. (ii) This entry
> implicitly treats the GPT-4o arms as the reproducible standard Sonnet was being
> compared against. That is wrong — GPT-4o is byte-stable in only 2/12 cells and
> graded-stable in 9/12, i.e. **less** graded-stable than Sonnet's 11/12. The
> per-arm verdicts below stand; the implied ranking does not.

| field | claude-sonnet-4-5-20250929 | gpt-5.5-2026-04-23 | gpt-5.6-terra / luna |
|---|---|---|---|
| dated snapshot | **YES** | YES | no (alias only) |
| `temperature=0` | **accepted** | rejected (400) | rejected (400) |
| `seed` | **absent from API** (not a failure) | accepted, **ignored** | accepted, **ignored** |
| fingerprint analogue | **none** | None | None |
| raw text byte-stable (toy prompt) | **yes, 3/3** | n/a (temp forced to 1) | no |
| raw text byte-stable (real T02/T05) | **no** (2/3, 3/3 distinct) | no | no |
| **graded fields stable (real T02/T05)** | **YES — 3/3 identical, both tasks** | ~~not measured~~ **8/12 cells** | no |
| existing prompt + strict schema | **FAILS — markdown fence** | OK unmodified | not run |
| tool-use path | **OK, parses** | n/a | n/a |
| separate thinking tokens | **yes**, `output_tokens_details.thinking_tokens` | yes, `reasoning_tokens` | key present, always 0 |
| **determinism_mode** | **temperature_only** | none | none |

**1. `temperature=0` is accepted and genuinely honoured** — unlike `seed` on the
OpenAI arms, which is accepted and silently ignored. There is no `seed`
parameter in the Anthropic API at all; the SDK raises `TypeError` on it. Recorded
as absence, not failure, per spec.

**2. Determinism had to be measured twice, and the toy prompt was misleading.**
On a short synthetic prompt, three temperature-0 calls were byte-identical (3/3),
which would have supported a clean `temperature_only` verdict. On the **real**
T02/T05 oracle/turtle prompts (~4.9k input tokens, ~450-500 char outputs) the raw
text is **not** byte-stable (T02 2/3 distinct, T05 3/3 distinct). This is the same
trap `seed` set in WI-4, one level deeper: do not generalise determinism from a
short generation to the study's actual workload.

**3. But the divergence is confined to unscored free text.** Re-running both
tasks and grading each repeat: **every graded field was identical across all
three calls on both tasks** (T02 class/property/intermediate identical,
partial 0.800 x3; T05 identical, partial 0.833 x3). So residual variance lives in
the `reasoning` string, not the answer. That is a materially better profile than
the OpenAI current-generation arms, where the WI-1 probe showed the *answers*
themselves varying. Hence `temperature_only` rather than `none`.
*Evidence limit: n=3, oracle only, turtle only, 2 tasks — sufficient to
distinguish it from the OpenAI arms, not sufficient to claim exact reproducibility.*

**4. Structured output DOES require a variant — and this is a D2 input, not a
decision.** With the existing `slot_filling_system_v4` prompt verbatim, Sonnet
wraps its JSON in a markdown code fence (` ```json ... ``` `), so
`json.loads` fails at char 0 and the unmodified strict schema rejects it. The
*content* inside the fence is correct and schema-shaped — this is a wrapper
problem, not a comprehension or schema problem. Three ways to resolve it, each
with a different confound cost, **none adopted**:

  - **(a) Anthropic tool-use** (probed, works): the prompt stays **byte-identical**
    to the other arms; only the API mechanism differs. Parsed and graded cleanly
    (`partial_credit=0.800`). Smallest confound — the prompt is not a variable.
  - **(b) Per-model prompt line** ("no markdown fences"): a documented per-model
    prompt variant, i.e. exactly the `v4-anthropic` confound the original spec
    warned about.
  - **(c) Fence-stripping in the shared parser**: changes the parsing path for
    **all** arms, including already-reported ones, and would alter existing
    results on rescore. Worst option for this study.

  On the evidence, (a) is the only route that leaves the prompt a constant across
  arms — but whether to accept a per-model *API path* at all is part of D2.

**5. Answer-quality note (n=1, not a result).** On T02 oracle/turtle Sonnet
answered `intermediate_node: true` where gold is `false`, scoring
`partial_credit=0.800` / `exact_match=0`; `gpt-5.5-2026-04-23` scored 1.000 on the
same cell. Single call, single format — recorded only so it is not mistaken for a
harness fault later.

**6. Pinning is an industry-wide problem, not an OpenAI one.** The Anthropic
model list shows current-generation models are **alias-only** too:
`claude-sonnet-5` (2026-06-29) and `claude-sonnet-4-6` (2026-02-17) carry no date
suffix; only `claude-sonnet-4-5-20250929`, `claude-opus-4-5-20251101` and
`claude-haiku-4-5-20251001` are pinned. `claude-sonnet-4-5-20250929` is therefore
the only probed arm that is **simultaneously pinned, temperature-controlled, and
pre-FDIS by construction** (Sept 2025 « April 2026), so it needs no contamination
floor re-run under the WI-6 scope limit — at the cost of not being
current-generation.

## 2026-08-04 (c) - WI-8 ELOT contrast reframed (scope change) + T04 claim retracted

Documentation only. No code, no corpora, and no gold sets changed. Resolution
adopted: **Option A — keep both ELOT corpora as they are and restate what the
contrast measures.**

### What the ELOT pair actually varies

On 2026-07-02 the flat `elot-org` arm gained an appended explicit
`- SubClassOf :: <parent>` line on class chunks (loader 2.0 -> 3.0). That change
converted the arm from a *heading-path ablation* into an **alternative encoding of
the same axiom**. `elot-org-ancestors` was left unchanged: its prepended ancestor
heading path already names the parent, so the explicit axiom is suppressed there.

The consequence, quantified by the WI-5 audit, is that the two arms now differ on
the **encoding style of subsumption**, not on the presence of the heading path:

| arm | subsumption on gold chunks | gold chunks missing an explicit statement |
|---|---|---|
| `elot-org` (flat) | explicit `- SubClassOf ::` line | **0 / 14** |
| `elot-org-ancestors` (nested) | heading-depth nesting only | **12 / 14** |

(Every other arm — turtle, omn, ofn, jsonld, yaml-ld, schema-concept — is also
0/14. `elot-org-ancestors` is the sole arm that encodes subsumption structurally.)

**Reframed scope.** The nested/flat pair tests **explicit axiom statement vs
structural (heading-depth) encoding of subsumption**. It does **not** test the
presence or absence of the heading path, because the arm lacking the path is also
the arm carrying the explicit axiom — either variable explains T04 equally well.
**Claims about the heading path per se are therefore out of scope for this
study** and must not be made from this pair.

**Why the reframed contrast is still worth reporting.** It answers a question the
original framing did not: *which encoding can an ELOT author rely on being read?*
That is a practitioner-facing result about authoring practice, and it is
actionable — an ELOT document that leans on heading depth to convey subsumption
is relying on something weaker models do not reliably read. The original framing
("what does structural hierarchy contribute?") could not be answered by this pair
at all once flat gained the axiom.

### RETRACTION — the T04 ELOT claim

**Retracted:** the 2026-06 entry *"Pilot post-retrieval: ELOT-flat
structural-encoding issue surfaced"*, and the 2026-07-02 claim that the
flat-vs-ancestors contrast *"now isolates exactly one variable"*. Both are marked
in place below. Prompted by the WI-5 audit
(`experiment/T04_gold_chunk_audit.md`, 2026-08-04).

**Replacement claim (narrower, and all the evidence supports):** on T04,
**gpt-4o-mini declined the inference under `elot-org-ancestors`**, reasoning that
the context *"does not explicitly state"* the relationship, and **was rescued
under the retrieved condition** by a property-level restatement
(`hasFunction ⊑ hasCapability`, `functionOf ⊑ capabilityOf`) supplied as explicit
axioms. That is evidence that **structural encoding is read less reliably than
explicit statement by weaker models** — nothing more. It is a single task, a
single model, and one arm; it is not evidence about the heading path, and not
evidence about stronger models (gpt-4o scored 1.000 on T04 in every arm and
condition).

### Separate item — the Llama T04 result is a model-reliability failure

Recorded separately because it must **not** be read as a context or format
effect. On T04 turtle/oracle, `llama3.1:8b-instruct-q8_0` returned
`"label": "contradicted"` while its own `reasoning` field reads, in full:

> `lis:Function rdfs:subClassOf lis:Capability.`

It quoted the exact triple that licenses `supported` and then emitted the
opposite label. Its condition split:

| condition | supported | contradicted |
|---|---|---|
| oracle | 3 | 21 |
| retrieved | 12 | 12 |

Retrieved is a 12/12 coin flip — noise, not improvement. Combined with the WI-2
floor inversion (floor 0.500 > oracle 0.125, which is the always-`supported`
degeneracy landing on a `supported` gold), the conclusion is that **Llama cannot
reliably convert a correctly-read axiom into the correct label**. Context is not
harmful to Llama on T04, and no format or context claim should be drawn from
this arm's T04 cells.

### Superseded phrasing found in the repo (listed, NOT edited)

The three literal strings named in the spec — "heading nesting carries",
"load-bearing subclass information", "ELOT-flat oracle failure" — **do not occur
anywhere in the repo**. The semantically equivalent claims that do occur:

| file | line | text |
|---|---|---|
| `experiment/CHANGELOG.MD` | 867-869 | "ELOT encodes subclass relationships via heading nesting in the source document. Stripping the heading path (flat) versus preserving it (nested) is a meaningful methodological distinction." |
| `experiment/CHANGELOG.MD` | 870-872 | "so the contribution of structural hierarchy can be measured rather than assumed" |
| `experiment/CHANGELOG.MD` | 1006 | heading: "Pilot post-retrieval: ELOT-flat structural-encoding issue surfaced" |
| `experiment/CHANGELOG.MD` | 1011-1013 | "ELOT-flat strips the heading path that encodes subclass structurally, and the flat chunk for `lis:Function` contains no explicit `SubClassOf` axiom" |
| `experiment/CHANGELOG.MD` | 1015-1020 | "treat ELOT-nested as the faithful ELOT representation and ELOT-flat as a controlled ablation that strips the heading path to measure what structural encoding contributes" |
| `experiment/CHANGELOG.MD` | 1096-1099 | "directly resolves the 2026-06 ELOT-flat finding (T04 ...) ... ELOT encodes the named superclass only through heading nesting, which the flat chunker strips" |
| `experiment/CHANGELOG.MD` | 1104-1105 | "The flat-vs-`elot-org-ancestors` contrast now isolates exactly one variable: 1-hop explicit axiom vs full ancestor heading path." |
| `app/document_loaders.py` | 1318 | "ELOT encodes a class's named superclass only through heading nesting, which ..." |
| `app/document_loaders.py` | 1348-1352 | "only through heading nesting. This is the default ``flat`` elot-org ... the prepended heading path ..." |
| `README.md` | 44 | "`elot-org-ancestors` uses the same `.org` source but instead prefixes entity chunks with their full ancestor heading path." |
| `experiment/config.py` | 54-57 | "ELOT ancestor chunks preserve the ancestor heading PATH ..." |
| `scripts/verify_ontology_chunkers.py` | 340 | "(1-hop SubClassOf, ancestor heading paths), so even a ..." |

Only the CHANGELOG occurrences are retractions of a *claim*; the
`document_loaders.py`, `config.py`, `README.md` and `verify_ontology_chunkers.py`
occurrences are accurate *descriptions of behaviour* and need no change — they are
listed because they use the superseded vocabulary and may need rewording if the
author wants the reframed scope reflected in prose.

**No analysis figures, captions, abstract draft, or presentation material for
this study exist in the repo.** Searched all `*.md/*.tex/*.ipynb/*.txt/*.rst`
outside `.venv`; the only prose carrying these claims is the methodology log
itself. The repo does contain binary/vector artefacts, but none are analysis
outputs of this study and none were searched or edited:
`resources/private/FDIS.docx` (the standard itself, binary — not searched),
`resources/private/images/*.svg` (10 hand-authored ontology hierarchy diagrams,
source material), `src/frontend/public/*.svg` (Next.js boilerplate), and
`src/rag/data/do-not-include/CII-FMEA.tex` (corpus material). If figure captions
or an abstract draft live outside this repo, they are **not** covered by this
sweep and must be checked by hand. Nothing was edited outside this log.

## 2026-08-04 (b) - WI-4 gpt-5.5 probe, WI-5 T04 audit, WI-6 parametric-knowledge result

### WI-6 - Parametric knowledge of IDO is ~zero (banked result)

**Result.** Across the WI-2 floor (`postretrieval-trial-10`), **slot-filling
exact-match is 0.000 in all 30 floor cells**, and every model's verification
accuracy is at or below the 0.667 majority-class baseline.

**Scope.** 3 models (`gpt-4o-2024-11-20`, `gpt-4o-mini-2024-07-18`,
`llama3.1:8b-instruct-q8_0`) x 5 tasks (T01-T05) x 2 floor conditions
(`no_context`, `empty_context`) x N=3 = 90 calls. Residual slot partial credit
(0.083-0.183) is the `intermediate_node` boolean being guessable at chance, not
recall of IDO content.

**Why it matters.** The lit review currently argues the near-zero-parametric-
knowledge premise from *publication timelines* — LIS-14/IDO reached FDIS in April
2026, after these models' training cutoffs. This is now a **direct measurement**
of that premise rather than an inference from dates, which is the stronger claim
and the one Mallen-style framing actually requires.

**Scope limit — the premise is NOT inherited by newer models.** It is a property
of the arms measured, not of the ontology. **Any arm postdating the April 2026
FDIS release must have this floor re-run before its results are interpreted**;
`gpt-5.5-2026-04-23` and the `gpt-5.6-*` family all postdate it and are therefore
*not* covered by this result. The floor is cheap ($0.046 for 90 calls), so there
is no reason to skip it when an arm is added. The original spec already routes the
new-model floor through T02/T05 as a contamination check; that remains required.

### WI-4 - `gpt-5.5-2026-04-23` determinism probe

Same probe and same fields as WI-1, run 2026-08-04. **Result: pinnable, but not
deterministic — `determinism_mode = none`, identical to the 5.6 arms.**

| field | gpt-5.5-2026-04-23 | gpt-5.6-terra | gpt-5.6-luna |
|---|---|---|---|
| dated snapshot | **YES** | no (alias only) | no (alias only) |
| `temperature=0` | **rejected (400)** | rejected (400) | rejected (400) |
| `seed` accepted | yes | yes | yes |
| `seed` **honoured** | **no** (3/3 distinct) | no (3/3 distinct) | no (3/3 distinct) |
| `system_fingerprint` | **None** | None | None |
| `response_format=json_object` | yes | yes | yes |
| T02 oracle/turtle parse | **OK, unmodified schema** | not run | not run |
| reasoning tokens | **YES, non-zero** | key present, always 0 | key present, always 0 |
| `reasoning_effort` effect | **real** (0/14/15/22) | none observed | none observed |
| **determinism_mode** | **none** | **none** | **none** |

Two findings that change the D2 trade-off:

1. **Pinning and determinism are separable, and only pinning is available.**
   `gpt-5.5-2026-04-23` fixes *model identity* but not *sampling*: temperature is
   forced to 1 and the seed is accepted-but-ignored, with no fingerprint to fall
   back on. So the choice is not "reproducible 5.5 vs non-reproducible 5.6" — it
   is "pinned-but-stochastic vs unpinned-and-stochastic". Neither restores the
   `seeded` mode the GPT-4o arms have.
2. **5.5 actually spends reasoning tokens, and they dominate cost.** The T02
   oracle/turtle acceptance call used **913 reasoning tokens of 1015 completion
   tokens (90%)**, at prompt=3932. Reasoning bills as output, so a 5.5 arm costs
   roughly an order of magnitude more per call than the GPT-4o arms on the same
   prompt. The 5.6 aliases reported 0 reasoning tokens at every effort level.

Acceptance check passed: T02/oracle/turtle returned a schema-valid parse on the
**unmodified** strict Pydantic schema with **no prompt change**
(`exact_match=1`, `partial_credit=1.000`, class `lis:PhysicalObject`, property
`lis:hasPhysicalQuantity`). So no per-model prompt variant is needed for the GPT
arms; the structured-output confound does not arise.

No adapter code and no pricing constants were added — the arm is not yet adopted.
Per the follow-up spec, if an arm with `determinism_mode = none` is adopted it
runs **N=5, not 3**, reports mean +/- SD, makes no format claim smaller than
within-cell noise, and is labelled non-reproducible in the manifest and in every
figure caption.

### D1 input - verification label set (tabulated, no recommendation)

**Undetermined-response rate under the floor** (verification only, n=9 per cell):

| model | condition | undetermined | supported | contradicted | undet. rate |
|---|---|---|---|---|---|
| gpt-4o-2024-11-20 | no_context | 9 | 0 | 0 | 1.000 |
| gpt-4o-2024-11-20 | empty_context | 9 | 0 | 0 | 1.000 |
| gpt-4o-mini | no_context | 9 | 0 | 0 | 1.000 |
| gpt-4o-mini | empty_context | 6 | 3 | 0 | 0.667 |
| llama3.1:8b-q8_0 | no_context | 0 | 9 | 0 | 0.000 |
| llama3.1:8b-q8_0 | empty_context | 6 | 3 | 0 | 0.667 |

**Current gold-label distribution, T01-T05:**

| gold_label | n tasks | share | tasks |
|---|---|---|---|
| supported | 2 | 0.667 | T01, T04 |
| contradicted | 1 | 0.333 | T03 |
| **undetermined** | **0** | **0.000** | — |
| total verification | 3 | | |
| slot_filling (no label) | 2 | | T02, T05 |

Both GPT arms answer `undetermined` on 100% of `no_context` items and score
0.000, because no gold item carries that label. Tabulated per the spec; no
recommendation offered.

### WI-5 - T04 gold-chunk audit

Full diagnosis: `experiment/T04_gold_chunk_audit.md`. **Proposal only — no gold
set changed.** Headline: **T04's gold is correct and sufficient**; the two signals
pointing at it have separate, non-gold causes.

- The `lis:Function` gold chunk carries the licensing axiom
  `rdfs:subClassOf lis:Capability` verbatim. Gold is 2 class chunks, 0 property
  chunks, so the "gold dominated by property chunks" hypothesis does not apply.
- **`elot-org-ancestors` drops the explicit subsumption statement on 12 of 14
  gold chunks across all five tasks**, encoding it as heading-indentation depth
  instead. Every other arm (including flat `elot-org`, which adds an explicit
  `- SubClassOf ::` line) keeps it: 0/14 missing. This is the cause of the one
  genuine oracle<retrieved cell (gpt-4o-mini), where mini answered `undetermined`
  with the reasoning "does not explicitly state" and retrieval rescued it by
  supplying `hasFunction ⊑ hasCapability` / `functionOf ⊑ capabilityOf` as
  explicit *property*-level restatements.
- **Llama's contribution is not a context effect at all**: its turtle/oracle
  failure quotes `lis:Function rdfs:subClassOf lis:Capability.` as its reasoning
  and returns `contradicted`. Its retrieved split is 12 supported / 12
  contradicted — a coin flip. The floor inversion is the always-`supported`
  degeneracy landing on a `supported` gold.

**Proposed rule (needs sign-off):** validate gold for **axiom licensing**, not
just entity resolution — each verification task declares a `licensing_axiom`
triple, and a gate asserts per arm that it is recoverable from the gold-chunk
union alone (entailment for round-trippable arms; explicit surface statement
otherwise, with structure-only encodings *not* counting). Explicitly rejected:
widening T04's gold with the property chunks, which would change the oracle for
all 8 arms to fix a defect in 1 and mask a real format finding.

**Caveat this creates for the format comparison:** `elot-org-ancestors` differs
from flat `elot-org` in *two* ways at once on gold chunks (ancestor path added,
explicit axiom removed), so any ancestors-vs-flat contrast confounds two
variables and should be reported as such.

## 2026-08-04 - Model-expansion capability probe (STOPPED) + no-context floor added

Work package: three items — add GPT-5.6 Terra / GPT-5.6 Luna / Claude Sonnet as
post-retrieval arms (WI-1), add a no-context floor condition (WI-2), then run a
new-models trial on T02+T05 (WI-3). **WI-2 is delivered. WI-1 and WI-3 are
stopped at the capability probe and await a supervisor decision** — two of the
package's own stop conditions fired. Recorded here because the reason is a
methodological one (reproducibility), not an implementation obstacle.

### WI-1 capability probe — result: STOP

Probed against the live API on 2026-08-04 with the project key. No adapter code
was written, per the package's instruction to stop rather than work around.

| check | gpt-5.6-terra | gpt-5.6-luna | Claude Sonnet |
|---|---|---|---|
| model reachable | yes | yes | **no — no credential** |
| pinned dated snapshot | **NO — alias only** | **NO — alias only** | not assessed |
| `temperature=0` | **rejected (400)** | **rejected (400)** | not assessed |
| `seed` accepted | yes | yes | not assessed |
| `seed` *honoured* | **no** | **no** | not assessed |
| `response_format=json_object` | yes | yes | n/a (tool-use API) |
| reasoning tokens exposed | key present, always 0 | key present, always 0 | not assessed |
| `reasoning_effort` accepted | yes (no observable effect) | yes (no observable effect) | not assessed |

**1. No dated snapshot exists (primary stop condition).** `/v1/models` lists
`gpt-5.6-terra`, `gpt-5.6-luna` and `gpt-5.6-sol` as floating aliases only.
Every other family member carries a pinned snapshot (`gpt-5.5-2026-04-23`,
`gpt-5.4-2026-03-05`, `gpt-5-2025-08-07`, …); probing for the corresponding
`gpt-5.6-*-2026-*` ids returns 404. An alias is repointed by the provider at
will, so a 5.6 arm could not be cited the way the existing arms are — and the
whole point of pinning `gpt-4o-2024-11-20` and the `q8_0` Llama quantisation was
that a floating alias is not a reproducible citation (see `config.MODELS`).

**2. Determinism cannot be established → `determinism_mode = none`.**
`temperature=0` is refused outright ("Only the default (1) value is supported"),
so these models can only be run at temperature 1. `seed` is *accepted without
error*, which is exactly the silent-ignore case the package warned about: three
identical calls with the same seed returned three different answers, and
`system_fingerprint` is `None`, so there is no backend-version handle either.
The existing arms are `seeded`; a 5.6 arm would be `none`. N=3 would then measure
sampling noise rather than reproduce a fixed draw — a different claim, and one
that cannot be silently mixed into the same table as the GPT-4o arms.

**3. Claude Sonnet is not runnable here at all.** No `ANTHROPIC_API_KEY` in
`src/.env` or the environment, and the `anthropic` SDK is not installed in the
venv. This is a provisioning + spend decision, not a code fix.

**Not blockers:** structured output needs no prompt change on the GPT arms
(`response_format=json_object` returns a schema-valid parse first try, so no
`v4-anthropic`-style prompt variant is required for them), and reasoning tokens
are exposed at `usage.completion_tokens_details.reasoning_tokens` but read 0 at
every `reasoning_effort` level, so the cost stop condition (~USD 25) is not
currently in play. Pricing constants were deliberately NOT added: pinning a rate
to a model the study may not adopt would put an unverified constant in the
methods chapter.

**Decision required from supervisors** (each changes the claim, not the code):
substitute the pinnable `gpt-5.5-2026-04-23` for the 5.6 aliases; or accept 5.6
as an explicitly non-reproducible arm reported as `determinism_mode=none` at
temperature 1; or drop the current-generation arm. Cross-vendor coverage
additionally needs an Anthropic key.

WI-3 (3 new models x 8 formats x {T02,T05} x {oracle,retrieved} x N=3 = 288
calls) is **not run**, as it is defined entirely over the arms above.

### WI-2 no-context floor — delivered

Adds two conditions measuring what each model scores with **no ontology context
at all**, so context-conditioned scores can be read against a baseline instead
of in absolute terms. `config.FLOOR_CONDITIONS`:

- **`no_context`** — the task input alone; the `Ontology content:` header is
  omitted entirely, so the prompt never mentions a corpus.
- **`empty_context`** — the identical scaffolding with an empty body (header
  present, zero chunks inside).

Both are kept: the pair separates "the model knows this from pretraining" from
"the model responds to an empty context block differently than to no block at
all". They differ *only* in the scaffolding, which is what makes the contrast
attributable to the empty block (asserted in
`test_floor_prompts_differ_only_in_the_context_scaffolding`).

**The floor is format-independent by construction.** With no corpus there is no
serialisation, so there is no format arm; cells are model x task x trial. Three
consequences, each deliberate:
- The format loop is **collapsed to a single sentinel run** per
  (task, condition, model, trial). Emitting one row per format would inflate the
  call count 8x and manufacture per-format "variance" between identical prompts.
- `format` is written as the sentinel **`__no_corpus__`**, not an empty cell: an
  empty CSV field is indistinguishable from a missing value, and this is
  greppable and unambiguous in downstream joins.
- **No prefix block is included.** Prefix blocks are per-format, so including one
  would both reintroduce a format arm and leak ontology namespaces into a
  condition that claims to have no ontology context.

**Undefined-vs-zero.** Retrieval and coverage columns are emitted as **null, never
0**, on floor rows. A 0 would read as a genuine miss and pollute any aggregate
averaging across conditions; the honest value is "undefined — there was no
corpus to retrieve from".

**Citations under the floor.** Any chunk citation is fabricated by definition, so
it is *recorded, not fatal*: `citation_hallucinated` (0/1) and
`hallucinated_citation_ids` per row, aggregated into a new
`floor_citations` diagnostics section with a per-model rate and flag.

**Schema relaxation is floor-scoped, on purpose.** Under a floor condition,
declining to cite is *correct*, so `FloorSlotFillingResponse` makes
`supporting_chunks` optional — otherwise a correct refusal parses as malformed
and silently zeroes the decision fields too. This is **not** applied to
`SlotFillingResponse`: 12 existing Llama pilot rows fail on a top-level missing
`supporting_chunks`, so a global relaxation would retroactively change how
already-reported arms grade on rescore. Floor-scoping keeps every existing arm
bit-identical (`test_wi1_regrade_reproduces_grades_except_documented_changes`
still passes, and `test_floor_scoped_schema_does_not_change_the_strict_schema`
pins the distinction).

**Reporting against the majority-class baseline.** `floor.py` writes
`floor_summary.csv` (per model x condition) and `floor_by_task.csv` (per model x
condition x task), and every verification accuracy is reported next to the
majority-class baseline for the same label distribution, with
`accuracy_minus_baseline` and `beats_majority_baseline`. Raw floor accuracy alone
would be actively misleading here for two already-documented reasons: the
verification golds contain no `undetermined` class, and gpt-4o-mini has a known
"supported" response bias (WI6: 123/126 "supported", 0.643 against a 0.667
baseline — *below* chance-by-majority). A model can post a respectable-looking
floor purely by answering one label every time; only the baseline delta exposes
it.

Floor-only runs skip `validate_gold_chunks_resolve` and record no
`loader_versions`, so the floor is runnable and interpretable independently of
any format's availability. Manifest additionally records
`floor_conditions_run`, `floor_only_run`, `floor_format_sentinel`.

### WI-2 floor results (`postretrieval-trial-10`)

3 base models x T01-T05 x 2 floor conditions x N=3 = **90 calls, $0.046**.
Per-model floor, verification accuracy against the 0.667 majority baseline:

| model | condition | verif acc | delta vs baseline | modal label | slot exact | fabricated citations |
|---|---|---|---|---|---|---|
| gpt-4o-2024-11-20 | empty_context | 0.000 | -0.667 | `undetermined` 1.00 | 0.000 | 0.500 |
| gpt-4o-2024-11-20 | no_context | 0.000 | -0.667 | `undetermined` 1.00 | 0.000 | 1.000 |
| gpt-4o-mini | empty_context | 0.333 | -0.333 | `undetermined` 0.67 | 0.000 | 1.000 |
| gpt-4o-mini | no_context | 0.000 | -0.667 | `undetermined` 1.00 | 0.000 | 1.000 |
| llama3.1:8b-q8_0 | empty_context | 0.333 | -0.333 | `undetermined` 0.67 | 0.000 | 0.500 |
| llama3.1:8b-q8_0 | no_context | **0.667** | **+0.000 (AT)** | `supported` 1.00 | 0.000 | 1.000 |

**No contamination signal.** Every model is at or below the majority-class
baseline, and slot exact-match is 0.000 in all 30 cells. Residual partial credit
(0.083-0.183) is the `intermediate_node` boolean being guessable, not knowledge.
IDO is not recoverable from these models' pretraining on this benchmark.

**Llama's 0.667 is the degenerate case, not knowledge.** Its `no_context` score
*equals* the baseline because it answered `supported` on 100% of items. This is
precisely the artefact the baseline-delta reporting exists to expose: read as raw
accuracy it is the best floor in the table; read against the baseline it is worth
nothing. Confirmed by the floor-vs-oracle comparison below.

**Floor vs context-conditioned oracle** (mean over the 8 format arms,
trials 8+9), gap = oracle - floor:

- **gpt-4o**: gaps 0.66-1.00 on every task. Context does real work throughout.
- **gpt-4o-mini**: healthy gaps except **T03 (floor 0.000 = oracle 0.000)** —
  mini fails T03 with or without the ontology, so T03 measures nothing *for this
  model*.
- **llama3.1:8b**: essentially **no task discriminates**. T01 floor 1.000 =
  oracle 1.000; T02 gap 0.100; T03 0.000 = 0.000; T05 gap 0.125; and **T04 is
  NEGATIVE (floor 0.500 vs oracle 0.125)** — Llama scores *better with no
  ontology than with it*. Its T01/T04 floor "successes" are the always-
  `supported` bias landing on `supported` golds, not comprehension.
  **Implication: the Llama verification arm carries little interpretable signal
  and should not be read as a format comparison.**

**Benchmark limitation surfaced by the floor (important for the write-up).**
Under no context GPT-4o answers `undetermined` on 100% of verification items —
epistemically the *correct* response when given no ontology — yet scores 0.000,
because `undetermined` never occurs as a gold label (already flagged by WI6 as
`labels_absent_everywhere`). The verification task therefore **cannot distinguish
correct abstention from error**, and a floor of 0.000 here should be read as "the
task has no way to credit the right answer", not as "the model knows nothing".
This bounds how low a verification floor can be interpreted at all, and is a
caveat the examiners should see stated.

**Fabricated citations are the norm without context**: 0.50-1.00 across models,
and 1.000 for every model under `no_context`. Models invent a chunk id rather
than decline, even when no context block exists to cite from.

`no_context` vs `empty_context` did diverge (mini 0.000 vs 0.333; Llama 0.667 vs
0.333), so keeping both was justified — the empty block is not inert, and it
generally pushed models *away* from the degenerate always-`supported` answer and
toward `undetermined`.

## 2026-07-30 - Schema-concept (Voicebox-style) exploratory condition added + piloted

Added an eighth, exploratory chunking condition, `schema-concept`, and ran a
bounded pilot. Unlike the seven core formats it is not a serialisation of the
ontology: it is a lossy, curated schema-first indexing baseline inspired by
commercial ontology assistants (Stardog Voicebox), which ground natural-language
interaction on schema labels/descriptions, class hierarchy, and property
domain/range. Spec: `experiment/voicebox_style_lis14_schema_concept_chunking.md`;
build plan: `experiment/schema_concept_chunking_implementation_plan.md`.

**Deliberately kept out of `config.FORMATS`.** It cannot satisfy the two claims
that define the core comparison — whole-graph isomorphism to canonical Turtle
(`verify_source_graph_equality`) and the full-serialisation entity set — because
it drops content by design (capped labels/descriptions/examples/notes, no full
restrictions or neighbourhoods, no annotation-property/individual chunks). So it
lives in a new `EXPLORATORY_FORMATS`/`ALL_SELECTABLE_FORMATS` (config.py); the
default `--formats` run stays the 7-serialisation RQ1/RQ2 headline, and the
condition is opt-in (`--formats schema-concept`). Chunk text is re-derived
deterministically from the canonical `.ttl` via rdflib — one curated chunk per
`owl:Class`/`owl:ObjectProperty`/`owl:DatatypeProperty` (155 entities, exactly
Turtle's named-retrievable class/property set). `entity_id` stays the bare CURIE
so gold-chunk resolution is unchanged. Wiring mirrors the ofn arm across
`document_loaders.py`, `config.py`, `corpus_index.py`, `context_block.py`,
`run_experiment.py`, and `verify_ontology_chunkers.py` (a scoped check sized to
what the condition claims: metadata contract, determinism, class/property parity
vs Turtle, hard word budget; plus informational coverage/context-budget reports).
Also hardened: `entity_ids_by_format(formats=None)` now validates the formats the
caller actually runs, not just the hardcoded core set.

**Pilot** (`postretrieval-trial-6`, `retrieval-trial-9`): turtle vs schema-concept,
gpt-4o-2024-11-20 + gpt-4o-mini-2024-07-18, oracle + retrieved, 5 tasks, 1 trial.
40 calls, $0.13 (well under the ~$2 ceiling; N=1 pilot, not the N=3 protocol).
40/40 cells deterministic.

**RQ1 (retrieval).** schema-concept retrieves gold *worse* than Turtle:
recall@5 0.733 vs 0.867, gold_recall@5 0.560 vs 0.620, nDCG@5 0.692 vs 0.793;
only MRR is higher (0.800 vs 0.767). Curation did not help retrieval on these
tasks and hurt coverage.

**RQ2 (post-retrieval).**
- *Verification (T01/T03/T04):* format-invariant — identical accuracy in every
  cell (T01/T04 ceiling; T03 gpt-4o 1.0 / mini 0.0, same for both formats). A
  single-axiom subclass check reads the same whether rendered as Turtle or as a
  curated schema line.
- *Slot-filling, oracle:* on the ANSWER slots schema-concept equals Turtle (T02
  gpt-4o both predict PhysicalObject/hasPhysicalQuantity/false with
  coverage_frac=1.0; T05 both 0.833). The apparent oracle gap (T02 gpt-4o turtle
  exact=1.0 vs schema-concept partial=0.6) is entirely a **citation-surface-form
  confound**, NOT comprehension — see below.
- *Slot-filling, retrieved:* schema-concept collapses on T02 (partial 0.2/0.0 vs
  turtle 0.8/0.6). Cause is the RQ1 recall gap: schema-concept's retrieved
  context had coverage_frac=0.0 (missed all gold licensing chunks), surfacing
  lis:Compound / MaterialCompositionQuality / qualityQuantityValue for "steel bar
  → mass", so the model answered class=Compound, property=qualityQuantityValue.
  T05 tied both formats (0.167).

**FINDING (citation-surface-form confound), the headline result of the pilot.**
The spec renders a cosmetic `CHUNK ID:` line inside each chunk body (e.g.
`class:lis.PhysicalObject:schema_concept`). Decision #4 of the build plan noted
the harness never parses that line — but the MODEL reads it and, on slot-filling,
cites it: on T02 oracle gpt-4o schema-concept cited
`class:lis.PhysicalObject:schema_concept` / `object_property:lis.hasParticipant…`
where Turtle cited the bare CURIE `lis:PhysicalObject`. The strict-equality
citation grader (no accept-set for chunk citations) scores the schema-concept
citations 0 despite pointing at exactly the right entity, costing 2 of 5 graded
slots. So the format is handicapped on the citation slots for a reason unrelated
to whether it conveyed the ontology. The competing surface form is also redundant:
context assembly already prepends the harness's own `# Chunk: <entity_id>` label
(bare CURIE) to every chunk.

**FIX + RE-RUN (loader 1.0 -> 1.1; `retrieval-trial-10`, `postretrieval-trial-7`).**
Removed the cosmetic `CHUNK ID:` line from the rendered chunk body in
`EntityBasedSchemaConceptLoader` (the `ENTITY:` line already carries the bare
CURIE as the citable identity, and context assembly prepends the harness's own
`# Chunk: <entity_id>` label, so nothing identifying is lost). Chunk content
changed, so the loader version bumped to 1.1 and the FAISS index auto-rebuilt on
its content checksum. Verify suite still green (parity 155, max chunk 251 words).
Same bounded pilot re-run, $0.13, 40 calls. Effects, all in the predicted
direction:
- *Citations fixed:* T02 oracle gpt-4o now cites bare `lis:PhysicalObject` /
  `lis:hasPhysicalQuantity` (was `class:lis.PhysicalObject:schema_concept`), so
  its partial rose 0.6 -> 0.8. The one slot it still misses is a genuine
  comprehension error (`intermediate_node=true` where gold is false), not a
  citation artifact.
- *Retrieval improved* (the `class:lis.X:schema_concept` tokens had been polluting
  the embeddings): recall@5 0.733 -> 0.800, gold_recall 0.560 -> 0.600, MRR
  0.800 -> 1.000, nDCG 0.692 -> 0.828. schema-concept now BEATS Turtle on ranking
  (MRR 1.000 vs 0.767, nDCG 0.828 vs 0.793) and only slightly trails on recall@5
  (0.800 vs 0.867).
- *Retrieved-condition collapse resolved:* T02 retrieved partial 0.2/0.0 -> 0.6/0.4
  (gpt-4o/mini), tracking the recovered recall; still a touch under Turtle
  (0.8/0.6).

**N=1 CAVEAT (important for interpretation).** These are single-trial runs, and
OpenAI is only "mostly deterministic" at temperature 0 + fixed seed. Comparing
the two pilot runs exposes it directly: `T05 turtle oracle gpt-4o` moved
0.833 -> 1.000 between trial-6 and trial-7 with NO change to the Turtle arm — pure
run-to-run model noise on a borderline slot cell. So residual ~1-slot differences
between turtle and schema-concept on T02/T05 are within N=1 noise and must not be
read as format effects. The verification cells (T01/T03/T04) are stable and
format-invariant.

**VERDICT (pilot).** The citation confound is resolved; the fix also (unexpectedly)
helped retrieval. On this 5-task pilot the corrected schema-concept condition is
format-invariant on verification, competitive-to-better on retrieval ranking, and
neutral on slot-filling answers under oracle — no longer showing the earlier
harmful gap. But nothing here is separable from N=1 model noise on the slot tasks,
so a firm claim needs the full 3-model × 3-trial protocol. Run next (below).

**FULL RUN (all 8 formats × 3 models × 2 conditions × 5 tasks × N=3).**
`retrieval-trial-11` (RQ1, all 8 formats) + `postretrieval-trial-9` (GPT, 480
calls, $1.76) + `postretrieval-trial-8` (Llama, 240 calls, $0). Post-retrieval was
split by provider for resilience (call_model does not retry Ollama, and rows are
written only at the end, so a late Llama failure would otherwise lose the GPT
spend) — same pattern as the 2026-07-16 Llama re-run. Zero parse errors on the GPT
arm. The two arms were then merged and offline-rescored into
`postretrieval-combined-8-9/` (720 rows, all 3 models; `postretrieval_raw.csv` +
`_rescored.csv` + `_scored.csv` + `_variance.csv` + unified diagnostics/manifest).
Rescoring changed no grade (both runs were already at the current grader) and the
per-row chunk-count integrity check passed on all 720 rows; that combined dir is
the canonical dataset for this run.

RQ1 (retrieval, all 8): schema-concept has the BEST ranking of any format
(MRR 1.000, nDCG@5 0.828) but mid-pack recall@5 (0.800; ofn 0.933, turtle/omn/
yaml-ld 0.867). It ranks the gold it finds first, but finds slightly less of it.

RQ2 (GPT arm, the capable models — headline):
- *Verification (T01/T03/T04): format-invariant.* Every format is identical,
  schema-concept included; the ONLY cell where any format differed is
  elot-org-ancestors T04 oracle mini = 0.0 (all others, all formats, match). So
  serialisation — curated or verbatim — does not move single/near-single-axiom
  verification for these models. (T01/T04 sit at ceiling for gpt-4o, so they
  cannot discriminate formats by construction.)
- *Slot-filling, oracle:* schema-concept is competitive but marginally BELOW the
  strongest verbatim formats. T02 gpt-4o partial 0.867 vs ~1.000 for
  turtle/omn/jsonld/yaml-ld/ofn/elot-org-ancestors (elot-org 0.933); T05 gpt-4o
  0.833 vs 0.944 for turtle/omn (elot-org-ancestors worst at 0.556). On mini the
  formats mostly tie (~0.800 T02; schema-concept = turtle), with ofn the outlier
  (T02 0.400; T05 1.000). The residual schema-concept T02 gap is an occasional
  `intermediate_node=true` slip, not a citation artifact (that was fixed).
- *Slot-filling, retrieved:* noisy and low across all formats (jsonld best on T02
  at 1.000; ofn best on T05 at 0.667); schema-concept mid-pack (T02 0.600,
  T05 0.167), tracking its RQ1 recall.

Llama arm (`postretrieval-trial-8`): weak and largely format-insensitive
(verification acc 0.438 < 0.667 baseline; T02/T03/T05 at floor; only T01 ceiling),
as in prior runs — a low-capability reference point, no format signal.

**IMPORTANT — nondeterminism dominates the slot margins.** Only 65/160 GPT slot
cells were identical across the three trials, and several exact-match cells carry
std ±0.577 (a metric flipping 0↔1 between seeds). So the ~0.1-partial gaps between
schema-concept and the best verbatim formats on the oracle slot tasks are WITHIN
run-to-run model noise, not established format effects. With only two real slot
tasks (T02, T05) and verification at ceiling for the strong model, this 5-task set
cannot support a firm ranking; the 30-task benchmark is the real test.

**VERDICT (final, this study stage).** Across the full protocol, schema-concept is
verification-invariant, best-in-class on retrieval RANKING, mid-pack on retrieval
RECALL, and neutral-to-slightly-behind the strongest verbatim serialisations on
oracle slot-filling — the last within N=3 noise. So on this ontology and this
5-task pilot there is NO evidence that Voicebox-style schema-first curation
improves end-to-end answer quality over plain serialisation, though it does order
retrieved gold better. The condition is now fully wired, verified, de-confounded,
and exercised under the standard protocol; whether it earns a place in the 30-task
benchmark is a research call for the supervisor, and the honest input to that call
is "comparable, not better, on a task base too thin to rank confidently." I am deciding
since it is only comparable, and not better, it can just stay in the appendix.

## 2026-07-23 - Harness + schema changes before the 30-task run 

Pilot analysis (`postretrieval-trial-4`, 420 rows) exposed four defects; fixed before
the 30-task benchmark is authored. The pilot was graded under the now-removed class
accept-list, so it is regraded with the current strict grader (above); the only
per-field changes from the stored pilot are 84 T02 `support_intermediate` -> N/A (WI2)
and 37 T05 `class`/`support_class` 1->0 (strict policy). Overall slot MPC 0.645 -> 0.632.

**Grading decoupled from generation (refactor).** New `experiment/rescore.py`
(`python -m experiment.rescore <raw.csv>`): rebuilds the typed prediction from the
stored `pred_*` columns and re-runs the *pure* graders offline (no network), writing
`postretrieval_rescored.csv`. Regrading a completed run now costs nothing.
`grade_slot_filling` split into `_raw_slot_booleans` (unchanged strict comparisons) +
`_assemble_slot_grade` (denominator). WI1 itself changes no grade value.

**Partial-credit denominator is gold-driven, not a flat 6.** A support-citation
slot with no gold citation is unsatisfiable, so it is excluded (emitted N/A) instead of
scored 0; `grade_n_fields` counts only graded fields (T02 -> 5, T05 -> 6) and
`grade_exact_match` = all graded fields correct. Reason: a model wrongly predicting
`intermediate_node: true` previously lost 2 of 6 fields for one conceptual error
(48/84 T02 rows), and a prediction-conditioned denominator would make MPC incomparable
across cells. `validate_slot_gradeability` fails loudly if any graded field is
unsatisfiable given the item's gold.

**Reasoning_type + query_source on every task.** One answer-describing
`reasoning_type` per task (direct_assertion / structural / modelling_pattern /
definitional), crossable with task_type; query wording recorded separately as the
factual `query_source` (label / definition / example / paraphrase). Pilot rationale:
the two `paraphrase` items (T02, T05) were the only ones to produce format signal;
T01/T04 name both classes by IRI (direct_assertion) and sat at ceiling.

**Per-field supporting-chunk map.** `field_gold_chunks` maps each slot-answer
field to the gold chunk id(s) that license it; an empty list excludes the field (WI2)
and marks it N/A for coverage (WI5). Values are chunk ids, validated to resolve in all
7 formats. Licensing sets are the strict gold ids (aligned with the strict grader), not
the defensible-bearer accept-set. `primary_answer_chunk` deprecated: retained only as a
read-only alias for RQ1's `primary_answer_rank`, no longer written.

**Coverage covariate, ID-based (interpretation change).** `context_chunk_ids`
(JSON) recorded on every row; per graded field `covered_<field>` = set membership of a
licensing chunk in the context; `coverage_all`/`coverage_frac` over graded fields that
require an entity. Replaces fragile substring matching on prose. Backfill reads the
`# Chunk:` labels already in each stored `user_content` (exact, offline, no retrieval
re-run, no chunker-drift risk); a hard check asserts recovered chunk count ==
`n_context_chunks`. The mediation holds: T05 `grade_property_correct` is 0.89 where
`covered_property` is true (18 cells) vs 0.00 where false (10 cells).

**Diagnostics on every scoring run.** `experiment/diagnostics.py`: majority-class
baseline (overall / per-model / per-reasoning_type); per-model predicted-label
distribution (flag modal > 90%) and accuracy vs baseline (flag <=); gold-label balance
per reasoning_type (flag absent classes); ceiling/floor (flag items with >=90% of cells
at 1.0 / 0.0, exceptions counted); text-level determinism (identical-raw cells,
distinct fingerprints). Surfaces the pilot's response bias (mini answered supported on
123/126, accuracy 0.643 <= 0.667 baseline).

Padding is a THIRD
condition, `oracle_padded`, added ALONGSIDE the unpadded `oracle` upper bound, never
replacing it: three irrelevant chunks change the question from "can the model read this
format given exactly the right information" to "...given the right information plus
noise", which depresses oracle scores for reasons unrelated to retrieval, so both are
reported. Padding entity ids are sampled ONCE PER TASK with a pinned per-task seed from
the shared retrieval-eligible pool (domain entity chunks only, per the exclusion
policy) and the SAME entities are serialised into every format — sampling per format
would reintroduce the entity-set variation random padding exists to remove. Sampled ids
are recorded in the manifest (`oracle_pad_entity_ids`). `--pad-strategy random`
(per-task shared sample, offline; default) or `retrieved` (per-format top-ranked
non-gold, intentionally not entity-controlled). Oracle sets exceeding k are never
truncated; the over-k discrepancy is recorded.

FINDING (trial-5, all 3 models x 3 conditions) and DECISION: the length confound is
empirically negligible on the strong models — oracle vs oracle_padded slot MPC differs
by <=0.03 (4o 0.921 vs 0.905; mini 0.816 vs 0.807) and padding slightly HELPS Llama
(0.271 vs 0.312). So `oracle_padded` is demoted to a selectable robustness appendix,
removed from the default `CONDITIONS` (now `[oracle, retrieved]`; `ALL_CONDITIONS`
keeps it as a `--conditions` choice). The unpadded `oracle` is the headline upper
bound. (Note: padding is a no-op for the pilot's slot tasks — T02 gold=k, T05 gold>k —
so the only place it moved anything was mini's verification accuracy, 0.619 -> 0.524;
the 30-task set would need slot items with gold < k for padding to bite there.)

## 2026-07-23 - SupportingChunks: tolerate ABSENT citation keys, not just null

`SupportingChunks.class/.property/.intermediate_node` now default to `None`
(`str | None = None`), not merely `str | None`. In Pydantic v2 an `Optional` field
without a default is still REQUIRED — it permits the value `null` but not an omitted
key — so the earlier "str -> Optional[str]" change (2026-07-02) fixed `"property":
null` but NOT a Llama response that omits `property`/`intermediate_node` entirely. The
latter surfaced as 6 `Field required [type=missing]` parse failures (Llama, T02/omn,
oracle + oracle_padded, all trials) in trial-5. With the default, an absent citation
parses and grades as an uncited (wrong) slot, same as an explicit null.
`experiment.rescore` now also re-parses any previously-failed row's stored
`raw_response` with the current schema (offline), so such runs can be healed without
re-calling the API. Also: `reasoning_type`/`query_source` are now written onto every
raw/scored row 

## 2026-07-23 - Whole-graph set equality across formats; OMN ontology label stripped

Added a source-graph set-equality gate (`verify_source_graph_equality` in
`verify_ontology_chunkers.py`) and, prompted by it, made a one-line correction to
the OMN source. This strengthens the "same ontology, different serialisation"
claim from entity_id parity (the chunkers expose matching ids) to whole-graph
identity (each format's SOURCE FILE reconstructs the exact canonical-Turtle RDF
graph, blank nodes included, before chunking).

## 2026-07-23 - Class accept-list removed; class slot now strict exact-match

On the supervisor's advice (ontologist, T-Box ontology): a less-specific but
syntactically valid class is a semantic error, not partial success, so it should
earn no credit. Removed the `gold_class_accept` / "Option A" accept-list
machinery (2026-06-14 *Bearer-class grading* entry) - the `gold_class_accept`
field and `Task.accepted_class_ids()` in `schemas.py`, its handling in
`validate_gold_chunks_resolve`, the accept-set logic in
`grading.grade_slot_filling`, and the `gold_class_accept:` blocks on T02/T05.
The class slot (and its supporting-chunk citation) is now strict exact-match
against the single canonical `gold_class`, identical to how the property slot is
already graded (2026-07-16). A defensible-but-less-specific bearer (e.g.
`lis:PhysicalArtefact`/`lis:FunctionalObject` for the pump) now scores 0.

Unchanged: the response-level `partial_credit` metric (fraction of the six slots
exactly correct) stays - it measures how many slots are exactly right, not a
specificity reward, so it is orthogonal to the supervisor's point.

## 2026-07-17 - OWL Functional Syntax (OFN) added as a seventh format

Format list extended to seven, adding **ofn**. Unlike the YAML-LD arm (a re-emit
riding the JSON-LD path), OFN needed its own generator and its own parser.

Provenance - ROBOT/OWLAPI, not rdflib, not py-horned-owl. rdflib cannot emit OFN:
it is not an RDF serialisation but the OWL structural specification's own syntax.
The source `data/LIS-14-for-FDIS (1).ofn` is generated by `scripts/tangle_ofn.py`
via `robot convert --format ofn` from the canonical `.ttl`, so it is
axiom-identical to the other arms by construction.

py-horned-owl was evaluated as a pure-Python alternative (avoiding Java) and
**rejected for generation**: its RDF/XML reader silently drops
`owl:AllDisjointClasses`, yielding 15 binary DisjointClasses and 0 n-ary against
ROBOT's 15 + 3 (arity 3,3,4), which matches Turtle's 15 `owl:disjointWith`
triples + 3 `owl:AllDisjointClasses` blank nodes. The loss is *logically*
invisible here - the Turtle redundantly states all 12 covered pairs as binaries,
so entailments are unchanged - but structurally real: it would have left the OFN
arm with zero `ofn-axiom-*` chunks while Turtle has three. Note this is a defect
of its RDF path only; its OFN *reader* is sound and is retained as the
generation-time verification parser (`py-horned-owl==1.4.1`, build-time).

Reproducibility. OWLAPI's rendering affects output bytes, and `robot --version`
does not surface the bundled OWLAPI version, so the jar checksum is the pin. The
full set (ROBOT 1.9.10, jar SHA256, Java 16.0.2 Temurin, source `.ttl` SHA256,
output `.ofn` SHA256) is recorded in the `tangle_ofn.py` docstring. The 79MB jar
is deliberately not vendored (build-time only; the `.ofn` is committed): park it
outside the repo and point `$ROBOT_JAR` at it. ROBOT is never needed to *run* the
experiment.

Determinism. OWLAPI axiom ordering is unstable across runs (set iteration order),
so `tangle_ofn.py` sorts prefixes, ontology annotations, and axioms explicitly.
Verified byte-identical across two independent `robot convert` invocations.

**Chunk-membership policy (the arity/shape rule).** OFN is a flat axiom list with
no per-entity markers, so chunks are formed by grouping axioms by the entity they
attach to, where "attach" is pegged to *Turtle's CBD root* - the entity whose
subject position the axiom's RDF mapping uses. This is the one place a reader
could reasonably ask why chunks were grouped this way, so the rule is named here.
It is arg1 for most axioms, but three forms root elsewhere, each verified against
this ontology's Turtle rather than assumed:

| OFN form | roots at | n |
|---|---|---|
| `AnnotationAssertion(P S V)` | `S` (arg2) | 935 |
| `AnnotationAssertion(Annotation(..) P S V)` | `S` (arg3, after inline annotations) | 104 |
| `SubObjectPropertyOf(ObjectPropertyChain(..) Q)` | `Q` (arg2, the super-property) | 5 |
| `DisjointClasses(A B)` | `A` (arg1) | 15 |
| `DisjointClasses(A B C..)` | *nothing* -> standalone `ofn-axiom-*` chunk | 3 |

The last is the arity split: OWL's RDF mapping sends binary disjointness to a
plain `A owl:disjointWith B` triple (so Turtle's CBD for A holds it) but n-ary to
an `owl:AllDisjointClasses` blank node (so Turtle puts it in a `ttl-axiom-*`
chunk). `ofn-axiom-*` mirrors that. The 104 annotated assertions are the same
`owl:Axiom` reifications the JSON-LD arm reattaches via `owl:annotatedSource`.
All three forms share the property that **`entity_id` parity passes while chunk
content silently diverges**, so parity cannot catch them.

Trap enumeration is closed, not sampled. Rather than discover these one at a
time, the complete axiom-type inventory of the `.ofn` was enumerated and each
type's Turtle rooting checked. The blank-node-rooted forms present in IDO are
only `owl:Axiom` (104) and `owl:AllDisjointClasses` (3) - there are no
`owl:AllDisjointProperties`, `owl:AllDifferent`, or negative property
assertions. The Turtle<->OFN mapping reconciles exactly (`subClassOf 57` =
`SubClassOf 57`; `subPropertyOf 99 + propertyChainAxiom 5` =
`SubObjectPropertyOf 86 + SubAnnotationPropertyOf 18`; `domain 37` =
`ObjectPropertyDomain 34 + DataPropertyDomain 3`; etc.), so nothing is
unaccounted for.

Parsing. ROBOT emits exactly one axiom per line at column 0 with no multi-line
literals, so chunks are verbatim source slices (as in Turtle/OMN/ELOT, unlike the
re-serialised JSON-LD/YAML-LD arms). Subject extraction uses a quote- and
escape-aware top-level splitter (`ofn_split_args`), which is required, not
belt-and-braces: IDO's annotation prose contains both parentheses ("... (OM 2).")
and escaped quotes (`is defined in OWL Time as \"A temporal entity ...\"`), on
which a naive bracket counter mis-nests.

Verification. The **semantic diff against Turtle is the primary gate**, not the
last item: byte-stability and `entity_id` parity both pass on a chunker that
attaches axioms to the wrong entity. `verify_ontology_chunkers.py` diffs the OFN
axiom set against the Turtle triples for three diagnostic entities -
`lis:Activity` (restriction + both binary and n-ary disjointness; the n-ary must
be *absent*, as it is in Turtle), `lis:hasParticipant` (3 property chains), and
`lis:UnitOfMeasure` (annotated assertion) - and all reconcile exactly. Also
gated: axiom coverage (all 1552 axioms assigned exactly once - a check the flat
structure uniquely affords), set-equality of the axiom set across canonicalisation
(set, not count: two documents can agree on count and differ in content), chunk
determinism, named-retrievable parity vs Turtle (155), prefix equivalence (20
prefixes x 7 formats), and gold resolution.

Lesson recorded: an early `tangle_ofn.py` was byte-stable across runs *and*
produced an unparseable file - sorting lines shredded ROBOT's two-line
`Ontology(...)` header and its `#` section comments. Stability gates catch drift,
not wrongness; only the parse/set-equality gate caught it.

Context budget (cl100k_base): ofn max chunk 835 tok, worst-case top-5 + prefix +
largest system prompt = 4438, leaving 11946 headroom at `OLLAMA_NUM_CTX=16384`.
OFN is the lightest structured arm (cf. jsonld 1473/6046, yaml-ld 1265/5313).
207 chunks, 158 retrievable - identical to omn/jsonld/yaml-ld.

## 2026-07-16 - YAML-LD added as a sixth format

Format list extended to six: turtle, elot-org (flat), elot-org-ancestors
(nested), omn, jsonld, **yaml-ld**. Like JSON-LD, YAML-LD is a serialisation of
the *same* ontology, so it slots into the existing "same ontology, different
serialisation" comparison.

Provenance - a YAML re-emit of the JSON-LD arm, NOT an independent serialiser.
YAML-LD (W3C First Public Working Draft, 2026-03-04) is defined as conventions
over YAML such that any YAML-LD document converts to a valid JSON-LD document.
The arm exploits this: it rides the JSON-LD pipeline unchanged (rdflib parse,
CBD-per-named-subject grouping, `owl:Axiom` re-attachment by `annotatedSource`,
`@context` stripping) and diverges only at the *final emit* - the same
per-entity canonical Python object the JSON-LD arm renders as JSON is instead
rendered as YAML. `canonicalize_jsonld` was refactored to expose that
pre-serialisation object (`canonicalize_jsonld_object`); `canonicalize_jsonld`
and the new `canonicalize_yamlld` both call it, so the two arms cannot diverge
above the emit seam. The source file `data/LIS-14-for-FDIS (1).yamlld` is
produced by `scripts/tangle_yamlld.py`, which builds the exact same compacted
object as `scripts/tangle_jsonld.py` (`build_jsonld_object`) and emits YAML.

Pegging chain (chunk membership). YAML-LD chunk membership equals JSON-LD's by
construction (same graph, same CBD grouping, same entity_ids - the loader is a
subclass that overrides only source-read and emit), and JSON-LD's equals
Turtle's by construction (the 2026-07-03 parity guard). So YAML-LD is pegged to
Turtle transitively; `verify_ontology_chunkers.py` asserts the yaml-ld
named-retrievable entity set equals Turtle's (155 entities), same as jsonld.

YAML 1.2, pinned. Emit uses ruamel.yaml in YAML 1.2 Core Schema mode
(`version=(1,2)`, self-declaring `%YAML 1.2` directive per chunk), NOT PyYAML.
PyYAML is YAML 1.1 and coerces barewords `no`/`yes`/`on`/`off` to booleans (the
"Norway problem"), which YAML-LD rules out and which would silently corrupt any
matching local name or annotation value. Anchors/aliases are disabled
(`ignore_aliases`): they carry no information in YAML-LD and may be dropped, and
a shared node must inline exactly as it does in the JSON-LD chunk rather than
render as an alias. Determinism follows the JSON-LD discipline: keys sorted in
the shared canonical object, plain arrays sorted, `@list` never reordered
(ordered `rdf:List` - `owl:members`/`unionOf`/`intersectionOf`/`oneOf`).

Round-trip conformance is the gate. `verify_ontology_chunkers.py` parses every
emitted YAML-LD chunk back (YAML 1.2) and asserts it equals the JSON-LD object
of the matching chunk - the spec's "converts to valid JSON-LD" constraint. This
one check catches the Norway problem, anchor emission, and any 1.1 coercion.
All gates pass: round-trip/object-identity over 207 chunks; byte-determinism
across two loads; named-retrievable parity vs Turtle (155 entities);
prefix-block equivalence (the YAML `@context` parses to the same shared
20-prefix map, so `assert_prefix_equivalence` passes across all six formats);
gold-chunk resolution in all six formats.

Context budget (measured, cl100k_base). YAML-LD is the lighter LD arm, as
expected - it drops JSON's braces, brackets, and key quoting:

| | max chunk | worst-case top-5 block | + largest system prompt | headroom vs num_ctx=16384 |
|---|---|---|---|---|
| jsonld | 1473 | 5498 | 6111 | 10273 |
| yaml-ld | 1265 | 4765 | 5378 | 11006 |

Both formats expose 158 retrievable chunks (of 207 total). The top-5 figure is a
deliberate worst case - the five *largest* chunks retrieved together, which
retrieval would not actually produce - and it still leaves ~11k tokens of
headroom at the pinned `OLLAMA_NUM_CTX=16384`. Both would also fit the older
8192 setting (yaml-ld 5378, jsonld 6111), so no Llama cell can silently
truncate.

Wiring. `config.FORMATS`/`ONTOLOGY_FILES` (`.yamlld`),
`corpus_index.load_format_chunks`, `context_block.{extract_prefix_block,
parse_prefix_map}` (YAML `@context` branch), and `document_loaders`
(`EntityBasedYamlLdLoader` subclass of `EntityBasedJsonLdLoader`;
`ENTITY_LOADER_VERSIONS["yaml-ld"]=1.0`; `ONTOLOGY_FILE_EXTENSIONS`;
retrieval-exclusion of `yamlld:prefixes`/`yamlld:Prefixes`;
`load_ontology_file` branch). New dependency: `ruamel.yaml`. Index rebuilds
automatically on content-checksum change. The production assistant is unaffected
by default (`CORPUS_FORMAT` is `turtle`); the `yaml-ld` branch only activates
when explicitly selected.

## 2026-07-03 - JSON-LD added as a fifth format

Format list extended to five: turtle, elot-org (flat), elot-org-ancestors
(nested), omn, **jsonld**. The JSON-LD variant is a serialization of the *same*
ontology, so it slots into the existing "same ontology, different serialization"
comparison.

Provenance (not an ELOT tangle, not ROBOT). ELOT tangles only to OWL Manchester
(`.omn`); ROBOT's `--format json` emits OBO Graphs JSON, a different data model,
**not** JSON-LD. True JSON-LD is produced by `scripts/tangle_jsonld.py`, which
serializes the canonical Turtle source with rdflib (already a dependency), so the
JSON-LD is axiom-identical to the Turtle/OMN/ELOT variants. It is compacted
against the Turtle file's own `@prefix` set (qname `@id`s, a single top-level
`@context`); the source file is `data/LIS-14-for-FDIS (1).jsonld`.

Chunker (`EntityBasedJsonLdLoader`). JSON-LD has no per-entity source markers
(unlike Turtle's `###  URI` or OMN's `Class:`), so chunks are re-serialized per
subject: each chunk is the subject's Concise Bounded Description (restrictions
stay inlined, as in Turtle's verbatim slice) **plus** any `owl:Axiom` reification
whose `owl:annotatedSource` is that subject. The latter is a deliberate parity
fix: Protege writes axiom annotations (`explanatoryNote`, ...) as reified
`[ owl:Axiom ... ]` blocks placed after the entity, and Turtle's file-order slice
folds them into the entity chunk; attaching them by `annotatedSource` reproduces
that so oracle content matches across formats. `owl:AllDisjointClasses` (and any
unsourced `owl:Axiom`) become standalone `jsonld-axiom-*` chunks, mirroring
Turtle's `ttl-axiom-*`. Each chunk drops the `@context` (prepended once during
context assembly), leaving prefixed qnames.

Backend decision - rdflib + in-house bnode inliner, NOT pyld. The compaction spike
(plan's decision gate) found rdflib compacts `@id`s to qnames cleanly and emits
ordered lists as `@list`, but serializes a *flat* `@graph` with blank nodes
carrying `_:nXXXX` labels that are **regenerated on every parse** -- a determinism
break. Rather than add pyld for framing, `canonicalize_jsonld(inline_bnodes=True)`
resolves each `{"@id": "_:x"}` reference inline (Turtle-style nesting), drops the
volatile label, preserves `@list` order, and deterministically relabels any
free-floating axiom bnodes `_:b0..` by content order. Verified byte-identical
across two runs, keeping the FAISS content-checksum cache and the N=3 fixed-seed
protocol reproducible without a new pinned dependency.

Parity guard. `scripts/verify_ontology_chunkers.py` now asserts the JSON-LD
chunker exposes exactly the same *named, retrievable* entity set as the Turtle
baseline (155 class/object-property/data-property entities), catching a CBD
grouping that drops or invents an entity chunk where gold-subset resolution would
not. Prefix-equivalence (`@context` == the shared 20-prefix map) and
gold-chunk resolution pass across all five formats; the `jsonld` FAISS index
builds and returns sensible top-k.

Wiring. `config.FORMATS`/`ONTOLOGY_FILES`, `corpus_index.load_format_chunks`,
`context_block.{extract_prefix_block,parse_prefix_map}` (JSON `@context` branch),
and `document_loaders` (loader + `ENTITY_LOADER_VERSIONS["jsonld"]=1.0`,
`ONTOLOGY_FILE_EXTENSIONS`, retrieval-exclusion of `jsonld:prefixes`/`Prefixes`,
`load_ontology_file` branch). Index rebuilds automatically on content-checksum
change. The production assistant is unaffected by default (`CORPUS_FORMAT` is
`turtle`); the `jsonld` branch only activates when explicitly selected.

## 2026-05 - Harness scaffolded

Initial build of `src/rag/experiment/` as additive package. Production
assistant (`src/rag/app/`) and existing eval (`src/rag/eval/`) unchanged.
Reuses `document_loaders.load_ontology_file` for chunkers; everything
else is new. Format list locked to [turtle, elot-org, omn]. Smoke test
gates the build.

## 2026-05 - ELOT ancestor headings: variant added

Added `include_ancestor_headings: bool = False` flag to
`EntityBasedElotOrgLoader`. Default-off preserves existing assistant
behavior. Experiment package opts in for a second variant.

Rationale: ELOT encodes subclass relationships via heading nesting in
the source document. Stripping the heading path (flat) versus
preserving it (nested) is a meaningful methodological distinction.
Promoted from a one-vs-other choice to a variant comparison so the
contribution of structural hierarchy can be measured rather than
assumed. Format list extended to four: turtle, elot-org (flat),
elot-org-ancestors (nested), omn.

> **[SCOPE SUPERSEDED 2026-08-04 — see the 2026-08-04 (c) WI-8 entry.]** This
> rationale describes what the pair measured *as built in 2026-05*, when flat was
> genuinely a heading-path ablation. The 2026-07-02 loader change gave the flat
> arm an explicit `- SubClassOf ::` axiom, so the pair no longer measures "the
> contribution of structural hierarchy" — it measures **explicit axiom statement
> vs structural (heading-depth) encoding**. The variant comparison is retained;
> only its stated scope changes.

## 2026-05 - Prefix block extraction

Turtle's pre-chunk bundled namespace declarations with the full
owl:Ontology block (dcterms metadata, contributors, version history).
ELOT and OMN prefix chunks are namespace-only. `context_block.py`
now extracts just `@prefix`/`@base` lines from Turtle's pre-chunk,
dropping the ontology block, so prefix content is comparable across
formats. Stage-1 prefix-equivalence assertion checks the three
formats produce identical {prefix:uri} maps.

## 2026-05 - Retrieval index exclusion policy

Initial pilot retrieval surfaced `lis-ont:core` (ontology declaration
with `dcterms:description` mentioning industrial assets) in every
top-5 result across all formats. Investigation showed multiple other
chunk types should not be retrieval targets either.

Locked policy: retrieval index includes only owl:Class,
owl:ObjectProperty, owl:DataProperty chunks. Excluded:
- Ontology declarations (`lis-ont:core`)
- Annotation property declarations (all `owl:AnnotationProperty`)
- ELOT structural section chunks (`elot:section:*`)
- ELOT exporter metadata (`elot:file-intro`, `elot:root:core`)
- Prefix-block chunks (handled separately in context assembly)
- Empty datatype declarations (xsd primitives, rdfs:Literal)

Excluded chunks remain in the chunk store and are reachable via
`gold_chunks` for oracle context if a task references them.
Filter version bumped from 1.0 to 1.1.

## 2026-05 - Gold set policy: split retrieval vs supporting

Initial schema used a single `gold_chunks` field for both retrieval
scoring and oracle/rubric context. This conflated two distinct
questions: what the retriever should find from the query, and what
chunks the rubric needs to score the response.

Schema updated to:
- `gold_chunks`: oracle/rubric context (broader)
- `retrieval_gold_chunks`: retrieval scoring target (narrower)
- Defaults to `gold_chunks` if omitted (verification tasks usually
  collapse to one set)
- `gold_chunks_by_format` and `retrieval_gold_chunks_by_format`
  per-format overrides available

Rationale: for slot-filling tasks the scenario can introduce entities
(e.g. the bearer class) that are not discoverable from the query
alone. Including such chunks in `retrieval_gold_chunks` would
artificially cap achievable recall.

## 2026-05 - Primary answer chunk annotation

Added optional `primary_answer_chunk` field to slot-filling task
schema. Identifies the single chunk that most directly answers the
query. Not used in headline metrics; reported separately in error
analysis to surface within-cell ranking quality that unweighted MRR
obscures (e.g. cases where one format ranks the answer at rank 4 and
another at rank 1 while both score MRR = 1.0 against the broader
gold set).

## 2026-05 - Multi-trial post-retrieval protocol

Added `--n-trials` to `run_experiment.py`, default 3. Seeds pinned in
`config.POSTRETRIEVAL_SEEDS = [20260529, 20260530, 20260531]`.
`trial_idx` zero-based: 0 -> 20260529, 1 -> 20260530, 2 -> 20260531.
Manifest records seeds and trial-to-seed mapping.

Rationale: OpenAI does not guarantee bit-exact reproducibility at
temperature 0 with fixed seed (documented "mostly deterministic"
behavior). Recent LLM evaluation literature (HELM, Sclar et al.)
treats multiple-trial protocols as standard. N=3 chosen as
defensible minimum within budget. Retrieval remains single-trial
because the retrieval pipeline (embedding + FAISS flat index) is
fully deterministic.

## 2026-05 - Cost and diagnostic recording

`postretrieval_raw.csv` now records `prompt_tokens`,
`completion_tokens`, `total_tokens`, `system_fingerprint`, and
`model_returned` per call. `pricing.py` computes cost from token
counts against a pinned 2026-06-07 pricing snapshot. Manifest
includes `cost_summary` per trial directory. Recording tokens (not
USD directly) so cost can be recomputed against any later pricing
snapshot.

## 2026-05 - Slot-filling prompt v1 deprecated, v2 in progress

Pilot post-retrieval surfaced two issues in
`slot_filling_system_v1.txt`:
- References "Quality or QuantityValue" as the intermediate node
  type. IDO's actual class is `QualityDatum` (with
  `ScalarQuantityDatum` for scalar measurements). The mismatched
  terminology biased models toward incorrect supporting-chunk
  citations.
- Uses `lis:Quality` as the example for the class field. Quality is
  the partial-credit alternative to PhysicalQuantity in the rubric,
  so the example primes models toward the less-specific answer.

To be fixed in v2: replace QuantityValue reference with generic
"intermediate node (such as a Quality, Datum, or measurement-value
node)"; replace `lis:Quality` example with a non-rubric class like
`lis:Activity`.

## 2026-05 - T02 retrieval gold set tightened

Initial T02 gold set was [lis:hasPhysicalQuantity, lis:hasQuality,
lis:PhysicalQuantity, lis:Quality, lis:PhysicalObject]. Pilot
retrieval showed no format retrieved lis:Quality or lis:PhysicalObject
across multiple runs. The query targets a property; the broader
class chunks are rubric context, not retrieval targets.

`retrieval_gold_chunks` for T02 reduced to [lis:hasPhysicalQuantity,
lis:hasQuality, lis:PhysicalQuantity]. `gold_chunks` retained the
broader set for oracle/rubric context.

## 2026-05 - T05 gold set revised after PCA cross-check

Cross-referenced T05 against PCA online IDO page and local LIS-14
v4.2 FDIS source. The gold rubric used the generic `QualityDatum`
class, but the more precise IDO class for a scalar measured value
like "5 bar" is `ScalarQuantityDatum` (subclass of QualityDatum)
with `datumValue` and `datumUOM` slots.

`gold_chunks` for T05 extended to include `lis:ScalarQuantityDatum`
and `lis:datumValue`. `QualityDatum` retained as partial-credit
alternative for the intermediate-node slot.

Version note: local source is LIS-14 v4.2 FDIS (April 2026); PCA
online page is v4.0 (Proposed DIS, November 2024). The relationships
exercised by T05 verified consistent across both versions.

## 2026-06 - Pilot post-retrieval: ELOT-flat structural-encoding issue surfaced

> **[RETRACTED 2026-08-04 — see the 2026-08-04 (c) WI-8 entry.]** The observation
> below was accurate *at the time* (before the 2026-07-02 loader change), but the
> claim built on it no longer holds and the situation is now **inverted**: since
> 2026-07-02 the flat arm carries the explicit `- SubClassOf ::` axiom (0/14 gold
> chunks missing it) and it is **`elot-org-ancestors`** that lacks an explicit
> statement (12/14 missing, encoding subsumption as heading depth). The T04
> decline now occurs on the *nested* arm, not the flat one. The framing of flat
> as "a controlled ablation that strips the heading path" is retracted: the pair
> varies **encoding style**, not the presence of the heading path, so no claim
> about the heading path per se can be drawn from it. Prompted by the WI-5 audit
> (`experiment/T04_gold_chunk_audit.md`). Original text preserved below for
> provenance — do not cite it.

~~T04 (Function ⊑ Capability, oracle condition, ELOT-flat) returned
"undetermined" with reasoning that the ontology content does not
specify any relationship between Function and Capability. The model
is correct: ELOT-flat strips the heading path that encodes subclass
structurally, and the flat chunk for `lis:Function` contains no
explicit `SubClassOf` axiom.~~

~~Decision (pending supervisor sign-off): treat ELOT-nested as the
faithful ELOT representation and ELOT-flat as a controlled ablation
that strips the heading path to measure what structural encoding
contributes. Headline format comparison reports turtle/omn/elot
(using nested for elot); ELOT-flat reported in a separate
ablation section.~~

## 2026-06 - Pilot post-retrieval: slot-filling prompt ambiguity

GPT-4o on T02 (steel bar / mass scenario) consistently predicts
`lis:PhysicalQuantity` as the class instead of `lis:PhysicalObject`.
The model is interpreting "the scenario entity" as the quality
(mass) rather than the bearer (steel bar). The slot-filling prompt
does not disambiguate which entity in a two-entity scenario is the
subject. This causes 0% exact-match across all slot-filling cells
and suppresses format effects.

Fix in progress: prompt v2 to specify "the subject of the scenario,
the entity to which other entities are being attached."

## 2026-06-14 - Slot-filling prompt v3 (scenario-subject disambiguation)

Applied the prompt fix for the two-entity ambiguity. The new prompt is `slot_filling_system_v3.txt`. `config.SYSTEM_PROMPTS["slot_filling"]` now points at
v3; the per-trial manifest records the filename automatically.

Change vs v2: the "class" slot now models the subject of the scenario
- "the entity to which the other entities (qualities, quantities,
measured values) are being attached - the bearer, not the thing borne",
with a generic "X has a Y -> model X" example. The example is kept
abstract on purpose: using the actual T02 (steel bar / mass) or T05
(pump / pressure) scenarios as worked examples would leak the answers
to graded tasks, the same priming concern that removed `lis:Quality`
as the class example in v2.

Empirical motivation (postretrieval-trial-1): GPT-4o predicted
`lis:PhysicalQuantity` for T02's class across turtle oracle/retrieved
and elot cells, where the bearer-first gold is `lis:PhysicalObject`.

## 2026-06-14 - Slot-filling partial-credit policy for the rerun

`grading.py` scores each of the six slot fields as a binary exact
entity-id match; `partial_credit` is the fraction of those six fields
correct (response-level graceful degradation), not a within-slot
semantic score. The "less specific = partial" notes on T02
(hasQuality vs hasPhysicalQuantity) and T05 (QualityDatum vs
ScalarQuantityDatum) describe a within-slot scheme that is NOT
implemented.

Decision for this rerun: keep binary per slot. Full credit only for
the precise answer (`lis:hasPhysicalQuantity`, intermediate-node
support `lis:ScalarQuantityDatum`); the less-specific alternate scores
zero on that field but the response can still earn 5/6 on the others.
A within-slot partial scheme (acceptable-alternates-with-weight) is
deferred to the 30-task benchmark; it needs a tasks-schema + grader
change, not worth the regression risk immediately before the rerun.

## 2026-06-14 - T05 class slot made bearer-first 

The slot-filling class slot identifies the IDO class of the subject
(the bearer being modelled), consistent across T02 and T05. T02 was
already bearer-first (gold_class = lis:PhysicalObject, the steel bar);
T05 was not (gold_class and gold_supporting_chunks.class were
lis:PhysicalQuantity, the quality side). Both now set to
lis:PhysicalObject (the pump). property (hasPhysicalQuantity),
intermediate_node (true), and the intermediate-node support
(ScalarQuantityDatum) are unchanged.

## 2026-07-02 - elot-org (flat) now carries the 1-hop SubClassOf axiom

Redefined the `elot-org` (flat) format: each CLASS chunk now has its
immediate named superclass materialised as a single appended
`- SubClassOf :: <parent>` line. `EntityBasedElotOrgLoader` gains
`include_parent_axiom` (default True); the nearest level>=3 ancestor
that resolves to an entity id is the parent, and top-level classes get
nothing (matching Turtle/OMN, which give them no named superclass).
Object/data/annotation properties are untouched -- they already carry an
explicit `- SubPropertyOf ::` in the ELOT source. `elot-org-ancestors`
is unchanged: its prepended heading path already names the parent, so
the axiom is suppressed when ancestor headings are on. Loader version
`elot-org` 2.0 -> 3.0.

Rationale: directly resolves the 2026-06 ELOT-flat finding (T04,
Function subclass-of Capability). Previously the flat chunk for
`lis:Function` contained no `SubClassOf` axiom -- ELOT encodes the
named superclass only through heading nesting, which the flat chunker
strips -- so flat elot was structurally handicapped relative to
turtle/omn, which state the immediate superclass natively. Flat elot is
no longer a "no subclass info" ablation; it is the verbatim slice plus
the same 1-hop superclass the other formats carry. The
flat-vs-`elot-org-ancestors` contrast now isolates exactly one variable:
1-hop explicit axiom vs full ancestor heading path.

> **[CLAIM RETRACTED 2026-08-04 — see the 2026-08-04 (c) WI-8 entry.]** "Isolates
> exactly one variable" is wrong. The change described in this entry altered the
> flat arm on **two** dimensions relative to nested: the heading path is absent
> *and* an explicit axiom is present. Either variable explains T04, so the pair
> cannot attribute an effect to the heading path. The contrast is reframed as
> **explicit axiom statement vs structural (heading-depth) encoding of
> subsumption**; claims about the heading path per se are out of scope. Evidence:
> explicit statement missing on 12/14 gold chunks under `elot-org-ancestors` vs
> 0/14 under every other arm (WI-5 audit, `experiment/T04_gold_chunk_audit.md`).
> The rest of this entry — what the loader change did and why — remains accurate.

Impact: elot-org chunk content changes, so its FAISS index and any
prior elot-org results must be regenerated; the index cache rebuilds
automatically on content-checksum change. The production assistant
(which loads elot-org via loader defaults) also now emits the axiom.

Class chosen by checking LIS-14-for-FDIS (v4.2):
- lis:FunctionalObject carries the canonical example "A pump, a
  hammer, a password", but it is `subClassOf lis:Object`, not
  PhysicalObject.
- lis:hasPhysicalQuantity (T05's gold property) has
  `rdfs:domain lis:PhysicalObject`. FunctionalObject does not satisfy
  that domain; lis:PhysicalArtefact (subClassOf PhysicalObject) would,
  but using it for the pump while T02 uses PhysicalObject for the
  steel bar would reintroduce a cross-task inconsistency.
- lis:PhysicalObject is bearer-first, in the property's domain,
  parallel to T02, and already in T05 gold_chunks (resolves in all
  formats, available as oracle context and a citable support chunk).

PhysicalArtefact is recorded here as the more-specific defensible
alternative if a later revision wants per-task specificity; not used
for the pilot.

## 2026-06-14 - Bearer-class grading

Refines the binary partial-credit note above for the class slot. The
slot-filling class slot tests "can the model identify a defensible
bearer class?", not "the single most specific class". Different
ontologists reasonably pick different specificity levels, so the
grader now accepts a set of equivalent bearer classes at full credit, rather than only the canonical answer.

Implementation (explicit accept-list, not subtree traversal, so
classes outside the PhysicalObject subtree can be accepted too):
- `schemas.Task` gains `gold_class_accept: list[str] | None`. The
  canonical `gold_class` is always accepted implicitly;
  `Task.accepted_class_ids()` returns canonical + accepts.
- `grading.grade_slot_filling` scores `class_correct` and
  `support_class_correct` against the accept set (the citation for an
  accepted class is consistent with picking it). `property`,
  `intermediate_node`, and their supports stay exact-match.
- `validate_gold_chunks_resolve` checks accept classes resolve in all
  four formats.

Accept-lists (chosen by walking the FDIS subclass hierarchy; accept
classes are correct typings of the subject as a physical object):
- T02 (steel bar): gold_class lis:PhysicalObject; accept
  lis:PhysicalArtefact (made by deliberate activity),
  lis:InanimatePhysicalObject (not living).
- T05 (pump): gold_class lis:PhysicalObject; accept
  lis:PhysicalArtefact, lis:InanimatePhysicalObject, and
  lis:FunctionalObject (the source's "a pump" example class). Class and
  property slots are graded independently, so accepting FunctionalObject
  does not assert a domain-consistent pairing with hasPhysicalQuantity.

Deliberately excluded as re-framings of the subject rather than typings
of it: Compound (material composition), Phase (state of matter), Feature
(a part/surface), System (multi-part functional assembly). Available to
add if a more forgiving policy is wanted.

Scope: grading tolerance only. Accept classes are NOT added to
`gold_chunks`, so oracle context still shows the canonical class; the
accept-list mainly bites in the retrieved condition (or if a model
brings a defensible class from the shown chunks). Per-slot grading
stays binary; "specificity vs correctness" would be a separate task
type if ever wanted.

## 2026-07-02 - Supporting-chunk citations made nullable

`SupportingChunks.class` and `.property` are now `str | None`
(`intermediate_node` already was). Llama 3.1 8B often returns `null`
for a citation instead of omitting it, and a required `str` rejected
that - one null citation raised a ValidationError that failed the
whole response at parse time, throwing away the slots the model got
right. Grading is unchanged: `_norm(None)` is "", so a null citation
just scores as an uncited (wrong) slot.

## 2026-07-02 - Slot-filling prompt v4 (flat-schema lock)

Bumped `SYSTEM_PROMPTS["slot_filling"]` to `slot_filling_system_v4.txt`.
v3's scenario-subject text is unchanged; v4 only hardens the output
format. On oracle cells Llama 3.1 8B ignored the flat schema and
returned JSON-LD (`{"@context": ..., "@type": "lis:Pump", ...}`), so
none of the five keys were present and the response didn't parse.
GPT-4o followed v3 fine - v3 just wasn't firm enough for the 8B model.

v4 adds: an "exactly these five top-level keys" instruction, an
explicit ban on JSON-LD/RDF and `@context`/`@type`/etc., and a
negative example. The negative example uses placeholder `ex:` prefixes,
not the T05/T02 answers, so it doesn't leak gold entities (same reason
v2 dropped the `lis:Quality` example).

Verified at the code level only (v4 parses the flat schema, still
rejects JSON-LD). Not yet tested against live Llama - no Ollama on this
machine.

## 2026-07-02 - Pilot T05 Llama oracle data excluded from format comparisons

Llama's T05 oracle parse failures in postretrieval-trial-2 are an
instruction-following problem (JSON-LD instead of the flat schema), not
a format effect - the context on those cells is fine. Including them
would read a prompt artefact as a format signal, so they're excluded
from the format comparisons. GPT-4o T05 data is unaffected.

## 2026-07-16 - Property grading uses strict equality by design (no gold_property_accept)

The slot-filling rubric grades the property slot with strict equality only.
There is no gold_property_accept mechanism analogous to gold_class_accept.
This is deliberate: for classes, multiple bearer classes can be genuinely
equivalent (e.g. PhysicalObject / PhysicalArtefact / FunctionalObject for a
pump), so an accept set is appropriate. For properties in IDO's Quality/Datum
pattern, lis:hasQuality and lis:hasPhysicalQuantity are not interchangeable —
choosing the superclass when the more specific subproperty exists is a
specificity failure that the task is designed to detect. The task intentionally
tests subproperty resolution. T02 and T05 notes have been updated to remove
misleading "partial credit" language that implied the property slot is
fractionally scored for superclass picks; it is not.

## 2026-07-16 - T05 Llama oracle re-run under v4 + nullable schema (postretrieval-trial-3)

Re-ran T05 × oracle × slot_filling × Llama (llama3.1:8b-instruct-q8_0) across
all 5 formats, 3 seeded trials. Parse errors are resolved: the flat-schema lock
in v4 eliminated the JSON-LD output. All 5 formats scored exact=0.000,
partial=0.333 (1 of 3 slots correct) with std=0.000 across all trials and
metrics. The format made no difference — Llama returned the same answer
regardless of serialisation, and it was consistently partially correct.
These cells replace the excluded trial-2 T05 Llama oracle rows in any
format comparison that includes local models.
