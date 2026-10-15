"""Leak-resistant paired OFFICIAL_ANY_PRIZE evaluator for branch 6.

This module scores frozen pre-draw portfolios against later official draws.
It does not rank numbers, does not emit a prediction, and does not invent
historical frozen artifacts. A real observed-success report with no admitted
pair stays ``NOT_ESTABLISHED`` / ``NOT_COMPARABLE``.

Observed wins call ``score_big_lotto_ticket`` and ``resolve_big_lotto_prize_tier``.
Uniform-model coverage from ``b649_official_any_prize_exact`` is stored on a
separate field and is never written into the observed win indicator.

``prediction_generated_at`` is recorded when present and is excluded from the
frozen-artifact digest. It is not pre-draw proof. Admission requires a matching
artifact SHA-256 and ``EXTERNAL_PREDRAW_ATTESTATION`` evidence whose capture
time is at or before the supplied legal information cutoff and strictly before
the official result is available.

Data submitters cannot self-establish trust for REAL_OBSERVED. Caller-supplied
verifier callbacks, caller-supplied trusted=true flags, self-declared attestation
JSON, self-filled timestamps, locators, and always-True verifiers do not constitute
independent trust. Selection and verification of trusted sources must be independent
of data submitter control.

In the absence of an integrated independent trusted verification source, any attempt
to evaluate or admit real evidence under REAL_OBSERVED is REJECTED.
Observed success gain remains NOT_ESTABLISHED and valid real paired draws remains 0.
Synthetic fixtures always need the explicit label and cannot be promoted to real.

Only complete, already selected portfolios are accepted, with a frozen lexical
tie policy. Partial rankings/score lists cannot be completed using draw results.
Any invalid input invalidates the whole batch; no lift is computed on a
validation-selected subset.

Donor: original Branch6 source, 44755 bytes, mtime_ns=1792035396658573758,
SHA256=cc676cf0baaac449799409755eea1fc9a624447c4d5256dd95767eb6ed1feac3.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from typing import Final, cast

from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    BigLottoPrizeTier,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)
from lottolab.research.b649_official_any_prize_exact import (
    independent_random_official_any_prize,
)

EVALUATOR_ID: Final = "b649_branch6_forward_paired_any_prize_r1"
EVALUATOR_VERSION: Final = "1.1.0"
SUPPORTED_TICKET_COUNTS: Final[tuple[int, ...]] = (2, 3, 5, 10, 20)
TIE_ORDER_LEXICOGRAPHIC: Final = "LEXICOGRAPHIC_TICKET"

NOT_ESTABLISHED: Final = "NOT_ESTABLISHED"
NOT_COMPARABLE: Final = "NOT_COMPARABLE"
SAME_COUNT_PAIRED: Final = "SAME_COUNT_PAIRED"
SIGNIFICANCE_NOT_CLAIMED: Final = "SIGNIFICANCE_NOT_CLAIMED"
REAL_OBSERVED: Final = "REAL_OBSERVED"
SYNTHETIC_FIXTURE: Final = "SYNTHETIC_FIXTURE"
REAL_PREDRAW_ARTIFACT: Final = "REAL_PREDRAW_ARTIFACT"
EXTERNAL_PREDRAW_ATTESTATION: Final = "EXTERNAL_PREDRAW_ATTESTATION"
GENERATED_AT_ONLY: Final = "GENERATED_AT_ONLY"
IN_SAMPLE: Final = "IN_SAMPLE"
OUT_OF_SAMPLE: Final = "OUT_OF_SAMPLE"
OBSERVED_WIN_FIELD: Final = "candidate_observed_official_any_prize"
THEORETICAL_COVERAGE_FIELD: Final = "theoretical_uniform_any_prize_coverage"
COST_COMPARISON_POLICY: Final = (
    "Each ticket_count is the stake. Same-count rates stay beside that stake. "
    "A larger stake is not evidence of a stronger ranking."
)

MISSING_FREEZE_EVIDENCE: Final = "MISSING_FREEZE_EVIDENCE"
GENERATED_AT_ONLY_REJECTION: Final = "GENERATED_AT_ONLY"
UNTRUSTED_FREEZE_EVIDENCE: Final = "UNTRUSTED_FREEZE_EVIDENCE"
DAMAGED_SHA256: Final = "DAMAGED_SHA256"
SHA256_MISMATCH: Final = "SHA256_MISMATCH"
MISSING_CUTOFF: Final = "MISSING_CUTOFF"
LATE_CUTOFF: Final = "LATE_CUTOFF"
CUTOFF_NOT_BEFORE_RESULT: Final = "CUTOFF_NOT_BEFORE_RESULT"
MISSING_LEGAL_INFORMATION_CUTOFF: Final = "MISSING_LEGAL_INFORMATION_CUTOFF"
LATE_CAPTURE: Final = "LATE_CAPTURE"
WRONG_COUNT_BASELINE: Final = "WRONG_COUNT_BASELINE"
WRONG_BUDGET_BASELINE: Final = "WRONG_BUDGET_BASELINE"
CANDIDATE_TICKET_COUNT_MISMATCH: Final = "CANDIDATE_TICKET_COUNT_MISMATCH"
DUPLICATE_DRAW: Final = "DUPLICATE_DRAW"
MISSING_OFFICIAL_RESULT: Final = "MISSING_OFFICIAL_RESULT"
AMBIGUOUS_OFFICIAL_RESULT: Final = "AMBIGUOUS_OFFICIAL_RESULT"
ILLEGAL_TICKET: Final = "ILLEGAL_TICKET"
ILLEGAL_OFFICIAL_DRAW: Final = "ILLEGAL_OFFICIAL_DRAW"
UNSUPPORTED_TICKET_COUNT: Final = "UNSUPPORTED_TICKET_COUNT"
INVALID_SAMPLE_SCOPE: Final = "INVALID_SAMPLE_SCOPE"
MISSING_RANKING_IDENTITY: Final = "MISSING_RANKING_IDENTITY"
MISSING_SOURCE_IDENTITY: Final = "MISSING_SOURCE_IDENTITY"
NAIVE_DATETIME: Final = "NAIVE_DATETIME"
MALFORMED_SNAPSHOT: Final = "MALFORMED_SNAPSHOT"
MALFORMED_BASELINE: Final = "MALFORMED_BASELINE"
MALFORMED_OFFICIAL_RESULT: Final = "MALFORMED_OFFICIAL_RESULT"
UNTRUSTED_PROVENANCE: Final = "UNTRUSTED_PROVENANCE"
SYNTHETIC_EXCLUDED_FROM_REAL: Final = "SYNTHETIC_EXCLUDED_FROM_REAL"
REAL_EXCLUDED_FROM_SYNTHETIC: Final = "REAL_EXCLUDED_FROM_SYNTHETIC"
FROZEN_BYTES_MISMATCH: Final = "FROZEN_BYTES_MISMATCH"
BASELINE_DRAW_MISMATCH: Final = "BASELINE_DRAW_MISMATCH"
BASELINE_CUTOFF_MISMATCH: Final = "BASELINE_CUTOFF_MISMATCH"
INVALID_TIE_ORDER: Final = "INVALID_TIE_ORDER"
ATTESTATION_BINDING_MISMATCH: Final = "ATTESTATION_BINDING_MISMATCH"
MISSING_INDEPENDENT_VERIFIER: Final = "MISSING_INDEPENDENT_VERIFIER"
GENERATED_AFTER_CAPTURE: Final = "GENERATED_AFTER_CAPTURE"

_SHA256_WIDTH: Final = 64
_REPORT_LABELS: Final = frozenset({REAL_OBSERVED, SYNTHETIC_FIXTURE})
_SAMPLE_SCOPES: Final = frozenset({IN_SAMPLE, OUT_OF_SAMPLE})
_SCOPE_ORDER: Final = {IN_SAMPLE: 0, OUT_OF_SAMPLE: 1}
Ticket = tuple[int, ...]


class FrozenArtifactError(ValueError):
    """The pre-draw snapshot cannot be canonicalized into artifact bytes."""


@dataclass(frozen=True, slots=True)
class PreDrawCaptureEvidence:
    """Separate attestation that the artifact bytes were fixed before the draw."""

    evidence_kind: str
    artifact_sha256: str
    captured_at: datetime | None
    capture_locator: str


@dataclass(frozen=True, slots=True)
class VerifiedExternalAttestation:
    """Trusted adapter output, never parsed from input JSON.

    ``source_sha256`` identifies the authenticated evidence bytes, rather than
    merely repeating the prediction digest. The adapter must verify authority,
    timestamp, draw identity, provenance and official clocks independently of
    the submitted claims. Returning a value is a trust decision by host code;
    passing through unverified JSON is not an implementation of this contract.
    Tests using mock evidence must retain SYNTHETIC_FIXTURE provenance.
    """

    artifact_sha256: str
    draw_id: str
    captured_at: datetime
    prediction_cutoff: datetime
    capture_locator: str
    source_identity: str
    source_sha256: str
    provenance: str
    official_draw_source_identity: str
    official_result_available_at: datetime
    legal_pre_draw_information_cutoff: datetime


AttestationVerifier = Callable[[PreDrawCaptureEvidence, bytes], VerifiedExternalAttestation | None]


@dataclass(frozen=True, slots=True)
class PairedDrawEvaluation:
    """One admitted same-count pair. Official numbers did not choose the tickets."""

    draw_id: str
    ticket_count: int
    stake: int
    prediction_cutoff: str
    sample_scope: str
    ranking_algorithm_id: str
    ranking_version: str
    candidate_portfolio: tuple[Ticket, ...]
    baseline_portfolio: tuple[Ticket, ...]
    candidate_observed_official_any_prize: bool
    baseline_observed_official_any_prize: bool
    paired_indicator_difference: int
    theoretical_uniform_any_prize_coverage: str
    report_label: str
    frozen_artifact_sha256: str
    attestation_source_identity: str
    attestation_source_sha256: str


@dataclass(frozen=True, slots=True)
class ScopeBucketReport:
    """In-sample and out-of-sample lifts are never pooled in one bucket."""

    sample_scope: str
    ticket_count: int
    stake: int
    valid_paired_draw_count: int
    draw_ids: tuple[str, ...]
    same_count_observed_lift: str
    records: tuple[PairedDrawEvaluation, ...]


@dataclass(frozen=True, slots=True)
class InputRejection:
    """One submitted row that did not become a valid paired draw."""

    input_index: int
    draw_id: str
    ticket_count: int | None
    codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LeakageDisposition:
    """What this run admitted. ``generated_at`` alone never counts as proof."""

    admitted_real_pair_count: int
    admitted_synthetic_pair_count: int
    generated_at_alone_is_proof: bool
    official_numbers_used_for_selection: bool
    rejected_count: int
    rejections: tuple[InputRejection, ...]


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Paired OFFICIAL_ANY_PRIZE report. Empty admission does not claim a gain."""

    report_label: str
    evaluator_id: str
    evaluator_version: str
    official_prize_rule_identity: str
    valid_paired_draw_count: int
    same_count_observed_lift: str
    predictive_gain: str
    future_predictive_gain: str
    ranking_comparability: str
    sample_uncertainty: str
    significance_claim: str
    leakage_disposition: LeakageDisposition
    cost_comparison_policy: str
    in_sample_buckets: tuple[ScopeBucketReport, ...]
    out_of_sample_buckets: tuple[ScopeBucketReport, ...]
    cross_count_lines: tuple[str, ...]
    observed_field_name: str
    theoretical_field_name: str
    validation_status: str
    valid_real_paired_draws: int
    observed_success_gain: str


