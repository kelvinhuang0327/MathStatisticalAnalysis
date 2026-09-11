"""Read-only Authority B binding and strict consensus promotion.

The promotion boundary consumes one immutable PR #284 forecast payload and its
already-materialized source stream files.  It never imports strategy adapters,
re-runs aggregation, writes the draw database, or writes candidate artifacts.
The only state-changing operation is delegated to ``SQLiteResearchRepository``.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from lottolab.application.future_draw_identity import ScheduledDrawIdentityRecord
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import OutcomePresenceAttestation
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.domain.research_live_forecast import (
    CANONICAL_CONSENSUS,
    CONSENSUS_AUTHORITY_B_PAYLOAD_SHA256,
    CONSENSUS_AUTHORITY_B_SCOPE,
    CONSENSUS_CORRELATED_FAMILY_POLICY,
    CONSENSUS_DECISION_RANKING,
    CONSENSUS_IMPLEMENTATION_COMMIT,
    CONSENSUS_IMPLEMENTATION_SOURCE_HASHES,
    CONSENSUS_IMPLEMENTATION_TREE,
    CONSENSUS_MISSING,
    CONSENSUS_PROVENANCE_SCHEMA_VERSION,
    CONSENSUS_SCHEMA_VERSION,
    CONSENSUS_STREAM,
    CONSENSUS_STREAM_SPECS,
    CONSENSUS_STREAM_VERSION,
    CONSENSUS_TARGET_DATA_CUTOFF,
    CONSENSUS_TARGET_DRAW_DATE,
    CONSENSUS_TARGET_DRAW_NUMBER,
    CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
    CONSENSUS_TARGET_HISTORY_SHA256,
    CONSENSUS_TARGET_LOTTERY_TYPE,
    CONSENSUS_TARGET_SCHEDULED_AT,
    CONSENSUS_TARGET_TIMEZONE,
    CONSENSUS_UPSTREAM_TASK_ID,
    ORIGINAL_FIELDS,
    LiveForecastInput,
    canonical_json,
    digest,
    utc_text,
)
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.persistence.research_repository import (
    LiveForecastCurrentResult,
    LiveForecastResult,
    ResearchRepositoryError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import ResearchDataPaths
from lottolab.infrastructure.pre_outcome_target_operational import (
    SQLiteOfficialOutcomePresenceProbe,
)

TARGET_LOTTERY_TYPE = CONSENSUS_TARGET_LOTTERY_TYPE
TARGET_DRAW_NUMBER = CONSENSUS_TARGET_DRAW_NUMBER
TARGET_DRAW_DATE = CONSENSUS_TARGET_DRAW_DATE
TARGET_SCHEDULED_AT = CONSENSUS_TARGET_SCHEDULED_AT
TARGET_TIMEZONE = CONSENSUS_TARGET_TIMEZONE
TARGET_DATA_CUTOFF = CONSENSUS_TARGET_DATA_CUTOFF
TARGET_HISTORY_SHA256 = CONSENSUS_TARGET_HISTORY_SHA256
EXPECTED_IMPLEMENTATION_COMMIT = CONSENSUS_IMPLEMENTATION_COMMIT
EXPECTED_IMPLEMENTATION_TREE = CONSENSUS_IMPLEMENTATION_TREE
EXPECTED_IMPLEMENTATION_SOURCE_HASHES = CONSENSUS_IMPLEMENTATION_SOURCE_HASHES
EXPECTED_CANDIDATE_SHA256 = CONSENSUS_AUTHORITY_B_PAYLOAD_SHA256
EXPECTED_OPERATION_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1"
)
EXPECTED_CANDIDATE_LOCATOR = EXPECTED_OPERATION_ROOT / (
    "forecasts/115000087/B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS/1.0.0/"
    "final_forecast_payload.json"
)
PROMOTION_DEADLINE = datetime.fromisoformat(TARGET_SCHEDULED_AT)
CONSENSUS_SCOPE = CONSENSUS_AUTHORITY_B_SCOPE

BLOCKER_SCHEDULE_AUTHORITY_MISSING = "IMMUTABLE_SCHEDULE_AUTHORITY_MISSING"
BLOCKER_TARGET_CHANGED = "TARGET_CHANGED"
BLOCKER_SCHEDULED_TIME_CHANGED = "SCHEDULED_TIME_CHANGED"
BLOCKER_SCHEDULE_HASH_CHANGED = "SCHEDULE_HASH_CHANGED"
BLOCKER_SCHEDULE_HASH_NOT_BOUND = "SCHEDULE_HASH_NOT_BOUND"
BLOCKER_OFFICIAL_OUTCOME_PRESENT = "OFFICIAL_OUTCOME_PRESENT"
BLOCKER_OFFICIAL_OUTCOME_UNKNOWN = "OFFICIAL_OUTCOME_UNKNOWN"
BLOCKER_DEADLINE_REACHED = "DEADLINE_REACHED"
BLOCKER_DEADLINE_PASSED = "DEADLINE_PASSED"
BLOCKER_PRE_DRAW_REQUIRED = "PRE_DRAW_REQUIRED"


class _ScheduleReader(Protocol):
    def get_scheduled_draw(
        self,
        lottery_type: LotteryType,
        draw_number: str,
    ) -> ScheduledDrawIdentityRecord | None: ...


class _OutcomeProbe(Protocol):
    def probe(
        self,
        target: ObservationTarget,
        *,
        as_of: datetime,
    ) -> OutcomePresenceAttestation: ...


class ConsensusCandidateError(ValueError):
    """The candidate or one of its immutable source files is invalid."""


class CanonicalEligibilityError(ResearchRepositoryError):
    """The current schedule/outcome gate blocks promotion."""

    def __init__(self, blockers: tuple[str, ...]) -> None:
        self.blockers = blockers
        super().__init__("canonical consensus promotion is blocked: " + ", ".join(blockers))


@dataclass(frozen=True, slots=True)
class CanonicalConsensusCandidate:
    """Byte-preserving, SHA-bound view of the Authority B payload."""

    candidate_locator: Path
    candidate_sha256: str
    candidate_bytes: bytes
    payload: dict[str, object]
    source_root: Path

    @property
    def target(self) -> dict[str, object]:
        return {
            "lottery_type": TARGET_LOTTERY_TYPE,
            "target_draw_number": TARGET_DRAW_NUMBER,
            "target_draw_date": TARGET_DRAW_DATE,
            "scheduled_at": TARGET_SCHEDULED_AT,
            "timezone": TARGET_TIMEZONE,
            "data_cutoff": TARGET_DATA_CUTOFF,
            "forecast_horizon": 1,
            "history_draw_count": CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
            "causal_history_sha256": TARGET_HISTORY_SHA256,
        }

    @property
    def scope(self) -> tuple[str, str, str, str, str]:
        return CONSENSUS_SCOPE

    @property
    def stream_inputs(self) -> list[dict[str, object]]:
        return cast(list[dict[str, object]], self.payload["stream_inputs"])

    def build_consensus_provenance(self, *, schedule_authority_sha256: str) -> str:
        _require_sha(schedule_authority_sha256, "schedule_authority_sha256")
        implementation = {
            "commit": self.payload["implementation_commit"],
            "tree": self.payload["implementation_tree"],
            "source_hashes": self.payload["implementation_source_hashes"],
        }
        production = {
            "task_id": self.payload["task_id"],
            "upstream_task_id": self.payload["upstream_task_id"],
            "created_at": self.payload["created_at"],
            "pre_outcome_temporal_integrity": self.payload["pre_outcome_temporal_integrity"],
            "stream_input_manifest_sha256": self.payload["stream_input_manifest_sha256"],
            "implementation": implementation,
        }
        target = {
            "lottery_type": TARGET_LOTTERY_TYPE,
            "draw_number": TARGET_DRAW_NUMBER,
            "draw_date": TARGET_DRAW_DATE,
            "scheduled_at": TARGET_SCHEDULED_AT,
            "timezone": TARGET_TIMEZONE,
            "cutoff": TARGET_DATA_CUTOFF,
            "history_draw_count": CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
            "causal_history_sha256": TARGET_HISTORY_SHA256,
            "temporal_class": "PRE_DRAW",
            "target_result_used": False,
            "schedule_authority_sha256": schedule_authority_sha256,
        }
        return canonical_json(
            {
                "algorithm": {
                    "algorithm_id": "build_canonical_consensus",
                    "method_id": self.payload["aggregation_method_id"],
                    "method_version": self.payload["aggregation_method_version"],
                    "aggregation_unit": self.payload["aggregation_unit"],
                    "weight_policy": self.payload["weight_policy"],
                    "correlated_family_policy": self.payload["correlated_family_policy"],
                    "tie_break": self.payload["tie_break"],
                    "score_denominator": self.payload["score_denominator"],
                    "decision_ranking_formula": self.payload["decision_ranking_formula"],
                },
                "aggregation_reexecution": "NO",
                "candidate": {
                    "locator": str(self.candidate_locator),
                    "sha256": self.candidate_sha256,
                },
                "contract_version": CONSENSUS_PROVENANCE_SCHEMA_VERSION,
                "final_decision_ranking": self.payload["final_decision_ranking"],
                "final_recommended_output": self.payload["final_recommended_output"],
                "generated_at": self.payload["created_at"],
                "implementation": implementation,
                "production": production,
                "source_provenance": {
                    "locator": str(self.candidate_locator),
                    "sha256": self.candidate_sha256,
                    "document": production,
                },
                "strategy_reexecution": "NO",
                "streams": self.stream_inputs,
                "target": target,
            }
        )

    def build_forecast(
        self,
        request: PromotionRequest,
        *,
        schedule_authority_sha256: str | None = None,
    ) -> LiveForecastInput:
        _validate_loaded_candidate(self)
        selected_schedule_hash = request.schedule_authority_sha256
        if schedule_authority_sha256 is not None:
            _require_sha(schedule_authority_sha256, "schedule_authority_sha256")
            if schedule_authority_sha256 != selected_schedule_hash:
                raise ValueError("schedule authority hash differs from the promotion request")
        target = self.target
        target["schedule_authority_sha256"] = selected_schedule_hash
        forecast = LiveForecastInput(
            request_id=request.request_id,
            request_sha256=request.request_sha256,
            provenance_class=CANONICAL_CONSENSUS,
            forecast_stream_id=CONSENSUS_STREAM,
            forecast_stream_version=CONSENSUS_STREAM_VERSION,
            target_json=canonical_json(target),
            payload_bytes=self.candidate_bytes,
            source_locator=str(self.candidate_locator),
            original_execution_json=canonical_json(dict.fromkeys(ORIGINAL_FIELDS)),
            missing_provenance_json=canonical_json(CONSENSUS_MISSING),
            import_execution_json=request.import_execution_json(),
            consensus_provenance_json=self.build_consensus_provenance(
                schedule_authority_sha256=selected_schedule_hash
            ),
        )
        forecast.validate()
        return forecast


@dataclass(frozen=True, slots=True)
class PromotionRequest:
    """Stable caller identity plus the activation-time schedule binding."""

    request_id: str
    request_sha256: str
    expected_current_version: int
    schedule_authority_sha256: str
    authorization_evidence_reference: str
    promotion_executor_identity: str
    execution_source_id: str
    execution_source_version: str
    promotion_attempted_at: datetime | None = None
    command_runtime_identity: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_sha(self.request_sha256, "request_sha256")
        _require_sha(self.schedule_authority_sha256, "schedule_authority_sha256")
        if type(self.expected_current_version) is not int or self.expected_current_version < 0:
            raise ValueError("expected_current_version must be a non-negative integer")
        for value, label in (
            (self.authorization_evidence_reference, "authorization_evidence_reference"),
            (self.promotion_executor_identity, "promotion_executor_identity"),
            (self.execution_source_id, "execution_source_id"),
            (self.execution_source_version, "execution_source_version"),
        ):
            _require_text(value, label)
        if self.promotion_attempted_at is not None:
            _require_aware(self.promotion_attempted_at, "promotion_attempted_at")
        if self.command_runtime_identity is not None:
            _validate_runtime_identity(self.command_runtime_identity)

    def import_execution_json(self) -> str:
        attempted_at = self.promotion_attempted_at or datetime.now(UTC)
        runtime = self.command_runtime_identity or {
            "python": platform.python_version(),
            "executable": sys.executable,
            "command": list(sys.argv),
        }
        return canonical_json(
            {
                "activation_event": "CANONICAL_CONSENSUS_PROMOTION_IMPORT",
                "aggregation_execution": "NOT_PERFORMED",
                "authorization_evidence_reference": self.authorization_evidence_reference,
                "command_runtime_identity": runtime,
                "execution_source": {
                    "source_id": self.execution_source_id,
                    "source_version": self.execution_source_version,
                },
                "native_generation": "NOT_PERFORMED",
                "promotion_attempted_at": utc_text(_as_utc(attempted_at)),
                "promotion_executor_identity": self.promotion_executor_identity,
                "schedule_authority_sha256": self.schedule_authority_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class CanonicalEligibilityResult:
    """Read-only gate result, including exact blocker names for CLI use."""

    eligible: bool
    blockers: tuple[str, ...]
    checked_at: datetime
    schedule_hash: str | None = None
    outcome_presence: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "blockers": list(self.blockers),
            "checked_at": utc_text(_as_utc(self.checked_at)),
            "schedule_hash": self.schedule_hash,
            "outcome_presence": self.outcome_presence,
        }


class CanonicalConsensusEligibilityGate:
    """Evaluate schedule and outcome authority without changing either store."""

    def __init__(
        self,
        draw_paths: LocalDataPaths | None = None,
        *,
        schedule_reader: _ScheduleReader | None = None,
        outcome_probe: _OutcomeProbe | None = None,
    ) -> None:
        self._schedule_reader: _ScheduleReader | None = (
            schedule_reader
            if schedule_reader is not None
            else None
            if draw_paths is None
            else SQLiteFutureDrawIdentityReader(draw_paths)
        )
        self._outcome_probe: _OutcomeProbe | None = (
            outcome_probe
            if outcome_probe is not None
            else None
            if draw_paths is None
            else SQLiteOfficialOutcomePresenceProbe(draw_paths)
        )

    def check(
        self,
        candidate_target: Mapping[str, object] | None = None,
        *,
        now: datetime | None = None,
    ) -> CanonicalEligibilityResult:
        checked_at = datetime.now(UTC) if now is None else now
        _require_aware(checked_at, "now")
        checked_at = _as_utc(checked_at)
        blockers: list[str] = []
        target = _target_for_gate(candidate_target)
        for key, expected, blocker in (
            ("lottery_type", TARGET_LOTTERY_TYPE, BLOCKER_TARGET_CHANGED),
            ("target_draw_number", TARGET_DRAW_NUMBER, BLOCKER_TARGET_CHANGED),
            ("target_draw_date", TARGET_DRAW_DATE, BLOCKER_TARGET_CHANGED),
            ("scheduled_at", TARGET_SCHEDULED_AT, BLOCKER_SCHEDULED_TIME_CHANGED),
            ("timezone", TARGET_TIMEZONE, BLOCKER_SCHEDULED_TIME_CHANGED),
            ("data_cutoff", TARGET_DATA_CUTOFF, BLOCKER_TARGET_CHANGED),
        ):
            if target.get(key) != expected:
                blockers.append(blocker)
        if target.get("temporal_class") is not None and target.get("temporal_class") != "PRE_DRAW":
            blockers.append(BLOCKER_PRE_DRAW_REQUIRED)
        if (
            target.get("target_result_used") is not None
            and target.get("target_result_used") is not False
        ):
            blockers.append(BLOCKER_OFFICIAL_OUTCOME_PRESENT)

        candidate_schedule_hash = target.get("schedule_authority_sha256")
        candidate_hash_valid = False
        if candidate_schedule_hash is None:
            blockers.append(BLOCKER_SCHEDULE_HASH_NOT_BOUND)
        elif not isinstance(candidate_schedule_hash, str):
            blockers.append(BLOCKER_SCHEDULE_HASH_CHANGED)
        else:
            try:
                _require_sha(candidate_schedule_hash, "schedule_authority_sha256")
            except ValueError:
                blockers.append(BLOCKER_SCHEDULE_HASH_CHANGED)
            else:
                candidate_hash_valid = True

        record: ScheduledDrawIdentityRecord | None = None
        outcome_presence: str | None = None
        schedule_hash: str | None = None
        if self._schedule_reader is None:
            blockers.append(BLOCKER_SCHEDULE_AUTHORITY_MISSING)
        else:
            try:
                record = self._schedule_reader.get_scheduled_draw(
                    LotteryType.BIG_LOTTO,
                    TARGET_DRAW_NUMBER,
                )
            except Exception:
                blockers.append(BLOCKER_SCHEDULE_AUTHORITY_MISSING)
            if record is None:
                blockers.append(BLOCKER_SCHEDULE_AUTHORITY_MISSING)
            else:
                announcement = record.announcement
                if (
                    announcement.target.lottery_type.value != TARGET_LOTTERY_TYPE
                    or announcement.target.draw_number != TARGET_DRAW_NUMBER
                    or announcement.target.draw_date.isoformat() != TARGET_DRAW_DATE
                ):
                    blockers.append(BLOCKER_TARGET_CHANGED)
                if (
                    announcement.scheduled_at != PROMOTION_DEADLINE
                    or announcement.schedule_timezone != TARGET_TIMEZONE
                ):
                    blockers.append(BLOCKER_SCHEDULED_TIME_CHANGED)
                schedule_hash = record.immutable_schedule_sha256
                if schedule_hash is None:
                    blockers.append(BLOCKER_SCHEDULE_AUTHORITY_MISSING)
                else:
                    try:
                        _require_sha(schedule_hash, "immutable_schedule_sha256")
                    except ValueError:
                        blockers.append(BLOCKER_SCHEDULE_AUTHORITY_MISSING)
                    else:
                        if candidate_hash_valid and candidate_schedule_hash != schedule_hash:
                            blockers.append(BLOCKER_SCHEDULE_HASH_CHANGED)
                if self._outcome_probe is None:
                    blockers.append(BLOCKER_OFFICIAL_OUTCOME_UNKNOWN)
                else:
                    try:
                        attestation = self._outcome_probe.probe(
                            announcement.target,
                            as_of=checked_at,
                        )
                        presence = getattr(attestation, "presence", None)
                        presence_value = getattr(presence, "value", presence)
                        if presence_value == OutcomePresenceAtPrediction.PRESENT.value:
                            blockers.append(BLOCKER_OFFICIAL_OUTCOME_PRESENT)
                        elif presence_value != OutcomePresenceAtPrediction.ABSENT.value:
                            blockers.append(BLOCKER_OFFICIAL_OUTCOME_UNKNOWN)
                        outcome_presence = cast(str, presence_value)
                    except Exception:
                        blockers.append(BLOCKER_OFFICIAL_OUTCOME_UNKNOWN)

        deadline = _as_utc(PROMOTION_DEADLINE)
        if checked_at == deadline:
            blockers.append(BLOCKER_DEADLINE_REACHED)
        elif checked_at > deadline:
            blockers.append(BLOCKER_DEADLINE_PASSED)
        unique_blockers = tuple(dict.fromkeys(blockers))
        return CanonicalEligibilityResult(
            eligible=not unique_blockers,
            blockers=unique_blockers,
            checked_at=checked_at,
            schedule_hash=schedule_hash,
            outcome_presence=outcome_presence,
        )

    def assert_eligible(
        self,
        candidate_target: Mapping[str, object] | None = None,
        *,
        now: datetime | None = None,
    ) -> CanonicalEligibilityResult:
        result = self.check(candidate_target, now=now)
        if not result.eligible:
            raise CanonicalEligibilityError(result.blockers)
        return result


def load_consensus_candidate(
    candidate_locator: str | Path,
    *,
    candidate_sha256: str = EXPECTED_CANDIDATE_SHA256,
    source_root: str | Path | None = None,
) -> CanonicalConsensusCandidate:
    """Load and verify the exact Authority B candidate without writing files."""

    candidate_path = _regular_path(candidate_locator, "candidate_locator")
    if candidate_path != EXPECTED_CANDIDATE_LOCATOR:
        raise ConsensusCandidateError("candidate locator is not the Authority B artifact")
    _require_sha(candidate_sha256, "candidate_sha256")
    if candidate_sha256 != EXPECTED_CANDIDATE_SHA256:
        raise ConsensusCandidateError("candidate SHA-256 is not the Authority B identity")
    candidate_bytes, actual_candidate_sha = _read_hashed(candidate_path)
    if actual_candidate_sha != EXPECTED_CANDIDATE_SHA256:
        raise ConsensusCandidateError("candidate SHA-256 does not match Authority B")
    if actual_candidate_sha != candidate_sha256:
        raise ConsensusCandidateError("candidate SHA-256 does not match the requested identity")
    payload = _json_object(candidate_bytes, "candidate payload")
    _validate_payload_contract(payload)
    selected_source_root = (
        EXPECTED_OPERATION_ROOT
        if source_root is None
        else _absolute_directory(source_root, "source_root")
    )
    if selected_source_root != EXPECTED_OPERATION_ROOT:
        raise ConsensusCandidateError("source_root is not the Authority B operation root")
    _validate_source_manifest(selected_source_root, payload["stream_inputs"])
    return CanonicalConsensusCandidate(
        candidate_locator=candidate_path,
        candidate_sha256=actual_candidate_sha,
        candidate_bytes=candidate_bytes,
        payload=payload,
        source_root=selected_source_root,
    )


def _validate_loaded_candidate(candidate: CanonicalConsensusCandidate) -> None:
    if (
        candidate.candidate_locator != EXPECTED_CANDIDATE_LOCATOR
        or candidate.candidate_sha256 != EXPECTED_CANDIDATE_SHA256
        or candidate.source_root != EXPECTED_OPERATION_ROOT
    ):
        raise ConsensusCandidateError("candidate is not the Authority B artifact")
    actual_sha = hashlib.sha256(candidate.candidate_bytes).hexdigest()
    if actual_sha != EXPECTED_CANDIDATE_SHA256:
        raise ConsensusCandidateError("candidate bytes are not the Authority B artifact")
    current_bytes, current_sha = _read_hashed(candidate.candidate_locator)
    if current_sha != EXPECTED_CANDIDATE_SHA256 or current_bytes != candidate.candidate_bytes:
        raise ConsensusCandidateError("candidate changed after it was loaded")
    payload = _json_object(candidate.candidate_bytes, "candidate payload")
    if payload != candidate.payload:
        raise ConsensusCandidateError("candidate payload view does not match its raw bytes")
    _validate_payload_contract(payload)
    _validate_source_manifest(candidate.source_root, payload["stream_inputs"])


def promote_consensus_candidate(
    database_path: Path,
    candidate: CanonicalConsensusCandidate,
    request: PromotionRequest,
    *,
    eligibility_gate: CanonicalConsensusEligibilityGate,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> LiveForecastResult:
    """Promote through the repository's strict writer, never through ad-hoc SQL."""

    paths = _research_paths(database_path)
    forecast = candidate.build_forecast(request)

    def current_eligible() -> bool:
        result = eligibility_gate.check(forecast.target, now=_as_utc(clock()))
        return result.eligible and result.schedule_hash == request.schedule_authority_sha256

    repository = SQLiteResearchRepository(paths, initialize=False)
    return repository.commit_consensus_promotion(
        forecast,
        expected_current_version=request.expected_current_version,
        current_eligible=current_eligible,
        clock=clock,
        idempotency_key=request.request_id,
    )


