---
title: "The author tools — why they write what the checks verify, and where each refuses"
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

**Read this before** changing what `docsys id`, `seal`, `rename` or `slugify` write, or the order in which they decide.
It is written for the maintainer of `docsys`, initiated in tooling engineering.

## What they are for

A check says what is wrong; an author tool writes what the check wants, so the fix is a command rather than a hand edit that can miss.
Each tool is the other half of a check, and takes its rule from that check's module instead of restating it: `id` mints what the ULID check validates ([`ulid.py`](../src/docsys/ulid.py)), `seal` writes what the fixity check verifies ([`checks/hashes.py`](../src/docsys/checks/hashes.py)), `rename` rewrites the links the link check reads ([`checks/links.py`](../src/docsys/checks/links.py)), and `slugify` makes the name the slug check accepts ([`checks/slugs.py`](../src/docsys/checks/slugs.py)).
A change to a rule is made in the check; the tool follows by import, and for `seal`, `rename` and `slugify` a test runs the check on what the tool wrote, so a tool that wrote what its check then refuses fails there.

They were extracted from `scripts/ulid.py`, `hash_seal.py`, `rename_doc.py` and `slugify_names.py` of the documentation system's repository, test first.

## Where each one refuses

- **`id`** needs no workspace, since the identifier exists before the document does.
  It refuses a date it cannot read and an order outside 48 bits, with exit `2`; the module raises `ValueError`, and only the command turns it into an exit code, so the library can be used without a process exit.
- **`seal`** never overwrites a seal that no longer matches unless `--reseal` is given.
  A seal that fails to match is the signal the check exists to give, and a tool that silently refreshed it would erase the signal; re-sealing is a deliberate act, so it is a flag and the default is a report with exit `1`.
  `--frozen` reads each frontmatter as YAML to decide whether a record is frozen, and a failure to read stops the command: a record taken for not frozen because its YAML failed would simply go unsealed.
  The seal is computed over lines, not parsed YAML, as the check does, and the tool keeps line endings and every other byte.
- **`rename`** computes the whole change before it moves anything, so a move that cannot be made, or a document it cannot read, changes nothing.
  It reads links as the link check does, line by line with the same pattern, so a link the check would not read is not rewritten; a link whose target it cannot place (a web link, an anchor, a placeholder, an absolute path) is left as written.
  It maps a path by prefix, so a link to the moved folder itself, and to a file in it, are both rewritten.
  The script it replaces mapped only the files, and left a link to a folder inside a moved folder pointing at the old place.
- **`slugify`** plans every rename, then refuses the lot if a name is taken or wanted twice.
  It leaves alone the `<slug>-<id>` name, which the slug check accepts; `slugify_names.py` renamed it to `<slug>.md` too, which undid a convention the check allows.
  A slug that cannot name a file is reported and skipped, never repaired by guessing a spelling.

## A rewritten link breaks a seal

`rename`, and `slugify` through it, rewrite links in every document of the scope, sealed records included.
The seal covers the record's content, links among it, so a rewrite makes it fail the fixity check.
The tools do not hide this and do not renew the seal on their own: they list each sealed record they rewrote with `docsys seal --reseal PATH`, and the author decides.
The alternative, leaving the frozen record's link dead and allowing it in `links.allow`, keeps the seal and costs an allowance with its reason.
Which is right depends on whether the record's meaning is its link target or its words, and the roadmap parks the question of what a freeze covers (*Life cycle*), so the tools state the choice instead of making it.

## What they do not do

They do not check; run `docsys check` after them.
They do not rewrite a path written in prose, or the display text of a link.
`rename` does not move a `links.allow` entry or a `register` row that names the moved document, and does not follow a file referenced from `docsys.yaml`: the next `docsys check` reports a stale allowance or a missing register entry, with its fix.
`migrate_ids.py`, the inverse of `slugify`, is kept in [`legacy/`](../legacy/README.md) and does not run.

## Where a maintainer touches this

- **A new thing a tool writes** is first a rule in a check, and then a function the tool imports from it; do not copy a rule into a tool.
- **The links `rename` reads** are the check's `LINK_RE` and `NOT_RESOLVED`; if the check learns a new kind of link, `_rewrite_target` in [`rename.py`](../src/docsys/rename.py) learns it with a test in [`tests/test_rename.py`](../tests/test_rename.py).
- **A new status that closes a record** is added to `FROZEN_STATUSES` in the fixity check; `seal --frozen` follows.
- **The command line** is in [`cli.py`](../src/docsys/cli.py), and its reference for a project is the documentation system's [`docsys-commands.md`](https://github.com/Skl8em/documentality/blob/main/codifying/docsys-commands.md).
