"""CLI for the frozen Core-Satellite and Zone Split backtest batch."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, NoReturn, cast

import typer

from lottolab.application.legacy_random_native_portfolios import DEFAULT_USER_SEED
from lottolab.infrastructure.legacy_random_batch_import import (
    LegacyRandomBatchImportError,
    materialize_legacy_random_native_batch,
)


class LegacyRandomBatchCliError(RuntimeError):
    """A caller-safe random-native batch materialization failure."""


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def build_legacy_random_native_batch_input(
    *,
    database: Path,
    expected_database_sha256: str,
    output_file: Path,
    user_seed: str = DEFAULT_USER_SEED,
) -> str:
    """Materialize and atomically create one evaluator input artifact."""

    if output_file.exists():
        raise LegacyRandomBatchCliError(
            "refusing to overwrite existing output file"
        )
    try:
        document = materialize_legacy_random_native_batch(
            database=database,
            expected_database_sha256=expected_database_sha256,
            user_seed=user_seed,
        )
        content = _canonical_bytes(document)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_file.with_name(
            f".{output_file.name}.tmp-{os.getpid()}"
        )
        try:
            with temporary.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, output_file)
        finally:
            temporary.unlink(missing_ok=True)
    except LegacyRandomBatchImportError as exc:
        raise LegacyRandomBatchCliError(str(exc)) from exc
    except LegacyRandomBatchCliError:
        raise
    except OSError as exc:
        raise LegacyRandomBatchCliError(
            "materialization output failed"
        ) from exc

    provenance = document.get("source_provenance")
    if not isinstance(provenance, dict):
        raise LegacyRandomBatchCliError("materialization provenance is malformed")
    status_counts = cast(
        dict[str, object],
        provenance,
    ).get("execution_status_counts")
    if not isinstance(status_counts, dict):
        raise LegacyRandomBatchCliError("execution status counts are malformed")
    summary: dict[str, object] = {
        "execution_count": len(cast(list[object], document["executions"])),
        "execution_status_counts": cast(dict[str, object], status_counts),
        "input_sha256": hashlib.sha256(content).hexdigest(),
        "output_file": str(output_file),
        "target_draw_count": len(cast(list[object], document["targets"])),
    }
    return _canonical_bytes(summary).decode("utf-8").rstrip("\n")


def materialize_legacy_random_native_batch_command(
    database: Annotated[
        Path,
        typer.Option("--database", exists=True, dir_okay=False),
    ],
    expected_database_sha256: Annotated[
        str,
        typer.Option("--expected-database-sha256"),
    ],
    output_file: Annotated[Path, typer.Option("--output-file")],
    user_seed: Annotated[
        str,
        typer.Option("--user-seed"),
    ] = DEFAULT_USER_SEED,
) -> None:
    """Create causal evaluator input for two frozen random-native methods."""

    try:
        typer.echo(
            build_legacy_random_native_batch_input(
                database=database,
                expected_database_sha256=expected_database_sha256,
                output_file=output_file,
                user_seed=user_seed,
            )
        )
    except LegacyRandomBatchCliError as exc:
        _fail(str(exc))
    except Exception:
        _fail("materialization failed safely")


def _fail(message: str) -> NoReturn:
    typer.echo(
        f"materialize-biglotto-random-native-batch error: {message}",
        err=True,
    )
    raise typer.Exit(code=1)


__all__ = [
    "LegacyRandomBatchCliError",
    "build_legacy_random_native_batch_input",
    "materialize_legacy_random_native_batch_command",
]
