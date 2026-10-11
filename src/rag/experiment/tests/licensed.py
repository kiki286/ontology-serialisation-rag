"""Skip markers for tests that need material this repository does not redistribute.

The ontology corpus is licensed (README, "The ontology corpus"), so its files are
absent from a fresh clone, and the committed run outputs carry no prompt text:
their ``user_content`` column is blank because the prompt embeds the ontology
chunks. Tests that read either skip with the reason rather than fail.
"""

import csv

import pytest

from experiment.config import DATA_DIR, ONTOLOGY_FILES, RESULTS_DIR

PILOT_RAW = RESULTS_DIR / "superseded" / "postretrieval-trial-4" / "postretrieval_raw.csv"

_missing = sorted({name for name in ONTOLOGY_FILES.values() if not (DATA_DIR / name).exists()})

needs_ontology = pytest.mark.skipif(
    bool(_missing),
    reason="needs the licensed ontology: missing from src/rag/data/: " + ", ".join(_missing),
)


def _prompt_text_withheld(path):
    csv.field_size_limit(10**9)
    with open(path, encoding="utf-8", newline="") as handle:
        return all(not row["user_content"] for row in csv.DictReader(handle))


needs_prompt_text = pytest.mark.skipif(
    _prompt_text_withheld(PILOT_RAW),
    reason="needs the licensed ontology: the prompt text (user_content) in "
    f"{PILOT_RAW.relative_to(RESULTS_DIR.parent.parent)} is withheld",
)
