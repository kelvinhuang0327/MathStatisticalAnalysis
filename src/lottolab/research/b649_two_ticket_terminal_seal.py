"""Winning-slot-pair validation for B649 two-ticket terminal seals.

Extracted from ``B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1/engine/driver.py``
(SHA-256: 2d15f064e71d01a410d5f76039fc9f9ae965babc97ea9806b46116887edb955f).
Only tuple/list representation is normalized; neither pair orientation nor
sequence order is changed.

Future task-local drivers can replace the winning-pair comparison in
``seal_result`` with::

    try:
        winning_pairs = validate_winning_slot_pairs(
            iteration.get("global_best_winning_slot_pairs"),
            winning_pairs,
            ticket_count=K,
        )
    except ValueError as error:
        raise SystemExit(
            f"CHECKPOINT_RESULT_MISMATCH: iteration {expected_iteration} "
            f"winning pairs: {error}"
        ) from error

The expected sequence must come from the driver's verified pair results, in
their existing order. Checkpoint identity, complete pair-output accounting,
invariants, best-delta validation, tie-breaking and exact recounts remain the
driver's responsibility; successful pair comparison is not a complete seal.
"""

from __future__ import annotations


def canonicalize_winning_slot_pairs(pairs: object, *, ticket_count: int) -> list[list[int]]:
    """Return fresh JSON-safe pairs while rejecting malformed or duplicate entries."""

    if type(ticket_count) is not int or ticket_count < 2:
        raise ValueError("ticket_count must be an integer of at least two")
    if not isinstance(pairs, (list, tuple)) or not pairs:
        raise ValueError("winning slot pairs must be a non-empty list or tuple")

    canonical: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("each winning slot pair must contain exactly two slots")
        i, j = pair
        if type(i) is not int or type(j) is not int:
            raise ValueError("winning slot indices must be integers")
        if not 0 <= i < j < ticket_count:
            raise ValueError("winning slot pairs must satisfy 0 <= i < j < ticket_count")
        if (i, j) in seen:
            raise ValueError("duplicate winning slot pair")
        seen.add((i, j))
        canonical.append([i, j])
    return canonical


def validate_winning_slot_pairs(
    recorded_pairs: object, expected_pairs: object, *, ticket_count: int
) -> list[list[int]]:
    """Require identical ordered winning pairs, accepting tuple/list equivalents.

    Missing, extra or different pairs and ordering changes raise ``ValueError``.
    Both inputs are validated; neither is mutated or silently deduplicated.
    """

    recorded = canonicalize_winning_slot_pairs(recorded_pairs, ticket_count=ticket_count)
    expected = canonicalize_winning_slot_pairs(expected_pairs, ticket_count=ticket_count)
    if recorded != expected:
        raise ValueError("winning slot pairs mismatch")
    return recorded
