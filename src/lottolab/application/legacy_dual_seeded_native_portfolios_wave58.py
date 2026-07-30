"""Frozen enhanced-dual and seeded-v6 portfolio replay for wave 58."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE58_PROTOCOL = "legacy_dual_seeded_native_wave58/v1"
DEFAULT_SOURCE_NATIVE_WAVE58_USER_SEED = (
    "biglotto-full-universe-dual-seeded-native-wave58-v1"
)
ENHANCED_DUAL_METHOD_ID = (
    "lottery_api/models/enhanced_dual_bet_predictor.py"
)
SEEDED_V6_METHOD_ID = "tools/biglotto_diversified_ensemble_v6.py"
SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS = (
    ENHANCED_DUAL_METHOD_ID,
    SEEDED_V6_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = MappingProxyType(
    {
        ENHANCED_DUAL_METHOD_ID: (
            "d5b3de348d01164c2e0079ec207c1a590c44b935217f81dfc9d704a825e50957"
        ),
        SEEDED_V6_METHOD_ID: (
            "8caaac8fcb5d1976174e6def13bf01d47e0fb00edb6d555d838c662bb5daaf2d"
        ),
    }
)
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = (
    MappingProxyType(
        {
            ENHANCED_DUAL_METHOD_ID: (
                (
                    "lottery_api/common.py",
                    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
                ),
                (
                    "lottery_api/database.py",
                    "9fa60bd417050f630af1cbef059550d4ae4cfb7644dac20e0489a16a88b3478a",
                ),
                (
                    "lottery_api/models/negative_selector.py",
                    "e977d50bcf3600ca04f66c2bc296164dda6dd35d0be0ecfbb7a901d5a57d111c",
                ),
                (
                    "lottery_api/models/unified_predictor.py",
                    "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004",
                ),
            ),
            SEEDED_V6_METHOD_ID: (
                (
                    "lottery_api/common.py",
                    "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2",
                ),
                (
                    "lottery_api/database.py",
                    "9fa60bd417050f630af1cbef059550d4ae4cfb7644dac20e0489a16a88b3478a",
                ),
                (
                    "lottery_api/models/biglotto_graph.py",
                    "4b5129659aa19628bb9d361b28ba35b65fd79f769f4bf00718c0cb7f45d62e90",
                ),
                (
                    "lottery_api/models/unified_predictor.py",
                    "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004",
                ),
            ),
        }
    )
)
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = (
    MappingProxyType(
        {
            ENHANCED_DUAL_METHOD_ID: (
                "TWO_POSITIONAL_TICKETS_ZONE_BALANCE_W500_THEN_"
                "BAYESIAN_W300_WITH_NEGATIVE_EXCLUSION"
            ),
            SEEDED_V6_METHOD_ID: (
                "THREE_POSITIONAL_TICKETS_CONSENSUS_GRAPH_SYNERGY_"
                "THEN_TAIL_DISRUPTOR"
            ),
        }
    )
)
LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = (
    MappingProxyType(
        {
            ENHANCED_DUAL_METHOD_ID: (
                "BIG_LOTTO_DEFAULT_APPLY_EXCLUSION_TRUE"
            ),
            SEEDED_V6_METHOD_ID: (
                "DEFAULT_SEED_42_THREE_BET_CONFIGURATION"
            ),
        }
    )
)
IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = (
    MappingProxyType(
        {
            ENHANCED_DUAL_METHOD_ID: (),
            SEEDED_V6_METHOD_ID: (),
        }
    )
)
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = (
    MappingProxyType(
        {
            ENHANCED_DUAL_METHOD_ID: 2,
            SEEDED_V6_METHOD_ID: 3,
        }
    )
)
MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = (
    MappingProxyType(
        {
            ENHANCED_DUAL_METHOD_ID: 100,
            SEEDED_V6_METHOD_ID: 1,
        }
    )
)
SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = (
    MappingProxyType(
        {
            ENHANCED_DUAL_METHOD_ID: (49,),
            SEEDED_V6_METHOD_ID: (12, 20, 49),
        }
    )
)
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = MappingProxyType(
    {
        ENHANCED_DUAL_METHOD_ID: (
            "DETERMINISTIC_ZONE_BAYESIAN_AND_NEGATIVE_EXCLUSION_NO_RNG"
        ),
        SEEDED_V6_METHOD_ID: (
            "PYTHON_RANDOM_AND_NUMPY_RANDOM_RESET_TO_42_AT_EACH_"
            "PREDICT_3BETS_CALL"
        ),
    }
)
RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE58_METHOD: Final = MappingProxyType(
    {
        ENHANCED_DUAL_METHOD_ID: False,
        SEEDED_V6_METHOD_ID: True,
    }
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_RESOURCE_NAME = (
    "biglotto_dual_seeded_wave58_ticket_ledger_v1.json"
)
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_DUAL_SEEDED_WAVE58_TICKET_LEDGER_V1"
)
LEDGER_FILE_SHA256 = (
    "3070f69175c806674547111c54b8109d94ec57c8b34a78b1082f4e34adbabe01"
)
LEDGER_CONTENT_SHA256 = (
    "c104cd26281dd1786a0dc037eab2ceff2f4a1ac5f4c237b6be723c724637fa44"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_NETWORKX_3_2_1_"
    "ENHANCED_DUAL_DETERMINISTIC_AND_V6_RANDOM_SEED_42_PER_TARGET"
)
MODEL_CANDIDATE_K = 49
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_THE_FULL_STRICTLY_EARLIER_DRAW_PREFIX"
)
INSUFFICIENT_HISTORY_REASON = (
    "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
)


class LegacyDualSeededNativeWave58Error(ValueError):
    """A request or packaged wave-58 ledger violates its contract."""


class LegacyDualSeededNativeWave58SourceError(
    LegacyDualSeededNativeWave58Error
):
    """The requested target has no executable frozen source output."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyDualSeededNativeWave58Request:
    legacy_method_id: str
    target_draw_number: str
    target_draw_date: date
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE58_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyDualSeededNativeWave58Metadata:
    protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    target_draw_date: str
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
    context_draw_count: int
    context_numbers_sha256: str
    minimum_history_draws: int
    source_candidate_k_values: tuple[int, ...]
    candidate_k: None
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    local_source_configuration: str
    imported_comparators_excluded: tuple[str, ...]
    causal_eligibility_rule: str
    source_reference_runtime: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyDualSeededNativeWave58Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyDualSeededNativeWave58Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    context_sha256: tuple[str, ...]
    tickets_by_method: MappingProxyType[
        str, tuple[tuple[Ticket, ...] | None, ...]
    ]
    closed_reason_by_method: MappingProxyType[
        str, tuple[str | None, ...]
    ]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _ticket(value: object) -> Ticket:
    if not isinstance(value, list):
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 ticket must be an array"
        )
    values = cast(list[object], value)
    integers = (
        cast(list[int], values)
        if all(type(number) is int for number in values)
        else []
    )
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    resource = files("lottolab.strategies.data").joinpath(
        LEDGER_RESOURCE_NAME
    )
    raw = resource.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 ledger must be an object"
        )
    document = cast(dict[str, Any], parsed)
    claimed_content_sha256 = document.pop("ledger_content_sha256", None)
    if (
        claimed_content_sha256 != LEDGER_CONTENT_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != LEDGER_CONTENT_SHA256
        or document.get("ledger_schema_version")
        != LEDGER_SCHEMA_VERSION
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("causal_eligibility_rule")
        != CAUSAL_ELIGIBILITY_RULE
        or document.get("context_policy") != CONTEXT_POLICY
        or document.get("minimum_history_draws_by_method")
        != dict(MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD)
        or document.get("native_ticket_count_by_method")
        != dict(NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD)
        or document.get("source_sha256_by_method")
        != dict(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD)
    ):
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 ledger identity changed"
        )
    targets_raw = document.get("target_draw_numbers")
    contexts_raw = document.get("context_numbers_sha256_by_target")
    tickets_raw = document.get("tickets_by_method")
    reasons_raw = document.get("closed_reason_by_method")
    if (
        not isinstance(targets_raw, list)
        or not isinstance(contexts_raw, list)
        or not isinstance(tickets_raw, dict)
        or not isinstance(reasons_raw, dict)
    ):
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 ledger layout changed"
        )
    targets = cast(list[object], targets_raw)
    contexts = cast(list[object], contexts_raw)
    if (
        len(targets) != 2149
        or len(contexts) != 2149
        or len(set(targets)) != 2149
        or any(type(item) is not str or not item for item in targets)
        or any(type(item) is not str or len(item) != 64 for item in contexts)
    ):
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 target sequence changed"
        )
    typed_tickets_raw = cast(dict[str, object], tickets_raw)
    typed_reasons_raw = cast(dict[str, object], reasons_raw)
    expected_methods = set(SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS)
    if (
        set(typed_tickets_raw) != expected_methods
        or set(typed_reasons_raw) != expected_methods
    ):
        raise LegacyDualSeededNativeWave58Error(
            "packaged wave-58 method set changed"
        )
    tickets_by_method: dict[
        str, tuple[tuple[Ticket, ...] | None, ...]
    ] = {}
    reasons_by_method: dict[str, tuple[str | None, ...]] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS:
        method_rows_raw = typed_tickets_raw[method_id]
        method_reasons_raw = typed_reasons_raw[method_id]
        if not isinstance(method_rows_raw, list) or not isinstance(
            method_reasons_raw, list
        ):
            raise LegacyDualSeededNativeWave58Error(
                "packaged wave-58 method sequence changed"
            )
        method_rows: list[tuple[Ticket, ...] | None] = []
        method_reasons: list[str | None] = []
        for index, (candidate, reason) in enumerate(
            zip(
                cast(list[object], method_rows_raw),
                cast(list[object], method_reasons_raw),
                strict=True,
            )
        ):
            if index < (
                MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    method_id
                ]
            ):
                if (
                    candidate is not None
                    or reason != INSUFFICIENT_HISTORY_REASON
                ):
                    raise LegacyDualSeededNativeWave58Error(
                        "packaged wave-58 closed prefix changed"
                    )
                method_rows.append(None)
                method_reasons.append(INSUFFICIENT_HISTORY_REASON)
                continue
            if reason is not None or not isinstance(candidate, list):
                raise LegacyDualSeededNativeWave58Error(
                    "packaged wave-58 executable row changed"
                )
            portfolio = tuple(
                _ticket(ticket)
                for ticket in cast(list[object], candidate)
            )
            if (
                len(portfolio)
                != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    method_id
                ]
            ):
                raise LegacyDualSeededNativeWave58Error(
                    "packaged wave-58 native count changed"
                )
            method_rows.append(portfolio)
            method_reasons.append(None)
        if len(method_rows) != 2149 or len(method_reasons) != 2149:
            raise LegacyDualSeededNativeWave58Error(
                "packaged wave-58 method target count changed"
            )
        tickets_by_method[method_id] = tuple(method_rows)
        reasons_by_method[method_id] = tuple(method_reasons)
    return _Ledger(
        targets=cast(tuple[str, ...], tuple(targets)),
        context_sha256=cast(tuple[str, ...], tuple(contexts)),
        tickets_by_method=MappingProxyType(tickets_by_method),
        closed_reason_by_method=MappingProxyType(reasons_by_method),
    )


