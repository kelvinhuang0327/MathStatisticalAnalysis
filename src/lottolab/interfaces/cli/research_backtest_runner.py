"""Thin explicit-path CLI composition for the BIG_LOTTO research backtest."""

from __future__ import annotations

import json
import os
import signal
import threading
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.research_backtest_runner import (
    BigLottoResearchBacktestManifest,
    ResearchBacktestError,
    ResearchBacktestInputError,
    RunBigLottoResearchBacktest,
)
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    build_production_generate_ordered_candidate_emission,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATABASE_FILENAME as DRAW_DATABASE_FILENAME,
)
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.infrastructure.persistence.ordered_candidate_materialization_reader import (
    SQLiteOrderedCandidateMaterializationReader,
)
from lottolab.infrastructure.persistence.research_repository import (
    ResearchRepositoryError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    RESEARCH_DATABASE_FILENAME,
    ResearchDataError,
    ResearchDataPaths,
    ResearchSchemaError,
)
from lottolab.infrastructure.strategy_source_provenance import (
    PythonStrategySourceIdentityResolver,
    resolve_repository_source_commit_oid,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

SAFE_PAUSE_EXIT_CODE = 75
_PRODUCTION_RESEARCH_DIRECTORY = (
    Path.home() / "Library" / "Application Support" / "LottoLab"
)


class ResearchBacktestCliError(RuntimeError):
    """Caller-safe explicit-path composition failure."""

    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        super().__init__(message)


def run_biglotto_research_backtest_command(
    manifest_file: Annotated[
        Path,
        typer.Option(
            "--manifest-file",
            help="Absolute canonical BIG_LOTTO R1 manifest file.",
        ),
    ],
    draw_data_dir: Annotated[
        Path,
        typer.Option(
            "--draw-data-dir",
            help="Absolute existing draw-data directory opened read-only.",
        ),
    ],
    research_data_dir: Annotated[
        Path,
        typer.Option(
            "--research-data-dir",
            help="Absolute existing task-owned research destination.",
        ),
    ],
) -> None:
    """Run, safely pause, resume, or no-op one explicit manifest."""

    stop_requested = threading.Event()
    previous_handler = signal.getsignal(signal.SIGTERM)

    def request_safe_stop(_signum: int, _frame: object) -> None:
        stop_requested.set()

    signal.signal(signal.SIGTERM, request_safe_stop)
    try:
        manifest_path, draw_directory, research_directory = _validate_paths(
            manifest_file,
            draw_data_dir,
            research_data_dir,
        )
        try:
            manifest_bytes = manifest_path.read_bytes()
        except OSError as exc:
            raise ResearchBacktestCliError(
                "MANIFEST_FILE_UNREADABLE",
                "manifest file could not be read",
            ) from exc
        manifest = BigLottoResearchBacktestManifest.from_canonical_file_bytes(
            manifest_bytes
        )
        repository_root = Path(__file__).resolve().parents[4]
        draw_paths = LocalDataPaths(
            draw_directory,
            draw_directory / DRAW_DATABASE_FILENAME,
        )
        research_paths = ResearchDataPaths(
            research_directory,
            research_directory / RESEARCH_DATABASE_FILENAME,
        )
        catalog = production_catalog()
        executable_registry = ExecutableRegistry(catalog)
        result = RunBigLottoResearchBacktest(
            repository_factory=lambda: SQLiteResearchRepository(
                research_paths
            ),
            source_reader=SQLiteOrderedCandidateMaterializationReader(
                draw_paths
            ),
            catalog=catalog,
            executable_registry=executable_registry,
            generate_ordered_candidate_emission=(
                build_production_generate_ordered_candidate_emission()
            ),
            source_commit_resolver=lambda: (
                resolve_repository_source_commit_oid(repository_root)
            ),
            strategy_source_identity_resolver=(
                PythonStrategySourceIdentityResolver(repository_root)
            ),
        ).execute(
            manifest,
            stop_requested=stop_requested,
        )
    except ResearchBacktestInputError as exc:
        payload: dict[str, object] = {
            "message": str(exc),
            "reason_code": exc.reason_code,
            "status": "ERROR",
        }
        if exc.target_draw is not None:
            payload["target_draw"] = exc.target_draw
        _fail(payload)
    except ResearchBacktestCliError as exc:
        _fail(
            {
                "message": str(exc),
                "reason_code": exc.reason_code,
                "status": "ERROR",
            }
        )
    except (
        ResearchBacktestError,
        ResearchDataError,
        ResearchRepositoryError,
        ResearchSchemaError,
    ) as exc:
        _fail(
            {
                "message": str(exc),
                "reason_code": "RESEARCH_BACKTEST_FAILED",
                "status": "ERROR",
            }
        )
    except Exception:
        _fail(
            {
                "message": "research backtest failed safely",
                "reason_code": "UNEXPECTED_FAILURE",
                "status": "ERROR",
            }
        )
    finally:
        signal.signal(signal.SIGTERM, previous_handler)

    typer.echo(_canonical_json(result.as_dict()))
    if result.interrupted:
        raise typer.Exit(code=SAFE_PAUSE_EXIT_CODE)


def _validate_paths(
    manifest_file: Path,
    draw_data_dir: Path,
    research_data_dir: Path,
) -> tuple[Path, Path, Path]:
    for value, name in (
        (manifest_file, "manifest-file"),
        (draw_data_dir, "draw-data-dir"),
        (research_data_dir, "research-data-dir"),
    ):
        if not value.is_absolute():
            raise ResearchBacktestCliError(
                f"{name.upper().replace('-', '_')}_NOT_ABSOLUTE",
                f"{name} must be an absolute path",
            )
    manifest_path = Path(os.path.abspath(manifest_file))
    draw_directory = Path(os.path.abspath(draw_data_dir))
    research_directory = Path(os.path.abspath(research_data_dir))
    production_directory = Path(os.path.abspath(_PRODUCTION_RESEARCH_DIRECTORY))
    if research_directory == production_directory:
        raise ResearchBacktestCliError(
            "PRODUCTION_RESEARCH_PATH_FORBIDDEN",
            "the production canonical research destination is forbidden",
        )
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ResearchBacktestCliError(
            "MANIFEST_FILE_MISSING",
            "manifest-file must name an existing regular file",
        )
    if not draw_directory.is_dir() or draw_directory.is_symlink():
        raise ResearchBacktestCliError(
            "DRAW_DATA_DIR_MISSING",
            "draw-data-dir must name an existing directory",
        )
    if not research_directory.is_dir() or research_directory.is_symlink():
        raise ResearchBacktestCliError(
            "RESEARCH_DATA_DIR_MISSING",
            "research-data-dir must name an existing directory",
        )
    manifest_path = manifest_path.resolve(strict=True)
    draw_directory = draw_directory.resolve(strict=True)
    research_directory = research_directory.resolve(strict=True)
    if research_directory == production_directory:
        raise ResearchBacktestCliError(
            "PRODUCTION_RESEARCH_PATH_FORBIDDEN",
            "the production canonical research destination is forbidden",
        )
    return manifest_path, draw_directory, research_directory


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _fail(payload: dict[str, object]) -> NoReturn:
    typer.echo(_canonical_json(payload), err=True)
    raise typer.Exit(code=1)


__all__ = [
    "SAFE_PAUSE_EXIT_CODE",
    "ResearchBacktestCliError",
    "run_biglotto_research_backtest_command",
]
