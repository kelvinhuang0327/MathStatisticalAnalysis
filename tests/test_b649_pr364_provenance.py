from __future__ import annotations

import subprocess
from pathlib import Path

from tools.verify_b649_pr364_provenance import (
    RESTRICTED_TAG_REF,
    verify_provenance,
)


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _seed_remote(tmp_path: Path) -> tuple[Path, Path, dict[str, tuple[str, str]]]:
    remote = tmp_path / "origin.git"
    source = tmp_path / "source"
    _git(tmp_path, "init", "--quiet", "--bare", str(remote))
    _git(tmp_path, "init", "--quiet", "--initial-branch=main", str(source))
    _git(source, "config", "user.name", "Provenance Test")
    _git(source, "config", "user.email", "provenance-test@example.invalid")

    approved: dict[str, tuple[str, str]] = {}
    for index in range(5):
        (source / "source.txt").write_text(f"approved source {index}\n", encoding="utf-8")
        _git(source, "add", "source.txt")
        _git(source, "commit", "--quiet", "-m", f"approved source {index}")
        commit = _git(source, "rev-parse", "HEAD")
        tree = _git(source, "rev-parse", "HEAD^{tree}")
        tag_ref = f"refs/tags/test/provenance/{index}"
        _git(source, "update-ref", tag_ref, commit)
        approved[tag_ref] = (commit, tree)

    _git(source, "remote", "add", "origin", str(remote))
    _git(source, "push", "--quiet", "--tags", "origin")
    return remote, source, approved


def test_approved_tags_and_trees_pass_when_restricted_tag_is_absent(
    tmp_path: Path,
) -> None:
    remote, _, approved = _seed_remote(tmp_path)

    assert verify_provenance(str(remote), approved) == []


def test_missing_approved_tag_fails(tmp_path: Path) -> None:
    remote, _, approved = _seed_remote(tmp_path)
    missing_ref = next(iter(approved))
    _git(remote, "update-ref", "-d", missing_ref)

    errors = verify_provenance(str(remote), approved)

    assert any(f"MISSING_APPROVED_TAG: {missing_ref}" in error for error in errors)


def test_moved_approved_tag_fails(tmp_path: Path) -> None:
    remote, source, approved = _seed_remote(tmp_path)
    moved_ref = next(iter(approved))
    (source / "source.txt").write_text("replacement source\n", encoding="utf-8")
    _git(source, "add", "source.txt")
    _git(source, "commit", "--quiet", "-m", "moved source")
    moved_commit = _git(source, "rev-parse", "HEAD")
    _git(source, "update-ref", moved_ref, moved_commit)
    _git(source, "push", "--quiet", "--force", "origin", f"{moved_ref}:{moved_ref}")

    errors = verify_provenance(str(remote), approved)

    assert any(f"MOVED_APPROVED_TAG: {moved_ref}" in error for error in errors)


def test_wrong_tree_fails(tmp_path: Path) -> None:
    remote, _, approved = _seed_remote(tmp_path)
    wrong_tree_ref = next(iter(approved))
    commit, _ = approved[wrong_tree_ref]
    wrong_targets = dict(approved)
    wrong_targets[wrong_tree_ref] = (commit, "0" * 40)

    errors = verify_provenance(str(remote), wrong_targets)

    assert any(
        f"PROVENANCE_TREE_MISMATCH: {wrong_tree_ref}" in error for error in errors
    )


def test_restricted_tag_publication_fails(tmp_path: Path) -> None:
    remote, source, approved = _seed_remote(tmp_path)
    approved_commit, _ = next(iter(approved.values()))
    _git(source, "update-ref", RESTRICTED_TAG_REF, approved_commit)
    _git(
        source,
        "push",
        "--quiet",
        "origin",
        f"{RESTRICTED_TAG_REF}:{RESTRICTED_TAG_REF}",
    )

    errors = verify_provenance(str(remote), approved)

    assert any("UNAUTHORIZED_RESTRICTED_TAG_PUBLISHED" in error for error in errors)
