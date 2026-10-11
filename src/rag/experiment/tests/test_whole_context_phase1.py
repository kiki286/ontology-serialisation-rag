"""Offline regressions for the Phase 1 whole-context construction."""

from __future__ import annotations

from experiment import corpus_index
from experiment.config import FORMATS, ontology_path
from experiment.context_block import assemble_context_block
from experiment.tests.licensed import needs_ontology


@needs_ontology
def test_whole_context_provider_returns_source_file_verbatim():
    for corpus_format in FORMATS:
        with ontology_path(corpus_format).open("r", encoding="utf-8", newline="") as source:
            expected = source.read()
        assert corpus_index.get_source_file_context(corpus_format) == expected


@needs_ontology
def test_source_file_is_not_chunk_scaffolded():
    source = corpus_index.get_source_file_context("turtle")
    chunked = assemble_context_block("turtle", corpus_index.get_all_chunks("turtle"))

    assert "# Chunk:" not in source
    assert "# --- chunk boundary ---" not in source
    assert source != chunked