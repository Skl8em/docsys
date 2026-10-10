"""The code meets the tools the editor runs: basedpyright (strict, `Any` refused)
and ruff (lint and format), configured in `pyproject.toml`. The tests run the
copies locked in this environment, the ones the editor's extensions find, so the
editor and the test suite report the same thing."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(["basedpyright", "--project", str(ROOT)], id="basedpyright"),
        pytest.param(["ruff", "check", str(ROOT)], id="ruff check"),
        pytest.param(["ruff", "format", "--check", str(ROOT)], id="ruff format"),
    ],
)
def test_the_tool_reports_nothing(command: list[str]) -> None:
    tool = Path(sys.executable).parent / command[0]
    result = subprocess.run([str(tool), *command[1:]], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
