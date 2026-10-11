# Deterministic Voicebox-Style Schema Concept Chunking for LIS-14

## Purpose

This document specifies a deterministic method for creating **Voicebox-style schema concept chunks** for an ontology such as **LIS-14 / IDO**.

The goal is to create an exploratory, industry-adjacent baseline for RAG over ontologies that is closer to a schema-aware assistant than naïve raw-file chunking.

This condition is inspired by the public Stardog Voicebox developer guidance, which states that Voicebox uses schema labels/descriptions, class hierarchy, property domain/range, and stored/example queries to support SPARQL generation. For Stardog schema elements specifically, `rdfs:label` and `rdfs:comment` are used as labels/comments; however, LIS-14 uses additional annotation conventions such as `iof-av:naturalLanguageDefinition`, `skos:example`, and `skos:scopeNote`, so this method adapts the idea to LIS-14 while remaining deterministic.

This condition should **not** be treated as another ontology serialization format. It is a **schema-concept indexing representation**.

---

## 1. Design Principle

The chunking strategy is:

```text
One chunk per schema concept.
Each chunk contains human-readable labels/descriptions plus minimal formal schema context.
No raw TTL/JSON-LD/OWL serialization chunks.
No LLM-generated summaries.
No full graph neighbourhood expansion.
```

The guiding assumption is:

```text
For ontology-assisted SPARQL generation, the most useful retrieval units are schema concepts,
not arbitrary slices of the ontology source file.
```

---

## 2. Entity Types Included

Generate chunks for:

```text
owl:Class
owl:ObjectProperty
owl:DatatypeProperty
```

Optional, but disabled by default:

```text
owl:AnnotationProperty
owl:NamedIndividual
```

Default recommendation for the honours experiment:

```text
include:
  - owl:Class
  - owl:ObjectProperty
  - owl:DatatypeProperty

exclude:
  - owl:AnnotationProperty
  - owl:NamedIndividual
```

Reason: the aim is schema retrieval, not instance-level document retrieval.

---

## 3. Chunk Types

Use three chunk types:

```text
class_schema_concept
object_property_schema_concept
datatype_property_schema_concept
```

Each chunk has:

```text
chunk_id
primary_entity
entity_type
canonical_label
description
minimal_schema_context
examples_or_usage_notes, capped
retrieval_terms, optional
metadata
```

---

## 4. Global Parameters

```python
MAX_LABELS = 4
MAX_DESCRIPTIONS = 2
MAX_EXAMPLES = 2
MAX_NOTES = 1
MAX_DIRECT_SUPERCLASSES = 3
MAX_DIRECT_SUBCLASSES = 5
MAX_DOMAINS = 3
MAX_RANGES = 3
MAX_INVERSES = 1
MAX_SUPERPROPERTIES = 3
MAX_SUBPROPERTIES = 5
MAX_EQUIVALENT_CLASSES = 2
MAX_DISJOINT_CLASSES = 3
MAX_RETRIEVAL_TERMS = 20

CHUNK_TARGET_WORDS = 150
CHUNK_SOFT_MAX_WORDS = 350
CHUNK_HARD_MAX_WORDS = 500
```

This condition should stay compact. If chunks regularly exceed 500 words, the condition has drifted toward neighbourhood GraphRAG rather than schema concept indexing.

---

## 5. LIS-14 Annotation Mapping

Stardog Voicebox documentation specifically names `rdfs:label` and `rdfs:comment` for schema labels/comments. LIS-14 often uses richer annotation predicates. Therefore, this condition defines a deterministic LIS-14-compatible mapping from ontology annotations into the two core fields:

```text
label
description
```

### 5.1 Label Sources

For each entity `E`, collect labels from these predicates in priority order:

```text
1. rdfs:label
2. skos:prefLabel
3. skos:altLabel
4. iof-av:synonym
5. local name from IRI, if no explicit label exists
```

Rules:

```text
- Preserve original capitalization.
- Deduplicate exact duplicate labels.
- Include max MAX_LABELS labels.
- First label becomes canonical_label.
- Additional labels become aliases.
```

### 5.2 Description Sources

For each entity `E`, collect description-like literals from these predicates in priority order:

```text
1. rdfs:comment
2. iof-av:naturalLanguageDefinition
3. skos:definition
4. dcterms:description
5. schema:description
6. iof-av:semiFormalNaturalLanguageDefinition
7. iof-av:semiFormalNaturalLanguageAxiom
8. iof-av:usageNote
9. skos:scopeNote
```

Rules:

```text
- Include max MAX_DESCRIPTIONS description-like literals.
- Prefer concise natural-language definitions over long explanatory notes.
- Preserve original wording.
- Do not summarize or rewrite.
- If no description exists, omit the description field rather than generating one.
```

