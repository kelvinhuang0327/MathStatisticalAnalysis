"""Seven fixed equality histograms; frozen pilot core, one in-process native call.

No retry/resume or two-ticket evaluation. Generated library lives in OS temp.
Native cancellation uses cooperative scalar-access/IO checks and C longjmp,
not a Python elapsed check after an uninterruptible call or a measurement child.
"""
from __future__ import annotations

import ast
import ctypes
import hashlib
import json
import math
import os
import re
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "B649_C2_N2_EQUALITY_SEVEN_PAIR_BATCH_R1"
BASE = "334a52ea9ea584221ab9c5449e13265bf44f31d2"
BASE_TREE = "235828261c6e56c367518e32c16927f057b0016d"
N2 = "0ba102858c9d5156b759a172fe0ab0fad01ab8c0"
PILOT = "tools/b649_c2_n2_equality_histogram_pilot_r1.py"
PILOT_SHA = "4d8a1f02281f119768e2de0dd720511e2216536d20c4136137de1d30f38a5ff7"
PILOT_RESULT = "docs/research/matrix-native-results/b649-c2-n2-equality-histogram-pilot-r1-result.json"
PILOT_RESULT_SHA = "65477969003be8fbcc7567343301616f0b7e2c9610de7dcc66368b781506fd42"
SEALED = "docs/research/matrix-native-results/b649-k20-c2-orbit-reduced-exact-n2-r1-result.json"
SEALED_SHA = "daf6dae3bd177903cf352ff0087c5a66f3232751eaf935244e2537698d20653d"
CONTRACT_SHA = "1b75a9e3fdf624d43ab0886eecf426fdcf9e6599b6282b3e651606100a53edb2"
DONOR_SHA = "ed7c88467a56648c6587aadbbce6b23bc419c9218f840405238019ac7286d4fa"
RESULT_REL = "docs/research/matrix-native-results/b649-c2-n2-equality-seven-pair-batch-r1-result.json"
RESULT = ROOT / RESULT_REL
TEST_NAME = "test_b649_c2_n2_equality_seven_pair_batch_r1.py"
ALLOWLIST = (
    ((0, 6), (0, 11), 5, 1), ((0, 12), (0, 12), 11, 6),
    ((0, 18), (0, 18), 12, 2), ((12, 13), (12, 13), 90, 6),
    ((12, 15), (12, 15), 91, 9), ((12, 18), (12, 18), 92, 12),
    ((18, 19), (18, 19), 93, 1),
)
BATCH_WALL, PAIR_WALL, RESERVE = 120.0, 15.0, 5.0
RSS_LIMIT, RESULT_LIMIT, TEMP_LIMIT = 512 << 20, 128 << 20, 64 << 20
STOP_CODES = {1: "PAIR_DEADLINE", 2: "BATCH_DEADLINE", 3: "RSS_TARGET", 4: "OUTPUT_CAPACITY", 5: "NATIVE_ERROR"}
FORBIDDEN = ("pair-overlap", "N2-pair-sweep", "checker", "CP-SAT", "canonical-portfolio-evaluator")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(value) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()


def git(*args, timeout=10) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=timeout).strip()


def blob(locator: str, expected: str) -> bytes:
    data = subprocess.check_output(["git", "show", locator], cwd=ROOT, timeout=10)
    if sha(data) != expected:
        raise ValueError("immutable blob SHA mismatch: " + locator)
    return data


def pinned(path: str, expected: str) -> bytes:
    data = Path(path).read_bytes()
    if sha(data) != expected:
        raise ValueError("source SHA mismatch: " + path)
    return data


def pilot_namespace() -> dict:
    # Reuse only these immutable definitions; do not import/execute the N2 driver.
    source = blob(BASE + ":" + PILOT, PILOT_SHA)
    names = {"C_HEADER", "C_MAIN", "c_source", "equality_count", "input_text", "validate_measurement"}
    tree = ast.parse(source)
    nodes = [n for n in tree.body if
             (isinstance(n, ast.FunctionDef) and n.name in names) or
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))]
    namespace = {"sha": sha, "math": math, "DONOR_SHA": DONOR_SHA}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), PILOT, "exec"), namespace)
    return namespace


def pair_identity(ordered, engine, slots, row, spec) -> dict:
    pair, expected_engine, index, size = spec
    if list(slots) != [engine.index(t) for t in ordered] or engine != sorted(ordered):
        raise ValueError("by-value normalization mismatch")
    actual = sorted(slots[i] for i in pair)
    if actual != list(expected_engine):
        raise ValueError("ordered-to-engine pair mismatch")
    if (row["ORDERED_PAIR"] != list(pair) or row["ENGINE_PAIR"] != actual or
        row["ORBIT_INDEX"] != index or row["ORBIT_SIZE"] != size or
        row["IS_REPRESENTATIVE"] is not True or
        row["REPRESENTATIVE_ORDERED_PAIR"] != list(pair) or
        row["REPRESENTATIVE_ENGINE_PAIR"] != actual):
        raise ValueError("full mapping row identity mismatch")
    removed = [ordered[i] for i in pair]
    untouched = [t for i, t in enumerate(ordered) if i not in pair]
    if len(untouched) != 18 or sorted(engine[i] for i in actual) != sorted(removed) or sorted(
        t for i, t in enumerate(engine) if i not in actual) != sorted(untouched):
        raise ValueError("removed/18 untouched values mismatch")
    return {"PAIR_ORDERED": list(pair), "PAIR_ENGINE": actual, "ORBIT_INDEX": index,
            "ORBIT_SIZE": size, "PAIR_MAPPING_ROW": row, "ORDERED_TO_ENGINE_SLOTS": slots,
            "ORDERED_TICKETS": ordered, "ENGINE_TICKETS": engine,
            "REMOVED_TICKETS": removed, "UNTOUCHED_TICKETS": untouched}


