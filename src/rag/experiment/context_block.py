"""Assemble the per-call context block.

This is the only place where format actually varies. The block is:

    <prefix block>            # namespace declarations only, prepended once
    # --- chunk boundary ---
    # Chunk: <entity_id>
    <chunk content>
    # --- chunk boundary ---
    # Chunk: <entity_id>
    <chunk content>
    ...

The prefix block is deliberately *namespace declarations only*: Turtle's source
bundles @prefix lines with the owl:Ontology declaration (description,
contributors, versions), so we slice that down to just @prefix/@base lines.
ELOT and OMN keep their prefix blocks prefix-only natively. This prevents
ontology-level metadata from leaking into one format's context but not another.
``assert_prefix_equivalence`` enforces that the three prefix blocks declare the
same {prefix: uri} map and contain no metadata.
"""

from __future__ import annotations

import json
import re

from app.document_loaders import dump_yamlld, load_yamlld
from experiment.config import CHUNK_DELIMITER, CHUNK_LABEL, ontology_path

# Tokens that indicate ontology-level metadata has leaked into a prefix block.
# These never appear in a pure namespace-declaration block (declaring the
# `dcterms` prefix yields "dcterms:" but not "dcterms:description").
_LEAKAGE_MARKERS = (
    "dcterms:description",
    "dcterms:contributor",
    "dcterms:creator",
    "owl:versionInfo",
    "owl:versionIRI",
    "owl:Ontology",
    "Annotations:",
    "orcid.org",
    "naturalLanguageDefinition",
)


def _is_elot_format(corpus_format: str) -> bool:
    return corpus_format in {"elot-org", "elot-org-ancestors"}


def _read_source(corpus_format: str) -> str:
    return ontology_path(corpus_format).read_text(encoding="utf-8")


def extract_prefix_block(corpus_format: str, source: str | None = None) -> str:
    """Return the namespace-declaration-only prefix block, in native syntax."""
    src = source if source is not None else _read_source(corpus_format)
    lines = src.splitlines()

    if corpus_format == "schema-concept":
        # schema-concept indexes the canonical Turtle, so its namespace block is
        # Turtle's. Reuse it verbatim rather than defining a second representation.
        return extract_prefix_block("turtle", src)

    if corpus_format == "turtle":
        kept = [
            ln
            for ln in lines
            if ln.lstrip().startswith("@prefix") or ln.lstrip().startswith("@base")
        ]
        return "\n".join(kept).rstrip()

    if corpus_format == "omn":
        kept = [ln for ln in lines if ln.lstrip().startswith("Prefix:")]
        return "\n".join(kept).rstrip()

    if corpus_format == "ofn":
        # OFN declares namespaces as ``Prefix(lis:=<...>)`` lines above Ontology(...).
        kept = [ln for ln in lines if ln.lstrip().startswith("Prefix(")]
        return "\n".join(kept).rstrip()

    if corpus_format == "jsonld":
        # The source file's top-level @context is the namespace-declaration block.
        context = json.loads(src).get("@context", {})
        return json.dumps({"@context": context}, indent=2, sort_keys=True, ensure_ascii=False)

    if corpus_format == "yaml-ld":
        # YAML mirror of the JSON-LD @context block (same map, YAML 1.2 emit).
        context = load_yamlld(src).get("@context", {})
        return dump_yamlld({"@context": context})

    if _is_elot_format(corpus_format):
        # The ** Prefixes section: heading through to the next level-2 heading.
        start = next(
            (i for i, ln in enumerate(lines) if re.match(r"^\*\*\s+Prefixes\b", ln)),
            None,
        )
        if start is None:
            return ""
        end = start + 1
        while end < len(lines) and not re.match(r"^\*\*\s+\S", lines[end]):
            end += 1
        return "\n".join(lines[start:end]).rstrip()

    raise ValueError(f"unknown format {corpus_format!r}")


