"""Pure, deterministic aggregation for the B649 canonical stream contract.

The production contract is deliberately small: every registered stream has
    one equal vote, while a stream's own native ticket positions are averaged so a
    three-ticket stream does not receive three times the mass of a single-ticket
    stream.  This module has no filesystem, clock, database, network, or outcome
    dependency.  The target, causal-history, and stream provenance are supplied
    through :class:`CanonicalConsensusContext` before aggregation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, cast

MIN_NUMBER: Final = 1
MAX_NUMBER: Final = 49
FINAL_TICKET_SIZE: Final = 6
PRE_DRAW: Final = "PRE_DRAW"
CANONICAL_CONSENSUS_SCHEMA_VERSION: Final = "b649-canonical-forecast-v1"
CANONICAL_CONSENSUS_METHOD_ID: Final = "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
CANONICAL_CONSENSUS_METHOD_VERSION: Final = "1.0.0"
AGGREGATION_UNIT: Final = "NUMBER_LEVEL"
STREAM_WEIGHT_POLICY: Final = "EQUAL_STREAM_WEIGHT"
CORRELATED_FAMILY_POLICY: Final = "FULL_VOTE_PER_FROZEN_STREAM_NO_FAMILY_NORMALIZATION"
TIE_BREAK: Final = "SUPPORT_UNITS_DESC_NUMBER_ASC"
SCORE_DENOMINATOR: Final = 66
EXPECTED_STREAM_COUNT: Final = 11
AGGREGATION_CONTRACT_REVIEW_ID: Final = (
    "B649_11_STREAM_CANONICAL_AGGREGATION_CTO_REVIEW_R1"
)
AGGREGATION_CONTRACT_APPROVED_AT: Final = "2026-09-10T05:50:29Z"
DECISION_RANKING_FORMULA: Final = (
    "U(n)=sum_i((6/k_i)*c_i(n)); rank by U(n) descending, then number ascending; "
    "each stream has equal weight and c_i(n) counts native ticket positions containing n"
)

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]+", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]+", flags=re.ASCII)
_FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "outcome",
        "result",
        "score",
        "official_outcome",
        "winning_numbers",
        "main_numbers",
        "special_number",
    }
)


class CanonicalConsensusInputError(ValueError):
    """Raised when a stream cannot participate in canonical aggregation."""


@dataclass(frozen=True, slots=True)
class StreamConsensusInput:
    """One already-read, provenance-bound production stream prediction."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    prediction_run_id: str
    source_relative_path: str
    source_sha256: str
    prediction_created_at: datetime
    tickets: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        if type(self.strategy_id) is not str or _IDENTIFIER.fullmatch(self.strategy_id) is None:
            raise CanonicalConsensusInputError("strategy_id is not canonical")
        if type(self.strategy_version) is not str or not self.strategy_version.strip():
            raise CanonicalConsensusInputError("strategy_version must be non-empty text")
        if type(self.native_ticket_count) is not int or self.native_ticket_count < 1:
            raise CanonicalConsensusInputError("native_ticket_count must be a positive integer")
        if FINAL_TICKET_SIZE % self.native_ticket_count != 0:
            raise CanonicalConsensusInputError(
                "native_ticket_count must divide the six-number ticket size"
            )
        if type(self.prediction_run_id) is not str or not self.prediction_run_id.strip():
            raise CanonicalConsensusInputError("prediction_run_id must be non-empty text")
        if (
            type(self.source_relative_path) is not str
            or not self.source_relative_path
            or self.source_relative_path.startswith("/")
            or "\\" in self.source_relative_path
            or any(part in {"", ".", ".."} for part in self.source_relative_path.split("/"))
        ):
            raise CanonicalConsensusInputError("source_relative_path must be a safe relative path")
        if type(self.source_sha256) is not str or _SHA256.fullmatch(self.source_sha256) is None:
            raise CanonicalConsensusInputError("source_sha256 must be a lowercase SHA-256 digest")
        if (
            type(self.prediction_created_at) is not datetime
            or self.prediction_created_at.tzinfo is None
            or self.prediction_created_at.utcoffset() is None
        ):
            raise CanonicalConsensusInputError(
                "prediction_created_at must be timezone-aware"
            )
        if type(self.tickets) is not tuple or len(self.tickets) != self.native_ticket_count:
            raise CanonicalConsensusInputError("native ticket count does not match tickets")
        for position, ticket in enumerate(self.tickets, start=1):
            if (
                type(ticket) is not tuple
                or len(ticket) != FINAL_TICKET_SIZE
                or any(type(number) is not int for number in ticket)
                or len(set(ticket)) != FINAL_TICKET_SIZE
                or any(not MIN_NUMBER <= number <= MAX_NUMBER for number in ticket)
            ):
                raise CanonicalConsensusInputError(
                    f"{self.strategy_id}: ticket {position} is not a legal six-number set"
                )

    def canonical_dict(self) -> dict[str, object]:
        """Return the exact six-field manifest row required by the contract."""

        return {
            "native_ticket_count": self.native_ticket_count,
            "prediction_run_id": self.prediction_run_id,
            "source_relative_path": self.source_relative_path,
            "source_sha256": self.source_sha256,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
        }