### 5.3 Examples

Collect examples from:

```text
skos:example
```

Rules:

```text
- Include max MAX_EXAMPLES examples.
- Prefer shorter examples.
- Preserve original wording.
- Truncate only at sentence boundaries if needed.
```

### 5.4 Notes

Collect notes from:

```text
1. skos:scopeNote
2. iof-av:usageNote
3. iof-av:explanatoryNote
4. iof-av:primitiveRationale
```

Rules:

```text
- Include max MAX_NOTES.
- Prefer notes attached directly to the entity.
- Exclude explanatory notes attached only to external alignment axioms, unless no other definition/description exists.
```

---

## 6. Class Schema Concept Chunks

For each `owl:Class` entity `C`, generate one chunk.

### 6.1 Included Fields

Include these fields, in this exact order:

```text
CHUNK ID
ENTITY
TYPE
LABEL
ALIASES
DESCRIPTION
SCHEMA CONTEXT
EXAMPLES
NOTES
RETRIEVAL TERMS
```

### 6.2 Schema Context for Classes

For classes, include only minimal formal context:

```text
Direct superclass(es)
Direct subclass(es)
Equivalent class(es), optional and capped
Disjoint class(es), optional and capped
```

Do **not** include by default:

```text
- full restrictions
- property chains
- all adjacent properties
- all incoming/outgoing relations
- external ontology alignments
- all ancestors
- all descendants
```

This is intentionally lighter than an entity-neighbourhood representation.

### 6.3 Optional Restriction Summary

For LIS-14, some classes are defined heavily through OWL restrictions. To avoid losing all formal meaning, restrictions may be included only if they are direct and compact.

Include restrictions only when:

```text
C rdfs:subClassOf [ owl:onProperty P ; owl:someValuesFrom / owl:allValuesFrom / owl:hasValue X ]
```

Rules:

```text
- Include max 2 direct restrictions.
- Render as compact Manchester-style text.
- Exclude cardinality restrictions unless they are central to the class definition.
- Exclude complex nested anonymous expressions unless they can be rendered in one line.
```

Example:

```text
Restriction: lis:hasParticipant some lis:PhysicalObject
```

### 6.4 Class Chunk Template

```text
CHUNK ID:
class:{CURIE}:schema_concept

ENTITY:
{CURIE}

TYPE:
owl:Class

LABEL:
{canonical_label}

ALIASES:
- {alias_1}
- {alias_2}

DESCRIPTION:
{description_1}
{description_2 optional}

SCHEMA CONTEXT:
Direct superclass(es): {superclasses}
Direct subclass(es): {subclasses}
Restriction(s): {compact direct restrictions, optional}
Disjoint with: {disjoint classes, optional}

EXAMPLES:
- {example_1}
- {example_2}

NOTES:
{note_1}

RETRIEVAL TERMS:
{deterministically generated terms}
```

---

## 7. Object Property Schema Concept Chunks

For each `owl:ObjectProperty` entity `P`, generate one chunk.

### 7.1 Included Fields

Include these fields, in this exact order:

```text
CHUNK ID
ENTITY
TYPE
LABEL
ALIASES
DESCRIPTION
SCHEMA CONTEXT
EXAMPLES
NOTES
RETRIEVAL TERMS
```

### 7.2 Schema Context for Object Properties

For object properties, include:

```text
Domain(s)
Range(s)
Inverse property, if present
Direct superproperty/properties
Direct subproperty/properties
Property characteristics, if present
```

Do not include by default:

```text
- full property chain explanations
- all examples from related classes
- all external alignments
- long usage notes from inverse properties
```

### 7.3 Property Chain Flag

LIS-14 uses property chains for some important properties. Include only a compact flag by default:

```text
Property chain involvement: yes
```

Optionally include compact chains only for property chunks, not class chunks:

```text
Property chain: lis:hasActivityPart o lis:hasParticipant -> lis:hasParticipant
```

Rules:

```text
- Include max MAX_PROPERTY_CHAINS if property chains are enabled.
- Preserve exact CURIEs.
- Do not paraphrase inferred semantics unless the ontology itself provides a note.
```

### 7.4 Object Property Chunk Template

