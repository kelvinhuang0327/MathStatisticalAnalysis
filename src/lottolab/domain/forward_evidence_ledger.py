"""Immutable contracts and deterministic validation for forward evidence ledgers.

The forward evidence ledger records longitudinal prospective evaluation facts
for individual cohort members over time.  It references immutable sealed identities
(PredictionRecord, OfficialOutcome, ScoreRecord) rather than recomputing or mutating
historical evaluations.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    CheckpointDiagnosticCount,
    DiagnosticEvent,
    PredictionAvailability,
    PredictionRecord,
    ScoreAvailability,
    ScoreRecord,
    TemporalProvenance,
)

FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION = "1.0.0"

_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value.strip():
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


class ForwardEvidenceLedgerError(RuntimeError):
    """Base class for fail-closed forward evidence ledger errors."""


class ForwardEvidenceLedgerConflictError(ForwardEvidenceLedgerError):
    """A logical ledger entry identity already contains conflicting content."""


class ForwardEvidenceLedgerLinkError(ForwardEvidenceLedgerError):
    """A ledger entry does not link its sealed prediction, outcome, or score records."""


class ForwardEvidenceLedgerSequenceError(ForwardEvidenceLedgerError):
    """A ledger append operation violates chronological or causal sequencing."""


@dataclass(frozen=True, slots=True)
class ForwardEvidenceLedgerEntryIdentity:
    """Immutable 6-tuple identity for a single member's prospective draw observation."""

    lottery_type: LotteryType
    cohort_id: str
    cohort_version: str
    member_id: str
    target_draw_date: date
    target_draw_number: str

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        _require_text(self.cohort_id, "cohort_id")
        _require_text(self.cohort_version, "cohort_version")
        _require_text(self.member_id, "member_id")
        if type(self.target_draw_date) is not date:
            raise ValueError("target_draw_date must be a date")
        if (
            type(self.target_draw_number) is not str
            or _DRAW_NUMBER.fullmatch(self.target_draw_number) is None
        ):
            raise ValueError("target_draw_number must contain 1-32 ASCII decimal digits")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cohort_id": self.cohort_id,
            "cohort_version": self.cohort_version,
            "lottery_type": self.lottery_type.value,
            "member_id": self.member_id,
            "target_draw_date": self.target_draw_date.isoformat(),
            "target_draw_number": self.target_draw_number,
        }


@dataclass(frozen=True, slots=True)
class LedgerTicketEvidence:
    """Immutable per-ticket evaluation evidence preserving exact selection order."""

    selection_index: int
    main_numbers: tuple[int, ...]
    special_number: int | None
    zone1_hits: int
    zone2_hit: bool
    prize_tier: str | None
    prize_tier_order: int | None
    is_winner: bool

    def __post_init__(self) -> None:
        if type(self.selection_index) is not int or self.selection_index < 0:
            raise ValueError("selection_index must be a non-negative integer")
        if (
            type(self.main_numbers) is not tuple
            or not self.main_numbers
            or any(type(n) is not int or n <= 0 for n in self.main_numbers)
            or self.main_numbers != tuple(sorted(self.main_numbers))
            or len(self.main_numbers) != len(set(self.main_numbers))
        ):
            raise ValueError("main_numbers must be unique positive integers in ascending order")
        if self.special_number is not None and (
            type(self.special_number) is not int or self.special_number <= 0
        ):
            raise ValueError("special_number must be a positive integer or None")
        if type(self.zone1_hits) is not int or self.zone1_hits < 0:
            raise ValueError("zone1_hits must be a non-negative integer")
        if type(self.zone2_hit) is not bool:
            raise ValueError("zone2_hit must be a boolean")
        if type(self.is_winner) is not bool:
            raise ValueError("is_winner must be a boolean")
        if self.prize_tier is not None:
            _require_text(self.prize_tier, "prize_tier")
            if type(self.prize_tier_order) is not int or self.prize_tier_order <= 0:
                raise ValueError("winning ticket requires a positive prize_tier_order")
            if not self.is_winner:
                raise ValueError("winning prize_tier requires is_winner=True")
        else:
            if self.prize_tier_order is not None:
                raise ValueError("non-winning ticket must have prize_tier_order=None")
            if self.is_winner:
                raise ValueError("non-winning ticket must have is_winner=False")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "is_winner": self.is_winner,
            "main_numbers": list(self.main_numbers),
            "prize_tier": self.prize_tier,
            "prize_tier_order": self.prize_tier_order,
            "selection_index": self.selection_index,
            "special_number": self.special_number,
            "zone1_hits": self.zone1_hits,
            "zone2_hit": self.zone2_hit,
        }