def load_inputs():
    if git("config", "--get", "remote.origin.url") != "https://github.com/kelvinhuang0327/MathStatisticalAnalysis.git":
        raise ValueError("exact repository mismatch")
    if git("rev-parse", BASE + "^{tree}") != BASE_TREE:
        raise ValueError("base tree mismatch")
    blob(BASE + ":" + PILOT, PILOT_SHA)
    pilot_result = json.loads(blob(BASE + ":" + PILOT_RESULT, PILOT_RESULT_SHA))
    if pilot_result["COUNTING_UNIT"] != "7_SET":
        raise ValueError("pilot coverage reference is not in 7-set units")
    sealed = json.loads(blob(N2 + ":" + SEALED, SEALED_SHA))
    contract_path = sealed["RUN_LOCATORS"]["CONTRACT"]
    if sealed["ENGINE_AUTHORITY"]["CONTRACT_SHA256"] != CONTRACT_SHA:
        raise ValueError("N2 contract binding mismatch")
    contract = json.loads(pinned(contract_path, CONTRACT_SHA))
    donor = pinned(contract["ENGINE"]["SOURCE_PATH"], DONOR_SHA).decode()
    if contract["ENGINE"]["SOURCE_SHA256"] != DONOR_SHA:
        raise ValueError("donor contract binding mismatch")
    pinned(contract["ENGINE"]["BINARY_PATH"], contract["ENGINE"]["BINARY_SHA256"])
    dependencies = {}
    for key in ("ORBIT_MODULE", "EVALUATOR"):
        entry = contract[key]
        blob(BASE + ":" + entry["PATH"], entry["SHA256"])
        dependencies[key] = {**entry, "LOCATOR": BASE + ":" + entry["PATH"], "EXECUTED": False}
    start = contract["START"]
    ordered = json.loads(blob(start["LOCATOR"], start["FILE_SHA256"]))["C2"]["full_portfolio"]
    if sha(compact(ordered)) != start["ORDERED_SHA256"] or sha(compact(sorted(ordered))) != start["SORTED_SHA256"]:
        raise ValueError("20-ticket source identity mismatch")
    mf = contract["ORBIT"]["MAPPING_FILE"]
    mapping = json.loads(pinned(mf["PATH"], mf["SHA256"]))
    if (mapping["ORDERED_TICKETS"] != ordered or len(mapping["ROWS"]) != 190 or
        sha(compact(mapping["ROWS"])) != contract["ORBIT"]["MAPPING_SHA256"]):
        raise ValueError("sealed mapping/ROWS mismatch")
    identities = [pair_identity(ordered, mapping["ENGINE_TICKETS"], mapping["ORDERED_TO_ENGINE_SLOTS"],
                  next(r for r in mapping["ROWS"] if r["ORDERED_PAIR"] == list(spec[0])), spec) for spec in ALLOWLIST]
    for identity in identities:
        identity["EXPECTED_COVERED_P_7_SET"] = pilot_result["COVERED_P"]
    # Recheck the sealed number/slot witnesses only for the seven selected orbits.
    for identity in identities:
        orbit_rows = [r for r in mapping["ROWS"] if r["ORBIT_INDEX"] == identity["ORBIT_INDEX"]]
        if len(orbit_rows) != identity["ORBIT_SIZE"]:
            raise ValueError("orbit cardinality mismatch")
        for r in orbit_rows:
            slots, numbers = r["WITNESS_SLOTS"], r["WITNESS_NUMBERS"]
            if sorted(slots) != list(range(20)) or sorted(numbers) != list(range(1, 50)):
                raise ValueError("orbit witness is not a permutation")
            if any(sorted(numbers[n-1] for n in t) != ordered[slots[i]] for i, t in enumerate(ordered)):
                raise ValueError("orbit witness does not preserve the 20 tickets")
            if sorted(slots[i] for i in r["ORDERED_PAIR"]) != identity["PAIR_ORDERED"]:
                raise ValueError("orbit witness does not map to selected representative")
        identity["COVERED_ORIGINAL_PAIRS"] = [r["ORDERED_PAIR"] for r in orbit_rows]
    provenance = {"DONOR_LOCATOR": contract["ENGINE"]["SOURCE_PATH"], "DONOR_SHA256": DONOR_SHA,
                  "ORIGINAL_BINARY": contract["ENGINE"], "CONTRACT_LOCATOR": contract_path,
                  "CONTRACT_SHA256": CONTRACT_SHA, "N2_RESULT_LOCATOR": N2 + ":" + SEALED,
                  "N2_RESULT_SHA256": SEALED_SHA, "PILOT_SHA256": PILOT_SHA,
                  "PILOT_RESULT_SHA256": PILOT_RESULT_SHA, "START": start,
                  "MAPPING_FILE": mf, "MAPPING_ROWS_SHA256": contract["ORBIT"]["MAPPING_SHA256"],
                  "DEPENDENCIES": dependencies}
    return identities, donor, provenance


