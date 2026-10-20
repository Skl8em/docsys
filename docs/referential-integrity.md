---
title: "Referential integrity — why a pointer that points nowhere fails the check"
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

**Read this before** changing how records are identified, how supersession is stored, or the shape of the decision register.
It is written for the maintainer of `docsys`, initiated in tooling engineering.
It explains a *mechanism*; what supersession means as a coordinate belongs to the documentation system's [`operationalizing/`](https://github.com/Skl8em/documentality/blob/main/operationalizing/README.md), whose orient lists that fiche among those still to write.

## What is checked

The ULID check, [`src/docsys/checks/ulids.py`](../src/docsys/checks/ulids.py), does two things: it checks that every `id` is a valid, unique ULID (`ulids/form`, `ulids/unique`), and it checks the pointers between records.
A record without an `id` is permitted; wherever something names it, its identity is its filename stem, the convention that predates ULIDs and that most of the documentation system's records still follow.
A document whose frontmatter cannot be read is skipped here and reported once, by the frontmatter check.

Four rules catch the ways `supersedes` / `superseded-by` can go stale without anything failing:

1. **Every non-null reference resolves** (`ulids/resolve`).
   The target is some record's `id`, or its filename stem.
   A rule that resolved by `id` alone would fail almost every reference in a corpus where few records carry one.
   A `<...>` placeholder, as in a force template's specimen frontmatter, is not a reference and is skipped.
2. **Supersession is symmetric** (`ulids/symmetric`).
   If A names B in `supersedes`, then B's `superseded-by` names A, and the other way round.
3. **No record supersedes itself, and no chain loops** (`ulids/self`, `ulids/cycle`).
   Neither is caught by the two rules above, because they hold trivially: in a pair where A and B each supersede the other, each names the other and is named back, and a record that names itself does so in both directions.
   A self-reference is reported on the record, and dropped before the symmetry and cycle rules run, so it is reported once.
   A cycle is followed along `superseded-by`, the chain from a record to what replaced it, and is reported once, at the record of the loop whose path sorts first, with the route.
   A loop leaves no record that still binds, which is the one thing a supersession chain has to end in.
4. **The register agrees** (`ulids/register`), when the project keeps one.
   The rule runs only when `register:` is set in `docsys.yaml`; the [`docsys.yaml` reference](https://github.com/Skl8em/documentality/blob/main/codifying/docsys-configuration.md) lists its keys.
   Each row that says "superseded by N" is checked against that record's own `superseded-by`, and a row that says no such thing against the record having none.
   The register's path and row shape are the project's; the package knows the *idea* of a register, not any one register.
   A register path that is not a document of the workspace is reported on `docsys.yaml`.
   A register in which the configured row shape matches no row at all is reported too, rather than passing for want of anything to compare: a renamed column or a reworded ordinal would otherwise switch the rule off without a word.

## Why a dangling pointer is an error, not a warning

The register is meant to be read as the set of decisions that still bind ([ADR-032](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-10-schema/adr-tiering.md)).
A supersession pointer is how a reader learns that a decision no longer does.
A pointer that resolves to nothing removes that knowledge silently, in the one document meant to be the project's authoritative governance line, and a check that only read fields would pass it.

## Why supersession is stored in both directions, and must agree

The schema declares `superseded-by` as "the inverse of `supersedes`, kept symmetric" — a stored inverse, which is redundancy, and redundancy that nothing enforces drifts.
The check enforces it.

The reason that survives contact with the mechanism is the reader.
No decision record argues it; this is the reasoning, not a quotation of one [medium confidence].
A record is usually reached by a link, and an old record read alone must say it has been replaced; that needs the pointer *on the old record*.
The successor must, in turn, say what it replaced.
Either direction alone leaves one of them silent, and each record has to be sufficient by itself, since a fixity seal ([ADR-031](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-10-schema/content-hash-fixity.md)) is per record and travels with it.

This claim belongs upstream: it is about what `supersedes` means, not how the check runs, and it is carried here until an operationalizing fiche for `supersedes` exists.

### The cost, which is real

A supersession *edits the old record*, and the old record is frozen.
When a decision is superseded, its `superseded-by` is set after the fact, which changes its frontmatter and so breaks its seal; the record is then re-sealed deliberately.
The documentation system's [`hosting-codeberg-github-mirror.md`](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-10-schema/hosting-codeberg-github-mirror.md) went through exactly this when ADR-034 replaced it.
The design rule is that the pointer is kept live and only the decision's own reasoning is fixed; the seal covers both, so the exception has to be made by hand each time.
The fixity check's `hashes/seal` finding gives the new seal in its `fix:`, so a maintainer meets this at the check, not by surprise.

## What the check does not establish

It does not establish that a pointer names the *right* record, only that the record exists, points back, and is not part of a loop.
Whether a register row's *decision text* matches its record is likewise beyond it; it compares status text to the pointer.

## Where a maintainer touches this

- **A new kind of reference** (a field that names another record) needs a place in `REF_FIELDS`, its inverse in `INVERSE`, and cases in [`conformance/ulids.yaml`](../conformance/ulids.yaml).
  A case there is the documents of a small workspace and the findings expected on them, as data, so the deliberately broken cases are never documents of a real workspace and any `docsys` package, in any language, is held to the same rules.
- **A new rule** is declared under `rules:` in that file with its default severity and statement, and added to `RULES`; [`tests/test_conformance.py`](../tests/test_conformance.py) fails when the two disagree, or when a declared rule is reported by no case.
- **A different register shape** is a `docsys.yaml` edit; the cases already run the check against a second shape (four columns, another folder, "replaced by") to show nothing here is specific to one project's register.
- **A message** carries a `fix:`, and the conformance runner fails a finding that does not ([the error-message audit](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-12-codifying/error-message-audit.md) sets the standard).
