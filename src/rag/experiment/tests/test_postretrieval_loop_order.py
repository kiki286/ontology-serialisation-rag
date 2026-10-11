"""Acceptance test for the B2 post-retrieval loop reorder.

Pytest-compatible (``test_*`` functions) but also runnable without pytest, matching
the repo's convention:

    python -m experiment.tests.test_postretrieval_loop_order

Referenced by the loop-order comment in ``experiment/postretrieval.py``. Fully
offline: ``run_one`` is stubbed to record its arguments instead of calling a model,
so the current nesting can be compared exhaustively against the previous one with
no provider access and no spend.

The claim under test is that the reorder is ORDER-ONLY. ``run_one`` is a pure
function of (task, format, condition, model, seed, pad_*), so if the multiset of
those argument tuples is unchanged, neither the set of calls nor any grade can
depend on iteration order. The two structural properties the reorder exists to buy
-- trials of a cell running back-to-back, and the local Llama arm never
interleaving between an API cell's calls -- are asserted separately, since those
are what make provider prefix-caching pay.
"""

from __future__ import annotations

from collections import Counter
from itertools import groupby

from experiment import postretrieval
from experiment.config import (
    BENCHMARK_DIR,
    CONDITIONS,
    FLOOR_FORMAT_SENTINEL,
    FORMATS,
    POSTRETRIEVAL_SEEDS,
    is_floor_condition,
)
from experiment.schemas import load_tasks

TASKS_60 = BENCHMARK_DIR / "tasks_60.yaml"
MODELS = [
    "gpt-4o-2024-11-20",
    "gpt-4o-mini-2024-07-18",
    "claude-sonnet-4-5-20250929",
    "llama3.1:8b-instruct-q8_0",
]
# A floor condition is included so the sentinel collapse is exercised: floor rows
# have no format arm and must contribute ONE cell, not one per format (WI2).
CONDS = list(CONDITIONS) + ["no_context"]


def _record_calls():
    """Patch ``run_one``/``_summarise_raw_rows``; return (calls, restore)."""
    calls: list[tuple] = []
    original_run_one = postretrieval.run_one
    original_summarise = postretrieval._summarise_raw_rows

    def stub(task, corpus_format, condition, model, k, *, trial_idx, seed, **kwargs):
        calls.append((task.task_id, corpus_format, condition, model, trial_idx, seed))
        return {"stub": True}, {}

    def restore():
        postretrieval.run_one = original_run_one
        postretrieval._summarise_raw_rows = original_summarise

    postretrieval.run_one = stub
    # Not under test: the summariser needs fully graded rows, which the stub omits.
    postretrieval._summarise_raw_rows = lambda rows: []
    return calls, restore


def _previous_ordering(tasks, formats, conditions, models, seeds) -> list[tuple]:
    """The nesting in force before B2: trial -> task -> condition -> format -> model."""
    calls: list[tuple] = []
    for trial_idx, seed in enumerate(seeds):
        for task in tasks:
            for condition in conditions:
                cond_formats = (
                    [FLOOR_FORMAT_SENTINEL] if is_floor_condition(condition) else formats
                )
                for corpus_format in cond_formats:
                    for model in models:
                        calls.append(
                            (task.task_id, corpus_format, condition, model, trial_idx, seed)
                        )
    return calls


def _current_ordering(tasks, formats, conditions, models, seeds) -> list[tuple]:
    calls, restore = _record_calls()
    try:
        postretrieval.run_postretrieval(tasks, formats, conditions, models, seeds=seeds)
    finally:
        restore()
    return list(calls)


def test_reorder_is_order_only():
    """Same calls, same count, no duplicates -- only the sequence differs."""
    tasks = load_tasks(TASKS_60)
    previous = _previous_ordering(tasks, FORMATS, CONDS, MODELS, POSTRETRIEVAL_SEEDS)
    current = _current_ordering(tasks, FORMATS, CONDS, MODELS, POSTRETRIEVAL_SEEDS)

    assert Counter(previous) == Counter(current), (
        "the reorder changed WHICH calls are made, not just their order"
    )
    assert len(previous) == len(current), f"{len(previous)} != {len(current)}"
    duplicates = [call for call, n in Counter(current).items() if n > 1]
    assert not duplicates, f"duplicated calls: {duplicates[:3]}"
    assert previous != current, "ordering did not actually change; is the reorder applied?"


def test_trials_of_a_cell_run_back_to_back():
    """The three seeded trials of one prompt must be consecutive.

    This is the whole mechanism: in the chunked conditions the corpus block is
    task-specific, so the only byte-identical prompt repetition is across trials.
    If they are not adjacent the prefix is evicted between hits, and on Anthropic
    a re-written prefix costs 1.25x, i.e. worse than not caching at all.
    """
    tasks = load_tasks(TASKS_60)
    current = _current_ordering(tasks, FORMATS, CONDS, MODELS, POSTRETRIEVAL_SEEDS)
    n_trials = len(POSTRETRIEVAL_SEEDS)

    for start in range(0, len(current), n_trials):
        group = current[start : start + n_trials]
        cells = {call[:4] for call in group}
        assert len(cells) == 1, f"trials not contiguous at offset {start}: {cells}"
        assert [call[4] for call in group] == list(range(n_trials)), (
            f"trial_idx not sequential at offset {start}: {[c[4] for c in group]}"
        )


def test_local_arm_does_not_interleave_between_api_calls():
    """Llama calls must form contiguous blocks, not sit between an API cell's calls.

    Interleaving is what evicts the GPT/Anthropic prefix caches: a Llama call takes
    13-16s, so a handful between two API calls can span the provider TTL.
    """
    tasks = load_tasks(TASKS_60)
    current = _current_ordering(tasks, FORMATS, CONDS, MODELS, POSTRETRIEVAL_SEEDS)

    is_local = ["llama" in call[3].lower() for call in current]
    blocks = [(key, len(list(group))) for key, group in groupby(is_local)]
    # One block per (cell, provider-kind); with model above task/trial every model's
    # calls within a cell are contiguous, so blocks equal cells x models, not calls.
    n_cells = len(FORMATS) * len(CONDITIONS) + 1  # +1 floor cell under the sentinel
    assert len(blocks) <= n_cells * len(MODELS), (
        f"local/API runs are fragmented: {len(blocks)} blocks"
    )
    calls_per_cell_model = len(tasks) * len(POSTRETRIEVAL_SEEDS)
    for local, length in blocks:
        if local:
            assert length % calls_per_cell_model == 0, (
                f"a local block of {length} is not whole cells "
                f"({calls_per_cell_model} calls each) -- Llama is interleaving"
            )


def test_floor_condition_collapses_to_one_sentinel_cell():
    """Floor rows have no format arm, so they must not be emitted once per format."""
    tasks = load_tasks(TASKS_60)
    current = _current_ordering(tasks, FORMATS, CONDS, MODELS, POSTRETRIEVAL_SEEDS)

    floor = [call for call in current if is_floor_condition(call[2])]
    assert floor, "no floor calls recorded; adjust CONDS"
    assert {call[1] for call in floor} == {FLOOR_FORMAT_SENTINEL}, (
        "floor calls carry a real format; the format loop did not collapse"
    )
    expected = len(tasks) * len(MODELS) * len(POSTRETRIEVAL_SEEDS)
    assert len(floor) == expected, f"expected {expected} floor calls, got {len(floor)}"


def _all_tests():
    return [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]


def main() -> int:
    failures = 0
    for test in _all_tests():
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"\n{len(_all_tests()) - failures}/{len(_all_tests())} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