C_CONTROL = r"""
#include <setjmp.h>
#include <stdarg.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach/mach.h>
#endif
static jmp_buf STOP;
static FILE *INPUT, *OUTPUT;
static double pair_end, batch_end, last_poll, max_gap, stop_latency;
static uint64_t rss_cap, output_cap, emitted, peak_rss, ticks;
static int stop_code;
static char reason[256];
static unsigned char *probe_memory;
static uint64_t current_rss(void) {
#ifdef __APPLE__
    mach_task_basic_info_data_t info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &count) != KERN_SUCCESS)
        return UINT64_MAX;
    return info.resident_size;
#else
    FILE *f=fopen("/proc/self/statm","r"); unsigned long pages, resident;
    if (!f || fscanf(f,"%lu %lu",&pages,&resident)!=2) { if(f) fclose(f); return UINT64_MAX; }
    fclose(f); return (uint64_t)resident * (uint64_t)sysconf(_SC_PAGESIZE);
#endif
}
static void fail(int code, const char *msg) {
    stop_code=code; snprintf(reason,sizeof(reason),"%s",msg); longjmp(STOP,1);
}
static void die(const char *msg) { fail(5,msg); }
static void poll_control(void) {
    double t=now_s();
    if(t-last_poll>max_gap) max_gap=t-last_poll;
    last_poll=t;
    uint64_t rss=current_rss(); if(rss>peak_rss) peak_rss=rss;
    if(t>=batch_end) { stop_latency=t-batch_end; fail(2,"BATCH_DEADLINE"); }
    if(t>=pair_end) { stop_latency=t-pair_end; fail(1,"PAIR_DEADLINE"); }
    if(rss>rss_cap) { stop_latency=max_gap; fail(3,"RSS_TARGET"); }
}
/* Donor text is byte-identical. This scalar lvalue accessor adds control polls
   at every 4096 reads/writes of N, including a6, a5, lower tables and sweep. */
static int *checked_n(void) { if((++ticks & 4095)==0) poll_control(); return &N; }
#define N (*checked_n())
static int bounded_printf(const char *fmt, ...) {
    poll_control(); char buffer[1024]; va_list ap; va_start(ap,fmt);
    int len=vsnprintf(buffer,sizeof(buffer),fmt,ap); va_end(ap);
    if(len<0 || (size_t)len>=sizeof(buffer)) die("formatted fragment exceeds buffer");
    if(emitted+(uint64_t)len>output_cap) fail(4,"OUTPUT_CAPACITY");
    if(fwrite(buffer,1,(size_t)len,OUTPUT)!=(size_t)len) die("output write failed");
    emitted+=(uint64_t)len; return len;
}
"""

C_EXPORTS = r"""
#undef N
static void clear_state(void) {
    free(A3);free(A4);free(A5);free(A6);free(H);free(IS_R);free(SINGLE_GAINS);free(probe_memory);
    A3=A4=A5=A6=NULL; H=SINGLE_GAINS=NULL; IS_R=NULL; probe_memory=NULL;
    N=NB=0; N3=N4=N5=N6=N7=raw=excluded=gain_bound=0;
    memset(BM,0,sizeof(BM));memset(BIN,0,sizeof(BIN));
    if(INPUT) fclose(INPUT); if(OUTPUT) fclose(OUTPUT); INPUT=OUTPUT=NULL;
}
int native_state_zero(void) { return !A3&&!A4&&!A5&&!A6&&!H&&!IS_R&&!SINGLE_GAINS&&!NB&&!raw&&!excluded&&!N&&!probe_memory; }
uint64_t native_rss(void) { return current_rss(); }
uint64_t native_peak_rss(void) { return peak_rss; }
double native_max_poll_gap(void) { return max_gap; }
double native_stop_latency(void) { return stop_latency; }
double native_now(void) { return now_s(); }
const char *native_reason(void) { return reason; }
int native_pid(void) { return (int)getpid(); }
static void setup(double pe,double be,uint64_t rc,uint64_t oc) {
    clear_state(); pair_end=pe;batch_end=be;rss_cap=rc;output_cap=oc;
    emitted=ticks=peak_rss=0; stop_code=0; reason[0]=0;
    last_poll=now_s();max_gap=stop_latency=0;
}
int native_histogram(const char *in, const char *out, double pe, double be, uint64_t rc, uint64_t oc) {
    setup(pe,be,rc,oc);
    if(!setjmp(STOP)) {
        poll_control(); INPUT=fopen(in,"r");OUTPUT=fopen(out,"w");
        if(!INPUT||!OUTPUT) die("native IO open failed");
        if(histogram_body()) die("histogram error");
        poll_control();
    }
    clear_state(); return stop_code;
}
int native_guard(int mode) {
    setup(now_s()+1,now_s()+1,UINT64_MAX,1024);
    if(!setjmp(STOP)) {
        switch(mode) {
        case 0: overlap_R();break; case 1: donor_pair_sweep();break;
        case 2: die("FORBIDDEN: checker");break; case 3: die("FORBIDDEN: CP-SAT");break;
        case 4: die("FORBIDDEN: canonical portfolio evaluator");break;
        case 5: pair_U_exact();break; default: g_brute_pair();break;
        }
    }
    clear_state();return stop_code;
}
/* No ticket/gain computation: exercise exactly the same polling and cleanup. */
int native_synthetic(int mode, double pe, double be, uint64_t rc, uint64_t oc, const char *out) {
    setup(pe,be,rc,oc);
    if(!setjmp(STOP)) {
        if(mode==1) { probe_memory=malloc(16*1024*1024); if(!probe_memory) die("probe malloc failed"); }
        if(mode==2) { OUTPUT=fopen(out,"w");if(!OUTPUT)die("probe output open failed"); }
        uint64_t i=0;
        for(;;i++) {
            if(mode==1) probe_memory[(i%4096)*4096]=(unsigned char)i;
            if(mode==2) bounded_printf("synthetic-capacity-fixture-0123456789\n");
            (void)checked_n();
        }
    }
    clear_state();return stop_code;
}
"""


