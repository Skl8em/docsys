#!/usr/bin/env python3
"""Migration tool (ADR-028): rename count-named records to <slug>-<ulid>.

This is the ULID-in-filename direction of the open naming convention (slug first,
per the maintainer's preference). The default convention is `<slug>.md` with the
ULID in frontmatter (see scripts/slugify_names.py); this tool is kept available for
when global uniqueness in the filename is wanted. It is not part of the gate.


- ADRs (ADR-NNN-slug.md): chronological ULID from the record's first-commit time,
  with the ADR number as a sub-second tiebreak so same-commit ADRs keep their order.
- Phases (phase-NN-slug/): ordinal ULID from `order = NN * 1_000_000` (gap-spaced),
  written into the phase README together with `id`/`slug`.

Adds `id`/`slug` (and, for phases, `order`) to frontmatter, then renames via the
safe-rename core so every link is rewritten. Runs the full gate at the end.

    python3 scripts/migrate_ids.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ulid import new_ulid          # noqa: E402
from rename_doc import rename_path  # noqa: E402

ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
os.chdir(ROOT)

PHASE_GAP = 1_000_000


def first_commit_ms(path):
    out = subprocess.check_output(
        ["git", "log", "--follow", "--diff-filter=A", "--format=%at", "--", path],
        text=True,
    ).split()
    return int(out[-1]) * 1000 if out else 0  # oldest add commit


def fm_bounds(lines):
    if not lines or lines[0].strip() != "---":
        raise SystemExit("no frontmatter block")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    return end


def add_frontmatter(path, fields):
    lines = open(path, encoding="utf-8").read().split("\n")
    end = fm_bounds(lines)
    block = lines[1:end]
    if any(re.match(r"\s*id:", ln) for ln in block):
        return  # already migrated
    # insert after the title line if present, else at the top of the block
    at = 1
    for i in range(1, end):
        if lines[i].startswith("title:"):
            at = i + 1
            break
    lines[at:at] = [f"{k}: {v}" for k, v in fields.items()]
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def migrate_adrs():
    adrs = [f for f in subprocess.check_output(["git", "ls-files", "phases"], text=True).splitlines()
            if re.match(r"ADR-\d+-.*\.md$", os.path.basename(f))]
    renames = []
    for path in adrs:
        base = os.path.basename(path)
        num = int(re.match(r"ADR-(\d+)-", base).group(1))
        slug = re.sub(r"^ADR-\d+-", "", base[:-3])
        ulid = new_ulid(ts_ms=first_commit_ms(path) + (num % 1000))
        add_frontmatter(path, {"id": ulid, "slug": slug})
        new = os.path.join(os.path.dirname(path), f"{slug}-{ulid}.md")
        renames.append((path, new, num))
    for old, new, _ in sorted(renames, key=lambda r: r[2]):
        rename_path(old, new)
    return len(renames)


def migrate_phases():
    dirs = sorted({os.path.dirname(f) for f in subprocess.check_output(["git", "ls-files", "phases"], text=True).splitlines()
                   if re.match(r"phase-\d+-", os.path.basename(os.path.dirname(f)))})
    count = 0
    for d in dirs:
        base = os.path.basename(d)
        m = re.match(r"phase-(\d+)-(.+)$", base)
        num, slug = int(m.group(1)), m.group(2)
        order = num * PHASE_GAP
        ulid = new_ulid(order=order)
        readme = os.path.join(d, "README.md")
        if os.path.exists(readme):
            add_frontmatter(readme, {"id": ulid, "slug": slug, "order": order})
        new = os.path.join(os.path.dirname(d), f"{slug}-{ulid}")
        rename_path(d, new)
        count += 1
    return count


def main():
    n_adr = migrate_adrs()      # files first (inside their phase folders)
    n_phase = migrate_phases()  # then the folders carry the renamed files
    print(f"\nmigrated {n_adr} ADRs and {n_phase} phase folders")
    print("=== running the gate ===")
    return subprocess.call([sys.executable, os.path.join(HERE, "check.py")])


if __name__ == "__main__":
    sys.exit(main())
