"""Mechanical grading for the two post-retrieval task types.

Per-item graders return flat dicts of booleans/scores; aggregate functions turn
lists of those into the metrics reported in the dissertation (accuracy,
precision/recall/F1, confusion matrix; slot exact-match and partial credit).
"""

from __future__ import annotations

from experiment.schemas import SlotFillingResponse, Task, VerificationResponse

VERIFICATION_LABELS = ["supported", "contradicted", "undetermined"]
DETERMINATE_VERIFICATION_LABELS = {"supported", "contradicted"}

# The slot-filling fields: three decisions + their three supporting-chunk citations.
# Each maps to the field_gold_chunks key that licenses it (WI4). Decision fields are
# always graded; support (citation) fields are graded only when their gold citation
# exists (WI2). Insertion order defines the stable CSV column order.
DECISION_FIELDS = {
    "class_correct": "class",
    "property_correct": "property",
    "intermediate_correct": "intermediate_node",
}
SUPPORT_FIELDS = {
    "support_class_correct": "support_class",
    "support_property_correct": "support_property",
    "support_intermediate_correct": "support_intermediate",
}
FIELD_GOLD_CHUNK_KEY = {**DECISION_FIELDS, **SUPPORT_FIELDS}
SLOT_FIELDS = list(FIELD_GOLD_CHUNK_KEY)  # all six, in stable order


def _norm(value: object) -> str:
    """Light normalisation for entity-id comparison (whitespace, <> brackets)."""
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1]
    return s


def _present(value: object) -> bool:
    """True when a gold citation is a real chunk id (not None / blank)."""
    return _norm(value) != ""


def graded_slot_fields(task: Task) -> list[str]:
    """The slot fields that count toward the denominator, per the item's GOLD (WI2).

    Decision fields (class/property/intermediate_node) are always graded: a correct
    answer is always possible from gold. A support (citation) field is graded only
    when its field_gold_chunks licensing set is non-empty, i.e. gold actually names a
    chunk to cite. Excluded fields (empty licensing set) are unsatisfiable and become
    N/A, never a scored zero. The denominator is thus a function of gold alone, never
    of the model's prediction.
    """
    graded = list(DECISION_FIELDS)
    for field, key in SUPPORT_FIELDS.items():
        if task.field_gold_chunks_for(key):
            graded.append(field)
    return [f for f in SLOT_FIELDS if f in set(graded)]


def _assemble_slot_grade(task: Task, raw: dict[str, int]) -> dict:
    """Apply the gold-driven denominator (WI2) to the six raw per-field booleans.

    Graded fields keep their 0/1 value; excluded fields become ``None`` (N/A). The
    composites (``exact_match``, ``partial_credit``) and ``n_fields`` are computed
    over the graded fields only.
    """
    graded = set(graded_slot_fields(task))
    grade: dict = {f: (raw[f] if f in graded else None) for f in SLOT_FIELDS}
    n = len(graded)
    correct = sum(raw[f] for f in SLOT_FIELDS if f in graded)
    grade["n_fields"] = n
    grade["exact_match"] = int(correct == n) if n else 0
    grade["partial_credit"] = (correct / n) if n else 0.0
    return grade


# ---------------------------------------------------------------------------
# Per-item grading
# ---------------------------------------------------------------------------
def grade_verification(task: Task, pred: VerificationResponse) -> dict:
    answered = int(pred.label in DETERMINATE_VERIFICATION_LABELS)
    return {
        "gold_label": task.gold_label,
        "pred_label": pred.label,
        "correct": int(task.gold_label == pred.label),
        "answered": answered,
        "selective_correct": int(answered and task.gold_label == pred.label),
    }


def _raw_slot_booleans(task: Task, pred: SlotFillingResponse) -> dict[str, int]:
    """The six raw per-field booleans (strict exact-match, pre-denominator).

    Every slot is strict exact-match against the single canonical gold answer. A
    less-specific but syntactically valid class scores 0, exactly as the property
    slot already treats a less-specific superproperty: for a T-Box ontology a
    less-specific typing is a semantic error, not partial success. This comparison
    logic is unchanged from the pre-WI2 grader (the WI1 fidelity gate depends on it).
    """
    gold = task.gold_supporting_chunks
    return {
        "class_correct": int(_norm(task.gold_class) == _norm(pred.cls)),
        "property_correct": int(_norm(task.gold_property) == _norm(pred.prop)),
        "intermediate_correct": int(bool(task.gold_intermediate_node) == bool(pred.intermediate_node)),
        "support_class_correct": int(_norm(gold.cls) == _norm(pred.supporting_chunks.cls)),
        "support_property_correct": int(_norm(gold.prop) == _norm(pred.supporting_chunks.prop)),
        "support_intermediate_correct": int(
            _norm(gold.intermediate_node) == _norm(pred.supporting_chunks.intermediate_node)
        ),
    }


