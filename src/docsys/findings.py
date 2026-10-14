"""Rules and findings — part of the cross-package API: every docsys package names
its rules with the same identifiers, gives them the same default severities, and
reports a finding as its path, line, rule, message and fix.

    path:line: rule: message — fix: the edit that clears it
"""

from dataclasses import dataclass
from typing import Literal

# What a finding of the rule does to the run: an error fails it, a warning is
# reported without failing it, and a rule that is off is not reported.
Severity = Literal["error", "warning", "off"]


@dataclass(frozen=True)
class Rule:
    id: str  # `<check>/<rule>`, e.g. `links/resolve`
    severity: Severity  # the methodology's default


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str  # relative to the workspace, POSIX
    line: int  # 1-based
    message: str
    fix: str  # the edit that clears it, addressed to a reader with no other context

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.message} — fix: {self.fix}"
