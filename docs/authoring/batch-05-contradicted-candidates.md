# Batch 05 — Final Contradicted Candidates

**Candidate pool for human selection. These are not finished benchmark items.** No item was
selected, no wording was finalised, and nothing was written to `tasks_60.yaml`, `tasks.yaml`,
any validator, or any schema.

**Pool size: 32 candidates generated, 27 surviving the gates**
(24 `composed_domain_range_disjointness`, 3 `functional_property`,
0 `direct_domain_range`). Seven items are to be selected from this pool.

**Two stop conditions fire (§8.2).** `direct_domain_range` yields **0** candidates against a
required 3 (threshold 6), and `functional_property` yields **3** against a required 2
(threshold 4). Both are reallocation decisions for the author; §1 and §6 below give the evidence.
Stop conditions 1, 3, 4, 5 and 6 do **not** fire.

---

## 1. Enumeration counts per stratum, before and after gates

### 1.1 The enumeration space

Measured from the canonical Turtle (`data/LIS-14-for-FDIS (1).ttl`) with rdflib:

| quantity | count |
| --- | ---: |
| named classes | 50 |
| object properties / data properties | 102 / 3 |
| `rdfs:domain` axioms (4 of them union-valued) | 37 |
| `rdfs:range` axioms (1 of them union-valued) | 40 |
| asserted pairwise `owl:disjointWith` | 15 |
| `owl:AllDisjointClasses` groups (all 12 member pairs already covered pairwise) | 3 |
| `owl:FunctionalProperty` declarations | 2 (`lis:datumUOM`, `lis:datumValue`) |

Enumerating every (domain-or-range axiom × named class) pair where the class is provably disjoint
from the constraint class gives the raw violation space:

| family | 0 extra subsumption hops | 1 hop | 2 hops | total |
| --- | ---: | ---: | ---: | ---: |
| domain violation (`X ⊑ ∃P.⊤`, `X ⊥ domain(P)`) | 60 | 402 | 847 | 1309 |
| range violation (`X ⊑ ∃P.Y`, `Y ⊥ range(P)`) | 50 | 361 | 1089 | 1500 |

“0 extra hops” means the disjointness axiom relates the statement’s own class and the
domain/range class directly, with no intervening `rdfs:subClassOf` step. The 0-hop pool spans
**29 distinct properties** (domain family) and **24** (range family). All work below is drawn from
the 0-hop pool; the 1- and 2-hop families differ only by adding subsumption steps to reach the same
15 disjointness axioms, so they change nothing in the analysis of §1.2.

### 1.2 Gate results

| stratum | required | enumerated | shortlisted | `robot reason` pass | gate `pass` | after `states_axiom` + artefact rejections |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bare_disjointness` | 0 | — | — | — | — | complete (T06–T08) |
| `direct_domain_range` | 3 | **0** | 0 | — | — | **0** |
| `composed_domain_range_disjointness` | 2 | 110 (0-hop) | 26 | 26 | 26 | **24** |
| `functional_property` | 2 | 2 axioms → 6 phrasings | 6 | 6 | 6 | **3** |

Rejections: 1 composed (`B05-R15`, `states_axiom`) + 1 composed dropped on a gate artefact
(`B05-D08`, see §9.1) + 3 functional (`states_axiom`).

---

## 2. Why `direct_domain_range` is empty (§6.6)

**Finding: the stratum as defined in §3.2 of the brief cannot be populated from LIS-14. Not one
candidate. This is a property of the ontology, not of the search.**

§3.2 requires a domain/range violation whose unsatisfiability follows **without** composing a
separate disjointness axiom. Two independent lines of evidence say no such violation exists.

**Empirical.** Every one of the **108** object-property assertions in the 0-hop pool was asserted
into a copy of the canonical graph with all `owl:disjointWith` triples and all
`owl:AllDisjointClasses` groups removed, and reasoned with ROBOT 1.9.10 / HermiT. Run in 12 chunks
of 9; by monotonicity (adding axioms can only add unsatisfiability) a satisfiable chunk certifies
every assertion in it:

```
0-hop object-property assertions in pool: 108
chunk  1 (9 assertions) stripped -> unsat=[] rc=0 inconsistent=False OK
...
chunk 12 (9 assertions) stripped -> unsat=[] rc=0 inconsistent=False OK
FAILING CHUNKS: none
```

The same 26 shortlisted candidates were also run individually: **26/26 unsatisfiable on the
canonical graph, 26/26 satisfiable with disjointness stripped.** The strip is load-bearing, not a
no-op — control: asserting T06’s `lis:SpatialLocation rdfs:subClassOf lis:Site` gives
`[lis:LineInSpace, lis:PlaneInSpace, lis:PointInSpace, lis:SpatialLocation, lis:VolumeInSpace]`
unsatisfiable on the canonical graph and `[]` on the stripped graph. Baseline for both graphs is 0
unsatisfiable.

**Structural.** LIS-14 contains no construct capable of producing a contradiction other than
disjointness and functionality. The complete predicate inventory has no `owl:complementOf`, no
`owl:disjointUnionOf`, no `owl:propertyDisjointWith`, no `owl:maxCardinality` /
`owl:maxQualifiedCardinality`, no `owl:AsymmetricProperty` or `owl:IrreflexiveProperty`, no
`owl:AllDifferent`, no datatype range with facets, and no named individuals at all. What remains is
15 `owl:disjointWith`, 3 `owl:AllDisjointClasses`, 2 `owl:FunctionalProperty`, and one
`owl:allValuesFrom` (`lis:Event ⊑ ∀lis:hasTemporalExtent.lis:InstantRegion`, which is not
contradiction-inducing on its own because `lis:InstantRegion` and `lis:IntervalRegion` are not
disjoint). `rdfs:domain` and `rdfs:range` are purely type-inferring: on their own they add types,
never a clash. So the only route from a domain/range violation to unsatisfiability runs through a
disjointness axiom — which is the definition of §3.3, not §3.2.

**Consequence.** The 3 items allocated to `direct_domain_range` have to go somewhere. The `composed`
stratum can absorb them (24 surviving candidates across 23 distinct properties), but that is
a reallocation decision for the author, not one this pass makes. Note also that the §3.2/§3.3 split
was, on this evidence, never a real split in this ontology: **every** domain/range item is composed.

---

## 3. Consolidated candidate list

Shared across every candidate below, so it is stated once rather than 32 times:

- `reasoning_type: structural` — each requires composing at least two axioms (a domain/range or
  functionality axiom with a disjointness axiom or a cardinality reading). None is a single asserted
  axiom in a single chunk, so `direct_assertion` is wrong; none turns on reading a definition, so
  `definitional` is wrong.
- `query_source: label` — every draft query names its property and classes by IRI, following
  T06–T08. Paraphrase variants are available if the author wants to balance `query_source`, but
  drafting them was out of scope here.
- `gold_label: contradicted`; `task_type: verification`.
- **Every candidate is non-vacuous.** For each, `X and (P some Y) SubClassOf: owl:Nothing`
  (respectively `X and (P min 2 …)`) is entailed by the *unmodified* canonical graph, checked with
  the existing unmodified `explain_entailment`, while `X SubClassOf: owl:Nothing` is not. The
  open-world vacuity caveat carried by the bare-disjointness items **does not apply to any candidate
  in this batch**: what is proved empty is the conjunction, not the subject class, so the result
  holds whether or not the subject class has instances. Per §2 of the brief this makes every one of
  these strictly stronger than T06–T08.

### 3.1 `direct_domain_range` — 0 candidates

Empty. See §2.

### 3.2 `composed_domain_range_disjointness` — 26 enumerated, 24 surviving

| id | draft statement | unsat class (ROBOT) | collateral | prose | link-1 leak | uniform | gold | reuse flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B05-R01 | Every lis:PhysicalObject lis:residesIn a lis:SpatialLocation. | `lis:PhysicalObject` | +11 | **toward** | yes | true | 4 | T06 pair |
| B05-R02 | Every lis:PhysicalObject lis:hasSpatialExtent a lis:Site. | `lis:PhysicalObject` | +11 | **toward** | yes | true | 4 | T06 pair |
| B05-R03 | Every lis:InformationObject lis:hasContentPart a lis:PhysicalObject. | `lis:InformationObject` | +5 | away | yes | true | 3 | T08 pair |
| B05-R04 | Every lis:Location lis:hasSubLocation a lis:PhysicalObject. | `lis:Location` | +6 | away | yes | true | 3 | — |
| B05-R05 | Every lis:Activity lis:hasParticipant a lis:Temporal. | `lis:Activity` | +2 | away | yes | true | 4 | — |
| B05-R06 | Every lis:Object lis:hasQuality a lis:Potential. | `lis:Object` | +28 | away | yes | true | 4 | — |
| B05-R07 | Every lis:Activity lis:hasTemporalRegion a lis:SpatiotemporalRegion. | `lis:Activity` | +2 | **toward** | yes | true | 4 | — |
| B05-R08 | Every lis:Activity lis:hasSpatiotemporalExtent a lis:TemporalRegion. | `lis:Activity` | +2 | away | yes | true | 4 | — |
| B05-R09 | Every lis:Object lis:representedIn a lis:PhysicalObject. | `lis:Object` | +28 | neutral | **no** | true | 4 | T08 pair |
| B05-R10 | Every lis:Site lis:siteDeterminedBy a lis:Location. | `lis:Site` | +0 | away | yes | true | 4 | — |
| B05-R11 | Every lis:Object lis:locatedRelativeTo a lis:Temporal. | `lis:Object` | +28 | away | yes | true | 3 | — |
| B05-R12 | Every lis:PhysicalObject lis:hasArrangedPart an lis:InformationObject. | `lis:PhysicalObject` | +11 | neutral | **no** | true | 3 | T08 pair |
| B05-R13 | Every lis:ActivityProfile lis:profileOfQuality a lis:Potential. | `lis:ActivityProfile` | +0 | away | yes | true | 4 | — |
| B05-R14 | Every lis:Potential lis:realizedIn a lis:TemporalRegion. | `lis:Potential` | +7 | away | yes | true | 4 | — |
| B05-R15 | Every lis:Actual lis:implements an lis:Actual. | `lis:Actual` | +0 | **states_axiom** | yes | true | 3 | — |
| B05-R16 | Every lis:PhysicalObject lis:connectedTo a lis:Location. | `lis:PhysicalObject` | +11 | neutral | **no** | true | 3 | — |
| B05-D01 | Every lis:PhysicalObject lis:isAbout an lis:Activity. | `lis:PhysicalObject` | +11 | away | yes | true | 4 | T08 pair |
| B05-D02 | Every lis:SpatialLocation lis:siteOf an lis:Activity. | `lis:SpatialLocation` | +4 | away | yes | true | 4 | T06 pair |
| B05-D03 | Every lis:Organization lis:hasPhysicalQuantity a lis:PhysicalQuantity. | `lis:Organization` | +0 | neutral | **no** | true | 4 | — |
| B05-D04 | Every lis:Organization lis:hasContentPart an lis:InformationObject. | `lis:Organization` | +0 | away | yes | true | 3 | — |
| B05-D05 | Every lis:Location lis:hasMaterialPart a lis:Compound. | `lis:Location` | +6 | away | yes | true | 4 | — |
| B05-D06 | Every lis:Potential lis:qualityQuantifiedAs a lis:QualityDatum. | `lis:Potential` | +7 | away | yes | true | 4 | — |
| B05-D07 | Every lis:TemporalRegion lis:hasActivityPart an lis:Activity. | `lis:TemporalRegion` | +5 | away | yes | true | 3 | — |
| B05-D08 | Every lis:Organization lis:contains a lis:PhysicalObject. | `lis:Organization` | +0 | away | yes | false | 4 | — |
| B05-D09 | Every lis:Activity lis:temporalRegionQuantifiedAs a lis:TemporalDatum. | `lis:Activity` | +2 | away | yes | true | 4 | — |
| B05-D10 | Every lis:Dependent lis:hasPotential a lis:Potential. | `lis:Dependent` | +18 | away | yes | true | 4 | T07 pair |

“Collateral” is the number of *additional* classes that fall with the named subject (subclasses of
an unsatisfiable class). It is not a defect — T06 behaves the same way, taking 4 subclasses with it —
but a wide blast radius means the assertion invalidates a large slice of the ontology, which the
author may or may not want in a benchmark item.

### 3.3 `functional_property` — 6 enumerated, 3 surviving

| id | draft statement | unsat class (ROBOT) | collateral | prose | link-1 leak | uniform | gold | reuse flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B05-F01 | A single quality datum carries two different units of measure at once. | `lis:QualityDatum` | +1 | **toward** | **no** | true | 2 | — |
| B05-F02 | A single quality datum carries two different literal values at once. | `lis:QualityDatum` | +1 | **toward** | **no** | true | 2 | — |
| B05-F03 | A single scalar quantity datum carries two different units of measure at once. | `lis:ScalarQuantityDatum` | +0 | **states_axiom** | **no** | true | 2 | — |
| B05-F04 | A single scalar quantity datum carries two different literal values at once. | `lis:ScalarQuantityDatum` | +0 | **states_axiom** | **no** | true | 2 | — |
| B05-F05 | A single quality datum carries two different units of measure at once. | `lis:QualityDatum` | +1 | **toward** | **no** | true | 3 | — |
| B05-F06 | A single scalar quantity datum carries two different units of measure at once. | `lis:ScalarQuantityDatum` | +0 | **states_axiom** | **no** | true | 3 | — |

Both `lis:datumUOM` and `lis:datumValue` items are authored **T-Box**, as required: the A-Box form
produces ontology *inconsistency* rather than class unsatisfiability, which the convention does not
reach. No A-Box item was authored. Wording follows the author’s selected Candidate 2 (existential,
T03-style) phrasing.

As the Part A finding predicted, all six functional-property profiles are **uniform (all seven
true)** because `rdf:type owl:FunctionalProperty` is materialised in every serialisation. That is
expected and correct, not a defect — bare disjointness was uniform by construction in the same way.
It does mean these items carry no format-effect signal and contribute only to contradicted-class
label balance.

---

## 4. Per-candidate detail

### 4.1 `composed_domain_range_disjointness`

#### B05-R01

> **Draft statement.** “Every lis:PhysicalObject lis:residesIn a lis:SpatialLocation.”

| field | value |
| --- | --- |
| draft query | “Does every lis:PhysicalObject lis:residesIn a lis:SpatialLocation in IDO?” |
| formal axiom | `lis:PhysicalObject SubClassOf (lis:residesIn some lis:SpatialLocation)` |
| `licensing_axiom` | `lis:residesIn rdfs:range lis:Site`<br>`lis:Site owl:disjointWith lis:SpatialLocation` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:residesIn rdfs:range lis:Site` → every `lis:residesIn` filler is a `lis:Site`. 2. The statement’s filler is a `lis:SpatialLocation`. 3. `lis:Site owl:disjointWith lis:SpatialLocation` → `lis:residesIn some lis:SpatialLocation` is empty, so `lis:PhysicalObject` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:PhysicalObject` (plus 11 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:PhysicalObject and (lis:residesIn some lis:SpatialLocation) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:PhysicalObject SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`toward`** — lis:residesIn naturalLanguageDefinition: “If x ‘resides in’ y, then x is a ‘physical object’, **y is a ‘location’**, and x is located entirely within y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:PhysicalObject`, `lis:Site`, `lis:SpatialLocation`, `lis:residesIn` |
| `retrieval_gold_chunks` | `lis:PhysicalObject`, `lis:SpatialLocation`, `lis:residesIn` — narrower than `gold_chunks`: `lis:Site` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T06 entity pair exactly**; committed entities in gold: `lis:PhysicalObject`, `lis:Site`, `lis:SpatialLocation`, `lis:residesIn` |
| notes | Prose states a WEAKER range (Location) than the axiom (Site), and lis:SpatialLocation IS a lis:Location — so the annotation positively licenses the false statement while the axiom refutes it. Strongest toward candidate in the batch. Counter-pull: the usageNote says “an object x is located in a site y”. |

