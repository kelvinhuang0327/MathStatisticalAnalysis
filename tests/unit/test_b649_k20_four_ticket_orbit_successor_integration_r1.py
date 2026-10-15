from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from lottolab.research import b649_k20_four_ticket_orbit_successor_integration_r1 as integration

binding = integration.binding
dispatcher = integration.dispatcher


@pytest.fixture(autouse=True)
def isolated_local_integration(tmp_path, monkeypatch):
    monkeypatch.setattr(integration, "INTEGRATION_WORKTREE", Path(__file__).resolve().parents[2])
    monkeypatch.setattr(integration, "TEST_RUNTIME_ROOT", tmp_path)


class InterruptedTest(Exception):
    pass


class MemoryJournal:
    def __init__(self):
        self.data = b""

    def read_bytes(self):
        return self.data

    def append_line(self, expected_previous, line):
        assert self.data == expected_previous
        self.data += line


@pytest.fixture(scope="module")
def manifest_bytes():
    return (integration.INTEGRATION_WORKTREE / dispatcher.MANIFEST_RELATIVE_PATH).read_bytes()


@pytest.fixture(scope="module")
def plan(manifest_bytes):
    return dispatcher.load_manifest_plan(manifest_bytes)


@pytest.fixture(scope="module")
def prefix(manifest_bytes, plan):
    # Valid synthetic resume state bounds the real generator to the final three
    # representatives. These seeded results are test data, never scientific data.
    journal = MemoryJournal()

    def seed(representative):
        if representative == plan.representatives[-3]:
            raise InterruptedTest
        return dispatcher.RepresentativeEvaluation(
            dispatcher.RAW_ATTEMPTS_PER_REPRESENTATIVE,
            [
                dispatcher.CandidateOutcome(
                    dispatcher.BASELINE_COUNT,
                    hashlib.sha256(f"synthetic-prefix:{representative.index}".encode()).hexdigest(),
                )
            ],
        )

    with pytest.raises(InterruptedTest):
        dispatcher.run_dispatch(manifest_bytes, journal=journal, score_representative=seed)
    assert len(dispatcher.validate_progress_prefix(journal.data, plan).records) == 427
    return journal.data


def journal_directory(root, prefix):
    directory = root / dispatcher.TASK_ID
    directory.mkdir(parents=True)
    (directory / dispatcher.PROGRESS_FILENAME).write_bytes(prefix)
    return directory


class SyntheticEvaluator:
    """Cheap exact-interface double; the original generator is never patched."""

    def __init__(self, gain=1, interrupt_index=None):
        self.gain = gain
        self.interrupt_index = interrupt_index
        self.representatives = []
        self.baseline = None
        self.recounts = []

    def official_count(self, portfolio):
        self.recounts.append(portfolio)
        if self.baseline is None:
            self.baseline = portfolio
        return dispatcher.BASELINE_COUNT + (0 if portfolio == self.baseline else self.gain)

    def build_residual(self, start, representative):
        assert start.portfolio == self.baseline
        assert start.outcome_count == dispatcher.BASELINE_COUNT
        assert start.sha256 == dispatcher.BASELINE_PORTFOLIO_SHA256
        self.representatives.append(representative)
        evaluator = self

        class Residual:
            universe_numbers = tuple(
                sorted(
                    {
                        number
                        for index in representative.quadruple
                        for number in start.portfolio[index]
                    }
                )
            )
            pattern_count = 1

            def __init__(self):
                self.calls = 0

            def outcome_count(self, tickets):
                self.calls += 1
                if representative.index == evaluator.interrupt_index and self.calls == 3:
                    raise InterruptedTest
                return dispatcher.BASELINE_COUNT + (0 if self.calls == 1 else evaluator.gain)

        return Residual()


