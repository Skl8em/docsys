"""The configuration, `docsys.yaml`: a format version, the scope of the documents
the framework governs (every document, unless excluded with a reason, or excluded
and then included back), the root document, and three optional sections — the
decision register, the paired-change rule, the phases — whose checks run only when
they are present. The vocabulary is closed, and every refusal names the file, the
key and the fix."""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import TypeGuard

import pytest

from docsys.config import ConfigError, Scope, covers_folder, in_scope, load_config, validate
from docsys.workspace import CONFIG_NAME

# A configuration as read from YAML, before validation: built malformed on purpose,
# so it is typed as what `validate` accepts, not as the `Config` it returns.
Raw = dict[str, object]
Mutation = Callable[[Raw], None]

MINIMAL: Raw = {"version": "1"}

REGISTER: dict[str, str] = {
    "path": "log.md",
    "columns": "5",
    "ordinal_column": "0",
    "status_column": "4",
    "ordinal_pattern": r"^\[(\d+)\]\(([^)]+)\)$",
    "superseded_pattern": r"superseded by (\d+)",
}
LINKS: Raw = {
    "allow": [
        {
            "document": "records/old.md",
            "target": "../tools/gone.py",
            "reason": "retired with tools/; the record is frozen",
        },
        {"document": "records/old.md", "target": "gone.md#part", "reason": "moved to another repository"},
    ]
}
PAIRED_CHANGE: Raw = {
    "since": "0123456789abcdef0123456789abcdef01234567",
    "mechanism": ["engine/"],
    "understanding": ["docs/", "ARCHITECTURE.md"],
    "exempt": ["engine/test_"],
    "enforce_on": ["trunk"],
}
PHASES: Raw = {
    "ledger": "state/phases.yaml",
    "root": "records",
    "folder": "phase-{number:02d}-{name}",
    "field": "{number:02d}-{name}",
    "markers": {"done": "done", "current": "in progress", "planned": "unnumbered"},
    "tables": [{"path": "plan/roadmap.md", "row": r"^\| (?P<number>\d+)? ?\*\((?P<marker>[^)]*)\)\*"}],
    "status": {"path": "INDEX.md", "line": r"^\*\*Phase (?P<number>\d+)\*\*"},
    "mention": r"\bPhase (?P<number>\d+)",
}
FULL: Raw = {
    "version": "1",
    "scope": {
        "exclude": {"raw/": "upstream essays, not authored here", "**/transcripts/": "raw agent output"},
        "include": ["raw/README.md"],
    },
    "root_document": "docs/README.md",
    "links": LINKS,
    "register": REGISTER,
    "paired_change": PAIRED_CHANGE,
    "phases": PHASES,
    "rules": {"links/resolve": "warning", "hashes/unsealed": "error", "frontmatter/open": "off"},
    "tools": [
        {"name": "markdownlint", "command": ["markdownlint-cli2"]},
        {"name": "spelling", "command": ["codespell", "--quiet-level", "2"]},
    ],
}


def full_with(mutate: Mutation) -> Raw:
    cfg = copy.deepcopy(FULL)
    mutate(cfg)
    return cfg


def is_raw(value: object) -> TypeGuard[Raw]:
    return isinstance(value, dict)


def unchanged(cfg: Raw) -> None:
    pass


def section_of(cfg: Raw, section: str) -> Raw:
    value = cfg[section]
    assert is_raw(value)
    return value


def drop(section: str, key: str | None = None) -> Mutation:
    def go(cfg: Raw) -> None:
        if key is None:
            del cfg[section]
        else:
            del section_of(cfg, section)[key]

    return go


def setter(section: str, key: str | None, value: object) -> Mutation:
    def go(cfg: Raw) -> None:
        if key is None:
            cfg[section] = value
        else:
            section_of(cfg, section)[key] = value

    return go


# --- what a valid configuration reads as ------------------------------------------


def test_a_minimal_configuration_turns_the_optional_checks_off() -> None:
    cfg = validate(copy.deepcopy(MINIMAL))
    assert cfg["register"] is None
    assert cfg["paired_change"] is None
    assert cfg["phases"] is None


