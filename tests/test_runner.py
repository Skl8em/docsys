"""The runner: `docsys check` runs every check the configuration turns on, in a fixed
order, gives each finding the severity its rule has in this workspace, prints what
is not off, and exits `0` when nothing is an error, `1` when something is, and `2`
when the run cannot happen."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from docsys import exitcodes
from docsys.config import load_config
from docsys.runner import run
from docsys.workspace import CONFIG_NAME

FIELDS = (
    "---\ntitle: Fixture\nforce: explain\nintention: state\nconstitutive: no\nview: synchronic\n"
    "provenance: { type: function, id: steering }\naudience: [contributor]\nreader: H+M\nstatus: draft\n"
)
ROOT = FIELDS + "axis: provenance\ndominant-community: writing\n---\n\n"  # the root document carries two more
DOCUMENT = FIELDS + "---\n\n"
CLEAN = ROOT + "Body.\n"
BROKEN = ROOT + "A [link](missing.md).\n"
BROKEN_LINE = 15  # twelve lines of frontmatter and fence, a blank line, then the body


def workspace(root: Path, config: str, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / CONFIG_NAME).write_text(config, encoding="utf-8")
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    return root


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


# --- the library: a report of errors and warnings ----------------------------------


def test_a_workspace_that_breaks_no_rule_reports_nothing(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\n", {"README.md": CLEAN})
    report = run(root, load_config(root))
    assert report.errors == []
    assert report.warnings == []


def test_a_broken_link_is_an_error_by_default(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\n", {"README.md": BROKEN})
    report = run(root, load_config(root))
    assert [(f.rule, f.path, f.line) for f in report.errors] == [("links/resolve", "README.md", BROKEN_LINE)]
    assert report.warnings == []


def test_the_configuration_turns_a_rule_into_a_warning(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\nrules:\n  links/resolve: warning\n", {"README.md": BROKEN})
    report = run(root, load_config(root))
    assert report.errors == []
    assert [f.rule for f in report.warnings] == ["links/resolve"]


def test_the_configuration_turns_a_rule_off(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\nrules:\n  links/resolve: off\n", {"README.md": BROKEN})
    report = run(root, load_config(root))
    assert report.errors == []
    assert report.warnings == []


def test_a_rule_that_is_off_by_default_reports_once_turned_on(tmp_path: Path) -> None:
    frozen = (
        CLEAN.replace("status: draft", "status: done")
        .replace("view: synchronic", "view: diachronic")
        .replace("provenance: { type: function, id: steering }", "provenance: { type: project, id: p1 }")
    )
    config = "version: 1\nrules:\n  hashes/unsealed: error\n"
    root = workspace(tmp_path / "p", config, {"README.md": frozen})
    assert [f.rule for f in run(root, load_config(root)).errors] == ["hashes/unsealed"]
    off = workspace(tmp_path / "q", "version: 1\n", {"README.md": frozen})
    assert run(off, load_config(off)).errors == []


def test_a_check_runs_only_when_its_section_is_configured(tmp_path: Path) -> None:
    phases = (
        "phases:\n  ledger: state/phases.yaml\n  root: records\n  folder: 'phase-{number:02d}-{name}'\n"
        "  field: '{number:02d}-{name}'\n  markers: {done: done, current: current, planned: planned}\n"
        "  tables:\n    - {path: README.md, row: '^\\| (?P<number>\\d+) \\| (?P<marker>\\w+)'}\n"
        "  status: {path: README.md, line: '^Phase (?P<number>\\d+)'}\n  mention: 'Phase (?P<number>\\d+)'\n"
    )
    configured = workspace(tmp_path / "with", "version: 1\n" + phases, {"README.md": CLEAN})
    assert [f.rule for f in run(configured, load_config(configured)).errors] == ["ledger/missing", "phase-state/ledger"]
    bare = workspace(tmp_path / "without", "version: 1\n", {"README.md": CLEAN})
    assert run(bare, load_config(bare)).errors == []


def test_findings_come_in_the_order_of_the_checks_then_of_the_path(tmp_path: Path) -> None:
    broken = DOCUMENT + "A [link](missing.md).\n"
    files = {"README.md": CLEAN, "b.md": broken, "a.md": broken, "c.md": "no frontmatter [x](gone.md)\n"}
    root = workspace(tmp_path / "p", "version: 1\n", files)
    order = [(f.rule, f.path) for f in run(root, load_config(root)).errors]
    assert order == [
        ("links/resolve", "a.md"),
        ("links/resolve", "b.md"),
        ("links/resolve", "c.md"),
        ("frontmatter/missing-block", "c.md"),
    ]


# --- the command: output and exit codes ---------------------------------------------


def test_check_exits_0_and_says_it_passed(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\n", {"README.md": CLEAN})
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "passed" in result.stdout


def test_check_exits_1_and_prints_each_finding_with_its_fix(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\n", {"README.md": BROKEN})
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.FINDINGS
    lines = result.stdout.splitlines()
    assert f"README.md:{BROKEN_LINE}: links/resolve: `missing.md` points to no file or folder — fix:" in lines[0]
    assert "failed" in result.stdout
    assert "1 error" in result.stdout


def test_check_prints_warnings_and_still_passes(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\nrules:\n  links/resolve: warning\n", {"README.md": BROKEN})
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.OK
    assert f"README.md:{BROKEN_LINE}: links/resolve:" in result.stdout
    assert "1 warning" in result.stdout
    assert "passed" in result.stdout


def test_check_with_a_rule_off_prints_nothing_of_it(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\nrules:\n  links/resolve: off\n", {"README.md": BROKEN})
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.OK
    assert "links/resolve" not in result.stdout


def test_check_with_a_rule_that_does_not_exist_is_a_configuration_error(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", "version: 1\nrules:\n  links/nothing: off\n", {"README.md": CLEAN})
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.ERROR
    assert "docsys.yaml: `rules.links/nothing`" in result.stderr
    assert "fix:" in result.stderr


def test_check_outside_git_is_an_error_naming_the_fix(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / CONFIG_NAME).write_text("version: 1\n", encoding="utf-8")
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.ERROR
    assert "git" in result.stderr
    assert "fix:" in result.stderr


@pytest.mark.parametrize("scope", ["", "scope: {exclude: {README.md: not yet revised}}\n"])
def test_an_excluded_document_is_not_checked(tmp_path: Path, scope: str) -> None:
    root = workspace(tmp_path / "p", "version: 1\n" + scope, {"README.md": BROKEN})
    expected = exitcodes.OK if scope else exitcodes.FINDINGS
    assert run_cli("check", cwd=root).returncode == expected
