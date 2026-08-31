"""Immutable P4 attribution contracts for sealed Next-Draw recommendations.

The P4 artifact is deliberately downstream of the recommendation seal.  It
contains only tickets that were already present in a verified V1/V2 seal and
their deterministic BIG_LOTTO prize evaluation against one exact official
``DRAW_DATA_V3`` outcome.  Ranking, strategy execution, and ticket generation
are not represented by this module and cannot be invoked through its types.
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
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.next_draw_recommendation import (
    NATIVE_TICKET_COUNT_BUCKETS,
    TOP_N,
    BucketAvailabilityStatus,
    bucket_availability,
)
from lottolab.domain.next_draw_recommendation_seal import (
    SealedRecommendationBucket,
    TicketSealStatus,
)
from lottolab.domain.prospective_observer import ObservationTarget

NEXT_DRAW_P4_ATTRIBUTION_SCHEMA_VERSION = "LOTTOLAB_NEXT_DRAW_P4_ATTRIBUTION_V1"
NEXT_DRAW_RECOMMENDATION_SEAL_V1 = "LOTTOLAB_NEXT_DRAW_RECOMMENDATION_SEAL_V1"
NEXT_DRAW_RECOMMENDATION_SEAL_V2 = "LOTTOLAB_NEXT_DRAW_RECOMMENDATION_SEAL_V2"
SUPPORTED_NEXT_DRAW_RECOMMENDATION_SEAL_VERSIONS = (
    NEXT_DRAW_RECOMMENDATION_SEAL_V1,
    NEXT_DRAW_RECOMMENDATION_SEAL_V2,
)
BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_ID = "BIG_LOTTO_PRIZE_EVALUATION_V1"
BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256 = (
    "481bc001d2a92e6b8b7df7dc5b07d9615383cfb89d2ebe2fb2c8881bd944bfa4"
)

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", flags=re.ASCII)


class NextDrawOutcomeAttributionContractError(ValueError):
    """A P4 artifact, verified input, or nested projection violates the contract."""


class NextDrawOutcomeAttributionTamperError(NextDrawOutcomeAttributionContractError):
    """A declared P4 or official-outcome self hash does not match its content."""


class NextDrawP4PersistenceOutcome(StrEnum):
    """Closed result of one create-once P4 persistence attempt."""

    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    CONFLICT = "CONFLICT"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _require_sha256(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise NextDrawOutcomeAttributionContractError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _require_text(value: object, label: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value) or value != value.strip():
        raise NextDrawOutcomeAttributionContractError(f"{label} must be canonical text")
    return value


def _require_utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise NextDrawOutcomeAttributionContractError(f"{label} must be a UTC datetime")
    return value


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _validate_big_lotto_main_numbers(main_numbers: tuple[int, ...], *, label: str) -> None:
    rule = BIG_LOTTO_RULE_CONTRACT
    if type(main_numbers) is not tuple or len(main_numbers) != rule.main_number_count:
        raise NextDrawOutcomeAttributionContractError(
            f"{label}.main_numbers must contain exactly {rule.main_number_count} numbers"
        )
    if any(type(number) is not int for number in main_numbers):
        raise NextDrawOutcomeAttributionContractError(
            f"{label}.main_numbers must contain exact integers"
        )
    if any(not rule.main_number_min <= number <= rule.main_number_max for number in main_numbers):
        raise NextDrawOutcomeAttributionContractError(
            f"{label}.main_numbers contains an out-of-range number"
        )
    if len(set(main_numbers)) != len(main_numbers) or main_numbers != tuple(sorted(main_numbers)):
        raise NextDrawOutcomeAttributionContractError(
            f"{label}.main_numbers must be unique and in ascending order"
        )


def _validate_big_lotto_numbers(
    main_numbers: tuple[int, ...], special_number: int, *, label: str
) -> None:
    _validate_big_lotto_main_numbers(main_numbers, label=label)
    rule = BIG_LOTTO_RULE_CONTRACT
    if type(special_number) is not int or not (
        rule.special_number_min <= special_number <= rule.special_number_max
    ):
        raise NextDrawOutcomeAttributionContractError(f"{label}.special_number is invalid")
    if not rule.main_special_overlap_allowed and special_number in main_numbers:
        raise NextDrawOutcomeAttributionContractError(
            f"{label}.special_number must not overlap main_numbers"
        )


def compute_draw_data_v3_normalized_record_hash(
    *,
    lottery_type: LotteryType,
    draw_number: str,
    draw_date_value: date,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
) -> str:
    """Recompute the exact normalized-record hash used by DRAW_DATA_V3 imports."""

    if type(lottery_type) is not LotteryType:
        raise NextDrawOutcomeAttributionContractError("lottery_type must be a LotteryType")
    if type(draw_number) is not str or _DRAW_NUMBER.fullmatch(draw_number) is None:
        raise NextDrawOutcomeAttributionContractError("draw_number is invalid")
    if type(draw_date_value) is not date:
        raise NextDrawOutcomeAttributionContractError("draw_date must be a date")
    payload = {
        "draw_date": draw_date_value.isoformat(),
        "draw_number": draw_number,
        "lottery_type": lottery_type.value,
        "main_numbers": main_numbers,
        "special_numbers": special_numbers,
    }
    return _canonical_sha256(payload)


def current_big_lotto_prize_evaluation_contract_sha256() -> str:
    """Hash the committed BIG_LOTTO rule contract used by the evaluator."""

    return hashlib.sha256(BIG_LOTTO_RULE_CONTRACT.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VerifiedNextDrawRecommendationSeal:
    """Normalized, read-only authority produced after raw V1/V2 seal verification."""

    schema_version: str
    target: ObservationTarget
    source_head: str | None
    source_tree: str | None
    buckets: tuple[SealedRecommendationBucket, ...]
    seal_digest: str
    seal_file_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_NEXT_DRAW_RECOMMENDATION_SEAL_VERSIONS:
            raise NextDrawOutcomeAttributionContractError("unsupported seal schema_version")
        if type(self.target) is not ObservationTarget:
            raise NextDrawOutcomeAttributionContractError("seal target must be canonical")
        _require_sha256(self.seal_digest, "seal_digest")
        _require_sha256(self.seal_file_sha256, "seal_file_sha256")
        source_values = (self.source_head, self.source_tree)
        if self.schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_V1:
            if source_values != (None, None):
                raise NextDrawOutcomeAttributionContractError(
                    "V1 seals must remain V1 and cannot synthesize V2 source Git fields"
                )
        elif any(value is None for value in source_values):
            raise NextDrawOutcomeAttributionContractError(
                "V2 seals must carry both source_head and source_tree"
            )
        else:
            for label, value in zip(("source_head", "source_tree"), source_values, strict=True):
                if (
                    type(value) is not str
                    or _GIT_OBJECT_ID.fullmatch(value) is None
                    or value == "0" * len(value)
                ):
                    raise NextDrawOutcomeAttributionContractError(
                        f"{label} must be a full non-placeholder Git object ID"
                    )
        counts = tuple(bucket.native_ticket_count for bucket in self.buckets)
        if counts != NATIVE_TICKET_COUNT_BUCKETS:
            raise NextDrawOutcomeAttributionContractError(
                "seal buckets must cover the exact six-bucket universe in order"
            )
        for bucket in self.buckets:
            _validate_verified_seal_bucket(bucket, schema_version=self.schema_version)


def _validate_verified_seal_bucket(
    bucket: SealedRecommendationBucket, *, schema_version: str
) -> None:
    try:
        availability = BucketAvailabilityStatus(bucket.availability)
    except ValueError as exc:
        raise NextDrawOutcomeAttributionContractError(
            "seal bucket availability is unsupported"
        ) from exc
    expected = bucket_availability(bucket.total_candidate_count)
    if availability is not expected:
        raise NextDrawOutcomeAttributionContractError(
            "seal bucket availability contradicts total_candidate_count"
        )
    expected_ranked = min(bucket.total_candidate_count, TOP_N)
    if schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_V1:
        # V1 retains the full ranked list; candidate-pool metadata can include
        # excluded candidates, which must never become fabricated seal children.
        expected_ranked = min(len(bucket.ranked_strategy_ids), TOP_N)
    elif len(bucket.ranked_strategy_ids) != expected_ranked:
        raise NextDrawOutcomeAttributionContractError(
            "seal bucket ranked_strategy_ids do not cover the frozen top-N projection"
        )
    if len(bucket.sealed_tickets) != expected_ranked:
        raise NextDrawOutcomeAttributionContractError(
            "seal bucket must preserve one ticket status for every strategy in its top-N prefix"
        )
    if availability is BucketAvailabilityStatus.UNAVAILABLE and bucket.sealed_tickets:
        raise NextDrawOutcomeAttributionContractError(
            "an UNAVAILABLE seal bucket cannot carry scoreable children"
        )
    for strategy in bucket.sealed_tickets:
        if strategy.status is TicketSealStatus.OK:
            if len(strategy.tickets) != bucket.native_ticket_count:
                raise NextDrawOutcomeAttributionContractError(
                    "an OK seal child must carry its bucket's exact native ticket count"
                )
            for ticket in strategy.tickets:
                _validate_big_lotto_main_numbers(ticket, label="seal_ticket")


@dataclass(frozen=True, slots=True)
class NextDrawOfficialOutcomeProvenance:
    """Successful DRAW_DATA_V3 ingestion provenance for one exact outcome row."""

    ingestion_run_id: str
    operation_type: str
    status: str
    source_filename: str
    source_sha256: str
    parser_version: str
    completed_at: datetime
    source_name: str | None
    source_reference: str | None

    def __post_init__(self) -> None:
        for label, value in (
            ("ingestion_run_id", self.ingestion_run_id),
            ("operation_type", self.operation_type),
            ("source_filename", self.source_filename),
            ("parser_version", self.parser_version),
        ):
            _require_text(value, label)
        if self.status != "SUCCESS":
            raise NextDrawOutcomeAttributionContractError(
                "official outcome provenance must come from a SUCCESS ingestion run"
            )
        _require_sha256(self.source_sha256, "source_sha256")
        _require_utc(self.completed_at, "completed_at")
        for label, value in (
            ("source_name", self.source_name),
            ("source_reference", self.source_reference),
        ):
            if value is not None:
                _require_text(value, label)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "completed_at": _utc_text(self.completed_at),
            "ingestion_run_id": self.ingestion_run_id,
            "operation_type": self.operation_type,
            "parser_version": self.parser_version,
            "source_filename": self.source_filename,
            "source_name": self.source_name,
            "source_reference": self.source_reference,
            "source_sha256": self.source_sha256,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class NextDrawOfficialOutcome:
    """Exact, legal, self-hashed official outcome read from DRAW_DATA_V3."""

    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    winning_main_numbers: tuple[int, ...]
    winning_special_number: int
    normalized_record_hash: str
    provenance: NextDrawOfficialOutcomeProvenance
    outcome_sha256: str

    @classmethod
    def create(
        cls,
        *,
        lottery_type: LotteryType,
        draw_number: str,
        draw_date: date,
        winning_main_numbers: tuple[int, ...],
        winning_special_number: int,
        normalized_record_hash: str,
        provenance: NextDrawOfficialOutcomeProvenance,
    ) -> NextDrawOfficialOutcome:
        material = _official_outcome_material(
            lottery_type=lottery_type,
            draw_number=draw_number,
            draw_date=draw_date,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
            normalized_record_hash=normalized_record_hash,
            provenance=provenance,
        )
        return cls(
            lottery_type=lottery_type,
            draw_number=draw_number,
            draw_date=draw_date,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
            normalized_record_hash=normalized_record_hash,
            provenance=provenance,
            outcome_sha256=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise NextDrawOutcomeAttributionContractError(
                "P4 scoring supports the frozen BIG_LOTTO contract only"
            )
        if _DRAW_NUMBER.fullmatch(self.draw_number) is None:
            raise NextDrawOutcomeAttributionContractError("outcome draw_number is invalid")
        if type(self.draw_date) is not date:
            raise NextDrawOutcomeAttributionContractError("outcome draw_date is invalid")
        _validate_big_lotto_numbers(
            self.winning_main_numbers,
            self.winning_special_number,
            label="official_outcome",
        )
        expected_record_hash = compute_draw_data_v3_normalized_record_hash(
            lottery_type=self.lottery_type,
            draw_number=self.draw_number,
            draw_date_value=self.draw_date,
            main_numbers=self.winning_main_numbers,
            special_numbers=(self.winning_special_number,),
        )
        if self.normalized_record_hash != expected_record_hash:
            raise NextDrawOutcomeAttributionTamperError(
                "official outcome normalized_record_hash does not match its canonical fields"
            )
        _require_sha256(self.outcome_sha256, "outcome_sha256")
        if self.outcome_sha256 != _canonical_sha256(self.canonical_material()):
            raise NextDrawOutcomeAttributionTamperError(
                "official outcome self hash does not match its canonical material"
            )

    def canonical_material(self) -> dict[str, object]:
        return _official_outcome_material(
            lottery_type=self.lottery_type,
            draw_number=self.draw_number,
            draw_date=self.draw_date,
            winning_main_numbers=self.winning_main_numbers,
            winning_special_number=self.winning_special_number,
            normalized_record_hash=self.normalized_record_hash,
            provenance=self.provenance,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "outcome_sha256": self.outcome_sha256}

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> NextDrawOfficialOutcome:
        mapping = _mapping(value, "official_outcome")
        _expect_keys(
            mapping,
            {
                "draw_date",
                "draw_number",
                "lottery_type",
                "normalized_record_hash",
                "outcome_sha256",
                "provenance",
                "winning_main_numbers",
                "winning_special_number",
            },
            "official_outcome",
        )
        provenance = _provenance_from_dict(mapping["provenance"])
        return cls(
            lottery_type=_lottery_type(mapping["lottery_type"]),
            draw_number=_string(mapping["draw_number"], "official_outcome.draw_number"),
            draw_date=_date(mapping["draw_date"], "official_outcome.draw_date"),
            winning_main_numbers=_int_tuple(
                mapping["winning_main_numbers"], "official_outcome.winning_main_numbers"
            ),
            winning_special_number=_int(
                mapping["winning_special_number"], "official_outcome.winning_special_number"
            ),
            normalized_record_hash=_sha256(
                mapping["normalized_record_hash"], "official_outcome.normalized_record_hash"
            ),
            provenance=provenance,
            outcome_sha256=_sha256(
                mapping["outcome_sha256"], "official_outcome.outcome_sha256"
            ),
        )


def _official_outcome_material(
    *,
    lottery_type: LotteryType,
    draw_number: str,
    draw_date: date,
    winning_main_numbers: tuple[int, ...],
    winning_special_number: int,
    normalized_record_hash: str,
    provenance: NextDrawOfficialOutcomeProvenance,
) -> dict[str, object]:
    return {
        "draw_date": draw_date.isoformat(),
        "draw_number": draw_number,
        "lottery_type": lottery_type.value,
        "normalized_record_hash": normalized_record_hash,
        "provenance": provenance.canonical_dict(),
        "winning_main_numbers": list(winning_main_numbers),
        "winning_special_number": winning_special_number,
    }


@dataclass(frozen=True, slots=True)
class NextDrawTicketOutcomeAttribution:
    """One already-sealed ticket's deterministic BIG_LOTTO prize evaluation."""

    ticket_position: int
    predicted_main_numbers: tuple[int, ...]
    is_winner: bool
    prize_tier: str | None
    main_number_hit_count: int
    special_number_hit: bool
    prize_rule_version: str
    prize_rule_provenance: str

    def __post_init__(self) -> None:
        if type(self.ticket_position) is not int or self.ticket_position < 1:
            raise NextDrawOutcomeAttributionContractError("ticket_position must be >= 1")
        _validate_big_lotto_main_numbers(
            self.predicted_main_numbers, label="predicted_ticket"
        )
        if type(self.is_winner) is not bool:
            raise NextDrawOutcomeAttributionContractError("is_winner must be a bool")
        if self.prize_tier is not None:
            _require_text(self.prize_tier, "prize_tier")
        if self.is_winner != (self.prize_tier is not None):
            raise NextDrawOutcomeAttributionContractError(
                "is_winner and prize_tier presence must agree"
            )
        if (
            type(self.main_number_hit_count) is not int
            or not 0 <= self.main_number_hit_count <= 6
        ):
            raise NextDrawOutcomeAttributionContractError(
                "main_number_hit_count must be between 0 and 6"
            )
        if type(self.special_number_hit) is not bool:
            raise NextDrawOutcomeAttributionContractError("special_number_hit must be a bool")
        _require_text(self.prize_rule_version, "prize_rule_version")
        _require_text(self.prize_rule_provenance, "prize_rule_provenance")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "is_winner": self.is_winner,
            "main_number_hit_count": self.main_number_hit_count,
            "predicted_main_numbers": list(self.predicted_main_numbers),
            "prize_rule_provenance": self.prize_rule_provenance,
            "prize_rule_version": self.prize_rule_version,
            "prize_tier": self.prize_tier,
            "special_number_hit": self.special_number_hit,
            "ticket_position": self.ticket_position,
        }

    @classmethod
    def from_canonical_dict(
        cls, value: Mapping[str, object]
    ) -> NextDrawTicketOutcomeAttribution:
        mapping = _mapping(value, "ticket_attribution")
        _expect_keys(
            mapping,
            {
                "is_winner",
                "main_number_hit_count",
                "predicted_main_numbers",
                "prize_rule_provenance",
                "prize_rule_version",
                "prize_tier",
                "special_number_hit",
                "ticket_position",
            },
            "ticket_attribution",
        )
        return cls(
            ticket_position=_int(mapping["ticket_position"], "ticket_position"),
            predicted_main_numbers=_int_tuple(
                mapping["predicted_main_numbers"], "predicted_main_numbers"
            ),
            is_winner=_bool(mapping["is_winner"], "is_winner"),
            prize_tier=_optional_string(mapping["prize_tier"], "prize_tier"),
            main_number_hit_count=_int(
                mapping["main_number_hit_count"], "main_number_hit_count"
            ),
            special_number_hit=_bool(mapping["special_number_hit"], "special_number_hit"),
            prize_rule_version=_string(mapping["prize_rule_version"], "prize_rule_version"),
            prize_rule_provenance=_string(
                mapping["prize_rule_provenance"], "prize_rule_provenance"
            ),
        )


