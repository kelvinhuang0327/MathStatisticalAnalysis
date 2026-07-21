"""Canonical LCJ-1 artifact for deterministic Replay portfolio-ranking evidence.

Wraps one :class:`PortfolioRankingResult` computed against a validated
``ReplayScoringArtifact``, stamping a top-level self-excluding SHA-256 over
the whole document (which itself embeds every already-hash-stamped
candidate). Builds on the existing LCJ-1 primitives in
``lottolab.evidence.canonical_json`` rather than reinventing canonicalization.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_portfolio_ranking import (
    RANKING_POLICY_ID,
    PortfolioRankingGroup,
    PortfolioRankingResult,
    RankedPortfolioCandidate,
    candidate_canonical_dict,
)
from lottolab.evidence.canonical_json import canonical_bytes, self_key_removed_sha256

RANKING_ARTIFACT_SCHEMA_VERSION = "1.0.0"
_PLACEHOLDER_SHA256 = "0" * 64
_SHA256_LENGTH = 64


class ReplayPortfolioRankingArtifactTamperError(ValueError):
    """The top-level ranking-artifact hash does not match its content."""


@dataclasses.dataclass(frozen=True, slots=True)
class ReplayPortfolioRankingArtifact:
    artifact_schema_version: str
    ranking_policy_id: str
    source_scoring_artifact_payload_sha256: str
    source_replay_artifact_payload_sha256: str
    dataset_id: str
    dataset_version: str
    lottery_type: LotteryType
    target_count: int
    strategy_count: int
    top_k: int
    groups: tuple[PortfolioRankingGroup, ...]
    artifact_sha256: str

    def __post_init__(self) -> None:
        if self.artifact_schema_version != RANKING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported ranking artifact schema version")
        if self.ranking_policy_id != RANKING_POLICY_ID:
            raise ValueError("unsupported ranking policy id")
        for label, value in (
            ("source_scoring_artifact_payload_sha256", self.source_scoring_artifact_payload_sha256),
            ("source_replay_artifact_payload_sha256", self.source_replay_artifact_payload_sha256),
        ):
            if len(value) != _SHA256_LENGTH:
                raise ValueError(f"{label} must be a SHA-256 digest")
        if not self.dataset_id or not self.dataset_version:
            raise ValueError("dataset identity/version must not be empty")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("Replay portfolio ranking currently supports BIG_LOTTO only")

        # Re-derives every group/candidate invariant (five groups, contiguous
        # ranks, sorted-per-policy order, count arithmetic) by constructing
        # the underlying domain result -- raises ValueError on any violation.
        PortfolioRankingResult(
            strategy_count=self.strategy_count,
            target_count=self.target_count,
            top_k=self.top_k,
            groups=self.groups,
        )

        if len(self.artifact_sha256) != _SHA256_LENGTH:
            raise ValueError("artifact_sha256 must be a SHA-256 digest")
        if recompute_ranking_artifact_sha256(self) != self.artifact_sha256:
            raise ReplayPortfolioRankingArtifactTamperError(
                "ranking artifact payload hash mismatch"
            )


def _candidate_dict(candidate: RankedPortfolioCandidate) -> dict[str, Any]:
    return candidate_canonical_dict(candidate, include_hash=True)


def _group_dict(group: PortfolioRankingGroup) -> dict[str, Any]:
    return {
        "ticket_count": group.ticket_count,
        "status": group.status.value,
        "total_candidate_count": group.total_candidate_count,
        "candidates": [_candidate_dict(candidate) for candidate in group.candidates],
    }


def _artifact_content_dict(
    *,
    artifact_schema_version: str,
    ranking_policy_id: str,
    source_scoring_artifact_payload_sha256: str,
    source_replay_artifact_payload_sha256: str,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    target_count: int,
    strategy_count: int,
    top_k: int,
    groups: tuple[PortfolioRankingGroup, ...],
    artifact_sha256: str,
) -> dict[str, Any]:
    return {
        "artifact_schema_version": artifact_schema_version,
        "artifact_sha256": artifact_sha256,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "groups": [_group_dict(group) for group in groups],
        "lottery_type": lottery_type.value,
        "ranking_policy_id": ranking_policy_id,
        "source_replay_artifact_payload_sha256": source_replay_artifact_payload_sha256,
        "source_scoring_artifact_payload_sha256": source_scoring_artifact_payload_sha256,
        "strategy_count": strategy_count,
        "target_count": target_count,
        "top_k": top_k,
    }


def recompute_ranking_artifact_sha256(artifact: ReplayPortfolioRankingArtifact) -> str:
    values = {
        field.name: getattr(artifact, field.name) for field in dataclasses.fields(artifact)
    }
    del values["artifact_sha256"]
    content = _artifact_content_dict(**values, artifact_sha256=_PLACEHOLDER_SHA256)
    return self_key_removed_sha256(content, "artifact_sha256")


def build_replay_portfolio_ranking_artifact(
    *,
    source_scoring_artifact_payload_sha256: str,
    source_replay_artifact_payload_sha256: str,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    result: PortfolioRankingResult,
) -> ReplayPortfolioRankingArtifact:
    values: dict[str, Any] = {
        "artifact_schema_version": RANKING_ARTIFACT_SCHEMA_VERSION,
        "ranking_policy_id": RANKING_POLICY_ID,
        "source_scoring_artifact_payload_sha256": source_scoring_artifact_payload_sha256,
        "source_replay_artifact_payload_sha256": source_replay_artifact_payload_sha256,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "lottery_type": lottery_type,
        "target_count": result.target_count,
        "strategy_count": result.strategy_count,
        "top_k": result.top_k,
        "groups": result.groups,
    }
    content = _artifact_content_dict(**values, artifact_sha256=_PLACEHOLDER_SHA256)
    return ReplayPortfolioRankingArtifact(
        **values,
        artifact_sha256=self_key_removed_sha256(content, "artifact_sha256"),
    )


def serialize_replay_portfolio_ranking_artifact(artifact: ReplayPortfolioRankingArtifact) -> bytes:
    if recompute_ranking_artifact_sha256(artifact) != artifact.artifact_sha256:
        raise ReplayPortfolioRankingArtifactTamperError("ranking artifact payload hash mismatch")
    values = {field.name: getattr(artifact, field.name) for field in dataclasses.fields(artifact)}
    return canonical_bytes(_artifact_content_dict(**values))


def portfolio_ranking_artifact_view(artifact: ReplayPortfolioRankingArtifact) -> dict[str, Any]:
    """A plain, JSON-ready view of ``artifact`` for API/response serialization."""

    values = {field.name: getattr(artifact, field.name) for field in dataclasses.fields(artifact)}
    return _artifact_content_dict(**values)


__all__ = [
    "RANKING_ARTIFACT_SCHEMA_VERSION",
    "ReplayPortfolioRankingArtifact",
    "ReplayPortfolioRankingArtifactTamperError",
    "build_replay_portfolio_ranking_artifact",
    "portfolio_ranking_artifact_view",
    "recompute_ranking_artifact_sha256",
    "serialize_replay_portfolio_ranking_artifact",
]
