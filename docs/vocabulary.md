---
title: "The vocabulary and its reader — what the schema says, and what the frontmatter check knows beyond it"
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

**Read this before** editing `src/docsys/schema/frontmatter-rules.yaml`, the strict YAML loader, or anything that judges a frontmatter.
It is written for the maintainer of `docsys`, initiated in tooling engineering.
What each frontmatter coordinate *means* is the documentation system's [`operationalizing/`](https://github.com/Skl8em/documentality/blob/main/operationalizing/README.md); its [`writing/frontmatter.md`](https://github.com/Skl8em/documentality/blob/main/writing/frontmatter.md) explains the fields to the people who fill them.

## The vocabulary, and why it is YAML

[`src/docsys/schema/frontmatter-rules.yaml`](../src/docsys/schema/frontmatter-rules.yaml) declares the required fields, the enumerations, the fields only the root document carries, the direction-of-fit table, what is still undecided, and every optional field with the reason it exists.
It ships inside the package, and [`schema.py`](../src/docsys/schema.py) is its one reader.

It is YAML because the reason for a line matters more than the line, and JSON cannot carry a comment.
The reason is enforced, not hoped for: an optional field without a non-empty rationale makes the vocabulary refuse to load, so a field cannot be declared without being justified, the two being one act.
The vocabulary is closed: a field it does not declare is an error in a document (`frontmatter/vocabulary`).

The vocabulary is judged before any document is: a section missing or unknown, an optional field without its reason, or a direction-of-fit table that does not partition the forces exactly is refused with its `fix:`, since every document would otherwise be judged by an incoherent rule.

## The strict loader

YAML 1.1 reads bare `yes` and `no` as booleans, an all-digit ULID as an integer and a date as a date.
Loaded with a plain `yaml.safe_load`, the vocabulary's own `constitutive: [yes, no]` becomes `[true, false]`, which breaks that enumeration silently; the documentation system's schema pipeline fell into exactly this.
So everything is loaded through `StrictLoader` in [`yaml_frontmatter.py`](../src/docsys/yaml_frontmatter.py): scalars stay strings and only `null` resolves, and a key repeated at any depth is an error, since `pyyaml` would otherwise keep the last one silently.
The documents, the vocabulary, `docsys.yaml` and the phase ledger all load through it, so the fix is made once.
The rule for a maintainer: **never load any of them through a bare `safe_load`**, in new code or in a test.

## What the check knows that the vocabulary does not say

The vocabulary is data, but not all of what the frontmatter check enforces is in it.
The code of [`checks/frontmatter.py`](../src/docsys/checks/frontmatter.py) and of `schema.py` encodes:

- that the direction-of-fit table partitions `force` exactly, so `register` can be derived from it;
- that `register` is derived — `govern` when the document is constitutive, otherwise the register of its force — and never stored (`frontmatter/register`);
- that the root document alone carries the root-only fields (`frontmatter/root-only`), the root being the one `root_document` names in `docsys.yaml`;
- how a composite force `a+b` is read: each component is a force.

Changing the vocabulary is an edit to the YAML; changing what the vocabulary is *allowed to express* is an edit to code.
The load-time refusals exist because those code-level assumptions can be broken from the data side.

## Which statuses close a record

The vocabulary declares the `status` words and lists, among its still-open questions, that current documents and frozen records use different ones; it does not say which words close a record.
[`checks/hashes.py`](../src/docsys/checks/hashes.py) does, deliberately: a `frozen` declaration in the vocabulary would rule on part of that open question by side effect.
It classifies every word twice over, `FROZEN_STATUSES` and `OPEN_STATUSES`, and [`tests/test_hashes.py`](../tests/test_hashes.py) fails when the two lists together stop matching the vocabulary — a word added and classified nowhere, a word dropped, a word in both.
Two checks rely on the answer: the fixity check seals and verifies a frozen record, and the phase-state check does not read one for mentions.
So a vocabulary edit that adds a status is met in the suite with the edit that clears it, not discovered as a record that is silently never sealed.
The definition moves into the vocabulary when the status vocabulary is ruled.

## What this does not establish

- **That the vocabulary is right.**
  The load-time checks establish that it is coherent, not that its words are the correct ones; what is undecided is listed in its own `still_open`.
  A value outside the current practice of a field it has not ruled on (`warn_enums`) is a warning, `frontmatter/open`, never an error, so a red never means unsettled.
- **That code reads the vocabulary through `schema.py`.**
  A check that hard-coded an enumeration would not be caught.
