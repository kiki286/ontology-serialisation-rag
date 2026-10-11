"""Pydantic models for benchmark tasks and structured LLM responses.

Kept dependency-light (pydantic + PyYAML only) so it can be imported without
pulling in FAISS/OpenAI. Cross-format entity resolution is validated separately
in ``validate_gold_chunks_resolve`` once the corpus entity maps are available.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from experiment.config import FORMATS, TASKS_PATH

Label = Literal["supported", "contradicted", "undetermined"]

# One reasoning_type per task, describing the ANSWER (not query difficulty). See
# CHANGELOG 2026-07-23 (WI3): kept orthogonal to query_source so the two can be
# crossed in analysis.
ReasoningType = Literal[
    "direct_assertion",  # answer is one asserted axiom in one chunk
    "structural",  # requires composing axioms (subclass chain, inverse, domain/range)
    "modelling_pattern",  # requires selecting the ontology's representational convention
    "definitional",  # requires reading a definition/equivalence axiom to identify the entity
]

# How the query is worded. A factual field, NOT a difficulty judgement, so it does
# not violate the one-reasoning_type-per-task rule (WI3).
QuerySource = Literal["label", "definition", "example", "paraphrase"]
AnnotationProseScreen = Literal["passed", "failed"]
ContradictedProseDirection = Literal["toward", "away", "neutral", "states_axiom"]

# What relationship the recorded ``licensing_axiom`` bears to the canonical graph.
# ``hypothetical`` marks the axiom IDO *would* need to assert for an undetermined
# claim to hold; it is NOT in the graph, and every branch that treats a licensing
# axiom as true must skip it (see recoverability.assess_draft_recoverability and
# scripts.verify_undetermined_items). Branch on this field explicitly, never on a
# ``licensing_axiom is None`` test, so a missing field can never be silently read
# as hypothetical.
LicensingAxiomStatus = Literal["asserted", "entailed_chain", "hypothetical"]

LicensingAxiom = tuple[str, str, str]
LicensingChain = list[LicensingAxiom]


class LicensingAxiomError(ValueError):
    """Raised when a verification licensing axiom is malformed."""


class ParseError(ValueError):
    """Raised when a model response cannot be parsed/validated."""


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------
class SupportingChunks(BaseModel):
    """Which context chunk (entity_id) supports each slot-filling decision.

    All three citation fields tolerate BOTH a null value AND an absent key. Local
    models (Llama 3.1 8B) do both: some emit ``"property": null``, others omit the key
    entirely. In Pydantic v2 ``str | None`` still makes a field *required* — it permits
    the value None but not absence, so a missing key raised "Field required
    [type=missing]" and crashed the whole response at parse time (observed on 6 Llama
    T02/omn rows, trial-5). The ``= None`` DEFAULT is what actually permits absence;
    the earlier "str -> Optional[str]" change alone did not. Either way an
    unstated/null citation grades as an uncited (wrong) slot.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    cls: str | None = Field(default=None, alias="class")
    prop: str | None = Field(default=None, alias="property")
    intermediate_node: str | None = None


class ClassProseCovariate(BaseModel):
    """Quoted class annotation evidence recorded during slot-filling authoring."""

    stated: bool
    source_chunk: str
    fragment: str | None = None


