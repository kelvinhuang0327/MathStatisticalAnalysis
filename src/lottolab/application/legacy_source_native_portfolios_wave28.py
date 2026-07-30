"""Faithful ports of the twenty-eighth frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Final, cast

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
from lottolab.application.legacy_source_native_portfolios_wave24 import (
    frozen_tools_kill_numbers,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE28_PROTOCOL = "legacy_source_native_wave28/v1"
DEFAULT_SOURCE_NATIVE_WAVE28_USER_SEED = (
    "biglotto-full-universe-source-native-wave28-v1"
)
TWO_BET_METHOD_ID = "tools/predict_biglotto_115000007_2bets.py"
SEVEN_BET_METHOD_ID = "tools/predict_biglotto_7bets.py"
ELITE_SEVEN_METHOD_ID = "tools/predict_biglotto_elite7.py"
SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS = (
    TWO_BET_METHOD_ID,
    SEVEN_BET_METHOD_ID,
    ELITE_SEVEN_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    TWO_BET_METHOD_ID: (
        "3dc7842c05116f4322ec88f27cc953d1912625f6816fcdbb170128aee8c74839"
    ),
    SEVEN_BET_METHOD_ID: (
        "778d3a46678e777bb918913c7fff3a0704c42d957f1d621d1ef7da711daac278"
    ),
    ELITE_SEVEN_METHOD_ID: (
        "eb46a985644626a796640ef0fd9913c340f4c9780a694824029f5083ed1b833a"
    ),
}
_COMMON_SHA256 = (
    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
)
_NEGATIVE_SELECTOR_SHA256 = (
    "80e79f80f9f5978ee2d7e71bb65e7b63bf101192a402ab8a9d0644796d4e3ff0"
)
_CORE_SUPPORT = (
    ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
    ("lottery_api/common.py", _COMMON_SHA256),
    ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
    ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
)
_KILL_SUPPORT = (("tools/negative_selector.py", _NEGATIVE_SELECTOR_SHA256),)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    TWO_BET_METHOD_ID: _CORE_SUPPORT + _KILL_SUPPORT,
    SEVEN_BET_METHOD_ID: _CORE_SUPPORT + _KILL_SUPPORT,
    ELITE_SEVEN_METHOD_ID: _CORE_SUPPORT,
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    method_id: 1 for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    TWO_BET_METHOD_ID: (
        "TWO_POSITIONAL_DISJOINT_SLICES_0_6_AND_6_12_FROM_WEIGHTED_TOP20"
    ),
    SEVEN_BET_METHOD_ID: (
        "UP_TO_SEVEN_POSITIONAL_OVERLAPPING_SLICES_FROM_WEIGHTED_TOP30"
    ),
    ELITE_SEVEN_METHOD_ID: (
        "SIX_POSITIONAL_WINDOWED_UNIFIED_TICKETS_THEN_ONE_CONSENSUS_TICKET"
    ),
}
DECLARED_NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    TWO_BET_METHOD_ID: 2,
    SEVEN_BET_METHOD_ID: None,
    ELITE_SEVEN_METHOD_ID: 7,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    TWO_BET_METHOD_ID: (
        "deviation_predict:weight_2.5",
        "markov_predict:weight_2.0",
        "statistical_predict:weight_1.5",
        "zone_balance_predict:weight_1.5",
        "frequency_predict:weight_1.0",
    ),
    SEVEN_BET_METHOD_ID: (
        "deviation_predict:weight_2.5",
        "markov_predict:weight_2.0",
        "statistical_predict:weight_1.5",
        "zone_balance_predict:weight_1.5",
        "frequency_predict:weight_1.0",
    ),
    ELITE_SEVEN_METHOD_ID: (
        "markov_predict:source_tail_window_50",
        "markov_predict:source_tail_window_100",
        "deviation_predict:source_tail_window_100",
        "deviation_predict:source_tail_window_200",
        "statistical_predict:source_tail_window_100",
        "statistical_predict:source_tail_window_110",
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    method_id: len(members)
    for method_id, members in (
        SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE28_METHOD.items()
    )
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    method_id: "RECENT_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    method_id: "DATABASE_GET_ALL_DRAWS_ORDER_BY_INTEGER_DRAW_DESC_NEWEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE28_METHOD: Final = {
    method_id: (
        "PYTHON_RANDOM_SEED_EQUALS_SOURCE_SLICE_HISTORY_LENGTH_FOR_EACH_"
        "STATISTICAL_PREDICT_CALL"
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS
}
EngineCache = Mapping[tuple[int, str], tuple[int, ...]]


class LegacySourceNativeWave28Error(ValueError):
    """A request cannot satisfy the twenty-eighth source-native contract."""


class LegacySourceNativeWave28SourceError(LegacySourceNativeWave28Error):
    """The frozen source emitted no valid native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave28Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE28_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave28Metadata:
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
    kill_numbers: tuple[int, ...]
    statistical_call_count: int
    source_tail_windows: tuple[int, ...]
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave28Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave28Metadata


