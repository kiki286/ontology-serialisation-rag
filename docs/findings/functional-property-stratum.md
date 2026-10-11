# Functional-property stratum — A1–A3 findings and verdict

**Date:** 2026-08-19 · **Scope:** Part A of the functional-property / pre-run spec.
**Cost:** zero API calls. All evidence is ROBOT/HermiT against the canonical Turtle.

**Verdict: STRATUM VIABLE.** Both `lis:datumUOM` and `lis:datumValue` items can be
authored under the existing `contradicted` convention, with the existing gate, and
without touching `verification_system_v1.txt`. No convention extension is required and
no supervisor sign-off is triggered — **provided the statement is authored as a T-Box
claim** (§A3). The reallocation contingency in A4 does not apply.

> **Tooling note.** ROBOT was not installed on this machine. ROBOT 1.9.10 was downloaded
> as a local `robot.jar`; its SHA256 is
> `16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105`, which **matches the
> pin recorded in `scripts/tangle_ofn.py`** exactly, and the local JDK is Temurin 16.0.2 —
> the same toolchain that produced the committed `.ofn`. Set `ROBOT_JAR` to that path to
> reproduce anything below.

---

## A1 — Does the ROBOT gate accept property-level axioms?

**No, not directly — but functionality has a class-expression route that the unmodified
gate does accept.** This is the material difference from `unasserted_inverse`.

Five phrasings were put through `scripts/verify_undetermined_items.explain_entailment`
(the real gate function, not a reimplementation). All fail to parse:

| phrasing | result |
|---|---|
| `lis:datumUOM rdf:type owl:FunctionalProperty` | parse error at `rdf:type`, col 16 |
| `Functional: lis:datumUOM` | parse error |
| `lis:datumUOM Characteristics: Functional` | parse error at `Characteristics:`, col 14 |
| `FunctionalObjectProperty(lis:datumUOM)` | parse error at col 1 |
| `lis:datumValue rdf:type owl:FunctionalProperty` | parse error at `rdf:type`, col 16 |

The parser reports it expected one of `SubClassOf:`, `DisjointWith:`, `EquivalentTo:`,
`or`, `and` — i.e. it accepts **class-expression axioms only**, confirming the same wall
that removed `unasserted_inverse`.

**However**, functionality is expressible *as* a class expression, and that form parses
and is entailed:

| axiom | entailed |
|---|---|
| `owl:Thing SubClassOf: lis:datumUOM max 1 owl:Thing` | **True** |
| `owl:Thing SubClassOf: lis:datumValue max 1 rdfs:Literal` | **True** |
| `owl:Thing SubClassOf: lis:hasContentPart max 1 owl:Thing` *(non-functional control)* | False |
| `owl:Thing SubClassOf: lis:hasPart max 1 owl:Thing` *(control)* | False |
| `owl:Thing SubClassOf: lis:uomOfDatum max 1 owl:Thing` *(control)* | False |

The negative controls are the point: the test **discriminates**. It returns True for
exactly the two functional properties and False for non-functional ones, so a True is
evidence of functionality rather than an artefact of the phrasing.

**Scoping correction worth recording.** A1's premise slightly conflates two gates.
`robot explain --axiom` is the gate for the **undetermined** class (two-sided
non-entailment). The **contradicted** class is gated by a different route entirely —
`robot reason`, asserting the statement and checking that a named class becomes
unsatisfiable (`scripts/generate_bare_disjointness_candidates.py:158-201`). Since
`functional_property` is a *contradicted* mechanism, the `explain --axiom` wall was never
on its critical path. A1's answer is therefore doubly favourable: the wall is real, it
does not apply here, and a route through it exists anyway.

*(Incidental: `inv` appears in the parser's expected-token list, which suggests the
`unasserted_inverse` drop may deserve a re-check. Out of scope here — flagged, not acted
on.)*

---

## A2 — Does the adopted `contradicted` convention cover it?

**Yes for the T-Box form, no for the A-Box form.** The convention needs no extension; the
authoring choice does the work. Measured against the canonical graph:

| # | added assertion | reasoner outcome | covered? |
|---|---|---|---|
| 0 | *(baseline, untouched)* | consistent, 0 unsatisfiable | — |
| 1 | A-Box: one datum, two UOMs, **no** `differentFrom` | **consistent, 0 unsatisfiable** | no violation at all |
| 2 | A-Box: same **with** `owl:differentFrom` | **ontology INCONSISTENT**, 0 unsatisfiable classes | **no** |
| 3 | T-Box: `QualityDatum ⊑ datumUOM min 2` | consistent, **`lis:QualityDatum` + `lis:ScalarQuantityDatum` unsatisfiable** | **yes** |
| 4 | T-Box: `QualityDatum ⊑ datumValue min 2` | consistent, **same two classes unsatisfiable** | **yes** |

Three things follow.

**Case 1 is the trap.** Without an explicit `owl:differentFrom`, OWL's lack of a
unique-name assumption means the reasoner simply infers the two units are the same
individual. The naive reading of "a datum with two units" is **not a violation**. Any
A-Box phrasing must assert distinctness explicitly or it tests nothing.

**Case 2 is the one the convention does not reach.** It produces *ontology inconsistency*,
not class unsatisfiability — exactly the outcome the spec predicted. The existing checker
looks for `subject ∈ unsatisfiable`, which is empty here, so it would raise "ROBOT did not
establish that … becomes unsatisfiable". Authoring the item this way **would** require an
extension, and therefore supervisor sign-off.

**Cases 3–4 satisfy the convention verbatim.** The convention is "asserting the statement
renders some class unsatisfiable"; asserting the T-Box form renders `lis:QualityDatum`
unsatisfiable. Same reasoner-outcome *shape* as the bare-disjointness items already
adopted. `lis:ScalarQuantityDatum` also falls, being a subclass of an unsatisfiable class
— expected collateral, and the bare-disjointness items behave the same way.

