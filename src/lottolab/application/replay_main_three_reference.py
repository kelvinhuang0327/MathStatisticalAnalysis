"""Fail-closed view and exact random baseline for saved K3 main-hit research."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from functools import lru_cache
from math import comb
from typing import Any, TypeGuard, cast

MAIN_THREE_EVENT = "MAIN_HITS_GE_3_ANY_OF_THREE"


def _claim_matches(item: dict[str, Any], identity: dict[str, Any], position: int) -> bool:
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


def _legal_main_numbers(value: object) -> TypeGuard[list[int]]:
    if type(value) is not list:
        return False
    values = cast(list[object], value)
    if len(values) != 6 or not all(type(n) is int and 1 <= n <= 49 for n in values):
        return False
    return len(set(cast(list[int], values))) == 6


def main_three_reference(
    payload: dict[str, Any], identity: dict[str, Any]
) -> dict[str, Any] | None:
    """Expose only explicitly declared saved research outcomes, with independent checks."""
    if payload.get("research_success_event") != MAIN_THREE_EVENT:
        return None
    scorer = payload.get("research_scorer_version")
    result: dict[str, Any] = {
        "metric_id": MAIN_THREE_EVENT,
        "status": "UNKNOWN",
        "success": None,
        "scorer_version": scorer if type(scorer) is str and scorer.strip() else None,
    }
    if result["scorer_version"] is None:
        return result
    if not isinstance(identity.get("run_id"), str):
        return result
    for key in ("dataset_identity", "execution_version", "result_identity"):
        if not isinstance(identity.get(key), str) or payload.get(key) != identity[key]:
            return result
    body = {key: value for key, value in payload.items() if key != "result_identity"}
    try:
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    except (TypeError, ValueError):
        return result
    if digest != identity["result_identity"]:
        return result
    fields = (
        "lottery_type",
        "strategy_id",
        "strategy_version",
        "target_draw_id",
        "target_draw_date",
        "cell_identity",
    )
    if (
        identity.get("lottery_type") != "BIG_LOTTO"
        or payload.get("execution_status") != "COMPLETE"
        or type(payload.get("expected_native_ticket_count")) is not int
        or payload["expected_native_ticket_count"] != 3
        or any(payload.get(key) != identity.get(key) for key in fields)
        or ("run_id" in payload and payload["run_id"] != identity["run_id"])
    ):
        return result
    winning: object = payload.get("winning_numbers")
    tickets: object = payload.get("predicted_tickets")
    hits: object = payload.get("hit_details")
    if (
        type(winning) is not dict
        or type(tickets) is not list
        or type(hits) is not list
    ):
        return result
    win_data = cast(dict[str, Any], winning)
    main: object = win_data.get("main_numbers")
    ticket_values = cast(list[object], tickets)
    hit_values = cast(list[object], hits)
    if not _legal_main_numbers(main) or len(ticket_values) != 3 or len(hit_values) != 3:
        return result
    winning_numbers = set(main)
    by_position: dict[int, dict[str, Any]] = {}
    for raw_hit in hit_values:
        if type(raw_hit) is not dict:
            return result
        hit = cast(dict[str, Any], raw_hit)
        position: object = hit.get("ticket_position")
        if type(position) is not int:
            return result
        if position in by_position or not _claim_matches(hit, identity, position):
            return result
        by_position[position] = hit
    positions: set[int] = set()
    expected = False
    for raw_ticket in ticket_values:
        if type(raw_ticket) is not dict:
            return result
        ticket = cast(dict[str, Any], raw_ticket)
        position = ticket.get("ticket_position")
        if type(position) is not int:
            return result
        numbers: object = ticket.get("main_numbers")
        hit = by_position.get(position)
        if (
            position in positions
            or not _claim_matches(ticket, identity, position)
            or not _legal_main_numbers(numbers)
            or ticket.get("special_number") is not None
            or hit is None
            or type(hit.get("zone1_hits")) is not int
            or hit["zone1_hits"] != len(set(numbers) & winning_numbers)
        ):
            return result
        positions.add(position)
        expected = expected or hit["zone1_hits"] >= 3
    if positions != {1, 2, 3} or set(by_position) != positions:
        return result
    saved = payload.get("research_success")
    if type(saved) is not bool or saved is not expected:
        return result
    return {**result, "status": "SCORABLE", "success": expected}


@lru_cache(maxsize=8192)
def _baseline_by_regions(regions: tuple[int, ...]) -> Fraction:
    """Exact union probability over C(49, 6), counting ticket overlap once."""
    numerator = 0

    def visit(mask: int, remaining: int, hits: tuple[int, int, int], weight: int) -> None:
        nonlocal numerator
        if mask == 8:
            if remaining == 0 and max(hits) >= 3:
                numerator += weight
            return
        for count in range(min(remaining, regions[mask]) + 1):
            next_hits = cast(
                tuple[int, int, int],
                tuple(hits[i] + (count if mask & (1 << i) else 0) for i in range(3)),
            )
            visit(mask + 1, remaining - count, next_hits, weight * comb(regions[mask], count))

    visit(0, 6, (0, 0, 0), 1)
    return Fraction(numerator, comb(49, 6))


def main_three_baseline(payload: dict[str, Any]) -> Fraction:
    """Called only after main_three_reference validated the three saved tickets."""
    tickets = [set(ticket["main_numbers"]) for ticket in payload["predicted_tickets"]]
    if len(tickets) != 3 or any(len(ticket) != 6 for ticket in tickets):
        raise ValueError("invalid K3 ticket geometry")
    regions = [0] * 8
    for number in range(1, 50):
        regions[sum(1 << i for i, ticket in enumerate(tickets) if number in ticket)] += 1
    return _baseline_by_regions(tuple(regions))