def load_legacy_dual_seeded_native_wave58_ledger_for_verification() -> (
    _Ledger
):
    """Expose the immutable checksummed ledger to verification code."""

    return _load_ledger()


def _validate_request(
    request: LegacyDualSeededNativeWave58Request,
) -> None:
    if (
        request.legacy_method_id
        not in SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS
    ):
        raise LegacyDualSeededNativeWave58Error(
            "legacy method is outside the wave-58 batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.target_draw_date) is not date
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
        or request.dataset_sha256 != PINNED_DATASET_SHA256
    ):
        raise LegacyDualSeededNativeWave58Error(
            "invalid wave-58 request identity"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacyDualSeededNativeWave58Error(
                "causal history draw identities are invalid"
            )
        _ticket(list(draw.numbers))
        seen.add(draw.draw_number)


def _full_context_sha256(
    history: tuple[LegacyHistoryDraw, ...],
) -> str:
    return hashlib.sha256(
        json.dumps(
            [list(draw.numbers) for draw in history],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def generate_legacy_dual_seeded_native_wave58_portfolio(
    request: LegacyDualSeededNativeWave58Request,
) -> LegacyDualSeededNativeWave58Result:
    """Return exact frozen-runtime native tickets for one causal target."""

    _validate_request(request)
    ledger = _load_ledger()
    try:
        target_index = ledger.targets.index(request.target_draw_number)
    except ValueError as exc:
        raise LegacyDualSeededNativeWave58SourceError(
            "TARGET_OUTSIDE_FROZEN_WAVE58_TICKET_LEDGER"
        ) from exc
    context_sha256 = _full_context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacyDualSeededNativeWave58SourceError(
            "FROZEN_WAVE58_FULL_PREFIX_CONTEXT_MISMATCH"
        )
    tickets = ledger.tickets_by_method[
        request.legacy_method_id
    ][target_index]
    if tickets is None:
        reason = ledger.closed_reason_by_method[
            request.legacy_method_id
        ][target_index]
        raise LegacyDualSeededNativeWave58SourceError(
            reason or "FROZEN_WAVE58_CLOSED_WITHOUT_REASON"
        )
    if request.legacy_method_id == SEEDED_V6_METHOD_ID:
        seed_material = "random.seed(42);numpy.random.seed(42)"
        seed_integer = 42
    else:
        seed_material = "DETERMINISTIC_NO_RNG"
        seed_integer = 0
    seed_digest = hashlib.sha256(
        seed_material.encode("utf-8")
    ).hexdigest()
    return LegacyDualSeededNativeWave58Result(
        tickets=tickets,
        metadata=LegacyDualSeededNativeWave58Metadata(
            protocol=SOURCE_NATIVE_WAVE58_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            target_draw_date=request.target_draw_date.isoformat(),
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            randomness_used=(
                RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            randomness_reproduction=(
                "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="RECENT_FIRST",
            source_history_order_detail=(
                "DATABASE_LOGICAL_OLDEST_FIRST_STRICT_PREFIX_REVERSED_"
                "TO_SOURCE_RECENT_FIRST_BEFORE_PUBLIC_ENTRYPOINT"
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            minimum_history_draws=(
                MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_k_values=(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_SOURCE_POSITIONAL_ORDER_BEFORE_ORDERED_20"
            ),
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            combination_count=None,
            local_source_configuration=(
                LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            imported_comparators_excluded=(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
            causal_eligibility_rule=CAUSAL_ELIGIBILITY_RULE,
            source_reference_runtime=SOURCE_REFERENCE_RUNTIME,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
            ledger_file_sha256=LEDGER_FILE_SHA256,
            ledger_content_sha256=LEDGER_CONTENT_SHA256,
            ledger_target_index=target_index,
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE58_METHOD[
                    request.legacy_method_id
                ]
            ),
        ),
    )


__all__ = [
    "CAUSAL_ELIGIBILITY_RULE",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE58_USER_SEED",
    "ENHANCED_DUAL_METHOD_ID",
    "FROZEN_SOURCE_COMMIT",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "INSUFFICIENT_HISTORY_REASON",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "MINIMUM_HISTORY_DRAWS_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "PINNED_DATASET_SHA256",
    "RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "SEEDED_V6_METHOD_ID",
    "SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "SOURCE_NATIVE_WAVE58_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE58_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE58_METHODS",
    "LegacyDualSeededNativeWave58Error",
    "LegacyDualSeededNativeWave58Metadata",
    "LegacyDualSeededNativeWave58Request",
    "LegacyDualSeededNativeWave58Result",
    "LegacyDualSeededNativeWave58SourceError",
    "generate_legacy_dual_seeded_native_wave58_portfolio",
    "load_legacy_dual_seeded_native_wave58_ledger_for_verification",
]