def c_source(donor):
    pilot = pilot_namespace()
    source, provenance = pilot["c_source"](donor)
    header = pilot["C_HEADER"].replace('static void die(const char *msg) { fprintf(stderr, "%s\\n", msg); exit(3); }', "")
    header = header.replace("    clock_gettime(CLOCK_MONOTONIC, &ts);", """    #ifdef __APPLE__
    clock_gettime(CLOCK_UPTIME_RAW, &ts); /* Python mach_absolute_time timebase */
    #else
    clock_gettime(CLOCK_MONOTONIC, &ts);
    #endif""")
    start = source.index("/* Removed donor paths")
    body = source[start:]
    a, b = body.index("int main("), body.index("    const double start = now_s();")
    body = body[:a] + "static int histogram_body(void) {\n" + body[b:]
    body = body.replace("scanf(", "fscanf(INPUT,").replace("printf(", "bounded_printf(")
    # Guard the native boundary independently of Python's allowlist.
    seam = '    init_binom();'
    guard = '''    if (N==49) {
        const int allowed[7][2]={{0,11},{0,12},{0,18},{12,13},{12,15},{12,18},{18,19}};
        int ok=0;for(int i=0;i<7;i++) if(pi==allowed[i][0]&&pj==allowed[i][1])ok=1;
        if(k!=20||!ok)die("FORBIDDEN: pair outside seven-pair allowlist");
    }
'''
    body = body.replace(seam, guard + seam, 1)
    core = donor[donor.index("static void init_binom("):donor.index("/* Table-free two-ticket")]
    generated = header + C_CONTROL + core + body + C_EXPORTS
    provenance.update({"GENERATED_C_SHA256": sha(generated.encode()),
                       "CONTROL_SEAM": "N scalar accessor every 4096 accesses; bounded output checks; unchanged donor core text",
                       "NATIVE_INTERFACE": "ctypes.PyDLL native_histogram: same PID, caller thread, GIL held",
                       "GUARD_MODES": list(FORBIDDEN) + ["pair_U_exact", "g_brute_pair"]})
    return generated, provenance


class StopBatch(RuntimeError):
    def __init__(self, message, observation=None):
        super().__init__(message)
        self.observation = observation or {}


def folder_bytes(folder):
    return sum(p.stat().st_size for p in Path(folder).rglob("*") if p.is_file())


def peak_memory():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def check_limits(deadline, folder, *, temp_limit=TEMP_LIMIT):
    if time.monotonic() >= deadline:
        raise StopBatch("BATCH_DEADLINE")
    if peak_memory() > RSS_LIMIT:
        raise StopBatch("RSS_TARGET")
    size = folder_bytes(folder)
    if size > temp_limit:
        raise StopBatch("TEMP_CAPACITY")
    return size


def compile_c(source, folder, deadline):
    c, library = Path(folder)/"histogram.c", Path(folder)/"histogram.dylib"
    if len(source.encode()) > TEMP_LIMIT:
        raise StopBatch("TEMP_CAPACITY")
    c.write_text(source)
    command = ["clang", "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror", "-dynamiclib" if sys.platform == "darwin" else "-shared", "-fPIC", str(c), "-o", str(library)]
    env = dict(os.environ, TMPDIR=str(folder), OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    # Compiler is preparation only; bounded polling/terminate, no signal retries.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    temp_peak = 0
    try:
        while process.poll() is None:
            temp_peak = max(temp_peak, check_limits(deadline, folder))
            rss_sample = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(process.pid)], capture_output=True, text=True, timeout=.5)
            if rss_sample.stdout.strip() and int(rss_sample.stdout.strip())*1024 > RSS_LIMIT:
                raise StopBatch("COMPILER_RSS_TARGET")
            try:
                _, err = process.communicate(timeout=0.02)
                break
            except subprocess.TimeoutExpired:
                pass
        else:
            _, err = process.communicate()
        if process.returncode:
            raise StopBatch("COMPILE_ERROR: " + err.decode()[:2000])
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired as exc:
                raise StopBatch("COMPILER_STOP_UNVERIFIED") from exc
        raise
    temp_peak = max(temp_peak, check_limits(deadline, folder))
    return library, command, temp_peak


