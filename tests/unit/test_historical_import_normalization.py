"""Adversarial tests for strict raw-JSON verification (BLHQ R1)."""

from __future__ import annotations

import copy
from typing import Any

from tests.fixtures.historical.builder import (
    REAL_STRATEGY_IDS,
    build_baseline_envelope,
    build_small_envelope,
    envelope_bytes,
    recompute_envelope_hashes,
)

from lottolab.domain.historical_results import HistoricalRunImport
from lottolab.normalization.historical_import import (
    HistoricalImportOutcome,
    HistoricalImportVerificationResult,
    verify_and_normalize_historical_import,
)


def _verify(envelope: dict[str, Any]) -> HistoricalImportVerificationResult:
    return verify_and_normalize_historical_import(envelope_bytes(envelope))


def test_fresh_valid_import_passes_and_normalizes() -> None:
    envelope = build_baseline_envelope()
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_PASS
    assert result.findings == ()
    assert isinstance(result.normalized_import, HistoricalRunImport)
    assert result.normalized_import.import_identity_sha256 == envelope["import_identity_sha256"]
    assert result.normalized_import.manifest_sha256 == envelope["manifest_sha256"]
    assert len(result.normalized_import.portfolios) == 5
    assert all(len(p.tickets) == 20 for p in result.normalized_import.portfolios)
    assert all(
        tuple(t.portfolio_position for t in p.tickets) == tuple(range(1, 21))
        for p in result.normalized_import.portfolios
    )


def test_distinct_envelopes_yield_distinct_import_identities() -> None:
    big = build_baseline_envelope()
    small = build_small_envelope()
    assert big["import_identity_sha256"] != small["import_identity_sha256"]
    assert _verify(big).outcome is HistoricalImportOutcome.IMPORT_PASS
    assert _verify(small).outcome is HistoricalImportOutcome.IMPORT_PASS


def test_malformed_json_is_rejected() -> None:
    result = verify_and_normalize_historical_import(b"{not valid json")
    assert result.outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED
    assert result.normalized_import is None
    assert result.findings


def test_non_bytes_input_is_rejected() -> None:
    result = verify_and_normalize_historical_import("not-bytes")  # type: ignore[arg-type]
    assert result.outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_extra_field_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["unexpected_field"] = "nope"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_synthetic_identity_prefix_guard_rejects_mismatched_id() -> None:
    envelope = build_baseline_envelope()
    envelope["strategy_descriptors"][2]["strategy_id"] = "NOT_SYNTHETIC_BASE_A"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_non_synthetic_identity_cannot_use_synthetic_prefix() -> None:
    envelope = build_baseline_envelope()
    envelope["strategy_descriptors"][0]["strategy_id"] = "SYNTHETIC_" + REAL_STRATEGY_IDS[0]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_duplicate_strategy_descriptor_triple_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["strategy_descriptors"].append(copy.deepcopy(envelope["strategy_descriptors"][0]))
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_duplicate_draw_number_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"].append(copy.deepcopy(envelope["draw_snapshots"][0]))
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_manifest_hash_mismatch_is_rejected_before_db_access() -> None:
    envelope = build_baseline_envelope()
    envelope["manifest_sha256"] = "0" * 64
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_MANIFEST_HASH_MISMATCH


def test_import_identity_hash_mismatch_is_rejected_before_manifest() -> None:
    envelope = build_baseline_envelope()
    envelope["import_identity_sha256"] = "1" * 64
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_IDENTITY_HASH_MISMATCH


def test_causal_violation_when_cutoff_not_before_target() -> None:
    envelope = build_baseline_envelope()
    portfolio = envelope["portfolios"][0]
    portfolio["cutoff_draw_number"] = portfolio["target_draw_number"]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_CAUSAL_VIOLATION


def test_causal_violation_when_referenced_draw_is_absent() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["cutoff_draw_number"] = 1
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_CAUSAL_VIOLATION


def test_strategy_reference_absent_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["strategy_version"] = "does-not-exist"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_STRATEGY_REFERENCE_ABSENT


def test_alias_target_absent_is_rejected() -> None:
    envelope = build_baseline_envelope()
    for descriptor in envelope["strategy_descriptors"]:
        if descriptor["strategy_id"] == "SYNTHETIC_ALIAS_B":
            descriptor["alias_of_strategy_id"] = "SYNTHETIC_NOWHERE"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_ALIAS_TARGET_ABSENT


def test_portfolio_with_wrong_ticket_count_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["tickets"].pop()
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_TICKET_SHAPE_VIOLATION


def test_duplicate_ticket_position_is_rejected() -> None:
    envelope = build_baseline_envelope()
    tickets = envelope["portfolios"][0]["tickets"]
    tickets[5] = copy.deepcopy(tickets[4])
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_TICKET_SHAPE_VIOLATION


def test_reordered_ticket_position_is_rejected() -> None:
    envelope = build_baseline_envelope()
    tickets = envelope["portfolios"][0]["tickets"]
    tickets[0], tickets[1] = tickets[1], tickets[0]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_TICKET_SHAPE_VIOLATION


def test_main_hit_mismatch_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["tickets"][0]["main_hit_count"] += 1
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_HIT_MISMATCH


def test_special_hit_mismatch_is_rejected() -> None:
    envelope = build_baseline_envelope()
    ticket = envelope["portfolios"][0]["tickets"][0]
    ticket["special_hit"] = not ticket["special_hit"]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_HIT_MISMATCH


def test_ticket_hash_mismatch_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["tickets"][0]["ticket_sha256"] = "2" * 64
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH


def test_portfolio_hash_mismatch_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["portfolio_sha256"] = "3" * 64
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH


def test_prefix10_hash_mismatch_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["prefix10_sha256"] = "4" * 64
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH


def test_prefix15_hash_mismatch_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["portfolios"][0]["prefix15_sha256"] = "5" * 64
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH
