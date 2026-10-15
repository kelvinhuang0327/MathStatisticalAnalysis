"""Production CLI for the frozen orbit API and its durable terminal result.

Future scientific use requires separate run authorization and the explicit
``--authorized-scientific-run`` flag. This module does not acquire a heavy slot,
initialize a generation, or replace the protected Fable launcher.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lottolab.research import b649_k20_four_ticket_orbit_successor_integration_r1 as integration
from lottolab.research import b649_k20_orbit_official_evaluator_binding_r1 as official
from lottolab.research import b649_k20_orbit_successor_dispatcher_r1 as dispatcher
from lottolab.research import b649_k20_orbit_successor_terminal_seal_r1 as terminal

BASE_COMMIT = "5f6ba002e890d59245add9f344f5293049d05ed4"
BASE_TREE = "00810d28dc25fe5dfefde5d959364909535663c3"
BASELINE_SOURCE_COMMIT = "032ce592c3efd0ac4b5b82a813d157224419c794"
BASELINE_ARTIFACT_PATH = (
    "docs/research/matrix-native-results/b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
BASELINE_ARTIFACT_BLOB = "404e35563564a40bdd228dafa25fdf5b82e45812"
BASELINE_ARTIFACT_SHA256 = "3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00"
OFFICIAL_BINDING_SHA256 = "6d75e80228dd87f3496ae3bcb2b454385b37c012c061c4509916e05e9d861e51"
TERMINAL_SEAL_SHA256 = "3d688f7babfe3e71d77366fddf8d993d7086602e958ead5355e9965b93ae7081"
AUTHORITY_FILENAME = "root-authority.json"
RESULT_FILENAME = "terminal-result.json"


class ProductionCallerError(RuntimeError):
    """Fail closed without publishing a terminal result."""


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(integration.PRODUCTION_WORKTREE), *args],
        check=True,
        capture_output=True,
    ).stdout


def load_frozen_baseline() -> tuple[tuple[int, ...], ...]:
    """Read START_TICKETS only from the byte-pinned, committed artifact."""
    locator = f"{BASELINE_SOURCE_COMMIT}:{BASELINE_ARTIFACT_PATH}"
    if _git("rev-parse", locator).decode("ascii").strip() != BASELINE_ARTIFACT_BLOB:
        raise ProductionCallerError("BASELINE_ARTIFACT_BLOB_MISMATCH")
    data = _git("show", locator)
    if hashlib.sha256(data).hexdigest() != BASELINE_ARTIFACT_SHA256:
        raise ProductionCallerError("BASELINE_ARTIFACT_SHA256_MISMATCH")
    document = dispatcher._json_object(data, "pinned baseline artifact")
    portfolio, digest = terminal._normalize_portfolio(
        document.get("START_TICKETS"), label="baseline START_TICKETS"
    )
    if digest != dispatcher.BASELINE_PORTFOLIO_SHA256:
        raise ProductionCallerError("BASELINE_PORTFOLIO_SHA256_MISMATCH")
    if document.get("FINAL_COUNT") != dispatcher.BASELINE_COUNT:
        raise ProductionCallerError("BASELINE_COUNT_MISMATCH")
    return portfolio


def verify_sources() -> bytes:
    """Verify definitions and pins only; never score or enumerate outcomes."""
    expected = integration.PRODUCTION_WORKTREE / "src/lottolab/research" / Path(__file__).name
    if Path(__file__) != expected or expected.resolve(strict=True) != expected:
        raise ProductionCallerError("PRODUCTION_CALLER_SOURCE_PATH_MISMATCH")
    if _git("rev-parse", BASE_COMMIT + "^{tree}").decode().strip() != BASE_TREE:
        raise ProductionCallerError("BASE_TREE_MISMATCH")
    _git("merge-base", "--is-ancestor", BASE_COMMIT, "HEAD")
    for module, digest in (
        (official, OFFICIAL_BINDING_SHA256),
        (terminal, TERMINAL_SEAL_SHA256),
    ):
        integration._verify_reused_module(module, digest, integration.PRODUCTION_WORKTREE)
    manifest = integration.binding._stable_bytes(
        integration.PRODUCTION_WORKTREE / dispatcher.MANIFEST_RELATIVE_PATH, "ORBIT_MANIFEST"
    )
    dispatcher.load_manifest_plan(manifest)
    historical = integration.binding._stable_bytes(
        integration.binding.TASK_ROOT / "attempt-results.jsonl", "HISTORICAL_JOURNAL"
    )
    if hashlib.sha256(historical).hexdigest() != dispatcher.HISTORICAL_JOURNAL_SHA256:
        raise ProductionCallerError("HISTORICAL_JOURNAL_SHA256_MISMATCH")
    with integration._original_binding(source_worktree=integration.PRODUCTION_WORKTREE):
        pass
    return manifest


def _authority_bytes(authority: integration.JournalRootAuthority) -> bytes:
    return terminal.canonical_result_bytes(
        {
            "schema": "B649_K20_ORBIT_PRODUCTION_JOURNAL_ROOT_R1",
            "source_worktree": str(integration.PRODUCTION_WORKTREE),
            "journal_directory": str(authority.directory),
            "manifest_sha256": dispatcher.EXPECTED_MANIFEST_SHA256,
            "baseline_sha256": dispatcher.BASELINE_PORTFOLIO_SHA256,
            "mode": "SYNTHETIC_TEST" if authority.testing else "SCIENTIFIC",
        }
    )


def _regular_bytes(path: Path) -> bytes:
    return integration.binding._stable_bytes(path, "PRODUCTION_DURABLE_FILE")


def _fsync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish_bytes(directory: Path, name: str, data: bytes) -> None:
    """Caller holds the directory lock; publish with read-back or remove on error."""
    destination = directory / name
    if destination.exists() or destination.is_symlink():
        if _regular_bytes(destination) != data:
            raise ProductionCallerError("EXISTING_RESULT_CONFLICT")
        return
    fd, temporary_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=directory)
    temporary = Path(temporary_name)
    published = False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Check again immediately before replace, while holding the root lock.
        if destination.exists() or destination.is_symlink():
            raise ProductionCallerError("EXISTING_RESULT_CONFLICT")
        os.replace(temporary, destination)
        published = True
        _fsync_directory(directory)
        if _regular_bytes(destination) != data:
            raise ProductionCallerError("RESULT_READBACK_MISMATCH")
    except BaseException:
        if published:
            destination.unlink()
        raise
    finally:
        temporary.unlink(missing_ok=True)


def _validate_root(authority: integration.JournalRootAuthority) -> None:
    authority.validate(authority.directory, testing=authority.testing)
    allowed = {AUTHORITY_FILENAME, dispatcher.PROGRESS_FILENAME, RESULT_FILENAME}
    for child in authority.directory.iterdir():
        info = child.lstat()
        if (
            child.name not in allowed
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or child.is_symlink()
        ):
            raise ProductionCallerError("UNRECOGNIZED_JOURNAL_ROOT_CONTENT")
    if _regular_bytes(authority.directory / AUTHORITY_FILENAME) != _authority_bytes(authority):
        raise ProductionCallerError("JOURNAL_ROOT_MARKER_MISMATCH")


def provision_journal_root(
    authority: integration.JournalRootAuthority, *, authorized: bool
) -> None:
    """Only explicit future run authorization may create the exact durable root."""
    authority.validate(authority.directory, testing=authority.testing, must_exist=False)
    if not authorized:
        raise ProductionCallerError("ROOT_PROVISIONING_REQUIRES_AUTHORIZATION")
    directory = authority.directory
    if directory.exists():
        _validate_root(authority)
        return
    parent = directory.parent
    if parent.resolve(strict=False) != parent or parent.is_symlink():
        raise ProductionCallerError("JOURNAL_ROOT_PARENT_IDENTITY_MISMATCH")
    if not parent.exists():
        # Exactly one designated parent; no arbitrary recursive mkdir/fallback.
        parent.mkdir(mode=0o700)
        _fsync_directory(parent.parent)
    if not parent.is_dir():
        raise ProductionCallerError("JOURNAL_ROOT_PARENT_IDENTITY_MISMATCH")
    directory.mkdir(mode=0o700)
    _fsync_directory(parent)
    with _root_lock(authority, validate_marker=False):
        _publish_bytes(directory, AUTHORITY_FILENAME, _authority_bytes(authority))
    _validate_root(authority)


@contextmanager
def _root_lock(
    authority: integration.JournalRootAuthority, *, validate_marker: bool = True
) -> Iterator[None]:
    authority.validate(authority.directory, testing=authority.testing)
    fd = os.open(authority.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        # An OS lock releases on crash, so resume needs no stale-lock fallback.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        opened = os.fstat(fd)
        current = authority.directory.stat()
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise ProductionCallerError("JOURNAL_ROOT_CHANGED")
        if validate_marker:
            _validate_root(authority)
        yield
        authority.validate(authority.directory, testing=authority.testing)
        current = authority.directory.stat()
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise ProductionCallerError("JOURNAL_ROOT_CHANGED")
    finally:
        os.close(fd)


def _validate_result(
    data: bytes, manifest: bytes, journal: bytes, *, testing: bool
) -> dict[str, Any]:
    result = dispatcher._json_object(data, "terminal result")
    unsigned = {key: value for key, value in result.items() if key != "result_sha256"}
    if terminal.canonical_result_bytes(result) != data or hashlib.sha256(
        terminal.canonical_result_bytes(unsigned)
    ).hexdigest() != result.get("result_sha256"):
        raise ProductionCallerError("RESULT_SHA256_MISMATCH")
    state = dispatcher.summarize_progress(manifest, journal)
    if (
        len(state.completed_representative_indices) != dispatcher.PENDING_REPRESENTATIVES
        or state.unexecuted_representative_indices
        or state.new_raw_attempts_completed != dispatcher.EXPECTED_NEW_RAW_ATTEMPTS
        or result.get("status") != terminal.STATUS_SEALED
        or result.get("completed_scientific_seal") is not True
        or result.get("schema") != terminal.RESULT_SCHEMA
        or result.get("run_disposition") != terminal.DISPOSITION_TERMINAL
    ):
        raise ProductionCallerError("TERMINAL_REQUIRES_COMPLETE_ACCEPTED_JOURNAL")
    expected_journal = {
        "successor_journal_sha256": hashlib.sha256(journal).hexdigest(),
        "record_count": dispatcher.PENDING_REPRESENTATIVES,
        "representative_indices": list(state.completed_representative_indices),
    }
    if result.get("journal_identity") != expected_journal:
        raise ProductionCallerError("RESULT_JOURNAL_IDENTITY_MISMATCH")
    pins = result.get("source_pins", {})
    if any(
        pins.get(key) != expected
        for key, expected in {
            "repository": terminal.REPOSITORY,
            "base_commit": terminal.BASE_COMMIT,
            "base_tree": terminal.BASE_TREE,
            "manifest_sha256": dispatcher.EXPECTED_MANIFEST_SHA256,
            "historical_journal_sha256": dispatcher.HISTORICAL_JOURNAL_SHA256,
            "official_evaluator_sha256": dispatcher.EVALUATOR_SHA256,
        }.items()
    ):
        raise ProductionCallerError("RESULT_SOURCE_IDENTITY_MISMATCH")
    portfolio = result.get("portfolio", {})
    tickets, digest = terminal._normalize_portfolio(
        portfolio.get("tickets"), label="result portfolio"
    )
    if (
        digest != portfolio.get("normalized_sha256")
        or digest != state.incumbent.result_identity_sha256
        or result.get("exact_count") != state.incumbent.official_count
        or result.get("terminal_recount", {}).get("recount_count") != state.incumbent.official_count
    ):
        raise ProductionCallerError("RESULT_WINNER_IDENTITY_MISMATCH")
    winner = integration.reconstruct_final_winner(manifest, journal, load_frozen_baseline())
    if tickets != winner:
        raise ProductionCallerError("RESULT_WINNER_IDENTITY_MISMATCH")
    recount = result.get("terminal_recount", {})
    if (
        recount.get("official_evaluator_executed") is not (not testing)
        or recount.get("official_universe_enumerated") is not (not testing)
        or recount.get("real_canonical_recount") != ("NOT RUN" if testing else "COMPLETED")
        or recount.get("interface")
        != ("injected_portfolio_count" if testing else "pinned_official_evaluator")
        or result.get("synthetic_result_is_not_a_discovered_higher_winning_count") is not testing
    ):
        raise ProductionCallerError("RESULT_EXECUTION_MODE_MISMATCH")
    terminal._reject_forbidden_claims(result)
    return result


def write_terminal_result(
    authority: integration.JournalRootAuthority, result: dict[str, Any], manifest: bytes
) -> dict[str, Any]:
    """Validate, atomically publish, and verify; caller must hold the root lock."""
    _validate_root(authority)
    journal = dispatcher.JsonlProgressJournal(authority.directory).read_bytes()
    data = terminal.canonical_result_bytes(result)
    _validate_result(data, manifest, journal, testing=authority.testing)
    _publish_bytes(authority.directory, RESULT_FILENAME, data)
    return _validate_result(
        _regular_bytes(authority.directory / RESULT_FILENAME),
        manifest,
        journal,
        testing=authority.testing,
    )


def run_production(
    *,
    journal_directory: Path = integration.PRODUCTION_JOURNAL_DIRECTORY,
    authorized_scientific_run: bool = False,
    provision_root: bool = False,
    test_evaluator: integration.BoundedTestEvaluator | None = None,
    test_terminal_recount: Callable[[tuple[tuple[int, ...], ...]], int] | None = None,
) -> dict[str, Any]:
    """One caller for baseline load, durable resume, terminal seal and writer."""
    testing = test_evaluator is not None or test_terminal_recount is not None
    if testing and (test_evaluator is None or test_terminal_recount is None):
        raise ProductionCallerError("PAIRED_ISOLATED_TEST_SEAMS_REQUIRED")
    if not testing and not authorized_scientific_run:
        raise ProductionCallerError("SEPARATE_SCIENTIFIC_RUN_AUTHORIZATION_REQUIRED")
    authority = integration.JournalRootAuthority(Path(journal_directory), testing=testing)
    authority.validate(authority.directory, testing=testing, must_exist=False)
    baseline = load_frozen_baseline()
    manifest = verify_sources()
    if provision_root:
        provision_journal_root(authority, authorized=testing or authorized_scientific_run)
    with _root_lock(authority):
        journal = dispatcher.JsonlProgressJournal(authority.directory)
        dispatcher.summarize_progress(manifest, journal.read_bytes())
        result_path = authority.directory / RESULT_FILENAME
        if result_path.exists():
            return _validate_result(
                _regular_bytes(result_path), manifest, journal.read_bytes(), testing=testing
            )
        result = integration.run_successor_and_seal(
            journal_directory=authority.directory,
            portfolio_tickets=baseline,
            test_evaluator=test_evaluator,
            test_terminal_recount=test_terminal_recount,
            journal_authority=authority,
        )
        return write_terminal_result(authority, result, manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify pinned inputs without execution"
    )
    parser.add_argument(
        "--journal-directory", type=Path, default=integration.PRODUCTION_JOURNAL_DIRECTORY
    )
    parser.add_argument("--authorized-scientific-run", action="store_true")
    parser.add_argument("--provision-journal-root", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        if args.authorized_scientific_run or args.provision_journal_root:
            parser.error("--check cannot authorize execution or root provisioning")
        authority = integration.JournalRootAuthority(args.journal_directory)
        authority.validate(args.journal_directory, testing=False, must_exist=False)
        load_frozen_baseline()
        verify_sources()
        print("PINNED_INPUTS: PASS; SCIENTIFIC_EXECUTION: NOT RUN; OFFICIAL_RECOUNT: NOT RUN")
        return 0
    result = run_production(
        journal_directory=args.journal_directory,
        authorized_scientific_run=args.authorized_scientific_run,
        provision_root=args.provision_journal_root,
    )
    print(terminal.canonical_result_bytes(result).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
