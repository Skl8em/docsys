#!/usr/bin/env python3
"""Fixture test for the custom `sentence-per-line` rule (MD100, ADR-021).

The rule is a heuristic, so it needs cases pinned down: each fixture below is a
tiny document plus the exact line numbers the rule must flag. Fixtures live here
as strings, not as `.md` files in the corpus — a fixture full of deliberate
violations would otherwise have to be exempted from the gate that runs this.

Runs the PINNED markdownlint-cli2 (its rule API is part of the contract), the
same way scripts/check.py does. Stdlib only.

    python3 tools/markdownlint/test_sentence_per_line.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
RULE = os.path.join(ROOT, "tools", "markdownlint", "sentence-per-line.js")

# (name, markdown body, line numbers the rule must flag)
# Line 1 of each body is the first line of the string below the opening quotes.
CASES = [
    # --- (a) two sentences on one line ---------------------------------------
    ("plain sentence boundary",
     "One sentence here. Another sentence here.\n",
     [1]),
    ("strong emphasis wrapping the first sentence",
     "**You should stop here.** The next sentence follows on the same line.\n",
     [1]),
    ("emphasis wrapping the first sentence",
     "*This is an important distinction.* And so is this one.\n",
     [1]),
    ("underscore emphasis wrapping the first sentence",
     "_Underscore emphasis ends here._ Another sentence.\n",
     [1]),
    ("second sentence opens with emphasis",
     "The plain sentence ends here. **And a bold one starts.**\n",
     [1]),
    ("second sentence opens with a link",
     "The plain sentence ends here. [ADR-021](x.md) says otherwise.\n",
     [1]),
    ("emphasis on both sides of the boundary",
     "*First sentence.* **Second sentence.**\n",
     [1]),

    # --- (b) one sentence broken across lines ---------------------------------
    ("sentence broken mid-emphasis",
     "The point is *not*\nthat it matters.\n",
     [1]),
    ("plain sentence broken across lines",
     "The point is not\nthat it matters.\n",
     [1]),

    # --- clean: emphasised sentences that DO get their own line ---------------
    ("strong-emphasised sentence on its own line",
     "**You should stop here.**\nThe next sentence follows.\n",
     []),
    ("emphasised sentence on its own line",
     "*This is an important distinction.*\nAnd so is this one.\n",
     []),
    ("emphasis mid-sentence",
     "The distinction is *important* and worth keeping.\n",
     []),
    ("emphasis around a trailing colon",
     "**Why:**\nbecause the diff should show the sentence that changed.\n",
     []),

    # --- clean: the abbreviation / initial / decimal allow-list ---------------
    ("abbreviation inside emphasis",
     "See *ibid.* Then we continue.\n",
     []),
    ("abbreviation at a would-be boundary",
     "Some tools, e.g. Nix, are pinned.\n",
     []),
    ("initial inside emphasis",
     "Attributed to **J.** Smith in the margin.\n",
     []),
    ("decimal number",
     "We pin nixpkgs 25.05 There is no sentence here.\n",
     []),
    ("trailing colon introduces a list",
     "The gate runs these:\n\n- linkcheck\n",
     []),
]

VIOLATION = re.compile(r"^[^:]+:(\d+):\d+ sentence-per-line/MD100")


def markdownlint_cmd():
    if os.environ.get("DOCSYS_DEVSHELL") == "1":
        return ["markdownlint-cli2"]
    if shutil.which("nix"):
        return ["nix", "develop", ROOT, "--command", "markdownlint-cli2"]
    if shutil.which("markdownlint-cli2"):
        print("WARNING: using markdownlint-cli2 from PATH — not the pinned devShell version.")
        return ["markdownlint-cli2"]
    return None


def run(cmd, workdir, body):
    """Lint `body` as a standalone document; return the flagged line numbers."""
    with open(os.path.join(workdir, "case.md"), "w") as f:
        f.write(body)
    proc = subprocess.run(cmd + ["case.md"], cwd=workdir, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    return sorted(int(m.group(1)) for m in (VIOLATION.match(ln) for ln in out.splitlines()) if m)


def main():
    cmd = markdownlint_cmd()
    if cmd is None:
        print("FAIL — markdownlint-cli2 unavailable (no PATH entry and no nix). "
              "Enter the devShell: nix develop")
        return 1

    with tempfile.TemporaryDirectory() as workdir:
        # Only MD100 is under test here; the rest of the ruleset is tested by the
        # corpus itself (scripts/check.py lints every file against it).
        with open(os.path.join(workdir, ".markdownlint-cli2.jsonc"), "w") as f:
            json.dump({"customRules": [RULE],
                       "config": {"default": False, "sentence-per-line": True}}, f)

        failures = []
        for name, body, expected in CASES:
            got = run(cmd, workdir, body)
            if got != sorted(expected):
                failures.append((name, body, expected, got))
                print(f"FAIL  {name}: expected lines {sorted(expected)}, flagged {got}")
            else:
                print(f"ok    {name}")

    print("\n" + "=" * 40)
    if failures:
        print(f"sentence-per-line: {len(failures)}/{len(CASES)} case(s) failed")
        return 1
    print(f"sentence-per-line: all {len(CASES)} cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
