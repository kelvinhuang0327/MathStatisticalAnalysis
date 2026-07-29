"""Faithful port of the twentieth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE20_PROTOCOL = "legacy_source_native_wave20/v1"
DEFAULT_SOURCE_NATIVE_WAVE20_USER_SEED = (
    "biglotto-full-universe-source-native-wave20-v1"
)
ZONE_BALANCE_500_METHOD_ID = (
    "predict_biglotto_115000002_zone_balance.py"
)
SUPPORTED_SOURCE_NATIVE_WAVE20_METHODS = (
    ZONE_BALANCE_500_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: (
        "8febca575f5d61b28095b1a27ff92b9717f74da88dd810ec0837fabba9033d02"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: (
        (
            "lottery_api/models/unified_predictor.py",
            "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004",
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: (
        "FIVE_POSITIONAL_ZONE_BALANCE_OUTPUTS_MAIN_500_THEN_"
        "COMPARISON_100_200_300_500_INCLUDING_REPEATED_500"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: "NONE_DETERMINISTIC",
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: 4,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: (
        "zone_balance_predict:window=100",
        "zone_balance_predict:window=200",
        "zone_balance_predict:window=300",
        "zone_balance_predict:window=500",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE20_METHOD: Final = {
    ZONE_BALANCE_500_METHOD_ID: "OLDEST_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_SOURCE_WINDOWS = (100, 200, 300, 500)


class LegacySourceNativeWave20Error(ValueError):
    """A request cannot satisfy the twentieth source-native contract."""


class LegacySourceNativeWave20SourceError(
    LegacySourceNativeWave20Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave20Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE20_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave20Metadata:
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
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave20Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave20Metadata


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
        raise LegacySourceNativeWave20SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacySourceNativeWave20Request) -> None:
    if request.legacy_method_id != ZONE_BALANCE_500_METHOD_ID:
        raise LegacySourceNativeWave20Error(
            "legacy method is outside the twentieth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave20Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave20Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave20Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave20Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacySourceNativeWave20Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE20_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _dynamic_zone_partition(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[tuple[int, ...], ...], float]:
    frequency: Counter[int] = Counter(
        number for draw in history for number in draw.numbers
    )
    sorted_pairs = sorted(
        (
            (number, frequency.get(number, 0))
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    number_of_zones = 4
    zone_size = len(sorted_pairs) // number_of_zones
    remainder = len(sorted_pairs) % number_of_zones
    zones: list[tuple[int, ...]] = []
    start_index = 0
    for index in range(number_of_zones):
        current_size = zone_size + (1 if index < remainder else 0)
        zone = tuple(
            sorted(
                number
                for number, _count in sorted_pairs[
                    start_index : start_index + current_size
                ]
            )
        )
        if zone:
            zones.append(zone)
        start_index += current_size

    zone_means = [
        sum(frequency.get(number, 0) for number in zone) / len(zone)
        for zone in zones
    ]
    between_variance = _variance(zone_means)
    within_variances = [
        _variance(
            [
                float(frequency.get(number, 0))
                for number in zone
            ]
        )
        for zone in zones
        if len(zone) > 1
    ]
    average_within = (
        sum(within_variances) / len(within_variances)
        if within_variances
        else 1.0
    )
    quality = between_variance / (average_within + 1.0)
    return tuple(zones), min(1.0, quality / 10.0)


def _zone_balance_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    if (
        len(history) > 1
        and history[0].draw_number > history[-1].draw_number
    ):
        history = tuple(reversed(history))
    zones, _quality = _dynamic_zone_partition(history)
    zone_counts = [0] * len(zones)
    for draw in history[-min(len(history), 80) :]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    zone_counts[index] += 1
                    break

    recent_zone_counts = [0] * len(zones)
    for draw in history[-20:]:
        for number in draw.numbers:
            for index, zone in enumerate(zones):
                if min(zone) <= number <= max(zone):
                    recent_zone_counts[index] += 1
                    break

    total = sum(zone_counts) if sum(zone_counts) > 0 else 1
    recent_total = (
        sum(recent_zone_counts) if sum(recent_zone_counts) > 0 else 1
    )
    targets = [
        round(
            (
                zone_counts[index] / total * 0.7
                + recent_zone_counts[index] / recent_total * 0.3
            )
            * _PICK_COUNT
        )
        for index in range(len(zones))
    ]
    while sum(targets) < _PICK_COUNT:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > _PICK_COUNT:
        targets[targets.index(max(targets))] -= 1

    frequency: Counter[int] = Counter(
        number for draw in history for number in draw.numbers
    )
    predicted: list[int] = []
    for index, zone in enumerate(zones):
        zone_scores: list[tuple[int, float]] = []
        for number in zone:
            recent_frequency = sum(
                1
                for draw in history[-30:]
                for candidate in draw.numbers
                if candidate == number
            )
            zone_scores.append(
                (
                    number,
                    frequency.get(number, 0) * 0.6
                    + recent_frequency * 0.4,
                )
            )
        zone_scores.sort(key=lambda item: item[1], reverse=True)
        predicted.extend(
            number for number, _score in zone_scores[: targets[index]]
        )
    return _ticket(predicted)


def generate_frozen_zone_balance_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    """Expose the pinned UnifiedPredictionEngine zone-balance behavior."""

    return _zone_balance_ticket(history)


def _source_native_tickets(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, ...]:
    main_500 = _zone_balance_ticket(history[-500:])
    comparisons = tuple(
        _zone_balance_ticket(history[-window:])
        for window in _SOURCE_WINDOWS
    )
    return (main_500, *comparisons)


def generate_legacy_source_native_wave20_portfolio(
    request: LegacySourceNativeWave20Request,
) -> LegacySourceNativeWave20Result:
    """Reproduce all five frozen output ticket positions causally."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE20_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave20SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    tickets = _source_native_tickets(request.history)
    duplicate_count = len(tickets) - len(set(tickets))
    metadata = LegacySourceNativeWave20Metadata(
        protocol=SOURCE_NATIVE_WAVE20_PROTOCOL,
        legacy_method_id=request.legacy_method_id,
        source_sha256=(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD[
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
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE20_METHOD[
                request.legacy_method_id
            ]
        ),
        randomness_used=False,
        randomness_reproduction="NONE_DETERMINISTIC",
        history_draw_count=len(request.history),
        history_first_draw_number=request.history[0].draw_number,
        history_cutoff_draw_number=request.history[-1].draw_number,
        source_history_order=(
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE20_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_count=len(tickets),
        native_ticket_count_semantics=(
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE20_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_order=(
            "MAIN_RECOMMENDATION_500_FIRST_THEN_COMPARISON_"
            "WINDOWS_100_200_300_500"
        ),
        native_duplicate_ticket_count=duplicate_count,
        source_combination_members=(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE20_METHOD[
                request.legacy_method_id
            ]
        ),
        source_candidate_ticket_counts=(1, 1, 1, 1),
        source_candidate_k_values=(),
        frozen_support_artifacts=(
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE20_METHOD[
                request.legacy_method_id
            ]
        ),
        source_runtime_parameters=(
            "main_recommendation_window=500",
            "comparison_windows=100,200,300,500",
            "zone_count=4",
            "zone_analysis_window=80",
            "zone_recent_window=20",
            "number_recent_window=30",
        ),
        candidate_k=None,
        combination_count=None,
    )
    return LegacySourceNativeWave20Result(
        tickets=tickets,
        metadata=metadata,
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE20_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "SOURCE_NATIVE_WAVE20_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE20_METHODS",
    "ZONE_BALANCE_500_METHOD_ID",
    "LegacySourceNativeWave20Error",
    "LegacySourceNativeWave20Metadata",
    "LegacySourceNativeWave20Request",
    "LegacySourceNativeWave20Result",
    "LegacySourceNativeWave20SourceError",
    "generate_frozen_zone_balance_ticket",
    "generate_legacy_source_native_wave20_portfolio",
]
