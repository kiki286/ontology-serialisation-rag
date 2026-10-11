"""Acceptance tests for the WI1-WI7 harness/schema changes.

Pytest-compatible (``test_*`` functions) but also runnable without pytest, matching
the repo's ``scripts/verify_ontology_chunkers.py`` convention:

    python -m experiment.tests.test_harness_changes

All checks are offline and pin against the committed 420-row pilot
(``results/superseded/postretrieval-trial-4``), which is known ground truth.
Ground-truth constants
here reflect the two WI6 corrections agreed for the pilot:
  * GPT-4o-mini verification accuracy is 0.643 (81/126), at/below the 0.667 baseline.
  * T04 is a >=90% ceiling (27/28 cells at 1.0, 1 exception), not a 28/28 ceiling.
"""

from __future__ import annotations

import socket
from collections import Counter
from types import SimpleNamespace

from experiment import diagnostics
from experiment.config import BENCHMARK_DIR, FORMATS, RESULTS_DIR
from experiment.grading import (
    SLOT_FIELDS,
    aggregate_verification,
    graded_slot_fields,
    validate_slot_gradeability,
)
from experiment.rescore import load_raw_csv, rescore_rows
from experiment.recoverability import assess_draft_recoverability, assess_field_recoverability
from experiment.schemas import (
    Task,
    load_tasks,
    validate_authoring_constraints,
    validate_gold_chunks_resolve,
)
from experiment.tests.licensed import PILOT_RAW, needs_ontology, needs_prompt_text
from scripts.verify_undetermined_items import verify_undetermined_items

# The complete, expected set of per-field grade changes when the pilot (graded under
# the removed class accept-list) is regraded with the current strict grader + WI2:
#   - T02 support_intermediate -> N/A for all 84 rows (WI2 exclusion)
#   - T05 class / support_class 1->0 (merged strict policy, commit 172173c)
EXPECTED_FIELD_DIFFS = {
    ("T02", "support_intermediate_correct", "1", ""): 36,
    ("T02", "support_intermediate_correct", "0", ""): 48,
    ("T05", "class_correct", "1", "0"): 24,
    ("T05", "support_class_correct", "1", "0"): 13,
}


def _load_pilot():
    raw = load_raw_csv(PILOT_RAW)
    tasks = load_tasks()
    return raw, tasks, rescore_rows(raw, tasks)


def _s(value: object) -> str:
    return "" if value is None else str(value)


def test_ollama_context_window_preserves_existing_conditions():
    from experiment import llm_call

    captured = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "model": "llama-test",
                "message": {"content": "{}"},
                "done_reason": "stop",
                "prompt_eval_count": 2,
                "eval_count": 1,
            }

    original_post = llm_call.requests.post
    original_tokenizer = llm_call._llama_tokenizer
    def fake_post(url, **kwargs):
        captured.append((url, kwargs))
        return FakeResponse()

    llm_call.requests.post = fake_post
    llm_call._llama_tokenizer = SimpleNamespace(encode=lambda text: SimpleNamespace(ids=[1, 2]))
    try:
        llm_call.call_model("llama-test", "system", "user", condition="oracle")
        llm_call.call_model("llama-test", "system", "user", condition="whole_context")
        llm_call.call_model("llama-test", "system", "user", condition="whole_context", num_ctx=49152)
    finally:
        llm_call.requests.post = original_post
        llm_call._llama_tokenizer = original_tokenizer

    assert captured[0][1]["json"]["options"]["num_ctx"] == 16384
    assert captured[1][1]["json"]["options"]["num_ctx"] == 56246
    assert captured[2][1]["json"]["options"]["num_ctx"] == 49152


@needs_ontology
def test_authoring_field_assessor_preserves_all_stored_verification_profiles():
    task_paths = [BENCHMARK_DIR / "tasks.yaml", BENCHMARK_DIR / "tasks_60.yaml"]
    tasks = [task for path in task_paths for task in load_tasks(path)]
    profiled = [
        task
        for task in tasks
        if task.task_type == "verification" and task.recoverability_profile is not None
    ]
    # 16 before the batch-05 contradicted items; T59-T65 are determinate and so
    # each carry a stored profile.
    assert len(profiled) == 23
    for task in profiled:
        assert assess_draft_recoverability(task)["profile"] == task.recoverability_profile

    domain = assess_field_recoverability(
        [("lis:hasPhysicalQuantity", "rdfs:domain", "lis:PhysicalObject")],
        ["lis:hasPhysicalQuantity"],
    )
    assert domain["profile"] == {corpus_format: True for corpus_format in FORMATS}


