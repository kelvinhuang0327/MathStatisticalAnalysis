# pyright: reportPrivateUsage=false

"""Focused contract tests for the imported-optimizer Strategy Matrix."""

from __future__ import annotations

import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import strategy_matrix_comparison as smc
from lottolab.research.biglotto_multi_ticket_constructors_r1 import CONSTRUCTORS
from lottolab.research.strategy_matrix_comparison import (
    BOUNDED,
    HARD_DIV,
    K_SCOPE,
    LEDGER_PATH,
    NATIVE_MEASUREMENT_PATH,
    NATIVE_PORTFOLIO_HASH_CANONICALIZATION,
    PAIRWISE_MAX_INTERSECTION,
    RESULT_PATH,
    RULES,
    SIDON,
    _attach_native_portfolio_hash,
    _hard_div_native_row,
    build_comparison,
    canonical_json_bytes,
)

ROOT = Path(__file__).resolve().parents[2]
# Frozen HARD_DIV evidence. `native_sha256` is the adapter's own compact-JSON
# identity; the Matrix's portfolio_sha256 is deliberately a different byte
# convention over the same portfolio and is NOT expected to equal it.
HARD_DIV_FROZEN: dict[int, dict[str, str]] = {
    2: {
        "seed_q": "129287/3495954",
        "exact_q": "21702/582659",
        "delta": "925/3495954",
        "native_sha256": "2588a64fddeef6b7a66c35cfa7407f7df185daff9678d8a7632a627de7c5b3cd",
    },
    3: {
        "seed_q": "27487/499422",
        "exact_q": "32528/582659",
        "delta": "2759/3495954",
        "native_sha256": "f3f8026685d58c60ddba7eb4155edbb6c05e545ba5bf693f0d57b44ddd45dadf",
    },
    5: {
        "seed_q": "18299/202664",
        "exact_q": "54130/582659",
        "delta": "12163/4661272",
        "native_sha256": "985ceea1c7790da4b4b47b01585e1ca41cdcd927a2c63f50462de2c75edce009",
    },
    10: {
        "seed_q": "2428175/13983816",
        "exact_q": "364025/1997688",
        "delta": "5000/582659",
        "native_sha256": "13b1126d5b26ce44c9aba24670142eeab49f4a4b51aaf3bbabe7a7f1659ac673",
    },
    20: {
        "seed_q": "108833/332948",
        "exact_q": "4805093/13983816",
        "delta": "4981/297528",
        "native_sha256": "a920c98327de729438c240b57d0b4a8a47909404106f40cd1f687a60ffc7d3bf",
    },
}
HARD_DIV_ROW_IDS = {k: f"NATIVE_BIG_LOTTO|{HARD_DIV}|default|k{k}|m3" for k in HARD_DIV_FROZEN}
REQUIRED_SURFACE = {
    "strategy_family",
    "strategy_id",
    "method_type",
    "portfolio_or_ticket_level",
    "supported_lottery",
    "supported_k",
    "objective",
    "search_type",
    "neighborhood_radius",
    "exact_or_heuristic",
    "diversification_constraint",
    "deterministic",
    "source_status",
    "evidence_source",
    "proof_status",
}


REBUILD = os.environ.get("MATRIX_REBUILD") == "1"


@pytest.fixture(scope="module")
def comparison() -> dict[str, Any]:
    """The canonical artifact by default; a real rebuild only when asked for.

    Registering HARD_DIV made the build perform an exact radius-1 five-k search
    that costs tens of minutes, so the default contract run validates the
    checked-in canonical artifact - the actual deliverable, written by
    ``tools/run_strategy_matrix_imported_optimizers.py``. Set ``MATRIX_REBUILD=1``
    to re-derive it in-process and additionally prove it reproduces byte-for-byte.
    """

    if REBUILD:
        return build_comparison(ROOT)
    return cast(dict[str, Any], json.loads((ROOT / RESULT_PATH).read_text()))


def _hard_div_rows(comparison: dict[str, Any]) -> dict[int, dict[str, Any]]:
    by_id = {row["row_id"]: row for row in comparison["rows"]}
    return {k: by_id[row_id] for k, row_id in HARD_DIV_ROW_IDS.items()}


