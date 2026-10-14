"""One new R3 identity; one frozen-core (18,19) gain call; compact verified seal.

R2 results are streamed into SHA256 only, never decoded or imported. Native
resource control, donor arithmetic and integer E come from the pinned core.
No runner/monitor, retry, resume, candidate materialization or scoring is added.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "B649_C2_N2_EQUALITY_LAST_PAIR_R3_R1"
BRANCH = "codex/b649-c2-n2-equality-last-pair-r3-r1"
BASE = "6c18791b644183eb66bc393e0a6ec4812b025f98"
BASE_TREE = "e58717ade8f3efda473be3e927a2045fbd896355"
CORE_REL = "tools/b649_c2_n2_equality_seven_pair_batch_r1.py"
CORE_SHA = "9124c1f8ac6b071cc58978a81120efc7959bfde508b2a8e9e272e497563bfc05"
ORDERED_SHA = "6a537ea56c2741e1208dbbb4abf1064bc74508f2d356712920d348d11e3a4a24"
SPEC = ((18, 19), (18, 19), 93, 1)
REMOVED = [[32, 37, 42, 44, 46, 48], [33, 38, 43, 45, 47, 49]]
RESULT_REL = "docs/research/matrix-native-results/b649-c2-n2-equality-last-pair-r3-r1-result.json"
RESULT = ROOT / RESULT_REL
TEST_NAME = "test_b649_c2_n2_equality_last_pair_r3_r1.py"
PRIOR = (
    ("B649_C2_N2_EQUALITY_SEVEN_PAIR_BATCH_R1",
     "docs/research/matrix-native-results/b649-c2-n2-equality-seven-pair-batch-r1-result.json",
     "9a23ebf7fd01cc829c4de8f71eaae4fdf846d8b87f869bed079969b551175922"),
    ("B649_C2_N2_EQUALITY_SEVEN_PAIR_BATCH_R2",
     "docs/research/matrix-native-results/b649-c2-n2-equality-seven-pair-batch-r2-result.json",
     "777e182713dcd9a37f3e344adb653c623c8ea32bc8b5225872923db35e89834f"),
)
WALL, PAIR_WALL = 60.0, 15.0
RAW, EXCLUDED, LEGAL = 13983816, 18, 13983798
COVERAGE, OUTCOMES = 44751984, 313263888


def load_core(path=ROOT / CORE_REL, expected=CORE_SHA):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("frozen gain core SHA mismatch")
    spec = importlib.util.spec_from_file_location("r3_frozen_gain_core", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(data, str(path), "exec"), module.__dict__)
    # Input selection only; the verified gain/control/validation bytes stay intact.
    module.ALLOWLIST = (SPEC,)
    return module


core = load_core()


def stream_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prior_snapshot():
    snapshot = {}
    for task, rel, expected in PRIOR:
        for path in (ROOT / rel, ROOT.parent / task / rel):
            if not path.is_file() or stream_sha(path) != expected:
                raise ValueError("prior result missing/changed: " + str(path))
            snapshot[str(path)] = expected
        # Preserve the whole task-specific runtime surface, including locks and
        # checkpoints if present. No old writer/state is acquired or modified.
        runtime = ROOT.parent / task / ".task-data" / task
        snapshot[str(runtime)] = {str(p.relative_to(runtime)): stream_sha(p)
                                  for p in runtime.rglob("*") if p.is_file()} if runtime.exists() else None
    return snapshot


def validate_identity(identity):
    if (identity["PAIR_ORDERED"], identity["PAIR_ENGINE"], identity["ORBIT_INDEX"], identity["ORBIT_SIZE"]) != ([18, 19], [18, 19], 93, 1):
        raise ValueError("R3 only permits the single (18,19) orbit")
    if (core.sha(core.compact(identity["ORDERED_TICKETS"])) != ORDERED_SHA or
            identity["EXPECTED_COVERED_P_7_SET"] != COVERAGE or "C_ij" in identity):
        raise ValueError("C2 source/unit identity mismatch or preset C_ij")
    verified = core.pair_identity(identity["ORDERED_TICKETS"], identity["ENGINE_TICKETS"],
                                  identity["ORDERED_TO_ENGINE_SLOTS"], identity["PAIR_MAPPING_ROW"], SPEC)
    if (identity["REMOVED_TICKETS"] != REMOVED or
            verified["REMOVED_TICKETS"] != identity["REMOVED_TICKETS"] or
            verified["UNTOUCHED_TICKETS"] != identity["UNTOUCHED_TICKETS"]):
        raise ValueError("removed/18 untouched ticket values mismatch")


def load_inputs():
    identities, donor, provenance = core.load_inputs()
    if len(identities) != 1:
        raise ValueError("R3 must select exactly one pair")
    identity = identities[0]
    validate_identity(identity)
    if provenance["START"]["COUNT"] != OUTCOMES or COVERAGE * 7 != OUTCOMES:
        raise ValueError("source outcome/7_SET identity mismatch")
    return identity, donor, provenance


def measure_once(lib, folder, identity, pilot, batch_deadline, pair_deadline):
    validate_identity(identity)
    return core.measured_row(lib, folder, identity, pilot, batch_deadline, pair_deadline)


def encode(result):
    return json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def independent_reparse(data, original):
    """Rebuild all buckets and complements from bytes; never repeat gain work."""
    parsed = json.loads(data)
    if parsed != original:
        raise core.StopBatch("ARCHIVE_REPARSE_MISMATCH")
    if parsed["TASK_STATUS"] != "COMPLETE":
        if parsed["E"] is not None or parsed["EXACT_EQUALITY_PAIR_COUNT"] is not None:
            raise core.StopBatch("PARTIAL_E_MUST_BE_NULL")
        return "PARTIAL_NULL_E"
    row = parsed["PAIR_RESULT"]
    identity = parsed["PAIR_IDENTITY"]
    validate_identity(identity)
    if (any(row[k] != identity[k] for k in ("PAIR_ORDERED", "PAIR_ENGINE", "ENGINE_TICKETS", "ORDERED_TICKETS")) or
            row["REMOVED_TICKETS"] != REMOVED or
            sorted(row["UNTOUCHED_TICKETS"]) != sorted(identity["UNTOUCHED_TICKETS"])):
        raise core.StopBatch("ARCHIVE_TICKET_IDENTITY_MISMATCH")
    if (row["COUNTING_UNIT"] != "7_SET" or row["HISTOGRAM_COMPLETE"] is not True or
            row["STATUS"] != "COMPLETE" or row["ARTIFACT_COMPLETE"] is not True or
            (row["RAW_SINGLE_TICKETS"], row["EXCLUDED_UNTOUCHED_TICKETS"], row["LEGAL_SINGLE_TICKETS"]) != (RAW, EXCLUDED, LEGAL)):
        raise core.StopBatch("ARCHIVE_ACCOUNTING_MISMATCH")
    if any(type(row[k]) is not int for k in ("COVERED_P", "COVERED_R", "C_ij")):
        raise core.StopBatch("ARCHIVE_C_IJ_TYPE_MISMATCH")
    cij = row["COVERED_P"] - row["COVERED_R"]
    if row["COVERED_P"] != COVERAGE or cij < 0 or cij != row["C_ij"] or cij != parsed["C_ij"]:
        raise core.StopBatch("ARCHIVE_C_IJ_MISMATCH")
    h = {}
    previous = -1
    for gain, count in row["HISTOGRAM"]:
        if type(gain) is not int or type(count) is not int or gain <= previous or count <= 0:
            raise core.StopBatch("ARCHIVE_HISTOGRAM_MISMATCH")
        h[gain] = count
        previous = gain
    rebuilt = [[g, h[g]] for g in h]
    if sum(h.values()) != LEGAL or len(h) != row["BUCKET_COUNT"]:
        raise core.StopBatch("ARCHIVE_HISTOGRAM_TOTAL_MISMATCH")
    table = []
    exact = 0
    for a, n in h.items():
        b = cij - a
        if b < a or b not in h:
            continue
        contribution = n * h[b] if a < b else n * (n - 1) // 2
        exact += contribution
        table.append({"A": a, "B": b, "H_A": n, "H_B": h[b],
                      "RULE": "PRODUCT" if a < b else "CHOOSE_2_DISTINCT", "CONTRIBUTION": contribution})
    if (any(type(value) is not int for value in (row["E"], parsed["E"], parsed["EXACT_EQUALITY_PAIR_COUNT"])) or row["E"] != exact or
            parsed["E"] != exact or parsed["EXACT_EQUALITY_PAIR_COUNT"] != exact or
            table != row["COMPLEMENTARY_BUCKET_TABLE"] or
            core.sha(core.compact(rebuilt)) != row["HISTOGRAM_SHA256"] or
            core.sha(core.compact(table)) != row["COMPLEMENTARY_TABLE_SHA256"]):
        raise core.StopBatch("ARCHIVE_E_OR_SHA_MISMATCH")
    # Independently verified archive identity; compact round trip has no hidden
    # truncation or duplicate JSON keys emitted by this serializer.
    if encode(parsed) != data:
        raise core.StopBatch("ARCHIVE_COMPACT_MISMATCH")
    return "PASS"


def archive(result, path, folder, *, deadline=None, peaks=None,
            result_limit=core.RESULT_LIMIT, temp_limit=core.TEMP_LIMIT):
    data = encode(result)
    if len(data) > result_limit:
        raise core.StopBatch("RESULT_CAPACITY")
    scratch = Path(folder) / "seal.json"
    total = core.folder_bytes(folder) + len(data)
    if total > temp_limit:
        raise core.StopBatch("TEMP_CAPACITY")
    independent_reparse(data, result)
    if deadline is not None:
        core.check_limits(deadline, folder)
    with scratch.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if scratch.read_bytes() != data:
        raise core.StopBatch("ARCHIVE_READBACK_MISMATCH")
    os.replace(scratch, path)
    if Path(path).read_bytes() != data:
        raise core.StopBatch("ARCHIVE_READBACK_MISMATCH")
    if peaks is not None:
        peaks["RESULT"] = max(peaks["RESULT"], len(data))
        peaks["TEMP"] = max(peaks["TEMP"], total)
    if deadline is not None:
        core.check_limits(deadline, folder)
    return len(data)


def mark_partial(result, reason):
    result.update(TASK_STATUS="PARTIAL", STOP_REASON=reason, E=None,
                  EXACT_EQUALITY_PAIR_COUNT=None, INDEPENDENT_REPARSE_VERDICT="PARTIAL_NULL_E")
    if result.get("PAIR_RESULT"):
        result["PAIR_RESULT"].update(STATUS="INCOMPLETE", E=None, HISTOGRAM_COMPLETE=False,
                                     ARTIFACT_COMPLETE=False, HISTOGRAM=[], HISTOGRAM_SHA256=None,
                                     COMPLEMENTARY_BUCKET_TABLE=[], COMPLEMENTARY_TABLE_SHA256=None)


def main():
    started = time.monotonic()
    deadline = started + WALL
    if sys.argv[1:] != ["run"]:
        raise SystemExit("usage: b649_c2_n2_equality_last_pair_r3_r1.py run")
    if RESULT.exists():
        raise SystemExit("R3 execution already exists: retry/resume forbidden")
    expected = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
    if (str(ROOT) != expected or core.git("branch", "--show-current") != BRANCH or
            core.git("rev-parse", "HEAD") != BASE or core.git("rev-parse", "HEAD^{tree}") != BASE_TREE):
        raise SystemExit("exclusive R3 worktree/branch/base mismatch")
    before = prior_snapshot()
    result = {"TASK_ID": TASK_ID, "TASK_STATUS": "PARTIAL", "BASE_HEAD": BASE, "BASE_TREE": BASE_TREE,
              "EXECUTION_IDENTITY": TASK_ID + ":" + str(os.getpid()) + ":" + str(time.time_ns()),
              "EXECUTION_RELATION": "new R3 execution; R2 SHA-only read; no takeover/retry/resume",
              "ACTUAL_R3_ADAPTER_SHA256": core.sha(Path(__file__).read_bytes()), "GAIN_CORE_SHA256": CORE_SHA,
              "DONOR_SHA256": core.DONOR_SHA, "C2_ORDERED_SHA256": ORDERED_SHA,
              "COUNTING_UNIT": "7_SET", "SOURCE_COVERAGE_7SET": COVERAGE, "SOURCE_OUTCOME_COUNT": OUTCOMES,
              "PAIR_ORDERED": [18, 19], "PAIR_ENGINE": [18, 19], "REMOVED_TICKETS": REMOVED,
              "UNTOUCHED_TICKETS_VERIFIED": False, "C_ij": None, "E": None, "EXACT_EQUALITY_PAIR_COUNT": None,
              "PAIR_RESULT": None, "STOP_REASON": None, "INDEPENDENT_REPARSE_VERDICT": "NOT_RUN",
              "NATIVE_MEASUREMENT_CALLS": 0, "OTHER_PAIRS_REMEASURED": 0, "PAIR_OVERLAP_CALLS": 0,
              "CHECKER_CALLS": 0, "N2_SWEEP_CALLS": 0, "CP_SAT_CALLS": 0, "CANONICAL_SCORING_CALLS": 0,
              "EQUALITY_PAIRS_MATERIALIZED": 0, "R2_FULL_HISTOGRAM_OBJECTS_LOADED": 0,
              "RESOURCE_LIMITS": {"R3_WALL_SECONDS": WALL, "PAIR_WALL_SECONDS": PAIR_WALL,
                  "RSS_TARGET_BYTES": core.RSS_LIMIT, "RESULT_LIMIT_BYTES": core.RESULT_LIMIT,
                  "TEMP_LIMIT_BYTES": core.TEMP_LIMIT, "STOP_ARCHIVE_RESERVE_SECONDS": core.RESERVE},
              "PROCESS_MODEL": {"MEASUREMENT_PID": os.getpid(), "MEASUREMENT_PROCESSES": 1, "WORKERS": 1,
                  "COMPUTE_THREADS": 1, "INTERFACE": "unchanged ctypes.PyDLL; caller thread, GIL held"},
              "RESOURCE_ENFORCEMENT": {"STOP": "unchanged cooperative stop every 4096 N accesses and each output fragment",
                  "RSS": "512 MiB monitored stop target, NOT an OS hard limit; polling may overshoot",
                  "CAPACITY": "unchanged bounded native output; compact result/scratch size checks",
                  "LIMITATIONS": "cooperative polls do not hard-bound OS scheduling/IO stalls"},
              "REUSED_CORE_TEST_EVIDENCE": {"LOCATOR": BASE + ":" + PRIOR[0][1], "SHA256": PRIOR[0][2],
                  "FOCUSED_TESTS_PASS": 18, "RERUN": False, "PILOT_FOCUSED_TESTS_PASS": 16,
                  "PILOT_RESULT_SHA256": core.PILOT_RESULT_SHA, "GAIN_CORE_UNCHANGED": True},
              "HASH_CONVENTION": "SHA256 UTF-8 compact JSON ensure_ascii=True, no newline for histogram/table; file SHA includes trailing newline",
              "R1_R2_RESULT_IDENTITIES_UNCHANGED": False, "PRIOR_RESULT_AND_RUNTIME_SNAPSHOT": before,
              "RESULT_LOCATOR": str(RESULT), "AUTO_RETRY": False, "AUTO_RESUME": False,
              "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN", "REMAINING_TASK_MODEL": "最強模型 — 完成的E值之數學解讀",
              "SCIENTIFIC_SCOPE": "E=0 closes only orbit 93 (size 1); E>0 is not a proven tie. No extrapolation to 86 unmeasured representatives, strict gain or global optimum claim."}
    peaks = {"RESULT": 0, "TEMP": 0}
    pair_start = None
    pair_deadline = deadline
    with tempfile.TemporaryDirectory(prefix=TASK_ID + "-") as tmp:
        try:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=tmp,
                       OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
            command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/unit", "-p", TEST_NAME, "-v"]
            tests = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                   timeout=max(.001, deadline - core.RESERVE - time.monotonic()))
            print(tests.stderr, flush=True)
            count = re.search(r"Ran (\d+) tests", tests.stderr)
            result["FOCUSED_TEST_RESULTS"] = {"ARGV": command, "COUNT": int(count[1]) if count else 0,
                                               "PASS": tests.returncode == 0, "OUTPUT": tests.stderr.strip()}
            if tests.returncode or not count:
                raise core.StopBatch("FOCUSED_TESTS_FAILED")
            identity, donor, provenance = load_inputs()
            result.update(PAIR_IDENTITY=identity, UNTOUCHED_TICKETS_VERIFIED=True,
                          DONOR_AND_SOURCE_IDENTITIES=provenance)
            source, native_provenance = core.c_source(donor)
            result["ADAPTER_PROVENANCE"] = native_provenance
            result["GENERATED_C_SHA256"] = core.sha(source.encode())
            library, compile_command, temp_peak = core.compile_c(source, tmp, deadline - core.RESERVE)
            peaks["TEMP"] = max(peaks["TEMP"], temp_peak)
            result.update(COMPILE_COMMAND=compile_command, BINARY_SHA256=stream_sha(library))
            lib = core.native_library(library)
            pilot = core.pilot_namespace()
            if lib.native_pid() != os.getpid():
                raise core.StopBatch("MEASUREMENT_PROCESS_MISMATCH")
            now = time.monotonic()
            if not now - .001 <= lib.native_now() <= time.monotonic() + .001:
                raise core.StopBatch("NATIVE_CLOCK_MISMATCH")
            core.check_limits(deadline - core.RESERVE, tmp)
            pair_start = time.monotonic()
            pair_deadline = min(pair_start + PAIR_WALL, deadline - core.RESERVE)
            result["NATIVE_MEASUREMENT_CALLS"] = 1
            row = measure_once(lib, tmp, identity, pilot, deadline - core.RESERVE, pair_deadline)
            peaks["TEMP"] = max(peaks["TEMP"], row["TEMP_PEAK_BYTES"])
            result.update(PAIR_RESULT=row, C_ij=row["C_ij"], E=row["E"], EXACT_EQUALITY_PAIR_COUNT=row["E"],
                          TASK_STATUS="COMPLETE", INDEPENDENT_REPARSE_VERDICT="PASS")
            if prior_snapshot() != before:
                raise core.StopBatch("R1_R2_IDENTITY_CHANGED")
            core.pinned(ROOT / CORE_REL, CORE_SHA)
            core.pinned(provenance["DONOR_LOCATOR"], core.DONOR_SHA)
            result["R1_R2_RESULT_IDENTITIES_UNCHANGED"] = True
            independent_reparse(encode(result), result)
            core.check_limits(pair_deadline, tmp)
            result["PAIR_WALL_THROUGH_INDEPENDENT_REPARSE_SECONDS"] = time.monotonic() - pair_start
        except Exception as exc:
            if isinstance(exc, core.StopBatch):
                result["STOP_OBSERVATION"] = exc.observation
            mark_partial(result, str(exc))
        result["PEAK_RSS_BYTES"] = core.peak_memory()
        result["WALL_TIME_BEFORE_FINAL_SEAL_SECONDS"] = time.monotonic() - started
        result["WALL_TIMING_SCOPE"] = "entry through focused tests, identities, compiler, one native call and reparse; terminal wall additionally includes final seal/readback and temp cleanup"
        result["INDEPENDENT_REPARSE_SCOPE"] = "all archived buckets reconstructed, total and SHA recomputed; C_ij from covered_P-covered_R; independent integer complement products and choose-2; no gain remeasurement"
        for _ in range(3):
            size = len(encode(result))
            result["RESULT_PEAK_BYTES"] = max(peaks["RESULT"], size)
            result["TEMP_PEAK_BYTES"] = max(peaks["TEMP"], core.folder_bytes(tmp) + size)
        try:
            archive(result, RESULT, tmp, deadline=min(deadline, pair_deadline), peaks=peaks)
        except Exception as exc:
            mark_partial(result, str(exc))
            # Stop sealing is not another measurement or a budget extension.
            (Path(tmp) / "seal.json").unlink(missing_ok=True)
            archive(result, RESULT, tmp, peaks=peaks)
    print(json.dumps({"TASK_STATUS": result["TASK_STATUS"], "C_ij": result["C_ij"],
                      "EXACT_EQUALITY_PAIR_COUNT": result["EXACT_EQUALITY_PAIR_COUNT"],
                      "WALL_TIME_SECONDS": time.monotonic() - started, "PEAK_RSS_BYTES": core.peak_memory(),
                      "PAIR_WALL_THROUGH_FINAL_SEAL_SECONDS": time.monotonic() - pair_start if pair_start else None,
                      "RESULT_SHA256": stream_sha(RESULT), "RESULT_LOCATOR": str(RESULT)}), flush=True)


if __name__ == "__main__":
    main()
