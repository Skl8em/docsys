"""Every function in the package and its tests is statically typed: `mypy` in
strict mode, configured in `pyproject.toml`, reports nothing."""
from pathlib import Path

from mypy import api

ROOT = Path(__file__).resolve().parent.parent


def test_mypy_strict_reports_nothing() -> None:
    stdout, stderr, status = api.run(["--config-file", str(ROOT / "pyproject.toml"), str(ROOT / "src"), str(ROOT / "tests")])
    assert status == 0, stdout + stderr
