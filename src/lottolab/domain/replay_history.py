"""Replay-specific, read-only causal Big Lotto draw history types.

This module is intentionally narrow: it defines the immutable row shape used
by Replay's causal-history boundary. It is unrelated to
:class:`lottolab.strategies.adapters.base.CausalDrawRow`, which is a
different, already-existing type used by strategy adapters (no special
number, ``draw``/``date``/``numbers`` fields) — do not conflate the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT


@dataclass(frozen=True, slots=True)
class ReplayCausalDrawRow:
    """One immutable BIG_LOTTO draw strictly preceding a Replay target draw."""

    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int

    def __post_init__(self) -> None:
        rule = BIG_LOTTO_RULE_CONTRACT
        if type(self.draw_number) is not str or not self.draw_number:
            raise ValueError("draw_number must be a non-empty string")
        if type(self.draw_date) is not date:
            raise ValueError("draw_date must be a date")
        if type(self.main_numbers) is not tuple:
            raise ValueError("main_numbers must be a tuple")
        if len(self.main_numbers) != rule.main_number_count:
            raise ValueError(
                f"main_numbers must contain exactly {rule.main_number_count} numbers"
            )
        if not all(type(number) is int for number in self.main_numbers):
            raise ValueError("main_numbers must contain only exact built-in integers")
        if not all(
            rule.main_number_min <= number <= rule.main_number_max
            for number in self.main_numbers
        ):
            raise ValueError(
                f"main_numbers must fall within "
                f"[{rule.main_number_min}..{rule.main_number_max}]"
            )
        if rule.main_numbers_unique and len(set(self.main_numbers)) != rule.main_number_count:
            raise ValueError("main_numbers must not contain duplicates")
        if type(self.special_number) is not int:
            raise ValueError("special_number must be an exact built-in integer")
        if not (rule.special_number_min <= self.special_number <= rule.special_number_max):
            raise ValueError(
                f"special_number must fall within "
                f"[{rule.special_number_min}..{rule.special_number_max}]"
            )
        if not rule.main_special_overlap_allowed and self.special_number in self.main_numbers:
            raise ValueError("special_number must not overlap main_numbers")


__all__ = ["ReplayCausalDrawRow"]