@dataclass(frozen=True, slots=True)
class NextDrawStrategyOutcomeAttribution:
    """One sealed strategy status and only the ticket scores actually present."""

    rank: int
    strategy_id: str
    strategy_name: str
    seal_status: TicketSealStatus
    detail: str
    ticket_attributions: tuple[NextDrawTicketOutcomeAttribution, ...]

    def __post_init__(self) -> None:
        if type(self.rank) is not int or self.rank < 1:
            raise NextDrawOutcomeAttributionContractError("strategy rank must be >= 1")
        _require_text(self.strategy_id, "strategy_id")
        _require_text(self.strategy_name, "strategy_name")
        _require_text(self.detail, "detail", allow_empty=True)
        if type(self.seal_status) is not TicketSealStatus:
            raise NextDrawOutcomeAttributionContractError("seal_status is invalid")
        if self.seal_status is TicketSealStatus.OK and not self.ticket_attributions:
            raise NextDrawOutcomeAttributionContractError(
                "an OK sealed strategy must carry actual ticket attributions"
            )
        if self.seal_status is not TicketSealStatus.OK and self.ticket_attributions:
            raise NextDrawOutcomeAttributionContractError(
                "DECLINED/UNREACHABLE strategies must preserve status without fake scores"
            )
        expected_positions = tuple(range(1, len(self.ticket_attributions) + 1))
        if tuple(item.ticket_position for item in self.ticket_attributions) != expected_positions:
            raise NextDrawOutcomeAttributionContractError(
                "ticket attributions must preserve contiguous sealed ticket order"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "detail": self.detail,
            "rank": self.rank,
            "seal_status": self.seal_status.value,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "ticket_attributions": [item.canonical_dict() for item in self.ticket_attributions],
        }

    @classmethod
    def from_canonical_dict(
        cls, value: Mapping[str, object]
    ) -> NextDrawStrategyOutcomeAttribution:
        mapping = _mapping(value, "strategy_attribution")
        _expect_keys(
            mapping,
            {
                "detail",
                "rank",
                "seal_status",
                "strategy_id",
                "strategy_name",
                "ticket_attributions",
            },
            "strategy_attribution",
        )
        raw = _list(mapping["ticket_attributions"], "ticket_attributions")
        return cls(
            rank=_int(mapping["rank"], "rank"),
            strategy_id=_string(mapping["strategy_id"], "strategy_id"),
            strategy_name=_string(mapping["strategy_name"], "strategy_name"),
            seal_status=TicketSealStatus(_string(mapping["seal_status"], "seal_status")),
            detail=_string_allow_empty(mapping["detail"], "detail"),
            ticket_attributions=tuple(
                NextDrawTicketOutcomeAttribution.from_canonical_dict(item) for item in raw
            ),
        )


