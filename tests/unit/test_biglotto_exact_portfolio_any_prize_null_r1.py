"""Independent exactness checks for the Big Lotto portfolio null engine."""

from __future__ import annotations

from functools import cache
from itertools import combinations
from math import comb

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import LOTTERY_PRIZE_EVALUATOR
from lottolab.research.biglotto_exact_portfolio_any_prize_null_r1 import (
    TOTAL_OUTCOME_COUNT,
    TOTAL_SEVEN_SET_COUNT,
    BigLottoExactPortfolioNullContractError,
    ExactPortfolioAnyPrizeProbability,
    exact_portfolio_any_prize_probability,
    exact_seven_set_ticket_triple_union_count,
)

TICKET_A = (1, 2, 3, 4, 5, 6)


@cache
def _evaluate(
    portfolio: tuple[tuple[int, ...], ...],
) -> ExactPortfolioAnyPrizeProbability:
    return exact_portfolio_any_prize_probability(portfolio)


def _outcome_for_signature(
    main_hits: int,
    special_hit: bool,
) -> tuple[tuple[int, ...], int]:
    outside_ticket = tuple(range(7, 50))
    winning_main = tuple(sorted((*TICKET_A[:main_hits], *outside_ticket[: 6 - main_hits])))
    winning_special = TICKET_A[main_hits] if special_hit else outside_ticket[6 - main_hits]
    return winning_main, winning_special


@pytest.mark.parametrize(
    ("main_hits", "special_hit"),
    [(main_hits, special_hit) for main_hits in range(7) for special_hit in (False, True)][
        :-1
    ],
)
def test_seven_set_threshold_is_equivalent_to_canonical_evaluator_for_all_signatures(
    main_hits: int,
    special_hit: bool,
) -> None:
    winning_main, winning_special = _outcome_for_signature(main_hits, special_hit)

    evaluated = LOTTERY_PRIZE_EVALUATOR.evaluate(
        lottery_type=LotteryType.BIG_LOTTO,
        predicted_main_numbers=TICKET_A,
        predicted_special_number=None,
        winning_main_numbers=winning_main,
        winning_special_number=winning_special,
    )

    assert evaluated.zone1_hits == main_hits
    assert evaluated.zone2_hit is special_hit
    assert evaluated.is_winner is (main_hits + int(special_hit) >= 3)


def _single_ticket_original_outcome_oracle() -> int:
    """Count directly in the original (main set, designated special) space."""

    favorable = 0
    for main_hits in range(7):
        main_set_count = comb(6, main_hits) * comb(43, 6 - main_hits)
        for special_hit in (False, True):
            if main_hits + int(special_hit) > 6:
                continue
            if main_hits + int(special_hit) < 3:
                continue
            special_count = (6 - main_hits) if special_hit else (37 + main_hits)
            favorable += main_set_count * special_count
    return favorable


def test_single_ticket_matches_original_outcome_combinatorial_oracle() -> None:
    actual = _evaluate((TICKET_A,))
    oracle_count = _single_ticket_original_outcome_oracle()

    assert TOTAL_OUTCOME_COUNT == 601_304_088
    assert TOTAL_SEVEN_SET_COUNT == 85_900_584
    assert oracle_count == 18_611_432
    assert actual.favorable_outcome_count == oracle_count
    assert actual.exact_probability.numerator == 7_729
    assert actual.exact_probability.denominator == 249_711
    assert actual.canonical_dict()["FAVORABLE_OUTCOME_COUNT"] == oracle_count


