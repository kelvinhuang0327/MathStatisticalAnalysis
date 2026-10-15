"""Branch6 correctness checks. Every successful example is SYNTHETIC_FIXTURE.

No fixture or mock receipt establishes a real historical paired draw.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.research import b649_branch6_forward_paired_any_prize_r1 as evaluator

Row = dict[str, object]


def _nested(row: Row, field: str) -> Row:
    return cast(Row, row[field])


def _freeze(row: Row) -> None:
    row["frozen_artifact_bytes"] = evaluator.canonical_frozen_artifact_bytes(row)
    digest = evaluator.frozen_artifact_sha256(row)
    row["frozen_artifact_sha256"] = digest
    _nested(row, "pre_draw_capture_evidence")["artifact_sha256"] = digest


def _inputs(count: int = 2, draw: str = "SYNTHETIC-FIXTURE-DRAW-1") -> tuple[Row, Row]:
    row, official = evaluator.synthetic_launch_inputs()
    losing = tuple(itertools.islice(itertools.combinations(range(20, 32), 6), count))
    row.update(draw_id=draw, ticket_count=count)
    row["candidate_portfolio"] = ((1, 2, 7, 8, 9, 10), *losing[: count - 1])
    _nested(row, "same_count_baseline").update(draw_id=draw, ticket_count=count, portfolio=losing)
    official["official_draw_id"] = draw
    _freeze(row)
    return row, official


def _synthetic(row: Row, official: Row) -> evaluator.EvaluationReport:
    return evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )


def _rejected(report: evaluator.EvaluationReport, code: str) -> None:
    assert report.validation_status == "INVALID_INPUT"
    assert report.valid_paired_draw_count == 0
    assert report.valid_real_paired_draws == 0
    assert report.same_count_observed_lift == evaluator.NOT_ESTABLISHED
    assert report.observed_success_gain == evaluator.NOT_ESTABLISHED
    assert report.future_predictive_gain == evaluator.NOT_ESTABLISHED
    assert report.ranking_comparability == evaluator.NOT_COMPARABLE
    assert not report.in_sample_buckets
    assert not report.out_of_sample_buckets
    assert any(code in rejection.codes for rejection in report.leakage_disposition.rejections)


def _verified_fixture(row: Row, official: Row) -> evaluator.VerifiedExternalAttestation:
    evidence = _nested(row, "pre_draw_capture_evidence")
    return evaluator.VerifiedExternalAttestation(
        artifact_sha256=cast(str, row["frozen_artifact_sha256"]),
        draw_id=cast(str, row["draw_id"]),
        captured_at=cast(datetime, evidence["captured_at"]),
        prediction_cutoff=cast(datetime, row["prediction_cutoff"]),
        capture_locator=cast(str, evidence["capture_locator"]),
        source_identity="SYNTHETIC-MOCK-AUTHORITY-NOT-REAL-EVIDENCE",
        source_sha256=hashlib.sha256(b"synthetic authenticated receipt fixture").hexdigest(),
        provenance=evaluator.SYNTHETIC_FIXTURE,
        official_draw_source_identity=cast(str, official["official_draw_source_identity"]),
        official_result_available_at=cast(datetime, official["official_result_available_at"]),
        legal_pre_draw_information_cutoff=cast(
            datetime, official["legal_pre_draw_information_cutoff"]
        ),
    )


def _adapter(
    record: evaluator.VerifiedExternalAttestation,
) -> evaluator.AttestationVerifier:
    def verify(
        evidence: evaluator.PreDrawCaptureEvidence, frozen_bytes: bytes
    ) -> evaluator.VerifiedExternalAttestation:
        assert evidence.capture_locator == record.capture_locator
        assert hashlib.sha256(frozen_bytes).hexdigest() == record.artifact_sha256
        return record

    return verify


@pytest.mark.parametrize("count", evaluator.SUPPORTED_TICKET_COUNTS)
def test_all_ticket_counts_use_same_official_evaluator(count: int) -> None:
    row, official = _inputs(count)
    report = _synthetic(row, official)
    assert report.validation_status == "VALID"
    assert report.valid_paired_draw_count == 1
    assert report.valid_real_paired_draws == 0
    assert report.observed_success_gain == evaluator.NOT_ESTABLISHED
    assert report.leakage_disposition.admitted_synthetic_pair_count == 1
    bucket = report.out_of_sample_buckets[0]
    assert (bucket.ticket_count, bucket.stake, bucket.same_count_observed_lift) == (
        count,
        count,
        "1/1",
    )
    record = bucket.records[0]
    assert record.candidate_observed_official_any_prize is True  # 2 mains + special.
    assert record.baseline_observed_official_any_prize is False
    assert record.paired_indicator_difference == 1
    assert len(record.candidate_portfolio) == len(record.baseline_portfolio) == count
    assert record.frozen_artifact_sha256 == row["frozen_artifact_sha256"]
    assert report.predictive_gain == report.future_predictive_gain == evaluator.NOT_ESTABLISHED


def test_no_real_data_and_no_invented_inference() -> None:
    report = evaluator.evaluate_paired_any_prize([], [])
    text = evaluator.render_evaluation_report(report)
    assert report.valid_paired_draw_count == 0
    assert report.sample_uncertainty == evaluator.NOT_ESTABLISHED
    assert report.significance_claim == evaluator.SIGNIFICANCE_NOT_CLAIMED
    assert "VALID_REAL_PAIRED_DRAWS=0\n" in text
    assert "OBSERVED_SUCCESS_GAIN=NOT_ESTABLISHED\n" in text
    assert "FUTURE_PREDICTIVE_GAIN=NOT_ESTABLISHED\n" in text
    assert "p_value" not in text and "confidence_interval" not in text
    assert not report.in_sample_buckets and not report.out_of_sample_buckets


def test_synthetic_cannot_enter_default_real_report() -> None:
    row, official = _inputs()
    _rejected(
        evaluator.evaluate_paired_any_prize([row], [official]), "SYNTHETIC_EXCLUDED_FROM_REAL"
    )


def test_self_declared_external_attestation_and_forged_time_are_not_proof() -> None:
    row, official = _inputs()
    # Counterfeit claims are submitted only to demonstrate rejection; never a
    # successful real report. Even all old syntactic checks passing is no proof.
    row["provenance"] = official["provenance"] = evaluator.REAL_PREDRAW_ARTIFACT
    row["prediction_generated_at"] = datetime(1990, 1, 1, tzinfo=UTC)
    _nested(row, "pre_draw_capture_evidence")["captured_at"] = datetime(1991, 1, 1, tzinfo=UTC)
    _freeze(row)
    _rejected(
        evaluator.evaluate_paired_any_prize([row], [official]), "MISSING_INDEPENDENT_VERIFIER"
    )


def test_mock_receipt_cannot_be_promoted_to_real() -> None:
    row, official = _inputs()
    verified = _verified_fixture(row, official)
    row["provenance"] = official["provenance"] = evaluator.REAL_PREDRAW_ARTIFACT
    _freeze(row)
    verified = replace(verified, artifact_sha256=cast(str, row["frozen_artifact_sha256"]))
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], attestation_verifier=_adapter(verified)
    )
    _rejected(report, "ATTESTATION_BINDING_MISMATCH")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("frozen_artifact_sha256", "0" * 64, "SHA256_MISMATCH"),
        ("frozen_artifact_sha256", "not-a-digest", "DAMAGED_SHA256"),
        ("frozen_artifact_bytes", b"modified prediction bytes", "FROZEN_BYTES_MISMATCH"),
        ("frozen_artifact_bytes", None, "FROZEN_BYTES_MISMATCH"),
        ("pre_draw_capture_evidence", None, "MISSING_FREEZE_EVIDENCE"),
        ("ticket_count", 4, "UNSUPPORTED_TICKET_COUNT"),
        ("ticket_count", True, "UNSUPPORTED_TICKET_COUNT"),
        ("candidate_portfolio", ((1, 2, 3, 4, 5, 6),), "CANDIDATE_TICKET_COUNT_MISMATCH"),
        ("candidate_portfolio", None, "CANDIDATE_TICKET_COUNT_MISMATCH"),
        ("ranking_version", "", "MISSING_RANKING_IDENTITY"),
        ("ranking_algorithm_id", "", "MISSING_RANKING_IDENTITY"),
        ("tie_order", "SELECT_BEST_AFTER_DRAW", "INVALID_TIE_ORDER"),
        ("tie_order", None, "INVALID_TIE_ORDER"),
        ("prediction_cutoff", None, "MISSING_CUTOFF"),
        ("prediction_cutoff", datetime(2026, 1, 1), "NAIVE_DATETIME"),
        ("sample_scope", "UNKNOWN", "INVALID_SAMPLE_SCOPE"),
        ("provenance", "UNKNOWN", "UNTRUSTED_PROVENANCE"),
    ],
)
def test_invalid_snapshot_fails_closed(field: str, value: object, code: str) -> None:
    row, official = _inputs()
    row[field] = value
    _rejected(_synthetic(row, official), code)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("evidence_kind", evaluator.GENERATED_AT_ONLY, "GENERATED_AT_ONLY"),
        ("evidence_kind", "LOCAL_JSON_ASSERTION", "UNTRUSTED_FREEZE_EVIDENCE"),
        ("artifact_sha256", "0" * 64, "SHA256_MISMATCH"),
        ("capture_locator", "", "UNTRUSTED_FREEZE_EVIDENCE"),
        ("captured_at", None, "UNTRUSTED_FREEZE_EVIDENCE"),
        ("captured_at", datetime(2026, 1, 1, 13, tzinfo=UTC), "LATE_CAPTURE"),
        ("captured_at", datetime(2026, 1, 1, 20, tzinfo=UTC), "LATE_CAPTURE"),
        ("captured_at", datetime(2026, 1, 1, 11), "NAIVE_DATETIME"),
    ],
)
def test_invalid_attestation_claim_fails_closed(field: str, value: object, code: str) -> None:
    row, official = _inputs()
    _nested(row, "pre_draw_capture_evidence")[field] = value
    _rejected(_synthetic(row, official), code)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("ticket_count", 3, "WRONG_COUNT_BASELINE"),
        ("portfolio", ((20, 21, 22, 23, 24, 25),), "WRONG_BUDGET_BASELINE"),
        ("draw_id", "OTHER-DRAW", "BASELINE_DRAW_MISMATCH"),
        ("prediction_cutoff", datetime(2026, 1, 1, 11, tzinfo=UTC), "BASELINE_CUTOFF_MISMATCH"),
        ("draw_id", None, "MALFORMED_BASELINE"),
    ],
)
def test_baseline_must_have_same_draw_cutoff_and_budget(
    field: str, value: object, code: str
) -> None:
    row, official = _inputs()
    _nested(row, "same_count_baseline")[field] = value
    _rejected(_synthetic(row, official), code)


@pytest.mark.parametrize("hour", [13, 20, 21])
def test_late_cutoff_is_rejected_even_with_recomputed_digest(hour: int) -> None:
    row, official = _inputs()
    cutoff = datetime(2026, 1, 1, hour, tzinfo=UTC)
    row["prediction_cutoff"] = _nested(row, "same_count_baseline")["prediction_cutoff"] = cutoff
    _freeze(row)
    report = _synthetic(row, official)
    _rejected(report, "LATE_CUTOFF")
    if hour >= 20:
        _rejected(report, "CUTOFF_NOT_BEFORE_RESULT")


def test_capture_must_be_by_prediction_cutoff_not_just_draw_cutoff() -> None:
    row, official = _inputs()
    official["legal_pre_draw_information_cutoff"] = datetime(2026, 1, 1, 13, tzinfo=UTC)
    _nested(row, "pre_draw_capture_evidence")["captured_at"] = datetime(
        2026, 1, 1, 12, 30, tzinfo=UTC
    )
    _rejected(_synthetic(row, official), "LATE_CAPTURE")


def test_generated_time_after_capture_is_inconsistent() -> None:
    row, official = _inputs()
    row["prediction_generated_at"] = datetime(2026, 1, 1, 12, tzinfo=UTC)
    _rejected(_synthetic(row, official), "GENERATED_AFTER_CAPTURE")


def test_modified_frozen_bytes_are_detected_even_when_decoded_json_is_identical() -> None:
    row, official = _inputs()
    frozen_bytes = cast(bytes, row["frozen_artifact_bytes"])
    row["frozen_artifact_bytes"] = frozen_bytes + b"\n"
    assert json.loads(frozen_bytes) == json.loads(row["frozen_artifact_bytes"])
    _rejected(_synthetic(row, official), "FROZEN_BYTES_MISMATCH")


def test_post_draw_portfolio_or_ranking_switch_cannot_use_old_receipt() -> None:
    row, official = _inputs()
    row["candidate_portfolio"] = ((1, 2, 3, 4, 5, 6), (20, 21, 22, 23, 24, 25))
    row["ranking_version"] = "selected-after-draw"
    _rejected(_synthetic(row, official), "SHA256_MISMATCH")


@pytest.mark.parametrize("scope", [evaluator.IN_SAMPLE, evaluator.OUT_OF_SAMPLE])
def test_duplicate_draw_in_any_scope_is_rejected(scope: str) -> None:
    row, official = _inputs()
    other = deepcopy(row)
    other["sample_scope"] = scope
    _freeze(other)
    report = evaluator.evaluate_paired_any_prize(
        [row, other], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "DUPLICATE_DRAW")


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_official_results_are_rejected(conflicting: bool) -> None:
    row, official = _inputs()
    duplicate = deepcopy(official)
    if conflicting:
        duplicate["winning_special_number"] = 8
    report = evaluator.evaluate_paired_any_prize(
        [row], [official, duplicate], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "AMBIGUOUS_OFFICIAL_RESULT")


def test_draw_identity_must_match_exactly() -> None:
    row, official = _inputs()
    official["official_draw_id"] = "OTHER-DRAW"
    _rejected(_synthetic(row, official), "MISSING_OFFICIAL_RESULT")


@pytest.mark.parametrize(
    "ticket",
    [(1, 1, 2, 3, 4, 5), (0, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 50), (1, 2, 3, 4, 5)],
)
def test_illegal_ticket_cannot_be_scored(ticket: tuple[int, ...]) -> None:
    row, official = _inputs()
    row["candidate_portfolio"] = ((20, 21, 22, 23, 24, 25), ticket)
    _freeze(row)
    _rejected(_synthetic(row, official), "ILLEGAL_TICKET")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("winning_main_numbers", (1, 1, 2, 3, 4, 5), "ILLEGAL_OFFICIAL_DRAW"),
        ("winning_special_number", 1, "ILLEGAL_OFFICIAL_DRAW"),
        ("winning_special_number", 50, "ILLEGAL_OFFICIAL_DRAW"),
        ("official_result_available_at", None, "MISSING_OFFICIAL_RESULT"),
        ("legal_pre_draw_information_cutoff", None, "MISSING_LEGAL_INFORMATION_CUTOFF"),
        ("official_draw_source_identity", "", "MISSING_SOURCE_IDENTITY"),
        ("provenance", evaluator.REAL_PREDRAW_ARTIFACT, "REAL_EXCLUDED_FROM_SYNTHETIC"),
    ],
)
def test_bad_official_result_fails_closed(field: str, value: object, code: str) -> None:
    row, official = _inputs()
    official[field] = value
    _rejected(_synthetic(row, official), code)


def test_any_invalid_row_prevents_lift_from_a_selected_valid_subset() -> None:
    row, official = _inputs()
    bad, bad_official = _inputs(draw="SYNTHETIC-BAD")
    bad["frozen_artifact_sha256"] = "0" * 64
    report = evaluator.evaluate_paired_any_prize(
        [row, bad], [official, bad_official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "SHA256_MISMATCH")
    assert report.leakage_disposition.admitted_synthetic_pair_count == 0


def test_unmatched_malformed_official_row_is_not_silently_dropped() -> None:
    row, official = _inputs()
    report = evaluator.evaluate_paired_any_prize(
        [row], [official, {}], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "MALFORMED_OFFICIAL_RESULT")


def test_independent_adapter_bindings_and_audit_identity_with_fixture_label() -> None:
    row, official = _inputs()
    verified = _verified_fixture(row, official)
    report = evaluator.evaluate_paired_any_prize(
        [row],
        [official],
        report_label=evaluator.SYNTHETIC_FIXTURE,
        attestation_verifier=_adapter(verified),
    )
    assert report.valid_paired_draw_count == 1
    assert report.valid_real_paired_draws == 0
    record = report.out_of_sample_buckets[0].records[0]
    assert record.attestation_source_sha256 == verified.source_sha256
    assert verified.source_identity in evaluator.render_evaluation_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_sha256", "0" * 64),
        ("draw_id", "OTHER-DRAW"),
        ("captured_at", datetime(2026, 1, 1, 10, tzinfo=UTC)),
        ("prediction_cutoff", datetime(2026, 1, 1, 10, tzinfo=UTC)),
        ("capture_locator", "forged-source"),
        ("source_identity", ""),
        ("source_sha256", "bad-digest"),
        ("provenance", evaluator.REAL_PREDRAW_ARTIFACT),
        ("official_draw_source_identity", "another-official-source"),
        ("official_result_available_at", datetime(2026, 1, 1, 21, tzinfo=UTC)),
        ("legal_pre_draw_information_cutoff", datetime(2026, 1, 1, 13, tzinfo=UTC)),
    ],
)
def test_verified_response_must_bind_every_claim(field: str, value: object) -> None:
    row, official = _inputs()
    verified = replace(_verified_fixture(row, official), **{field: value})
    # Do not assert bad bindings in the mock itself: the evaluator must catch them.
    report = evaluator.evaluate_paired_any_prize(
        [row],
        [official],
        report_label=evaluator.SYNTHETIC_FIXTURE,
        attestation_verifier=lambda _e, _b: verified,
    )
    _rejected(report, "ATTESTATION_BINDING_MISMATCH")


@pytest.mark.parametrize("mode", ["denied", "exception", "json", "naive"])
def test_verifier_failure_or_untyped_json_cannot_authorize(mode: str) -> None:
    row, official = _inputs()

    def verify(
        _evidence: evaluator.PreDrawCaptureEvidence, _frozen_bytes: bytes
    ) -> evaluator.VerifiedExternalAttestation | None:
        if mode == "exception":
            raise OSError("independent evidence source unavailable")
        if mode == "json":
            return cast(evaluator.VerifiedExternalAttestation, {"trusted": True})
        if mode == "naive":
            return replace(_verified_fixture(row, official), captured_at=datetime(2026, 1, 1))
        return None

    report = evaluator.evaluate_paired_any_prize(
        [row],
        [official],
        report_label=evaluator.SYNTHETIC_FIXTURE,
        attestation_verifier=verify,
    )
    _rejected(report, "UNTRUSTED_FREEZE_EVIDENCE")


@pytest.mark.parametrize(
    ("main_hits", "special"),
    [(hits, special) for hits in range(7) for special in (False, True) if hits + special <= 6],
)
def test_existing_official_prize_rules_cover_every_legal_hit_signature(
    main_hits: int, special: bool
) -> None:
    ticket = (*range(1, main_hits + 1), *((7,) if special else ()))
    ticket += tuple(range(20, 20 + 6 - len(ticket)))
    expected = main_hits >= 3 or (main_hits == 2 and special)
    assert evaluator.observed_official_any_prize([ticket], (1, 2, 3, 4, 5, 6), 7) is expected


def test_public_scorer_validates_later_tickets_after_a_winner() -> None:
    with pytest.raises(ValueError):
        evaluator.observed_official_any_prize(
            [(1, 2, 3, 4, 5, 6), (40, 41, 42, 43, 44, 50)], (1, 2, 3, 4, 5, 6), 7
        )


def test_theoretical_coverage_does_not_create_an_observed_win() -> None:
    row, official = _inputs()
    row["candidate_portfolio"] = _nested(row, "same_count_baseline")["portfolio"]
    _freeze(row)
    report = _synthetic(row, official)
    record = report.out_of_sample_buckets[0].records[0]
    assert record.theoretical_uniform_any_prize_coverage != "0/1"
    assert record.candidate_observed_official_any_prize is False
    assert report.out_of_sample_buckets[0].same_count_observed_lift == "0/1"


def test_frozen_identity_includes_selection_and_excludes_generated_time() -> None:
    row, official = _inputs()
    original = evaluator.frozen_artifact_sha256(row)
    row["prediction_generated_at"] = datetime(1980, 1, 1, tzinfo=UTC)
    assert evaluator.frozen_artifact_sha256(row) == original
    for field, value in (
        ("ranking_version", "other-version"),
        ("sample_scope", evaluator.IN_SAMPLE),
        ("provenance", evaluator.REAL_PREDRAW_ARTIFACT),
    ):
        changed = deepcopy(row)
        changed[field] = value
        assert evaluator.frozen_artifact_sha256(changed) != original
    assert _synthetic(row, official).valid_paired_draw_count == 1
    payload = json.loads(evaluator.canonical_frozen_artifact_bytes(row))
    assert "winning_main_numbers" not in payload
    assert "prediction_generated_at" not in payload
    assert payload["tie_order"] == evaluator.TIE_ORDER_LEXICOGRAPHIC


def test_fixed_replay_is_deterministic_and_does_not_mutate_inputs() -> None:
    row, official = _inputs()
    saved = deepcopy((row, official))
    first = _synthetic(row, official)
    second = _synthetic(row, official)
    assert first == second
    assert (
        evaluator.render_evaluation_report(first).encode()
        == evaluator.render_evaluation_report(second).encode()
    )
    assert (row, official) == saved
    reversed_row = deepcopy(row)
    reversed_row["candidate_portfolio"] = tuple(
        reversed(cast(tuple[tuple[int, ...], ...], row["candidate_portfolio"]))
    )
    assert evaluator.canonical_frozen_artifact_bytes(reversed_row) == row["frozen_artifact_bytes"]
    assert _synthetic(reversed_row, official) == first
    # Golden replay pins actual bytes and complete output, not just two calls
    # to the same implementation. These are exclusively synthetic observations.
    assert row["frozen_artifact_sha256"] == (
        "e697d51a9cf87f628388ede6032083ac79eda628e808718914ac8dcf15c495ef"
    )
    assert hashlib.sha256(evaluator.render_evaluation_report(first).encode()).hexdigest() == (
        "a5281cecce85bbb783cd96ca9df9edc813dd2a21320e3545848e20558c415174"
    )


def test_equivalent_timezones_do_not_change_frozen_identity() -> None:
    row, official = _inputs()
    cutoff = cast(datetime, row["prediction_cutoff"])
    row["prediction_cutoff"] = cutoff.astimezone(timezone(timedelta(hours=8)))
    _nested(row, "same_count_baseline")["prediction_cutoff"] = row["prediction_cutoff"]
    assert _synthetic(row, official).valid_paired_draw_count == 1


def test_same_draw_across_budgets_stays_in_separate_descriptive_buckets() -> None:
    pairs = [_inputs(count) for count in evaluator.SUPPORTED_TICKET_COUNTS]
    report = evaluator.evaluate_paired_any_prize(
        [pair[0] for pair in pairs], [pairs[0][1]], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    assert [bucket.ticket_count for bucket in report.out_of_sample_buckets] == [2, 3, 5, 10, 20]
    assert report.valid_real_paired_draws == 0
    assert report.observed_success_gain == evaluator.NOT_ESTABLISHED
    assert "cross_count_comparison_is_not_ranking_skill=true" in report.cross_count_lines
    assert all(bucket.valid_paired_draw_count == 1 for bucket in report.out_of_sample_buckets)


def test_in_and_out_of_sample_are_not_pooled() -> None:
    row, official = _inputs()
    other, other_official = _inputs(draw="SYNTHETIC-IN-SAMPLE")
    other["sample_scope"] = evaluator.IN_SAMPLE
    _freeze(other)
    report = evaluator.evaluate_paired_any_prize(
        [row, other], [official, other_official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    assert report.valid_paired_draw_count == 2
    assert len(report.in_sample_buckets) == len(report.out_of_sample_buckets) == 1


def test_exact_existing_official_rule_identity() -> None:
    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
    assert prize_rule is not None
    assert evaluator.official_prize_rule_identity() == "BIG_LOTTO:2026-07-16.1:prize_schema:1.0.0"
    assert prize_rule.source_sha256 == (
        "397639210969faba3002ffbd309dba10c44ead2063dd51ed47def98624994c15"
    )


def test_unknown_label_is_an_explicit_error() -> None:
    with pytest.raises(ValueError, match="unsupported report_label"):
        evaluator.evaluate_paired_any_prize([], [], report_label="UNKNOWN")


@pytest.mark.parametrize("candidate_wins", [False, True])
@pytest.mark.parametrize("baseline_wins", [False, True])
def test_paired_indicator_all_four_outcomes(candidate_wins: bool, baseline_wins: bool) -> None:
    row, official = _inputs()
    winning = row["candidate_portfolio"]
    losing = _nested(row, "same_count_baseline")["portfolio"]
    row["candidate_portfolio"] = winning if candidate_wins else losing
    _nested(row, "same_count_baseline")["portfolio"] = winning if baseline_wins else losing
    _freeze(row)
    record = _synthetic(row, official).out_of_sample_buckets[0].records[0]
    assert record.paired_indicator_difference == int(candidate_wins) - int(baseline_wins)


# ---------------------------------------------------------------------------
# Section VI Mandatory Fail-Closed Negative Tests (directly hitting evaluate_paired_any_prize)
# ---------------------------------------------------------------------------


def test_negative_case_01_caller_always_true_verifier_fails_closed() -> None:
    row, official = _inputs()
    row["provenance"] = official["provenance"] = evaluator.REAL_PREDRAW_ARTIFACT
    _freeze(row)
    verified = _verified_fixture(row, official)
    verified = replace(
        verified,
        artifact_sha256=cast(str, row["frozen_artifact_sha256"]),
        provenance=evaluator.REAL_PREDRAW_ARTIFACT,
    )
    report = evaluator.evaluate_paired_any_prize(
        [row],
        [official],
        report_label=evaluator.REAL_OBSERVED,
        attestation_verifier=lambda _e, _b: verified,
    )
    _rejected(report, "MISSING_INDEPENDENT_VERIFIER")
    assert report.valid_real_paired_draws == 0
    assert report.observed_success_gain == evaluator.NOT_ESTABLISHED


def test_negative_case_02_caller_self_generated_attestation_rejected() -> None:
    row, official = _inputs()
    row["provenance"] = official["provenance"] = evaluator.REAL_PREDRAW_ARTIFACT
    row["prediction_generated_at"] = datetime(2026, 1, 1, 11, tzinfo=UTC)
    _nested(row, "pre_draw_capture_evidence")["captured_at"] = datetime(
        2026, 1, 1, 11, 30, tzinfo=UTC
    )
    _freeze(row)
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.REAL_OBSERVED
    )
    _rejected(report, "MISSING_INDEPENDENT_VERIFIER")
    assert report.valid_real_paired_draws == 0
    assert report.observed_success_gain == evaluator.NOT_ESTABLISHED


def test_negative_case_03_synthetic_labeled_real_observed_rejected() -> None:
    row, official = _inputs()
    row["provenance"] = official["provenance"] = evaluator.SYNTHETIC_FIXTURE
    _freeze(row)
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.REAL_OBSERVED
    )
    _rejected(report, "SYNTHETIC_EXCLUDED_FROM_REAL")
    assert report.valid_real_paired_draws == 0


def test_negative_case_04_false_predraw_timestamp_rejected() -> None:
    row, official = _inputs()
    row["prediction_cutoff"] = _nested(row, "same_count_baseline")["prediction_cutoff"] = datetime(
        2026, 1, 1, 21, tzinfo=UTC
    )
    _freeze(row)
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "LATE_CUTOFF")
    _rejected(report, "CUTOFF_NOT_BEFORE_RESULT")


def test_negative_case_05_wrong_artifact_sha256_rejected() -> None:
    row, official = _inputs()
    row["frozen_artifact_sha256"] = "f" * 64
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "SHA256_MISMATCH")


def test_negative_case_06_frozen_bytes_replacement_rejected() -> None:
    row, official = _inputs()
    row["frozen_artifact_bytes"] = b"tampered frozen bytes replacement"
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "FROZEN_BYTES_MISMATCH")


def test_negative_case_07_draw_id_mismatch_rejected() -> None:
    row, official = _inputs()
    _nested(row, "same_count_baseline")["draw_id"] = "MISMATCHED-DRAW-ID"
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "BASELINE_DRAW_MISMATCH")


def test_negative_case_08_cutoff_mismatch_rejected() -> None:
    row, official = _inputs()
    _nested(row, "same_count_baseline")["prediction_cutoff"] = datetime(2026, 1, 1, 10, tzinfo=UTC)
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "BASELINE_CUTOFF_MISMATCH")


def test_negative_case_09_duplicate_draw_rejected() -> None:
    row, official = _inputs()
    duplicate = deepcopy(row)
    report = evaluator.evaluate_paired_any_prize(
        [row, duplicate], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "DUPLICATE_DRAW")


def test_negative_case_10_ticket_count_mismatch_rejected() -> None:
    row, official = _inputs()
    row["candidate_portfolio"] = ((1, 2, 3, 4, 5, 6),)  # 1 ticket instead of count=2
    _freeze(row)
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "CANDIDATE_TICKET_COUNT_MISMATCH")


def test_negative_case_11_budget_mismatch_rejected() -> None:
    row, official = _inputs()
    _nested(row, "same_count_baseline")["portfolio"] = ((20, 21, 22, 23, 24, 25),)
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "WRONG_BUDGET_BASELINE")


def test_negative_case_12_time_order_violation_rejected() -> None:
    row, official = _inputs()
    row["prediction_generated_at"] = datetime(2026, 1, 1, 12, tzinfo=UTC)
    _nested(row, "pre_draw_capture_evidence")["captured_at"] = datetime(2026, 1, 1, 11, tzinfo=UTC)
    report = evaluator.evaluate_paired_any_prize(
        [row], [official], report_label=evaluator.SYNTHETIC_FIXTURE
    )
    _rejected(report, "GENERATED_AFTER_CAPTURE")


def test_negative_case_13_reproduced_attack_fabricated_1_1_gain_rejected() -> None:
    row, official = _inputs()
    row["provenance"] = official["provenance"] = evaluator.REAL_PREDRAW_ARTIFACT
    row["candidate_portfolio"] = ((1, 2, 7, 8, 9, 10), (20, 21, 22, 23, 24, 25))
    _freeze(row)
    digest = cast(str, row["frozen_artifact_sha256"])
    evidence = _nested(row, "pre_draw_capture_evidence")

    verified = evaluator.VerifiedExternalAttestation(
        artifact_sha256=digest,
        draw_id=cast(str, row["draw_id"]),
        captured_at=cast(datetime, evidence["captured_at"]),
        prediction_cutoff=cast(datetime, row["prediction_cutoff"]),
        capture_locator=cast(str, evidence["capture_locator"]),
        source_identity="ATTACKER-MOCK-AUTHORITY",
        source_sha256=hashlib.sha256(b"fake receipt").hexdigest(),
        provenance=evaluator.REAL_PREDRAW_ARTIFACT,
        official_draw_source_identity=cast(str, official["official_draw_source_identity"]),
        official_result_available_at=cast(datetime, official["official_result_available_at"]),
        legal_pre_draw_information_cutoff=cast(
            datetime, official["legal_pre_draw_information_cutoff"]
        ),
    )

    report = evaluator.evaluate_paired_any_prize(
        [row],
        [official],
        report_label=evaluator.REAL_OBSERVED,
        attestation_verifier=lambda _e, _b: verified,
    )
    _rejected(report, "MISSING_INDEPENDENT_VERIFIER")
    _rejected(report, "UNTRUSTED_FREEZE_EVIDENCE")
    assert report.validation_status == "INVALID_INPUT"
    assert report.valid_real_paired_draws == 0
    assert report.valid_paired_draw_count == 0
    assert report.observed_success_gain == evaluator.NOT_ESTABLISHED
    assert report.future_predictive_gain == evaluator.NOT_ESTABLISHED


def test_negative_case_14_no_real_sample_reports_observed_gain_not_established() -> None:
    report = evaluator.evaluate_paired_any_prize([], [], report_label=evaluator.REAL_OBSERVED)
    assert report.valid_real_paired_draws == 0
    assert report.observed_success_gain == evaluator.NOT_ESTABLISHED
    assert report.future_predictive_gain == evaluator.NOT_ESTABLISHED
    rendered = evaluator.render_evaluation_report(report)
    assert "VALID_REAL_PAIRED_DRAWS=0\n" in rendered
    assert "OBSERVED_SUCCESS_GAIN=NOT_ESTABLISHED\n" in rendered
    assert "FUTURE_PREDICTIVE_GAIN=NOT_ESTABLISHED\n" in rendered


def test_negative_case_15_caller_substitutes_trust_root_rejected() -> None:
    row, official = _inputs()
    row["provenance"] = official["provenance"] = evaluator.REAL_PREDRAW_ARTIFACT
    _freeze(row)
    verified = replace(
        _verified_fixture(row, official),
        source_identity="CALLER-SUPPLIED-ROOT-AUTHORITY",
        provenance=evaluator.REAL_PREDRAW_ARTIFACT,
        artifact_sha256=cast(str, row["frozen_artifact_sha256"]),
    )
    report = evaluator.evaluate_paired_any_prize(
        [row],
        [official],
        report_label=evaluator.REAL_OBSERVED,
        attestation_verifier=lambda _e, _b: verified,
    )
    _rejected(report, "UNTRUSTED_FREEZE_EVIDENCE")
    _rejected(report, "MISSING_INDEPENDENT_VERIFIER")
    assert report.valid_real_paired_draws == 0


def test_negative_case_16_cross_draw_attestation_reuse_rejected() -> None:
    row1, official1 = _inputs(count=2, draw="SYNTHETIC-DRAW-1")
    row2, official2 = _inputs(count=2, draw="SYNTHETIC-DRAW-2")
    verified1 = _verified_fixture(row1, official1)
    # The verifier reuses the identical receipt source_sha256 for Draw 2.
    verified2 = replace(
        _verified_fixture(row2, official2),
        source_sha256=verified1.source_sha256,
    )

    def cross_draw_verifier(
        evidence: evaluator.PreDrawCaptureEvidence, _bytes: bytes
    ) -> evaluator.VerifiedExternalAttestation:
        if evidence.capture_locator == verified1.capture_locator:
            return verified1
        return verified2

    report = evaluator.evaluate_paired_any_prize(
        [row1, row2],
        [official1, official2],
        report_label=evaluator.SYNTHETIC_FIXTURE,
        attestation_verifier=cross_draw_verifier,
    )
    _rejected(report, "ATTESTATION_BINDING_MISMATCH")