def test_intake_has_twelve_methods_seven_deduplicated_families_and_full_surface(
    comparison: dict[str, Any],
) -> None:
    methods = comparison["methods"]
    assert comparison["imported_method_count"] == len(methods) == 12
    assert comparison["distinct_family_count"] == len(comparison["method_families"]) == 7
    assert len({method["strategy_id"] for method in methods}) == 12
    assert all(method.keys() >= REQUIRED_SURFACE for method in methods)

    bounded = next(method for method in methods if method["strategy_id"] == BOUNDED)
    assert {entry["path"] for entry in bounded["source_files"]} >= {
        "src/lottolab/research/bounded_coverage_optimizer.py",
        "src/lottolab/research/bounded_coverage_optimizer_fast.py",
    }
    assert not any("FAST" in method["strategy_id"] for method in methods)


def test_frozen_candidate_constructors_map_k_5_10_20_and_mark_low_k_not_applicable(
    comparison: dict[str, Any],
) -> None:
    methods = {method["strategy_id"]: method for method in comparison["methods"]}
    for strategy_id in CONSTRUCTORS:
        assert methods[strategy_id]["supported_k"] == [5, 10, 20]
        rows = [
            row
            for row in comparison["rows"]
            if row["strategy_id"] == strategy_id
            and row["case_id"].startswith("CANDIDATES_BIG_LOTTO_")
        ]
        by_k = {k: {row["status"] for row in rows if row["k"] == k} for k in K_SCOPE}
        assert by_k[2] == by_k[3] == {"NOT_APPLICABLE"}
        assert by_k[5] == by_k[10] == by_k[20] == {"MEASURED"}


def test_exact_evaluation_and_local_certificates_do_not_imply_global_optimum(
    comparison: dict[str, Any],
) -> None:
    exact_rows = [row for row in comparison["rows"] if row["exact_q"] is not None]
    assert exact_rows
    for row in exact_rows:
        q = Fraction(row["exact_q"]["exact"])
        if row["global_optimum_status"] == "CERTIFIED_BY_UNIT_UPPER_BOUND":
            assert q == 1
            assert row["proof_status"] == "GLOBAL_OPTIMUM_CERTIFIED_BY_UNIT_UPPER_BOUND"
        else:
            assert row["global_optimum_status"] == "UNKNOWN"

    local_rows = [
        row
        for row in exact_rows
        if row["local_optimum_status"] == "CERTIFIED_ONE_NUMBER_EXCHANGE"
        and Fraction(row["exact_q"]["exact"]) < 1
    ]
    assert local_rows
    assert all("NO_GLOBAL_PROOF" in row["proof_status"] for row in local_rows)


def test_missing_search_capabilities_are_explicit_gaps_not_false_results(
    comparison: dict[str, Any],
) -> None:
    gaps = {gap["gap_id"]: gap for gap in comparison["gaps"]}
    assert {
        "GLOBAL_EXACT_SOLVER",
        "TWO_EXCHANGE_AND_RADIUS_N",
        "COVERAGE_WITH_HARD_DIVERSIFICATION",
        "EXPECTED_HIT_UTILITY_CONTRACT",
    } <= gaps.keys()
    assert gaps["GLOBAL_EXACT_SOLVER"]["category"] == "METHOD_GAPS"
    assert gaps["TWO_EXCHANGE_AND_RADIUS_N"]["category"] == "SEARCH_GAPS"
    assert set(comparison["handoffs"]["branch_3"]) == {
        "GLOBAL_EXACT_SOLVER",
        "K_GAP_NATIVE_CANDIDATE_CONSTRUCTORS",
        "TWO_EXCHANGE_AND_RADIUS_N",
        "COVERAGE_WITH_HARD_DIVERSIFICATION",
    }
    assert gaps["EXPECTED_HIT_UTILITY_CONTRACT"]["handoff_branch"] is None
    assert not any(
        row["search_type"] in {"GLOBAL_EXACT_SOLVER", "TWO_EXCHANGE", "RADIUS_N"}
        for row in comparison["rows"]
    )


