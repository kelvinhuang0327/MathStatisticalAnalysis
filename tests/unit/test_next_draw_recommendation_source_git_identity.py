"""Unit contracts for fail-closed Next-Draw source Git identity resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lottolab.application.use_cases.seal_next_draw_recommendation import (
    SealSourceGitIdentityError,
)
from lottolab.infrastructure.source_git_identity import GitSourceIdentityResolver


def test_resolver_returns_exact_head_and_corresponding_tree_for_clean_worktree(
    tmp_path: Path,
) -> None:
    repository, source_file = _clean_repository(tmp_path)

    identity = GitSourceIdentityResolver(source_file)()

    assert identity.source_head == _git(repository, "rev-parse", "--verify", "HEAD^{commit}")
    assert identity.source_tree == _git(repository, "rev-parse", "--verify", "HEAD^{tree}")


@pytest.mark.parametrize("dirty_kind", ("tracked", "untracked"))
def test_resolver_rejects_dirty_worktree_without_returning_a_placeholder(
    tmp_path: Path, dirty_kind: str
) -> None:
    repository, source_file = _clean_repository(tmp_path)
    if dirty_kind == "tracked":
        source_file.write_text("VALUE = 2\n", encoding="utf-8")
    else:
        (repository / "untracked.py").write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(SealSourceGitIdentityError, match="must be clean"):
        GitSourceIdentityResolver(source_file)()


def test_resolver_rejects_a_non_repository_instead_of_defaulting_identity(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "runtime.py"
    source_file.write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(SealSourceGitIdentityError, match="cannot be resolved"):
        GitSourceIdentityResolver(source_file)()


def test_resolver_rejects_an_ignored_untracked_source_file(tmp_path: Path) -> None:
    repository, _ = _clean_repository(tmp_path)
    (repository / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    _git(repository, "add", ".gitignore")
    _git(repository, "commit", "-q", "-m", "ignore synthetic runtime")
    ignored_source = repository / "ignored.py"
    ignored_source.write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(SealSourceGitIdentityError, match="cannot be resolved"):
        GitSourceIdentityResolver(ignored_source)()


def _clean_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "source-repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.name", "LottoLab Test")
    _git(repository, "config", "user.email", "lottolab@example.test")
    source_file = repository / "runtime.py"
    source_file.write_text("VALUE = 1\n", encoding="utf-8")
    _git(repository, "add", "runtime.py")
    _git(repository, "commit", "-q", "-m", "synthetic source")
    return repository, source_file


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
