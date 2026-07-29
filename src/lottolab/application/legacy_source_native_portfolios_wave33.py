"""Faithful port of the thirty-third frozen BIG_LOTTO strategy batch."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

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

SOURCE_NATIVE_WAVE33_PROTOCOL = "legacy_source_native_wave33/v1"
DEFAULT_SOURCE_NATIVE_WAVE33_USER_SEED = (
    "biglotto-full-universe-source-native-wave33-v1"
)
FEASIBILITY_METHOD_ID = "tools/feasibility_benchmark_biglotto.py"
SUPPORTED_SOURCE_NATIVE_WAVE33_METHODS = (FEASIBILITY_METHOD_ID,)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: (
        "793823a0c3f88c29b274ae6c1f830026a82f84213d607932f77b6f27c21dcc66"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: (
        ("lottery_api/models/unified_predictor.py", FROZEN_UNIFIED_SOURCE_SHA256),
        (
            "lottery_api/common.py",
            "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
        ),
        ("lottery_api/config_loader.py", FROZEN_CONFIG_LOADER_SHA256),
        ("config/prediction_config.yaml", FROZEN_PREDICTION_CONFIG_SHA256),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: 1,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: 8,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: (
        "SIX_BENCHMARK_CONFIGURATIONS_FLATTENED_TO_EIGHT_POSITIONAL_TICKETS"
    ),
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: (
        "markov_single",
        "deviation_single",
        "statistical_single",
        "bayesian_single",
        "markov_plus_deviation_two_bet",
        "top12_markov_deviation_statistical_slicing_two_bet",
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: 6,
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: "OLDEST_FIRST",
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE33_METHOD: Final = {
    FEASIBILITY_METHOD_ID: (
        "DATABASE_NEWEST_FIRST_REVERSED_ONCE_THEN_STRICTLY_PRIOR_ROWS"
    ),
}


class LegacySourceNativeWave33Error(ValueError):
    """A request cannot satisfy the thirty-third source-native contract."""


class LegacySourceNativeWave33SourceError(LegacySourceNativeWave33Error):
    """The frozen source emitted no legal native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave33Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE33_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave33Metadata:
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
    statistical_candidate_count: int
    statistical_fallback_used: bool
    tie_order_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave33Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave33Metadata


def _validate_request(request: LegacySourceNativeWave33Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE33_METHODS:
        raise LegacySourceNativeWave33Error(
            "unsupported frozen source-native wave-33 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or len(request.history)
        < MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE33_METHOD[
            request.legacy_method_id
        ]
    ):
        raise LegacySourceNativeWave33Error(
            "invalid frozen source-native wave-33 request"
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
            raise LegacySourceNativeWave33Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave33Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE33_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _statistical(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, int, bool]:
    try:
        ticket, count = frozen_statistical_ticket(history)
        return ticket, count, False
    except ValueError as exc:
        if str(exc) != "FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED":
            raise
        return frozen_frequency_ticket(history), 0, True


def _ticket(values: tuple[int, ...]) -> Ticket:
    ticket = tuple(sorted(values))
    if (
        len(ticket) != 6
        or len(set(ticket)) != 6
        or any(not 1 <= number <= 49 for number in ticket)
    ):
        raise LegacySourceNativeWave33SourceError(
            "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
        )
    return ticket


def generate_legacy_source_native_wave33_portfolio(
    request: LegacySourceNativeWave33Request,
) -> LegacySourceNativeWave33Result:
    """Reproduce the frozen six-config feasibility portfolio."""

    _validate_request(request)
    history = request.history
    markov = frozen_markov_ticket(history)[0]
    deviation = frozen_deviation_ticket(history)
    statistical, statistical_count, fallback = _statistical(history)
    bayesian = frozen_bayesian_ticket(history)
    scores: Counter[int] = Counter()
    for source_ticket in (markov, deviation, statistical):
        for number in source_ticket:
            scores[number] += 1
    top12 = tuple(
        number for number, _score in scores.most_common(12)
    )
    tickets = (
        markov,
        deviation,
        statistical,
        bayesian,
        markov,
        deviation,
        _ticket(top12[:6]),
        _ticket(top12[6:12]),
    )
    if (
        len(tickets)
        != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD[
            request.legacy_method_id
        ]
    ):
        raise LegacySourceNativeWave33SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    material, digest, seed_integer = _seed(request)
    return LegacySourceNativeWave33Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave33Metadata(
            protocol=SOURCE_NATIVE_WAVE33_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD[
                request.legacy_method_id
            ],
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=material,
            seed_digest=digest,
            seed_integer=seed_integer,
            random_protocol=(
                "WRAPPER_RANDOM_AND_NUMPY_SEED_42_BEFORE_EACH_BENCHMARK_"
                "WITH_STATISTICAL_RANDOM_RESEEDED_BY_HISTORY_LENGTH"
            ),
            randomness_used=True,
            history_draw_count=len(history),
            history_first_draw_number=history[0].draw_number,
            history_cutoff_draw_number=history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE33_METHOD[
                    request.legacy_method_id
                ]
            ),
            candidate_k=None,
            candidate_pools=(top12,),
            native_ticket_count=len(tickets),
            native_ticket_order=(
                "MARKOV_DEVIATION_STATISTICAL_BAYESIAN_THEN_MARKOV_"
                "DEVIATION_THEN_TOP12_SLICE_0_6_AND_6_12"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE33_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD[
                    request.legacy_method_id
                ]
            ),
            statistical_candidate_count=statistical_count,
            statistical_fallback_used=fallback,
            tie_order_semantics=(
                "COUNTER_FIRST_INSERTION_MARKOV_THEN_DEVIATION_THEN_"
                "STATISTICAL"
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE33_METHOD[
                    request.legacy_method_id
                ]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE33_USER_SEED",
    "FEASIBILITY_METHOD_ID",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "SOURCE_NATIVE_WAVE33_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE33_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE33_METHODS",
    "LegacySourceNativeWave33Error",
    "LegacySourceNativeWave33Metadata",
    "LegacySourceNativeWave33Request",
    "LegacySourceNativeWave33Result",
    "LegacySourceNativeWave33SourceError",
    "generate_legacy_source_native_wave33_portfolio",
]
