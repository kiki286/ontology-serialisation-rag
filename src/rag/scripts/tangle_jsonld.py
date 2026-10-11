#!/usr/bin/env python3
"""Generate a canonical, compacted JSON-LD serialization of the LIS-14 ontology.

This is not an ELOT tangle and not a ROBOT conversion: ELOT tangles only to OWL
Manchester syntax, and ROBOT's ``--format json`` emits OBO Graphs JSON, which is
a different data model -- not JSON-LD. True JSON-LD comes from rdflib serializing
the canonical Turtle source, so the JSON-LD variant under test is axiom-identical
to the Turtle/OMN/ELOT variants.

Output is compacted against the Turtle file's own prefix map (qname ``@id``s, a
single top-level ``@context``) and canonicalized via
``app.document_loaders.canonicalize_jsonld`` (sorted keys, sorted plain arrays,
``@list`` preserved) so it is byte-stable across runs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from rdflib import Graph  # noqa: E402

from app.document_loaders import canonicalize_jsonld  # noqa: E402

DATA_DIR = RAG_DIR / "data"
TTL_PATH = DATA_DIR / "LIS-14-for-FDIS (1).ttl"
JSONLD_PATH = DATA_DIR / "LIS-14-for-FDIS (1).jsonld"

PREFIX_RE = re.compile(r"@prefix\s+([^:]*):\s*<([^>]+)>")


def ttl_prefix_map(ttl_text: str) -> dict[str, str]:
    """The Turtle file's declared ``@prefix`` set.

    Uses the source ``@prefix`` lines -- not rdflib's ``g.namespaces()``, which
    adds many default bindings -- so the JSON-LD ``@context`` declares exactly the
    same prefixes as Turtle and the Stage-1 prefix-equivalence gate passes. Mirrors
    the Turtle branch of ``experiment.context_block.parse_prefix_map``.
    """
    out: dict[str, str] = {}
    for line in ttl_text.splitlines():
        m = PREFIX_RE.match(line.strip())
        if m:
            out[m.group(1).strip()] = m.group(2)
    return out


def build_jsonld_object(ttl_path: Path) -> dict:
    """The compacted JSON-LD *object* for the whole ontology, pre-serialisation.

    Shared with ``scripts/tangle_yamlld.py`` so the YAML-LD source file is derived
    from the exact same graph and object as the JSON-LD source file -- the YAML-LD
    arm is a re-emit, not an independent serialiser.
    """
    ttl_text = ttl_path.read_text(encoding="utf-8")
    context = ttl_prefix_map(ttl_text)

    g = Graph()
    g.parse(data=ttl_text, format="turtle")

    raw = g.serialize(format="json-ld", context=context, auto_compact=True)
    doc = json.loads(raw)
    if isinstance(doc, list):
        doc = {"@graph": doc}
    # Pin @context to the exact Turtle prefix map (defensive against rdflib
    # echoing a mangled or default-extended context).
    doc["@context"] = context
    return doc


def build_jsonld(ttl_path: Path) -> str:
    return canonicalize_jsonld(build_jsonld_object(ttl_path), inline_bnodes=True) + "\n"


def main() -> int:
    if not TTL_PATH.exists():
        raise SystemExit(f"Turtle source not found: {TTL_PATH}")
    text = build_jsonld(TTL_PATH)
    JSONLD_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {JSONLD_PATH} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
