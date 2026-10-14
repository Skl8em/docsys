"""The frontmatter vocabulary, read from the YAML the package ships."""

from typing import TypedDict


class SchemaError(Exception):
    """The schema is incoherent; the message carries its `fix:`."""


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


def validate(raw: object) -> Schema:
    raise NotImplementedError


def load_schema() -> Schema:
    raise NotImplementedError
