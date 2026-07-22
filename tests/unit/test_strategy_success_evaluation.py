from __future__ import annotations

import dataclasses

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategy_success_evaluation import (
    BigLottoSuccessCriterion,
    Daily539SuccessCriterion,
    ExactSuccessRate,
    ObservationEvaluation,
    OfficialTierSuccessCriterion,
    PowerLottoSuccessCriterion,
    PowerLottoZone2Requirement,
    StrategySuccessEvaluationInputError,
    WindowEvaluationStatus,
    WindowKind,
    evaluate_observation,
    evaluate_strategy_success_windows,
)
from lottolab.domain.strategy_success_measurement import (
    DEFAULT_WINDOW_POLICY,
    BigLottoOutcomeSignature,
    Daily539OutcomeSignature,
    EvidenceStatus,
    MeasurementMode,
    MeasurementProvenance,
    MeasurementWindowPolicy,
    OutcomeEligibility,
    PowerLottoOutcomeSignature,
    SelectionIdentity,
    StrategySuccessMeasurement,
    WindowRole,
)


def _selection(lottery: LotteryType, mode: MeasurementMode) -> SelectionIdentity:
    values: dict[str, object] = {
        "lottery": lottery,
        "strategy_id": "name-without-parsed-axes",
        "strategy_version": "v1",
    }
    if mode is MeasurementMode.CANDIDATE_COVERAGE:
        values["candidate_k"] = 6 if lottery is not LotteryType.DAILY_539 else 5
    else:
        values["ticket_count"] = 1
    return SelectionIdentity(**values)  # type: ignore[arg-type]


def _measurement(
    index: int,
    *,
    lottery: LotteryType = LotteryType.BIG_LOTTO,
    mode: MeasurementMode = MeasurementMode.CANDIDATE_COVERAGE,
    outcome: BigLottoOutcomeSignature | PowerLottoOutcomeSignature | Daily539OutcomeSignature
    | None = None,
    selection: SelectionIdentity | None = None,
    policy: MeasurementWindowPolicy = DEFAULT_WINDOW_POLICY,
    official_prize_tier_id: str | None = None,
) -> StrategySuccessMeasurement:
    if outcome is None:
        if lottery is LotteryType.BIG_LOTTO:
            outcome = BigLottoOutcomeSignature(main_hits=2, special_hit=True)
        elif lottery is LotteryType.POWER_LOTTO:
            outcome = PowerLottoOutcomeSignature(zone1_hits=1, zone2_hit=True)
        else:
            outcome = Daily539OutcomeSignature(main_hits=1)
    if mode is MeasurementMode.OFFICIAL_PRIZE_TIER and official_prize_tier_id is None:
        official_prize_tier_id = "TIER_A"
    return StrategySuccessMeasurement(
        mode=mode,
        selection=selection or _selection(lottery, mode),
        outcome_signature=outcome,
        evidence_status=EvidenceStatus.DESCRIPTIVE_ONLY,
        provenance=MeasurementProvenance(
            strategy_version="v1",
            history_cutoff=f"cutoff-{index}",
            target_draw=f"draw-{index}",
            window_policy_version=policy.policy_version,
        ),
        window_policy=policy,
        official_prize_tier_id=official_prize_tier_id,
    )


def _big_criterion(
    *,
    minimum: int = 2,
    special: bool = True,
    mode: MeasurementMode = MeasurementMode.CANDIDATE_COVERAGE,
) -> BigLottoSuccessCriterion:
    return BigLottoSuccessCriterion(
        minimum_main_hits=minimum,
        require_special_hit=special,
        expected_mode=mode,
    )


def test_more_than_750_records_produces_nested_source_ordered_windows() -> None:
    observations = tuple(
        _measurement(
            index,
            outcome=BigLottoOutcomeSignature(main_hits=2, special_hit=index % 2 == 0),
        )
        for index in range(800)
    )

    summaries = evaluate_strategy_success_windows(observations, _big_criterion())

    assert tuple(summary.window_kind for summary in summaries) == (
        WindowKind.FULL_HISTORY,
        WindowKind.LONG,
        WindowKind.MEDIUM,
        WindowKind.SHORT,
    )
    assert tuple(summary.source_draw_count for summary in summaries) == (800, 750, 300, 50)
    assert tuple(summary.success_count for summary in summaries) == (400, 375, 150, 25)
    assert tuple(summary.first_target_draw for summary in summaries) == (
        "draw-0",
        "draw-50",
        "draw-500",
        "draw-750",
    )
    assert all(summary.last_target_draw == "draw-799" for summary in summaries)
    assert all(summary.nested_windows_independent is False for summary in summaries)


