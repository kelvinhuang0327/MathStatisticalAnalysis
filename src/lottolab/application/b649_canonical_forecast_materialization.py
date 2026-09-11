"""Application boundary for the immutable B649 canonical forecast.

The service owns target-aware orchestration and exact persisted-input
selection.  It deliberately receives already-read prediction records and a
small authority port: filesystem traversal and atomic publication stay in
infrastructure, while the aggregation itself remains in the domain module.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from lottolab.domain.b649_canonical_consensus import (
    AGGREGATION_CONTRACT_APPROVED_AT,
    AGGREGATION_CONTRACT_REVIEW_ID,
    CANONICAL_CONSENSUS_METHOD_ID,
    CANONICAL_CONSENSUS_METHOD_VERSION,
    CANONICAL_CONSENSUS_SCHEMA_VERSION,
    DECISION_RANKING_FORMULA,
    EXPECTED_STREAM_COUNT,
    FINAL_TICKET_SIZE,
    MAX_NUMBER,
    MIN_NUMBER,
    PRE_DRAW,
    CanonicalConsensusDecision,
    CanonicalConsensusInputError,
    StreamConsensusInput,
    build_canonical_consensus,
)
from lottolab.evidence.canonical_json import canonical_file_bytes

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]+", flags=re.ASCII)
_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_COMMIT = re.compile(r"[0-9a-f]{40,64}", flags=re.ASCII)
_FORBIDDEN_KEYS = frozenset(
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
_IMPLEMENTATION_KEYS = frozenset(
    {"implementation_commit", "implementation_tree", "implementation_source_hashes"}
)
_NON_SEMANTIC_AUTHORITY_KEYS = _IMPLEMENTATION_KEYS | frozenset(
    {"task_id", "upstream_task_id"}
)

Clock = Callable[[], datetime]


class CanonicalForecastMaterializationError(RuntimeError):
    """Base failure raised when the canonical forecast cannot be completed."""

    code: str = "FORECAST_MATERIALIZATION_ERROR"
    reason: str = "BLOCK_FORECAST_MATERIALIZATION"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"{self.code}: {self.reason}: {detail}")


class CanonicalForecastInputError(CanonicalForecastMaterializationError):
    """The scheduler supplied an invalid or incomplete persisted input set."""

    code: str = "FORECAST_INPUT_INVALID"
    reason: str = "BLOCK_FORECAST_INPUT_REMEDIATION_REQUIRED"


class MissingStreamInputError(CanonicalForecastInputError):
    code: str = "MISSING_STREAM_INPUT"
    reason: str = "BLOCK_MISSING_STREAM_INPUT"


class AmbiguousStreamInputError(CanonicalForecastInputError):
    code: str = "AMBIGUOUS_STREAM_INPUT"
    reason: str = "BLOCK_AMBIGUOUS_STREAM_INPUT"


class StreamVersionMismatchError(CanonicalForecastInputError):
    code: str = "STREAM_VERSION_MISMATCH"
    reason: str = "BLOCK_STREAM_VERSION_MISMATCH"


class TargetIdentityMismatchError(CanonicalForecastInputError):
    code: str = "TARGET_IDENTITY_MISMATCH"
    reason: str = "BLOCK_TARGET_IDENTITY_MISMATCH"


class CausalCutoffMismatchError(CanonicalForecastInputError):
    code: str = "CAUSAL_CUTOFF_MISMATCH"
    reason: str = "BLOCK_CAUSAL_CUTOFF_MISMATCH"


class HistoryIdentityMismatchError(CanonicalForecastInputError):
    code: str = "HISTORY_IDENTITY_MISMATCH"
    reason: str = "BLOCK_HISTORY_IDENTITY_MISMATCH"


class PostDrawInputError(CanonicalForecastInputError):
    code: str = "POST_DRAW_INPUT"
    reason: str = "BLOCK_POST_DRAW_INPUT"


class SourceIdentityMismatchError(CanonicalForecastInputError):
    code: str = "SOURCE_IDENTITY_MISMATCH"
    reason: str = "BLOCK_SOURCE_IDENTITY_MISMATCH"


class ImplementationIdentityError(CanonicalForecastMaterializationError):
    code: str = "IMPLEMENTATION_IDENTITY_MISMATCH"
    reason: str = "BLOCK_IMPLEMENTATION_IDENTITY_MISMATCH"


class PreOutcomeWindowClosedError(CanonicalForecastMaterializationError):
    code: str = "PRE_OUTCOME_WINDOW_MISSED"
    reason: str = "BLOCKED_PRE_OUTCOME_WINDOW_CLOSED"


class ForecastAuthorityConflictError(CanonicalForecastMaterializationError):
    code: str = "FORECAST_AUTHORITY_CONFLICT"
    reason: str = "BLOCK_FORECAST_AUTHORITY_REMEDIATION_REQUIRED"


class ForecastAuthorityStorageError(CanonicalForecastMaterializationError):
    code: str = "FORECAST_AUTHORITY_STORAGE_ERROR"
    reason: str = "BLOCK_FORECAST_AUTHORITY_STORAGE_REMEDIATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class CanonicalForecastTarget:
    """One target identity resolved by the scheduler."""

    lottery_type: str
    draw_number: str
    draw_date: str
    scheduled_at: str


@dataclass(frozen=True, slots=True)
class CanonicalForecastCutoff:
    """The maximum causal draw/date admitted for one target."""

    draw_number: str
    draw_date: str


@dataclass(frozen=True, slots=True)
class CanonicalHistoryIdentity:
    """The scheduler-owned history snapshot identity used by all streams."""

    cutoff_draw_number: str
    cutoff_date: str
    draw_count: int
    history_sha256: str
    history_caveat: str


@dataclass(frozen=True, slots=True)
class RegisteredForecastStream:
    """The exact production registry entry a persisted stream must match."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int