# ---------------------------------------------------------------------------
# Benchmark task
# ---------------------------------------------------------------------------
class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_type: Literal["verification", "slot_filling"]
    query: str
    # WI3: every task records its answer's reasoning_type and its query wording.
    # Required on all tasks so the taxonomy is complete and crossable with task_type.
    reasoning_type: ReasoningType
    query_source: QuerySource
    mechanism: str
    gold_chunks: list[str]
    gold_chunks_by_format: dict[str, list[str]] | None = None
    retrieval_gold_chunks: list[str] | None = None
    retrieval_gold_chunks_by_format: dict[str, list[str]] | None = None
    notes: str | None = None
    source_candidate_id: str | None = None
    sub_kind: str | None = None
    shared_parent: str | None = None
    adversarial: bool | None = None
    authoring_source: str | None = None

    # verification
    statement: str | None = None
    gold_label: Label | None = None
    # Manchester axioms used by the ROBOT two-sided non-entailment gate. They are
    # required for undetermined verification items and intentionally separate from
    # the natural-language statement shown to the model.
    axiom: str | None = None
    negated_axiom: str | None = None
    licensing_axiom: LicensingAxiom | LicensingChain | None = None
    # Required (authoring gate) on every verification item; its value is derivable
    # from the item's own content, so the stored value is cross-checked rather than
    # trusted. ``hypothetical`` is required at LOAD time on every undetermined item
    # so an undetermined claim can never load without its axiom being marked as not
    # asserted. Kept nullable in the base model only so the frozen five-item pilot
    # (which predates the field) still loads; the pilot never reaches the authoring gate.
    licensing_axiom_status: LicensingAxiomStatus | None = None
    recoverability_profile: dict[str, bool] | None = None
    # Required for undetermined verification items. ``passed`` means the
    # naturalLanguageDefinition/usageNote prose on the gold chunks does not
    # settle either side of the claim.
    annotation_prose_screen: AnnotationProseScreen | ContradictedProseDirection | None = None

    # slot_filling
    scenario: str | None = None
    gold_class: str | None = None
    gold_property: str | None = None
    gold_intermediate_node: bool | None = None
    gold_supporting_chunks: SupportingChunks | None = None
    # WI4: per-answer-field map of the gold chunk id(s) that license/cover each field.
    # Keys are the slot-answer concepts: class, property, intermediate_node, and the
    # citation fields support_class, support_property, support_intermediate. An empty
    # list means the field requires no chunk (excluded from the denominator per WI2
    # and N/A for coverage per WI5). Values are chunk identifiers, not free text.
    field_gold_chunks: dict[str, list[str]] | None = None
    # Authoring-only recoverability fields for Batch 4. They are intentionally
    # separate from grading and optional so existing benchmark items remain stable.
    class_domain_recoverable: dict[str, bool] | None = None
    class_prose_covariate: ClassProseCovariate | None = None
    class_domain_axiom: LicensingAxiom | None = None
    property_licensing_axioms: list[LicensingAxiom] | None = None
    intermediate_node_licensing_axioms: list[LicensingAxiom] | None = None
    property_recoverability_profile: dict[str, bool] | None = None
    intermediate_node_recoverability_profile: dict[str, bool] | None = None
    # DEPRECATED (WI4): superseded by field_gold_chunks. Retained as a read-only alias
    # for RQ1's primary_answer_rank (retrieval.py); the harness no longer writes it.
    primary_answer_chunk: str | None = None

    @model_validator(mode="after")
    def _check_required_for_type(self) -> "Task":
        if not self.mechanism.strip():
            raise ValueError(f"task {self.task_id} has a blank mechanism")
        if self.task_type == "verification":
            missing = [f for f in ("statement", "gold_label") if getattr(self, f) is None]
            if self.gold_label == "undetermined":
                missing.extend(
                    f for f in ("axiom", "negated_axiom") if getattr(self, f) is None
                )
                if self.annotation_prose_screen is None:
                    missing.append("annotation_prose_screen")
                if self.licensing_axiom is None:
                    missing.append("licensing_axiom")
                # Load-time containment: an undetermined item cannot load unless its
                # axiom is explicitly marked hypothetical, so no downstream branch can
                # ever mistake it for an asserted relation.
                if self.licensing_axiom_status != "hypothetical":
                    missing.append("licensing_axiom_status[hypothetical]")
            elif self.licensing_axiom is None:
                missing.append("licensing_axiom")
            if self.gold_label == "contradicted" and self.annotation_prose_screen not in {
                "toward",
                "away",
                "neutral",
                "states_axiom",
            }:
                missing.append("annotation_prose_screen[toward|away|neutral|states_axiom]")
            if self.recoverability_profile is not None and set(self.recoverability_profile) != set(
                FORMATS
            ):
                missing.append("recoverability_profile[all seven formats]")
        else:  # slot_filling
            missing = [
                f
                for f in (
                    "scenario",
                    "gold_class",
                    "gold_property",
                    "gold_intermediate_node",
                    "gold_supporting_chunks",
                    "field_gold_chunks",
                )
                if getattr(self, f) is None
            ]
        if missing:
            raise ValueError(
                f"task {self.task_id} ({self.task_type}) missing required fields: {missing}"
            )
        if self.licensing_axiom is not None:
            if self.is_licensing_chain:
                links = self.licensing_links
                if any(len(link) != 3 for link in links):
                    raise LicensingAxiomError(
                        f"task {self.task_id}: every licensing_axiom chain link must contain exactly 3 values"
                    )
                if any(left[2] != right[0] for left, right in zip(links, links[1:])):
                    raise LicensingAxiomError(
                        f"task {self.task_id}: licensing_axiom chain links must be ordered and connected"
                    )
                missing_gold = sorted(
                    {entity for link in links for entity in (link[0], link[2])}
                    - set(self.gold_chunks)
                )
                if missing_gold:
                    raise LicensingAxiomError(
                        f"task {self.task_id}: licensing_axiom chain entities missing from gold_chunks: "
                        f"{missing_gold}"
                    )
            elif len(self.licensing_axiom) != 3:
                raise LicensingAxiomError(
                    f"task {self.task_id}: licensing_axiom must contain exactly 3 values"
                )
        if self.task_type == "verification" and self.licensing_axiom_status is not None:
            derived = self.derived_licensing_axiom_status
            if derived is not None and self.licensing_axiom_status != derived:
                raise LicensingAxiomError(
                    f"task {self.task_id}: stored licensing_axiom_status "
                    f"{self.licensing_axiom_status!r} disagrees with the status its content "
                    f"implies ({derived!r}); a stored licensing_axiom is wrong"
                )
            if self.licensing_axiom_status == "hypothetical":
                # 2.4: every class named in the hypothetical relation must be in the
                # gold set, since they are what a reader needs to see that nothing
                # settles the claim. (Chains already enforce this above.)
                hypothetical_gold = sorted(
                    {entity for link in self.licensing_links for entity in (link[0], link[2])}
                    - set(self.gold_chunks)
                )
                if hypothetical_gold:
                    raise LicensingAxiomError(
                        f"task {self.task_id}: hypothetical licensing_axiom entities missing "
                        f"from gold_chunks: {hypothetical_gold}"
                    )
        return self

    @property
    def derived_licensing_axiom_status(self) -> str | None:
        """The status implied by the item's own content, not its stored field.

        Backfill and load-time validation derive from this so the stored
        ``licensing_axiom_status`` is a checked value rather than an assumed one: an
        undetermined item's axiom is ``hypothetical``; a determinate item's axiom is
        ``entailed_chain`` when it is a multi-link chain and ``asserted`` when it is a
        single directly-serialized triple. Returns ``None`` when no status is derivable
        (non-verification item, or verification item with no ``licensing_axiom``).
        """
        if self.task_type != "verification" or self.licensing_axiom is None:
            return None
        if self.gold_label == "undetermined":
            return "hypothetical"
        return "entailed_chain" if self.is_licensing_chain else "asserted"

    @property
    def is_licensing_chain(self) -> bool:
        return bool(self.licensing_axiom and isinstance(self.licensing_axiom[0], tuple))

    @property
    def licensing_links(self) -> list[LicensingAxiom]:
        if self.licensing_axiom is None:
            return []
        if self.is_licensing_chain:
            return list(self.licensing_axiom)
        return [self.licensing_axiom]

    def gold_chunks_for(self, corpus_format: str) -> list[str]:
        """Oracle/context entity_ids, honouring a per-format override if present."""
        if self.gold_chunks_by_format and corpus_format in self.gold_chunks_by_format:
            return self.gold_chunks_by_format[corpus_format]
        return self.gold_chunks

    def retrieval_gold_chunks_for(self, corpus_format: str) -> list[str]:
        """Retrieval-scoring entity_ids, falling back to oracle chunks."""
        if (
            self.retrieval_gold_chunks_by_format
            and corpus_format in self.retrieval_gold_chunks_by_format
        ):
            return self.retrieval_gold_chunks_by_format[corpus_format]
        if self.retrieval_gold_chunks is not None:
            return self.retrieval_gold_chunks
        return self.gold_chunks_for(corpus_format)

    def field_gold_chunks_for(self, field_key: str) -> list[str]:
        """Licensing chunk ids for a slot-answer field key (empty list if unset).

        ``field_key`` is a slot-answer concept: ``class``, ``property``,
        ``intermediate_node``, ``support_class``, ``support_property`` or
        ``support_intermediate``. An empty list means the field requires no chunk.
        """
        if not self.field_gold_chunks:
            return []
        return list(self.field_gold_chunks.get(field_key, []))