def _validate_request(request: LegacySourceNativeWave28Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS:
        raise LegacySourceNativeWave28Error(
            "unsupported frozen source-native wave-28 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave28Error(
            "invalid frozen source-native wave-28 request"
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
            raise LegacySourceNativeWave28Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave28Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE28_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def frozen_wave28_engine_output(
    method_name: str,
    source_history: tuple[LegacyHistoryDraw, ...],
) -> tuple[int, ...]:
    """Return the exact frozen Unified result for source-order history."""

    if method_name == "deviation":
        return frozen_deviation_ticket(source_history)
    if method_name == "markov":
        return frozen_markov_ticket(source_history)[0]
    if method_name == "statistical":
        return frozen_statistical_ticket(source_history)[0]
    if method_name == "zone_balance":
        return frozen_zone_balance_ticket(source_history)
    if method_name == "frequency":
        return frozen_frequency_ticket(source_history)
    raise LegacySourceNativeWave28Error("unknown frozen Unified method")


def _engine_output(
    method_name: str,
    source_history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> tuple[int, ...]:
    key = (len(source_history), method_name)
    if cache is not None and key in cache:
        return cache[key]
    return frozen_wave28_engine_output(method_name, source_history)


def _weighted_pool(
    source_history: tuple[LegacyHistoryDraw, ...],
    *,
    kill_numbers: tuple[int, ...],
    limit: int,
    cache: EngineCache | None,
) -> list[int]:
    candidates: Counter[int] = Counter()
    for method_name, weight in (
        ("deviation", 2.5),
        ("markov", 2.0),
        ("statistical", 1.5),
        ("zone_balance", 1.5),
        ("frequency", 1.0),
    ):
        try:
            for number in _engine_output(
                method_name,
                source_history,
                cache,
            ):
                candidates[number] += cast(int, weight)
        except Exception:
            continue
    for number in kill_numbers:
        candidates[number] = -9999
    return [number for number, _score in candidates.most_common(limit)]


def _weighted_rows(
    method_id: str,
    candidate_pool: list[int],
) -> list[list[int]]:
    if method_id == TWO_BET_METHOD_ID:
        rows: list[list[int]] = []
        for start, end in ((0, 6), (6, 12)):
            if len(candidate_pool) >= end:
                rows.append(sorted(candidate_pool[start:end]))
            else:
                rows.append(sorted(candidate_pool[:6]))
        return rows
    rows = []
    for start, end in (
        (0, 6),
        (3, 9),
        (6, 12),
        (9, 15),
        (12, 18),
        (15, 21),
        (20, 26),
    ):
        if end <= len(candidate_pool):
            rows.append(sorted(candidate_pool[start:end]))
        elif len(candidate_pool) - start >= 6:
            rows.append(sorted(candidate_pool[start : start + 6]))
    return rows


def _elite_rows(
    source_history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> list[list[int]]:
    rows: list[list[int]] = []
    for method_name, window in (
        ("markov", 50),
        ("markov", 100),
        ("deviation", 100),
        ("deviation", 200),
        ("statistical", 100),
        ("statistical", 110),
    ):
        analysis_history = source_history[-window:]
        try:
            rows.append(
                sorted(
                    _engine_output(
                        method_name,
                        analysis_history,
                        cache,
                    )[:6]
                )
            )
        except Exception:
            continue
    if rows:
        consensus = Counter(
            number for row in rows for number in row
        ).most_common(6)
        rows.append(sorted(number for number, _count in consensus))
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
            raise LegacySourceNativeWave28SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    if not tickets:
        raise LegacySourceNativeWave28SourceError(
            "FROZEN_SOURCE_EMITTED_NO_NATIVE_TICKETS"
        )
    return tuple(tickets)


def generate_legacy_source_native_wave28_portfolio(
    request: LegacySourceNativeWave28Request,
    *,
    engine_cache: EngineCache | None = None,
) -> LegacySourceNativeWave28Result:
    """Reproduce one frozen newest-first weighted or Elite-7 portfolio."""

    _validate_request(request)
    method_id = request.legacy_method_id
    source_history = tuple(reversed(request.history))
    candidate_pool: list[int] = []
    kill_numbers: tuple[int, ...] = ()
    source_tail_windows: tuple[int, ...] = ()
    statistical_calls = 1
    if method_id in (TWO_BET_METHOD_ID, SEVEN_BET_METHOD_ID):
        kill_numbers = frozen_tools_kill_numbers(
            source_history,
            count=8 if method_id == TWO_BET_METHOD_ID else 10,
        )
        candidate_pool = _weighted_pool(
            source_history,
            kill_numbers=kill_numbers,
            limit=20 if method_id == TWO_BET_METHOD_ID else 30,
            cache=engine_cache,
        )
        rows = _weighted_rows(method_id, candidate_pool)
    else:
        rows = _elite_rows(source_history, engine_cache)
        source_tail_windows = (50, 100, 100, 200, 100, 110)
        statistical_calls = 2
    tickets = _tickets_or_close(rows)
    if method_id == TWO_BET_METHOD_ID and len(tickets) != 2:
        raise LegacySourceNativeWave28SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    if method_id == ELITE_SEVEN_METHOD_ID and len(tickets) != 7:
        raise LegacySourceNativeWave28SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave28Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave28Metadata(
            protocol=SOURCE_NATIVE_WAVE28_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_STATISTICAL_CALLS_RESEED_FROM_EACH_SOURCE_SLICE_"
                "HISTORY_LENGTH"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            source_history_first_draw_number=(
                source_history[0].draw_number
            ),
            source_history_last_draw_number=(
                source_history[-1].draw_number
            ),
            native_ticket_count=len(tickets),
            native_ticket_order="FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER",
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            candidate_k=None,
            candidate_pool=tuple(candidate_pool),
            candidate_pool_size=(
                len(candidate_pool) if candidate_pool else None
            ),
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
            kill_numbers=kill_numbers,
            statistical_call_count=statistical_calls,
            source_tail_windows=source_tail_windows,
            tie_order_semantics=(
                "FROZEN_COUNTER_FIRST_INSERTION_AND_PYTHON_STABLE_SORT_ORDER"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE28_METHOD[
                    method_id
                ]
            ),
        ),
    )


__all__ = [
    "DECLARED_NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE28_USER_SEED",
    "ELITE_SEVEN_METHOD_ID",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "SEVEN_BET_METHOD_ID",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "SOURCE_NATIVE_WAVE28_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS",
    "TWO_BET_METHOD_ID",
    "LegacySourceNativeWave28Error",
    "LegacySourceNativeWave28Metadata",
    "LegacySourceNativeWave28Request",
    "LegacySourceNativeWave28Result",
    "LegacySourceNativeWave28SourceError",
    "frozen_wave28_engine_output",
    "generate_legacy_source_native_wave28_portfolio",
]