def read_current_consensus(database_path: Path) -> LiveForecastCurrentResult | None:
    """Read the exact current consensus pointer; never infer from history."""

    repository = SQLiteResearchRepository(_research_paths(database_path), initialize=False)
    return repository.read_current_consensus()


_EXPECTED_PAYLOAD_KEYS = frozenset(
    {
        "aggregation_contract_approved_at",
        "aggregation_contract_review_id",
        "aggregation_method_id",
        "aggregation_method_version",
        "aggregation_unit",
        "correlated_family_policy",
        "created_at",
        "decision_ranking_formula",
        "exact_stream_ids",
        "final_decision_ranking",
        "final_recommended_output",
        "history_caveat",
        "history_draw_count",
        "history_sha256",
        "implementation_commit",
        "implementation_source_hashes",
        "implementation_tree",
        "lottery_type",
        "max_data_cutoff",
        "pre_outcome_temporal_integrity",
        "scheduled_at",
        "schema_version",
        "score_denominator",
        "stream_count",
        "stream_input_manifest_sha256",
        "stream_inputs",
        "target_draw",
        "target_result_used",
        "task_id",
        "tie_break",
        "upstream_task_id",
        "weight_policy",
    }
)
_EXPECTED_SOURCE_KEYS = frozenset(
    {
        "availability",
        "draw_date",
        "draw_number",
        "history_caveat",
        "history_cutoff",
        "history_draw_count",
        "history_sha256",
        "lottery_type",
        "native_ticket_count",
        "pinned_implementation",
        "prediction_created_at",
        "prediction_run_id",
        "prediction_temporal_class",
        "producer_fingerprint",
        "scheduled_at",
        "schema_version",
        "strategy_config",
        "strategy_id",
        "strategy_version",
        "task_id",
        "tickets",
        "unavailable_reason",
    }
)
_FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "outcome",
        "result",
        "score",
        "official_outcome",
        "winning_numbers",
        "main_numbers",
        "special_number",
    }
)