def parse_prefix_map(corpus_format: str, block: str) -> dict[str, str]:
    """Parse a prefix block into a {prefix: uri} map (@base excluded)."""
    if corpus_format == "schema-concept":
        # Block is Turtle @prefix syntax (see extract_prefix_block).
        return parse_prefix_map("turtle", block)
    if corpus_format in ("jsonld", "yaml-ld"):
        # The block is a JSON/YAML ``@context`` object; @-keys are JSON-LD keywords.
        loaded = json.loads(block) if corpus_format == "jsonld" else load_yamlld(block)
        context = loaded.get("@context", {})
        return {
            k: v
            for k, v in context.items()
            if isinstance(v, str) and not k.startswith("@")
        }

    out: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if corpus_format == "turtle":
            m = re.match(r"@prefix\s+([^:]*):\s*<([^>]+)>", line)
            if m:
                out[m.group(1).strip()] = m.group(2)
        elif corpus_format == "omn":
            m = re.match(r"Prefix:\s*([^:\s]*):\s*<([^>]+)>", line)
            if m:
                out[m.group(1).strip()] = m.group(2)
        elif corpus_format == "ofn":
            m = re.match(r"Prefix\(\s*([^:\s]*):\s*=\s*<([^>]+)>\s*\)", line)
            if m:
                out[m.group(1).strip()] = m.group(2)
        elif _is_elot_format(corpus_format):
            m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
            if not m:
                continue
            prefix, uri = m.group(1).strip(), m.group(2).strip()
            if prefix.lower() in {"prefix", "----------"} or uri.lower() in {"uri", "-----"}:
                continue
            out[prefix.rstrip(":")] = uri
        else:
            raise ValueError(f"unknown format {corpus_format!r}")
    return out


def assert_prefix_equivalence(prefix_blocks: dict[str, str]) -> dict[str, str]:
    """Assert all prefix blocks declare the same map and carry no metadata.

    Returns the shared {prefix: uri} map on success. Raises ValueError with a
    full diff otherwise. This is the Stage-1 comparability gate.
    """
    maps = {fmt: parse_prefix_map(fmt, blk) for fmt, blk in prefix_blocks.items()}

    errors: list[str] = []

    # 1. No metadata leakage.
    for fmt, block in prefix_blocks.items():
        leaked = [m for m in _LEAKAGE_MARKERS if m in block]
        if leaked:
            errors.append(f"  {fmt}: prefix block leaks metadata markers {leaked}")

    # 2. Identical {prefix: uri} maps across formats.
    reference_fmt = next(iter(maps))
    reference = maps[reference_fmt]
    for fmt, mapping in maps.items():
        if fmt == reference_fmt:
            continue
        missing = set(reference) - set(mapping)
        extra = set(mapping) - set(reference)
        mismatched = {
            p: (reference[p], mapping[p])
            for p in set(reference) & set(mapping)
            if reference[p] != mapping[p]
        }
        if missing:
            errors.append(f"  {fmt}: missing prefixes vs {reference_fmt}: {sorted(missing)}")
        if extra:
            errors.append(f"  {fmt}: extra prefixes vs {reference_fmt}: {sorted(extra)}")
        if mismatched:
            errors.append(f"  {fmt}: prefix URI mismatch vs {reference_fmt}: {mismatched}")

    if errors:
        raise ValueError("prefix-block equivalence failed:\n" + "\n".join(errors))
    return reference


def assemble_context_block(
    corpus_format: str,
    chunks: list[tuple[str, str]],
    *,
    prefix_block: str | None = None,
) -> str:
    """Build the full context block.

    ``chunks`` is an ordered list of (entity_id, page_content). Order is the
    gold order (oracle) or the retrieval rank (retrieved).
    """
    pb = prefix_block if prefix_block is not None else extract_prefix_block(corpus_format)
    parts: list[str] = []
    if pb:
        parts.append(pb)
    for entity_id, content in chunks:
        parts.append(CHUNK_DELIMITER)
        parts.append(CHUNK_LABEL.format(entity_id=entity_id))
        parts.append(content)
    return "\n".join(parts)
