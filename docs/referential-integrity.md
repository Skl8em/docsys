---
title: "Referential integrity — why a pointer that points nowhere fails the gate"
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
It is written for the maintainer, initiated in tooling engineering.
It explains a *mechanism*; what supersession means as a coordinate is [`operationalizing/`](../operationalizing/README.md)'s, and that fiche is not written yet — the [operationalizing orient](../operationalizing/README.md) lists it among the apports still to write.

## What is checked

[`scripts/ulid_check.py`](../scripts/ulid_check.py) does two things: it checks that every `id` is a valid, unique ULID, and — since Phase 11 — it checks the pointers between records.
Four checks, each catching a way `supersedes` / `superseded-by` can go stale without anything failing:

1. **Every non-null reference resolves.**
   The target is some record's `id`, or its filename stem — the pre-ULID way to name a record, which most of the corpus still uses.
   Only a few records carry an `id`, so a rule that resolved by `id` alone would have failed almost every reference.
   A `<...>` placeholder, as in a force template's specimen frontmatter, is not a reference and is skipped.
2. **Supersession is symmetric.**
   If A names B in `supersedes`, then B's `superseded-by` names A, and the other way round.
3. **No record supersedes itself, and no chain loops.**
   Neither is caught by the two rules above, because they hold trivially: in a pair where A and B each supersede the other, each names the other and is named back, and a record that names itself does so in both directions.
   A self-reference is reported on the record.
   A cycle is followed along `superseded-by`, the chain from a record to what replaced it, and is reported once, at the first record of the loop in path order, with the route.
   A loop leaves no record that still binds, which is the one thing a supersession chain has to end in.
   It was a hole in Phase 11's check, found while this fiche was first written and closed in Phase 12 T4.
4. **The register agrees.**
   Each row of the central decision register that says "superseded by N" is checked against that record's own `superseded-by`, and a row that says no such thing against the record having none.
   The register's path and row shape are this repository's instance, read from `register:` in [`docsys.yaml`](../docsys.yaml); the engine knows the *idea* of a register, not this one.
   A register in which the configured row shape matches no row at all fails, rather than passing for want of anything to compare: a renamed column or a reworded ordinal would otherwise switch the check off without a word, the same silent fallback the seam work removed for a missing register file.

## Why a dangling pointer is a hard error, not a warning

The register is meant to be read as the set of decisions that still bind ([ADR-032](../phases/refoundation/phase-10-schema/adr-tiering.md)).
A supersession pointer is how a reader learns that a decision no longer does.
A pointer that resolves to nothing removes that knowledge silently, in the one document meant to be the project's authoritative governance line, and leaves the gate green.

The trigger was concrete.
ADR-034's `supersedes` had been checked by hand; a typo there would have produced a dangling supersession on a passing gate.
Phase 11 makes that a failure.

## Why supersession is stored in both directions, and must agree

The schema declares `superseded-by` as "the inverse of `supersedes`, kept symmetric" — a stored inverse, which is redundancy, and redundancy that nothing enforces drifts.
The check enforces it.

The reason that survives contact with the mechanism is the reader.
No phase record argues it; this is the reasoning, not a quotation of one [medium confidence].
A record is usually reached by a link, and an old record read alone must say it has been replaced; that needs the pointer *on the old record*.
The successor must, in turn, say what it replaced.
Either direction alone leaves one of them silent, and each record has to be sufficient by itself, since a fixity seal ([ADR-031](../phases/refoundation/phase-10-schema/content-hash-fixity.md)) is per record and travels with it.

This is the claim that belongs upstream: it is about what `supersedes` means, not how the check runs, and it is carried here until an operationalizing fiche for `supersedes` exists.

### The cost, which is real

A supersession *edits the old record*, and the old record is frozen.
When a decision is superseded, its `superseded-by` is set after the fact, which changes its frontmatter and so breaks its seal; the record is then re-sealed deliberately.
[`hosting-codeberg-github-mirror.md`](../phases/refoundation/phase-10-schema/hosting-codeberg-github-mirror.md) went through exactly this when ADR-034 replaced it.
The design rule is that the pointer is kept live and only the decision's own reasoning is fixed; the seal covers both, so the exception has to be made by hand each time.
`hash_check.py` prints the re-seal command in its failure line, so a maintainer meets this at the gate, not by surprise.

## What the check does not establish

It does not establish that a pointer names the *right* record, only that the record exists, points back, and is not part of a loop.
Whether a register row's *decision text* matches its record is likewise beyond it; it compares status text to the pointer.

## Where a maintainer touches this

- **A new kind of reference** (a field that names another record) needs a place in `REF_FIELDS` and a stated inverse, and a fixture — [`scripts/test_ulid_check.py`](../scripts/test_ulid_check.py) is the model, with each case a small dict of records rather than a file in the corpus, so the deliberately broken cases need no exemption from the gate that runs them.
- **A different register shape** is a `docsys.yaml` edit; the fixtures already run the engine against a second shape (four columns, "replaced by") to show nothing here is specific to this repository's register.
- **A message** carries `fix:`, and the fixtures fail a case whose message does not ([the audit](../phases/refoundation/phase-12-codifying/error-message-audit.md)).
