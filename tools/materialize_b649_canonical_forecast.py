"""Materialize the immutable PRE_OUTCOME B649 stream-consensus authority.

The materializer is intentionally separate from the operational prediction
loop.  It consumes the eleven already-persisted prediction records, validates
their identities and temporal class, computes the pure number-level consensus,
binds the exact committed implementation bytes, and publishes one canonical
file with a two-sample clock boundary and no-overwrite semantics.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lottolab.domain.b649_canonical_consensus import (
    AGGREGATION_CONTRACT_APPROVED_AT,
    AGGREGATION_CONTRACT_REVIEW_ID,
    AGGREGATION_UNIT,
    CANONICAL_CONSENSUS_METHOD_ID,
    CANONICAL_CONSENSUS_METHOD_VERSION,
    CANONICAL_CONSENSUS_SCHEMA_VERSION,
    CORRELATED_FAMILY_POLICY,
    EXPECTED_STREAM_COUNT,
    FINAL_TICKET_SIZE,
    HISTORY_CAVEAT,
    HISTORY_DRAW_COUNT,
    HISTORY_SHA256,
    MAX_DATA_CUTOFF,
    MAX_DATA_CUTOFF_DATE,
    PRE_DRAW,
    TARGET_DRAW_DATE,
    TARGET_DRAW_NUMBER,
    TARGET_SCHEDULED_AT,
    CanonicalConsensusDecision,
    StreamConsensusInput,
    build_canonical_consensus,
)
from lottolab.evidence.canonical_json import canonical_bytes, canonical_file_bytes, sha256_hex
from lottolab.infrastructure.b649_canonical_forecast_writer import (
    StagedCanonicalForecast,
    ensure_output_parent,
    publish_staged,
    read_existing_bytes,
    stage_payload,
)

TASK_ID: Final = (
    "B649_11_STREAM_CANONICAL_AGGREGATION_IMPLEMENT_AND_MATERIALIZE_115000087_R1"
)
UPSTREAM_TASK_ID: Final = "B649_OPERATIONAL_PREDICTION_LOOP_R1"
LOTTERY_TYPE: Final = "BIG_LOTTO"
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
DECISION_RANKING_FORMULA: Final = (
    "U(n)=sum_i((6/k_i)*c_i(n)); rank by U(n) descending, then number ascending; "
    "each stream has equal weight and c_i(n) counts native ticket positions containing n"
)
IMPLEMENTATION_SOURCE_PATHS: Final = (
    "src/lottolab/domain/b649_canonical_consensus.py",
    "src/lottolab/infrastructure/b649_canonical_forecast_writer.py",
    "tools/materialize_b649_canonical_forecast.py",
)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_GIT_OBJECT = re.compile(r"[0-9a-f]{40,64}", flags=re.ASCII)
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


class ForecastMaterializationError(RuntimeError):
    """The requested forecast cannot be materialized safely."""


class FrozenInputError(ForecastMaterializationError):
    """A supposedly frozen prediction input is absent, malformed, or mismatched."""


class ImplementationIdentityError(ForecastMaterializationError):
    """The implementation source is not exactly the committed source identity."""


class PreOutcomeWindowClosedError(ForecastMaterializationError):
    """One of the two PRE_OUTCOME publication boundaries is closed."""

    code: Final = "BLOCKED_PRE_OUTCOME_WINDOW_CLOSED"

    def __init__(self, detail: str) -> None:
        super().__init__(f"{self.code}: {detail}")


class ForecastAuthorityConflictError(ForecastMaterializationError):
    """The immutable authority exists with different or invalid content."""

    code: Final = "BLOCK_FORECAST_AUTHORITY_REMEDIATION_REQUIRED"

    def __init__(self, detail: str) -> None:
        super().__init__(f"{self.code}: {detail}")


@dataclass(frozen=True, slots=True)
class FrozenStreamSpec:
    """The exact stream identity and native cardinality accepted for this run."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    source_relative_path: str


@dataclass(frozen=True, slots=True)
class FrozenInputBundle:
    """Validated inputs plus the shared target schedule used by the materializer."""

    streams: tuple[StreamConsensusInput, ...]
    scheduled_at: datetime


