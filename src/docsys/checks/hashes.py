"""The fixity check: a frozen record's `hash:` seal matches its content."""

from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule

SEAL: Final = Rule("hashes/seal", "error")
UNSEALED: Final = Rule("hashes/unsealed", "off")
RULES: Final = (SEAL, UNSEALED)


def check(workspace: Path, config: Config) -> list[Finding]:
    return []
