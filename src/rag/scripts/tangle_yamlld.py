#!/usr/bin/env python3
"""Generate a canonical YAML-LD serialization of the LIS-14 ontology.

YAML-LD (W3C First Public Working Draft, 2026-03-04) is a set of conventions over
YAML such that any YAML-LD document converts to a valid JSON-LD document. It builds
the exact same compacted JSON-LD object as ``scripts/tangle_jsonld.py`` 
(``build_jsonld_object``) and renders it as YAML instead of JSON, via 
``app.document_loaders.canonicalize_yamlld``.

YAML 1.2 Core Schema (ruamel.yaml), anchors/aliases disabled, ``@list`` order
preserved The source file is ``data/LIS-14-for-FDIS (1).yamlld``.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

from app.document_loaders import (  # noqa: E402
    canonicalize_jsonld_object,
    canonicalize_yamlld,
    load_yamlld,
)
from scripts.tangle_jsonld import build_jsonld_object  # noqa: E402

DATA_DIR = RAG_DIR / "data"
TTL_PATH = DATA_DIR / "LIS-14-for-FDIS (1).ttl"
YAMLLD_PATH = DATA_DIR / "LIS-14-for-FDIS (1).yamlld"


def build_yamlld(ttl_path: Path) -> str:
    text = canonicalize_yamlld(build_jsonld_object(ttl_path), inline_bnodes=True)
    return text if text.endswith("\n") else text + "\n"


def main() -> int:
    if not TTL_PATH.exists():
        raise SystemExit(f"Turtle source not found: {TTL_PATH}")

    text = build_yamlld(TTL_PATH)

    # Determinism gate: regenerating must be byte-identical.
    if build_yamlld(TTL_PATH) != text:
        raise SystemExit("YAML-LD generation is not deterministic across runs")

    # Round-trip conformance gate (the YAML-LD spec's core constraint): the emitted
    # YAML must parse back to exactly the canonical JSON-LD object it was emitted
    # from (keys sorted, bnodes inlined -- the same object the JSON-LD file holds).
    expected = canonicalize_jsonld_object(build_jsonld_object(TTL_PATH), inline_bnodes=True)
    if load_yamlld(text) != expected:
        raise SystemExit("YAML-LD does not round-trip to the JSON-LD object")

    YAMLLD_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {YAMLLD_PATH} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
