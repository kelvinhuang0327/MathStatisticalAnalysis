"""Frozen-runtime source-grid portfolio reproduction for BIG_LOTTO wave 49."""

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

SOURCE_NATIVE_WAVE49_PROTOCOL = "legacy_source_grid_native_wave49/v1"
DEFAULT_SOURCE_NATIVE_WAVE49_USER_SEED = "biglotto-full-universe-source-grid-native-wave49-v1"
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_FFTPACK_POCKETFFT"
LEDGER_RESOURCE_NAME = "biglotto_source_grid_wave49_ticket_ledger_v1.json"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE49_TICKET_LEDGER_V1"
LEDGER_FILE_SHA256 = "401a6abb2fef088c70c982c1ea4f466e98dfe6c030c9ee093d40ee4c8c018e05"
LEDGER_CONTENT_SHA256 = "fcc1883924238ecf5afc5ebb1216ce084371b4c01dbebc283e1c9961d975c0b8"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
MODEL_CANDIDATE_K = 49

AUTO_DISCOVERY_METHOD_ID = "tools/auto_discovery_biglotto.py"
EVALUATE_COMBINATIONS_METHOD_ID = "tools/evaluate_combinations.py"
FOURIER_RHYTHM_METHOD_ID = "tools/power_fourier_rhythm.py"

SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS = (
    AUTO_DISCOVERY_METHOD_ID,
    EVALUATE_COMBINATIONS_METHOD_ID,
    FOURIER_RHYTHM_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        AUTO_DISCOVERY_METHOD_ID: (
            "06bcb164db844857927366a5e0216387a56f490ae689c8114608fec84d5a4765"
        ),
        EVALUATE_COMBINATIONS_METHOD_ID: (
            "d49d0787d0c6fb9407024111d339cf76c4b165dc90d0713a0ac589929f9371a0"
        ),
        FOURIER_RHYTHM_METHOD_ID: (
            "cb75e72e4c948466a23a432527ca9e5af40e8618c509154f54277ac860d62d59"
        ),
    }
)
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        AUTO_DISCOVERY_METHOD_ID: 649,
        EVALUATE_COMBINATIONS_METHOD_ID: 649,
        FOURIER_RHYTHM_METHOD_ID: 500,
    }
)
MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        AUTO_DISCOVERY_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
        EVALUATE_COMBINATIONS_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
        FOURIER_RHYTHM_METHOD_ID: "SOURCE_FOURIER_WINDOW_500",
    }
)
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        AUTO_DISCOVERY_METHOD_ID: 54,
        EVALUATE_COMBINATIONS_METHOD_ID: 14,
        FOURIER_RHYTHM_METHOD_ID: 2,
    }
)
SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        AUTO_DISCOVERY_METHOD_ID: tuple(
            sorted(
                (
                    "A1_cooc_pairs_w30",
                    "A1_cooc_pairs_w50",
                    "A1_cooc_pairs_w100",
                    "A1_cooc_pairs_w200",
                    "A2_cooc_trans_w30",
                    "A2_cooc_trans_w50",
                    "A2_cooc_trans_w100",
                    "A3_cooc_anti_w50",
                    "A3_cooc_anti_w100",
                    "A3_cooc_anti_w200",
                    "A4_cooc_trip_w50",
                    "A4_cooc_trip_w100",
                    "A5_cooc_cond_w30",
                    "A5_cooc_cond_w50",
                    "A5_cooc_cond_w100",
                    "B1_struct_tmpl_w100",
                    "B1_struct_tmpl_w200",
                    "B1_struct_tmpl_w500",
                    "B2_struct_sum_w30",
                    "B2_struct_sum_w50",
                    "B2_struct_sum_w100",
                    "B3_struct_oe_w50",
                    "B3_struct_oe_w100",
                    "B3_struct_oe_w200",
                    "B4_struct_gap_w50",
                    "B4_struct_gap_w100",
                    "C1_cond_entropy_w50",
                    "C1_cond_entropy_w100",
                    "C1_cond_entropy_w200",
                    "C2_mutual_info_w50",
                    "C2_mutual_info_w100",
                    "C3_surprise_w50",
                    "C3_surprise_w100",
                    "D1_neg_elim_w30",
                    "D1_neg_elim_w50",
                    "D1_neg_elim_w100",
                    "D2_neg_overdue",
                    "D3_neg_consensus_w20",
                    "D3_neg_consensus_w30",
                    "D3_neg_consensus_w50",
                    "E1_zone_trans_w50",
                    "E1_zone_trans_w100",
                    "E1_zone_trans_w200",
                    "E2_zone_consec_w30",
                    "E2_zone_consec_w50",
                    "E2_zone_consec_w100",
                    "F1_graph_degree_w50",
                    "F1_graph_degree_w100",
                    "F1_graph_degree_w200",
                    "F2_graph_bridge_w50",
                    "F2_graph_bridge_w100",
                    "F3_graph_pagerank_w50",
                    "F3_graph_pagerank_w100",
                    "F3_graph_pagerank_w200",
                )
            )
        ),
        EVALUATE_COMBINATIONS_METHOD_ID: (
            "SIGNAL_PREFIX_2BET",
            "SIGNAL_PREFIX_3BET",
            "SIGNAL_PREFIX_4BET",
            "SIGNAL_PREFIX_5BET",
        ),
        FOURIER_RHYTHM_METHOD_ID: ("BIG_LOTTO_DEFAULT_2BET_FOURIER_WINDOW_500",),
    }
)
SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        method_id: len(members)
        for method_id, members in (
            SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE49_METHOD.items()
        )
    }
)
SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {method_id: (49,) for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS}
)
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        method_id: (
            f"{NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]}_"
            "SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER"
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS
    }
)
INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD: Final = MappingProxyType(
    {
        method_id: "SOURCE_ALREADY_SORTED_EACH_TICKET"
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS
    }
)


