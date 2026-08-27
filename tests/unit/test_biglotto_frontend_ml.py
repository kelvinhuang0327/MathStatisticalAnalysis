"""Executable old/new parity for the legacy frontend ML donor."""

from __future__ import annotations

import inspect
from typing import Final

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetStatus,
    build_production_generate_one_bet,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import (
    BigLottoFrontendMLFeatureWeightedAdapter,
    BigLottoFrontendMLGeneticAdapter,
    BigLottoFrontendMLRandomForestAdapter,
    CausalDrawRow,
)
from lottolab.strategies.adapters.base import (
    BetAdapter,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_frontend_ml import (
    ticket_for_mode,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

FEATURE_WEIGHTED_ID: Final = "legacy_biglotto__frontend_ml_features__3a4324bc2aa9"
RANDOM_FOREST_ID: Final = "legacy_biglotto__frontend_ml_forest__3a4324bc2aa9"
GENETIC_ID: Final = "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9"
SOURCE_SHA256: Final = "3a4324bc2aa95dc03aabef21e1b5b8682e4ce05385ce5169a3ff349605df95db"


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


def _make_stride_history(
    length: int, mul: int = 7, step_mul: int = 11
) -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for i in range(length):
        numbers = tuple(sorted(((i * mul + step * step_mul) % 49) + 1 for step in range(6)))
        rows.append(_row(f"stride-len-{i}", numbers))
    return tuple(rows)


def _edge() -> tuple[CausalDrawRow, ...]:
    return (
        _row("edge-0", (1, 2, 3, 4, 5, 6)),
        _row("edge-1", (44, 45, 46, 47, 48, 49)),
    )


def _tie_draw() -> tuple[CausalDrawRow, ...]:
    return (
        _row("tie-0", (10, 20, 30, 40, 45, 49)),
        _row("tie-1", (10, 20, 30, 40, 45, 49)),
    )


# Captured by executing MLStrategy.js with a synchronous
# calculateFrequency/calculateMissingValues stub and the same FormulaRandom
# sequence patched onto Math.random.
FEATURE_WEIGHTED_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...], int]] = {
    "stride-1": (_history(1), (1, 9, 17, 25, 33, 41), 49),
    "stride-10": (_history(10), (17, 18, 25, 26, 41, 42), 49),
    "stride-50": (_history(50), (9, 17, 24, 25, 41, 49), 49),
    "stride-100": (_make_stride_history(100), (19, 23, 27, 41, 45, 49), 49),
    "stride-500": (_make_stride_history(500), (19, 21, 23, 26, 45, 48), 49),
    "edge": (_edge(), (44, 45, 46, 47, 48, 49), 49),
    "tie-draw": (_tie_draw(), (10, 20, 30, 40, 45, 49), 49),
}

RANDOM_FOREST_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...], int]] = {
    "stride-1": (_history(1), (1, 9, 17, 25, 33, 41), 2723),
    "stride-10": (_history(10), (9, 17, 18, 41, 42, 45), 2723),
    "stride-50": (_history(50), (18, 19, 42, 43, 44, 45), 2723),
    "stride-100": (_make_stride_history(100), (15, 17, 33, 37, 44, 48), 2723),
    "stride-500": (_make_stride_history(500), (13, 17, 33, 35, 40, 44), 2723),
    "edge": (_edge(), (5, 44, 45, 46, 47, 48), 2723),
    "tie-draw": (_tie_draw(), (10, 20, 30, 40, 45, 49), 2723),
}

GENETIC_GOLDENS: dict[str, tuple[tuple[CausalDrawRow, ...], tuple[int, ...], int]] = {
    "stride-1": (_history(1), (6, 9, 10, 17, 24, 41), 19936),
    "stride-10": (_history(10), (4, 5, 28, 29, 33, 36), 19674),
    "stride-50": (_history(50), (4, 9, 19, 26, 28, 31), 19850),
    "stride-100": (_make_stride_history(100), (7, 10, 15, 20, 33, 36), 19813),
    "stride-500": (_make_stride_history(500), (6, 8, 19, 26, 29, 33), 19799),
    "edge": (_edge(), (5, 9, 11, 12, 40, 44), 20094),
    "tie-draw": (_tie_draw(), (7, 8, 20, 33, 45, 46), 19878),
}


