---
title: "The link check — why a dead link can be allowed, and why the allowance can go stale"
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

**Read this before** changing what the link check reads, how a link's target is compared, or the `links` section of `docsys.yaml`.
It is written for the maintainer of `docsys`, initiated in tooling engineering.

## What is checked

The link check, [`src/docsys/checks/links.py`](../src/docsys/checks/links.py), reads every document in the scope, finds each `[text](target)` on its lines, and reports a relative target that points to no file or folder (`links/resolve`).
The target is read from the document's own folder, after a link title and an anchor are dropped; it resolves when a file or a folder exists there, whether it is a document or not and whether the scope covers it or not.
Four kinds of target are not resolved: `http://`, `https://` and `mailto:` targets, a same-document anchor, and a fill-in placeholder (`<path>`, or a target holding `…`), which a template shows where its reader writes a path.
The check does not read the web, and it does not check that an anchor names a heading of its target.

## Why a dead link can be allowed

A frozen record is sealed ([ADR-031](https://github.com/Skl8em/documentality/blob/main/phases/refoundation/phase-10-schema/content-hash-fixity.md)): editing it to repair a link changes its seal, and the repair would rewrite what the record said when it was decided.
When the file a frozen record links to is retired, the link is dead for good and the record is right to keep it.
Without an allowance the project had two bad choices: edit the record, or switch `links/resolve` off for every document, which also hides the links that matter.
`links.allow` is the third: the one link, in the one document, accepted with its reason.

```yaml
links:
  allow:
    - document: phases/refoundation/phase-09-tooling/plan.md
      target: ../../../scripts/linkcheck.py
      reason: retired with scripts/ when the gate moved to docsys; the record is frozen
```

An allowance is exact on purpose.
It names a document and a target *as written* (anchor included, title dropped), not a pattern: a glob would allow links nobody has looked at, and the list is short because each entry was a decision.
`../x.md` and `../x.md#part` are two targets; an allowance for one does not cover the other.
It covers every line of the document that holds the link.

## Why an allowance carries a reason

The reason is what a later reader needs to decide whether the entry still holds.
An entry without one is refused when the configuration is read (`docsys.yaml: links.allow[0].reason`), as an exclusion from the scope is: a list of silenced findings with no account of why is a list nobody can safely shorten.

## Why a stale allowance is reported

An allowance whose link resolves, or whose document no longer holds that link, allows nothing: the dead link it excused has been repaired, moved or deleted (`links/allowance`).
Left in place it would excuse the next dead link that happens to take the same target in the same document, which is a different decision nobody made.
So the check reports it, on `docsys.yaml` at the line where the entry starts, with the edit that clears it: remove the entry.
It is the same device as `lagging:` in the phase ledger, an allowance that must go when its reason does.

A document the scope leaves out is not read, so an allowance for one is reported as well: the allowance would be dead weight, and the exclusion already carries its own reason.

## What the check does not establish

It does not establish that a link's reason is true, only that one was written.
It does not allow a class of links, and it does not look at web links, so a link into another repository is neither checked nor needs an allowance.

## Where a maintainer touches this

- **A change to what counts as a link or a target** is made in `check` and stated first as cases in [`conformance/links.yaml`](../conformance/links.yaml); an allowance compares against the same target string the message names.
- **A new key of an allowance** is a change to `Allowance` and `_links` in [`config.py`](../src/docsys/config.py), to the refusals in [`tests/test_config.py`](../tests/test_config.py) and to the project-facing reference of `docsys.yaml`.
- **The line of a stale allowance** is read from `docsys.yaml` again by `load_located`, since the configuration reader does not keep lines; the check reads the file only when an allowance is stale.
