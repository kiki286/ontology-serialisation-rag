"""Acceptance test for post-retrieval checkpoint/resume.

Pytest-compatible (``test_*`` functions) but also runnable without pytest, matching
the repo's convention:

    python -m experiment.tests.test_postretrieval_checkpoint

Fully offline: ``run_one`` is stubbed to record its arguments and return a synthetic
row instead of calling a model, so no provider access and no spend.

The claim under test is that resuming is not an approximation of the interrupted
run but a REPRODUCTION of it. ``run_one`` is a pure function of
(task, format, condition, model, seed, pad_*), every component of which is in the
checkpoint key, so a row replayed from disk is the row the call would have
produced. The three properties that matter:

  1. a crash loses nothing that already completed;
  2. resuming re-issues exactly the calls that did NOT complete -- no duplicates
     (which would be double spend) and no gaps (which would be missing data);
  3. the final raw and scored output is identical to an uninterrupted run.

Motivated by the 2026-08-19 overnight failure: an Ollama read timeout in cell 4 of
56 discarded ~540 completed, billed API calls because rows were accumulated in
memory and the results directory was not created until the loop returned.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from experiment import postretrieval
from experiment.config import BENCHMARK_DIR
from experiment.schemas import load_tasks

FORMATS = ["turtle", "omn"]
CONDITIONS = ["oracle"]
MODELS = ["m-api", "m-local"]
SEEDS = [11, 22]


class _SimulatedTimeout(RuntimeError):
    """Stands in for the requests.ReadTimeout raised by the Ollama branch."""


def _tasks():
    return load_tasks(BENCHMARK_DIR / "tasks_60.yaml")[:4]


def _stub(calls: list, fail_after: int | None):
    """A run_one replacement that records its call tuple and can fail on cue."""

    def fake_run_one(task, corpus_format, condition, model, k, *, trial_idx, seed, **kwargs):
        calls.append((task.task_id, corpus_format, condition, model, trial_idx))
        if fail_after is not None and len(calls) > fail_after:
            raise _SimulatedTimeout("simulated provider read timeout")
        row = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "reasoning_type": task.reasoning_type,
            "query_source": task.query_source,
            "mechanism": task.mechanism,
            "format": corpus_format,
            "condition": condition,
            "model": model,
            "trial_idx": trial_idx,
            "seed": seed,
            "parse_ok": True,
            "grade_correct": 1,
            "grade_answered": 1,
            "grade_selective_correct": 1,
            "raw_response": f"resp-{task.task_id}-{corpus_format}-{model}-{trial_idx}",
        }
        return row, {}

    return fake_run_one


def _run(checkpoint_path, calls, fail_after=None):
    original = postretrieval.run_one
    postretrieval.run_one = _stub(calls, fail_after)
    try:
        return postretrieval.run_postretrieval(
            _tasks(), FORMATS, CONDITIONS, MODELS, 5,
            seeds=SEEDS, checkpoint_path=checkpoint_path,
        )
    finally:
        postretrieval.run_one = original


def test_resume_reproduces_an_uninterrupted_run():
    baseline_calls: list = []
    baseline_raw, baseline_scored = _run(None, baseline_calls)

    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / postretrieval.CHECKPOINT_NAME
        crash_calls: list = []
        try:
            _run(checkpoint, crash_calls, fail_after=9)
        except _SimulatedTimeout:
            pass
        else:  # pragma: no cover - the stub must raise
            raise AssertionError("stub did not raise; the crash path was not exercised")

        resume_calls: list = []
        resumed_raw, resumed_scored = _run(checkpoint, resume_calls)

    assert resumed_raw == baseline_raw, "resumed raw rows differ from an uninterrupted run"
    assert resumed_scored == baseline_scored, "resumed scored rows differ"
    # No duplicates and no gaps: the two attempts together issue exactly the calls
    # one clean run issues. A duplicate would be double spend; a gap, missing data.
    assert 9 + len(resume_calls) == len(baseline_calls)
    assert sorted(crash_calls[:9] + resume_calls) == sorted(baseline_calls)


def test_completed_rows_survive_a_crash():
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / postretrieval.CHECKPOINT_NAME
        calls: list = []
        try:
            _run(checkpoint, calls, fail_after=5)
        except _SimulatedTimeout:
            pass
        done = postretrieval.load_checkpoint(checkpoint)
    # The 6th call raised; the 5 before it are durable.
    assert len(done) == 5
    assert all(len(key) == 5 for key in done)


def test_truncated_final_line_is_dropped_not_fatal():
    """A process killed mid-write leaves a partial line; that row is re-called."""
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / postretrieval.CHECKPOINT_NAME
        calls: list = []
        try:
            _run(checkpoint, calls, fail_after=6)
        except _SimulatedTimeout:
            pass
        text = checkpoint.read_text(encoding="utf-8")
        checkpoint.write_text(text[: -len(text.splitlines()[-1]) // 2], encoding="utf-8")

        recovered = postretrieval.load_checkpoint(checkpoint)
        assert len(recovered) == 5, "the intact rows should still load"

        resume_calls: list = []
        resumed_raw, _ = _run(checkpoint, resume_calls)
        # The half-written row is simply re-called, not lost and not corrupt.
        total_cells = len(_tasks()) * len(FORMATS) * len(CONDITIONS) * len(MODELS) * len(SEEDS)
        assert len(recovered) + len(resume_calls) == total_cells
        assert len(resumed_raw) == total_cells


def test_checkpoint_rows_are_json_serialisable_verbatim():
    """The checkpoint must round-trip rows unchanged, or resume would alter data."""
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / postretrieval.CHECKPOINT_NAME
        calls: list = []
        raw, _scored = _run(checkpoint, calls)
        on_disk = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines()]
    assert on_disk == raw


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)
