"""One fixed, research-only K20 four-ticket destroy/repair batch.

The seven-set score is a sampled union, never an exact count or a bound.
Only the pinned native evaluator can produce NEW_EXACT. Evidence lookup and
bounded incidence-isomorphism searches have an explicitly limited scope.
No production registration, dependency installation, historical draws or workers.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import resource
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_K20_VERSIONS,
    canonical_portfolio_sha256,
    verify_sealed_geometry_portfolio,
)
from lottolab.research import b649_official_any_prize_exact as native

TASK_ID = "B649_K20_FOUR_TICKET_REPAIR_PILOT_R1"
BASE_HEAD = "9b0dc98b10623dac7727f50aa4e47f14f68dcf6d"
BRANCH = "codex/b649-k20-four-ticket-repair-pilot-r1"
BASELINE_SHA = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
EVALUATOR_BLOB = "3d053b2d9bc2182fc00b22889e837be5d0ba10aa"
BASELINE_COUNT = 313263888
DENOMINATOR = 601304088
HISTORY_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/"
    "B649_K20_SCOPE_FILTERED_EXACT_SEARCH_R1/.task-data/"
    "B649_K20_SCOPE_FILTERED_EXACT_SEARCH_R1"
)
STATUSES = (
    "INVALID",
    "BASELINE_OR_DUPLICATE",
    "KNOWN_EXACT",
    "PROVEN_CLOSED",
    "ISOMORPHIC_REUSED",
    "NEW_EXACT",
    "NOT_SELECTED",
    "UNFINISHED",
)
type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Masks = npt.NDArray[np.uint64]
type Bits = npt.NDArray[np.bool_]
type Record = dict[str, Any]


@dataclass(frozen=True)
class Config:
    seed: int = 20261020
    destroy_set_count: int = 32
    repairs_per_destroy_set: int = 8
    max_complete_proposals: int = 256
    repair_ticket_pool_per_step: int = 64
    pool_attempt_limit: int = 256
    surrogate_seven_set_samples: int = 32768
    rcl_alpha: float = 0.20
    max_exact_calls: int = 12
    wall_seconds: float = 3600
    memory_bytes: int = 2 * 1024**3
    iso_node_limit: int = 2000


FIXED_CONFIG = Config()


class BudgetStop(RuntimeError):
    """Preserve partial results; never silently restart or extend a budget."""


def peak_memory_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


@dataclass
class Budget:
    config: Config
    started: float
    calls: int = 0
    clock: Callable[[], float] = time.monotonic

    def check(self) -> None:
        if self.clock() - self.started >= self.config.wall_seconds:
            raise BudgetStop("SCIENTIFIC_WALL_CLOCK_LIMIT")
        if peak_memory_bytes() >= self.config.memory_bytes:
            raise BudgetStop("PROCESS_MEMORY_LIMIT")

    def reserve_exact(self) -> None:
        self.check()
        if self.calls >= self.config.max_exact_calls:
            raise BudgetStop("EXACT_CALL_LIMIT")
        self.calls += 1  # An interrupted native call still consumes a call.


def canonical(tickets: Sequence[Sequence[int]]) -> Portfolio:
    return tuple(sorted(tuple(sorted(t)) for t in tickets))


def legal(tickets: Sequence[Sequence[int]], *, count: int = 20) -> bool:
    return (
        len(tickets) == count
        and all(
            len(t) == 6 and len(set(t)) == 6 and all(type(n) is int and 1 <= n <= 49 for n in t)
            for t in tickets
        )
        and len(set(tuple(sorted(t)) for t in tickets)) == count
    )


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derived_seed(seed: int, *parts: object) -> int:
    return int.from_bytes(hashlib.sha256(repr((seed, *parts)).encode()).digest()[:16])


def fixed_plan(config: Config) -> Record:
    universe = list(itertools.combinations(range(20), 4))
    destroys = random.Random(config.seed).sample(universe, config.destroy_set_count)
    return {
        "config": asdict(config),
        "destroy_sets_zero_based_in_execution_order": destroys,
        "repair_seeds": [
            [
                derived_seed(config.seed, "repair", d, r)
                for r in range(config.repairs_per_destroy_set)
            ]
            for d in range(config.destroy_set_count)
        ],
        "sample_seed": derived_seed(config.seed, "seven_sets"),
        "sampling": "independent random.sample(1..49,7); repeats across samples allowed",
        "pool": "uniform random.sample(1..49,6), deduplicate, sort lexicographically",
        "rcl": "gain >= max - alpha*(max-min), lexicographic order then rng.choice",
        "ranking": "surrogate union delta descending, canonical portfolio lexicographic",
        "iso_scope": "loaded historical portfolios; at most 2000 backtracking nodes per pair",
    }


def seven_samples(config: Config) -> Masks:
    rng = random.Random(derived_seed(config.seed, "seven_sets"))
    return np.fromiter(
        (
            native.ticket_mask(rng.sample(range(1, 50), 7))
            for _ in range(config.surrogate_seven_set_samples)
        ),
        dtype=np.uint64,
        count=config.surrogate_seven_set_samples,
    )


def coverage(ticket: Ticket, samples: Masks) -> Bits:
    return np.bitwise_count(samples & np.uint64(native.ticket_mask(ticket))) >= 3


def union_coverage(portfolio: Portfolio, samples: Masks) -> Bits:
    covered = np.zeros(samples.size, dtype=np.bool_)
    for ticket in portfolio:
        covered |= coverage(ticket, samples)
    return covered


def ticket_pool(
    rng: random.Random,
    excluded: set[Ticket],
    config: Config,
) -> tuple[list[Ticket], int]:
    found: set[Ticket] = set()
    attempts = 0
    while len(found) < config.repair_ticket_pool_per_step and attempts < config.pool_attempt_limit:
        attempts += 1
        ticket = tuple(sorted(rng.sample(range(1, 50), 6)))
        if ticket not in excluded:
            found.add(ticket)
    return sorted(found), attempts


def choose_rcl(gains: Sequence[int], rng: random.Random, alpha: float) -> int:
    low, high = min(gains), max(gains)
    threshold = high - alpha * (high - low)
    return rng.choice([i for i, gain in enumerate(gains) if gain >= threshold])


def repair(
    baseline: Portfolio,
    destroy: Sequence[int],
    seed: int,
    samples: Masks,
    config: Config,
    budget: Budget,
) -> tuple[Portfolio | None, list[Record]]:
    retained = tuple(t for i, t in enumerate(baseline) if i not in destroy)
    selected = list(retained)
    covered = union_coverage(retained, samples)
    rng = random.Random(seed)
    steps: list[Record] = []
    for step in range(4):
        budget.check()
        pool, attempts = ticket_pool(rng, set(selected), config)
        if not pool:
            steps.append({"step": step, "pool_size": 0, "attempts": attempts})
            return None, steps
        gains = [int(np.count_nonzero(coverage(t, samples) & ~covered)) for t in pool]
        index = choose_rcl(gains, rng, config.rcl_alpha)
        ticket = pool[index]
        steps.append(
            {
                "step": step,
                "pool_size": len(pool),
                "attempts": attempts,
                "shortfall": config.repair_ticket_pool_per_step - len(pool),
                "min_gain": min(gains),
                "max_gain": max(gains),
                "selected_gain": gains[index],
                "ticket": ticket,
                "pool_sha256": canonical_portfolio_sha256(pool),
            }
        )
        selected.append(ticket)
        covered |= coverage(ticket, samples)
    return canonical(selected), steps


def signature(portfolio: Portfolio) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Necessary invariants only. A match never proves isomorphism."""
    degrees = Counter(n for t in portfolio for n in t)
    intersections = sorted(len(set(a) & set(b)) for a, b in itertools.combinations(portfolio, 2))
    return tuple(sorted(degrees.get(n, 0) for n in range(1, 50))), tuple(intersections)