@dataclass(frozen=True, slots=True)
class _ParsedSnapshot:
    input_index: int
    draw_id: str
    ticket_count: int | None
    ranking_algorithm_id: str
    ranking_version: str
    candidate_portfolio: tuple[Ticket, ...] | None
    baseline_ticket_count: int | None
    baseline_portfolio: tuple[Ticket, ...] | None
    prediction_cutoff: datetime | None
    prediction_generated_at: datetime | None
    frozen_artifact_sha256: str
    evidence: PreDrawCaptureEvidence | None
    sample_scope: str
    provenance: str
    codes: tuple[str, ...]
    frozen_bytes: bytes | None
    baseline_draw_id: str
    baseline_cutoff: datetime | None


@dataclass(frozen=True, slots=True)
class _ParsedOfficial:
    draw_id: str
    source_identity: str
    available_at: datetime | None
    winning_main: tuple[int, ...] | None
    winning_special: int | None
    legal_cutoff: datetime | None
    codes: tuple[str, ...]
    provenance: str

    def identity_key(self) -> tuple[object, ...]:
        return (
            self.draw_id,
            self.source_identity,
            _iso_or_none(self.available_at),
            self.winning_main,
            self.winning_special,
            _iso_or_none(self.legal_cutoff),
            self.codes,
            self.provenance,
        )


def official_prize_rule_identity() -> str:
    """Identity of the pinned BIG_LOTTO prize contract this evaluator calls."""

    prize_rule = BIG_LOTTO_RULE_CONTRACT.prize_rule
    if prize_rule is None:
        raise RuntimeError("BIG_LOTTO prize rule is missing")
    return (
        f"{BIG_LOTTO_RULE_CONTRACT.lottery_type.value}:"
        f"{BIG_LOTTO_RULE_CONTRACT.contract_version}:"
        f"prize_schema:{prize_rule.schema_version}"
    )


def deterministic_tie_order(tickets: Sequence[Sequence[int]]) -> tuple[Ticket, ...]:
    """Stable portfolio order. Same tickets always produce the same sequence."""

    normalized: list[Ticket] = []
    for ticket in tickets:
        normalized.append(tuple(ticket))
    return tuple(sorted(normalized))


def canonical_frozen_artifact_bytes(snapshot: Mapping[str, object]) -> bytes:
    """Digest input for the pre-draw snapshot. Official results are not inputs.

    ``prediction_generated_at``, the SHA field, and the capture evidence are
    omitted on purpose. A self-filled timestamp cannot change or satisfy the digest.
    """

    parsed = _parse_snapshot(0, snapshot)
    if parsed.codes:
        raise FrozenArtifactError(",".join(parsed.codes))
    if parsed.prediction_cutoff is None or not _is_aware(parsed.prediction_cutoff):
        raise FrozenArtifactError(NAIVE_DATETIME)
    if (
        parsed.candidate_portfolio is None
        or parsed.baseline_portfolio is None
        or parsed.baseline_ticket_count is None
        or parsed.ticket_count is None
    ):
        raise FrozenArtifactError(MALFORMED_SNAPSHOT)
    return _artifact_bytes(
        draw_id=parsed.draw_id,
        ticket_count=parsed.ticket_count,
        ranking_algorithm_id=parsed.ranking_algorithm_id,
        ranking_version=parsed.ranking_version,
        candidate_portfolio=parsed.candidate_portfolio,
        baseline_ticket_count=parsed.baseline_ticket_count,
        baseline_portfolio=parsed.baseline_portfolio,
        prediction_cutoff=parsed.prediction_cutoff,
        sample_scope=parsed.sample_scope,
        provenance=parsed.provenance,
    )


