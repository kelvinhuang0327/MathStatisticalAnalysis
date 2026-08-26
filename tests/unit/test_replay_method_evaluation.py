"""Contract tests for the Replay -> base-method-evaluation composition seam.

Two kinds of claim are under test here. First, that the seam itself is exact
and fail-closed: hit counts are set intersections, caller order survives, and
every missing/extra/duplicate/mismatched/unsuccessful input raises instead of
silently degrading into a zero-hit draw. Second -- the load-bearing one -- that
composing through the seam is indistinguishable from invoking the existing
evaluator directly, so this module can never become a second metric contract.

Expected metric values below are derived independently of the code under test
(counting successes by hand, and the hypergeometric mean 6*6/49 for AVG_MATCH)
rather than by re-running the same formula, so a wrong formula fails here and
not just a wrong transcription.
"""

from __future__ import annotations

from datetime import date, timedelta
from fractions import Fraction

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import (
    SNAPSHOT_SCHEMA_VERSION,
    ReplayPredictionSnapshot,
    ReplaySourceMode,
)
from lottolab.research.base_method_evaluation import (
    AVG_MATCH_ID,
    BIG_LOTTO_MATCH_CONTRACT,
    EvaluableStatus,
    ExposureKind,
    MethodDrawObservation,
    MethodEvaluationRecord,
    MethodExposure,
    MethodIdentity,
    MethodTargetCoverage,
    OutputShape,
    ReplayStatus,
    WindowKind,
    evaluate_method,
)
from lottolab.research.replay_method_evaluation import (
    ReplayMethodEvaluationError,
    ReplayTargetOutcome,
    build_method_draw_observations,
    build_single_ticket_identity,
    evaluate_replayed_single_ticket_method,
)

_STRATEGY_ID = "synthetic_single_ticket_strategy"
_STRATEGY_VERSION = "1.2.3"
_METHOD_FAMILY = "SYNTHETIC_TEST_FAMILY"
_BASE_DATE = date(2020, 1, 1)
_DIGEST = "0" * 64


def _draw_date(index: int) -> date:
    return _BASE_DATE + timedelta(days=index)


def _draw_number(index: int) -> str:
    return str(1000000 + index)


def _snapshot(
    index: int,
    predicted: tuple[int, ...] | None,
    *,
    strategy_id: str = _STRATEGY_ID,
    strategy_version: str | None = _STRATEGY_VERSION,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
    history_status: str = "OK",
    history_reason_code: str | None = None,
    prediction_status: str | None = "OK",
    prediction_reason_code: str | None = None,
) -> ReplayPredictionSnapshot:
    """One closed-schema snapshot; defaults describe a fully successful replay."""

    history_ok = history_status == "OK"
    identity_present = strategy_version is not None
    return ReplayPredictionSnapshot(
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        dataset_id="SYNTHETIC_DATASET",
        dataset_version="1",
        lottery_type=lottery_type,
        source_mode=ReplaySourceMode.TARGET_NATIVE,
        target_draw_number=_draw_number(index),
        target_draw_date=_draw_date(index),
        cutoff_draw_number=_draw_number(index - 1) if history_ok else None,
        cutoff_draw_date=_draw_date(index - 1) if history_ok else None,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        adapter_strategy_id=strategy_id if identity_present else None,
        adapter_strategy_name="Synthetic Strategy" if identity_present else None,
        adapter_strategy_version=strategy_version,
        history_status=history_status,
        history_reason_code=history_reason_code,
        causal_history_count=50 if history_ok else None,
        causal_history_sha256=_DIGEST if history_ok else None,
        prediction_status=prediction_status if history_ok else None,
        prediction_reason_code=prediction_reason_code if history_ok else None,
        predicted_main_numbers=predicted,
        result_sha256=_DIGEST,
    )


def _outcome(index: int, main_numbers: tuple[int, ...]) -> ReplayTargetOutcome:
    return ReplayTargetOutcome(
        draw_number=_draw_number(index),
        draw_date=_draw_date(index),
        main_numbers=main_numbers,
    )


# Hand-built so the hit counts are obvious by inspection: 6, 3, 0, 1.
_CASES: tuple[tuple[int, tuple[int, ...], tuple[int, ...], int], ...] = (
    (1, (1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6), 6),
    (2, (1, 2, 3, 40, 41, 42), (1, 2, 3, 10, 11, 12), 3),
    (3, (1, 2, 3, 4, 5, 6), (20, 21, 22, 23, 24, 25), 0),
    (4, (1, 30, 31, 32, 33, 34), (1, 10, 11, 12, 13, 14), 1),
)
_EXPECTED_HITS = tuple(case[3] for case in _CASES)


def _snapshots() -> tuple[ReplayPredictionSnapshot, ...]:
    return tuple(_snapshot(index, predicted) for index, predicted, _, _ in _CASES)