def _validate_payload_contract(payload: dict[str, object]) -> None:
    if set(payload) != set(_EXPECTED_PAYLOAD_KEYS):
        raise ConsensusCandidateError("Authority B payload field inventory mismatch")
    expected_scalars = {
        "schema_version": CONSENSUS_SCHEMA_VERSION,
        "aggregation_contract_review_id": "B649_11_STREAM_CANONICAL_AGGREGATION_CTO_REVIEW_R1",
        "aggregation_contract_approved_at": "2026-09-10T05:50:29Z",
        "aggregation_method_id": CONSENSUS_STREAM,
        "aggregation_method_version": CONSENSUS_STREAM_VERSION,
        "aggregation_unit": "NUMBER_LEVEL",
        "correlated_family_policy": CONSENSUS_CORRELATED_FAMILY_POLICY,
        "weight_policy": "EQUAL_STREAM_WEIGHT",
        "tie_break": "SUPPORT_UNITS_DESC_NUMBER_ASC",
        "score_denominator": 66,
        "lottery_type": TARGET_LOTTERY_TYPE,
        "history_caveat": "YES",
        "history_draw_count": CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
        "history_sha256": TARGET_HISTORY_SHA256,
        "pre_outcome_temporal_integrity": "PASS",
        "target_result_used": False,
        "stream_count": len(CONSENSUS_STREAM_SPECS),
        "task_id": "B649_11_STREAM_CANONICAL_AGGREGATION_IMPLEMENT_AND_MATERIALIZE_115000087_R1",
        "upstream_task_id": CONSENSUS_UPSTREAM_TASK_ID,
        "decision_ranking_formula": (
            "U(n)=sum_i((6/k_i)*c_i(n)); rank by U(n) descending, then number ascending; "
            "each stream has equal weight and c_i(n) counts native ticket positions containing n"
        ),
    }
    for key, expected in expected_scalars.items():
        if payload.get(key) != expected:
            raise ConsensusCandidateError(f"Authority B payload {key} mismatch")
    if payload.get("target_draw") != {
        "draw_date": TARGET_DRAW_DATE,
        "draw_number": TARGET_DRAW_NUMBER,
    }:
        raise ConsensusCandidateError("Authority B target identity mismatch")
    if payload.get("max_data_cutoff") != {
        "draw_date": "2026-09-08",
        "draw_number": TARGET_DATA_CUTOFF,
    }:
        raise ConsensusCandidateError("Authority B cutoff identity mismatch")
    _timestamp(payload.get("created_at"), "created_at")
    if payload.get("scheduled_at") != TARGET_SCHEDULED_AT:
        raise ConsensusCandidateError("Authority B schedule identity mismatch")
    _require_sha(payload.get("history_sha256"), "history_sha256")
    _require_sha(payload.get("stream_input_manifest_sha256"), "stream_input_manifest_sha256")
    streams = _validate_stream_manifest(payload.get("stream_inputs"), "stream_inputs")
    if payload.get("exact_stream_ids") != [spec[0] for spec in CONSENSUS_STREAM_SPECS]:
        raise ConsensusCandidateError("Authority B stream id inventory mismatch")
    if payload.get("stream_input_manifest_sha256") != digest(streams):
        raise ConsensusCandidateError("Authority B stream manifest digest mismatch")
    expected_sources = [
        {"path": path, "sha256": source_sha}
        for path, source_sha in EXPECTED_IMPLEMENTATION_SOURCE_HASHES
    ]
    if payload.get("implementation_source_hashes") != expected_sources:
        raise ConsensusCandidateError("Authority B implementation source lineage mismatch")
    if payload.get("implementation_commit") != EXPECTED_IMPLEMENTATION_COMMIT:
        raise ConsensusCandidateError("Authority B implementation commit mismatch")
    if payload.get("implementation_tree") != EXPECTED_IMPLEMENTATION_TREE:
        raise ConsensusCandidateError("Authority B implementation tree mismatch")
    expected_ranking = [
        {"number": number, "rank": rank, "support_units": support}
        for rank, (number, support) in enumerate(CONSENSUS_DECISION_RANKING, start=1)
    ]
    if payload.get("final_decision_ranking") != expected_ranking:
        raise ConsensusCandidateError("Authority B decision ranking mismatch")
    if payload.get("final_recommended_output") != [
        {"predicted_numbers": [4, 12, 24, 25, 26, 29], "ticket_position": 1}
    ]:
        raise ConsensusCandidateError("Authority B recommendation mismatch")
    _reject_outcome_keys(payload)


