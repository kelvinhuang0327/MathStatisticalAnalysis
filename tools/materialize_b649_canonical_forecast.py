"""Historical 087 adapter for the reusable B649 forecast service.

The production scheduler does not import this module.  Its 087 constants and
frozen source paths remain only to support bounded compatibility verification
of the already-published historical authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lottolab.application.b649_canonical_forecast_materialization import (
    CanonicalForecastAuthorityPort,
    CanonicalForecastCutoff,
    CanonicalForecastMaterializationError,
    CanonicalForecastMaterializationRequest,
    CanonicalForecastMaterializationResult,
    CanonicalForecastTarget,
    CanonicalHistoryIdentity,
    ForecastAuthorityConflictError,
    ImplementationIdentity,
    ImplementationIdentityError,
    ImplementationSource,
    PersistedForecastPrediction,
    PreOutcomeWindowClosedError,
    RegisteredForecastStream,
    select_stream_inputs,
)
from lottolab.application.b649_canonical_forecast_materialization import (
    materialize_canonical_forecast as _materialize_service,
)
from lottolab.domain.b649_canonical_consensus import (
    AGGREGATION_CONTRACT_APPROVED_AT,
    AGGREGATION_CONTRACT_REVIEW_ID,
    AGGREGATION_UNIT,
    CANONICAL_CONSENSUS_METHOD_ID,
    CANONICAL_CONSENSUS_METHOD_VERSION,
    CANONICAL_CONSENSUS_SCHEMA_VERSION,
    CORRELATED_FAMILY_POLICY,
    DECISION_RANKING_FORMULA,
    EXPECTED_STREAM_COUNT,
    FINAL_TICKET_SIZE,
    HISTORY_CAVEAT,
    HISTORY_DRAW_COUNT,
    HISTORY_SHA256,
    MAX_DATA_CUTOFF,
    MAX_DATA_CUTOFF_DATE,
    PRE_DRAW,
    STREAM_WEIGHT_POLICY,
    TARGET_DRAW_DATE,
    TARGET_DRAW_NUMBER,
    TARGET_SCHEDULED_AT,
    TIE_BREAK,
    CanonicalConsensusContext,
    StreamConsensusInput,
)
from lottolab.evidence.canonical_json import sha256_hex
from lottolab.infrastructure.b649_canonical_forecast_writer import (
    discard_staged,
    ensure_output_parent,
    publish_staged,
    read_existing_bytes,
    read_persisted_prediction_records,
    stage_payload,
)

TASK_ID: Final = (
    "B649_11_STREAM_CANONICAL_AGGREGATION_IMPLEMENT_AND_MATERIALIZE_115000087_R1"
)
UPSTREAM_TASK_ID: Final = "B649_OPERATIONAL_PREDICTION_LOOP_R1"
LOTTERY_TYPE: Final = "BIG_LOTTO"
TARGET_DRAW_NUMBER: Final = "115000087"
TARGET_DRAW_DATE: Final = "2026-09-11"
TARGET_SCHEDULED_AT: Final = "2026-09-11T20:30:00+08:00"
MAX_DATA_CUTOFF: Final = "115000086"
MAX_DATA_CUTOFF_DATE: Final = "2026-09-08"
HISTORY_DRAW_COUNT: Final = 2168
HISTORY_SHA256: Final = "c2ba95be375c739c096baaae6ac03b666bc93ef81c9a721ec9381ed7b4c2cec4"
HISTORY_CAVEAT: Final = "YES"
OPERATION_ROOT: Final = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1"
)
FORECAST_RELATIVE_PATH: Final = Path(
    "forecasts/115000087/B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS/1.0.0/"
    "final_forecast_payload.json"
)
EXPECTED_STREAM_INPUT_MANIFEST_SHA256: Final = (
    "d1489a3eadecf57edb6932a3e9d34a97a1285306c7527e86376915e656c63ee6"
)
IMPLEMENTATION_SOURCE_PATHS: Final = (
    "src/lottolab/application/b649_canonical_forecast_materialization.py",
    "src/lottolab/domain/b649_canonical_consensus.py",
    "src/lottolab/infrastructure/b649_canonical_forecast_writer.py",
    "tools/b649_goalc_local_scheduler.py",
    "tools/materialize_b649_canonical_forecast.py",
)
_GIT_OBJECT = re.compile(r"[0-9a-f]{40,64}", flags=re.ASCII)

# Compatibility names retain the previous CLI/test surface while the
# implementation lives in the application service.
ForecastMaterializationError = CanonicalForecastMaterializationError
FrozenInputError = CanonicalForecastMaterializationError


class ForecastAuthorityMissingError(ForecastMaterializationError):
    """The requested canonical forecast authority has not been published."""


@dataclass(frozen=True, slots=True)
class FrozenStreamSpec:
    """One exact historical 087 source path and registry identity."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    source_relative_path: str


@dataclass(frozen=True, slots=True)
class FrozenInputBundle:
    streams: tuple[StreamConsensusInput, ...]
    scheduled_at: datetime


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    status: Literal["CREATED", "ALREADY_PRESENT", "DRY_RUN"]
    destination: Path
    payload: dict[str, object]


