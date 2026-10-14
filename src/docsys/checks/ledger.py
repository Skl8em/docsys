"""The phase ledger check: where the project is, declared once, and the ledger's own
rules.

The current phase used to be implied in a dozen places, and nothing tied them
together. The ledger says it once: an ordered list of phases, each a name, an era
and a status of `done`, `current` or `planned`, and optionally a `lagging:` list of
the documents whose `phase:` may stay behind the last closed phase, each with a
reason. `phases.ledger` in docsys.yaml says where it is; a project with no `phases`
section keeps no ledger and the check does not run. That every other place agrees
with the ledger is the phase-state check's.

The ledger is read as YAML with every scalar a string, so a number is `"1"` here and
the rules say what a number is. When an entry is malformed the findings are those
about entries and about `lagging`, alone: the rules about order and numbering read
well-formed entries. Findings come in the order of their line.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..config import Config
from ..findings import Finding, Rule
from ..workspace import CONFIG_NAME
from ..yaml_frontmatter import Located, YamlError, load_located

MISSING: Final = Rule("ledger/missing", "error")
YAML: Final = Rule("ledger/yaml", "error")
SHAPE: Final = Rule("ledger/shape", "error")
FORM: Final = Rule("ledger/form", "error")
NUMBER: Final = Rule("ledger/number", "error")
UNIQUE: Final = Rule("ledger/unique", "error")
CURRENT: Final = Rule("ledger/current", "error")
ORDER: Final = Rule("ledger/order", "error")
LAGGING: Final = Rule("ledger/lagging", "error")
RULES: Final = (MISSING, YAML, SHAPE, FORM, NUMBER, UNIQUE, CURRENT, ORDER, LAGGING)

TOP_KEYS: Final = ("phases", "lagging")
LAG_KEYS: Final = ("path", "reason")
ENTRY_KEYS: Final = ("number", "name", "era", "status")
REQUIRED: Final = ("name", "era", "status")
STATUSES: Final = ("done", "current", "planned")  # in the order the list must follow
SLUG_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NUMBER_RE: Final = re.compile(r"^[1-9][0-9]*$")


@dataclass(frozen=True)
class Entry:
    """A phase of the ledger, well-formed but for what the order rules judge."""

    line: int
    name: str
    era: str
    status: str
    number: int | None


@dataclass(frozen=True)
class Lagging:
    """A document the ledger lets stay behind the last closed phase."""

    line: int
    path: str


@dataclass(frozen=True)
class Ledger:
    """A ledger that breaks none of its own rules: what the checks that compare other
    places with it read."""

    phases: list[Entry]
    lagging: list[Lagging]

    def numbered(self) -> dict[int, Entry]:
        return {entry.number: entry for entry in self.phases if entry.number is not None}

    def current(self) -> Entry:
        return next(entry for entry in self.phases if entry.status == "current")

    def last_done(self) -> Entry | None:
        done = [entry for entry in self.numbered().values() if entry.status == "done"]
        return max(done, key=lambda entry: entry.number or 0) if done else None


def check(workspace: Path, config: Config) -> list[Finding]:
    return sorted(read(workspace, config)[1], key=lambda finding: finding.line)


def read(workspace: Path, config: Config) -> tuple[Ledger | None, list[Finding]]:
    """The ledger, when the project keeps one and it breaks none of its rules; else
    None and the findings. A project with no `phases` section has neither."""
    phases = config["phases"]
    if phases is None:
        return None, []
    path = phases["ledger"]
    if not (workspace / path).is_file():
        return None, [
            Finding(
                MISSING.id,
                CONFIG_NAME,
                1,
                f"`phases.ledger` names `{path}`, which does not exist",
                f"restore it from git, or correct `phases.ledger` in {CONFIG_NAME}",
            )
        ]
    try:
        ledger = load_located((workspace / path).read_text(encoding="utf-8"))
    except YamlError as exc:
        return None, [
            Finding(YAML.id, path, exc.line, f"is not valid YAML ({exc.message})", "correct the YAML at that line")
        ]
    return _ledger(path, ledger)


def _finding(rule: Rule, path: str, line: int, message: str, fix: str) -> Finding:
    return Finding(rule.id, path, line, message, fix)


def _ledger(path: str, ledger: Located | None) -> tuple[Ledger | None, list[Finding]]:
    if ledger is None or not isinstance(ledger.value, dict):
        return None, [
            _finding(
                SHAPE,
                path,
                1,
                "must be a mapping with a `phases:` list",
                "write `phases:` and a list of the project's phases, in order",
            )
        ]
    top = ledger.value
    unknown = sorted(set(top) - set(TOP_KEYS))
    if unknown:
        return None, [
            _finding(
                SHAPE,
                path,
                top[key].line,
                f"unknown top-level key `{key}`",
                f"remove it; the vocabulary is closed: {list(TOP_KEYS)}",
            )
            for key in unknown
        ]
    if "phases" not in top:
        return None, [
            _finding(SHAPE, path, 1, "`phases` is missing", "add a `phases:` list of the project's phases, in order")
        ]
    listed = top["phases"]
    if not isinstance(listed.value, list) or not listed.value:
        return None, [
            _finding(
                SHAPE,
                path,
                listed.line,
                "`phases` must list at least one phase",
                "list the phases in order, one of them `current`",
            )
        ]
    findings: list[Finding] = []
    entries: list[Entry] = []
    for index, item in enumerate(listed.value):
        entry, problems = _entry(path, index, item)
        findings.extend(problems)
        if entry is not None:
            entries.append(entry)
    lagging_findings, lagging = _lagging(path, top["lagging"]) if "lagging" in top else ([], [])
    findings = findings or _order(path, listed.line, entries)
    findings = findings + lagging_findings
    return (None if findings else Ledger(entries, lagging)), findings


def _entry(path: str, index: int, item: Located) -> tuple[Entry | None, list[Finding]]:
    """One entry's own findings, and the entry itself when it has none."""
    where = f"`phases[{index}]`"
    if not isinstance(item.value, dict):
        return None, [
            _finding(
                SHAPE,
                path,
                item.line,
                f"{where} is not a mapping",
                "write it as `{number: N, name: …, era: …, status: …}`",
            )
        ]
    fields = item.value
    name = fields["name"].value if "name" in fields else None
    label = f"{where} ({name})" if isinstance(name, str) else where
    unknown = sorted(set(fields) - set(ENTRY_KEYS))
    if unknown:
        return None, [
            _finding(
                SHAPE,
                path,
                item.line,
                f"{label} has unknown key(s) {unknown}",
                f"remove them; allowed: {list(ENTRY_KEYS)}",
            )
        ]
    missing = [key for key in REQUIRED if key not in fields]
    if missing:
        return None, [
            _finding(
                SHAPE,
                path,
                item.line,
                f"{label} is missing {missing}",
                "add them; every phase has a name, an era and a status",
            )
        ]
    text = {key: located.value for key, located in fields.items()}
    findings: list[Finding] = []
    for key in ("name", "era"):
        word = text[key]
        if not isinstance(word, str) or not SLUG_RE.match(word):
            findings.append(
                _finding(
                    FORM,
                    path,
                    item.line,
                    f"{label} {key} {word!r} is not hyphen-cased (a-z, 0-9, -)",
                    "rewrite it in lowercase words joined by hyphens",
                )
            )
    status = text["status"]
    number = text.get("number")
    if status not in STATUSES:
        findings.append(
            _finding(
                FORM,
                path,
                item.line,
                f"{label} status {status!r} is not one of done, current or planned",
                "use one of the three",
            )
        )
    elif status == "planned" and "number" in fields:
        findings.append(
            _finding(
                NUMBER,
                path,
                item.line,
                f"{label} is planned and has a number; a planned phase has no number (ADR-038)",
                "remove `number`; it is given when the phase starts and becomes `current`",
            )
        )
    elif status != "planned" and "number" not in fields:
        findings.append(
            _finding(
                NUMBER,
                path,
                item.line,
                f"{label} is {status} and has no number",
                "add `number`, one more than the phase before it",
            )
        )
    if "number" in fields and (not isinstance(number, str) or not NUMBER_RE.match(number)):
        findings.append(
            _finding(
                FORM,
                path,
                item.line,
                f"{label} number {number!r} is not a positive integer",
                "write a bare number with no leading zero, e.g. `number: 6`",
            )
        )
    if findings or not isinstance(name, str) or not isinstance(status, str):
        return None, findings
    era = text["era"]
    if not isinstance(era, str):
        return None, findings
    return Entry(item.line, name, era, status, int(number) if isinstance(number, str) else None), findings


