"""Immutable pre-draw sealing contracts for the Next-Draw Recommendation surface.

``lottolab.domain.next_draw_recommendation`` composes a PREVIEW ranking that is
"never bound or sealed to a future target" (see that module's docstring). This
sibling module adds the *separate* binding dimension the preview stage
explicitly declared out of scope: a self-verifying, immutable record that
freezes one bucket-set of ranked candidates and their generated tickets
against one canonical future target, using the existing outcome-free target
authority in ``lottolab.domain.pre_outcome_target`` /
``lottolab.application.pre_outcome_target`` -- never a re-derived
"last draw + 1" schedule guess.

This module owns only the frozen seal *shape*, its closed vocabulary, and its
self-verifying digest. Resolving a target, checking outcome absence,
re-deriving the ranking projection, and generating tickets are orchestration
concerns that live one layer up, in
``lottolab.application.use_cases.seal_next_draw_recommendation`` and
``lottolab.application.use_cases.get_next_draw_recommendation_lifecycle``.

A sealed record never contains official outcome numbers: it freezes the
*prediction* side only (target identity, evidence/ranking/history digests,
and generated tickets), the same outcome-free boundary
``lottolab.domain.prospective_observer`` already draws between prediction and
scoring.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import (
    NATIVE_TICKET_COUNT_BUCKETS,
    RECOMMENDATION_POLICY_ID,
)
from lottolab.domain.prospective_observer import ObservationTarget

NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1 = "LOTTOLAB_NEXT_DRAW_RECOMMENDATION_SEAL_V1"
NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V2 = "LOTTOLAB_NEXT_DRAW_RECOMMENDATION_SEAL_V2"
NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION = NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V2

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", flags=re.ASCII)
_PLACEHOLDER_SHA256 = "0" * 64


class NextDrawRecommendationSealContractError(ValueError):
    """Base class for closed-contract validation failures in this module."""


class NextDrawRecommendationSealTamperError(NextDrawRecommendationSealContractError):
    """The seal's declared self-digest does not match its recomputed content."""


class NextDrawRecommendationLifecycleState(StrEnum):
    """Externally observable pre-draw sealing lifecycle for one lottery type."""

    WAITING_FOR_ELIGIBLE_TARGET = "WAITING_FOR_ELIGIBLE_TARGET"
    TARGET_AVAILABLE = "TARGET_AVAILABLE"
    PREDICTIONS_SEALED = "PREDICTIONS_SEALED"
    OUTCOME_AVAILABLE = "OUTCOME_AVAILABLE"


class TicketSealStatus(StrEnum):
    """Closed mirror of the application-layer ticket generation outcome."""

    OK = "OK"
    DECLINED = "DECLINED"
    UNREACHABLE = "UNREACHABLE"


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise NextDrawRecommendationSealContractError(f"{label} must be canonical non-empty text")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise NextDrawRecommendationSealContractError(f"{label} must be a lowercase SHA-256 digest")


def _require_git_object_id(value: object, label: str) -> None:
    if (
        type(value) is not str
        or _GIT_OBJECT_ID.fullmatch(value) is None
        or value == "0" * len(value)
    ):
        raise NextDrawRecommendationSealContractError(
            f"{label} must be a canonical non-placeholder full Git object ID"
        )