# ---------------------------------------------------------------------------
# WI1 - decoupled, faithful, network-free regrade
# ---------------------------------------------------------------------------
@needs_prompt_text
def test_wi1_regrade_reproduces_grades_except_documented_changes():
    raw, _tasks, scored = _load_pilot()
    by_key = {(r["task_id"], r["format"], r["condition"], r["trial_idx"], r["model"]): r for r in raw}

    field_diffs: Counter = Counter()
    verif_diffs = 0
    for new in scored:
        old = by_key[(new["task_id"], new["format"], new["condition"], new["trial_idx"], new["model"])]
        if new["task_type"] == "verification":
            if _s(new.get("grade_correct")) != _s(old.get("grade_correct")):
                verif_diffs += 1
            continue
        for field in SLOT_FIELDS:
            o, n = _s(old.get(f"grade_{field}")), _s(new.get(f"grade_{field}"))
            if o != n:
                field_diffs[(new["task_id"], field, o, n)] += 1

    assert verif_diffs == 0, f"verification grade_correct changed on {verif_diffs} rows"
    assert dict(field_diffs) == EXPECTED_FIELD_DIFFS, (
        f"unexpected per-field grade changes:\n{dict(field_diffs)}"
    )


@needs_prompt_text
def test_wi1_scoring_path_makes_no_network_calls():
    raw = load_raw_csv(PILOT_RAW)
    original = socket.socket

    def _boom(*args, **kwargs):  # pragma: no cover - only fires on failure
        raise AssertionError("scoring path attempted network access")

    socket.socket = _boom
    try:
        rescore_rows(raw[:20])
    finally:
        socket.socket = original


# ---------------------------------------------------------------------------
# WI2 - gold-driven denominator, N/A excluded fields, no unsatisfiable graded field
# ---------------------------------------------------------------------------
@needs_prompt_text
def test_wi2_denominator_and_exclusion():
    _raw, tasks, scored = _load_pilot()
    assert graded_slot_fields({t.task_id: t for t in tasks}["T02"]) == [
        "class_correct", "property_correct", "intermediate_correct",
        "support_class_correct", "support_property_correct",
    ]

    t02 = [r for r in scored if r["task_id"] == "T02"]
    t05 = [r for r in scored if r["task_id"] == "T05"]
    assert t02 and all(_s(r["grade_n_fields"]) == "5" for r in t02)
    assert t05 and all(_s(r["grade_n_fields"]) == "6" for r in t05)
    # T02 support_intermediate is N/A for all 84 rows.
    assert len(t02) == 84
    assert all(_s(r["grade_support_intermediate_correct"]) == "" for r in t02)


def test_wi2_no_unsatisfiable_graded_field():
    tasks = load_tasks()
    validate_slot_gradeability(tasks)  # passes on the real dataset

    # And fails loudly on an inconsistent item: a graded support field with no gold.
    bad = Task.model_validate(
        {
            "task_id": "BAD",
            "task_type": "slot_filling",
            "query": "q",
            "reasoning_type": "modelling_pattern",
            "query_source": "paraphrase",
            "mechanism": "test_fixture",
            "gold_chunks": ["lis:PhysicalObject"],
            "scenario": "s",
            "gold_class": "lis:PhysicalObject",
            "gold_property": "lis:hasPhysicalQuantity",
            "gold_intermediate_node": False,
            "gold_supporting_chunks": {
                "class": "lis:PhysicalObject",
                "property": "lis:hasPhysicalQuantity",
                "intermediate_node": None,  # no gold citation ...
            },
            "field_gold_chunks": {
                "class": ["lis:PhysicalObject"],
                "property": ["lis:hasPhysicalQuantity"],
                "intermediate_node": [],
                "support_class": ["lis:PhysicalObject"],
                "support_property": ["lis:hasPhysicalQuantity"],
                "support_intermediate": ["lis:ScalarQuantityDatum"],  # ... but licensed -> inconsistent
            },
        }
    )
    raised = False
    try:
        validate_slot_gradeability([bad])
    except ValueError:
        raised = True
    assert raised, "validate_slot_gradeability should reject an unsatisfiable graded field"


