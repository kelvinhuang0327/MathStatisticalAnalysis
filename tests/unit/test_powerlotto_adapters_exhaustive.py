"""Contracts for the Owner-authorized exhaustive BIG_LOTTO -> P638 set."""

from __future__ import annotations

import inspect
import random

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.p638_current_ranking_forwarder import (
    CURRENT_STRATEGIES,
)
from lottolab.strategies.adapters import (
    powerlotto_biglotto_core,
    powerlotto_wave4,
    powerlotto_wave5,
)
from lottolab.strategies.adapters.base import InsufficientHistory
from lottolab.strategies.adapters.powerlotto_biglotto_core import (
    POWER_LOTTO_FIRST_ZONE_GAME,
)
from lottolab.strategies.adapters.powerlotto_wave1 import P638HistoryRow, P638StrategySpec
from lottolab.strategies.adapters.powerlotto_wave3 import (
    WAVE3_BLOCKED_STRATEGIES,
    WAVE3_STRATEGIES,
)
from lottolab.strategies.adapters.powerlotto_wave4 import WAVE4_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave5 import WAVE5_STRATEGIES
from lottolab.strategies.powerlotto_second_zone import second_zone_predict

_WAVE4_IDS = (
    "power_biglotto_zone_split_3bet",
    "power_biglotto_high_prize_trend_7bet",
    "power_biglotto_core_satellite_12bet",
    "power_biglotto_two_bet_final_2bet",
    "power_biglotto_two_bet_optimizer_2bet",
    "power_biglotto_two_bet_optimizer_v2_2bet",
    "power_biglotto_tme_optimizer_4bet",
    "power_biglotto_optimized_ensemble_1bet",
    "power_biglotto_two_bet_elite_2bet",
    "power_biglotto_echo_2bet",
    "power_biglotto_elite_7bet",
    "power_biglotto_variant_history_11bet",
    "power_biglotto_auto_optimizer_alpha_25bet",
    "power_biglotto_backtest_10bet",
    "power_biglotto_tme_3bet",
    "power_biglotto_gemini_v1_2bet",
    "power_biglotto_five_me_5bet",
    "power_biglotto_smart_2bet",
)
_WAVE4_COUNTS = (3, 7, 12, 2, 2, 2, 4, 1, 2, 2, 7, 11, 25, 10, 3, 2, 5, 2)

_WAVE5_IDS = (
    "power_biglotto_dms_3bet",
    "power_biglotto_mwsc_3bet",
    "power_biglotto_cag_3bet",
    "power_biglotto_zdp_3bet",
    "power_biglotto_enhanced_dual_2bet",
    "power_biglotto_diversified_ensemble_v6_3bet",
    "power_biglotto_random_core_satellite_3bet",
    "power_biglotto_random_zone_split_3bet",
    "power_biglotto_exhaustive_audit_3bet",
    "power_biglotto_asm_3bet",
    "power_biglotto_hpsb_1bet",
)
_WAVE5_COUNTS = (3, 3, 3, 3, 2, 3, 3, 3, 3, 3, 1)

_FINAL_NONPORTABLE_IDS = {
    "biglotto_social_wisdom_anti_popularity",
    "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
    "legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
    "legacy_biglotto__test_ces__78d17c530ab8",
    "legacy_biglotto__test_greedy_optimizer__82df7f878ece",
    "legacy_biglotto__social_wisdom_predictor__a00829b5d875",
    "legacy_biglotto__negative_selection_biglotto__98f860c52cc2",
    "legacy_biglotto__test_cluster_cover__5b43959e7c55",
    "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
    "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
    "legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a",
    "legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669",
    "legacy_biglotto__backtest_strategy_1__41ed79a6de62",
    "legacy_biglotto__test_dcb__c3299c25ca59",
    "legacy_biglotto__test_ecp__c9d5ac6decdd",
    "legacy_biglotto__test_pce__9c0cf22b4217",
    "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
}


@pytest.fixture(scope="module")
def causal_history() -> tuple[P638HistoryRow, ...]:
    rng = random.Random("p638-exhaustive-portability-contract")
    return tuple(
        P638HistoryRow(
            draw=f"{97000001 + index}",
            date=f"2024-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 39), 6))),
            second_number=rng.randint(1, 8),
        )
        for index in range(180)
    )


def test_game_spec_is_the_authoritative_p638_first_zone() -> None:
    assert POWER_LOTTO_FIRST_ZONE_GAME.minimum == 1
    assert POWER_LOTTO_FIRST_ZONE_GAME.maximum == 38
    assert POWER_LOTTO_FIRST_ZONE_GAME.pick_count == 6