def check_bijection(left: Portfolio, right: Portfolio, mapping: Sequence[int]) -> bool:
    return sorted(mapping) == list(range(1, 50)) and canonical(
        tuple(tuple(mapping[n - 1] for n in t) for t in left)
    ) == canonical(right)


def prove_isomorphism(
    left: Portfolio,
    right: Portfolio,
    *,
    max_nodes: int = 2000,
) -> tuple[list[int] | None, int]:
    """Bounded ticket-intersection search, finished by a full incidence witness.

    Pairwise intersection agreement is insufficient: at a complete ticket
    permutation compare all 49 number-incidence classes, then validate the
    resulting number bijection against every ticket.
    """
    if len(left) != len(right) or signature(left) != signature(right):
        return None, 0
    size = len(left)
    a = [[len(set(x) & set(y)) for y in left] for x in left]
    b = [[len(set(x) & set(y)) for y in right] for x in right]
    choices = [[j for j in range(size) if sorted(a[i]) == sorted(b[j])] for i in range(size)]
    order = sorted(range(size), key=lambda i: (len(choices[i]), i))
    left_degrees = Counter(n for t in left for n in t)
    right_degrees = Counter(n for t in right for n in t)
    assignment: dict[int, int] = {}
    nodes = 0

    def incidence_prefix_agrees() -> bool:
        # Necessary higher-order incidence constraints prune symmetric dead ends.
        # Degree is a color only; a final full bijection remains mandatory.
        pairs = sorted(assignment.items())
        return Counter(
            (left_degrees[n], tuple(n in left[i] for i, _ in pairs)) for n in range(1, 50)
        ) == Counter(
            (right_degrees[n], tuple(n in right[j] for _, j in pairs)) for n in range(1, 50)
        )

    def walk(depth: int) -> list[int] | None:
        nonlocal nodes
        if nodes >= max_nodes:
            return None
        nodes += 1
        if depth == size:
            lc: dict[tuple[int, ...], list[int]] = defaultdict(list)
            rc: dict[tuple[int, ...], list[int]] = defaultdict(list)
            for number in range(1, 50):
                lc[tuple(assignment[i] for i in range(size) if number in left[i])].append(number)
                rc[tuple(j for j in range(size) if number in right[j])].append(number)
            # Sort incidence tuples: assignment order need not be ascending.
            lc = {tuple(sorted(k)): v for k, v in lc.items()}
            if set(lc) != set(rc) or any(len(v) != len(rc[k]) for k, v in lc.items()):
                return None
            mapping = [0] * 49
            for key, numbers in lc.items():
                for x, y in zip(numbers, rc[key], strict=True):
                    mapping[x - 1] = y
            return mapping if check_bijection(left, right, mapping) else None
        i = order[depth]
        for j in choices[i]:
            if j not in assignment.values() and all(
                a[i][k] == b[j][v] for k, v in assignment.items()
            ):
                assignment[i] = j
                result = walk(depth + 1) if incidence_prefix_agrees() else None
                del assignment[i]
                if result is not None:
                    return result
                if nodes >= max_nodes:
                    break
        return None

    return walk(0), nodes


