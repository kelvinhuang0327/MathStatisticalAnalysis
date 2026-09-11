"""Historical 087 adapter for the reusable B649 forecast service.

The production scheduler does not import this module.  Its 087 constants and
frozen source paths remain only to support bounded compatibility verification
of the already-published historical authority.
"""

from __future__ import annotations

import argparse
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
    STREAM_WEIGHT_POLICY,
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
    if not path.is_absolute():
        raise ForecastMaterializationError(f"{label} must be an absolute Path")


def _git(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ImplementationIdentityError(
            f"git command failed: git {' '.join(args)}"
        ) from exc
    return result.stdout


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ImplementationIdentityError(
            f"git command failed: git {' '.join(args)}"
        ) from exc
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
