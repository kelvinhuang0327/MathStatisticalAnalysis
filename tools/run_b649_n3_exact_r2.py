"""Frozen-input validation, proof replay and bounded complete-N3 R2 execution.

Run expensive subcommands through the Fable protected launcher. The runner never
solves previously closed real sets, and never replaces an existing terminal file.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK = "B649_K20_V7_FULL_N3_HARD_SET_BOUND_TIGHTENING_R2"
RUN = ROOT / ".task-data" / TASK
R1 = ROOT / ".task-data/B649_K20_V7_FULL_N3_SIGNATURE_COMPRESSION_FEASIBILITY_R1/run1"
SOURCE = ROOT / "src/lottolab/research/b649_n3_exact"
SUMMARY = ROOT / (
    "docs/research/matrix-native-results/"
    "b649-k20-v7-full-n3-signature-compression-feasibility-r1-result.json"
)
START_COUNT = 313_239_661
START_SHA = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
type Document = dict[str, Any]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path) -> Document:
    return json.loads(path.read_text())


def save(path: Path, doc: Document) -> None:
    """Atomic result write; terminal results are never implicitly rerun."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
    temp.replace(path)


def inputs() -> tuple[Document, Document]:
    summary = read(SUMMARY)
    payload = {k: v for k, v in summary.items() if k != "SEAL"}
    assert (
        digest(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        == (summary["SEAL"]["CANONICAL_PAYLOAD_SHA256"])
    )
    manifest = R1 / "selection-manifest.json"
    assert digest(manifest.read_bytes()) == summary["EVIDENCE"]["SELECTION_MANIFEST_SHA256"]
    assert digest((R1 / "engine/n3sig").read_bytes()) == summary["EVIDENCE"]["ENGINE_BINARY_SHA256"]
    pinned = summary["EVIDENCE"]["PINNED_SOURCE"]
    raw = subprocess.check_output(["git", "show", f"{pinned['COMMIT']}:{pinned['PATH']}"], cwd=ROOT)
    assert digest(raw) == pinned["SHA256"]
    source = json.loads(raw)
    assert source["START_COUNT"] == START_COUNT
    assert source["START_SHA256"] == START_SHA
    assert digest(json.dumps(source["BEST_PORTFOLIO"], separators=(",", ":")).encode()) == START_SHA
    assert [s["POSITIONS"] for s in summary["SETS"]] == read(manifest)["DESTROY_TRIPLES"]
    for record in summary["SETS"]:
        if "TERMINAL_RESULT_PATH" in record:
            previous_path = Path(record["TERMINAL_RESULT_PATH"])
            assert digest(previous_path.read_bytes()) == (record["TERMINAL_RESULT_SHA256"])
            if record["DISPOSITION"] == "PROVEN_COMPLETE":
                solver = read(previous_path)["SOLVER"]
                assert solver["CLOSED"] and solver["ACCOUNTING_COMPLETE"]
                assert solver["TRIPLES_ACCOUNTED"] == solver["TRIPLES_TOTAL"]
                assert solver["OPTIMAL_TRIPLE_COUNT"] == len(solver["TIES"]) > 0
    return summary, source


def build() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    sources = sorted(SOURCE.glob("*.c"))
    argv = ["clang", "-std=c11", "-O3", "-Wall", "-Wextra", *(str(p) for p in sources)]
    subprocess.run([*argv, "-o", str(RUN / "n3-exact")], check=True, cwd=ROOT)
    save(
        RUN / "build.json",
        {
            "ARGV": argv,
            "SOURCE_SHA256": {p.name: digest(p.read_bytes()) for p in sorted(SOURCE.iterdir())},
            "BINARY_SHA256": digest((RUN / "n3-exact").read_bytes()),
            "BASE_HEAD": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
            .decode()
            .strip(),
        },
    )


def correctness() -> None:
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "tests/unit/test_b649_n3_exact_r2.py",
        "-q",
        "-s",
    ]
    process = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    print(process.stdout, flush=True)
    print(process.stderr, file=sys.stderr, flush=True)
    assert process.returncode == 0
    stats: Document = {}
    for line in process.stdout.splitlines():
        if "{" in line:
            stats.update(json.loads(line[line.index("{") :]))
    save(
        RUN / "correctness.json",
        {
            "ARGV": argv,
            "EXIT_CODE": process.returncode,
            "STATUS": "PASS",
            **stats,
            "SOURCE_SHA256": {p.name: digest(p.read_bytes()) for p in sorted(SOURCE.iterdir())},
            "MUTATIONS_REJECTED": [
                "MUTANT_CONDITIONAL_BOUND",
                "MUTANT_PRUNE_EQUAL",
                "MUTANT_CACHE_VALUE",
                "MUTANT_SUFFIX_CUTOFF",
                "MUTANT_SHARED_LOWER_BOUND",
                "MUTANT_GEOMETRIC_LOWER_BOUND",
            ],
        },
    )


