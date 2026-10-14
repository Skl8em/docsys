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
Its checks were extracted, one at a time and test first, from the `scripts/` folder of the documentation system's repository: links, slugs, ULIDs, fixity, the phase ledger, phase state, paired change and frontmatter. `docsys check` runs none of them until the runner is written.

A document is a Markdown file of the workspace that git tracks, or would track once added, and that the scope in `docsys.yaml` governs.
Each check's rules are stated in [`conformance/`](conformance/), as the documents of a small workspace and the findings expected on them, so that any `docsys` package, in any language, can be held to them.
A finding reads `path:line: rule: message — fix: the edit that clears it`.

`docsys` exits `0` when every check passes, `1` when a check reports a finding, and `2` when the run cannot happen (usage, configuration, workspace); every `docsys` package, in any language, returns the same.

## Licensing

Each kind of file carries the licence that fits it, mapped per path in [`REUSE.toml`](REUSE.toml), with the texts in [`LICENSES/`](LICENSES/):

- **code** — GPL-3.0-or-later;
- **what a project copies into its own repository** — the schema, the templates, the starting configuration, the conformance suite — CC0-1.0;
- **prose** — CC BY-SA 4.0.

The reasons are in the documentation system's [licensing decision](https://github.com/Skl8em/documentality/blob/main/phases/rush-to-mvp/phase-13-design/licensing.md).
