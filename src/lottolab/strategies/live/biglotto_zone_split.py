"""Internal port of the legacy live Zone Split core (P605C).

This preserves the donor ``ZoneSplitStrategy.generate_bets`` /
``get_zone_split_predictor`` callable's actual behavioral semantics for
BIG_LOTTO — no causal history, equal zone partitioning with a ±2 overlap,
last-zone remainder absorption, pool widening, and one independent sample
per zone — as a standalone, dependency-free compatibility component. It is
distinct from the deterministic, catalog-registered
``biglotto_zone_split_3bet_bet1`` strategy: shared zone geometry does not
imply behavioral equivalence, and nothing here is registered, executable,
or reachable through the catalog, ExecutableRegistry, CLI, HTTP, or
frontend. See docs/migration/migration-ledger.yaml
(``lottery.prediction.generate``) for the full compatibility-track note.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT

_MIN_NUM_BETS = 1
_MAX_NUM_BETS = 10
_DEFAULT_NUM_BETS = 3
_OVERLAP_SIZE = 2
_METHOD_ID = "biglotto_live_zone_split_core_port"
_PHILOSOPHY = (
    "Legacy live Zone Split core port (P605C): an internal, unregistered "
    "compatibility component preserving the donor's no-history, multi-bet "
    "spatial-diversification semantics. Distinct from the deterministic "
    "biglotto_zone_split_3bet_bet1 strategy — shared zone geometry does not "
    "imply behavioral equivalence."
)


class Sampler(Protocol):
    """A callable drawing ``k`` unique numbers from ``population``."""

    def __call__(self, population: Sequence[int], k: int, /) -> Sequence[int]: ...


class MalformedSamplerOutput(ValueError):
    """An injected sampler or RNG returned output violating the bet contract."""


@dataclass(frozen=True, slots=True)
class LiveZoneSplitResult:
    """Immutable multi-bet Zone Split result with donor-compatible metadata."""

    bets: tuple[tuple[int, ...], ...]
    coverage_rate: float
    total_unique_numbers: int
    method: str = _METHOD_ID
    philosophy: str = _PHILOSOPHY


def _validate_num_bets(num_bets: object) -> int:
    """Reject non-``int`` (including ``bool``) and out-of-range values."""

    if type(num_bets) is not int:
        raise TypeError("num_bets must be an exact int (bool and float are rejected)")
    if not (_MIN_NUM_BETS <= num_bets <= _MAX_NUM_BETS):
        raise ValueError(
            f"num_bets must be between {_MIN_NUM_BETS} and {_MAX_NUM_BETS}, got {num_bets}"
        )
    return num_bets


def _resolve_sampler(sampler: Sampler | random.Random | None) -> Sampler:
    """Accept an injected callable sampler, an RNG exposing ``.sample``, or none.

    The production default (``sampler=None``) creates a fresh, unseeded
    ``random.Random`` private to this call — never the process-global
    ``random`` module — so production randomness never mutates global state.
    """

    if sampler is None:
        rng = random.Random()

        def _default_sampler(population: Sequence[int], k: int, /) -> Sequence[int]:
            return rng.sample(population, k)

        return _default_sampler
    if isinstance(sampler, random.Random):
        rng = sampler

        def _rng_sampler(population: Sequence[int], k: int, /) -> Sequence[int]:
            return rng.sample(population, k)

        return _rng_sampler
    return sampler


def _zone_pool(
    index: int,
    num_bets: int,
    *,
    min_num: int,
    max_num: int,
    pick_count: int,
) -> tuple[int, ...]:
    """Return one zone's candidate pool, widening to the full range if too small."""

    full_range = max_num - min_num + 1
    zone_size = full_range // num_bets
    start = min_num + index * zone_size
    end = min_num + (index + 1) * zone_size - 1
    if index == num_bets - 1:
        end = max_num
    pool = tuple(
        range(max(min_num, start - _OVERLAP_SIZE), min(max_num, end + _OVERLAP_SIZE) + 1)
    )
    if len(pool) < pick_count:
        pool = tuple(range(min_num, max_num + 1))
    return pool


def _validate_bet(
    raw: object,
    *,
    pick_count: int,
    min_num: int,
    max_num: int,
) -> tuple[int, ...]:
    """Validate one sampler-produced bet, failing closed on any contract violation."""

    if type(raw) not in (list, tuple):
        raise MalformedSamplerOutput("sampler must return a list or tuple")
    candidates = cast("tuple[object, ...]", tuple(raw))  # type: ignore[call-overload]
    if len(candidates) != pick_count:
        raise MalformedSamplerOutput(f"sampler must return exactly {pick_count} numbers")
    if not all(type(candidate) is int for candidate in candidates):
        raise MalformedSamplerOutput("sampler must return exact built-in integers")
    values = cast("tuple[int, ...]", candidates)
    if len(set(values)) != pick_count:
        raise MalformedSamplerOutput("sampler returned duplicate numbers")
    if not all(min_num <= value <= max_num for value in values):
        raise MalformedSamplerOutput(f"sampler returned a number outside [{min_num}..{max_num}]")
    return tuple(sorted(values))


def generate_live_zone_split_bets(
    num_bets: int = _DEFAULT_NUM_BETS,
    sampler: Sampler | random.Random | None = None,
) -> LiveZoneSplitResult:
    """Port of the legacy ``ZoneSplitStrategy.generate_bets`` core for BIG_LOTTO.

    No causal history is accepted or used. Production calls (``sampler=None``)
    draw from a fresh, unseeded ``random.Random`` instance private to this
    call; the process-global ``random`` module state is never read or
    mutated. Tests inject a deterministic ``sampler`` callable or
    ``random.Random`` instance for exact, reproducible, mutation-sensitive
    assertions without changing production semantics.
    """

    validated_num_bets = _validate_num_bets(num_bets)
    resolved_sampler = _resolve_sampler(sampler)

    rule = BIG_LOTTO_RULE_CONTRACT
    min_num = rule.main_number_min
    max_num = rule.main_number_max
    pick_count = rule.main_number_count

    bets: list[tuple[int, ...]] = []
    for index in range(validated_num_bets):
        pool = _zone_pool(
            index,
            validated_num_bets,
            min_num=min_num,
            max_num=max_num,
            pick_count=pick_count,
        )
        raw_bet = resolved_sampler(pool, pick_count)
        bets.append(
            _validate_bet(raw_bet, pick_count=pick_count, min_num=min_num, max_num=max_num)
        )

    all_numbers = {number for bet in bets for number in bet}
    full_range = max_num - min_num + 1
    coverage_rate = round(len(all_numbers) / full_range, 4)

    return LiveZoneSplitResult(
        bets=tuple(bets),
        coverage_rate=coverage_rate,
        total_unique_numbers=len(all_numbers),
    )


__all__ = [
    "LiveZoneSplitResult",
    "MalformedSamplerOutput",
    "Sampler",
    "generate_live_zone_split_bets",
]
