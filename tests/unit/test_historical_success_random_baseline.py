"""Exact-mathematics tests for the official-six-number IID baseline."""

from __future__ import annotations

import dataclasses
from fractions import Fraction

import pytest

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessCriterion,
)
from lottolab.application.historical_success_random_baseline import (
    INTERPRETATION_CAVEAT,
    LEGAL_TICKET_COUNT,
    NOMINAL_TICKET_COUNT_EQUIVALENT,
    RANDOM_BASELINE_POLICY_VERSION,
    HistoricalSuccessExactRational,
    HistoricalSuccessRandomBaselineCellIdentity,
    HistoricalSuccessRandomBaselineContractError,
    HistoricalSuccessRandomBaselineNotReadyReason,
    HistoricalSuccessRandomBaselineObservationOperand,
    HistoricalSuccessRandomBaselineReadiness,
    HistoricalSuccessRandomBaselineTicketOperand,
    binomial_upper_tail,
    criterion_success_ticket_count,
    evaluate_historical_success_random_baseline,
    portfolio_success_probability,
    render_exact_decimal_18,
)
from lottolab.domain.strategy_success_evaluation import WindowKind


@pytest.mark.parametrize(
    ("criterion", "expected_count"),
    [
        (HistoricalPrefixSuccessCriterion.M3_PLUS, 260_624),
        (HistoricalPrefixSuccessCriterion.M4_PLUS, 13_804),
        (HistoricalPrefixSuccessCriterion.M5_PLUS, 259),
        (HistoricalPrefixSuccessCriterion.M6, 1),
        (HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL, 190_056),
        (HistoricalPrefixSuccessCriterion.M3_PLUS_SPECIAL, 17_856),
        (HistoricalPrefixSuccessCriterion.M4_PLUS_SPECIAL, 636),
        (HistoricalPrefixSuccessCriterion.M5_PLUS_SPECIAL, 6),
    ],
)
def test_all_official_criterion_counts_are_exact(
    criterion: HistoricalPrefixSuccessCriterion,
    expected_count: int,
) -> None:
    assert LEGAL_TICKET_COUNT == 13_983_816
    assert criterion_success_ticket_count(criterion) == expected_count
    probability = portfolio_success_probability(criterion, 1)
    assert probability.as_fraction() == Fraction(expected_count, LEGAL_TICKET_COUNT)


@pytest.mark.parametrize("prefix_count", [1, 2, 5, 10, 15, 20])
def test_iid_with_replacement_portfolio_probability_is_exact(prefix_count: int) -> None:
    criterion = HistoricalPrefixSuccessCriterion.M4_PLUS_SPECIAL
    successes = criterion_success_ticket_count(criterion)
    expected = 1 - Fraction(LEGAL_TICKET_COUNT - successes, LEGAL_TICKET_COUNT) ** prefix_count

    actual = portfolio_success_probability(criterion, prefix_count)

    assert actual.as_fraction() == expected
    assert actual == HistoricalSuccessExactRational(
        expected.numerator,
        expected.denominator,
    )


def test_exact_rationals_are_reduced_and_binary_float_is_not_an_authoritative_type() -> None:
    reduced = HistoricalSuccessExactRational.from_fraction(Fraction(6, 8))

    assert reduced == HistoricalSuccessExactRational(3, 4)
    assert reduced.canonical_dict() == {"denominator": 4, "numerator": 3}
    with pytest.raises(HistoricalSuccessRandomBaselineContractError):
        HistoricalSuccessExactRational(6, 8)
    with pytest.raises(HistoricalSuccessRandomBaselineContractError):
        HistoricalSuccessExactRational(1.0, 2)  # type: ignore[arg-type]


def test_decimal_renderer_is_fixed_18_place_half_even() -> None:
    assert render_exact_decimal_18(HistoricalSuccessExactRational(1, 2)) == (
        "0.500000000000000000"
    )
    assert render_exact_decimal_18(
        HistoricalSuccessExactRational(1, 2_000_000_000_000_000_000)
    ) == "0.000000000000000000"
    assert render_exact_decimal_18(
        HistoricalSuccessExactRational(3, 2_000_000_000_000_000_000)
    ) == "0.000000000000000002"
    assert render_exact_decimal_18(
        HistoricalSuccessExactRational(
            15 * 10**81 - 1,
            10**100,
        )
    ) == "0.000000000000000001"


def test_binomial_upper_tail_handles_boundaries_and_small_brute_force_cases() -> None:
    half = HistoricalSuccessExactRational(1, 2)

    assert binomial_upper_tail(5, 0, half) == HistoricalSuccessExactRational(1, 1)
    assert binomial_upper_tail(5, 5, half) == HistoricalSuccessExactRational(1, 32)
    assert binomial_upper_tail(3, 2, half) == HistoricalSuccessExactRational(1, 2)
    assert binomial_upper_tail(4, 3, half) == HistoricalSuccessExactRational(5, 16)