def test_actual_integration_binds_sources_dispatches_frozen_rows_and_durably_completes(
    tmp_path,
    monkeypatch,
    manifest_bytes,
    plan,
    prefix,
):
    directory = journal_directory(tmp_path, prefix)
    evaluator = SyntheticEvaluator()
    observed = {}
    original_load = binding.load_original_predicate_for_successor
    original_dispatch = dispatcher.run_dispatch
    original_root = binding.SUCCESSOR_WORKTREE
    original_path = sys.path[:]

    def load():
        evidence = original_load()
        observed["binding"] = evidence
        assert evidence.binding_module_sha256 == integration.SOURCE_BINDING_SHA256
        assert evidence.binding_module_path.is_relative_to(integration.INTEGRATION_WORKTREE)
        assert evidence.driver_sha256 == dispatcher.DRIVER_SHA256
        assert evidence.predicate_sha256 == dispatcher.PREDICATE_SHA256
        assert evidence.dependency_sha256 == binding.ARCHIVED_DEPENDENCY_SHA256
        assert evidence.official_sha256 == dispatcher.EVALUATOR_SHA256
        original_scan = evidence.predicate_module.scan_quadruple

        def scan(start, residual, quadruple):
            result = original_scan(start, residual, quadruple)
            # Independent enumeration characterizes the original first-seen
            # order. It is not derived by sorting the integrated callback output.
            expected = []
            seen = set()
            module = evidence.predicate_module
            for spec in module.iter_quadruple_specs(
                start.portfolio,
                quadruple,
                pool_size=start.pool_size,
            ):
                emitted = module.classify_attempt(start.portfolio, spec, pool_size=start.pool_size)
                if not isinstance(emitted, str) and emitted.sha256 not in seen:
                    seen.add(emitted.sha256)
                    expected.append(emitted.sha256)
            assert [row[0] for row in result["ROWS"]] == expected
            observed.setdefault("rows", []).append(result["ROWS"])
            return result

        monkeypatch.setattr(evidence.predicate_module, "scan_quadruple", scan)
        return evidence

    def dispatch(manifest, *, journal, score_representative):
        assert manifest == manifest_bytes
        assert isinstance(journal, dispatcher.JsonlProgressJournal)
        assert journal.directory == directory
        observed["dispatcher"] = True

        def score(representative):
            evaluation = score_representative(representative)
            outcomes = list(evaluation.candidate_results)
            assert evaluation.raw_attempts == 7_776
            assert [(item.result_identity_sha256, item.official_count) for item in outcomes] == [
                (row[0], row[3]) for row in observed["rows"][-1]
            ]
            return dispatcher.RepresentativeEvaluation(evaluation.raw_attempts, outcomes)

        return original_dispatch(manifest, journal=journal, score_representative=score)

    monkeypatch.setattr(binding, "load_original_predicate_for_successor", load)
    monkeypatch.setattr(dispatcher, "run_dispatch", dispatch)
    summary = integration.run_successor(journal_directory=directory, test_evaluator=evaluator)
    assert observed["dispatcher"] is True
    assert evaluator.representatives == list(plan.representatives[-3:])
    assert len(summary.completed_representative_indices) == 430
    assert summary.unexecuted_representative_indices == ()
    assert summary.incumbent.official_count == 313_263_889
    assert summary.incumbent.representative_index == plan.representatives[-3].index
    assert summary.incumbent.candidate_ordinal == 0
    assert summary.incumbent.result_identity_sha256 == observed["rows"][0][0][0]
    data = (directory / dispatcher.PROGRESS_FILENAME).read_bytes()
    assert data.startswith(prefix)
    assert len(dispatcher.validate_progress_prefix(data, plan).records) == 430
    assert dispatcher.summarize_progress(manifest_bytes, data) == summary
    assert original_root == binding.SUCCESSOR_WORKTREE
    assert sys.path == original_path
    assert binding.FOUR_TICKET_IMPORT_NAME not in sys.modules
    assert len(evaluator.recounts) == 2  # Baseline plus the first strict improvement.


@pytest.mark.parametrize("gain", [0, 1])
def test_integrated_strict_gain_boundary_and_earlier_candidate_ties(
    tmp_path,
    plan,
    prefix,
    gain,
):
    evaluator = SyntheticEvaluator(gain=gain)
    directory = journal_directory(tmp_path, prefix)
    summary = integration.run_successor(journal_directory=directory, test_evaluator=evaluator)
    assert summary.incumbent.official_count == 313_263_888 + gain
    assert dispatcher.is_strict_gain(summary.incumbent.official_count) is bool(gain)
    assert summary.incumbent.representative_index == (
        plan.representatives[-3].index if gain else None
    )
    assert summary.incumbent.candidate_ordinal == (0 if gain else None)
    rows = (directory / dispatcher.PROGRESS_FILENAME).read_bytes().splitlines()[-3:]
    assert len({json.loads(row)["incumbent_after"]["result_identity_sha256"] for row in rows}) == 1


def test_durable_interrupted_generator_resume_equals_uninterrupted_integration(
    tmp_path,
    manifest_bytes,
    plan,
    prefix,
):
    uninterrupted = journal_directory(tmp_path / "uninterrupted", prefix)
    full = integration.run_successor(
        journal_directory=uninterrupted,
        test_evaluator=SyntheticEvaluator(),
    )
    interrupted = journal_directory(tmp_path / "interrupted", prefix)
    evaluator = SyntheticEvaluator(interrupt_index=plan.representatives[-2].index)
    with pytest.raises(InterruptedTest):
        integration.run_successor(journal_directory=interrupted, test_evaluator=evaluator)
    partial = (interrupted / dispatcher.PROGRESS_FILENAME).read_bytes()
    assert len(dispatcher.validate_progress_prefix(partial, plan).records) == 428
    assert binding.FOUR_TICKET_IMPORT_NAME not in sys.modules
    resumed_evaluator = SyntheticEvaluator()
    resumed = integration.run_successor(
        journal_directory=interrupted,
        test_evaluator=resumed_evaluator,
    )
    assert resumed_evaluator.representatives == list(plan.representatives[-2:])
    assert resumed == full
    assert (interrupted / dispatcher.PROGRESS_FILENAME).read_bytes() == (
        uninterrupted / dispatcher.PROGRESS_FILENAME
    ).read_bytes()
    # Completed resume does not call any evaluator method.
    no_work = SyntheticEvaluator()
    assert integration.run_successor(journal_directory=interrupted, test_evaluator=no_work) == full
    assert no_work.representatives == no_work.recounts == []


