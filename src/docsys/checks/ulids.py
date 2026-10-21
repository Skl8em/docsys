"""The ULID check (the documentation system's ADR-028): a record's identifier, and
the references that supersede one record with another.

The canonical identifier is the frontmatter `id`, a ULID. A record without one is
permitted: wherever something else needs to name it, its identity is its filename
stem, the convention that predates ULIDs. `supersedes` and `superseded-by` name
records by either, and four things must hold of them: each resolves to a record,
the pair is kept symmetric, no record supersedes itself, and no chain of
`superseded-by` loops back. When the project keeps a decision register
(`register:` in docsys.yaml), each of its rows must agree with the record it links
to; a register whose configured row shape finds no row is an error, not a pass,
since it would switch the comparison off without a word.

A reference may name a record the scope excludes: it resolves, and the excluded record,
which is not checked, is not asked to name it back.
A `<...>` reference is a template's fill-in and is skipped. A document whose
frontmatter cannot be read is left to the frontmatter check. Findings come in the
order of their path, then their line.
"""

import posixpath
import re
from pathlib import Path, PurePosixPath
from typing import Final, TypeGuard

from ..config import Config, Register
from ..documents import documents, excluded
from ..findings import Finding, Rule
from ..ulid import is_ulid
from ..workspace import CONFIG_NAME
from ..yaml_frontmatter import Frontmatter, FrontmatterError, load

FORM: Final = Rule("ulids/form", "error")
UNIQUE: Final = Rule("ulids/unique", "error")
RESOLVE: Final = Rule("ulids/resolve", "error")
SELF: Final = Rule("ulids/self", "error")
SYMMETRIC: Final = Rule("ulids/symmetric", "error")
CYCLE: Final = Rule("ulids/cycle", "error")
REGISTER: Final = Rule("ulids/register", "error")
RULES: Final = (FORM, UNIQUE, RESOLVE, SELF, SYMMETRIC, CYCLE, REGISTER)

SUPERSEDES: Final = "supersedes"
SUPERSEDED_BY: Final = "superseded-by"
REF_FIELDS: Final = (SUPERSEDES, SUPERSEDED_BY)
INVERSE: Final = {SUPERSEDES: SUPERSEDED_BY, SUPERSEDED_BY: SUPERSEDES}

Records = dict[str, Frontmatter]  # path -> frontmatter ({} when the document has none)


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def check(workspace: Path, config: Config) -> list[Finding]:
    paths = documents(workspace, config["scope"])
    records: Records = {}
    for path in paths:
        try:
            records[path] = load(workspace / path) or {}
        except FrontmatterError:
            continue
    findings = [*_ids(records), *_references(records, _outside(workspace, config))]
    register = config["register"]
    if register is not None:
        findings.extend(_register(workspace, set(paths), records, register))
    return sorted(findings, key=lambda finding: (finding.path, finding.line))


# --- the ids ---------------------------------------------------------------------


def _ids(records: Records) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, str] = {}
    for path, frontmatter in records.items():
        if "id" not in frontmatter:
            continue
        identifier, line = frontmatter["id"]
        if not identifier:
            continue
        if not isinstance(identifier, str) or not is_ulid(identifier):
            findings.append(
                Finding(
                    FORM.id,
                    path,
                    line,
                    f"id {identifier!r} is not a valid ULID",
                    "mint one with `docsys id`",
                )
            )
        if not isinstance(identifier, str):
            continue
        if identifier in seen:
            findings.append(
                Finding(
                    UNIQUE.id,
                    path,
                    line,
                    f"duplicate id (also in {seen[identifier]})",
                    "give one of the two records a fresh `id` from `docsys id`",
                )
            )
        seen[identifier] = path
    return findings


# --- the references between records ----------------------------------------------


def _identity(path: str, frontmatter: Frontmatter) -> str:
    """How something else names the record: its `id` if it carries one, else its
    filename stem."""
    identifier = frontmatter.get("id", (None, 0))[0]
    return identifier if isinstance(identifier, str) and identifier else PurePosixPath(path).stem


def _references_in(value: object) -> list[str]:
    """What a `supersedes`/`superseded-by` value names: nothing for null, the string
    for a string, each string of a list. A `<...>` fill-in is not a reference."""
    items: list[object] = value if _is_list(value) else [value]
    return [item for item in items if isinstance(item, str) and "<" not in item]


def _find_cycles(successors: dict[str, list[str]]) -> list[list[str]]:
    """Each cycle once, as the nodes it passes through, starting at its smallest, in
    the order the edges are followed."""
    cycles: list[list[str]] = []
    done: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in trail:
            loop = trail[trail.index(node) :]
            start = loop.index(min(loop))
            loop = loop[start:] + loop[:start]
            if loop not in cycles:
                cycles.append(loop)
            return
        if node in done:
            return
        for following in successors.get(node, []):
            visit(following, [*trail, node])
        done.add(node)

    for node in sorted(successors):
        visit(node, [])
    return cycles


def _outside(workspace: Path, config: Config) -> set[str]:
    """How the records the scope excludes are named. A reference to one resolves: an
    exclusion takes a document out of the checks, not out of the project. It is not
    checked, so it is not asked to name the reference back."""
    names: set[str] = set()
    for item in excluded(workspace, config["scope"]):
        try:
            frontmatter = load(workspace / item.path) or {}
        except FrontmatterError:
            frontmatter = {}
        names.add(_identity(item.path, frontmatter))
    return names