def _require_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise NextDrawRecommendationSealContractError(
            f"{label} must be a timezone-aware UTC datetime"
        )


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class SealedStrategyTickets:
    """One top-ranked strategy's frozen ticket-generation outcome at seal time."""

    rank: int
    strategy_id: str
    strategy_name: str
    status: TicketSealStatus
    tickets: tuple[tuple[int, ...], ...]
    detail: str

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise NextDrawRecommendationSealContractError("rank must be >= 1")
        _require_text(self.strategy_id, "strategy_id")
        _require_text(self.strategy_name, "strategy_name")
        if type(self.status) is not TicketSealStatus:
            raise NextDrawRecommendationSealContractError("status must be a TicketSealStatus")
        if type(self.detail) is not str:
            raise NextDrawRecommendationSealContractError("detail must be text")
        has_tickets = len(self.tickets) > 0
        if self.status is TicketSealStatus.OK and not has_tickets:
            raise NextDrawRecommendationSealContractError(
                "an OK sealed ticket set must carry at least one ticket"
            )
        if self.status is not TicketSealStatus.OK and has_tickets:
            raise NextDrawRecommendationSealContractError(
                "only an OK sealed ticket set may carry ticket numbers"
            )
        for ticket in self.tickets:
            if type(ticket) is not tuple or not ticket:
                raise NextDrawRecommendationSealContractError(
                    "each sealed ticket must be a non-empty tuple"
                )
            if any(type(number) is not int for number in ticket):
                raise NextDrawRecommendationSealContractError(
                    "sealed ticket numbers must be exact integers"
                )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "detail": self.detail,
            "rank": self.rank,
            "status": self.status.value,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "tickets": [list(ticket) for ticket in self.tickets],
        }

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> SealedStrategyTickets:
        mapping = _mapping(value, "sealed_ticket")
        _expect_keys(
            mapping,
            {"detail", "rank", "status", "strategy_id", "strategy_name", "tickets"},
            "sealed_ticket",
        )
        raw_tickets = mapping["tickets"]
        if type(raw_tickets) is not list:
            raise NextDrawRecommendationSealContractError("sealed_ticket.tickets must be a list")
        ticket_values = cast(list[object], raw_tickets)
        for ticket in ticket_values:
            if type(ticket) is not list:
                raise NextDrawRecommendationSealContractError(
                    "sealed_ticket.tickets[] must be a list"
                )
        return cls(
            rank=_int(mapping["rank"], "sealed_ticket.rank"),
            strategy_id=_string(mapping["strategy_id"], "sealed_ticket.strategy_id"),
            strategy_name=_string(mapping["strategy_name"], "sealed_ticket.strategy_name"),
            status=TicketSealStatus(_string(mapping["status"], "sealed_ticket.status")),
            tickets=tuple(
                tuple(
                    _int(number, "sealed_ticket.tickets[]")
                    for number in cast(list[object], ticket)
                )
                for ticket in ticket_values
            ),
            detail=_string_allow_empty(mapping["detail"], "sealed_ticket.detail"),
        )


@dataclass(frozen=True, slots=True)
class SealedRecommendationBucket:
    """One native-ticket-count bucket's frozen ranking projection and tickets."""

    native_ticket_count: int
    availability: str
    total_candidate_count: int
    ranked_strategy_ids: tuple[str, ...]
    ranking_projection_sha256: str
    sealed_tickets: tuple[SealedStrategyTickets, ...]

    def __post_init__(self) -> None:
        if self.native_ticket_count not in NATIVE_TICKET_COUNT_BUCKETS:
            raise NextDrawRecommendationSealContractError(
                f"native_ticket_count must be one of {NATIVE_TICKET_COUNT_BUCKETS}"
            )
        _require_text(self.availability, "availability")
        if self.total_candidate_count < 0:
            raise NextDrawRecommendationSealContractError(
                "total_candidate_count must be non-negative"
            )
        if len(self.ranked_strategy_ids) != len(set(self.ranked_strategy_ids)):
            raise NextDrawRecommendationSealContractError("ranked_strategy_ids must be unique")
        if len(self.ranked_strategy_ids) > self.total_candidate_count:
            raise NextDrawRecommendationSealContractError(
                "ranked_strategy_ids cannot exceed total_candidate_count"
            )
        _require_sha256(self.ranking_projection_sha256, "ranking_projection_sha256")
        sealed_ids = tuple(ticket.strategy_id for ticket in self.sealed_tickets)
        if len(sealed_ids) != len(set(sealed_ids)):
            raise NextDrawRecommendationSealContractError(
                "sealed_tickets strategy_id values must be unique"
            )
        ranked_prefix = self.ranked_strategy_ids[: len(self.sealed_tickets)]
        if sealed_ids != ranked_prefix:
            raise NextDrawRecommendationSealContractError(
                "sealed_tickets must cover exactly the leading ranked_strategy_ids, in rank order"
            )
        expected_ranks = tuple(range(1, len(self.sealed_tickets) + 1))
        if tuple(ticket.rank for ticket in self.sealed_tickets) != expected_ranks:
            raise NextDrawRecommendationSealContractError(
                "sealed_tickets must be contiguously ranked from 1"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability,
            "native_ticket_count": self.native_ticket_count,
            "ranked_strategy_ids": list(self.ranked_strategy_ids),
            "ranking_projection_sha256": self.ranking_projection_sha256,
            "sealed_tickets": [ticket.canonical_dict() for ticket in self.sealed_tickets],
            "total_candidate_count": self.total_candidate_count,
        }

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> SealedRecommendationBucket:
        mapping = _mapping(value, "sealed_bucket")
        _expect_keys(
            mapping,
            {
                "availability",
                "native_ticket_count",
                "ranked_strategy_ids",
                "ranking_projection_sha256",
                "sealed_tickets",
                "total_candidate_count",
            },
            "sealed_bucket",
        )
        raw_ids = mapping["ranked_strategy_ids"]
        if type(raw_ids) is not list:
            raise NextDrawRecommendationSealContractError(
                "sealed_bucket.ranked_strategy_ids must be a list"
            )
        raw_tickets = mapping["sealed_tickets"]
        if type(raw_tickets) is not list:
            raise NextDrawRecommendationSealContractError(
                "sealed_bucket.sealed_tickets must be a list"
            )
        return cls(
            native_ticket_count=_int(
                mapping["native_ticket_count"], "sealed_bucket.native_ticket_count"
            ),
            availability=_string(mapping["availability"], "sealed_bucket.availability"),
            total_candidate_count=_int(
                mapping["total_candidate_count"], "sealed_bucket.total_candidate_count"
            ),
            ranked_strategy_ids=tuple(
                _string(item, "sealed_bucket.ranked_strategy_ids[]")
                for item in cast(list[object], raw_ids)
            ),
            ranking_projection_sha256=_sha256(
                mapping["ranking_projection_sha256"], "sealed_bucket.ranking_projection_sha256"
            ),
            sealed_tickets=tuple(
                SealedStrategyTickets.from_canonical_dict(
                    _mapping(item, "sealed_bucket.sealed_tickets[]")
                )
                for item in cast(list[object], raw_tickets)
            ),
        )


