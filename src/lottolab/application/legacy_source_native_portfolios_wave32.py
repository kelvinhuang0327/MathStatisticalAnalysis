"""Faithful port of the thirty-second frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
    frozen_zone_balance_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE32_PROTOCOL = "legacy_source_native_wave32/v1"
DEFAULT_SOURCE_NATIVE_WAVE32_USER_SEED = (
    "biglotto-full-universe-source-native-wave32-v1"
)
VARIANT_HISTORY_METHOD_ID = "tools/research_variant_history.py"
SUPPORTED_SOURCE_NATIVE_WAVE32_METHODS = (VARIANT_HISTORY_METHOD_ID,)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: (
        "149648f9fffcd0e6e9b5f89c2ab58ce5c1171ad75a5b7ed9f336469e710e8d68"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: (
        ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
        (
            "lottery_api/common.py",
            "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
        ),
        ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
        ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: 20,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: 11,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: (
        "ELEVEN_POSITIONAL_UNIFIED_PREDICTOR_WINDOW_VARIANTS"
    ),
}
VARIANT_CONFIGURATIONS: Final = (
    ("deviation_predict", 50),
    ("deviation_predict", 100),
    ("deviation_predict", 200),
    ("statistical_predict", 50),
    ("statistical_predict", 100),
    ("statistical_predict", 200),
    ("markov_predict", 50),
    ("markov_predict", 100),
    ("markov_predict", 200),
    ("frequency_predict", 50),
    ("zone_balance_predict", 100),
)
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: tuple(
        f"{method_name}:window_{window}"
        for method_name, window in VARIANT_CONFIGURATIONS
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: len(VARIANT_CONFIGURATIONS),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: "OLDEST_FIRST",
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD: Final = {
    VARIANT_HISTORY_METHOD_ID: (
        "DATABASE_NEWEST_FIRST_REVERSED_ONCE_THEN_PER_TARGET_TRAILING_"
        "WINDOW_SLICE"
    ),
}


class LegacySourceNativeWave32Error(ValueError):
    """A request cannot satisfy the thirty-second source-native contract."""


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave32Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE32_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave32Metadata:
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
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    source_history_order_detail: str
    candidate_k: int | None
    candidate_pools: tuple[tuple[int, ...], ...]
    native_ticket_count: int
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: int | None
    combination_members: tuple[str, ...]
    source_method_combination_count: int
    variant_history_draw_counts: tuple[int, ...]
    statistical_candidate_counts: tuple[int | None, ...]
    statistical_fallback_positions: tuple[int, ...]
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave32Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave32Metadata


def _validate_request(request: LegacySourceNativeWave32Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE32_METHODS:
        raise LegacySourceNativeWave32Error(
            "unsupported frozen source-native wave-32 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or len(request.history)
        < MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD[
            request.legacy_method_id
        ]
    ):
        raise LegacySourceNativeWave32Error(
            "invalid frozen source-native wave-32 request"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
            or len(draw.numbers) != 6
            or len(set(draw.numbers)) != 6
            or any(
                type(number) is not int or not 1 <= number <= 49
                for number in draw.numbers
            )
        ):
            raise LegacySourceNativeWave32Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave32Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE32_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _variant_ticket(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, int | None, bool]:
    if method_name == "deviation_predict":
        return frozen_deviation_ticket(history), None, False
    if method_name == "statistical_predict":
        try:
            ticket, candidate_count = frozen_statistical_ticket(history)
            return ticket, candidate_count, False
        except ValueError as exc:
            if str(exc) != "FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED":
                raise
            return frozen_frequency_ticket(history), 0, True
    if method_name == "markov_predict":
        return frozen_markov_ticket(history)[0], None, False
    if method_name == "frequency_predict":
        return frozen_frequency_ticket(history), None, False
    if method_name == "zone_balance_predict":
        return frozen_zone_balance_ticket(history), None, False
    raise LegacySourceNativeWave32Error("unknown frozen Unified method")


def generate_legacy_source_native_wave32_portfolio(
    request: LegacySourceNativeWave32Request,
) -> LegacySourceNativeWave32Result:
    """Reproduce the frozen ordered eleven-variant research portfolio."""

    _validate_request(request)
    tickets: list[Ticket] = []
    history_counts: list[int] = []
    statistical_counts: list[int | None] = []
    fallback_positions: list[int] = []
    for position, (method_name, window) in enumerate(
        VARIANT_CONFIGURATIONS,
        start=1,
    ):
        variant_history = request.history[-window:]
        ticket, candidate_count, used_fallback = _variant_ticket(
            method_name,
            variant_history,
        )
        tickets.append(ticket)
        history_counts.append(len(variant_history))
        statistical_counts.append(candidate_count)
        if used_fallback:
            fallback_positions.append(position)
    native_tickets = tuple(tickets)
    if (
        len(native_tickets)
        != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD[
            request.legacy_method_id
        ]
    ):
        raise LegacySourceNativeWave32Error(
            "frozen source native ticket count changed"
        )
    material, digest, seed_integer = _seed(request)
    return LegacySourceNativeWave32Result(
        tickets=native_tickets,
        metadata=LegacySourceNativeWave32Metadata(
            protocol=SOURCE_NATIVE_WAVE32_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD[
                request.legacy_method_id
            ],
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=material,
            seed_digest=digest,
            seed_integer=seed_integer,
            random_protocol=(
                "PYTHON_RANDOM_MODULE_SEEDED_WITH_VARIANT_HISTORY_LENGTH_"
                "FOR_STATISTICAL_POSITIONS_4_5_6"
            ),
            randomness_used=True,
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD[
                    request.legacy_method_id
                ]
            ),
            candidate_k=None,
            candidate_pools=(),
            native_ticket_count=len(native_tickets),
            native_ticket_order=(
                "FROZEN_VARIANTS_LIST_POSITION_1_THROUGH_11"
            ),
            native_duplicate_ticket_count=(
                len(native_tickets) - len(set(native_tickets))
            ),
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE32_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD[
                    request.legacy_method_id
                ]
            ),
            variant_history_draw_counts=tuple(history_counts),
            statistical_candidate_counts=tuple(statistical_counts),
            statistical_fallback_positions=tuple(fallback_positions),
            tie_order_semantics=(
                "FROZEN_PREDICTOR_SPECIFIC_STABLE_ORDER_AND_PYTHON_"
                "COUNTER_INSERTION_ORDER"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD[
                    request.legacy_method_id
                ]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE32_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "SOURCE_NATIVE_WAVE32_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE32_METHODS",
    "VARIANT_CONFIGURATIONS",
    "VARIANT_HISTORY_METHOD_ID",
    "LegacySourceNativeWave32Error",
    "LegacySourceNativeWave32Metadata",
    "LegacySourceNativeWave32Request",
    "LegacySourceNativeWave32Result",
    "generate_legacy_source_native_wave32_portfolio",
]
