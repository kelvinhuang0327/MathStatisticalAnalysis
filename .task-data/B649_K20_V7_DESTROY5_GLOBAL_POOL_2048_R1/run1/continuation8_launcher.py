"""Owner-authorized atomic gate; unchanged Destroy5 scientific driver and logical run1."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


DRIVER_SHA256 = "d1a554378d7d468c71aa288f9699588bbd734de4c3f87430a705359a669ed30f"
PRIOR_ARGV_SHA256 = "43cfb877da8bc93f570634335a051b9e39c1f5f9bd0cc37ccc0294c048c1b37b"
VERIFICATION_SHA256 = "8e4ae28cf94678d21ffa3778092556b4aa1a0d6e827cceef2bb44678c21208f2"
EXECUTION_AUTHORITY_SOURCE_SHA256 = {
    "src/lottolab/research/b649_k20_destroy5_result_semantics.py": "653a4f091ca4531d3750f420739e2f03d98fe6be7bf0a7c35bda281a10d41a22",
    "src/lottolab/research/b649_k20_destroy5_execution_authority.py": "a5b928bd8452777583fe40b716e827908b614a4c1d0cfad4f2101a3b4b716a2d",
}
PROTECTED_EXECUTION_ID = "run8"
CONTINUATION = 8
LAUNCHER = Path("/Users/kelvin/VibeCoding-WorkSpace/skill-launcher/fable-method/scripts/task_checkpoint.rb")
PACKET = "/Users/kelvin/.codex/worktrees/b649-k20-v7-destroy5-global-pool-2048-r1/MathStatisticalAnalysis/.task-data/B649_K20_V7_DESTROY5_GLOBAL_POOL_2048_R1/run1/owner-continuation8-packet.txt"


class LaunchStop(RuntimeError):
    pass


def bind_execution_authority(
    driver,
    repo,
    run,
    *,
    incumbent_resolver=None,
    _test_only_allow_synthetic_run_root=False,
):
    actual_hashes = {}
    for relative, expected in EXECUTION_AUTHORITY_SOURCE_SHA256.items():
        path = repo / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"required execution-authority source is unavailable: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"execution-authority source identity mismatch: {relative}")
        actual_hashes[relative] = actual

    wrapper_path = repo / "src/lottolab/research/b649_k20_destroy5_execution_authority.py"
    module_name = "_b649_k20_destroy5_2048_execution_authority"
    spec = importlib.util.spec_from_file_location(module_name, wrapper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("2048 Destroy5 execution-authority wrapper cannot be loaded")
    wrapper = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = wrapper
    spec.loader.exec_module(wrapper)
    if Path(wrapper.__file__).resolve() != wrapper_path.resolve():
        raise RuntimeError("execution-authority import escaped the repository source")
    binding = wrapper.bind_driver(
        driver,
        repo,
        run,
        incumbent_resolver=incumbent_resolver,
        _test_only_allow_synthetic_run_root=_test_only_allow_synthetic_run_root,
    )
    return binding, actual_hashes


def blocking_writers_once():
    output = subprocess.check_output(
        ["/bin/ps", "-ww", "-axo", "pid=,ppid=,%cpu=,%mem=,state=,command="], text=True
    )
    rows = []
    for line in output.splitlines():
        parts = line.strip().split(None, 5)
        if len(parts) != 6:
            raise RuntimeError("unparseable process snapshot; no launch")
        pid, parent, cpu, memory, state, command = parts
        rows.append((int(pid), int(parent), float(cpu), float(memory), state, command))
    parents = {row[0]: row[1] for row in rows}
    ancestors = set()
    current = os.getpid()
    while current and current not in ancestors:
        ancestors.add(current)
        current = parents.get(current, 0)
    writers = []
    for pid, _, cpu, memory, state, command in rows:
        if pid in ancestors or state.startswith("Z"):
            continue
        try:
            argv = shlex.split(command)
        except ValueError:
            argv = command.split()
        if not argv:
            continue
        executable = Path(argv[0]).name.lower()
        scientific = (
            "/.task-data/" in command
            or any("b649_k" in arg.lower() or "b649-k" in arg.lower() for arg in argv)
            or any(Path(arg).name in {"tbr_engine", "ldr_engine", "exact_score.py"} for arg in argv)
            or "lottolab.research" in command
        )
        computational = (
            "python" in executable
            or executable in {"tbr_engine", "ldr_engine"}
            or (scientific and cpu >= 5.0 and executable not in {"ruby", "zsh", "bash", "sh", "ps", "tail", "cat"})
        )
        if scientific and computational:
            evidence = {"PID": pid, "COMMAND": command, "CPU_PERCENT": cpu, "MEMORY_PERCENT": memory}
            for arg in argv:
                if arg.startswith("/") and "/.task-data/" in arg:
                    worktree, suffix = arg.split("/.task-data/", 1)
                    task_id = suffix.split("/", 1)[0]
                    if re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
                        evidence["TASK_ID"] = task_id
                        evidence["WORKTREE"] = worktree
                        break
            writers.append(evidence)
    return writers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    repo, run = args.repo_root.resolve(), args.run_root.resolve()
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest(run / "driver.py") == DRIVER_SHA256
    assert digest(run / "execution-argv-continuation7.json") == PRIOR_ARGV_SHA256
    assert digest(run / "prelaunch-verification.json") == VERIFICATION_SHA256
    prior = json.loads((run / "execution-argv-continuation7.json").read_text())
    assert digest(LAUNCHER) == prior["LAUNCHER_SHA256"]
    spec = importlib.util.spec_from_file_location("verified_destroy5_driver", run / "driver.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    assert run == repo / ".task-data" / driver.TASK_ID / driver.EXECUTION_ID
    assert driver.git_output(repo, "rev-parse", "--show-toplevel") == str(repo)
    for name in ("state.json", "set-results.jsonl", "canonical-recounts.jsonl", "execution-argv-continuation8.json", "owner-continuation8-launch-check.json", "owner-continuation8-stop-result.json", "owner-continuation8-phase0.json"):
        assert not (run / name).exists(), f"preexisting state: {name}"
    verification = json.loads((run / "prelaunch-verification.json").read_text())
    source_hashes = {"driver.py": DRIVER_SHA256, **verification["SOURCE_SHA256"]}
    source_hashes.update({"engine/src/" + relative: value for relative, value in driver.REUSE_FILES.items()})
    assert all(digest(run / name) == value for name, value in source_hashes.items())
    execution_authority_binding, execution_authority_source_hashes = bind_execution_authority(driver, repo, run)
    start = json.loads((run / "start.json").read_text())
    manifest = json.loads((run / "destroy-sets-frozen.json").read_text())
    assert start["START_COUNT"] == driver.START_COUNT and start["START_SHA256"] == driver.START_SHA256
    assert digest(repo / start["START_SOURCE_FILE"]) == start["START_SOURCE_FILE_SHA256"]
    assert manifest["START_PORTFOLIO"] == start["START_PORTFOLIO"] and manifest["START_SHA256"] == driver.START_SHA256
    assert manifest["MANIFEST_SHA256"] == driver.FROZEN_MANIFEST_DIGEST
    assert manifest["SAMPLE_COUNT"] == 2048 and manifest["SEED"] == 20261007 and manifest["DESTROY_SIZE"] == 5
    assert verification["STATUS"] == "PASS" and verification["MISMATCHES"] == 0
    phase0 = {
        "PHASE0_STATUS": "PASS_IDENTITIES_UNCHANGED", "TASK_ID": driver.TASK_ID,
        "AUTHORITATIVE_PACKET_REF": PACKET, "WORKTREE": str(repo), "RUN_ROOT": str(run),
        "HEAD": driver.git_output(repo, "rev-parse", "HEAD"),
        "TREE": driver.git_output(repo, "rev-parse", "HEAD^{tree}"),
        "SOURCE_SHA256": source_hashes, "PRELAUNCH_VERIFICATION_SHA256": VERIFICATION_SHA256,
        "EXECUTION_AUTHORITY_SOURCE_SHA256": execution_authority_source_hashes,
        "START_COUNT": driver.START_COUNT, "START_SHA256": driver.START_SHA256,
        "TASK_SCOPED_RUFF": "PASS_REUSED", "PYRIGHT": "PASS_REUSED", "EXACTNESS": "PASS_REUSED",
        "PARITY_MISMATCHES": 0, "CORRECTNESS_CHECKS_RERUN": False, "PROJECT_MEMORY_WRITTEN": "NO",
    }
    upstream = [prior["UPSTREAM_ARGV"][0], "-u", str(Path(__file__).resolve()), "--repo-root", str(repo), "--run-root", str(run)]
    protected = ["/usr/bin/ruby", str(LAUNCHER), "--run", "--repo", str(repo), "--worktree", str(repo), "--task-id", driver.TASK_ID, "--execution-id", PROTECTED_EXECUTION_ID, "--", *upstream]
    execution = {
        "TASK_ID": driver.TASK_ID, "EXECUTION_ID": driver.EXECUTION_ID,
        "PROTECTED_EXECUTION_ID": PROTECTED_EXECUTION_ID, "CONTINUATION": CONTINUATION,
        "UPSTREAM_ARGV": upstream, "UPSTREAM_ARGV_SHA256": driver.sha256_bytes(driver.canonical_json(upstream)),
        "PROTECTED_ARGV": protected, "PROTECTED_ARGV_SHA256": driver.sha256_bytes(driver.canonical_json(protected)),
        "ARGV_HASH_DEFINITION": "SHA256 of sorted-key compact JSON array plus newline",
        "FROZEN_PREVIOUS_UPSTREAM_ARGV": prior["UPSTREAM_ARGV"],
        "FROZEN_PREVIOUS_UPSTREAM_ARGV_SHA256": prior["UPSTREAM_ARGV_SHA256"],
        "FROZEN_SCIENTIFIC_ENTRYPOINT": "driver.run_campaign(repo, run)",
        "SCIENTIFIC_DRIVER_SHA256": DRIVER_SHA256, "SCIENTIFIC_ARGS": {"repo_root": str(repo), "run_root": str(run)},
        "EXECUTION_AUTHORITY_SOURCE_SHA256": execution_authority_source_hashes,
        "RUN_AUTHORITY_PERSISTED_IN": "state.json",
        "CONTINUATION_LAUNCHER_SHA256": digest(Path(__file__)), "LAUNCHER_SHA256": digest(LAUNCHER),
        "AUTHORITATIVE_PACKET_REF": PACKET, "RECORDED_AT_UTC": driver.utc_now(), "PID": os.getpid(),
        "WORKERS": 1, "THREAD_LIMITS": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        "LOGICAL_RUN_CHANGED": False, "SCIENTIFIC_SOURCE_CHANGED": False, "PROJECT_MEMORY_WRITTEN": "NO",
    }
    driver.atomic_create_or_match(run / "owner-continuation8-phase0.json", driver.canonical_json(phase0))
    driver.atomic_create_or_match(run / "execution-argv-continuation8.json", driver.canonical_json(execution))
    gate_calls = 0

    def launch_gate(path):
        nonlocal gate_calls
        if gate_calls:
            raise RuntimeError("second resource gate forbidden")
        gate_calls += 1
        writers = blocking_writers_once()
        usage = shutil.disk_usage(path)
        passed = usage.free >= driver.FINAL_GATE_BYTES and not writers
        gate = {
            "TASK_ID": driver.TASK_ID, "EXECUTION_ID": driver.EXECUTION_ID,
            "PROTECTED_EXECUTION_ID": PROTECTED_EXECUTION_ID, "CHECKED_AT_UTC": driver.utc_now(),
            "FREE_SPACE_GIB": usage.free / 1024**3, "REQUIRED_FREE_SPACE_GIB": 8,
            "HEAVY_SCIENTIFIC_WRITER_ACTIVE": "YES" if writers else "NO", "BLOCKING_HEAVY_PROCESSES": writers,
            "FREE_SPACE_READ_COUNT": 1, "ACTIVE_WRITER_SNAPSHOT_COUNT": 1, "RECHECKS": 0,
            "FINAL_LAUNCH_CHECK": "PASS" if passed else "FAIL", "STOP_ONCE": not passed,
        }
        driver.atomic_create_or_match(run / "owner-continuation8-launch-check.json", driver.canonical_json(gate))
        print(json.dumps(gate, sort_keys=True), flush=True)
        if not passed:
            result = {
                "TASK_STATUS": "STOPPED_PRELAUNCH_GATE", "BLOCKER_CODE": "FINAL_LAUNCH_GATE_FAILED_STOP_ONCE",
                "FREE_SPACE_GIB": gate["FREE_SPACE_GIB"], "HEAVY_SCIENTIFIC_WRITER_ACTIVE": gate["HEAVY_SCIENTIFIC_WRITER_ACTIVE"],
                "BLOCKING_HEAVY_PROCESSES": writers, "SCIENTIFIC_CAMPAIGN_STARTED": "NO",
                "SETS_COMPLETED": 0, "PROVEN_OPTIMAL_SETS": 0, "GLOBAL_TICKETS_SCORED": 0,
                "NODES_EXPLORED": 0, "NODES_PRUNED": 0, "BEST_COUNT": driver.START_COUNT, "BEST_DELTA": 0,
                "BEST_SHA256": driver.START_SHA256, "BEST_DESTROY_INDICES": None, "BEST_NEW_TICKETS": [],
                "BEST_CANONICAL_RECOUNT_STATUS": "PASS_REUSED_FROZEN_START_EVIDENCE",
                "SCIENTIFIC_RESULT": "NOT_RUN", "NO_IMPROVEMENT_CLAIMED": False, "COMPLETE_N5_OPTIMUM": "NOT_CLAIMED",
                "TASK_ID": driver.TASK_ID, "EXECUTION_ID": driver.EXECUTION_ID, "PROTECTED_EXECUTION_ID": PROTECTED_EXECUTION_ID,
                "WORKTREE": str(repo), "RUN_ROOT": str(run), "FINAL_LAUNCH_CHECK": gate,
                "PHASE0_FILE": "owner-continuation8-phase0.json", "EXECUTION_ARGV_FILE": "execution-argv-continuation8.json",
                "EXECUTION_ARGV_FILE_SHA256": digest(run / "execution-argv-continuation8.json"),
                "JOURNAL_PREFIX_SHA256": hashlib.sha256(b"").hexdigest(), "JOURNAL_STATUS": "NOT_INITIALIZED",
                "CORRECTNESS_CHECKS_RERUN": False, "VERIFIED_COMPLETED_SETS_RECOMPUTED": 0,
                "PROJECT_MEMORY_WRITTEN": "NO", "PUSH": "NO", "PR": "NO", "MERGE": "NO", "PRODUCTION_CHANGE": "NONE",
                "MILESTONE_MONITOR_STATUS": "EXPECTED_NOT_STARTED", "SET7_STATUS": "NOT_RUN_DESTROY5_NOT_TERMINAL", "SET5_STATUS": "NOT_RUN",
                "SEALED_AT_UTC": driver.utc_now(),
            }
            driver.atomic_create_or_match(run / "owner-continuation8-stop-result.json", driver.canonical_json(result))
            raise LaunchStop("FINAL_LAUNCH_GATE_FAILED_STOP_ONCE")
        driver.atomic_create_or_match(run / "canonical-recounts.jsonl", b"", mode=0o600)
        return usage

    # The existing driver asks for disk usage exactly once, after acquiring its
    # scientific single-writer lock. Bind the atomic resource gate to that call.
    # The original scientific driver, source overlay, START and manifest remain unchanged.
    driver.shutil = SimpleNamespace(disk_usage=launch_gate)
    try:
        assert execution_authority_binding["run_root"] == run
        driver.run_campaign(repo, run)
        return 0
    except LaunchStop:
        print("STOP_ONCE: scientific campaign not launched", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
