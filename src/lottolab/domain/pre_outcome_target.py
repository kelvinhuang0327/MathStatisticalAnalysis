"""Immutable authority records for outcome-free prospective target registration.

This module deliberately carries only target identity, schedule provenance,
outcome *presence* metadata, and causal-history identity.  Official winning
numbers remain confined to the later scoring boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    ObservationTarget,
    OfficialOutcome,
    OutcomePresenceAtPrediction,
    PredictionContext,
)

PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION = "LOTTOLAB_PRE_OUTCOME_TARGET_AUTHORITY_V1"
_PREDICTION_INPUT_IDENTITY_SCHEMA = "LOTTOLAB_PRE_OUTCOME_PREDICTION_INPUT_V1"
_OUTCOME_BINDING_IDENTITY_SCHEMA = "LOTTOLAB_PRE_OUTCOME_BINDING_V1"

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class TargetBindingMismatchError(ValueError):
    """An official outcome does not identify the registered target."""


class PredictionContextBindingMismatchError(ValueError):
    """A prediction context does not match the registered causal input."""


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    if value.tzinfo is not UTC:
        raise ValueError(f"{label} must use UTC")


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} fields differ; missing={missing}, unknown={unknown}")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _string(value: object, label: str) -> str:
    _require_text(value, label)
    return cast(str, value)


def _sha256(value: object, label: str) -> str:
    _require_sha256(value, label)
    return cast(str, value)


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a canonical ISO date") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{label} must be a canonical ISO date")
    return parsed


def _datetime(value: object, label: str) -> datetime:
    text = _string(value, label)
    if not text.endswith("Z"):
        raise ValueError(f"{label} must use canonical UTC text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} must use canonical UTC text") from exc
    _require_utc(parsed, label)
    if _utc_text(parsed) != text:
        raise ValueError(f"{label} must use canonical UTC text")
    return parsed


def _target_from_canonical_dict(value: object, label: str) -> ObservationTarget:
    mapping = _mapping(value, label)
    _expect_keys(mapping, {"draw_date", "draw_number", "lottery_type"}, label)
    try:
        lottery_type = LotteryType(_string(mapping["lottery_type"], f"{label}.lottery_type"))
    except ValueError as exc:
        raise ValueError(f"{label}.lottery_type is unsupported") from exc
    return ObservationTarget(
        lottery_type=lottery_type,
        draw_number=_string(mapping["draw_number"], f"{label}.draw_number"),
        draw_date=_date(mapping["draw_date"], f"{label}.draw_date"),
    )


def _history_from_canonical_dict(value: object) -> CausalHistoryRef:
    mapping = _mapping(value, "causal_history")
    _expect_keys(
        mapping,
        {"draw_count", "history_sha256", "last_draw_date", "last_draw_number"},
        "causal_history",
    )
    draw_count = mapping["draw_count"]
    if type(draw_count) is not int:
        raise ValueError("causal_history.draw_count must be an exact integer")
    last_number_value = mapping["last_draw_number"]
    last_date_value = mapping["last_draw_date"]
    return CausalHistoryRef(
        draw_count=draw_count,
        last_draw_number=(
            None
            if last_number_value is None
            else _string(last_number_value, "causal_history.last_draw_number")
        ),
        last_draw_date=(
            None
            if last_date_value is None
            else _date(last_date_value, "causal_history.last_draw_date")
        ),
        history_sha256=_sha256(mapping["history_sha256"], "causal_history.history_sha256"),
    )


@dataclass(frozen=True, slots=True)
class TargetSourceProvenance:
    """Versioned identity of the payload used to establish one fact."""

    source_id: str
    source_version: str
    source_locator: str
    source_sha256: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.source_id, "source_id")
        _require_text(self.source_version, "source_version")
        _require_text(self.source_locator, "source_locator")
        _require_sha256(self.source_sha256, "source_sha256")
        _require_utc(self.observed_at, "observed_at")

    @property
    def source_payload_sha256(self) -> str:
        """Packet terminology alias for the exact source-payload digest."""

        return self.source_sha256

    def canonical_dict(self) -> dict[str, object]:
        return {
            "observed_at": _utc_text(self.observed_at),
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "source_version": self.source_version,
        }

    @classmethod
    def from_canonical_dict(
        cls,
        value: Mapping[str, object],
    ) -> TargetSourceProvenance:
        mapping = _mapping(value, "source")
        _expect_keys(
            mapping,
            {"observed_at", "source_id", "source_locator", "source_sha256", "source_version"},
            "source",
        )
        return cls(
            source_id=_string(mapping["source_id"], "source.source_id"),
            source_version=_string(mapping["source_version"], "source.source_version"),
            source_locator=_string(mapping["source_locator"], "source.source_locator"),
            source_sha256=_sha256(mapping["source_sha256"], "source.source_sha256"),
            observed_at=_datetime(mapping["observed_at"], "source.observed_at"),
        )


@dataclass(frozen=True, slots=True)
class TargetAnnouncement:
    """Source-bound identity and scheduled instant of one future draw."""

    target: ObservationTarget
    schedule_timezone: str
    scheduled_at: datetime
    source: TargetSourceProvenance

    def __post_init__(self) -> None:
        if type(self.target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        _require_text(self.schedule_timezone, "schedule_timezone")
        _require_utc(self.scheduled_at, "scheduled_at")
        if type(self.source) is not TargetSourceProvenance:
            raise ValueError("source must be a TargetSourceProvenance")
        try:
            timezone = ZoneInfo(self.schedule_timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("schedule_timezone must name an IANA timezone") from exc
        if self.scheduled_at.astimezone(timezone).date() != self.target.draw_date:
            raise ValueError("scheduled_at local date must match target.draw_date")
        if self.source.observed_at >= self.scheduled_at:
            raise ValueError("target source must be observed before scheduled_at")

    @property
    def target_timezone(self) -> str:
        """Compatibility alias emphasizing that the timezone belongs to the target schedule."""

        return self.schedule_timezone

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schedule_timezone": self.schedule_timezone,
            "scheduled_at": _utc_text(self.scheduled_at),
            "source": self.source.canonical_dict(),
            "target": self.target.canonical_dict(),
        }

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> TargetAnnouncement:
        mapping = _mapping(value, "announcement")
        _expect_keys(
            mapping,
            {"schedule_timezone", "scheduled_at", "source", "target"},
            "announcement",
        )
        return cls(
            target=_target_from_canonical_dict(mapping["target"], "announcement.target"),
            schedule_timezone=_string(
                mapping["schedule_timezone"], "announcement.schedule_timezone"
            ),
            scheduled_at=_datetime(mapping["scheduled_at"], "announcement.scheduled_at"),
            source=TargetSourceProvenance.from_canonical_dict(
                _mapping(mapping["source"], "announcement.source")
            ),
        )


@dataclass(frozen=True, slots=True)
class OutcomePresenceAttestation:
    """Target-specific presence metadata with no outcome values or outcome hash."""

    target: ObservationTarget
    presence: OutcomePresenceAtPrediction
    attested_at: datetime
    source: TargetSourceProvenance

    def __post_init__(self) -> None:
        if type(self.target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        if type(self.presence) is not OutcomePresenceAtPrediction:
            raise ValueError("presence must be an OutcomePresenceAtPrediction")
        _require_utc(self.attested_at, "attested_at")
        if type(self.source) is not TargetSourceProvenance:
            raise ValueError("source must be a TargetSourceProvenance")
        if self.source.observed_at > self.attested_at:
            raise ValueError("presence source cannot be observed after attested_at")

    @property
    def as_of(self) -> datetime:
        return self.attested_at

    def canonical_dict(self) -> dict[str, object]:
        return {
            "attested_at": _utc_text(self.attested_at),
            "presence": self.presence.value,
            "source": self.source.canonical_dict(),
            "target": self.target.canonical_dict(),
        }

    @classmethod
    def from_canonical_dict(
        cls,
        value: Mapping[str, object],
    ) -> OutcomePresenceAttestation:
        mapping = _mapping(value, "absence_attestation")
        _expect_keys(
            mapping,
            {"attested_at", "presence", "source", "target"},
            "absence_attestation",
        )
        try:
            presence = OutcomePresenceAtPrediction(
                _string(mapping["presence"], "absence_attestation.presence")
            )
        except ValueError as exc:
            raise ValueError("absence_attestation.presence is unsupported") from exc
        return cls(
            target=_target_from_canonical_dict(mapping["target"], "absence_attestation.target"),
            presence=presence,
            attested_at=_datetime(mapping["attested_at"], "absence_attestation.attested_at"),
            source=TargetSourceProvenance.from_canonical_dict(
                _mapping(mapping["source"], "absence_attestation.source")
            ),
        )


def _prediction_input_identity(
    announcement: TargetAnnouncement,
    absence_attestation: OutcomePresenceAttestation,
    causal_history: CausalHistoryRef,
    registered_at: datetime,
) -> str:
    return _canonical_sha256(
        {
            "absence_attestation": absence_attestation.canonical_dict(),
            "announcement": announcement.canonical_dict(),
            "causal_history": causal_history.canonical_dict(),
            "identity_schema": _PREDICTION_INPUT_IDENTITY_SCHEMA,
            "registered_at": _utc_text(registered_at),
        }
    )


def _outcome_binding_identity(target: ObservationTarget) -> str:
    return _canonical_sha256(
        {
            "identity_schema": _OUTCOME_BINDING_IDENTITY_SCHEMA,
            "target": target.canonical_dict(),
        }
    )


@dataclass(frozen=True, slots=True)
class PreOutcomeTargetRegistration:
    """Self-verifying authority record created strictly before a target's schedule."""

    schema_version: str
    announcement: TargetAnnouncement
    absence_attestation: OutcomePresenceAttestation
    causal_history: CausalHistoryRef
    registered_at: datetime
    prediction_input_identity: str
    outcome_binding_identity: str
    registration_digest: str

    @classmethod
    def create(
        cls,
        *,
        announcement: TargetAnnouncement,
        absence_attestation: OutcomePresenceAttestation,
        causal_history: CausalHistoryRef,
        registered_at: datetime,
    ) -> PreOutcomeTargetRegistration:
        prediction_identity = _prediction_input_identity(
            announcement,
            absence_attestation,
            causal_history,
            registered_at,
        )
        outcome_identity = _outcome_binding_identity(announcement.target)
        material = _registration_material(
            schema_version=PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION,
            announcement=announcement,
            absence_attestation=absence_attestation,
            causal_history=causal_history,
            registered_at=registered_at,
            prediction_input_identity=prediction_identity,
            outcome_binding_identity=outcome_identity,
        )
        return cls(
            schema_version=PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION,
            announcement=announcement,
            absence_attestation=absence_attestation,
            causal_history=causal_history,
            registered_at=registered_at,
            prediction_input_identity=prediction_identity,
            outcome_binding_identity=outcome_identity,
            registration_digest=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.schema_version != PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION:
            raise ValueError("unsupported pre-outcome target authority schema_version")
        if type(self.announcement) is not TargetAnnouncement:
            raise ValueError("announcement must be a TargetAnnouncement")
        if type(self.absence_attestation) is not OutcomePresenceAttestation:
            raise ValueError("absence_attestation must be an OutcomePresenceAttestation")
        if self.absence_attestation.presence is not OutcomePresenceAtPrediction.ABSENT:
            raise ValueError("accepted registration requires an ABSENT outcome attestation")
        if type(self.causal_history) is not CausalHistoryRef:
            raise ValueError("causal_history must be a CausalHistoryRef")
        _require_utc(self.registered_at, "registered_at")
        if self.absence_attestation.target != self.announcement.target:
            raise ValueError("absence attestation target must match announced target")
        if self.announcement.source.observed_at > self.registered_at:
            raise ValueError("target source must be observed no later than registered_at")
        if self.absence_attestation.source.observed_at > self.registered_at:
            raise ValueError("presence source must be observed no later than registered_at")
        if self.absence_attestation.attested_at > self.registered_at:
            raise ValueError("absence must be attested no later than registered_at")
        if self.registered_at >= self.announcement.scheduled_at:
            raise ValueError("registration must occur strictly before scheduled_at")
        self.causal_history.validate_against(self.announcement.target)

        _require_sha256(self.prediction_input_identity, "prediction_input_identity")
        expected_prediction_identity = _prediction_input_identity(
            self.announcement,
            self.absence_attestation,
            self.causal_history,
            self.registered_at,
        )
        if self.prediction_input_identity != expected_prediction_identity:
            raise ValueError("prediction_input_identity does not match causal authority")

        _require_sha256(self.outcome_binding_identity, "outcome_binding_identity")
        if self.outcome_binding_identity != _outcome_binding_identity(self.announcement.target):
            raise ValueError("outcome_binding_identity does not match target")

        _require_sha256(self.registration_digest, "registration_digest")
        if self.registration_digest != _canonical_sha256(self.canonical_material()):
            raise ValueError("registration_digest does not match registration content")

    @property
    def target(self) -> ObservationTarget:
        return self.announcement.target

    def to_observation_target(self) -> ObservationTarget:
        return self.target

    def matches_request(
        self,
        announcement: TargetAnnouncement,
        causal_history: CausalHistoryRef,
    ) -> bool:
        if (
            type(announcement) is not TargetAnnouncement
            or type(causal_history) is not CausalHistoryRef
        ):
            return False
        return self.announcement == announcement and self.causal_history == causal_history

    def canonical_material(self) -> dict[str, object]:
        return _registration_material(
            schema_version=self.schema_version,
            announcement=self.announcement,
            absence_attestation=self.absence_attestation,
            causal_history=self.causal_history,
            registered_at=self.registered_at,
            prediction_input_identity=self.prediction_input_identity,
            outcome_binding_identity=self.outcome_binding_identity,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "registration_digest": self.registration_digest}

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())

    @classmethod
    def from_canonical_dict(
        cls,
        value: Mapping[str, object],
    ) -> PreOutcomeTargetRegistration:
        mapping = _mapping(value, "registration")
        _expect_keys(
            mapping,
            {
                "absence_attestation",
                "announcement",
                "causal_history",
                "outcome_binding_identity",
                "prediction_input_identity",
                "registered_at",
                "registration_digest",
                "schema_version",
            },
            "registration",
        )
        return cls(
            schema_version=_string(mapping["schema_version"], "registration.schema_version"),
            announcement=TargetAnnouncement.from_canonical_dict(
                _mapping(mapping["announcement"], "registration.announcement")
            ),
            absence_attestation=OutcomePresenceAttestation.from_canonical_dict(
                _mapping(
                    mapping["absence_attestation"],
                    "registration.absence_attestation",
                )
            ),
            causal_history=_history_from_canonical_dict(mapping["causal_history"]),
            registered_at=_datetime(mapping["registered_at"], "registration.registered_at"),
            prediction_input_identity=_sha256(
                mapping["prediction_input_identity"],
                "registration.prediction_input_identity",
            ),
            outcome_binding_identity=_sha256(
                mapping["outcome_binding_identity"],
                "registration.outcome_binding_identity",
            ),
            registration_digest=_sha256(
                mapping["registration_digest"],
                "registration.registration_digest",
            ),
        )