def _validate_stream_manifest(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ConsensusCandidateError(f"{label} must contain exactly eleven streams")
    items = cast(list[object], value)
    if len(items) != len(CONSENSUS_STREAM_SPECS):
        raise ConsensusCandidateError(f"{label} must contain exactly eleven streams")
    expected = {spec[0]: spec for spec in CONSENSUS_STREAM_SPECS}
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, object]] = []
    for index, item in enumerate(items):
        stream = _mapping(item, f"{label}[{index}]")
        if set(stream) != {
            "native_ticket_count",
            "prediction_run_id",
            "source_relative_path",
            "source_sha256",
            "strategy_id",
            "strategy_version",
        }:
            raise ConsensusCandidateError(f"{label}[{index}] field inventory mismatch")
        strategy_id = _text(stream.get("strategy_id"), f"{label}[{index}].strategy_id")
        strategy_version = _text(
            stream.get("strategy_version"), f"{label}[{index}].strategy_version"
        )
        run_id = _text(stream.get("prediction_run_id"), f"{label}[{index}].prediction_run_id")
        source_relative_path = _text(
            stream.get("source_relative_path"), f"{label}[{index}].source_relative_path"
        )
        _safe_relative_path(source_relative_path, f"{label}[{index}].source_relative_path")
        _require_sha(stream.get("source_sha256"), f"{label}[{index}].source_sha256")
        count = stream.get("native_ticket_count")
        if type(count) is not int or count < 1 or 6 % count:
            raise ConsensusCandidateError(f"{label}[{index}] native ticket count is invalid")
        identity = (strategy_id, strategy_version, run_id)
        if identity in seen:
            raise ConsensusCandidateError(f"{label} contains duplicate stream identities")
        seen.add(identity)
        expected_spec = expected.get(strategy_id)
        if (
            expected_spec is None
            or (
                strategy_id,
                strategy_version,
                count,
                source_relative_path,
            )
            != expected_spec
        ):
            raise ConsensusCandidateError(f"{label}[{index}] is not an Authority B stream")
        result.append(stream)
    return result


