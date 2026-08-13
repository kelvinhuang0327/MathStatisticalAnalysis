"""Immutable contracts for prospective prediction and later outcome scoring.

The prediction-side types deliberately contain no official outcome payload.  A
consumer can therefore run :class:`PredictionContext` in an isolated Phase A
process and pass only the resulting immutable record to the scoring process.
Lottery-specific validation and prize semantics remain application ports; this
module owns only shared identity, hashing, lifecycle, and checkpoint accounting.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import PrizeEvaluationResult

PRODUCER_FINGERPRINT_SCHEMA_VERSION = "1.0.0"
PREDICTION_SCHEMA_VERSION = "1.0.0"
OUTCOME_SCHEMA_VERSION = "1.0.0"
SCORE_SCHEMA_VERSION = "1.0.0"

_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty string")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{label} must use UTC")


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


class OutcomePresenceAtPrediction(StrEnum):
    """Presence-only Phase A metadata; never outcome numbers or an outcome hash."""

    ABSENT = "ABSENT"
    PRESENT = "PRESENT"


class TemporalProvenance(StrEnum):
    PRE_FREEZE_DATE_UNSEEN_HOLDOUT = "PRE_FREEZE_DATE_UNSEEN_HOLDOUT"
    POST_FREEZE_DATE_PROSPECTIVE = "POST_FREEZE_DATE_PROSPECTIVE"
    POST_FREEZE_DATE_RETROSPECTIVE_AVAILABLE_OUTCOME = (
        "POST_FREEZE_DATE_RETROSPECTIVE_AVAILABLE_OUTCOME"
    )
    FREEZE_DATE_NON_PROSPECTIVE_AMBIGUOUS = "FREEZE_DATE_NON_PROSPECTIVE_AMBIGUOUS"


class PredictionAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ScoreAvailability(StrEnum):
    SCORED = "SCORED"
    UNAVAILABLE_PREDICTION = "UNAVAILABLE_PREDICTION"


class CreateOnceOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class ProducerDependency:
    """One consumer-declared behavior-authority dependency."""

    locator: str
    source_sha256: str
    load_bearing_role: str

    def __post_init__(self) -> None:
        _require_text(self.locator, "locator")
        _require_sha256(self.source_sha256, "source_sha256")
        _require_text(self.load_bearing_role, "load_bearing_role")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "load_bearing_role": self.load_bearing_role,
            "locator": self.locator,
            "source_sha256": self.source_sha256,
        }


@dataclass(frozen=True, slots=True)
class ProducerFingerprint:
    """Closed, self-verifying manifest supplied by a prediction consumer.

    The generic core validates the manifest and its digest but never discovers
    or hardcodes a producer's dependency closure.
    """

    schema_version: str
    producer_id: str
    producer_version: str
    dependencies: tuple[ProducerDependency, ...]
    digest: str

    def __post_init__(self) -> None:
        if self.schema_version != PRODUCER_FINGERPRINT_SCHEMA_VERSION:
            raise ValueError("unsupported producer fingerprint schema_version")
        _require_text(self.producer_id, "producer_id")
        _require_text(self.producer_version, "producer_version")
        if type(self.dependencies) is not tuple or not self.dependencies:
            raise ValueError("dependencies must be a non-empty tuple")
        if any(type(item) is not ProducerDependency for item in self.dependencies):
            raise ValueError("dependencies must contain ProducerDependency values")
        locators = tuple(item.locator for item in self.dependencies)
        if locators != tuple(sorted(locators)) or len(locators) != len(set(locators)):
            raise ValueError("dependencies must be unique and sorted by locator")
        _require_sha256(self.digest, "digest")
        if self.digest != _canonical_sha256(self.canonical_material()):
            raise ValueError("digest does not match the producer fingerprint manifest")

    @classmethod
    def create(
        cls,
        *,
        producer_id: str,
        producer_version: str,
        dependencies: tuple[ProducerDependency, ...],
    ) -> ProducerFingerprint:
        ordered = tuple(sorted(dependencies, key=lambda item: item.locator))
        material: dict[str, object] = {
            "dependencies": [item.canonical_dict() for item in ordered],
            "producer_id": producer_id,
            "producer_version": producer_version,
            "schema_version": PRODUCER_FINGERPRINT_SCHEMA_VERSION,
        }
        return cls(
            schema_version=PRODUCER_FINGERPRINT_SCHEMA_VERSION,
            producer_id=producer_id,
            producer_version=producer_version,
            dependencies=ordered,
            digest=_canonical_sha256(material),
        )

    def canonical_material(self) -> dict[str, object]:
        return {
            "dependencies": [item.canonical_dict() for item in self.dependencies],
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "schema_version": self.schema_version,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "digest": self.digest}


@dataclass(frozen=True, slots=True)
class ObservationTarget:
    """Outcome-free target identity passed to the prediction process."""

    lottery_type: LotteryType
    draw_number: str
    draw_date: date

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.draw_number) is not str or _DRAW_NUMBER.fullmatch(self.draw_number) is None:
            raise ValueError("draw_number must contain 1-32 ASCII decimal digits")
        if type(self.draw_date) is not date:
            raise ValueError("draw_date must be a date")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_date": self.draw_date.isoformat(),
            "draw_number": self.draw_number,
            "lottery_type": self.lottery_type.value,
        }


@dataclass(frozen=True, slots=True)
class CausalHistoryRef:
    """Hash identity for history known strictly before a target."""

    draw_count: int
    last_draw_number: str | None
    last_draw_date: date | None
    history_sha256: str

    def __post_init__(self) -> None:
        if type(self.draw_count) is not int or self.draw_count < 0:
            raise ValueError("draw_count must be a non-negative exact integer")
        _require_sha256(self.history_sha256, "history_sha256")
        if self.draw_count == 0:
            if self.last_draw_number is not None or self.last_draw_date is not None:
                raise ValueError("empty history must not carry a last draw")
        else:
            if (
                type(self.last_draw_number) is not str
                or _DRAW_NUMBER.fullmatch(self.last_draw_number) is None
                or type(self.last_draw_date) is not date
            ):
                raise ValueError("non-empty history requires a canonical last draw identity")

    def validate_against(self, target: ObservationTarget) -> None:
        if self.draw_count == 0:
            return
        assert self.last_draw_number is not None
        assert self.last_draw_date is not None
        if (self.last_draw_date, int(self.last_draw_number)) >= (
            target.draw_date,
            int(target.draw_number),
        ):
            raise ValueError("causal history must end strictly before the target")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_count": self.draw_count,
            "history_sha256": self.history_sha256,
            "last_draw_date": self.last_draw_date.isoformat() if self.last_draw_date else None,
            "last_draw_number": self.last_draw_number,
        }


@dataclass(frozen=True, slots=True)
class MatchedBaselineRef:
    """Opaque game-owned baseline identity with shape-matching evidence."""

    lottery_type: LotteryType
    baseline_id: str
    baseline_version: str
    authority_sha256: str
    ticket_count: int
    candidate_sizes: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        _require_text(self.baseline_id, "baseline_id")
        _require_text(self.baseline_version, "baseline_version")
        _require_sha256(self.authority_sha256, "authority_sha256")
        if type(self.ticket_count) is not int or self.ticket_count <= 0:
            raise ValueError("ticket_count must be a positive exact integer")
        if (
            type(self.candidate_sizes) is not tuple
            or len(self.candidate_sizes) != self.ticket_count
            or any(type(size) is not int or size <= 0 for size in self.candidate_sizes)
        ):
            raise ValueError("candidate_sizes must contain one positive size per ticket")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "authority_sha256": self.authority_sha256,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "candidate_sizes": list(self.candidate_sizes),
            "lottery_type": self.lottery_type.value,
            "ticket_count": self.ticket_count,
        }


@dataclass(frozen=True, slots=True)
class FrozenCohortRef:
    """Immutable per-lottery cohort and its configured checkpoint policy."""

    lottery_type: LotteryType
    cohort_id: str
    cohort_version: str
    authority_sha256: str
    frozen_at: datetime
    member_ids: tuple[str, ...]
    checkpoint_sizes: tuple[int, ...]
    checkpoint_provenance: tuple[TemporalProvenance, ...]

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        _require_text(self.cohort_id, "cohort_id")
        _require_text(self.cohort_version, "cohort_version")
        _require_sha256(self.authority_sha256, "authority_sha256")
        _require_utc(self.frozen_at, "frozen_at")
        if (
            type(self.member_ids) is not tuple
            or not self.member_ids
            or any(type(member_id) is not str or not member_id for member_id in self.member_ids)
            or len(self.member_ids) != len(set(self.member_ids))
        ):
            raise ValueError("member_ids must be a non-empty tuple of unique identifiers")
        if (
            type(self.checkpoint_sizes) is not tuple
            or not self.checkpoint_sizes
            or any(type(size) is not int or size <= 0 for size in self.checkpoint_sizes)
            or self.checkpoint_sizes != tuple(sorted(set(self.checkpoint_sizes)))
        ):
            raise ValueError("checkpoint_sizes must be strictly increasing positive integers")
        if (
            type(self.checkpoint_provenance) is not tuple
            or not self.checkpoint_provenance
            or any(type(item) is not TemporalProvenance for item in self.checkpoint_provenance)
            or len(self.checkpoint_provenance) != len(set(self.checkpoint_provenance))
        ):
            raise ValueError("checkpoint_provenance must contain unique TemporalProvenance values")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "authority_sha256": self.authority_sha256,
            "checkpoint_provenance": [item.value for item in self.checkpoint_provenance],
            "checkpoint_sizes": list(self.checkpoint_sizes),
            "cohort_id": self.cohort_id,
            "cohort_version": self.cohort_version,
            "frozen_at": _utc_text(self.frozen_at),
            "lottery_type": self.lottery_type.value,
            "member_ids": list(self.member_ids),
        }


@dataclass(frozen=True, slots=True)
class ProspectiveObservationIdentity:
    lottery_type: LotteryType
    cohort_id: str
    cohort_version: str
    target_draw_number: str
    target_draw_date: date

    @classmethod
    def from_context(cls, context: PredictionContext) -> ProspectiveObservationIdentity:
        return cls(
            lottery_type=context.target.lottery_type,
            cohort_id=context.cohort.cohort_id,
            cohort_version=context.cohort.cohort_version,
            target_draw_number=context.target.draw_number,
            target_draw_date=context.target.draw_date,
        )

    def __post_init__(self) -> None:
        ObservationTarget(
            lottery_type=self.lottery_type,
            draw_number=self.target_draw_number,
            draw_date=self.target_draw_date,
        )
        _require_text(self.cohort_id, "cohort_id")
        _require_text(self.cohort_version, "cohort_version")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cohort_id": self.cohort_id,
            "cohort_version": self.cohort_version,
            "lottery_type": self.lottery_type.value,
            "target_draw_date": self.target_draw_date.isoformat(),
            "target_draw_number": self.target_draw_number,
        }


@dataclass(frozen=True, slots=True)
class ProspectiveSelection:
    """Game-native ticket or candidate shape interpreted only by a game contract."""

    main_numbers: tuple[int, ...]
    special_number: int | None = None

    def __post_init__(self) -> None:
        if (
            type(self.main_numbers) is not tuple
            or not self.main_numbers
            or any(type(number) is not int or number <= 0 for number in self.main_numbers)
            or self.main_numbers != tuple(sorted(self.main_numbers))
            or len(self.main_numbers) != len(set(self.main_numbers))
        ):
            raise ValueError("main_numbers must be unique positive integers in ascending order")
        if self.special_number is not None and (
            type(self.special_number) is not int or self.special_number <= 0
        ):
            raise ValueError("special_number must be a positive exact integer or None")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "main_numbers": list(self.main_numbers),
            "special_number": self.special_number,
        }


@dataclass(frozen=True, slots=True)
class PredictionEntryDraft:
    member_id: str
    availability: PredictionAvailability
    selections: tuple[ProspectiveSelection, ...]
    matched_baseline: MatchedBaselineRef | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        _require_text(self.member_id, "member_id")
        if type(self.availability) is not PredictionAvailability:
            raise ValueError("availability must be a PredictionAvailability")
        if type(self.selections) is not tuple or any(
            type(selection) is not ProspectiveSelection for selection in self.selections
        ):
            raise ValueError("selections must contain ProspectiveSelection values")
        if self.availability is PredictionAvailability.AVAILABLE:
            if not self.selections or self.matched_baseline is None:
                raise ValueError("AVAILABLE requires selections and a matched baseline")
            if self.unavailable_reason is not None:
                raise ValueError("AVAILABLE must not carry an unavailable_reason")
            expected_sizes = tuple(len(selection.main_numbers) for selection in self.selections)
            if (
                self.matched_baseline.ticket_count != len(self.selections)
                or self.matched_baseline.candidate_sizes != expected_sizes
            ):
                raise ValueError("matched baseline must match ticket count and candidate sizes")
        else:
            if self.selections or self.matched_baseline is not None:
                raise ValueError("UNAVAILABLE must not carry selections or a baseline")
            _require_text(self.unavailable_reason, "unavailable_reason")

    @classmethod
    def available(
        cls,
        *,
        member_id: str,
        selections: tuple[ProspectiveSelection, ...],
        matched_baseline: MatchedBaselineRef,
    ) -> PredictionEntryDraft:
        return cls(
            member_id=member_id,
            availability=PredictionAvailability.AVAILABLE,
            selections=selections,
            matched_baseline=matched_baseline,
            unavailable_reason=None,
        )

    @classmethod
    def unavailable(cls, *, member_id: str, reason: str) -> PredictionEntryDraft:
        return cls(
            member_id=member_id,
            availability=PredictionAvailability.UNAVAILABLE,
            selections=(),
            matched_baseline=None,
            unavailable_reason=reason,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability.value,
            "matched_baseline": (
                self.matched_baseline.canonical_dict() if self.matched_baseline else None
            ),
            "member_id": self.member_id,
            "selections": [selection.canonical_dict() for selection in self.selections],
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class PredictionDraft:
    entries: tuple[PredictionEntryDraft, ...]

    def __post_init__(self) -> None:
        if type(self.entries) is not tuple or not self.entries or any(
            type(entry) is not PredictionEntryDraft for entry in self.entries
        ):
            raise ValueError("entries must be a non-empty tuple of PredictionEntryDraft values")
        member_ids = tuple(entry.member_id for entry in self.entries)
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("entries contain duplicate member_id values")


@dataclass(frozen=True, slots=True)
class PredictionContext:
    """The complete and deliberately outcome-free input to a producer."""

    target: ObservationTarget
    cohort: FrozenCohortRef
    producer_fingerprint: ProducerFingerprint
    causal_history: CausalHistoryRef

    def __post_init__(self) -> None:
        if type(self.target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        if type(self.cohort) is not FrozenCohortRef:
            raise ValueError("cohort must be a FrozenCohortRef")
        if type(self.producer_fingerprint) is not ProducerFingerprint:
            raise ValueError("producer_fingerprint must be a ProducerFingerprint")
        if type(self.causal_history) is not CausalHistoryRef:
            raise ValueError("causal_history must be a CausalHistoryRef")
        if self.target.lottery_type is not self.cohort.lottery_type:
            raise ValueError("target and cohort lottery types differ")
        self.causal_history.validate_against(self.target)


@dataclass(frozen=True, slots=True)
class PredictionPhaseRequest:
    context: PredictionContext
    outcome_presence_at_start: OutcomePresenceAtPrediction

    def __post_init__(self) -> None:
        if type(self.context) is not PredictionContext:
            raise ValueError("context must be a PredictionContext")
        if type(self.outcome_presence_at_start) is not OutcomePresenceAtPrediction:
            raise ValueError("outcome_presence_at_start must be presence-only metadata")


def classify_temporal_provenance(
    *,
    target_date: date,
    frozen_at: datetime,
    outcome_presence: OutcomePresenceAtPrediction,
) -> TemporalProvenance:
    freeze_date = frozen_at.date()
    if target_date < freeze_date:
        return TemporalProvenance.PRE_FREEZE_DATE_UNSEEN_HOLDOUT
    if target_date > freeze_date and outcome_presence is OutcomePresenceAtPrediction.ABSENT:
        return TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE
    if target_date > freeze_date:
        return TemporalProvenance.POST_FREEZE_DATE_RETROSPECTIVE_AVAILABLE_OUTCOME
    return TemporalProvenance.FREEZE_DATE_NON_PROSPECTIVE_AMBIGUOUS


@dataclass(frozen=True, slots=True)
class PredictionEntry:
    member_id: str
    availability: PredictionAvailability
    selections: tuple[ProspectiveSelection, ...]
    matched_baseline: MatchedBaselineRef | None
    unavailable_reason: str | None
    prediction_hash: str

    @classmethod
    def from_draft(cls, draft: PredictionEntryDraft) -> PredictionEntry:
        material = draft.canonical_dict()
        return cls(
            member_id=draft.member_id,
            availability=draft.availability,
            selections=draft.selections,
            matched_baseline=draft.matched_baseline,
            unavailable_reason=draft.unavailable_reason,
            prediction_hash=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        draft = PredictionEntryDraft(
            member_id=self.member_id,
            availability=self.availability,
            selections=self.selections,
            matched_baseline=self.matched_baseline,
            unavailable_reason=self.unavailable_reason,
        )
        _require_sha256(self.prediction_hash, "prediction_hash")
        if self.prediction_hash != _canonical_sha256(draft.canonical_dict()):
            raise ValueError("prediction_hash does not match prediction entry content")

    def canonical_dict(self) -> dict[str, object]:
        draft = PredictionEntryDraft(
            member_id=self.member_id,
            availability=self.availability,
            selections=self.selections,
            matched_baseline=self.matched_baseline,
            unavailable_reason=self.unavailable_reason,
        )
        return {**draft.canonical_dict(), "prediction_hash": self.prediction_hash}


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    schema_version: str
    identity: ProspectiveObservationIdentity
    cohort: FrozenCohortRef
    producer_fingerprint: ProducerFingerprint
    causal_history: CausalHistoryRef
    outcome_presence_at_start: OutcomePresenceAtPrediction
    temporal_provenance: TemporalProvenance
    predicted_at: datetime
    entries: tuple[PredictionEntry, ...]
    prediction_hash: str

    @classmethod
    def create(
        cls,
        *,
        request: PredictionPhaseRequest,
        draft: PredictionDraft,
        predicted_at: datetime,
    ) -> PredictionRecord:
        context = request.context
        member_ids = tuple(entry.member_id for entry in draft.entries)
        if member_ids != context.cohort.member_ids:
            raise ValueError("prediction entries must exactly match frozen cohort membership")
        entries = tuple(PredictionEntry.from_draft(entry) for entry in draft.entries)
        identity = ProspectiveObservationIdentity.from_context(context)
        provenance = classify_temporal_provenance(
            target_date=context.target.draw_date,
            frozen_at=context.cohort.frozen_at,
            outcome_presence=request.outcome_presence_at_start,
        )
        material = _prediction_material(
            schema_version=PREDICTION_SCHEMA_VERSION,
            identity=identity,
            cohort=context.cohort,
            producer_fingerprint=context.producer_fingerprint,
            causal_history=context.causal_history,
            outcome_presence_at_start=request.outcome_presence_at_start,
            temporal_provenance=provenance,
            entries=entries,
        )
        return cls(
            schema_version=PREDICTION_SCHEMA_VERSION,
            identity=identity,
            cohort=context.cohort,
            producer_fingerprint=context.producer_fingerprint,
            causal_history=context.causal_history,
            outcome_presence_at_start=request.outcome_presence_at_start,
            temporal_provenance=provenance,
            predicted_at=predicted_at,
            entries=entries,
            prediction_hash=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.schema_version != PREDICTION_SCHEMA_VERSION:
            raise ValueError("unsupported prediction schema_version")
        if type(self.identity) is not ProspectiveObservationIdentity:
            raise ValueError("identity must be a ProspectiveObservationIdentity")
        if type(self.cohort) is not FrozenCohortRef:
            raise ValueError("cohort must be a FrozenCohortRef")
        if type(self.producer_fingerprint) is not ProducerFingerprint:
            raise ValueError("producer_fingerprint must be a ProducerFingerprint")
        if type(self.causal_history) is not CausalHistoryRef:
            raise ValueError("causal_history must be a CausalHistoryRef")
        if type(self.outcome_presence_at_start) is not OutcomePresenceAtPrediction:
            raise ValueError("outcome_presence_at_start must be presence-only metadata")
        if self.identity.lottery_type is not self.cohort.lottery_type:
            raise ValueError("identity and cohort lottery types differ")
        if (
            self.identity.cohort_id != self.cohort.cohort_id
            or self.identity.cohort_version != self.cohort.cohort_version
        ):
            raise ValueError("identity and cohort references differ")
        _require_utc(self.predicted_at, "predicted_at")
        if type(self.temporal_provenance) is not TemporalProvenance:
            raise ValueError("temporal_provenance must be a TemporalProvenance")
        if type(self.entries) is not tuple or any(
            type(entry) is not PredictionEntry for entry in self.entries
        ):
            raise ValueError("entries must contain PredictionEntry values")
        member_ids = tuple(entry.member_id for entry in self.entries)
        if member_ids != self.cohort.member_ids:
            raise ValueError("prediction entries must exactly match frozen cohort membership")
        _require_sha256(self.prediction_hash, "prediction_hash")
        if self.prediction_hash != _canonical_sha256(self.canonical_material()):
            raise ValueError("prediction_hash does not match prediction record content")

    def canonical_material(self) -> dict[str, object]:
        return _prediction_material(
            schema_version=self.schema_version,
            identity=self.identity,
            cohort=self.cohort,
            producer_fingerprint=self.producer_fingerprint,
            causal_history=self.causal_history,
            outcome_presence_at_start=self.outcome_presence_at_start,
            temporal_provenance=self.temporal_provenance,
            entries=self.entries,
        )


def _prediction_material(
    *,
    schema_version: str,
    identity: ProspectiveObservationIdentity,
    cohort: FrozenCohortRef,
    producer_fingerprint: ProducerFingerprint,
    causal_history: CausalHistoryRef,
    outcome_presence_at_start: OutcomePresenceAtPrediction,
    temporal_provenance: TemporalProvenance,
    entries: tuple[PredictionEntry, ...],
) -> dict[str, object]:
    return {
        "causal_history": causal_history.canonical_dict(),
        "cohort": cohort.canonical_dict(),
        "entries": [entry.canonical_dict() for entry in entries],
        "identity": identity.canonical_dict(),
        "outcome_presence_at_start": outcome_presence_at_start.value,
        "producer_fingerprint": producer_fingerprint.canonical_dict(),
        "schema_version": schema_version,
        "temporal_provenance": temporal_provenance.value,
    }


@dataclass(frozen=True, slots=True)
class OfficialOutcome:
    """Phase B only: immutable game-native official outcome and source identity."""

    schema_version: str
    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int | None
    source_id: str
    source_sha256: str
    outcome_hash: str

    @classmethod
    def create(
        cls,
        *,
        lottery_type: LotteryType,
        draw_number: str,
        draw_date: date,
        main_numbers: tuple[int, ...],
        special_number: int | None,
        source_id: str,
        source_sha256: str,
    ) -> OfficialOutcome:
        material = _outcome_material(
            schema_version=OUTCOME_SCHEMA_VERSION,
            lottery_type=lottery_type,
            draw_number=draw_number,
            draw_date=draw_date,
            main_numbers=main_numbers,
            special_number=special_number,
            source_id=source_id,
            source_sha256=source_sha256,
        )
        return cls(
            schema_version=OUTCOME_SCHEMA_VERSION,
            lottery_type=lottery_type,
            draw_number=draw_number,
            draw_date=draw_date,
            main_numbers=main_numbers,
            special_number=special_number,
            source_id=source_id,
            source_sha256=source_sha256,
            outcome_hash=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.schema_version != OUTCOME_SCHEMA_VERSION:
            raise ValueError("unsupported outcome schema_version")
        ObservationTarget(self.lottery_type, self.draw_number, self.draw_date)
        if (
            type(self.main_numbers) is not tuple
            or not self.main_numbers
            or any(type(number) is not int for number in self.main_numbers)
        ):
            raise ValueError("main_numbers must be a non-empty tuple of exact integers")
        if self.special_number is not None and type(self.special_number) is not int:
            raise ValueError("special_number must be an exact integer or None")
        _require_text(self.source_id, "source_id")
        _require_sha256(self.source_sha256, "source_sha256")
        _require_sha256(self.outcome_hash, "outcome_hash")
        if self.outcome_hash != _canonical_sha256(self.canonical_material()):
            raise ValueError("outcome_hash does not match official outcome content")

    def canonical_material(self) -> dict[str, object]:
        return _outcome_material(
            schema_version=self.schema_version,
            lottery_type=self.lottery_type,
            draw_number=self.draw_number,
            draw_date=self.draw_date,
            main_numbers=self.main_numbers,
            special_number=self.special_number,
            source_id=self.source_id,
            source_sha256=self.source_sha256,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "outcome_hash": self.outcome_hash}


def _outcome_material(
    *,
    schema_version: str,
    lottery_type: LotteryType,
    draw_number: str,
    draw_date: date,
    main_numbers: tuple[int, ...],
    special_number: int | None,
    source_id: str,
    source_sha256: str,
) -> dict[str, object]:
    return {
        "draw_date": draw_date.isoformat(),
        "draw_number": draw_number,
        "lottery_type": lottery_type.value,
        "main_numbers": list(main_numbers),
        "schema_version": schema_version,
        "source_id": source_id,
        "source_sha256": source_sha256,
        "special_number": special_number,
    }


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    """Game-owned boolean diagnostic; ``None`` is explicitly not applicable."""

    name: str
    occurred: bool | None

    def __post_init__(self) -> None:
        _require_text(self.name, "diagnostic event name")
        if self.occurred is not None and type(self.occurred) is not bool:
            raise ValueError("diagnostic event occurred must be bool or None")

    def canonical_dict(self) -> dict[str, object]:
        return {"name": self.name, "occurred": self.occurred}


@dataclass(frozen=True, slots=True)
class GameEvaluation:
    """Opaque shared envelope around lottery-owned ticket results and events."""

    lottery_type: LotteryType
    ticket_results: tuple[PrizeEvaluationResult, ...]
    diagnostic_events: tuple[DiagnosticEvent, ...]

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.ticket_results) is not tuple or not self.ticket_results:
            raise ValueError("ticket_results must be a non-empty tuple")
        if any(
            type(result) is not PrizeEvaluationResult
            or result.lottery_type is not self.lottery_type
            for result in self.ticket_results
        ):
            raise ValueError("ticket_results must match the evaluation lottery type")
        if type(self.diagnostic_events) is not tuple or any(
            type(event) is not DiagnosticEvent for event in self.diagnostic_events
        ):
            raise ValueError("diagnostic_events must contain DiagnosticEvent values")
        names = tuple(event.name for event in self.diagnostic_events)
        if len(names) != len(set(names)):
            raise ValueError("diagnostic event names must be unique")

    @property
    def is_winner(self) -> bool:
        return any(result.is_winner for result in self.ticket_results)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "diagnostic_events": [event.canonical_dict() for event in self.diagnostic_events],
            "lottery_type": self.lottery_type.value,
            "ticket_results": [result.canonical_dict() for result in self.ticket_results],
        }


@dataclass(frozen=True, slots=True)
class ScoreEntry:
    member_id: str
    prediction_hash: str
    availability: ScoreAvailability
    evaluation: GameEvaluation | None

    def __post_init__(self) -> None:
        _require_text(self.member_id, "member_id")
        _require_sha256(self.prediction_hash, "prediction_hash")
        if type(self.availability) is not ScoreAvailability:
            raise ValueError("availability must be a ScoreAvailability")
        if self.availability is ScoreAvailability.SCORED:
            if type(self.evaluation) is not GameEvaluation:
                raise ValueError("SCORED requires a game evaluation")
        elif self.evaluation is not None:
            raise ValueError("UNAVAILABLE_PREDICTION must not carry an evaluation")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability.value,
            "evaluation": self.evaluation.canonical_dict() if self.evaluation else None,
            "member_id": self.member_id,
            "prediction_hash": self.prediction_hash,
        }


@dataclass(frozen=True, slots=True)
class ScoreRecord:
    schema_version: str
    identity: ProspectiveObservationIdentity
    prediction_hash: str
    outcome: OfficialOutcome
    scored_at: datetime
    entries: tuple[ScoreEntry, ...]
    score_hash: str

    @classmethod
    def create(
        cls,
        *,
        prediction: PredictionRecord,
        outcome: OfficialOutcome,
        entries: tuple[ScoreEntry, ...],
        scored_at: datetime,
    ) -> ScoreRecord:
        if type(entries) is not tuple or any(type(entry) is not ScoreEntry for entry in entries):
            raise ValueError("entries must contain ScoreEntry values")
        expected_member_ids = tuple(entry.member_id for entry in prediction.entries)
        actual_member_ids = tuple(entry.member_id for entry in entries)
        if actual_member_ids != expected_member_ids:
            raise ValueError("score entries must exactly match prediction membership")
        prediction_by_member = {entry.member_id: entry for entry in prediction.entries}
        for entry in entries:
            source = prediction_by_member[entry.member_id]
            if entry.prediction_hash != source.prediction_hash:
                raise ValueError("score entry does not link its immutable prediction entry")
            if (
                entry.evaluation is not None
                and entry.evaluation.lottery_type is not prediction.identity.lottery_type
            ):
                raise ValueError("score entry evaluation has the wrong lottery type")
        material = _score_material(
            schema_version=SCORE_SCHEMA_VERSION,
            identity=prediction.identity,
            prediction_hash=prediction.prediction_hash,
            outcome=outcome,
            entries=entries,
        )
        return cls(
            schema_version=SCORE_SCHEMA_VERSION,
            identity=prediction.identity,
            prediction_hash=prediction.prediction_hash,
            outcome=outcome,
            scored_at=scored_at,
            entries=entries,
            score_hash=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.schema_version != SCORE_SCHEMA_VERSION:
            raise ValueError("unsupported score schema_version")
        if type(self.identity) is not ProspectiveObservationIdentity:
            raise ValueError("identity must be a ProspectiveObservationIdentity")
        if type(self.outcome) is not OfficialOutcome:
            raise ValueError("outcome must be an OfficialOutcome")
        _require_sha256(self.prediction_hash, "prediction_hash")
        _require_utc(self.scored_at, "scored_at")
        if (
            self.outcome.lottery_type is not self.identity.lottery_type
            or self.outcome.draw_number != self.identity.target_draw_number
            or self.outcome.draw_date != self.identity.target_draw_date
        ):
            raise ValueError("score outcome does not match observation identity")
        if (
            type(self.entries) is not tuple
            or not self.entries
            or any(type(entry) is not ScoreEntry for entry in self.entries)
        ):
            raise ValueError("score entries must be a non-empty tuple of ScoreEntry values")
        member_ids = tuple(entry.member_id for entry in self.entries)
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("score entries contain duplicate member_id values")
        _require_sha256(self.score_hash, "score_hash")
        if self.score_hash != _canonical_sha256(self.canonical_material()):
            raise ValueError("score_hash does not match score record content")

    def canonical_material(self) -> dict[str, object]:
        return _score_material(
            schema_version=self.schema_version,
            identity=self.identity,
            prediction_hash=self.prediction_hash,
            outcome=self.outcome,
            entries=self.entries,
        )


def _score_material(
    *,
    schema_version: str,
    identity: ProspectiveObservationIdentity,
    prediction_hash: str,
    outcome: OfficialOutcome,
    entries: tuple[ScoreEntry, ...],
) -> dict[str, object]:
    return {
        "entries": [entry.canonical_dict() for entry in entries],
        "identity": identity.canonical_dict(),
        "outcome": outcome.canonical_dict(),
        "prediction_hash": prediction_hash,
        "schema_version": schema_version,
    }


@dataclass(frozen=True, slots=True)
class CheckpointDiagnosticCount:
    name: str
    eligible_count: int
    occurred_count: int

    def __post_init__(self) -> None:
        _require_text(self.name, "diagnostic name")
        if (
            type(self.eligible_count) is not int
            or type(self.occurred_count) is not int
            or self.eligible_count < 0
            or not 0 <= self.occurred_count <= self.eligible_count
        ):
            raise ValueError("diagnostic counts are invalid")


@dataclass(frozen=True, slots=True)
class CheckpointSummary:
    member_id: str
    checkpoint_size: int
    observation_count: int
    scored_count: int
    unavailable_count: int
    pending_outcome_count: int
    winning_count: int
    nonwinning_count: int
    diagnostic_counts: tuple[CheckpointDiagnosticCount, ...]

    def __post_init__(self) -> None:
        _require_text(self.member_id, "member_id")
        for name, value in (
            ("checkpoint_size", self.checkpoint_size),
            ("observation_count", self.observation_count),
            ("scored_count", self.scored_count),
            ("unavailable_count", self.unavailable_count),
            ("pending_outcome_count", self.pending_outcome_count),
            ("winning_count", self.winning_count),
            ("nonwinning_count", self.nonwinning_count),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative exact integer")
        if self.checkpoint_size != self.observation_count:
            raise ValueError("checkpoint_size must equal observation_count")
        if self.observation_count != (
            self.scored_count + self.unavailable_count + self.pending_outcome_count
        ):
            raise ValueError("observations must equal scored plus unavailable plus pending")
        if self.scored_count != self.winning_count + self.nonwinning_count:
            raise ValueError("scored must equal winning plus nonwinning")
        if type(self.diagnostic_counts) is not tuple or any(
            type(count) is not CheckpointDiagnosticCount for count in self.diagnostic_counts
        ):
            raise ValueError("diagnostic_counts must contain CheckpointDiagnosticCount values")
        names = tuple(count.name for count in self.diagnostic_counts)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("diagnostic_counts must be unique and sorted by name")


def build_checkpoint_summaries(
    predictions: tuple[PredictionRecord, ...],
    scores: tuple[ScoreRecord, ...],
) -> tuple[CheckpointSummary, ...]:
    """Aggregate one frozen cohort without fabricating unreached checkpoints."""

    if type(predictions) is not tuple or not predictions:
        raise ValueError("predictions must be a non-empty tuple")
    if any(type(prediction) is not PredictionRecord for prediction in predictions):
        raise ValueError("predictions must contain PredictionRecord values")
    if type(scores) is not tuple or any(type(score) is not ScoreRecord for score in scores):
        raise ValueError("scores must contain ScoreRecord values")
    cohort = predictions[0].cohort
    if any(prediction.cohort != cohort for prediction in predictions):
        raise ValueError("checkpoint input must contain exactly one frozen cohort")
    identities = tuple(prediction.identity for prediction in predictions)
    if len(identities) != len(set(identities)):
        raise ValueError("checkpoint predictions contain duplicate identities")
    score_by_identity: dict[ProspectiveObservationIdentity, ScoreRecord] = {}
    for score in scores:
        if score.identity in score_by_identity:
            raise ValueError("checkpoint scores contain duplicate identities")
        score_by_identity[score.identity] = score
    prediction_by_identity = {prediction.identity: prediction for prediction in predictions}
    if not set(score_by_identity) <= set(prediction_by_identity):
        raise ValueError("checkpoint score has no matching prediction")
    for identity, score in score_by_identity.items():
        prediction = prediction_by_identity[identity]
        if score.prediction_hash != prediction.prediction_hash:
            raise ValueError("checkpoint score does not link the immutable prediction")
        prediction_entries = {entry.member_id: entry for entry in prediction.entries}
        if tuple(entry.member_id for entry in score.entries) != cohort.member_ids:
            raise ValueError("checkpoint score does not contain every frozen cohort member")
        if any(
            entry.prediction_hash != prediction_entries[entry.member_id].prediction_hash
            for entry in score.entries
        ):
            raise ValueError("checkpoint score entry does not link its prediction entry")

    eligible = sorted(
        (
            prediction
            for prediction in predictions
            if prediction.temporal_provenance in cohort.checkpoint_provenance
        ),
        key=lambda item: (
            item.identity.target_draw_date,
            int(item.identity.target_draw_number),
        ),
    )
    summaries: list[CheckpointSummary] = []
    for member_id in cohort.member_ids:
        for checkpoint_size in cohort.checkpoint_sizes:
            if len(eligible) < checkpoint_size:
                continue
            summaries.append(
                _checkpoint_for_member(
                    member_id=member_id,
                    checkpoint_size=checkpoint_size,
                    predictions=tuple(eligible[:checkpoint_size]),
                    score_by_identity=score_by_identity,
                )
            )
    return tuple(summaries)


def _checkpoint_for_member(
    *,
    member_id: str,
    checkpoint_size: int,
    predictions: tuple[PredictionRecord, ...],
    score_by_identity: dict[ProspectiveObservationIdentity, ScoreRecord],
) -> CheckpointSummary:
    scored = 0
    unavailable = 0
    pending = 0
    winning = 0
    nonwinning = 0
    diagnostic: dict[str, list[int]] = {}
    for prediction in predictions:
        prediction_entry = next(
            (entry for entry in prediction.entries if entry.member_id == member_id),
            None,
        )
        if prediction_entry is None:
            raise ValueError("checkpoint prediction is missing a frozen cohort member")
        score = score_by_identity.get(prediction.identity)
        score_entry = (
            next((entry for entry in score.entries if entry.member_id == member_id), None)
            if score is not None
            else None
        )
        if prediction_entry.availability is PredictionAvailability.UNAVAILABLE:
            unavailable += 1
            if score_entry is not None and (
                score_entry.availability is not ScoreAvailability.UNAVAILABLE_PREDICTION
                or score_entry.prediction_hash != prediction_entry.prediction_hash
            ):
                raise ValueError("unavailable prediction has an incompatible score entry")
            continue
        if score is None:
            pending += 1
            continue
        if (
            score_entry is None
            or score_entry.availability is not ScoreAvailability.SCORED
            or score_entry.evaluation is None
            or score_entry.prediction_hash != prediction_entry.prediction_hash
        ):
            raise ValueError("available prediction has an incompatible score entry")
        scored += 1
        if score_entry.evaluation.is_winner:
            winning += 1
        else:
            nonwinning += 1
        for event in score_entry.evaluation.diagnostic_events:
            if event.occurred is None:
                continue
            counts = diagnostic.setdefault(event.name, [0, 0])
            counts[0] += 1
            counts[1] += int(event.occurred)
    diagnostic_counts = tuple(
        CheckpointDiagnosticCount(name, counts[0], counts[1])
        for name, counts in sorted(diagnostic.items())
    )
    return CheckpointSummary(
        member_id=member_id,
        checkpoint_size=checkpoint_size,
        observation_count=len(predictions),
        scored_count=scored,
        unavailable_count=unavailable,
        pending_outcome_count=pending,
        winning_count=winning,
        nonwinning_count=nonwinning,
        diagnostic_counts=diagnostic_counts,
    )
