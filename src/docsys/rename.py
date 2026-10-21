"""Renaming: move a file or folder and keep every relative link to it working.

The links rewritten are those the link check reads (`checks.links`): in each document
of the scope, and in each moved document wherever the scope puts it, the target of
every relative link that pointed at the moved path or at anything under it, and the
target of every link of a moved document, for its new folder. A link keeps its anchor,
its title and the way it was written (`./`, a trailing `/`); a link the move does not
affect is not touched. Display text and paths written in prose are not links and are
left for the author.

The whole change is computed before anything is moved, so a move that cannot be made
changes nothing. A sealed record whose link is rewritten no longer matches its seal:
the rewrite is made, as it is for any document, and the record is reported so its
seal can be renewed deliberately (`docsys seal --reseal`).
"""

import os
import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .checks.hashes import declared_seal, split_document
from .checks.links import LINK_RE, NOT_RESOLVED
from .config import Scope
from .documents import documents, files

TARGET_RE: Final = re.compile(r"(\S+)(\s.*)?$", re.DOTALL)


class RenameError(Exception):
    """The move cannot be made; the message carries its `fix:`."""


@dataclass(frozen=True)
class Renamed:
    old: str
    new: str
    rewritten: dict[str, int]  # document (where it ends up) -> links rewritten in it
    stale_seals: list[str]  # sealed documents among them, whose seal no longer matches
    dry_run: bool


def _moved(path: str, old: str, new: str) -> str | None:
    """Where `path` goes when `old` becomes `new`; None when it does not move."""
    if path == old:
        return new
    if path.startswith(old + "/"):
        return new + path[len(old) :]
    return None


def _rewrite_target(raw: str, old_dir: str, new_dir: str, file_moved: bool, old: str, new: str) -> str:
    stripped = raw.strip()
    if stripped.startswith(NOT_RESOLVED):
        return raw
    match = TARGET_RE.match(stripped)
    if match is None:
        return raw
    token, tail = match.group(1), match.group(2) or ""
    path, hash_, anchor = token.partition("#")
    if not path or path.startswith(("<", "/")) or "…" in path:
        return raw
    resolved = posixpath.normpath(posixpath.join(old_dir, path))
    target = _moved(resolved, old, new)
    if target is None and not file_moved:
        return raw
    relative = posixpath.relpath(target or resolved, new_dir or ".")
    if posixpath.normpath(relative) == posixpath.normpath(path):
        return raw
    if path.endswith("/") and not relative.endswith("/"):
        relative += "/"
    if path.startswith("./") and not relative.startswith("."):
        relative = "./" + relative
    return raw[: len(raw) - len(raw.lstrip())] + relative + hash_ + anchor + tail


def _rewrite_text(text: str, old_dir: str, new_dir: str, old: str, new: str) -> tuple[str, int]:
    count = 0
    file_moved = old_dir != new_dir
    lines: list[str] = []
    for line in text.split("\n"):

        def replace(match: re.Match[str]) -> str:
            nonlocal count
            target = _rewrite_target(match.group(1), old_dir, new_dir, file_moved, old, new)
            if target == match.group(1):
                return match.group(0)
            count += 1
            start = match.start(1) - match.start(0)
            return match.group(0)[:start] + target + ")"

        lines.append(LINK_RE.sub(replace, line))
    return "\n".join(lines), count


def _normalise(workspace: Path, given: str, role: str) -> str:
    path = posixpath.normpath(given.replace(os.sep, "/"))
    if path == "." or path.startswith(("/", "../")) or path == "..":
        raise RenameError(f"{role} `{given}` is outside the workspace — fix: name a path inside {workspace}")
    if path.split("/")[0] == ".git":
        raise RenameError(f"{role} `{given}` is inside .git — fix: name a path of the project")
    return path


def _git_tracks(workspace: Path, path: str) -> bool:
    listed = subprocess.run(
        ["git", "-C", str(workspace), "ls-files", "--", path], capture_output=True, text=True, check=False
    )
    return listed.returncode == 0 and bool(listed.stdout.strip())


def rename(workspace: Path, scope: Scope, old: str, new: str, *, dry_run: bool = False) -> Renamed:
    """Move `old` to `new` (workspace-relative paths) and rewrite the links to it.
    Raises `RenameError`, having changed nothing, when the move cannot be made."""
    old, new = _normalise(workspace, old, "OLD"), _normalise(workspace, new, "NEW")
    if not os.path.lexists(workspace / old):
        raise RenameError(f"OLD `{old}` does not exist — fix: name an existing file or folder")
    if os.path.lexists(workspace / new):
        raise RenameError(f"NEW `{new}` already exists — fix: choose a free name, or move the existing one first")
    if new.startswith(old + "/"):
        raise RenameError(f"NEW `{new}` is inside itself — fix: move `{old}` beside its destination, not into it")

    moving = files(workspace, under=old, suffix=".md") if (workspace / old).is_dir() else [old]
    pre = sorted({*documents(workspace, scope), *(path for path in moving if path.endswith(".md"))})
    rewritten: dict[str, int] = {}
    stale: list[str] = []
    writes: dict[str, str] = {}  # where a document ends up -> its new text
    for path in pre:
        post = _moved(path, old, new) or path
        raw = (workspace / path).read_bytes().decode("utf-8")
        text, count = _rewrite_text(raw, posixpath.dirname(path), posixpath.dirname(post), old, new)
        if count:
            rewritten[post] = count
            writes[post] = text
            parts = split_document(raw)
            if parts is not None and declared_seal(parts[0]) is not None:
                stale.append(post)
    result = Renamed(old, new, rewritten, stale, dry_run)
    if dry_run:
        return result

    (workspace / new).parent.mkdir(parents=True, exist_ok=True)
    if _git_tracks(workspace, old):
        moved = subprocess.run(
            ["git", "-C", str(workspace), "mv", "--", old, new], capture_output=True, text=True, check=False
        )
        if moved.returncode != 0:
            raise RenameError(f"git could not move `{old}` to `{new}`: {moved.stderr.strip()}")
    else:
        os.rename(workspace / old, workspace / new)
    for post, text in writes.items():
        (workspace / post).write_bytes(text.encode("utf-8"))
    return result