@dataclass(frozen=True, slots=True)
class NextDrawBucketOutcomeAttribution:
    """One exact P4 bucket projection, preserving availability and child status."""

    native_ticket_count: int
    availability: BucketAvailabilityStatus
    total_candidate_count: int
    strategies: tuple[NextDrawStrategyOutcomeAttribution, ...]

    def __post_init__(self) -> None:
        if self.native_ticket_count not in NATIVE_TICKET_COUNT_BUCKETS:
            raise NextDrawOutcomeAttributionContractError("native_ticket_count is unsupported")
        if type(self.availability) is not BucketAvailabilityStatus:
            raise NextDrawOutcomeAttributionContractError("availability is invalid")
        if type(self.total_candidate_count) is not int or self.total_candidate_count < 0:
            raise NextDrawOutcomeAttributionContractError(
                "total_candidate_count must be non-negative"
            )
        if self.availability is not bucket_availability(self.total_candidate_count):
            raise NextDrawOutcomeAttributionContractError(
                "availability contradicts total_candidate_count"
            )
        if self.availability is BucketAvailabilityStatus.UNAVAILABLE and self.strategies:
            raise NextDrawOutcomeAttributionContractError(
                "UNAVAILABLE buckets must have zero score children"
            )
        # Exact cardinality belongs to the enclosing seal schema: V1 pool
        # metadata can exceed its actual sealed prefix. V2 remains exact below.
        expected_count = min(self.total_candidate_count, TOP_N)
        if len(self.strategies) > expected_count:
            raise NextDrawOutcomeAttributionContractError(
                "bucket strategy count must preserve the sealed top-N projection"
            )
        if tuple(item.rank for item in self.strategies) != tuple(
            range(1, len(self.strategies) + 1)
        ):
            raise NextDrawOutcomeAttributionContractError(
                "bucket strategies must preserve contiguous seal rank"
            )
        for strategy in self.strategies:
            if strategy.seal_status is TicketSealStatus.OK and len(
                strategy.ticket_attributions
            ) != self.native_ticket_count:
                raise NextDrawOutcomeAttributionContractError(
                    "OK strategy output must score every actual sealed ticket exactly once"
                )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "availability": self.availability.value,
            "native_ticket_count": self.native_ticket_count,
            "strategies": [item.canonical_dict() for item in self.strategies],
            "total_candidate_count": self.total_candidate_count,
        }

    @classmethod
    def from_canonical_dict(
        cls, value: Mapping[str, object]
    ) -> NextDrawBucketOutcomeAttribution:
        mapping = _mapping(value, "bucket_attribution")
        _expect_keys(
            mapping,
            {"availability", "native_ticket_count", "strategies", "total_candidate_count"},
            "bucket_attribution",
        )
        raw = _list(mapping["strategies"], "strategies")
        return cls(
            native_ticket_count=_int(mapping["native_ticket_count"], "native_ticket_count"),
            availability=BucketAvailabilityStatus(
                _string(mapping["availability"], "availability")
            ),
            total_candidate_count=_int(
                mapping["total_candidate_count"], "total_candidate_count"
            ),
            strategies=tuple(
                NextDrawStrategyOutcomeAttribution.from_canonical_dict(item) for item in raw
            ),
        )


