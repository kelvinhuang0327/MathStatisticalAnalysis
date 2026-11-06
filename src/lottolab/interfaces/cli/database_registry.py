"""Typer adapter for the audited database registry persistence operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.infrastructure.persistence.database_registry import (
    RegistryError,
    add_writable,
    backfill_changelog,
    remove_writable,
    verify_registry,
)
from lottolab.infrastructure.persistence.project_database_paths import canonical_project_root

app = typer.Typer(
    no_args_is_help=True, help="Verify or auditably edit the project database registry."
)


@app.command("verify")
def verify_command() -> None:
    """Read-only compare of database-locations.json and its changelog."""
    try:
        result = verify_registry(canonical_project_root())
    except RegistryError as exc:
        _fail(exc)
    typer.echo(
        " ".join(
            (
                f"status={result.status}",
                f"registry_sha256={result.registry_sha256 or 'null'}",
                f"changelog_after_sha256={result.changelog_after_sha256 or 'null'}",
                f"task_id={result.task_id or 'null'}",
            )
        )
    )
    if result.exit_code:
        raise typer.Exit(code=result.exit_code)


@app.command("add-writable")
def add_writable_command(
    database_filename: str,
    task_id: Annotated[str, typer.Option("--task-id", help="Task identifier authorized to write.")],
    authorization_file: Annotated[
        Path,
        typer.Option("--authorization-file", help="Absolute path to the authorization sentence."),
    ],
) -> None:
    """Add a DB filename to writable_databases."""
    try:
        result = add_writable(
            canonical_project_root(),
            database_filename,
            task_id=task_id,
            authorization_file=authorization_file,
            repository_root=_repository_root(),
        )
    except RegistryError as exc:
        _fail(exc)
    typer.echo(
        f"status=RECORDED operation=add before_sha256={result.before_sha256} "
        f"after_sha256={result.after_sha256} task_id={result.task_id}"
    )


@app.command("remove-writable")
def remove_writable_command(
    database_filename: str,
    task_id: Annotated[str, typer.Option("--task-id", help="Task identifier authorized to write.")],
    authorization_file: Annotated[
        Path,
        typer.Option("--authorization-file", help="Absolute path to the authorization sentence."),
    ],
) -> None:
    """Remove a DB filename from writable_databases."""
    try:
        result = remove_writable(
            canonical_project_root(),
            database_filename,
            task_id=task_id,
            authorization_file=authorization_file,
            repository_root=_repository_root(),
        )
    except RegistryError as exc:
        _fail(exc)
    typer.echo(
        f"status=RECORDED operation=remove before_sha256={result.before_sha256} "
        f"after_sha256={result.after_sha256} task_id={result.task_id}"
    )


@app.command("backfill")
def backfill_command(
    entries: Annotated[
        Path,
        typer.Option(
            "--entries", exists=True, dir_okay=False, help="JSON array of history entries."
        ),
    ],
    task_id: Annotated[str, typer.Option("--task-id", help="Task identifier authorized to write.")],
    authorization_file: Annotated[
        Path,
        typer.Option("--authorization-file", help="Absolute path to the authorization sentence."),
    ],
) -> None:
    """Append validated historical registry change entries."""
    try:
        result = backfill_changelog(
            canonical_project_root(),
            entries,
            task_id=task_id,
            authorization_file=authorization_file,
            repository_root=_repository_root(),
        )
    except RegistryError as exc:
        _fail(exc)
    typer.echo(
        f"status=RECORDED operation=backfill entries={result.entries_written} "
        f"before_sha256={result.before_sha256} after_sha256={result.after_sha256} "
        f"task_id={result.task_id}"
    )


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _fail(error: RegistryError) -> NoReturn:
    typer.echo(f"{error.status}: {error}", err=True)
    raise typer.Exit(code=error.exit_code) from error
