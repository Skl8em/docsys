"""The link check: every relative link in a document resolves.

A link is `[text](target)`. Its target is read from the document's own folder,
after dropping a link title and an anchor, and resolves when a file or folder
exists there — a document or not, in the scope or not. Not resolved: `http://`,
`https://` and `mailto:` targets, a same-document anchor (`#part`), and a fill-in
placeholder (`<path>`, or a target holding `…`), which a template shows where its
reader writes a path.
"""

import os
import posixpath
import re
from pathlib import Path
from typing import Final

from ..config import Config
from ..documents import documents
from ..findings import Finding, Rule

RESOLVE: Final = Rule("links/resolve", "error")
RULES: Final = (RESOLVE,)

LINK_RE: Final = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
NOT_RESOLVED: Final = ("http://", "https://", "#", "mailto:")


def check(workspace: Path, config: Config) -> list[Finding]:
    findings: list[Finding] = []
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
                if not os.path.exists(workspace / resolved):
                    findings.append(
                        Finding(
                            rule=RESOLVE.id,
                            path=path,
                            line=lineno,
                            message=f"`{target}` points to no file or folder",
                            fix="point the link at an existing path, or remove it",
                        )
                    )
    return findings
