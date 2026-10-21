"""Which `status` words close a record — a fact the fixity and phase-state checks
rely on, kept in code beside the vocabulary that declares the words.

The vocabulary leaves its status words among its open questions, so it does not say
which of them are frozen; `docsys.checks.hashes` does. Every word the vocabulary
declares is classified there exactly once, frozen or open, so a word added to the
vocabulary is met here, rather than as a record that is silently never sealed."""

from docsys.checks.hashes import FROZEN_STATUSES, OPEN_STATUSES
from docsys.schema import load_schema


def test_every_declared_status_is_classified_once_as_frozen_or_open() -> None:
    declared = set(load_schema()["warn_enums"]["status"])
    frozen, open_ = set(FROZEN_STATUSES), set(OPEN_STATUSES)
    assert not frozen & open_, (
        f"status {sorted(frozen & open_)} is both frozen and open — fix: keep it in the one list of "
        "docsys/checks/hashes.py that says whether such a record is closed"
    )
    assert not declared - frozen - open_, (
        f"the vocabulary declares status {sorted(declared - frozen - open_)}, classified neither frozen nor open — "
        "fix: add it to FROZEN_STATUSES in docsys/checks/hashes.py if a record with it is closed, else to OPEN_STATUSES"
    )
    assert not (frozen | open_) - declared, (
        f"docsys/checks/hashes.py classifies status {sorted((frozen | open_) - declared)}, which the vocabulary "
        "no longer declares — fix: remove it there, or restore it in warn_enums.status"
    )
