"""Read evidence for the remediated pair and validate actual observer coverage."""
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from write_observer import install

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "config-r2.json").read_text())
emit = install("verification", ROOT / "config.json", denial_probe=True)
os.umask(0o077)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def events(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def under(path, root):
    return Path(path).is_relative_to(Path(root))


def save(name, value):
    with (ROOT / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


execution = load(ROOT / "execution-result-r2.json")
controller = load(ROOT / "strict-controller-r2-dispatch.json")
before = load(ROOT / "strict-r2-isolated-before.json")
after = load(ROOT / "strict-r2-isolated-after.json")
host_before = load(ROOT / "strict-r2-host-before.json")
host_after = load(ROOT / "strict-r2-host-after.json")
harness = events(ROOT / ("strict-harness-" + str(execution["harness_pid"]) + ".jsonl"))
checks = {"strict_controller_exit": controller["exit_status"] == 0 and not controller["stderr"],
          "same_strict_harness_pid": controller["pid"] == execution["harness_pid"],
          "independent_metadata": before["common_dir"] == C["isolated_repo"] + "/.git" and not before["alternates_exists"] and before["shallow"] == "false" and not before["remotes"],
          "fixed_head_tree": before["head"] == C["expected_head"] and before["tree"] == C["expected_tree"],
          "all_isolated_product_and_git_files_unchanged": before == after,
          "host_source_fixed_clean": host_before["source"]["head_tree_parent"] == host_after["source"]["head_tree_parent"] and not host_after["source"]["status"],
          "existing_source_refs_unchanged_during_strict_pair": host_before["source"]["refs"] == host_after["source"]["refs"],
          "old_judge_unchanged": sha(C["judge"]) == C["judge_sha256"],
          "original_launcher_bytes": sha(C["launcher"]) == "e9d3e5e03fded1974fb16fcb177cfc96ccc817bf8e72d2084ff7407a4383be62",
          "old_files_preserved": all(Path(p).is_file() and sha(p) == data["sha256"] and oct(Path(p).stat().st_mode & 0o777) == data["mode"] for p, data in C["old_files"].items()),
          "strict_harness_denial_observed": any(e["operation"] == "sandbox-write-denied" and e["denied"] and not e["exists"] for e in harness),
          "no_suite_or_solver": execution["full_suite_runs"] == execution["solver_runs"] == 0}
profile = (ROOT / "smoke-r2.sb").read_text()
allowed_roots = [str(ROOT), C["runtime_parent"], *[str(Path(C["original_root"]) / "runs" / name) for name in C["execution_ids"]]]
checks["strict_policy_exact_allowlist"] = ("(deny file-write*)" in profile and "(deny network*)" in profile
    and re.findall(r'\(subpath "([^"]+)"\)', profile) == allowed_roots
    and all(not under(Path(C["isolated_repo"]) / ".git", p) for p in allowed_roots)
    and all(not under(Path(C["primary"]) / ".git", p) for p in allowed_roots))

run_checks = {}
provenance = []
all_controlled_events = list(harness)
for run in execution["runs"]:
    name = run["execution_id"]
    directory = Path(run["run_dir"])
    launch, terminal, end = (load(directory / n) for n in ("launch.json", "capture.json", "end.json"))
    ruby = events(ROOT / ("ruby-" + str(run["pid"]) + ".jsonl"))
    pylogs = [(p, events(p)) for p in ROOT.glob("python-child-*.jsonl")]
    pylogs = [(p, ev) for p, ev in pylogs if ev[0]["ppid"] == run["pid"]]
    py = [event for _, ev in pylogs for event in ev]
    child_pid = run["child_observation"]["observed_pid"]
    child = [e for e in py if e["pid"] == child_pid]
    spawn_events = [e for e in ruby if e["operation"] == "process-spawn"]
    spawned = {e["child_pid"] for e in spawn_events}
    trace = events(ROOT / ("git-" + name + ".jsonl"))
    git_starts = [e for e in trace if e.get("event") == "start"]
    git_pids = {int(re.findall(r'-P([0-9a-fA-F]+)', e["sid"])[-1], 16) for e in git_starts}
    git_commands = {e["argv"][e["argv"].index("-C") + 2] for e in git_starts}
    py_pids = {ev[0]["pid"] for _, ev in pylogs}
    created = {e["path"] for e in ruby if e["operation"] == "file-open-return" and e["result"] == "SUCCESS"}
    created.update(e["to"] for e in ruby if e["operation"] == "file-rename")
    file_origins = {str(p): run["pid"] for p in directory.iterdir() if p.is_file() and str(p) in created}
    uncovered = [str(p) for p in directory.iterdir() if p.is_file() and str(p) not in file_origins]
    denied = [e for e in ruby + py if e["operation"] == "sandbox-write-denied"]
    actual_file_requests = [e["path"] for e in ruby + py if e["operation"] in {"file-open-request", "file-write-request"}]
    expected_denials = {e["path"] for e in denied}
    outside_requests = [p for p in actual_file_requests if not any(under(p, allowed) for allowed in allowed_roots) and p not in expected_denials]
    launch_return = next(e for e in ruby if e["operation"] == "file-open-return" and e["path"] == str(directory / "launch.json") and e["result"] == "SUCCESS")
    launch_commit_ns = int(datetime.fromisoformat(launch_return["utc"].replace("Z", "+00:00")).timestamp() * 1e9)
    first_child_start = min(e["time_ns"] for e in child if e["operation"] == "observer-start")
    local = {"expected_exit": run["exit_status"] == terminal["exit_status"] == end["exit_status"] == run["expected_exit"],
             "original_streams": run["stdout"] == terminal["stdout"] == (directory / "stdout.txt").read_text() and run["stderr"] == terminal["stderr"] == (directory / "stderr.txt").read_text(),
             "stderr_marker_exact": terminal["stderr"] == ("normal-smoke-stderr\n" if run["expected_exit"] == 0 else "negative-smoke-stderr\n"),
             "launch_hash_and_order": run["child_observation"]["launch_sha256"] == sha(directory / "launch.json") == end["launch_sha256"] and launch_commit_ns < first_child_start,
             "umask_and_paths": launch["effective_umask"] == run["child_observation"]["observed_umask"] == "0077" and launch["appdata"]["mode"] == "0700" and under(launch["runtime_root"]["path"], C["runtime_parent"]),
             "python_dependency_identity": launch["python"]["pytest"] == "9.1.1" and sha(launch["dependency_manifest"]["path"]) == launch["dependency_manifest"]["sha256"],
             "ruby_parent_is_strict_harness": ruby[0]["ppid"] == execution["harness_pid"],
             "python_parent_is_recorded_ruby": all(ev[0]["ppid"] == run["pid"] for _, ev in pylogs) and child_pid in py_pids,
             "all_spawn_edges_accounted": spawned == git_pids | py_pids and len(py_pids) == 2 and len(git_pids) == 41,
             "git_commands_read_only": git_commands <= {"rev-parse", "status", "for-each-ref", "show"},
             "all_receipt_writers_observed": not uncovered,
             "child_probe_write_observed": any(e["operation"] == "file-write-request" and e["path"] == run["child_observation"]["probe_path"] for e in child),
             "all_python_and_ruby_denials_observed": {e["pid"] for e in denied} == py_pids | {run["pid"]} and all(not e["exists"] for e in denied),
             "all_write_requests_within_allowlist_or_denied_probe": not outside_requests,
             "no_failed_denial_probe": not any(e["operation"] == "sandbox-write-denial-FAILED" for e in ruby + py),
             "isolated_refs_and_status_unchanged": end["source_refs_diff"] == {"removed": [], "added": []} and end["source_status_diff"] == {"removed": [], "added": []}}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest, filename = line.split("  ", 1)
        assert sha(directory / filename) == digest
    run_checks[name] = local
    provenance.append({"execution_id": name, "ruby_pid": run["pid"], "harness_pid": execution["harness_pid"],
                       "python_pids": sorted(py_pids), "smoke_pid": child_pid, "git_pids": sorted(git_pids),
                       "git_command_types": sorted(git_commands), "receipt_file_writer_pids": file_origins,
                       "denial_pids": sorted({e["pid"] for e in denied}), "uncovered_receipt_files": uncovered,
                       "out_of_scope_write_requests": outside_requests, "ruby_observer_path": str(ROOT / ("ruby-" + str(run["pid"]) + ".jsonl")),
                       "python_observer_paths": [str(p) for p, _ in pylogs],
                       "capture_sha256": sha(directory / "capture.json"), "launch_sha256": sha(directory / "launch.json"), "end_sha256": sha(directory / "end.json")})
    all_controlled_events.extend(ruby + py)

checks["no_network_event"] = not any(e["operation"] == "network-request" for e in all_controlled_events)
checks["all_focused_checks"] = all(all(checks_.values()) for checks_ in run_checks.values())
compat = subprocess.run(["/usr/bin/ruby", "-r", "/Users/kelvin/.codex/skills/fable-method/scripts/task_checkpoint.rb", "-e",
    "ARGV.each { |p| c=DurableCommandCapture.load(p); abort 'incomplete' unless c.complete?; puts JSON.generate(path: p, classification: DurableCommandCapture.classify_evidence(p), exit_status: c.exit_status) }",
    *[str(Path(run["run_dir"]) / "capture.json") for run in execution["runs"]]], capture_output=True, text=True)
checks["formal_fable_compatible"] = compat.returncode == 0 and all(json.loads(line)["classification"] == "EVIDENCE_COMPLETE" for line in compat.stdout.splitlines()) and len(compat.stdout.splitlines()) == 2
assert all(checks.values()) and all(all(group.values()) for group in run_checks.values()), (checks, run_checks)
save("provenance-validation.json", {"status": "PASS", "checks": checks, "run_checks": run_checks, "provenance": provenance,
     "formal_fable_validation": {"exit_status": compat.returncode, "stdout": compat.stdout, "stderr": compat.stderr},
     "kernel_write_deny_observed_pids": sorted({e["pid"] for e in all_controlled_events if e["operation"] == "sandbox-write-denied"}),
     "isolated_manifest_entries": len(before["filesystem_manifest"]), "old_files_checked": len(C["old_files"]),
     "coverage_limit": "Trusted task-specific Ruby/Python API observers plus Git Trace2, process edges, full isolated filesystem snapshots and inherited macOS kernel sandbox. No global root-level syscall trace or malicious same-UID adversary immunity claimed. Historical R1 unknown attribution remains unchanged."})
print(json.dumps({"status": "PASS", "checks": checks, "run_checks": run_checks,
                  "denial_pids": sorted({e["pid"] for e in all_controlled_events if e["operation"] == "sandbox-write-denied"})}), flush=True)
