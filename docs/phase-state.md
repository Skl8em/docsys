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

The current phase is declared once, in the ledger [`steering/phases.yaml`](../steering/phases.yaml): an ordered list of phases, each `done`, `current` or `planned`, the planned ones unnumbered (ADR-038).
It is the project's state, kept with steering; `phases:` in `docsys.yaml` only says where it is and how to read every other place that speaks of the current phase.
Two checks read it, in this order.

`phase-ledger` (`scripts/phase_ledger.py`) checks the ledger's own rules: a closed vocabulary, exactly one `current`, no number on a `planned` phase, done then current then planned, numbers counting from 1 without a gap.

`phase-state` (`scripts/phase_state.py`) checks every other place against it, each rule a pure function with fixtures:

- **folders** — a numbered phase has its folder, `phases/<era>/phase-<NN>-<name>`, and no tracked phase folder is missing from the ledger;
- **tables** — each phase row of the roadmap and the phases index carries the marker of the ledger's status (`done`, `in progress`, `unnumbered`; the text after a ` — ` is free), a row numbering a phase the ledger has not numbered fails, the current phase has a row, and a row pattern that matches nothing is an error, not a pass;
- **mentions** — no living document names, by number, a phase above the highest the ledger has numbered;
- **status** — the root README has one status line, and it names the current phase;
- **`phase:` fields** — each names a numbered phase, and none is behind the last closed phase unless the ledger lists it under `lagging:` with a reason; an allowance whose document has caught up fails, so the list cannot go stale.

Two scope choices are easy to undo by accident.
A **frozen record is not read for mentions**: it states what was true when it froze and cannot be edited, and [ADR-038](../phases/refoundation/phase-11-tooling-hardening/unstarted-work-unnumbered.md) itself quotes, as its example of the forbidden form, a sentence giving the next phase its number — a red there could never be cleared, and this fiche cannot repeat the example without failing the rule.
The **status file is not in the seam's leak check**: here it is the root `README.md`, which the frontmatter linter also names as the methodology's root document.

What the check does not do yet: verify that a closed phase's README says `done` and its records are sealed.
That rule, as planned, conflicts with ADR-031's choice to leave the naive-sketch era unsealed and rests on a `status` vocabulary nobody has ruled, so it was handed to the life-cycle phase ([roadmap](../steering/roadmap.md); open point 12 in the [Phase 12 plan](../phases/refoundation/phase-12-codifying/plan.md#open-points-and-when-each-is-settled)).

Starting a phase is one edit to the ledger, and the gate then names every place still describing the old one.
