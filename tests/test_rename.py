"""`docsys rename OLD NEW` moves a file or folder and rewrites, in the workspace's
documents, the target of every relative link that pointed at the moved path, or at
anything under it, and the moved documents' own links for their new depth.
Anchors, link titles and the way a link was written (`./`, a trailing `/`) are kept,
and a link the move does not affect is not touched, whatever its form.
It moves with `git mv` when git tracks the path and by plain rename otherwise, and
it refuses before changing anything when the move cannot be made."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from docsys import exitcodes
from docsys.checks.links import check
from docsys.config import Scope, load_config
from docsys.rename import RenameError, rename
from docsys.workspace import CONFIG_NAME

NO_SCOPE = Scope(include=[], exclude={})


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def write(root: Path, path: str, text: str = "") -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def read(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    write(tmp_path, CONFIG_NAME, "version: 1\n")
    return tmp_path


def dead_links(root: Path) -> list[str]:
    return [f"{f.path}: {f.message}" for f in check(root, load_config(root))]


# --- links --------------------------------------------------------------------------


def test_an_inbound_link_follows_the_moved_file(repo: Path) -> None:
    write(repo, "a/old.md", "# Old\n")
    write(repo, "b/page.md", "See [old](../a/old.md).\n")
    rename(repo, NO_SCOPE, "a/old.md", "c/deep/new.md")
    assert read(repo, "b/page.md") == "See [old](../c/deep/new.md).\n"
    assert dead_links(repo) == []


def test_anchor_title_and_dot_slash_are_kept(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "sub/page.md", '[a](../old.md#part) [b](../old.md "A title") [c](../old.md#x "T")\n')
    write(repo, "page.md", "[d](./old.md)\n")
    rename(repo, NO_SCOPE, "old.md", "sub/new.md")
    assert read(repo, "sub/page.md") == '[a](new.md#part) [b](new.md "A title") [c](new.md#x "T")\n'
    assert read(repo, "page.md") == "[d](./sub/new.md)\n"


def test_the_moved_document_keeps_its_outbound_links_working(repo: Path) -> None:
    write(repo, "a/doc.md", "[sibling](other.md) [up](../top.md) [self](doc.md)\n")
    write(repo, "a/other.md")
    write(repo, "top.md")
    rename(repo, NO_SCOPE, "a/doc.md", "x/y/doc.md")
    assert read(repo, "x/y/doc.md") == "[sibling](../../a/other.md) [up](../../top.md) [self](doc.md)\n"
    assert dead_links(repo) == []


def test_a_folder_move_rewrites_links_to_the_folder_and_into_it_but_not_among_its_files(repo: Path) -> None:
    write(repo, "old/one.md", "[two](two.md) [out](../top.md)\n")
    write(repo, "old/two.md")
    write(repo, "top.md", "[dir](old/) [one](old/one.md#h) [dir2](./old)\n")
    rename(repo, NO_SCOPE, "old", "deep/new")
    assert read(repo, "deep/new/one.md") == "[two](two.md) [out](../../top.md)\n"
    assert read(repo, "top.md") == "[dir](deep/new/) [one](deep/new/one.md#h) [dir2](./deep/new)\n"
    assert dead_links(repo) == []


def test_a_link_the_move_does_not_affect_is_not_normalised(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "keep.md")
    write(repo, "page.md", "[k](docs/../keep.md) [o](old.md)\n")
    rename(repo, NO_SCOPE, "old.md", "new.md")
    assert read(repo, "page.md") == "[k](docs/../keep.md) [o](new.md)\n"


def test_web_anchor_and_placeholder_links_are_left_alone(repo: Path) -> None:
    write(repo, "old.md")
    text = "[w](https://x.org/old.md) [h](#old.md) [m](mailto:a@b.c) [p](<path>) [t](…/old.md)\n"
    write(repo, "page.md", text)
    rename(repo, NO_SCOPE, "old.md", "new.md")
    assert read(repo, "page.md") == text


def test_a_document_the_scope_excludes_is_not_rewritten(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "theory/t.md", "[o](../old.md)\n")
    scope = Scope(include=[], exclude={"theory/": "not a framework document"})
    rename(repo, scope, "old.md", "new.md")
    assert read(repo, "theory/t.md") == "[o](../old.md)\n"


def test_a_sealed_record_is_rewritten_and_reported_as_needing_a_new_seal(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "rec.md", "---\ntitle: R\nhash: sha256:abc\n---\n\n[o](old.md)\n")
    result = rename(repo, NO_SCOPE, "old.md", "new.md")
    assert "[o](new.md)" in read(repo, "rec.md")
    assert result.stale_seals == ["rec.md"]


# --- the move -----------------------------------------------------------------------


def test_the_result_counts_the_links_and_files_it_rewrote(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "a.md", "[1](old.md) [2](old.md)\n")
    write(repo, "b.md", "[3](old.md)\n")
    result = rename(repo, NO_SCOPE, "old.md", "new.md")
    assert result.rewritten == {"a.md": 2, "b.md": 1}


def test_a_tracked_file_is_moved_with_git_mv(repo: Path) -> None:
    write(repo, "old.md")
    git(repo, "add", "old.md")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "x")
    rename(repo, NO_SCOPE, "old.md", "new.md")
    assert "R  old.md -> new.md" in git(repo, "status", "--porcelain").splitlines()


def test_an_untracked_file_is_moved_in_place(repo: Path) -> None:
    write(repo, "old.md")
    rename(repo, NO_SCOPE, "old.md", "sub/new.md")
    assert not (repo / "old.md").exists()
    assert (repo / "sub/new.md").is_file()


def test_a_workspace_outside_git_is_accepted(tmp_path: Path) -> None:
    write(tmp_path, "old.md")
    write(tmp_path, "page.md", "[o](old.md)\n")
    rename(tmp_path, NO_SCOPE, "old.md", "new.md")
    assert read(tmp_path, "page.md") == "[o](new.md)\n"


def test_dry_run_changes_nothing_and_counts(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "page.md", "[o](old.md)\n")
    result = rename(repo, NO_SCOPE, "old.md", "new.md", dry_run=True)
    assert result.rewritten == {"page.md": 1}
    assert (repo / "old.md").exists()
    assert not (repo / "new.md").exists()
    assert read(repo, "page.md") == "[o](old.md)\n"


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        pytest.param("missing.md", "new.md", "missing.md", id="OLD does not exist"),
        pytest.param("old.md", "taken.md", "taken.md", id="NEW exists"),
        pytest.param("dir", "dir/inside", "inside itself", id="NEW inside OLD"),
        pytest.param("old.md", "../outside.md", "outside", id="NEW outside the workspace"),
        pytest.param(".git", "elsewhere", ".git", id="the git folder"),
    ],
)
def test_a_move_that_cannot_be_made_is_refused_before_anything_changes(
    repo: Path, old: str, new: str, message: str
) -> None:
    write(repo, "old.md")
    write(repo, "taken.md")
    write(repo, "dir/a.md")
    write(repo, "page.md", "[o](old.md)\n")
    with pytest.raises(RenameError, match=message):
        rename(repo, NO_SCOPE, old, new)
    assert read(repo, "page.md") == "[o](old.md)\n"
    assert (repo / "old.md").exists()


# --- the command --------------------------------------------------------------------


def test_the_command_moves_and_reports(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "page.md", "[o](old.md)\n")
    result = run_cli("rename", "old.md", "new.md", cwd=repo)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "moved old.md -> new.md; rewrote 1 link in 1 file" in result.stdout
    assert read(repo, "page.md") == "[o](new.md)\n"


def test_the_command_reads_its_paths_from_the_current_directory(repo: Path) -> None:
    write(repo, "sub/old.md")
    write(repo, "page.md", "[o](sub/old.md)\n")
    result = run_cli("rename", "old.md", "new.md", cwd=repo / "sub")
    assert result.returncode == exitcodes.OK, result.stderr
    assert read(repo, "page.md") == "[o](sub/new.md)\n"


def test_the_command_dry_run_says_so_and_changes_nothing(repo: Path) -> None:
    write(repo, "old.md")
    result = run_cli("rename", "--dry-run", "old.md", "new.md", cwd=repo)
    assert result.returncode == exitcodes.OK, result.stderr
    assert result.stdout.startswith("[dry-run] moved old.md -> new.md")
    assert (repo / "old.md").exists()


def test_the_command_names_each_sealed_record_it_changed(repo: Path) -> None:
    write(repo, "old.md")
    write(repo, "rec.md", "---\ntitle: R\nhash: sha256:abc\n---\n\n[o](old.md)\n")
    result = run_cli("rename", "old.md", "new.md", cwd=repo)
    assert result.returncode == exitcodes.OK
    assert "rec.md" in result.stdout
    assert "docsys seal --reseal rec.md" in result.stdout


def test_the_command_refuses_with_the_error_exit_code(repo: Path) -> None:
    result = run_cli("rename", "missing.md", "new.md", cwd=repo)
    assert result.returncode == exitcodes.ERROR
    assert "missing.md" in result.stderr
    assert result.stdout == ""
