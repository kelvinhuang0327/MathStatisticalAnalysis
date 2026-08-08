"""Frozen-runtime source-grid portfolio reproduction for BIG_LOTTO wave 46."""

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

SOURCE_NATIVE_WAVE46_PROTOCOL = "legacy_source_grid_native_wave46/v1"
DEFAULT_SOURCE_NATIVE_WAVE46_USER_SEED = (
    "biglotto-full-universe-source-grid-native-wave46-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_FFTPACK_POCKETFFT"
LEDGER_RESOURCE_NAME = "biglotto_source_grid_wave46_ticket_ledger_v1.json"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE46_TICKET_LEDGER_V1"
LEDGER_FILE_SHA256 = "fa7e629fe14c167cf1f7a188db91072bc31017204b18be767fa6d0e95f28cb02"
LEDGER_CONTENT_SHA256 = "a25bef088b8d31815a50565be6fe7e8a94ff3218327bfbfd2090fe959fdb9227"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
MODEL_CANDIDATE_K = 49

PORTFOLIO_OPTIMIZER_METHOD_ID = "ai_lab/automl_biglotto/portfolio_optimizer.py"
ORTHOGONAL_5BET_METHOD_ID = "tools/backtest_big_lotto_orthogonal_5bet.py"
SIX_BET_METHOD_ID = "tools/backtest_biglotto_6bet.py"
EWMA_SIX_BET_METHOD_ID = "tools/backtest_biglotto_6bet_ewma.py"
COLD_POOL_METHOD_ID = "tools/backtest_biglotto_coldpool_15.py"
MARKOV_4BET_METHOD_ID = "tools/backtest_biglotto_markov_4bet.py"
TRIPLE_STRIKE_V2_METHOD_ID = "tools/backtest_biglotto_triple_strike_v2.py"
MARKOV_REPEAT_METHOD_ID = "tools/backtest_markov_repeat_exception.py"
STRUCTURAL_GROUP_METHOD_ID = "tools/backtest_structural_group.py"
SUM_CONSTRAINT_METHOD_ID = "tools/backtest_sum_constraint.py"
OPTIMAL_MATRIX_METHOD_ID = "tools/optimal_2bet_3bet_matrix.py"
QUAD_STRIKE_METHOD_ID = "tools/predict_biglotto_quad_strike.py"
PREDICTABILITY_ALIAS_METHOD_ID = "tools/predictability_engine.py"

SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS = (
    PORTFOLIO_OPTIMIZER_METHOD_ID,
    ORTHOGONAL_5BET_METHOD_ID,
    SIX_BET_METHOD_ID,
    EWMA_SIX_BET_METHOD_ID,
    COLD_POOL_METHOD_ID,
    MARKOV_4BET_METHOD_ID,
    TRIPLE_STRIKE_V2_METHOD_ID,
    MARKOV_REPEAT_METHOD_ID,
    STRUCTURAL_GROUP_METHOD_ID,
    SUM_CONSTRAINT_METHOD_ID,
    OPTIMAL_MATRIX_METHOD_ID,
    QUAD_STRIKE_METHOD_ID,
)
AUDITED_SOURCE_NATIVE_WAVE46_METHODS = (
    *SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS,
    PREDICTABILITY_ALIAS_METHOD_ID,
)

SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        PORTFOLIO_OPTIMIZER_METHOD_ID: (
            "1a6efc7959b61fc400c037fe62fd143cfa2ad33d70c59f799326f1f196f55719"
        ),
        ORTHOGONAL_5BET_METHOD_ID: (
            "c4dff46c5a5eff0621cdfba64a623c0a36ad365a4912355b90d3a9ad1c8a0df0"
        ),
        SIX_BET_METHOD_ID: (
            "f5d8c03421d2be5f093233335d5fc28d7409eed54d203c788c4b9d46e53b1410"
        ),
        EWMA_SIX_BET_METHOD_ID: (
            "e1b5e100d254e2d77a5336b2d5a77675c65034d952c99940772b33d3d2332a08"
        ),
        COLD_POOL_METHOD_ID: (
            "2a80423e3cf5ee0d9543c0c7a43454a378c970d5f88edcb9b95117e4c5361223"
        ),
        MARKOV_4BET_METHOD_ID: (
            "aefb54eb345bf38fbeb1526959c12a3585a970325316dfbc2c6a7bb440b5ec6a"
        ),
        TRIPLE_STRIKE_V2_METHOD_ID: (
            "977a7cf65c8f8c5732d08edce53eb5250c9959992bf9718adb6cd3ec32a1bda5"
        ),
        MARKOV_REPEAT_METHOD_ID: (
            "9bd283fca5f3c543116b64cac512f41f889dadaf7cd646431cc83a62980ac071"
        ),
        STRUCTURAL_GROUP_METHOD_ID: (
            "2fc42ff67ab1e07c6a57adf9e9837ca5989163eff92c107c89f2b58d0081be0f"
        ),
        SUM_CONSTRAINT_METHOD_ID: (
            "acb3b118300ddeae322f98923e75bb85de2a8e8e13a9cf85c8d6bed10b9f5533"
        ),
        OPTIMAL_MATRIX_METHOD_ID: (
            "6e5aec296145ab1680cb90db65ba8265d7ed3b895ec26fc9506db8932d333c6e"
        ),
        QUAD_STRIKE_METHOD_ID: (
            "e202e664208faf3f998f93f4992a8e2595fe17f2179345bba8d4587deff48a36"
        ),
        PREDICTABILITY_ALIAS_METHOD_ID: (
            "6b456e12778745fafff402a779ba961291e215c58ce3f78d6f276b58dcefcaa2"
        ),
    }
)
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        PORTFOLIO_OPTIMIZER_METHOD_ID: 200,
        ORTHOGONAL_5BET_METHOD_ID: 500,
        SIX_BET_METHOD_ID: 200,
        EWMA_SIX_BET_METHOD_ID: 200,
        COLD_POOL_METHOD_ID: 300,
        MARKOV_4BET_METHOD_ID: 150,
        TRIPLE_STRIKE_V2_METHOD_ID: 500,
        MARKOV_REPEAT_METHOD_ID: 150,
        STRUCTURAL_GROUP_METHOD_ID: 150,
        SUM_CONSTRAINT_METHOD_ID: 150,
        OPTIMAL_MATRIX_METHOD_ID: 200,
        QUAD_STRIKE_METHOD_ID: 1,
        PREDICTABILITY_ALIAS_METHOD_ID: 200,
    }
)
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        PORTFOLIO_OPTIMIZER_METHOD_ID: 5,
        ORTHOGONAL_5BET_METHOD_ID: 5,
        SIX_BET_METHOD_ID: 11,
        EWMA_SIX_BET_METHOD_ID: 17,
        COLD_POOL_METHOD_ID: 10,
        MARKOV_4BET_METHOD_ID: 27,
        TRIPLE_STRIKE_V2_METHOD_ID: 3,
        MARKOV_REPEAT_METHOD_ID: 24,
        STRUCTURAL_GROUP_METHOD_ID: 10,
        SUM_CONSTRAINT_METHOD_ID: 39,
        OPTIMAL_MATRIX_METHOD_ID: 5,
        QUAD_STRIKE_METHOD_ID: 4,
        PREDICTABILITY_ALIAS_METHOD_ID: 5,
    }
)
SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        PORTFOLIO_OPTIMIZER_METHOD_ID: 1,
        ORTHOGONAL_5BET_METHOD_ID: 1,
        SIX_BET_METHOD_ID: 2,
        EWMA_SIX_BET_METHOD_ID: 3,
        COLD_POOL_METHOD_ID: 2,
        MARKOV_4BET_METHOD_ID: 7,
        TRIPLE_STRIKE_V2_METHOD_ID: 1,
        MARKOV_REPEAT_METHOD_ID: 6,
        STRUCTURAL_GROUP_METHOD_ID: 3,
        SUM_CONSTRAINT_METHOD_ID: 13,
        OPTIMAL_MATRIX_METHOD_ID: 1,
        QUAD_STRIKE_METHOD_ID: 1,
        PREDICTABILITY_ALIAS_METHOD_ID: 1,
    }
)
SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        PORTFOLIO_OPTIMIZER_METHOD_ID: ("P3_VERIFIED_TS3_MARKOV_FREQ_ORTHO_5BET",),
        ORTHOGONAL_5BET_METHOD_ID: ("POWER_PRECISION_ORTHOGONAL_5BET",),
        SIX_BET_METHOD_ID: ("GENERATE_5BET", "GENERATE_6BET_LAG2_ECHO"),
        EWMA_SIX_BET_METHOD_ID: (
            "GENERATE_5BET",
            "GENERATE_6BET_EWMA_HIGH_DRIFT",
            "GENERATE_6BET_EWMA_LOW_DRIFT",
        ),
        COLD_POOL_METHOD_ID: ("COLD_POOL_SIZE_12", "COLD_POOL_SIZE_15"),
        MARKOV_4BET_METHOD_ID: (
            "TRIPLE_STRIKE_BASELINE",
            "TS3_MARKOV_DEFAULT_WINDOW_100",
            "TS3_MARKOV_SENSITIVITY_WINDOW_30",
            "TS3_MARKOV_SENSITIVITY_WINDOW_50",
            "TS3_MARKOV_SENSITIVITY_WINDOW_100",
            "TS3_MARKOV_SENSITIVITY_WINDOW_200",
            "TS3_MARKOV_SENSITIVITY_WINDOW_500",
        ),
        TRIPLE_STRIKE_V2_METHOD_ID: ("CYCLE_STRUCTURAL_EXTREME_TRIPLE",),
        MARKOV_REPEAT_METHOD_ID: (
            "MARKOV_REPEAT_BOOST_0_0_BASELINE",
            "MARKOV_REPEAT_BOOST_0_1",
            "MARKOV_REPEAT_BOOST_0_2",
            "MARKOV_REPEAT_BOOST_0_3",
            "MARKOV_REPEAT_BOOST_0_5",
            "MARKOV_REPEAT_BOOST_1_0",
        ),
        STRUCTURAL_GROUP_METHOD_ID: (
            "TRIPLE_STRIKE_BASELINE",
            "TS3_STRUCTURAL_REVERSION_4BET",
            "TS3_STRUCTURAL_COLD_3BET",
        ),
        SUM_CONSTRAINT_METHOD_ID: (
            "TRIPLE_STRIKE_BASELINE",
            "POOL_8_APPLY_ALL",
            "POOL_8_APPLY_BET2_ONLY",
            "POOL_8_APPLY_BET1_ONLY",
            "POOL_10_APPLY_ALL",
            "POOL_10_APPLY_BET2_ONLY",
            "POOL_10_APPLY_BET1_ONLY",
            "POOL_12_APPLY_ALL",
            "POOL_12_APPLY_BET2_ONLY",
            "POOL_12_APPLY_BET1_ONLY",
            "POOL_15_APPLY_ALL",
            "POOL_15_APPLY_BET2_ONLY",
            "POOL_15_APPLY_BET1_ONLY",
        ),
        OPTIMAL_MATRIX_METHOD_ID: ("ALL_FIVE_PRE_SELECTION_CANDIDATE_BETS",),
        QUAD_STRIKE_METHOD_ID: ("FOURIER_COLD_TAIL_GRAY_GAP_QUAD",),
        PREDICTABILITY_ALIAS_METHOD_ID: ("TS3_MARKOV_FREQ_ORTHO_LABEL_PORTFOLIO",),
    }
)
SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        method_id: (
            (12, 15)
            if method_id == COLD_POOL_METHOD_ID
            else (8, 10, 12, 15)
            if method_id == SUM_CONSTRAINT_METHOD_ID
            else (49,)
        )
        for method_id in AUDITED_SOURCE_NATIVE_WAVE46_METHODS
    }
)
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        method_id: (
            f"{NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]}_"
            "SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER"
        )
        for method_id in AUDITED_SOURCE_NATIVE_WAVE46_METHODS
    }
)
INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD: Final = MappingProxyType(
    {
        method_id: (
            "SOURCE_LEGAL_NUMBER_SET_CANONICALIZED_TO_SORTED_TICKET_"
            "WITHOUT_CHANGING_NUMBER_SET_CONFIGURATION_OR_TICKET_POSITION"
            if method_id == SUM_CONSTRAINT_METHOD_ID
            else "SOURCE_ALREADY_SORTED_EACH_TICKET"
        )
        for method_id in AUDITED_SOURCE_NATIVE_WAVE46_METHODS
    }
)