def _validate_v1_attribution_projection(
    seal: VerifiedNextDrawRecommendationSeal,
    buckets: tuple[NextDrawBucketOutcomeAttribution, ...],
) -> None:
    """Bind V1 output to actual sealed children, never to candidate-pool size."""

    if tuple(bucket.native_ticket_count for bucket in buckets) != tuple(
        bucket.native_ticket_count for bucket in seal.buckets
    ):
        raise NextDrawOutcomeAttributionContractError("V1 attribution bucket projection changed")
    for projected, sealed in zip(buckets, seal.buckets, strict=True):
        if (
            projected.availability.value != sealed.availability
            or projected.total_candidate_count != sealed.total_candidate_count
            or len(projected.strategies) != len(sealed.sealed_tickets)
        ):
            raise NextDrawOutcomeAttributionContractError(
                "V1 attribution must preserve bucket metadata and actual sealed strategy count"
            )
        for strategy, original in zip(projected.strategies, sealed.sealed_tickets, strict=True):
            if (
                strategy.rank != original.rank
                or strategy.strategy_id != original.strategy_id
                or strategy.strategy_name != original.strategy_name
                or strategy.seal_status is not original.status
                or strategy.detail != original.detail
                or tuple(item.predicted_main_numbers for item in strategy.ticket_attributions)
                != original.tickets
            ):
                raise NextDrawOutcomeAttributionContractError(
                    "V1 attribution must preserve only the actual sealed strategies and tickets"
                )


