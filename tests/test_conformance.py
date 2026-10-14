"""The conformance suite, `conformance/*.yaml`: each rule stated as the documents
of a small workspace and the findings expected on them, in data files that every
docsys package runs. This module is the Python package's runner for them: it
builds each case's workspace as a fresh git repository, runs the check, and
compares the findings. It also holds the package to the rules each file declares,
so the data and the code cannot drift apart."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeGuard

import pytest

from docsys.checks import hashes, ledger, links, paired_change, phase_state, slugs, ulids
from docsys.config import Config, load_config
from docsys.findings import Finding, Rule
from docsys.workspace import CONFIG_NAME
from docsys.yaml_frontmatter import load_yaml

SUITE = Path(__file__).resolve().parent.parent / "conformance"

Check = Callable[[Path, Config], list[Finding]]

# conformance/<name>.yaml -> the check it states, and the rules that check reports.
CHECKS: dict[str, tuple[Check, tuple[Rule, ...]]] = {
    "ledger": (ledger.check, ledger.RULES),
    "links": (links.check, links.RULES),
    "hashes": (hashes.check, hashes.RULES),
    "paired-change": (paired_change.check, paired_change.RULES),
    "phase-state": (phase_state.check, phase_state.RULES),
    "slugs": (slugs.check, slugs.RULES),
    "ulids": (ulids.check, ulids.RULES),
}


@dataclass(frozen=True)
class Commit:
    message: str
    files: dict[str, str | None] = field(default_factory=dict)  # path -> text, None deletes it
    label: str | None = None  # `${label}` in the config becomes this commit's id
    branch: str | None = None  # switch to it (created if absent) before committing, and stay
    merge: str | None = None  # merge this branch into the current one, instead of committing files


@dataclass(frozen=True)
class Case:
    name: str
    config: str
    files: dict[str, str]
    findings: list[tuple[str, str, int]]  # (rule, path, line)
    history: list[Commit] = field(default_factory=list)
    branch: str | None = None  # the branch the workspace ends on (default: the last commit's)
    detached: bool = False  # HEAD detached at the end


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


def _commit(raw: object) -> Commit:
    item = _mapping(raw, "history item")
    files: dict[str, str | None] = {}
    for path, text in _mapping(item.get("files", {}), "history files").items():
        assert text is None or isinstance(text, str), f"history files.{path} must be a string or null"
        files[path] = text
    strings = {key: item.get(key) for key in ("message", "label", "branch", "merge")}
    for key, value in strings.items():
        assert value is None or isinstance(value, str), f"history {key} must be a string"
    message = strings["message"]
    assert isinstance(message, str), "a history item needs a message"
    return Commit(
        message=message,
        files=files,
        label=strings["label"] if isinstance(strings["label"], str) else None,
        branch=strings["branch"] if isinstance(strings["branch"], str) else None,
        merge=strings["merge"] if isinstance(strings["merge"], str) else None,
    )


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
        raw_history = case.get("history", [])
        assert _is_list(raw_history), "history must be a list"
        branch = case.get("branch")
        assert branch is None or isinstance(branch, str), "branch must be a string"
        cases.append(
            Case(
                name=name_,
                config=config,
                files=_strings(case.get("files", {}), "files"),
                findings=findings,
                history=[_commit(item) for item in raw_history],
                branch=branch,
                detached=case.get("detached") == "true",
            )
        )
    return rules, cases


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=docsys", "-c", "user.email=docsys@example.invalid", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def switch(root: Path, branch: str) -> None:
    exists = git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0
    git(root, "switch", "-q", *([] if exists else ["-c"]), branch)


def build(root: Path, case: Case) -> Path:
    """The case's workspace, in a new git repository: its history, if it has one, made
    commit by commit; then its docsys.yaml and its files, none of them committed."""
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    ids: dict[str, str] = {}
    for commit in case.history:
        if commit.branch:
            switch(root, commit.branch)
        if commit.merge:
            git(root, "merge", "-q", "--no-ff", "-m", commit.message, commit.merge)
        else:
            for path, text in commit.files.items():
                if text is None:
                    git(root, "rm", "-q", path)
                else:
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text, encoding="utf-8")
                    git(root, "add", path)
            git(root, "commit", "-q", "-m", commit.message)
        if commit.label:
            ids[commit.label] = git(root, "rev-parse", "HEAD").stdout.strip()
    if case.detached:
        git(root, "switch", "-q", "--detach")
    elif case.branch:
        switch(root, case.branch)
    config = case.config
    for label, commit_id in ids.items():
        config = config.replace("${" + label + "}", commit_id)
    (root / CONFIG_NAME).write_text(config, encoding="utf-8")
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


def _git_output(root: Path, *args: str) -> str:
    return git(root, *args).stdout.strip()


def test_a_case_can_have_a_history(tmp_path: Path) -> None:
    case = Case(
        name="history",
        config="version: 1\nanchor: ${anchor}\n",
        files={"b.md": "b\n"},
        findings=[],
        history=[
            Commit(message="one", files={"a.md": "a\n"}, label="anchor"),
            Commit(message="two", files={"a.md": None, "c.md": "c\n"}, branch="side"),
            Commit(message="three", files={"d.md": "d\n"}, branch="main"),
            Commit(message="merge side", merge="side"),
        ],
        branch="side",
    )
    root = build(tmp_path / "workspace", case)
    anchor = _git_output(root, "rev-list", "--max-parents=0", "HEAD")
    assert _git_output(root, "branch", "--show-current") == "side"
    assert _git_output(root, "log", "--format=%s", "--first-parent", "main") == "merge side\nthree\none"
    assert not (root / "a.md").exists()  # deleted on `side`, which is checked out
    assert (root / "b.md").read_text(encoding="utf-8") == "b\n"  # written after the history, uncommitted
    assert f"anchor: {anchor}" in (root / "docsys.yaml").read_text(encoding="utf-8")
    detached = build(
        tmp_path / "detached", Case(name="d", config="", files={}, findings=[], history=case.history, detached=True)
    )
    assert _git_output(detached, "branch", "--show-current") == ""


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
