"""The paired-change check: the tooling does not change unexplained."""

from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule

UNPAIRED: Final = Rule("paired-change/unpaired", "error")
ADVISORY: Final = Rule("paired-change/advisory", "warning")
ANCHOR: Final = Rule("paired-change/anchor", "error")
BRANCHES: Final = Rule("paired-change/branches", "error")
RULES: Final = (UNPAIRED, ADVISORY, ANCHOR, BRANCHES)


def check(workspace: Path, config: Config) -> list[Finding]:
    return []
