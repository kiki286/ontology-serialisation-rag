"""Run the full benchmark authoring constraints at task-load time."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import TASKS_PATH  # noqa: E402
from experiment.schemas import load_tasks, validate_authoring_constraints  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the complete 60-item benchmark.")
    parser.add_argument("--tasks", type=Path, default=TASKS_PATH)
    parser.add_argument(
        "--skip-profile-check",
        action="store_true",
        help="validate allocation counts without loading ontology chunks to recompute profiles",
    )
    args = parser.parse_args(argv)
    tasks = load_tasks(args.tasks)
    validate_authoring_constraints(tasks, verify_profiles=not args.skip_profile_check)
    print(f"authoring constraints passed: {len(tasks)} tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())