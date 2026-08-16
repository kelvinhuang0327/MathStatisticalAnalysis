"""POWER_LOTTO (P638) composition for the shared forward auto-cycle core."""

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
from lottolab.domain.prize_evaluation import evaluate_power_lotto_ticket
from lottolab.strategies.adapters.powerlotto_wave1 import (
    WAVE1_STRATEGY_BY_ID,
    P638HistoryRow,
)
from lottolab.strategies.powerlotto_second_zone import validate_power_lotto_ticket

LOTTERY_TYPE = LotteryType.POWER_LOTTO.value
TASK_ID = "P638_OPERATIONAL_PREDICTION_LOOP_R1"
P638_OPERATION_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/P638_OPERATIONAL_PREDICTION_LOOP_R1"
)

# Both identities are complete native portfolios from the existing P638 Wave 1
# executable registry.  No first-zone-only or invented strategy is admitted.
P638_ENABLED_STRATEGY_IDS = (
    "zonal_entropy_2bet",
    "power_orthogonal_5bet",
)


def _canonical_streams() -> tuple[ForwardCycleStrategyStream, ...]:
    missing = [
        strategy_id
        for strategy_id in P638_ENABLED_STRATEGY_IDS
        if strategy_id not in WAVE1_STRATEGY_BY_ID
    ]
    if missing:
        raise RuntimeError(f"P638 canonical strategy set is missing: {missing}")
    return tuple(
        ForwardCycleStrategyStream(
            strategy_id=spec.strategy_id,
            strategy_version=spec.strategy_version,
            enabled=True,
            adapter_factory=lambda spec=spec: spec,
            native_ticket_count=spec.native_ticket_count,
        )
        for spec in (
            WAVE1_STRATEGY_BY_ID[strategy_id]
            for strategy_id in P638_ENABLED_STRATEGY_IDS
        )
    )


P638_STRATEGY_STREAMS = _canonical_streams()
PredictionTarget = ForwardCycleTarget
HistorySnapshot = ForwardCycleHistorySnapshot[P638HistoryRow]
StrategyStream = ForwardCycleStrategyStream


