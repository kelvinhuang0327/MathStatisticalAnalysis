"""Immutable consensus candidate admission authority for LottoLab B649.

Under the V5 target-parameterized canonical promotion contract, candidate
admission is a dedicated, immutable step before promotion. The authority
validates the pre-draw publication payload and its 11 source streams against
canonical schedule authority and outcome absence, then writes an immutable row
into ``research_consensus_candidate_authorities``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from lottolab.application.pre_outcome_target_operational import (
    OutcomePresenceEvidenceUnavailableError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    OutcomePresenceAtPrediction,
)
from lottolab.domain.research_live_forecast import (
    CANONICAL_CONSENSUS,
    CONSENSUS_MISSING,
    CONSENSUS_STREAM,
    CONSENSUS_STREAM_SPECS,
    CONSENSUS_STREAM_VERSION,
    ORIGINAL_FIELDS,
    SUCCESSOR_CONSENSUS_PROVENANCE_SCHEMA_VERSION,
    LiveForecastInput,
    canonical_json,
    digest,
    utc_text,
    validate_successor_consensus_payload,
)
from lottolab.infrastructure.b649_consensus_promotion import (
    PromotionRequest,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV as DRAW_DATA_DIRECTORY_ENV,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.draw_schema import (
    open_database as open_draw_database,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    DATA_DIRECTORY_ENV,
    ResearchDataPaths,
    resolve_research_data_paths,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    SQLiteOfficialOutcomePresenceProbe,
)


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must be a lowercase 64-character hex string")
    return value


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _as_utc(value: datetime) -> datetime:
    _require_aware(value, "datetime")
    return value.astimezone(UTC)


DEFAULT_PUBLICATION_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1"
)


class ConsensusCandidateAuthorityError(ValueError):
    """Base error for candidate admission authority failures."""


class ConsensusCandidateAdmissionError(ConsensusCandidateAuthorityError):
    """The candidate fails admission requirements or pre-conditions."""


class ConsensusCandidateConflictError(ConsensusCandidateAuthorityError):
    """A conflicting candidate has already been admitted for this target."""


class ConsensusCandidateNotFoundError(ConsensusCandidateAuthorityError):
    """The specified candidate_ref was not found in the admission store."""


@dataclass(frozen=True, slots=True)
class AdmittedConsensusCandidate:
    """Immutable view of an admitted candidate record from the research store."""

    candidate_ref: str
    lottery_type: str
    target_draw_number: str
    target_draw_date: str
    forecast_stream_id: str
    forecast_stream_version: str
    payload_bytes: bytes
    payload_sha256: str
    candidate_locator: Path
    candidate_created_at: str
    scheduled_at: str
    deadline: str
    data_cutoff_draw_number: str
    data_cutoff_draw_date: str
    history_draw_count: int
    causal_history_sha256: str
    schedule_authority_sha256: str
    stream_input_manifest_sha256: str
    implementation_commit: str
    implementation_tree: str
    implementation_source_hashes: list[dict[str, str]]
    streams: list[dict[str, object]]
    admission_provenance: dict[str, object]
    admitted_at: str
    payload: dict[str, object]

    @property
    def scope(self) -> tuple[str, str, str, str, str]:
        return (
            self.lottery_type,
            self.target_draw_number,
            self.target_draw_date,
            self.forecast_stream_id,
            self.forecast_stream_version,
        )

    @property
    def target(self) -> dict[str, object]:
        return {
            "lottery_type": self.lottery_type,
            "target_draw_number": self.target_draw_number,
            "target_draw_date": self.target_draw_date,
            "scheduled_at": self.scheduled_at,
            "timezone": "Asia/Taipei",
            "data_cutoff": self.data_cutoff_draw_number,
            "forecast_horizon": 1,
            "history_draw_count": self.history_draw_count,
            "causal_history_sha256": self.causal_history_sha256,
            "schedule_authority_sha256": self.schedule_authority_sha256,
        }

    def build_consensus_provenance(self, *, schedule_authority_sha256: str | None = None) -> str:
        selected_schedule_hash = (
            self.schedule_authority_sha256
            if schedule_authority_sha256 is None
            else schedule_authority_sha256
        )
        _require_sha(selected_schedule_hash, "schedule_authority_sha256")
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
            "lottery_type": self.lottery_type,
            "draw_number": self.target_draw_number,
            "draw_date": self.target_draw_date,
            "scheduled_at": self.scheduled_at,
            "timezone": "Asia/Taipei",
            "cutoff": self.data_cutoff_draw_number,
            "history_draw_count": self.history_draw_count,
            "causal_history_sha256": self.causal_history_sha256,
            "temporal_class": "PRE_DRAW",
            "target_result_used": False,
            "schedule_authority_sha256": selected_schedule_hash,
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
                    "candidate_ref": self.candidate_ref,
                    "locator": str(self.candidate_locator),
                    "sha256": self.payload_sha256,
                },
                "contract_version": SUCCESSOR_CONSENSUS_PROVENANCE_SCHEMA_VERSION,
                "final_decision_ranking": self.payload["final_decision_ranking"],
                "final_recommended_output": self.payload["final_recommended_output"],
                "generated_at": self.payload["created_at"],
                "implementation": implementation,
                "production": production,
                "source_provenance": {
                    "locator": str(self.candidate_locator),
                    "sha256": self.payload_sha256,
                    "document": production,
                },
                "strategy_reexecution": "NO",
                "streams": self.streams,
                "target": target,
            }
        )

    def build_forecast(
        self,
        request: PromotionRequest,
        *,
        schedule_authority_sha256: str | None = None,
    ) -> LiveForecastInput:
        selected_schedule_hash = request.schedule_authority_sha256
        if schedule_authority_sha256 is not None:
            _require_sha(schedule_authority_sha256, "schedule_authority_sha256")
            if schedule_authority_sha256 != selected_schedule_hash:
                raise ValueError("schedule authority hash differs from the promotion request")
        if selected_schedule_hash != self.schedule_authority_sha256:
            raise ValueError(
                "promotion request schedule authority hash does not match admitted candidate"
            )
        target = self.target
        forecast = LiveForecastInput(
            request_id=request.request_id,
            request_sha256=request.request_sha256,
            provenance_class=CANONICAL_CONSENSUS,
            forecast_stream_id=self.forecast_stream_id,
            forecast_stream_version=self.forecast_stream_version,
            target_json=canonical_json(target),
            payload_bytes=self.payload_bytes,
            source_locator=str(self.candidate_locator),
            original_execution_json=canonical_json(dict.fromkeys(ORIGINAL_FIELDS)),
            missing_provenance_json=canonical_json(CONSENSUS_MISSING),
            import_execution_json=request.import_execution_json(candidate_ref=self.candidate_ref),
            consensus_provenance_json=self.build_consensus_provenance(
                schedule_authority_sha256=selected_schedule_hash
            ),
            candidate_ref=self.candidate_ref,
        )
        forecast.validate()
        return forecast


def _to_research_paths(paths: ResearchDataPaths | Path | str) -> ResearchDataPaths:
    if isinstance(paths, ResearchDataPaths):
        return paths
    p = Path(paths)
    if p.is_dir():
        return resolve_research_data_paths(environ={DATA_DIRECTORY_ENV: str(p)})
    return ResearchDataPaths(p.parent, p)


def _to_draw_paths(paths: LocalDataPaths | Path | str | None) -> LocalDataPaths:
    if paths is None:
        return resolve_local_data_paths()
    if isinstance(paths, LocalDataPaths):
        return paths
    p = Path(paths)
    if p.is_dir():
        return resolve_local_data_paths(environ={DRAW_DATA_DIRECTORY_ENV: str(p)})
    return LocalDataPaths(p.parent, p)


def admit_consensus_candidate(
    *,
    research_paths: ResearchDataPaths | Path | str,
    target_draw_number: str,
    draw_paths: LocalDataPaths | Path | str | None = None,
    publication_root: Path | str | None = None,
    expected_payload_sha256: str | None = None,
    now: datetime | None = None,
    admitter_identity: str = "consensus-admission-authority",
    notes: str | None = None,
) -> AdmittedConsensusCandidate:
    """Admit a candidate into the research store authority table."""

    target_draw_str = str(target_draw_number).strip()
    if not target_draw_str:
        raise ConsensusCandidateAdmissionError("target_draw_number must be non-empty")
    if target_draw_str == "115000087":
        raise ConsensusCandidateAdmissionError(
            "target 115000087 is frozen under V4 contract and "
            "cannot be admitted to V5 candidate authority"
        )

    checked_at = datetime.now(UTC) if now is None else now
    _require_aware(checked_at, "now")
    checked_at = _as_utc(checked_at)

    resolved_draw_paths = _to_draw_paths(draw_paths)
    resolved_research_paths = _to_research_paths(research_paths)

    # 1. Schedule authority lookup
    reader = SQLiteFutureDrawIdentityReader(resolved_draw_paths, require_active_authority=True)
    try:
        record = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, target_draw_str)
    except Exception as exc:
        raise ConsensusCandidateAdmissionError(
            f"failed to read schedule for BIG_LOTTO {target_draw_str}"
        ) from exc
    if record is None:
        raise ConsensusCandidateAdmissionError(
            f"no scheduled draw identity for BIG_LOTTO {target_draw_str}"
        )
    announcement = record.announcement
    if (
        announcement.target.lottery_type != LotteryType.BIG_LOTTO
        or announcement.target.draw_number != target_draw_str
    ):
        raise ConsensusCandidateAdmissionError("scheduled draw target mismatch")
    schedule_hash = record.immutable_schedule_sha256
    if schedule_hash is None:
        raise ConsensusCandidateAdmissionError("scheduled draw has no immutable schedule hash")
    _require_sha(schedule_hash, "schedule_authority_sha256")

    # 2. Outcome presence probe
    with open_draw_database(resolved_draw_paths, read_only=True) as conn:
        draw_row = conn.execute(
            "SELECT draw_number FROM draws WHERE lottery_type = ? AND draw_number = ?",
            (LotteryType.BIG_LOTTO.value, target_draw_str),
        ).fetchone()
        if draw_row is not None:
            raise ConsensusCandidateAdmissionError(
                f"official outcome is already present for {target_draw_str}"
            )

    probe = SQLiteOfficialOutcomePresenceProbe(resolved_draw_paths)
    try:
        attestation = probe.probe(announcement.target, as_of=checked_at)
        presence = getattr(attestation, "presence", None)
        presence_value = getattr(presence, "value", presence)
        if presence_value != OutcomePresenceAtPrediction.ABSENT.value:
            raise ConsensusCandidateAdmissionError(
                f"official outcome presence is {presence_value}, expected ABSENT"
            )
    except OutcomePresenceEvidenceUnavailableError:
        pass
    except Exception as exc:
        if isinstance(exc, ConsensusCandidateAdmissionError):
            raise
        raise ConsensusCandidateAdmissionError(
            f"failed to probe outcome presence for {target_draw_str}"
        ) from exc

    # 3. Temporal deadline check (strict inequality: checked_at < deadline)
    deadline = _as_utc(announcement.scheduled_at)
    if checked_at >= deadline:
        raise ConsensusCandidateAdmissionError(
            f"admission deadline reached or passed: "
            f"checked_at={checked_at.isoformat()} >= deadline={deadline.isoformat()}"
        )

    # 4. Publication store locator
    raw_pub_root = (
        Path(publication_root)
        if publication_root is not None
        else DEFAULT_PUBLICATION_ROOT
    )
    if not raw_pub_root.exists():
        raise ConsensusCandidateAdmissionError(
            f"publication_root does not exist: {raw_pub_root}"
        )
    pub_root = raw_pub_root.resolve()

    # Symlink security checks
    forecasts_dir = pub_root / "forecasts"
    if forecasts_dir.exists():
        for p in forecasts_dir.rglob("*"):
            if p.is_symlink():
                raise ConsensusCandidateAdmissionError(
                    f"symlink detected in publication store: {p}"
                )
    predictions_dir = pub_root / "predictions"
    if predictions_dir.exists():
        for p in predictions_dir.rglob("*"):
            if p.is_symlink():
                raise ConsensusCandidateAdmissionError(
                    f"symlink detected in publication store: {p}"
                )

    candidate_relpath = Path(
        f"forecasts/{target_draw_str}/B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS/1.0.0/final_forecast_payload.json"
    )
    candidate_locator = pub_root / candidate_relpath
    if not candidate_locator.exists():
        raise ConsensusCandidateAdmissionError(
            f"candidate payload not found at {candidate_locator}"
        )
    if candidate_locator.is_symlink():
        raise ConsensusCandidateAdmissionError(
            f"candidate locator must not be a symlink: {candidate_locator}"
        )

    payload_bytes = candidate_locator.read_bytes()
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise ConsensusCandidateAdmissionError("candidate payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ConsensusCandidateAdmissionError("candidate payload must be a JSON object")
    payload = cast(dict[str, object], payload)

    payload_scheduled_at_raw = payload.get("scheduled_at")
    if not isinstance(payload_scheduled_at_raw, str):
        raise ConsensusCandidateAdmissionError("candidate payload scheduled_at must be a string")
    try:
        payload_scheduled_at = datetime.fromisoformat(payload_scheduled_at_raw)
    except ValueError as exc:
        raise ConsensusCandidateAdmissionError(
            "candidate payload scheduled_at is invalid ISO"
        ) from exc
    if _as_utc(payload_scheduled_at) != _as_utc(announcement.scheduled_at):
        raise ConsensusCandidateAdmissionError(
            f"candidate payload scheduled_at {payload_scheduled_at_raw} does not match "
            f"canonical schedule authority {announcement.scheduled_at.isoformat()}"
        )

    # 5. Payload semantic and lineage validation
    # Verify stream input files exist in pub_root and match hashes
    stream_inputs_raw = payload.get("stream_inputs")
    if not isinstance(stream_inputs_raw, list):
        raise ConsensusCandidateAdmissionError("candidate payload must contain stream_inputs list")
    stream_inputs = cast(list[object], stream_inputs_raw)
    if len(stream_inputs) != len(CONSENSUS_STREAM_SPECS):
        raise ConsensusCandidateAdmissionError("candidate payload must contain exactly 11 streams")

    expected_stream_specs = {spec[0]: spec for spec in CONSENSUS_STREAM_SPECS}
    validated_streams: list[dict[str, object]] = []
    for idx, s in enumerate(stream_inputs):
        if not isinstance(s, dict):
            raise ConsensusCandidateAdmissionError(f"stream_inputs[{idx}] must be an object")
        s_dict = cast(dict[str, object], s)
        strategy_id = str(s_dict.get("strategy_id", ""))
        rel_path = str(s_dict.get("source_relative_path", ""))
        if not rel_path or rel_path.startswith("/") or ".." in rel_path:
            raise ConsensusCandidateAdmissionError(
                f"stream_inputs[{idx}] unsafe relative path: {rel_path}"
            )
        stream_file = pub_root / rel_path
        if not stream_file.exists():
            raise ConsensusCandidateAdmissionError(
                f"stream input file missing from publication store: {stream_file}"
            )
        stream_bytes = stream_file.read_bytes()
        actual_stream_sha = hashlib.sha256(stream_bytes).hexdigest()
        if actual_stream_sha != s_dict.get("source_sha256"):
            raise ConsensusCandidateAdmissionError(
                f"stream input file SHA256 mismatch for {strategy_id}: "
                f"{actual_stream_sha} != {s_dict.get('source_sha256')}"
            )
        if strategy_id not in expected_stream_specs:
            raise ConsensusCandidateAdmissionError(f"unknown stream strategy_id: {strategy_id}")
        spec = expected_stream_specs[strategy_id]
        if s_dict.get("native_ticket_count") != spec[2]:
            raise ConsensusCandidateAdmissionError(
                f"stream {strategy_id} ticket count mismatch: "
                f"{s_dict.get('native_ticket_count')} != {spec[2]}"
            )
        validated_streams.append(s_dict)

    if expected_payload_sha256 is not None:
        _require_sha(expected_payload_sha256, "expected_payload_sha256")
        if payload_sha256 != expected_payload_sha256:
            raise ConsensusCandidateAdmissionError(
                f"candidate payload SHA256 mismatch: {payload_sha256} != {expected_payload_sha256}"
            )

    if payload.get("stream_input_manifest_sha256") != digest(validated_streams):
        raise ConsensusCandidateAdmissionError("stream input manifest SHA256 mismatch")

    # Domain payload validation
    target_dict: dict[str, object] = {
        "lottery_type": "BIG_LOTTO",
        "target_draw_number": target_draw_str,
        "target_draw_date": announcement.target.draw_date.isoformat(),
        "scheduled_at": payload_scheduled_at_raw,
        "timezone": "Asia/Taipei",
        "data_cutoff": str(
            cast(dict[str, object], payload.get("max_data_cutoff", {})).get("draw_number", "")
        ),
        "forecast_horizon": 1,
        "history_draw_count": int(cast(int, payload.get("history_draw_count", 0))),
        "causal_history_sha256": str(payload.get("history_sha256", "")),
        "schedule_authority_sha256": schedule_hash,
    }
    try:
        validate_successor_consensus_payload(payload, target_dict)
    except ValueError as exc:
        raise ConsensusCandidateAdmissionError(f"invalid candidate payload: {exc}") from exc

    # 6. Candidate ref derivation
    candidate_ref = f"cand-consensus-b649-{target_draw_str}-{payload_sha256[:16]}"

    # 7. Persistence into research_consensus_candidate_authorities
    now_str = utc_text(checked_at)
    admission_provenance = {
        "admitted_at": now_str,
        "admitter_identity": admitter_identity,
        "publication_root": str(pub_root),
        "schedule_record_id": record.internal_id,
    }
    if notes is not None:
        admission_provenance["notes"] = str(notes)

    # INTENT: Delegate storage of admitted consensus candidate to SQLiteResearchRepository
    repository = SQLiteResearchRepository(resolved_research_paths)
    try:
        repository.persist_consensus_candidate_authority(
            candidate_ref=candidate_ref,
            lottery_type="BIG_LOTTO",
            target_draw_number=target_draw_str,
            target_draw_date=announcement.target.draw_date.isoformat(),
            forecast_stream_id=CONSENSUS_STREAM,
            forecast_stream_version=CONSENSUS_STREAM_VERSION,
            payload_bytes=payload_bytes,
            payload_sha256=payload_sha256,
            candidate_locator=str(candidate_locator),
            candidate_created_at=str(payload.get("created_at", "")),
            scheduled_at=payload_scheduled_at_raw,
            deadline=payload_scheduled_at_raw,
            data_cutoff_draw_number=str(
                cast(dict[str, object], payload["max_data_cutoff"])["draw_number"]
            ),
            data_cutoff_draw_date=str(
                cast(dict[str, object], payload["max_data_cutoff"])["draw_date"]
            ),
            history_draw_count=int(cast(int, payload["history_draw_count"])),
            causal_history_sha256=str(payload["history_sha256"]),
            schedule_authority_sha256=schedule_hash,
            stream_input_manifest_sha256=str(payload["stream_input_manifest_sha256"]),
            implementation_commit=str(payload["implementation_commit"]),
            implementation_tree=str(payload["implementation_tree"]),
            implementation_source_hashes_json=canonical_json(
                payload["implementation_source_hashes"]
            ),
            streams_json=canonical_json(payload["stream_inputs"]),
            admission_provenance_json=canonical_json(admission_provenance),
            admitted_at=now_str,
        )
    except ResearchConflictError as exc:
        raise ConsensusCandidateConflictError(str(exc)) from exc

    return load_admitted_candidate(resolved_research_paths, candidate_ref)


def load_admitted_candidate(
    research_paths: ResearchDataPaths | Path | str,
    candidate_ref: str,
) -> AdmittedConsensusCandidate:
    """Load an admitted candidate record from the research database."""

    # INTENT: Delegate retrieval of admitted consensus candidate to SQLiteResearchRepository
    resolved_paths = _to_research_paths(research_paths)
    repository = SQLiteResearchRepository(resolved_paths)
    rec = repository.get_consensus_candidate_authority(candidate_ref)
    if rec is None:
        raise ConsensusCandidateNotFoundError(
            f"admitted candidate not found for ref: {candidate_ref}"
        )

    payload_bytes = cast(bytes, rec["payload_bytes"])
    payload = cast(dict[str, object], json.loads(payload_bytes))
    source_hashes = cast(
        list[dict[str, str]], json.loads(str(rec["implementation_source_hashes_json"]))
    )
    streams = cast(list[dict[str, object]], json.loads(str(rec["streams_json"])))
    admission_provenance = cast(
        dict[str, object], json.loads(str(rec["admission_provenance_json"]))
    )

    return AdmittedConsensusCandidate(
        candidate_ref=str(rec["candidate_ref"]),
        lottery_type=str(rec["lottery_type"]),
        target_draw_number=str(rec["target_draw_number"]),
        target_draw_date=str(rec["target_draw_date"]),
        forecast_stream_id=str(rec["forecast_stream_id"]),
        forecast_stream_version=str(rec["forecast_stream_version"]),
        payload_bytes=payload_bytes,
        payload_sha256=str(rec["payload_sha256"]),
        candidate_locator=Path(str(rec["candidate_locator"])),
        candidate_created_at=str(rec["candidate_created_at"]),
        scheduled_at=str(rec["scheduled_at"]),
        deadline=str(rec["deadline"]),
        data_cutoff_draw_number=str(rec["data_cutoff_draw_number"]),
        data_cutoff_draw_date=str(rec["data_cutoff_draw_date"]),
        history_draw_count=int(cast(int, rec["history_draw_count"])),
        causal_history_sha256=str(rec["causal_history_sha256"]),
        schedule_authority_sha256=str(rec["schedule_authority_sha256"]),
        stream_input_manifest_sha256=str(rec["stream_input_manifest_sha256"]),
        implementation_commit=str(rec["implementation_commit"]),
        implementation_tree=str(rec["implementation_tree"]),
        implementation_source_hashes=source_hashes,
        streams=streams,
        admission_provenance=admission_provenance,
        admitted_at=str(rec["admitted_at"]),
        payload=payload,
    )


__all__ = [
    "DEFAULT_PUBLICATION_ROOT",
    "AdmittedConsensusCandidate",
    "ConsensusCandidateAdmissionError",
    "ConsensusCandidateAuthorityError",
    "ConsensusCandidateConflictError",
    "ConsensusCandidateNotFoundError",
    "admit_consensus_candidate",
    "load_admitted_candidate",
]