def _outcomes() -> tuple[ReplayTargetOutcome, ...]:
    return tuple(_outcome(index, numbers) for index, _, numbers, _ in _CASES)


def _record() -> MethodEvaluationRecord:
    return evaluate_replayed_single_ticket_method(
        _snapshots(),
        _outcomes(),
        method_family=_METHOD_FAMILY,
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )


class TestObservationConversion:
    def test_hit_counts_are_exact_set_intersections(self) -> None:
        observations = build_method_draw_observations(_snapshots(), _outcomes())

        assert tuple(obs.main_hit_counts[0] for obs in observations) == _EXPECTED_HITS

    def test_single_ticket_exposure_counts_are_one(self) -> None:
        observations = build_method_draw_observations(_snapshots(), _outcomes())

        assert all(obs.native_ticket_count == 1 for obs in observations)
        assert all(obs.distinct_ticket_count == 1 for obs in observations)
        assert all(len(obs.main_hit_counts) == 1 for obs in observations)

    def test_draw_identity_is_carried_through_verbatim(self) -> None:
        observations = build_method_draw_observations(_snapshots(), _outcomes())

        assert tuple(obs.draw_id for obs in observations) == tuple(
            _draw_number(index) for index, _, _, _ in _CASES
        )
        assert tuple(obs.draw_date for obs in observations) == tuple(
            _draw_date(index).isoformat() for index, _, _, _ in _CASES
        )

    def test_caller_order_is_preserved_and_never_sorted(self) -> None:
        """A deliberately unsorted batch must come back in the caller's order."""

        shuffled = (3, 1, 4, 2)
        snapshots = tuple(_snapshot(index, _CASES[index - 1][1]) for index in shuffled)
        outcomes = tuple(_outcome(index, _CASES[index - 1][2]) for index in shuffled)

        observations = build_method_draw_observations(snapshots, outcomes)

        assert tuple(obs.draw_id for obs in observations) == tuple(
            _draw_number(index) for index in shuffled
        )
        assert tuple(obs.main_hit_counts[0] for obs in observations) == tuple(
            _CASES[index - 1][3] for index in shuffled
        )

    def test_outcome_order_does_not_affect_binding(self) -> None:
        """Outcomes bind by target identity, so their own order is irrelevant."""

        observations = build_method_draw_observations(_snapshots(), tuple(reversed(_outcomes())))

        assert tuple(obs.main_hit_counts[0] for obs in observations) == _EXPECTED_HITS


