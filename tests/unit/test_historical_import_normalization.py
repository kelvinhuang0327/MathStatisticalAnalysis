"""Adversarial tests for strict raw-JSON verification (BLHQ R1)."""

from __future__ import annotations

import copy
import json
from typing import Any

from tests.fixtures.historical.builder import (
    CUTOFF_DRAW_NUMBER,
    CUTOFF_MAIN_NUMBERS,
    CUTOFF_SPECIAL_NUMBERS,
    REAL_STRATEGY_IDS,
    build_baseline_envelope,
    build_draw_snapshot,
    build_small_envelope,
    deep_copy,
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


# Verification order for the two content-hash checks below (BLHQ R1 correction):
# import-identity hash, manifest hash, alias-target resolution, *then*
# independent strategy-descriptor content hash, *then* independent
# draw-snapshot content hash, before the per-portfolio loop. Placing the
# content-hash checks after alias-target resolution keeps
# ``test_alias_target_absent_is_rejected`` (which tampers with
# ``alias_of_strategy_id`` — a descriptor content field — without touching
# ``descriptor_sha256``) isolated to that one violation instead of tripping
# the new descriptor-hash check first.


def test_descriptor_content_tamper_with_stale_hash_is_rejected() -> None:
    """Test 1: a descriptor content field changes but ``descriptor_sha256`` is stale.

    ``recompute_envelope_hashes`` only refreshes the two root hashes, so the
    stale ``descriptor_sha256`` cannot be attributed to a merely-stale
    ``import_identity_sha256`` or ``manifest_sha256``.
    """

    envelope = build_baseline_envelope()
    tampered = envelope["strategy_descriptors"][2]
    assert tampered["strategy_id"] == "SYNTHETIC_BASE_A"
    tampered["governance_status"] = "REJECTED"
    envelope = recompute_envelope_hashes(envelope)
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH
    assert result.normalized_import is None


def test_cutoff_draw_content_tamper_with_stale_hash_is_rejected() -> None:
    """Test 2: the cutoff draw's content changes but ``draw_sha256`` is stale.

    Only the cutoff draw is touched; the target draw and every declared
    ticket hit stay exactly as built, so the failure isolates to the
    independent draw-content-hash check rather than a hit or causal check.
    """

    envelope = build_baseline_envelope()
    cutoff_draw = next(
        draw for draw in envelope["draw_snapshots"] if draw["draw_number"] == CUTOFF_DRAW_NUMBER
    )
    cutoff_draw["draw_date"] = "2026-01-02"
    envelope = recompute_envelope_hashes(envelope)
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH
    assert result.normalized_import is None


def test_explicit_json_null_is_rejected_and_distinguished_from_omission() -> None:
    """Test 3: an explicit JSON ``null`` is rejected; an omitted field is not.

    ``legacy_run_id`` is optional. The baseline envelope omits it entirely
    and passes. A hand-built raw payload that includes the key with a
    literal JSON ``null`` must fail differently: LCJ-1 canonical bytes
    forbid ``None`` outright, so ``canonical_bytes`` cannot be used to
    produce this input — the raw bytes are built with plain ``json.dumps``.
    """

    envelope = build_baseline_envelope()
    assert "legacy_run_id" not in envelope["source"]
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_PASS

    envelope_with_explicit_null = deep_copy(envelope)
    envelope_with_explicit_null["source"]["legacy_run_id"] = None
    raw_with_explicit_null = json.dumps(envelope_with_explicit_null).encode("utf-8")

    result = verify_and_normalize_historical_import(raw_with_explicit_null)
    assert result.outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED
    assert result.normalized_import is None


# --- BLHQ R1 R3 correction: import-identity/draw-content binding ---------------


def test_target_draw_main_numbers_tamper_with_stale_hash_is_rejected() -> None:
    envelope = build_baseline_envelope()
    target_draw = next(
        draw for draw in envelope["draw_snapshots"] if draw["draw_number"] != CUTOFF_DRAW_NUMBER
    )
    target_draw["main_numbers"][0] = 40
    envelope = recompute_envelope_hashes(envelope)
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH
    assert result.normalized_import is None


def test_target_draw_special_number_tamper_with_stale_hash_is_rejected() -> None:
    envelope = build_baseline_envelope()
    target_draw = next(
        draw for draw in envelope["draw_snapshots"] if draw["draw_number"] != CUTOFF_DRAW_NUMBER
    )
    target_draw["special_numbers"] = [41]
    envelope = recompute_envelope_hashes(envelope)
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_HASH_MISMATCH
    assert result.normalized_import is None


def test_repeated_normalization_of_same_envelope_is_deterministic() -> None:
    raw = envelope_bytes(build_baseline_envelope())
    first = verify_and_normalize_historical_import(raw)
    second = verify_and_normalize_historical_import(raw)
    assert first.outcome is HistoricalImportOutcome.IMPORT_PASS
    assert second.outcome is HistoricalImportOutcome.IMPORT_PASS
    assert first.normalized_import is not None
    assert second.normalized_import is not None
    assert (
        first.normalized_import.import_identity_sha256
        == second.normalized_import.import_identity_sha256
    )


# --- BLHQ R1 R3 correction: canonical ordering ---------------------------------


def test_reordered_draw_main_numbers_yield_identical_hash_and_identity() -> None:
    ascending = build_draw_snapshot(
        draw_number=CUTOFF_DRAW_NUMBER,
        draw_date="2026-01-01",
        main_numbers=CUTOFF_MAIN_NUMBERS,
        special_numbers=CUTOFF_SPECIAL_NUMBERS,
    )
    reordered = build_draw_snapshot(
        draw_number=CUTOFF_DRAW_NUMBER,
        draw_date="2026-01-01",
        main_numbers=tuple(reversed(CUTOFF_MAIN_NUMBERS)),
        special_numbers=CUTOFF_SPECIAL_NUMBERS,
    )
    assert ascending["draw_sha256"] == reordered["draw_sha256"]

    baseline_envelope = build_baseline_envelope()
    baseline_result = _verify(baseline_envelope)
    assert baseline_result.normalized_import is not None

    envelope = deep_copy(baseline_envelope)
    envelope["draw_snapshots"] = [
        reordered if draw["draw_number"] == CUTOFF_DRAW_NUMBER else draw
        for draw in envelope["draw_snapshots"]
    ]
    envelope = recompute_envelope_hashes(envelope)
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_PASS
    assert result.normalized_import is not None
    assert (
        result.normalized_import.import_identity_sha256
        == baseline_result.normalized_import.import_identity_sha256
    )
    normalized_cutoff = next(
        draw
        for draw in result.normalized_import.draw_snapshots
        if draw.draw_number == CUTOFF_DRAW_NUMBER
    )
    assert normalized_cutoff.main_numbers == tuple(sorted(CUTOFF_MAIN_NUMBERS))


def test_reordered_ticket_main_numbers_normalize_to_canonical_domain_order() -> None:
    envelope = build_baseline_envelope()
    ticket = envelope["portfolios"][0]["tickets"][0]
    original_main = list(ticket["main_numbers"])
    ticket["main_numbers"] = list(reversed(original_main))
    envelope = recompute_envelope_hashes(envelope)
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_PASS
    assert result.normalized_import is not None
    normalized_ticket = result.normalized_import.portfolios[0].tickets[0]
    assert normalized_ticket.main_numbers == tuple(sorted(original_main))
    assert normalized_ticket.portfolio_position == 1


# --- BLHQ R1 R3 correction: calendar-valid canonical date contract -------------


def test_non_date_string_draw_date_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["draw_date"] = "not-a-date"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_invalid_month_and_day_draw_date_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["draw_date"] = "2026-99-99"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_impossible_calendar_date_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["draw_date"] = "2026-02-30"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_noncanonical_timestamp_draw_date_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["draw_date"] = "2026-01-01T00:00:00Z"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_non_leap_year_february_29_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["draw_date"] = "2026-02-29"
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_leap_day_draw_date_is_accepted() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"] = [
        build_draw_snapshot(
            draw_number=CUTOFF_DRAW_NUMBER,
            draw_date="2024-02-29",
            main_numbers=CUTOFF_MAIN_NUMBERS,
            special_numbers=CUTOFF_SPECIAL_NUMBERS,
        )
        if draw["draw_number"] == CUTOFF_DRAW_NUMBER
        else draw
        for draw in envelope["draw_snapshots"]
    ]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_PASS


