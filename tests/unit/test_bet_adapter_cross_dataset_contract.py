"""Contract tests for the lottery-rule-driven BetAdapter/PortfolioBetAdapter base.

Covers: BIG_LOTTO adapters keep their exact prior behavior, the legacy
3-argument ``CausalDrawRow`` construction stays valid (and its shape stays
exactly ``draw, date, numbers`` — see the dependency-rule regression guards
in ``tests/architecture/test_replay_execution_dependency_rules.py`` and
``tests/architecture/test_replay_history_dependency_rules.py``, which keep
second-zone history in the separate, dataset-specific
``lottolab.domain.replay_history.ReplayCausalDrawRow`` type), invalid native
shapes fail closed per lottery, and typed DAILY_539/POWER_LOTTO adapters can
execute through the real ``BetAdapter``/``PortfolioBetAdapter`` contract (not
just a private helper) with a predicted special number preserved end to end.
"""

from __future__ import annotations

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
    validated_history,
)


def _biglotto_history(rows: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(str(index), f"2026-01-{(index % 28) + 1:02d}", (1, 2, 3, 4, 5, 6))
        for index in range(1, rows + 1)
    )


def _daily539_history(rows: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(index),
            date=f"2026-01-{(index % 28) + 1:02d}",
            numbers=(1, 2, 3, 4, 5),
        )
        for index in range(1, rows + 1)
    )


def _powerlotto_history(rows: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(index),
            date=f"2026-01-{(index % 28) + 1:02d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(1, rows + 1)
    )


class _BigLottoFixtureAdapter(BetAdapter):
    strategy_id = "fixture_biglotto_contract"
    strategy_name = "Fixture BIG_LOTTO"
    strategy_version = "v1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return (44, 43, 42, 41, 40, 39)