def test_one_hundred_observations_preserve_incomplete_and_complete_windows() -> None:
    summaries = evaluate_strategy_success_windows(
        tuple(_measurement(index) for index in range(100)),
        _big_criterion(),
    )

    assert tuple(summary.evaluation_status for summary in summaries) == (
        WindowEvaluationStatus.COMPLETE,
        WindowEvaluationStatus.INSUFFICIENT_DRAWS,
        WindowEvaluationStatus.INSUFFICIENT_DRAWS,
        WindowEvaluationStatus.COMPLETE,
    )
    assert summaries[1].source_draw_count == 100
    assert summaries[2].source_draw_count == 100
    assert summaries[1].success_rate == ExactSuccessRate.unavailable()
    assert summaries[2].success_rate == ExactSuccessRate.unavailable()
    assert summaries[0].success_rate == ExactSuccessRate(100, 100)
    assert summaries[3].success_rate == ExactSuccessRate(50, 50)


def test_zero_eligible_observations_have_no_eligible_draws_and_unavailable_rate() -> None:
    missing = PowerLottoOutcomeSignature(
        zone1_hits=1,
        zone2_hit=None,
        eligibility=OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE,
    )
    observations = tuple(
        _measurement(index, lottery=LotteryType.POWER_LOTTO, outcome=missing)
        for index in range(50)
    )
    criterion = PowerLottoSuccessCriterion(
        minimum_zone1_hits=1,
        zone2_requirement=PowerLottoZone2Requirement.HIT_REQUIRED,
        expected_mode=MeasurementMode.CANDIDATE_COVERAGE,
    )

    full, _, _, short = evaluate_strategy_success_windows(observations, criterion)

    assert full.evaluation_status is WindowEvaluationStatus.NO_ELIGIBLE_DRAWS
    assert short.evaluation_status is WindowEvaluationStatus.NO_ELIGIBLE_DRAWS
    assert full.success_rate == ExactSuccessRate.unavailable()
    assert short.success_rate == ExactSuccessRate.unavailable()
    assert (short.eligible_draw_count, short.excluded_draw_count) == (0, 50)


def test_exact_counts_exclude_missing_zone2_without_turning_it_into_failure() -> None:
    outcomes: list[PowerLottoOutcomeSignature] = []
    outcomes.extend(
        PowerLottoOutcomeSignature(
            zone1_hits=1,
            zone2_hit=None,
            eligibility=OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE,
        )
        for _ in range(10)
    )
    outcomes.extend(PowerLottoOutcomeSignature(1, True) for _ in range(20))
    outcomes.extend(PowerLottoOutcomeSignature(1, False) for _ in range(20))
    criterion = PowerLottoSuccessCriterion(
        minimum_zone1_hits=1,
        zone2_requirement=PowerLottoZone2Requirement.HIT_REQUIRED,
        expected_mode=MeasurementMode.CANDIDATE_COVERAGE,
    )

    short = evaluate_strategy_success_windows(
        tuple(
            _measurement(index, lottery=LotteryType.POWER_LOTTO, outcome=outcome)
            for index, outcome in enumerate(outcomes)
        ),
        criterion,
    )[-1]

    assert short.source_draw_count == 50
    assert (short.success_count, short.failure_count, short.excluded_draw_count) == (20, 20, 10)
    assert short.success_rate == ExactSuccessRate(20, 40)


def test_exact_success_rate_is_integer_only_and_canonically_serialized() -> None:
    rate = ExactSuccessRate(2, 3)

    assert rate.canonical_json() == '{"available":true,"denominator":3,"numerator":2}'
    assert ExactSuccessRate.unavailable().canonical_json() == (
        '{"available":false,"denominator":0,"numerator":0}'
    )
    with pytest.raises(ValueError, match="integers"):
        ExactSuccessRate(True, 1)
    with pytest.raises(ValueError, match="cannot exceed"):
        ExactSuccessRate(2, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rate.numerator = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (BigLottoOutcomeSignature(2, True), ObservationEvaluation.SUCCESS),
        (BigLottoOutcomeSignature(2, False), ObservationEvaluation.FAILURE),
        (BigLottoOutcomeSignature(1, True), ObservationEvaluation.FAILURE),
    ],
)
def test_big_lotto_m2_special_boundary(
    outcome: BigLottoOutcomeSignature,
    expected: ObservationEvaluation,
) -> None:
    assert evaluate_observation(_measurement(1, outcome=outcome), _big_criterion()) is expected