@dataclass(frozen=True, slots=True)
class NextDrawOutcomeAttribution:
    """Complete deterministic P4 artifact for one sealed target and outcome."""

    schema_version: str
    target: ObservationTarget
    seal_schema_version: str
    seal_file_sha256: str
    seal_digest: str
    seal_source_head: str | None
    seal_source_tree: str | None
    scoring_contract_id: str
    scoring_contract_sha256: str
    official_outcome: NextDrawOfficialOutcome
    buckets: tuple[NextDrawBucketOutcomeAttribution, ...]
    attribution_sha256: str

    @classmethod
    def create(
        cls,
        *,
        seal: VerifiedNextDrawRecommendationSeal,
        official_outcome: NextDrawOfficialOutcome,
        buckets: tuple[NextDrawBucketOutcomeAttribution, ...],
    ) -> NextDrawOutcomeAttribution:
        if seal.schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_V1:
            _validate_v1_attribution_projection(seal, buckets)
        material = _attribution_material(
            schema_version=NEXT_DRAW_P4_ATTRIBUTION_SCHEMA_VERSION,
            target=seal.target,
            seal_schema_version=seal.schema_version,
            seal_file_sha256=seal.seal_file_sha256,
            seal_digest=seal.seal_digest,
            seal_source_head=seal.source_head,
            seal_source_tree=seal.source_tree,
            scoring_contract_id=BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_ID,
            scoring_contract_sha256=BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256,
            official_outcome=official_outcome,
            buckets=buckets,
        )
        return cls(
            schema_version=NEXT_DRAW_P4_ATTRIBUTION_SCHEMA_VERSION,
            target=seal.target,
            seal_schema_version=seal.schema_version,
            seal_file_sha256=seal.seal_file_sha256,
            seal_digest=seal.seal_digest,
            seal_source_head=seal.source_head,
            seal_source_tree=seal.source_tree,
            scoring_contract_id=BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_ID,
            scoring_contract_sha256=BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256,
            official_outcome=official_outcome,
            buckets=buckets,
            attribution_sha256=_canonical_sha256(material),
        )

    def __post_init__(self) -> None:
        if self.schema_version != NEXT_DRAW_P4_ATTRIBUTION_SCHEMA_VERSION:
            raise NextDrawOutcomeAttributionContractError("unsupported P4 schema_version")
        if type(self.target) is not ObservationTarget:
            raise NextDrawOutcomeAttributionContractError("target must be canonical")
        if self.seal_schema_version not in SUPPORTED_NEXT_DRAW_RECOMMENDATION_SEAL_VERSIONS:
            raise NextDrawOutcomeAttributionContractError("unsupported seal schema_version")
        _require_sha256(self.seal_file_sha256, "seal_file_sha256")
        _require_sha256(self.seal_digest, "seal_digest")
        if self.seal_schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_V1:
            if (self.seal_source_head, self.seal_source_tree) != (None, None):
                raise NextDrawOutcomeAttributionContractError(
                    "V1 attribution must not rewrite the seal as V2"
                )
        elif self.seal_source_head is None or self.seal_source_tree is None:
            raise NextDrawOutcomeAttributionContractError(
                "V2 attribution must retain source Git identity"
            )
        else:
            for label, value in (
                ("seal_source_head", self.seal_source_head),
                ("seal_source_tree", self.seal_source_tree),
            ):
                if (
                    _GIT_OBJECT_ID.fullmatch(value) is None
                    or value == "0" * len(value)
                ):
                    raise NextDrawOutcomeAttributionContractError(
                        f"{label} must be a full non-placeholder Git object ID"
                    )
        if self.scoring_contract_id != BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_ID:
            raise NextDrawOutcomeAttributionContractError("scoring_contract_id changed")
        if self.scoring_contract_sha256 != BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256:
            raise NextDrawOutcomeAttributionContractError("scoring contract SHA changed")
        if (
            self.official_outcome.lottery_type is not self.target.lottery_type
            or self.official_outcome.draw_number != self.target.draw_number
            or self.official_outcome.draw_date != self.target.draw_date
        ):
            raise NextDrawOutcomeAttributionContractError(
                "official outcome must match the exact sealed target"
            )
        if tuple(bucket.native_ticket_count for bucket in self.buckets) != (
            NATIVE_TICKET_COUNT_BUCKETS
        ):
            raise NextDrawOutcomeAttributionContractError(
                "P4 output must contain the exact six-bucket projection in order"
            )
        if self.seal_schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_V2:
            for bucket in self.buckets:
                if len(bucket.strategies) != min(bucket.total_candidate_count, TOP_N):
                    raise NextDrawOutcomeAttributionContractError(
                        "bucket strategy count must preserve the sealed top-N projection"
                    )
        _require_sha256(self.attribution_sha256, "attribution_sha256")
        if self.attribution_sha256 != _canonical_sha256(self.canonical_material()):
            raise NextDrawOutcomeAttributionTamperError(
                "P4 attribution self hash does not match its canonical material"
            )

    def canonical_material(self) -> dict[str, object]:
        return _attribution_material(
            schema_version=self.schema_version,
            target=self.target,
            seal_schema_version=self.seal_schema_version,
            seal_file_sha256=self.seal_file_sha256,
            seal_digest=self.seal_digest,
            seal_source_head=self.seal_source_head,
            seal_source_tree=self.seal_source_tree,
            scoring_contract_id=self.scoring_contract_id,
            scoring_contract_sha256=self.scoring_contract_sha256,
            official_outcome=self.official_outcome,
            buckets=self.buckets,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "attribution_sha256": self.attribution_sha256}

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> NextDrawOutcomeAttribution:
        mapping = _mapping(value, "attribution")
        _expect_keys(
            mapping,
            {
                "attribution_sha256",
                "buckets",
                "official_outcome",
                "schema_version",
                "scoring_contract_id",
                "scoring_contract_sha256",
                "seal_digest",
                "seal_file_sha256",
                "seal_schema_version",
                "seal_source_head",
                "seal_source_tree",
                "target",
            },
            "attribution",
        )
        target = _target(mapping["target"])
        raw_buckets = _list(mapping["buckets"], "buckets")
        return cls(
            schema_version=_string(mapping["schema_version"], "schema_version"),
            target=target,
            seal_schema_version=_string(
                mapping["seal_schema_version"], "seal_schema_version"
            ),
            seal_file_sha256=_sha256(mapping["seal_file_sha256"], "seal_file_sha256"),
            seal_digest=_sha256(mapping["seal_digest"], "seal_digest"),
            seal_source_head=_optional_string(
                mapping["seal_source_head"], "seal_source_head"
            ),
            seal_source_tree=_optional_string(
                mapping["seal_source_tree"], "seal_source_tree"
            ),
            scoring_contract_id=_string(
                mapping["scoring_contract_id"], "scoring_contract_id"
            ),
            scoring_contract_sha256=_sha256(
                mapping["scoring_contract_sha256"], "scoring_contract_sha256"
            ),
            official_outcome=NextDrawOfficialOutcome.from_canonical_dict(
                _mapping(mapping["official_outcome"], "official_outcome")
            ),
            buckets=tuple(
                NextDrawBucketOutcomeAttribution.from_canonical_dict(item)
                for item in raw_buckets
            ),
            attribution_sha256=_sha256(
                mapping["attribution_sha256"], "attribution_sha256"
            ),
        )


