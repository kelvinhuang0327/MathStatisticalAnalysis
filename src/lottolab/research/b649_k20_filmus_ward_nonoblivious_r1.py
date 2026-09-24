# pyright: reportPrivateUsage=false
"""Bounded Filmus-Ward-style non-oblivious search for the pinned B649 K20 champion."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import platform
import random
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt

from lottolab.research import (
    b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as bonferroni,
)
from lottolab.research.b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_runner import (
    load_and_verify_pinned_incumbent,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type IntArray = npt.NDArray[np.int64]
type MaskArray = npt.NDArray[np.uint64]
type CountArray = npt.NDArray[np.uint8]
type PotentialPair = tuple[int, int]

TASK_ID = "B649_K20_FILMUS_WARD_NONOBLIVIOUS_R1"
RUN_ID = "RUN1"
BRANCH = "b649-k20-filmus-ward-nonoblivious-r1"
BASE_HEAD = "b24646d1ba86690bffd1acdf21fec5b64c56834d"
BASE_TREE = "d2fe5f0ef46c4518ff960f9e10d8ba1f3e14c4d8"
INCUMBENT_PATH = (
    "docs/research/matrix-native-results/b649-k20-cross-swap-champion-r1.json"
)
INCUMBENT_SHA256 = "5a2839db8fe5cd38f03366968cc6a024a5aa378ab360d4d049b9b45baa8e84df"
INCUMBENT_BLOB = "a5bc9a73d5c31cf44a4c79cafb69b0af3d9fc5d5"
INCUMBENT_PORTFOLIO_SHA256 = (
    "4343a4aa699050f71d5913d26d59b138d637c8aad3528111d9bcf6d69593546b"
)
INCUMBENT_OUTCOME_COUNT = 312_867_226
INCUMBENT_FRACTION = "519713/998844"
TOTAL_OFFICIAL_OUTCOMES = 601_304_088

IMPLEMENTATION_PATH = "src/lottolab/research/b649_k20_filmus_ward_nonoblivious_r1.py"
TEST_PATH = "tests/unit/test_b649_k20_filmus_ward_nonoblivious_r1.py"
PREREGISTRATION_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-filmus-ward-nonoblivious-r1-preregistration.json"
)
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-filmus-ward-nonoblivious-r1-result.json"
)
REPORT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-filmus-ward-nonoblivious-r1-report.md"
)
EVIDENCE_RELATIVE_PATH = (
    ".task-data/B649_K20_FILMUS_WARD_NONOBLIVIOUS_R1/run1"
)

SEED = 64_920
REQUIRED_PYTHON = (3, 13, 8)
ROUNDS = 8
RAW_PROPOSALS_PER_ROUND = 32
TOTAL_RAW_PROPOSALS = ROUNDS * RAW_PROPOSALS_PER_ROUND
HISTOGRAM_CHUNK_SIZE = 65_536
WALL_CLOCK_LIMIT_SECONDS = 3_600
MAX_DISTINCT_PROPOSAL_EVALUATIONS = 256
MAX_ACCEPTED_SEARCH_MOVES = 8
MAX_MARGINAL_HISTOGRAM_EVALUATIONS = 416
MAX_CANONICAL_EXACT_CALLS = 272
OUTCOME_SIZE = BIG_LOTTO_DRAW_SIZE + 1
MINIMUM_TICKET_HITS = 3
TOTAL_SEVEN_SETS = math.comb(BIG_LOTTO_POOL_SIZE, OUTCOME_SIZE)
SEAL_COMMIT_SUBJECT = "research(b649): seal Filmus-Ward nonoblivious r1"


class IncompleteRun(RuntimeError):
    """Raised when a required run decision or invariant cannot be completed."""


class ExperimentTimeout(IncompleteRun):
    """Raised when the frozen RUN1 wall-clock budget expires."""


@dataclass(frozen=True, slots=True)
class RawProposal:
    slot: int
    ticket_index: int
    old_ticket: Ticket
    new_ticket: Ticket
    removed_sample: tuple[int, ...]
    added_sample: tuple[int, ...]
    sample_order: tuple[int, ...]
    rng_state_before: object
    rng_state_after: object


@dataclass(slots=True)
class CandidateEvaluation:
    portfolio: Portfolio
    portfolio_sha256: str
    potential_a: int
    potential_b: int
    potential_sign: int
    u3_outcome_count: int
    exact_outcome_count: int | None
    exact_fraction: str | None
    raw_record: dict[str, object]


@dataclass(slots=True)
class RunSummary:
    run_status: str = "BOUNDED_INCOMPLETE"
    termination_reason: str = "NOT_STARTED"
    final_decision: str = "BOUNDED_INCOMPLETE"
    start_utc: str = ""
    end_utc: str = ""
    duration_seconds: float = 0.0
    implementation_seal_head: str | None = None
    implementation_seal_tree: str | None = None
    initial_portfolio: Portfolio | None = None
    initial_portfolio_sha256: str | None = None
    initial_outcome_count: int | None = None
    initial_fraction: str | None = None
    final_x: Portfolio | None = None
    final_x_sha256: str | None = None
    final_x_outcome_count: int | None = None
    final_x_fraction: str | None = None
    final_champion: Portfolio | None = None
    final_champion_sha256: str | None = None
    final_champion_outcome_count: int | None = None
    final_champion_fraction: str | None = None
    relative_potential_a: int = 0
    relative_potential_b: int = 0
    rounds_completed: int = 0
    raw_proposal_count: int = 0
    distinct_legal_proposal_count: int = 0
    no_op_count: int = 0
    duplicate_ticket_count: int = 0
    repeated_candidate_count: int = 0
    marginal_histogram_evaluation_count: int = 0
    marginal_histogram_request_count: int = 0
    canonical_exact_call_count: int = 0
    accepted_search_move_count: int = 0
    u3_safe_exclusion_count: int = 0
    u3_exact_required_count: int = 0
    exact_call_reasons: dict[str, int] = field(
        default_factory=lambda: dict[str, int]()
    )
    disposition_counts: dict[str, int] = field(
        default_factory=lambda: dict[str, int]()
    )
    champion_updates: list[dict[str, object]] = field(
        default_factory=lambda: list[dict[str, object]]()
    )
    round_rng_states: list[dict[str, object]] = field(
        default_factory=lambda: list[dict[str, object]]()
    )
    trace_records: list[dict[str, object]] = field(
        default_factory=lambda: list[dict[str, object]]()
    )
    initial_rng_state: object | None = None
    final_rng_state: object | None = None
    error: str | None = None
    implementation_hashes: dict[str, dict[str, str]] = field(
        default_factory=lambda: dict[str, dict[str, str]]()
    )
    reused_source_hashes: dict[str, dict[str, str]] = field(
        default_factory=lambda: dict[str, dict[str, str]]()
    )
    artifact_hashes: dict[str, str] = field(
        default_factory=lambda: dict[str, str]()
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_safe(value: object) -> object:
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, (tuple, list)):
        sequence = cast(Sequence[object], value)
        return [_json_safe(item) for item in sequence]
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return {str(key): _json_safe(item) for key, item in mapping.items()}
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _random_state_json(rng: random.Random) -> object:
    return _json_safe(rng.getstate())


def _binomial_total(population_size: int, choose: int) -> int:
    if choose < 0 or choose > population_size:
        return 0
    return math.comb(population_size, choose)


@cache
def _binomial_values(max_n: int, choose: int) -> IntArray:
    return np.fromiter(
        (math.comb(value, choose) if choose <= value else 0 for value in range(max_n + 1)),
        dtype=np.int64,
        count=max_n + 1,
    )


def _unrank_combinations(
    population_size: int, choose: int, start: int, stop: int
) -> npt.NDArray[np.int16]:
    """Return colex-ranked combinations as sorted zero-based rows."""

    total = _binomial_total(population_size, choose)
    if not 0 <= start <= stop <= total:
        raise ValueError("combination rank interval is outside its universe")
    size = stop - start
    result = np.empty((size, choose), dtype=np.int16)
    if choose == 0:
        return result
    remainder = np.arange(start, stop, dtype=np.int64)
    for order in range(choose, 0, -1):
        values = _binomial_values(population_size - 1, order)
        selected = np.searchsorted(values, remainder, side="right") - 1
        if np.any(selected < 0):
            raise AssertionError("combinatorial unranking selected a negative element")
        result[:, order - 1] = selected.astype(np.int16)
        remainder -= values[selected]
    if np.any(remainder != 0):
        raise AssertionError("combinatorial unranking left a nonzero remainder")
    return result


def _rows_to_masks(rows: npt.NDArray[np.int16]) -> MaskArray:
    masks = np.zeros(rows.shape[0], dtype=np.uint64)
    for column in range(rows.shape[1]):
        masks |= np.left_shift(np.uint64(1), rows[:, column].astype(np.uint64))
    return masks


def _combinadic_ranks(
    sorted_rows: npt.NDArray[np.int16], pool_size: int
) -> IntArray:
    ranks = np.zeros(sorted_rows.shape[0], dtype=np.int64)
    for column in range(sorted_rows.shape[1]):
        values = _binomial_values(pool_size - 1, column + 1)
        ranks += values[sorted_rows[:, column]]
    return ranks


def _check_deadline(deadline: float | None, *, now: float | None = None) -> None:
    if deadline is not None and (time.monotonic() if now is None else now) >= deadline:
        raise ExperimentTimeout("the frozen 3600-second RUN1 limit expired")


def _winning_w_count(
    ticket_size: int, pool_size: int, w_size: int, minimum_hits: int
) -> int:
    complement_size = pool_size - ticket_size
    return sum(
        math.comb(ticket_size, hits) * math.comb(complement_size, w_size - hits)
        for hits in range(minimum_hits, min(ticket_size, w_size) + 1)
        if 0 <= w_size - hits <= complement_size
    )


def _iter_winning_w_chunks(
    ticket: tuple[int, ...],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    w_size: int = OUTCOME_SIZE,
    minimum_hits: int = MINIMUM_TICKET_HITS,
    chunk_size: int = HISTOGRAM_CHUNK_SIZE,
    deadline: float | None = None,
) -> Iterator[tuple[MaskArray, IntArray]]:
    """Yield each winning W once as its bit mask and colex rank."""

    if chunk_size <= 0 or chunk_size > HISTOGRAM_CHUNK_SIZE:
        raise ValueError("histogram chunk size must be within 1..65536")
    if len(set(ticket)) != len(ticket) or any(
        type(number) is not int or not 1 <= number <= pool_size for number in ticket
    ):
        raise ValueError("ticket is not a legal subset of the declared pool")
    ordered_ticket = tuple(sorted(ticket))
    ticket_set = set(ordered_ticket)
    complement = tuple(number for number in range(1, pool_size + 1) if number not in ticket_set)
    ticket_size = len(ordered_ticket)

    for hits in range(minimum_hits, min(ticket_size, w_size) + 1):
        complement_size = w_size - hits
        if not 0 <= complement_size <= len(complement):
            continue
        complement_total = math.comb(len(complement), complement_size)
        for ticket_part in itertools.combinations(ordered_ticket, hits):
            ticket_row = np.asarray(ticket_part, dtype=np.int16)
            for start in range(0, complement_total, chunk_size):
                _check_deadline(deadline)
                stop = min(start + chunk_size, complement_total)
                complement_indices = _unrank_combinations(
                    len(complement), complement_size, start, stop
                )
                complement_rows = np.asarray(complement, dtype=np.int16)[
                    complement_indices
                ]
                ticket_rows = np.broadcast_to(
                    ticket_row, (stop - start, len(ticket_row))
                )
                rows = np.sort(
                    np.concatenate((ticket_rows, complement_rows), axis=1), axis=1
                )
                zero_based_rows = rows - np.int16(1)
                masks = _rows_to_masks(zero_based_rows)
                ranks = _combinadic_ranks(zero_based_rows, pool_size)
                yield masks, ranks


def _coverage_counts_by_colex_rank(
    portfolio: tuple[tuple[int, ...], ...],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    w_size: int = OUTCOME_SIZE,
    minimum_hits: int = MINIMUM_TICKET_HITS,
    chunk_size: int = HISTOGRAM_CHUNK_SIZE,
    deadline: float | None = None,
) -> CountArray:
    """Compute c_P(W) for every W, in bounded chunks and colex-rank order."""

    if chunk_size <= 0 or chunk_size > HISTOGRAM_CHUNK_SIZE:
        raise ValueError("coverage chunk size must be within 1..65536")
    total = math.comb(pool_size, w_size)
    coverage = np.empty(total, dtype=np.uint8)
    masks = tuple(ticket_mask(ticket) for ticket in portfolio)
    for start in range(0, total, chunk_size):
        _check_deadline(deadline)
        stop = min(start + chunk_size, total)
        rows = _unrank_combinations(pool_size, w_size, start, stop)
        w_masks = _rows_to_masks(rows)
        counts = np.zeros(stop - start, dtype=np.uint8)
        for mask in masks:
            covered = np.bitwise_count(w_masks & np.uint64(mask)) >= minimum_hits
            counts += covered.astype(np.uint8)
        coverage[start:stop] = counts
    return coverage


def _marginal_histogram(
    coverage_by_rank: CountArray,
    *,
    removed_ticket: tuple[int, ...],
    measured_ticket: tuple[int, ...],
    portfolio_size: int,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    w_size: int = OUTCOME_SIZE,
    minimum_hits: int = MINIMUM_TICKET_HITS,
    chunk_size: int = HISTOGRAM_CHUNK_SIZE,
    deadline: float | None = None,
) -> IntArray:
    """Compute H_(X without t,v)(r), enumerating each winning W once."""

    if coverage_by_rank.size != math.comb(pool_size, w_size):
        raise ValueError("coverage array does not match the seven-set universe")
    histogram = np.zeros(portfolio_size, dtype=np.int64)
    removed_mask = np.uint64(ticket_mask(removed_ticket))
    observed = 0
    for w_masks, ranks in _iter_winning_w_chunks(
        measured_ticket,
        pool_size=pool_size,
        w_size=w_size,
        minimum_hits=minimum_hits,
        chunk_size=chunk_size,
        deadline=deadline,
    ):
        if np.any(ranks < 0) or np.any(ranks >= coverage_by_rank.size):
            raise AssertionError("winning-set rank is outside its universe")
        residual = coverage_by_rank[ranks].astype(np.int16)
        removed_wins = np.bitwise_count(w_masks & removed_mask) >= minimum_hits
        residual -= removed_wins.astype(np.int16)
        if np.any(residual < 0) or np.any(residual >= portfolio_size):
            raise AssertionError("residual coverage multiplicity is outside 0..K-1")
        histogram += np.bincount(
            residual.astype(np.int64), minlength=portfolio_size
        )
        observed += w_masks.size
    expected = _winning_w_count(
        len(measured_ticket), pool_size, w_size, minimum_hits
    )
    if observed != expected:
        raise AssertionError(
            f"marginal enumerated {observed} winning W sets, expected {expected}"
        )
    return histogram


def _bonferroni_coefficients(max_multiplicity: int) -> tuple[int, ...]:
    values = [1]
    for order in range(1, max_multiplicity + 1):
        values.append(order * values[-1] + 1)
    return tuple(values)


def _potential_difference_pair(
    added_histogram: npt.NDArray[np.integer],
    removed_histogram: npt.NDArray[np.integer],
) -> PotentialPair:
    if added_histogram.shape != removed_histogram.shape:
        raise ValueError("marginal histograms must have equal dimensions")
    factorial = 1
    bonferroni_coefficients = _bonferroni_coefficients(
        added_histogram.size - 1
    )
    coefficient_a = 0
    coefficient_b = 0
    for multiplicity in range(added_histogram.size):
        if multiplicity > 0:
            factorial *= multiplicity
        difference = int(added_histogram[multiplicity]) - int(
            removed_histogram[multiplicity]
        )
        coefficient_a += difference * factorial
        coefficient_b += difference * bonferroni_coefficients[multiplicity]
    return 7 * coefficient_a, 7 * coefficient_b


def _certified_e_bounds(order: int) -> tuple[Fraction, Fraction]:
    if order not in (64, 128):
        raise ValueError("certified e bounds are frozen at n=64 and n=128")
    factorial = math.factorial(order)
    lower_numerator = sum(
        factorial // math.factorial(index) for index in range(order + 1)
    )
    lower = Fraction(lower_numerator, factorial)
    upper = lower + Fraction(1, order * factorial)
    return lower, upper


def _compare_certified_a_e_minus_b(coefficient_a: int, coefficient_b: int) -> int | None:
    """Return the exact sign of A*e-B, or None if n=128 is inconclusive."""

    if type(coefficient_a) is not int or type(coefficient_b) is not int:
        raise TypeError("certified potential coefficients must be arbitrary-precision ints")
    if coefficient_a == 0:
        return (coefficient_b < 0) - (coefficient_b > 0)
    for order in (64, 128):
        lower_e, upper_e = _certified_e_bounds(order)
        if coefficient_a > 0:
            lower_value = coefficient_a * lower_e - coefficient_b
            upper_value = coefficient_a * upper_e - coefficient_b
        else:
            lower_value = coefficient_a * upper_e - coefficient_b
            upper_value = coefficient_a * lower_e - coefficient_b
        if lower_value >= 0:
            return 1
        if upper_value <= 0:
            return -1
    return None


def _compare_potential_pairs(first: PotentialPair, second: PotentialPair) -> int | None:
    return _compare_certified_a_e_minus_b(
        first[0] - second[0], first[1] - second[1]
    )


def _canonical_state(raw: Sequence[Sequence[int]]) -> Portfolio:
    return bonferroni.normalize_portfolio(
        raw, expected_ticket_count=20
    )


def _classify_replacement(
    frozen_state: Portfolio, ticket_index: int, new_ticket: Ticket
) -> tuple[str, Portfolio | None]:
    old_ticket = frozen_state[ticket_index]
    if new_ticket == old_ticket:
        return "NO_OP", None
    if new_ticket in frozen_state:
        return "DUPLICATE_TICKET", None
    candidate = list(frozen_state)
    candidate[ticket_index] = new_ticket
    return "UNIQUE_CANDIDATE_PENDING", _canonical_state(candidate)


def _generate_raw_proposal(
    rng: random.Random, frozen_state: Portfolio, slot: int
) -> RawProposal:
    if not 0 <= slot < RAW_PROPOSALS_PER_ROUND:
        raise ValueError("raw proposal slot must be within the frozen 32-slot batch")
    rng_before = _random_state_json(rng)
    ticket_index = rng.randrange(20)
    old_ticket = frozen_state[ticket_index]
    old_set = set(old_ticket)
    if slot < 16:
        removed = tuple(rng.sample(list(old_ticket), 1))
        complement = [number for number in range(1, 50) if number not in old_set]
        added = tuple(rng.sample(complement, 1))
        sample_order = removed + added
    elif slot < 24:
        removed = tuple(rng.sample(list(old_ticket), 2))
        complement = [number for number in range(1, 50) if number not in old_set]
        added = tuple(rng.sample(complement, 2))
        sample_order = removed + added
    else:
        new_sample = tuple(rng.sample(list(range(1, 50)), 6))
        removed = old_ticket
        added = new_sample
        sample_order = new_sample
    new_ticket = tuple(sorted((old_set - set(removed)) | set(added)))
    return RawProposal(
        slot=slot,
        ticket_index=ticket_index,
        old_ticket=old_ticket,
        new_ticket=new_ticket,
        removed_sample=removed,
        added_sample=added,
        sample_order=sample_order,
        rng_state_before=rng_before,
        rng_state_after=_random_state_json(rng),
    )


def _generate_raw_batch(
    rng: random.Random,
    frozen_state: Portfolio,
    *,
    on_generated: Callable[[RawProposal], None] | None = None,
) -> tuple[RawProposal, ...]:
    proposals: list[RawProposal] = []
    for slot in range(RAW_PROPOSALS_PER_ROUND):
        proposal = _generate_raw_proposal(rng, frozen_state, slot)
        proposals.append(proposal)
        if on_generated is not None:
            on_generated(proposal)
    return tuple(proposals)


def _claim_candidate_identity(
    candidate: Portfolio, slot: int, seen: dict[Portfolio, int]
) -> tuple[str, int | None]:
    earliest_slot = seen.get(candidate)
    if earliest_slot is not None:
        return "REPEATED_CANDIDATE", earliest_slot
    seen[candidate] = slot
    return "FIRST_CANDIDATE", None


def _raw_proposal_record(
    raw: RawProposal, round_number: int, frozen_x_sha256: str
) -> dict[str, object]:
    return {
        "round": round_number,
        "raw_slot": raw.slot,
        "rng_state_before": raw.rng_state_before,
        "rng_state_after": raw.rng_state_after,
        "ticket_index": raw.ticket_index,
        "old_ticket": raw.old_ticket,
        "removed_sample": raw.removed_sample,
        "added_sample": raw.added_sample,
        "sample_order": raw.sample_order,
        "proposed_ticket_normalized": raw.new_ticket,
        "frozen_x_sha256": frozen_x_sha256,
    }


def _candidate_exact_score_required(
    u3_outcome_count: int,
    champion_outcome_count: int,
    *,
    selected_search_move: bool = False,
    already_scored: bool = False,
) -> bool:
    if already_scored:
        return False
    return selected_search_move or not bonferroni.should_safe_prune(
        u3_outcome_count, champion_outcome_count
    )


def _evaluate_candidate_components(
    *,
    u3_outcome_count: int,
    champion_outcome_count: int,
    exact_score: Callable[[], int],
    potential_pair: Callable[[], PotentialPair],
) -> tuple[int | None, PotentialPair, str]:
    """Screen exact champion scoring, then always evaluate the search potential."""

    safe_exclusion = bonferroni.should_safe_prune(
        u3_outcome_count, champion_outcome_count
    )
    exact_count = None if safe_exclusion else exact_score()
    pair = potential_pair()
    disposition = "SAFE_EXCLUDED" if safe_exclusion else "CANONICAL_EXACT_REQUIRED"
    return exact_count, pair, disposition


def _strict_champion_update(
    champion: Portfolio,
    champion_count: int,
    candidate: Portfolio,
    candidate_count: int | None,
) -> tuple[Portfolio, int, bool]:
    if candidate_count is not None and candidate_count > champion_count:
        return candidate, candidate_count, True
    return champion, champion_count, False


def _select_best_positive_candidate(
    evaluations: list[CandidateEvaluation],
) -> CandidateEvaluation | None:
    best: CandidateEvaluation | None = None
    for candidate in evaluations:
        if candidate.potential_sign <= 0:
            continue
        if best is None:
            best = candidate
            continue
        relation = _compare_potential_pairs(
            (candidate.potential_a, candidate.potential_b),
            (best.potential_a, best.potential_b),
        )
        if relation is None:
            raise IncompleteRun("n=128 could not certify potential-difference ordering")
        if relation > 0 or (
            relation == 0 and candidate.portfolio < best.portfolio
        ):
            best = candidate
    return best


def _final_decision(
    run_status: str, initial_count: int | None, final_champion_count: int | None
) -> str:
    if run_status != "COMPLETE" or initial_count is None or final_champion_count is None:
        return "BOUNDED_INCOMPLETE"
    if final_champion_count > initial_count:
        return "STRICT_IMPROVEMENT_FOUND"
    return "DIRECT_OBJECTIVE_BOUNDED_NEGATIVE"


def _accounting_is_within_budget(
    *,
    raw_proposals: int,
    distinct_proposals: int,
    accepted_moves: int,
    marginal_evaluations: int,
    exact_calls: int,
) -> bool:
    return (
        0 <= raw_proposals <= TOTAL_RAW_PROPOSALS
        and 0 <= distinct_proposals <= MAX_DISTINCT_PROPOSAL_EVALUATIONS
        and 0 <= accepted_moves <= MAX_ACCEPTED_SEARCH_MOVES
        and 0 <= marginal_evaluations <= MAX_MARGINAL_HISTOGRAM_EVALUATIONS
        and 0 <= exact_calls <= MAX_CANONICAL_EXACT_CALLS
    )


def _check_python_runtime() -> None:
    if sys.implementation.name != "cpython" or sys.version_info[:3] != REQUIRED_PYTHON:
        raise IncompleteRun(
            "REQUIRED_FILMUS_WARD_RUNTIME_UNAVAILABLE: expected CPython 3.13.8"
        )


def _git_output(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _verify_sealed_tree(repository: Path) -> tuple[str, str]:
    head = _git_output(repository, "rev-parse", "HEAD")
    tree = _git_output(repository, "rev-parse", "HEAD^{tree}")
    branch = _git_output(repository, "branch", "--show-current")
    subject = _git_output(repository, "show", "-s", "--format=%s", "HEAD")
    parent = _git_output(repository, "rev-parse", "HEAD^")
    parent_tree = _git_output(repository, "rev-parse", f"{parent}^{{tree}}")
    if branch != BRANCH or subject != SEAL_COMMIT_SUBJECT:
        raise IncompleteRun("implementation seal branch or commit subject mismatch")
    if parent != BASE_HEAD or parent_tree != BASE_TREE:
        raise IncompleteRun("implementation seal is not based on the exact pinned base")
    changed = _git_output(
        repository, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"
    ).splitlines()
    expected = sorted((IMPLEMENTATION_PATH, TEST_PATH, PREREGISTRATION_PATH))
    if sorted(changed) != expected:
        raise IncompleteRun("implementation seal changed paths do not match the packet")
    dirty = _git_output(
        repository, "status", "--porcelain=v2", "--untracked-files=all"
    )
    if dirty:
        raise IncompleteRun("worktree is not clean at scientific-run startup")
    return head, tree


def _sealed_file_identity(
    repository: Path, commit: str, relative_path: str
) -> dict[str, str]:
    file_path = repository / relative_path
    raw = file_path.read_bytes()
    git_blob = _git_output(repository, "rev-parse", f"{commit}:{relative_path}")
    worktree_blob = _git_output(repository, "hash-object", relative_path)
    if git_blob != worktree_blob:
        raise IncompleteRun(f"sealed file changed after implementation commit: {relative_path}")
    return {
        "path": relative_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "git_blob": git_blob,
    }


def _load_sealed_identities(
    repository: Path, commit: str
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    implementation = {
        path: _sealed_file_identity(repository, commit, path)
        for path in (IMPLEMENTATION_PATH, TEST_PATH, PREREGISTRATION_PATH)
    }
    reused = {
        path: _sealed_file_identity(repository, commit, path)
        for path in (
            "src/lottolab/research/b649_official_any_prize_exact.py",
            "src/lottolab/research/"
            "b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1.py",
            "src/lottolab/research/"
            "b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_runner.py",
        )
    }
    return implementation, reused


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fraction_text(count: int) -> str:
    return str(Fraction(count, TOTAL_OFFICIAL_OUTCOMES))


def _claim_canonical_exact_call(summary: RunSummary, reason: str) -> None:
    if summary.canonical_exact_call_count >= MAX_CANONICAL_EXACT_CALLS:
        raise IncompleteRun("canonical exact-call budget would be exceeded")
    summary.canonical_exact_call_count += 1
    summary.exact_call_reasons[reason] = summary.exact_call_reasons.get(reason, 0) + 1


def _claim_marginal_histogram_evaluation(summary: RunSummary) -> None:
    if summary.marginal_histogram_evaluation_count >= MAX_MARGINAL_HISTOGRAM_EVALUATIONS:
        raise IncompleteRun("marginal-histogram budget would be exceeded")
    summary.marginal_histogram_evaluation_count += 1


def _exact_score(
    portfolio: Portfolio, draws: DrawMasks, summary: RunSummary, reason: str
) -> tuple[int, str]:
    _claim_canonical_exact_call(summary, reason)
    result = evaluate_portfolio(portfolio, draws=draws)
    return result.official_any_prize_outcome_count, str(result.official_any_prize)


def _record_disposition(summary: RunSummary, name: str) -> None:
    summary.disposition_counts[name] = summary.disposition_counts.get(name, 0) + 1


def _portfolio_payload(
    portfolio: Portfolio | None, digest: str | None, outcome_count: int | None
) -> dict[str, object]:
    return {
        "portfolio": portfolio,
        "portfolio_sha256": digest,
        "outcome_count": outcome_count,
        "exact_fraction": (
            _fraction_text(outcome_count) if outcome_count is not None else None
        ),
    }


def _run_search(repository: Path, deadline: float, summary: RunSummary) -> None:
    _check_deadline(deadline)
    _claim_canonical_exact_call(summary, "INITIAL_CHAMPION_VERIFICATION")
    validated = load_and_verify_pinned_incumbent(
        repository,
        source_commit=BASE_HEAD,
        source_path=INCUMBENT_PATH,
        artifact_sha256=INCUMBENT_SHA256,
    )
    incumbent = validated.incumbent
    initial = _canonical_state(incumbent.portfolio)
    if (
        validated.artifact_blob != INCUMBENT_BLOB
        or validated.artifact_sha256 != INCUMBENT_SHA256
        or incumbent.portfolio_sha256 != INCUMBENT_PORTFOLIO_SHA256
        or validated.exact.official_any_prize_outcome_count != INCUMBENT_OUTCOME_COUNT
        or str(validated.exact.official_any_prize) != INCUMBENT_FRACTION
        or validated.exact.main_draw_count * validated.exact.special_count
        != TOTAL_OFFICIAL_OUTCOMES
    ):
        raise IncompleteRun("pinned incumbent identity or exact score mismatch")

    for _fixture_hash in validated.bound_fixture_hashes:
        _claim_canonical_exact_call(summary, "PINNED_LOADER_BOUND_FIXTURE")
    summary.initial_portfolio = initial
    summary.initial_portfolio_sha256 = bonferroni.portfolio_sha256(initial)
    summary.initial_outcome_count = validated.exact.official_any_prize_outcome_count
    summary.initial_fraction = str(validated.exact.official_any_prize)
    current_x = initial
    current_x_count = validated.exact.official_any_prize_outcome_count
    current_champion = initial
    current_champion_count = validated.exact.official_any_prize_outcome_count
    summary.final_x = initial
    summary.final_x_sha256 = summary.initial_portfolio_sha256
    summary.final_x_outcome_count = current_x_count
    summary.final_x_fraction = summary.initial_fraction
    summary.final_champion = initial
    summary.final_champion_sha256 = summary.initial_portfolio_sha256
    summary.final_champion_outcome_count = current_champion_count
    summary.final_champion_fraction = summary.initial_fraction
    rng = random.Random(SEED)
    summary.initial_rng_state = _random_state_json(rng)
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    if draws.size * (BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE) != (
        TOTAL_OFFICIAL_OUTCOMES
    ):
        raise IncompleteRun("canonical main-draw and special count is inconsistent")

    normal_termination = False
    for round_index in range(ROUNDS):
        _check_deadline(deadline)
        round_number = round_index + 1
        frozen_x = current_x
        round_start_state = _random_state_json(rng)
        round_trace: list[dict[str, object]] = []
        removal_cache: dict[Ticket, IntArray] = {}
        seen_candidates: dict[Portfolio, int] = {}
        evaluations: list[CandidateEvaluation] = []
        raw_batch: list[RawProposal] = []
        batch_accounted = False
        try:
            coverage_by_rank = _coverage_counts_by_colex_rank(
                frozen_x, deadline=deadline
            )

            def note_generated(
                proposal: RawProposal,
                _raw_batch: list[RawProposal] = raw_batch,
                _summary: RunSummary = summary,
            ) -> None:
                _raw_batch.append(proposal)
                _summary.raw_proposal_count += 1

            frozen_x_sha256 = bonferroni.portfolio_sha256(frozen_x)
            _generate_raw_batch(rng, frozen_x, on_generated=note_generated)

            for raw in raw_batch:
                _check_deadline(deadline)
                slot = raw.slot
                record = _raw_proposal_record(raw, round_number, frozen_x_sha256)
                round_trace.append(record)
                disposition, candidate = _classify_replacement(
                    frozen_x, raw.ticket_index, raw.new_ticket
                )
                if disposition == "NO_OP":
                    summary.no_op_count += 1
                    record["disposition"] = disposition
                    _record_disposition(summary, disposition)
                    continue
                if disposition == "DUPLICATE_TICKET":
                    summary.duplicate_ticket_count += 1
                    record["disposition"] = disposition
                    _record_disposition(summary, disposition)
                    continue
                if candidate is None:
                    raise IncompleteRun("legal proposal did not normalize to a candidate")
                candidate_digest = bonferroni.portfolio_sha256(candidate)
                record["candidate_portfolio_sha256"] = candidate_digest
                identity_status, earliest_slot = _claim_candidate_identity(
                    candidate, slot, seen_candidates
                )
                if identity_status == "REPEATED_CANDIDATE":
                    summary.repeated_candidate_count += 1
                    record["disposition"] = "REPEATED_CANDIDATE"
                    record["earliest_raw_slot"] = earliest_slot
                    _record_disposition(summary, "REPEATED_CANDIDATE")
                    continue
                summary.distinct_legal_proposal_count += 1
                if (
                    summary.distinct_legal_proposal_count
                    > MAX_DISTINCT_PROPOSAL_EVALUATIONS
                ):
                    raise IncompleteRun("distinct-proposal budget was exceeded")

                components = bonferroni.full_u3_components(candidate)
                u3_count = components.u3
                record["u3_outcome_count"] = u3_count

                removed_ticket = raw.old_ticket
                u3_safe_exclusion = bonferroni.should_safe_prune(
                    u3_count, current_champion_count
                )
                u3_disposition = (
                    "SAFE_EXCLUDED"
                    if u3_safe_exclusion
                    else "CANONICAL_EXACT_REQUIRED"
                )
                record["u3_disposition"] = u3_disposition
                if u3_safe_exclusion:
                    summary.u3_safe_exclusion_count += 1
                else:
                    summary.u3_exact_required_count += 1

                removed_histogram: IntArray | None = None
                added_histogram: IntArray | None = None

                def score_for_champion(
                    _candidate: Portfolio = candidate,
                    _record: dict[str, object] = record,
                    _candidate_digest: str = candidate_digest,
                    _round_number: int = round_number,
                    _slot: int = slot,
                ) -> int:
                    nonlocal current_champion, current_champion_count
                    exact_count, exact_fraction = _exact_score(
                        _candidate,
                        draws,
                        summary,
                        "U3_STRICTLY_EXCEEDS_CHAMPION",
                    )
                    current_champion, current_champion_count, updated = (
                        _strict_champion_update(
                            current_champion,
                            current_champion_count,
                            _candidate,
                            exact_count,
                        )
                    )
                    summary.final_champion = current_champion
                    summary.final_champion_sha256 = bonferroni.portfolio_sha256(
                        current_champion
                    )
                    summary.final_champion_outcome_count = current_champion_count
                    summary.final_champion_fraction = _fraction_text(
                        current_champion_count
                    )
                    _record["canonical_exact_outcome_count"] = exact_count
                    _record["canonical_exact_fraction"] = exact_fraction
                    _record["canonical_exact_trigger"] = (
                        "U3_STRICTLY_EXCEEDS_CHAMPION"
                    )
                    _record["champion_updated"] = updated
                    if updated:
                        summary.champion_updates.append(
                            {
                                "round": _round_number,
                                "raw_slot": _slot,
                                "portfolio_sha256": _candidate_digest,
                                "outcome_count": exact_count,
                                "fraction": exact_fraction,
                            }
                        )
                    return exact_count

                def evaluate_potential(
                    _removed_ticket: Ticket = removed_ticket,
                    _removal_cache: dict[Ticket, IntArray] = removal_cache,
                    _record: dict[str, object] = record,
                    _coverage_by_rank: CountArray = coverage_by_rank,
                    _frozen_x: Portfolio = frozen_x,
                    _raw: RawProposal = raw,
                    _deadline: float = deadline,
                ) -> PotentialPair:
                    nonlocal removed_histogram, added_histogram
                    summary.marginal_histogram_request_count += 1
                    if _removed_ticket in _removal_cache:
                        removed_histogram = _removal_cache[_removed_ticket]
                        _record["removed_histogram_cached"] = True
                    else:
                        _claim_marginal_histogram_evaluation(summary)
                        removed_histogram = _marginal_histogram(
                            _coverage_by_rank,
                            removed_ticket=_removed_ticket,
                            measured_ticket=_removed_ticket,
                            portfolio_size=len(_frozen_x),
                            deadline=_deadline,
                        )
                        _removal_cache[_removed_ticket] = removed_histogram
                        _record["removed_histogram_cached"] = False
                    summary.marginal_histogram_request_count += 1
                    _claim_marginal_histogram_evaluation(summary)
                    added_histogram = _marginal_histogram(
                        _coverage_by_rank,
                        removed_ticket=_removed_ticket,
                        measured_ticket=_raw.new_ticket,
                        portfolio_size=len(_frozen_x),
                        deadline=_deadline,
                    )
                    _record["removed_histogram"] = removed_histogram.tolist()
                    _record["added_histogram"] = added_histogram.tolist()
                    return _potential_difference_pair(
                        added_histogram, removed_histogram
                    )

                exact_count, coefficient_pair, observed_disposition = (
                    _evaluate_candidate_components(
                        u3_outcome_count=u3_count,
                        champion_outcome_count=current_champion_count,
                        exact_score=score_for_champion,
                        potential_pair=evaluate_potential,
                    )
                )
                if observed_disposition != u3_disposition:
                    raise AssertionError("U3 exact-score screen changed during evaluation")
                if removed_histogram is None or added_histogram is None:
                    raise AssertionError("potential callback omitted a marginal histogram")
                if exact_count is not None:
                    exact_fraction = cast(
                        str, record["canonical_exact_fraction"]
                    )
                else:
                    exact_fraction = None
                    record["canonical_exact_outcome_count"] = None
                    record["canonical_exact_fraction"] = None
                    record["canonical_exact_trigger"] = None
                    record["champion_updated"] = False

                if exact_count is not None and (
                    exact_count - current_x_count
                    != 7
                    * (
                        int(added_histogram[0]) - int(removed_histogram[0])
                    )
                ):
                    raise IncompleteRun(
                        "canonical score delta disagrees with the coverage marginal identity"
                    )
                sign = _compare_certified_a_e_minus_b(*coefficient_pair)
                record["potential_difference_A"] = str(coefficient_pair[0])
                record["potential_difference_B"] = str(coefficient_pair[1])
                record["potential_sign"] = sign
                record["search_potential_is_surrogate"] = True
                if sign is None:
                    record["disposition"] = "POTENTIAL_SIGN_UNRESOLVED_N128"
                    raise IncompleteRun(
                        "potential sign remained unresolved after certified n=128 bounds"
                    )

                evaluation = CandidateEvaluation(
                    portfolio=candidate,
                    portfolio_sha256=candidate_digest,
                    potential_a=coefficient_pair[0],
                    potential_b=coefficient_pair[1],
                    potential_sign=sign,
                    u3_outcome_count=u3_count,
                    exact_outcome_count=exact_count,
                    exact_fraction=exact_fraction,
                    raw_record=record,
                )
                evaluations.append(evaluation)
                record["disposition"] = "UNIQUE_LEGAL_EVALUATED"
                _record_disposition(summary, "UNIQUE_LEGAL_EVALUATED")


            selected = _select_best_positive_candidate(evaluations)
            if selected is not None:
                selected.raw_record["selected_search_move"] = True
                if _candidate_exact_score_required(
                    selected.u3_outcome_count,
                    current_champion_count,
                    selected_search_move=True,
                    already_scored=selected.exact_outcome_count is not None,
                ):
                    selected_count, selected_fraction = _exact_score(
                        selected.portfolio,
                        draws,
                        summary,
                        "SELECTED_SEARCH_MOVE",
                    )
                    selected.exact_outcome_count = selected_count
                    selected.exact_fraction = selected_fraction
                    selected.raw_record["canonical_exact_outcome_count"] = selected_count
                    selected.raw_record["canonical_exact_fraction"] = selected_fraction
                    selected.raw_record["canonical_exact_trigger"] = (
                        "SELECTED_SEARCH_MOVE"
                    )
                    current_champion, current_champion_count, updated = (
                        _strict_champion_update(
                            current_champion,
                            current_champion_count,
                            selected.portfolio,
                            selected_count,
                        )
                    )
                    summary.final_champion = current_champion
                    summary.final_champion_sha256 = bonferroni.portfolio_sha256(
                        current_champion
                    )
                    summary.final_champion_outcome_count = current_champion_count
                    summary.final_champion_fraction = _fraction_text(
                        current_champion_count
                    )
                    selected.raw_record["champion_updated"] = updated
                    if updated:
                        update = {
                            "round": round_number,
                            "raw_slot": selected.raw_record["raw_slot"],
                            "portfolio_sha256": selected.portfolio_sha256,
                            "outcome_count": selected_count,
                            "fraction": selected_fraction,
                        }
                        summary.champion_updates.append(update)
                selected_count = selected.exact_outcome_count
                if selected_count is None:
                    raise IncompleteRun("selected search move lacks canonical exact score")
                selected_slot = cast(int, selected.raw_record["raw_slot"])
                removed_hist = cast(
                    list[int], selected.raw_record["removed_histogram"]
                )
                added_hist = cast(list[int], selected.raw_record["added_histogram"])
                if selected_count - current_x_count != 7 * (
                    added_hist[0] - removed_hist[0]
                ):
                    raise IncompleteRun(
                        "selected move failed canonical score-delta consistency"
                    )
                current_x = selected.portfolio
                current_x_count = selected_count
                summary.final_x = current_x
                summary.final_x_sha256 = bonferroni.portfolio_sha256(current_x)
                summary.final_x_outcome_count = current_x_count
                summary.final_x_fraction = _fraction_text(current_x_count)
                summary.relative_potential_a += selected.potential_a
                summary.relative_potential_b += selected.potential_b
                summary.accepted_search_move_count += 1
                if summary.accepted_search_move_count > MAX_ACCEPTED_SEARCH_MOVES:
                    raise IncompleteRun("accepted-search-move budget was exceeded")
                summary.final_rng_state = _random_state_json(rng)
                _record_disposition(summary, "ACCEPTED_SEARCH_MOVE")
                _record_disposition(summary, f"SELECTED_RAW_SLOT_{selected_slot}")
                summary.termination_reason = "STRICT_POTENTIAL_ASCENT"
            else:
                summary.termination_reason = "NO_STRICT_POTENTIAL_IMPROVEMENT"

            summary.rounds_completed += 1
            summary.round_rng_states.append(
                {
                    "round": round_number,
                    "state_before": round_start_state,
                    "state_after": _random_state_json(rng),
                    "raw_proposals_generated": len(round_trace),
                    "batch_complete": True,
                }
            )
            summary.trace_records.extend(round_trace)
            batch_accounted = True
            if selected is None:
                normal_termination = True
                break
            if round_number == ROUNDS:
                summary.termination_reason = "ROUND_8_COMPLETED"
                normal_termination = True
                break
        except Exception:
            accounted_slots = {
                cast(int, record["raw_slot"])
                for record in round_trace
                if "raw_slot" in record
            }
            for raw in raw_batch:
                if raw.slot not in accounted_slots:
                    unprocessed = _raw_proposal_record(
                        raw, round_number, bonferroni.portfolio_sha256(frozen_x)
                    )
                    unprocessed["disposition"] = "RAW_SLOT_GENERATED_NOT_EVALUATED"
                    round_trace.append(unprocessed)
            round_trace.sort(key=lambda record: cast(int, record["raw_slot"]))
            summary.trace_records.extend(round_trace)
            if not batch_accounted:
                summary.round_rng_states.append(
                    {
                        "round": round_number,
                        "state_before": round_start_state,
                        "state_after": _random_state_json(rng),
                        "raw_proposals_generated": len(raw_batch),
                        "batch_complete": False,
                    }
                )
            raise

    if not normal_termination:
        raise IncompleteRun("search exited without a frozen normal terminal condition")

    terminal_x_count, terminal_x_fraction = _exact_score(
        current_x, draws, summary, "TERMINAL_SEARCH_STATE"
    )
    if terminal_x_count != current_x_count or terminal_x_fraction != _fraction_text(
        current_x_count
    ):
        raise IncompleteRun("terminal search-state exact recomputation was inconsistent")
    terminal_champion_count, terminal_champion_fraction = _exact_score(
        current_champion, draws, summary, "FINAL_ARCHIVED_CHAMPION"
    )
    if (
        terminal_champion_count != current_champion_count
        or terminal_champion_fraction != _fraction_text(current_champion_count)
    ):
        raise IncompleteRun("final champion exact recomputation was inconsistent")
    if terminal_champion_count < INCUMBENT_OUTCOME_COUNT:
        raise IncompleteRun("final champion is below the verified initial champion")

    summary.run_status = "COMPLETE"
    summary.termination_reason = summary.termination_reason or "NORMAL_TERMINATION"
    summary.final_x = current_x
    summary.final_x_sha256 = bonferroni.portfolio_sha256(current_x)
    summary.final_x_outcome_count = terminal_x_count
    summary.final_x_fraction = terminal_x_fraction
    summary.final_champion = current_champion
    summary.final_champion_sha256 = bonferroni.portfolio_sha256(current_champion)
    summary.final_champion_outcome_count = terminal_champion_count
    summary.final_champion_fraction = terminal_champion_fraction
    summary.final_rng_state = _random_state_json(rng)
    if not _accounting_is_within_budget(
        raw_proposals=summary.raw_proposal_count,
        distinct_proposals=summary.distinct_legal_proposal_count,
        accepted_moves=summary.accepted_search_move_count,
        marginal_evaluations=summary.marginal_histogram_evaluation_count,
        exact_calls=summary.canonical_exact_call_count,
    ):
        raise IncompleteRun("terminal run accounting exceeded a frozen budget")
    summary.final_decision = _final_decision(
        summary.run_status,
        summary.initial_outcome_count,
        summary.final_champion_outcome_count,
    )


def _summary_payload(summary: RunSummary) -> dict[str, object]:
    return {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "run_status": summary.run_status,
        "termination_reason": summary.termination_reason,
        "final_decision": summary.final_decision,
        "start_utc": summary.start_utc,
        "end_utc": summary.end_utc,
        "duration_seconds": summary.duration_seconds,
        "implementation_seal_head": summary.implementation_seal_head,
        "implementation_seal_tree": summary.implementation_seal_tree,
        "initial_champion": _portfolio_payload(
            summary.initial_portfolio,
            summary.initial_portfolio_sha256,
            summary.initial_outcome_count,
        ),
        "final_search_state_x": _portfolio_payload(
            summary.final_x,
            summary.final_x_sha256,
            summary.final_x_outcome_count,
        ),
        "final_champion_c": _portfolio_payload(
            summary.final_champion,
            summary.final_champion_sha256,
            summary.final_champion_outcome_count,
        ),
        "search_potential_result": {
            "is_surrogate": True,
            "relative_to_initial_x": {
                "A": str(summary.relative_potential_a),
                "B": str(summary.relative_potential_b),
                "expression": "(A*e-B)/(e-1)",
            },
        },
        "exact_objective_result": {
            "objective": "OFFICIAL_ANY_PRIZE_EXACT",
            "initial_outcome_count": summary.initial_outcome_count,
            "final_search_state_outcome_count": summary.final_x_outcome_count,
            "final_champion_outcome_count": summary.final_champion_outcome_count,
            "integer_improvement": (
                summary.final_champion_outcome_count - summary.initial_outcome_count
                if summary.final_champion_outcome_count is not None
                and summary.initial_outcome_count is not None
                else None
            ),
        },
        "accounting": {
            "rounds_completed": summary.rounds_completed,
            "raw_proposal_count": summary.raw_proposal_count,
            "distinct_legal_proposal_count": summary.distinct_legal_proposal_count,
            "no_op_count": summary.no_op_count,
            "duplicate_ticket_count": summary.duplicate_ticket_count,
            "repeated_candidate_count": summary.repeated_candidate_count,
            "marginal_histogram_evaluation_count": (
                summary.marginal_histogram_evaluation_count
            ),
            "marginal_histogram_request_count": summary.marginal_histogram_request_count,
            "canonical_exact_call_count": summary.canonical_exact_call_count,
            "accepted_search_move_count": summary.accepted_search_move_count,
            "u3_safe_exclusion_count": summary.u3_safe_exclusion_count,
            "u3_exact_required_count": summary.u3_exact_required_count,
            "disposition_counts": summary.disposition_counts,
            "exact_call_reasons": summary.exact_call_reasons,
        },
        "global_k20_optimum_status": "UNKNOWN",
        "neighborhood_completeness": "NOT_PROVEN",
        "global_optimum_claim": "FORBIDDEN",
        "error": summary.error,
    }


def _report_text(summary: RunSummary) -> str:
    initial = summary.initial_outcome_count
    final_x = summary.final_x_outcome_count
    final_c = summary.final_champion_outcome_count
    improvement = (
        final_c - initial
        if initial is not None and final_c is not None
        else None
    )
    return "\n".join(
        (
            "# B649 K20 Filmus-Ward nonoblivious R1",
            "",
            f"- **Run status:** {summary.run_status}",
            f"- **Final decision:** {summary.final_decision}",
            f"- **Termination:** {summary.termination_reason}",
            f"- **Seed / interpreter:** {SEED} / CPython 3.13.8",
            f"- **Rounds completed:** {summary.rounds_completed}",
            "",
            "## Initial champion",
            "",
            f"- Outcome count: {initial}",
            f"- Exact fraction: {summary.initial_fraction}",
            f"- Portfolio SHA-256: {summary.initial_portfolio_sha256}",
            "",
            "## Final search state X",
            "",
            f"- Outcome count: {final_x}",
            f"- Exact fraction: {summary.final_x_fraction}",
            f"- Portfolio SHA-256: {summary.final_x_sha256}",
            "",
            "## Final champion C",
            "",
            f"- Outcome count: {final_c}",
            f"- Exact fraction: {summary.final_champion_fraction}",
            f"- Portfolio SHA-256: {summary.final_champion_sha256}",
            f"- Improvement over initial champion: {improvement}",
            "",
            "## Search potential",
            "",
            "The Filmus-Ward coverage potential was used only to select search moves.",
            "The reported coefficients encode the relative potential from the initial X as",
            "(A*e-B)/(e-1); exact OFFICIAL_ANY_PRIZE scoring alone updates champion C.",
            "",
            f"- A: {summary.relative_potential_a}",
            f"- B: {summary.relative_potential_b}",
            "",
            "## Accounting",
            "",
            f"- Raw proposals: {summary.raw_proposal_count}",
            f"- Distinct legal proposal evaluations: {summary.distinct_legal_proposal_count}",
            f"- No-op / duplicate ticket / repeated candidate: "
            f"{summary.no_op_count} / {summary.duplicate_ticket_count} / "
            f"{summary.repeated_candidate_count}",
            f"- Marginal histogram evaluations: {summary.marginal_histogram_evaluation_count}",
            f"- Canonical exact calls: {summary.canonical_exact_call_count}",
            f"- Accepted search moves: {summary.accepted_search_move_count}",
            "",
            "## Claim boundary",
            "",
            "- GLOBAL_K20_OPTIMUM_STATUS: UNKNOWN",
            "- NEIGHBORHOOD_COMPLETENESS: NOT_PROVEN",
            "- No global optimum or Filmus-Ward approximation guarantee is claimed.",
            "- A negative result, if present, is limited to this seed, proposal policy,",
            "  trajectory, and frozen budget.",
            "",
            f"Project-local provenance: {EVIDENCE_RELATIVE_PATH}/provenance.json",
            f"Trace: {EVIDENCE_RELATIVE_PATH}/trace.jsonl",
            "",
        )
    )


def _write_run_artifacts(
    repository: Path,
    evidence_dir: Path,
    summary: RunSummary,
    command_argv: list[str],
) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    trace_path = evidence_dir / "trace.jsonl"
    checkpoint_path = evidence_dir / "checkpoint.json"
    stdout_path = evidence_dir / "stdout.log"
    stderr_path = evidence_dir / "stderr.log"
    provenance_path = evidence_dir / "provenance.json"
    trace_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for record in summary.trace_records
        ),
        encoding="utf-8",
    )
    checkpoint = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "status": summary.run_status,
        "termination_reason": summary.termination_reason,
        "last_completed_round": summary.rounds_completed,
        "raw_proposal_count": summary.raw_proposal_count,
        "current_x": _portfolio_payload(
            summary.final_x,
            summary.final_x_sha256,
            summary.final_x_outcome_count,
        ),
        "champion_c": _portfolio_payload(
            summary.final_champion,
            summary.final_champion_sha256,
            summary.final_champion_outcome_count,
        ),
        "final_rng_state": summary.final_rng_state,
    }
    _write_json(checkpoint_path, checkpoint)
    stdout_path.write_text(
        "\n".join(
            (
                f"RUN_ID={RUN_ID}",
                f"RUN_STATUS={summary.run_status}",
                f"FINAL_DECISION={summary.final_decision}",
                f"ROUNDS_COMPLETED={summary.rounds_completed}",
                f"RAW_PROPOSALS={summary.raw_proposal_count}",
                "",
            )
        ),
        encoding="utf-8",
    )
    stderr_path.write_text(
        (summary.error + "\n") if summary.error is not None else "",
        encoding="utf-8",
    )

    result_payload = _summary_payload(summary)
    result_file = repository / RESULT_PATH
    report_file = repository / REPORT_PATH
    if result_file.exists() or report_file.exists():
        raise IncompleteRun("authorized result/report path already exists; refusing overwrite")
    result_file.write_text(
        json.dumps(result_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    report_file.write_text(_report_text(summary), encoding="utf-8")
    summary.artifact_hashes = {
        "trace.jsonl": _sha256_file(trace_path),
        "checkpoint.json": _sha256_file(checkpoint_path),
        "stdout.log": _sha256_file(stdout_path),
        "stderr.log": _sha256_file(stderr_path),
        RESULT_PATH: _sha256_file(result_file),
        REPORT_PATH: _sha256_file(report_file),
    }

    provenance = {
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "run_count": 1,
        "execution_id": RUN_ID,
        "run_status": summary.run_status,
        "termination_reason": summary.termination_reason,
        "final_decision": summary.final_decision,
        "start_utc": summary.start_utc,
        "end_utc": summary.end_utc,
        "wall_clock_duration_seconds": summary.duration_seconds,
        "implementation_seal_head": summary.implementation_seal_head,
        "implementation_seal_tree": summary.implementation_seal_tree,
        "implementation_hashes": summary.implementation_hashes,
        "reused_source_hashes": summary.reused_source_hashes,
        "pinned_incumbent": {
            "source_commit": BASE_HEAD,
            "source_tree": BASE_TREE,
            "source_path": INCUMBENT_PATH,
            "artifact_blob": INCUMBENT_BLOB,
            "artifact_sha256": INCUMBENT_SHA256,
            "portfolio_sha256": INCUMBENT_PORTFOLIO_SHA256,
            "outcome_count": INCUMBENT_OUTCOME_COUNT,
            "exact_fraction": INCUMBENT_FRACTION,
            "total_official_outcomes": TOTAL_OFFICIAL_OUTCOMES,
        },
        "runtime": {
            "implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "python_version_full": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "dependencies": {"numpy": np.__version__},
            "command_argv": command_argv,
            "numpy_module_path": np.__file__,
        },
        "rng": {
            "class": "random.Random",
            "seed": SEED,
            "initial_state": summary.initial_rng_state,
            "per_round_states": summary.round_rng_states,
            "final_state": summary.final_rng_state,
        },
        "accounting": _summary_payload(summary)["accounting"],
        "champion_updates": summary.champion_updates,
        "initial_champion": _portfolio_payload(
            summary.initial_portfolio,
            summary.initial_portfolio_sha256,
            summary.initial_outcome_count,
        ),
        "final_search_state_x": _portfolio_payload(
            summary.final_x,
            summary.final_x_sha256,
            summary.final_x_outcome_count,
        ),
        "final_champion_c": _portfolio_payload(
            summary.final_champion,
            summary.final_champion_sha256,
            summary.final_champion_outcome_count,
        ),
        "authorized_artifact_sha256": summary.artifact_hashes,
        "error": summary.error,
    }
    _write_json(provenance_path, provenance)


def run_scientific_run1(repository: Path) -> RunSummary:
    """Execute exactly one frozen run and write only the packet-authorized outputs."""

    repository = repository.resolve(strict=True)
    _check_python_runtime()
    evidence_dir = repository / EVIDENCE_RELATIVE_PATH
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        raise IncompleteRun("RUN1 evidence path is nonempty; restart is forbidden")
    if (repository / RESULT_PATH).exists() or (repository / REPORT_PATH).exists():
        raise IncompleteRun("RUN1 result/report path already exists; refusing a second run")

    summary = RunSummary(start_utc=_utc_now())
    summary.implementation_seal_head, summary.implementation_seal_tree = (
        _verify_sealed_tree(repository)
    )
    summary.implementation_hashes, summary.reused_source_hashes = (
        _load_sealed_identities(repository, summary.implementation_seal_head)
    )
    started = time.monotonic()
    deadline = started + WALL_CLOCK_LIMIT_SECONDS
    old_handler = signal.getsignal(signal.SIGALRM)

    def timeout_handler(_signum: int, _frame: object) -> None:
        raise ExperimentTimeout("the frozen 3600-second RUN1 limit expired")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, WALL_CLOCK_LIMIT_SECONDS)
    try:
        _run_search(repository, deadline, summary)
    except (Exception, KeyboardInterrupt) as exc:
        summary.run_status = "BOUNDED_INCOMPLETE"
        summary.termination_reason = (
            "TIMEOUT" if isinstance(exc, ExperimentTimeout) else "INCOMPLETE_REQUIRED_CHECK"
        )
        summary.final_decision = "BOUNDED_INCOMPLETE"
        summary.error = f"{type(exc).__name__}: {exc}"
        if summary.final_x is None and summary.initial_portfolio is not None:
            summary.final_x = summary.initial_portfolio
            summary.final_x_sha256 = summary.initial_portfolio_sha256
            summary.final_x_outcome_count = summary.initial_outcome_count
            summary.final_x_fraction = summary.initial_fraction
        if summary.final_champion is None and summary.initial_portfolio is not None:
            summary.final_champion = summary.initial_portfolio
            summary.final_champion_sha256 = summary.initial_portfolio_sha256
            summary.final_champion_outcome_count = summary.initial_outcome_count
            summary.final_champion_fraction = summary.initial_fraction
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
    summary.end_utc = _utc_now()
    summary.duration_seconds = round(time.monotonic() - started, 6)
    if summary.run_status != "COMPLETE":
        summary.final_decision = "BOUNDED_INCOMPLETE"
    command_argv = [
        sys.executable,
        "-m",
        "lottolab.research.b649_k20_filmus_ward_nonoblivious_r1",
        "--run1",
    ]
    _write_run_artifacts(repository, evidence_dir, summary, command_argv)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the preregistered B649 K20 Filmus-Ward RUN1."
    )
    parser.add_argument("--run1", action="store_true", required=True)
    arguments = parser.parse_args(argv)
    if not arguments.run1:
        return 2
    try:
        summary = run_scientific_run1(Path.cwd())
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 2
    sys.stdout.write(
        f"RUN_STATUS={summary.run_status}\n"
        f"FINAL_DECISION={summary.final_decision}\n"
        f"PROVENANCE_PATH={EVIDENCE_RELATIVE_PATH}/provenance.json\n"
    )
    return 0 if summary.run_status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