def _cell(
    *,
    criterion: HistoricalPrefixSuccessCriterion = HistoricalPrefixSuccessCriterion.M3_PLUS,
    prefix_count: int = 2,
) -> HistoricalSuccessRandomBaselineCellIdentity:
    return HistoricalSuccessRandomBaselineCellIdentity(
        policy_version=RANDOM_BASELINE_POLICY_VERSION,
        import_identity_sha256="a" * 64,
        dataset_sha256="b" * 64,
        source_artifact_sha256="c" * 64,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        window_kind=WindowKind.FULL_HISTORY,
        window_policy_version="STRATEGY_SUCCESS_WINDOWS_V1",
        prefix_count=prefix_count,
        criterion=criterion,
    )


def _ticket(
    main_numbers: tuple[int, ...],
    *,
    main_hits: int,
    legacy_special_hit: bool = False,
) -> HistoricalSuccessRandomBaselineTicketOperand:
    return HistoricalSuccessRandomBaselineTicketOperand(
        main_numbers=main_numbers,
        persisted_main_hit_count=main_hits,
        persisted_legacy_special_hit=legacy_special_hit,
    )


def _observation(
    tickets: tuple[HistoricalSuccessRandomBaselineTicketOperand, ...],
    *,
    target_main_numbers: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
    target_special_number: int = 7,
) -> HistoricalSuccessRandomBaselineObservationOperand:
    return HistoricalSuccessRandomBaselineObservationOperand(
        target_main_numbers=target_main_numbers,
        target_special_number=target_special_number,
        tickets=tickets,
    )


def _evaluate(
    *,
    cell: HistoricalSuccessRandomBaselineCellIdentity,
    observations: tuple[HistoricalSuccessRandomBaselineObservationOperand, ...],
    complete: bool = True,
    eligible: int | None = None,
    excluded: int = 0,
    legacy_successes: int = 0,
):
    return evaluate_historical_success_random_baseline(
        cell=cell,
        observations=observations,
        window_complete=complete,
        eligible_observation_count=(
            len(observations) - excluded if eligible is None else eligible
        ),
        excluded_observation_count=excluded,
        legacy_window_success_count=legacy_successes,
    )


def test_official_special_uses_ticket_main_numbers_and_ignores_legacy_special() -> None:
    cell = _cell(
        criterion=HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL,
        prefix_count=1,
    )
    official_hit = _ticket(
        (1, 2, 7, 10, 11, 12),
        main_hits=2,
        legacy_special_hit=False,
    )
    observation = _observation((official_hit,))

    result = _evaluate(
        cell=cell,
        observations=(observation,),
        legacy_successes=0,
    )
    flipped_legacy = _evaluate(
        cell=cell,
        observations=(
            _observation(
                (
                    dataclasses.replace(
                        official_hit,
                        persisted_legacy_special_hit=True,
                    ),
                )
            ),
        ),
        legacy_successes=1,
    )

    assert result.readiness is HistoricalSuccessRandomBaselineReadiness.READY
    assert result.observed_success_count == 1
    assert flipped_legacy.observed_success_count == result.observed_success_count
    assert flipped_legacy.portfolio_success_probability == result.portfolio_success_probability


def test_duplicates_are_disclosed_per_observation_without_changing_k() -> None:
    duplicate = _ticket((1, 2, 3, 10, 11, 12), main_hits=3)
    result = _evaluate(
        cell=_cell(prefix_count=2),
        observations=(
            _observation((duplicate, duplicate)),
            _observation(
                (
                    duplicate,
                    _ticket((8, 9, 10, 11, 12, 13), main_hits=0),
                )
            ),
        ),
        legacy_successes=2,
    )

    assert result.readiness is HistoricalSuccessRandomBaselineReadiness.READY
    assert result.observed_ticket_position_count == 4
    assert result.observed_distinct_ticket_count == 3
    assert result.observed_duplicate_ticket_count == 1
    assert result.observation_count_with_duplicates == 1
    assert result.portfolio_success_probability == portfolio_success_probability(
        HistoricalPrefixSuccessCriterion.M3_PLUS,
        2,
    )


@pytest.mark.parametrize(
    "observation",
    [
        _observation(
            (
                _ticket((1, 2, 3, 10, 11, 12), main_hits=2),
                _ticket((8, 9, 10, 11, 12, 13), main_hits=0),
            )
        ),
        _observation(
            (
                _ticket((1, 1, 3, 10, 11, 12), main_hits=2),
                _ticket((8, 9, 10, 11, 12, 13), main_hits=0),
            )
        ),
        _observation(
            (
                _ticket((1, 2, 3, 4, 5, 6), main_hits=6),
                _ticket((8, 9, 10, 11, 12, 13), main_hits=0),
            ),
            target_special_number=6,
        ),
    ],
)
def test_invalid_raw_operands_stored_main_mismatch_and_official_six_plus_special_fail_closed(
    observation: HistoricalSuccessRandomBaselineObservationOperand,
) -> None:
    result = _evaluate(
        cell=_cell(),
        observations=(observation,),
        legacy_successes=0,
    )

    assert result.readiness is HistoricalSuccessRandomBaselineReadiness.NOT_READY
    assert result.reason_codes == (
        HistoricalSuccessRandomBaselineNotReadyReason.SOURCE_TICKET_SEMANTICS_CONFLICT,
    )
    assert result.observed_success_count is None
    assert result.upper_tail_probability is None


