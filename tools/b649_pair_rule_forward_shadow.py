"""Forward-only Big Lotto pair-rule shadow execution.

The pair candidates in this module are research observations, not Goal-C
primary streams.  The implementation reads the frozen authority and its
readiness evidence, executes only the two already-online component adapters,
and writes create-or-byte-verify records below one private shadow namespace.
"""

from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import os
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from lottolab.application.strategy_preserving_20_ticket import (
    ConstructorRequest,
    ConstructorSuccess,
    construct_strategy_preserving_20_ticket,
)
from lottolab.application.use_cases.generate_bet import instantiate_portfolio_adapter
from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import evaluate_big_lotto_ticket
from lottolab.strategies.adapters.base import PortfolioBetAdapter
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry
from tools.b649_operational_prediction_loop import (
    HistorySnapshot,
    PredictionTarget,
)

TASK_ID = "BIG_LOTTO_PAIR_RULE_FORWARD_SHADOW_IMPLEMENTATION_R1"
READINESS_TASK_ID = "BIG_LOTTO_PAIR_RULE_FORWARD_SHADOW_READINESS_FREEZE_R1"
PREDICTION_SCHEMA_VERSION = "b649-pair-rule-forward-shadow-prediction-v1"
SCORE_SCHEMA_VERSION = "b649-pair-rule-forward-shadow-score-v1"
COMPARISON_SCHEMA_VERSION = "b649-pair-rule-forward-shadow-comparison-v1"
RUNTIME_REGISTRY_SCHEMA_VERSION = "b649-pair-rule-forward-shadow-runtime-registry-v1"
SHADOW_HEALTH_NAMESPACE = "research_shadow.biglotto_pair_rule_forward_v1"
SHADOW_LOCK_FILE = "shadow.lock"

READINESS_ROOT_ENV = "LOTTOLAB_B649_PAIR_RULE_FORWARD_SHADOW_READINESS_ROOT"
DEFAULT_READINESS_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "BIG_LOTTO_PAIR_RULE_FORWARD_SHADOW_READINESS_FREEZE_R1"
)
READINESS_ROOT = Path(os.environ.get(READINESS_ROOT_ENV, str(DEFAULT_READINESS_ROOT)))
FREEZE_PATH = READINESS_ROOT / "forward_shadow_candidate_freeze.json"
EXPECTED_FREEZE_SHA256 = "88cb22d721a0cf0742e121dfe254ed88221cd61921cef59957eda35fbd5e05d8"
EXPECTED_CANDIDATE_SET_SHA256 = "15a5f13d3b97f77c3ce79c6c9ea57b1e1020ed4e87b8a3df0be387280df52853"
READINESS_ARTIFACT_HASHES: dict[str, str] = {
    "forward_shadow_candidate_freeze.json": EXPECTED_FREEZE_SHA256,
    "current_origin_candidates.csv": (
        "68d012a8ed31a4a9708411b291d0706e4eb3f9bdc22d7d49c317b24bf9f479d7"
    ),
    "component_runtime_mapping.csv": (
        "ebde243a147c3f78c03bf7601c93ca78b4a1db0de50d26aa24657a273a9c5326"
    ),
    "candidate_readiness.csv": ("3e9314a844d0854764551bb90ca88dd3d1ca61d1bcc933670567a7c15b22d484"),
    "migration_handoff.csv": ("7a699e1c701a1e8b4da85bddfa71855736f43c1ad2a8e5625e4642c09c750f3f"),
    "integration_contract.json": (
        "19816d5ce70445b27b04e0a0ee19edb0f732a382a149eeb4beab2663a075e09e"
    ),
    "implementation_allowlist.md": (
        "af0a05d051f795e9cf00c6f1a6017880bc8c9f78f87806a528e2e5e86f543c68"
    ),
    "run_manifest.json": ("1da4f38d6981b9fbd9d30b9d3d56413e87eea7e61519a17b159f6654acbca577"),
}
RUNTIME_SUBROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "B649_OPERATIONAL_PREDICTION_LOOP_R1/research_shadow/"
    "biglotto_pair_rule_forward_v1"
)
ORDERED20_SEED = "biglotto-full-universe-source-grid-native-wave46-v1"
ORDERED20_CONSTRUCTOR_VERSION = "strategy_preserving_20_ticket/v1"

ORTHOGONAL_STRATEGY_ID = "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e"
COLDPOOL_STRATEGY_ID = "legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5"

READY_CANDIDATE_IDS = (
    "CURRENT-R3_BIDIRECTIONAL_RESCUE_FIRST-B20",
    "CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B10",
    "CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B20",
)
MIGRATION_BLOCKED_CANDIDATE_IDS = (
    "CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B2",
    "CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B10",
)
FROZEN_CANDIDATE_IDS = (
    "CURRENT-R3_BIDIRECTIONAL_RESCUE_FIRST-B20",
    "CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B2",
    "CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B10",
    "CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B10",
    "CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B20",
)

EQUIVALENT_GROUP_R3_R6_B20 = "ORTHOGONAL_COLDPOOL_10_10_V1"
EQUIVALENT_GROUP_R5_B10 = "ORTHOGONAL_COLDPOOL_4_6_V1"
EQUIVALENT_GROUP_R5_B2 = "MIGRATION_BLOCKED_R5_B2_V1"
EQUIVALENT_GROUP_R6_B10 = "MIGRATION_BLOCKED_R6_B10_V1"
_CANDIDATE_GROUPS = {
    "CURRENT-R3_BIDIRECTIONAL_RESCUE_FIRST-B20": EQUIVALENT_GROUP_R3_R6_B20,
    "CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B2": EQUIVALENT_GROUP_R5_B2,
    "CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B10": EQUIVALENT_GROUP_R5_B10,
    "CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B10": EQUIVALENT_GROUP_R6_B10,
    "CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B20": EQUIVALENT_GROUP_R3_R6_B20,
}

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class PairRuleForwardShadowError(RuntimeError):
    """Base class for fail-closed shadow authority or record errors."""


class ShadowAuthorityError(PairRuleForwardShadowError):
    """The frozen candidate authority or readiness evidence is invalid."""


class ShadowRecordConflictError(PairRuleForwardShadowError):
    """An existing create-once shadow record differs from its deterministic value."""


class ShadowAlreadyRunning(PairRuleForwardShadowError):
    """Another process currently holds the isolated shadow lock."""


@dataclass(frozen=True, slots=True)
class FrozenCandidate:
    candidate_id: str
    rule_id: str
    budget: int
    strategy_a_id: str
    strategy_b_id: str
    a_tickets: int
    b_tickets: int
    selection_fingerprint: str
    equivalent_portfolio_group_id: str