def json_object(data: bytes) -> Record:
    value: object = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return cast(Record, value)


def read_history(root: Path) -> tuple[list[Record], Record]:
    summary_bytes = (root / "summary.json").read_bytes()
    candidate_bytes = (root / "candidates.jsonl").read_bytes()
    summary = json_object(summary_bytes)
    rows = [json_object(line) for line in candidate_bytes.splitlines()]
    if (
        summary["BASELINE_TICKET_IDENTITY"] != BASELINE_SHA
        or summary["BASELINE_COUNT"] != BASELINE_COUNT
        or summary["DENOMINATOR"] != DENOMINATOR
        or Counter(r["status"] for r in rows) != {"KNOWN_EXACT": 12, "PROVEN_CLOSED": 5148}
    ):
        raise ValueError("historical evidence identity/accounting mismatch")
    for row in rows:
        tickets = canonical(row["tickets"])
        if not legal(tickets) or canonical_portfolio_sha256(tickets) != row["portfolio_sha256"]:
            raise ValueError("historical portfolio content/hash mismatch")
    return rows, {
        "summary_path": str(root / "summary.json"),
        "summary_sha256": sha(summary_bytes),
        "candidates_path": str(root / "candidates.jsonl"),
        "candidates_sha256": sha(candidate_bytes),
        "records": len(rows),
        "scope": "only these files and matched rows' direct references",
    }


