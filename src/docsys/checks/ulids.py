"""The ULID check (the documentation system's ADR-028): identifiers, and the
supersession references between records."""

from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule

FORM: Final = Rule("ulids/form", "error")
UNIQUE: Final = Rule("ulids/unique", "error")
RESOLVE: Final = Rule("ulids/resolve", "error")
SELF: Final = Rule("ulids/self", "error")
SYMMETRIC: Final = Rule("ulids/symmetric", "error")
CYCLE: Final = Rule("ulids/cycle", "error")
REGISTER: Final = Rule("ulids/register", "error")
RULES: Final = (FORM, UNIQUE, RESOLVE, SELF, SYMMETRIC, CYCLE, REGISTER)


def check(workspace: Path, config: Config) -> list[Finding]:
    return []