@pytest.mark.parametrize("corruption", ["hash", "duplicate", "ordering"])
def test_integrated_journal_corruption_fails_closed_before_binding(
    tmp_path,
    monkeypatch,
    prefix,
    corruption,
):
    lines = prefix.splitlines(keepends=True)
    if corruption == "hash":
        corrupted = prefix.replace(b'"candidate_count":1', b'"candidate_count":2', 1)
    elif corruption == "duplicate":
        corrupted = lines[0] + lines[0] + b"".join(lines[2:])
    else:
        corrupted = lines[1] + lines[0] + b"".join(lines[2:])
    assert corrupted != prefix
    directory = journal_directory(tmp_path, corrupted)

    def forbidden_load():
        pytest.fail("corrupt resume must fail before source binding or evaluation")

    monkeypatch.setattr(binding, "load_original_predicate_for_successor", forbidden_load)
    with pytest.raises(dispatcher.DispatcherError):
        integration.run_successor(journal_directory=directory, test_evaluator=SyntheticEvaluator())
    assert (directory / dispatcher.PROGRESS_FILENAME).read_bytes() == corrupted


def test_altered_source_identity_fails_actual_integration(tmp_path, monkeypatch, prefix):
    directory = journal_directory(tmp_path, prefix)
    monkeypatch.setattr(binding, "FROZEN_PREDICATE_SHA256", "0" * 64)
    with pytest.raises(binding.SourceBindingError, match="FROZEN_PREDICATE:SHA256_MISMATCH"):
        integration.run_successor(journal_directory=directory, test_evaluator=SyntheticEvaluator())
    assert (directory / dispatcher.PROGRESS_FILENAME).read_bytes() == prefix


def test_altered_representative_mapping_fails_actual_integration(
    tmp_path,
    monkeypatch,
    manifest_bytes,
    prefix,
):
    directory = journal_directory(tmp_path, prefix)
    path = integration.INTEGRATION_WORKTREE / dispatcher.MANIFEST_RELATIVE_PATH
    original_read = Path.read_bytes

    def altered_read(self):
        if self == path:
            return manifest_bytes.replace(b'"index":626,"quadruple"', b'"index":627,"quadruple"', 1)
        return original_read(self)

    monkeypatch.setattr(Path, "read_bytes", altered_read)
    with pytest.raises(dispatcher.DispatcherError, match="manifest SHA-256 differs"):
        integration.run_successor(journal_directory=directory, test_evaluator=SyntheticEvaluator())
    assert (directory / dispatcher.PROGRESS_FILENAME).read_bytes() == prefix


def test_synthetic_journal_cannot_use_scientific_evaluator(tmp_path, prefix):
    directory = journal_directory(tmp_path, prefix)
    with pytest.raises(
        integration.IntegrationError,
        match="SCIENTIFIC_EVALUATOR_REQUIRES_SEPARATE_SUCCESSOR_JOURNAL",
    ):
        integration.run_successor(journal_directory=directory)


def test_test_evaluator_cannot_write_outside_test_runtime(tmp_path, monkeypatch, prefix):
    directory = journal_directory(tmp_path, prefix)
    monkeypatch.setattr(integration, "TEST_RUNTIME_ROOT", tmp_path / "different-root")
    with pytest.raises(
        integration.IntegrationError, match="TEST_EVALUATOR_REQUIRES_ISOLATED_TEST_JOURNAL"
    ):
        integration.run_successor(journal_directory=directory, test_evaluator=SyntheticEvaluator())


def test_incorrect_canonical_recount_never_appends(tmp_path, prefix):
    directory = journal_directory(tmp_path, prefix)

    class BadRecount(SyntheticEvaluator):
        def official_count(self, portfolio):
            super().official_count(portfolio)
            return dispatcher.BASELINE_COUNT

    with pytest.raises(
        integration.IntegrationError, match="STRICT_GAIN_CANONICAL_RECOUNT_MISMATCH"
    ):
        integration.run_successor(journal_directory=directory, test_evaluator=BadRecount())
    assert (directory / dispatcher.PROGRESS_FILENAME).read_bytes() == prefix
