# `legacy/` — code kept as found

**`migrate_ids.py` does not run as it stands.**
It is copied unchanged from the documentation system's `scripts/`, and it imports two modules of that folder, `ulid` and `rename_doc`, which the engine replaced with [`docsys.ulid`](../src/docsys/ulid.py) and [`docsys.rename`](../src/docsys/rename.py) (the commands `docsys id` and `docsys rename`).

## Why it is kept

It renames count-named records to `<slug>-<ulid>` and writes `id` and `slug` into their frontmatter: the ULID-in-filename direction of the naming convention of ADR-028, the inverse of `docsys slugify`.
The convention stays open in both directions, and the day a project wants global uniqueness in the filename this is the tool that would be ported.
Until then it is parked: the [roadmap](https://github.com/Skl8em/documentality/blob/main/steering/roadmap.md) lists it under *Parked*, with no position in the sequence.

## What it needs to run

Port it, do not patch it: take the ULID from `docsys.ulid.new_ulid` and the move from `docsys.rename.rename`, type it, and give it tests.
Until then nothing imports it, ruff and basedpyright do not read this folder, and the engine's checks read it only as the documents it holds.