class LegacySourceGridNativeWave46Error(ValueError):
    """The request or packaged source-runtime ledger is invalid."""


class LegacySourceGridNativeWave46SourceError(LegacySourceGridNativeWave46Error):
    """A target cannot produce a source-valid wave-46 portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave46Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE46_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceGridNativeWave46Metadata:
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
class LegacySourceGridNativeWave46Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceGridNativeWave46Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index_by_number: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    tickets_by_method: MappingProxyType[str, tuple[tuple[Ticket, ...] | None, ...]]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _ticket(value: object) -> Ticket:
    if not isinstance(value, list):
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 ticket must be an array"
        )
    values = cast(list[object], value)
    integer_values = (
        cast(list[int], values) if all(type(number) is int for number in values) else []
    )
    if (
        len(values) != 6
        or len(integer_values) != 6
        or integer_values != sorted(integer_values)
        or len(set(values)) != 6
        or any(not 1 <= cast(int, number) <= 49 for number in values)
    ):
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integer_values))


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    resource = files("lottolab.strategies.data").joinpath(LEDGER_RESOURCE_NAME)
    raw = resource.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 ledger must be an object"
        )
    document = cast(dict[str, Any], parsed)
    claimed_content_sha256 = document.pop("ledger_content_sha256", None)
    if (
        claimed_content_sha256 != LEDGER_CONTENT_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest() != LEDGER_CONTENT_SHA256
        or document.get("ledger_schema_version") != LEDGER_SCHEMA_VERSION
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("source_reference_runtime") != SOURCE_REFERENCE_RUNTIME
        or document.get("context_policy") != CONTEXT_POLICY
        or document.get("minimum_history_by_method")
        != dict(MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD)
        or document.get("source_sha256_by_method")
        != dict(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD)
        or document.get("source_configuration_count_by_method")
        != dict(SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD)
        or document.get("source_configuration_members_by_method")
        != {
            method_id: list(members)
            for method_id, members in (
                SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE46_METHOD.items()
            )
        }
    ):
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 ledger identity changed"
        )
    targets_raw = document.get("target_draw_numbers")
    contexts_raw = document.get("context_numbers_sha256_by_target")
    tickets_raw = document.get("tickets_by_method")
    if (
        not isinstance(targets_raw, list)
        or not isinstance(contexts_raw, list)
        or not isinstance(tickets_raw, dict)
    ):
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 ledger layout changed"
        )
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
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 target sequence changed"
        )
    typed_targets = cast(tuple[str, ...], tuple(targets))
    by_method: dict[str, tuple[tuple[Ticket, ...] | None, ...]] = {}
    typed_tickets = cast(dict[str, object], tickets_raw)
    if set(typed_tickets) != set(AUDITED_SOURCE_NATIVE_WAVE46_METHODS):
        raise LegacySourceGridNativeWave46Error(
            "packaged wave-46 method set changed"
        )
    for method_id in AUDITED_SOURCE_NATIVE_WAVE46_METHODS:
        raw_sequence = typed_tickets[method_id]
        if not isinstance(raw_sequence, list):
            raise LegacySourceGridNativeWave46Error(
                "packaged wave-46 method sequence changed"
            )
        sequence: list[tuple[Ticket, ...] | None] = []
        for candidate in cast(list[object], raw_sequence):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise LegacySourceGridNativeWave46Error(
                    "packaged wave-46 portfolio changed"
                )
            portfolio = tuple(_ticket(ticket) for ticket in cast(list[object], candidate))
            if (
                len(portfolio)
                != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
            ):
                raise LegacySourceGridNativeWave46Error(
                    "packaged wave-46 native ticket count changed"
                )
            sequence.append(portfolio)
        if len(sequence) != len(typed_targets):
            raise LegacySourceGridNativeWave46Error(
                "packaged wave-46 target alignment changed"
            )
        by_method[method_id] = tuple(sequence)
    return _Ledger(
        targets=typed_targets,
        target_index_by_number=MappingProxyType(
            {draw_number: index for index, draw_number in enumerate(typed_targets)}
        ),
        context_sha256=cast(tuple[str, ...], tuple(contexts)),
        tickets_by_method=MappingProxyType(by_method),
    )


def load_legacy_source_grid_native_wave46_ledger_for_verification() -> _Ledger:
    """Expose the immutable checksummed ledger to contract tests."""

    return _load_ledger()


def _validate_request(request: LegacySourceGridNativeWave46Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS:
        raise LegacySourceGridNativeWave46Error(
            "legacy method is outside the executable wave-46 batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or request.dataset_sha256 != PINNED_DATASET_SHA256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacySourceGridNativeWave46Error(
            "invalid frozen source-grid request identity"
        )
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceGridNativeWave46SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
        ):
            raise LegacySourceGridNativeWave46Error(
                "causal history draw identities are invalid"
            )
        _ticket(list(draw.numbers))
        seen.add(draw.draw_number)


def _context_sha256(history: tuple[LegacyHistoryDraw, ...]) -> str:
    context = [list(draw.numbers) for draw in history]
    return hashlib.sha256(
        json.dumps(context, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def generate_legacy_source_grid_native_wave46_portfolio(
    request: LegacySourceGridNativeWave46Request,
) -> LegacySourceGridNativeWave46Result:
    """Return the exact positional portfolio for one causal target."""

    _validate_request(request)
    ledger = _load_ledger()
    try:
        target_index = ledger.target_index_by_number[request.target_draw_number]
    except KeyError as exc:
        raise LegacySourceGridNativeWave46SourceError(
            "TARGET_OUTSIDE_FROZEN_SOURCE_GRID_TICKET_LEDGER"
        ) from exc
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacySourceGridNativeWave46SourceError(
            "FROZEN_SOURCE_CONTEXT_IDENTITY_MISMATCH"
        )
    tickets = ledger.tickets_by_method[request.legacy_method_id][target_index]
    if tickets is None:
        raise LegacySourceGridNativeWave46SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    method_id = request.legacy_method_id
    seed_material = "|".join(
        (
            SOURCE_NATIVE_WAVE46_PROTOCOL,
            method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    seed_digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    return LegacySourceGridNativeWave46Result(
        tickets=tickets,
        metadata=LegacySourceGridNativeWave46Metadata(
            protocol=SOURCE_NATIVE_WAVE46_PROTOCOL,
            legacy_method_id=method_id,
            source_sha256=SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id],
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
                "DATABASE_NEWEST_FIRST_REVERSED_ONCE_THEN_FULL_STRICT_"
                "PREFIX_BEFORE_TARGET"
            ),
            source_minimum_history_draws=(
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            candidate_k=None,
            source_candidate_k_values=(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
            ),
            native_ticket_order="FROZEN_SOURCE_CONFIGURATION_THEN_POSITIONAL_BET_ORDER",
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            combination_count=None,
            source_method_combination_count=(
                SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
            ),
            combination_members=(
                SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
            ),
            intra_ticket_order_semantics=(
                INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD[method_id]
            ),
            source_reference_runtime=SOURCE_REFERENCE_RUNTIME,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
            ledger_file_sha256=LEDGER_FILE_SHA256,
            ledger_content_sha256=LEDGER_CONTENT_SHA256,
            ledger_target_index=target_index,
        ),
    )


__all__ = [
    "AUDITED_SOURCE_NATIVE_WAVE46_METHODS",
    "COLD_POOL_METHOD_ID",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE46_USER_SEED",
    "EWMA_SIX_BET_METHOD_ID",
    "FROZEN_SOURCE_COMMIT",
    "INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "MARKOV_4BET_METHOD_ID",
    "MARKOV_REPEAT_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "OPTIMAL_MATRIX_METHOD_ID",
    "ORTHOGONAL_5BET_METHOD_ID",
    "PINNED_DATASET_SHA256",
    "PORTFOLIO_OPTIMIZER_METHOD_ID",
    "PREDICTABILITY_ALIAS_METHOD_ID",
    "QUAD_STRIKE_METHOD_ID",
    "SIX_BET_METHOD_ID",
    "SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "SOURCE_NATIVE_WAVE46_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE46_METHOD",
    "STRUCTURAL_GROUP_METHOD_ID",
    "SUM_CONSTRAINT_METHOD_ID",
    "SUPPORTED_SOURCE_NATIVE_WAVE46_METHODS",
    "TRIPLE_STRIKE_V2_METHOD_ID",
    "LegacySourceGridNativeWave46Error",
    "LegacySourceGridNativeWave46Metadata",
    "LegacySourceGridNativeWave46Request",
    "LegacySourceGridNativeWave46Result",
    "LegacySourceGridNativeWave46SourceError",
    "generate_legacy_source_grid_native_wave46_portfolio",
    "load_legacy_source_grid_native_wave46_ledger_for_verification",
]
