"""Frozen-runtime source-grid portfolio reproduction for BIG_LOTTO wave 47."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE47_PROTOCOL = "legacy_source_grid_native_wave47/v1"
DEFAULT_SOURCE_NATIVE_WAVE47_USER_SEED = "biglotto-full-universe-source-grid-native-wave47-v1"
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_FFTPACK_POCKETFFT"
LEDGER_RESOURCE_NAME = "biglotto_source_grid_wave47_ticket_ledger_v1.json"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE47_TICKET_LEDGER_V1"
LEDGER_FILE_SHA256 = "0cc9d97e5a647c6f60da5612636b39f05b06a9f98c2b53286ef3eb595b0e07df"
LEDGER_CONTENT_SHA256 = "e16399eb618b29eb0cbde3d4ee9e51e493f661cbb472e7470c112a1b3348072e"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
MODEL_CANDIDATE_K = 49

EDGE_SPLICER_METHOD_ID = "tools/edge_splicer.py"
EDGE_SPLICER_5BET_METHOD_ID = "tools/edge_splicer_5bet.py"
EDGE_SPLICER_V2_METHOD_ID = "tools/edge_splicer_v2.py"
CONCENTRATOR_METHOD_ID = "tools/evaluate_concentrator.py"
ORTHOGONAL_2_3_METHOD_ID = "tools/generate_2_3_bets.py"
STABILITY_ALIAS_METHOD_ID = "tools/stability_coverage_study.py"
STANDARD_TS3_METHOD_ID = "tools/standard_ts3_5bet.py"
QUICK_PREDICT_METHOD_ID = "tools/quick_predict.py"
STABILITY_ALIAS_TARGET_METHOD_ID = "tools/backtest_big_lotto_orthogonal_5bet.py"

SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS = (
    EDGE_SPLICER_METHOD_ID,
    EDGE_SPLICER_5BET_METHOD_ID,
    EDGE_SPLICER_V2_METHOD_ID,
    CONCENTRATOR_METHOD_ID,
    ORTHOGONAL_2_3_METHOD_ID,
    STANDARD_TS3_METHOD_ID,
    QUICK_PREDICT_METHOD_ID,
)
AUDITED_SOURCE_NATIVE_WAVE47_METHODS = (
    EDGE_SPLICER_METHOD_ID,
    EDGE_SPLICER_5BET_METHOD_ID,
    EDGE_SPLICER_V2_METHOD_ID,
    CONCENTRATOR_METHOD_ID,
    ORTHOGONAL_2_3_METHOD_ID,
    STABILITY_ALIAS_METHOD_ID,
    STANDARD_TS3_METHOD_ID,
    QUICK_PREDICT_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        EDGE_SPLICER_METHOD_ID: (
            "04d9e8bbfe76f16be95e0a1f4e016913fb29c69add18313eeaca9a378d51c58c"
        ),
        EDGE_SPLICER_5BET_METHOD_ID: (
            "da1d1eed4d966323a9570a75ea334983e912bf90ace978f6ad112db53951d479"
        ),
        EDGE_SPLICER_V2_METHOD_ID: (
            "6b6e9d64da1253762c5fa22eb8a4f815bf4c3e058b952c2a05a2a9654782bf00"
        ),
        CONCENTRATOR_METHOD_ID: (
            "d732e4dd594c9f19aff5dea2292711d33a4bb6e7c3acd0a4ecd9fc5aba302970"
        ),
        ORTHOGONAL_2_3_METHOD_ID: (
            "f8853b95f3c53bd25e0af0a6ddd5060046ac457faeba523d8ff68eff25af1000"
        ),
        STABILITY_ALIAS_METHOD_ID: (
            "71ce29834518d6d3af3375cd4dd2452d1b67da95b43f807a194cc1bd0e8013ba"
        ),
        STANDARD_TS3_METHOD_ID: (
            "527fed00a7c4d47bbd286dfce905ca278c471cacaadf4e8e93ab3f693425db74"
        ),
        QUICK_PREDICT_METHOD_ID: (
            "86259fc99c70862b8d7730280bdccf4f37c24d9a951d67501ff188a8af3c3344"
        ),
    }
)
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        EDGE_SPLICER_METHOD_ID: 649,
        EDGE_SPLICER_5BET_METHOD_ID: 649,
        EDGE_SPLICER_V2_METHOD_ID: 649,
        CONCENTRATOR_METHOD_ID: 649,
        ORTHOGONAL_2_3_METHOD_ID: 1,
        STABILITY_ALIAS_METHOD_ID: 500,
        STANDARD_TS3_METHOD_ID: 649,
        QUICK_PREDICT_METHOD_ID: 50,
    }
)
MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        EDGE_SPLICER_METHOD_ID: ("PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY"),
        EDGE_SPLICER_5BET_METHOD_ID: ("PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY"),
        EDGE_SPLICER_V2_METHOD_ID: ("PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY"),
        CONCENTRATOR_METHOD_ID: ("PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY"),
        ORTHOGONAL_2_3_METHOD_ID: ("SOURCE_GENERATOR_DEFINED_WITH_ONE_PRIOR_DRAW"),
        STABILITY_ALIAS_METHOD_ID: "SOURCE_MIN_BUFFER_500",
        STANDARD_TS3_METHOD_ID: ("PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY"),
        QUICK_PREDICT_METHOD_ID: ("SOURCE_CLI_REQUIRES_50_HISTORY_DRAWS"),
    }
)
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        EDGE_SPLICER_METHOD_ID: 5,
        EDGE_SPLICER_5BET_METHOD_ID: 5,
        EDGE_SPLICER_V2_METHOD_ID: 3,
        CONCENTRATOR_METHOD_ID: 2,
        ORTHOGONAL_2_3_METHOD_ID: 5,
        STABILITY_ALIAS_METHOD_ID: 5,
        STANDARD_TS3_METHOD_ID: 5,
        QUICK_PREDICT_METHOD_ID: 5,
    }
)
SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        EDGE_SPLICER_METHOD_ID: (
            "CUSTOM_ORTHOGONAL_2BET",
            "CUSTOM_ORTHOGONAL_3BET",
        ),
        EDGE_SPLICER_5BET_METHOD_ID: ("FIVE_ATOMIC_SIGNAL_ORTHOGONAL_MATRIX",),
        EDGE_SPLICER_V2_METHOD_ID: ("TRI_AXIS_ORTHOGONAL_MATRIX",),
        CONCENTRATOR_METHOD_ID: ("CO_OCCURRENCE_CONCENTRATED_2BET",),
        ORTHOGONAL_2_3_METHOD_ID: (
            "ORTHOGONAL_SNAKE_DRAFT_2BET",
            "ORTHOGONAL_SNAKE_DRAFT_3BET",
        ),
        STABILITY_ALIAS_METHOD_ID: ("BIG_LOTTO_TS3_MARKOV_FREQ_ORTHO_5BET",),
        STANDARD_TS3_METHOD_ID: ("ORIGINAL_TS3_MARKOV_FREQ_ORTHO_5BET",),
        QUICK_PREDICT_METHOD_ID: ("DEFAULT_BIG_LOTTO_5BET_ORTHOGONAL",),
    }
)
SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        method_id: len(members)
        for method_id, members in (
            SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD.items()
        )
    }
)
SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {method_id: (49,) for method_id in AUDITED_SOURCE_NATIVE_WAVE47_METHODS}
)
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        method_id: (
            f"{NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]}_"
            "SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER"
        )
        for method_id in AUDITED_SOURCE_NATIVE_WAVE47_METHODS
    }
)
INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD: Final = MappingProxyType(
    {
        method_id: "SOURCE_ALREADY_SORTED_EACH_TICKET"
        for method_id in AUDITED_SOURCE_NATIVE_WAVE47_METHODS
    }
)


class LegacySourceGridNativeWave47Error(ValueError):
    """The request or packaged source-runtime ledger is invalid."""


class LegacySourceGridNativeWave47SourceError(LegacySourceGridNativeWave47Error):
    """A target cannot produce a source-valid wave-47 portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave47Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE47_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave47Metadata:
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
class LegacySourceGridNativeWave47Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceGridNativeWave47Metadata


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
        raise LegacySourceGridNativeWave47Error("packaged wave-47 ticket must be an array")
    values = cast(list[object], value)
    integers = cast(list[int], values) if all(type(number) is int for number in values) else []
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacySourceGridNativeWave47Error(
            "packaged wave-47 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    raw = files("lottolab.strategies.data").joinpath(LEDGER_RESOURCE_NAME).read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacySourceGridNativeWave47Error("packaged wave-47 ledger file SHA changed")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacySourceGridNativeWave47Error("packaged wave-47 ledger is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise LegacySourceGridNativeWave47Error("packaged wave-47 ledger must be an object")
    document = cast(dict[str, Any], parsed)
    claimed_content_sha256 = document.pop("ledger_content_sha256", None)
    expected_members = {
        method_id: list(members)
        for method_id, members in (
            SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD.items()
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
        != dict(MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD)
        or document.get("minimum_history_rationale_by_method")
        != dict(MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD)
        or document.get("source_sha256_by_method")
        != dict(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD)
        or document.get("source_configuration_count_by_method")
        != dict(SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD)
        or document.get("source_configuration_members_by_method") != expected_members
    ):
        raise LegacySourceGridNativeWave47Error("packaged wave-47 ledger identity changed")
    targets_raw = document.get("target_draw_numbers")
    contexts_raw = document.get("context_numbers_sha256_by_target")
    tickets_raw = document.get("tickets_by_method")
    if (
        not isinstance(targets_raw, list)
        or not isinstance(contexts_raw, list)
        or not isinstance(tickets_raw, dict)
    ):
        raise LegacySourceGridNativeWave47Error("packaged wave-47 ledger layout changed")
    targets = cast(list[object], targets_raw)
    contexts = cast(list[object], contexts_raw)
    if (
        len(targets) != 2148
        or len(contexts) != 2148
        or len(set(targets)) != 2148
        or any(type(item) is not str or not item for item in targets)
        or any(
            type(item) is not str
            or len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
            for item in contexts
        )
    ):
        raise LegacySourceGridNativeWave47Error("packaged wave-47 target sequence changed")
    typed_targets = cast(tuple[str, ...], tuple(targets))
    typed_tickets = cast(dict[str, object], tickets_raw)
    if set(typed_tickets) != set(AUDITED_SOURCE_NATIVE_WAVE47_METHODS):
        raise LegacySourceGridNativeWave47Error("packaged wave-47 method set changed")
    by_method: dict[str, tuple[tuple[Ticket, ...] | None, ...]] = {}
    for method_id in AUDITED_SOURCE_NATIVE_WAVE47_METHODS:
        raw_sequence = typed_tickets[method_id]
        if not isinstance(raw_sequence, list):
            raise LegacySourceGridNativeWave47Error("packaged wave-47 method sequence changed")
        sequence: list[tuple[Ticket, ...] | None] = []
        for candidate in cast(list[object], raw_sequence):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise LegacySourceGridNativeWave47Error("packaged wave-47 portfolio changed")
            portfolio = tuple(_ticket(ticket) for ticket in cast(list[object], candidate))
            if len(portfolio) != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]:
                raise LegacySourceGridNativeWave47Error(
                    "packaged wave-47 native ticket count changed"
                )
            sequence.append(portfolio)
        if len(sequence) != len(typed_targets):
            raise LegacySourceGridNativeWave47Error("packaged wave-47 target alignment changed")
        by_method[method_id] = tuple(sequence)
    return _Ledger(
        targets=typed_targets,
        target_index_by_number=MappingProxyType(
            {draw_number: index for index, draw_number in enumerate(typed_targets)}
        ),
        context_sha256=cast(tuple[str, ...], tuple(contexts)),
        tickets_by_method=MappingProxyType(by_method),
    )


def load_legacy_source_grid_native_wave47_ledger_for_verification() -> _Ledger:
    """Expose the immutable checksummed ledger to contract tests."""

    return _load_ledger()


def _validate_request(request: LegacySourceGridNativeWave47Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS:
        raise LegacySourceGridNativeWave47Error(
            "legacy method is outside the executable wave-47 batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.dataset_sha256) is not str or not request.dataset_sha256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacySourceGridNativeWave47Error("invalid frozen source-grid request identity")
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD[request.legacy_method_id]
    if len(request.history) < minimum:
        raise LegacySourceGridNativeWave47SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacySourceGridNativeWave47Error("causal history draw identities are invalid")
        _ticket(list(draw.numbers))
        seen.add(draw.draw_number)


def _context_sha256(history: tuple[LegacyHistoryDraw, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            [list(draw.numbers) for draw in history],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def generate_legacy_source_grid_native_wave47_portfolio(
    request: LegacySourceGridNativeWave47Request,
) -> LegacySourceGridNativeWave47Result:
    """Return the exact positional portfolio for one causal target."""

    _validate_request(request)
    ledger = _load_ledger()
    try:
        target_index = ledger.target_index_by_number[request.target_draw_number]
    except KeyError as exc:
        raise LegacySourceGridNativeWave47SourceError(
            "TARGET_OUTSIDE_FROZEN_SOURCE_GRID_TICKET_LEDGER"
        ) from exc
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacySourceGridNativeWave47SourceError("FROZEN_SOURCE_CONTEXT_IDENTITY_MISMATCH")
    tickets = ledger.tickets_by_method[request.legacy_method_id][target_index]
    if tickets is None:
        raise LegacySourceGridNativeWave47SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    method_id = request.legacy_method_id
    seed_material = "|".join(
        (
            SOURCE_NATIVE_WAVE47_PROTOCOL,
            method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    seed_digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    return LegacySourceGridNativeWave47Result(
        tickets=tickets,
        metadata=LegacySourceGridNativeWave47Metadata(
            protocol=SOURCE_NATIVE_WAVE47_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=int(seed_digest, 16),
            random_protocol="NONE_DETERMINISTIC_FROZEN_SOURCE",
            randomness_used=False,
            randomness_reproduction="NOT_APPLICABLE",
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            source_history_order_detail=(
                "DATABASE_NEWEST_FIRST_REVERSED_ONCE_THEN_FULL_STRICT_PREFIX_BEFORE_TARGET"
            ),
            source_minimum_history_draws=(
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
            ),
            source_minimum_history_rationale=(
                MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            candidate_k=None,
            source_candidate_k_values=(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
            ),
            native_ticket_order=("FROZEN_SOURCE_CONFIGURATION_THEN_POSITIONAL_BET_ORDER"),
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            combination_count=None,
            source_method_combination_count=(
                SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
            ),
            combination_members=(
                SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
            ),
            intra_ticket_order_semantics=(
                INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
            ),
            source_reference_runtime=SOURCE_REFERENCE_RUNTIME,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
            ledger_file_sha256=LEDGER_FILE_SHA256,
            ledger_content_sha256=LEDGER_CONTENT_SHA256,
            ledger_target_index=target_index,
        ),
    )


__all__ = [
    "AUDITED_SOURCE_NATIVE_WAVE47_METHODS",
    "CONCENTRATOR_METHOD_ID",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE47_USER_SEED",
    "EDGE_SPLICER_5BET_METHOD_ID",
    "EDGE_SPLICER_METHOD_ID",
    "EDGE_SPLICER_V2_METHOD_ID",
    "FROZEN_SOURCE_COMMIT",
    "INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "ORTHOGONAL_2_3_METHOD_ID",
    "PINNED_DATASET_SHA256",
    "QUICK_PREDICT_METHOD_ID",
    "SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "SOURCE_NATIVE_WAVE47_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD",
    "STABILITY_ALIAS_METHOD_ID",
    "STABILITY_ALIAS_TARGET_METHOD_ID",
    "STANDARD_TS3_METHOD_ID",
    "SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS",
    "LegacySourceGridNativeWave47Error",
    "LegacySourceGridNativeWave47Metadata",
    "LegacySourceGridNativeWave47Request",
    "LegacySourceGridNativeWave47Result",
    "LegacySourceGridNativeWave47SourceError",
    "generate_legacy_source_grid_native_wave47_portfolio",
    "load_legacy_source_grid_native_wave47_ledger_for_verification",
]
