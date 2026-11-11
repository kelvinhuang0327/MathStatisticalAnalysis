"""Reproducible, versioned replay of a stochastic single-ticket adapter.

This wrapper never changes the historical unseeded implementation or its
saved results. Its derived seed depends on the strategy ID and causal history,
not the target outcome, process-global random state, or execution order.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from typing import Any

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayTicket
from lottolab.strategies.adapters.base import CausalDrawRow

SEED_CONTRACT = "seeded-single-causal-history-sha256-v1"


def seeded_replay_version(source_version: str) -> str:
    """Name the seeded replay separately from its unseeded source version."""
    return f"{source_version}+seeded-replay-v1"


def replay_seed(strategy_id: str, history: tuple[ReplayDraw, ...]) -> int:
    payload = {
        "contract": SEED_CONTRACT,
        "strategy_id": strategy_id,
        "history": [
            [d.draw_number, d.draw_date.isoformat(), list(d.main_numbers), d.special_number]
            for d in history
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(raw.encode("utf-8")).digest(), "big")


class SeededSingleTicketReplay:
    """Construct a fresh adapter and private stream for every replay target."""

    native_ticket_count = 1

    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        source_version: str,
        min_history: int,
        factory: Callable[[random.Random], Any],
    ) -> None:
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.strategy_version = seeded_replay_version(source_version)
        self.min_history = min_history
        self._factory = factory

    def get_replay_tickets(
        self, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> tuple[ReplayTicket, ...]:
        if any(draw.sort_key >= target.sort_key for draw in history):
            raise ValueError("history must strictly precede target")
        rows = tuple(
            CausalDrawRow(d.draw_number, d.draw_date.isoformat(), d.main_numbers) for d in history
        )
        implementation = self._factory(random.Random(replay_seed(self.strategy_id, history)))
        numbers, special = implementation.get_one_bet(rows, LotteryType.BIG_LOTTO)
        return (ReplayTicket(1, numbers, special),)
