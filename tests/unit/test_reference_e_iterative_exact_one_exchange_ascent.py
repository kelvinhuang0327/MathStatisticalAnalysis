"""Tests for deterministic iterative exact 1-number-exchange ascent."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
from tools.run_strategy_matrix_phase10_b649_iterative_exact_1exchange_local_ascent import (
    FROZEN_SEED_IDENTITIES,
    LOCKED_PHASE9_RESULT_SHA256,
    canonical_json_bytes,
    load_and_verify_phase9_seed_authority,
    portfolio_sha256,
)

from lottolab.research.reference_e_exact_one_exchange_refinement import Portfolio
from lottolab.research.reference_e_iterative_exact_one_exchange_ascent import (
    enumerate_unique_legal_one_exchange_neighbors,
    evaluate_exact_one_exchange_neighborhood,
    iterative_exact_one_exchange_ascent,
)

PREREGISTRATION_PATH = Path(
    "docs/research/matrix-native-results/"
    "reference-e-iterative-exact-one-exchange-ascent-b649-v1-preregistration.md"
)
RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "reference-e-iterative-exact-one-exchange-ascent-b649-v1-result.json"
)
REPORT_PATH = Path(
    "docs/research/matrix-native-results/"
    "reference-e-iterative-exact-one-exchange-ascent-b649-v1-report.md"
)
PHASE9_RESULT_PATH = Path(
    "docs/research/matrix-native-results/reference-e-exact-one-exchange-b649-v1-result.json"
)

LOCKED_PREREGISTRATION_SHA256 = (
    "593dc33d34190063c5be5817a36bab4bfd3d64a9b98dac2ca1d942d06b567cfd"
)


def brute_force_exact_portfolio_coverage(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    portfolio: Portfolio,
) -> Fraction:
    """Exact winning-space scan independent from the simultaneous evaluator."""
    covered = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_set = set(draw)
        if any(len(draw_set & set(ticket)) >= minimum_matches for ticket in portfolio):
            covered += 1
    return Fraction(covered, math.comb(pool_size, draw_size))


def _portfolio_from_json(payload: Any) -> Portfolio:
    rows = cast(list[list[int]], payload)
    return tuple(tuple(row) for row in rows)


def _fraction_from_json(payload: Any) -> Fraction:
    mapping = cast(dict[str, Any], payload)
    numerator = cast(int, mapping["numerator"])
    denominator = cast(int, mapping["denominator"])
    value = Fraction(numerator, denominator)
    assert mapping["exact"] == f"{value.numerator}/{value.denominator}"
    return value


def test_complete_legal_neighborhood_enumeration() -> None:
    portfolio = ((1, 2, 3), (4, 5, 6))
    neighbors = enumerate_unique_legal_one_exchange_neighbors(portfolio, pool_size=6)

    assert len(neighbors) == 18
    assert len(set(neighbors)) == 18
    assert neighbors == tuple(sorted(neighbors))
    for neighbor in neighbors:
        assert len(neighbor) == 2
        assert len(set(neighbor)) == 2


def test_duplicate_ticket_rejection() -> None:
    portfolio = ((1, 2, 3), (1, 2, 4))
    neighbors = enumerate_unique_legal_one_exchange_neighbors(portfolio, pool_size=6)

    assert len(neighbors) == 16
    assert all(len(set(neighbor)) == 2 for neighbor in neighbors)
    assert portfolio not in neighbors


@pytest.mark.parametrize(
    "portfolio",
    [
        ((1, 2, 3, 4), (4, 5, 6, 7)),
        ((1, 2, 3, 4), (1, 2, 3, 5), (5, 6, 7, 8)),
        ((1, 2, 3, 4), (1, 2, 5, 6), (3, 4, 7, 8)),
    ],
)
def test_simultaneous_exact_fast_evaluator_parity_against_brute_force(
    portfolio: Portfolio,
) -> None:
    result = evaluate_exact_one_exchange_neighborhood(8, 4, 3, portfolio)

    assert result.input_q == brute_force_exact_portfolio_coverage(8, 4, 3, portfolio)
    assert result.unique_legal_neighbor_count == len(result.neighbors)
    for neighbor in result.neighbors:
        assert neighbor.exact_q == brute_force_exact_portfolio_coverage(
            8, 4, 3, neighbor.portfolio
        )


def test_complete_portfolio_lexicographic_tie_break() -> None:
    portfolio = ((1, 2, 3, 4), (4, 5, 6, 7))
    result = evaluate_exact_one_exchange_neighborhood(7, 4, 3, portfolio)
    maximum_q = max(neighbor.exact_q for neighbor in result.neighbors)
    expected = min(
        neighbor.portfolio for neighbor in result.neighbors if neighbor.exact_q == maximum_q
    )

    assert result.best_neighbor_q == maximum_q
    assert result.best_neighbor_portfolio == expected


def test_strict_improvement_acceptance_and_multi_iteration_ascent() -> None:
    seed = ((1, 2, 3, 4), (1, 2, 3, 5))
    ascent = iterative_exact_one_exchange_ascent(8, 4, 3, seed)

    assert ascent.move_count == 2
    assert len(ascent.iterations) == 3
    assert [iteration.delta for iteration in ascent.iterations] == [
        Fraction(2, 35),
        Fraction(2, 35),
        Fraction(0, 1),
    ]
    assert all(iteration.accepted_move for iteration in ascent.iterations[:-1])
    assert all(iteration.delta > 0 for iteration in ascent.iterations[:-1])
    assert not ascent.iterations[-1].accepted_move


def test_equality_plateau_rejection_and_zero_move_terminal() -> None:
    seed = ((1, 2, 3, 4), (4, 5, 6, 7))
    ascent = iterative_exact_one_exchange_ascent(7, 4, 3, seed)

    assert ascent.move_count == 0
    assert len(ascent.iterations) == 1
    assert ascent.iterations[0].delta == 0
    assert not ascent.iterations[0].accepted_move
    assert ascent.terminal_portfolio == seed
    assert ascent.iterations[0].best_neighbor_q == ascent.terminal_q


def test_deterministic_terminal_certificate_and_trace_chain() -> None:
    seed = ((1, 2, 3, 4), (1, 2, 3, 5))
    first = iterative_exact_one_exchange_ascent(8, 4, 3, seed)
    second = iterative_exact_one_exchange_ascent(8, 4, 3, seed)

    assert first == second
    assert tuple(iteration.iteration_index for iteration in first.iterations) == (0, 1, 2)
    for previous, following in itertools.pairwise(first.iterations):
        assert previous.accepted_move
        assert previous.best_neighbor_portfolio == following.input_portfolio
        assert previous.best_neighbor_q == following.input_q
    terminal = first.iterations[-1]
    assert terminal.input_portfolio == first.terminal_portfolio
    assert terminal.input_q == first.terminal_q
    assert terminal.best_neighbor_q <= first.terminal_q


def test_rung_independence() -> None:
    seed_a = ((1, 2, 3, 4), (1, 2, 3, 5))
    seed_b = ((1, 2, 3, 4), (4, 5, 6, 7))

    a_before_b = iterative_exact_one_exchange_ascent(8, 4, 3, seed_a)
    b_after_a = iterative_exact_one_exchange_ascent(8, 4, 3, seed_b)
    b_before_a = iterative_exact_one_exchange_ascent(8, 4, 3, seed_b)
    a_after_b = iterative_exact_one_exchange_ascent(8, 4, 3, seed_a)

    assert a_before_b == a_after_b
    assert b_after_a == b_before_a


def test_canonical_serialization_determinism() -> None:
    first = {"z": [3, 2, 1], "a": {"q": "2/3", "n": 2}}
    second = {"a": {"n": 2, "q": "2/3"}, "z": [3, 2, 1]}

    first_bytes = canonical_json_bytes(first)
    second_bytes = canonical_json_bytes(second)
    assert first_bytes == second_bytes
    assert first_bytes.endswith(b"\n")
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()


def test_frozen_phase9_seed_sha_and_q_identities() -> None:
    assert hashlib.sha256(PHASE9_RESULT_PATH.read_bytes()).hexdigest() == (
        LOCKED_PHASE9_RESULT_SHA256
    )
    authorities = load_and_verify_phase9_seed_authority()

    assert set(authorities) == {10, 15, 20}
    for k, authority in authorities.items():
        expected_sha256, expected_q = FROZEN_SEED_IDENTITIES[k]
        assert authority.portfolio_sha256 == expected_sha256
        assert portfolio_sha256(authority.portfolio) == expected_sha256
        assert authority.q == expected_q


def test_phase10_preregistration_result_and_terminal_certificates() -> None:
    assert PREREGISTRATION_PATH.exists()
    assert hashlib.sha256(PREREGISTRATION_PATH.read_bytes()).hexdigest() == (
        LOCKED_PREREGISTRATION_SHA256
    )
    payload = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))

    assert payload["study_id"] == (
        "STRATEGY_MATRIX_PHASE10_B649_ITERATIVE_EXACT_1EXCHANGE_LOCAL_ASCENT_V1"
    )
    gate = cast(dict[str, Any], payload["gate"])
    assert gate["phase10_execution_gate"] == "PASS"
    assert gate["global_optimum_status"] == "UNKNOWN"
    assert payload["rung_coupling"] == "NONE"

    per_k = cast(dict[str, Any], payload["per_k"])
    for k in (10, 15, 20):
        rung = cast(dict[str, Any], per_k[str(k)])
        iterations = cast(list[dict[str, Any]], rung["iterations"])
        assert rung["move_count"] == len(iterations) - 1
        assert rung["iteration_count"] == len(iterations)
        assert rung["terminal_classification"] == (
            "TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED"
        )
        certificate = cast(dict[str, Any], rung["terminal_certificate"])
        assert certificate["status"] == "PASS"
        assert certificate["accepted_moves_strict_exact_improvements"] is True
        assert certificate["terminal_iteration_accepted_move"] is False
        assert certificate["terminal_best_q_lte_terminal_q"] is True

        for index, iteration in enumerate(iterations):
            assert iteration["iteration_index"] == index
            input_portfolio = _portfolio_from_json(iteration["input_portfolio"])
            best_portfolio = _portfolio_from_json(iteration["best_neighbor_portfolio"])
            assert portfolio_sha256(input_portfolio) == iteration["input_portfolio_sha256"]
            assert portfolio_sha256(best_portfolio) == (
                iteration["best_neighbor_portfolio_sha256"]
            )
            delta = _fraction_from_json(iteration["delta"])
            input_q = _fraction_from_json(iteration["exact_input_q"])
            best_q = _fraction_from_json(iteration["exact_best_neighbor_q"])
            assert delta == best_q - input_q
            if iteration["accepted_move"]:
                assert delta > 0

        terminal = iterations[-1]
        terminal_q = _fraction_from_json(rung["terminal_q"])
        assert terminal["accepted_move"] is False
        assert _fraction_from_json(terminal["exact_best_neighbor_q"]) <= terminal_q
        assert _fraction_from_json(terminal["exact_input_q"]) == terminal_q
        terminal_portfolio = _portfolio_from_json(rung["terminal_portfolio"])
        assert portfolio_sha256(terminal_portfolio) == rung["terminal_portfolio_sha256"]


def test_phase10_report_claim_boundary_and_reproduction_evidence() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    for required in (
        "PHASE10_EXECUTION_GATE: PASS",
        "GLOBAL_OPTIMUM_STATUS: UNKNOWN",
        "FRESH_PROCESS_BYTE_IDENTITY: PASS",
        "HISTORICAL_DRAWS = NOT USED",
        "RNG = NONE",
        "MONTE_CARLO = NONE",
        "DB_ACCESS = NO",
        "SECOND_EXCHANGE = NOT RUN",
        "T539_P638 = NOT RUN",
        "REFERENCE_PROMOTION = NOT AUTHORIZED",
        "RUNTIME_PROMOTION = NOT AUTHORIZED",
        "PUSH = NOT RUN",
        "PR = NOT CREATED",
        LOCKED_PREREGISTRATION_SHA256,
    ):
        assert required in report