# ---------------------------------------------------------------------------
# Structured LLM responses
# ---------------------------------------------------------------------------
class VerificationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: Label
    reasoning: str = ""


class SlotFillingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    cls: str = Field(alias="class")
    prop: str = Field(alias="property")
    intermediate_node: bool
    supporting_chunks: SupportingChunks
    reasoning: str = ""


class FloorSlotFillingResponse(SlotFillingResponse):
    """Slot-filling response for the no-corpus FLOOR conditions only (WI2).

    Identical to ``SlotFillingResponse`` except that ``supporting_chunks`` may be
    absent entirely. Under a floor condition there are no chunks, so declining to
    cite one is the CORRECT behaviour and must parse cleanly; treating it as a
    malformed response would conflate "correctly declined to cite" with "emitted
    garbage" and silently zero the decision fields too.

    Deliberately scoped to the floor rather than relaxing ``SlotFillingResponse``
    globally: 12 existing Llama rows in the pilot fail on a top-level missing
    ``supporting_chunks``, so a global relaxation would retroactively change how
    already-reported arms grade on rescore. Floor-scoping keeps every existing arm
    bit-identical. See CHANGELOG 2026-08-04.
    """

    supporting_chunks: SupportingChunks = SupportingChunks()


RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    "verification": VerificationResponse,
    "slot_filling": SlotFillingResponse,
}

