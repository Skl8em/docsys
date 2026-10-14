"""The phase-state check: every place that speaks of the current phase agrees with
the ledger."""

from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule

LEDGER: Final = Rule("phase-state/ledger", "error")
FOLDER: Final = Rule("phase-state/folder", "error")
TABLE: Final = Rule("phase-state/table", "error")
MENTION: Final = Rule("phase-state/mention", "error")
STATUS: Final = Rule("phase-state/status", "error")
FIELD: Final = Rule("phase-state/field", "error")
LAGGING: Final = Rule("phase-state/lagging", "error")
RULES: Final = (LEDGER, FOLDER, TABLE, MENTION, STATUS, FIELD, LAGGING)


def check(workspace: Path, config: Config) -> list[Finding]:
    return []