def _references(records: Records, outside: set[str]) -> list[Finding]:
    index = {_identity(path, frontmatter): path for path, frontmatter in records.items()}
    findings: list[Finding] = []
    resolved: dict[tuple[str, str], list[str]] = {}  # (path, field) -> the records it names
    lines: dict[tuple[str, str], int] = {}  # (path, field) -> the line of the field
    for path, frontmatter in records.items():
        for field in REF_FIELDS:
            targets: list[str] = []
            value, line = frontmatter.get(field, (None, 0))
            lines[path, field] = line
            for reference in _references_in(value):
                target = index.get(reference)
                if target is None and reference in outside:
                    continue
                if target is None:
                    findings.append(
                        Finding(
                            RESOLVE.id,
                            path,
                            line,
                            f"`{field}: {reference}` does not resolve to any record's `id` or filename",
                            "correct the reference to an existing record's `id` or filename stem, "
                            "or set the field to null",
                        )
                    )
                elif target == path:
                    # Reported here and dropped, so it is neither also an asymmetry
                    # nor a one-node cycle below.
                    findings.append(
                        Finding(
                            SELF.id,
                            path,
                            line,
                            f"`{field}: {reference}` names this record itself, and a record cannot supersede itself",
                            "name the record it really replaces (or is replaced by), or set the field to null",
                        )
                    )
                else:
                    targets.append(target)
            resolved[path, field] = targets

    for path in records:
        for field in REF_FIELDS:
            inverse = INVERSE[field]
            for target in resolved[path, field]:
                if path not in resolved[target, inverse]:
                    findings.append(
                        Finding(
                            SYMMETRIC.id,
                            path,
                            lines[path, field],
                            f"`{field}` names {target}, but its `{inverse}` does not name this record back",
                            f"set `{inverse}` in {target} to this record's `id` or filename stem, "
                            f"or remove the `{field}` here",
                        )
                    )

    chain = {path: resolved[path, SUPERSEDED_BY] for path in records}
    for loop in _find_cycles(chain):
        route = " -> ".join([*loop, loop[0]])
        findings.append(
            Finding(
                CYCLE.id,
                loop[0],
                lines[loop[0], SUPERSEDED_BY],
                f"`{SUPERSEDED_BY}` loops back on itself ({route}): a supersession cycle leaves no record that binds",
                f"break the loop by clearing the `{SUPERSEDED_BY}` (and the matching `{SUPERSEDES}`) "
                "on the record that is not really replaced",
            )
        )
    return findings


# --- the decision register -------------------------------------------------------


def _register(workspace: Path, paths: set[str], records: Records, register: Register) -> list[Finding]:
    """Compare the register's "superseded by N" status text with the `superseded-by`
    of the record each row links to. A broken link is the link check's to report."""
    if register["path"] not in paths:
        return [
            Finding(
                REGISTER.id,
                CONFIG_NAME,
                1,
                f"`register.path` names `{register['path']}`, which is not a document of the workspace",
                "correct `register.path`",
            )
        ]
    rows = _rows(workspace, register)
    if not rows:
        # Nothing to compare is not "nothing wrong": a row shape that matches no row
        # (a renamed column, a reworded ordinal) would otherwise switch the check off.
        return [
            Finding(
                REGISTER.id,
                register["path"],
                1,
                f"`register` in {CONFIG_NAME} matches no decision rows in `{register['path']}` "
                f"(rows of {register['columns']} cells whose cell {register['ordinal_column']} "
                f"matches {register['ordinal_pattern']!r})",
                f"correct the `register:` shape in {CONFIG_NAME} to match the register's rows, or the rows to match it",
            )
        ]
    index = {_identity(path, frontmatter): path for path, frontmatter in records.items()}
    ordinal_to_path = {ordinal: path for ordinal, path, _ in rows}
    superseded = re.compile(register["superseded_pattern"])
    findings: list[Finding] = []
    for ordinal, path, status in rows:
        if path not in records:
            continue
        value, line = records[path].get(SUPERSEDED_BY, (None, 0))
        named = {index[reference] for reference in _references_in(value) if reference in index}
        match = superseded.search(status)
        if match:
            if ordinal_to_path.get(match.group(1)) not in named:
                findings.append(
                    Finding(
                        REGISTER.id,
                        path,
                        line or 1,
                        f"register row {ordinal} says {status!r}, but this record's `{SUPERSEDED_BY}` does not name it",
                        f"set `{SUPERSEDED_BY}` here to the superseding record, "
                        f"or correct the row in {register['path']}",
                    )
                )
        elif named:
            findings.append(
                Finding(
                    REGISTER.id,
                    path,
                    line or 1,
                    f"register row {ordinal} says {status!r} (no supersession), "
                    f"but this record's `{SUPERSEDED_BY}` is set",
                    f"mark the row superseded in {register['path']}, or clear `{SUPERSEDED_BY}` here",
                )
            )
    return findings


def _rows(workspace: Path, register: Register) -> list[tuple[str, str, str]]:
    """Each decision row of the register as (ordinal, the linked record's path from
    the workspace, status). The link is read from the register's own folder, as a
    Markdown link is."""
    folder = posixpath.dirname(register["path"])
    ordinal_re = re.compile(register["ordinal_pattern"])
    rows: list[tuple[str, str, str]] = []
    for line in (workspace / register["path"]).read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != register["columns"]:
            continue
        match = ordinal_re.match(cells[register["ordinal_column"]])
        if not match:
            continue  # the header, the separator, any row that is not a decision row
        rows.append(
            (
                match.group(1),
                posixpath.normpath(posixpath.join(folder, match.group(2))),
                cells[register["status_column"]],
            )
        )
    return rows
