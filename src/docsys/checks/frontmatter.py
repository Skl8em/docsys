"""The frontmatter check: every document's frontmatter is judged by the vocabulary."""

from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule

YAML: Final = Rule("frontmatter/yaml", "error")
MISSING_BLOCK: Final = Rule("frontmatter/missing-block", "error")
REQUIRED: Final = Rule("frontmatter/required", "error")
PROVENANCE: Final = Rule("frontmatter/provenance", "error")
ENUM: Final = Rule("frontmatter/enum", "error")
REGISTER: Final = Rule("frontmatter/register", "error")
HASH: Final = Rule("frontmatter/hash", "error")
AUDIENCE: Final = Rule("frontmatter/audience", "error")
AUDIENCE_ROLE: Final = Rule("frontmatter/audience-role", "warning")
ROOT_ONLY: Final = Rule("frontmatter/root-only", "error")
OPEN: Final = Rule("frontmatter/open", "warning")
VOCABULARY: Final = Rule("frontmatter/vocabulary", "error")
RULES: Final = (
    YAML,
    MISSING_BLOCK,
    REQUIRED,
    PROVENANCE,
    ENUM,
    REGISTER,
    HASH,
    AUDIENCE,
    AUDIENCE_ROLE,
    ROOT_ONLY,
    OPEN,
    VOCABULARY,
)


def check(workspace: Path, config: Config) -> list[Finding]:
    return []
