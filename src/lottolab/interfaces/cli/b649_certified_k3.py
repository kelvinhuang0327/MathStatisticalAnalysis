"""Explicit CLI for the deterministic, globally certified B649 K3 geometry.

The target ID is only an identity input to the fixed hash ordering rule. It is
not a statistical feature and carries no information about a future draw.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated

import typer

STRATEGY_ID = "B649_CERTIFIED_K3_R1"
GENERATOR_VERSION = "K3_CERTIFIED_R1"
PRODUCER_TASK_ID = "NUMBER2_C_K3_CERTIFIED_TICKET_PRODUCER_R1"
PRODUCER_SOURCE_SHA256 = "05753a903dfbdbdd21722f39256aabbfd7e79051983dd48494f6d44c5aa04327"
CERTIFICATE_ID = "NUMBER2_D_K3_GLOBAL_GEOMETRY_CERTIFICATE_R1"
CERTIFICATE_RESULT_SHA256 = "0c4f7e225975daec4ea3357b49d952f816313097e52064b8e3c120a6b4a17723"

K = 3
NUMBERS_PER_TICKET = 6
MAX_NUMBER = 49
TICKET_COUNT = 3
COST_NTD = 150
EXACT_WIN7 = 7_930_128
TOTAL_7SETS = 85_900_584
EXACT_PROBABILITY_FRACTION = "7930128/85900584"

Ticket = tuple[int, ...]
Tickets = tuple[Ticket, Ticket, Ticket]


class InvalidTargetId(ValueError):
    """Raised when a target ID is not exactly nine ASCII digits."""


def build_certified_k3(target_id: str) -> Tickets:
    """Generate the certified ticket group using the fixed SHA-256 ranking."""
    if re.fullmatch(r"[0-9]{9}", target_id) is None:
        raise InvalidTargetId("target_id must be exactly nine ASCII digits")

    ranked_numbers = sorted(
        range(1, MAX_NUMBER + 1),
        key=lambda number: (
            hashlib.sha256(
                f"{GENERATOR_VERSION}|{target_id}|{number:02d}".encode("ascii")
            ).digest(),
            number,
        ),
    )
    selected = ranked_numbers[: TICKET_COUNT * NUMBERS_PER_TICKET]
    tickets = tuple(
        tuple(sorted(selected[start : start + NUMBERS_PER_TICKET]))
        for start in range(0, TICKET_COUNT * NUMBERS_PER_TICKET, NUMBERS_PER_TICKET)
    )
    return tickets  # type: ignore[return-value]


def build_cli_payload(target_id: str) -> dict[str, object]:
    """Build the stable JSON payload for one explicit target ID."""
    tickets = build_certified_k3(target_id)
    return {
        "TARGET_ID": target_id,
        "STRATEGY_ID": STRATEGY_ID,
        "GENERATOR_VERSION": GENERATOR_VERSION,
        "TICKETS": [list(ticket) for ticket in tickets],
        "K": K,
        "COST_NTD": COST_NTD,
        "EXACT_WIN7": EXACT_WIN7,
        "EXACT_PROBABILITY_FRACTION": EXACT_PROBABILITY_FRACTION,
    }


def b649_certified_k3_command(
    target_id: Annotated[
        str,
        typer.Option(
            "--target-id",
            help="Exact nine-digit target ID; used only as a deterministic identity key.",
        ),
    ],
) -> None:
    """Print three disjoint certified K3 tickets for an explicit B649 target."""
    try:
        payload = build_cli_payload(target_id)
    except InvalidTargetId as exc:
        raise typer.BadParameter(str(exc), param_hint="--target-id") from exc

    typer.echo(json.dumps(payload, ensure_ascii=True, indent=2))
