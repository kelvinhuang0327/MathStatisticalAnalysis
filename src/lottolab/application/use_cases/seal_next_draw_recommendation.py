"""Explicit pre-draw sealing command for the Next-Draw Recommendation surface.

This is the *one* seal command described by the product's target-binding
design: resolve the canonical future target (reusing
``PreOutcomeTargetOperationalService`` -- never a re-derived "last draw + 1"
guess), verify the outcome is still absent, freeze the evidence/ranking/
causal-history digests, generate every supported native-ticket-count bucket's
top-ranked tickets, re-verify nothing drifted or became available while that
generation ran, and only then durably accept one immutable seal.

Sealing never joins, scores, or stores official outcome numbers -- it freezes
the *prediction* side only. It never mutates the draw database, the evidence
artifact, or the ``NEXT_DRAW_ROBUSTNESS_V1`` ranking algorithm; it only reads
their already-computed output and freezes a copy of it against one target.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from fractions import Fraction
from typing import Protocol, runtime_checkable

from lottolab.application.pre_outcome_target import (
    InvalidScheduleTimeError,
    OutcomeAlreadyAvailableError,
    OutcomePresenceProbe,
)
from lottolab.application.pre_outcome_target_operational import (
    CausalHistoryAuthority,
    OperationalRegistrationStatus,
    PreOutcomeTargetOperationalService,
)
from lottolab.application.use_cases.build_next_draw_recommendation import (
    BuildNextDrawRecommendationBucket,
)
from lottolab.application.use_cases.generate_next_draw_top_tickets import (
    GenerateNextDrawTopTickets,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import (
    NATIVE_TICKET_COUNT_BUCKETS,
    TOP_N,
    RecommendationBucketView,
)
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationSeal,
    SealedRecommendationBucket,
    SealedStrategyTickets,
    SourceGitIdentity,
    TicketSealStatus,
)
from lottolab.domain.pre_outcome_target import PreOutcomeTargetRegistration
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.evidence.next_draw_recommendation_evidence import (
    NextDrawRecommendationEvidenceArtifact,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog


class SealNextDrawRecommendationError(RuntimeError):
    """Base class for fail-closed sealing failures owned by this module."""


class SealEvidenceUnavailableError(SealNextDrawRecommendationError):
    """No Next-Draw Recommendation evidence artifact is configured to freeze."""


class SealEvidenceLotteryTypeMismatchError(SealNextDrawRecommendationError):
    """The configured evidence artifact does not cover the resolved target's lottery type."""


class SealCausalHistoryDriftError(SealNextDrawRecommendationError):
    """The causal history authority or bulk reader disagreed during generation."""


class SealSourceGitIdentityError(SealNextDrawRecommendationError):
    """The exact clean-worktree Git identity is unavailable, invalid, or drifted."""


class SealStoreCorruptionError(SealNextDrawRecommendationError):
    """The seal store returned an outcome its own contract does not allow."""


class SealOutcomeStatus(StrEnum):
    """Outcome of one explicit seal-command attempt for one lottery type."""

    NO_ELIGIBLE_TARGET = "NO_ELIGIBLE_TARGET"
    CREATED = "CREATED"
    IDEMPOTENT_EXISTING = "IDEMPOTENT_EXISTING"
    FAIL_CLOSED_CONFLICT = "FAIL_CLOSED_CONFLICT"


@dataclass(frozen=True, slots=True)
class SealNextDrawRecommendationResult:
    status: SealOutcomeStatus
    seal: NextDrawRecommendationSeal | None

    def __post_init__(self) -> None:
        if type(self.status) is not SealOutcomeStatus:
            raise ValueError("status must be a SealOutcomeStatus")
        has_seal = self.status in {SealOutcomeStatus.CREATED, SealOutcomeStatus.IDEMPOTENT_EXISTING}
        if has_seal != (self.seal is not None):
            raise ValueError("seal must be present exactly when the attempt produced one")


@runtime_checkable
class NextDrawRecommendationSealStore(Protocol):
    """Durable create-once boundary for accepted Next-Draw Recommendation seals."""

    def get_seal(self, target: ObservationTarget) -> NextDrawRecommendationSeal | None: ...

    def create_seal(self, seal: NextDrawRecommendationSeal) -> CreateOnceOutcome: ...


