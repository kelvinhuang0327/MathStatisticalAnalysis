from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

APPROVED_TAG_TARGETS: dict[str, tuple[str, str]] = {
    "refs/tags/research/provenance/pr-364/4e2fa8a560d6538c2b05b499f99d639e356c6cfa": (
        "4e2fa8a560d6538c2b05b499f99d639e356c6cfa",
        "a452a2a868abce481d3ea02fcfa47ba865981a65",
    ),
    "refs/tags/research/provenance/pr-364/7683a4853929b32506a1343f8659427abb4f1ecc": (
        "7683a4853929b32506a1343f8659427abb4f1ecc",
        "39b1de3977495fdfee7cd64eb8cdeb0f1a2123e0",
    ),
    "refs/tags/research/provenance/pr-364/9c9d309f89b6050e7b4cb49155fc72ff168f7ef8": (
        "9c9d309f89b6050e7b4cb49155fc72ff168f7ef8",
        "3972a602f45062c36d0bac8716a739ca47e95478",
    ),
    "refs/tags/research/provenance/pr-364/eb2e23902c72720722cd7f12343b5f2b476dd6cc": (
        "eb2e23902c72720722cd7f12343b5f2b476dd6cc",
        "ffac7fbe81470cd0a85ffa01d052ca7779278953",
    ),
    "refs/tags/research/provenance/pr-364/f2ad83b4e07571a6842ac301d336360cec805a6a": (
        "f2ad83b4e07571a6842ac301d336360cec805a6a",
        "0b089eb90884f14283679528be40295098a5d3ef",
    ),
}
RESTRICTED_TAG_REF = (
    "refs/tags/research/provenance/pr-364/22747b6ebab1c1ded8773d39edf9e5a44eb70769"
)
_GIT_ENVIRONMENT_KEYS_TO_CLEAR = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


class GitCommandError(RuntimeError):
    pass


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for key in _GIT_ENVIRONMENT_KEYS_TO_CLEAR:
        environment.pop(key, None)
    return environment


def _run_git(args: list[str], *, git_dir: Path | None = None) -> str:
    command = ["git"]
    if git_dir is not None:
        command.extend([f"--git-dir={git_dir}"])
    command.extend(args)
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=_git_environment(),
        )
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", "")
        detail = stderr.strip() or str(error)
        raise GitCommandError(detail) from error
    return result.stdout.strip()


def verify_provenance(
    remote_url: str,
    approved_targets: Mapping[str, tuple[str, str]] = APPROVED_TAG_TARGETS,
    restricted_tag_ref: str = RESTRICTED_TAG_REF,
) -> list[str]:
    refs_to_check = [*approved_targets, restricted_tag_ref]
    try:
        listing = _run_git(["ls-remote", "--refs", remote_url, *refs_to_check])
    except GitCommandError as error:
        return [f"PROVENANCE_REF_LIST_FAILED: {error}"]

    remote_refs: dict[str, str] = {}
    errors: list[str] = []
    for line in listing.splitlines():
        object_id, separator, ref = line.partition("\t")
        if not separator:
            errors.append(f"PROVENANCE_REF_LIST_MALFORMED: {line}")
        elif ref in remote_refs:
            errors.append(f"PROVENANCE_REF_LIST_DUPLICATE: {ref}")
        else:
            remote_refs[ref] = object_id

    if restricted_tag_ref in remote_refs:
        errors.append(
            "UNAUTHORIZED_RESTRICTED_TAG_PUBLISHED: "
            f"{restricted_tag_ref} -> {remote_refs[restricted_tag_ref]}"
        )

    with tempfile.TemporaryDirectory(prefix="b649-approved-provenance-") as temp_dir:
        for index, (tag_ref, (expected_commit, expected_tree)) in enumerate(
            approved_targets.items()
        ):
            remote_object = remote_refs.get(tag_ref)
            if remote_object is None:
                errors.append(f"MISSING_APPROVED_TAG: {tag_ref}")
                continue
            if remote_object != expected_commit:
                errors.append(
                    f"MOVED_APPROVED_TAG: {tag_ref} points to {remote_object}; "
                    f"expected {expected_commit}"
                )

            probe_repo = Path(temp_dir) / f"source-{index}.git"
            try:
                _run_git(["init", "--quiet", "--bare", str(probe_repo)])
                _run_git(
                    ["fetch", "--no-tags", remote_url, tag_ref],
                    git_dir=probe_repo,
                )
                actual_commit = _run_git(
                    ["rev-parse", "--verify", "FETCH_HEAD^{commit}"],
                    git_dir=probe_repo,
                )
                actual_tree = _run_git(
                    ["rev-parse", "--verify", "FETCH_HEAD^{tree}"],
                    git_dir=probe_repo,
                )
            except GitCommandError as error:
                errors.append(f"MISSING_APPROVED_SOURCE: {tag_ref}: {error}")
                continue

            if actual_commit != expected_commit:
                errors.append(
                    f"PROVENANCE_COMMIT_MISMATCH: {tag_ref} resolved to "
                    f"{actual_commit}; expected {expected_commit}"
                )
            if actual_tree != expected_tree:
                errors.append(
                    f"PROVENANCE_TREE_MISMATCH: {tag_ref} has tree {actual_tree}; "
                    f"expected {expected_tree}"
                )

    return errors


def main() -> int:
    try:
        remote_url = _run_git(["remote", "get-url", "origin"])
    except GitCommandError as error:
        print(f"::error::PROVENANCE_ORIGIN_UNAVAILABLE: {error}", file=sys.stderr)
        return 1

    errors = verify_provenance(remote_url)
    if errors:
        for error in errors:
            print(f"::error::{error}", file=sys.stderr)
        return 1

    for tag_ref, (commit, tree) in APPROVED_TAG_TARGETS.items():
        print(f"PASS: {tag_ref} -> {commit} (tree {tree})")
    print(f"PASS: restricted tag absent: {RESTRICTED_TAG_REF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
