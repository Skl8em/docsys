"""The configuration — the one reader of a workspace's `docsys.yaml`.

`docsys` knows how to check documentation; `docsys.yaml` says what it is pointed
at in one project: the format version, which documents the framework governs, the
root document, and — each optional, its checks running only when it is present —
the decision register, the paired-change rule and the phases.

The vocabulary is closed: an unknown section or key is an error, not a silently
ignored typo, and a section that is present must be complete. Scalars stay strings
(`docsys.yaml_frontmatter.StrictLoader`), so integer keys are converted here, and
refused when they are not integers. Every refusal starts with the file's name and
ends with a `fix:`, since the reader is often a machine with no other context.

The file is read as `object` and every value narrowed before it is kept, so what
`validate` returns is exactly the `Config` it is typed as.

    from docsys.config import load_config, in_scope
    cfg = load_config(workspace)
    cfg["register"]         # None when the project keeps no register
    in_scope(cfg["scope"], "docs/README.md")
"""

import os
import re
from collections.abc import Iterable, Sequence
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Final, TypedDict, TypeGuard

import yaml

from .findings import Severity
from .workspace import CONFIG_NAME
from .yaml_frontmatter import load_yaml


class Scope(TypedDict):
    include: list[str]  # patterns included back, over an exclusion
    exclude: dict[str, str]  # pattern -> why the documents it matches are excluded


class Allowance(TypedDict):
    document: str  # the document holding the link
    target: str  # the link's target as written, anchor included, title dropped
    reason: str  # why the link may stay dead


class Links(TypedDict):
    allow: list[Allowance]


class Register(TypedDict):
    path: str
    columns: int
    ordinal_column: int
    status_column: int
    ordinal_pattern: str
    superseded_pattern: str


class PairedChange(TypedDict):
    since: str
    mechanism: list[str]
    understanding: list[str]
    exempt: list[str]
    enforce_on: list[str]


class Markers(TypedDict):
    done: str
    current: str
    planned: str


class PhaseTable(TypedDict):
    path: str
    row: str


class StatusLine(TypedDict):
    path: str
    line: str


class Phases(TypedDict):
    ledger: str
    root: str
    folder: str
    field: str
    markers: Markers
    tables: list[PhaseTable]
    status: StatusLine
    mention: str


class Tool(TypedDict):
    name: str
    command: list[str]


class Config(TypedDict):
    version: str
    scope: Scope
    root_document: str
    links: Links
    register: Register | None
    paired_change: PairedChange | None
    phases: Phases | None
    rules: dict[str, Severity]  # rule id -> the severity that replaces its default
    tools: list[Tool]  # external commands `docsys check` runs after its own checks


# The formats of docsys.yaml this package reads — part of the cross-package API:
# every docsys package, in any language, reads the same files.
FORMAT_VERSIONS: Final = ("1",)

DEFAULT_ROOT_DOCUMENT: Final = "README.md"
SEVERITIES: Final[tuple[Severity, ...]] = ("error", "warning", "off")
NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RULE_ID_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$")
# The keys each section accepts are the fields of its type, in their order.
TOP_LEVEL: Final = tuple(Config.__annotations__)
# register.<key> -> number of capture groups its pattern must carry.
PATTERN_GROUPS: Final = {"ordinal_pattern": 2, "superseded_pattern": 1}


class ConfigError(ValueError):
    """The configuration is unusable. The message starts with the file's name and
    carries its `fix:`."""

    def __init__(self, message: str) -> None:
        super().__init__(f"{CONFIG_NAME}: {message}")


# --- narrowing a value read from YAML ---------------------------------------------

# `isinstance` narrows `object` to a dict or list of unknown items; these narrow it
# to items of type `object`, which is what YAML data is until each item is checked.


