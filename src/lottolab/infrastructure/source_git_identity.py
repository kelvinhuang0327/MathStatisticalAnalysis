"""Fail-closed Git identity resolution for immutable source-bound artifacts."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from lottolab.application.use_cases.seal_next_draw_recommendation import (
    SealSourceGitIdentityError,
)
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationSealContractError,
    SourceGitIdentity,
)

_GIT_TIMEOUT_SECONDS = 5


class GitSourceIdentityResolver:
    """Resolve stable HEAD/tree only for the clean worktree containing source_path."""

    def __init__(self, source_path: str | Path) -> None:
        if not str(source_path):
            raise ValueError("source_path must be a non-empty filesystem path")
        self._source_path = Path(source_path).absolute()

    def __call__(self) -> SourceGitIdentity:
        git = shutil.which("git")
        if git is None:
            raise SealSourceGitIdentityError(
                "git is required to resolve the executing source worktree identity"
            )

        try:
            source_path = self._source_path.resolve(strict=True)
        except OSError as exc:
            raise SealSourceGitIdentityError(
                "the executing source path cannot be resolved"
            ) from exc
        if not source_path.is_file():
            raise SealSourceGitIdentityError(
                "the executing source path must resolve to a regular file"
            )
        start_directory = source_path.parent

        repository_text = _run_git(git, start_directory, "rev-parse", "--show-toplevel")
        if not repository_text or "\n" in repository_text:
            raise SealSourceGitIdentityError("git returned a non-canonical executing worktree root")
        try:
            repository_root = Path(repository_text).resolve(strict=True)
            relative_source_path = source_path.relative_to(repository_root)
        except (OSError, ValueError) as exc:
            raise SealSourceGitIdentityError(
                "the executing source path is not contained by its resolved Git worktree"
            ) from exc
        _run_git(
            git,
            repository_root,
            "ls-files",
            "--error-unmatch",
            "--",
            relative_source_path.as_posix(),
        )

        _require_clean(repository_root, git)
        identity = _resolve_identity(repository_root, git)
        _require_clean(repository_root, git)
        fresh_identity = _resolve_identity(repository_root, git)
        if fresh_identity != identity:
            raise SealSourceGitIdentityError(
                "Git HEAD/tree changed while source identity was being resolved"
            )
        return identity


def _require_clean(repository_root: Path, git: str) -> None:
    status = _run_git(
        git,
        repository_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise SealSourceGitIdentityError(
            "the executing source worktree must be clean before sealing"
        )


def _resolve_identity(repository_root: Path, git: str) -> SourceGitIdentity:
    source_head = _run_git(git, repository_root, "rev-parse", "--verify", "HEAD^{commit}")
    source_tree = _run_git(git, repository_root, "rev-parse", "--verify", "HEAD^{tree}")
    try:
        return SourceGitIdentity(source_head=source_head, source_tree=source_tree)
    except NextDrawRecommendationSealContractError as exc:
        raise SealSourceGitIdentityError(
            "git returned an invalid or placeholder HEAD/tree identity"
        ) from exc


def _run_git(git: str, repository: Path, *args: str) -> str:
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            [git, "-C", str(repository), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SealSourceGitIdentityError(
            "the executing source worktree Git identity cannot be resolved"
        ) from exc
    if completed.returncode != 0:
        raise SealSourceGitIdentityError(
            "the executing source worktree Git identity cannot be resolved"
        )
    return completed.stdout.strip()


__all__ = ["GitSourceIdentityResolver"]
