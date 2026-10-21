"""The paired-change check: the tooling does not change unexplained.

A change to the mechanism that leaves the documents explaining it describing the old
one is noticed here: a unit of change that touches the mechanism must also touch at
least one file a human reads for understanding. Which paths are mechanism, which are
understanding, which need no account, where the rule starts and where it is enforced
is configuration (`paired_change:` in docsys.yaml); a project with no such section
does not run it.

The unit is one commit, plus the uncommitted work that will become the next one. It
is deliberately not the branch: a phase-long branch nearly always touches some
document, so a branch-level rule would pass the very case that motivated it. It is
not a proof of adequacy either, only that a change to the tooling was not made in
silence. A merge commit is not a unit: it brings in another line's history, which is
that line's to answer for.

Two things are no change to the mechanism, because there is nothing to explain: a file
under an `exempt` prefix, and a Python edit whose syntax tree, docstrings set aside,
is unchanged. A file added or deleted is never such an edit, and neither is a version
that does not parse.

It fails where work lands, a branch named in `enforce_on` or a detached HEAD (a pull
request's merge commit in CI); elsewhere the same findings are advisory. Paths are the
workspace's own, so a workspace that is a folder of a larger repository sees only its
own changes. Findings come in the order of the commits, oldest first, the uncommitted
work last.
"""

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..config import Config, PairedChange
from ..documents import DocumentsError
from ..findings import Finding, Rule
from ..workspace import CONFIG_NAME

UNPAIRED: Final = Rule("paired-change/unpaired", "error")
ADVISORY: Final = Rule("paired-change/advisory", "warning")
ANCHOR: Final = Rule("paired-change/anchor", "error")
BRANCHES: Final = Rule("paired-change/branches", "error")
RULES: Final = (UNPAIRED, ADVISORY, ANCHOR, BRANCHES)

PENDING: Final = "uncommitted changes (what the next commit will contain)"


@dataclass(frozen=True)
class Unit:
    label: str
    paths: list[str]
    trivial: set[str]  # the paths of the unit whose change is comment-only