# ---------------------------------------------------------------------------
# WI5 - coverage covariate, ID membership (not prose)
# ---------------------------------------------------------------------------
def _present_absent(scored, task_id, condition, entity, column="context_chunk_ids"):
    import json
    present, absent = [], []
    for fmt in ["turtle", "elot-org", "elot-org-ancestors", "omn", "jsonld", "yaml-ld", "ofn"]:
        row = next(
            r for r in scored
            if r["task_id"] == task_id and r["condition"] == condition
            and r["format"] == fmt and r["trial_idx"] == "0" and r["model"] == "gpt-4o-2024-11-20"
        )
        ids = row[column] if isinstance(row[column], list) else json.loads(row[column])
        (present if entity in ids else absent).append(fmt)
    return present, absent


@needs_prompt_text
def test_wi5_coverage_membership_facts():
    _raw, _tasks, scored = _load_pilot()
    p, _ = _present_absent(scored, "T02", "retrieved", "lis:Compound")
    assert set(p) == {"elot-org", "elot-org-ancestors", "jsonld", "ofn"}
    p, a = _present_absent(scored, "T02", "oracle", "lis:Compound")
    assert p == [] and len(a) == 7
    p, _ = _present_absent(scored, "T05", "retrieved", "lis:hasPhysicalQuantity")
    assert set(p) == {"omn", "ofn"}
    p, a = _present_absent(scored, "T05", "retrieved", "lis:ScalarQuantityDatum")
    assert p == [] and len(a) == 7


@needs_prompt_text
def test_wi5_covered_property_predicts_correctness():
    _raw, _tasks, scored = _load_pilot()
    t05 = [r for r in scored if r["task_id"] == "T05"]
    true_rows = [r for r in t05 if _s(r["covered_property"]) == "1"]
    false_rows = [r for r in t05 if _s(r["covered_property"]) == "0"]
    # 18 covered cells x 3 trials, 10 uncovered cells x 3 trials.
    assert len(true_rows) == 54 and len(false_rows) == 30
    mean_true = sum(int(r["grade_property_correct"]) for r in true_rows) / len(true_rows)
    mean_false = sum(int(r["grade_property_correct"]) for r in false_rows) / len(false_rows)
    assert round(mean_true, 2) == 0.89
    assert mean_false == 0.0


# ---------------------------------------------------------------------------
# WI6 - diagnostics (with the two corrected ground-truth criteria)
# ---------------------------------------------------------------------------
@needs_prompt_text
def test_wi6_diagnostics():
    _raw, tasks, scored = _load_pilot()
    report = diagnostics.build_report(scored, tasks)
    v = report["verification"]

    assert round(v["majority_class_baseline"], 3) == 0.667
    mini = v["per_model"]["gpt-4o-mini-2024-07-18"]
    assert round(mini["accuracy"], 3) == 0.643
    assert mini["accuracy"] <= v["majority_class_baseline"]
    assert any("majority baseline" in f for f in mini["flags"])
    assert mini["modal_pred_label"] == "supported"
    assert mini["pred_label_counts"]["supported"] == 123
    assert any(">90%" in f for f in mini["flags"])
    assert v["labels_absent_everywhere"] == ["undetermined"]

    cf = report["ceiling_floor"]["per_task"]
    assert cf["T01"]["ceiling"] and cf["T01"]["cells_at_1.0"] == 28
    assert cf["T04"]["ceiling"] and cf["T04"]["cells_at_1.0"] == 27 and cf["T04"]["exception_cells"] == 1

    det = report["determinism"]
    assert det["n_cells"] == 140
    assert det["identical_raw_cells"] == 52
    assert det["distinct_system_fingerprints"] == 4


def test_d1_selective_verification_metrics():
    metrics = aggregate_verification(
        [
            {"gold_label": "supported", "pred_label": "supported", "correct": 1},
            {"gold_label": "contradicted", "pred_label": "undetermined", "correct": 0},
            {"gold_label": "supported", "pred_label": None, "correct": 0},
            {"gold_label": "contradicted", "pred_label": "contradicted", "correct": 1},
        ]
    )
    assert metrics["n_answered"] == 2
    assert metrics["coverage"] == 0.5
    assert metrics["accuracy_on_answered"] == 1.0


def test_contradicted_items_require_prose_direction():
    task_data = load_tasks()[2].model_dump()
    task_data.pop("annotation_prose_screen", None)
    try:
        Task.model_validate(task_data)
    except ValueError as exc:
        assert "annotation_prose_screen[toward|away|neutral|states_axiom]" in str(exc)
    else:
        raise AssertionError("contradicted items must record prose direction")