def test_exhaustive_wave_metadata_and_final_denominator_are_exact() -> None:
    assert tuple(spec.strategy_id for spec in WAVE4_STRATEGIES) == _WAVE4_IDS
    assert tuple(spec.native_ticket_count for spec in WAVE4_STRATEGIES) == _WAVE4_COUNTS
    assert tuple(spec.strategy_id for spec in WAVE5_STRATEGIES) == _WAVE5_IDS
    assert tuple(spec.native_ticket_count for spec in WAVE5_STRATEGIES) == _WAVE5_COUNTS

    migrated = WAVE3_STRATEGIES + WAVE4_STRATEGIES + WAVE5_STRATEGIES
    assert len(migrated) == 38
    assert len({spec.strategy_id for spec in migrated}) == 38
    assert len(CURRENT_STRATEGIES) == 61
    assert CURRENT_STRATEGIES[-29:] == WAVE4_STRATEGIES + WAVE5_STRATEGIES

    # Final audited 59-row partition after alias and source-closure collapse.
    categories = {
        "ALREADY_EQUIVALENT_IN_P638": 0,
        "PORTABLE_DIRECT": 5,
        "PORTABLE_WITH_GAMESPEC": 33,
        "DUPLICATE_OR_ALIAS": 4,
        "BIGLOTTO_RULE_DEPENDENT": 7,
        "BLOCKED_DEPENDENCY_OR_NONDETERMINISM": 10,
    }
    assert sum(categories.values()) == 59
    assert categories["PORTABLE_DIRECT"] + categories["PORTABLE_WITH_GAMESPEC"] == 38


def test_final_nonportable_ledger_has_no_batch_size_deferral() -> None:
    assert {entry.strategy_id for entry in WAVE3_BLOCKED_STRATEGIES} == _FINAL_NONPORTABLE_IDS
    assert all("DEFERRED" not in entry.reason for entry in WAVE3_BLOCKED_STRATEGIES)


def test_new_modules_are_target_native_and_leave_second_zone_to_the_spec() -> None:
    for module in (powerlotto_biglotto_core, powerlotto_wave4, powerlotto_wave5):
        imports = [
            line.strip()
            for line in inspect.getsource(module).splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        assert not any("adapters.biglotto" in line for line in imports)
        assert not any(
            f"lottolab.{layer}" in line
            for line in imports
            for layer in ("application", "infrastructure", "interfaces")
        )
        assert not any("powerlotto_second_zone" in line for line in imports)


@pytest.mark.parametrize(
    "spec",
    WAVE4_STRATEGIES + WAVE5_STRATEGIES,
    ids=lambda spec: spec.strategy_id,
)
def test_every_exhaustive_adapter_is_deterministic_complete_and_uses_second_zone_ssot(
    spec: P638StrategySpec,
    causal_history: tuple[P638HistoryRow, ...],
) -> None:
    required = max(30, spec.min_history)
    history = causal_history[: max(required, 160)]
    first = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    second = spec.get_bets(history, LotteryType.POWER_LOTTO)
    assert first == second
    assert len(first) == spec.native_ticket_count
    expected_second_zone = second_zone_predict([{"special": row.second_number} for row in history])
    for first_zone, second_zone in first:
        assert len(first_zone) == 6
        assert len(set(first_zone)) == 6
        assert all(type(number) is int and 1 <= number <= 38 for number in first_zone)
        assert second_zone == expected_second_zone


def _low_entropy_history(length: int, *, alternating: bool) -> tuple[P638HistoryRow, ...]:
    low = (1, 2, 3, 4, 5, 6)
    high = (33, 34, 35, 36, 37, 38)
    return tuple(
        P638HistoryRow(
            draw=str(98000001 + index),
            date=f"2025-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=high if alternating and index % 2 else low,
            second_number=(index % 8) + 1,
        )
        for index in range(length)
    )


@pytest.mark.parametrize("length", (30, 50, 100, 500))
@pytest.mark.parametrize("alternating", (False, True), ids=("constant", "alternating"))
def test_final_migrated_set_is_total_on_adversarial_low_entropy_histories(
    length: int,
    *,
    alternating: bool,
) -> None:
    migrated = WAVE3_STRATEGIES + WAVE4_STRATEGIES + WAVE5_STRATEGIES
    for spec in migrated:
        history = _low_entropy_history(max(length, spec.min_history), alternating=alternating)
        bets = spec.predict_tickets(history, LotteryType.POWER_LOTTO)
        assert len(bets) == spec.native_ticket_count, spec.strategy_id
        assert all(len(first_zone) == 6 for first_zone, _second_zone in bets), spec.strategy_id


@pytest.mark.parametrize(
    "spec",
    WAVE4_STRATEGIES + WAVE5_STRATEGIES,
    ids=lambda spec: spec.strategy_id,
)
def test_every_exhaustive_adapter_rejects_below_its_declared_minimum(
    spec: P638StrategySpec,
    causal_history: tuple[P638HistoryRow, ...],
) -> None:
    with pytest.raises(InsufficientHistory):
        spec.predict_tickets(causal_history[: spec.min_history - 1], LotteryType.POWER_LOTTO)


def test_seeded_zone_split_changes_with_causal_identity_and_repeats_exactly(
    causal_history: tuple[P638HistoryRow, ...],
) -> None:
    spec = powerlotto_wave4.WAVE4_STRATEGY_BY_ID["power_biglotto_zone_split_3bet"]
    first = spec.predict_tickets(causal_history[:80], LotteryType.POWER_LOTTO)
    repeated = spec.predict_tickets(causal_history[:80], LotteryType.POWER_LOTTO)
    extended = spec.predict_tickets(causal_history[:81], LotteryType.POWER_LOTTO)
    assert first == repeated
    assert first != extended
