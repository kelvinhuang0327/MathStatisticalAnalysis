"""POWER_LOTTO Wave 6: BigLotto Batch-15 cross-lottery closure.

The upstream BigLotto catalog grew from 59 to 68 descriptors.  Waves 3--5
already covered the portable portion of the first 59; this wave adds the nine
new deterministic Batch-15 identities.  Their pool/pick math is bound to the
POWER_LOTTO first-zone GameSpec, and the existing ``P638StrategySpec`` remains
the sole owner of second-zone prediction and complete-ticket validation.

Two donor-native closures stay explicit: zone-momentum may return no legal
ticket on a low-diversity causal history, and DM-DMS may return only one of its
two selected tickets when one audited producer closes.  Neither case is
padded or silently reclassified as a successful prediction.
"""

from __future__ import annotations

from collections.abc import Callable

from lottolab.strategies.adapters.biglotto_batch15_cross_lottery_core import (
    POWERLOTTO_GAME,
    NumberHistory,
    TargetGameSpec,
    Ticket,
    cold_hunter_predict,
    dm_dms_tickets,
    dms_solo_ticket,
    gap_pressure_predict,
    moderate_rank_predict,
    pure_cold_predict,
    rebound_aware_predict,
    short_window_deviation_predict,
    validate_ticket,
    zone_momentum_candidate,
)
from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638BlockedStrategy,
    P638FirstZoneTicketSet,
    P638HistoryRow,
    P638StrategySpec,
)

_DONOR_SHA256 = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"


def _number_history(history: tuple[P638HistoryRow, ...]) -> NumberHistory:
    return tuple(row.numbers for row in history)


def _single_predictor(
    predictor: Callable[[NumberHistory, TargetGameSpec], Ticket],
) -> Callable[[tuple[P638HistoryRow, ...]], P638FirstZoneTicketSet]:
    def predict(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
        candidate = predictor(_number_history(history), POWERLOTTO_GAME)
        if type(candidate) is not tuple or len(candidate) != POWERLOTTO_GAME.pick_count:
            # P638StrategySpec recognizes an empty portfolio as the typed
            # source-native closure for a one-ticket strategy.
            return ()
        return (validate_ticket(candidate, POWERLOTTO_GAME, "P638 Batch-15 output"),)

    return predict


def _dm_dms_predict(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    candidates = dm_dms_tickets(_number_history(history), POWERLOTTO_GAME)
    return tuple(
        validate_ticket(ticket, POWERLOTTO_GAME, f"P638 DM-DMS ticket {index + 1}")
        for index, ticket in enumerate(candidates)
    )


def _dms_predict(history: tuple[P638HistoryRow, ...]) -> P638FirstZoneTicketSet:
    ticket = dms_solo_ticket(_number_history(history), POWERLOTTO_GAME)
    return (validate_ticket(ticket, POWERLOTTO_GAME, "P638 DMS output"),)


def _spec(
    strategy_id: str,
    native_ticket_count: int,
    donor_id: str,
    predictor: Callable[[tuple[P638HistoryRow, ...]], P638FirstZoneTicketSet],
    *,
    source_native_closure_ticket_counts: tuple[int, ...] = (),
) -> P638StrategySpec:
    return P638StrategySpec(
        strategy_id=strategy_id,
        strategy_version="v0.1-p638-wave6",
        native_ticket_count=native_ticket_count,
        min_history=1,
        source_paths=(
            "src/lottolab/strategies/adapters/biglotto_batch15.py",
            "src/lottolab/strategies/adapters/biglotto_batch15_cross_lottery_core.py",
        ),
        provenance=(
            f"POWER_LOTTO GameSpec port of {donor_id}; donor archive "
            f"{_DONOR_SHA256}; Batch-15 closure-preserving target-native "
            "implementation with second-zone composition delegated to the "
            "P638 strategy spec."
        ),
        _predictor=predictor,
        source_native_closure_ticket_counts=source_native_closure_ticket_counts,
    )


WAVE6_STRATEGIES: tuple[P638StrategySpec, ...] = (
    _spec(
        "power_biglotto_cold_hunter_1bet",
        1,
        "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
        _single_predictor(cold_hunter_predict),
    ),
    _spec(
        "power_biglotto_short_window_deviation_1bet",
        1,
        "legacy_biglotto__short_window_deviation_predict__9e89f2b41add",
        _single_predictor(short_window_deviation_predict),
    ),
    _spec(
        "power_biglotto_rebound_aware_1bet",
        1,
        "legacy_biglotto__rebound_aware_predict__9e89f2b41add",
        _single_predictor(rebound_aware_predict),
    ),
    _spec(
        "power_biglotto_zone_momentum_1bet",
        1,
        "legacy_biglotto__zone_momentum_predict__9e89f2b41add",
        _single_predictor(zone_momentum_candidate),
        source_native_closure_ticket_counts=(0,),
    ),
    _spec(
        "power_biglotto_pure_cold_1bet",
        1,
        "legacy_biglotto__pure_cold_predict__9e89f2b41add",
        _single_predictor(pure_cold_predict),
    ),
    _spec(
        "power_biglotto_moderate_rank_1bet",
        1,
        "legacy_biglotto__moderate_rank_predict__9e89f2b41add",
        _single_predictor(moderate_rank_predict),
    ),
    _spec(
        "power_biglotto_gap_pressure_1bet",
        1,
        "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6",
        _single_predictor(gap_pressure_predict),
    ),
    _spec(
        "power_biglotto_dm_dms_2bet",
        2,
        "legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
        _dm_dms_predict,
        source_native_closure_ticket_counts=(0, 1),
    ),
    _spec(
        "power_biglotto_dms_1bet",
        1,
        "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
        _dms_predict,
    ),
)

WAVE6_STRATEGY_BY_ID = {spec.strategy_id: spec for spec in WAVE6_STRATEGIES}
WAVE6_BLOCKED_STRATEGIES: tuple[P638BlockedStrategy, ...] = ()

__all__ = [
    "WAVE6_BLOCKED_STRATEGIES",
    "WAVE6_STRATEGIES",
    "WAVE6_STRATEGY_BY_ID",
]