@dataclass(frozen=True, slots=True)
class CanonicalConsensusContext:
    """Explicit execution identity required by the canonical authority.

    The context is deliberately separate from the aggregation arithmetic.  It
    binds one future target, one causal-history cutoff, and exactly the eleven
    stream records that are allowed to participate in that target's authority.
    No target outcome is represented or accepted here.
    """

    lottery_type: str
    target_draw_number: str
    target_draw_date: str
    scheduled_at: datetime
    causal_cutoff_draw_number: str
    causal_cutoff_date: str
    history_draw_count: int
    history_sha256: str
    streams: tuple[StreamConsensusInput, ...]
    history_caveat: str = "YES"

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not str or not self.lottery_type.strip():
            raise CanonicalConsensusInputError("lottery_type must be non-empty text")
        _validate_draw_identity(self.target_draw_number, self.target_draw_date, "target")
        _validate_draw_identity(
            self.causal_cutoff_draw_number,
            self.causal_cutoff_date,
            "causal cutoff",
        )
        if (
            _draw_key(self.causal_cutoff_draw_number, self.causal_cutoff_date)
            >= _draw_key(self.target_draw_number, self.target_draw_date)
        ):
            raise CanonicalConsensusInputError(
                "causal cutoff must be strictly before target draw"
            )
        if (
            type(self.scheduled_at) is not datetime
            or self.scheduled_at.tzinfo is None
            or self.scheduled_at.utcoffset() is None
        ):
            raise CanonicalConsensusInputError("scheduled_at must be timezone-aware")
        if self.scheduled_at.date().isoformat() != self.target_draw_date:
            raise CanonicalConsensusInputError(
                "scheduled_at local date must match target_draw_date"
            )
        if type(self.history_draw_count) is not int or self.history_draw_count < 1:
            raise CanonicalConsensusInputError(
                "history_draw_count must be a positive integer"
            )
        if (
            type(self.history_sha256) is not str
            or _SHA256.fullmatch(self.history_sha256) is None
        ):
            raise CanonicalConsensusInputError(
                "history_sha256 must be a lowercase SHA-256 digest"
            )
        if type(self.history_caveat) is not str or not self.history_caveat.strip():
            raise CanonicalConsensusInputError("history_caveat must be non-empty text")
        if type(self.streams) is not tuple:
            raise CanonicalConsensusInputError("streams must be an exact tuple of records")
        if len(self.streams) != EXPECTED_STREAM_COUNT:
            raise CanonicalConsensusInputError(
                f"exactly {EXPECTED_STREAM_COUNT} streams are required"
            )
        stream_values = cast(tuple[object, ...], self.streams)
        if any(not isinstance(stream, StreamConsensusInput) for stream in stream_values):
            raise CanonicalConsensusInputError("streams must contain stream input records")
        if len({stream.strategy_id for stream in self.streams}) != len(self.streams):
            raise CanonicalConsensusInputError("stream strategy_id values must be unique")
        if len({stream.source_relative_path for stream in self.streams}) != len(self.streams):
            raise CanonicalConsensusInputError("stream source paths must be unique")
        if any(stream.prediction_created_at >= self.scheduled_at for stream in self.streams):
            raise CanonicalConsensusInputError(
                "every stream prediction_created_at must be before scheduled_at"
            )

    @property
    def stream_inputs(self) -> tuple[StreamConsensusInput, ...]:
        """Compatibility alias for callers that name the records explicitly."""

        return self.streams


