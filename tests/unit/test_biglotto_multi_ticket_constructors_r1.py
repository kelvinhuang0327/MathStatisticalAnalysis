from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from lottolab.research.biglotto_multi_ticket_constructors_r1 import (
    B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1_METADATA,
    B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1_METADATA,
    B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA,
    CONSTRUCTOR_METADATA,
    CONSTRUCTORS,
    SUPPORTED_TICKET_COUNTS,
    Ticket,
    construct_b649_candidate_set_exposure_balanced_v1,
    construct_b649_candidate_set_hybrid_diversity_v1,
    construct_b649_candidate_set_low_overlap_v1,
)

CandidateConstructor = Callable[[tuple[Ticket, ...], int], tuple[Ticket, ...]]

_POOL: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 8, 9, 10, 11),
    (2, 7, 12, 13, 14, 15),
    (3, 8, 16, 17, 18, 19),
    (4, 9, 20, 21, 22, 23),
    (5, 10, 24, 25, 26, 27),
    (6, 11, 28, 29, 30, 31),
    (1, 12, 20, 28, 36, 44),
    (2, 13, 21, 29, 37, 45),
    (3, 14, 22, 30, 38, 46),
    (4, 15, 23, 31, 39, 47),
    (5, 16, 24, 32, 40, 48),
    (6, 17, 25, 33, 41, 49),
    (7, 18, 26, 34, 42, 43),
    (8, 19, 27, 35, 40, 46),
    (9, 20, 28, 36, 41, 47),
    (10, 21, 29, 37, 42, 48),
    (11, 22, 30, 38, 43, 49),
    (12, 23, 31, 39, 44, 45),
    (13, 24, 32, 40, 46, 47),
    (14, 25, 33, 41, 48, 49),
    (15, 26, 34, 42, 44, 46),
    (16, 27, 35, 43, 45, 47),
    (17, 28, 36, 44, 48, 49),
)


def _run_all(
    candidate_tickets: tuple[Ticket, ...], ticket_count: int
) -> tuple[tuple[Ticket, ...], ...]:
    return tuple(
        constructor(candidate_tickets, ticket_count)
        for constructor in (
            construct_b649_candidate_set_low_overlap_v1,
            construct_b649_candidate_set_exposure_balanced_v1,
            construct_b649_candidate_set_hybrid_diversity_v1,
        )
    )


def _exposure_vector(portfolio: tuple[Ticket, ...]) -> tuple[int, ...]:
    counts = [0] * 49
    for ticket in portfolio:
        for number in ticket:
            counts[number - 1] += 1
    return tuple(sorted(counts, reverse=True))


def test_valid_legal_candidate_pool_supports_all_three_families() -> None:
    portfolios = _run_all(_POOL, 5)
    assert all(len(portfolio) == 5 for portfolio in portfolios)
    assert all(len(set(portfolio)) == 5 for portfolio in portfolios)
    assert all(ticket == tuple(sorted(ticket)) for portfolio in portfolios for ticket in portfolio)


@pytest.mark.parametrize("ticket_count", [5, 10, 20])
def test_native_ticket_budgets_are_supported(ticket_count: int) -> None:
    for portfolio in _run_all(_POOL, ticket_count):
        assert len(portfolio) == ticket_count


def test_unsupported_ticket_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="supported native budgets"):
        construct_b649_candidate_set_low_overlap_v1(_POOL, 2)


def test_candidate_count_below_ticket_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 5"):
        construct_b649_candidate_set_exposure_balanced_v1(_POOL[:4], 5)