def test_the_root_document_defaults_to_the_readme() -> None:
    assert validate(copy.deepcopy(MINIMAL))["root_document"] == "README.md"


def test_without_a_scope_nothing_is_excluded_or_included_back() -> None:
    assert validate(copy.deepcopy(MINIMAL))["scope"] == {"include": [], "exclude": {}}


def test_each_scope_list_is_optional() -> None:
    only_exclude = validate({"version": "1", "scope": {"exclude": {"raw/": "upstream"}}})
    assert only_exclude["scope"] == {"include": [], "exclude": {"raw/": "upstream"}}
    only_include = validate({"version": "1", "scope": {"include": ["raw/a.md"]}})
    assert only_include["scope"] == {"include": ["raw/a.md"], "exclude": {}}


def test_exclusions_keep_their_reasons() -> None:
    assert validate(copy.deepcopy(FULL))["scope"]["exclude"]["raw/"] == "upstream essays, not authored here"


def test_a_full_configuration_is_kept_with_integer_keys_converted() -> None:
    cfg = validate(copy.deepcopy(FULL))
    assert cfg["root_document"] == "docs/README.md"
    assert cfg["register"] is not None
    assert cfg["register"]["columns"] == 5
    assert cfg["register"]["status_column"] == 4
    assert cfg["paired_change"] == PAIRED_CHANGE
    assert cfg["phases"] is not None
    assert cfg["phases"]["ledger"] == "state/phases.yaml"


def test_without_links_nothing_is_allowed() -> None:
    assert validate(copy.deepcopy(MINIMAL))["links"] == {"allow": []}


def test_allowances_keep_their_order_and_reasons() -> None:
    assert validate(copy.deepcopy(FULL))["links"]["allow"] == LINKS["allow"]


def test_without_rules_every_rule_keeps_its_default_severity() -> None:
    assert validate(copy.deepcopy(MINIMAL))["rules"] == {}


def test_a_rule_can_be_set_to_error_warning_or_off() -> None:
    assert validate(copy.deepcopy(FULL))["rules"] == {
        "links/resolve": "warning",
        "hashes/unsealed": "error",
        "frontmatter/open": "off",
    }


def test_without_tools_no_external_command_runs() -> None:
    assert validate(copy.deepcopy(MINIMAL))["tools"] == []


def test_tools_keep_their_order_names_and_commands() -> None:
    assert validate(copy.deepcopy(FULL))["tools"] == [
        {"name": "markdownlint", "command": ["markdownlint-cli2"]},
        {"name": "spelling", "command": ["codespell", "--quiet-level", "2"]},
    ]


def test_validation_does_not_change_its_input() -> None:
    raw = copy.deepcopy(FULL)
    validate(raw)
    assert raw == FULL


# --- refusals: (mutation of FULL, fragments the message must contain) ---------------

