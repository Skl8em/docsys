---
title: "docsys — the engine of the documentation system"
force: orient
intention: formative
view: synchronic
provenance: { type: function, id: codifying }
constitutive: no
audience: [user, contributor]
reader: H+M
status: draft
---

`docsys` checks a project's documentation against the [documentation system](https://github.com/Skl8em/documentality): every document carries a frontmatter that declares what it does and for whom, and `docsys` verifies that frontmatter, the identifiers and links between documents, and the fixity of frozen records.

It is a Python package that a project declares as a development dependency.
It installs, finds its workspace — the nearest directory holding `docsys.yaml`, or the one `--workspace` names — and reads that file, whose keys the documentation system's [`docsys.yaml` reference](https://github.com/Skl8em/documentality/blob/main/codifying/docsys-configuration.md) lists.
Its checks were extracted, one at a time and test first, from the `scripts/` folder of the documentation system's repository: links, slugs, ULIDs, fixity, the phase ledger, phase state, paired change and frontmatter.
`docsys check` runs those a project's `docsys.yaml` turns on, and each rule has a severity the project can change.
A project can also name external tools, such as a Markdown linter, that `docsys check` runs after its checks.
The package also ships a markdownlint rule, `sentence-per-line` (MD100), in `src/docsys/markdownlint/`: a project that keeps one sentence per line names it under `customRules` in its markdownlint configuration, and runs markdownlint as a tool.
`docsys report` lists the documents the scope leaves out, each with the reason of its exclusion, and counts them.

A document is a Markdown file of the workspace that git tracks, or would track once added, and that the scope in `docsys.yaml` governs.
Each check's rules are stated in [`conformance/`](conformance/), as the documents of a small workspace and the findings expected on them, so that any `docsys` package, in any language, can be held to them.
How the engine works inside, and why it is built so, is explained for its maintainer in [`docs/`](docs/), which holds the fiches on the [runner](docs/runner.md), on the ULID check, [referential integrity](docs/referential-integrity.md), and on the [paired-change rule](docs/paired-change.md); the fiches on the other checks are still to write.
A finding reads `path:line: rule: message — fix: the edit that clears it`.

`docsys` exits `0` when every check passes, `1` when a check reports a finding, and `2` when the run cannot happen (usage, configuration, workspace); every `docsys` package, in any language, returns the same.

## Licensing

Each kind of file carries the licence that fits it, mapped per path in [`REUSE.toml`](REUSE.toml), with the texts in [`LICENSES/`](LICENSES/):

- **code** — GPL-3.0-or-later;
- **what a project copies into its own repository** — the schema, the templates, the starting configuration, the conformance suite — CC0-1.0;
- **prose** — CC BY-SA 4.0.

The reasons are in the documentation system's [licensing decision](https://github.com/Skl8em/documentality/blob/main/phases/rush-to-mvp/phase-13-design/licensing.md).
