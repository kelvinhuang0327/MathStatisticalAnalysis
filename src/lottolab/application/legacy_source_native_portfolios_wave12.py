"""Faithful port of the twelfth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE12_PROTOCOL = "legacy_source_native_wave12/v1"
DEFAULT_SOURCE_NATIVE_WAVE12_USER_SEED = (
    "biglotto-full-universe-source-native-wave12-v1"
)
MODERATE_SELECTION_METHOD_ID = "tools/optimize_moderate_selection.py"
SUPPORTED_SOURCE_NATIVE_WAVE12_METHODS = (
    MODERATE_SELECTION_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: (
        "7e2c3a0ab92f78f39628a3677168d844765d52d06bb2a084d16cd098e468fed7"
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: 50,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: (
        "180_FROZEN_GRID_CONFIGURATIONS_X_2_POSITIONAL_TICKETS_"
        "FLATTENED_TO_360_WITH_REPEATS"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: "NONE_DETERMINISTIC",
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: 180,
}
_PENALTIES = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)
_HOT_RANK_MINS = (3, 4, 5, 6)
_COLD_GAP_RANGES = ((6, 10), (7, 11), (8, 12), (9, 13), (10, 14))
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: tuple(
        "penalty="
        f"{penalty:.2f}|hot_rank_min={hot_rank_min}|"
        f"cold_gap={cold_min}-{cold_max}"
        for penalty in _PENALTIES
        for hot_rank_min in _HOT_RANK_MINS
        for cold_min, cold_max in _COLD_GAP_RANGES
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: "OLDEST_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacySourceNativeWave12Error(ValueError):
    """A request cannot satisfy the twelfth source-native contract."""


class LegacySourceNativeWave12SourceError(
    LegacySourceNativeWave12Error
):
    """A frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave12Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE12_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave12Metadata:
    protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    replicate_id: int
    user_seed: str | int
    seed_material: str
    seed_digest: str
    seed_integer: int
    random_protocol: str
    randomness_used: bool
    randomness_reproduction: str
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    source_combination_members: tuple[str, ...]
    source_candidate_ticket_counts: tuple[int, ...]
    source_runtime_parameters: tuple[str, ...]
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave12Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave12Metadata


History = tuple[tuple[int, ...], ...]


def _validate_request(request: LegacySourceNativeWave12Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD
    ):
        raise LegacySourceNativeWave12Error(
            "legacy method is outside the twelfth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave12Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave12Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave12Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave12Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave12Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE12_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _ticket(numbers: tuple[int, ...] | list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int
            or not _MIN_NUMBER <= number <= _MAX_NUMBER
            for number in values
        )
    ):
        raise LegacySourceNativeWave12SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


@dataclass(frozen=True, slots=True)
class _Features:
    last_draw_numbers: frozenset[int]
    gaps: dict[int, int]
    frequency_30: Counter[int]
    frequency_50: Counter[int]
    frequency_rank: dict[int, int]


def _frequency(
    history: History,
    *,
    window: int,
) -> Counter[int]:
    frequency: Counter[int] = Counter()
    recent = history[-window:] if len(history) >= window else history
    for draw in recent:
        for number in draw:
            frequency[number] += 1
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number not in frequency:
            frequency[number] = 0
    return frequency


def _features(history: History) -> _Features:
    gaps = {
        number: len(history)
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    for index, draw in enumerate(reversed(history)):
        for number in draw:
            if gaps[number] == len(history):
                gaps[number] = index
    frequency_30 = _frequency(history, window=30)
    frequency_50 = _frequency(history, window=50)
    frequency_sorted = sorted(
        frequency_30.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return _Features(
        last_draw_numbers=frozenset(history[-1]),
        gaps=gaps,
        frequency_30=frequency_30,
        frequency_50=frequency_50,
        frequency_rank={
            number: rank
            for rank, (number, _count) in enumerate(
                frequency_sorted,
                1,
            )
        },
    )


def _moderate_selection(
    features: _Features,
    *,
    last_draw_penalty: float,
    hot_rank_min: int,
    hot_rank_max: int,
    cold_gap_min: int,
    cold_gap_max: int,
) -> list[int]:
    scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        gap = features.gaps[number]
        frequency_30 = features.frequency_30[number]
        frequency_50 = features.frequency_50[number]
        rank = features.frequency_rank[number]
        base_score = (
            frequency_30 * 2 + frequency_50 + gap * 0.5
        )
        if rank < hot_rank_min:
            base_score *= 0.7
        if hot_rank_min <= rank <= hot_rank_max:
            base_score *= 1.2
        if gap > 15:
            base_score *= 0.6
        if cold_gap_min <= gap <= cold_gap_max:
            base_score *= 1.3
        if number in features.last_draw_numbers:
            base_score *= last_draw_penalty
        scores[number] = base_score
    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return sorted(number for number, _score in ranked[:_PICK_COUNT])


def _native_tickets(history: History) -> tuple[list[int], ...]:
    features = _features(history)
    tickets: list[list[int]] = []
    for penalty in _PENALTIES:
        for hot_rank_min in _HOT_RANK_MINS:
            for cold_min, cold_max in _COLD_GAP_RANGES:
                for bet_index in range(2):
                    adjusted_penalty = penalty * (
                        1 + bet_index * 0.1
                    )
                    tickets.append(
                        _moderate_selection(
                            features,
                            last_draw_penalty=min(
                                adjusted_penalty,
                                0.5,
                            ),
                            hot_rank_min=(
                                hot_rank_min + bet_index * 2
                            ),
                            hot_rank_max=15,
                            cold_gap_min=cold_min,
                            cold_gap_max=cold_max,
                        )
                    )
    return tuple(tickets)


def generate_legacy_source_native_wave12_portfolio(
    request: LegacySourceNativeWave12Request,
) -> LegacySourceNativeWave12Result:
    """Generate source-grid-ordered native tickets from prior history."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave12Error(
            f"method requires at least {minimum} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    raw_tickets = _native_tickets(
        tuple(draw.numbers for draw in request.history)
    )
    if not raw_tickets:
        raise LegacySourceNativeWave12SourceError(
            "FROZEN_SOURCE_NO_NATIVE_TICKETS"
        )
    tickets = tuple(_ticket(ticket) for ticket in raw_tickets)
    return LegacySourceNativeWave12Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave12Metadata(
            protocol=SOURCE_NATIVE_WAVE12_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol="NONE_DETERMINISTIC",
            randomness_used=False,
            randomness_reproduction="SOURCE_DETERMINISTIC",
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_PENALTY_HOT_RANK_COLD_GAP_AND_BET_LOOP_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            source_combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(2,) * 180,
            source_runtime_parameters=(
                "source_test_periods=300",
                "source_num_bets=2",
                "hot_rank_max=15",
                "extreme_cold_penalty=0.6",
            ),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE12_USER_SEED",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "MODERATE_SELECTION_METHOD_ID",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "SOURCE_NATIVE_WAVE12_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE12_METHODS",
    "LegacySourceNativeWave12Error",
    "LegacySourceNativeWave12Metadata",
    "LegacySourceNativeWave12Request",
    "LegacySourceNativeWave12Result",
    "LegacySourceNativeWave12SourceError",
    "generate_legacy_source_native_wave12_portfolio",
]
