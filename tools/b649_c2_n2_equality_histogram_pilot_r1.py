"""One fixed C2 pair: reuse frozen donor single gains, export integer histogram.

Generated C and its binary are disposable OS-temp files. No original execution
is launched or written. The donor pair loop, overlap code and COVERED7 builder
are omitted; their entry points are replaced by unconditional rejection guards.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lottolab.research import b649_k20_c2_orbit_reduced_exact_n2 as orbit  # noqa: E402

TASK_ID = "B649_C2_N2_EQUALITY_HISTOGRAM_PILOT_R1"
BASE = "0ba102858c9d5156b759a172fe0ab0fad01ab8c0"
SEALED = "docs/research/matrix-native-results/b649-k20-c2-orbit-reduced-exact-n2-r1-result.json"
SEALED_SHA = "daf6dae3bd177903cf352ff0087c5a66f3232751eaf935244e2537698d20653d"
DONOR_SHA = "ed7c88467a56648c6587aadbbce6b23bc419c9218f840405238019ac7286d4fa"
RESULT = (
    ROOT / "docs/research/matrix-native-results/b649-c2-n2-equality-histogram-pilot-r1-result.json"
)
TEST = "tests/unit/test_b649_c2_n2_equality_histogram_pilot_r1.py"
WALL_CAP = 600


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def pinned_file(path: str, expected: str) -> bytes:
    data = Path(path).read_bytes()
    if sha(data) != expected:
        raise ValueError(f"pinned SHA mismatch: {path}")
    return data


def pair_identity(ordered: list, engine: list, mapping: list) -> dict:
    """Check *all* ticket values, including the removed and untouched subsets."""
    orbit.require_c2_start(ordered)
    actual = list(orbit.ordered_to_engine_slots(ordered))
    if actual != mapping or engine != sorted(ordered):
        raise ValueError("mapping differs from by-value C2 normalization")
    if any(engine[mapping[i]] != t for i, t in enumerate(ordered)):
        raise ValueError("ticket value mismatch")
    pair = list(orbit.engine_pair(mapping, (0, 1)))
    removed = [ordered[i] for i in (0, 1)]
    untouched = ordered[2:]
    if sorted(engine[i] for i in pair) != sorted(removed):
        raise ValueError("removed ticket values differ")
    if sorted(t for i, t in enumerate(engine) if i not in pair) != sorted(untouched):
        raise ValueError("untouched ticket values differ")
    return {
        "PAIR_ORDERED": [0, 1],
        "PAIR_ENGINE": pair,
        "REMOVED_TICKETS": removed,
        "UNTOUCHED_TICKETS": untouched,
        "ORDERED_TO_ENGINE_SLOTS": mapping,
    }


def load_inputs() -> tuple[dict, str]:
    sealed_bytes = (ROOT / SEALED).read_bytes()
    if sha(sealed_bytes) != SEALED_SHA:
        raise ValueError("sealed result identity mismatch")
    sealed = json.loads(sealed_bytes)
    contract_path = sealed["RUN_LOCATORS"]["CONTRACT"]
    contract = json.loads(pinned_file(contract_path, sealed["ENGINE_AUTHORITY"]["CONTRACT_SHA256"]))
    engine = contract["ENGINE"]
    donor = pinned_file(engine["SOURCE_PATH"], DONOR_SHA).decode()
    pinned_file(engine["BINARY_PATH"], engine["BINARY_SHA256"])
    locator = contract["START"]["LOCATOR"]
    c2_bytes = subprocess.check_output(["git", "show", locator], cwd=ROOT)
    if sha(c2_bytes) != contract["START"]["FILE_SHA256"]:
        raise ValueError("C2 source artifact identity mismatch")
    ordered = json.loads(c2_bytes)["C2"]["full_portfolio"]
    map_file = contract["ORBIT"]["MAPPING_FILE"]
    mapping = json.loads(pinned_file(map_file["PATH"], map_file["SHA256"]))
    if mapping["ORDERED_TICKETS"] != ordered:
        raise ValueError("mapping ordered ticket values differ")
    identity = pair_identity(ordered, mapping["ENGINE_TICKETS"], mapping["ORDERED_TO_ENGINE_SLOTS"])
    row = next(r for r in mapping["ROWS"] if r["ORDERED_PAIR"] == [0, 1])
    if row["ENGINE_PAIR"] != identity["PAIR_ENGINE"]:
        raise ValueError("existing mapping row differs")
    identity.update(
        {
            "ENGINE_TICKETS": mapping["ENGINE_TICKETS"],
            "DONOR_LOCATOR": engine["SOURCE_PATH"],
            "DONOR_BINARY_SHA256": engine["BINARY_SHA256"],
            "CONTRACT_LOCATOR": contract_path,
            "CONTRACT_SHA256": sealed["ENGINE_AUTHORITY"]["CONTRACT_SHA256"],
            "SEALED_N2_RESULT_SHA256": SEALED_SHA,
            "C2_INPUT_IDENTITY": {
                "ARTIFACT_LOCATOR": locator,
                "ARTIFACT_SHA256": sha(c2_bytes),
                "ORDERED_SHA256": orbit.compact_sha256(ordered),
                "SORTED_SHA256": orbit.compact_sha256(sorted(ordered)),
                "MAPPING_FILE": map_file,
                "MAPPING_ROWS_SHA256": orbit.mapping_sha256(mapping["ROWS"]),
                "PAIR_MAPPING_ROW": row,
                "BY_VALUE_REMOVED_AND_18_UNTOUCHED_CHECK": "PASS",
            },
        }
    )
    if identity["C2_INPUT_IDENTITY"]["MAPPING_ROWS_SHA256"] != contract["ORBIT"]["MAPPING_SHA256"]:
        raise ValueError("existing mapping row identity mismatch")
    return identity, donor


def equality_count(buckets: list, target: int, *, complete: bool) -> tuple[int, list]:
    if not complete:
        raise ValueError("partial histogram cannot yield an exact equality count")
    if type(target) is not int or target < 0:
        raise ValueError("target must be a nonnegative integer in 7-set units")
    h = {}
    for a, count in buckets:
        if type(a) is not int or type(count) is not int or a < 0 or count <= 0 or a in h:
            raise ValueError("histogram must have unique integer gains and positive integer counts")
        h[a] = count
    rows = []
    for a in sorted(h):
        b = target - a
        if a > b or b not in h:
            continue
        contribution = h[a] * h[b] if a < b else math.comb(h[a], 2)
        rows.append(
            {
                "A": a,
                "B": b,
                "H_A": h[a],
                "H_B": h[b],
                "RULE": "PRODUCT" if a < b else "CHOOSE_2_DISTINCT",
                "CONTRIBUTION": contribution,
            }
        )
    return sum(row["CONTRIBUTION"] for row in rows), rows


C_HEADER = r"""
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/resource.h>
#define MAXN 64
#define MAXK 64
static int64_t BIN[MAXN + 2][9];
static int N;
static int64_t C4 = 3, C5 = 6, C6 = 10;
static int32_t *A3, *A4, *A5, *A6;
static int64_t N3, N4, N5, N6, N7;
static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}
static void die(const char *msg) { fprintf(stderr, "%s\n", msg); exit(3); }
"""

C_MAIN = r"""
/* Removed donor paths fail closed. No pair loop/overlap implementation exists. */
static void overlap_R(void) { die("FORBIDDEN: overlap_R"); }
static void pair_U_exact(void) { die("FORBIDDEN: pair_U_exact"); }
static void g_brute_pair(void) { die("FORBIDDEN: g_brute_pair"); }
static void donor_pair_sweep(void) { die("FORBIDDEN: donor N2 pair sweep"); }
static int64_t *H, *SINGLE_GAINS, gain_bound, raw, excluded;
static uint8_t *IS_R;
static uint64_t BM[MAXK];
static int NB;
static void record_gain(int64_t rank, int64_t gain, const int *prefix, int last) {
    if (gain < 0 || gain > gain_bound) die("gain outside exact single-ticket coverage bound");
    raw++;
    if (SINGLE_GAINS) {
        int t[6];
        memcpy(t, prefix, 5 * sizeof(int)); t[5] = last;
        if (g_direct(t) != gain || g_brute_single(t, BM, NB) != gain)
            die("small-domain donor direct/brute single gain mismatch");
        SINGLE_GAINS[rank] = gain;
    }
    if (IS_R[rank]) {
        if (gain != 0) die("untouched ticket must have zero gain");
        excluded++;
    } else H[gain]++;
}
static void print_ticket(const int *t) {
    printf("[%d,%d,%d,%d,%d,%d]",t[0]+1,t[1]+1,t[2]+1,t[3]+1,t[4]+1,t[5]+1);
}
int main(int argc, char **argv) {
    if (argc != 2) die("expected histogram mode");
    if (!strcmp(argv[1], "guard_overlap_R")) overlap_R();
    if (!strcmp(argv[1], "guard_pair_U_exact")) pair_U_exact();
    if (!strcmp(argv[1], "guard_g_brute_pair")) g_brute_pair();
    if (strcmp(argv[1], "histogram")) donor_pair_sweep();
    const double start = now_s();
    int k, pi, pj, tickets[MAXK][6];
    uint64_t masks[MAXK];
    if (scanf("%d %d", &N, &k) != 2 || N < 8 || N > 49 || k < 3 || k > 20)
        die("invalid histogram header");
    for (int i=0; i<k; i++) {
        masks[i]=0;
        for (int j=0; j<6; j++) {
            int v;
            if (scanf("%d", &v)!=1 || v<1 || v>N) die("invalid ticket value");
            tickets[i][j]=v-1;
            if (j && tickets[i][j]<=tickets[i][j-1]) die("ticket must be increasing");
            masks[i] |= 1ULL<<(v-1);
        }
        for (int j=0; j<i; j++) if (masks[j]==masks[i]) die("duplicate input ticket");
    }
    if (scanf("%d %d",&pi,&pj)!=2 || pi<0 || pi>=k || pj<=pi || pj>=k)
        die("invalid removed pair");
    init_binom();
    N3=binom(N,3); N4=binom(N,4); N5=binom(N,5); N6=binom(N,6); N7=binom(N,7);
    if (!selftest_rank(3) || !selftest_rank(4) || !selftest_rank(5) || !selftest_rank(6))
        die("donor rank selftest failed");
    for (int i=0; i<k; i++) if (i!=pi && i!=pj) BM[NB++]=masks[i];
    A6=malloc((size_t)N6*sizeof(int32_t)); A5=malloc((size_t)N5*sizeof(int32_t));
    A4=malloc((size_t)N4*sizeof(int32_t)); A3=malloc((size_t)N3*sizeof(int32_t));
    IS_R=calloc((size_t)N6,1);
    /* A ticket can win only with j=3..6 of its numbers in W; this is an exact
       upper bound, never a truncation or approximate bucket range. */
    gain_bound=0;
    for (int j=3; j<=6; j++) gain_bound += binom(6,j)*binom(N-6,7-j);
    H=calloc((size_t)(gain_bound+1),sizeof(int64_t));
    SINGLE_GAINS=N<=12 ? malloc((size_t)N6*sizeof(int64_t)) : NULL;
    if (!A6 || !A5 || !A4 || !A3 || !IS_R || !H || (N<=12 && !SINGLE_GAINS))
        die("allocation failed");
    for (int i=0; i<k; i++) if (i!=pi && i!=pj) IS_R[lexrank(tickets[i],6)]=1;
    /* Same donor COV7 identity: each uncovered 7-set contributes seven a6
       incidences. Divide sums by 7 exactly once; gains are already 7-set counts. */
    int64_t sum_P=compute_a6(masks,k);
    int64_t sum_R=compute_a6(BM,NB);
    if (sum_P%7 || sum_R%7) die("a6 incidence sums not divisible by seven");
    int64_t covered_P=N7-sum_P/7, covered_R=N7-sum_R/7;
    int64_t C_ij=covered_P-covered_R;
    if (!compute_a5() || !compute_lower(4,A5,N5,A4,N4,3) ||
        !compute_lower(3,A4,N4,A3,N3,4)) die("donor lower-table divisibility failed");
    double sweep_start=now_s();
    /* DONOR_SWEEP */
    double sweep_seconds=now_s()-sweep_start;
    int64_t legal=0;
    for (int64_t g=0; g<=gain_bound; g++) legal+=H[g];
    if (raw!=N6 || excluded!=NB || legal!=N6-NB) die("single ticket accounting mismatch");
    printf("{\"COUNTING_UNIT\":\"7_SET\",\"C_ij\":%"PRId64
           ",\"COVERED_P\":%"PRId64",\"COVERED_R\":%"PRId64
           ",\"RAW_SINGLE_TICKETS\":%"PRId64",\"EXCLUDED_UNTOUCHED_TICKETS\":%"PRId64
           ",\"LEGAL_SINGLE_TICKETS\":%"PRId64",\"HISTOGRAM_COMPLETE\":true,\"HISTOGRAM\":[",
           C_ij,covered_P,covered_R,raw,excluded,legal);
    int comma=0;
    for (int64_t g=0; g<=gain_bound; g++) if (H[g]) {
        printf("%s[%"PRId64",%"PRId64"]",comma ? "," : "",g,H[g]); comma=1;
    }
    printf("],\"REMOVED_TICKETS\":["); print_ticket(tickets[pi]); printf(",");
    print_ticket(tickets[pj]); printf("],\"UNTOUCHED_TICKETS\":["); comma=0;
    for (int i=0; i<k; i++) if (i!=pi && i!=pj) {
        if (comma) printf(","); print_ticket(tickets[i]); comma=1;
    }
    printf("],\"SINGLE_GAINS_SMALL_TEST_ONLY\":[");
    if (SINGLE_GAINS) for (int64_t r=0; r<N6; r++)
        printf("%s%"PRId64,r ? "," : "",SINGLE_GAINS[r]);
    struct rusage usage;
    if (getrusage(RUSAGE_SELF,&usage)) die("getrusage failed");
    int64_t rss=(int64_t)usage.ru_maxrss;
    #ifndef __APPLE__
    rss*=1024;
    #endif
    printf("],\"PAIR_OVERLAP_CALLS\":0,\"N2_PAIR_SWEEP_CALLS\":0,"
           "\"EQUALITY_PAIRS_MATERIALIZED\":0,\"GAIN_BOUND\":%"PRId64
           ",\"SWEEP_SECONDS\":%.9f,\"ENGINE_WALL_SECONDS\":%.9f,\"PEAK_MEMORY_BYTES\":%"PRId64"}\n",
           gain_bound,sweep_seconds,now_s()-start,rss);
    return 0; /* Immediate histogram exit. No donor two-ticket continuation. */
}
"""


def c_source(donor: str) -> tuple[str, dict]:
    if sha(donor.encode()) != DONOR_SHA:
        raise ValueError("donor source identity mismatch")
    core = donor[donor.index("static void init_binom(") : donor.index("/* Table-free two-ticket")]
    start = donor.index("    {\n        int x[6], s[6];", donor.index("/* Full g_R sweep"))
    stop = donor.index("    double t_sweep", start)
    sweep = donor[start:stop]
    old = "                G[r6].rank = r6;\n                G[r6].g = (int32_t)g;"
    if sweep.count(old) != 1:
        raise ValueError("donor sweep storage seam changed")
    adapted = sweep.replace(old, "                record_gain(r6, g, x, y);")
    source = C_HEADER + core + C_MAIN.replace("    /* DONOR_SWEEP */", adapted)
    return source, {
        "VERBATIM_CORE_SHA256": sha(core.encode()),
        "DONOR_SWEEP_SHA256": sha(sweep.encode()),
        "ADAPTED_SWEEP_SHA256": sha(adapted.encode()),
        "GENERATED_C_SHA256": sha(source.encode()),
        "VERBATIM_FUNCTIONS": [
            "init_binom",
            "binom",
            "lexrank",
            "lexunrank6",
            "next_comb",
            "selftest_rank",
            "compute_a6",
            "compute_a5",
            "compute_lower",
            "g_direct",
            "g_brute_single",
        ],
        "DIFFERENCES": [
            "Optimized donor sweep unchanged except G storage replaced with record_gain.",
            "C_ij from full and R compute_a6 sums, divide incidence sums by 7 once.",
            "Full portfolio A6 computed first, then R A6 and lower tables (no redundant rebuild).",
            "Reject guarded pair/overlap entry points; omit donor main, pair loop and COVERED7.",
            "Exclude untouched tickets by lexrank of verified full values; int64 histogram.",
            "Small test domains only: compare every sweep gain with donor direct and brute.",
            "Emit complete nonzero buckets and exit; Python integer complementary products.",
        ],
        "GUARD_MODES": [
            "slotpair",
            "score_pairs",
            "tablefree_pair",
            "guard_overlap_R",
            "guard_pair_U_exact",
            "guard_g_brute_pair",
        ],
    }


def compile_c(source: str, folder: Path) -> tuple[Path, list[str]]:
    c = folder / "histogram.c"
    binary = folder / "histogram"
    c.write_text(source, encoding="utf-8")
    command = ["clang", "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror", str(c), "-o", str(binary)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return binary, command


def input_text(n: int, tickets: list, pair: list) -> str:
    return (
        f"{n} {len(tickets)}\n"
        + "\n".join(" ".join(map(str, t)) for t in tickets)
        + "\n"
        + " ".join(map(str, pair))
        + "\n"
    )


def validate_measurement(data: dict, identity: dict) -> tuple[int, list]:
    if data["COUNTING_UNIT"] != "7_SET" or not data["HISTOGRAM_COMPLETE"]:
        raise ValueError("measurement incomplete or wrong counting unit")
    if (
        data["RAW_SINGLE_TICKETS"],
        data["EXCLUDED_UNTOUCHED_TICKETS"],
        data["LEGAL_SINGLE_TICKETS"],
    ) != (math.comb(49, 6), 18, math.comb(49, 6) - 18):
        raise ValueError("full single ticket accounting mismatch")
    if sum(c for _, c in data["HISTOGRAM"]) != data["LEGAL_SINGLE_TICKETS"]:
        raise ValueError("histogram sum mismatch")
    if data["REMOVED_TICKETS"] != identity["REMOVED_TICKETS"]:
        raise ValueError("measured removed tickets differ by value")
    if sorted(data["UNTOUCHED_TICKETS"]) != sorted(identity["UNTOUCHED_TICKETS"]):
        raise ValueError("measured untouched tickets differ by value")
    if data["SINGLE_GAINS_SMALL_TEST_ONLY"] or any(
        data[k] != 0
        for k in ("PAIR_OVERLAP_CALLS", "N2_PAIR_SWEEP_CALLS", "EQUALITY_PAIRS_MATERIALIZED")
    ):
        raise ValueError("forbidden pair materialization/call")
    return equality_count(data["HISTOGRAM"], data["C_ij"], complete=True)


def main() -> None:
    if sys.argv[1:] != ["run"]:
        raise SystemExit("usage: b649_c2_n2_equality_histogram_pilot_r1.py run")
    if RESULT.exists():
        raise SystemExit("result already exists; no automatic measurement rerun")
    if git("rev-parse", "HEAD") != BASE:
        raise SystemExit("measurement must start at pinned base")
    pipeline_start = time.monotonic()
    identity, donor = load_inputs()
    source, provenance = c_source(donor)
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
    )
    test_cmd = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests/unit",
        "-p",
        Path(TEST).name,
    ]
    tests = subprocess.run(test_cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    match = re.search(r"Ran (\d+) tests", tests.stderr)
    if not match:
        raise ValueError("focused test count unavailable")
    print(tests.stderr, flush=True)
    result = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "MEASUREMENT_INCOMPLETE",
        "SCIENTIFIC_OUTPUT": "EXACT_EQUALITY_CANDIDATE_COUNT",
        "SOURCE_HEAD": BASE,
        "SOURCE_TREE": git("rev-parse", "HEAD^{tree}"),
        "DONOR_SHA256": DONOR_SHA,
        "ADAPTER_SHA256": sha(Path(__file__).read_bytes()),
        **identity,
        "ADAPTER_PROVENANCE": provenance,
        "COUNTING_UNIT": "7_SET",
        "C_ij": None,
        "RAW_SINGLE_TICKETS": None,
        "EXCLUDED_UNTOUCHED_TICKETS": None,
        "LEGAL_SINGLE_TICKETS": None,
        "HISTOGRAM_COMPLETE": False,
        "HISTOGRAM": [],
        "HISTOGRAM_SHA256": None,
        "COMPLEMENTARY_BUCKET_TABLE": [],
        "EXACT_EQUALITY_PAIR_COUNT": None,
        "EQUALITY_PAIRS_MATERIALIZED": 0,
        "PAIR_OVERLAP_CALLS": 0,
        "N2_PAIR_SWEEP_CALLS": 0,
        "DIAGNOSTIC_WALL_CAP_SECONDS": WALL_CAP,
        "DIAGNOSTIC_ATTEMPTS": 1,
        "MAX_CPU_INTENSIVE_WORKERS": 1,
        "FOCUSED_TEST_COMMAND_AND_COUNTS": {
            "ARGV": test_cmd,
            "TESTS": int(match[1]),
            "PASS": True,
            "OUTPUT": tests.stderr.strip(),
        },
        "NEW_STRICT_GAIN_CLAIMED": "NO",
        "TIE_CLASS_COMPLETENESS_CLAIMED": "NO",
        "N2_STRICT_GAIN_CLOSURE_REDETERMINED": False,
        "OTHER_PAIRS_EXTRAPOLATED": False,
        "REMAINING_TASK_MODEL": {
            "最強模型": "等號範圍是否值得處理的科學決策",
            "強模型": "僅固定資料交付問題",
        },
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
        "RESULT_LOCATOR": str(RESULT),
        "RUNTIME_OUTPUT_POLICY": (
            "Only generated C/binary in disposable OS temp; result is sole durable runtime output."
        ),
    }
    with tempfile.TemporaryDirectory(prefix=TASK_ID + "-") as tmp:
        binary, command = compile_c(source, Path(tmp))
        result["COMPILE_COMMAND"] = command
        result["DIAGNOSTIC_BINARY_SHA256"] = sha(binary.read_bytes())
        payload = input_text(49, identity["ENGINE_TICKETS"], identity["PAIR_ENGINE"])
        result["ENGINE_STDIN_SHA256"] = sha(payload.encode())
        started = time.monotonic()
        process = subprocess.Popen(
            [str(binary), "histogram"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=env,
        )
        try:
            out, err = process.communicate(
                payload, timeout=max(0.001, WALL_CAP - (time.monotonic() - started))
            )
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            out, err = process.communicate(timeout=5)
            result["MEASUREMENT_STOP_REASON"] = "600_SECOND_WALL_CAP_NO_RETRY"
            result["PROCESS_TERMINATION"] = "Task-owned process group SIGTERM at wall cap"
        else:
            if process.returncode == 0:
                data = json.loads(out)
                exact, table = validate_measurement(data, identity)
                result.update(data)
                result.update(
                    {
                        "TASK_STATUS": "COMPLETE",
                        "EXACT_EQUALITY_PAIR_COUNT": exact,
                        "COMPLEMENTARY_BUCKET_TABLE": table,
                        "HISTOGRAM_SHA256": orbit.compact_sha256(data["HISTOGRAM"]),
                        "SCIENTIFIC_INTERPRETATION": (
                            "Candidates for this single pair only; no overlap evaluated, "
                            "no ties or new classes established."
                        )
                        if exact
                        else "Equality boundary empty for this single pair only.",
                    }
                )
            else:
                result["MEASUREMENT_STOP_REASON"] = "DIAGNOSTIC_ERROR_NO_RETRY"
        result["WALL_TIME_SECONDS"] = time.monotonic() - started
        result["DIAGNOSTIC_RETURN_CODE"] = process.returncode
        result["DIAGNOSTIC_STDERR"] = err
        # C self-rusage is exact on success. wait4-derived child rusage also
        # remains available on timeout; its scope includes prior compilation.
        if "PEAK_MEMORY_BYTES" not in result:
            import resource

            peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            result["PEAK_MEMORY_BYTES"] = peak if sys.platform == "darwin" else peak * 1024
            result["PEAK_MEMORY_SCOPE"] = (
                "CHILDREN_INCLUDING_FOCUSED_TESTS_AND_COMPILER_UPPER_BOUND"
            )
        else:
            result["PEAK_MEMORY_SCOPE"] = "DIAGNOSTIC_RUSAGE_SELF"
    result["FULL_PIPELINE_WALL_SECONDS"] = time.monotonic() - pipeline_start
    # Recheck frozen inputs after execution; only the new result may be written.
    load_inputs()
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "C_ij",
                    "EXACT_EQUALITY_PAIR_COUNT",
                    "WALL_TIME_SECONDS",
                    "PEAK_MEMORY_BYTES",
                )
            }
        ),
        flush=True,
    )
    print("RESULT_SHA256", sha(RESULT.read_bytes()), flush=True)


if __name__ == "__main__":
    main()
