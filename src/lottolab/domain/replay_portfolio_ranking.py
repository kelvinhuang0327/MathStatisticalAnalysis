"""Immutable domain contracts for deterministic, post-hoc Replay portfolio ranking.

Ranks 1-5-strategy portfolios drawn from one validated ``ReplayScoringArtifact``
under the frozen ``BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1`` descriptive policy.
This module owns shapes and invariants only: it enumerates no combination,
reads no artifact, executes no strategy, and computes no payout, probability,
EV, or ROI. "Optimal" means rank 1 under this frozen policy only -- it is not
a predictive or recommendation claim.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any

RANKING_POLICY_ID = "BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1"
RANKING_DOMAIN_SCHEMA_VERSION = "1.0.0"

MIN_TICKET_COUNT = 1
MAX_TICKET_COUNT = 5
MIN_TOP_K = 1
MAX_TOP_K = 50
DEFAULT_TOP_K = 10
MAX_EXHAUSTIVE_PORTFOLIO_CANDIDATES = 100_000

_TICKET_COUNTS = tuple(range(MIN_TICKET_COUNT, MAX_TICKET_COUNT + 1))

_TOTAL_COUNT_FIELDS = (
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
)

_TIER_COUNT_FIELDS = (
    "first_prize_count",
    "second_prize_count",
    "third_prize_count",
    "fourth_prize_count",
    "fifth_prize_count",
    "sixth_prize_count",
    "seventh_prize_count",
    "general_prize_count",
)


class PortfolioSearchSpaceExceededError(ValueError):
    """The complete N=1..5 combination search space exceeds the exhaustive-search cap."""


class PortfolioGroupStatus(StrEnum):
    RANKED = "RANKED"
    INSUFFICIENT_STRATEGIES = "INSUFFICIENT_STRATEGIES"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def portfolio_sort_key(
    *,
    first_prize_count: int,
    second_prize_count: int,
    third_prize_count: int,
    fourth_prize_count: int,
    fifth_prize_count: int,
    sixth_prize_count: int,
    seventh_prize_count: int,
    general_prize_count: int,
    scored_count: int,
    target_identity_mismatch_count: int,
    target_outcome_not_found_count: int,
    history_closed_count: int,
    prediction_closed_count: int,
    strategy_positions: tuple[int, ...],
) -> tuple[int, ...]:
    """The frozen ``BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1`` tie-break tuple.

    Ascending comparison of this tuple reproduces the policy's 14-key order
    exactly: tiers 1..7 then general (descending, via negation), scored count
    (descending), the four closed-style counts (ascending), then the
    source-strategy-position tuple (ascending) as the final tie-break.
    """

    return (
        -first_prize_count,
        -second_prize_count,
        -third_prize_count,
        -fourth_prize_count,
        -fifth_prize_count,
        -sixth_prize_count,
        -seventh_prize_count,
        -general_prize_count,
        -scored_count,
        target_identity_mismatch_count,
        target_outcome_not_found_count,
        history_closed_count,
        prediction_closed_count,
        *strategy_positions,
    )


def _candidate_content_dict(
    *,
    rank: int,
    ticket_count: int,
    strategy_positions: tuple[int, ...],
    strategy_ids: tuple[str, ...],
    strategy_versions: tuple[str | None, ...],
    target_count: int,
    total_ticket_count: int,
    scored_count: int,
    history_closed_count: int,
    prediction_closed_count: int,
    target_outcome_not_found_count: int,
    target_identity_mismatch_count: int,
    first_prize_count: int,
    second_prize_count: int,
    third_prize_count: int,
    fourth_prize_count: int,
    fifth_prize_count: int,
    sixth_prize_count: int,
    seventh_prize_count: int,
    general_prize_count: int,
    no_prize_count: int,
    winning_ticket_count: int,
) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    for position, strategy_id, strategy_version in zip(
        strategy_positions, strategy_ids, strategy_versions, strict=True
    ):
        member: dict[str, Any] = {"source_position": position, "strategy_id": strategy_id}
        if strategy_version is not None:
            member["strategy_version"] = strategy_version
        members.append(member)
    return {
        "rank": rank,
        "ticket_count": ticket_count,
        "members": members,
        "target_count": target_count,
        "total_ticket_count": total_ticket_count,
        "scored_count": scored_count,
        "history_closed_count": history_closed_count,
        "prediction_closed_count": prediction_closed_count,
        "target_outcome_not_found_count": target_outcome_not_found_count,
        "target_identity_mismatch_count": target_identity_mismatch_count,
        "first_prize_count": first_prize_count,
        "second_prize_count": second_prize_count,
        "third_prize_count": third_prize_count,
        "fourth_prize_count": fourth_prize_count,
        "fifth_prize_count": fifth_prize_count,
        "sixth_prize_count": sixth_prize_count,
        "seventh_prize_count": seventh_prize_count,
        "general_prize_count": general_prize_count,
        "no_prize_count": no_prize_count,
        "winning_ticket_count": winning_ticket_count,
    }


@dataclass(frozen=True, slots=True)
class RankedPortfolioCandidate:
    """One ranked N-strategy portfolio within its ticket-count group.

    ``strategy_positions`` are ascending 0-based indices into the source
    artifact's ``strategy_identities``/``strategy_aggregates`` tuples; the
    frozen policy's final tie-break compares this tuple directly.
    """

    rank: int
    ticket_count: int
    strategy_positions: tuple[int, ...]
    strategy_ids: tuple[str, ...]
    strategy_versions: tuple[str | None, ...]
    target_count: int
    total_ticket_count: int
    scored_count: int
    history_closed_count: int
    prediction_closed_count: int
    target_outcome_not_found_count: int
    target_identity_mismatch_count: int
    first_prize_count: int
    second_prize_count: int
    third_prize_count: int
    fourth_prize_count: int
    fifth_prize_count: int
    sixth_prize_count: int
    seventh_prize_count: int
    general_prize_count: int
    no_prize_count: int
    winning_ticket_count: int
    candidate_sha256: str

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("rank must be a positive integer")
        if self.ticket_count not in _TICKET_COUNTS:
            raise ValueError("ticket_count must fall within 1..5")
        if len(self.strategy_positions) != self.ticket_count:
            raise ValueError("strategy_positions length must equal ticket_count")
        if tuple(sorted(set(self.strategy_positions))) != self.strategy_positions:
            raise ValueError("strategy_positions must be strictly ascending and distinct")
        if (
            len(self.strategy_ids) != self.ticket_count
            or len(self.strategy_versions) != self.ticket_count
        ):
            raise ValueError("strategy_ids/strategy_versions length must equal ticket_count")
        if len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise ValueError("strategy_ids must not contain duplicates")
        if self.target_count < 1:
            raise ValueError("target_count must be positive")
        if self.total_ticket_count != self.target_count * self.ticket_count:
            raise ValueError("total_ticket_count must equal target_count * ticket_count")

        count_fields = ("target_count", "total_ticket_count", *_TOTAL_COUNT_FIELDS)
        for name in count_fields:
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

        closed_total = (
            self.history_closed_count
            + self.prediction_closed_count
            + self.target_outcome_not_found_count
            + self.target_identity_mismatch_count
        )
        if self.total_ticket_count != self.scored_count + closed_total:
            raise ValueError("total_ticket_count does not equal scored plus closed counts")
        tier_total = sum(getattr(self, name) for name in _TIER_COUNT_FIELDS)
        if self.scored_count != tier_total + self.no_prize_count:
            raise ValueError("scored_count does not equal prize-tier plus no-prize counts")
        if self.winning_ticket_count != tier_total:
            raise ValueError("winning_ticket_count must equal the sum of the eight tier counts")

        if len(self.candidate_sha256) != 64:
            raise ValueError("candidate_sha256 must be a SHA-256 digest")
        if self.candidate_sha256 != recompute_candidate_sha256(self):
            raise ValueError("candidate_sha256 does not match candidate content")

    @property
    def sort_key(self) -> tuple[int, ...]:
        return portfolio_sort_key(
            first_prize_count=self.first_prize_count,
            second_prize_count=self.second_prize_count,
            third_prize_count=self.third_prize_count,
            fourth_prize_count=self.fourth_prize_count,
            fifth_prize_count=self.fifth_prize_count,
            sixth_prize_count=self.sixth_prize_count,
            seventh_prize_count=self.seventh_prize_count,
            general_prize_count=self.general_prize_count,
            scored_count=self.scored_count,
            target_identity_mismatch_count=self.target_identity_mismatch_count,
            target_outcome_not_found_count=self.target_outcome_not_found_count,
            history_closed_count=self.history_closed_count,
            prediction_closed_count=self.prediction_closed_count,
            strategy_positions=self.strategy_positions,
        )


def recompute_candidate_sha256(candidate: RankedPortfolioCandidate) -> str:
    values = {field.name: getattr(candidate, field.name) for field in fields(candidate)}
    del values["candidate_sha256"]
    return _canonical_sha256(_candidate_content_dict(**values))


def candidate_canonical_dict(
    candidate: RankedPortfolioCandidate, *, include_hash: bool = True
) -> dict[str, Any]:
    """The candidate's canonical content dict, for embedding in a parent artifact."""

    values = {field.name: getattr(candidate, field.name) for field in fields(candidate)}
    del values["candidate_sha256"]
    payload = _candidate_content_dict(**values)
    if include_hash:
        payload["candidate_sha256"] = candidate.candidate_sha256
    return payload


