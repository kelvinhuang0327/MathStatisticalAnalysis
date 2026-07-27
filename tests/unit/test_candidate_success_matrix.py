from __future__ import annotations

import dataclasses
from fractions import Fraction

import pytest

from lottolab.application.candidate_success_matrix import (
    BaselineRelation,
    CandidateCoverageCriterion,
    CandidateSuccessMatrix,
    CandidateSuccessMatrixCell,
    CandidateSuccessMatrixInputError,
    ExactRational,
    candidate_random_baseline,
    evaluate_candidate_success_matrix,
    supported_criteria,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_evidence import (
    DONOR_SEMANTIC_REFERENCES,
    CandidateCoverageOutcome,
    CandidateSourceArtifactIdentity,
    DuplicateHandlingPolicy,
    OrderedCandidateObservation,
    PowerLottoZone2Operand,
    evaluate_candidate_coverage,
)
from lottolab.domain.strategy_success_evaluation import (
    WindowEvaluationStatus,
    WindowKind,
)
from lottolab.domain.strategy_success_measurement import (
    DEFAULT_WINDOW_POLICY_VERSION,
    MeasurementMode,
)

_SOURCE = CandidateSourceArtifactIdentity(
    repository="synthetic/golden",
    commit_oid="b" * 40,
    path="fixtures/ordered-candidates.json",
    sha256="a" * 64,
)


def _big(
    target: int,
    *,
    strategy_id: str = "golden-big",
    emitted: tuple[int, ...] = (7, 1, 7, 2, 3, 4, 5),
) -> OrderedCandidateObservation:
    return OrderedCandidateObservation(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id=strategy_id,
        strategy_version="v1",
        replicate=1,
        target_draw=str(target),
        history_cutoff=str(target - 1),
        emitted_main_numbers=emitted,
        duplicate_handling_policy=DuplicateHandlingPolicy.PRESERVE_FIRST_OCCURRENCE,
        predicted_big_lotto_special_operand=9,
        predicted_power_lotto_zone2_operand=None,
        actual_main_numbers=(1, 2, 3, 4, 5, 6),
        actual_special_or_zone2=7,
        source_artifact_identity=_SOURCE,
        window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
    )


def _daily(
    target: int,
    *,
    strategy_id: str = "golden-daily",
    emitted: tuple[int, ...] = (9, 9, 8, 7, 6, 5),
) -> OrderedCandidateObservation:
    return OrderedCandidateObservation(
        lottery_type=LotteryType.DAILY_539,
        strategy_id=strategy_id,
        strategy_version="v1",
        replicate=1,
        target_draw=str(target),
        history_cutoff=str(target - 1),
        emitted_main_numbers=emitted,
        duplicate_handling_policy=DuplicateHandlingPolicy.PRESERVE_FIRST_OCCURRENCE,
        predicted_big_lotto_special_operand=None,
        predicted_power_lotto_zone2_operand=None,
        actual_main_numbers=(5, 6, 7, 8, 9),
        actual_special_or_zone2=None,
        source_artifact_identity=_SOURCE,
        window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
    )


def _power(
    target: int,
    *,
    strategy_id: str = "golden-power",
    emitted: tuple[int, ...] = (10, 10, 11, 12, 13, 14, 15),
    zone2: PowerLottoZone2Operand | None = None,
) -> OrderedCandidateObservation:
    return OrderedCandidateObservation(
        lottery_type=LotteryType.POWER_LOTTO,
        strategy_id=strategy_id,
        strategy_version="v1",
        replicate=1,
        target_draw=str(target),
        history_cutoff=str(target - 1),
        emitted_main_numbers=emitted,
        duplicate_handling_policy=DuplicateHandlingPolicy.PRESERVE_FIRST_OCCURRENCE,
        predicted_big_lotto_special_operand=None,
        predicted_power_lotto_zone2_operand=(
            PowerLottoZone2Operand.present(3) if zone2 is None else zone2
        ),
        actual_main_numbers=(10, 11, 12, 20, 21, 22),
        actual_special_or_zone2=3,
        source_artifact_identity=_SOURCE,
        window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
    )


def _cell(
    matrix: CandidateSuccessMatrix,
    *,
    kind: WindowKind,
    requested_k: int,
    criterion: CandidateCoverageCriterion,
) -> CandidateSuccessMatrixCell:
    return next(
        cell
        for cell in matrix.cells
        if cell.window_kind is kind
        and cell.requested_k == requested_k
        and cell.criterion is criterion
    )


@pytest.mark.parametrize(
    ("observation", "expected_first", "expected_max"),
    [
        (_big(2), (7,), (7, 1, 2, 3, 4, 5)),
        (_daily(2), (9,), (9, 8, 7, 6, 5)),
        (_power(2), (10,), (10, 11, 12, 13, 14, 15)),
    ],
)
def test_candidate_k_preserves_emission_order_and_removes_later_duplicates(
    observation: OrderedCandidateObservation,
    expected_first: tuple[int, ...],
    expected_max: tuple[int, ...],
) -> None:
    maximum = 5 if observation.lottery_type is LotteryType.DAILY_539 else 6

    first = observation.select_candidate_k(1)
    last = observation.select_candidate_k(maximum)

    assert first.selected_main_numbers == expected_first
    assert last.selected_main_numbers == expected_max
    assert first.requested_k == first.effective_unique_k == 1
    assert last.requested_k == last.effective_unique_k == maximum
    assert not hasattr(last, "ticket_count")
    assert not hasattr(last, "max_bet_index")


def test_requested_k_and_effective_unique_k_remain_separate() -> None:
    observation = _big(2, emitted=(1, 1, 2))

    selection = observation.select_candidate_k(6)

    assert selection.requested_k == 6
    assert selection.effective_unique_k == 2
    assert selection.selected_main_numbers == (1, 2)


def test_big_lotto_golden_special_condition_is_candidate_coverage_only() -> None:
    observation = _big(2)

    k1 = evaluate_candidate_coverage(observation, 1)
    k6 = evaluate_candidate_coverage(observation, 6)

    assert (k1.main_hits, k1.special_hit) == (0, True)
    assert (k6.main_hits, k6.special_hit) == (5, True)
    matrix = evaluate_candidate_success_matrix((observation,))
    special = _cell(
        matrix,
        kind=WindowKind.FULL_HISTORY,
        requested_k=1,
        criterion=CandidateCoverageCriterion.SPECIAL_HIT,
    )
    compound = _cell(
        matrix,
        kind=WindowKind.FULL_HISTORY,
        requested_k=6,
        criterion=CandidateCoverageCriterion.M2_PLUS_SPECIAL,
    )
    assert special.success_rate.numerator == special.success_rate.denominator == 1
    assert compound.success_rate.numerator == compound.success_rate.denominator == 1
    assert matrix.measurement_mode is MeasurementMode.CANDIDATE_COVERAGE
    assert not hasattr(compound, "official_prize_tier_id")


def test_power_lotto_zone2_hit_and_explicit_missing_are_distinct() -> None:
    present = _power(2)
    missing = _power(3, zone2=PowerLottoZone2Operand.explicitly_missing())

    assert evaluate_candidate_coverage(present, 1).zone2_hit is True
    assert evaluate_candidate_coverage(missing, 1).zone2_hit is None

    matrix = evaluate_candidate_success_matrix((present, missing))
    zone2 = _cell(
        matrix,
        kind=WindowKind.FULL_HISTORY,
        requested_k=1,
        criterion=CandidateCoverageCriterion.ZONE2_HIT,
    )
    main = _cell(
        matrix,
        kind=WindowKind.FULL_HISTORY,
        requested_k=1,
        criterion=CandidateCoverageCriterion.M1_PLUS,
    )
    assert (zone2.eligible_observation_count, zone2.excluded_observation_count) == (1, 1)
    assert zone2.success_rate.numerator == zone2.success_rate.denominator == 1
    assert (main.eligible_observation_count, main.excluded_observation_count) == (2, 0)


def test_only_explicit_missing_power_zone2_is_accepted() -> None:
    values = _power(2)

    with pytest.raises(ValueError, match="requires a present or explicitly-missing"):
        dataclasses.replace(values, predicted_power_lotto_zone2_operand=None)


def test_all_three_lotteries_have_complete_game_specific_criterion_sets() -> None:
    big = evaluate_candidate_success_matrix((_big(2),))
    daily = evaluate_candidate_success_matrix((_daily(2),))
    power = evaluate_candidate_success_matrix((_power(2),))

    assert big.requested_candidate_ks == (1, 2, 3, 4, 5, 6)
    assert daily.requested_candidate_ks == (1, 2, 3, 4, 5)
    assert power.requested_candidate_ks == (1, 2, 3, 4, 5, 6)
    assert CandidateCoverageCriterion.SPECIAL_HIT in big.criteria
    assert CandidateCoverageCriterion.M6_PLUS_SPECIAL in big.criteria
    assert supported_criteria(LotteryType.DAILY_539) == (
        CandidateCoverageCriterion.M1_PLUS,
        CandidateCoverageCriterion.M2_PLUS,
        CandidateCoverageCriterion.M3_PLUS,
        CandidateCoverageCriterion.M4_PLUS,
        CandidateCoverageCriterion.M5_PLUS,
    )
    assert CandidateCoverageCriterion.ZONE2_HIT in power.criteria
    assert CandidateCoverageCriterion.M6_PLUS_ZONE2 in power.criteria
    assert len(big.cells) == 4 * 6 * len(big.criteria)
    assert len(daily.cells) == 4 * 5 * len(daily.criteria)
    assert len(power.cells) == 4 * 6 * len(power.criteria)


def test_full_750_300_50_cardinality_and_nested_roles_are_exact() -> None:
    observations = tuple(_big(index) for index in range(2, 762))

    matrix = evaluate_candidate_success_matrix(observations)
    cells = {
        kind: _cell(
            matrix,
            kind=kind,
            requested_k=1,
            criterion=CandidateCoverageCriterion.M1_PLUS,
        )
        for kind in WindowKind
    }

    assert cells[WindowKind.FULL_HISTORY].source_observation_count == 760
    assert cells[WindowKind.LONG].source_observation_count == 750
    assert cells[WindowKind.MEDIUM].source_observation_count == 300
    assert cells[WindowKind.SHORT].source_observation_count == 50
    assert all(
        cell.evaluation_status is WindowEvaluationStatus.COMPLETE for cell in cells.values()
    )
    assert all(cell.nested_windows_independent is False for cell in cells.values())
    assert cells[WindowKind.LONG].first_target_draw == "12"
    assert cells[WindowKind.SHORT].first_target_draw == "712"
    assert cells[WindowKind.SHORT].last_target_draw == "761"


def test_insufficient_windows_retain_counts_and_explicit_status() -> None:
    observations = tuple(_daily(index) for index in range(2, 62))
    matrix = evaluate_candidate_success_matrix(observations)

    full = _cell(
        matrix,
        kind=WindowKind.FULL_HISTORY,
        requested_k=5,
        criterion=CandidateCoverageCriterion.M5_PLUS,
    )
    long = _cell(
        matrix,
        kind=WindowKind.LONG,
        requested_k=5,
        criterion=CandidateCoverageCriterion.M5_PLUS,
    )
    medium = _cell(
        matrix,
        kind=WindowKind.MEDIUM,
        requested_k=5,
        criterion=CandidateCoverageCriterion.M5_PLUS,
    )
    short = _cell(
        matrix,
        kind=WindowKind.SHORT,
        requested_k=5,
        criterion=CandidateCoverageCriterion.M5_PLUS,
    )

    assert full.evaluation_status is WindowEvaluationStatus.COMPLETE
    assert long.evaluation_status is WindowEvaluationStatus.INSUFFICIENT_DRAWS
    assert medium.evaluation_status is WindowEvaluationStatus.INSUFFICIENT_DRAWS
    assert short.evaluation_status is WindowEvaluationStatus.COMPLETE
    assert (long.success_rate.numerator, long.success_rate.denominator) == (60, 60)
    assert short.source_observation_count == 50


def test_random_baselines_are_exact_and_game_specific() -> None:
    big_main = candidate_random_baseline(
        lottery_type=LotteryType.BIG_LOTTO,
        effective_unique_k=1,
        criterion=CandidateCoverageCriterion.M1_PLUS,
    )
    big_special = candidate_random_baseline(
        lottery_type=LotteryType.BIG_LOTTO,
        effective_unique_k=1,
        criterion=CandidateCoverageCriterion.SPECIAL_HIT,
    )
    daily_main = candidate_random_baseline(
        lottery_type=LotteryType.DAILY_539,
        effective_unique_k=1,
        criterion=CandidateCoverageCriterion.M1_PLUS,
    )
    power_zone2 = candidate_random_baseline(
        lottery_type=LotteryType.POWER_LOTTO,
        effective_unique_k=1,
        criterion=CandidateCoverageCriterion.ZONE2_HIT,
    )
    power_compound = candidate_random_baseline(
        lottery_type=LotteryType.POWER_LOTTO,
        effective_unique_k=1,
        criterion=CandidateCoverageCriterion.M1_PLUS_ZONE2,
    )

    assert big_main == ExactRational(6, 49)
    assert big_special == ExactRational(1, 49)
    assert daily_main == ExactRational(5, 39)
    assert power_zone2 == ExactRational(1, 8)
    assert power_compound == ExactRational(3, 152)
    assert power_compound is not None
    assert power_compound.as_fraction() == Fraction(6, 38) * Fraction(1, 8)


def test_baseline_relation_serialized_vocabulary_is_exact_and_neutral() -> None:
    members = tuple(BaselineRelation)
    vocabulary = tuple(relation.value for relation in members)

    assert members == (
        BaselineRelation.ABOVE,
        BaselineRelation.EQUAL,
        BaselineRelation.BELOW,
        BaselineRelation.NOT_COMPARABLE,
        BaselineRelation.INSUFFICIENT_DATA,
    )
    assert vocabulary == (
        "ABOVE_RANDOM",
        "EQUAL_RANDOM",
        "BELOW_RANDOM",
        "NOT_COMPARABLE",
        "INSUFFICIENT_DATA",
    )
    assert len(vocabulary) == 5
    assert {"ABOVE", "EQUAL", "BELOW"}.isdisjoint(vocabulary)
    assert {
        "REJECTED",
        "FAIL",
        "INVALID",
        "UNTRUSTWORTHY",
        "DISQUALIFIED",
        "ELIMINATED",
    }.isdisjoint(vocabulary)


def test_matrix_baseline_relation_uses_exact_rationals() -> None:
    matrix = evaluate_candidate_success_matrix((_daily(2),))
    cell = _cell(
        matrix,
        kind=WindowKind.FULL_HISTORY,
        requested_k=1,
        criterion=CandidateCoverageCriterion.M1_PLUS,
    )

    assert cell.success_rate.as_fraction() == Fraction(1, 1)
    assert cell.random_baseline == ExactRational(5, 39)
    assert cell.observed_minus_baseline is BaselineRelation.ABOVE


def test_below_random_relation_is_descriptive_only() -> None:
    matrix = evaluate_candidate_success_matrix(
        (_daily(2, emitted=(1, 2, 3, 4, 10)),)
    )
    cell = _cell(
        matrix,
        kind=WindowKind.FULL_HISTORY,
        requested_k=1,
        criterion=CandidateCoverageCriterion.M1_PLUS,
    )

    assert cell.success_rate.as_fraction() == Fraction(0, 1)
    assert cell.random_baseline == ExactRational(5, 39)
    assert cell.observed_minus_baseline is BaselineRelation.BELOW
    assert cell.canonical_dict()["observed_minus_baseline"] == "BELOW_RANDOM"
    assert cell.evaluation_status is WindowEvaluationStatus.COMPLETE
    assert cell in matrix.cells


@pytest.mark.parametrize(
    "observations",
    [
        (_big(2), _big(3, strategy_id="other")),
        (_big(2), _daily(3)),
        (_big(2), _big(2)),
    ],
)
def test_mixed_or_duplicate_sequence_identity_fails_closed(
    observations: tuple[OrderedCandidateObservation, ...],
) -> None:
    with pytest.raises(CandidateSuccessMatrixInputError):
        evaluate_candidate_success_matrix(observations)


def test_observation_rejects_malformed_identity_range_source_and_causality() -> None:
    valid = _big(2)

    with pytest.raises(ValueError, match="LotteryType"):
        dataclasses.replace(valid, lottery_type="BIG_LOTTO")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="out-of-range"):
        dataclasses.replace(valid, emitted_main_numbers=(50,))
    with pytest.raises(ValueError, match="after history_cutoff"):
        dataclasses.replace(valid, target_draw="2", history_cutoff="2")
    with pytest.raises(ValueError, match="SHA-256"):
        CandidateSourceArtifactIdentity(
            repository="synthetic/golden",
            commit_oid="b" * 40,
            path="fixture.json",
            sha256="not-a-sha",
        )