def _order(path: str, line: int, phases: list[Entry]) -> list[Finding]:
    """Findings across well-formed entries: uniqueness, one current, order, numbering."""
    findings: list[Finding] = []
    seen: set[str] = set()
    for index, phase in enumerate(phases):
        if phase.name in seen:
            findings.append(
                _finding(
                    UNIQUE,
                    path,
                    phase.line,
                    f"`phases[{index}]` name {phase.name!r} is a duplicate",
                    "give each phase its own name",
                )
            )
        seen.add(phase.name)
    current = [phase for phase in phases if phase.status == "current"]
    if len(current) != 1:
        findings.append(
            _finding(
                CURRENT,
                path,
                line,
                f"exactly one phase must be current, found {len(current)}",
                "mark the phase in progress `current`, and only that one",
            )
        )
    rank = [STATUSES.index(phase.status) for phase in phases]
    for index in range(1, len(phases)):
        if rank[index] < rank[index - 1]:
            findings.append(
                _finding(
                    ORDER,
                    path,
                    phases[index].line,
                    f"`phases[{index}]` ({phases[index].name}) is {phases[index].status} after a "
                    f"{phases[index - 1].status} phase; the order is every done, then the current, "
                    "then every planned",
                    "move it to its place in the list",
                )
            )
            break
    expected = 1
    for index, phase in enumerate(phases):
        if phase.number is None:
            continue
        if phase.number != expected:
            findings.append(
                _finding(
                    NUMBER,
                    path,
                    phase.line,
                    f"`phases[{index}]` ({phase.name}) has number {phase.number}, expected {expected}; "
                    "numbers count 1, 2, 3… in list order",
                    f"renumber it {expected}, or restore the missing phase",
                )
            )
            break
        expected += 1
    return findings