REFUSALS = [
    pytest.param(unchanged, [], id="(control: FULL is valid)", marks=pytest.mark.xfail(strict=True)),
    pytest.param(drop("version"), ["version", "missing"], id="no format version"),
    pytest.param(setter("version", None, "2"), ["version", "2", "1"], id="a format version this docsys does not read"),
    pytest.param(setter("version", None, "1.0"), ["version"], id="a format version that is not the integer"),
    pytest.param(setter("extra", None, {}), ["extra", "unknown"], id="an unknown section"),
    pytest.param(
        setter("schema", None, {"source": "s.yaml"}),
        ["schema", "unknown"],
        id="the schema section, which ships inside the package",
    ),
    pytest.param(
        setter("checks", None, []),
        ["checks", "unknown"],
        id="the checks section, which the configuration's sections decide",
    ),
    pytest.param(setter("scope", None, ["raw/"]), ["scope", "mapping"], id="a scope that is not a section"),
    pytest.param(
        setter("scope", "include", "docs/"), ["scope.include", "list of strings"], id="an include that is not a list"
    ),
    pytest.param(
        setter("scope", "exclude", ["raw/"]), ["scope.exclude", "mapping", "reason"], id="an exclude without reasons"
    ),
    pytest.param(
        setter("scope", "exclude", {"raw/": None}),
        ["scope.exclude", "raw/", "reason"],
        id="an exclusion with no reason",
    ),
    pytest.param(
        setter("scope", "exclude", {"raw/": ""}),
        ["scope.exclude", "raw/", "reason"],
        id="an exclusion with an empty reason",
    ),
    pytest.param(
        setter("scope", "exclude", {"/abs/": "why"}), ["scope.exclude", "/abs/", "relative"], id="an absolute pattern"
    ),
    pytest.param(
        setter("scope", "include", ["../outside/"]),
        ["scope.include", "..", "relative"],
        id="a pattern leaving the workspace",
    ),
    pytest.param(setter("scope", "include", [""]), ["scope.include", "empty"], id="an empty pattern"),
    pytest.param(setter("scope", "typo", ["x"]), ["scope", "typo", "unknown"], id="an unknown scope key"),
    pytest.param(
        setter("root_document", None, "/README.md"), ["root_document", "relative"], id="an absolute root document"
    ),
    pytest.param(
        setter("root_document", None, "../README.md"),
        ["root_document", "relative"],
        id="a root document outside the workspace",
    ),
    pytest.param(
        setter("root_document", None, ["README.md"]), ["root_document", "path"], id="a root document that is not a path"
    ),
    pytest.param(drop("register", "path"), ["register.path", "missing"], id="a register missing a key"),
    pytest.param(setter("register", "typo", "x"), ["register", "typo", "unknown"], id="an unknown register key"),
    pytest.param(
        setter("register", None, "steering/ADR.md"), ["register", "mapping"], id="a register that is not a section"
    ),
    pytest.param(
        setter("register", "path", ["log.md"]), ["register.path", "string"], id="a register path that is not a string"
    ),
    pytest.param(setter("register", "columns", "five"), ["register.columns", "integer"], id="a non-integer column"),
    pytest.param(
        setter("register", "superseded_pattern", "(unclosed"),
        ["register.superseded_pattern", "regular expression"],
        id="a pattern that does not compile",
    ),
    pytest.param(
        setter("register", "superseded_pattern", "superseded by"),
        ["register.superseded_pattern", "group"],
        id="a pattern with the wrong number of groups",
    ),
    pytest.param(
        setter("register", "status_column", "9"),
        ["register.status_column", "columns"],
        id="a status column outside the row",
    ),
    pytest.param(
        setter("paired_change", "since", "main"),
        ["paired_change.since", "commit"],
        id="a since that is not a commit id",
    ),
    pytest.param(
        setter("paired_change", "mechanism", []),
        ["paired_change.mechanism", "at least one"],
        id="an empty mechanism list",
    ),
    pytest.param(
        setter("paired_change", "understanding", "docs/"),
        ["paired_change.understanding", "list of strings"],
        id="an understanding list of non-strings",
    ),
    pytest.param(
        setter("paired_change", "enforce_on", []),
        ["paired_change.enforce_on", "at least one"],
        id="an empty enforce_on list",
    ),
    pytest.param(
        setter("paired_change", "exempt", "engine/test_"),
        ["paired_change.exempt", "list of strings"],
        id="an exempt list of non-strings",
    ),
    pytest.param(
        drop("paired_change", "enforce_on"), ["paired_change.enforce_on", "missing"], id="a missing paired_change key"
    ),
    pytest.param(drop("phases", "ledger"), ["phases.ledger", "missing"], id="a missing phases.ledger"),
    pytest.param(
        setter("phases", "ledger", ["a.yaml"]), ["phases.ledger", "path"], id="a phases.ledger that is not a path"
    ),
    pytest.param(
        setter("phases", "folder", "phase-{name}"),
        ["phases.folder", "{number"],
        id="a folder format without the number",
    ),
    pytest.param(
        setter("phases", "field", "{number:02d}-{name}-{era}"),
        ["phases.field", "format"],
        id="a field format that does not format",
    ),
    pytest.param(
        setter("phases", "markers", {"done": "done", "current": "now"}),
        ["phases.markers", "planned"],
        id="markers missing a status",
    ),
    pytest.param(
        setter("phases", "markers", {"done": "done", "current": "done", "planned": "later"}),
        ["phases.markers", "distinct"],
        id="two statuses with one marker",
    ),
    pytest.param(setter("phases", "tables", []), ["phases.tables", "at least one"], id="no table"),
    pytest.param(
        setter("phases", "tables", [{"path": "r.md", "row": r"^\| (?P<number>\d+)"}]),
        ["phases.tables[0]", "marker"],
        id="a table row pattern without a marker group",
    ),
    pytest.param(
        setter("phases", "tables", [{"path": "r.md", "row": "(?P<number>"}]),
        ["phases.tables[0]", "regular expression"],
        id="a table row pattern that does not compile",
    ),
    pytest.param(
        setter("phases", "tables", [{"path": "r.md", "row": "x", "header": "y"}]),
        ["phases.tables[0]", "header", "unknown"],
        id="a table entry with an unknown key",
    ),
    pytest.param(
        setter("phases", "tables", [{"path": None, "row": r"(?P<number>\d)(?P<marker>x)"}]),
        ["phases.tables[0].path", "string"],
        id="a table path that is not a string",
    ),
    pytest.param(
        setter("phases", "status", {"path": ["R.md"], "line": r"(?P<number>\d+)"}),
        ["phases.status.path", "string"],
        id="a status path that is not a string",
    ),
    pytest.param(
        setter("register", None, {None: "log.md"}), ["register", "None", "not a name"], id="a key that is not a name"
    ),
    pytest.param(
        setter("phases", "status", {"path": "R.md", "line": r"^\*\*Phase \d+"}),
        ["phases.status", "number"],
        id="a status pattern without a number group",
    ),
    pytest.param(
        setter("phases", "mention", r"\bPhase \d+"),
        ["phases.mention", "number"],
        id="a mention pattern without a number group",
    ),
    pytest.param(setter("rules", None, ["links/resolve"]), ["rules", "mapping"], id="rules that are not a mapping"),
    pytest.param(
        setter("rules", "links/resolve", "loud"),
        ["rules", "links/resolve", "loud", "error", "warning", "off"],
        id="a severity that is not one of the three",
    ),
    pytest.param(
        setter("rules", "links/resolve", ["error"]),
        ["rules", "links/resolve", "error", "warning", "off"],
        id="a severity that is not a word",
    ),
    pytest.param(setter("links", None, ["a.md"]), ["links", "mapping"], id="links that are not a section"),
    pytest.param(setter("links", "extra", []), ["links", "extra", "unknown"], id="an unknown links key"),
    pytest.param(setter("links", "allow", {"a.md": "x"}), ["links.allow", "list"], id="an allow that is not a list"),
    pytest.param(
        setter("links", "allow", ["a.md"]),
        ["links.allow[0]", "document", "target", "reason"],
        id="an allowance that is a word",
    ),
    pytest.param(
        setter("links", "allow", [{"document": "a.md", "target": "x.md"}]),
        ["links.allow[0].reason", "missing"],
        id="an allowance with no reason",
    ),
    pytest.param(
        setter("links", "allow", [{"document": "a.md", "target": "x.md", "reason": " "}]),
        ["links.allow[0].reason", "non-empty"],
        id="an allowance with a blank reason",
    ),
    pytest.param(
        setter("links", "allow", [{"target": "x.md", "reason": "why"}]),
        ["links.allow[0].document", "missing"],
        id="an allowance with no document",
    ),
    pytest.param(
        setter("links", "allow", [{"document": "a.md", "reason": "why"}]),
        ["links.allow[0].target", "missing"],
        id="an allowance with no target",
    ),
    pytest.param(
        setter("links", "allow", [{"document": "/a.md", "target": "x.md", "reason": "why"}]),
        ["links.allow[0].document", "/a.md", "relative"],
        id="an absolute document",
    ),
    pytest.param(
        setter("links", "allow", [{"document": "a.md", "target": "", "reason": "why"}]),
        ["links.allow[0].target", "non-empty"],
        id="an empty target",
    ),
    pytest.param(
        setter(
            "links",
            "allow",
            [
                {"document": "a.md", "target": "x.md", "reason": "why"},
                {"document": "a.md", "target": "x.md", "reason": "again"},
            ],
        ),
        ["links.allow[1]", "a.md", "x.md", "twice"],
        id="the same link allowed twice",
    ),
    pytest.param(setter("tools", None, {"name": "x"}), ["tools", "list"], id="tools that are not a list"),
    pytest.param(setter("tools", None, ["markdownlint"]), ["tools[0]", "name", "command"], id="a tool that is a word"),
    pytest.param(setter("tools", None, [{"name": "x"}]), ["tools[0].command", "missing"], id="a tool with no command"),
    pytest.param(setter("tools", None, [{"command": ["x"]}]), ["tools[0].name", "missing"], id="a tool with no name"),
    pytest.param(
        setter("tools", None, [{"name": "x", "command": ["x"], "cwd": "."}]),
        ["tools[0]", "cwd", "unknown"],
        id="a tool with an unknown key",
    ),
    pytest.param(
        setter("tools", None, [{"name": "Mark Down", "command": ["x"]}]),
        ["tools[0].name", "Mark Down", "hyphen"],
        id="a tool name that is not hyphen-cased",
    ),
    pytest.param(
        setter("tools", None, [{"name": "x", "command": ["a"]}, {"name": "x", "command": ["b"]}]),
        ["tools[1].name", "x", "twice"],
        id="two tools of one name",
    ),
    pytest.param(
        setter("tools", None, [{"name": "x", "command": "markdownlint-cli2 --fix"}]),
        ["tools[0].command", "list"],
        id="a command written as one string",
    ),
    pytest.param(
        setter("tools", None, [{"name": "x", "command": list[str]()}]),
        ["tools[0].command", "empty"],
        id="an empty command",
    ),
    pytest.param(
        setter("tools", None, [{"name": "x", "command": ["a", ""]}]),
        ["tools[0].command", "empty"],
        id="a command holding an empty word",
    ),
    pytest.param(
        setter("rules", "links", "error"), ["rules", "links", "<check>/<rule>"], id="a rule named without its check"
    ),
]


