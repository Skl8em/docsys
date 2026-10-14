"""The frontmatter vocabulary — the one reader of `schema/frontmatter-rules.yaml`,
shipped inside the package.

The file says what a document's frontmatter may declare and with which values. It
is read through the strict YAML loader (scalars stay strings, so `constitutive:
[yes, no]` is two words and not two booleans) and refused when it is incoherent,
since every document is judged by it: a section missing or unknown, an optional field
declared without its reason (declaring and justifying a field are one act), a
`direction_of_fit` that does not partition the forces exactly (the register cannot
be derived from a table with a gap or an overlap).

    from docsys.schema import load_schema
    schema = load_schema()
    schema["error_enums"]["view"]   # ["synchronic", "diachronic"]
"""

import re
from collections.abc import Sequence
from importlib import resources
from typing import Final, TypedDict, TypeGuard

from .yaml_frontmatter import load_yaml

RESOURCE: Final = "schema/frontmatter-rules.yaml"


class SchemaError(Exception):
    """The schema is incoherent; the message names the file and carries its `fix:`."""

    def __init__(self, message: str) -> None:
        super().__init__(f"{RESOURCE}: {message}")


class ErrorEnums(TypedDict):
    view: list[str]
    reader: list[str]
    force: list[str]
    provenance_type: list[str]
    intention: list[str]
    constitutive: list[str]


class DirectionOfFit(TypedDict):
    know: list[str]
    do: list[str]


class WarnEnums(TypedDict):
    distance: list[str]
    power: list[str]
    status: list[str]


class Schema(TypedDict):
    required: list[str]
    error_enums: ErrorEnums
    audience_base_roles: list[str]
    root_only_fields: list[str]
    direction_of_fit: DirectionOfFit
    optional_fields: dict[str, str]
    hash_pattern: str
    warn_enums: WarnEnums


# Sections of the file that document the vocabulary and that no check reads.
PROSE_SECTIONS: Final = ("derived_fields", "still_open")


def _is_mapping(value: object) -> TypeGuard[dict[object, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _mapping(value: object, name: str, keys: Sequence[str]) -> dict[str, object]:
    """A mapping that carries exactly `keys`."""
    if not _is_mapping(value):
        raise SchemaError(f"`{name}` must be a mapping — fix: write it as `{name}:` and its keys {list(keys)}.")
    section = {str(key): item for key, item in value.items()}
    for key in keys:
        if key not in section:
            raise SchemaError(
                f"`{name}.{key}` is missing — fix: add it." if name else f"`{key}` is missing — fix: add it."
            )
    extra = sorted(set(section) - set(keys))
    if extra:
        raise SchemaError(f"`{name}` has unknown key(s) {extra} — fix: remove them; allowed: {list(keys)}.")
    return section


def _strings(value: object, name: str) -> list[str]:
    if not _is_list(value):
        raise SchemaError(f"`{name}` must be a list of strings — fix: write it as `{name.split('.')[-1]}: [a, b]`.")
    checked: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise SchemaError(f"`{name}` must be a list of strings, and holds {item!r} — fix: write each as a string.")
        checked.append(item)
    return checked


def validate(raw: object) -> Schema:
    """Check a loaded schema and return it narrowed."""
    if not _is_mapping(raw):
        raise SchemaError("must be a mapping of the vocabulary's sections — fix: restore it from the package.")
    top = {str(key): item for key, item in raw.items()}
    sections = (*Schema.__annotations__, *PROSE_SECTIONS)
    for key in Schema.__annotations__:
        if key not in top:
            raise SchemaError(f"`{key}` is missing — fix: add the section.")
    unknown = sorted(set(top) - set(sections))
    if unknown:
        raise SchemaError(
            f"unknown section(s) {unknown} — fix: remove them; the vocabulary is closed: {list(sections)}."
        )

    enums = _mapping(top["error_enums"], "error_enums", tuple(ErrorEnums.__annotations__))
    error_enums = ErrorEnums(
        view=_strings(enums["view"], "error_enums.view"),
        reader=_strings(enums["reader"], "error_enums.reader"),
        force=_strings(enums["force"], "error_enums.force"),
        provenance_type=_strings(enums["provenance_type"], "error_enums.provenance_type"),
        intention=_strings(enums["intention"], "error_enums.intention"),
        constitutive=_strings(enums["constitutive"], "error_enums.constitutive"),
    )
    warned = _mapping(top["warn_enums"], "warn_enums", tuple(WarnEnums.__annotations__))
    fit = _mapping(top["direction_of_fit"], "direction_of_fit", tuple(DirectionOfFit.__annotations__))
    direction = DirectionOfFit(
        know=_strings(fit["know"], "direction_of_fit.know"), do=_strings(fit["do"], "direction_of_fit.do")
    )
    covered = direction["know"] + direction["do"]
    if sorted(covered) != sorted(error_enums["force"]):
        missing = sorted(set(error_enums["force"]) - set(covered))
        unknown_forces = sorted(set(covered) - set(error_enums["force"]))
        raise SchemaError(
            "`direction_of_fit` must partition `force` exactly — "
            f"missing {missing}, unknown {unknown_forces} — fix: list every force under exactly one of know / do."
        )
    optional_raw = top["optional_fields"]
    if not _is_mapping(optional_raw):
        raise SchemaError("`optional_fields` must map each field to its rationale — fix: write `field: reason`.")
    optional: dict[str, str] = {}
    for field, rationale in optional_raw.items():
        if not isinstance(rationale, str) or not rationale.strip():
            raise SchemaError(
                f"optional field `{field}` has no rationale string — fix: give it a one-line reason, or remove it"
            )
        optional[str(field)] = rationale
    pattern = top["hash_pattern"]
    if not isinstance(pattern, str):
        raise SchemaError("`hash_pattern` must be a regular expression string — fix: quote it.")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise SchemaError(
            f"`hash_pattern` is not a valid regular expression ({exc}) — fix: correct the pattern."
        ) from None
    return Schema(
        required=_strings(top["required"], "required"),
        error_enums=error_enums,
        audience_base_roles=_strings(top["audience_base_roles"], "audience_base_roles"),
        root_only_fields=_strings(top["root_only_fields"], "root_only_fields"),
        direction_of_fit=direction,
        optional_fields=optional,
        hash_pattern=pattern,
        warn_enums=WarnEnums(
            distance=_strings(warned["distance"], "warn_enums.distance"),
            power=_strings(warned["power"], "warn_enums.power"),
            status=_strings(warned["status"], "warn_enums.status"),
        ),
    )


def load_schema() -> Schema:
    """The vocabulary the package ships."""
    text = resources.files("docsys").joinpath(RESOURCE).read_text(encoding="utf-8")
    return validate(load_yaml(text))
