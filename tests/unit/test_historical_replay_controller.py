"""Focused acceptance tests for the shared historical replay controller."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    Daily539ReplayAdapter,
    PowerLottoReplayAdapter,
    binding_from_implementation,
    binding_from_p638_spec,
)
from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayController,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ComparisonVerdict,
    HistoricalReplayMode,
    HistoricalReplayRequest,
    ReplayBehavior,
    ReplayCellStatus,
    ReplayDraw,
    ReplayEvaluation,
    ReplaySourceSnapshot,
    ReplayStoredTarget,
    ReplayStoredTicket,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.strategies.adapters.daily539_wave1 import Daily539MarkovColdAdapter
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES


def _draw(number: int, *, lottery: LotteryType = LotteryType.DAILY_539) -> ReplayDraw:
    main_numbers = tuple(
        sorted(((number * 7 + offset * 8) % 39) + 1 for offset in range(5))
    )
    return ReplayDraw(
        lottery_type=lottery,
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 1),
        main_numbers=main_numbers if lottery is LotteryType.DAILY_539 else (1, 2, 3, 4, 5, 6),
        special_number=None if lottery is LotteryType.DAILY_539 else (number % 8) + 1,
    )


def _strategy(
    strategy_id: str = "fixture",
    *,
    behavior: ReplayBehavior = ReplayBehavior.DETERMINISTIC,
    native_ticket_count: int = 1,
    min_history: int = 0,
    version: str = "v1",
) -> ReplayStrategy:
    return ReplayStrategy(
        strategy_id=strategy_id,
        strategy_name=f"Fixture {strategy_id}",
        strategy_version=version,
        behavior=behavior,
        native_ticket_count=native_ticket_count,
        min_history=min_history,
    )


class _FakeDailyAdapter:
    lottery_type = LotteryType.DAILY_539

    def __init__(self, *, native_ticket_count: int = 1) -> None:
        self.native_ticket_count = native_ticket_count
        self.histories: list[tuple[str, ...]] = []

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        self.histories.append(tuple(draw.draw_number for draw in history))
        return tuple(
            ReplayTicket(
                ticket_position=position,
                main_numbers=tuple(range(position, position + 5)),
            )
            for position in range(1, strategy.native_ticket_count + 1)
        )

    def evaluate(
        self,
        strategy: ReplayStrategy,
        ticket: ReplayTicket,
        target: ReplayDraw,
    ) -> ReplayEvaluation:
        return ReplayEvaluation(
            zone1_hits=0,
            zone2_hit=False,
            is_winner=False,
            prize_tier=None,
        )


def _request(
    mode: HistoricalReplayMode,
    *,
    historical: tuple[ReplayDraw, ...],
    official: tuple[ReplayDraw, ...] = (),
    strategies: tuple[ReplayStrategy, ...] = (_strategy(),),
    stored_targets: tuple[ReplayStoredTarget, ...] = (),
    stored_tickets: tuple[ReplayStoredTicket, ...] = (),
    cutoff: str | None = None,
) -> HistoricalReplayRequest:
    return HistoricalReplayRequest(
        lottery_type=LotteryType.DAILY_539,
        mode=mode,
        source=ReplaySourceSnapshot(
            lottery_type=LotteryType.DAILY_539,
            historical_draws=historical,
            official_draws=official,
            stored_targets=stored_targets,
            stored_tickets=stored_tickets,
        ),
        strategies=strategies,
        cutoff_draw_number=cutoff,
    )


def test_incremental_refresh_only_executes_new_official_draws() -> None:
    adapter = _FakeDailyAdapter()
    controller = HistoricalReplayController(adapter)
    result = controller.execute(
        _request(
            HistoricalReplayMode.INCREMENTAL_REFRESH,
            historical=(_draw(1), _draw(2)),
            official=(_draw(1), _draw(2), _draw(3), _draw(4)),
        )
    )

    assert result.added_draws == 2
    assert result.target_count == 2
    assert [record.target.draw_number for record in result.records] == ["3", "4"]
    assert adapter.histories == [("1", "2"), ("1", "2", "3")]
    assert all(
        record.target.draw_number not in {row.draw_number for row in record.causal_history}
        for record in result.records
    )
    assert result.comparison_verdict is ComparisonVerdict.NORMAL


def test_reconcile_repairs_only_missing_and_partial_cells() -> None:
    strategy = _strategy(native_ticket_count=2)
    stored_target = ReplayStoredTarget(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="1",
        target_draw_date=_draw(1).draw_date,
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        expected_ticket_count=2,
        status=ReplayCellStatus.COMPLETE,
    )
    stored_ticket = ReplayStoredTicket(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="1",
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        ticket_position=1,
    )
    result = HistoricalReplayController(_FakeDailyAdapter(native_ticket_count=2)).execute(
        _request(
            HistoricalReplayMode.RECONCILE,
            historical=(_draw(1), _draw(2), _draw(3)),
            strategies=(strategy,),
            stored_targets=(stored_target,),
            stored_tickets=(stored_ticket,),
        )
    )

    assert result.partial_count == 1
    assert result.missing_count == 2
    assert result.comparison_verdict is ComparisonVerdict.ABNORMAL
    assert {(cell.target_draw_number, cell.strategy_id) for cell in result.repair_plan} == {
        ("1", "fixture"),
        ("2", "fixture"),
        ("3", "fixture"),
    }
    first_cell = next(cell for cell in result.repair_plan if cell.target_draw_number == "1")
    assert first_cell.missing_ticket_positions == (2,)


def test_full_replay_uses_strictly_prior_history_and_does_not_need_persistence() -> None:
    adapter = _FakeDailyAdapter()
    strategy = _strategy(min_history=1)
    result = HistoricalReplayController(adapter).execute(
        _request(
            HistoricalReplayMode.FULL_REPLAY,
            historical=(_draw(1), _draw(2), _draw(3)),
            strategies=(strategy,),
            cutoff="3",
        )
    )

    assert result.historical_start == "1"
    assert result.historical_cutoff == "3"
    assert result.pre_eligible_target_count == 2
    assert adapter.histories == [("1",), ("1", "2")]
    assert result.native_ticket_count == 2
    assert all(record.evaluations for record in result.records if record.tickets)


def test_target_specific_native_ticket_counts_are_preserved() -> None:
    class _VariableCountAdapter(_FakeDailyAdapter):
        def expected_native_ticket_count(
            self,
            strategy: ReplayStrategy,
            history: tuple[ReplayDraw, ...],
            target: ReplayDraw,
        ) -> int:
            del strategy, history
            return int(target.draw_number)

        def generate(
            self,
            strategy: ReplayStrategy,
            history: tuple[ReplayDraw, ...],
            target: ReplayDraw,
        ) -> tuple[ReplayTicket, ...]:
            del strategy, history
            count = int(target.draw_number)
            return tuple(
                ReplayTicket(
                    ticket_position=position,
                    main_numbers=tuple(range(position, position + 5)),
                )
                for position in range(1, count + 1)
            )

    strategy = _strategy(native_ticket_count=1)
    result = HistoricalReplayController(_VariableCountAdapter()).execute(
        _request(
            HistoricalReplayMode.FULL_REPLAY,
            historical=(_draw(1), _draw(2), _draw(3)),
            strategies=(strategy,),
            cutoff="3",
        )
    )

    assert result.expected_native_ticket_count == 6
    assert result.native_ticket_count == 6
    assert [record.expected_native_ticket_count for record in result.records] == [1, 2, 3]
    assert [len(record.tickets) for record in result.records] == [1, 2, 3]


def test_deterministic_mismatch_is_abnormal() -> None:
    strategy = _strategy()
    stored_target = ReplayStoredTarget(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="1",
        target_draw_date=_draw(1).draw_date,
        strategy_id="fixture",
        strategy_version="v1",
        expected_ticket_count=1,
        status=ReplayCellStatus.COMPLETE,
    )
    stored_ticket = ReplayStoredTicket(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="1",
        strategy_id="fixture",
        strategy_version="v1",
        ticket_position=1,
        main_numbers=(30, 31, 32, 33, 34),
    )
    result = HistoricalReplayController(_FakeDailyAdapter()).execute(
        _request(
            HistoricalReplayMode.RECONCILE,
            historical=(_draw(1),),
            strategies=(strategy,),
            stored_targets=(stored_target,),
            stored_tickets=(stored_ticket,),
        )
    )

    assert result.deterministic_mismatch_count == 1
    assert result.comparison_verdict is ComparisonVerdict.ABNORMAL
    assert result.repair_plan[0].reasons == ("DETERMINISTIC_OUTPUT_MISMATCH",)


@pytest.mark.parametrize(
    ("behavior", "expected_verdict"),
    [
        (ReplayBehavior.SEEDED_STOCHASTIC, ComparisonVerdict.NORMAL),
        (ReplayBehavior.LEGACY_NONDETERMINISTIC, ComparisonVerdict.REVIEW),
    ],
)
def test_nondeterministic_classification_is_explicit(
    behavior: ReplayBehavior, expected_verdict: ComparisonVerdict
) -> None:
    strategy = _strategy(behavior=behavior)
    stored_target = ReplayStoredTarget(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="1",
        target_draw_date=_draw(1).draw_date,
        strategy_id="fixture",
        strategy_version="v1",
        expected_ticket_count=1,
        status=ReplayCellStatus.COMPLETE,
    )
    stored_ticket = ReplayStoredTicket(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="1",
        strategy_id="fixture",
        strategy_version="v1",
        ticket_position=1,
        main_numbers=(30, 31, 32, 33, 34),
    )
    result = HistoricalReplayController(_FakeDailyAdapter()).execute(
        _request(
            HistoricalReplayMode.RECONCILE,
            historical=(_draw(1),),
            strategies=(strategy,),
            stored_targets=(stored_target,),
            stored_tickets=(stored_ticket,),
        )
    )

    assert result.stochastic_difference_count == 1
    assert result.comparison_verdict is expected_verdict


def test_version_change_is_review_and_causal_metadata_error_is_abnormal() -> None:
    strategy = _strategy(version="v2")
    stored_target = ReplayStoredTarget(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="2",
        target_draw_date=_draw(2).draw_date,
        strategy_id="fixture",
        strategy_version="v1",
        expected_ticket_count=1,
        status=ReplayCellStatus.COMPLETE,
        cutoff_draw_number="2",
    )
    stored_ticket = ReplayStoredTicket(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="2",
        strategy_id="fixture",
        strategy_version="v1",
        ticket_position=1,
    )
    result = HistoricalReplayController(_FakeDailyAdapter()).execute(
        _request(
            HistoricalReplayMode.RECONCILE,
            historical=(_draw(1), _draw(2)),
            strategies=(strategy,),
            stored_targets=(stored_target,),
            stored_tickets=(stored_ticket,),
        )
    )

    assert result.strategy_version_change_count >= 1
    assert result.causal_violation_count == 1
    assert result.comparison_verdict is ComparisonVerdict.ABNORMAL


def test_inconsistent_target_metadata_is_abnormal() -> None:
    strategy = _strategy()
    stored_target = ReplayStoredTarget(
        lottery_type=LotteryType.DAILY_539,
        target_draw_number="1",
        target_draw_date=_draw(1).draw_date + timedelta(days=1),
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        expected_ticket_count=strategy.native_ticket_count,
        status=ReplayCellStatus.COMPLETE,
    )
    result = HistoricalReplayController(_FakeDailyAdapter()).execute(
        _request(
            HistoricalReplayMode.RECONCILE,
            historical=(_draw(1),),
            strategies=(strategy,),
            stored_targets=(stored_target,),
        )
    )

    assert result.comparison_verdict is ComparisonVerdict.ABNORMAL
    assert "INCONSISTENT_TARGET_METADATA" in result.reasons


def test_t539_adapter_reuses_existing_native_ticket_contract() -> None:
    draws = tuple(_draw(index) for index in range(1, 102))
    strategy = Daily539ReplayAdapter().strategies[0]
    result = HistoricalReplayController(Daily539ReplayAdapter()).execute(
        _request(
            HistoricalReplayMode.FULL_REPLAY,
            historical=draws,
            strategies=(strategy,),
            cutoff="101",
        )
    )

    record = next(record for record in result.records if record.target.draw_number == "101")
    assert record.status is ReplayCellStatus.COMPLETE
    assert len(record.tickets) == strategy.native_ticket_count
    assert len(record.evaluations) == len(record.tickets)


def test_t539_single_ticket_adapter_defaults_to_one_native_position() -> None:
    draws = tuple(_draw(index) for index in range(1, 102))
    binding = binding_from_implementation(Daily539MarkovColdAdapter())
    adapter = Daily539ReplayAdapter((binding,))
    result = HistoricalReplayController(adapter).execute(
        _request(
            HistoricalReplayMode.FULL_REPLAY,
            historical=draws,
            strategies=adapter.strategies,
            cutoff="101",
        )
    )

    record = next(record for record in result.records if record.target.draw_number == "101")
    assert record.status is ReplayCellStatus.COMPLETE
    assert tuple(ticket.ticket_position for ticket in record.tickets) == (1,)


def _power_draw(number: int) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 1),
        main_numbers=tuple(sorted(((number * 7 + offset * 3) % 38) + 1 for offset in range(6))),
        special_number=(number % 8) + 1,
    )


def test_p638_adapter_preserves_every_native_position_and_second_zone() -> None:
    binding = binding_from_p638_spec(WAVE1_STRATEGIES[0])
    adapter = PowerLottoReplayAdapter((binding,))
    strategy = adapter.strategies[0]
    draws = tuple(_power_draw(index) for index in range(1, 32))
    source = ReplaySourceSnapshot(
        lottery_type=LotteryType.POWER_LOTTO,
        historical_draws=draws,
    )
    result = HistoricalReplayController(adapter).execute(
        HistoricalReplayRequest(
            lottery_type=LotteryType.POWER_LOTTO,
            mode=HistoricalReplayMode.FULL_REPLAY,
            source=source,
            strategies=(strategy,),
            cutoff_draw_number="31",
        )
    )

    record = next(record for record in result.records if record.target.draw_number == "31")
    assert record.status is ReplayCellStatus.COMPLETE
    assert tuple(ticket.ticket_position for ticket in record.tickets) == (1, 2)
    assert all(ticket.special_number is not None for ticket in record.tickets)
    assert len({ticket.special_number for ticket in record.tickets}) == 1


def test_big_lotto_enters_shared_replay_controller() -> None:
    class _B649Implementation:
        strategy_id = "b649-fixture"
        strategy_name = "B649 fixture"
        strategy_version = "v1"
        min_history = 0

        def get_one_bet(
            self,
            history: object,
            lottery_type: LotteryType,
        ) -> tuple[tuple[int, ...], None]:
            del history, lottery_type
            return (1, 2, 3, 4, 5, 6), None

    binding = binding_from_implementation(_B649Implementation())
    adapter = BigLottoReplayAdapter((binding,))
    draws = (
        ReplayDraw(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number="1",
            draw_date=date(2026, 1, 1),
            main_numbers=(7, 8, 9, 10, 11, 12),
            special_number=13,
        ),
        ReplayDraw(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number="2",
            draw_date=date(2026, 1, 2),
            main_numbers=(1, 2, 3, 4, 5, 6),
            special_number=7,
        ),
    )
    result = HistoricalReplayController(adapter).execute(
        HistoricalReplayRequest(
            lottery_type=LotteryType.BIG_LOTTO,
            mode=HistoricalReplayMode.FULL_REPLAY,
            source=ReplaySourceSnapshot(
                lottery_type=LotteryType.BIG_LOTTO,
                historical_draws=draws,
            ),
            strategies=adapter.strategies,
            cutoff_draw_number="2",
        )
    )

    record = result.records[-1]
    assert record.status is ReplayCellStatus.COMPLETE
    assert tuple(ticket.ticket_position for ticket in record.tickets) == (1,)
    assert record.evaluations[0].is_winner is True
    assert record.evaluations[0].prize_tier == "FIRST"
