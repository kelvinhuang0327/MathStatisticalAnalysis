"""Executable old/new parity for the legacy frontend Wheeling donor."""

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
from lottolab.strategies.adapters import (
    BigLottoFrontendWheelingAdapter,
    CausalDrawRow,
)
from lottolab.strategies.adapters.base import (
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__frontend_wheeling_strategy__ce978baff05b"
SOURCE_SHA256 = (
    "ce978baff05b9b1307794c14d048b46e682c1a317b21e34f4b0463c86988365d"
)
ADAPTER_PATH = (
    "lottolab.strategies.adapters.biglotto_frontend_wheeling:"
    "BigLottoFrontendWheelingAdapter"
)


class FormulaRandom:
    """Fixed equivalent of the donor execution's process-global Math.random calls."""

    def __init__(self) -> None:
        self.calls = 0

    def random(self) -> float:
        value = ((self.calls * 37) % 997) / 997
        self.calls += 1
        return value


def _row(draw: str, numbers: tuple[int, ...]) -> CausalDrawRow:
    return CausalDrawRow(draw, "2020-01-01", numbers)


def _stride_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return _row(f"frontend-wheeling-{index}", numbers)


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""

    return tuple(_stride_row(index) for index in range(length))


# Captured by directly importing and executing the donor JavaScript module with
# the same fixed Math.random sequence, then checking the target port.
DONOR_GOLDENS: dict[
    str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...], int]
] = {
    "edge": (
        (
            _row("edge-0", (1, 2, 3, 4, 5, 6)),
            _row("edge-1", (44, 45, 46, 47, 48, 49)),
        ),
        (4, 5, 7, 9, 12, 40),
        2_599,
    ),
    "tie": (
        (
            _row("tie-0", (10, 20, 30, 40, 45, 49)),
            _row("tie-1", (10, 20, 30, 40, 45, 49)),
        ),
        (1, 3, 5, 8, 10, 20),
        2_599,
    ),
    "stride-1": (_history(1), (6, 9, 10, 17, 25, 46), 2_599),
    "stride-9": (_history(9), (8, 9, 17, 25, 33, 46), 2_599),
    "stride-10": (_history(10), (6, 9, 10, 11, 17, 46), 2_599),
    "stride-50": (_history(50), (6, 9, 10, 17, 25, 46), 2_599),
}


@pytest.mark.parametrize("case", tuple(DONOR_GOLDENS))
def test_matches_executed_donor_golden(case: str) -> None:
    history, expected, expected_calls = DONOR_GOLDENS[case]
    rng = FormulaRandom()
    execution = BigLottoFrontendWheelingAdapter(rng).get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == expected
    assert execution.emitted_main_numbers == expected
    assert execution.special_number is None
    assert rng.calls == expected_calls


def test_target_empty_boundary_is_insufficient_history() -> None:
    # The executed source accepts empty history; the native contract closes it
    # at its explicit minimum-history boundary.
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendWheelingAdapter(FormulaRandom()).get_one_bet(
            (), LotteryType.BIG_LOTTO
        )


def test_output_contract_is_one_sorted_legal_ticket() -> None:
    execution = BigLottoFrontendWheelingAdapter(FormulaRandom()).get_one_bet_with_emission(
        _history(10), LotteryType.BIG_LOTTO
    )
    assert len(execution.legal_main_numbers) == 6
    assert execution.legal_main_numbers == tuple(sorted(set(execution.legal_main_numbers)))
    assert all(1 <= number <= 49 for number in execution.legal_main_numbers)
    assert execution.emitted_main_numbers == execution.legal_main_numbers
    assert execution.special_number is None


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendWheelingAdapter(FormulaRandom())
    invalid = (_row("bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_catalog_and_registry_add_exactly_one_online_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert len(catalog) == 127
    assert [item.strategy_id for item in catalog].count(STRATEGY_ID) == 1
    assert descriptor.strategy_id == BigLottoFrontendWheelingAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoFrontendWheelingAdapter.strategy_name
    assert descriptor.version == BigLottoFrontendWheelingAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == ADAPTER_PATH
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "legacy_symbol:WheelingStrategy.predict" in descriptor.provenance
    assert "legacy_runtime:PredictionEngine.strategies.wheeling" in descriptor.provenance
    assert "legacy_history_order:FREQUENCY_ORDER_INDEPENDENT" in descriptor.provenance
    assert "target_history_order:OLDEST_FIRST" in descriptor.provenance
    assert (
        "donor_execution:EXECUTABLE_DIRECT_NODE_MODULE_IMPORT_WITH_SYNCHRONOUS_"
        "STATISTICS_SERVICE_STUB_AND_FIXED_RANDOM_SEQUENCE"
        in descriptor.provenance
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoFrontendWheelingAdapter
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
        raise AssertionError("Frontend Wheeling Strategy must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_one_bet().execute(_request(_history(10)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 6
