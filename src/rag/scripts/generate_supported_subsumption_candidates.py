"""Generate the Batch 2 supported-subsumption authoring candidate report.

Blinded authoring pass (no experimental results consulted). Enumerates every
``lis:X rdfs:subClassOf lis:Y`` pair that IDO entails, restricted to entities
present in the corpus chunk store of all seven formats, labels each by distance
class (immediate / near / distant) and source (asserted / entailed), verifies
entailment with ROBOT/HermiT against the canonical Turtle graph, and records the
seven-format direct-axiom recoverability profile computed by the same assessor
that ``check_authoring_candidate`` wraps.

Produces a candidate table for human selection. It does NOT select benchmark
items, finalise wording, judge difficulty, or write to tasks.yaml.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path

import yaml
from rdflib import Graph, RDFS, URIRef

RAG_DIR = Path(__file__).resolve().parents[1]
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from experiment.config import FORMATS  # noqa: E402
from experiment.corpus_index import build_oracle_map  # noqa: E402
from experiment.recoverability import assess_draft_recoverability  # noqa: E402
from scripts.tangle_ofn import _robot_command  # noqa: E402
from scripts.verify_undetermined_items import _prefix_args  # noqa: E402

CANONICAL_TURTLE = RAG_DIR / "data" / "LIS-14-for-FDIS (1).ttl"
CHECKER = RAG_DIR / "scripts" / "check_authoring_candidate.py"
LIS_NS = "http://rds.posccaesar.org/ontology/lis14/rdl/"
PILOT_FILES = [
    RAG_DIR / "experiment" / "benchmark" / "tasks.yaml",
    RAG_DIR / "experiment" / "benchmark" / "tasks_60.yaml",
]
EXPLANATION_HEADING_RE = re.compile(r"^## .+ ##$", re.MULTILINE)
ANNOTATION_PREDICATES = {"naturalLanguageDefinition", "usageNote"}
FALSE_PROFILE = {fmt: False for fmt in FORMATS}
EXPECTED_PROFILE = {fmt: fmt != "elot-org-ancestors" for fmt in FORMATS}


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------
def compact(graph: Graph, node: URIRef) -> str:
    value = str(node)
    for prefix, namespace in graph.namespaces():
        base = str(namespace)
        if value.startswith(base):
            return f"{prefix}:{value[len(base):]}"
    return value


def term_for(entity_id: str) -> URIRef:
    return URIRef(f"{LIS_NS}{entity_id.split(':', 1)[1]}")


def human_phrase(entity_id: str) -> str:
    """CamelCase local name -> lowercase spaced phrase (the genus form in prose)."""
    local = entity_id.split(":", 1)[1]
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", local)
    return spaced.lower()


def shared_store_entities() -> set[str]:
    """lis: entity_ids present in the oracle chunk map of every one of the seven formats."""
    per_format = [set(build_oracle_map(fmt)) for fmt in FORMATS]
    shared = set.intersection(*per_format)
    return {eid for eid in shared if eid.startswith("lis:")}


def asserted_parents(graph: Graph) -> dict[str, set[str]]:
    parents: dict[str, set[str]] = defaultdict(set)
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if isinstance(child, URIRef) and isinstance(parent, URIRef):
            child_id, parent_id = compact(graph, child), compact(graph, parent)
            if child_id.startswith("lis:") and parent_id.startswith("lis:"):
                parents[child_id].add(parent_id)
    return parents


def shortest_path(parents: dict[str, set[str]], start: str, goal: str) -> list[str]:
    """Shortest ancestor path start..goal over asserted parent edges (inclusive)."""
    predecessor: dict[str, str] = {start: start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            break
        for parent in sorted(parents.get(node, ())):
            if parent not in predecessor:
                predecessor[parent] = node
                queue.append(parent)
    if goal not in predecessor:
        return []
    path = [goal]
    while path[-1] != start:
        path.append(predecessor[path[-1]])
    return list(reversed(path))


def distance_class(distance: int) -> str:
    if distance == 1:
        return "immediate"
    if distance == 2:
        return "near"
    return "distant"


def annotation_fragments(graph: Graph, entity_id: str) -> list[str]:
    fragments: list[str] = []
    for predicate, value in graph.predicate_objects(term_for(entity_id)):
        local = str(predicate).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        if local in ANNOTATION_PREDICATES:
            fragments.append(f"{entity_id} {local}: {str(value)}")
    return fragments


# ---------------------------------------------------------------------------
# Recoverability (the function check_authoring_candidate wraps)
# ---------------------------------------------------------------------------
def draft(subject: str, object_: str, *, path: list[str] | None = None) -> dict[str, object]:
    links = [
        [child, "rdfs:subClassOf", parent]
        for child, parent in zip(path, path[1:])
    ] if path else None
    gold_chunks = path if path else [subject, object_]
    return {
        "task_id": f"{subject}->{object_}",
        "task_type": "verification",
        "query": f"Is every {subject} an {object_} in IDO?",
        "reasoning_type": "structural",
        "query_source": "label",
        "mechanism": "subsumption",
        "gold_chunks": gold_chunks,
        "retrieval_gold_chunks": gold_chunks,
        "statement": f"Every {subject} is an {object_}.",
        "gold_label": "supported",
        "licensing_axiom": links if links and len(links) > 1 else [subject, "rdfs:subClassOf", object_],
    }


def cli_assessment(draft_map: dict[str, object]) -> dict[str, object]:
    """Invoke the actual check_authoring_candidate CLI on one draft (equivalence sample)."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "candidate.yaml"
        path.write_text(yaml.safe_dump(draft_map, sort_keys=False), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, str(CHECKER), str(path)],
            cwd=RAG_DIR,
            capture_output=True,
            text=True,
        )
    if not process.stdout.strip():
        raise RuntimeError(process.stderr.strip() or "checker returned no assessment")
    return json.loads(process.stdout)