def test_contradicted_items_accept_states_axiom_prose_screen():
    task_data = load_tasks()[2].model_dump()
    task_data["annotation_prose_screen"] = "states_axiom"
    assert Task.model_validate(task_data).annotation_prose_screen == "states_axiom"


def test_recoverability_rejects_substrings_and_restriction_fillers():
    from experiment.recoverability import _elot_chunk_has_axiom, _ofn_chunk_has_axiom

    assert not _ofn_chunk_has_axiom(
        "SubClassOf(lis:InstantRegion lis:TemporalRegion)",
        "lis:InstantRegion",
        "rdfs:subClassOf",
        "lis:Temporal",
    )
    assert not _elot_chunk_has_axiom(
        "*** System (lis:System)\n - SubClassOf :: lis:hasFunctionalPart some lis:FunctionalObject",
        "lis:System",
        "rdfs:subClassOf",
        "lis:FunctionalObject",
    )


def test_chain_recoverability_requires_every_link_and_gold_class():
    task = {
        "task_id": "CHAIN",
        "task_type": "verification",
        "query": "q",
        "reasoning_type": "structural",
        "query_source": "label",
        "mechanism": "subsumption",
        "gold_chunks": ["lis:Function", "lis:Capability", "lis:Disposition"],
        "statement": "Every Function is a Disposition.",
        "gold_label": "supported",
        "licensing_axiom": [
            ["lis:Function", "rdfs:subClassOf", "lis:Capability"],
            ["lis:Capability", "rdfs:subClassOf", "lis:Disposition"],
        ],
    }

    def provider(_fmt, _gold):
        return [
            "lis:Function rdfs:subClassOf lis:Capability .",
            "lis:Capability rdfs:subClassOf lis:Disposition .",
        ]

    assessment = assess_draft_recoverability(task, formats=["turtle"], chunk_provider=provider)
    assert assessment["profile"] == {"turtle": True}
    assert [result["profile"] for result in assessment["per_link"]] == [
        {"turtle": True},
        {"turtle": True},
    ]

    incomplete = dict(task)
    incomplete["gold_chunks"] = ["lis:Function", "lis:Capability"]
    try:
        Task.model_validate(incomplete)
    except ValueError as exc:
        assert "missing from gold_chunks" in str(exc)
    else:
        raise AssertionError("chain items must include every chain class in gold_chunks")


def test_paper_authoring_allocation_is_jointly_satisfiable():
    allocation = load_tasks(BENCHMARK_DIR / "authoring_allocation.yaml")
    validate_authoring_constraints(allocation, verify_profiles=False)


@needs_ontology
def test_gold_validation_rejects_retrieval_excluded_oracle_chunk():
    from experiment.corpus_index import build_oracle_map

    assert "elot:root:core" not in build_oracle_map("elot-org")
    verification = load_tasks()[0].model_dump()
    slot = load_tasks()[1].model_dump()
    cases = []

    direct = dict(verification)
    direct["gold_chunks"] = ["elot:root:core"]
    cases.append((Task.model_validate(direct), {"elot:root:core", "lis:Person", "lis:Organism"}))

    oracle_override = dict(verification)
    oracle_override["gold_chunks_by_format"] = {"elot-org": ["elot:root:core"]}
    cases.append((Task.model_validate(oracle_override), {"elot:root:core", "lis:Person", "lis:Organism"}))

    retrieval = dict(verification)
    retrieval["retrieval_gold_chunks"] = ["elot:root:core"]
    cases.append((Task.model_validate(retrieval), {"elot:root:core", "lis:Person", "lis:Organism"}))

    retrieval_override = dict(verification)
    retrieval_override["retrieval_gold_chunks_by_format"] = {"elot-org": ["elot:root:core"]}
    cases.append((Task.model_validate(retrieval_override), {"elot:root:core", "lis:Person", "lis:Organism"}))

    primary = dict(slot)
    primary["primary_answer_chunk"] = "elot:root:core"
    slot_ids = set(slot["gold_chunks"]) | {"elot:root:core"}
    cases.append((Task.model_validate(primary), slot_ids))

    field = dict(slot)
    field["field_gold_chunks"] = dict(slot["field_gold_chunks"])
    field["field_gold_chunks"]["class"] = ["elot:root:core"]
    cases.append((Task.model_validate(field), slot_ids))

    for task, available_ids in cases:
        try:
            validate_gold_chunks_resolve(
                [task],
                {"elot-org": available_ids},
                {"elot-org": available_ids - {"elot:root:core"}},
            )
        except ValueError as exc:
            assert "elot:root:core" in str(exc)
            assert "excluded from the elot-org retrieval index" in str(exc)
        else:
            raise AssertionError(
                f"retrieval-excluded root must fail for every gold-bearing field: {task.task_id}"
            )


