"""Executable old/new parity for the legacy frontend Unified Ensemble donor."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

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
    BigLottoFrontendUnifiedEnsembleAdvancedAdapter,
    BigLottoFrontendUnifiedEnsembleCombinedAdapter,
    BigLottoFrontendUnifiedEnsembleWeightedAdapter,
    CausalDrawRow,
)
from lottolab.strategies.adapters import biglotto_frontend_unified_ensemble as ensemble_module
from lottolab.strategies.adapters.base import (
    BetAdapter,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_frontend_unified_ensemble import (
    ticket_for_mode,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

WEIGHTED_ID = "legacy_biglotto__frontend_unified_ensemble_weighted__8f1183a9d8a7"
COMBINED_ID = "legacy_biglotto__frontend_unified_ensemble_combined__8f1183a9d8a7"
ADVANCED_ID = "legacy_biglotto__frontend_unified_ensemble_advanced__8f1183a9d8a7"
SOURCE_SHA256 = (
    "8f1183a9d8a797f5481f875cdcf3d6bd803cd1584256af9de43913d30d57fe58"
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
    return _row(f"stride-{index}", numbers)


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    """LottoLab's canonical oldest-first causal history."""

    return tuple(_stride_row(index) for index in range(length))


def _edge() -> tuple[CausalDrawRow, ...]:
    return (
        _row("edge-0", (1, 2, 3, 4, 5, 6)),
        _row("edge-1", (44, 45, 46, 47, 48, 49)),
    )


# Captured by executing UnifiedEnsembleStrategy.js with a synchronous
# calculateFrequency/calculateMissingValues stub and the same FormulaRandom
# sequence patched onto Math.random for weighted/advanced.
COMBINED_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...]]] = {
    "stride-1": (_history(1), (1, 9, 17, 25, 33, 41)),
    "stride-50": (_history(50), (2, 10, 18, 26, 42, 43)),
    "stride-301": (_history(301), (8, 16, 24, 32, 48, 49)),
    "edge": (_edge(), (1, 2, 3, 4, 5, 6)),
}
COOCCURRENCE_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...]]] = {
    "stride-1": (_history(1), (1, 2, 3, 4, 5, 6)),
    "stride-10": (_history(10), (2, 9, 17, 25, 33, 41)),
    "edge": (_edge(), (1, 2, 3, 4, 5, 6)),
    "single": ((_row("z-0", (1, 2, 3, 4, 5, 6)),), (1, 2, 3, 4, 5, 6)),
}
FEATURE_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...]]] = {
    "stride-1": (_history(1), (1, 9, 17, 25, 33, 41)),
    "stride-20": (_history(20), (4, 12, 14, 22, 38, 46)),
    "stride-50": (_history(50), (2, 10, 18, 26, 34, 42)),
    "edge": (_edge(), (14, 15, 16, 24, 25, 26)),
}
BOOSTING_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...]]] = {
    "stride-1": (_history(1), (1, 9, 17, 25, 33, 41)),
    "stride-10": (_history(10), (3, 11, 19, 27, 35, 43)),
    "edge": (_edge(), (1, 2, 3, 4, 5, 6)),
}
WEIGHTED_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...], int]] = {
    "stride-1": (_history(1), (1, 9, 17, 25, 33, 41), 89_821),
    "stride-10": (_history(10), (1, 10, 18, 26, 34, 42), 60_000),
    "edge": (_edge(), (44, 45, 46, 47, 48, 49), 72_773),
}


@pytest.mark.parametrize("case", tuple(COMBINED_GOLDENS))
def test_combined_matches_executed_donor_golden(case: str) -> None:
    history, expected = COMBINED_GOLDENS[case]
    execution = BigLottoFrontendUnifiedEnsembleCombinedAdapter().get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == expected
    assert execution.emitted_main_numbers == expected
    assert execution.special_number is None


@pytest.mark.parametrize("case", tuple(COOCCURRENCE_GOLDENS))
def test_cooccurrence_matches_executed_donor_golden(case: str) -> None:
    history, expected = COOCCURRENCE_GOLDENS[case]
    newest = tuple(reversed(history))
    assert ticket_for_mode(newest, "cooccurrence") == expected


@pytest.mark.parametrize("case", tuple(FEATURE_GOLDENS))
def test_feature_weighted_matches_executed_donor_golden(case: str) -> None:
    history, expected = FEATURE_GOLDENS[case]
    newest = tuple(reversed(history))
    assert ticket_for_mode(newest, "feature_weighted") == expected


@pytest.mark.parametrize("case", tuple(BOOSTING_GOLDENS))
def test_boosting_matches_executed_donor_golden(case: str) -> None:
    history, expected = BOOSTING_GOLDENS[case]
    newest = tuple(reversed(history))
    assert ticket_for_mode(newest, "boosting") == expected


@pytest.mark.parametrize("case", tuple(WEIGHTED_GOLDENS))
def test_weighted_matches_executed_donor_golden(case: str) -> None:
    history, expected, expected_calls = WEIGHTED_GOLDENS[case]
    rng = FormulaRandom()
    execution = BigLottoFrontendUnifiedEnsembleWeightedAdapter(rng).get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == expected
    assert execution.emitted_main_numbers == expected
    assert execution.special_number is None
    assert rng.calls == expected_calls


def test_advanced_equals_weighted_on_the_same_rng_stream() -> None:
    history, expected, expected_calls = WEIGHTED_GOLDENS["stride-10"]
    weighted_rng = FormulaRandom()
    advanced_rng = FormulaRandom()
    weighted = BigLottoFrontendUnifiedEnsembleWeightedAdapter(weighted_rng).get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    advanced = BigLottoFrontendUnifiedEnsembleAdvancedAdapter(advanced_rng).get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    assert weighted == advanced == (expected, None)
    assert weighted_rng.calls == advanced_rng.calls == expected_calls


