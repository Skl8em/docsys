"""The workspace: the project root a `docsys` run works in.

It is the directory holding `docsys.yaml`. The CLI finds it as the nearest
ancestor of the starting point that holds one, the way `make` finds its makefile,
or takes it explicitly with `--workspace`; a library caller passes it as an
argument. Nothing is assumed from the current directory or from where the package
is installed.
"""
import os
from pathlib import Path

CONFIG_NAME = "docsys.yaml"

StrPath = str | os.PathLike[str]


class WorkspaceError(Exception):
    """No workspace can be established; the message carries its `fix:`."""


def find_workspace(start: StrPath) -> Path:
    """Return the nearest directory, from `start` upwards, that holds `docsys.yaml`."""
    start = Path(start).resolve()
    here = start if start.is_dir() else start.parent
    for candidate in (here, *here.parents):
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    raise WorkspaceError(
        f"no {CONFIG_NAME} in {here} or any directory above it — "
        f"fix: run `docsys init` at the project's root, or pass --workspace PATH")


def resolve_workspace(start: StrPath, explicit: StrPath | None = None) -> Path:
    """The workspace for a run: `explicit` if given (it must hold `docsys.yaml`),
    otherwise the nearest one above `start`."""
    if explicit is None:
        return find_workspace(start)
    root = Path(explicit).resolve()
    if not (root / CONFIG_NAME).is_file():
        raise WorkspaceError(
            f"{root} holds no {CONFIG_NAME} — "
            f"fix: pass the directory that holds it, or run `docsys init` there")
    return root