@dataclass(frozen=True, slots=True)
class PersistedForecastPrediction:
    """A prediction file read once by infrastructure with its raw hash."""

    source_relative_path: str
    source_sha256: str
    raw_bytes: bytes
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ImplementationSource:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ImplementationIdentity:
    """The implementation provenance attached to a newly created authority."""

    commit: str
    tree: str
    source_hashes: tuple[ImplementationSource, ...]


@dataclass(frozen=True, slots=True)
class CanonicalForecastMaterializationRequest:
    """All dynamic target and input identity required for one materialization."""

    task_id: str
    upstream_task_id: str
    target: CanonicalForecastTarget
    max_data_cutoff: CanonicalForecastCutoff
    history: CanonicalHistoryIdentity
    registered_streams: tuple[RegisteredForecastStream, ...]
    predictions: tuple[PersistedForecastPrediction, ...]
    implementation_identity: ImplementationIdentity
    expected_manifest_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalForecastMaterializationResult:
    """The observed durable result, including the exact payload bytes' hash."""

    status: Literal["COMPLETE", "DRY_RUN"]
    publication: Literal["CREATED", "ALREADY_PRESENT"] | None
    destination: Path
    payload: dict[str, object]
    artifact_sha256: str

    @property
    def input_manifest_sha256(self) -> str:
        value = self.payload.get("stream_input_manifest_sha256")
        if type(value) is not str:
            raise CanonicalForecastMaterializationError(
                "materialization payload has no stream input manifest"
            )
        return value


@dataclass(frozen=True, slots=True)
class CanonicalForecastAuthorityPort:
    """Small application port implemented by filesystem infrastructure."""

    read_existing_bytes: Callable[[Path], bytes | None]
    ensure_output_parent: Callable[[Path], None]
    stage_payload: Callable[[Path, bytes], object]
    publish_staged: Callable[[Any], object]
    discard_staged: Callable[[Any], None]