FROZEN_STREAM_SPECS: Final = (
    FrozenStreamSpec(
        "b649_new_horizon_minimax_disagreement_r1",
        "v0.1",
        2,
        "predictions/115000087/b649_new_horizon_minimax_disagreement_r1/"
        "115000087-b649_new_horizon_minimax_disagreement_r1-20260908T220756458387p0800-06e621e7.json",
    ),
    FrozenStreamSpec(
        "biglotto_deviation_2bet",
        "v0.1",
        1,
        "predictions/115000087/biglotto_deviation_2bet/"
        "115000087-biglotto_deviation_2bet-20260908T220756549249p0800-ee8a5778.json",
    ),
    FrozenStreamSpec(
        "biglotto_social_wisdom_anti_popularity",
        "v0.1",
        1,
        "predictions/115000087/biglotto_social_wisdom_anti_popularity/"
        "115000087-biglotto_social_wisdom_anti_popularity-20260908T220756520593p0800-2dd5f277.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "v0.1",
        1,
        "predictions/115000087/legacy_biglotto__graph_predictor__cd70713a5709/"
        "115000087-legacy_biglotto__graph_predictor__cd70713a5709-20260908T220756579053p0800-b2a25749.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
        "v0.1",
        1,
        "predictions/115000087/legacy_biglotto__hpsb_optimizer__cf5cd7d971e8/"
        "115000087-legacy_biglotto__hpsb_optimizer__cf5cd7d971e8-20260908T220756655001p0800-c29b6fe8.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__pure_cold_predict__9e89f2b41add",
        "v0.1",
        1,
        "predictions/115000087/legacy_biglotto__pure_cold_predict__9e89f2b41add/"
        "115000087-legacy_biglotto__pure_cold_predict__9e89f2b41add-20260908T220756630806p0800-ff2d46c3.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__test_asm__d39a233a4c75",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_asm__d39a233a4c75/"
        "115000087-legacy_biglotto__test_asm__d39a233a4c75-20260908T220756904980p0800-67e675a6.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__test_ces__78d17c530ab8",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_ces__78d17c530ab8/"
        "115000087-legacy_biglotto__test_ces__78d17c530ab8-20260908T220756949668p0800-046fc46c.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__test_ecp__c9d5ac6decdd",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_ecp__c9d5ac6decdd/"
        "115000087-legacy_biglotto__test_ecp__c9d5ac6decdd-20260908T220757075956p0800-7db57da2.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__test_mwsc__ba37643d6a3b",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_mwsc__ba37643d6a3b/"
        "115000087-legacy_biglotto__test_mwsc__ba37643d6a3b-20260908T220757124722p0800-4ea6d9e2.json",
    ),
    FrozenStreamSpec(
        "legacy_biglotto__test_tme__f3bb5106dfe3",
        "v0.1",
        3,
        "predictions/115000087/legacy_biglotto__test_tme__f3bb5106dfe3/"
        "115000087-legacy_biglotto__test_tme__f3bb5106dfe3-20260908T220757155867p0800-92a4b552.json",
    ),
)


Clock = Callable[[], datetime]


def load_frozen_stream_inputs(
    operation_root: Path = OPERATION_ROOT,
    *,
    specs: Sequence[FrozenStreamSpec] = FROZEN_STREAM_SPECS,
    expected_manifest_sha256: str | None = EXPECTED_STREAM_INPUT_MANIFEST_SHA256,
) -> FrozenInputBundle:
    """Read the exact 087 files through the infrastructure reader."""

    spec_tuple = tuple(specs)
    if len(spec_tuple) != EXPECTED_STREAM_COUNT:
        raise FrozenInputError(f"expected exactly {EXPECTED_STREAM_COUNT} stream specs")
    records = read_persisted_prediction_records(operation_root, TARGET_DRAW_NUMBER)
    by_path = {record.source_relative_path: record for record in records}
    selected: list[PersistedForecastPrediction] = []
    registered: list[RegisteredForecastStream] = []
    for spec in spec_tuple:
        record = by_path.get(spec.source_relative_path)
        if record is None:
            raise FrozenInputError(f"missing frozen input: {spec.source_relative_path}")
        selected.append(
            PersistedForecastPrediction(
                source_relative_path=record.source_relative_path,
                source_sha256=record.source_sha256,
                raw_bytes=record.raw_bytes,
                payload=record.payload,
            )
        )
        registered.append(
            RegisteredForecastStream(
                strategy_id=spec.strategy_id,
                strategy_version=spec.strategy_version,
                native_ticket_count=spec.native_ticket_count,
            )
        )
    request = _request(
        selected,
        registered,
        ImplementationIdentity(
            "a" * 40,
            "b" * 40,
            (ImplementationSource("compat", "c" * 64),),
        ),
        expected_manifest_sha256=expected_manifest_sha256,
    )
    return FrozenInputBundle(
        streams=select_stream_inputs(request),
        scheduled_at=datetime.fromisoformat(TARGET_SCHEDULED_AT),
    )


def resolve_implementation_identity(repo_root: Path) -> ImplementationIdentity:
    """Resolve committed hashes for the reusable service and its callers."""

    discovered = Path(_git(repo_root, "rev-parse", "--show-toplevel").strip()).resolve()
    if discovered != repo_root.resolve():
        raise ImplementationIdentityError(
            f"repo_root is not the Git root: expected {repo_root}, found {discovered}"
        )
    rows: list[ImplementationSource] = []
    for relative_path in IMPLEMENTATION_SOURCE_PATHS:
        tracked = _git(
            repo_root,
            "ls-files",
            "--error-unmatch",
            "--",
            relative_path,
        ).strip()
        if tracked != relative_path:
            raise ImplementationIdentityError(
                f"implementation source is not tracked: {relative_path}"
            )
        dirty = _git(
            repo_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            relative_path,
        ).strip()
        if dirty:
            raise ImplementationIdentityError(f"implementation source is dirty: {relative_path}")
        path = repo_root / relative_path
        raw = path.read_bytes()
        committed = _git_bytes(repo_root, "show", f"HEAD:{relative_path}")
        if raw != committed:
            raise ImplementationIdentityError(f"working source differs from HEAD: {relative_path}")
        rows.append(ImplementationSource(relative_path, sha256_hex(raw)))
    commit = _git(repo_root, "rev-parse", "HEAD").strip()
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}").strip()
    if _GIT_OBJECT.fullmatch(commit) is None or _GIT_OBJECT.fullmatch(tree) is None:
        raise ImplementationIdentityError("Git returned a non-canonical identity")
    return ImplementationIdentity(commit, tree, tuple(rows))


