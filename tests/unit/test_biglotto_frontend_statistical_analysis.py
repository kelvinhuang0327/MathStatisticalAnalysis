"""Executable old/new parity for the legacy frontend Statistical Analysis donor."""

from __future__ import annotations

import sqlite3

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import BigLottoFrontendStatisticalAnalysisAdapter
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = (
    "legacy_biglotto__frontend_statistical_analysis_strategy__a9364825de2a"
)


class FormulaRandom:
    """Fixed equivalent of the donor execution's process-global Math.random calls."""

    def __init__(self) -> None:
        self.calls = 0

    def random(self) -> float:
        value = ((self.calls * 37) % 997) / 997
        self.calls += 1
        return value


class FallbackRandom:
    """Repeat a low-number sequence that reaches the donor's fallback branch."""

    _values = (0.001, 0.03, 0.05, 0.07, 0.09, 0.11)

    def __init__(self) -> None:
        self.calls = 0

    def random(self) -> float:
        value = self._values[self.calls % len(self._values)]
        self.calls += 1
        return value


def _row(draw: str, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(draw, "2020-01-01", numbers)


def _stride_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return _row(f"frontend-statistical-analysis-{index}", numbers)


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""

    return tuple(_stride_row(index) for index in range(length))


DONOR_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...], int]] = {
    "edge": (
        (
            _row("edge-0", (1, 2, 3, 4, 5, 6)),
            _row("edge-1", (44, 45, 46, 47, 48, 49)),
        ),
        (1, 3, 5, 7, 47, 48),
        3_990,
    ),
    "tie": (
        (
            _row("tie-0", (10, 20, 30, 40, 45, 49)),
            _row("tie-1", (10, 20, 30, 40, 45, 49)),
        ),
        (1, 42, 43, 45, 47, 49),
        6_606,
    ),
    "stride-1": (_history(1), (1, 41, 42, 44, 46, 48), 3_990),
    "stride-9": (_history(9), (1, 41, 42, 44, 46, 48), 3_612),
    "stride-10": (_history(10), (1, 41, 42, 44, 46, 48), 3_990),
    "stride-50": (_history(50), (1, 41, 42, 44, 46, 48), 3_990),
}


@pytest.mark.parametrize("case", tuple(DONOR_GOLDENS))
def test_matches_executed_donor_golden(case: str) -> None:
    history, expected, expected_calls = DONOR_GOLDENS[case]
    rng = FormulaRandom()
    execution = BigLottoFrontendStatisticalAnalysisAdapter(rng).get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == expected
    assert execution.emitted_main_numbers == expected
    assert execution.special_number is None
    assert rng.calls == expected_calls


def test_reachable_donor_fallback_matches_executed_source() -> None:
    rng = FallbackRandom()
    execution = BigLottoFrontendStatisticalAnalysisAdapter(rng).get_one_bet_with_emission(
        (_row("fallback", (1, 2, 3, 4, 5, 6)),), LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == (1, 2, 3, 4, 5, 6)
    assert execution.emitted_main_numbers == (1, 2, 3, 4, 5, 6)
    assert rng.calls == 12_006


def test_minimum_history_and_output_are_sorted_legal_and_deterministic() -> None:
    adapter = BigLottoFrontendStatisticalAnalysisAdapter(FormulaRandom())
    with pytest.raises(InsufficientHistory):
        adapter.get_one_bet((), LotteryType.BIG_LOTTO)

    first = adapter.get_one_bet_with_emission(
        _history(10), LotteryType.BIG_LOTTO
    )
    second = BigLottoFrontendStatisticalAnalysisAdapter(FormulaRandom()).get_one_bet_with_emission(
        _history(10), LotteryType.BIG_LOTTO
    )
    assert first == second
    assert first.emitted_main_numbers == (1, 41, 42, 44, 46, 48)
    assert first.legal_main_numbers == (1, 41, 42, 44, 46, 48)
    assert first.special_number is None


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendStatisticalAnalysisAdapter(FormulaRandom())
    invalid = (_row("bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_catalog_and_registry_add_exactly_one_online_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert [item.strategy_id for item in catalog].count(STRATEGY_ID) == 1
    assert descriptor.strategy_id == BigLottoFrontendStatisticalAnalysisAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendStatisticalAnalysisAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendStatisticalAnalysisAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_frontend_statistical_analysis:"
        "BigLottoFrontendStatisticalAnalysisAdapter"
    )
    assert (
        "legacy_source_sha256:"
        "a9364825de2ad648bf1e9f9406f2abe52181df29aae62e587424dfc29d86984f"
        in descriptor.provenance
    )
    assert "legacy_symbol:StatisticalAnalysisStrategy.predict" in descriptor.provenance
    assert "legacy_runtime:PredictionEngine.strategies.statistical" in descriptor.provenance
    assert (
        "donor_execution:EXECUTABLE_DIRECT_NODE_MODULE_IMPORT_WITH_SYNCHRONOUS_STATISTICS_SERVICE_STUB_AND_FIXED_RANDOM_SEQUENCE"
        in descriptor.provenance
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoFrontendStatisticalAnalysisAdapter
    )


def _request(history: tuple[CausalDrawRow, ...]) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )


def test_production_single_ticket_generation_path_is_reachable() -> None:
    result = build_production_generate_one_bet().execute(_request(_history(10)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 6
    assert result.numbers == tuple(sorted(set(result.numbers)))
    assert all(1 <= number <= 49 for number in result.numbers)
    assert result.special_number is None
    assert result.reason_code is None


def test_portfolio_path_rejects_single_ticket_identity() -> None:
    result = build_production_generate_portfolio().execute(_request(_history(10)))
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.numbers is None
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO


def test_production_generation_never_opens_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Frontend Statistical Analysis Strategy must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(10)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 6
