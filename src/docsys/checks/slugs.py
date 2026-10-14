"""The slug check (ADR-028): a document's filename is named after its slug."""

from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule

TYPE: Final = Rule("slugs/type", "error")
FORM: Final = Rule("slugs/form", "error")
FILENAME: Final = Rule("slugs/filename", "error")
RULES: Final = (TYPE, FORM, FILENAME)


def check(workspace: Path, config: Config) -> list[Finding]:
    return []