def test_main_only_recomputation_must_equal_existing_window_success_count() -> None:
    successful = _ticket((1, 2, 3, 10, 11, 12), main_hits=3)

    result = _evaluate(
        cell=_cell(prefix_count=1),
        observations=(_observation((successful,)),),
        legacy_successes=0,
    )

    assert result.readiness is HistoricalSuccessRandomBaselineReadiness.NOT_READY
    assert result.reason_codes == (
        HistoricalSuccessRandomBaselineNotReadyReason.SOURCE_TICKET_SEMANTICS_CONFLICT,
    )


@pytest.mark.parametrize(
    ("observations", "complete", "eligible", "excluded", "expected_reasons"),
    [
        (
            (),
            False,
            0,
            0,
            (HistoricalSuccessRandomBaselineNotReadyReason.NO_OBSERVATIONS,),
        ),
        (
            (
                _observation(
                    (
                        _ticket((8, 9, 10, 11, 12, 13), main_hits=0),
                        _ticket((14, 15, 16, 17, 18, 19), main_hits=0),
                    )
                ),
            ),
            False,
            1,
            0,
            (HistoricalSuccessRandomBaselineNotReadyReason.WINDOW_INCOMPLETE,),
        ),
        (
            (
                _observation(
                    (
                        _ticket((8, 9, 10, 11, 12, 13), main_hits=0),
                        _ticket((14, 15, 16, 17, 18, 19), main_hits=0),
                    )
                ),
            ),
            True,
            0,
            1,
            (HistoricalSuccessRandomBaselineNotReadyReason.EXCLUDED_OBSERVATIONS,),
        ),
    ],
)
def test_readiness_is_closed_for_empty_incomplete_and_excluded_windows(
    observations: tuple[HistoricalSuccessRandomBaselineObservationOperand, ...],
    complete: bool,
    eligible: int,
    excluded: int,
    expected_reasons: tuple[HistoricalSuccessRandomBaselineNotReadyReason, ...],
) -> None:
    result = _evaluate(
        cell=_cell(),
        observations=observations,
        complete=complete,
        eligible=eligible,
        excluded=excluded,
    )

    assert result.readiness is HistoricalSuccessRandomBaselineReadiness.NOT_READY
    assert result.reason_codes == expected_reasons


def test_ready_result_has_exact_expectation_tail_caveat_and_canonical_representation() -> None:
    successful = _ticket((1, 2, 3, 10, 11, 12), main_hits=3)
    failing = _ticket((8, 9, 10, 11, 12, 13), main_hits=0)
    cell = _cell(prefix_count=1)
    result = _evaluate(
        cell=cell,
        observations=(
            _observation((successful,)),
            _observation((failing,)),
        ),
        legacy_successes=1,
    )
    probability = portfolio_success_probability(cell.criterion, cell.prefix_count)

    assert result.expected_successes is not None
    assert result.expected_successes.as_fraction() == 2 * probability.as_fraction()
    assert result.upper_tail_probability == binomial_upper_tail(2, 1, probability)
    assert result.interpretation_caveat == INTERPRETATION_CAVEAT
    assert result.ticket_count_interpretation == NOMINAL_TICKET_COUNT_EQUIVALENT
    assert "monetary cost" not in result.ticket_count_interpretation
    assert result == dataclasses.replace(result)
    assert result.canonical_json() == dataclasses.replace(result).canonical_json()


def test_contradictory_readiness_and_window_counts_are_rejected() -> None:
    failing = _ticket((8, 9, 10, 11, 12, 13), main_hits=0)
    result = _evaluate(
        cell=_cell(prefix_count=1),
        observations=(_observation((failing,)),),
        legacy_successes=0,
    )

    with pytest.raises(HistoricalSuccessRandomBaselineContractError):
        dataclasses.replace(
            result,
            readiness=HistoricalSuccessRandomBaselineReadiness.NOT_READY,
        )
    with pytest.raises(HistoricalSuccessRandomBaselineContractError):
        dataclasses.replace(
            result,
            expected_successes=HistoricalSuccessExactRational(1, 1),
        )
    with pytest.raises(HistoricalSuccessRandomBaselineContractError):
        evaluate_historical_success_random_baseline(
            cell=_cell(prefix_count=1),
            observations=(_observation((failing,)),),
            window_complete=True,
            eligible_observation_count=0,
            excluded_observation_count=0,
            legacy_window_success_count=0,
        )
