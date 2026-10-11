"""Document loaders/chunkers for turtle files, markdown files, and web pages."""

import os
import json
import logging
import requests
import re
from bs4 import BeautifulSoup
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document
from langchain_community.document_loaders.base import BaseLoader
from rdflib import Graph, URIRef, Literal, BNode, RDF, RDFS, OWL, Namespace
from collections import defaultdict
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from pathlib import Path

logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_DIR = os.path.dirname(APP_DIR)
DATA_DIR = os.path.join(RAG_DIR, "data")
DO_NOT_EMBED_DIR = os.path.join(DATA_DIR, "do-not-embed")

# ---------------------------------------------------------------------------
# Loader version constants -- bump when chunking logic changes
# ---------------------------------------------------------------------------
ENTITY_LOADER_VERSIONS = {
    "turtle": "4.0",
    "elot-org": "3.0",
    "elot-org-ancestors": "2.0",
    "omn": "2.0",
    "jsonld": "1.0",
    "yaml-ld": "1.0",
    "ofn": "1.0",
    # Exploratory schema-concept (Voicebox-style) indexing condition. NOT a
    # serialisation of the ontology -- a lossy, curated schema-first chunking, so
    # it is deliberately kept out of the "same ontology, seven serialisations"
    # comparison (config.FORMATS). See experiment/voicebox_style_lis14_*.md.
    # 1.1: dropped the cosmetic ``CHUNK ID:`` line (citation confound; CHANGELOG
    # 2026-07-30), changing chunk content -> FAISS index auto-rebuilds.
    "schema-concept": "1.1",
}
NAIVE_LOADER_VERSION = "1.0"
RETRIEVAL_INDEX_FILTER_VERSION = "1.1"
RETRIEVAL_INDEX_EXCLUDED_ENTITY_TYPES = {
    "owl:AnnotationProperty",
    "owl:Ontology",
    "elot:FileIntro",
    "elot:Prefixes",
    "elot:Root",
    "omn:Prefixes",
    "jsonld:Prefixes",
    "yamlld:Prefixes",
    "ofn:Prefixes",
}
RETRIEVAL_INDEX_EXCLUDED_ENTITY_IDS = {
    "elot:file-intro",
    "elot:prefixes",
    "elot:root:core",
    "omn:prefixes",
    "jsonld:prefixes",
    "yamlld:prefixes",
    "ofn:prefixes",
    "rdfs:Literal",
    "xsd:boolean",
    "xsd:date",
    "xsd:dateTime",
    "xsd:string",
}

# Primary entity type priority (first match wins)
ENTITY_TYPE_PRIORITY = [
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    RDFS.Datatype,
    OWL.NamedIndividual,
]

ONTOLOGY_FILE_EXTENSIONS = {
    "turtle": ".ttl",
    "elot-org": ".org",
    "elot-org-ancestors": ".org",
    "omn": ".omn",
    "jsonld": ".jsonld",
    "yaml-ld": ".yamlld",
    "ofn": ".ofn",
    # schema-concept parses the canonical Turtle directly (no derived source file).
    "schema-concept": ".ttl",
}

ELOT_SECTION_TYPES = {
    "Datatypes": "rdfs:Datatype",
    "Classes": "owl:Class",
    "Object properties": "owl:ObjectProperty",
    "Data properties": "owl:DatatypeProperty",
    "Annotation properties": "owl:AnnotationProperty",
    "Individuals": "owl:NamedIndividual",
}

OMN_FRAME_TYPES = {
    "Ontology": "owl:Ontology",
    "Class": "owl:Class",
    "ObjectProperty": "owl:ObjectProperty",
    "DataProperty": "owl:DatatypeProperty",
    "AnnotationProperty": "owl:AnnotationProperty",
    "Datatype": "rdfs:Datatype",
    "Individual": "owl:NamedIndividual",
}

OMN_MISC_AXIOM_TYPES = {
    "DisjointClasses",
    "EquivalentClasses",
    "DisjointProperties",
    "EquivalentProperties",
    "SameIndividual",
    "DifferentIndividuals",
}


def _ns_qname(g, uri) -> str:
    """Render a URI as a prefixed qname using a graph's namespace manager."""
    try:
        return g.namespace_manager.normalizeUri(uri)
    except Exception:
        return f"<{uri}>"


def _ns_primary_type(g, entity) -> str:
    """Return the highest-priority ``rdf:type`` of an entity as a qname."""
    types = set(g.objects(entity, RDF.type))
    for t in ENTITY_TYPE_PRIORITY:
        if t in types:
            return _ns_qname(g, t)
    any_type = next(iter(types), None)
    return _ns_qname(g, any_type) if any_type else "rdf:Resource"


def get_loader_version(strategy: str, corpus_format: str | None = None) -> str:
    """Return the version string for the active loader."""
    if strategy == "entity-based":
        fmt = corpus_format or os.getenv("CORPUS_FORMAT", "turtle")
        return ENTITY_LOADER_VERSIONS.get(fmt, ENTITY_LOADER_VERSIONS["turtle"])
    return NAIVE_LOADER_VERSION


def _count_tokens(text: str) -> int:
    """Count tokens for reporting chunk length, falling back to whitespace words."""
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return len(re.findall(r"\S+", text))


def _format_scoped_chunk_id(format_name: str, entity_id: str) -> str:
    return f"{format_name}:{entity_id}"


def _add_common_ontology_metadata(
    doc: Document,
    *,
    format_name: str,
    source: str,
    entity_id: str,
    entity_type: str,
    label: str | None = None,
    entity_uri: str = "",
):
    doc.metadata.update({
        "chunk_id": _format_scoped_chunk_id(format_name, entity_id),
        "entity_id": entity_id,
        "entity_uri": entity_uri,
        "label": label or entity_id,
        "entity_type": entity_type,
        "format": format_name,
        "source": os.path.basename(source),
        "type": format_name,
        "chunk_strategy": "entity-based",
        "loader_version": get_loader_version("entity-based", format_name),
        "char_count": len(doc.page_content),
        "token_count": _count_tokens(doc.page_content),
    })
    return doc


def should_include_in_retrieval_index(doc: Document) -> bool:
    """Return whether a loaded chunk should be embedded for retrieval.

    The excluded chunks are retained by the loaders for inspection and oracle
    lookup, but are provenance/structure rather than domain retrieval content.
    """
    entity_type = doc.metadata.get("entity_type")
    entity_id = str(doc.metadata.get("entity_id") or "")

    if entity_type in RETRIEVAL_INDEX_EXCLUDED_ENTITY_TYPES:
        return False
    if entity_id in RETRIEVAL_INDEX_EXCLUDED_ENTITY_IDS:
        return False
    if entity_id.startswith("elot:section:"):
        return False
    return True


def filter_retrieval_index_documents(docs: list[Document]) -> list[Document]:
    """Filter loaded documents down to chunks that should be embedded."""
    return [doc for doc in docs if should_include_in_retrieval_index(doc)]


def _is_bnode_id(x) -> bool:
    return isinstance(x, str) and x.startswith("_:")


def inline_and_relabel_bnodes(doc):
    """Nest blank-node objects into their referrers and stabilise their labels.

    rdflib serializes a CBD/graph as a *flat* ``@graph``: the named subject plus
    every blank node (``owl:Restriction``, anonymous class expression, ...) as a
    separate node, linked by a generated ``_:nXXXX`` label that is **not stable
    across parses**. We resolve each ``{"@id": "_:x"}`` reference to the referenced
    node inline (Turtle-style nesting, e.g. a restriction under ``rdfs:subClassOf``)
    and drop the label. ``rdf:List`` already serializes as an ordered ``@list``, so
    only structural bnodes need inlining. Free-floating blank axioms (e.g.
    ``owl:AllDisjointClasses`` -- referenced by nothing) can't be inlined; they are
    relabeled ``_:b0..`` in canonical-content order so output stays byte-stable.
    """
    if isinstance(doc, dict) and "@graph" in doc:
        context = doc.get("@context")
        nodes = doc["@graph"]
    elif isinstance(doc, dict):
        context = doc.get("@context")
        nodes = [{k: v for k, v in doc.items() if k != "@context"}]
    else:
        context = None
        nodes = doc

    bmap = {
        n["@id"]: n
        for n in nodes
        if isinstance(n, dict) and _is_bnode_id(n.get("@id"))
    }

    def resolve(val, path):
        if isinstance(val, dict):
            if set(val.keys()) == {"@id"} and val["@id"] in bmap and val["@id"] not in path:
                bid = val["@id"]
                body = {k: v for k, v in bmap[bid].items() if k != "@id"}
                return resolve(body, path | {bid})
            return {k: resolve(v, path) for k, v in val.items()}
        if isinstance(val, list):
            return [resolve(x, path) for x in val]
        return val

    referenced: set[str] = set()

    def collect(val):
        if isinstance(val, dict):
            if set(val.keys()) == {"@id"} and _is_bnode_id(val.get("@id")):
                referenced.add(val["@id"])
            else:
                for v in val.values():
                    collect(v)
        elif isinstance(val, list):
            for x in val:
                collect(x)

    for n in nodes:
        collect(n)

    top = [
        n
        for n in nodes
        if not (isinstance(n, dict) and _is_bnode_id(n.get("@id")) and n["@id"] in referenced)
    ]
    resolved = [resolve(n, frozenset()) for n in top]

    remap: dict[str, str] = {}
    survivors = sorted(
        (n for n in resolved if isinstance(n, dict) and _is_bnode_id(n.get("@id"))),
        key=lambda n: json.dumps(
            {k: v for k, v in n.items() if k != "@id"}, sort_keys=True, ensure_ascii=False
        ),
    )
    for i, n in enumerate(survivors):
        remap[n["@id"]] = f"_:b{i}"

    def apply_remap(val):
        if isinstance(val, dict):
            return {
                k: (remap[v] if k == "@id" and v in remap else apply_remap(v))
                for k, v in val.items()
            }
        if isinstance(val, list):
            return [apply_remap(x) for x in val]
        return val

    resolved = [apply_remap(n) for n in resolved]

    if len(resolved) == 1:
        node = resolved[0]
        return {"@context": context, **node} if context is not None else node
    out: dict = {"@graph": resolved}
    if context is not None:
        out["@context"] = context
    return out


# ---------------------------------------------------------------------------
# YAML-LD emit/parse (YAML 1.2 Core Schema; shared by the yaml-ld arm)
# ---------------------------------------------------------------------------
def _yamlld_engine():
    """A ruamel.yaml engine pinned to YAML 1.2 Core Schema.

    PyYAML is YAML 1.1 and coerces barewords like ``no``/``yes``/``on``/``off`` to
    booleans (the "Norway problem"), which YAML-LD rules out and which would
    silently corrupt any matching local name or annotation value; ruamel in 1.2
    mode does not. ``typ="safe"`` loads/dumps plain dict/list/scalar so a parsed
    chunk compares equal to the JSON-LD object it was emitted from.
    """
    from ruamel.yaml import YAML

    y = YAML(typ="safe", pure=True)
    y.version = (1, 2)  # pin 1.2; emits a self-declaring ``%YAML 1.2`` directive
    y.default_flow_style = False
    y.allow_unicode = True
    y.width = 1_000_000_000  # never line-wrap scalars (reflow would break determinism)
    return y


def dump_yamlld(obj) -> str:
    """Serialise a plain object to deterministic YAML 1.2 text (no anchors/aliases)."""
    import io

    y = _yamlld_engine()
    # Anchors/aliases carry no information in YAML-LD and may be dropped; a shared
    # node must inline exactly as it does in the JSON-LD chunk, not alias to it.
    y.representer.ignore_aliases = lambda *_a: True
    buf = io.StringIO()
    y.dump(obj, buf)
    return buf.getvalue()