class CanonicalForecastMaterializationService:
    """Select exactly one input per stream, aggregate, and publish once."""

    def __init__(self, authority: CanonicalForecastAuthorityPort) -> None:
        self._authority = authority

    def execute(
        self,
        request: CanonicalForecastMaterializationRequest,
        *,
        destination: Path,
        clock: Clock,
        dry_run: bool = False,
    ) -> CanonicalForecastMaterializationResult:
        _validate_request(request)
        if not destination.is_absolute():
            raise CanonicalForecastMaterializationError(
                "destination must be an absolute Path"
            )

        streams = _select_stream_inputs(request)
        try:
            decision = build_canonical_consensus(streams)
        except CanonicalConsensusInputError as exc:
            raise CanonicalForecastInputError(str(exc)) from exc
        if len(decision.sources) != EXPECTED_STREAM_COUNT:
            raise CanonicalForecastInputError(
                f"expected exactly {EXPECTED_STREAM_COUNT} selected streams"
            )
        if request.expected_manifest_sha256 is not None and (
            decision.stream_input_manifest_sha256 != request.expected_manifest_sha256
        ):
            raise SourceIdentityMismatchError(
                "stream input manifest does not match the scheduler-owned expectation"
            )

        base = _base_payload(request, decision)
        try:
            existing = self._authority.read_existing_bytes(destination)
        except Exception as exc:
            raise ForecastAuthorityStorageError("existing authority could not be read") from exc
        if existing is not None:
            payload = _validate_existing_payload(existing, base, request, streams)
            return CanonicalForecastMaterializationResult(
                status="COMPLETE",
                publication="ALREADY_PRESENT",
                destination=destination,
                payload=payload,
                artifact_sha256=hashlib.sha256(existing).hexdigest(),
            )
        if dry_run:
            preview = canonical_file_bytes(base)
            return CanonicalForecastMaterializationResult(
                status="DRY_RUN",
                publication=None,
                destination=destination,
                payload=base,
                artifact_sha256=hashlib.sha256(preview).hexdigest(),
            )

        now = _clock_value(clock)
        _require_creation_window(now, request, streams, context="created_at")
        created_payload = {**base, "created_at": _format_timestamp(now)}
        payload_bytes = canonical_file_bytes(created_payload)
        try:
            self._authority.ensure_output_parent(destination)
            staged = self._authority.stage_payload(destination, payload_bytes)
        except CanonicalForecastMaterializationError:
            raise
        except Exception as exc:
            raise ForecastAuthorityStorageError("canonical forecast could not be staged") from exc

        published = False
        try:
            pre_publish_now = _clock_value(clock)
            _require_scheduled_boundary(pre_publish_now, request.target.scheduled_at)
            try:
                write_result = self._authority.publish_staged(staged)
                published = True
            except Exception as exc:
                raise ForecastAuthorityStorageError(
                    "canonical forecast could not be atomically published"
                ) from exc
            publication = getattr(write_result, "status", None)
            if publication == "CREATED":
                try:
                    observed = self._authority.read_existing_bytes(destination)
                except Exception as exc:
                    raise ForecastAuthorityStorageError(
                        "created authority could not be read back"
                    ) from exc
                if observed != payload_bytes:
                    raise ForecastAuthorityConflictError(
                        "read-after-write authority bytes differ from staged payload"
                    )
                return CanonicalForecastMaterializationResult(
                    status="COMPLETE",
                    publication="CREATED",
                    destination=destination,
                    payload=created_payload,
                    artifact_sha256=hashlib.sha256(payload_bytes).hexdigest(),
                )
            if publication != "ALREADY_PRESENT":
                raise ForecastAuthorityStorageError(
                    "authority publisher returned an unknown publication status"
                )
            try:
                observed = self._authority.read_existing_bytes(destination)
            except Exception as exc:
                raise ForecastAuthorityStorageError(
                    "competing authority could not be read"
                ) from exc
            if observed is None:
                raise ForecastAuthorityConflictError(
                    "atomic publication reported an authority that disappeared"
                )
            payload = _validate_existing_payload(observed, base, request, streams)
            return CanonicalForecastMaterializationResult(
                status="COMPLETE",
                publication="ALREADY_PRESENT",
                destination=destination,
                payload=payload,
                artifact_sha256=hashlib.sha256(observed).hexdigest(),
            )
        finally:
            if not published:
                try:
                    self._authority.discard_staged(staged)
                except Exception as exc:
                    raise ForecastAuthorityStorageError(
                        "staged canonical forecast cleanup failed"
                    ) from exc


def materialize_canonical_forecast(
    request: CanonicalForecastMaterializationRequest,
    *,
    destination: Path,
    authority: CanonicalForecastAuthorityPort,
    clock: Clock,
    dry_run: bool = False,
) -> CanonicalForecastMaterializationResult:
    """Functional composition entry point for CLI and scheduler callers."""

    return CanonicalForecastMaterializationService(authority).execute(
        request,
        destination=destination,
        clock=clock,
        dry_run=dry_run,
    )


def select_stream_inputs(
    request: CanonicalForecastMaterializationRequest,
) -> tuple[StreamConsensusInput, ...]:
    """Validate and select the exact one-per-stream input set without writing."""

    _validate_request(request)
    return _select_stream_inputs(request)


def build_forecast_health(
    result: CanonicalForecastMaterializationResult,
) -> dict[str, object]:
    """Project a successful service result into the scheduler health contract."""

    return {
        "status": "COMPLETE",
        "publication": result.publication,
        "target_draw": _target_draw_from_payload(result.payload),
        "method_id": CANONICAL_CONSENSUS_METHOD_ID,
        "method_version": CANONICAL_CONSENSUS_METHOD_VERSION,
        "artifact_path": str(result.destination),
        "artifact_sha256": result.artifact_sha256,
        "input_manifest_sha256": result.input_manifest_sha256,
        "error_class": None,
        "reason": None,
    }