@pytest.mark.parametrize(("mutate", "fragments"), REFUSALS)
def test_refusals_name_the_file_the_key_and_the_fix(mutate: Mutation, fragments: list[str]) -> None:
    with pytest.raises(ConfigError) as caught:
        validate(full_with(mutate))
    message = str(caught.value)
    assert message.startswith(f"{CONFIG_NAME}: ")
    assert "fix:" in message
    for fragment in fragments:
        assert fragment in message


@pytest.mark.parametrize("raw", [None, [], "version: 1"], ids=["empty file", "a list", "a string"])
def test_a_file_that_is_not_a_mapping_is_refused(raw: object) -> None:
    with pytest.raises(ConfigError) as caught:
        validate(raw)
    assert "fix:" in str(caught.value)


# --- the scope ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        pytest.param("docs/", "docs/README.md", True, id="a folder holds its direct files"),
        pytest.param("docs/", "docs/build/know/api.md", True, id="a folder holds its whole subtree"),
        pytest.param("docs/", "docsite/README.md", False, id="a folder is not a prefix of a longer name"),
        pytest.param("docs/", "src/docs/README.md", False, id="a folder is anchored at the workspace root"),
        pytest.param("README.md", "README.md", True, id="a file names itself"),
        pytest.param("README.md", "docs/README.md", False, id="a file is anchored at the workspace root"),
        pytest.param("*.md", "CHANGELOG.md", True, id="a star matches within one segment"),
        pytest.param("*.md", "docs/CHANGELOG.md", False, id="a star does not cross a slash"),
        pytest.param("**/*.md", "CHANGELOG.md", True, id="a double star matches zero segments"),
        pytest.param("**/*.md", "a/b/c/CHANGELOG.md", True, id="a double star matches several segments"),
        pytest.param("**/transcripts/", "phases/p7/transcripts/round2.md", True, id="a folder anywhere"),
        pytest.param("docs/?.md", "docs/a.md", True, id="a question mark is one character"),
        pytest.param("docs/?.md", "docs/ab.md", False, id="a question mark is only one character"),
        pytest.param("notes+[draft].md", "notes+[draft].md", True, id="other characters are literal"),
    ],
)
def test_patterns(pattern: str, path: str, expected: bool) -> None:
    excluded = not in_scope({"include": [], "exclude": {pattern: "a reason"}}, path)
    assert excluded is expected


