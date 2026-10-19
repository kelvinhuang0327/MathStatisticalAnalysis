"""Prepare a task-owned standalone temp checkout and bind authentic sealed evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HEAD = "e440d4298551ce93ef3ea9a9226143784afa3eff"
TREE = "294cbf6bbe7ee8a8ebad947f397852edc1981b57"
TEST = "tests/unit/test_b649_min_s2_advanced_11row_exact_adoption_r1.py"
TEST_SHA = "5f1198daf582db4340c2bf424071375a442e8ca9e54fd8d27e4d10d03ef9f067"
REPORT = ".git/worktrees/B649_MIN_S2_AB_T242_T241_EXACT_FAMILY_AUTHORITY_R1/task-evidence/fresh-judge-report.md"
REPORT_SHA = "216340c3d1cd2b7724571d95e4c7951d731fd48d04996dd10d53e83b98e12a3b"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    runtime = args.runtime.resolve(strict=True)
    source = args.source.resolve(strict=True)
    assert runtime.is_relative_to(Path("/private/tmp")) and "b649" not in str(runtime).casefold()
    assert git(source, "rev-parse", "HEAD") == HEAD
    assert git(source, "rev-parse", "HEAD^{tree}") == TREE
    assert hashlib.sha256((source / TEST).read_bytes()).hexdigest() == TEST_SHA
    target = runtime / "testrepo"
    if not target.exists():
        target.mkdir(mode=0o700)
        subprocess.run(["git", "init", "--quiet", str(target)], check=True)
        objects = Path(git(source, "rev-parse", "--path-format=absolute", "--git-path", "objects"))
        # Full independent object copy: no alternates, hard links, refs or source writes.
        shutil.copytree(objects, target / ".git/objects", dirs_exist_ok=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--quiet", "--detach", HEAD], check=True)
    assert git(target, "rev-parse", "HEAD") == HEAD
    assert git(target, "rev-parse", "HEAD^{tree}") == TREE
    assert hashlib.sha256((target / TEST).read_bytes()).hexdigest() == TEST_SHA
    assert not (target / ".git/objects/info/alternates").exists()
    assert git(target, "remote") == ""
    assert git(target, "rev-parse", "--is-shallow-repository") == "false"
    if args.report:
        raw = args.report.resolve(strict=True).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == REPORT_SHA
        assert raw.decode().splitlines()[0] == "VERIFIED_WITH_CAVEATS"
        assert "JUDGED_TREE: 8c2719af507006a74fd0f5f205d9fbb24c528994" in raw.decode()
        destination = target / REPORT
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if destination.exists():
            assert destination.read_bytes() == raw
        else:
            destination.write_bytes(raw)
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == REPORT_SHA
    print(json.dumps({"repository": str(target), "head": HEAD, "tree": TREE,
                      "report_present": (target / REPORT).is_file(),
                      "report_sha256": hashlib.sha256((target / REPORT).read_bytes()).hexdigest()
                      if (target / REPORT).is_file() else None}, sort_keys=True))


if __name__ == "__main__":
    main()