def load_yamlld(text: str):
    """Parse YAML 1.2 text back into a plain object (for round-trip conformance)."""
    return _yamlld_engine().load(text)


def canonicalize_jsonld_object(obj, *, drop_context: bool = False, inline_bnodes: bool = False):
    """Return the deterministic canonical *Python object* for a JSON-LD input.

    This is the shared pre-serialisation seam for the JSON-LD and YAML-LD arms:
    both render *this* object (one to JSON, one to YAML), so a YAML-LD chunk parses
    back to the identical JSON-LD chunk object -- the YAML-LD spec's core "converts
    to valid JSON-LD" constraint. Object keys are sorted so the JSON and YAML
    renderings share one key order; *plain* multi-value arrays are sorted by their
    serialized element, but ``@list`` arrays are never reordered -- those are
    ordered ``rdf:List`` constructs (``owl:members``/``unionOf``/``intersectionOf``/
    ``oneOf``) whose order is semantic. ``inline_bnodes`` nests blank nodes into
    their referrers and stabilises labels (see ``inline_and_relabel_bnodes``);
    ``drop_context`` removes the top-level ``@context``.
    """
    if isinstance(obj, str):
        obj = json.loads(obj)
    if inline_bnodes:
        obj = inline_and_relabel_bnodes(obj)
    if drop_context and isinstance(obj, dict):
        obj = {k: v for k, v in obj.items() if k != "@context"}

    def _canon(node):
        if isinstance(node, dict):
            out = {}
            for k in sorted(node.keys()):
                v = node[k]
                out[k] = (
                    [_canon(x) for x in v]
                    if k == "@list" and isinstance(v, list)
                    else _canon(v)
                )
            return out
        if isinstance(node, list):
            items = [_canon(x) for x in node]
            return sorted(
                items, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)
            )
        return node

    return _canon(obj)


def canonicalize_jsonld(obj, *, drop_context: bool = False, inline_bnodes: bool = False) -> str:
    """Return deterministic, pretty JSON text for a JSON-LD object.

    rdflib's JSON-LD serializer does not guarantee stable key or array ordering.
    Object keys are sorted and *plain* multi-value arrays are sorted by their
    serialized element, but ``@list`` arrays are never reordered -- those are
    ordered ``rdf:List`` constructs (e.g. ``owl:members``, ``owl:unionOf``) whose
    order is meaningful. This keeps the generated source file and every chunk body
    byte-stable across runs, so the content-checksum index cache and the fixed-seed
    trial protocol stay reproducible.

    ``inline_bnodes`` nests blank nodes into their referrers and stabilises labels
    (see ``inline_and_relabel_bnodes``). ``drop_context`` removes the top-level
    ``@context`` so per-entity chunks are prefix-free (the prefix block is
    prepended once during context assembly).
    """
    canon = canonicalize_jsonld_object(
        obj, drop_context=drop_context, inline_bnodes=inline_bnodes
    )
    return json.dumps(canon, sort_keys=True, indent=2, ensure_ascii=False)


def canonicalize_yamlld(obj, *, drop_context: bool = False, inline_bnodes: bool = False) -> str:
    """Return deterministic YAML-LD text for a JSON-LD object.

    YAML-LD (W3C First Public Working Draft, 2026-03-04) is a set of conventions
    over YAML such that the document converts to a valid JSON-LD document. This is
    therefore a *re-emit*, not a new serialiser: it renders the same canonical
    object the JSON-LD arm renders (``canonicalize_jsonld_object``) as YAML, so the
    YAML-LD chunk round-trips to the identical JSON-LD chunk object. Emitted under
    YAML 1.2 Core Schema with anchors/aliases disabled (see ``dump_yamlld``).
    """
    canon = canonicalize_jsonld_object(
        obj, drop_context=drop_context, inline_bnodes=inline_bnodes
    )
    return dump_yamlld(canon)


def _extract_label_from_lines(lines: list[str], fallback: str) -> str:
    for line in lines:
        match = re.search(r'rdfs:label\s+(?:::)?\s*"([^"]+)"', line)
        if match:
            return match.group(1)
        match = re.search(r"-\s+rdfs:label\s+::\s+(.+)$", line)
        if match:
            return match.group(1).strip().strip('"')
    if ":" in fallback:
        return fallback.rsplit(":", 1)[-1]
    return fallback


# ---------------------------------------------------------------------------
# NaiveTurtleLoader (original, preserved for A/B comparison)
# ---------------------------------------------------------------------------
class NaiveTurtleLoader(BaseLoader):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self):
        g = Graph()
        g.parse(self.file_path, format="turtle")

        prefixes = {prefix: str(uri) for prefix, uri in g.namespace_manager.namespaces()}

        grouped = defaultdict(list)
        for s, p, o in g:
            grouped[s].append((p, o))

        docs = []

        for subject, triples in grouped.items():
            subgraph = Graph()
            for prefix, uri in prefixes.items():
                subgraph.bind(prefix, Namespace(uri), replace=True)
            for p, o in triples:
                subgraph.add((subject, p, o))

            docs.append(
                Document(
                    page_content=subgraph.serialize(format="turtle").strip(),
                    metadata={
                        "subject": str(subject),
                        "source": self.file_path,
                    },
                )
            )

        file_name = os.path.basename(self.file_path)
        for doc in docs:
            entity_id = doc.metadata.get("subject", "")
            _add_common_ontology_metadata(
                doc,
                format_name="turtle",
                source=file_name,
                entity_id=entity_id or "unknown",
                entity_type="rdf:Resource",
                label=entity_id or "unknown",
                entity_uri=entity_id,
            )

        return docs


# ---------------------------------------------------------------------------
# EntityBasedTurtleLoader
# ---------------------------------------------------------------------------
class EntityBasedTurtleLoader(BaseLoader):
    """Entity-level chunker for OWL ontologies in Turtle format.

    Each chunk's page_content is a verbatim slice of the source file -- no
    rdflib re-serialization, no triple reordering, no prefix reinjection.
    rdflib is only used to look up entity types and labels for metadata.

    Splits at Protege-style ``###  URI`` header lines. The text before the
    first such header becomes the "pre" chunk (prefix declarations +
    ``owl:Ontology`` declaration). Trailing top-level blank-node axioms
    (typically ``[ rdf:type owl:AllDisjointClasses ... ] .``) are split off
    from the final named-entity chunk into their own chunks.

    For files without ``###  URI`` markers, falls back to the legacy
    rdflib-serialize path so non-Protege Turtle is still chunked.
    """

    ENTITY_HEADER_RE = re.compile(r"^###\s+(\S+)\s*$")

    def __init__(self, file_path: str, include_external_vocab: bool = False):
        self.file_path = file_path
        self.include_external_vocab = include_external_vocab

    # --- Source-text helpers --------------------------------------------------

    @staticmethod
    def _sanitise_chunk_id(raw_id):
        """Sanitise a chunk ID for safe use in filenames and metric tables."""
        return re.sub(r'[^a-zA-Z0-9_+.-]', '-', raw_id)

    def _parse_graph(self):
        g = Graph()
        g.parse(self.file_path, format="turtle")
        return g

    def _read_source(self):
        return Path(self.file_path).read_text(encoding="utf-8")

    @staticmethod
    def _is_uri_like(token):
        return (
            token.startswith("http://")
            or token.startswith("https://")
            or (token.startswith("<") and token.endswith(">"))
            or (":" in token and not token.startswith("#"))
        )

    def _find_entity_headers(self, lines):
        """Return list of (line_index, uri_token) for each ``### URI`` header."""
        headers = []
        for i, line in enumerate(lines):
            m = self.ENTITY_HEADER_RE.match(line)
            if not m:
                continue
            token = m.group(1)
            if not self._is_uri_like(token):
                continue
            headers.append((i, token))
        return headers

    def _resolve_uri(self, g, token):
        """Resolve a URI token from a ``### URI`` header to a URIRef using graph prefixes."""
        if token.startswith("<") and token.endswith(">"):
            token = token[1:-1]
        if token.startswith("http://") or token.startswith("https://"):
            return URIRef(token)
        if ":" in token:
            prefix, local = token.split(":", 1)
            for p, ns in g.namespace_manager.namespaces():
                if (p or "") == prefix:
                    return URIRef(str(ns) + local)
        return URIRef(token)

    def _render_qname(self, g, uri):
        try:
            return g.namespace_manager.normalizeUri(uri)
        except Exception:
            return f"<{uri}>"

    def _primary_type(self, g, entity):
        types = set(g.objects(entity, RDF.type))
        for t in ENTITY_TYPE_PRIORITY:
            if t in types:
                return self._render_qname(g, t)
        any_type = next(iter(types), None)
        return self._render_qname(g, any_type) if any_type else "rdf:Resource"

    # --- Trailing-axiom splitter ---------------------------------------------

    @staticmethod
    def _split_trailing_axioms(block_lines):
        """Separate a named-entity block from any unrelated trailing axioms.

        Returns (entity_lines, trailing_blocks) where trailing_blocks is a list
        of raw text strings, one per detected trailing section. A "trailing"
        block is anything after the entity's last ``.``-terminated statement
        that contains a ``#####`` section divider or a top-level bare bracket
        axiom (``[`` at column 0). Inline reified annotations whose ``[``
        immediately follows the entity stay with the entity.
        """
        # Find the index of every line that begins a top-level statement
        # (column-0 non-comment, non-blank). The entity owns lines from the
        # ### header through the LAST run of column-0 statements that read as
        # the entity declaration plus immediately-following reified [ ... ] .
        # annotations. A ##### section divider marks a hard break.
        divider_re = re.compile(r"^#{4,}\s*$")
        section_label_re = re.compile(r"^#\s+\S")  # "#    General axioms"

        # Walk forward, tracking the position where the entity ends.
        # Default: entity owns everything until first divider or EOF.
        cut = len(block_lines)
        for idx in range(1, len(block_lines)):
            line = block_lines[idx]
            if divider_re.match(line):
                # Section divider: look backward for the start of the divider
                # block (consecutive blank lines and dividers + comment label)
                back = idx
                while back > 1 and (
                    not block_lines[back - 1].strip()
                    or divider_re.match(block_lines[back - 1])
                    or section_label_re.match(block_lines[back - 1])
                ):
                    back -= 1
                cut = back
                break

        entity_lines = block_lines[:cut]
        trailing = block_lines[cut:]

        # Split trailing region into individual axiom chunks. Boundaries:
        # blank-line runs between top-level [ ... ] . blocks, and the
        # ###-prefixed trailer comment (e.g. "### Generated by ...").
        trailing_blocks = []
        cur = []
        for line in trailing:
            if line.startswith("###") and not EntityBasedTurtleLoader.ENTITY_HEADER_RE.match(line):
                # Generator trailer or similar single-line comment -- drop it
                if cur:
                    chunk = "\n".join(cur).strip()
                    if chunk:
                        trailing_blocks.append(chunk)
                    cur = []
                continue
            cur.append(line)
            # End a block when we see a bracket-axiom terminator ("] .")
            if line.rstrip().endswith("] ."):
                chunk = "\n".join(cur).strip()
                if chunk:
                    trailing_blocks.append(chunk)
                cur = []
        if cur:
            chunk = "\n".join(cur).strip()
            if chunk:
                trailing_blocks.append(chunk)

        return entity_lines, trailing_blocks

    @staticmethod
    def _axiom_signature(axiom_text):
        """Extract a stable signature from a bare bracket axiom for chunk_id.

        Looks for ``rdf:type <Type>`` and ``owl:members ( ... )`` to produce
        an identifier like ``ttl-axiom-AllDisjointClasses-lis-A+lis-B``.
        Falls back to a numeric index if no signature is recoverable.
        """
        type_match = re.search(r"rdf:type\s+(\S+?)\s*[;\]]", axiom_text)
        type_name = type_match.group(1) if type_match else "Axiom"
        type_local = type_name.split(":", 1)[-1].rstrip(",;")

        members_match = re.search(r"owl:members\s*\(([^)]*)\)", axiom_text, re.DOTALL)
        if members_match:
            members = members_match.group(1).split()
            members = [m.strip(",;") for m in members if m.strip()]
            sorted_members = "+".join(sorted(members))
            return f"ttl-axiom-{type_local}-{sorted_members}"
        return f"ttl-axiom-{type_local}"

    # --- Legacy fallback (preserved for files without ### markers) ----------

    def _legacy_load(self, g):
        """rdflib-driven fallback when ``### URI`` markers are absent."""
        docs = []
        grouped = defaultdict(list)
        for s, p, o in g:
            grouped[s].append((p, o))

        prefixes = {prefix: str(uri) for prefix, uri in g.namespace_manager.namespaces()}

        for subject, triples in grouped.items():
            if not isinstance(subject, URIRef):
                continue
            subgraph = Graph()
            for prefix, uri in prefixes.items():
                subgraph.bind(prefix, Namespace(uri), replace=True)
            for p, o in triples:
                subgraph.add((subject, p, o))

            text = subgraph.serialize(format="turtle").strip()
            entity_qname = self._render_qname(g, subject)
            entity_type = self._primary_type(g, subject)
            doc = Document(page_content=text, metadata={})
            docs.append(_add_common_ontology_metadata(
                doc,
                format_name="turtle",
                source=self.file_path,
                entity_id=entity_qname,
                entity_uri=str(subject),
                label=str(g.value(subject, RDFS.label) or entity_qname),
                entity_type=entity_type,
            ))

        return docs

    # --- Main load method -----------------------------------------------------

    def load(self):
        g = self._parse_graph()
        source = self._read_source()
        lines = source.splitlines()
        headers = self._find_entity_headers(lines)

        if not headers:
            logger.info("No '###  URI' markers found; falling back to rdflib re-serialization.")
            return self._legacy_load(g)

        docs = []
        seen_chunk_ids = set()

        def _emit(entity_id, entity_type, label, page_content, entity_uri=""):
            scoped = _format_scoped_chunk_id("turtle", entity_id)
            # Disambiguate duplicate chunk_ids (e.g., repeated axiom signatures).
            base_id = entity_id
            counter = 1
            while scoped in seen_chunk_ids:
                counter += 1
                entity_id = f"{base_id}-{counter}"
                scoped = _format_scoped_chunk_id("turtle", entity_id)
            seen_chunk_ids.add(scoped)

            doc = Document(page_content=page_content, metadata={})
            _add_common_ontology_metadata(
                doc,
                format_name="turtle",
                source=self.file_path,
                entity_id=entity_id,
                entity_uri=entity_uri,
                label=label,
                entity_type=entity_type,
            )
            docs.append(doc)

        # 1. "Pre" chunk: prefixes + ontology declaration (everything before the first ###)
        pre_text = "\n".join(lines[: headers[0][0]]).rstrip()
        if pre_text:
            ont_subject = next(iter(g.subjects(RDF.type, OWL.Ontology)), None)
            if ont_subject is not None:
                ont_qname = self._render_qname(g, ont_subject)
                ont_label = str(g.value(ont_subject, RDFS.label) or ont_qname)
                _emit(
                    entity_id=ont_qname,
                    entity_type="owl:Ontology",
                    label=ont_label,
                    page_content=pre_text,
                    entity_uri=str(ont_subject),
                )
            else:
                _emit(
                    entity_id="ttl:prefixes",
                    entity_type="owl:Ontology",
                    label="prefixes",
                    page_content=pre_text,
                )

        # 2. Named-entity chunks: each ###...### slice, raw.
        for idx, (line_idx, uri_token) in enumerate(headers):
            end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
            block_lines = lines[line_idx:end]

            entity_uri = self._resolve_uri(g, uri_token)
            entity_qname = self._render_qname(g, entity_uri)
            entity_type = self._primary_type(g, entity_uri)
            label = str(g.value(entity_uri, RDFS.label) or entity_qname)

            is_last = idx == len(headers) - 1
            if is_last:
                entity_lines, trailing_blocks = self._split_trailing_axioms(block_lines)
            else:
                entity_lines, trailing_blocks = block_lines, []

            entity_text = "\n".join(entity_lines).rstrip()
            if entity_text:
                _emit(
                    entity_id=entity_qname,
                    entity_type=entity_type,
                    label=label,
                    page_content=entity_text,
                    entity_uri=str(entity_uri),
                )

            for axiom_text in trailing_blocks:
                if not axiom_text.lstrip().startswith("["):
                    continue
                signature = self._sanitise_chunk_id(self._axiom_signature(axiom_text))
                type_match = re.search(r"rdf:type\s+(\S+?)\s*[;\]]", axiom_text)
                axiom_type = type_match.group(1).rstrip(",;") if type_match else "owl:Axiom"
                _emit(
                    entity_id=signature,
                    entity_type=axiom_type,
                    label=signature,
                    page_content=axiom_text,
                )

        return docs


