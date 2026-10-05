"""Durable lexicographic orchestration around the byte-identical sealed pilot.

No scientific function is copied, patched, or replaced. The original score_destroy
owns scoring, pool construction, exact enumeration, legality, and SHA tie breaking.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import itertools
import json
import math
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
TASK_ID = "B649_K20_V7_DESTROY3_GLOBAL_POOL_EXHAUSTIVE_R1"
SEALED_COMMIT = "e7b472a97c4ab6c87a3f40211b9d97aaaa705b7b"
SEALED_SHA = "d233d6ab14efae0813055cf29699c7dc2a29c33769d1a328d066d845bb6ae078"
PILOT_REL = ".task-data/B649_K20_V7_THREE_TICKET_GLOBAL_REPAIR_PILOT_R1/run1"
PILOT = ROOT / PILOT_REL
PILOT_RESULT_REL = "docs/research/matrix-native-results/b649-k20-v7-three-ticket-global-repair-pilot-r1-result.json"
RESULT_REL = "docs/research/matrix-native-results/b649-k20-v7-destroy3-global-pool-exhaustive-r1-result.json"
RESULT = ROOT / RESULT_REL
CONTRACT = RUN / "execution-contract.json"
STATE = RUN / "state.json"
JOURNAL = RUN / "set-results.jsonl"
START_COUNT = 313239661
START_SHA = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
TRIPLES = tuple(itertools.combinations(range(20), 3))
UNIVERSE_SIZE = 13983816
THREAD_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
}
OWNER_PATH = Path("/Users/kelvin/.codex/attachments/814aa4ee-3d23-48d7-a9b3-ef1307739aba/pasted-text-1.txt")


def encoded(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path, value):
    require(not path.is_symlink(), f"unsafe output: {path}")
    temporary = path.with_name(path.name + ".tmp")
    require(not temporary.is_symlink(), f"unsafe temporary: {temporary}")
    with temporary.open("wb") as stream:
        stream.write(encoded(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_dir(path.parent)


@contextlib.contextmanager
def writer_lock(path):
    require(not path.is_symlink(), "unsafe writer lock")
    with path.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def peak_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def hash_matches(path, expected):
    require(path.is_file() and not path.is_symlink(), f"missing/unsafe source: {path}")
    require(sha(path.read_bytes()) == expected, f"SOURCE_IDENTITY_MISMATCH:{path}")


def load_pilot():
    spec = importlib.util.spec_from_file_location("sealed_three_ticket_pilot", PILOT / "driver.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sealed_identity():
    blob = subprocess.check_output(["git", "show", f"{SEALED_COMMIT}:{PILOT_RESULT_REL}"], cwd=ROOT)
    require(sha(blob) == SEALED_SHA, "SEALED_RESULT_SHA_MISMATCH")
    document = json.loads(blob)
    sources = {}
    driver_rel = PILOT_REL + "/driver.py"
    sources[driver_rel] = document["DRIVER_SHA256"]
    for name, expected in document["REUSED_ENGINE_SHA256"].items():
        sources[PILOT_REL + "/engine/src/lottolab/research/" + name] = expected
    sources[PILOT_REL + "/engine/src/lottolab/__init__.py"] = document["REUSED_ENGINE_SHA256"]["__init__.py"]
    sources["src/lottolab/research/b649_official_any_prize_exact.py"] = document["REUSED_ENGINE_SHA256"]["b649_official_any_prize_exact.py"]
    for relative, expected in sources.items():
        hash_matches(ROOT / relative, expected)
        # The official engine file was an ignored exact copy in the pilot. Its
        # committed canonical source independently binds its frozen bytes.
        committed = relative
        if relative.endswith("/research/b649_official_any_prize_exact.py"):
            committed = "src/lottolab/research/b649_official_any_prize_exact.py"
        frozen = subprocess.check_output(["git", "show", f"{SEALED_COMMIT}:{committed}"], cwd=ROOT)
        require(sha(frozen) == expected, f"SEALED_SOURCE_MISMATCH:{relative}")
    require(document["START_SHA256"] == START_SHA and document["START_COUNT"] == START_COUNT,
            "PILOT_START_MISMATCH")
    require(document["GLOBAL_TOP_MARGINAL"] == 64 and document["REPAIR_POOL_MAX"] == 80,
            "PILOT_POOL_RULE_MISMATCH")
    require(document["PARITY_MISMATCHES"] == 0, "PILOT_PARITY_FAILED")
    return document, sources


def validate_row(row, positions, start, elites, pilot):
    exact = pilot.exact
    require(tuple(row["POSITIONS"]) == tuple(positions), "DESTROY_ORDER_MISMATCH")
    remaining = tuple(ticket for i, ticket in enumerate(start) if i not in positions)
    removed = tuple(start[i] for i in positions)
    require(row["R_SIZE"] == 17 and row["REMOVED_TICKETS"] == [list(t) for t in removed],
            "FROZEN_START_MISMATCH")
    require(row["TICKETS_SCORED"] == UNIVERSE_SIZE and row["GLOBAL_IDENTITIES"]["PASS"] is True,
            "INCOMPLETE_GLOBAL_SCORE")
    identities = row["GLOBAL_IDENTITIES"]
    require(identities["TICKETS_EXPECTED"] == UNIVERSE_SIZE and identities["TICKETS_SCORED"] == UNIVERSE_SIZE,
            "GLOBAL_UNIVERSE_MISMATCH")
    for key in ("SUM_TOP_COUNTS", "SUM_MARGINALS"):
        require(identities[key] == identities[key + "_EXPECTED"], "GLOBAL_IDENTITY_FAILED")
    top = [tuple(item["TICKET"]) for item in row["GLOBAL_TOP64"]]
    require(len(top) == 64 and len(set(top)) == 64 and not set(top).intersection(remaining),
            "INVALID_TOP64")
    ordering = [(-item["RESIDUAL_MARGINAL_7SUBSETS"], tuple(item["TICKET"])) for item in row["GLOBAL_TOP64"]]
    require(ordering == sorted(ordering), "GLOBAL_TOP64_TIE_ORDER_MISMATCH")
    require([item["RANK"] for item in row["GLOBAL_TOP64"]] == list(range(1, 65)), "TOP64_RANK_MISMATCH")
    base = set(top) | set(removed)
    eligible = set(elites) - set(remaining) - base
    added = [tuple(item["TICKET"]) for item in row["ELITE_TICKETS_ADDED"]]
    capacity = 80 - len(base)
    require(len(eligible) <= capacity, "UNEXPECTED_ELITE_CAPACITY_TRUNCATION")
    require(set(added) == eligible and len(added) == len(eligible), "ELITE_POOL_MISMATCH")
    elite_order = [(-item["RESIDUAL_MARGINAL_7SUBSETS"], tuple(item["TICKET"])) for item in row["ELITE_TICKETS_ADDED"]]
    require(elite_order == sorted(elite_order), "ELITE_TIE_ORDER_MISMATCH")
    pool = tuple(tuple(item["TICKET"]) for item in row["POOL_SOURCES"])
    require(pool == tuple(sorted(base | eligible)) and len(pool) == row["POOL_SIZE"] <= 80,
            "POOL_RETENTION_MISMATCH")
    expected_sources = {t: "GLOBAL_TOP64" for t in top}
    expected_sources.update({t: "REMOVED_INCUMBENT" for t in removed})
    expected_sources.update({t: "STABLE_ELITE" for t in added})
    require(all(item["SOURCE"] == expected_sources[tuple(item["TICKET"])] for item in row["POOL_SOURCES"]),
            "POOL_SOURCE_MISMATCH")
    require(row["GLOBAL_TOP64_DROPPED_FOR_ELITES"] == 0, "TOP64_DROPPED")
    require(row["PROVEN_OPTIMALITY_STATUS"] == "PROVEN_OPTIMAL", "UNPROVEN_REPAIR")
    leaves = math.comb(len(pool), 3)
    require(row["EXACT_CANDIDATE_TRIPLES_EVALUATED"] == row["EXACT_CANDIDATE_TRIPLES_EXPECTED"] == leaves,
            "INCOMPLETE_EXACT_SOLVE")
    count = (row["HISTOGRAM_COVERED_BY_R"] + row["BEST_RESIDUAL_SUBSETS"]) * 7
    require(row["FROZEN_REMAINDER_CANONICAL_COUNT"] == row["HISTOGRAM_COVERED_BY_R"] * 7,
            "REMAINDER_COUNT_MISMATCH")
    require(row["BEST_COUNT"] == count >= START_COUNT and row["BEST_DELTA"] == count - START_COUNT,
            "BEST_COUNT_MISMATCH")
    candidates = row["CANONICALLY_RECOUNTED_OPTIMA"]
    require(row["ALL_OPTIMAL_SETS_CANONICALLY_RECOUNTED"] is True and len(candidates) == row["OPTIMAL_SET_COUNT"] > 0,
            "MISSING_OPTIMAL_RECOUNTS")
    seen = set()
    for candidate in candidates:
        indices = tuple(candidate["POOL_INDICES"])
        require(len(indices) == 3 and indices == tuple(sorted(set(indices))) and indices not in seen,
                "INVALID_OPTIMAL_INDICES")
        seen.add(indices)
        replacements = tuple(pool[i] for i in indices)
        portfolio = exact.normalize_portfolio((*remaining, *replacements))
        require(len(portfolio) == 20 and len(set(portfolio)) == 20, "ILLEGAL_PORTFOLIO")
        require(candidate["REPLACEMENTS"] == [list(t) for t in replacements] and
                candidate["PORTFOLIO"] == [list(t) for t in portfolio] and
                candidate["DESTROY_POSITIONS"] == list(positions) and
                candidate["PORTFOLIO_SHA256"] == exact.portfolio_sha256(portfolio) and
                candidate["CANONICAL_COUNT"] == count, "OPTIMAL_PORTFOLIO_MISMATCH")
    best = min(candidates, key=lambda item: (item["PORTFOLIO_SHA256"], item["POOL_INDICES"]))
    require(row["BEST_PORTFOLIO_SHA256"] == best["PORTFOLIO_SHA256"] and
            row["BEST_REPLACEMENTS"] == best["REPLACEMENTS"], "BEST_SHA_TIE_BREAK_MISMATCH")


def reusable_records(document, start, elites, pilot):
    rows = document["PER_DESTROY_TRIPLE"]
    require(len(rows) == 64 and document["PROVEN_OPTIMAL_REPAIR_SETS"] == 64, "PILOT_NOT_TERMINAL")
    positions = [row["POSITIONS"] for row in rows]
    require(positions == document["DESTROY_TRIPLES"] and sha(encoded(positions)) ==
            document["DESTROY_TRIPLES_SAMPLE_SHA256"], "PILOT_TRIPLE_IDENTITY_MISMATCH")
    require(positions == sorted(positions) and len({tuple(p) for p in positions}) == 64,
            "DUPLICATE_PILOT_TRIPLES")
    result = {}
    for row in rows:
        key = tuple(row["POSITIONS"])
        require(key in TRIPLES, "PILOT_TRIPLE_OUT_OF_SCOPE")
        validate_row(row, key, start, elites, pilot)
        result[key] = row
    return result


class Journal:
    """Append-only, fsynced terminal records with a SHA-bound durable prefix."""
    def __init__(self, directory, contract_sha, triples, validator):
        self.directory = directory
        self.path = directory / "set-results.jsonl"
        self.state_path = directory / "state.json"
        self.contract_sha = contract_sha
        self.triples = triples
        self.validator = validator
        self.rows = []
        self.state = json.loads(self.state_path.read_bytes())
        require(self.state["CONTRACT_SHA256"] == contract_sha, "STATE_CONTRACT_MISMATCH")
        data = self.path.read_bytes() if self.path.exists() else b""
        prefix_size = self.state["JOURNAL_PREFIX_BYTES"]
        require(len(data) >= prefix_size and sha(data[:prefix_size]) == self.state["JOURNAL_PREFIX_SHA256"],
                "JOURNAL_PREFIX_SHA_MISMATCH")
        require(prefix_size == 0 or data[prefix_size - 1:prefix_size] == b"\n", "INVALID_PREFIX_BOUNDARY")
        durable_lines = data[:prefix_size].splitlines()
        require(len(durable_lines) == self.state["COMPLETED_COUNT"], "STATE_COUNT_MISMATCH")
        end = data.rfind(b"\n") + 1
        for line in data[:end].splitlines():
            entry = json.loads(line)
            self.check(entry)
            self.rows.append(entry)
        if end != len(data):
            tail = data[end:]
            quarantine = directory / ("interrupted-tail-" + sha(tail) + ".bin")
            if not quarantine.exists():
                with quarantine.open("xb") as stream:
                    stream.write(tail)
                    stream.flush()
                    os.fsync(stream.fileno())
            else:
                require(quarantine.read_bytes() == tail, "TAIL_QUARANTINE_MISMATCH")
            with self.path.open("r+b") as stream:
                stream.truncate(end)
                stream.flush()
                os.fsync(stream.fileno())
            sync_dir(directory)

    def check(self, entry):
        n = len(self.rows)
        require(n < len(self.triples) and entry["SEQUENCE"] == n and
                entry["CONTRACT_SHA256"] == self.contract_sha, "JOURNAL_ORDER_OR_CONTRACT_MISMATCH")
        require(entry["ORIGIN"] in ("PILOT_REUSED", "NEWLY_COMPUTED"), "INVALID_RECORD_ORIGIN")
        require(entry["RECORD_SHA256"] == sha(encoded(entry["RECORD"])), "RECORD_SHA_MISMATCH")
        self.validator(entry["RECORD"], self.triples[n], entry["ORIGIN"])

    def append(self, row, origin):
        entry = {"SEQUENCE": len(self.rows), "CONTRACT_SHA256": self.contract_sha,
                 "ORIGIN": origin, "RECORD_SHA256": sha(encoded(row)), "RECORD": row}
        self.check(entry)
        with self.path.open("ab") as stream:
            stream.write(encoded(entry) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        sync_dir(self.directory)
        self.rows.append(entry)

    def checkpoint(self, **extra):
        data = self.path.read_bytes() if self.path.exists() else b""
        records = [entry["RECORD"] for entry in self.rows]
        count = len(records)
        self.state.update({
            "COMPLETED_COUNT": count, "DESTROY_TRIPLES_COMPLETED": count,
            "PROVEN_OPTIMAL_TRIPLES": sum(r["PROVEN_OPTIMALITY_STATUS"] == "PROVEN_OPTIMAL" for r in records),
            "REUSED_PILOT_TRIPLES": sum(e["ORIGIN"] == "PILOT_REUSED" for e in self.rows),
            "NEWLY_COMPUTED_TRIPLES": sum(e["ORIGIN"] == "NEWLY_COMPUTED" for e in self.rows),
            "GLOBAL_TICKETS_SCORED": sum(r["TICKETS_SCORED"] for r in records),
            "EXACT_LEAVES_SCORED": sum(r["EXACT_CANDIDATE_TRIPLES_EVALUATED"] for r in records),
            "NODES_EXPLORED": sum(r["EXACT_CANDIDATE_TRIPLES_EVALUATED"] for r in records),
            "NODES_PRUNED": 0,
            "BEST_COUNT": max([START_COUNT, *[r["BEST_COUNT"] for r in records]]),
            "NEXT_INCOMPLETE_TRIPLE": list(self.triples[count]) if count < len(self.triples) else None,
            "JOURNAL_PREFIX_BYTES": len(data), "JOURNAL_PREFIX_SHA256": sha(data),
            "UPDATED_AT_UTC": utc(),
        })
        self.state.update(extra)
        atomic_json(self.state_path, self.state)


def exact_argv():
    return ["/usr/bin/env", *[f"{key}={value}" for key, value in THREAD_ENV.items()],
            str(ROOT / ".venv/bin/python"), "-u", str(Path(__file__).resolve()), "run"]


def prepare():
    with writer_lock(RUN / "execution.lock"):
        require(not CONTRACT.exists() and not STATE.exists() and not JOURNAL.exists() and not RESULT.exists(),
                "CAMPAIGN_ALREADY_EXISTS")
        require(git("rev-parse", "HEAD") == SEALED_COMMIT, "PREPARE_HEAD_MISMATCH")
        require(not git("diff", "--name-only") and not git("diff", "--cached", "--name-only"),
                "TRACKED_OR_STAGED_WORK_PRESENT")
        document, sources = sealed_identity()
        pilot = load_pilot()
        start = pilot.current_start()
        elite_records, elites = pilot.verify_elites(start)
        require(elite_records == document["ELITE_SOURCE_VERIFICATION"], "ELITE_SOURCE_IDENTITY_MISMATCH")
        reused = reusable_records(document, start, elites, pilot)
        recounter = pilot.exact.CanonicalRecounter()
        count = recounter.count(start)
        require(count == START_COUNT and pilot.exact.portfolio_sha256(start) == START_SHA,
                "START_CANONICAL_RECOUNT_FAILED")
        sources["src/lottolab/application/b649_sealed_geometry_portfolio.py"] = sha(
            (ROOT / "src/lottolab/application/b649_sealed_geometry_portfolio.py").read_bytes())
        owner = OWNER_PATH.read_bytes()
        owner_copy = RUN / "owner-authorization.txt"
        require(not owner_copy.exists(), "OWNER_COPY_ALREADY_EXISTS")
        with owner_copy.open("xb") as stream:
            stream.write(owner)
            stream.flush()
            os.fsync(stream.fileno())
        tests = RUN / "test_accounting.py"
        test_evidence = json.loads((RUN / "accounting-test-result.json").read_bytes())
        require(test_evidence["STATUS"] == "PASS" and test_evidence["TEST_SOURCE_SHA256"] == sha(tests.read_bytes()) and
                test_evidence["ORCHESTRATOR_SOURCE_SHA256"] == sha(Path(__file__).read_bytes()),
                "FOCUSED_ACCOUNTING_TESTS_NOT_PASSED")
        contract = {
            "SCHEMA_VERSION": "B649_DESTROY3_EXECUTION_CONTRACT_V1", "TASK_ID": TASK_ID,
            "TASK_CLASS": "STATE_CHANGING_IMPLEMENTATION", "WORKER_ROUTE": "STANDARD",
            "IMPLEMENTATION_DEPTH": "ENHANCED", "DEPTH_SOURCE": "PLANNER_SUPPLIED",
            "JUDGE_MODE": "NOT_APPLICABLE", "JUDGE_DISPATCH": "SUPPRESSED",
            "OWNER_AUTHORIZATION_PATH": str(owner_copy), "OWNER_AUTHORIZATION_SHA256": sha(owner),
            "LAUNCH_METHOD": "FROZEN_DIRECT_LOCAL_ARGV",
            "LAUNCHER_STATUS": "ABSENT_PROVEN_BEFORE_EXECUTION",
            "LAUNCHER_CHECKED_ROOTS": ["/Users/kelvin/.codex/skills/fable-method", "/Users/kelvin/Documents/ChatGPT/共用Skill專案"],
            "EFFECT_CLASSIFICATION": "LOCAL_ONLY_NO_HIGH_RISK",
            "EXACT_ARGV": exact_argv(), "WORKTREE": str(ROOT),
            "SOURCE_HEAD": git("rev-parse", "HEAD"), "SOURCE_TREE": git("rev-parse", "HEAD^{tree}"),
            "SOURCE_BRANCH": git("branch", "--show-current"),
            "SEALED_RESULT_COMMIT": SEALED_COMMIT, "SEALED_RESULT_SHA256": SEALED_SHA,
            "SCIENTIFIC_SOURCE_SHA256": sources,
            "ORCHESTRATOR_SHA256": sha(Path(__file__).read_bytes()),
            "ACCOUNTING_TEST_SOURCE_SHA256": sha(tests.read_bytes()),
            "FOCUSED_ACCOUNTING_EVIDENCE": test_evidence,
            "START_COUNT": count, "START_SHA256": START_SHA, "START_PORTFOLIO": [list(t) for t in start],
            "START_CANONICAL_RECOUNT_STATUS": "PASS", "START_RECOUNT_AT_UTC": utc(),
            "FIXED_INCUMBENT": True, "DESTROY_SIZE": 3,
            "DESTROY_TRIPLES": [list(t) for t in TRIPLES], "DESTROY_TRIPLES_SHA256": sha(encoded(TRIPLES)),
            "SEARCH_ORDER": "0 <= i < j < k < 20; lexicographic, including imported rows at their original positions",
            "GLOBAL_TICKET_UNIVERSE": UNIVERSE_SIZE, "GLOBAL_TOP_MARGINAL": 64, "REPAIR_POOL_MAX": 80,
            "ELITE_SOURCE_VERIFICATION": elite_records, "STABLE_ELITE_TICKETS": [list(t) for t in elites],
            "POOL_RULE": "Byte-identical sealed pilot score_destroy: global exact top64, removed three, eligible stable v5/v6/v7 elites by exact marginal and ticket order, deduplicated and capped at80",
            "SOLVER": document["SOLVER"], "SOLVER_DETAIL": document["SOLVER_DETAIL"],
            "TIE_BREAK": document["TIE_BREAK"],
            "REUSABLE_PILOT_TRIPLES": len(reused),
            "REUSABLE_PILOT_RECORD_SHA256": {",".join(map(str, t)): sha(encoded(r)) for t, r in reused.items()},
            "PARITY_REUSE": {"STATUS": "REUSED_EXACT_SOURCE_EVIDENCE", "BYTE_IDENTICAL": True,
                             "SEALED_PARITY": document["PARITY"], "PARITY_MISMATCHES": 0},
            "SINGLE_WRITER": True, "CHECKPOINT_MAX_COMPLETED_INTERVAL": 1,
            "JOURNAL_PROTOCOL": "fsync each complete terminal row; atomic fsynced state SHA prefix each row; verify prefix, validate and adopt complete suffix; quarantine incomplete suffix only",
            "CPU_POLICY": {"WORKERS": 1, "THREAD_ENV": THREAD_ENV, "AUTO_SCALING": "FORBIDDEN"},
            "SCIENTIFIC_SCOPE": "COMPLETE_DESTROY3_GLOBAL_TOP64_POOL_FAMILY_ON_CANONICAL_V7",
            "SEAL_COMMIT_PATHS": [RESULT_REL, str(Path(__file__).relative_to(ROOT)),
                                  str(CONTRACT.relative_to(ROOT)), str(tests.relative_to(ROOT)),
                                  str((RUN / "accounting-test-result.json").relative_to(ROOT)),
                                  str(owner_copy.relative_to(ROOT))],
            "PROJECT_MEMORY_WRITE": "FORBIDDEN", "PUSH": "NO", "PR": "NO", "MERGE": "NO",
            "PRODUCTION_CHANGE": "NONE", "PREPARED_AT_UTC": utc(),
        }
        atomic_json(CONTRACT, contract)
        state = {"SCHEMA_VERSION": "B649_DESTROY3_STATE_V1", "TASK_ID": TASK_ID,
                 "CONTRACT_SHA256": sha(CONTRACT.read_bytes()), "PHASE": "PREPARED",
                 "COMPLETED_COUNT": 0, "DESTROY_TRIPLES_COMPLETED": 0,
                 "PROVEN_OPTIMAL_TRIPLES": 0, "REUSED_PILOT_TRIPLES": 0, "NEWLY_COMPUTED_TRIPLES": 0,
                 "JOURNAL_PREFIX_BYTES": 0, "JOURNAL_PREFIX_SHA256": sha(b""),
                 "NEXT_INCOMPLETE_TRIPLE": list(TRIPLES[0]), "PEAK_MEMORY_BYTES": peak_bytes(),
                 "CAMPAIGN_STARTED_UNIX": time.time(), "START_COUNT": count, "START_SHA256": START_SHA,
                 "BEST_COUNT": count, "UPDATED_AT_UTC": utc()}
        atomic_json(STATE, state)
        print(f"PREPARED start={count} sha={START_SHA} reusable={len(reused)} triples={len(TRIPLES)}", flush=True)


def verify_runtime(contract):
    require(str(ROOT) == contract["WORKTREE"] and exact_argv() == contract["EXACT_ARGV"], "ARGV_OR_WORKTREE_MISMATCH")
    for key, value in THREAD_ENV.items():
        require(os.environ.get(key) == value, f"THREAD_ENV_MISMATCH:{key}")
    hash_matches(Path(__file__), contract["ORCHESTRATOR_SHA256"])
    for relative, expected in contract["SCIENTIFIC_SOURCE_SHA256"].items():
        hash_matches(ROOT / relative, expected)
    hash_matches(RUN / "test_accounting.py", contract["ACCOUNTING_TEST_SOURCE_SHA256"])
    require(contract["DESTROY_TRIPLES"] == [list(t) for t in TRIPLES] and
            contract["DESTROY_TRIPLES_SHA256"] == sha(encoded(TRIPLES)), "SEARCH_FAMILY_MISMATCH")


def terminal_result(journal, contract, pilot):
    require(len(journal.rows) == 1140 and journal.state["PROVEN_OPTIMAL_TRIPLES"] == 1140,
            "TERMINAL_SEARCH_INCOMPLETE")
    records = [entry["RECORD"] for entry in journal.rows]
    optima = [item for row in records for item in row["CANONICALLY_RECOUNTED_OPTIMA"]]
    winner = min(optima, key=lambda item: (-item["CANONICAL_COUNT"], item["PORTFOLIO_SHA256"], item["DESTROY_POSITIONS"], item["POOL_INDICES"]))
    ties = [item for item in optima if item["CANONICAL_COUNT"] == winner["CANONICAL_COUNT"]]
    unique = {item["PORTFOLIO_SHA256"]: item for item in ties}
    recounter = pilot.exact.CanonicalRecounter()
    recounts = {}
    tie_recounts = []
    for item in ties:
        digest = item["PORTFOLIO_SHA256"]
        portfolio = tuple(tuple(t) for t in item["PORTFOLIO"])
        require(pilot.exact.portfolio_sha256(portfolio) == digest, "TERMINAL_TIE_SHA_MISMATCH")
        count = recounter.count(portfolio)
        require(count == winner["CANONICAL_COUNT"], "TERMINAL_CANONICAL_RECOUNT_MISMATCH")
        recounts[digest] = count
        tie_recounts.append({"PORTFOLIO_SHA256": digest, "DESTROY_POSITIONS": item["DESTROY_POSITIONS"],
                             "POOL_INDICES": item["POOL_INDICES"], "CANONICAL_RECOUNT": count})
        print(f"terminal_recount={len(tie_recounts)}/{len(ties)} count={count}", flush=True)
    require(all(recounts[t["PORTFOLIO_SHA256"]] == t["CANONICAL_COUNT"] for t in ties),
            "TERMINAL_TIE_NOT_RECOUNTED")
    total_tickets = sum(row["TICKETS_SCORED"] for row in records)
    require(total_tickets == 1140 * UNIVERSE_SIZE, "TERMINAL_TICKET_ACCOUNTING_MISMATCH")
    new_entries = [e for e in journal.rows if e["ORIGIN"] == "NEWLY_COMPUTED"]
    result = {
        "SCHEMA_VERSION": "B649_DESTROY3_GLOBAL_POOL_EXHAUSTIVE_RESULT_V1", "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE", "SCIENTIFIC_SCOPE": contract["SCIENTIFIC_SCOPE"],
        "SCIENTIFIC_RESULT": "IMPROVED" if winner["CANONICAL_COUNT"] > START_COUNT else "NO_IMPROVEMENT",
        "START_COUNT": START_COUNT, "START_SHA256": START_SHA, "FIXED_INCUMBENT": True,
        "DESTROY_TRIPLES_COMPLETED": 1140, "DESTROY_TRIPLES_EXPECTED": 1140,
        "PROVEN_OPTIMAL_TRIPLES": journal.state["PROVEN_OPTIMAL_TRIPLES"],
        "REUSED_PILOT_TRIPLES": journal.state["REUSED_PILOT_TRIPLES"],
        "NEWLY_COMPUTED_TRIPLES": journal.state["NEWLY_COMPUTED_TRIPLES"],
        "GLOBAL_TICKETS_SCORED": total_tickets,
        "NEW_GLOBAL_TICKETS_SCORED": sum(e["RECORD"]["TICKETS_SCORED"] for e in new_entries),
        "REUSED_GLOBAL_TICKETS_SCORED": total_tickets - sum(e["RECORD"]["TICKETS_SCORED"] for e in new_entries),
        "NODES_EXPLORED": journal.state["NODES_EXPLORED"], "NODES_PRUNED": 0,
        "EXACT_LEAVES_SCORED": journal.state["EXACT_LEAVES_SCORED"],
        "NODE_ACCOUNTING": "The sealed exhaustive solver visits complete replacement triples only. Each evaluated triple is one explored node and one exact leaf; it performs no pruning.",
        "WALL_SECONDS": round(time.time() - journal.state["CAMPAIGN_STARTED_UNIX"], 3),
        "WALL_SECONDS_DEFINITION": "Elapsed campaign wall time from prepared state through terminal recount, including any interruption; excludes historical pilot execution.",
        "NEW_SCIENTIFIC_RECORD_SECONDS": round(sum(e["RECORD"]["SECONDS_TOTAL"] for e in new_entries), 3),
        "REUSED_PILOT_RECORD_SECONDS": round(sum(e["RECORD"]["SECONDS_TOTAL"] for e in journal.rows if e["ORIGIN"] == "PILOT_REUSED"), 3),
        "PEAK_MEMORY_BYTES": max(journal.state["PEAK_MEMORY_BYTES"], peak_bytes()),
        "BEST_COUNT": winner["CANONICAL_COUNT"], "BEST_DELTA": winner["CANONICAL_COUNT"] - START_COUNT,
        "BEST_SHA256": winner["PORTFOLIO_SHA256"], "BEST_PORTFOLIO": winner["PORTFOLIO"],
        "BEST_DESTROY_INDICES": winner["DESTROY_POSITIONS"], "BEST_NEW_TICKETS": winner["REPLACEMENTS"],
        "BEST_TIE_COUNT": len(ties), "BEST_TIE_COUNT_DEFINITION": "Optimal replacement triples at global-best count, including occurrences in different destroy sets, as in the predecessor.",
        "BEST_TIE_UNIQUE_PORTFOLIO_COUNT": len(unique), "BEST_CANONICAL_RECOUNT_STATUS": "PASS",
        "BEST_CANONICAL_RECOUNT": recounts[winner["PORTFOLIO_SHA256"]],
        "GLOBAL_BEST_UNIQUE_CANONICAL_RECOUNTS": recounts,
        "GLOBAL_BEST_TIE_CANONICAL_RECOUNTS": tie_recounts,
        "GLOBAL_BEST_TIE_FRESH_CANONICAL_RECOUNT_COUNT": len(tie_recounts),
        "EVERY_GLOBAL_BEST_TIE_CANONICAL_RECOUNT_STATUS": "PASS",
        "TIE_RECOUNT_ACCOUNTING": "Fresh canonical recount for every global-best replacement triple occurrence, including repeated normalized portfolios in different destroy sets.",
        "GLOBAL_BEST_TIES": ties, "PER_DESTROY_TRIPLE": records,
        "ELITE_SOURCE_VERIFICATION": contract["ELITE_SOURCE_VERIFICATION"],
        "GLOBAL_TOP_MARGINAL": 64, "REPAIR_POOL_MAX": 80,
        "SOLVER": contract["SOLVER"], "SOLVER_DETAIL": contract["SOLVER_DETAIL"], "TIE_BREAK": contract["TIE_BREAK"],
        "PARITY_REUSE": contract["PARITY_REUSE"], "PARITY_MISMATCHES": 0,
        "FOCUSED_ACCOUNTING_EVIDENCE": contract["FOCUSED_ACCOUNTING_EVIDENCE"],
        "EXECUTION_CONTRACT": contract, "EXECUTION_CONTRACT_SHA256": journal.contract_sha,
        "JOURNAL_SHA256": sha(JOURNAL.read_bytes()), "JOURNAL_PATH": str(JOURNAL),
        "RESULT_LOCATOR": str(RESULT), "TERMINAL_VERIFIED_AT_UTC": utc(),
        "PROJECT_MEMORY_WRITTEN": "NO", "PRODUCTION_CHANGE": "NONE", "PUSH": "NO", "PR": "NO", "MERGE": "NO",
    }
    require(result["REUSED_PILOT_TRIPLES"] == 64 and result["NEWLY_COMPUTED_TRIPLES"] == 1076,
            "TERMINAL_REUSE_ACCOUNTING_MISMATCH")
    return result


def seal(journal, contract):
    result = json.loads(RESULT.read_bytes())
    require(result["EXECUTION_CONTRACT_SHA256"] == journal.contract_sha and
            result["JOURNAL_SHA256"] == sha(JOURNAL.read_bytes()) and
            result["DESTROY_TRIPLES_COMPLETED"] == result["PROVEN_OPTIMAL_TRIPLES"] == 1140 and
            result["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS", "UNVERIFIED_RESULT_CANNOT_BE_SEALED")
    paths = contract["SEAL_COMMIT_PATHS"]
    require(git("branch", "--show-current") == contract["SOURCE_BRANCH"], "SEAL_BRANCH_MISMATCH")
    # If interrupted after commit and before the receipt, recognize the exact
    # result already committed on this branch instead of creating a second seal.
    if git("rev-parse", "HEAD") != contract["SOURCE_HEAD"]:
        committed = subprocess.check_output(["git", "show", f"HEAD:{RESULT_REL}"], cwd=ROOT)
        require(committed == RESULT.read_bytes() and git("rev-parse", "HEAD^") == contract["SOURCE_HEAD"],
                "UNEXPLAINED_HEAD_CHANGE_AT_SEAL")
        commit = git("rev-parse", "HEAD")
    else:
        staged = set(git("diff", "--cached", "--name-only").splitlines())
        require(staged.issubset(set(paths)), "UNRELATED_STAGED_WORK_AT_SEAL")
        for path in staged:
            indexed = subprocess.check_output(["git", "show", f":{path}"], cwd=ROOT)
            require(indexed == (ROOT / path).read_bytes(), "SEAL_STAGED_BYTES_MISMATCH")
        subprocess.run(["git", "add", "--force", "--", *paths], cwd=ROOT, check=True)
        require(set(git("diff", "--cached", "--name-only").splitlines()) == set(paths), "SEAL_PATH_SCOPE_MISMATCH")
        subprocess.run(["git", "commit", "-m", "Seal B649 K20 V7 exhaustive destroy3 global-pool result"], cwd=ROOT, check=True)
        commit = git("rev-parse", "HEAD")
        require(git("rev-parse", "HEAD^") == contract["SOURCE_HEAD"], "SEAL_PARENT_MISMATCH")
        committed = subprocess.check_output(["git", "show", f"HEAD:{RESULT_REL}"], cwd=ROOT)
        require(committed == RESULT.read_bytes(), "SEAL_RESULT_BYTES_MISMATCH")
    receipt = {"TASK_ID": TASK_ID, "RESULT_COMMIT": commit, "RESULT_SHA256": sha(RESULT.read_bytes()),
               "RESULT_LOCATOR": str(RESULT), "SEALED_AT_UTC": utc()}
    atomic_json(RUN / "seal-receipt.json", receipt)
    journal.checkpoint(PHASE="COMPLETE_SEALED", ACTIVE_PID=None, RESULT_COMMIT=commit, RESULT_SHA256=receipt["RESULT_SHA256"],
                       PEAK_MEMORY_BYTES=max(journal.state["PEAK_MEMORY_BYTES"], peak_bytes()))
    print(f"SEALED commit={commit} result={result['SCIENTIFIC_RESULT']} best={result['BEST_COUNT']} delta={result['BEST_DELTA']}", flush=True)


def run():
    with writer_lock(RUN / "execution.lock"):
        contract = json.loads(CONTRACT.read_bytes())
        verify_runtime(contract)
        document, _ = sealed_identity()
        pilot = load_pilot()
        start = tuple(tuple(t) for t in contract["START_PORTFOLIO"])
        require(pilot.current_start() == start, "CANONICAL_START_CHANGED")
        elite_records, elites = pilot.verify_elites(start)
        require(elite_records == contract["ELITE_SOURCE_VERIFICATION"], "ELITES_CHANGED")
        reused = reusable_records(document, start, elites, pilot)

        def validator(row, positions, origin):
            validate_row(row, positions, start, elites, pilot)
            if origin == "PILOT_REUSED":
                require(positions in reused and encoded(row) == encoded(reused[positions]), "IMPORTED_RECORD_CHANGED")
            else:
                require(positions not in reused, "PILOT_TRIPLE_RECOMPUTED")

        journal = Journal(RUN, sha(CONTRACT.read_bytes()), TRIPLES, validator)
        if journal.state["PHASE"] == "COMPLETE_SEALED":
            seal(journal, contract)
            return
        journal.checkpoint(PHASE="SEARCHING", ACTIVE_PID=os.getpid(), PEAK_MEMORY_BYTES=max(journal.state["PEAK_MEMORY_BYTES"], peak_bytes()))
        print(f"RESUME completed={len(journal.rows)}/1140 next={journal.state['NEXT_INCOMPLETE_TRIPLE']}", flush=True)
        if len(journal.rows) < len(TRIPLES):
            universe = pilot.core.build_universe()
            recounter = pilot.exact.CanonicalRecounter()
            for positions in TRIPLES[len(journal.rows):]:
                verify_runtime(contract)
                if positions in reused:
                    row, origin = reused[positions], "PILOT_REUSED"
                else:
                    row = pilot.score_destroy(positions, start, elites, universe, recounter)
                    origin = "NEWLY_COMPUTED"
                journal.append(row, origin)
                journal.checkpoint(PHASE="SEARCHING", PEAK_MEMORY_BYTES=max(journal.state["PEAK_MEMORY_BYTES"], peak_bytes()))
                print(f"complete={len(journal.rows)}/1140 positions={positions} origin={origin} pool={row['POOL_SIZE']} delta={row['BEST_DELTA']} global_best={journal.state['BEST_COUNT']}", flush=True)
        verify_runtime(contract)
        journal.checkpoint(PHASE="TERMINAL_VERIFYING", PEAK_MEMORY_BYTES=max(journal.state["PEAK_MEMORY_BYTES"], peak_bytes()))
        if not RESULT.exists():
            result = terminal_result(journal, contract, pilot)
            atomic_json(RESULT, result)
        journal.checkpoint(PHASE="COMPLETE_UNSEALED", RESULT_SHA256=sha(RESULT.read_bytes()))
        seal(journal, contract)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "run"))
    args = parser.parse_args()
    {"prepare": prepare, "run": run}[args.mode]()
