"""Faithful ports of the twenty-ninth frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    frozen_deviation_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE29_PROTOCOL = "legacy_source_native_wave29/v1"
DEFAULT_SOURCE_NATIVE_WAVE29_USER_SEED = (
    "biglotto-full-universe-source-native-wave29-v1"
)
OPTIMIZED_BACKTEST_METHOD_ID = (
    "tools/backtest_biglotto_7bet_optimized.py"
)
ELITE_CLAIM_VERIFIER_METHOD_ID = "tools/verify_elite7_claim.py"
SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS = (
    OPTIMIZED_BACKTEST_METHOD_ID,
    ELITE_CLAIM_VERIFIER_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    OPTIMIZED_BACKTEST_METHOD_ID: (
        "2881417de6f86685cef917fe69a55466382391e09e9b512fe43676d80e3dea59"
    ),
    ELITE_CLAIM_VERIFIER_METHOD_ID: (
        "937afa8d61336b5f5bc7d96584cdfeaf6b8293a944b9861c46f26ee9bc8aa49c"
    ),
}
_COMMON_SHA256 = (
    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
)
_CORE_SUPPORT = (
    ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
    ("lottery_api/common.py", _COMMON_SHA256),
    ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
    ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: _CORE_SUPPORT
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: 1 for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: 7 for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: (
        "SIX_RECENT_WINDOW_UNIFIED_TICKETS_THEN_ONE_UNWEIGHTED_CONSENSUS_"
        "TICKET"
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: (
        "markov_predict:recent_window_50",
        "markov_predict:recent_window_100",
        "deviation_predict:recent_window_100",
        "deviation_predict:recent_window_200",
        "statistical_predict:recent_window_100",
        "statistical_predict:recent_window_110",
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: len(members)
    for method_id, members in (
        SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD.items()
    )
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: "DATABASE_GET_ALL_DRAWS_REVERSED_TO_ASCENDING_BEFORE_WINDOWS"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE29_METHOD: Final = {
    method_id: (
        "PYTHON_RANDOM_SEED_EQUALS_RECENT_WINDOW_HISTORY_LENGTH_FOR_EACH_"
        "STATISTICAL_PREDICT_CALL"
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
}
EngineCache = Mapping[tuple[int, str], tuple[int, ...]]


class LegacySourceNativeWave29Error(ValueError):
    """A request cannot satisfy the twenty-ninth source-native contract."""


class LegacySourceNativeWave29SourceError(LegacySourceNativeWave29Error):
    """The frozen source emitted no valid native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave29Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE29_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave29Metadata:
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
    source_history_order_detail: str
    source_history_first_draw_number: str
    source_history_last_draw_number: str
    native_ticket_count: int
    native_ticket_order: str
    native_duplicate_ticket_count: int
    candidate_k: int | None
    candidate_pool: tuple[int, ...]
    candidate_pool_size: int | None
    combination_count: int | None
    combination_members: tuple[str, ...]
    source_method_combination_count: int
    source_recent_windows: tuple[int, ...]
    statistical_call_count: int
    all_base_methods_failed_behavior: str
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave29Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave29Metadata


def _validate_request(request: LegacySourceNativeWave29Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS:
        raise LegacySourceNativeWave29Error(
            "unsupported frozen source-native wave-29 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave29Error(
            "invalid frozen source-native wave-29 request"
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
            raise LegacySourceNativeWave29Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave29Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE29_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def frozen_wave29_engine_output(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[int, ...]:
    """Return the exact frozen Unified result for chronological history."""

    if method_name == "deviation":
        return frozen_deviation_ticket(history)
    if method_name == "markov":
        return frozen_markov_ticket(history)[0]
    if method_name == "statistical":
        return frozen_statistical_ticket(history)[0]
    raise LegacySourceNativeWave29Error("unknown frozen Unified method")


def _engine_output(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> tuple[int, ...]:
    key = (len(history), method_name)
    if cache is not None and key in cache:
        return cache[key]
    return frozen_wave29_engine_output(method_name, history)


def _source_rows(
    history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> list[list[int]]:
    rows: list[list[int]] = []
    all_numbers: list[int] = []
    for method_name, window in (
        ("markov", 50),
        ("markov", 100),
        ("deviation", 100),
        ("deviation", 200),
        ("statistical", 100),
        ("statistical", 110),
    ):
        analysis_history = history[-window:]
        try:
            numbers = list(
                _engine_output(
                    method_name,
                    analysis_history,
                    cache,
                )[:6]
            )
        except Exception:
            continue
        rows.append(numbers)
        all_numbers.extend(numbers)
    if all_numbers:
        rows.append(
            [
                number
                for number, _count in Counter(all_numbers).most_common(6)
            ]
        )
    return rows


def _tickets_or_close(rows: list[list[int]]) -> tuple[Ticket, ...]:
    tickets: list[Ticket] = []
    for row in rows:
        ticket = tuple(sorted(row))
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(not 1 <= number <= 49 for number in ticket)
        ):
            raise LegacySourceNativeWave29SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    if not tickets:
        raise LegacySourceNativeWave29SourceError(
            "FROZEN_SOURCE_ALL_BASE_METHODS_FAILED"
        )
    return tuple(tickets)


def generate_legacy_source_native_wave29_portfolio(
    request: LegacySourceNativeWave29Request,
    *,
    engine_cache: EngineCache | None = None,
) -> LegacySourceNativeWave29Result:
    """Reproduce one frozen chronological rolling Elite-7 portfolio."""

    _validate_request(request)
    method_id = request.legacy_method_id
    tickets = _tickets_or_close(_source_rows(request.history, engine_cache))
    if len(tickets) != 7:
        raise LegacySourceNativeWave29SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave29Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave29Metadata(
            protocol=SOURCE_NATIVE_WAVE29_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_STATISTICAL_CALLS_RESEED_FROM_EACH_RECENT_WINDOW_"
                "HISTORY_LENGTH"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            source_history_first_draw_number=(
                request.history[0].draw_number
            ),
            source_history_last_draw_number=(
                request.history[-1].draw_number
            ),
            native_ticket_count=len(tickets),
            native_ticket_order=(
                "SIX_FROZEN_CONFIG_POSITIONS_THEN_CONSENSUS_POSITION"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            candidate_k=None,
            candidate_pool=(),
            candidate_pool_size=None,
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
            source_recent_windows=(50, 100, 100, 200, 100, 110),
            statistical_call_count=2,
            all_base_methods_failed_behavior=(
                "UNSEEDED_RANDOM_FALLBACK"
                if method_id == OPTIMIZED_BACKTEST_METHOD_ID
                else "NO_CONSENSUS_TICKET"
            ),
            tie_order_semantics=(
                "FROZEN_COUNTER_FIRST_INSERTION_MOST_COMMON_ORDER"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD[
                    method_id
                ]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE29_USER_SEED",
    "ELITE_CLAIM_VERIFIER_METHOD_ID",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "OPTIMIZED_BACKTEST_METHOD_ID",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "SOURCE_NATIVE_WAVE29_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS",
    "LegacySourceNativeWave29Error",
    "LegacySourceNativeWave29Metadata",
    "LegacySourceNativeWave29Request",
    "LegacySourceNativeWave29Result",
    "LegacySourceNativeWave29SourceError",
    "frozen_wave29_engine_output",
    "generate_legacy_source_native_wave29_portfolio",
]