def _validate_source_manifest(source_root: Path, value: object) -> None:
    streams = _validate_stream_manifest(value, "source manifest")
    for stream in streams:
        relative = cast(str, stream["source_relative_path"])
        source_path = _safe_source_path(source_root, relative)
        raw, actual_sha = _read_hashed(source_path)
        if actual_sha != stream["source_sha256"]:
            raise ConsensusCandidateError(f"source stream SHA-256 mismatch: {relative}")
        source = _json_object(raw, f"source stream {relative}")
        _validate_source_document(source, stream, relative)


def _validate_source_document(
    source: dict[str, object],
    stream: dict[str, object],
    relative: str,
) -> None:
    if set(source) != set(_EXPECTED_SOURCE_KEYS):
        raise ConsensusCandidateError(f"source stream field inventory mismatch: {relative}")
    expected = {
        "availability": "AVAILABLE",
        "draw_date": TARGET_DRAW_DATE,
        "draw_number": TARGET_DRAW_NUMBER,
        "history_caveat": "YES",
        "history_draw_count": CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
        "history_sha256": TARGET_HISTORY_SHA256,
        "lottery_type": TARGET_LOTTERY_TYPE,
        "prediction_run_id": stream["prediction_run_id"],
        "prediction_temporal_class": "PRE_DRAW",
        "schema_version": "b649-operational-prediction-v1",
        "strategy_id": stream["strategy_id"],
        "strategy_version": stream["strategy_version"],
        "task_id": CONSENSUS_UPSTREAM_TASK_ID,
        "unavailable_reason": None,
    }
    for key, expected_value in expected.items():
        if source.get(key) != expected_value:
            raise ConsensusCandidateError(f"source stream {key} mismatch: {relative}")
    if source.get("history_cutoff") != {
        "draw_date": "2026-09-08",
        "draw_number": TARGET_DATA_CUTOFF,
    }:
        raise ConsensusCandidateError(f"source stream cutoff mismatch: {relative}")
    _timestamp(source.get("prediction_created_at"), f"source stream timestamp: {relative}")
    tickets = source.get("tickets")
    count = stream["native_ticket_count"]
    if not isinstance(tickets, list):
        raise ConsensusCandidateError(f"source stream ticket count mismatch: {relative}")
    ticket_items = cast(list[object], tickets)
    if len(ticket_items) != count:
        raise ConsensusCandidateError(f"source stream ticket count mismatch: {relative}")
    for position, item in enumerate(ticket_items, start=1):
        ticket = _mapping(item, f"source stream ticket: {relative}")
        if set(ticket) != {"predicted_numbers", "ticket_position"}:
            raise ConsensusCandidateError(f"source stream ticket shape mismatch: {relative}")
        if ticket.get("ticket_position") != position:
            raise ConsensusCandidateError(f"source stream ticket order mismatch: {relative}")
        numbers = ticket.get("predicted_numbers")
        number_items = cast(list[object], numbers) if isinstance(numbers, list) else None
        if (
            number_items is None
            or len(number_items) != 6
            or len(set(number_items)) != 6
            or any(type(number) is not int or not 1 <= number <= 49 for number in number_items)
        ):
            raise ConsensusCandidateError(f"source stream ticket numbers are invalid: {relative}")
    _reject_outcome_keys(source)


