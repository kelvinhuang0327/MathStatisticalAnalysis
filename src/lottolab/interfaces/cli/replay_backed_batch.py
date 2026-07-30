"""CLI for materializing the exact two-method legacy replay batch."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated, NoReturn, cast

import typer

from lottolab.infrastructure.replay_backed_batch_import import (
    ReplayBatchImportError,
    materialize_exact_replay_batch,
)


class ReplayBatchCliError(RuntimeError):
    """A caller-safe exact replay batch materialization failure."""


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


def build_exact_replay_batch_input(
    *,
    database: Path,
    expected_database_sha256: str,
    output_file: Path,
) -> str:
    """Materialize and atomically create one evaluator input artifact."""

    if output_file.exists():
        raise ReplayBatchCliError("refusing to overwrite existing output file")
    try:
        document = materialize_exact_replay_batch(
            database=database,
            expected_database_sha256=expected_database_sha256,
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
    except ReplayBatchImportError as exc:
        raise ReplayBatchCliError(str(exc)) from exc
    except ReplayBatchCliError:
        raise
    except OSError as exc:
        raise ReplayBatchCliError("materialization output failed") from exc

    provenance = document["source_provenance"]
    if not isinstance(provenance, dict):
        raise ReplayBatchCliError("materialization provenance is malformed")
    counts = cast(dict[str, object], provenance)["registry_execution_counts"]
    if not isinstance(counts, dict):
        raise ReplayBatchCliError("materialization counts are malformed")
    typed_counts = cast(dict[str, object], counts)
    summary: dict[str, object] = {
        "execution_count": len(cast(list[object], document["executions"])),
        "input_sha256": hashlib.sha256(content).hexdigest(),
        "output_file": str(output_file),
        "registry_execution_counts": typed_counts,
        "target_draw_count": len(cast(list[object], document["targets"])),
    }
    return _canonical_bytes(summary).decode("utf-8").rstrip("\n")


def materialize_exact_replay_batch_command(
    database: Annotated[
        Path,
        typer.Option("--database", exists=True, dir_okay=False),
    ],
    expected_database_sha256: Annotated[
        str,
        typer.Option("--expected-database-sha256"),
    ],
    output_file: Annotated[Path, typer.Option("--output-file")],
) -> None:
    """Create causal ordered-20 evaluator input for the exact replay batch."""

    try:
        typer.echo(
            build_exact_replay_batch_input(
                database=database,
                expected_database_sha256=expected_database_sha256,
                output_file=output_file,
            )
        )
    except ReplayBatchCliError as exc:
        _fail(str(exc))
    except Exception:
        _fail("materialization failed safely")


def _fail(message: str) -> NoReturn:
    typer.echo(f"materialize-biglotto-replay-batch error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "ReplayBatchCliError",
    "build_exact_replay_batch_input",
    "materialize_exact_replay_batch_command",
]
