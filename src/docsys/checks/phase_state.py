"""The phase-state check: every place that speaks of the current phase agrees with
the ledger.

The ledger (`phases.ledger` in docsys.yaml, checked by the ledger check) declares
where the project is. This check reads every other place that says so and reports
where one disagrees:

  - folders: a numbered phase has its folder, and no phase folder exists that the
    ledger does not list;
  - tables: each phase row of a configured table carries the marker of its ledger
    status, a number the ledger has not given is refused, the current phase has a
    row, and a row pattern that matches no row is an error rather than a pass;
  - mentions: no document in scope names, by number, a phase above the highest the
    ledger has numbered. A frozen record is not read: it says what was true when it
    froze and cannot be edited, so a finding in it could never be cleared;
  - status: the file of `phases.status` has exactly one status line, and it names the
    current phase;
  - `phase:` fields: each names a numbered phase of the ledger, and none is behind the
    last closed phase unless the ledger lists it under `lagging:`, an allowance that
    is reported once it is no longer needed.

It verifies that the places agree, not that any of them is true: a status paragraph
can name the right phase and still describe it wrongly. Where each place is, and the
shape of its rows, is configuration (`phases:` in docsys.yaml). A project with no
`phases` section keeps no ledger and the check does not run. Findings come in the
order of their path, then their line.
"""

import re
from pathlib import Path
from typing import Final

from ..config import Config, Phases
from ..documents import documents, files
from ..findings import Finding, Rule
from ..yaml_frontmatter import Frontmatter, FrontmatterError, parse
from .hashes import FROZEN_STATUSES
from .ledger import Ledger, read

LEDGER: Final = Rule("phase-state/ledger", "error")
FOLDER: Final = Rule("phase-state/folder", "error")
TABLE: Final = Rule("phase-state/table", "error")
MENTION: Final = Rule("phase-state/mention", "error")
STATUS: Final = Rule("phase-state/status", "error")
FIELD: Final = Rule("phase-state/field", "error")
LAGGING: Final = Rule("phase-state/lagging", "error")
RULES: Final = (LEDGER, FOLDER, TABLE, MENTION, STATUS, FIELD, LAGGING)


def check(workspace: Path, config: Config) -> list[Finding]:
    phases = config["phases"]
    if phases is None:
        return []
    ledger, problems = read(workspace, config)
    if ledger is None:
        return [
            Finding(
                LEDGER.id,
                problems[0].path,
                1,
                f"`{phases['ledger']}` is missing or breaks its own rules, so there is nothing to compare with",
                "see the ledger check first",
            )
        ]
    texts: dict[str, str] = {}
    frontmatters: dict[str, Frontmatter | None] = {}
    for path in documents(workspace, config["scope"]):
        texts[path] = (workspace / path).read_text(encoding="utf-8")
        try:
            frontmatters[path] = parse(texts[path])
        except FrontmatterError:
            continue  # the frontmatter check reports it
    findings = _folders(ledger, phases, phases["ledger"], files(workspace))
    for table in phases["tables"]:
        findings += _table(ledger, phases, table["path"], re.compile(table["row"]), texts.get(table["path"], ""))
    frozen = {path for path, fm in frontmatters.items() if fm and fm.get("status", (None, 0))[0] in FROZEN_STATUSES}
    findings += _mentions(ledger, re.compile(phases["mention"]), texts, frozen)
    findings += _status(ledger, phases["status"]["path"], re.compile(phases["status"]["line"]), texts)
    findings += _fields(ledger, phases, frontmatters)
    return sorted(findings, key=lambda finding: (finding.path, finding.line))


def _folders(ledger: Ledger, phases: Phases, ledger_path: str, tracked: list[str]) -> list[Finding]:
    """A numbered phase without its folder; a phase folder the ledger does not list.
    A folder exists when a file is in it."""
    expected = {
        f"{phases['root']}/{entry.era}/{phases['folder'].format(number=number, name=entry.name)}": entry
        for number, entry in ledger.numbered().items()
    }
    depth = len(phases["root"].split("/")) + 2
    present = {"/".join(p.split("/")[:depth]) for p in tracked if p.startswith(phases["root"] + "/")}
    present = {p for p in present if p.count("/") + 1 == depth}
    findings: list[Finding] = []
    for path, entry in expected.items():
        if path not in present:
            findings.append(
                Finding(
                    FOLDER.id,
                    ledger_path,
                    entry.line,
                    f"phase {entry.number} ({entry.name}, {entry.status}) has no folder: `{path}` does not exist",
                    "create it, or correct the phase's era or name in the ledger",
                )
            )
    for path in sorted(present - set(expected)):
        findings.append(
            Finding(
                FOLDER.id,
                path,
                1,
                "a phase folder that is not in the ledger",
                "add its phase to the ledger, or move the folder to the path the ledger gives it",
            )
        )
    return findings


