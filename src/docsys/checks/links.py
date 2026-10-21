"""The link check: every relative link in a document resolves.

A link is `[text](target)`. Its target is read from the document's own folder,
after dropping a link title and an anchor, and resolves when a file or folder
exists there — a document or not, in the scope or not. Not resolved: `http://`,
`https://` and `mailto:` targets, a same-document anchor (`#part`), and a fill-in
placeholder (`<path>`, or a target holding `…`), which a template shows where its
reader writes a path.

A dead link can be allowed, with its reason, in `links.allow` of `docsys.yaml`: the
document and the target as written. An allowed link that does not resolve is not
reported. An allowance that allows nothing — its document does not hold the link, or
the link resolves — is reported (`links/allowance`) on `docsys.yaml`, at the line
where the entry starts, so the list cannot outlive its reason.
"""

import os
import posixpath
import re
from pathlib import Path
from typing import Final

from ..config import Config
from ..documents import documents
from ..findings import Finding, Rule
from ..workspace import CONFIG_NAME
from ..yaml_frontmatter import load_located

RESOLVE: Final = Rule("links/resolve", "error")
ALLOWANCE: Final = Rule("links/allowance", "error")
RULES: Final = (RESOLVE, ALLOWANCE)

LINK_RE: Final = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
NOT_RESOLVED: Final = ("http://", "https://", "#", "mailto:")


def _allowance_lines(text: str) -> list[int]:
    """The 1-based line of `docsys.yaml` where each `links.allow` entry starts."""
    root = load_located(text)
    links = root.value.get("links") if root and isinstance(root.value, dict) else None
    allow = links.value.get("allow") if links and isinstance(links.value, dict) else None
    return [entry.line for entry in allow.value] if allow and isinstance(allow.value, list) else []


def check(workspace: Path, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    allowed = {(a["document"], a["target"]): index for index, a in enumerate(config["links"]["allow"])}
    live: set[int] = set()  # the allowances that allow a dead link
    for path in documents(workspace, config["scope"]):
        text = (workspace / path).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), 1):
            for match in LINK_RE.finditer(line):
                target = match.group(1).strip()
                if target.startswith(NOT_RESOLVED):
                    continue
                target = target.split()[0]  # drop a link title
                link_path = target.split("#", 1)[0]  # drop an anchor
                if not link_path or link_path.startswith("<") or "…" in link_path:
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), link_path))
                if os.path.exists(workspace / resolved):
                    continue
                if (path, target) in allowed:
                    live.add(allowed[path, target])
                    continue
                findings.append(
                    Finding(
                        rule=RESOLVE.id,
                        path=path,
                        line=lineno,
                        message=f"`{target}` points to no file or folder",
                        fix="point the link at an existing path, or remove it",
                    )
                )
    stale = [index for index in range(len(config["links"]["allow"])) if index not in live]
    if stale:
        text = (workspace / CONFIG_NAME).read_text(encoding="utf-8")
        lines = _allowance_lines(text)
        for index in stale:
            allowance = config["links"]["allow"][index]
            findings.append(
                Finding(
                    rule=ALLOWANCE.id,
                    path=CONFIG_NAME,
                    line=lines[index],
                    message=(
                        f"`{allowance['target']}` in {allowance['document']} is allowed, "
                        "but that document holds no such link that fails to resolve"
                    ),
                    fix="remove the allowance from `links.allow`",
                )
            )
    return findings