def frozen_artifact_sha256(snapshot: Mapping[str, object]) -> str:
    """Lowercase SHA-256 of :func:`canonical_frozen_artifact_bytes`."""

    return hashlib.sha256(canonical_frozen_artifact_bytes(snapshot)).hexdigest()


def observed_official_any_prize(
    portfolio: Sequence[Sequence[int]],
    winning_main_numbers: Sequence[int],
    winning_special_number: int,
) -> bool:
    """True when one ticket resolves to a ``BigLottoPrizeTier`` under the contract."""

    mains = tuple(winning_main_numbers)
    won = False
    # Validate every ticket, including tickets after a winner.
    score_big_lotto_ticket(
        predicted_main_numbers=mains,
        winning_main_numbers=mains,
        winning_special_number=winning_special_number,
    )
    for ticket in deterministic_tie_order(portfolio):
        score = score_big_lotto_ticket(
            predicted_main_numbers=ticket,
            winning_main_numbers=mains,
            winning_special_number=winning_special_number,
        )
        tier = resolve_big_lotto_prize_tier(score.main_hits, score.special_hit)
        if isinstance(tier, BigLottoPrizeTier):
            won = True
    return won


def evaluate_paired_any_prize(
    pre_draw_snapshots: Sequence[Mapping[str, object]],
    official_results: Sequence[Mapping[str, object]],
    *,
    report_label: str = REAL_OBSERVED,
    attestation_verifier: AttestationVerifier | None = None,
) -> EvaluationReport:
    """Pair frozen snapshots with official results and score OFFICIAL_ANY_PRIZE.

    ``report_label`` is ``REAL_OBSERVED`` or ``SYNTHETIC_FIXTURE``. Synthetic
    rows are rejected by a real report, and real rows are rejected by a
    synthetic report, so a fixture win cannot enter the real observed tally.
    """

    if report_label not in _REPORT_LABELS:
        raise ValueError(f"unsupported report_label: {report_label}")

    officials, ambiguous_ids = _index_official_results(official_results)
    parsed = [_parse_snapshot(index, snapshot) for index, snapshot in enumerate(pre_draw_snapshots)]
    duplicate_keys = _duplicate_keys(parsed)
    verified_sources: dict[str, str] = {}
    verified_locators: dict[str, str] = {}

    admitted: list[PairedDrawEvaluation] = []
    rejections: list[InputRejection] = []
    # Validate all submitted official rows, including unmatched rows. Never
    # silently discard malformed or duplicate results before computing a lift.
    for index, raw in enumerate(official_results):
        official = _parse_official(index, raw)
        codes = list(official.codes)
        _add_provenance_codes(codes, official.provenance, report_label)
        if official.draw_id in ambiguous_ids:
            _add(codes, AMBIGUOUS_OFFICIAL_RESULT)
        if codes:
            rejections.append(InputRejection(index, official.draw_id, None, tuple(codes)))
    for row in parsed:
        codes = list(row.codes)
        key = _duplicate_key(row)
        if key is not None and key in duplicate_keys:
            _add(codes, DUPLICATE_DRAW)
        if not codes:
            codes = _admission_codes(row, officials, ambiguous_ids, report_label)
        verified: VerifiedExternalAttestation | None = None
        if not codes and (report_label == REAL_OBSERVED or attestation_verifier is not None):
            verified = _verify_external_attestation(
                codes,
                row,
                officials[row.draw_id],
                attestation_verifier,
                verified_sources,
                verified_locators,
            )
        if codes:
            rejections.append(
                InputRejection(
                    input_index=row.input_index,
                    draw_id=row.draw_id,
                    ticket_count=row.ticket_count,
                    codes=tuple(codes),
                )
            )
            continue
        admitted.append(_score_admitted(row, officials[row.draw_id], report_label, verified))

    return _assemble_report(report_label, () if rejections else tuple(admitted), tuple(rejections))


def render_evaluation_report(report: EvaluationReport) -> str:
    """Deterministic text form. Two renders of the same report match byte for byte."""

    leakage = report.leakage_disposition
    lines = [
        f"report_label={report.report_label}",
        f"validation_status={report.validation_status}",
        f"VALID_REAL_PAIRED_DRAWS={report.valid_real_paired_draws}",
        f"OBSERVED_SUCCESS_GAIN={report.observed_success_gain}",
        f"FUTURE_PREDICTIVE_GAIN={report.future_predictive_gain}",
        f"evaluator_id={report.evaluator_id}",
        f"evaluator_version={report.evaluator_version}",
        f"official_prize_rule_identity={report.official_prize_rule_identity}",
        f"valid_paired_draw_count={report.valid_paired_draw_count}",
        f"same_count_observed_lift={report.same_count_observed_lift}",
        f"predictive_gain={report.predictive_gain}",
        f"future_predictive_gain={report.future_predictive_gain}",
        f"ranking_comparability={report.ranking_comparability}",
        f"sample_uncertainty={report.sample_uncertainty}",
        f"significance_claim={report.significance_claim}",
        f"leakage_admitted_real_pairs={leakage.admitted_real_pair_count}",
        f"leakage_admitted_synthetic_pairs={leakage.admitted_synthetic_pair_count}",
        f"generated_at_alone_is_proof={str(leakage.generated_at_alone_is_proof).lower()}",
        "official_numbers_used_for_selection="
        f"{str(leakage.official_numbers_used_for_selection).lower()}",
        f"rejected_count={leakage.rejected_count}",
        f"cost_comparison_policy={report.cost_comparison_policy}",
        f"observed_field_name={report.observed_field_name}",
        f"theoretical_field_name={report.theoretical_field_name}",
    ]
    for rejection in leakage.rejections:
        code_text = ",".join(rejection.codes)
        lines.append(
            f"rejection index={rejection.input_index} draw_id={rejection.draw_id} "
            f"ticket_count={rejection.ticket_count} codes={code_text}"
        )
    for bucket in (*report.in_sample_buckets, *report.out_of_sample_buckets):
        lines.append(
            f"bucket sample_scope={bucket.sample_scope} stake={bucket.stake} "
            f"ticket_count={bucket.ticket_count} "
            f"valid_paired_draw_count={bucket.valid_paired_draw_count} "
            f"draw_ids={','.join(bucket.draw_ids)} "
            f"same_count_observed_lift={bucket.same_count_observed_lift}"
        )
        for record in bucket.records:
            lines.append(
                f"pair draw_id={record.draw_id} stake={record.stake} "
                f"sample_scope={record.sample_scope} "
                f"candidate_observed_official_any_prize="
                f"{str(record.candidate_observed_official_any_prize).lower()} "
                f"baseline_observed_official_any_prize="
                f"{str(record.baseline_observed_official_any_prize).lower()} "
                f"paired_indicator_difference={record.paired_indicator_difference} "
                f"frozen_artifact_sha256={record.frozen_artifact_sha256} "
                f"attestation_source_identity={record.attestation_source_identity} "
                f"attestation_source_sha256={record.attestation_source_sha256} "
                f"theoretical_uniform_any_prize_coverage="
                f"{record.theoretical_uniform_any_prize_coverage} "
                f"candidate_portfolio={_portfolio_text(record.candidate_portfolio)} "
                f"baseline_portfolio={_portfolio_text(record.baseline_portfolio)}"
            )
    lines.extend(report.cross_count_lines)
    return "\n".join(lines) + "\n"


