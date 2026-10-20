"""The opt-in tools: external commands that `docsys.yaml` names in `tools:` and
`docsys check` runs after its own checks, from the workspace. Their output is
kept and shown under their name; a tool that exits non-zero, or that is not
installed, is a finding like any other — `tools/failed`, `tools/missing` — whose
severity the project can change. A project with no `tools:` runs none."""

import json
import os
import subprocess
import sys
from pathlib import Path

from docsys import exitcodes
from docsys.config import load_config
from docsys.runner import run
from docsys.workspace import CONFIG_NAME

FIELDS = (
    "---\ntitle: Fixture\nforce: explain\nintention: state\nconstitutive: no\nview: synchronic\n"
    "provenance: { type: function, id: steering }\naudience: [contributor]\nreader: H+M\nstatus: draft\n"
)
README = FIELDS + "axis: provenance\ndominant-community: writing\n---\n\nBody.\n"


def python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def workspace(root: Path, tools: list[dict[str, object]], extra: str = "") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    (root / CONFIG_NAME).write_text(f"version: 1\n{extra}tools: {json.dumps(tools)}\n", encoding="utf-8")
    (root / "README.md").write_text(README, encoding="utf-8")
    return root


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


# --- the library --------------------------------------------------------------------


def test_a_tool_that_succeeds_reports_nothing_and_its_output_is_kept(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", [{"name": "say", "command": python("print('all well')")}])
    report = run(root, load_config(root))
    assert report.errors == []
    assert [(name, output.strip()) for name, output in report.tool_outputs] == [("say", "all well")]


def test_a_tool_runs_from_the_workspace(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", [{"name": "where", "command": python("import os; print(os.getcwd())")}])
    [(_, output)] = run(root, load_config(root)).tool_outputs
    assert Path(output.strip()).resolve() == root.resolve()


def test_a_tool_that_exits_non_zero_is_an_error_naming_it_and_the_fix(tmp_path: Path) -> None:
    command = python("import sys; print('3 problems'); print('and more', file=sys.stderr); sys.exit(4)")
    root = workspace(tmp_path / "p", [{"name": "lint", "command": command}])
    report = run(root, load_config(root))
    [finding] = report.errors
    assert (finding.rule, finding.path) == ("tools/failed", CONFIG_NAME)
    assert "`lint`" in finding.message
    assert "4" in finding.message
    assert finding.fix
    [(_, output)] = report.tool_outputs
    assert "3 problems" in output
    assert "and more" in output


def test_a_tool_that_is_not_installed_is_an_error_saying_how_to_install_it(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", [{"name": "lint", "command": ["no-such-tool-anywhere", "--flag"]}])
    report = run(root, load_config(root))
    [finding] = report.errors
    assert finding.rule == "tools/missing"
    assert "`no-such-tool-anywhere`" in finding.message
    assert "`lint`" in finding.message
    assert "fix:" in str(finding)
    assert report.tool_outputs == []


def test_a_failing_tool_does_not_stop_the_next_one(tmp_path: Path) -> None:
    tools = [
        {"name": "first", "command": python("import sys; sys.exit(1)")},
        {"name": "second", "command": python("print('ran')")},
    ]
    root = workspace(tmp_path / "p", tools)
    report = run(root, load_config(root))
    assert [name for name, _ in report.tool_outputs] == ["first", "second"]
    assert [f.rule for f in report.errors] == ["tools/failed"]


def test_the_severity_of_a_tool_failure_can_be_changed(tmp_path: Path) -> None:
    root = workspace(
        tmp_path / "p",
        [{"name": "lint", "command": python("import sys; sys.exit(1)")}],
        extra="rules:\n  tools/failed: warning\n",
    )
    report = run(root, load_config(root))
    assert report.errors == []
    assert [f.rule for f in report.warnings] == ["tools/failed"]


# --- the command --------------------------------------------------------------------


def test_check_shows_each_tool_under_its_name_and_exits_1_when_one_fails(tmp_path: Path) -> None:
    tools = [
        {"name": "lint", "command": python("print('lint says no'); raise SystemExit(1)")},
        {"name": "spell", "command": python("print('spell says yes')")},
    ]
    root = workspace(tmp_path / "p", tools)
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.FINDINGS
    assert "=== lint ===\nlint says no\n" in result.stdout
    assert "=== spell ===\nspell says yes\n" in result.stdout
    assert result.stdout.index("=== lint ===") < result.stdout.index("=== spell ===")
    assert f"{CONFIG_NAME}:1: tools/failed:" in result.stdout
    assert "docsys check failed: 1 error" in result.stdout


def test_check_passes_when_every_tool_does(tmp_path: Path) -> None:
    root = workspace(tmp_path / "p", [{"name": "say", "command": python("print('fine')")}])
    result = run_cli("check", cwd=root)
    assert result.returncode == exitcodes.OK, result.stdout + result.stderr
    assert "=== say ===\nfine\n" in result.stdout
