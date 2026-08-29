"""Focused tests for B649 K2 fixed-universe failure attribution."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import pytest
from tools import analyze_b649_k2_fixed_universe_failures as analyzer


def _metadata(
    strategy_id: str,
    *,
    family: str,
    display_name: str | None = None,
) -> analyzer.StrategyMetadata:
    return analyzer.StrategyMetadata(
        strategy_id=strategy_id,
        display_name=display_name or strategy_id,
        version="v0.1",
        adapter_path=f"lottolab.strategies.adapters.{family}:Adapter",
        implementation_family=family,
        provenance=(),
    )


def _row(
    strategy_id: str,
    target: str,
    target_date: str,
    *,
    failure_reason: str | None = None,
) -> analyzer.EvidenceRow:
    return analyzer.EvidenceRow(
        strategy_id=strategy_id,
        strategy_version="v0.1",
        display_name=strategy_id,
        target_draw_number=target,
        target_draw_date=target_date,
        replay_status="EXECUTION_FAILURE" if failure_reason else "COMPLETE",
        reason=failure_reason,
    )


def _fixture() -> tuple[
    tuple[analyzer.EvidenceRow, ...],
    dict[str, analyzer.StrategyMetadata],
]:
    targets = (
        ("001", "2026-01-01"),
        ("002", "2026-01-02"),
        ("003", "2026-01-03"),
        ("004", "2026-01-04"),
    )
    metadata = {
        "intermittent": _metadata("intermittent", family="radical"),
        "persistent": _metadata("persistent", family="wave12"),
        "stable": _metadata("stable", family="stable"),
    }
    rows: list[analyzer.EvidenceRow] = []
    for strategy_id in metadata:
        for target, target_date in targets:
            reason: str | None = None
            if strategy_id == "persistent":
                reason = "Wave12FrozenSourceError: SLICE"
            elif strategy_id == "intermittent" and target in {"002", "004"}:
                reason = "InvalidOutput: TOO_FEW"
            rows.append(
                _row(
                    strategy_id,
                    target,
                    target_date,
                    failure_reason=reason,
                )
            )
    return tuple(rows), metadata


def _taxonomy(
    rows: tuple[analyzer.EvidenceRow, ...] | None = None,
) -> dict[str, Any]:
    fixture_rows, metadata = _fixture()
    return analyzer.build_failure_taxonomy(
        rows or fixture_rows,
        metadata,
        analyzer.EXPECTED_WAVE26_AUTHORITY_LINEAGE_IDS,
        expected_target_count=4,
        expected_strategy_ids=tuple(metadata),
    )


def _matrix_by_id(taxonomy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    matrix = cast(list[dict[str, Any]], taxonomy["per_strategy_failure_matrix"])
    return {cast(str, row["strategy_id"]): row for row in matrix}


def test_failure_set_accounting_and_target_union_coverage() -> None:
    taxonomy = _taxonomy()
    matrix = _matrix_by_id(taxonomy)

    assert matrix["stable"]["evaluated_target_count"] == 4
    assert matrix["stable"]["successful_target_count"] == 4
    assert matrix["stable"]["execution_failure_count"] == 0
    assert matrix["persistent"]["successful_target_count"] == 0
    assert matrix["persistent"]["execution_failure_count"] == 4
    assert matrix["intermittent"]["successful_target_count"] == 2
    assert matrix["intermittent"]["execution_failure_count"] == 2

    assert taxonomy["blocked_target_union"]["target_count"] == 4
    assert taxonomy["blocked_target_union"]["targets"] == ["001", "002", "003", "004"]
    assert taxonomy["fixed_universe"]["complete_target_count"] == 0
    assert taxonomy["per_target_failing_strategy_count_distribution"] == {
        "1": 2,
        "2": 2,
    }


def test_no_failure_persistent_and_intermittent_rows_are_classified() -> None:
    matrix = _matrix_by_id(_taxonomy())

    assert matrix["stable"]["failure_pattern"] == "NO_FAILURE"
    assert matrix["stable"]["first_failure_target"] is None
    assert matrix["stable"]["failure_reason_counts"] == {}

    assert matrix["persistent"]["failure_pattern"] == "PERSISTENT"
    assert matrix["persistent"]["first_failure_target"] == "001"
    assert matrix["persistent"]["last_failure_target"] == "004"
    assert matrix["persistent"]["failure_run_count"] == 1

    assert matrix["intermittent"]["failure_pattern"] == "INTERMITTENT"
    assert matrix["intermittent"]["failure_run_count"] == 2
    assert matrix["intermittent"]["isolated_failure_targets"] == ["002", "004"]
    assert matrix["intermittent"]["failure_categories"] == {"InvalidOutput": 2}


def test_minimum_cover_set_logic_is_exact_and_deterministic() -> None:
    failure_sets = {
        "d": frozenset({"2", "3"}),
        "c": frozenset({"1"}),
        "b": frozenset({"3"}),
        "a": frozenset({"1", "2"}),
    }

    assert analyzer.minimum_failure_cover_sets(
        failure_sets, frozenset({"1", "2", "3"})
    ) == (("a", "b"), ("a", "d"), ("c", "d"))
    assert analyzer.minimum_failure_cover_sets({}, frozenset()) == ((),)
    assert _taxonomy()["diagnostic_cover_sets"] == {
        "meaning": (
            "strategy failure-set union covers every blocked target; "
            "not an exclusion authorization"
        ),
        "minimum_cardinality": 1,
        "strategy_sets": [["persistent"]],
    }


def test_duplicate_strategy_target_row_fails_closed() -> None:
    rows, _ = _fixture()

    with pytest.raises(
        analyzer.FailureTaxonomyError,
        match="DUPLICATE_K2_STRATEGY_TARGET_ROW: intermittent/001",
    ):
        _taxonomy((*rows, rows[0]))


def test_exact_source_hash_verification_accepts_match_and_rejects_mismatch() -> None:
    task_file = Path(__file__)
    expected = hashlib.sha256(task_file.read_bytes()).hexdigest()

    assert analyzer.require_sha256(task_file, expected)["sha256"] == expected
    with pytest.raises(
        analyzer.FailureTaxonomyError,
        match="SEALED_B649_K2_EVIDENCE_UNAVAILABLE: SHA-256 mismatch",
    ):
        analyzer.require_sha256(task_file, "0" * 64)


def test_output_ordering_and_serialization_are_deterministic() -> None:
    rows, metadata = _fixture()
    first = analyzer.build_failure_taxonomy(
        rows,
        metadata,
        tuple(reversed(analyzer.EXPECTED_WAVE26_AUTHORITY_LINEAGE_IDS)),
        expected_target_count=4,
        expected_strategy_ids=tuple(reversed(metadata)),
    )
    second = analyzer.build_failure_taxonomy(
        tuple(reversed(rows)),
        dict(reversed(tuple(metadata.items()))),
        analyzer.EXPECTED_WAVE26_AUTHORITY_LINEAGE_IDS,
        expected_target_count=4,
        expected_strategy_ids=tuple(metadata),
    )

    assert analyzer.canonical_json_bytes(first) == analyzer.canonical_json_bytes(second)
    assert analyzer.canonical_json_bytes(first).endswith(b"\n")


def test_wave26_ids_do_not_intersect_k2_fixture() -> None:
    wave26 = cast(dict[str, Any], _taxonomy()["wave26_authority_lineage"])

    assert wave26["strategy_ids"] == list(analyzer.EXPECTED_WAVE26_AUTHORITY_LINEAGE_IDS)
    assert wave26["involved_in_k2_universe"] == []
    assert wave26["involved_in_k2_failure_set"] == []
