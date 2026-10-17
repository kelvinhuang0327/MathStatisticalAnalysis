"""Task-local protected adapter; immutable donor math and frozen N3 kernel."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import resource
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_C2_N3_0_18_19_FULL_DOMAIN_R1"
EXECUTION_ID = "run1"
RECORD_ROOT = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")
EXACT_ROOT = Path("/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis") / TASK_ID
DONOR_COMMIT = "f347766d4252c087d2a0bf36375242dd72238a88"
KERNEL_SHA = "ebd39a1611aada9fcc8bec132a674de54613b8ac1b95029c57ac0e3d95204588"
LAUNCHER = Path("/Users/kelvin/VibeCoding-WorkSpace/skill/fable-method/scripts/task_checkpoint.rb")
LAUNCHER_SHA = "c2258c763ec86b20c0e38b7700ecde4b1069a5ffbb0038fb766cd9bad00f6a02"
ORIGINAL_START = 1792132635
TOTAL_BUDGET = 86400
RESERVE = 3600
MEMORY_BUDGET = 8589934592
RSS_STOP = 7516192768
STATE = ROOT / ".task-data" / TASK_ID
RUN = STATE / EXECUTION_ID
CLOCK = STATE / "task-clock.json"
RESULT = RUN / "task-result.json"
JOURNAL = RUN / "solver.anchors.jsonl"
ORIGINAL_PACKET = Path(
    "/Users/kelvin/.codex/attachments/daaeba9c-56c9-4f72-aa48-72b162cf22fb/pasted-text-1.txt"
)
CURRENT_PACKET = Path(
    "/Users/kelvin/.codex/attachments/f103b2f1-0ab1-4024-ba15-1c3c369bdc4c/pasted-text-1.txt"
)
ORIGINAL_SESSION = Path(
    "/Users/kelvin/.codex/sessions/2026/10/16/rollout-2026-10-16T14-37-11-01a1436d-b99c-7f52-9625-4b64728a3322.jsonl"
)
DONOR_PATH = ROOT / "src/lottolab/research/b649_c2_n3_121314_full_domain_r1.py"
spec = importlib.util.spec_from_file_location(__name__ + "._pinned_donor", DONOR_PATH)
donor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(donor)
donor.TASK_ID = TASK_ID
donor.DESTROY_SLOTS = (0, 18, 19)
donor.REMOVED_TICKETS = ((1, 2, 3, 4, 5, 21), (32, 37, 42, 44, 46, 48), (33, 38, 43, 45, 47, 49))
donor.REMAINDER_SHA256 = "e27578baabb0b6dac6c4b7ae79fa1ae386384ae5a4794a2586d6c36842ed4e81"
_STOP_SIGNAL = None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def write_json(path, data, exclusive=False):
    raw = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)


def utc(epoch):
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def remaining(clock, now):
    if (
        clock["original_start_epoch"] != ORIGINAL_START
        or clock["total_budget_seconds"] != TOTAL_BUDGET
    ):
        raise RuntimeError("clock authority changed")
    if clock["absolute_deadline_epoch"] != ORIGINAL_START + TOTAL_BUDGET:
        raise RuntimeError("absolute deadline changed")
    if clock["solver_deadline_epoch"] != ORIGINAL_START + TOTAL_BUDGET - RESERVE:
        raise RuntimeError("solver deadline changed")
    return max(0.0, clock["solver_deadline_epoch"] - now)


def bind_clock():
    events = []
    with ORIGINAL_SESSION.open() as stream:
        for line in stream:
            obj = json.loads(line)
            payload = obj.get("payload", {})
            if (
                payload.get("type") == "thread_goal_updated"
                and payload.get("goal", {}).get("createdAt") == ORIGINAL_START
            ):
                events.append(obj)
    if not events:
        raise RuntimeError("original Goal createdAt authority absent")
    event = events[0]
    expected = {
        "task_id": TASK_ID,
        "execution_id": EXECUTION_ID,
        "original_thread_id": "01a1436d-b99c-7f52-9625-4b64728a3322",
        "original_start_epoch": ORIGINAL_START,
        "original_start_utc": utc(ORIGINAL_START),
        "original_time_authority": "original persisted thread_goal_updated.goal.createdAt",
        "original_goal_event": event,
        "original_packet_sha256": file_sha(ORIGINAL_PACKET),
        "continuation_packet_sha256": file_sha(CURRENT_PACKET),
        "total_budget_seconds": TOTAL_BUDGET,
        "canonical_reserve_seconds": RESERVE,
        "absolute_deadline_epoch": ORIGINAL_START + TOTAL_BUDGET,
        "solver_deadline_epoch": ORIGINAL_START + TOTAL_BUDGET - RESERVE,
        "absolute_deadline_utc": utc(ORIGINAL_START + TOTAL_BUDGET),
        "solver_deadline_utc": utc(ORIGINAL_START + TOTAL_BUDGET - RESERVE),
        "policy": (
            "original Goal start bounds setup, blocked time, search and sealing; never reset"
        ),
    }
    if CLOCK.exists():
        clock = json.loads(CLOCK.read_text())
        if clock != expected:
            raise RuntimeError("existing clock differs; no replacement permitted")
    else:
        write_json(CLOCK, expected, exclusive=True)
        for name, source in [
            ("original-packet.txt", ORIGINAL_PACKET),
            ("continuation-packet.txt", CURRENT_PACKET),
        ]:
            with (STATE / name).open("xb") as out:
                out.write(source.read_bytes())
    remaining(expected, time.time())
    return expected


def verify_sources():
    if (
        ROOT != EXACT_ROOT
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        != DONOR_COMMIT
    ):
        raise RuntimeError("exact worktree/source identity mismatch")
    donor_relative = str(DONOR_PATH.relative_to(ROOT))
    if DONOR_PATH.read_bytes() != git_blob(DONOR_COMMIT, donor_relative):
        raise RuntimeError("donor changed")
    c2_path = "docs/research/matrix-native-results/b649-cell-a-c2-independent-recount-r1.json"
    c2 = json.loads(git_blob(donor.C2_RECOUNT_COMMIT, c2_path))
    ordered = c2["C2"]["full_portfolio"]
    if ordered != donor.ordered_tickets(ROOT) or donor.sha256_text(ordered) != donor.ORDERED_SHA256:
        raise RuntimeError("immutable C2 identity mismatch")
    kept = donor.remainder_tickets(ROOT)
    if not donor.portfolio_structure_ok(ordered, kept, donor.REMOVED_TICKETS):
        raise RuntimeError("illegal C2/remainder")
    for commit, path in [(donor.N1_COMMIT, donor.N1_RESULT), (donor.N2_COMMIT, donor.N2_RESULT)]:
        if (ROOT / path).read_bytes() != git_blob(commit, path):
            raise RuntimeError("archived N1/N2 certificate changed")
    if not donor.n1_n2_certificate(ROOT)["applies"]:
        raise RuntimeError("archived N1/N2 evidence does not apply")
    if file_sha(ROOT / donor.EVALUATOR_RELATIVE) != donor.EVALUATOR_SHA256:
        raise RuntimeError("evaluator pin mismatch")
    if LAUNCHER.resolve() != LAUNCHER or file_sha(LAUNCHER) != LAUNCHER_SHA:
        raise RuntimeError("canonical launcher identity mismatch")
    marker = RECORD_ROOT / ".git/fable-locks/repository-generation.json"
    doc = json.loads(marker.read_text())
    if doc["generation"] != 2 or doc["common_directory"] != str(RECORD_ROOT / ".git"):
        raise RuntimeError("generation marker mismatch")
    return {
        "C2_ORDERED_SHA256": donor.sha256_text(ordered),
        "REMAINDER_SHA256": donor.sha256_text(kept),
        "EVALUATOR_SHA256": donor.EVALUATOR_SHA256,
        "DONOR_SHA256": file_sha(DONOR_PATH),
        "GENERATION_MARKER_SHA256": file_sha(marker),
        "N1_N2_CERTIFICATE": donor.n1_n2_certificate(ROOT),
        "DOMAINS": donor.domain_integers(),
    }


def prepare():
    sources = verify_sources()
    clock = bind_clock()
    if remaining(clock, time.time()) <= 0:
        raise RuntimeError("TIME_WINDOW_EXPIRED")
    if (RUN / "SOLVER_STARTED.json").exists():
        raise RuntimeError("formal solver already started")
    RUN.mkdir(parents=True, exist_ok=True)
    source_dir = RUN / "kernel-src"
    donor._extract_kernel(ROOT, source_dir)
    source_sha, hashes = donor._kernel_source_digest(source_dir)
    if source_sha != KERNEL_SHA:
        raise RuntimeError("frozen kernel source mismatch")
    compile_argv = [
        "clang",
        "-std=c11",
        "-O3",
        "-Wall",
        "-Wextra",
        f'-DN3_ENGINE_SHA256="{source_sha}"',
        *[str(source_dir / n) for n in donor.KERNEL_FILES if n.endswith(".c")],
        "-o",
        str(RUN / "n3-exact"),
    ]
    compiled = subprocess.run(compile_argv, cwd=ROOT, capture_output=True, text=True)
    (RUN / "compile.log").write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise RuntimeError(f"kernel compilation exit {compiled.returncode}")
    recount_source = ROOT / "src/lottolab/research/b649_c2_n3_0_18_19_recount.c"
    recount_argv = [
        "clang",
        "-std=c11",
        "-O3",
        "-Wall",
        "-Wextra",
        str(recount_source),
        "-o",
        str(RUN / "recount-7set"),
    ]
    recount_compile = subprocess.run(recount_argv, capture_output=True, text=True)
    if recount_compile.returncode:
        raise RuntimeError(recount_compile.stderr)
    report = {
        **sources,
        "SOURCE_HEAD": DONOR_COMMIT,
        "SOURCE_TREE": subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True
        ).strip(),
        "CANONICAL_LAUNCHER_PATH": str(LAUNCHER),
        "CANONICAL_LAUNCHER_SHA256": LAUNCHER_SHA,
        "TASK_CLOCK_SHA256": file_sha(CLOCK),
        "CLOCK": clock,
        "KERNEL_SOURCE_SHA256": source_sha,
        "KERNEL_SOURCE_FILES": hashes,
        "KERNEL_BINARY_SHA256": file_sha(RUN / "n3-exact"),
        "COMPILE_ARGV": compile_argv,
        "COMPILE_EXIT_CODE": compiled.returncode,
        "ADAPTER_SHA256": file_sha(__file__),
        "RECOUNT_SOURCE_SHA256": file_sha(recount_source),
        "RECOUNT_BINARY_SHA256": file_sha(RUN / "recount-7set"),
        "GEOMETRIC_LUT_ENABLED": False,
        "IMPLEMENTATION_DEPTH": "NORMAL",
        "DEPTH_SOURCE": "fable-method default; Packet specifies STANDARD/SELF_CHECK_ONLY",
    }
    write_json(RUN / "preflight.json", report)
    return report


def inherited_protection():
    fields = {
        key: os.environ.get(key)
        for key in (
            "FABLE_PROTECTED_RUN_LOCK_FD",
            "FABLE_HEAVY_SCIENTIFIC_LEASE_FD",
            "FABLE_HEAVY_SCIENTIFIC_LEASE_TASK_ID",
            "FABLE_HEAVY_SCIENTIFIC_LEASE_EXECUTION_ID",
            "FABLE_HEAVY_SCIENTIFIC_LEASE_WORKTREE",
            "FABLE_HEAVY_SCIENTIFIC_LEASE_RUN_ROOT",
        )
    }
    if (
        fields["FABLE_HEAVY_SCIENTIFIC_LEASE_TASK_ID"] != TASK_ID
        or fields["FABLE_HEAVY_SCIENTIFIC_LEASE_EXECUTION_ID"] != EXECUTION_ID
    ):
        raise RuntimeError("protected heavy lease scope absent/mismatched")
    if fields["FABLE_HEAVY_SCIENTIFIC_LEASE_WORKTREE"] != str(ROOT) or fields[
        "FABLE_HEAVY_SCIENTIFIC_LEASE_RUN_ROOT"
    ] != str(RUN):
        raise RuntimeError("protected heavy lease paths mismatch")
    fds = tuple(
        int(fields[k]) for k in ("FABLE_PROTECTED_RUN_LOCK_FD", "FABLE_HEAVY_SCIENTIFIC_LEASE_FD")
    )
    if len(set(fds)) != 2:
        raise RuntimeError("protection descriptors invalid")
    for fd in fds:
        os.fstat(fd)
    return fields, fds


def memory_limits():
    result = {
        "MEMORY_BUDGET_BYTES": MEMORY_BUDGET,
        "MONITORED_STOP_LOSS_BYTES": RSS_STOP,
        "MONITOR_IS_OS_HARD_CAP": False,
        "OS_HARD_LIMIT_AVAILABLE": False,
        "RLIMITS": {},
    }
    for name in ("RLIMIT_AS", "RLIMIT_DATA", "RLIMIT_RSS"):
        kind = getattr(resource, name)
        before = resource.getrlimit(kind)
        try:
            resource.setrlimit(kind, (MEMORY_BUDGET, before[1]))
            after = resource.getrlimit(kind)
            enforced = name in ("RLIMIT_AS", "RLIMIT_DATA") and sys.platform != "darwin"
            result["RLIMITS"][name] = {
                "before": before,
                "after": after,
                "set_success": True,
                "enforcement_confirmed": enforced,
            }
            result["OS_HARD_LIMIT_AVAILABLE"] |= enforced
        except (OSError, ValueError) as exc:
            result["RLIMITS"][name] = {"before": before, "set_success": False, "error": str(exc)}
    result["OS_HARD_LIMIT_BYTES"] = MEMORY_BUDGET if result["OS_HARD_LIMIT_AVAILABLE"] else None
    return result


def validate_journal(path, doc):
    lines = path.read_bytes().splitlines(keepends=True)
    body, prefix = lines[0].rstrip(b"\n").rsplit(b"|JOURNAL_PREFIX_SHA256=", 1)
    if digest(body).encode() != prefix:
        raise RuntimeError("journal header hash mismatch")
    header = dict(part.decode().split("=", 1) for part in body.split(b"|")[1:])
    if header["ENGINE_SHA256"] != KERNEL_SHA or int(header["F0"]) != doc["INCUMBENT"]["F0_DIRECT"]:
        raise RuntimeError("journal source/problem mismatch")
    previous_accounted = 0
    for index, line in enumerate(lines[1:]):
        if not line.endswith(b"\n"):
            raise RuntimeError("truncated journal")
        record, current = line.rstrip(b"\n").rsplit(b"|", 1)
        if digest(prefix + b"\n" + record).encode() != current:
            raise RuntimeError("journal chain mismatch")
        fields = record.split(b"|")
        if fields[0] != b"A" or int(fields[1]) != index or int(fields[7]) < previous_accounted:
            raise RuntimeError("journal sequence/accounting mismatch")
        if fields[2] == b"P" and not 0 <= int(fields[4]) < int(fields[3]):
            raise RuntimeError("journal unsafe pruned bound")
        previous_accounted = int(fields[7])
        prefix = current
    solver = doc["SOLVER"]
    if (
        len(lines) - 1 != solver["CHECKPOINT_ANCHORS_RECORDED"]
        or prefix.decode() != solver["JOURNAL_PREFIX_SHA256"]
    ):
        raise RuntimeError("journal/kernel final prefix mismatch")
    if solver["CLOSED"] and len(lines) - 1 != int(header["TOTAL_ANCHORS"]):
        raise RuntimeError("closure has missing anchors")
    return {
        "status": "PASS",
        "anchors": len(lines) - 1,
        "header": header,
        "prefix_sha256": prefix.decode(),
        "sha256": file_sha(path),
    }


def result_status(accounting, kernel_code, journal_ok, verified_gain, stop_reason):
    if stop_reason in (
        "ABSOLUTE_SOLVER_DEADLINE",
        "MEMORY_MONITOR_STOP_LOSS",
        "OWNER_OR_PROCESS_SIGNAL",
    ):
        return "INCOMPLETE_FRONTIER_OPEN"
    if kernel_code != 0 or not journal_ok:
        return "EXECUTION_ERROR"
    return donor.status_from_accounting(
        accounting["buckets"],
        stop_reason=stop_reason,
        verified_gain=verified_gain,
        positive_exact=accounting["listed_gain"] is not None and not verified_gain,
    )


def accept_gain(portfolio, kept, triple, delta7, canonical, independent):
    return (
        donor.portfolio_structure_ok(portfolio, kept, triple)
        and independent * 7 == canonical
        and donor.decision_from_recount(
            count=canonical,
            delta7=delta7,
            structural_ok=True,
            evaluator_sha256=donor.EVALUATOR_SHA256,
        )
    )


def signal_stop(signum, _frame):
    global _STOP_SIGNAL
    _STOP_SIGNAL = signum


def bounded_capture(argv, deadline, fds):
    timeout = deadline - time.time()
    if timeout <= 0:
        raise TimeoutError("verification deadline exhausted")
    return subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, pass_fds=fds
    )


def solve():
    report = json.loads((RUN / "preflight.json").read_text())
    clock = json.loads(CLOCK.read_text())
    verify_sources()
    if (
        file_sha(CLOCK) != report["TASK_CLOCK_SHA256"]
        or file_sha(__file__) != report["ADAPTER_SHA256"]
    ):
        raise RuntimeError("preflight/clock/adapter changed")
    if file_sha(RUN / "n3-exact") != report["KERNEL_BINARY_SHA256"]:
        raise RuntimeError("kernel binary changed")
    if file_sha(RUN / "recount-7set") != report["RECOUNT_BINARY_SHA256"]:
        raise RuntimeError("independent recount binary changed")
    protection, fds = inherited_protection()
    budget = remaining(clock, time.time())
    if budget <= 0:
        raise RuntimeError("TIME_WINDOW_EXPIRED")
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, signal_stop)
    resources = memory_limits()
    kept = donor.remainder_tickets(ROOT)
    argv = [
        str(RUN / "n3-exact"),
        "--kept",
        donor._tickets_arg(kept),
        "--removed",
        donor._tickets_arg(donor.REMOVED_TICKETS),
        "--out",
        str(RUN / "kernel-result.json"),
        "--checkpoint",
        str(JOURNAL),
        "--time-limit",
        str(budget),
        "--verbose",
    ]
    write_json(
        RUN / "SOLVER_STARTED.json",
        {
            "task_id": TASK_ID,
            "execution_id": EXECUTION_ID,
            "driver_pid": os.getpid(),
            "started_epoch": time.time(),
            "clock_sha256": file_sha(CLOCK),
            "argv": argv,
            "protection": protection,
        },
        exclusive=True,
    )
    started = time.monotonic()
    peak = 0
    stop = "KERNEL_EXIT"
    env = {
        **os.environ,
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    with (RUN / "solver.log").open("w") as log:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=log, pass_fds=fds, env=env)
        write_json(
            RUN / "process.json",
            {
                "driver_pid": os.getpid(),
                "kernel_pid": process.pid,
                "started_epoch": time.time(),
                "argv": argv,
            },
            exclusive=True,
        )
        while process.poll() is None:
            rss = donor._sample_rss(process.pid)
            peak = max(peak, rss or 0)
            if (
                _STOP_SIGNAL
                or (rss is not None and rss >= RSS_STOP)
                or time.time() >= clock["solver_deadline_epoch"]
            ):
                stop = (
                    "OWNER_OR_PROCESS_SIGNAL"
                    if _STOP_SIGNAL
                    else "MEMORY_MONITOR_STOP_LOSS"
                    if (rss or 0) >= RSS_STOP
                    else "ABSOLUTE_SOLVER_DEADLINE"
                )
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                break
            time.sleep(1)
        code = process.wait()
    wall = time.monotonic() - started
    doc = (
        donor._load_kernel_document(RUN / "kernel-result.json")
        if (RUN / "kernel-result.json").exists()
        else None
    )
    summary = donor.normalize_kernel_document(doc) if doc else None
    accounting = donor.account_kernel(summary, certificate_ok=True, kept=kept)
    journal = None
    error = None
    try:
        if doc:
            if doc["KEPT"] != kept or doc["REMOVED"] != [list(t) for t in donor.REMOVED_TICKETS]:
                raise RuntimeError("kernel input mismatch")
            journal = validate_journal(JOURNAL, doc)
    except Exception as exc:
        error = repr(exc)
    verified = False
    recount = None
    delta7 = int(summary["best_f"]) - int(summary["f0"]) if summary else None
    if accounting["listed_gain"] is not None and delta7 is not None and delta7 > 0:
        triple = accounting["listed_gain"]
        portfolio = donor._replace_slots(kept, sorted(triple, key=donor._ticket_key))
        try:
            write_json(RUN / "candidate-portfolio.json", portfolio, exclusive=True)
            canonical_script = (
                "import json; from pathlib import Path; "
                "from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio; "
                "p=json.loads(Path('" + str(RUN / "candidate-portfolio.json") + "').read_text()); "
                "print(evaluate_portfolio([tuple(t) for t in p]).official_any_prize_outcome_count)"
            )
            canonical = bounded_capture(
                [sys.executable, "-c", canonical_script], clock["absolute_deadline_epoch"] - 60, fds
            )
            independent = bounded_capture(
                [
                    str(RUN / "recount-7set"),
                    "49",
                    *[str(sum(1 << (n - 1) for n in t)) for t in portfolio],
                ],
                clock["absolute_deadline_epoch"] - 30,
                fds,
            )
            canonical_count = int(canonical.stdout.strip()) if canonical.returncode == 0 else None
            independent_count = (
                int(independent.stdout.strip()) if independent.returncode == 0 else None
            )
            verified = (
                canonical_count is not None
                and independent_count is not None
                and accept_gain(
                    portfolio,
                    kept,
                    sorted(triple, key=donor._ticket_key),
                    delta7,
                    canonical_count,
                    independent_count,
                )
            )
            recount = {
                "portfolio": portfolio,
                "ordered_sha256": donor.sha256_text(portfolio),
                "normalized_sha256": donor.sha256_text(sorted(portfolio)),
                "canonical_count": canonical_count,
                "independent_7set_count": independent_count,
                "canonical_exit_code": canonical.returncode,
                "independent_exit_code": independent.returncode,
                "canonical_stderr": canonical.stderr,
                "independent_stderr": independent.stderr,
                "accepted": verified,
            }
        except Exception as exc:
            error = repr(exc)
    effective_stop = accounting["stop_reason"] if stop == "KERNEL_EXIT" else stop
    status = result_status(accounting, code, journal is not None, verified, effective_stop)
    if time.time() >= clock["absolute_deadline_epoch"]:
        status = "INCOMPLETE_FRONTIER_OPEN"
        effective_stop = "TOTAL_ABSOLUTE_DEADLINE"
    buckets = accounting["buckets"]
    payload = {
        "TASK_ID": TASK_ID,
        "EXECUTION_ID": EXECUTION_ID,
        "TASK_STATUS": status,
        "PREFLIGHT": report,
        "SOURCE_HEAD": report["SOURCE_HEAD"],
        "SOURCE_TREE": report["SOURCE_TREE"],
        "WORKTREE_PATH": str(ROOT),
        "BRANCH": "codex/b649-c2-n3-0-18-19-full-domain-r1",
        "FORMAL_EXECUTION_COUNT": 1,
        "SOLVER_STARTED_EVIDENCE": str(RUN / "SOLVER_STARTED.json"),
        "ORIGINAL_TIME_AUTHORITY": clock["original_time_authority"],
        "TASK_CLOCK_SHA256": file_sha(CLOCK),
        "ACTUAL_ABSOLUTE_DEADLINES": clock,
        "CANONICAL_LAUNCHER_PATH": str(LAUNCHER),
        "CANONICAL_LAUNCHER_SHA256": LAUNCHER_SHA,
        "HEAVY_LEASE_STATUS": "INHERITED_CANONICAL_PROTECTED_LEASE",
        "PROTECTION": protection,
        "GENERATION_MARKER_STATUS": "PRESENT_IDENTITY_MATCH",
        "KERNEL_SOURCE_SHA256": KERNEL_SHA,
        "KERNEL_BINARY_SHA256": report["KERNEL_BINARY_SHA256"],
        "EVALUATOR_SHA256": donor.EVALUATOR_SHA256,
        "C2_ORDERED_SHA256": donor.ORDERED_SHA256,
        "REMAINDER_SHA256": donor.REMAINDER_SHA256,
        "RAW_LEGAL_DOMAIN": str(donor.RAW_LEGAL_N3_DOMAIN),
        "N1_N2_CERTIFIED_COUNT": str(buckets["N1_N2_CERTIFIED_NO_GAIN"]),
        "EXACT_EVALUATED_COUNT": str(buckets["EXACT_EVALUATED"]),
        "BOUND_PRUNED_COUNT": str(buckets["PROVEN_BOUND_PRUNED"]),
        "UNRESOLVED_FRONTIER_COUNT": str(buckets["UNRESOLVED_FRONTIER"]),
        "ACCOUNTING_PARITY": sum(buckets.values()) == donor.RAW_LEGAL_N3_DOMAIN,
        "SAFE_PRUNING_CERTIFICATES": accounting["certificates"],
        "FIRST_UNFINISHED_FRONTIER": accounting["first_unfinished_frontier"],
        "BEST_DELTA_7SET": delta7,
        "BEST_CANONICAL_COUNT": recount["canonical_count"] if verified else donor.START_COUNT,
        "BEST_PORTFOLIO_SHA": recount["ordered_sha256"] if verified else donor.ORDERED_SHA256,
        "CANONICAL_RECOUNT_STATUS": "PASS"
        if verified
        else "FAIL"
        if recount
        else "NOT_APPLICABLE_NO_GAIN_CANDIDATE",
        "INDEPENDENT_7SET_RECOUNT_STATUS": "PASS"
        if verified
        else "FAIL"
        if recount
        else "NOT_APPLICABLE_NO_GAIN_CANDIDATE",
        "RECOUNT": recount,
        "SOLVER_WALL": wall,
        "TOTAL_WALL": time.time() - ORIGINAL_START,
        "PEAK_RSS": max(peak, doc.get("PEAK_RSS_BYTES", 0) if doc else 0),
        "STOP_REASON": effective_stop,
        "RESOURCE_ENFORCEMENT": resources,
        "KERNEL_EXIT_CODE": code,
        "DRIVER_EXIT_CODE": 0 if status != "EXECUTION_ERROR" else 1,
        "LAUNCHER_EXIT_CODE": "PENDING_EXTERNAL_OS_OBSERVATION",
        "JOURNAL_VALIDATION": journal,
        "ERROR": error,
        "CHECKPOINT_LOCATOR": str(JOURNAL),
        "CHECKPOINT_SHA256": file_sha(JOURNAL) if JOURNAL.exists() else None,
        "KERNEL_RESULT_SHA256": file_sha(RUN / "kernel-result.json") if doc else None,
        "SHARED_FABLE_CHANGED": False,
        "OLD_N3_CHANGED": False,
        "GEOMETRIC_LUT_ENABLED": False,
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "COMMIT_STATUS": "NOT_CREATED",
        "WORKTREE_STATUS": "RETAINED",
    }
    write_json(RESULT, payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "solve"])
    args = parser.parse_args()
    payload = prepare() if args.command == "prepare" else solve()
    print(
        json.dumps(
            {
                k: payload[k]
                for k in (
                    "TASK_STATUS",
                    "KERNEL_BINARY_SHA256",
                    "TASK_CLOCK_SHA256",
                    "UNRESOLVED_FRONTIER_COUNT",
                )
                if k in payload
            }
        )
    )
    return int(payload.get("DRIVER_EXIT_CODE", 0))


if __name__ == "__main__":
    raise SystemExit(main())