def test_impossible_hit_signature_fails_closed() -> None:
    selection = _big(2).select_candidate_k(1)

    with pytest.raises(ValueError, match="exceeds effective unique K"):
        CandidateCoverageOutcome(
            selection=selection,
            main_hits=1,
            special_hit=True,
            zone2_hit=None,
        )


def test_donor_semantic_provenance_is_exact_and_runtime_native() -> None:
    assert tuple(reference.commit_oid for reference in DONOR_SEMANTIC_REFERENCES) == (
        "24617fe3bb7ec087acf121f302bffd638ccfa179",
        "24617fe3bb7ec087acf121f302bffd638ccfa179",
    )
    assert tuple(reference.symbol for reference in DONOR_SEMANTIC_REFERENCES) == (
        "select_strategy_numbers",
        "evaluate_strategy_pick_extended",
    )
    assert tuple(reference.blob_oid for reference in DONOR_SEMANTIC_REFERENCES) == (
        "f08b1d7dc3f974be53bf5bbe08b9dce285c04ac5",
        "1ae89e8dd6d82cabf0b4e97d270f6cb083f25c87",
    )


def test_repeated_evaluation_has_value_and_byte_identity() -> None:
    observations = (_power(2), _power(3))

    first = evaluate_candidate_success_matrix(observations)
    second = evaluate_candidate_success_matrix(observations)

    assert first == second
    assert first.canonical_json() == second.canonical_json()
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.cells = ()  # type: ignore[misc]