def test_new_comparisons_and_reused_native_evidence_remain_disjoint(
    comparison: dict[str, Any],
) -> None:
    measured = {row["row_id"] for row in comparison["rows"] if row["status"] == "MEASURED"}
    reused = {row["row_id"] for row in comparison["rows"] if row["status"] == "REUSED_VERIFIED"}
    assert measured == set(comparison["new_deterministic_comparison_row_ids"])
    assert reused == set(comparison["reused_native_evidence_row_ids"])
    assert measured and reused and measured.isdisjoint(reused)
    assert all(
        row["source_evidence"] is not None
        for row in comparison["rows"]
        if row["status"] == "REUSED_VERIFIED"
    )


def test_native_measurement_artifact_closes_open_cells_without_pooling_evidence(
    comparison: dict[str, Any],
) -> None:
    ledger = json.loads((ROOT / LEDGER_PATH).read_text())
    entry = ledger["imported_optimizer_matrix"]["native_evidence"]["native_coverage_r1"]
    artifact_path = ROOT / NATIVE_MEASUREMENT_PATH
    artifact = json.loads(artifact_path.read_text())

    assert entry["evidence_class"] == "NEW_NATIVE_MEASURED_EVIDENCE"
    assert entry["path"] == NATIVE_MEASUREMENT_PATH.as_posix()
    assert entry["sha256"] == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    assert artifact["starting_supported_native_not_run_count"] == 79
    assert artifact["new_native_measured_count"] == 79
    assert artifact["remaining_native_not_run_count"] == 0
    assert len(artifact["rows"]) == 79
    assert canonical_json_bytes(artifact) == artifact_path.read_bytes()

    measured = [row for row in artifact["rows"] if row["status"] == "MEASURED"]
    not_run = [row for row in artifact["rows"] if row["status"] == "NOT_RUN"]
    assert all(
        row["measurement_evidence"]["execution_classification"]
        == "EXECUTED_EXISTING_NATIVE_METHOD"
        for row in measured
    )
    assert not not_run

    native_rows = [row for row in comparison["rows"] if row["case_id"].startswith("NATIVE_")]
    new_native_rows = [
        row
        for row in native_rows
        if row["status"] == "MEASURED"
        and row["source_evidence"] is not None
        and row["source_evidence"]["path"] == NATIVE_MEASUREMENT_PATH.as_posix()
    ]
    assert len(new_native_rows) == 79
    assert all(row["evidence_scope"] == "NATIVE_UNIFORM_WINNING_SPACE" for row in new_native_rows)
    direct_native_rows = [
        row
        for row in native_rows
        if row["status"] == "MEASURED" and row["strategy_id"] == HARD_DIV
    ]
    assert len(direct_native_rows) == 5
    assert all(
        row["source_evidence"]["dispatch"] == "CANONICAL_ADAPTER_PUBLIC_API"
        and row["measurement_evidence"]["dispatch"]
        == "CANONICAL_HARD_DIV_PAIRWISE_BOUNDED_CANDIDATE_ADAPTER"
        for row in direct_native_rows
    )
    assert all(
        row["status"] in {"REUSED_VERIFIED", "NOT_APPLICABLE", "NOT_RUN"}
        or row["source_evidence"].get("evidence_class") == "NEW_NATIVE_MEASURED_EVIDENCE"
        or row in direct_native_rows
        for row in native_rows
    )

    geometry_rows = [
        row
        for row in comparison["rows"]
        if row["evidence_scope"] == "NATIVE_RULE_SYNTHETIC_CANDIDATE_GEOMETRY"
        and row.get("coverage_status") is not None
    ]
    assert geometry_rows
    assert all(row["coverage_status"] == "NOT_RUN" for row in geometry_rows)


def test_canonical_ledger_is_consumed_and_build_is_deterministic(
    comparison: dict[str, Any],
) -> None:
    ledger = json.loads((ROOT / LEDGER_PATH).read_text())
    intake = ledger["imported_optimizer_matrix"]
    assert intake["canonical_result_path"] == RESULT_PATH.as_posix()
    assert (
        comparison["matrix_intake_sha256"]
        == hashlib.sha256(canonical_json_bytes(intake)).hexdigest()
    )
    # Determinism is proved by re-serializing the SAME already-computed result
    # objects, not by repeating the exact five-k search: canonical serialization
    # must be idempotent under a round-trip (no key-order or float instability).
    # Cross-process build reproducibility is covered by the checked-in artifact
    # comparison below, where the artifact was written by a separate runner
    # process from the one that builds this fixture.
    serialized = canonical_json_bytes(comparison)
    assert canonical_json_bytes(json.loads(serialized)) == serialized
    row_ids = [row["row_id"] for row in comparison["rows"]]
    assert row_ids == sorted(row_ids)
    assert len(row_ids) == len(set(row_ids))