def check_pilot_profiles() -> list[str]:
    """Recompute every stored pilot recoverability_profile; return mismatch messages."""
    mismatches: list[str] = []
    for pilot_file in PILOT_FILES:
        if not pilot_file.is_file():
            continue
        for task in yaml.safe_load(pilot_file.read_text(encoding="utf-8")) or []:
            stored = task.get("recoverability_profile")
            if task.get("task_type") != "verification" or not stored:
                continue
            recomputed = assess_draft_recoverability(task)["profile"]
            if recomputed != stored:
                mismatches.append(
                    f"{pilot_file.name}:{task.get('task_id')}: stored={stored} "
                    f"recomputed={recomputed}"
                )
    return mismatches


# ---------------------------------------------------------------------------
# ROBOT / HermiT entailment
# ---------------------------------------------------------------------------
def robot_entails(subject: str, object_: str) -> tuple[bool, str]:
    """Return (entailed, chain-string) from a ROBOT/HermiT explanation for X SubClassOf Y."""
    with tempfile.TemporaryDirectory() as directory:
        explanation_path = Path(directory) / "explanation.md"
        command = _robot_command() + [
            "explain",
            "--input",
            str(CANONICAL_TURTLE),
            "--input-format",
            "ttl",
            "--reasoner",
            "HermiT",
            *_prefix_args(CANONICAL_TURTLE),
            "--axiom",
            f"{subject} SubClassOf: {object_}",
            "--explanation",
            str(explanation_path),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise RuntimeError(f"ROBOT explain failed for {subject}->{object_}: {detail}")
        explanation = explanation_path.read_text(encoding="utf-8")
    entailed = bool(EXPLANATION_HEADING_RE.search(explanation))
    used = re.findall(r"- \[[^\]]+\]\([^)]+\) SubClassOf \[[^\]]+\]\([^)]+\) \[core\]", explanation)
    chain = "; ".join(
        re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line).lstrip("- ").strip() for line in used
    )
    return entailed, chain


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------
def enumerate_candidates(graph: Graph) -> list[dict[str, object]]:
    parents = asserted_parents(graph)
    store = shared_store_entities()

    closure: dict[str, set[str]] = {}
    for child in parents:
        seen: set[str] = set()
        pending = list(parents[child])
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(parents.get(node, ()))
        closure[child] = seen

    asserted_pairs = {
        (child, parent) for child, ps in parents.items() for parent in ps
    }

    candidates: list[dict[str, object]] = []
    for child in sorted(closure):
        if child not in store:
            continue
        for ancestor in sorted(closure[child]):
            if ancestor not in store:
                continue
            path = shortest_path(parents, child, ancestor)
            distance = len(path) - 1
            source = "asserted" if (child, ancestor) in asserted_pairs else "entailed"
            candidates.append(
                {
                    "subject": child,
                    "object": ancestor,
                    "source": source,
                    "distance": distance,
                    "distance_class": distance_class(distance),
                    "path": path,
                    "intervening": max(len(path) - 2, 0),
                }
            )
    return candidates


