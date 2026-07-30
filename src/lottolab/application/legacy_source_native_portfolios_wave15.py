"""Faithful port of the fifteenth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE15_PROTOCOL = "legacy_source_native_wave15/v1"
DEFAULT_SOURCE_NATIVE_WAVE15_USER_SEED = (
    "biglotto-full-universe-source-native-wave15-v1"
)
ATTENTION_REPLAY_METHOD_ID = (
    "ai_lab/scripts/attention_replay_predictor.py"
)
SUPPORTED_SOURCE_NATIVE_WAVE15_METHODS = (
    ATTENTION_REPLAY_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: (
        "a811e2eb821506396cad2c739c90f05184792bd57b09bf6808e996afbace94fc"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: (
        (
            "ai_lab/ai_models/v3_deep_resonance.pth",
            "ef21497fe396cff4d96dc7a123987f9cb188725900162b435be91cfd7d23712d",
        ),
        (
            "ai_lab/data/real_biglotto.json",
            "434f31e944e835231813bfed7af8e380f1f286523c29737166d5d7d721fd75a8",
        ),
        (
            "ai_lab/scripts/train_v3.py",
            "7ba91423549ab8b410d74da6fe8aecf7d877fe69a2aa088c9e313ff80069237f",
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: (
        "ONE_FIXED_15_DRAW_RECENCY_WEIGHTED_FREQUENCY_TICKET"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: "NONE_DETERMINISTIC",
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: None,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: (),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE15_METHOD: Final = {
    ATTENTION_REPLAY_METHOD_ID: "OLDEST_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_ATTENTION_WEIGHTS = tuple(
    (1.0 + index * 0.1) / 25.5 for index in range(15)
)


class LegacySourceNativeWave15Error(ValueError):
    """A request cannot satisfy the fifteenth source-native contract."""


class LegacySourceNativeWave15SourceError(
    LegacySourceNativeWave15Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave15Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE15_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave15Metadata:
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
    source_ignored_model_output_semantics: str
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave15Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave15Metadata


def _validate_request(request: LegacySourceNativeWave15Request) -> None:
    if request.legacy_method_id != ATTENTION_REPLAY_METHOD_ID:
        raise LegacySourceNativeWave15Error(
            "legacy method is outside the fifteenth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave15Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave15Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave15Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave15Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave15Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE15_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD[
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
        raise LegacySourceNativeWave15SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _attention_replay_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    recent_history = history[-15:]
    for index, draw in enumerate(recent_history):
        weight = _ATTENTION_WEIGHTS[index]
        for number in draw.numbers:
            weighted_frequency[number] += weight
    ranked = sorted(
        weighted_frequency.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return _ticket([number for number, _weight in ranked[:6]])


def generate_legacy_source_native_wave15_portfolio(
    request: LegacySourceNativeWave15Request,
) -> LegacySourceNativeWave15Result:
    """Reproduce the output-identical attention replay ticket causally."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE15_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave15SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    tickets = (_attention_replay_ticket(request.history),)
    metadata = LegacySourceNativeWave15Metadata(
        protocol=SOURCE_NATIVE_WAVE15_PROTOCOL,
        legacy_method_id=request.legacy_method_id,
        source_sha256=(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD[
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
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE15_METHOD[
                request.legacy_method_id
            ]
        ),
        randomness_used=False,
        randomness_reproduction="NONE_DETERMINISTIC",
        history_draw_count=len(request.history),
        history_first_draw_number=request.history[0].draw_number,
        history_cutoff_draw_number=request.history[-1].draw_number,
        source_history_order=(
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE15_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_count=1,
        native_ticket_count_semantics=(
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE15_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_order="SINGLE_FROZEN_SOURCE_TICKET",
        native_duplicate_ticket_count=0,
        source_combination_members=(),
        source_candidate_ticket_counts=(1,),
        source_candidate_k_values=(),
        frozen_support_artifacts=(
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE15_METHOD[
                request.legacy_method_id
            ]
        ),
        source_runtime_parameters=(
            "context_draw_count=15",
            "raw_weight[index]=1.0+index*0.1",
            "normalized_weight_sum=25.5",
        ),
        source_ignored_model_output_semantics=(
            "FROZEN_FORWARD_PASS_LOGITS_ARE_NOT_USED; SOURCE_RETURNS_"
            "FIXED_UNIFORM_PLUS_RECENCY_WEIGHTS"
        ),
        candidate_k=None,
        combination_count=None,
    )
    return LegacySourceNativeWave15Result(
        tickets=tickets,
        metadata=metadata,
    )


__all__ = [
    "ATTENTION_REPLAY_METHOD_ID",
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE15_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "SOURCE_NATIVE_WAVE15_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE15_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE15_METHODS",
    "LegacySourceNativeWave15Error",
    "LegacySourceNativeWave15Metadata",
    "LegacySourceNativeWave15Request",
    "LegacySourceNativeWave15Result",
    "LegacySourceNativeWave15SourceError",
    "generate_legacy_source_native_wave15_portfolio",
]
