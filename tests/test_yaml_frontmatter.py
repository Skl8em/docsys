"""The frontmatter reader: real YAML, with two departures from `yaml.safe_load` —
scalars stay strings (only null resolves), and a duplicate key is an error at any
depth — and every error located at a file line."""
import pytest

from docsys.yaml_frontmatter import FrontmatterError, StrictLoader, parse, values


def doc(frontmatter: str) -> str:
    return f"---\n{frontmatter}---\n\nBody.\n"


@pytest.mark.parametrize("frontmatter, expected", [
    pytest.param("axis: provenance       # the producer's shelf\n", {"axis": "provenance"},
                 id="a comment is stripped from a value"),
    pytest.param("id: 12345670123456701234567012\n", {"id": "12345670123456701234567012"},
                 id="a ULID made only of digits stays a string"),
    pytest.param("valid-for: 2026-09-15\n", {"valid-for": "2026-09-15"},
                 id="a date stays a string"),
    pytest.param("constitutive: yes\nother: no\n", {"constitutive": "yes", "other": "no"},
                 id="yes and no stay strings, where YAML 1.1 reads booleans"),
    pytest.param("supersedes: null\nsuperseded-by: ~\n", {"supersedes": None, "superseded-by": None},
                 id="null and ~ are None"),
    pytest.param("", {}, id="an empty block"),
    pytest.param("view: synchronic\n  diachronic\n", {"view": "synchronic diachronic"},
                 id="a plain scalar folded onto the next line is one value"),
    pytest.param("audience:\n  - contributor\n  - decider\n", {"audience": ["contributor", "decider"]},
                 id="a block sequence"),
    pytest.param('provenance: { type: function, id: "steering, type: bogus" }\n',
                 {"provenance": {"type": "function", "id": "steering, type: bogus"}},
                 id="a quoted comma inside an inline map"),
])
def test_values(frontmatter: str, expected: dict[str, object]) -> None:
    assert values(parse(doc(frontmatter))) == expected


def test_each_key_carries_its_file_line() -> None:
    fm = parse(doc("title: A\nview: synchronic\n"))
    assert fm == {"title": ("A", 2), "view": ("synchronic", 3)}


def test_a_document_without_a_block_has_no_frontmatter() -> None:
    assert parse("# Title\n\nBody.\n") is None
    assert values(None) == {}


def test_crlf_line_endings_read_like_lf() -> None:
    assert values(parse("---\r\ntitle: A\r\n---\r\nBody.\r\n")) == {"title": "A"}


@pytest.mark.parametrize("frontmatter, line, fragment", [
    pytest.param("view: bogus\nview: synchronic\n", 3, "duplicate key `view`",
                 id="a duplicate key, even when the last one is valid"),
    pytest.param("provenance: { type: bogus, id: steering, type: function }\n", 2, "duplicate key `type`",
                 id="a duplicate key inside an inline map"),
    pytest.param("title: A\n  review: pending\n", 3, "",
                 id="a field hidden by indentation"),
    pytest.param('title: "A\nview: synchronic\n', 3, "from line 2",
                 id="an unterminated quoted string, located where the parser stopped"),
    pytest.param("- a\n- b\n", 2, "not a key: value mapping",
                 id="a block that is not a mapping"),
])
def test_errors_are_located(frontmatter: str, line: int, fragment: str) -> None:
    with pytest.raises(FrontmatterError) as caught:
        parse(doc(frontmatter))
    assert caught.value.line == line
    assert fragment in caught.value.message


def test_an_unterminated_block_is_an_error_on_line_1() -> None:
    with pytest.raises(FrontmatterError) as caught:
        parse("---\ntitle: A\n")
    assert caught.value.line == 1


def test_the_strict_loader_is_reusable_for_other_files() -> None:
    import yaml
    assert yaml.load("constitutive: [yes, no]\n", Loader=StrictLoader) == {"constitutive": ["yes", "no"]}
    with pytest.raises(yaml.YAMLError):
        yaml.load("a: 1\na: 2\n", Loader=StrictLoader)
