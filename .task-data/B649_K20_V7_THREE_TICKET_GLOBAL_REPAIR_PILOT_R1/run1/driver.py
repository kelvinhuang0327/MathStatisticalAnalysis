from __future__ import annotations

import ast
import fcntl
import hashlib
import importlib.util
import itertools
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ENGINE_SRC = RUN / "engine" / "src"
RESULT_PATH = ROOT / "docs/research/matrix-native-results/b649-k20-v7-three-ticket-global-repair-pilot-r1-result.json"
SAMPLE_PATH = RUN / "destroy-triples-sample.json"
SET_RESULTS_PATH = RUN / "set-results.jsonl"
PROGRESS_PATH = RUN / "progress.jsonl"
LOCK_PATH = RUN / "execution.lock"
TASK_ID = "B649_K20_V7_THREE_TICKET_GLOBAL_REPAIR_PILOT_R1"
START_COUNT = 313239661
START_SHA256 = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
EXPECTED_ELITE = {
    "ELITE_V5": "bc755e9b674e2ff37dac0fc8b52bb9f01bfd5a2bf90fc5f9f245dbb049c0ae86",
    "ELITE_V6": "0c52a1f0bed90cd47d08bb031b13c9bf693317493f88e45da8e087bd4a0ab65b",
    "ELITE_V7": START_SHA256,
}
ELITE_COMMITS = {
    "ELITE_V5": "56c9715ca60bb9af3afe3b5faae83b0dc0471d8f",
    "ELITE_V6": "76085ccc8f226c8752cc7df28390e27009d21746",
}
SAMPLE_RULE_ID = "SHA256_RANKED_DESTROY_TRIPLES_V1"
SAMPLE_SEED = 20261003
SAMPLE_COUNT = 64
GLOBAL_TOP_MARGINAL = 64
REPAIR_POOL_MAX = 80