def native_library(path):
    lib = ctypes.PyDLL(str(path))  # caller's thread; do not release GIL
    limits = [ctypes.c_double, ctypes.c_double, ctypes.c_uint64, ctypes.c_uint64]
    lib.native_histogram.argtypes = [ctypes.c_char_p, ctypes.c_char_p] + limits
    lib.native_synthetic.argtypes = [ctypes.c_int] + limits + [ctypes.c_char_p]
    lib.native_guard.argtypes = [ctypes.c_int]
    for name in ("native_rss", "native_peak_rss"):
        getattr(lib, name).restype = ctypes.c_uint64
    for name in ("native_max_poll_gap", "native_stop_latency", "native_now"):
        getattr(lib, name).restype = ctypes.c_double
    lib.native_reason.restype = ctypes.c_char_p
    return lib


def synthetic_capabilities(lib, folder):
    reports = []
    before = time.monotonic()
    native_time = lib.native_now()
    after = time.monotonic()
    if not before-.001 <= native_time <= after+.001:
        raise StopBatch("BLOCKED_PRELAUNCH: native/Python clock mismatch")
    for name, mode, pair_delta, batch_delta, rss, outcap, expected in (
        ("PAIR_DEADLINE", 0, .025, 1, RSS_LIMIT, 1024, 1),
        ("BATCH_DEADLINE", 0, 1, .025, RSS_LIMIT, 1024, 2),
        # malloc may reuse resident free pages; a forced-low fixture threshold
        # tests the actual RSS comparator/stop path without assuming RSS growth.
        ("RSS_TARGET", 1, 1, 1, 1, 1024, 3),
        ("OUTPUT_CAPACITY", 2, 1, 1, RSS_LIMIT, 70, 4),
    ):
        output = Path(folder)/"synthetic.out"
        start = time.monotonic()
        code = lib.native_synthetic(mode, start+pair_delta, start+batch_delta, rss, outcap, os.fsencode(output))
        elapsed = time.monotonic()-start
        size = output.stat().st_size if output.exists() else 0
        if code != expected or elapsed > .25 or not lib.native_state_zero() or size > outcap:
            raise StopBatch("BLOCKED_PRELAUNCH: synthetic " + name)
        reports.append({"CASE": name, "RETURN_CODE": code, "ELAPSED_SECONDS": elapsed,
                        "RSS_CAP_BYTES": rss, "RSS_FIXTURE": "forced-low 1-byte threshold" if mode == 1 else None,
                        "STOP_LATENCY_SECONDS": lib.native_stop_latency(), "MAX_POLL_GAP_SECONDS": lib.native_max_poll_gap(),
                        "PEAK_CURRENT_RSS_BYTES": lib.native_peak_rss(), "OUTPUT_BYTES": size, "STATE_ZERO": True})
        output.unlink(missing_ok=True)
    if lib.native_pid() != os.getpid() or any(lib.native_guard(i) != 5 for i in range(7)):
        raise StopBatch("BLOCKED_PRELAUNCH: process/forbidden-entry guard")
    return reports


def empty_row(identity):
    return {**identity, "STATUS": "NOT_RUN", "C_ij": None, "LEGAL_SINGLE_TICKETS": None,
            "BUCKET_COUNT": None, "E": None, "HISTOGRAM_COMPLETE": False,
            "HISTOGRAM": [], "HISTOGRAM_SHA256": None, "COMPLEMENTARY_BUCKET_TABLE": [],
            "COMPLEMENTARY_TABLE_SHA256": None, "ELAPSED_SECONDS": None,
            "PEAK_MEMORY_BYTES": None, "ARTIFACT_COMPLETE": False}


