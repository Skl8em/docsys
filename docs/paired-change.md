---
title: "The paired-change rule — why the tooling may not change unexplained"
force: explain
intention: formative
view: synchronic
provenance: { type: function, id: codifying }
constitutive: no
distance: initiated
audience: [contributor]
reader: H+M
status: draft
---

`paired-change` (`scripts/paired_change.py`, decided in [ADR-039](../phases/refoundation/phase-12-codifying/paired-change-rule.md) and refined by [ADR-040](../phases/refoundation/phase-12-codifying/paired-change-where-it-fails.md)) fails a change to `scripts/`, `schema/` or `docsys.yaml` that touches no file under `writing/`, `structuring/`, `operationalizing/` or `codifying/` and not `steering/ARCHITECTURE.md`.
Its lists — mechanism, understanding, what needs no account, the branches it is enforced on, and the anchor — are `paired_change:` in `docsys.yaml`, so the engine names none of them.
This fiche is one of the files that satisfies it, which is why a change to the gate lands with an edit here.

Four properties are easy to get wrong when touching it.

**The unit is the commit, not the branch.**
It examines every non-merge commit after `paired_change.since`, and the uncommitted work that will become the next one, each on its own.
A branch-level rule was tried against Phase 11 first and passes it: the phase touched three explaining documents incidentally, and on a phase-long branch any such edit pairs every script edit.
So a later docs commit never pairs an earlier scripts commit, and the account goes in the same commit as the change.

**Two kinds of change are not a change to the mechanism.**
A file under an `exempt` prefix (`scripts/test_`) and a Python edit whose syntax tree, docstrings set aside, is unchanged — comments, docstrings, formatting — have nothing to explain, so they need no account, on any branch.
The second is a comparison of the file before and after, so it is a heuristic on the tree and not on intent: a docstring that replaces the description of unchanged behaviour passes, and only Python is examined.
A version that does not parse, or a file added or deleted, is never comment-only.

**It fails only where work lands.**
On a branch in `enforce_on` (`main`, `develop`) and on a detached HEAD — which is what CI checks out for a pull request — a finding fails the gate.
On any other branch the same finding is a `WARNING` naming the branch and where it is enforced, and the exit status is 0, so a mechanism commit may precede the commit that explains it while the work is in progress.
The cost moved, it did not vanish: the pull request examines every commit since the anchor, so the earlier commit fails there and has to be amended or squashed with its account.
If the integration branch is renamed and `enforce_on` is not, the rule would quietly become a warning; so it fails, on every run, when no listed branch exists locally or on a remote (a CI checkout is detached and holds remote refs only).

**The anchor is the only exemption from history, and it shows in a diff.**
Commits before `since` are not examined.
A violating commit that is already made cannot be repaired by adding docs afterwards; moving `since` past it is the way to accept it, and that is an edit to a tracked file that a reviewer sees.
An anchor that cannot be resolved (a shallow clone; a commit not in this history) is an error, never a pass, and that is why CI fetches full history.

**It reads git, so it depends on where it runs.**
Run by hand or from the opt-in hook it sees the working tree; in CI it sees the commits pushed.
A clone that has not opted into the hook meets the failure only in CI, after the commit exists.

It checks co-occurrence, and a one-word edit to a fiche passes; what it removes is the silent case.
`docsys.yaml` is in the mechanism list since Phase 12 T6: it decides what the gate runs and where the rule bites, so a change to it is a change to the tooling.
That includes moving `since`, which accepts a commit and so needs an account like any other change.
The phase ledger is kept out of `docsys.yaml` for this reason: it lives in `steering/phases.yaml`, `phases.ledger` points at it, and a phase transition is a ruling the roadmap explains, not a change to the tooling.
The markdownlint rule is no longer in this repository, so a change to it is a change to the engine, paired there with its account.
