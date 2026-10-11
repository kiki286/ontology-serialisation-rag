# Benchmark task schema (`tasks.yaml`)

`tasks.yaml` is a YAML list of task objects. It is validated on load by the
pydantic models in `experiment/schemas.py` — a missing required field, an
unknown `task_type`, or a referenced `entity_id` that does not resolve in all
formats fails fast with a clear error.

During authoring, assess one draft without a complete benchmark:
`python -m scripts.check_authoring_candidate path/to/draft.yaml`. Before a run,
load the complete set with the 60-item constraints enabled:
`python -m scripts.verify_authoring_constraints`.

## Cross-format rule

All references to ontology content use the format-stable `entity_id`
(e.g. `lis:Person`, `lis:hasQuality`), never the format-scoped `chunk_id`
(e.g. `turtle:lis:Person`). The same `entity_id` resolves in Turtle, ELOT
Org-mode, and OMN.

> Note: synthesised axiom chunks (disjointness/equivalence) are not
> format-stable. Prefer naming the participating classes/properties. If a task
> must cite an axiom chunk, use the optional `gold_chunks_by_format` override.

## Common fields (all tasks)

| field          | type        | required | meaning                                                   |
|----------------|-------------|----------|-----------------------------------------------------------|
| `task_id`      | string      | yes      | Stable id, e.g. `T01`.                                     |
| `task_type`    | enum        | yes      | `verification` or `slot_filling`.                         |
| `query`        | string      | yes      | Retrieval query (retrieved condition + RQ1 scoring).      |
| `reasoning_type` | enum      | yes      | Answer route: `direct_assertion`, `structural`, `modelling_pattern`, or `definitional`. |
| `query_source` | enum        | yes      | Wording source: `label`, `definition`, `example`, or `paraphrase`. |
| `mechanism`    | string      | yes      | Authoring-time mechanism stratum, such as `bare_disjointness`, `domain_range`, or `functional_property`. |
| `gold_chunks`  | list[str]   | yes      | `entity_id`s used for oracle context. Include chunks needed to support the response rubric. |
| `gold_chunks_by_format` | map | no       | Optional oracle-context per-format override (turtle/elot-org/elot-org-ancestors/omn lists). |
| `retrieval_gold_chunks` | list[str] | no | Narrow `entity_id` set used for retrieval scoring. Defaults to `gold_chunks` when omitted. |
| `retrieval_gold_chunks_by_format` | map | no | Optional retrieval-scoring per-format override. |
| `recoverability_profile` | map[str, bool] | verification only | Stored seven-format direct-axiom profile; computed by the authoring assessor for determinate verification items. |
| `notes`        | string      | no       | Free-text annotation rationale (not used by the harness). |

For verification items, `licensing_axiom` is a nullable `[subject, predicate, object]`
triple or an ordered list of those triples forming a connected chain. A chain's
`gold_chunks` must contain every link subject and object. It is required for every
verification item. For undetermined items it records the hypothetical triple
that would license the candidate if IDO asserted it; recoverability explicitly
skips this class.

Every verification item also carries `licensing_axiom_status`, recording what
relationship the axiom bears to the canonical graph:

| value | meaning | applies to |
|---|---|---|
| `asserted` | the triple appears directly in the canonical graph | supported (immediate), contradicted |
| `entailed_chain` | ordered connected chain from the ROBOT/HermiT explanation | supported (near, distant) |
| `hypothetical` | the relation IDO would need to assert for the claim to hold; **not in the graph** | undetermined |

The stored value is derivable from the item's own content (a chain is
`entailed_chain`, a single directly-serialized triple is `asserted`, an
undetermined item's axiom is `hypothetical`) and is cross-checked against that
derivation on load, so a stored status that disagrees with the axiom fails
validation. Every branch that treats a licensing axiom as true — the
recoverability assessor and the authoring gates — branches on this field, never on
a `licensing_axiom is None` test, so a missing field can never be read as
hypothetical. An undetermined item cannot load unless its status is `hypothetical`,
and the classes named in a `hypothetical` axiom must all be in `gold_chunks`.
`recoverability_profile` stays required-and-null for `hypothetical` items.
`licensing_axiom_status` is enforced-present on every verification item at the
authoring gate; it is nullable in the base model only so the frozen five-item
pilot still loads.

Undetermined items additionally require `axiom` and
`negated_axiom`, both in ROBOT Manchester syntax, for the canonical-graph
two-sided non-entailment gate, plus `annotation_prose_screen: passed`. That screen
records that `naturalLanguageDefinition`/`usageNote` prose on the gold chunks does
not settle either side of the claim. The gate rejects missing or failed screens
before checking two-sided non-entailment. Every gold-bearing chunk id must also be
eligible for the retrieval index; excluded document/root chunks cannot be used as
oracle gold.

## Gold Chunk Policy

`retrieval_gold_chunks` answers: what should the retriever find from `query`
alone? These chunks are used for the headline Recall@k, MRR, and nDCG@k.

`gold_chunks` answers: what chunks should be available in the oracle condition
so the LLM can justify the response rubric? This set can be broader than
`retrieval_gold_chunks`, especially for slot-filling tasks where the scenario
requires class/background support that is not a direct retrieval target.

If `retrieval_gold_chunks` is omitted, retrieval metrics fall back to
`gold_chunks`.

RQ1 also reports a secondary `gold_recall_at_k` against the broader
`gold_chunks` set. This measures whether retrieval found useful oracle/context
chunks, including background that may not be directly requested by the query.

## `verification` fields

| field                      | type   | required | meaning                                                                 |
|----------------------------|--------|----------|-------------------------------------------------------------------------|
| `statement`                | string | yes      | The candidate modelling statement to judge.                             |
| `gold_label`               | enum   | yes      | `supported` / `contradicted` / `undetermined`.                          |
| `licensing_axiom`          | list   | yes      | One `[subject, predicate, object]` triple or an ordered connected list of triples. For undetermined items, the hypothetical triple that would license the claim. |
| `licensing_axiom_status`   | enum   | yes      | `asserted` / `entailed_chain` / `hypothetical`. Derived from and cross-checked against the axiom's content; required-present at the authoring gate. |
| `axiom`                    | string | conditional | ROBOT Manchester axiom required for undetermined items.                 |
| `negated_axiom`            | string | conditional | Formal contradiction required for undetermined items.                  |
| `annotation_prose_screen`  | enum   | conditional | Undetermined: `passed`/`failed`; contradicted: `toward`/`away`/`neutral`/`states_axiom`. `states_axiom` flags annotation prose that states the licensing axiom and is unsuitable for formal-legibility testing except as a deliberate contrast class. |
| `recoverability_profile`   | map    | conditional | Seven booleans, one per core format; required and checked for determinate items. |

## `slot_filling` fields

| field                   | type   | required | meaning                                        |
|-------------------------|--------|----------|------------------------------------------------|
| `scenario`              | string | yes      | The modelling scenario.                        |
| `gold_class`            | string | yes      | Correct IDO class (`entity_id`).               |
| `gold_property`         | string | yes      | Correct linking property (`entity_id`).        |
| `gold_intermediate_node`| bool   | yes      | Whether a Quality/QuantityValue node is needed.|
| `primary_answer_chunk`  | string | no       | Main answer chunk to track in retrieval raw rows for error analysis only; not used in headline metrics. |
| `gold_supporting_chunks`| map    | yes      | `{class, property, intermediate_node}` -> `entity_id` supporting each decision; `intermediate_node` may be `null` when no intermediate node is required. |
