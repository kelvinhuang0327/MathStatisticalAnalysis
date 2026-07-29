"""Faithful port of the thirty-fourth frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    frozen_bayesian_ticket,
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_trend_ticket,
    frozen_zone_balance_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE34_PROTOCOL = "legacy_source_native_wave34/v1"
DEFAULT_SOURCE_NATIVE_WAVE34_USER_SEED = (
    "biglotto-full-universe-source-native-wave34-v1"
)
AUTO_OPTIMIZER_METHOD_ID = "tools/auto_optimizer_alpha.py"
SUPPORTED_SOURCE_NATIVE_WAVE34_METHODS = (AUTO_OPTIMIZER_METHOD_ID,)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: (
        "7eaa9572e3848fdf8fbcb66dbade25f653bf25a7fe7c4be95b6e9d2f8df1d61d"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: (
        ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
        (
            "lottery_api/common.py",
            "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
        ),
        ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
        ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
        (
            "lottery_api/models/backtest_framework.py",
            "853f77d49ad62c64b407b3c7d27d935673b28265ed01f51d4fc0e6acaf041636",
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: 1,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: 25,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: (
        "TWENTY_FIVE_POSITIONAL_UNIFIED_PREDICTOR_WINDOW_CONFIGURATIONS"
    ),
}
METHOD_NAMES: Final = (
    "zone_balance_predict",
    "bayesian_predict",
    "trend_predict",
    "frequency_predict",
    "deviation_predict",
)
WINDOWS: Final = (50, 100, 200, 300, 500)
VARIANT_CONFIGURATIONS: Final = tuple(
    (method_name, window)
    for method_name in METHOD_NAMES
    for window in WINDOWS
)
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: tuple(
        f"{method_name}:window_{window}"
        for method_name, window in VARIANT_CONFIGURATIONS
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: len(VARIANT_CONFIGURATIONS),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: "OLDEST_FIRST",
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE34_METHOD: Final = {
    AUTO_OPTIMIZER_METHOD_ID: (
        "DATABASE_NEWEST_FIRST_REVERSED_ONCE_THEN_ADAPTER_TRAILING_WINDOW"
    ),
}


class LegacySourceNativeWave34Error(ValueError):
    """A request cannot satisfy the thirty-fourth source-native contract."""


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave34Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE34_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave34Metadata:
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
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave34Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave34Metadata


def _validate_request(request: LegacySourceNativeWave34Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE34_METHODS:
        raise LegacySourceNativeWave34Error(
            "unsupported frozen source-native wave-34 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or len(request.history)
        < MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE34_METHOD[
            request.legacy_method_id
        ]
    ):
        raise LegacySourceNativeWave34Error(
            "invalid frozen source-native wave-34 request"
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
            raise LegacySourceNativeWave34Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave34Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE34_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _ticket(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    if method_name == "zone_balance_predict":
        return frozen_zone_balance_ticket(history)
    if method_name == "bayesian_predict":
        return frozen_bayesian_ticket(history)
    if method_name == "trend_predict":
        return frozen_trend_ticket(history)
    if method_name == "frequency_predict":
        return frozen_frequency_ticket(history)
    if method_name == "deviation_predict":
        return frozen_deviation_ticket(history)
    raise LegacySourceNativeWave34Error("unknown frozen Unified method")


def generate_legacy_source_native_wave34_portfolio(
    request: LegacySourceNativeWave34Request,
) -> LegacySourceNativeWave34Result:
    """Reproduce the frozen 5-by-5 auto-optimizer strategy space."""

    _validate_request(request)
    tickets: list[Ticket] = []
    history_counts: list[int] = []
    for method_name, window in VARIANT_CONFIGURATIONS:
        variant_history = request.history[-window:]
        tickets.append(_ticket(method_name, variant_history))
        history_counts.append(len(variant_history))
    native_tickets = tuple(tickets)
    if (
        len(native_tickets)
        != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD[
            request.legacy_method_id
        ]
    ):
        raise LegacySourceNativeWave34Error(
            "frozen source native ticket count changed"
        )
    material, digest, seed_integer = _seed(request)
    return LegacySourceNativeWave34Result(
        tickets=native_tickets,
        metadata=LegacySourceNativeWave34Metadata(
            protocol=SOURCE_NATIVE_WAVE34_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD[
                request.legacy_method_id
            ],
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=material,
            seed_digest=digest,
            seed_integer=seed_integer,
            random_protocol="NONE_DETERMINISTIC",
            randomness_used=False,
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE34_METHOD[
                    request.legacy_method_id
                ]
            ),
            candidate_k=None,
            candidate_pools=(),
            native_ticket_count=len(native_tickets),
            native_ticket_order=(
                "METHOD_MAJOR_ZONE_BAYESIAN_TREND_FREQUENCY_DEVIATION_"
                "THEN_WINDOW_50_100_200_300_500"
            ),
            native_duplicate_ticket_count=(
                len(native_tickets) - len(set(native_tickets))
            ),
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE34_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD[
                    request.legacy_method_id
                ]
            ),
            variant_history_draw_counts=tuple(history_counts),
            tie_order_semantics=(
                "FROZEN_PREDICTOR_SPECIFIC_STABLE_ORDER"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE34_METHOD[
                    request.legacy_method_id
                ]
            ),
        ),
    )


__all__ = [
    "AUTO_OPTIMIZER_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE34_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "METHOD_NAMES",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "SOURCE_NATIVE_WAVE34_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE34_METHODS",
    "VARIANT_CONFIGURATIONS",
    "WINDOWS",
    "LegacySourceNativeWave34Error",
    "LegacySourceNativeWave34Metadata",
    "LegacySourceNativeWave34Request",
    "LegacySourceNativeWave34Result",
    "generate_legacy_source_native_wave34_portfolio",
]
