"""Synthetic terminal routes only. Never enumerate the real official universe."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lottolab.research import b649_k20_four_ticket_orbit_successor_integration_r1 as caller
from lottolab.research import b649_k20_orbit_official_evaluator_binding_r1 as official
from lottolab.research import b649_k20_orbit_successor_dispatcher_r1 as dispatcher
from lottolab.research import b649_k20_orbit_successor_terminal_seal_r1 as seal


class MemoryJournal:
    def __init__(self) -> None:
        self.data = b""

    def read_bytes(self) -> bytes:
        return self.data

    def append_line(self, expected_previous: bytes, line: bytes) -> None:
        assert expected_previous == self.data
        self.data += line


class NoScientificWork:
    def build_residual(self, start: Any, representative: dispatcher.Representative) -> Any:
        pytest.fail("a completed synthetic journal must never generate a candidate")

    def official_count(self, portfolio: Sequence[Sequence[int]]) -> int:
        pytest.fail("a completed synthetic journal must never score a candidate")


@pytest.fixture(scope="module")
def data() -> SimpleNamespace:
    manifest = (caller.INTEGRATION_WORKTREE / dispatcher.MANIFEST_RELATIVE_PATH).read_bytes()
    baseline = json.loads(manifest)["baseline"]["normalized_tickets"]
    improvement = copy.deepcopy(baseline)
    improvement[0] = [1, 2, 3, 4, 6, 21]
    normalized = sorted(sorted(ticket) for ticket in improvement)
    identity = hashlib.sha256(json.dumps(normalized, separators=(",", ":")).encode()).hexdigest()
    assert identity != dispatcher.BASELINE_PORTFOLIO_SHA256

    def journal(gain: bool) -> bytes:
        memory = MemoryJournal()

        def score(representative: Any) -> Any:
            return dispatcher.RepresentativeEvaluation(
                7776,
                [
                    dispatcher.CandidateOutcome(
                        dispatcher.STRICT_GAIN_MINIMUM_COUNT if gain else dispatcher.BASELINE_COUNT,
                        identity,
                    )
                ],
            )

        dispatcher.run_dispatch(manifest, journal=memory, score_representative=score)
        return memory.data

    return SimpleNamespace(
        manifest=manifest,
        baseline=baseline,
        improvement=improvement,
        no_gain=journal(False),
        strict=journal(True),
        identity=identity,
    )


@pytest.fixture
def route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: Any) -> Any:
    """Call the real pinned run_successor on already complete synthetic journals."""
    directory = tmp_path / dispatcher.TASK_ID
    directory.mkdir()
    monkeypatch.setattr(caller, "TEST_RUNTIME_ROOT", tmp_path)
    original_context = caller._pinned_scientific_caller  # pyright: ignore[reportPrivateUsage]
    calls: list[str] = []
    control: dict[str, Any] = {}

    @contextmanager
    def pinned() -> Any:
        with original_context() as original:
            monkeypatch.setattr(original, "TEST_RUNTIME_ROOT", tmp_path)
            original_run = original.run_successor

            def run(**kwargs: Any) -> Any:
                calls.append("original.run_successor")
                if "failure" in control:
                    raise control["failure"]
                if control.get("partial"):
                    return dispatcher.summarize_progress(data.manifest, path.read_bytes())
                # The production terminal test substitutes only the upstream run's
                # test seam. Its terminal caller/binding/seal are the real path.
                kwargs["test_evaluator"] = NoScientificWork()
                return original_run(**kwargs)

            monkeypatch.setattr(original, "run_successor", run)
            yield original

    monkeypatch.setattr(caller, "_pinned_scientific_caller", pinned)
    path = directory / dispatcher.PROGRESS_FILENAME

    def invoke(
        *,
        journal: bytes | None = None,
        tickets: Any = None,
        count: int = dispatcher.BASELINE_COUNT,
        production: bool = False,
    ) -> Any:
        path.write_bytes(data.no_gain if journal is None else journal)

        def recount(portfolio: Any) -> int:
            calls.append("synthetic.recount")
            expected = tuple(sorted(tuple(sorted(row)) for row in tickets or data.baseline))
            assert expected == portfolio
            return count

        kwargs: dict[str, Any] = (
            {}
            if production
            else {
                "test_evaluator": NoScientificWork(),
                "test_terminal_recount": recount,
            }
        )
        return caller.run_successor_and_seal(
            journal_directory=directory,
            portfolio_tickets=data.baseline if tickets is None else tickets,
            **kwargs,
        )

    return SimpleNamespace(invoke=invoke, calls=calls, control=control, path=path)


def test_1_actual_caller_complete_synthetic_terminal_path(route: Any) -> None:
    result = route.invoke()
    assert result["status"] == seal.STATUS_SEALED
    assert result["journal_identity"]["record_count"] == 430
    assert result["orbit_accounting"]["historical_covered_orbits"] == 240
    assert result["orbit_accounting"]["new_covered_orbits"] == 430
    assert result["orbit_accounting"]["new_raw_attempts"] == 3343680
    assert route.calls == ["original.run_successor", "synthetic.recount"]
    assert result["terminal_recount"]["real_canonical_recount"] == "NOT RUN"


def test_2_real_terminal_route_enters_pinned_evaluator_without_full_recount(
    route: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound = official.load_official_recount()
    assert bound.module.__file__ is not None
    assert Path(bound.module.__file__) == official.source.OFFICIAL_SOURCE_PATH
    assert bound._evaluate is bound.module.evaluate_portfolio  # pyright: ignore[reportPrivateUsage]
    assert hashlib.sha256(bound.evaluator_bytes).hexdigest() == dispatcher.EVALUATOR_SHA256
    calls: list[tuple[int, int]] = []

    class BeforeEnumeration(Exception):
        pass

    def stop(pool_size: int, draw_size: int) -> Any:
        calls.append((pool_size, draw_size))
        raise BeforeEnumeration

    monkeypatch.setattr(bound.module, "all_main_draw_masks", stop)
    with pytest.raises(BeforeEnumeration):
        route.invoke(production=True)
    assert calls == [(49, 6)]
    assert "synthetic.recount" not in route.calls


@pytest.mark.parametrize("swap", ["loader", "evaluate", "binding_call"])
def test_3_fixed_count_swap_rejected_and_4_restored_binding_passes(
    route: Any,
    monkeypatch: pytest.MonkeyPatch,
    swap: str,
) -> None:
    bound = official.load_official_recount()
    with monkeypatch.context() as patch:

        def fixed(*args: Any, **kwargs: Any) -> int:
            return dispatcher.BASELINE_COUNT

        if swap == "loader":
            patch.setattr(official, "load_official_recount", lambda: fixed)
        elif swap == "evaluate":
            patch.setattr(bound.module, "evaluate_portfolio", fixed)
        else:
            patch.setattr(official.OfficialRecountBinding, "__call__", fixed)
        with pytest.raises(official.OfficialEvaluatorBindingError):
            route.invoke(production=True)
        assert "synthetic.recount" not in route.calls
    assert route.invoke()["status"] == seal.STATUS_SEALED


def test_5_partial_429_never_constructs_official_binding(
    route: Any,
    data: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route.control["partial"] = True
    monkeypatch.setattr(official, "load_official_recount", lambda: pytest.fail("partial binding"))
    prefix = b"".join(data.no_gain.splitlines(keepends=True)[:429])
    with pytest.raises(caller.IntegrationError, match="COMPLETE_ACCEPTED_JOURNAL"):
        route.invoke(journal=prefix)
    assert "synthetic.recount" not in route.calls


def test_6_completed_binding_occurs_after_journal_acceptance(
    route: Any,
    monkeypatch: pytest.MonkeyPatch,
    data: Any,
) -> None:
    load = official.load_official_recount

    def checked() -> Any:
        state = dispatcher.summarize_progress(data.manifest, route.path.read_bytes())
        assert len(state.completed_representative_indices) == 430
        assert state.unexecuted_representative_indices == ()
        assert route.calls == ["original.run_successor"]
        return load()

    monkeypatch.setattr(official, "load_official_recount", checked)
    route.invoke()


@pytest.mark.parametrize("damage", ["duplicate", "missing", "order", "truncated", "manifest"])
def test_7_invalid_journal_never_constructs_binding_or_recounts(
    route: Any,
    data: Any,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    lines = data.no_gain.splitlines(keepends=True)
    if damage == "duplicate":
        lines[1] = lines[0]
    elif damage == "missing":
        lines.pop(1)
    elif damage == "order":
        lines[0], lines[1] = lines[1], lines[0]
    elif damage == "truncated":
        lines[-1] = lines[-1][:-3]
    else:
        lines[0] = lines[0].replace(dispatcher.EXPECTED_MANIFEST_SHA256.encode(), b"0" * 64)
    monkeypatch.setattr(official, "load_official_recount", lambda: pytest.fail("corrupt binding"))
    with pytest.raises(ValueError):
        route.invoke(journal=b"".join(lines))
    assert "synthetic.recount" not in route.calls


def test_interrupted_upstream_never_constructs_binding(
    route: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route.control["failure"] = InterruptedError("synthetic interruption")
    monkeypatch.setattr(
        official, "load_official_recount", lambda: pytest.fail("interrupted binding")
    )
    with pytest.raises(InterruptedError):
        route.invoke()


def test_8_recount_count_mismatch_fails_closed(route: Any) -> None:
    with pytest.raises(seal.TerminalSealError, match="recount count differs"):
        route.invoke(count=dispatcher.BASELINE_COUNT + 1)


def test_9_tie_preserves_baseline_and_10_gain_uses_improvement(route: Any, data: Any) -> None:
    tied = route.invoke()
    assert tied["portfolio"]["normalized_sha256"] == dispatcher.BASELINE_PORTFOLIO_SHA256
    assert tied["scientific_classification"] == "NO_GAIN"
    gained = route.invoke(
        journal=data.strict,
        tickets=data.improvement,
        count=dispatcher.STRICT_GAIN_MINIMUM_COUNT,
    )
    assert gained["portfolio"]["normalized_sha256"] == data.identity
    assert gained["portfolio"]["normalized_sha256"] != dispatcher.BASELINE_PORTFOLIO_SHA256
    assert gained["scientific_classification"] == "STRICT_GAIN"
    assert gained["launch_time_incumbent"]["replaced"] is True
    assert dispatcher.is_strict_gain(313263888) is False
    assert dispatcher.is_strict_gain(313263889) is True
    with pytest.raises(seal.TerminalSealError, match="normalized SHA-256"):
        route.invoke(journal=data.strict, count=dispatcher.STRICT_GAIN_MINIMUM_COUNT)


@pytest.mark.parametrize("wrong", ["bytes", "file", "spec", "capability"])
def test_11_wrong_evaluator_identity_fails_closed(
    route: Any,
    monkeypatch: pytest.MonkeyPatch,
    wrong: str,
) -> None:
    bound = official.load_official_recount()
    if wrong == "bytes":
        monkeypatch.setattr(official.source, "OFFICIAL_SOURCE_SHA256", "0" * 64)
    elif wrong == "file":
        monkeypatch.setattr(bound.module, "__file__", str(Path(__file__).resolve()))
    elif wrong == "spec":
        monkeypatch.setattr(bound.module.__spec__, "origin", str(Path(__file__).resolve()))
    else:

        def fixed(portfolio: Any) -> int:
            return 1

        forged = official.OfficialRecountBinding(bound.module, bound.evaluator_bytes, fixed)
        monkeypatch.setattr(official, "load_official_recount", lambda: forged)
    # The pinned original loader has its own SourceBindingError class instance.
    errors = (RuntimeError, official.OfficialEvaluatorBindingError)
    with pytest.raises(errors, match=r"SHA256_MISMATCH|WRONG_MODULE_PATH|BINDING_CHANGED"):
        route.invoke(production=True)


def test_12_deterministic_seal_binds_source_portfolio_and_digest(route: Any) -> None:
    first = route.invoke()
    second = route.invoke()
    assert seal.canonical_result_bytes(first) == seal.canonical_result_bytes(second)
    assert first["source_pins"]["official_evaluator_sha256"] == dispatcher.EVALUATOR_SHA256
    assert first["source_pins"]["manifest_sha256"] == dispatcher.EXPECTED_MANIFEST_SHA256
    assert first["source_pins"]["historical_journal_sha256"] == dispatcher.HISTORICAL_JOURNAL_SHA256
    unsigned = {key: value for key, value in first.items() if key != "result_sha256"}
    expected = hashlib.sha256(seal.canonical_result_bytes(unsigned)).hexdigest()
    assert first["result_sha256"] == expected


def test_test_callback_cannot_enter_production_directory(tmp_path: Path) -> None:
    with pytest.raises(caller.IntegrationError, match="TEST_SEAMS_REQUIRE_ISOLATED"):
        caller.run_successor_and_seal(
            journal_directory=tmp_path,
            portfolio_tickets=[],
            test_terminal_recount=lambda _: dispatcher.BASELINE_COUNT,
        )
