"""Canonical LCJ-1 artifact for deterministic Replay prize-scoring evidence."""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BigLottoPrizeTierId, NoPrizeResult
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayPrizeAggregation,
    ReplayScoredPrediction,
    ReplayScoringReason,
    ReplayScoringStatus,
    ReplayScoringStrategyIdentity,
    recompute_aggregation_sha256,
    recompute_scored_result_sha256,
    replay_prize_aggregation_canonical_dict,
    replay_scored_prediction_canonical_dict,
)
from lottolab.evidence.canonical_json import (
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
)
from lottolab.evidence.replay_artifact import ReplayArtifact

SCORING_ARTIFACT_SCHEMA_VERSION = "1.0.0"
_PLACEHOLDER_SHA256 = "0" * 64


class ReplayScoringArtifactTamperError(ValueError):
    """A top-level or nested scoring hash does not match its content."""


class ReplayScoringArtifactShapeError(ValueError):
    """Serialized scoring bytes do not match the closed artifact shape."""


@dataclasses.dataclass(frozen=True, slots=True)
class ReplayScoringArtifact:
    artifact_schema_version: str
    source_replay_artifact_payload_sha256: str
    dataset_id: str
    dataset_version: str
    lottery_type: LotteryType
    target_identities: tuple[ReplayTarget, ...]
    strategy_identities: tuple[ReplayScoringStrategyIdentity, ...]
    scored_predictions: tuple[ReplayScoredPrediction, ...]
    strategy_aggregates: tuple[ReplayPrizeAggregation, ...]
    overall_aggregate: ReplayPrizeAggregation
    scored_record_count: int
    payload_sha256: str

    def __post_init__(self) -> None:
        if self.artifact_schema_version != SCORING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported scoring artifact schema version")
        if not self.dataset_id or not self.dataset_version:
            raise ValueError("dataset identity/version must not be empty")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("Replay prize scoring currently supports BIG_LOTTO only")
        if not self.target_identities or not self.strategy_identities:
            raise ValueError("target and strategy identities must not be empty")
        if len({target.draw_number for target in self.target_identities}) != len(
            self.target_identities
        ):
            raise ValueError("target identities must not contain duplicate draw numbers")
        strategy_ids = tuple(identity.strategy_id for identity in self.strategy_identities)
        if len(set(strategy_ids)) != len(strategy_ids):
            raise ValueError("strategy identities must not contain duplicates")
        if self.scored_record_count != len(self.scored_predictions):
            raise ValueError("scored_record_count must equal len(scored_predictions)")
        if self.scored_record_count != len(self.target_identities) * len(
            self.strategy_identities
        ):
            raise ValueError("scored record count must equal targets times strategies")

        expected_pairs = tuple(
            (target, identity)
            for target in self.target_identities
            for identity in self.strategy_identities
        )
        for record, (target, identity) in zip(
            self.scored_predictions,
            expected_pairs,
            strict=True,
        ):
            if (
                record.source_replay_artifact_payload_sha256
                != self.source_replay_artifact_payload_sha256
                or record.dataset_id != self.dataset_id
                or record.dataset_version != self.dataset_version
                or record.lottery_type is not self.lottery_type
                or record.target_draw_number != target.draw_number
                or record.target_draw_date != target.draw_date
                or record.strategy_id != identity.strategy_id
                or record.strategy_version != identity.strategy_version
            ):
                raise ValueError("scored prediction identity/order mismatch")
            if recompute_scored_result_sha256(record) != record.scored_result_sha256:
                raise ReplayScoringArtifactTamperError("nested scored-result hash mismatch")

        if len(self.strategy_aggregates) != len(self.strategy_identities):
            raise ValueError("one strategy aggregate is required per strategy identity")
        for identity, aggregation in zip(
            self.strategy_identities,
            self.strategy_aggregates,
            strict=True,
        ):
            strategy_records = tuple(
                record
                for record in self.scored_predictions
                if record.strategy_id == identity.strategy_id
            )
            expected = ReplayPrizeAggregation.from_records(
                strategy_records,
                strategy_id=identity.strategy_id,
                strategy_version=identity.strategy_version,
            )
            if aggregation != expected:
                raise ValueError("strategy aggregation does not match scored records")
            if recompute_aggregation_sha256(aggregation) != aggregation.aggregation_sha256:
                raise ReplayScoringArtifactTamperError("strategy aggregation hash mismatch")
        expected_overall = ReplayPrizeAggregation.from_records(self.scored_predictions)
        if self.overall_aggregate != expected_overall:
            raise ValueError("overall aggregation does not match scored records")
        if (
            recompute_aggregation_sha256(self.overall_aggregate)
            != self.overall_aggregate.aggregation_sha256
        ):
            raise ReplayScoringArtifactTamperError("overall aggregation hash mismatch")
        if recompute_scoring_artifact_payload_sha256(self) != self.payload_sha256:
            raise ReplayScoringArtifactTamperError("scoring artifact payload hash mismatch")


