"""The fixity check: a frozen record's `hash:` seal matches its content.

A seal is the SHA-256 of a canonical form of the document (`canonical_text`), so it
travels with the document and verifies it wherever it is copied to. The canonical
form is the contract: changing it invalidates every seal already written.

  1. read as UTF-8, CRLF and CR as LF, and split at the frontmatter fences;
  2. frontmatter: drop the `hash:` lines, strip trailing whitespace, drop blank
     lines, then sort the rest, so that reordering keys breaks nothing;
  3. body: strip trailing whitespace per line, then blank lines at both ends;
  4. canonical text = sorted frontmatter + "\\n---\\n" + body + "\\n";
  5. seal = "sha256:" + the hex SHA-256 of its UTF-8.

The seal is read and computed over lines, not parsed YAML, so a document whose YAML
cannot be read still has its seal verified. A frozen record that carries no seal is
reported by a rule that is off by default: sealing is optional.
"""

import hashlib
from pathlib import Path
from typing import Final, TypeGuard

from ..config import Config
from ..documents import documents
from ..findings import Finding, Rule
from ..yaml_frontmatter import Frontmatter, FrontmatterError, parse

SEAL: Final = Rule("hashes/seal", "error")
UNSEALED: Final = Rule("hashes/unsealed", "off")
RULES: Final = (SEAL, UNSEALED)

# Which `status` words close a record, and which do not. The vocabulary declares the
# words but leaves which are frozen among its open questions, so the answer is here,
# and tests/test_hashes.py fails when a declared word is in neither list.
FROZEN_STATUSES: Final = ("accepted", "done", "stable")
OPEN_STATUSES: Final = ("draft", "deprecated", "in-progress", "planned")


def _is_mapping(value: object) -> TypeGuard[dict[object, object]]:
    return isinstance(value, dict)


def split_document(text: str) -> tuple[list[str], list[str]] | None:
    """The frontmatter lines and the body lines, or None when there is no closed
    frontmatter block."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], lines[index + 1 :]
    return None


def canonical_text(frontmatter: list[str], body: list[str]) -> str:
    kept = sorted(line.rstrip() for line in frontmatter if line.strip() and line.split(":", 1)[0].strip() != "hash")
    stripped = [line.rstrip() for line in body]
    while stripped and not stripped[0]:
        stripped.pop(0)
    while stripped and not stripped[-1]:
        stripped.pop()
    return "\n".join(kept) + "\n---\n" + "\n".join(stripped) + "\n"


def seal_of(frontmatter: list[str], body: list[str]) -> str:
    return "sha256:" + hashlib.sha256(canonical_text(frontmatter, body).encode("utf-8")).hexdigest()


def is_frozen(frontmatter: Frontmatter) -> bool:
    """A project's diachronic record that has closed. A template's specimen
    (`id: <phase-or-project-id>`) is not a record of any project."""
    provenance = frontmatter.get("provenance", (None, 0))[0]
    if not _is_mapping(provenance) or provenance.get("type") != "project":
        return False
    if "<" in str(provenance.get("id", "")):
        return False
    return frontmatter.get("view", (None, 0))[0] == "diachronic" and (
        frontmatter.get("status", (None, 0))[0] in FROZEN_STATUSES
    )


def _declared(frontmatter: list[str]) -> tuple[str, int] | None:
    """The `hash:` line's value, and its file line (the block starts on line 2)."""
    for index, line in enumerate(frontmatter):
        if line.startswith("hash:"):
            return line.split(":", 1)[1].strip(), index + 2
    return None


def check(workspace: Path, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    for path in documents(workspace, config["scope"]):
        try:
            text = (workspace / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        parts = split_document(text)
        if parts is None:
            continue
        frontmatter, body = parts
        declared = _declared(frontmatter)
        if declared is not None:
            actual = seal_of(frontmatter, body)
            if declared[0] != actual:
                findings.append(
                    Finding(
                        SEAL.id,
                        path,
                        declared[1],
                        f"frozen record changed since it was sealed (declared {declared[0]!r}, actual {actual})",
                        f"revert the change, or re-freeze deliberately by setting `hash: {actual}`",
                    )
                )
            continue
        try:
            parsed = parse(text)
        except FrontmatterError:
            continue
        if parsed is not None and is_frozen(parsed):
            findings.append(
                Finding(
                    UNSEALED.id,
                    path,
                    1,
                    "frozen record carries no `hash:` seal",
                    "seal it by adding `hash:` with the seal of its present content, or leave it unsealed",
                )
            )
    return findings
