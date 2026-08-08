"""DAILY_539 GameSpec adapters for the portable BIG_LOTTO families.

The P638 waves contain the already-verified target-neutral donor formulas for
the 38 pre-Batch15 portable families.  This module reuses those formulas at a
target boundary that binds the pool and pick count to DAILY_539's 5-of-39
contract.  It never converts a six-number P638 ticket into a five-number
ticket: the shared formula is executed with the target GameSpec and every
native ticket position is validated independently.

The nine Batch15 identities remain in ``daily539_biglotto_batch15``.  They are
not duplicated here; this module owns only the 38 missing R2 families.
"""

from __future__ import annotations

# pyright: reportPrivateUsage=false
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import powerlotto_wave3 as _wave3
from lottolab.strategies.adapters import powerlotto_wave4 as _wave4
from lottolab.strategies.adapters import powerlotto_wave5 as _wave5
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    SourceNativePortfolioClosure,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_batch15_cross_lottery_core import (
    DAILY539_GAME,
    validate_ticket,
)
from lottolab.strategies.adapters.powerlotto_biglotto_core import (
    DAILY539_FIRST_ZONE_GAME,
    use_first_zone_game,
)

_DONOR_ARCHIVE_SHA256 = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"


@dataclass(frozen=True, slots=True)
class Daily539PortableHistoryRow:
    """The immutable row shape consumed by the shared portable formulas."""

    draw: str
    date: str
    numbers: tuple[int, ...]


PortablePredictor = Callable[..., tuple[tuple[int, ...], ...]]


@dataclass(frozen=True, slots=True)
class Daily539BigLottoPortableSpec:
    """One source identity and its target-native predictor metadata."""

    source_strategy_id: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    predictor: PortablePredictor
    source_paths: tuple[str, ...]


def _validated_history(history: object, strategy_id: str) -> tuple[Daily539PortableHistoryRow, ...]:
    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    rows: list[Daily539PortableHistoryRow] = []
    for index, candidate in enumerate(cast(tuple[object, ...], history)):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        if type(row.draw) is not str or not row.draw:
            raise InvalidOutput(f"{strategy_id}: history row {index} draw is invalid")
        if type(row.date) is not str or not row.date:
            raise InvalidOutput(f"{strategy_id}: history row {index} date is invalid")
        try:
            numbers = validate_ticket(
                row.numbers,
                DAILY539_GAME,
                f"{strategy_id} history row {index}",
            )
        except ValueError as exc:
            raise InvalidOutput(str(exc)) from exc
        rows.append(Daily539PortableHistoryRow(row.draw, row.date, numbers))
    return tuple(rows)


def _predict(
    spec: Daily539BigLottoPortableSpec,
    history: tuple[Daily539PortableHistoryRow, ...],
) -> tuple[tuple[int, ...], ...]:
    with use_first_zone_game(DAILY539_FIRST_ZONE_GAME):
        raw = spec.predictor(history)
    if type(raw) is not tuple:
        raise InvalidOutput(f"{spec.strategy_id}: predictor must return a tuple")
    if len(raw) != spec.native_ticket_count:
        raise SourceNativePortfolioClosure(
            strategy_id=spec.strategy_id,
            expected_ticket_count=spec.native_ticket_count,
            actual_ticket_count=len(raw),
        )
    validated: list[tuple[int, ...]] = []
    for index, candidate in enumerate(raw, start=1):
        try:
            validated.append(
                validate_ticket(candidate, DAILY539_GAME, f"{spec.strategy_id} ticket {index}")
            )
        except ValueError as exc:
            raise InvalidOutput(str(exc)) from exc
    return tuple(validated)


class Daily539BigLottoPortableAdapter:
    """Common target-native adapter for one portable donor family."""

    supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (LotteryType.DAILY_539,)

    def __init__(self, spec: Daily539BigLottoPortableSpec) -> None:
        self._spec = spec
        self.strategy_id = spec.strategy_id
        self.strategy_name = spec.strategy_name
        self.strategy_version = spec.strategy_version
        self.min_history = spec.min_history
        self.native_ticket_count = spec.native_ticket_count

    def get_bets(self, history: object, lottery_type: LotteryType) -> tuple[tuple[int, ...], ...]:
        if type(lottery_type) is not LotteryType or lottery_type is not LotteryType.DAILY_539:
            raise UnsupportedLotteryType(
                f"{self.strategy_id} supports only {LotteryType.DAILY_539.value}"
            )
        canonical = _validated_history(history, self.strategy_id)
        if len(canonical) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical)}"
            )
        return _predict(self._spec, canonical)


