"""Compose existing Replay snapshots into the existing base-method evaluation.

One pure, deterministic seam and nothing else: this module owns no metric
mathematics, no window semantics, no ranking, no persistence, and no second
replay engine. It converts already-computed
:class:`~lottolab.domain.replay_predictions.ReplayPredictionSnapshot` objects
plus caller-supplied realized draw outcomes into
:class:`~lottolab.research.base_method_evaluation.MethodDrawObservation`
values, then hands them to the unmodified
:func:`~lottolab.research.base_method_evaluation.evaluate_method`.

Scope is deliberately one ``SINGLE_TICKET`` strategy per invocation. Every
window kind, hit tier, random reference and exact ``Fraction`` in the returned
:class:`~lottolab.research.base_method_evaluation.MethodEvaluationRecord` is
produced by that existing evaluator, so composing through this seam can never
disagree with calling the evaluator directly.

Fail-closed by construction: a replay snapshot whose causal history or
prediction did not succeed is never silently recorded as a zero-hit draw, and a
target whose outcome is missing, duplicated, unused, or identity-mismatched
raises instead of quietly dropping a draw. Ordering is the caller's --
observations are emitted in snapshot order and never sorted -- matching both
Replay's own target-major convention and the evaluator's documented "caller
supplies ascending chronological order" contract.

Like :mod:`lottolab.research.base_method_evaluation`, this module adds no
lottery-specific code path: the match parameters arrive as a
``LotteryMatchContract``. The V1A scope exercised here is BIG_LOTTO only.
This module records; it never ranks, promotes, persists, or takes any position
on whether a method is good.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.research.base_method_evaluation import (
    BIG_LOTTO_MATCH_CONTRACT,
    ExposureKind,
    LotteryMatchContract,
    MethodDrawObservation,
    MethodEvaluationRecord,
    MethodExposure,
    MethodIdentity,
    MethodTargetCoverage,
    OutputShape,
    ReplayStatus,
    evaluate_method,
)

#: A snapshot is only evaluable when both closed-result stages succeeded.
OK_STATUS = "OK"

#: V1A evaluates exactly one native ticket per draw, per invocation.
SINGLE_TICKET_COUNT = 1


class ReplayMethodEvaluationError(ValueError):
    """Closed-contract failure while composing replay snapshots into evaluation input."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayMethodEvaluationError(message)


@dataclass(frozen=True, slots=True)
class ReplayTargetOutcome:
    """The realized main-number outcome of one replay target draw.

    Supplied explicitly by the caller rather than read from any outcome store:
    this module performs no I/O, so a hermetic caller can evaluate a synthetic
    fixture with exactly the same code path a real one would use.
    """

    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        _require(bool(self.draw_number), "draw_number must be a non-empty string")
        _require(type(self.draw_date) is date, "draw_date must be a date")
        _require(len(self.main_numbers) > 0, "main_numbers must not be empty")
        _require(
            len(set(self.main_numbers)) == len(self.main_numbers),
            "main_numbers must not contain duplicates",
        )


def _validate_number_set(
    numbers: tuple[int, ...],
    *,
    expected_count: int,
    population_size: int,
    label: str,
    draw_number: str,
) -> None:
    _require(
        len(numbers) == expected_count,
        f"{label} for draw {draw_number} must contain exactly {expected_count} numbers",
    )
    _require(
        len(set(numbers)) == len(numbers),
        f"{label} for draw {draw_number} must not contain duplicates",
    )
    _require(
        all(1 <= number <= population_size for number in numbers),
        f"{label} for draw {draw_number} must fall within 1..{population_size}",
    )


def _resolve_single_strategy(
    snapshots: Sequence[ReplayPredictionSnapshot],
) -> tuple[str, str]:
    """Return the one ``(strategy_id, strategy_version)`` the batch evaluates.

    Fails closed on a mixed batch and on an unresolved strategy identity: a
    snapshot whose ``strategy_id`` the catalog could not resolve carries no
    ``strategy_version``, and an evaluation record must never claim an identity
    the replay itself could not establish.
    """

    strategy_ids = {snapshot.strategy_id for snapshot in snapshots}
    _require(
        len(strategy_ids) == 1,
        "snapshots must all belong to exactly one strategy_id per invocation",
    )
    strategy_id = snapshots[0].strategy_id
    versions = {snapshot.strategy_version for snapshot in snapshots}
    _require(
        len(versions) == 1,
        f"snapshots for {strategy_id} must all carry the same strategy_version",
    )
    strategy_version = snapshots[0].strategy_version
    _require(
        strategy_version is not None,
        f"strategy identity for {strategy_id} was never resolved by the replay catalog",
    )
    assert strategy_version is not None  # narrowed by the check above
    return strategy_id, strategy_version


def _index_outcomes(
    outcomes: Sequence[ReplayTargetOutcome],
) -> dict[str, ReplayTargetOutcome]:
    indexed: dict[str, ReplayTargetOutcome] = {}
    for outcome in outcomes:
        _require(
            outcome.draw_number not in indexed,
            f"outcomes contain a duplicate entry for draw {outcome.draw_number}",
        )
        indexed[outcome.draw_number] = outcome
    return indexed