@dataclass(frozen=True, slots=True)
class ImplementationSource:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ImplementationIdentity:
    """Git identity and raw hashes for every source file in the implementation scope."""

    commit: str
    tree: str
    source_hashes: tuple[ImplementationSource, ...]


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    """Publication status and the exact payload observed after the operation."""

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
UTC = timezone.utc  # noqa: UP017


def load_frozen_stream_inputs(
    operation_root: Path = OPERATION_ROOT,
    *,
    specs: Sequence[FrozenStreamSpec] = FROZEN_STREAM_SPECS,
    expected_manifest_sha256: str | None = EXPECTED_STREAM_INPUT_MANIFEST_SHA256,
) -> FrozenInputBundle:
    """Read and validate only the eleven exact PRE_DRAW source files."""

    _require_absolute_path(operation_root, "operation_root")
    spec_tuple = tuple(specs)
    if len(spec_tuple) != EXPECTED_STREAM_COUNT:
        raise FrozenInputError(f"expected exactly {EXPECTED_STREAM_COUNT} stream specs")
    if len({spec.strategy_id for spec in spec_tuple}) != len(spec_tuple):
        raise FrozenInputError("frozen stream strategy ids must be unique")
    if len({spec.source_relative_path for spec in spec_tuple}) != len(spec_tuple):
        raise FrozenInputError("frozen stream source paths must be unique")

    streams: list[StreamConsensusInput] = []
    scheduled_at: datetime | None = None
    for spec in spec_tuple:
        _validate_spec(spec)
        source_path = operation_root / spec.source_relative_path
        raw, value = _read_json_object(source_path, operation_root)
        _reject_forbidden_keys(value, source_path)
        stream, source_schedule = _stream_from_source(
            value,
            spec=spec,
            source_path=source_path,
            raw_source=raw,
            operation_root=operation_root,
        )
        if scheduled_at is None:
            scheduled_at = source_schedule
        elif source_schedule != scheduled_at:
            raise FrozenInputError("stream scheduled_at values disagree")
        streams.append(stream)

    ordered = tuple(sorted(streams, key=lambda stream: stream.strategy_id))
    if tuple(stream.strategy_id for stream in ordered) != tuple(
        sorted(spec.strategy_id for spec in spec_tuple)
    ):
        raise FrozenInputError("frozen stream identity set does not match the registry")
    if scheduled_at is None:
        raise FrozenInputError("no frozen streams were loaded")
    manifest = sha256_hex(canonical_bytes([stream.canonical_dict() for stream in ordered]))
    if expected_manifest_sha256 is not None and manifest != expected_manifest_sha256:
        raise FrozenInputError(
            f"stream input manifest mismatch: expected {expected_manifest_sha256}, got {manifest}"
        )
    if len(ordered) != EXPECTED_STREAM_COUNT:
        raise FrozenInputError("validated stream count is not eleven")
    return FrozenInputBundle(ordered, scheduled_at)


