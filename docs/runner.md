---
title: "The runner — why every check runs, and what makes a run fail"
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

**Read this before** adding a check, changing a rule's default severity, or changing what `docsys check` prints or exits with.
It is written for the maintainer of `docsys`, initiated in tooling engineering.

## What a run is

`docsys check` finds the workspace, reads `docsys.yaml`, and calls each check of `CHECKS` in [`src/docsys/runner.py`](../src/docsys/runner.py) with the workspace and the configuration.
A check returns its findings; it does not print, exit or decide how serious they are.
The runner gives each finding the severity its rule has in this workspace, and the command prints what is not off and exits.

| Exit | Means |
| --- | --- |
| `0` | no finding is an error (warnings may exist) |
| `1` | at least one finding is an error |
| `2` | the run could not happen: no workspace, a refused configuration, a workspace outside git |

The codes are the cross-package API's ([`exitcodes.py`](../src/docsys/exitcodes.py)): a script in front of any `docsys` package can tell a project that fails its rules from a run that did not happen.

## Why every check runs

A check that fails does not stop the ones after it.
The run is the conjunction of its checks, and the reader of a failing run, often a machine that cannot ask, needs every failure from one run, not the first.
A check that cannot read a document leaves it to the check that owns the reading (the frontmatter check owns an unreadable frontmatter), so one defect is reported once and by the right check.

## Why the order is fixed

`CHECKS` follows the order of the rules in [`rules.py`](../src/docsys/rules.py): links, frontmatter, ULIDs, slugs, fixity, paired change, phase ledger, phase state.
Findings are printed in that order, then by path and line within a check, so two runs on the same tree print the same text.
The order is a reading order, not a dependency: no check relies on another having run.
The phase-state check reads the ledger itself, and reports `phase-state/ledger` when the ledger is unusable, after the ledger check has said why.

## Why a section turns a check on

A check whose section `docsys.yaml` leaves out returns no finding: the register, the paired-change rule and the phases are the project's, and a project without them has nothing for the check to compare with.
The runner does not decide this.
Each check does, from its own section, so a check called directly (as the conformance suite calls it) behaves as it does in a run.

## Severity

A rule's default severity is set where the check names the rule (`Rule("links/resolve", "error")`), and is the methodology's: a rule stated as a heuristic is a `warning`, one not yet wanted by default is `off`.
[`rules.severities`](../src/docsys/rules.py) overlays the project's `rules:` section on the defaults.
It refuses a rule no check has, naming the rules that exist, because a misspelt rule that silently changed nothing would read as a rule turned off.

The check still reports a finding of a rule that is `off`, and the runner drops it.
Whether a rule runs is therefore decided in one place, and a check does not have to know about the project's severities.
The cost is that an `off` rule is still computed; none is known to be expensive, and the day one is, the runner can skip it.

## What a green run does not say

The runner reports findings; it has no opinion on a document no check reads.
A document outside the scope is not checked, so a run that passes says nothing about the documents the project excluded; `docsys report` lists them.
A rule at `off` or `warning` does not fail the run, so a project that turns rules down passes by having asked less.