def _is_mapping(value: object) -> TypeGuard[dict[object, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _mapping(value: object, key: str, fix: str) -> dict[str, object]:
    if not _is_mapping(value):
        raise ConfigError(f"`{key}` must be a mapping — fix: {fix}.")
    checked: dict[str, object] = {}
    for name, item in value.items():
        if not isinstance(name, str):
            raise ConfigError(f"`{key}` has a key {name!r} that is not a name — fix: write it as a word.")
        checked[name] = item
    return checked


def _section(value: object, name: str, keys: Sequence[str]) -> dict[str, object]:
    """A section, which must carry exactly `keys`."""
    section = _mapping(value, name, f"give it the keys {list(keys)}, or remove it to turn its checks off")
    for key in keys:
        if key not in section:
            raise ConfigError(f"`{name}.{key}` is missing — fix: add it to the `{name}` section.")
    extra = sorted(set(section) - set(keys))
    if extra:
        raise ConfigError(f"`{name}` has unknown key(s) {extra} — fix: remove them; allowed: {list(keys)}.")
    return section


def _string(value: object, key: str, fix: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"`{key}` must be a non-empty string — fix: {fix}.")
    return value


def _string_list(value: object, key: str) -> list[str]:
    if not _is_list(value):
        raise ConfigError(f"`{key}` must be a list of strings — fix: write it as `{key.split('.')[-1]}: [a, b]`.")
    checked: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(
                f"`{key}` must be a list of strings, and holds {item!r} — fix: write it as "
                f"`{key.split('.')[-1]}: [a, b]`."
            )
        checked.append(item)
    return checked


def _relative_path(value: object, key: str, example: str) -> str:
    """A path relative to the workspace, staying inside it."""
    if not isinstance(value, str) or not value:
        raise ConfigError(f"`{key}` must be a path — fix: write it as `{key.split('.')[-1]}: {example}`.")
    if value.startswith("/") or ".." in PurePosixPath(value).parts:
        raise ConfigError(
            f"`{key}`: `{value}` must be relative to the workspace and stay inside it — "
            f"fix: write it from the folder holding {CONFIG_NAME}, without a leading `/` or `..`."
        )
    return value


def _integer(value: object, key: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    raise ConfigError(
        f"`{key}` must be an integer, got {value!r} — fix: write a bare number, e.g. `{key.split('.')[-1]}: 4`."
    )


def _regex(value: object, key: str, named: Sequence[str] = (), groups: int | None = None) -> str:
    """A regular expression that compiles, carries the `named` groups and, when
    `groups` is given, exactly that many capture groups."""
    if not isinstance(value, str):
        raise ConfigError(f"`{key}` must be a regular expression, got {value!r} — fix: write it as a quoted string.")
    try:
        compiled = re.compile(value)
    except re.error as exc:
        raise ConfigError(f"`{key}` is not a valid regular expression ({exc}) — fix: correct the pattern.") from None
    missing = [g for g in named if g not in compiled.groupindex]
    if missing:
        raise ConfigError(f"`{key}` must have the named group(s) {missing} — fix: write them as `(?P<name>…)`.")
    if groups is not None and compiled.groups != groups:
        raise ConfigError(
            f"`{key}` must have exactly {groups} capture group(s) "
            f"(found {compiled.groups}) — fix: wrap the part to extract in ( )."
        )
    return value


# --- the sections -----------------------------------------------------------------


def _version(cfg: dict[str, object]) -> str:
    if "version" not in cfg:
        raise ConfigError(f"`version` is missing — fix: add `version: {FORMAT_VERSIONS[-1]}` at the top.")
    version = cfg["version"]
    if not isinstance(version, str) or version not in FORMAT_VERSIONS:
        raise ConfigError(
            f"`version` is {version!r}, and this docsys reads version(s) "
            f"{', '.join(FORMAT_VERSIONS)} — fix: install a docsys that reads it, "
            f"or write the file in version {FORMAT_VERSIONS[-1]}."
        )
    return version


def _pattern(value: str, key: str) -> str:
    if not value:
        raise ConfigError(f"`{key}` holds an empty pattern — fix: remove it.")
    return _relative_path(value, key, "docs/")


def _scope(cfg: dict[str, object]) -> Scope:
    raw = _mapping(
        cfg.get("scope", {}), "scope", "write it as `scope: {exclude: {<pattern>: <reason>}, include: [<pattern>]}`"
    )
    keys = tuple(Scope.__annotations__)
    extra = sorted(set(raw) - set(keys))
    if extra:
        raise ConfigError(f"`scope` has unknown key(s) {extra} — fix: remove them; allowed: {list(keys)}.")
    include = [_pattern(p, "scope.include") for p in _string_list(raw.get("include", []), "scope.include")]
    exclude: dict[str, str] = {}
    fix = "write each exclusion as `<pattern>: <reason>`, the reason saying why it is excluded"
    for pattern, reason in _mapping(raw.get("exclude", {}), "scope.exclude", f"{fix}, under `exclude:`").items():
        if not isinstance(reason, str) or not reason.strip():
            raise ConfigError(f"`scope.exclude` gives `{pattern}` no reason — fix: {fix}.")
        exclude[_pattern(pattern, "scope.exclude")] = reason
    return Scope(include=include, exclude=exclude)


def _links(value: object) -> Links:
    raw = _mapping(value, "links", "write it as `links: {allow: [{document: …, target: …, reason: …}]}`")
    keys = tuple(Links.__annotations__)
    extra = sorted(set(raw) - set(keys))
    if extra:
        raise ConfigError(f"`links` has unknown key(s) {extra} — fix: remove them; allowed: {list(keys)}.")
    allow_fix = "write each allowance as `- document: …`, `target: …` and `reason: …`, under `allow:`"
    items = raw.get("allow", [])
    if not _is_list(items):
        raise ConfigError(f"`links.allow` must be a list — fix: {allow_fix}.")
    allow: list[Allowance] = []
    for index, item in enumerate(items):
        where = f"links.allow[{index}]"
        entry = _section(item, where, tuple(Allowance.__annotations__))
        document = _relative_path(entry["document"], f"{where}.document", "docs/a.md")
        target = _string(entry["target"], f"{where}.target", "write the link's target as it is written in the document")
        reason = _string(entry["reason"], f"{where}.reason", "say why the link may stay dead")
        if not reason.strip():
            raise ConfigError(f"`{where}.reason` must be non-empty — fix: say why the link may stay dead.")
        if any(a["document"] == document and a["target"] == target for a in allow):
            raise ConfigError(
                f"`{where}` allows `{target}` in `{document}` twice — fix: keep one allowance for each link."
            )
        allow.append(Allowance(document=document, target=target, reason=reason))
    return Links(allow=allow)


def _register(value: object) -> Register:
    raw = _section(value, "register", tuple(Register.__annotations__))
    columns = _integer(raw["columns"], "register.columns")
    ordinal_column = _integer(raw["ordinal_column"], "register.ordinal_column")
    status_column = _integer(raw["status_column"], "register.status_column")
    for key, column in (("ordinal_column", ordinal_column), ("status_column", status_column)):
        if not 0 <= column < columns:
            raise ConfigError(
                f"`register.{key}` ({column}) is outside the row: `register.columns` is "
                f"{columns}, so columns are numbered 0–{columns - 1} — fix: correct one of them."
            )
    patterns = {key: _regex(raw[key], f"register.{key}", groups=groups) for key, groups in PATTERN_GROUPS.items()}
    return Register(
        path=_string(raw["path"], "register.path", "name the register's file"),
        columns=columns,
        ordinal_column=ordinal_column,
        status_column=status_column,
        ordinal_pattern=patterns["ordinal_pattern"],
        superseded_pattern=patterns["superseded_pattern"],
    )


def _paired_change(value: object) -> PairedChange:
    raw = _section(value, "paired_change", tuple(PairedChange.__annotations__))
    since = raw["since"]
    if not isinstance(since, str) or not re.fullmatch(r"[0-9a-f]{7,40}", since):
        raise ConfigError(
            f"`paired_change.since` must be a commit id (7–40 lowercase hex digits), "
            f"got {since!r} — fix: write the id of the commit after which the rule applies."
        )
    lists = {
        key: _string_list(raw[key], f"paired_change.{key}")
        for key in ("mechanism", "understanding", "exempt", "enforce_on")
    }
    consequence = {
        "mechanism": "the rule would never fire",
        "understanding": "the rule would never pass",
        "enforce_on": "the rule would never fail",
    }
    for key, why in consequence.items():
        if not lists[key]:
            raise ConfigError(
                f"`paired_change.{key}` must list at least one entry — {why}; "
                f"fix: add one, or remove `paired_change` to turn the rule off."
            )
    return PairedChange(
        since=since,
        mechanism=lists["mechanism"],
        understanding=lists["understanding"],
        exempt=lists["exempt"],
        enforce_on=lists["enforce_on"],
    )


def _phase_format(value: object, key: str) -> str:
    if not isinstance(value, str) or "{number" not in value or "{name" not in value:
        raise ConfigError(
            f"`phases.{key}` must contain `{{number…}}` and `{{name}}` — "
            f"fix: write it as e.g. `{key}: 'phase-{{number:02d}}-{{name}}'`."
        )
    try:
        value.format(number=1, name="x")
    except (KeyError, IndexError, ValueError) as exc:
        raise ConfigError(
            f"`phases.{key}` does not format with a number and a name ({exc!r}) — "
            f"fix: use only `{{number…}}` and `{{name}}`."
        ) from None
    return value


def _markers(value: object) -> Markers:
    statuses = tuple(Markers.__annotations__)
    fix = "write it as `markers: {done: …, current: …, planned: …}`"
    raw = _mapping(value, "phases.markers", fix)
    words = {status: raw.get(status) for status in statuses}
    if set(raw) != set(statuses) or not all(isinstance(w, str) and w for w in words.values()):
        raise ConfigError(
            f"`phases.markers` must map each of {list(statuses)} to the word a table shows for it — fix: {fix}."
        )
    checked = {status: _string(word, f"phases.markers.{status}", fix) for status, word in words.items()}
    if len(set(checked.values())) != len(statuses):
        raise ConfigError(
            "`phases.markers` must give each status a distinct word, or a table row would "
            "not say which status it means — fix: change the repeated word."
        )
    return Markers(done=checked["done"], current=checked["current"], planned=checked["planned"])


def _tables(value: object) -> list[PhaseTable]:
    if not _is_list(value) or not value:
        raise ConfigError(
            "`phases.tables` must list at least one table, or the phase-state check would "
            "compare the ledger with nothing — fix: add the table that lists the phases."
        )
    tables: list[PhaseTable] = []
    for index, item in enumerate(value):
        where = f"phases.tables[{index}]"
        fix = "write it as `{path: <file>, row: <pattern>}`"
        table = _mapping(item, where, fix)
        if set(table) != {"path", "row"}:
            extra = sorted(set(table) - {"path", "row"})
            raise ConfigError(
                f"`{where}` must have exactly `path` and `row`"
                + (f"; unknown key(s) {extra}" if extra else "")
                + f" — fix: {fix}."
            )
        tables.append(
            PhaseTable(
                path=_string(table["path"], f"{where}.path", "name the file"),
                row=_regex(table["row"], f"{where}.row", named=("number", "marker")),
            )
        )
    return tables


def _status(value: object) -> StatusLine:
    fix = "name the file holding the status line, and the pattern that finds it"
    status = _mapping(value, "phases.status", fix)
    if set(status) != {"path", "line"}:
        raise ConfigError(f"`phases.status` must have exactly `path` and `line` — fix: {fix}.")
    return StatusLine(
        path=_string(status["path"], "phases.status.path", fix),
        line=_regex(status["line"], "phases.status.line", named=("number",)),
    )


def _phases(value: object) -> Phases:
    raw = _section(value, "phases", tuple(Phases.__annotations__))
    paths = {
        key: _string(raw[key], f"phases.{key}", f"write it as a path relative to the workspace, `{key}: <dir>/<file>`")
        for key in ("ledger", "root")
    }
    return Phases(
        ledger=paths["ledger"],
        root=paths["root"],
        folder=_phase_format(raw["folder"], "folder"),
        field=_phase_format(raw["field"], "field"),
        markers=_markers(raw["markers"]),
        tables=_tables(raw["tables"]),
        status=_status(raw["status"]),
        mention=_regex(raw["mention"], "phases.mention", named=("number",)),
    )


def _severity(value: object) -> Severity | None:
    for severity in SEVERITIES:
        if value == severity:
            return severity
    return None


def _rules(value: object) -> dict[str, Severity]:
    """Which rules the project turns up or down. Whether each id names a rule is
    for `docsys.rules.severities`, which knows the checks; this reads the form."""
    fix = "write each as `<check>/<rule>: error`, `warning` or `off`, under `rules:`"
    checked: dict[str, Severity] = {}
    for rule, setting in _mapping(value, "rules", fix).items():
        if not RULE_ID_RE.match(rule):
            raise ConfigError(f"`rules.{rule}` is not named `<check>/<rule>` — fix: {fix}.")
        severity = _severity(setting)
        if severity is None:
            raise ConfigError(
                f"`rules.{rule}` is {setting!r}, which is not a severity — fix: write `error`, `warning` or `off`."
            )
        checked[rule] = severity
    return checked


def _tools(value: object) -> list[Tool]:
    fix = "write each as `- name: <word>` and `command: [<program>, <argument>, ...]`, under `tools:`"
    if not _is_list(value):
        raise ConfigError(f"`tools` must be a list — fix: {fix}.")
    tools: list[Tool] = []
    for index, item in enumerate(value):
        where = f"tools[{index}]"
        entry = _section(item, where, tuple(Tool.__annotations__))
        name = _string(entry["name"], f"{where}.name", "give it a name, such as `markdownlint`")
        if not NAME_RE.match(name):
            raise ConfigError(
                f"`{where}.name` is {name!r}, which is not hyphen-cased — fix: write it in lowercase words "
                "joined by hyphens, such as `markdownlint`."
            )
        if any(tool["name"] == name for tool in tools):
            raise ConfigError(f"`{where}.name`: `{name}` is named twice — fix: give each tool its own name.")
        command = _string_list(entry["command"], f"{where}.command")
        if not command or not all(command):
            raise ConfigError(
                f"`{where}.command` is empty or holds an empty word — fix: write the program, then each argument "
                "as its own item, such as `[markdownlint-cli2, --fix]`."
            )
        tools.append(Tool(name=name, command=command))
    return tools


def validate(raw: object) -> Config:
    """Check a loaded configuration and return it normalised: integer keys
    converted, `root_document` and `scope.exclude` defaulted, and every optional
    section present, None when it is off. The input is not changed. Raises
    ConfigError."""
    if not _is_mapping(raw):
        raise ConfigError(
            f"must be a mapping of sections — fix: start from `version: {FORMAT_VERSIONS[-1]}` "
            f"and `scope: {{include: [<folder>/]}}`."
        )
    cfg = _mapping(raw, "the file", "write each section as `name:` at the start of a line")
    unknown = sorted(set(cfg) - set(TOP_LEVEL))
    if unknown:
        raise ConfigError(
            f"unknown section(s) {unknown} — fix: remove them; the vocabulary is closed: {list(TOP_LEVEL)}."
        )
    return Config(
        version=_version(cfg),
        scope=_scope(cfg),
        root_document=_relative_path(
            cfg.get("root_document", DEFAULT_ROOT_DOCUMENT), "root_document", DEFAULT_ROOT_DOCUMENT
        ),
        links=_links(cfg.get("links", {})),
        register=_register(cfg["register"]) if "register" in cfg else None,
        paired_change=_paired_change(cfg["paired_change"]) if "paired_change" in cfg else None,
        phases=_phases(cfg["phases"]) if "phases" in cfg else None,
        rules=_rules(cfg.get("rules", {})),
        tools=_tools(cfg.get("tools", [])),
    )


def load_config(workspace: str | os.PathLike[str]) -> Config:
    """Read and validate `docsys.yaml` in the workspace."""
    path = Path(workspace) / CONFIG_NAME
    try:
        with open(path, encoding="utf-8") as fh:
            raw = load_yaml(fh)
    except FileNotFoundError:
        raise ConfigError(
            f"not found in {workspace} — fix: run `docsys init` there, or pass the workspace that holds it."
        ) from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"is not valid YAML ({exc}) — fix: correct the line it names.") from None
    return validate(raw)


# --- the scope --------------------------------------------------------------------


@cache
def _compile(pattern: str) -> re.Pattern[str]:
    """A scope pattern as a regular expression over a workspace-relative path.
    `**` spans any number of folders, `*` and `?` stay within one, and a trailing
    `/` names everything below the folder."""
    if pattern.endswith("/"):
        pattern += "**"
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def in_scope(scope: Scope, path: str) -> bool:
    """Does the framework govern `path`, a workspace-relative POSIX path? Every
    document is governed by default; an `exclude` pattern takes it out, and an
    `include` pattern brings it back."""

    def matches(patterns: Iterable[str]) -> bool:
        return any(_compile(p).fullmatch(path) for p in patterns)

    return matches(scope["include"]) or not matches(scope["exclude"])


def exclusion(scope: Scope, path: str) -> tuple[str, str] | None:
    """The first exclusion that takes `path` out of the scope, as its pattern and
    its reason; None when the document is in scope."""
    if in_scope(scope, path):
        return None
    for pattern, reason in scope["exclude"].items():
        if _compile(pattern).fullmatch(path):
            return pattern, reason
    return None


def covers_folder(scope: Scope, folder: str) -> bool:
    """Does the scope leave out everything below `folder`, a workspace-relative POSIX
    path, so that no walk need enter it? An exclusion covers it only when it matches
    files and subfolders of any name, and no inclusion could reach into it: an
    inclusion is taken to reach in unless the literal text before its first wildcard
    rules the folder out. When in doubt the answer is no, and the walk goes on."""
    below = folder + "/"
    for pattern in scope["include"]:
        literal = re.split(r"[*?]", pattern, maxsplit=1)[0]
        if below.startswith(literal) or literal.startswith(below):
            return False
    probes = (below + "\x01/\x01.md", below + "\x01.txt")
    return any(all(_compile(pattern).fullmatch(probe) for probe in probes) for pattern in scope["exclude"])
