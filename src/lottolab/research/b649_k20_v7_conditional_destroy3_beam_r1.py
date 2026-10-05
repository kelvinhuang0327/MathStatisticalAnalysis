"""Owner-authorized 32-set conditional destroy-three beam, fixed run1.

Every expansion scores C(49,6). Exact coverage is primary; diversity and beam
truncation are heuristics. No complete N3 or global K20 optimum is claimed.
"""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import importlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
TASK = "B649_K20_V7_CONDITIONAL_DESTROY3_BEAM_R1"
RUN = ROOT / ".task-data" / TASK / "run1"
SOURCE_COMMIT = "c5c2c704f20ae1be3588355ed0ca9e6ece1a2ba2"
SOURCE_REL = "docs/research/matrix-native-results/b649-k20-v7-destroy3-global-pool-exhaustive-r1-result.json"
RESULT = ROOT / "docs/research/matrix-native-results/b649-k20-v7-conditional-destroy3-beam-r1-result.json"
CPP = Path(__file__).with_suffix(".cpp")
NATIVE = RUN / "conditional-scorer.dylib"
TEST = ROOT / "tests/unit/test_b649_k20_v7_conditional_destroy3_beam_r1.py"
DONOR = ROOT / ".task-data/B649_K20_V7_THREE_TICKET_GLOBAL_REPAIR_PILOT_R1/run1/engine/src"
START_COUNT = 313239661
START_SHA = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
TOTAL = math.comb(49, 6)
OUTCOMES7 = math.comb(49, 7)
TOP_NEXT = 24
BEAM_WIDTH = 32
SIGNATURE_SAMPLES = 16384
WORKERS = 2


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value):
    return hashlib.sha256(compact(value).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def portfolio(value):
    rows = tuple(sorted(tuple(sorted(t)) for t in value))
    if len(set(rows)) != len(rows) or any(len(t) != 6 or len(set(t)) != 6 or
            any(type(n) is not int or not 1 <= n <= 49 for n in t) for t in rows):
        raise ValueError("invalid or duplicate ticket")
    return rows


def portfolio_sha(value):
    return hashlib.sha256(json.dumps(portfolio(value), separators=(",", ":")).encode()).hexdigest()


def mask(ticket):
    return sum(1 << (n - 1) for n in ticket)


def ticket_distance(a, b):
    """Minimum number of replaced numbers over bijections of equal-size ticket sets."""
    if len(a) != len(b):
        raise ValueError("distance requires equal replacement depth")
    common = set(map(tuple, a)).intersection(map(tuple, b))
    a = [t for t in a if tuple(t) not in common]
    b = [t for t in b if tuple(t) not in common]
    if not a:
        return 0
    return min(sum(6 - len(set(x).intersection(y)) for x, y in zip(a, p))
               for p in itertools.permutations(b))


def selection_document(source):
    rows = source.get("PER_DESTROY_TRIPLE", [])
    all_triples = list(itertools.combinations(range(20), 3))
    evidence = []
    sufficient = len(rows) == 1140
    for row in rows:
        opts = row.get("CANONICALLY_RECOUNTED_OPTIMA", [])
        count = row.get("OPTIMAL_SET_COUNT")
        positions = tuple(row.get("POSITIONS", []))
        sufficient &= (positions in all_triples and isinstance(count, int) and count > 0
                       and len(opts) == count)
        candidates = [portfolio(x.get("REPLACEMENTS", [])) for x in opts]
        sufficient &= all(len(x) == 3 for x in candidates) and len(set(candidates)) == len(candidates)
        sufficient &= all(x.get("CANONICAL_COUNT") == row.get("BEST_COUNT") for x in opts)
        distances = [ticket_distance(a, b) for a, b in itertools.combinations(candidates, 2)]
        evidence.append({"POSITIONS": positions, "BEST_COUNT": row.get("BEST_COUNT"),
                         "BEST_COUNT_TIE_MULTIPLICITY": count,
                         "STRUCTURAL_DISTANCE_PAIR_SUM": sum(distances),
                         "STRUCTURAL_DISTANCE_PAIR_COUNT": len(distances),
                         "BEST_REPLACEMENT_SETS_SHA256": digest(candidates)})
    sufficient &= len({tuple(x["POSITIONS"]) for x in evidence}) == 1140
    if sufficient:
        # Multiplicity is the first key, hence equal-key pair denominators are equal.
        evidence.sort(key=lambda x: (-x["BEST_COUNT_TIE_MULTIPLICITY"],
                                     -x["STRUCTURAL_DISTANCE_PAIR_SUM"], x["POSITIONS"]))
        triples = [list(x["POSITIONS"]) for x in evidence[:32]]
        rule = "BEST_TIE_MULTIPLICITY_DESC_STRUCTURAL_MEAN_DISTANCE_DESC_LEX_V1"
    else:
        triples = [list(t) for t in sorted(all_triples,
                   key=lambda t: (hashlib.sha256(f"{TASK}|{t[0]}|{t[1]}|{t[2]}".encode()).hexdigest(), t))[:32]]
        rule = "SHA256_TASK_ID_PIPE_I_PIPE_J_PIPE_K_ASC_V1"
    return {"TASK_ID": TASK, "RUN_ID": "run1", "SOURCE_COMMIT": SOURCE_COMMIT,
            "RULE": rule, "SOURCE_FIELDS_SUFFICIENT": bool(sufficient),
            "STRUCTURAL_DISTANCE": "minimum sum(6-overlap) over all bijections of three replacement tickets; mean over all best-candidate pairs",
            "RANKED_SOURCE_EVIDENCE": evidence, "DESTROY_TRIPLES": triples,
            "DESTROY_TRIPLES_SHA256": digest(triples)}


def atomic_json(path, value, *, immutable=False):
    path = Path(path)
    payload = compact(value).encode()
    if path.exists() and immutable:
        if path.read_bytes() != payload:
            raise RuntimeError(f"IMMUTABLE_IDENTITY_CONFLICT:{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def source_document():
    committed = subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:{SOURCE_REL}"], cwd=ROOT)
    if (ROOT / SOURCE_REL).read_bytes() != committed:
        raise RuntimeError("PINNED_SOURCE_RESULT_CONFLICT")
    value = json.loads(committed)
    if (value["TASK_STATUS"] != "COMPLETE" or value["DESTROY_TRIPLES_COMPLETED"] != 1140
            or value["BEST_CANONICAL_RECOUNT_STATUS"] != "PASS"
            or value["START_COUNT"] != START_COUNT or value["START_SHA256"] != START_SHA):
        raise RuntimeError("PINNED_SOURCE_NOT_COMPLETE_OR_WRONG_START")
    start = portfolio(value["EXECUTION_CONTRACT"]["START_PORTFOLIO"])
    if len(start) != 20 or portfolio_sha(start) != START_SHA:
        raise RuntimeError("START_PORTFOLIO_IDENTITY_CONFLICT")
    return value, start


def science_hashes():
    paths = [Path(__file__), CPP, TEST, ROOT / SOURCE_REL,
             DONOR / "lottolab/research/b649_k20_global_residual_pool_repair_r1.py",
             DONOR / "lottolab/research/b649_k20_five_ticket_exact_repair_r1.py",
             ROOT / "src/lottolab/research/b649_official_any_prize_exact.py"]
    return {str(p.relative_to(ROOT)): file_sha(p) for p in paths}


def freeze():
    source, start = source_document()
    RUN.mkdir(parents=True, exist_ok=True)
    selected = selection_document(source)
    selected["SOURCE_RESULT_SHA256"] = file_sha(ROOT / SOURCE_REL)
    atomic_json(RUN / "destroy-triples.json", selected, immutable=True)
    argv = ["/usr/bin/env", "PYTHONDONTWRITEBYTECODE=1", "OMP_NUM_THREADS=1", "MKL_NUM_THREADS=1",
            "OPENBLAS_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1", "VECLIB_MAXIMUM_THREADS=1",
            "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python",
            "-u", str(Path(__file__)), "run"]
    launcher_roots = [Path("/Users/kelvin/.codex/skills/fable-method"), Path("/Users/kelvin/Documents/ChatGPT/共用Skill專案")]
    if any(list(p.rglob("task_checkpoint.rb")) for p in launcher_roots):
        raise RuntimeError("PROTECTED_LAUNCHER_DISCOVERED_USE_REQUIRED_ENTRYPOINT")
    contract = {"TASK_ID": TASK, "RUN_ID": "run1", "WORKTREE": str(ROOT), "NATIVE_SHA256": file_sha(NATIVE),
                "SOURCE_COMMIT": SOURCE_COMMIT, "START_COUNT": START_COUNT, "START_SHA256": START_SHA,
                "SCIENTIFIC_SOURCE_SHA256": science_hashes(), "SELECTION_SHA256": file_sha(RUN / "destroy-triples.json"),
                "DEPTHS": 3, "TOP_NEXT": TOP_NEXT, "BEAM_WIDTH": BEAM_WIDTH, "WORKERS": WORKERS,
                "TICKET_DISTANCE": selected["STRUCTURAL_DISTANCE"].split(";", 1)[0],
                "SIGNATURE_DISTANCE": "Hamming distance of replacement coverage on R-residual outcomes from 16384 unique SHA256-ranked colex 7-subset probes, seed task ID; greedy maximin against retained states; first anchor lowest canonical full-current-state SHA",
                "TIE_BREAK": "exact coverage descending, residual-signature maximin descending, replacement-set maximin descending, canonical current portfolio SHA ascending",
                "TOP_NEXT_TIE_BREAK": "same diversity rule, applied to ALL tickets tied at the exact top-24 threshold",
                "DEDUPLICATION": "canonical replacement set before beam retention; permutations are one state",
                "SCIENTIFIC_SCOPE": "HEURISTIC_NOT_COMPLETE_N3_OPTIMUM",
                "IMPLEMENTATION_DEPTH": "ENHANCED", "DEPTH_SOURCE": "PLANNER_SUPPLIED",
                "JUDGE_MODE": "NOT_APPLICABLE", "JUDGE_DISPATCH": "SUPPRESSED",
                "LAUNCHER_STATUS": "ABSENT_PROVEN_BEFORE_EXECUTION",
                "LAUNCHER_CHECKED_ROOTS": ["/Users/kelvin/.codex/skills/fable-method", "/Users/kelvin/Documents/ChatGPT/共用Skill專案"],
                "EXACT_ARGV": argv, "EFFECT_CLASSIFICATION": "LOCAL_ONLY_NO_HIGH_RISK",
                "OUTPUT_ROOTS": [str(RUN), str(RESULT)], "CLEANUP_DISPOSITION": "RETAIN_AFTER_HANDOFF",
                "PROJECT_MEMORY_WRITE": "FORBIDDEN", "PUSH": "NO", "PR": "NO", "MERGE": "NO", "PRODUCTION_CHANGE": "NONE"}
    atomic_json(RUN / "execution-contract.json", contract, immutable=True)
    print(compact({"FROZEN": True, "TRIPLES": selected["DESTROY_TRIPLES"],
                   "SELECTION_SHA256": file_sha(RUN / "destroy-triples.json")} ), flush=True)


class Native:
    def __init__(self, n=49, workers=2, path=NATIVE):
        self.lib = ctypes.CDLL(str(path))
        self.lib.b649_create.argtypes = [ctypes.c_int, ctypes.c_int]
        self.lib.b649_create.restype = ctypes.c_void_p
        self.lib.b649_destroy.argtypes = [ctypes.c_void_p]
        self.lib.b649_total.argtypes = [ctypes.c_void_p]
        self.lib.b649_total.restype = ctypes.c_uint64
        self.lib.b649_rows.argtypes = [ctypes.c_void_p]
        self.lib.b649_rows.restype = ctypes.POINTER(ctypes.c_uint8)
        self.lib.b649_score.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
        self.ptr = self.lib.b649_create(n, workers)
        if not self.ptr:
            raise RuntimeError("native allocation or universe arguments failed")
        self.n = n
        self.total = self.lib.b649_total(self.ptr)
        self.rows = np.ctypeslib.as_array(self.lib.b649_rows(self.ptr), shape=(self.total * 6,)).reshape(-1, 6)

    def score(self, frozen):
        masks = np.array([mask(t) for t in frozen], dtype=np.uint64)
        values = np.empty(self.total, dtype=np.int32)
        stats = np.zeros(3, dtype=np.uint64)
        begun = time.monotonic()
        rc = self.lib.b649_score(self.ptr, masks.ctypes.data, len(masks), values.ctypes.data, stats.ctypes.data)
        if rc:
            raise RuntimeError(f"NATIVE_INTEGER_INVARIANT_FAILURE:{rc}")
        return values, {"TICKETS_SCORED": int(stats[0]), "SUM_TOP_COUNTS": int(stats[1]),
                        "SUM_MARGINALS": int(stats[2]), "SECONDS": round(time.monotonic() - begun, 6)}

    def ticket(self, i):
        return tuple(int(x) + 1 for x in self.rows[i])

    def index(self, ticket):
        return sum(math.comb(x - 1, j + 1) for j, x in enumerate(sorted(ticket)))

    def close(self):
        if self.ptr:
            self.lib.b649_destroy(self.ptr)
            self.ptr = None


def verify_identities(stats, coverage7):
    residual = OUTCOMES7 - coverage7
    hits = sum(math.comb(7, j) * math.comb(42, 6 - j) for j in range(3, 7))
    if (stats["TICKETS_SCORED"] != TOTAL or stats["SUM_TOP_COUNTS"] != 7 * residual
            or stats["SUM_MARGINALS"] != hits * residual):
        raise RuntimeError("EXACT_GLOBAL_SCORE_IDENTITY_MISMATCH")


def unrank(rank, k=7, n=49):
    row = []
    for width in range(k, 0, -1):
        n -= 1
        while math.comb(n, width) > rank:
            n -= 1
        row.append(n + 1)
        rank -= math.comb(n, width)
    return tuple(reversed(row))


def signature_sample():
    ranks = set()
    i = 0
    while len(ranks) < SIGNATURE_SAMPLES:
        ranks.add(int(hashlib.sha256(f"{TASK}|signature|{i}".encode()).hexdigest(), 16) % OUTCOMES7)
        i += 1
    return np.array([mask(unrank(x)) for x in sorted(ranks)], dtype=np.uint64)


def residual_sample(sample, remaining):
    won = np.zeros(sample.size, dtype=np.bool_)
    for ticket in remaining:
        won |= np.bitwise_count(sample & np.uint64(mask(ticket))) >= 3
    return sample[~won]


def signature(replacements, sample):
    won = np.zeros(sample.size, dtype=np.bool_)
    for ticket in replacements:
        won |= np.bitwise_count(sample & np.uint64(mask(ticket))) >= 3
    return int.from_bytes(np.packbits(won, bitorder="little").tobytes(), "little")


def state(remaining, replacements, coverage7, sample):
    tickets = portfolio(replacements)
    return {"TICKETS": [list(t) for t in tickets], "COVERAGE7": int(coverage7),
            "SHA256": portfolio_sha(tuple(remaining) + tickets),
            "SIGNATURE": hex(signature(tickets, sample))}


def choose(states, width):
    """Coverage-primary greedy maximin, including all threshold ties."""
    unique = {}
    for s in states:
        sha = s["SHA256"]
        if sha in unique and unique[sha] != s:
            raise RuntimeError("CANONICAL_STATE_CONFLICT")
        unique[sha] = s
    ordered = sorted(unique.values(), key=lambda s: (-s["COVERAGE7"], s["SHA256"]))
    retained = []
    ties = saves = 0
    for _, group in itertools.groupby(ordered, key=lambda s: s["COVERAGE7"]):
        group = list(group)
        take = min(width - len(retained), len(group))
        if take <= 0:
            break
        if len(group) > 1:
            ties += 1
        baseline = {s["SHA256"] for s in group[:take]}
        # Updating min distances once per retained state is exactly greedy maximin.
        minimums = {s["SHA256"]: [math.inf, math.inf] for s in group}
        anchors = list(retained)
        for _ in range(take):
            for anchor in anchors:
                sig = int(anchor["SIGNATURE"], 16)
                for s in group:
                    pair = minimums[s["SHA256"]]
                    pair[0] = min(pair[0], (int(s["SIGNATURE"], 16) ^ sig).bit_count())
                    pair[1] = min(pair[1], ticket_distance(s["TICKETS"], anchor["TICKETS"]))
            picked = min(group, key=lambda s: (-minimums[s["SHA256"]][0],
                                               -minimums[s["SHA256"]][1], s["SHA256"]))
            retained.append(picked)
            saves += picked["SHA256"] not in baseline
            group.remove(picked)
            anchors = [picked]
    return retained, {"TIE_GROUPS": ties, "DIVERSITY_SAVES": saves, "UNIQUE_STATES": len(unique)}


def donor_modules():
    sys.path.insert(0, str(DONOR))
    package = importlib.import_module("lottolab.research")
    package.__path__.append(str(ROOT / "src/lottolab/research"))
    core = importlib.import_module("lottolab.research.b649_k20_global_residual_pool_repair_r1")
    exact = importlib.import_module("lottolab.research.b649_k20_five_ticket_exact_repair_r1")
    oracle = importlib.import_module("lottolab.research.b649_official_any_prize_exact")
    return core, exact, oracle


def real_parity(native, source, start, triples):
    path = RUN / "parity-result.json"
    if path.exists():
        record = json.loads(path.read_text())
        if record["CHECKS"] < 200 or record["PARITY_MISMATCHES"] != 0 or record["SCIENCE_SHA256"] != digest(science_hashes()):
            raise RuntimeError("PARITY_RESUME_IDENTITY_CONFLICT")
        return record
    _, exact, oracle = donor_modules()
    removed = [start[i] for i in triples[0]]
    remaining = tuple(t for i, t in enumerate(start) if i not in triples[0])
    contexts = []
    for depth in range(3):
        frozen = portfolio(remaining + tuple(removed[:depth]))
        official = oracle.evaluate_portfolio(frozen).official_any_prize_outcome_count
        if official % 7:
            raise RuntimeError("CANONICAL_SEVEN_SUBSET_IDENTITY_FAILURE")
        scores, stats = native.score(frozen)
        verify_identities(stats, official // 7)
        probes = {native.index(removed[depth]), native.index(frozen[0]), int(np.argmax(scores)), 0, TOTAL - 1}
        i = 0
        while len(probes) < 70:
            probes.add(int(hashlib.sha256(f"{TASK}|real-parity|{depth}|{i}".encode()).hexdigest(), 16) % TOTAL)
            i += 1
        probes = sorted(probes)
        tickets = [native.ticket(i) for i in probes]
        direct = exact.direct_marginals(frozen, tickets)
        comparisons = [{"TICKET": t, "TRANSFORM": int(scores[i]), "DIRECT_7SUBSET": v}
                       for i, t, v in zip(probes, tickets, direct)]
        mismatches = sum(x["TRANSFORM"] != x["DIRECT_7SUBSET"] for x in comparisons)
        if mismatches:
            atomic_json(RUN / "parity-failure.json", {"DEPTH": depth, "COMPARISONS": comparisons})
            raise RuntimeError("REAL_CONDITIONAL_PARITY_MISMATCH")
        contexts.append({"CONDITIONING_REPLACEMENTS": removed[:depth], "FROZEN_PORTFOLIO_SHA256": portfolio_sha(frozen),
                         "CANONICAL_COUNT": official, "ENUMERATION": stats, "COMPARISONS": comparisons})
        print(compact({"PARITY_DEPTH": depth + 1, "CHECKS": len(comparisons), "MISMATCHES": mismatches}), flush=True)
    record = {"CHECKS": 210, "PARITY_MISMATCHES": 0, "STATUS": "PASS", "SCIENCE_SHA256": digest(science_hashes()),
              "CONDITIONAL_ENUMERATIONS": 3, "GLOBAL_TICKETS_SCORED": 3 * TOTAL,
              "ORACLE": "independent brute-force 7-subset conditional marginals, plus official main-draw/special recount for each real context",
              "CONTEXTS": contexts}
    atomic_json(path, record, immutable=True)
    return record


def expansion(native, remaining, parent, sample, prefix, depth, contract_sha):
    path = RUN / "enumerations" / prefix / f"{depth}-{parent['SHA256']}.json"
    if path.exists():
        row = json.loads(path.read_text())
        if row.get("PAYLOAD_SHA256") != digest({k: v for k, v in row.items() if k != "PAYLOAD_SHA256"}):
            raise RuntimeError("ENUMERATION_CHECKSUM_MISMATCH")
        if row["PARENT_SHA256"] != parent["SHA256"] or row["CONTRACT_SHA256"] != contract_sha or row["DEPTH"] != depth:
            raise RuntimeError("ENUMERATION_RESUME_IDENTITY_CONFLICT")
        verify_identities(row["ENUMERATION"], parent["COVERAGE7"])
        return row
    frozen = portfolio(tuple(remaining) + tuple(tuple(t) for t in parent["TICKETS"]))
    scores, stats = native.score(frozen)
    verify_identities(stats, parent["COVERAGE7"])
    # All tickets were scored. Duplicates are excluded only at expansion selection.
    for ticket in frozen:
        scores[native.index(ticket)] = -1
    threshold = int(np.partition(scores, TOTAL - TOP_NEXT)[TOTAL - TOP_NEXT])
    indices = np.flatnonzero(scores >= threshold)
    children = [state(remaining, tuple(tuple(t) for t in parent["TICKETS"]) + (native.ticket(int(i)),),
                      parent["COVERAGE7"] + int(scores[i]), sample) for i in indices]
    selected, diversity = choose(children, TOP_NEXT)
    if len(selected) != TOP_NEXT:
        raise RuntimeError("TOP_NEXT_CARDINALITY_FAILURE")
    row = {"PARENT_SHA256": parent["SHA256"], "CONTRACT_SHA256": contract_sha, "DEPTH": depth,
           "ENUMERATION": stats, "TOP_NEXT_THRESHOLD": threshold, "THRESHOLD_ELIGIBLE_TICKETS": len(children),
           "CHILDREN": selected, "GENERATED": len(selected), "DIVERSITY": diversity}
    row["PAYLOAD_SHA256"] = digest(row)
    atomic_json(path, row, immutable=True)
    print(compact({"TRIPLE": prefix, "DEPTH": depth, "PARENT": parent["SHA256"][:12],
                   "SECONDS": stats["SECONDS"], "THRESHOLD_TIES": len(children)}), flush=True)
    return row


def completed_rows(triples, contract_sha):
    rows = []
    for number, positions in enumerate(triples):
        prefix = f"{number+1:02d}-" + "-".join(map(str, positions))
        path = RUN / "triples" / f"{prefix}.json"
        if not path.exists():
            break
        row = json.loads(path.read_text())
        if row.get("PAYLOAD_SHA256") != digest({k: v for k, v in row.items() if k != "PAYLOAD_SHA256"}):
            raise RuntimeError("TRIPLE_CHECKSUM_MISMATCH")
        if row["POSITIONS"] != positions or row["CONTRACT_SHA256"] != contract_sha or row["STATUS"] != "COMPLETED":
            raise RuntimeError("TRIPLE_CHECKPOINT_IDENTITY_CONFLICT")
        rows.append(row)
    return rows


def summary(rows, start, parity):
    incumbent = {"TICKETS": [], "COVERAGE7": START_COUNT // 7, "SHA256": START_SHA,
                 "PORTFOLIO": start, "POSITIONS": None}
    candidates = [incumbent] + [x["BEST"] for x in rows]
    best = min(candidates, key=lambda x: (-x["COVERAGE7"], x["SHA256"]))
    keys = ["CONDITIONAL_ENUMERATIONS", "BEAM_STATES_GENERATED", "BEAM_STATES_RETAINED", "TIE_GROUPS", "DIVERSITY_SAVES"]
    counts = {k: sum(x[k] for x in rows) for k in keys}
    return {"TASK_ID": TASK, "RUN_ID": "run1", "SOURCE_COMMIT": SOURCE_COMMIT, "START_COUNT": START_COUNT,
            "START_SHA256": START_SHA, "DESTROY_TRIPLES_COMPLETED": len(rows), "DESTROY_TRIPLES_EXPECTED": 32,
            **counts, "GLOBAL_TICKETS_SCORED": counts["CONDITIONAL_ENUMERATIONS"] * TOTAL,
            "PARITY_CHECKS": parity["CHECKS"], "PARITY_MISMATCHES": parity["PARITY_MISMATCHES"],
            "PARITY_CONDITIONAL_ENUMERATIONS": parity["CONDITIONAL_ENUMERATIONS"],
            "PARITY_GLOBAL_TICKETS_SCORED": parity["GLOBAL_TICKETS_SCORED"],
            "BEST_COUNT": 7 * best["COVERAGE7"], "BEST_DELTA": 7 * best["COVERAGE7"] - START_COUNT,
            "BEST_SHA256": best["SHA256"], "BEST_NEW_TICKETS": best["TICKETS"],
            "BEST_PORTFOLIO": best["PORTFOLIO"], "BEST_DESTROY_INDICES": best["POSITIONS"],
            "BEST_CANONICAL_RECOUNT_STATUS": "NOT_RUN", "TASK_STATUS": "IN_PROGRESS",
            "SCIENTIFIC_RESULT": "IN_PROGRESS", "SCIENTIFIC_SCOPE": "HEURISTIC_NOT_COMPLETE_N3_OPTIMUM",
            "ACCOUNTING_DEFINITIONS": {"CONDITIONAL_ENUMERATIONS": "completed search expansions, excluding the three separately reported parity enumerations",
                                      "GLOBAL_TICKETS_SCORED": "search conditional enumerations times 13983816; includes duplicate tickets scored before post-scoring exclusion",
                                      "BEAM_STATES_GENERATED": "24 selected children per parent before cross-parent canonical deduplication",
                                      "BEAM_STATES_RETAINED": "sum of retained nonempty states at depths 1,2,3",
                                      "TIE_GROUPS": "equal-coverage groups encountered in top-next and beam selection",
                                      "DIVERSITY_SAVES": "retained members absent from SHA-only truncation of the same coverage group"}}


def run():
    lock_path = RUN / "execution.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("SINGLE_WRITER_ALREADY_ACTIVE") from None
        source, start = source_document()
        contract = json.loads((RUN / "execution-contract.json").read_text())
        if (contract["WORKTREE"] != str(ROOT) or contract["SCIENTIFIC_SOURCE_SHA256"] != science_hashes()
                or contract["NATIVE_SHA256"] != file_sha(NATIVE)):
            raise RuntimeError("SCIENCE_OR_WORKTREE_IDENTITY_CONFLICT")
        selection = json.loads((RUN / "destroy-triples.json").read_text())
        if file_sha(RUN / "destroy-triples.json") != contract["SELECTION_SHA256"]:
            raise RuntimeError("FROZEN_SELECTION_CONFLICT")
        triples = selection["DESTROY_TRIPLES"]
        if len(triples) != 32 or digest(triples) != selection["DESTROY_TRIPLES_SHA256"]:
            raise RuntimeError("FROZEN_TRIPLES_CARDINALITY_OR_IDENTITY_FAILURE")
        contract_sha = file_sha(RUN / "execution-contract.json")
        if RESULT.exists():
            result = json.loads(RESULT.read_text())
            if result.get("EXECUTION_CONTRACT_SHA256") != contract_sha or result.get("TASK_STATUS") != "COMPLETED":
                raise RuntimeError("TERMINAL_RESULT_CONFLICT")
            print(compact({"REUSED_COMPLETED_RUN": True, "BEST_COUNT": result["BEST_COUNT"]}), flush=True)
            return
        free = shutil.disk_usage(RUN).free
        if free < 10 * (1 << 30):
            raise RuntimeError("PRELAUNCH_FREE_DISK_BELOW_10_GIB")
        rows = completed_rows(triples, contract_sha)
        attempt = {"PID": os.getpid(), "FREE_DISK_BYTES": free, "CONTRACT_SHA256": contract_sha,
                   "RESUMED_COMPLETED_TRIPLES": len(rows), "STARTED_AT_UTC": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        atomic_json(RUN / "active-attempt.json", attempt)
        print(compact({"STARTED": attempt}), flush=True)
        native = Native()
        try:
            parity = real_parity(native, source, start, triples)
            sample = signature_sample()
            source_rows = {tuple(x["POSITIONS"]): x for x in source["PER_DESTROY_TRIPLE"]}
            for number in range(len(rows), 32):
                positions = triples[number]
                prefix = f"{number+1:02d}-" + "-".join(map(str, positions))
                path = RUN / "triples" / f"{prefix}.json"
                remaining = tuple(t for i, t in enumerate(start) if i not in positions)
                probes = residual_sample(sample, remaining)
                base_count = source_rows[tuple(positions)]["FROZEN_REMAINDER_CANONICAL_COUNT"]
                if len(remaining) != 17 or base_count % 7:
                    raise RuntimeError("FROZEN_REMAINDER_INVARIANT_FAILURE")
                retained = [state(remaining, (), base_count // 7, probes)]
                enumerations = generated = kept = ties = saves = 0
                layers = []
                for depth in range(1, 4):
                    children = []
                    for parent in retained:
                        expanded = expansion(native, remaining, parent, probes, prefix, depth, contract_sha)
                        children.extend(expanded["CHILDREN"])
                        enumerations += 1
                        generated += expanded["GENERATED"]
                        ties += expanded["DIVERSITY"]["TIE_GROUPS"]
                        saves += expanded["DIVERSITY"]["DIVERSITY_SAVES"]
                    retained, diversity = choose(children, BEAM_WIDTH)
                    kept += len(retained)
                    ties += diversity["TIE_GROUPS"]
                    saves += diversity["DIVERSITY_SAVES"]
                    layers.append({"DEPTH": depth, "GENERATED": len(children), "RETAINED": retained,
                                   "DIVERSITY": diversity})
                best = dict(min(retained, key=lambda x: (-x["COVERAGE7"], x["SHA256"])))
                best["PORTFOLIO"] = portfolio(remaining + tuple(tuple(t) for t in best["TICKETS"]))
                best["POSITIONS"] = positions
                row = {"POSITIONS": positions, "STATUS": "COMPLETED", "CONTRACT_SHA256": contract_sha,
                       "R_SHA256": portfolio_sha(remaining), "R_COUNT": base_count, "SIGNATURE_RESIDUAL_PROBES": int(probes.size),
                       "CONDITIONAL_ENUMERATIONS": enumerations, "BEAM_STATES_GENERATED": generated,
                       "BEAM_STATES_RETAINED": kept, "TIE_GROUPS": ties, "DIVERSITY_SAVES": saves,
                       "BEST": best, "LAYERS": layers}
                row["PAYLOAD_SHA256"] = digest(row)
                atomic_json(path, row, immutable=True)
                rows.append(row)
                checkpoint = summary(rows, start, parity)
                checkpoint["COMPLETED_TRIPLE_FILE_SHA256"] = {p.name: file_sha(p) for p in sorted((RUN / "triples").glob("*.json"))}
                checkpoint["EXECUTION_CONTRACT_SHA256"] = contract_sha
                atomic_json(RUN / "checkpoint.json", checkpoint)
                print(compact({"CHECKPOINT_COMPLETED_TRIPLES": len(rows), "BEST_COUNT": checkpoint["BEST_COUNT"],
                               "ENUMERATIONS": checkpoint["CONDITIONAL_ENUMERATIONS"]}), flush=True)
            result = summary(rows, start, parity)
            _, _, oracle = donor_modules()
            recount = oracle.evaluate_portfolio(result["BEST_PORTFOLIO"]).official_any_prize_outcome_count
            if recount != result["BEST_COUNT"] or portfolio_sha(result["BEST_PORTFOLIO"]) != result["BEST_SHA256"]:
                raise RuntimeError("GLOBAL_BEST_CANONICAL_RECOUNT_MISMATCH")
            if len(rows) != 32 or parity["CHECKS"] < 200 or parity["PARITY_MISMATCHES"]:
                raise RuntimeError("TERMINAL_ACCEPTANCE_NOT_SATISFIED")
            result.update({"TASK_STATUS": "COMPLETED", "SCIENTIFIC_RESULT": "IMPROVED" if recount > START_COUNT else "NO_IMPROVEMENT_IN_32_SET_CONDITIONAL_DESTROY3_BEAM",
                           "BEST_CANONICAL_RECOUNT": recount, "BEST_CANONICAL_RECOUNT_STATUS": "PASS",
                           "CANONICAL_RECOUNTER": "pinned evaluate_portfolio: independently enumerate main draws and legal special outcomes",
                           "EXECUTION_CONTRACT": contract, "EXECUTION_CONTRACT_SHA256": contract_sha,
                           "SELECTION": selection, "PARITY_EVIDENCE_SHA256": file_sha(RUN / "parity-result.json"),
                           "PER_DESTROY_TRIPLE": [{k: v for k, v in x.items() if k != "LAYERS"} for x in rows],
                           "COMPLETED_TRIPLE_FILE_SHA256": {p.name: file_sha(p) for p in sorted((RUN / "triples").glob("*.json"))},
                           "TERMINAL_AT_UTC": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "PROJECT_MEMORY_WRITTEN": "NO", "PRODUCTION_CHANGE": "NONE", "PUSH": "NO", "PR": "NO", "MERGE": "NO"})
            atomic_json(RESULT, result, immutable=True)
            atomic_json(RUN / "checkpoint.json", result)
            print(compact({k: v for k, v in result.items() if not isinstance(v, (list, dict))}), flush=True)
        finally:
            native.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "run"])
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        run()


if __name__ == "__main__":
    main()
