"""Faithful ports of the twenty-sixth frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final, cast

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    frozen_bayesian_ticket,
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_hot_cold_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
    frozen_trend_ticket,
    frozen_zone_balance_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave24 import (
    frozen_tools_kill_numbers,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE26_PROTOCOL = "legacy_source_native_wave26/v1"
DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED = (
    "biglotto-full-universe-source-native-wave26-v1"
)
CES_METHOD_ID = "tools/test_ces.py"
DMS_METHOD_ID = "tools/test_dms.py"
GREEDY_METHOD_ID = "tools/test_greedy_optimizer.py"
MWSC_METHOD_ID = "tools/test_mwsc.py"
PCE_METHOD_ID = "tools/test_pce.py"
SMH_CLOSED_METHOD_ID = "tools/test_smh.py"
SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS = (
    CES_METHOD_ID,
    DMS_METHOD_ID,
    GREEDY_METHOD_ID,
    MWSC_METHOD_ID,
    PCE_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    CES_METHOD_ID: (
        "78d17c530ab8cacf25146c5c39cb4017e3a3ffacde90a4e14ae07a8026b0bc22"
    ),
    DMS_METHOD_ID: (
        "b63442289bd5862955075bdea70bc682e16b2fe885190d16367b7b2987234dd1"
    ),
    GREEDY_METHOD_ID: (
        "82df7f878ece8f9daa86b3efc1208dd85440bab8a241308fcf7a2d14c7cd6db6"
    ),
    MWSC_METHOD_ID: (
        "ba37643d6a3b533d1e61dadf91f040e667d088e95a5163007d568931bcdc6033"
    ),
    PCE_METHOD_ID: (
        "9c0cf22b42179ffc496f7fb93cbc3cfc902a7ff60a43095e3fe1f44168b6d28c"
    ),
    SMH_CLOSED_METHOD_ID: (
        "dc7d83ebf7b7d35c6c9b721b4da735b6b8a701614de3205bfc0405c3d4a9995d"
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
_SUPPORT = (
    ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
    ("lottery_api/common.py", _COMMON_SHA256),
    ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
    ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
    (
        "lottery_api/models/biglotto_3bet_optimizer.py",
        _THREE_BET_OPTIMIZER_SHA256,
    ),
    ("tools/negative_selector.py", _TOOLS_NEGATIVE_SELECTOR_SHA256),
)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    method_id: _SUPPORT
    for method_id in (
        *SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS,
        SMH_CLOSED_METHOD_ID,
    )
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    CES_METHOD_ID: 1,
    DMS_METHOD_ID: 20,
    GREEDY_METHOD_ID: 1,
    MWSC_METHOD_ID: 1,
    PCE_METHOD_ID: 1,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    method_id: 3 for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    CES_METHOD_ID: (
        "THREE_POSITIONAL_SCORE_SORTED_CONSTRAINED_TOP20_COMBINATIONS"
    ),
    DMS_METHOD_ID: (
        "THREE_POSITIONAL_RECENT_AUDIT_SELECTED_UNIFIED_METHOD_TICKETS"
    ),
    GREEDY_METHOD_ID: (
        "THREE_POSITIONAL_DIVERSITY_GREEDY_TOP18_COMBINATIONS"
    ),
    MWSC_METHOD_ID: (
        "THREE_POSITIONAL_SLICES_FROM_MULTI_WINDOW_CONSENSUS_TOP18"
    ),
    PCE_METHOD_ID: (
        "UP_TO_THREE_POSITIONAL_PAIRWISE_CONSENSUS_GREEDY_TICKETS"
    ),
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    CES_METHOD_ID: (
        "deviation_predict:weight_1.5",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_2.0",
        "hot_cold_mix_predict:weight_1.0",
    ),
    DMS_METHOD_ID: (
        "frequency_predict:audit_candidate",
        "bayesian_predict:audit_candidate",
        "markov_predict:audit_candidate",
        "trend_predict:audit_candidate",
        "deviation_predict:audit_candidate",
        "statistical_predict:audit_candidate",
        "zone_balance_predict:audit_candidate",
        "hot_cold_mix_predict:audit_candidate",
    ),
    GREEDY_METHOD_ID: (
        "deviation_predict:weight_1.5",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_2.0",
    ),
    MWSC_METHOD_ID: tuple(
        f"{window}:{method}"
        for window in (10, 20, 50, 100)
        for method in (
            "statistical_predict",
            "deviation_predict",
            "markov_predict",
        )
    ),
    PCE_METHOD_ID: (
        "frequency_predict",
        "bayesian_predict",
        "markov_predict",
        "deviation_predict",
        "statistical_predict",
        "trend_predict",
        "zone_balance_predict",
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    method_id: len(members)
    for method_id, members in (
        SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE26_METHOD.items()
    )
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE26_METHOD: Final = {
    method_id: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_EACH_"
        "STATISTICAL_PREDICT_CALL"
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS
}
SMH_CLOSED_REASON_CODE = (
    "CLOSED_UNEXECUTABLE:UNSEEDED_MODULE_GLOBAL_RANDOM_STATE_NOT_SERIALIZED"
)

_ENGINE_METHOD_ORDER = (
    "frequency",
    "bayesian",
    "markov",
    "trend",
    "deviation",
    "statistical",
    "zone_balance",
    "hot_cold_mix",
)
EngineCache = Mapping[tuple[int, str], tuple[int, ...]]


class LegacySourceNativeWave26Error(ValueError):
    """A request cannot satisfy the twenty-sixth source-native contract."""


class LegacySourceNativeWave26SourceError(LegacySourceNativeWave26Error):
    """The frozen source emitted no valid three-ticket native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave26Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave26Metadata:
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
    selected_methods: tuple[str, ...]
    statistical_call_count: int
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave26Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave26Metadata


