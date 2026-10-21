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

**Read this before** changing what counts as a change to the mechanism, how the unit of change is cut, or where the rule fails rather than warns.
It is written for the maintainer of `docsys`, initiated in tooling engineering.
The rule was decided for the documentation system in [ADR-039](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-12-codifying/paired-change-rule.md) and refined by [ADR-040](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-12-codifying/paired-change-where-it-fails.md); this fiche explains the check that enforces it.

## What is checked

The paired-change check, [`src/docsys/checks/paired_change.py`](../src/docsys/checks/paired_change.py), fails a unit of change that touches the project's mechanism and nothing a person reads to understand it (`paired-change/unpaired`).
Which paths are which is the project's: `paired_change:` in `docsys.yaml` lists the `mechanism` prefixes, the `understanding` prefixes (a prefix may name one file), the `exempt` prefixes that need no account, the commit the rule starts after (`since`) and the branches it is enforced on (`enforce_on`).
The [`docsys.yaml` reference](https://github.com/Skl8em/documentality/blob/main/codifying/docsys-configuration.md) lists the keys; a project without the section does not run the check.

A finding is on the first mechanism file of the unit that lacks an account, at line 1, since the defect is in a commit and not at a line; findings come in the order of the commits, oldest first, the uncommitted work last.
Two findings are about the configuration, on `docsys.yaml` at line 1: `paired-change/anchor` when `since` is no commit of this history or not an ancestor of `HEAD`, and `paired-change/branches` when `enforce_on` names no branch the repository has.
The cases are in [`conformance/paired-change.yaml`](../conformance/paired-change.yaml), each with the git history it runs on.

## Five properties that are easy to get wrong

**The unit is the commit, not the branch.**
The check examines every non-merge commit after `since`, and the uncommitted work that will become the next one, each on its own.
A branch-level rule passes the very case that motivated the rule: tried against a phase-long branch of the documentation system, it passed, because the branch touched three explaining documents incidentally and any such edit paired every script edit.
So a later commit that edits a document never pairs an earlier commit that changed the mechanism, and the account goes in the same commit as the change.
A merge commit is not a unit: it brings in another line's history, which is that line's to answer for.

**Two kinds of change are not a change to the mechanism.**
A file under an `exempt` prefix, typically the tests, and a Python edit whose syntax tree, docstrings set aside, is unchanged — comments, docstrings, formatting — have nothing to explain, so they need no account, on any branch.
The second is a comparison of the file before and after (`comment_only`), so it is a heuristic on the tree and not on intent: a docstring that replaces the description of unchanged behaviour passes, and only Python is examined.
A version that does not parse, or a file added or deleted, is never comment-only.
A rename is read as a deletion and an addition, so moving a file out of the mechanism is caught by its old path.

**It fails only where work lands.**
On a branch in `enforce_on` and on a detached `HEAD`, which is what CI checks out for a pull request, a unit without its account is `paired-change/unpaired`, an error.
On any other branch the same unit is `paired-change/advisory`, a warning naming the branch and where the rule is enforced, so a commit that changes the mechanism may precede the one that explains it while the work is in progress.
The cost moved, it did not vanish: the pull request examines every commit since the anchor, so the earlier commit fails there and has to be amended or squashed with its account.
If the integration branch is renamed and `enforce_on` is not, the rule would quietly become a warning everywhere; so `paired-change/branches` fails when no listed branch exists, locally or on a remote, since a CI checkout is detached and holds remote refs only.

**The anchor is the only exemption from history, and it shows in a diff.**
Commits up to and including `since` are not examined.
A commit already made without its account cannot be repaired by adding the account afterwards; moving `since` past it is the way to accept it, and that is an edit to `docsys.yaml` a reviewer sees.
An anchor that cannot be resolved is an error, never a pass, and the finding says which case it is: a shallow clone, whose fix is to fetch the full history (`fetch-depth: 0` in CI), a commit that is not in this history, or one that is not an ancestor of `HEAD`.

**It reads git, so it depends on where it runs.**
Run by hand or from a pre-commit hook it sees the working tree: the uncommitted unit is the difference between `HEAD` and the files, staged or not.
In CI it sees the commits pushed.
Paths are the workspace's, so a workspace that is a folder of a larger repository sees only its own changes.

## What the check does not establish

- **That the account is right.**
  It checks co-occurrence, and a one-word edit to an explaining document passes; what it removes is the silent case.
- **That a file nothing tracks needs an account.**
  An untracked file is in no unit: no commit holds it, and the difference against `HEAD` does not show it.
  It is examined once it is staged, which is before it can be committed, so a pre-commit hook still meets it; a run made earlier does not.
- **That the lists are right.**
  A mechanism path missing from `mechanism` is never examined, and the check cannot know it exists.

## Where a maintainer touches this

- **A new kind of trivial change** — an edit with nothing to explain, in a language other than Python — needs its own comparison beside `comment_only`, and cases in the conformance file showing both the trivial edit and the real one.
- **A change to what a unit is** changes every finding's meaning; the cases that build histories (a later document, a merge, a deletion, a move) are the ones to read first.
- **A message** carries a `fix:`, and the conformance runner fails a finding that does not ([the error-message audit](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-12-codifying/error-message-audit.md) sets the standard).
