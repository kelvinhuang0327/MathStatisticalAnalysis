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
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.b649_sealed_geometry_portfolio import (
    K20_PORTFOLIO_VERSION,
    K20_V7_PORTFOLIO_VERSION,
    SEALED_GEOMETRY_K20_VERSIONS,
    SEALED_GEOMETRY_METHOD_ID,
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
CANONICAL_FRONTIER_SHA256 = "5b0ccf7485c3db699b9bb9e398f04857d018ec7b1ca87700f86cbace5a719d3e"
K20_WINNER_TASK_ID = "B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1"
K20_WINNER_RESULT_LOCATOR = (
    "docs/research/matrix-native-results/"
    "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
K20_WINNER_RESULT_SHA256 = "3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00"
K20_SOURCE_PORTFOLIO_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
K20_EXPECTED_ENGINE_NORMALIZED_SHA256 = (
    "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
)
K20_START_ARTIFACT_SHA256 = "10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b"
K20_V7_TASK_ID = "B649_K20_EXACT_TWO_TICKET_JOINT_REPLACEMENT_SWEEP_R1"
K20_V7_RESULT_LOCATOR = (
    "docs/research/matrix-native-results/"
    "b649-k20-exact-two-ticket-joint-replacement-terminal-r1.json"
)
K20_V7_RESULT_SHA256 = "e7698ff0d76a91c69378bf9bf0badb4ed9ac4f4dd146c71e5c94300bcfbbff9e"
K20_V7_PORTFOLIO_SHA256 = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
K20_V7_COVERAGE = 313239661
K20_V8_COVERAGE = 313263888
K20_TOTAL_OUTCOMES = 601304088
K20_V8_SOURCE_REVISION = "da26b434499927f5611e3c3d12e50485f2e58a6a"
K20_EXPECTED_OUTCOME_COUNT = K20_V8_COVERAGE
K20_EXPECTED_EXACT_FRACTION = Fraction(1864666, 3579191)
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
    # Selected independently per K, so deliberately not nested.
    assert buckets[10] != buckets[20][:10]
    assert buckets[5] != buckets[10][:5]


def test_method_v8_and_k5_identity_are_unchanged_from_v1() -> None:
    assert SEALED_GEOMETRY_METHOD_ID == "B649_SEALED_GEOMETRY_PORTFOLIO"
    assert SEALED_GEOMETRY_METHOD_VERSION == "8.0.0"
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
    if size == 20:
        historical_v7 = SEALED_GEOMETRY_K20_VERSIONS[K20_V7_PORTFOLIO_VERSION]
        old_result = evaluate_portfolio(historical_v7.tickets, draws=big_lotto_draws)
        outcome_space = result.main_draw_count * result.special_count
        gain = result.official_any_prize_outcome_count - old_result.official_any_prize_outcome_count

        assert result.official_any_prize_outcome_count == K20_V8_COVERAGE
        assert old_result.official_any_prize_outcome_count == K20_V7_COVERAGE
        assert result.official_any_prize == K20_EXPECTED_EXACT_FRACTION
        assert outcome_space == K20_TOTAL_OUTCOMES
        assert gain == 24227


@pytest.mark.parametrize("size", [5, 10, 20])
def test_sealed_portfolios_beat_independent_random_tickets(size: int) -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[size]

    assert entry.official_any_prize_probability > independent_random_official_any_prize(size)


def _committed_json(locator: str, expected_sha256: str) -> dict[str, object]:
    raw = (REPO_ROOT / locator).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha256
    return cast(dict[str, object], json.loads(raw))


def test_k10_matches_the_frozen_canonical_frontier_contract() -> None:
    frontier = _committed_json(CANONICAL_FRONTIER_LOCATOR, CANONICAL_FRONTIER_SHA256)
    identities = cast(list[dict[str, object]], frontier["CANDIDATE_IDENTITIES"])
    for size, expected in FROZEN_V2_PORTFOLIOS.items():
        if size == 20:
            continue
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


def test_k20_matches_v8_two_ticket_ascent_authority() -> None:
    entry = SEALED_GEOMETRY_PORTFOLIOS[20]
    authority = _committed_json(K20_WINNER_RESULT_LOCATOR, K20_WINNER_RESULT_SHA256)
    sealed_tickets = cast(list[list[int]], authority["FINAL_TICKETS"])

    assert entry.source_id == K20_WINNER_TASK_ID
    assert entry.source_locator == K20_WINNER_RESULT_LOCATOR
    assert entry.source_sha256 == K20_WINNER_RESULT_SHA256
    assert entry.tickets == tuple(tuple(ticket) for ticket in sealed_tickets)
    assert entry.portfolio_sha256 == K20_SOURCE_PORTFOLIO_SHA256
    assert canonical_portfolio_sha256(entry.tickets) == K20_SOURCE_PORTFOLIO_SHA256
    assert K20_V7_PORTFOLIO_VERSION == "7.0.0"
    assert K20_PORTFOLIO_VERSION == "8.0.0"
    assert SEALED_GEOMETRY_K20_VERSIONS[K20_PORTFOLIO_VERSION] is entry
    assert entry.portfolio_version == K20_PORTFOLIO_VERSION
    assert entry.source_revision == K20_V8_SOURCE_REVISION
    assert entry.provenance()["portfolio_version"] == K20_PORTFOLIO_VERSION
    assert entry.provenance()["source_revision"] == K20_V8_SOURCE_REVISION
    assert str(entry.official_any_prize_probability) == authority["FINAL_EXACT_FRACTION"]
    assert entry.official_any_prize_probability == K20_EXPECTED_EXACT_FRACTION
    assert entry.m3_plus_probability == Fraction(1201973, 3495954)

    assert authority["TASK_ID"] == K20_WINNER_TASK_ID
    assert authority["TASK_STATUS"] == "COMPLETE"
    assert authority["FINAL_COUNT"] == K20_EXPECTED_OUTCOME_COUNT
    assert authority["FINAL_ENGINE_NORMALIZED_SHA256"] == (
        K20_EXPECTED_ENGINE_NORMALIZED_SHA256
    )
    assert authority["START_ARTIFACT_SHA256"] == K20_START_ARTIFACT_SHA256
    assert K20_START_ARTIFACT_SHA256 != K20_EXPECTED_ENGINE_NORMALIZED_SHA256
    assert (
        authority["TWO_TICKET_LOCAL_OPTIMUM_STATUS"]
        == "PROVEN_FOR_VALIDATED_EXACT_TWO_TICKET_NEIGHBORHOOD"
    )
    assert authority["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"


def test_k20_v7_history_matches_the_sealed_sweep_terminal() -> None:
    entry = SEALED_GEOMETRY_K20_VERSIONS[K20_V7_PORTFOLIO_VERSION]
    authority = _committed_json(K20_V7_RESULT_LOCATOR, K20_V7_RESULT_SHA256)
    sealed_tickets = cast(list[list[int]], authority["TICKETS"])

    assert entry.source_id == K20_V7_TASK_ID
    assert entry.source_locator == K20_V7_RESULT_LOCATOR
    assert entry.source_sha256 == K20_V7_RESULT_SHA256
    assert entry.tickets == tuple(tuple(ticket) for ticket in sealed_tickets)
    assert entry.portfolio_sha256 == K20_V7_PORTFOLIO_SHA256
    assert canonical_portfolio_sha256(entry.tickets) == K20_V7_PORTFOLIO_SHA256
    assert str(entry.official_any_prize_probability) == authority["FINAL_EXACT_FRACTION"]
    assert entry.official_any_prize_probability == Fraction(44748523, 85900584)

    assert authority["TASK_ID"] == K20_V7_TASK_ID
    assert authority["RESULT_TYPE"] == "TERMINAL_LOCAL_OPTIMUM"
    assert authority["METHOD_ID"] == SEALED_GEOMETRY_METHOD_ID
    assert authority["METHOD_VERSION"] == K20_V7_PORTFOLIO_VERSION
    assert authority["FINAL_EXACT_COUNT"] == K20_V7_COVERAGE
    assert authority["TOTAL_OUTCOMES"] == K20_TOTAL_OUTCOMES
    assert authority["GLOBAL_OPTIMUM"] == "UNKNOWN"


def test_k20_geometry_matches_the_sealed_overlap_and_usage_contract() -> None:
    tickets = SEALED_GEOMETRY_PORTFOLIOS[20].tickets
    overlaps = [
        len(set(left) & set(right))
        for index, left in enumerate(tickets)
        for right in tickets[index + 1 :]
    ]
    number_uses = Counter(number for ticket in tickets for number in ticket)

    assert len(tickets) == len(set(tickets)) == 20
    assert Counter(overlaps) == Counter({0: 97, 1: 93})
    assert max(overlaps) == 1
    assert sum(overlap * overlap for overlap in overlaps) == 93
    assert Counter(number_uses.values()) == Counter({2: 27, 3: 22})


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


@pytest.mark.parametrize(
    "tickets",
    [
        (*SEALED_GEOMETRY_PORTFOLIOS[20].tickets[:-1], SEALED_GEOMETRY_PORTFOLIOS[20].tickets[0]),
        (
            (1, 2, 3, 4, 5, 50),
            *SEALED_GEOMETRY_PORTFOLIOS[20].tickets[1:],
        ),
    ],
)
def test_k20_integrity_rejects_duplicate_or_illegal_ticket(
    tickets: tuple[tuple[int, ...], ...],
) -> None:
    tampered = dataclasses.replace(SEALED_GEOMETRY_PORTFOLIOS[20], tickets=tickets)

    with pytest.raises(SealedGeometryIntegrityError):
        verify_sealed_geometry_portfolio(tampered)


def test_unsupported_bucket_size_is_rejected() -> None:
    with pytest.raises(SealedGeometryIntegrityError):
        sealed_geometry_buckets((5, 15))