def synthetic_launch_inputs() -> tuple[dict[str, object], dict[str, object]]:
    """One labeled synthetic pair. Not a historical frozen prediction."""

    draw_id = "SYNTHETIC-FIXTURE-DRAW-1"
    ticket_count = 2
    candidate = ((1, 2, 7, 8, 9, 10), (20, 21, 22, 23, 24, 25))
    baseline = ((20, 21, 22, 23, 24, 25), (26, 27, 28, 29, 30, 31))
    cutoff = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    generated_at = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    captured_at = datetime(2026, 1, 1, 11, 30, tzinfo=UTC)
    snapshot: dict[str, object] = {
        "draw_id": draw_id,
        "ticket_count": ticket_count,
        "ranking_algorithm_id": "fixture-ranking",
        "ranking_version": "fixture-0",
        "candidate_portfolio": candidate,
        "same_count_baseline": {
            "ticket_count": ticket_count,
            "portfolio": baseline,
            "draw_id": draw_id,
            "prediction_cutoff": cutoff,
        },
        "prediction_cutoff": cutoff,
        "prediction_generated_at": generated_at,
        "frozen_artifact_sha256": "",
        "pre_draw_capture_evidence": {
            "evidence_kind": EXTERNAL_PREDRAW_ATTESTATION,
            "artifact_sha256": "",
            "captured_at": captured_at,
            "capture_locator": f"external-capture:{draw_id}",
        },
        "sample_scope": OUT_OF_SAMPLE,
        "provenance": SYNTHETIC_FIXTURE,
        "tie_order": TIE_ORDER_LEXICOGRAPHIC,
    }
    digest = frozen_artifact_sha256(snapshot)
    snapshot["frozen_artifact_sha256"] = digest
    evidence = snapshot["pre_draw_capture_evidence"]
    if not isinstance(evidence, dict):
        raise FrozenArtifactError(MALFORMED_SNAPSHOT)
    evidence["artifact_sha256"] = digest
    snapshot["frozen_artifact_bytes"] = canonical_frozen_artifact_bytes(snapshot)
    official: dict[str, object] = {
        "official_draw_id": draw_id,
        "official_draw_source_identity": f"synthetic-source:{draw_id}",
        "official_result_available_at": datetime(2026, 1, 1, 20, 0, tzinfo=UTC),
        "winning_main_numbers": (1, 2, 3, 4, 5, 6),
        "winning_special_number": 7,
        "legal_pre_draw_information_cutoff": cutoff,
        "provenance": SYNTHETIC_FIXTURE,
    }
    return snapshot, official


def _score_admitted(
    row: _ParsedSnapshot,
    official: _ParsedOfficial,
    report_label: str,
    verified: VerifiedExternalAttestation | None = None,
) -> PairedDrawEvaluation:
    if (
        row.candidate_portfolio is None
        or row.baseline_portfolio is None
        or row.ticket_count is None
        or row.prediction_cutoff is None
        or official.winning_main is None
        or official.winning_special is None
    ):
        raise RuntimeError("admitted row missing fields that admission already checked")
    candidate = deterministic_tie_order(row.candidate_portfolio)
    baseline = deterministic_tie_order(row.baseline_portfolio)
    mains = official.winning_main
    special = official.winning_special
    candidate_win = observed_official_any_prize(candidate, mains, special)
    baseline_win = observed_official_any_prize(baseline, mains, special)
    coverage = independent_random_official_any_prize(row.ticket_count)
    return PairedDrawEvaluation(
        draw_id=row.draw_id,
        ticket_count=row.ticket_count,
        stake=row.ticket_count,
        prediction_cutoff=_iso_z(row.prediction_cutoff),
        sample_scope=row.sample_scope,
        ranking_algorithm_id=row.ranking_algorithm_id,
        ranking_version=row.ranking_version,
        candidate_portfolio=candidate,
        baseline_portfolio=baseline,
        candidate_observed_official_any_prize=candidate_win,
        baseline_observed_official_any_prize=baseline_win,
        paired_indicator_difference=int(candidate_win) - int(baseline_win),
        theoretical_uniform_any_prize_coverage=f"{coverage.numerator}/{coverage.denominator}",
        report_label=report_label,
        frozen_artifact_sha256=row.frozen_artifact_sha256,
        attestation_source_identity=(verified.source_identity if verified else SYNTHETIC_FIXTURE),
        attestation_source_sha256=(verified.source_sha256 if verified else ""),
    )


def _admission_codes(
    row: _ParsedSnapshot,
    officials: Mapping[str, _ParsedOfficial],
    ambiguous_ids: frozenset[str],
    report_label: str,
) -> list[str]:
    codes: list[str] = []
    _add_provenance_codes(codes, row.provenance, report_label)
    _add_identity_codes(codes, row)
    _add_baseline_codes(codes, row)
    _add_clock_codes(codes, row)
    digest = _digest_or_codes(codes, row)
    _add_sha_codes(codes, row.frozen_artifact_sha256, digest)
    _add_evidence_codes(codes, row, digest)
    official = _matched_official(codes, row, officials, ambiguous_ids)
    if official is not None:
        _add_result_clock_codes(codes, row, official)
        _add_legality_codes(codes, row, official)
    return codes


def _add_provenance_codes(codes: list[str], provenance: str, report_label: str) -> None:
    if report_label == REAL_OBSERVED and provenance != REAL_PREDRAW_ARTIFACT:
        _add(codes, SYNTHETIC_EXCLUDED_FROM_REAL)
    elif report_label == SYNTHETIC_FIXTURE and provenance != SYNTHETIC_FIXTURE:
        _add(codes, REAL_EXCLUDED_FROM_SYNTHETIC)
    elif provenance not in {REAL_PREDRAW_ARTIFACT, SYNTHETIC_FIXTURE}:
        _add(codes, UNTRUSTED_PROVENANCE)


def _add_identity_codes(codes: list[str], row: _ParsedSnapshot) -> None:
    if row.ticket_count not in SUPPORTED_TICKET_COUNTS:
        _add(codes, UNSUPPORTED_TICKET_COUNT)
    if row.sample_scope not in _SAMPLE_SCOPES:
        _add(codes, INVALID_SAMPLE_SCOPE)
    if not row.ranking_algorithm_id or not row.ranking_version:
        _add(codes, MISSING_RANKING_IDENTITY)
    candidate = row.candidate_portfolio
    if candidate is None or (row.ticket_count is not None and len(candidate) != row.ticket_count):
        _add(codes, CANDIDATE_TICKET_COUNT_MISMATCH)


def _add_baseline_codes(codes: list[str], row: _ParsedSnapshot) -> None:
    if row.baseline_draw_id != row.draw_id:
        _add(codes, BASELINE_DRAW_MISMATCH)
    if row.baseline_cutoff != row.prediction_cutoff:
        _add(codes, BASELINE_CUTOFF_MISMATCH)
    if row.baseline_ticket_count is None or row.baseline_portfolio is None:
        _add(codes, MALFORMED_BASELINE)
        return
    if row.ticket_count is None:
        return
    if row.baseline_ticket_count != row.ticket_count:
        _add(codes, WRONG_COUNT_BASELINE)
    if len(row.baseline_portfolio) != row.ticket_count:
        _add(codes, WRONG_BUDGET_BASELINE)


