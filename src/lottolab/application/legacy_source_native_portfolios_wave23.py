"""Faithful ports of the twenty-third frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Final

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
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE23_PROTOCOL = "legacy_source_native_wave23/v1"
DEFAULT_SOURCE_NATIVE_WAVE23_USER_SEED = (
    "biglotto-full-universe-source-native-wave23-v1"
)
FIVE_ME_METHOD_ID = "tools/predict_5me_115000004.py"
TME_METHOD_ID = "tools/test_tme.py"
SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS = (
    FIVE_ME_METHOD_ID,
    TME_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: (
        "8a1c06ce1bddb2ab605ad00e95503d1f6bea35b102ad5c39559eb1cf4c5e5782"
    ),
    TME_METHOD_ID: (
        "f3bb5106dfe3f255bc84317169fb5fbafa653a97c2977b66cb12a49eab07891c"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: (
        (
            "lottery_api/models/unified_predictor.py",
            FROZEN_UNIFIED_SOURCE_SHA256,
        ),
        (
            "lottery_api/models/negative_selector.py",
            "e977d50bcf3600ca04f66c2bc296164dda6dd35d0be0ecfbb7a901d5a57d111c",
        ),
        (
            "lottery_api/common.py",
            "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
        ),
        (
            "lottery_api/config_loader.py",
            FROZEN_CONFIG_LOADER_SHA256,
        ),
        (
            "config/prediction_config.yaml",
            FROZEN_PREDICTION_CONFIG_SHA256,
        ),
    ),
    TME_METHOD_ID: (
        (
            "lottery_api/models/unified_predictor.py",
            FROZEN_UNIFIED_SOURCE_SHA256,
        ),
        (
            "lottery_api/models/biglotto_3bet_optimizer.py",
            "2835d6cb20c5351f636ef649b9b437f8b474cfad7bbd585aba3d08a95b18742a",
        ),
        (
            "tools/negative_selector.py",
            "80e79f80f9f5978ee2d7e71bb65e7b63bf101192a402ab8a9d0644796d4e3ff0",
        ),
        (
            "lottery_api/common.py",
            "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
        ),
        (
            "lottery_api/config_loader.py",
            FROZEN_CONFIG_LOADER_SHA256,
        ),
        (
            "config/prediction_config.yaml",
            FROZEN_PREDICTION_CONFIG_SHA256,
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: 1,
    TME_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: (
        "FIVE_POSITIONAL_UNIFIED_ENGINE_TICKETS_STATISTICAL_DEVIATION_"
        "MARKOV_HOT_COLD_THEN_TREND"
    ),
    TME_METHOD_ID: (
        "THREE_POSITIONAL_UNIFIED_ENGINE_TICKETS_STATISTICAL_DEVIATION_"
        "THEN_MARKOV"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_STATISTICAL"
    ),
    TME_METHOD_ID: (
        "PYTHON_RANDOM_SEED_EQUALS_CAUSAL_HISTORY_LENGTH_FOR_STATISTICAL"
    ),
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: None,
    TME_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: 5,
    TME_METHOD_ID: 3,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: (
        "statistical_predict:pinned_big_lotto_config",
        "deviation_predict:pinned_big_lotto_config",
        "markov_predict:adaptive_order_with_frozen_draw_string_order_check",
        "hot_cold_mix_predict:multi_window_temperature",
        "trend_predict:pinned_big_lotto_lambda_0.01",
    ),
    TME_METHOD_ID: (
        "statistical_predict:pinned_big_lotto_config",
        "deviation_predict:pinned_big_lotto_config",
        "markov_predict:adaptive_order_with_frozen_draw_string_order_check",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE23_METHOD: Final = {
    FIVE_ME_METHOD_ID: "OLDEST_FIRST",
    TME_METHOD_ID: "OLDEST_FIRST",
}


class LegacySourceNativeWave23Error(ValueError):
    """A request cannot satisfy the twenty-third source-native contract."""


class LegacySourceNativeWave23SourceError(
    LegacySourceNativeWave23Error
):
    """The frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave23Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE23_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave23Metadata:
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
    combination_count: int | None
    combination_members: tuple[str, ...]
    source_candidate_ticket_counts: tuple[int, ...]
    markov_order: int
    config_loader_runtime_semantics: str
    non_ticket_side_calculation_semantics: str
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave23Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave23Metadata


