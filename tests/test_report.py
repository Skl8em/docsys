"""The report: `docsys report` lists each exclusion of the scope with its reason and
the number of documents it leaves out, and counts the documents in scope, so the gap
between the documents a project has and the documents the framework governs is
visible and shrinks over time. `--documents` adds the excluded documents one by one.
It is not a gate: it exits `0` however many documents are excluded."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from docsys import exitcodes
from docsys.config import Scope
from docsys.documents import Exclusion, Excluded, excluded, exclusions
from docsys.workspace import CONFIG_NAME


def write(root: Path, path: str, text: str = "") -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    return root


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


# --- the library: which documents are excluded, and why ------------------------------


def test_with_nothing_excluded_no_document_is_listed(repo: Path) -> None:
    write(repo, "a.md")
    assert excluded(repo, Scope(include=[], exclude={})) == []


def test_an_excluded_document_is_listed_with_its_pattern_and_reason(repo: Path) -> None:
    write(repo, "legacy/old.md")
    write(repo, "docs/new.md")
    scope = Scope(include=[], exclude={"legacy/": "predates docsys; awaiting review"})
    assert excluded(repo, scope) == [Excluded("legacy/old.md", "legacy/", "predates docsys; awaiting review")]


def test_a_document_included_back_is_no_longer_excluded(repo: Path) -> None:
    write(repo, "legacy/old.md")
    write(repo, "legacy/revised.md")
    scope = Scope(include=["legacy/revised.md"], exclude={"legacy/": "predates docsys"})
    assert [item.path for item in excluded(repo, scope)] == ["legacy/old.md"]


def test_the_first_matching_exclusion_gives_the_reason(repo: Path) -> None:
    write(repo, "legacy/transcripts/a.md")
    scope = Scope(include=[], exclude={"legacy/": "predates docsys", "**/transcripts/": "raw output"})
    assert excluded(repo, scope) == [Excluded("legacy/transcripts/a.md", "legacy/", "predates docsys")]


def test_the_listing_is_in_path_order(repo: Path) -> None:
    for path in ("z/b.md", "a/z.md", "z/a.md"):
        write(repo, path)
    scope = Scope(include=[], exclude={"z/": "later", "a/": "first"})
    assert [item.path for item in excluded(repo, scope)] == ["a/z.md", "z/a.md", "z/b.md"]


def test_each_exclusion_is_listed_with_its_reason_and_its_count(repo: Path) -> None:
    for path in ("legacy/a.md", "legacy/b.md", "docs/new.md"):
        write(repo, path)
    scope = Scope(include=["legacy/b.md"], exclude={"legacy/": "predates docsys", "gone/": "removed"})
    assert exclusions(repo, scope) == [Exclusion("legacy/", "predates docsys", 1), Exclusion("gone/", "removed", 0)]


def test_a_document_counts_for_the_first_exclusion_only(repo: Path) -> None:
    write(repo, "legacy/transcripts/a.md")
    scope = Scope(include=[], exclude={"legacy/": "predates docsys", "**/transcripts/": "raw output"})
    assert exclusions(repo, scope) == [Exclusion("legacy/", "predates docsys", 1), Exclusion("**/transcripts/", "raw output", 0)]


def test_excluded_documents_inside_an_ignored_folder_are_counted(repo: Path) -> None:
    write(repo, ".gitignore", ".venv/\n")
    write(repo, ".venv/lib/x.md")
    assert exclusions(repo, Scope(include=[], exclude={".venv/": "environment"})) == [Exclusion(".venv/", "environment", 1)]


# --- the command ----------------------------------------------------------------------


def test_report_lists_each_exclusion_with_its_reason_and_its_count(repo: Path) -> None:
    config = "version: 1\nscope:\n  exclude:\n    legacy/: predates docsys; awaiting review\n"
    (repo / CONFIG_NAME).write_text(config, encoding="utf-8")
    write(repo, "legacy/a.md")
    write(repo, "legacy/b.md")
    write(repo, "README.md")
    result = run_cli("report", cwd=repo)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "legacy/: predates docsys; awaiting review (2 documents)" in result.stdout
    assert "legacy/a.md" not in result.stdout
    assert "README.md" not in result.stdout
    assert "2 documents excluded, 1 in scope" in result.stdout


def test_report_with_documents_lists_each_excluded_document(repo: Path) -> None:
    config = "version: 1\nscope:\n  exclude:\n    legacy/: predates docsys; awaiting review\n"
    (repo / CONFIG_NAME).write_text(config, encoding="utf-8")
    write(repo, "legacy/a.md")
    write(repo, "README.md")
    result = run_cli("report", "--documents", cwd=repo)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "legacy/a.md: predates docsys; awaiting review (excluded by `legacy/`)" in result.stdout
    assert "README.md" not in result.stdout


def test_report_with_nothing_excluded_says_so(repo: Path) -> None:
    (repo / CONFIG_NAME).write_text("version: 1\n", encoding="utf-8")
    write(repo, "README.md")
    result = run_cli("report", cwd=repo)
    assert result.returncode == exitcodes.OK
    assert "no document is excluded, 1 in scope" in result.stdout


def test_report_says_one_document_in_the_singular(repo: Path) -> None:
    (repo / CONFIG_NAME).write_text("version: 1\nscope:\n  exclude:\n    old.md: not yet\n", encoding="utf-8")
    write(repo, "old.md")
    result = run_cli("report", cwd=repo)
    assert "old.md: not yet (1 document)" in result.stdout
    assert "1 document excluded, 0 in scope" in result.stdout


def test_report_without_a_workspace_is_a_configuration_error(tmp_path: Path) -> None:
    result = run_cli("report", cwd=tmp_path)
    assert result.returncode == exitcodes.ERROR
    assert "fix:" in result.stderr


def test_report_outside_git_works_like_anywhere(tmp_path: Path) -> None:
    (tmp_path / CONFIG_NAME).write_text("version: 1\n", encoding="utf-8")
    write(tmp_path, "README.md")
    result = run_cli("report", cwd=tmp_path)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "no document is excluded, 1 in scope" in result.stdout
