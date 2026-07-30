"""Faithful ports of the twenty-fifth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final, cast

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    FrozenUnifiedTickets,
    generate_frozen_unified_tickets,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave24 import (
    frozen_tools_kill_numbers,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE25_PROTOCOL = "legacy_source_native_wave25/v1"
DEFAULT_SOURCE_NATIVE_WAVE25_USER_SEED = (
    "biglotto-full-universe-source-native-wave25-v1"
)
TME_OPTIMIZER_METHOD_ID = (
    "lottery_api/models/biglotto_tme_optimizer.py"
)
CAG_METHOD_ID = "tools/test_cag.py"
CLUSTER_COVER_METHOD_ID = "tools/test_cluster_cover.py"
ZDP_METHOD_ID = "tools/test_zdp.py"
SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS = (
    TME_OPTIMIZER_METHOD_ID,
    CAG_METHOD_ID,
    CLUSTER_COVER_METHOD_ID,
    ZDP_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    TME_OPTIMIZER_METHOD_ID: (
        "62c6cb676bada8f8dd80ec0448622c6394caf9459318b9cd0790fd2a800e6bcb"
    ),
    CAG_METHOD_ID: (
        "7ca5343dfedd506f06277efc2ee4a45e61b4cc96722736dd28a93a085c7d7cec"
    ),
    CLUSTER_COVER_METHOD_ID: (
        "5b43959e7c55d9590e858ac51a5d6fd361e4bf71e519b1f4d3fee6dba071feeb"
    ),
    ZDP_METHOD_ID: (
        "e80cc7e954534e34095d413bb1db763ca6208b5a159dd9cffaa351a4eaf7337b"
    ),
}
_THREE_BET_OPTIMIZER_SHA256 = (
    "2835d6cb20c5351f636ef649b9b437f8b474cfad7bbd585aba3d08a95b18742a"
)
_TOOLS_NEGATIVE_SELECTOR_SHA256 = (
    "80e79f80f9f5978ee2d7e71bb65e7b63bf101192a402ab8a9d0644796d4e3ff0"
)
_COMMON_SHA256 = (
    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
)
_CORE_SUPPORT = (
    ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
    ("lottery_api/common.py", _COMMON_SHA256),
    ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
    ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
)
_BASE_SUPPORT = (
    (
        "lottery_api/models/biglotto_3bet_optimizer.py",
        _THREE_BET_OPTIMIZER_SHA256,
    ),
    ("tools/negative_selector.py", _TOOLS_NEGATIVE_SELECTOR_SHA256),
)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    TME_OPTIMIZER_METHOD_ID: (
        *_CORE_SUPPORT,
        (
            "tools/negative_selector.py",
            _TOOLS_NEGATIVE_SELECTOR_SHA256,
        ),
    ),
    CAG_METHOD_ID: _CORE_SUPPORT + _BASE_SUPPORT,
    CLUSTER_COVER_METHOD_ID: _CORE_SUPPORT + _BASE_SUPPORT,
    ZDP_METHOD_ID: _CORE_SUPPORT + _BASE_SUPPORT,
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    method_id: 1 for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    TME_OPTIMIZER_METHOD_ID: 4,
    CAG_METHOD_ID: 3,
    CLUSTER_COVER_METHOD_ID: 3,
    ZDP_METHOD_ID: 3,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    TME_OPTIMIZER_METHOD_ID: (
        "FOUR_POSITIONAL_INDEPENDENT_UNIFIED_TICKETS_STATISTICAL_"
        "DEVIATION_MARKOV_THEN_HOT_COLD"
    ),
    CAG_METHOD_ID: (
        "THREE_POSITIONAL_TOP3_ANCHOR_COOCCURRENCE_GROUP_TICKETS_FROM_"
        "BASE_TOP18"
    ),
    CLUSTER_COVER_METHOD_ID: (
        "THREE_POSITIONAL_ROUND_ROBIN_DISJOINT_COOCCURRENCE_CLUSTER_"
        "TICKETS_FROM_BASE_TOP18"
    ),
    ZDP_METHOD_ID: (
        "THREE_POSITIONAL_LOW_MID_HIGH_HEAVY_ZONE_TICKETS_FROM_WEIGHTED_"
        "TOP30_POOL"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    TME_OPTIMIZER_METHOD_ID: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_STATISTICAL"
    ),
    CAG_METHOD_ID: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_STATISTICAL"
    ),
    CLUSTER_COVER_METHOD_ID: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_STATISTICAL"
    ),
    ZDP_METHOD_ID: (
        "STATISTICAL_CALLS_RESEED_WITH_CAUSAL_HISTORY_LENGTH_THEN_EACH_"
        "ZONE_FALLBACK_RESEEDS_PYTHON_RANDOM_TO_42"
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    method_id: 4 if method_id == TME_OPTIMIZER_METHOD_ID else 3
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    TME_OPTIMIZER_METHOD_ID: (
        "statistical_predict:independent_ticket",
        "deviation_predict:independent_ticket",
        "markov_predict:independent_ticket",
        "hot_cold_mix_predict:independent_ticket",
    ),
    CAG_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.0",
    ),
    CLUSTER_COVER_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.0",
    ),
    ZDP_METHOD_ID: (
        "deviation_predict:weight_1.5",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_2.0",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE25_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS
}


class LegacySourceNativeWave25Error(ValueError):
    """A request cannot satisfy the twenty-fifth source-native contract."""


class LegacySourceNativeWave25SourceError(
    LegacySourceNativeWave25Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave25Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE25_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave25Metadata:
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
    native_ticket_order: str
    native_duplicate_ticket_count: int
    candidate_k: int | None
    candidate_pool: tuple[int, ...]
    candidate_pool_size: int | None
    combination_count: int | None
    combination_members: tuple[str, ...]
    source_method_combination_count: int
    kill_numbers: tuple[int, ...]
    markov_order: int
    statistical_call_count: int
    set_iteration_semantics: str
    non_ticket_side_calculation_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave25Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave25Metadata


def _validate_request(request: LegacySourceNativeWave25Request) -> None:
    if (
        request.legacy_method_id
        not in SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS
    ):
        raise LegacySourceNativeWave25Error(
            "unsupported frozen source-native wave-25 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave25Error(
            "invalid frozen source-native wave-25 request"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacySourceNativeWave25Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        if (
            len(draw.numbers) != 6
            or len(set(draw.numbers)) != 6
            or any(
                type(number) is not int or not 1 <= number <= 49
                for number in draw.numbers
            )
        ):
            raise LegacySourceNativeWave25Error(
                "causal history ticket is invalid"
            )


def _seed(
    request: LegacySourceNativeWave25Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE25_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _weighted_candidates(
    unified: FrozenUnifiedTickets,
    specifications: tuple[tuple[str, float], ...],
) -> Counter[int]:
    tickets = {
        "deviation": unified.deviation,
        "markov": unified.markov,
        "statistical": unified.statistical,
    }
    candidates: Counter[int] = Counter()
    for method_name, weight in specifications:
        for number in tickets[method_name]:
            candidates[number] += cast(int, weight)
    return candidates


def _base_top18(
    unified: FrozenUnifiedTickets,
    kill_numbers: tuple[int, ...],
) -> list[int]:
    candidates = _weighted_candidates(
        unified,
        (
            ("deviation", 2.0),
            ("markov", 1.5),
            ("statistical", 1.0),
        ),
    )
    for number in kill_numbers:
        candidates[number] = -9999
    return [number for number, _score in candidates.most_common(18)]


def _cooccurrence(
    history: tuple[LegacyHistoryDraw, ...],
) -> defaultdict[int, Counter[int]]:
    matrix: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in history[-200:]:
        for left, right in combinations(sorted(draw.numbers), 2):
            matrix[left][right] += 1
            matrix[right][left] += 1
    return matrix


def _cag_rows(
    top_candidates: list[int],
    history: tuple[LegacyHistoryDraw, ...],
) -> list[list[int]]:
    matrix = _cooccurrence(history)
    anchors = top_candidates[:3]
    pool = set(top_candidates)
    rows: list[list[int]] = []
    for anchor in anchors:
        companions = [
            (candidate, matrix[anchor][candidate])
            for candidate in pool
            if candidate != anchor
        ]
        companions.sort(
            key=lambda item: (
                item[1],
                -top_candidates.index(item[0]),
            ),
            reverse=True,
        )
        if len(companions) < 5:
            raise LegacySourceNativeWave25SourceError(
                "FROZEN_SOURCE_CANDIDATE_INDEX_OUT_OF_RANGE"
            )
        rows.append(
            sorted(
                [anchor]
                + [companions[index][0] for index in range(5)]
            )
        )
    return rows


def _cluster_cover_rows(
    top_candidates: list[int],
    history: tuple[LegacyHistoryDraw, ...],
) -> list[list[int]]:
    matrix = _cooccurrence(history)
    anchors = top_candidates[:3]
    rows = [[anchor] for anchor in anchors]
    available = set(top_candidates[3:])
    for _round in range(5):
        for row_index in range(3):
            if not available:
                break
            best_candidate: int | None = None
            maximum_score = -1
            for candidate in available:
                score = sum(
                    matrix[candidate][member]
                    for member in rows[row_index]
                )
                if score > maximum_score:
                    maximum_score = score
                    best_candidate = candidate
            if best_candidate:
                rows[row_index].append(best_candidate)
                available.remove(best_candidate)
    return [sorted(row) for row in rows]


def _zdp_rows(
    unified: FrozenUnifiedTickets,
    kill_numbers: tuple[int, ...],
) -> tuple[list[list[int]], list[int]]:
    candidates = _weighted_candidates(
        unified,
        (
            ("deviation", 1.5),
            ("markov", 1.5),
            ("statistical", 2.0),
        ),
    )
    for number in kill_numbers:
        candidates[number] = -9999
    top_candidates = [
        number for number, _score in candidates.most_common(30)
    ]
    low = [number for number in top_candidates if 1 <= number <= 16]
    middle = [
        number for number in top_candidates if 17 <= number <= 32
    ]
    high = [
        number for number in top_candidates if 33 <= number <= 49
    ]
    rows: list[list[int]] = []
    for heavy, others in (
        (low, middle + high),
        (middle, low + high),
        (high, low + middle),
    ):
        source_random = random.Random(42)
        row = list(heavy[:4])
        index = 0
        while len(row) < 6 and index < len(others):
            if others[index] not in row:
                row.append(others[index])
            index += 1
        while len(row) < 6:
            row.append(source_random.randint(1, 49))
        rows.append(sorted(row))
    return rows, top_candidates


def _tickets_or_close(
    rows: list[list[int]] | tuple[Ticket, ...],
) -> tuple[Ticket, ...]:
    tickets: list[Ticket] = []
    for row in rows:
        ticket = tuple(sorted(row))
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(not 1 <= number <= 49 for number in ticket)
        ):
            raise LegacySourceNativeWave25SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    return tuple(tickets)


def build_legacy_source_native_wave25_result(
    request: LegacySourceNativeWave25Request,
    unified: FrozenUnifiedTickets,
) -> LegacySourceNativeWave25Result:
    """Build method-specific native output from one shared frozen core run."""

    _validate_request(request)
    method_id = request.legacy_method_id
    candidate_pool: list[int] = []
    kill_numbers: tuple[int, ...] = ()
    statistical_call_count = 1
    set_semantics = "NOT_APPLICABLE_NO_SOURCE_SET_TIE_BREAK"
    non_ticket = "NONE"
    if method_id == TME_OPTIMIZER_METHOD_ID:
        rows: list[list[int]] | tuple[Ticket, ...] = (
            unified.statistical,
            unified.deviation,
            unified.markov,
            unified.hot_cold,
        )
    else:
        kill_numbers = frozen_tools_kill_numbers(request.history)
        if method_id in (CAG_METHOD_ID, CLUSTER_COVER_METHOD_ID):
            candidate_pool = _base_top18(unified, kill_numbers)
            set_semantics = (
                "FROZEN_CPYTHON_INTEGER_SET_ITERATION_CONTROLS_EQUAL_"
                "SCORE_TIES"
            )
            rows = (
                _cag_rows(candidate_pool, request.history)
                if method_id == CAG_METHOD_ID
                else _cluster_cover_rows(
                    candidate_pool,
                    request.history,
                )
            )
        else:
            rows, candidate_pool = _zdp_rows(unified, kill_numbers)
            statistical_call_count = 2
            non_ticket = (
                "BASE_THREE_BET_PREDICTION_CALCULATED_FIRST_BUT_RESULT_"
                "IS_UNUSED_BEFORE_INDEPENDENT_ZDP_SCORING"
            )
    tickets = _tickets_or_close(rows)
    expected_count = (
        NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD[method_id]
    )
    if len(tickets) != expected_count:
        raise LegacySourceNativeWave25SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave25Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave25Metadata(
            protocol=SOURCE_NATIVE_WAVE25_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD[method_id]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE25_METHOD[method_id]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_STATISTICAL_HISTORY_LENGTH_SEED_AND_ZDP_"
                "FALLBACK_SEED_42_WHEN_APPLICABLE"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE25_METHOD[
                    method_id
                ]
            ),
            native_ticket_count=len(tickets),
            native_ticket_order=(
                "FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER"
            ),
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
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE25_METHOD[
                    method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD[
                    method_id
                ]
            ),
            kill_numbers=kill_numbers,
            markov_order=unified.markov_order,
            statistical_call_count=statistical_call_count,
            set_iteration_semantics=set_semantics,
            non_ticket_side_calculation_semantics=non_ticket,
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE25_METHOD[
                    method_id
                ]
            ),
        ),
    )


def generate_legacy_source_native_wave25_portfolio(
    request: LegacySourceNativeWave25Request,
) -> LegacySourceNativeWave25Result:
    """Reproduce one frozen TME, cooccurrence, or zonal portfolio."""

    _validate_request(request)
    try:
        unified = generate_frozen_unified_tickets(request.history)
    except ValueError as exc:
        raise LegacySourceNativeWave25SourceError(str(exc)) from exc
    return build_legacy_source_native_wave25_result(request, unified)


__all__ = [
    "CAG_METHOD_ID",
    "CLUSTER_COVER_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE25_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "SOURCE_NATIVE_WAVE25_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE25_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE25_METHODS",
    "TME_OPTIMIZER_METHOD_ID",
    "ZDP_METHOD_ID",
    "LegacySourceNativeWave25Error",
    "LegacySourceNativeWave25Metadata",
    "LegacySourceNativeWave25Request",
    "LegacySourceNativeWave25Result",
    "LegacySourceNativeWave25SourceError",
    "build_legacy_source_native_wave25_result",
    "generate_legacy_source_native_wave25_portfolio",
]
