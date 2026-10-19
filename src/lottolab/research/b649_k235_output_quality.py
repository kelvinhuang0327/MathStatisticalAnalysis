"""Quality verification and fair-draw coverage evaluation for B649 K2/K3/K5 predictions.

This module enforces strict output quality checks:
1. Exact native ticket count K for each portfolio.
2. Exact ticket shape: each ticket must contain exactly 6 distinct integers in 1..49.
   Non-integers (bool, float, str) and out-of-range numbers are rejected.
3. Strict disjointness: exactly 6*K distinct numbers across all K tickets
   (zero cross-ticket overlap).
4. Fair-draw exact official any-prize coverage probability:
   K2 = 5302152 / 85900584
   K3 = 7930128 / 85900584
   K5 = 13139880 / 85900584
   Rejected portfolios never receive these values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

QUALITY_COMPONENT_VERSION = "1.0.0"

FAIR_DRAW_EXACT_COVERAGE_FRACTIONS: Mapping[int, tuple[int, int]] = {
    2: (5302152, 85900584),
    3: (7930128, 85900584),
    5: (13139880, 85900584),
}


@dataclass(frozen=True, slots=True)
class QualityEvaluation:
    """Outcome of quality evaluation for one candidate portfolio."""

    is_valid: bool
    rejection_reasons: tuple[str, ...]
    ticket_count: int
    expected_ticket_count: int
    unique_number_count: int
    expected_unique_count: int
    exact_fraction: str | None
    exact_numerator: int | None
    exact_denominator: int | None
    coverage_probability: float | None

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "rejection_reasons": list(self.rejection_reasons),
            "ticket_count": self.ticket_count,
            "expected_ticket_count": self.expected_ticket_count,
            "unique_number_count": self.unique_number_count,
            "expected_unique_count": self.expected_unique_count,
            "exact_fraction": self.exact_fraction,
            "exact_numerator": self.exact_numerator,
            "exact_denominator": self.exact_denominator,
            "coverage_probability": self.coverage_probability,
        }


def _extract_raw_ticket_numbers(ticket: Any) -> Sequence[Any] | None:
    if isinstance(ticket, Mapping):
        mapping = cast(Mapping[str, Any], ticket)
        if "emitted_main_numbers" in mapping:
            return cast(Sequence[Any], mapping["emitted_main_numbers"])
        if "legal_main_numbers" in mapping:
            return cast(Sequence[Any], mapping["legal_main_numbers"])
        if "numbers" in mapping:
            return cast(Sequence[Any], mapping["numbers"])
    if isinstance(ticket, (list, tuple)):
        return cast(Sequence[Any], ticket)
    return None


def evaluate_candidate_quality(
    tickets: Sequence[Any] | None,
    expected_k: int,
) -> QualityEvaluation:
    """Validate a candidate's tickets against the K2/K3/K5 disjoint quality contract."""

    expected_unique = 6 * expected_k
    reasons: list[str] = []

    if tickets is None:
        return QualityEvaluation(
            is_valid=False,
            rejection_reasons=("MISSING_TICKETS: tickets payload is None",),
            ticket_count=0,
            expected_ticket_count=expected_k,
            unique_number_count=0,
            expected_unique_count=expected_unique,
            exact_fraction=None,
            exact_numerator=None,
            exact_denominator=None,
            coverage_probability=None,
        )

    if not isinstance(tickets, (list, tuple)):
        return QualityEvaluation(
            is_valid=False,
            rejection_reasons=(
                f"INVALID_TICKETS_CONTAINER: expected sequence, got {type(tickets).__name__}",
            ),
            ticket_count=0,
            expected_ticket_count=expected_k,
            unique_number_count=0,
            expected_unique_count=expected_unique,
            exact_fraction=None,
            exact_numerator=None,
            exact_denominator=None,
            coverage_probability=None,
        )

    actual_ticket_count = len(tickets)
    if actual_ticket_count != expected_k:
        reasons.append(
            f"TICKET_COUNT_MISMATCH: expected {expected_k} tickets, got {actual_ticket_count}"
        )

    parsed_tickets: list[list[int]] = []
    all_numbers: list[int] = []

    for index, raw_ticket in enumerate(tickets, start=1):
        numbers = _extract_raw_ticket_numbers(raw_ticket)
        if numbers is None:
            reasons.append(
                f"TICKET_{index}_NOT_A_SEQUENCE: ticket is of type {type(raw_ticket).__name__}"
            )
            continue

        if not isinstance(numbers, (list, tuple)):
            reasons.append(
                f"TICKET_{index}_NOT_A_SEQUENCE: numbers is of type {type(numbers).__name__}"
            )
            continue

        if len(numbers) != 6:
            reasons.append(
                f"TICKET_{index}_LENGTH_INVALID: expected 6 numbers, got {len(numbers)}"
            )

        ticket_ints: list[int] = []
        has_type_or_range_error = False

        for n in numbers:
            # Note: bool is a subclass of int in Python; reject bool explicitly
            if type(n) is not int or isinstance(n, bool):
                reasons.append(
                    f"TICKET_{index}_INVALID_NUMBER_TYPE: "
                    f"value {n!r} has type {type(n).__name__}, expected int"
                )
                has_type_or_range_error = True
            elif not 1 <= n <= 49:
                reasons.append(
                    f"TICKET_{index}_NUMBER_OUT_OF_RANGE: number {n} outside 1..49"
                )
                has_type_or_range_error = True
            else:
                ticket_ints.append(n)

        if not has_type_or_range_error and len(ticket_ints) == 6:
            if len(set(ticket_ints)) != 6:
                reasons.append(
                    f"TICKET_{index}_DUPLICATE_NUMBERS: "
                    f"ticket has internal duplicates: {ticket_ints}"
                )
            parsed_tickets.append(ticket_ints)
            all_numbers.extend(ticket_ints)

    unique_count = len(set(all_numbers))

    # Cross-ticket overlap check
    if (
        actual_ticket_count == expected_k
        and len(parsed_tickets) == expected_k
        and unique_count != expected_unique
    ):
        reasons.append(
            f"CROSS_TICKET_OVERLAP: expected {expected_unique} unique numbers "
            f"across {expected_k} tickets, got {unique_count}"
        )

    is_valid = len(reasons) == 0

    if is_valid and expected_k in FAIR_DRAW_EXACT_COVERAGE_FRACTIONS:
        num, den = FAIR_DRAW_EXACT_COVERAGE_FRACTIONS[expected_k]
        exact_fraction = f"{num}/{den}"
        exact_numerator = num
        exact_denominator = den
        coverage_probability = num / den
    else:
        exact_fraction = None
        exact_numerator = None
        exact_denominator = None
        coverage_probability = None

    return QualityEvaluation(
        is_valid=is_valid,
        rejection_reasons=tuple(reasons),
        ticket_count=actual_ticket_count,
        expected_ticket_count=expected_k,
        unique_number_count=unique_count,
        expected_unique_count=expected_unique,
        exact_fraction=exact_fraction,
        exact_numerator=exact_numerator,
        exact_denominator=exact_denominator,
        coverage_probability=coverage_probability,
    )


