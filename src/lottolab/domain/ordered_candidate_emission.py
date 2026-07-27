"""Immutable producer-ordered candidate emission values.

This boundary records only caller-supplied, target-native values. It performs
no I/O and never fills identity or auxiliary fields from ambient state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_evidence import candidate_game_rule

ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION = "1.0.0"

_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)


class AuxiliaryOperandKind(StrEnum):
    BIG_LOTTO_SPECIAL = "BIG_LOTTO_SPECIAL"
    POWER_LOTTO_ZONE2 = "POWER_LOTTO_ZONE2"
    DAILY_539 = "DAILY_539"


class AuxiliaryOperandAvailability(StrEnum):
    PRESENT = "PRESENT"
    EXPLICITLY_MISSING = "EXPLICITLY_MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


def _require_canonical_text(value: object, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty canonical string")


def _require_decimal_draw(value: object, name: str) -> None:
    if type(value) is not str or _ASCII_DECIMAL.fullmatch(value) is None:
        raise ValueError(f"{name} must be an ASCII decimal draw identity")


@dataclass(frozen=True, slots=True)
class OrderedCandidateEmission:
    """One closed, source-ordered strategy emission for a causal target."""

    schema_version: str
    lottery_type: LotteryType
    strategy_id: str
    strategy_version: str
    replicate: int
    target_draw: str
    history_cutoff: str
    emitted_main_numbers: tuple[int, ...]
    auxiliary_operand_kind: AuxiliaryOperandKind
    auxiliary_operand_availability: AuxiliaryOperandAvailability
    auxiliary_operand_value: int | None

    def __post_init__(self) -> None:
        if self.schema_version != ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must be exactly "
                f"{ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION}"
            )
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        _require_canonical_text(self.strategy_id, "strategy_id")
        _require_canonical_text(self.strategy_version, "strategy_version")
        if type(self.replicate) is not int or self.replicate < 1:
            raise ValueError("replicate must be an integer >= 1")
        _require_decimal_draw(self.target_draw, "target_draw")
        _require_decimal_draw(self.history_cutoff, "history_cutoff")
        if int(self.target_draw) <= int(self.history_cutoff):
            raise ValueError("target_draw must be after history_cutoff")

        game_rule = candidate_game_rule(self.lottery_type)
        if (
            type(self.emitted_main_numbers) is not tuple
            or not self.emitted_main_numbers
            or any(type(number) is not int for number in self.emitted_main_numbers)
        ):
            raise ValueError(
                "emitted_main_numbers must be a non-empty immutable integer tuple"
            )
        if any(
            not 1 <= number <= game_rule.main_pool_size
            for number in self.emitted_main_numbers
        ):
            raise ValueError("emitted_main_numbers contains an out-of-range number")

        if type(self.auxiliary_operand_kind) is not AuxiliaryOperandKind:
            raise ValueError("auxiliary_operand_kind must be an AuxiliaryOperandKind")
        if (
            type(self.auxiliary_operand_availability)
            is not AuxiliaryOperandAvailability
        ):
            raise ValueError(
                "auxiliary_operand_availability must be an "
                "AuxiliaryOperandAvailability"
            )

        expected_kind = {
            LotteryType.BIG_LOTTO: AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
            LotteryType.POWER_LOTTO: AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
            LotteryType.DAILY_539: AuxiliaryOperandKind.DAILY_539,
        }[self.lottery_type]
        if self.auxiliary_operand_kind is not expected_kind:
            raise ValueError("auxiliary_operand_kind does not match lottery_type")

        availability = self.auxiliary_operand_availability
        if self.lottery_type is LotteryType.DAILY_539:
            if (
                availability is not AuxiliaryOperandAvailability.NOT_APPLICABLE
                or self.auxiliary_operand_value is not None
            ):
                raise ValueError(
                    "Daily 539 requires NOT_APPLICABLE with no auxiliary value"
                )
            return

        if availability is AuxiliaryOperandAvailability.PRESENT:
            auxiliary_pool_size = game_rule.auxiliary_pool_size
            if (
                auxiliary_pool_size is None
                or type(self.auxiliary_operand_value) is not int
                or not 1 <= self.auxiliary_operand_value <= auxiliary_pool_size
            ):
                raise ValueError(
                    "a present auxiliary operand must be an exact in-range integer"
                )
        elif availability is AuxiliaryOperandAvailability.EXPLICITLY_MISSING:
            if self.auxiliary_operand_value is not None:
                raise ValueError(
                    "an explicitly missing auxiliary operand must have value None"
                )
        else:
            raise ValueError(
                "Big Lotto and Power Lotto require PRESENT or EXPLICITLY_MISSING"
            )


__all__ = [
    "ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION",
    "AuxiliaryOperandAvailability",
    "AuxiliaryOperandKind",
    "OrderedCandidateEmission",
]
