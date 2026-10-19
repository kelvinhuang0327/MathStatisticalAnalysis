"""Immutable FULL-history, within-native-K next-undrawn forecast contracts.

Hashes use the same compact, sorted-key, UTF-8 JSON dialect as the generic
prospective contracts (no trailing LF). No outcome source or strategy runs here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from fractions import Fraction
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    ObservationTarget,
    ProducerFingerprint,
)
from lottolab.domain.strategies import ResponseShape, StrategyDescriptor

SCHEMA_VERSION = "B649_NEXT_UNDRAWN_FORECAST_V1"
RANKING_POLICY_VERSION = "B649_FULL_OFFICIAL_ANY_PRIZE_R1"
OBJECTIVE = "OFFICIAL_ANY_PRIZE"
COHORT_ID = "B649_NEXT_UNDRAWN_FORECAST"
OUTPUT_BUCKETS = (1, 2, 3, 5, 10, 20)
OUTPUT_TOP_N = 1
REQUIRED_HISTORY_CUTOFF = "115000085"
TicketSet = tuple[tuple[int, ...], ...]


class ForecastContractError(ValueError):
    """A supplied authority or payload contradicts the frozen forecast contract."""


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_digest(value: str) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ForecastContractError("expected lowercase SHA-256")


def validate_tickets(tickets: TicketSet, native_k: int) -> None:
    if type(tickets) is not tuple or len(tickets) != native_k:
        raise ForecastContractError("NATIVE_TICKET_COUNT_VIOLATION")
    for ticket in tickets:
        if (
            type(ticket) is not tuple
            or len(ticket) != 6
            or any(type(n) is not int or not 1 <= n <= 49 for n in ticket)
            or len(set(ticket)) != 6
            or tuple(sorted(ticket)) != ticket
        ):
            raise ForecastContractError("INVALID_SIX_NUMBER_TICKET")
    # Ticket positions and duplicate tickets are canonical native output too.


def history_payload(draws: tuple[Draw, ...]) -> list[dict[str, object]]:
    return [
        {
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "draw_number": d.draw_number,
            "draw_date": d.draw_date.isoformat(),
            "main_numbers": list(d.main_numbers),
            "special_number": d.special_number,
        }
        for d in draws
    ]


def history_ref(draws: tuple[Draw, ...]) -> CausalHistoryRef:
    return CausalHistoryRef(
        len(draws),
        draws[-1].draw_number if draws else None,
        draws[-1].draw_date if draws else None,
        digest(history_payload(draws)),
    )


def validate_history(
    draws: tuple[Draw, ...],
    target: ObservationTarget,
    authority: CausalHistoryRef,
    required_cutoff: str = REQUIRED_HISTORY_CUTOFF,
) -> None:
    if target.lottery_type is not LotteryType.BIG_LOTTO or not draws:
        raise ForecastContractError("BIG_LOTTO_FULL_HISTORY_REQUIRED")
    if target.draw_number == "115000086" and required_cutoff != REQUIRED_HISTORY_CUTOFF:
        raise ForecastContractError("STALE_HISTORY_AUTHORITY")
    if not required_cutoff.isascii() or not required_cutoff.isdecimal():
        raise ForecastContractError("INVALID_CUTOFF")
    previous_number = -1
    previous_date = date.min
    for draw in draws:
        if (
            not draw.draw_number.isascii()
            or not draw.draw_number.isdecimal()
            or len(draw.draw_number) not in (8, 9)
        ):
            raise ForecastContractError("INVALID_DRAW_IDENTITY")
        validate_tickets((draw.main_numbers,), 1)
        if (
            type(draw.special_number) is not int
            or not 1 <= draw.special_number <= 49
            or draw.special_number in draw.main_numbers
        ):
            raise ForecastContractError("INVALID_SPECIAL_NUMBER")
        if (
            int(draw.draw_number) <= previous_number
            or draw.draw_date <= previous_date
            or int(draw.draw_number) >= int(target.draw_number)
            or draw.draw_date >= target.draw_date
            or int(draw.draw_number) > int(required_cutoff)
        ):
            raise ForecastContractError("FUTURE_OR_NONCHRONOLOGICAL_HISTORY")
        previous_number, previous_date = int(draw.draw_number), draw.draw_date
    if draws[-1].draw_number != required_cutoff:
        raise ForecastContractError("STALE_HISTORY_AUTHORITY")
    if history_ref(draws) != authority:
        raise ForecastContractError("HISTORY_IDENTITY_MISMATCH")
    authority.validate_against(target)


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    strategy_id: str
    strategy_version: str
    native_k: int
    parameters_json: str
    rng_semantics_json: str

    def __post_init__(self) -> None:
        if (
            not self.strategy_id
            or not self.strategy_version
            or type(self.native_k) is not int
            or self.native_k not in OUTPUT_BUCKETS
        ):
            raise ForecastContractError("INVALID_GENERATION_IDENTITY")
        for value in (self.parameters_json, self.rng_semantics_json):
            parsed: object = json.loads(value)
            if type(parsed) is not dict or canonical_json(cast(dict[str, object], parsed)) != value:
                raise ForecastContractError(
                    "generation configuration must be canonical JSON objects"
                )

    def payload(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "native_k": self.native_k,
            "parameters": json.loads(self.parameters_json),
            "rng_semantics": json.loads(self.rng_semantics_json),
        }

    @property
    def sha256(self) -> str:
        return digest(self.payload())


def catalog_exclusion(descriptor: StrategyDescriptor) -> str | None:
    if LotteryType.BIG_LOTTO not in descriptor.lottery_types:
        return "OTHER_LOTTERY"
    if not descriptor.executable:
        return "NOT_EXECUTABLE"
    k = descriptor.native_ticket_count
    if k not in OUTPUT_BUCKETS:
        return "NATIVE_K_OUTSIDE_OUTPUT_BUCKETS"
    if descriptor.native_ticket_count_bounds != (k, k):
        return "VARIABLE_NATIVE_CARDINALITY"
    if descriptor.response_shape not in (ResponseShape.SINGLE_TICKET, ResponseShape.PORTFOLIO):
        return "UNSUPPORTED_RESPONSE_SHAPE"
    return None


class ObservationStatus(StrEnum):
    EVALUATED = "ELIGIBLE_EVALUATED"
    WARMUP = "CANONICAL_WARMUP_EXCLUSION"
    MISSING = "MISSING_OBSERVATION"
    FAILURE = "REPLAY_GENERATION_FAILURE"
    METRIC_UNAVAILABLE = "METRIC_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ReplayObservation:
    strategy_id: str
    strategy_version: str
    native_k: int
    draw_number: str
    draw_date: date
    causal_history_sha256: str
    generation_config_sha256: str
    status: ObservationStatus
    producer_fingerprint: str = field(kw_only=True)
    tickets: TicketSet = ()
    failure_code: str | None = None
    replay_invocation_identity: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        require_digest(self.causal_history_sha256)
        require_digest(self.generation_config_sha256)
        require_digest(self.producer_fingerprint)
        if type(self.status) is not ObservationStatus:
            raise ForecastContractError("UNTYPED_OBSERVATION")
        if type(self.tickets) is not tuple:
            raise ForecastContractError("IMMUTABLE_TICKETS_REQUIRED")
        if self.replay_invocation_identity is not None:
            try:
                parsed_identity = json.loads(self.replay_invocation_identity)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ForecastContractError("INVALID_REPLAY_INVOCATION_IDENTITY") from exc
            if (
                type(parsed_identity) is not dict
                or canonical_json(cast(dict[str, object], parsed_identity))
                != self.replay_invocation_identity
            ):
                raise ForecastContractError("INVALID_REPLAY_INVOCATION_IDENTITY")
        if self.status is ObservationStatus.EVALUATED:
            validate_tickets(self.tickets, self.native_k)
        elif self.tickets:
            raise ForecastContractError("unevaluated observations cannot carry tickets")
        if (self.status is ObservationStatus.FAILURE) != bool(self.failure_code):
            raise ForecastContractError("failure observations require a typed failure code only")

    @property
    def generation_identity_sha256(self) -> str:
        """Identity of the causal generation call, independent of its result/status."""
        return digest(
            {
                "strategy_id": self.strategy_id,
                "strategy_version": self.strategy_version,
                "native_k": self.native_k,
                "draw_number": self.draw_number,
                "draw_date": self.draw_date.isoformat(),
                "causal_history_sha256": self.causal_history_sha256,
                "generation_config_sha256": self.generation_config_sha256,
                "producer_fingerprint": self.producer_fingerprint,
                "replay_invocation_identity": (
                    None
                    if self.replay_invocation_identity is None
                    else json.loads(self.replay_invocation_identity)
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class ExactMetric:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if (
            type(self.numerator) is not int
            or type(self.denominator) is not int
            or not 0 <= self.numerator <= self.denominator
        ):
            raise ForecastContractError("INVALID_METRIC_COUNTS")

    @property
    def rate(self) -> Fraction | None:
        return Fraction(self.numerator, self.denominator) if self.denominator else None

    def payload(self) -> dict[str, object]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate": rational_payload(self.rate),
        }


def rational_payload(value: Fraction | None) -> dict[str, str] | None:
    # Strings preserve arbitrary precision for consumers using IEEE-754 JSON numbers.
    return (
        None
        if value is None
        else {"numerator": str(value.numerator), "denominator": str(value.denominator)}
    )


@dataclass(frozen=True, slots=True)
class ClassifiedObservation:
    draw_number: str
    status: ObservationStatus
    official_any_prize: bool | None = None
    failure_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not ObservationStatus:
            raise ForecastContractError("UNTYPED_OBSERVATION")
        if self.status is ObservationStatus.EVALUATED:
            if type(self.official_any_prize) is not bool:
                raise ForecastContractError("EVALUATED_METRIC_REQUIRED")
        elif self.official_any_prize is not None:
            raise ForecastContractError("UNEVALUATED_METRIC_FORBIDDEN")
        if (self.status is ObservationStatus.FAILURE) != bool(self.failure_code):
            raise ForecastContractError("TYPED_FAILURE_CODE_REQUIRED")


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    descriptor: StrategyDescriptor
    observations: tuple[ClassifiedObservation, ...]

    @property
    def complete(self) -> bool:
        return all(
            o.status in (ObservationStatus.EVALUATED, ObservationStatus.WARMUP)
            for o in self.observations
        )

    @property
    def metric(self) -> ExactMetric:
        evaluated = [o for o in self.observations if o.status is ObservationStatus.EVALUATED]
        return ExactMetric(sum(o.official_any_prize is True for o in evaluated), len(evaluated))

    @property
    def rankable(self) -> bool:
        return self.complete and self.metric.denominator > 0

    def payload(self) -> dict[str, object]:
        counts = {
            state.value: sum(o.status is state for o in self.observations)
            for state in ObservationStatus
        }
        return {
            "strategy_id": self.descriptor.strategy_id,
            "strategy_version": self.descriptor.version,
            "native_k": self.descriptor.native_ticket_count,
            "rankable": self.rankable,
            "evidence_complete": self.complete,
            "metric": self.metric.payload(),
            "coverage": {
                "requested": len(self.observations),
                "counts": counts,
                "eligible_expected": len(self.observations)
                - counts[ObservationStatus.WARMUP.value],
            },
            "observations": [asdict(o) for o in self.observations],
        }


def rank_candidates(candidates: tuple[CandidateEvidence, ...]) -> tuple[CandidateEvidence, ...]:
    if len({c.descriptor.native_ticket_count for c in candidates}) > 1:
        raise ForecastContractError("CROSS_K_RANKING_FORBIDDEN")
    if len({c.descriptor.strategy_id for c in candidates}) != len(candidates):
        raise ForecastContractError("DUPLICATE_CANDIDATE")
    return tuple(
        sorted(
            (c for c in candidates if c.rankable),
            key=lambda c: (-cast(Fraction, c.metric.rate), c.descriptor.strategy_id),
        )
    )


@dataclass(frozen=True, slots=True)
class ForecastIdentity:
    target: ObservationTarget
    schedule_authority_sha256: str
    history_cutoff: str
    history_payload_sha256: str
    producer: ProducerFingerprint
    catalog_universe_sha256: str
    generation_config_sha256: str

    def __post_init__(self) -> None:
        for value in (
            self.schedule_authority_sha256,
            self.history_payload_sha256,
            self.catalog_universe_sha256,
            self.generation_config_sha256,
        ):
            require_digest(value)
        if self.target.lottery_type is not LotteryType.BIG_LOTTO:
            raise ForecastContractError("BIG_LOTTO_REQUIRED")

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "lottery_type": self.target.lottery_type.value,
            "target_draw_number": self.target.draw_number,
            "target_draw_date": self.target.draw_date.isoformat(),
            "schedule_authority_sha256": self.schedule_authority_sha256,
            "history_cutoff": self.history_cutoff,
            "history_payload_sha256": self.history_payload_sha256,
            "objective": OBJECTIVE,
            "ranking_policy_version": RANKING_POLICY_VERSION,
            "producer_id": self.producer.producer_id,
            "producer_version": self.producer.producer_version,
            "producer_fingerprint": self.producer.digest,
            "catalog_universe_sha256": self.catalog_universe_sha256,
            "generation_config_sha256": self.generation_config_sha256,
            "output_buckets": list(OUTPUT_BUCKETS),
            "output_top_n": OUTPUT_TOP_N,
        }

    @property
    def bundle_id(self) -> str:
        return digest(self.payload())


@dataclass(frozen=True, slots=True)
class ForecastBundle:
    identity: ForecastIdentity
    payload_json: str

    def __post_init__(self) -> None:
        payload = self.payload()
        if (
            canonical_json(payload) != self.payload_json
            or payload.get("identity") != self.identity.payload()
            or payload.get("bundle_id") != self.identity.bundle_id
        ):
            raise ForecastContractError("BUNDLE_IDENTITY_MISMATCH")
        raw_buckets = payload.get("buckets")
        if type(raw_buckets) is not list:
            raise ForecastContractError("EXACTLY_SIX_BUCKETS_REQUIRED")
        buckets = cast(list[dict[str, object]], raw_buckets)
        if [b.get("native_k") for b in buckets] != list(OUTPUT_BUCKETS):
            raise ForecastContractError("EXACTLY_SIX_BUCKETS_REQUIRED")

    def payload(self) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.payload_json))

    @property
    def payload_sha256(self) -> str:
        return digest(self.payload())
