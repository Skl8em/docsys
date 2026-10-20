"""The `docsys` command line."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, exitcodes
from .config import Config, ConfigError, load_config
from .documents import DocumentsError, documents, excluded
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
    report = commands.add_parser("report", help="list the documents the scope leaves out, with their reasons")
    report.add_argument(
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
        config = load_config(workspace)
        if args.command == "report":
            return _report(workspace, config)
        report = run(workspace, config)
    except (ConfigError, DocumentsError) as exc:
        print(f"docsys: {exc}", file=sys.stderr)
        return exitcodes.ERROR
    for finding in report.errors:
        print(finding)
    if report.warnings:
        print(f"warnings ({len(report.warnings)}), reported without failing the run:")
        for finding in report.warnings:
            print(f"  {finding}")
    for name, output in report.tool_outputs:
        print(f"=== {name} ===")
        print(output, end="" if output.endswith("\n") or not output else "\n")
    counts = f"{_count(len(report.errors), 'error')}, {_count(len(report.warnings), 'warning')}"
    if report.errors:
        print(f"docsys check failed: {counts}")
        return exitcodes.FINDINGS
    print(f"docsys check passed: {counts}")
    return exitcodes.OK


def _report(workspace: Path, config: Config) -> int:
    left_out = excluded(workspace, config["scope"])
    for item in left_out:
        print(f"{item.path}: {item.reason} (excluded by `{item.pattern}`)")
    in_scope = len(documents(workspace, config["scope"]))
    count = f"{len(left_out)} {'document' if len(left_out) == 1 else 'documents'} excluded"
    print(f"{count if left_out else 'no document is excluded'}, {in_scope} in scope")
    return exitcodes.OK


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"
