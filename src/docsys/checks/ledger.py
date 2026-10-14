"""The phase ledger check: the ledger's own rules."""

from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule

MISSING: Final = Rule("ledger/missing", "error")
YAML: Final = Rule("ledger/yaml", "error")
SHAPE: Final = Rule("ledger/shape", "error")
FORM: Final = Rule("ledger/form", "error")
NUMBER: Final = Rule("ledger/number", "error")
UNIQUE: Final = Rule("ledger/unique", "error")
CURRENT: Final = Rule("ledger/current", "error")
ORDER: Final = Rule("ledger/order", "error")
LAGGING: Final = Rule("ledger/lagging", "error")
RULES: Final = (MISSING, YAML, SHAPE, FORM, NUMBER, UNIQUE, CURRENT, ORDER, LAGGING)


def check(workspace: Path, config: Config) -> list[Finding]:
    return []
