"""`docsys seal` writes a frozen record's `hash:` seal, in the canonical form the
fixity check verifies. It refuses to overwrite a seal that no longer matches unless
`--reseal` says so, since re-sealing is a deliberate act; `--print` computes and
writes nothing; `--frozen` seals every frozen record of the workspace that has no
seal yet."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from docsys import exitcodes
from docsys.checks.hashes import check
from docsys.config import load_config
from docsys.seal import SealOutcome, sealed_text
from docsys.workspace import CONFIG_NAME

FROZEN = """\
---
title: A closed record
view: diachronic
provenance: {{ type: project, id: some-phase }}
status: {status}
---

Body of the record.
"""


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / CONFIG_NAME).write_text("version: 1\n", encoding="utf-8")
    return tmp_path


def record(root: Path, name: str, status: str = "done") -> Path:
    path = root / name
    path.write_text(FROZEN.format(status=status), encoding="utf-8")
    return path


def findings(root: Path) -> list[str]:
    return [finding.rule for finding in check(root, load_config(root))]


# --- the library ---------------------------------------------------------------------


def test_sealing_adds_the_hash_line_last_in_the_frontmatter() -> None:
    result = sealed_text(FROZEN.format(status="done"), reseal=False)
    assert result.outcome is SealOutcome.SEALED
    lines = result.text.split("\n")
    assert lines[5].startswith("hash: sha256:")
    assert lines[6] == "---"


def test_sealing_twice_changes_nothing() -> None:
    once = sealed_text(FROZEN.format(status="done"), reseal=False).text
    again = sealed_text(once, reseal=False)
    assert again.outcome is SealOutcome.UNCHANGED
    assert again.text == once


def test_a_changed_sealed_record_is_refused_without_reseal() -> None:
    sealed = sealed_text(FROZEN.format(status="done"), reseal=False).text
    edited = sealed + "A later edit.\n"
    refused = sealed_text(edited, reseal=False)
    assert refused.outcome is SealOutcome.REFUSED
    assert refused.text == edited


def test_reseal_replaces_the_seal() -> None:
    sealed = sealed_text(FROZEN.format(status="done"), reseal=False).text
    edited = sealed + "A later edit.\n"
    result = sealed_text(edited, reseal=True)
    assert result.outcome is SealOutcome.RESEALED
    assert result.text.count("hash:") == 1
    assert sealed_text(result.text, reseal=False).outcome is SealOutcome.UNCHANGED


def test_crlf_line_endings_are_kept() -> None:
    text = FROZEN.format(status="done").replace("\n", "\r\n")
    result = sealed_text(text, reseal=False)
    assert "\r\nhash: sha256:" in result.text
    assert result.text.replace("\r\n", "").count("\n") == 0


def test_a_document_without_frontmatter_is_refused() -> None:
    with pytest.raises(ValueError, match="no frontmatter"):
        sealed_text("No frontmatter here.\n", reseal=False)


# --- the command ---------------------------------------------------------------------


def test_a_sealed_file_passes_the_fixity_check(workspace: Path) -> None:
    record(workspace, "a.md")
    result = run_cli("seal", "a.md", cwd=workspace)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "sealed" in result.stdout
    assert "hashes/seal" not in findings(workspace)


def test_print_computes_and_writes_nothing(workspace: Path) -> None:
    path = record(workspace, "a.md")
    before = path.read_text(encoding="utf-8")
    result = run_cli("seal", "--print", "a.md", cwd=workspace)
    assert result.returncode == exitcodes.OK, result.stderr
    assert result.stdout.startswith("sha256:")
    assert result.stdout.rstrip().endswith("a.md")
    assert path.read_text(encoding="utf-8") == before


def test_the_printed_seal_is_the_one_written(workspace: Path) -> None:
    path = record(workspace, "a.md")
    printed = run_cli("seal", "--print", "a.md", cwd=workspace).stdout.split()[0]
    run_cli("seal", "a.md", cwd=workspace)
    assert f"hash: {printed}" in path.read_text(encoding="utf-8")


def test_a_changed_seal_is_refused_with_findings_exit_and_reseal_accepts_it(workspace: Path) -> None:
    path = record(workspace, "a.md")
    run_cli("seal", "a.md", cwd=workspace)
    path.write_text(path.read_text(encoding="utf-8") + "A later edit.\n", encoding="utf-8")
    refused = run_cli("seal", "a.md", cwd=workspace)
    assert refused.returncode == exitcodes.FINDINGS
    assert "--reseal" in refused.stdout
    assert findings(workspace) == ["hashes/seal"]
    accepted = run_cli("seal", "--reseal", "a.md", cwd=workspace)
    assert accepted.returncode == exitcodes.OK
    assert findings(workspace) == []


def test_frozen_seals_each_frozen_record_and_only_those(workspace: Path) -> None:
    record(workspace, "closed.md")
    draft = record(workspace, "draft.md", status="draft")
    result = run_cli("seal", "--frozen", cwd=workspace)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "hash:" in (workspace / "closed.md").read_text(encoding="utf-8")
    assert "hash:" not in draft.read_text(encoding="utf-8")
    assert "1 record" in result.stdout


def test_frozen_leaves_an_excluded_record_alone(workspace: Path) -> None:
    (workspace / CONFIG_NAME).write_text("version: 1\nscope:\n  exclude:\n    old/: kept as found\n", encoding="utf-8")
    (workspace / "old").mkdir()
    old = record(workspace, "old/a.md")
    run_cli("seal", "--frozen", cwd=workspace)
    assert "hash:" not in old.read_text(encoding="utf-8")


def test_frozen_with_paths_is_a_usage_error(workspace: Path) -> None:
    record(workspace, "a.md")
    assert run_cli("seal", "--frozen", "a.md", cwd=workspace).returncode == exitcodes.ERROR


def test_no_path_and_no_frozen_is_a_usage_error(workspace: Path) -> None:
    result = run_cli("seal", cwd=workspace)
    assert result.returncode == exitcodes.ERROR
    assert "--frozen" in result.stderr


def test_a_missing_file_is_an_error_naming_it(workspace: Path) -> None:
    result = run_cli("seal", "nope.md", cwd=workspace)
    assert result.returncode == exitcodes.ERROR
    assert "nope.md" in result.stderr
