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

    from docsys.config import load_config, in_scope
    cfg = load_config(workspace)
    cfg["register"]         # None when the project keeps no register
    in_scope(cfg["scope"], "docs/README.md")
"""
import copy
import re
from functools import lru_cache
from pathlib import Path, PurePosixPath

import yaml

from .workspace import CONFIG_NAME
from .yaml_frontmatter import StrictLoader

# The formats of docsys.yaml this package reads — part of the cross-package API:
# every docsys package, in any language, reads the same files.
FORMAT_VERSIONS = ("1",)

DEFAULT_ROOT_DOCUMENT = "README.md"
SCOPE_KEYS = ("include", "exclude")
OPTIONAL_SECTIONS = {
    "register": ("path", "columns", "ordinal_column", "status_column",
                 "ordinal_pattern", "superseded_pattern"),
    "paired_change": ("since", "mechanism", "understanding", "exempt", "enforce_on"),
    "phases": ("ledger", "root", "folder", "field", "markers", "tables", "status", "mention"),
}
TOP_LEVEL = ("version", "scope", "root_document", *OPTIONAL_SECTIONS)
# register.<key> -> number of capture groups its pattern must carry.
PATTERN_GROUPS = {"ordinal_pattern": 2, "superseded_pattern": 1}


class ConfigError(ValueError):
    """The configuration is unusable. The message starts with the file's name and
    carries its `fix:`."""

    def __init__(self, message):
        super().__init__(f"{CONFIG_NAME}: {message}")


def _string_list(value, key):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"`{key}` must be a list of strings — fix: write it as "
                          f"`{key.split('.')[-1]}: [a, b]`.")


def _relative_path(value, key, example):
    """A path relative to the workspace, staying inside it."""
    if not isinstance(value, str) or not value:
        raise ConfigError(f"`{key}` must be a path — fix: write it as `{key.split('.')[-1]}: {example}`.")
    if value.startswith("/") or ".." in PurePosixPath(value).parts:
        raise ConfigError(f"`{key}`: `{value}` must be relative to the workspace and stay inside it — "
                          f"fix: write it from the folder holding {CONFIG_NAME}, without a leading `/` or `..`.")


def _integer(value, key):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"`{key}` must be an integer, got {value!r} — fix: write a bare number, "
                          f"e.g. `{key.split('.')[-1]}: 4`.") from None


def _section(cfg, name, keys):
    section = cfg[name]
    if not isinstance(section, dict):
        raise ConfigError(f"`{name}` must be a mapping — fix: give it the keys {list(keys)}, "
                          f"or remove it to turn its checks off.")
    for key in keys:
        if key not in section:
            raise ConfigError(f"`{name}.{key}` is missing — fix: add it to the `{name}` section.")
    extra = sorted(set(section) - set(keys))
    if extra:
        raise ConfigError(f"`{name}` has unknown key(s) {extra} — fix: remove them; allowed: {list(keys)}.")


def _validate_version(cfg):
    if "version" not in cfg:
        raise ConfigError(f"`version` is missing — fix: add `version: {FORMAT_VERSIONS[-1]}` at the top.")
    version = cfg["version"]
    if version not in FORMAT_VERSIONS:
        raise ConfigError(f"`version` is {version!r}, and this docsys reads version(s) "
                          f"{', '.join(FORMAT_VERSIONS)} — fix: install a docsys that reads it, "
                          f"or write the file in version {FORMAT_VERSIONS[-1]}.")


def _validate_scope(cfg):
    if "scope" not in cfg:
        raise ConfigError("`scope` is missing — fix: add `scope: {include: [<folder>/]}`, naming the "
                          "documents the framework governs.")
    scope = cfg["scope"]
    if not isinstance(scope, dict):
        raise ConfigError("`scope` must be a mapping — fix: write it as `scope: {include: [<folder>/]}`.")
    extra = sorted(set(scope) - set(SCOPE_KEYS))
    if extra:
        raise ConfigError(f"`scope` has unknown key(s) {extra} — fix: remove them; allowed: {list(SCOPE_KEYS)}.")
    if "include" not in scope:
        raise ConfigError("`scope.include` is missing — fix: list the folders and files the framework governs.")
    scope.setdefault("exclude", [])
    for key in SCOPE_KEYS:
        _string_list(scope[key], f"scope.{key}")
        for pattern in scope[key]:
            if not pattern:
                raise ConfigError(f"`scope.{key}` holds an empty pattern — fix: remove it.")
            _relative_path(pattern, f"scope.{key}", "[docs/]")
    if not scope["include"]:
        raise ConfigError("`scope.include` must list at least one pattern — the gate would check nothing; "
                          "fix: name the folders and files the framework governs.")


def _validate_register(reg):
    for key in ("columns", "ordinal_column", "status_column"):
        reg[key] = _integer(reg[key], f"register.{key}")
    for key in ("ordinal_column", "status_column"):
        if not 0 <= reg[key] < reg["columns"]:
            raise ConfigError(
                f"`register.{key}` ({reg[key]}) is outside the row: `register.columns` is "
                f"{reg['columns']}, so columns are numbered 0–{reg['columns'] - 1} — fix: correct one of them.")
    for key, groups in PATTERN_GROUPS.items():
        try:
            compiled = re.compile(reg[key])
        except (re.error, TypeError) as exc:
            raise ConfigError(f"`register.{key}` is not a valid regular expression ({exc}) — "
                              f"fix: correct the pattern.") from None
        if compiled.groups != groups:
            raise ConfigError(f"`register.{key}` must have exactly {groups} capture group(s) "
                              f"(found {compiled.groups}) — fix: wrap the part to extract in ( ).")


def _validate_paired_change(pc):
    if not isinstance(pc["since"], str) or not re.fullmatch(r"[0-9a-f]{7,40}", pc["since"]):
        raise ConfigError(f"`paired_change.since` must be a commit id (7–40 lowercase hex digits), "
                          f"got {pc['since']!r} — fix: write the id of the commit after which the rule applies.")
    for key in ("mechanism", "understanding", "exempt", "enforce_on"):
        _string_list(pc[key], f"paired_change.{key}")
    consequence = {"mechanism": "the rule would never fire", "understanding": "the rule would never pass",
                   "enforce_on": "the rule would never fail"}
    for key, why in consequence.items():
        if not pc[key]:
            raise ConfigError(f"`paired_change.{key}` must list at least one entry — {why}; "
                              f"fix: add one, or remove `paired_change` to turn the rule off.")


def _pattern(value, key, groups):
    """A regular expression that compiles and carries the named `groups`."""
    try:
        compiled = re.compile(value)
    except (re.error, TypeError) as exc:
        raise ConfigError(f"`{key}` is not a valid regular expression ({exc}) — fix: correct the pattern.") from None
    missing = [g for g in groups if g not in compiled.groupindex]
    if missing:
        raise ConfigError(f"`{key}` must have the named group(s) {missing} — fix: write them as `(?P<name>…)`.")


def _validate_phases(ph):
    for key in ("ledger", "root"):
        if not isinstance(ph[key], str) or not ph[key]:
            raise ConfigError(f"`phases.{key}` must be a path, relative to the workspace — "
                              f"fix: write it as `{key}: <dir>/<file>`.")
    for key in ("folder", "field"):
        fmt = ph[key]
        if not isinstance(fmt, str) or "{number" not in fmt or "{name" not in fmt:
            raise ConfigError(f"`phases.{key}` must contain `{{number…}}` and `{{name}}` — "
                              f"fix: write it as e.g. `{key}: 'phase-{{number:02d}}-{{name}}'`.")
        try:
            fmt.format(number=1, name="x")
        except (KeyError, IndexError, ValueError) as exc:
            raise ConfigError(f"`phases.{key}` does not format with a number and a name ({exc!r}) — "
                              f"fix: use only `{{number…}}` and `{{name}}`.") from None
    markers = ph["markers"]
    statuses = ("done", "current", "planned")
    if not isinstance(markers, dict) or set(markers) != set(statuses) \
            or not all(isinstance(v, str) and v for v in markers.values()):
        raise ConfigError(f"`phases.markers` must map each of {list(statuses)} to the word a table shows for it "
                          f"— fix: write it as `markers: {{done: …, current: …, planned: …}}`.")
    if len(set(markers.values())) != len(statuses):
        raise ConfigError("`phases.markers` must give each status a distinct word, or a table row would "
                          "not say which status it means — fix: change the repeated word.")
    tables = ph["tables"]
    if not isinstance(tables, list) or not tables:
        raise ConfigError("`phases.tables` must list at least one table, or the phase-state check would "
                          "compare the ledger with nothing — fix: add the table that lists the phases.")
    for index, table in enumerate(tables):
        where = f"phases.tables[{index}]"
        if not isinstance(table, dict) or set(table) != {"path", "row"}:
            extra = sorted(set(table) - {"path", "row"}) if isinstance(table, dict) else []
            raise ConfigError(f"`{where}` must have exactly `path` and `row`"
                              + (f"; unknown key(s) {extra}" if extra else "")
                              + " — fix: write it as `{path: <file>, row: <pattern>}`.")
        _pattern(table["row"], f"{where}.row", ("number", "marker"))
    status = ph["status"]
    if not isinstance(status, dict) or set(status) != {"path", "line"}:
        raise ConfigError("`phases.status` must have exactly `path` and `line` — fix: name the file holding "
                          "the status line, and the pattern that finds it.")
    _pattern(status["line"], "phases.status.line", ("number",))
    _pattern(ph["mention"], "phases.mention", ("number",))


VALIDATORS = {"register": _validate_register, "paired_change": _validate_paired_change,
              "phases": _validate_phases}


def validate(raw):
    """Check a loaded configuration and return a normalised copy: integer keys
    converted, `root_document` and `scope.exclude` defaulted, and every optional
    section present, None when it is off. Raises ConfigError."""
    if not isinstance(raw, dict):
        raise ConfigError(f"must be a mapping of sections — fix: start from `version: {FORMAT_VERSIONS[-1]}` "
                          f"and `scope: {{include: [<folder>/]}}`.")
    cfg = copy.deepcopy(raw)
    unknown = sorted(set(cfg) - set(TOP_LEVEL))
    if unknown:
        raise ConfigError(f"unknown section(s) {unknown} — fix: remove them; the vocabulary is closed: "
                          f"{list(TOP_LEVEL)}.")
    _validate_version(cfg)
    _validate_scope(cfg)
    cfg.setdefault("root_document", DEFAULT_ROOT_DOCUMENT)
    _relative_path(cfg["root_document"], "root_document", DEFAULT_ROOT_DOCUMENT)
    for name, keys in OPTIONAL_SECTIONS.items():
        if name not in cfg:
            cfg[name] = None
            continue
        _section(cfg, name, keys)
        VALIDATORS[name](cfg[name])
    return cfg


def load_config(workspace):
    """Read and validate `docsys.yaml` in the workspace."""
    path = Path(workspace) / CONFIG_NAME
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.load(fh, Loader=StrictLoader)
    except FileNotFoundError:
        raise ConfigError(f"not found in {workspace} — fix: run `docsys init` there, "
                          f"or pass the workspace that holds it.") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"is not valid YAML ({exc}) — fix: correct the line it names.") from None
    return validate(raw)


@lru_cache(maxsize=None)
def _compile(pattern):
    """A scope pattern as a regular expression over a workspace-relative path.
    `**` spans any number of folders, `*` and `?` stay within one, and a trailing
    `/` names everything below the folder."""
    if pattern.endswith("/"):
        pattern += "**"
    out, i = [], 0
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


def in_scope(scope, path):
    """Does the framework govern `path`, a workspace-relative POSIX path? It must
    match an `include` pattern and no `exclude` pattern."""
    def matches(patterns):
        return any(_compile(p).fullmatch(path) for p in patterns)
    return matches(scope["include"]) and not matches(scope["exclude"])
