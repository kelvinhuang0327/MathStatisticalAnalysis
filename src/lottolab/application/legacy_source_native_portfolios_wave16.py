"""Faithful port of the sixteenth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE16_PROTOCOL = "legacy_source_native_wave16/v1"
DEFAULT_SOURCE_NATIVE_WAVE16_USER_SEED = (
    "biglotto-full-universe-source-native-wave16-v1"
)
HOT_COOCCURRENCE_METHOD_ID = "tools/hot_cooccurrence_analyzer.py"
P270B_GEOMETRY_AUDIT_METHOD_ID = (
    "analysis/p270b_outcome_blind_portfolio_geometry_power_audit.py"
)
P282B_DEDUP_REPLAY_METHOD_ID = (
    "tools/p282b_big649_deduplicated_portfolio_replay.py"
)
SUPPORTED_SOURCE_NATIVE_WAVE16_METHODS = (
    HOT_COOCCURRENCE_METHOD_ID,
)
CLOSED_SOURCE_NATIVE_WAVE16_METHODS = (
    P270B_GEOMETRY_AUDIT_METHOD_ID,
    P282B_DEDUP_REPLAY_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: (
        "48121f27d7eedfcac0714bf9c3145926d7656ce1b16d98fa5110d5c2b714d28c"
    ),
    P270B_GEOMETRY_AUDIT_METHOD_ID: (
        "98e45eed87c81dc09264f828a80c25a4e94f09ababe274805829528edc671ec4"
    ),
    P282B_DEDUP_REPLAY_METHOD_ID: (
        "25db67c395d794e7211ea4162b938cba3927032438fb2d5c4a23fd651084d71d"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: (
        (
            "lottery_api/requirements.txt",
            "2046dd0aa9cc084352a2fb1a664e032fba23ac81f0b1e7d3f1d70ff9d1a1e130",
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: (
        "ONE_TOP20_HOT_POOL_WITH_NORMALIZED_100_DRAW_COOCCURRENCE_TICKET"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: "NONE_DETERMINISTIC",
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: 1,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: (
        "hot_window=50|co_window=100|cooccurrence_weight=0.3",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE16_METHOD: Final = {
    HOT_COOCCURRENCE_METHOD_ID: "OLDEST_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_HOT_WINDOW = 50
_COOCCURRENCE_WINDOW = 100
_HOT_POOL_LIMIT = 20
_COOCCURRENCE_WEIGHT = 0.3


class LegacySourceNativeWave16Error(ValueError):
    """A request cannot satisfy the sixteenth source-native contract."""


class LegacySourceNativeWave16SourceError(
    LegacySourceNativeWave16Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave16Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE16_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave16Metadata:
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
class LegacySourceNativeWave16Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave16Metadata


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
        raise LegacySourceNativeWave16SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacySourceNativeWave16Request) -> None:
    if request.legacy_method_id != HOT_COOCCURRENCE_METHOD_ID:
        raise LegacySourceNativeWave16Error(
            "legacy method is outside the sixteenth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave16Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave16Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave16Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave16Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave16Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE16_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _hot_cooccurrence_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, int]:
    recent_hot = history[-_HOT_WINDOW:]
    frequency: Counter[int] = Counter(
        number for draw in recent_hot for number in draw.numbers
    )
    hot_numbers = [
        number
        for number, _count in frequency.most_common(_HOT_POOL_LIMIT)
    ]
    if len(hot_numbers) <= _PICK_COUNT:
        return _ticket(hot_numbers), len(hot_numbers)

    recent_cooccurrence = history[-_COOCCURRENCE_WINDOW:]
    pair_counts: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in recent_cooccurrence:
        numbers = draw.numbers
        for index, left in enumerate(numbers):
            for right in numbers[index + 1 :]:
                pair_counts[left][right] += 1
                pair_counts[right][left] += 1

    denominator = len(recent_cooccurrence)
    scores: dict[int, float] = {}
    for index, number in enumerate(hot_numbers):
        rank_score = (len(hot_numbers) - index) / len(hot_numbers)
        cooccurrence_sum = sum(
            pair_counts[number][other] / denominator
            for other in hot_numbers
            if other != number
        )
        cooccurrence_score = cooccurrence_sum / (
            len(hot_numbers) - 1
        )
        scores[number] = (
            (1 - _COOCCURRENCE_WEIGHT) * rank_score
            + _COOCCURRENCE_WEIGHT * cooccurrence_score
        )
    selected = sorted(
        scores,
        key=lambda number: scores[number],
        reverse=True,
    )[:_PICK_COUNT]
    return _ticket(selected), len(hot_numbers)


def generate_legacy_source_native_wave16_portfolio(
    request: LegacySourceNativeWave16Request,
) -> LegacySourceNativeWave16Result:
    """Reproduce the deterministic hot/co-occurrence recommendation."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE16_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave16SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    ticket, candidate_k = _hot_cooccurrence_ticket(request.history)
    metadata = LegacySourceNativeWave16Metadata(
        protocol=SOURCE_NATIVE_WAVE16_PROTOCOL,
        legacy_method_id=request.legacy_method_id,
        source_sha256=(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
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
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE16_METHOD[
                request.legacy_method_id
            ]
        ),
        randomness_used=False,
        randomness_reproduction="NONE_DETERMINISTIC",
        history_draw_count=len(request.history),
        history_first_draw_number=request.history[0].draw_number,
        history_cutoff_draw_number=request.history[-1].draw_number,
        source_history_order=(
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE16_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_count=1,
        native_ticket_count_semantics=(
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE16_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_order="SINGLE_FROZEN_SOURCE_TICKET",
        native_duplicate_ticket_count=0,
        source_combination_members=(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE16_METHOD[
                request.legacy_method_id
            ]
        ),
        source_candidate_ticket_counts=(1,),
        source_candidate_k_values=(candidate_k,),
        frozen_support_artifacts=(
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE16_METHOD[
                request.legacy_method_id
            ]
        ),
        source_runtime_parameters=(
            "hot_window=50",
            "hot_pool_limit=20",
            "cooccurrence_window=100",
            "cooccurrence_normalization=window_draw_count",
            "cooccurrence_weight=0.3",
        ),
        candidate_k=None,
        combination_count=None,
    )
    return LegacySourceNativeWave16Result(
        tickets=(ticket,),
        metadata=metadata,
    )


__all__ = [
    "CLOSED_SOURCE_NATIVE_WAVE16_METHODS",
    "DEFAULT_SOURCE_NATIVE_WAVE16_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "HOT_COOCCURRENCE_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "P270B_GEOMETRY_AUDIT_METHOD_ID",
    "P282B_DEDUP_REPLAY_METHOD_ID",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "SOURCE_NATIVE_WAVE16_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE16_METHODS",
    "LegacySourceNativeWave16Error",
    "LegacySourceNativeWave16Metadata",
    "LegacySourceNativeWave16Request",
    "LegacySourceNativeWave16Result",
    "LegacySourceNativeWave16SourceError",
    "generate_legacy_source_native_wave16_portfolio",
]