class EntityBasedJsonLdLoader(BaseLoader):
    """Entity-level chunker for the ontology in compacted JSON-LD.

    JSON-LD has no per-entity source markers (unlike Turtle's ``###  URI`` headers
    or OMN's ``Class:`` frames), so chunks are produced by *re-serialization*:
    parse the graph and, for each named subject, serialize a per-entity subgraph.
    The subgraph is the subject's Concise Bounded Description -- so anonymous class
    restrictions stay inlined, matching Turtle's verbatim slice -- **plus** any
    ``owl:Axiom`` reification whose ``owl:annotatedSource`` is the subject. Those
    reifications carry axiom-level annotations (``explanatoryNote`` etc.) that
    Turtle keeps inside the entity's slice, so attaching them preserves
    cross-format chunk parity. ``owl:AllDisjointClasses`` and unsourced
    ``owl:Axiom`` nodes become their own ``jsonld-axiom-*`` chunks, mirroring
    Turtle's ``ttl-axiom-*`` split.

    Each chunk is compacted against the file's own ``@context`` (qname ``@id``s)
    with the ``@context`` stripped (the prefix block is prepended once during
    context assembly), and inlined/canonicalized via ``canonicalize_jsonld`` so
    blank-node labels are stable and output is byte-deterministic.
    """

    # Chunk identifiers for the prefix chunk and standalone-axiom chunks. The
    # yaml-ld subclass overrides these so its synthetic (non-IRI) chunks are
    # format-distinct while every named-IRI chunk keeps a shared entity_id.
    PREFIX_ENTITY_ID = "jsonld:prefixes"
    PREFIX_ENTITY_TYPE = "jsonld:Prefixes"
    AXIOM_PREFIX = "jsonld-axiom"

    def __init__(self, file_path: str, format_name: str = "jsonld"):
        self.file_path = file_path
        self.format_name = format_name

    @staticmethod
    def _sanitise_chunk_id(raw_id):
        return re.sub(r'[^a-zA-Z0-9_+.-]', '-', raw_id)

    # --- Source / serialisation seams (overridden by the yaml-ld subclass) ----

    def _read_source_object(self):
        """Parse the source file into the top-level JSON-LD object."""
        return json.loads(Path(self.file_path).read_text(encoding="utf-8"))

    def _parse_into_graph(self, g, source) -> None:
        """Parse the source into an rdflib graph (shared upstream of emit)."""
        g.parse(self.file_path, format="json-ld")

    def _serialize_chunk(self, subgraph, context) -> str:
        raw = subgraph.serialize(format="json-ld", context=context, auto_compact=True)
        return canonicalize_jsonld(raw, inline_bnodes=True, drop_context=True)

    def _serialize_context_chunk(self, context) -> str:
        """Serialise the ``@context`` as the standalone prefix chunk body."""
        return json.dumps(
            {"@context": context}, indent=2, sort_keys=True, ensure_ascii=False
        )

    def _axiom_signature(self, g, ax, type_qname) -> str:
        """Stable id for a standalone axiom, from its ``owl:members`` if present."""
        local = type_qname.split(":", 1)[-1]
        members_head = g.value(ax, OWL.members)
        if members_head is not None:
            items = [_ns_qname(g, m) for m in g.items(members_head)]
            if items:
                return f"{self.AXIOM_PREFIX}-{local}-" + "+".join(sorted(items))
        return f"{self.AXIOM_PREFIX}-{local}"

    def load(self):
        source = self._read_source_object()
        context = source.get("@context", {}) if isinstance(source, dict) else {}

        g = Graph()
        self._parse_into_graph(g, source)
        for pfx, uri in context.items():
            if isinstance(uri, str):
                g.namespace_manager.bind(pfx or "", Namespace(uri), replace=True, override=True)

        docs = []
        seen_chunk_ids = set()

        def _emit(entity_id, entity_type, label, page_content, entity_uri=""):
            scoped = _format_scoped_chunk_id(self.format_name, entity_id)
            base = entity_id
            counter = 1
            while scoped in seen_chunk_ids:
                counter += 1
                entity_id = f"{base}-{counter}"
                scoped = _format_scoped_chunk_id(self.format_name, entity_id)
            seen_chunk_ids.add(scoped)
            doc = Document(page_content=page_content, metadata={})
            _add_common_ontology_metadata(
                doc,
                format_name=self.format_name,
                source=self.file_path,
                entity_id=entity_id,
                entity_uri=entity_uri,
                label=label,
                entity_type=entity_type,
            )
            docs.append(doc)

        # Prefix chunk: the @context (parity with omn:prefixes / turtle pre-chunk).
        _emit(
            entity_id=self.PREFIX_ENTITY_ID,
            entity_type=self.PREFIX_ENTITY_TYPE,
            label="Prefixes",
            page_content=self._serialize_context_chunk(context),
        )

        # Group owl:Axiom reifications by their annotated (named) source so they
        # ride with that entity's chunk, as they do in Turtle's file-order slice.
        axioms_by_source = defaultdict(list)
        standalone: list = []  # (type_uri, axiom_bnode)
        for ax in g.subjects(RDF.type, OWL.Axiom):
            src = g.value(ax, OWL.annotatedSource)
            if isinstance(src, URIRef):
                axioms_by_source[src].append(ax)
            else:
                standalone.append((OWL.Axiom, ax))
        for t in (OWL.AllDisjointClasses, OWL.AllDisjointProperties, OWL.AllDifferent):
            for ax in g.subjects(RDF.type, t):
                standalone.append((t, ax))

        # Named-entity chunks: one per URIRef subject that carries an rdf:type.
        named = sorted(
            {s for s in g.subjects(RDF.type, None) if isinstance(s, URIRef)}, key=str
        )
        for subj in named:
            sub = g.cbd(subj)
            for ax in axioms_by_source.get(subj, []):
                sub += g.cbd(ax)
            entity_qname = _ns_qname(g, subj)
            entity_type = _ns_primary_type(g, subj)
            label = str(g.value(subj, RDFS.label) or entity_qname)
            _emit(
                entity_qname,
                entity_type,
                label,
                self._serialize_chunk(sub, context),
                str(subj),
            )

        # Standalone axiom chunks (sorted by signature for stable emission order).
        signed = sorted(
            (
                (self._sanitise_chunk_id(self._axiom_signature(g, ax, _ns_qname(g, t))), t, ax)
                for t, ax in standalone
            ),
            key=lambda x: x[0],
        )
        for signature, type_uri, ax in signed:
            _emit(
                signature,
                _ns_qname(g, type_uri),
                signature,
                self._serialize_chunk(g.cbd(ax), context),
            )

        return docs