def test_every_document_is_in_scope_by_default() -> None:
    assert in_scope({"include": [], "exclude": {}}, "any/where/at/all.md")


def test_an_exclusion_wins_over_the_default() -> None:
    scope: Scope = {"include": [], "exclude": {"raw/": "upstream"}}
    assert not in_scope(scope, "raw/essay.md")
    assert in_scope(scope, "docs/a.md")


def test_an_inclusion_wins_over_an_exclusion() -> None:
    scope: Scope = {"include": ["raw/essay.md", "raw/kept/"], "exclude": {"raw/": "upstream"}}
    assert in_scope(scope, "raw/essay.md")
    assert in_scope(scope, "raw/kept/notes.md")
    assert not in_scope(scope, "raw/other.md")


# --- loading from a workspace -------------------------------------------------------


def write_config(root: Path, text: str) -> Path:
    (root / CONFIG_NAME).write_text(text, encoding="utf-8")
    return root


def test_load_reads_the_workspace_config(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        "version: 1\nscope:\n  exclude: {raw/: upstream essays}\n  include: [docs/]\nregister:\n"
        + "".join(f"  {key}: '{value}'\n" for key, value in REGISTER.items()),
    )
    cfg = load_config(tmp_path)
    assert cfg["scope"] == {"include": ["docs/"], "exclude": {"raw/": "upstream essays"}}
    assert cfg["register"] is not None
    assert cfg["register"]["columns"] == 5


