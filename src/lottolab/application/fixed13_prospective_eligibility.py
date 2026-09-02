"""Outcome-free eligibility sealing for the frozen Big Lotto fixed-13 cohort.

The builder in this module consumes only already-sealed prediction authority,
pre-outcome target/timing authority, and the provenance emitted by the verified
fixed-13 producer.  It never accepts official winning numbers and never runs a
strategy.  Every failed admission gate is recorded as an immutable
``PRE_OUTCOME_INELIGIBLE`` disposition.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import cast

from lottolab.application.fixed13_prospective_producer import (
    FIXED_13_COHORT_STRATEGY_IDS,
    RNG_DOMAIN_TAG,
    RNG_POLICY_ID,
    RNG_REQUIRED_STRATEGY_IDS,
    RNG_SEED_DERIVATION_FORMULA,
    AdapterConstruction,
    Fixed13ProspectiveProducerRecord,
    ProducerImplementationIdentity,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import PreOutcomeTargetRegistration
from lottolab.domain.prospective_observer import (
    OutcomePresenceAtPrediction,
    PredictionAvailability,
    PredictionRecord,
    ProspectiveObservationIdentity,
    TemporalProvenance,
    classify_temporal_provenance,
)

FIXED13_PROSPECTIVE_ELIGIBILITY_SCHEMA_VERSION = (
    "LOTTOLAB_FIXED13_PROSPECTIVE_ELIGIBILITY_V1"
)
PRE_OUTCOME_TIMING_PROOF_REF_SCHEMA_VERSION = "LOTTOLAB_PRE_OUTCOME_TIMING_PROOF_REF_V1"
PINNED_FREEZE_ARTIFACT_FILE_SHA256 = (
    "61beff4d35f7b0d10502fe0d1f36cc39e5a240128499061eac2599132019154b"
)
PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256 = (
    "814088795f4e1b5b5d0de2035905b7b6ff89e0cb874a456ef544f7bcc6afd786"
)
FIXED_MEMBER_COUNT = 13
_PRODUCER_MODULE_PATH = "lottolab.application.fixed13_prospective_producer"
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", flags=re.ASCII)


class Fixed13EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    PRE_OUTCOME_INELIGIBLE = "PRE_OUTCOME_INELIGIBLE"


@dataclass(frozen=True, slots=True)
class PreOutcomeTimingProofRef:
    """Minimal external-receipt reference; this layer does not produce the receipt."""

    proof_type: str
    reference: str
    reference_sha256: str

    def __post_init__(self) -> None:
        _require_text(self.proof_type, "proof_type")
        _require_text(self.reference, "reference")
        _require_sha256(self.reference_sha256, "reference_sha256")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "proof_type": self.proof_type,
            "reference": self.reference,
            "reference_sha256": self.reference_sha256,
            "schema_version": PRE_OUTCOME_TIMING_PROOF_REF_SCHEMA_VERSION,
        }

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> PreOutcomeTimingProofRef:
        _expect_keys(
            value,
            {"proof_type", "reference", "reference_sha256", "schema_version"},
            "pre_outcome_timing_proof_ref",
        )
        _expect_exact(
            value["schema_version"],
            PRE_OUTCOME_TIMING_PROOF_REF_SCHEMA_VERSION,
            "pre_outcome_timing_proof_ref.schema_version",
        )
        return cls(
            proof_type=_string(value["proof_type"], "pre_outcome_timing_proof_ref.proof_type"),
            reference=_string(value["reference"], "pre_outcome_timing_proof_ref.reference"),
            reference_sha256=_sha256(
                value["reference_sha256"],
                "pre_outcome_timing_proof_ref.reference_sha256",
            ),
        )


@dataclass(frozen=True, slots=True)
class Fixed13MemberTicket:
    strategy_id: str
    canonical_ticket: tuple[int, ...] | None

    def __post_init__(self) -> None:
        _require_text(self.strategy_id, "member ticket strategy_id")
        if self.canonical_ticket is not None and not _is_legal_canonical_ticket(
            self.canonical_ticket
        ):
            raise ValueError("canonical_ticket must be a legal Big Lotto ticket or None")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "canonical_ticket": (
                list(self.canonical_ticket) if self.canonical_ticket is not None else None
            ),
            "strategy_id": self.strategy_id,
        }


@dataclass(frozen=True, slots=True)
class Fixed13DuplicateGroup:
    canonical_ticket: tuple[int, ...]
    member_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _is_legal_canonical_ticket(self.canonical_ticket):
            raise ValueError("duplicate group ticket must be a legal Big Lotto ticket")
        if (
            type(self.member_ids) is not tuple
            or len(self.member_ids) < 2
            or any(type(member_id) is not str or not member_id for member_id in self.member_ids)
            or len(self.member_ids) != len(set(self.member_ids))
        ):
            raise ValueError("duplicate group must contain at least two unique member IDs")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "canonical_ticket": list(self.canonical_ticket),
            "member_ids": list(self.member_ids),
        }


@dataclass(frozen=True, slots=True)
class Fixed13MemberRngProvenance:
    strategy_id: str
    adapter_path: str
    adapter_construction: str
    per_member_rng_required: bool
    rng_policy_id: str
    rng_domain_tag: str
    rng_seed_derivation_formula: str
    rng_seed_sha256_hex: str | None
    causal_history_digest: str
    causal_history_row_count: int
    causal_history_last_draw_identity: str
    producer_repository_head: str
    producer_repository_tree: str
    producer_module_path: str
    python_implementation_identity: str
    rng_selfcheck_vector: tuple[float, ...] | None
    historical_r2_ticket_parity_note: str

    def __post_init__(self) -> None:
        string_fields = (
            self.strategy_id,
            self.adapter_path,
            self.adapter_construction,
            self.rng_policy_id,
            self.rng_domain_tag,
            self.rng_seed_derivation_formula,
            self.causal_history_digest,
            self.causal_history_last_draw_identity,
            self.producer_repository_head,
            self.producer_repository_tree,
            self.producer_module_path,
            self.python_implementation_identity,
            self.historical_r2_ticket_parity_note,
        )
        if any(type(value) is not str for value in string_fields):
            raise ValueError("provenance string fields must be exact strings")
        if type(self.per_member_rng_required) is not bool:
            raise ValueError("per_member_rng_required must be an exact boolean")
        if self.rng_seed_sha256_hex is not None and type(self.rng_seed_sha256_hex) is not str:
            raise ValueError("rng_seed_sha256_hex must be a string or None")
        if type(self.causal_history_row_count) is not int:
            raise ValueError("causal_history_row_count must be an exact integer")
        if self.rng_selfcheck_vector is not None and (
            type(self.rng_selfcheck_vector) is not tuple
            or any(
                type(value) is not float or not math.isfinite(value)
                for value in self.rng_selfcheck_vector
            )
        ):
            raise ValueError("rng_selfcheck_vector must contain finite floats or be None")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "adapter_construction": self.adapter_construction,
            "adapter_path": self.adapter_path,
            "causal_history_digest": self.causal_history_digest,
            "causal_history_last_draw_identity": self.causal_history_last_draw_identity,
            "causal_history_row_count": self.causal_history_row_count,
            "historical_r2_ticket_parity_note": self.historical_r2_ticket_parity_note,
            "per_member_rng_required": self.per_member_rng_required,
            "producer_module_path": self.producer_module_path,
            "producer_repository_head": self.producer_repository_head,
            "producer_repository_tree": self.producer_repository_tree,
            "python_implementation_identity": self.python_implementation_identity,
            "rng_domain_tag": self.rng_domain_tag,
            "rng_policy_id": self.rng_policy_id,
            "rng_seed_derivation_formula": self.rng_seed_derivation_formula,
            "rng_seed_sha256_hex": self.rng_seed_sha256_hex,
            "rng_selfcheck_vector": (
                list(self.rng_selfcheck_vector)
                if self.rng_selfcheck_vector is not None
                else None
            ),
            "strategy_id": self.strategy_id,
        }


@dataclass(frozen=True, slots=True)
class Fixed13ProspectiveEligibilityRecord:
    schema_version: str
    identity: ProspectiveObservationIdentity
    official_draw_identity: str
    lottery_type: LotteryType
    eligibility_status: Fixed13EligibilityStatus
    ineligibility_reasons: tuple[str, ...]
    freeze_artifact_file_sha256: str
    cohort_membership_strategy_ids_lcj1_sha256: str
    prediction_record_digest: str
    target_registration_digest: str
    target_scheduled_at: datetime
    prediction_created_at: datetime
    eligibility_sealed_at: datetime
    pre_outcome_timing_proof_ref: PreOutcomeTimingProofRef | None
    temporal_provenance: TemporalProvenance
    fixed_member_count: int
    canonical_member_order: tuple[str, ...]
    observed_member_order: tuple[str, ...]
    per_member_canonical_tickets: tuple[Fixed13MemberTicket, ...]
    k_d: int
    distinct_canonical_tickets: tuple[tuple[int, ...], ...]
    duplicate_groups: tuple[Fixed13DuplicateGroup, ...]
    per_member_rng_provenance: tuple[Fixed13MemberRngProvenance, ...]
    eligibility_record_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != FIXED13_PROSPECTIVE_ELIGIBILITY_SCHEMA_VERSION:
            raise ValueError("unsupported fixed-13 eligibility schema_version")
        if type(self.identity) is not ProspectiveObservationIdentity:
            raise ValueError("identity must be a ProspectiveObservationIdentity")
        if self.identity.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("eligibility identity must be BIG_LOTTO")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("lottery_type must be BIG_LOTTO")
        if self.official_draw_identity != self.identity.target_draw_number:
            raise ValueError("official_draw_identity must match the storage identity")
        if type(self.eligibility_status) is not Fixed13EligibilityStatus:
            raise ValueError("eligibility_status is unsupported")
        if (
            type(self.ineligibility_reasons) is not tuple
            or any(type(reason) is not str or not reason for reason in self.ineligibility_reasons)
            or self.ineligibility_reasons != tuple(sorted(set(self.ineligibility_reasons)))
        ):
            raise ValueError("ineligibility_reasons must be unique and sorted")
        if self.eligibility_status is Fixed13EligibilityStatus.ELIGIBLE:
            if self.ineligibility_reasons:
                raise ValueError("ELIGIBLE must not carry ineligibility reasons")
        elif not self.ineligibility_reasons:
            raise ValueError("PRE_OUTCOME_INELIGIBLE requires at least one reason")
        for label, digest in (
            ("freeze_artifact_file_sha256", self.freeze_artifact_file_sha256),
            (
                "cohort_membership_strategy_ids_lcj1_sha256",
                self.cohort_membership_strategy_ids_lcj1_sha256,
            ),
            ("prediction_record_digest", self.prediction_record_digest),
            ("target_registration_digest", self.target_registration_digest),
        ):
            _require_sha256(digest, label)
        _require_utc(self.target_scheduled_at, "target_scheduled_at")
        _require_utc(self.prediction_created_at, "prediction_created_at")
        _require_utc(self.eligibility_sealed_at, "eligibility_sealed_at")
        if self.pre_outcome_timing_proof_ref is not None and type(
            self.pre_outcome_timing_proof_ref
        ) is not PreOutcomeTimingProofRef:
            raise ValueError("pre_outcome_timing_proof_ref has the wrong type")
        if type(self.temporal_provenance) is not TemporalProvenance:
            raise ValueError("temporal_provenance is unsupported")
        if self.fixed_member_count != FIXED_MEMBER_COUNT:
            raise ValueError("fixed_member_count must equal 13")
        if self.canonical_member_order != FIXED_13_COHORT_STRATEGY_IDS:
            raise ValueError("canonical_member_order differs from the frozen fixed-13 order")
        if type(self.observed_member_order) is not tuple or any(
            type(member_id) is not str for member_id in self.observed_member_order
        ):
            raise ValueError("observed_member_order must be a tuple of strings")
        if (
            type(self.per_member_canonical_tickets) is not tuple
            or len(self.per_member_canonical_tickets) != FIXED_MEMBER_COUNT
            or any(
                type(item) is not Fixed13MemberTicket
                for item in self.per_member_canonical_tickets
            )
            or tuple(item.strategy_id for item in self.per_member_canonical_tickets)
            != FIXED_13_COHORT_STRATEGY_IDS
        ):
            raise ValueError("per_member_canonical_tickets must cover the canonical fixed-13 order")
        if type(self.distinct_canonical_tickets) is not tuple or any(
            not _is_legal_canonical_ticket(ticket)
            for ticket in self.distinct_canonical_tickets
        ):
            raise ValueError("distinct_canonical_tickets contains an invalid ticket")
        if self.distinct_canonical_tickets != tuple(sorted(set(self.distinct_canonical_tickets))):
            raise ValueError("distinct_canonical_tickets must be unique and sorted")
        if type(self.k_d) is not int or self.k_d != len(self.distinct_canonical_tickets):
            raise ValueError("k_d must equal the number of distinct canonical tickets")
        if not 0 <= self.k_d <= FIXED_MEMBER_COUNT:
            raise ValueError("k_d must be between 0 and 13")
        if type(self.duplicate_groups) is not tuple or any(
            type(group) is not Fixed13DuplicateGroup for group in self.duplicate_groups
        ):
            raise ValueError("duplicate_groups must contain Fixed13DuplicateGroup values")
        expected_distinct, expected_duplicates = _ticket_aggregates(
            self.per_member_canonical_tickets
        )
        if self.distinct_canonical_tickets != expected_distinct:
            raise ValueError("distinct_canonical_tickets does not match member tickets")
        if self.duplicate_groups != expected_duplicates:
            raise ValueError("duplicate_groups does not match member tickets")
        if type(self.per_member_rng_provenance) is not tuple or any(
            type(item) is not Fixed13MemberRngProvenance
            for item in self.per_member_rng_provenance
        ):
            raise ValueError("per_member_rng_provenance contains an invalid item")
        if self.eligibility_status is Fixed13EligibilityStatus.ELIGIBLE:
            if self.k_d < 1:
                raise ValueError("ELIGIBLE requires at least one distinct ticket")
            if any(item.canonical_ticket is None for item in self.per_member_canonical_tickets):
                raise ValueError("ELIGIBLE requires all 13 canonical tickets")
            if tuple(item.strategy_id for item in self.per_member_rng_provenance) != (
                FIXED_13_COHORT_STRATEGY_IDS
            ):
                raise ValueError("ELIGIBLE requires all 13 provenance records in frozen order")
            _validate_eligible_record(self)
        _require_sha256(self.eligibility_record_digest, "eligibility_record_digest")
        if self.eligibility_record_digest != _canonical_sha256(self.canonical_material()):
            raise ValueError("eligibility_record_digest does not match complete record semantics")

    @classmethod
    def create(
        cls,
        *,
        identity: ProspectiveObservationIdentity,
        eligibility_status: Fixed13EligibilityStatus,
        ineligibility_reasons: tuple[str, ...],
        freeze_artifact_file_sha256: str,
        cohort_membership_strategy_ids_lcj1_sha256: str,
        prediction_record_digest: str,
        target_registration_digest: str,
        target_scheduled_at: datetime,
        prediction_created_at: datetime,
        eligibility_sealed_at: datetime,
        pre_outcome_timing_proof_ref: PreOutcomeTimingProofRef | None,
        temporal_provenance: TemporalProvenance,
        observed_member_order: tuple[str, ...],
        per_member_canonical_tickets: tuple[Fixed13MemberTicket, ...],
        distinct_canonical_tickets: tuple[tuple[int, ...], ...],
        duplicate_groups: tuple[Fixed13DuplicateGroup, ...],
        per_member_rng_provenance: tuple[Fixed13MemberRngProvenance, ...],
    ) -> Fixed13ProspectiveEligibilityRecord:
        material = _eligibility_material(
            identity=identity,
            official_draw_identity=identity.target_draw_number,
            lottery_type=LotteryType.BIG_LOTTO,
            eligibility_status=eligibility_status,
            ineligibility_reasons=ineligibility_reasons,
            freeze_artifact_file_sha256=freeze_artifact_file_sha256,
            cohort_membership_strategy_ids_lcj1_sha256=(
                cohort_membership_strategy_ids_lcj1_sha256
            ),
            prediction_record_digest=prediction_record_digest,
            target_registration_digest=target_registration_digest,
            target_scheduled_at=target_scheduled_at,
            prediction_created_at=prediction_created_at,
            eligibility_sealed_at=eligibility_sealed_at,
            pre_outcome_timing_proof_ref=pre_outcome_timing_proof_ref,
            temporal_provenance=temporal_provenance,
            fixed_member_count=FIXED_MEMBER_COUNT,
            canonical_member_order=FIXED_13_COHORT_STRATEGY_IDS,
            observed_member_order=observed_member_order,
            per_member_canonical_tickets=per_member_canonical_tickets,
            k_d=len(distinct_canonical_tickets),
            distinct_canonical_tickets=distinct_canonical_tickets,
            duplicate_groups=duplicate_groups,
            per_member_rng_provenance=per_member_rng_provenance,
        )
        return cls(
            schema_version=FIXED13_PROSPECTIVE_ELIGIBILITY_SCHEMA_VERSION,
            identity=identity,
            official_draw_identity=identity.target_draw_number,
            lottery_type=LotteryType.BIG_LOTTO,
            eligibility_status=eligibility_status,
            ineligibility_reasons=ineligibility_reasons,
            freeze_artifact_file_sha256=freeze_artifact_file_sha256,
            cohort_membership_strategy_ids_lcj1_sha256=(
                cohort_membership_strategy_ids_lcj1_sha256
            ),
            prediction_record_digest=prediction_record_digest,
            target_registration_digest=target_registration_digest,
            target_scheduled_at=target_scheduled_at,
            prediction_created_at=prediction_created_at,
            eligibility_sealed_at=eligibility_sealed_at,
            pre_outcome_timing_proof_ref=pre_outcome_timing_proof_ref,
            temporal_provenance=temporal_provenance,
            fixed_member_count=FIXED_MEMBER_COUNT,
            canonical_member_order=FIXED_13_COHORT_STRATEGY_IDS,
            observed_member_order=observed_member_order,
            per_member_canonical_tickets=per_member_canonical_tickets,
            k_d=len(distinct_canonical_tickets),
            distinct_canonical_tickets=distinct_canonical_tickets,
            duplicate_groups=duplicate_groups,
            per_member_rng_provenance=per_member_rng_provenance,
            eligibility_record_digest=_canonical_sha256(material),
        )

    def canonical_material(self) -> dict[str, object]:
        return _eligibility_material(
            identity=self.identity,
            official_draw_identity=self.official_draw_identity,
            lottery_type=self.lottery_type,
            eligibility_status=self.eligibility_status,
            ineligibility_reasons=self.ineligibility_reasons,
            freeze_artifact_file_sha256=self.freeze_artifact_file_sha256,
            cohort_membership_strategy_ids_lcj1_sha256=(
                self.cohort_membership_strategy_ids_lcj1_sha256
            ),
            prediction_record_digest=self.prediction_record_digest,
            target_registration_digest=self.target_registration_digest,
            target_scheduled_at=self.target_scheduled_at,
            prediction_created_at=self.prediction_created_at,
            eligibility_sealed_at=self.eligibility_sealed_at,
            pre_outcome_timing_proof_ref=self.pre_outcome_timing_proof_ref,
            temporal_provenance=self.temporal_provenance,
            fixed_member_count=self.fixed_member_count,
            canonical_member_order=self.canonical_member_order,
            observed_member_order=self.observed_member_order,
            per_member_canonical_tickets=self.per_member_canonical_tickets,
            k_d=self.k_d,
            distinct_canonical_tickets=self.distinct_canonical_tickets,
            duplicate_groups=self.duplicate_groups,
            per_member_rng_provenance=self.per_member_rng_provenance,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_material(),
            "eligibility_record_digest": self.eligibility_record_digest,
        }

    def validate_against_prediction(self, prediction: PredictionRecord) -> None:
        """Require every prediction-derived field to match one immutable record."""

        if type(prediction) is not PredictionRecord:
            raise ValueError("prediction must be a PredictionRecord")
        if self.identity != prediction.identity:
            raise ValueError("eligibility identity does not match immutable prediction")
        if self.prediction_record_digest != prediction.prediction_hash:
            raise ValueError("eligibility digest link does not match immutable prediction")
        if self.prediction_created_at != prediction.predicted_at:
            raise ValueError("eligibility prediction timestamp does not match immutable prediction")
        if self.temporal_provenance is not prediction.temporal_provenance:
            raise ValueError("eligibility temporal provenance does not match prediction")
        observed_order = tuple(entry.member_id for entry in prediction.entries)
        if self.observed_member_order != observed_order:
            raise ValueError("eligibility observed-member order does not match prediction")

        expected_tickets: list[Fixed13MemberTicket] = []
        for strategy_id in FIXED_13_COHORT_STRATEGY_IDS:
            matches = tuple(
                entry for entry in prediction.entries if entry.member_id == strategy_id
            )
            ticket: tuple[int, ...] | None = None
            if len(matches) == 1:
                entry = matches[0]
                if (
                    entry.availability is PredictionAvailability.AVAILABLE
                    and len(entry.selections) == 1
                    and entry.selections[0].special_number is None
                    and _is_legal_canonical_ticket(entry.selections[0].main_numbers)
                ):
                    ticket = tuple(sorted(entry.selections[0].main_numbers))
            expected_tickets.append(Fixed13MemberTicket(strategy_id, ticket))
        if self.per_member_canonical_tickets != tuple(expected_tickets):
            raise ValueError("eligibility canonical tickets do not match sealed prediction")

        if self.eligibility_status is Fixed13EligibilityStatus.ELIGIBLE:
            if prediction.cohort.authority_sha256 != PINNED_FREEZE_ARTIFACT_FILE_SHA256:
                raise ValueError("eligible prediction is not bound to the pinned freeze")
            if prediction.cohort.member_ids != FIXED_13_COHORT_STRATEGY_IDS:
                raise ValueError("eligible prediction does not contain the frozen cohort")
            if (
                prediction.outcome_presence_at_start
                is not OutcomePresenceAtPrediction.ABSENT
            ):
                raise ValueError("eligible prediction did not begin outcome-absent")
            for item in self.per_member_rng_provenance:
                if item.causal_history_digest != prediction.causal_history.history_sha256:
                    raise ValueError("eligible provenance history digest differs from prediction")
                if item.causal_history_row_count != prediction.causal_history.draw_count:
                    raise ValueError("eligible provenance history count differs from prediction")
                if (
                    item.causal_history_last_draw_identity
                    != prediction.causal_history.last_draw_number
                ):
                    raise ValueError("eligible provenance last draw differs from prediction")

    @classmethod
    def from_canonical_dict(
        cls,
        value: Mapping[str, object],
    ) -> Fixed13ProspectiveEligibilityRecord:
        expected_keys = {
            "canonical_member_order",
            "cohort_membership_strategy_ids_lcj1_sha256",
            "distinct_canonical_tickets",
            "duplicate_groups",
            "eligibility_record_digest",
            "eligibility_sealed_at",
            "eligibility_status",
            "fixed_member_count",
            "freeze_artifact_file_sha256",
            "identity",
            "ineligibility_reasons",
            "k_d",
            "lottery_type",
            "observed_member_order",
            "official_draw_identity",
            "per_member_canonical_tickets",
            "per_member_rng_provenance",
            "pre_outcome_timing_proof_ref",
            "prediction_created_at",
            "prediction_record_digest",
            "schema_version",
            "target_registration_digest",
            "target_scheduled_at",
            "temporal_provenance",
        }
        _expect_keys(value, expected_keys, "eligibility record")
        identity = _identity_from_dict(_object(value["identity"], "identity"))
        timing_value = value["pre_outcome_timing_proof_ref"]
        timing_ref = (
            None
            if timing_value is None
            else PreOutcomeTimingProofRef.from_canonical_dict(
                _object(timing_value, "pre_outcome_timing_proof_ref")
            )
        )
        return cls(
            schema_version=_string(value["schema_version"], "schema_version"),
            identity=identity,
            official_draw_identity=_string(
                value["official_draw_identity"], "official_draw_identity"
            ),
            lottery_type=_lottery_type(value["lottery_type"], "lottery_type"),
            eligibility_status=_eligibility_status(value["eligibility_status"]),
            ineligibility_reasons=tuple(
                _string(item, "ineligibility_reasons item")
                for item in _array(value["ineligibility_reasons"], "ineligibility_reasons")
            ),
            freeze_artifact_file_sha256=_sha256(
                value["freeze_artifact_file_sha256"], "freeze_artifact_file_sha256"
            ),
            cohort_membership_strategy_ids_lcj1_sha256=_sha256(
                value["cohort_membership_strategy_ids_lcj1_sha256"],
                "cohort_membership_strategy_ids_lcj1_sha256",
            ),
            prediction_record_digest=_sha256(
                value["prediction_record_digest"], "prediction_record_digest"
            ),
            target_registration_digest=_sha256(
                value["target_registration_digest"], "target_registration_digest"
            ),
            target_scheduled_at=_datetime(value["target_scheduled_at"], "target_scheduled_at"),
            prediction_created_at=_datetime(
                value["prediction_created_at"], "prediction_created_at"
            ),
            eligibility_sealed_at=_datetime(
                value["eligibility_sealed_at"], "eligibility_sealed_at"
            ),
            pre_outcome_timing_proof_ref=timing_ref,
            temporal_provenance=_temporal_provenance(value["temporal_provenance"]),
            fixed_member_count=_integer(value["fixed_member_count"], "fixed_member_count"),
            canonical_member_order=tuple(
                _string(item, "canonical_member_order item")
                for item in _array(value["canonical_member_order"], "canonical_member_order")
            ),
            observed_member_order=tuple(
                _string(item, "observed_member_order item")
                for item in _array(value["observed_member_order"], "observed_member_order")
            ),
            per_member_canonical_tickets=tuple(
                _member_ticket_from_dict(_object(item, "member ticket"))
                for item in _array(
                    value["per_member_canonical_tickets"], "per_member_canonical_tickets"
                )
            ),
            k_d=_integer(value["k_d"], "k_d"),
            distinct_canonical_tickets=tuple(
                _ticket_from_value(item, "distinct canonical ticket")
                for item in _array(
                    value["distinct_canonical_tickets"], "distinct_canonical_tickets"
                )
            ),
            duplicate_groups=tuple(
                _duplicate_group_from_dict(_object(item, "duplicate group"))
                for item in _array(value["duplicate_groups"], "duplicate_groups")
            ),
            per_member_rng_provenance=tuple(
                _rng_provenance_from_dict(_object(item, "RNG provenance"))
                for item in _array(
                    value["per_member_rng_provenance"], "per_member_rng_provenance"
                )
            ),
            eligibility_record_digest=_sha256(
                value["eligibility_record_digest"], "eligibility_record_digest"
            ),
        )


def build_fixed13_prospective_eligibility(
    *,
    prediction: PredictionRecord,
    target_registration: PreOutcomeTargetRegistration,
    producer_records: tuple[Fixed13ProspectiveProducerRecord, ...],
    freeze_artifact_file_sha256: str,
    cohort_membership_strategy_ids_lcj1_sha256: str,
    eligibility_sealed_at: datetime,
    pre_outcome_timing_proof_ref: PreOutcomeTimingProofRef | None,
) -> Fixed13ProspectiveEligibilityRecord:
    """Derive one deterministic, outcome-free fixed-13 eligibility disposition."""

    if type(prediction) is not PredictionRecord:
        raise ValueError("prediction must be a PredictionRecord")
    if type(target_registration) is not PreOutcomeTargetRegistration:
        raise ValueError("target_registration must be a PreOutcomeTargetRegistration")
    if type(producer_records) is not tuple:
        raise ValueError("producer_records must be a tuple")
    _require_sha256(freeze_artifact_file_sha256, "freeze_artifact_file_sha256")
    _require_sha256(
        cohort_membership_strategy_ids_lcj1_sha256,
        "cohort_membership_strategy_ids_lcj1_sha256",
    )
    _require_utc(eligibility_sealed_at, "eligibility_sealed_at")

    reasons: list[str] = []

    def reject(reason: str, strategy_id: str | None = None) -> None:
        reasons.append(reason if strategy_id is None else f"{reason}:{strategy_id}")

    if freeze_artifact_file_sha256 != PINNED_FREEZE_ARTIFACT_FILE_SHA256:
        reject("FREEZE_ARTIFACT_SHA256_MISMATCH")
    if (
        cohort_membership_strategy_ids_lcj1_sha256
        != PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256
    ):
        reject("COHORT_MEMBERSHIP_SHA256_MISMATCH")
    if prediction.cohort.authority_sha256 != PINNED_FREEZE_ARTIFACT_FILE_SHA256:
        reject("PREDICTION_COHORT_FREEZE_AUTHORITY_MISMATCH")
    if prediction.identity.lottery_type is not LotteryType.BIG_LOTTO:
        reject("PREDICTION_LOTTERY_TYPE_MISMATCH")
    if target_registration.target.lottery_type is not LotteryType.BIG_LOTTO:
        reject("TARGET_LOTTERY_TYPE_MISMATCH")
    if target_registration.target.draw_number != prediction.identity.target_draw_number:
        reject("OFFICIAL_DRAW_IDENTITY_MISMATCH")
    if target_registration.target.draw_date != prediction.identity.target_draw_date:
        reject("TARGET_DRAW_DATE_MISMATCH")
    if target_registration.causal_history != prediction.causal_history:
        reject("PREDICTION_TARGET_CAUSAL_HISTORY_MISMATCH")
    try:
        target_registration_digest_valid = (
            target_registration.registration_digest
            == _canonical_sha256(target_registration.canonical_material())
        )
    except (TypeError, ValueError):
        target_registration_digest_valid = False
    if not target_registration_digest_valid:
        reject("TARGET_REGISTRATION_DIGEST_INVALID")
    try:
        prediction_digest_valid = prediction.prediction_hash == _canonical_sha256(
            prediction.canonical_material()
        )
    except (TypeError, ValueError):
        prediction_digest_valid = False
    if not prediction_digest_valid:
        reject("PREDICTION_RECORD_DIGEST_INVALID")

    recomputed_temporal = classify_temporal_provenance(
        target_date=prediction.identity.target_draw_date,
        frozen_at=prediction.cohort.frozen_at,
        outcome_presence=prediction.outcome_presence_at_start,
    )
    if prediction.temporal_provenance is not recomputed_temporal:
        reject("TEMPORAL_PROVENANCE_SELF_CLASSIFICATION_MISMATCH")
    if recomputed_temporal is not TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE:
        reject("TEMPORAL_PROVENANCE_NOT_PROSPECTIVE")
    if prediction.outcome_presence_at_start is not OutcomePresenceAtPrediction.ABSENT:
        reject("OUTCOME_NOT_ABSENT_AT_PREDICTION")
    if prediction.predicted_at < target_registration.registered_at:
        reject("PREDICTION_PRECEDES_TARGET_REGISTRATION")
    if prediction.predicted_at >= target_registration.announcement.scheduled_at:
        reject("PREDICTION_NOT_BEFORE_TARGET_SCHEDULE")
    if prediction.predicted_at > eligibility_sealed_at:
        reject("PREDICTION_CREATED_AFTER_ELIGIBILITY_SEAL")
    if eligibility_sealed_at >= target_registration.announcement.scheduled_at:
        reject("ELIGIBILITY_NOT_STRICTLY_BEFORE_TARGET_SCHEDULE")

    valid_timing_ref: PreOutcomeTimingProofRef | None
    if pre_outcome_timing_proof_ref is None:
        reject("PRE_OUTCOME_TIMING_PROOF_MISSING")
        valid_timing_ref = None
    elif type(pre_outcome_timing_proof_ref) is not PreOutcomeTimingProofRef or not (
        _is_valid_timing_ref(pre_outcome_timing_proof_ref)
    ):
        reject("PRE_OUTCOME_TIMING_PROOF_INVALID")
        valid_timing_ref = None
    else:
        valid_timing_ref = pre_outcome_timing_proof_ref

    observed_member_order = tuple(entry.member_id for entry in prediction.entries)
    if len(prediction.entries) != FIXED_MEMBER_COUNT:
        reject("FIXED_MEMBER_COUNT_MISMATCH")
    if prediction.cohort.member_ids != FIXED_13_COHORT_STRATEGY_IDS:
        reject("FROZEN_COHORT_MEMBERSHIP_MISMATCH")
    if observed_member_order != FIXED_13_COHORT_STRATEGY_IDS:
        reject("PREDICTION_MEMBER_ORDER_MISMATCH")

    member_tickets: list[Fixed13MemberTicket] = []
    for strategy_id in FIXED_13_COHORT_STRATEGY_IDS:
        matches = tuple(entry for entry in prediction.entries if entry.member_id == strategy_id)
        canonical_ticket: tuple[int, ...] | None = None
        if len(matches) != 1:
            reject("PREDICTION_MEMBER_MISSING_OR_DUPLICATED", strategy_id)
        else:
            entry = matches[0]
            if entry.availability is not PredictionAvailability.AVAILABLE:
                reject("PREDICTION_MEMBER_UNAVAILABLE", strategy_id)
            if len(entry.selections) != 1:
                reject("PREDICTION_SELECTION_COUNT_INVALID", strategy_id)
            else:
                selection = entry.selections[0]
                numbers = selection.main_numbers
                if selection.special_number is not None or not _is_legal_canonical_ticket(numbers):
                    reject("PREDICTION_NATIVE_TICKET_INVALID", strategy_id)
                else:
                    canonical_ticket = tuple(sorted(numbers))
        member_tickets.append(Fixed13MemberTicket(strategy_id, canonical_ticket))

    member_ticket_tuple = tuple(member_tickets)
    distinct_tickets, duplicate_groups = _ticket_aggregates(member_ticket_tuple)
    if not 1 <= len(distinct_tickets) <= FIXED_MEMBER_COUNT:
        reject("DISTINCT_TICKET_COUNT_INVALID")

    typed_producer_records: list[Fixed13ProspectiveProducerRecord] = []
    for index, producer_record in enumerate(producer_records):
        if type(producer_record) is not Fixed13ProspectiveProducerRecord:
            reject("PRODUCER_PROVENANCE_RECORD_INVALID", str(index))
            continue
        typed_producer_records.append(producer_record)
    producer_tuple = tuple(typed_producer_records)
    producer_member_order = tuple(record.strategy_id for record in producer_tuple)
    if len(producer_tuple) != FIXED_MEMBER_COUNT:
        reject("PRODUCER_PROVENANCE_COUNT_MISMATCH")
    if producer_member_order != FIXED_13_COHORT_STRATEGY_IDS:
        reject("PRODUCER_PROVENANCE_MEMBER_ORDER_MISMATCH")

    normalized_provenance: list[Fixed13MemberRngProvenance] = []
    for producer_record in producer_tuple:
        strategy_id = producer_record.strategy_id
        _validate_producer_record(producer_record, prediction, reject)
        normalized_provenance.append(_normalize_producer_record(producer_record))

    final_reasons = tuple(sorted(set(reasons)))
    status = (
        Fixed13EligibilityStatus.ELIGIBLE
        if not final_reasons
        else Fixed13EligibilityStatus.PRE_OUTCOME_INELIGIBLE
    )
    return Fixed13ProspectiveEligibilityRecord.create(
        identity=prediction.identity,
        eligibility_status=status,
        ineligibility_reasons=final_reasons,
        freeze_artifact_file_sha256=freeze_artifact_file_sha256,
        cohort_membership_strategy_ids_lcj1_sha256=(
            cohort_membership_strategy_ids_lcj1_sha256
        ),
        prediction_record_digest=prediction.prediction_hash,
        target_registration_digest=target_registration.registration_digest,
        target_scheduled_at=target_registration.announcement.scheduled_at,
        prediction_created_at=prediction.predicted_at,
        eligibility_sealed_at=eligibility_sealed_at,
        pre_outcome_timing_proof_ref=valid_timing_ref,
        temporal_provenance=prediction.temporal_provenance,
        observed_member_order=observed_member_order,
        per_member_canonical_tickets=member_ticket_tuple,
        distinct_canonical_tickets=distinct_tickets,
        duplicate_groups=duplicate_groups,
        per_member_rng_provenance=tuple(normalized_provenance),
    )


def _validate_producer_record(
    record: Fixed13ProspectiveProducerRecord,
    prediction: PredictionRecord,
    reject: Callable[[str, str | None], None],
) -> None:
    reject_fn = reject
    strategy_id = record.strategy_id
    if strategy_id not in FIXED_13_COHORT_STRATEGY_IDS:
        reject_fn("PRODUCER_STRATEGY_NOT_IN_FROZEN_COHORT", strategy_id)
    if record.official_draw_identity != prediction.identity.target_draw_number:
        reject_fn("PRODUCER_DRAW_IDENTITY_MISMATCH", strategy_id)
    expected_rng = strategy_id in RNG_REQUIRED_STRATEGY_IDS
    if record.rng_policy_id != RNG_POLICY_ID:
        reject_fn("PRODUCER_RNG_POLICY_INVALID", strategy_id)
    if record.rng_domain_tag != RNG_DOMAIN_TAG:
        reject_fn("PRODUCER_RNG_DOMAIN_TAG_INVALID", strategy_id)
    if record.rng_seed_derivation_formula != RNG_SEED_DERIVATION_FORMULA:
        reject_fn("PRODUCER_RNG_SEED_FORMULA_INVALID", strategy_id)
    if type(record.per_member_rng_required) is not bool or (
        record.per_member_rng_required is not expected_rng
    ):
        reject_fn("PRODUCER_RNG_REQUIRED_FLAG_INVALID", strategy_id)
    expected_construction = (
        AdapterConstruction.RNG_INJECTED
        if expected_rng
        else AdapterConstruction.ZERO_ARG_DEFAULT
    )
    if record.per_member_adapter_construction is not expected_construction:
        reject_fn("PRODUCER_ADAPTER_CONSTRUCTION_INVALID", strategy_id)
    if type(record.per_member_adapter_path) is not str or not record.per_member_adapter_path:
        reject_fn("PRODUCER_ADAPTER_PATH_INVALID", strategy_id)
    if expected_rng:
        if not _is_sha256(record.per_member_rng_seed_sha256_hex):
            reject_fn("PRODUCER_RNG_SEED_INVALID", strategy_id)
        if not _is_selfcheck_vector(record.rng_selfcheck_vector):
            reject_fn("PRODUCER_RNG_SELFCHECK_INVALID", strategy_id)
    else:
        if record.per_member_rng_seed_sha256_hex is not None:
            reject_fn("PRODUCER_ZERO_ARG_RNG_SEED_FABRICATED", strategy_id)
        if record.rng_selfcheck_vector is not None:
            reject_fn("PRODUCER_ZERO_ARG_RNG_SELFCHECK_FABRICATED", strategy_id)
    if record.per_member_causal_history_digest != prediction.causal_history.history_sha256:
        reject_fn("PRODUCER_CAUSAL_HISTORY_DIGEST_MISMATCH", strategy_id)
    if record.causal_history_row_count != prediction.causal_history.draw_count:
        reject_fn("PRODUCER_CAUSAL_HISTORY_ROW_COUNT_MISMATCH", strategy_id)
    if record.causal_history_last_draw_identity != prediction.causal_history.last_draw_number:
        reject_fn("PRODUCER_CAUSAL_HISTORY_LAST_DRAW_MISMATCH", strategy_id)
    identity = record.producer_implementation_identity
    if type(identity) is not ProducerImplementationIdentity:
        reject_fn("PRODUCER_IMPLEMENTATION_IDENTITY_INVALID", strategy_id)
    else:
        if _GIT_OBJECT_ID.fullmatch(identity.repository_head) is None:
            reject_fn("PRODUCER_REPOSITORY_HEAD_INVALID", strategy_id)
        if _GIT_OBJECT_ID.fullmatch(identity.repository_tree) is None:
            reject_fn("PRODUCER_REPOSITORY_TREE_INVALID", strategy_id)
        if identity.module_path != _PRODUCER_MODULE_PATH:
            reject_fn("PRODUCER_MODULE_PATH_INVALID", strategy_id)
    if (
        type(record.python_implementation_identity) is not str
        or not record.python_implementation_identity
    ):
        reject_fn("PRODUCER_PYTHON_IDENTITY_INVALID", strategy_id)
    if (
        type(record.historical_r2_ticket_parity_note) is not str
        or not record.historical_r2_ticket_parity_note
    ):
        reject_fn("PRODUCER_HISTORICAL_PARITY_NOTE_INVALID", strategy_id)


def _normalize_producer_record(
    record: Fixed13ProspectiveProducerRecord,
) -> Fixed13MemberRngProvenance:
    construction = record.per_member_adapter_construction
    construction_text = _normalized_text(
        construction.value if type(construction) is AdapterConstruction else construction
    )
    identity = record.producer_implementation_identity
    if type(identity) is ProducerImplementationIdentity:
        repository_head = _normalized_text(identity.repository_head)
        repository_tree = _normalized_text(identity.repository_tree)
        module_path = _normalized_text(identity.module_path)
    else:
        repository_head = "INVALID"
        repository_tree = "INVALID"
        module_path = "INVALID"
    selfcheck = record.rng_selfcheck_vector
    normalized_selfcheck = (
        cast(tuple[float, ...], selfcheck)
        if type(selfcheck) is tuple
        and all(type(value) is float and math.isfinite(value) for value in selfcheck)
        else None
    )
    seed = record.per_member_rng_seed_sha256_hex
    normalized_seed = (
        None if seed is None else _normalized_text(seed)
    )
    return Fixed13MemberRngProvenance(
        strategy_id=_normalized_text(record.strategy_id),
        adapter_path=_normalized_text(record.per_member_adapter_path),
        adapter_construction=construction_text,
        per_member_rng_required=(
            record.per_member_rng_required
            if type(record.per_member_rng_required) is bool
            else False
        ),
        rng_policy_id=_normalized_text(record.rng_policy_id),
        rng_domain_tag=_normalized_text(record.rng_domain_tag),
        rng_seed_derivation_formula=_normalized_text(record.rng_seed_derivation_formula),
        rng_seed_sha256_hex=normalized_seed,
        causal_history_digest=_normalized_text(record.per_member_causal_history_digest),
        causal_history_row_count=(
            record.causal_history_row_count
            if type(record.causal_history_row_count) is int
            else -1
        ),
        causal_history_last_draw_identity=_normalized_text(
            record.causal_history_last_draw_identity
        ),
        producer_repository_head=repository_head,
        producer_repository_tree=repository_tree,
        producer_module_path=module_path,
        python_implementation_identity=_normalized_text(
            record.python_implementation_identity
        ),
        rng_selfcheck_vector=normalized_selfcheck,
        historical_r2_ticket_parity_note=_normalized_text(
            record.historical_r2_ticket_parity_note
        ),
    )


def _normalized_text(value: object) -> str:
    return value if type(value) is str and value else "INVALID"


def _eligibility_material(
    *,
    identity: ProspectiveObservationIdentity,
    official_draw_identity: str,
    lottery_type: LotteryType,
    eligibility_status: Fixed13EligibilityStatus,
    ineligibility_reasons: tuple[str, ...],
    freeze_artifact_file_sha256: str,
    cohort_membership_strategy_ids_lcj1_sha256: str,
    prediction_record_digest: str,
    target_registration_digest: str,
    target_scheduled_at: datetime,
    prediction_created_at: datetime,
    eligibility_sealed_at: datetime,
    pre_outcome_timing_proof_ref: PreOutcomeTimingProofRef | None,
    temporal_provenance: TemporalProvenance,
    fixed_member_count: int,
    canonical_member_order: tuple[str, ...],
    observed_member_order: tuple[str, ...],
    per_member_canonical_tickets: tuple[Fixed13MemberTicket, ...],
    k_d: int,
    distinct_canonical_tickets: tuple[tuple[int, ...], ...],
    duplicate_groups: tuple[Fixed13DuplicateGroup, ...],
    per_member_rng_provenance: tuple[Fixed13MemberRngProvenance, ...],
) -> dict[str, object]:
    return {
        "canonical_member_order": list(canonical_member_order),
        "cohort_membership_strategy_ids_lcj1_sha256": (
            cohort_membership_strategy_ids_lcj1_sha256
        ),
        "distinct_canonical_tickets": [list(ticket) for ticket in distinct_canonical_tickets],
        "duplicate_groups": [group.canonical_dict() for group in duplicate_groups],
        "eligibility_sealed_at": _utc_text(eligibility_sealed_at),
        "eligibility_status": eligibility_status.value,
        "fixed_member_count": fixed_member_count,
        "freeze_artifact_file_sha256": freeze_artifact_file_sha256,
        "identity": identity.canonical_dict(),
        "ineligibility_reasons": list(ineligibility_reasons),
        "k_d": k_d,
        "lottery_type": lottery_type.value,
        "observed_member_order": list(observed_member_order),
        "official_draw_identity": official_draw_identity,
        "per_member_canonical_tickets": [
            item.canonical_dict() for item in per_member_canonical_tickets
        ],
        "per_member_rng_provenance": [
            item.canonical_dict() for item in per_member_rng_provenance
        ],
        "pre_outcome_timing_proof_ref": (
            pre_outcome_timing_proof_ref.canonical_dict()
            if pre_outcome_timing_proof_ref is not None
            else None
        ),
        "prediction_created_at": _utc_text(prediction_created_at),
        "prediction_record_digest": prediction_record_digest,
        "schema_version": FIXED13_PROSPECTIVE_ELIGIBILITY_SCHEMA_VERSION,
        "target_registration_digest": target_registration_digest,
        "target_scheduled_at": _utc_text(target_scheduled_at),
        "temporal_provenance": temporal_provenance.value,
    }


def _validate_eligible_record(record: Fixed13ProspectiveEligibilityRecord) -> None:
    if record.freeze_artifact_file_sha256 != PINNED_FREEZE_ARTIFACT_FILE_SHA256:
        raise ValueError("ELIGIBLE requires the pinned freeze artifact digest")
    if (
        record.cohort_membership_strategy_ids_lcj1_sha256
        != PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256
    ):
        raise ValueError("ELIGIBLE requires the pinned cohort-membership digest")
    timing_ref = record.pre_outcome_timing_proof_ref
    if timing_ref is None or not _is_valid_timing_ref(timing_ref):
        raise ValueError("ELIGIBLE requires a structurally valid timing-proof reference")
    if record.temporal_provenance is not TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE:
        raise ValueError("ELIGIBLE requires prospective temporal provenance")
    if record.eligibility_sealed_at >= record.target_scheduled_at:
        raise ValueError("ELIGIBLE must be sealed strictly before target_scheduled_at")
    if record.prediction_created_at >= record.target_scheduled_at:
        raise ValueError("ELIGIBLE prediction must precede target_scheduled_at")
    if record.prediction_created_at > record.eligibility_sealed_at:
        raise ValueError("ELIGIBLE prediction must exist before the eligibility seal")
    if record.observed_member_order != FIXED_13_COHORT_STRATEGY_IDS:
        raise ValueError("ELIGIBLE requires the exact frozen prediction-member order")

    history_identities: set[tuple[str, int, str]] = set()
    for item, strategy_id in zip(
        record.per_member_rng_provenance,
        FIXED_13_COHORT_STRATEGY_IDS,
        strict=True,
    ):
        expected_rng = strategy_id in RNG_REQUIRED_STRATEGY_IDS
        expected_construction = (
            AdapterConstruction.RNG_INJECTED.value
            if expected_rng
            else AdapterConstruction.ZERO_ARG_DEFAULT.value
        )
        if item.strategy_id != strategy_id:
            raise ValueError("ELIGIBLE provenance strategy order differs from fixed-13")
        if item.rng_policy_id != RNG_POLICY_ID or item.rng_domain_tag != RNG_DOMAIN_TAG:
            raise ValueError("ELIGIBLE provenance carries an invalid RNG policy identity")
        if item.rng_seed_derivation_formula != RNG_SEED_DERIVATION_FORMULA:
            raise ValueError("ELIGIBLE provenance carries an invalid RNG seed formula")
        if item.per_member_rng_required is not expected_rng:
            raise ValueError("ELIGIBLE provenance carries an invalid RNG-required flag")
        if item.adapter_construction != expected_construction:
            raise ValueError("ELIGIBLE provenance carries an invalid adapter construction")
        if not item.adapter_path:
            raise ValueError("ELIGIBLE provenance requires an adapter path")
        if expected_rng:
            if not _is_sha256(item.rng_seed_sha256_hex):
                raise ValueError("ELIGIBLE stochastic provenance requires a valid RNG seed")
            if not _is_selfcheck_vector(item.rng_selfcheck_vector):
                raise ValueError("ELIGIBLE stochastic provenance requires a selfcheck vector")
        elif item.rng_seed_sha256_hex is not None or item.rng_selfcheck_vector is not None:
            raise ValueError("ELIGIBLE zero-arg provenance must not fabricate RNG authority")
        if not _is_sha256(item.causal_history_digest):
            raise ValueError("ELIGIBLE provenance requires a causal-history digest")
        if item.causal_history_row_count <= 0 or not item.causal_history_last_draw_identity:
            raise ValueError("ELIGIBLE provenance requires non-empty causal-history identity")
        history_identities.add(
            (
                item.causal_history_digest,
                item.causal_history_row_count,
                item.causal_history_last_draw_identity,
            )
        )
        if _GIT_OBJECT_ID.fullmatch(item.producer_repository_head) is None:
            raise ValueError("ELIGIBLE provenance requires a producer repository HEAD")
        if _GIT_OBJECT_ID.fullmatch(item.producer_repository_tree) is None:
            raise ValueError("ELIGIBLE provenance requires a producer repository tree")
        if item.producer_module_path != _PRODUCER_MODULE_PATH:
            raise ValueError("ELIGIBLE provenance requires the verified producer module")
        if not item.python_implementation_identity or not item.historical_r2_ticket_parity_note:
            raise ValueError("ELIGIBLE provenance requires complete implementation metadata")
    if len(history_identities) != 1:
        raise ValueError("ELIGIBLE requires one shared causal-history identity")


def _ticket_aggregates(
    member_tickets: tuple[Fixed13MemberTicket, ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[Fixed13DuplicateGroup, ...]]:
    members_by_ticket: dict[tuple[int, ...], list[str]] = {}
    for item in member_tickets:
        if item.canonical_ticket is None:
            continue
        members_by_ticket.setdefault(item.canonical_ticket, []).append(item.strategy_id)
    distinct = tuple(sorted(members_by_ticket))
    duplicates = tuple(
        Fixed13DuplicateGroup(ticket, tuple(members_by_ticket[ticket]))
        for ticket in distinct
        if len(members_by_ticket[ticket]) > 1
    )
    return distinct, duplicates


def _is_legal_canonical_ticket(value: object) -> bool:
    if type(value) is not tuple:
        return False
    raw = cast(tuple[object, ...], value)
    if len(raw) != 6 or not all(type(number) is int for number in raw):
        return False
    numbers = cast(tuple[int, ...], raw)
    return (
        all(1 <= number <= 49 for number in numbers)
        and numbers == tuple(sorted(numbers))
        and len(set(numbers)) == 6
    )


def _is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _is_selfcheck_vector(value: object) -> bool:
    return (
        type(value) is tuple
        and len(cast(tuple[object, ...], value)) == 3
        and all(
            type(item) is float and math.isfinite(item)
            for item in cast(tuple[object, ...], value)
        )
    )


def _is_valid_timing_ref(value: PreOutcomeTimingProofRef) -> bool:
    return (
        type(value.proof_type) is str
        and bool(value.proof_type)
        and type(value.reference) is str
        and bool(value.reference)
        and _is_sha256(value.reference_sha256)
    )


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty exact string")


def _require_sha256(value: object, label: str) -> None:
    if not _is_sha256(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_utc(value: object, label: str) -> None:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _expect_exact(value: object, expected: str, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} must equal {expected}")


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _array(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return cast(Sequence[object], value)


def _string(value: object, label: str) -> str:
    _require_text(value, label)
    return cast(str, value)


def _sha256(value: object, label: str) -> str:
    _require_sha256(value, label)
    return cast(str, value)


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact integer")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be an exact boolean")
    return value


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


def _lottery_type(value: object, label: str) -> LotteryType:
    try:
        return LotteryType(_string(value, label))
    except ValueError as exc:
        raise ValueError(f"{label} is unsupported") from exc


def _eligibility_status(value: object) -> Fixed13EligibilityStatus:
    try:
        return Fixed13EligibilityStatus(_string(value, "eligibility_status"))
    except ValueError as exc:
        raise ValueError("eligibility_status is unsupported") from exc


def _temporal_provenance(value: object) -> TemporalProvenance:
    try:
        return TemporalProvenance(_string(value, "temporal_provenance"))
    except ValueError as exc:
        raise ValueError("temporal_provenance is unsupported") from exc


def _identity_from_dict(value: Mapping[str, object]) -> ProspectiveObservationIdentity:
    _expect_keys(
        value,
        {
            "cohort_id",
            "cohort_version",
            "lottery_type",
            "target_draw_date",
            "target_draw_number",
        },
        "identity",
    )
    return ProspectiveObservationIdentity(
        lottery_type=_lottery_type(value["lottery_type"], "identity.lottery_type"),
        cohort_id=_string(value["cohort_id"], "identity.cohort_id"),
        cohort_version=_string(value["cohort_version"], "identity.cohort_version"),
        target_draw_number=_string(
            value["target_draw_number"], "identity.target_draw_number"
        ),
        target_draw_date=_date(value["target_draw_date"], "identity.target_draw_date"),
    )


def _ticket_from_value(value: object, label: str) -> tuple[int, ...]:
    return tuple(_integer(item, f"{label} item") for item in _array(value, label))


def _member_ticket_from_dict(value: Mapping[str, object]) -> Fixed13MemberTicket:
    _expect_keys(value, {"canonical_ticket", "strategy_id"}, "member ticket")
    ticket_value = value["canonical_ticket"]
    return Fixed13MemberTicket(
        strategy_id=_string(value["strategy_id"], "member ticket strategy_id"),
        canonical_ticket=(
            None
            if ticket_value is None
            else _ticket_from_value(ticket_value, "member canonical_ticket")
        ),
    )


def _duplicate_group_from_dict(value: Mapping[str, object]) -> Fixed13DuplicateGroup:
    _expect_keys(value, {"canonical_ticket", "member_ids"}, "duplicate group")
    return Fixed13DuplicateGroup(
        canonical_ticket=_ticket_from_value(
            value["canonical_ticket"], "duplicate group canonical_ticket"
        ),
        member_ids=tuple(
            _string(item, "duplicate group member_id")
            for item in _array(value["member_ids"], "duplicate group member_ids")
        ),
    )


def _rng_provenance_from_dict(value: Mapping[str, object]) -> Fixed13MemberRngProvenance:
    expected = {
        "adapter_construction",
        "adapter_path",
        "causal_history_digest",
        "causal_history_last_draw_identity",
        "causal_history_row_count",
        "historical_r2_ticket_parity_note",
        "per_member_rng_required",
        "producer_module_path",
        "producer_repository_head",
        "producer_repository_tree",
        "python_implementation_identity",
        "rng_domain_tag",
        "rng_policy_id",
        "rng_seed_derivation_formula",
        "rng_seed_sha256_hex",
        "rng_selfcheck_vector",
        "strategy_id",
    }
    _expect_keys(value, expected, "RNG provenance")
    seed_value = value["rng_seed_sha256_hex"]
    selfcheck_value = value["rng_selfcheck_vector"]
    return Fixed13MemberRngProvenance(
        strategy_id=_string(value["strategy_id"], "RNG provenance strategy_id"),
        adapter_path=_string(value["adapter_path"], "RNG provenance adapter_path"),
        adapter_construction=_string(
            value["adapter_construction"], "RNG provenance adapter_construction"
        ),
        per_member_rng_required=_boolean(
            value["per_member_rng_required"], "RNG provenance per_member_rng_required"
        ),
        rng_policy_id=_string(value["rng_policy_id"], "RNG provenance rng_policy_id"),
        rng_domain_tag=_string(value["rng_domain_tag"], "RNG provenance rng_domain_tag"),
        rng_seed_derivation_formula=_string(
            value["rng_seed_derivation_formula"],
            "RNG provenance rng_seed_derivation_formula",
        ),
        rng_seed_sha256_hex=(
            None
            if seed_value is None
            else _string(seed_value, "RNG provenance rng_seed_sha256_hex")
        ),
        causal_history_digest=_string(
            value["causal_history_digest"], "RNG provenance causal_history_digest"
        ),
        causal_history_row_count=_integer(
            value["causal_history_row_count"], "RNG provenance causal_history_row_count"
        ),
        causal_history_last_draw_identity=_string(
            value["causal_history_last_draw_identity"],
            "RNG provenance causal_history_last_draw_identity",
        ),
        producer_repository_head=_string(
            value["producer_repository_head"], "RNG provenance producer_repository_head"
        ),
        producer_repository_tree=_string(
            value["producer_repository_tree"], "RNG provenance producer_repository_tree"
        ),
        producer_module_path=_string(
            value["producer_module_path"], "RNG provenance producer_module_path"
        ),
        python_implementation_identity=_string(
            value["python_implementation_identity"],
            "RNG provenance python_implementation_identity",
        ),
        rng_selfcheck_vector=(
            None
            if selfcheck_value is None
            else tuple(
                _float(item, "RNG provenance rng_selfcheck_vector item")
                for item in _array(
                    selfcheck_value, "RNG provenance rng_selfcheck_vector"
                )
            )
        ),
        historical_r2_ticket_parity_note=_string(
            value["historical_r2_ticket_parity_note"],
            "RNG provenance historical_r2_ticket_parity_note",
        ),
    )


def _float(value: object, label: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite binary float")
    return value


__all__ = [
    "FIXED13_PROSPECTIVE_ELIGIBILITY_SCHEMA_VERSION",
    "FIXED_MEMBER_COUNT",
    "PINNED_COHORT_MEMBERSHIP_STRATEGY_IDS_LCJ1_SHA256",
    "PINNED_FREEZE_ARTIFACT_FILE_SHA256",
    "PRE_OUTCOME_TIMING_PROOF_REF_SCHEMA_VERSION",
    "Fixed13DuplicateGroup",
    "Fixed13EligibilityStatus",
    "Fixed13MemberRngProvenance",
    "Fixed13MemberTicket",
    "Fixed13ProspectiveEligibilityRecord",
    "PreOutcomeTimingProofRef",
    "build_fixed13_prospective_eligibility",
]
