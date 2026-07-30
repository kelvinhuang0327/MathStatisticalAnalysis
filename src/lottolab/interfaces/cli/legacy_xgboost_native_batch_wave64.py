"""CLI for the wave-64 frozen XGBoost BIG_LOTTO batch."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED,
)
from lottolab.infrastructure.legacy_xgboost_native_batch_import_wave64 import (
    LegacyXGBoostNativeWave64BatchImportError,
    materialize_legacy_xgboost_native_wave64_batch,
)


class LegacyXGBoostNativeWave64BatchCliError(RuntimeError):
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


def materialize_legacy_xgboost_native_wave64_batch_file(
    *,
    history_input: Path,
    output_file: Path,
    user_seed: str = DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED,
) -> str:
    """Write one canonical wave-64 input atomically and refuse overwrite."""

    if output_file.exists():
        raise LegacyXGBoostNativeWave64BatchCliError(
            f"refusing to overwrite existing output: {output_file}"
        )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        document = materialize_legacy_xgboost_native_wave64_batch(
            history_input=history_input,
            user_seed=user_seed,
        )
    except LegacyXGBoostNativeWave64BatchImportError as exc:
        raise LegacyXGBoostNativeWave64BatchCliError(str(exc)) from exc
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
            raise LegacyXGBoostNativeWave64BatchCliError(
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
            "strategy_count": 1,
            "target_draw_count": len(
                cast(list[object], document["targets"])
            ),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def materialize_legacy_xgboost_native_wave64_batch_command(
    history_input: Annotated[
        Path,
        typer.Option(
            "--history-input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    output_file: Annotated[
        Path,
        typer.Option("--output-file", resolve_path=True),
    ],
    user_seed: Annotated[
        str,
        typer.Option("--user-seed"),
    ] = DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED,
) -> None:
    """Create causal evaluator input for the wave-64 XGBoost method."""

    try:
        summary = materialize_legacy_xgboost_native_wave64_batch_file(
            history_input=history_input,
            output_file=output_file,
            user_seed=user_seed,
        )
    except LegacyXGBoostNativeWave64BatchCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(summary)


__all__ = [
    "LegacyXGBoostNativeWave64BatchCliError",
    "materialize_legacy_xgboost_native_wave64_batch_command",
    "materialize_legacy_xgboost_native_wave64_batch_file",
]
