"""Faithful port of the thirtieth frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
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
    frozen_hot_cold_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
    frozen_trend_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE30_PROTOCOL = "legacy_source_native_wave30/v1"
DEFAULT_SOURCE_NATIVE_WAVE30_USER_SEED = (
    "biglotto-full-universe-source-native-wave30-v1"
)
TEN_BET_METHOD_ID = "tools/backtest_10bet_biglotto.py"
SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS = (TEN_BET_METHOD_ID,)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: (
        "054e85b088bec0827318b2442255dee961fa3e9ca8b08b87cc2d5b4cfcb669f2"
    )
}
_COMMON_SHA256 = (
    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
)
_REQUIREMENTS_SHA256 = (
    "2046dd0aa9cc084352a2fb1a664e032fba23ac81f0b1e7d3f1d70ff9d1a1e130"
)
_SUPPORT = (
    ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
    ("lottery_api/common.py", _COMMON_SHA256),
    ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
    ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
    ("lottery_api/requirements.txt", _REQUIREMENTS_SHA256),
)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: _SUPPORT
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: 1
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: 10
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: (
        "SEVEN_UNIFIED_METHOD_TICKETS_THEN_THREE_SCALAR_EWMA_TREND_VARIANTS"
    )
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: (
        "markov_predict",
        "deviation_predict",
        "statistical_predict",
        "trend_predict",
        "frequency_predict",
        "bayesian_predict",
        "hot_cold_mix_predict",
        "ewma_scalar_exp:lambda_0.03",
        "ewma_scalar_exp:lambda_0.10",
        "ewma_scalar_exp:lambda_0.15",
    )
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    method_id: len(members)
    for method_id, members in (
        SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE30_METHOD.items()
    )
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: "OLDEST_FIRST"
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: (
        "DATABASE_GET_ALL_DRAWS_REVERSED_TO_ASCENDING_BEFORE_TARGET_LOOP"
    )
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE30_METHOD: Final = {
    TEN_BET_METHOD_ID: (
        "PYTHON_RANDOM_SEED_EQUALS_FULL_PREFIX_HISTORY_LENGTH_FOR_"
        "STATISTICAL_PREDICT_CALL"
    )
}
EngineCache = Mapping[str, tuple[int, ...]]


class LegacySourceNativeWave30Error(ValueError):
    """A request cannot satisfy the thirtieth source-native contract."""


class LegacySourceNativeWave30SourceError(LegacySourceNativeWave30Error):
    """The frozen source emitted no valid native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave30Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE30_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave30Metadata:
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
    source_engine_method_count: int
    source_ewma_variant_count: int
    source_ewma_lambdas: tuple[str, ...]
    numpy_version_pin: str
    numpy_scalar_exp_reproduction: str
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave30Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave30Metadata


def _validate_request(request: LegacySourceNativeWave30Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS:
        raise LegacySourceNativeWave30Error(
            "unsupported frozen source-native wave-30 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave30Error(
            "invalid frozen source-native wave-30 request"
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
            raise LegacySourceNativeWave30Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave30Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE30_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def frozen_wave30_engine_output(
    method_name: str,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[int, ...]:
    """Return one frozen Unified result for chronological history."""

    if method_name == "markov":
        return frozen_markov_ticket(history)[0]
    if method_name == "deviation":
        return frozen_deviation_ticket(history)
    if method_name == "statistical":
        return frozen_statistical_ticket(history)[0]
    if method_name == "trend":
        return frozen_trend_ticket(history)
    if method_name == "frequency":
        return frozen_frequency_ticket(history)
    if method_name == "bayesian":
        return frozen_bayesian_ticket(history)
    if method_name == "hot_cold_mix":
        return frozen_hot_cold_ticket(history)
    raise LegacySourceNativeWave30Error("unknown frozen Unified method")


def _ewma_ticket(
    history: tuple[LegacyHistoryDraw, ...],
    lambda_value: float,
) -> Ticket:
    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history)):
        for number in draw.numbers:
            weighted_frequency[number] += math.exp(-lambda_value * age)
    total = sum(weighted_frequency.values())
    probabilities = {
        number: weighted_frequency.get(number, 0.0) / total
        for number in range(1, 50)
    }
    ranked = sorted(
        probabilities,
        key=lambda number: probabilities[number],
        reverse=True,
    )
    return cast(Ticket, tuple(sorted(ranked[:6])))


def _source_rows(
    history: tuple[LegacyHistoryDraw, ...],
    cache: EngineCache | None,
) -> list[list[int]]:
    rows: list[list[int]] = []
    for method_name in (
        "markov",
        "deviation",
        "statistical",
        "trend",
        "frequency",
        "bayesian",
        "hot_cold_mix",
    ):
        try:
            numbers = (
                cache[method_name]
                if cache is not None and method_name in cache
                else frozen_wave30_engine_output(method_name, history)
            )
        except Exception:
            continue
        rows.append(list(numbers[:6]))
    for lambda_value in (0.03, 0.10, 0.15):
        rows.append(list(_ewma_ticket(history, lambda_value)))
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
            raise LegacySourceNativeWave30SourceError(
                "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
            )
        tickets.append(ticket)
    if not tickets:
        raise LegacySourceNativeWave30SourceError(
            "FROZEN_SOURCE_EMITTED_NO_NATIVE_TICKETS"
        )
    return tuple(tickets)


def generate_legacy_source_native_wave30_portfolio(
    request: LegacySourceNativeWave30Request,
    *,
    engine_cache: EngineCache | None = None,
) -> LegacySourceNativeWave30Result:
    """Reproduce the frozen chronological ten-ticket portfolio."""

    _validate_request(request)
    method_id = request.legacy_method_id
    tickets = _tickets_or_close(_source_rows(request.history, engine_cache))
    if len(tickets) != 10:
        raise LegacySourceNativeWave30SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave30Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave30Metadata(
            protocol=SOURCE_NATIVE_WAVE30_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE30_METHOD[method_id]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_STATISTICAL_CALL_RESEEDS_FROM_FULL_PREFIX_LENGTH"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE30_METHOD[
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
                "SEVEN_FROZEN_ENGINE_METHOD_POSITIONS_THEN_EWMA_"
                "LAMBDA_0.03_0.10_0.15"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            candidate_k=None,
            candidate_pool=(),
            candidate_pool_size=None,
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
            source_engine_method_count=7,
            source_ewma_variant_count=3,
            source_ewma_lambdas=("0.03", "0.10", "0.15"),
            numpy_version_pin="numpy==1.26.2",
            numpy_scalar_exp_reproduction=(
                "SCALAR_NUMPY_EXP_REPRODUCED_WITH_IEEE754_MATH_EXP"
            ),
            tie_order_semantics=(
                "FROZEN_METHOD_DECLARATION_ORDER_AND_STABLE_NUMBER_ASCENDING_"
                "TIES"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE30_METHOD[
                    method_id
                ]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE30_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "SOURCE_NATIVE_WAVE30_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE30_METHODS",
    "TEN_BET_METHOD_ID",
    "LegacySourceNativeWave30Error",
    "LegacySourceNativeWave30Metadata",
    "LegacySourceNativeWave30Request",
    "LegacySourceNativeWave30Result",
    "LegacySourceNativeWave30SourceError",
    "frozen_wave30_engine_output",
    "generate_legacy_source_native_wave30_portfolio",
]
