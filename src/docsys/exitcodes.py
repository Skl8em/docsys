"""Exit codes, part of the cross-package API: every docsys package returns the same."""
OK = 0        # every check passed
FINDINGS = 1  # at least one check reported a finding
ERROR = 2     # the run could not happen: usage, configuration, workspace