@dataclass(frozen=True, slots=True)
class CanonicalConsensusDecision:
    """The complete number ranking and one-ticket recommendation."""

    sources: tuple[StreamConsensusInput, ...]
    support_units: tuple[int, ...]
    deterministic_ranking: tuple[int, ...]
    selected_ranked_numbers: tuple[int, ...]
    final_ticket: tuple[int, ...]
    stream_input_manifest_sha256: str
    context: CanonicalConsensusContext | None = None

    @property
    def number_scores(self) -> tuple[int, ...]:
        """Compatibility alias for callers that use the score terminology."""

        return self.support_units

    @property
    def target_draw_number(self) -> str:
        return self._require_context().target_draw_number

    @property
    def target_draw_date(self) -> str:
        return self._require_context().target_draw_date

    @property
    def input_cutoff_draw_number(self) -> str:
        return self._require_context().causal_cutoff_draw_number

    @property
    def input_cutoff_date(self) -> str:
        return self._require_context().causal_cutoff_date

    @property
    def scheduled_at(self) -> datetime:
        return self._require_context().scheduled_at

    @property
    def history_draw_count(self) -> int:
        return self._require_context().history_draw_count

    @property
    def history_sha256(self) -> str:
        return self._require_context().history_sha256

    def _require_context(self) -> CanonicalConsensusContext:
        if self.context is None:
            raise CanonicalConsensusInputError(
                "explicit canonical execution context is required"
            )
        return self.context
    def decision_fields(self) -> dict[str, object]:
        """Return payload fields that are independent of publication timestamps."""

        return {
            "stream_count": len(self.sources),
            "exact_stream_ids": [source.strategy_id for source in self.sources],
            "stream_inputs": [source.canonical_dict() for source in self.sources],
            "stream_input_manifest_sha256": self.stream_input_manifest_sha256,
            "final_decision_ranking": [
                {
                    "rank": rank,
                    "number": number,
                    "support_units": self.support_units[number - MIN_NUMBER],
                }
                for rank, number in enumerate(self.deterministic_ranking, start=1)
            ],
            "final_recommended_output": [
                {
                    "ticket_position": 1,
                    "predicted_numbers": list(self.final_ticket),
                }
            ],
        }

    def to_payload(self, *, task_id: str, lottery_type: str) -> dict[str, object]:
        """Compatibility serializer for the decision core.

        Publication metadata such as timestamps, implementation identity, and
        temporal attestations is deliberately supplied by the materializer.
        """

        context = self.context
        context_fields: dict[str, object] = {}
        payload_lottery_type = lottery_type
        if context is not None:
            if lottery_type != context.lottery_type:
                raise CanonicalConsensusInputError(
                    "lottery_type does not match canonical execution context"
                )
            payload_lottery_type = context.lottery_type
            context_fields = {
                "target_draw": {
                    "draw_number": context.target_draw_number,
                    "draw_date": context.target_draw_date,
                },
                "max_data_cutoff": context.causal_cutoff_draw_number,
            }
        return {
            "schema_version": CANONICAL_CONSENSUS_SCHEMA_VERSION,
            "task_id": task_id,
            "lottery_type": payload_lottery_type,
            **context_fields,
            "aggregation_method_id": CANONICAL_CONSENSUS_METHOD_ID,
            "aggregation_method_version": CANONICAL_CONSENSUS_METHOD_VERSION,
            "aggregation_unit": AGGREGATION_UNIT,
            "weight_policy": STREAM_WEIGHT_POLICY,
            "correlated_family_policy": CORRELATED_FAMILY_POLICY,
            "tie_break": TIE_BREAK,
            "score_denominator": SCORE_DENOMINATOR,
            "decision_ranking_formula": DECISION_RANKING_FORMULA,
            **self.decision_fields(),
        }


