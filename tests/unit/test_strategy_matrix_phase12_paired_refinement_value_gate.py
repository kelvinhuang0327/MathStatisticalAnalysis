"""Focused checks for the Phase 12 paired refinement-value evaluator."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import cast

from tools import run_strategy_matrix_phase12_paired_refinement_value_gate as phase12

from lottolab.application.ports import TargetDrawNotFoundError
from lottolab.application.use_cases.build_causal_history import (
    BuildCausalHistoryReason,
    BuildCausalHistoryStatus,
)
from lottolab.application.use_cases.generate_bet import GeneratePortfolioStatus
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.strategy_success_evaluation import WindowKind
from lottolab.domain.strategy_success_measurement import (
    BigLottoPortfolioOutcomeSignature,
    Daily539OutcomeSignature,
    OutcomeEligibility,
    PowerLottoOutcomeSignature,
)


class _SnapshotHistoryReader:
    def __init__(self, rows: tuple[ReplayCausalDrawRow, ...]) -> None:
        self._rows = rows

    def read_causal_history(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
        *,
        maximum_history_draws: int | None = None,
    ) -> tuple[ReplayCausalDrawRow, ...]:
        try:
            target_index = next(
                index
                for index, row in enumerate(self._rows)
                if row.lottery_type is lottery_type
                and row.draw_number == target_draw_number
            )
        except StopIteration as exc:
            raise TargetDrawNotFoundError(target_draw_number) from exc
        history = self._rows[:target_index]
        if maximum_history_draws is not None:
            history = history[-maximum_history_draws:]
        return history


def _big_targets() -> tuple[phase12.TargetOutcome, ...]:
    start = date(2026, 1, 1)
    return tuple(
        phase12.TargetOutcome(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=str(index),
            draw_date=start + timedelta(days=index - 1),
            main_numbers=tuple(range(index, index + 6)),
            special_number=index + 10,
            normalized_record_hash=f"hash-{index}",
            source_name="fixture",
            source_reference=f"fixture:{index}",
            ingestion_run_id="fixture-run",
        )
        for index in (1, 2, 3)
    )


def _history_rows(
    targets: tuple[phase12.TargetOutcome, ...],
) -> tuple[ReplayCausalDrawRow, ...]:
    return tuple(
        ReplayCausalDrawRow(
            lottery_type=target.lottery_type,
            draw_number=target.draw_number,
            draw_date=target.draw_date,
            main_numbers=target.main_numbers,
            special_number=target.special_number,
        )
        for target in targets
    )


def test_authorities_resolve_exactly_nine_frozen_pairs() -> None:
    assert phase12.verify_current_base_identity() == {
        "commit": phase12.PINNED_BASE_COMMIT,
        "tree": phase12.PINNED_BASE_TREE,
    }
    authority = phase12.verify_contract_authority()
    window_policy = cast(dict[str, object], authority["window_policy"])
    assert window_policy["policy_version"] == (
        "STRATEGY_SUCCESS_WINDOWS_V1"
    )
    pairs = phase12.load_frozen_pairs()
    assert len(pairs) == 9
    assert {(pair.structure_id, pair.k) for pair in pairs} == set(
        phase12.LOCKED_PAIR_SHA256
    )
    for pair in pairs:
        expected_baseline, expected_refined = phase12.LOCKED_PAIR_SHA256[
            (pair.structure_id, pair.k)
        ]
        assert len(pair.baseline.portfolio) == len(pair.refined.portfolio) == pair.k
        assert phase12.portfolio_sha256(pair.baseline.portfolio) == expected_baseline
        assert phase12.portfolio_sha256(pair.refined.portfolio) == expected_refined


def test_replay_preserves_pair_targets_cutoffs_ticket_order_and_typed_closure() -> None:
    pair = next(
        pair
        for pair in phase12.load_frozen_pairs()
        if pair.structure_id == "BIG_LOTTO" and pair.k == 10
    )
    targets = _big_targets()
    rows = _history_rows(targets)
    replayed = phase12.replay_frozen_pairs(
        lottery_type=LotteryType.BIG_LOTTO,
        targets=targets,
        pairs=(pair,),
        database_sha256="0" * 64,
        reader_factory=lambda: _SnapshotHistoryReader(rows),
    )

    baseline = replayed[pair.baseline.strategy_id]
    refined = replayed[pair.refined.strategy_id]
    assert len(baseline) == len(refined) == len(targets)
    assert [snapshot.target_draw_number for snapshot in baseline] == ["1", "2", "3"]
    assert [snapshot.target_draw_number for snapshot in refined] == ["1", "2", "3"]

    for snapshots, member in (
        (baseline, pair.baseline),
        (refined, pair.refined),
    ):
        first = snapshots[0]
        assert first.history_status == BuildCausalHistoryStatus.INSUFFICIENT_HISTORY.value
        assert first.history_reason_code == (
            BuildCausalHistoryReason.AVAILABLE_HISTORY_BELOW_MINIMUM.value
        )
        assert first.prediction_status is None
        assert first.predicted_tickets is None
        for index, snapshot in enumerate(snapshots[1:], start=1):
            assert snapshot.history_status == BuildCausalHistoryStatus.OK.value
            assert snapshot.prediction_status == GeneratePortfolioStatus.OK.value
            assert snapshot.cutoff_draw_number == str(index)
            assert snapshot.cutoff_draw_date == targets[index - 1].draw_date
            assert snapshot.predicted_tickets == member.portfolio
            predicted_tickets = snapshot.predicted_tickets
            assert predicted_tickets is not None
            assert len(predicted_tickets) == pair.k


def test_pair_evaluation_uses_identical_eligible_targets_and_canonical_windows() -> None:
    pair = next(
        pair
        for pair in phase12.load_frozen_pairs()
        if pair.structure_id == "BIG_LOTTO" and pair.k == 10
    )
    targets = _big_targets()
    rows = _history_rows(targets)
    replayed = phase12.replay_frozen_pairs(
        lottery_type=LotteryType.BIG_LOTTO,
        targets=targets,
        pairs=(pair,),
        database_sha256="0" * 64,
        reader_factory=lambda: _SnapshotHistoryReader(rows),
    )
    result = phase12.evaluate_pair(
        pair=pair,
        targets=targets,
        snapshots_by_strategy=replayed,
    )

    baseline = cast(dict[str, object], result["baseline"])
    refined = cast(dict[str, object], result["refined"])
    assert baseline["all_target_count"] == refined["all_target_count"] == 3
    assert baseline["eligible_target_count"] == refined["eligible_target_count"] == 2
    assert baseline["closure_count"] == refined["closure_count"] == 1
    assert baseline["all_target_identities_sha256"] == (
        refined["all_target_identities_sha256"]
    )
    assert baseline["eligible_target_identities_sha256"] == (
        refined["eligible_target_identities_sha256"]
    )
    windows = cast(dict[str, dict[str, object]], result["windows"])
    assert set(windows) == {kind.value for kind in WindowKind}
    full_delta = cast(dict[str, object], windows["FULL_HISTORY"]["paired_delta_success_rate"])
    assert full_delta == {
        "available": True,
        "denominator": 1,
        "exact": "0/1",
        "numerator": 0,
    }
    for kind in ("LONG", "MEDIUM", "SHORT"):
        delta = cast(dict[str, object], windows[kind]["paired_delta_success_rate"])
        assert delta["available"] is False


def test_native_scoring_contracts_preserve_portfolio_semantics_without_zone2() -> None:
    pairs = phase12.load_frozen_pairs()
    big_pair = next(pair for pair in pairs if pair.structure_id == "BIG_LOTTO")
    big_target = _big_targets()[1]
    big = phase12.outcome_signature(
        LotteryType.BIG_LOTTO,
        big_pair.baseline.portfolio,
        big_target,
    )
    assert isinstance(big, BigLottoPortfolioOutcomeSignature)
    assert big.ticket_count == big_pair.k

    daily_pair = next(pair for pair in pairs if pair.structure_id == "DAILY_539")
    daily_target = phase12.TargetOutcome(
        lottery_type=LotteryType.DAILY_539,
        draw_number="1",
        draw_date=date(2026, 1, 1),
        main_numbers=(1, 2, 3, 4, 5),
        special_number=None,
        normalized_record_hash="daily",
        source_name="fixture",
        source_reference="fixture",
        ingestion_run_id="fixture-run",
    )
    daily = phase12.outcome_signature(
        LotteryType.DAILY_539,
        daily_pair.baseline.portfolio,
        daily_target,
    )
    assert isinstance(daily, Daily539OutcomeSignature)
    assert daily.main_hits == max(
        len(set(ticket).intersection(daily_target.main_numbers))
        for ticket in daily_pair.baseline.portfolio
    )

    power_pair = next(pair for pair in pairs if pair.structure_id == "POWER_LOTTO_ZONE1")
    power_target = phase12.TargetOutcome(
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number="1",
        draw_date=date(2026, 1, 1),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
        normalized_record_hash="power",
        source_name="fixture",
        source_reference="fixture",
        ingestion_run_id="fixture-run",
    )
    power = phase12.outcome_signature(
        LotteryType.POWER_LOTTO,
        power_pair.baseline.portfolio,
        power_target,
    )
    assert isinstance(power, PowerLottoOutcomeSignature)
    assert power.zone1_hits == max(
        len(set(ticket).intersection(power_target.main_numbers))
        for ticket in power_pair.baseline.portfolio
    )
    assert power.zone2_hit is None
    assert power.eligibility is OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE
    assert phase12.criterion_for_lottery(LotteryType.POWER_LOTTO).canonical_dict()[
        "zone2_requirement"
    ] == "NOT_USED"


def test_normalized_bytes_are_deterministic_and_no_decision_rule_is_invented() -> None:
    first = {
        "z": [3, 2, 1],
        "aggregate": {
            "classification": phase12.AGGREGATE_INTERPRETATION,
            "decision_rule": None,
        },
    }
    second = {
        "aggregate": {
            "decision_rule": None,
            "classification": "INCONCLUSIVE",
        },
        "z": [3, 2, 1],
    }
    assert phase12.canonical_json_bytes(first) == phase12.canonical_json_bytes(second)
    assert phase12.AGGREGATE_INTERPRETATION == "INCONCLUSIVE"


def test_sealed_result_contains_all_nine_cells_when_materialized() -> None:
    payload = json.loads(phase12.OUTPUT_PATH.read_bytes())
    assert payload["study_id"] == phase12.STUDY_ID
    assert payload["task_id"] == phase12.TASK_ID
    assert payload["pair_count"] == 9
    assert len(payload["per_cell"]) == 9
    assert payload["aggregate_interpretation"] == {
        "classification": "INCONCLUSIVE",
        "decision_rule": None,
        "reason": (
            "The canonical evaluator is descriptive and defines no paired "
            "refinement-value decision rule; no Worker-invented threshold was applied."
        ),
    }
    assert payload["invariants"]["p638_zone2"] == "NOT_RUN"
    assert payload["invariants"]["database_writes"] == "NONE"
    for cell in payload["per_cell"]:
        assert cell["pair_checks"] == {
            "all_target_identities_equal": True,
            "criterion_and_scoring_equal": True,
            "eligible_target_identities_equal": True,
            "no_result_silently_omitted": True,
            "ticket_count_equal": True,
            "ticket_position_semantics": "SOURCE_ORDER_PRESERVED",
        }