@dataclass(frozen=True, slots=True)
class NextDrawRecommendationSealV1:
    """Permanent read-compatible representation of the original V1 seal.

    V1 predates source-Git binding. It is intentionally a separate immutable
    type: reading a historical V1 record must never manufacture V2 fields or
    rewrite the record as a newer schema.
    """

    schema_version: str
    target: ObservationTarget
    target_scheduled_at: datetime
    sealed_at: datetime
    ranking_policy_id: str
    target_registration_digest: str
    evidence_artifact_sha256: str
    causal_history_sha256: str
    causal_history_draw_count: int
    buckets: tuple[SealedRecommendationBucket, ...]
    seal_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1:
            raise NextDrawRecommendationSealContractError("unsupported V1 seal schema_version")
        if type(self.target) is not ObservationTarget:
            raise NextDrawRecommendationSealContractError("target must be an ObservationTarget")
        _require_utc(self.target_scheduled_at, "target_scheduled_at")
        _require_utc(self.sealed_at, "sealed_at")
        if self.ranking_policy_id != RECOMMENDATION_POLICY_ID:
            raise NextDrawRecommendationSealContractError(
                "ranking_policy_id must match the frozen NEXT_DRAW_ROBUSTNESS_V1 policy"
            )
        _require_sha256(self.target_registration_digest, "target_registration_digest")
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        _require_sha256(self.causal_history_sha256, "causal_history_sha256")
        if self.causal_history_draw_count < 0:
            raise NextDrawRecommendationSealContractError(
                "causal_history_draw_count must be non-negative"
            )
        bucket_counts = tuple(bucket.native_ticket_count for bucket in self.buckets)
        if bucket_counts != NATIVE_TICKET_COUNT_BUCKETS:
            raise NextDrawRecommendationSealContractError(
                "buckets must cover every supported native_ticket_count exactly once, in order"
            )
        if self.sealed_at >= self.target_scheduled_at:
            raise NextDrawRecommendationSealContractError(
                "a seal must be accepted strictly before its target's scheduled time"
            )
        _require_sha256(self.seal_digest, "seal_digest")
        expected = _canonical_sha256(self.canonical_material())
        if self.seal_digest != expected:
            raise NextDrawRecommendationSealTamperError(
                f"declared seal_digest={self.seal_digest} != recomputed {expected}"
            )

    def canonical_material(self) -> dict[str, object]:
        return _seal_v1_material(
            schema_version=self.schema_version,
            target=self.target,
            target_scheduled_at=self.target_scheduled_at,
            sealed_at=self.sealed_at,
            ranking_policy_id=self.ranking_policy_id,
            target_registration_digest=self.target_registration_digest,
            evidence_artifact_sha256=self.evidence_artifact_sha256,
            causal_history_sha256=self.causal_history_sha256,
            causal_history_draw_count=self.causal_history_draw_count,
            buckets=self.buckets,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "seal_digest": self.seal_digest}

    def bucket(self, native_ticket_count: int) -> SealedRecommendationBucket | None:
        for candidate in self.buckets:
            if candidate.native_ticket_count == native_ticket_count:
                return candidate
        return None

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> NextDrawRecommendationSealV1:
        mapping = _mapping(value, "seal")
        _expect_keys(
            mapping,
            {
                "buckets",
                "causal_history_draw_count",
                "causal_history_sha256",
                "evidence_artifact_sha256",
                "ranking_policy_id",
                "schema_version",
                "seal_digest",
                "sealed_at",
                "target",
                "target_registration_digest",
                "target_scheduled_at",
            },
            "seal",
        )
        raw_buckets = mapping["buckets"]
        if type(raw_buckets) is not list:
            raise NextDrawRecommendationSealContractError("seal.buckets must be a list")
        return cls(
            schema_version=_string(mapping["schema_version"], "seal.schema_version"),
            target=_target_from_canonical_dict(mapping["target"]),
            target_scheduled_at=_datetime(
                mapping["target_scheduled_at"], "seal.target_scheduled_at"
            ),
            sealed_at=_datetime(mapping["sealed_at"], "seal.sealed_at"),
            ranking_policy_id=_string(mapping["ranking_policy_id"], "seal.ranking_policy_id"),
            target_registration_digest=_sha256(
                mapping["target_registration_digest"], "seal.target_registration_digest"
            ),
            evidence_artifact_sha256=_sha256(
                mapping["evidence_artifact_sha256"], "seal.evidence_artifact_sha256"
            ),
            causal_history_sha256=_sha256(
                mapping["causal_history_sha256"], "seal.causal_history_sha256"
            ),
            causal_history_draw_count=_int(
                mapping["causal_history_draw_count"], "seal.causal_history_draw_count"
            ),
            buckets=tuple(
                SealedRecommendationBucket.from_canonical_dict(
                    _mapping(item, "seal.buckets[]")
                )
                for item in cast(list[object], raw_buckets)
            ),
            seal_digest=_sha256(mapping["seal_digest"], "seal.seal_digest"),
        )


