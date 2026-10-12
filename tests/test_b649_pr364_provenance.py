from __future__ import annotations

import subprocess
from pathlib import Path

from tools.verify_b649_pr364_provenance import (
    RESTRICTED_TAG_REF,
    fetch_exact_commit,
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


def test_exact_commit_fetch_is_sha_bound_and_does_not_create_a_ref(
    tmp_path: Path,
) -> None:
    remote, source, approved = _seed_remote(tmp_path)
    (source / "historical.txt").write_text("unadvertised history\n", encoding="utf-8")
    _git(source, "add", "historical.txt")
    _git(source, "commit", "--quiet", "-m", "unadvertised historical commit")
    historical_commit = _git(source, "rev-parse", "HEAD")
    historical_tree = _git(source, "rev-parse", "HEAD^{tree}")
    _git(
        source,
        "push",
        "--quiet",
        "origin",
        f"HEAD:refs/hidden/{historical_commit}",
    )
    _git(remote, "config", "uploadpack.hideRefs", "refs/hidden")
    _git(remote, "config", "uploadpack.allowAnySHA1InWant", "true")

    checkout = tmp_path / "checkout.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(checkout))
    approved_ref, (unrelated_head, unrelated_tree) = next(iter(approved.items()))
    _git(
        tmp_path,
        f"--git-dir={checkout}",
        "fetch",
        "--no-tags",
        str(remote),
        f"{approved_ref}:{approved_ref}",
    )
    _git(tmp_path, f"--git-dir={checkout}", "update-ref", "refs/heads/main", unrelated_head)
    _git(tmp_path, f"--git-dir={checkout}", "symbolic-ref", "HEAD", "refs/heads/main")

    unavailable_before = subprocess.run(
        [
            "git",
            f"--git-dir={checkout}",
            "rev-parse",
            "--verify",
            f"{historical_commit}^{{commit}}",
        ],
        capture_output=True,
        text=True,
    )
    assert unavailable_before.returncode != 0
    assert historical_commit not in _git(tmp_path, "ls-remote", "--refs", str(remote))

    errors = fetch_exact_commit(
        str(remote), historical_commit, historical_tree, git_dir=checkout
    )

    assert errors == []
    assert (
        _git(
            tmp_path,
            f"--git-dir={checkout}",
            "rev-parse",
            "--verify",
            "FETCH_HEAD^{commit}",
        )
        == historical_commit
    )
    assert (
        _git(
            tmp_path,
            f"--git-dir={checkout}",
            "rev-parse",
            "--verify",
            "FETCH_HEAD^{tree}",
        )
        == historical_tree
    )
    assert historical_commit not in _git(
        tmp_path, f"--git-dir={checkout}", "show-ref", "--heads", "--tags"
    )

    wrong_tree = fetch_exact_commit(
        str(remote), historical_commit, "0" * 40, git_dir=checkout
    )
    assert any("HISTORICAL_TREE_MISMATCH" in error for error in wrong_tree)

    wrong_commit = fetch_exact_commit(str(remote), "0" * 40, historical_tree, git_dir=checkout)
    assert any("HISTORICAL_OBJECT_FETCH_FAILED" in error for error in wrong_commit)

    missing_remote = tmp_path / "missing.git"
    _git(tmp_path, "init", "--quiet", "--bare", str(missing_remote))
    missing = fetch_exact_commit(
        str(missing_remote), historical_commit, historical_tree, git_dir=checkout
    )
    assert any("HISTORICAL_OBJECT_FETCH_FAILED" in error for error in missing)

    local_head_fallback = fetch_exact_commit(
        str(missing_remote), unrelated_head, unrelated_tree, git_dir=checkout
    )
    assert any(
        "HISTORICAL_OBJECT_FETCH_FAILED" in error for error in local_head_fallback
    )