class TestFailClosed:
    def test_empty_snapshots_fail_closed(self) -> None:
        with pytest.raises(ReplayMethodEvaluationError, match="snapshots must not be empty"):
            build_method_draw_observations((), ())

    def test_missing_outcome_fails_closed(self) -> None:
        with pytest.raises(ReplayMethodEvaluationError, match="no target outcome was supplied"):
            build_method_draw_observations(_snapshots(), _outcomes()[:-1])

    def test_extra_outcome_fails_closed(self) -> None:
        extra = (*_outcomes(), _outcome(9, (7, 8, 9, 10, 11, 12)))

        with pytest.raises(ReplayMethodEvaluationError, match="no matching snapshot"):
            build_method_draw_observations(_snapshots(), extra)

    def test_duplicate_outcome_fails_closed(self) -> None:
        duplicated = (*_outcomes(), _outcome(1, (1, 2, 3, 4, 5, 6)))

        with pytest.raises(ReplayMethodEvaluationError, match="duplicate entry for draw"):
            build_method_draw_observations(_snapshots(), duplicated)

    def test_duplicate_snapshot_target_fails_closed(self) -> None:
        snapshots = (*_snapshots(), _snapshot(1, (1, 2, 3, 4, 5, 6)))

        with pytest.raises(ReplayMethodEvaluationError, match="duplicate target draw"):
            build_method_draw_observations(snapshots, _outcomes())

    def test_outcome_date_mismatch_fails_closed(self) -> None:
        mismatched = (
            ReplayTargetOutcome(
                draw_number=_draw_number(1),
                draw_date=_draw_date(99),
                main_numbers=(1, 2, 3, 4, 5, 6),
            ),
            *_outcomes()[1:],
        )

        with pytest.raises(ReplayMethodEvaluationError, match="but the snapshot targets"):
            build_method_draw_observations(_snapshots(), mismatched)

    def test_failed_history_is_never_recorded_as_zero_hits(self) -> None:
        """The regression this seam exists to prevent: absence != a miss."""

        snapshots = (
            _snapshot(
                1,
                None,
                history_status="INSUFFICIENT_HISTORY",
                history_reason_code="TOO_FEW_DRAWS",
                prediction_status=None,
            ),
            *_snapshots()[1:],
        )

        with pytest.raises(ReplayMethodEvaluationError, match="history_status"):
            build_method_draw_observations(snapshots, _outcomes())

    def test_failed_prediction_is_never_recorded_as_zero_hits(self) -> None:
        snapshots = (
            _snapshot(
                1,
                None,
                prediction_status="STRATEGY_UNAVAILABLE",
                prediction_reason_code="NOT_REGISTERED",
            ),
            *_snapshots()[1:],
        )

        with pytest.raises(ReplayMethodEvaluationError, match="prediction_status"):
            build_method_draw_observations(snapshots, _outcomes())

    def test_foreign_lottery_snapshot_fails_closed(self) -> None:
        snapshots = (
            _snapshot(1, (1, 2, 3, 4, 5, 6), lottery_type=LotteryType.DAILY_539),
            *_snapshots()[1:],
        )

        with pytest.raises(ReplayMethodEvaluationError, match="not a BIG_LOTTO snapshot"):
            build_method_draw_observations(snapshots, _outcomes())

    @pytest.mark.parametrize(
        "predicted",
        [
            (1, 2, 3, 4, 5),
            (1, 2, 3, 4, 5, 6, 7),
            (1, 2, 3, 4, 5, 50),
            (1, 2, 3, 4, 5, 0),
        ],
    )
    def test_illegal_predicted_ticket_fails_closed(self, predicted: tuple[int, ...]) -> None:
        snapshots = (_snapshot(1, predicted),)
        outcomes = (_outcome(1, (1, 2, 3, 4, 5, 6)),)

        with pytest.raises(ReplayMethodEvaluationError, match="predicted_main_numbers"):
            build_method_draw_observations(snapshots, outcomes)

    def test_duplicate_predicted_numbers_fail_closed(self) -> None:
        snapshots = (_snapshot(1, (1, 1, 2, 3, 4, 5)),)
        outcomes = (_outcome(1, (1, 2, 3, 4, 5, 6)),)

        with pytest.raises(ReplayMethodEvaluationError, match="must not contain duplicates"):
            build_method_draw_observations(snapshots, outcomes)

    def test_illegal_outcome_number_count_fails_closed(self) -> None:
        snapshots = (_snapshot(1, (1, 2, 3, 4, 5, 6)),)
        outcomes = (_outcome(1, (1, 2, 3, 4, 5)),)

        with pytest.raises(ReplayMethodEvaluationError, match="outcome main_numbers"):
            build_method_draw_observations(snapshots, outcomes)

    def test_outcome_rejects_duplicate_numbers_at_construction(self) -> None:
        with pytest.raises(ReplayMethodEvaluationError, match="must not contain duplicates"):
            ReplayTargetOutcome(
                draw_number=_draw_number(1),
                draw_date=_draw_date(1),
                main_numbers=(1, 1, 2, 3, 4, 5),
            )

    def test_outcome_rejects_empty_draw_number(self) -> None:
        with pytest.raises(ReplayMethodEvaluationError, match="draw_number"):
            ReplayTargetOutcome(
                draw_number="",
                draw_date=_draw_date(1),
                main_numbers=(1, 2, 3, 4, 5, 6),
            )


class TestIdentity:
    def test_identity_is_derived_from_the_replayed_strategy(self) -> None:
        observations = build_method_draw_observations(_snapshots(), _outcomes())

        identity = build_single_ticket_identity(
            _snapshots(),
            observations,
            method_family=_METHOD_FAMILY,
            replay_status=ReplayStatus.BASELINE_RECORDED,
        )

        assert identity.method_id == _STRATEGY_ID
        assert identity.method_version == _STRATEGY_VERSION
        assert identity.method_family == _METHOD_FAMILY
        assert identity.output_shape is OutputShape.SINGLE_OUTPUT
        assert identity.exposure.kind is ExposureKind.FIXED
        assert identity.exposure.minimum_native_ticket_count == 1
        assert identity.exposure.maximum_native_ticket_count == 1
        assert identity.target_coverage.eligible_draw_count == len(_CASES)
        assert identity.target_coverage.first_draw_id == _draw_number(1)
        assert identity.target_coverage.last_draw_id == _draw_number(4)

    def test_mixed_strategy_ids_fail_closed(self) -> None:
        snapshots = (
            _snapshot(1, (1, 2, 3, 4, 5, 6)),
            _snapshot(2, (1, 2, 3, 4, 5, 6), strategy_id="another_strategy"),
        )
        observations = build_method_draw_observations(
            snapshots,
            (_outcome(1, (1, 2, 3, 4, 5, 6)), _outcome(2, (1, 2, 3, 4, 5, 6))),
        )

        with pytest.raises(ReplayMethodEvaluationError, match="exactly one strategy_id"):
            build_single_ticket_identity(
                snapshots,
                observations,
                method_family=_METHOD_FAMILY,
                replay_status=ReplayStatus.BASELINE_RECORDED,
            )

    def test_unresolved_strategy_identity_fails_closed(self) -> None:
        snapshots = (_snapshot(1, (1, 2, 3, 4, 5, 6), strategy_version=None),)
        observations = build_method_draw_observations(
            snapshots, (_outcome(1, (1, 2, 3, 4, 5, 6)),)
        )

        with pytest.raises(ReplayMethodEvaluationError, match="never resolved"):
            build_single_ticket_identity(
                snapshots,
                observations,
                method_family=_METHOD_FAMILY,
                replay_status=ReplayStatus.BASELINE_RECORDED,
            )

    def test_empty_method_family_fails_closed(self) -> None:
        observations = build_method_draw_observations(_snapshots(), _outcomes())

        with pytest.raises(ReplayMethodEvaluationError, match="method_family"):
            build_single_ticket_identity(
                _snapshots(),
                observations,
                method_family="",
                replay_status=ReplayStatus.BASELINE_RECORDED,
            )


