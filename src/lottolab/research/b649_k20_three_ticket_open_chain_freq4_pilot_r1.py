"""Frozen 21-endpoint K20 three-ticket open-chain frequency-4 pilot."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    canonical_portfolio_sha256,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]

TASK_ID: Final = "B649_K20_THREE_TICKET_OPEN_CHAIN_FREQ4_PILOT_R1"
START_COUNT: Final = 313239661
START_SHA256: Final = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
Y_VALUES: Final = (4, 6, 7, 8, 9, 10, 11, 13, 15, 16, 18, 19, 20, 24, 26, 28, 29, 36, 39, 46, 49)
CHANGED_SLOTS: Final = (0, 1, 3)
FREQUENCY_HISTOGRAM: Final = {2: 28, 3: 20, 4: 1}
WITNESS_SHA256: Final = "6ef2a2ff6d0782339d835b65d56f451d08569b589fb0b33fa02c7f14d3dd42a4"
EVALUATOR_AUTHORITY: Final = "src/lottolab/research/b649_official_any_prize_exact.py"
REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
RESULT_PATH: Final = (
    REPOSITORY_ROOT
    / (
        "docs/research/matrix-native-results/"
        "b649-k20-three-ticket-open-chain-freq4-pilot-r1-result.json"
    )
)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One validated endpoint, retaining the original START slot order."""

    y: int
    portfolio: Portfolio
    portfolio_sha256: str


def normalize_portfolio(portfolio: Sequence[Sequence[int]]) -> Portfolio:
    """Sort ticket numbers and tickets for canonical portfolio identity."""

    return tuple(sorted(tuple(sorted(ticket)) for ticket in portfolio))


def portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    """Hash the compact canonical JSON list of lists used by the repository."""

    return canonical_portfolio_sha256(normalize_portfolio(portfolio))


def load_start_portfolio() -> Portfolio:
    """Load the pinned K20 START from the canonical sealed portfolio source."""

    return tuple(tuple(ticket) for ticket in SEALED_GEOMETRY_PORTFOLIOS[20].tickets)


def _is_legal_ticket(ticket: Sequence[int]) -> bool:
    return (
        len(ticket) == 6
        and len(set(ticket)) == 6
        and all(type(number) is int and 1 <= number <= 49 for number in ticket)
    )


def _replace_number(ticket: Ticket, removed: int, added: int) -> Ticket:
    if removed not in ticket or added in ticket:
        raise ValueError(f"invalid frozen replacement {removed}->{added} in {ticket}")
    return tuple(sorted((set(ticket) - {removed}) | {added}))


def _validate_endpoint(start: Portfolio, candidate: Portfolio, y: int) -> None:
    if len(candidate) != 20 or any(not _is_legal_ticket(ticket) for ticket in candidate):
        raise ValueError(f"FAMILY_IDENTITY_MISMATCH: illegal K20 endpoint for y={y}")
    if len(set(candidate)) != 20:
        raise ValueError(f"FAMILY_IDENTITY_MISMATCH: duplicate ticket for y={y}")

    changed_slots = tuple(
        index
        for index, pair in enumerate(zip(start, candidate, strict=True))
        if pair[0] != pair[1]
    )
    if changed_slots != CHANGED_SLOTS:
        raise ValueError(f"FAMILY_IDENTITY_MISMATCH: changed slots {changed_slots} for y={y}")

    for left in range(20):
        for right in range(left + 1, 20):
            if len(set(candidate[left]) & set(candidate[right])) > 1:
                raise ValueError(f"FAMILY_IDENTITY_MISMATCH: pair overlap for y={y}")

    frequencies = Counter(number for ticket in candidate for number in ticket)
    histogram = Counter(frequencies.values())
    if histogram != Counter(FREQUENCY_HISTOGRAM):
        raise ValueError(
            f"FAMILY_IDENTITY_MISMATCH: frequency histogram {dict(histogram)} for y={y}"
        )
    fourfold = tuple(sorted(number for number, frequency in frequencies.items() if frequency == 4))
    if fourfold != (y,):
        raise ValueError(f"FAMILY_IDENTITY_MISMATCH: frequency-4 number {fourfold} for y={y}")


def build_candidate_family(start: Sequence[Sequence[int]]) -> tuple[Candidate, ...]:
    """Build all endpoints atomically from the unchanged START slot ordering."""

    original: Portfolio = tuple(tuple(ticket) for ticket in start)
    if len(original) != 20 or any(not _is_legal_ticket(ticket) for ticket in original):
        raise ValueError("FAMILY_IDENTITY_MISMATCH: START is not a legal K20 portfolio")

    candidates: list[Candidate] = []
    for y in Y_VALUES:
        updated = list(original)
        updated[3] = _replace_number(original[3], 3, 2)
        updated[0] = _replace_number(original[0], 2, 33)
        updated[1] = _replace_number(original[1], 33, y)
        portfolio = tuple(updated)
        _validate_endpoint(original, portfolio, y)
        candidates.append(Candidate(y, portfolio, portfolio_sha256(portfolio)))

    if len(candidates) != 21 or len({candidate.portfolio_sha256 for candidate in candidates}) != 21:
        raise ValueError("FAMILY_IDENTITY_MISMATCH: endpoints are not 21 legal unique portfolios")

    witness = next(candidate for candidate in candidates if candidate.y == 4)
    expected_tickets = {
        0: (1, 33, 34, 41, 42, 45),
        1: (1, 4, 17, 22, 30, 43),
        3: (2, 4, 10, 15, 26, 27),
    }
    if any(witness.portfolio[slot] != ticket for slot, ticket in expected_tickets.items()):
        raise ValueError("FAMILY_IDENTITY_MISMATCH: y=4 changed-ticket witness differs")
    if witness.portfolio_sha256 != WITNESS_SHA256:
        raise ValueError("FAMILY_IDENTITY_MISMATCH: y=4 portfolio SHA256 differs")
    return tuple(candidates)