def _validate_request(request: CanonicalForecastMaterializationRequest) -> None:
    for value, label in (
        (request.task_id, "task_id"),
        (request.upstream_task_id, "upstream_task_id"),
    ):
        if type(value) is not str or not value.strip():
            raise CanonicalForecastMaterializationError(f"{label} must be non-empty text")
    target = request.target
    if any(
        type(value) is not str or not value.strip()
        for value in (
            target.lottery_type,
            target.draw_number,
            target.draw_date,
            target.scheduled_at,
        )
    ):
        raise TargetIdentityMismatchError("target identity fields must be non-empty")
    if _DECIMAL.fullmatch(target.draw_number) is None:
        raise TargetIdentityMismatchError("target draw number is not decimal")
    _parse_date(target.draw_date, "target draw_date")
    scheduled = _parse_timestamp(target.scheduled_at, "target scheduled_at")
    if scheduled.date().isoformat() != target.draw_date:
        raise TargetIdentityMismatchError(
            "target scheduled_at local date conflicts with target draw_date"
        )
    _validate_cutoff(request.max_data_cutoff, target)
    history = request.history
    if type(history.draw_count) is not int or history.draw_count < 1:
        raise HistoryIdentityMismatchError("history draw_count must be positive")
    if _SHA256.fullmatch(history.history_sha256) is None:
        raise HistoryIdentityMismatchError("history_sha256 must be lowercase SHA-256")
    if type(history.history_caveat) is not str or not history.history_caveat.strip():
        raise HistoryIdentityMismatchError("history_caveat must be non-empty text")
    if (
        history.cutoff_draw_number != request.max_data_cutoff.draw_number
        or history.cutoff_date != request.max_data_cutoff.draw_date
    ):
        raise HistoryIdentityMismatchError(
            "scheduler history cutoff differs from max_data_cutoff"
        )
    if len(request.registered_streams) != EXPECTED_STREAM_COUNT:
        raise CanonicalForecastInputError(
            f"registered stream count must be exactly {EXPECTED_STREAM_COUNT}"
        )
    stream_ids: set[str] = set()
    for stream in request.registered_streams:
        if _IDENTIFIER.fullmatch(stream.strategy_id) is None:
            raise CanonicalForecastInputError("registered strategy_id is not canonical")
        if type(stream.strategy_version) is not str or not stream.strategy_version.strip():
            raise CanonicalForecastInputError("registered strategy_version is empty")
        if stream.strategy_id in stream_ids:
            raise CanonicalForecastInputError("registered strategy_id values must be unique")
        stream_ids.add(stream.strategy_id)
        if type(stream.native_ticket_count) is not int or stream.native_ticket_count < 1:
            raise CanonicalForecastInputError("registered native_ticket_count is invalid")
        if FINAL_TICKET_SIZE % stream.native_ticket_count:
            raise CanonicalForecastInputError(
                "registered native_ticket_count must divide six"
            )
    identity = request.implementation_identity
    if _COMMIT.fullmatch(identity.commit) is None or _COMMIT.fullmatch(identity.tree) is None:
        raise ImplementationIdentityError("implementation commit/tree identity is invalid")
    if not identity.source_hashes:
        raise ImplementationIdentityError("implementation source hash scope is empty")
    seen_paths: set[str] = set()
    for source in identity.source_hashes:
        if (
            type(source.path) is not str
            or not source.path
            or source.path.startswith("/")
            or "\\" in source.path
            or any(part in {"", ".", ".."} for part in source.path.split("/"))
        ):
            raise ImplementationIdentityError("implementation source path is unsafe")
        if source.path in seen_paths or _SHA256.fullmatch(source.sha256) is None:
            raise ImplementationIdentityError("implementation source hash scope is invalid")
        seen_paths.add(source.path)
    if request.expected_manifest_sha256 is not None and _SHA256.fullmatch(
        request.expected_manifest_sha256
    ) is None:
        raise SourceIdentityMismatchError("expected stream manifest SHA-256 is invalid")
    del scheduled


def _validate_cutoff(cutoff: CanonicalForecastCutoff, target: CanonicalForecastTarget) -> None:
    if (
        type(cutoff.draw_number) is not str
        or _DECIMAL.fullmatch(cutoff.draw_number) is None
        or type(cutoff.draw_date) is not str
    ):
        raise CausalCutoffMismatchError("max_data_cutoff identity is invalid")
    _parse_date(cutoff.draw_date, "max_data_cutoff.draw_date")
    if (datetime.fromisoformat(cutoff.draw_date), int(cutoff.draw_number)) >= (
        datetime.fromisoformat(target.draw_date),
        int(target.draw_number),
    ):
        raise CausalCutoffMismatchError("max_data_cutoff is not strictly before target")


