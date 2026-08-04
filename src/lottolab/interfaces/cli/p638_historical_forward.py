"""CLI for the offline P638 R4 -> Historical Results V2 forwarder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from lottolab.infrastructure.persistence.p638_historical_forwarder import (
    P638ForwardingError,
    P638HistoricalForwarder,
)


def forward_p638_historical_command(
    source_replay_db: Annotated[
        Path, typer.Option("--source-replay-db", help="Pinned read-only P638 R4 replay DB.")
    ],
    source_draw_db: Annotated[
        Path, typer.Option("--source-draw-db", help="Pinned read-only P638 draw authority DB.")
    ],
    database: Annotated[
        Path,
        typer.Option("--database", help="Explicit task-owned Historical Results V2 DB."),
    ],
) -> None:
    """Forward P638 replay results and exclusions without network or source writes."""

    try:
        result = P638HistoricalForwarder(
            source_replay_db=source_replay_db,
            source_draw_db=source_draw_db,
            output_db=database,
        ).forward()
    except P638ForwardingError as exc:
        typer.echo(json.dumps({"status": "FAILED", "error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "status": "COMPLETED",
                "run_id": result.run_id,
                "import_identity_sha256": result.import_identity_sha256,
                "strategy_count": result.strategy_count,
                "draw_count": result.draw_count,
                "forwarded_target_count": result.forwarded_target_count,
                "forwarded_complete_target_count": result.forwarded_complete_target_count,
                "forwarded_excluded_target_count": result.forwarded_excluded_target_count,
                "forwarded_failed_target_count": result.forwarded_failed_target_count,
                "forwarded_ticket_count": result.forwarded_ticket_count,
                "excluded_strategy_count": result.excluded_strategy_count,
                "is_idempotent_replay": result.is_idempotent_replay,
            },
            sort_keys=True,
        )
    )


__all__ = ["forward_p638_historical_command"]
