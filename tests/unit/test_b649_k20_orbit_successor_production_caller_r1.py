"""Synthetic production-path acceptance. No scientific search or real recount."""

from __future__ import annotations

import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from lottolab.research import b649_k20_orbit_successor_production_caller_r1 as caller

integration = caller.integration
dispatcher = caller.dispatcher
terminal = caller.terminal
WINNER_SHA256 = "b0061c79fa469be65e91f3d89cafb745610d092e93240e2e10854f15221dee72"
REMOVED = (
    (27, 29, 30, 31, 32, 33),
    (28, 29, 34, 39, 44, 45),
    (32, 37, 42, 44, 46, 48),
    (33, 38, 43, 45, 47, 49),
)
ADDED = (
    (27, 38, 43, 45, 47, 49),
    (28, 29, 30, 31, 32, 33),
    (29, 32, 34, 39, 44, 45),
    (33, 37, 42, 44, 46, 48),
)


class MemoryJournal:
    def __init__(self):
        self.data = b""

    def read_bytes(self):
        return self.data

    def append_line(self, expected_previous, line):
        assert expected_previous == self.data
        self.data += line


class SyntheticEvaluator:
    def __init__(self, gain=0, interrupt_index=None):
        self.gain = gain
        self.interrupt_index = interrupt_index
        self.representatives = []
        self.recounts = []

    def official_count(self, portfolio):
        self.recounts.append(portfolio)
        return dispatcher.BASELINE_COUNT + (
            self.gain if portfolio != caller.load_frozen_baseline() else 0
        )

    def build_residual(self, start, representative):
        self.representatives.append(representative.index)
        if representative.index == self.interrupt_index:
            raise InterruptedError("synthetic stop")
        gain = self.gain

        class Residual:
            universe_numbers = tuple(
                sorted({n for i in representative.quadruple for n in start.portfolio[i]})
            )
            pattern_count = 1

            def __init__(self):
                self.calls = 0

            def outcome_count(self, tickets):
                self.calls += 1
                return dispatcher.BASELINE_COUNT + (gain if self.calls > 1 else 0)

        return Residual()


@pytest.fixture(scope="module")
def data():
    baseline = caller.load_frozen_baseline()
    manifest = caller.verify_sources()
    plan = dispatcher.load_manifest_plan(manifest)
    assert plan.representatives[-1].index == 4805
    assert plan.representatives[-1].quadruple == (12, 15, 18, 19)
    winner = tuple(sorted((set(baseline) - set(REMOVED)) | set(ADDED)))
    assert (
        hashlib.sha256(json.dumps(winner, separators=(",", ":")).encode()).hexdigest()
        == WINNER_SHA256
    )

    def journal(*, gain=False, identity=WINNER_SHA256, ordinal=0):
        memory = MemoryJournal()

        def score(representative):
            rows = [dispatcher.CandidateOutcome(dispatcher.BASELINE_COUNT, "f" * 64)]
            if gain and representative.index == 4805:
                rows = [
                    dispatcher.CandidateOutcome(dispatcher.BASELINE_COUNT, "e" * 64)
                    for _ in range(ordinal)
                ] + [dispatcher.CandidateOutcome(dispatcher.STRICT_GAIN_MINIMUM_COUNT, identity)]
            return dispatcher.RepresentativeEvaluation(7776, rows)

        dispatcher.run_dispatch(manifest, journal=memory, score_representative=score)
        return memory.data

    no_gain = journal()
    return SimpleNamespace(
        baseline=baseline,
        manifest=manifest,
        plan=plan,
        winner=winner,
        no_gain=no_gain,
        gain=journal(gain=True),
        journal=journal,
        prefix=b"".join(no_gain.splitlines(keepends=True)[:429]),
    )


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(integration, "PRODUCTION_TEST_RUNTIME_ROOT", tmp_path)
    authority = integration.JournalRootAuthority(tmp_path / dispatcher.TASK_ID, testing=True)
    caller.provision_journal_root(authority, authorized=True)
    return authority