CausalHistoryRowsFactory = Callable[[LotteryType], tuple[CausalDrawRow, ...]]
EvidenceArtifactFactory = Callable[[], NextDrawRecommendationEvidenceArtifact | None]
SourceGitIdentityFactory = Callable[[], SourceGitIdentity]


class SealNextDrawRecommendation:
    """Resolve, freeze, and durably seal one lottery type's next-draw output."""

    def __init__(
        self,
        *,
        catalog: StrategyCatalog,
        operational_service: PreOutcomeTargetOperationalService,
        causal_history_authority: CausalHistoryAuthority,
        causal_history_rows_factory: CausalHistoryRowsFactory,
        evidence_factory: EvidenceArtifactFactory,
        source_git_identity_factory: SourceGitIdentityFactory,
        outcome_presence_probe: OutcomePresenceProbe,
        seal_store: NextDrawRecommendationSealStore,
        clock: Callable[[], datetime],
    ) -> None:
        self._catalog = catalog
        self._operational_service = operational_service
        self._causal_history_authority = causal_history_authority
        self._causal_history_rows_factory = causal_history_rows_factory
        self._evidence_factory = evidence_factory
        self._source_git_identity_factory = source_git_identity_factory
        self._outcome_presence_probe = outcome_presence_probe
        self._seal_store = seal_store
        self._clock = clock
        self._ticket_use_case = GenerateNextDrawTopTickets(catalog=catalog)

    def execute(self, lottery_type: LotteryType) -> SealNextDrawRecommendationResult:
        registration_result = self._operational_service.register_earliest(lottery_type)
        if registration_result.status in {
            OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT,
            OperationalRegistrationStatus.NO_REGISTERABLE_PRE_OUTCOME_TARGET,
        }:
            return SealNextDrawRecommendationResult(SealOutcomeStatus.NO_ELIGIBLE_TARGET, None)

        registration = registration_result.registration
        assert registration is not None  # completed statuses always carry a registration
        target = registration.target

        evidence = self._evidence_factory()
        if evidence is None:
            raise SealEvidenceUnavailableError(
                "no Next-Draw Recommendation evidence artifact is configured"
            )
        if evidence.lottery_type != target.lottery_type.value:
            # The target authority is multi-lottery (see
            # PreOutcomeTargetOperationalService); the configured evidence
            # factory may not be. Never silently freeze one lottery type's
            # target against another lottery type's backtest evidence.
            raise SealEvidenceLotteryTypeMismatchError(
                f"evidence artifact covers {evidence.lottery_type!r} but the resolved "
                f"target is {target.lottery_type.value!r}"
            )

        source_git_identity = self._resolve_source_git_identity()
        existing = self._seal_store.get_seal(target)
        if existing is not None:
            # "One seal per target": once any valid seal exists, never
            # regenerate or re-execute strategies. A strategy's generated
            # ticket numbers may legitimately differ run to run (some catalog
            # strategies are not reproducible), so idempotency is decided by
            # comparing frozen *inputs*, never by re-deriving and diffing
            # bucket/ticket bytes.
            if existing.matches_frozen_inputs(
                target=target,
                target_scheduled_at=registration.announcement.scheduled_at,
                source_head=source_git_identity.source_head,
                source_tree=source_git_identity.source_tree,
                target_registration_digest=registration.registration_digest,
                evidence_artifact_sha256=evidence.artifact_sha256,
                causal_history_sha256=registration.causal_history.history_sha256,
                causal_history_draw_count=registration.causal_history.draw_count,
            ):
                return SealNextDrawRecommendationResult(
                    SealOutcomeStatus.IDEMPOTENT_EXISTING, existing
                )
            return SealNextDrawRecommendationResult(SealOutcomeStatus.FAIL_CLOSED_CONFLICT, None)

        causal_rows = self._causal_history_rows_factory(lottery_type)
        filtered_rows = _rows_strictly_before(causal_rows, target)
        _require_history_consistency(filtered_rows, registration.causal_history)

        buckets = tuple(
            self._seal_one_bucket(
                lottery_type=lottery_type,
                native_ticket_count=native_ticket_count,
                evidence=evidence,
                causal_history_rows=filtered_rows,
            )
            for native_ticket_count in NATIVE_TICKET_COUNT_BUCKETS
        )

        seal = NextDrawRecommendationSeal.create(
            target=target,
            target_scheduled_at=registration.announcement.scheduled_at,
            sealed_at=self._clock(),
            source_head=source_git_identity.source_head,
            source_tree=source_git_identity.source_tree,
            target_registration_digest=registration.registration_digest,
            evidence_artifact_sha256=evidence.artifact_sha256,
            causal_history_sha256=registration.causal_history.history_sha256,
            causal_history_draw_count=registration.causal_history.draw_count,
            buckets=buckets,
        )

        self._require_fresh_final_gate(
            target=target,
            registration=registration,
            source_git_identity=source_git_identity,
        )

        outcome = self._seal_store.create_seal(seal)
        if outcome is CreateOnceOutcome.INSERTED:
            return SealNextDrawRecommendationResult(SealOutcomeStatus.CREATED, seal)
        if outcome in {CreateOnceOutcome.CONFLICT, CreateOnceOutcome.ALREADY_PRESENT}:
            # Lost a create-once race against a concurrent sealing attempt for
            # this exact target. Compare frozen *inputs* against the winner,
            # never raw bucket/ticket bytes -- see matches_frozen_inputs.
            persisted = self._seal_store.get_seal(target)
            if persisted is None:
                raise SealStoreCorruptionError(
                    "seal store reported an existing record without a persisted value"
                )
            if persisted.matches_frozen_inputs(
                target=seal.target,
                target_scheduled_at=seal.target_scheduled_at,
                source_head=seal.source_head,
                source_tree=seal.source_tree,
                target_registration_digest=seal.target_registration_digest,
                evidence_artifact_sha256=seal.evidence_artifact_sha256,
                causal_history_sha256=seal.causal_history_sha256,
                causal_history_draw_count=seal.causal_history_draw_count,
            ):
                return SealNextDrawRecommendationResult(
                    SealOutcomeStatus.IDEMPOTENT_EXISTING, persisted
                )
            return SealNextDrawRecommendationResult(SealOutcomeStatus.FAIL_CLOSED_CONFLICT, None)
        raise SealStoreCorruptionError(f"seal store returned an unsupported outcome: {outcome!r}")

    def _resolve_source_git_identity(self) -> SourceGitIdentity:
        identity = self._source_git_identity_factory()
        if type(identity) is not SourceGitIdentity:
            raise SealSourceGitIdentityError(
                "source Git identity resolver returned an unsupported value"
            )
        return identity

    def _seal_one_bucket(
        self,
        *,
        lottery_type: LotteryType,
        native_ticket_count: int,
        evidence: NextDrawRecommendationEvidenceArtifact,
        causal_history_rows: tuple[CausalDrawRow, ...],
    ) -> SealedRecommendationBucket:
        build_use_case = BuildNextDrawRecommendationBucket(catalog=self._catalog, evidence=evidence)
        view = build_use_case.execute(
            lottery_type=lottery_type, native_ticket_count=native_ticket_count
        )

        top_candidates = view.ranked[:TOP_N]
        top_ids = tuple(candidate.strategy_id for candidate in top_candidates)
        names_by_id = {
            candidate.strategy_id: candidate.strategy_name for candidate in top_candidates
        }
        ticket_sets = (
            self._ticket_use_case.execute(
                top_ids,
                lottery_type=lottery_type,
                causal_history=causal_history_rows,
            )
            if top_ids
            else ()
        )
        sealed_tickets = tuple(
            SealedStrategyTickets(
                rank=index + 1,
                strategy_id=ticket_set.strategy_id,
                strategy_name=names_by_id[ticket_set.strategy_id],
                status=TicketSealStatus(ticket_set.status.value),
                tickets=ticket_set.tickets,
                detail=ticket_set.detail,
            )
            for index, ticket_set in enumerate(ticket_sets)
        )
        return SealedRecommendationBucket(
            native_ticket_count=native_ticket_count,
            availability=view.availability.value,
            total_candidate_count=view.total_candidate_count,
            ranked_strategy_ids=tuple(candidate.strategy_id for candidate in view.ranked),
            ranking_projection_sha256=_ranking_projection_sha256(view),
            sealed_tickets=sealed_tickets,
        )

    def _require_fresh_final_gate(
        self,
        *,
        target: ObservationTarget,
        registration: PreOutcomeTargetRegistration,
        source_git_identity: SourceGitIdentity,
    ) -> None:
        """Re-verify source, absence, pre-draw window, and history before accept.

        Bucket/ticket generation across every supported ticket count can take
        real wall-clock time; this closes the window where the outcome became
        available, the schedule passed, or new draws landed *during*
        generation -- never trusting the registration-time checks alone.
        """

        fresh_source_git_identity = self._resolve_source_git_identity()
        if fresh_source_git_identity != source_git_identity:
            raise SealSourceGitIdentityError(
                "source Git HEAD/tree changed while generating sealed buckets"
            )

        fresh_history = self._causal_history_authority.resolve(target)
        if fresh_history != registration.causal_history:
            raise SealCausalHistoryDriftError(
                "canonical causal history changed while generating sealed buckets"
            )

        now = self._clock()
        _require_utc(now)
        if now >= registration.announcement.scheduled_at:
            raise InvalidScheduleTimeError(
                "the announced schedule elapsed while generating sealed buckets"
            )

        # The registration's own probe already proved ABSENT at registration
        # time; re-probe now (read-only) so an outcome that landed mid-
        # generation still fails the seal closed rather than sealing a stale
        # absence claim.
        attestation = self._outcome_presence_probe.probe(target, as_of=now)
        if attestation.presence is OutcomePresenceAtPrediction.PRESENT:
            raise OutcomeAlreadyAvailableError(
                "official outcome became available while generating sealed buckets"
            )