def test_undetermined_items_require_annotation_prose_screen():
    task_data = {
        "task_id": "UNDETERMINED",
        "task_type": "verification",
        "query": "q",
        "reasoning_type": "structural",
        "query_source": "paraphrase",
        "mechanism": "test_fixture",
        "gold_chunks": ["lis:PhysicalObject"],
        "statement": "A claim.",
        "gold_label": "undetermined",
        "axiom": "lis:PhysicalObject SubClassOf lis:PhysicalQuantity",
        "negated_axiom": "lis:PhysicalQuantity SubClassOf lis:PhysicalObject",
        "licensing_axiom": ["lis:PhysicalObject", "rdfs:subClassOf", "lis:PhysicalQuantity"],
    }
    raised = False
    try:
        Task.model_validate(task_data)
    except ValueError as exc:
        raised = "annotation_prose_screen" in str(exc)
    assert raised, "undetermined items must record the annotation-prose screen"


def test_undetermined_gate_rejects_failed_annotation_prose_screen():
    task = Task.model_validate(
        {
            "task_id": "UNDETERMINED_FAILED_SCREEN",
            "task_type": "verification",
            "query": "q",
            "reasoning_type": "structural",
            "query_source": "paraphrase",
            "mechanism": "test_fixture",
            "gold_chunks": ["lis:PhysicalObject", "lis:PhysicalQuantity"],
            "statement": "A claim.",
            "gold_label": "undetermined",
            "axiom": "lis:PhysicalObject SubClassOf lis:PhysicalQuantity",
            "negated_axiom": "lis:PhysicalQuantity SubClassOf lis:PhysicalObject",
            "licensing_axiom": ["lis:PhysicalObject", "rdfs:subClassOf", "lis:PhysicalQuantity"],
            "licensing_axiom_status": "hypothetical",
            "notes": "The gold chunk prose plainly settles the claim; this must fail the screen.",
            "annotation_prose_screen": "failed",
        }
    )
    try:
        verify_undetermined_items([task], ontology_path=RESULTS_DIR / "missing.ttl")
    except AssertionError as exc:
        assert "annotation_prose_screen" in str(exc)
    else:
        raise AssertionError("failed annotation-prose screen must fail the gate")


@needs_ontology
def test_recoverability_profile_is_computed_for_one_draft():
    task = next(task for task in load_tasks() if task.task_id == "T01")
    assessment = assess_draft_recoverability(task)
    assert assessment["gate_verdict"] == "pass"
    assert assessment["profile"] == {
        "turtle": True,
        "elot-org": True,
        "elot-org-ancestors": False,
        "omn": True,
        "jsonld": True,
        "yaml-ld": True,
        "ofn": True,
    }
    assert assessment["uniform"] is False


def test_undetermined_recoverability_is_explicitly_skipped():
    task = Task.model_validate(
        {
            "task_id": "UNDETERMINED_SKIP",
            "task_type": "verification",
            "query": "q",
            "reasoning_type": "structural",
            "query_source": "paraphrase",
            "mechanism": "test_fixture",
            "gold_chunks": ["lis:PhysicalObject", "lis:PhysicalQuantity"],
            "statement": "A claim.",
            "gold_label": "undetermined",
            "axiom": "lis:PhysicalObject SubClassOf lis:PhysicalQuantity",
            "negated_axiom": "lis:PhysicalQuantity SubClassOf lis:PhysicalObject",
            "licensing_axiom": ["lis:PhysicalObject", "rdfs:subClassOf", "lis:PhysicalQuantity"],
            "licensing_axiom_status": "hypothetical",
            "annotation_prose_screen": "passed",
        }
    )

    def must_not_load(_format, _ids):
        raise AssertionError("hypothetical item must skip recoverability loading")

    assessment = assess_draft_recoverability(task, chunk_provider=must_not_load)
    assert assessment["gate_verdict"] == "skipped"
    assert assessment["skip_reason"] == "hypothetical_licensing_axiom"
    assert all(value is None for value in assessment["profile"].values())


