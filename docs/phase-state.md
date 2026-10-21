---
title: "The phase ledger and the phase-state check — where the project is, said once"
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

**Read this before** changing the ledger's format, what a phase-state rule reads, or which documents the mention rule skips.
It is written for the maintainer of `docsys`, initiated in tooling engineering.

## Why a ledger

A project that works in phases says where it is in many places: a roadmap, an index of phases, a status line in its README, the folders of its phase records, a `phase:` field in some documents.
Nothing ties them together, so each phase closes with some of them stale; the documentation system closed two phases that way before it kept a ledger.
The ledger says it once, and every other place is checked against it.
A project with no `phases:` section in `docsys.yaml` keeps no ledger, and neither check runs.

## The ledger check

The ledger check, [`src/docsys/checks/ledger.py`](../src/docsys/checks/ledger.py), reads the file `phases.ledger` names: an ordered list of phases, each a `name`, an `era` and a `status` of `done`, `current` or `planned`, the done and current ones with a `number`, and an optional `lagging:` list of documents allowed to stay behind, each with its `reason`.
It checks the ledger's own rules:

- the file exists and is YAML (`ledger/missing`, `ledger/yaml`);
- the vocabulary is closed and each entry complete (`ledger/shape`), names and eras hyphen-cased and statuses known (`ledger/form`);
- a planned phase has no number, because unstarted work is named and never numbered ([ADR-038](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-11-tooling-hardening/unstarted-work-unnumbered.md)), and the numbers count from 1 without a gap (`ledger/number`);
- names are unique (`ledger/unique`), exactly one phase is current (`ledger/current`), and the list runs done, then current, then planned (`ledger/order`);
- each `lagging:` entry names one document and gives a reason (`ledger/lagging`).

It reads the ledger with every scalar a string, like `docsys.yaml`, and with the line of every value, so each finding is on the line it is about.
When an entry is malformed, only the findings about entries and about `lagging` are reported: the order and numbering rules read well-formed entries, and would otherwise report the same defect twice under other names.

## The phase-state check

The phase-state check, [`src/docsys/checks/phase_state.py`](../src/docsys/checks/phase_state.py), reads every other place against the ledger.
Where each place is, and the shape of its rows, is the project's: `phases:` in `docsys.yaml`, whose keys the [`docsys.yaml` reference](https://github.com/Skl8em/documentality/blob/main/codifying/docsys-configuration.md) lists.

- **Folders** (`phase-state/folder`) — a numbered phase has its folder, `<root>/<era>/<folder>`, and every folder at that depth under `<root>` is one the ledger gives a phase; a folder exists when a file of the workspace is in it, since git keeps no empty folder.
- **Tables** (`phase-state/table`) — each phase row of a configured table carries the marker of its ledger status; a row that numbers a phase the ledger has not numbered fails; the current phase has a row; and a row pattern that matches no row is an error, not a pass, since a reworded table would otherwise switch the rule off without a word.
- **Mentions** (`phase-state/mention`) — no document in scope names, by number, a phase above the highest the ledger has numbered.
- **Status** (`phase-state/status`) — the file `phases.status` names has exactly one status line, and it names the current phase.
- **`phase:` fields** (`phase-state/field`, `phase-state/lagging`) — each names a numbered phase of the ledger, and none is behind the last closed phase unless the ledger lists it under `lagging:`; an allowance whose document has caught up, or has no `phase:`, is itself reported, so the list cannot go stale.

When the ledger is missing or breaks its own rules there is nothing to compare: the check reports that once (`phase-state/ledger`), after the ledger check has said why, and reads nothing else.

## Two choices that are easy to undo by accident

**A frozen record is not read for mentions.**
It states what was true when it froze and cannot be edited, so a finding in it could never be cleared.
ADR-038 itself quotes, as its example of the forbidden form, a sentence giving the next phase its number; read for mentions, it would fail forever.
A frozen record is one whose `status` the fixity check counts as frozen (`FROZEN_STATUSES` in [`hashes.py`](../src/docsys/checks/hashes.py)).

**The era name is not a number.**
The documentation system calls an era "Phase II"; the `mention` pattern of a project has to match a number, and the conformance cases hold a mention of the era as not a finding.

## What the checks do not establish

- **That a place which agrees with the ledger is true.**
  A status paragraph can name the right phase and describe it wrongly.
- **That the ledger is true.**
  Starting a phase is one edit to the ledger, and the checks then name every place still describing the old one; they cannot tell a ledger that moved too early.
- **That a closed phase is closed.**
  Whether a done phase's records are complete or sealed is the project's closure rule, not a rule of these checks.

## Where a maintainer touches this

- **A new place that names the current phase** is a new key of `phases:`, read in `config.py`, and a rule here, with cases in [`conformance/phase-state.yaml`](../conformance/phase-state.yaml) showing it agree and disagree.
- **A change to the ledger's format** changes [`conformance/ledger.yaml`](../conformance/ledger.yaml) first; the format is part of what every `docsys` package reads.
- **A message** carries a `fix:`, and the conformance runner fails a finding that does not ([the error-message audit](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-12-codifying/error-message-audit.md) sets the standard).
