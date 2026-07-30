"""Thin CLI composition for the sealed BIG_LOTTO reference import."""

from __future__ import annotations

import json
import signal
import subprocess
import threading
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.legacy_reference_import import (
    BigLottoLegacyReferenceImporter,
    LegacyReferenceImportError,
)
from lottolab.infrastructure.persistence.research_repository import (
    ResearchRepositoryError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    DATA_DIRECTORY_ENV,
    ResearchDataError,
    ResearchSchemaError,
    resolve_research_data_paths,
)


def import_biglotto_legacy_reference_command(
    corpus_root: Annotated[
        Path,
        typer.Option(
            "--corpus-root",
            help="Absolute sealed LOTTOLAB_LEGACY_REFERENCE_CORPUS_V1 path.",
        ),
    ],
    data_dir: Annotated[
        Path,
        typer.Option(
            "--data-dir",
            help=(
                "Explicit task-owned import destination. Required. This "
                "command never falls back to the default canonical research "
                "store or to an ambient LOTTOLAB_DATA_DIR."
            ),
        ),
    ],
    include_duration_samples: Annotated[
        bool,
        typer.Option(
            "--include-duration-samples",
            help="Include per-target timings for controlled shakedown evidence.",
        ),
    ] = False,
) -> None:
    """Import or resume the sealed BIG_LOTTO reference baseline into an
    explicitly selected scratch destination; never the default canonical store."""

    stop_requested = threading.Event()
    previous_handler = signal.getsignal(signal.SIGTERM)

    def request_safe_stop(_signum: int, _frame: object) -> None:
        stop_requested.set()

    signal.signal(signal.SIGTERM, request_safe_stop)
    try:
        paths = resolve_research_data_paths(
            environ={DATA_DIRECTORY_ENV: str(data_dir)}
        )
        repository = SQLiteResearchRepository(paths)
        source_commit_oid = _resolve_source_commit_oid()
        result = BigLottoLegacyReferenceImporter(repository).execute(
            corpus_root,
            source_commit_oid=source_commit_oid,
            stop_requested=stop_requested,
        )
    except (
        LegacyReferenceImportError,
        ResearchDataError,
        ResearchRepositoryError,
        ResearchSchemaError,
    ) as exc:
        _fail(str(exc))
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
    typer.echo(
        json.dumps(
            result.as_dict(include_duration_samples=include_duration_samples),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    if result.interrupted:
        raise typer.Exit(code=75)


def _resolve_source_commit_oid() -> str:
    repository_root = Path(__file__).resolve().parents[4]
    try:
        status = subprocess.run(
            ["git", "-C", str(repository_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LegacyReferenceImportError(
            "repository identity could not be resolved"
        ) from exc
    if status.stdout:
        raise LegacyReferenceImportError(
            "repository must be clean so source_commit_oid identifies importer bytes"
        )
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LegacyReferenceImportError(
            "repository identity could not be resolved"
        ) from exc
    return result.stdout.strip()


def _fail(message: str) -> NoReturn:
    typer.echo(f"legacy-reference-import error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = ["import_biglotto_legacy_reference_command"]