sys.path.insert(0, str(ENGINE_SRC))
from lottolab.research import b649_k20_global_residual_pool_repair_r1 as core  # noqa: E402
from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as exact  # noqa: E402
from lottolab.research.b649_official_any_prize_exact import ticket_mask  # noqa: E402


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def digest_json(value: Any) -> str:
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def append_jsonl(path: Path, value: Any) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(compact_json(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def current_start() -> exact.Portfolio:
    path = ROOT / "src/lottolab/application/b649_sealed_geometry_portfolio.py"
    spec = importlib.util.spec_from_file_location("current_sealed_geometry", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the current canonical K20 portfolio source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    entry = module.SEALED_GEOMETRY_PORTFOLIOS[20]
    module.verify_sealed_geometry_portfolio(entry)
    tickets = tuple(tuple(ticket) for ticket in entry.tickets)
    if module.canonical_portfolio_sha256(tickets) != START_SHA256:
        raise RuntimeError("START_IDENTITY_MISMATCH")
    return tickets


def extract_k20_from_commit(commit: str) -> exact.Portfolio:
    path = "src/lottolab/application/b649_sealed_geometry_portfolio.py"
    source = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT, text=True)
    section = source.split("_K20 = SealedGeometryPortfolio(", 1)[1]
    match = re.search(r"tickets=(\s*\(.*?\n\s*\)),\n\s*portfolio_sha256", section, re.S)
    if match is None:
        raise RuntimeError(f"cannot extract K20 tickets from {commit}")
    tickets = ast.literal_eval(match.group(1))
    return tuple(tuple(ticket) for ticket in tickets)


def verify_elites(start: exact.Portfolio) -> tuple[dict[str, dict[str, Any]], tuple[exact.Ticket, ...]]:
    portfolios = {
        "ELITE_V5": extract_k20_from_commit(ELITE_COMMITS["ELITE_V5"]),
        "ELITE_V6": extract_k20_from_commit(ELITE_COMMITS["ELITE_V6"]),
        "ELITE_V7": start,
    }
    records: dict[str, dict[str, Any]] = {}
    for name, tickets in portfolios.items():
        actual = exact.portfolio_sha256(tickets)
        record = {
            "SOURCE_COMMIT": ELITE_COMMITS.get(name, "CURRENT_CANONICAL_START"),
            "TICKET_COUNT": len(tickets),
            "EXPECTED_SHA256": EXPECTED_ELITE[name],
            "ACTUAL_SHA256": actual,
            "SHA_VERIFIED": actual == EXPECTED_ELITE[name] and len(tickets) == 20,
        }
        records[name] = record
        if not record["SHA_VERIFIED"]:
            raise RuntimeError(f"ELITE_SOURCE_IDENTITY_MISMATCH:{name}:{record}")
    unique = tuple(sorted({ticket for tickets in portfolios.values() for ticket in tickets}))
    return records, unique


def freeze_sample() -> tuple[list[tuple[int, int, int]], str, str]:
    all_triples = list(itertools.combinations(range(20), 3))
    ranked = sorted(
        all_triples,
        key=lambda triple: (
            hashlib.sha256(
                f"{SAMPLE_SEED}|{triple[0]}|{triple[1]}|{triple[2]}".encode("utf-8")
            ).hexdigest(),
            triple,
        ),
    )
    selected = sorted(ranked[:SAMPLE_COUNT])
    triple_lists = [list(triple) for triple in selected]
    triples_sha = digest_json(triple_lists)
    document = {
        "TASK_ID": TASK_ID,
        "SAMPLE_RULE_ID": SAMPLE_RULE_ID,
        "SAMPLE_SEED": SAMPLE_SEED,
        "POPULATION_SIZE": len(all_triples),
        "DESTROY_TRIPLE_SAMPLE_COUNT": SAMPLE_COUNT,
        "RANKING_DIGEST_FORMAT": "sha256(UTF8(seed|i|j|k)), ascending hex then lexicographic triple",
        "PERSISTED_TRIPLES_ORDER": "lexicographic",
        "DESTROY_TRIPLES_SAMPLE_SHA256": triples_sha,
        "DESTROY_TRIPLES": triple_lists,
    }
    payload = compact_json(document).encode("utf-8")
    if SAMPLE_PATH.exists():
        if SAMPLE_PATH.read_bytes() != payload:
            raise RuntimeError("persisted destroy sample differs from the frozen deterministic sample")
    else:
        with SAMPLE_PATH.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    file_sha = hashlib.sha256(SAMPLE_PATH.read_bytes()).hexdigest()
    return selected, triples_sha, file_sha


def load_completed_sets() -> dict[tuple[int, int, int], dict[str, Any]]:
    if not SET_RESULTS_PATH.exists():
        return {}
    completed: dict[tuple[int, int, int], dict[str, Any]] = {}
    for line in SET_RESULTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        positions = tuple(row["POSITIONS"])
        if len(positions) != 3 or positions in completed:
            raise RuntimeError("invalid or duplicate completed destroy record")
        completed[positions] = row
    return completed


def residual_pool_histogram(remaining: exact.Portfolio, pool: exact.Portfolio) -> tuple[np.ndarray, np.ndarray, int, int]:
    if len(pool) > REPAIR_POOL_MAX or len(pool) <= 64:
        raise ValueError("the two-mask implementation requires a pool in 65..80")
    remaining_masks = [np.uint64(ticket_mask(ticket)) for ticket in remaining]
    low_masks = [np.uint64(ticket_mask(ticket)) for ticket in pool[:64]]
    high_masks = [np.uint64(ticket_mask(ticket)) for ticket in pool[64:]]
    partial_patterns: list[np.ndarray] = []
    partial_weights: list[np.ndarray] = []
    total_subsets = 0
    covered_by_remaining = 0
    zero_winner_subsets = 0
    for block in core.iter_subset_mask_blocks(49, 7):
        covered = np.zeros(block.size, dtype=np.bool_)
        for mask in remaining_masks:
            covered |= np.bitwise_count(block & mask) >= 3
        residual = block[~covered]
        total_subsets += int(block.size)
        covered_by_remaining += int(block.size - residual.size)
        low = np.zeros(residual.size, dtype=np.uint64)
        high = np.zeros(residual.size, dtype=np.uint64)
        for index, mask in enumerate(low_masks):
            low |= (np.bitwise_count(residual & mask) >= 3).astype(np.uint64) << np.uint64(index)
        for index, mask in enumerate(high_masks):
            high |= (np.bitwise_count(residual & mask) >= 3).astype(np.uint64) << np.uint64(index)
        zero_winner_subsets += int(np.count_nonzero((low == 0) & (high == 0)))
        keys = np.column_stack((low, high))
        unique, counts = np.unique(keys, axis=0, return_counts=True)
        partial_patterns.append(unique)
        partial_weights.append(counts.astype(np.int64))
    if total_subsets != core.comb(49, 7):
        raise AssertionError("histogram did not enumerate all legal 7-subsets")
    keys = np.concatenate(partial_patterns, axis=0)
    counts = np.concatenate(partial_weights)
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    weights = np.bincount(inverse, weights=counts).astype(np.int64)
    live = np.any(unique != 0, axis=1)
    patterns = unique[live]
    weights = weights[live]
    if int(weights.sum()) + zero_winner_subsets != total_subsets - covered_by_remaining:
        raise AssertionError("histogram residual subset accounting failed")
    return patterns, weights, covered_by_remaining, zero_winner_subsets


def solve_three(patterns: np.ndarray, weights: np.ndarray, pool_count: int) -> dict[str, Any]:
    singles = np.zeros(pool_count, dtype=np.int64)
    pairs = np.zeros((pool_count, pool_count), dtype=np.int64)
    triples = np.zeros((pool_count, pool_count, pool_count), dtype=np.int64)
    for (low_value, high_value), raw_weight in zip(patterns, weights, strict=True):
        low = int(low_value)
        high = int(high_value)
        winners: list[int] = []
        while low:
            bit = low & -low
            winners.append(bit.bit_length() - 1)
            low ^= bit
        while high:
            bit = high & -high
            winners.append(64 + bit.bit_length() - 1)
            high ^= bit
        weight = int(raw_weight)
        for index in winners:
            singles[index] += weight
        for i, j in itertools.combinations(winners, 2):
            pairs[i, j] += weight
        for i, j, k in itertools.combinations(winners, 3):
            triples[i, j, k] += weight
    best = -1
    optimal: list[tuple[int, int, int]] = []
    evaluated = 0
    for i, j, k in itertools.combinations(range(pool_count), 3):
        value = (
            int(singles[i]) + int(singles[j]) + int(singles[k])
            - int(pairs[i, j]) - int(pairs[i, k]) - int(pairs[j, k])
            + int(triples[i, j, k])
        )
        evaluated += 1
        if value > best:
            best = value
            optimal = [(i, j, k)]
        elif value == best:
            optimal.append((i, j, k))
    expected = core.comb(pool_count, 3)
    if evaluated != expected or not optimal:
        raise AssertionError("replacement triple enumeration was incomplete")
    parity_checks = 0
    for i, j, k in itertools.islice(itertools.combinations(range(pool_count), 3), 16):
        low_mask = sum(1 << index for index in (i, j, k) if index < 64)
        high_mask = sum(1 << (index - 64) for index in (i, j, k) if index >= 64)
        direct = int(
            weights[
                ((patterns[:, 0] & np.uint64(low_mask)) != 0)
                | ((patterns[:, 1] & np.uint64(high_mask)) != 0)
            ].sum()
        )
        inclusion_exclusion = (
            int(singles[i]) + int(singles[j]) + int(singles[k])
            - int(pairs[i, j]) - int(pairs[i, k]) - int(pairs[j, k])
            + int(triples[i, j, k])
        )
        if direct != inclusion_exclusion:
            raise AssertionError("three-ticket inclusion-exclusion parity failed")
        parity_checks += 1
    return {
        "BEST_RESIDUAL_SUBSETS": best,
        "OPTIMAL_POOL_INDEX_TRIPLES": optimal,
        "CANDIDATE_TRIPLES_EVALUATED": evaluated,
        "CANDIDATE_TRIPLES_EXPECTED": expected,
        "TRIPLE_INTERSECTION_NONZERO_COUNT": int(np.count_nonzero(triples)),
        "DIRECT_TRIPLE_PARITY_COMPARISONS": parity_checks,
    }


def verify_direct_marginals(
    remaining: exact.Portfolio,
    pool: exact.Portfolio,
    scores: core.GlobalScores,
    universe: core.ColexUniverse,
) -> int:
    probes = [pool[index] for index in sorted({0, 1, 2, 3, 7, 15, 31, len(pool) - 1})]
    direct = exact.direct_marginals(remaining, probes)
    for ticket, actual in zip(probes, direct, strict=True):
        expected = int(scores.marginals[universe.index_of(ticket)])
        if actual != expected:
            raise AssertionError(f"direct/global marginal mismatch for {ticket}: {actual} != {expected}")
    return len(probes)


def score_destroy(
    positions: tuple[int, int, int],
    start: exact.Portfolio,
    elites: tuple[exact.Ticket, ...],
    universe: core.ColexUniverse,
    recounter: exact.CanonicalRecounter,
) -> dict[str, Any]:
    wall_started = time.perf_counter()
    destroyed = exact.destroy_positions(start, positions)
    remaining_count = recounter.count(destroyed.remaining)
    if remaining_count % 7:
        raise AssertionError("frozen remainder canonical count is not divisible by seven")
    residual_subsets = core.comb(49, 7) - remaining_count // 7
    scores = core.score_all_tickets(universe, destroyed.remaining)
    identities = core.check_score_identities(scores, universe, residual_subsets)
    eligible_marginals = scores.marginals.copy()
    remaining_set = set(destroyed.remaining)
    for ticket in destroyed.remaining:
        eligible_marginals[universe.index_of(ticket)] = -1
    top_indices = core.top_ticket_indices(eligible_marginals, universe.tickets, GLOBAL_TOP_MARGINAL)
    top_tickets = tuple(universe.ticket_at(int(index)) for index in top_indices)
    if len(top_tickets) != GLOBAL_TOP_MARGINAL or any(ticket in remaining_set for ticket in top_tickets):
        raise AssertionError("global top-64 filtering included a frozen ticket")
    top_set = set(top_tickets)
    removed_set = set(destroyed.removed)
    base_pool = top_set | removed_set
    if not top_set.issubset(base_pool) or not removed_set.issubset(base_pool):
        raise AssertionError("base pool dropped a required top-64 or removed ticket")
    elite_only = sorted(set(elites) - remaining_set - base_pool)
    elite_only.sort(key=lambda ticket: (-int(scores.marginals[universe.index_of(ticket)]), ticket))
    elite_capacity = REPAIR_POOL_MAX - len(base_pool)
    elite_added = elite_only[:elite_capacity]
    pool_source: dict[exact.Ticket, str] = {ticket: "GLOBAL_TOP64" for ticket in top_set}
    pool_source.update({ticket: "REMOVED_INCUMBENT" for ticket in removed_set})
    pool_source.update({ticket: "STABLE_ELITE" for ticket in elite_added})
    pool = tuple(sorted(pool_source))
    if len(pool) > REPAIR_POOL_MAX or len(top_set - set(pool)) != 0 or len(removed_set - set(pool)) != 0:
        raise AssertionError("repair-pool construction violated a mandatory-retention rule")
    if len(pool) > 64:
        patterns, weights, covered_by_remaining, zero_winner_subsets = residual_pool_histogram(
            destroyed.remaining, pool
        )
        solution = solve_three(patterns, weights, len(pool))
    else:
        histogram = core.build_repair_histogram(destroyed.remaining, pool)
        singles = np.array([histogram.subset_value([i]) for i in range(len(pool))], dtype=np.int64)
        pair_values = np.zeros((len(pool), len(pool)), dtype=np.int64)
        for i, j in itertools.combinations(range(len(pool)), 2):
            pair_values[i, j] = int(histogram.subset_value((i, j)))
        # The task's construction always includes 64 distinct global tickets plus three removals;
        # this fallback protects correctness if a future canonical source collapses duplicates.
        triples_list = []
        best_value = -1
        for i, j, k in itertools.combinations(range(len(pool)), 3):
            value = int(histogram.subset_value((i, j, k)))
            if value > best_value:
                best_value, triples_list = value, [(i, j, k)]
            elif value == best_value:
                triples_list.append((i, j, k))
        solution = {
            "BEST_RESIDUAL_SUBSETS": best_value,
            "OPTIMAL_POOL_INDEX_TRIPLES": triples_list,
            "CANDIDATE_TRIPLES_EVALUATED": core.comb(len(pool), 3),
            "CANDIDATE_TRIPLES_EXPECTED": core.comb(len(pool), 3),
            "TRIPLE_INTERSECTION_NONZERO_COUNT": None,
        }
        patterns = histogram.masks.reshape(-1, 1)
        weights = histogram.weights
        covered_by_remaining = histogram.covered_by_remaining
        zero_winner_subsets = histogram.dead_subsets
    expected_start = recounter.count(start)
    if expected_start != START_COUNT:
        raise AssertionError("start portfolio canonical recount drifted")
    removed_indices = tuple(pool.index(ticket) for ticket in destroyed.removed)
    if len(removed_indices) != 3:
        raise AssertionError("removed incumbent triple is not retained in the repair pool")
    if len(pool) > 64:
        initial_score = sum(int(scores.marginals[universe.index_of(t)]) for t in destroyed.removed)
        initial_union = 0
        for mask_pair, weight in zip(patterns, weights, strict=True):
            low = int(mask_pair[0])
            high = int(mask_pair[1])
            if any(
                ((low >> index) & 1) if index < 64 else ((high >> (index - 64)) & 1)
                for index in removed_indices
            ):
                initial_union += int(weight)
    else:
        initial_union = int(histogram.subset_value(removed_indices))
    if covered_by_remaining * 7 + initial_union * 7 != START_COUNT:
        raise AssertionError("removed-ticket baseline differs from the canonical start count")
    candidates: list[dict[str, Any]] = []
    for chosen in solution["OPTIMAL_POOL_INDEX_TRIPLES"]:
        portfolio = exact.normalize_portfolio((*destroyed.remaining, *(pool[index] for index in chosen)))
        portfolio_sha = exact.portfolio_sha256(portfolio)
        exact_count = recounter.count(portfolio)
        expected_count = (covered_by_remaining + int(solution["BEST_RESIDUAL_SUBSETS"])) * 7
        if exact_count != expected_count:
            raise AssertionError(
                f"canonical recount mismatch for {portfolio_sha}: {exact_count} != {expected_count}"
            )
        candidates.append(
            {
                "POOL_INDICES": list(chosen),
                "REPLACEMENTS": [list(pool[index]) for index in chosen],
                "PORTFOLIO": [list(ticket) for ticket in portfolio],
                "DESTROY_POSITIONS": list(positions),
                "PORTFOLIO_SHA256": portfolio_sha,
                "CANONICAL_COUNT": exact_count,
            }
        )
    candidates.sort(key=lambda item: (item["PORTFOLIO_SHA256"], item["POOL_INDICES"]))
    best = candidates[0]
    direct_comparisons = verify_direct_marginals(destroyed.remaining, pool, scores, universe)
    row = {
        "POSITIONS": list(positions),
        "REMOVED_TICKETS": [list(ticket) for ticket in destroyed.removed],
        "R_SIZE": len(destroyed.remaining),
        "FROZEN_REMAINDER_CANONICAL_COUNT": remaining_count,
        "RESIDUAL_SUBSETS": residual_subsets,
        "TICKETS_SCORED": scores.tickets_scored,
        "GLOBAL_IDENTITIES": identities,
        "GLOBAL_TOP64": [
            {"RANK": rank, "TICKET": list(ticket), "RESIDUAL_MARGINAL_7SUBSETS": int(scores.marginals[index])}
            for rank, (index, ticket) in enumerate(zip(top_indices, top_tickets, strict=True), start=1)
        ],
        "GLOBAL_TOP64_DROPPED_FOR_ELITES": 0,
        "BASE_POOL_SIZE": len(base_pool),
        "ELITE_ONLY_CANDIDATE_COUNT": len(elite_only),
        "ELITE_CAPACITY": elite_capacity,
        "ELITE_TICKETS_ADDED": [
            {"TICKET": list(ticket), "RESIDUAL_MARGINAL_7SUBSETS": int(scores.marginals[universe.index_of(ticket)])}
            for ticket in elite_added
        ],
        "POOL_SIZE": len(pool),
        "POOL_SOURCES": [
            {"TICKET": list(ticket), "SOURCE": pool_source[ticket]}
            for ticket in pool
        ],
        "HISTOGRAM_ROWS": int(len(patterns)),
        "ZERO_WINNER_RESIDUAL_SUBSETS": zero_winner_subsets,
        "HISTOGRAM_COVERED_BY_R": covered_by_remaining,
        "DIRECT_MARGINAL_PARITY_COMPARISONS": direct_comparisons,
        "DIRECT_TRIPLE_PARITY_COMPARISONS": solution.get("DIRECT_TRIPLE_PARITY_COMPARISONS", 0),
        "EXACT_CANDIDATE_TRIPLES_EVALUATED": solution["CANDIDATE_TRIPLES_EVALUATED"],
        "EXACT_CANDIDATE_TRIPLES_EXPECTED": solution["CANDIDATE_TRIPLES_EXPECTED"],
        "PROVEN_OPTIMALITY_STATUS": "PROVEN_OPTIMAL",
        "BEST_RESIDUAL_SUBSETS": solution["BEST_RESIDUAL_SUBSETS"],
        "BEST_COUNT": best["CANONICAL_COUNT"],
        "BEST_DELTA": best["CANONICAL_COUNT"] - START_COUNT,
        "BEST_PORTFOLIO_SHA256": best["PORTFOLIO_SHA256"],
        "BEST_REPLACEMENTS": best["REPLACEMENTS"],
        "OPTIMAL_SET_COUNT": len(candidates),
        "ALL_OPTIMAL_SETS_CANONICALLY_RECOUNTED": True,
        "CANONICALLY_RECOUNTED_OPTIMA": candidates,
        "TIE_BREAK": "highest exact count, then lowest normalized portfolio SHA-256",
        "SECONDS_TOTAL": round(time.perf_counter() - wall_started, 3),
        "SECONDS_GLOBAL_SCORE": round(scores.seconds, 3),
    }
    return row


def run() -> dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if RESULT_PATH.exists():
            raise FileExistsError(f"refusing to overwrite {RESULT_PATH}")
        start = current_start()
        triples, triples_sha, sample_file_sha = freeze_sample()
        elite_records, elite_union = verify_elites(start)
        start_recounter = exact.CanonicalRecounter()
        start_count = start_recounter.count(start)
        if start_count != START_COUNT or exact.portfolio_sha256(start) != START_SHA256:
            raise RuntimeError("START_REPRODUCTION_MISMATCH")
        universe = core.build_universe()
        completed = load_completed_sets()
        if any(key not in triples for key in completed):
            raise RuntimeError("checkpoint contains a destroy triple outside the frozen sample")
        append_jsonl(
            PROGRESS_PATH,
            {
                "EVENT": "RUN_STARTED",
                "TASK_ID": TASK_ID,
                "SAMPLE_SHA256": triples_sha,
                "COMPLETED_SETS_AT_START": len(completed),
                "AT_UTC": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
        recounter = start_recounter
        records = dict(completed)
        for positions in triples:
            if positions in records:
                continue
            row = score_destroy(positions, start, elite_union, universe, recounter)
            append_jsonl(SET_RESULTS_PATH, row)
            records[positions] = row
            append_jsonl(
                PROGRESS_PATH,
                {
                    "EVENT": "DESTROY_TRIPLE_COMPLETE",
                    "POSITIONS": list(positions),
                    "BEST_DELTA": row["BEST_DELTA"],
                    "POOL_SIZE": row["POOL_SIZE"],
                    "SECONDS_TOTAL": row["SECONDS_TOTAL"],
                },
            )
            print(
                f"complete={len(records)}/{SAMPLE_COUNT} positions={positions} "
                f"pool={row['POOL_SIZE']} delta={row['BEST_DELTA']}",
                flush=True,
            )
        ordered = [records[positions] for positions in triples]
        all_optima = [candidate for row in ordered for candidate in row["CANONICALLY_RECOUNTED_OPTIMA"]]
        winner = min(
            all_optima,
            key=lambda candidate: (-candidate["CANONICAL_COUNT"], candidate["PORTFOLIO_SHA256"]),
        )
        run_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        run_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()
        driver_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        result = {
            "SCHEMA_VERSION": "B649_K20_THREE_TICKET_GLOBAL_REPAIR_RESULT_V1",
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "COMPLETE",
            "SCIENTIFIC_SCOPE": "64_SHA256_RANKED_DESTROY3_GLOBAL_TOP64_POOL80_EXACT_THREE_REPLACEMENT_REPAIRS",
            "SCIENTIFIC_RESULT": "IMPROVED" if winner["CANONICAL_COUNT"] > START_COUNT else "NO_IMPROVEMENT_IN_FROZEN_64_DESTROY_TRIPLE_SAMPLE",
            "START_COUNT": START_COUNT,
            "START_SHA256": START_SHA256,
            "START_REPRODUCTION": {"CANONICAL_COUNT": start_count, "PORTFOLIO_SHA256": exact.portfolio_sha256(start)},
            "ELITE_V5_SHA_VERIFIED": "YES" if elite_records["ELITE_V5"]["SHA_VERIFIED"] else "NO",
            "ELITE_V6_SHA_VERIFIED": "YES" if elite_records["ELITE_V6"]["SHA_VERIFIED"] else "NO",
            "ELITE_V7_SHA_VERIFIED": "YES" if elite_records["ELITE_V7"]["SHA_VERIFIED"] else "NO",
            "ELITE_SOURCE_VERIFICATION": elite_records,
            "STABLE_ELITE_UNIQUE_TICKET_COUNT": len(elite_union),
            "SAMPLE_RULE_ID": SAMPLE_RULE_ID,
            "SAMPLE_SEED": SAMPLE_SEED,
            "DESTROY_TRIPLE_SAMPLE_COUNT": SAMPLE_COUNT,
            "DESTROY_TRIPLES_SAMPLE_SHA256": triples_sha,
            "DESTROY_TRIPLES_SAMPLE_SHA256_FORMAT": "SHA-256 of compact JSON array of lexicographically ordered triples",
            "DESTROY_TRIPLES_SAMPLE_FILE_SHA256": sample_file_sha,
            "DESTROY_TRIPLES": [list(triple) for triple in triples],
            "GLOBAL_TOP_MARGINAL": GLOBAL_TOP_MARGINAL,
            "REPAIR_POOL_MAX": REPAIR_POOL_MAX,
            "GLOBAL_TOP64_DROPPED_FOR_ELITES": 0,
            "REPAIR_POOL_MIN": min(row["POOL_SIZE"] for row in ordered),
            "REPAIR_POOL_MAX_ACTUAL": max(row["POOL_SIZE"] for row in ordered),
            "REPAIR_POOL_MEAN": round(sum(row["POOL_SIZE"] for row in ordered) / len(ordered), 3),
            "GLOBAL_ENUMERATION_COMPLETE_SETS": len(ordered),
            "GLOBAL_TICKET_UNIVERSE_SIZE": 13983816,
            "GLOBAL_TICKETS_SCORED_TOTAL": sum(row["TICKETS_SCORED"] for row in ordered),
            "PROVEN_OPTIMAL_REPAIR_SETS": sum(row["PROVEN_OPTIMALITY_STATUS"] == "PROVEN_OPTIMAL" for row in ordered),
            "EXACT_REPLACEMENT_TRIPLES_EVALUATED_TOTAL": sum(row["EXACT_CANDIDATE_TRIPLES_EVALUATED"] for row in ordered),
            "BEST_COUNT": winner["CANONICAL_COUNT"],
            "BEST_DELTA": winner["CANONICAL_COUNT"] - START_COUNT,
            "BEST_SHA256": winner["PORTFOLIO_SHA256"],
            "BEST_PORTFOLIO": winner["PORTFOLIO"],
            "BEST_DESTROY_INDICES": winner["DESTROY_POSITIONS"],
            "BEST_NEW_TICKETS": winner["REPLACEMENTS"],
            "BEST_CANONICAL_RECOUNT": winner["CANONICAL_COUNT"],
            "BEST_CANONICAL_RECOUNT_STATUS": "PASS",
            "BEST_COUNT_TIE_COUNT": sum(candidate["CANONICAL_COUNT"] == winner["CANONICAL_COUNT"] for candidate in all_optima),
            "TIE_BREAK": "highest exact canonical count, then lowest normalized portfolio SHA-256",
            "PARITY_MISMATCHES": 0,
            "PARITY": {
                "GLOBAL_ENUMERATION_COUNT_CHECKS": len(ordered),
                "GLOBAL_SCORE_IDENTITY_CHECKS": len(ordered),
                "DIRECT_GLOBAL_MARGINAL_COMPARISONS": sum(row["DIRECT_MARGINAL_PARITY_COMPARISONS"] for row in ordered),
                "DIRECT_TRIPLE_INCLUSION_EXCLUSION_COMPARISONS": sum(row["DIRECT_TRIPLE_PARITY_COMPARISONS"] for row in ordered),
                "FROZEN_REMAINDER_AND_HISTOGRAM_BASELINE_CHECKS": len(ordered),
                "ALL_OPTIMAL_PORTFOLIO_CANONICAL_RECOUNTS_MATCH": all(
                    candidate["CANONICAL_COUNT"] == (row["HISTOGRAM_COVERED_BY_R"] + row["BEST_RESIDUAL_SUBSETS"]) * 7
                    for row in ordered
                    for candidate in row["CANONICALLY_RECOUNTED_OPTIMA"]
                ),
            },
            "PER_DESTROY_TRIPLE": ordered,
            "SOLVER": "EXHAUSTIVE_THREE_TICKET_ENUMERATION_WITH_EXACT_WINNER_PATTERN_INCLUSION_EXCLUSION",
            "SOLVER_DETAIL": "All C(pool,3) distinct replacement triples are evaluated from exact weighted residual winner-pattern intersections; no heuristic pruning; every optimum SHA tie is canonically recounted.",
            "CPU_POLICY": {"RESOURCE_POLICY": "SHARED_WORKSTATION", "WORKERS": 1, "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "1"), "AUTO_SCALING": "FORBIDDEN"},
            "OUTCOME_INFORMATION_USED": "NONE",
            "PROTECTED_LANE_3_TOUCHED": "NO",
            "PROJECT_MEMORY_WRITTEN": "NO",
            "PRODUCTION_CHANGE": "NONE",
            "PUSH": "NO",
            "PR": "NOT_CREATED",
            "RUN_HEAD": run_head,
            "RUN_TREE": run_tree,
            "DRIVER_PATH": str(Path(__file__).resolve()),
            "DRIVER_SHA256": driver_sha,
            "RUNTIME_EVIDENCE_PATH": str(RUN),
            "RESULT_LOCATOR": str(RESULT_PATH),
            "REUSED_ENGINE_SHA256": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted((RUN / "engine/src/lottolab/research").glob("*.py"))
            },
        }
        if len(ordered) != SAMPLE_COUNT or result["PROVEN_OPTIMAL_REPAIR_SETS"] != SAMPLE_COUNT:
            raise AssertionError("final acceptance set is incomplete")
        if result["GLOBAL_TICKETS_SCORED_TOTAL"] != SAMPLE_COUNT * 13983816:
            raise AssertionError("not every legal ticket was scored for every selected triple")
        if RESULT_PATH.exists():
            raise FileExistsError(f"refusing to overwrite {RESULT_PATH}")
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        exact.write_atomically(RESULT_PATH, compact_json(result))
        append_jsonl(PROGRESS_PATH, {"EVENT": "RESULT_WRITTEN", "PATH": str(RESULT_PATH)})
        return result


if __name__ == "__main__":
    result = run()
    print(
        f"RESULT={result['SCIENTIFIC_RESULT']} BEST_COUNT={result['BEST_COUNT']} "
        f"BEST_DELTA={result['BEST_DELTA']} REPAIRS={result['PROVEN_OPTIMAL_REPAIR_SETS']}",
        flush=True,
    )
