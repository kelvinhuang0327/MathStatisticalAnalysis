"""Focused integrity checks for the Phase 11 native replication artifacts."""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
from fractions import Fraction
from typing import Any, cast

import pytest
from tools import (
    run_strategy_matrix_phase11_t539_p638_zone1_iterative_exact_1exchange_replication as phase11,
)


def _fraction(payload: Any) -> Fraction:
    mapping = cast(dict[str, Any], payload)
    value = Fraction(cast(int, mapping["numerator"]), cast(int, mapping["denominator"]))
    assert mapping["exact"] == f"{value.numerator}/{value.denominator}"
    return value


def _portfolio(payload: Any) -> tuple[tuple[int, ...], ...]:
    rows = cast(list[list[int]], payload)
    return tuple(tuple(row) for row in rows)


EXPECTED_BASE_COMMIT = "1de7bf0d51160802115aa7ade416e5e717a00461"
EXPECTED_BASE_TREE = "895696e5c2ab87b7ebe1c294a2a32edcdefefe43"


def _install_mock_git_responses(
    monkeypatch: pytest.MonkeyPatch,
    *,
    commit: str = EXPECTED_BASE_COMMIT,
    tree: str = EXPECTED_BASE_TREE,
    ancestry_returncode: int = 0,
) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []
    commit_command = (
        "git",
        "rev-parse",
        f"{EXPECTED_BASE_COMMIT}^{{commit}}",
    )
    tree_command = (
        "git",
        "rev-parse",
        f"{EXPECTED_BASE_COMMIT}^{{tree}}",
    )
    ancestry_command = (
        "git",
        "merge-base",
        "--is-ancestor",
        EXPECTED_BASE_COMMIT,
        "HEAD",
    )

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        call = tuple(command)
        calls.append(call)
        assert capture_output is True
        assert text is True
        if call == commit_command:
            assert check is True
            return subprocess.CompletedProcess(
                command, 0, stdout=f"{commit}\n", stderr=""
            )
        if call == tree_command:
            assert check is True
            return subprocess.CompletedProcess(command, 0, stdout=f"{tree}\n", stderr="")
        if call == ancestry_command:
            assert check is False
            return subprocess.CompletedProcess(
                command, ancestry_returncode, stdout="", stderr=""
            )
        raise AssertionError(f"unexpected Git command: {command}")

    monkeypatch.setattr(phase11.subprocess, "run", fake_run)
    return calls


def test_preregistration_and_base_identity_are_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert phase11.verify_preregistration_lock() == phase11.LOCKED_PREREGISTRATION_SHA256
    assert hashlib.sha256(phase11.PREREGISTRATION_PATH.read_bytes()).hexdigest() == (
        phase11.LOCKED_PREREGISTRATION_SHA256
    )
    calls = _install_mock_git_responses(monkeypatch)
    assert phase11.verify_current_base_identity() == {
        "commit": "1de7bf0d51160802115aa7ade416e5e717a00461",
        "tree": "895696e5c2ab87b7ebe1c294a2a32edcdefefe43",
    }
    assert calls == [
        ("git", "rev-parse", f"{EXPECTED_BASE_COMMIT}^{{commit}}"),
        ("git", "rev-parse", f"{EXPECTED_BASE_COMMIT}^{{tree}}"),
        (
            "git",
            "merge-base",
            "--is-ancestor",
            EXPECTED_BASE_COMMIT,
            "HEAD",
        ),
    ]


@pytest.mark.parametrize(
    ("commit", "tree"),
    [
        ("0" * 40, EXPECTED_BASE_TREE),
        (EXPECTED_BASE_COMMIT, "0" * 40),
    ],
)
def test_base_identity_rejects_commit_or_tree_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    commit: str,
    tree: str,
) -> None:
    _install_mock_git_responses(monkeypatch, commit=commit, tree=tree)

    with pytest.raises(ValueError, match="CANONICAL_BASE_IDENTITY_MISMATCH"):
        phase11.verify_current_base_identity()


def test_base_identity_rejects_ancestry_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_mock_git_responses(monkeypatch, ancestry_returncode=1)

    with pytest.raises(ValueError, match="CANONICAL_BASE_ANCESTRY_MISMATCH"):
        phase11.verify_current_base_identity()


def test_phase7_method_e_authorities_and_native_mappings_are_frozen() -> None:
    assert phase11.CANONICAL_METHOD_IMPLEMENTATION.endswith(
        "reference_e_iterative_exact_one_exchange_ascent.py"
    )
    assert phase11.K_SCOPE == (10, 15, 20)
    assert {spec.structure_id for spec in phase11.STRUCTURES} == {
        "DAILY_539",
        "POWER_LOTTO_ZONE1",
    }
    for spec in phase11.STRUCTURES:
        authority = phase11.verify_phase7_authority(spec)
        assert authority["sha256"] == spec.phase7_authority_sha256
        assert authority["method_e_portfolio_sha256_k20"] == (
            spec.expected_method_e_sha256_k20
        )
        for k, expected_q in spec.expected_method_e_q.items():
            assert _fraction(authority["method_e_q"][str(k)]) == expected_q


