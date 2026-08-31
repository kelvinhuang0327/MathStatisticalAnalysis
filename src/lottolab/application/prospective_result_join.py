"""Stage E exact prediction-outcome result join composition.

This module binds an immutable Stage C sealed prediction record to its exact
canonical official outcome loaded from an official draw repository, executes
deterministic prize/diagnostic scoring via :class:`ScoringPhaseService`, and
persists canonical score records into :class:`ProspectiveObservationStore`.

Exact join identity is strictly (lottery_type, draw_number, draw_date).
Date-only, fuzzy, or cross-game joins are strictly rejected and fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from lottolab.application.draw_data import DrawRecord
from lottolab.application.prospective_observer import (
    PredictionRequiredError,
    ProducerFingerprintDriftError,
    ProspectiveObservationStore,
    ScorePhaseRequest,
    ScoreSyncStatus,
    ScoringPhaseService,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    OfficialOutcome,
    PredictionRecord,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ScoreRecord,
)


class ProspectiveResultJoinError(RuntimeError):
    """Base class for fail-closed prospective result-join errors."""


@runtime_checkable
class OfficialDrawReader(Protocol):
    """Read a recorded official draw by lottery type and draw number."""

    def find(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None: ...


def official_outcome_from_draw_record(
    draw: DrawRecord,
    *,
    source_id: str | None = None,
    source_sha256: str | None = None,
) -> OfficialOutcome:
    """Build canonical OfficialOutcome from a validated DrawRecord.

    Preserves exact official lottery type, draw number, draw date, main numbers,
    and special numbers according to the canonical OfficialOutcome contract.
    """
    if type(draw) is not DrawRecord:
        raise ValueError("draw must be a DrawRecord")

    special_number: int | None
    if draw.lottery_type is LotteryType.DAILY_539:
        # DAILY_539 has no special-number semantics; if any number is present,
        # pass it through so that game contract validation fails closed.
        special_number = draw.special_numbers[0] if draw.special_numbers else None
    elif draw.lottery_type in {LotteryType.POWER_LOTTO, LotteryType.BIG_LOTTO}:
        if len(draw.special_numbers) == 1:
            special_number = draw.special_numbers[0]
        elif len(draw.special_numbers) == 0:
            special_number = None
        else:
            special_number = draw.special_numbers[0]
    else:
        special_number = draw.special_numbers[0] if draw.special_numbers else None

    resolved_source_id = (
        source_id or draw.source_name or draw.source_reference or draw.ingestion_run_id
    )
    resolved_source_sha256 = source_sha256 or draw.normalized_record_hash

    return OfficialOutcome.create(
        lottery_type=draw.lottery_type,
        draw_number=draw.draw_number,
        draw_date=draw.draw_date,
        main_numbers=draw.main_numbers,
        special_number=special_number,
        source_id=resolved_source_id,
        source_sha256=resolved_source_sha256,
    )


class ProspectiveResultJoinStatus(StrEnum):
    CREATED = "CREATED"
    EXACT_IDEMPOTENT_NO_OP = "EXACT_IDEMPOTENT_NO_OP"
    OUTCOME_UNAVAILABLE = "OUTCOME_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ProspectiveResultJoinResult:
    """Immutable outcome of one prospective result join attempt."""

    status: ProspectiveResultJoinStatus
    lottery_type: LotteryType
    identity: ProspectiveObservationIdentity
    outcome: OfficialOutcome | None
    score: ScoreRecord | None

    def __post_init__(self) -> None:
        if type(self.status) is not ProspectiveResultJoinStatus:
            raise ValueError("status must be a ProspectiveResultJoinStatus")
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.identity) is not ProspectiveObservationIdentity:
            raise ValueError("identity must be a ProspectiveObservationIdentity")
        if self.identity.lottery_type is not self.lottery_type:
            raise ValueError("identity lottery type does not match result lottery type")
        completed = self.status in {
            ProspectiveResultJoinStatus.CREATED,
            ProspectiveResultJoinStatus.EXACT_IDEMPOTENT_NO_OP,
        }
        if completed:
            if type(self.outcome) is not OfficialOutcome or type(self.score) is not ScoreRecord:
                raise ValueError("completed result join requires an outcome and score")
            if self.outcome.lottery_type is not self.lottery_type:
                raise ValueError("outcome lottery type does not match result lottery type")
            if self.score.identity != self.identity:
                raise ValueError("score identity does not match result identity")
        else:
            if self.outcome is not None or self.score is not None:
                raise ValueError("unavailable outcome result must not expose outcome or score")


@dataclass(frozen=True, slots=True)
class ProspectiveResultJoinService:
    """Exact Stage E prediction-outcome result join application service.

    Joins strictly on (lottery_type, draw_number, draw_date) without fuzzy matching,
    date-only joins, or cross-game contamination.  Fails closed on any identity mismatch,
    contract violation, or producer fingerprint drift.
    """

    draw_reader: OfficialDrawReader
    scoring_service: ScoringPhaseService
    store: ProspectiveObservationStore

    def join_result(
        self,
        identity: ProspectiveObservationIdentity,
        producer_fingerprint: ProducerFingerprint,
        *,
        source_id: str | None = None,
        source_sha256: str | None = None,
    ) -> ProspectiveResultJoinResult:
        """Join one sealed prediction with its exact canonical official outcome."""
        if type(identity) is not ProspectiveObservationIdentity:
            raise ValueError("identity must be a ProspectiveObservationIdentity")
        if type(producer_fingerprint) is not ProducerFingerprint:
            raise ValueError("producer_fingerprint must be a ProducerFingerprint")

        prediction = self.store.get_prediction(identity)
        if prediction is None:
            raise PredictionRequiredError("score requires an immutable prediction")
        if prediction.producer_fingerprint != producer_fingerprint:
            raise ProducerFingerprintDriftError(
                "producer fingerprint differs from immutable prediction authority"
            )

        draw = self.draw_reader.find(identity.lottery_type, identity.target_draw_number)
        if draw is None:
            self.scoring_service.sync(
                ScorePhaseRequest(
                    identity=identity,
                    producer_fingerprint=producer_fingerprint,
                    outcome=None,
                )
            )
            return ProspectiveResultJoinResult(
                status=ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE,
                lottery_type=identity.lottery_type,
                identity=identity,
                outcome=None,
                score=None,
            )

        if (
            draw.lottery_type is not identity.lottery_type
            or draw.draw_number != identity.target_draw_number
            or draw.draw_date != identity.target_draw_date
        ):
            from lottolab.application.prospective_observer import GameContractError

            expected_desc = (
                f"{identity.lottery_type.value} #{identity.target_draw_number} "
                f"on {identity.target_draw_date}"
            )
            actual_desc = f"{draw.lottery_type.value} #{draw.draw_number} on {draw.draw_date}"
            raise GameContractError(
                f"official draw identity does not match prediction "
                f"(expected {expected_desc}, got {actual_desc})"
            )

        outcome = official_outcome_from_draw_record(
            draw,
            source_id=source_id,
            source_sha256=source_sha256,
        )

        score_result = self.scoring_service.sync(
            ScorePhaseRequest(
                identity=identity,
                producer_fingerprint=producer_fingerprint,
                outcome=outcome,
            )
        )

        if score_result.status is ScoreSyncStatus.CREATED:
            status = ProspectiveResultJoinStatus.CREATED
        elif score_result.status is ScoreSyncStatus.EXACT_IDEMPOTENT_NO_OP:
            status = ProspectiveResultJoinStatus.EXACT_IDEMPOTENT_NO_OP
        else:
            raise RuntimeError(f"unsupported score sync status: {score_result.status!r}")

        return ProspectiveResultJoinResult(
            status=status,
            lottery_type=identity.lottery_type,
            identity=identity,
            outcome=outcome,
            score=score_result.score,
        )

    def join_prediction(
        self,
        prediction: PredictionRecord,
        *,
        source_id: str | None = None,
        source_sha256: str | None = None,
    ) -> ProspectiveResultJoinResult:
        """Join from an existing PredictionRecord instance."""
        if type(prediction) is not PredictionRecord:
            raise ValueError("prediction must be a PredictionRecord")
        return self.join_result(
            prediction.identity,
            prediction.producer_fingerprint,
            source_id=source_id,
            source_sha256=source_sha256,
        )


__all__ = [
    "OfficialDrawReader",
    "ProspectiveResultJoinError",
    "ProspectiveResultJoinResult",
    "ProspectiveResultJoinService",
    "ProspectiveResultJoinStatus",
    "official_outcome_from_draw_record",
]