def test_candidate_and_legal_ticket_modes_are_not_interchangeable() -> None:
    legal = _measurement(
        1,
        mode=MeasurementMode.LEGAL_TICKET_PRIZE,
        outcome=BigLottoOutcomeSignature(3, True),
    )
    candidate_criterion = _big_criterion(mode=MeasurementMode.CANDIDATE_COVERAGE)
    legal_criterion = _big_criterion(mode=MeasurementMode.LEGAL_TICKET_PRIZE)

    assert evaluate_observation(legal, candidate_criterion) is ObservationEvaluation.EXCLUDED
    assert evaluate_observation(legal, legal_criterion) is ObservationEvaluation.SUCCESS


def test_power_lotto_hit_miss_missing_and_explicit_zone1_only_semantics() -> None:
    hit = _measurement(
        1,
        lottery=LotteryType.POWER_LOTTO,
        outcome=PowerLottoOutcomeSignature(1, True),
    )
    miss = _measurement(
        2,
        lottery=LotteryType.POWER_LOTTO,
        outcome=PowerLottoOutcomeSignature(1, False),
    )
    missing = _measurement(
        3,
        lottery=LotteryType.POWER_LOTTO,
        outcome=PowerLottoOutcomeSignature(
            1,
            None,
            OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE,
        ),
    )
    dependent = PowerLottoSuccessCriterion(
        1,
        PowerLottoZone2Requirement.HIT_REQUIRED,
        MeasurementMode.CANDIDATE_COVERAGE,
    )
    zone1_only = PowerLottoSuccessCriterion(
        1,
        PowerLottoZone2Requirement.NOT_USED,
        MeasurementMode.CANDIDATE_COVERAGE,
    )

    assert evaluate_observation(hit, dependent) is ObservationEvaluation.SUCCESS
    assert evaluate_observation(miss, dependent) is ObservationEvaluation.FAILURE
    assert evaluate_observation(missing, dependent) is ObservationEvaluation.EXCLUDED
    assert evaluate_observation(missing, zone1_only) is ObservationEvaluation.SUCCESS


def test_daily_539_m1_boundary_and_criterion_shape() -> None:
    criterion = Daily539SuccessCriterion(1, MeasurementMode.CANDIDATE_COVERAGE)
    success = _measurement(
        1,
        lottery=LotteryType.DAILY_539,
        outcome=Daily539OutcomeSignature(1),
    )
    failure = _measurement(
        2,
        lottery=LotteryType.DAILY_539,
        outcome=Daily539OutcomeSignature(0),
    )

    assert evaluate_observation(success, criterion) is ObservationEvaluation.SUCCESS
    assert evaluate_observation(failure, criterion) is ObservationEvaluation.FAILURE
    with pytest.raises(TypeError):
        Daily539SuccessCriterion(1, MeasurementMode.CANDIDATE_COVERAGE, special=True)  # type: ignore[call-arg]


def test_official_tier_requires_exact_mode_and_tier_identity() -> None:
    criterion = OfficialTierSuccessCriterion(LotteryType.BIG_LOTTO, "TIER_A")
    exact = _measurement(1, mode=MeasurementMode.OFFICIAL_PRIZE_TIER)
    other = _measurement(
        2,
        mode=MeasurementMode.OFFICIAL_PRIZE_TIER,
        official_prize_tier_id="TIER_B",
    )
    diagnostic = _measurement(3)

    assert evaluate_observation(exact, criterion) is ObservationEvaluation.SUCCESS
    assert evaluate_observation(other, criterion) is ObservationEvaluation.FAILURE
    assert evaluate_observation(diagnostic, criterion) is ObservationEvaluation.EXCLUDED
    with pytest.raises(ValueError, match="OFFICIAL_PRIZE_TIER"):
        OfficialTierSuccessCriterion(
            LotteryType.BIG_LOTTO,
            "TIER_A",
            MeasurementMode.CANDIDATE_COVERAGE,
        )
    with pytest.raises(ValueError, match="diagnostic criteria"):
        BigLottoSuccessCriterion(2, True, MeasurementMode.OFFICIAL_PRIZE_TIER)


def test_official_power_tier_excludes_missing_zone2() -> None:
    missing = _measurement(
        1,
        lottery=LotteryType.POWER_LOTTO,
        mode=MeasurementMode.OFFICIAL_PRIZE_TIER,
        outcome=PowerLottoOutcomeSignature(
            1,
            None,
            OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE,
        ),
    )
    criterion = OfficialTierSuccessCriterion(LotteryType.POWER_LOTTO, "TIER_A")

    assert evaluate_observation(missing, criterion) is ObservationEvaluation.EXCLUDED