def _add_clock_codes(codes: list[str], row: _ParsedSnapshot) -> None:
    if row.prediction_cutoff is None:
        _add(codes, MISSING_CUTOFF)
    elif not _is_aware(row.prediction_cutoff):
        _add(codes, NAIVE_DATETIME)
    if row.prediction_generated_at is not None and not _is_aware(row.prediction_generated_at):
        _add(codes, NAIVE_DATETIME)
    generated = row.prediction_generated_at
    captured = row.evidence.captured_at if row.evidence else None
    if (
        generated is not None
        and captured is not None
        and _is_aware(generated)
        and _is_aware(captured)
        and generated > captured
    ):
        _add(codes, GENERATED_AFTER_CAPTURE)


def _digest_or_codes(codes: list[str], row: _ParsedSnapshot) -> str | None:
    if codes:
        return None
    if (
        row.prediction_cutoff is None
        or row.candidate_portfolio is None
        or row.baseline_portfolio is None
        or row.baseline_ticket_count is None
        or row.ticket_count is None
    ):
        return None
    try:
        digest = hashlib.sha256(
            _artifact_bytes(
                draw_id=row.draw_id,
                ticket_count=row.ticket_count,
                ranking_algorithm_id=row.ranking_algorithm_id,
                ranking_version=row.ranking_version,
                candidate_portfolio=row.candidate_portfolio,
                baseline_ticket_count=row.baseline_ticket_count,
                baseline_portfolio=row.baseline_portfolio,
                prediction_cutoff=row.prediction_cutoff,
                sample_scope=row.sample_scope,
                provenance=row.provenance,
            )
        ).hexdigest()
    except FrozenArtifactError:
        _add(codes, MALFORMED_SNAPSHOT)
        return None
    if row.frozen_bytes is None:
        _add(codes, FROZEN_BYTES_MISMATCH)
    else:
        # Bind the actual bytes as well as the parsed selected portfolios.
        # Re-serialization alone would hide changes to frozen bytes.
        if hashlib.sha256(row.frozen_bytes).hexdigest() != digest:
            _add(codes, FROZEN_BYTES_MISMATCH)
    return digest


def _add_sha_codes(codes: list[str], declared: str, digest: str | None) -> None:
    if not _is_sha256(declared):
        _add(codes, DAMAGED_SHA256)
        return
    if digest is not None and declared != digest:
        _add(codes, SHA256_MISMATCH)


def _add_evidence_codes(codes: list[str], row: _ParsedSnapshot, digest: str | None) -> None:
    evidence = row.evidence
    if evidence is None:
        _add(codes, MISSING_FREEZE_EVIDENCE)
        return
    if evidence.evidence_kind == GENERATED_AT_ONLY:
        _add(codes, GENERATED_AT_ONLY_REJECTION)
        return
    if evidence.evidence_kind != EXTERNAL_PREDRAW_ATTESTATION:
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        return
    locator = evidence.capture_locator.strip()
    generated = row.prediction_generated_at
    if not locator:
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
    elif generated is not None and _is_aware(generated) and locator == _iso_z(generated):
        _add(codes, GENERATED_AT_ONLY_REJECTION)
    if not _is_sha256(evidence.artifact_sha256):
        _add(codes, DAMAGED_SHA256)
    elif digest is not None and evidence.artifact_sha256 != digest:
        _add(codes, SHA256_MISMATCH)
    if evidence.captured_at is None:
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
    elif not _is_aware(evidence.captured_at):
        _add(codes, NAIVE_DATETIME)


def _verify_external_attestation(
    codes: list[str],
    row: _ParsedSnapshot,
    official: _ParsedOfficial,
    verifier: AttestationVerifier | None,
    verified_sources: dict[str, str] | None = None,
    verified_locators: dict[str, str] | None = None,
) -> VerifiedExternalAttestation | None:
    if verifier is None:
        _add(codes, MISSING_INDEPENDENT_VERIFIER)
        return None
    if row.evidence is None or row.frozen_bytes is None:
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        return None

    # Caller-supplied verifier callbacks are controlled by the data submitter and cannot
    # serve as an independent trust root for real pre-draw attestation.
    if row.provenance == REAL_PREDRAW_ARTIFACT:
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        _add(codes, MISSING_INDEPENDENT_VERIFIER)
        try:
            verified = verifier(row.evidence, row.frozen_bytes)
            if (
                isinstance(verified, VerifiedExternalAttestation)
                and verified.provenance != row.provenance
            ):
                _add(codes, ATTESTATION_BINDING_MISMATCH)
        except Exception:
            pass
        return None

    try:
        verified = verifier(row.evidence, row.frozen_bytes)
    except Exception:  # A verification outage must never admit or score a real row.
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        return None
    if not isinstance(verified, VerifiedExternalAttestation):
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        return None
    if verified.provenance != SYNTHETIC_FIXTURE:
        # Caller-supplied verifiers can only authenticate SYNTHETIC_FIXTURE fixtures.
        # They cannot promote evidence to real or replace the independent trust root.
        _add(codes, ATTESTATION_BINDING_MISMATCH)
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        return None
    texts = (
        verified.artifact_sha256,
        verified.draw_id,
        verified.capture_locator,
        verified.source_identity,
        verified.source_sha256,
        verified.provenance,
        verified.official_draw_source_identity,
    )
    if any(type(value) is not str for value in texts):
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        return None
    clocks = (
        verified.captured_at,
        verified.prediction_cutoff,
        verified.official_result_available_at,
        verified.legal_pre_draw_information_cutoff,
    )
    if any(type(value) is not datetime or not _is_aware(value) for value in clocks):
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
        return None
    if (
        verified.artifact_sha256 != row.frozen_artifact_sha256
        or verified.draw_id != row.draw_id
        or verified.captured_at != row.evidence.captured_at
        or verified.prediction_cutoff != row.prediction_cutoff
        or verified.capture_locator != row.evidence.capture_locator
        or verified.provenance != row.provenance
        or verified.official_draw_source_identity != official.source_identity
        or verified.official_result_available_at != official.available_at
        or verified.legal_pre_draw_information_cutoff != official.legal_cutoff
        or not verified.source_identity.strip()
        or not _is_sha256(verified.source_sha256)
    ):
        _add(codes, ATTESTATION_BINDING_MISMATCH)
        return None
    if verified_sources is not None:
        source_key = verified.source_sha256
        if source_key in verified_sources and verified_sources[source_key] != row.draw_id:
            _add(codes, ATTESTATION_BINDING_MISMATCH)
            return None
        verified_sources[source_key] = row.draw_id
    if verified_locators is not None:
        loc_key = verified.capture_locator
        if loc_key in verified_locators and verified_locators[loc_key] != row.draw_id:
            _add(codes, ATTESTATION_BINDING_MISMATCH)
            return None
        verified_locators[loc_key] = row.draw_id
    return verified


def _matched_official(
    codes: list[str],
    row: _ParsedSnapshot,
    officials: Mapping[str, _ParsedOfficial],
    ambiguous_ids: frozenset[str],
) -> _ParsedOfficial | None:
    if row.draw_id in ambiguous_ids:
        _add(codes, AMBIGUOUS_OFFICIAL_RESULT)
        return None
    official = officials.get(row.draw_id)
    if official is None:
        _add(codes, MISSING_OFFICIAL_RESULT)
        return None
    for code in official.codes:
        _add(codes, code)
    return official


