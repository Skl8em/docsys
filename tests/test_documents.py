"""The documents of a workspace: its Markdown files, anywhere under it but inside
`.git`, that the scope governs. The walk consults neither git's index nor
`.gitignore`, follows no symlink, and does not enter a folder the scope leaves out
wholly, so a build folder or a virtual environment costs nothing. A workspace
outside git is a workspace like another."""

import os
import subprocess
from pathlib import Path

import pytest

from docsys.config import Scope
from docsys.documents import documents, files

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


def test_a_deleted_document_is_not_listed(repo: Path) -> None:
    write(repo, "gone.md")
    git(repo, "add", "gone.md")
    (repo / "gone.md").unlink()
    assert documents(repo, EVERYTHING) == []


def test_an_ignored_markdown_file_is_a_document(repo: Path) -> None:
    write(repo, ".gitignore", ".venv/\n")
    write(repo, ".venv/lib/pkg/README.md")
    write(repo, "notes.txt")
    assert documents(repo, EVERYTHING) == [".venv/lib/pkg/README.md"]


def test_an_untracked_document_is_a_document(repo: Path) -> None:
    write(repo, "new.md")
    assert documents(repo, EVERYTHING) == ["new.md"]


def test_a_file_inside_git_is_not_a_document(repo: Path) -> None:
    write(repo, ".git/notes.md")
    write(repo, "a.md")
    assert documents(repo, EVERYTHING) == ["a.md"]


def test_a_submodules_files_are_documents(repo: Path) -> None:
    write(repo, "sub/.git", "gitdir: ../.git/modules/sub\n")
    write(repo, "sub/README.md")
    assert documents(repo, EVERYTHING) == ["sub/README.md"]


def test_a_symlinked_folder_is_not_followed(repo: Path) -> None:
    write(repo, "real/a.md")
    (repo / "alias").symlink_to(repo / "real", target_is_directory=True)
    assert documents(repo, EVERYTHING) == ["real/a.md"]


def test_a_symlinked_file_is_not_a_document(repo: Path) -> None:
    write(repo, "a.md")
    (repo / "b.md").symlink_to(repo / "a.md")
    assert documents(repo, EVERYTHING) == ["a.md"]


def test_a_workspace_outside_git_lists_its_documents(tmp_path: Path) -> None:
    write(tmp_path, "README.md")
    write(tmp_path, "docs/a.md")
    assert documents(tmp_path, EVERYTHING) == ["README.md", "docs/a.md"]


def test_a_folder_the_scope_leaves_out_wholly_is_not_entered(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write(repo, ".venv/lib/x.md")
    write(repo, "docs/a.md")
    entered: list[str] = []
    scandir = os.scandir

    def spy(path: str | os.PathLike[str] = ".") -> "os._ScandirIterator[str]":
        entered.append(os.fspath(path))
        return scandir(path)

    monkeypatch.setattr(os, "scandir", spy)
    scope = Scope(include=[], exclude={".venv/": "environment"})
    assert documents(repo, scope) == ["docs/a.md"]
    assert not any(".venv" in path for path in entered)


def test_a_folder_an_inclusion_reaches_into_is_entered(repo: Path) -> None:
    write(repo, "legacy/old.md")
    write(repo, "legacy/deep/revised.md")
    scope = Scope(include=["legacy/**/revised.md"], exclude={"legacy/": "predates docsys"})
    assert documents(repo, scope) == ["legacy/deep/revised.md"]


def test_files_lists_every_kind_of_file_under_a_folder(repo: Path) -> None:
    write(repo, ".gitignore", ".venv/\n")
    write(repo, "phases/a/README.md")
    write(repo, "phases/a/data.yaml")
    write(repo, ".venv/x.md")
    write(repo, ".git/HEAD.md")
    assert files(repo, under="phases") == ["phases/a/README.md", "phases/a/data.yaml"]
    assert ".git/HEAD.md" not in files(repo)


def test_files_can_be_narrowed_by_a_suffix(repo: Path) -> None:
    write(repo, "a.md")
    write(repo, "b.yaml")
    assert files(repo, suffix=".yaml") == ["b.yaml"]