def _select_stream_inputs(
    request: CanonicalForecastMaterializationRequest,
) -> tuple[StreamConsensusInput, ...]:
    expected = {stream.strategy_id: stream for stream in request.registered_streams}
    grouped: dict[str, list[PersistedForecastPrediction]] = {}
    for record in request.predictions:
        strategy_id = record.payload.get("strategy_id")
        if type(strategy_id) is not str or not strategy_id:
            raise TargetIdentityMismatchError(
                f"{record.source_relative_path}: strategy_id is missing"
            )
        if strategy_id not in expected:
            raise TargetIdentityMismatchError(
                f"{record.source_relative_path}: strategy_id is outside the registered streams"
            )
        grouped.setdefault(strategy_id, []).append(record)

    missing = tuple(
        stream.strategy_id
        for stream in request.registered_streams
        if not grouped.get(stream.strategy_id)
    )
    if missing:
        raise MissingStreamInputError("missing registered streams: " + ", ".join(missing))
    ambiguous = tuple(
        strategy_id for strategy_id, records in grouped.items() if len(records) != 1
    )
    if ambiguous:
        raise AmbiguousStreamInputError(
            "multiple persisted records for registered streams: " + ", ".join(sorted(ambiguous))
        )

    selected: list[StreamConsensusInput] = []
    for stream in request.registered_streams:
        selected.append(
            _validate_prediction_record(
                grouped[stream.strategy_id][0],
                stream=stream,
                request=request,
            )
        )
    return tuple(selected)


def _validate_prediction_record(
    record: PersistedForecastPrediction,
    *,
    stream: RegisteredForecastStream,
    request: CanonicalForecastMaterializationRequest,
) -> StreamConsensusInput:
    payload = record.payload
    _validate_source_identity(record, request.target)
    _reject_forbidden_keys(payload, record.source_relative_path)
    if payload.get("lottery_type") != request.target.lottery_type:
        raise TargetIdentityMismatchError(f"{record.source_relative_path}: lottery_type mismatch")
    for key, expected in (
        ("draw_number", request.target.draw_number),
        ("draw_date", request.target.draw_date),
        ("scheduled_at", request.target.scheduled_at),
    ):
        if payload.get(key) != expected:
            raise TargetIdentityMismatchError(
                f"{record.source_relative_path}: {key} does not match target"
            )
    temporal_class = payload.get("prediction_temporal_class")
    if temporal_class == "POST_DRAW":
        raise PostDrawInputError(f"{record.source_relative_path}: POST_DRAW input is forbidden")
    if temporal_class != PRE_DRAW:
        raise TargetIdentityMismatchError(
            f"{record.source_relative_path}: prediction is not PRE_DRAW"
        )
    if payload.get("availability") != "AVAILABLE":
        raise MissingStreamInputError(
            f"{record.source_relative_path}: prediction is not AVAILABLE"
        )
    strategy_id = _required_text(payload, "strategy_id", record.source_relative_path)
    if strategy_id != stream.strategy_id:
        raise TargetIdentityMismatchError(
            f"{record.source_relative_path}: strategy_id does not match registry"
        )
    strategy_version = _required_text(payload, "strategy_version", record.source_relative_path)
    if strategy_version != stream.strategy_version:
        raise StreamVersionMismatchError(
            f"{record.source_relative_path}: strategy_version differs from registry"
        )
    prediction_run_id = _required_text(payload, "prediction_run_id", record.source_relative_path)
    path = PurePosixPath(record.source_relative_path)
    if path.stem != prediction_run_id:
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: prediction_run_id does not match file identity"
        )
    created_at = _parse_timestamp(
        _required_text(payload, "prediction_created_at", record.source_relative_path),
        f"{record.source_relative_path}.prediction_created_at",
    )
    scheduled_at = _parse_timestamp(request.target.scheduled_at, "target scheduled_at")
    if created_at >= scheduled_at:
        raise PostDrawInputError(
            f"{record.source_relative_path}: prediction_created_at is not before scheduled_at"
        )
    cutoff = payload.get("history_cutoff")
    expected_cutoff = {
        "draw_number": request.max_data_cutoff.draw_number,
        "draw_date": request.max_data_cutoff.draw_date,
    }
    if cutoff != expected_cutoff:
        raise CausalCutoffMismatchError(
            f"{record.source_relative_path}: history_cutoff differs from scheduler cutoff"
        )
    if payload.get("history_draw_count") != request.history.draw_count:
        raise HistoryIdentityMismatchError(
            f"{record.source_relative_path}: history_draw_count differs from authority"
        )
    if payload.get("history_sha256") != request.history.history_sha256:
        raise HistoryIdentityMismatchError(
            f"{record.source_relative_path}: history_sha256 differs from authority"
        )
    if payload.get("history_caveat") != request.history.history_caveat:
        raise HistoryIdentityMismatchError(
            f"{record.source_relative_path}: history_caveat differs from authority"
        )
    native_count = payload.get("native_ticket_count")
    if native_count != stream.native_ticket_count:
        raise TargetIdentityMismatchError(
            f"{record.source_relative_path}: native_ticket_count differs from registry"
        )
    tickets = _parse_tickets(payload, stream.native_ticket_count, record.source_relative_path)
    return StreamConsensusInput(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        native_ticket_count=stream.native_ticket_count,
        prediction_run_id=prediction_run_id,
        source_relative_path=record.source_relative_path,
        source_sha256=record.source_sha256,
        prediction_created_at=created_at,
        tickets=tickets,
    )


