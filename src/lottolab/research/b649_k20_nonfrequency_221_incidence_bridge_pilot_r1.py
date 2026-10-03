"""Bounded seven-endpoint B649 K20 incidence-bridge pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

TASK_ID = "B649_K20_NONFREQUENCY_221_INCIDENCE_BRIDGE_PILOT_R1"
START_COUNT = 313_239_661
START_SHA256 = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
Z_VALUES = (12, 14, 23, 27, 31, 33, 37)
MODIFIED_SLOTS = (0, 1, 3)
MAX_CANONICAL_EXACT_EVALUATIONS = 9
EXPECTED_FREQUENCY_HISTOGRAM = Counter({2: 27, 3: 22})
WITNESS_SHA256 = "d2003d98e700a30cfafc1b377e85052c9f5d5112dd0865ee8be3a951724eaef5"

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    / "b649-k20-exact-two-ticket-joint-replacement-terminal-r1.json"
)
OUTPUT_RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    / "b649-k20-nonfrequency-221-incidence-bridge-pilot-r1-result.json"
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    """One simultaneous bridge endpoint, retaining slot order for audit."""

    z: int
    slot_ordered_portfolio: Portfolio
    portfolio: Portfolio
    sha256: str


@dataclass(frozen=True, slots=True)
class EndpointScore:
    z: int
    sha256: str
    exact_count: int


@dataclass(frozen=True, slots=True)
class PilotResult:
    source_result_sha256: str
    start_count: int
    start_sha256: str
    candidates: tuple[Candidate, ...]
    endpoint_scores: tuple[EndpointScore, ...]
    canonical_exact_evaluations: int
    pilot_result: str
    best_count: int
    best_delta: int
    best_portfolio_sha256: str
    best_portfolio: Portfolio | None
    first_improving_z: int | None
    fresh_recount: str
    ready_for_next_expansion_review: str
    confirmation_count: int | None

    def to_dict(self) -> dict[str, object]:
        """Return the compact, JSON-ready result artifact."""

        result: dict[str, object] = {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "COMPLETE",
            "SOURCE_RESULT": str(SOURCE_RESULT_PATH.relative_to(REPOSITORY_ROOT)),
            "SOURCE_RESULT_SHA256": self.source_result_sha256,
            "START_COUNT": self.start_count,
            "START_SHA256": self.start_sha256,
            "LEGAL_ENDPOINTS": len(self.candidates),
            "Z_ORDER": list(Z_VALUES),
            "WITNESS_Z": 12,
            "WITNESS_SHA256": WITNESS_SHA256,
            "CANONICAL_EXACT_EVALUATIONS": self.canonical_exact_evaluations,
            "PILOT_RESULT": self.pilot_result,
            "BEST_COUNT": self.best_count,
            "BEST_DELTA": self.best_delta,
            "BEST_PORTFOLIO_SHA256": self.best_portfolio_sha256,
            "FIRST_IMPROVING_Z": self.first_improving_z,
            "FRESH_RECOUNT": self.fresh_recount,
            "READY_FOR_NEXT_EXPANSION_REVIEW": self.ready_for_next_expansion_review,
            "CONFIRMATION_COUNT": self.confirmation_count,
            "ENDPOINT_SCORES": [
                {
                    "Z": score.z,
                    "SHA256": score.sha256,
                    "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": score.exact_count,
                    "DELTA": score.exact_count - self.start_count,
                }
                for score in self.endpoint_scores
            ],
        }
        if self.best_portfolio is not None:
            result["BEST_PORTFOLIO"] = [list(ticket) for ticket in self.best_portfolio]
        return result


def normalize_portfolio(portfolio: Sequence[Sequence[int]]) -> Portfolio:
    """Sort ticket numbers and the complete portfolio into canonical order."""

    return tuple(sorted(tuple(sorted(ticket)) for ticket in portfolio))


def portfolio_sha256(portfolio: Portfolio) -> str:
    """Hash the canonical compact JSON representation of a portfolio."""

    encoded = json.dumps(portfolio, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _validate_portfolio(portfolio: Portfolio) -> None:
    if len(portfolio) != 20 or len(set(portfolio)) != 20:
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: expected 20 distinct tickets")
    for ticket in portfolio:
        if (
            len(ticket) != 6
            or len(set(ticket)) != 6
            or any(
                type(number) is not int or not 1 <= number <= BIG_LOTTO_POOL_SIZE
                for number in ticket
            )
        ):
            raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: illegal ticket")


def _frequencies(portfolio: Portfolio) -> Counter[int]:
    return Counter(number for ticket in portfolio for number in ticket)


def _require_frequency_structure(portfolio: Portfolio, *, z: int | None = None) -> None:
    frequencies = _frequencies(portfolio)
    if Counter(frequencies.values()) != EXPECTED_FREQUENCY_HISTOGRAM:
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: frequency histogram changed")
    if z is not None and (frequencies.get(3) != 2 or frequencies.get(z) != 3):
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: label-frequency transition changed")


def build_candidates(start_portfolio: Sequence[Sequence[int]]) -> tuple[Candidate, ...]:
    """Build and structurally gate the frozen simultaneous seven-endpoint family."""

    start = normalize_portfolio(start_portfolio)
    _validate_portfolio(start)
    _require_frequency_structure(start)
    start_frequencies = _frequencies(start)
    if start_frequencies.get(3) != 3 or any(start_frequencies.get(z) != 2 for z in Z_VALUES):
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: unexpected START label frequencies")

    candidates: list[Candidate] = []
    for z in Z_VALUES:
        # Apply all three edits to the original START slots, as one atomic move.
        slot_ordered = list(start)
        slot_ordered[0] = tuple(sorted((set(start[0]) - {2, 34}) | {22, z}))
        slot_ordered[1] = tuple(sorted((set(start[1]) - {22, 33}) | {2, 34}))
        slot_ordered[3] = tuple(sorted((set(start[3]) - {3}) | {33}))
        slot_ordered_portfolio = tuple(slot_ordered)

        changed_slots = tuple(
            index
            for index, (before, after) in enumerate(
                zip(start, slot_ordered_portfolio, strict=True)
            )
            if before != after
        )
        if changed_slots != MODIFIED_SLOTS:
            raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: wrong changed slots")
        _validate_portfolio(slot_ordered_portfolio)
        _require_frequency_structure(slot_ordered_portfolio, z=z)

        canonical = normalize_portfolio(slot_ordered_portfolio)
        _validate_portfolio(canonical)
        candidates.append(
            Candidate(
                z=z,
                slot_ordered_portfolio=slot_ordered_portfolio,
                portfolio=canonical,
                sha256=portfolio_sha256(canonical),
            )
        )

    if len(candidates) != 7 or len({candidate.sha256 for candidate in candidates}) != 7:
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: expected 7 unique legal endpoints")
    witness = candidates[0]
    if witness.z != 12 or witness.sha256 != WITNESS_SHA256:
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: z=12 witness SHA256 differs")
    if witness.slot_ordered_portfolio[0] != (1, 12, 22, 41, 42, 45):
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: z=12 slot 0 witness differs")
    if witness.slot_ordered_portfolio[1] != (1, 2, 17, 30, 34, 43):
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: z=12 slot 1 witness differs")
    if witness.slot_ordered_portfolio[3] != (4, 10, 15, 26, 27, 33):
        raise ValueError("PILOT_FAMILY_IDENTITY_MISMATCH: z=12 slot 3 witness differs")
    return tuple(candidates)


def canonical_exact_count(portfolio: Portfolio, draws: DrawMasks) -> int:
    """Use only the canonical OFFICIAL_ANY_PRIZE exact outcome count."""

    return evaluate_portfolio(portfolio, draws=draws).official_any_prize_outcome_count


def run_pilot(
    start_portfolio: Sequence[Sequence[int]],
    *,
    recorded_start_sha256: str,
    recorded_start_count: int,
    source_result_sha256: str,
    count_portfolio: Callable[[Portfolio], int],
    start_recount_count: int | None = None,
) -> PilotResult:
    """Validate START, then score candidates in fixed order with strict early stop.

    ``start_recount_count`` resumes an already completed canonical START
    evaluation; otherwise this function performs that evaluation itself.
    """

    start = normalize_portfolio(start_portfolio)
    _validate_portfolio(start)
    start_sha256 = portfolio_sha256(start)
    if (
        start_sha256 != START_SHA256
        or recorded_start_sha256 != START_SHA256
        or recorded_start_count != START_COUNT
    ):
        raise ValueError("START_IDENTITY_MISMATCH")

    start_count = (
        count_portfolio(start) if start_recount_count is None else start_recount_count
    )
    evaluations = 1
    if start_count != START_COUNT:
        raise ValueError("START_IDENTITY_MISMATCH")

    candidates = build_candidates(start)
    scores: list[EndpointScore] = []
    for candidate in candidates:
        if evaluations >= MAX_CANONICAL_EXACT_EVALUATIONS:
            raise RuntimeError("canonical exact evaluation limit exceeded")
        candidate_count = count_portfolio(candidate.portfolio)
        evaluations += 1
        scores.append(EndpointScore(candidate.z, candidate.sha256, candidate_count))
        if candidate_count <= START_COUNT:
            continue

        if evaluations >= MAX_CANONICAL_EXACT_EVALUATIONS:
            raise RuntimeError("confirmation recount would exceed the canonical evaluation limit")
        confirmation_count = count_portfolio(candidate.portfolio)
        evaluations += 1
        if confirmation_count != candidate_count:
            return PilotResult(
                source_result_sha256=source_result_sha256,
                start_count=start_count,
                start_sha256=start_sha256,
                candidates=candidates,
                endpoint_scores=tuple(scores),
                canonical_exact_evaluations=evaluations,
                pilot_result="CONFIRMATION_RECOUNT_MISMATCH",
                best_count=start_count,
                best_delta=0,
                best_portfolio_sha256=start_sha256,
                best_portfolio=None,
                first_improving_z=candidate.z,
                fresh_recount="FAIL",
                ready_for_next_expansion_review="NO",
                confirmation_count=confirmation_count,
            )
        return PilotResult(
            source_result_sha256=source_result_sha256,
            start_count=start_count,
            start_sha256=start_sha256,
            candidates=candidates,
            endpoint_scores=tuple(scores),
            canonical_exact_evaluations=evaluations,
            pilot_result="IMPROVEMENT_FOUND",
            best_count=candidate_count,
            best_delta=candidate_count - start_count,
            best_portfolio_sha256=candidate.sha256,
            best_portfolio=candidate.portfolio,
            first_improving_z=candidate.z,
            fresh_recount="PASS",
            ready_for_next_expansion_review="YES",
            confirmation_count=confirmation_count,
        )

    return PilotResult(
        source_result_sha256=source_result_sha256,
        start_count=start_count,
        start_sha256=start_sha256,
        candidates=candidates,
        endpoint_scores=tuple(scores),
        canonical_exact_evaluations=evaluations,
        pilot_result="NO_IMPROVEMENT",
        best_count=START_COUNT,
        best_delta=0,
        best_portfolio_sha256=START_SHA256,
        best_portfolio=None,
        first_improving_z=None,
        fresh_recount="NOT_REQUIRED",
        ready_for_next_expansion_review="NO",
        confirmation_count=None,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start-recount-count",
        type=int,
        help="continue after an already completed canonical START recount",
    )
    arguments = parser.parse_args()
    source_bytes = SOURCE_RESULT_PATH.read_bytes()
    source_result = json.loads(source_bytes)
    start_portfolio = source_result["TICKETS"]
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    result = run_pilot(
        start_portfolio,
        recorded_start_sha256=source_result["PORTFOLIO_SHA256"],
        recorded_start_count=source_result["FINAL_EXACT_COUNT"],
        source_result_sha256=hashlib.sha256(source_bytes).hexdigest(),
        count_portfolio=lambda portfolio: canonical_exact_count(portfolio, draws),
        start_recount_count=arguments.start_recount_count,
    )
    if OUTPUT_RESULT_PATH.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT_RESULT_PATH}")
    artifact_text = json.dumps(result.to_dict(), sort_keys=True, indent=2) + "\n"
    OUTPUT_RESULT_PATH.write_text(artifact_text, encoding="utf-8")
    print(artifact_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
