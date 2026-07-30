"""Faithful port of the twenty-first frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave20 import (
    generate_frozen_zone_balance_ticket,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE21_PROTOCOL = "legacy_source_native_wave21/v1"
DEFAULT_SOURCE_NATIVE_WAVE21_USER_SEED = (
    "biglotto-full-universe-source-native-wave21-v1"
)
POST_SELECTION_FILTER_METHOD_ID = "tools/backtest_strategy_1.py"
SUPPORTED_SOURCE_NATIVE_WAVE21_METHODS = (
    POST_SELECTION_FILTER_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: (
        "41ed79a6de6255bee0f5197bb6df1b75c2e417e006d165bd6feaa9dcfff842f3"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: (
        (
            "lottery_api/models/unified_predictor.py",
            "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004",
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: (
        "TWO_POSITIONAL_POST_SELECTION_TICKETS_FREQUENCY_50_"
        "DANGER_FILTER_THEN_ZONE_BALANCE_500_OR_510"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: "NONE_DETERMINISTIC",
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: 2,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: (
        "frequency_50_with_post_selection_danger_filter",
        "zone_balance_500_with_danger_triggered_510_retry",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE21_METHOD: Final = {
    POST_SELECTION_FILTER_METHOD_ID: "OLDEST_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacySourceNativeWave21Error(ValueError):
    """A request cannot satisfy the twenty-first source-native contract."""


class LegacySourceNativeWave21SourceError(
    LegacySourceNativeWave21Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave21Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE21_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave21Metadata:
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
    source_candidate_k_values: tuple[int, ...]
    frozen_support_artifacts: tuple[tuple[str, str], ...]
    source_runtime_parameters: tuple[str, ...]
    danger_numbers: tuple[int, ...]
    zone_retry_used: bool
    zone_fallback_used: bool
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave21Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave21Metadata


def _ticket(numbers: list[int]) -> Ticket:
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
        raise LegacySourceNativeWave21SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacySourceNativeWave21Request) -> None:
    if request.legacy_method_id != POST_SELECTION_FILTER_METHOD_ID:
        raise LegacySourceNativeWave21Error(
            "legacy method is outside the twenty-first source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave21Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave21Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave21Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave21Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacySourceNativeWave21Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE21_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _danger_numbers(
    history: tuple[LegacyHistoryDraw, ...],
) -> set[int]:
    if len(history) < 3:
        return set()
    return (
        set(history[-1].numbers)
        & set(history[-2].numbers)
        & set(history[-3].numbers)
    )


def _frequency_ticket(
    history: tuple[LegacyHistoryDraw, ...],
    danger_numbers: set[int],
) -> tuple[Ticket, int]:
    history_50 = history[-50:]
    frequency = Counter(
        number for draw in history_50 for number in draw.numbers
    )
    candidates = [
        number for number, _count in frequency.most_common()
    ]
    selected: list[int] = []
    pointer = 0
    while len(selected) < _PICK_COUNT and pointer < len(candidates):
        number = candidates[pointer]
        if number not in danger_numbers:
            selected.append(number)
        pointer += 1
    return _ticket(selected), len(candidates)


def _zone_ticket(
    history: tuple[LegacyHistoryDraw, ...],
    danger_numbers: set[int],
) -> tuple[Ticket, bool, bool]:
    retry_used = False
    fallback_used = False
    try:
        ticket = generate_frozen_zone_balance_ticket(history[-500:])
        if set(ticket) & danger_numbers:
            retry_used = True
            ticket = generate_frozen_zone_balance_ticket(history[-510:])
    except Exception:
        fallback_used = True
        ticket = (1, 2, 3, 4, 5, 6)
    return _ticket(list(ticket)), retry_used, fallback_used


def generate_legacy_source_native_wave21_portfolio(
    request: LegacySourceNativeWave21Request,
) -> LegacySourceNativeWave21Result:
    """Reproduce both frozen post-selection ticket positions causally."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE21_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave21SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    danger_numbers = _danger_numbers(request.history)
    frequency_ticket, frequency_candidate_count = _frequency_ticket(
        request.history,
        danger_numbers,
    )
    zone_ticket, zone_retry_used, zone_fallback_used = _zone_ticket(
        request.history,
        danger_numbers,
    )
    tickets = (frequency_ticket, zone_ticket)
    metadata = LegacySourceNativeWave21Metadata(
        protocol=SOURCE_NATIVE_WAVE21_PROTOCOL,
        legacy_method_id=request.legacy_method_id,
        source_sha256=(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD[
                request.legacy_method_id
            ]
        ),
        target_draw_number=request.target_draw_number,
        replicate_id=request.replicate_id,
        user_seed=request.user_seed,
        seed_material=seed_material,
        seed_digest=seed_digest,
        seed_integer=seed_integer,
        random_protocol=(
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE21_METHOD[
                request.legacy_method_id
            ]
        ),
        randomness_used=False,
        randomness_reproduction="NONE_DETERMINISTIC",
        history_draw_count=len(request.history),
        history_first_draw_number=request.history[0].draw_number,
        history_cutoff_draw_number=request.history[-1].draw_number,
        source_history_order=(
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE21_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_count=len(tickets),
        native_ticket_count_semantics=(
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE21_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_order=(
            "FREQUENCY_50_POST_SELECTION_FIRST_THEN_ZONE_BALANCE_"
            "500_OR_DANGER_TRIGGERED_510"
        ),
        native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
        source_combination_members=(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE21_METHOD[
                request.legacy_method_id
            ]
        ),
        source_candidate_ticket_counts=(
            frequency_candidate_count,
            _MAX_NUMBER,
        ),
        source_candidate_k_values=(),
        frozen_support_artifacts=(
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE21_METHOD[
                request.legacy_method_id
            ]
        ),
        source_runtime_parameters=(
            "frequency_window=50",
            "danger_streak_draw_count=3",
            "zone_primary_window=500",
            "zone_retry_window=510",
            "zone_fallback_ticket=1,2,3,4,5,6",
        ),
        danger_numbers=tuple(sorted(danger_numbers)),
        zone_retry_used=zone_retry_used,
        zone_fallback_used=zone_fallback_used,
        candidate_k=None,
        combination_count=None,
    )
    return LegacySourceNativeWave21Result(
        tickets=tickets,
        metadata=metadata,
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE21_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "POST_SELECTION_FILTER_METHOD_ID",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "SOURCE_NATIVE_WAVE21_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE21_METHODS",
    "LegacySourceNativeWave21Error",
    "LegacySourceNativeWave21Metadata",
    "LegacySourceNativeWave21Request",
    "LegacySourceNativeWave21Result",
    "LegacySourceNativeWave21SourceError",
    "generate_legacy_source_native_wave21_portfolio",
]