def _artifact_content_dict(
    *,
    artifact_schema_version: str,
    source_replay_artifact_payload_sha256: str,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    target_identities: tuple[ReplayTarget, ...],
    strategy_identities: tuple[ReplayScoringStrategyIdentity, ...],
    scored_predictions: tuple[ReplayScoredPrediction, ...],
    strategy_aggregates: tuple[ReplayPrizeAggregation, ...],
    overall_aggregate: ReplayPrizeAggregation,
    scored_record_count: int,
    payload_sha256: str,
) -> dict[str, Any]:
    strategy_payloads: list[dict[str, Any]] = []
    for identity in strategy_identities:
        payload: dict[str, Any] = {"strategy_id": identity.strategy_id}
        if identity.strategy_version is not None:
            payload["strategy_version"] = identity.strategy_version
        strategy_payloads.append(payload)
    return {
        "artifact_schema_version": artifact_schema_version,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "lottery_type": lottery_type.value,
        "overall_aggregate": replay_prize_aggregation_canonical_dict(overall_aggregate),
        "payload_sha256": payload_sha256,
        "scored_predictions": [
            replay_scored_prediction_canonical_dict(record) for record in scored_predictions
        ],
        "scored_record_count": scored_record_count,
        "source_replay_artifact_payload_sha256": source_replay_artifact_payload_sha256,
        "strategy_aggregates": [
            replay_prize_aggregation_canonical_dict(aggregation)
            for aggregation in strategy_aggregates
        ],
        "strategy_identities": strategy_payloads,
        "target_identities": [
            {
                "target_draw_date": target.draw_date.isoformat(),
                "target_draw_number": target.draw_number,
            }
            for target in target_identities
        ],
    }


def build_replay_scoring_artifact(
    *,
    source_artifact: ReplayArtifact,
    scored_predictions: tuple[ReplayScoredPrediction, ...],
    strategy_aggregates: tuple[ReplayPrizeAggregation, ...],
    overall_aggregate: ReplayPrizeAggregation,
) -> ReplayScoringArtifact:
    versions_by_strategy: dict[str, str | None] = {}
    for strategy_id in source_artifact.strategy_ids:
        versions = {
            record.strategy_version
            for record in scored_predictions
            if record.strategy_id == strategy_id
        }
        if len(versions) != 1:
            raise ValueError("scored records contain inconsistent strategy versions")
        versions_by_strategy[strategy_id] = versions.pop()
    strategy_identities = tuple(
        ReplayScoringStrategyIdentity(strategy_id, versions_by_strategy[strategy_id])
        for strategy_id in source_artifact.strategy_ids
    )
    values: dict[str, Any] = {
        "artifact_schema_version": SCORING_ARTIFACT_SCHEMA_VERSION,
        "source_replay_artifact_payload_sha256": source_artifact.payload_sha256,
        "dataset_id": source_artifact.dataset_id,
        "dataset_version": source_artifact.dataset_version,
        "lottery_type": source_artifact.lottery_type,
        "target_identities": source_artifact.targets,
        "strategy_identities": strategy_identities,
        "scored_predictions": scored_predictions,
        "strategy_aggregates": strategy_aggregates,
        "overall_aggregate": overall_aggregate,
        "scored_record_count": len(scored_predictions),
    }
    content = _artifact_content_dict(**values, payload_sha256=_PLACEHOLDER_SHA256)
    return ReplayScoringArtifact(
        **values,
        payload_sha256=self_key_removed_sha256(content, "payload_sha256"),
    )


def recompute_scoring_artifact_payload_sha256(artifact: ReplayScoringArtifact) -> str:
    values = {field.name: getattr(artifact, field.name) for field in dataclasses.fields(artifact)}
    return self_key_removed_sha256(_artifact_content_dict(**values), "payload_sha256")


def serialize_replay_scoring_artifact(artifact: ReplayScoringArtifact) -> bytes:
    if recompute_scoring_artifact_payload_sha256(artifact) != artifact.payload_sha256:
        raise ReplayScoringArtifactTamperError("scoring artifact payload hash mismatch")
    return canonical_bytes(
        _artifact_content_dict(
            **{
                field.name: getattr(artifact, field.name)
                for field in dataclasses.fields(artifact)
            }
        )
    )


