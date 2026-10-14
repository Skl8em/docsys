"""The paired-change check where git, not the case format, is the subject: a shallow
clone that lost the anchor, a branch that exists only on a remote, and a workspace
that is a folder of a larger repository. The rule itself is stated in
conformance/paired-change.yaml."""

import subprocess
from pathlib import Path

from docsys.checks import paired_change
from docsys.config import load_config

CONFIG = """\
version: 1
paired_change:
  since: {since}
  mechanism: [scripts/]
  understanding: [writing/]
  exempt: []
  enforce_on: [{enforce_on}]
"""


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t.invalid", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(root: Path, message: str, files: dict[str, str]) -> str:
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(root, "add", path)
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def origin(tmp_path: Path) -> Path:
    root = tmp_path / "origin"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    return root


def test_a_shallow_clone_that_lost_the_anchor_is_told_to_fetch_the_history(tmp_path: Path) -> None:
    source = origin(tmp_path)
    first = commit(source, "first", {"writing/a.md": "a\n"})
    commit(source, "second", {"writing/b.md": "b\n"})
    commit(source, "third", {"writing/c.md": "c\n"})
    clone = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{source}", str(clone)], check=True)
    (clone / "docsys.yaml").write_text(CONFIG.format(since=first, enforce_on="main"), encoding="utf-8")
    found = paired_change.check(clone, load_config(clone))
    assert [f.rule for f in found] == ["paired-change/anchor"]
    assert "fetch" in found[0].fix


def test_a_branch_that_exists_only_on_a_remote_counts_as_one_to_enforce_on(tmp_path: Path) -> None:
    source = origin(tmp_path)
    anchor = commit(source, "first", {"writing/a.md": "a\n"})
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", f"file://{source}", str(clone)], check=True)
    git(clone, "switch", "-q", "--detach")
    git(clone, "branch", "-q", "-D", "main")
    (clone / "docsys.yaml").write_text(CONFIG.format(since=anchor, enforce_on="main"), encoding="utf-8")
    assert paired_change.check(clone, load_config(clone)) == []


def test_a_workspace_that_is_a_folder_of_a_repository_sees_its_own_paths(tmp_path: Path) -> None:
    root = origin(tmp_path)
    anchor = commit(root, "anchor", {"sub/writing/a.md": "a\n", "outside/x.py": "x\n"})
    commit(root, "outside tooling", {"scripts/outside.py": "o\n"})
    commit(root, "inside tooling", {"sub/scripts/x.py": "x\n"})
    workspace = root / "sub"
    (workspace / "docsys.yaml").write_text(CONFIG.format(since=anchor, enforce_on="main"), encoding="utf-8")
    found = paired_change.check(workspace, load_config(workspace))
    assert [(f.rule, f.path) for f in found] == [("paired-change/unpaired", "scripts/x.py")]
