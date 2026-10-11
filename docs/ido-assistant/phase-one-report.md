# IDO Assistant - Phase One

## Overview

The IDO Assistant is a Retrieval-Augmented Generation (RAG) web application designed to introduce the Industrial Data Ontology (IDO) to businesses. It supports organisations, especially technology-oriented ones, that want to build IDO-aligned ontologies as part of their infrastructure.

### Purpose

The goal of the IDO Assistant is to lower the barrier for organisations to engage with IDO. Many businesses lack ontology expertise, and the Assistant provides an accessible, interactive way to learn IDO concepts, principles, and use cases.

### Objectives

* Provide accurate, source-grounded answers about IDO.
* Help organisations understand how to align their ontologies with IDO.
* Act as a trusted reference point by minimising hallucinations and surfacing authoritative sources.

### Phase One

Phase One of the IDO Assistant project originally focused on the overall architecture of the application (see [Requirements V1](requirements-v1.0.md) and [Architecture Overview V1](architecture-v1.0.md)). This direction changed mid-way through the project. After setting up the core docker-compose services, being the `frontend`, `backend`, `postgres`, and `rag` (see [README](../../README.md) for more details), the focus turned to the RAG component of the project and conducting experimentation to improve it.

This report focuses on the RAG component and is broken up into the following sections: Initial RAG Pipeline, Experiments & Findings, Final RAG Pipeline, and Future Work.

## Initial RAG Pipeline