def deserialize_replay_scoring_artifact(data: bytes) -> ReplayScoringArtifact:
    raw = loads_canonical(data)
    if not isinstance(raw, dict):
        raise ReplayScoringArtifactShapeError("scoring artifact must be a JSON object")
    parsed = cast("dict[str, Any]", raw)
    _require_keys(
        parsed,
        {
            "artifact_schema_version",
            "source_replay_artifact_payload_sha256",
            "dataset_id",
            "dataset_version",
            "lottery_type",
            "target_identities",
            "strategy_identities",
            "scored_predictions",
            "strategy_aggregates",
            "overall_aggregate",
            "scored_record_count",
            "payload_sha256",
        },
    )
    declared_sha256 = cast(str, parsed["payload_sha256"])
    if self_key_removed_sha256(parsed, "payload_sha256") != declared_sha256:
        raise ReplayScoringArtifactTamperError("scoring artifact payload hash mismatch")
    try:
        targets = tuple(
            _target_from_dict(cast("dict[str, Any]", entry))
            for entry in cast("list[object]", parsed["target_identities"])
        )
        identities = tuple(
            _strategy_identity_from_dict(cast("dict[str, Any]", entry))
            for entry in cast("list[object]", parsed["strategy_identities"])
        )
        records = tuple(
            _scored_prediction_from_dict(cast("dict[str, Any]", entry))
            for entry in cast("list[object]", parsed["scored_predictions"])
        )
        strategy_aggregates = tuple(
            _aggregation_from_dict(cast("dict[str, Any]", entry))
            for entry in cast("list[object]", parsed["strategy_aggregates"])
        )
        overall = _aggregation_from_dict(
            cast("dict[str, Any]", parsed["overall_aggregate"])
        )
        return ReplayScoringArtifact(
            artifact_schema_version=cast(str, parsed["artifact_schema_version"]),
            source_replay_artifact_payload_sha256=cast(
                str, parsed["source_replay_artifact_payload_sha256"]
            ),
            dataset_id=cast(str, parsed["dataset_id"]),
            dataset_version=cast(str, parsed["dataset_version"]),
            lottery_type=LotteryType(parsed["lottery_type"]),
            target_identities=targets,
            strategy_identities=identities,
            scored_predictions=records,
            strategy_aggregates=strategy_aggregates,
            overall_aggregate=overall,
            scored_record_count=cast(int, parsed["scored_record_count"]),
            payload_sha256=declared_sha256,
        )
    except ReplayScoringArtifactTamperError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        message = str(exc)
        if "sha256" in message or "aggregation does not match" in message:
            raise ReplayScoringArtifactTamperError(message) from exc
        raise ReplayScoringArtifactShapeError(message) from exc


def _target_from_dict(payload: dict[str, Any]) -> ReplayTarget:
    _require_keys(payload, {"target_draw_number", "target_draw_date"})
    return ReplayTarget(
        draw_number=payload["target_draw_number"],
        draw_date=date.fromisoformat(payload["target_draw_date"]),
    )


def _strategy_identity_from_dict(payload: dict[str, Any]) -> ReplayScoringStrategyIdentity:
    _require_keys(payload, {"strategy_id"}, {"strategy_version"})
    return ReplayScoringStrategyIdentity(
        strategy_id=payload["strategy_id"],
        strategy_version=payload.get("strategy_version"),
    )


