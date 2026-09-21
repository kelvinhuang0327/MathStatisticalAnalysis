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
    SEALED_GEOMETRY_METHOD_VERSION,
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

CANONICAL_FRONTIER_LOCATOR = (
    "docs/research/matrix-native-results/"
    "b649-official-any-prize-frontier-reconciliation-r1/frontier_reconciliation.json"
)
CANONICAL_FRONTIER_SHA256 = (
    "5b0ccf7485c3db699b9bb9e398f04857d018ec7b1ca87700f86cbace5a719d3e"
)
K5_EXPECTED_TICKETS = (
    (1, 2, 3, 4, 5, 6),
    (7, 8, 9, 10, 11, 12),
    (13, 14, 15, 16, 17, 18),
    (19, 20, 21, 22, 23, 24),
    (25, 26, 27, 28, 29, 30),
)
K5_EXPECTED_PROVENANCE = {
    "ticket_count": 5,
    "portfolio_sha256": "ec858fe04075ee40931366c05617ad7d04d934c5f72ac35c9b74c26ba91f8d87",
    "source_id": "STRATEGY_MATRIX_REFERENCE_E_METHOD_E_20_PREFIX_K5",
    "source_locator": (
        "docs/research/matrix-native-results/"
        "diversification-constructor-frontier-b649-v1-result.json"
    ),
    "source_sha256": "f2a48557dffb04a2ac13ed2b1286ef85bb5fffda97313728863680c67200ffec",
    "m3_plus_probability": "54130/582659",
    "official_any_prize_probability": "547495/3579191",
}
FROZEN_V2_PORTFOLIOS = {
    10: {
        "frontier_selector": 4,
        "source_id": "HARD_DIV_PAIRWISE_OVERLAP_R1_K10_RADIUS2",
        "portfolio_sha256": "13b1126d5b26ce44c9aba24670142eeab49f4a4b51aaf3bbabe7a7f1659ac673",
        "m3_plus": "364025/1997688",
        "official_any_prize": "536005/1827672",
    },
    20: {
        "frontier_selector": 8,
        "source_id": "HARD_DIV_PAIRWISE_OVERLAP_R1_K20_RADIUS2",
        "portfolio_sha256": "9a802a103f79948f2345e51f4746860236857f18beece22fe444886cde9d3424",
        "m3_plus": "1601841/4661272",
        "official_any_prize": "22345625/42950292",
    },
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


def test_method_v2_and_k5_identity_are_unchanged_from_v1() -> None:
    assert SEALED_GEOMETRY_METHOD_VERSION == "2.0.0"
    entry = SEALED_GEOMETRY_PORTFOLIOS[5]

    assert entry.tickets == K5_EXPECTED_TICKETS
    assert entry.provenance() == K5_EXPECTED_PROVENANCE


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


def _committed_json(locator: str, expected_sha256: str) -> dict[str, object]:
    raw = (REPO_ROOT / locator).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha256
    return cast(dict[str, object], json.loads(raw))


def test_k10_and_k20_match_the_frozen_canonical_frontier_contract() -> None:
    frontier = _committed_json(CANONICAL_FRONTIER_LOCATOR, CANONICAL_FRONTIER_SHA256)
    identities = cast(list[dict[str, object]], frontier["CANDIDATE_IDENTITIES"])

    for size, expected in FROZEN_V2_PORTFOLIOS.items():
        entry = SEALED_GEOMETRY_PORTFOLIOS[size]
        selector = cast(int, expected["frontier_selector"])
        candidate = identities[selector]
        exact = cast(dict[str, object], candidate["EXACT_EVALUATION"])
        source = next(
            identity
            for identity in cast(list[dict[str, object]], candidate["SOURCE_IDENTITIES"])
            if identity["SOURCE_ID"] == expected["source_id"]
        )

        assert entry.source_id == expected["source_id"]
        assert entry.source_locator == CANONICAL_FRONTIER_LOCATOR
        assert entry.source_sha256 == CANONICAL_FRONTIER_SHA256
        assert entry.portfolio_sha256 == expected["portfolio_sha256"]
        assert canonical_portfolio_sha256(entry.tickets) == expected["portfolio_sha256"]
        assert candidate["K"] == size
        assert candidate["NORMALIZED_SEMANTIC_ID"] == expected["portfolio_sha256"]
        assert candidate["NORMALIZED_TICKET_SET"] == [list(ticket) for ticket in entry.tickets]
        assert exact["m3_plus"] == expected["m3_plus"]
        assert exact["official_any_prize"] == expected["official_any_prize"]
        assert source["SOURCE_ID"] == expected["source_id"]
        assert source["SOURCE_FILE_SHA256"] == (
            "2d37c6dceb69664b489a458f46d201d9e13b544a08c3924ece8b848f44d25b82"
        )


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
