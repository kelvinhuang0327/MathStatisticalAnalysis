"""Guarded, outcome-free K3 research entry point.

This is an opt-in boundary; it does not change or protect the existing
history-native APIs.  Callers must obtain registrations, attestations,
publication timestamps, and the clock from trusted authorities and seal the
returned result separately.  A self-consistent in-memory record alone is not
proof that an actual prediction was made before a draw.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from lottolab.application.legacy_analyze_k3_candidate import (
    ANALYZE_DONOR_SHA256,
    ANALYZE_K3_CANDIDATE_PROTOCOL,
    analyze_native_14,
    deduplicate_native_prefix,
)
from lottolab.application.legacy_history_native_portfolios import (
    DEFAULT_HISTORY_NATIVE_USER_SEED,
    EXHAUSTIVE_AUDIT_METHOD_ID,
    OPTIMIZED_ENSEMBLE_METHOD_ID,
    LegacyHistoryDraw,
    LegacyHistoryNativeRequest,
    generate_legacy_history_native_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave21 import (
    DEFAULT_SOURCE_NATIVE_WAVE21_USER_SEED,
    POST_SELECTION_FILTER_METHOD_ID,
    LegacySourceNativeWave21Request,
    generate_legacy_source_native_wave21_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
)
from lottolab.domain.prospective_observer import OutcomePresenceAtPrediction
from lottolab.strategies.adapters.base import CausalDrawRow

_HISTORY_SCHEMA = "LOTTOLAB_PRE_OUTCOME_CAUSAL_HISTORY_V1"
_MAX_ATTESTATION_AGE = timedelta(minutes=5)
GREEDY_K3 = ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18))


class K3PreDrawError(ValueError):
    """The request cannot establish the required pre-draw conditions."""


class K3Policy(StrEnum):
    EXHAUSTIVE = "EXHAUSTIVE"
    BACKTEST_STRATEGY_1 = "BACKTEST_STRATEGY_1"
    OPTIMIZED_ENSEMBLE = "OPTIMIZED_ENSEMBLE"
    ANALYZE_CANDIDATE = "ANALYZE_CANDIDATE"


@dataclass(frozen=True, slots=True)
class K3HistoryRow:
    """A previously published draw; timestamps come from a trusted caller."""

    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int
    drawn_at: datetime
    available_at: datetime


@dataclass(frozen=True, slots=True)
class GuardedK3Result:
    policy: K3Policy
    target_draw: str
    registration_digest: str
    history_sha256: str
    availability_sha256: str
    absence_attested_at: datetime
    producer_protocol: str
    producer_source_sha256: str
    producer_seed_digest: str
    started_at: datetime
    produced_at: datetime
    source_native_tickets: tuple[tuple[int, ...], ...]
    native_tickets: tuple[tuple[int, ...], ...]
    native_positions: tuple[int, ...]
    tickets: tuple[tuple[int, ...], ...]
    supplement_indices: tuple[int, ...]


def _utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise K3PreDrawError(f"{label} must be a UTC datetime")
    return value


def _draw_id(value: object, label: str) -> int:
    if (
        type(value) is not str
        or not value.isascii()
        or not value.isdecimal()
        or value.startswith("0")
        or not 8 <= len(value) <= 9
        or int(value[-6:]) == 0
    ):
        raise K3PreDrawError(f"{label} must be a canonical BIG_LOTTO draw number")
    return int(value)


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _record_hash(row: K3HistoryRow) -> str:
    return _sha256_json(
        {
            "draw_date": row.draw_date.isoformat(),
            "draw_number": row.draw_number,
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "main_numbers": row.main_numbers,
            "special_numbers": (row.special_number,),
        }
    )


def _validate_ticket(ticket: tuple[int, ...]) -> None:
    if (
        type(ticket) is not tuple
        or len(ticket) != 6
        or any(type(number) is not int or not 1 <= number <= 49 for number in ticket)
        or len(set(ticket)) != 6
    ):
        raise K3PreDrawError("producer emitted an invalid ticket")


def _supplement(
    native: tuple[tuple[int, ...], ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    if type(native) is not tuple or not 1 <= len(native) <= 3:
        raise K3PreDrawError("native portfolio must have one to three tickets")
    for ticket in native:
        _validate_ticket(ticket)
    if len({frozenset(ticket) for ticket in native}) != len(native):
        raise K3PreDrawError("native tickets must be distinct")
    selected = list(native)
    indices: list[int] = []
    while len(selected) < 3:
        used = {frozenset(ticket) for ticket in selected}
        candidates = [
            (max(len(set(ticket) & set(item)) for item in selected), index)
            for index, ticket in enumerate(GREEDY_K3)
            if frozenset(ticket) not in used
        ]
        if not candidates:
            raise K3PreDrawError("Greedy cannot complete the portfolio")
        _, index = min(candidates)
        selected.append(GREEDY_K3[index])
        indices.append(index)
    return tuple(selected), tuple(indices)


def _guard_history(
    registration: PreOutcomeTargetRegistration,
    history: tuple[K3HistoryRow, ...],
) -> tuple[LegacyHistoryDraw, ...]:
    if type(registration) is not PreOutcomeTargetRegistration:
        raise K3PreDrawError("a validated pre-outcome registration is required")
    target = registration.target
    if target.lottery_type is not LotteryType.BIG_LOTTO:
        raise K3PreDrawError("target must be BIG_LOTTO")
    target_id = _draw_id(target.draw_number, "target")
    if type(history) is not tuple or not history:
        raise K3PreDrawError("history must be a nonempty immutable tuple")
    timezone = ZoneInfo(registration.announcement.schedule_timezone)
    material: list[dict[str, str]] = []
    previous_id = 0
    previous_date: date | None = None
    previous_drawn: datetime | None = None
    native: list[LegacyHistoryDraw] = []
    for row in history:
        if type(row) is not K3HistoryRow or type(row.draw_date) is not date:
            raise K3PreDrawError("history must contain exact dated K3HistoryRow values")
        number = _draw_id(row.draw_number, "history draw")
        drawn_at = _utc(row.drawn_at, "drawn_at")
        available_at = _utc(row.available_at, "available_at")
        if (
            number <= previous_id
            or number >= target_id
            or row.draw_date > target.draw_date
            or (previous_date is not None and row.draw_date < previous_date)
            or (previous_drawn is not None and drawn_at <= previous_drawn)
            or drawn_at.astimezone(timezone).date() != row.draw_date
            or drawn_at > available_at
            or available_at > registration.registered_at
            or drawn_at >= registration.announcement.scheduled_at
        ):
            raise K3PreDrawError("history is not strictly prior, ordered, and available")
        _validate_ticket(row.main_numbers)
        if tuple(sorted(row.main_numbers)) != row.main_numbers:
            raise K3PreDrawError("history main numbers must be canonical ascending")
        if type(row.special_number) is not int or not 1 <= row.special_number <= 49:
            raise K3PreDrawError("history special number is invalid")
        if row.special_number in row.main_numbers:
            raise K3PreDrawError("history special number overlaps main numbers")
        material.append(
            {
                "draw_date": row.draw_date.isoformat(),
                "draw_number": row.draw_number,
                "normalized_record_hash": _record_hash(row),
            }
        )
        native.append(LegacyHistoryDraw(row.draw_number, row.main_numbers))
        previous_id, previous_date, previous_drawn = number, row.draw_date, drawn_at
    ref = registration.causal_history
    digest = _sha256_json(
        {
            "draws": material,
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "schema_version": _HISTORY_SCHEMA,
            "target": target.canonical_dict(),
        }
    )
    if (
        ref.draw_count != len(history)
        or ref.last_draw_number != history[-1].draw_number
        or ref.last_draw_date != history[-1].draw_date
        or ref.history_sha256 != digest
    ):
        raise K3PreDrawError("history does not match the registered authority")
    return tuple(native)


def generate_guarded_k3(
    *,
    policy: K3Policy,
    registration: PreOutcomeTargetRegistration,
    history: tuple[K3HistoryRow, ...],
    absence: OutcomePresenceAttestation,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> GuardedK3Result:
    """Check authority before producing; reject a result finishing after the draw.

    The returned object is not a durable or independently time-stamped seal.
    """
    if type(policy) is not K3Policy:
        raise K3PreDrawError("unsupported K3 policy")
    native_history = _guard_history(registration, history)
    now = _utc(clock(), "clock")
    if type(absence) is not OutcomePresenceAttestation:
        raise K3PreDrawError("fresh outcome absence attestation is required")
    if (
        absence.target != registration.target
        or absence.presence is not OutcomePresenceAtPrediction.ABSENT
        or absence.attested_at < registration.registered_at
        or absence.attested_at > now
        or now - absence.attested_at > _MAX_ATTESTATION_AGE
        or now < registration.registered_at
        or now >= registration.announcement.scheduled_at
    ):
        raise K3PreDrawError("target is not confirmed absent and strictly pre-draw")
    target = registration.target.draw_number
    if policy is K3Policy.ANALYZE_CANDIDATE:
        rows = tuple(
            CausalDrawRow(row.draw_number, row.draw_date.isoformat(), row.main_numbers)
            for row in history
        )
        try:
            source_native_tickets = analyze_native_14(rows)
            if len(source_native_tickets) != 14:
                raise K3PreDrawError("analyze source must return 14 native positions")
            for source_ticket in source_native_tickets:
                _validate_ticket(source_ticket)
            native_tickets, native_positions = deduplicate_native_prefix(source_native_tickets)
        except ValueError as exc:
            raise K3PreDrawError(str(exc)) from exc
        protocol = ANALYZE_K3_CANDIDATE_PROTOCOL
        source_sha256 = ANALYZE_DONOR_SHA256
        seed_digest = hashlib.sha256(b"deterministic-no-randomness").hexdigest()
    elif policy is K3Policy.BACKTEST_STRATEGY_1:
        generated = generate_legacy_source_native_wave21_portfolio(
            LegacySourceNativeWave21Request(
                POST_SELECTION_FILTER_METHOD_ID,
                target,
                native_history,
                replicate_id=0,
                user_seed=DEFAULT_SOURCE_NATIVE_WAVE21_USER_SEED,
            )
        )
        native_tickets = generated.tickets
        source_native_tickets = native_tickets
        native_positions = tuple(range(1, len(native_tickets) + 1))
        protocol = generated.metadata.protocol
        source_sha256 = generated.metadata.source_sha256
        seed_digest = generated.metadata.seed_digest
    else:
        method = (
            EXHAUSTIVE_AUDIT_METHOD_ID
            if policy is K3Policy.EXHAUSTIVE
            else OPTIMIZED_ENSEMBLE_METHOD_ID
        )
        generated = generate_legacy_history_native_portfolio(
            LegacyHistoryNativeRequest(
                method,
                target,
                native_history,
                replicate_id=0,
                user_seed=DEFAULT_HISTORY_NATIVE_USER_SEED,
            )
        )
        native_tickets = generated.tickets
        source_native_tickets = native_tickets
        native_positions = tuple(range(1, len(native_tickets) + 1))
        protocol = generated.metadata.protocol
        source_sha256 = generated.metadata.source_sha256
        seed_digest = generated.metadata.seed_digest
    tickets, indices = _supplement(native_tickets)
    finished_at = _utc(clock(), "clock")
    if (
        finished_at < now
        or finished_at >= registration.announcement.scheduled_at
        or finished_at - absence.attested_at > _MAX_ATTESTATION_AGE
    ):
        raise K3PreDrawError("production clock regressed, passed the draw, or absence became stale")
    return GuardedK3Result(
        policy=policy,
        target_draw=target,
        registration_digest=registration.registration_digest,
        history_sha256=registration.causal_history.history_sha256,
        availability_sha256=_sha256_json(
            {
                "registration_digest": registration.registration_digest,
                "rows": [
                    {
                        "draw_number": row.draw_number,
                        "drawn_at": row.drawn_at.isoformat(),
                        "available_at": row.available_at.isoformat(),
                    }
                    for row in history
                ],
            }
        ),
        absence_attested_at=absence.attested_at,
        producer_protocol=protocol,
        producer_source_sha256=source_sha256,
        producer_seed_digest=seed_digest,
        started_at=now,
        produced_at=finished_at,
        source_native_tickets=source_native_tickets,
        native_tickets=native_tickets,
        native_positions=native_positions,
        tickets=tickets,
        supplement_indices=indices,
    )
