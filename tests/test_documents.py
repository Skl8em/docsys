"""The documents of a workspace: its Markdown files that git tracks or would track —
committed or not, never ignored, never inside a submodule — that the scope
governs. Git is what tells a project's own files from its build output and its
virtual environments, so a workspace outside git is refused rather than walked."""

import subprocess
from pathlib import Path

import pytest

from docsys.config import Scope
from docsys.documents import DocumentsError, documents

EVERYTHING = Scope(include=[], exclude={})


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def write(root: Path, path: str, text: str = "") -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    return root


def test_committed_and_uncommitted_documents_are_listed_in_path_order(repo: Path) -> None:
    write(repo, "b.md")
    write(repo, "a/z.md")
    git(repo, "add", "b.md")
    assert documents(repo, EVERYTHING) == ["a/z.md", "b.md"]


def test_a_tracked_document_deleted_from_the_worktree_is_not_listed(repo: Path) -> None:
    write(repo, "gone.md")
    git(repo, "add", "gone.md")
    (repo / "gone.md").unlink()
    assert documents(repo, EVERYTHING) == []


def test_ignored_files_and_other_extensions_are_not_documents(repo: Path) -> None:
    write(repo, ".gitignore", ".venv/\n")
    write(repo, ".venv/lib/site-packages/pkg/README.md")
    write(repo, "notes.txt")
    write(repo, "README.md")
    assert documents(repo, EVERYTHING) == ["README.md"]


def test_the_scope_filters_the_documents(repo: Path) -> None:
    write(repo, "legacy/old.md")
    write(repo, "legacy/revised.md")
    write(repo, "docs/new.md")
    scope = Scope(include=["legacy/revised.md"], exclude={"legacy/": "predates docsys"})
    assert documents(repo, scope) == ["docs/new.md", "legacy/revised.md"]


def test_a_workspace_below_the_repository_root_lists_its_own_documents(repo: Path) -> None:
    write(repo, "outside.md")
    write(repo, "project/docs/a.md")
    assert documents(repo / "project", EVERYTHING) == ["docs/a.md"]


def test_a_workspace_outside_git_is_refused_with_a_fix(tmp_path: Path) -> None:
    write(tmp_path, "README.md")
    with pytest.raises(DocumentsError) as caught:
        documents(tmp_path, EVERYTHING)
    message = str(caught.value)
    assert str(tmp_path) in message
    assert "fix:" in message