class EntityBasedYamlLdLoader(EntityBasedJsonLdLoader):
    """Entity-level chunker for the ontology in YAML-LD.

    YAML-LD (W3C First Public Working Draft, 2026-03-04) is a set of conventions
    over YAML such that any YAML-LD document converts to a valid JSON-LD document.
    This loader is therefore *not* an independent serialiser: it rides the JSON-LD
    pipeline (``EntityBasedJsonLdLoader``) unchanged through rdflib parse, CBD-per-
    named-subject grouping, ``owl:Axiom`` re-attachment, and ``@context`` stripping,
    then diverges only at the final emit -- the same per-entity canonical object is
    rendered as YAML (``canonicalize_yamlld``) instead of JSON. By construction each
    named-IRI chunk therefore has the *same* ``entity_id`` and CBD membership as the
    JSON-LD arm (and, transitively, Turtle's). The ``@context`` becomes a
    ``yamlld:prefixes`` chunk of YAML, mirroring ``jsonld:prefixes``.

    Emit is YAML 1.2 Core Schema with anchors/aliases disabled (see
    ``dump_yamlld``): barewords like ``no``/``on`` stay strings (no "Norway
    problem") and a shared node inlines rather than aliasing, so the emitted YAML
    parses back to the exact JSON-LD chunk object.
    """

    PREFIX_ENTITY_ID = "yamlld:prefixes"
    PREFIX_ENTITY_TYPE = "yamlld:Prefixes"
    AXIOM_PREFIX = "yamlld-axiom"

    def __init__(self, file_path: str, format_name: str = "yaml-ld"):
        super().__init__(file_path, format_name=format_name)

    def _read_source_object(self):
        return load_yamlld(Path(self.file_path).read_text(encoding="utf-8"))

    def _parse_into_graph(self, g, source) -> None:
        # rdflib has no YAML-LD reader; YAML-LD -> JSON-LD -> RDF is the spec path,
        # and ``source`` is already the equivalent JSON-LD object, so feed rdflib
        # its JSON form. This is the same graph the JSON-LD arm parses.
        g.parse(data=json.dumps(source), format="json-ld")

    def _serialize_chunk(self, subgraph, context) -> str:
        raw = subgraph.serialize(format="json-ld", context=context, auto_compact=True)
        return canonicalize_yamlld(raw, inline_bnodes=True, drop_context=True)

    def _serialize_context_chunk(self, context) -> str:
        return dump_yamlld({"@context": context})


# ---------------------------------------------------------------------------
# OWL Functional Syntax (OFN) parsing helpers
# ---------------------------------------------------------------------------
OFN_DECLARATION_TYPES = {
    "Class": "owl:Class",
    "ObjectProperty": "owl:ObjectProperty",
    "DataProperty": "owl:DatatypeProperty",
    "AnnotationProperty": "owl:AnnotationProperty",
    "Datatype": "rdfs:Datatype",
    "NamedIndividual": "owl:NamedIndividual",
}

_OFN_PREFIX_RE = re.compile(r"^Prefix\(\s*([^:\s]*):\s*=\s*<([^>]+)>\s*\)\s*$")


def ofn_split_args(body: str) -> list[str]:
    """Split an OFN argument list at top level, quote- and escape-aware.

    A naive bracket counter mis-nests on IDO's annotation prose, which contains both
    parentheses ("... (OM 2).") and escaped quotes ('is defined in OWL Time as
    \\"A temporal entity ...\\"'). This walks the string tracking string state and
    escapes, so only *unquoted* parens affect depth and only top-level whitespace
    separates arguments.
    """
    args: list[str] = []
    cur: list[str] = []
    depth = 0
    in_str = False
    esc = False
    for ch in body:
        if in_str:
            cur.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            cur.append(ch)
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch.isspace() and depth == 0:
            if cur:
                args.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        args.append("".join(cur))
    return args


def ofn_parse_axiom(line: str) -> tuple[str, list[str]]:
    """Split an OFN axiom line into (functor, top-level args)."""
    open_idx = line.index("(")
    functor = line[:open_idx]
    body = line[open_idx + 1 : line.rindex(")")]
    return functor, ofn_split_args(body)


def _ofn_is_named(token: str) -> bool:
    """True if a token is a named entity reference (qname or <IRI>), not an
    expression, literal, or keyword."""
    if not token or "(" in token or token.startswith('"'):
        return False
    return token.startswith("<") or ":" in token


def ofn_axiom_subject(functor: str, args: list[str]) -> str | None:
    """The entity an OFN axiom attaches to -- i.e. its Turtle CBD root.

    Chunk membership is pegged to Turtle's, so an axiom belongs to whichever entity
    Turtle's RDF mapping *roots the triple at*. That is arg1 for most axioms, but
    three forms root elsewhere, and each was verified against this ontology's Turtle:

    * ``AnnotationAssertion(P S V)`` roots at ``S`` (arg2): RDF emits ``S P V``.
    * Any axiom may carry leading ``Annotation(...)`` axiom annotations (104 here --
      the ``owl:Axiom`` reifications the JSON-LD arm reattaches by
      ``owl:annotatedSource``). They precede the subject and are skipped.
    * ``SubObjectPropertyOf(ObjectPropertyChain(...) Q)`` roots at ``Q`` (arg2): RDF
      emits ``Q owl:propertyChainAxiom (...)``, NOT at the chain members.

    Returns ``None`` when the axiom has no named root -- an n-ary
    ``DisjointClasses`` (RDF emits a blank ``owl:AllDisjointClasses`` node, which
    Turtle puts in its own ``ttl-axiom-*`` chunk) or any axiom whose subject slot is
    an anonymous expression. Those become standalone ``ofn-axiom-*`` chunks.
    """
    args = [a for a in args if not a.startswith("Annotation(")]
    if not args:
        return None

    if functor == "Declaration":
        inner = args[0]
        if "(" not in inner:
            return None
        token = inner[inner.index("(") + 1 : inner.rindex(")")]
        return token if _ofn_is_named(token) else None

    if functor == "AnnotationAssertion":
        subject = args[1] if len(args) > 1 else None
        return subject if subject and _ofn_is_named(subject) else None

    if functor == "DisjointClasses":
        # Binary -> plain ``A owl:disjointWith B``, rooted at A (verified: OFN's
        # operand order matches the Turtle subject for all 15). N-ary -> blank node.
        if len(args) != 2:
            return None
        return args[0] if _ofn_is_named(args[0]) else None

    if functor == "SubObjectPropertyOf" and args[0].startswith("ObjectPropertyChain("):
        return args[1] if len(args) > 1 and _ofn_is_named(args[1]) else None

    return args[0] if _ofn_is_named(args[0]) else None


class EntityBasedOfnLoader(BaseLoader):
    """Entity-level chunker for the ontology in OWL Functional Syntax.

    OFN is a flat axiom list wrapped in ``Ontology(...)``, not frame-based like OMN
    and with no per-entity source markers like Turtle's ``###  URI``. Chunks are
    therefore produced by *grouping axioms by the entity they attach to*, where
    "attach" means Turtle's CBD root -- see ``ofn_axiom_subject`` for the three forms
    that do not root at arg1. Membership is thus pegged to Turtle's by construction,
    exactly as the JSON-LD arm's CBD grouping is.

    Each chunk's page_content is a verbatim slice of the source lines (as in Turtle/
    OMN/ELOT, and unlike the re-serialised JSON-LD/YAML-LD arms). ROBOT emits exactly
    one axiom per line at column 0, so a chunk is just that entity's axiom lines in
    file order -- which ``scripts/tangle_ofn.py`` has already sorted deterministically.
    Anonymous class expressions are inline in OFN, so they travel with their axiom
    and need no special handling (they are Turtle's inlined blank nodes).

    N-ary ``DisjointClasses`` becomes an ``ofn-axiom-*`` chunk, mirroring Turtle's
    ``ttl-axiom-*`` split for ``owl:AllDisjointClasses``.
    """

    def __init__(self, file_path: str, format_name: str = "ofn"):
        self.file_path = file_path
        self.format_name = format_name

    @staticmethod
    def _sanitise_chunk_id(raw_id):
        return re.sub(r"[^a-zA-Z0-9_+.-]", "-", raw_id)

    def _read_lines(self) -> list[str]:
        text = Path(self.file_path).read_text(encoding="utf-8")
        return [ln for ln in text.splitlines() if ln.strip()]

    @staticmethod
    def _parse_prefixes(lines) -> dict[str, str]:
        out: dict[str, str] = {}
        for ln in lines:
            m = _OFN_PREFIX_RE.match(ln)
            if m:
                out[m.group(1)] = m.group(2)
        return out

    @staticmethod
    def _expand(token: str, prefixes: dict[str, str]) -> str:
        if token.startswith("<") and token.endswith(">"):
            return token[1:-1]
        if ":" not in token:
            return ""
        pfx, local = token.split(":", 1)
        base = prefixes.get(pfx)
        return f"{base}{local}" if base else ""

    def _axiom_signature(self, functor: str, args: list[str]) -> str:
        named = sorted(a for a in args if _ofn_is_named(a))
        if named:
            return f"ofn-axiom-{functor}-" + "+".join(named)
        return f"ofn-axiom-{functor}"

    def load(self):
        lines = self._read_lines()
        prefixes = self._parse_prefixes(lines)

        prefix_lines = [ln for ln in lines if ln.startswith("Prefix(")]
        header_idx = next(i for i, ln in enumerate(lines) if ln.startswith("Ontology("))
        body = lines[header_idx + 1 :]
        if body and body[-1].strip() == ")":
            body = body[:-1]

        # The Ontology(...) header plus its version IRI and ontology-level
        # Annotation(...) lines are the ontology declaration (Turtle's pre-chunk).
        header_lines = [lines[header_idx]]
        while body and (
            re.fullmatch(r"<[^>]+>", body[0].strip()) or body[0].startswith("Annotation(")
        ):
            header_lines.append(body.pop(0))

        docs = []
        seen_chunk_ids = set()

        def _emit(entity_id, entity_type, label, page_content, entity_uri=""):
            scoped = _format_scoped_chunk_id(self.format_name, entity_id)
            base = entity_id
            counter = 1
            while scoped in seen_chunk_ids:
                counter += 1
                entity_id = f"{base}-{counter}"
                scoped = _format_scoped_chunk_id(self.format_name, entity_id)
            seen_chunk_ids.add(scoped)
            doc = Document(page_content=page_content, metadata={})
            _add_common_ontology_metadata(
                doc,
                format_name=self.format_name,
                source=self.file_path,
                entity_id=entity_id,
                entity_uri=entity_uri,
                label=label,
                entity_type=entity_type,
            )
            docs.append(doc)

        # Prefix chunk (parity with omn:prefixes / jsonld:prefixes).
        _emit(
            entity_id="ofn:prefixes",
            entity_type="ofn:Prefixes",
            label="Prefixes",
            page_content="\n".join(prefix_lines),
        )

        # Group axiom lines by the entity they attach to, preserving file order.
        by_entity: dict[str, list[str]] = defaultdict(list)
        standalone: list[tuple[str, str, list[str]]] = []
        declared_types: dict[str, str] = {}
        for ln in body:
            functor, args = ofn_parse_axiom(ln)
            subject = ofn_axiom_subject(functor, args)
            if subject is None:
                standalone.append((ln, functor, args))
                continue
            by_entity[subject].append(ln)
            if functor == "Declaration":
                inner = args[0] if args else ""
                kind = inner[: inner.index("(")] if "(" in inner else ""
                if kind in OFN_DECLARATION_TYPES:
                    declared_types[subject] = OFN_DECLARATION_TYPES[kind]

        ont_iri = lines[header_idx][len("Ontology(") :].strip()
        ont_id = ont_iri
        for pfx, base in prefixes.items():
            raw = ont_iri.strip("<>")
            if base and raw.startswith(base):
                ont_id = f"{pfx}:{raw[len(base):]}"
                break
        _emit(
            entity_id=ont_id,
            entity_type="owl:Ontology",
            label=ont_id,
            page_content="\n".join(header_lines),
            entity_uri=ont_iri.strip("<>"),
        )

        for entity_id in sorted(by_entity):
            axiom_lines = by_entity[entity_id]
            entity_type = declared_types.get(entity_id, "rdf:Resource")
            label = _extract_label_from_lines(axiom_lines, entity_id)
            _emit(
                entity_id=entity_id,
                entity_type=entity_type,
                label=label,
                page_content="\n".join(axiom_lines),
                entity_uri=self._expand(entity_id, prefixes),
            )

        for signature, functor, ln in sorted(
            (
                (self._sanitise_chunk_id(self._axiom_signature(f, a)), f, l)
                for l, f, a in standalone
            ),
            key=lambda x: (x[0], x[2]),
        ):
            _emit(
                entity_id=signature,
                entity_type=f"owl:{functor}",
                label=signature,
                page_content=ln,
            )

        return docs


