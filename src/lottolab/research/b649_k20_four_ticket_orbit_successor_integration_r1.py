"""Join the pinned source binding and dispatcher without changing either source.

``run_successor`` is the single execution entrypoint. Its default scorer uses
the frozen baseline binder, residual, generator and official recount. Calling
that scientific path requires separate run authorization. Integration tests
may inject a bounded evaluator only in the isolated test journal directory.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Callable, Generator, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from lottolab.research import b649_k20_four_ticket_orbit_source_binding_r1 as binding
from lottolab.research import b649_k20_orbit_successor_dispatcher_r1 as dispatcher

INTEGRATION_WORKTREE = Path(
    "/Users/kelvin/.codex/worktrees/b649-k20-orbit-integration-r1/MathStatisticalAnalysis"
)
SOURCE_BINDING_SHA256 = "2789a0310ad538637457d93d6b053d7c3c24241834a1148a42b66f3d6a27d269"
DISPATCHER_SHA256 = "0880a472437f736675ed3a5fddd48d377161458dc90d02f7940dedb36b9197e7"
TEST_RUNTIME_ROOT = INTEGRATION_WORKTREE / ".integration-test-runtime"


class IntegrationError(RuntimeError):
    """The integrated source, baseline or frozen scoring contract differs."""


class BoundedTestEvaluator(Protocol):
    """Test-only residual and canonical recount seam; generation stays frozen."""

    def build_residual(self, start: Any, representative: dispatcher.Representative) -> Any: ...

    def official_count(self, portfolio: Sequence[Sequence[int]]) -> int: ...


def _verify_reused_module(module: Any, digest: str) -> None:
    path = Path(module.__file__)
    expected = INTEGRATION_WORKTREE / "src/lottolab/research" / path.name
    if path != expected or path.resolve(strict=True) != expected:
        raise IntegrationError("REUSED_MODULE_PATH_MISMATCH")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise IntegrationError("REUSED_MODULE_SHA256_MISMATCH")


@contextmanager
def _original_binding() -> Iterator[binding.SuccessorSourceBinding]:
    _verify_reused_module(binding, SOURCE_BINDING_SHA256)
    _verify_reused_module(dispatcher, DISPATCHER_SHA256)
    names = (
        binding._DRIVER_IMPORT_NAME,
        binding.OFFICIAL_IMPORT_NAME,
        binding.DEPENDENCY_IMPORT_NAME,
        binding.FOUR_TICKET_IMPORT_NAME,
    )
    previous_modules = {name: sys.modules.get(name) for name in names}
    previous_path = sys.path[:]
    previous_root = binding.SUCCESSOR_WORKTREE
    old_driver = previous_modules[binding._DRIVER_IMPORT_NAME]
    previous_ttc = getattr(
        old_driver,
        "TTC",
        binding.CANONICAL_REPOSITORY
        / ("src/lottolab/research/b649_k20_three_ticket_single_number_cycle_r1.py"),
    )
    # The unchanged loader pins its own location. Rebind that location in memory
    # only after checking the exact imported copy's original source identity.
    binding.SUCCESSOR_WORKTREE = INTEGRATION_WORKTREE
    try:
        evidence = binding.load_original_predicate_for_successor()
        yield evidence
    finally:
        driver = sys.modules.get(binding._DRIVER_IMPORT_NAME)
        if driver is not None:
            driver.TTC = previous_ttc
        binding.SUCCESSOR_WORKTREE = previous_root
        sys.path[:] = previous_path
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _score_representatives(
    evidence: binding.SuccessorSourceBinding,
    incumbent_count: int,
    test_evaluator: BoundedTestEvaluator | None,
) -> Callable[[dispatcher.Representative], dispatcher.RepresentativeEvaluation]:
    driver = evidence.driver_module
    predicate = evidence.predicate_module
    dependency = evidence.dependency_module
    tickets, _ = driver.load_baseline()
    portfolio = dependency.normalize_portfolio(
        tickets, pool_size=driver.POOL_SIZE, expected_ticket_count=driver.TICKETS
    )
    if (
        dependency.portfolio_sha256(portfolio, pool_size=driver.POOL_SIZE)
        != dispatcher.BASELINE_PORTFOLIO_SHA256
        or driver.BASELINE_COUNT != dispatcher.BASELINE_COUNT
    ):
        raise IntegrationError("FROZEN_BASELINE_MISMATCH")
    start = dependency.StartBinding(
        portfolio, driver.POOL_SIZE, driver.BASELINE_SHA256, driver.BASELINE_COUNT
    )
    draws = None
    baseline_verified = False

    def score(representative: dispatcher.Representative) -> dispatcher.RepresentativeEvaluation:
        nonlocal draws, start, baseline_verified, incumbent_count
        if test_evaluator is None:
            if draws is None:
                draws = dependency.load_draws(driver.POOL_SIZE)
                start = driver.gate_a(predicate, tickets, draws)
            residual = predicate.build_subset_residual(
                start.portfolio,
                representative.quadruple,
                pool_size=start.pool_size,
                draws=draws,
            )
        else:
            if not baseline_verified:
                if test_evaluator.official_count(start.portfolio) != dispatcher.BASELINE_COUNT:
                    raise IntegrationError("TEST_BASELINE_RECOUNT_MISMATCH")
                baseline_verified = True
            residual = test_evaluator.build_residual(start, representative)

        # This is the unchanged scan used by the original driver's worker_scan.
        scanned = predicate.scan_quadruple(start, residual, representative.quadruple)
        rows = scanned["ROWS"]
        if (
            tuple(scanned["QUADRUPLE"]) != representative.quadruple
            or scanned["RAW"] != dispatcher.RAW_ATTEMPTS_PER_REPRESENTATIVE
            or scanned["REBIND_COUNT"] != dispatcher.BASELINE_COUNT
            or scanned["RAW"] != scanned["LEGAL"] + sum(scanned["REJECTED"].values())
            or len(rows) != scanned["LEGAL"] - scanned["LOCAL_DUPLICATES"]
        ):
            raise IntegrationError("FROZEN_SCAN_ACCOUNTING_MISMATCH")
        outcomes = []
        for identity, numbers, orientation, count in rows:
            if count > incumbent_count:
                spec = predicate.RawFourCycleSpec(
                    quadruple=representative.quadruple,
                    numbers=tuple(numbers),
                    orientation=orientation,
                )
                emitted = predicate.classify_attempt(
                    start.portfolio, spec, pool_size=start.pool_size
                )
                if isinstance(emitted, str) or emitted.sha256 != identity:
                    raise IntegrationError("STRICT_GAIN_REBIND_MISMATCH")
                canonical_count = (
                    dependency.official_any_prize_outcome_count(
                        emitted.portfolio,
                        pool_size=start.pool_size,
                        draws=draws,
                    )
                    if test_evaluator is None
                    else test_evaluator.official_count(emitted.portfolio)
                )
                if canonical_count != count:
                    raise IntegrationError("STRICT_GAIN_CANONICAL_RECOUNT_MISMATCH")
                incumbent_count = count
            outcomes.append(dispatcher.CandidateOutcome(count, identity))
        return dispatcher.RepresentativeEvaluation(scanned["RAW"], outcomes)

    return score


def run_successor(
    *,
    journal_directory: Path,
    test_evaluator: BoundedTestEvaluator | None = None,
) -> dispatcher.DispatchSummary:
    """Bind original sources, score in their original order, and durably dispatch.

    The caller supplies an existing successor-specific journal directory.
    Synthetic results cannot be resumed by the default scientific scorer.
    No directory, historical record, or scientific source is created/modified.
    """

    directory = Path(journal_directory)
    resolved = directory.resolve(strict=True)
    if directory != resolved or directory.name != dispatcher.TASK_ID:
        raise IntegrationError("SUCCESSOR_JOURNAL_PATH_MISMATCH")
    is_test_directory = directory.is_relative_to(TEST_RUNTIME_ROOT)
    if test_evaluator is not None and not is_test_directory:
        raise IntegrationError("TEST_EVALUATOR_REQUIRES_ISOLATED_TEST_JOURNAL")
    if test_evaluator is None and (
        is_test_directory or directory != INTEGRATION_WORKTREE / ".task-data" / dispatcher.TASK_ID
    ):
        raise IntegrationError("SCIENTIFIC_EVALUATOR_REQUIRES_SEPARATE_SUCCESSOR_JOURNAL")
    manifest_bytes = (INTEGRATION_WORKTREE / dispatcher.MANIFEST_RELATIVE_PATH).read_bytes()
    journal = dispatcher.JsonlProgressJournal(directory)
    state = dispatcher.summarize_progress(manifest_bytes, journal.read_bytes())
    with _original_binding() as evidence:
        scorer = _score_representatives(evidence, state.incumbent.official_count, test_evaluator)
        return dispatcher.run_dispatch(
            manifest_bytes,
            journal=journal,
            score_representative=scorer,
        )


@contextmanager
def _pinned_scientific_caller() -> Generator[ModuleType]:
    """Use the original entrypoint in its pinned checkout, including its path gates.

    This terminal adapter may live in another worktree. The original entrypoint
    requires its original binding/dispatcher paths; do not relax those checks.
    """
    import lottolab.research as package

    integration_name = "_b649_orbit_original_scientific_integration_r1"
    modules = (
        (binding.__name__, SOURCE_BINDING_SHA256),
        (dispatcher.__name__, DISPATCHER_SHA256),
        (integration_name, "d775a165378f49fd049605522966943bf696bf32b288b15f26f9e957d3788478"),
    )
    previous = {name: sys.modules.get(name) for name, _ in modules}
    attributes = {
        name.rsplit(".", 1)[-1]: getattr(package, name.rsplit(".", 1)[-1], None)
        for name, _ in modules[:2]
    }
    module: ModuleType | None = None
    try:
        for name, digest in modules:
            sys.modules.pop(name, None)
            filename = (
                "b649_k20_four_ticket_orbit_successor_integration_r1.py"
                if name == integration_name
                else name.rsplit(".", 1)[-1] + ".py"
            )
            path = INTEGRATION_WORKTREE / "src/lottolab/research" / filename
            module, _path, _digest, _created = binding._load_verified_module(  # pyright: ignore[reportPrivateUsage]
                name, path, path, digest, "ORIGINAL_SCIENTIFIC_CALLER"
            )
            if name != integration_name:
                setattr(package, name.rsplit(".", 1)[-1], module)
        assert module is not None
        yield module
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
        for name, old in attributes.items():
            if old is None and hasattr(package, name):
                delattr(package, name)
            elif old is not None:
                setattr(package, name, old)


def run_successor_and_seal(
    *,
    journal_directory: Path,
    portfolio_tickets: object,
    test_evaluator: BoundedTestEvaluator | None = None,
    test_terminal_recount: Callable[[tuple[tuple[int, ...], ...]], int] | None = None,
) -> dict[str, Any]:
    """Delegate the frozen run, then bind the official evaluator at terminal only.

    Production accepts no recount callback. Both test seams require the isolated
    test directory; their seals continue to say that real recount was NOT RUN.
    The result is returned to the caller; no result file is written here.
    """
    from lottolab.research import b649_k20_orbit_official_evaluator_binding_r1 as official
    from lottolab.research import b649_k20_orbit_successor_terminal_seal_r1 as terminal

    directory = Path(journal_directory)
    if directory != directory.resolve(strict=True):
        raise IntegrationError("SUCCESSOR_JOURNAL_PATH_MISMATCH")
    testing = test_evaluator is not None or test_terminal_recount is not None
    if testing and (
        test_evaluator is None
        or test_terminal_recount is None
        or not directory.is_relative_to(TEST_RUNTIME_ROOT)
    ):
        raise IntegrationError("TERMINAL_TEST_SEAMS_REQUIRE_ISOLATED_TEST_JOURNAL")

    with _pinned_scientific_caller() as original:
        summary = original.run_successor(journal_directory=directory, test_evaluator=test_evaluator)
    manifest_bytes = (INTEGRATION_WORKTREE / dispatcher.MANIFEST_RELATIVE_PATH).read_bytes()
    journal = dispatcher.JsonlProgressJournal(directory)
    journal_bytes = journal.read_bytes()
    accepted = dispatcher.summarize_progress(manifest_bytes, journal_bytes)
    if (
        asdict(summary) != asdict(accepted)
        or len(accepted.completed_representative_indices) != dispatcher.PENDING_REPRESENTATIVES
        or accepted.unexecuted_representative_indices
        or accepted.new_raw_attempts_completed != dispatcher.EXPECTED_NEW_RAW_ATTEMPTS
    ):
        raise IntegrationError("TERMINAL_REQUIRES_COMPLETE_ACCEPTED_JOURNAL")

    # No evaluator import or recount capability is created for a partial prefix.
    recount = official.require_official_binding(official.load_official_recount())
    terminal_recount: Callable[[tuple[tuple[int, ...], ...]], int] = recount
    if testing:
        assert test_terminal_recount is not None
        terminal_recount = test_terminal_recount
    result = terminal.seal_orbit_successor_terminal(
        manifest_bytes,
        journal_bytes,
        (binding.TASK_ROOT / "attempt-results.jsonl").read_bytes(),
        portfolio_tickets,
        terminal.certified_coverage_mapping(manifest_bytes),
        evaluator_bytes=recount.evaluator_bytes,
        recount=terminal_recount,
        run_disposition=terminal.DISPOSITION_TERMINAL,
        source_commit=terminal.BASE_COMMIT,
        source_tree=terminal.BASE_TREE,
    )
    if journal.read_bytes() != journal_bytes:
        raise IntegrationError("TERMINAL_JOURNAL_CHANGED_DURING_RECOUNT")
    return result