# Used only when ``allow_missing_citations=True`` (floor conditions).
FLOOR_RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    "verification": VerificationResponse,
    "slot_filling": FloorSlotFillingResponse,
}


def parse_response(
    task_type: str, raw: str, *, allow_missing_citations: bool = False
) -> BaseModel:
    """Parse a raw model string into the typed response model. Mechanical only.

    ``allow_missing_citations`` selects the floor-scoped schema, in which the
    chunk-citation block is optional (expected-absent when there is no context).
    """
    registry = FLOOR_RESPONSE_MODELS if allow_missing_citations else RESPONSE_MODELS
    model_cls = registry.get(task_type)
    if model_cls is None:
        raise ParseError(f"unknown task_type {task_type!r}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(f"response is not valid JSON: {exc}") from exc
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise ParseError(f"response failed {task_type} schema: {exc}") from exc


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------
def load_tasks(
    path: Path = TASKS_PATH, *, enforce_authoring_constraints: bool = False
) -> list[Task]:
    """Load and validate tasks.yaml. Fails fast with a clear message."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a YAML list of tasks")

    tasks: list[Task] = []
    for i, item in enumerate(raw):
        try:
            tasks.append(Task.model_validate(item))
        except ValidationError as exc:
            raise ValueError(f"task #{i} in {path.name} is invalid:\n{exc}") from exc

    ids = [t.task_id for t in tasks]
    dupes = {tid for tid in ids if ids.count(tid) > 1}
    if dupes:
        raise ValueError(f"duplicate task_id(s) in {path.name}: {sorted(dupes)}")
    if enforce_authoring_constraints:
        validate_authoring_constraints(tasks)
    return tasks


def validate_authoring_constraints(
    tasks: list[Task],
    *,
    expected_n: int = 60,
    verify_profiles: bool = True,
) -> None:
    """Enforce the fixed 60-item authoring design at load time.

    ``verify_profiles=False`` is reserved for fast unit fixtures. The authoring
    entry point leaves it enabled so stored profiles are compared with the live
    seven-format gold-chunk unions before any generation call.
    """
    from collections import Counter

    errors: list[str] = []
    if len(tasks) != expected_n:
        errors.append(f"expected {expected_n} tasks, found {len(tasks)}")

    type_counts = Counter(task.task_type for task in tasks)
    for task_type, expected in {"verification": 30, "slot_filling": 30}.items():
        if type_counts[task_type] != expected:
            errors.append(
                f"task_type={task_type}: expected {expected}, found {type_counts[task_type]}"
            )

    label_counts = Counter(
        task.gold_label for task in tasks if task.task_type == "verification"
    )
    for label in ("supported", "contradicted", "undetermined"):
        if label_counts[label] != 10:
            errors.append(
                f"verification gold_label={label}: expected 10, found {label_counts[label]}"
            )

    for reasoning_type in (
        "direct_assertion",
        "structural",
        "modelling_pattern",
        "definitional",
    ):
        for task_type in ("verification", "slot_filling"):
            count = sum(
                task.reasoning_type == reasoning_type and task.task_type == task_type
                for task in tasks
            )
            if count < 3:
                warnings.warn(
                    "authoring allocation warning: reasoning_type="
                    f"{reasoning_type}, task_type={task_type} has {count} item(s), fewer than "
                    "three. The fixed 7-8 per-cell rule was relaxed because the achievable "
                    "distribution is determined by what the ontology supplies; distributions "
                    "are reported rather than targeted.",
                    stacklevel=2,
                )

    for task in tasks:
        if task.task_type != "verification":
            continue
        # Required on every verification item (2.1). Enforced here rather than in the
        # base model so the frozen pilot, which never reaches this gate, still loads.
        if task.licensing_axiom_status is None:
            errors.append(f"{task.task_id}: missing licensing_axiom_status")
        # 2.3: branch on the status, not on the gold label or a null test, so the skip
        # stays correct if a hypothetical axiom ever appears outside the undetermined class.
        if task.licensing_axiom_status == "hypothetical":
            if task.recoverability_profile is not None:
                errors.append(
                    f"{task.task_id}: hypothetical recoverability must be explicitly skipped"
                )
            continue
        if task.recoverability_profile is None:
            errors.append(f"{task.task_id}: missing stored recoverability_profile")
            continue
        if verify_profiles:
            from experiment.recoverability import assess_draft_recoverability

            assessment = assess_draft_recoverability(task)
            computed = assessment["profile"]
            if assessment["gate_verdict"] != "pass":
                errors.append(
                    f"{task.task_id}: recoverability gate {assessment['gate_verdict']}"
                )
            if task.recoverability_profile != computed:
                errors.append(
                    f"{task.task_id}: stored recoverability_profile does not match "
                    f"computed profile {computed}"
                )
    if errors:
        raise ValueError("authoring constraints failed:\n  " + "\n  ".join(errors))


def validate_gold_chunks_resolve(
    tasks: list[Task],
    entity_ids_by_format: dict[str, set[str]],
    retrieval_entity_ids_by_format: dict[str, set[str]] | None = None,
) -> None:
    """Assert every gold_chunks entity resolves in every format.

    ``entity_ids_by_format`` maps a format name to the set of entity_ids its
    chunker emits. Raises ValueError listing all unresolved (task, format,
    entity) triples so the whole dataset can be fixed in one pass.
    """
    errors: list[str] = []
    retrieval_entity_ids_by_format = retrieval_entity_ids_by_format or entity_ids_by_format
    for task in tasks:
        for fmt, available in entity_ids_by_format.items():
            gold_entity_ids = task.gold_chunks_for(fmt)
            retrieval_gold_entity_ids = task.retrieval_gold_chunks_for(fmt)
            guarded_gold_ids = list(gold_entity_ids) + list(retrieval_gold_entity_ids)
            if task.primary_answer_chunk:
                guarded_gold_ids.append(task.primary_answer_chunk)
            # WI4: field_gold_chunks values are chunk identifiers and must resolve too.
            if task.field_gold_chunks:
                for ids in task.field_gold_chunks.values():
                    guarded_gold_ids.extend(ids)
            for entity_id in guarded_gold_ids:
                if entity_id not in available:
                    errors.append(f"  {task.task_id}: '{entity_id}' not found in {fmt}")
            retrieval_available = retrieval_entity_ids_by_format.get(fmt, available)
            for entity_id in guarded_gold_ids:
                if entity_id not in retrieval_available:
                    errors.append(
                        f"  {task.task_id}: gold chunk '{entity_id}' is excluded from the "
                        f"{fmt} retrieval index"
                    )
    if errors:
        raise ValueError(
            "gold_chunks entities do not resolve in all formats:\n" + "\n".join(errors)
        )