def archive(result, path, folder, *, result_limit=RESULT_LIMIT, temp_limit=TEMP_LIMIT, deadline=None, peaks=None):
    # Capacity checks precede mutation; never truncate complete buckets/tables.
    data = json.dumps(result, ensure_ascii=False, indent=2).encode() + b"\n"
    if len(data) > result_limit:
        raise StopBatch("RESULT_CAPACITY")
    scratch = Path(folder)/"seal.json"
    scratch_peak = folder_bytes(folder) + len(data)
    if scratch_peak > temp_limit:
        raise StopBatch("TEMP_CAPACITY")
    if deadline is not None:
        check_limits(deadline, folder)
    with scratch.open("xb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    if peaks is not None:
        peaks["RESULT"] = max(peaks["RESULT"], len(data))
        peaks["TEMP"] = max(peaks["TEMP"], scratch_peak)
    if scratch.read_bytes() != data:
        raise StopBatch("ARCHIVE_READBACK_MISMATCH")
    os.replace(scratch, path)
    with Path(path).open("rb") as f:
        if f.read() != data:
            raise StopBatch("ARCHIVE_READBACK_MISMATCH")
    if deadline is not None:
        check_limits(deadline, folder)
    return len(data)


def mark_partial(result, index, reason):
    result["TASK_STATUS"] = "PARTIAL"
    result["STOP_REASON"] = reason
    if index is not None:
        identity = result["SEVEN_PAIRS"][index]
        identity.update({"STATUS": "INCOMPLETE", "E": None, "HISTOGRAM_COMPLETE": False,
                         "ARTIFACT_COMPLETE": False, "HISTOGRAM": [], "HISTOGRAM_SHA256": None,
                         "COMPLEMENTARY_BUCKET_TABLE": [], "COMPLEMENTARY_TABLE_SHA256": None})


def validate_source_coverage(data, identity):
    # The original N2 START count is a sevenfold incidence count; reference the
    # immutable pilot's already-converted 7_SET coverage. Never scale C_ij/gain.
    if data["COVERED_P"] != identity["EXPECTED_COVERED_P_7_SET"] or data["C_ij"] != data["COVERED_P"]-data["COVERED_R"]:
        raise ValueError("C_ij/source coverage mismatch in 7_SET units")


def measured_row(lib, folder, identity, pilot, batch_deadline, pair_deadline):
    input_path, output_path = Path(folder)/"input.txt", Path(folder)/"native.json"
    payload = pilot["input_text"](49, identity["ENGINE_TICKETS"], identity["PAIR_ENGINE"])
    input_path.write_text(payload)
    available = TEMP_LIMIT - folder_bytes(folder)
    start = time.monotonic()
    code = lib.native_histogram(os.fsencode(input_path), os.fsencode(output_path), pair_deadline, batch_deadline, RSS_LIMIT, available)
    elapsed = time.monotonic()-start
    observations = {"ELAPSED_SECONDS": elapsed, "PEAK_MEMORY_BYTES": lib.native_peak_rss(),
                    "MAX_POLL_GAP_SECONDS": lib.native_max_poll_gap(), "STOP_LATENCY_SECONDS": lib.native_stop_latency(),
                    "TEMP_PEAK_BYTES": folder_bytes(folder), "MEASUREMENT_PID": lib.native_pid()}
    try:
        if not lib.native_state_zero():
            raise StopBatch("NATIVE_STATE_CONTAMINATION")
        if code:
            raise StopBatch(STOP_CODES.get(code, "NATIVE_ERROR") + ": " + lib.native_reason().decode(), observations)
        data = json.loads(output_path.read_bytes())
        exact, table = pilot["validate_measurement"](data, identity)
        if data["HISTOGRAM"] != sorted(data["HISTOGRAM"]):
            raise ValueError("histogram is not sorted")
        validate_source_coverage(data, identity)
        return {**identity, **data, "STATUS": "COMPLETE", "E": exact,
                "BUCKET_COUNT": len(data["HISTOGRAM"]), "HISTOGRAM_SHA256": sha(compact(data["HISTOGRAM"])),
                "COMPLEMENTARY_BUCKET_TABLE": table, "COMPLEMENTARY_TABLE_SHA256": sha(compact(table)),
                **observations,
                "PROCESS_PEAK_MEMORY_BYTES": data["PEAK_MEMORY_BYTES"],
                "MAX_POLL_GAP_SECONDS": lib.native_max_poll_gap(), "STOP_LATENCY_SECONDS": lib.native_stop_latency(),
                "ENGINE_INPUT_SHA256": sha(payload.encode()), "MEASUREMENT_PID": lib.native_pid(),
                "STATE_ZERO_AFTER_CALL": True, "ARTIFACT_COMPLETE": True}
    except Exception as exc:
        if isinstance(exc, StopBatch):
            exc.observation.update(observations)
            raise
        raise StopBatch("VALIDATION_ERROR: " + str(exc), observations) from exc
    finally:
        input_path.unlink(missing_ok=True); output_path.unlink(missing_ok=True)


def main():
    if sys.argv[1:] != ["run"]:
        raise SystemExit("usage: b649_c2_n2_equality_seven_pair_batch_r1.py run")
    if RESULT.exists():
        raise SystemExit("result exists: retry/resume forbidden")
    expected = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
    if str(ROOT) != expected or git("branch", "--show-current") != "codex/b649-c2-n2-equality-seven-pair-batch-r1":
        raise SystemExit("exclusive worktree/branch mismatch")
    # Development and synthetic tests precede, and are separately timed from, batch.
    development_start = time.monotonic()
    test_command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/unit", "-p", TEST_NAME, "-v"]
    tests = subprocess.run(test_command, cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    print(tests.stderr, flush=True)
    development_wall = time.monotonic()-development_start
    test_count_match = re.search(r"Ran (\d+) tests", tests.stderr)
    development_epoch = os.environ.get("B649_DEVELOPMENT_START_UNIX")
    result = {"TASK_ID": TASK_ID, "TASK_STATUS": "BLOCKED_PRELAUNCH", "BASE_HEAD": BASE,
              "BASE_TREE": BASE_TREE, "SOURCE_HEAD": git("rev-parse", "HEAD"),
              "SOURCE_TREE": git("rev-parse", "HEAD^{tree}"), "NEW_ADAPTER_SHA256": sha(Path(__file__).read_bytes()),
              "COUNTING_UNIT": "7_SET", "SEVEN_PAIRS": [empty_row({"PAIR_ORDERED": list(s[0]), "PAIR_ENGINE": list(s[1]), "ORBIT_INDEX": s[2], "ORBIT_SIZE": s[3]}) for s in ALLOWLIST],
              "RESOURCE_LIMITS": {"BATCH_WALL_SECONDS": BATCH_WALL, "PAIR_WALL_SECONDS": PAIR_WALL, "STOP_ARCHIVE_RESERVE_SECONDS": RESERVE,
                                  "RSS_TARGET_BYTES": RSS_LIMIT, "RESULT_LIMIT_BYTES": RESULT_LIMIT, "TEMP_LIMIT_BYTES": TEMP_LIMIT},
              "NATIVE_CALL_AND_PROCESS_MODEL": {"MEASUREMENT_PID": os.getpid(), "PROCESSES": 1, "WORKERS": 1, "COMPUTATION_THREADS": 1,
                                               "INTERFACE": "ctypes.PyDLL; native histogram in caller thread, GIL held; compiler subprocess only during preparation"},
              "RESOURCE_ENFORCEMENT_CAPABILITIES_AND_LIMITATIONS": {"NATIVE_STOP": "cooperative control every 4096 N accesses and every output fragment; C longjmp to wrapper, full cleanup",
                  "RSS": "current resident bytes via mach_task_basic_info on macOS; monitored target, NOT OS hard limit; polling can overshoot",
                  "CAPACITY": "bounded native output before each write; aggregate OS-temp monitor in preparation; exact full result/scratch size checked before sealing",
                  "LIMITATIONS": "cooperative polling cannot hard-bound OS scheduling/IO stalls; compiler aggregate temp check may overshoot between polls (20ms plus ps query); Python verification checks deadlines between bounded stages"},
              "HASH_CONVENTION": "SHA256 UTF-8 json.dumps(value,separators=(',',':'),ensure_ascii=True); histogram sorted by unique integer gain, positive integer counts; table ascending A; missing buckets zero",
              "FOCUSED_TEST_COMMAND_AND_COUNTS": {"ARGV": test_command, "TESTS": int(test_count_match[1]) if test_count_match else 0, "PASS": tests.returncode == 0, "OUTPUT": tests.stderr.strip()},
              "DEVELOPMENT_FOCUSED_TEST_WALL_SECONDS": development_wall, "STOP_REASON": None,
              "DEVELOPMENT_TOTAL_WALL_SECONDS_BEFORE_BATCH": time.time()-float(development_epoch) if development_epoch else None,
              "DEVELOPMENT_PRIOR_FAILED_ATTEMPTS": [{"COMMAND": test_command, "TESTS_RUN": 0, "WALL_SECONDS": 8.140,
                  "FAILURE": "synthetic pair deadline: mismatched Darwin CLOCK_MONOTONIC and Python mach_absolute_time timebases",
                  "REAL_MEASUREMENTS": 0, "REPAIR": "native uses CLOCK_UPTIME_RAW on Darwin; clock equivalence acceptance added"}],
              "NEGATIVE_AND_PARTIAL_TESTS": "native deadline/RSS/output stops; archive result/temp caps; previous COMPLETE retained/current INCOMPLETE/subsequent NOT_RUN; forbidden native guards; by-value negatives; broken stop gate rejected; repeated native state cleared",
              "PILOT_(0,1)_REMEASURED": "NO", "EQUALITY_PAIRS_MATERIALIZED": 0, "PAIR_OVERLAP_CALLS": 0, "N2_PAIR_SWEEP_CALLS": 0,
              "CHECKER_CALLS": 0, "CP_SAT_CALLS": 0, "CANONICAL_SCORING_CALLS": 0,
              "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN", "REMAINING_TASK_MODEL": {"最強模型": "新histogram結果的科學解讀", "強模型": "僅固定資料與執行契約問題"},
              "SCIENTIFIC_SCOPE": "E>0 means equality candidates only. E=0 closes only the selected representative and its verified orbit equality boundary. No tie disappearance, new isomorphism class or global optimum claimed.",
              "RESULT_LOCATOR": str(RESULT), "RUNTIME_TRANSITION_OCCURRED": "NO", "ATTEMPTS_PER_PAIR": 1, "AUTO_RETRY": False, "AUTO_RESUME": False}
    batch_start = time.monotonic()
    deadline = batch_start+BATCH_WALL
    temp_peak = result_peak = 0
    peaks = {"RESULT": 0, "TEMP": 0}
    current = None
    with tempfile.TemporaryDirectory(prefix=TASK_ID+"-") as tmp:
        try:
            if tests.returncode:
                raise StopBatch("FOCUSED_CAPABILITY_TESTS_FAILED")
            identities, donor, dependencies = load_inputs()
            result["DONOR_AND_DEPENDENCY_IDENTITIES"] = dependencies
            result["SEVEN_PAIRS"] = [empty_row(i) for i in identities]
            source, provenance = c_source(donor)
            result["ADAPTER_PROVENANCE"] = provenance
            library, command, temp_peak = compile_c(source, tmp, deadline-RESERVE)
            result["COMPILE_COMMAND"] = command
            result["GENERATED_C_SHA256"] = sha(source.encode())
            result["BINARY_SHA256"] = sha(library.read_bytes())
            lib = native_library(library)
            result["SYNTHETIC_CAPABILITY_OBSERVATIONS"] = synthetic_capabilities(lib, tmp)
            pilot = pilot_namespace()
            result["TASK_STATUS"] = "PARTIAL"
            result_peak = archive(result, RESULT, tmp, peaks=peaks)
            for i, identity in enumerate(identities):
                check_limits(deadline-RESERVE, tmp)
                current = i
                pair_start = time.monotonic()
                pair_deadline = min(pair_start+PAIR_WALL, deadline-RESERVE)
                row = measured_row(lib, tmp, identity, pilot, deadline-RESERVE, pair_deadline)
                temp_peak = max(temp_peak, row["TEMP_PEAK_BYTES"])
                check_limits(pair_deadline, tmp)
                candidate = {**result, "SEVEN_PAIRS": list(result["SEVEN_PAIRS"])}
                candidate["SEVEN_PAIRS"][i] = row
                candidate["TASK_STATUS"] = "COMPLETE" if i == 6 else "PARTIAL"
                result_peak = max(result_peak, archive(candidate, RESULT, tmp, deadline=pair_deadline, peaks=peaks))
                row["PAIR_TOTAL_WALL_THROUGH_ARCHIVE_SECONDS"] = time.monotonic()-pair_start
                result = candidate
                current = None
                print(json.dumps({"PAIR_ORDERED": row["PAIR_ORDERED"], "STATUS": row["STATUS"], "C_ij": row["C_ij"], "E": row["E"], "ELAPSED_SECONDS": row["ELAPSED_SECONDS"]}), flush=True)
            load_inputs()  # immutable/sealed inputs must remain identical
            check_limits(deadline, tmp)
        except Exception as exc:
            if result["TASK_STATUS"] == "BLOCKED_PRELAUNCH":
                result["STOP_REASON"] = str(exc)
            else:
                if current is not None and isinstance(exc, StopBatch):
                    result["SEVEN_PAIRS"][current].update(exc.observation)
                    temp_peak = max(temp_peak, exc.observation.get("TEMP_PEAK_BYTES", 0))
                mark_partial(result, current, str(exc))
            print("STOP", str(exc), flush=True)
        result["COMPLETED_REPRESENTATIVES"] = sum(r["STATUS"] == "COMPLETE" for r in result["SEVEN_PAIRS"])
        result["COVERED_ORIGINAL_PAIRS"] = sum(r["ORBIT_SIZE"] for r in result["SEVEN_PAIRS"] if r["STATUS"] == "COMPLETE")
        temp_peak = max(temp_peak, folder_bytes(tmp))
        result["RESULT_PEAK_BYTES"] = peaks["RESULT"]
        result["TEMP_PEAK_BYTES"] = max(temp_peak, peaks["TEMP"])
        result["PROCESS_PEAK_MEMORY_BYTES"] = peak_memory()
        result["BATCH_WALL_SECONDS"] = time.monotonic()-batch_start
        result["BATCH_WALL_TIMING_SCOPE"] = "artifact timer sampled before final seal; terminal summary includes final seal/readback and OS-temp cleanup"
        result["TEMP_PEAK_SCOPE"] = "native file and seal scratch sizes accounted exactly; compiler temporary peak sampled between polls"
        # Solve metadata size accounting before writing the final artifact.
        for _ in range(4):
            size = len(json.dumps(result, ensure_ascii=False, indent=2).encode())+1
            result["RESULT_PEAK_BYTES"] = max(result["RESULT_PEAK_BYTES"], size)
            result["TEMP_PEAK_BYTES"] = max(result["TEMP_PEAK_BYTES"], folder_bytes(tmp)+size)
        try:
            archive(result, RESULT, tmp, deadline=deadline, peaks=peaks)
        except StopBatch as exc:
            mark_partial(result, None, str(exc))
            archive(result, RESULT, tmp, peaks=peaks)
    print(json.dumps({"TASK_STATUS": result["TASK_STATUS"], "COMPLETED_REPRESENTATIVES": result["COMPLETED_REPRESENTATIVES"], "COVERED_ORIGINAL_PAIRS": result["COVERED_ORIGINAL_PAIRS"], "BATCH_WALL_SECONDS": time.monotonic()-batch_start, "RESULT_SHA256": sha(RESULT.read_bytes())}), flush=True)


if __name__ == "__main__":
    main()