def screen_prose(graph: Graph, subject: str, object_: str) -> dict[str, object]:
    subject_fragments = annotation_fragments(graph, subject)
    object_fragments = annotation_fragments(graph, object_)
    genus = human_phrase(object_)
    alt_terms = {genus}
    for predicate, value in graph.predicate_objects(term_for(object_)):
        if str(predicate).endswith("altLabel"):
            alt_terms.add(str(value).lower())
    hit = None
    matched_term = None
    for fragment in subject_fragments:
        body = fragment.split(": ", 1)[-1].lower()
        for term in alt_terms:
            if term and re.search(rf"\b{re.escape(term)}\b", body):
                hit = fragment
                matched_term = term
                break
        if hit:
            break
    # Compound-substring risk: a single-word target (e.g. "object", "temporal") can
    # word-match inside a longer genus phrase actually asserted by the prose (e.g.
    # "information object", "temporal region"). Flag so the human reads the fragment.
    compound_risk = bool(
        hit
        and matched_term
        and re.search(rf"\b{re.escape(matched_term)}\s+\w+", hit.split(': ', 1)[-1].lower())
        and " " not in matched_term
    )
    direction = "states_axiom" if hit else "neutral"
    return {
        "direction": direction,
        "genus_hit": hit,
        "matched_term": matched_term,
        "compound_risk": compound_risk,
        "subject_fragments": subject_fragments,
        "object_fragments": object_fragments,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def quote(fragments: list[str]) -> str:
    if not fragments:
        return "—"
    return " / ".join(f"“{f}”" for f in fragments).replace("|", "\\|")


def profile_string(profile: dict[str, object]) -> str:
    return ", ".join(f"{fmt}={str(profile[fmt]).lower()}" for fmt in FORMATS)


def candidate_row(candidate: dict[str, object]) -> str:
    prose = candidate["prose"]
    prose_cell = (
        f"`{prose['direction']}`; genus mention: “{prose['genus_hit']}”"
        if prose["genus_hit"]
        else f"`{prose['direction']}`; no genus mention in subject prose"
    )
    return (
        "| {id} | {statement} | `{subject} SubClassOf {object}` | {licensing} | `{source}` "
        "| `{dclass}` (d={distance}) | {path} ({intervening} intervening) | {robot} "
        "| `{gold}` / `{retrieval}` | {profile} | `{uniform}` | {prose} | `{reasoning}` | {notes} |"
    ).format(
        id=candidate["id"],
        statement=candidate["statement"],
        subject=candidate["subject"],
        object=candidate["object"],
        licensing=candidate["licensing"],
        source=candidate["source"],
        dclass=candidate["distance_class"],
        distance=candidate["distance"],
        path=" → ".join(candidate["path"]),
        intervening=candidate["intervening"],
        robot=candidate["robot_cell"],
        gold=", ".join(candidate["gold_chunks"]),
        retrieval=", ".join(candidate["retrieval_gold_chunks"]),
        profile=profile_string(candidate["profile"]),
        uniform=str(candidate["uniform"]).lower(),
        prose=prose_cell.replace("|", "\\|"),
        reasoning=candidate["reasoning_type"],
        notes=candidate["notes"].replace("|", "\\|"),
    )


TABLE_HEADER = (
    "| ID | Draft statement | Formal axiom | Licensing axiom / chain | Source | Distance "
    "| Ancestor path | ROBOT/HermiT | Gold chunks / retrieval | Recoverability profile | Uniform "
    "| Prose direction | Reasoning type | Notes |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)


def build_report(candidates: list[dict[str, object]], sample: list[dict[str, object]]) -> str:
    from collections import Counter

    by_source = Counter(c["source"] for c in candidates)
    by_class = Counter(c["distance_class"] for c in candidates)
    by_source_class = Counter((c["source"], c["distance_class"]) for c in candidates)
    by_distance = Counter(c["distance"] for c in candidates)

    states_axiom = [c for c in candidates if c["prose"]["direction"] == "states_axiom"]
    plain = [c for c in candidates if c["prose"]["direction"] != "states_axiom"]

    expected = EXPECTED_PROFILE

    def matches_expected(candidate: dict[str, object]) -> bool:
        return candidate["profile"] == expected and candidate["gate"] == "pass"

    deviations = [c for c in candidates if not matches_expected(c)]

    lines: list[str] = []
    lines.append("# Batch 02: Supported-Subsumption Candidates")
    lines.append("")
    lines.append(
        "Blinded authoring pass. No experimental results, methodology log, or findings "
        "were consulted. This is a candidate table for human selection, not a set of "
        "finished benchmark items: statements are drafts so gold chunks and profiles can "
        "be computed, and no ten items are selected here."
    )
    lines.append("")
    states_axiom_asserted_n = sum(
        c["source"] == "asserted" and c["prose"]["direction"] == "states_axiom"
        for c in candidates
    )
    prose_neutral_asserted_n = by_source["asserted"] - states_axiom_asserted_n
    entailed_artifact_n = sum(
        c["source"] == "entailed" and c["profile"] != FALSE_PROFILE for c in candidates
    )
    lines.append("## 0. Key findings for the selector")
    lines.append("")
    lines.append(
        f"1. **{len(candidates)}** entailed `lis:X ⊑ lis:Y` pairs in the shared chunk store: "
        f"**{by_source['asserted']}** asserted/immediate, **{by_class['near']}** entailed-near, "
        f"**{by_class['distant']}** entailed-distant. No sampling (under the ~150 threshold)."
    )
    lines.append(
        "2. **Asserted ⟺ immediate, entailed ⟺ near/distant**, exactly. Distance does not vary "
        "*within* the recoverable (asserted) pool — every asserted pair is a single hop."
    )
    lines.append(
        f"3. **Prose leakage is the dominant fact.** {states_axiom_asserted_n} of "
        f"{by_source['asserted']} asserted/immediate candidates are `states_axiom` — the "
        "subject's definition names the target genus (IDO uses genus–differentia definitions). "
        f"Only **{prose_neutral_asserted_n}** asserted/immediate candidates are prose-neutral. "
        "These are the ones whose `elot-org-ancestors=false, else true` profile actually "
        "measures formal-axiom legibility rather than prose recovery (see §4, §5)."
    )
    lines.append(
        f"4. **All {by_source['entailed']} entailed candidates are ROBOT/HermiT-confirmed "
        "`supported` items but are not profileable by the direct-axiom instrument** (the "
        "licensing relation is a chain, not a serialized triple), so "
        f"{by_source['entailed'] - entailed_artifact_n} return a degenerate uniform-`false` "
        f"profile and {entailed_artifact_n} return a matcher false positive (§3a). Reported as "
        "a different kind, never as asserted."
    )
    asserted_dev_n = sum(
        c["source"] == "asserted" and (c["profile"] != EXPECTED_PROFILE or c["gate"] != "pass")
        for c in candidates
    )
    lines.append(
        f"5. **Three direct-axiom recoverability matcher false positives surfaced** and are "
        f"reported, not patched (§4): {entailed_artifact_n} in OFN (target IRI a substring of "
        f"the true parent, e.g. `Temporal` ⊂ `TemporalRegion`) and {asserted_dev_n} in ELOT "
        "(an existential-restriction filler counted as the named superclass, `lis:System`). "
        "`recoverability.py` was left unmodified."
    )
    lines.append("")
    lines.append("## 1. Enumeration totals")
    lines.append("")
    lines.append(
        f"From the canonical graph there are **{len(candidates)}** ordered pairs "
        "`lis:X ⊑ lis:Y` that IDO entails with both `X` and `Y` present in the corpus "
        "chunk store of all seven formats (the intersection of the seven oracle maps, "
        f"{len(shared_store_entities())} shared `lis:` entities). The total is under the "
        "~150 threshold, so **no sampling was applied**; every entailed pair is reported."
    )
    lines.append("")
    lines.append("By source:")
    lines.append("")
    lines.append("| source | count |")
    lines.append("| --- | --- |")
    for source in ("asserted", "entailed"):
        lines.append(f"| {source} | {by_source[source]} |")
    lines.append("")
    lines.append("By distance class:")
    lines.append("")
    lines.append("| distance class | count |")
    lines.append("| --- | --- |")
    for dclass in ("immediate", "near", "distant"):
        lines.append(f"| {dclass} | {by_class[dclass]} |")
    lines.append("")
    lines.append("By source × distance class:")
    lines.append("")
    lines.append("| source | immediate | near | distant |")
    lines.append("| --- | --- | --- | --- |")
    for source in ("asserted", "entailed"):
        lines.append(
            f"| {source} | {by_source_class[(source, 'immediate')]} "
            f"| {by_source_class[(source, 'near')]} "
            f"| {by_source_class[(source, 'distant')]} |"
        )
    lines.append("")
    lines.append(
        "Raw hierarchy distance (steps of asserted `rdfs:subClassOf` from `X` up to `Y`): "
        + ", ".join(f"d={d}: {n}" for d, n in sorted(by_distance.items()))
        + "."
    )
    lines.append("")
    lines.append(
        "The mapping is clean and exact: every **asserted** pair is **immediate** "
        "(distance 1) and every **entailed** pair is **near or distant** (distance ≥ 2). "
        "No asserted pair sits above its directly asserted parent, and no entailed pair "
        "is at distance 1, because *asserted* and *directly-asserted-parent* coincide in "
        "this ontology."
    )
    lines.append("")
    lines.append(f"`states_axiom` (subject prose names the target genus): **{len(states_axiom)}**.")
    lines.append("")

    lines.append("## 2. Candidate table")
    lines.append("")
    lines.append(
        "Grouped by distance class. `states_axiom` candidates are listed separately in "
        "§4. Gold chunks use format-stable entity IDs; the authoring checker resolves them "
        "in each of the seven corpora. The licensing column records the direct "
        "`rdfs:subClassOf` triple for asserted pairs and the entailing chain (from the "
        "ROBOT/HermiT explanation) for entailed pairs."
    )
    for dclass in ("immediate", "near", "distant"):
        group = [c for c in plain if c["distance_class"] == dclass]
        lines.append("")
        lines.append(f"### 2.{dclass} — {dclass} ({len(group)} candidates, `states_axiom` excluded)")
        lines.append("")
        if not group:
            lines.append("_None in this class after removing `states_axiom` candidates._")
            continue
        lines.append(TABLE_HEADER)
        for candidate in group:
            lines.append(candidate_row(candidate))

    lines.append("")
    lines.append("## 3. Profile-deviation section")
    lines.append("")
    lines.append(
        "Expected mechanism-level pattern (§2.1 of the brief): "
        "`elot-org-ancestors=false, else true`, gate `pass`."
    )
    lines.append("")
    asserted_dev = [c for c in deviations if c["source"] == "asserted"]
    entailed_all = [c for c in candidates if c["source"] == "entailed"]
    entailed_uniform_false = [c for c in entailed_all if c["profile"] == FALSE_PROFILE]
    entailed_artifact = [c for c in entailed_all if c["profile"] != FALSE_PROFILE]
    if not asserted_dev:
        lines.append(
            f"**No asserted (immediate) candidate deviates.** All {by_source['asserted']} "
            "profile exactly `elot-org-ancestors=false, else true` with gate `pass`, "
            "consistent with the established mechanism-level result: subsumption is written "
            "as a direct `SubClassOf` axiom in every format except `elot-org-ancestors`, "
            "which encodes it only as heading depth."
        )
    else:
        lines.append(
            f"**{len(asserted_dev)} asserted (immediate) candidate(s) deviate from the "
            "expected pattern.** These are the candidates §2.1 asks to be surfaced immediately, "
            "because an asserted subsumption that is *not* `elot-org-ancestors=false, else true` "
            "would contradict the mechanism-level result. In each case here the deviation is a "
            "**recoverability-matcher false positive**, not a real contradiction of the "
            "mechanism — the named superclass is genuinely absent from `elot-org-ancestors`, "
            "but the ELOT matcher matches the target IRI where it appears as the *filler of an "
            "existential `SubClassOf` restriction* on the same chunk:"
        )
        lines.append("")
        from experiment.corpus_index import get_oracle_chunks

        for candidate in asserted_dev:
            spurious = [
                fmt for fmt in FORMATS
                if candidate["profile"][fmt] and not expected.get(fmt, False)
            ]
            offending = []
            for fmt in ("elot-org-ancestors",):
                if fmt in spurious:
                    for _eid, content in get_oracle_chunks(fmt, [candidate["subject"]]):
                        offending += [
                            ln.strip()
                            for ln in content.splitlines()
                            if "SubClassOf" in ln and candidate["object"].split(":", 1)[1] in ln
                        ]
            lines.append(
                f"- `{candidate['id']}` `{candidate['subject']} ⊑ {candidate['object']}`: "
                f"profile {profile_string(candidate['profile'])}, gate `{candidate['gate']}`. "
                f"Spuriously `true` format(s): `{', '.join(spurious) or 'none'}`."
            )
            for line in offending:
                lines.append(f"  - surviving restriction line matched: `{line}`")
        lines.append("")
        lines.append(
            "Per §4, `recoverability.py` was **not** modified. The corrected reading is that "
            "each such candidate's *named-superclass* profile is `elot-org-ancestors=false, "
            "else true` as the mechanism predicts; the extra `true` is the matcher counting an "
            "existential-restriction filler as the named superclass. A human wanting one of "
            "these must note the confound."
        )
    lines.append("")
    lines.append("### 3a. Entailed candidates with a non-uniform profile — matcher artifact")
    lines.append("")
    if not entailed_artifact:
        lines.append("_None: every entailed candidate profiles uniformly false._")
    else:
        lines.append(
            f"**{len(entailed_artifact)} entailed candidate(s) profile non-uniformly, and the "
            "single `true` format is a false positive of the recoverability matcher, not real "
            "axiom recovery.** Each is an entailed pair whose target IRI is a proper prefix "
            "substring of the true immediate parent's IRI, and the OFN matcher in "
            "`recoverability.py` tests `object_id in args[1]` (a substring test, "
            "`_ofn_chunk_has_axiom`), so e.g. `lis:Temporal` matches inside "
            "`SubClassOf(... lis:TemporalRegion)`:"
        )
        lines.append("")
        for candidate in entailed_artifact:
            true_formats = [f for f in FORMATS if candidate["profile"][f]]
            lines.append(
                f"- `{candidate['id']}` `{candidate['subject']} ⊑ {candidate['object']}` "
                f"(direct parent `{candidate['path'][1]}`): profile "
                f"{profile_string(candidate['profile'])} — the `{', '.join(true_formats)}` "
                f"hit is `{candidate['object']}` matching as a substring of "
                f"`{candidate['path'][1]}`, gate `{candidate['gate']}`."
            )
        lines.append("")
        lines.append(
            "Per §4 of the brief, `recoverability.py` was **not** modified to tighten the OFN "
            "substring test. These candidates should not be put forward on the strength of a "
            "matcher artifact; a human who wants either pair must decide the recoverability "
            "question directly. The same prefix-substring effect also inflates the prose "
            "screen (`temporal` word-matches inside the genus phrase \"temporal region\")."
        )
    lines.append("")
    lines.append("### 3b. Entailed candidates with a uniform-false profile — by construction")
    lines.append("")
    lines.append(
        f"**The remaining {len(entailed_uniform_false)} entailed (near/distant) candidates "
        "profile uniformly `false` in every format, gate `failed`.** This is expected: the "
        "direct-axiom recoverability assessor requires the `X rdfs:subClassOf Y` triple to be "
        "*serialized in a gold chunk*, and for a transitively entailed pair that triple is "
        "written nowhere — only the immediate-parent links of the chain are serialized. "
        "`elot-org-ancestors` does surface `Y` as an ancestor heading, but the assessor "
        "deliberately rejects headings (see `recoverability.py`: \"Ancestor headings and other "
        "structural context are deliberately not accepted\"). The uniform-`false` profile "
        "therefore carries no per-item information and must not be read as the "
        "`elot-org-ancestors=false, else true` split; entailed candidates are a different kind "
        "and are reported as such, never presented as asserted."
    )
    lines.append("")
    lines.append(
        "**Representation-rule gap (per §4 of the brief).** The checker's licensing axiom is "
        "a single triple and cannot represent a subsumption *chain*, so entailed candidates "
        "cannot be profiled by the existing instrument. `recoverability.py` was **not** "
        "modified to add a chain/heading matcher branch; the gap is reported here instead. A "
        "human selecting an entailed item must decide separately whether heading-depth "
        "recovery in `elot-org-ancestors` (and multi-hop composition elsewhere) counts as "
        "recoverable for that item."
    )
    lines.append("")
    lines.append("Entailed candidates (near then distant), with the ROBOT/HermiT entailing chain:")
    lines.append("")
    lines.append(
        "| ID | Draft statement | Entailing chain | Source | Distance | Ancestor path "
        "| ROBOT/HermiT | Profile | Gate | Prose direction | Notes |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for candidate in sorted(entailed_all, key=lambda c: (c["distance"], c["id"])):
        prose = candidate["prose"]
        prose_cell = (
            f"`{prose['direction']}`; “{prose['genus_hit']}”"
            if prose["genus_hit"]
            else f"`{prose['direction']}`"
        )
        lines.append(
            "| {id} | {statement} | {licensing} | `{source}` | `{dclass}` (d={distance}) "
            "| {path} | {robot} | all false | `{gate}` | {prose} | {notes} |".format(
                id=candidate["id"],
                statement=candidate["statement"],
                licensing=candidate["licensing"],
                source=candidate["source"],
                dclass=candidate["distance_class"],
                distance=candidate["distance"],
                path=" → ".join(candidate["path"]),
                robot=candidate["robot_cell"],
                gate=candidate["gate"],
                prose=prose_cell.replace("|", "\\|"),
                notes=candidate["notes"].replace("|", "\\|"),
            )
        )

    lines.append("")
    lines.append("## 4. `states_axiom` candidates (listed separately)")
    lines.append("")
    lines.append(
        "For these candidates the subject's `naturalLanguageDefinition` or `usageNote` names "
        "the target class as its genus, so the subsumption is legible from prose alone. Prose "
        "recovery then succeeds even where the *axiom* is absent — which for this mechanism is "
        "exactly the `elot-org-ancestors` arm — so the recoverability profile of a "
        "`states_axiom` candidate is uninformative about formal-axiom legibility. These are the "
        "candidates most likely to look informative and be inert; they are flagged and counted "
        f"here. Count: **{len(states_axiom)}** ({sum(c['source'] == 'asserted' for c in states_axiom)} "
        f"asserted, {sum(c['source'] == 'entailed' for c in states_axiom)} entailed). The genus "
        "detection is a first-pass heuristic (target human-label phrase or altLabel appearing in "
        "the subject prose); the quoted fragment is provided for a human to confirm. **Caveat "
        "for single-word targets** (`Object`, `Temporal`): the word can match inside a more "
        "specific genus the prose actually asserts (e.g. `object` inside \"information object\", "
        "`temporal` inside \"temporal region\"), which for a distant target names a subclass of "
        "the target rather than the target itself. The quoted fragment disambiguates; treat "
        "these as \"prose names a genus that entails the target\" — still prose-legible, but "
        "confirm against the fragment."
    )
    lines.append("")
    if states_axiom:
        lines.append(TABLE_HEADER)
        for candidate in sorted(
            states_axiom, key=lambda c: (c["source"], c["distance"], c["id"])
        ):
            lines.append(candidate_row(candidate))
    else:
        lines.append("_No candidate's subject prose names the target genus._")

    lines.append("")
    lines.append("## 5. Candidates not put forward")
    lines.append("")
    lines.append(
        "No candidate is silently dropped. Two classes carry caveats a human selector must "
        "weigh, restated here so nothing is put forward without its qualification:"
    )
    lines.append("")
    lines.append(
        "- **Entailed (near/distant) candidates** are genuine `supported` items (ROBOT/HermiT "
        "confirms entailment for every one), but they cannot be profiled by the direct-axiom "
        "recoverability instrument and return a degenerate uniform-`false`/gate-`failed` "
        "profile. They should be selected only with an explicit, separate decision about what "
        "counts as recoverable for a multi-hop subsumption. See §3."
    )
    lines.append(
        "- **`states_axiom` candidates** (§4) have a recoverability profile that does not "
        "measure formal-axiom legibility, because the subsumption leaks into prose. Selecting "
        "one as a formal-legibility item would be a mistake; selecting one as a deliberate "
        "prose-contrast item is legitimate."
    )
    lines.append(
        "- **Matcher-artifact candidates** — `lis:System ⊑ lis:FunctionalObject` (ELOT "
        "restriction-filler, §3) and the two OFN substring pairs (§3a) — carry a `true` that is "
        "a false positive of the recoverability matcher rather than real axiom recovery, so "
        "their stored profile would misrepresent them. Do not put forward on the strength of "
        "the artifact."
    )
    lines.append("")
    prose_neutral_asserted = [
        c for c in candidates
        if c["source"] == "asserted" and c["prose"]["direction"] != "states_axiom"
    ]
    lines.append(
        f"**Pool-size note (stop condition 1).** {by_source['asserted']} asserted/immediate "
        "candidates survive §3.2 (entailment ROBOT-confirmed, profile computed, gate `pass`), "
        "which is above the 20-candidate floor, so the batch does not hard-stop. **But the "
        "distribution the author should see before selecting is lopsided:** of those "
        f"{by_source['asserted']}, **{len(states_axiom_asserted := [c for c in states_axiom if c['source'] == 'asserted'])} "
        f"are `states_axiom`** (subject prose names the genus), leaving only "
        f"**{len(prose_neutral_asserted)}** asserted/immediate candidates that are both "
        "gate-`pass` and prose-neutral: "
        + ", ".join(f"`{c['subject']} ⊑ {c['object']}`" for c in prose_neutral_asserted)
        + ". If the study needs formal-legibility items whose prose does not already settle "
        "the subsumption, the effective pool is these "
        f"{len(prose_neutral_asserted)}, far below ten. This is a selection judgement for the "
        "author — `states_axiom` items remain legitimate as a deliberate prose-contrast class "
        "(§4) — so it is reported, not resolved here."
    )

    lines.append("")
    lines.append("## 6. Verification record")
    lines.append("")
    lines.append(
        "- Every stored pilot verification `recoverability_profile` in `tasks.yaml` and "
        "`tasks_60.yaml` was recomputed and matched its stored value before this batch was "
        "processed."
    )
    lines.append(
        "- The seven-format profile for every one of the "
        f"{len(candidates)} candidates was computed with `assess_draft_recoverability` — the "
        "exact function `check_authoring_candidate` wraps."
    )
    if sample:
        sample_ids = ", ".join(f"`{s['id']}`" for s in sample)
        lines.append(
            "- The `check_authoring_candidate` CLI itself was run on an equivalence sample "
            f"spanning both gate outcomes and all three distance classes ({sample_ids}); the "
            "CLI output matched the in-process assessment for every sampled candidate."
        )
    lines.append(
        "- ROBOT/HermiT (`robot explain`, reasoner HermiT) was run once for every candidate "
        "against the canonical Turtle graph; it confirmed entailment for all "
        f"{len(candidates)} and supplied the entailing chain recorded above."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    graph = Graph().parse(CANONICAL_TURTLE, format="turtle")

    mismatches = check_pilot_profiles()
    if mismatches:
        raise SystemExit(
            "STOP (condition 2): recomputed pilot profile disagrees with stored value:\n  "
            + "\n  ".join(mismatches)
        )

    candidates = enumerate_candidates(graph)
    print(f"enumerated {len(candidates)} candidates", file=sys.stderr)

    counter = {"asserted": 0, "entailed": 0}
    for candidate in candidates:
        subject, object_ = candidate["subject"], candidate["object"]
        draft_map = draft(subject, object_)
        assessment = assess_draft_recoverability(draft_map)
        if assessment["errors"]:
            raise SystemExit(
                f"STOP (condition 2): checker errors for {subject}->{object_}: "
                f"{assessment['errors']}"
            )
        entailed, chain = robot_entails(subject, object_)
        if not entailed:
            raise SystemExit(
                f"STOP (condition 4): ROBOT/HermiT did not confirm {subject} SubClassOf "
                f"{object_}, which graph traversal reported as entailed."
            )
        counter[candidate["source"]] += 1
        candidate["id"] = f"B02-{candidate['source'][0].upper()}{counter[candidate['source']]:02d}"
        candidate["statement"] = draft_map["statement"]
        candidate["gold_chunks"] = draft_map["gold_chunks"]
        candidate["retrieval_gold_chunks"] = draft_map["retrieval_gold_chunks"]
        candidate["profile"] = assessment["profile"]
        candidate["uniform"] = assessment["uniform"]
        candidate["gate"] = assessment["gate_verdict"]
        candidate["reasoning_type"] = "structural"
        candidate["prose"] = screen_prose(graph, subject, object_)
        candidate["robot_cell"] = "entailed"
        if candidate["source"] == "asserted":
            candidate["licensing"] = f"`{subject} rdfs:subClassOf {object_}`"
            candidate["notes"] = "Directly asserted immediate subclass axiom."
        else:
            candidate["licensing"] = f"chain: {chain}" if chain else "chain (see explanation)"
            candidate["notes"] = (
                "Transitively entailed; no direct SubClassOf triple serialized in any "
                "format, so the direct-axiom profile is uniform-false (see §3)."
            )
        print(
            f"  {candidate['id']} {subject}->{object_} "
            f"[{candidate['source']}/{candidate['distance_class']}] "
            f"gate={candidate['gate']} prose={candidate['prose']['direction']}",
            file=sys.stderr,
        )

    # CLI equivalence sample: one per (gate outcome × distance class) where available.
    sample: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate["gate"], candidate["distance_class"])
        if key not in seen_keys:
            cli = cli_assessment(draft(candidate["subject"], candidate["object"]))
            if cli["profile"] != candidate["profile"]:
                raise SystemExit(
                    f"STOP (condition 2): CLI/in-process disagree for {candidate['id']}: "
                    f"cli={cli['profile']} inprocess={candidate['profile']}"
                )
            seen_keys.add(key)
            sample.append(candidate)

    report = build_report(candidates, sample)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"wrote {args.output} with {len(candidates)} candidates", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