@dataclass(frozen=True, slots=True)
class SourceGitIdentity:
    """Exact commit and corresponding tree for the clean executing worktree."""

    source_head: str
    source_tree: str

    def __post_init__(self) -> None:
        _require_git_object_id(self.source_head, "source_head")
        _require_git_object_id(self.source_tree, "source_tree")
        if len(self.source_head) != len(self.source_tree):
            raise NextDrawRecommendationSealContractError(
                "source_head and source_tree must use the same Git object format"
            )


@dataclass(frozen=True, slots=True)
class NextDrawRecommendationSeal:
    """Self-verifying, immutable pre-draw seal binding a target to frozen output.

    Created strictly before ``target_scheduled_at``, and never mutated after
    acceptance: any change to persisted bytes is caught by ``seal_digest``.
    """

    schema_version: str
    target: ObservationTarget
    target_scheduled_at: datetime
    sealed_at: datetime
    ranking_policy_id: str
    source_head: str
    source_tree: str
    target_registration_digest: str
    evidence_artifact_sha256: str
    causal_history_sha256: str
    causal_history_draw_count: int
    buckets: tuple[SealedRecommendationBucket, ...]
    seal_digest: str

    @classmethod
    def create(
        cls,
        *,
        target: ObservationTarget,
        target_scheduled_at: datetime,
        sealed_at: datetime,
        source_head: str,
        source_tree: str,
        target_registration_digest: str,
        evidence_artifact_sha256: str,
        causal_history_sha256: str,
        causal_history_draw_count: int,
        buckets: tuple[SealedRecommendationBucket, ...],
    ) -> NextDrawRecommendationSeal:
        material = _seal_material(
            schema_version=NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION,
            target=target,
            target_scheduled_at=target_scheduled_at,
            sealed_at=sealed_at,
            ranking_policy_id=RECOMMENDATION_POLICY_ID,
            source_head=source_head,
            source_tree=source_tree,
            target_registration_digest=target_registration_digest,
            evidence_artifact_sha256=evidence_artifact_sha256,
            causal_history_sha256=causal_history_sha256,
            causal_history_draw_count=causal_history_draw_count,
            buckets=buckets,
        )
        return cls(
            schema_version=NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION,
            target=target,
            target_scheduled_at=target_scheduled_at,
            sealed_at=sealed_at,
            ranking_policy_id=RECOMMENDATION_POLICY_ID,
            source_head=source_head,
            source_tree=source_tree,
            target_registration_digest=target_registration_digest,
            evidence_artifact_sha256=evidence_artifact_sha256,
            causal_history_sha256=causal_history_sha256,
            causal_history_draw_count=causal_history_draw_count,
            buckets=buckets,
            seal_digest=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.schema_version != NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION:
            raise NextDrawRecommendationSealContractError("unsupported seal schema_version")
        if type(self.target) is not ObservationTarget:
            raise NextDrawRecommendationSealContractError("target must be an ObservationTarget")
        _require_utc(self.target_scheduled_at, "target_scheduled_at")
        _require_utc(self.sealed_at, "sealed_at")
        if self.ranking_policy_id != RECOMMENDATION_POLICY_ID:
            raise NextDrawRecommendationSealContractError(
                "ranking_policy_id must match the frozen NEXT_DRAW_ROBUSTNESS_V1 policy"
            )
        _require_git_object_id(self.source_head, "source_head")
        _require_git_object_id(self.source_tree, "source_tree")
        if len(self.source_head) != len(self.source_tree):
            raise NextDrawRecommendationSealContractError(
                "source_head and source_tree must use the same Git object format"
            )
        _require_sha256(self.target_registration_digest, "target_registration_digest")
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        _require_sha256(self.causal_history_sha256, "causal_history_sha256")
        if self.causal_history_draw_count < 0:
            raise NextDrawRecommendationSealContractError(
                "causal_history_draw_count must be non-negative"
            )
        bucket_counts = tuple(bucket.native_ticket_count for bucket in self.buckets)
        if bucket_counts != NATIVE_TICKET_COUNT_BUCKETS:
            raise NextDrawRecommendationSealContractError(
                "buckets must cover every supported native_ticket_count exactly once, in order"
            )
        if self.sealed_at >= self.target_scheduled_at:
            raise NextDrawRecommendationSealContractError(
                "a seal must be accepted strictly before its target's scheduled time"
            )

        _require_sha256(self.seal_digest, "seal_digest")
        expected = _canonical_sha256(self.canonical_material())
        if self.seal_digest != expected:
            raise NextDrawRecommendationSealTamperError(
                f"declared seal_digest={self.seal_digest} != recomputed {expected}"
            )

    def canonical_material(self) -> dict[str, object]:
        return _seal_material(
            schema_version=self.schema_version,
            target=self.target,
            target_scheduled_at=self.target_scheduled_at,
            sealed_at=self.sealed_at,
            ranking_policy_id=self.ranking_policy_id,
            source_head=self.source_head,
            source_tree=self.source_tree,
            target_registration_digest=self.target_registration_digest,
            evidence_artifact_sha256=self.evidence_artifact_sha256,
            causal_history_sha256=self.causal_history_sha256,
            causal_history_draw_count=self.causal_history_draw_count,
            buckets=self.buckets,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "seal_digest": self.seal_digest}

    def bucket(self, native_ticket_count: int) -> SealedRecommendationBucket | None:
        for candidate in self.buckets:
            if candidate.native_ticket_count == native_ticket_count:
                return candidate
        return None

    def matches_frozen_inputs(
        self,
        *,
        target: ObservationTarget,
        target_scheduled_at: datetime,
        source_head: str,
        source_tree: str,
        target_registration_digest: str,
        evidence_artifact_sha256: str,
        causal_history_sha256: str,
        causal_history_draw_count: int,
    ) -> bool:
        """Whether another seal attempt shares this seal's frozen prediction inputs.

        "One seal per target" (see the sealing use case) is enforced against
        these *inputs* -- the source Git identity, registration, evidence, and
        causal-history identity a seal was built from -- never against the generated
        ``buckets`` bytes. Some catalog strategies are not reproducible run to
        run (see the Method Universe reproducibility axis); a strategy's
        generated ticket numbers may legitimately differ between two sealing
        attempts that share the exact same frozen inputs. Once any valid seal
        exists for a target, it is authoritative regardless of such
        differences -- this method decides only whether a new attempt should
        be treated as the *same* prediction event (``IDEMPOTENT_EXISTING``) or
        a genuinely competing one (``FAIL_CLOSED_CONFLICT``).
        """

        return (
            self.target == target
            and self.target_scheduled_at == target_scheduled_at
            and self.source_head == source_head
            and self.source_tree == source_tree
            and self.target_registration_digest == target_registration_digest
            and self.evidence_artifact_sha256 == evidence_artifact_sha256
            and self.causal_history_sha256 == causal_history_sha256
            and self.causal_history_draw_count == causal_history_draw_count
        )

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> NextDrawRecommendationSeal:
        mapping = _mapping(value, "seal")
        _expect_keys(
            mapping,
            {
                "buckets",
                "causal_history_draw_count",
                "causal_history_sha256",
                "evidence_artifact_sha256",
                "ranking_policy_id",
                "schema_version",
                "seal_digest",
                "sealed_at",
                "source_head",
                "source_tree",
                "target",
                "target_registration_digest",
                "target_scheduled_at",
            },
            "seal",
        )
        raw_buckets = mapping["buckets"]
        if type(raw_buckets) is not list:
            raise NextDrawRecommendationSealContractError("seal.buckets must be a list")
        return cls(
            schema_version=_string(mapping["schema_version"], "seal.schema_version"),
            target=_target_from_canonical_dict(mapping["target"]),
            target_scheduled_at=_datetime(
                mapping["target_scheduled_at"], "seal.target_scheduled_at"
            ),
            sealed_at=_datetime(mapping["sealed_at"], "seal.sealed_at"),
            ranking_policy_id=_string(mapping["ranking_policy_id"], "seal.ranking_policy_id"),
            source_head=_git_object_id(mapping["source_head"], "seal.source_head"),
            source_tree=_git_object_id(mapping["source_tree"], "seal.source_tree"),
            target_registration_digest=_sha256(
                mapping["target_registration_digest"], "seal.target_registration_digest"
            ),
            evidence_artifact_sha256=_sha256(
                mapping["evidence_artifact_sha256"], "seal.evidence_artifact_sha256"
            ),
            causal_history_sha256=_sha256(
                mapping["causal_history_sha256"], "seal.causal_history_sha256"
            ),
            causal_history_draw_count=_int(
                mapping["causal_history_draw_count"], "seal.causal_history_draw_count"
            ),
            buckets=tuple(
                SealedRecommendationBucket.from_canonical_dict(
                    _mapping(item, "seal.buckets[]")
                )
                for item in cast(list[object], raw_buckets)
            ),
            seal_digest=_sha256(mapping["seal_digest"], "seal.seal_digest"),
        )


type ReadableNextDrawRecommendationSeal = (
    NextDrawRecommendationSealV1 | NextDrawRecommendationSeal
)


def parse_next_draw_recommendation_seal(
    value: Mapping[str, object],
) -> ReadableNextDrawRecommendationSeal:
    """Strictly parse a supported immutable seal without schema conversion."""

    mapping = _mapping(value, "seal")
    schema_version = _string(mapping.get("schema_version"), "seal.schema_version")
    if schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1:
        return NextDrawRecommendationSealV1.from_canonical_dict(mapping)
    if schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V2:
        return NextDrawRecommendationSeal.from_canonical_dict(mapping)
    raise NextDrawRecommendationSealContractError("unsupported seal schema_version")


def _seal_v1_material(
    *,
    schema_version: str,
    target: ObservationTarget,
    target_scheduled_at: datetime,
    sealed_at: datetime,
    ranking_policy_id: str,
    target_registration_digest: str,
    evidence_artifact_sha256: str,
    causal_history_sha256: str,
    causal_history_draw_count: int,
    buckets: tuple[SealedRecommendationBucket, ...],
) -> dict[str, object]:
    return {
        "buckets": [bucket.canonical_dict() for bucket in buckets],
        "causal_history_draw_count": causal_history_draw_count,
        "causal_history_sha256": causal_history_sha256,
        "evidence_artifact_sha256": evidence_artifact_sha256,
        "ranking_policy_id": ranking_policy_id,
        "schema_version": schema_version,
        "sealed_at": _utc_text(sealed_at),
        "target": target.canonical_dict(),
        "target_registration_digest": target_registration_digest,
        "target_scheduled_at": _utc_text(target_scheduled_at),
    }


def _seal_material(
    *,
    schema_version: str,
    target: ObservationTarget,
    target_scheduled_at: datetime,
    sealed_at: datetime,
    ranking_policy_id: str,
    source_head: str,
    source_tree: str,
    target_registration_digest: str,
    evidence_artifact_sha256: str,
    causal_history_sha256: str,
    causal_history_draw_count: int,
    buckets: tuple[SealedRecommendationBucket, ...],
) -> dict[str, object]:
    return {
        "buckets": [bucket.canonical_dict() for bucket in buckets],
        "causal_history_draw_count": causal_history_draw_count,
        "causal_history_sha256": causal_history_sha256,
        "evidence_artifact_sha256": evidence_artifact_sha256,
        "ranking_policy_id": ranking_policy_id,
        "schema_version": schema_version,
        "sealed_at": _utc_text(sealed_at),
        "source_head": source_head,
        "source_tree": source_tree,
        "target": target.canonical_dict(),
        "target_registration_digest": target_registration_digest,
        "target_scheduled_at": _utc_text(target_scheduled_at),
    }


def _target_from_canonical_dict(value: object) -> ObservationTarget:
    mapping = _mapping(value, "seal.target")
    _expect_keys(mapping, {"draw_date", "draw_number", "lottery_type"}, "seal.target")
    try:
        lottery_type = LotteryType(_string(mapping["lottery_type"], "seal.target.lottery_type"))
    except ValueError as exc:
        raise NextDrawRecommendationSealContractError(
            "seal.target.lottery_type is unsupported"
        ) from exc
    return ObservationTarget(
        lottery_type=lottery_type,
        draw_number=_string(mapping["draw_number"], "seal.target.draw_number"),
        draw_date=_date(mapping["draw_date"], "seal.target.draw_date"),
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise NextDrawRecommendationSealContractError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise NextDrawRecommendationSealContractError(
            f"{label} fields differ; missing={missing}, unknown={unknown}"
        )


def _string(value: object, label: str) -> str:
    _require_text(value, label)
    return cast(str, value)


def _string_allow_empty(value: object, label: str) -> str:
    if type(value) is not str:
        raise NextDrawRecommendationSealContractError(f"{label} must be text")
    return value


def _sha256(value: object, label: str) -> str:
    _require_sha256(value, label)
    return cast(str, value)


def _git_object_id(value: object, label: str) -> str:
    _require_git_object_id(value, label)
    return cast(str, value)


def _int(value: object, label: str) -> int:
    if type(value) is not int:
        raise NextDrawRecommendationSealContractError(f"{label} must be an exact integer")
    return value


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise NextDrawRecommendationSealContractError(
            f"{label} must be a canonical ISO date"
        ) from exc
    if parsed.isoformat() != text:
        raise NextDrawRecommendationSealContractError(f"{label} must be a canonical ISO date")
    return parsed


def _datetime(value: object, label: str) -> datetime:
    text = _string(value, label)
    if not text.endswith("Z"):
        raise NextDrawRecommendationSealContractError(f"{label} must use canonical UTC text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise NextDrawRecommendationSealContractError(
            f"{label} must use canonical UTC text"
        ) from exc
    _require_utc(parsed, label)
    if _utc_text(parsed) != text:
        raise NextDrawRecommendationSealContractError(f"{label} must use canonical UTC text")
    return parsed


__all__ = [
    "NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION",
    "NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1",
    "NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V2",
    "NextDrawRecommendationLifecycleState",
    "NextDrawRecommendationSeal",
    "NextDrawRecommendationSealContractError",
    "NextDrawRecommendationSealTamperError",
    "NextDrawRecommendationSealV1",
    "ReadableNextDrawRecommendationSeal",
    "SealedRecommendationBucket",
    "SealedStrategyTickets",
    "SourceGitIdentity",
    "TicketSealStatus",
    "parse_next_draw_recommendation_seal",
]
