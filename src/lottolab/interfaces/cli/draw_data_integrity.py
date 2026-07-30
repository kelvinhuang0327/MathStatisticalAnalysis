"""Official read-only root-CLI adapter for the P337 draw-data integrity inspection core.

This module exposes ``draw_data_integrity_command`` through the LottoLab root
CLI. It holds no database-checking logic of its own -- it only composes the
already merged ``InspectDrawDataIntegrity`` use case with
``SQLiteDrawDataIntegrityReader`` and renders the closed report as compact,
deterministic JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.use_cases.inspect_draw_data_integrity import (
    InspectDrawDataIntegrity,
    InspectDrawDataIntegrityRequest,
)
from lottolab.domain.draw_data_integrity import DrawDataIntegrityReport, DrawDataIntegrityStatus
from lottolab.infrastructure.persistence.draw_data_integrity_reader import (
    SQLiteDrawDataIntegrityReader,
)
from lottolab.infrastructure.persistence.draw_schema import LocalDataError, SchemaMigrationError


class DrawDataIntegrityCliError(RuntimeError):
    """A sanitized, caller-safe draw-data integrity CLI failure."""


def inspect_draw_data_integrity_report(database: Path) -> DrawDataIntegrityReport:
    """Run exactly one read-only inspection of the explicitly supplied database."""

    try:
        return InspectDrawDataIntegrity(SQLiteDrawDataIntegrityReader()).execute(
            InspectDrawDataIntegrityRequest(database=database)
        )
    except (LocalDataError, SchemaMigrationError) as exc:
        raise DrawDataIntegrityCliError(str(exc)) from exc
    except Exception as exc:
        raise DrawDataIntegrityCliError("inspection failed safely") from exc


def render_draw_data_integrity_report(report: DrawDataIntegrityReport) -> str:
    """Render the closed report as one compact, key-sorted, deterministic JSON line."""

    payload = {
        "status": report.status.value,
        "schema_version": report.schema_version,
        "table_counts": [
            {"table_name": entry.table_name, "row_count": entry.row_count}
            for entry in report.table_counts
        ],
        "lottery_summaries": [
            {
                "lottery_type": entry.lottery_type,
                "draw_count": entry.draw_count,
                "first_draw_number": entry.first_draw_number,
                "first_draw_date": entry.first_draw_date,
                "last_draw_number": entry.last_draw_number,
                "last_draw_date": entry.last_draw_date,
            }
            for entry in report.lottery_summaries
        ],
        "findings": [
            {"code": finding.code.value, "count": finding.count} for finding in report.findings
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def draw_data_integrity_command(
    database: Annotated[
        Path,
        typer.Option(
            "--database",
            help="Explicit absolute path to a draw-data SQLite database.",
        ),
    ],
) -> None:
    """Report read-only draw-data integrity for one explicitly supplied database."""

    try:
        report = inspect_draw_data_integrity_report(database)
    except DrawDataIntegrityCliError as exc:
        _fail(str(exc))

    typer.echo(render_draw_data_integrity_report(report))
    if report.status is not DrawDataIntegrityStatus.HEALTHY:
        raise typer.Exit(code=1)


def _fail(message: str) -> NoReturn:
    typer.echo(f"inspect-draw-data-integrity error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "DrawDataIntegrityCliError",
    "draw_data_integrity_command",
    "inspect_draw_data_integrity_report",
    "render_draw_data_integrity_report",
]