def validate_evidence(row: Record) -> Record:
    """Load original direct evidence only when a portfolio can actually reuse it."""
    evidence = cast(Record, row["evidence"])
    if row["status"] == "KNOWN_EXACT":
        raw = Path(evidence["path"]).read_bytes()
        if sha(raw) != evidence["sha256"]:
            raise ValueError("known exact original file changed")
        original = json_object(raw)
        original_tickets = next(
            (
                p
                for p in original["TOP12_PORTFOLIOS"]
                if p["portfolio_sha256"] == row["portfolio_sha256"]
            ),
            None,
        )
        if (
            original_tickets is None
            or canonical(original_tickets["tickets"]) != canonical(row["tickets"])
            or original["TOP12_EXACT_COUNTS"][original_tickets["label"]] != row["exact_count"]
            or original["MAIN_DRAWS_PER_PORTFOLIO"][original_tickets["label"]] != 13983816
            or original["SCIENTIFIC_RESULT_CLASS"] != "COMPACT_FULL_CENSUS_COUNT"
        ):
            raise ValueError("known exact value is not bound to the original complete census")
        census = cast(Record, evidence["census"])
        if (
            census["main_draw_count"] != 13983816
            or census["windows"] != [[0, None]]
            or census["covered_outcome_sum"] != row["exact_count"]
            or census["portfolio_sha256"] != row["portfolio_sha256"]
            or sum(census["coverage_histogram"]) != 13983816
            or sum(i * n for i, n in enumerate(census["coverage_histogram"])) != row["exact_count"]
        ):
            raise ValueError("known exact census is incomplete or inconsistent")
        return {"kind": "FULL_OUTCOME_CENSUS_REUSED", "original": evidence}
    reference = str(evidence["certificate"])
    if not reference.startswith("git:"):
        raise ValueError("certificate must be immutable Git evidence")
    _, commit, path = reference.split(":", 2)
    raw = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        check=True,
    ).stdout
    certificate = json_object(raw)
    radius = int(evidence["radius"])
    if (
        radius not in (1, 2)
        or certificate["TASK_STATUS"] != "COMPLETE"
        or certificate["BEST_EXACT_COUNT"] != BASELINE_COUNT
        or certificate["BEST_IS_GAIN"] is not False
        or certificate["START"]["CANONICAL_RECOUNT"] != BASELINE_COUNT
        or certificate["ENGINE_AUTHORITY"]["EVALUATOR_SHA256"]
        != sha(Path(native.__file__).read_bytes())
        or not str(certificate[f"N{radius}_LOCAL_CLOSURE_STATUS"]).startswith(
            f"C2_N{radius}_LOCAL_CLOSURE_PROVEN_FOR_EXACT_"
        )
    ):
        raise ValueError("certificate has the wrong event/domain or is unfinished")
    if radius == 1 and (
        certificate["NEIGHBORHOOD_ACCOUNTING"]["UNFINISHED_CANDIDATES"] != 0
        or certificate["NEIGHBORHOOD_ACCOUNTING"]["FULLY_ACCOUNTED_CANDIDATES"] != 279676320
    ):
        raise ValueError("N1 certificate has incomplete domain coverage")
    if radius == 2 and (
        certificate["MATHEMATICALLY_COVERED_ORIGINAL_PAIRS"] != 190
        or certificate["ACCOUNTING"]["IDENTITIES_OK"] is not True
    ):
        raise ValueError("N2 certificate has incomplete domain coverage")
    original_portfolio = canonical(certificate["START"]["TICKETS_NORMALIZED"])
    mapping = list(evidence["number_bijection_candidate_to_certificate"])
    if sorted(mapping) != list(range(1, 50)):
        raise ValueError("invalid closure number bijection")
    mapped = canonical(tuple(tuple(mapping[n - 1] for n in t) for t in row["tickets"]))
    if (
        not legal(mapped)
        or len(set(mapped) - set(original_portfolio)) > radius
        or row["exact_count"] is not None
        or row["upper_bound"] != BASELINE_COUNT
    ):
        raise ValueError("candidate is outside the certificate replacement domain")
    return {
        "kind": "PINNED_REPLACEMENT_DOMAIN_CERTIFICATE",
        "reference": reference,
        "certificate_sha256": sha(raw),
        "original_witness": evidence,
        "upper_bound": BASELINE_COUNT,
        "exact_count": None,
    }


