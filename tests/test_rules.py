"""The rules and their severities: every check names its rules, each rule has the
methodology's default severity, and `rules:` in `docsys.yaml` changes it per rule —
to `error`, `warning` or `off` — for a rule that exists."""

import pytest

from docsys import tools
from docsys.checks import frontmatter, hashes, ledger, links, paired_change, phase_state, slugs, ulids
from docsys.config import ConfigError, validate
from docsys.rules import RULES, severities

CHECK_RULES = (
    frontmatter.RULES,
    hashes.RULES,
    ledger.RULES,
    links.RULES,
    paired_change.RULES,
    phase_state.RULES,
    slugs.RULES,
    tools.RULES,
    ulids.RULES,
)


def test_the_registry_holds_every_rule_of_every_check_once() -> None:
    expected = sorted(rule.id for rules in CHECK_RULES for rule in rules)
    assert sorted(rule.id for rule in RULES) == expected
    assert len(set(expected)) == len(expected)


def test_every_rule_is_named_check_slash_rule() -> None:
    for rule in RULES:
        check, _, name = rule.id.partition("/")
        assert check
        assert name


def test_without_rules_in_the_configuration_each_rule_has_its_default() -> None:
    defaults = severities(validate({"version": "1"}))
    assert defaults == {rule.id: rule.severity for rule in RULES}
    assert defaults["hashes/unsealed"] == "off"
    assert defaults["frontmatter/open"] == "warning"
    assert defaults["links/resolve"] == "error"


def test_the_configuration_sets_a_severity_rule_by_rule() -> None:
    cfg = validate({"version": "1", "rules": {"links/resolve": "warning", "hashes/unsealed": "error"}})
    set_ = severities(cfg)
    assert set_["links/resolve"] == "warning"
    assert set_["hashes/unsealed"] == "error"
    assert set_["slugs/form"] == "error"


@pytest.mark.parametrize("rule", ["links/nothing", "nothing/resolve", "links/resolv"])
def test_a_rule_that_does_not_exist_is_refused_with_the_rules_that_do(rule: str) -> None:
    cfg = validate({"version": "1", "rules": {rule: "off"}})
    with pytest.raises(ConfigError) as caught:
        severities(cfg)
    message = str(caught.value)
    assert message.startswith("docsys.yaml: ")
    assert f"`rules.{rule}`" in message
    assert "fix:" in message
    assert "links/resolve" in message
