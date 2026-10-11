"""Verify entity-based ontology chunkers across TTL, ELOT Org, OMN, JSON-LD, YAML-LD.

This script is intentionally lightweight so the dissertation experiment can
check corpus comparability without depending on OpenAI credentials or FAISS.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from app.document_loaders import (  # noqa: E402
    SC_CHUNK_HARD_MAX_WORDS,
    SC_CHUNK_SOFT_MAX_WORDS,
    filter_retrieval_index_documents,
    get_assistant_corpus_mode,
    get_corpus_format,
    load_all_documents,
    load_ontology_file,
    load_yamlld,
    ofn_parse_axiom,
    should_load_data_file,
)
from experiment.config import OLLAMA_NUM_CTX, RETRIEVAL_K  # noqa: E402

DATA_DIR = RAG_DIR / "data"

FORMATS = {
    "turtle": "LIS-14-for-FDIS (1).ttl",
    "elot-org": "LIS-14-for-FDIS (1).org",
    "elot-org-ancestors": "LIS-14-for-FDIS (1).org",
    "omn": "LIS-14-for-FDIS (1).omn",
    "jsonld": "LIS-14-for-FDIS (1).jsonld",
    "yaml-ld": "LIS-14-for-FDIS (1).yamlld",
    "ofn": "LIS-14-for-FDIS (1).ofn",
}

KNOWN_ENTITY_IDS = {
    "lis:Activity",
    "lis:PhysicalObject",
    "lis:hasParticipant",
    "lis:datumValue",
}

# Exploratory schema-concept condition. Verified separately from the 7-format
# gates above: it is deliberately lossy (capped fields, no restrictions/examples
# past the caps, no annotation-property or individual chunks), so it neither
# reconstructs the whole canonical graph (verify_source_graph_equality) nor
# exposes the full 155-entity serialisation set the way FORMATS members do -- its
# checks are sized to what it actually claims. Same source file as turtle.
SCHEMA_CONCEPT_FILE = "LIS-14-for-FDIS (1).ttl"
SCHEMA_CONCEPT_TYPES = {"owl:Class", "owl:ObjectProperty", "owl:DatatypeProperty"}

REQUIRED_METADATA = {
    "format",
    "source",
    "entity_id",
    "chunk_id",
    "entity_type",
    "token_count",
    "char_count",
    "chunk_strategy",
    "loader_version",
}


def assert_metadata_contract(format_name: str, docs):
    chunk_ids = [doc.metadata.get("chunk_id") for doc in docs]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise AssertionError(f"{format_name}: chunk_id values are not unique")

    entity_ids = {doc.metadata.get("entity_id") for doc in docs}
    missing_entities = KNOWN_ENTITY_IDS - entity_ids
    if missing_entities:
        raise AssertionError(f"{format_name}: missing known entities {sorted(missing_entities)}")

    for doc in docs:
        missing = REQUIRED_METADATA - set(doc.metadata)
        if missing:
            raise AssertionError(
                f"{format_name}: {doc.metadata.get('chunk_id')} missing metadata {sorted(missing)}"
            )
        if not doc.metadata["chunk_id"].startswith(f"{format_name}:"):
            raise AssertionError(f"{format_name}: chunk_id is not format-scoped")
        if doc.metadata["char_count"] != len(doc.page_content):
            raise AssertionError(f"{format_name}: char_count does not match content length")
        if doc.metadata["token_count"] <= 0:
            raise AssertionError(f"{format_name}: token_count must be positive")


def named_retrievable_ids(docs):
    """Retrievable, named entity_ids (real IRIs; excludes synthetic axiom/prefix
    chunks, whose ids are format-specific by construction)."""
    return {
        doc.metadata["entity_id"]
        for doc in filter_retrieval_index_documents(docs)
        if doc.metadata.get("entity_uri")
    }


def verify_direct_loaders():
    all_entity_sets = {}
    named_retrievable = {}
    for format_name, filename in FORMATS.items():
        docs = load_ontology_file(DATA_DIR / filename, format_name)
        assert_metadata_contract(format_name, docs)
        all_entity_sets[format_name] = {doc.metadata["entity_id"] for doc in docs}
        named_retrievable[format_name] = named_retrievable_ids(docs)
        counts = Counter(doc.metadata["entity_type"] for doc in docs)
        print(f"{format_name}: {len(docs)} chunks; entity types={dict(sorted(counts.items()))}")

    for entity_id in KNOWN_ENTITY_IDS:
        formats_with_entity = [
            format_name
            for format_name, entity_ids in all_entity_sets.items()
            if entity_id in entity_ids
        ]
        if len(formats_with_entity) != len(FORMATS):
            raise AssertionError(f"{entity_id}: not present in every format")

    # Parity guard: the re-serialization-based JSON-LD chunker (and, riding on it,
    # the YAML-LD re-emit) must expose exactly the same named, retrievable entities
    # as the verbatim-slice Turtle baseline. This catches a chunker that drops or
    # invents a class/property chunk (e.g. a CBD grouping error) where the
    # gold-subset resolution check would not.
    reference = named_retrievable["turtle"]
    for fmt in ("jsonld", "yaml-ld", "ofn"):
        got = named_retrievable[fmt]
        if got != reference:
            raise AssertionError(
                f"{fmt}: named-retrievable entity set differs from turtle "
                f"(missing={sorted(reference - got)}, extra={sorted(got - reference)})"
            )
        print(f"{fmt}<->turtle named-retrievable parity OK: {len(reference)} entities")


def verify_yamlld_conformance():
    """YAML-LD round-trip + object-identity gate (the spec's core constraint).

    YAML-LD converts to valid JSON-LD, so every emitted YAML-LD chunk must parse
    back (YAML 1.2 Core Schema) to *exactly* the JSON-LD object of the matching
    JSON-LD chunk. Named-IRI chunks share an entity_id across the two arms; the
    synthetic prefix/axiom chunks differ only by the ``yamlld``/``jsonld`` token.
    This single check catches the Norway problem, any anchor/alias emission, and any
    YAML 1.1 coercion.
    """
    yaml_docs = load_ontology_file(DATA_DIR / FORMATS["yaml-ld"], "yaml-ld")
    json_docs = load_ontology_file(DATA_DIR / FORMATS["jsonld"], "jsonld")
    json_by_id = {d.metadata["entity_id"]: json.loads(d.page_content) for d in json_docs}

    def counterpart_id(entity_id: str) -> str:
        return entity_id.replace("yamlld", "jsonld")

    mismatches = []
    for doc in yaml_docs:
        jid = counterpart_id(doc.metadata["entity_id"])
        if jid not in json_by_id:
            mismatches.append(f"no JSON-LD counterpart for {doc.metadata['entity_id']}")
            continue
        if load_yamlld(doc.page_content) != json_by_id[jid]:
            mismatches.append(
                f"round-trip/object mismatch for {doc.metadata['entity_id']}"
            )
    if len(yaml_docs) != len(json_docs):
        mismatches.append(
            f"chunk count differs: yaml-ld={len(yaml_docs)} jsonld={len(json_docs)}"
        )
    if mismatches:
        raise AssertionError("YAML-LD conformance failed:\n  " + "\n  ".join(mismatches))
    print(f"yaml-ld round-trip + JSON-LD object-identity OK: {len(yaml_docs)} chunks")


def verify_yamlld_determinism():
    """Chunk bodies must be byte-identical across two independent loads."""
    a = load_ontology_file(DATA_DIR / FORMATS["yaml-ld"], "yaml-ld")
    b = load_ontology_file(DATA_DIR / FORMATS["yaml-ld"], "yaml-ld")
    if [d.page_content for d in a] != [d.page_content for d in b]:
        raise AssertionError("yaml-ld chunk bodies are not deterministic across loads")
    print(f"yaml-ld determinism OK: {len(a)} chunks byte-identical across two loads")


def verify_ofn_axiom_coverage():
    """Every axiom in the .ofn is assigned to exactly one chunk.

    OFN's flat axiom list gives a check the frame/graph formats cannot offer: the
    source is a countable set of axiom lines, so a parser that silently drops or
    double-attaches one is caught directly rather than inferred.
    """
    docs = load_ontology_file(DATA_DIR / FORMATS["ofn"], "ofn")
    src = [
        ln
        for ln in (DATA_DIR / FORMATS["ofn"]).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    axiom_lines = [
        ln
        for ln in src
        if not ln.startswith(("Prefix(", "Ontology(", "Annotation("))
        and ln != ")"
        and not re.fullmatch(r"<[^>]+>", ln.strip())
    ]
    assigned = []
    for doc in docs:
        if doc.metadata["entity_type"] in ("ofn:Prefixes", "owl:Ontology"):
            continue
        assigned += doc.page_content.splitlines()

    want, got = Counter(axiom_lines), Counter(assigned)
    if want != got:
        raise AssertionError(
            "ofn axiom coverage failed:\n"
            f"  dropped: {list((want - got).elements())[:5]}\n"
            f"  duplicated: {list((got - want).elements())[:5]}"
        )
    print(f"ofn axiom coverage OK: {len(axiom_lines)} axioms, each assigned exactly once")


# Diagnostic entities for the semantic diff: a class with a restriction and both
# binary and n-ary disjointness; a property carrying owl:propertyChainAxiom; a class
# whose annotations include an owl:Axiom reification (inline Annotation(...) in OFN).
OFN_SEMANTIC_SPOT_CHECK = {
    "lis:Activity": {"SubClassOf": "rdfs:subClassOf", "DisjointClasses": "owl:disjointWith"},
    "lis:hasParticipant": {
        "SubObjectPropertyOf": "owl:propertyChainAxiom",
        "InverseObjectProperties": "owl:inverseOf",
        "ObjectPropertyDomain": "rdfs:domain",
        "ObjectPropertyRange": "rdfs:range",
    },
    "lis:UnitOfMeasure": {"SubClassOf": "rdfs:subClassOf"},
}


def verify_ofn_turtle_semantic_diff():
    """Diff each spot-check entity's OFN axiom set against its Turtle triples.

    This is the primary correctness gate for the OFN arm. Byte-stability and
    entity_id parity both pass on a chunker that attaches axioms to the *wrong*
    entity, because ids and determinism are unaffected by mis-grouping. Only a
    semantic diff against Turtle catches it. The three entities exercise the three
    forms whose RDF mapping does not root at OFN arg1 (see ``ofn_axiom_subject``):
    n-ary disjointness (must be ABSENT here -- it lives in a standalone chunk, as it
    does in Turtle), property chains (root at the super-property, arg2), and
    axiom-annotated assertions (root at arg3, after the inline annotation).
    """
    from rdflib import Graph, URIRef

    docs = {d.metadata["entity_id"]: d for d in load_ontology_file(DATA_DIR / FORMATS["ofn"], "ofn")}
    g = Graph()
    g.parse(DATA_DIR / FORMATS["turtle"], format="turtle")
    qname = g.namespace_manager.normalizeUri

    errors = []
    for entity_id, expected in OFN_SEMANTIC_SPOT_CHECK.items():
        doc = docs.get(entity_id)
        if doc is None:
            errors.append(f"  {entity_id}: no ofn chunk")
            continue
        functors = Counter(ofn_parse_axiom(ln)[0] for ln in doc.page_content.splitlines())
        uri = URIRef(str(g.namespace_manager.expand_curie(entity_id)))
        preds = Counter(qname(p) for _s, p, _o in g.triples((uri, None, None)))
        for functor, predicate in expected.items():
            if functors.get(functor, 0) != preds.get(predicate, 0):
                errors.append(
                    f"  {entity_id}: OFN {functor}={functors.get(functor, 0)} but "
                    f"Turtle {predicate}={preds.get(predicate, 0)}"
                )
        # Annotation axioms: OFN's AnnotationAssertion count must equal the number of
        # annotation triples Turtle roots at the entity (everything not structural).
        structural = set(expected.values()) | {"rdf:type"}
        n_annot = sum(v for k, v in preds.items() if k not in structural)
        if functors.get("AnnotationAssertion", 0) != n_annot:
            errors.append(
                f"  {entity_id}: OFN AnnotationAssertion={functors.get('AnnotationAssertion', 0)} "
                f"but Turtle annotation triples={n_annot}"
            )

    # The n-ary disjointness must NOT ride with a member entity, in either format.
    activity = docs.get("lis:Activity")
    if activity and any(
        len(ofn_parse_axiom(ln)[1]) > 2
        for ln in activity.page_content.splitlines()
        if ofn_parse_axiom(ln)[0] == "DisjointClasses"
    ):
        errors.append("  lis:Activity: n-ary DisjointClasses leaked into the entity chunk")

    if errors:
        raise AssertionError("ofn<->turtle semantic diff failed:\n" + "\n".join(errors))
    print(
        f"ofn<->turtle semantic diff OK: {len(OFN_SEMANTIC_SPOT_CHECK)} entities "
        "(restriction + mixed-arity disjointness, property chain, annotated assertion)"
    )


def _reference_graph():
    from rdflib import Graph

    g = Graph()
    g.parse(DATA_DIR / FORMATS["turtle"], format="turtle")
    return g


def _robot_available() -> bool:
    import sys as _sys

    _sys.path.insert(0, str(RAG_DIR))
    try:
        from scripts.tangle_ofn import _robot_command

        _robot_command()
        return True
    except SystemExit:
        return False


def verify_source_graph_equality():
    """Whole-graph set equality: each source deserialises to the canonical Turtle.

    This is the strongest backing for "same ontology, different serialisation": not
    just that the chunkers expose matching entity_ids, but that each format's SOURCE
    FILE reconstructs the exact same RDF graph (isomorphic, blank nodes included) as
    the canonical Turtle -- before chunking enters the picture.

    Coverage is bounded by what has an in-repo deserialiser:
      * jsonld, yaml-ld -- rdflib (native / via YAML->JSON->JSON-LD). Always checked.
      * ofn, omn        -- need ROBOT (OWLAPI); checked opportunistically when a
                           robot.jar is reachable ($ROBOT_JAR or `robot` on PATH),
                           skipped otherwise. (OMN's ELOT-injected ontology label was
                           stripped from the source so it is now isomorphic too.)
      * elot-org(-ancestors) -- the .org source is not deserialisable to RDF without
                           the ELOT/Emacs tangling toolchain, so whole-graph equality
                           is NOT checkable in-repo (reported, not asserted). The
                           elot chunkers also deliberately inject non-source content
                           (1-hop SubClassOf, ancestor heading paths), so even a
                           text-coverage notion would need special-casing.
    """
    import json as _json
    import subprocess
    import tempfile

    from rdflib import Graph

    ref = _reference_graph()
    print(f"source-graph set equality (canonical turtle = {len(ref)} triples):")

    # --- rdflib-native arms (always) ---
    jl = Graph()
    jl.parse(DATA_DIR / FORMATS["jsonld"], format="json-ld")
    if not ref.isomorphic(jl):
        raise AssertionError(f"jsonld source graph ({len(jl)}) not isomorphic to turtle")
    print(f"  jsonld  : {len(jl)} triples, isomorphic OK")

    obj = load_yamlld((DATA_DIR / FORMATS["yaml-ld"]).read_text(encoding="utf-8"))
    yl = Graph()
    yl.parse(data=_json.dumps(obj), format="json-ld")
    if not ref.isomorphic(yl):
        raise AssertionError(f"yaml-ld source graph ({len(yl)}) not isomorphic to turtle")
    print(f"  yaml-ld : {len(yl)} triples, isomorphic OK")

    # --- ROBOT-backed arms (opportunistic) ---
    if _robot_available():
        from scripts.tangle_ofn import _robot_command

        def _to_graph(ext: str) -> Graph:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "x.ttl"
                cmd = _robot_command() + [
                    "convert", "--input", str(DATA_DIR / FORMATS[ext]),
                    "--format", "ttl", "--output", str(out),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    raise AssertionError(f"robot convert {ext}->ttl failed:\n{proc.stderr}")
                g = Graph()
                g.parse(str(out), format="turtle")
                return g

        for ext in ("ofn", "omn"):
            g = _to_graph(ext)
            if not ref.isomorphic(g):
                raise AssertionError(f"{ext} source graph ({len(g)}) not isomorphic to turtle")
            print(f"  {ext:7} : {len(g)} triples, isomorphic OK")
    else:
        print("  ofn/omn : skipped (no robot.jar; set $ROBOT_JAR to check). "
              "ofn verified axiom-set-equal at generation time.")

    print("  elot-org: whole-graph equality not checkable in-repo (needs ELOT/Emacs tangle)")


def report_chunk_token_lengths():
    """Log max chunk length and a top-k=5 assembly estimate for the LD formats.

    YAML-LD should be lighter than JSON-LD; this confirms a worst-case top-5
    assembly stays well under Ollama's num_ctx with prompt-scaffold headroom, so
    no Llama cell silently truncates.
    """
    for fmt in ("jsonld", "yaml-ld", "ofn"):
        docs = filter_retrieval_index_documents(
            load_ontology_file(DATA_DIR / FORMATS[fmt], fmt)
        )
        token_counts = sorted((d.metadata["token_count"] for d in docs), reverse=True)
        max_len = token_counts[0] if token_counts else 0
        top5 = sum(token_counts[:5])
        print(
            f"  {fmt:>8}: max_chunk_tokens={max_len} "
            f"top5_sum_tokens={top5} (retrievable chunks={len(docs)})"
        )


def verify_schema_concept_chunker():
    """Verify the exploratory schema-concept chunker against what it claims.

    Unlike the 7-format gates, this is NOT whole-graph isomorphism or full
    serialisation parity (the condition is intentionally lossy). It asserts:
      * the shared metadata contract (unique ids, required keys, char/token);
      * byte-determinism across two independent loads;
      * ENTITY parity vs Turtle -- schema-concept must expose EXACTLY Turtle's
        named, retrievable class/object-property/datatype-property entities,
        neither dropping nor inventing one (a curation bug that ids-only parity
        elsewhere would still pass);
      * the spec's hard word budget (no chunk exceeds SC_CHUNK_HARD_MAX_WORDS).
    Plus informational reports (annotation coverage, context budget) captured for
    the write-up but not asserted.
    """
    sc_docs = load_ontology_file(DATA_DIR / SCHEMA_CONCEPT_FILE, "schema-concept")
    assert_metadata_contract("schema-concept", sc_docs)

    # Determinism: two loads must be byte-identical.
    again = load_ontology_file(DATA_DIR / SCHEMA_CONCEPT_FILE, "schema-concept")
    if [d.page_content for d in sc_docs] != [d.page_content for d in again]:
        raise AssertionError("schema-concept chunk bodies are not deterministic across loads")

    # Entity parity vs Turtle's named-retrievable class/property set. Turtle's
    # named-retrievable set already excludes annotation properties and datatypes,
    # so restricting it to the three included types is exactly that set (155);
    # schema-concept must reproduce it precisely.
    turtle_docs = load_ontology_file(DATA_DIR / FORMATS["turtle"], "turtle")
    turtle_named = {
        d.metadata["entity_id"]
        for d in filter_retrieval_index_documents(turtle_docs)
        if d.metadata.get("entity_uri") and d.metadata["entity_type"] in SCHEMA_CONCEPT_TYPES
    }
    sc_named = named_retrievable_ids(sc_docs)
    if sc_named != turtle_named:
        raise AssertionError(
            "schema-concept named-entity set differs from turtle's class/property set "
            f"(missing={sorted(turtle_named - sc_named)[:5]}, "
            f"extra={sorted(sc_named - turtle_named)[:5]})"
        )
    print(f"schema-concept<->turtle class/property parity OK: {len(sc_named)} entities")

    # Hard word budget (spec s10). Truncation should keep every chunk within it.
    word_counts = {d.metadata["entity_id"]: len(d.page_content.split()) for d in sc_docs}
    over_hard = {e: n for e, n in word_counts.items() if n > SC_CHUNK_HARD_MAX_WORDS}
    if over_hard:
        raise AssertionError(
            f"schema-concept chunks exceed hard word budget ({SC_CHUNK_HARD_MAX_WORDS}): "
            f"{dict(sorted(over_hard.items(), key=lambda kv: -kv[1])[:5])}"
        )
    over_soft = sorted((n for n in word_counts.values() if n > SC_CHUNK_SOFT_MAX_WORDS), reverse=True)
    max_words = max(word_counts.values())
    print(
        f"schema-concept word budget OK: max={max_words} words "
        f"(soft={SC_CHUNK_SOFT_MAX_WORDS}, hard={SC_CHUNK_HARD_MAX_WORDS}); "
        f"{len(over_soft)} chunk(s) over soft cap"
    )

    # Informational: annotation-mapping coverage. Confirms the priority-list
    # mapping actually finds content (cross-check the source grep counts:
    # naturalLanguageDefinition/skos:example each 107, so most chunks should carry
    # a description and an example).
    n = len(sc_docs)
    def _pct(marker):
        return 100.0 * sum(f"{marker}:" in d.page_content for d in sc_docs) / n
    print(
        f"  schema-concept coverage: DESCRIPTION {_pct('DESCRIPTION'):.0f}%, "
        f"EXAMPLES {_pct('EXAMPLES'):.0f}%, SCHEMA CONTEXT {_pct('SCHEMA CONTEXT'):.0f}% "
        f"of {n} chunks"
    )

    # Informational: context budget (mirror report_chunk_token_lengths). Worst
    # case is the RETRIEVAL_K largest chunks retrieved together + headroom.
    token_counts = sorted((d.metadata["token_count"] for d in sc_docs), reverse=True)
    topk = sum(token_counts[:RETRIEVAL_K])
    print(
        f"  schema-concept context budget: max_chunk_tokens={token_counts[0]} "
        f"top{RETRIEVAL_K}_sum={topk} (headroom vs num_ctx={OLLAMA_NUM_CTX}: "
        f"{OLLAMA_NUM_CTX - topk})"
    )


def verify_corpus_mode_switches():
    if not should_load_data_file("ontology.ttl", "turtle", "ontology"):
        raise AssertionError("ontology mode should load the selected ontology extension")
    if should_load_data_file("ontology.org", "turtle", "ontology"):
        raise AssertionError("ontology mode should not load non-selected ontology extensions")
    if should_load_data_file("notes.md", "turtle", "ontology"):
        raise AssertionError("ontology mode should not load shared markdown docs")
    if not should_load_data_file("notes.md", "turtle", "full"):
        raise AssertionError("full mode should load shared markdown docs")

    original_mode = os.environ.get("ASSISTANT_CORPUS_MODE")
    original_format = os.environ.get("CORPUS_FORMAT")
    try:
        for format_name in FORMATS:
            os.environ["ASSISTANT_CORPUS_MODE"] = "ontology"
            os.environ["CORPUS_FORMAT"] = format_name
            docs = load_all_documents()
            loaded_formats = {doc.metadata.get("format") for doc in docs}
            if loaded_formats != {format_name}:
                raise AssertionError(
                    f"ontology mode for {format_name} loaded unexpected formats: {loaded_formats}"
                )
            print(f"ontology mode {format_name}: {len(docs)} chunks")
    finally:
        if original_mode is None:
            os.environ.pop("ASSISTANT_CORPUS_MODE", None)
        else:
            os.environ["ASSISTANT_CORPUS_MODE"] = original_mode
        if original_format is None:
            os.environ.pop("CORPUS_FORMAT", None)
        else:
            os.environ["CORPUS_FORMAT"] = original_format

    print(
        "active defaults:",
        f"ASSISTANT_CORPUS_MODE={get_assistant_corpus_mode()}",
        f"CORPUS_FORMAT={get_corpus_format()}",
    )


if __name__ == "__main__":
    # The corpus is licensed and not redistributed: without a local copy every gate
    # below is unrunnable, so say so and stop rather than fail.
    missing = sorted({name for name in FORMATS.values() if not (DATA_DIR / name).exists()})
    if missing:
        print("SKIPPED: the chunker verification needs the licensed ontology. Missing from "
              f"{DATA_DIR.relative_to(RAG_DIR)}/: " + ", ".join(missing))
        print("See the README, \"The ontology corpus\", for where the canonical Turtle goes "
              "and how to regenerate the other serialisations.")
        sys.exit(0)

    from scripts.verify_undetermined_items import verify_undetermined_items
    from experiment.schemas import load_tasks

    undetermined_results = verify_undetermined_items(
        load_tasks(), DATA_DIR / FORMATS["turtle"]
    )
    if undetermined_results:
        print(
            f"two-sided non-entailment / condition-invariance gate OK: "
            f"{len(undetermined_results)} item(s)"
        )
    verify_direct_loaders()
    verify_yamlld_conformance()
    verify_yamlld_determinism()
    verify_ofn_axiom_coverage()
    verify_ofn_turtle_semantic_diff()
    verify_source_graph_equality()
    print("\nChunk token lengths (retrievable chunks):")
    report_chunk_token_lengths()
    print("\nSchema-concept (exploratory condition):")
    verify_schema_concept_chunker()
    verify_corpus_mode_switches()
    print("Ontology chunker verification passed.")