def filter_proposals(
    records: list[Record],
    baseline: Portfolio,
    history: list[Record],
    budget: Budget,
) -> Record:
    identity = {canonical(r["tickets"]): r for r in history}
    index: dict[tuple[tuple[int, ...], tuple[int, ...]], list[Record]] = defaultdict(list)
    base_row: Record = {"tickets": baseline, "status": "BASELINE", "exact_count": BASELINE_COUNT}
    for row in [base_row, *history]:
        index[signature(canonical(row["tickets"]))].append(row)
    validated: dict[str, Record] = {}
    seen: set[Portfolio] = set()
    attempts = exhausted = 0
    for row in records:
        budget.check()
        tickets = canonical(row["tickets"])
        if not legal(tickets):
            row.update(status="INVALID", reason="K20 legality/duplicate ticket failure")
            continue
        if tickets == canonical(baseline) or tickets in seen:
            row.update(status="BASELINE_OR_DUPLICATE", reason="canonical identity")
            continue
        seen.add(tickets)
        match = identity.get(tickets)
        mapping: list[int] | None = None
        if match is None:
            for possible in index.get(signature(tickets), []):
                budget.check()
                attempts += 1
                mapping, nodes = prove_isomorphism(
                    tickets,
                    canonical(possible["tickets"]),
                    max_nodes=budget.config.iso_node_limit,
                )
                exhausted += int(nodes >= budget.config.iso_node_limit and mapping is None)
                if mapping is not None:
                    match = possible
                    break
        if match is None:
            row["status"] = "NOT_SELECTED"
            row["reason"] = "no proof in loaded evidence and bounded mapping search"
            continue
        key = canonical_portfolio_sha256(canonical(match["tickets"]))
        if match["status"] == "BASELINE":
            proof: Record = {"kind": "PINNED_BASELINE_EXACT", "exact_count": BASELINE_COUNT}
        else:
            if key not in validated:
                validated[key] = validate_evidence(match)
            proof = validated[key]
        status = "ISOMORPHIC_REUSED" if mapping is not None else match["status"]
        row.update(
            status=status,
            exact_count=match.get("exact_count"),
            upper_bound=match.get("upper_bound"),
            evidence={
                "reference_portfolio_sha256": key,
                "proof": proof,
                "number_bijection_to_reference": mapping,
                "event": "OFFICIAL_ANY_PRIZE",
                "denominator": DENOMINATOR,
            },
        )
    return {
        "isomorphism_pairs_tried": attempts,
        "node_limit_exhaustions": exhausted,
        "matched_original_evidence_validated": len(validated),
        "certificate_scope": "identity or verified number bijection to loaded historical rows",
        "unmatched": "not a claim of project-wide novelty or certificate non-membership",
    }


def rank_and_mark(records: list[Record], limit: int) -> list[Record]:
    eligible = sorted(
        (r for r in records if r["status"] == "NOT_SELECTED"),
        key=lambda r: (-int(r["surrogate_delta"]), canonical(r["tickets"])),
    )
    chosen = eligible[:limit]
    for row in eligible[limit:]:
        row["reason"] = "outside fixed surrogate Top12"
    for rank, row in enumerate(chosen, 1):
        row.update(
            status="UNFINISHED", exact_rank=rank, reason="selected before any new exact score"
        )
    return chosen


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def source_identity() -> Record:
    root = Path(__file__).resolve().parents[3]
    evaluator = Path(native.__file__).resolve()
    baseline_file = root / "src/lottolab/application/b649_sealed_geometry_portfolio.py"
    test_file = root / "tests/unit/test_b649_k20_four_ticket_repair_pilot_r1.py"
    return {
        "base_head": BASE_HEAD,
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "worktree": str(root),
        "entrypoint_sha256": sha(Path(__file__).read_bytes()),
        "test_sha256": sha(test_file.read_bytes()),
        "baseline_source_sha256": sha(baseline_file.read_bytes()),
        "evaluator_sha256": sha(evaluator.read_bytes()),
        "evaluator_git_blob": git("hash-object", str(evaluator)),
        "python": sys.version,
        "numpy": np.__version__,
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def save_records(root: Path, records: list[Record]) -> None:
    (root / "candidates.jsonl").write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in records)
    )


