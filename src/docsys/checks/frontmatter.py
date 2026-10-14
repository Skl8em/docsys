"""The frontmatter check: every document's frontmatter is judged by the vocabulary.

Every document in scope opens with a YAML frontmatter block, read as real YAML in
which scalars stay strings and a duplicate key is an error, and judged by the
vocabulary the package ships (`docsys.schema`): the required fields, the
enumerations, the optional fields each declared with a reason, the fields of the root
document alone. Settled rules are errors; what the vocabulary lists as still
undecided is a warning. This is the check that reports a frontmatter that cannot be
read: every other check leaves such a document to it.

The root document is the one `root_document` names in docsys.yaml. Findings come in
the order of their path, then their line.
"""

import re
from pathlib import Path
from typing import Final, TypeGuard

from ..config import Config
from ..documents import documents
from ..findings import Finding, Rule
from ..schema import RESOURCE, Schema, load_schema
from ..yaml_frontmatter import Frontmatter, FrontmatterError, parse

YAML: Final = Rule("frontmatter/yaml", "error")
MISSING_BLOCK: Final = Rule("frontmatter/missing-block", "error")
REQUIRED: Final = Rule("frontmatter/required", "error")
PROVENANCE: Final = Rule("frontmatter/provenance", "error")
ENUM: Final = Rule("frontmatter/enum", "error")
REGISTER: Final = Rule("frontmatter/register", "error")
HASH: Final = Rule("frontmatter/hash", "error")
AUDIENCE: Final = Rule("frontmatter/audience", "error")
AUDIENCE_ROLE: Final = Rule("frontmatter/audience-role", "warning")
ROOT_ONLY: Final = Rule("frontmatter/root-only", "error")
OPEN: Final = Rule("frontmatter/open", "warning")
VOCABULARY: Final = Rule("frontmatter/vocabulary", "error")
RULES: Final = (
    YAML,
    MISSING_BLOCK,
    REQUIRED,
    PROVENANCE,
    ENUM,
    REGISTER,
    HASH,
    AUDIENCE,
    AUDIENCE_ROLE,
    ROOT_ONLY,
    OPEN,
    VOCABULARY,
)


def _is_mapping(value: object) -> TypeGuard[dict[object, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def check(workspace: Path, config: Config) -> list[Finding]:
    schema = load_schema()
    findings: list[Finding] = []
    for path in documents(workspace, config["scope"]):
        text = (workspace / path).read_text(encoding="utf-8")
        try:
            frontmatter = parse(text)
        except FrontmatterError as exc:
            findings.append(
                Finding(
                    YAML.id,
                    path,
                    exc.line,
                    f"invalid YAML frontmatter: {exc.message}",
                    "correct the YAML at this line",
                )
            )
            continue
        if frontmatter is None:
            findings.append(
                Finding(
                    MISSING_BLOCK.id,
                    path,
                    1,
                    "no YAML frontmatter block",
                    "open the file with a `---`-fenced block carrying the required fields",
                )
            )
            continue
        findings += _lint(path, frontmatter, schema, path == config["root_document"])
    return sorted(findings, key=lambda finding: (finding.path, finding.line))


def _lint(path: str, frontmatter: Frontmatter, schema: Schema, is_root: bool) -> list[Finding]:
    findings: list[Finding] = []

    def add(rule: Rule, line: int, message: str, fix: str) -> None:
        findings.append(Finding(rule.id, path, line, message, fix))

    def value(key: str) -> object:
        return frontmatter[key][0] if key in frontmatter else None

    def line(key: str) -> int:
        return frontmatter[key][1] if key in frontmatter else 1

    for field in schema["required"]:
        if field not in frontmatter or frontmatter[field][0] in (None, "", []):
            add(REQUIRED, 1, f"missing required field `{field}`", f"add `{field}:` to the frontmatter")

    enums = schema["error_enums"]
    provenance = value("provenance")
    if provenance is not None:
        if not _is_mapping(provenance) or "type" not in provenance or "id" not in provenance:
            add(
                PROVENANCE,
                line("provenance"),
                "provenance must be `{type, id}`",
                "write `provenance: { type: function, id: <name> }`",
            )
        elif provenance["type"] not in enums["provenance_type"]:
            add(
                PROVENANCE,
                line("provenance"),
                f"provenance.type `{provenance['type']}` not in {enums['provenance_type']}",
                "use one of them",
            )

    simple = {
        "view": enums["view"],
        "reader": enums["reader"],
        "intention": enums["intention"],
        "constitutive": enums["constitutive"],
    }
    for field, allowed in simple.items():
        current = value(field)
        if current is not None and current not in allowed:
            add(ENUM, line(field), f"{field} `{current}` not in {allowed}", "use one of them")

    if "register" in frontmatter:
        add(
            REGISTER,
            line("register"),
            "`register` is derived (`constitutive ? govern : direction-of-fit(force)`), never stored",
            "remove the field",
        )

    seal = value("hash")
    if seal is not None and not re.match(schema["hash_pattern"], str(seal)):
        add(
            HASH,
            line("hash"),
            f"hash `{seal}` does not match {schema['hash_pattern']}",
            "set it to the record's seal, or remove `hash` if the record is not frozen",
        )

    force = value("force")
    if force is not None:
        for component in str(force).split("+"):
            if component.strip() not in enums["force"]:
                add(
                    ENUM,
                    line("force"),
                    f"force component `{component.strip()}` not a known force",
                    f"use one of {enums['force']}",
                )

    audience = value("audience")
    if audience is not None:
        if not _is_list(audience) or not audience:
            add(
                AUDIENCE, line("audience"), "audience must be a non-empty list", "write it as `audience: [contributor]`"
            )
        else:
            for role in audience:
                if role not in schema["audience_base_roles"]:
                    add(
                        AUDIENCE_ROLE,
                        line("audience"),
                        f"audience role `{role}` is a project refinement (base: {schema['audience_base_roles']})",
                        "keep it if the project declares that role, or use a base role",
                    )

    for field in schema["root_only_fields"]:
        if field in frontmatter and not is_root:
            add(ROOT_ONLY, line(field), f"`{field}` may only appear on the root document", "remove it from this file")
        elif is_root and field not in frontmatter:
            add(ROOT_ONLY, 1, f"the root document must carry `{field}`", f"add `{field}:` to its frontmatter")

    warned = schema["warn_enums"]
    open_enums = {"distance": warned["distance"], "power": warned["power"], "status": warned["status"]}
    for field, allowed in open_enums.items():
        current = value(field)
        if current is not None and current not in allowed:
            add(
                OPEN,
                line(field),
                f"{field} `{current}` outside the current practice {allowed} (still open)",
                "use one of the current values, or leave it: the vocabulary has not ruled on it",
            )

    known = set(schema["required"]) | set(schema["optional_fields"]) | set(schema["root_only_fields"])
    for field in frontmatter:
        if field not in known and field != "register":
            add(
                VOCABULARY,
                line(field),
                f"`{field}` is not in the closed frontmatter vocabulary",
                f"remove it, or have it declared with a rationale in the vocabulary the package ships ({RESOURCE})",
            )
    return findings
