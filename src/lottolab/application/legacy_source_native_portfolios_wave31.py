"""Faithful ports of the thirty-first frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_markov_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE31_PROTOCOL = "legacy_source_native_wave31/v1"
DEFAULT_SOURCE_NATIVE_WAVE31_USER_SEED = (
    "biglotto-full-universe-source-native-wave31-v1"
)
RADICAL_PREDICT_METHOD_ID = "tools/predict_biglotto_radical.py"
RADICAL_BACKTEST_METHOD_ID = "tools/backtest_radical_strategy.py"
SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS = (
    RADICAL_PREDICT_METHOD_ID,
    RADICAL_BACKTEST_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    RADICAL_PREDICT_METHOD_ID: (
        "1f1c6e060b19303fa4302d87f223767a415cb9eb44fae875722db25821f53eaf"
    ),
    RADICAL_BACKTEST_METHOD_ID: (
        "e54cc0812bc6fff14a259282a37821810d264c023c4fb87517305b511db08fd9"
    ),
}
_COMMON_SHA256 = (
    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
)
_SUPPORT = (
    ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
    ("lottery_api/common.py", _COMMON_SHA256),
    ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
    ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    method_id: _SUPPORT
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    RADICAL_PREDICT_METHOD_ID: 1,
    RADICAL_BACKTEST_METHOD_ID: 50,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    RADICAL_PREDICT_METHOD_ID: 1,
    RADICAL_BACKTEST_METHOD_ID: 2,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    RADICAL_PREDICT_METHOD_ID: (
        "ONE_GAP_01_19_WEIGHTED_TICKET_WITH_LOW_SUM_SHIFT"
    ),
    RADICAL_BACKTEST_METHOD_ID: (
        "TWO_POSITIONAL_GAP_TICKETS_EXCLUDING_01_19_THEN_20_29"
    ),
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    RADICAL_PREDICT_METHOD_ID: (
        "deviation_predict:weight_1.5",
        "markov_predict:weight_1.2",
        "frequency_predict:weight_1.0",
    ),
    RADICAL_BACKTEST_METHOD_ID: (
        "gap_01_19",
        "gap_20_29",
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    method_id: len(members)
    for method_id, members in (
        SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE31_METHOD.items()
    )
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    method_id: "RECENT_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE31_METHOD: Final = {
    RADICAL_PREDICT_METHOD_ID: (
        "DATABASE_GET_ALL_DRAWS_NEWEST_FIRST_WITH_DRAW_115000007_FILTERED"
    ),
    RADICAL_BACKTEST_METHOD_ID: (
        "DATABASE_NEWEST_300_REVERSED_FOR_TARGET_LOOP_THEN_PRIOR_ROWS_"
        "REVERSED_BACK_TO_NEWEST_FIRST"
    ),
}


class LegacySourceNativeWave31Error(ValueError):
    """A request cannot satisfy the thirty-first source-native contract."""


class LegacySourceNativeWave31SourceError(LegacySourceNativeWave31Error):
    """The frozen source emitted no valid native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave31Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE31_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave31Metadata:
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
    source_history_first_draw_number: str
    source_history_last_draw_number: str
    source_history_draw_count: int
    source_history_limit: int | None
    hardcoded_excluded_draw_numbers: tuple[str, ...]
    gap_exclusion_ranges: tuple[tuple[int, int], ...]
    candidate_k: int | None
    candidate_pools: tuple[tuple[int, ...], ...]
    native_ticket_count: int
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: int | None
    combination_members: tuple[str, ...]
    source_method_combination_count: int
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave31Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave31Metadata


