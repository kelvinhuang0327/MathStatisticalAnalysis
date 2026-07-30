"""CLI for the fifteenth frozen source-native BIG_LOTTO batch."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from lottolab.application.legacy_source_native_portfolios_wave15 import (
    DEFAULT_SOURCE_NATIVE_WAVE15_USER_SEED,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave15 import (
    LegacySourceNativeWave15BatchImportError,
    materialize_legacy_source_native_wave15_batch,
)


class LegacySourceNativeWave15BatchCliError(RuntimeError):
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


def materialize_legacy_source_native_wave15_batch_file(
    *,
    database: Path,
    expected_database_sha256: str,
    output_file: Path,
    user_seed: str = DEFAULT_SOURCE_NATIVE_WAVE15_USER_SEED,
) -> str:
    """Write one canonical wave-15 artifact atomically and refuse overwrite."""

    if output_file.exists():
        raise LegacySourceNativeWave15BatchCliError(
            f"refusing to overwrite existing output: {output_file}"
        )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        document = materialize_legacy_source_native_wave15_batch(
            database=database,
            expected_database_sha256=expected_database_sha256,
            user_seed=user_seed,
        )
    except LegacySourceNativeWave15BatchImportError as exc:
        raise LegacySourceNativeWave15BatchCliError(str(exc)) from exc
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
            raise LegacySourceNativeWave15BatchCliError(
                f"refusing to overwrite existing output: {output_file}"
            )
        os.replace(temporary_path, output_file)
    finally:
        temporary_path.unlink(missing_ok=True)

    executions = cast(list[dict[str, Any]], document["executions"])
    status_counts = Counter(
        cast(str, row["status"]) for row in executions
    )
    return json.dumps(
        {
            "execution_count": len(executions),
            "execution_status_counts": dict(
                sorted(status_counts.items())
            ),
            "input_sha256": hashlib.sha256(payload).hexdigest(),
            "output_file": str(output_file),
            "target_draw_count": len(
                cast(list[object], document["targets"])
            ),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def materialize_legacy_source_native_wave15_batch_command(
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
    ] = DEFAULT_SOURCE_NATIVE_WAVE15_USER_SEED,
) -> None:
    """Create causal evaluator input for the fifteenth source-native batch."""

    try:
        summary = materialize_legacy_source_native_wave15_batch_file(
            database=database,
            expected_database_sha256=expected_database_sha256,
            output_file=output_file,
            user_seed=user_seed,
        )
    except LegacySourceNativeWave15BatchCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(summary)


__all__ = [
    "LegacySourceNativeWave15BatchCliError",
    "materialize_legacy_source_native_wave15_batch_command",
    "materialize_legacy_source_native_wave15_batch_file",
]