def test_malformed_and_lottery_mismatched_observations_fail_closed() -> None:
    big = _measurement(1)
    daily = Daily539SuccessCriterion(1, MeasurementMode.CANDIDATE_COVERAGE)

    assert evaluate_observation(object(), _big_criterion()) is ObservationEvaluation.EXCLUDED
    assert evaluate_observation(big, object()) is ObservationEvaluation.EXCLUDED
    assert evaluate_observation(big, daily) is ObservationEvaluation.EXCLUDED


def test_duplicate_target_draw_fails() -> None:
    with pytest.raises(StrategySuccessEvaluationInputError, match="duplicate target_draw"):
        evaluate_strategy_success_windows((_measurement(1), _measurement(1)), _big_criterion())


def test_mixed_selection_identities_fail() -> None:
    other = SelectionIdentity(
        lottery=LotteryType.BIG_LOTTO,
        strategy_id="other",
        strategy_version="v1",
        candidate_k=6,
    )
    with pytest.raises(StrategySuccessEvaluationInputError, match="selection identities"):
        evaluate_strategy_success_windows(
            (_measurement(1), _measurement(2, selection=other)),
            _big_criterion(),
        )


def test_mixed_measurement_modes_fail() -> None:
    with pytest.raises(StrategySuccessEvaluationInputError, match="measurement modes"):
        evaluate_strategy_success_windows(
            (
                _measurement(1),
                _measurement(2, mode=MeasurementMode.LEGAL_TICKET_PRIZE),
            ),
            _big_criterion(),
        )


def test_mixed_window_policy_versions_fail() -> None:
    version_two = MeasurementWindowPolicy(policy_version="STRATEGY_SUCCESS_WINDOWS_V2")
    with pytest.raises(StrategySuccessEvaluationInputError, match="window-policy versions"):
        evaluate_strategy_success_windows(
            (_measurement(1), _measurement(2, policy=version_two)),
            _big_criterion(),
        )


@pytest.mark.parametrize("missing_field", ["target_draw", "history_cutoff"])
def test_required_provenance_identity_must_be_present(missing_field: str) -> None:
    provenance_values: dict[str, str | None] = {
        "strategy_version": "v1",
        "history_cutoff": "cutoff-1",
        "target_draw": "draw-1",
        "window_policy_version": DEFAULT_WINDOW_POLICY.policy_version,
    }
    provenance_values[missing_field] = None
    source = _measurement(1)
    malformed = dataclasses.replace(
        source,
        provenance=MeasurementProvenance(**provenance_values),
    )
    with pytest.raises(StrategySuccessEvaluationInputError, match=missing_field):
        evaluate_strategy_success_windows((malformed,), _big_criterion())


def test_window_evidence_never_promotes_and_roles_remain_policy_roles() -> None:
    summaries = evaluate_strategy_success_windows(
        tuple(_measurement(index) for index in range(100)),
        _big_criterion(),
    )

    assert tuple(summary.window_role for summary in summaries) == (
        WindowRole.REFERENCE_ONLY,
        WindowRole.PRIMARY_EVIDENCE,
        WindowRole.STABILITY_CONFIRMATION,
        WindowRole.DEGRADATION_VETO,
    )
    assert summaries[0].evidence_status is EvidenceStatus.DESCRIPTIVE_ONLY
    assert summaries[3].evidence_status is EvidenceStatus.DESCRIPTIVE_ONLY
    assert summaries[1].evidence_status is EvidenceStatus.NOT_READY
    assert summaries[2].evidence_status is EvidenceStatus.NOT_READY
    assert all(
        summary.evidence_status
        not in (
            EvidenceStatus.HISTORICAL_OOS_VERIFIED,
            EvidenceStatus.CROSS_GAME_VERIFIED,
            EvidenceStatus.SHADOW_CAPTURE,
            EvidenceStatus.PRODUCTION_ELIGIBLE,
        )
        for summary in summaries
    )


def test_summary_canonical_serialization_preserves_exact_identity_and_counts() -> None:
    summary = evaluate_strategy_success_windows((_measurement(1),), _big_criterion())[0]

    assert summary.canonical_json() == summary.canonical_json()
    assert '"criterion_identity":"{\\"criterion_type\\":' in summary.canonical_json()
    assert '"success_rate":{"available":true,"denominator":1,"numerator":1}' in (
        summary.canonical_json()
    )
