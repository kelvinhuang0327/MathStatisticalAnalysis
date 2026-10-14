"""R2 execution of the corrected seven-pair equality histogram adapter.

The corrected R1 adapter bytes are executed verbatim (SHA pinned) and supply every
input, gain, validation and native resource control. This file adds only the R2
identity, its own result destination, a prelaunch 7_SET unit check through the
same validator, and the Owner-approved compact result serialization (indent=2
would exceed the 64 MiB temp cap at about six full histograms).
No retry/resume; the R1 result is read-only evidence and its values are not reused.
"""
from __future__ import annotations

import functools
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
TASK_ID = "B649_C2_N2_EQUALITY_SEVEN_PAIR_BATCH_R2"
BRANCH = "codex/b649-c2-n2-equality-seven-pair-batch-r2"
R2_BASE = "669f2099f2166833cc1c2ed9280f3aca3608e2cb"
R2_BASE_TREE = "8262c8e36dc6ed43dff363f779812d76759d0b59"
CORE_REL = "tools/b649_c2_n2_equality_seven_pair_batch_r1.py"
CORE_SHA = "9124c1f8ac6b071cc58978a81120efc7959bfde508b2a8e9e272e497563bfc05"
R1_RESULT_REL = "docs/research/matrix-native-results/b649-c2-n2-equality-seven-pair-batch-r1-result.json"
R1_RESULT_SHA = "9a23ebf7fd01cc829c4de8f71eaae4fdf846d8b87f869bed079969b551175922"
R1_MEASUREMENT_ADAPTER_SHA = "95ec48b21e02170491764e6fcc86c37fb64a98d718ad67f6dcf2fd854c2f55af"
R1_GENERATED_C_SHA = "55b9a80fbdc2cca13985c88e6ddfbb1b48242b7346188e922c8f8215e8149855"
RESULT_REL = "docs/research/matrix-native-results/b649-c2-n2-equality-seven-pair-batch-r2-result.json"
RESULT = ROOT / RESULT_REL
TEST_NAME = "test_b649_c2_n2_equality_seven_pair_batch_r2.py"
SOURCE_COVERAGE_7SET, SOURCE_OUTCOME_COUNT, SET_SIZE = 44751984, 313263888, 7
SERIALIZATION = "compact JSON separators=(',',':'), ensure_ascii=False, trailing newline"


def load_core(path=ROOT / CORE_REL, expected=CORE_SHA):
    data = Path(path).read_bytes()
    if __import__("hashlib").sha256(data).hexdigest() != expected:
        raise ValueError("corrected adapter SHA mismatch")
    spec = importlib.util.spec_from_file_location("seven_pair_core", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(data, str(path), "exec"), module.__dict__)  # exactly the verified bytes
    return module


core = load_core()


def encode(result) -> bytes:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


@functools.cache
def equality_count():
    return core.pilot_namespace()["equality_count"]


def verify_reparsed(data, result):
    # Compact bytes must reparse to the same histogram, table, C_ij and E; E/SHAs recomputed from the bytes.
    parsed = json.loads(data)
    for row, back in zip(result["SEVEN_PAIRS"], parsed["SEVEN_PAIRS"], strict=True):
        if row["STATUS"] != "COMPLETE":
            continue
        exact, table = equality_count()(back["HISTOGRAM"], back["C_ij"], complete=back["HISTOGRAM_COMPLETE"])
        if (back["HISTOGRAM"] != row["HISTOGRAM"] or back["COMPLEMENTARY_BUCKET_TABLE"] != row["COMPLEMENTARY_BUCKET_TABLE"] or
                back["C_ij"] != row["C_ij"] or back["E"] != row["E"] or exact != back["E"] or
                table != back["COMPLEMENTARY_BUCKET_TABLE"] or
                core.sha(core.compact(back["HISTOGRAM"])) != row["HISTOGRAM_SHA256"] or
                core.sha(core.compact(table)) != row["COMPLEMENTARY_TABLE_SHA256"]):
            raise core.StopBatch("ARCHIVE_REPARSE_MISMATCH")