def invoke(root, *, evaluator=None, count=dispatcher.BASELINE_COUNT):
    return caller.run_production(
        journal_directory=root.directory,
        test_evaluator=SyntheticEvaluator() if evaluator is None else evaluator,
        test_terminal_recount=lambda _: count,
    )


def put_journal(root, journal):
    (root.directory / dispatcher.PROGRESS_FILENAME).write_bytes(journal)


def test_exact_inputs_baseline_and_check_cli_are_read_only(capsys):
    root = integration.PRODUCTION_JOURNAL_DIRECTORY
    before = root.exists()
    assert len(caller.load_frozen_baseline()) == 20
    assert caller.main(["--check"]) == 0
    assert "SCIENTIFIC_EXECUTION: NOT RUN" in capsys.readouterr().out
    assert root.exists() == before


def test_cli_wires_single_production_api(monkeypatch, capsys):
    observed = []
    monkeypatch.setattr(caller, "run_production", lambda **kwargs: observed.append(kwargs) or {})
    assert caller.main(["--authorized-scientific-run", "--provision-journal-root"]) == 0
    assert observed == [
        {
            "journal_directory": integration.PRODUCTION_JOURNAL_DIRECTORY,
            "authorized_scientific_run": True,
            "provision_root": True,
        }
    ]
    capsys.readouterr()


def test_production_requires_separate_launch_authorization():
    with pytest.raises(caller.ProductionCallerError, match="RUN_AUTHORIZATION"):
        caller.run_production()


@pytest.mark.parametrize("damage", ["hash", "count", "duplicate", "number", "bool"])
def test_bad_baseline_rejected(monkeypatch, damage):
    original = caller._git
    raw = original("show", f"{caller.BASELINE_SOURCE_COMMIT}:{caller.BASELINE_ARTIFACT_PATH}")
    document = json.loads(raw)
    if damage == "hash":
        document["START_TICKETS"][0] = [1, 2, 3, 4, 6, 21]
    elif damage == "count":
        document["START_TICKETS"].pop()
    elif damage == "duplicate":
        document["START_TICKETS"][0] = document["START_TICKETS"][1]
    elif damage == "number":
        document["START_TICKETS"][0][0] = 50
    else:
        document["START_TICKETS"][0][0] = True
    changed = json.dumps(document).encode()
    monkeypatch.setattr(caller, "BASELINE_ARTIFACT_SHA256", hashlib.sha256(changed).hexdigest())
    monkeypatch.setattr(caller, "_git", lambda *a: changed if a[0] == "show" else original(*a))
    with pytest.raises((caller.ProductionCallerError, terminal.TerminalSealError)):
        caller.load_frozen_baseline()


def test_artifact_file_identity_rejected(monkeypatch):
    monkeypatch.setattr(caller, "BASELINE_ARTIFACT_SHA256", "0" * 64)
    with pytest.raises(caller.ProductionCallerError, match="ARTIFACT_SHA256"):
        caller.load_frozen_baseline()


def test_provisioning_authority_marker_and_idempotence(root):
    original = (root.directory / caller.AUTHORITY_FILENAME).read_bytes()
    caller.provision_journal_root(root, authorized=True)
    assert (root.directory / caller.AUTHORITY_FILENAME).read_bytes() == original
    assert set(p.name for p in root.directory.iterdir()) == {caller.AUTHORITY_FILENAME}


def test_provision_requires_authorization(tmp_path, monkeypatch):
    monkeypatch.setattr(integration, "PRODUCTION_TEST_RUNTIME_ROOT", tmp_path)
    authority = integration.JournalRootAuthority(tmp_path / dispatcher.TASK_ID, testing=True)
    with pytest.raises(caller.ProductionCallerError, match="REQUIRES_AUTHORIZATION"):
        caller.provision_journal_root(authority, authorized=False)
    assert not authority.directory.exists()