def test_canonical_json_bytes_is_deterministic() -> None:
    first = {"z": [3, 2, 1], "a": {"q": "2/3", "n": 2}}
    second = {"a": {"n": 2, "q": "2/3"}, "z": [3, 2, 1]}

    first_bytes = phase11.canonical_json_bytes(first)
    second_bytes = phase11.canonical_json_bytes(second)

    assert first_bytes == second_bytes
    assert first_bytes.endswith(b"\n")


def test_phase11_result_contains_six_terminal_certificates() -> None:
    payload = cast(
        dict[str, Any], json.loads(phase11.OUTPUT_PATH.read_text(encoding="utf-8"))
    )
    assert payload["study_id"] == phase11.STUDY_ID
    assert payload["canonical_method_implementation"] == (
        phase11.CANONICAL_METHOD_IMPLEMENTATION
    )
    assert payload["gate"]["phase11_execution_gate"] == "PASS"
    assert payload["gate"]["global_optimum_status"] == "UNKNOWN"
    assert payload["rung_coupling"] == "NONE"
    assert payload["invariants"]["p638_zone2"] == "NOT_RUN"

    for spec in phase11.STRUCTURES:
        structure = cast(dict[str, Any], payload["structures"][spec.structure_id])
        assert structure["structure_id"] == spec.structure_id
        assert structure["pool_size"] == spec.pool_size
        assert structure["draw_size"] == spec.draw_size
        assert structure["primary_event_minimum_matches"] == 3
        method_e = cast(dict[str, Any], structure["method_e_regeneration"])
        assert method_e["portfolio_20_sha256"] == spec.expected_method_e_sha256_k20
        assert phase11.portfolio_sha256(_portfolio(method_e["portfolio_20"])) == (
            spec.expected_method_e_sha256_k20
        )

        per_k = cast(dict[str, Any], structure["per_k"])
        assert set(per_k) == {str(k) for k in phase11.K_SCOPE}
        for k in phase11.K_SCOPE:
            rung = cast(dict[str, Any], per_k[str(k)])
            assert rung["structure_id"] == spec.structure_id
            assert rung["k"] == k
            seed = _portfolio(rung["seed_method_e_portfolio"])
            assert len(seed) == k
            assert phase11.portfolio_sha256(seed) == rung["seed_method_e_portfolio_sha256"]
            assert _fraction(rung["seed_exact_q"]) == spec.expected_method_e_q[k]

            iterations = cast(list[dict[str, Any]], rung["iterations"])
            assert rung["iteration_count"] == len(iterations)
            assert rung["move_count"] == sum(
                1 for iteration in iterations if iteration["accepted_move"]
            )
            for index, iteration in enumerate(iterations):
                assert iteration["structure_id"] == spec.structure_id
                assert iteration["iteration_index"] == index
                input_portfolio = _portfolio(iteration["input_portfolio"])
                best_portfolio = _portfolio(iteration["best_neighbor_portfolio"])
                assert phase11.portfolio_sha256(input_portfolio) == iteration[
                    "input_portfolio_sha256"
                ]
                assert phase11.portfolio_sha256(best_portfolio) == iteration[
                    "best_neighbor_portfolio_sha256"
                ]
                input_q = _fraction(iteration["exact_input_q"])
                best_q = _fraction(iteration["exact_best_neighbor_q"])
                assert _fraction(iteration["delta"]) == best_q - input_q
                assert _fraction(iteration["exact_delta"]) == best_q - input_q
                if iteration["accepted_move"]:
                    assert best_q > input_q

            for previous, following in itertools.pairwise(iterations):
                assert previous["accepted_move"] is True
                assert previous["best_neighbor_portfolio"] == following["input_portfolio"]
                assert previous["exact_best_neighbor_q"] == following["exact_input_q"]

            terminal = iterations[-1]
            terminal_q = _fraction(rung["terminal_q"])
            terminal_portfolio = _portfolio(rung["terminal_portfolio"])
            assert terminal["accepted_move"] is False
            assert _fraction(terminal["exact_input_q"]) == terminal_q
            assert _fraction(terminal["exact_best_neighbor_q"]) <= terminal_q
            assert terminal_portfolio == _portfolio(terminal["input_portfolio"])
            assert terminal_portfolio == _portfolio(rung["terminal_portfolio"])
            assert phase11.portfolio_sha256(terminal_portfolio) == rung[
                "terminal_portfolio_sha256"
            ]
            assert _fraction(rung["terminal_exact_q"]) == terminal_q
            assert _fraction(rung["exact_delta_terminal_vs_method_e"]) == (
                terminal_q - spec.expected_method_e_q[k]
            )
            assert rung["terminal_classification"] == (
                "TERMINAL_1EXCHANGE_LOCAL_OPTIMUM_CERTIFIED"
            )
            assert rung["terminal_certificate"]["status"] == "PASS"
            assert rung["terminal_certificate"]["terminal_iteration_accepted_move"] is False
            assert rung["terminal_certificate"]["terminal_best_q_lte_terminal_q"] is True