```text
CHUNK ID:
object_property:{CURIE}:schema_concept

ENTITY:
{CURIE}

TYPE:
owl:ObjectProperty

LABEL:
{canonical_label}

ALIASES:
- {alias_1}
- {alias_2}

DESCRIPTION:
{description_1}
{description_2 optional}

SCHEMA CONTEXT:
Domain: {domain classes}
Range: {range classes}
Inverse: {inverse property optional}
Superproperty: {superproperties optional}
Subproperties: {subproperties optional}
Characteristics: {functional/symmetric/transitive/etc optional}
Property chain involvement: {yes/no}

EXAMPLES:
- {example_1}
- {example_2}

NOTES:
{note_1}

RETRIEVAL TERMS:
{deterministically generated terms}
```

---

## 8. Datatype Property Schema Concept Chunks

For each `owl:DatatypeProperty` entity `D`, generate one chunk.

### 8.1 Included Fields

Include:

```text
label(s)
description(s)
domain(s)
range datatype(s)
superproperty/properties
subproperty/properties
functional property flag, if present
examples
notes
```

### 8.2 Datatype Property Chunk Template

```text
CHUNK ID:
datatype_property:{CURIE}:schema_concept

ENTITY:
{CURIE}

TYPE:
owl:DatatypeProperty

LABEL:
{canonical_label}

ALIASES:
- {alias_1}
- {alias_2}

DESCRIPTION:
{description_1}
{description_2 optional}

SCHEMA CONTEXT:
Domain: {domain classes}
Range: {range datatypes}
Superproperty: {superproperties optional}
Subproperties: {subproperties optional}
Characteristics: {functional/etc optional}

EXAMPLES:
- {example_1}
- {example_2}

NOTES:
{note_1}

RETRIEVAL TERMS:
{deterministically generated terms}
```

---

## 9. Retrieval Terms

Retrieval terms are optional but useful for transparent evaluation.

They must be generated only from existing source strings.

Allowed sources:

```text
- CURIE local name
- rdfs:label
- skos:prefLabel
- skos:altLabel
- iof-av:synonym
- selected descriptions
- selected examples
- domain/range labels for properties
- superclass/subclass labels for classes
```

Forbidden sources:

```text
- LLM-generated synonyms
- manually invented keywords
- external thesaurus expansion unless pre-declared
```

Recommended deterministic procedure:

```python
def generate_retrieval_terms(profile):
    terms = []
    terms.extend(tokenize_local_name(profile.curie))
    terms.extend(tokenize_literals(profile.labels))
    terms.extend(tokenize_literals(profile.aliases))
    terms.extend(tokenize_literals(profile.descriptions))
    terms.extend(tokenize_literals(profile.examples))
    terms.extend(tokenize_literals(profile.schema_context_labels))

    terms = normalize_case(terms)
    terms = split_camel_case(terms)
    terms = remove_punctuation(terms)
    terms = remove_stopwords(terms)
    terms = deduplicate_preserve_order(terms)

    return terms[:MAX_RETRIEVAL_TERMS]
```

If this introduces too much implementation complexity, omit the retrieval terms field entirely.

---

## 10. Truncation Rules

If a chunk exceeds `CHUNK_HARD_MAX_WORDS`, drop fields in this order:

```text
1. RETRIEVAL TERMS
2. NOTES
3. EXAMPLES beyond the first
4. DIRECT SUBCLASSES beyond first 3
5. DISJOINT WITH
6. EQUIVALENT CLASS
7. SECOND DESCRIPTION
8. ALIASES beyond first 2
```

Never drop:

```text
- CHUNK ID
- ENTITY
- TYPE
- LABEL or generated local-name label
- first DESCRIPTION if present
- DOMAIN/RANGE for properties
- DIRECT SUPERCLASS for classes, if present
```

---

## 11. Pseudocode

### 11.1 Main Pipeline

```python
def build_voicebox_style_schema_chunks(graph):
    chunks = []

    classes = get_entities_of_type(graph, OWL.Class)
    object_properties = get_entities_of_type(graph, OWL.ObjectProperty)
    datatype_properties = get_entities_of_type(graph, OWL.DatatypeProperty)

    for C in sorted(classes, key=curie):
        profile = extract_class_schema_profile(graph, C)
        text = render_class_schema_chunk(profile)
        text = enforce_chunk_budget(text)
        chunks.append(make_chunk_record(profile, text, "class_schema_concept"))

    for P in sorted(object_properties, key=curie):
        profile = extract_object_property_schema_profile(graph, P)
        text = render_object_property_schema_chunk(profile)
        text = enforce_chunk_budget(text)
        chunks.append(make_chunk_record(profile, text, "object_property_schema_concept"))

    for D in sorted(datatype_properties, key=curie):
        profile = extract_datatype_property_schema_profile(graph, D)
        text = render_datatype_property_schema_chunk(profile)
        text = enforce_chunk_budget(text)
        chunks.append(make_chunk_record(profile, text, "datatype_property_schema_concept"))

    return chunks
```