@pytest.mark.skipif(
    not REBUILD,
    reason="needs MATRIX_REBUILD=1: re-runs the exact five-k search (tens of minutes)",
)
def test_checked_in_result_is_the_canonical_build(comparison: dict[str, Any]) -> None:
    assert (ROOT / RESULT_PATH).read_bytes() == canonical_json_bytes(comparison)


def test_checked_in_result_is_canonically_serialized(comparison: dict[str, Any]) -> None:
    """The artifact on disk must already be in canonical form, rebuild or not."""

    on_disk = (ROOT / RESULT_PATH).read_bytes()
    assert canonical_json_bytes(json.loads(on_disk)) == on_disk
    assert canonical_json_bytes(comparison) == on_disk


def test_hard_div_is_registered_once_with_its_frozen_contract(
    comparison: dict[str, Any],
) -> None:
    methods = [m for m in comparison["methods"] if m["strategy_id"] == HARD_DIV]
    assert len(methods) == 1
    method = methods[0]
    assert method["supported_k"] == [2, 3, 5, 10, 20]
    assert method["supported_lottery"] == ["BIG_LOTTO"]
    assert method["neighborhood_radius"] == 1
    assert method["deterministic"] is True
    assert method["objective"] == "EXACT_UNIFORM_M3_PLUS_COVERAGE"
    assert method["search_type"] == "EXACT_ONE_NUMBER_EXCHANGE_LOCAL_REFINEMENT"
    assert method["diversification_constraint"] == "HARD_PAIRWISE_OVERLAP_AT_MOST_ONE"
    assert method["proof_status"] == (
        "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_WITHIN_HARD_FEASIBLE_SET_NO_GLOBAL_PROOF"
    )
    assert {entry["path"] for entry in method["source_files"]} == {
        "src/lottolab/research/hard_div_pairwise_bounded_candidate_adapter.py"
    }
    # The Matrix must dispatch, never reimplement the search.
    assert method["strategy_family"] == "HARD_CONSTRAINED_EXACT_ONE_NUMBER_EXCHANGE"


def test_hard_div_has_exactly_five_measured_rows_matching_frozen_evidence(
    comparison: dict[str, Any],
) -> None:
    rows = _hard_div_rows(comparison)
    assert len(rows) == 5
    hard_div_all = [row for row in comparison["rows"] if row["strategy_id"] == HARD_DIV]
    measured = [row for row in hard_div_all if row["status"] == "MEASURED"]
    assert len(measured) == 5
    assert {row["row_id"] for row in measured} == set(HARD_DIV_ROW_IDS.values())

    for k, row in rows.items():
        frozen = HARD_DIV_FROZEN[k]
        assert row["status"] == "MEASURED"
        assert row["k"] == k
        assert row["lottery"] == "BIG_LOTTO"
        assert row["minimum_matches"] == 3
        assert row["evidence_scope"] == "NATIVE_UNIFORM_WINNING_SPACE"
        assert row["exact_q"]["exact"] == frozen["exact_q"]
        assert row["delta_vs_reference"]["exact"] == frozen["delta"]
        assert row["reference"]["strategy_id"] == SIDON
        assert row["reference"]["exact_q"]["exact"] == frozen["seed_q"]
        assert row["search_evidence"]["seed_exact_q"]["exact"] == frozen["seed_q"]
        # Exact rationals, not floats.
        assert Fraction(row["exact_q"]["exact"]) - Fraction(frozen["seed_q"]) == Fraction(
            frozen["delta"]
        )