def _validate_source_identity(
    record: PersistedForecastPrediction,
    target: CanonicalForecastTarget,
) -> None:
    if type(record.raw_bytes) is not bytes:
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: raw source bytes are unavailable"
        )
    if _SHA256.fullmatch(record.source_sha256) is None:
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: captured source SHA-256 is invalid"
        )
    actual_sha = hashlib.sha256(record.raw_bytes).hexdigest()
    if actual_sha != record.source_sha256:
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: captured source SHA-256 does not match raw bytes"
        )
    path = PurePosixPath(record.source_relative_path)
    if (
        path.is_absolute()
        or "\\" in record.source_relative_path
        or any(part in {"", ".", ".."} for part in path.parts)
        or len(path.parts) < 3
        or path.parts[0] != "predictions"
        or path.parts[1] != target.draw_number
        or path.suffix != ".json"
    ):
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: source path is not the exact target file identity"
        )
    try:
        parsed = json.loads(
            record.raw_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: raw source is not valid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: raw source is not one JSON object"
        )
    parsed_mapping = cast(dict[object, object], parsed)
    if any(type(key) is not str for key in parsed_mapping):
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: raw source keys are not strings"
        )
    if dict(record.payload) != cast(dict[str, object], parsed_mapping):
        raise SourceIdentityMismatchError(
            f"{record.source_relative_path}: parsed payload differs from raw source"
        )


def _parse_tickets(
    payload: Mapping[str, object], native_count: int, source: str
) -> tuple[tuple[int, ...], ...]:
    raw_tickets_value = payload.get("tickets")
    if type(raw_tickets_value) is not list:
        raise TargetIdentityMismatchError(f"{source}: native ticket shape is invalid")
    raw_tickets = cast(list[object], raw_tickets_value)
    if len(raw_tickets) != native_count:
        raise TargetIdentityMismatchError(f"{source}: native ticket shape is invalid")
    tickets: list[tuple[int, ...]] = []
    for position, raw_ticket in enumerate(raw_tickets, start=1):
        if not isinstance(raw_ticket, dict):
            raise TargetIdentityMismatchError(f"{source}: ticket row is invalid")
        row = cast(dict[object, object], raw_ticket)
        if row.get("ticket_position") != position:
            raise TargetIdentityMismatchError(f"{source}: ticket positions are not contiguous")
        numbers_value = row.get("predicted_numbers")
        if type(numbers_value) is not list:
            raise TargetIdentityMismatchError(f"{source}: ticket numbers are not six integers")
        number_values = cast(list[object], numbers_value)
        if len(number_values) != FINAL_TICKET_SIZE:
            raise TargetIdentityMismatchError(f"{source}: ticket numbers are not six integers")
        if any(type(number) is not int for number in number_values):
            raise TargetIdentityMismatchError(f"{source}: ticket numbers are not six integers")
        ticket = tuple(cast(list[int], number_values))
        if len(set(ticket)) != FINAL_TICKET_SIZE or any(
            number < MIN_NUMBER or number > MAX_NUMBER for number in ticket
        ):
            raise TargetIdentityMismatchError(f"{source}: ticket contains illegal numbers")
        tickets.append(ticket)
    return tuple(tickets)


