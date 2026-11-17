"""Separate, fail-closed eight-tier research view of an existing replay cell."""

from __future__ import annotations

from typing import Any, cast

from lottolab.domain.lottery_rules import (
    BigLottoPrizeTier,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)


def _identity_claims_match(item: dict[str, Any], identity: dict[str, Any], position: int) -> bool:
    fields = ("lottery_type", "run_id", "target_draw_id", "strategy_id", "strategy_version")
    if any(key in item and item[key] != identity.get(key) for key in fields):
        return False
    if "identity" not in item:
        return True
    raw_nested: object = item["identity"]
    if type(raw_nested) is not dict:
        return False
    nested = cast(dict[str, Any], raw_nested)
    return all(nested.get(key) == identity.get(key) for key in fields) and nested.get(
        "ticket_position"
    ) == position


def uniform_eight_reference(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    """Use the committed scorer; never turn incomplete evidence into a loss."""
    tickets: object = payload.get("predicted_tickets")
    count: object = payload.get("expected_native_ticket_count")
    result: dict[str, Any] = {
        "status": "UNKNOWN",
        "ticket_count": count if type(count) is int and count > 0 else None,
        "any_prize": None,
    }
    if identity.get("lottery_type") != "BIG_LOTTO" or payload.get("execution_status") != "COMPLETE":
        return result
    for key in (
        "lottery_type",
        "strategy_id",
        "strategy_version",
        "target_draw_id",
        "target_draw_date",
    ):
        if payload.get(key) != identity.get(key):
            return result
    if "cell_identity" in payload and payload["cell_identity"] != identity.get("cell_identity"):
        return result
    if "run_id" in payload and payload["run_id"] != identity.get("run_id"):
        return result
    winning: object = payload.get("winning_numbers")
    hits: object = payload.get("hit_details")
    if (
        type(count) is not int
        or count < 1
        or type(tickets) is not list
        or type(hits) is not list
        or type(winning) is not dict
    ):
        return result
    ticket_values = cast(list[object], tickets)
    hit_values = cast(list[object], hits)
    winning_data = cast(dict[str, Any], winning)
    raw_main: object = winning_data.get("main_numbers")
    raw_special: object = winning_data.get("special_number")
    if (
        len(ticket_values) != count
        or len(hit_values) != count
        or type(raw_main) is not list
        or any(type(n) is not int for n in cast(list[object], raw_main))
        or type(raw_special) is not int
    ):
        return result
    positions: set[int] = set()
    by_position: dict[int, dict[str, Any]] = {}
    for raw_hit in hit_values:
        if type(raw_hit) is not dict:
            return result
        hit = cast(dict[str, Any], raw_hit)
        if type(hit.get("ticket_position")) is not int:
            return result
        position = cast(int, hit["ticket_position"])
        if position in by_position or not _identity_claims_match(hit, identity, position):
            return result
        by_position[position] = hit
    winner = False
    try:
        main = tuple(sorted(cast(list[int], raw_main)))
        for raw_ticket in ticket_values:
            if type(raw_ticket) is not dict:
                return result
            ticket = cast(dict[str, Any], raw_ticket)
            if type(ticket.get("ticket_position")) is not int:
                return result
            position = cast(int, ticket["ticket_position"])
            numbers: object = ticket.get("main_numbers")
            hit = by_position.get(position)
            if (
                position in positions
                or type(numbers) is not list
                or any(type(n) is not int for n in cast(list[object], numbers))
                or hit is None
                or ticket.get("special_number") is not None
                or not _identity_claims_match(ticket, identity, position)
            ):
                return result
            positions.add(position)
            score = score_big_lotto_ticket(
                predicted_main_numbers=tuple(sorted(cast(list[int], numbers))),
                winning_main_numbers=main,
                winning_special_number=raw_special,
            )
            if (
                type(hit.get("zone1_hits")) is not int
                or type(hit.get("zone2_hit")) is not bool
                or hit["zone1_hits"] != score.main_hits
                or hit["zone2_hit"] != score.special_hit
            ):
                return result
            winner = winner or isinstance(
                resolve_big_lotto_prize_tier(score.main_hits, score.special_hit),
                BigLottoPrizeTier,
            )
    except (TypeError, ValueError):
        return result
    if positions != set(range(1, count + 1)) or set(by_position) != positions:
        return result
    return {"status": "SCORABLE", "ticket_count": count, "any_prize": winner}