def materialize_canonical_forecast(
    *,
    operation_root: Path = OPERATION_ROOT,
    repo_root: Path | None = None,
    destination: Path | None = None,
    clock: Clock | None = None,
    specs: Sequence[FrozenStreamSpec] = FROZEN_STREAM_SPECS,
    expected_manifest_sha256: str | None = EXPECTED_STREAM_INPUT_MANIFEST_SHA256,
    implementation_identity: ImplementationIdentity | None = None,
    dry_run: bool = False,
) -> MaterializationResult:
    """Adapt the historical 087 inputs to the application-owned service."""

    _require_absolute_path(operation_root, "operation_root")
    spec_tuple = tuple(specs)
    records = read_persisted_prediction_records(operation_root, TARGET_DRAW_NUMBER)
    by_path = {record.source_relative_path: record for record in records}
    selected: list[PersistedForecastPrediction] = []
    registered: list[RegisteredForecastStream] = []
    for spec in spec_tuple:
        record = by_path.get(spec.source_relative_path)
        if record is None:
            raise FrozenInputError(f"missing frozen input: {spec.source_relative_path}")
        selected.append(
            PersistedForecastPrediction(
                source_relative_path=record.source_relative_path,
                source_sha256=record.source_sha256,
                raw_bytes=record.raw_bytes,
                payload=record.payload,
            )
        )
        registered.append(
            RegisteredForecastStream(
                strategy_id=spec.strategy_id,
                strategy_version=spec.strategy_version,
                native_ticket_count=spec.native_ticket_count,
            )
        )
    effective_repo = Path(__file__).resolve().parents[1] if repo_root is None else repo_root
    _require_absolute_path(effective_repo, "repo_root")
    identity = (
        resolve_implementation_identity(effective_repo)
        if implementation_identity is None
        else implementation_identity
    )
    request = _request(
        selected,
        registered,
        identity,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    output = operation_root / FORECAST_RELATIVE_PATH if destination is None else destination
    result = _materialize_service(
        request,
        destination=output,
        authority=_authority_port(),
        clock=(lambda: datetime.now(UTC)) if clock is None else clock,
        dry_run=dry_run,
    )
    return _materialization_result(result)


def _request(
    predictions: Sequence[PersistedForecastPrediction],
    registered: Sequence[RegisteredForecastStream],
    identity: ImplementationIdentity,
    *,
    expected_manifest_sha256: str | None,
) -> CanonicalForecastMaterializationRequest:
    return CanonicalForecastMaterializationRequest(
        task_id=TASK_ID,
        upstream_task_id=UPSTREAM_TASK_ID,
        target=CanonicalForecastTarget(
            lottery_type=LOTTERY_TYPE,
            draw_number=TARGET_DRAW_NUMBER,
            draw_date=TARGET_DRAW_DATE,
            scheduled_at=TARGET_SCHEDULED_AT,
        ),
        max_data_cutoff=CanonicalForecastCutoff(MAX_DATA_CUTOFF, MAX_DATA_CUTOFF_DATE),
        history=CanonicalHistoryIdentity(
            cutoff_draw_number=MAX_DATA_CUTOFF,
            cutoff_date=MAX_DATA_CUTOFF_DATE,
            draw_count=HISTORY_DRAW_COUNT,
            history_sha256=HISTORY_SHA256,
            history_caveat=HISTORY_CAVEAT,
        ),
        registered_streams=tuple(registered),
        predictions=tuple(predictions),
        implementation_identity=identity,
        expected_manifest_sha256=expected_manifest_sha256,
    )


def materialize_dynamic_canonical_forecast(
    *,
    context: CanonicalConsensusContext | None = None,
    operation_root: Path,
    repo_root: Path | None = None,
    destination: Path | None = None,
    clock: Clock | None = None,
    implementation_identity: ImplementationIdentity | None = None,
    request: CanonicalForecastMaterializationRequest | None = None,
    predictions: Sequence[PersistedForecastPrediction] = (),
    registered_streams: Sequence[RegisteredForecastStream] = (),
    expected_manifest_sha256: str | None = None,
    task_id: str = "B649_GOALC_LOCAL_LAUNCHD_R1",
    upstream_task_id: str = UPSTREAM_TASK_ID,
    dry_run: bool = False,
) -> MaterializationResult:
    """Adapt a dynamic request to the application-owned materialization service.

    The production scheduler calls the application service directly.  This
    compatibility adapter remains available for focused tooling/tests, but it
    accepts the same raw prediction records and registered stream identities;
    it never aggregates or writes an authority itself.
    """

    _require_absolute_path(operation_root, "operation_root")
    if request is None:
        if context is None:
            raise ForecastMaterializationError(
                "dynamic materialization requires a context or application request"
            )
        effective_identity = implementation_identity
        if effective_identity is None:
            root = Path(__file__).resolve().parents[1] if repo_root is None else repo_root
            _require_absolute_path(root, "repo_root")
            effective_identity = resolve_implementation_identity(root)
        if not predictions or not registered_streams:
            raise ForecastMaterializationError(
                "dynamic materialization requires raw predictions and registered streams"
            )
        request = _request_from_context(
            context,
            predictions=predictions,
            registered_streams=registered_streams,
            identity=effective_identity,
            expected_manifest_sha256=expected_manifest_sha256,
            task_id=task_id,
            upstream_task_id=upstream_task_id,
        )
    output = (
        canonical_forecast_path(
            operation_root,
            request.target.draw_number,
        )
        if destination is None
        else destination
    )
    result = _materialize_service(
        request,
        destination=output,
        authority=_authority_port(),
        clock=(lambda: datetime.now(UTC)) if clock is None else clock,
        dry_run=dry_run,
    )
    return _materialization_result(result)


def load_canonical_forecast_authority(
    *,
    operation_root: Path,
    destination: Path | None = None,
    request: CanonicalForecastMaterializationRequest | None = None,
    context: CanonicalConsensusContext | None = None,
    repo_root: Path | None = None,
    predictions: Sequence[PersistedForecastPrediction] = (),
    registered_streams: Sequence[RegisteredForecastStream] = (),
    implementation_identity: ImplementationIdentity | None = None,
    expected_manifest_sha256: str | None = None,
    task_id: str = "B649_GOALC_LOCAL_LAUNCHD_R1",
    upstream_task_id: str = UPSTREAM_TASK_ID,
) -> dict[str, object]:
    """Read and validate one existing authority without any write or clock read."""

    _require_absolute_path(operation_root, "operation_root")
    if request is None:
        if context is None:
            raise ForecastMaterializationError(
                "authority validation requires a context or application request"
            )
        effective_identity = implementation_identity
        if effective_identity is None:
            root = Path(__file__).resolve().parents[1] if repo_root is None else repo_root
            _require_absolute_path(root, "repo_root")
            effective_identity = resolve_implementation_identity(root)
        if not predictions or not registered_streams:
            raise ForecastMaterializationError(
                "authority validation requires raw predictions and registered streams"
            )
        request = _request_from_context(
            context,
            predictions=predictions,
            registered_streams=registered_streams,
            identity=effective_identity,
            expected_manifest_sha256=expected_manifest_sha256,
            task_id=task_id,
            upstream_task_id=upstream_task_id,
        )
    output = (
        canonical_forecast_path(operation_root, request.target.draw_number)
        if destination is None
        else destination
    )
    if read_existing_bytes(output) is None:
        raise ForecastAuthorityMissingError(f"canonical forecast authority is absent: {output}")
    result = _materialize_service(
        request,
        destination=output,
        authority=_authority_port(),
        clock=lambda: datetime.now(UTC),
        dry_run=True,
    )
    if result.publication != "ALREADY_PRESENT":
        raise ForecastAuthorityConflictError(
            "existing authority was not validated as already present"
        )
    return result.payload


def _request_from_context(
    context: CanonicalConsensusContext,
    *,
    predictions: Sequence[PersistedForecastPrediction],
    registered_streams: Sequence[RegisteredForecastStream],
    identity: ImplementationIdentity,
    expected_manifest_sha256: str | None,
    task_id: str,
    upstream_task_id: str,
) -> CanonicalForecastMaterializationRequest:
    return CanonicalForecastMaterializationRequest(
        task_id=task_id,
        upstream_task_id=upstream_task_id,
        target=CanonicalForecastTarget(
            lottery_type=context.lottery_type,
            draw_number=context.target_draw_number,
            draw_date=context.target_draw_date,
            scheduled_at=context.scheduled_at.isoformat(),
        ),
        max_data_cutoff=CanonicalForecastCutoff(
            context.causal_cutoff_draw_number,
            context.causal_cutoff_date,
        ),
        history=CanonicalHistoryIdentity(
            cutoff_draw_number=context.causal_cutoff_draw_number,
            cutoff_date=context.causal_cutoff_date,
            draw_count=context.history_draw_count,
            history_sha256=context.history_sha256,
            history_caveat=context.history_caveat,
        ),
        registered_streams=tuple(registered_streams),
        predictions=tuple(predictions),
        implementation_identity=identity,
        expected_manifest_sha256=expected_manifest_sha256,
    )


def _authority_port() -> CanonicalForecastAuthorityPort:
    return CanonicalForecastAuthorityPort(
        read_existing_bytes=read_existing_bytes,
        ensure_output_parent=ensure_output_parent,
        stage_payload=stage_payload,
        publish_staged=publish_staged,
        discard_staged=discard_staged,
    )


def _materialization_result(
    service_result: CanonicalForecastMaterializationResult,
) -> MaterializationResult:
    status_value = service_result.status
    if status_value == "DRY_RUN":
        status: Literal["CREATED", "ALREADY_PRESENT", "DRY_RUN"] = "DRY_RUN"
    else:
        publication = service_result.publication
        if publication not in {"CREATED", "ALREADY_PRESENT"}:
            raise ForecastMaterializationError("application service returned no publication")
        status = publication
    return MaterializationResult(
        status=status,
        destination=service_result.destination,
        payload=service_result.payload,
    )


def canonical_forecast_path(operation_root: Path, target_draw_number: str) -> Path:
    """Return the canonical forecast hierarchy for one validated target number."""

    _require_absolute_path(operation_root, "operation_root")
    if type(target_draw_number) is not str or not re.fullmatch(
        r"[0-9]+", target_draw_number, flags=re.ASCII
    ):
        raise ForecastMaterializationError("target draw number is not numeric text")
    return (
        operation_root
        / "forecasts"
        / target_draw_number
        / CANONICAL_CONSENSUS_METHOD_ID
        / CANONICAL_CONSENSUS_METHOD_VERSION
        / "final_forecast_payload.json"
    )


def _require_absolute_path(path: Path, label: str) -> None:
    if not isinstance(path, Path) or not path.is_absolute():
        raise ForecastMaterializationError(f"{label} must be an absolute Path")


def _require_context(value: object) -> CanonicalConsensusContext:
    if not isinstance(value, CanonicalConsensusContext):
        raise ForecastMaterializationError("canonical forecast context has the wrong type")
    return value


def _materialize_context(
    *,
    context: CanonicalConsensusContext,
    operation_root: Path,
    destination: Path,
    clock: Clock | None,
    implementation_identity: ImplementationIdentity | None,
    task_id: str,
    upstream_task_id: str,
    dry_run: bool,
) -> MaterializationResult:
    _require_absolute_path(operation_root, "operation_root")
    # Idempotent retries never sample the clock or stage a replacement.  The
    # existing bytes are independently checked against the immutable base and
    # its own original created_at window.
    existing = read_existing_bytes(destination)
    if existing is not None:
        payload = _validate_existing_payload(
            existing,
            context,
            operation_root=operation_root,
            destination=destination,
        )
        return MaterializationResult("ALREADY_PRESENT", destination, payload)
    if dry_run:
        decision = build_canonical_consensus(context)
        base = _base_payload(
            decision,
            context,
            implementation_identity,
            task_id=task_id,
            upstream_task_id=upstream_task_id,
        )
        return MaterializationResult("DRY_RUN", destination, base)

    decision = build_canonical_consensus(context)
    base = _base_payload(
        decision,
        context,
        implementation_identity,
        task_id=task_id,
        upstream_task_id=upstream_task_id,
    )
    now = _clock(clock)
    _require_creation_window(now, context, context_label="created_at")
    created_payload = {**base, "created_at": _format_timestamp(now)}
    payload_bytes = canonical_file_bytes(created_payload)

    # Directory creation and staging happen before the final clock sample;
    # neither operation can create the authority destination itself.
    ensure_output_parent(destination)
    staged: StagedCanonicalForecast | None = None
    try:
        staged = stage_payload(destination, payload_bytes)
        pre_publish_now = _clock(clock)
        if _as_utc(pre_publish_now) >= context.scheduled_at.astimezone(UTC):
            raise PreOutcomeWindowClosedError(
                "pre_publish_now must be strictly before scheduled_at"
            )
        # Keep this call directly adjacent to the second clock boundary.  The
        # writer's first operation is the atomic no-overwrite link.
        result = publish_staged(staged)
        if result.status == "CREATED":
            observed = read_existing_bytes(destination)
            if observed != payload_bytes:
                raise ForecastAuthorityConflictError(
                    "read-after-write authority bytes differ from the staged payload"
                )
            return MaterializationResult("CREATED", destination, created_payload)
        observed = read_existing_bytes(destination)
        if observed is None:
            raise ForecastAuthorityConflictError(
                "atomic publication reported an existing authority that disappeared"
            )
        existing_payload = _validate_existing_payload(
            observed,
            context,
            operation_root=operation_root,
            destination=destination,
        )
        return MaterializationResult("ALREADY_PRESENT", destination, existing_payload)
    finally:
        # publish_staged owns normal temporary cleanup.  This branch handles a
        # closed second boundary before publish_staged is entered.
        if staged is not None and staged.temporary.exists():
            try:
                staged.temporary.unlink()
            except OSError as exc:
                raise ForecastMaterializationError(
                    "staged temporary cleanup failed after an aborted publication"
                ) from exc


def _base_payload(
    decision: CanonicalConsensusDecision,
    context: CanonicalConsensusContext,
    identity: ImplementationIdentity | None,
    *,
    task_id: str,
    upstream_task_id: str,
) -> dict[str, object]:
    # ``decision`` is kept as an object at this boundary so this helper remains
    # easy to audit: only the domain serializer supplies ranking and manifest
    # fields, while this module supplies authority and provenance metadata.
    decision_payload = decision.to_payload(
        task_id=task_id,
        lottery_type=context.lottery_type,
    )
    if decision_payload.get("stream_count") != EXPECTED_STREAM_COUNT:
        raise FrozenInputError("decision stream count is not eleven")
    if decision_payload.get("stream_input_manifest_sha256") is None:
        raise FrozenInputError("decision has no stream input manifest")
    payload: dict[str, object] = {
        **decision_payload,
        "task_id": task_id,
        "target_draw": {
            "draw_number": context.target_draw_number,
            "draw_date": context.target_draw_date,
        },
        "scheduled_at": context.scheduled_at.isoformat(),
        "max_data_cutoff": {
            "draw_number": context.causal_cutoff_draw_number,
            "draw_date": context.causal_cutoff_date,
        },
        "history_sha256": context.history_sha256,
        "history_draw_count": context.history_draw_count,
        "history_caveat": context.history_caveat,
        "target_result_used": False,
        "aggregation_contract_review_id": AGGREGATION_CONTRACT_REVIEW_ID,
        "aggregation_contract_approved_at": AGGREGATION_CONTRACT_APPROVED_AT,
        "decision_ranking_formula": DECISION_RANKING_FORMULA,
        "pre_outcome_temporal_integrity": "PASS",
        "upstream_task_id": upstream_task_id,
    }
    if identity is not None:
        source_rows = [
            {"path": source.path, "sha256": source.sha256}
            for source in sorted(identity.source_hashes, key=lambda item: item.path)
        ]
        if tuple(row["path"] for row in source_rows) != IMPLEMENTATION_SOURCE_PATHS:
            raise ImplementationIdentityError("implementation source hash scope is not exact")
        payload.update(
            {
                "implementation_commit": identity.commit,
                "implementation_tree": identity.tree,
                "implementation_source_hashes": source_rows,
            }
        )
    return payload


def _validate_existing_payload(
    raw: bytes,
    context: CanonicalConsensusContext | None,
    *,
    operation_root: Path,
    destination: Path,
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
    except (ValueError, UnicodeDecodeError) as exc:
        raise ForecastAuthorityConflictError("existing authority is not valid JSON") from exc
    parsed_value: object = parsed
    if not isinstance(parsed_value, dict):
        raise ForecastAuthorityConflictError("existing authority is not one JSON object")
    payload = cast(dict[str, object], parsed_value)
    try:
        canonical = canonical_file_bytes(payload)
    except ValueError as exc:
        raise ForecastAuthorityConflictError(
            "existing authority leaves the canonical JSON domain"
        ) from exc
    if canonical != raw:
        raise ForecastAuthorityConflictError("existing authority is not canonical JSON")

    try:
        _reject_forbidden_keys(payload, destination)
    except FrozenInputError as exc:
        raise ForecastAuthorityConflictError(str(exc)) from exc
    forbidden_compatibility_keys = _NONCANONICAL_AUTHORITY_KEYS.intersection(payload)
    if forbidden_compatibility_keys:
        raise ForecastAuthorityConflictError(
            "existing authority contains noncanonical descriptive keys: "
            + ", ".join(sorted(forbidden_compatibility_keys))
        )

    expected_target_number = TARGET_DRAW_NUMBER if context is None else context.target_draw_number
    expected_target_date = TARGET_DRAW_DATE if context is None else context.target_draw_date
    expected_scheduled_at = (
        _parse_timestamp(TARGET_SCHEDULED_AT, "target scheduled_at")
        if context is None
        else context.scheduled_at
    )
    expected_cutoff_number = (
        MAX_DATA_CUTOFF if context is None else context.causal_cutoff_draw_number
    )
    expected_cutoff_date = (
        MAX_DATA_CUTOFF_DATE if context is None else context.causal_cutoff_date
    )
    expected_history_count = (
        HISTORY_DRAW_COUNT if context is None else context.history_draw_count
    )
    expected_history_sha = HISTORY_SHA256 if context is None else context.history_sha256
    expected_history_caveat = HISTORY_CAVEAT if context is None else context.history_caveat

    if payload.get("schema_version") != CANONICAL_CONSENSUS_SCHEMA_VERSION:
        raise ForecastAuthorityConflictError("existing authority schema is invalid")
    if payload.get("lottery_type") != LOTTERY_TYPE:
        raise ForecastAuthorityConflictError("existing authority lottery type is invalid")
    if type(payload.get("task_id")) is not str or not cast(str, payload["task_id"]).strip():
        raise ForecastAuthorityConflictError("existing authority task_id is invalid")
    if (
        type(payload.get("upstream_task_id")) is not str
        or not cast(str, payload["upstream_task_id"]).strip()
    ):
        raise ForecastAuthorityConflictError("existing authority upstream_task_id is invalid")

    target_value = payload.get("target_draw")
    if not isinstance(target_value, Mapping):
        raise ForecastAuthorityConflictError("existing authority target is invalid")
    target = cast(Mapping[str, object], target_value)
    if (
        target.get("draw_number") != expected_target_number
        or target.get("draw_date") != expected_target_date
    ):
        raise ForecastAuthorityConflictError("existing authority target does not match context")

    scheduled_value = payload.get("scheduled_at")
    if type(scheduled_value) is not str:
        raise ForecastAuthorityConflictError("existing authority scheduled_at is invalid")
    try:
        persisted_scheduled_at = _parse_timestamp(scheduled_value, "existing.scheduled_at")
    except FrozenInputError as exc:
        raise ForecastAuthorityConflictError(str(exc)) from exc
    if _as_utc(persisted_scheduled_at) != _as_utc(expected_scheduled_at):
        raise ForecastAuthorityConflictError(
            "existing authority scheduled_at does not match context"
        )

    cutoff_value = payload.get("max_data_cutoff")
    if not isinstance(cutoff_value, Mapping):
        raise ForecastAuthorityConflictError("existing authority max_data_cutoff is invalid")
    cutoff = cast(Mapping[str, object], cutoff_value)
    if (
        cutoff.get("draw_number") != expected_cutoff_number
        or cutoff.get("draw_date") != expected_cutoff_date
    ):
        raise ForecastAuthorityConflictError("existing authority cutoff does not match context")
    if payload.get("history_draw_count") != expected_history_count:
        raise ForecastAuthorityConflictError(
            "existing authority history count does not match context"
        )
    if payload.get("history_sha256") != expected_history_sha:
        raise ForecastAuthorityConflictError(
            "existing authority history digest does not match context"
        )
    if payload.get("history_caveat") != expected_history_caveat:
        raise ForecastAuthorityConflictError(
            "existing authority history caveat does not match context"
        )

    if payload.get("aggregation_method_id") != CANONICAL_CONSENSUS_METHOD_ID:
        raise ForecastAuthorityConflictError("existing authority method is invalid")
    if payload.get("aggregation_method_version") != CANONICAL_CONSENSUS_METHOD_VERSION:
        raise ForecastAuthorityConflictError("existing authority method version is invalid")
    for key, expected in (
        ("aggregation_unit", AGGREGATION_UNIT),
        ("weight_policy", STREAM_WEIGHT_POLICY),
        ("correlated_family_policy", CORRELATED_FAMILY_POLICY),
        ("tie_break", TIE_BREAK),
        ("score_denominator", SCORE_DENOMINATOR),
        ("target_result_used", False),
        ("pre_outcome_temporal_integrity", "PASS"),
    ):
        if payload.get(key) != expected:
            raise ForecastAuthorityConflictError(f"existing authority {key} is invalid")
    if payload.get("aggregation_contract_review_id") != AGGREGATION_CONTRACT_REVIEW_ID:
        raise ForecastAuthorityConflictError("existing authority contract review id is invalid")
    if payload.get("aggregation_contract_approved_at") != AGGREGATION_CONTRACT_APPROVED_AT:
        raise ForecastAuthorityConflictError("existing authority contract approval is invalid")
    if payload.get("decision_ranking_formula") != DECISION_RANKING_FORMULA:
        raise ForecastAuthorityConflictError("existing authority ranking formula is invalid")

    stream_ids_value = payload.get("exact_stream_ids")
    if not isinstance(stream_ids_value, list):
        raise ForecastAuthorityConflictError("existing authority stream identities are invalid")
    stream_ids = cast(list[object], stream_ids_value)
    if len(stream_ids) != EXPECTED_STREAM_COUNT:
        raise ForecastAuthorityConflictError("existing authority stream identities are invalid")
    stream_id_text: list[str] = []
    for value in stream_ids:
        if type(value) is not str or not value.strip():
            raise ForecastAuthorityConflictError(
                "existing authority stream identities are invalid"
            )
        stream_id_text.append(value)
    if len(set(stream_id_text)) != EXPECTED_STREAM_COUNT:
        raise ForecastAuthorityConflictError("existing authority stream identities are not unique")
    if context is not None:
        expected_stream_ids = sorted(stream.strategy_id for stream in context.streams)
        if stream_id_text != expected_stream_ids:
            raise ForecastAuthorityConflictError(
                "existing authority stream identities do not match context"
            )

    stream_inputs_value = payload.get("stream_inputs")
    if not isinstance(stream_inputs_value, list):
        raise ForecastAuthorityConflictError("existing authority stream inputs are invalid")
    stream_inputs = cast(list[object], stream_inputs_value)
    if len(stream_inputs) != EXPECTED_STREAM_COUNT:
        raise ForecastAuthorityConflictError("existing authority stream inputs are invalid")
    expected_stream_input_keys = {
        "native_ticket_count",
        "prediction_run_id",
        "source_relative_path",
        "source_sha256",
        "strategy_id",
        "strategy_version",
    }
    validated_input_rows: list[dict[str, object]] = []
    for position, value in enumerate(stream_inputs, start=1):
        if not isinstance(value, Mapping):
            raise ForecastAuthorityConflictError(
                f"existing authority stream input {position} is invalid"
            )
        row = cast(Mapping[str, object], value)
        if set(row) != expected_stream_input_keys:
            raise ForecastAuthorityConflictError(
                f"existing authority stream input {position} has the wrong fields"
            )
        native_count = row.get("native_ticket_count")
        if (
            type(native_count) is not int
            or native_count < 1
            or FINAL_TICKET_SIZE % native_count != 0
        ):
            raise ForecastAuthorityConflictError(
                f"existing authority stream input {position} has an invalid native count"
            )
        for key in ("prediction_run_id", "strategy_id", "strategy_version"):
            value_text = row.get(key)
            if type(value_text) is not str or not value_text.strip():
                raise ForecastAuthorityConflictError(
                    f"existing authority stream input {position} has invalid {key}"
                )
        relative_path = row.get("source_relative_path")
        if type(relative_path) is not str:
            raise ForecastAuthorityConflictError(
                f"existing authority stream input {position} has an unsafe source path"
            )
        if (
            not relative_path
            or relative_path.startswith("/")
            or "\\" in relative_path
            or any(part in {"", ".", ".."} for part in relative_path.split("/"))
        ):
            raise ForecastAuthorityConflictError(
                f"existing authority stream input {position} has an unsafe source path"
            )
        source_sha = row.get("source_sha256")
        if type(source_sha) is not str:
            raise ForecastAuthorityConflictError(
                f"existing authority stream input {position} has an invalid source digest"
            )
        if _SHA256.fullmatch(source_sha) is None:
            raise ForecastAuthorityConflictError(
                f"existing authority stream input {position} has an invalid source digest"
            )
        validated_input_rows.append(dict(row))
    if [cast(str, row["strategy_id"]) for row in validated_input_rows] != stream_id_text:
        raise ForecastAuthorityConflictError(
            "existing authority stream input identities do not match exact_stream_ids"
        )
    manifest_value = payload.get("stream_input_manifest_sha256")
    if type(manifest_value) is not str or _SHA256.fullmatch(manifest_value) is None:
        raise ForecastAuthorityConflictError("existing authority stream manifest is invalid")
    manifest_bytes = json.dumps(
        validated_input_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_value:
        raise ForecastAuthorityConflictError(
            "existing authority stream manifest does not match persisted inputs"
        )

    ranking_value = payload.get("final_decision_ranking")
    if not isinstance(ranking_value, list):
        raise ForecastAuthorityConflictError("existing authority ranking is invalid")
    ranking = cast(list[object], ranking_value)
    if len(ranking) != 49:
        raise ForecastAuthorityConflictError("existing authority ranking is invalid")
    ranking_numbers: list[int] = []
    ranking_support: list[int] = []
    for expected_rank, value in enumerate(ranking, start=1):
        if not isinstance(value, Mapping):
            raise ForecastAuthorityConflictError("existing authority ranking row is invalid")
        row = cast(Mapping[str, object], value)
        if row.get("rank") != expected_rank:
            raise ForecastAuthorityConflictError("existing authority ranking ranks are invalid")
        number = row.get("number")
        support_units = row.get("support_units")
        if (
            type(number) is not int
            or number < 1
            or number > 49
            or type(support_units) is not int
            or support_units < 0
        ):
            raise ForecastAuthorityConflictError("existing authority ranking values are invalid")
        ranking_numbers.append(number)
        ranking_support.append(support_units)
    if (
        sorted(ranking_numbers) != list(range(1, 50))
        or sum(ranking_support) != EXPECTED_STREAM_COUNT * FINAL_TICKET_SIZE * FINAL_TICKET_SIZE
    ):
        raise ForecastAuthorityConflictError("existing authority ranking conservation is invalid")
    if ranking != sorted(
        ranking,
        key=lambda value: (
            -cast(int, cast(Mapping[str, object], value)["support_units"]),
            cast(int, cast(Mapping[str, object], value)["number"]),
        ),
    ):
        raise ForecastAuthorityConflictError("existing authority ranking tie-break is invalid")

    final_output_value = payload.get("final_recommended_output")
    if not isinstance(final_output_value, list):
        raise ForecastAuthorityConflictError("existing authority final output is invalid")
    final_output_rows = cast(list[object], final_output_value)
    if len(final_output_rows) != 1 or not isinstance(final_output_rows[0], Mapping):
        raise ForecastAuthorityConflictError("existing authority final output is invalid")
    final_output = cast(Mapping[str, object], final_output_rows[0])
    if final_output.get("ticket_position") != 1:
        raise ForecastAuthorityConflictError("existing authority ticket position is invalid")
    final_numbers_value = final_output.get("predicted_numbers")
    if not isinstance(final_numbers_value, list):
        raise ForecastAuthorityConflictError("existing authority final ticket is invalid")
    final_numbers = cast(list[object], final_numbers_value)
    if len(final_numbers) != FINAL_TICKET_SIZE:
        raise ForecastAuthorityConflictError("existing authority final ticket is invalid")
    if (
        any(type(number) is not int or number < 1 or number > 49 for number in final_numbers)
        or len(set(final_numbers)) != FINAL_TICKET_SIZE
        or final_numbers != sorted(cast(list[int], final_numbers))
        or set(cast(list[int], final_numbers)) != set(ranking_numbers[:FINAL_TICKET_SIZE])
    ):
        raise ForecastAuthorityConflictError("existing authority final ticket is inconsistent")

    created_value = payload.get("created_at")
    if type(created_value) is not str:
        raise ForecastAuthorityConflictError("existing authority has no canonical created_at")
    try:
        created_at = _parse_timestamp(created_value, "existing.created_at")
    except FrozenInputError as exc:
        raise ForecastAuthorityConflictError(str(exc)) from exc
    if _as_utc(created_at) < _as_utc(
        _parse_timestamp(AGGREGATION_CONTRACT_APPROVED_AT, "approval")
    ) or _as_utc(created_at) >= _as_utc(expected_scheduled_at):
        raise ForecastAuthorityConflictError(
            "existing authority created_at is outside the PRE_OUTCOME window"
        )
    if context is not None and any(
        _as_utc(stream.prediction_created_at) > _as_utc(created_at)
        for stream in context.streams
    ):
        raise ForecastAuthorityConflictError(
            "existing authority created_at is earlier than a persisted stream prediction"
        )

    implementation_keys = {
        "implementation_commit",
        "implementation_tree",
        "implementation_source_hashes",
    }
    present_implementation_keys = implementation_keys.intersection(payload)
    if present_implementation_keys and present_implementation_keys != implementation_keys:
        raise ForecastAuthorityConflictError(
            "existing authority implementation provenance is incomplete"
        )
    if present_implementation_keys:
        commit = payload.get("implementation_commit")
        tree = payload.get("implementation_tree")
        hashes_value = payload.get("implementation_source_hashes")
        if (
            type(commit) is not str
            or _GIT_OBJECT.fullmatch(commit) is None
            or type(tree) is not str
            or _GIT_OBJECT.fullmatch(tree) is None
            or not isinstance(hashes_value, list)
        ):
            raise ForecastAuthorityConflictError(
                "existing authority implementation provenance is invalid"
            )
        hashes = cast(list[object], hashes_value)
        if len(hashes) != len(IMPLEMENTATION_SOURCE_PATHS):
            raise ForecastAuthorityConflictError(
                "existing authority implementation source scope is invalid"
            )
        observed_paths: list[str] = []
        for value in hashes:
            if not isinstance(value, Mapping):
                raise ForecastAuthorityConflictError(
                    "existing authority implementation source row is invalid"
                )
            row = cast(Mapping[str, object], value)
            path_value = row.get("path")
            digest_value = row.get("sha256")
            if (
                type(path_value) is not str
                or type(digest_value) is not str
                or _SHA256.fullmatch(digest_value) is None
            ):
                raise ForecastAuthorityConflictError(
                    "existing authority implementation source row is invalid"
                )
            observed_paths.append(path_value)
        if tuple(observed_paths) != IMPLEMENTATION_SOURCE_PATHS:
            raise ForecastAuthorityConflictError(
                "existing authority implementation source scope is invalid"
            )

    if (
        expected_target_number == TARGET_DRAW_NUMBER
        and operation_root == OPERATION_ROOT
        and destination == OPERATION_ROOT / FORECAST_RELATIVE_PATH
        and hashlib.sha256(raw).hexdigest() != HISTORICAL_087_AUTHORITY_SHA256
    ):
        raise ForecastAuthorityConflictError(
            "historical 115000087 authority digest does not match the pinned artifact"
        )
    return payload


def _require_creation_window(
    created_at: datetime,
    context: CanonicalConsensusContext,
    *,
    context_label: str,
) -> None:
    created_utc = _as_utc(created_at)
    scheduled_utc = _as_utc(context.scheduled_at)
    approved_utc = _as_utc(_parse_timestamp(AGGREGATION_CONTRACT_APPROVED_AT, "approval"))
    if any(_as_utc(stream.prediction_created_at) > created_utc for stream in context.streams):
        raise PreOutcomeWindowClosedError(
            f"{context_label} is earlier than a prediction_created_at"
        )
    if approved_utc > created_utc:
        raise PreOutcomeWindowClosedError(
            f"{context_label} is earlier than aggregation_contract_approved_at"
        )
    if created_utc >= scheduled_utc:
        raise PreOutcomeWindowClosedError(
            f"{context_label} must be strictly before scheduled_at"
        )


def _read_json_object(path: Path, operation_root: Path) -> tuple[bytes, dict[str, object]]:
    raw = _read_regular_file(path, operation_root)
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise FrozenInputError(f"{path}: invalid JSON source") from exc
    if not isinstance(parsed, dict):
        raise FrozenInputError(f"{path}: source must contain one JSON object")
    return raw, cast(dict[str, object], parsed)


def _read_regular_file(path: Path, root: Path) -> bytes:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise FrozenInputError(f"source path escapes operation_root: {path}") from exc
    current = root
    try:
        metadata = current.lstat()
    except OSError as exc:
        raise FrozenInputError(f"cannot inspect operation_root: {root}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise FrozenInputError("operation_root is not a directory")
    for part in relative.parts:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError as exc:
            raise FrozenInputError(f"missing frozen input: {current}") from exc
        except OSError as exc:
            raise FrozenInputError(f"cannot inspect frozen input: {current}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise FrozenInputError(f"symlink is forbidden in frozen input path: {current}")
    if not stat.S_ISREG(metadata.st_mode):
        raise FrozenInputError(f"frozen input is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise FrozenInputError(f"cannot read frozen input: {path}") from exc


def _read_committed_source(path: Path) -> bytes:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ImplementationIdentityError(
                f"implementation source is not a regular file: {path}"
            )
        return path.read_bytes()
    except ImplementationIdentityError:
        raise
    except OSError as exc:
        raise ImplementationIdentityError(f"cannot read implementation source: {path}") from exc


def _validate_spec(spec: FrozenStreamSpec) -> None:
    if not spec.strategy_id or not spec.strategy_version:
        raise FrozenInputError("frozen stream identity fields must be non-empty")
    if spec.native_ticket_count < 1 or FINAL_TICKET_SIZE % spec.native_ticket_count:
        raise FrozenInputError("frozen native_ticket_count must divide six")
    if (
        not spec.source_relative_path
        or spec.source_relative_path.startswith("/")
        or "\\" in spec.source_relative_path
        or any(part in {"", ".", ".."} for part in spec.source_relative_path.split("/"))
    ):
        raise FrozenInputError("frozen source path is not safe relative POSIX text")


def _reject_forbidden_keys(value: object, source_path: Path) -> None:
    if isinstance(value, dict):
        mapping = cast(Mapping[str, object], value)
        for key, item in mapping.items():
            if key in _FORBIDDEN_KEYS:
                raise FrozenInputError(
                    f"{source_path}: forbidden outcome/scoring key observed: {key}"
                )
            _reject_forbidden_keys(item, source_path)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _reject_forbidden_keys(item, source_path)


def _expect(value: Mapping[str, object], key: str, expected: object, source_path: Path) -> None:
    if value.get(key) != expected:
        raise FrozenInputError(f"{source_path}: {key} does not equal frozen value")


def _required_text(value: Mapping[str, object], key: str, source_path: Path) -> str:
    item = value.get(key)
    if type(item) is not str or not item.strip():
        raise FrozenInputError(f"{source_path}: {key} must be non-empty text")
    return item


def _required_int(value: Mapping[str, object], key: str, source_path: Path) -> int:
    item = value.get(key)
    if type(item) is not int:
        raise FrozenInputError(f"{source_path}: {key} must be an integer")
    return item


def _parse_timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FrozenInputError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FrozenInputError(f"{label} must be timezone-aware")
    return parsed


def _format_timestamp(value: datetime) -> str:
    return _as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PreOutcomeWindowClosedError("clock must return a timezone-aware datetime")
    return value.astimezone(UTC)


def _clock(provider: Clock | None) -> datetime:
    value = datetime.now(UTC) if provider is None else provider()
    if type(value) is not datetime:
        raise PreOutcomeWindowClosedError("clock must return a datetime")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _git(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ImplementationIdentityError(f"git command failed: git {' '.join(args)}") from exc
    return result.stdout


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ImplementationIdentityError(f"git command failed: git {' '.join(args)}") from exc
    return result.stdout


def _default_destination(operation_root: Path) -> Path:
    return operation_root / FORECAST_RELATIVE_PATH


def _canonical_summary(result: MaterializationResult) -> str:
    return json.dumps(
        {
            "destination": str(result.destination),
            "status": result.status,
            "created_at": result.payload.get("created_at"),
            "final_ticket": result.payload.get("final_recommended_output"),
            "implementation_commit": result.payload.get("implementation_commit"),
            "stream_input_manifest_sha256": result.payload.get("stream_input_manifest_sha256"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation-root", type=Path, default=OPERATION_ROOT)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    destination = args.destination
    if destination is None:
        destination = _default_destination(args.operation_root)
    try:
        result = materialize_canonical_forecast(
            operation_root=args.operation_root,
            repo_root=args.repo_root,
            destination=destination,
            dry_run=bool(args.dry_run),
        )
    except CanonicalForecastMaterializationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AGGREGATION_CONTRACT_APPROVED_AT",
    "AGGREGATION_CONTRACT_REVIEW_ID",
    "AGGREGATION_UNIT",
    "CANONICAL_CONSENSUS_METHOD_ID",
    "CANONICAL_CONSENSUS_METHOD_VERSION",
    "CANONICAL_CONSENSUS_SCHEMA_VERSION",
    "CORRELATED_FAMILY_POLICY",
    "DECISION_RANKING_FORMULA",
    "EXPECTED_STREAM_COUNT",
    "EXPECTED_STREAM_INPUT_MANIFEST_SHA256",
    "FINAL_TICKET_SIZE",
    "FORECAST_RELATIVE_PATH",
    "FROZEN_STREAM_SPECS",
    "IMPLEMENTATION_SOURCE_PATHS",
    "LOTTERY_TYPE",
    "MAX_DATA_CUTOFF",
    "MAX_DATA_CUTOFF_DATE",
    "OPERATION_ROOT",
    "STREAM_WEIGHT_POLICY",
    "TARGET_DRAW_DATE",
    "TARGET_DRAW_NUMBER",
    "TARGET_SCHEDULED_AT",
    "TASK_ID",
    "TIE_BREAK",
    "UPSTREAM_TASK_ID",
    "CanonicalConsensusContext",
    "ForecastAuthorityConflictError",
    "ForecastAuthorityMissingError",
    "ForecastMaterializationError",
    "FrozenInputBundle",
    "FrozenInputError",
    "FrozenStreamSpec",
    "ImplementationIdentity",
    "ImplementationIdentityError",
    "ImplementationSource",
    "MaterializationResult",
    "PreOutcomeWindowClosedError",
    "canonical_forecast_path",
    "load_canonical_forecast_authority",
    "load_frozen_stream_inputs",
    "materialize_canonical_forecast",
    "materialize_dynamic_canonical_forecast",
    "resolve_implementation_identity",
]