def _base_payload(
    request: CanonicalForecastMaterializationRequest,
    decision: CanonicalConsensusDecision,
) -> dict[str, object]:
    decision_payload = decision.to_payload(
        task_id=request.task_id,
        lottery_type=request.target.lottery_type,
    )
    identity_rows = [
        {"path": source.path, "sha256": source.sha256}
        for source in sorted(
            request.implementation_identity.source_hashes,
            key=lambda source: source.path,
        )
    ]
    return {
        **decision_payload,
        "schema_version": CANONICAL_CONSENSUS_SCHEMA_VERSION,
        "task_id": request.task_id,
        "target_draw": {
            "draw_number": request.target.draw_number,
            "draw_date": request.target.draw_date,
        },
        "scheduled_at": request.target.scheduled_at,
        "max_data_cutoff": {
            "draw_number": request.max_data_cutoff.draw_number,
            "draw_date": request.max_data_cutoff.draw_date,
        },
        "history_sha256": request.history.history_sha256,
        "history_draw_count": request.history.draw_count,
        "history_caveat": request.history.history_caveat,
        "target_result_used": False,
        "aggregation_contract_review_id": AGGREGATION_CONTRACT_REVIEW_ID,
        "aggregation_contract_approved_at": AGGREGATION_CONTRACT_APPROVED_AT,
        "decision_ranking_formula": DECISION_RANKING_FORMULA,
        "implementation_commit": request.implementation_identity.commit,
        "implementation_tree": request.implementation_identity.tree,
        "implementation_source_hashes": identity_rows,
        "pre_outcome_temporal_integrity": "PASS",
        "upstream_task_id": request.upstream_task_id,
    }