class EntityBasedElotOrgLoader(BaseLoader):
    """Entity-level chunker for generated ELOT Org-mode ontology files.

    Each chunk's page_content is a verbatim slice of the source: the heading
    line and the lines beneath it, up to (but not including) the next heading
    of any level. No ancestor headings, prefix tables, or root intros are
    injected. File-level intro + ``* core`` root + ``** Prefixes`` are
    preserved as their own dedicated chunks.

    ELOT encodes a class's named superclass only through heading nesting, which
    is lost once each entity becomes its own chunk. By default (``flat``
    elot-org) each CLASS chunk therefore gets its 1-hop parent materialised as a
    single ``- SubClassOf :: <parent>`` line, giving it the same immediate-
    superclass axiom that Turtle and OMN state natively (see
    ``include_parent_axiom``). Object/data/annotation properties already carry
    an explicit ``- SubPropertyOf ::`` in the source, so they are left untouched.
    """

    HEADING_RE = re.compile(r"^(\*+)\s+(.+?)\s*$")

    def __init__(
        self,
        file_path: str,
        include_narrative: bool = False,
        include_ancestor_headings: bool = False,
        include_parent_axiom: bool = True,
        format_name: str = "elot-org",
    ):
        self.file_path = file_path
        self.include_narrative = include_narrative
        self.format_name = format_name
        # When True, each entity chunk is prefixed with the raw ancestor heading
        # LINES (the class/property chain, level >= 3) as they appear in the
        # source -- not the ancestor bodies. Faithful to how ELOT encodes
        # hierarchy via document nesting.
        self.include_ancestor_headings = include_ancestor_headings
        # When True (and ancestor headings are off), each CLASS chunk gets a
        # single explicit ``- SubClassOf :: <immediate parent>`` line appended,
        # materialising the 1-hop named superclass that ELOT otherwise encodes
        # only through heading nesting. This is the default ``flat`` elot-org
        # structure and brings class chunks to parity with Turtle/OMN, which
        # state the immediate superclass natively. Ignored when
        # include_ancestor_headings is on, since the prepended heading path
        # already names the parent.
        self.include_parent_axiom = include_parent_axiom

    def _read_lines(self):
        return Path(self.file_path).read_text(encoding="utf-8").splitlines()

    def _parse_prefixes(self, lines):
        prefixes = {}
        in_prefix_table = False
        for line in lines:
            if line.startswith("#+name: prefix-table"):
                in_prefix_table = True
                continue
            if not in_prefix_table:
                continue
            if line.startswith("** "):
                break
            match = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
            if not match:
                continue
            prefix = match.group(1).strip()
            uri = match.group(2).strip()
            if prefix.lower() in {"prefix", "----------"} or uri.lower() in {"uri", "-----"}:
                continue
            prefixes[prefix.rstrip(":")] = uri
        return prefixes

    def _clean_heading_title(self, title):
        return re.sub(r"\s+:[A-Za-z0-9_@#%:.-]+:\s*$", "", title).strip()

    def _extract_entity_id(self, title):
        title = self._clean_heading_title(title)
        paren = re.search(r"\(([^)]+)\)", title)
        if paren:
            for token in paren.group(1).split():
                if ":" in token or token.startswith("<"):
                    return token.strip(",")
        token = title.split()[0] if title.split() else ""
        if ":" in token or token.startswith("<"):
            return token.strip(",")
        return ""

    def _expand_entity_uri(self, entity_id, prefixes):
        if entity_id.startswith("<") and entity_id.endswith(">"):
            return entity_id[1:-1]
        if ":" not in entity_id:
            return ""
        prefix, local = entity_id.split(":", 1)
        uri = prefixes.get(prefix)
        return f"{uri}{local}" if uri else ""

    def _heading_level(self, line):
        match = self.HEADING_RE.match(line)
        return len(match.group(1)) if match else None

    def _raw_slice(self, lines, start_index, stop_at_level=None):
        """Return raw lines from start to the next heading.

        If ``stop_at_level`` is None, stops at the next heading of any level.
        Otherwise stops at headings of that level or shallower.
        """
        end = start_index + 1
        while end < len(lines):
            next_level = self._heading_level(lines[end])
            if next_level is not None:
                if stop_at_level is None or next_level <= stop_at_level:
                    break
            end += 1
        return "\n".join(lines[start_index:end]).rstrip()

    def load(self):
        lines = self._read_lines()
        prefixes = self._parse_prefixes(lines)
        docs = []
        seen_chunk_ids = set()
        heading_stack = []

        def _emit(entity_id, entity_type, label, page_content, entity_uri=""):
            scoped = _format_scoped_chunk_id(self.format_name, entity_id)
            base = entity_id
            counter = 1
            while scoped in seen_chunk_ids:
                counter += 1
                entity_id = f"{base}-{counter}"
                scoped = _format_scoped_chunk_id(self.format_name, entity_id)
            seen_chunk_ids.add(scoped)
            doc = Document(page_content=page_content, metadata={})
            _add_common_ontology_metadata(
                doc,
                format_name=self.format_name,
                source=self.file_path,
                entity_id=entity_id,
                entity_uri=entity_uri,
                label=label,
                entity_type=entity_type,
            )
            docs.append(doc)

        # 1. File-level intro chunk: everything before the first heading.
        first_heading_idx = next(
            (i for i, line in enumerate(lines) if self._heading_level(line) is not None),
            None,
        )
        if first_heading_idx is not None and first_heading_idx > 0:
            intro_text = "\n".join(lines[:first_heading_idx]).rstrip()
            if intro_text:
                _emit(
                    entity_id="elot:file-intro",
                    entity_type="elot:FileIntro",
                    label="file intro",
                    page_content=intro_text,
                )

        for i, line in enumerate(lines):
            match = self.HEADING_RE.match(line)
            if not match:
                continue

            level = len(match.group(1))
            title = self._clean_heading_title(match.group(2))
            while heading_stack and heading_stack[-1]["level"] >= level:
                heading_stack.pop()
            ancestors = list(heading_stack)

            # Level 1: root ontology heading. Emit the heading + its PROPERTIES
            # drawer + any prose before the first level-2 section as a chunk.
            if level == 1:
                root_text = self._raw_slice(lines, i, stop_at_level=1)
                if root_text:
                    _emit(
                        entity_id=f"elot:root:{title}",
                        entity_type="elot:Root",
                        label=title,
                        page_content=root_text,
                    )
                heading_stack.append({"level": level, "title": title, "line": line, "index": i})
                continue

            if level == 2:
                if "ontology" in title.lower():
                    entity_id = self._extract_entity_id(title) or "ontology"
                    block = self._raw_slice(lines, i, stop_at_level=2)
                    _emit(
                        entity_id=entity_id,
                        entity_type="owl:Ontology",
                        label=_extract_label_from_lines(block.splitlines(), entity_id),
                        page_content=block,
                        entity_uri=self._expand_entity_uri(entity_id, prefixes),
                    )
                elif title.lower() == "prefixes":
                    block = self._raw_slice(lines, i, stop_at_level=2)
                    _emit(
                        entity_id="elot:prefixes",
                        entity_type="elot:Prefixes",
                        label="Prefixes",
                        page_content=block,
                    )
                else:
                    # Section heading (e.g. ** Classes, ** Datatypes): emit
                    # just the heading + its PROPERTIES drawer + prose, but
                    # NOT the level-3 entities beneath (those are their own
                    # chunks).
                    section_text = self._raw_slice(lines, i, stop_at_level=None)
                    if section_text:
                        _emit(
                            entity_id=f"elot:section:{title}",
                            entity_type="elot:Section",
                            label=title,
                            page_content=section_text,
                        )
                heading_stack.append({"level": level, "title": title, "line": line, "index": i})
                continue

            # level >= 3: entities and sub-entities.
            current_section = next(
                (ancestor["title"] for ancestor in reversed(ancestors) if ancestor["title"] in ELOT_SECTION_TYPES),
                None,
            )
            if current_section not in ELOT_SECTION_TYPES:
                heading_stack.append({"level": level, "title": title, "line": line, "index": i})
                continue

            # Each entity chunk is a raw slice ending at the NEXT heading of
            # any level. Nested sub-entities become their own chunks; the
            # parent's chunk does not duplicate them.
            block = self._raw_slice(lines, i, stop_at_level=None)

            if ":nodeclare:" in line:
                if re.search(r"^\s*-\s+\w[\w:-]*\s+::", block, flags=re.MULTILINE):
                    entity_id = self._sanitise_chunk_id(f"elot-axiom:{title}")
                    _emit(
                        entity_id=entity_id,
                        entity_type="owl:Axiom",
                        label=title,
                        page_content=block,
                    )
                heading_stack.append({"level": level, "title": title, "line": line, "index": i})
                continue

            entity_id = self._extract_entity_id(title)
            if not entity_id:
                if not self.include_narrative:
                    heading_stack.append({"level": level, "title": title, "line": line, "index": i})
                    continue
                entity_id = f"narrative:{self._clean_heading_title(title)}"
                entity_type = "narrative"
            else:
                entity_type = ELOT_SECTION_TYPES[current_section]

            page_content = block
            if self.include_ancestor_headings:
                ancestor_heading_lines = [a["line"] for a in ancestors if a["level"] >= 3]
                if ancestor_heading_lines:
                    page_content = "\n".join(ancestor_heading_lines) + "\n" + block
            elif self.include_parent_axiom and entity_type == "owl:Class":
                # Nearest ancestor at level >= 3 that resolves to an entity id is
                # the immediate superclass. Top-level classes (direct children of
                # the ** Classes section) have none -- matching Turtle/OMN, where
                # they carry no named superclass either -- so nothing is appended.
                parent_id = ""
                for ancestor in reversed(ancestors):
                    if ancestor["level"] < 3:
                        continue
                    candidate = self._extract_entity_id(ancestor["title"])
                    if candidate:
                        parent_id = candidate
                        break
                if parent_id:
                    page_content = f"{block}\n - SubClassOf :: {parent_id}"

            _emit(
                entity_id=entity_id,
                entity_type=entity_type,
                label=_extract_label_from_lines(block.splitlines(), title.split("(", 1)[0].strip() or entity_id),
                page_content=page_content,
                entity_uri=self._expand_entity_uri(entity_id, prefixes),
            )
            heading_stack.append({"level": level, "title": title, "line": line, "index": i})

        return docs

    @staticmethod
    def _sanitise_chunk_id(raw_id):
        return re.sub(r'[^a-zA-Z0-9_+.:,-]', '-', raw_id)