@pytest.mark.parametrize(
    "damage", ["wrong_root", "symlink", "parent_symlink", "unknown", "marker", "unowned"]
)
def test_root_identity_and_unknown_contents_fail_closed(root, tmp_path, damage):
    directory = root.directory
    if damage == "wrong_root":
        root = integration.JournalRootAuthority(tmp_path / "other" / dispatcher.TASK_ID)
    elif damage in {"symlink", "parent_symlink"}:
        link = tmp_path / "link"
        link.symlink_to(directory if damage == "symlink" else tmp_path, target_is_directory=True)
        root = integration.JournalRootAuthority(
            link if damage == "symlink" else link / dispatcher.TASK_ID, testing=True
        )
    elif damage == "unknown":
        (directory / "unknown").write_bytes(b"unrecognized")
    elif damage == "marker":
        (directory / caller.AUTHORITY_FILENAME).write_bytes(b"{}\n")
    else:
        (directory / caller.AUTHORITY_FILENAME).unlink()
    with pytest.raises((RuntimeError, FileNotFoundError)):
        caller.provision_journal_root(root, authorized=True)
    assert not (directory / caller.RESULT_FILENAME).exists()


@pytest.mark.parametrize("gain", [0, 1])
def test_actual_caller_resumes_frozen_generator_and_seals_winner(root, data, gain):
    put_journal(root, data.prefix)
    evaluator = SyntheticEvaluator(gain=gain)
    result = invoke(root, evaluator=evaluator, count=dispatcher.BASELINE_COUNT + gain)
    assert evaluator.representatives == [4805]
    assert result["portfolio"]["tickets"] == [
        list(t) for t in (data.winner if gain else data.baseline)
    ]
    assert result["portfolio"]["normalized_sha256"] == (
        WINNER_SHA256 if gain else dispatcher.BASELINE_PORTFOLIO_SHA256
    )
    assert result["terminal_recount"]["real_canonical_recount"] == "NOT RUN"
    assert result["journal_identity"]["record_count"] == 430
    assert result["orbit_accounting"]["new_raw_attempts"] == 3343680
    path = root.directory / caller.RESULT_FILENAME
    assert path.read_bytes() == terminal.canonical_result_bytes(result)
    unsigned = {k: v for k, v in result.items() if k != "result_sha256"}
    assert (
        result["result_sha256"]
        == hashlib.sha256(terminal.canonical_result_bytes(unsigned)).hexdigest()
    )
    # Finished resume revalidates the result and does not call either scorer.
    monkey = pytest.MonkeyPatch()
    with monkey.context() as patch:
        patch.setattr(
            integration, "run_successor_and_seal", lambda **_: pytest.fail("finished rerun")
        )
        assert invoke(root) == result


def test_completed_resume_reconstructs_nonzero_candidate_ordinal(root, data):
    second_sha = "b5254e57057997fa72cce3e1e4aff379c089ac23d269676ffada9a2d36e91964"
    added = {
        (27, 37, 42, 44, 46, 48),
        (28, 29, 30, 31, 32, 33),
        (29, 33, 34, 39, 44, 45),
        (32, 38, 43, 45, 47, 49),
    }
    expected = tuple(sorted((set(data.baseline) - set(REMOVED)) | added))
    put_journal(root, data.journal(gain=True, identity=second_sha, ordinal=1))
    result = invoke(root, count=dispatcher.STRICT_GAIN_MINIMUM_COUNT)
    assert result["portfolio"]["tickets"] == [list(t) for t in expected]
    assert result["portfolio"]["normalized_sha256"] == second_sha


