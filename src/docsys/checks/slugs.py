"""The slug check (ADR-028): a document's filename is named after its slug.

A document that declares a `slug` is named after it: its filename stem is the slug,
or the slug and the document's own `id` after a hyphen. The convention is opt-in —
a document without a slug is not checked — and a document whose frontmatter cannot
be read is left to the frontmatter check.
"""

import re
from pathlib import Path, PurePosixPath
from typing import Final

from ..config import Config
from ..documents import documents
from ..findings import Finding, Rule
from ..yaml_frontmatter import FrontmatterError, load

TYPE: Final = Rule("slugs/type", "error")
FORM: Final = Rule("slugs/form", "error")
FILENAME: Final = Rule("slugs/filename", "error")
RULES: Final = (TYPE, FORM, FILENAME)

SLUG_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def check(workspace: Path, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    for path in documents(workspace, config["scope"]):
        try:
            frontmatter = load(workspace / path)
        except FrontmatterError:
            continue
        if frontmatter is None or "slug" not in frontmatter:
            continue
        slug, line = frontmatter["slug"]
        if not slug:
            continue
        if not isinstance(slug, str):
            findings.append(
                Finding(
                    TYPE.id,
                    path,
                    line,
                    f"slug {slug!r} is not a string",
                    "write it as a plain hyphen-cased word, e.g. `slug: my-record`",
                )
            )
            continue
        if not SLUG_RE.match(slug):
            findings.append(
                Finding(
                    FORM.id,
                    path,
                    line,
                    f"slug {slug!r} is not hyphen-cased (a-z, 0-9, -)",
                    "rewrite it in lowercase words joined by hyphens",
                )
            )
        allowed = {slug}
        identifier = frontmatter.get("id", (None, 0))[0]
        if isinstance(identifier, str) and identifier:
            allowed.add(f"{slug}-{identifier}")
        stem = PurePosixPath(path).stem
        if stem not in allowed:
            want = f"{slug} (or {slug}-<id>)" if len(allowed) > 1 else slug
            findings.append(
                Finding(
                    FILENAME.id,
                    path,
                    line,
                    f"filename stem {stem!r} is not the slug {want}",
                    "rename the file, with its links, or change `slug`",
                )
            )
    return findings
