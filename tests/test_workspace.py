"""The workspace: the project root `docsys` works in, found from the nearest
`docsys.yaml`, or given explicitly — never assumed from the current directory or
from where the package is installed."""
import os
import subprocess
import sys

import pytest

from docsys.workspace import CONFIG_NAME, WorkspaceError, find_workspace, resolve_workspace


def make_workspace(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / CONFIG_NAME).write_text("version: 1\n", encoding="utf-8")
    return path


def test_the_start_directory_holds_the_config(tmp_path):
    root = make_workspace(tmp_path / "project")
    assert find_workspace(root) == root


def test_an_ancestor_holds_the_config(tmp_path):
    root = make_workspace(tmp_path / "project")
    deep = root / "docs" / "build" / "know"
    deep.mkdir(parents=True)
    assert find_workspace(deep) == root


def test_a_file_starts_the_search_from_its_directory(tmp_path):
    root = make_workspace(tmp_path / "project")
    doc = root / "docs" / "README.md"
    doc.parent.mkdir()
    doc.write_text("", encoding="utf-8")
    assert find_workspace(doc) == root


def test_the_nearest_config_wins(tmp_path):
    outer = make_workspace(tmp_path / "outer")
    inner = make_workspace(outer / "vendored" / "inner")
    assert find_workspace(inner / ".") == inner


def test_no_config_anywhere_is_an_error_naming_the_start_and_the_fix(tmp_path):
    start = tmp_path / "nowhere"
    start.mkdir()
    with pytest.raises(WorkspaceError) as caught:
        find_workspace(start)
    message = str(caught.value)
    assert str(start) in message
    assert "fix:" in message


def test_an_explicit_workspace_must_hold_the_config(tmp_path):
    with pytest.raises(WorkspaceError) as caught:
        resolve_workspace(start=tmp_path, explicit=tmp_path)
    assert "fix:" in str(caught.value)


def test_an_explicit_workspace_is_used_as_given(tmp_path):
    root = make_workspace(tmp_path / "project")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert resolve_workspace(start=elsewhere, explicit=root) == root


def test_importing_the_package_does_not_change_the_current_directory(tmp_path):
    code = (
        "import os, pkgutil, importlib, docsys\n"
        "before = os.getcwd()\n"
        "for m in pkgutil.walk_packages(docsys.__path__, 'docsys.'):\n"
        "    if m.name != 'docsys.__main__':  # the entry point, which runs the CLI by design\n"
        "        importlib.import_module(m.name)\n"
        "assert os.getcwd() == before, os.getcwd()\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def run_cli(*args, cwd):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


def test_check_outside_any_workspace_is_a_configuration_error(tmp_path):
    result = run_cli("check", cwd=tmp_path)
    assert result.returncode == 2
    assert "fix:" in result.stderr


def test_check_with_an_explicit_workspace_finds_it_from_anywhere(tmp_path):
    root = make_workspace(tmp_path / "project")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_cli("check", "--workspace", str(root), cwd=elsewhere)
    assert str(root) in result.stdout + result.stderr
