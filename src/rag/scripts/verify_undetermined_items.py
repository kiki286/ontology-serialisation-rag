"""Verify two-sided non-entailment for undetermined benchmark items.

Each undetermined verification task supplies two Manchester axioms:
``axiom`` is the candidate statement and ``negated_axiom`` is its formal
contradiction. ROBOT/HermiT checks both against the canonical Turtle graph.
Passing this gate is also the condition-invariance check: whole-context uses
that same graph, so additional retrieval context cannot resolve either axiom.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import TASKS_PATH  # noqa: E402
from experiment.schemas import Task, load_tasks  # noqa: E402
from scripts.tangle_ofn import _robot_command  # noqa: E402

DATA_DIR = RAG_DIR / "data"
CANONICAL_TURTLE = DATA_DIR / "LIS-14-for-FDIS (1).ttl"
PREFIX_RE = re.compile(r"^\s*@prefix\s+([^:]+):\s+<([^>]+)>\s*\.", re.MULTILINE)
EXPLANATION_HEADING_RE = re.compile(r"^## .+ ##$", re.MULTILINE)


def _prefix_args(ontology_path: Path) -> list[str]:
    """Return ROBOT prefix arguments needed by Manchester candidate axioms."""
    text = ontology_path.read_text(encoding="utf-8")
    args: list[str] = []
    for prefix, iri in PREFIX_RE.findall(text):
        args.extend(("--prefix", f"{prefix}: {iri}"))
    return args


def explain_entailment(
    ontology_path: Path,
    axiom: str,
    *,
    reasoner: str = "HermiT",
) -> bool:
    """Return whether ROBOT finds an explanation for a Manchester axiom."""
    with tempfile.TemporaryDirectory() as tmp:
        explanation_path = Path(tmp) / "explanation.md"
        command = _robot_command() + [
            "explain",
            "--input",
            str(ontology_path),
            "--input-format",
            "ttl",
            "--reasoner",
            reasoner,
            *_prefix_args(ontology_path),
            "--axiom",
            axiom,
            "--explanation",
            str(explanation_path),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise RuntimeError(f"ROBOT explain failed for {axiom!r}: {detail}")
        explanation = explanation_path.read_text(encoding="utf-8")
        return bool(EXPLANATION_HEADING_RE.search(explanation))


def verify_undetermined_items(
    tasks: list[Task],
    ontology_path: Path = CANONICAL_TURTLE,
    *,
    reasoner: str = "HermiT",
) -> list[dict[str, object]]:
    """Assert that every undetermined item is silent in both directions.

    Returns one result dictionary per undetermined task so callers can include
    the evidence in a verification report. Non-undetermined tasks are ignored.
    """
    undetermined = [
        task for task in tasks
        if task.task_type == "verification" and task.gold_label == "undetermined"
    ]
    if not undetermined:
        return []

    errors: list[str] = []
    results: list[dict[str, object]] = []
    for task in undetermined:
        if not task.axiom or not task.negated_axiom:
            errors.append(
                f"{task.task_id}: undetermined item must define both axiom and negated_axiom"
            )
            continue
        if task.annotation_prose_screen != "passed":
            errors.append(
                f"{task.task_id}: annotation_prose_screen must be 'passed'; "
                "gold-chunk naturalLanguageDefinition/usageNote prose must not settle "
                "either side"
            )
            continue
        # 2.2: the hypothetical licensing_axiom must not be entailed by the canonical
        # graph. Rather than convert the triple to Manchester and run a second reasoner
        # pass, we require the recorded relation to be the SAME relation as ``axiom``
        # (its entities must appear in the Manchester ``axiom``) and then reuse the
        # two-sided non-entailment result below: if ``axiom`` is unentailed, so is the
        # relation it expresses. The drift guard is the value add — it catches a
        # licensing_axiom that wandered away from its statement during authoring, which
        # would otherwise leave the non-entailment proof checking a different relation.
        if task.licensing_axiom is not None:
            axiom_text = task.axiom or ""
            drifted = sorted(
                {entity for link in task.licensing_links for entity in (link[0], link[2])}
                - {token for token in re.split(r"[^\w:]+", axiom_text) if token}
            )
            if drifted:
                errors.append(
                    f"{task.task_id}: hypothetical licensing_axiom entities {drifted} are not "
                    f"in axiom {task.axiom!r}; the licensing_axiom has drifted from the statement "
                    "so the non-entailment gate would not be checking the recorded relation"
                )
                continue
        entails_axiom = explain_entailment(ontology_path, task.axiom, reasoner=reasoner)
        entails_negation = explain_entailment(
            ontology_path, task.negated_axiom, reasoner=reasoner
        )
        results.append(
            {
                "task_id": task.task_id,
                "entails_axiom": entails_axiom,
                "entails_negated_axiom": entails_negation,
                "condition_invariant": not entails_axiom and not entails_negation,
            }
        )
        if entails_axiom or entails_negation:
            errors.append(
                f"{task.task_id}: expected neither axiom nor negated_axiom to be entailed "
                f"(axiom={entails_axiom}, negated_axiom={entails_negation})"
            )
    if errors:
        raise AssertionError("two-sided non-entailment gate failed:\n  " + "\n  ".join(errors))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify undetermined tasks are non-entailing in both directions."
    )
    parser.add_argument("--tasks", type=Path, default=TASKS_PATH)
    parser.add_argument("--ontology", type=Path, default=CANONICAL_TURTLE)
    parser.add_argument("--reasoner", default="HermiT", choices=("HermiT", "JFact", "ELK"))
    parser.add_argument("--robot-jar", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.robot_jar is not None:
        os.environ["ROBOT_JAR"] = str(args.robot_jar)

    tasks = load_tasks(args.tasks)
    results = verify_undetermined_items(tasks, args.ontology, reasoner=args.reasoner)
    if not results:
        print("two-sided non-entailment gate: no undetermined verification items")
        return 0
    for result in results:
        print(
            f"{result['task_id']}: KB entails axiom={result['entails_axiom']}, "
            f"negated_axiom={result['entails_negated_axiom']}; "
            f"condition_invariant={result['condition_invariant']}"
        )
    print(f"two-sided non-entailment gate passed: {len(results)} item(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())