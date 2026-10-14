"""The link check's message, which the conformance suite leaves to each package:
it names the target as written, so the reader finds the link on the line."""

import subprocess
from pathlib import Path

from docsys.checks import links
from docsys.config import load_config
from docsys.workspace import CONFIG_NAME


def test_the_message_names_the_target_as_written(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / CONFIG_NAME).write_text("version: 1\n", encoding="utf-8")
    (tmp_path / "a.md").write_text('[x](gone.md#part "Title")\n', encoding="utf-8")
    [finding] = links.check(tmp_path, load_config(tmp_path))
    assert "gone.md#part" in finding.message
