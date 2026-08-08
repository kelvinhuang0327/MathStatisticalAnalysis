"""DAILY_539 target-native wrappers for the BigLotto Batch-15 producers.

The nine identities in this module keep their BigLotto donor identity in
provenance, but their bounds are the DAILY_539 5-of-39 rule contract.  The
shared pure core does not know about ``CausalDrawRow`` or external state; this
module owns the exact history, output, lottery-type, and native-portfolio
validation required by the T539 runner.

The target-native zone-momentum selector is still checked for the donor's
short-output closure, although DAILY_539's five zones normally yield five
numbers.  The DM-DMS selector can emit fewer than two tickets when one of its
audited producers closes.  Both outcomes are surfaced as typed source-native
closures; no padding is invented.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    SourceNativePortfolioClosure,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_batch15_cross_lottery_core import (
    DAILY539_GAME,
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


def _validated_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    rows: list[CausalDrawRow] = []
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
        rows.append(CausalDrawRow(draw=row.draw, date=row.date, numbers=numbers))
    return tuple(rows)


def _number_history(history: tuple[CausalDrawRow, ...]) -> NumberHistory:
    return tuple(row.numbers for row in history)


def _single_ticket(
    history: tuple[CausalDrawRow, ...],
    strategy_id: str,
    predictor: Callable[[NumberHistory, TargetGameSpec], Ticket],
) -> tuple[Ticket, None]:
    candidate = predictor(_number_history(history), DAILY539_GAME)
    if type(candidate) is not tuple or len(candidate) != DAILY539_GAME.pick_count:
        raise SourceNativePortfolioClosure(
            strategy_id=strategy_id,
            expected_ticket_count=1,
            actual_ticket_count=0,
        )
    try:
        ticket = validate_ticket(candidate, DAILY539_GAME, f"{strategy_id} output")
    except ValueError as exc:
        raise InvalidOutput(str(exc)) from exc
    return ticket, None


class _Daily539Batch15SingleAdapter:
    strategy_id: ClassVar[str]
    strategy_name: ClassVar[str]
    strategy_version: ClassVar[str] = "v0.1-t539-batch15"
    min_history: ClassVar[int] = 1
    native_ticket_count: ClassVar[int] = 1
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (LotteryType.DAILY_539,)
    _predictor: ClassVar[Callable[[NumberHistory, TargetGameSpec], Ticket]]

    def get_one_bet(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        canonical = _validated_history(history, self.strategy_id)
        if len(canonical) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical)}"
            )
        return _single_ticket(canonical, self.strategy_id, type(self)._predictor)


class Daily539BigLottoColdHunterAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_cold_hunter_1bet"
    strategy_name = "今彩539 BigLotto Cold Hunter 1注"
    _predictor = cold_hunter_predict


class Daily539BigLottoShortWindowDeviationAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_short_window_deviation_1bet"
    strategy_name = "今彩539 BigLotto Short-Window Deviation 1注"
    _predictor = short_window_deviation_predict


class Daily539BigLottoReboundAwareAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_rebound_aware_1bet"
    strategy_name = "今彩539 BigLotto Rebound-Aware 1注"
    _predictor = rebound_aware_predict


class Daily539BigLottoZoneMomentumAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_zone_momentum_1bet"
    strategy_name = "今彩539 BigLotto Zone-Momentum 1注"
    _predictor = zone_momentum_candidate


class Daily539BigLottoPureColdAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_pure_cold_1bet"
    strategy_name = "今彩539 BigLotto Pure Cold 1注"
    _predictor = pure_cold_predict


class Daily539BigLottoModerateRankAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_moderate_rank_1bet"
    strategy_name = "今彩539 BigLotto Moderate-Rank 1注"
    _predictor = moderate_rank_predict


class Daily539BigLottoGapPressureAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_gap_pressure_1bet"
    strategy_name = "今彩539 BigLotto Gap-Pressure 1注"
    _predictor = gap_pressure_predict


class Daily539BigLottoDmDmsAdapter:
    """Native two-ticket DM-DMS portfolio with donor-faithful closure."""

    strategy_id = "t539_biglotto_dm_dms_2bet"
    strategy_name = "今彩539 BigLotto DM-DMS 2注"
    strategy_version = "v0.1-t539-batch15"
    min_history = 1
    native_ticket_count = 2
    supported_lottery_types = (LotteryType.DAILY_539,)

    def get_bets(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        canonical = _validated_history(history, self.strategy_id)
        if len(canonical) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, got {len(canonical)}"
            )
        predicted = dm_dms_tickets(_number_history(canonical), DAILY539_GAME)
        if len(predicted) != self.native_ticket_count:
            raise SourceNativePortfolioClosure(
                strategy_id=self.strategy_id,
                expected_ticket_count=self.native_ticket_count,
                actual_ticket_count=len(predicted),
            )
        return tuple(
            validate_ticket(ticket, DAILY539_GAME, f"{self.strategy_id} ticket {index + 1}")
            for index, ticket in enumerate(predicted)
        )


class Daily539BigLottoDmsAdapter(_Daily539Batch15SingleAdapter):
    strategy_id = "t539_biglotto_dms_1bet"
    strategy_name = "今彩539 BigLotto DMS 1注"
    _predictor = dms_solo_ticket


type Daily539Batch15AdapterClass = (
    type[_Daily539Batch15SingleAdapter] | type[Daily539BigLottoDmDmsAdapter]
)

DAILY539_BATCH15_ADAPTERS: tuple[Daily539Batch15AdapterClass, ...] = (
    Daily539BigLottoColdHunterAdapter,
    Daily539BigLottoShortWindowDeviationAdapter,
    Daily539BigLottoReboundAwareAdapter,
    Daily539BigLottoZoneMomentumAdapter,
    Daily539BigLottoPureColdAdapter,
    Daily539BigLottoModerateRankAdapter,
    Daily539BigLottoGapPressureAdapter,
    Daily539BigLottoDmDmsAdapter,
    Daily539BigLottoDmsAdapter,
)


__all__ = [
    "DAILY539_BATCH15_ADAPTERS",
    "Daily539Batch15AdapterClass",
    "Daily539BigLottoColdHunterAdapter",
    "Daily539BigLottoDmDmsAdapter",
    "Daily539BigLottoDmsAdapter",
    "Daily539BigLottoGapPressureAdapter",
    "Daily539BigLottoModerateRankAdapter",
    "Daily539BigLottoPureColdAdapter",
    "Daily539BigLottoReboundAwareAdapter",
    "Daily539BigLottoShortWindowDeviationAdapter",
    "Daily539BigLottoZoneMomentumAdapter",
]
