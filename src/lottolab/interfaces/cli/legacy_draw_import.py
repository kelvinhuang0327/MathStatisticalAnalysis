"""Explicit CLI adapter for the legacy single- and multi-file draw importer."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from lottolab.application.draw_data import RepositoryBusyError, RepositoryUnavailableError
from lottolab.application.use_cases.batch_draw_imports import (
    BATCH_PARSER_VERSION,
    CommitBatchDrawImport,
    InvalidBatchDrawImportError,
    PreviewBatchDrawImport,
)
from lottolab.domain.batch_imports import BatchDrawImportPreview, ImportFilePayload
from lottolab.infrastructure.imports.batch_files import preview_import_batch
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository


def legacy_draw_import_command(
    inputs: Annotated[
        list[Path],
        typer.Option(
            "--input",
            exists=True,
            dir_okay=False,
            readable=True,
            help="One explicit CSV, TXT, or ZIP input; repeat for a multi-file batch.",
        ),
    ],
    database: Annotated[
        Path,
        typer.Option(
            "--database",
            help="Explicit task-owned SQLite database path for the commit.",
        ),
    ],
    preview_only: Annotated[
        bool,
        typer.Option("--preview-only", help="Parse and report without writing the database."),
    ] = False,
) -> None:
    """Preview or commit explicit legacy draw files in bounded transactions."""

    if not inputs:
        _fail("at least one --input is required")
    try:
        payloads = tuple(ImportFilePayload(path.name, path.read_bytes()) for path in inputs)
        preview = PreviewBatchDrawImport(preview_import_batch).execute(payloads)
        if preview_only:
            typer.echo(render_legacy_draw_import_preview(preview))
            if not preview.is_valid:
                raise typer.Exit(code=1)
            return
        if not preview.is_valid:
            typer.echo(render_legacy_draw_import_preview(preview))
            raise typer.Exit(code=1)
        paths = LocalDataPaths(data_directory=database.parent, database=database)
        repository = SQLiteDrawDataRepository(paths)
        commit = CommitBatchDrawImport(
            preview_import_batch,
            lambda: repository,
        ).execute(
            payloads=payloads,
            expected_manifest_sha256=preview.manifest_sha256,
            parser_version=BATCH_PARSER_VERSION,
        )
    except InvalidBatchDrawImportError as exc:
        typer.echo(render_legacy_draw_import_preview(exc.preview))
        raise typer.Exit(code=1) from exc
    except (
        OSError,
        LocalDataError,
        SchemaMigrationError,
        RepositoryBusyError,
        RepositoryUnavailableError,
    ) as exc:
        _fail(str(exc))
    typer.echo(
        json.dumps(asdict(commit), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def render_legacy_draw_import_preview(preview: BatchDrawImportPreview) -> str:
    """Render bounded per-file statuses and counters without normalized row payloads."""

    payload: dict[str, Any] = {
        "is_valid": preview.is_valid,
        "manifest_sha256": preview.manifest_sha256,
        "parser_version": BATCH_PARSER_VERSION,
        "summary": asdict(preview.summary),
        "files": [asdict(file) for file in preview.files],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _fail(message: str) -> NoReturn:
    typer.echo(f"import-legacy-draw-files error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = ["legacy_draw_import_command", "render_legacy_draw_import_preview"]
