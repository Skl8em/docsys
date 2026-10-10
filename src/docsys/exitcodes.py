"""Exit codes, part of the cross-package API: every docsys package returns the same."""

from typing import Final

OK: Final = 0  # every check passed
FINDINGS: Final = 1  # at least one check reported a finding
ERROR: Final = 2  # the run could not happen: usage, configuration, workspace
