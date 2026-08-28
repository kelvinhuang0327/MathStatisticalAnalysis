"""LCJ-1 evidence artifact for one Next-Draw Recommendation backtest snapshot.

Wraps a fresh, self-contained causal backtest of every executable BIG_LOTTO
strategy's own native-ticket output (see
``lottolab.domain.next_draw_recommendation`` for the boundary this evidence
feeds) into one hash-stamped, immutable document, following the same LCJ-1
self-excluding top-level SHA-256 convention as
``ReplayPortfolioRankingArtifact``.

This artifact records a FRESH_UNREVIEWED computation: it is produced by
directly executing each strategy's shipped adapter against real historical
draws (never a fabricated or estimated number), but it has not gone through
this repository's existing evidence-promotion review. Consumers must treat
its ``computation_status`` field as load-bearing, not decorative -- it is
never silently presented as a ``CANONICAL_CURRENT`` storage authority.
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum
from fractions import Fraction

from lottolab.evidence.canonical_json import canonical_bytes, self_key_removed_sha256

RECOMMENDATION_EVIDENCE_SCHEMA_VERSION = "1.0.0"
_PLACEHOLDER_SHA256 = "0" * 64


class RecommendationEvidenceArtifactTamperError(ValueError):
    """The top-level artifact hash does not match its own content."""


class ComputationStatus(StrEnum):
    FRESH_UNREVIEWED = "FRESH_UNREVIEWED"


class StrategyBacktestStatus(StrEnum):
    EVALUATED = "EVALUATED"
    NOT_ABC_COMPLIANT = "NOT_ABC_COMPLIANT"
    NO_OBSERVATIONS = "NO_OBSERVATIONS"
    DRIVER_ERROR = "DRIVER_ERROR"


def _fraction_to_pair(value: Fraction) -> dict[str, str]:
    # Portfolio random-baseline denominators (comb(49,6) raised to a native
    # ticket count up to 10) routinely exceed the LCJ-1 safe-integer bound,
    # so exact values are carried as decimal strings, not JSON integers --
    # the same convention ``evidence/models.py`` uses for big exact numbers.
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def _pair_to_fraction(pair: dict[str, str]) -> Fraction:
    return Fraction(int(pair["numerator"]), int(pair["denominator"]))


@dataclasses.dataclass(frozen=True, slots=True)
class RecommendationEvidenceWindow:
    window_kind: str
    window_status: str
    eligible_draw_count: int
    observed_value: Fraction | None
    random_reference: Fraction | None
    delta_vs_random: Fraction | None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "window_kind": self.window_kind,
            "window_status": self.window_status,
            "eligible_draw_count": self.eligible_draw_count,
            "observed_value": (
                None if self.observed_value is None else _fraction_to_pair(self.observed_value)
            ),
            "random_reference": (
                None if self.random_reference is None else _fraction_to_pair(self.random_reference)
            ),
            "delta_vs_random": (
                None if self.delta_vs_random is None else _fraction_to_pair(self.delta_vs_random)
            ),
        }

    @classmethod
    def from_canonical_dict(cls, payload: dict[str, object]) -> RecommendationEvidenceWindow:
        def _opt(key: str) -> Fraction | None:
            value = payload[key]
            return None if value is None else _pair_to_fraction(value)  # type: ignore[arg-type]

        return cls(
            window_kind=payload["window_kind"],  # type: ignore[arg-type]
            window_status=payload["window_status"],  # type: ignore[arg-type]
            eligible_draw_count=payload["eligible_draw_count"],  # type: ignore[arg-type]
            observed_value=_opt("observed_value"),
            random_reference=_opt("random_reference"),
            delta_vs_random=_opt("delta_vs_random"),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class RecommendationEvidenceStrategyRecord:
    strategy_id: str
    strategy_name: str
    native_ticket_count: int
    status: StrategyBacktestStatus
    hit_tier_id: str
    windows: tuple[RecommendationEvidenceWindow, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "native_ticket_count": self.native_ticket_count,
            "status": self.status.value,
            "hit_tier_id": self.hit_tier_id,
            "windows": [window.canonical_dict() for window in self.windows],
        }

    @classmethod
    def from_canonical_dict(
        cls, payload: dict[str, object]
    ) -> RecommendationEvidenceStrategyRecord:
        return cls(
            strategy_id=payload["strategy_id"],  # type: ignore[arg-type]
            strategy_name=payload["strategy_name"],  # type: ignore[arg-type]
            native_ticket_count=payload["native_ticket_count"],  # type: ignore[arg-type]
            status=StrategyBacktestStatus(payload["status"]),
            hit_tier_id=payload["hit_tier_id"],  # type: ignore[arg-type]
            windows=tuple(
                RecommendationEvidenceWindow.from_canonical_dict(window)
                for window in payload["windows"]  # type: ignore[union-attr]
            ),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class NextDrawRecommendationEvidenceArtifact:
    """One immutable, hash-stamped snapshot of the native-ticket-count backtest."""

    artifact_schema_version: str
    computation_status: ComputationStatus
    lottery_type: str
    source_draw_db_sha256: str
    source_draw_count: int
    last_causal_draw_id: str
    replay_depth: int
    hit_tier_id: str
    records: tuple[RecommendationEvidenceStrategyRecord, ...]
    artifact_sha256: str

    def __post_init__(self) -> None:
        if self.artifact_schema_version != RECOMMENDATION_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unsupported artifact_schema_version")
        recomputed = self_key_removed_sha256(self.canonical_dict(), "artifact_sha256")
        if self.artifact_sha256 != recomputed:
            raise RecommendationEvidenceArtifactTamperError(
                f"declared artifact_sha256={self.artifact_sha256} != recomputed {recomputed}"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "artifact_schema_version": self.artifact_schema_version,
            "computation_status": self.computation_status.value,
            "lottery_type": self.lottery_type,
            "source_draw_db_sha256": self.source_draw_db_sha256,
            "source_draw_count": self.source_draw_count,
            "last_causal_draw_id": self.last_causal_draw_id,
            "replay_depth": self.replay_depth,
            "hit_tier_id": self.hit_tier_id,
            "records": [record.canonical_dict() for record in self.records],
            "artifact_sha256": self.artifact_sha256,
        }

    @classmethod
    def build(
        cls,
        *,
        lottery_type: str,
        source_draw_db_sha256: str,
        source_draw_count: int,
        last_causal_draw_id: str,
        replay_depth: int,
        hit_tier_id: str,
        records: tuple[RecommendationEvidenceStrategyRecord, ...],
    ) -> NextDrawRecommendationEvidenceArtifact:
        content = {
            "artifact_schema_version": RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
            "computation_status": ComputationStatus.FRESH_UNREVIEWED.value,
            "lottery_type": lottery_type,
            "source_draw_db_sha256": source_draw_db_sha256,
            "source_draw_count": source_draw_count,
            "last_causal_draw_id": last_causal_draw_id,
            "replay_depth": replay_depth,
            "hit_tier_id": hit_tier_id,
            "records": [record.canonical_dict() for record in records],
            "artifact_sha256": _PLACEHOLDER_SHA256,
        }
        real_sha256 = self_key_removed_sha256(content, "artifact_sha256")
        return cls(
            artifact_schema_version=RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
            computation_status=ComputationStatus.FRESH_UNREVIEWED,
            lottery_type=lottery_type,
            source_draw_db_sha256=source_draw_db_sha256,
            source_draw_count=source_draw_count,
            last_causal_draw_id=last_causal_draw_id,
            replay_depth=replay_depth,
            hit_tier_id=hit_tier_id,
            records=records,
            artifact_sha256=real_sha256,
        )

    @classmethod
    def from_canonical_dict(
        cls, payload: dict[str, object]
    ) -> NextDrawRecommendationEvidenceArtifact:
        return cls(
            artifact_schema_version=payload["artifact_schema_version"],  # type: ignore[arg-type]
            computation_status=ComputationStatus(payload["computation_status"]),
            lottery_type=payload["lottery_type"],  # type: ignore[arg-type]
            source_draw_db_sha256=payload["source_draw_db_sha256"],  # type: ignore[arg-type]
            source_draw_count=payload["source_draw_count"],  # type: ignore[arg-type]
            last_causal_draw_id=payload["last_causal_draw_id"],  # type: ignore[arg-type]
            replay_depth=payload["replay_depth"],  # type: ignore[arg-type]
            hit_tier_id=payload["hit_tier_id"],  # type: ignore[arg-type]
            records=tuple(
                RecommendationEvidenceStrategyRecord.from_canonical_dict(record)
                for record in payload["records"]  # type: ignore[union-attr]
            ),
            artifact_sha256=payload["artifact_sha256"],  # type: ignore[arg-type]
        )


def canonical_json_bytes(artifact: NextDrawRecommendationEvidenceArtifact) -> bytes:
    return canonical_bytes(artifact.canonical_dict())


__all__ = [
    "RECOMMENDATION_EVIDENCE_SCHEMA_VERSION",
    "ComputationStatus",
    "NextDrawRecommendationEvidenceArtifact",
    "RecommendationEvidenceArtifactTamperError",
    "RecommendationEvidenceStrategyRecord",
    "RecommendationEvidenceWindow",
    "StrategyBacktestStatus",
    "canonical_json_bytes",
]