def _attribution_material(
    *,
    schema_version: str,
    target: ObservationTarget,
    seal_schema_version: str,
    seal_file_sha256: str,
    seal_digest: str,
    seal_source_head: str | None,
    seal_source_tree: str | None,
    scoring_contract_id: str,
    scoring_contract_sha256: str,
    official_outcome: NextDrawOfficialOutcome,
    buckets: tuple[NextDrawBucketOutcomeAttribution, ...],
) -> dict[str, object]:
    return {
        "buckets": [bucket.canonical_dict() for bucket in buckets],
        "official_outcome": official_outcome.canonical_dict(),
        "schema_version": schema_version,
        "scoring_contract_id": scoring_contract_id,
        "scoring_contract_sha256": scoring_contract_sha256,
        "seal_digest": seal_digest,
        "seal_file_sha256": seal_file_sha256,
        "seal_schema_version": seal_schema_version,
        "seal_source_head": seal_source_head,
        "seal_source_tree": seal_source_tree,
        "target": target.canonical_dict(),
    }


def serialize_next_draw_outcome_attribution(
    artifact: NextDrawOutcomeAttribution,
) -> bytes:
    """Return the sole canonical byte representation stored by P4 SQLite."""

    if type(artifact) is not NextDrawOutcomeAttribution:
        raise NextDrawOutcomeAttributionContractError(
            "artifact must be a NextDrawOutcomeAttribution"
        )
    return _canonical_bytes(artifact.canonical_dict())


