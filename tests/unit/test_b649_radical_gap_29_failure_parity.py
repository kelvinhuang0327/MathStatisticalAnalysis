"""Focused contracts for the sealed Radical-gap 29-failure attribution."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tools import analyze_b649_radical_gap_29_failure_parity as analyzer


def _sealed_history(count: int) -> tuple[analyzer.SealedTargetRow, ...]:
    rows: list[analyzer.SealedTargetRow] = []
    for index in range(count):
        values = sorted(((index * 7 + offset * 5) % 49) + 1 for offset in range(6))
        previous = str(index) if index else "PREVIOUS"
        rows.append(
            analyzer.SealedTargetRow(
                target_draw_number=str(index + 1),
                target_draw_date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
                main_numbers=(
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                ),
                special_number=next(number for number in range(1, 50) if number not in values),
                replay_status="COMPLETE",
                reason=None,
                causal_cutoff_draw_number=previous,
                causal_cutoff_date="2025-12-31",
                causal_history_length=index,
                causal_history_fingerprint="0" * 64,
            )
        )
    return tuple(rows)


def test_donor_faithful_closure_and_adapter_intermediates_match() -> None:
    reference, adapter = analyzer.inspect_execution_paths(
        _sealed_history(300),
        "301",
    )

    classification, divergence = analyzer.classify_observations(reference, adapter)

    assert classification == analyzer.DONOR_FAITHFUL_SOURCE_CLOSURE
    assert divergence is None
    assert reference.outcome_status == "CLOSED"
    assert reference.closure_reason == analyzer.REFERENCE_CLOSURE_REASON
    assert adapter.outcome_status == "CLOSED"
    assert adapter.closure_reason == analyzer.ADAPTER_CLOSURE_REASON
    assert reference.components == adapter.components
    assert reference.candidate_pools == adapter.candidate_pools
    assert any(len(pool) < 6 for pool in reference.candidate_pools)


def test_exact_sealed_29_target_accounting_accepts_only_pinned_order() -> None:
    assert analyzer.require_exact_failure_targets(analyzer.EXPECTED_FAILURE_TARGETS) == (
        analyzer.EXPECTED_FAILURE_TARGETS
    )

    with pytest.raises(
        analyzer.ParityAttributionError,
        match="SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: exact 29-target accounting",
    ):
        analyzer.require_exact_failure_targets(analyzer.EXPECTED_FAILURE_TARGETS[:-1])


def test_port_regression_reports_first_divergent_candidate_pool() -> None:
    reference, adapter = analyzer.inspect_execution_paths(
        _sealed_history(300),
        "301",
    )
    changed_adapter = replace(
        adapter,
        candidate_pools=((49,), adapter.candidate_pools[1]),
    )

    classification, divergence = analyzer.classify_observations(
        reference,
        changed_adapter,
    )

    assert classification == analyzer.PORT_REGRESSION
    assert divergence == "candidate_pool:GAP_01_19"


def test_source_authority_digest_mismatch_fails_closed() -> None:
    with pytest.raises(
        analyzer.ParityAttributionError,
        match="SEALED_RADICAL_FAILURE_AUTHORITY_UNAVAILABLE: SHA-256 mismatch",
    ):
        analyzer.require_digest("0" * 64, "1" * 64, "sealed fixture")


def test_unresolved_retained_reference_never_becomes_port_regression() -> None:
    unresolved = analyzer.PathObservation(
        components=(),
        candidate_pools=(),
        outcome_status="UNRESOLVED",
        tickets=None,
        closure_reason=None,
        exception_type="ReferenceError",
        exception_message="unavailable",
    )
    adapter = replace(
        unresolved,
        outcome_status="CLOSED",
        closure_reason=analyzer.ADAPTER_CLOSURE_REASON,
        exception_type="InvalidOutput",
        exception_message=analyzer.ADAPTER_CLOSURE_REASON,
    )

    assert analyzer.classify_observations(unresolved, adapter) == (
        analyzer.SOURCE_AUTHORITY_UNRESOLVED,
        None,
    )


def test_canonical_output_is_deterministic() -> None:
    first = {
        "rows": [{"target": "2"}, {"target": "1"}],
        "summary": {"b": 2, "a": 1},
    }
    second = {
        "summary": {"a": 1, "b": 2},
        "rows": [{"target": "2"}, {"target": "1"}],
    }

    assert analyzer.canonical_json_bytes(first) == analyzer.canonical_json_bytes(second)
    assert analyzer.canonical_json_bytes(first).endswith(b"\n")
