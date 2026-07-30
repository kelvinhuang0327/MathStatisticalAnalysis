"""CLI for the wave-52 frozen source-grid BIG_LOTTO batch."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from lottolab.application.legacy_source_grid_native_portfolios_wave52 import (
    DEFAULT_SOURCE_NATIVE_WAVE52_USER_SEED,
    SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS,
)
from lottolab.infrastructure.legacy_source_grid_native_batch_import_wave52 import (
    LegacySourceGridNativeWave52BatchImportError,
    materialize_legacy_source_grid_native_wave52_batch,
)


class LegacySourceGridNativeWave52BatchCliError(RuntimeError):
    """The CLI cannot safely materialize the requested artifact."""


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def materialize_legacy_source_grid_native_wave52_batch_file(
    *,
    database: Path,
    expected_database_sha256: str,
    output_file: Path,
    user_seed: str = DEFAULT_SOURCE_NATIVE_WAVE52_USER_SEED,
) -> str:
    """Write one canonical wave-52 input atomically and refuse overwrite."""

    if output_file.exists():
        raise LegacySourceGridNativeWave52BatchCliError(
            f"refusing to overwrite existing output: {output_file}"
        )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        document = materialize_legacy_source_grid_native_wave52_batch(
            database=database,
            expected_database_sha256=expected_database_sha256,
            user_seed=user_seed,
        )
    except LegacySourceGridNativeWave52BatchImportError as exc:
        raise LegacySourceGridNativeWave52BatchCliError(str(exc)) from exc
    payload = _canonical_bytes(document)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_file.parent,
        prefix=f".{output_file.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if output_file.exists():
            raise LegacySourceGridNativeWave52BatchCliError(
                f"refusing to overwrite existing output: {output_file}"
            )
        os.replace(temporary_path, output_file)
    finally:
        temporary_path.unlink(missing_ok=True)
    executions = cast(list[dict[str, Any]], document["executions"])
    status_counts = Counter(cast(str, row["status"]) for row in executions)
    return json.dumps(
        {
            "execution_count": len(executions),
            "execution_status_counts": dict(sorted(status_counts.items())),
            "input_sha256": hashlib.sha256(payload).hexdigest(),
            "output_file": str(output_file),
            "strategy_count": len(SUPPORTED_SOURCE_NATIVE_WAVE52_METHODS),
            "target_draw_count": len(cast(list[object], document["targets"])),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def materialize_legacy_source_grid_native_wave52_batch_command(
    database: Annotated[
        Path,
        typer.Option(
            "--database",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    expected_database_sha256: Annotated[
        str,
        typer.Option("--expected-database-sha256"),
    ],
    output_file: Annotated[
        Path,
        typer.Option("--output-file", resolve_path=True),
    ],
    user_seed: Annotated[
        str,
        typer.Option("--user-seed"),
    ] = DEFAULT_SOURCE_NATIVE_WAVE52_USER_SEED,
) -> None:
    """Create causal evaluator input for the wave-52 source-grid methods."""

    try:
        summary = materialize_legacy_source_grid_native_wave52_batch_file(
            database=database,
            expected_database_sha256=expected_database_sha256,
            output_file=output_file,
            user_seed=user_seed,
        )
    except LegacySourceGridNativeWave52BatchCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(summary)


__all__ = [
    "LegacySourceGridNativeWave52BatchCliError",
    "materialize_legacy_source_grid_native_wave52_batch_command",
    "materialize_legacy_source_grid_native_wave52_batch_file",
]