def build_ranked_portfolio_candidate(
    *,
    rank: int,
    ticket_count: int,
    strategy_positions: tuple[int, ...],
    strategy_ids: tuple[str, ...],
    strategy_versions: tuple[str | None, ...],
    target_count: int,
    total_ticket_count: int,
    scored_count: int,
    history_closed_count: int,
    prediction_closed_count: int,
    target_outcome_not_found_count: int,
    target_identity_mismatch_count: int,
    first_prize_count: int,
    second_prize_count: int,
    third_prize_count: int,
    fourth_prize_count: int,
    fifth_prize_count: int,
    sixth_prize_count: int,
    seventh_prize_count: int,
    general_prize_count: int,
    no_prize_count: int,
    winning_ticket_count: int,
) -> RankedPortfolioCandidate:
    content = _candidate_content_dict(
        rank=rank,
        ticket_count=ticket_count,
        strategy_positions=strategy_positions,
        strategy_ids=strategy_ids,
        strategy_versions=strategy_versions,
        target_count=target_count,
        total_ticket_count=total_ticket_count,
        scored_count=scored_count,
        history_closed_count=history_closed_count,
        prediction_closed_count=prediction_closed_count,
        target_outcome_not_found_count=target_outcome_not_found_count,
        target_identity_mismatch_count=target_identity_mismatch_count,
        first_prize_count=first_prize_count,
        second_prize_count=second_prize_count,
        third_prize_count=third_prize_count,
        fourth_prize_count=fourth_prize_count,
        fifth_prize_count=fifth_prize_count,
        sixth_prize_count=sixth_prize_count,
        seventh_prize_count=seventh_prize_count,
        general_prize_count=general_prize_count,
        no_prize_count=no_prize_count,
        winning_ticket_count=winning_ticket_count,
    )
    return RankedPortfolioCandidate(
        rank=rank,
        ticket_count=ticket_count,
        strategy_positions=strategy_positions,
        strategy_ids=strategy_ids,
        strategy_versions=strategy_versions,
        target_count=target_count,
        total_ticket_count=total_ticket_count,
        scored_count=scored_count,
        history_closed_count=history_closed_count,
        prediction_closed_count=prediction_closed_count,
        target_outcome_not_found_count=target_outcome_not_found_count,
        target_identity_mismatch_count=target_identity_mismatch_count,
        first_prize_count=first_prize_count,
        second_prize_count=second_prize_count,
        third_prize_count=third_prize_count,
        fourth_prize_count=fourth_prize_count,
        fifth_prize_count=fifth_prize_count,
        sixth_prize_count=sixth_prize_count,
        seventh_prize_count=seventh_prize_count,
        general_prize_count=general_prize_count,
        no_prize_count=no_prize_count,
        winning_ticket_count=winning_ticket_count,
        candidate_sha256=_canonical_sha256(content),
    )