def resolve_implementation_identity(repo_root: Path) -> ImplementationIdentity:
    """Require a clean, exact HEAD for the scoped implementation sources."""

    _require_absolute_path(repo_root, "repo_root")
    discovered = Path(_git(repo_root, "rev-parse", "--show-toplevel").strip()).resolve()
    if discovered != repo_root.resolve():
        raise ImplementationIdentityError(
            f"repo_root is not the Git root: expected {repo_root}, found {discovered}"
        )
    rows: list[ImplementationSource] = []
    for relative_path in IMPLEMENTATION_SOURCE_PATHS:
        listed = _git(repo_root, "ls-files", "--error-unmatch", "--", relative_path).strip()
        if listed != relative_path:
            raise ImplementationIdentityError(
                f"implementation source is not tracked: {relative_path}"
            )
        status = _git(
            repo_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            relative_path,
        )
        if status.strip():
            raise ImplementationIdentityError(
                f"implementation source is dirty; commit it before materialization: {relative_path}"
            )
        path = repo_root / relative_path
        raw = _read_committed_source(path)
        committed = _git_bytes(repo_root, "show", f"HEAD:{relative_path}")
        if raw != committed:
            raise ImplementationIdentityError(
                f"working source differs from HEAD despite clean status: {relative_path}"
            )
        rows.append(ImplementationSource(relative_path, sha256_hex(raw)))
    commit = _git(repo_root, "rev-parse", "HEAD").strip()
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}").strip()
    if _GIT_OBJECT.fullmatch(commit) is None or _GIT_OBJECT.fullmatch(tree) is None:
        raise ImplementationIdentityError("Git returned a non-canonical commit or tree identity")
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
    """Validate, aggregate, and atomically create the canonical forecast.

    ``clock`` is sampled only after all source reads, hashes, validation, and
    aggregation.  A second sample is taken immediately before the atomic link
    call in :func:`publish_staged`; either closed boundary fails closed.
    """

    _require_absolute_path(operation_root, "operation_root")
    effective_repo = Path(__file__).resolve().parents[1] if repo_root is None else repo_root
    _require_absolute_path(effective_repo, "repo_root")
    output = (
        operation_root / FORECAST_RELATIVE_PATH if destination is None else destination
    )
    bundle = load_frozen_stream_inputs(
        operation_root,
        specs=specs,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    decision = build_canonical_consensus(bundle.streams)
    identity = (
        resolve_implementation_identity(effective_repo)
        if implementation_identity is None
        else implementation_identity
    )
    base = _base_payload(decision, bundle, identity)

    # Idempotent retries never sample the clock or stage a replacement.  The
    # existing bytes are independently checked against the immutable base and
    # its own original created_at window.
    existing = read_existing_bytes(output)
    if existing is not None:
        payload = _validate_existing_payload(existing, base, bundle)
        return MaterializationResult("ALREADY_PRESENT", output, payload)
    if dry_run:
        return MaterializationResult("DRY_RUN", output, base)

    now = _clock(clock)
    _require_creation_window(now, bundle, context="created_at")
    created_payload = {**base, "created_at": _format_timestamp(now)}
    payload_bytes = canonical_file_bytes(created_payload)

    # Directory creation and staging happen before the final clock sample;
    # neither operation can create the authority destination itself.
    ensure_output_parent(output)
    staged: StagedCanonicalForecast | None = None
    try:
        staged = stage_payload(output, payload_bytes)
        pre_publish_now = _clock(clock)
        if _as_utc(pre_publish_now) >= bundle.scheduled_at.astimezone(UTC):
            raise PreOutcomeWindowClosedError(
                "pre_publish_now must be strictly before scheduled_at"
            )
        # Keep this call directly adjacent to the second clock boundary.  The
        # writer's first operation is the atomic no-overwrite link.
        result = publish_staged(staged)
        if result.status == "CREATED":
            observed = read_existing_bytes(output)
            if observed != payload_bytes:
                raise ForecastAuthorityConflictError(
                    "read-after-write authority bytes differ from the staged payload"
                )
            return MaterializationResult("CREATED", output, created_payload)
        observed = read_existing_bytes(output)
        if observed is None:
            raise ForecastAuthorityConflictError(
                "atomic publication reported an existing authority that disappeared"
            )
        existing_payload = _validate_existing_payload(observed, base, bundle)
        return MaterializationResult("ALREADY_PRESENT", output, existing_payload)
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
    bundle: FrozenInputBundle,
    identity: ImplementationIdentity,
) -> dict[str, object]:
    # ``decision`` is kept as an object at this boundary so this helper remains
    # easy to audit: only the domain serializer supplies ranking and manifest
    # fields, while this module supplies authority and provenance metadata.
    decision_payload = decision.to_payload(task_id=TASK_ID, lottery_type=LOTTERY_TYPE)
    if decision_payload.get("stream_count") != EXPECTED_STREAM_COUNT:
        raise FrozenInputError("decision stream count is not eleven")
    if decision_payload.get("stream_input_manifest_sha256") is None:
        raise FrozenInputError("decision has no stream input manifest")
    source_rows = [
        {"path": source.path, "sha256": source.sha256}
        for source in sorted(identity.source_hashes, key=lambda item: item.path)
    ]
    if tuple(row["path"] for row in source_rows) != IMPLEMENTATION_SOURCE_PATHS:
        raise ImplementationIdentityError("implementation source hash scope is not exact")
    return {
        **decision_payload,
        "task_id": TASK_ID,
        "target_draw": {
            "draw_number": TARGET_DRAW_NUMBER,
            "draw_date": TARGET_DRAW_DATE,
        },
        "scheduled_at": TARGET_SCHEDULED_AT,
        "max_data_cutoff": {
            "draw_number": MAX_DATA_CUTOFF,
            "draw_date": MAX_DATA_CUTOFF_DATE,
        },
        "history_sha256": HISTORY_SHA256,
        "history_draw_count": HISTORY_DRAW_COUNT,
        "history_caveat": HISTORY_CAVEAT,
        "target_result_used": False,
        "aggregation_contract_review_id": AGGREGATION_CONTRACT_REVIEW_ID,
        "aggregation_contract_approved_at": AGGREGATION_CONTRACT_APPROVED_AT,
        "decision_ranking_formula": DECISION_RANKING_FORMULA,
        "implementation_commit": identity.commit,
        "implementation_tree": identity.tree,
        "implementation_source_hashes": source_rows,
        "pre_outcome_temporal_integrity": "PASS",
        "upstream_task_id": UPSTREAM_TASK_ID,
    }