Negative control, again the load-bearing part: asserting `min 2` with a **non**-functional
property (`lis:hasContentPart`, `lis:hasPart`) leaves **zero** classes unsatisfiable. The
unsatisfiability in cases 3–4 is caused by functionality and nothing else.

**Conclusion: no extension is required, and stop condition 1 does not fire** — on the
condition that the item is authored as T-Box. That is an authoring constraint, not a
convention change.

---

## A3 — Can a violation be phrased as a T-Box statement?

**Yes, and two viable phrasings exist.** Both fit the `verification` schema
(`benchmark/schema.md`) with no new fields and no prompt change. Note the schema requires
`axiom`/`negated_axiom` only for *undetermined* items, so a contradicted
functional-property item needs neither.

Relevant fact: **LIS-14 contains zero `owl:NamedIndividual`s.** It is a pure T-Box. An
A-Box phrasing would require inventing individuals that exist nowhere else in the
benchmark — a second reason beyond A2 to avoid that route.

### Candidate 1 — universal (safest)

> **"Every `lis:QualityDatum` has at least two different units of measure."**

- Formalises to `QualityDatum ⊑ datumUOM min 2`, which is **exactly** the assertion in A2
  case 3 — prose and asserted axiom coincide, no interpretive gap.
- Satisfies the convention *verbatim*; no reformulation, no sign-off.
- Matches the dominant `Every lis:X is a lis:Y` statement template used by 20+ items.
- Inherits the **same** open-world vacuity caveat already accepted for bare disjointness
  (`X` may be empty, so strict negation is not entailed). This is the known,
  already-adopted caveat, not a new one — see the note at
  `generate_bare_disjointness_candidates.py:218`.
- Weakness: stilted prose, and a model could plausibly read "the ontology doesn't
  *require* two units" as grounds for `undetermined`.

### Candidate 2 — existential, T03-style (recommended)

> **"A single quality datum carries two different units of measure at once."**

- Formalises to the claim that `QualityDatum ⊓ (datumUOM min 2)` is non-empty;
  contradicted because that class is provably empty. Verified through the **existing,
  unmodified** `explain_entailment`:
  `lis:QualityDatum and (lis:datumUOM min 2 owl:Thing) SubClassOf: owl:Nothing` →
  **entailed=True**, while the non-functional control (`lis:hasContentPart`) → **False**.
- **Formally stronger than Candidate 1**: no vacuity caveat, since "this class is empty"
  is a strict entailment.
- Natural modelling prose, and **T03 is the precedent** — its statement ("A maintenance
  procedure document `lis:concretizes` a printed paper copy of itself") is likewise an
  indefinite-singular sentence graded against T-Box entailment. So this is not a new kind
  of item.
- Cost: it establishes unsatisfiability of an *anonymous class expression* rather than of
  a *named class* after assertion. Both are class-level unsatisfiability, but it is a mild
  reformulation of the convention's letter. **This is the author's call** — if it is judged
  a reformulation, Candidate 1 is the no-extension fallback that needs no such judgement.

**Recommendation: Candidate 2 for prose quality and formal strength; Candidate 1 if strict
adherence to the convention's exact wording is preferred.** Either way the stratum is
authorable. The `lis:datumValue` item mirrors whichever is chosen ("…two different literal
values at once").

---

## A4 — Verdict and caveat

**Stratum viable.** Gate route: the contradicted class's unsatisfiability gate
(`robot reason`), which both candidates pass; no `explain --axiom` dependency and no
convention extension. The 7 remaining contradicted items keep their planned four-tier
split (3 bare disjointness / 3 direct domain-range / 2 composed / **2 functional
property**). **No reallocation is proposed** — the contingency did not trigger.

As of commit `34e87b5` the slot-filling half is complete (30/30), so **these 7 items are
the only authoring work left** in the 60-task benchmark. Verification currently stands at
10 supported / 10 undetermined / 3 contradicted; the 7 take the contradicted class to 10
and the set to the intended 10/10/10.

**One caveat the author should weigh.** Both drafts were run through
`scripts.check_authoring_candidate`: `gate_verdict: pass`, but the seven-format
`recoverability_profile` is **uniform (all true)** for both, because
`rdf:type owl:FunctionalProperty` is materialised in every serialisation. This confirms the
2026-08-14 measurement ("the two functional properties were uniform by construction"). The
global uniform-profile cap was dropped on 2026-08-14, so this is permitted — but these two
items **carry no format-effect signal by construction** and will contribute only to the
contradicted-class label balance. Worth stating explicitly in the methods chapter rather
than leaving a reader to infer it.

## Reproduction

```bash
export ROBOT_JAR=/path/to/robot.jar
./.venv/Scripts/python.exe -m scripts.check_authoring_candidate <draft.yaml>
```

A1/A2 probes were scratch scripts (not committed); every result above is reproducible from
`explain_entailment` and `robot reason` as cited.

## Methodology-log entries to write (flagged, not written)

1. **ROBOT gate is class-expression-only; functionality has a class-expression route.**
   Record the parse-failure table and the discriminating `max 1` test with its negative
   controls, plus the scoping correction that the contradicted class never used that gate.
2. **Functional-property violations: A-Box ⇒ inconsistency, T-Box ⇒ unsatisfiability.**
   Record the five-case table, the no-UNA trap (case 1), and that the convention is
   satisfied without extension provided items are authored T-Box.
3. **Functional-property items have uniform recoverability profiles by construction** —
   permitted since the 2026-08-14 cap removal, but they contribute no format signal.