def require_correctness() -> None:
    checks = read(RUN / "correctness.json")
    assert checks["STATUS"] == "PASS" and checks["MISMATCHES"] == 0
    current = {p.name: digest(p.read_bytes()) for p in sorted(SOURCE.iterdir())}
    assert current == checks["SOURCE_SHA256"] == read(RUN / "build.json")["SOURCE_SHA256"]
    assert digest((RUN / "n3-exact").read_bytes()) == read(RUN / "build.json")["BINARY_SHA256"]


def tickets_arg(tickets: list[list[int]]) -> str:
    return ";".join(",".join(str(number) for number in ticket) for ticket in tickets)


def reference(set_number: int) -> tuple[Document, list[list[int]], list[list[int]]]:
    summary, source = inputs()
    selected = summary["SETS"][set_number - 1]
    positions = selected["POSITIONS"]
    start = source["BEST_PORTFOLIO"]
    rec = next(r for r in source["PER_DESTROY_TRIPLE"] if r["POSITIONS"] == positions)
    return (
        rec,
        [t for i, t in enumerate(start) if i not in positions],
        [start[i] for i in positions],
    )


def engine(
    set_number: int,
    name: str,
    *,
    limit: float,
    legacy: bool = False,
    anchor_limit: int = 0,
    witness_file: Path | None = None,
) -> Document:
    rec, kept, removed = reference(set_number)
    out = RUN / f"{name}.json"
    timing = RUN / f"{name}-observation.json"
    if out.exists():
        assert timing.exists(), (
            "Existing terminal output lacks its runner observation; inspect first"
        )
        result = read(out)
        assert result["KEPT"] == kept and result["REMOVED"] == removed
        return result
    argv = [
        str(RUN / "n3-exact"),
        "--kept",
        tickets_arg(kept),
        "--removed",
        tickets_arg(removed),
        "--out",
        str(out),
        "--time-limit",
        str(limit),
        "--verbose",
    ]
    if legacy:
        argv.append("--legacy")
    if anchor_limit:
        argv.extend(["--anchor-limit", str(anchor_limit)])
    if witness_file:
        argv.extend(["--witness-file", str(witness_file)])
    start = time.monotonic()
    with (RUN / f"{name}.log").open("w") as log:
        process = subprocess.run(argv, cwd=ROOT, stdout=log, stderr=log, check=False)
    wall = time.monotonic() - start
    save(timing, {"ARGV": argv, "EXIT_CODE": process.returncode, "WALL_SECONDS": wall})
    assert process.returncode == 0, f"Native validation failed: {name}"
    result = read(out)
    assert result["KEPT"] == kept and result["REMOVED"] == removed
    assert result["RESIDUAL_SUBSETS"] == rec["RESIDUAL_SUBSETS"]
    assert result["FROZEN_REMAINDER_COUNT"] == rec["FROZEN_REMAINDER_CANONICAL_COUNT"]
    assert result["INCUMBENT"]["F0_DIRECT"] == rec["BEST_RESIDUAL_SUBSETS"]
    assert result["INCUMBENT"]["F0_DIRECT"] == result["INCUMBENT"]["F0_INCLUSION_EXCLUSION"]
    assert result["IDENTITIES"]["PASS"]
    if result["SOLVER"]["RAN"]:
        assert result["SOLVER"]["PRUNE_AUDIT_FAILURES"] == 0
        assert result["SOLVER"]["LEAF_DIRECT_AUDIT_FAILURES"] == 0
    return result


