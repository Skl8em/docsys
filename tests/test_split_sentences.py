"""`split-sentences.js`, the companion of the `sentence-per-line` rule (MD100).

It reads markdownlint-cli2's output on its standard input and breaks, in place, the
lines the rule flagged as two sentences on one line. It is the tool that brings an
existing corpus into compliance when a project adopts the rule, or when the rule
learns to see more.

Each case is a tiny document, the document the tool must leave, and the proof that
the rule then flags nothing: the tool copies the rule's sentence boundary, and a
rule it no longer agrees with would leave violations behind.

It needs `node` and `markdownlint-cli2` on the PATH; without them the suite fails
rather than skips.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent / "src" / "docsys" / "markdownlint"
RULE = HERE / "sentence-per-line.js"
TOOL = HERE / "split-sentences.js"

# (name, document, document after the tool)
CASES: list[tuple[str, str, str]] = [
    ("two sentences", "One sentence here. Another sentence here.\n", "One sentence here.\nAnother sentence here.\n"),
    ("three sentences", "One. Two. Three.\n", "One.\nTwo.\nThree.\n"),
    (
        "strong lead-in, then inline code",
        "**Verification.** `[V]` only when read. `[C]` means claimed.\n",
        "**Verification.**\n`[V]` only when read.\n`[C]` means claimed.\n",
    ),
    (
        "abbreviation is not a boundary",
        "Some tools, e.g. Nix, are pinned. Others are not.\n",
        "Some tools, e.g. Nix, are pinned.\nOthers are not.\n",
    ),
    ("list item keeps its indentation", "- First point. Second point.\n", "- First point.\n  Second point.\n"),
    (
        "numbered item keeps its indentation",
        "10. First point. Second point.\n",
        "10. First point.\n    Second point.\n",
    ),
    ("a clean document is left alone", "One sentence.\nAnother sentence.\n", "One sentence.\nAnother sentence.\n"),
]


@pytest.fixture(scope="module")
def workdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    for tool in ("node", "markdownlint-cli2"):
        if shutil.which(tool) is None:
            pytest.fail(f"{tool} is not on the PATH — fix: enter the development shell that pins it")
    root = tmp_path_factory.mktemp("split-sentences")
    config = {"customRules": [str(RULE)], "config": {"default": False, "sentence-per-line": True}}
    (root / ".markdownlint-cli2.jsonc").write_text(json.dumps(config), encoding="utf-8")
    return root


def lint(workdir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["markdownlint-cli2", "case.md"], cwd=workdir, capture_output=True, text=True, check=False)


@pytest.mark.parametrize(
    ("body", "expected"), [pytest.param(body, expected, id=name) for name, body, expected in CASES]
)
def test_the_tool_splits_what_the_rule_flags_and_nothing_else(workdir: Path, body: str, expected: str) -> None:
    case = workdir / "case.md"
    case.write_text(body, encoding="utf-8")
    report = lint(workdir)
    subprocess.run(["node", str(TOOL)], cwd=workdir, input=report.stdout + report.stderr, text=True, check=True)
    assert case.read_text(encoding="utf-8") == expected
    assert lint(workdir).returncode == 0, "the rule still flags the document the tool left"