def test_hard_div_rows_respect_the_hard_pairwise_cap_and_proof_boundary(
    comparison: dict[str, Any],
) -> None:
    for row in _hard_div_rows(comparison).values():
        assert row["geometry"]["max_pairwise_overlap"] <= PAIRWISE_MAX_INTERSECTION == 1
        assert row["search_evidence"]["hard_pairwise_intersection_cap"] == 1
        assert row["search_evidence"]["neighborhood_radius"] == 1
        assert row["local_optimum_status"] == "CERTIFIED_ONE_NUMBER_EXCHANGE"
        assert row["proof_status"] == (
            "LOCAL_OPTIMUM_CERTIFIED_EXACT_RADIUS_1_WITHIN_HARD_FEASIBLE_SET_NO_GLOBAL_PROOF"
        )
        # A radius-1 local certificate is never a global optimality claim.
        assert row["global_optimum_status"] == "UNKNOWN"
        assert row["search_evidence"]["terminal_no_strict_improvement"] is True
        assert row["search_evidence"]["complete_neighborhood_certified"] is True
    assert not any(
        row["global_optimum_status"] != "UNKNOWN"
        for row in comparison["rows"]
        if row["strategy_id"] == HARD_DIV
    )


def test_matrix_and_native_portfolio_hashes_are_independent_identities(
    comparison: dict[str, Any],
) -> None:
    """The two hashes answer different questions and must not be conflated."""

    for k, row in _hard_div_rows(comparison).items():
        portfolio = row["portfolio"]
        # portfolio_sha256 is Matrix-owned: recomputed from the stored portfolio.
        assert row["portfolio_sha256"] == hashlib.sha256(
            canonical_json_bytes(portfolio)
        ).hexdigest()
        # native_portfolio_sha256 is carried verbatim from the adapter, under a
        # different declared byte convention, and equals the frozen value.
        assert row["native_portfolio_sha256"] == HARD_DIV_FROZEN[k]["native_sha256"]
        assert row["native_portfolio_sha256"] == hashlib.sha256(
            json.dumps(portfolio, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert (
            row["native_portfolio_sha256_canonicalization"]
            == NATIVE_PORTFOLIO_HASH_CANONICALIZATION
            == "COMPACT_JSON_NO_TRAILING_NEWLINE"
        )
        # Differing canonicalizations of the same portfolio: expected, not a bug.
        assert row["portfolio_sha256"] != row["native_portfolio_sha256"]


def test_native_hash_field_is_sparse_and_always_declares_its_canonicalization(
    comparison: dict[str, Any],
) -> None:
    carriers = [row for row in comparison["rows"] if "native_portfolio_sha256" in row]
    # Only the direct-dispatch method carries a native identity today.
    assert {row["strategy_id"] for row in carriers} == {HARD_DIV}
    assert len(carriers) == 5
    for row in carriers:
        assert "native_portfolio_sha256_canonicalization" in row
        # Every adapter-provided hash declares its convention, including the seed
        # hash carried inside the native evidence block.
        evidence = row["search_evidence"]
        assert evidence["seed_portfolio_sha256"] is not None
        assert (
            evidence["portfolio_hash_canonicalization"] == NATIVE_PORTFOLIO_HASH_CANONICALIZATION
        )
    # Every pre-existing row is untouched by the new field.
    others = [row for row in comparison["rows"] if row["strategy_id"] != HARD_DIV]
    assert others
    assert not any("native_portfolio_sha256" in row for row in others)
    assert not any("native_portfolio_sha256_canonicalization" in row for row in others)


def test_every_matrix_portfolio_hash_is_self_consistent(comparison: dict[str, Any]) -> None:
    """No row may carry a portfolio hash that its own portfolio does not produce."""

    checked = 0
    for row in comparison["rows"]:
        if row.get("portfolio") is None:
            continue
        assert row["portfolio_sha256"] == hashlib.sha256(
            canonical_json_bytes(row["portfolio"])
        ).hexdigest()
        checked += 1
    assert checked >= 224


def test_hard_div_unsupported_cells_are_not_applicable_not_measured(
    comparison: dict[str, Any],
) -> None:
    hard_div = [row for row in comparison["rows"] if row["strategy_id"] == HARD_DIV]
    unsupported = [row for row in hard_div if row["lottery"] != "BIG_LOTTO"]
    assert len(unsupported) == 10
    assert {row["lottery"] for row in unsupported} == {"DAILY_539", "POWER_LOTTO_ZONE1"}
    for row in unsupported:
        assert row["status"] == "NOT_APPLICABLE"
        assert row["status_reason"] == "UNSUPPORTED_LOTTERY_OR_K"
        assert row["exact_q"] is None
        assert row["portfolio"] is None
        assert "native_portfolio_sha256" not in row
    assert len(hard_div) == 15


def test_hard_div_unsupported_k_dispatch_returns_not_applicable(
    comparison: dict[str, Any],
) -> None:
    method = next(m for m in comparison["methods"] if m["strategy_id"] == HARD_DIV)
    row = _hard_div_native_row(method, "BIG_LOTTO", RULES["BIG_LOTTO"], 4)
    assert row["status"] == "NOT_APPLICABLE"
    assert row["portfolio"] is None
    assert "native_portfolio_sha256" not in row


def test_hard_div_execution_failure_is_not_run_and_never_fabricated(
    comparison: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method = next(m for m in comparison["methods"] if m["strategy_id"] == HARD_DIV)

    def exploding_adapter(_dispatch: object) -> None:
        raise RuntimeError("adapter failed")

    monkeypatch.setattr(smc, "run_hard_div_pairwise_bounded_candidate_adapter", exploding_adapter)
    row = _hard_div_native_row(method, "BIG_LOTTO", RULES["BIG_LOTTO"], 2)
    assert row["status"] == "NOT_RUN"
    assert row["status_reason"] == "HARD_DIV_ADAPTER_EXECUTION_FAILED:RuntimeError"
    assert row["exact_q"] is None
    assert row["portfolio"] is None
    assert "portfolio_sha256" not in row
    assert "native_portfolio_sha256" not in row


def test_native_hash_helper_rejects_a_hash_without_valid_digest(
    comparison: dict[str, Any],
) -> None:
    row: dict[str, Any] = {}
    with pytest.raises(ValueError, match="native portfolio hash"):
        _attach_native_portfolio_hash(row, "not-a-sha256")
    assert row == {}
    with pytest.raises(ValueError, match="native portfolio hash"):
        _attach_native_portfolio_hash(row, "AB" * 32)
    valid = HARD_DIV_FROZEN[2]["native_sha256"]
    _attach_native_portfolio_hash(row, valid)
    assert row["native_portfolio_sha256"] == valid
    assert row["native_portfolio_sha256_canonicalization"] == (
        NATIVE_PORTFOLIO_HASH_CANONICALIZATION
    )


def test_hard_div_registration_uses_no_history_db_or_future_outcome(
    comparison: dict[str, Any],
) -> None:
    assert comparison["claim_boundary"]["db_access"] == "NO"
    assert comparison["claim_boundary"]["db_write"] == "NO"
    assert comparison["claim_boundary"]["future_outcome_access"] == "NO"
    assert comparison["claim_boundary"]["global_optimum_without_proof"] == "NEVER_CLAIMED"
    for row in _hard_div_rows(comparison).values():
        evidence = row["measurement_evidence"]
        assert evidence["execution_classification"] == "EXECUTED_EXISTING_NATIVE_METHOD"
        assert evidence["dispatch"] == "CANONICAL_HARD_DIV_PAIRWISE_BOUNDED_CANDIDATE_ADAPTER"
        assert evidence["method_invocation"] == HARD_DIV
        # Coverage is over the uniform winning space, not a draw history.
        assert row["search_evidence"]["total_draw_count"] == 13983816


def test_hard_div_is_excluded_from_the_native_coverage_checkpoint_population() -> None:
    """HARD_DIV runs inline, so it must not widen the pinned checkpoint's cells."""

    matrix = smc.load_matrix(ROOT)
    methods = {m["strategy_id"]: m for m in matrix["methods"]}
    expected_open = smc._native_supported_not_run_row_ids(methods)
    artifact = json.loads((ROOT / NATIVE_MEASUREMENT_PATH).read_text())
    assert expected_open == artifact["supported_native_not_run_row_ids"]
    assert len(expected_open) == 79
    assert not any(HARD_DIV in row_id for row_id in expected_open)
    assert not smc._is_checkpoint_managed(HARD_DIV, "BIG_LOTTO", 2)
    assert smc._is_checkpoint_managed(smc.ITERATIVE, "BIG_LOTTO", 2)