class TestEvaluatorParity:
    def test_record_equals_direct_evaluator_invocation(self) -> None:
        """The load-bearing claim: the seam is not a second metric contract."""

        observations = build_method_draw_observations(_snapshots(), _outcomes())
        identity = build_single_ticket_identity(
            _snapshots(),
            observations,
            method_family=_METHOD_FAMILY,
            replay_status=ReplayStatus.BASELINE_RECORDED,
        )
        expected = evaluate_method(BIG_LOTTO_MATCH_CONTRACT, identity, observations)

        assert _record() == expected

    def test_hand_built_observations_reach_the_same_record(self) -> None:
        """Bypassing the seam entirely must produce an identical record."""

        hand_built = tuple(
            MethodDrawObservation(
                draw_id=_draw_number(index),
                draw_date=_draw_date(index).isoformat(),
                native_ticket_count=1,
                distinct_ticket_count=1,
                main_hit_counts=(hits,),
            )
            for index, _, _, hits in _CASES
        )
        identity = MethodIdentity(
            method_id=_STRATEGY_ID,
            method_version=_STRATEGY_VERSION,
            method_family=_METHOD_FAMILY,
            output_shape=OutputShape.SINGLE_OUTPUT,
            exposure=MethodExposure(
                kind=ExposureKind.FIXED,
                minimum_native_ticket_count=1,
                maximum_native_ticket_count=1,
            ),
            target_coverage=MethodTargetCoverage(
                eligible_draw_count=len(_CASES),
                first_draw_id=_draw_number(1),
                last_draw_id=_draw_number(4),
            ),
            replay_status=ReplayStatus.BASELINE_RECORDED,
        )

        assert _record() == evaluate_method(BIG_LOTTO_MATCH_CONTRACT, identity, hand_built)

    def test_identical_input_is_deterministic(self) -> None:
        assert _record() == _record()

    def test_all_four_windows_are_present(self) -> None:
        record = _record()

        assert set(record.windows) == {
            WindowKind.WINDOW_50,
            WindowKind.WINDOW_300,
            WindowKind.WINDOW_750,
            WindowKind.FULL_HISTORY,
        }


class TestExactMetrics:
    def test_average_match_is_the_independently_counted_value(self) -> None:
        """10 hits over 4 single-ticket draws, against the 6*6/49 hypergeometric mean."""

        cell = _record().windows[WindowKind.FULL_HISTORY].metrics[AVG_MATCH_ID]

        assert cell.observed_value == Fraction(10, 4)
        assert cell.random_reference == Fraction(36, 49)
        assert cell.delta_vs_random == Fraction(10, 4) - Fraction(36, 49)

    def test_m1_plus_success_count_is_independently_counted(self) -> None:
        """Three of the four crafted draws hit at least one number."""

        cell = _record().windows[WindowKind.FULL_HISTORY].metrics["M1_PLUS"]

        assert cell.success_draw_count == 3
        assert cell.observed_value == Fraction(3, 4)

    def test_m4_plus_success_count_is_independently_counted(self) -> None:
        """Only the perfect draw reaches four or more hits."""

        cell = _record().windows[WindowKind.FULL_HISTORY].metrics["M4_PLUS"]

        assert cell.success_draw_count == 1
        assert cell.observed_value == Fraction(1, 4)

    def test_small_history_is_reported_insufficient_not_evaluable(self) -> None:
        """Four draws is far below MINIMUM_SUPPORTED_DRAWS; the evaluator owns that call."""

        cell = _record().windows[WindowKind.FULL_HISTORY].metrics[AVG_MATCH_ID]

        assert cell.evaluable_status is EvaluableStatus.INSUFFICIENT
