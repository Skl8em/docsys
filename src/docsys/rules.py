"""The rules of every check, and the severity each has in a workspace.

A rule's default severity is the methodology's, set where the check names the rule;
`rules:` in `docsys.yaml` replaces it rule by rule — `error` fails the run,
`warning` is reported without failing it, `off` is not reported.

    from docsys.rules import RULES, severities
    severities(cfg)["links/resolve"]  # "error", unless docsys.yaml says otherwise
"""

from typing import Final

from . import tools
from .checks import frontmatter, hashes, ledger, links, paired_change, phase_state, slugs, ulids
from .config import Config, ConfigError
from .findings import Rule, Severity

RULES: Final[tuple[Rule, ...]] = (
    *links.RULES,
    *frontmatter.RULES,
    *ulids.RULES,
    *slugs.RULES,
    *hashes.RULES,
    *paired_change.RULES,
    *ledger.RULES,
    *phase_state.RULES,
    *tools.RULES,
)


def severities(config: Config) -> dict[str, Severity]:
    """The severity of every rule in this workspace. Raises ConfigError when
    `rules:` names a rule that no check has."""
    known: dict[str, Severity] = {rule.id: rule.severity for rule in RULES}
    for rule in config["rules"]:
        if rule not in known:
            raise ConfigError(
                f"`rules.{rule}` names no rule — fix: use one of {', '.join(sorted(known))}, or remove it."
            )
    return {**known, **config["rules"]}