def score_selected(
    selected: list[Record],
    budget: Budget,
    root: Path,
    all_records: list[Record],
) -> None:
    draws: native.DrawMasks | None = None
    for row in selected:
        budget.check()
        if draws is None:
            draws = native.all_main_draw_masks(49, 6)
            if draws.size != 13983816:
                raise AssertionError("incomplete native draw generator")
            draws.flags.writeable = False
        budget.reserve_exact()
        row["native_call_started"] = True
        save_records(root, all_records)
        started = time.monotonic()
        result = native.evaluate_portfolio(row["tickets"], draws=draws, chunk_size=1 << 18)
        if result.main_draw_count * result.special_count != DENOMINATOR:
            raise AssertionError("native outcome denominator changed")
        row.update(
            status="NEW_EXACT",
            reason="full pinned native evaluator completed",
            exact_count=result.official_any_prize_outcome_count,
            delta_count=result.official_any_prize_outcome_count - BASELINE_COUNT,
            delta_percentage_points=100
            * (result.official_any_prize_outcome_count - BASELINE_COUNT)
            / DENOMINATOR,
            exact_seconds=time.monotonic() - started,
            main_draw_count=result.main_draw_count,
            special_count=result.special_count,
            m3_plus_draw_count=result.m3_plus_draw_count,
        )
        save_records(root, all_records)
        print(
            json.dumps(
                {
                    "exact_rank": row["exact_rank"],
                    "exact_count": row["exact_count"],
                    "delta_count": row["delta_count"],
                }
            ),
            flush=True,
        )