@dataclass(frozen=True, slots=True)
class PortfolioRankingGroup:
    """The exhaustively ranked candidates for one fixed ticket count."""

    ticket_count: int
    status: PortfolioGroupStatus
    total_candidate_count: int
    candidates: tuple[RankedPortfolioCandidate, ...]

    def __post_init__(self) -> None:
        if self.ticket_count not in _TICKET_COUNTS:
            raise ValueError("ticket_count must fall within 1..5")
        if self.total_candidate_count < 0:
            raise ValueError("total_candidate_count must be non-negative")
        if self.status is PortfolioGroupStatus.INSUFFICIENT_STRATEGIES:
            if self.total_candidate_count != 0 or self.candidates:
                raise ValueError("INSUFFICIENT_STRATEGIES groups must carry zero candidates")
        elif len(self.candidates) > self.total_candidate_count:
            raise ValueError("candidates cannot exceed the total candidate count")

        for candidate in self.candidates:
            if candidate.ticket_count != self.ticket_count:
                raise ValueError("candidate ticket_count must match its group")
        ranks = tuple(candidate.rank for candidate in self.candidates)
        if ranks != tuple(range(1, len(self.candidates) + 1)):
            raise ValueError("candidate ranks must be contiguous starting at 1")
        sort_keys = tuple(candidate.sort_key for candidate in self.candidates)
        if sort_keys != tuple(sorted(sort_keys)):
            raise ValueError("candidates must be sorted per the frozen ranking policy")