def replay() -> None:
    summary, _ = inputs()
    replays: list[Document] = []
    for s in summary["SETS"]:
        if s["DISPOSITION"] != "PROVEN_COMPLETE":
            continue
        previous = read(Path(s["TERMINAL_RESULT_PATH"]))
        witnesses = RUN / f"set{s['SET']}-stored-witnesses.txt"
        text = "\n".join(tickets_arg(tri) for tri in previous["SOLVER"]["TIES"]) + "\n"
        if witnesses.exists():
            assert witnesses.read_text() == text
        else:
            witnesses.write_text(text)
        current = engine(
            s["SET"], f"set{s['SET']}-proof-replay-v3", limit=3600, witness_file=witnesses
        )
        checks = current["STORED_PROOF_REPLAY"]
        assert not current["SOLVER"]["RAN"]
        assert checks["WITNESSES"] == previous["SOLVER"]["OPTIMAL_TRIPLE_COUNT"]
        assert checks["MISMATCHES"] == 0
        assert checks["REFERENCE_F"] == previous["SOLVER"]["BEST_F"]
        replays.append({"SET": s["SET"], "OLD_CLOSED": True, **checks})
        print(json.dumps(replays[-1]), flush=True)
    save(
        RUN / "proof-replay.json", {"PARITY_MISMATCHES": 0, "FULL_REAL_RERUNS": 0, "SETS": replays}
    )


def profile() -> None:
    require_correctness()
    assert read(RUN / "proof-replay.json")["PARITY_MISMATCHES"] == 0
    runs: dict[str, Document] = {}
    for legacy in (True, False):
        name = "set8-profile-old" if legacy else "set8-profile-new-v3"
        result = engine(8, name, limit=360, anchor_limit=16, legacy=legacy)
        observation = read(RUN / f"{name}-observation.json")
        runs["OLD" if legacy else "NEW"] = {
            **result["SOLVER"],
            "WALL_SECONDS": observation["WALL_SECONDS"],
        }
    old, new = runs["OLD"], runs["NEW"]
    comparable = (
        old["STOP_REASON"] == new["STOP_REASON"] == "ANCHOR_PROFILE_LIMIT"
        and old["A_EXPLORED"] == new["ANCHORS_COMPLETED"] == 16
        and old["BEST_F"] == new["BEST_F"]
    )
    ratio = old["WALL_SECONDS"] / new["WALL_SECONDS"] if comparable else None
    save(
        RUN / "profile.json",
        {"RUNS": runs, "SAME_ANCHOR_PREFIX": comparable, "WALL_SPEEDUP": ratio},
    )
    print(json.dumps({"SAME_ANCHOR_PREFIX": comparable, "WALL_SPEEDUP": ratio}), flush=True)


def solve(set_number: int) -> None:
    require_correctness()
    assert set_number in (5, 7, 8), "Closed real sets must never be rerun"
    assert read(RUN / "proof-replay.json")["PARITY_MISMATCHES"] == 0
    if set_number != 8:
        eight = read(RUN / "set8-solve.json")["SOLVER"]
        profile_doc = read(RUN / "profile.json")
        speedup = profile_doc["WALL_SPEEDUP"] or 0
        assert eight["CLOSED"] or speedup >= 5, "SET8 gate has not passed"
    result = engine(set_number, f"set{set_number}-solve", limit=3600)
    s = result["SOLVER"]
    assert s["RAN"]
    if s["CLOSED"]:
        assert s["ACCOUNTING_COMPLETE"]
        assert s["TRIPLES_ACCOUNTED"] == s["TRIPLES_TOTAL"]
        assert s["OPTIMAL_TRIPLE_COUNT"] == s["TIES_STORED"] > 0
    print(
        json.dumps(
            {
                "SET": set_number,
                **{
                    k: s[k]
                    for k in (
                        "CLOSED",
                        "BEST_F",
                        "OPEN_UPPER_BOUND",
                        "A_EXPLORED",
                        "ANCHORS_COMPLETED",
                        "SECONDS",
                        "PAIR_CALLS",
                        "CACHE_HITS",
                        "CACHE_MISSES",
                    )
                },
            }
        ),
        flush=True,
    )


