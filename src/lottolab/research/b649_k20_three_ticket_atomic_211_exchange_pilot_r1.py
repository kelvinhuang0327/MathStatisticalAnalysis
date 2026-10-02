"""Bounded K20 three-ticket atomic (2,1,1) exchange pilot."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lottolab.application.b649_sealed_geometry_portfolio import canonical_portfolio_sha256
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type ExactEvaluator = Callable[..., ExactPortfolioProbability]

TASK_ID = "B649_K20_THREE_TICKET_ATOMIC_211_EXCHANGE_PILOT_R1"
START_SOURCE_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-exact-two-ticket-joint-replacement-terminal-r1.json"
)
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-three-ticket-atomic-211-exchange-pilot-r1-result.json"
)
START_PORTFOLIO_SHA256 = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
START_EXACT_COUNT = 313_239_661
RAW_COMBINATION_COUNT = 1_080
EXPECTED_CANDIDATE_COUNT = 504
FROZEN_SLOTS = (0, 1, 2)


class StartCanonicalRecountMismatch(ValueError):
    """The canonical evaluator did not reproduce the frozen START count."""


class PilotFamilyIdentityMismatch(ValueError):
    """The frozen exchange family differs from its reviewed cardinality."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One legal endpoint plus its original slot assignment and exchange values."""

    slot_portfolio: Portfolio
    portfolio_sha256: str
    a1: int
    a2: int
    b: int
    c: int

    @property
    def portfolio(self) -> Portfolio:
        """Return the endpoint in canonical complete-portfolio order."""

        return tuple(sorted(self.slot_portfolio))


@dataclass(frozen=True, slots=True)
class CandidateFamily:
    raw_combinations: int
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True, slots=True)
class PilotOutcome:
    start_portfolio: Portfolio
    start_count: int
    raw_combinations: int
    candidates: tuple[Candidate, ...]
    candidates_evaluated: int
    best_count: int
    best_candidate: Candidate | None
    first_improving_candidate_ordinal: int | None

    @property
    def pilot_result(self) -> str:
        return "IMPROVEMENT_FOUND" if self.best_candidate is not None else "NO_IMPROVEMENT"

    @property
    def best_portfolio(self) -> Portfolio:
        if self.best_candidate is None:
            return self.start_portfolio
        return self.best_candidate.portfolio

    @property
    def best_portfolio_sha256(self) -> str:
        if self.best_candidate is None:
            return START_PORTFOLIO_SHA256
        return self.best_candidate.portfolio_sha256

    @property
    def best_delta(self) -> int:
        return self.best_count - self.start_count


