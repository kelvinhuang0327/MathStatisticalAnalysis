"""Explicit, target-envelope-only Historical Results import CLI."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.use_cases.import_historical_results import ImportHistoricalResults
from lottolab.domain.historical_results import HistoricalImportCommitResult, HistoricalRunStatus
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultRepository,
)
from lottolab.normalization.historical_import import (
    HistoricalImportOutcome,
    HistoricalImportVerificationResult,
    verify_and_normalize_historical_import,
)


class HistoricalImportCliError(RuntimeError):
    """A caller-safe Historical Results import failure."""


def historical_import_command(
    input_path: Annotated[Path, typer.Option("--input", help="Target-envelope JSON file.")],
    database: Annotated[
        Path,
        typer.Option("--database", help="Explicit absolute Historical Results SQLite path."),
    ],
) -> None:
    """Validate and import one target-native Historical Results envelope."""

    try:
        raw = _read_validated_input(input_path)
        _validate_database_path(database)
        verification = verify_and_normalize_historical_import(raw)
        if verification.outcome is not HistoricalImportOutcome.IMPORT_PASS:
            typer.echo(_render_verification_failure(verification))
            raise typer.Exit(code=1)
        normalized_import = verification.normalized_import
        if normalized_import is None:
            raise HistoricalImportCliError("validated import was unavailable")

        repository = SQLiteHistoricalResultRepository(database)
        result = ImportHistoricalResults(repository)(normalized_import)
    except HistoricalImportCliError as exc:
        _fail(str(exc))
    except typer.Exit:
        raise
    except Exception:
        _fail("request failed safely")

    typer.echo(_render_commit_result(result))
    if result.status is not HistoricalRunStatus.COMPLETED:
        raise typer.Exit(code=1)


def _read_validated_input(input_path: Path) -> bytes:
    raw_path = str(input_path)
    if "\x00" in raw_path:
        raise HistoricalImportCliError("input path is invalid")
    if _contains_forbidden_component(input_path):
        raise HistoricalImportCliError("input path is protected")

    try:
        metadata = os.lstat(input_path)
    except FileNotFoundError as exc:
        raise HistoricalImportCliError("input must be an existing regular file") from exc
    except OSError as exc:
        raise HistoricalImportCliError("input path could not be inspected safely") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise HistoricalImportCliError("input must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise HistoricalImportCliError("input must be a regular file")

    try:
        resolved = input_path.resolve(strict=True)
        repository_root = Path(__file__).resolve().parents[4]
    except (OSError, RuntimeError) as exc:
        raise HistoricalImportCliError("input path could not be resolved safely") from exc
    if _contains_forbidden_component(resolved) or _is_relative_to(resolved, repository_root):
        raise HistoricalImportCliError("input path is protected")

    try:
        return input_path.read_bytes()
    except OSError as exc:
        raise HistoricalImportCliError("input could not be read safely") from exc


def _validate_database_path(database: Path) -> None:
    if "\x00" in str(database):
        raise HistoricalImportCliError("database path is invalid")
    if not database.is_absolute():
        raise HistoricalImportCliError("database path must be absolute")
    if ".." in database.parts or database == Path(database.anchor):
        raise HistoricalImportCliError("database path is invalid")
    if _contains_forbidden_component(database):
        raise HistoricalImportCliError("database path is protected")
    try:
        resolved = database.resolve(strict=False)
        repository_root = Path(__file__).resolve().parents[4]
    except (OSError, RuntimeError) as exc:
        raise HistoricalImportCliError("database path could not be resolved safely") from exc
    if _contains_forbidden_component(resolved):
        raise HistoricalImportCliError("database path is protected")
    if _is_relative_to(resolved, repository_root):
        raise HistoricalImportCliError("database path must be outside the Git worktree")


def _contains_forbidden_component(path: Path) -> bool:
    return any(part.casefold() == "lotterynew" for part in path.parts)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _render_verification_failure(result: HistoricalImportVerificationResult) -> str:
    reason_code = result.findings[0].reason_code
    return _render_json(
        {
            "reason_code": reason_code,
            "status": result.outcome.value,
        }
    )


def _render_commit_result(result: HistoricalImportCommitResult) -> str:
    return _render_json(
        {
            "completed_at": result.completed_at,
            "import_identity_sha256": result.import_identity_sha256,
            "is_idempotent_replay": result.is_idempotent_replay,
            "manifest_sha256": result.manifest_sha256,
            "reason_code": result.error_code,
            "run_id": result.run_id,
            "status": result.status.value,
        }
    )


def _render_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _fail(message: str) -> NoReturn:
    typer.echo(f"import-historical-results error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "HistoricalImportCliError",
    "historical_import_command",
]
