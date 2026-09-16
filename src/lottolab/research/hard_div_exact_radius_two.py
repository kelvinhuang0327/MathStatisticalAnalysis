# pyright: reportPrivateUsage=false

"""Exact HARD_DIV radius-2 comparison against frozen radius-1 terminals.

Reuses the transplanted two one-number-exchange neighborhood.  Intermediate
portfolios are never scored.  Endpoints that violate pairwise intersection
<= 1 are discarded before exact M3+ scoring.  Frozen radius-1 HARD_DIV values
are read-only.  A complete neighborhood with no strict improvement certifies
radius-2 local optimality inside the hard-feasible set; it does not prove a
global optimum.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Any, Final

from lottolab.research.exact_radius_two_local_escape import (
    PackedWinningSpace,
    _portfolio_with_one_replacement,
    _portfolio_with_two_replacements,
    _single_replacement_tickets,
    one_exchange_candidates_by_slot,
    radius_two_endpoint_feasibility,
)
from lottolab.research.global_exact_coverage_solver import PAIRWISE_MAX_INTERSECTION
from lottolab.research.hard_div_pairwise_bounded_candidate_adapter import (
    BIG_LOTTO,
    DRAW_SIZE,
    GLOBAL_OPTIMUM_STATUS,
    MINIMUM_MATCHES,
    POOL_SIZE,
    SUPPORTED_K,
    WINNING_DRAW_COUNT,
    AdapterStatus,
    HardDivPairwiseAdapterDispatch,
    _canonical_legal_portfolio,
    _portfolio_max_pairwise_intersection,
    _portfolio_sha256,
    big_lotto_dispatch,
)
from lottolab.research.reference_e_exact_one_exchange_refinement import Portfolio

METHOD_ID: Final = "HARD_DIV_PAIRWISE_OVERLAP_R1"
RADIUS_TWO_NEIGHBORHOOD_UNIT: Final = "TWO_LEGAL_ONE_NUMBER_EXCHANGES"
BASELINE_CERTIFICATE: Final = "EXACT_RADIUS_1_LOCAL_OPTIMUM"
RADIUS2_LOCAL_CERTIFICATE: Final = "CERTIFIED_RADIUS2_LOCAL_OPTIMUM"
RADIUS2_IMPROVEMENT_CERTIFICATE: Final = "STRICT_IMPROVEMENT_BEST_HARD_FEASIBLE_RADIUS2_NEIGHBOR"
PROOF_STATUS: Final = (
    "EXACT_RADIUS_2_WITHIN_HARD_FEASIBLE_SET_NO_GLOBAL_PROOF"
)
FROZEN_RADIUS1_RESULT_PATH: Final = Path(
    "docs/research/matrix-native-results/imported-optimizer-integration-r1-result.json"
)
FROZEN_RADIUS1_ROW_ID: Final = {
    2: "NATIVE_BIG_LOTTO|HARD_DIV_PAIRWISE_OVERLAP_R1|default|k2|m3",
    3: "NATIVE_BIG_LOTTO|HARD_DIV_PAIRWISE_OVERLAP_R1|default|k3|m3",
    5: "NATIVE_BIG_LOTTO|HARD_DIV_PAIRWISE_OVERLAP_R1|default|k5|m3",
    10: "NATIVE_BIG_LOTTO|HARD_DIV_PAIRWISE_OVERLAP_R1|default|k10|m3",
    20: "NATIVE_BIG_LOTTO|HARD_DIV_PAIRWISE_OVERLAP_R1|default|k20|m3",
}
FROZEN_RADIUS1_Q: Final = {
    2: Fraction(21702, 582659),
    3: Fraction(32528, 582659),
    5: Fraction(54130, 582659),
    10: Fraction(364025, 1997688),
    20: Fraction(4805093, 13983816),
}
FROZEN_RADIUS1_PORTFOLIO_SHA256: Final = {
    2: "74f912d40045be7fde0bdac0e921883716123f46d2fb62d33c308d48abd7e3ae",
    3: "0244c201efd0b2645a0413be2cbd03ef79e68f44cef34439cda160f37e791b02",
    5: "cbd4c4721a4b83b05127806eafdfe0325a4f3692033686c5e1a6639da122d3e4",
    10: "363a087f9b3f1294291c98f4353115be1031606946d25f6c56774b14261b5f49",
    20: "36d1cd6e226b9e8b982d881854b8cf1c4c3aa90dfce22fe75ba5d8f161385ac0",
}
UNSUPPORTED_REASON: Final = "UNSUPPORTED_LOTTERY_OR_K"


class Radius2Classification(StrEnum):
    """Per-k comparison against the frozen radius-1 terminal."""

    STRICT_IMPROVEMENT = "STRICT_IMPROVEMENT"
    NO_STRICT_IMPROVEMENT = "NO_STRICT_IMPROVEMENT"


class FiveKClassification(StrEnum):
    """Cross-k summary of strict radius-2 improvements."""

    CROSS_K_STRONG = "CROSS_K_STRONG"
    CROSS_K_MIXED = "CROSS_K_MIXED"
    CROSS_K_NONE = "CROSS_K_NONE"


@dataclass(frozen=True, slots=True)
class FrozenRadiusOneBaseline:
    """Read-only HARD_DIV radius-1 terminal used as the radius-2 seed."""

    k: int
    row_id: str
    portfolio: Portfolio
    portfolio_sha256: str
    exact_q: Fraction
    local_optimum_status: str
    global_optimum_status: str


@dataclass(frozen=True, slots=True)
class HardDivRadiusTwoNeighborhood:
    """One complete hard-feasible radius-2 scan from a frozen radius-1 seed."""

    input_portfolio: Portfolio
    input_q: Fraction
    complete_endpoint_count: int
    hard_feasible_endpoint_count: int
    exact_evaluated_endpoint_count: int
    best_feasible_portfolio: Portfolio
    best_feasible_q: Fraction
    delta: Fraction
    accepted_move: bool


@dataclass(frozen=True, slots=True)
class HardDivRadiusTwoKResult:
    """Measured or fail-closed radius-2 comparison for one supported k."""

    status: AdapterStatus
    status_reason: str | None
    k: int
    radius1_q: Fraction | None
    radius2_q: Fraction | None
    delta: Fraction | None
    classification: Radius2Classification | None
    radius1_portfolio: Portfolio | None
    radius1_portfolio_sha256: str | None
    radius2_portfolio: Portfolio | None
    radius2_portfolio_sha256: str | None
    max_pairwise_intersection: int | None
    radius2_terminal_certificate: str | None
    global_optimum_status: str
    neighborhood: HardDivRadiusTwoNeighborhood | None


def _is_supported_dispatch(dispatch: HardDivPairwiseAdapterDispatch) -> bool:
    return (
        dispatch.lottery == BIG_LOTTO
        and dispatch.pool_size == POOL_SIZE
        and dispatch.draw_size == DRAW_SIZE
        and dispatch.minimum_matches == MINIMUM_MATCHES
        and dispatch.k in SUPPORTED_K
    )


def _ticket_respects_cap(candidate: tuple[int, ...], others: tuple[tuple[int, ...], ...]) -> bool:
    candidate_numbers = set(candidate)
    return all(
        len(candidate_numbers.intersection(other)) <= PAIRWISE_MAX_INTERSECTION for other in others
    )


def load_frozen_radius1_baseline(
    k: int,
    *,
    result_path: Path | None = None,
) -> FrozenRadiusOneBaseline:
    """Load the frozen HARD_DIV radius-1 terminal without altering it."""

    if k not in FROZEN_RADIUS1_ROW_ID:
        raise ValueError(f"unsupported HARD_DIV k: {k}")
    path = result_path if result_path is not None else FROZEN_RADIUS1_RESULT_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    row_id = FROZEN_RADIUS1_ROW_ID[k]
    row = next(entry for entry in payload["rows"] if entry.get("row_id") == row_id)
    if row.get("status") != "MEASURED":
        raise ValueError(f"frozen radius-1 row is not MEASURED: {row_id}")
    exact = row["exact_q"]
    q_value = Fraction(exact["numerator"], exact["denominator"])
    if q_value != FROZEN_RADIUS1_Q[k]:
        raise ValueError(f"frozen radius-1 Q identity changed for k={k}")
    portfolio = tuple(tuple(ticket) for ticket in row["portfolio"])
    sha = str(row["portfolio_sha256"])
    if sha != FROZEN_RADIUS1_PORTFOLIO_SHA256[k]:
        raise ValueError(f"frozen radius-1 portfolio hash identity changed for k={k}")
    if row.get("global_optimum_status") != GLOBAL_OPTIMUM_STATUS:
        raise ValueError(f"frozen radius-1 global status changed for k={k}")
    if row.get("local_optimum_status") != "CERTIFIED_ONE_NUMBER_EXCHANGE":
        raise ValueError(f"frozen radius-1 certificate changed for k={k}")
    return FrozenRadiusOneBaseline(
        k=k,
        row_id=row_id,
        portfolio=portfolio,
        portfolio_sha256=sha,
        exact_q=q_value,
        local_optimum_status=str(row["local_optimum_status"]),
        global_optimum_status=str(row["global_optimum_status"]),
    )


def evaluate_hard_feasible_radius_two_neighborhood(
    space: PackedWinningSpace,
    portfolio: Portfolio,
) -> HardDivRadiusTwoNeighborhood:
    """Exact-score every hard-feasible radius-2 endpoint; skip infeasible ones."""

    canonical = _canonical_legal_portfolio(
        portfolio,
        expected_k=len(portfolio),
        pool_size=space.pool_size,
        draw_size=space.draw_size,
    )
    if _portfolio_max_pairwise_intersection(canonical) > PAIRWISE_MAX_INTERSECTION:
        raise ValueError("input portfolio violates hard pairwise cap")
    feasibility = radius_two_endpoint_feasibility(
        space.pool_size,
        space.draw_size,
        canonical,
    )
    portfolio_set = set(canonical)
    first_level_by_slot = one_exchange_candidates_by_slot(canonical, space.pool_size)
    original_qualification = tuple(
        space.ticket_qualification_bitset(ticket) for ticket in canonical
    )
    input_covered = 0
    for bitset in original_qualification:
        input_covered |= bitset
    input_count = input_covered.bit_count()
    input_q = Fraction(input_count, space.total_draws)

    best_count = input_count
    best_portfolio = canonical
    complete_count = 0
    feasible_count = 0
    exact_count = 0

    for slot_index, ticket in enumerate(canonical):
        unchanged_covered = 0
        for other_slot, bitset in enumerate(original_qualification):
            if other_slot != slot_index:
                unchanged_covered |= bitset
        domain = space.universe_mask ^ unchanged_covered
        base_count = space.total_draws - domain.bit_count()
        restricted_numbers = space.restricted_number_bitsets(domain)
        candidates = _single_replacement_tickets(
            ticket,
            pool_size=space.pool_size,
            portfolio_set=portfolio_set,
        )
        unchanged = tuple(
            other for other_slot, other in enumerate(canonical) if other_slot != slot_index
        )
        for candidate in candidates:
            endpoint = _portfolio_with_one_replacement(canonical, slot_index, candidate)
            complete_count += 1
            if not _ticket_respects_cap(candidate, unchanged):
                continue
            feasible_count += 1
            candidate_bits = space.ticket_qualification_bitset(
                candidate,
                restricted_number_bitsets=restricted_numbers,
            )
            candidate_count = base_count + candidate_bits.bit_count()
            exact_count += 1
            if candidate_count > best_count or (
                candidate_count == best_count and endpoint < best_portfolio
            ):
                best_count = candidate_count
                best_portfolio = endpoint

    slot_pairs = tuple(itertools.combinations(range(len(canonical)), 2))
    for left_slot, right_slot in slot_pairs:
        unchanged_covered = 0
        for other_slot, bitset in enumerate(original_qualification):
            if other_slot not in (left_slot, right_slot):
                unchanged_covered |= bitset
        domain = space.universe_mask ^ unchanged_covered
        base_count = space.total_draws - domain.bit_count()
        restricted_numbers = space.restricted_number_bitsets(domain)
        left_candidates = first_level_by_slot[left_slot]
        right_candidates = first_level_by_slot[right_slot]
        left_scored = tuple(
            (
                candidate,
                space.ticket_qualification_bitset(
                    candidate,
                    restricted_number_bitsets=restricted_numbers,
                ),
            )
            for candidate in left_candidates
        )
        right_scored = tuple(
            (
                candidate,
                space.ticket_qualification_bitset(
                    candidate,
                    restricted_number_bitsets=restricted_numbers,
                ),
            )
            for candidate in right_candidates
        )
        overlap = set(left_candidates) & set(right_candidates)
        left_set = set(left_candidates)
        right_set = set(right_candidates)
        unchanged = tuple(
            other
            for other_slot, other in enumerate(canonical)
            if other_slot not in (left_slot, right_slot)
        )
        for left_candidate, left_bits in left_scored:
            skipped_left = not _ticket_respects_cap(left_candidate, unchanged)
            left_numbers = set(left_candidate)
            for right_candidate, right_bits in right_scored:
                if left_candidate == right_candidate:
                    continue
                if overlap and (
                    right_candidate in left_set
                    and left_candidate in right_set
                    and right_candidate < left_candidate
                ):
                    continue
                complete_count += 1
                if skipped_left or not _ticket_respects_cap(right_candidate, unchanged):
                    continue
                if len(left_numbers.intersection(right_candidate)) > PAIRWISE_MAX_INTERSECTION:
                    continue
                feasible_count += 1
                endpoint = _portfolio_with_two_replacements(
                    canonical,
                    left_slot,
                    right_slot,
                    left_candidate,
                    right_candidate,
                )
                candidate_count = (
                    base_count
                    + left_bits.bit_count()
                    + right_bits.bit_count()
                    - (left_bits & right_bits).bit_count()
                )
                exact_count += 1
                if candidate_count > best_count or (
                    candidate_count == best_count and endpoint < best_portfolio
                ):
                    best_count = candidate_count
                    best_portfolio = endpoint

    if complete_count != feasibility.unique_endpoint_count:
        raise RuntimeError(
            "complete radius-2 endpoint count mismatch: "
            f"expected {feasibility.unique_endpoint_count}, got {complete_count}"
        )
    if exact_count != feasible_count:
        raise RuntimeError("hard-feasible endpoints were not exact-scored one-for-one")

    best_q = Fraction(best_count, space.total_draws)
    accepted_move = best_count > input_count
    if not accepted_move:
        best_portfolio = canonical
        best_q = input_q
    delta = best_q - input_q
    return HardDivRadiusTwoNeighborhood(
        input_portfolio=canonical,
        input_q=input_q,
        complete_endpoint_count=complete_count,
        hard_feasible_endpoint_count=feasible_count,
        exact_evaluated_endpoint_count=exact_count,
        best_feasible_portfolio=best_portfolio,
        best_feasible_q=best_q,
        delta=delta,
        accepted_move=accepted_move,
    )


def _non_measured_k_result(
    k: int,
    *,
    status: AdapterStatus,
    reason: str,
) -> HardDivRadiusTwoKResult:
    return HardDivRadiusTwoKResult(
        status=status,
        status_reason=reason,
        k=k,
        radius1_q=None,
        radius2_q=None,
        delta=None,
        classification=None,
        radius1_portfolio=None,
        radius1_portfolio_sha256=None,
        radius2_portfolio=None,
        radius2_portfolio_sha256=None,
        max_pairwise_intersection=None,
        radius2_terminal_certificate=None,
        global_optimum_status=GLOBAL_OPTIMUM_STATUS,
        neighborhood=None,
    )


def compare_hard_div_radius_two(
    dispatch: HardDivPairwiseAdapterDispatch,
    *,
    space: PackedWinningSpace | None = None,
    frozen_result_path: Path | None = None,
) -> HardDivRadiusTwoKResult:
    """Compare one frozen HARD_DIV radius-1 terminal to its exact radius-2 neighborhood."""

    if not _is_supported_dispatch(dispatch):
        return _non_measured_k_result(
            dispatch.k,
            status=AdapterStatus.NOT_APPLICABLE,
            reason=UNSUPPORTED_REASON,
        )
    try:
        baseline = load_frozen_radius1_baseline(
            dispatch.k,
            result_path=frozen_result_path,
        )
        if space is None:
            space = PackedWinningSpace.build(POOL_SIZE, DRAW_SIZE)
        if space.pool_size != POOL_SIZE or space.draw_size != DRAW_SIZE:
            raise ValueError("PackedWinningSpace does not match frozen BIG_LOTTO identity")
        replay_q = space.exact_portfolio_q(baseline.portfolio)
        if replay_q != baseline.exact_q:
            raise ValueError("frozen radius-1 Q does not replay on the exact packed space")
        neighborhood = evaluate_hard_feasible_radius_two_neighborhood(
            space,
            baseline.portfolio,
        )
        if neighborhood.input_q != baseline.exact_q:
            raise ValueError("radius-2 input Q diverged from frozen radius-1 Q")
        if neighborhood.accepted_move:
            classification = Radius2Classification.STRICT_IMPROVEMENT
            certificate = RADIUS2_IMPROVEMENT_CERTIFICATE
            radius2_portfolio = neighborhood.best_feasible_portfolio
            radius2_q = neighborhood.best_feasible_q
        else:
            classification = Radius2Classification.NO_STRICT_IMPROVEMENT
            certificate = RADIUS2_LOCAL_CERTIFICATE
            radius2_portfolio = baseline.portfolio
            radius2_q = baseline.exact_q
        if _portfolio_max_pairwise_intersection(radius2_portfolio) > PAIRWISE_MAX_INTERSECTION:
            raise ValueError("radius-2 portfolio violates hard pairwise cap")
        delta = radius2_q - baseline.exact_q
        if delta != neighborhood.delta:
            raise ValueError("radius-2 delta arithmetic mismatch")
        return HardDivRadiusTwoKResult(
            status=AdapterStatus.MEASURED,
            status_reason=None,
            k=dispatch.k,
            radius1_q=baseline.exact_q,
            radius2_q=radius2_q,
            delta=delta,
            classification=classification,
            radius1_portfolio=baseline.portfolio,
            radius1_portfolio_sha256=baseline.portfolio_sha256,
            radius2_portfolio=radius2_portfolio,
            radius2_portfolio_sha256=_portfolio_sha256(radius2_portfolio),
            max_pairwise_intersection=_portfolio_max_pairwise_intersection(radius2_portfolio),
            radius2_terminal_certificate=certificate,
            global_optimum_status=GLOBAL_OPTIMUM_STATUS,
            neighborhood=neighborhood,
        )
    except Exception as error:
        return _non_measured_k_result(
            dispatch.k,
            status=AdapterStatus.NOT_RUN,
            reason=f"EXISTING_NATIVE_EXECUTION_FAILED:{type(error).__name__}:{error}",
        )


def classify_five_k(
    results: tuple[HardDivRadiusTwoKResult, ...],
) -> FiveKClassification:
    """Classify the five-k HARD_DIV radius-2 comparison."""

    measured = tuple(
        result
        for result in results
        if result.status == AdapterStatus.MEASURED and result.classification is not None
    )
    if len(measured) != 5:
        raise ValueError("five-k classification requires five MEASURED rows")
    improved = sum(
        result.classification == Radius2Classification.STRICT_IMPROVEMENT for result in measured
    )
    if improved == 5:
        return FiveKClassification.CROSS_K_STRONG
    if improved == 0:
        return FiveKClassification.CROSS_K_NONE
    return FiveKClassification.CROSS_K_MIXED


def _rational(value: Fraction) -> dict[str, int | str]:
    return {
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
        "numerator": value.numerator,
    }


def k_result_payload(result: HardDivRadiusTwoKResult) -> dict[str, Any]:
    """Serialize one k-row from the already-computed semantic result."""

    neighborhood = result.neighborhood
    return {
        "classification": None if result.classification is None else str(result.classification),
        "delta": None if result.delta is None else _rational(result.delta),
        "global_optimum_status": result.global_optimum_status,
        "k": result.k,
        "max_pairwise_intersection": result.max_pairwise_intersection,
        "neighborhood": None
        if neighborhood is None
        else {
            "accepted_move": neighborhood.accepted_move,
            "complete_endpoint_count": neighborhood.complete_endpoint_count,
            "exact_evaluated_endpoint_count": neighborhood.exact_evaluated_endpoint_count,
            "hard_feasible_endpoint_count": neighborhood.hard_feasible_endpoint_count,
        },
        "radius1_portfolio": result.radius1_portfolio,
        "radius1_portfolio_sha256": result.radius1_portfolio_sha256,
        "radius1_q": None if result.radius1_q is None else _rational(result.radius1_q),
        "radius2_portfolio": result.radius2_portfolio,
        "radius2_portfolio_sha256": result.radius2_portfolio_sha256,
        "radius2_q": None if result.radius2_q is None else _rational(result.radius2_q),
        "radius2_terminal_certificate": result.radius2_terminal_certificate,
        "status": str(result.status),
        "status_reason": result.status_reason,
    }


def reconciliation_payload(
    results: tuple[HardDivRadiusTwoKResult, ...],
    *,
    five_k_classification: FiveKClassification | None,
) -> dict[str, Any]:
    """Build the durable semantic payload without rerunning search."""

    return {
        "baseline_certificate": BASELINE_CERTIFICATE,
        "baseline_method_id": METHOD_ID,
        "five_k_classification": None
        if five_k_classification is None
        else str(five_k_classification),
        "global_optimum_status": GLOBAL_OPTIMUM_STATUS,
        "hard_pairwise_max_intersection": PAIRWISE_MAX_INTERSECTION,
        "k_results": [k_result_payload(result) for result in results],
        "lottery": BIG_LOTTO,
        "minimum_matches": MINIMUM_MATCHES,
        "neighborhood_unit": RADIUS_TWO_NEIGHBORHOOD_UNIT,
        "pool_size": POOL_SIZE,
        "proof_status": PROOF_STATUS,
        "supported_k": list(SUPPORTED_K),
        "task_id": "BIG_LOTTO_HARD_DIV_EXACT_RADIUS2_RECONCILIATION_R1",
        "total_draw_count": WINNING_DRAW_COUNT,
    }


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Independently serialize an already-computed semantic result."""

    return (json.dumps(payload, indent=2, sort_keys=True).rstrip("\n") + "\n").encode("utf-8")


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def big_lotto_radius_two_dispatch(k: int) -> HardDivPairwiseAdapterDispatch:
    return big_lotto_dispatch(k)