# ---------------------------------------------------------------------------
# Hypothetical licensing-axiom containment (2.5). A hypothetical axiom must be
# rejected or skipped by every path that would treat it as asserted. Each test
# actually exercises the hypothetical branch rather than passing vacuously.
# ---------------------------------------------------------------------------
def _hypothetical_item(**overrides) -> dict:
    item = {
        "task_id": "HYPOTHETICAL",
        "task_type": "verification",
        "query": "q",
        "reasoning_type": "structural",
        "query_source": "paraphrase",
        "mechanism": "test_fixture",
        "gold_chunks": ["lis:Person", "lis:PhysicalQuantity"],
        "statement": "A claim.",
        "gold_label": "undetermined",
        "axiom": "lis:Person SubClassOf lis:PhysicalQuantity",
        "negated_axiom": "lis:PhysicalQuantity SubClassOf lis:Person",
        "licensing_axiom": ["lis:Person", "rdfs:subClassOf", "lis:PhysicalQuantity"],
        "licensing_axiom_status": "hypothetical",
        "annotation_prose_screen": "passed",
    }
    item.update(overrides)
    return item


def test_undetermined_item_cannot_load_without_hypothetical_status():
    data = _hypothetical_item()
    data.pop("licensing_axiom_status")
    try:
        Task.model_validate(data)
    except ValueError as exc:
        assert "licensing_axiom_status" in str(exc)
    else:
        raise AssertionError("an undetermined item must load only with hypothetical status")


def test_hypothetical_axiom_requires_its_classes_in_gold_chunks():
    # 2.4: the object class is dropped from gold_chunks; the item must be rejected.
    data = _hypothetical_item(gold_chunks=["lis:Person"])
    try:
        Task.model_validate(data)
    except ValueError as exc:
        assert "missing from gold_chunks" in str(exc)
    else:
        raise AssertionError("hypothetical axiom classes must all be in gold_chunks")


def test_stored_status_must_match_content():
    # A single directly-serialized supported triple stored as a chain status.
    data = {
        "task_id": "MISLABELLED",
        "task_type": "verification",
        "query": "q",
        "reasoning_type": "structural",
        "query_source": "label",
        "mechanism": "subsumption",
        "gold_chunks": ["lis:Feature", "lis:PhysicalObject"],
        "statement": "Every Feature is a PhysicalObject.",
        "gold_label": "supported",
        "licensing_axiom": ["lis:Feature", "rdfs:subClassOf", "lis:PhysicalObject"],
        "licensing_axiom_status": "entailed_chain",
    }
    try:
        Task.model_validate(data)
    except ValueError as exc:
        assert "disagrees" in str(exc)
    else:
        raise AssertionError("a stored status disagreeing with content must be rejected")


def test_authoring_gate_requires_null_profile_for_hypothetical():
    task = Task.model_validate(
        _hypothetical_item(
            recoverability_profile={fmt: False for fmt in [
                "turtle", "elot-org", "elot-org-ancestors", "omn", "jsonld", "yaml-ld", "ofn",
            ]}
        )
    )
    try:
        validate_authoring_constraints([task], expected_n=1, verify_profiles=False)
    except ValueError as exc:
        assert "hypothetical recoverability must be explicitly skipped" in str(exc)
    else:
        raise AssertionError("hypothetical items must record a null recoverability profile")


def test_undetermined_gate_rejects_drifted_hypothetical_axiom():
    # The recorded licensing_axiom names lis:PhysicalObject, but the axiom is about
    # lis:PhysicalQuantity: the two express different relations, so the non-entailment
    # proof would not be checking the recorded axiom. Fails offline, before any ROBOT call.
    task = Task.model_validate(
        _hypothetical_item(
            gold_chunks=["lis:Person", "lis:PhysicalObject"],
            licensing_axiom=["lis:Person", "rdfs:subClassOf", "lis:PhysicalObject"],
        )
    )
    try:
        verify_undetermined_items([task], ontology_path=RESULTS_DIR / "missing.ttl")
    except AssertionError as exc:
        assert "drifted" in str(exc)
    else:
        raise AssertionError("a licensing_axiom that drifted from the statement must fail the gate")


def test_full_authoring_constraints_are_load_time_enforced():
    try:
        load_tasks(enforce_authoring_constraints=True)
    except ValueError as exc:
        assert "expected 60 tasks, found 5" in str(exc)
        assert "task_type=verification: expected 30" in str(exc)
    else:
        raise AssertionError("the five-item pilot must not satisfy the 60-item authoring gate")


