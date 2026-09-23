"""Run the fixed, bounded K20 2/3-ticket exact-objective pilot.

This is a discrimination smoke run: two pinned starts, two arities, one
frequency-preserving and one off-face proposal per scan. It is not the later
large search and never certifies a local or global optimum.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Final

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    canonical_portfolio_sha256,
)
from lottolab.research.b649_k20_exact_ticket_exchange import (
    ExchangeMove,
    Portfolio,
    apply_exchange,
    bounded_pilot_moves,
    canonical_portfolio,
    frequency_profile,
    scan_exchanges,
)

TASK_ID: Final = "B649_K20_2_3_TICKET_EXACT_OBJECTIVE_EXCHANGE_ENGINE_R1"
AUTHORITY_LOCATOR: Final = (
    "c9e24cf66bb8366e96c93cf6c80022fb20d45e3a:"
    "src/lottolab/research/b649_k20_min_overlap_feasibility_r1.json"
)
HARD_DIV_RECORD: Final = Path(
    "docs/research/matrix-native-results/hard-div-exact-radius2-reconciliation-r1-result.json"
)
HARD_DIV_SHA256: Final = "9a802a103f79948f2345e51f4746860236857f18beece22fe444886cde9d3424"
HARD_DIV_EXACT: Final = Fraction(22345625, 42950292)
OUTPUT_PATH: Final = Path(
    "docs/research/b649-k20-2-3-ticket-exact-objective-exchange-pilot-r1.json"
)
PILOT_SEED: Final = 20260923
MAX_PROPOSALS_PER_SCAN: Final = 2


def _hard_div_portfolio() -> Portfolio:
    payload = json.loads(HARD_DIV_RECORD.read_text(encoding="utf-8"))
    rows = [row for row in payload["k_results"] if row["k"] == 20]
    if len(rows) != 1 or rows[0]["radius2_portfolio_sha256"] != HARD_DIV_SHA256:
        raise ValueError("HARD_DIV K20 authority identity changed")
    portfolio = canonical_portfolio(rows[0]["radius2_portfolio"])
    if canonical_portfolio_sha256(portfolio) != HARD_DIV_SHA256:
        raise ValueError("HARD_DIV K20 ticket bytes changed")
    return portfolio


def _move_payload(move: ExchangeMove) -> dict[str, Any]:
    return {
        "added": list(move.added),
        "mode": move.mode,
        "removed": list(move.removed),
        "slots_zero_based": list(move.slots),
    }


def _profile_payload(portfolio: Portfolio) -> dict[str, int]:
    return {
        str(count): number_count
        for count, number_count in frequency_profile(portfolio).items()
    }


def run_pilot() -> dict[str, Any]:
    """Run exactly eight candidate evaluations plus four baseline evaluations."""

    hard_div = _hard_div_portfolio()
    sealed_entry = SEALED_GEOMETRY_PORTFOLIOS[20]
    sealed = canonical_portfolio(sealed_entry.tickets)
    if canonical_portfolio_sha256(sealed) != sealed_entry.portfolio_sha256:
        raise ValueError("sealed K20 identity changed")
    starts = (
        ("HARD_DIV_MINIMUM_OVERLAP", hard_div, HARD_DIV_EXACT),
        ("SEALED_EXACT_ONE_EXCHANGE_TERMINAL", sealed, sealed_entry.official_any_prize_probability),
    )
    scans: list[dict[str, Any]] = []
    for start_name, start_portfolio, expected_q in starts:
        for arity in (2, 3):
            moves = bounded_pilot_moves(start_portfolio, arity=arity, seed=PILOT_SEED)
            if len(moves) != MAX_PROPOSALS_PER_SCAN:
                raise ValueError("pilot proposal count changed")
            result = scan_exchanges(
                start_portfolio,
                moves,
                max_proposals=MAX_PROPOSALS_PER_SCAN,
            )
            if result.input_score.official_any_prize != expected_q:
                raise ValueError(f"{start_name} exact baseline probability changed")
            candidates: list[dict[str, Any]] = []
            for candidate in result.candidates:
                replay = apply_exchange(result.input_portfolio, candidate.move)
                if replay != candidate.portfolio:
                    raise AssertionError("candidate move did not replay")
                candidates.append(
                    {
                        "move": _move_payload(candidate.move),
                        "portfolio": candidate.portfolio,
                        "portfolio_sha256": canonical_portfolio_sha256(candidate.portfolio),
                        "frequency_profile": _profile_payload(candidate.portfolio),
                        "official_any_prize": str(candidate.score.official_any_prize),
                        "official_any_prize_outcome_count": (
                            candidate.score.official_any_prize_outcome_count
                        ),
                        "m3_plus": str(candidate.score.m3_plus),
                        "delta_vs_start": str(
                            candidate.score.official_any_prize
                            - result.input_score.official_any_prize
                        ),
                    }
                )
            scans.append(
                {
                    "start": start_name,
                    "arity": arity,
                    "proposal_count": len(moves),
                    "exact_candidate_score_count": len(candidates),
                    "input_portfolio": result.input_portfolio,
                    "input_portfolio_sha256": canonical_portfolio_sha256(result.input_portfolio),
                    "input_frequency_profile": _profile_payload(result.input_portfolio),
                    "input_official_any_prize": str(result.input_score.official_any_prize),
                    "input_outcome_count": result.input_score.official_any_prize_outcome_count,
                    "candidates": candidates,
                    "strict_improvement": result.strict_improvement,
                    "selected_portfolio_sha256": canonical_portfolio_sha256(
                        result.selected_portfolio
                    ),
                    "selected_official_any_prize": str(result.selected_score.official_any_prize),
                    "selected_move": (
                        None
                        if result.selected_move is None
                        else _move_payload(result.selected_move)
                    ),
                    "selected_delta": str(result.delta),
                }
            )
    return {
        "task_id": TASK_ID,
        "schema_version": "b649-k20-exact-2-3-ticket-exchange-pilot-r1",
        "upstream_authority_locator": AUTHORITY_LOCATOR,
        "probability_model": "BIG_LOTTO_UNIFORM_FAIR_DRAW",
        "acceptance_objective": "OFFICIAL_ANY_PRIZE",
        "pilot_seed": PILOT_SEED,
        "start_count": len(starts),
        "arity_set": [2, 3],
        "proposal_modes_per_scan": ["NUMBER_CYCLE", "EXTERNAL_SUBSTITUTION"],
        "max_proposals_per_scan": MAX_PROPOSALS_PER_SCAN,
        "scan_count": len(scans),
        "exact_candidate_score_count": sum(scan["exact_candidate_score_count"] for scan in scans),
        "exact_baseline_score_count": len(scans),
        "global_optimum_status": "UNKNOWN",
        "neighborhood_exhausted": False,
        "later_large_search_started": False,
        "scans": scans,
    }


def main() -> None:
    payload = run_pilot()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(OUTPUT_PATH),
                "scan_count": payload["scan_count"],
                "exact_candidate_score_count": payload["exact_candidate_score_count"],
                "strict_improvement_count": sum(
                    scan["strict_improvement"] for scan in payload["scans"]
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