@pytest.mark.parametrize(
    ("bad_ticket", "message"),
    [
        ((1, 2, 3, 4, 5), "exactly 6"),
        ((1, 2, 3, 4, 5, 6, 7), "exactly 6"),
        ((0, 2, 3, 4, 5, 6), "outside 1..49"),
        ((1, 2, 3, 4, 5, 50), "outside 1..49"),
        ((1, 2, 3, 3, 5, 6), "strictly ascending"),
        ((1, 2, 4, 3, 5, 6), "strictly ascending"),
    ],
)
def test_malformed_ticket_is_rejected(bad_ticket: tuple[int, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        construct_b649_candidate_set_hybrid_diversity_v1((bad_ticket, *_POOL), 5)


def test_mutable_ticket_is_rejected_instead_of_silently_canonicalized() -> None:
    bad_pool: tuple[object, ...] = ([1, 2, 3, 4, 5, 6], *_POOL[1:])
    with pytest.raises(ValueError, match="immutable tuple"):
        construct_b649_candidate_set_low_overlap_v1(bad_pool, 5)


def test_duplicate_candidate_ticket_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate ticket"):
        construct_b649_candidate_set_exposure_balanced_v1((*_POOL, _POOL[0]), 5)


def test_source_candidate_order_is_the_final_tie_authority() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
    )
    assert construct_b649_candidate_set_low_overlap_v1(pool, 5)[0] == pool[0]
    assert construct_b649_candidate_set_exposure_balanced_v1(pool, 5)[0] == pool[0]
    assert construct_b649_candidate_set_hybrid_diversity_v1(pool, 5)[0] == pool[0]


def test_low_overlap_max_overlap_precedes_source_rank() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (7, 8, 9, 10, 11, 12),
        (2, 13, 14, 15, 16, 17),
        (3, 18, 19, 20, 21, 22),
    )
    portfolio = construct_b649_candidate_set_low_overlap_v1(pool, 5)
    assert portfolio[:2] == (pool[0], pool[2])


def test_low_overlap_total_overlap_is_secondary() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (1, 12, 13, 14, 15, 16),
        (2, 3, 17, 18, 19, 20),
        (4, 5, 21, 22, 23, 24),
    )
    portfolio = construct_b649_candidate_set_low_overlap_v1(pool, 5)
    # After the first ticket, candidates 1 and 2 both have max overlap 1.
    # Candidate 1 has total overlap 1, so it is selected before candidate 2.
    assert portfolio[:3] == (pool[0], pool[1], pool[2])


def test_exposure_balanced_maximum_exposure_precedes_source_rank() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (7, 8, 9, 10, 11, 12),
        (2, 13, 14, 15, 16, 17),
        (3, 18, 19, 20, 21, 22),
    )
    portfolio = construct_b649_candidate_set_exposure_balanced_v1(pool, 5)
    assert portfolio[:2] == (pool[0], pool[2])


def test_exposure_balanced_uses_the_full_exposure_vector() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 7, 8, 9, 10),
        (1, 11, 12, 13, 14, 15),
        (3, 16, 17, 18, 19, 20),
        (4, 21, 22, 23, 24, 25),
    )
    portfolio = construct_b649_candidate_set_exposure_balanced_v1(pool, 5)
    # Candidates 1 and 2 both create maximum exposure 2.  Candidate 2 has
    # vector (2, 1, 1, ...) versus candidate 1's (2, 2, 1, ...).
    assert portfolio[:2] == (pool[0], pool[2])


def test_hybrid_max_overlap_precedes_exposure_vector() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (1, 12, 13, 14, 15, 16),
        (2, 3, 17, 18, 19, 20),
        (3, 4, 21, 22, 23, 24),
    )
    portfolio = construct_b649_candidate_set_hybrid_diversity_v1(pool, 5)
    assert portfolio[:3] == (pool[0], pool[1], pool[2])


def test_hybrid_exposure_vector_is_secondary_to_max_overlap() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (1, 12, 13, 14, 15, 16),
        (2, 17, 18, 19, 20, 21),
        (3, 4, 22, 23, 24, 25),
    )
    portfolio = construct_b649_candidate_set_hybrid_diversity_v1(pool, 5)
    # Candidates 2 and 3 tie on max overlap 1; candidate 3 spreads exposure
    # more evenly and therefore wins despite its later source rank.
    assert portfolio[:3] == (pool[0], pool[1], pool[3])


def test_hybrid_total_overlap_coordinate_is_present_after_exposure_vector() -> None:
    objective = B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1_METADATA.SELECTION_OBJECTIVE
    assert objective.index("EXPOSURE_VECTOR_AFTER_ADDING_CANDIDATE") < objective.index(
        "TOTAL_OVERLAP"
    )
    assert objective.index("TOTAL_OVERLAP") < objective.index("ORIGINAL_RANK")