def _spec(
    source_strategy_id: str,
    strategy_id: str,
    strategy_name: str,
    native_ticket_count: int,
    min_history: int,
    predictor: PortablePredictor,
    source_path: str,
) -> Daily539BigLottoPortableSpec:
    return Daily539BigLottoPortableSpec(
        source_strategy_id=source_strategy_id,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        strategy_version="v0.1-t539-cross-lottery-r2",
        native_ticket_count=native_ticket_count,
        min_history=min_history,
        predictor=predictor,
        source_paths=(
            "src/lottolab/strategies/adapters/daily539_biglotto_portable.py",
            source_path,
        ),
    )


DAILY539_BIGLOTTO_PORTABLE_SPECS: tuple[Daily539BigLottoPortableSpec, ...] = (
    _spec(
        "biglotto_deviation_2bet",
        "t539_biglotto_deviation_2bet",
        "今彩539 BigLotto Deviation 2注",
        2,
        100,
        _wave3._deviation_tickets,
        "src/lottolab/strategies/adapters/biglotto_selected.py",
    ),
    _spec(
        "biglotto_p0_2bet_bet1",
        "t539_biglotto_p0_echo_2bet",
        "今彩539 BigLotto P0 Echo 2注",
        2,
        1,
        _wave3._p0_echo_tickets,
        "src/lottolab/strategies/adapters/biglotto_selected.py",
    ),
    _spec(
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "t539_biglotto_graph_predictor_1bet",
        "今彩539 BigLotto Graph Predictor 1注",
        1,
        1,
        _wave3._graph_predictor_tickets,
        "src/lottolab/strategies/adapters/biglotto_wave1.py",
    ),
    _spec(
        "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
        "t539_biglotto_must_hit_top6_1bet",
        "今彩539 BigLotto Must-Hit Top6 1注",
        1,
        50,
        _wave3._must_hit_top6_tickets,
        "src/lottolab/strategies/adapters/biglotto_wave1.py",
    ),
    _spec(
        "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
        "t539_biglotto_dynamic_frequency_1bet",
        "今彩539 BigLotto Dynamic Frequency 1注",
        1,
        200,
        _wave3._dynamic_frequency_tickets,
        "src/lottolab/strategies/adapters/biglotto_wave1.py",
    ),
    _spec(
        "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
        "t539_biglotto_hot_cooccurrence_1bet",
        "今彩539 BigLotto Hot Co-occurrence 1注",
        1,
        1,
        _wave3._hot_cooccurrence_tickets,
        "src/lottolab/strategies/adapters/biglotto_wave1.py",
    ),
    _spec(
        "legacy_biglotto__attention_replay_predictor__a811e2eb8215",
        "t539_biglotto_attention_replay_1bet",
        "今彩539 BigLotto Attention Replay 1注",
        1,
        1,
        _wave3._attention_replay_tickets,
        "src/lottolab/strategies/adapters/biglotto_wave7.py",
    ),
    _spec(
        "legacy_biglotto__predict_biglotto_115000002_zone_balance__8febca575f5d",
        "t539_biglotto_zone_balance_5bet",
        "今彩539 BigLotto Zone Balance 5注",
        5,
        1,
        _wave3._zone_balance_tickets,
        "src/lottolab/strategies/adapters/biglotto_wave7.py",
    ),
    _spec(
        "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519",
        "t539_biglotto_gemini_phase2_7bet",
        "今彩539 BigLotto Gemini Phase2 7注",
        7,
        100,
        _wave3._gemini_phase2_tickets,
        "src/lottolab/strategies/adapters/biglotto_wave7.py",
    ),
    _spec(
        "biglotto_zone_split_3bet_bet1",
        "t539_biglotto_zone_split_3bet",
        "今彩539 BigLotto Zone Split 3注",
        3,
        1,
        _wave4._zone_split_3bet,
        "src/lottolab/strategies/adapters/biglotto_selected.py",
    ),
    _spec(
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
        "t539_biglotto_high_prize_trend_7bet",
        "今彩539 BigLotto High Prize Trend 7注",
        7,
        1,
        _wave4._high_prize_trend_7bet,
        "src/lottolab/strategies/adapters/biglotto_wave2.py",
    ),
    _spec(
        "legacy_biglotto__core_satellite__2e82891003b3",
        "t539_biglotto_core_satellite_12bet",
        "今彩539 BigLotto Core Satellite 12注",
        12,
        1,
        _wave4._core_satellite_12bet,
        "src/lottolab/strategies/adapters/biglotto_wave2.py",
    ),
    _spec(
        "legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
        "t539_biglotto_two_bet_final_2bet",
        "今彩539 BigLotto Two-Bet Final 2注",
        2,
        1,
        _wave4._two_bet_final,
        "src/lottolab/strategies/adapters/biglotto_wave3.py",
    ),
    _spec(
        "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
        "t539_biglotto_two_bet_optimizer_2bet",
        "今彩539 BigLotto Two-Bet Optimizer 2注",
        2,
        1,
        _wave4._two_bet_optimizer,
        "src/lottolab/strategies/adapters/biglotto_wave3.py",
    ),
    _spec(
        "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
        "t539_biglotto_two_bet_optimizer_v2_2bet",
        "今彩539 BigLotto Two-Bet Optimizer V2 2注",
        2,
        1,
        _wave4._two_bet_optimizer_v2,
        "src/lottolab/strategies/adapters/biglotto_wave3.py",
    ),
    _spec(
        "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
        "t539_biglotto_tme_optimizer_4bet",
        "今彩539 BigLotto TME Optimizer 4注",
        4,
        1,
        _wave4._tme_optimizer,
        "src/lottolab/strategies/adapters/biglotto_wave4.py",
    ),
    _spec(
        "legacy_biglotto__optimized_ensemble__e05e0fde22d7",
        "t539_biglotto_optimized_ensemble_1bet",
        "今彩539 BigLotto Optimized Ensemble 1注",
        1,
        1,
        _wave4._optimized_ensemble,
        "src/lottolab/strategies/adapters/biglotto_wave4.py",
    ),
    _spec(
        "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
        "t539_biglotto_two_bet_elite_2bet",
        "今彩539 BigLotto Two-Bet Elite 2注",
        2,
        1,
        _wave4._two_bet_elite,
        "src/lottolab/strategies/adapters/biglotto_wave4.py",
    ),
    _spec(
        "legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa",
        "t539_biglotto_echo_2bet",
        "今彩539 BigLotto Echo 2注",
        2,
        1,
        _wave4._echo_2bet,
        "src/lottolab/strategies/adapters/biglotto_wave5.py",
    ),
    _spec(
        "legacy_biglotto__predict_biglotto_elite7__eb46a9856446",
        "t539_biglotto_elite_7bet",
        "今彩539 BigLotto Elite 7注",
        7,
        1,
        _wave4._elite_7bet,
        "src/lottolab/strategies/adapters/biglotto_wave5.py",
    ),
    _spec(
        "legacy_biglotto__research_variant_history__149648f9fffc",
        "t539_biglotto_variant_history_11bet",
        "今彩539 BigLotto Variant History 11注",
        11,
        20,
        _wave4._variant_history_11bet,
        "src/lottolab/strategies/adapters/biglotto_wave5.py",
    ),
    _spec(
        "legacy_biglotto__auto_optimizer_alpha__7eaa9572e384",
        "t539_biglotto_auto_optimizer_alpha_25bet",
        "今彩539 BigLotto Auto Optimizer Alpha 25注",
        25,
        1,
        _wave4._auto_optimizer_25bet,
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
    ),
    _spec(
        "legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
        "t539_biglotto_backtest_10bet",
        "今彩539 BigLotto Backtest 10注",
        10,
        1,
        _wave4._backtest_10bet,
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
    ),
    _spec(
        "legacy_biglotto__test_tme__f3bb5106dfe3",
        "t539_biglotto_tme_3bet",
        "今彩539 BigLotto TME 3注",
        3,
        1,
        _wave4._tme_3bet,
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
    ),
    _spec(
        "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776",
        "t539_biglotto_gemini_v1_2bet",
        "今彩539 BigLotto Gemini V1 2注",
        2,
        50,
        _wave4._gemini_v1_2bet,
        "src/lottolab/strategies/adapters/biglotto_wave6.py",
    ),
    _spec(
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
        "t539_biglotto_five_me_5bet",
        "今彩539 BigLotto Five-ME 5注",
        5,
        1,
        _wave4._five_me_5bet,
        "src/lottolab/strategies/adapters/biglotto_wave7.py",
    ),
    _spec(
        "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a",
        "t539_biglotto_smart_2bet",
        "今彩539 BigLotto Smart 2注",
        2,
        1,
        _wave4._smart_2bet,
        "src/lottolab/strategies/adapters/biglotto_wave7.py",
    ),
    _spec(
        "legacy_biglotto__test_dms__b63442289bd5",
        "t539_biglotto_dms_3bet",
        "今彩539 BigLotto DMS 3注",
        3,
        20,
        _wave5._dms_3bet,
        "src/lottolab/strategies/adapters/biglotto_wave8.py",
    ),
    _spec(
        "legacy_biglotto__test_mwsc__ba37643d6a3b",
        "t539_biglotto_mwsc_3bet",
        "今彩539 BigLotto MWSC 3注",
        3,
        1,
        _wave5._mwsc_3bet,
        "src/lottolab/strategies/adapters/biglotto_wave8.py",
    ),
    _spec(
        "legacy_biglotto__test_cag__7ca5343dfedd",
        "t539_biglotto_cag_3bet",
        "今彩539 BigLotto CAG 3注",
        3,
        1,
        _wave5._cag_3bet,
        "src/lottolab/strategies/adapters/biglotto_wave9.py",
    ),
    _spec(
        "legacy_biglotto__test_zdp__e80cc7e95453",
        "t539_biglotto_zdp_3bet",
        "今彩539 BigLotto ZDP 3注",
        3,
        1,
        _wave5._zdp_3bet,
        "src/lottolab/strategies/adapters/biglotto_wave9.py",
    ),
    _spec(
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
        "t539_biglotto_enhanced_dual_2bet",
        "今彩539 BigLotto Enhanced Dual 2注",
        2,
        100,
        _wave5._enhanced_dual_2bet,
        "src/lottolab/strategies/adapters/biglotto_wave10.py",
    ),
    _spec(
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
        "t539_biglotto_diversified_ensemble_v6_3bet",
        "今彩539 BigLotto Diversified Ensemble V6 3注",
        3,
        1,
        _wave5._diversified_ensemble_v6,
        "src/lottolab/strategies/adapters/biglotto_wave10.py",
    ),
    _spec(
        "legacy_biglotto__core_satellite__611284461323",
        "t539_biglotto_random_core_satellite_3bet",
        "今彩539 BigLotto Random Core Satellite 3注",
        3,
        1,
        _wave5._random_core_satellite,
        "src/lottolab/strategies/adapters/biglotto_wave11.py",
    ),
    _spec(
        "legacy_biglotto__zone_split__b6144f9d479f",
        "t539_biglotto_random_zone_split_3bet",
        "今彩539 BigLotto Random Zone Split 3注",
        3,
        1,
        _wave5._random_zone_split,
        "src/lottolab/strategies/adapters/biglotto_wave11.py",
    ),
    _spec(
        "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2",
        "t539_biglotto_exhaustive_audit_3bet",
        "今彩539 BigLotto Exhaustive Audit 3注",
        3,
        50,
        _wave5._exhaustive_audit_3bet,
        "src/lottolab/strategies/adapters/biglotto_wave11.py",
    ),
    _spec(
        "legacy_biglotto__test_asm__d39a233a4c75",
        "t539_biglotto_asm_3bet",
        "今彩539 BigLotto ASM 3注",
        3,
        1,
        _wave5._asm_3bet,
        "src/lottolab/strategies/adapters/biglotto_wave13.py",
    ),
    _spec(
        "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
        "t539_biglotto_hpsb_1bet",
        "今彩539 BigLotto HPSB 1注",
        1,
        1,
        _wave5._hpsb_1bet,
        "src/lottolab/strategies/adapters/biglotto_wave14.py",
    ),
)

DAILY539_BIGLOTTO_PORTABLE_BY_ID = {
    spec.strategy_id: spec for spec in DAILY539_BIGLOTTO_PORTABLE_SPECS
}


__all__ = [
    "DAILY539_BIGLOTTO_PORTABLE_BY_ID",
    "DAILY539_BIGLOTTO_PORTABLE_SPECS",
    "Daily539BigLottoPortableAdapter",
    "Daily539BigLottoPortableSpec",
]
