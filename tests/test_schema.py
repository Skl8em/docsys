"""The frontmatter vocabulary the package ships: read through the strict loader, and
refused when it is incoherent, since every document is judged by it."""

import copy
from importlib import resources
from pathlib import Path

import pytest

from docsys.schema import SchemaError, load_schema, validate
from docsys.yaml_frontmatter import load_yaml


def as_raw(text: str) -> dict[str, object]:
    loaded = load_yaml(text)
    assert isinstance(loaded, dict)
    return {str(key): value for key, value in loaded.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def raw_schema() -> dict[str, object]:
    return as_raw(resources.files("docsys").joinpath("schema/frontmatter-rules.yaml").read_text(encoding="utf-8"))


def test_the_packaged_schema_loads_with_its_enums_as_strings() -> None:
    schema = load_schema()
    assert schema["error_enums"]["constitutive"] == ["yes", "no"]
    assert len(schema["required"]) == 9
    assert "slug" in schema["optional_fields"]
    assert schema["root_only_fields"] == ["axis", "dominant-community"]


def mutated(key: str, value: object) -> dict[str, object]:
    raw = copy.deepcopy(raw_schema())
    if value is None:
        del raw[key]
    else:
        raw[key] = value
    return raw


def without_rationale() -> dict[str, object]:
    raw = copy.deepcopy(raw_schema())
    optional = raw["optional_fields"]
    assert isinstance(optional, dict)
    optional["slug"] = " "  # pyright: ignore[reportUnknownMemberType]
    return raw


def partition_missing_a_force() -> dict[str, object]:
    raw = copy.deepcopy(raw_schema())
    fit = raw["direction_of_fit"]
    assert isinstance(fit, dict)
    fit["know"] = ["orient"]  # pyright: ignore[reportUnknownMemberType]
    return raw


@pytest.mark.parametrize(
    ("raw", "fragments"),
    [
        pytest.param(["not", "a", "mapping"], ["mapping"], id="not a mapping"),
        pytest.param(mutated("required", None), ["required", "missing"], id="a missing section"),
        pytest.param(mutated("extra", ["x"]) | {"required": ["title"]}, ["extra", "unknown"], id="an unknown section"),
        pytest.param(mutated("hash_pattern", "[unclosed"), ["hash_pattern", "regular expression"], id="a bad pattern"),
        pytest.param(mutated("root_only_fields", "axis"), ["root_only_fields", "list"], id="a list that is a string"),
        pytest.param(without_rationale(), ["slug", "rationale"], id="an optional field without its reason"),
        pytest.param(
            partition_missing_a_force(), ["direction_of_fit", "partition", "missing"], id="a partition with a gap"
        ),
    ],
)
def test_an_incoherent_schema_is_refused_with_its_fix(raw: object, fragments: list[str]) -> None:
    with pytest.raises(SchemaError) as caught:
        validate(raw)
    message = str(caught.value)
    for fragment in fragments:
        assert fragment in message
    assert "fix:" in message


# --- the copy that the documentation system keeps beside its scripts ------------------

BEHAVIOUR = (
    "required",
    "error_enums",
    "audience_base_roles",
    "root_only_fields",
    "direction_of_fit",
    "hash_pattern",
    "warn_enums",
)


def differences(shipped: dict[str, object], other: dict[str, object]) -> list[str]:
    """What the two vocabularies disagree on that changes a verdict: the sections, and
    the names of the optional fields (their rationales are prose)."""
    out = [key for key in BEHAVIOUR if shipped[key] != other[key]]
    shipped_optional, other_optional = shipped["optional_fields"], other["optional_fields"]
    assert isinstance(shipped_optional, dict)
    assert isinstance(other_optional, dict)
    if set(shipped_optional) != set(other_optional):  # pyright: ignore[reportUnknownArgumentType]
        out.append("optional_fields")
    return out


def test_vocabularies_that_differ_in_a_verdict_are_told_apart() -> None:
    changed = copy.deepcopy(raw_schema())
    changed["required"] = ["title"]
    assert differences(raw_schema(), changed) == ["required"]
    assert differences(raw_schema(), copy.deepcopy(raw_schema())) == []


def test_the_vocabulary_matches_the_documentation_systems_own_when_mounted_there() -> None:
    """The documentation system keeps its own copy until its gate runs docsys, and the
    two must not drift. Skipped outside that repository, where there is no other copy."""
    other = Path(__file__).resolve().parents[2] / "schema" / "frontmatter-rules.yaml"
    if not other.is_file():
        pytest.skip("not mounted in the documentation system")
    assert differences(raw_schema(), as_raw(other.read_text(encoding="utf-8"))) == []
