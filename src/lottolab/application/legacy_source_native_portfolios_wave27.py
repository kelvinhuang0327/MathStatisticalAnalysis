"""Faithful ports of the twenty-seventh frozen BIG_LOTTO strategy batch."""

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
    frozen_bayesian_ticket,
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE27_PROTOCOL = "legacy_source_native_wave27/v1"
DEFAULT_SOURCE_NATIVE_WAVE27_USER_SEED = (
    "biglotto-full-universe-source-native-wave27-v1"
)
MODEL_V1_METHOD_ID = "lottery_api/models/biglotto_2bet_optimizer.py"
MODEL_V2_METHOD_ID = "lottery_api/models/biglotto_2bet_optimizer_v2.py"
GEMINI_2BET_METHOD_ID = "tools/verify_gemini_2bet_claim.py"
GEMINI_3BET_METHOD_ID = "tools/verify_gemini_3bet_claim.py"
SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS = (
    MODEL_V1_METHOD_ID,
    MODEL_V2_METHOD_ID,
    GEMINI_2BET_METHOD_ID,
    GEMINI_3BET_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    MODEL_V1_METHOD_ID: (
        "898ac9e38876841fb000796a3e9627dc339a19ad89babb23d7a2869da5db8e9c"
    ),
    MODEL_V2_METHOD_ID: (
        "783226366ac392dd441bbdfb89b873d3c7dd9eb4a231c0f2ccb0144de56798dd"
    ),
    GEMINI_2BET_METHOD_ID: (
        "d5ca233aa776d257c12b0f07e6d68205c5126b05759c39cf00e8ce8314062df3"
    ),
    GEMINI_3BET_METHOD_ID: (
        "05734b9e2afee57e9bfc3047a4cb3a79c9e4177c7bff38a13ed5a78c732fb978"
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
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    method_id: _SUPPORT
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    MODEL_V1_METHOD_ID: 1,
    MODEL_V2_METHOD_ID: 1,
    GEMINI_2BET_METHOD_ID: 50,
    GEMINI_3BET_METHOD_ID: 50,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    MODEL_V1_METHOD_ID: 2,
    MODEL_V2_METHOD_ID: 2,
    GEMINI_2BET_METHOD_ID: 2,
    GEMINI_3BET_METHOD_ID: 3,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    MODEL_V1_METHOD_ID: (
        "TWO_POSITIONAL_TOP12_WEIGHTED_CANDIDATE_SLICES_0_6_AND_3_9"
    ),
    MODEL_V2_METHOD_ID: (
        "TWO_POSITIONAL_TOP18_WEIGHTED_CANDIDATE_SLICES_0_6_AND_4_10"
    ),
    GEMINI_2BET_METHOD_ID: (
        "TWO_POSITIONAL_TOP12_WEIGHTED_CANDIDATE_SLICES_0_6_AND_3_9"
    ),
    GEMINI_3BET_METHOD_ID: (
        "THREE_POSITIONAL_TOP18_WEIGHTED_CANDIDATE_SLICES_0_6_4_10_8_14"
    ),
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    MODEL_V1_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.0",
    ),
    MODEL_V2_METHOD_ID: (
        "deviation_predict:weight_1.5",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.2",
        "bayesian_predict:weight_1.0",
        "frequency_predict:weight_1.0",
    ),
    GEMINI_2BET_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.0",
    ),
    GEMINI_3BET_METHOD_ID: (
        "deviation_predict:weight_2.0",
        "markov_predict:weight_1.5",
        "statistical_predict:weight_1.0",
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    method_id: len(members)
    for method_id, members in (
        SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE27_METHOD.items()
    )
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE27_METHOD: Final = {
    method_id: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_THE_"
        "STATISTICAL_PREDICT_CALL"
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS
}
EngineCache = Mapping[tuple[int, str], tuple[int, ...]]


class LegacySourceNativeWave27Error(ValueError):
    """A request cannot satisfy the twenty-seventh source-native contract."""


class LegacySourceNativeWave27SourceError(LegacySourceNativeWave27Error):
    """The frozen source emitted no valid native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave27Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE27_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave27Metadata:
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
    candidate_pool_size: int
    combination_count: int | None
    combination_members: tuple[str, ...]
    source_method_combination_count: int
    minimum_history_draws: int
    minimum_history_semantics: str
    insufficient_candidate_reason_code: str
    statistical_call_count: int
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave27Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave27Metadata


def _validate_request(request: LegacySourceNativeWave27Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS:
        raise LegacySourceNativeWave27Error(
            "unsupported frozen source-native wave-27 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave27Error(
            "invalid frozen source-native wave-27 request"
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
            raise LegacySourceNativeWave27Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave27Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE27_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def frozen_wave27_engine_output(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[int, ...]:
    """Return the exact frozen Unified main-number result."""

    if method_name == "deviation":
        return frozen_deviation_ticket(history)
    if method_name == "markov":
        return frozen_markov_ticket(history)[0]
    if method_name == "statistical":
        return frozen_statistical_ticket(history)[0]
    if method_name == "bayesian":
        return frozen_bayesian_ticket(history)
    if method_name == "frequency":
        return frozen_frequency_ticket(history)
    raise LegacySourceNativeWave27Error("unknown frozen Unified method")


def _engine_output(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> tuple[int, ...]:
    key = (len(history), method_name)
    if cache is not None and key in cache:
        return cache[key]
    return frozen_wave27_engine_output(method_name, history)


def _weighted_pool(
    history: tuple[LegacyHistoryDraw, ...],
    specifications: tuple[tuple[str, float], ...],
    cache: EngineCache | None,
    limit: int,
) -> list[int]:
    candidates: Counter[int] = Counter()
    for method_name, weight in specifications:
        try:
            for number in _engine_output(method_name, history, cache):
                candidates[number] += cast(int, weight)
        except Exception:
            continue
    return [number for number, _score in candidates.most_common(limit)]


def _configuration(
    method_id: str,
) -> tuple[
    tuple[tuple[str, float], ...],
    int,
    tuple[tuple[int, int], ...],
    int,
    str,
]:
    if method_id == MODEL_V2_METHOD_ID:
        return (
            (
                ("deviation", 1.5),
                ("markov", 1.5),
                ("statistical", 1.2),
                ("bayesian", 1.0),
                ("frequency", 1.0),
            ),
            18,
            ((0, 6), (4, 10)),
            10,
            "FROZEN_MODEL_ENTRYPOINT_HAS_NO_EXPLICIT_MINIMUM_HISTORY_GUARD",
        )
    if method_id == GEMINI_3BET_METHOD_ID:
        return (
            (
                ("deviation", 2.0),
                ("markov", 1.5),
                ("statistical", 1.0),
            ),
            18,
            ((0, 6), (4, 10), (8, 14)),
            14,
            "FROZEN_STRICT_ROLLING_BACKTEST_REQUIRES_50_PRIOR_DRAWS",
        )
    minimum_semantics = (
        "FROZEN_STRICT_ROLLING_BACKTEST_REQUIRES_50_PRIOR_DRAWS"
        if method_id == GEMINI_2BET_METHOD_ID
        else "FROZEN_MODEL_ENTRYPOINT_HAS_NO_EXPLICIT_MINIMUM_HISTORY_GUARD"
    )
    return (
        (
            ("deviation", 2.0),
            ("markov", 1.5),
            ("statistical", 1.0),
        ),
        12,
        ((0, 6), (3, 9)),
        9,
        minimum_semantics,
    )


def _tickets_or_close(
    *,
    pool: list[int],
    slices: tuple[tuple[int, int], ...],
    required_candidate_count: int,
    explicit_candidate_guard: bool,
) -> tuple[Ticket, ...]:
    if explicit_candidate_guard and len(pool) < required_candidate_count:
        raise LegacySourceNativeWave27SourceError(
            "FROZEN_SOURCE_CANDIDATE_POOL_BELOW_REQUIRED_SLICE"
        )
    tickets: list[Ticket] = []
    for start, end in slices:
        ticket = tuple(sorted(pool[start:end]))
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(not 1 <= number <= 49 for number in ticket)
        ):
            raise LegacySourceNativeWave27SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    return tuple(tickets)


def generate_legacy_source_native_wave27_portfolio(
    request: LegacySourceNativeWave27Request,
    *,
    engine_cache: EngineCache | None = None,
) -> LegacySourceNativeWave27Result:
    """Reproduce one frozen 2-bet or 3-bet weighted candidate portfolio."""

    _validate_request(request)
    method_id = request.legacy_method_id
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave27SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    (
        specifications,
        pool_limit,
        slices,
        required_candidate_count,
        minimum_semantics,
    ) = _configuration(method_id)
    candidate_pool = _weighted_pool(
        request.history,
        specifications,
        engine_cache,
        pool_limit,
    )
    tickets = _tickets_or_close(
        pool=candidate_pool,
        slices=slices,
        required_candidate_count=required_candidate_count,
        explicit_candidate_guard=method_id
        in (GEMINI_2BET_METHOD_ID, GEMINI_3BET_METHOD_ID),
    )
    expected_ticket_count = (
        NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
    )
    if len(tickets) != expected_ticket_count:
        raise LegacySourceNativeWave27SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave27Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave27Metadata(
            protocol=SOURCE_NATIVE_WAVE27_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_STATISTICAL_CALL_RESEEDS_FROM_CAUSAL_HISTORY_LENGTH"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            native_ticket_count=len(tickets),
            native_ticket_order="FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER",
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            candidate_k=None,
            candidate_pool=tuple(candidate_pool),
            candidate_pool_size=len(candidate_pool),
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ),
            minimum_history_draws=minimum,
            minimum_history_semantics=minimum_semantics,
            insufficient_candidate_reason_code=(
                "FROZEN_SOURCE_CANDIDATE_POOL_BELOW_REQUIRED_SLICE"
                if method_id
                in (GEMINI_2BET_METHOD_ID, GEMINI_3BET_METHOD_ID)
                else "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            ),
            statistical_call_count=1,
            tie_order_semantics=(
                "FROZEN_COUNTER_FIRST_INSERTION_ORDER_FOR_EQUAL_SCORES"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE27_METHOD[
                    method_id
                ]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE27_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "GEMINI_2BET_METHOD_ID",
    "GEMINI_3BET_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "MODEL_V1_METHOD_ID",
    "MODEL_V2_METHOD_ID",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "SOURCE_NATIVE_WAVE27_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS",
    "LegacySourceNativeWave27Error",
    "LegacySourceNativeWave27Metadata",
    "LegacySourceNativeWave27Request",
    "LegacySourceNativeWave27Result",
    "LegacySourceNativeWave27SourceError",
    "frozen_wave27_engine_output",
    "generate_legacy_source_native_wave27_portfolio",
]