def _validate_request(request: LegacySourceNativeWave31Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS:
        raise LegacySourceNativeWave31Error(
            "unsupported frozen source-native wave-31 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or len(request.history)
        < MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE31_METHOD[
            request.legacy_method_id
        ]
    ):
        raise LegacySourceNativeWave31Error(
            "invalid frozen source-native wave-31 request"
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
            raise LegacySourceNativeWave31Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave31Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE31_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _engine_ticket(
    method_name: str,
    source_history: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    if method_name == "deviation":
        return frozen_deviation_ticket(source_history)
    if method_name == "markov":
        return frozen_markov_ticket(source_history)[0]
    if method_name == "frequency":
        return frozen_frequency_ticket(source_history)
    raise LegacySourceNativeWave31Error("unknown frozen Unified method")


def _weighted_candidates(
    source_history: tuple[LegacyHistoryDraw, ...],
    exclude_range: range,
    *,
    cold_bonus: bool,
    strict_primary_methods: bool,
) -> tuple[int, ...]:
    candidates: dict[int, float] = {}
    for method_name, weight in (
        ("deviation", 1.5),
        ("markov", 1.2),
        ("frequency", 1.0),
    ):
        try:
            result = _engine_ticket(method_name, source_history)
        except Exception:
            if strict_primary_methods and method_name != "frequency":
                raise
            continue
        for index, number in enumerate(result):
            if number not in exclude_range:
                candidates[number] = (
                    candidates.get(number, 0.0)
                    + (20 - index) * weight
                )
    if cold_bonus:
        recent_counts = Counter(
            number
            for draw in source_history[:50]
            for number in draw.numbers
        )
        for number in range(1, 50):
            if number not in exclude_range and recent_counts[number] <= 1:
                candidates[number] = candidates.get(number, 0.0) + 15
    ranked = sorted(
        candidates,
        key=lambda number: candidates[number],
        reverse=True,
    )
    return tuple(ranked[:12])


def _ticket(values: tuple[int, ...]) -> Ticket:
    ticket = tuple(sorted(values))
    if (
        len(ticket) != 6
        or len(set(ticket)) != 6
        or any(not 1 <= number <= 49 for number in ticket)
    ):
        raise LegacySourceNativeWave31SourceError(
            "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
        )
    return ticket


def generate_legacy_source_native_wave31_portfolio(
    request: LegacySourceNativeWave31Request,
) -> LegacySourceNativeWave31Result:
    """Reproduce one frozen radical gap portfolio."""

    _validate_request(request)
    method_id = request.legacy_method_id
    newest_first = tuple(reversed(request.history))
    hardcoded_excluded: tuple[str, ...] = ()
    source_limit: int | None = None
    if method_id == RADICAL_PREDICT_METHOD_ID:
        hardcoded_excluded = ("115000007",)
        source_history = tuple(
            draw
            for draw in newest_first
            if draw.draw_number not in hardcoded_excluded
        )
        if not source_history:
            raise LegacySourceNativeWave31SourceError(
                "FROZEN_SOURCE_HISTORY_EMPTY_AFTER_HARDCODED_FILTER"
            )
        pool = _weighted_candidates(
            source_history,
            range(1, 20),
            cold_bonus=True,
            strict_primary_methods=True,
        )
        selected = pool[:6]
        if sum(selected) < 150 and len(pool) > 6:
            selected = pool[1:7]
        tickets = (_ticket(selected),)
        candidate_pools = (pool,)
        gap_ranges = ((1, 19),)
        candidate_k: int | None = None
        native_order = "ONE_GAP_01_19_TICKET"
    else:
        source_limit = 300
        source_history = newest_first[:source_limit]
        candidate_pools = (
            _weighted_candidates(
                source_history,
                range(1, 20),
                cold_bonus=False,
                strict_primary_methods=False,
            ),
            _weighted_candidates(
                source_history,
                range(20, 30),
                cold_bonus=False,
                strict_primary_methods=False,
            ),
        )
        tickets = tuple(_ticket(pool[:6]) for pool in candidate_pools)
        gap_ranges = ((1, 19), (20, 29))
        candidate_k = None
        native_order = "GAP_01_19_THEN_GAP_20_29"
    if len(tickets) != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
        method_id
    ]:
        raise LegacySourceNativeWave31SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    material, digest, seed_integer = _seed(request)
    return LegacySourceNativeWave31Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave31Metadata(
            protocol=SOURCE_NATIVE_WAVE31_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD[
                method_id
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
            source_history_order="RECENT_FIRST",
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            source_history_first_draw_number=source_history[0].draw_number,
            source_history_last_draw_number=source_history[-1].draw_number,
            source_history_draw_count=len(source_history),
            source_history_limit=source_limit,
            hardcoded_excluded_draw_numbers=hardcoded_excluded,
            gap_exclusion_ranges=gap_ranges,
            candidate_k=candidate_k,
            candidate_pools=candidate_pools,
            native_ticket_count=len(tickets),
            native_ticket_order=native_order,
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
            tie_order_semantics=(
                "COUNTER_FIRST_INSERTION_THEN_ASCENDING_RANGE_INSERTION"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE31_METHOD[
                    method_id
                ]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE31_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "RADICAL_BACKTEST_METHOD_ID",
    "RADICAL_PREDICT_METHOD_ID",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "SOURCE_NATIVE_WAVE31_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS",
    "LegacySourceNativeWave31Error",
    "LegacySourceNativeWave31Metadata",
    "LegacySourceNativeWave31Request",
    "LegacySourceNativeWave31Result",
    "LegacySourceNativeWave31SourceError",
    "generate_legacy_source_native_wave31_portfolio",
]