# ---------------------------------------------------------------------------
# WI7 - oracle_padded: entities sampled once per task, identical across formats
# ---------------------------------------------------------------------------
@needs_ontology
def test_wi7_padding_is_shared_across_formats_and_deterministic():
    from experiment.config import FORMATS, RETRIEVAL_K
    from experiment.postretrieval import task_gold_union, task_padding_ids

    tasks = {t.task_id: t for t in load_tasks()}
    # T01/T03/T04 have gold below k, so they actually get padded.
    for tid in ("T01", "T03", "T04"):
        task = tasks[tid]
        per_format = {f: task_padding_ids(task, f, RETRIEVAL_K) for f in FORMATS}
        first = per_format[FORMATS[0]]
        # Same padding entity SET across every format (the key invariant).
        for fmt, ids in per_format.items():
            assert set(ids) == set(first), f"{tid}: padding differs in {fmt}"
        # Pads exactly up to k, and never overlaps gold.
        assert len(first) == RETRIEVAL_K - len(task.gold_chunks)
        assert not (set(first) & set(task_gold_union(task)))
        # Deterministic across calls (pinned per-task seed).
        assert task_padding_ids(task, FORMATS[0], RETRIEVAL_K) == first
    # Different tasks draw different samples.
    assert task_padding_ids(tasks["T01"], FORMATS[0], RETRIEVAL_K) != \
        task_padding_ids(tasks["T03"], FORMATS[0], RETRIEVAL_K)
    # Slot tasks already at/over k -> no padding (never truncates gold).
    assert task_padding_ids(tasks["T02"], FORMATS[0], RETRIEVAL_K) == []  # 5 gold == k
    assert task_padding_ids(tasks["T05"], FORMATS[0], RETRIEVAL_K) == []  # 10 gold > k


# ---------------------------------------------------------------------------
# SupportingChunks tolerates ABSENT keys (not just null) - the real Pydantic fix
# ---------------------------------------------------------------------------
def test_supporting_chunks_tolerates_absent_and_null_citations():
    from experiment.schemas import parse_response

    # Llama-style: supporting_chunks omits 'property' and 'intermediate_node' entirely.
    absent = (
        '{"class":"lis:PhysicalObject","property":"lis:hasQuality",'
        '"intermediate_node":false,"supporting_chunks":{"class":"lis:PhysicalObject"},'
        '"reasoning":"x"}'
    )
    pred = parse_response("slot_filling", absent)
    assert pred.supporting_chunks.cls == "lis:PhysicalObject"
    assert pred.supporting_chunks.prop is None
    assert pred.supporting_chunks.intermediate_node is None

    # Explicit nulls still parse (unchanged behaviour).
    nulls = (
        '{"class":"lis:PhysicalObject","property":"lis:hasQuality",'
        '"intermediate_node":false,'
        '"supporting_chunks":{"class":null,"property":null,"intermediate_node":null},'
        '"reasoning":"x"}'
    )
    pred2 = parse_response("slot_filling", nulls)
    assert pred2.supporting_chunks.cls is None


@needs_prompt_text
def test_reasoning_type_and_query_source_written_on_rescore():
    _raw, _tasks, scored = _load_pilot()
    assert all(r.get("reasoning_type") for r in scored)
    assert all(r.get("query_source") for r in scored)
    t02 = next(r for r in scored if r["task_id"] == "T02")
    assert t02["reasoning_type"] == "modelling_pattern" and t02["query_source"] == "paraphrase"


# ---------------------------------------------------------------------------
# WI2 (model expansion spec) - no-context floor
# ---------------------------------------------------------------------------
def test_floor_conditions_consult_no_corpus_and_are_format_independent():
    from experiment.config import FLOOR_CONDITIONS, FLOOR_FORMAT_SENTINEL, is_floor_condition
    from experiment.postretrieval import _context_chunks

    tasks = load_tasks()
    task = tasks[0]
    for condition in FLOOR_CONDITIONS:
        assert is_floor_condition(condition)
        chunks, meta = _context_chunks(task, FLOOR_FORMAT_SENTINEL, condition, 5)
        # No chunks and no padding provenance: nothing was read from any corpus.
        assert chunks == [], f"{condition} produced context chunks"
        assert meta["n_pad_chunks"] == 0 and meta["pad_strategy"] is None


