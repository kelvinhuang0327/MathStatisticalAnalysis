"""Ports the application layer depends on; infrastructure provides implementations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from quantlab.domain.lottery.draws import Draw, LotteryType


class DrawRepository(Protocol):
    def recent_draws(self, lottery_type: LotteryType, limit: int) -> Sequence[Draw]:
        """Return draws newest-first, ordered by numeric draw id."""
        ...
