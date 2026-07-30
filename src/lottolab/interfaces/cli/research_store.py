"""Thin operator CLI for creating or verifying the canonical research store."""

from __future__ import annotations

import json
from typing import Annotated, NoReturn

import typer

from lottolab.infrastructure.persistence.research_repository import (
    ResearchRepositoryError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    ResearchDataError,
    ResearchSchemaError,
    resolve_research_data_paths,
    verify_schema_read_only,
)


def research_store_command(
    create: Annotated[
        bool,
        typer.Option(
            "--create/--verify-only",
            help=(
                "Create the canonical store when absent, or verify only without "
                "creating any path."
            ),
        ),
    ] = False,
) -> None:
    """Create or fail-closed verify the canonical prediction/backtest store."""

    try:
        paths = resolve_research_data_paths()
        if create:
            repository = SQLiteResearchRepository(paths)
        else:
            if not verify_schema_read_only(paths):
                _fail("research store is absent")
            repository = SQLiteResearchRepository(paths, initialize=False)
        report = repository.verify_store()
    except (ResearchDataError, ResearchRepositoryError, ResearchSchemaError) as exc:
        _fail(str(exc))
    typer.echo(
        json.dumps(
            report.as_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    if not report.healthy:
        raise typer.Exit(code=1)


def _fail(message: str) -> NoReturn:
    typer.echo(f"research-store error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = ["research_store_command"]
