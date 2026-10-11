"""Format x task comparison study harness (additive).

This package runs the dissertation experiment that compares three ontology
serialisation formats (Turtle, ELOT Org-mode, OWL Manchester Syntax) across two
post-retrieval task types (restriction verification, constrained slot-filling)
and two context conditions (oracle, retrieved).

It is intentionally separate from ``app`` (the production assistant) and
``eval`` (the conversational QA evaluation). It reuses the real chunkers in
``app.document_loaders`` but runs its own clean, single-query, parameterised
pipeline so format is the only thing that varies in the context block.
"""