def _scored_prediction_from_dict(payload: dict[str, Any]) -> ReplayScoredPrediction:
    required = {
        "scoring_schema_version",
        "source_replay_artifact_payload_sha256",
        "source_replay_snapshot_result_sha256",
        "dataset_id",
        "dataset_version",
        "lottery_type",
        "target_draw_number",
        "target_draw_date",
        "strategy_id",
        "source_history_status",
        "scoring_status",
        "scored_result_sha256",
    }
    optional = {
        "strategy_version",
        "source_history_reason_code",
        "source_prediction_status",
        "source_prediction_reason_code",
        "scoring_reason_code",
        "predicted_main_numbers",
        "target_outcome_sha256",
        "main_number_hit_count",
        "special_number_hit",
        "prize_tier_id",
        "prize_official_label",
        "no_prize_result",
    }
    _require_keys(payload, required, optional)
    try:
        record = ReplayScoredPrediction(
            scoring_schema_version=payload["scoring_schema_version"],
            source_replay_artifact_payload_sha256=payload[
                "source_replay_artifact_payload_sha256"
            ],
            source_replay_snapshot_result_sha256=payload[
                "source_replay_snapshot_result_sha256"
            ],
            dataset_id=payload["dataset_id"],
            dataset_version=payload["dataset_version"],
            lottery_type=LotteryType(payload["lottery_type"]),
            target_draw_number=payload["target_draw_number"],
            target_draw_date=date.fromisoformat(payload["target_draw_date"]),
            strategy_id=payload["strategy_id"],
            strategy_version=payload.get("strategy_version"),
            source_history_status=payload["source_history_status"],
            source_history_reason_code=payload.get("source_history_reason_code"),
            source_prediction_status=payload.get("source_prediction_status"),
            source_prediction_reason_code=payload.get("source_prediction_reason_code"),
            scoring_status=ReplayScoringStatus(payload["scoring_status"]),
            scoring_reason_code=(
                ReplayScoringReason(payload["scoring_reason_code"])
                if "scoring_reason_code" in payload
                else None
            ),
            predicted_main_numbers=(
                tuple(payload["predicted_main_numbers"])
                if "predicted_main_numbers" in payload
                else None
            ),
            target_outcome_sha256=payload.get("target_outcome_sha256"),
            main_number_hit_count=payload.get("main_number_hit_count"),
            special_number_hit=payload.get("special_number_hit"),
            prize_tier_id=(
                BigLottoPrizeTierId(payload["prize_tier_id"])
                if "prize_tier_id" in payload
                else None
            ),
            prize_official_label=payload.get("prize_official_label"),
            no_prize_result=(
                NoPrizeResult(payload["no_prize_result"])
                if "no_prize_result" in payload
                else None
            ),
            scored_result_sha256=payload["scored_result_sha256"],
        )
    except (TypeError, ValueError) as exc:
        raise ReplayScoringArtifactTamperError(
            f"nested scored record is invalid: {exc}"
        ) from exc
    if recompute_scored_result_sha256(record) != record.scored_result_sha256:
        raise ReplayScoringArtifactTamperError("nested scored-result hash mismatch")
    return record


def _aggregation_from_dict(payload: dict[str, Any]) -> ReplayPrizeAggregation:
    required = {
        "aggregation_schema_version",
        "source_snapshot_count",
        "scored_count",
        "history_closed_count",
        "prediction_closed_count",
        "target_outcome_not_found_count",
        "target_identity_mismatch_count",
        "first_prize_count",
        "second_prize_count",
        "third_prize_count",
        "fourth_prize_count",
        "fifth_prize_count",
        "sixth_prize_count",
        "seventh_prize_count",
        "general_prize_count",
        "no_prize_count",
        "aggregation_sha256",
    }
    _require_keys(payload, required, {"strategy_id", "strategy_version"})
    try:
        aggregation = ReplayPrizeAggregation(
            aggregation_schema_version=payload["aggregation_schema_version"],
            strategy_id=payload.get("strategy_id"),
            strategy_version=payload.get("strategy_version"),
            source_snapshot_count=payload["source_snapshot_count"],
            scored_count=payload["scored_count"],
            history_closed_count=payload["history_closed_count"],
            prediction_closed_count=payload["prediction_closed_count"],
            target_outcome_not_found_count=payload["target_outcome_not_found_count"],
            target_identity_mismatch_count=payload["target_identity_mismatch_count"],
            first_prize_count=payload["first_prize_count"],
            second_prize_count=payload["second_prize_count"],
            third_prize_count=payload["third_prize_count"],
            fourth_prize_count=payload["fourth_prize_count"],
            fifth_prize_count=payload["fifth_prize_count"],
            sixth_prize_count=payload["sixth_prize_count"],
            seventh_prize_count=payload["seventh_prize_count"],
            general_prize_count=payload["general_prize_count"],
            no_prize_count=payload["no_prize_count"],
            aggregation_sha256=payload["aggregation_sha256"],
        )
    except (TypeError, ValueError) as exc:
        raise ReplayScoringArtifactTamperError(
            f"nested aggregation is invalid: {exc}"
        ) from exc
    if recompute_aggregation_sha256(aggregation) != aggregation.aggregation_sha256:
        raise ReplayScoringArtifactTamperError("aggregation hash mismatch")
    return aggregation


def _require_keys(
    payload: dict[str, Any],
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    if set(payload) != required | (set(payload) & (optional or set())):
        missing = required - set(payload)
        extra = set(payload) - allowed
        raise ReplayScoringArtifactShapeError(
            f"invalid keys; missing={sorted(missing)} extra={sorted(extra)}"
        )


__all__ = [
    "SCORING_ARTIFACT_SCHEMA_VERSION",
    "ReplayScoringArtifact",
    "ReplayScoringArtifactShapeError",
    "ReplayScoringArtifactTamperError",
    "build_replay_scoring_artifact",
    "deserialize_replay_scoring_artifact",
    "recompute_scoring_artifact_payload_sha256",
    "serialize_replay_scoring_artifact",
]