def _lagging(path: str, lagging: Located) -> tuple[list[Finding], list[Lagging]]:
    """The `lagging:` list's own findings: its shape, a reason for each, no duplicate."""
    if not isinstance(lagging.value, list):
        return [
            _finding(
                SHAPE,
                path,
                lagging.line,
                "`lagging` must be a list of `{path: …, reason: …}`",
                "write each document as a list item",
            )
        ], []
    findings: list[Finding] = []
    allowed: list[Lagging] = []
    seen: set[str] = set()
    for index, item in enumerate(lagging.value):
        where = f"`lagging[{index}]`"
        if not isinstance(item.value, dict):
            findings.append(
                _finding(SHAPE, path, item.line, f"{where} is not a mapping", "write it as `{path: …, reason: …}`")
            )
            continue
        fields = {key: located.value for key, located in item.value.items()}
        unknown = sorted(set(fields) - set(LAG_KEYS))
        if unknown:
            findings.append(
                _finding(
                    SHAPE,
                    path,
                    item.line,
                    f"{where} has unknown key(s) {unknown}",
                    f"remove them; allowed: {list(LAG_KEYS)}",
                )
            )
            continue
        document = fields.get("path")
        if not isinstance(document, str) or not document:
            findings.append(
                _finding(
                    SHAPE, path, item.line, f"{where} has no `path`", "name the document, relative to the workspace"
                )
            )
            continue
        reason = fields.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            findings.append(
                _finding(
                    LAGGING,
                    path,
                    item.line,
                    f"{where} ({document}) has no reason",
                    "say why it may lag and when it will be re-read; an exemption without a reason is not allowed",
                )
            )
        if document in seen:
            findings.append(
                _finding(UNIQUE, path, item.line, f"{where} {document!r} is a duplicate", "list each document once")
            )
        seen.add(document)
        allowed.append(Lagging(item.line, document))
    return findings, allowed
