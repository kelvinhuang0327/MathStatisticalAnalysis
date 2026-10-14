from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from lottolab.research import b649_k20_orbit_successor_dispatcher_r1 as dispatcher


class MemoryJournal:
    """Synthetic journal adapter; tests perform no filesystem writes."""

    def __init__(self) -> None:
        self.data = b""

    def read_bytes(self) -> bytes:
        return self.data

    def append_line(self, expected_previous: bytes, line: bytes) -> None:
        if self.data != expected_previous:
            raise dispatcher.DispatcherError("synthetic journal compare failed")
        self.data += line


class SyntheticInterruption(Exception):
    pass


@pytest.fixture(scope="module")
def manifest_bytes() -> bytes:
    path = Path(__file__).resolve().parents[2] / dispatcher.MANIFEST_RELATIVE_PATH
    return path.read_bytes()


@pytest.fixture(scope="module")
def plan(manifest_bytes: bytes) -> dispatcher.ManifestPlan:
    return dispatcher.load_manifest_plan(manifest_bytes)


def _identity(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _synthetic_evaluation(
    representative: dispatcher.Representative,
) -> dispatcher.RepresentativeEvaluation:
    count = dispatcher.BASELINE_COUNT + representative.index % 3
    return dispatcher.RepresentativeEvaluation(
        dispatcher.RAW_ATTEMPTS_PER_REPRESENTATIVE,
        (
            dispatcher.CandidateOutcome(count, _identity(f"{representative.index}:first")),
            dispatcher.CandidateOutcome(count, _identity(f"{representative.index}:tie")),
        ),
    )


def _prefix_bytes(
    manifest_bytes: bytes,
    plan: dispatcher.ManifestPlan,
    completed_count: int,
) -> bytes:
    assert 0 <= completed_count < len(plan.representatives)
    journal = MemoryJournal()
    stop_index = plan.representatives[completed_count].index

    def stop_after_prefix(
        representative: dispatcher.Representative,
    ) -> dispatcher.RepresentativeEvaluation:
        if representative.index == stop_index:
            raise SyntheticInterruption
        return _synthetic_evaluation(representative)

    with pytest.raises(SyntheticInterruption):
        dispatcher.run_dispatch(
            manifest_bytes, journal=journal, score_representative=stop_after_prefix
        )
    return journal.data


def test_manifest_and_representative_identities_match_frozen_authority(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    assert hashlib.sha256(manifest_bytes).hexdigest() == dispatcher.EXPECTED_MANIFEST_SHA256
    assert plan.manifest_sha256 == dispatcher.EXPECTED_MANIFEST_SHA256
    assert plan.representative_tuples_sha256 == dispatcher.EXPECTED_REPRESENTATIVE_TUPLES_SHA256


def test_orbit_coverage_historical_attempts_and_new_attempt_target_are_separate(
    plan: dispatcher.ManifestPlan,
) -> None:
    assert plan.total_orbits == 670
    assert plan.historically_covered_orbits == 240
    assert plan.historical_directly_scored_quadruples == 623
    assert plan.historical_executed_raw_attempts == 4_844_448
    assert len(plan.representatives) == 430
    assert plan.raw_attempts_per_representative == 7_776
    assert plan.expected_new_raw_attempts == 3_343_680


def test_dispatch_order_is_exact_manifest_order_without_duplicates(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    manifest = json.loads(manifest_bytes)
    expected = tuple(
        dispatcher.Representative(item["index"], tuple(item["quadruple"]))
        for item in manifest["remaining_representatives"]
    )
    actual_indices = [item.index for item in plan.representatives]
    assert plan.representatives == expected
    assert actual_indices == sorted(actual_indices)
    assert len(actual_indices) == len(set(actual_indices)) == 430
    assert len({item.quadruple for item in plan.representatives}) == 430


def test_strict_gain_boundary_is_one_above_the_baseline() -> None:
    assert dispatcher.is_strict_gain(313_263_888) is False
    assert dispatcher.is_strict_gain(313_263_889) is True


def test_ties_keep_the_earlier_result_and_source_order_is_consumed_as_given(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    first = dispatcher.CandidateOutcome(dispatcher.BASELINE_COUNT + 7, _identity("ordered-first"))
    second = dispatcher.CandidateOutcome(dispatcher.BASELINE_COUNT + 7, _identity("ordered-second"))
    observed: list[str] = []

    def source_order():
        observed.append("first")
        yield first
        observed.append("second")
        yield second

    journal = MemoryJournal()
    first_index = plan.representatives[0].index

    def score(
        representative: dispatcher.Representative,
    ) -> dispatcher.RepresentativeEvaluation:
        if representative.index == first_index:
            return dispatcher.RepresentativeEvaluation(7_776, source_order())
        return dispatcher.RepresentativeEvaluation(
            7_776,
            (
                dispatcher.CandidateOutcome(
                    dispatcher.BASELINE_COUNT, _identity(str(representative.index))
                ),
            ),
        )

    summary = dispatcher.run_dispatch(manifest_bytes, journal=journal, score_representative=score)
    first_record = json.loads(journal.data.splitlines()[0])
    assert observed == ["first", "second"]
    assert first_record["representative_result"] == {
        "official_count": dispatcher.BASELINE_COUNT + 7,
        "result_identity_sha256": first.result_identity_sha256,
        "candidate_ordinal": 0,
    }
    assert summary.incumbent.representative_index == first_index
    assert summary.incumbent.result_identity_sha256 == first.result_identity_sha256


def test_interrupted_resume_matches_uninterrupted_synthetic_dispatch(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    uninterrupted_journal = MemoryJournal()
    uninterrupted_summary = dispatcher.run_dispatch(
        manifest_bytes,
        journal=uninterrupted_journal,
        score_representative=_synthetic_evaluation,
    )

    interrupted_journal = MemoryJournal()
    completed_before_interrupt = 9
    stop_index = plan.representatives[completed_before_interrupt].index
    calls_before_interrupt: list[int] = []

    def interrupt_on_tenth(
        representative: dispatcher.Representative,
    ) -> dispatcher.RepresentativeEvaluation:
        if representative.index == stop_index:
            raise SyntheticInterruption
        calls_before_interrupt.append(representative.index)
        return _synthetic_evaluation(representative)

    with pytest.raises(SyntheticInterruption):
        dispatcher.run_dispatch(
            manifest_bytes,
            journal=interrupted_journal,
            score_representative=interrupt_on_tenth,
        )
    partial = dispatcher.validate_progress_prefix(interrupted_journal.data, plan)
    assert len(partial.records) == completed_before_interrupt
    assert calls_before_interrupt == [
        item.index for item in plan.representatives[:completed_before_interrupt]
    ]

    resumed_calls: list[int] = []

    def resume_score(
        representative: dispatcher.Representative,
    ) -> dispatcher.RepresentativeEvaluation:
        resumed_calls.append(representative.index)
        return _synthetic_evaluation(representative)

    resumed_summary = dispatcher.run_dispatch(
        manifest_bytes,
        journal=interrupted_journal,
        score_representative=resume_score,
    )
    assert resumed_calls == [
        item.index for item in plan.representatives[completed_before_interrupt:]
    ]
    assert interrupted_journal.data == uninterrupted_journal.data
    assert resumed_summary == uninterrupted_summary
    assert len(resumed_summary.directly_scored_representative_indices) == 430
    assert resumed_summary.new_raw_attempts_completed == 3_343_680


def test_journal_prefix_is_valid_and_rejects_duplicates_and_reordering(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    prefix = _prefix_bytes(manifest_bytes, plan, 3)
    state = dispatcher.validate_progress_prefix(prefix, plan)
    assert [row["representative_index"] for row in state.records] == [
        item.index for item in plan.representatives[:3]
    ]

    lines = prefix.splitlines(keepends=True)
    duplicate = lines[0] + lines[0] + lines[2]
    reordered = lines[1] + lines[0] + lines[2]
    with pytest.raises(dispatcher.DispatcherError, match="ordered manifest prefix"):
        dispatcher.validate_progress_prefix(duplicate, plan)
    with pytest.raises(dispatcher.DispatcherError, match="ordered manifest prefix"):
        dispatcher.validate_progress_prefix(reordered, plan)


def test_journal_bound_to_another_manifest_fails_closed(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    record = json.loads(_prefix_bytes(manifest_bytes, plan, 1))
    record["manifest_sha256"] = "0" * 64
    unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
    record["record_sha256"] = dispatcher._sha256(dispatcher._canonical_json_bytes(unsigned))
    changed_identity = dispatcher._canonical_json_bytes(record)
    with pytest.raises(
        dispatcher.DispatcherError, match="progress record manifest identity differs"
    ):
        dispatcher.validate_progress_prefix(changed_identity, plan)


def test_corrupt_or_truncated_journal_fails_closed(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    prefix = _prefix_bytes(manifest_bytes, plan, 1)
    corrupted = prefix.replace(b'"candidate_count":2', b'"candidate_count":3', 1)
    assert corrupted != prefix
    with pytest.raises(dispatcher.DispatcherError, match="SHA-256 differs"):
        dispatcher.validate_progress_prefix(corrupted, plan)
    with pytest.raises(dispatcher.DispatcherError, match="truncated final record"):
        dispatcher.validate_progress_prefix(prefix[:-1], plan)


def test_altered_manifest_fails_closed(manifest_bytes: bytes) -> None:
    marker = b'"index":626,"quadruple"'
    assert marker in manifest_bytes
    altered = manifest_bytes.replace(marker, b'"index":627,"quadruple"', 1)
    with pytest.raises(dispatcher.DispatcherError, match="manifest SHA-256 differs"):
        dispatcher.load_manifest_plan(altered)


def test_changed_representative_mapping_fails_targeted_validation(
    manifest_bytes: bytes,
) -> None:
    document = copy.deepcopy(json.loads(manifest_bytes))
    document["remaining_representatives"][0]["quadruple"] = [0, 1, 2, 3]
    unsigned = {key: value for key, value in document.items() if key != "manifest_content_sha256"}
    document["manifest_content_sha256"] = dispatcher._sha256(
        dispatcher._canonical_json_bytes(unsigned)
    )
    with pytest.raises(
        dispatcher.DispatcherError,
        match="remaining representatives differ from unvisited orbit rows",
    ):
        dispatcher._manifest_plan_from_object(
            document, manifest_sha256=dispatcher.EXPECTED_MANIFEST_SHA256
        )


def test_empty_progress_keeps_mathematical_coverage_separate_from_direct_scores(
    manifest_bytes: bytes,
) -> None:
    summary = dispatcher.summarize_progress(manifest_bytes, b"")
    assert summary.total_orbits == 670
    assert summary.mathematically_covered_orbits == 240
    assert summary.historical_directly_scored_quadruples == 623
    assert summary.historical_executed_raw_attempts == 4_844_448
    assert summary.pending_representatives_total == 430
    assert summary.completed_representative_indices == ()
    assert summary.directly_scored_representative_indices == ()
    assert len(summary.unexecuted_representative_indices) == 430
    assert summary.new_raw_attempts_completed == 0
    assert summary.expected_new_raw_attempts == 3_343_680


def test_incomplete_group_is_never_recorded(
    manifest_bytes: bytes, plan: dispatcher.ManifestPlan
) -> None:
    journal = MemoryJournal()

    def incomplete(
        _representative: dispatcher.Representative,
    ) -> dispatcher.RepresentativeEvaluation:
        return dispatcher.RepresentativeEvaluation(
            7_775,
            (dispatcher.CandidateOutcome(dispatcher.BASELINE_COUNT, _identity("incomplete")),),
        )

    with pytest.raises(dispatcher.DispatcherError, match="raw attempt count differs"):
        dispatcher.run_dispatch(manifest_bytes, journal=journal, score_representative=incomplete)
    assert journal.data == b""
    assert dispatcher.validate_progress_prefix(journal.data, plan).records == ()
