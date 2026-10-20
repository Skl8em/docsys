"""The opt-in tools: external commands a project names in `tools:` of `docsys.yaml`.

Some checks need a program `docsys` does not carry — a Markdown linter that needs
Node, a spell checker. A project that wants one names it, and `docsys check` runs it
after its own checks, from the workspace, keeping its output to show under its name.
A tool that exits non-zero fails (`tools/failed`) and one that is not installed
fails with the way to install it (`tools/missing`); both are findings, so a project
can turn either down with `rules:`. A tool is the project's to pin: `docsys` runs
the program the PATH finds.
"""

import subprocess
from pathlib import Path
from typing import Final

from .config import Config, Tool
from .findings import Finding, Rule
from .workspace import CONFIG_NAME

FAILED: Final = Rule("tools/failed", "error")
MISSING: Final = Rule("tools/missing", "error")
RULES: Final = (FAILED, MISSING)

Output = tuple[str, str]  # (the tool's name, what it printed on stdout and stderr)


def run_tools(workspace: Path, config: Config) -> tuple[list[Finding], list[Output]]:
    """Run each tool in order, all of them whatever one does: the findings of the
    ones that failed or are missing, and the output of the ones that ran."""
    findings: list[Finding] = []
    outputs: list[Output] = []
    for tool in config["tools"]:
        finding, output = _run(workspace, tool)
        if finding is not None:
            findings.append(finding)
        if output is not None:
            outputs.append((tool["name"], output))
    return findings, outputs


def _run(workspace: Path, tool: Tool) -> tuple[Finding | None, str | None]:
    program = tool["command"][0]
    try:
        result = subprocess.run(
            tool["command"], cwd=workspace, capture_output=True, text=True, stdin=subprocess.DEVNULL, check=False
        )
    except OSError:
        return (
            Finding(
                MISSING.id,
                CONFIG_NAME,
                1,
                f"the tool `{tool['name']}` runs `{program}`, which cannot be run here",
                f"install `{program}` so that it is on the PATH, or remove `{tool['name']}` from `tools:` in "
                f"{CONFIG_NAME}",
            ),
            None,
        )
    output = result.stdout + result.stderr
    if result.returncode == 0:
        return None, output
    return (
        Finding(
            FAILED.id,
            CONFIG_NAME,
            1,
            f"the tool `{tool['name']}` exited with status {result.returncode}",
            f"read what `{tool['name']}` printed under its name, and fix what it reports",
        ),
        output,
    )