def _table(ledger: Ledger, phases: Phases, path: str, row: re.Pattern[str], text: str) -> list[Finding]:
    """Each phase row of one table against the ledger. The row pattern has the groups
    `number` (optional) and `marker` (optional, so a row without one is reported, not
    skipped)."""
    markers = phases["markers"]
    words = {"done": markers["done"], "current": markers["current"], "planned": markers["planned"]}
    by_number = ledger.numbered()
    current = ledger.current()
    rows = 0
    seen: set[int] = set()
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = row.match(line)
        if not match:
            continue
        rows += 1
        number, marker = match.group("number"), match.group("marker")
        if marker is None:
            findings.append(
                Finding(
                    TABLE.id,
                    path,
                    lineno,
                    "a phase row with no status marker",
                    f"add the ledger's status after the phase's name, e.g. `*({markers['done']})*`",
                )
            )
            continue
        word = marker.split(" — ")[0].strip()
        if number is None:
            if word != markers["planned"]:
                findings.append(
                    Finding(
                        TABLE.id,
                        path,
                        lineno,
                        f"an unnumbered row marked {word!r}; only a planned phase is unnumbered, "
                        f"and it is marked {markers['planned']!r}",
                        f"give the row its number, or mark it `*({markers['planned']})*`",
                    )
                )
            continue
        entry = by_number.get(int(number))
        if entry is None:
            findings.append(
                Finding(
                    TABLE.id,
                    path,
                    lineno,
                    f"phase {int(number)} is not numbered in the ledger; a planned phase has no number (ADR-038)",
                    "write the row without its number, or start the phase in the ledger",
                )
            )
            continue
        seen.add(int(number))
        want = words[entry.status]
        if word != want:
            findings.append(
                Finding(
                    TABLE.id,
                    path,
                    lineno,
                    f"phase {number} is marked {word!r}, but the ledger says {entry.status}",
                    f"mark it `*({want})*`",
                )
            )
    if rows == 0:
        return [
            Finding(
                TABLE.id,
                path,
                1,
                "no phase row matches the configured row pattern",
                "correct the row pattern for this table in docsys.yaml (`phases.tables`), or the table's rows",
            )
        ]
    if current.number not in seen:
        findings.append(
            Finding(
                TABLE.id,
                path,
                1,
                f"the current phase, phase {current.number} ({current.name}), has no row",
                f"add its row, marked `*({markers['current']})*`",
            )
        )
    return findings


def _mentions(ledger: Ledger, mention: re.Pattern[str], texts: dict[str, str], frozen: set[str]) -> list[Finding]:
    """A phase named by a number the ledger has not given. The pattern has the group
    `number`; a frozen record is not read."""
    highest = max(ledger.numbered())
    findings: list[Finding] = []
    for path in sorted(set(texts) - frozen):
        for lineno, line in enumerate(texts[path].splitlines(), 1):
            for match in mention.finditer(line):
                number = int(match.group("number"))
                if number > highest:
                    findings.append(
                        Finding(
                            MENTION.id,
                            path,
                            lineno,
                            f"{match.group(0)!r} names phase {number}, but the ledger numbers phases only up to "
                            f"{highest}; unstarted work is named, never numbered (ADR-038)",
                            "name the work instead, or start the phase in the ledger",
                        )
                    )
    return findings


def _status(ledger: Ledger, path: str, line: re.Pattern[str], texts: dict[str, str]) -> list[Finding]:
    """The one status line of `path` names the current phase. The pattern has the
    group `number`."""
    current = ledger.current()
    found = [
        (lineno, match)
        for lineno, text in enumerate(texts.get(path, "").splitlines(), 1)
        for match in [line.match(text)]
        if match
    ]
    if not found:
        return [
            Finding(
                STATUS.id,
                path,
                1,
                "no status line matches the configured pattern",
                "restore the status line, or correct `phases.status` in docsys.yaml",
            )
        ]
    if len(found) > 1:
        where = ", ".join(str(lineno) for lineno, _ in found)
        return [
            Finding(
                STATUS.id,
                path,
                found[1][0],
                f"{len(found)} status lines (lines {where})",
                "keep one, naming the current phase",
            )
        ]
    lineno, match = found[0]
    number = int(match.group("number"))
    if number != current.number:
        return [
            Finding(
                STATUS.id,
                path,
                lineno,
                f"the status line names phase {number}, but the current phase is {current.number} ({current.name})",
                f"rewrite the status paragraph for phase {current.number}",
            )
        ]
    return []


def _fields(ledger: Ledger, phases: Phases, frontmatters: dict[str, Frontmatter | None]) -> list[Finding]:
    """Each `phase:` value against the ledger. An allowance in `lagging:` must still
    be needed."""
    fmt = phases["field"]
    by_value = {fmt.format(number=number, name=entry.name): number for number, entry in ledger.numbered().items()}
    current = ledger.current()
    now = fmt.format(number=current.number, name=current.name)
    done = ledger.last_done()
    floor = fmt.format(number=done.number, name=done.name) if done else None
    allowed = {item.path: item.line for item in ledger.lagging}
    fields: dict[str, tuple[str, int]] = {}
    for path, frontmatter in frontmatters.items():
        value, line = (frontmatter or {}).get("phase", (None, 0))
        if value is not None:
            fields[path] = (str(value), line)
    findings: list[Finding] = []
    for path in sorted(fields):
        value, line = fields[path]
        number = by_value.get(value)
        behind = number is not None and done is not None and done.number is not None and number < done.number
        if number is None:
            findings.append(
                Finding(
                    FIELD.id,
                    path,
                    line,
                    f"`phase: {value}` is not a numbered phase in the ledger",
                    f"write the phase the document is current as of, e.g. `phase: {now}`",
                )
            )
        elif behind and path not in allowed:
            findings.append(
                Finding(
                    FIELD.id,
                    path,
                    line,
                    f"`phase: {value}` is behind {floor}, the last phase closed; a document is re-read and its "
                    "`phase:` raised when a phase closes",
                    f"re-read it whole and set `phase: {now}`, or list it under `lagging:` in the ledger with a reason",
                )
            )
        elif not behind and path in allowed:
            findings.append(
                Finding(
                    LAGGING.id,
                    phases["ledger"],
                    allowed[path],
                    f"{path} is listed as lagging but is no longer behind (`phase: {value}`)",
                    "remove its `lagging:` entry",
                )
            )
    for path in sorted(set(allowed) - set(fields)):
        findings.append(
            Finding(
                LAGGING.id,
                phases["ledger"],
                allowed[path],
                f"{path} is listed as lagging, but it has no `phase:` field",
                "remove the entry, or correct its path",
            )
        )
    return findings