def test_load_without_a_config_names_the_fix(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path)
    assert "fix:" in str(caught.value)


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        pytest.param("version: 1\nscope: {include: [docs/]\n", "YAML", id="invalid YAML"),
        pytest.param("version: 1\nversion: 1\nscope: {include: [docs/]}\n", "duplicate key", id="a duplicate key"),
    ],
)
def test_load_refuses_unreadable_yaml(tmp_path: Path, text: str, fragment: str) -> None:
    write_config(tmp_path, text)
    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path)
    assert fragment in str(caught.value)
    assert "fix:" in str(caught.value)


def test_a_folder_pattern_leaves_its_folder_out_wholly() -> None:
    assert covers_folder(Scope(include=[], exclude={".venv/": "environment"}), ".venv")
    assert covers_folder(Scope(include=[], exclude={"**/transcripts/": "raw"}), "a/transcripts")


def test_a_pattern_short_of_the_whole_folder_does_not() -> None:
    assert not covers_folder(Scope(include=[], exclude={"docs/*": "top level only"}), "docs")
    assert not covers_folder(Scope(include=[], exclude={"docs/**/*.md": "markdown only"}), "docs")
    assert not covers_folder(Scope(include=[], exclude={}), "docs")


def test_an_inclusion_that_may_reach_into_the_folder_defeats_it() -> None:
    exclude = {"legacy/": "predates docsys"}
    assert not covers_folder(Scope(include=["legacy/revised.md"], exclude=exclude), "legacy")
    assert not covers_folder(Scope(include=["**/revised.md"], exclude=exclude), "legacy")
    assert covers_folder(Scope(include=["docs/a.md"], exclude=exclude), "legacy")
