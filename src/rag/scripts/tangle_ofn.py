#!/usr/bin/env python3
"""Generate a canonical OWL Functional Syntax (OFN) serialization of LIS-14.

Backend: ROBOT (OWLAPI). As with the JSON-LD arm, the source is derived from 
the canonical Turtle so the OFN variant is axiom-identical to the Turtle/OMN/
ELOT/JSON-LD variants by construction.

Determinism. OWLAPI axiom ordering is not stable across runs (set iteration order),
so successive ``robot convert`` invocations can emit the same axioms in a different
order. This script canonicalises explicitly: prefix declarations, ontology-level
annotations, and axioms are each sorted by a deterministic key before writing, so
the source file is byte-stable regardless of what order ROBOT emitted.

ROBOT is a build-time dependency only: it is needed to regenerate
``data/LIS-14-for-FDIS (1).ofn``, never to run the experiment, which just reads the
generated file. Point ``ROBOT_JAR`` at robot.jar, or put ``robot`` on PATH.
Download: https://github.com/ontodev/robot/releases (needs Java 11+).

Provenance of the committed .ofn (2026-07-17). OWLAPI's rendering choices affect the
output bytes, so regenerating the identical file requires the same toolchain. ``robot 
--version`` reports only its own version and does NOT surface the bundled OWLAPI 
version, so the jar checksum is the real pin:

    ROBOT             1.9.10
    robot.jar SHA256  16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105
    Java              openjdk 16.0.2 (Temurin-16.0.2+7)
    source .ttl       SHA256 669ddbe19807f918095b5e78c18bfebf5c00b2ad74c0bd8eef51b31c6b82cca6
    output .ofn       SHA256 fb6cd0132965990b9cc507f20517f6aa3e660162125ebcf5388358849d400fcd

"""

from __future__ import annotations

import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAG_DIR))

DATA_DIR = RAG_DIR / "data"
TTL_PATH = DATA_DIR / "LIS-14-for-FDIS (1).ttl"
OFN_PATH = DATA_DIR / "LIS-14-for-FDIS (1).ofn"


def _robot_command() -> list[str]:
    """The ROBOT invocation: ``$ROBOT_JAR`` via java, else ``robot`` on PATH."""
    jar = os.environ.get("ROBOT_JAR")
    if jar:
        if not Path(jar).is_file():
            raise SystemExit(f"ROBOT_JAR is set but not a file: {jar}")
        java = shutil.which("java")
        if not java:
            raise SystemExit("ROBOT_JAR is set but no `java` on PATH (ROBOT needs Java 11+)")
        return [java, "-jar", jar]
    exe = shutil.which("robot")
    if exe:
        return [exe]
    raise SystemExit(
        "ROBOT not found. Set ROBOT_JAR=/path/to/robot.jar (needs Java 11+) or put "
        "`robot` on PATH. Download: https://github.com/ontodev/robot/releases\n"
        "ROBOT is only needed to regenerate the .ofn source, not to run the experiment."
    )


