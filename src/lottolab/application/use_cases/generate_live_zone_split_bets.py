"""Standalone application use case for the internal live Zone Split multi-bet core.

Wraps the merged P605C core (``lottolab.strategies.live.biglotto_zone_split``)
in a closed status/reason-code envelope. The request carries only
``num_bets``: no causal history, no strategy_id/lottery_type dispatch, and no
caller-facing seed or sampler. Production calls preserve the core's
call-local, unseeded nondeterminism; tests inject a deterministic generator
via constructor injection. Distinct from, and never routes through,
``GenerateOneBet``. See docs/migration/migration-ledger.yaml
(``lottery.prediction.generate``) for the compatibility-track note.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.strategies.live.biglotto_zone_split import (
    LiveZoneSplitResult,
    MalformedSamplerOutput,
    generate_live_zone_split_bets,
)

_MIN_NUM_BETS = 1
_MAX_NUM_BETS = 10
_EXPECTED_BET_LENGTH = 6


class GenerateLiveZoneSplitBetsStatus(StrEnum):
    OK = "OK"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class GenerateLiveZoneSplitBetsReason(StrEnum):
    INVALID_NUM_BETS = "INVALID_NUM_BETS"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    EXECUTION_ERROR = "EXECUTION_ERROR"


@dataclass(frozen=True, slots=True)
class GenerateLiveZoneSplitBetsInput:
    num_bets: int


@dataclass(frozen=True, slots=True)
class GenerateLiveZoneSplitBetsResult:
    status: GenerateLiveZoneSplitBetsStatus
    bets: tuple[tuple[int, ...], ...] | None
    coverage_rate: float | None
    total_unique_numbers: int | None
    method: str | None
    philosophy: str | None
    reason_code: GenerateLiveZoneSplitBetsReason | None

    def __post_init__(self) -> None:
        if self.status is GenerateLiveZoneSplitBetsStatus.OK:
            if (
                self.bets is None
                or self.coverage_rate is None
                or self.total_unique_numbers is None
                or self.method is None
                or self.philosophy is None
                or self.reason_code is not None
            ):
                raise ValueError("OK results require every payload field and no reason code")
        elif (
            self.bets is not None
            or self.coverage_rate is not None
            or self.total_unique_numbers is not None
            or self.method is not None
            or self.philosophy is not None
            or self.reason_code is None
        ):
            raise ValueError("non-OK results require a reason code and no payload fields")


class LiveZoneSplitGenerator(Protocol):
    """A callable producing one multi-bet live Zone Split result."""

    def __call__(self, num_bets: int) -> LiveZoneSplitResult: ...


class GenerateLiveZoneSplitBets:
    """Resolve the injected generator and convert every outcome to a closed result."""

    def __init__(self, generator: LiveZoneSplitGenerator) -> None:
        self._generator = generator

    def execute(
        self, request: GenerateLiveZoneSplitBetsInput
    ) -> GenerateLiveZoneSplitBetsResult:
        num_bets = request.num_bets
        if type(num_bets) is not int or not (_MIN_NUM_BETS <= num_bets <= _MAX_NUM_BETS):
            return self._failure(
                GenerateLiveZoneSplitBetsStatus.INVALID_REQUEST,
                GenerateLiveZoneSplitBetsReason.INVALID_NUM_BETS,
            )

        try:
            raw_result = self._generator(num_bets)
        except MalformedSamplerOutput:
            return self._failure(
                GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT,
                GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT,
            )
        except Exception:
            return self._failure(
                GenerateLiveZoneSplitBetsStatus.EXECUTION_ERROR,
                GenerateLiveZoneSplitBetsReason.EXECUTION_ERROR,
            )

        validated = self._validate_output(raw_result, num_bets)
        if validated is None:
            return self._failure(
                GenerateLiveZoneSplitBetsStatus.INVALID_OUTPUT,
                GenerateLiveZoneSplitBetsReason.MALFORMED_OUTPUT,
            )
        bets, coverage_rate, total_unique_numbers, method, philosophy = validated

        return GenerateLiveZoneSplitBetsResult(
            status=GenerateLiveZoneSplitBetsStatus.OK,
            bets=bets,
            coverage_rate=coverage_rate,
            total_unique_numbers=total_unique_numbers,
            method=method,
            philosophy=philosophy,
            reason_code=None,
        )

    @staticmethod
    def _validate_output(
        raw_result: object, num_bets: int
    ) -> tuple[tuple[tuple[int, ...], ...], float, int, str, str] | None:
        if type(raw_result) is not LiveZoneSplitResult:
            return None

        bets = raw_result.bets
        if type(bets) is not tuple or len(bets) != num_bets:
            return None

        min_num = BIG_LOTTO_RULE_CONTRACT.main_number_min
        max_num = BIG_LOTTO_RULE_CONTRACT.main_number_max
        pick_count = BIG_LOTTO_RULE_CONTRACT.main_number_count
        if pick_count != _EXPECTED_BET_LENGTH:
            return None

        all_numbers: set[int] = set()
        for bet in bets:
            if type(bet) is not tuple or len(bet) != pick_count:
                return None
            if not all(type(number) is int for number in bet):
                return None
            if len(set(bet)) != pick_count:
                return None
            if not all(min_num <= number <= max_num for number in bet):
                return None
            all_numbers.update(bet)

        total_unique_numbers = raw_result.total_unique_numbers
        if type(total_unique_numbers) is not int or total_unique_numbers != len(all_numbers):
            return None

        full_range = max_num - min_num + 1
        coverage_rate = raw_result.coverage_rate
        expected_coverage_rate = round(len(all_numbers) / full_range, 4)
        if type(coverage_rate) is not float or coverage_rate != expected_coverage_rate:
            return None

        method = raw_result.method
        if type(method) is not str or not method:
            return None

        philosophy = raw_result.philosophy
        if type(philosophy) is not str or not philosophy:
            return None

        return bets, coverage_rate, total_unique_numbers, method, philosophy

    @staticmethod
    def _failure(
        status: GenerateLiveZoneSplitBetsStatus,
        reason: GenerateLiveZoneSplitBetsReason,
    ) -> GenerateLiveZoneSplitBetsResult:
        return GenerateLiveZoneSplitBetsResult(
            status=status,
            bets=None,
            coverage_rate=None,
            total_unique_numbers=None,
            method=None,
            philosophy=None,
            reason_code=reason,
        )


def build_production_generate_live_zone_split_bets() -> GenerateLiveZoneSplitBets:
    """Compose the merged P605C live Zone Split core with no RNG/sampler exposure.

    The production generator always calls the core with ``sampler=None``, so
    each call draws from a fresh, unseeded ``random.Random`` private to that
    call — the core's existing call-local nondeterminism is preserved
    unchanged.
    """

    def _production_generator(num_bets: int) -> LiveZoneSplitResult:
        return generate_live_zone_split_bets(num_bets=num_bets)

    return GenerateLiveZoneSplitBets(_production_generator)


__all__ = [
    "GenerateLiveZoneSplitBets",
    "GenerateLiveZoneSplitBetsInput",
    "GenerateLiveZoneSplitBetsReason",
    "GenerateLiveZoneSplitBetsResult",
    "GenerateLiveZoneSplitBetsStatus",
    "LiveZoneSplitGenerator",
    "build_production_generate_live_zone_split_bets",
]