def _validate_request(request: LegacySourceNativeWave26Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS:
        raise LegacySourceNativeWave26Error(
            "unsupported frozen source-native wave-26 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave26Error(
            "invalid frozen source-native wave-26 request"
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
            raise LegacySourceNativeWave26Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave26Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE26_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def frozen_wave26_engine_output(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[int, ...]:
    """Return exactly the frozen Unified main-number result, including empty."""

    if method_name == "frequency":
        return () if not history else frozen_frequency_ticket(history)
    if method_name == "bayesian":
        return frozen_bayesian_ticket(history)
    if method_name == "markov":
        return frozen_markov_ticket(history)[0]
    if method_name == "trend":
        return frozen_trend_ticket(history)
    if method_name == "deviation":
        return frozen_deviation_ticket(history)
    if method_name == "statistical":
        return frozen_statistical_ticket(history)[0]
    if method_name == "zone_balance":
        return frozen_zone_balance_ticket(history)
    if method_name == "hot_cold_mix":
        return frozen_hot_cold_ticket(history)
    raise LegacySourceNativeWave26Error("unknown frozen Unified method")


def _engine_output(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> tuple[int, ...]:
    key = (len(history), method_name)
    if cache is not None and key in cache:
        return cache[key]
    return frozen_wave26_engine_output(method_name, history)


def _weighted_pool(
    history: tuple[LegacyHistoryDraw, ...],
    specifications: tuple[tuple[str, float], ...],
    kill_numbers: tuple[int, ...],
    cache: EngineCache | None,
    limit: int,
) -> list[int]:
    scores: Counter[int] = Counter()
    for method_name, weight in specifications:
        try:
            for number in _engine_output(method_name, history, cache):
                scores[number] += cast(int, weight)
        except Exception:
            continue
    for number in kill_numbers:
        scores[number] = -9999
    return [number for number, _score in scores.most_common(limit)]


def _ces_valid(row: tuple[int, ...]) -> bool:
    if not 110 <= sum(row) <= 190:
        return False
    differences = {
        right - left
        for left, right in combinations(sorted(row), 2)
    }
    if len(differences) - 5 < 6:
        return False
    odd = sum(number % 2 == 1 for number in row)
    return 2 <= odd <= 4 and max(row) - min(row) >= 25


def _ces_rows(
    history: tuple[LegacyHistoryDraw, ...],
    kill_numbers: tuple[int, ...],
    cache: EngineCache | None,
) -> tuple[list[list[int]], list[int]]:
    specifications = (
        ("deviation", 1.5),
        ("markov", 1.5),
        ("statistical", 2.0),
        ("hot_cold_mix", 1.0),
    )
    pool = _weighted_pool(
        history, specifications, kill_numbers, cache, 20
    )
    scores: Counter[int] = Counter()
    for method_name, weight in specifications:
        try:
            for number in _engine_output(method_name, history, cache):
                scores[number] += cast(int, weight)
        except Exception:
            continue
    for number in kill_numbers:
        scores[number] = -9999
    valid = [
        (row, sum(scores[number] for number in row))
        for row in combinations(pool, 6)
        if _ces_valid(row)
    ]
    valid.sort(key=lambda item: item[1], reverse=True)
    selected: list[tuple[int, ...]] = []
    for row, _score in valid:
        if not selected or all(
            len(set(row) & set(previous)) <= 2
            for previous in selected
        ):
            selected.append(row)
        if len(selected) >= 3:
            break
    while len(selected) < 3 and valid:
        selected.append(valid[len(selected)][0])
    return [sorted(row) for row in selected], pool


def _dms_rows(
    history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> tuple[list[list[int]], tuple[str, ...]]:
    if len(history) < 20:
        raise LegacySourceNativeWave26SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    performance: Counter[str] = Counter()
    for index in range(10, 30):
        offset = 30 - index
        actual = set(history[-offset].numbers)
        past = history[:-offset]
        for method_name in _ENGINE_METHOD_ORDER:
            try:
                output = _engine_output(method_name, past, cache)
                performance[method_name] += len(set(output) & actual)
            except Exception:
                continue
    top_methods = tuple(
        method_name
        for method_name, _score in performance.most_common(3)
    )
    rows: list[list[int]] = []
    for method_name in top_methods:
        try:
            rows.append(
                sorted(_engine_output(method_name, history, cache))
            )
        except Exception:
            continue
    while len(rows) < 3:
        rows.append(
            sorted(_engine_output("statistical", history, cache))
        )
    return rows, top_methods


def _mwsc_rows(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[list[list[int]], list[int]]:
    consensus: Counter[int] = Counter()
    for window in (10, 20, 50, 100):
        past = history[-window:]
        for method_name in ("statistical", "deviation", "markov"):
            try:
                for number in frozen_wave26_engine_output(
                    method_name, past
                ):
                    consensus[number] += 1
            except Exception:
                continue
    kill_numbers = frozen_tools_kill_numbers(history)
    for number in kill_numbers:
        consensus[number] = -9999
    pool = [number for number, _score in consensus.most_common(18)]
    return (
        [
            sorted(pool[start:end])
            for start, end in ((0, 6), (4, 10), (8, 14))
        ],
        pool,
    )


def _pce_rows(
    history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> list[list[int]]:
    predictions: list[tuple[int, ...]] = []
    for method_name in (
        "frequency",
        "bayesian",
        "markov",
        "deviation",
        "statistical",
        "trend",
        "zone_balance",
    ):
        try:
            predictions.append(
                _engine_output(method_name, history, cache)
            )
        except Exception:
            continue
    pair_votes: Counter[tuple[int, int]] = Counter()
    number_votes: Counter[int] = Counter()
    for prediction in predictions:
        for number in prediction:
            number_votes[number] += 1
        for pair in combinations(sorted(prediction), 2):
            pair_votes[pair] += 1
    kill_set = set(frozen_tools_kill_numbers(history))
    sorted_pairs = sorted(
        pair_votes.items(), key=lambda item: item[1], reverse=True
    )
    remaining = sorted(
        number_votes.items(), key=lambda item: item[1], reverse=True
    )
    rows: list[list[int]] = []
    for pair, _votes in sorted_pairs:
        if pair[0] in kill_set or pair[1] in kill_set:
            continue
        row = set(pair)
        for number, _votes in remaining:
            if number not in row and number not in kill_set:
                row.add(number)
            if len(row) >= 6:
                break
        ordered = sorted(row)
        if len(ordered) == 6 and ordered not in rows:
            rows.append(ordered)
        if len(rows) >= 3:
            break
    return rows


def _greedy_score(
    row: tuple[int, ...],
    number_scores: Counter[int],
    matrix: defaultdict[int, Counter[int]],
) -> float:
    score = sum(number_scores.get(number, 0) for number in row)
    score += (
        sum(
            matrix[left][right]
            for left, right in combinations(sorted(row), 2)
        )
        * 0.1
    )
    score -= abs(sum(row) - 150) / 50
    differences = {
        right - left
        for left, right in combinations(sorted(row), 2)
    }
    if len(differences) - 5 < 6:
        score -= 5
    odd = sum(number % 2 == 1 for number in row)
    if odd < 2 or odd > 4:
        score -= 10
    return score


def _greedy_rows(
    history: tuple[LegacyHistoryDraw, ...],
    kill_numbers: tuple[int, ...],
    cache: EngineCache | None,
) -> tuple[list[list[int]], list[int]]:
    specifications = (
        ("deviation", 1.5),
        ("markov", 1.5),
        ("statistical", 2.0),
    )
    pool = _weighted_pool(
        history, specifications, kill_numbers, cache, 18
    )
    number_scores: Counter[int] = Counter()
    for method_name, weight in specifications:
        try:
            for number in _engine_output(method_name, history, cache):
                number_scores[number] += cast(int, weight)
        except Exception:
            continue
    for number in kill_numbers:
        number_scores[number] = -999
    matrix: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in history[-200:]:
        for left, right in combinations(sorted(draw.numbers), 2):
            matrix[left][right] += 1
            matrix[right][left] += 1
    top_five = set(pool[:5])
    scored = [
        (row, _greedy_score(row, number_scores, matrix))
        for row in combinations(pool, 6)
        if len(set(row) & top_five) >= 1
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    selected: list[tuple[int, ...]] = []
    for row, _score in scored:
        if not selected or all(
            len(set(row) & set(previous)) <= 3
            for previous in selected
        ):
            selected.append(row)
        if len(selected) >= 3:
            break
    return [sorted(row) for row in selected], pool


def _tickets_or_close(rows: list[list[int]]) -> tuple[Ticket, ...]:
    tickets: list[Ticket] = []
    for row in rows:
        ticket = tuple(sorted(row))
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(not 1 <= number <= 49 for number in ticket)
        ):
            raise LegacySourceNativeWave26SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    if len(tickets) != 3:
        raise LegacySourceNativeWave26SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    return tuple(tickets)


def generate_legacy_source_native_wave26_portfolio(
    request: LegacySourceNativeWave26Request,
    *,
    engine_cache: EngineCache | None = None,
) -> LegacySourceNativeWave26Result:
    """Reproduce one frozen CES, DMS, Greedy, MWSC, or PCE portfolio."""

    _validate_request(request)
    method_id = request.legacy_method_id
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE26_METHOD[method_id]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave26SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    kill_numbers: tuple[int, ...] = ()
    candidate_pool: list[int] = []
    selected_methods: tuple[str, ...] = ()
    statistical_calls = 1
    if method_id == CES_METHOD_ID:
        kill_numbers = frozen_tools_kill_numbers(request.history)
        rows, candidate_pool = _ces_rows(
            request.history, kill_numbers, engine_cache
        )
    elif method_id == DMS_METHOD_ID:
        rows, selected_methods = _dms_rows(
            request.history, engine_cache
        )
        statistical_calls = 20 + int(
            "statistical" in selected_methods
        )
    elif method_id == GREEDY_METHOD_ID:
        kill_numbers = frozen_tools_kill_numbers(request.history)
        rows, candidate_pool = _greedy_rows(
            request.history, kill_numbers, engine_cache
        )
    elif method_id == MWSC_METHOD_ID:
        rows, candidate_pool = _mwsc_rows(request.history)
        kill_numbers = frozen_tools_kill_numbers(request.history)
        statistical_calls = 4
    else:
        rows = _pce_rows(request.history, engine_cache)
        kill_numbers = frozen_tools_kill_numbers(request.history)
    tickets = _tickets_or_close(rows)
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave26Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave26Metadata(
            protocol=SOURCE_NATIVE_WAVE26_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[method_id]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE26_METHOD[method_id]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_STATISTICAL_CALLS_RESEED_FROM_THEIR_CAUSAL_"
                "HISTORY_LENGTH"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
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
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE26_METHOD[
                    method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD[
                    method_id
                ]
            ),
            kill_numbers=kill_numbers,
            selected_methods=selected_methods,
            statistical_call_count=statistical_calls,
            tie_order_semantics=(
                "FROZEN_COUNTER_INSERTION_AND_STABLE_SORT_ORDER"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE26_METHOD[
                    method_id
                ]
            ),
        ),
    )


__all__ = [
    "CES_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED",
    "DMS_METHOD_ID",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "GREEDY_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "MWSC_METHOD_ID",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "PCE_METHOD_ID",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "SMH_CLOSED_METHOD_ID",
    "SMH_CLOSED_REASON_CODE",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "SOURCE_NATIVE_WAVE26_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS",
    "EngineCache",
    "LegacySourceNativeWave26Error",
    "LegacySourceNativeWave26Metadata",
    "LegacySourceNativeWave26Request",
    "LegacySourceNativeWave26Result",
    "LegacySourceNativeWave26SourceError",
    "frozen_wave26_engine_output",
    "generate_legacy_source_native_wave26_portfolio",
]
