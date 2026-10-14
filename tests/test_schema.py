"""The frontmatter vocabulary the package ships: read through the strict loader, and
refused when it is incoherent, since every document is judged by it."""

import copy
from importlib import resources

import pytest

from docsys.schema import SchemaError, load_schema, validate
from docsys.yaml_frontmatter import load_yaml


def raw_schema() -> dict[str, object]:
    text = resources.files("docsys").joinpath("schema/frontmatter-rules.yaml").read_text(encoding="utf-8")
    loaded = load_yaml(text)
    assert isinstance(loaded, dict)
    return {str(key): value for key, value in loaded.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


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
