"""Target-aware playback of the Wave 64 XGBoost source-runtime ledger."""

from itertools import pairwise
from typing import cast

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    CLOSED_REASON,
    PINNED_DATASET_SHA256,
    SOURCE_REFERENCE_RUNTIME,
    LegacyXGBoostNativeWave64Request,
    LegacyXGBoostNativeWave64SourceError,
    generate_legacy_xgboost_native_wave64_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.application.use_cases.historical_replay_controller import (
    RecordedInsufficientHistory,
    ReplayTypedClosure,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayTicket


class FrozenXGBoostWave64Replay:
    strategy_id = "legacy_biglotto__xgboost_model__38c72a70c627"
    strategy_version = "legacy-source-49a25effa62f-38c72a70c627"
    strategy_name = "大樂透 XGBoost (Wave 64 歷史票券回放)"
    min_history = 15
    native_ticket_count = 1
    replays_recorded_closures = True
    replay_scope = (
        "Playback is limited to the 2,149 Wave 64 targets (96000001 through 115000073) "
        "and their recorded strict prefixes. The archived "
        f"{SOURCE_REFERENCE_RUNTIME} runtime produced these tickets."
    )

    def get_replay_tickets(
        self, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> tuple[ReplayTicket, ...]:
        if target.lottery_type is not LotteryType.BIG_LOTTO or any(
            row.lottery_type is not LotteryType.BIG_LOTTO for row in history
        ):
            raise ValueError("Wave 64 requires BIG_LOTTO draws")
        if (history and history[-1].sort_key >= target.sort_key) or any(
            earlier.sort_key >= later.sort_key for earlier, later in pairwise(history)
        ):
            raise ValueError("Wave 64 history must strictly precede the target in draw order")
        request = LegacyXGBoostNativeWave64Request(
            target_draw_number=target.draw_number,
            target_draw_date=target.draw_date,
            history=tuple(
                LegacyHistoryDraw(row.draw_number, cast(Ticket, row.main_numbers))
                for row in history
            ),
            dataset_sha256=PINNED_DATASET_SHA256,
        )
        try:
            result = generate_legacy_xgboost_native_wave64_portfolio(request)
        except LegacyXGBoostNativeWave64SourceError as exc:
            if exc.reason_code == CLOSED_REASON:
                raise RecordedInsufficientHistory(CLOSED_REASON) from exc
            if exc.reason_code == "TARGET_OUTSIDE_FROZEN_WAVE64_TICKET_LEDGER":
                raise ReplayTypedClosure(exc.reason_code) from exc
            raise
        return tuple(ReplayTicket(i, ticket) for i, ticket in enumerate(result.tickets, 1))