#### B05-R02

> **Draft statement.** “Every lis:PhysicalObject lis:hasSpatialExtent a lis:Site.”

| field | value |
| --- | --- |
| draft query | “Does every lis:PhysicalObject lis:hasSpatialExtent a lis:Site in IDO?” |
| formal axiom | `lis:PhysicalObject SubClassOf (lis:hasSpatialExtent some lis:Site)` |
| `licensing_axiom` | `lis:hasSpatialExtent rdfs:range lis:SpatialLocation`<br>`lis:SpatialLocation owl:disjointWith lis:Site` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasSpatialExtent rdfs:range lis:SpatialLocation` → every `lis:hasSpatialExtent` filler is a `lis:SpatialLocation`. 2. The statement’s filler is a `lis:Site`. 3. `lis:SpatialLocation owl:disjointWith lis:Site` → `lis:hasSpatialExtent some lis:Site` is empty, so `lis:PhysicalObject` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:PhysicalObject` (plus 11 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:PhysicalObject and (lis:hasSpatialExtent some lis:Site) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:PhysicalObject SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`toward`** — lis:hasSpatialExtent usageNote: “**The site of an object** will occupy different spatial locations over time if the location and size of the object changes.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:PhysicalObject`, `lis:Site`, `lis:SpatialLocation`, `lis:hasSpatialExtent` |
| `retrieval_gold_chunks` | `lis:PhysicalObject`, `lis:Site`, `lis:hasSpatialExtent` — narrower than `gold_chunks`: `lis:SpatialLocation` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T06 entity pair exactly**; committed entities in gold: `lis:PhysicalObject`, `lis:Site`, `lis:SpatialLocation`; not previously used: `lis:hasSpatialExtent` |
| notes | Mixed. The usageNote attaches ‘site’ to this very property; the NLD states the correct range (‘spatial location’). Toward and away pull inside one chunk. |

#### B05-R03

> **Draft statement.** “Every lis:InformationObject lis:hasContentPart a lis:PhysicalObject.”

| field | value |
| --- | --- |
| draft query | “Does every lis:InformationObject lis:hasContentPart a lis:PhysicalObject in IDO?” |
| formal axiom | `lis:InformationObject SubClassOf (lis:hasContentPart some lis:PhysicalObject)` |
| `licensing_axiom` | `lis:hasContentPart rdfs:range lis:InformationObject`<br>`lis:InformationObject owl:disjointWith lis:PhysicalObject` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasContentPart rdfs:range lis:InformationObject` → every `lis:hasContentPart` filler is a `lis:InformationObject`. 2. The statement’s filler is a `lis:PhysicalObject`. 3. `lis:InformationObject owl:disjointWith lis:PhysicalObject` → `lis:hasContentPart some lis:PhysicalObject` is empty, so `lis:InformationObject` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:InformationObject` (plus 5 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:InformationObject and (lis:hasContentPart some lis:PhysicalObject) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:InformationObject SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasContentPart naturalLanguageDefinition: “If x ‘has content part’ y, then **x and y are information objects**, and x ‘has part’ y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:InformationObject`, `lis:PhysicalObject`, `lis:hasContentPart` |
| `retrieval_gold_chunks` | `lis:InformationObject`, `lis:PhysicalObject`, `lis:hasContentPart` |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T08 entity pair exactly**; committed entities in gold: `lis:InformationObject`, `lis:PhysicalObject`, `lis:hasContentPart` |
| notes | Reuses the T08 entity pair exactly (InformationObject / PhysicalObject). |

#### B05-R04

> **Draft statement.** “Every lis:Location lis:hasSubLocation a lis:PhysicalObject.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Location lis:hasSubLocation a lis:PhysicalObject in IDO?” |
| formal axiom | `lis:Location SubClassOf (lis:hasSubLocation some lis:PhysicalObject)` |
| `licensing_axiom` | `lis:hasSubLocation rdfs:range lis:Location`<br>`lis:Location owl:disjointWith lis:PhysicalObject` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasSubLocation rdfs:range lis:Location` → every `lis:hasSubLocation` filler is a `lis:Location`. 2. The statement’s filler is a `lis:PhysicalObject`. 3. `lis:Location owl:disjointWith lis:PhysicalObject` → `lis:hasSubLocation some lis:PhysicalObject` is empty, so `lis:Location` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Location` (plus 6 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Location and (lis:hasSubLocation some lis:PhysicalObject) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Location SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasSubLocation naturalLanguageDefinition: “If x ‘has sublocation’ y, then **x and y are locations**, and x ‘has part’ y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Location`, `lis:PhysicalObject`, `lis:hasSubLocation` |
| `retrieval_gold_chunks` | `lis:Location`, `lis:PhysicalObject`, `lis:hasSubLocation` |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Location`, `lis:PhysicalObject`, `lis:hasSubLocation` |
| notes | — |

#### B05-R05

> **Draft statement.** “Every lis:Activity lis:hasParticipant a lis:Temporal.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Activity lis:hasParticipant a lis:Temporal in IDO?” |
| formal axiom | `lis:Activity SubClassOf (lis:hasParticipant some lis:Temporal)` |
| `licensing_axiom` | `lis:hasParticipant rdfs:range lis:Object`<br>`lis:Object owl:disjointWith lis:Temporal` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasParticipant rdfs:range lis:Object` → every `lis:hasParticipant` filler is a `lis:Object`. 2. The statement’s filler is a `lis:Temporal`. 3. `lis:Object owl:disjointWith lis:Temporal` → `lis:hasParticipant some lis:Temporal` is empty, so `lis:Activity` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Activity` (plus 2 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Activity and (lis:hasParticipant some lis:Temporal) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Activity SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasParticipant naturalLanguageDefinition: “If x ‘has participant’ y, then x is an ‘activity’, and **y is an ‘object’** that participates in x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:Object`, `lis:Temporal`, `lis:hasParticipant` |
| `retrieval_gold_chunks` | `lis:Activity`, `lis:Temporal`, `lis:hasParticipant` — narrower than `gold_chunks`: `lis:Object` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Activity`, `lis:Object`, `lis:Temporal`, `lis:hasParticipant` |
| notes | lis:Activity’s own NLD (“A temporal entity in which one or more physical objects participate”) reinforces the away reading. |

#### B05-R06

> **Draft statement.** “Every lis:Object lis:hasQuality a lis:Potential.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Object lis:hasQuality a lis:Potential in IDO?” |
| formal axiom | `lis:Object SubClassOf (lis:hasQuality some lis:Potential)` |
| `licensing_axiom` | `lis:hasQuality rdfs:range lis:Quality`<br>`lis:Quality owl:disjointWith lis:Potential` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasQuality rdfs:range lis:Quality` → every `lis:hasQuality` filler is a `lis:Quality`. 2. The statement’s filler is a `lis:Potential`. 3. `lis:Quality owl:disjointWith lis:Potential` → `lis:hasQuality some lis:Potential` is empty, so `lis:Object` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Object` (plus 28 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Object and (lis:hasQuality some lis:Potential) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Object SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasQuality naturalLanguageDefinition: “If x ‘has quality’ y, then x is an ‘object’, and **y is a ‘quality’** that is dependent on x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Object`, `lis:Potential`, `lis:Quality`, `lis:hasQuality` |
| `retrieval_gold_chunks` | `lis:Object`, `lis:Potential`, `lis:hasQuality` — narrower than `gold_chunks`: `lis:Quality` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Object`, `lis:Potential`, `lis:Quality`, `lis:hasQuality` |
| notes | Conflation risk: lis:Quality and lis:Potential are both defined as “A dependent entity …”, so their NLDs alone do not separate them. Very wide blast radius (29 classes fall). |

#### B05-R07

> **Draft statement.** “Every lis:Activity lis:hasTemporalRegion a lis:SpatiotemporalRegion.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Activity lis:hasTemporalRegion a lis:SpatiotemporalRegion in IDO?” |
| formal axiom | `lis:Activity SubClassOf (lis:hasTemporalRegion some lis:SpatiotemporalRegion)` |
| `licensing_axiom` | `lis:hasTemporalRegion rdfs:range lis:TemporalRegion`<br>`lis:TemporalRegion owl:disjointWith lis:SpatiotemporalRegion` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasTemporalRegion rdfs:range lis:TemporalRegion` → every `lis:hasTemporalRegion` filler is a `lis:TemporalRegion`. 2. The statement’s filler is a `lis:SpatiotemporalRegion`. 3. `lis:TemporalRegion owl:disjointWith lis:SpatiotemporalRegion` → `lis:hasTemporalRegion some lis:SpatiotemporalRegion` is empty, so `lis:Activity` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Activity` (plus 2 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Activity and (lis:hasTemporalRegion some lis:SpatiotemporalRegion) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Activity SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`toward`** — lis:hasTemporalRegion usageNote: “Use this relation to associate an activity with **any temporal region of interest**, not only its maximal temporal extent.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:SpatiotemporalRegion`, `lis:TemporalRegion`, `lis:hasTemporalRegion` |
| `retrieval_gold_chunks` | `lis:Activity`, `lis:SpatiotemporalRegion`, `lis:hasTemporalRegion` — narrower than `gold_chunks`: `lis:TemporalRegion` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Activity`, `lis:SpatiotemporalRegion`, `lis:TemporalRegion`, `lis:hasTemporalRegion` |
| notes | Mixed. “Any temporal region of interest” invites a spatiotemporal region; the NLD states the correct range. Weaker toward pull than R01/R02. |

#### B05-R08

> **Draft statement.** “Every lis:Activity lis:hasSpatiotemporalExtent a lis:TemporalRegion.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Activity lis:hasSpatiotemporalExtent a lis:TemporalRegion in IDO?” |
| formal axiom | `lis:Activity SubClassOf (lis:hasSpatiotemporalExtent some lis:TemporalRegion)` |
| `licensing_axiom` | `lis:hasSpatiotemporalExtent rdfs:range lis:SpatiotemporalRegion`<br>`lis:SpatiotemporalRegion owl:disjointWith lis:TemporalRegion` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasSpatiotemporalExtent rdfs:range lis:SpatiotemporalRegion` → every `lis:hasSpatiotemporalExtent` filler is a `lis:SpatiotemporalRegion`. 2. The statement’s filler is a `lis:TemporalRegion`. 3. `lis:SpatiotemporalRegion owl:disjointWith lis:TemporalRegion` → `lis:hasSpatiotemporalExtent some lis:TemporalRegion` is empty, so `lis:Activity` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Activity` (plus 2 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Activity and (lis:hasSpatiotemporalExtent some lis:TemporalRegion) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Activity SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasSpatiotemporalExtent naturalLanguageDefinition: “If x ‘has spatiotemporal extent’ y, then x is an activity, and **y is a spatiotemporal region** which is the spatiotemporal extent of x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:SpatiotemporalRegion`, `lis:TemporalRegion`, `lis:hasSpatiotemporalExtent` |
| `retrieval_gold_chunks` | `lis:Activity`, `lis:TemporalRegion`, `lis:hasSpatiotemporalExtent` — narrower than `gold_chunks`: `lis:SpatiotemporalRegion` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Activity`, `lis:SpatiotemporalRegion`, `lis:TemporalRegion`, `lis:hasSpatiotemporalExtent` |
| notes | — |

#### B05-R09

> **Draft statement.** “Every lis:Object lis:representedIn a lis:PhysicalObject.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Object lis:representedIn a lis:PhysicalObject in IDO?” |
| formal axiom | `lis:Object SubClassOf (lis:representedIn some lis:PhysicalObject)` |
| `licensing_axiom` | `lis:representedIn rdfs:range lis:InformationObject`<br>`lis:InformationObject owl:disjointWith lis:PhysicalObject` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:representedIn rdfs:range lis:InformationObject` → every `lis:representedIn` filler is a `lis:InformationObject`. 2. The statement’s filler is a `lis:PhysicalObject`. 3. `lis:InformationObject owl:disjointWith lis:PhysicalObject` → `lis:representedIn some lis:PhysicalObject` is empty, so `lis:Object` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Object` (plus 28 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Object and (lis:representedIn some lis:PhysicalObject) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Object SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`neutral`** — lis:representedIn usageNote (the property’s ONLY annotation): “For annotations, see the inverse relation ‘is about’.” |
| per-link prose leakage | link 1 (domain/range) not stated in prose; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:InformationObject`, `lis:Object`, `lis:PhysicalObject`, `lis:representedIn` |
| `retrieval_gold_chunks` | `lis:Object`, `lis:PhysicalObject`, `lis:representedIn` — narrower than `gold_chunks`: `lis:InformationObject` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T08 entity pair exactly**; committed entities in gold: `lis:InformationObject`, `lis:Object`, `lis:PhysicalObject`; not previously used: `lis:representedIn` |
| notes | No prose leakage on either link: the property carries no naturalLanguageDefinition at all, so the range axiom is recoverable ONLY from the formal serialisation. Cleanest formal-legibility item in the batch. Wide blast radius (29 classes). |

#### B05-R10

> **Draft statement.** “Every lis:Site lis:siteDeterminedBy a lis:Location.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Site lis:siteDeterminedBy a lis:Location in IDO?” |
| formal axiom | `lis:Site SubClassOf (lis:siteDeterminedBy some lis:Location)` |
| `licensing_axiom` | `lis:siteDeterminedBy rdfs:range lis:PhysicalObject`<br>`lis:PhysicalObject owl:disjointWith lis:Location` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:siteDeterminedBy rdfs:range lis:PhysicalObject` → every `lis:siteDeterminedBy` filler is a `lis:PhysicalObject`. 2. The statement’s filler is a `lis:Location`. 3. `lis:PhysicalObject owl:disjointWith lis:Location` → `lis:siteDeterminedBy some lis:Location` is empty, so `lis:Site` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Site` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Site and (lis:siteDeterminedBy some lis:Location) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Site SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:siteDeterminedBy naturalLanguageDefinition: “If x is ‘site determined by’ y, then x is a ‘site’ and **y is a ‘physical object’** that demarcates or otherwise determines x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Location`, `lis:PhysicalObject`, `lis:Site`, `lis:siteDeterminedBy` |
| `retrieval_gold_chunks` | `lis:Location`, `lis:Site`, `lis:siteDeterminedBy` — narrower than `gold_chunks`: `lis:PhysicalObject` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Location`, `lis:PhysicalObject`, `lis:Site`; not previously used: `lis:siteDeterminedBy` |
| notes | Narrow blast radius: lis:Site alone. |

#### B05-R11

> **Draft statement.** “Every lis:Object lis:locatedRelativeTo a lis:Temporal.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Object lis:locatedRelativeTo a lis:Temporal in IDO?” |
| formal axiom | `lis:Object SubClassOf (lis:locatedRelativeTo some lis:Temporal)` |
| `licensing_axiom` | `lis:locatedRelativeTo rdfs:range lis:Object`<br>`lis:Object owl:disjointWith lis:Temporal` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:locatedRelativeTo rdfs:range lis:Object` → every `lis:locatedRelativeTo` filler is a `lis:Object`. 2. The statement’s filler is a `lis:Temporal`. 3. `lis:Object owl:disjointWith lis:Temporal` → `lis:locatedRelativeTo some lis:Temporal` is empty, so `lis:Object` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Object` (plus 28 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Object and (lis:locatedRelativeTo some lis:Temporal) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Object SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:locatedRelativeTo naturalLanguageDefinition: “If x is ‘located relative to’ y, then **x and y are ‘object’s** with location in space.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Object`, `lis:Temporal`, `lis:locatedRelativeTo` |
| `retrieval_gold_chunks` | `lis:Object`, `lis:Temporal`, `lis:locatedRelativeTo` |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Object`, `lis:Temporal`; not previously used: `lis:locatedRelativeTo` |
| notes | Wide blast radius (29 classes). |

#### B05-R12

> **Draft statement.** “Every lis:PhysicalObject lis:hasArrangedPart an lis:InformationObject.”

| field | value |
| --- | --- |
| draft query | “Does every lis:PhysicalObject lis:hasArrangedPart an lis:InformationObject in IDO?” |
| formal axiom | `lis:PhysicalObject SubClassOf (lis:hasArrangedPart some lis:InformationObject)` |
| `licensing_axiom` | `lis:hasArrangedPart rdfs:range lis:PhysicalObject`<br>`lis:PhysicalObject owl:disjointWith lis:InformationObject` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasArrangedPart rdfs:range lis:PhysicalObject` → every `lis:hasArrangedPart` filler is a `lis:PhysicalObject`. 2. The statement’s filler is a `lis:InformationObject`. 3. `lis:PhysicalObject owl:disjointWith lis:InformationObject` → `lis:hasArrangedPart some lis:InformationObject` is empty, so `lis:PhysicalObject` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:PhysicalObject` (plus 11 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:PhysicalObject and (lis:hasArrangedPart some lis:InformationObject) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:PhysicalObject SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`neutral`** — lis:hasArrangedPart naturalLanguageDefinition: “If x ‘has arranged part’ y, then y is a part of x with a boundary determined in relation to other parts of x.” — names no class. |
| per-link prose leakage | link 1 (domain/range) not stated in prose; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:InformationObject`, `lis:PhysicalObject`, `lis:hasArrangedPart` |
| `retrieval_gold_chunks` | `lis:InformationObject`, `lis:PhysicalObject`, `lis:hasArrangedPart` |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T08 entity pair exactly**; committed entities in gold: `lis:InformationObject`, `lis:PhysicalObject`, `lis:hasArrangedPart` |
| notes | No prose leakage on the range link. Second-cleanest formal-legibility item. |

#### B05-R13

> **Draft statement.** “Every lis:ActivityProfile lis:profileOfQuality a lis:Potential.”

| field | value |
| --- | --- |
| draft query | “Does every lis:ActivityProfile lis:profileOfQuality a lis:Potential in IDO?” |
| formal axiom | `lis:ActivityProfile SubClassOf (lis:profileOfQuality some lis:Potential)` |
| `licensing_axiom` | `lis:profileOfQuality rdfs:range lis:Quality`<br>`lis:Quality owl:disjointWith lis:Potential` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:profileOfQuality rdfs:range lis:Quality` → every `lis:profileOfQuality` filler is a `lis:Quality`. 2. The statement’s filler is a `lis:Potential`. 3. `lis:Quality owl:disjointWith lis:Potential` → `lis:profileOfQuality some lis:Potential` is empty, so `lis:ActivityProfile` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:ActivityProfile` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:ActivityProfile and (lis:profileOfQuality some lis:Potential) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:ActivityProfile SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:profileOfQuality naturalLanguageDefinition: “x is a ‘profile of quality’ y if and only if x is an ‘activity profile’ that **varies only in the ‘quality’ y**.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:ActivityProfile`, `lis:Potential`, `lis:Quality`, `lis:profileOfQuality` |
| `retrieval_gold_chunks` | `lis:ActivityProfile`, `lis:Potential`, `lis:profileOfQuality` — narrower than `gold_chunks`: `lis:Quality` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:ActivityProfile`, `lis:Potential`, `lis:Quality`, `lis:profileOfQuality` |
| notes | Narrow blast radius: lis:ActivityProfile alone. |

#### B05-R14

> **Draft statement.** “Every lis:Potential lis:realizedIn a lis:TemporalRegion.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Potential lis:realizedIn a lis:TemporalRegion in IDO?” |
| formal axiom | `lis:Potential SubClassOf (lis:realizedIn some lis:TemporalRegion)` |
| `licensing_axiom` | `lis:realizedIn rdfs:range lis:Activity`<br>`lis:Activity owl:disjointWith lis:TemporalRegion` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:realizedIn rdfs:range lis:Activity` → every `lis:realizedIn` filler is a `lis:Activity`. 2. The statement’s filler is a `lis:TemporalRegion`. 3. `lis:Activity owl:disjointWith lis:TemporalRegion` → `lis:realizedIn some lis:TemporalRegion` is empty, so `lis:Potential` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Potential` (plus 7 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Potential and (lis:realizedIn some lis:TemporalRegion) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Potential SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:realizedIn naturalLanguageDefinition: “If x is ‘realized in’ y, then x is a ‘potential’, and **y is an ‘activity’** that successfully realizes x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:Potential`, `lis:TemporalRegion`, `lis:realizedIn` |
| `retrieval_gold_chunks` | `lis:Potential`, `lis:TemporalRegion`, `lis:realizedIn` — narrower than `gold_chunks`: `lis:Activity` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Activity`, `lis:Potential`, `lis:TemporalRegion`, `lis:realizedIn` |
| notes | — |

#### B05-R15  ❌ *rejected — see notes*

> **Draft statement.** “Every lis:Actual lis:implements an lis:Actual.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Actual lis:implements an lis:Actual in IDO?” |
| formal axiom | `lis:Actual SubClassOf (lis:implements some lis:Actual)` |
| `licensing_axiom` | `lis:implements rdfs:range lis:Specified`<br>`lis:Specified owl:disjointWith lis:Actual` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:implements rdfs:range lis:Specified` → every `lis:implements` filler is a `lis:Specified`. 2. The statement’s filler is a `lis:Actual`. 3. `lis:Specified owl:disjointWith lis:Actual` → `lis:implements some lis:Actual` is empty, so `lis:Actual` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Actual` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Actual and (lis:implements some lis:Actual) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Actual SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`states_axiom`** — lis:implements explanatoryNote: “**The domain and range restrictions to disjunct classes ‘actual’ and ‘specified’** prevent chains of ‘implements’ relationships.” — AND — lis:Specified usageNote: “**The disjointness axiom** serves to block iterated chains of ‘implements’, etc., relationships.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) **stated in prose** |
| `gold_chunks` | `lis:Actual`, `lis:Specified`, `lis:implements` |
| `retrieval_gold_chunks` | `lis:Actual`, `lis:implements` — narrower than `gold_chunks`: `lis:Specified` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Actual`, `lis:Specified`, `lis:implements` |
| notes | REJECTED. The only candidate whose FULL route — both the range axiom and the disjointness axiom — is stated in prose on the gold chunks. Prose recovery succeeds in every format, so the recoverability profile carries no information. |

#### B05-R16

> **Draft statement.** “Every lis:PhysicalObject lis:connectedTo a lis:Location.”

| field | value |
| --- | --- |
| draft query | “Does every lis:PhysicalObject lis:connectedTo a lis:Location in IDO?” |
| formal axiom | `lis:PhysicalObject SubClassOf (lis:connectedTo some lis:Location)` |
| `licensing_axiom` | `lis:connectedTo rdfs:range lis:PhysicalObject`<br>`lis:PhysicalObject owl:disjointWith lis:Location` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:connectedTo rdfs:range lis:PhysicalObject` → every `lis:connectedTo` filler is a `lis:PhysicalObject`. 2. The statement’s filler is a `lis:Location`. 3. `lis:PhysicalObject owl:disjointWith lis:Location` → `lis:connectedTo some lis:Location` is empty, so `lis:PhysicalObject` — asserted to have such a filler — is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:PhysicalObject` (plus 11 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:PhysicalObject and (lis:connectedTo some lis:Location) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:PhysicalObject SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`neutral`** — lis:connectedTo naturalLanguageDefinition: “If x is ‘connected to’ y, then there is a **physical** connection between x and y.” — names no class. |
| per-link prose leakage | link 1 (domain/range) not stated in prose; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Location`, `lis:PhysicalObject`, `lis:connectedTo` |
| `retrieval_gold_chunks` | `lis:Location`, `lis:PhysicalObject`, `lis:connectedTo` |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Location`, `lis:PhysicalObject`, `lis:connectedTo` |
| notes | No prose leakage on the range link; “physical connection” is a lexical hint only, not a class name. |

#### B05-D01

> **Draft statement.** “Every lis:PhysicalObject lis:isAbout an lis:Activity.”

| field | value |
| --- | --- |
| draft query | “Does every lis:PhysicalObject lis:isAbout an lis:Activity in IDO?” |
| formal axiom | `lis:PhysicalObject SubClassOf (lis:isAbout some lis:Activity)` |
| `licensing_axiom` | `lis:isAbout rdfs:domain lis:InformationObject`<br>`lis:InformationObject owl:disjointWith lis:PhysicalObject` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:isAbout rdfs:domain lis:InformationObject` → anything with a `lis:isAbout` edge is a `lis:InformationObject`. 2. The statement’s subject is a `lis:PhysicalObject`. 3. `lis:InformationObject owl:disjointWith lis:PhysicalObject` → `lis:PhysicalObject` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:PhysicalObject` (plus 11 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:PhysicalObject and (lis:isAbout some lis:Activity) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:PhysicalObject SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:isAbout naturalLanguageDefinition: “If x ‘is about’ y, then **x is an ‘information object’** of relevance to y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:InformationObject`, `lis:PhysicalObject`, `lis:isAbout` |
| `retrieval_gold_chunks` | `lis:Activity`, `lis:PhysicalObject`, `lis:isAbout` — narrower than `gold_chunks`: `lis:InformationObject` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T08 entity pair exactly**; committed entities in gold: `lis:Activity`, `lis:InformationObject`, `lis:PhysicalObject`; not previously used: `lis:isAbout` |
| notes | — |

#### B05-D02

> **Draft statement.** “Every lis:SpatialLocation lis:siteOf an lis:Activity.”

| field | value |
| --- | --- |
| draft query | “Does every lis:SpatialLocation lis:siteOf an lis:Activity in IDO?” |
| formal axiom | `lis:SpatialLocation SubClassOf (lis:siteOf some lis:Activity)` |
| `licensing_axiom` | `lis:siteOf rdfs:domain lis:Site`<br>`lis:Site owl:disjointWith lis:SpatialLocation` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:siteOf rdfs:domain lis:Site` → anything with a `lis:siteOf` edge is a `lis:Site`. 2. The statement’s subject is a `lis:SpatialLocation`. 3. `lis:Site owl:disjointWith lis:SpatialLocation` → `lis:SpatialLocation` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:SpatialLocation` (plus 4 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:SpatialLocation and (lis:siteOf some lis:Activity) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:SpatialLocation SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:siteOf naturalLanguageDefinition: “If x ‘site of’ y, then **x is a ‘site’**, y is an ‘activity’, and y takes place entirely within x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:Site`, `lis:SpatialLocation`, `lis:siteOf` |
| `retrieval_gold_chunks` | `lis:Activity`, `lis:SpatialLocation`, `lis:siteOf` — narrower than `gold_chunks`: `lis:Site` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T06 entity pair exactly**; committed entities in gold: `lis:Activity`, `lis:Site`, `lis:SpatialLocation`, `lis:siteOf` |
| notes | Conflation risk: lis:Site and lis:SpatialLocation are both defined as kinds of location. Reuses the T06 entity pair exactly. |

#### B05-D03

> **Draft statement.** “Every lis:Organization lis:hasPhysicalQuantity a lis:PhysicalQuantity.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Organization lis:hasPhysicalQuantity a lis:PhysicalQuantity in IDO?” |
| formal axiom | `lis:Organization SubClassOf (lis:hasPhysicalQuantity some lis:PhysicalQuantity)` |
| `licensing_axiom` | `lis:hasPhysicalQuantity rdfs:domain lis:PhysicalObject`<br>`lis:PhysicalObject owl:disjointWith lis:Organization` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasPhysicalQuantity rdfs:domain lis:PhysicalObject` → anything with a `lis:hasPhysicalQuantity` edge is a `lis:PhysicalObject`. 2. The statement’s subject is a `lis:Organization`. 3. `lis:PhysicalObject owl:disjointWith lis:Organization` → `lis:Organization` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Organization` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Organization and (lis:hasPhysicalQuantity some lis:PhysicalQuantity) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Organization SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`neutral`** — lis:hasPhysicalQuantity naturalLanguageDefinition: “x ‘has physical quantity’ y if and only if x ‘has quality’ y, and y is a ‘physical quantity’.” — states the RANGE but never the domain. |
| per-link prose leakage | link 1 (domain/range) not stated in prose; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Organization`, `lis:PhysicalObject`, `lis:PhysicalQuantity`, `lis:hasPhysicalQuantity` |
| `retrieval_gold_chunks` | `lis:Organization`, `lis:PhysicalQuantity`, `lis:hasPhysicalQuantity` — narrower than `gold_chunks`: `lis:PhysicalObject` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Organization`, `lis:PhysicalObject`, `lis:PhysicalQuantity`, `lis:hasPhysicalQuantity` |
| notes | No prose leakage on the DOMAIN link, which is the licensing link here. Uses the Organization/PhysicalObject disjointness axiom, which no committed item uses. Narrow blast radius: lis:Organization alone. Mild counter-pull: an organisation “comprising one or more persons” might be read as having mass. |

#### B05-D04

> **Draft statement.** “Every lis:Organization lis:hasContentPart an lis:InformationObject.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Organization lis:hasContentPart an lis:InformationObject in IDO?” |
| formal axiom | `lis:Organization SubClassOf (lis:hasContentPart some lis:InformationObject)` |
| `licensing_axiom` | `lis:hasContentPart rdfs:domain lis:InformationObject`<br>`lis:InformationObject owl:disjointWith lis:Organization` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasContentPart rdfs:domain lis:InformationObject` → anything with a `lis:hasContentPart` edge is a `lis:InformationObject`. 2. The statement’s subject is a `lis:Organization`. 3. `lis:InformationObject owl:disjointWith lis:Organization` → `lis:Organization` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Organization` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Organization and (lis:hasContentPart some lis:InformationObject) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Organization SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasContentPart naturalLanguageDefinition: “If x ‘has content part’ y, then **x and y are information objects**, and x ‘has part’ y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:InformationObject`, `lis:Organization`, `lis:hasContentPart` |
| `retrieval_gold_chunks` | `lis:InformationObject`, `lis:Organization`, `lis:hasContentPart` |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:InformationObject`, `lis:Organization`, `lis:hasContentPart` |
| notes | Uses the InformationObject/Organization disjointness axiom, unused by any committed item. Narrow blast radius: lis:Organization alone. |

#### B05-D05

> **Draft statement.** “Every lis:Location lis:hasMaterialPart a lis:Compound.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Location lis:hasMaterialPart a lis:Compound in IDO?” |
| formal axiom | `lis:Location SubClassOf (lis:hasMaterialPart some lis:Compound)` |
| `licensing_axiom` | `lis:hasMaterialPart rdfs:domain lis:PhysicalObject`<br>`lis:PhysicalObject owl:disjointWith lis:Location` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasMaterialPart rdfs:domain lis:PhysicalObject` → anything with a `lis:hasMaterialPart` edge is a `lis:PhysicalObject`. 2. The statement’s subject is a `lis:Location`. 3. `lis:PhysicalObject owl:disjointWith lis:Location` → `lis:Location` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Location` (plus 6 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Location and (lis:hasMaterialPart some lis:Compound) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Location SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasMaterialPart naturalLanguageDefinition: “If x ‘has material part’ y, then **x is a ‘physical object’**, and y is a maximal part of x that has a certain ‘material composition quality’.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Compound`, `lis:Location`, `lis:PhysicalObject`, `lis:hasMaterialPart` |
| `retrieval_gold_chunks` | `lis:Compound`, `lis:Location`, `lis:hasMaterialPart` — narrower than `gold_chunks`: `lis:PhysicalObject` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Compound`, `lis:Location`, `lis:PhysicalObject`, `lis:hasMaterialPart` |
| notes | — |

#### B05-D06

> **Draft statement.** “Every lis:Potential lis:qualityQuantifiedAs a lis:QualityDatum.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Potential lis:qualityQuantifiedAs a lis:QualityDatum in IDO?” |
| formal axiom | `lis:Potential SubClassOf (lis:qualityQuantifiedAs some lis:QualityDatum)` |
| `licensing_axiom` | `lis:qualityQuantifiedAs rdfs:domain lis:Quality`<br>`lis:Quality owl:disjointWith lis:Potential` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:qualityQuantifiedAs rdfs:domain lis:Quality` → anything with a `lis:qualityQuantifiedAs` edge is a `lis:Quality`. 2. The statement’s subject is a `lis:Potential`. 3. `lis:Quality owl:disjointWith lis:Potential` → `lis:Potential` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Potential` (plus 7 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Potential and (lis:qualityQuantifiedAs some lis:QualityDatum) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Potential SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:qualityQuantifiedAs naturalLanguageDefinition: “If x is a ‘quality quantified as’ y, then **x is an ‘quality’** that is ‘represented in’ the ‘quality datum’ y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Potential`, `lis:Quality`, `lis:QualityDatum`, `lis:qualityQuantifiedAs` |
| `retrieval_gold_chunks` | `lis:Potential`, `lis:QualityDatum`, `lis:qualityQuantifiedAs` — narrower than `gold_chunks`: `lis:Quality` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Potential`, `lis:Quality`, `lis:QualityDatum`, `lis:qualityQuantifiedAs` |
| notes | — |

#### B05-D07

> **Draft statement.** “Every lis:TemporalRegion lis:hasActivityPart an lis:Activity.”

| field | value |
| --- | --- |
| draft query | “Does every lis:TemporalRegion lis:hasActivityPart an lis:Activity in IDO?” |
| formal axiom | `lis:TemporalRegion SubClassOf (lis:hasActivityPart some lis:Activity)` |
| `licensing_axiom` | `lis:hasActivityPart rdfs:domain lis:Activity`<br>`lis:Activity owl:disjointWith lis:TemporalRegion` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasActivityPart rdfs:domain lis:Activity` → anything with a `lis:hasActivityPart` edge is a `lis:Activity`. 2. The statement’s subject is a `lis:TemporalRegion`. 3. `lis:Activity owl:disjointWith lis:TemporalRegion` → `lis:TemporalRegion` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:TemporalRegion` (plus 5 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:TemporalRegion and (lis:hasActivityPart some lis:Activity) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:TemporalRegion SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasActivityPart naturalLanguageDefinition: “If x ‘has activity part’ y, then **x and y are activities**, and x ‘has temporal part’ y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:TemporalRegion`, `lis:hasActivityPart` |
| `retrieval_gold_chunks` | `lis:Activity`, `lis:TemporalRegion`, `lis:hasActivityPart` |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Activity`, `lis:TemporalRegion`, `lis:hasActivityPart` |
| notes | — |

#### B05-D08  ❌ *rejected — see notes*

> **Draft statement.** “Every lis:Organization lis:contains a lis:PhysicalObject.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Organization lis:contains a lis:PhysicalObject in IDO?” |
| formal axiom | `lis:Organization SubClassOf (lis:contains some lis:PhysicalObject)` |
| `licensing_axiom` | `lis:contains rdfs:domain lis:Location`<br>`lis:Location owl:disjointWith lis:Organization` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:contains rdfs:domain lis:Location` (union domain `lis:Location` ⊔ `lis:PhysicalObject`; `lis:Organization` is disjoint from *both* disjuncts) → anything with a `lis:contains` edge is a `lis:Location`. 2. The statement’s subject is a `lis:Organization`. 3. `lis:Location owl:disjointWith lis:Organization` → `lis:Organization` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Organization` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Organization and (lis:contains some lis:PhysicalObject) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Organization SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:contains naturalLanguageDefinition: “If x ‘contains’ y, then **x and y are both ‘physical object’ or ‘location’**, and y is located entirely within x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Location`, `lis:Organization`, `lis:PhysicalObject`, `lis:contains` |
| `retrieval_gold_chunks` | `lis:Organization`, `lis:PhysicalObject`, `lis:contains` — narrower than `gold_chunks`: `lis:Location` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=F elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `false` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Location`, `lis:Organization`, `lis:PhysicalObject`; not previously used: `lis:contains` |
| notes | DROP, or investigate first. Sole non-uniform profile in the batch (turtle=false) — but that is a MATCHER ARTEFACT, not a serialisation difference; see the gate-gap section. Also the only union-domain candidate, so a single connected chain cannot record the full route (Organization is disjoint from BOTH disjuncts; the chain records only the Location disjunct). |

#### B05-D09

> **Draft statement.** “Every lis:Activity lis:temporalRegionQuantifiedAs a lis:TemporalDatum.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Activity lis:temporalRegionQuantifiedAs a lis:TemporalDatum in IDO?” |
| formal axiom | `lis:Activity SubClassOf (lis:temporalRegionQuantifiedAs some lis:TemporalDatum)` |
| `licensing_axiom` | `lis:temporalRegionQuantifiedAs rdfs:domain lis:TemporalRegion`<br>`lis:TemporalRegion owl:disjointWith lis:Activity` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:temporalRegionQuantifiedAs rdfs:domain lis:TemporalRegion` → anything with a `lis:temporalRegionQuantifiedAs` edge is a `lis:TemporalRegion`. 2. The statement’s subject is a `lis:Activity`. 3. `lis:TemporalRegion owl:disjointWith lis:Activity` → `lis:Activity` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Activity` (plus 2 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Activity and (lis:temporalRegionQuantifiedAs some lis:TemporalDatum) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Activity SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:temporalRegionQuantifiedAs naturalLanguageDefinition: “If x is ‘temporal region quantified as’ y, then **x is a ‘temporal region’** that is represented in the ‘temporal datum’ y.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Activity`, `lis:TemporalDatum`, `lis:TemporalRegion`, `lis:temporalRegionQuantifiedAs` |
| `retrieval_gold_chunks` | `lis:Activity`, `lis:TemporalDatum`, `lis:temporalRegionQuantifiedAs` — narrower than `gold_chunks`: `lis:TemporalRegion` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:Activity`, `lis:TemporalDatum`, `lis:TemporalRegion`, `lis:temporalRegionQuantifiedAs` |
| notes | — |

#### B05-D10

> **Draft statement.** “Every lis:Dependent lis:hasPotential a lis:Potential.”

| field | value |
| --- | --- |
| draft query | “Does every lis:Dependent lis:hasPotential a lis:Potential in IDO?” |
| formal axiom | `lis:Dependent SubClassOf (lis:hasPotential some lis:Potential)` |
| `licensing_axiom` | `lis:hasPotential rdfs:domain lis:Object`<br>`lis:Object owl:disjointWith lis:Dependent` |
| `licensing_axiom_status` | `entailed_chain` |
| mechanism | `composed_domain_range_disjointness` |
| inference route | 1. `lis:hasPotential rdfs:domain lis:Object` → anything with a `lis:hasPotential` edge is a `lis:Object`. 2. The statement’s subject is a `lis:Dependent`. 3. `lis:Object owl:disjointWith lis:Dependent` → `lis:Dependent` is unsatisfiable. |
| `robot reason` result | unsatisfiable: `lis:Dependent` (plus 18 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:Dependent and (lis:hasPotential some lis:Potential) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:Dependent SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`away`** — lis:hasPotential naturalLanguageDefinition: “If x ‘has potential’ y, then **x is an ‘object’**, and y is a ‘potential’ that is dependent on x.” |
| per-link prose leakage | link 1 (domain/range) **stated in prose**; link 2 (disjointness) not stated in prose |
| `gold_chunks` | `lis:Dependent`, `lis:Object`, `lis:Potential`, `lis:hasPotential` |
| `retrieval_gold_chunks` | `lis:Dependent`, `lis:Potential`, `lis:hasPotential` — narrower than `gold_chunks`: `lis:Object` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (4 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | **reuses the T07 entity pair exactly**; committed entities in gold: `lis:Dependent`, `lis:Object`, `lis:Potential`, `lis:hasPotential` |
| notes | Reuses the T07 entity pair exactly (Dependent / Object). Wide blast radius (19 classes). |

### 4.2 `functional_property`

#### B05-F01

> **Draft statement.** “A single quality datum carries two different units of measure at once.”

| field | value |
| --- | --- |
| draft query | “Can one lis:QualityDatum have more than one lis:datumUOM in IDO?” |
| formal axiom | `lis:QualityDatum SubClassOf (lis:datumUOM min 2 owl:Thing)` — i.e. the claim that `lis:QualityDatum and (lis:datumUOM min 2 owl:Thing)` is non-empty |
| `licensing_axiom` | `lis:datumUOM rdf:type owl:FunctionalProperty` |
| `licensing_axiom_status` | `asserted` |
| mechanism | `functional_property` |
| inference route | 1. `lis:datumUOM rdf:type owl:FunctionalProperty` → every individual has at most one `lis:datumUOM` filler. 2. The statement requires an individual of `lis:QualityDatum` with two *different* fillers. 3. `lis:QualityDatum ⊓ (lis:datumUOM min 2)` is therefore empty; asserting it as a superclass of `lis:QualityDatum` makes `lis:QualityDatum` unsatisfiable. No disjointness axiom is involved. |
| `robot reason` result | unsatisfiable: `lis:QualityDatum` (plus 1 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:QualityDatum and (lis:datumUOM min 2 owl:Thing) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:QualityDatum SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`toward`** — lis:QualityDatum usageNote: “This class may be used for data that **don’t fit the restriction to ‘single unit, single number’** of ‘scalar quantity datum’, including data employing vectors instead of numbers …” |
| per-link prose leakage | link 1 (functionality) not stated in prose |
| `gold_chunks` | `lis:QualityDatum`, `lis:datumUOM` |
| `retrieval_gold_chunks` | `lis:QualityDatum`, `lis:datumUOM` |
| gold-size class | gold &lt; k (2 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:QualityDatum`, `lis:datumUOM` |
| notes | The author’s selected Candidate-2 phrasing, on lis:datumUOM. The QualityDatum usageNote says explicitly that this class is NOT bound by the single-unit restriction, which a reader can take as licensing two units — prose pointing toward the false claim. Not surfaced by the Part A gate work, which ran the reasoner gate but no prose screen. |

#### B05-F02

> **Draft statement.** “A single quality datum carries two different literal values at once.”

| field | value |
| --- | --- |
| draft query | “Can one lis:QualityDatum have more than one lis:datumValue in IDO?” |
| formal axiom | `lis:QualityDatum SubClassOf (lis:datumValue min 2 rdfs:Literal)` — i.e. the claim that `lis:QualityDatum and (lis:datumValue min 2 rdfs:Literal)` is non-empty |
| `licensing_axiom` | `lis:datumValue rdf:type owl:FunctionalProperty` |
| `licensing_axiom_status` | `asserted` |
| mechanism | `functional_property` |
| inference route | 1. `lis:datumValue rdf:type owl:FunctionalProperty` → every individual has at most one `lis:datumValue` filler. 2. The statement requires an individual of `lis:QualityDatum` with two *different* fillers. 3. `lis:QualityDatum ⊓ (lis:datumValue min 2)` is therefore empty; asserting it as a superclass of `lis:QualityDatum` makes `lis:QualityDatum` unsatisfiable. No disjointness axiom is involved. |
| `robot reason` result | unsatisfiable: `lis:QualityDatum` (plus 1 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:QualityDatum and (lis:datumValue min 2 rdfs:Literal) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:QualityDatum SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`toward`** — lis:QualityDatum usageNote: “This class may be used for data that **don’t fit the restriction to ‘single unit, single number’** of ‘scalar quantity datum’ …” |
| per-link prose leakage | link 1 (functionality) not stated in prose |
| `gold_chunks` | `lis:QualityDatum`, `lis:datumValue` |
| `retrieval_gold_chunks` | `lis:QualityDatum`, `lis:datumValue` |
| gold-size class | gold &lt; k (2 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:QualityDatum`, `lis:datumValue` |
| notes | The lis:datumValue mirror of F01. Counter-pull: lis:datumValue usageNote says “Provide **a** unit of measure … for a ‘quality datum’ to be interpretable” (singular). |

#### B05-F03  ❌ *rejected — see notes*

> **Draft statement.** “A single scalar quantity datum carries two different units of measure at once.”

| field | value |
| --- | --- |
| draft query | “Can one lis:ScalarQuantityDatum have more than one lis:datumUOM in IDO?” |
| formal axiom | `lis:ScalarQuantityDatum SubClassOf (lis:datumUOM min 2 owl:Thing)` — i.e. the claim that `lis:ScalarQuantityDatum and (lis:datumUOM min 2 owl:Thing)` is non-empty |
| `licensing_axiom` | `lis:datumUOM rdf:type owl:FunctionalProperty` |
| `licensing_axiom_status` | `asserted` |
| mechanism | `functional_property` |
| inference route | 1. `lis:datumUOM rdf:type owl:FunctionalProperty` → every individual has at most one `lis:datumUOM` filler. 2. The statement requires an individual of `lis:ScalarQuantityDatum` with two *different* fillers. 3. `lis:ScalarQuantityDatum ⊓ (lis:datumUOM min 2)` is therefore empty; asserting it as a superclass of `lis:ScalarQuantityDatum` makes `lis:ScalarQuantityDatum` unsatisfiable. No disjointness axiom is involved. |
| `robot reason` result | unsatisfiable: `lis:ScalarQuantityDatum` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:ScalarQuantityDatum and (lis:datumUOM min 2 owl:Thing) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:ScalarQuantityDatum SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`states_axiom`** — lis:ScalarQuantityDatum usageNote: “A scalar quantity datum **has a unique unit of measure** and a unique numeric value.” |
| per-link prose leakage | link 1 (functionality) not stated in prose |
| `gold_chunks` | `lis:ScalarQuantityDatum`, `lis:datumUOM` |
| `retrieval_gold_chunks` | `lis:ScalarQuantityDatum`, `lis:datumUOM` |
| gold-size class | gold &lt; k (2 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:ScalarQuantityDatum`, `lis:datumUOM` |
| notes | REJECTED. The gold chunk’s own usageNote states the functionality consequence verbatim for this class, so prose recovery succeeds in every format. |

#### B05-F04  ❌ *rejected — see notes*

> **Draft statement.** “A single scalar quantity datum carries two different literal values at once.”

| field | value |
| --- | --- |
| draft query | “Can one lis:ScalarQuantityDatum have more than one lis:datumValue in IDO?” |
| formal axiom | `lis:ScalarQuantityDatum SubClassOf (lis:datumValue min 2 rdfs:Literal)` — i.e. the claim that `lis:ScalarQuantityDatum and (lis:datumValue min 2 rdfs:Literal)` is non-empty |
| `licensing_axiom` | `lis:datumValue rdf:type owl:FunctionalProperty` |
| `licensing_axiom_status` | `asserted` |
| mechanism | `functional_property` |
| inference route | 1. `lis:datumValue rdf:type owl:FunctionalProperty` → every individual has at most one `lis:datumValue` filler. 2. The statement requires an individual of `lis:ScalarQuantityDatum` with two *different* fillers. 3. `lis:ScalarQuantityDatum ⊓ (lis:datumValue min 2)` is therefore empty; asserting it as a superclass of `lis:ScalarQuantityDatum` makes `lis:ScalarQuantityDatum` unsatisfiable. No disjointness axiom is involved. |
| `robot reason` result | unsatisfiable: `lis:ScalarQuantityDatum` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:ScalarQuantityDatum and (lis:datumValue min 2 rdfs:Literal) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:ScalarQuantityDatum SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`states_axiom`** — lis:ScalarQuantityDatum usageNote: “A scalar quantity datum has a unique unit of measure and **a unique numeric value**.” |
| per-link prose leakage | link 1 (functionality) not stated in prose |
| `gold_chunks` | `lis:ScalarQuantityDatum`, `lis:datumValue` |
| `retrieval_gold_chunks` | `lis:ScalarQuantityDatum`, `lis:datumValue` |
| gold-size class | gold &lt; k (2 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:ScalarQuantityDatum`, `lis:datumValue` |
| notes | REJECTED, same fragment, value half. |

#### B05-F05

> **Draft statement.** “A single quality datum carries two different units of measure at once.”

| field | value |
| --- | --- |
| draft query | “Can one lis:QualityDatum have more than one lis:datumUOM in IDO?” |
| formal axiom | `lis:QualityDatum SubClassOf (lis:datumUOM min 2 lis:UnitOfMeasure)` — i.e. the claim that `lis:QualityDatum and (lis:datumUOM min 2 lis:UnitOfMeasure)` is non-empty |
| `licensing_axiom` | `lis:datumUOM rdf:type owl:FunctionalProperty` |
| `licensing_axiom_status` | `asserted` |
| mechanism | `functional_property` |
| inference route | 1. `lis:datumUOM rdf:type owl:FunctionalProperty` → every individual has at most one `lis:datumUOM` filler. 2. The statement requires an individual of `lis:QualityDatum` with two *different* fillers. 3. `lis:QualityDatum ⊓ (lis:datumUOM min 2)` is therefore empty; asserting it as a superclass of `lis:QualityDatum` makes `lis:QualityDatum` unsatisfiable. No disjointness axiom is involved. |
| `robot reason` result | unsatisfiable: `lis:QualityDatum` (plus 1 subclasses of it) |
| vacuity | **caveat does not apply** — the Manchester form `lis:QualityDatum and (lis:datumUOM min 2 lis:UnitOfMeasure) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:QualityDatum SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`toward`** — lis:QualityDatum usageNote: “This class may be used for data that **don’t fit the restriction to ‘single unit, single number’** of ‘scalar quantity datum’ …” |
| per-link prose leakage | link 1 (functionality) not stated in prose |
| `gold_chunks` | `lis:QualityDatum`, `lis:UnitOfMeasure`, `lis:datumUOM` |
| `retrieval_gold_chunks` | `lis:QualityDatum`, `lis:datumUOM` — narrower than `gold_chunks`: `lis:UnitOfMeasure` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:QualityDatum`, `lis:UnitOfMeasure`, `lis:datumUOM` |
| notes | Qualified-cardinality variant of F01 (min 2 lis:UnitOfMeasure rather than min 2 owl:Thing). Same statement, same licensing axiom — a phrasing variant of F01, not an independent item. |

#### B05-F06  ❌ *rejected — see notes*

> **Draft statement.** “A single scalar quantity datum carries two different units of measure at once.”

| field | value |
| --- | --- |
| draft query | “Can one lis:ScalarQuantityDatum have more than one lis:datumUOM in IDO?” |
| formal axiom | `lis:ScalarQuantityDatum SubClassOf (lis:datumUOM min 2 lis:UnitOfMeasure)` — i.e. the claim that `lis:ScalarQuantityDatum and (lis:datumUOM min 2 lis:UnitOfMeasure)` is non-empty |
| `licensing_axiom` | `lis:datumUOM rdf:type owl:FunctionalProperty` |
| `licensing_axiom_status` | `asserted` |
| mechanism | `functional_property` |
| inference route | 1. `lis:datumUOM rdf:type owl:FunctionalProperty` → every individual has at most one `lis:datumUOM` filler. 2. The statement requires an individual of `lis:ScalarQuantityDatum` with two *different* fillers. 3. `lis:ScalarQuantityDatum ⊓ (lis:datumUOM min 2)` is therefore empty; asserting it as a superclass of `lis:ScalarQuantityDatum` makes `lis:ScalarQuantityDatum` unsatisfiable. No disjointness axiom is involved. |
| `robot reason` result | unsatisfiable: `lis:ScalarQuantityDatum` (no collateral) |
| vacuity | **caveat does not apply** — the Manchester form `lis:ScalarQuantityDatum and (lis:datumUOM min 2 lis:UnitOfMeasure) SubClassOf: owl:Nothing` is entailed by the *unmodified* canonical graph (checked with `explain_entailment`), and `lis:ScalarQuantityDatum SubClassOf owl:Nothing` is **not** entailed. Strictly stronger than the bare-disjointness items. |
| `annotation_prose_screen` | **`states_axiom`** — lis:ScalarQuantityDatum usageNote: “A scalar quantity datum **has a unique unit of measure** and a unique numeric value.” |
| per-link prose leakage | link 1 (functionality) not stated in prose |
| `gold_chunks` | `lis:ScalarQuantityDatum`, `lis:UnitOfMeasure`, `lis:datumUOM` |
| `retrieval_gold_chunks` | `lis:ScalarQuantityDatum`, `lis:datumUOM` — narrower than `gold_chunks`: `lis:UnitOfMeasure` justifies the contradiction but is not named in the query, so it is not a retrieval target (T03 precedent) |
| gold-size class | gold &lt; k (3 chunks, top-k = 5) |
| `recoverability_profile` | turtle=T elot-org=T elot-org-ancestors=T omn=T jsonld=T yaml-ld=T ofn=T |
| `uniform` | `true` |
| gate verdict | `pass` |
| `reasoning_type` | `structural` |
| `query_source` | `label` |
| entity reuse | committed entities in gold: `lis:ScalarQuantityDatum`, `lis:UnitOfMeasure`, `lis:datumUOM` |
| notes | REJECTED. Qualified-cardinality variant of F03; same rejection. |

---

## 5. Entity-reuse summary against the committed set

The committed contradicted items use three disjointness axioms:

| item | pair |
| --- | --- |
| T06 | `lis:Site` ⊥ `lis:SpatialLocation` |
| T07 | `lis:Dependent` ⊥ `lis:Object` |
| T08 | `lis:InformationObject` ⊥ `lis:PhysicalObject` |

**Candidates reusing a committed pair exactly** (both classes present in the gold set):

| committed item | shared pair | candidates |
| --- | --- | --- |
| T06 | `lis:Site` ⊥ `lis:SpatialLocation` | B05-R01, B05-R02, B05-D02 |
| T07 | `lis:Dependent` ⊥ `lis:Object` | B05-D10 |
| T08 | `lis:InformationObject` ⊥ `lis:PhysicalObject` | B05-R03, B05-R09, B05-R12, B05-D01 |

That is **8 of 32** candidates carrying a committed pair; the other 24 do not.

**Disjointness-axiom coverage.** The composed candidates draw on **12 of the 15** asserted pairwise disjointness axioms, leaving 3 untouched. 3 of the 3 axioms used by T06–T08 reappear here.

| disjointness axiom | used by | already used by a committed item? |
| --- | --- | --- |
| `lis:Activity` ⊥ `lis:TemporalRegion` | B05-R14, B05-D07, B05-D09 | **no — fresh axiom** |
| `lis:Actual` ⊥ `lis:Specified` | B05-R15 | **no — fresh axiom** |
| `lis:Dependent` ⊥ `lis:Object` | B05-D10 | T07 |
| `lis:InformationObject` ⊥ `lis:Organization` | B05-D04 | **no — fresh axiom** |
| `lis:InformationObject` ⊥ `lis:PhysicalObject` | B05-R03, B05-R09, B05-R12, B05-D01 | T08 |
| `lis:Location` ⊥ `lis:Organization` | B05-D08 | **no — fresh axiom** |
| `lis:Location` ⊥ `lis:PhysicalObject` | B05-R04, B05-R10, B05-R16, B05-D05 | **no — fresh axiom** |
| `lis:Object` ⊥ `lis:Temporal` | B05-R05, B05-R11 | **no — fresh axiom** |
| `lis:Organization` ⊥ `lis:PhysicalObject` | B05-D03 | **no — fresh axiom** |
| `lis:Potential` ⊥ `lis:Quality` | B05-R06, B05-R13, B05-D06 | **no — fresh axiom** |
| `lis:Site` ⊥ `lis:SpatialLocation` | B05-R01, B05-R02, B05-D02 | T06 |
| `lis:SpatiotemporalRegion` ⊥ `lis:TemporalRegion` | B05-R07, B05-R08 | **no — fresh axiom** |

**Candidates whose gold set avoids all eight entities the brief flags as already committed** (`lis:InformationObject`, `lis:PhysicalObject`, `lis:Specified`, `lis:Actual`, `lis:Site`, `lis:SpatialLocation`, `lis:Object`, `lis:Dependent`): **B05-R07, B05-R08, B05-R13, B05-R14, B05-D06, B05-D07, B05-D09, B05-F01, B05-F02, B05-F03, B05-F04, B05-F05, B05-F06** — 13 of 32.

**Within-batch reuse.** The 26 composed candidates use **25 distinct properties**; the only repeat is `lis:hasContentPart` (2×) — B05-R03 violates its range and B05-D04 violates its domain, so they are different links resting on different disjointness axioms. Subject classes repeat more: `lis:PhysicalObject` ×5, `lis:Activity` ×4, `lis:Object` ×3, `lis:Organization` ×3, `lis:Location` ×2, `lis:Potential` ×2. The 6 functional-property candidates use 2 properties across 2 subject classes.

**Widest-reuse entities across the committed benchmark**, for context when selecting: `lis:PhysicalObject` (94 mentions in `tasks_60.yaml`), `lis:Activity` (92), `lis:QualityDatum` (52), `lis:Object` (45), `lis:TemporalRegion` (37).

---

## 6. Prose direction — recorded, not targeted

No distribution was targeted. Measured over all 32 candidates:

| direction | n | candidates |
| --- | ---: | --- |
| `toward` | 6 | B05-R01, B05-R02, B05-R07, B05-F01, B05-F02, B05-F05 |
| `neutral` | 4 | B05-R09, B05-R12, B05-R16, B05-D03 |
| `away` | 18 | B05-R03, B05-R04, B05-R05, B05-R06, B05-R08, B05-R10, B05-R11, B05-R13, B05-R14, B05-D01, B05-D02, B05-D04, B05-D05, B05-D06, B05-D07, B05-D08, B05-D09, B05-D10 |
| `states_axiom` (rejected) | 4 | B05-R15, B05-F03, B05-F04, B05-F06 |

**`toward` candidates, flagged prominently as the brief asks.** Six turned up, and they split into
two quite different kinds:

1. **B05-R01 (`lis:residesIn`) is the strongest.** The property’s `naturalLanguageDefinition` says
   the filler is “a ‘location’”, but the asserted `rdfs:range` is the narrower `lis:Site`. Since
   `lis:SpatialLocation` *is* a `lis:Location`, a reader following the annotation concludes
   `supported`, while the axioms give `contradicted`. This is prose and formal axiom genuinely
   disagreeing in IDO, not a lexical accident — the closest structural analogue to T03 in the batch.
2. **B05-R02 and B05-R07 are lexical pulls**, where a `usageNote` puts the violating class next to
   the property (“**The site of an object** will occupy different spatial locations over time”;
   “any temporal region of interest”) while the `naturalLanguageDefinition` states the correct
   constraint. Both chunks contain a toward pull and an away pull.
3. **B05-F01, B05-F02, B05-F05** inherit `toward` from a single `lis:QualityDatum` usageNote:
   “This class may be used for data that **don’t fit the restriction to ‘single unit, single
   number’** of ‘scalar quantity datum’”. Read plainly, that says a `lis:QualityDatum` is not bound
   to one unit — pointing toward the false statement. **This was not surfaced by the Part A
   functional-property finding**, which ran the reasoner gate but no prose screen. The author should
   weigh it: the selected phrasing is on `lis:QualityDatum` precisely because the
   `lis:ScalarQuantityDatum` alternative is a `states_axiom` rejection (§7.1), so the stratum offers
   a choice between prose that points the wrong way and prose that gives the answer away.

**A structural finding about the composed stratum.** IDO annotates properties with a fixed template
— “If x ‘P’ y, then x is an ‘A’, and y is a ‘B’” — which **restates the domain and range in prose**.
So link 1 of the licensing chain is stated in prose for **22 of the 26** composed candidates. The
four exceptions, where the licensing link is recoverable *only* from the formal serialisation, are
**B05-R09, B05-R12, B05-R16, B05-D03** (`lis:representedIn` carries no NLD at all;
`lis:hasArrangedPart` and `lis:connectedTo` name no class; `lis:hasPhysicalQuantity` states its range
but never its domain, and the domain is the licensing link). If the study wants composed items that
isolate formal-axiom legibility rather than prose legibility, those four are the ones that do it.

This leakage is *partial*, and on the reading used here it is not disqualifying: link 2 — the
disjointness axiom — is never in prose except for B05-R15. Prose alone therefore does not settle any
composed candidate except that one, so the recoverability profile still means something. This
matches how Batch 02 handled T11/T12/T13, which are committed with per-link `states_axiom` leakage
recorded in their notes. **If the author prefers a strict per-link reading, the composed stratum
loses 22 of 26 candidates and only the four named above survive** — enough for three items, but with
no room to reject. That is a judgement call, flagged rather than made.

---

## 7. `states_axiom` rejections, with the settling fragment

Four candidates are rejected because prose on a gold chunk states the licensing axiom outright, so
prose recovery succeeds regardless of format and the recoverability profile is uninformative.

### 7.1 Functional property — B05-F03, B05-F04, B05-F06

> `lis:ScalarQuantityDatum` **usageNote**: “A scalar quantity datum **has a unique unit of measure
> and a unique numeric value**. This class is inspired by the class ‘scalar measurement datum’ of
> the Information Artifact Ontology.”

That sentence states the consequence of both `owl:FunctionalProperty` declarations, in prose, on the
gold chunk. Any item whose subject is `lis:ScalarQuantityDatum` is settled by reading it. **This is
why both functional-property items must take `lis:QualityDatum` as their subject** — which is what
the author’s selected phrasing already does, but for a reason Part A did not record.

### 7.2 Composed — B05-R15 (`lis:implements`)

> `lis:implements` **explanatoryNote**: “**The domain and range restrictions to disjunct classes
> ‘actual’ and ‘specified’** prevent chains of ‘implements’ relationships.”
>
> `lis:Specified` **usageNote**: “This class is not intended to be used directly, but only for
> serving as the domain of ‘implements’ and similar relations. **The disjointness axiom** serves to
> block iterated chains of ‘implements’, etc., relationships.”

This is the only candidate in the batch whose **full** route — range axiom *and* disjointness axiom —
is spelled out in prose, and it is spelled out twice. Rejected.

---

## 8. `robot reason` outcomes

**No candidate failed where unsatisfiability was expected.** All 32 produced an unsatisfiable named
class on the canonical graph; baseline (canonical, unmodified) is 0 unsatisfiable and the ontology
stays consistent in every run — none produced *inconsistency* rather than unsatisfiability, so the
convention is satisfied verbatim throughout and no extension was needed.

One mechanical note for anyone re-running this: ROBOT exits with **return code 1** whenever it finds
an unsatisfiable class. That is the success case here, and
`generate_bare_disjointness_candidates.robot_unsatisfiable_classes` already treats it that way
(it raises only when `returncode != 0` *and* no unsatisfiable class was parsed).

---

## 9. Gate gaps found — reported, not fixed

Per §7 of the brief, `recoverability.py` and the gate scripts were not modified.

### 9.1 `_turtle_chunk_has_axiom` misses every non-final member of an `owl:unionOf` list

`B05-D08` is the only candidate in the batch with a non-uniform profile
(`turtle=F`, all six other formats `T`). **It is a matcher artefact, not a serialisation
difference.** In the Turtle chunk both union members are equally present:

```turtle
lis:contains rdfs:domain [ rdf:type owl:Class ;
                           owl:unionOf ( lis:Location
                                         lis:PhysicalObject ) ] ;
```

The `nested` pattern in `_turtle_chunk_has_axiom` ends with the lookahead
`(?=\s*(?:[;,.]|\]|\)|$))`, which only succeeds for the union member immediately preceding the
closing paren. Scoped across all five union-valued domain/range axioms in IDO:

| axiom | member | position | turtle | other six formats |
| --- | --- | --- | --- | --- |
| `lis:concretizes rdfs:domain` | `lis:Activity` | 1 of 2 | **false** | true |
| `lis:concretizes rdfs:domain` | `lis:PhysicalObject` | last | true | true |
| `lis:contains rdfs:domain` | `lis:Location` | 1 of 2 | **false** | true |
| `lis:contains rdfs:domain` | `lis:PhysicalObject` | last | true | true |
| `lis:contains rdfs:range` | `lis:Location` | 1 of 2 | **false** | true |
| `lis:contains rdfs:range` | `lis:PhysicalObject` | last | true | true |
| `lis:hasInterest rdfs:domain` | `lis:Organism` | 1 of 2 | **false** | true |
| `lis:hasInterest rdfs:domain` | `lis:Organization` | last | true | true |
| `lis:hasSpatialExtent rdfs:domain` | `lis:Location` | 1 of 2 | **false** | true |
| `lis:hasSpatialExtent rdfs:domain` | `lis:PhysicalObject` | last | true | true |

The pattern is entirely positional: last member true, every earlier member false, in all five cases.

**Live risk to a committed item.** Pilot **T03**’s licensing axiom is
`[lis:concretizes, rdfs:domain, lis:PhysicalObject]`, and its stored all-true profile survives *only*
because `lis:PhysicalObject` happens to be the last member of that union. Had the author recorded
`lis:Activity` — equally correct, since the domain is a union of the two — T03 would carry a spurious
`turtle=false`. Any future union-domain item is exposed the same way.

`B05-D08` is dropped from the pool on this basis: its one interesting property (a non-uniform
profile) is not real, and it is also the only candidate whose route cannot be recorded in a single
connected chain (see §9.3).

### 9.2 `licensing_axiom_status` has no value that fits a composed contradicted item

`schemas.Task.derived_licensing_axiom_status` derives the status **structurally**: a multi-link chain
is `entailed_chain`, a single triple is `asserted`. A composed contradicted item needs two links, so
it validates as `entailed_chain` — but **both of its links are directly asserted in the canonical
graph; neither is entailed**, and `benchmark/schema.md`’s own table says `entailed_chain` means “ordered
connected chain from the ROBOT/HermiT explanation” and applies to “supported (near, distant)”, with
`contradicted` listed only under `asserted`.

So every composed candidate in this batch is a combination the schema documentation does not
anticipate: **contradicted + entailed_chain**. It loads and validates cleanly — the derivation is
purely structural, so nothing breaks — but the stored label is descriptively wrong for these items.
Three options, all the author’s call:

1. Accept `entailed_chain` and note the widened meaning in the methods chapter. Requires no code or
   schema change. Recommended, as the least invasive.
2. Record only one link as a single `asserted` triple, the way T03 does
   (`[lis:concretizes, rdfs:domain, lis:PhysicalObject]`). This loses half the route and contradicts
   the brief’s instruction to use “chain form where composed”.
3. Change the schema. Out of scope here and forbidden by §7.

The functional-property candidates are unaffected: a single `asserted` triple,
`[lis:datumUOM, rdf:type, owl:FunctionalProperty]`, is exactly right for them.

### 9.3 A connected chain cannot express a union-domain route

`licensing_axiom` chains are validated as ordered and connected (`left[2] == right[0]`). For
`B05-D08`, `lis:Organization` must be shown disjoint from **both** disjuncts of
`(lis:Location ⊔ lis:PhysicalObject)`, which needs two disjointness links branching off one domain
link — not expressible as a single connected chain. The recorded chain would capture only the
`lis:Location` disjunct, understating the route. Second reason to drop `B05-D08`; a general
limitation for any future union-domain item.

---

## 10. Verification record

Everything in this report is reproducible with:

```bash
export ROBOT_JAR=/path/to/robot.jar   # ROBOT 1.9.10, Temurin JDK 16.0.2
cd src/rag && ./.venv/Scripts/python.exe -m scripts.check_authoring_candidate <draft.yaml>
```

- **ROBOT/HermiT**: 32 candidates × 2 `reason` runs (canonical, disjointness-stripped) + 2 `explain`
  runs each, plus 12 chunked `reason` runs for the §2 proof and 4 baseline/control runs — 148 runs,
  0 unexpected failures.
- **`check_authoring_candidate`**: run on all 32 drafts. `gate_verdict: pass` for all 32, no
  `errors` returned on any.
- **Stored-profile check (stop condition 5)**: every stored `recoverability_profile` in both
  `tasks.yaml` (T01, T03, T04) and `tasks_60.yaml` (T06–T18) was recomputed with
  `assess_draft_recoverability` and compared with its stored value. **16 checked, 0 mismatches.**
- **Cost**: zero API calls.

## 11. Stop-condition status

| # | condition | status |
| --- | --- | --- |
| 1 | fewer than 20 candidates survive | **not fired** — 27 survive |
| 2 | a stratum yields fewer than double its requirement | **FIRED, twice** — `direct_domain_range` 0/6, `functional_property` 3/4 |
| 3 | `robot reason` fails where unsatisfiability was expected | not fired — 32/32 produced an unsatisfiable named class |
| 4 | a candidate needs the convention extended | not fired — every candidate makes a **named** class unsatisfiable, no A-Box item was authored, no inconsistency-only outcome |
| 5 | checker errors, or a stored profile disagrees with its recomputed value | not fired — 32/32 gate `pass`, 16/16 stored profiles match |
| 6 | information needed from a forbidden path | not fired — sources were the ontology, the seven corpora, `schemas.py`, `recoverability.py`, `tasks.yaml`, `tasks_60.yaml`, `benchmark/schema.md`, the two named scripts, and `docs/findings/functional-property-stratum.md` |

### What the author needs to decide

1. **Where the 3 `direct_domain_range` items go.** The stratum is provably empty (§2). `composed`
   can absorb them.
2. **Whether `functional_property` stays at 2.** Only 3 candidates survive and they rest on
   2 underlying axioms — F05 is a cardinality-phrasing variant of F01, not an independent item. The
   stratum cannot supply more than 2 genuinely distinct items, because LIS-14 declares exactly 2
   functional properties and the `lis:ScalarQuantityDatum` phrasings are `states_axiom` rejections.
3. **Whether partial (link-1) prose leakage is acceptable** in the composed stratum. Accepting it
   leaves 24 candidates; rejecting it leaves 4.
4. **Whether `contradicted` + `entailed_chain` is acceptable** as a `licensing_axiom_status`
   combination (§9.2).