def test_interrupted_resume_equals_uninterrupted(root, data):
    prefix = b"".join(data.no_gain.splitlines(keepends=True)[:427])
    put_journal(root, prefix)
    stop = data.plan.representatives[-2].index
    with pytest.raises(InterruptedError):
        invoke(root, evaluator=SyntheticEvaluator(interrupt_index=stop))
    partial = (root.directory / dispatcher.PROGRESS_FILENAME).read_bytes()
    assert len(partial.splitlines()) == 428
    assert not (root.directory / caller.RESULT_FILENAME).exists()
    resumed = invoke(root)
    full_bytes = (root.directory / dispatcher.PROGRESS_FILENAME).read_bytes()
    # Reset only this synthetic fixture, preserving the accepted prefix bytes.
    (root.directory / caller.RESULT_FILENAME).unlink()
    put_journal(root, prefix)
    assert invoke(root) == resumed
    assert (root.directory / dispatcher.PROGRESS_FILENAME).read_bytes() == full_bytes


def test_429_gate_prevents_binding_seal_and_result(root, data, monkeypatch):
    put_journal(root, data.prefix)
    monkeypatch.setattr(
        integration,
        "run_successor",
        lambda **_: dispatcher.summarize_progress(data.manifest, data.prefix),
    )
    monkeypatch.setattr(
        caller.official, "load_official_recount", lambda: pytest.fail("partial binding")
    )
    monkeypatch.setattr(
        terminal, "seal_orbit_successor_terminal", lambda *a, **k: pytest.fail("partial seal")
    )
    with pytest.raises(integration.IntegrationError, match="COMPLETE_ACCEPTED_JOURNAL"):
        invoke(root)
    assert not (root.directory / caller.RESULT_FILENAME).exists()


@pytest.mark.parametrize("damage", ["duplicate", "hash", "truncated"])
def test_corrupt_journal_before_binding(root, data, monkeypatch, damage):
    lines = data.no_gain.splitlines(keepends=True)
    if damage == "duplicate":
        lines[1] = lines[0]
    elif damage == "hash":
        lines[0] = lines[0].replace(b'"candidate_count":1', b'"candidate_count":2')
    else:
        lines[-1] = lines[-1][:-3]
    put_journal(root, b"".join(lines))
    monkeypatch.setattr(
        integration, "run_successor_and_seal", lambda **_: pytest.fail("corrupt run")
    )
    with pytest.raises(dispatcher.DispatcherError):
        invoke(root)
    assert not (root.directory / caller.RESULT_FILENAME).exists()


@pytest.mark.parametrize("identity,ordinal", [("0" * 64, 0), (WINNER_SHA256, 1)])
def test_unverifiable_gain_or_wrong_winner_mapping_rejected(root, data, identity, ordinal):
    put_journal(root, data.journal(gain=True, identity=identity, ordinal=ordinal))
    with pytest.raises(integration.IntegrationError, match="FINAL_WINNER_SHA256_MISMATCH"):
        invoke(root, count=dispatcher.STRICT_GAIN_MINIMUM_COUNT)
    assert not (root.directory / caller.RESULT_FILENAME).exists()


def test_recount_mismatch_does_not_publish(root, data):
    put_journal(root, data.gain)
    with pytest.raises(terminal.TerminalSealError, match="recount count differs"):
        invoke(root)
    assert not (root.directory / caller.RESULT_FILENAME).exists()


def test_production_path_uses_verified_official_binding_before_enumeration(root, data, monkeypatch):
    put_journal(root, data.no_gain)
    # Exercise the same production recount branch in the isolated fixture.
    monkeypatch.setattr(integration.JournalRootAuthority, "validate", lambda *a, **k: None)
    monkeypatch.setattr(
        caller,
        "_authority_bytes",
        lambda _: (root.directory / caller.AUTHORITY_FILENAME).read_bytes(),
    )
    bound = caller.official.load_official_recount()

    class BeforeEnumeration(Exception):
        pass

    seen = []

    def stop(pool_size, draw_size):
        seen.append((pool_size, draw_size))
        raise BeforeEnumeration

    monkeypatch.setattr(bound.module, "all_main_draw_masks", stop)
    with pytest.raises(BeforeEnumeration):
        caller.run_production(journal_directory=root.directory, authorized_scientific_run=True)
    assert seen == [(49, 6)]
    assert not (root.directory / caller.RESULT_FILENAME).exists()