def _add_result_clock_codes(
    codes: list[str],
    row: _ParsedSnapshot,
    official: _ParsedOfficial,
) -> None:
    if official.legal_cutoff is None:
        _add(codes, MISSING_LEGAL_INFORMATION_CUTOFF)
    elif not _is_aware(official.legal_cutoff):
        _add(codes, NAIVE_DATETIME)
    if official.available_at is None:
        _add(codes, MISSING_OFFICIAL_RESULT)
    elif not _is_aware(official.available_at):
        _add(codes, NAIVE_DATETIME)
    cutoff = row.prediction_cutoff
    if (
        cutoff is not None
        and _is_aware(cutoff)
        and official.legal_cutoff is not None
        and _is_aware(official.legal_cutoff)
        and _to_utc(cutoff) > _to_utc(official.legal_cutoff)
    ):
        _add(codes, LATE_CUTOFF)
    if (
        cutoff is not None
        and _is_aware(cutoff)
        and official.available_at is not None
        and _is_aware(official.available_at)
        and _to_utc(cutoff) >= _to_utc(official.available_at)
    ):
        _add(codes, CUTOFF_NOT_BEFORE_RESULT)
    evidence = row.evidence
    captured = evidence.captured_at if evidence is not None else None
    legal_cutoff = official.legal_cutoff
    available_at = official.available_at
    if (
        captured is not None
        and _is_aware(captured)
        and legal_cutoff is not None
        and _is_aware(legal_cutoff)
        and _to_utc(captured) > _to_utc(legal_cutoff)
    ):
        _add(codes, LATE_CAPTURE)
    if (
        captured is not None
        and cutoff is not None
        and _is_aware(captured)
        and _is_aware(cutoff)
        and captured > cutoff
    ):
        _add(codes, LATE_CAPTURE)
    if (
        captured is not None
        and _is_aware(captured)
        and available_at is not None
        and _is_aware(available_at)
        and _to_utc(captured) >= _to_utc(available_at)
    ):
        _add(codes, LATE_CAPTURE)


def _add_legality_codes(
    codes: list[str],
    row: _ParsedSnapshot,
    official: _ParsedOfficial,
) -> None:
    if official.winning_main is None or official.winning_special is None:
        _add(codes, ILLEGAL_OFFICIAL_DRAW)
        return
    portfolios = (row.candidate_portfolio, row.baseline_portfolio)
    for portfolio in portfolios:
        if portfolio is None:
            continue
        for ticket in portfolio:
            code = _ticket_code(ticket, official.winning_main, official.winning_special)
            if code is not None:
                _add(codes, code)