def _require_utc(value: datetime) -> None:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise SealNextDrawRecommendationError(
            "the sealing clock must return a timezone-aware UTC datetime"
        )


def _rows_strictly_before(
    rows: tuple[CausalDrawRow, ...], target: ObservationTarget
) -> tuple[CausalDrawRow, ...]:
    target_key = (target.draw_date.isoformat(), int(target.draw_number))
    return tuple(row for row in rows if (row.date, int(row.draw)) < target_key)


def _require_history_consistency(
    filtered_rows: tuple[CausalDrawRow, ...],
    causal_history: CausalHistoryRef,
) -> None:
    if len(filtered_rows) != causal_history.draw_count:
        raise SealCausalHistoryDriftError(
            "bulk causal history row count does not match the registered causal-history authority"
        )
    if filtered_rows:
        last = filtered_rows[-1]
        if last.draw != causal_history.last_draw_number or last.date != (
            causal_history.last_draw_date.isoformat() if causal_history.last_draw_date else None
        ):
            raise SealCausalHistoryDriftError(
                "bulk causal history's last draw does not match the registered "
                "causal-history authority"
            )


def _fraction_pair(value: Fraction | None) -> dict[str, str] | None:
    return (
        None
        if value is None
        else {"numerator": str(value.numerator), "denominator": str(value.denominator)}
    )


