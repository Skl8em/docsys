"""`docsys slugify` renames each document that declares a `slug` and is not named
after it to `<slug>.md`, through `rename`, so every link follows. A name the slug
check already accepts (the slug, or the slug and the document's `id` after a hyphen)
is left alone, as is a document without a slug or outside the scope. A slug that
could not name a file is reported, not guessed at, and when two documents would
take one name, or the name is taken, nothing is renamed."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from docsys import exitcodes
from docsys.checks.slugs import check
from docsys.config import Scope, load_config
from docsys.slugify import SlugifyError, slugify
from docsys.workspace import CONFIG_NAME

NO_SCOPE = Scope(include=[], exclude={})


def run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
    return subprocess.run([sys.executable, "-m", "docsys", *args], cwd=cwd, capture_output=True, text=True, env=env)


def write(root: Path, path: str, text: str = "") -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def slugged(slug: str, extra: str = "") -> str:
    return f"---\ntitle: T\nslug: {slug}\n{extra}---\n\nBody.\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q", "-b", "main"], check=True)
    write(tmp_path, CONFIG_NAME, "version: 1\n")
    return tmp_path


def test_a_document_is_renamed_to_its_slug_and_links_follow(repo: Path) -> None:
    write(repo, "notes/draft-one.md", slugged("gerund-naming"))
    write(repo, "index.md", "[n](notes/draft-one.md#top)\n")
    result = slugify(repo, NO_SCOPE)
    assert result.renamed == [("notes/draft-one.md", "notes/gerund-naming.md")]
    assert (repo / "notes/gerund-naming.md").is_file()
    assert (repo / "index.md").read_text(encoding="utf-8") == "[n](notes/gerund-naming.md#top)\n"


def test_the_slug_check_then_reports_nothing(repo: Path) -> None:
    write(repo, "a.md", slugged("alpha"))
    write(repo, "sub/b.md", slugged("beta"))
    slugify(repo, NO_SCOPE)
    assert check(repo, load_config(repo)) == []


def test_a_name_the_slug_check_accepts_is_left_alone(repo: Path) -> None:
    write(repo, "alpha.md", slugged("alpha"))
    write(repo, "beta-01M4FM6C3CASQQB5BRBN7C3BGE.md", slugged("beta", "id: 01M4FM6C3CASQQB5BRBN7C3BGE\n"))
    assert slugify(repo, NO_SCOPE).renamed == []


def test_a_document_without_a_slug_or_outside_the_scope_is_left_alone(repo: Path) -> None:
    write(repo, "plain.md", "---\ntitle: T\n---\n\nBody.\n")
    write(repo, "bare.md", "No frontmatter.\n")
    write(repo, "theory/t.md", slugged("theory-note"))
    scope = Scope(include=[], exclude={"theory/": "not a framework document"})
    assert slugify(repo, scope).renamed == []


def test_a_slug_that_could_not_name_a_file_is_skipped_and_reported(repo: Path) -> None:
    write(repo, "a.md", slugged("Not A Slug"))
    write(repo, "b.md", slugged("fine-one"))
    result = slugify(repo, NO_SCOPE)
    assert result.renamed == [("b.md", "fine-one.md")]
    assert [path for path, _ in result.skipped] == ["a.md"]
    assert "hyphen-cased" in result.skipped[0][1]


def test_a_taken_name_refuses_everything_before_any_rename(repo: Path) -> None:
    write(repo, "a.md", slugged("alpha"))
    write(repo, "alpha.md", "---\ntitle: other\n---\n")
    write(repo, "z.md", slugged("zeta"))
    with pytest.raises(SlugifyError, match=r"alpha\.md"):
        slugify(repo, NO_SCOPE)
    assert (repo / "z.md").exists()
    assert (repo / "a.md").exists()


def test_two_documents_taking_one_name_refuse_everything(repo: Path) -> None:
    write(repo, "a/x.md", slugged("same"))
    write(repo, "a/y.md", slugged("same"))
    with pytest.raises(SlugifyError, match=r"same\.md"):
        slugify(repo, NO_SCOPE)
    assert (repo / "a/x.md").exists()


def test_dry_run_changes_nothing(repo: Path) -> None:
    write(repo, "a.md", slugged("alpha"))
    result = slugify(repo, NO_SCOPE, dry_run=True)
    assert result.renamed == [("a.md", "alpha.md")]
    assert (repo / "a.md").exists()


def test_a_sealed_record_whose_links_changed_is_reported(repo: Path) -> None:
    write(repo, "a.md", slugged("alpha"))
    write(repo, "rec.md", "---\ntitle: R\nhash: sha256:abc\n---\n\n[a](a.md)\n")
    assert slugify(repo, NO_SCOPE).stale_seals == ["rec.md"]


def test_the_command_renames_and_reports(repo: Path) -> None:
    write(repo, "a.md", slugged("alpha"))
    result = run_cli("slugify", cwd=repo)
    assert result.returncode == exitcodes.OK, result.stderr
    assert "a.md -> alpha.md" in result.stdout
    assert "1 document renamed" in result.stdout


def test_the_command_says_when_there_is_nothing_to_do(repo: Path) -> None:
    write(repo, "alpha.md", slugged("alpha"))
    result = run_cli("slugify", cwd=repo)
    assert result.returncode == exitcodes.OK
    assert "nothing to do" in result.stdout


def test_the_command_dry_run_marks_its_lines_and_changes_nothing(repo: Path) -> None:
    write(repo, "a.md", slugged("alpha"))
    result = run_cli("slugify", "--dry-run", cwd=repo)
    assert result.stdout.startswith("[dry-run] a.md -> alpha.md")
    assert (repo / "a.md").exists()


def test_the_command_fails_with_findings_when_a_slug_was_skipped(repo: Path) -> None:
    write(repo, "a.md", slugged("Not A Slug"))
    result = run_cli("slugify", cwd=repo)
    assert result.returncode == exitcodes.FINDINGS
    assert "a.md" in result.stdout


def test_the_command_refuses_a_taken_name_with_the_error_exit_code(repo: Path) -> None:
    write(repo, "a.md", slugged("alpha"))
    write(repo, "alpha.md")
    result = run_cli("slugify", cwd=repo)
    assert result.returncode == exitcodes.ERROR
    assert "alpha.md" in result.stderr