def portfolio_sha(tickets: list[list[int]]) -> str:
    normalized = sorted(sorted(ticket) for ticket in tickets)
    assert len({tuple(t) for t in normalized}) == len(normalized)
    return digest(json.dumps(normalized, separators=(",", ":")).encode())


def report() -> None:
    """Fresh independent canonical recounts, followed by a compact sealed result."""
    require_correctness()
    from lottolab.research.b649_official_any_prize_exact import (
        all_main_draw_masks,
        evaluate_portfolio,
    )

    summary, pinned = inputs()
    checks = read(RUN / "correctness.json")
    replay_doc = read(RUN / "proof-replay.json")
    profile_doc = read(RUN / "profile.json")
    for name in ("n3_overlap.c", "n3_mtab.c", "n3_mtab.h", "n3_sig.c", "n3_sig.h"):
        assert (SOURCE / name).read_bytes() == (R1 / "engine" / name).read_bytes()
    draws = all_main_draw_masks(49, 6)

    def count(tickets: list[list[int]]) -> int:
        return evaluate_portfolio(tickets, draws=draws).official_any_prize_outcome_count

    best_portfolio = pinned["BEST_PORTFOLIO"]
    best_count = count(best_portfolio)
    assert best_count == START_COUNT and portfolio_sha(best_portfolio) == START_SHA
    per_set: list[Document] = []
    for number in (8, 5, 7):
        path = RUN / f"set{number}-solve.json"
        if not path.exists():
            gate = per_set and (
                per_set[0]["STATUS"] == "PROVEN_COMPLETE" or (profile_doc["WALL_SPEEDUP"] or 0) >= 5
            )
            per_set.append(
                {
                    "SET": number,
                    "STATUS": "NOT_RUN_OPTIONAL" if gate else "NOT_RUN_SET8_GATE_NOT_PASSED",
                }
            )
            continue
        native = read(path)
        s = native["SOLVER"]
        rec, kept, removed = reference(number)
        assert native["KEPT"] == kept and native["REMOVED"] == removed
        assert native["IDENTITIES"]["PASS"]
        assert s["PRUNE_AUDIT_FAILURES"] == s["LEAF_DIRECT_AUDIT_FAILURES"] == 0
        assert count(kept) == native["FROZEN_REMAINDER_COUNT"]
        total = native["FROZEN_REMAINDER_COUNT"] + 7 * s["BEST_F"]
        if s["CLOSED"]:
            assert s["ACCOUNTING_COMPLETE"] and s["TRIPLES_ACCOUNTED"] == s["TRIPLES_TOTAL"]
            assert s["OPTIMAL_TRIPLE_COUNT"] == len(s["TIES"]) > 0
        ranked = sorted((portfolio_sha(kept + tri), tri) for tri in s["TIES"])
        recounts: list[Document] = []
        for sha, tri in ranked[:4]:
            candidate = sorted(kept + tri)
            verified = count(candidate)
            assert verified == total
            recounts.append({"PORTFOLIO_SHA256": sha, "COUNT": verified, "REPLACEMENTS": tri})
            if verified > best_count:
                best_count, best_portfolio = verified, candidate
        if total > START_COUNT:
            assert recounts, "A strict improver needs an independent canonical recount"
        nodes = s["A_EXPLORED"] + s["B_EXPLORED"] + s["LEAVES_EXACT"]
        observation = read(RUN / f"set{number}-solve-observation.json")
        assert observation["EXIT_CODE"] == 0
        wall = observation["WALL_SECONDS"]
        upper = s["BEST_F"] if s["CLOSED"] else max(s["BEST_F"], s["OPEN_UPPER_BOUND"])
        rate = s["ANCHORS_COMPLETED"] / s["SECONDS"] if s["SECONDS"] else 0
        row = {
            "SET": number,
            "DESTROY_POSITIONS": summary["SETS"][number - 1]["POSITIONS"],
            "KEPT_TICKETS": kept,
            "REMOVED_TICKETS": removed,
            "RESIDUAL_SUBSETS": rec["RESIDUAL_SUBSETS"],
            "STATUS": "PROVEN_COMPLETE" if s["CLOSED"] else "NOT_CLOSED_WITHIN_PER_SET_TIME_LIMIT",
            "F0": native["INCUMBENT"]["F0_DIRECT"],
            "BEST_RESIDUAL_UNION": s["BEST_F"],
            "BEST_COUNT": total,
            "UPPER_BOUND": upper,
            "CANONICAL_UPPER_COUNT": native["FROZEN_REMAINDER_COUNT"] + 7 * upper,
            "ANCHORS_EXPANDED": s["A_EXPLORED"],
            "ANCHORS_COMPLETED": s["ANCHORS_COMPLETED"],
            "ANCHORS_INITIAL_BOUND_TOTAL": s["A_BOUND_COUNT"],
            "NODES": nodes,
            "NODES_PER_SECOND": nodes / s["SECONDS"] if s["SECONDS"] else 0,
            "ANCHORS_PER_SECOND": rate,
            "WALL_SECONDS": wall,
            "SOLVER_SECONDS": s["SECONDS"],
            "PEAK_RSS_BYTES": native["PEAK_RSS_BYTES"],
            "PAIR_REQUESTS": s["PAIR_CALLS"],
            "CACHE_HITS": s["CACHE_HITS"],
            "CACHE_MISSES": s["CACHE_MISSES"],
            "LOWER_BOUND_CALLS": s["LOWER_BOUND_CALLS"],
            "PAIR_CANDIDATES_PER_SECOND": (
                s["LOWER_BOUND_CALLS"] / s["SECONDS"] if s["SECONDS"] else 0
            ),
            "LEAVES_PRUNED_LOWER": s["LEAVES_PRUNED_LOWER"],
            "PAIR_SHARED_COUNTS": s["PAIR_SHARED_COUNTS"],
            "CONDITIONAL_ANCHORS_PRUNED": s["ANCHORS_PRUNED_CONDITIONAL"],
            "PROJECTION_REMAINING_SECONDS": 0
            if s["CLOSED"]
            else (max(0, s["A_BOUND_COUNT"] - s["ANCHORS_COMPLETED"]) / rate if rate else None),
            "PROJECTION_DEFINITION": (
                "Linear estimate from fully completed anchors; not a proof or deadline guarantee"
            ),
            "CANONICAL_RECOUNTS": recounts,
            "PRUNE_AUDIT_FAILURES": s["PRUNE_AUDIT_FAILURES"],
            "LEAF_AUDIT_FAILURES": s["LEAF_DIRECT_AUDIT_FAILURES"],
            "PRUNE_AUDITS": s["PRUNE_AUDITS"],
            "LEAF_DIRECT_AUDITS": s["LEAF_DIRECT_AUDITS"],
            "ACCOUNTING_COMPLETE": s["ACCOUNTING_COMPLETE"],
            "TRIPLES_ACCOUNTED": s["TRIPLES_ACCOUNTED"],
            "TRIPLES_TOTAL": s["TRIPLES_TOTAL"],
            "PROOF_SCOPE": "COMPLETE LEGAL TICKET UNIVERSE"
            if s["CLOSED"]
            else "EXACT PARTIAL SEARCH WITH ADMISSIBLE FRONTIER BOUND",
            "NATIVE_RESULT_SHA256": digest(path.read_bytes()),
        }
        per_set.append(row)
        print(
            json.dumps(
                {
                    "SET": number,
                    "STATUS": row["STATUS"],
                    "BEST_COUNT": total,
                    "UPPER_BOUND": upper,
                    "CANONICAL_RECOUNT": "PASS",
                }
            ),
            flush=True,
        )
    eight = per_set[0]
    speedup = profile_doc["WALL_SPEEDUP"] or 0
    result: Document = {
        "SCHEMA_VERSION": "B649_K20_FULL_N3_HARD_SET_BOUND_TIGHTENING_RESULT_V2",
        "TASK_ID": TASK,
        "TASK_CLASS": "STATE_CHANGING_IMPLEMENTATION",
        "WORKER_ROUTE": "STANDARD",
        "JUDGE_MODE": "NOT_APPLICABLE",
        "JUDGE_DISPATCH": "SUPPRESSED",
        "SEALED_AT_LOCAL": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        ).isoformat(),
        "START_COUNT": START_COUNT,
        "START_SHA256": START_SHA,
        "OLD_BOUND_RULE": (
            "Global r-order; B/C remaining-slot bounds use unconditional r, "
            "with lazy per-anchor i(A,T) memoization; pair bound uses "
            "iABC<=min(iAB,iAC,iBC)."
        ),
        "NEW_BOUND_RULE": (
            "Before exact BC overlap, also apply the geometric kept-ticket union bound. "
            "Count a provable subset of res(B) intersect res(C): "
            "3+ common-number coverage, or a 9-term two-common-number subset count. "
            "Prune only if base+gA(C)-max(0,lower-min(iAB,iAC))<target. "
            "For each globally ordered anchor A, exactly score and sort all "
            "potentially competitive suffix tickets by gA(T)=r(T)-i(A,T); "
            "upper bound r(A)+gA(B)+gA(C). Retain equality. Optional exact "
            "unordered-rank-key pair cache recomputes on collision or eviction; "
            "it is disabled in the measured final solver. Unchanged R1 pair bound and exact "
            "inclusion-exclusion leaf value."
        ),
        "BOUND_PROOFS": [
            (
                "If U is the complement of kept coverage, i_U(B,C)>=i_full(B,C)-"
                "sum_R i_full(B,C,R). Each unconditional triple count is computed exactly "
                "from eight Venn-atom cardinalities. Common-number subset counts supply "
                "another lower bound L. Then iBC-iABC>=max(0,L-min(iAB,iAC)), proving the "
                "cheap pair upper bound. Every count and bound is integral."
            ),
            (
                "Every ticket is scored over all C(49,6) tickets. A ticket with "
                "r<F0-2*rho cannot appear in a triple reaching F0, because "
                "union<=sum(r)<=r+2*rho<F0. The threshold is mathematical, never "
                "fixed top-L."
            ),
            (
                "Every unordered triple has a unique smallest global-order "
                "anchor. Within its suffix, conditional sorting enumerates each "
                "remaining unordered pair exactly once."
            ),
            (
                "For fixed A, F(A,B,C)=r(A)+|res(B)\\res(A)|+|res(C)\\(res(A) union "
                "res(B))|<=r(A)+gA(B)+gA(C). The sum of the two largest remaining "
                "gA values bounds the whole block."
            ),
            (
                "Discarding a suffix ticket T requires r(A)+r(a+1)+r(T)<target; "
                "every other suffix ticket has r<=r(a+1), so no competitive pair "
                "involving T is lost."
            ),
            (
                "iABC<=min(iAB,iAC,iBC), so the retained pair bound remains "
                "admissible. Exact keys identify two colex ticket ranks; hash "
                "collisions cause replacement, never false reuse."
            ),
            (
                "All new pruning is strict (<target), preserving every optimum "
                "tie. Accounted blocks are disjoint. Closure requires their sum "
                "to equal C(13983816,3). Timeout includes the active conditional "
                "block and every later global anchor in its upper bound."
            ),
        ],
        "PARITY_MISMATCHES": checks["MISMATCHES"] + replay_doc["PARITY_MISMATCHES"],
        "PARITY_SCOPE": (
            "Exhaustive old/new toy solver comparison plus "
            "preservation/replay of every stored optimum from each previously "
            "proven real set; previous full real searches were NOT rerun."
        ),
        "REAL_SET_PARITY_DERIVATION": (
            "Reused sealed old full-search proofs establish the optimum and all ties. "
            "The unchanged exact overlap kernel cannot produce a larger valid union. "
            "Every saved optimum survives all new bounds in each anchor rotation. "
            "The admissibility and unique-enumeration proofs therefore establish "
            "old/new optimum parity without rerunning those closed searches."
        ),
        "CORRECTNESS": checks,
        "PREVIOUS_PROVEN_SET_REPLAYS": replay_doc,
        "EXACT_PREFIX_PROFILE": profile_doc,
        "DEVELOPMENT_ATTEMPTS": [
            {
                "VARIANT": suffix or "cache-only",
                "WALL_SECONDS": read(RUN / f"set8-profile-new{suffix}-observation.json")[
                    "WALL_SECONDS"
                ],
                "WALL_SPEEDUP": profile_doc["RUNS"]["OLD"]["WALL_SECONDS"]
                / read(RUN / f"set8-profile-new{suffix}-observation.json")["WALL_SECONDS"],
            }
            for suffix in ("", "-v2", "-v3")
        ],
        "SET8_STATUS": eight["STATUS"],
        "SET8_BEST_COUNT": eight["BEST_COUNT"],
        "SET8_UPPER_BOUND": eight["UPPER_BOUND"],
        "SET8_NODES": eight["NODES"],
        "SET8_WALL_SECONDS": eight["WALL_SECONDS"],
        "SET5_STATUS": per_set[1]["STATUS"],
        "SET7_STATUS": per_set[2]["STATUS"],
        "SETS": per_set,
        "STRICT_IMPROVER_FOUND": best_count > START_COUNT,
        "BEST_VERIFIED_COUNT": best_count,
        "BEST_VERIFIED_SHA": portfolio_sha(best_portfolio),
        "BEST_CANONICAL_RECOUNT_STATUS": "PASS",
        "BEST_VERIFIED_PORTFOLIO": best_portfolio,
        "PRIMARY_SUCCESS": any(s["STATUS"] == "PROVEN_COMPLETE" for s in per_set),
        "SECONDARY_SUCCESS": best_count > START_COUNT,
        "ENGINEERING_SUCCESS": (
            profile_doc["SAME_ANCHOR_PREFIX"]
            and speedup >= 5
            and checks["MISMATCHES"] == replay_doc["PARITY_MISMATCHES"] == 0
        ),
        "PROOF_SCOPE": (
            "For each reported frozen 17-ticket remainder: COMPLETE LEGAL "
            "TICKET UNIVERSE of three distinct replacement tickets for "
            "PROVEN_COMPLETE sets; conservative partial frontier bound for "
            "time-limited sets. No claim of global K20 portfolio optimality "
            "or closure of other destroy sets."
        ),
        "FIELD_DEFINITIONS": {
            "UPPER_BOUND": "Residual winning 7-subsets, matching the R1 F0/open-bound units",
            "BEST_COUNT": (
                "Full canonical portfolio outcome count = frozen remainder count + 7*residual union"
            ),
            "NODES": (
                "Expanded anchors + expanded B nodes + exactly evaluated triple "
                "leaves, matching R1 convention"
            ),
            "CACHE_MISSES": (
                "Exact pair overlap oracle calls, including conditional anchor "
                "marginals and BC leaves"
            ),
        },
        "BUILD": read(RUN / "build.json"),
        "SOURCE_RESULT_SHA256": digest(SUMMARY.read_bytes()),
        "SOURCE_RESULT_SEAL": summary["SEAL"],
        "FROZEN_SELECTION_MANIFEST_SHA256": digest((R1 / "selection-manifest.json").read_bytes()),
        "PINNED_SOURCE": summary["EVIDENCE"]["PINNED_SOURCE"],
        "R1_SOURCE_PROVENANCE": {
            "DIRECTORY": str(R1 / "engine"),
            "SOURCE_SHA256": {
                p.name: digest(p.read_bytes())
                for p in sorted((R1 / "engine").iterdir())
                if p.suffix in (".c", ".h")
            },
            "ORIGINAL_BINARY_SHA256": digest((R1 / "engine/n3sig").read_bytes()),
            "LEGACY_SEARCH_DELTA": (
                "Observed source diff: solver_run renamed to solver_run_legacy; "
                "five-line exact anchor-profile stopping guard added. "
                "All legacy search bounds and exact arithmetic are unchanged."
            ),
            "UNCHANGED_EXACT_KERNELS": [
                "n3_overlap.c",
                "n3_mtab.c",
                "n3_mtab.h",
                "n3_sig.c",
                "n3_sig.h",
            ],
        },
        "RUN_DIRECTORY": str(RUN),
        "RESOURCE_POLICY": {
            "CPU_WORKERS": 1,
            "DEFAULT_CACHE_BYTES": 0,
            "OPTIONAL_CACHE_MAX_BYTES": 12 * (1 << 25),
        },
        "MEMOIZATION_DISPOSITION": (
            "Cache-only profiling gave no speedup; default cache is disabled in the "
            "fixed improved solver. Optional exact-key cache remains validated."
        ),
        "DEVELOPMENT_PROFILE_LIMIT": {
            "SET": 8,
            "ANCHORS": 16,
            "SECONDS_PER_VARIANT": 360,
            "VARIANTS_MAX": 4,
        },
        "PER_SET_TIME_LIMIT_SECONDS": 3600,
        "PROJECT_MEMORY_WRITTEN": False,
        "PUSH": False,
        "PR": False,
        "MERGE": False,
        "PRODUCTION_CHANGE": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": False,
        "TASK_EVIDENCE_RETENTION": {
            "RUN_DIRECTORY": str(RUN),
            "PROTECTED_LAUNCH_RECEIPTS": str(ROOT / ".fable/checkpoints" / TASK),
            "DISPOSITION": "RETAINED_FOR_REPRODUCIBLE_RESEARCH_EVIDENCE",
        },
        "DESTRUCTIVE_ACTION_OCCURRED": True,
        "DESTRUCTIVE_TARGET": "/tmp/b649-n3-r2-build-check",
        "DESTRUCTIVE_TARGET_PRESTATE": "Task-created compiler-check executable (87064 bytes)",
        "DESTRUCTIVE_ACTION": "rm of this single task-created temporary file",
        "DESTRUCTIVE_ACTION_AT": "2026-10-06T05:55:55+00:00",
        "DESTRUCTIVE_ACTION_AUTHORIZATION_SOURCE": "Task-authorized verification scratch cleanup",
        "DESTRUCTIVE_TARGET_POSTSTATE": "Confirmed absent by test ! -e, exit 0",
        "IMPLEMENTATION_DEPTH": "ENHANCED",
        "DEPTH_SOURCE": "PLANNER_SUPPLIED",
        "INTENT": (
            "code does unconditional-r remaining-slot pruning in R1; "
            "the check/task expects exact complete-N3 tightening or closure; "
            "the opened spec says no heuristic pruning and no top-L truncation."
        ),
        "ENHANCED_EVIDENCE": [
            {
                "INVARIANT": (
                    "Admissibility, all optimum ties, disjoint accounting, collision "
                    "safety, timeout frontier"
                ),
                "CHECK": (
                    "Native production search on explicit coverage-set brute oracle; "
                    "six mutants rejected"
                ),
                "RESULT": "RUN_THIS_TASK PASS",
            },
            {
                "INVARIANT": "Previous closed real set optima preserved",
                "CHECK": (
                    "All 1360 saved optima replayed through unchanged exact "
                    "coverage/overlap kernel and new bounds, 20 direct-union witnesses"
                ),
                "RESULT": "RUN_THIS_TASK PASS; old optimality proofs reused, no full real reruns",
            },
        ],
        "EXECUTION_NOTE": (
            "Concurrent protected correctness launch was rejected while proof "
            "replay was active; no child ran. The same launch identity "
            "succeeded after replay completed. All expensive runs were "
            "serialized through the protected launcher."
        ),
    }
    result["TASK_STATUS"] = "BOUNDED_EXACT_EXPERIMENT_COMPLETE"
    result["SEAL"] = {
        "ALGORITHM": "SHA-256",
        "CANONICAL_PAYLOAD_SHA256": digest(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ),
        "CANONICAL_PAYLOAD_DEFINITION": (
            "UTF-8 JSON with sorted keys, compact separators and SEAL omitted"
        ),
    }
    destination = (
        ROOT
        / "docs/research/matrix-native-results"
        / "b649-k20-v7-full-n3-hard-set-bound-tightening-r2-result.json"
    )
    save(destination, result)
    save(RUN / "final-result.json", result)
    print(str(destination), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "correctness", "replay", "profile", "solve", "report")
    )
    parser.add_argument("--set", dest="set_number", type=int, default=8)
    args = parser.parse_args()
    if args.action == "build":
        inputs()
        build()
    elif args.action == "correctness":
        correctness()
    elif args.action == "replay":
        replay()
    elif args.action == "profile":
        profile()
    elif args.action == "report":
        report()
    else:
        solve(args.set_number)


if __name__ == "__main__":
    main()