### 11.2 Class Profile Extraction

```python
def extract_class_schema_profile(graph, C):
    return {
        "entity": C,
        "curie": curie(C),
        "type": "owl:Class",
        "labels": get_labels(graph, C),
        "aliases": get_aliases(graph, C),
        "descriptions": get_descriptions(graph, C, max_items=MAX_DESCRIPTIONS),
        "examples": get_examples(graph, C, max_items=MAX_EXAMPLES),
        "notes": get_notes(graph, C, max_items=MAX_NOTES),
        "direct_superclasses": get_direct_named_superclasses(graph, C, MAX_DIRECT_SUPERCLASSES),
        "direct_subclasses": get_direct_named_subclasses(graph, C, MAX_DIRECT_SUBCLASSES),
        "compact_restrictions": get_compact_direct_restrictions(graph, C, max_items=2),
        "equivalent_classes": get_named_equivalent_classes(graph, C, MAX_EQUIVALENT_CLASSES),
        "disjoint_classes": get_disjoint_classes(graph, C, MAX_DISJOINT_CLASSES),
    }
```

### 11.3 Object Property Profile Extraction

```python
def extract_object_property_schema_profile(graph, P):
    return {
        "entity": P,
        "curie": curie(P),
        "type": "owl:ObjectProperty",
        "labels": get_labels(graph, P),
        "aliases": get_aliases(graph, P),
        "descriptions": get_descriptions(graph, P, max_items=MAX_DESCRIPTIONS),
        "examples": get_examples(graph, P, max_items=MAX_EXAMPLES),
        "notes": get_notes(graph, P, max_items=MAX_NOTES),
        "domains": get_named_domains(graph, P, MAX_DOMAINS),
        "ranges": get_named_ranges(graph, P, MAX_RANGES),
        "inverse": get_inverse_property(graph, P),
        "superproperties": get_direct_superproperties(graph, P, MAX_SUPERPROPERTIES),
        "subproperties": get_direct_subproperties(graph, P, MAX_SUBPROPERTIES),
        "characteristics": get_property_characteristics(graph, P),
        "property_chain_involvement": appears_in_property_chain(graph, P),
        "property_chains": get_property_chains(graph, P, max_items=MAX_PROPERTY_CHAINS),
    }
```

### 11.4 Datatype Property Profile Extraction

```python
def extract_datatype_property_schema_profile(graph, D):
    return {
        "entity": D,
        "curie": curie(D),
        "type": "owl:DatatypeProperty",
        "labels": get_labels(graph, D),
        "aliases": get_aliases(graph, D),
        "descriptions": get_descriptions(graph, D, max_items=MAX_DESCRIPTIONS),
        "examples": get_examples(graph, D, max_items=MAX_EXAMPLES),
        "notes": get_notes(graph, D, max_items=MAX_NOTES),
        "domains": get_named_domains(graph, D, MAX_DOMAINS),
        "ranges": get_literal_ranges(graph, D, MAX_RANGES),
        "superproperties": get_direct_superproperties(graph, D, MAX_SUPERPROPERTIES),
        "subproperties": get_direct_subproperties(graph, D, MAX_SUBPROPERTIES),
        "characteristics": get_property_characteristics(graph, D),
    }
```

---

## 12. Example Class Chunk: `lis:Activity`

```text
CHUNK ID:
class:lis.Activity:schema_concept

ENTITY:
lis:Activity

TYPE:
owl:Class

LABEL:
Activity

DESCRIPTION:
A temporal entity in which one or more physical objects participate.

SCHEMA CONTEXT:
Direct superclass(es): lis:Temporal
Direct subclass(es): lis:ActivityProfile; lis:Event
Restriction(s): lis:hasParticipant some lis:PhysicalObject
Disjoint with: lis:SpatiotemporalRegion; lis:TemporalRegion

EXAMPLES:
- A pumping, an inspection, a report writing, a fastening.

NOTES:
An Activity may have temporal gaps. For example, intermittent operation of a heater over a week may be represented by a single Activity individual.

RETRIEVAL TERMS:
activity; temporal; physical; object; participate; pumping; inspection; report; writing; fastening; activity profile; event
```

---

## 13. Example Object Property Chunk: `lis:hasParticipant`

