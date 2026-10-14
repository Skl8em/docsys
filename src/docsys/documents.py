"""The documents of a workspace — the files every check reads.

A document is a Markdown file of the workspace that git tracks, or would track
once added: committed or not, but never one `.gitignore` excludes, and never one
inside a submodule, which is another project. Git is what tells a project's own
files from its build output and virtual environments, so a workspace outside a
git repository is refused, not walked. Of those files, the documents are the ones
the scope governs (`docsys.config.in_scope`).

    from docsys.documents import documents
    documents(workspace, cfg["scope"])  # ["README.md", "docs/a.md", ...]
"""

import subprocess
from pathlib import Path

from .config import Scope, in_scope


class DocumentsError(Exception):
    """The documents cannot be listed; the message carries its `fix:`."""


def documents(workspace: Path, scope: Scope) -> list[str]:
    """The workspace's documents in scope, as workspace-relative POSIX paths, sorted."""
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
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
    return sorted(path for path in paths if (workspace / path).is_file() and in_scope(scope, path))