def partition_k_entries(
    entries: Sequence[Mapping[str, Any]],
    expected_k: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate each strategy entry and separate into accepted and rejected lists."""

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for entry in entries:
        tickets = entry.get("tickets", [])
        quality = evaluate_candidate_quality(tickets, expected_k)
        annotated_entry = dict(entry)
        annotated_entry["quality_evaluation"] = quality.canonical_dict()

        if quality.is_valid:
            annotated_entry["quality_status"] = "ACCEPTED"
            annotated_entry["rejection_reasons"] = []
            annotated_entry["exact_coverage_fraction"] = quality.exact_fraction
            annotated_entry["coverage_probability"] = quality.coverage_probability
            accepted.append(annotated_entry)
        else:
            annotated_entry["quality_status"] = "REJECTED"
            annotated_entry["rejection_reasons"] = list(quality.rejection_reasons)
            annotated_entry["exact_coverage_fraction"] = None
            annotated_entry["coverage_probability"] = None
            rejected.append(annotated_entry)

    return accepted, rejected


__all__ = [
    "FAIR_DRAW_EXACT_COVERAGE_FRACTIONS",
    "QUALITY_COMPONENT_VERSION",
    "QualityEvaluation",
    "evaluate_candidate_quality",
    "partition_k_entries",
]
