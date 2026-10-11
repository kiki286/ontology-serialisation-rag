"""Assess one draft benchmark item without requiring the complete benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.recoverability import assess_draft_recoverability  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess one draft item's seven-format recoverability profile."
    )
    parser.add_argument("draft", type=Path, help="YAML file containing one task mapping")
    args = parser.parse_args(argv)
    raw = yaml.safe_load(args.draft.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit("draft must contain one YAML task mapping")
    try:
        assessment = assess_draft_recoverability(raw)
    except ValueError as exc:
        raise SystemExit(f"invalid draft: {exc}") from exc
    print(json.dumps(assessment, indent=2, sort_keys=True))
    return 0 if assessment["gate_verdict"] in {"pass", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())