def robot_convert_to_ofn(ttl_path: Path) -> str:
    """Run ``robot convert --format ofn`` on the canonical Turtle."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.ofn"
        cmd = _robot_command() + [
            "convert",
            "--input", str(ttl_path),
            "--format", "ofn",
            "--output", str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(f"robot convert failed:\n{proc.stdout}\n{proc.stderr}")
        return out.read_text(encoding="utf-8")


def canonicalize_ofn(text: str) -> str:
    """Sort an OFN document into a byte-stable form.

    ROBOT emits one top-level construct per line at column 0: ``Prefix(...)`` lines,
    the ``Ontology(<iri> <versionIri>`` header, ontology-level ``Annotation(...)``
    lines, the axioms, and a closing ``)``. Each group is sorted independently -- the
    header and the closing paren keep their position, since they are structural.
    Sorting by the rendered line makes the output independent of OWLAPI's unstable
    axiom iteration order.

    ROBOT's ``#   Classes`` / ``#   Object Properties`` section comments are dropped:
    they label ROBOT's own emission grouping, which sorting destroys anyway, so they
    would otherwise sort in among the axioms as meaningless noise.
    """
    lines = [
        ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]

    prefixes = sorted(ln for ln in lines if ln.startswith("Prefix("))
    header = next((ln for ln in lines if ln.startswith("Ontology(")), None)
    if header is None:
        raise SystemExit("OFN output has no Ontology(...) header")

    # ROBOT splits the header across two lines, putting the version IRI bare on its
    # own line: ``Ontology(<...core>`` / ``<...core/4.2>``. It is part of the header,
    # not an axiom -- sorting it into the body yields an unparseable file.
    head_idx = lines.index(header)
    header_lines = [header]
    body = lines[head_idx + 1 :]
    if body and re.fullmatch(r"<[^>]+>", body[0].strip()):
        header_lines.append(body[0])
        body = body[1:]
    if body and body[-1].strip() == ")":
        body = body[:-1]
    else:
        raise SystemExit("OFN output does not end with a closing ')'")

    # Ontology-level annotations stay ahead of the axioms, mirroring ROBOT's own
    # layout; both groups are sorted by rendered text for determinism.
    annotations = sorted(ln for ln in body if ln.startswith("Annotation("))
    axioms = sorted(ln for ln in body if not ln.startswith("Annotation("))

    out = prefixes + [""] + header_lines + annotations + axioms + [")"]
    return "\n".join(out) + "\n"


def build_ofn(ttl_path: Path) -> str:
    return canonicalize_ofn(robot_convert_to_ofn(ttl_path))


def _axiom_multiset(ofn_text: str):
    """The axiom set of an OFN document, keyed by content.

    Parsed with py-horned-owl (a real OWL parser) and re-rendered through its own
    writer so both sides of a comparison share one rendering. Keying on content is
    the point: horned-owl's model objects have identity-based ``repr``, so comparing
    those compares memory addresses and always reports a difference.
    """
    import pyhornedowl  # build-time only; see module docstring

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.ofn"
        p.write_text(ofn_text, encoding="utf-8")
        onto = pyhornedowl.open_ontology_from_file(str(p), "ofn")
        rendered = onto.save_to_string("ofn")
    return collections.Counter(ln.strip() for ln in rendered.splitlines() if ln.strip())


def assert_canonicalisation_preserves_axioms(raw: str, canonical: str) -> int:
    """Gate: canonicalisation must preserve the axiom set exactly.

    Set equality, not count equality: two documents can agree on axiom count and
    differ in content. This is also the gate that catches a *byte-stable* but wrong
    file -- sorting lines is deterministic even when it shreds a multi-line construct
    (as it did with ROBOT's two-line ``Ontology(...)`` header), so stability alone
    proves nothing about correctness.
    """
    before, after = _axiom_multiset(raw), _axiom_multiset(canonical)
    if before != after:
        lost = list((before - after).elements())[:5]
        gained = list((after - before).elements())[:5]
        raise SystemExit(
            "canonicalisation changed the axiom set:\n"
            f"  lost:   {lost}\n"
            f"  gained: {gained}"
        )
    return sum(after.values())


def main() -> int:
    if not TTL_PATH.exists():
        raise SystemExit(f"Turtle source not found: {TTL_PATH}")

    raw = robot_convert_to_ofn(TTL_PATH)
    text = canonicalize_ofn(raw)

    # Gate: sorting must not have changed the axiom set (set equality, not count).
    n_parsed = assert_canonicalisation_preserves_axioms(raw, text)

    OFN_PATH.write_text(text, encoding="utf-8")
    n_axioms = sum(
        1
        for ln in text.splitlines()
        if ln
        and not ln.startswith(("Prefix(", "Ontology(", "Annotation("))
        and ln != ")"
        and not re.fullmatch(r"<[^>]+>", ln.strip())  # the bare version IRI line
    )
    print(
        f"wrote {OFN_PATH} ({len(text)} bytes, {n_axioms} axiom lines; "
        f"{n_parsed} constructs parsed, axiom set preserved by canonicalisation)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