class P638ForwardAutoCycleAdapter(FileForwardAutoCycleAdapter):
    """Adapt complete POWER_LOTTO tickets to the shared cycle port."""

    lottery_type = LOTTERY_TYPE
    task_id = TASK_ID
    default_operation_root = P638_OPERATION_ROOT
    default_streams = P638_STRATEGY_STREAMS

    def _build_history_snapshot(
        self, target: ForwardCycleTarget
    ) -> ForwardCycleHistorySnapshot[object]:
        snapshot = load_causal_history(
            self.database,
            target=target,
            lottery_type=LotteryType.POWER_LOTTO,
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
        _validate_zone1(main_numbers, "zone1_numbers")
        zone2 = _one_zone2(special_numbers)
        return _outcome_payload(target, main_numbers, zone2, source)

    def _normalize_outcome(
        self,
        target: ForwardCycleTarget,
        outcome: dict[str, object],
    ) -> dict[str, object]:
        if outcome.get("lottery_type", LOTTERY_TYPE) != LOTTERY_TYPE:
            raise ValueError("outcome lottery_type must be POWER_LOTTO")
        if outcome.get("draw_number", target.draw_number) != target.draw_number:
            raise ValueError("outcome draw_number differs from target")
        draw_date = outcome.get("draw_date", target.draw_date)
        if type(draw_date) is not str or draw_date != target.draw_date:
            raise ValueError("outcome draw_date differs from target")
        zone1 = _outcome_zone1(outcome)
        zone2 = _outcome_zone2(outcome)
        _validate_zone1(zone1, "zone1_numbers")
        _validate_zone2(zone2, "zone2_number")
        source = outcome.get("source", "owner:manual")
        if type(source) is not str or not source.strip():
            raise ValueError("outcome source must be non-empty text")
        return _outcome_payload(target, zone1, zone2, source)

    def _outcome_identity(self, outcome: dict[str, object]) -> object:
        return (_outcome_zone1(outcome), _outcome_zone2(outcome))

    def _ticket_to_record(self, ticket: object) -> dict[str, object]:
        if type(ticket) is not tuple:
            raise ValueError("POWER_LOTTO ticket must contain zone1 and zone2")
        raw = cast(tuple[object, ...], ticket)
        if len(raw) != 2:
            raise ValueError("POWER_LOTTO ticket must contain zone1 and zone2")
        zone1 = _number_tuple(raw[0], "zone1_numbers")
        zone2 = raw[1]
        validate_power_lotto_ticket(zone1, zone2)
        if type(zone2) is not int:
            raise ValueError("zone2_number must be an integer")
        return {
            "zone1_numbers": list(zone1),
            "zone2_number": zone2,
            "predicted_numbers": list(zone1),
            "predicted_special_number": zone2,
        }

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
        ticket_scores: list[dict[str, object]] = []
        winning_zone1 = _outcome_zone1(outcome)
        winning_zone2 = _outcome_zone2(outcome)
        for raw_ticket in cast(list[object], tickets):
            if type(raw_ticket) is not dict:
                raise ValueError("prediction ticket must be an object")
            ticket = cast(dict[str, object], raw_ticket)
            zone1 = _number_tuple(
                ticket.get("zone1_numbers", ticket.get("predicted_numbers")),
                "zone1_numbers",
            )
            raw_zone2 = ticket.get(
                "zone2_number", ticket.get("predicted_special_number")
            )
            if type(raw_zone2) is not int:
                raise ValueError("zone2_number must be an integer")
            validate_power_lotto_ticket(zone1, raw_zone2)
            evaluation = evaluate_power_lotto_ticket(
                predicted_main_numbers=zone1,
                predicted_special_number=raw_zone2,
                winning_main_numbers=winning_zone1,
                winning_special_number=winning_zone2,
            )
            ticket_scores.append(
                {
                    "ticket_position": _required_int(ticket, "ticket_position"),
                    "zone1_numbers": list(zone1),
                    "zone2_number": raw_zone2,
                    "zone1_hits": evaluation.zone1_hits,
                    "main_hits": evaluation.zone1_hits,
                    "zone2_hit": evaluation.zone2_hit,
                    "special_hit": evaluation.zone2_hit,
                    "official_any_prize": evaluation.is_winner,
                    "official_prize_tier": evaluation.prize_tier,
                    "official_prize_tier_order": evaluation.prize_tier_order,
                }
            )
        return {
            **metadata,
            "score_status": "SCORED",
            "ticket_scores": ticket_scores,
            "portfolio_score": {
                "max_zone1_hits": max(
                    int(cast(int, ticket["zone1_hits"])) for ticket in ticket_scores
                ),
                "zone2_hit": any(bool(ticket["zone2_hit"]) for ticket in ticket_scores),
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
) -> P638HistoryRow:
    return P638HistoryRow(
        draw=draw_number,
        date=draw_date,
        numbers=main_numbers,
        second_number=_one_zone2(special_numbers),
    )


def _outcome_payload(
    target: ForwardCycleTarget,
    zone1: tuple[int, ...],
    zone2: int,
    source: str,
) -> dict[str, object]:
    return {
        "lottery_type": LOTTERY_TYPE,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "zone1_numbers": list(zone1),
        "zone2_number": zone2,
        "main_numbers": list(zone1),
        "special_number": zone2,
        "source": source,
    }


def _outcome_zone1(outcome: dict[str, object]) -> tuple[int, ...]:
    return _number_tuple(
        outcome.get("zone1_numbers", outcome.get("main_numbers")),
        "outcome zone1_numbers",
    )


def _outcome_zone2(outcome: dict[str, object]) -> int:
    raw = outcome.get("zone2_number", outcome.get("special_number"))
    if type(raw) is not int:
        raise ValueError("outcome zone2_number must be an integer")
    return raw


def _number_tuple(raw: object, label: str) -> tuple[int, ...]:
    if type(raw) not in (list, tuple):
        raise ValueError(f"{label} must be an integer list")
    values = cast(list[object] | tuple[object, ...], raw)
    if any(type(value) is not int for value in values):
        raise ValueError(f"{label} must be an integer list")
    return tuple(cast(tuple[int, ...], tuple(values)))


def _one_zone2(numbers: tuple[int, ...]) -> int:
    if len(numbers) != 1 or type(numbers[0]) is not int:
        raise ValueError("POWER_LOTTO history/outcome must contain one zone2 number")
    _validate_zone2(numbers[0], "zone2_number")
    return numbers[0]


def _validate_zone1(numbers: tuple[int, ...], label: str) -> None:
    if (
        type(numbers) is not tuple
        or len(numbers) != 6
        or any(type(number) is not int for number in numbers)
        or numbers != tuple(sorted(numbers))
        or len(set(numbers)) != 6
        or any(number < 1 or number > 38 for number in numbers)
    ):
        raise ValueError(f"{label} must be six unique ascending POWER_LOTTO numbers")


def _validate_zone2(number: int, label: str) -> None:
    if type(number) is not int or not 1 <= number <= 8:
        raise ValueError(f"{label} must be an integer from 1 through 8")


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
    "P638_ENABLED_STRATEGY_IDS",
    "P638_OPERATION_ROOT",
    "P638_STRATEGY_STREAMS",
    "TASK_ID",
    "HistorySnapshot",
    "P638ForwardAutoCycleAdapter",
    "PredictionTarget",
    "StrategyStream",
]