def _registration_material(
    *,
    schema_version: str,
    announcement: TargetAnnouncement,
    absence_attestation: OutcomePresenceAttestation,
    causal_history: CausalHistoryRef,
    registered_at: datetime,
    prediction_input_identity: str,
    outcome_binding_identity: str,
) -> dict[str, object]:
    return {
        "absence_attestation": absence_attestation.canonical_dict(),
        "announcement": announcement.canonical_dict(),
        "causal_history": causal_history.canonical_dict(),
        "outcome_binding_identity": outcome_binding_identity,
        "prediction_input_identity": prediction_input_identity,
        "registered_at": _utc_text(registered_at),
        "schema_version": schema_version,
    }


def validate_prediction_context_binding(
    registration: PreOutcomeTargetRegistration,
    context: PredictionContext,
) -> None:
    """Require a Phase-A context to use the registered target and history."""

    if type(registration) is not PreOutcomeTargetRegistration:
        raise ValueError("registration must be a PreOutcomeTargetRegistration")
    if type(context) is not PredictionContext:
        raise ValueError("context must be a PredictionContext")
    if context.target != registration.target:
        raise PredictionContextBindingMismatchError(
            "prediction context target does not match registered target"
        )
    if context.causal_history != registration.causal_history:
        raise PredictionContextBindingMismatchError(
            "prediction context causal history does not match registered authority"
        )


def validate_official_outcome_binding(
    registration: PreOutcomeTargetRegistration,
    outcome: OfficialOutcome,
) -> None:
    """Require a Phase-B outcome to identify exactly the registered target."""

    if type(registration) is not PreOutcomeTargetRegistration:
        raise ValueError("registration must be a PreOutcomeTargetRegistration")
    if type(outcome) is not OfficialOutcome:
        raise ValueError("outcome must be an OfficialOutcome")
    outcome_target = ObservationTarget(
        lottery_type=outcome.lottery_type,
        draw_number=outcome.draw_number,
        draw_date=outcome.draw_date,
    )
    if (
        outcome_target != registration.target
        or _outcome_binding_identity(outcome_target) != registration.outcome_binding_identity
    ):
        raise TargetBindingMismatchError("official outcome target does not match registered target")


__all__ = [
    "PRE_OUTCOME_TARGET_AUTHORITY_SCHEMA_VERSION",
    "OutcomePresenceAttestation",
    "PreOutcomeTargetRegistration",
    "PredictionContextBindingMismatchError",
    "TargetAnnouncement",
    "TargetBindingMismatchError",
    "TargetSourceProvenance",
    "validate_official_outcome_binding",
    "validate_prediction_context_binding",
]