@pytest.mark.parametrize("case", tuple(FEATURE_WEIGHTED_GOLDENS))
def test_feature_weighted_matches_executed_donor_golden(case: str) -> None:
    history, expected, expected_calls = FEATURE_WEIGHTED_GOLDENS[case]
    rng = FormulaRandom()
    execution = BigLottoFrontendMLFeatureWeightedAdapter(rng).get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == expected
    assert execution.emitted_main_numbers == expected
    assert execution.special_number is None
    assert rng.calls == expected_calls


@pytest.mark.parametrize("case", tuple(RANDOM_FOREST_GOLDENS))
def test_random_forest_matches_executed_donor_golden(case: str) -> None:
    history, expected, expected_calls = RANDOM_FOREST_GOLDENS[case]
    rng = FormulaRandom()
    execution = BigLottoFrontendMLRandomForestAdapter(rng).get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == expected
    assert execution.emitted_main_numbers == expected
    assert execution.special_number is None
    assert rng.calls == expected_calls


@pytest.mark.parametrize("case", tuple(GENETIC_GOLDENS))
def test_genetic_matches_executed_donor_golden(case: str) -> None:
    history, expected, expected_calls = GENETIC_GOLDENS[case]
    rng = FormulaRandom()
    execution = BigLottoFrontendMLGeneticAdapter(rng).get_one_bet_with_emission(
        history, LotteryType.BIG_LOTTO
    )
    assert execution.legal_main_numbers == expected
    assert execution.emitted_main_numbers == expected
    assert execution.special_number is None
    assert rng.calls == expected_calls


def test_ticket_for_mode_helper() -> None:
    history, expected, _ = FEATURE_WEIGHTED_GOLDENS["stride-1"]
    newest = tuple(reversed(history))
    rng = FormulaRandom()
    assert ticket_for_mode(newest, "feature_weighted", rng) == expected


def test_minimum_history_is_insufficient_history() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendMLFeatureWeightedAdapter(FormulaRandom()).get_one_bet(
            (), LotteryType.BIG_LOTTO
        )
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendMLRandomForestAdapter(FormulaRandom()).get_one_bet(
            (), LotteryType.BIG_LOTTO
        )
    with pytest.raises(InsufficientHistory):
        BigLottoFrontendMLGeneticAdapter(FormulaRandom()).get_one_bet((), LotteryType.BIG_LOTTO)


def test_invalid_history_and_wrong_lottery_fail_closed() -> None:
    adapter = BigLottoFrontendMLFeatureWeightedAdapter(FormulaRandom())
    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(_history(1), LotteryType.DAILY_539)


def test_adapters_do_not_seed_process_global_rng() -> None:
    for cls in (
        BigLottoFrontendMLFeatureWeightedAdapter,
        BigLottoFrontendMLRandomForestAdapter,
        BigLottoFrontendMLGeneticAdapter,
    ):
        source = inspect.getsource(cls)
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


def test_catalog_registers_three_live_ml_identities() -> None:
    _catalog_identity(
        FEATURE_WEIGHTED_ID,
        BigLottoFrontendMLFeatureWeightedAdapter,
        "lottolab.strategies.adapters.biglotto_frontend_ml:"
        "BigLottoFrontendMLFeatureWeightedAdapter",
    )
    _catalog_identity(
        RANDOM_FOREST_ID,
        BigLottoFrontendMLRandomForestAdapter,
        "lottolab.strategies.adapters.biglotto_frontend_ml:BigLottoFrontendMLRandomForestAdapter",
    )
    _catalog_identity(
        GENETIC_ID,
        BigLottoFrontendMLGeneticAdapter,
        "lottolab.strategies.adapters.biglotto_frontend_ml:BigLottoFrontendMLGeneticAdapter",
    )


def test_generate_one_bet_use_case_with_ml_adapters() -> None:
    use_case = build_production_generate_one_bet()
    history = _history(10)
    for strategy_id in (FEATURE_WEIGHTED_ID, RANDOM_FOREST_ID, GENETIC_ID):
        output = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=history,
            )
        )
        assert output.status is GenerateOneBetStatus.OK
        assert output.numbers is not None
        assert len(output.numbers) == 6
        assert output.special_number is None