@dataclass(frozen=True, slots=True)
class ForwardEvidenceLedgerEntry:
    """Deterministic sealed forward evidence record for one cohort member draw."""

    schema_version: str
    identity: ForwardEvidenceLedgerEntryIdentity
    prediction_hash: str
    outcome_hash: str
    score_hash: str
    producer_fingerprint_digest: str
    cohort_authority_sha256: str
    temporal_provenance: TemporalProvenance
    availability: ScoreAvailability
    unavailable_reason: str | None
    matched_baseline_id: str | None
    prize_rule_version: str | None
    prize_rule_provenance: str | None
    tickets: tuple[LedgerTicketEvidence, ...]
    diagnostic_events: tuple[DiagnosticEvent, ...]
    is_winner: bool | None
    entry_created_at: datetime
    ledger_entry_hash: str

    @classmethod
    def from_records(
        cls,
        *,
        prediction: PredictionRecord,
        score: ScoreRecord,
        member_id: str,
        entry_created_at: datetime,
    ) -> ForwardEvidenceLedgerEntry:
        """Construct canonical entry from sealed prediction and score records."""
        if type(prediction) is not PredictionRecord:
            raise ValueError("prediction must be a PredictionRecord")
        if type(score) is not ScoreRecord:
            raise ValueError("score must be a ScoreRecord")
        _require_text(member_id, "member_id")
        _require_utc(entry_created_at, "entry_created_at")

        if score.prediction_hash != prediction.prediction_hash:
            raise ForwardEvidenceLedgerLinkError(
                "score prediction_hash does not match sealed prediction record"
            )
        if score.identity != prediction.identity:
            raise ForwardEvidenceLedgerLinkError(
                "score observation identity does not match prediction observation identity"
            )

        if member_id not in prediction.cohort.member_ids:
            raise ValueError(f"member_id '{member_id}' is not in frozen cohort members")

        pred_entry = next(
            (entry for entry in prediction.entries if entry.member_id == member_id),
            None,
        )
        if pred_entry is None:
            raise ForwardEvidenceLedgerLinkError(
                f"prediction record is missing entry for member '{member_id}'"
            )

        score_entry = next(
            (entry for entry in score.entries if entry.member_id == member_id),
            None,
        )
        if score_entry is None:
            raise ForwardEvidenceLedgerLinkError(
                f"score record is missing entry for member '{member_id}'"
            )

        if score_entry.prediction_hash != pred_entry.prediction_hash:
            raise ForwardEvidenceLedgerLinkError(
                f"score entry prediction_hash does not match prediction entry for '{member_id}'"
            )

        identity = ForwardEvidenceLedgerEntryIdentity(
            lottery_type=prediction.identity.lottery_type,
            cohort_id=prediction.identity.cohort_id,
            cohort_version=prediction.identity.cohort_version,
            member_id=member_id,
            target_draw_date=prediction.identity.target_draw_date,
            target_draw_number=prediction.identity.target_draw_number,
        )

        availability = score_entry.availability
        tickets: list[LedgerTicketEvidence] = []
        diagnostic_events: tuple[DiagnosticEvent, ...] = ()
        prize_rule_version: str | None = None
        prize_rule_provenance: str | None = None
        is_winner: bool | None = None
        unavailable_reason: str | None = None
        matched_baseline_id: str | None = None

        if pred_entry.availability is PredictionAvailability.UNAVAILABLE:
            if availability is not ScoreAvailability.UNAVAILABLE_PREDICTION:
                raise ForwardEvidenceLedgerLinkError(
                    "unavailable prediction entry must map to UNAVAILABLE_PREDICTION score"
                )
            if score_entry.evaluation is not None:
                raise ForwardEvidenceLedgerLinkError(
                    "unavailable score entry must not contain a game evaluation"
                )
            unavailable_reason = pred_entry.unavailable_reason
            is_winner = None
        else:
            if availability is not ScoreAvailability.SCORED or score_entry.evaluation is None:
                raise ForwardEvidenceLedgerLinkError(
                    "available prediction entry requires a SCORED game evaluation"
                )
            evaluation = score_entry.evaluation
            if evaluation.lottery_type is not identity.lottery_type:
                raise ForwardEvidenceLedgerLinkError(
                    "evaluation lottery type does not match observation lottery type"
                )
            if len(evaluation.ticket_results) != len(pred_entry.selections):
                raise ForwardEvidenceLedgerLinkError(
                    "evaluation ticket results count does not match prediction selections count"
                )

            for idx, (selection, res) in enumerate(
                zip(pred_entry.selections, evaluation.ticket_results, strict=True)
            ):
                tickets.append(
                    LedgerTicketEvidence(
                        selection_index=idx,
                        main_numbers=selection.main_numbers,
                        special_number=selection.special_number,
                        zone1_hits=res.zone1_hits,
                        zone2_hit=res.zone2_hit,
                        prize_tier=res.prize_tier,
                        prize_tier_order=res.prize_tier_order,
                        is_winner=res.is_winner,
                    )
                )

            if evaluation.ticket_results:
                prize_rule_version = evaluation.ticket_results[0].prize_rule_version
                prize_rule_provenance = evaluation.ticket_results[0].prize_rule_provenance

            diagnostic_events = evaluation.diagnostic_events
            is_winner = evaluation.is_winner
            matched_baseline_id = (
                pred_entry.matched_baseline.baseline_id if pred_entry.matched_baseline else None
            )

        material = _ledger_entry_material(
            schema_version=FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION,
            identity=identity,
            prediction_hash=prediction.prediction_hash,
            outcome_hash=score.outcome.outcome_hash,
            score_hash=score.score_hash,
            producer_fingerprint_digest=prediction.producer_fingerprint.digest,
            cohort_authority_sha256=prediction.cohort.authority_sha256,
            temporal_provenance=prediction.temporal_provenance,
            availability=availability,
            unavailable_reason=unavailable_reason,
            matched_baseline_id=matched_baseline_id,
            prize_rule_version=prize_rule_version,
            prize_rule_provenance=prize_rule_provenance,
            tickets=tuple(tickets),
            diagnostic_events=diagnostic_events,
            is_winner=is_winner,
        )

        return cls(
            schema_version=FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION,
            identity=identity,
            prediction_hash=prediction.prediction_hash,
            outcome_hash=score.outcome.outcome_hash,
            score_hash=score.score_hash,
            producer_fingerprint_digest=prediction.producer_fingerprint.digest,
            cohort_authority_sha256=prediction.cohort.authority_sha256,
            temporal_provenance=prediction.temporal_provenance,
            availability=availability,
            unavailable_reason=unavailable_reason,
            matched_baseline_id=matched_baseline_id,
            prize_rule_version=prize_rule_version,
            prize_rule_provenance=prize_rule_provenance,
            tickets=tuple(tickets),
            diagnostic_events=diagnostic_events,
            is_winner=is_winner,
            entry_created_at=entry_created_at,
            ledger_entry_hash=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.schema_version != FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION:
            raise ValueError("unsupported ledger entry schema_version")
        if type(self.identity) is not ForwardEvidenceLedgerEntryIdentity:
            raise ValueError("identity must be a ForwardEvidenceLedgerEntryIdentity")
        _require_sha256(self.prediction_hash, "prediction_hash")
        _require_sha256(self.outcome_hash, "outcome_hash")
        _require_sha256(self.score_hash, "score_hash")
        _require_sha256(self.producer_fingerprint_digest, "producer_fingerprint_digest")
        _require_sha256(self.cohort_authority_sha256, "cohort_authority_sha256")
        if type(self.temporal_provenance) is not TemporalProvenance:
            raise ValueError("temporal_provenance must be a TemporalProvenance")
        if type(self.availability) is not ScoreAvailability:
            raise ValueError("availability must be a ScoreAvailability")
        _require_utc(self.entry_created_at, "entry_created_at")

        if self.availability is ScoreAvailability.UNAVAILABLE_PREDICTION:
            _require_text(self.unavailable_reason, "unavailable_reason")
            if self.matched_baseline_id is not None:
                raise ValueError("unavailable entry must not have matched_baseline_id")
            if self.prize_rule_version is not None or self.prize_rule_provenance is not None:
                raise ValueError("unavailable entry must not have prize rule details")
            if self.tickets:
                raise ValueError("unavailable entry must not carry tickets")
            if self.diagnostic_events:
                raise ValueError("unavailable entry must not carry diagnostic_events")
            if self.is_winner is not None:
                raise ValueError("unavailable entry is_winner must be None")
        else:
            if self.unavailable_reason is not None:
                raise ValueError("scored entry must not carry unavailable_reason")
            if not self.tickets:
                raise ValueError("scored entry must carry tickets")
            _require_text(self.prize_rule_version, "prize_rule_version")
            _require_text(self.prize_rule_provenance, "prize_rule_provenance")
            if type(self.is_winner) is not bool:
                raise ValueError("scored entry is_winner must be a boolean")
            if any(type(t) is not LedgerTicketEvidence for t in self.tickets):
                raise ValueError("tickets must contain LedgerTicketEvidence values")
            indices = tuple(t.selection_index for t in self.tickets)
            if indices != tuple(range(len(self.tickets))):
                raise ValueError("ticket selection_indices must be contiguous starting from 0")

        if type(self.diagnostic_events) is not tuple or any(
            type(e) is not DiagnosticEvent for e in self.diagnostic_events
        ):
            raise ValueError("diagnostic_events must contain DiagnosticEvent values")
        event_names = tuple(e.name for e in self.diagnostic_events)
        if len(event_names) != len(set(event_names)):
            raise ValueError("diagnostic event names must be unique")

        _require_sha256(self.ledger_entry_hash, "ledger_entry_hash")
        if self.ledger_entry_hash != _canonical_sha256(self.canonical_material()):
            raise ValueError("ledger_entry_hash does not match canonical material")

    def canonical_material(self) -> dict[str, object]:
        return _ledger_entry_material(
            schema_version=self.schema_version,
            identity=self.identity,
            prediction_hash=self.prediction_hash,
            outcome_hash=self.outcome_hash,
            score_hash=self.score_hash,
            producer_fingerprint_digest=self.producer_fingerprint_digest,
            cohort_authority_sha256=self.cohort_authority_sha256,
            temporal_provenance=self.temporal_provenance,
            availability=self.availability,
            unavailable_reason=self.unavailable_reason,
            matched_baseline_id=self.matched_baseline_id,
            prize_rule_version=self.prize_rule_version,
            prize_rule_provenance=self.prize_rule_provenance,
            tickets=self.tickets,
            diagnostic_events=self.diagnostic_events,
            is_winner=self.is_winner,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_material(),
            "entry_created_at": _utc_text(self.entry_created_at),
            "ledger_entry_hash": self.ledger_entry_hash,
        }


def _ledger_entry_material(
    *,
    schema_version: str,
    identity: ForwardEvidenceLedgerEntryIdentity,
    prediction_hash: str,
    outcome_hash: str,
    score_hash: str,
    producer_fingerprint_digest: str,
    cohort_authority_sha256: str,
    temporal_provenance: TemporalProvenance,
    availability: ScoreAvailability,
    unavailable_reason: str | None,
    matched_baseline_id: str | None,
    prize_rule_version: str | None,
    prize_rule_provenance: str | None,
    tickets: tuple[LedgerTicketEvidence, ...],
    diagnostic_events: tuple[DiagnosticEvent, ...],
    is_winner: bool | None,
) -> dict[str, object]:
    return {
        "availability": availability.value,
        "cohort_authority_sha256": cohort_authority_sha256,
        "diagnostic_events": [e.canonical_dict() for e in diagnostic_events],
        "identity": identity.canonical_dict(),
        "is_winner": is_winner,
        "matched_baseline_id": matched_baseline_id,
        "outcome_hash": outcome_hash,
        "prediction_hash": prediction_hash,
        "prize_rule_provenance": prize_rule_provenance,
        "prize_rule_version": prize_rule_version,
        "producer_fingerprint_digest": producer_fingerprint_digest,
        "schema_version": schema_version,
        "score_hash": score_hash,
        "temporal_provenance": temporal_provenance.value,
        "tickets": [t.canonical_dict() for t in tickets],
        "unavailable_reason": unavailable_reason,
    }


@dataclass(frozen=True, slots=True)
class MemberLongitudinalEvidenceSummary:
    """Deterministic longitudinal summary of forward evidence for one member."""

    member_id: str
    lottery_type: LotteryType
    cohort_id: str
    cohort_version: str
    total_entries: int
    scored_count: int
    unavailable_count: int
    winning_count: int
    nonwinning_count: int
    total_tickets_evaluated: int
    winning_tickets_count: int
    prize_tier_counts: dict[str, int]
    diagnostic_counts: tuple[CheckpointDiagnosticCount, ...]
    first_draw_date: date | None
    last_draw_date: date | None
    first_draw_number: str | None
    last_draw_number: str | None

    def __post_init__(self) -> None:
        _require_text(self.member_id, "member_id")
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        _require_text(self.cohort_id, "cohort_id")
        _require_text(self.cohort_version, "cohort_version")
        for label, val in (
            ("total_entries", self.total_entries),
            ("scored_count", self.scored_count),
            ("unavailable_count", self.unavailable_count),
            ("winning_count", self.winning_count),
            ("nonwinning_count", self.nonwinning_count),
            ("total_tickets_evaluated", self.total_tickets_evaluated),
            ("winning_tickets_count", self.winning_tickets_count),
        ):
            if type(val) is not int or val < 0:
                raise ValueError(f"{label} must be a non-negative integer")

        if self.total_entries != self.scored_count + self.unavailable_count:
            raise ValueError("total_entries must equal scored_count + unavailable_count")
        if self.scored_count != self.winning_count + self.nonwinning_count:
            raise ValueError("scored_count must equal winning_count + nonwinning_count")
        if self.total_tickets_evaluated < self.winning_tickets_count:
            raise ValueError("total_tickets_evaluated cannot be less than winning_tickets_count")

        if type(self.prize_tier_counts) is not dict:
            raise ValueError("prize_tier_counts must be a dictionary")
        if type(self.diagnostic_counts) is not tuple or any(
            type(c) is not CheckpointDiagnosticCount for c in self.diagnostic_counts
        ):
            raise ValueError("diagnostic_counts must contain CheckpointDiagnosticCount values")
        names = tuple(c.name for c in self.diagnostic_counts)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("diagnostic_counts must be unique and sorted by name")


def build_member_longitudinal_summary(
    entries: tuple[ForwardEvidenceLedgerEntry, ...],
) -> MemberLongitudinalEvidenceSummary:
    """Build longitudinal summary over an ordered sequence of entries for one member."""
    if type(entries) is not tuple or not entries:
        raise ValueError("entries must be a non-empty tuple of ForwardEvidenceLedgerEntry values")
    if any(type(e) is not ForwardEvidenceLedgerEntry for e in entries):
        raise ValueError("entries must contain ForwardEvidenceLedgerEntry values")

    first_entry = entries[0]
    member_id = first_entry.identity.member_id
    lottery_type = first_entry.identity.lottery_type
    cohort_id = first_entry.identity.cohort_id
    cohort_version = first_entry.identity.cohort_version

    for entry in entries:
        if (
            entry.identity.member_id != member_id
            or entry.identity.lottery_type is not lottery_type
            or entry.identity.cohort_id != cohort_id
            or entry.identity.cohort_version != cohort_version
        ):
            raise ValueError("all entries in summary must belong to the same member and cohort")

    # Sort deterministically by canonical draw order
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.identity.target_draw_date, int(e.identity.target_draw_number)),
    )

    scored_count = 0
    unavailable_count = 0
    winning_count = 0
    nonwinning_count = 0
    total_tickets = 0
    winning_tickets = 0
    tier_counts: dict[str, int] = {}
    diag_map: dict[str, list[int]] = {}

    for entry in sorted_entries:
        if entry.availability is ScoreAvailability.UNAVAILABLE_PREDICTION:
            unavailable_count += 1
            continue

        scored_count += 1
        if entry.is_winner:
            winning_count += 1
        else:
            nonwinning_count += 1

        for ticket in entry.tickets:
            total_tickets += 1
            if ticket.is_winner:
                winning_tickets += 1
            if ticket.prize_tier is not None:
                tier_counts[ticket.prize_tier] = tier_counts.get(ticket.prize_tier, 0) + 1

        for diag in entry.diagnostic_events:
            if diag.occurred is None:
                continue
            counts = diag_map.setdefault(diag.name, [0, 0])
            counts[0] += 1
            counts[1] += int(diag.occurred)

    diagnostic_counts = tuple(
        CheckpointDiagnosticCount(name, counts[0], counts[1])
        for name, counts in sorted(diag_map.items())
    )

    first_entry_sorted = sorted_entries[0]
    last_entry_sorted = sorted_entries[-1]

    return MemberLongitudinalEvidenceSummary(
        member_id=member_id,
        lottery_type=lottery_type,
        cohort_id=cohort_id,
        cohort_version=cohort_version,
        total_entries=len(sorted_entries),
        scored_count=scored_count,
        unavailable_count=unavailable_count,
        winning_count=winning_count,
        nonwinning_count=nonwinning_count,
        total_tickets_evaluated=total_tickets,
        winning_tickets_count=winning_tickets,
        prize_tier_counts=tier_counts,
        diagnostic_counts=diagnostic_counts,
        first_draw_date=first_entry_sorted.identity.target_draw_date,
        last_draw_date=last_entry_sorted.identity.target_draw_date,
        first_draw_number=first_entry_sorted.identity.target_draw_number,
        last_draw_number=last_entry_sorted.identity.target_draw_number,
    )


__all__ = [
    "FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION",
    "ForwardEvidenceLedgerConflictError",
    "ForwardEvidenceLedgerEntry",
    "ForwardEvidenceLedgerEntryIdentity",
    "ForwardEvidenceLedgerError",
    "ForwardEvidenceLedgerLinkError",
    "ForwardEvidenceLedgerSequenceError",
    "LedgerTicketEvidence",
    "MemberLongitudinalEvidenceSummary",
    "build_member_longitudinal_summary",
]