def test_history_order_uses_newest_draw_as_cooccurrence_leaders() -> None:
    history = _edge()
    newest = tuple(reversed(history))
    assert newest[0].numbers == (44, 45, 46, 47, 48, 49)
    assert ticket_for_mode(newest, "cooccurrence") == (1, 2, 3, 4, 5, 6)


def test_all_zero_cooccurrence_tie_break_is_ascending_integer_keys() -> None:
    history = (_row("z-0", (1, 2, 3, 4, 5, 6)),)
    assert ticket_for_mode(tuple(reversed(history)), "cooccurrence") == (
        1,
        2,
        3,
        4,
        5,
        6,
    )


def test_combined_assigns_tail_weight_and_never_applies_it() -> None:
    module_file = ensemble_module.__file__
    assert module_file is not None
    source_text = Path(module_file).read_text(encoding="utf-8")
    assert '"tail": 0.15' in source_text
    assert 'weights["tail"]' not in source_text


def test_minimum_history_is_insufficient_history() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendUnifiedEnsembleCombinedAdapter().get_one_bet(
            (), LotteryType.BIG_LOTTO
        )
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendUnifiedEnsembleWeightedAdapter(FormulaRandom()).get_one_bet(
            (), LotteryType.BIG_LOTTO
        )


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendUnifiedEnsembleCombinedAdapter()
    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_weighted_does_not_seed_process_global_rng() -> None:
    source = inspect.getsource(BigLottoFrontendUnifiedEnsembleWeightedAdapter)
    assert "random.seed(" not in source
    assert "GenerateOneBetInput.seed" not in source


def _catalog_identity(
    strategy_id: str,
    adapter_cls: type[BetAdapter],
    adapter_path: str,
) -> None:
    catalog = production_catalog()
    descriptor = catalog.get(strategy_id)
    assert [item.strategy_id for item in catalog].count(strategy_id) == 1
    assert descriptor.strategy_id == adapter_cls.strategy_id
    assert descriptor.strategy_name == adapter_cls.strategy_name
    assert descriptor.version == adapter_cls.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == adapter_path
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in "".join(descriptor.provenance)
    assert ExecutableRegistry(catalog).load_adapter(strategy_id) is adapter_cls


def test_catalog_registers_three_live_ensemble_identities() -> None:
    _catalog_identity(
        WEIGHTED_ID,
        BigLottoFrontendUnifiedEnsembleWeightedAdapter,
        "lottolab.strategies.adapters.biglotto_frontend_unified_ensemble:"
        "BigLottoFrontendUnifiedEnsembleWeightedAdapter",
    )
    _catalog_identity(
        COMBINED_ID,
        BigLottoFrontendUnifiedEnsembleCombinedAdapter,
        "lottolab.strategies.adapters.biglotto_frontend_unified_ensemble:"
        "BigLottoFrontendUnifiedEnsembleCombinedAdapter",
    )
    _catalog_identity(
        ADVANCED_ID,
        BigLottoFrontendUnifiedEnsembleAdvancedAdapter,
        "lottolab.strategies.adapters.biglotto_frontend_unified_ensemble:"
        "BigLottoFrontendUnifiedEnsembleAdvancedAdapter",
    )
    catalog_ids = [item.strategy_id for item in production_catalog()]
    assert "ensemble_boosting" not in "".join(catalog_ids)
    assert WEIGHTED_ID in catalog_ids
    assert COMBINED_ID in catalog_ids
    assert ADVANCED_ID in catalog_ids


def _request(strategy_id: str, history: tuple[CausalDrawRow, ...]) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=strategy_id,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
        seed=12345,
    )


@pytest.mark.parametrize("strategy_id", (WEIGHTED_ID, COMBINED_ID, ADVANCED_ID))
def test_production_single_ticket_generation_path_is_reachable(strategy_id: str) -> None:
    result = build_production_generate_one_bet().execute(_request(strategy_id, _history(10)))
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 6
    assert result.numbers == tuple(sorted(set(result.numbers)))
    assert all(1 <= number <= 49 for number in result.numbers)
    assert result.special_number is None
    assert result.reason_code is None


@pytest.mark.parametrize("strategy_id", (WEIGHTED_ID, COMBINED_ID, ADVANCED_ID))
def test_portfolio_path_rejects_single_ticket_identity(strategy_id: str) -> None:
    result = build_production_generate_portfolio().execute(
        _request(strategy_id, _history(10))
    )
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.numbers is None
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO


def test_production_generation_never_opens_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Unified Ensemble must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    for strategy_id in (WEIGHTED_ID, COMBINED_ID, ADVANCED_ID):
        result = build_production_generate_one_bet().execute(
            _request(strategy_id, _history(10))
        )
        assert result.status is GenerateOneBetStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == 6


def test_generate_one_bet_seed_is_not_threaded_into_weighted_rng() -> None:
    history = _history(10)
    seeded = build_production_generate_one_bet().execute(_request(WEIGHTED_ID, history))
    unseeded = build_production_generate_one_bet().execute(
        GenerateOneBetInput(
            strategy_id=WEIGHTED_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
            seed=None,
        )
    )
    assert seeded.status is GenerateOneBetStatus.OK
    assert unseeded.status is GenerateOneBetStatus.OK
    module_file = ensemble_module.__file__
    assert module_file is not None
    source_text = Path(module_file).read_text(encoding="utf-8")
    assert "GenerateOneBetInput.seed" not in source_text
    assert "random.seed(" not in source_text
