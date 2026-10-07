"""Exact census of the Owner-defined 108 Pareto-interface support cycles.

Ticket slots retain the champion's artifact order. Normalization sorts numbers
within tickets and then sorts tickets; it is used only for exact-set dedup and
the SHA tie-break. No number relabeling or graph-isomorphism reduction is used.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import Literal, cast

from lottolab.research.b649_official_any_prize_exact import (
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

TASK_ID = "B649_K20_12_8_PARETO_INTERFACE_SIX_TICKET_CYCLE_R1"
OPERATOR_SIGNATURE = "PARETO_INTERFACE_F3_F3_F2_SELECTED_SUPPORT_CYCLE_V1"
SOURCE_HEAD = "f785f8f5b1af1f4987558caf42180e7c8bc4bf03"
BASELINE_COUNT = 313263888
BASELINE_ARTIFACT_SHA = "10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b"
BASELINE_NORMALIZED_SHA = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
NO_GAIN_STATUS = "NO_STRICT_GAIN_FOR_DEFINED_PARETO_INTERFACE_SIX_TICKET_CYCLE_FAMILY"
GAIN_STATUS = "STRICT_GAIN_FOR_DEFINED_PARETO_INTERFACE_SIX_TICKET_CYCLE_FAMILY"
REQUIRED_SUPPORTS: dict[int, tuple[int, ...]] = {
    21: (0, 10),
    22: (1, 2),
    23: (3, 9),
    24: (4, 7),
    25: (5, 8),
    26: (6, 11),
    27: (12, 13, 14),
    28: (15, 16, 17),
}

type Portfolio = tuple[tuple[int, ...], ...]
type Direction = Literal["FORWARD", "REVERSE"]


def normalize(tickets: Sequence[Sequence[int]]) -> Portfolio:
    return tuple(sorted(tuple(sorted(ticket)) for ticket in tickets))


def portfolio_sha(tickets: Sequence[Sequence[int]]) -> str:
    return hashlib.sha256(json.dumps(tickets, separators=(",", ":")).encode()).hexdigest()


def supports(tickets: Portfolio, number: int) -> tuple[int, ...]:
    return tuple(slot for slot, ticket in enumerate(tickets) if number in ticket)


def frequencies(tickets: Portfolio) -> Counter[int]:
    return Counter(number for ticket in tickets for number in ticket)


def require_legal(tickets: Portfolio) -> None:
    if len(tickets) != 20 or len(set(normalize(tickets))) != 20:
        raise ValueError("LEGALITY_DISTINCT_TICKET_MISMATCH")
    for ticket in tickets:
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(type(number) is not int or not 1 <= number <= 49 for number in ticket)
        ):
            raise ValueError("LEGALITY_DISTINCT_TICKET_MISMATCH")


def require_support_identity(tickets: Portfolio) -> None:
    if any(supports(tickets, number) != slots for number, slots in REQUIRED_SUPPORTS.items()):
        raise ValueError("PARETO_INTERFACE_IDENTITY_MISMATCH")


def require_baseline_identity(tickets: Portfolio) -> None:
    require_legal(tickets)
    require_support_identity(tickets)
    if portfolio_sha(tickets) != BASELINE_ARTIFACT_SHA:
        raise ValueError("BASELINE_ARTIFACT_SHA_MISMATCH")
    if portfolio_sha(normalize(tickets)) != BASELINE_NORMALIZED_SHA:
        raise ValueError("BASELINE_NORMALIZED_SHA_MISMATCH")


def parse_tickets(value: object) -> Portfolio:
    if not isinstance(value, list):
        raise ValueError("BASELINE_TICKETS_MALFORMED")
    tickets: list[tuple[int, ...]] = []
    for row in cast(list[object], value):
        if not isinstance(row, list):
            raise ValueError("BASELINE_TICKETS_MALFORMED")
        numbers: list[int] = []
        for number in cast(list[object], row):
            if not isinstance(number, int) or isinstance(number, bool):
                raise ValueError("BASELINE_TICKETS_MALFORMED")
            numbers.append(number)
        tickets.append(tuple(numbers))
    return tuple(tickets)


def load_baseline(authority_path: Path) -> Portfolio:
    authority = cast(dict[str, object], json.loads(authority_path.read_text(encoding="utf-8")))
    if (
        authority.get("TASK_ID") != "B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1"
        or authority.get("TASK_STATUS") != "COMPLETE"
        or authority.get("FINAL_COUNT") != BASELINE_COUNT
        or authority.get("FINAL_ENGINE_NORMALIZED_SHA256") != BASELINE_NORMALIZED_SHA
        or authority.get("START_ARTIFACT_SHA256") != BASELINE_ARTIFACT_SHA
        or authority.get("CANONICAL_RESCORE") != "PASS"
        or authority.get("N1_N2_COMBINED_LOCAL_STATUS")
        != "PROVEN_FOR_VALIDATED_N1_AND_N2_NEIGHBORHOODS"
    ):
        raise ValueError("BASELINE_AUTHORITY_MISMATCH")
    # N2 accepted no move: preserve START_TICKETS' slots, verify its FINAL set.
    tickets = parse_tickets(authority.get("START_TICKETS"))
    require_baseline_identity(tickets)
    if normalize(parse_tickets(authority.get("FINAL_TICKETS"))) != normalize(tickets):
        raise ValueError("BASELINE_FINAL_TICKET_SET_MISMATCH")
    return tickets


@dataclass(frozen=True, slots=True)
class Candidate:
    y: int
    ax: tuple[int, ...]
    az: tuple[int, ...]
    direction: Direction
    tickets: Portfolio

    @property
    def normalized_sha(self) -> str:
        return portfolio_sha(normalize(self.tickets))

    def operator_record(self) -> dict[str, object]:
        return {
            "Y": self.y,
            "AX": list(self.ax),
            "AZ": list(self.az),
            "DIRECTION": self.direction,
            "NORMALIZED_SHA": self.normalized_sha,
        }


def require_candidate(baseline: Portfolio, candidate: Candidate) -> None:
    require_legal(candidate.tickets)
    changed = sum(
        set(old) != set(new) for old, new in zip(baseline, candidate.tickets, strict=True)
    )
    if changed != 6:
        raise ValueError("SIX_TICKET_DIFFERENCE_MISMATCH")
    counts = frequencies(candidate.tickets)
    if counts != frequencies(baseline) or (counts[27], counts[28], counts[candidate.y]) != (
        3,
        3,
        2,
    ):
        raise ValueError("FREQUENCY_PRESERVATION_MISMATCH")
    moved = {27, 28, candidate.y}
    if any(
        set(old) - moved != set(new) - moved
        for old, new in zip(baseline, candidate.tickets, strict=True)
    ):
        raise ValueError("OTHER_NUMBER_SUPPORT_CHANGED")


def enumerate_candidates(baseline: Portfolio) -> tuple[Candidate, ...]:
    require_baseline_identity(baseline)
    raw: list[Candidate] = []
    directions: tuple[Direction, ...] = ("FORWARD", "REVERSE")
    for y in range(21, 27):
        ay = set(supports(baseline, y))
        for ax in itertools.combinations(supports(baseline, 27), 2):
            for az in itertools.combinations(supports(baseline, 28), 2):
                for direction in directions:
                    if direction == "FORWARD":
                        target = {
                            27: (set(supports(baseline, 27)) - set(ax)) | set(az),
                            28: (set(supports(baseline, 28)) - set(az)) | ay,
                            y: set(ax),
                        }
                    else:
                        target = {
                            27: (set(supports(baseline, 27)) - set(ax)) | ay,
                            y: set(az),
                            28: (set(supports(baseline, 28)) - set(az)) | set(ax),
                        }
                    moved = set(target)
                    tickets = tuple(
                        tuple(
                            sorted(
                                (set(ticket) - moved)
                                | {number for number, slots in target.items() if slot in slots}
                            )
                        )
                        for slot, ticket in enumerate(baseline)
                    )
                    candidate = Candidate(y, ax, az, direction, tickets)
                    require_candidate(baseline, candidate)
                    raw.append(candidate)
    if len(raw) != 108:
        raise AssertionError("RAW_OPERATOR_ACCOUNTING_MISMATCH")
    return tuple(raw)


def deduplicate(candidates: Iterable[Candidate]) -> tuple[Candidate, ...]:
    unique: dict[Portfolio, Candidate] = {}
    for candidate in candidates:
        unique.setdefault(normalize(candidate.tickets), candidate)
    return tuple(unique.values())


@dataclass(frozen=True, slots=True)
class Components:
    official: int
    m3_plus: int
    rescue: int

    @classmethod
    def from_exact(cls, exact: ExactPortfolioProbability) -> Components:
        if exact.main_draw_count != comb(49, 6) or exact.special_count != 43:
            raise ValueError("INCOMPLETE_CANONICAL_DRAW_SPACE")
        rescue = exact.official_any_prize_outcome_count - 43 * exact.m3_plus_draw_count
        if not 0 <= exact.m3_plus_draw_count <= exact.main_draw_count or not (
            0 <= rescue <= 43 * (exact.main_draw_count - exact.m3_plus_draw_count)
        ):
            raise ValueError("EXACT_COMPONENT_ARITHMETIC_MISMATCH")
        return cls(exact.official_any_prize_outcome_count, exact.m3_plus_draw_count, rescue)

    def record(self) -> dict[str, object]:
        return {
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": self.official,
            "M3_PLUS_DRAW_COUNT": self.m3_plus,
            "SPECIAL_RESCUE_OUTCOMES": self.rescue,
        }


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: Candidate
    components: Components


def select_best(scored: Sequence[ScoredCandidate]) -> ScoredCandidate:
    return min(scored, key=lambda item: (-item.components.official, item.candidate.normalized_sha))


def write_result(result: dict[str, object], path: Path) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if json.loads(payload) != result:
        raise AssertionError("JSON_ROUND_TRIP_MISMATCH")
    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    if json.loads(path.read_text(encoding="utf-8")) != result:
        raise AssertionError("JSON_ROUND_TRIP_MISMATCH")


def run_research(authority_path: Path, result_path: Path) -> dict[str, object]:
    if result_path.exists():
        raise FileExistsError(result_path)
    authority_sha = hashlib.sha256(authority_path.read_bytes()).hexdigest()
    baseline = load_baseline(authority_path)
    raw = enumerate_candidates(baseline)
    unique = deduplicate(raw)
    # One complete draw space is shared by the baseline, all unique candidates,
    # and the fresh, uncached canonical recount of the selected best candidate.
    draws = all_main_draw_masks(49, 6)
    baseline_score = Components.from_exact(evaluate_portfolio(baseline, draws=draws))
    if baseline_score.official != BASELINE_COUNT:
        raise ValueError("BASELINE_CANONICAL_RESCORE_MISMATCH")
    print(json.dumps({"BASELINE_CANONICAL_RESCORE": "PASS", **baseline_score.record()}), flush=True)
    scored: list[ScoredCandidate] = []
    for index, candidate in enumerate(unique, start=1):
        score = Components.from_exact(evaluate_portfolio(candidate.tickets, draws=draws))
        scored.append(ScoredCandidate(candidate, score))
        print(json.dumps({"SCORED": index, "TOTAL": len(unique), **score.record()}), flush=True)
    best = select_best(scored)
    recount = Components.from_exact(evaluate_portfolio(best.candidate.tickets, draws=draws))
    if recount != best.components:
        raise ValueError("BEST_CANONICAL_RESCORE_MISMATCH")
    if hashlib.sha256(authority_path.read_bytes()).hexdigest() != authority_sha:
        raise ValueError("BASELINE_AUTHORITY_CHANGED_DURING_RESEARCH")
    gained = best.components.official > BASELINE_COUNT
    result: dict[str, object] = {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SOURCE_HEAD": SOURCE_HEAD,
        "START_NORMALIZED_SHA": BASELINE_NORMALIZED_SHA,
        "OPERATOR_SIGNATURE": OPERATOR_SIGNATURE,
        "BASELINE_AUTHORITY_PATH": str(authority_path),
        "BASELINE_AUTHORITY_FILE_SHA256": authority_sha,
        "BASELINE_COUNT": BASELINE_COUNT,
        "BASELINE_ARTIFACT_SHA": portfolio_sha(baseline),
        "BASELINE_NORMALIZED_SHA": portfolio_sha(normalize(baseline)),
        "BASELINE_TICKETS": [list(ticket) for ticket in baseline],
        "BASELINE_CANONICAL_RESCORE": "PASS",
        "RAW_CANDIDATES": len(raw),
        "LEGAL_CANDIDATES": len(raw),
        "UNIQUE_NORMALIZED_CANDIDATES": len(unique),
        "FORWARD_CANDIDATES": sum(candidate.direction == "FORWARD" for candidate in raw),
        "REVERSE_CANDIDATES": sum(candidate.direction == "REVERSE" for candidate in raw),
        "CANDIDATE_SCORES": [
            {**item.candidate.operator_record(), **item.components.record()} for item in scored
        ],
        "BEST_EXACT_COUNT": best.components.official,
        "BEST_DELTA": best.components.official - BASELINE_COUNT,
        "BEST_NORMALIZED_SHA": best.candidate.normalized_sha,
        "BEST_OPERATOR": best.candidate.operator_record(),
        "BEST_TICKETS": [list(ticket) for ticket in best.candidate.tickets],
        "BASELINE_M3_PLUS_DRAW_COUNT": baseline_score.m3_plus,
        "BASELINE_SPECIAL_RESCUE_OUTCOMES": baseline_score.rescue,
        "BEST_M3_PLUS_DRAW_COUNT": best.components.m3_plus,
        "BEST_SPECIAL_RESCUE_OUTCOMES": best.components.rescue,
        "BEST_FRESH_CANONICAL_COMPONENTS": recount.record(),
        "CANONICAL_RESCORE": "PASS",
        "CANONICAL_EVALUATOR": "src/lottolab/research/b649_official_any_prize_exact.py",
        "CANONICAL_EVALUATOR_SHA256": hashlib.sha256(
            (
                Path(__file__).resolve().parents[1]
                / "src/lottolab/research"
                / "b649_official_any_prize_exact.py"
            ).read_bytes()
        ).hexdigest(),
        "COMPLETE_MAIN_DRAW_COUNT": int(draws.size),
        "SPECIAL_COUNT": 43,
        "CANONICAL_EVALUATIONS": len(unique) + 2,
        "STRICT_GAIN": "YES" if gained else "NO",
        "FAMILY_STATUS": GAIN_STATUS if gained else NO_GAIN_STATUS,
        "READY_FOR_N1_ASCENT": "YES" if gained else "NO",
        "JSON_ROUND_TRIP": "PASS",
        "PUSH": "NOT RUN",
        "PR": "NOT CREATED",
        "PRODUCTION_MUTATION": "NONE",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
    }
    write_result(result, result_path)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "BEST_EXACT_COUNT",
                    "BEST_DELTA",
                    "STRICT_GAIN",
                    "FAMILY_STATUS",
                )
            }
        ),
        flush=True,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-authority", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != SOURCE_HEAD:
        raise ValueError("SOURCE_HEAD_MISMATCH")
    run_research(cast(Path, args.baseline_authority), cast(Path, args.result))


if __name__ == "__main__":
    main()
