"""The `docsys` command line."""

import argparse
import os
import sys
from collections.abc import Sequence

from . import __version__, exitcodes
from .config import ConfigError, load_config
from .documents import DocumentsError
from .runner import run
from .workspace import WorkspaceError, resolve_workspace


class Arguments(argparse.Namespace):
    """The parsed command line, typed: argparse fills these attributes."""

    command: str = ""
    workspace: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docsys", description=__doc__)
    parser.add_argument("--version", action="version", version=f"docsys {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="run the checks docsys.yaml configures")
    check.add_argument(
        "--workspace",
        help="the project root holding docsys.yaml (default: the nearest one above the current directory)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv, namespace=Arguments())
    try:
        workspace = resolve_workspace(start=os.getcwd(), explicit=args.workspace)
    except WorkspaceError as exc:
        print(f"docsys: {exc}", file=sys.stderr)
        return exitcodes.ERROR
    print(f"docsys {__version__}: workspace {workspace}", file=sys.stderr)
    try:
        report = run(workspace, load_config(workspace))
    except (ConfigError, DocumentsError) as exc:
        print(f"docsys: {exc}", file=sys.stderr)
        return exitcodes.ERROR
    for finding in report.errors:
        print(finding)
    if report.warnings:
        print(f"warnings ({len(report.warnings)}), reported without failing the run:")
        for finding in report.warnings:
            print(f"  {finding}")
    counts = f"{_count(len(report.errors), 'error')}, {_count(len(report.warnings), 'warning')}"
    if report.errors:
        print(f"docsys check failed: {counts}")
        return exitcodes.FINDINGS
    print(f"docsys check passed: {counts}")
    return exitcodes.OK


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"