class LegacySourceGridNativeWave49Error(ValueError):
    """The request or packaged source-runtime ledger is invalid."""


class LegacySourceGridNativeWave49SourceError(LegacySourceGridNativeWave49Error):
    """A target cannot produce a source-valid wave-49 portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave49Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE49_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave49Metadata:
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
class LegacySourceGridNativeWave49Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceGridNativeWave49Metadata


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
        raise LegacySourceGridNativeWave49Error("packaged wave-49 ticket must be an array")
    numbers = cast(list[object], value)
    integers = cast(list[int], numbers) if all(type(number) is int for number in numbers) else []
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacySourceGridNativeWave49Error(
            "packaged wave-49 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    raw = files("lottolab.strategies.data").joinpath(LEDGER_RESOURCE_NAME).read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacySourceGridNativeWave49Error("packaged wave-49 ledger file SHA changed")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacySourceGridNativeWave49Error("packaged wave-49 ledger is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise LegacySourceGridNativeWave49Error("packaged wave-49 ledger must be an object")
    document = cast(dict[str, Any], parsed)
    claimed_content_sha256 = document.pop("ledger_content_sha256", None)
    expected_members = {
        method_id: list(members)
        for method_id, members in (
            SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE49_METHOD.items()
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
        != dict(MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD)
        or document.get("minimum_history_rationale_by_method")
        != dict(MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE49_METHOD)
        or document.get("source_sha256_by_method")
        != dict(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD)
        or document.get("source_configuration_count_by_method")
        != dict(SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD)
        or document.get("source_configuration_members_by_method") != expected_members
    ):
        raise LegacySourceGridNativeWave49Error("packaged wave-49 ledger identity changed")
    targets_raw = document.get("target_draw_numbers")
    contexts_raw = document.get("context_numbers_sha256_by_target")
    tickets_raw = document.get("tickets_by_method")
    if (
        not isinstance(targets_raw, list)
        or not isinstance(contexts_raw, list)
        or not isinstance(tickets_raw, dict)
    ):
        raise LegacySourceGridNativeWave49Error("packaged wave-49 ledger layout changed")
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
        raise LegacySourceGridNativeWave49Error("packaged wave-49 target sequence changed")
    typed_tickets = cast(dict[str, object], tickets_raw)
    if set(typed_tickets) != set(SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS):
        raise LegacySourceGridNativeWave49Error("packaged wave-49 method set changed")
    by_method: dict[str, tuple[tuple[Ticket, ...] | None, ...]] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS:
        raw_sequence = typed_tickets[method_id]
        if not isinstance(raw_sequence, list):
            raise LegacySourceGridNativeWave49Error("packaged wave-49 method sequence changed")
        sequence: list[tuple[Ticket, ...] | None] = []
        for candidate in cast(list[object], raw_sequence):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise LegacySourceGridNativeWave49Error("packaged wave-49 portfolio changed")
            portfolio = tuple(_ticket(ticket) for ticket in cast(list[object], candidate))
            if len(portfolio) != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]:
                raise LegacySourceGridNativeWave49Error(
                    "packaged wave-49 native ticket count changed"
                )
            sequence.append(portfolio)
        if len(sequence) != 2148:
            raise LegacySourceGridNativeWave49Error("packaged wave-49 target alignment changed")
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


def load_legacy_source_grid_native_wave49_ledger_for_verification() -> _Ledger:
    """Expose the immutable checksummed ledger to contract tests."""

    return _load_ledger()


def _validate_request(request: LegacySourceGridNativeWave49Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS:
        raise LegacySourceGridNativeWave49Error(
            "legacy method is outside the executable wave-49 batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.dataset_sha256) is not str or not request.dataset_sha256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacySourceGridNativeWave49Error("invalid frozen source-grid request identity")
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD[request.legacy_method_id]
    if len(request.history) < minimum:
        raise LegacySourceGridNativeWave49SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacySourceGridNativeWave49Error("causal history draw identities are invalid")
        _ticket(list(draw.numbers))
        seen.add(draw.draw_number)


def _context_sha256(history: tuple[LegacyHistoryDraw, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            [list(draw.numbers) for draw in history],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def generate_legacy_source_grid_native_wave49_portfolio(
    request: LegacySourceGridNativeWave49Request,
) -> LegacySourceGridNativeWave49Result:
    """Return the exact positional portfolio for one causal target."""

    _validate_request(request)
    ledger = _load_ledger()
    try:
        target_index = ledger.target_index_by_number[request.target_draw_number]
    except KeyError as exc:
        raise LegacySourceGridNativeWave49SourceError(
            "TARGET_OUTSIDE_FROZEN_SOURCE_GRID_TICKET_LEDGER"
        ) from exc
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacySourceGridNativeWave49SourceError("FROZEN_SOURCE_CONTEXT_IDENTITY_MISMATCH")
    tickets = ledger.tickets_by_method[request.legacy_method_id][target_index]
    if tickets is None:
        raise LegacySourceGridNativeWave49SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    method_id = request.legacy_method_id
    seed_material = "|".join(
        (
            SOURCE_NATIVE_WAVE49_PROTOCOL,
            method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    seed_digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    return LegacySourceGridNativeWave49Result(
        tickets=tickets,
        metadata=LegacySourceGridNativeWave49Metadata(
            protocol=SOURCE_NATIVE_WAVE49_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id],
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
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
            ),
            source_minimum_history_rationale=(
                MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            candidate_k=None,
            source_candidate_k_values=(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
            ),
            native_ticket_order="FROZEN_SOURCE_CONFIGURATION_THEN_POSITIONAL_BET_ORDER",
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            combination_count=None,
            source_method_combination_count=(
                SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
            ),
            combination_members=(
                SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
            ),
            intra_ticket_order_semantics=(
                INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD[method_id]
            ),
            source_reference_runtime=SOURCE_REFERENCE_RUNTIME,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
            ledger_file_sha256=LEDGER_FILE_SHA256,
            ledger_content_sha256=LEDGER_CONTENT_SHA256,
            ledger_target_index=target_index,
        ),
    )


__all__ = [
    "AUTO_DISCOVERY_METHOD_ID",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE49_USER_SEED",
    "EVALUATE_COMBINATIONS_METHOD_ID",
    "FOURIER_RHYTHM_METHOD_ID",
    "FROZEN_SOURCE_COMMIT",
    "INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "PINNED_DATASET_SHA256",
    "SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "SOURCE_NATIVE_WAVE49_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE49_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE49_METHODS",
    "LegacySourceGridNativeWave49Error",
    "LegacySourceGridNativeWave49Metadata",
    "LegacySourceGridNativeWave49Request",
    "LegacySourceGridNativeWave49Result",
    "LegacySourceGridNativeWave49SourceError",
    "generate_legacy_source_grid_native_wave49_portfolio",
    "load_legacy_source_grid_native_wave49_ledger_for_verification",
]