def test_fixed_count_cannot_replace_official_binding(root, data, monkeypatch):
    put_journal(root, data.no_gain)
    monkeypatch.setattr(
        caller.official, "load_official_recount", lambda: lambda _: dispatcher.BASELINE_COUNT
    )
    with pytest.raises(caller.official.OfficialEvaluatorBindingError):
        invoke(root)
    assert not (root.directory / caller.RESULT_FILENAME).exists()


@pytest.mark.parametrize("failure", ["file_fsync", "replace", "directory_fsync", "readback"])
def test_atomic_write_failure_has_no_valid_result(root, data, monkeypatch, failure):
    put_journal(root, data.no_gain)
    result = integration.run_successor_and_seal(
        journal_directory=root.directory,
        portfolio_tickets=data.baseline,
        journal_authority=root,
        test_evaluator=SyntheticEvaluator(),
        test_terminal_recount=lambda _: dispatcher.BASELINE_COUNT,
    )

    def fail(*args, **kwargs):
        raise OSError("synthetic atomic failure")

    with monkeypatch.context() as patch:
        if failure == "file_fsync":
            patch.setattr(os, "fsync", fail)
        elif failure == "replace":
            patch.setattr(os, "replace", fail)
        elif failure == "directory_fsync":
            patch.setattr(caller, "_fsync_directory", fail)
        else:
            original = caller._regular_bytes
            patch.setattr(
                caller,
                "_regular_bytes",
                lambda p: b"corrupt" if p.name == caller.RESULT_FILENAME else original(p),
            )
        with pytest.raises((OSError, caller.ProductionCallerError)), caller._root_lock(root):
            caller.write_terminal_result(root, result, data.manifest)
    assert not (root.directory / caller.RESULT_FILENAME).exists()
    assert not list(root.directory.glob("*.tmp"))
    assert invoke(root) == result


def test_existing_identical_result_and_conflict_fail_closed(root, data):
    put_journal(root, data.no_gain)
    result = invoke(root)
    path = root.directory / caller.RESULT_FILENAME
    original = path.read_bytes()
    with caller._root_lock(root):
        assert caller.write_terminal_result(root, result, data.manifest) == result
        changed = dict(result, extra="different result")
        changed["result_sha256"] = terminal._result_sha256(changed)
        with pytest.raises(caller.ProductionCallerError, match="EXISTING_RESULT_CONFLICT"):
            caller.write_terminal_result(root, changed, data.manifest)
    assert path.read_bytes() == original
    path.write_bytes(original.replace(b'"exact_count":313263888', b'"exact_count":313263889'))
    with pytest.raises(caller.ProductionCallerError, match="RESULT_SHA256_MISMATCH"):
        invoke(root)


def test_result_writer_rejects_partial_even_with_fake_signed_result(root, data):
    put_journal(root, data.no_gain)
    result = invoke(root)
    (root.directory / caller.RESULT_FILENAME).unlink()
    put_journal(root, data.prefix)
    with (
        pytest.raises(caller.ProductionCallerError, match="COMPLETE_ACCEPTED_JOURNAL"),
        caller._root_lock(root),
    ):
        caller.write_terminal_result(root, result, data.manifest)
    assert not (root.directory / caller.RESULT_FILENAME).exists()


def test_result_execution_mode_cannot_be_relabelled(root, data):
    put_journal(root, data.no_gain)
    result = invoke(root)
    result["terminal_recount"]["real_canonical_recount"] = "COMPLETED"
    result["result_sha256"] = terminal._result_sha256(result)
    path = root.directory / caller.RESULT_FILENAME
    path.write_bytes(terminal.canonical_result_bytes(result))
    with pytest.raises(caller.ProductionCallerError, match="RESULT_EXECUTION_MODE_MISMATCH"):
        invoke(root)