def build_method_draw_observations(
    snapshots: Sequence[ReplayPredictionSnapshot],
    outcomes: Sequence[ReplayTargetOutcome],
    *,
    contract: LotteryMatchContract = BIG_LOTTO_MATCH_CONTRACT,
) -> tuple[MethodDrawObservation, ...]:
    """Bind each replay snapshot to its realized outcome, in snapshot order.

    ``snapshots`` order is preserved verbatim -- this function never sorts,
    deduplicates, or reorders -- so the caller keeps full responsibility for the
    ascending chronological order ``evaluate_method`` documents. Every snapshot
    must have succeeded at both stages, and every outcome must be consumed
    exactly once by a snapshot whose target identity matches it.
    """

    _require(len(snapshots) > 0, "snapshots must not be empty")

    indexed_outcomes = _index_outcomes(outcomes)
    observations: list[MethodDrawObservation] = []
    consumed: set[str] = set()

    for snapshot in snapshots:
        draw_number = snapshot.target_draw_number
        _require(
            snapshot.lottery_type.value == contract.lottery_type,
            f"snapshot for draw {draw_number} is not a {contract.lottery_type} snapshot",
        )
        _require(
            draw_number not in consumed,
            f"snapshots contain a duplicate target draw {draw_number}",
        )
        _require(
            snapshot.history_status == OK_STATUS,
            f"snapshot for draw {draw_number} has history_status "
            f"{snapshot.history_status!r} and is not evaluable",
        )
        _require(
            snapshot.prediction_status == OK_STATUS,
            f"snapshot for draw {draw_number} has prediction_status "
            f"{snapshot.prediction_status!r} and is not evaluable",
        )
        predicted = snapshot.predicted_main_numbers
        _require(
            predicted is not None,
            f"snapshot for draw {draw_number} carries no predicted_main_numbers",
        )
        assert predicted is not None  # narrowed by the check above
        _validate_number_set(
            predicted,
            expected_count=contract.ticket_number_count,
            population_size=contract.population_size,
            label="predicted_main_numbers",
            draw_number=draw_number,
        )

        outcome = indexed_outcomes.get(draw_number)
        _require(
            outcome is not None,
            f"no target outcome was supplied for draw {draw_number}",
        )
        assert outcome is not None  # narrowed by the check above
        _require(
            outcome.draw_date == snapshot.target_draw_date,
            f"outcome for draw {draw_number} has draw_date {outcome.draw_date} "
            f"but the snapshot targets {snapshot.target_draw_date}",
        )
        _validate_number_set(
            outcome.main_numbers,
            expected_count=contract.winning_number_count,
            population_size=contract.population_size,
            label="outcome main_numbers",
            draw_number=draw_number,
        )

        main_hit_count = len(set(predicted) & set(outcome.main_numbers))
        consumed.add(draw_number)
        observations.append(
            MethodDrawObservation(
                draw_id=draw_number,
                draw_date=snapshot.target_draw_date.isoformat(),
                native_ticket_count=SINGLE_TICKET_COUNT,
                distinct_ticket_count=SINGLE_TICKET_COUNT,
                main_hit_counts=(main_hit_count,),
            )
        )

    unused = sorted(set(indexed_outcomes) - consumed)
    _require(
        not unused,
        f"outcomes were supplied for draws with no matching snapshot: {', '.join(unused)}",
    )
    return tuple(observations)


def build_single_ticket_identity(
    snapshots: Sequence[ReplayPredictionSnapshot],
    observations: Sequence[MethodDrawObservation],
    *,
    method_family: str,
    replay_status: ReplayStatus,
) -> MethodIdentity:
    """Derive the evaluation identity from the replay itself, not from the caller.

    ``method_id``/``method_version`` come from the snapshots' own resolved
    strategy identity so a record can never describe a different method than
    the one that was actually replayed. Exposure is fixed at one native ticket,
    which is what makes the record's ``output_shape`` ``SINGLE_OUTPUT``.
    """

    _require(len(observations) > 0, "observations must not be empty")
    _require(bool(method_family), "method_family must be a non-empty string")
    strategy_id, strategy_version = _resolve_single_strategy(snapshots)
    return MethodIdentity(
        method_id=strategy_id,
        method_version=strategy_version,
        method_family=method_family,
        output_shape=OutputShape.SINGLE_OUTPUT,
        exposure=MethodExposure(
            kind=ExposureKind.FIXED,
            minimum_native_ticket_count=SINGLE_TICKET_COUNT,
            maximum_native_ticket_count=SINGLE_TICKET_COUNT,
        ),
        target_coverage=MethodTargetCoverage(
            eligible_draw_count=len(observations),
            first_draw_id=observations[0].draw_id,
            last_draw_id=observations[-1].draw_id,
        ),
        replay_status=replay_status,
    )


def evaluate_replayed_single_ticket_method(
    snapshots: Sequence[ReplayPredictionSnapshot],
    outcomes: Sequence[ReplayTargetOutcome],
    *,
    method_family: str,
    replay_status: ReplayStatus,
    contract: LotteryMatchContract = BIG_LOTTO_MATCH_CONTRACT,
) -> MethodEvaluationRecord:
    """Replay snapshots plus realized outcomes to one full evaluation record.

    The whole seam in one call: bind, convert, then delegate to the unmodified
    :func:`evaluate_method`. All four window kinds, every hit tier, the random
    references and the exact ``Fraction`` arithmetic come from that evaluator.
    """

    observations = build_method_draw_observations(snapshots, outcomes, contract=contract)
    identity = build_single_ticket_identity(
        snapshots,
        observations,
        method_family=method_family,
        replay_status=replay_status,
    )
    return evaluate_method(contract, identity, observations)


__all__ = [
    "OK_STATUS",
    "SINGLE_TICKET_COUNT",
    "ReplayMethodEvaluationError",
    "ReplayTargetOutcome",
    "build_method_draw_observations",
    "build_single_ticket_identity",
    "evaluate_replayed_single_ticket_method",
]