def _reject_outcome_keys(value: object) -> None:
    if isinstance(value, dict):
        entries = cast(dict[str, object], value)
        for key, item in entries.items():
            if key in _FORBIDDEN_OUTCOME_KEYS:
                raise ConsensusCandidateError(f"forbidden outcome key observed: {key}")
            _reject_outcome_keys(item)
    elif isinstance(value, list):
        items = cast(list[object], value)
        for item in items:
            _reject_outcome_keys(item)


def _target_for_gate(value: Mapping[str, object] | None) -> dict[str, object]:
    if value is None:
        return {
            "lottery_type": TARGET_LOTTERY_TYPE,
            "target_draw_number": TARGET_DRAW_NUMBER,
            "target_draw_date": TARGET_DRAW_DATE,
            "scheduled_at": TARGET_SCHEDULED_AT,
            "timezone": TARGET_TIMEZONE,
            "data_cutoff": TARGET_DATA_CUTOFF,
        }
    return dict(value)


def _research_paths(database_path: Path) -> ResearchDataPaths:
    path = Path(database_path)
    if not path.is_absolute() or path.name != "lottolab_research.db":
        raise ResearchRepositoryError("database path must be the explicit research database")
    return ResearchDataPaths(path.parent, path)


def _regular_path(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ConsensusCandidateError(f"{label} must be absolute")
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise ConsensusCandidateError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ConsensusCandidateError(f"{label} cannot be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ConsensusCandidateError(f"{label} must be a regular file")
    return path


def _absolute_directory(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        raise ConsensusCandidateError(f"{label} must be an absolute directory")
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise ConsensusCandidateError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ConsensusCandidateError(f"{label} cannot be a symlink")
    return path


def _safe_relative_path(value: str, label: str) -> None:
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ConsensusCandidateError(f"{label} is unsafe")


def _safe_source_path(root: Path, relative: str) -> Path:
    _safe_relative_path(relative, "source_relative_path")
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ConsensusCandidateError(f"source file is unavailable: {relative}") from exc
    if resolved != path or not resolved.is_relative_to(root):
        raise ConsensusCandidateError(f"source file escapes the operation root: {relative}")
    return _regular_path(path, f"source file {relative}")


def _read_hashed(path: Path) -> tuple[bytes, str]:
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise ConsensusCandidateError(f"cannot read immutable artifact: {path}") from exc
    return value, hashlib.sha256(value).hexdigest()


def _json_object(value: bytes, label: str) -> dict[str, object]:
    try:
        decoded: object = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ConsensusCandidateError(f"{label} is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ConsensusCandidateError(f"{label} must be a JSON object")
    return cast(dict[str, object], decoded)


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConsensusCandidateError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConsensusCandidateError(f"{label} must be non-empty text")
    return value


def _require_text(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")


def _require_sha(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ConsensusCandidateError(f"{label} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConsensusCandidateError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ConsensusCandidateError(f"{label} must include a timezone")
    return parsed


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _as_utc(value: datetime) -> datetime:
    _require_aware(value, "datetime")
    return value.astimezone(UTC)


def _validate_runtime_identity(value: Mapping[str, object]) -> None:
    for key in ("python", "executable"):
        _require_text(value.get(key), f"command_runtime_identity.{key}")
    command = value.get("command")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(part, str) or not part for part in cast(list[object], command))
    ):
        raise ValueError("command_runtime_identity.command must be a non-empty argv")


__all__ = [
    "BLOCKER_DEADLINE_PASSED",
    "BLOCKER_DEADLINE_REACHED",
    "BLOCKER_OFFICIAL_OUTCOME_PRESENT",
    "BLOCKER_OFFICIAL_OUTCOME_UNKNOWN",
    "BLOCKER_PRE_DRAW_REQUIRED",
    "BLOCKER_SCHEDULED_TIME_CHANGED",
    "BLOCKER_SCHEDULE_AUTHORITY_MISSING",
    "BLOCKER_SCHEDULE_HASH_CHANGED",
    "BLOCKER_SCHEDULE_HASH_NOT_BOUND",
    "BLOCKER_TARGET_CHANGED",
    "CANONICAL_CONSENSUS",
    "CONSENSUS_SCOPE",
    "CONSENSUS_STREAM",
    "CONSENSUS_STREAM_VERSION",
    "EXPECTED_CANDIDATE_LOCATOR",
    "EXPECTED_CANDIDATE_SHA256",
    "EXPECTED_IMPLEMENTATION_COMMIT",
    "EXPECTED_IMPLEMENTATION_SOURCE_HASHES",
    "EXPECTED_IMPLEMENTATION_TREE",
    "EXPECTED_OPERATION_ROOT",
    "PROMOTION_DEADLINE",
    "TARGET_DATA_CUTOFF",
    "TARGET_DRAW_DATE",
    "TARGET_DRAW_NUMBER",
    "TARGET_LOTTERY_TYPE",
    "TARGET_SCHEDULED_AT",
    "TARGET_TIMEZONE",
    "CanonicalConsensusCandidate",
    "CanonicalConsensusEligibilityGate",
    "CanonicalEligibilityError",
    "CanonicalEligibilityResult",
    "ConsensusCandidateError",
    "PromotionRequest",
    "load_consensus_candidate",
    "promote_consensus_candidate",
    "read_current_consensus",
]
