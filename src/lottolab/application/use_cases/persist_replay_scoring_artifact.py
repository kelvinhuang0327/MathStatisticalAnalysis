"""Persist one validated Replay-scoring artifact through the narrow writer port."""

from __future__ import annotations

from lottolab.application.ports import ReplayScoringProjectionWriter
from lottolab.domain.replay_scoring import (
    recompute_aggregation_sha256,
    recompute_scored_result_sha256,
)
from lottolab.domain.replay_scoring_projection import ReplayScoringPersistResult
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    ReplayScoringArtifactTamperError,
    recompute_scoring_artifact_payload_sha256,
    serialize_replay_scoring_artifact,
)


class PersistReplayScoringArtifact:
    """Revalidate one artifact, then delegate whole-run persistence to the writer port."""

    def __init__(self, writer: ReplayScoringProjectionWriter) -> None:
        self._writer = writer

    def execute(self, artifact: ReplayScoringArtifact) -> ReplayScoringPersistResult:
        _revalidate_source_artifact(artifact)
        canonical_bytes = serialize_replay_scoring_artifact(artifact)
        return self._writer.persist_replay_scoring_artifact(artifact, canonical_bytes)


def _revalidate_source_artifact(artifact: ReplayScoringArtifact) -> None:
    if recompute_scoring_artifact_payload_sha256(artifact) != artifact.payload_sha256:
        raise ReplayScoringArtifactTamperError("scoring artifact payload hash mismatch")
    for record in artifact.scored_predictions:
        if recompute_scored_result_sha256(record) != record.scored_result_sha256:
            raise ReplayScoringArtifactTamperError("nested scored-result hash mismatch")
    for aggregation in (*artifact.strategy_aggregates, artifact.overall_aggregate):
        if recompute_aggregation_sha256(aggregation) != aggregation.aggregation_sha256:
            raise ReplayScoringArtifactTamperError("nested aggregation hash mismatch")


__all__ = ["PersistReplayScoringArtifact"]
