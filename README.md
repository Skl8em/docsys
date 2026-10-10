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
It is not installable yet: its code is being extracted from the `scripts/` folder of the documentation system's repository.

## Licensing

Each kind of file carries the licence that fits it, mapped per path in [`REUSE.toml`](REUSE.toml), with the texts in [`LICENSES/`](LICENSES/):

- **code** — GPL-3.0-or-later;
- **what a project copies into its own repository** — the schema, the templates, the starting configuration, the conformance suite — CC0-1.0;
- **prose** — CC BY-SA 4.0.

The reasons are in the documentation system's [licensing decision](https://github.com/Skl8em/documentality/blob/main/phases/rush-to-mvp/phase-13-design/licensing.md).
