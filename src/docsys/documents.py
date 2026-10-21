"""The documents of a workspace — the files every check reads.

A document is a Markdown file anywhere under the workspace but inside `.git`:
tracked, untracked or ignored by git alike, and a submodule's files included, since
`.gitignore` says what git leaves out, not what is documentation. What a project
leaves out of the framework it says in `scope.exclude`, with its reason. The walk
follows no symlink, and does not enter a folder the scope leaves out wholly, so a
build folder or a virtual environment costs nothing. A workspace need not be a git
repository. Of those files, the documents are the ones the scope governs
(`docsys.config.in_scope`).

    from docsys.documents import documents, files
    documents(workspace, cfg["scope"])  # ["README.md", "docs/a.md", ...]
    files(workspace, under="phases")    # every file below `phases/`, whatever its kind
"""

import os
from dataclasses import dataclass
from pathlib import Path

from .config import Scope, covers_folder, exclusion, in_scope


@dataclass(frozen=True)
class Excluded:
    """A document the scope leaves out, and the exclusion that took it out."""

    path: str
    pattern: str
    reason: str


class DocumentsError(Exception):
    """The documents cannot be listed; the message carries its `fix:`."""


def files(workspace: Path, scope: Scope | None = None, *, under: str = "", suffix: str = "") -> list[str]:
    """The workspace's files below the folder `under` (the whole workspace by
    default) whose name ends with `suffix`, as workspace-relative POSIX paths,
    sorted. Nothing inside `.git` is listed and no symlink is followed or listed.
    With a scope, a folder it leaves out wholly is not entered."""
    top = workspace / under
    found: list[str] = []
    for folder, subfolders, names in os.walk(top):
        here = Path(folder).relative_to(workspace)
        subfolders[:] = [
            name
            for name in subfolders
            if name != ".git" and (scope is None or not covers_folder(scope, (here / name).as_posix()))
        ]
        found += [
            (here / name).as_posix()
            for name in names
            if name.endswith(suffix) and not (Path(folder) / name).is_symlink()
        ]
    return sorted(found)


def documents(workspace: Path, scope: Scope) -> list[str]:
    """The workspace's documents in scope, as workspace-relative POSIX paths, sorted."""
    return [path for path in files(workspace, scope, suffix=".md") if in_scope(scope, path)]


def excluded(workspace: Path, scope: Scope) -> list[Excluded]:
    """The workspace's documents the scope leaves out, with the first exclusion
    that took each out, sorted by path: the documents still owed."""
    left_out: list[Excluded] = []
    for path in files(workspace, suffix=".md"):
        taken = exclusion(scope, path)
        if taken is not None:
            left_out.append(Excluded(path, *taken))
    return left_out


@dataclass(frozen=True)
class Exclusion:
    """An exclusion of the scope, with the number of documents it took out: a
    document counts for the first exclusion that matches it. A count of 0 is a
    stale exclusion, or one another exclusion shadows."""

    pattern: str
    reason: str
    count: int


def exclusions(workspace: Path, scope: Scope) -> list[Exclusion]:
    """The scope's exclusions in the order the configuration lists them, each with
    its count of documents."""
    counts = dict.fromkeys(scope["exclude"], 0)
    for item in excluded(workspace, scope):
        counts[item.pattern] += 1
    return [Exclusion(pattern, reason, counts[pattern]) for pattern, reason in scope["exclude"].items()]