@dataclass(frozen=True, slots=True)
class PortfolioRankingResult:
    """The complete, always-five-group ranking result for one artifact."""

    strategy_count: int
    target_count: int
    top_k: int
    groups: tuple[PortfolioRankingGroup, ...]

    def __post_init__(self) -> None:
        if self.strategy_count < 0:
            raise ValueError("strategy_count must be non-negative")
        if self.target_count < 1:
            raise ValueError("target_count must be positive")
        if not MIN_TOP_K <= self.top_k <= MAX_TOP_K:
            raise ValueError("top_k must fall within 1..50")
        if tuple(group.ticket_count for group in self.groups) != _TICKET_COUNTS:
            raise ValueError("exactly five groups (ticket_count 1..5, in order) are required")
        for group in self.groups:
            if group.status is PortfolioGroupStatus.INSUFFICIENT_STRATEGIES:
                if self.strategy_count >= group.ticket_count:
                    raise ValueError("INSUFFICIENT_STRATEGIES is inconsistent with strategy_count")
            elif self.strategy_count < group.ticket_count:
                raise ValueError("a rankable group requires enough strategies")
            if len(group.candidates) > self.top_k:
                raise ValueError("a group cannot expose more than top_k candidates")
            for candidate in group.candidates:
                if candidate.target_count != self.target_count:
                    raise ValueError("candidate target_count must match the result")
                if any(
                    position >= self.strategy_count for position in candidate.strategy_positions
                ):
                    raise ValueError("candidate strategy_positions must reference real strategies")


__all__ = [
    "DEFAULT_TOP_K",
    "MAX_EXHAUSTIVE_PORTFOLIO_CANDIDATES",
    "MAX_TICKET_COUNT",
    "MAX_TOP_K",
    "MIN_TICKET_COUNT",
    "MIN_TOP_K",
    "RANKING_DOMAIN_SCHEMA_VERSION",
    "RANKING_POLICY_ID",
    "PortfolioGroupStatus",
    "PortfolioRankingGroup",
    "PortfolioRankingResult",
    "PortfolioSearchSpaceExceededError",
    "RankedPortfolioCandidate",
    "build_ranked_portfolio_candidate",
    "candidate_canonical_dict",
    "portfolio_sort_key",
    "recompute_candidate_sha256",
]
