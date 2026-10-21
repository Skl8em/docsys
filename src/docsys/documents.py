"""The documents of a workspace — the files every check reads.

A document is a Markdown file of the workspace that git tracks, or would track
once added: committed or not, but never one `.gitignore` excludes, and never one
inside a submodule, which is another project. Git is what tells a project's own
files from its build output and virtual environments, so a workspace outside a
git repository is refused, not walked. Of those files, the documents are the ones
the scope governs (`docsys.config.in_scope`).

    from docsys.documents import documents, files
    documents(workspace, cfg["scope"])  # ["README.md", "docs/a.md", ...]
    files(workspace)                    # every such file, whatever its kind
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Scope, exclusion, in_scope


@dataclass(frozen=True)
class Excluded:
    """A document the scope leaves out, and the exclusion that took it out."""

    path: str
    pattern: str
    reason: str


class DocumentsError(Exception):
    """The documents cannot be listed; the message carries its `fix:`."""


def files(workspace: Path, pathspec: str = "*") -> list[str]:
    """The workspace's files git tracks or would track once added, matching the
    pathspec, as workspace-relative POSIX paths, sorted: never one `.gitignore`
    excludes, and never one inside a submodule."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                pathspec,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise DocumentsError(
            "git is not installed — fix: install git; docsys reads the list of documents from it"
        ) from None
    if result.returncode != 0:
        raise DocumentsError(
            f"{workspace} is not in a git repository ({result.stderr.strip()}) — "
            f"fix: run `git init` there; docsys reads the list of documents from git"
        )
    paths = {path for path in result.stdout.split("\0") if path}
    return sorted(path for path in paths if (workspace / path).is_file())


def documents(workspace: Path, scope: Scope) -> list[str]:
    """The workspace's documents in scope, as workspace-relative POSIX paths, sorted."""
    return [path for path in files(workspace, "*.md") if in_scope(scope, path)]


def excluded(workspace: Path, scope: Scope) -> list[Excluded]:
    """The workspace's documents the scope leaves out, with the first exclusion
    that took each out, sorted by path: the documents still owed."""
    left_out: list[Excluded] = []
    for path in files(workspace, "*.md"):
        taken = exclusion(scope, path)
        if taken is not None:
            left_out.append(Excluded(path, *taken))
    return left_out


@dataclass(frozen=True)
class Exclusion:
    """Stub."""

    pattern: str
    reason: str
    count: int


def exclusions(workspace: Path, scope: Scope) -> list[Exclusion]:
    """Stub."""
    raise NotImplementedError