def test_repeated_invocation_is_identical() -> None:
    for constructor in (
        construct_b649_candidate_set_low_overlap_v1,
        construct_b649_candidate_set_exposure_balanced_v1,
        construct_b649_candidate_set_hybrid_diversity_v1,
    ):
        assert constructor(_POOL, 20) == constructor(_POOL, 20)


def test_caller_input_is_not_mutated() -> None:
    source = list(_POOL)
    snapshot = source.copy()
    result = construct_b649_candidate_set_low_overlap_v1(source, 10)
    assert source == snapshot
    assert result == construct_b649_candidate_set_low_overlap_v1(tuple(snapshot), 10)


@pytest.mark.parametrize("constructor", list(CONSTRUCTORS.values()))
def test_returned_tickets_remain_legal_and_distinct(constructor: CandidateConstructor) -> None:
    portfolio = constructor(_POOL, 20)
    assert len(portfolio) == 20
    assert len(set(portfolio)) == 20
    for ticket in portfolio:
        assert len(ticket) == 6
        assert all(type(number) is int and 1 <= number <= 49 for number in ticket)
        assert ticket == tuple(sorted(ticket))


@pytest.mark.parametrize("constructor", list(CONSTRUCTORS.values()))
def test_exposure_ladder_is_an_exact_prefix(constructor: CandidateConstructor) -> None:
    portfolio_5 = constructor(_POOL, 5)
    portfolio_10 = constructor(_POOL, 10)
    portfolio_20 = constructor(_POOL, 20)
    assert portfolio_10[:5] == portfolio_5
    assert portfolio_20[:10] == portfolio_10


def test_adversarial_pool_demonstrates_selection_not_first_k_slicing() -> None:
    pool = (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 7, 8, 9),
        (1, 2, 3, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
        (31, 32, 33, 34, 35, 36),
    )
    for constructor in (
        construct_b649_candidate_set_low_overlap_v1,
        construct_b649_candidate_set_exposure_balanced_v1,
        construct_b649_candidate_set_hybrid_diversity_v1,
    ):
        assert constructor(pool, 5) != pool[:5]


def test_metadata_is_complete_and_immutable() -> None:
    expected_ids = {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
    }
    assert set(CONSTRUCTOR_METADATA) == expected_ids
    assert set(CONSTRUCTORS) == expected_ids
    for metadata in CONSTRUCTOR_METADATA.values():
        assert metadata.VERSION == "v1"
        assert metadata.SUPPORTED_TICKET_COUNTS == SUPPORTED_TICKET_COUNTS
        assert metadata.LOTTERY_TYPE == "BIG_LOTTO"
        assert metadata.PICK_COUNT == 6
        assert metadata.NUMBER_DOMAIN == (1, 49)
        assert metadata.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
        assert metadata.OUTPUT_ORDER == "GREEDY_SELECTION_ORDER"
    with pytest.raises(FrozenInstanceError):
        B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA.VERSION = "v2"  # type: ignore[misc]
    with pytest.raises(TypeError):
        CONSTRUCTOR_METADATA["new"] = B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA  # type: ignore[index]


def test_each_metadata_object_has_its_expected_objective() -> None:
    assert "MAX_OVERLAP, TOTAL_OVERLAP, ORIGINAL_RANK" in (
        B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA.SELECTION_OBJECTIVE
    )
    assert "EXPOSURE_VECTOR_AFTER_ADDING_CANDIDATE, ORIGINAL_RANK" in (
        B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1_METADATA.SELECTION_OBJECTIVE
    )
    assert (
        "MAX_OVERLAP, EXPOSURE_VECTOR_AFTER_ADDING_CANDIDATE, TOTAL_OVERLAP, ORIGINAL_RANK"
        in B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1_METADATA.SELECTION_OBJECTIVE
    )


def test_exposure_vector_helper_observation_matches_the_constructor_result() -> None:
    portfolio = construct_b649_candidate_set_exposure_balanced_v1(_POOL, 10)
    vector = _exposure_vector(portfolio)
    assert len(vector) == 49
    assert sum(vector) == 60