def build_canonical_consensus(
    artifacts: CanonicalConsensusContext
    | Sequence[StreamConsensusInput | Mapping[str, object]],
) -> CanonicalConsensusDecision:
    """Aggregate streams using ``U(n)=sum_i (6/k_i)c_i(n)``.

    ``c_i(n)`` counts ticket positions containing number ``n``.  The resulting
    integer support units have denominator 66 for eleven equal-weight streams;
    ties are resolved by ascending number.  Stream order, ticket order, and
    repeated ticket positions do not change the result.
    """

    context = artifacts if isinstance(artifacts, CanonicalConsensusContext) else None
    if context is not None:
        streams = context.streams
    else:
        stream_artifacts = cast(
            Sequence[StreamConsensusInput | Mapping[str, object]], artifacts
        )
        if not stream_artifacts:
            raise CanonicalConsensusInputError("at least one stream is required")
        streams = tuple(
            item if isinstance(item, StreamConsensusInput) else _from_mapping(item)
            for item in stream_artifacts
        )
    if context is not None and len(streams) != EXPECTED_STREAM_COUNT:
        raise CanonicalConsensusInputError(
            f"exactly {EXPECTED_STREAM_COUNT} streams are required"
        )
    if len({stream.strategy_id for stream in streams}) != len(streams):
        raise CanonicalConsensusInputError("stream strategy_id values must be unique")
    if len({stream.source_relative_path for stream in streams}) != len(streams):
        raise CanonicalConsensusInputError("stream source paths must be unique")

    ordered = tuple(sorted(streams, key=lambda stream: stream.strategy_id))
    support = [0] * MAX_NUMBER
    for stream in ordered:
        factor = FINAL_TICKET_SIZE // stream.native_ticket_count
        for ticket in stream.tickets:
            for number in ticket:
                support[number - MIN_NUMBER] += factor
    expected_total = len(ordered) * FINAL_TICKET_SIZE * FINAL_TICKET_SIZE
    if sum(support) != expected_total:
        raise CanonicalConsensusInputError("support-unit conservation invariant failed")
    ranking = tuple(
        sorted(
            range(MIN_NUMBER, MAX_NUMBER + 1),
            key=lambda number: (-support[number - MIN_NUMBER], number),
        )
    )
    selected = ranking[:FINAL_TICKET_SIZE]
    manifest_bytes = json.dumps(
        [stream.canonical_dict() for stream in ordered],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return CanonicalConsensusDecision(
        sources=ordered,
        support_units=tuple(support),
        deterministic_ranking=ranking,
        selected_ranked_numbers=selected,
        final_ticket=tuple(sorted(selected)),
        stream_input_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        context=context,
    )


def _from_mapping(value: Mapping[str, object]) -> StreamConsensusInput:
    """Accept the operational JSON shape for compatibility and tests."""

    _reject_outcome_keys(value)
    strategy_id = _text(value.get("strategy_id"), "strategy_id")
    strategy_version = _text(value.get("strategy_version", "v0.1"), "strategy_version")
    run_id = _text(value.get("prediction_run_id", f"run-{strategy_id}"), "prediction_run_id")
    source_path = value.get("source_relative_path", value.get("prediction_path"))
    if source_path is None:
        source_path = f"prediction/{run_id}"
    source_sha = value.get("source_sha256", "0" * 64)
    tickets_raw = value.get("tickets")
    if not isinstance(tickets_raw, list):
        raise CanonicalConsensusInputError(f"{strategy_id}: tickets must be a list")
    tickets: list[tuple[int, ...]] = []
    for raw in cast(list[object], tickets_raw):
        if not isinstance(raw, Mapping):
            raise CanonicalConsensusInputError(f"{strategy_id}: ticket must be an object")
        raw_mapping = cast(Mapping[str, object], raw)
        numbers = raw_mapping.get("predicted_numbers")
        if not isinstance(numbers, list):
            raise CanonicalConsensusInputError(f"{strategy_id}: ticket numbers must be a list")
        tickets.append(tuple(cast(list[int], numbers)))
    native_count = value.get("native_ticket_count", len(tickets))
    if type(native_count) is not int:
        raise CanonicalConsensusInputError("native_ticket_count must be an integer")
    return StreamConsensusInput(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        native_ticket_count=native_count,
        prediction_run_id=run_id,
        source_relative_path=_text(source_path, "source_relative_path"),
        source_sha256=_text(source_sha, "source_sha256"),
        prediction_created_at=_datetime(
            value.get("prediction_created_at", "1970-01-01T00:00:00+00:00"),
            "prediction_created_at",
        ),
        tickets=tuple(tickets),
    )


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise CanonicalConsensusInputError(f"{label} must be non-empty text")
    return value


def _datetime(value: object, label: str) -> datetime:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanonicalConsensusInputError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CanonicalConsensusInputError(f"{label} must be timezone-aware")
    return parsed


def _validate_draw_identity(draw_number: str, draw_date: str, label: str) -> None:
    if type(draw_number) is not str or _DRAW_NUMBER.fullmatch(draw_number) is None:
        raise CanonicalConsensusInputError(f"{label} draw number must be numeric text")
    if type(draw_date) is not str:
        raise CanonicalConsensusInputError(f"{label} draw date must be ISO date text")
    try:
        parsed = date.fromisoformat(draw_date)
    except ValueError as exc:
        raise CanonicalConsensusInputError(
            f"{label} draw date must be ISO date text"
        ) from exc
    if parsed.isoformat() != draw_date:
        raise CanonicalConsensusInputError(f"{label} draw date must be ISO date text")


def _draw_key(draw_number: str, draw_date: str) -> tuple[date, int]:
    return date.fromisoformat(draw_date), int(draw_number)


def _reject_outcome_keys(value: object) -> None:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            if key in _FORBIDDEN_OUTCOME_KEYS:
                raise CanonicalConsensusInputError(
                    f"target outcome field is forbidden: {key}"
                )
            _reject_outcome_keys(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        for item in sequence:
            _reject_outcome_keys(item)


__all__ = [
    "AGGREGATION_CONTRACT_APPROVED_AT",
    "AGGREGATION_CONTRACT_REVIEW_ID",
    "AGGREGATION_UNIT",
    "CANONICAL_CONSENSUS_METHOD_ID",
    "CANONICAL_CONSENSUS_METHOD_VERSION",
    "CANONICAL_CONSENSUS_SCHEMA_VERSION",
    "CORRELATED_FAMILY_POLICY",
    "DECISION_RANKING_FORMULA",
    "EXPECTED_STREAM_COUNT",
    "FINAL_TICKET_SIZE",
    "MAX_NUMBER",
    "MIN_NUMBER",
    "PRE_DRAW",
    "SCORE_DENOMINATOR",
    "STREAM_WEIGHT_POLICY",
    "TIE_BREAK",
    "CanonicalConsensusContext",
    "CanonicalConsensusDecision",
    "CanonicalConsensusInputError",
    "StreamConsensusInput",
    "build_canonical_consensus",
]
