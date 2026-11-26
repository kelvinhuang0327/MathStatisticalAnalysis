"""Synthetic acceptance for typed source-native replay closures.

These fixtures exercise Replay status and persistence contracts only. They do
not claim production-strategy boundary evidence for the 13/14 or 17/18 cases.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from lottolab.application.replay_official_ranking import JsonObject, aggregate_ranking
from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayController,
)
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    BackfillStore,
    ReplayBackfill,
)
from lottolab.application.use_cases.replay_backfill import (
    JsonObject as BackfillJsonObject,
)
from lottolab.application.use_cases.replay_exact_native_targets import (
    causal_row,
    replay_cell,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw, RuntimeBinding
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    HistoricalReplayRequest,
    ReplayBehavior,
    ReplayCellStatus,
    ReplayDraw,
    ReplayEvaluation,
    ReplaySourceSnapshot,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.evidence.exact_native_replay_manifest import history_fingerprint
from lottolab.strategies.adapters.base import (
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    SourceNativePortfolioClosure,
)

_TICKETS_BY_CANDIDATE_COUNT = {
    14: (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 7, 8, 9),
        (1, 2, 3, 10, 11, 12),
    ),
    18: (
        (1, 4, 5, 6, 7, 8),
        (2, 9, 10, 11, 12, 13),
        (3, 14, 15, 16, 17, 18),
    ),
}


def _replay_draw(number: int) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 1),
        main_numbers=(30, 31, 32, 33, 34, 35),
        special_number=7,
    )


def _native_draw(number: int) -> Draw:
    return Draw(
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 1),
        main_numbers=(30, 31, 32, 33, 34, 35),
        special_number=7,
    )


def _strategy(*, min_history: int = 1) -> ReplayStrategy:
    return ReplayStrategy(
        strategy_id="synthetic__k235_closure__v2",
        strategy_name="Synthetic K235 closure fixture",
        strategy_version="v2",
        behavior=ReplayBehavior.DETERMINISTIC,
        native_ticket_count=3,
        min_history=min_history,
    )


def _descriptor(*, min_history: int = 1) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id="synthetic__k235_closure__v2",
        strategy_name="Synthetic K235 closure fixture",
        version="v2",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path="synthetic.fixture:Portfolio",
        min_history=min_history,
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=3,
    )


def _source_native_exception(
    strategy_id: str = "synthetic__k235_closure__v2",
) -> SourceNativePortfolioClosure:
    return SourceNativePortfolioClosure(
        strategy_id=strategy_id,
        expected_ticket_count=3,
        actual_ticket_count=2,
    )


def _replay_tickets(candidate_count: int) -> tuple[ReplayTicket, ...]:
    return tuple(
        ReplayTicket(ticket_position=position, main_numbers=numbers)
        for position, numbers in enumerate(_TICKETS_BY_CANDIDATE_COUNT[candidate_count], start=1)
    )


def _native_executions(candidate_count: int) -> tuple[BetAdapterExecution, ...]:
    return tuple(
        BetAdapterExecution(
            emitted_main_numbers=numbers,
            legal_main_numbers=numbers,
            special_number=None,
        )
        for numbers in _TICKETS_BY_CANDIDATE_COUNT[candidate_count]
    )


class _SyntheticReplayAdapter:
    lottery_type = LotteryType.BIG_LOTTO

    def __init__(self, candidate_count: int, failure: str | None = None) -> None:
        self.candidate_count = candidate_count
        self.failure = failure

    def expected_native_ticket_count(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> int:
        del strategy, history, target
        return 3

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        del history, target
        if self.failure == "value_error":
            raise ValueError("synthetic unclassified failure")
        if self.failure == "invalid_output":
            return _replay_tickets(14)[:2]
        if self.failure == "misbound_closure":
            raise _source_native_exception("different_strategy")
        if self.candidate_count in (13, 17):
            raise _source_native_exception(strategy.strategy_id)
        return _replay_tickets(self.candidate_count)

    def evaluate(
        self,
        strategy: ReplayStrategy,
        ticket: ReplayTicket,
        target: ReplayDraw,
    ) -> ReplayEvaluation:
        del strategy, ticket, target
        return ReplayEvaluation(zone1_hits=0, zone2_hit=False, is_winner=False, prize_tier=None)


class _SyntheticNativeAdapter:
    def __init__(
        self,
        candidate_count: int,
        failure: str | None = None,
        exception_strategy_id: str = "synthetic__k235_closure__v2",
    ) -> None:
        self.candidate_count = candidate_count
        self.failure = failure
        self.exception_strategy_id = exception_strategy_id

    def get_bets_with_emission(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[BetAdapterExecution, ...]:
        del history, lottery_type
        if self.failure == "value_error":
            raise ValueError("synthetic unclassified failure")
        if self.failure == "insufficient_history":
            raise InsufficientHistory("synthetic history gap")
        if self.failure == "invalid_output":
            raise InvalidOutput("synthetic invalid ticket")
        if self.failure is None and self.candidate_count in (13, 17):
            raise _source_native_exception(self.exception_strategy_id)
        return _native_executions(self.candidate_count)


class _CapturingBackfillStore:
    """In-memory implementation of the formal store contract for one focused test."""

    def __init__(self) -> None:
        self.saved_cells: tuple[BackfillJsonObject, ...] = ()

    def prepare(self, manifest: BackfillJsonObject) -> None:
        del manifest

    def lookup(self, cell_identity: str) -> BackfillJsonObject | None:
        del cell_identity
        return None

    def lookup_many(
        self, cell_identities: tuple[str, ...]
    ) -> dict[str, BackfillJsonObject]:
        del cell_identities
        return {}

    def lookup_many_by_unique_keys(
        self,
        keys: tuple[tuple[str, str, str, str, str, str], ...],
    ) -> dict[tuple[str, str, str, str, str, str], BackfillJsonObject]:
        del keys
        return {}

    def lookup_complete_by_logical_keys(
        self,
        keys: tuple[tuple[str, str, str, str], ...],
    ) -> dict[tuple[str, str, str, str], tuple[BackfillJsonObject, ...]]:
        del keys
        return {}

    def save(
        self, run_id: str, result: BackfillJsonObject, *, attempted: bool = True
    ) -> None:
        del run_id, result, attempted

    def save_many(
        self, run_id: str, results: tuple[BackfillJsonObject, ...]
    ) -> None:
        del run_id
        self.saved_cells = results

    def summary(self, run_id: str) -> BackfillJsonObject:
        return {"run_id": run_id}


def _controller_result(adapter: _SyntheticReplayAdapter, *, min_history: int = 1):
    historical = (_replay_draw(1), _replay_draw(2))
    strategy = _strategy(min_history=min_history)
    request = HistoricalReplayRequest(
        lottery_type=LotteryType.BIG_LOTTO,
        mode=HistoricalReplayMode.FULL_REPLAY,
        source=ReplaySourceSnapshot(
            lottery_type=LotteryType.BIG_LOTTO,
            historical_draws=historical,
            official_draws=(),
            stored_targets=(),
            stored_tickets=(),
        ),
        strategies=(strategy,),
        cutoff_draw_number="2",
    )
    return HistoricalReplayController(adapter).execute(request), strategy, historical


def _native_row(
    candidate_count: int,
    *,
    failure: str | None = None,
    min_history: int = 1,
    exception_strategy_id: str = "synthetic__k235_closure__v2",
) -> dict[str, object]:
    history = (_native_draw(1),)
    target = _native_draw(2)
    descriptor = _descriptor(min_history=min_history)
    implementation = _SyntheticNativeAdapter(
        candidate_count,
        failure,
        exception_strategy_id,
    )
    binding = RuntimeBinding(descriptor, implementation, "SyntheticNativeAdapter", None)
    return replay_cell(
        binding,
        target,
        history,
        {"FULL": {"draw_numbers": [target.draw_number]}},
        "synthetic-run",
        causal_rows=tuple(causal_row(draw) for draw in history),
        history_fingerprint=history_fingerprint(history),
    )


@pytest.mark.parametrize(
    ("candidate_count", "expected_status"),
    [(13, ReplayCellStatus.TYPED_CLOSURE), (14, ReplayCellStatus.COMPLETE),
     (17, ReplayCellStatus.TYPED_CLOSURE), (18, ReplayCellStatus.COMPLETE)],
)
def test_controller_synthetic_13_14_and_17_18_boundaries(
    candidate_count: int, expected_status: ReplayCellStatus
) -> None:
    adapter = _SyntheticReplayAdapter(candidate_count)
    result, strategy, historical = _controller_result(adapter)
    record = next(row for row in result.records if row.target.draw_number == "2")

    assert record.status is expected_status
    if expected_status is ReplayCellStatus.TYPED_CLOSURE:
        assert record.native_ticket_count == strategy.native_ticket_count == 3
        assert record.pre_eligible is True
        assert record.reason is not None and "2 of 3" in record.reason
        assert record.tickets == record.evaluations == ()
        capturing_store = _CapturingBackfillStore()
        store: BackfillStore = capturing_store
        backfill = ReplayBackfill(
            adapter=adapter,
            strategies=(strategy,),
            draws=historical,
            source_identity="synthetic-k235-closure",
            store=store,
            execution_version="typed-closure-v2",
        )
        summary = backfill.execute(BackfillSelection(latest=1))
        assert summary["newly_calculated_count"] == 1
        assert len(capturing_store.saved_cells) == 1
        payload = capturing_store.saved_cells[0]
        assert payload["execution_status"] == "TYPED_CLOSURE"
        assert payload["expected_native_ticket_count"] == 3
        assert payload["combination_success"] is None
        assert payload["predicted_tickets"] == []
        assert payload["prize_results"] == []
    else:
        assert record.native_ticket_count == 3
        assert len(record.tickets) == len(record.evaluations) == 3
        assert all(len(ticket.main_numbers) == 6 for ticket in record.tickets)
        assert all(len(set(ticket.main_numbers)) == 6 for ticket in record.tickets)
        assert all(
            set(ticket.main_numbers) <= set(range(1, candidate_count + 1))
            for ticket in record.tickets
        )


@pytest.mark.parametrize(
    ("candidate_count", "expected_status"),
    [(13, "TYPED_CLOSURE"), (14, "COMPLETE"), (17, "TYPED_CLOSURE"), (18, "COMPLETE")],
)
def test_exact_native_synthetic_boundaries_keep_closure_outcomes_null(
    candidate_count: int, expected_status: str
) -> None:
    row = _native_row(candidate_count)
    persisted_row = json.loads(json.dumps(row))

    assert persisted_row["replay_status"] == expected_status
    if expected_status == "TYPED_CLOSURE":
        assert persisted_row["native_ticket_count"] == 3
        assert persisted_row["actual_native_ticket_count"] == 2
        assert persisted_row["reason"] is not None and "2 of 3" in persisted_row["reason"]
        assert persisted_row["native_portfolio"] is None
        assert persisted_row["ticket_evaluations"] is None
        assert persisted_row["official_any_prize"] is None
        assert persisted_row["best_official_prize"] is None
    else:
        assert persisted_row["actual_native_ticket_count"] == 3
        assert persisted_row["official_any_prize"] is False
        assert len(persisted_row["ticket_evaluations"]) == 3
        assert all(
            set(ticket["predicted_main_numbers"]) <= set(range(1, candidate_count + 1))
            for ticket in persisted_row["ticket_evaluations"]
        )


def test_unclassified_errors_invalid_output_and_missing_history_are_not_closures() -> None:
    failure_result, _strategy_value, _draws = _controller_result(
        _SyntheticReplayAdapter(14, failure="value_error")
    )
    failure_record = next(row for row in failure_result.records if row.target.draw_number == "2")
    invalid_result, _strategy_value, _draws = _controller_result(
        _SyntheticReplayAdapter(14, failure="invalid_output")
    )
    invalid_record = next(row for row in invalid_result.records if row.target.draw_number == "2")
    misbound_result, _strategy_value, _draws = _controller_result(
        _SyntheticReplayAdapter(13, failure="misbound_closure")
    )
    misbound_record = next(row for row in misbound_result.records if row.target.draw_number == "2")
    short_history_result, _strategy_value, _draws = _controller_result(
        _SyntheticReplayAdapter(14), min_history=2
    )
    short_history_record = next(
        row for row in short_history_result.records if row.target.draw_number == "2"
    )

    assert failure_record.status is ReplayCellStatus.FAILED
    assert invalid_record.status is ReplayCellStatus.FAILED
    assert misbound_record.status is ReplayCellStatus.FAILED
    assert short_history_record.status is ReplayCellStatus.NOT_ELIGIBLE

    assert _native_row(14, failure="value_error")["replay_status"] == "EXECUTION_FAILURE"
    assert _native_row(14, failure="invalid_output")["replay_status"] == "EXECUTION_FAILURE"
    assert (
        _native_row(14, failure="insufficient_history", min_history=2)["replay_status"]
        == "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS"
    )


def test_misbound_source_closure_falls_back_to_execution_failure() -> None:
    row = _native_row(13, exception_strategy_id="different_strategy")
    assert row["replay_status"] == "EXECUTION_FAILURE"
    assert row["official_any_prize"] is None


def test_typed_closure_and_absent_cells_are_unknown_not_misses() -> None:
    target = {
        "run_id": "synthetic-run",
        "target_draw_id": "2",
        "target_draw_date": "2026-01-02",
        "main": "[1,2,3,4,5,6]",
        "special": "[7]",
    }
    closure_cell: JsonObject = {
        "run_id": "synthetic-run",
        "target_draw_id": "2",
        "target_draw_date": "2026-01-02",
        "strategy_id": "synthetic__k235_closure__v2",
        "strategy_version": "v2",
        "execution_version": "typed-closure-v2",
        "dataset_identity": "synthetic-dataset",
        "execution_status": "TYPED_CLOSURE",
        "expected_ticket_count": 3,
        "ticket_count": 3,
        "ticket_evidence_valid": False,
        "payload_json": "{}",
        "tickets": [],
    }
    missing_cell: JsonObject = {**closure_cell, "execution_status": "MISSING"}
    for cells in ([closure_cell], [missing_cell]):
        row = aggregate_ranking("BIG_LOTTO", "FULL", [target], cells, {})[0]
        assert row["evaluated"] == 0
        assert row["unknown"] == 1
        assert row["successes"] == 0
        assert row["rate"] is None


def test_synthetic_denominator_ledger_keeps_closure_failed_and_missing_out_of_misses() -> None:
    records = (
        [("COMPLETE", True, True)]
        + [("COMPLETE", True, False)] * 3
        + [("FAILED", True, None), ("TYPED_CLOSURE", True, None)]
        + [("NOT_ELIGIBLE", False, None)] * 2
        + [("MISSING", True, None)] * 2
    )
    expected = len(records)
    pre_eligible = sum(eligible for _status, eligible, _success in records)
    complete = [row for row in records if row[0] == "COMPLETE"]
    successes = sum(success is True for _status, _eligible, success in complete)
    misses = sum(success is False for _status, _eligible, success in records)

    assert (len(records), pre_eligible, len(complete), successes, misses) == (10, 8, 4, 1, 3)
    assert len(complete) / expected == pytest.approx(4 / 10)
    assert len(complete) / pre_eligible == pytest.approx(4 / 8)
    assert successes / len(complete) == pytest.approx(1 / 4)


def test_exact_native_window_reaggregation_excludes_typed_closure() -> None:
    from lottolab.domain.exact_native_replay import evaluate_window_reaggregation_eligibility

    rows = [
        {"target_draw_number": "1", "replay_status": "COMPLETE"},
        {
            "target_draw_number": "2",
            "replay_status": "TYPED_CLOSURE",
            "reason": "SourceNativePortfolioClosure: 2 of 3",
        },
    ]
    result = evaluate_window_reaggregation_eligibility(
        window_name="FULL",
        window_draw_numbers=("1", "2"),
        evidence_rows=rows,
    )

    assert result.metric_status == "AVAILABLE"
    assert result.rankable is True
    assert result.available_observation_count == 1
    assert result.excluded_observation_count == 1
    assert result.failure_count == 0
    assert result.coverage == pytest.approx(1.0)
