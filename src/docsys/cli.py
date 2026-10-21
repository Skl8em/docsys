"""The `docsys` command line."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, exitcodes
from .checks.hashes import is_frozen
from .config import Config, ConfigError, load_config
from .documents import DocumentsError, documents, excluded, exclusions
from .runner import run
from .seal import SealOutcome, seal_text, sealed_text
from .ulid import at_to_ms, new_ulid
from .workspace import WorkspaceError, resolve_workspace
from .yaml_frontmatter import parse


class Arguments(argparse.Namespace):
    """The parsed command line, typed: argparse fills these attributes."""

    command: str = ""
    workspace: str | None = None
    documents: bool = False
    at: str | None = None
    order: int | None = None
    slug: str | None = None
    paths: Sequence[str] = ()
    frozen: bool = False
    reseal: bool = False
    print_only: bool = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docsys", description=__doc__)
    parser.add_argument("--version", action="version", version=f"docsys {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="run the checks docsys.yaml configures")
    check.add_argument(
        "--workspace",
        help="the project root holding docsys.yaml (default: the nearest one above the current directory)",
    )
    report = commands.add_parser("report", help="list the scope's exclusions, with their reasons and counts")
    report.add_argument(
        "--workspace",
        help="the project root holding docsys.yaml (default: the nearest one above the current directory)",
    )
    report.add_argument(
        "--documents",
        action="store_true",
        help="also list each excluded document, with the exclusion that took it out",
    )
    mint = commands.add_parser("id", help="print a new ULID; it needs no workspace")
    when = mint.add_mutually_exclusive_group()
    when.add_argument("--at", help="chronological: an ISO date or date-time (UTC) for the timestamp")
    when.add_argument("--order", type=int, help="ordinal: a controlled sort key, for re-orderable records")
    mint.add_argument("--slug", help="print <ulid>-<slug>, a filename stem")
    seal = commands.add_parser(
        "seal", help="write a frozen record's `hash:` seal, in the fixity check's canonical form"
    )
    seal.add_argument("paths", nargs="*", metavar="PATH", help="the documents to seal")
    seal.add_argument("--frozen", action="store_true", help="seal every frozen record of the scope, instead of PATHs")
    seal.add_argument("--reseal", action="store_true", help="replace a seal whose record changed (a deliberate act)")
    seal.add_argument("--print", dest="print_only", action="store_true", help="print each seal, write nothing")
    seal.add_argument("--workspace", help="the project root holding docsys.yaml, read by --frozen")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv, namespace=Arguments())
    if args.command == "id":
        return _id(args)
    if args.command == "seal" and not args.frozen:
        return _seal(args, [Path(path) for path in args.paths])
    try:
        workspace = resolve_workspace(start=os.getcwd(), explicit=args.workspace)
    except WorkspaceError as exc:
        print(f"docsys: {exc}", file=sys.stderr)
        return exitcodes.ERROR
    print(f"docsys {__version__}: workspace {workspace}", file=sys.stderr)
    try:
        config = load_config(workspace)
        if args.command == "seal":
            return _seal(args, [workspace / path for path in documents(workspace, config["scope"])])
        if args.command == "report":
            return _report(workspace, config, args.documents)
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


def _id(args: Arguments) -> int:
    try:
        ulid = new_ulid(ts_ms=None if args.at is None else at_to_ms(args.at), order=args.order)
    except ValueError as exc:
        print(f"docsys: {exc}", file=sys.stderr)
        return exitcodes.ERROR
    print(f"{ulid}-{args.slug}" if args.slug else ulid)
    return exitcodes.OK


def _seal(args: Arguments, paths: list[Path]) -> int:
    """Seal, or with --print show the seal of, each of `paths`. With --frozen the
    paths are the scope's documents and only the frozen ones are considered."""
    if args.frozen == bool(args.paths):
        print("docsys: give the documents to seal, or --frozen, not both nor neither", file=sys.stderr)
        return exitcodes.ERROR
    considered = 0
    refused = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            if args.frozen:
                parsed = parse(text)
                if parsed is None or not is_frozen(parsed):
                    continue
            considered += 1
            if args.print_only:
                print(f"{seal_text(text)}  {path}")
                continue
            result = sealed_text(text, reseal=args.reseal)
        except (OSError, ValueError) as exc:  # FrontmatterError is a ValueError
            print(f"docsys: {path}: {exc}", file=sys.stderr)
            return exitcodes.ERROR
        if result.outcome is SealOutcome.REFUSED:
            refused += 1
            print(
                f"{result.outcome.value:10}  {path}"
                f" — fix: revert it, or seal deliberately with `docsys seal --reseal {path}`"
            )
            continue
        if result.text != text:
            path.write_text(result.text, encoding="utf-8", newline="")
        print(f"{result.outcome.value:10}  {path}")
    if not args.print_only:
        print(f"\n{_count(considered, 'record')} considered.")
    return exitcodes.FINDINGS if refused else exitcodes.OK


def _report(workspace: Path, config: Config, listing: bool) -> int:
    for item in exclusions(workspace, config["scope"]):
        print(f"{item.pattern}: {item.reason} ({_count(item.count, 'document')})")
    left_out = excluded(workspace, config["scope"])
    if listing:
        for document in left_out:
            print(f"{document.path}: {document.reason} (excluded by `{document.pattern}`)")
    in_scope = len(documents(workspace, config["scope"]))
    count = f"{len(left_out)} {'document' if len(left_out) == 1 else 'documents'} excluded"
    print(f"{count if left_out else 'no document is excluded'}, {in_scope} in scope")
    return exitcodes.OK


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"