def _validate_request(request: LegacySourceNativeWave23Request) -> None:
    if (
        request.legacy_method_id
        not in SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS
    ):
        raise LegacySourceNativeWave23Error(
            "unsupported frozen source-native wave-23 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or not request.history
    ):
        raise LegacySourceNativeWave23Error(
            "invalid frozen source-native wave-23 request"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacySourceNativeWave23Error(
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
            raise LegacySourceNativeWave23Error(
                "causal history ticket is invalid"
            )


def _seed(
    request: LegacySourceNativeWave23Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE23_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def build_legacy_source_native_wave23_result(
    request: LegacySourceNativeWave23Request,
    unified: FrozenUnifiedTickets,
) -> LegacySourceNativeWave23Result:
    """Build method-specific native output from one shared frozen core run."""

    _validate_request(request)
    if request.legacy_method_id == FIVE_ME_METHOD_ID:
        tickets = unified.five_me
        non_ticket = (
            "MODEL_NEGATIVE_SELECTOR_KILL_10_CALCULATED_FOR_DISPLAY_ONLY_"
            "AFTER_TICKETS_AND_DOES_NOT_MUTATE_PORTFOLIO"
        )
    else:
        tickets = unified.tme
        non_ticket = (
            "TOOLS_NEGATIVE_SELECTOR_KILL_10_CALCULATED_BEFORE_TICKETS_"
            "BUT_LOCAL_KILL_NUMS_IS_UNUSED_AND_DOES_NOT_MUTATE_PORTFOLIO"
        )
    expected_count = SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE23_METHOD[
        request.legacy_method_id
    ]
    if len(tickets) != expected_count:
        raise LegacySourceNativeWave23SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    return LegacySourceNativeWave23Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave23Metadata(
            protocol=SOURCE_NATIVE_WAVE23_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE23_METHOD[
                    request.legacy_method_id
                ]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "FROZEN_SOURCE_RESEEDS_PYTHON_RANDOM_WITH_CAUSAL_HISTORY_"
                "LENGTH_INSIDE_STATISTICAL_PREDICT"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE23_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_count=len(tickets),
            native_ticket_order="FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER",
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            candidate_k=None,
            combination_count=None,
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE23_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=tuple(
                unified.statistical_candidate_count
                if position == 0
                else 1
                for position in range(len(tickets))
            ),
            markov_order=unified.markov_order,
            config_loader_runtime_semantics=(
                "PINNED_PREDICTION_CONFIG_BIG_LOTTO_TREND_LAMBDA_0_01_"
                "AND_STATISTICAL_OPTIMIZED_PARAMETERS"
            ),
            non_ticket_side_calculation_semantics=non_ticket,
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD[
                    request.legacy_method_id
                ]
            ),
        ),
    )


def generate_legacy_source_native_wave23_portfolio(
    request: LegacySourceNativeWave23Request,
) -> LegacySourceNativeWave23Result:
    """Reproduce one frozen 5ME or TME native portfolio."""

    _validate_request(request)
    try:
        unified = generate_frozen_unified_tickets(request.history)
    except ValueError as exc:
        raise LegacySourceNativeWave23SourceError(str(exc)) from exc
    return build_legacy_source_native_wave23_result(request, unified)


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE23_USER_SEED",
    "FIVE_ME_METHOD_ID",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "SOURCE_NATIVE_WAVE23_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE23_METHODS",
    "TME_METHOD_ID",
    "LegacySourceNativeWave23Error",
    "LegacySourceNativeWave23Metadata",
    "LegacySourceNativeWave23Request",
    "LegacySourceNativeWave23Result",
    "LegacySourceNativeWave23SourceError",
    "build_legacy_source_native_wave23_result",
    "generate_legacy_source_native_wave23_portfolio",
]