```text
CHUNK ID:
object_property:lis.hasParticipant:schema_concept

ENTITY:
lis:hasParticipant

TYPE:
owl:ObjectProperty

LABEL:
hasParticipant

DESCRIPTION:
If x has participant y, then x is an Activity, and y is an Object that participates in x.

SCHEMA CONTEXT:
Domain: lis:Activity
Range: lis:Object
Inverse: lis:participantIn
Subproperties: lis:hasActiveParticipant; lis:hasPassiveParticipant; lis:hasPrimaryParticipant
Property chain involvement: yes

EXAMPLES:
- A pump participates in pumping.
- An electric transformer participates in voltage conversion.

NOTES:
A property chain axiom secures that a participant in part of an activity participates in the activity as a whole.

RETRIEVAL TERMS:
has participant; participant; activity; object; active participant; passive participant; primary participant; pumping; voltage conversion
```

---

## 14. Example Datatype Property Chunk: `lis:datumValue`

```text
CHUNK ID:
datatype_property:lis.datumValue:schema_concept

ENTITY:
lis:datumValue

TYPE:
owl:DatatypeProperty

LABEL:
datumValue

DESCRIPTION:
If x datum value y, then x is a QualityDatum, and y is the literal value of x.

SCHEMA CONTEXT:
Domain: lis:QualityDatum
Range: literal value
Characteristics: FunctionalProperty

EXAMPLES:
- The measured datum "55 degrees Celsius" has "55" as literal value.

NOTES:
A literal value is uninterpreted. Provide a unit of measure, or other category, for a QualityDatum to be interpretable.

RETRIEVAL TERMS:
datum value; quality datum; literal value; measured datum; unit of measure
```

---

## 15. Metadata for Each Chunk

Each chunk should be saved with metadata like:

```json
{
  "chunk_id": "class:lis.Activity:schema_concept",
  "chunk_type": "class_schema_concept",
  "primary_entity": "http://rds.posccaesar.org/ontology/lis14/rdl/Activity",
  "primary_curie": "lis:Activity",
  "entity_type": "owl:Class",
  "included_entities": [
    "lis:Activity",
    "lis:Temporal",
    "lis:ActivityProfile",
    "lis:Event",
    "lis:hasParticipant",
    "lis:PhysicalObject"
  ],
  "included_predicates": [
    "rdfs:label",
    "iof-av:naturalLanguageDefinition",
    "skos:example",
    "skos:scopeNote",
    "rdfs:subClassOf",
    "owl:onProperty",
    "owl:someValuesFrom",
    "owl:disjointWith"
  ]
}
```

---

## 16. How This Differs From Raw Serialization Chunking

Raw serialization chunking:

```text
ontology file text → token chunks → embeddings
```

Voicebox-style schema concept chunking:

```text
ontology graph → schema entities → labels/descriptions/minimal schema context → embeddings
```

The latter changes the unit of retrieval from arbitrary text spans to schema concepts.

---

## 17. How This Differs From Full GraphRAG

This condition does **not** do:

```text
- query-time graph traversal
- dynamic SPARQL generation
- vector + symbolic reranking
- path retrieval
- graph community detection
- pattern chunking
- LLM-generated ontology summaries
```

It is deliberately simpler:

```text
static schema concept chunks + normal vector retrieval
```

This makes it suitable as an exploratory baseline in a study focused primarily on serialization format effects.

---

## 18. Recommended Thesis Framing

Suggested methods wording:

```text
In addition to raw serialization-based RAG, an exploratory schema-concept chunking condition was included. This condition was inspired by commercial ontology assistants that use schema labels, descriptions, hierarchy, and domain/range information to ground natural-language interaction with knowledge graphs. For each ontology class or property, a deterministic chunk was generated containing its labels, LIS-14 definition annotations, examples, notes, and minimal schema context such as direct superclasses or property domain/range. The condition is not treated as another serialization format, but as a lightweight ontology-aware indexing baseline.
```

Suggested limitation:

```text
This condition approximates schema-aware retrieval but does not replicate any proprietary vendor implementation. It also omits richer graph-aware retrieval steps such as query-time traversal, text-to-SPARQL generation, and structural reranking.
```

---

## 19. Things Not To Do

Avoid:

```text
- using an LLM to write or summarize descriptions
- adding synonyms not present in the ontology
- including full one-hop neighbourhoods
- including all OWL restrictions and property chains in every class chunk
- changing the annotation mapping after seeing final evaluation results
- treating this as a serialization format
```

---

## 20. Summary

The recommended Voicebox-style LIS-14 chunking condition is:

```text
One chunk per class/property.
Use human-authored labels, definitions, examples, and notes.
Adapt LIS-14 annotations such as iof-av:naturalLanguageDefinition into the description field.
Include minimal schema context only:
  - classes: direct superclass/subclass, compact direct restrictions, selected disjointness
  - properties: domain, range, inverse, super/subproperty, property-chain flag
Avoid full graph neighbourhoods.
Avoid LLM-generated text.
Keep chunks short and deterministic.
```