class EntityBasedOmnLoader(BaseLoader):
    """Entity-level chunker for OWL Manchester Syntax files.

    Each chunk's page_content is a verbatim slice of the source. The
    ``Prefix:`` declarations at the top of the file (plus any preceding
    comment lines) become a single dedicated chunk; every ``Class:``,
    ``ObjectProperty:``, etc. frame and every miscellaneous axiom (e.g.
    ``DisjointClasses:``) is emitted as its own raw slice.
    """

    FRAME_RE = re.compile(r"^(Ontology|Class|ObjectProperty|DataProperty|AnnotationProperty|Datatype|Individual):\s+(.+?)\s*$")
    MISC_RE = re.compile(r"^(" + "|".join(sorted(OMN_MISC_AXIOM_TYPES)) + r"):\s+(.+?)\s*$")
    PREFIX_RE = re.compile(r"^Prefix:\s+([^:\s]*):\s+<([^>]+)>")

    def __init__(self, file_path: str):
        self.file_path = file_path

    def _read_lines(self):
        return Path(self.file_path).read_text(encoding="utf-8").splitlines()

    def _parse_prefixes(self, lines):
        prefixes = {}
        for line in lines:
            match = self.PREFIX_RE.match(line)
            if match:
                prefixes[match.group(1)] = match.group(2)
        return prefixes

    def _prefix_block(self, lines):
        first_prefix = next((i for i, line in enumerate(lines) if self.PREFIX_RE.match(line)), None)
        if first_prefix is None:
            return ""

        start = first_prefix
        while start > 0 and (lines[start - 1].strip() == "" or lines[start - 1].lstrip().startswith("#")):
            start -= 1

        end = first_prefix + 1
        while end < len(lines):
            stripped = lines[end].strip()
            if stripped == "" or stripped.startswith("#") or self.PREFIX_RE.match(lines[end]):
                end += 1
                continue
            break

        return "\n".join(lines[start:end]).rstrip()

    def _extract_entity_id(self, frame_type, identifier):
        token = identifier.split()[0] if identifier.split() else frame_type
        return token.strip()

    def _expand_entity_uri(self, entity_id, prefixes):
        if entity_id.startswith("<") and entity_id.endswith(">"):
            return entity_id[1:-1]
        if ":" not in entity_id:
            return ""
        prefix, local = entity_id.split(":", 1)
        uri = prefixes.get(prefix)
        return f"{uri}{local}" if uri else ""

    def _collect_blocks(self, lines):
        blocks = []
        i = 0
        while i < len(lines):
            match = self.FRAME_RE.match(lines[i])
            is_misc = False
            if not match:
                match = self.MISC_RE.match(lines[i])
                is_misc = match is not None
            if not match:
                i += 1
                continue
            start = i
            i += 1
            while i < len(lines) and not self.FRAME_RE.match(lines[i]) and not self.MISC_RE.match(lines[i]):
                i += 1
            block_type = "misc" if is_misc else "frame"
            blocks.append((block_type, match.group(1), match.group(2), "\n".join(lines[start:i]).rstrip()))
        return blocks

    def load(self):
        lines = self._read_lines()
        prefixes = self._parse_prefixes(lines)
        prefix_block = self._prefix_block(lines)
        docs = []
        seen_chunk_ids = set()

        def _emit(entity_id, entity_type, label, page_content, entity_uri=""):
            scoped = _format_scoped_chunk_id("omn", entity_id)
            base = entity_id
            counter = 1
            while scoped in seen_chunk_ids:
                counter += 1
                entity_id = f"{base}-{counter}"
                scoped = _format_scoped_chunk_id("omn", entity_id)
            seen_chunk_ids.add(scoped)
            doc = Document(page_content=page_content, metadata={})
            _add_common_ontology_metadata(
                doc,
                format_name="omn",
                source=self.file_path,
                entity_id=entity_id,
                entity_uri=entity_uri,
                label=label,
                entity_type=entity_type,
            )
            docs.append(doc)

        # Prefix block as its own chunk.
        if prefix_block:
            _emit(
                entity_id="omn:prefixes",
                entity_type="omn:Prefixes",
                label="Prefixes",
                page_content=prefix_block,
            )

        for block_type, frame_type, identifier, block in self._collect_blocks(lines):
            if block_type == "misc":
                entity_id = self._sanitise_chunk_id(f"{frame_type}:{identifier}")
                entity_type = "owl:Axiom"
                entity_uri = ""
                label = f"{frame_type}: {identifier}"
            else:
                entity_id = self._extract_entity_id(frame_type, identifier)
                entity_type = OMN_FRAME_TYPES[frame_type]
                entity_uri = self._expand_entity_uri(entity_id, prefixes)
                label = _extract_label_from_lines(block.splitlines(), entity_id)

            _emit(
                entity_id=entity_id,
                entity_type=entity_type,
                label=label,
                page_content=block,
                entity_uri=entity_uri,
            )

        return docs

    @staticmethod
    def _sanitise_chunk_id(raw_id):
        return re.sub(r'[^a-zA-Z0-9_+.:,-]', '-', raw_id)


# ---------------------------------------------------------------------------
# Schema-concept (Voicebox-style) chunking
#
# An exploratory, schema-first indexing condition (spec:
# experiment/voicebox_style_lis14_schema_concept_chunking.md). One curated chunk
# per class/object-property/datatype-property, holding human-readable
# labels/definitions/examples/notes plus MINIMAL formal schema context. It is
# deliberately lossy (capped fields, no full restrictions/neighbourhoods, no
# annotation-property or individual chunks), so it is NOT a serialisation of the
# ontology and must never join config.FORMATS. Chunk text is re-derived from the
# canonical Turtle graph deterministically -- no LLM, no source-file slicing.
# ---------------------------------------------------------------------------
SKOS_NS = Namespace("http://www.w3.org/2004/02/skos/core#")
IOFAV_NS = Namespace(
    "https://spec.industrialontologies.org/ontology/core/meta/AnnotationVocabulary/"
)
DCTERMS_NS = Namespace("http://purl.org/dc/terms/")
SCHEMA_NS = Namespace("http://schema.org/")

# Global parameters (spec doc s4). MAX_PROPERTY_CHAINS fills a spec gap: it is
# used in s7.3 / s11.3 but was never defined among the s4 parameters.
SC_MAX_LABELS = 4
SC_MAX_DESCRIPTIONS = 2
SC_MAX_EXAMPLES = 2
SC_MAX_NOTES = 1
SC_MAX_DIRECT_SUPERCLASSES = 3
SC_MAX_DIRECT_SUBCLASSES = 5
SC_MAX_DOMAINS = 3
SC_MAX_RANGES = 3
SC_MAX_INVERSES = 1
SC_MAX_SUPERPROPERTIES = 3
SC_MAX_SUBPROPERTIES = 5
SC_MAX_EQUIVALENT_CLASSES = 2
SC_MAX_DISJOINT_CLASSES = 3
SC_MAX_RESTRICTIONS = 2
SC_MAX_PROPERTY_CHAINS = 2
SC_MAX_RETRIEVAL_TERMS = 20
SC_CHUNK_SOFT_MAX_WORDS = 350
SC_CHUNK_HARD_MAX_WORDS = 500

# Label sources in priority order (spec s5.1). rdfs:label is canonical; the rest
# become aliases.
SC_LABEL_PREDICATES = [RDFS.label, SKOS_NS.prefLabel, SKOS_NS.altLabel, IOFAV_NS.synonym]

# Description sources (spec s5.2). Split into the primary DEFINITIONAL predicates
# and lower-priority fallbacks: usageNote/scopeNote/semiFormalAxiom are ALSO note
# sources (s5.4), so they are used as descriptions only when no definitional
# literal exists -- otherwise they would both duplicate into NOTES and displace
# the definition. This reproduces the spec's worked examples (s12-s14), where the
# definition lands in DESCRIPTION and the usage/scope guidance in NOTES.
SC_DESCRIPTION_PRIMARY = [
    RDFS.comment,
    IOFAV_NS.naturalLanguageDefinition,
    SKOS_NS.definition,
    DCTERMS_NS.description,
    SCHEMA_NS.description,
    IOFAV_NS.semiFormalNaturalLanguageDefinition,
]
SC_DESCRIPTION_FALLBACK = [
    IOFAV_NS.semiFormalNaturalLanguageAxiom,
    IOFAV_NS.usageNote,
    SKOS_NS.scopeNote,
]

# Note sources (spec s5.4). Only literals attached DIRECTLY to the entity are
# eligible -- alignment-axiom explanatoryNotes live on reified owl:Axiom blank
# nodes (annotatedSource) rather than on the entity, so querying direct triples
# realises the spec's "exclude notes attached only to external alignment axioms".
SC_NOTE_PREDICATES = [
    SKOS_NS.scopeNote,
    IOFAV_NS.usageNote,
    IOFAV_NS.explanatoryNote,
    IOFAV_NS.primitiveRationale,
]

SC_PROPERTY_CHARACTERISTICS = [
    (OWL.FunctionalProperty, "FunctionalProperty"),
    (OWL.InverseFunctionalProperty, "InverseFunctionalProperty"),
    (OWL.TransitiveProperty, "TransitiveProperty"),
    (OWL.SymmetricProperty, "SymmetricProperty"),
    (OWL.AsymmetricProperty, "AsymmetricProperty"),
    (OWL.ReflexiveProperty, "ReflexiveProperty"),
    (OWL.IrreflexiveProperty, "IrreflexiveProperty"),
]

SC_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "if", "in", "is", "it", "its", "of", "on", "or", "that", "the", "then", "to",
    "with", "x", "y",
}

_CAMEL_SPLIT_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


def _sc_split_camel(token: str) -> list[str]:
    """Split a camelCase / PascalCase token into lowercase word parts."""
    parts = _CAMEL_SPLIT_RE.findall(token)
    return [p.lower() for p in parts] if parts else [token.lower()]


def _sc_tokenize(strings, cap: int) -> list[str]:
    """Deterministic retrieval-term tokenisation (spec s9).

    Only source strings feed this -- no invented synonyms. Splits on
    non-alphanumerics, then camelCase, lowercases, drops stopwords, dedupes
    preserving first-seen order, and caps.
    """
    out: list[str] = []
    seen: set[str] = set()
    for s in strings:
        for raw in re.split(r"[^A-Za-z0-9]+", s):
            if not raw:
                continue
            for tok in _sc_split_camel(raw):
                if not tok or tok in SC_STOPWORDS or tok in seen:
                    continue
                seen.add(tok)
                out.append(tok)
                if len(out) >= cap:
                    return out
    return out