def _ticket_code(
    ticket: Ticket,
    winning_main: tuple[int, ...],
    winning_special: int,
) -> str | None:
    try:
        score_big_lotto_ticket(
            predicted_main_numbers=ticket,
            winning_main_numbers=winning_main,
            winning_special_number=winning_special,
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith("predicted_main_numbers"):
            return ILLEGAL_TICKET
        return ILLEGAL_OFFICIAL_DRAW
    return None


def _assemble_report(
    report_label: str,
    admitted: tuple[PairedDrawEvaluation, ...],
    rejections: tuple[InputRejection, ...],
) -> EvaluationReport:
    ordered = tuple(sorted(rejections, key=_rejection_sort_key))
    buckets = _buckets(admitted)
    in_sample = tuple(bucket for bucket in buckets if bucket.sample_scope == IN_SAMPLE)
    out_of_sample = tuple(bucket for bucket in buckets if bucket.sample_scope == OUT_OF_SAMPLE)
    count = len(admitted)
    # Real observed admission requires an integrated independent trusted source.
    # Without such an independent authority, no real draw is admitted, and
    # observed success gain remains NOT_ESTABLISHED.
    real_count = 0
    synthetic_count = count if report_label == SYNTHETIC_FIXTURE else 0
    return EvaluationReport(
        report_label=report_label,
        evaluator_id=EVALUATOR_ID,
        evaluator_version=EVALUATOR_VERSION,
        official_prize_rule_identity=official_prize_rule_identity(),
        valid_paired_draw_count=count,
        same_count_observed_lift=_lift_text(buckets),
        predictive_gain=NOT_ESTABLISHED,
        future_predictive_gain=NOT_ESTABLISHED,
        ranking_comparability=SAME_COUNT_PAIRED if count else NOT_COMPARABLE,
        sample_uncertainty=_uncertainty(count),
        significance_claim=SIGNIFICANCE_NOT_CLAIMED,
        leakage_disposition=LeakageDisposition(
            admitted_real_pair_count=real_count,
            admitted_synthetic_pair_count=synthetic_count,
            generated_at_alone_is_proof=False,
            official_numbers_used_for_selection=False,
            rejected_count=len(ordered),
            rejections=ordered,
        ),
        cost_comparison_policy=COST_COMPARISON_POLICY,
        in_sample_buckets=in_sample,
        out_of_sample_buckets=out_of_sample,
        cross_count_lines=_cross_count_lines(buckets),
        observed_field_name=OBSERVED_WIN_FIELD,
        theoretical_field_name=THEORETICAL_COVERAGE_FIELD,
        validation_status="INVALID_INPUT" if rejections else "VALID",
        valid_real_paired_draws=0,
        observed_success_gain=NOT_ESTABLISHED,
    )


def _buckets(admitted: tuple[PairedDrawEvaluation, ...]) -> tuple[ScopeBucketReport, ...]:
    grouped: dict[tuple[str, int], list[PairedDrawEvaluation]] = {}
    for record in admitted:
        grouped.setdefault((record.sample_scope, record.ticket_count), []).append(record)
    reports: list[ScopeBucketReport] = []
    for scope, ticket_count in sorted(grouped, key=_bucket_sort_key):
        records = tuple(sorted(grouped[(scope, ticket_count)], key=lambda item: item.draw_id))
        total = sum(record.paired_indicator_difference for record in records)
        lift = Fraction(total, len(records))
        reports.append(
            ScopeBucketReport(
                sample_scope=scope,
                ticket_count=ticket_count,
                stake=ticket_count,
                valid_paired_draw_count=len(records),
                draw_ids=tuple(record.draw_id for record in records),
                same_count_observed_lift=f"{lift.numerator}/{lift.denominator}",
                records=records,
            )
        )
    return tuple(reports)


def _lift_text(buckets: tuple[ScopeBucketReport, ...]) -> str:
    if not buckets:
        return NOT_ESTABLISHED
    parts = [
        f"{bucket.sample_scope}:stake={bucket.stake}:ticket_count={bucket.ticket_count}:"
        f"{bucket.same_count_observed_lift}"
        for bucket in buckets
    ]
    return ";".join(parts)


def _uncertainty(count: int) -> str:
    if count == 0:
        return NOT_ESTABLISHED
    return f"DESCRIPTIVE_PAIRS={count};SIGNIFICANCE_NOT_CLAIMED"


def _cross_count_lines(buckets: tuple[ScopeBucketReport, ...]) -> tuple[str, ...]:
    lines = [
        f"stake={bucket.stake} ticket_count={bucket.ticket_count} "
        f"sample_scope={bucket.sample_scope} "
        f"same_count_observed_lift={bucket.same_count_observed_lift} "
        "larger_stake_is_not_ranking_skill=true"
        for bucket in buckets
    ]
    if len({bucket.ticket_count for bucket in buckets}) > 1:
        lines.append("cross_count_comparison_is_not_ranking_skill=true")
    return tuple(lines)


def _index_official_results(
    official_results: Sequence[Mapping[str, object]],
) -> tuple[dict[str, _ParsedOfficial], frozenset[str]]:
    grouped: dict[str, list[_ParsedOfficial]] = {}
    for index, raw in enumerate(official_results):
        parsed = _parse_official(index, raw)
        grouped.setdefault(parsed.draw_id, []).append(parsed)
    unique: dict[str, _ParsedOfficial] = {}
    ambiguous: set[str] = set()
    for draw_id, rows in grouped.items():
        keys = {row.identity_key() for row in rows}
        if len(rows) > 1 or len(keys) > 1 or draw_id == "":
            if draw_id != "":
                ambiguous.add(draw_id)
            continue
        unique[draw_id] = rows[0]
    return unique, frozenset(ambiguous)


def _as_mapping(raw: object) -> Mapping[str, object] | None:
    if not isinstance(raw, Mapping):
        return None
    return cast(Mapping[str, object], raw)


def _as_sequence(raw: object) -> Sequence[object] | None:
    if type(raw) is not list and type(raw) is not tuple:
        return None
    return cast(Sequence[object], raw)


def _parse_official(index: int, raw: object) -> _ParsedOfficial:
    del index
    mapping = _as_mapping(raw)
    if mapping is None:
        return _ParsedOfficial("", "", None, None, None, None, (MALFORMED_OFFICIAL_RESULT,), "")
    codes: list[str] = []
    draw_id = mapping.get("official_draw_id")
    if type(draw_id) is not str or not draw_id.strip():
        draw_id = ""
        _add(codes, MALFORMED_OFFICIAL_RESULT)
    source = mapping.get("official_draw_source_identity")
    if type(source) is not str or not source.strip():
        source = ""
        _add(codes, MISSING_SOURCE_IDENTITY)
    available = _optional_datetime(mapping.get("official_result_available_at"), codes)
    if available is None:
        _add(codes, MISSING_OFFICIAL_RESULT)
    legal = _optional_datetime(mapping.get("legal_pre_draw_information_cutoff"), codes)
    if "legal_pre_draw_information_cutoff" not in mapping or legal is None:
        _add(codes, MISSING_LEGAL_INFORMATION_CUTOFF)
    mains = _parse_ticket(mapping.get("winning_main_numbers"))
    special = mapping.get("winning_special_number")
    if mains is None or type(special) is not int:
        _add(codes, ILLEGAL_OFFICIAL_DRAW)
        special_number = None
    else:
        special_number = special
        if _ticket_code(mains, mains, special_number) is not None:
            _add(codes, ILLEGAL_OFFICIAL_DRAW)
    provenance = _optional_text(mapping.get("provenance"))
    if provenance not in {REAL_PREDRAW_ARTIFACT, SYNTHETIC_FIXTURE}:
        _add(codes, UNTRUSTED_PROVENANCE)
    return _ParsedOfficial(
        draw_id=draw_id,
        source_identity=source,
        available_at=available,
        winning_main=mains,
        winning_special=special_number,
        legal_cutoff=legal,
        codes=tuple(codes),
        provenance=provenance,
    )


def _parse_snapshot(index: int, raw: object) -> _ParsedSnapshot:
    mapping = _as_mapping(raw)
    if mapping is None:
        return _empty_snapshot(index, (MALFORMED_SNAPSHOT,))
    codes: list[str] = []
    draw_id = mapping.get("draw_id")
    if type(draw_id) is not str or not draw_id.strip():
        draw_id = ""
        _add(codes, MALFORMED_SNAPSHOT)
    ticket_count = mapping.get("ticket_count")
    parsed_count = ticket_count if type(ticket_count) is int else None
    if parsed_count is None:
        _add(codes, UNSUPPORTED_TICKET_COUNT)
    ranking_algorithm_id = _optional_text(mapping.get("ranking_algorithm_id"))
    ranking_version = _optional_text(mapping.get("ranking_version"))
    if not ranking_algorithm_id or not ranking_version:
        _add(codes, MISSING_RANKING_IDENTITY)
    candidate = _parse_portfolio(mapping.get("candidate_portfolio"))
    if candidate is None:
        _add(codes, CANDIDATE_TICKET_COUNT_MISMATCH)
    baseline_count, baseline, baseline_codes = _parse_baseline(mapping.get("same_count_baseline"))
    for code in baseline_codes:
        _add(codes, code)
    baseline_mapping = _as_mapping(mapping.get("same_count_baseline"))
    baseline_draw_id = _optional_text(baseline_mapping.get("draw_id")) if baseline_mapping else ""
    baseline_cutoff = _optional_datetime(
        baseline_mapping.get("prediction_cutoff") if baseline_mapping else None, codes
    )
    if not baseline_draw_id or baseline_cutoff is None:
        _add(codes, MALFORMED_BASELINE)
    if mapping.get("tie_order") != TIE_ORDER_LEXICOGRAPHIC:
        _add(codes, INVALID_TIE_ORDER)
    cutoff = _optional_datetime(mapping.get("prediction_cutoff"), codes)
    if "prediction_cutoff" not in mapping or cutoff is None:
        _add(codes, MISSING_CUTOFF)
    generated = _optional_datetime(mapping.get("prediction_generated_at"), codes)
    sha = mapping.get("frozen_artifact_sha256")
    sha_text = sha if type(sha) is str else ""
    if type(sha) is not str:
        _add(codes, DAMAGED_SHA256)
    evidence, evidence_codes = _parse_evidence(mapping.get("pre_draw_capture_evidence"))
    evidence_raw = mapping.get("pre_draw_capture_evidence")
    if "pre_draw_capture_evidence" not in mapping or evidence_raw is None:
        _add(codes, MISSING_FREEZE_EVIDENCE)
    for code in evidence_codes:
        _add(codes, code)
    scope = mapping.get("sample_scope")
    scope_text = scope if type(scope) is str else ""
    if scope_text not in _SAMPLE_SCOPES:
        _add(codes, INVALID_SAMPLE_SCOPE)
    provenance = mapping.get("provenance")
    provenance_text = provenance if type(provenance) is str else ""
    if provenance_text not in {REAL_PREDRAW_ARTIFACT, SYNTHETIC_FIXTURE}:
        _add(codes, UNTRUSTED_PROVENANCE)
    frozen_bytes = mapping.get("frozen_artifact_bytes")
    return _ParsedSnapshot(
        input_index=index,
        draw_id=draw_id,
        ticket_count=parsed_count,
        ranking_algorithm_id=ranking_algorithm_id,
        ranking_version=ranking_version,
        candidate_portfolio=candidate,
        baseline_ticket_count=baseline_count,
        baseline_portfolio=baseline,
        prediction_cutoff=cutoff,
        prediction_generated_at=generated,
        frozen_artifact_sha256=sha_text,
        evidence=evidence,
        sample_scope=scope_text,
        provenance=provenance_text,
        codes=tuple(codes),
        frozen_bytes=frozen_bytes if type(frozen_bytes) is bytes else None,
        baseline_draw_id=baseline_draw_id,
        baseline_cutoff=baseline_cutoff,
    )


def _parse_baseline(
    raw: object,
) -> tuple[int | None, tuple[Ticket, ...] | None, tuple[str, ...]]:
    mapping = _as_mapping(raw)
    if mapping is None:
        return None, None, (MALFORMED_BASELINE,)
    count = mapping.get("ticket_count")
    portfolio = _parse_portfolio(mapping.get("portfolio"))
    parsed_count = count if type(count) is int else None
    if parsed_count is None or portfolio is None:
        return parsed_count, portfolio, (MALFORMED_BASELINE,)
    return parsed_count, portfolio, ()


def _parse_evidence(
    raw: object,
) -> tuple[PreDrawCaptureEvidence | None, tuple[str, ...]]:
    if raw is None:
        return None, ()
    mapping = _as_mapping(raw)
    if mapping is None:
        return None, (UNTRUSTED_FREEZE_EVIDENCE,)
    kind = mapping.get("evidence_kind")
    sha = mapping.get("artifact_sha256")
    locator = mapping.get("capture_locator")
    codes: list[str] = []
    captured = _optional_datetime(mapping.get("captured_at"), codes)
    if "captured_at" not in mapping:
        _add(codes, UNTRUSTED_FREEZE_EVIDENCE)
    evidence = PreDrawCaptureEvidence(
        evidence_kind=kind if type(kind) is str else "",
        artifact_sha256=sha if type(sha) is str else "",
        captured_at=captured,
        capture_locator=locator if type(locator) is str else "",
    )
    return evidence, tuple(codes)


def _empty_snapshot(index: int, codes: tuple[str, ...]) -> _ParsedSnapshot:
    return _ParsedSnapshot(
        input_index=index,
        draw_id="",
        ticket_count=None,
        ranking_algorithm_id="",
        ranking_version="",
        candidate_portfolio=None,
        baseline_ticket_count=None,
        baseline_portfolio=None,
        prediction_cutoff=None,
        prediction_generated_at=None,
        frozen_artifact_sha256="",
        evidence=None,
        sample_scope="",
        provenance="",
        codes=codes,
        frozen_bytes=None,
        baseline_draw_id="",
        baseline_cutoff=None,
    )


def _duplicate_keys(rows: Sequence[_ParsedSnapshot]) -> frozenset[tuple[str, int, str]]:
    counts: dict[tuple[str, int, str], int] = {}
    for row in rows:
        key = _duplicate_key(row)
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
    return frozenset(key for key, count in counts.items() if count > 1)


def _duplicate_key(row: _ParsedSnapshot) -> tuple[str, int, str] | None:
    if row.draw_id == "" or row.ticket_count is None or row.sample_scope not in _SAMPLE_SCOPES:
        return None
    if row.ticket_count not in SUPPORTED_TICKET_COUNTS:
        return None
    # Same draw/count cannot be counted again under a different sample scope.
    return ("ANY_SCOPE", row.ticket_count, row.draw_id)


def _artifact_bytes(
    *,
    draw_id: str,
    ticket_count: int,
    ranking_algorithm_id: str,
    ranking_version: str,
    candidate_portfolio: Sequence[Sequence[int]],
    baseline_ticket_count: int,
    baseline_portfolio: Sequence[Sequence[int]],
    prediction_cutoff: datetime,
    sample_scope: str,
    provenance: str,
) -> bytes:
    if not _is_aware(prediction_cutoff):
        raise FrozenArtifactError(NAIVE_DATETIME)
    payload = {
        "baseline_portfolio": [
            list(ticket) for ticket in deterministic_tie_order(baseline_portfolio)
        ],
        "baseline_ticket_count": baseline_ticket_count,
        "baseline_draw_id": draw_id,
        "baseline_prediction_cutoff": _iso_z(prediction_cutoff),
        "candidate_portfolio": [
            list(ticket) for ticket in deterministic_tie_order(candidate_portfolio)
        ],
        "draw_id": draw_id,
        "prediction_cutoff": _iso_z(prediction_cutoff),
        "provenance": provenance,
        "ranking_algorithm_id": ranking_algorithm_id,
        "ranking_version": ranking_version,
        "sample_scope": sample_scope,
        "ticket_count": ticket_count,
        "tie_order": TIE_ORDER_LEXICOGRAPHIC,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _parse_portfolio(raw: object) -> tuple[Ticket, ...] | None:
    sequence = _as_sequence(raw)
    if sequence is None:
        return None
    tickets: list[Ticket] = []
    for item in sequence:
        ticket = _parse_ticket(item)
        if ticket is None:
            return None
        tickets.append(ticket)
    return tuple(tickets)


def _parse_ticket(raw: object) -> Ticket | None:
    sequence = _as_sequence(raw)
    if sequence is None:
        return None
    numbers: list[int] = []
    for item in sequence:
        if type(item) is not int:
            return None
        numbers.append(item)
    return tuple(numbers)


def _optional_datetime(raw: object, codes: list[str]) -> datetime | None:
    if raw is None:
        return None
    if type(raw) is not datetime:
        _add(codes, NAIVE_DATETIME)
        return None
    if not _is_aware(raw):
        _add(codes, NAIVE_DATETIME)
    return raw


def _optional_text(raw: object) -> str:
    if type(raw) is not str:
        return ""
    return raw.strip()


def _is_sha256(value: str) -> bool:
    if len(value) != _SHA256_WIDTH:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _iso_z(value: datetime) -> str:
    return _to_utc(value).isoformat().replace("+00:00", "Z")


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None or not _is_aware(value):
        return None
    return _iso_z(value)


def _portfolio_text(portfolio: tuple[Ticket, ...]) -> str:
    rendered = ["-".join(str(number) for number in ticket) for ticket in portfolio]
    return "|".join(rendered)


def _add(codes: list[str], code: str) -> None:
    if code not in codes:
        codes.append(code)


def _rejection_sort_key(rejection: InputRejection) -> tuple[int, str, int, tuple[str, ...]]:
    ticket_count = -1 if rejection.ticket_count is None else rejection.ticket_count
    return (rejection.input_index, rejection.draw_id, ticket_count, rejection.codes)


def _bucket_sort_key(key: tuple[str, int]) -> tuple[int, int]:
    scope, ticket_count = key
    return (_SCOPE_ORDER[scope], ticket_count)


__all__ = [
    "CANDIDATE_TICKET_COUNT_MISMATCH",
    "COST_COMPARISON_POLICY",
    "CUTOFF_NOT_BEFORE_RESULT",
    "DAMAGED_SHA256",
    "DUPLICATE_DRAW",
    "EVALUATOR_ID",
    "EVALUATOR_VERSION",
    "EXTERNAL_PREDRAW_ATTESTATION",
    "GENERATED_AT_ONLY",
    "GENERATED_AT_ONLY_REJECTION",
    "ILLEGAL_OFFICIAL_DRAW",
    "ILLEGAL_TICKET",
    "IN_SAMPLE",
    "LATE_CAPTURE",
    "LATE_CUTOFF",
    "MALFORMED_SNAPSHOT",
    "MISSING_CUTOFF",
    "MISSING_FREEZE_EVIDENCE",
    "MISSING_LEGAL_INFORMATION_CUTOFF",
    "MISSING_OFFICIAL_RESULT",
    "MISSING_SOURCE_IDENTITY",
    "NOT_COMPARABLE",
    "NOT_ESTABLISHED",
    "OUT_OF_SAMPLE",
    "REAL_EXCLUDED_FROM_SYNTHETIC",
    "REAL_OBSERVED",
    "REAL_PREDRAW_ARTIFACT",
    "SAME_COUNT_PAIRED",
    "SHA256_MISMATCH",
    "SIGNIFICANCE_NOT_CLAIMED",
    "SUPPORTED_TICKET_COUNTS",
    "SYNTHETIC_EXCLUDED_FROM_REAL",
    "SYNTHETIC_FIXTURE",
    "TIE_ORDER_LEXICOGRAPHIC",
    "UNTRUSTED_FREEZE_EVIDENCE",
    "WRONG_BUDGET_BASELINE",
    "WRONG_COUNT_BASELINE",
    "AttestationVerifier",
    "EvaluationReport",
    "InputRejection",
    "LeakageDisposition",
    "PairedDrawEvaluation",
    "PreDrawCaptureEvidence",
    "ScopeBucketReport",
    "VerifiedExternalAttestation",
    "canonical_frozen_artifact_bytes",
    "deterministic_tie_order",
    "evaluate_paired_any_prize",
    "frozen_artifact_sha256",
    "observed_official_any_prize",
    "official_prize_rule_identity",
    "render_evaluation_report",
    "synthetic_launch_inputs",
]
