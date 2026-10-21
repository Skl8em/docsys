"""Sealing: writing a frozen record's `hash:` line.

The seal itself, and the canonical form it hashes, are `docsys.checks.hashes`; this
module only writes the line the fixity check later verifies. A seal that no longer
matches is not overwritten unless the caller says so: re-sealing a record that
changed is a deliberate act.
"""

from dataclasses import dataclass
from enum import Enum

from .checks.hashes import declared_seal, seal_of, split_document


class SealOutcome(Enum):
    SEALED = "sealed"
    RESEALED = "resealed"
    UNCHANGED = "unchanged"
    REFUSED = "already sealed, content changed"


@dataclass(frozen=True)
class Sealed:
    outcome: SealOutcome
    text: str


def seal_text(text: str) -> str:
    """The seal of a document's present content. Raises `ValueError` without a
    closed frontmatter block."""
    parts = split_document(text)
    if parts is None:
        raise ValueError("no frontmatter block")
    return seal_of(*parts)


def sealed_text(text: str, *, reseal: bool) -> Sealed:
    """The document with its `hash:` line written, and what was done. The line goes
    last in the frontmatter; line endings and everything else are kept."""
    parts = split_document(text)
    if parts is None:
        raise ValueError("no frontmatter block")
    frontmatter, body = parts
    new = seal_of(frontmatter, body)
    declared = declared_seal(frontmatter)
    existing = declared[0] if declared else ""
    if existing == new:
        return Sealed(SealOutcome.UNCHANGED, text)
    if existing and not reseal:
        return Sealed(SealOutcome.REFUSED, text)
    lines = text.split("\n")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    carriage = "\r" if lines[0].endswith("\r") else ""
    kept = [line for line in lines[1:end] if not line.startswith("hash:")]
    out = [lines[0], *kept, f"hash: {new}{carriage}", *lines[end:]]
    return Sealed(SealOutcome.RESEALED if existing else SealOutcome.SEALED, "\n".join(out))