@dataclass(frozen=True, slots=True)
class NextDrawP4PersistResult:
    outcome: NextDrawP4PersistenceOutcome
    attribution_sha256: str

    def __post_init__(self) -> None:
        if type(self.outcome) is not NextDrawP4PersistenceOutcome:
            raise NextDrawOutcomeAttributionContractError("persistence outcome is invalid")
        _require_sha256(self.attribution_sha256, "attribution_sha256")


@dataclass(frozen=True, slots=True)
class NextDrawOutcomeAttributionPage:
    records: tuple[NextDrawOutcomeAttribution, ...]
    page: int
    page_size: int
    total_count: int
    total_pages: int

    def __post_init__(self) -> None:
        for label, value, minimum in (
            ("page", self.page, 1),
            ("page_size", self.page_size, 1),
            ("total_count", self.total_count, 0),
            ("total_pages", self.total_pages, 0),
        ):
            if type(value) is not int or value < minimum:
                raise NextDrawOutcomeAttributionContractError(f"{label} is invalid")
        expected_pages = 0
        if self.total_count:
            expected_pages = (self.total_count + self.page_size - 1) // self.page_size
        if self.total_pages != expected_pages or len(self.records) > self.page_size:
            raise NextDrawOutcomeAttributionContractError("history page metadata is inconsistent")


