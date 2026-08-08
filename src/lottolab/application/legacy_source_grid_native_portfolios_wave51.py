"""Frozen-runtime source-grid portfolio reproduction for BIG_LOTTO wave 51."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final, cast

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE51_PROTOCOL = "legacy_source_grid_native_wave51/v1"
DEFAULT_SOURCE_NATIVE_WAVE51_USER_SEED = (
    "biglotto-full-universe-source-grid-native-wave51-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_MT19937"
LEDGER_RESOURCE_NAME = "biglotto_source_grid_wave51_ticket_ledger_v1.json"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE51_TICKET_LEDGER_V1"
LEDGER_FILE_SHA256 = "626a4f8d1e779e48fe3411023da68ef2b25b4cfbe538d0e93b470273c554c4a0"
LEDGER_CONTENT_SHA256 = "5faa258c2f0d24213be5c2f98f3ef505c389844624a5322ff3deb16a04d2156c"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
MODEL_CANDIDATE_K = 49

CLUSTER_METHOD_ID = "tools/optimize_biglotto_cluster.py"
DEVIATION_METHOD_ID = "tools/optimize_deviation_extreme_generic.py"
SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS = (
    CLUSTER_METHOD_ID,
    DEVIATION_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: (
            "b2a833918f9558a577c18a297e920d1eb9f50bb926795821bb65baa83d8ea675"
        ),
        DEVIATION_METHOD_ID: (
            "87e19bb3514af177077869bd8f5ca8ea0aed273584b4af8e577fa7fac11cdc31"
        ),
    }
)
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: 1999,
        DEVIATION_METHOD_ID: 1999,
    }
)
MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: "PINNED_LAST_150_SOURCE_EVALUATION_BOUNDARY",
        DEVIATION_METHOD_ID: "PINNED_LAST_150_SOURCE_EVALUATION_BOUNDARY",
    }
)
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: 4,
        DEVIATION_METHOD_ID: 1,
    }
)
SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: (
            "BIG_LOTTO_4BET_DYNAMIC_CLUSTER_COLD5_FILTER_GLOBAL_SEED42",
        ),
        DEVIATION_METHOD_ID: (
            "BIG_LOTTO_1BET_DEVIATION_EXTREME_500_CANDIDATES_GLOBAL_SEED42",
        ),
    }
)
SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        method_id: len(members)
        for method_id, members in (
            SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE51_METHOD.items()
        )
    }
)
SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {method_id: (49,) for method_id in SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS}
)
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        method_id: (
            f"{NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]}_"
            "SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER"
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS
    }
)
INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        method_id: "SOURCE_VALUES_CANONICALIZED_ASCENDING_WITHOUT_POSITIONAL_REORDER"
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS
    }
)
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: (
            "MODULE_GLOBAL_NUMPY_MT19937_SEED42_SEQUENTIAL_LAST150_TARGETS"
        ),
        DEVIATION_METHOD_ID: (
            "MODULE_GLOBAL_NUMPY_MT19937_SEED42_500_CANDIDATES_PER_TARGET_"
            "SEQUENTIAL_LAST150_TARGETS"
        ),
    }
)
RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: True,
        DEVIATION_METHOD_ID: True,
    }
)
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: "OLDEST_FIRST",
        DEVIATION_METHOD_ID: "RECENT_FIRST",
    }
)
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE51_METHOD: Final = MappingProxyType(
    {
        CLUSTER_METHOD_ID: (
            "SOURCE_DATE_ASC_THEN_STRICT_PREFIX_BEFORE_TARGET"
        ),
        DEVIATION_METHOD_ID: (
            "SOURCE_DATABASE_NEWEST_FIRST_THEN_I_PLUS_1_CAUSAL_SUFFIX_"
            "BEFORE_TARGET"
        ),
    }
)


class LegacySourceGridNativeWave51Error(ValueError):
    """The request or packaged source-runtime ledger is invalid."""


class LegacySourceGridNativeWave51SourceError(LegacySourceGridNativeWave51Error):
    """A target cannot produce a source-valid wave-51 portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave51Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE51_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave51Metadata:
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
    source_minimum_history_draws: int
    source_minimum_history_rationale: str
    context_draw_count: int
    context_numbers_sha256: str
    candidate_k: None
    source_candidate_k_values: tuple[int, ...]
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    source_method_combination_count: int
    combination_members: tuple[str, ...]
    intra_ticket_order_semantics: str
    source_reference_runtime: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave51Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceGridNativeWave51Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index_by_number: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    tickets_by_method: MappingProxyType[
        str,
        tuple[tuple[Ticket, ...] | None, ...],
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
        raise LegacySourceGridNativeWave51Error(
            "packaged wave-51 ticket must be an array"
        )
    numbers = cast(list[object], value)
    integers = (
        cast(list[int], numbers) if all(type(number) is int for number in numbers) else []
    )
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacySourceGridNativeWave51Error(
            "packaged wave-51 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    raw = files("lottolab.strategies.data").joinpath(LEDGER_RESOURCE_NAME).read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacySourceGridNativeWave51Error("packaged wave-51 ledger file SHA changed")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacySourceGridNativeWave51Error(
            "packaged wave-51 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacySourceGridNativeWave51Error(
            "packaged wave-51 ledger must be an object"
        )
    document = cast(dict[str, Any], parsed)
    claimed_content_sha256 = document.pop("ledger_content_sha256", None)
    expected_members = {
        method_id: list(members)
        for method_id, members in (
            SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE51_METHOD.items()
        )
    }
    if (
        claimed_content_sha256 != LEDGER_CONTENT_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest() != LEDGER_CONTENT_SHA256
        or document.get("ledger_schema_version") != LEDGER_SCHEMA_VERSION
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or document.get("context_policy") != CONTEXT_POLICY
        or document.get("minimum_history_by_method")
        != dict(MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE51_METHOD)
        or document.get("minimum_history_rationale_by_method")
        != dict(MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE51_METHOD)
        or document.get("source_sha256_by_method")
        != dict(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE51_METHOD)
        or document.get("source_configuration_count_by_method")
        != dict(SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD)
        or document.get("source_configuration_members_by_method") != expected_members
    ):
        raise LegacySourceGridNativeWave51Error(
            "packaged wave-51 ledger identity changed"
        )
    targets_raw = document.get("target_draw_numbers")
    contexts_raw = document.get("context_numbers_sha256_by_target")
    tickets_raw = document.get("tickets_by_method")
    if (
        not isinstance(targets_raw, list)
        or not isinstance(contexts_raw, list)
        or not isinstance(tickets_raw, dict)
    ):
        raise LegacySourceGridNativeWave51Error(
            "packaged wave-51 ledger layout changed"
        )
    targets = cast(list[object], targets_raw)
    contexts = cast(list[object], contexts_raw)
    if (
        len(targets) != 2148
        or len(contexts) != 2148
        or len(set(cast(list[str], targets))) != 2148
        or any(type(item) is not str or not item for item in targets)
        or any(
            type(item) is not str
            or len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
            for item in contexts
        )
    ):
        raise LegacySourceGridNativeWave51Error(
            "packaged wave-51 target sequence changed"
        )
    typed_tickets = cast(dict[str, object], tickets_raw)
    if set(typed_tickets) != set(SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS):
        raise LegacySourceGridNativeWave51Error("packaged wave-51 method set changed")
    by_method: dict[str, tuple[tuple[Ticket, ...] | None, ...]] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS:
        raw_sequence = typed_tickets[method_id]
        if not isinstance(raw_sequence, list):
            raise LegacySourceGridNativeWave51Error(
                "packaged wave-51 method sequence changed"
            )
        sequence: list[tuple[Ticket, ...] | None] = []
        for candidate in cast(list[object], raw_sequence):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise LegacySourceGridNativeWave51Error(
                    "packaged wave-51 portfolio changed"
                )
            portfolio = tuple(_ticket(ticket) for ticket in cast(list[object], candidate))
            if (
                len(portfolio)
                != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ):
                raise LegacySourceGridNativeWave51Error(
                    "packaged wave-51 native ticket count changed"
                )
            sequence.append(portfolio)
        if len(sequence) != 2148:
            raise LegacySourceGridNativeWave51Error(
                "packaged wave-51 target alignment changed"
            )
        by_method[method_id] = tuple(sequence)
    typed_targets = cast(tuple[str, ...], tuple(targets))
    return _Ledger(
        targets=typed_targets,
        target_index_by_number=MappingProxyType(
            {draw_number: index for index, draw_number in enumerate(typed_targets)}
        ),
        context_sha256=cast(tuple[str, ...], tuple(contexts)),
        tickets_by_method=MappingProxyType(by_method),
    )


def load_legacy_source_grid_native_wave51_ledger_for_verification() -> _Ledger:
    """Expose the immutable checksummed ledger to contract tests."""

    return _load_ledger()


def _validate_request(request: LegacySourceGridNativeWave51Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS:
        raise LegacySourceGridNativeWave51Error(
            "legacy method is outside the executable wave-51 batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or request.dataset_sha256 != PINNED_DATASET_SHA256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacySourceGridNativeWave51Error(
            "invalid frozen source-grid request identity"
        )
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE51_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceGridNativeWave51SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacySourceGridNativeWave51Error(
                "causal history draw identities are invalid"
            )
        _ticket(list(draw.numbers))
        seen.add(draw.draw_number)


def _context_sha256(history: tuple[LegacyHistoryDraw, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            [list(draw.numbers) for draw in history],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def generate_legacy_source_grid_native_wave51_portfolio(
    request: LegacySourceGridNativeWave51Request,
) -> LegacySourceGridNativeWave51Result:
    """Return the exact positional portfolio for one causal target."""

    _validate_request(request)
    ledger = _load_ledger()
    try:
        target_index = ledger.target_index_by_number[request.target_draw_number]
    except KeyError as exc:
        raise LegacySourceGridNativeWave51SourceError(
            "TARGET_OUTSIDE_FROZEN_SOURCE_GRID_TICKET_LEDGER"
        ) from exc
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacySourceGridNativeWave51SourceError(
            "FROZEN_SOURCE_CONTEXT_IDENTITY_MISMATCH"
        )
    tickets = ledger.tickets_by_method[request.legacy_method_id][target_index]
    if tickets is None:
        raise LegacySourceGridNativeWave51SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    method_id = request.legacy_method_id
    seed_material = "|".join(
        (
            SOURCE_NATIVE_WAVE51_PROTOCOL,
            method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    seed_digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    randomness_used = RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
    return LegacySourceGridNativeWave51Result(
        tickets=tickets,
        metadata=LegacySourceGridNativeWave51Metadata(
            protocol=SOURCE_NATIVE_WAVE51_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id],
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=int(seed_digest, 16),
            random_protocol=RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id],
            randomness_used=randomness_used,
            randomness_reproduction=(
                "EXACT_FROZEN_RUNTIME_LEDGER"
                if randomness_used
                else "NOT_APPLICABLE"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE51_METHOD[
                    method_id
                ]
            ),
            source_minimum_history_draws=(
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            source_minimum_history_rationale=(
                MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            candidate_k=None,
            source_candidate_k_values=(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            native_ticket_order=(
                "FROZEN_SOURCE_CONFIGURATION_THEN_POSITIONAL_BET_ORDER"
            ),
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            combination_count=None,
            source_method_combination_count=(
                SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            combination_members=(
                SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            intra_ticket_order_semantics=(
                INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE51_METHOD[method_id]
            ),
            source_reference_runtime=SOURCE_REFERENCE_RUNTIME,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
            ledger_file_sha256=LEDGER_FILE_SHA256,
            ledger_content_sha256=LEDGER_CONTENT_SHA256,
            ledger_target_index=target_index,
        ),
    )


__all__ = [
    "CLUSTER_METHOD_ID",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE51_USER_SEED",
    "DEVIATION_METHOD_ID",
    "FROZEN_SOURCE_COMMIT",
    "INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "PINNED_DATASET_SHA256",
    "RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "SOURCE_NATIVE_WAVE51_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE51_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE51_METHODS",
    "LegacySourceGridNativeWave51Error",
    "LegacySourceGridNativeWave51Metadata",
    "LegacySourceGridNativeWave51Request",
    "LegacySourceGridNativeWave51Result",
    "LegacySourceGridNativeWave51SourceError",
    "generate_legacy_source_grid_native_wave51_portfolio",
    "load_legacy_source_grid_native_wave51_ledger_for_verification",
]