def archive(result, path, folder, *, result_limit=core.RESULT_LIMIT, temp_limit=core.TEMP_LIMIT, deadline=None, peaks=None):
    # core.archive with the serializer replaced and a reparse check; same caps, scratch, fsync and readback.
    data = encode(result)
    if len(data) > result_limit:
        raise core.StopBatch("RESULT_CAPACITY")
    scratch = Path(folder)/"seal.json"
    scratch_peak = core.folder_bytes(folder) + len(data)
    if scratch_peak > temp_limit:
        raise core.StopBatch("TEMP_CAPACITY")
    verify_reparsed(data, result)
    if deadline is not None:
        core.check_limits(deadline, folder)
    with scratch.open("xb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    if peaks is not None:
        peaks["RESULT"] = max(peaks["RESULT"], len(data))
        peaks["TEMP"] = max(peaks["TEMP"], scratch_peak)
    if scratch.read_bytes() != data:
        raise core.StopBatch("ARCHIVE_READBACK_MISMATCH")
    os.replace(scratch, path)
    with Path(path).open("rb") as f:
        if f.read() != data:
            raise core.StopBatch("ARCHIVE_READBACK_MISMATCH")
    if deadline is not None:
        core.check_limits(deadline, folder)
    return len(data)


def r1_preserved() -> dict:
    data = (ROOT / R1_RESULT_REL).read_bytes()
    if core.sha(data) != R1_RESULT_SHA or data != core.blob(R2_BASE + ":" + R1_RESULT_REL, R1_RESULT_SHA):
        raise ValueError("R1 result changed")
    r1 = json.loads(data)
    if (r1["TASK_STATUS"] != "PARTIAL" or r1["COMPLETED_REPRESENTATIVES"] != 0 or
            r1["MEASUREMENT_ADAPTER_SHA256"] != R1_MEASUREMENT_ADAPTER_SHA or
            any(row["E"] is not None for row in r1["SEVEN_PAIRS"])):
        raise ValueError("R1 failure record mismatch")
    return {"LOCATOR": R2_BASE + ":" + R1_RESULT_REL, "SHA256": R1_RESULT_SHA, "STATUS": "PARTIAL",
            "COMPLETED_REPRESENTATIVES": 0, "ALL_E_NULL": True, "STOP_REASON": r1["STOP_REASON"],
            "MEASUREMENT_ADAPTER_SHA256": R1_MEASUREMENT_ADAPTER_SHA, "PRESERVED_UNCHANGED": True,
            "VALUES_REUSED_IN_R2": False}


def unit_precheck(identities) -> dict:
    """Corrected validator on fixtures only; runs before any real native gain call."""
    pilot = json.loads(core.blob(core.BASE + ":" + core.PILOT_RESULT, core.PILOT_RESULT_SHA))
    sealed = json.loads(core.blob(core.N2 + ":" + core.SEALED, core.SEALED_SHA))
    coverage, outcomes = pilot["COVERED_P"], sealed["START"]["CANONICAL_RECOUNT"]
    if (pilot["COUNTING_UNIT"] != "7_SET" or coverage != SOURCE_COVERAGE_7SET or
            outcomes != SOURCE_OUTCOME_COUNT or coverage * SET_SIZE != outcomes):
        raise ValueError("source coverage/outcome unit identity mismatch")
    if any(i["EXPECTED_COVERED_P_7_SET"] != coverage or "C_ij" in i for i in identities):
        raise ValueError("pair identity carries a non-7_SET source or a preset C_ij")
    cases = []

    def case(name, data, identity, accept):
        try:
            core.validate_source_coverage(data, identity)
            accepted = True
        except ValueError:
            accepted = False
        cases.append({"CASE": name, "EXPECTED": "ACCEPT" if accept else "REJECT",
                      "OBSERVED": "ACCEPT" if accepted else "REJECT", "PASS": accepted == accept})
        if accepted != accept:
            raise ValueError("unit precheck failed: " + name)

    identity = identities[0]
    real = {k: pilot[k] for k in ("COVERED_P", "COVERED_R", "C_ij")}
    own = {"COVERED_P": coverage, "COVERED_R": coverage - 1, "C_ij": 1}  # pair-own C_ij != pilot C_ij
    case("PILOT_7_SET_SOURCE_ACCEPTED", real, identity, True)
    case("PAIR_OWN_C_IJ_ACCEPTED", own, identity, True)
    case("OUTCOME_COUNT_AS_7_SET_DATA_REJECTED", {"COVERED_P": outcomes, "COVERED_R": outcomes - 1, "C_ij": 1}, identity, False)
    case("OUTCOME_COUNT_AS_7_SET_REFERENCE_REJECTED", own, {**identity, "EXPECTED_COVERED_P_7_SET": outcomes}, False)
    case("PILOT_C_IJ_ON_OTHER_PAIR_DATA_REJECTED", {**own, "C_ij": pilot["C_ij"]}, identity, False)
    case("C_IJ_SCALED_BY_7_REJECTED", {**own, "C_ij": own["C_ij"] * SET_SIZE}, identity, False)
    return {"SOURCE_COVERAGE_7SET": coverage, "SOURCE_COVERAGE_LOCATOR": core.BASE + ":" + core.PILOT_RESULT,
            "SOURCE_OUTCOME_COUNT": outcomes, "SOURCE_OUTCOME_LOCATOR": core.N2 + ":" + core.SEALED + "#START.CANONICAL_RECOUNT",
            "IDENTITY": "44751984 x 7 = 313263888", "VALIDATOR": "core.validate_source_coverage (corrected adapter, unchanged)",
            "PER_PAIR_C_ij": "from each pair's native COVERED_P-COVERED_R; no pilot C_ij preset", "CASES": cases,
            "REAL_NATIVE_GAIN_CALLS_BEFORE_PRECHECK": 0, "EVALUATOR_CALLS": 0}


def main():
    if sys.argv[1:] != ["run"]:
        raise SystemExit("usage: b649_c2_n2_equality_seven_pair_batch_r2.py run")
    if RESULT.exists():
        raise SystemExit("result exists: retry/resume forbidden")
    expected = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
    if str(ROOT) != expected or core.git("branch", "--show-current") != BRANCH:
        raise SystemExit("exclusive worktree/branch mismatch")
    if core.git("rev-parse", R2_BASE + "^{tree}") != R2_BASE_TREE:
        raise SystemExit("R2 base tree mismatch")
    r1 = r1_preserved()
    # Focused R2 tests precede, and are separately timed from, the batch.
    development_start = time.monotonic()
    test_command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/unit", "-p", TEST_NAME, "-v"]
    tests = subprocess.run(test_command, cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    print(tests.stderr, flush=True)
    development_wall = time.monotonic()-development_start
    test_count_match = re.search(r"Ran (\d+) tests", tests.stderr)
    result = {"TASK_ID": TASK_ID, "TASK_STATUS": "BLOCKED_PRELAUNCH", "BASE_HEAD": R2_BASE, "BASE_TREE": R2_BASE_TREE,
              "IMMUTABLE_INPUT_BASE": {"HEAD": core.BASE, "TREE": core.BASE_TREE},
              "SOURCE_HEAD": core.git("rev-parse", "HEAD"), "SOURCE_TREE": core.git("rev-parse", "HEAD^{tree}"),
              "MEASUREMENT_ADAPTER_SHA256": core.sha(Path(__file__).read_bytes()),
              "CORE_ADAPTER": {"PATH": CORE_REL, "SHA256": CORE_SHA, "EXECUTED_VERBATIM": True},
              "EXECUTION_RELATION": "new R2 execution under its own Packet; not an automatic retry/resume of R1",
              "R1_RESULT": r1, "PRIOR_R2_RESULT_PRESENT_AT_LAUNCH": False,
              "RESULT_SERIALIZATION": {"FORMAT": SERIALIZATION, "OWNER_APPROVED_DELTA": "indent=2 replaced by compact JSON; gain core, E formula, 7_SET unit, domain, hash convention and limits unchanged",
                                       "REASON": "pilot histogram at seven-pair depth is 12.1 MiB/pair with indent=2 (~84.8 MiB for 7) > 64 MiB temp cap",
                                       "PER_PAIR_SEAL": "every archive (initial, per pair, final) encodes compact bytes directly; no indented intermediate exists",
                                       "REPARSE_CHECK": "before each write: compact bytes reparsed; HISTOGRAM, table, C_ij, E equal; E/table recomputed and SHAs recomputed from reparsed values",
                                       "RESULT_FILE_SHA": "computed from the sealed file bytes after the final readback"},
              "COUNTING_UNIT": "7_SET", "SEVEN_PAIRS": [core.empty_row({"PAIR_ORDERED": list(s[0]), "PAIR_ENGINE": list(s[1]), "ORBIT_INDEX": s[2], "ORBIT_SIZE": s[3]}) for s in core.ALLOWLIST],
              "RESOURCE_LIMITS": {"BATCH_WALL_SECONDS": core.BATCH_WALL, "PAIR_WALL_SECONDS": core.PAIR_WALL, "STOP_ARCHIVE_RESERVE_SECONDS": core.RESERVE,
                                  "RSS_TARGET_BYTES": core.RSS_LIMIT, "RESULT_LIMIT_BYTES": core.RESULT_LIMIT, "TEMP_LIMIT_BYTES": core.TEMP_LIMIT},
              "NATIVE_CALL_AND_PROCESS_MODEL": {"MEASUREMENT_PID": os.getpid(), "PROCESSES": 1, "WORKERS": 1, "COMPUTATION_THREADS": 1,
                                               "INTERFACE": "ctypes.PyDLL; native histogram in caller thread, GIL held; compiler subprocess only during preparation"},
              "RESOURCE_ENFORCEMENT_CAPABILITIES_AND_LIMITATIONS": {"NATIVE_STOP": "cooperative control every 4096 N accesses and every output fragment; C longjmp to wrapper, full cleanup",
                  "RSS": "current resident bytes via mach_task_basic_info on macOS; monitored target, NOT OS hard limit; polling can overshoot",
                  "CAPACITY": "bounded native output before each write; aggregate OS-temp monitor in preparation; exact full result/scratch size checked before sealing",
                  "LIMITATIONS": "cooperative polling cannot hard-bound OS scheduling/IO stalls; compiler aggregate temp check may overshoot between polls (20ms plus ps query); Python verification checks deadlines between bounded stages"},
              "HASH_CONVENTION": "SHA256 UTF-8 json.dumps(value,separators=(',',':'),ensure_ascii=True); histogram sorted by unique integer gain, positive integer counts; table ascending A; missing buckets zero",
              "FOCUSED_TEST_COMMAND_AND_COUNTS": {"ARGV": test_command, "TESTS": int(test_count_match[1]) if test_count_match else 0, "PASS": tests.returncode == 0, "OUTPUT": tests.stderr.strip()},
              "DEVELOPMENT_FOCUSED_TEST_WALL_SECONDS": development_wall, "STOP_REASON": None,
              "PILOT_(0,1)_REMEASURED": "NO", "EQUALITY_PAIRS_MATERIALIZED": 0, "PAIR_OVERLAP_CALLS": 0, "N2_PAIR_SWEEP_CALLS": 0,
              "CHECKER_CALLS": 0, "CP_SAT_CALLS": 0, "CANONICAL_SCORING_CALLS": 0,
              "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN", "REMAINING_TASK_MODEL": {"最強模型": "histogram科學解讀", "強模型": "僅固定程式或執行契約缺陷"},
              "SCIENTIFIC_SCOPE": "E>0 means equality candidates only, not a proven tie. E=0 closes only the selected representative and its verified orbit equality boundary. No success-rate gain or global optimum claimed.",
              "RESULT_LOCATOR": str(RESULT), "RUNTIME_TRANSITION_OCCURRED": "NO", "ATTEMPTS_PER_PAIR": 1, "AUTO_RETRY": False, "AUTO_RESUME": False}
    batch_start = time.monotonic()
    deadline = batch_start+core.BATCH_WALL
    temp_peak = 0
    peaks = {"RESULT": 0, "TEMP": 0}
    current = None
    with tempfile.TemporaryDirectory(prefix=TASK_ID+"-") as tmp:
        try:
            if tests.returncode:
                raise core.StopBatch("FOCUSED_CAPABILITY_TESTS_FAILED")
            identities, donor, dependencies = core.load_inputs()
            result["DONOR_AND_DEPENDENCY_IDENTITIES"] = dependencies
            result["SEVEN_PAIRS"] = [core.empty_row(i) for i in identities]
            result["UNIT_PRECHECK"] = unit_precheck(identities)
            source, provenance = core.c_source(donor)
            result["ADAPTER_PROVENANCE"] = provenance
            library, command, temp_peak = core.compile_c(source, tmp, deadline-core.RESERVE)
            result["COMPILE_COMMAND"] = command
            result["GENERATED_C_SHA256"] = core.sha(source.encode())
            result["GENERATED_C_MATCHES_R1"] = result["GENERATED_C_SHA256"] == R1_GENERATED_C_SHA
            result["BINARY_SHA256"] = core.sha(library.read_bytes())
            lib = core.native_library(library)
            result["SYNTHETIC_CAPABILITY_OBSERVATIONS"] = core.synthetic_capabilities(lib, tmp)
            pilot = core.pilot_namespace()
            result["TASK_STATUS"] = "PARTIAL"
            archive(result, RESULT, tmp, peaks=peaks)
            for i, identity in enumerate(identities):
                core.check_limits(deadline-core.RESERVE, tmp)
                current = i
                pair_start = time.monotonic()
                pair_deadline = min(pair_start+core.PAIR_WALL, deadline-core.RESERVE)
                row = core.measured_row(lib, tmp, identity, pilot, deadline-core.RESERVE, pair_deadline)
                temp_peak = max(temp_peak, row["TEMP_PEAK_BYTES"])
                core.check_limits(pair_deadline, tmp)
                candidate = {**result, "SEVEN_PAIRS": list(result["SEVEN_PAIRS"])}
                candidate["SEVEN_PAIRS"][i] = row
                candidate["TASK_STATUS"] = "COMPLETE" if i == 6 else "PARTIAL"
                archive(candidate, RESULT, tmp, deadline=pair_deadline, peaks=peaks)
                row["PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS"] = time.monotonic()-pair_start
                result = candidate
                current = None
                print(json.dumps({"PAIR_ORDERED": row["PAIR_ORDERED"], "STATUS": row["STATUS"], "C_ij": row["C_ij"], "E": row["E"], "ELAPSED_SECONDS": row["ELAPSED_SECONDS"]}), flush=True)
            core.load_inputs()  # immutable/sealed inputs must remain identical
            r1_preserved()
            core.check_limits(deadline, tmp)
        except Exception as exc:
            if result["TASK_STATUS"] == "BLOCKED_PRELAUNCH":
                result["STOP_REASON"] = str(exc)
            else:
                if current is not None and isinstance(exc, core.StopBatch):
                    result["SEVEN_PAIRS"][current].update(exc.observation)
                    temp_peak = max(temp_peak, exc.observation.get("TEMP_PEAK_BYTES", 0))
                core.mark_partial(result, current, str(exc))
            print("STOP", str(exc), flush=True)
        result["COMPLETED_REPRESENTATIVES"] = sum(r["STATUS"] == "COMPLETE" for r in result["SEVEN_PAIRS"])
        result["COVERED_ORIGINAL_PAIRS"] = sum(r["ORBIT_SIZE"] for r in result["SEVEN_PAIRS"] if r["STATUS"] == "COMPLETE")
        temp_peak = max(temp_peak, core.folder_bytes(tmp))
        result["RESULT_PEAK_BYTES"] = peaks["RESULT"]
        result["TEMP_PEAK_BYTES"] = max(temp_peak, peaks["TEMP"])
        result["PROCESS_PEAK_MEMORY_BYTES"] = core.peak_memory()
        result["BATCH_WALL_SECONDS"] = time.monotonic()-batch_start
        result["BATCH_WALL_TIMING_SCOPE"] = "artifact timer sampled before final seal; terminal summary includes final seal/readback and OS-temp cleanup"
        result["TEMP_PEAK_SCOPE"] = "native file and seal scratch sizes accounted exactly; compiler temporary peak sampled between polls"
        # Solve metadata size accounting before writing the final artifact.
        for _ in range(4):
            size = len(encode(result))
            result["RESULT_PEAK_BYTES"] = max(result["RESULT_PEAK_BYTES"], size)
            result["TEMP_PEAK_BYTES"] = max(result["TEMP_PEAK_BYTES"], core.folder_bytes(tmp)+size)
        try:
            archive(result, RESULT, tmp, deadline=deadline, peaks=peaks)
        except core.StopBatch as exc:
            core.mark_partial(result, None, str(exc))
            archive(result, RESULT, tmp, peaks=peaks)
    print(json.dumps({"TASK_STATUS": result["TASK_STATUS"], "COMPLETED_REPRESENTATIVES": result["COMPLETED_REPRESENTATIVES"], "COVERED_ORIGINAL_PAIRS": result["COVERED_ORIGINAL_PAIRS"], "BATCH_WALL_SECONDS": time.monotonic()-batch_start, "RESULT_SHA256": core.sha(RESULT.read_bytes())}), flush=True)


if __name__ == "__main__":
    main()
