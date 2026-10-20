"""The custom `sentence-per-line` rule (MD100), which the package ships for a
project to name in `tools:` and in its markdownlint configuration.

The rule is a heuristic, so it needs cases pinned down: each fixture below is a
tiny document plus the exact line numbers the rule must flag. Fixtures live here
as strings, not as `.md` files — a fixture full of deliberate violations would
otherwise have to be exempted from the checks that run on the repository.

The rule runs under markdownlint-cli2, whose rule API is part of the contract, so
the suite needs `markdownlint-cli2` on the PATH, at the version the project pins.
Without it the suite fails rather than skips: a skipped test reads as a rule that
passes.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RULE = Path(__file__).resolve().parent.parent / "src" / "docsys" / "markdownlint" / "sentence-per-line.js"

# (name, markdown body, line numbers the rule must flag)
# Line 1 of each body is the first line of the string below the opening quotes.
CASES: list[tuple[str, str, list[int]]] = [
    # --- (a) two sentences on one line ---------------------------------------
    ("plain sentence boundary", "One sentence here. Another sentence here.\n", [1]),
    (
        "strong emphasis wrapping the first sentence",
        "**You should stop here.** The next sentence follows on the same line.\n",
        [1],
    ),
    ("emphasis wrapping the first sentence", "*This is an important distinction.* And so is this one.\n", [1]),
    ("underscore emphasis wrapping the first sentence", "_Underscore emphasis ends here._ Another sentence.\n", [1]),
    ("second sentence opens with emphasis", "The plain sentence ends here. **And a bold one starts.**\n", [1]),
    ("second sentence opens with a link", "The plain sentence ends here. [ADR-021](x.md) says otherwise.\n", [1]),
    ("emphasis on both sides of the boundary", "*First sentence.* **Second sentence.**\n", [1]),
    # --- (b) one sentence broken across lines ---------------------------------
    ("sentence broken mid-emphasis", "The point is *not*\nthat it matters.\n", [1]),
    ("plain sentence broken across lines", "The point is not\nthat it matters.\n", [1]),
    # --- clean: emphasised sentences that DO get their own line ---------------
    ("strong-emphasised sentence on its own line", "**You should stop here.**\nThe next sentence follows.\n", []),
    ("emphasised sentence on its own line", "*This is an important distinction.*\nAnd so is this one.\n", []),
    ("emphasis mid-sentence", "The distinction is *important* and worth keeping.\n", []),
    ("emphasis around a trailing colon", "**Why:**\nbecause the diff should show the sentence that changed.\n", []),
    # --- clean: the abbreviation / initial / decimal allow-list ---------------
    ("abbreviation inside emphasis", "See *ibid.* Then we continue.\n", []),
    ("abbreviation at a would-be boundary", "Some tools, e.g. Nix, are pinned.\n", []),
    ("initial inside emphasis", "Attributed to **J.** Smith in the margin.\n", []),
    ("decimal number", "We pin nixpkgs 25.05 There is no sentence here.\n", []),
    ("trailing colon introduces a list", "The gate runs these:\n\n- linkcheck\n", []),
]

VIOLATION = re.compile(r"^[^:]+:(\d+):\d+ sentence-per-line/MD100")


@pytest.fixture(scope="module")
def workdir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("markdownlint-cli2") is None:
        pytest.fail(
            "markdownlint-cli2 is not on the PATH — fix: enter the development shell that pins it, "
            "or install the version your project pins; the rule cannot be tested without it"
        )
    root = tmp_path_factory.mktemp("sentence-per-line")
    # Only MD100 is under test: the rest of a project's ruleset is tested by its corpus.
    config = {"customRules": [str(RULE)], "config": {"default": False, "sentence-per-line": True}}
    (root / ".markdownlint-cli2.jsonc").write_text(json.dumps(config), encoding="utf-8")
    return root


@pytest.mark.parametrize(("body", "expected"), [pytest.param(body, lines, id=name) for name, body, lines in CASES])
def test_the_rule_flags_exactly_these_lines(workdir: Path, body: str, expected: list[int]) -> None:
    (workdir / "case.md").write_text(body, encoding="utf-8")
    result = subprocess.run(["markdownlint-cli2", "case.md"], cwd=workdir, capture_output=True, text=True, check=False)
    lines = (result.stdout + result.stderr).splitlines()
    flagged = sorted(int(match.group(1)) for match in map(VIOLATION.match, lines) if match)
    assert flagged == sorted(expected)
