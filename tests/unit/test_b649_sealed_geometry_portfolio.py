"""Production acceptance for the sealed B649 geometry portfolios.

The efficacy evidence is exact combinatorial probability under the uniform
fair-draw model, recomputed here over the full outcome space -- not replayed
history. These tests are the regression floor: the production buckets may only
change to portfolios that are at least as good on exact OFFICIAL_ANY_PRIZE.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    SealedGeometryIntegrityError,
    canonical_portfolio_sha256,
    sealed_geometry_buckets,
    verify_sealed_geometry_portfolio,
)
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    independent_random_official_any_prize,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# The P0c capture-gap portfolios this integration was commissioned to ship. The
# production buckets must never fall below them on exact OFFICIAL_ANY_PRIZE.
P0C_OFFICIAL_ANY_PRIZE_FLOOR = {
    10: Fraction(1095245, 3734808),
    20: Fraction(44615213, 85900584),
}


@pytest.fixture(scope="module")
def big_lotto_draws() -> DrawMasks:
    return all_main_draw_masks(49, 6)


def test_operational_buckets_are_sealed_for_k5_k10_k20() -> None:
    assert sorted(SEALED_GEOMETRY_PORTFOLIOS) == [5, 10, 20]
    buckets = sealed_geometry_buckets((5, 10, 20))

    for size, tickets in buckets.items():
        entry = SEALED_GEOMETRY_PORTFOLIOS[size]
        assert tickets == entry.tickets
        assert canonical_portfolio_sha256(tickets) == entry.portfolio_sha256
    # Independently optimal per K, so deliberately not nested.
    assert buckets[10] != buckets[20][:10]
    assert buckets[5] != buckets[10][:5]


@pytest.mark.parametrize("size", [5, 10, 20])
def test_exact_probabilities_reproduce_the_sealed_record(
    size: int, big_lotto_draws: DrawMasks
) -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[size]

    result = evaluate_portfolio(entry.tickets, draws=big_lotto_draws)

    assert result.m3_plus == entry.m3_plus_probability
    assert result.official_any_prize == entry.official_any_prize_probability


@pytest.mark.parametrize("size", [5, 10, 20])
def test_sealed_portfolios_beat_independent_random_tickets(size: int) -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[size]

    assert entry.official_any_prize_probability > independent_random_official_any_prize(size)


@pytest.mark.parametrize("size", sorted(P0C_OFFICIAL_ANY_PRIZE_FLOOR))
def test_sealed_portfolios_are_no_worse_than_the_p0c_solution(size: int) -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[size]

    assert entry.official_any_prize_probability >= P0C_OFFICIAL_ANY_PRIZE_FLOOR[size]


def _committed_json(locator: str, expected_sha256: str) -> dict[str, object]:
    raw = (REPO_ROOT / locator).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha256
    return cast(dict[str, object], json.loads(raw))


@pytest.mark.parametrize("size", sorted(P0C_OFFICIAL_ANY_PRIZE_FLOOR))
def test_k10_and_k20_are_the_commissioned_p0c_portfolios(size: int) -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[size]

    assert entry.source_id == f"B649_ANY_PRIZE_OBJECTIVE_CORRECTION_R1_P0C_CAPTURE_GAP_K{size}"
    assert entry.official_any_prize_probability == P0C_OFFICIAL_ANY_PRIZE_FLOOR[size]


def test_k5_reaches_the_committed_frontier_best_found_with_disjoint_tickets() -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[5]
    frontier = _committed_json(entry.source_locator, entry.source_sha256)

    best_found = cast(dict[str, dict[str, object]], frontier["best_found_q_primary_event"])["5"]

    assert Fraction(cast(str, best_found["exact"])) == entry.m3_plus_probability
    numbers = [number for ticket in entry.tickets for number in ticket]
    assert len(numbers) == len(set(numbers))


def test_every_ticket_number_is_used_at_k10_and_k20() -> None:
    for size in (10, 20):
        used = {number for ticket in SEALED_GEOMETRY_PORTFOLIOS[size].tickets for number in ticket}
        assert used == set(range(1, 50))


@pytest.mark.parametrize(
    "tickets",
    [
        # One number swapped: legal, but no longer the sealed identity.
        ((1, 2, 3, 4, 5, 7), *SEALED_GEOMETRY_PORTFOLIOS[5].tickets[1:]),
        # Unsorted ticket.
        ((2, 1, 3, 4, 5, 6), *SEALED_GEOMETRY_PORTFOLIOS[5].tickets[1:]),
        # Duplicate ticket.
        (*SEALED_GEOMETRY_PORTFOLIOS[5].tickets[:4], SEALED_GEOMETRY_PORTFOLIOS[5].tickets[0]),
        # Out-of-pool number.
        ((1, 2, 3, 4, 5, 50), *SEALED_GEOMETRY_PORTFOLIOS[5].tickets[1:]),
    ],
)
def test_integrity_check_rejects_any_drift(tickets: tuple[tuple[int, ...], ...]) -> None:
    tampered = dataclasses.replace(SEALED_GEOMETRY_PORTFOLIOS[5], tickets=tickets)

    with pytest.raises(SealedGeometryIntegrityError):
        verify_sealed_geometry_portfolio(tampered)


def test_unsupported_bucket_size_is_rejected() -> None:
    with pytest.raises(SealedGeometryIntegrityError):
        sealed_geometry_buckets((5, 15))
