"""Assess research portfolio uniqueness without changing native ticket positions."""

from __future__ import annotations

from typing import Any, cast


def assess_research_portfolio(
    tickets: object,
    expected_count: object,
    *,
    source_bound: bool,
    execution_status: object,
) -> dict[str, Any]:
    """Evaluate Big Lotto uniqueness only; this never establishes import eligibility.

    Source binding is a prerequisite, not proof that the underlying archive's hash
    was verified. Other qualification criteria are outside this assessment.
    """

    def unknown(reason: str) -> dict[str, Any]:
        return {
            "status": "UNKNOWN",
            "reason_code": reason,
            "duplicate_groups": [],
            "import_qualification": "UNKNOWN",
        }

    if not source_bound:
        return unknown("SOURCE_OR_STRATEGY_EVIDENCE_INCOMPLETE")
    if execution_status != "COMPLETE":
        return unknown("EXECUTION_NOT_COMPLETE")
    if type(expected_count) is not int or expected_count not in (2, 3, 5):
        return unknown("NATIVE_COUNT_UNKNOWN_OR_UNSUPPORTED")
    if type(tickets) is not list:
        return unknown("TICKET_COUNT_INCOMPLETE_OR_MISMATCH")
    ticket_values = cast(list[object], tickets)
    if len(ticket_values) != expected_count:
        return unknown("TICKET_COUNT_INCOMPLETE_OR_MISMATCH")

    positions: set[int] = set()
    combinations: dict[tuple[int, ...], list[int]] = {}
    for raw_ticket in ticket_values:
        if type(raw_ticket) is not dict:
            return unknown("TICKET_EVIDENCE_INCOMPLETE")
        ticket = cast(dict[str, object], raw_ticket)
        position: object = ticket.get("ticket_position")
        numbers: object = ticket.get("main_numbers")
        special: object = ticket.get("special_number")
        if type(position) is not int or type(numbers) is not list:
            return unknown("TICKET_EVIDENCE_INCOMPLETE")
        if position < 1 or position > expected_count or position in positions:
            return unknown("TICKET_POSITION_INVALID")
        number_values = cast(list[object], numbers)
        if len(number_values) != 6 or any(
            type(n) is not int or not 1 <= n <= 49 for n in number_values
        ):
            return unknown("TICKET_NUMBERS_INVALID")
        main_numbers = cast(list[int], number_values)
        if len(set(main_numbers)) != 6:
            return unknown("TICKET_NUMBERS_INVALID")
        if special is not None and (type(special) is not int or not 1 <= special <= 49):
            return unknown("TICKET_SPECIAL_NUMBER_INVALID")
        positions.add(position)
        combinations.setdefault(tuple(sorted(main_numbers)), []).append(position)
    if positions != set(range(1, expected_count + 1)):
        return unknown("TICKET_POSITION_INCOMPLETE")

    groups = [
        {"main_numbers": list(numbers), "positions": sorted(group)}
        for numbers, group in combinations.items()
        if len(group) > 1
    ]
    groups.sort(key=lambda group: group["positions"][0])
    if groups:
        return {
            "status": "FAIL",
            "reason_code": "DUPLICATE_MAIN_NUMBER_COMBINATION",
            "duplicate_groups": groups,
            "import_qualification": "NOT_QUALIFIED",
        }
    return {
        "status": "PASS",
        "reason_code": None,
        "duplicate_groups": [],
        "import_qualification": "UNKNOWN",
    }