def load_start_portfolio(repository: Path) -> Portfolio:
    """Load the exact START from its tracked terminal result artifact."""

    decoded: object = json.loads(
        (repository / START_SOURCE_PATH).read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise ValueError("START artifact must contain a JSON object")
    payload = cast(dict[str, object], decoded)
    raw_tickets = payload.get("TICKETS")
    if not isinstance(raw_tickets, list):
        raise ValueError("START artifact must contain a TICKETS list")
    raw_ticket_items = cast(list[object], raw_tickets)
    if payload.get("PORTFOLIO_SHA256") != START_PORTFOLIO_SHA256:
        raise ValueError("START artifact SHA256 differs from the frozen identity")
    if payload.get("FINAL_EXACT_COUNT") != START_EXACT_COUNT:
        raise ValueError("START artifact count differs from the frozen threshold")

    tickets: list[Ticket] = []
    for raw_ticket in raw_ticket_items:
        if not isinstance(raw_ticket, list):
            raise ValueError("START tickets must be lists of integer numbers")
        raw_numbers = cast(list[object], raw_ticket)
        numbers: list[int] = []
        for number in raw_numbers:
            if type(number) is not int:
                raise ValueError("START tickets must be lists of integer numbers")
            numbers.append(number)
        ticket: Ticket = tuple(numbers)
        if (
            len(ticket) != BIG_LOTTO_DRAW_SIZE
            or len(set(ticket)) != BIG_LOTTO_DRAW_SIZE
            or any(not 1 <= number <= BIG_LOTTO_POOL_SIZE for number in ticket)
        ):
            raise ValueError("START artifact contains an illegal ticket")
        tickets.append(ticket)

    portfolio = tuple(tickets)
    if len(portfolio) != 20 or len(set(portfolio)) != 20:
        raise ValueError("START must contain exactly 20 distinct tickets")
    if portfolio != tuple(sorted(portfolio)):
        raise ValueError("START tickets are not in canonical ticket order")
    if canonical_portfolio_sha256(portfolio) != START_PORTFOLIO_SHA256:
        raise ValueError("START ticket content does not match the frozen SHA256")
    return portfolio


def generate_candidate_family(start: Portfolio) -> CandidateFamily:
    """Generate, validate, deduplicate, and order the frozen slot 0/1/2 family."""

    if len(start) != 20 or start != tuple(sorted(start)):
        raise ValueError("START must be a canonically ordered K20 portfolio")
    ticket_a, ticket_b, ticket_c = (set(start[index]) for index in FROZEN_SLOTS)
    endpoints: dict[Portfolio, Candidate] = {}
    raw_combinations = 0

    for a1 in sorted(ticket_a):
        for a2 in sorted(ticket_a):
            if a1 == a2:
                continue
            for b in sorted(ticket_b):
                for c in sorted(ticket_c):
                    raw_combinations += 1
                    changed_a = tuple(sorted((ticket_a - {a1, a2}) | {b, c}))
                    changed_b = tuple(sorted((ticket_b - {b}) | {a1}))
                    changed_c = tuple(sorted((ticket_c - {c}) | {a2}))

                    changed_tickets = (changed_a, changed_b, changed_c)
                    if any(
                        len(ticket) != BIG_LOTTO_DRAW_SIZE
                        or len(set(ticket)) != BIG_LOTTO_DRAW_SIZE
                        or any(not 1 <= number <= BIG_LOTTO_POOL_SIZE for number in ticket)
                        for ticket in changed_tickets
                    ):
                        continue
                    if len(ticket_a - set(changed_a)) != 2 or len(set(changed_a) - ticket_a) != 2:
                        continue
                    if (
                        len(ticket_b - set(changed_b)) != 1
                        or len(set(changed_b) - ticket_b) != 1
                        or len(ticket_c - set(changed_c)) != 1
                        or len(set(changed_c) - ticket_c) != 1
                    ):
                        continue

                    slot_tickets = list(start)
                    for slot, ticket in zip(FROZEN_SLOTS, changed_tickets, strict=True):
                        slot_tickets[slot] = ticket
                    slot_portfolio = tuple(slot_tickets)
                    changed_slots = tuple(
                        index
                        for index, (before, after) in enumerate(
                            zip(start, slot_portfolio, strict=True)
                        )
                        if before != after
                    )
                    if changed_slots != FROZEN_SLOTS:
                        continue

                    portfolio = tuple(sorted(slot_portfolio))
                    if len(set(portfolio)) != 20:
                        continue
                    digest = canonical_portfolio_sha256(portfolio)
                    endpoints.setdefault(
                        portfolio,
                        Candidate(
                            slot_portfolio=slot_portfolio,
                            portfolio_sha256=digest,
                            a1=a1,
                            a2=a2,
                            b=b,
                            c=c,
                        ),
                    )

    if raw_combinations != RAW_COMBINATION_COUNT:
        raise PilotFamilyIdentityMismatch(
            f"expected {RAW_COMBINATION_COUNT} raw combinations, got {raw_combinations}"
        )
    if len(endpoints) != EXPECTED_CANDIDATE_COUNT:
        raise PilotFamilyIdentityMismatch(
            f"expected {EXPECTED_CANDIDATE_COUNT} legal unique candidates, got {len(endpoints)}"
        )
    candidates = tuple(sorted(endpoints.values(), key=lambda candidate: candidate.portfolio))
    return CandidateFamily(raw_combinations=raw_combinations, candidates=candidates)


def run_pilot(
    repository: Path,
    *,
    draw_masks: DrawMasks | None = None,
    exact_evaluator: ExactEvaluator | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> PilotOutcome:
    """Recount START, then score candidates until first strict gain or exhaustion."""

    start = load_start_portfolio(repository)
    family = generate_candidate_family(start)
    draws = (
        all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
        if draw_masks is None
        else draw_masks
    )
    evaluator = evaluate_portfolio if exact_evaluator is None else exact_evaluator

    start_count = evaluator(start, draws=draws).official_any_prize_outcome_count
    if start_count != START_EXACT_COUNT:
        raise StartCanonicalRecountMismatch(
            f"expected START count {START_EXACT_COUNT}, canonical recount returned {start_count}"
        )

    candidates_evaluated = 0
    best_count = START_EXACT_COUNT
    best_candidate: Candidate | None = None
    first_improving_candidate_ordinal: int | None = None
    for ordinal, candidate in enumerate(family.candidates, start=1):
        candidate_result = evaluator(candidate.portfolio, draws=draws)
        candidate_count = candidate_result.official_any_prize_outcome_count
        candidates_evaluated += 1
        if progress is not None:
            progress(ordinal, candidate_count)
        if candidate_count > START_EXACT_COUNT:
            best_count = candidate_count
            best_candidate = candidate
            first_improving_candidate_ordinal = ordinal
            break

    return PilotOutcome(
        start_portfolio=start,
        start_count=start_count,
        raw_combinations=family.raw_combinations,
        candidates=family.candidates,
        candidates_evaluated=candidates_evaluated,
        best_count=best_count,
        best_candidate=best_candidate,
        first_improving_candidate_ordinal=first_improving_candidate_ordinal,
    )


def result_payload(outcome: PilotOutcome) -> dict[str, object]:
    """Build the compact, packet-shaped result record."""

    candidate = outcome.best_candidate
    return {
        "TASK_ID": TASK_ID,
        "START_SOURCE_ARTIFACT": START_SOURCE_PATH,
        "START_SHA256": START_PORTFOLIO_SHA256,
        "START_CANONICAL_COUNT": outcome.start_count,
        "CANONICAL_RECOUNT_STATUS": "PASS",
        "RAW_COMBINATIONS": outcome.raw_combinations,
        "LEGAL_UNIQUE_CANDIDATES": len(outcome.candidates),
        "CANDIDATES_EVALUATED": outcome.candidates_evaluated,
        "CANONICAL_EXACT_EVALUATIONS": outcome.candidates_evaluated + 1,
        "MAX_CANONICAL_EXACT_EVALUATIONS": EXPECTED_CANDIDATE_COUNT + 1,
        "PILOT_RESULT": outcome.pilot_result,
        "BEST_COUNT": outcome.best_count,
        "BEST_DELTA": outcome.best_delta,
        "READY_FOR_NEXT_EXPANSION_REVIEW": (
            "YES" if outcome.best_candidate is not None else "NO"
        ),
        "BEST_PORTFOLIO_SHA256": outcome.best_portfolio_sha256,
        "BEST_PORTFOLIO": [list(ticket) for ticket in outcome.best_portfolio],
        "CHANGED_SLOTS": list(FROZEN_SLOTS) if candidate is not None else [],
        "FIRST_IMPROVING_CANDIDATE_ORDINAL": (
            outcome.first_improving_candidate_ordinal
            if outcome.first_improving_candidate_ordinal is not None
            else "NONE"
        ),
        "EXCHANGE_PARAMETERS": (
            {"a1": candidate.a1, "a2": candidate.a2, "b": candidate.b, "c": candidate.c}
            if candidate is not None
            else "NONE"
        ),
        "EXACT_EVALUATOR": (
            "lottolab.research.b649_official_any_prize_exact.evaluate_portfolio"
        ),
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
    }


def write_result_artifact(outcome: PilotOutcome, repository: Path) -> Path:
    result_path = repository / RESULT_PATH
    result_path.write_text(
        json.dumps(result_payload(outcome), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result_path


def main() -> None:
    repository = Path(__file__).resolve().parents[3]

    def report_progress(ordinal: int, exact_count: int) -> None:
        print(json.dumps({"candidate_ordinal": ordinal, "exact_count": exact_count}), flush=True)

    outcome = run_pilot(repository, progress=report_progress)
    artifact = write_result_artifact(outcome, repository)
    print(json.dumps(result_payload(outcome), indent=2, sort_keys=True), flush=True)
    print(f"RESULT_ARTIFACT={artifact}", flush=True)


if __name__ == "__main__":
    main()