class EntityBasedSchemaConceptLoader(BaseLoader):
    """Voicebox-style schema-concept chunker (see module comment + spec doc).

    One deterministic chunk per named ``owl:Class`` / ``owl:ObjectProperty`` /
    ``owl:DatatypeProperty``, built from the canonical Turtle graph via rdflib.
    ``entity_id`` is the bare CURIE (``lis:Activity``) exactly as every other
    loader emits, so task gold-chunk resolution keys on it unchanged; the
    ``CHUNK ID:`` line rendered inside the page text (``class:lis.Activity:
    schema_concept``) is a cosmetic label the harness never parses.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.g: Graph | None = None

    # --- Graph helpers --------------------------------------------------------

    def _q(self, uri) -> str:
        return _ns_qname(self.g, uri)

    def _label_of(self, uri) -> str:
        lbl = self.g.value(uri, RDFS.label)
        return str(lbl) if lbl is not None else self._q(uri)

    def _sorted_literals(self, entity, predicate, prefer_short: bool) -> list[str]:
        """All literal values of one predicate on an entity, deterministically
        ordered. ``prefer_short`` sorts shortest-first (spec 'prefer
        concise/shorter' for descriptions/examples); otherwise alphabetical,
        which for notes reproduces the spec's worked examples (s12-s14)."""
        vals = {str(o) for o in self.g.objects(entity, predicate) if isinstance(o, Literal)}
        key = (lambda s: (len(s), s)) if prefer_short else (lambda s: s)
        return sorted(vals, key=key)

    def _collect(self, entity, predicates, cap, prefer_short: bool = False):
        """Priority-ordered, deduped literals across a predicate list (cap=None
        for all)."""
        out: list[str] = []
        seen: set[str] = set()
        for pred in predicates:
            for val in self._sorted_literals(entity, pred, prefer_short):
                if val in seen:
                    continue
                seen.add(val)
                out.append(val)
                if cap is not None and len(out) >= cap:
                    return out
        return out

    def _get_labels(self, entity) -> list[str]:
        labels = self._collect(entity, SC_LABEL_PREDICATES, SC_MAX_LABELS)
        if labels:
            return labels
        # No explicit label anywhere: fall back to the IRI local name (spec s5.1).
        local = re.split(r"[#/]", str(entity))[-1]
        return [local] if local else [self._q(entity)]

    def _get_descriptions(self, entity) -> list[str]:
        primary = self._collect(entity, SC_DESCRIPTION_PRIMARY, SC_MAX_DESCRIPTIONS, prefer_short=True)
        if primary:
            return primary
        return self._collect(entity, SC_DESCRIPTION_FALLBACK, SC_MAX_DESCRIPTIONS, prefer_short=True)

    def _get_examples(self, entity) -> list[str]:
        return self._collect(entity, [SKOS_NS.example], SC_MAX_EXAMPLES, prefer_short=True)

    def _get_notes(self, entity, exclude: set[str]) -> list[str]:
        out: list[str] = []
        for val in self._collect(entity, SC_NOTE_PREDICATES, None):
            if val in exclude:
                continue
            out.append(val)
            if len(out) >= SC_MAX_NOTES:
                break
        return out

    def _class_expr(self, node):
        """Render a named class or a simple union/intersection bnode; None if the
        expression is anything more complex (skipped, keeping context compact)."""
        if isinstance(node, URIRef):
            return self._q(node)
        for pred, joiner in ((OWL.unionOf, " or "), (OWL.intersectionOf, " and ")):
            head = self.g.value(node, pred)
            if head is not None:
                members = [m for m in self.g.items(head) if isinstance(m, URIRef)]
                if members:
                    return joiner.join(sorted(self._q(m) for m in members))
        return None

    def _named_objects(self, entity, predicate, cap) -> list[str]:
        vals = {
            expr
            for o in self.g.objects(entity, predicate)
            if (expr := self._class_expr(o)) is not None
        }
        return sorted(vals)[:cap]

    def _named_subjects(self, predicate, entity, cap) -> list[str]:
        vals = {self._q(s) for s in self.g.subjects(predicate, entity) if isinstance(s, URIRef)}
        return sorted(vals)[:cap]

    def _restrictions(self, cls) -> list[str]:
        """Compact direct restrictions only (spec s6.3): a subClassOf a
        someValuesFrom / allValuesFrom / hasValue restriction on a named filler.
        Cardinality and nested-anonymous restrictions are excluded."""
        rendered: set[str] = set()
        keyword = ((OWL.someValuesFrom, "some"), (OWL.allValuesFrom, "only"), (OWL.hasValue, "value"))
        for node in self.g.objects(cls, RDFS.subClassOf):
            if not isinstance(node, BNode):
                continue
            if (node, RDF.type, OWL.Restriction) not in self.g:
                continue
            prop = self.g.value(node, OWL.onProperty)
            if not isinstance(prop, URIRef):
                continue
            for pred, kw in keyword:
                filler = self.g.value(node, pred)
                if filler is None:
                    continue
                if isinstance(filler, URIRef):
                    rendered.add(f"{self._q(prop)} {kw} {self._q(filler)}")
                elif isinstance(filler, Literal):
                    rendered.add(f"{self._q(prop)} {kw} {filler}")
                # Anonymous/complex fillers are intentionally skipped.
                break
        return sorted(rendered)[:SC_MAX_RESTRICTIONS]

    def _property_chains(self, prop) -> list[str]:
        chains: set[str] = set()
        for head in self.g.objects(prop, OWL.propertyChainAxiom):
            items = [self._q(i) for i in self.g.items(head) if isinstance(i, URIRef)]
            if items:
                chains.add(" o ".join(items) + f" -> {self._q(prop)}")
        return sorted(chains)[:SC_MAX_PROPERTY_CHAINS]

    def _characteristics(self, prop) -> list[str]:
        types = set(self.g.objects(prop, RDF.type))
        return [name for uri, name in SC_PROPERTY_CHARACTERISTICS if uri in types]

    # --- Profile extraction ---------------------------------------------------

    def _base_profile(self, entity, entity_type: str) -> dict:
        curie = self._q(entity)
        labels = self._get_labels(entity)
        descriptions = self._get_descriptions(entity)
        examples = self._get_examples(entity)
        notes = self._get_notes(entity, exclude=set(descriptions) | set(examples))
        return {
            "entity": entity,
            "curie": curie,
            "entity_type": entity_type,
            "canonical_label": labels[0],
            "aliases": labels[1:],
            "descriptions": descriptions,
            "examples": examples,
            "notes": notes,
        }

    def _class_profile(self, cls) -> dict:
        p = self._base_profile(cls, "owl:Class")
        p.update(
            direct_superclasses=self._named_objects(cls, RDFS.subClassOf, SC_MAX_DIRECT_SUPERCLASSES),
            direct_subclasses=self._named_subjects(RDFS.subClassOf, cls, SC_MAX_DIRECT_SUBCLASSES),
            restrictions=self._restrictions(cls),
            equivalent_classes=self._named_objects(cls, OWL.equivalentClass, SC_MAX_EQUIVALENT_CLASSES),
            disjoint_classes=self._named_objects(cls, OWL.disjointWith, SC_MAX_DISJOINT_CLASSES),
        )
        return p

    def _object_property_profile(self, prop) -> dict:
        p = self._base_profile(prop, "owl:ObjectProperty")
        inverses = self._named_objects(prop, OWL.inverseOf, SC_MAX_INVERSES)
        chains = self._property_chains(prop)
        p.update(
            domains=self._named_objects(prop, RDFS.domain, SC_MAX_DOMAINS),
            ranges=self._named_objects(prop, RDFS.range, SC_MAX_RANGES),
            inverse=inverses[0] if inverses else None,
            superproperties=self._named_objects(prop, RDFS.subPropertyOf, SC_MAX_SUPERPROPERTIES),
            subproperties=self._named_subjects(RDFS.subPropertyOf, prop, SC_MAX_SUBPROPERTIES),
            characteristics=self._characteristics(prop),
            property_chains=chains,
            property_chain_involvement=bool(chains),
        )
        return p

    def _datatype_property_profile(self, prop) -> dict:
        p = self._base_profile(prop, "owl:DatatypeProperty")
        p.update(
            domains=self._named_objects(prop, RDFS.domain, SC_MAX_DOMAINS),
            ranges=self._named_objects(prop, RDFS.range, SC_MAX_RANGES),
            superproperties=self._named_objects(prop, RDFS.subPropertyOf, SC_MAX_SUPERPROPERTIES),
            subproperties=self._named_subjects(RDFS.subPropertyOf, prop, SC_MAX_SUBPROPERTIES),
            characteristics=self._characteristics(prop),
        )
        return p

    # --- Retrieval terms ------------------------------------------------------

    def _retrieval_terms(self, profile: dict) -> list[str]:
        sources: list[str] = [profile["curie"].split(":", 1)[-1]]
        sources.append(profile["canonical_label"])
        sources.extend(profile["aliases"])
        sources.extend(profile["descriptions"])
        sources.extend(profile["examples"])
        # Schema-context labels of related NAMED entities (spec s9). Values are
        # already qnames; resolve each back to its human label where possible.
        ctx_curies: list[str] = []
        for key in ("direct_superclasses", "direct_subclasses", "domains", "ranges"):
            ctx_curies.extend(profile.get(key, []))
        for curie in ctx_curies:
            uri = self._expand(curie)
            sources.append(self._label_of(uri) if uri is not None else curie)
        return _sc_tokenize(sources, SC_MAX_RETRIEVAL_TERMS)

    def _expand(self, curie: str):
        # Only simple qnames resolve to a URI. Compound class expressions from
        # _class_expr ("A or B", "A and B") are left as-is for tokenisation --
        # expanding them would build a URIRef containing spaces.
        if ":" not in curie or " " in curie:
            return None
        prefix, local = curie.split(":", 1)
        for p, ns in self.g.namespace_manager.namespaces():
            if (p or "") == prefix:
                return URIRef(str(ns) + local)
        return None

    # --- Rendering ------------------------------------------------------------

    def _render(self, profile: dict) -> str:
        lines: list[str] = []

        def field(header: str, body_lines):
            body = [b for b in body_lines if b]
            if body:
                lines.append(f"{header}:")
                lines.extend(body)
                lines.append("")

        # NOTE: the spec's template opens with a cosmetic ``CHUNK ID:`` line
        # (``class:lis.X:schema_concept``). It is deliberately OMITTED here: the
        # pilot (results/superseded/postretrieval-trial-6, CHANGELOG 2026-07-30)
        # showed models copy
        # that surface form into slot-filling chunk citations instead of the bare
        # CURIE the strict-equality grader expects, handicapping the citation
        # slots for a reason unrelated to comprehension. ``ENTITY:`` below already
        # carries the bare CURIE as the citable identity, and context assembly
        # prepends the harness's own ``# Chunk: <entity_id>`` label, so dropping
        # the line removes a redundant, confounding surface form.
        field("ENTITY", [profile["curie"]])
        field("TYPE", [profile["entity_type"]])
        field("LABEL", [profile["canonical_label"]])
        field("ALIASES", [f"- {a}" for a in profile["aliases"]])
        field("DESCRIPTION", profile["descriptions"])

        ctx: list[str] = []
        if profile["entity_type"] == "owl:Class":
            if profile["direct_superclasses"]:
                ctx.append(f"Direct superclass(es): {'; '.join(profile['direct_superclasses'])}")
            if profile["direct_subclasses"]:
                ctx.append(f"Direct subclass(es): {'; '.join(profile['direct_subclasses'])}")
            if profile["restrictions"]:
                ctx.append(f"Restriction(s): {'; '.join(profile['restrictions'])}")
            if profile["equivalent_classes"]:
                ctx.append(f"Equivalent class(es): {'; '.join(profile['equivalent_classes'])}")
            if profile["disjoint_classes"]:
                ctx.append(f"Disjoint with: {'; '.join(profile['disjoint_classes'])}")
        else:
            if profile["domains"]:
                ctx.append(f"Domain: {'; '.join(profile['domains'])}")
            if profile["ranges"]:
                ctx.append(f"Range: {'; '.join(profile['ranges'])}")
            if profile.get("inverse"):
                ctx.append(f"Inverse: {profile['inverse']}")
            if profile["superproperties"]:
                ctx.append(f"Superproperty: {'; '.join(profile['superproperties'])}")
            if profile["subproperties"]:
                ctx.append(f"Subproperties: {'; '.join(profile['subproperties'])}")
            if profile["characteristics"]:
                ctx.append(f"Characteristics: {'; '.join(profile['characteristics'])}")
            if profile["entity_type"] == "owl:ObjectProperty":
                ctx.append(
                    "Property chain involvement: "
                    + ("yes" if profile["property_chain_involvement"] else "no")
                )
                for chain in profile["property_chains"]:
                    ctx.append(f"Property chain: {chain}")
        field("SCHEMA CONTEXT", ctx)

        field("EXAMPLES", [f"- {e}" for e in profile["examples"]])
        field("NOTES", profile["notes"])
        field("RETRIEVAL TERMS", ["; ".join(profile["retrieval_terms"])])

        return "\n".join(lines).rstrip()

    # --- Word-budget enforcement (spec s10) -----------------------------------

    @staticmethod
    def _word_count(text: str) -> int:
        return len(text.split())

    def _enforce_budget(self, profile: dict) -> str:
        """Render, then drop fields in the spec's order until under the hard word
        cap. The 'never drop' set (ids, type, label, first description, property
        domain/range, class direct superclass) is preserved."""
        text = self._render(profile)
        if self._word_count(text) <= SC_CHUNK_HARD_MAX_WORDS:
            return text

        def drop_retrieval(p):
            if p["retrieval_terms"]:
                p["retrieval_terms"] = []
                return True
            return False

        def drop_notes(p):
            if p["notes"]:
                p["notes"] = []
                return True
            return False

        def drop_extra_examples(p):
            if len(p["examples"]) > 1:
                p["examples"] = p["examples"][:1]
                return True
            return False

        def drop_extra_subclasses(p):
            if p.get("direct_subclasses") and len(p["direct_subclasses"]) > 3:
                p["direct_subclasses"] = p["direct_subclasses"][:3]
                return True
            return False

        def drop_disjoint(p):
            if p.get("disjoint_classes"):
                p["disjoint_classes"] = []
                return True
            return False

        def drop_equivalent(p):
            if p.get("equivalent_classes"):
                p["equivalent_classes"] = []
                return True
            return False

        def drop_second_description(p):
            if len(p["descriptions"]) > 1:
                p["descriptions"] = p["descriptions"][:1]
                return True
            return False

        def drop_extra_aliases(p):
            if len(p["aliases"]) > 2:
                p["aliases"] = p["aliases"][:2]
                return True
            return False

        for step in (
            drop_retrieval, drop_notes, drop_extra_examples, drop_extra_subclasses,
            drop_disjoint, drop_equivalent, drop_second_description, drop_extra_aliases,
        ):
            step(profile)
            text = self._render(profile)
            if self._word_count(text) <= SC_CHUNK_HARD_MAX_WORDS:
                break
        return text

    # --- Main load ------------------------------------------------------------

    def load(self):
        self.g = Graph()
        self.g.parse(self.file_path, format="turtle")

        builders = [
            (OWL.Class, self._class_profile),
            (OWL.ObjectProperty, self._object_property_profile),
            (OWL.DatatypeProperty, self._datatype_property_profile),
        ]

        docs = []
        seen_chunk_ids: set[str] = set()
        for rdf_type, build in builders:
            entities = sorted(
                (s for s in self.g.subjects(RDF.type, rdf_type) if isinstance(s, URIRef)),
                key=lambda s: self._q(s),
            )
            for entity in entities:
                entity_id = self._q(entity)
                scoped = _format_scoped_chunk_id("schema-concept", entity_id)
                if scoped in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(scoped)

                profile = build(entity)
                profile["retrieval_terms"] = self._retrieval_terms(profile)
                page_content = self._enforce_budget(profile)

                doc = Document(page_content=page_content, metadata={})
                _add_common_ontology_metadata(
                    doc,
                    format_name="schema-concept",
                    source=self.file_path,
                    entity_id=entity_id,
                    entity_uri=str(entity),
                    label=profile["canonical_label"],
                    entity_type=profile["entity_type"],
                )
                docs.append(doc)

        return docs


def load_turtle_file(file_path):
    strategy = os.getenv("CHUNKING_STRATEGY", "entity-based")
    if strategy == "entity-based":
        loader = EntityBasedTurtleLoader(file_path, include_external_vocab=True)
    else:
        loader = NaiveTurtleLoader(file_path)

    ttl_splits = loader.load()

    file_name = os.path.basename(file_path)

    for doc in ttl_splits:
        doc.metadata.update({
            "source": file_name,
            "type": "turtle"
        })

    return ttl_splits


def load_elot_org_file(file_path):
    loader = EntityBasedElotOrgLoader(file_path)
    return loader.load()


def load_elot_org_ancestors_file(file_path):
    loader = EntityBasedElotOrgLoader(
        file_path,
        include_ancestor_headings=True,
        format_name="elot-org-ancestors",
    )
    return loader.load()


def load_omn_file(file_path):
    loader = EntityBasedOmnLoader(file_path)
    return loader.load()


def load_jsonld_file(file_path):
    loader = EntityBasedJsonLdLoader(file_path)
    return loader.load()


def load_yamlld_file(file_path):
    loader = EntityBasedYamlLdLoader(file_path)
    return loader.load()


def load_ofn_file(file_path):
    loader = EntityBasedOfnLoader(file_path)
    return loader.load()


def load_schema_concept_file(file_path):
    loader = EntityBasedSchemaConceptLoader(file_path)
    return loader.load()


def load_ontology_file(file_path, corpus_format):
    if corpus_format == "turtle":
        print(f"Loading Turtle: {os.path.basename(file_path)}")
        return load_turtle_file(file_path)
    if corpus_format == "elot-org":
        print(f"Loading ELOT Org: {os.path.basename(file_path)}")
        return load_elot_org_file(file_path)
    if corpus_format == "elot-org-ancestors":
        print(f"Loading ELOT Org with ancestors: {os.path.basename(file_path)}")
        return load_elot_org_ancestors_file(file_path)
    if corpus_format == "omn":
        print(f"Loading OMN: {os.path.basename(file_path)}")
        return load_omn_file(file_path)
    if corpus_format == "jsonld":
        print(f"Loading JSON-LD: {os.path.basename(file_path)}")
        return load_jsonld_file(file_path)
    if corpus_format == "yaml-ld":
        print(f"Loading YAML-LD: {os.path.basename(file_path)}")
        return load_yamlld_file(file_path)
    if corpus_format == "ofn":
        print(f"Loading OFN: {os.path.basename(file_path)}")
        return load_ofn_file(file_path)
    if corpus_format == "schema-concept":
        print(f"Loading schema-concept: {os.path.basename(file_path)}")
        return load_schema_concept_file(file_path)
    raise ValueError(f"Unsupported CORPUS_FORMAT: {corpus_format}")

def load_markdown_file(file_path):
    with open(file_path, "r") as file:
        markdown_document = file.read() 

    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on, strip_headers=False)
    md_splits = markdown_splitter.split_text(markdown_document)

    file_name = os.path.basename(file_path)
    for i, doc in enumerate(md_splits):
        doc.metadata.update({
            "source": file_name,
            "type": "markdown"
        })

    return md_splits

