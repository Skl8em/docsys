"""The frontmatter reader — the one YAML parser every check shares.

Real YAML, via `pyyaml`, with two deliberate departures from `yaml.safe_load`,
both on `StrictLoader` below:

  - **Scalars stay strings; only `null`/`~`/empty resolve (to None).** YAML 1.1
    reads `constitutive: no` as False, an all-digit ULID as an int, `2026-09-15`
    as a date. The schema's vocabulary is strings, so implicit typing could only
    turn a valid value into an invalid one, or a crash. The schema's own source
    is just as string-typed: `constitutive: [yes, no]` would load as
    `[true, false]` under a plain SafeLoader.
  - **Duplicate keys are an error**, at any depth. YAML says keys are unique;
    pyyaml keeps the last one silently, so `view: bogus` followed by
    `view: synchronic` would pass.

`StrictLoader` is reusable beyond frontmatter blocks: the schema and the
configuration load through it too.

The fences: a first line `---`, closed by the next line that strips to `---`.

    from docsys.yaml_frontmatter import FrontmatterError, load, values
    fm = load(path)        # {key: (value, file line)}, or None if no block
    values(fm)             # {key: value}
"""

# This module is the boundary with PyYAML, whose stubs type every node and every
# constructed value as `Any`, and leave some parameters unannotated; `Any` and
# unknown members are allowed here and nowhere else. What leaves the
# module is typed: a `Frontmatter` block, or `object` for the caller to narrow.
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false
import os
from collections.abc import Hashable
from dataclasses import dataclass
from typing import IO, Any, Final

import yaml

NULL_TAG: Final = "tag:yaml.org,2002:null"

# A frontmatter block: each key's value, as the strict loader built it (a string,
# None, or a list or mapping of those, to be narrowed by whoever reads it), and the
# 1-based file line the key is on.
Frontmatter = dict[str, tuple[object, int]]


class FrontmatterError(ValueError):
    """Malformed frontmatter, located at a 1-based file line."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


class StrictLoader(yaml.SafeLoader):
    """SafeLoader with implicit typing narrowed to null-only, and duplicate keys
    (at any depth) raising instead of silently keeping the last one."""

    # The signature is PyYAML's, `Any` included: an override must accept and return
    # what the base class does.
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        seen: set[object] = set()
        for key_node, _ in node.value:
            key: object = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key `{key}`", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


StrictLoader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag == NULL_TAG]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def parse(text: str) -> Frontmatter | None:
    """Return {key: (value, file line)} for a document's frontmatter, or None if
    the document has no frontmatter block. Raises FrontmatterError otherwise."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise FrontmatterError(1, "unterminated frontmatter block")
    offset = 2  # pyyaml marks are 0-based, and the block starts on file line 2

    loader = StrictLoader("\n".join(lines[1:end]))
    try:
        root = loader.get_single_node()
        if root is None:
            return {}
        if not isinstance(root, yaml.MappingNode):
            raise FrontmatterError(root.start_mark.line + offset, "frontmatter is not a key: value mapping")
        fm: Frontmatter = {}
        for key_node, value_node in root.value:
            key: object = loader.construct_object(key_node, deep=True)
            line = key_node.start_mark.line + offset
            if not isinstance(key, str):
                raise FrontmatterError(line, f"key {key!r} is not a string")
            if key in fm:
                raise FrontmatterError(line, f"duplicate key `{key}`")
            value: object = loader.construct_object(value_node, deep=True)
            fm[key] = (value, line)
        return fm
    except yaml.MarkedYAMLError as exc:
        # Anchor on where the parser got stuck. The context mark is no better a
        # line on its own — for a block mapping it is the top of the block — so
        # it goes in the message instead.
        mark = exc.problem_mark or exc.context_mark
        line = mark.line + offset if mark else 1
        message = exc.problem or str(exc)
        if exc.context and exc.context_mark:
            message += f" ({exc.context}, from line {exc.context_mark.line + offset})"
        raise FrontmatterError(line, message) from None
    finally:
        loader.dispose()


@dataclass(frozen=True)
class Located:
    """A value read from YAML with the line it is on: a string, None, a list of
    `Located` or a mapping of key to `Located`. A mapping's value is on the line of
    its key, and a list's item on the line of the item."""

    value: "str | list[Located] | dict[str, Located] | None"
    line: int  # 1-based


class YamlError(ValueError):
    """YAML that cannot be read, located at a 1-based line."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


def load_located(text: str) -> Located | None:
    """A whole YAML document with the line of every value, scalars read as
    `StrictLoader` reads them; None when the document is empty."""
    raise NotImplementedError


def load_yaml(stream: str | IO[str]) -> object:
    """A whole YAML document, read with `StrictLoader`: what it holds is unknown
    until the caller narrows it."""
    return yaml.load(stream, Loader=StrictLoader)


def load(path: str | os.PathLike[str]) -> Frontmatter | None:
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read())


def values(fm: Frontmatter | None) -> dict[str, object]:
    """Drop the line numbers: {key: value}. No block reads as no fields."""
    return {key: value for key, (value, _) in (fm or {}).items()}