def _provenance_from_dict(value: object) -> NextDrawOfficialOutcomeProvenance:
    mapping = _mapping(value, "provenance")
    _expect_keys(
        mapping,
        {
            "completed_at",
            "ingestion_run_id",
            "operation_type",
            "parser_version",
            "source_filename",
            "source_name",
            "source_reference",
            "source_sha256",
            "status",
        },
        "provenance",
    )
    return NextDrawOfficialOutcomeProvenance(
        ingestion_run_id=_string(mapping["ingestion_run_id"], "ingestion_run_id"),
        operation_type=_string(mapping["operation_type"], "operation_type"),
        status=_string(mapping["status"], "status"),
        source_filename=_string(mapping["source_filename"], "source_filename"),
        source_sha256=_sha256(mapping["source_sha256"], "source_sha256"),
        parser_version=_string(mapping["parser_version"], "parser_version"),
        completed_at=_datetime(mapping["completed_at"], "completed_at"),
        source_name=_optional_string(mapping["source_name"], "source_name"),
        source_reference=_optional_string(mapping["source_reference"], "source_reference"),
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise NextDrawOutcomeAttributionContractError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise NextDrawOutcomeAttributionContractError(
            f"{label} fields differ; missing={sorted(expected - set(value))}, "
            f"unknown={sorted(set(value) - expected)}"
        )


def _list(value: object, label: str) -> list[Mapping[str, object]]:
    if type(value) is not list:
        raise NextDrawOutcomeAttributionContractError(f"{label} must be a list")
    return [_mapping(item, f"{label}[]") for item in cast(list[object], value)]


def _string(value: object, label: str) -> str:
    return _require_text(value, label)


def _string_allow_empty(value: object, label: str) -> str:
    return _require_text(value, label, allow_empty=True)


def _optional_string(value: object, label: str) -> str | None:
    return None if value is None else _string(value, label)


def _sha256(value: object, label: str) -> str:
    return _require_sha256(value, label)


def _int(value: object, label: str) -> int:
    if type(value) is not int:
        raise NextDrawOutcomeAttributionContractError(f"{label} must be an exact integer")
    return value


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise NextDrawOutcomeAttributionContractError(f"{label} must be a bool")
    return value


def _int_tuple(value: object, label: str) -> tuple[int, ...]:
    if type(value) is not list:
        raise NextDrawOutcomeAttributionContractError(
            f"{label} must be a list of exact integers"
        )
    items = cast(list[object], value)
    if any(type(item) is not int for item in items):
        raise NextDrawOutcomeAttributionContractError(
            f"{label} must be a list of exact integers"
        )
    return tuple(cast(list[int], items))


def _date(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise NextDrawOutcomeAttributionContractError(f"{label} is invalid") from exc
    if parsed.isoformat() != text:
        raise NextDrawOutcomeAttributionContractError(f"{label} is not canonical")
    return parsed


def _datetime(value: object, label: str) -> datetime:
    text = _string(value, label)
    if not text.endswith("Z"):
        raise NextDrawOutcomeAttributionContractError(f"{label} must use UTC Z text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise NextDrawOutcomeAttributionContractError(f"{label} is invalid") from exc
    if parsed.tzinfo is not UTC or _utc_text(parsed) != text:
        raise NextDrawOutcomeAttributionContractError(f"{label} is not canonical UTC")
    return parsed


def _lottery_type(value: object) -> LotteryType:
    try:
        return LotteryType(_string(value, "lottery_type"))
    except ValueError as exc:
        raise NextDrawOutcomeAttributionContractError("lottery_type is unsupported") from exc


def _target(value: object) -> ObservationTarget:
    mapping = _mapping(value, "target")
    _expect_keys(mapping, {"draw_date", "draw_number", "lottery_type"}, "target")
    return ObservationTarget(
        lottery_type=_lottery_type(mapping["lottery_type"]),
        draw_number=_string(mapping["draw_number"], "target.draw_number"),
        draw_date=_date(mapping["draw_date"], "target.draw_date"),
    )


__all__ = [
    "BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_ID",
    "BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256",
    "NEXT_DRAW_P4_ATTRIBUTION_SCHEMA_VERSION",
    "NEXT_DRAW_RECOMMENDATION_SEAL_V1",
    "NEXT_DRAW_RECOMMENDATION_SEAL_V2",
    "SUPPORTED_NEXT_DRAW_RECOMMENDATION_SEAL_VERSIONS",
    "NextDrawBucketOutcomeAttribution",
    "NextDrawOfficialOutcome",
    "NextDrawOfficialOutcomeProvenance",
    "NextDrawOutcomeAttribution",
    "NextDrawOutcomeAttributionContractError",
    "NextDrawOutcomeAttributionPage",
    "NextDrawOutcomeAttributionTamperError",
    "NextDrawP4PersistResult",
    "NextDrawP4PersistenceOutcome",
    "NextDrawStrategyOutcomeAttribution",
    "NextDrawTicketOutcomeAttribution",
    "VerifiedNextDrawRecommendationSeal",
    "compute_draw_data_v3_normalized_record_hash",
    "current_big_lotto_prize_evaluation_contract_sha256",
    "serialize_next_draw_outcome_attribution",
]