def _pair_with_overlap(overlap: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    ticket_b = tuple((*TICKET_A[:overlap], *range(7, 13 - overlap)))
    assert len(ticket_b) == 6
    return TICKET_A, ticket_b


def _pair_seven_set_oracle(overlap: int) -> int:
    """Independent category sum for two tickets with intersection size ``overlap``."""

    ticket_only = 6 - overlap
    outside_both = 49 - (12 - overlap)
    single_ticket = sum(comb(6, hits) * comb(43, 7 - hits) for hits in range(3, 7))
    intersection = 0
    for common in range(overlap + 1):
        for a_only in range(ticket_only + 1):
            for b_only in range(ticket_only + 1):
                outside = 7 - common - a_only - b_only
                if not 0 <= outside <= outside_both:
                    continue
                if common + a_only < 3 or common + b_only < 3:
                    continue
                intersection += (
                    comb(overlap, common)
                    * comb(ticket_only, a_only)
                    * comb(ticket_only, b_only)
                    * comb(outside_both, outside)
                )
    return 2 * single_ticket - intersection


@pytest.mark.parametrize("overlap", [0, 2, 5])
def test_two_ticket_overlap_classes_match_independent_category_oracle(
    overlap: int,
) -> None:
    portfolio = _pair_with_overlap(overlap)
    actual = _evaluate(portfolio)

    assert actual.favorable_seven_set_count == _pair_seven_set_oracle(overlap)
    assert actual.favorable_outcome_count == 7 * _pair_seven_set_oracle(overlap)


def test_duplicate_idempotence_and_portfolio_order_invariance() -> None:
    ticket_a, ticket_b = _pair_with_overlap(2)

    single = _evaluate((ticket_a,))
    duplicated = _evaluate((ticket_a, ticket_a))
    forward = _evaluate((ticket_a, ticket_b))
    reverse = _evaluate((ticket_b, ticket_a))

    assert duplicated.favorable_outcome_count == single.favorable_outcome_count
    assert duplicated.exact_probability == single.exact_probability
    assert duplicated.input_ticket_count == 2
    assert duplicated.unique_ticket_count == 1
    assert reverse.favorable_outcome_count == forward.favorable_outcome_count
    assert reverse.exact_probability == forward.exact_probability


@pytest.mark.parametrize(
    ("pool_size", "portfolio"),
    [
        (12, ((1, 2, 3, 4, 5, 6),)),
        (13, ((1, 2, 3, 4, 5, 6), (1, 2, 7, 8, 9, 10))),
        (
            14,
            (
                (1, 2, 3, 4, 5, 6),
                (1, 2, 3, 7, 8, 9),
                (1, 2, 3, 10, 11, 12),
            ),
        ),
    ],
)
def test_production_counter_matches_exhaustive_reduced_domain_oracle(
    pool_size: int,
    portfolio: tuple[tuple[int, ...], ...],
) -> None:
    exhaustive = sum(
        any(len(set(seven_set) & set(ticket)) >= 3 for ticket in portfolio)
        for seven_set in combinations(range(1, pool_size + 1), 7)
    )

    assert exact_seven_set_ticket_triple_union_count(pool_size, portfolio) == exhaustive


@pytest.mark.parametrize(
    ("portfolio", "message"),
    [
        (((1, 2, 3, 4, 5),), "exactly 6"),
        (((0, 2, 3, 4, 5, 6),), "between 1 and 49"),
        (((1, 2, 3, 4, 5, 50),), "between 1 and 49"),
        (((1, 2, 3, 4, 5, 5),), "distinct"),
        (((2, 1, 3, 4, 5, 6),), "ascending"),
        (((True, 2, 3, 4, 5, 6),), "built-in integers"),
    ],
)
def test_invalid_native_ticket_contract_fails_closed(
    portfolio: tuple[tuple[int, ...], ...],
    message: str,
) -> None:
    with pytest.raises(BigLottoExactPortfolioNullContractError, match=message):
        exact_portfolio_any_prize_probability(portfolio)


def test_non_tuple_portfolio_and_ticket_fail_closed() -> None:
    with pytest.raises(BigLottoExactPortfolioNullContractError, match="portfolio"):
        exact_portfolio_any_prize_probability([TICKET_A])  # type: ignore[arg-type]
    with pytest.raises(BigLottoExactPortfolioNullContractError, match="ticket"):
        exact_portfolio_any_prize_probability((list(TICKET_A),))  # type: ignore[arg-type]


def test_empty_portfolio_has_zero_exact_probability() -> None:
    result = _evaluate(())

    assert result.favorable_outcome_count == 0
    assert result.exact_probability.numerator == 0
    assert result.exact_probability.denominator == 1
    assert result.unique_ticket_count == 0
