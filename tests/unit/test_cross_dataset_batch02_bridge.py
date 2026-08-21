"""Catalog-bridge tests for the Batch02 cross-dataset base-method intake.

Covers: each of the 8 pinned strategies resolves through the real production
catalog to a properly-subclassed BetAdapter/PortfolioBetAdapter, executes to
legal, deterministic, native-shaped output through both the raw adapter
contract and the real GenerateOneBet/GeneratePortfolio use cases, and matches
its wrapped producer's output exactly (no algorithm duplicated or drifted).
"""

from __future__ import annotations

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetStatus,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.cross_dataset_batch02_bridge import (
    Daily539AcbMarkovMidfreq3BetCatalogAdapter,
    PowerC01RecencyDecayBridgeAdapter,
    PowerC02GapOverdueBridgeAdapter,
    PowerC03PairCentralityBridgeAdapter,
    PowerC04ZoneBalancedBridgeAdapter,
    PowerC05DispersionMatchBridgeAdapter,
    PowerC06RegimeCusumBridgeAdapter,
    PowerC07BordaEnsembleBridgeAdapter,
)
from lottolab.strategies.adapters.daily539_portfolio_phase2 import (
    Daily539AcbMarkovMidfreq3BetAdapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import P638HistoryRow
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGY_BY_ID
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

_POWER_LOTTO_BRIDGES = (
    ("power_c01_recency_decay_1bet", PowerC01RecencyDecayBridgeAdapter),
    ("power_c02_gap_overdue_1bet", PowerC02GapOverdueBridgeAdapter),
    ("power_c03_pair_centrality_1bet", PowerC03PairCentralityBridgeAdapter),
    ("power_c04_zone_balanced_1bet", PowerC04ZoneBalancedBridgeAdapter),
    ("power_c05_dispersion_match_1bet", PowerC05DispersionMatchBridgeAdapter),
    ("power_c06_regime_cusum_1bet", PowerC06RegimeCusumBridgeAdapter),
    ("power_c07_borda_ensemble_1bet", PowerC07BordaEnsembleBridgeAdapter),
)
_DAILY539_STRATEGY_ID = "acb_markov_midfreq_3bet"


def _powerlotto_history(rows: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(str(index), f"2026-01-{(index % 28) + 1:02d}", (1, 2, 3, 4, 5, 6))
        for index in range(1, rows + 1)
    )


def _daily539_history(rows: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(str(index), f"2026-01-{(index % 28) + 1:02d}", (1, 2, 3, 4, 5))
        for index in range(1, rows + 1)
    )


def _as_p638_history(history: tuple[CausalDrawRow, ...]) -> tuple[P638HistoryRow, ...]:
    return tuple(
        P638HistoryRow(draw=row.draw, date=row.date, numbers=row.numbers, second_number=1)
        for row in history
    )


# --- Catalog registration -------------------------------------------------


@pytest.mark.parametrize(("strategy_id", "adapter_class"), _POWER_LOTTO_BRIDGES)
def test_powerlotto_descriptor_matches_bridge_identity_and_loads(
    strategy_id: str, adapter_class: type[BetAdapter]
) -> None:
    catalog = production_catalog()
    descriptor = catalog.get(strategy_id)
    spec = WAVE2_STRATEGY_BY_ID[strategy_id]

    assert descriptor.lottery_types == (LotteryType.POWER_LOTTO,)
    assert descriptor.version == spec.strategy_version
    assert descriptor.min_history == spec.min_history == adapter_class.min_history
    assert descriptor.executable is True
    assert descriptor.response_shape.value == "SINGLE_TICKET"
    assert descriptor.native_ticket_count == 1

    loaded = ExecutableRegistry(catalog).load_adapter(strategy_id)
    assert loaded is adapter_class
    assert isinstance(loaded, type) and issubclass(loaded, BetAdapter)
    assert adapter_class.strategy_id == strategy_id


def test_daily539_descriptor_matches_bridge_identity_and_loads() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(_DAILY539_STRATEGY_ID)

    assert descriptor.lottery_types == (LotteryType.DAILY_539,)
    assert descriptor.version == Daily539AcbMarkovMidfreq3BetAdapter.strategy_version
    assert descriptor.min_history == Daily539AcbMarkovMidfreq3BetAdapter.min_history
    assert descriptor.native_ticket_count == 3
    assert descriptor.response_shape.value == "PORTFOLIO"

    loaded = ExecutableRegistry(catalog).load_adapter(_DAILY539_STRATEGY_ID)
    assert loaded is Daily539AcbMarkovMidfreq3BetCatalogAdapter
    assert isinstance(loaded, type) and issubclass(loaded, PortfolioBetAdapter)


def test_no_duplicate_strategy_ids_in_production_catalog() -> None:
    catalog = production_catalog()
    ids = [descriptor.strategy_id for descriptor in catalog]
    assert len(ids) == len(set(ids))


# --- POWER_LOTTO bridge execution -----------------------------------------


@pytest.mark.parametrize(("strategy_id", "adapter_class"), _POWER_LOTTO_BRIDGES)
def test_powerlotto_bridge_executes_legal_deterministic_first_zone_only(
    strategy_id: str, adapter_class: type[BetAdapter]
) -> None:
    history = _powerlotto_history(500)
    adapter = adapter_class()

    execution = adapter.get_one_bet_with_emission(history, LotteryType.POWER_LOTTO)
    repeat = adapter.get_one_bet_with_emission(history, LotteryType.POWER_LOTTO)

    assert execution == repeat
    assert len(execution.legal_main_numbers) == 6
    assert execution.legal_main_numbers == tuple(sorted(execution.legal_main_numbers))
    assert len(set(execution.legal_main_numbers)) == 6
    assert all(1 <= number <= 38 for number in execution.legal_main_numbers)
    assert execution.special_number is None


@pytest.mark.parametrize(("strategy_id", "adapter_class"), _POWER_LOTTO_BRIDGES)
def test_powerlotto_bridge_matches_wrapped_wave2_predictor_exactly(
    strategy_id: str, adapter_class: type[BetAdapter]
) -> None:
    history = _powerlotto_history(500)

    bridged_numbers, bridged_special = adapter_class().get_one_bet(
        history, LotteryType.POWER_LOTTO
    )
    direct_first_zone, _direct_second_zone = WAVE2_STRATEGY_BY_ID[strategy_id].predict_tickets(
        _as_p638_history(history), LotteryType.POWER_LOTTO
    )[0]

    assert bridged_numbers == direct_first_zone
    assert bridged_special is None


@pytest.mark.parametrize(("strategy_id", "adapter_class"), _POWER_LOTTO_BRIDGES)
def test_powerlotto_bridge_enforces_its_min_history(
    strategy_id: str, adapter_class: type[BetAdapter]
) -> None:
    short_history = _powerlotto_history(adapter_class.min_history - 1)
    with pytest.raises(InsufficientHistory):
        adapter_class().get_one_bet_with_emission(short_history, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize(("strategy_id", "adapter_class"), _POWER_LOTTO_BRIDGES)
def test_powerlotto_bridge_rejects_other_lottery_types(
    strategy_id: str, adapter_class: type[BetAdapter]
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_one_bet_with_emission(
            _daily539_history(500), LotteryType.DAILY_539
        )


# --- DAILY_539 portfolio bridge execution ----------------------------------


def test_daily539_bridge_executes_legal_deterministic_portfolio_matching_inner_adapter() -> None:
    history = _daily539_history(150)
    bridge = Daily539AcbMarkovMidfreq3BetCatalogAdapter()
    inner = Daily539AcbMarkovMidfreq3BetAdapter()

    execution = bridge.get_bets_with_emission(history, LotteryType.DAILY_539)
    repeat = bridge.get_bets_with_emission(history, LotteryType.DAILY_539)
    inner_tickets = inner.get_bets(history, LotteryType.DAILY_539)

    assert execution == repeat
    assert len(execution) == 3
    for ticket_execution in execution:
        assert len(ticket_execution.legal_main_numbers) == 5
        assert ticket_execution.legal_main_numbers == tuple(
            sorted(ticket_execution.legal_main_numbers)
        )
        assert len(set(ticket_execution.legal_main_numbers)) == 5
        assert all(1 <= number <= 39 for number in ticket_execution.legal_main_numbers)
        assert ticket_execution.special_number is None
    assert tuple(e.legal_main_numbers for e in execution) == inner_tickets


def test_daily539_bridge_enforces_its_min_history() -> None:
    short_history = _daily539_history(Daily539AcbMarkovMidfreq3BetCatalogAdapter.min_history - 1)
    with pytest.raises(InsufficientHistory):
        Daily539AcbMarkovMidfreq3BetCatalogAdapter().get_bets_with_emission(
            short_history, LotteryType.DAILY_539
        )


def test_daily539_bridge_rejects_other_lottery_types() -> None:
    with pytest.raises(UnsupportedLotteryType):
        Daily539AcbMarkovMidfreq3BetCatalogAdapter().get_bets_with_emission(
            _powerlotto_history(150), LotteryType.POWER_LOTTO
        )


# --- Real production use-case wiring (replay-readiness smoke) -------------


def test_production_generate_one_bet_wiring_includes_all_powerlotto_bridges() -> None:
    use_case = build_production_generate_one_bet()
    history = _powerlotto_history(500)

    for strategy_id, _adapter_class in _POWER_LOTTO_BRIDGES:
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.POWER_LOTTO,
                history=history,
            )
        )
        assert result.status is GenerateOneBetStatus.OK
        assert result.numbers is not None and len(result.numbers) == 6
        assert result.special_number is None


def test_production_generate_portfolio_wiring_includes_daily539_bridge() -> None:
    use_case = build_production_generate_portfolio()

    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=_DAILY539_STRATEGY_ID,
            lottery_type=LotteryType.DAILY_539,
            history=_daily539_history(150),
        )
    )

    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers is not None and len(result.numbers) == 3
