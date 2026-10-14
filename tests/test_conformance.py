"""The conformance suite, `conformance/*.yaml`: each rule stated as the documents
of a small workspace and the findings expected on them, in data files that every
docsys package runs. This module is the Python package's runner for them: it
builds each case's workspace as a fresh git repository, runs the check, and
compares the findings. It also holds the package to the rules each file declares,
so the data and the code cannot drift apart."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard

import pytest

from docsys.checks import links
from docsys.config import Config, load_config
from docsys.findings import Finding, Rule
from docsys.workspace import CONFIG_NAME
from docsys.yaml_frontmatter import load_yaml

SUITE = Path(__file__).resolve().parent.parent / "conformance"

Check = Callable[[Path, Config], list[Finding]]

# conformance/<name>.yaml -> the check it states, and the rules that check reports.
CHECKS: dict[str, tuple[Check, tuple[Rule, ...]]] = {
    "links": (links.check, links.RULES),
}


@dataclass(frozen=True)
class Case:
    name: str
    config: str
    files: dict[str, str]
    findings: list[tuple[str, str, int]]  # (rule, path, line)


# --- reading a suite file ----------------------------------------------------------


def _is_mapping(value: object) -> TypeGuard[dict[object, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _strings(value: object, where: str) -> dict[str, str]:
    assert _is_mapping(value), f"{where} must be a mapping"
    checked: dict[str, str] = {}
    for key, item in value.items():
        assert isinstance(key, str), f"{where}: key {key!r} is not a string"
        assert isinstance(item, str), f"{where}.{key} must be a string"
        checked[key] = item
    return checked


def _mapping(value: object, where: str) -> dict[str, object]:
    assert _is_mapping(value), f"{where} must be a mapping"
    return {str(key): item for key, item in value.items()}


def load_suite(name: str) -> tuple[dict[str, dict[str, str]], list[Case]]:
    """The rules a suite file declares, and its cases."""
    with open(SUITE / f"{name}.yaml", encoding="utf-8") as fh:
        suite = _mapping(load_yaml(fh), name)
    rules = {rule: _strings(spec, f"rules.{rule}") for rule, spec in _mapping(suite["rules"], "rules").items()}
    raw_cases = suite["cases"]
    assert _is_list(raw_cases), "cases must be a list"
    cases: list[Case] = []
    for raw in raw_cases:
        case = _mapping(raw, "case")
        expected = case["findings"]
        assert _is_list(expected), "findings must be a list"
        findings: list[tuple[str, str, int]] = []
        for item in expected:
            finding = _strings(item, "finding")
            findings.append((finding["rule"], finding["path"], int(finding["line"])))
        config = case.get("config", "version: 1\n")
        assert isinstance(config, str), "config must be the text of docsys.yaml"
        name_ = case["name"]
        assert isinstance(name_, str), "name must be a string"
        cases.append(Case(name=name_, config=config, files=_strings(case["files"], "files"), findings=findings))
    return rules, cases


def build(root: Path, case: Case) -> Path:
    """The case's workspace: its files and its docsys.yaml, in a new git repository."""
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / CONFIG_NAME).write_text(case.config, encoding="utf-8")
    for path, text in case.files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


PARAMS = [pytest.param(name, case, id=f"{name}: {case.name}") for name in CHECKS for case in load_suite(name)[1]]


# --- the tests --------------------------------------------------------------------


@pytest.mark.parametrize(("name", "case"), PARAMS)
def test_the_check_reports_what_the_case_states(name: str, case: Case, tmp_path: Path) -> None:
    workspace = build(tmp_path / "workspace", case)
    check, _ = CHECKS[name]
    found = check(workspace, load_config(workspace))
    assert [(f.rule, f.path, f.line) for f in found] == case.findings
    for finding in found:
        assert finding.fix, f"{finding} carries no fix"
        assert str(finding).startswith(f"{finding.path}:{finding.line}: {finding.rule}: ")
        assert str(finding).endswith(f" — fix: {finding.fix}")


@pytest.mark.parametrize("name", list(CHECKS))
def test_the_package_reports_the_rules_the_suite_declares(name: str) -> None:
    rules, _ = load_suite(name)
    _, implemented = CHECKS[name]
    assert {rule.id: rule.severity for rule in implemented} == {rule: spec["severity"] for rule, spec in rules.items()}


@pytest.mark.parametrize("name", list(CHECKS))
def test_every_rule_has_a_case_that_reports_it(name: str) -> None:
    rules, cases = load_suite(name)
    reported = {rule for case in cases for rule, _, _ in case.findings}
    assert reported == set(rules)


def test_every_suite_file_is_run() -> None:
    assert {path.stem for path in SUITE.glob("*.yaml")} == set(CHECKS)