def test_valid_canonical_draw_date_is_preserved() -> None:
    envelope = build_baseline_envelope()
    result = _verify(envelope)
    assert result.outcome is HistoricalImportOutcome.IMPORT_PASS
    assert result.normalized_import is not None
    assert {draw.draw_date for draw in result.normalized_import.draw_snapshots} == {
        "2026-01-01",
        "2026-01-10",
    }


# --- BLHQ R1 R3 correction: BIG_LOTTO draw-number invariants -------------------


def test_draw_with_five_main_numbers_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["main_numbers"] = envelope["draw_snapshots"][0]["main_numbers"][
        :5
    ]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_seven_main_numbers_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["main_numbers"].append(48)
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_duplicate_main_number_is_rejected() -> None:
    envelope = build_baseline_envelope()
    draw = envelope["draw_snapshots"][0]
    draw["main_numbers"][1] = draw["main_numbers"][0]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_main_number_below_range_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["main_numbers"][0] = 0
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_main_number_above_range_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["main_numbers"][0] = 50
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_zero_special_numbers_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["special_numbers"] = []
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_two_special_numbers_is_rejected() -> None:
    envelope = build_baseline_envelope()
    draw = envelope["draw_snapshots"][0]
    draw["special_numbers"] = [draw["special_numbers"][0], 40]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_special_number_below_range_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["special_numbers"] = [0]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_special_number_above_range_is_rejected() -> None:
    envelope = build_baseline_envelope()
    envelope["draw_snapshots"][0]["special_numbers"] = [50]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_draw_with_main_special_overlap_is_rejected() -> None:
    envelope = build_baseline_envelope()
    draw = envelope["draw_snapshots"][0]
    draw["special_numbers"] = [draw["main_numbers"][0]]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


# --- BLHQ R1 R3 correction: BIG_LOTTO ticket main-number invariants ------------


def test_ticket_with_wrong_main_number_count_is_rejected() -> None:
    envelope = build_baseline_envelope()
    ticket = envelope["portfolios"][0]["tickets"][0]
    ticket["main_numbers"] = ticket["main_numbers"][:5]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_ticket_with_duplicate_main_number_is_rejected() -> None:
    envelope = build_baseline_envelope()
    ticket = envelope["portfolios"][0]["tickets"][0]
    ticket["main_numbers"][1] = ticket["main_numbers"][0]
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED


def test_ticket_with_out_of_range_main_number_is_rejected() -> None:
    envelope = build_baseline_envelope()
    ticket = envelope["portfolios"][0]["tickets"][0]
    ticket["main_numbers"][0] = 50
    envelope = recompute_envelope_hashes(envelope)
    assert _verify(envelope).outcome is HistoricalImportOutcome.IMPORT_INPUT_UNVERIFIED
