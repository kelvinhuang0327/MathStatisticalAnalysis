"""Outcome-free canonical Goal-C consensus for B649 prediction artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

MIN_NUMBER: Final = 1
MAX_NUMBER: Final = 49
FINAL_TICKET_SIZE: Final = 6
PRE_DRAW: Final = "PRE_DRAW"
TEST_FAMILY_ID: Final = "test_family"
CANONICAL_CONSENSUS_SCHEMA_VERSION: Final = "b649-canonical-consensus-v1"
CANONICAL_CONSENSUS_METHOD_ID: Final = (
    "B649_GOALC_CANONICAL_FAMILY_BINARY_PRESENCE_V1"
)


class CanonicalConsensusInputError(ValueError):
    """Raised when prediction artifacts cannot participate in consensus."""


@dataclass(frozen=True, slots=True)
class CanonicalConsensusSource:
    """One parsed prediction artifact used as consensus provenance."""

    strategy_id: str
    prediction_run_id: str
    artifact_ref: str
    ticket_count: int
    history_sha256: str | None


@dataclass(frozen=True, slots=True)
class CanonicalConsensusFamily:
    """One canonical family after strategy-stream normalization."""

    family_id: str
    family_type: str
    source_strategy_ids: tuple[str, ...]
    source_artifact_refs: tuple[str, ...]
    union_numbers: tuple[int, ...]
    number_presence: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CanonicalConsensusDecision:
    """Deterministic canonical consensus decision and its decision trace."""

    target_draw_number: str
    target_draw_date: str
    input_cutoff_draw_number: str
    input_cutoff_date: str
    sources: tuple[CanonicalConsensusSource, ...]
    families: tuple[CanonicalConsensusFamily, ...]
    number_scores: tuple[int, ...]
    deterministic_ranking: tuple[int, ...]
    selected_ranked_numbers: tuple[int, ...]
    final_ticket: tuple[int, ...]

    @property
    def family_count(self) -> int:
        return len(self.families)

    def to_payload(self, *, task_id: str, lottery_type: str) -> dict[str, object]:
        """Serialize the decision using the canonical persisted contract."""

        family_scores = {
            family.family_id: _number_score_map(family.number_presence)
            for family in self.families
        }
        family_definitions = [
            {
                "family_id": family.family_id,
                "family_type": family.family_type,
                "source_strategy_ids": list(family.source_strategy_ids),
                "source_artifact_refs": list(family.source_artifact_refs),
                "union_numbers": list(family.union_numbers),
            }
            for family in self.families
        ]
        ranking = [
            {
                "rank": position,
                "number": number,
                "score": self.number_scores[number - MIN_NUMBER],
            }
            for position, number in enumerate(self.deterministic_ranking, start=1)
        ]
        return {
            "schema_version": CANONICAL_CONSENSUS_SCHEMA_VERSION,
            "task_id": task_id,
            "lottery_type": lottery_type,
            "draw_number": self.target_draw_number,
            "draw_date": self.target_draw_date,
            "target_draw": {
                "draw_number": self.target_draw_number,
                "draw_date": self.target_draw_date,
            },
            "input_cutoff": {
                "draw_number": self.input_cutoff_draw_number,
                "draw_date": self.input_cutoff_date,
            },
            "prediction_temporal_class": PRE_DRAW,
            "consensus_method": CANONICAL_CONSENSUS_METHOD_ID,
            "family_voting_unit": "STRATEGY_FAMILY",
            "stream_weighting": "1_PER_FAMILY",
            "multi_ticket_policy": "BINARY_NUMBER_PRESENCE_PER_FAMILY",
            "native_weight_policy": "NONE",
            "test_family_policy": "ALL_TEST_STREAMS_COLLAPSED",
            "diversity_override": "NONE",
            "coverage_override": "NONE",
            "anti_correlation_override": "NONE",
            "family_count": self.family_count,
            "family_definitions": family_definitions,
            "family_scores": family_scores,
            "number_scores": _number_score_map(self.number_scores),
            "deterministic_ranking": ranking,
            "selected_ranked_numbers": list(self.selected_ranked_numbers),
            "final_ticket_count": 1,
            "final_recommended_ticket": list(self.final_ticket),
            "final_recommended_ticket_display": " ".join(
                f"{number:02d}" for number in self.final_ticket
            ),
            "input_artifacts": [
                {
                    "strategy_id": source.strategy_id,
                    "prediction_run_id": source.prediction_run_id,
                    "artifact_ref": source.artifact_ref,
                    "ticket_count": source.ticket_count,
                    "history_sha256": source.history_sha256,
                }
                for source in self.sources
            ],
            "outcome_dependence": "NONE",
        }


@dataclass(frozen=True, slots=True)
class _ParsedArtifact:
    strategy_id: str
    prediction_run_id: str
    artifact_ref: str
    target_draw_number: str
    target_draw_date: str
    input_cutoff_draw_number: str
    input_cutoff_date: str
    tickets: tuple[tuple[int, ...], ...]
    history_sha256: str | None


@dataclass(slots=True)
class _FamilyAccumulator:
    family_type: str
    source_strategy_ids: set[str]
    source_artifact_refs: set[str]
    union_numbers: set[int]


def build_canonical_consensus(
    artifacts: Sequence[Mapping[str, object]],
) -> CanonicalConsensusDecision:
    """Build one canonical decision from already-parsed PRE_DRAW artifacts.

    The function performs no file, clock, database, network, or outcome access.
    Each artifact contributes at most one presence vote through its normalized
    family, regardless of its ticket count or duplicate ticket appearances.
    """

    if not artifacts:
        raise CanonicalConsensusInputError("at least one prediction artifact is required")

    parsed = tuple(_parse_artifact(artifact) for artifact in artifacts)
    first = parsed[0]
    for artifact in parsed[1:]:
        if artifact.target_draw_number != first.target_draw_number:
            raise CanonicalConsensusInputError("artifacts target different draws")
        if artifact.target_draw_date != first.target_draw_date:
            raise CanonicalConsensusInputError("artifacts target different draw dates")
        if artifact.input_cutoff_draw_number != first.input_cutoff_draw_number:
            raise CanonicalConsensusInputError("artifacts use different input cutoffs")
        if artifact.input_cutoff_date != first.input_cutoff_date:
            raise CanonicalConsensusInputError("artifacts use different cutoff dates")

    if int(first.input_cutoff_draw_number) >= int(first.target_draw_number):
        raise CanonicalConsensusInputError("input cutoff must precede the target draw")

    families_by_id: dict[str, _FamilyAccumulator] = {}
    for artifact in parsed:
        family_id, family_type = _classify_family(artifact.strategy_id)
        family = families_by_id.setdefault(
            family_id,
            _FamilyAccumulator(
                family_type=family_type,
                source_strategy_ids=set(),
                source_artifact_refs=set(),
                union_numbers=set(),
            ),
        )
        family.source_strategy_ids.add(artifact.strategy_id)
        family.source_artifact_refs.add(artifact.artifact_ref)
        for ticket in artifact.tickets:
            family.union_numbers.update(ticket)

    families = tuple(
        CanonicalConsensusFamily(
            family_id=family_id,
            family_type=family.family_type,
            source_strategy_ids=tuple(sorted(family.source_strategy_ids)),
            source_artifact_refs=tuple(sorted(family.source_artifact_refs)),
            union_numbers=tuple(sorted(family.union_numbers)),
            number_presence=tuple(
                1 if number in family.union_numbers else 0
                for number in range(MIN_NUMBER, MAX_NUMBER + 1)
            ),
        )
        for family_id, family in sorted(families_by_id.items())
    )
    number_scores = tuple(
        sum(family.number_presence[index] for family in families)
        for index in range(MAX_NUMBER)
    )
    ranking = tuple(
        sorted(
            range(MIN_NUMBER, MAX_NUMBER + 1),
            key=lambda number: (-number_scores[number - MIN_NUMBER], number),
        )
    )
    selected = ranking[:FINAL_TICKET_SIZE]
    sources = tuple(
        CanonicalConsensusSource(
            strategy_id=artifact.strategy_id,
            prediction_run_id=artifact.prediction_run_id,
            artifact_ref=artifact.artifact_ref,
            ticket_count=len(artifact.tickets),
            history_sha256=artifact.history_sha256,
        )
        for artifact in sorted(
            parsed,
            key=lambda item: (
                item.strategy_id,
                item.artifact_ref,
                item.prediction_run_id,
            ),
        )
    )
    return CanonicalConsensusDecision(
        target_draw_number=first.target_draw_number,
        target_draw_date=first.target_draw_date,
        input_cutoff_draw_number=first.input_cutoff_draw_number,
        input_cutoff_date=first.input_cutoff_date,
        sources=sources,
        families=families,
        number_scores=number_scores,
        deterministic_ranking=ranking,
        selected_ranked_numbers=selected,
        final_ticket=tuple(sorted(selected)),
    )


def _classify_family(strategy_id: str) -> tuple[str, str]:
    if any(part.startswith("test_") for part in strategy_id.split("__")):
        return TEST_FAMILY_ID, "TEST"
    return strategy_id, "STRATEGY"


def _parse_artifact(artifact: Mapping[str, object]) -> _ParsedArtifact:
    strategy_id = _required_text(artifact, "strategy_id")
    prediction_run_id = _required_text(artifact, "prediction_run_id")
    target_draw_number = _required_text(artifact, "draw_number")
    target_draw_date = _required_text(artifact, "draw_date")
    prediction_phase = _required_text(artifact, "prediction_temporal_class")
    if prediction_phase != PRE_DRAW:
        raise CanonicalConsensusInputError(
            f"{strategy_id}: consensus requires {PRE_DRAW} artifacts"
        )

    cutoff = _as_mapping(artifact.get("history_cutoff"), f"{strategy_id}: history_cutoff")
    input_cutoff_draw_number = _required_text(cutoff, "draw_number")
    input_cutoff_date = _required_text(cutoff, "draw_date")

    raw_tickets = artifact.get("tickets")
    if not isinstance(raw_tickets, list):
        raise CanonicalConsensusInputError(f"{strategy_id}: tickets must be a list")
    tickets: list[tuple[int, ...]] = []
    for index, raw_ticket in enumerate(cast(list[object], raw_tickets), start=1):
        ticket = _as_mapping(raw_ticket, f"{strategy_id}: ticket {index}")
        raw_numbers = ticket.get("predicted_numbers")
        if not isinstance(raw_numbers, list):
            raise CanonicalConsensusInputError(
                f"{strategy_id}: ticket {index} numbers must be a list"
            )
        numbers: list[int] = []
        for number in cast(list[object], raw_numbers):
            if type(number) is not int or not MIN_NUMBER <= number <= MAX_NUMBER:
                raise CanonicalConsensusInputError(
                    f"{strategy_id}: ticket {index} contains an invalid number"
                )
            numbers.append(number)
        tickets.append(tuple(numbers))

    artifact_ref = _optional_text(artifact, "prediction_path")
    if artifact_ref is None:
        artifact_ref = _optional_text(artifact, "artifact_ref")
    if artifact_ref is None:
        artifact_ref = f"prediction://{prediction_run_id}"
    history_sha256 = _optional_text(artifact, "history_sha256")
    return _ParsedArtifact(
        strategy_id=strategy_id,
        prediction_run_id=prediction_run_id,
        artifact_ref=artifact_ref,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        input_cutoff_draw_number=input_cutoff_draw_number,
        input_cutoff_date=input_cutoff_date,
        tickets=tuple(tickets),
        history_sha256=history_sha256,
    )


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CanonicalConsensusInputError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _required_text(value: Mapping[str, object], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise CanonicalConsensusInputError(f"{key} must be non-empty text")
    if key in {"draw_number", "history_cutoff"} and not raw.isdigit():
        raise CanonicalConsensusInputError(f"{key} must contain only digits")
    return raw


def _optional_text(value: Mapping[str, object], key: str) -> str | None:
    raw = value.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise CanonicalConsensusInputError(f"{key} must be non-empty text when present")
    return raw


def _number_score_map(scores: tuple[int, ...]) -> dict[str, int]:
    if len(scores) != MAX_NUMBER:
        raise CanonicalConsensusInputError("number score vector must cover 01 through 49")
    return {
        f"{index:02d}": scores[index - MIN_NUMBER]
        for index in range(MIN_NUMBER, MAX_NUMBER + 1)
    }


__all__ = [
    "CANONICAL_CONSENSUS_METHOD_ID",
    "CANONICAL_CONSENSUS_SCHEMA_VERSION",
    "FINAL_TICKET_SIZE",
    "MAX_NUMBER",
    "MIN_NUMBER",
    "PRE_DRAW",
    "TEST_FAMILY_ID",
    "CanonicalConsensusDecision",
    "CanonicalConsensusFamily",
    "CanonicalConsensusInputError",
    "CanonicalConsensusSource",
    "build_canonical_consensus",
]