def _validate_existing_payload(
    raw: bytes,
    base: Mapping[str, object],
    bundle: FrozenInputBundle,
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
    if "created_at" not in payload or type(payload["created_at"]) is not str:
        raise ForecastAuthorityConflictError("existing authority has no canonical created_at")
    created_at = _parse_timestamp(payload["created_at"], "existing.created_at")
    _require_creation_window(created_at, bundle, context="existing.created_at")
    if {key: value for key, value in payload.items() if key != "created_at"} != dict(base):
        raise ForecastAuthorityConflictError(
            "existing authority immutable fields differ from the committed forecast"
        )
    return payload


def _stream_from_source(
    value: Mapping[str, object],
    *,
    spec: FrozenStreamSpec,
    source_path: Path,
    raw_source: bytes,
    operation_root: Path,
) -> tuple[StreamConsensusInput, datetime]:
    _expect(value, "schema_version", "b649-operational-prediction-v1", source_path)
    _expect(value, "task_id", UPSTREAM_TASK_ID, source_path)
    _expect(value, "lottery_type", LOTTERY_TYPE, source_path)
    _expect(value, "draw_number", TARGET_DRAW_NUMBER, source_path)
    _expect(value, "draw_date", TARGET_DRAW_DATE, source_path)
    schedule_value = _required_text(value, "scheduled_at", source_path)
    if schedule_value != TARGET_SCHEDULED_AT:
        raise FrozenInputError(f"{source_path}: scheduled_at does not match target authority")
    schedule = _parse_timestamp(schedule_value, f"{source_path}.scheduled_at")
    _expect(value, "prediction_temporal_class", PRE_DRAW, source_path)
    _expect(value, "availability", "AVAILABLE", source_path)
    if value.get("unavailable_reason") is not None:
        raise FrozenInputError(f"{source_path}: AVAILABLE stream has an unavailable_reason")
    _expect(value, "history_draw_count", HISTORY_DRAW_COUNT, source_path)
    _expect(value, "history_sha256", HISTORY_SHA256, source_path)
    _expect(value, "history_caveat", HISTORY_CAVEAT, source_path)
    cutoff = value.get("history_cutoff")
    if cutoff != {"draw_number": MAX_DATA_CUTOFF, "draw_date": MAX_DATA_CUTOFF_DATE}:
        raise FrozenInputError(f"{source_path}: history_cutoff does not match the frozen cutoff")
    strategy_id = _required_text(value, "strategy_id", source_path)
    strategy_version = _required_text(value, "strategy_version", source_path)
    if strategy_id != spec.strategy_id or strategy_version != spec.strategy_version:
        raise FrozenInputError(f"{source_path}: strategy identity differs from the frozen registry")
    native_count = _required_int(value, "native_ticket_count", source_path)
    if native_count != spec.native_ticket_count:
        raise FrozenInputError(
            f"{source_path}: native_ticket_count differs from the frozen registry"
        )
    run_id = _required_text(value, "prediction_run_id", source_path)
    if run_id != source_path.stem:
        raise FrozenInputError(f"{source_path}: prediction_run_id does not match its filename")
    created_at = _parse_timestamp(
        _required_text(value, "prediction_created_at", source_path),
        f"{source_path}.prediction_created_at",
    )
    ticket_rows_value = value.get("tickets")
    if not isinstance(ticket_rows_value, list):
        raise FrozenInputError(
            f"{source_path}: ticket cardinality is not frozen native cardinality"
        )
    ticket_rows = cast(list[object], ticket_rows_value)
    if len(ticket_rows) != native_count:
        raise FrozenInputError(
            f"{source_path}: ticket cardinality is not frozen native cardinality"
        )
    tickets: list[tuple[int, ...]] = []
    for expected_position, raw_ticket in enumerate(ticket_rows, start=1):
        if not isinstance(raw_ticket, dict):
            raise FrozenInputError(f"{source_path}: ticket row is not an object")
        ticket_row = cast(Mapping[str, object], raw_ticket)
        if ticket_row.get("ticket_position") != expected_position:
            raise FrozenInputError(f"{source_path}: ticket positions are not contiguous")
        numbers_value = ticket_row.get("predicted_numbers")
        if not isinstance(numbers_value, list):
            raise FrozenInputError(f"{source_path}: ticket numbers are not six integers")
        numbers = cast(list[object], numbers_value)
        if len(numbers) != FINAL_TICKET_SIZE:
            raise FrozenInputError(f"{source_path}: ticket numbers are not six integers")
        if any(type(number) is not int for number in numbers):
            raise FrozenInputError(f"{source_path}: ticket numbers are not six integers")
        ticket = tuple(cast(list[int], numbers))
        if len(set(ticket)) != FINAL_TICKET_SIZE or any(
            number < 1 or number > 49 for number in ticket
        ):
            raise FrozenInputError(f"{source_path}: ticket contains duplicate or illegal numbers")
        tickets.append(ticket)
    relative = source_path.relative_to(operation_root).as_posix()
    if relative != spec.source_relative_path:
        raise FrozenInputError(f"{source_path}: source path is not the frozen relative path")
    return (
        StreamConsensusInput(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            native_ticket_count=native_count,
            prediction_run_id=run_id,
            source_relative_path=relative,
            source_sha256=sha256_hex(raw_source),
            prediction_created_at=created_at,
            tickets=tuple(tickets),
        ),
        schedule,
    )


def _require_creation_window(
    created_at: datetime,
    bundle: FrozenInputBundle,
    *,
    context: str,
) -> None:
    created_utc = _as_utc(created_at)
    scheduled_utc = _as_utc(bundle.scheduled_at)
    approved_utc = _as_utc(_parse_timestamp(AGGREGATION_CONTRACT_APPROVED_AT, "approval"))
    if any(_as_utc(stream.prediction_created_at) > created_utc for stream in bundle.streams):
        raise PreOutcomeWindowClosedError(f"{context} is earlier than a prediction_created_at")
    if approved_utc > created_utc:
        raise PreOutcomeWindowClosedError(
            f"{context} is earlier than aggregation_contract_approved_at"
        )
    if created_utc >= scheduled_utc:
        raise PreOutcomeWindowClosedError(f"{context} must be strictly before scheduled_at")


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


def _require_absolute_path(value: Path, label: str) -> None:
    if not value.is_absolute():
        raise ForecastMaterializationError(f"{label} must be an absolute Path")


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
            "stream_input_manifest_sha256": result.payload.get(
                "stream_input_manifest_sha256"
            ),
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
    except ForecastMaterializationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AGGREGATION_UNIT",
    "CANONICAL_CONSENSUS_METHOD_ID",
    "CANONICAL_CONSENSUS_METHOD_VERSION",
    "CANONICAL_CONSENSUS_SCHEMA_VERSION",
    "CORRELATED_FAMILY_POLICY",
    "DECISION_RANKING_FORMULA",
    "EXPECTED_STREAM_INPUT_MANIFEST_SHA256",
    "FORECAST_RELATIVE_PATH",
    "FROZEN_STREAM_SPECS",
    "IMPLEMENTATION_SOURCE_PATHS",
    "LOTTERY_TYPE",
    "OPERATION_ROOT",
    "TASK_ID",
    "UPSTREAM_TASK_ID",
    "ForecastAuthorityConflictError",
    "ForecastMaterializationError",
    "FrozenInputBundle",
    "FrozenInputError",
    "FrozenStreamSpec",
    "ImplementationIdentity",
    "ImplementationIdentityError",
    "ImplementationSource",
    "MaterializationResult",
    "PreOutcomeWindowClosedError",
    "load_frozen_stream_inputs",
    "materialize_canonical_forecast",
    "resolve_implementation_identity",
]