The initial pipeline used LangChain to conduct vector similarity search over document chunks based on the user’s query during retrieval. Only four document chunks were retrieved (K=4), and the default LangChain prompt was used during generation. The retrieval sources included the ISO_15926-14 ontology Turtle file, the ISO_23726-1 Markdown document, and the website [https://rds.posccaesar.org/](https://rds.posccaesar.org/).

Markdown documents were chunked using LangChain’s `MarkdownHeaderTextSplitter`, splitting on level-3 headers. Website sitemaps were retrieved, and the content of each page (excluding deep ontology pages) was extracted using LangChain’s `WebBaseLoader`, with each page stored as a single chunk.

As far as we are aware, ontology Turtle documents have no established chunking methodology in RAG systems. Naively chunking these documents based on tokens would break their semantic structure and result in incomplete triples across chunks, making them difficult for an LLM to interpret. To address this, a custom loader was implemented. This loader parses a Turtle (RDF) file and groups all triples by subject, with each subject’s set of triples forming a single chunk. The full set of namespaces and prefixes is also appended to every chunk to ensure the chunk can be interpreted independently by the LLM. The following is an example chunk of the subject class `Site`:

```text
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix csvw: <http://www.w3.org/ns/csvw#> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcmitype: <http://purl.org/dc/dcmitype/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix dcam: <http://purl.org/dc/dcam/> .
@prefix doap: <http://usefulinc.com/ns/doap#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix geo: <http://www.opengis.net/ont/geosparql#> .
@prefix odrl: <http://www.w3.org/ns/odrl/2/> .
@prefix org: <http://www.w3.org/ns/org#> .
@prefix prof: <http://www.w3.org/ns/dx/prof/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix qb: <http://purl.org/linked-data/cube#> .
@prefix schema: <https://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix ssn: <http://www.w3.org/ns/ssn/> .
@prefix time: <http://www.w3.org/2006/time#> .
@prefix vann: <http://purl.org/vocab/vann/> .
@prefix void: <http://rdfs.org/ns/void#> .
@prefix wgs: <https://www.w3.org/2003/01/geo/wgs84_pos#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix xml: <http://www.w3.org/XML/1998/namespace> .
@prefix lis: <http://rds.posccaesar.org/ontology/lis14/rdl/> .
@prefix obo: <http://purl.obolibrary.org/obo/> .
@prefix pav: <http://purl.org/pav/> .
@prefix lis2: <http://rds.posccaesar.org/2008/02/OWL/ISO-15926-2_2003#> .
@prefix lis12: <http://standards.iso.org/iso/15926/ontology/life-cycle-integration/> .

Subject: lis:Site
Triples:
- lis:relatedEntityISO15926: lis2:RegionInSpace
- rdf:type: owl:Class
- lis:relatedEntityISO15926: lis2:SpatialLocation
- rdfs:comment: "From BFO: "b is a site means: b is a three-dimensional immaterial entity that is (partially or wholly) bounded by a material entity or it is a three-dimensional immaterial part thereof. (axiom label in BFO2 Reference: [034-002])""
- rdfs:comment: "This class is inspired by the BFO/Information Artefact Ontology class "site" (BFO_0000029)."
- rdfs:label: "Site"
- rdfs:seeAlso: obo:BFO_0000029
- rdfs:subClassOf: lis:Location')]","A location is defined as “An object that is a region in space” (example: An outdoor plant area, an opening in a wall, the space inside an enclosure) and a site is defined as “A location determined in relation to one or more physical objects.” (example: A flight deck, the inside of a manifold, the hold of a ship, a centre of gravity, an outside area)
```

## Experiments & Findings

Each trial tested the RAG pipeline against 24 competency questions and gold answers. Each answer was manually checked and rated as either Complete (fully aligned with gold answer), Partial (part of the core answer aligns with the gold), or Bad (the entire core of the answer is quite misaligned with the gold). 

### Trial 1

**Pipeline Summary:**
- Naive RAG
- K=4
- Default Prompt
- Retrieval Sources
    ISO_15926-14.ttl
    ISO_23726-1.md
    https://rds.posccaesar.org/

**Key Pipeline Changes:**
- N/A

### Trial 2

**Pipeline Summary:**
- Naive RAG
- K=20
- v1 Generation Prompt
- Retrieval Sources
    ISO_15926-14.ttl
    ISO_23726-1.md
    https://rds.posccaesar.org/

**Key Pipeline Changes:**
- Retrieved 20 chunks rather than 4 (K=20)
- Used [v1 Generation Prompt](../../src/rag/prompts/archive/naive_rag_prompts/v1_naive_rag_prompt.txt), incorporating key context about the IDO Assistant. 

### Trial 3

**Pipeline Summary:**
- Naive RAG
- K=20
- v2 Generation Prompt
- Retrieval Sources
    ISO_15926-14.ttl
    ISO_23726-1.md
    https://rds.posccaesar.org/
    LIS-14.tex
    obi-ido-training-session 2, 3, 8, 9

**Key Pipeline Changes:**
- Used [v2 Generation Prompt](../../src/rag/prompts/archive/naive_rag_prompts/v2_naive_rag_prompt.txt), which add that responses should be kept to a maximum of approximately 4 sentences.
- Added LIS-14.tex to the retrieval sources (which also meant using LangChain's LaTex splitter).
- Added YouTube transcripts of OBI IDO Training Sessions 2, 3, 8, and 9 to the retrieval sources as txt documents, which were chunked using chunk_size=1200 and chunk_overlap=100.

**Results:**
- Complete = 13
- Partial = 4
- Bad = 7

**Takeaways:**
- **Prompting & terminology:** The LLM isn’t well-aligned with ontology language (e.g. “concepts”). It likely needs clearer upfront context about ontologies and interchangeable terms.
- **Abstraction level ambiguity:** Questions about class membership should expect the most specific class possible; otherwise the model is forced to guess the intended level of abstraction.
- **Retrieval brittleness:** RAG performance is sensitive to wording (e.g. “annotation” vs “annotation property”) causing missed context.
- **Documentation gaps:** Some expected information (latest IDO updates, supported languages) isn’t present in the retrieval sources.
- **High-level knowledge loss in RAG:** Core IDO/OBI principles are spread across chunks and aren’t retrieved reliably; summary-style background context may be needed.
- **Lack of robust OBI understanding:** There’s a general lack of robust OBI understanding, likely due to a mix of weak grounding context.

### Trial 4

Invalid trial.

### Trial 5

Invalid trial.

### Trial 6

**Pipeline Summary:**
- Naive RAG
- K=20
- v5 Generation Prompt
- Retrieval Sources
    ISO_15926-14.ttl
    ISO_23726-1.md
    https://rds.posccaesar.org/
    LIS-14.tex
    obi-ido-training-session 2, 3, 8, 9
    disjointness.md 
    CII-FMEA.tex 
    modelling_Objects_in_IDO.md 
    ido-summary 
    obi-principles 

**Key Pipeline Changes:**
- Used [v5 Generation Prompt](../../src/rag/prompts/archive/naive_rag_prompts/v5_naive_rag_prompt.txt), which adds explicit ontology and OBI background, clarifies interchangeable ontology terminology, and situates IDO within the wider OBI ecosystem.
- Added disjointness.md to retrieval sources
- Added CII-FMEA.tex to retrieval sources
- Added modelling_Objects_in_IDO.md to retrieval sources
- Added summary documents which are NOT chunked and ALWAYS included as context for the LLM: IDO Summary and OBI Principles

**Results:**
- Complete = 15
- Partial = 5
- Bad = 4

**Takeaways:**
- Some questions are very retrieval sensitive. The queries have additional information in them which clouds retrieval? Consider query re-writing to ensure retrieval is focused on the relevant portions of the question.
- Questions about applying the ontology generally fail, where LLM is required to pick a class etc. Response should be that it is currently not possible.
- Questions requiring a list, e.g. the OBI Principles, are answered incorrectly because of the maximum 4 sentence constraint? Adjust prompt so that if a list is requested, prioritise giving the full list.
- IDO supported languages context still missing. Consider adding Key Updates and Future Work documents to the retrieval sources.

### Trial 7

**Pipeline Summary:**
- Naive RAG
- K=20
- v7 Generation Prompt
- Retrieval Sources
    ISO_15926-14.ttl
    ISO_23726-1.md
    https://rds.posccaesar.org/
    LIS-14.md
    obi-ido-training-session 2, 3, 8, 9
    disjointness.md 
    CII-FMEA.tex 
    modelling_Objects_in_IDO.md 
    modelling-facts.md
    ido-summary 
    obi-principles 

**Key Pipeline Changes:**
- Used [v7 Generation Prompt](../../src/rag/prompts/archive/naive_rag_prompts/v7_naive_rag_prompt.txt), which allows full lists as responses even if it breaches the 4-sentence constraint, and does NOT respond to ontology modelling questions.
- Added modelling-facts.md to retrieval sources.
- Changed chunking strategy of markdown to chunk at level-4 headers rather than level-3 for more fine-grained retrieval.

**Results:**
- Complete = 16
- Partial = 3
- Bad = 5

**Takeaways:**
- Still not giving top 5 classes for the "key concepts of IDO" question even though they are retrieved.
- It should NOT answer the failure effect question but I think it believes CII-FMEA.tex input is part of IDO.
- Mistakes Location = SpatialLocation.
- Still cloudy retrieval for questions with additional wording in them that's irrelevant for retrieval (required annotation property question AND namespace structure question).
- Questions incorrectly chosen not to be answered
    - "What does a maintenance agency do?", thinks its out of scope!? weird...
    - "Who maintains ontologies aligned to IDO that are not part of ISO?" thinks its out of scope!? weird...
    - "Is IDO available in different languages?" -> this context not available yet and is therefore correctly not answered

### Trial 8

**Pipeline Summary:**
- Naive RAG
- K=20
- v9 Generation Prompt
- Retrieval Sources
    ISO_15926-14.ttl
    ISO_23726-1.md
    https://rds.posccaesar.org/
    LIS-14.md
    obi-ido-training-session 2, 3, 8, 9
    disjointness.md 
    CII-FMEA.tex 
    modelling_Objects_in_IDO.md 
    modelling-facts.md
    ido-summary 
    obi-principles 

**Key Pipeline Changes:**
- Used [v9 Generation Prompt](../../src/rag/prompts/archive/naive_rag_prompts/v9_naive_rag_prompt.txt) which tinkers with disallowing out of scope questions correctly.
- The OBI Principles summary has been shortened to only include headings. Since the document was previously quite long, and always at the beginning of the context, we believed it was creating the 'lost in the middle problem', where context toward the middle of the prompt is 'forgotten' by the LLM. This change improved responses to both the OBI Principles question and the Maintenance Agency questions.

### Trial 9

**Pipeline Summary:**
- Naive RAG + Query Breakdown Step
- K=20
- v9 Generation Prompt
- Retrieval Sources
    ISO_15926-14.ttl
    ISO_23726-1.md
    https://rds.posccaesar.org/
    LIS-14.md
    obi-ido-training-session 2, 3, 8, 9
    disjointness.md 
    CII-FMEA.tex 
    modelling_Objects_in_IDO.md 
    modelling-facts.md
    ido-summary 
    obi-principles 

**Key Pipeline Changes:**
- Added a query breakdown step which takes the query, breaks it down into (maximum 3) 'retrieval units' (short phrase representing one specific piece of information that must be retrieved from the corpus to answer the query), and uses these to retrieve better context. This aimed to assist the very retrieval sensitive questions: "I want to create a reference ontology for failure modes aligned with IDO, what should my namespace for my ontology look like?" and "If I create a concept in an IDO aligned ontology, what annotations / metadata is required on that concept." These questions have additional information within them not relevant for retrieval from a corpus made of entirely IDO-focused information. By extracting 'retrieval units', retrieval may be more focused on the core information needed to answer the query. An example is shown below:

```text
Query:
How are roles represented in IDO and what constraints apply to their use?

Retrieval Units (1):
role constraints
```

**Results:**
- Complete = 18
- Partial = 4
- Bad = 2

**Takeaways:**
- Still cannot answer these two because of extremely specific retrieval and the sections needed don't use the terms the query uses:
    - I want to create a reference ontology for failure modes aligned with IDO, what should my namespace for my ontology look like?
    - If I create a concept in an IDO aligned ontology, what annotations / metadata is required on that concept.
- Still don't have the 'languages' context. 
- Got a modelling question right! Although it should have not attempted to answer it...

## Final RAG Pipeline

The final pipeline is summarised below and is orchestrated using LangChain:

1. **Load conversation memory.**

2. **Rewrite the user’s query** using the [Query Rewrite Prompt](../../src/rag/prompts/query_rewrite_prompt.txt) to make it explicit with respect to the conversation history.
   For example:

   ```text
   Conversation History: The human asks about the properties of the Activity class. The AI explains that the Activity class in the IDO represents a temporal entity involving physical objects, defined as a subclass of the Temporal class. It has a key property, `hasParticipant`, that indicates participation. Examples of activities include actions like pumping, inspection, report writing, and fastening, and the class is designed to model activities with various temporal aspects.

   Question: What's the domain and range of the property?

   Rewritten Question: What's the domain and range of the `hasParticipant` property in the Activity class of the IDO?
   ```

3. **Break down the rewritten query into retrieval units** using the [Query Breakdown Prompt](../../src/rag/prompts/query_breakdown_prompt.txt).

4. **Retrieve relevant chunks per retrieval unit** using vector similarity search.

5. **Generate the response** using the retrieved chunks, the IDO summary document, the OBI principles document, and the conversation history, via the [v9 Generation Prompt](../../src/rag/prompts/archive/naive_rag_prompts/v9_naive_rag_prompt.txt).

6. **Summarise and persist conversation memory** for use in the next query.

## Future Work 

The modelling questions are still unable to be answered effectively by this pipeline, where the LLM needs to APPLY IDO to a specific use case and provide recommendations. Incorporating modelling patterns and examples may be particularly useful to answer these queries. Given that these types of questions may need to be identified and dealt with in a different manner, adding a step which identifies the intent of the question may be necessary. 

As well as modelling questions, these two questions are still unable to be answered:
1. I want to create a reference ontology for failure modes aligned with IDO, what should my namespace for my ontology look like?
2. If I create a concept in an IDO aligned ontology, what annotations / metadata is required on that concept.

These two questions each require ONE specific chunk to answer effectively. However, these chunks, specifically, do not use the same terminology as the questions. This means the chunks are often not retrieved. For example, the chunk needed to answer Q1 here is titled "Sub-directory structure" and discusses "URL structure" - not using the query's terminology of "namespace". A possible solution to this is adding a synonym generation step, where similar terms are appended to the query before retrieval commences (e.g., "namespace" -> "namespace / URL / URI"). 

Additional retrieval sources should also be completed which are noted on the Git issues. 

As for the overall web application, adding automated tests is an important next step before deployment. Deployment on a VM to this subdomain https://ido-assistant.equonto.org/ would be ideal. 