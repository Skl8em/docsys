"""The runner: every check the configuration turns on, run in a fixed order, each
finding given the severity its rule has in this workspace.

The checks run in the order of `CHECKS` — the order of their rules in
`docsys.rules.RULES` — and a failing check does not stop the ones after it: the
run is the conjunction of every check, and a reader needs every failure from one
run. A check whose section the configuration leaves out reports nothing.

    from docsys.runner import run
    report = run(workspace, cfg)
    report.errors    # findings of rules at `error`: the run fails
    report.warnings  # findings of rules at `warning`: reported, not failing
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .checks import frontmatter, hashes, ledger, links, paired_change, phase_state, slugs, ulids
from .config import Config
from .findings import Finding
from .rules import severities

Check = Callable[[Path, Config], list[Finding]]

CHECKS: Final[tuple[Check, ...]] = (
    links.check,
    frontmatter.check,
    ulids.check,
    slugs.check,
    hashes.check,
    paired_change.check,
    ledger.check,
    phase_state.check,
)


@dataclass(frozen=True)
class Report:
    errors: list[Finding] = field(default_factory=list[Finding])
    warnings: list[Finding] = field(default_factory=list[Finding])


def run(workspace: Path, config: Config) -> Report:
    """Run the checks. Raises ConfigError when `rules:` names a rule that no check
    has, and DocumentsError when the documents cannot be listed."""
    severity = severities(config)
    errors: list[Finding] = []
    warnings: list[Finding] = []
    for check in CHECKS:
        for finding in check(workspace, config):
            match severity[finding.rule]:
                case "error":
                    errors.append(finding)
                case "warning":
                    warnings.append(finding)
                case "off":
                    pass
    return Report(errors, warnings)