def _touches(path: str, prefixes: list[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = node.body
            first = body[0] if body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                del body[0]
                if not body:
                    body.append(ast.Pass())
    return tree


def comment_only(old: str, new: str) -> bool:
    """True when two versions of a Python file differ only in comments, docstrings or
    formatting. A version that does not parse is never comment-only: it is not known
    to be harmless."""
    try:
        return ast.dump(_strip_docstrings(ast.parse(old))) == ast.dump(_strip_docstrings(ast.parse(new)))
    except SyntaxError:
        return False


def _git(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace), "-c", "core.quotepath=off", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _show(workspace: Path, revision: str | None, path: str) -> str | None:
    """A file's text at a revision, or in the working tree when `revision` is None;
    None if it does not exist there."""
    if revision is None:
        try:
            return (workspace / path).read_text(encoding="utf-8")
        except OSError:
            return None
    result = _git(workspace, "show", f"{revision}:./{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def _trivial(workspace: Path, paths: list[str], old: str, new: str | None) -> set[str]:
    """The Python files among `paths` whose change between two revisions is
    comment-only. A file added or deleted in the unit is never comment-only."""
    trivial: set[str] = set()
    for path in paths:
        if path.endswith(".py"):
            before, after = _show(workspace, old, path), _show(workspace, new, path)
            if before is not None and after is not None and comment_only(before, after):
                trivial.add(path)
    return trivial


def _anchor_problem(since: str, workspace: Path) -> tuple[str, str] | None:
    """Why `since` cannot be used, and the fix; None when it can."""
    if _git(workspace, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}", check=False).returncode != 0:
        shallow = _git(workspace, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
        if shallow:
            return (
                f"`paired_change.since` ({since}) cannot be resolved: this is a shallow clone, so the history that "
                "holds it was not fetched",
                "fetch full history (`git fetch --unshallow`, or `fetch-depth: 0` in CI)",
            )
        return (
            f"`paired_change.since` ({since}) cannot be resolved: no such commit in this repository",
            f"set `paired_change.since` in {CONFIG_NAME} to a commit of this history",
        )
    if _git(workspace, "merge-base", "--is-ancestor", since, "HEAD", check=False).returncode != 0:
        return (
            f"`paired_change.since` ({since}) is not an ancestor of HEAD",
            f"set it in {CONFIG_NAME} to a commit on this branch's history",
        )
    return None


def _branches_problem(enforce_on: list[str], workspace: Path) -> bool:
    """True when no listed branch exists, locally or on a remote (CI checks out a
    detached HEAD with remote refs only): the rule would only ever be advisory."""
    refs = _git(workspace, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes").stdout.split()
    names = {ref[len("refs/heads/") :] for ref in refs if ref.startswith("refs/heads/")}
    names |= {ref.split("/", 3)[3] for ref in refs if ref.startswith("refs/remotes/") and ref.count("/") >= 3}
    return not names & set(enforce_on)


def _commit_units(since: str, workspace: Path) -> list[Unit]:
    """One unit per non-merge commit in since..HEAD, oldest first. The anchor itself
    is not examined: the rule starts after it."""
    out = _git(
        workspace,
        "log",
        "--reverse",
        "--no-merges",
        "--no-renames",
        "--relative",
        "--name-only",
        "--format=%x1e%H %s",
        f"{since}..HEAD",
    ).stdout
    units: list[Unit] = []
    for record in out.split("\x1e")[1:]:
        head, *lines = record.split("\n")
        sha, subject = head.split(" ", 1)
        paths = [line for line in lines if line]
        units.append(Unit(f"{sha[:7]} {subject}", paths, _trivial(workspace, paths, f"{sha}^", sha)))
    return units


def _pending_unit(workspace: Path) -> Unit | None:
    """The uncommitted change against HEAD (tracked files, staged or not), or None.
    Renames are split into delete and add, so moving a script out of the tooling still
    counts. An untracked file is in no unit until it is staged."""
    result = _git(workspace, "diff", "--name-only", "--no-renames", "--relative", "HEAD", check=False)
    paths = [line for line in result.stdout.splitlines() if line] if result.returncode == 0 else []
    return Unit(PENDING, paths, _trivial(workspace, paths, "HEAD", None)) if paths else None


def _unpaired(units: list[Unit], config: PairedChange) -> list[tuple[Unit, list[str]]]:
    """The units that touch the mechanism and nothing that explains it, with the
    mechanism paths that lacked an account. A path under an `exempt` prefix, or
    comment-only, needs none."""
    offenders: list[tuple[Unit, list[str]]] = []
    for unit in units:
        mechanism = [
            path
            for path in unit.paths
            if _touches(path, config["mechanism"]) and not _touches(path, config["exempt"]) and path not in unit.trivial
        ]
        if mechanism and not any(_touches(path, config["understanding"]) for path in unit.paths):
            offenders.append((unit, mechanism))
    return offenders


def check(workspace: Path, config: Config) -> list[Finding]:
    paired = config["paired_change"]
    if paired is None:
        return []
    if _git(workspace, "rev-parse", "--git-dir", check=False).returncode != 0:
        raise DocumentsError(
            f"{workspace} is not in a git repository — "
            "fix: run `git init` there; the paired-change rule reads the history from git"
        )
    if _branches_problem(paired["enforce_on"], workspace):
        names = ", ".join(paired["enforce_on"])
        return [
            Finding(
                BRANCHES.id,
                CONFIG_NAME,
                1,
                f"`paired_change.enforce_on` ({names}) names no branch of this repository, so the rule would only "
                "ever warn, except on a detached checkout",
                "list the integration branch's current name",
            )
        ]
    problem = _anchor_problem(paired["since"], workspace)
    if problem is not None:
        return [Finding(ANCHOR.id, CONFIG_NAME, 1, *problem)]
    units = _commit_units(paired["since"], workspace)
    pending = _pending_unit(workspace)
    if pending:
        units.append(pending)
    branch = _git(workspace, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip() or None
    enforced = branch is None or branch in paired["enforce_on"]
    places = ", ".join(paired["understanding"])
    fix = (
        f"in the same commit, update what a reader would need to learn about the change: a file under {places}. "
        "A commit already made cannot be paired afterwards: amend it if unpublished, otherwise move "
        f"`paired_change.since` in {CONFIG_NAME} past it, which is a reviewable, deliberate acceptance"
    )
    findings: list[Finding] = []
    for unit, mechanism in _unpaired(units, paired):
        message = f"{unit.label} changed the tooling ({', '.join(mechanism)}) and nothing that explains it"
        if not enforced:
            enforced_on = ", ".join(f"`{name}`" for name in paired["enforce_on"])
            message += (
                f" (not enforced on branch `{branch}`, only on {enforced_on} and detached checkouts: "
                "this will fail when it lands)"
            )
        findings.append(Finding((UNPAIRED if enforced else ADVISORY).id, mechanism[0], 1, message, fix))
    return findings