def test_floor_prompts_differ_only_in_the_context_scaffolding():
    from experiment.postretrieval import build_user_content

    tasks = load_tasks()
    slot = next(t for t in tasks if t.task_type == "slot_filling")
    no_ctx = build_user_content(slot, "", "no_context")
    empty_ctx = build_user_content(slot, "", "empty_context")

    # no_context never mentions a corpus; empty_context keeps the header.
    assert "Ontology content:" not in no_ctx
    assert empty_ctx.startswith("Ontology content:")
    # Both carry the identical task input, so the only difference is scaffolding.
    task_input = f"Scenario: {slot.scenario.strip()}"
    assert no_ctx == task_input
    assert empty_ctx.endswith(task_input)


def test_floor_scoped_schema_does_not_change_the_strict_schema():
    """The citation relaxation must be floor-only: existing arms rescore identically."""
    from experiment.schemas import ParseError, parse_response

    payload = '{"class":"lis:X","property":"lis:y","intermediate_node":false}'
    # Strict (existing) path still rejects a missing citation block.
    try:
        parse_response("slot_filling", payload)
    except ParseError:
        pass
    else:
        raise AssertionError("strict schema accepted a missing supporting_chunks")
    # Floor path accepts it, with empty (not fabricated) citations.
    pred = parse_response("slot_filling", payload, allow_missing_citations=True)
    assert pred.supporting_chunks.cls is None
    assert pred.supporting_chunks.prop is None


def test_floor_citation_hallucination_is_detected():
    from experiment.postretrieval import _cited_chunk_ids
    from experiment.schemas import parse_response

    declined = parse_response(
        "slot_filling",
        '{"class":"lis:X","property":"lis:y","intermediate_node":false}',
        allow_missing_citations=True,
    )
    assert _cited_chunk_ids(declined) == []

    fabricated = parse_response(
        "slot_filling",
        '{"class":"lis:X","property":"lis:y","intermediate_node":false,'
        '"supporting_chunks":{"class":"lis:Invented","property":null,'
        '"intermediate_node":null}}',
        allow_missing_citations=True,
    )
    assert _cited_chunk_ids(fabricated) == ["lis:Invented"]


def test_floor_summary_reports_accuracy_against_majority_baseline():
    from experiment.floor import build_floor_summary

    # Two gold 'supported', one gold 'contradicted' => majority baseline 2/3.
    rows = [
        {
            "model": "m", "condition": "no_context", "task_id": "T01",
            "task_type": "verification", "parse_ok": True,
            "grade_gold_label": "supported", "pred_label": "supported", "grade_correct": 1,
        },
        {
            "model": "m", "condition": "no_context", "task_id": "T02",
            "task_type": "verification", "parse_ok": True,
            "grade_gold_label": "supported", "pred_label": "supported", "grade_correct": 1,
        },
        {
            "model": "m", "condition": "no_context", "task_id": "T03",
            "task_type": "verification", "parse_ok": True,
            "grade_gold_label": "contradicted", "pred_label": "supported", "grade_correct": 0,
        },
    ]
    summary = build_floor_summary(rows)
    assert len(summary) == 1
    row = summary[0]
    assert abs(row["verification_accuracy"] - 2 / 3) < 1e-9
    assert abs(row["majority_class_baseline"] - 2 / 3) < 1e-9
    # An always-'supported' responder must NOT read as beating the baseline.
    assert row["beats_majority_baseline"] is False
    assert abs(row["accuracy_minus_baseline"]) < 1e-9
    assert row["modal_pred_label"] == "supported" and row["modal_pred_frac"] == 1.0
    # Retrieval metrics are undefined without a corpus: null, never zero.
    for metric in ("recall_at_k", "mrr", "ndcg_at_k", "coverage_frac"):
        assert row[metric] is None, f"{metric} should be null on floor rows"


# ---------------------------------------------------------------------------
# Runner (no pytest required)
# ---------------------------------------------------------------------------
def _all_tests():
    return [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]


def _skip_reason(test):
    """The reason of a satisfied ``skipif`` mark, so the plain runner honours them too."""
    for mark in getattr(test, "pytestmark", []):
        if mark.name == "skipif" and mark.args and mark.args[0]:
            return mark.kwargs.get("reason", "skipped")
    return None


def main() -> int:
    failures = skipped = 0
    for test in _all_tests():
        reason = _skip_reason(test)
        if reason:
            skipped += 1
            print(f"SKIP {test.__name__}: {reason}")
            continue
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    ran = len(_all_tests()) - skipped
    print(f"\n{ran - failures}/{ran} passed, {skipped} skipped")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
