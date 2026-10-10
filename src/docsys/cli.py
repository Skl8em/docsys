"""The `docsys` command line."""
import argparse
import os
import sys

from . import __version__, exitcodes
from .workspace import WorkspaceError, resolve_workspace


def build_parser():
    parser = argparse.ArgumentParser(prog="docsys", description=__doc__)
    parser.add_argument("--version", action="version", version=f"docsys {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="run the checks docsys.yaml configures")
    check.add_argument("--workspace", help="the project root holding docsys.yaml (default: the nearest one above the current directory)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        workspace = resolve_workspace(start=os.getcwd(), explicit=args.workspace)
    except WorkspaceError as exc:
        print(f"docsys: {exc}", file=sys.stderr)
        return exitcodes.ERROR
    print(f"docsys {__version__}: workspace {workspace}", file=sys.stderr)
    print(f"docsys: this version implements no checks yet — "
          f"fix: run the project's own gate until the checks are ported", file=sys.stderr)
    return exitcodes.ERROR
