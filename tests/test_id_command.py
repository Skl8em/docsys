"""`docsys id` mints a ULID and prints it: chronological by default or with `--at`,
ordinal with `--order`, and as a filename stem with `--slug`. It needs no workspace:
an identifier is minted before the document that carries it exists."""

import os
import subprocess
import sys
from pathlib import Path

from docsys import exitcodes
from docsys.ulid import is_ulid, timestamp_of


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


def test_it_prints_a_ulid_outside_any_workspace(tmp_path: Path) -> None:
    result = run_cli("id", cwd=tmp_path)
    assert result.returncode == exitcodes.OK, result.stderr
    assert is_ulid(result.stdout.strip())
    assert result.stderr == ""


def test_at_encodes_the_date(tmp_path: Path) -> None:
    result = run_cli("id", "--at", "2026-08-01", cwd=tmp_path)
    assert timestamp_of(result.stdout.strip()) == 1_785_542_400_000


def test_order_encodes_the_sort_key(tmp_path: Path) -> None:
    result = run_cli("id", "--order", "8500000", cwd=tmp_path)
    assert timestamp_of(result.stdout.strip()) == 8_500_000


def test_slug_is_appended_as_a_filename_stem(tmp_path: Path) -> None:
    result = run_cli("id", "--slug", "gerund-naming", cwd=tmp_path)
    ulid, _, slug = result.stdout.strip().partition("-")
    assert is_ulid(ulid)
    assert slug == "gerund-naming"


def test_at_and_order_are_exclusive(tmp_path: Path) -> None:
    result = run_cli("id", "--at", "2026-08-01", "--order", "1", cwd=tmp_path)
    assert result.returncode == exitcodes.ERROR
    assert result.stdout == ""


def test_an_unparseable_date_is_refused_with_the_usage_exit_code(tmp_path: Path) -> None:
    result = run_cli("id", "--at", "yesterday", cwd=tmp_path)
    assert result.returncode == exitcodes.ERROR
    assert "yesterday" in result.stderr
    assert result.stdout == ""


def test_an_order_outside_48_bits_is_refused(tmp_path: Path) -> None:
    result = run_cli("id", "--order", str(2**48), cwd=tmp_path)
    assert result.returncode == exitcodes.ERROR
    assert "48-bit" in result.stderr
    assert result.stdout == ""
