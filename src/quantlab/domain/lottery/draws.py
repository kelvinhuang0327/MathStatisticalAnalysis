"""Core draw entities shared by every lottery model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LotteryType(StrEnum):
    DAILY_539 = "DAILY_539"
    BIG_LOTTO = "BIG_LOTTO"
    POWER_LOTTO = "POWER_LOTTO"


@dataclass(frozen=True, slots=True)
class Draw:
    """A single historical draw.

    ``draw_id`` is text on purpose (legacy data stores it as TEXT); ordering
    must always go through :attr:`sort_key` — lexicographic ordering of draw
    ids has caused real bugs in the legacy system.
    """

    lottery_type: LotteryType
    draw_id: str
    numbers: tuple[int, ...]
    special: int | None = None

    @property
    def sort_key(self) -> int:
        return int(self.draw_id)