@dataclass(frozen=True, slots=True)
class ReadinessBundle:
    artifact_hashes: Mapping[str, str]
    rows: Mapping[str, tuple[Mapping[str, str], ...]]
    integration_contract: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ShadowAuthority:
    freeze_bytes: bytes
    freeze_sha256: str
    candidate_set_sha256: str
    candidates: tuple[FrozenCandidate, ...]
    readiness: ReadinessBundle
    runtime_registry_bytes: bytes
    runtime_registry_sha256: str

    @property
    def enabled_candidates(self) -> tuple[FrozenCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.candidate_id in READY_CANDIDATE_IDS
        )

    @property
    def migration_blocked_candidates(self) -> tuple[FrozenCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.candidate_id in MIGRATION_BLOCKED_CANDIDATE_IDS
        )

    @property
    def equivalent_groups(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for candidate in self.enabled_candidates:
            groups.setdefault(candidate.equivalent_portfolio_group_id, []).append(
                candidate.candidate_id
            )
        return groups


@dataclass(frozen=True, slots=True)
class _ComponentSpec:
    strategy_id: str
    adapter_class: str
    adapter_version: str
    native_ticket_count: int


_COMPONENT_SPECS: dict[str, _ComponentSpec] = {
    ORTHOGONAL_STRATEGY_ID: _ComponentSpec(
        strategy_id=ORTHOGONAL_STRATEGY_ID,
        adapter_class=(
            "lottolab.strategies.adapters.biglotto_orthogonal_5bet:BigLottoOrthogonal5BetAdapter"
        ),
        adapter_version="v0.1",
        native_ticket_count=5,
    ),
    COLDPOOL_STRATEGY_ID: _ComponentSpec(
        strategy_id=COLDPOOL_STRATEGY_ID,
        adapter_class=("lottolab.strategies.adapters.biglotto_batch18:BigLottoColdPool15Adapter"),
        adapter_version="v0.1",
        native_ticket_count=10,
    ),
}

_EXPECTED_CANDIDATES: tuple[FrozenCandidate, ...] = (
    FrozenCandidate(
        candidate_id="CURRENT-R3_BIDIRECTIONAL_RESCUE_FIRST-B20",
        rule_id="R3_BIDIRECTIONAL_RESCUE_FIRST",
        budget=20,
        strategy_a_id=ORTHOGONAL_STRATEGY_ID,
        strategy_b_id=COLDPOOL_STRATEGY_ID,
        a_tickets=10,
        b_tickets=10,
        selection_fingerprint=("17a171f88ad005767de4ebc301b3490d177aa11ae5d7d6e9d00c94c363788dd2"),
        equivalent_portfolio_group_id=EQUIVALENT_GROUP_R3_R6_B20,
    ),
    FrozenCandidate(
        candidate_id="CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B2",
        rule_id="R5_FAMILY_DIVERSE_PERFORMANCE",
        budget=2,
        strategy_a_id="legacy_biglotto__backtest_fcf_vs_ts3__efc61a551730",
        strategy_b_id="legacy_biglotto__biglotto_diversified_ensemble__36dbfc14b360",
        a_tickets=1,
        b_tickets=1,
        selection_fingerprint=("2cddfe000103d55a4884d1c78c29ce0ea8a83ffe3f0aa34c8896e1843da31c19"),
        equivalent_portfolio_group_id=EQUIVALENT_GROUP_R5_B2,
    ),
    FrozenCandidate(
        candidate_id="CURRENT-R5_FAMILY_DIVERSE_PERFORMANCE-B10",
        rule_id="R5_FAMILY_DIVERSE_PERFORMANCE",
        budget=10,
        strategy_a_id=ORTHOGONAL_STRATEGY_ID,
        strategy_b_id=COLDPOOL_STRATEGY_ID,
        a_tickets=4,
        b_tickets=6,
        selection_fingerprint=("b692b2f896f4d293384efcdff57a3ecbe6a2459d3364b50503efea881b0ebc9a"),
        equivalent_portfolio_group_id=EQUIVALENT_GROUP_R5_B10,
    ),
    FrozenCandidate(
        candidate_id="CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B10",
        rule_id="R6_BALANCED_ALLOCATION_PERFORMANCE",
        budget=10,
        strategy_a_id=ORTHOGONAL_STRATEGY_ID,
        strategy_b_id="legacy_biglotto__standard_ts3_5bet__527fed00a7c4",
        a_tickets=5,
        b_tickets=5,
        selection_fingerprint=("d99abe79528b44c7a47ef11c9caca8af36d7e016a025ce651b697406aa13e941"),
        equivalent_portfolio_group_id=EQUIVALENT_GROUP_R6_B10,
    ),
    FrozenCandidate(
        candidate_id="CURRENT-R6_BALANCED_ALLOCATION_PERFORMANCE-B20",
        rule_id="R6_BALANCED_ALLOCATION_PERFORMANCE",
        budget=20,
        strategy_a_id=ORTHOGONAL_STRATEGY_ID,
        strategy_b_id=COLDPOOL_STRATEGY_ID,
        a_tickets=10,
        b_tickets=10,
        selection_fingerprint=("dc30e8294d66352cd72e27eb6395c8cd96539bda35a81f3d7861be71c83864b4"),
        equivalent_portfolio_group_id=EQUIVALENT_GROUP_R3_R6_B20,
    ),
)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ShadowAuthorityError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _require_text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ShadowAuthorityError(f"{label} must be non-empty text")
    return value


def _require_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ShadowAuthorityError(f"{label} must be an integer")
    return value


def _load_frozen_candidate(raw: object, index: int) -> FrozenCandidate:
    item = _require_mapping(raw, f"candidates[{index}]")
    candidate_id = _require_text(item.get("candidate_id"), f"candidates[{index}].candidate_id")
    group_id = _CANDIDATE_GROUPS.get(candidate_id)
    if group_id is None:
        raise ShadowAuthorityError(f"candidate {candidate_id} lacks an equivalent group")
    return FrozenCandidate(
        candidate_id=candidate_id,
        rule_id=_require_text(item.get("rule_id"), f"candidates[{index}].rule_id"),
        budget=_require_int(item.get("budget"), f"candidates[{index}].budget"),
        strategy_a_id=_require_text(
            item.get("strategy_a_id"), f"candidates[{index}].strategy_a_id"
        ),
        strategy_b_id=_require_text(
            item.get("strategy_b_id"), f"candidates[{index}].strategy_b_id"
        ),
        a_tickets=_require_int(item.get("a_tickets"), f"candidates[{index}].a_tickets"),
        b_tickets=_require_int(item.get("b_tickets"), f"candidates[{index}].b_tickets"),
        selection_fingerprint=_require_text(
            item.get("selection_fingerprint"),
            f"candidates[{index}].selection_fingerprint",
        ),
        equivalent_portfolio_group_id=group_id,
    )


def _read_artifact(path: Path, expected_sha256: str, *, label: str) -> bytes:
    try:
        encoded = path.read_bytes()
    except OSError as exc:
        raise ShadowAuthorityError(f"cannot read readiness artifact: {path}") from exc
    observed = _sha256_bytes(encoded)
    if observed != expected_sha256:
        raise ShadowAuthorityError(
            f"{label} SHA-256 differs: expected {expected_sha256}, got {observed}"
        )
    return encoded


def _csv_rows(encoded: bytes, filename: str) -> tuple[Mapping[str, str], ...]:
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ShadowAuthorityError(f"{filename} is not UTF-8 CSV") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or any(not field for field in reader.fieldnames):
        raise ShadowAuthorityError(f"{filename} has no canonical CSV header")
    rows: list[Mapping[str, str]] = []
    for index, raw in enumerate(reader, start=2):
        if None in raw or any(value is None for value in raw.values()):
            raise ShadowAuthorityError(f"{filename} row {index} is malformed")
        rows.append(cast(Mapping[str, str], {str(key): str(value) for key, value in raw.items()}))
    if not rows:
        raise ShadowAuthorityError(f"{filename} is empty")
    return tuple(rows)


def _json_object(encoded: bytes, filename: str) -> Mapping[str, object]:
    try:
        decoded = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShadowAuthorityError(f"{filename} is not canonical UTF-8 JSON") from exc
    return _require_mapping(decoded, filename)


def _row_index(
    rows: Sequence[Mapping[str, str]], filename: str, key: str
) -> dict[str, Mapping[str, str]]:
    result: dict[str, Mapping[str, str]] = {}
    for row in rows:
        value = row.get(key)
        if not value or value in result:
            raise ShadowAuthorityError(f"{filename} has duplicate or empty {key}")
        result[value] = row
    return result


def _load_readiness_bundle(freeze_path: Path) -> ReadinessBundle:
    encoded_by_name: dict[str, bytes] = {}
    for filename, expected_sha256 in READINESS_ARTIFACT_HASHES.items():
        path = freeze_path if filename == FREEZE_PATH.name else READINESS_ROOT / filename
        encoded_by_name[filename] = _read_artifact(path, expected_sha256, label=filename)

    contract = _json_object(
        encoded_by_name["integration_contract.json"], "integration_contract.json"
    )
    if (
        contract.get("schema_version")
        != "biglotto-pair-rule-forward-shadow-integration-contract-v1"
    ):
        raise ShadowAuthorityError("integration contract schema is unsupported")
    if contract.get("task_id") != READINESS_TASK_ID:
        raise ShadowAuthorityError("integration contract task identity is unsupported")
    authority = _require_mapping(contract.get("authority"), "integration_contract.authority")
    if authority.get("candidate_freeze_sha256") != EXPECTED_FREEZE_SHA256:
        raise ShadowAuthorityError("integration contract freeze hash differs")
    if authority.get("candidate_set_sha256") != EXPECTED_CANDIDATE_SET_SHA256:
        raise ShadowAuthorityError("integration contract candidate-set hash differs")
    if authority.get("required_candidate_count") != 5:
        raise ShadowAuthorityError("integration contract candidate count differs")
    if authority.get("fallback_or_reselection_permitted") is not False:
        raise ShadowAuthorityError("fallback or reselection is not permitted")

    activation = _require_mapping(
        contract.get("candidate_activation"), "integration_contract.candidate_activation"
    )
    enabled_ids_value = activation.get("enabled_implementation_ready_candidate_ids", ())
    if not isinstance(enabled_ids_value, (list, tuple)):
        raise ShadowAuthorityError("integration contract active candidate set is invalid")
    enabled_ids = tuple(cast(Sequence[str], enabled_ids_value))
    if enabled_ids != READY_CANDIDATE_IDS:
        raise ShadowAuthorityError("integration contract active candidate set differs")
    blocked_ids_value = activation.get("migration_blocked_candidate_ids", ())
    if not isinstance(blocked_ids_value, (list, tuple)):
        raise ShadowAuthorityError("integration contract blocked candidate set is invalid")
    blocked_ids = tuple(cast(Sequence[str], blocked_ids_value))
    if blocked_ids != MIGRATION_BLOCKED_CANDIDATE_IDS:
        raise ShadowAuthorityError("integration contract blocked candidate set differs")
    frozen_ids_value = activation.get("frozen_candidate_ids", ())
    if not isinstance(frozen_ids_value, (list, tuple)):
        raise ShadowAuthorityError("integration contract frozen candidate set is invalid")
    frozen_contract_ids = tuple(cast(Sequence[str], frozen_ids_value))
    if set(frozen_contract_ids) != set(FROZEN_CANDIDATE_IDS) or len(frozen_contract_ids) != 5:
        raise ShadowAuthorityError("integration contract frozen candidate set differs")
    if activation.get("second_rank_fallback") is not False:
        raise ShadowAuthorityError("second-rank fallback is not permitted")

    rows: dict[str, tuple[Mapping[str, str], ...]] = {}
    for filename in (
        "current_origin_candidates.csv",
        "component_runtime_mapping.csv",
        "candidate_readiness.csv",
        "migration_handoff.csv",
    ):
        rows[filename] = _csv_rows(encoded_by_name[filename], filename)

    origins = _row_index(
        rows["current_origin_candidates.csv"], "current_origin_candidates.csv", "candidate_id"
    )
    readiness = _row_index(
        rows["candidate_readiness.csv"], "candidate_readiness.csv", "candidate_id"
    )
    mapping = _row_index(
        rows["component_runtime_mapping.csv"], "component_runtime_mapping.csv", "strategy_id"
    )
    handoff = _row_index(rows["migration_handoff.csv"], "migration_handoff.csv", "strategy_id")

    blocked_contract = _require_mapping(
        activation.get("blocked_status_contract"),
        "integration_contract.candidate_activation.blocked_status_contract",
    )
    for candidate in _EXPECTED_CANDIDATES:
        origin = origins.get(candidate.candidate_id)
        ready_row = readiness.get(candidate.candidate_id)
        if origin is None or ready_row is None:
            raise ShadowAuthorityError(f"readiness evidence lacks {candidate.candidate_id}")
        for key, expected in (
            ("rule_id", candidate.rule_id),
            ("budget", str(candidate.budget)),
            ("strategy_a_id", candidate.strategy_a_id),
            ("strategy_b_id", candidate.strategy_b_id),
            ("a_tickets", str(candidate.a_tickets)),
            ("b_tickets", str(candidate.b_tickets)),
            ("selection_fingerprint", candidate.selection_fingerprint),
        ):
            if origin.get(key) != expected:
                raise ShadowAuthorityError(
                    f"readiness evidence differs for {candidate.candidate_id}: {key}"
                )
        for key, expected in (
            ("rule_id", candidate.rule_id),
            ("budget", str(candidate.budget)),
            ("strategy_a_id", candidate.strategy_a_id),
            ("strategy_b_id", candidate.strategy_b_id),
            ("a_tickets", str(candidate.a_tickets)),
            ("b_tickets", str(candidate.b_tickets)),
        ):
            if ready_row.get(key) != expected:
                raise ShadowAuthorityError(
                    f"candidate readiness differs for {candidate.candidate_id}: {key}"
                )
        expected_classification = (
            "IMPLEMENTATION_READY"
            if candidate.candidate_id in READY_CANDIDATE_IDS
            else "FULL_MIGRATION_REQUIRED"
            if candidate.candidate_id.endswith("B2")
            else "PARTIAL_MIGRATION_REQUIRED"
        )
        if ready_row.get("candidate_readiness") != expected_classification:
            raise ShadowAuthorityError(f"candidate readiness differs for {candidate.candidate_id}")
        contract_row = blocked_contract.get(candidate.candidate_id)
        if candidate.candidate_id in READY_CANDIDATE_IDS:
            if ready_row.get("exact_blocker") != "NONE" or contract_row is not None:
                raise ShadowAuthorityError(
                    f"active candidate {candidate.candidate_id} has a blocker"
                )
        else:
            if not isinstance(contract_row, dict):
                raise ShadowAuthorityError(
                    f"blocked candidate {candidate.candidate_id} lacks exact blocker"
                )
            contract_row_mapping = cast(Mapping[str, object], contract_row)
            if ready_row.get("exact_blocker") != contract_row_mapping.get("exact_blocker"):
                raise ShadowAuthorityError(
                    f"blocked candidate {candidate.candidate_id} blocker differs"
                )

    for candidate in _EXPECTED_CANDIDATES:
        if candidate.candidate_id not in READY_CANDIDATE_IDS:
            continue
        for strategy_id in (candidate.strategy_a_id, candidate.strategy_b_id):
            row = mapping.get(strategy_id)
            if row is None:
                raise ShadowAuthorityError(f"runtime mapping lacks {strategy_id}")
            if row.get("readiness_classification") != "READY_EXISTING_EXECUTABLE":
                raise ShadowAuthorityError(f"runtime mapping is not ready for {strategy_id}")
            if row.get("production_catalog_descriptor_id") != strategy_id:
                raise ShadowAuthorityError(f"runtime catalog identity differs for {strategy_id}")
            if row.get("executable_registry_identity") != strategy_id:
                raise ShadowAuthorityError(f"runtime registry identity differs for {strategy_id}")
            if row.get("ordered20_constructor_version") != ORDERED20_CONSTRUCTOR_VERSION:
                raise ShadowAuthorityError(f"ordered20 constructor differs for {strategy_id}")
            if row.get("maximum_required_prefix") != "10":
                raise ShadowAuthorityError(f"ordered20 prefix authority differs for {strategy_id}")

    if set(handoff) != {
        "legacy_biglotto__backtest_fcf_vs_ts3__efc61a551730",
        "legacy_biglotto__biglotto_diversified_ensemble__36dbfc14b360",
        "legacy_biglotto__standard_ts3_5bet__527fed00a7c4",
    }:
        raise ShadowAuthorityError("migration handoff identity set differs")

    return ReadinessBundle(
        artifact_hashes=dict(READINESS_ARTIFACT_HASHES),
        rows=rows,
        integration_contract=contract,
    )


def _load_frozen_payload(
    path: Path,
) -> tuple[bytes, str, str, tuple[FrozenCandidate, ...]]:
    raw_bytes = _read_artifact(path, EXPECTED_FREEZE_SHA256, label="candidate freeze")
    try:
        decoded = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShadowAuthorityError("frozen candidate authority is not canonical JSON") from exc
    payload = _require_mapping(decoded, "freeze")
    if payload.get("schema_version") != "biglotto-forward-shadow-candidate-freeze-v1":
        raise ShadowAuthorityError("frozen candidate authority schema is unsupported")
    if payload.get("task_id") != READINESS_TASK_ID:
        raise ShadowAuthorityError("frozen candidate authority task identity is unsupported")
    if payload.get("freeze_status") != "FROZEN_BEFORE_RUNTIME_MAPPING":
        raise ShadowAuthorityError("frozen candidate authority is not runtime-frozen")
    if payload.get("selection_stage") != "CURRENT_ORIGIN_DISCOVERY_ONLY":
        raise ShadowAuthorityError("frozen candidate authority selection stage changed")
    candidates_value = payload.get("candidates")
    if not isinstance(candidates_value, list):
        raise ShadowAuthorityError("frozen candidate authority must contain five candidates")
    candidates_raw = cast(list[object], candidates_value)
    if len(candidates_raw) != 5:
        raise ShadowAuthorityError("frozen candidate authority must contain five candidates")
    candidates = tuple(
        _load_frozen_candidate(item, index) for index, item in enumerate(candidates_raw)
    )
    if tuple(candidate.candidate_id for candidate in candidates) != FROZEN_CANDIDATE_IDS:
        raise ShadowAuthorityError("frozen candidate IDs or order changed")
    if len(set(candidate.candidate_id for candidate in candidates)) != 5:
        raise ShadowAuthorityError("frozen candidate IDs are not unique")
    if candidates != _EXPECTED_CANDIDATES:
        raise ShadowAuthorityError("frozen candidate strategy IDs or allocations changed")
    candidate_set_sha256 = _require_text(
        payload.get("candidate_set_sha256"), "freeze.candidate_set_sha256"
    )
    if candidate_set_sha256 != _sha256_bytes(_canonical_bytes(candidates_raw)):
        raise ShadowAuthorityError("frozen candidate set digest does not verify")
    if candidate_set_sha256 != EXPECTED_CANDIDATE_SET_SHA256:
        raise ShadowAuthorityError("frozen candidate set digest is not authorized")
    if not _require_mapping(payload.get("authority"), "freeze.authority"):
        raise ShadowAuthorityError("freeze authority metadata is missing")
    return raw_bytes, EXPECTED_FREEZE_SHA256, candidate_set_sha256, candidates


def _component_provenance(strategy_id: str, readiness: ReadinessBundle) -> dict[str, object]:
    rows = _row_index(
        readiness.rows["component_runtime_mapping.csv"],
        "component_runtime_mapping.csv",
        "strategy_id",
    )
    row = rows.get(strategy_id)
    if row is None:
        return {"strategy_id": strategy_id, "activation_status": "MIGRATION_REQUIRED"}
    fields = (
        "strategy_id",
        "legacy_method_id",
        "source_path",
        "source_commit",
        "source_sha256",
        "research_strategy_version",
        "production_catalog_descriptor_id",
        "production_catalog_version",
        "production_catalog_lifecycle_status",
        "production_catalog_executable",
        "production_catalog_response_shape",
        "production_catalog_min_history",
        "production_catalog_native_ticket_count",
        "executable_registry_identity",
        "reverse_mapping_status",
        "adapter_class",
        "adapter_version",
        "adapter_instantiation_path",
        "ordered20_constructor_version",
        "ordered20_live_verified",
        "maximum_required_prefix",
        "readiness_classification",
    )
    return {field: row.get(field) for field in fields}


def _runtime_registry_bytes(
    freeze_sha256: str,
    candidate_set_sha256: str,
    candidates: Sequence[FrozenCandidate],
    readiness: ReadinessBundle,
) -> bytes:
    readiness_rows = _row_index(
        readiness.rows["candidate_readiness.csv"], "candidate_readiness.csv", "candidate_id"
    )
    origin_rows = _row_index(
        readiness.rows["current_origin_candidates.csv"],
        "current_origin_candidates.csv",
        "candidate_id",
    )
    handoff_rows = _row_index(
        readiness.rows["migration_handoff.csv"], "migration_handoff.csv", "strategy_id"
    )
    entries: list[dict[str, object]] = []
    for candidate in candidates:
        readiness_row = readiness_rows[candidate.candidate_id]
        origin = origin_rows[candidate.candidate_id]
        active = candidate.candidate_id in READY_CANDIDATE_IDS
        blocker = readiness_row.get("exact_blocker")
        entries.append(
            {
                "candidate_id": candidate.candidate_id,
                "activation_status": "ACTIVE_IMPLEMENTATION_READY"
                if active
                else "MIGRATION_REQUIRED",
                "candidate_readiness": readiness_row.get("candidate_readiness"),
                "exact_blocker": None if active else blocker,
                "rule_id": candidate.rule_id,
                "budget": candidate.budget,
                "strategy_a_id": candidate.strategy_a_id,
                "strategy_b_id": candidate.strategy_b_id,
                "allocation": {"a_tickets": candidate.a_tickets, "b_tickets": candidate.b_tickets},
                "selection_fingerprint": candidate.selection_fingerprint,
                "equivalent_portfolio_group_id": candidate.equivalent_portfolio_group_id,
                "freeze_sha256": freeze_sha256,
                "discovery": {
                    "cutoff_draw": origin.get("discovery_cutoff"),
                    "first_draw": origin.get("discovery_first_draw"),
                    "last_draw": origin.get("discovery_last_draw"),
                    "draw_count": origin.get("discovery_draw_count"),
                    "allocation": origin.get("allocation"),
                },
                "component_a": _component_provenance(candidate.strategy_a_id, readiness),
                "component_b": _component_provenance(candidate.strategy_b_id, readiness),
                "migration_handoff": (
                    None
                    if active
                    else [
                        handoff_rows[strategy_id]
                        for strategy_id in (candidate.strategy_a_id, candidate.strategy_b_id)
                        if strategy_id in handoff_rows
                    ]
                ),
            }
        )
    payload = {
        "schema_version": RUNTIME_REGISTRY_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "readiness_task_id": READINESS_TASK_ID,
        "freeze_sha256": freeze_sha256,
        "candidate_set_sha256": candidate_set_sha256,
        "readiness_artifact_hashes": dict(readiness.artifact_hashes),
        "active_candidate_ids": list(READY_CANDIDATE_IDS),
        "migration_blocked_candidate_ids": list(MIGRATION_BLOCKED_CANDIDATE_IDS),
        "equivalent_portfolio_groups": {
            group: [
                candidate.candidate_id
                for candidate in candidates
                if candidate.equivalent_portfolio_group_id == group
            ]
            for group in sorted(
                {candidate.equivalent_portfolio_group_id for candidate in candidates}
            )
        },
        "candidates": entries,
    }
    return _canonical_bytes(payload)


def load_shadow_authority(path: Path = FREEZE_PATH) -> ShadowAuthority:
    """Read and validate every frozen artifact before any runtime write."""

    readiness = _load_readiness_bundle(path)
    freeze_bytes, freeze_sha256, candidate_set_sha256, candidates = _load_frozen_payload(path)
    registry = _runtime_registry_bytes(freeze_sha256, candidate_set_sha256, candidates, readiness)
    return ShadowAuthority(
        freeze_bytes=freeze_bytes,
        freeze_sha256=freeze_sha256,
        candidate_set_sha256=candidate_set_sha256,
        candidates=candidates,
        readiness=readiness,
        runtime_registry_bytes=registry,
        runtime_registry_sha256=_sha256_bytes(registry),
    )


def shadow_health_not_run(
    status: str = "NOT_CONFIGURED",
    *,
    last_error: str | None = None,
    target: PredictionTarget | None = None,
    primary_status_observed: str | None = None,
    canonical_source_head: str | None = None,
) -> dict[str, object]:
    """Return a namespace-shaped status without touching runtime files."""

    payload: dict[str, object] = {
        "namespace": SHADOW_HEALTH_NAMESPACE,
        "status": status,
        "target_draw_number": None if target is None else target.draw_number,
        "target_draw_date": None if target is None else target.draw_date,
        "freeze_sha256": EXPECTED_FREEZE_SHA256,
        "runtime_registry_sha256": None,
        "authority_candidate_count": 5,
        "enabled_candidate_count": len(READY_CANDIDATE_IDS),
        "migration_blocked_candidate_count": len(MIGRATION_BLOCKED_CANDIDATE_IDS),
        "unique_active_portfolio_group_count": 2,
        "equivalent_portfolio_groups": {
            EQUIVALENT_GROUP_R3_R6_B20: [
                READY_CANDIDATE_IDS[0],
                READY_CANDIDATE_IDS[2],
            ],
            EQUIVALENT_GROUP_R5_B10: [READY_CANDIDATE_IDS[1]],
        },
        "available_enabled_candidate_ids": [],
        "missing_enabled_candidate_ids": list(READY_CANDIDATE_IDS),
        "migration_blocked_candidate_ids": list(MIGRATION_BLOCKED_CANDIDATE_IDS),
        "migration_block_reasons": {},
        "deadline_status": "NOT_RUN",
        "primary_status_observed": primary_status_observed,
        "canonical_source_head": canonical_source_head,
        "created_prediction_count": 0,
        "scored_candidate_count": 0,
        "consecutive_failures": 0,
        "no_backfill": True,
        "no_backfill_status": "ENFORCED",
        "shadow_lock_status": "NOT_HELD",
        "last_success_at": None,
        "last_error": last_error,
    }
    return payload


def _ensure_aware(value: datetime, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def _utc_text(value: datetime) -> str:
    return (
        _ensure_aware(value, "timestamp")
        .astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _target_deadline(target: PredictionTarget, explicit: datetime | None) -> datetime:
    if explicit is not None:
        deadline = _ensure_aware(explicit, "readiness_deadline")
    else:
        try:
            deadline = datetime.fromisoformat(target.scheduled_at)
        except ValueError as exc:
            raise ValueError("target.scheduled_at is not valid ISO-8601") from exc
        deadline = _ensure_aware(deadline, "target.scheduled_at")
    return deadline.astimezone(UTC)


def _canonical_scheduled_at(target: PredictionTarget) -> str:
    return _target_deadline(target, None).isoformat().replace("+00:00", "Z")


def _validate_target(target: PredictionTarget) -> None:
    if target.lottery_type != LotteryType.BIG_LOTTO.value:
        raise ValueError("pair-rule shadow supports BIG_LOTTO only")
    if type(target.draw_number) is not str or not target.draw_number:
        raise ValueError("target.draw_number must be non-empty text")
    if type(target.draw_date) is not str or not target.draw_date:
        raise ValueError("target.draw_date must be non-empty text")


def _safe_runtime_path(root: Path, *parts: str) -> Path:
    if not root.is_absolute():
        raise ValueError("shadow runtime root must be absolute")
    if any(not part or part in {".", ".."} or "/" in part for part in parts):
        raise ValueError("shadow runtime path component is invalid")
    candidate = root.joinpath(*parts)
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve(strict=False)
    if os.path.commonpath((str(root_resolved), str(candidate_resolved))) != str(root_resolved):
        raise ValueError("shadow runtime path escapes the namespace")
    return candidate


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise ShadowRecordConflictError(f"shadow path is not a private directory: {path}")
    path.chmod(0o700)


def _create_or_verify(path: Path, encoded: bytes) -> bool:
    _ensure_private_directory(path.parent)
    if path.is_symlink():
        raise ShadowRecordConflictError(f"shadow record is a symlink: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        existing = path.read_bytes()
        if existing != encoded:
            raise ShadowRecordConflictError(f"existing shadow record differs: {path}") from None
        return False
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)
    return True


def _replace_bytes(path: Path, encoded: bytes) -> None:
    _ensure_private_directory(path.parent)
    if path.is_symlink():
        raise ShadowRecordConflictError(f"shadow mutable record is a symlink: {path}")
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    except BaseException:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise


def _read_object(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ShadowRecordConflictError(f"shadow record is not a regular file: {path}")
    try:
        decoded = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShadowRecordConflictError(f"shadow record is not valid JSON: {path}") from exc
    if not isinstance(decoded, dict):
        raise ShadowRecordConflictError(f"shadow record is not a JSON object: {path}")
    return cast(dict[str, object], decoded)


class ShadowProcessLock:
    """Non-blocking lock scoped only to the research-shadow namespace."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._descriptor: int | None = None

    def __enter__(self) -> ShadowProcessLock:
        _ensure_private_directory(self._path.parent)
        descriptor: int | None = None
        try:
            descriptor = os.open(
                self._path,
                os.O_RDWR | os.O_CREAT | _NOFOLLOW,
                0o600,
            )
            os.fchmod(descriptor, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in {11, 35}:
                    raise ShadowAlreadyRunning("another shadow invocation holds the lock") from exc
                raise ShadowRecordConflictError("cannot acquire shadow lock") from exc
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
            raise
        self._descriptor = descriptor
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc_value, traceback
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _write_authority_snapshot(root: Path, authority: ShadowAuthority) -> None:
    _create_or_verify(_safe_runtime_path(root, "authority", "freeze.json"), authority.freeze_bytes)
    _create_or_verify(
        _safe_runtime_path(root, "authority", "runtime_registry.json"),
        authority.runtime_registry_bytes,
    )


def _idempotence_key(
    authority: ShadowAuthority,
    candidate: FrozenCandidate,
    target: PredictionTarget,
    history: HistorySnapshot,
) -> str:
    preimage = "|".join(
        (
            authority.freeze_sha256,
            candidate.selection_fingerprint,
            target.draw_number,
            history.history_sha256,
            _canonical_scheduled_at(target),
        )
    )
    return _sha256_bytes(preimage.encode("utf-8"))


def _portfolio_sha256(tickets: Sequence[Sequence[int]]) -> str:
    return _sha256_bytes(_canonical_bytes([list(ticket) for ticket in tickets]))


def _component_record(
    spec: _ComponentSpec,
    native_tickets: tuple[tuple[int, ...], ...],
    constructed: ConstructorSuccess,
    allocation_count: int = 20,
) -> dict[str, object]:
    metadata = constructed.metadata
    if len(constructed.tickets) != 20:
        raise PairRuleForwardShadowError(
            f"{spec.strategy_id}: ordered20 constructor emitted {len(constructed.tickets)} tickets"
        )
    if (
        metadata.constructor_name + "/" + metadata.constructor_version
        != ORDERED20_CONSTRUCTOR_VERSION
    ):
        raise PairRuleForwardShadowError(
            f"{spec.strategy_id}: ordered20 constructor identity changed"
        )
    if len(native_tickets) != spec.native_ticket_count:
        raise PairRuleForwardShadowError(f"{spec.strategy_id}: native ticket count changed")
    ordered = tuple(tuple(ticket) for ticket in constructed.tickets)
    return {
        "strategy_id": spec.strategy_id,
        "adapter_class": spec.adapter_class,
        "adapter_version": spec.adapter_version,
        "native_ticket_count": spec.native_ticket_count,
        "ordered20_constructor_version": ORDERED20_CONSTRUCTOR_VERSION,
        "ordered20_seed_digest": metadata.seed_digest,
        "allocation_prefix_count": allocation_count,
        "allocation_prefix_tickets": [list(ticket) for ticket in ordered[:allocation_count]],
        "ordered20_count": 20,
        "ordered20_sha256": _portfolio_sha256(ordered),
    }


def _build_component(
    strategy_id: str,
    *,
    history: HistorySnapshot,
    target: PredictionTarget,
    allocation_count: int = 20,
) -> tuple[dict[str, object], tuple[tuple[int, ...], ...]]:
    spec = _COMPONENT_SPECS.get(strategy_id)
    if spec is None:
        raise PairRuleForwardShadowError(f"{strategy_id}: component is not implementation-ready")
    catalog = production_catalog()
    descriptor = catalog.get(strategy_id)
    if not descriptor.executable or descriptor.adapter_path != spec.adapter_class:
        raise PairRuleForwardShadowError(
            f"{strategy_id}: executable catalog identity does not match the freeze"
        )
    adapter_class = ExecutableRegistry(catalog).load_adapter(strategy_id)
    if not isinstance(adapter_class, type) or not issubclass(adapter_class, PortfolioBetAdapter):
        raise PairRuleForwardShadowError(f"{strategy_id}: adapter is not a portfolio adapter")
    adapter_type = adapter_class
    adapter = instantiate_portfolio_adapter(strategy_id, adapter_type)
    if f"{adapter_type.__module__}:{adapter_type.__name__}" != spec.adapter_class:
        raise PairRuleForwardShadowError(f"{strategy_id}: adapter class identity changed")
    if adapter.strategy_id != spec.strategy_id or adapter.strategy_version != spec.adapter_version:
        raise PairRuleForwardShadowError(f"{strategy_id}: adapter version identity changed")
    if adapter.native_ticket_count != spec.native_ticket_count:
        raise PairRuleForwardShadowError(f"{strategy_id}: native ticket declaration changed")
    native_tickets = adapter.get_bets(history.rows, LotteryType.BIG_LOTTO)
    if len(native_tickets) != spec.native_ticket_count:
        raise PairRuleForwardShadowError(f"{strategy_id}: native execution count changed")
    constructed = construct_strategy_preserving_20_ticket(
        ConstructorRequest(
            strategy_id=strategy_id,
            draw_id=target.draw_number,
            replicate_id=0,
            raw_tickets=native_tickets,
            historical_cutoff_identity=history.cutoff_draw,
            user_seed=ORDERED20_SEED,
        )
    )
    if not isinstance(constructed, ConstructorSuccess):
        raise PairRuleForwardShadowError(
            f"{strategy_id}: ordered20 construction failed: {constructed}"
        )
    return _component_record(
        spec, native_tickets, constructed, allocation_count
    ), constructed.tickets


def _project_component(
    component: Mapping[str, object],
    ordered20: Sequence[Sequence[int]],
    allocation_count: int,
) -> dict[str, object]:
    projected = dict(component)
    projected["allocation_prefix_count"] = allocation_count
    projected["allocation_prefix_tickets"] = [
        list(ticket) for ticket in ordered20[:allocation_count]
    ]
    return projected


def _unavailable_component(strategy_id: str, allocation_count: int) -> dict[str, object]:
    return {
        "strategy_id": strategy_id,
        "adapter_class": None,
        "adapter_version": None,
        "native_ticket_count": None,
        "ordered20_constructor_version": None,
        "ordered20_seed_digest": None,
        "allocation_prefix_count": allocation_count,
        "allocation_prefix_tickets": [],
        "ordered20_count": None,
        "ordered20_sha256": None,
        "status": "NOT_GENERATED",
    }


def _prediction_path(root: Path, target: PredictionTarget, candidate: FrozenCandidate) -> Path:
    return _safe_runtime_path(
        root, "predictions", target.draw_number, f"{candidate.candidate_id}.json"
    )


def _score_path(root: Path, target: PredictionTarget, candidate: FrozenCandidate) -> Path:
    return _safe_runtime_path(root, "scores", target.draw_number, f"{candidate.candidate_id}.json")


def _prediction_ticket_list(value: object, label: str) -> list[list[int]]:
    if not isinstance(value, list):
        raise ShadowRecordConflictError(f"prediction {label} is not a ticket list")
    tickets: list[list[int]] = []
    for item in cast(list[object], value):
        if not isinstance(item, (list, tuple)):
            raise ShadowRecordConflictError(f"prediction {label} contains an invalid ticket")
        numbers = cast(Sequence[object], item)
        if len(numbers) != 6 or not all(type(number) is int for number in numbers):
            raise ShadowRecordConflictError(f"prediction {label} contains an invalid ticket")
        tickets.append(list(cast(Sequence[int], numbers)))
    return tickets


def _prediction_record(
    authority: ShadowAuthority,
    candidate: FrozenCandidate,
    target: PredictionTarget,
    history: HistorySnapshot,
    deadline: datetime,
    *,
    status: str,
    component_a: Mapping[str, object],
    component_b: Mapping[str, object],
    composed: Sequence[Sequence[int]],
    a_only: Sequence[Sequence[int]],
    b_only: Sequence[Sequence[int]],
    created_at: datetime,
    canonical_source_head: str,
) -> dict[str, object]:
    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "freeze_sha256": authority.freeze_sha256,
        "candidate_set_sha256": authority.candidate_set_sha256,
        "runtime_registry_sha256": authority.runtime_registry_sha256,
        "candidate_id": candidate.candidate_id,
        "equivalent_portfolio_group_id": candidate.equivalent_portfolio_group_id,
        "selection_fingerprint": candidate.selection_fingerprint,
        "rule_id": candidate.rule_id,
        "budget": candidate.budget,
        "lottery_type": target.lottery_type,
        "target_lottery_type": target.lottery_type,
        "target_draw_number": target.draw_number,
        "target_draw_date": target.draw_date,
        "scheduled_at": _canonical_scheduled_at(target),
        "prediction_created_at": _utc_text(created_at),
        "prediction_temporal_class": "PRE_DRAW",
        "canonical_source_head": canonical_source_head,
        "readiness_deadline": _utc_text(deadline),
        "history_cutoff_draw_number": history.cutoff_draw,
        "history_identity_sha256": history.history_sha256,
        "component_a": dict(component_a),
        "component_b": dict(component_b),
        "ordered20_hashes": {
            "a": component_a.get("ordered20_sha256"),
            "b": component_b.get("ordered20_sha256"),
        },
        "composed_ordered_tickets": [list(ticket) for ticket in composed],
        "combined_portfolio_sha256": _portfolio_sha256(composed),
        "a_only_same_budget_comparator_tickets": [list(ticket) for ticket in a_only],
        "b_only_same_budget_comparator_tickets": [list(ticket) for ticket in b_only],
        "a_only_same_budget_comparator_sha256": _portfolio_sha256(a_only),
        "b_only_same_budget_comparator_sha256": _portfolio_sha256(b_only),
        "idempotence_key": _idempotence_key(authority, candidate, target, history),
        "status": status,
    }


def _verify_existing_prediction(
    payload: Mapping[str, object],
    authority: ShadowAuthority,
    candidate: FrozenCandidate,
    target: PredictionTarget,
    history: HistorySnapshot,
) -> str:
    expected_key = _idempotence_key(authority, candidate, target, history)
    checks = (
        ("schema_version", PREDICTION_SCHEMA_VERSION),
        ("freeze_sha256", authority.freeze_sha256),
        ("candidate_set_sha256", authority.candidate_set_sha256),
        ("runtime_registry_sha256", authority.runtime_registry_sha256),
        ("candidate_id", candidate.candidate_id),
        ("equivalent_portfolio_group_id", candidate.equivalent_portfolio_group_id),
        ("selection_fingerprint", candidate.selection_fingerprint),
        ("rule_id", candidate.rule_id),
        ("budget", candidate.budget),
        ("target_draw_number", target.draw_number),
        ("target_draw_date", target.draw_date),
        ("scheduled_at", _canonical_scheduled_at(target)),
        ("history_cutoff_draw_number", history.cutoff_draw),
        ("history_identity_sha256", history.history_sha256),
        ("prediction_temporal_class", "PRE_DRAW"),
        ("idempotence_key", expected_key),
    )
    for key, expected in checks:
        if payload.get(key) != expected:
            raise ShadowRecordConflictError(f"existing shadow prediction {key} differs")
    status = payload.get("status")
    if type(status) is not str:
        raise ShadowRecordConflictError("existing shadow prediction status is invalid")
    if status == "AVAILABLE":
        for ticket_key, hash_key in (
            ("composed_ordered_tickets", "combined_portfolio_sha256"),
            (
                "a_only_same_budget_comparator_tickets",
                "a_only_same_budget_comparator_sha256",
            ),
            (
                "b_only_same_budget_comparator_tickets",
                "b_only_same_budget_comparator_sha256",
            ),
        ):
            tickets = _prediction_ticket_list(payload.get(ticket_key), ticket_key)
            if len(tickets) != candidate.budget:
                raise ShadowRecordConflictError(
                    f"existing shadow prediction {ticket_key} length differs"
                )
            if payload.get(hash_key) != _portfolio_sha256(tickets):
                raise ShadowRecordConflictError(f"existing shadow prediction {hash_key} differs")
    return status


def _previous_failure_count(root: Path) -> int:
    path = _safe_runtime_path(root, "health.json")
    if not path.exists():
        return 0
    try:
        value = _read_object(path).get("consecutive_failures", 0)
    except ShadowRecordConflictError:
        return 0
    return value if type(value) is int and value >= 0 else 0


def _candidate_blocker(authority: ShadowAuthority, candidate_id: str) -> str | None:
    rows = _row_index(
        authority.readiness.rows["candidate_readiness.csv"],
        "candidate_readiness.csv",
        "candidate_id",
    )
    return rows.get(candidate_id, {}).get("exact_blocker")


def _health(
    authority: ShadowAuthority,
    *,
    status: str,
    deadline_status: str,
    available: list[str],
    missing: list[str],
    last_error: str | None,
    target: PredictionTarget,
    primary_status_observed: str,
    canonical_source_head: str,
    created_prediction_count: int,
    scored_candidate_count: int,
    consecutive_failures: int,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "namespace": SHADOW_HEALTH_NAMESPACE,
        "status": status,
        "target_draw_number": target.draw_number,
        "target_draw_date": target.draw_date,
        "freeze_sha256": authority.freeze_sha256,
        "runtime_registry_sha256": authority.runtime_registry_sha256,
        "candidate_set_sha256": authority.candidate_set_sha256,
        "authority_candidate_count": len(authority.candidates),
        "enabled_candidate_count": len(authority.enabled_candidates),
        "migration_blocked_candidate_count": len(authority.migration_blocked_candidates),
        "unique_active_portfolio_group_count": len(authority.equivalent_groups),
        "equivalent_portfolio_groups": authority.equivalent_groups,
        "available_enabled_candidate_ids": available,
        "missing_enabled_candidate_ids": missing,
        "migration_blocked_candidate_ids": [
            candidate.candidate_id for candidate in authority.migration_blocked_candidates
        ],
        "migration_block_reasons": {
            candidate.candidate_id: _candidate_blocker(authority, candidate.candidate_id)
            for candidate in authority.migration_blocked_candidates
        },
        "deadline_status": deadline_status,
        "primary_status_observed": primary_status_observed,
        "canonical_source_head": canonical_source_head,
        "created_prediction_count": created_prediction_count,
        "scored_candidate_count": scored_candidate_count,
        "consecutive_failures": consecutive_failures,
        "no_backfill": True,
        "no_backfill_status": "ENFORCED",
        "shadow_lock_status": "HELD",
        "last_error": last_error,
    }
    if extra is not None:
        payload.update(extra)
    payload.setdefault(
        "last_success_at",
        payload.get("observed_at") if last_error is None else None,
    )
    return payload


def _write_health(root: Path, payload: Mapping[str, object]) -> None:
    _replace_bytes(_safe_runtime_path(root, "health.json"), _canonical_bytes(dict(payload)))


def _load_existing_status(
    root: Path,
    authority: ShadowAuthority,
    candidate: FrozenCandidate,
    target: PredictionTarget,
    history: HistorySnapshot,
) -> str | None:
    path = _prediction_path(root, target, candidate)
    if not path.exists():
        return None
    return _verify_existing_prediction(_read_object(path), authority, candidate, target, history)


def _official_outcome_identity(outcome: Mapping[str, object]) -> str:
    return _sha256_bytes(_canonical_bytes(dict(outcome)))


def _official_numbers(outcome: Mapping[str, object]) -> tuple[tuple[int, ...], int]:
    main_value = outcome.get("main_numbers")
    special = outcome.get("special_number")
    if not isinstance(main_value, (list, tuple)):
        raise ValueError("official outcome main_numbers must contain six integers")
    main_values = cast(Sequence[object], main_value)
    if len(main_values) != 6 or not all(type(value) is int for value in main_values):
        raise ValueError("official outcome main_numbers must contain six integers")
    if type(special) is not int:
        raise ValueError("official outcome special_number must be an integer")
    return cast(tuple[int, ...], tuple(main_values)), special


def _official_total_prize_amount(outcome: Mapping[str, object]) -> int:
    value = outcome.get("official_total_prize_amount", outcome.get("total_prize_amount", 0))
    if type(value) is not int or value < 0:
        raise ValueError("official total prize amount must be a non-negative integer")
    return value


def _ticket_results(
    tickets: Sequence[Sequence[int]],
    official_main: tuple[int, ...],
    official_special: int,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for position, raw_ticket in enumerate(tickets, start=1):
        if len(raw_ticket) != 6 or not all(type(number) is int for number in raw_ticket):
            raise ValueError("shadow prediction ticket contains a non-integer")
        predicted = tuple(raw_ticket)
        evaluation = evaluate_big_lotto_ticket(
            predicted_main_numbers=predicted,
            predicted_special_number=None,
            winning_main_numbers=official_main,
            winning_special_number=official_special,
        )
        results.append(
            {
                "ticket_position": position,
                "predicted_numbers": list(predicted),
                "main_hits": evaluation.zone1_hits,
                "special_hit": evaluation.zone2_hit,
                "official_any_prize": evaluation.is_winner,
                "official_prize_tier": evaluation.prize_tier,
                "prize_rule_version": evaluation.prize_rule_version,
            }
        )
    return results


def _portfolio_score(
    tickets: Sequence[Sequence[int]],
    official_main: tuple[int, ...],
    official_special: int,
) -> dict[str, object]:
    results = _ticket_results(tickets, official_main, official_special)
    best_main_hit = max((cast(int, result["main_hits"]) for result in results), default=0)
    any_prize_count = sum(int(cast(bool, result["official_any_prize"])) for result in results)
    hit_depth = {f"M{depth}+": best_main_hit >= depth for depth in range(1, 7)}
    prize_detail = [
        {
            "ticket_position": result["ticket_position"],
            "official_prize_tier": result["official_prize_tier"],
            "main_hits": result["main_hits"],
            "special_hit": result["special_hit"],
        }
        for result in results
    ]
    return {
        "portfolio_sha256": _portfolio_sha256(tickets),
        "ticket_count": len(tickets),
        "ticket_results": results,
        "official_any_prize": any_prize_count > 0,
        "official_any_prize_count": any_prize_count,
        "best_main_hit": best_main_hit,
        "hit_depth": hit_depth,
        **hit_depth,
        "prize_detail": prize_detail,
    }


def _score_delta(left: Mapping[str, object], right: Mapping[str, object]) -> dict[str, object]:
    keys = (
        "official_any_prize_count",
        "best_main_hit",
        "M1+",
        "M2+",
        "M3+",
        "M4+",
        "M5+",
        "M6+",
    )
    return {
        key: int(cast(int | bool, left[key])) - int(cast(int | bool, right[key])) for key in keys
    }


def _score_record(
    authority: ShadowAuthority,
    candidate: FrozenCandidate,
    target: PredictionTarget,
    prediction: Mapping[str, object],
    prediction_sha256: str,
    outcome: Mapping[str, object],
) -> dict[str, object]:
    if prediction.get("status") != "AVAILABLE":
        raise ValueError("only AVAILABLE shadow predictions can be scored")
    official_main, official_special = _official_numbers(outcome)

    def tickets(key: str) -> list[list[int]]:
        value = prediction.get(key)
        if not isinstance(value, list):
            raise ValueError(f"shadow prediction {key} is invalid")
        result: list[list[int]] = []
        for item in cast(list[object], value):
            if not isinstance(item, (list, tuple)):
                raise ValueError(f"shadow prediction {key} contains an invalid ticket")
            result.append(list(cast(Sequence[int], item)))
        return result

    pair_tickets = tickets("composed_ordered_tickets")
    a_tickets = tickets("a_only_same_budget_comparator_tickets")
    b_tickets = tickets("b_only_same_budget_comparator_tickets")
    pair = _portfolio_score(pair_tickets, official_main, official_special)
    a_only = _portfolio_score(a_tickets, official_main, official_special)
    b_only = _portfolio_score(b_tickets, official_main, official_special)
    outcome_identity = _official_outcome_identity(outcome)
    return {
        "schema_version": SCORE_SCHEMA_VERSION,
        "freeze_sha256": authority.freeze_sha256,
        "runtime_registry_sha256": authority.runtime_registry_sha256,
        "candidate_id": candidate.candidate_id,
        "equivalent_portfolio_group_id": candidate.equivalent_portfolio_group_id,
        "target_draw_number": target.draw_number,
        "prediction_sha256": prediction_sha256,
        "official_outcome_identity_sha256": outcome_identity,
        "official_outcome_revision": outcome.get("revision", outcome.get("outcome_revision")),
        "official_main_numbers": list(official_main),
        "official_special_number": official_special,
        "ticket_results": pair["ticket_results"],
        "official_any_prize": pair["official_any_prize"],
        "official_any_prize_count": pair["official_any_prize_count"],
        "official_total_prize_amount": _official_total_prize_amount(outcome),
        "best_main_hit": pair["best_main_hit"],
        "hit_depth": pair["hit_depth"],
        "prize_detail": pair["prize_detail"],
        "portfolio_scores": {"pair": pair, "a_only": a_only, "b_only": b_only},
        "pair_minus_a": _score_delta(pair, a_only),
        "pair_minus_b": _score_delta(pair, b_only),
        "status": "SCORED",
    }


def _comparison_record(
    authority: ShadowAuthority,
    candidate: FrozenCandidate,
    target: PredictionTarget,
    score: Mapping[str, object],
) -> dict[str, object]:
    prediction_sha256 = cast(str, score["prediction_sha256"])
    outcome_sha256 = cast(str, score["official_outcome_identity_sha256"])
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_key": "|".join(
            (
                authority.freeze_sha256,
                candidate.candidate_id,
                target.draw_number,
                prediction_sha256,
                outcome_sha256,
            )
        ),
        "freeze_sha256": authority.freeze_sha256,
        "runtime_registry_sha256": authority.runtime_registry_sha256,
        "candidate_id": candidate.candidate_id,
        "equivalent_portfolio_group_id": candidate.equivalent_portfolio_group_id,
        "target_draw_number": target.draw_number,
        "prediction_sha256": prediction_sha256,
        "official_outcome_identity_sha256": outcome_sha256,
        "official_any_prize_count": score["official_any_prize_count"],
        "official_total_prize_amount": score["official_total_prize_amount"],
        "pair_minus_a": score["pair_minus_a"],
        "pair_minus_b": score["pair_minus_b"],
        "status": "SCORED",
    }


def _append_comparison(root: Path, record: Mapping[str, object]) -> bool:
    path = _safe_runtime_path(root, "comparison.jsonl")
    encoded_line = _canonical_bytes(dict(record))
    key = record.get("comparison_key")
    if type(key) is not str:
        raise ShadowRecordConflictError("comparison record key is invalid")
    _ensure_private_directory(path.parent)
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise ShadowRecordConflictError("comparison ledger is not a regular file")
        for raw_line in path.read_bytes().splitlines(keepends=True):
            if not raw_line.strip():
                continue
            try:
                existing = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ShadowRecordConflictError("comparison ledger contains invalid JSON") from exc
            if not isinstance(existing, dict):
                raise ShadowRecordConflictError("comparison ledger contains a non-object row")
            existing_object = cast(Mapping[str, object], existing)
            if existing_object.get("comparison_key") == key:
                if raw_line != encoded_line:
                    raise ShadowRecordConflictError("comparison ledger key has conflicting bytes")
                return False
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | _NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "ab") as handle:
        handle.write(encoded_line)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)
    return True


def _history_from_prediction(prediction: Mapping[str, object]) -> HistorySnapshot:
    cutoff = prediction.get("history_cutoff_draw_number")
    history_sha = prediction.get("history_identity_sha256")
    if type(cutoff) is not str or type(history_sha) is not str:
        raise ShadowRecordConflictError("existing prediction history identity is invalid")
    return HistorySnapshot(
        rows=(),
        cutoff_draw=cutoff,
        cutoff_date="",
        draw_count=0,
        history_sha256=history_sha,
    )


class PairRuleForwardShadow:
    """Run the frozen Big Lotto pair candidates in an isolated shadow root."""

    def __init__(self, root: Path = RUNTIME_SUBROOT, *, freeze_path: Path = FREEZE_PATH) -> None:
        self.root = root
        self.freeze_path = freeze_path

    def load_authority(self) -> ShadowAuthority:
        return load_shadow_authority(self.freeze_path)

    def run_pre_draw(
        self,
        target: PredictionTarget,
        history: HistorySnapshot,
        *,
        observed_at: datetime,
        readiness_deadline: datetime | None = None,
        primary_status: str = "PREDRAW_READY",
        canonical_source_head: str = "UNKNOWN",
    ) -> dict[str, object]:
        """Create or verify only pre-deadline records after primary readiness."""

        _validate_target(target)
        try:
            with ShadowProcessLock(_safe_runtime_path(self.root, SHADOW_LOCK_FILE)):
                return self._run_pre_draw_locked(
                    target,
                    history,
                    observed_at=observed_at,
                    readiness_deadline=readiness_deadline,
                    primary_status=primary_status,
                    canonical_source_head=canonical_source_head,
                )
        except ShadowAlreadyRunning:
            return shadow_health_not_run(
                "ALREADY_RUNNING",
                last_error="isolated shadow lock is held",
                target=target,
                primary_status_observed=primary_status,
                canonical_source_head=canonical_source_head,
            )

    def _run_pre_draw_locked(
        self,
        target: PredictionTarget,
        history: HistorySnapshot,
        *,
        observed_at: datetime,
        readiness_deadline: datetime | None,
        primary_status: str,
        canonical_source_head: str,
    ) -> dict[str, object]:
        observed = _ensure_aware(observed_at, "observed_at").astimezone(UTC)
        deadline = _target_deadline(target, readiness_deadline)
        authority = self.load_authority()
        _write_authority_snapshot(self.root, authority)
        if primary_status != "PREDRAW_READY":
            payload = _health(
                authority,
                status="SKIPPED_PRIMARY_NOT_READY",
                deadline_status="NOT_RUN",
                available=[],
                missing=list(READY_CANDIDATE_IDS),
                last_error=None,
                target=target,
                primary_status_observed=primary_status,
                canonical_source_head=canonical_source_head,
                created_prediction_count=0,
                scored_candidate_count=0,
                consecutive_failures=0,
                extra={
                    "observed_at": _utc_text(observed),
                    "readiness_deadline": _utc_text(deadline),
                },
            )
            _write_health(self.root, payload)
            return payload

        available: list[str] = []
        missing: list[str] = []
        errors: list[str] = []
        created = 0
        component_cache: dict[
            str, tuple[dict[str, object], tuple[tuple[int, ...], ...]] | Exception
        ] = {}

        def component(strategy_id: str) -> tuple[dict[str, object], tuple[tuple[int, ...], ...]]:
            cached = component_cache.get(strategy_id)
            if isinstance(cached, Exception):
                raise cached
            if cached is not None:
                return cached
            try:
                result = _build_component(
                    strategy_id, history=history, target=target, allocation_count=20
                )
            except Exception as exc:
                component_cache[strategy_id] = exc
                raise
            component_cache[strategy_id] = result
            return result

        for candidate in authority.enabled_candidates:
            path = _prediction_path(self.root, target, candidate)
            try:
                existing = _load_existing_status(self.root, authority, candidate, target, history)
                if existing is not None:
                    if existing == "AVAILABLE":
                        available.append(candidate.candidate_id)
                    else:
                        missing.append(candidate.candidate_id)
                    continue
                if observed >= deadline:
                    record = _prediction_record(
                        authority,
                        candidate,
                        target,
                        history,
                        deadline,
                        status="MISSED_DEADLINE_NO_BACKFILL",
                        component_a=_unavailable_component(
                            candidate.strategy_a_id, candidate.a_tickets
                        ),
                        component_b=_unavailable_component(
                            candidate.strategy_b_id, candidate.b_tickets
                        ),
                        composed=(),
                        a_only=(),
                        b_only=(),
                        created_at=observed,
                        canonical_source_head=canonical_source_head,
                    )
                    if _create_or_verify(path, _canonical_bytes(record)):
                        created += 1
                    missing.append(candidate.candidate_id)
                    continue

                component_a_record, ordered_a = component(candidate.strategy_a_id)
                component_b_record, ordered_b = component(candidate.strategy_b_id)
                composed = tuple(ordered_a[: candidate.a_tickets]) + tuple(
                    ordered_b[: candidate.b_tickets]
                )
                a_only = tuple(ordered_a[: candidate.budget])
                b_only = tuple(ordered_b[: candidate.budget])
                if (
                    len(composed) != candidate.budget
                    or len(a_only) != candidate.budget
                    or len(b_only) != candidate.budget
                ):
                    raise PairRuleForwardShadowError(
                        f"{candidate.candidate_id}: allocation does not match budget"
                    )
                record = _prediction_record(
                    authority,
                    candidate,
                    target,
                    history,
                    deadline,
                    status="AVAILABLE",
                    component_a=_project_component(
                        component_a_record, ordered_a, candidate.a_tickets
                    ),
                    component_b=_project_component(
                        component_b_record, ordered_b, candidate.b_tickets
                    ),
                    composed=composed,
                    a_only=a_only,
                    b_only=b_only,
                    created_at=observed,
                    canonical_source_head=canonical_source_head,
                )
                if _create_or_verify(path, _canonical_bytes(record)):
                    created += 1
                available.append(candidate.candidate_id)
            except Exception as exc:
                errors.append(f"{candidate.candidate_id}: {type(exc).__name__}: {exc}")
                if (
                    candidate.candidate_id not in missing
                    and candidate.candidate_id not in available
                ):
                    missing.append(candidate.candidate_id)

        deadline_status = (
            "READY"
            if observed < deadline and not missing
            else "OPEN"
            if observed < deadline
            else "CLOSED"
            if not missing
            else "MISSED_DEADLINE_NO_BACKFILL"
        )
        previous_failures = _previous_failure_count(self.root)
        payload = _health(
            authority,
            status="PREDRAW_COMPLETE" if not errors else "PREDRAW_PARTIAL",
            deadline_status=deadline_status,
            available=available,
            missing=missing,
            last_error=None if not errors else "; ".join(errors),
            target=target,
            primary_status_observed=primary_status,
            canonical_source_head=canonical_source_head,
            created_prediction_count=created,
            scored_candidate_count=0,
            consecutive_failures=0 if not errors else previous_failures + 1,
            extra={
                "observed_at": _utc_text(observed),
                "readiness_deadline": _utc_text(deadline),
                "errors": errors,
            },
        )
        _write_health(self.root, payload)
        return payload

    def run_post_draw(
        self,
        target: PredictionTarget,
        official_outcome: Mapping[str, object] | None,
        *,
        observed_at: datetime,
        history: HistorySnapshot | None = None,
        primary_status: str = "COMPLETE",
        canonical_source_head: str = "UNKNOWN",
    ) -> dict[str, object]:
        """Score only existing PRE_DRAW shadow records after primary completion."""

        _validate_target(target)
        try:
            with ShadowProcessLock(_safe_runtime_path(self.root, SHADOW_LOCK_FILE)):
                return self._run_post_draw_locked(
                    target,
                    official_outcome,
                    observed_at=observed_at,
                    history=history,
                    primary_status=primary_status,
                    canonical_source_head=canonical_source_head,
                )
        except ShadowAlreadyRunning:
            return shadow_health_not_run(
                "ALREADY_RUNNING",
                last_error="isolated shadow lock is held",
                target=target,
                primary_status_observed=primary_status,
                canonical_source_head=canonical_source_head,
            )

    def _run_post_draw_locked(
        self,
        target: PredictionTarget,
        official_outcome: Mapping[str, object] | None,
        *,
        observed_at: datetime,
        history: HistorySnapshot | None,
        primary_status: str,
        canonical_source_head: str,
    ) -> dict[str, object]:
        observed = _ensure_aware(observed_at, "observed_at").astimezone(UTC)
        deadline = _target_deadline(target, None)
        authority = self.load_authority()
        _write_authority_snapshot(self.root, authority)
        if primary_status not in {"COMPLETE", "WAITING_FOR_OUTCOME"}:
            payload = _health(
                authority,
                status="SKIPPED_PRIMARY_STATUS",
                deadline_status="NOT_RUN",
                available=[],
                missing=list(READY_CANDIDATE_IDS),
                last_error=None,
                target=target,
                primary_status_observed=primary_status,
                canonical_source_head=canonical_source_head,
                created_prediction_count=0,
                scored_candidate_count=0,
                consecutive_failures=0,
                extra={
                    "observed_at": _utc_text(observed),
                    "readiness_deadline": _utc_text(deadline),
                },
            )
            _write_health(self.root, payload)
            return payload

        if official_outcome is None:
            payload = _health(
                authority,
                status="WAITING_FOR_OUTCOME",
                deadline_status="WAITING_FOR_OUTCOME",
                available=[],
                missing=list(READY_CANDIDATE_IDS),
                last_error=None,
                target=target,
                primary_status_observed=primary_status,
                canonical_source_head=canonical_source_head,
                created_prediction_count=0,
                scored_candidate_count=0,
                consecutive_failures=0,
                extra={
                    "observed_at": _utc_text(observed),
                    "readiness_deadline": _utc_text(deadline),
                },
            )
            _write_health(self.root, payload)
            return payload

        if primary_status != "COMPLETE":
            payload = _health(
                authority,
                status="WAITING_FOR_PRIMARY_COMPLETION",
                deadline_status="WAITING_FOR_PRIMARY_COMPLETION",
                available=[],
                missing=list(READY_CANDIDATE_IDS),
                last_error=None,
                target=target,
                primary_status_observed=primary_status,
                canonical_source_head=canonical_source_head,
                created_prediction_count=0,
                scored_candidate_count=0,
                consecutive_failures=0,
                extra={
                    "observed_at": _utc_text(observed),
                    "readiness_deadline": _utc_text(deadline),
                },
            )
            _write_health(self.root, payload)
            return payload

        if official_outcome.get("draw_number") != target.draw_number:
            raise ValueError("official outcome draw identity conflicts with the target")
        _official_numbers(official_outcome)
        available: list[str] = []
        missing: list[str] = []
        scored: list[str] = []
        errors: list[str] = []
        for candidate in authority.enabled_candidates:
            prediction_path = _prediction_path(self.root, target, candidate)
            if not prediction_path.exists():
                missing.append(candidate.candidate_id)
                continue
            try:
                prediction = _read_object(prediction_path)
                verification_history = (
                    history if history is not None else _history_from_prediction(prediction)
                )
                status = _verify_existing_prediction(
                    prediction, authority, candidate, target, verification_history
                )
                if status != "AVAILABLE":
                    missing.append(candidate.candidate_id)
                    continue
                available.append(candidate.candidate_id)
                prediction_sha256 = _sha256_bytes(prediction_path.read_bytes())
                score = _score_record(
                    authority, candidate, target, prediction, prediction_sha256, official_outcome
                )
                _create_or_verify(
                    _score_path(self.root, target, candidate), _canonical_bytes(score)
                )
                _append_comparison(
                    self.root, _comparison_record(authority, candidate, target, score)
                )
                scored.append(candidate.candidate_id)
            except Exception as exc:
                errors.append(f"{candidate.candidate_id}: {type(exc).__name__}: {exc}")

        payload = _health(
            authority,
            status="POSTDRAW_COMPLETE" if not errors else "POSTDRAW_PARTIAL",
            deadline_status="SCORED"
            if not missing and not errors
            else "WAITING_FOR_SHADOW_PREDICTIONS",
            available=available,
            missing=missing,
            last_error=None if not errors else "; ".join(errors),
            target=target,
            primary_status_observed=primary_status,
            canonical_source_head=canonical_source_head,
            created_prediction_count=0,
            scored_candidate_count=len(scored),
            consecutive_failures=0 if not errors else _previous_failure_count(self.root) + 1,
            extra={
                "observed_at": _utc_text(observed),
                "readiness_deadline": _utc_text(deadline),
                "scored_enabled_candidate_ids": scored,
                "official_outcome_identity_sha256": _official_outcome_identity(official_outcome),
                "errors": errors,
            },
        )
        _write_health(self.root, payload)
        return payload


def run_pre_draw_shadow(
    target: PredictionTarget,
    history: HistorySnapshot,
    *,
    observed_at: datetime,
    readiness_deadline: datetime | None = None,
    primary_status: str = "PREDRAW_READY",
    canonical_source_head: str = "UNKNOWN",
    root: Path = RUNTIME_SUBROOT,
    freeze_path: Path = FREEZE_PATH,
) -> dict[str, object]:
    """Functional wrapper for the Goal-C scheduler pre-draw hook."""

    return PairRuleForwardShadow(root, freeze_path=freeze_path).run_pre_draw(
        target,
        history,
        observed_at=observed_at,
        readiness_deadline=readiness_deadline,
        primary_status=primary_status,
        canonical_source_head=canonical_source_head,
    )


def run_post_draw_shadow(
    target: PredictionTarget,
    official_outcome: Mapping[str, object] | None,
    *,
    observed_at: datetime,
    history: HistorySnapshot | None = None,
    primary_status: str = "COMPLETE",
    canonical_source_head: str = "UNKNOWN",
    root: Path = RUNTIME_SUBROOT,
    freeze_path: Path = FREEZE_PATH,
) -> dict[str, object]:
    """Functional wrapper for the Goal-C scheduler post-draw hook."""

    return PairRuleForwardShadow(root, freeze_path=freeze_path).run_post_draw(
        target,
        official_outcome,
        observed_at=observed_at,
        history=history,
        primary_status=primary_status,
        canonical_source_head=canonical_source_head,
    )


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "EQUIVALENT_GROUP_R3_R6_B20",
    "EQUIVALENT_GROUP_R5_B10",
    "EXPECTED_CANDIDATE_SET_SHA256",
    "EXPECTED_FREEZE_SHA256",
    "FREEZE_PATH",
    "FROZEN_CANDIDATE_IDS",
    "MIGRATION_BLOCKED_CANDIDATE_IDS",
    "PREDICTION_SCHEMA_VERSION",
    "READINESS_ARTIFACT_HASHES",
    "READY_CANDIDATE_IDS",
    "RUNTIME_REGISTRY_SCHEMA_VERSION",
    "RUNTIME_SUBROOT",
    "SCORE_SCHEMA_VERSION",
    "SHADOW_HEALTH_NAMESPACE",
    "PairRuleForwardShadow",
    "PairRuleForwardShadowError",
    "ReadinessBundle",
    "ShadowAlreadyRunning",
    "ShadowAuthority",
    "ShadowAuthorityError",
    "ShadowProcessLock",
    "ShadowRecordConflictError",
    "load_shadow_authority",
    "run_post_draw_shadow",
    "run_pre_draw_shadow",
    "shadow_health_not_run",
]