def load_web_page(url):
    sitemap_url = url + "sitemap.xml"
    xml = requests.get(sitemap_url, timeout=10).text
    soup = BeautifulSoup(xml, "xml")
    urls = [loc.text.strip() for loc in soup.find_all("loc")]

    # exclude deep ontology pages
    filtered_urls = [
        u for u in urls
        if not re.match(r"^https://rds\.posccaesar\.org/ontology/(plm|lis14)/.+", u)
    ]

    loader = WebBaseLoader(filtered_urls)
    web_pages = loader.load()

    for i, doc in enumerate(web_pages):
        doc.metadata.update({
            "type": "webpage"
        })

    return web_pages

def load_latex_file(file_path):
    with open(file_path, "r") as file:
        latex_text = file.read()

    latex_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.LATEX,   
        chunk_size=1200,
        chunk_overlap=100
    )

    latex_docs = latex_splitter.create_documents([latex_text])

    file_name = os.path.basename(file_path)

    # Add metadata
    for doc in latex_docs:
        doc.metadata.update({
            "source": file_name,
            "type": "latex"
        })

    return latex_docs

def load_txt_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        raw_text = file.read()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=100
    )

    chunks = text_splitter.split_text(raw_text)

    file_name = os.path.basename(file_path)

    docs = [
        Document(
            page_content=chunk,
            metadata={
                "source": file_name,
                "type": "txt"
            }
        )
        for chunk in chunks
    ]

    return docs

def load_always_include_documents():
    docs = []
    if os.path.exists(DO_NOT_EMBED_DIR):
        for root, _, files in os.walk(DO_NOT_EMBED_DIR):
            for filename in files:
                full_path = Path(root) / filename
                text = full_path.read_text(encoding="utf-8")
                source_filename = full_path.relative_to(DO_NOT_EMBED_DIR)
                type = full_path.suffix.lstrip(".").lower()
                docs.append(Document(page_content=text, metadata={"source": str(source_filename), "type": type}))
    return docs


def get_corpus_format():
    corpus_format = os.getenv("CORPUS_FORMAT", "turtle")
    if corpus_format not in ONTOLOGY_FILE_EXTENSIONS:
        raise ValueError(
            f"Unsupported CORPUS_FORMAT '{corpus_format}'. "
            f"Expected one of: {', '.join(ONTOLOGY_FILE_EXTENSIONS)}"
        )
    return corpus_format


def get_assistant_corpus_mode():
    mode = os.getenv("ASSISTANT_CORPUS_MODE", "full")
    if mode not in {"full", "ontology"}:
        raise ValueError("ASSISTANT_CORPUS_MODE must be 'full' or 'ontology'")
    return mode


def should_load_data_file(filename, corpus_format=None, corpus_mode=None):
    corpus_format = corpus_format or get_corpus_format()
    corpus_mode = corpus_mode or get_assistant_corpus_mode()
    suffix = Path(filename).suffix.lower()
    selected_ontology_suffix = ONTOLOGY_FILE_EXTENSIONS[corpus_format]

    if suffix in ONTOLOGY_FILE_EXTENSIONS.values():
        return suffix == selected_ontology_suffix

    if corpus_mode == "ontology":
        return False

    return (
        filename.endswith(".md")
        or filename.endswith(".tex")
        or (filename.endswith(".txt") and filename != "url.txt")
        or filename == "url.txt"
    )


def iter_loadable_data_files():
    corpus_format = get_corpus_format()
    corpus_mode = get_assistant_corpus_mode()
    for filename in sorted(os.listdir(DATA_DIR)):
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.isfile(file_path) and should_load_data_file(filename, corpus_format, corpus_mode):
            yield filename, file_path


def load_all_documents():
    all_docs = []
    corpus_format = get_corpus_format()
    corpus_mode = get_assistant_corpus_mode()

    print(f"Corpus mode: {corpus_mode}; ontology format: {corpus_format}")

    for filename, file_path in iter_loadable_data_files():
        # Selected ontology representation
        if Path(filename).suffix.lower() in ONTOLOGY_FILE_EXTENSIONS.values():
            ontology_docs = load_ontology_file(file_path, corpus_format)
            all_docs.extend(ontology_docs)

        # Markdown files
        elif filename.endswith(".md"):
            print(f"Loading Markdown: {filename}")
            md_docs = load_markdown_file(file_path)
            all_docs.extend(md_docs)

        # LaTeX (.tex)
        elif filename.endswith(".tex"):
            print(f"Loading LaTeX: {filename}")
            latex_docs = load_latex_file(file_path)
            all_docs.extend(latex_docs)

        # Plain text files (SKIP url.txt)
        elif filename.endswith(".txt") and filename != "url.txt":
            print(f"Loading Text: {filename}")
            txt_docs = load_txt_file(file_path)
            all_docs.extend(txt_docs)

        # URLs (only for url.txt)
        elif filename == "url.txt":
            print(f"Loading URLs from: {filename}")
            with open(file_path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]

            for url in urls:
                try:
                    print(f"Fetching sitemap for: {url}")
                    url_docs = load_web_page(url)
                    all_docs.extend(url_docs)
                except Exception as e:
                    print(f"Skipping {url} — {e}")

    print(f"\nLoaded total of {len(all_docs)} document chunks.\n")
    return all_docs


# if __name__ == "__main__":
#     docs = load_all_documents()

#     print("\n=== Showing TEXT (.txt) chunks ===\n")
#     for d in docs:
#         if d.metadata.get("type") == "txt":
#             print("---- CHUNK ----")
#             print(d.page_content)
#             print("Metadata:", d.metadata)
#             print()
