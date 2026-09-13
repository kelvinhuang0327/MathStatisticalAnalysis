"""Focused verification for the k=2/3/5 exact multistart baseline."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
from tools import run_strategy_matrix_k235_multistart_baseline as baseline

RESULT_PATH = Path(
    "docs/research/matrix-native-results/strategy-matrix-k235-multistart-baseline-v1-result.json"
)


def _mapping(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _rows(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    rows = cast(list[object], value)
    assert all(isinstance(item, dict) for item in rows)
    return [cast(dict[str, Any], item) for item in rows]


def _fraction(value: object) -> Fraction:
    mapping = _mapping(value)
    numerator = mapping.get("numerator")
    denominator = mapping.get("denominator")
    assert type(numerator) is int
    assert type(denominator) is int
    result = Fraction(numerator, denominator)
    assert mapping.get("exact") == f"{result.numerator}/{result.denominator}"
    return result


def _portfolio(value: object) -> baseline.Portfolio:
    assert isinstance(value, list)
    tickets: list[tuple[int, ...]] = []
    for raw_ticket in cast(list[object], value):
        assert isinstance(raw_ticket, list)
        numbers = cast(list[object], raw_ticket)
        assert all(type(number) is int for number in numbers)
        tickets.append(tuple(cast(list[int], numbers)))
    return tuple(tickets)


def test_scope_and_locked_semantics() -> None:
    assert baseline.REQUESTED_K_SCOPE == (2, 3, 5)
    assert baseline.SUPPORTED_K_SCOPE == (2, 3, 5)
    assert baseline.START_IDS == (
        "CYCLIC_SIDON_SHIFT_OFFSET0_V1",
        "CYCLIC_SIDON_SHIFT_OFFSET1_V1",
        "CYCLIC_SIDON_SHIFT_OFFSET2_V1",
        "CYCLIC_SIDON_SHIFT_OFFSET3_V1",
    )
    assert baseline.START_OFFSETS == (0, 1, 2, 3)
    assert baseline.PINNED_BASE_COMMIT == (
        "07a5c3479123c03fd91b6f1ae2402046b5f16c2a"
    )
    assert baseline.PINNED_BASE_TREE == "cff549183e67ad49f12afb5076a11b1f8b712dde"
    assert baseline.verify_current_base_identity() == {
        "commit": baseline.PINNED_BASE_COMMIT,
        "tree": baseline.PINNED_BASE_TREE,
    }
    assert baseline.verify_file_identities(baseline.LOCKED_SOURCE_FILE_SHA256) == dict(
        baseline.LOCKED_SOURCE_FILE_SHA256
    )


def test_start_freeze_never_invokes_objective(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_objective(*_arguments: object, **_keywords: object) -> object:
        raise AssertionError("objective evaluator was called during seed freeze")

    monkeypatch.setattr(baseline, "iterative_exact_one_exchange_ascent", forbidden_objective)
    rebuilt = baseline.canonical_json_bytes(baseline.build_start_manifest())
    assert baseline.START_MANIFEST_PATH.exists()
    assert rebuilt == baseline.START_MANIFEST_PATH.read_bytes()


def test_every_frozen_cell_has_four_distinct_legal_starts() -> None:
    manifest = _mapping(json.loads(baseline.START_MANIFEST_PATH.read_bytes()))
    assert manifest["requested_k_scope"] == [2, 3, 5]
    assert manifest["supported_k_scope"] == [2, 3, 5]
    seed_policy = _mapping(manifest["seed_policy"])
    assert seed_policy == {
        "all_predeclared_starts_retained": True,
        "objective_evaluated_during_freeze": False,
        "random_derived_starts": "NONE",
        "start_ids": list(baseline.START_IDS),
        "start_offsets": list(baseline.START_OFFSETS),
    }
    structures = _mapping(manifest["structures"])
    assert set(structures) == {spec.structure_id for spec in baseline.STRUCTURES}
    for spec in baseline.STRUCTURES:
        per_k = _mapping(_mapping(structures[spec.structure_id])["per_k"])
        assert set(per_k) == {"2", "3", "5"}
        for k in baseline.SUPPORTED_K_SCOPE:
            cell = _mapping(per_k[str(k)])
            starts = _rows(cell["STARTS"])
            assert cell["START_COUNT"] == len(starts) == 4
            assert cell["UNIQUE_START_PORTFOLIO_COUNT"] == 4
            assert tuple(start["START_ID"] for start in starts) == baseline.START_IDS
            for start in starts:
                assert start["RANDOM_DERIVED"] is False
                portfolio = _portfolio(start["SEED_PORTFOLIO"])
                baseline.validate_portfolio(
                    portfolio,
                    pool_size=spec.pool_size,
                    draw_size=spec.draw_size,
                    ticket_count=k,
                )
                assert baseline.portfolio_sha256(portfolio) == start["SEED_PORTFOLIO_SHA256"]


def test_result_retains_all_starts_and_terminal_certificates() -> None:
    assert RESULT_PATH.exists(), "the required deterministic result has not been materialized"
    raw = RESULT_PATH.read_bytes()
    payload = _mapping(json.loads(raw))
    assert baseline.canonical_json_bytes(payload) == raw
    assert payload["study_id"] == baseline.STUDY_ID
    assert payload["task_id"] == baseline.TASK_ID
    gate = _mapping(payload["gate"])
    assert gate["MULTISTART_EXECUTION_GATE"] == "PASS"
    assert gate["GLOBAL_OPTIMUM_STATUS"] == "UNKNOWN"
    assert gate["STARTS_FROZEN_BEFORE_SCORING"] is True
    assert gate["ALL_FROZEN_STARTS_RETAINED"] is True
    assert gate["HIDDEN_RESTARTS_DISCARDED"] is False
    assert gate["RANDOM_DERIVED_STARTS"] == "NONE"

    structures = _mapping(payload["structures"])
    observed_start_results = 0
    for spec in baseline.STRUCTURES:
        structure = _mapping(structures[spec.structure_id])
        per_k = _mapping(structure["per_k"])
        assert set(per_k) == {"2", "3", "5"}
        for k in baseline.SUPPORTED_K_SCOPE:
            cell = _mapping(per_k[str(k)])
            starts = _rows(cell["STARTS"])
            observed_start_results += len(starts)
            assert cell["START_COUNT"] == len(starts) == 4
            assert tuple(start["START_ID"] for start in starts) == baseline.START_IDS
            assert cell["LOCAL_OPTIMUM_STATUS"] == (
                "EXACT_ONE_EXCHANGE_LOCAL_OPTIMUM"
            )
            assert cell["GLOBAL_OPTIMUM_STATUS"] == "UNKNOWN"

            terminal_portfolios: set[baseline.Portfolio] = set()
            terminal_q_by_start: dict[str, Fraction] = {}
            for start in starts:
                start_id = cast(str, start["START_ID"])
                iterations = _rows(start["ITERATIONS"])
                move_count = cast(int, start["MOVE_COUNT"])
                assert start["ITERATION_COUNT"] == len(iterations) == move_count + 1
                assert _portfolio(start["SEED_PORTFOLIO"]) == _portfolio(
                    iterations[0]["INPUT_PORTFOLIO"]
                )
                for index, iteration in enumerate(iterations):
                    assert iteration["ITERATION_INDEX"] == index
                    input_q = _fraction(iteration["INPUT_EXACT_Q"])
                    best_q = _fraction(iteration["BEST_NEIGHBOR_EXACT_Q"])
                    assert _fraction(iteration["DELTA"]) == best_q - input_q
                    if index < move_count:
                        assert iteration["ACCEPTED_MOVE"] is True
                        assert best_q > input_q
                        following = iterations[index + 1]
                        assert iteration["BEST_NEIGHBOR_PORTFOLIO"] == following[
                            "INPUT_PORTFOLIO"
                        ]
                        assert best_q == _fraction(following["INPUT_EXACT_Q"])
                    else:
                        assert iteration["ACCEPTED_MOVE"] is False
                        assert best_q <= input_q
                certificate = _mapping(start["TERMINAL_CERTIFICATE"])
                assert certificate["STATUS"] == "PASS"
                terminal_portfolio = _portfolio(start["TERMINAL_PORTFOLIO"])
                terminal_portfolios.add(terminal_portfolio)
                assert terminal_portfolio == _portfolio(iterations[-1]["INPUT_PORTFOLIO"])
                terminal_q = _fraction(start["TERMINAL_EXACT_Q"])
                assert terminal_q == _fraction(iterations[-1]["INPUT_EXACT_Q"])
                terminal_q_by_start[start_id] = terminal_q

            assert cell["UNIQUE_TERMINAL_COUNT"] == len(terminal_portfolios)
            unique_terminals = _rows(cell["UNIQUE_TERMINALS"])
            assert len(unique_terminals) == len(terminal_portfolios)
            assert _fraction(cell["BEST_EXACT_Q"]) == max(terminal_q_by_start.values())
    assert observed_start_results == 36
