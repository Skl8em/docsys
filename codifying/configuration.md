---
title: "docsys.yaml reference"
force: describe
verb: specify
intention: state
view: synchronic
provenance: { type: function, id: codifying }
constitutive: no
audience: [user, contributor]
reader: H+M
distance: far
power: none
status: draft
---

## Scope

This page lists every key `docsys.yaml` accepts in format version 1, what each means, and when a value is refused.
It does not say what each check verifies; that belongs with the checks.

## The file

`docsys.yaml` sits at the root of the workspace, the directory `docsys` works in (see the [README](../README.md)).
It is YAML, read with two departures from plain YAML: every scalar stays a string, so `version: 1` and `columns: 5` are read as text and converted where a number is meant, and a key repeated at any depth is an error.

The vocabulary is closed.
An unknown section or key is refused, and a section that is present must carry every one of its keys.

A refusal makes `docsys` exit `2`, with a message that starts `docsys.yaml:`, names the key and ends with a `fix:`.

## Sections

| Section | Required | Default when absent |
| --- | --- | --- |
| `version` | yes | — |
| `scope` | yes | — |
| `root_document` | no | `README.md` |
| `register` | no | the register checks do not run |
| `paired_change` | no | the paired-change rule does not run |
| `phases` | no | the phase checks do not run |

### `version`

The format of the file: `1`.
A version this `docsys` does not read is refused, naming the versions it reads.

### `scope`

The documents the framework governs, as two lists of patterns over paths relative to the workspace.

- `include` — required, at least one pattern.
- `exclude` — optional, empty by default.

A document is in scope when it matches an `include` pattern and no `exclude` pattern.
A document outside the scope is not checked.

A pattern is anchored at the workspace root and matches the whole path:

| Pattern | Matches |
| --- | --- |
| `docs/` | everything below the folder `docs` |
| `README.md` | that file, at the root only |
| `*` | any characters within one folder name or file name |
| `?` | one character within a name |
| `**/` | any number of folders, including none |
| `**` elsewhere | any characters, across folders |

Every other character matches itself.
A pattern that is empty, starts with `/` or contains a `..` segment is refused.

```yaml
scope:
  include: ["**/*.md"]
  exclude: [theorising/, "**/blind-test/"]
```

### `root_document`

The document that declares the tree's axis: a path relative to the workspace, `README.md` by default.
A path that starts with `/` or contains a `..` segment is refused.

### `register`

The central decision register, cross-checked against each record's `supersedes` and `superseded-by`.

| Key | Value |
| --- | --- |
| `path` | the register's file |
| `columns` | the number of cells in a decision row, an integer |
| `ordinal_column` | the cell holding the decision's ordinal, numbered from `0` |
| `status_column` | the cell holding its status, numbered from `0` |
| `ordinal_pattern` | a regular expression over the ordinal cell, with two groups: the ordinal, then the link to the record |
| `superseded_pattern` | a regular expression searched in the status cell, with one group: the ordinal of the superseding decision |

Both column numbers must fall inside the row.

### `paired_change`

The rule that a change to the mechanism touches something a person reads to understand it.

| Key | Value |
| --- | --- |
| `since` | the commit after which the rule applies: 7 to 40 lowercase hexadecimal digits |
| `mechanism` | path prefixes whose change needs an account, at least one |
| `understanding` | path prefixes that give the account, at least one |
| `exempt` | path prefixes that need no account, possibly none |
| `enforce_on` | the branches on which the rule fails rather than warns, at least one |

### `phases`

Where the phase ledger is, and how to read every other place that names the current phase.

| Key | Value |
| --- | --- |
| `ledger` | the ledger's file |
| `root` | the folder holding the phase records |
| `folder` | the name of a phase's folder, a format with `{number…}` and `{name}` |
| `field` | the value of a `phase:` frontmatter field, a format with `{number…}` and `{name}` |
| `markers` | the word a table shows for each of `done`, `current` and `planned`, three distinct words |
| `tables` | at least one `{path, row}`: a file listing the phases, and a regular expression over its phase rows with the named groups `number` and `marker` |
| `status` | `{path, line}`: the file holding the status line, and a regular expression that finds it with the named group `number` |
| `mention` | a regular expression for a phase named in prose, with the named group `number` |

## Out of scope

- What each check verifies, and the severity of its findings: with the checks, as they are ported.
- The frontmatter vocabulary, explained by the documentation system's [`writing/frontmatter.md`](https://github.com/Skl8em/documentality/blob/main/writing/frontmatter.md).
