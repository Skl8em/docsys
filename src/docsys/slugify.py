"""Slugifying: name each document after its slug.

The correction the slug check asks for (`checks.slugs`), made through `rename` so
every link follows. A document is renamed to `<slug>.md` in its own folder when it
declares a slug that can name a file and its name is not one the check accepts: the
slug, or the slug and the document's `id` after a hyphen. A document without a slug,
outside the scope, or whose frontmatter cannot be read (the frontmatter check says
so) is left alone; a slug that cannot name a file is reported, not repaired.
The plan is made whole before the first rename: a name already taken, or wanted by
two documents, refuses it all.
"""

import os
import posixpath
from dataclasses import dataclass
from pathlib import Path

from .checks.slugs import SLUG_RE
from .config import Scope
from .documents import documents
from .rename import rename
from .yaml_frontmatter import FrontmatterError, load


class SlugifyError(Exception):
    """The renames cannot be made; the message carries its `fix:`."""


@dataclass(frozen=True)
class Slugified:
    renamed: list[tuple[str, str]]  # (old, new), in the order made
    skipped: list[tuple[str, str]]  # (document, why its slug cannot name a file)
    stale_seals: list[str]  # sealed documents whose links were rewritten


def slugify(workspace: Path, scope: Scope, *, dry_run: bool = False) -> Slugified:
    plan: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    for path in documents(workspace, scope):
        try:
            frontmatter = load(workspace / path)
        except FrontmatterError:
            continue
        if frontmatter is None or not frontmatter.get("slug", (None, 0))[0]:
            continue
        slug = frontmatter["slug"][0]
        if not isinstance(slug, str):
            skipped.append((path, f"slug {slug!r} is not a string — fix: write it as a hyphen-cased word"))
            continue
        if not SLUG_RE.match(slug):
            skipped.append((path, f"slug {slug!r} is not hyphen-cased (a-z, 0-9, -) — fix: rewrite the slug"))
            continue
        identifier = frontmatter.get("id", (None, 0))[0]
        stem = posixpath.basename(path)[: -len(".md")]
        accepted = {slug, f"{slug}-{identifier}"} if isinstance(identifier, str) and identifier else {slug}
        if stem not in accepted:
            plan.append((path, posixpath.join(posixpath.dirname(path), f"{slug}.md")))

    wanted: dict[str, str] = {}
    problems: list[str] = []
    for old, new in plan:
        if os.path.lexists(workspace / new):
            problems.append(f"`{old}` would become `{new}`, which exists")
        elif new in wanted:
            problems.append(f"`{old}` and `{wanted[new]}` would both become `{new}`")
        wanted[new] = old
    if problems:
        raise SlugifyError(
            "; ".join(problems) + " — fix: change one of the slugs, or move the file in the way, then run it again"
        )

    stale: list[str] = []
    for old, new in plan:
        result = rename(workspace, scope, old, new, dry_run=dry_run)
        stale += [path for path in result.stale_seals if path not in stale]
    return Slugified(plan, skipped, stale)