def _ranking_projection_material(view: RecommendationBucketView) -> dict[str, object]:
    return {
        "availability": view.availability.value,
        "excluded": [
            {
                "detail": exclusion.detail,
                "reason": exclusion.reason.value,
                "strategy_id": exclusion.strategy_id,
            }
            for exclusion in view.excluded
        ],
        "native_ticket_count": view.native_ticket_count,
        "ranked": [
            {
                "cross_window_rank_sum": candidate.cross_window_rank_sum,
                "rank": candidate.rank,
                "strategy_id": candidate.strategy_id,
                "strategy_name": candidate.strategy_name,
                "windows": [
                    {
                        "delta_vs_random": _fraction_pair(window.delta_vs_random),
                        "eligible_draw_count": window.eligible_draw_count,
                        "observed_rate": _fraction_pair(window.observed_rate),
                        "random_baseline_rate": _fraction_pair(window.random_baseline_rate),
                        "window_complete": window.window_complete,
                        "window_kind": window.window_kind,
                    }
                    for window in candidate.windows
                ],
            }
            for candidate in view.ranked
        ],
        "total_candidate_count": view.total_candidate_count,
    }


def _ranking_projection_sha256(view: RecommendationBucketView) -> str:
    encoded = json.dumps(
        _ranking_projection_material(view),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "CausalHistoryRowsFactory",
    "EvidenceArtifactFactory",
    "InvalidScheduleTimeError",
    "NextDrawRecommendationSealStore",
    "OutcomeAlreadyAvailableError",
    "SealCausalHistoryDriftError",
    "SealEvidenceLotteryTypeMismatchError",
    "SealEvidenceUnavailableError",
    "SealNextDrawRecommendation",
    "SealNextDrawRecommendationError",
    "SealNextDrawRecommendationResult",
    "SealOutcomeStatus",
    "SealSourceGitIdentityError",
    "SealStoreCorruptionError",
    "SourceGitIdentityFactory",
]
