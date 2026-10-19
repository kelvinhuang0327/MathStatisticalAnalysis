"""Run exactly the authorized smoke pair under one inherited strict sandbox."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from write_observer import install

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "config.json")
C = json.loads(CONFIG.read_text())
TAG = C.get("run_tag", "")
PROFILE = ROOT / C.get("sandbox_profile", "smoke.sb")
EXTERNAL = Path(C["external_root"])
ISOLATED = Path(C["isolated_repo"])
emit = install("strict-harness", ROOT / "config.json", denial_probe=True)
os.umask(0o077)
ENV = {"PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(EXTERNAL / "home"),
       "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "GIT_OPTIONAL_LOCKS": "0",
       "GIT_NO_LAZY_FETCH": "1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_TRACE2_EVENT": str(ROOT / ("git-strict-harness" + TAG + ".jsonl"))}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    path = ROOT / name
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    emit("receipt-committed", path=str(path), sha256=sha(path))


def command(argv, *, environment=None, expected=0):
    started = time.time_ns()
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=EXTERNAL, env=environment or ENV)
    emit("spawn-started", child_pid=process.pid, argv=argv, cwd=str(EXTERNAL))
    stdout, stderr = process.communicate()
    result = {"argv": argv, "pid": process.pid, "ppid": os.getpid(), "exit_status": process.returncode,
              "started_ns": started, "ended_ns": time.time_ns(), "stdout": stdout.decode(), "stderr": stderr.decode()}
    emit("spawn-completed", child_pid=process.pid, exit_status=process.returncode)
    if process.returncode != expected:
        save("strict-failed-command-" + str(process.pid) + ".json", result)
        raise RuntimeError("controlled command failed: " + repr(argv) + ": " + result["stderr"])
    return result


def git(repo, *args):
    return command(["/usr/bin/git", "--no-optional-locks", "-C", str(repo), *args])["stdout"]


def manifest(directory):
    result = {}
    for path in sorted(directory.rglob("*")):
        stat = path.lstat()
        item = {"mode": stat.st_mode & 0o777, "mtime_ns": stat.st_mtime_ns}
        if path.is_symlink():
            item.update(type="symlink", target=os.readlink(path))
        elif path.is_file():
            item.update(type="file", bytes=stat.st_size, sha256=sha(path))
        elif path.is_dir():
            item.update(type="directory")
        else:
            item.update(type="other")
        result[str(path.relative_to(directory))] = item
    return result


def isolated_snapshot():
    return {"head": git(ISOLATED, "rev-parse", "HEAD").strip(),
            "tree": git(ISOLATED, "rev-parse", "HEAD^{tree}").strip(),
            "parent": git(ISOLATED, "rev-parse", "HEAD^").strip(),
            "refs": git(ISOLATED, "for-each-ref", "--sort=refname", "--format=%(refname) %(objectname) %(symref)"),
            "status": git(ISOLATED, "status", "--porcelain=v1", "--untracked-files=all"),
            "shallow": git(ISOLATED, "rev-parse", "--is-shallow-repository").strip(),
            "common_dir": git(ISOLATED, "rev-parse", "--path-format=absolute", "--git-common-dir").strip(),
            "alternates_exists": (ISOLATED / ".git/objects/info/alternates").exists(),
            "remotes": git(ISOLATED, "remote"), "filesystem_manifest": manifest(ISOLATED)}


def host_snapshot():
    result = {}
    for name in ("source", "primary"):
        repo = Path(C[name])
        result[name] = {"head_tree_parent": git(repo, "rev-parse", "HEAD", "HEAD^{tree}", "HEAD^"),
                        "refs": git(repo, "for-each-ref", "--sort=refname", "--format=%(refname) %(objectname) %(symref)"),
                        "status": git(repo, "status", "--porcelain=v1", "--untracked-files=all")}
    result["judge_sha256"] = sha(C["judge"])
    return result


try:
    assert not (ROOT / ("execution-result" + TAG + ".json")).exists(), "smoke pair already completed; no duplicate execution"
    baseline = json.loads((ROOT / "isolated-before.json").read_text())
    before = isolated_snapshot()
    assert before == baseline, "prepared source/Git changed before smoke; no takeover"
    save("strict" + TAG + "-isolated-before.json", before)
    host_before = host_snapshot()
    save("strict" + TAG + "-host-before.json", host_before)
    results = []
    for execution_id, expected_exit in zip(C["execution_ids"], (0, 23)):
        run_dir = Path(C["original_root"]) / "runs" / execution_id
        assert not run_dir.exists(), "existing smoke state must not be rerun"
        env = dict(ENV, GIT_TRACE2_EVENT=str(ROOT / ("git-" + execution_id + ".jsonl")))
        # The harness already entered smoke.sb at process startup. Children
        # inherit that kernel policy; macOS does not allow nested sandbox_apply.
        argv = ["/usr/bin/ruby", "-r", str(ROOT / "ruby_observer.rb"), C["launcher"],
                "--execution-id", execution_id, "--kind", "smoke", "--python", C["python"],
                "--source-worktree", str(ISOLATED), "--expected-head", C["expected_head"],
                "--expected-tree", C["expected_tree"], "--", C["smoke"], str(expected_exit)]
        result = command(argv, environment=env, expected=expected_exit)
        result.update(execution_id=execution_id, expected_exit=expected_exit, sandbox_profile_sha256=sha(PROFILE),
                      launcher_sha256=sha(C["launcher"]), ruby_observer_sha256=sha(ROOT / "ruby_observer.rb"),
                      python_observer_sha256=sha(ROOT / "write_observer.py"), run_dir=str(run_dir),
                      child_observation=json.loads(result["stdout"]))
        capture = json.loads((run_dir / "capture.json").read_text())
        assert capture["exit_status"] == expected_exit
        assert capture["stdout"] == result["stdout"] and capture["stderr"] == result["stderr"]
        assert result["stderr"] == ("normal-smoke-stderr\n" if expected_exit == 0 else "negative-smoke-stderr\n")
        assert result["child_observation"]["launch_receipt_exists_before_child"]
        assert result["child_observation"]["observed_appdata"].startswith(str(EXTERNAL / "runtime") + "/")
        save(execution_id + "-dispatch.json", result)
        results.append(result)
    after = isolated_snapshot()
    save("strict" + TAG + "-isolated-after.json", after)
    assert before == after, "isolated product/Git metadata changed during smoke pair"
    host_after = host_snapshot()
    save("strict" + TAG + "-host-after.json", host_after)
    assert host_before["source"]["head_tree_parent"] == host_after["source"]["head_tree_parent"]
    assert host_after["source"]["status"] == ""
    assert sha(C["judge"]) == C["judge_sha256"]
    old_changed = [path for path, expected in C["old_files"].items()
                   if not Path(path).is_file() or sha(path) != expected["sha256"] or oct(Path(path).stat().st_mode & 0o777) != expected["mode"]]
    assert not old_changed, old_changed
    save("execution-result" + TAG + ".json", {"status": "SMOKE_PAIR_COMPLETED", "normal_exit": 0, "negative_exit": 23,
         "isolated_before_after_identical": True, "old_files_checked": len(C["old_files"]), "old_files_changed": old_changed,
         "old_judge_sha256": sha(C["judge"]), "launcher_sha256": sha(C["launcher"]), "harness_pid": os.getpid(),
         "harness_ppid": os.getppid(), "smoke_sandbox_profile_sha256": sha(PROFILE),
         "runs": results, "full_suite_runs": 0, "solver_runs": 0})
    print(json.dumps({"status": "SMOKE_PAIR_COMPLETED", "normal_exit": 0, "negative_exit": 23,
                      "isolated_source_unchanged": True, "old_files_unchanged": True}), flush=True)
except BaseException as error:
    save("strict-execution-failed-" + str(os.getpid()) + ".json",
         {"error_type": type(error).__name__, "error": str(error), "pid": os.getpid(), "time_ns": time.time_ns()})
    raise
