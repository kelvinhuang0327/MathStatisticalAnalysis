"""DAILY_539 composition for the shared forward auto-cycle core."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast

from lottolab.application.forward_auto_cycle_operational import (
    FileForwardAutoCycleAdapter,
    ForwardCycleHistorySnapshot,
    ForwardCycleStrategyStream,
    ForwardCycleTarget,
    load_causal_history,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prize_evaluation import evaluate_daily_539_ticket
from lottolab.strategies.adapters.base import CausalDrawRow
from tools.run_daily539_t539_wave1 import DEFAULT_STRATEGY_SPECS

LOTTERY_TYPE = LotteryType.DAILY_539.value
TASK_ID = "T539_OPERATIONAL_PREDICTION_LOOP_R1"
T539_OPERATION_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/T539_OPERATIONAL_PREDICTION_LOOP_R1"
)

# These identities are existing complete entries from the task-owned canonical
# T539 executable set.  The adapter intentionally selects only a small forward
# representative subset for R1.
T539_ENABLED_STRATEGY_IDS = (
    "daily539_markov_cold",
    "daily539_f4cold_3bet",
)


def _canonical_streams() -> tuple[ForwardCycleStrategyStream, ...]:
    by_id = {spec.strategy_id: spec for spec in DEFAULT_STRATEGY_SPECS}
    missing = [strategy_id for strategy_id in T539_ENABLED_STRATEGY_IDS if strategy_id not in by_id]
    if missing:
        raise RuntimeError(f"T539 canonical strategy set is missing: {missing}")
    return tuple(
        ForwardCycleStrategyStream(
            strategy_id=by_id[strategy_id].strategy_id,
            strategy_version=by_id[strategy_id].strategy_version,
            enabled=True,
            adapter_factory=by_id[strategy_id].adapter_factory,
            native_ticket_count=by_id[strategy_id].native_ticket_count,
        )
        for strategy_id in T539_ENABLED_STRATEGY_IDS
    )


T539_STRATEGY_STREAMS = _canonical_streams()
PredictionTarget = ForwardCycleTarget
HistorySnapshot = ForwardCycleHistorySnapshot[CausalDrawRow]
StrategyStream = ForwardCycleStrategyStream


class T539ForwardAutoCycleAdapter(FileForwardAutoCycleAdapter):
    """Adapt DAILY_539-native strategies to the shared cycle port."""

    lottery_type = LOTTERY_TYPE
    task_id = TASK_ID
    default_operation_root = T539_OPERATION_ROOT
    default_streams = T539_STRATEGY_STREAMS

    def _build_history_snapshot(
        self, target: ForwardCycleTarget
    ) -> ForwardCycleHistorySnapshot[object]:
        snapshot = load_causal_history(
            self.database,
            target=target,
            lottery_type=LotteryType.DAILY_539,
            operation_root=self.root,
            row_factory=_history_row,
            as_of=self._clock(),
        )
        return cast(ForwardCycleHistorySnapshot[object], snapshot)

    def _format_draw_outcome(
        self,
        target: ForwardCycleTarget,
        main_numbers: tuple[int, ...],
        special_numbers: tuple[int, ...],
        source: str,
    ) -> dict[str, object]:
        _validate_numbers(main_numbers, "main_numbers")
        if special_numbers:
            raise ValueError("DAILY_539 outcome must not contain a second-zone number")
        return {
            "lottery_type": LOTTERY_TYPE,
            "draw_number": target.draw_number,
            "draw_date": target.draw_date,
            "main_numbers": list(main_numbers),
            "winning_numbers": list(main_numbers),
            "source": source,
        }

    def _normalize_outcome(
        self,
        target: ForwardCycleTarget,
        outcome: dict[str, object],
    ) -> dict[str, object]:
        if outcome.get("lottery_type", LOTTERY_TYPE) != LOTTERY_TYPE:
            raise ValueError("outcome lottery_type must be DAILY_539")
        draw_number = outcome.get("draw_number", target.draw_number)
        if draw_number != target.draw_number:
            raise ValueError("outcome draw_number differs from target")
        draw_date = outcome.get("draw_date", target.draw_date)
        if type(draw_date) is not str or draw_date != target.draw_date:
            raise ValueError("outcome draw_date differs from target")
        numbers = _outcome_numbers(outcome)
        _validate_numbers(numbers, "main_numbers")
        if outcome.get("special_number") not in (None, 0):
            raise ValueError("DAILY_539 outcome must not contain special_number")
        source = outcome.get("source", "owner:manual")
        if type(source) is not str or not source.strip():
            raise ValueError("outcome source must be non-empty text")
        return {
            "lottery_type": LOTTERY_TYPE,
            "draw_number": target.draw_number,
            "draw_date": target.draw_date,
            "main_numbers": list(numbers),
            "winning_numbers": list(numbers),
            "source": source,
        }

    def _outcome_identity(self, outcome: dict[str, object]) -> object:
        return _outcome_numbers(outcome)

    def _ticket_to_record(self, ticket: object) -> dict[str, object]:
        if type(ticket) is not tuple:
            raise ValueError("DAILY_539 ticket must be a tuple")
        numbers = cast(tuple[object, ...], ticket)
        if len(numbers) != 5 or any(type(number) is not int for number in numbers):
            raise ValueError("DAILY_539 ticket must contain five integers")
        validated = tuple(cast(tuple[int, ...], numbers))
        _validate_numbers(validated, "predicted_numbers")
        return {"predicted_numbers": list(validated)}

    def _score_prediction(
        self,
        prediction: dict[str, object],
        outcome: dict[str, object],
        scored_at: datetime,
    ) -> dict[str, object]:
        tickets = prediction.get("tickets")
        metadata = {
            "schema_version": "forward-operational-score-v1",
            "lottery_type": LOTTERY_TYPE,
            "draw_number": _required_text(prediction, "draw_number"),
            "prediction_run_id": _required_text(prediction, "prediction_run_id"),
            "strategy_id": _required_text(prediction, "strategy_id"),
            "strategy_version": _required_text(prediction, "strategy_version"),
            "prediction_temporal_class": _required_text(
                prediction, "prediction_temporal_class"
            ),
            "outcome_revision": _required_int(outcome, "revision", default=0),
            "outcome_updated_at": outcome.get("updated_at"),
            "outcome_source": outcome.get("source"),
            "scored_at": scored_at.isoformat(timespec="microseconds"),
        }
        if prediction.get("availability") != "AVAILABLE" or type(tickets) is not list:
            return {
                **metadata,
                "score_status": "UNAVAILABLE",
                "availability": prediction.get("availability"),
                "unavailable_reason": prediction.get("unavailable_reason"),
                "ticket_scores": [],
            }
        raw_tickets = cast(list[object], tickets)
        ticket_scores: list[dict[str, object]] = []
        winning_numbers = _outcome_numbers(outcome)
        for raw_ticket in raw_tickets:
            if type(raw_ticket) is not dict:
                raise ValueError("prediction ticket must be an object")
            ticket = cast(dict[str, object], raw_ticket)
            predicted = _ticket_numbers(ticket)
            evaluation = evaluate_daily_539_ticket(
                predicted_main_numbers=predicted,
                winning_main_numbers=winning_numbers,
            )
            ticket_scores.append(
                {
                    "ticket_position": _required_int(ticket, "ticket_position"),
                    "predicted_numbers": list(predicted),
                    "main_hits": evaluation.zone1_hits,
                    "zone1_hits": evaluation.zone1_hits,
                    "official_any_prize": evaluation.is_winner,
                    "official_prize_tier": evaluation.prize_tier,
                    "zone2_hit": False,
                }
            )
        return {
            **metadata,
            "score_status": "SCORED",
            "ticket_scores": ticket_scores,
            "portfolio_score": {
                "max_main_hits": max(
                    int(cast(int, ticket["main_hits"])) for ticket in ticket_scores
                ),
                "official_any_prize": any(
                    bool(ticket["official_any_prize"]) for ticket in ticket_scores
                ),
                "winning_ticket_count": sum(
                    int(bool(ticket["official_any_prize"])) for ticket in ticket_scores
                ),
            },
        }


def _history_row(
    draw_number: str,
    draw_date: str,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
) -> CausalDrawRow:
    if special_numbers:
        raise ValueError("DAILY_539 history must not contain a second zone")
    _validate_numbers(main_numbers, "history numbers")
    return CausalDrawRow(draw=draw_number, date=draw_date, numbers=main_numbers)


def _outcome_numbers(outcome: dict[str, object]) -> tuple[int, ...]:
    raw = outcome.get("main_numbers", outcome.get("winning_numbers"))
    return _number_tuple(raw, "outcome main_numbers")


def _ticket_numbers(ticket: dict[str, object]) -> tuple[int, ...]:
    return _number_tuple(ticket.get("predicted_numbers"), "predicted_numbers")


def _number_tuple(raw: object, label: str) -> tuple[int, ...]:
    if type(raw) not in (list, tuple):
        raise ValueError(f"{label} must be an integer list")
    values = cast(list[object] | tuple[object, ...], raw)
    if any(type(value) is not int for value in values):
        raise ValueError(f"{label} must be an integer list")
    return tuple(cast(tuple[int, ...], tuple(values)))


def _validate_numbers(numbers: tuple[int, ...], label: str) -> None:
    if (
        type(numbers) is not tuple
        or len(numbers) != 5
        or any(type(number) is not int for number in numbers)
        or numbers != tuple(sorted(numbers))
        or len(set(numbers)) != 5
        or any(number < 1 or number > 39 for number in numbers)
    ):
        raise ValueError(f"{label} must be five unique ascending DAILY_539 numbers")


def _required_text(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if type(result) is not str or not result:
        raise ValueError(f"{key} must be non-empty text")
    return result


def _required_int(
    value: dict[str, object], key: str, *, default: int | None = None
) -> int:
    result = value.get(key, default)
    if type(result) is not int:
        raise ValueError(f"{key} must be an integer")
    return result


__all__ = [
    "LOTTERY_TYPE",
    "T539_ENABLED_STRATEGY_IDS",
    "T539_OPERATION_ROOT",
    "T539_STRATEGY_STREAMS",
    "TASK_ID",
    "HistorySnapshot",
    "PredictionTarget",
    "StrategyStream",
    "T539ForwardAutoCycleAdapter",
]