def _validate_existing_payload(
    raw: bytes,
    base: Mapping[str, object],
    request: CanonicalForecastMaterializationRequest,
    streams: Sequence[StreamConsensusInput],
) -> dict[str, object]:
    if not raw.endswith(b"\n"):
        raise ForecastAuthorityConflictError(
            "existing authority is missing its canonical trailing LF"
        )
    try:
        parsed = json.loads(
            raw[:-1].decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise ForecastAuthorityConflictError("existing authority is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ForecastAuthorityConflictError("existing authority is not one JSON object")
    mapping = cast(dict[object, object], parsed)
    if any(type(key) is not str for key in mapping):
        raise ForecastAuthorityConflictError("existing authority keys are not strings")
    payload = cast(dict[str, object], mapping)
    try:
        canonical = canonical_file_bytes(payload)
    except ValueError as exc:
        raise ForecastAuthorityConflictError("existing authority is not canonical JSON") from exc
    if canonical != raw:
        raise ForecastAuthorityConflictError("existing authority is not canonical JSON")
    created = payload.get("created_at")
    if type(created) is not str:
        raise ForecastAuthorityConflictError("existing authority has no canonical created_at")
    try:
        _reject_forbidden_keys(payload, "existing authority")
        created_at = _parse_timestamp(created, "existing.created_at")
        _require_creation_window(created_at, request, streams, context="existing.created_at")
    except ForecastAuthorityConflictError:
        raise
    except CanonicalForecastMaterializationError as exc:
        raise ForecastAuthorityConflictError(
            "existing authority temporal or outcome identity is invalid"
        ) from exc
    actual_immutable = {key: value for key, value in payload.items() if key != "created_at"}
    expected_immutable = {
        key: value
        for key, value in base.items()
        if key not in _NON_SEMANTIC_AUTHORITY_KEYS
    }
    actual_comparable = {
        key: value
        for key, value in actual_immutable.items()
        if key not in _NON_SEMANTIC_AUTHORITY_KEYS
    }
    if actual_comparable != expected_immutable:
        raise ForecastAuthorityConflictError(
            "existing authority immutable fields differ from target/input/method authority"
        )
    return payload


def _require_creation_window(
    created_at: datetime,
    request: CanonicalForecastMaterializationRequest,
    streams: Sequence[StreamConsensusInput],
    *,
    context: str,
) -> None:
    created_utc = _as_utc(created_at, context)
    scheduled_utc = _as_utc(
        _parse_timestamp(request.target.scheduled_at, "target scheduled_at"),
        "target scheduled_at",
    )
    approved_utc = _as_utc(
        _parse_timestamp(AGGREGATION_CONTRACT_APPROVED_AT, "aggregation approval"),
        "aggregation approval",
    )
    if any(
        _as_utc(stream.prediction_created_at, "prediction_created_at") > created_utc
        for stream in streams
    ):
        raise PreOutcomeWindowClosedError(
            f"{context} is earlier than a selected prediction_created_at"
        )
    if approved_utc > created_utc:
        raise PreOutcomeWindowClosedError(
            f"{context} is earlier than aggregation_contract_approved_at"
        )
    if created_utc >= scheduled_utc:
        raise PreOutcomeWindowClosedError(f"{context} must be strictly before scheduled_at")


def _require_scheduled_boundary(now: datetime, scheduled_at: str) -> None:
    if _as_utc(now, "pre_publish_now") >= _as_utc(
        _parse_timestamp(scheduled_at, "target scheduled_at"),
        "target scheduled_at",
    ):
        raise PreOutcomeWindowClosedError(
            "pre_publish_now must be strictly before scheduled_at"
        )


def _target_draw_from_payload(payload: Mapping[str, object]) -> str:
    target_value = payload.get("target_draw")
    if type(target_value) is not dict:
        raise CanonicalForecastMaterializationError("payload target_draw is invalid")
    target = cast(dict[str, object], target_value)
    if type(target.get("draw_number")) is not str:
        raise CanonicalForecastMaterializationError("payload target_draw is invalid")
    return cast(str, target["draw_number"])


def _required_text(value: Mapping[str, object], key: str, source: str) -> str:
    item = value.get(key)
    if type(item) is not str or not item.strip():
        raise TargetIdentityMismatchError(f"{source}: {key} must be non-empty text")
    return item


def _parse_date(value: str, label: str) -> None:
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise TargetIdentityMismatchError(f"{label} must be an ISO date") from exc
    if len(value) != 10:
        raise TargetIdentityMismatchError(f"{label} must be an ISO date")


def _parse_timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TargetIdentityMismatchError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TargetIdentityMismatchError(f"{label} must be timezone-aware")
    return parsed


def _clock_value(clock: Clock) -> datetime:
    value = clock()
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise PreOutcomeWindowClosedError("clock must return a timezone-aware datetime")
    return value


def _as_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PreOutcomeWindowClosedError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return _as_utc(value, "created_at").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _reject_forbidden_keys(value: object, source: str) -> None:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        for key, item in mapping.items():
            if key in _FORBIDDEN_KEYS:
                raise PostDrawInputError(f"{source}: forbidden outcome/scoring key observed: {key}")
            _reject_forbidden_keys(item, source)
    elif isinstance(value, list):
        items = cast(list[object], value)
        for item in items:
            _reject_forbidden_keys(item, source)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


# Short aliases keep the service discoverable for callers that use the
# shorter request/result terminology.
ForecastTarget = CanonicalForecastTarget
ForecastCutoff = CanonicalForecastCutoff
HistoryIdentity = CanonicalHistoryIdentity
RegisteredStream = RegisteredForecastStream
PersistedPrediction = PersistedForecastPrediction
CanonicalForecastRequest = CanonicalForecastMaterializationRequest
CanonicalForecastResult = CanonicalForecastMaterializationResult
ForecastAuthorityPort = CanonicalForecastAuthorityPort


__all__ = [
    "AGGREGATION_CONTRACT_APPROVED_AT",
    "AGGREGATION_CONTRACT_REVIEW_ID",
    "CANONICAL_CONSENSUS_METHOD_ID",
    "CANONICAL_CONSENSUS_METHOD_VERSION",
    "CANONICAL_CONSENSUS_SCHEMA_VERSION",
    "AmbiguousStreamInputError",
    "CanonicalForecastAuthorityPort",
    "CanonicalForecastCutoff",
    "CanonicalForecastInputError",
    "CanonicalForecastMaterializationError",
    "CanonicalForecastMaterializationRequest",
    "CanonicalForecastMaterializationResult",
    "CanonicalForecastMaterializationService",
    "CanonicalForecastRequest",
    "CanonicalForecastResult",
    "CanonicalForecastTarget",
    "CanonicalHistoryIdentity",
    "CausalCutoffMismatchError",
    "ForecastAuthorityConflictError",
    "ForecastAuthorityPort",
    "ForecastAuthorityStorageError",
    "ForecastCutoff",
    "ForecastTarget",
    "HistoryIdentity",
    "HistoryIdentityMismatchError",
    "ImplementationIdentity",
    "ImplementationIdentityError",
    "ImplementationSource",
    "MissingStreamInputError",
    "PersistedForecastPrediction",
    "PersistedPrediction",
    "PostDrawInputError",
    "PreOutcomeWindowClosedError",
    "RegisteredForecastStream",
    "RegisteredStream",
    "SourceIdentityMismatchError",
    "StreamVersionMismatchError",
    "TargetIdentityMismatchError",
    "build_forecast_health",
    "materialize_canonical_forecast",
    "select_stream_inputs",
]