def grade_slot_filling(task: Task, pred: SlotFillingResponse) -> dict:
    return _assemble_slot_grade(task, _raw_slot_booleans(task, pred))


def grade_slot_filling_missing(task: Task) -> dict:
    """Grade an unparseable/missing slot response: every graded field scores 0, every
    excluded field is N/A, and the denominator (``n_fields``) still reflects gold."""
    return _assemble_slot_grade(task, {f: 0 for f in SLOT_FIELDS})


# ---------------------------------------------------------------------------
# Validation (WI2): fail loudly if any item declares a graded field that no answer
# could satisfy given its gold, or if the field_gold_chunks licensing disagrees with
# the gold citations that drive the denominator.
# ---------------------------------------------------------------------------
def validate_slot_gradeability(tasks: list[Task]) -> None:
    errors: list[str] = []
    for task in tasks:
        if task.task_type != "slot_filling":
            continue
        gold = task.gold_supporting_chunks
        gold_citation = {
            "support_class": None if gold is None else gold.cls,
            "support_property": None if gold is None else gold.prop,
            "support_intermediate": None if gold is None else gold.intermediate_node,
        }
        graded = set(graded_slot_fields(task))
        for field, key in SUPPORT_FIELDS.items():
            licensed = bool(task.field_gold_chunks_for(key))
            has_gold = _present(gold_citation[key])
            # A graded support field with no gold citation is unsatisfiable.
            if field in graded and not has_gold:
                errors.append(
                    f"  {task.task_id}: graded field '{field}' is unsatisfiable — "
                    f"field_gold_chunks['{key}'] is non-empty but gold names no citation"
                )
            # Licensing set and gold citation must agree, so the denominator is
            # unambiguously gold-driven.
            if licensed != has_gold:
                errors.append(
                    f"  {task.task_id}: field_gold_chunks['{key}'] is "
                    f"{'non-empty' if licensed else 'empty'} but the gold citation is "
                    f"{'present' if has_gold else 'absent'} (they must agree)"
                )
    if errors:
        raise ValueError("slot gradeability validation failed:\n" + "\n".join(errors))


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}


def aggregate_verification(items: list[dict]) -> dict:
    n = len(items)
    if n == 0:
        return {"n": 0}
    # Parse failures count as incorrect in accuracy but are excluded from the
    # confusion matrix / PRF (their pred_label is not a valid label).
    accuracy = sum(i["correct"] for i in items) / n
    parse_errors = sum(1 for i in items if i["pred_label"] not in VERIFICATION_LABELS)

    confusion = {g: {p: 0 for p in VERIFICATION_LABELS} for g in VERIFICATION_LABELS}
    for i in items:
        if i["pred_label"] in VERIFICATION_LABELS and i["gold_label"] in VERIFICATION_LABELS:
            confusion[i["gold_label"]][i["pred_label"]] += 1

    per_class = {}
    for label in VERIFICATION_LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[g][label] for g in VERIFICATION_LABELS if g != label)
        fn = sum(confusion[label][p] for p in VERIFICATION_LABELS if p != label)
        per_class[label] = _prf(tp, fp, fn)

    macro_f1 = sum(per_class[l]["f1"] for l in VERIFICATION_LABELS) / len(VERIFICATION_LABELS)
    answered = [
        i for i in items
        if i.get("pred_label") in DETERMINATE_VERIFICATION_LABELS
    ]
    selective_accuracy = (
        sum(i.get("gold_label") == i.get("pred_label") for i in answered) / len(answered)
        if answered else 0.0
    )
    return {
        "n": n,
        "accuracy": accuracy,
        "n_answered": len(answered),
        "coverage": len(answered) / n,
        "accuracy_on_answered": selective_accuracy,
        "parse_errors": parse_errors,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion": confusion,
    }


def aggregate_slot_filling(items: list[dict]) -> dict:
    n = len(items)
    if n == 0:
        return {"n": 0}
    # Field accuracy skips N/A (excluded) fields: each field is averaged only over the
    # items where it was graded, so an excluded field never counts as a zero (WI2).
    field_accuracy: dict[str, float] = {}
    for f in SLOT_FIELDS:
        graded = [i[f] for i in items if i.get(f) is not None]
        if graded:
            field_accuracy[f] = sum(graded) / len(graded)
    return {
        "n": n,
        "exact_match_rate": sum(i["exact_match"] for i in items) / n,
        "mean_partial_credit": sum(i["partial_credit"] for i in items) / n,
        "mean_n_fields": sum(i["n_fields"] for i in items) / n,
        "field_accuracy": field_accuracy,
    }
