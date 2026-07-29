"""Faithful port of the twenty-second frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE22_PROTOCOL = "legacy_source_native_wave22/v1"
DEFAULT_SOURCE_NATIVE_WAVE22_USER_SEED = (
    "biglotto-full-universe-source-native-wave22-v1"
)
SMART_2BET_METHOD_ID = "tools/predict_big_lotto_smart_2bet.py"
SUPPORTED_SOURCE_NATIVE_WAVE22_METHODS = (SMART_2BET_METHOD_ID,)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: (
        "7acdaab1bd0afea2dd270e225335c25ccdb26594ce788902f2752b5e41801ede"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: (
        (
            "lottery_api/models/unified_predictor.py",
            "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004",
        ),
        (
            "lottery_api/common.py",
            "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
        ),
        (
            "lottery_api/config_loader.py",
            "2becda7a755720ea7ba6ef6f7e9637a99d449d68b81536d12cf2320ec05e28a2",
        ),
        (
            "config/prediction_config.yaml",
            "a269c35fd571720534201592bccc7f1e407fb1e7ad5f6e7451b885b92c035002",
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: (
        "TWO_POSITIONAL_SMART_TICKETS_TRUE_FREQUENCY_50_"
        "CONSERVATIVE_THEN_FULL_HISTORY_DEVIATION_AGGRESSIVE"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: "NONE_DETERMINISTIC",
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: 2,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: (
        "true_frequency_predict:frequency_window=50:pick_count=6",
        "deviation_predict:full_history:pick_count=6",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE22_METHOD: Final = {
    SMART_2BET_METHOD_ID: "RECENT_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_DEVIATION_WEIGHTS = {
    "frequency": 0.30,
    "zone": 0.25,
    "odd_even": 0.20,
    "high_low": 0.15,
    "gap": 0.10,
}


class LegacySourceNativeWave22Error(ValueError):
    """A request cannot satisfy the twenty-second source-native contract."""


class LegacySourceNativeWave22SourceError(
    LegacySourceNativeWave22Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave22Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE22_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave22Metadata:
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
class LegacySourceNativeWave22Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave22Metadata


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
        raise LegacySourceNativeWave22SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacySourceNativeWave22Request) -> None:
    if request.legacy_method_id != SMART_2BET_METHOD_ID:
        raise LegacySourceNativeWave22Error(
            "legacy method is outside the twenty-second source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave22Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave22Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave22Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave22Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacySourceNativeWave22Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE22_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _true_frequency_ticket(
    recent_first: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, int]:
    counts: Counter[int] = Counter(
        number for draw in recent_first[:50] for number in draw.numbers
    )
    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return _ticket([number for number, _count in ranked[:6]]), len(ranked)


def _deviation_ticket(
    recent_first: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    total_numbers = _MAX_NUMBER - _MIN_NUMBER + 1
    expected_frequency = (
        len(recent_first) * _PICK_COUNT
    ) / total_numbers
    all_numbers = [
        number
        for draw in recent_first
        for number in draw.numbers
    ]
    frequency = Counter(all_numbers)
    sum_squared_difference = sum(
        (frequency.get(number, 0) - expected_frequency) ** 2
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    )
    standard_deviation = math.sqrt(
        sum_squared_difference / total_numbers
    )
    raw_frequency_scores = [0.0] * (_MAX_NUMBER + 1)
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        z_score = (
            (frequency.get(number, 0) - expected_frequency)
            / standard_deviation
            if standard_deviation > 0
            else 0.0
        )
        if z_score < -1.5:
            raw_frequency_scores[number] += 0.8 + abs(z_score) * 0.1
        elif z_score > 2.0:
            raw_frequency_scores[number] += 0.2
        elif 0.5 < z_score < 1.5:
            raw_frequency_scores[number] += 0.6 + z_score * 0.1
        else:
            raw_frequency_scores[number] += 0.4
    maximum_frequency_score = max(raw_frequency_scores)
    scores = [
        score
        / (maximum_frequency_score + 1e-10)
        * _DEVIATION_WEIGHTS["frequency"]
        for score in raw_frequency_scores
    ]

    zone_size = total_numbers // 5
    zones: dict[int, list[int]] = {}
    for zone_id in range(1, 6):
        start = _MIN_NUMBER + (zone_id - 1) * zone_size
        end = (
            _MAX_NUMBER
            if zone_id == 5
            else _MIN_NUMBER + zone_id * zone_size - 1
        )
        zones[zone_id] = list(range(start, end + 1))
    zone_counts = {zone_id: 0 for zone_id in zones}
    for number in all_numbers:
        for zone_id, zone_numbers in zones.items():
            if number in zone_numbers:
                zone_counts[zone_id] += 1
    for zone_id, zone_numbers in zones.items():
        expected = (
            len(recent_first)
            * _PICK_COUNT
            * len(zone_numbers)
            / total_numbers
        )
        zone_score = max(0.0, expected - zone_counts[zone_id])
        for number in zone_numbers:
            scores[number] += (
                zone_score
                * _DEVIATION_WEIGHTS["zone"]
                / len(zone_numbers)
            )

    odd_count = sum(1 for number in all_numbers if number % 2 == 1)
    expected_odd = len(all_numbers) / 2
    odd_deviation = expected_odd - odd_count
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number % 2 == 1 and odd_deviation > 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["odd_even"]
                * odd_deviation
                / expected_odd
            )
        elif number % 2 == 0 and odd_deviation < 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["odd_even"]
                * abs(odd_deviation)
                / expected_odd
            )

    midpoint = (_MIN_NUMBER + _MAX_NUMBER) // 2
    small_count = sum(
        1 for number in all_numbers if number <= midpoint
    )
    expected_small = len(all_numbers) / 2
    small_deviation = expected_small - small_count
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number <= midpoint and small_deviation > 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["high_low"]
                * small_deviation
                / expected_small
            )
        elif number > midpoint and small_deviation < 0:
            scores[number] += (
                _DEVIATION_WEIGHTS["high_low"]
                * abs(small_deviation)
                / expected_small
            )

    gaps: dict[int, int] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        for index, draw in enumerate(recent_first):
            if number in draw.numbers:
                gaps[number] = index
                break
        if number not in gaps:
            gaps[number] = len(recent_first)
    maximum_gap = max(gaps.values()) if gaps else 1
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        gap_score = gaps.get(number, 0) / maximum_gap
        scores[number] += gap_score * _DEVIATION_WEIGHTS["gap"]

    ranked = sorted(
        (
            (number, scores[number])
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return _ticket([number for number, _score in ranked[:6]])


def generate_legacy_source_native_wave22_portfolio(
    request: LegacySourceNativeWave22Request,
) -> LegacySourceNativeWave22Result:
    """Reproduce both frozen smart two-bet ticket positions causally."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE22_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave22SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    recent_first = tuple(reversed(request.history))
    true_frequency, frequency_candidate_count = (
        _true_frequency_ticket(recent_first)
    )
    deviation = _deviation_ticket(recent_first)
    tickets = (true_frequency, deviation)
    metadata = LegacySourceNativeWave22Metadata(
        protocol=SOURCE_NATIVE_WAVE22_PROTOCOL,
        legacy_method_id=request.legacy_method_id,
        source_sha256=(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD[
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
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE22_METHOD[
                request.legacy_method_id
            ]
        ),
        randomness_used=False,
        randomness_reproduction="NONE_DETERMINISTIC",
        history_draw_count=len(request.history),
        history_first_draw_number=request.history[-1].draw_number,
        history_cutoff_draw_number=request.history[-1].draw_number,
        source_history_order=(
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE22_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_count=len(tickets),
        native_ticket_count_semantics=(
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_order=(
            "CONSERVATIVE_TRUE_FREQUENCY_50_FIRST_THEN_AGGRESSIVE_"
            "FULL_HISTORY_DEVIATION"
        ),
        native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
        source_combination_members=(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                request.legacy_method_id
            ]
        ),
        source_candidate_ticket_counts=(
            frequency_candidate_count,
            _MAX_NUMBER,
        ),
        source_candidate_k_values=(),
        frozen_support_artifacts=(
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                request.legacy_method_id
            ]
        ),
        source_runtime_parameters=(
            "true_frequency_window=50",
            "pick_count=6",
            "deviation_history_window=FULL",
            "deviation_weights=frequency:0.30,zone:0.25,"
            "odd_even:0.20,high_low:0.15,gap:0.10",
        ),
        candidate_k=None,
        combination_count=None,
    )
    return LegacySourceNativeWave22Result(
        tickets=tickets,
        metadata=metadata,
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE22_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "SMART_2BET_METHOD_ID",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "SOURCE_NATIVE_WAVE22_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE22_METHODS",
    "LegacySourceNativeWave22Error",
    "LegacySourceNativeWave22Metadata",
    "LegacySourceNativeWave22Request",
    "LegacySourceNativeWave22Result",
    "LegacySourceNativeWave22SourceError",
    "generate_legacy_source_native_wave22_portfolio",
]
