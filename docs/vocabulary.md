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

## Why YAML is the source

The schema used to be JSON.
JSON cannot carry a comment, and the vocabulary is exactly the kind of file where the *reason* for a line matters more than the line: the file had grown a `"//"` key as a comment substitute.
The file's name, `frontmatter.schema.json`, also claimed a JSON Schema dialect that the hand-written validator never implemented, so no standard tool could consume it.

YAML fixes the first and the rename fixes the second.
The reason is enforced, not hoped for: every key of `optional_fields` must carry a non-empty rationale string, and the linter refuses to load the schema if one does not.
A field cannot be declared without being justified, because the two are the same act.

## The trap the pipeline already fell into

YAML 1.1 reads bare `yes` and `no` as booleans.
Compiled with a plain `yaml.safe_load`, `error_enums.constitutive: [yes, no]` became `[true, false]`, which silently broke that enum.
It is the same trap that frontmatter *documents* carry, reappearing in the schema's own source.

The generator therefore loads through `StrictLoader` in [`scripts/yaml_frontmatter.py`](../scripts/yaml_frontmatter.py): scalars stay strings and only `null` resolves, and a duplicate key is an error at any depth, since `pyyaml` would otherwise keep the last one silently.
The loader is shared by the document reader and the generator, so the fix is made once.
The rule for a maintainer: **never load this vocabulary through a bare `safe_load`**, in a new script or a test.

## What the linter still knows that the schema does not say

The schema is data, but not all of what the linter enforces is in it.
The linter's *code* encodes that the direction-of-fit table must partition `force` exactly, that `register` is derived and never stored, that the root README alone carries `axis` and `dominant-community`, and how a composite force `a+b` is read.
Changing the vocabulary is an edit to the YAML; changing what the vocabulary is *allowed to express* is an edit to code.
The schema-load refusals (a partition that does not cover the forces, an optional field without a reason) exist because those code-level assumptions can be broken from the data side.

One duplication sits outside this pipeline and is named so a maintainer is not surprised by it: `hash_seal.py` decides which `status` words make a record *frozen*, and the schema declares which words exist.
The definition stays in code, deliberately: the schema lists its status vocabulary among the questions it still leaves open, and a `frozen` declaration in it would rule on part of that question by side effect.
`hash_seal.py` therefore classifies every status word twice over, `FROZEN_STATUSES` and `OPEN_STATUSES`, and `scripts/test_hash_check.py` fails the gate when the two lists together stop matching `warn_enums.status` — a word added to the schema and classified nowhere, a word the schema dropped, a word in both.
So a schema edit that adds a status is met at the gate with the edit that clears it, not discovered as a record that silently never gets sealed.
The definition moves into the schema when the status vocabulary is ruled.
