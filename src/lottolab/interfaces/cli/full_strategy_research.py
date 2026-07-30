"""CLI export for the complete BIG_LOTTO research-strategy universe."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalogError,
    ReplayBatchMappingStatus,
    load_full_strategy_catalog,
)

CATALOG_JSON_FILENAME = "biglotto_full_strategy_catalog.json"
CATALOG_CSV_FILENAME = "biglotto_full_strategy_catalog.csv"
PROGRESS_JSON_FILENAME = "biglotto_full_strategy_progress.json"
CHECKSUM_FILENAME = "SHA256SUMS"
_OUTPUT_FILENAMES = (
    CATALOG_JSON_FILENAME,
    CATALOG_CSV_FILENAME,
    PROGRESS_JSON_FILENAME,
    CHECKSUM_FILENAME,
)


class FullStrategyResearchCliError(RuntimeError):
    """A caller-safe full-strategy research export failure."""


def _canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def export_full_strategy_research_catalog(output_directory: Path) -> str:
    """Write deterministic JSON/CSV/progress/checksums without overwriting files."""

    try:
        catalog = load_full_strategy_catalog()
    except FullStrategyCatalogError as exc:
        raise FullStrategyResearchCliError("packaged catalog validation failed") from exc

    try:
        if output_directory.exists() and not output_directory.is_dir():
            raise FullStrategyResearchCliError("output path exists and is not a directory")
        output_directory.mkdir(parents=True, exist_ok=True)
        existing = [
            filename
            for filename in _OUTPUT_FILENAMES
            if (output_directory / filename).exists()
        ]
        if existing:
            raise FullStrategyResearchCliError(
                "refusing to overwrite existing output: " + ",".join(existing)
            )

        catalog_json = catalog.canonical_json_bytes()
        catalog_csv = catalog.canonical_csv_bytes()
        progress_payload = {
            "catalog_sha256": catalog.catalog_sha256,
            "first_batch_exact_mapping_count": sum(
                mapping.mapping_status
                is ReplayBatchMappingStatus.EXACT_SOURCE_SYMBOL_MATCH
                for mapping in catalog.first_batch_mappings
            ),
            "first_batch_is_full_universe": False,
            "first_batch_owner_decision_required_mapping_count": sum(
                mapping.mapping_status
                is ReplayBatchMappingStatus.OWNER_DECISION_REQUIRED
                for mapping in catalog.first_batch_mappings
            ),
            "first_batch_strategy_count": len(catalog.first_batch_strategy_ids),
            "frozen_source_commit": catalog.frozen_source_commit,
            "full_universe_complete": catalog.full_universe_complete,
            "lottery_type": "BIG_LOTTO",
            "progress": catalog.progress.canonical_dict(),
            "research_disclaimer": catalog.research_disclaimer,
        }
        progress_json = _canonical_json_bytes(progress_payload)
        content_by_name = {
            CATALOG_CSV_FILENAME: catalog_csv,
            CATALOG_JSON_FILENAME: catalog_json,
            PROGRESS_JSON_FILENAME: progress_json,
        }
        checksums = "".join(
            f"{hashlib.sha256(content).hexdigest()}  {filename}\n"
            for filename, content in sorted(content_by_name.items())
        ).encode("ascii")
        content_by_name[CHECKSUM_FILENAME] = checksums

        temporary_paths: list[Path] = []
        try:
            for filename, content in content_by_name.items():
                temporary = output_directory / f".{filename}.tmp-{os.getpid()}"
                temporary_paths.append(temporary)
                with temporary.open("xb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            for filename in _OUTPUT_FILENAMES:
                os.replace(
                    output_directory / f".{filename}.tmp-{os.getpid()}",
                    output_directory / filename,
                )
        finally:
            for temporary in temporary_paths:
                temporary.unlink(missing_ok=True)
    except FullStrategyResearchCliError:
        raise
    except OSError as exc:
        raise FullStrategyResearchCliError("catalog export failed") from exc

    summary = {
        "catalog_sha256": catalog.catalog_sha256,
        "full_universe_complete": catalog.full_universe_complete,
        "output_directory": str(output_directory),
        **catalog.progress.canonical_dict(),
    }
    return _canonical_json_bytes(summary).decode("utf-8").rstrip("\n")


def export_full_strategy_research_catalog_command(
    output_directory: Annotated[Path, typer.Option("--output-directory")],
) -> None:
    """Export the audited 221-method research universe with checksums."""

    try:
        typer.echo(export_full_strategy_research_catalog(output_directory))
    except FullStrategyResearchCliError as exc:
        _fail(str(exc))
    except Exception:
        _fail("catalog export failed safely")


def _fail(message: str) -> NoReturn:
    typer.echo(f"export-biglotto-strategy-universe error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "CATALOG_CSV_FILENAME",
    "CATALOG_JSON_FILENAME",
    "CHECKSUM_FILENAME",
    "PROGRESS_JSON_FILENAME",
    "FullStrategyResearchCliError",
    "export_full_strategy_research_catalog",
    "export_full_strategy_research_catalog_command",
]