def canonical_official_any_prize_count(portfolio: Sequence[Sequence[int]]) -> int:
    """Score only through the named canonical exact evaluator."""

    return evaluate_portfolio(portfolio).official_any_prize_outcome_count


def execute_pilot(
    start: Sequence[Sequence[int]],
    scorer: Callable[[Portfolio], int],
    on_evaluation: Callable[[dict[str, int | str]], None] | None = None,
) -> dict[str, object]:
    """Run the frozen sequence, stopping at the first freshly confirmed gain."""

    original: Portfolio = tuple(tuple(ticket) for ticket in start)
    start_sha256 = portfolio_sha256(original)
    if start_sha256 != START_SHA256:
        raise RuntimeError(f"START_IDENTITY_MISMATCH: SHA256 {start_sha256}")

    start_count = scorer(original)
    if start_count != START_COUNT:
        raise RuntimeError(f"START_IDENTITY_MISMATCH: exact count {start_count}")

    candidates = build_candidate_family(original)
    evaluation_log: list[dict[str, int | str]] = [
        {"KIND": "START", "COUNT": start_count, "PORTFOLIO_SHA256": start_sha256}
    ]
    if on_evaluation is not None:
        on_evaluation(evaluation_log[-1])
    exact_evaluations = 1
    first_improving_y: int | None = None
    fresh_recount = "NOT_REQUIRED"
    best_count = START_COUNT
    best_portfolio = original
    best_sha256 = start_sha256

    for candidate in candidates:
        count = scorer(candidate.portfolio)
        exact_evaluations += 1
        evaluation_log.append(
            {
                "KIND": "CANDIDATE",
                "Y": candidate.y,
                "COUNT": count,
                "PORTFOLIO_SHA256": candidate.portfolio_sha256,
            }
        )
        if on_evaluation is not None:
            on_evaluation(evaluation_log[-1])
        if count <= START_COUNT:
            continue

        confirmation = scorer(candidate.portfolio)
        exact_evaluations += 1
        evaluation_log.append(
            {
                "KIND": "FRESH_RECOUNT",
                "Y": candidate.y,
                "COUNT": confirmation,
                "PORTFOLIO_SHA256": candidate.portfolio_sha256,
            }
        )
        if on_evaluation is not None:
            on_evaluation(evaluation_log[-1])
        if confirmation != count:
            raise RuntimeError(
                f"FRESH_RECOUNT_MISMATCH: y={candidate.y}, first={count}, "
                f"confirmation={confirmation}"
            )
        first_improving_y = candidate.y
        fresh_recount = "PASS"
        best_count = confirmation
        best_portfolio = candidate.portfolio
        best_sha256 = candidate.portfolio_sha256
        break

    improved = first_improving_y is not None
    return {
        "SCHEMA_VERSION": "B649_K20_THREE_TICKET_OPEN_CHAIN_FREQ4_PILOT_V1",
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "START_COUNT": START_COUNT,
        "START_SHA256": start_sha256,
        "RAW_CANDIDATES": len(candidates),
        "LEGAL_ENDPOINTS": len(candidates),
        "LEGAL_UNIQUE_ENDPOINTS": len({candidate.portfolio_sha256 for candidate in candidates}),
        "CANDIDATE_Y_ORDER": list(Y_VALUES),
        "CANONICAL_EXACT_EVALUATIONS": exact_evaluations,
        "EVALUATOR_AUTHORITY": EVALUATOR_AUTHORITY,
        "PILOT_RESULT": "IMPROVEMENT_FOUND" if improved else "NO_IMPROVEMENT",
        "BEST_COUNT": best_count,
        "BEST_DELTA": best_count - START_COUNT,
        "BEST_PORTFOLIO_SHA256": best_sha256,
        "FIRST_IMPROVING_Y": first_improving_y,
        "FRESH_RECOUNT": fresh_recount,
        "READY_FOR_NEXT_EXPANSION_REVIEW": "YES" if improved else "NO",
        "BEST_PORTFOLIO": [list(ticket) for ticket in normalize_portfolio(best_portfolio)],
        "EVALUATIONS": evaluation_log,
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "PUSH": "NOT RUN",
        "PR": "NOT CREATED",
        "PRODUCTION_MUTATION": "NONE",
    }


def serialize_result(result: dict[str, object]) -> str:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"


def write_result(result: dict[str, object], path: Path = RESULT_PATH) -> None:
    path.write_text(serialize_result(result), encoding="utf-8")


def main() -> int:
    def report_evaluation(row: dict[str, int | str]) -> None:
        print(
            json.dumps({"CANONICAL_EXACT_EVALUATION": row}, separators=(",", ":")),
            flush=True,
        )

    result = execute_pilot(
        load_start_portfolio(), canonical_official_any_prize_count, report_evaluation
    )
    write_result(result)
    print(serialize_result(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