class _Daily539FixtureAdapter(BetAdapter):
    strategy_id = "fixture_daily539_contract"
    strategy_name = "Fixture DAILY_539"
    strategy_version = "v1"
    min_history = 1
    supported_lottery_types = (LotteryType.DAILY_539,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return (7, 14, 21, 28, 35)


class _PowerLottoFixtureAdapter(BetAdapter):
    """Its predicted special number is a fixed value, not history-derived: the
    shared CausalDrawRow contract deliberately carries only primary numbers
    (see module docstring), so a native adapter's second-zone prediction must
    come from its own logic/state rather than from ``history`` rows here."""

    strategy_id = "fixture_powerlotto_contract"
    strategy_name = "Fixture POWER_LOTTO"
    strategy_version = "v1"
    min_history = 1
    supported_lottery_types = (LotteryType.POWER_LOTTO,)

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        return (2, 4, 6, 8, 10, 12)

    def _predict_special_number(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
        main_numbers: tuple[int, ...],
    ) -> int | None:
        return 5


class _PowerLottoPortfolioFixtureAdapter(PortfolioBetAdapter):
    strategy_id = "fixture_powerlotto_portfolio_contract"
    strategy_name = "Fixture POWER_LOTTO portfolio"
    strategy_version = "v1"
    min_history = 1
    native_ticket_count = 2
    supported_lottery_types = (LotteryType.POWER_LOTTO,)

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return ((2, 4, 6, 8, 10, 12), (1, 3, 5, 7, 9, 11))

    def _predict_special_numbers(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
        tickets: tuple[tuple[int, ...], ...],
    ) -> tuple[int | None, ...]:
        return (5, 8)


# --- BIG_LOTTO backward compatibility -------------------------------------


def test_causal_draw_row_three_argument_construction_stays_valid() -> None:
    row = CausalDrawRow("1", "2026-01-01", (1, 2, 3, 4, 5, 6))

    assert row == CausalDrawRow(draw="1", date="2026-01-01", numbers=(1, 2, 3, 4, 5, 6))
    assert row.numbers == (1, 2, 3, 4, 5, 6)


def test_bet_adapter_execution_accepts_a_concrete_special_number() -> None:
    execution = BetAdapterExecution(
        emitted_main_numbers=(1, 2, 3, 4, 5, 6),
        legal_main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=5,
    )

    assert execution.special_number == 5


def test_biglotto_two_argument_validated_history_call_is_unchanged() -> None:
    history = _biglotto_history(3)

    canonical = validated_history(history, "fixture_biglotto_contract")

    assert canonical == history


def test_biglotto_adapter_execution_is_unchanged() -> None:
    adapter = _BigLottoFixtureAdapter()

    execution = adapter.get_one_bet_with_emission(_biglotto_history(1), LotteryType.BIG_LOTTO)

    assert execution.emitted_main_numbers == (44, 43, 42, 41, 40, 39)
    assert execution.legal_main_numbers == (39, 40, 41, 42, 43, 44)
    assert execution.special_number is None
    assert adapter.get_one_bet(_biglotto_history(1), LotteryType.BIG_LOTTO) == (
        (39, 40, 41, 42, 43, 44),
        None,
    )


def test_adapter_still_rejects_unsupported_lottery_type() -> None:
    adapter = _Daily539FixtureAdapter()

    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet_with_emission(_daily539_history(1), LotteryType.POWER_LOTTO)


def test_adapter_still_enforces_insufficient_history() -> None:
    class _StricterBigLottoFixtureAdapter(_BigLottoFixtureAdapter):
        min_history = 5

    with pytest.raises(InsufficientHistory):
        _StricterBigLottoFixtureAdapter().get_one_bet_with_emission(
            _biglotto_history(1), LotteryType.BIG_LOTTO
        )


# --- Invalid native shapes fail closed -------------------------------------


def test_daily539_typed_adapter_rejects_biglotto_shaped_history() -> None:
    adapter = _Daily539FixtureAdapter()
    bad_history = (CausalDrawRow("1", "2026-01-01", (1, 2, 3, 4, 5, 6)),)

    with pytest.raises(InvalidOutput):
        adapter.get_one_bet_with_emission(bad_history, LotteryType.DAILY_539)


def test_special_number_out_of_range_fails_closed() -> None:
    class _BadSpecialAdapter(_PowerLottoFixtureAdapter):
        def _predict_special_number(
            self,
            history: tuple[CausalDrawRow, ...],
            lottery_type: LotteryType,
            main_numbers: tuple[int, ...],
        ) -> int | None:
            return 9  # POWER_LOTTO's special pool is 1..8

    with pytest.raises(InvalidOutput):
        _BadSpecialAdapter().get_one_bet_with_emission(
            _powerlotto_history(1), LotteryType.POWER_LOTTO
        )


def test_special_number_undefined_for_lottery_fails_closed() -> None:
    class _BadDaily539Adapter(_Daily539FixtureAdapter):
        def _predict_special_number(
            self,
            history: tuple[CausalDrawRow, ...],
            lottery_type: LotteryType,
            main_numbers: tuple[int, ...],
        ) -> int | None:
            return 1  # DAILY_539 has no special-number pool at all

    with pytest.raises(InvalidOutput):
        _BadDaily539Adapter().get_one_bet_with_emission(
            _daily539_history(1), LotteryType.DAILY_539
        )


# --- Typed DAILY_539 / POWER_LOTTO execution --------------------------------


def test_daily539_typed_adapter_executes_legal_5_of_39_output() -> None:
    adapter = _Daily539FixtureAdapter()

    execution = adapter.get_one_bet_with_emission(_daily539_history(1), LotteryType.DAILY_539)

    assert execution.legal_main_numbers == (7, 14, 21, 28, 35)
    assert len(execution.legal_main_numbers) == 5
    assert all(1 <= number <= 39 for number in execution.legal_main_numbers)
    assert execution.special_number is None


def test_powerlotto_typed_adapter_executes_legal_6_of_38_plus_1_of_8_output() -> None:
    adapter = _PowerLottoFixtureAdapter()

    execution = adapter.get_one_bet_with_emission(_powerlotto_history(1), LotteryType.POWER_LOTTO)

    assert execution.legal_main_numbers == (2, 4, 6, 8, 10, 12)
    assert len(execution.legal_main_numbers) == 6
    assert all(1 <= number <= 38 for number in execution.legal_main_numbers)
    assert execution.special_number == 5
    assert 1 <= execution.special_number <= 8


def test_powerlotto_portfolio_typed_adapter_preserves_per_ticket_special_numbers() -> None:
    adapter = _PowerLottoPortfolioFixtureAdapter()

    executions = adapter.get_bets_with_emission(_powerlotto_history(1), LotteryType.POWER_LOTTO)

    assert [execution.special_number for execution in executions] == [5, 8]
    assert all(len(execution.legal_main_numbers) == 6 for execution in executions)
    assert all(
        all(1 <= number <= 38 for number in execution.legal_main_numbers)
        for execution in executions
    )