def run_batch(root: Path, *, config: Config = FIXED_CONFIG) -> Record:
    if config != FIXED_CONFIG:
        raise ValueError("production CLI runs only the fixed Packet configuration")
    actual = source_identity()
    if (
        Path.cwd().resolve() != Path(actual["worktree"])
        or actual["branch"] != BRANCH
        or actual["evaluator_git_blob"] != EVALUATOR_BLOB
        or git("merge-base", BASE_HEAD, "HEAD") != BASE_HEAD
    ):
        raise ValueError("source/worktree/branch/evaluator identity mismatch")
    expected_root = Path(actual["worktree"]) / ".task-data" / TASK_ID
    if root.resolve() != expected_root.resolve():
        raise ValueError("output root must be the Packet's exact task root")
    root.mkdir(parents=True, exist_ok=True)
    if (root / "summary.json").exists() or (root / "candidates.jsonl").exists():
        raise FileExistsError("existing batch output: no restart or overwrite permitted")
    entry = SEALED_GEOMETRY_K20_VERSIONS["8.0.0"]
    verify_sealed_geometry_portfolio(entry)
    baseline = entry.tickets  # Actual sealed order defines the 20 destroy positions.
    if (
        entry.portfolio_sha256 != BASELINE_SHA
        or not legal(baseline)
        or entry.official_any_prize_probability * DENOMINATOR != BASELINE_COUNT
    ):
        raise ValueError("sealed K20 v8 baseline mismatch")
    with (root / "batch_started.json").open("x") as marker:
        json.dump({"task_id": TASK_ID, "identity": actual, "started_unix": time.time()}, marker)
    for name in (Path(__file__), Path(native.__file__)):
        (root / (name.name + ".executed")).write_bytes(name.read_bytes())
    plan = fixed_plan(config)
    write_json(root / "fixed_plan.json", plan)
    records: list[Record] = []
    failures: list[Record] = []
    attempted = 0
    phases = {"generation": 0.0, "filter": 0.0, "exact_scoring": 0.0}
    stop_reason: str | None = None
    failure: str | None = None
    history_metadata: Record = {}
    filter_metadata: Record = {}
    started = time.monotonic()
    budget = Budget(config, started)
    old_handler = signal.getsignal(signal.SIGALRM)

    def enforce(_signum: int, _frame: object) -> None:
        budget.check()

    # A single scientific process; all NumPy/BLAS thread env vars are set by launch.
    # RSS monitor runs every 100ms; no subprocess scoring or retained ticket cache.
    signal.signal(signal.SIGALRM, enforce)
    signal.setitimer(signal.ITIMER_REAL, 0.1, 0.1)
    phase = "generation"
    phase_start = started
    try:
        samples = seven_samples(config)
        write_json(
            root / "samples.json",
            {
                "sha256_uint64_little_endian": sha(samples.astype("<u8", copy=False).tobytes()),
                "count": int(samples.size),
            },
        )
        baseline_surrogate = int(np.count_nonzero(union_coverage(baseline, samples)))
        plan["baseline_surrogate_union"] = baseline_surrogate
        write_json(root / "fixed_plan.json", plan)
        for d, destroy in enumerate(plan["destroy_sets_zero_based_in_execution_order"]):
            for r in range(config.repairs_per_destroy_set):
                budget.check()
                attempted += 1
                portfolio, steps = repair(
                    baseline,
                    destroy,
                    plan["repair_seeds"][d][r],
                    samples,
                    config,
                    budget,
                )
                if portfolio is None:
                    failures.append(
                        {
                            "destroy_index": d,
                            "repair_index": r,
                            "steps": steps,
                            "reason": "EMPTY_REPAIR_POOL",
                        }
                    )
                    continue
                count = int(np.count_nonzero(union_coverage(portfolio, samples)))
                records.append(
                    {
                        "proposal_id": attempted,
                        "destroy_index": d,
                        "repair_index": r,
                        "destroy_positions_zero_based": destroy,
                        "steps": steps,
                        "repair_seed": plan["repair_seeds"][d][r],
                        "tickets": portfolio,
                        "portfolio_sha256": canonical_portfolio_sha256(portfolio),
                        "surrogate_union": count,
                        "surrogate_delta": count - baseline_surrogate,
                        "surrogate_kind": "SAMPLED_UNION_NOT_EXACT_NOT_A_BOUND",
                        "status": "UNFINISHED",
                        "exact_count": None,
                        "upper_bound": None,
                    }
                )
                if len(records) >= config.max_complete_proposals:
                    break
            if len(records) >= config.max_complete_proposals:
                break
        phases[phase] = time.monotonic() - phase_start
        save_records(root, records)
        phase = "filter"
        phase_start = time.monotonic()
        history, history_metadata = read_history(HISTORY_ROOT)
        filter_metadata = filter_proposals(records, baseline, history, budget)
        selected = rank_and_mark(records, config.max_exact_calls)
        # All selection and generation evidence is sealed before the first new exact result.
        write_json(
            root / "selection.json",
            {
                "selected_portfolio_sha256_in_order": [r["portfolio_sha256"] for r in selected],
                "fixed_plan_sha256": sha((root / "fixed_plan.json").read_bytes()),
                "pre_exact_candidates_sha256": sha(
                    "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records).encode()
                ),
            },
        )
        save_records(root, records)
        (root / "pre_exact_candidates.jsonl").write_bytes((root / "candidates.jsonl").read_bytes())
        phases[phase] = time.monotonic() - phase_start
        phase = "exact_scoring"
        phase_start = time.monotonic()
        score_selected(selected, budget, root, records)
        phases[phase] = time.monotonic() - phase_start
    except BudgetStop as exc:
        phases[phase] = time.monotonic() - phase_start
        stop_reason = str(exc)
        if attempted > len(records) + len(failures):
            failures.append({"proposal_id": attempted, "reason": "BUDGET_INTERRUPTED_REPAIR"})
    except Exception as exc:
        phases[phase] = time.monotonic() - phase_start
        failure = f"{type(exc).__name__}: {exc}"
        if attempted > len(records) + len(failures):
            failures.append({"proposal_id": attempted, "reason": "ERROR_INTERRUPTED_REPAIR"})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    elapsed = time.monotonic() - started
    after = source_identity()
    if after != actual:
        failure = "SOURCE_IDENTITY_CHANGED_DURING_BATCH"
    counts = {s: sum(r["status"] == s for r in records) for s in STATUSES}
    exact_rows = [r for r in records if r["status"] == "NEW_EXACT"]
    best = max(exact_rows, key=lambda r: int(r["exact_count"]), default=None)
    status = (
        "FAILED"
        if failure
        else ("PARTIAL_BUDGET_STOP" if stop_reason else "COMPLETE_BOUNDED_RESEARCH")
    )
    summary: Record = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "MODEL": "最強模型 (派工要求; 實際模型由平台配置)",
        "FINAL_SOURCE_IDENTITY": actual,
        "SOURCE_IDENTITY_AFTER": after,
        "BASELINE_IDENTITY": BASELINE_SHA,
        "BASELINE_TICKETS": baseline,
        "BASELINE_CANONICAL_COUNT": BASELINE_COUNT,
        "OUTCOME_DENOMINATOR": DENOMINATOR,
        "SUCCESS_EVENT": "exists t: |t & D|>=3 or (|t & D|=2 and s in t), s not in D",
        "PROPOSALS_ATTEMPTED": attempted,
        "COMPLETE": len(records),
        "STATUS_COUNTS": counts,
        "REPAIR_FAILURES": failures,
        "ACCOUNTING_CHECK": (
            sum(counts.values()) == len(records) and attempted == len(records) + len(failures)
        ),
        "BEST_NEW_EXACT_PORTFOLIO": best["tickets"] if best else None,
        "BEST_NEW_EXACT_COUNT": best["exact_count"] if best else None,
        "DELTA_COUNT": best["delta_count"] if best else None,
        "DELTA_PERCENTAGE_POINTS": best["delta_percentage_points"] if best else None,
        "NEW_STRICT_GAIN": (
            "WORKER_REPORTED_STRICT_GAIN"
            if best and best["delta_count"] > 0
            else "NO_IN_NEW_EXACT_SUBSET"
            if best
            else "未新增量測"
        ),
        "PROVEN_SCOPE": "completed native exact rows and individually validated reused evidence",
        "UNRESOLVED_SCOPE": "unscored proposals, other evidence/mappings, full four-ticket domain",
        "HISTORY": history_metadata,
        "FILTER": filter_metadata,
        "PHASE_SECONDS": phases,
        "TOTAL_SCIENTIFIC_TIME": elapsed,
        "PEAK_MEMORY_BYTES": peak_memory_bytes(),
        "EXACT_EVALUATOR_CALLS": budget.calls,
        "BUDGET_STOP": stop_reason,
        "FAILURE": failure,
        "MEMORY_CONTROL": "100ms SIGALRM process RSS monitor; one process; bounded arrays",
        "SCIENTIFIC_PROCESSES": 1,
        "BATCHES": 1,
        "INDEPENDENT_VERIFICATION": "NOT RUN",
        "FORMAL_ADOPTION": "NOT RUN",
        "INSTALLATION": "NOT RUN",
        "PRODUCTION_LOADING": "NOT RUN",
        "PREDICTIVE_LIFT": "NOT MEASURED",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "SKILL_REVISION": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
    }
    save_records(root, records)
    write_json(root / "summary.json", summary)
    print(
        json.dumps(
            {
                "TASK_STATUS": status,
                "STATUS_COUNTS": counts,
                "BEST_NEW_EXACT_COUNT": summary["BEST_NEW_EXACT_COUNT"],
            }
        ),
        flush=True,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    summary = run_batch(args.output_root)
    if summary["TASK_STATUS"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
