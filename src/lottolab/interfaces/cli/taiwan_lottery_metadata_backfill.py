"""Operator-triggered, bounded backfill of official draw research metadata.

Fetches directly from the live official Taiwan Lottery API via
``TaiwanLotteryDrawProvider.fetch_draws_with_metadata`` and appends the
result to an explicit JSON-lines sidecar file
(:mod:`lottolab.infrastructure.persistence.draw_metadata_sidecar`). Never
writes the canonical draw database and never runs automatically -- an
operator must invoke this command explicitly with an explicit output path.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.draw_automation import (
    DrawProviderContractError,
    DrawProviderUnavailableError,
    DrawSyncRequest,
    InvalidDrawSyncRequestError,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_metadata_sidecar import (
    DrawMetadataSidecarError,
    append_metadata_jsonl,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import TaiwanLotteryDrawProvider


class TaiwanLotteryMetadataBackfillCliError(RuntimeError):
    """A caller-safe metadata backfill failure."""


def taiwan_lottery_metadata_backfill_command(
    lottery_type: Annotated[
        LotteryType, typer.Option("--lottery-type", help="Lottery type to fetch.")
    ],
    date_from: Annotated[
        str, typer.Option("--date-from", help="Inclusive start date (YYYY-MM-DD).")
    ],
    date_to: Annotated[str, typer.Option("--date-to", help="Inclusive end date (YYYY-MM-DD).")],
    output: Annotated[
        Path,
        typer.Option(
            "--output", help="Explicit absolute JSON-lines sidecar path to append to."
        ),
    ],
) -> None:
    """Fetch one bounded range and append its research metadata to ``output``.

    Uses the same bounded-range rule as the canonical draw-sync path
    (``DrawSyncRequest``) but writes only to the additive metadata sidecar --
    it never touches the canonical draw database.
    """

    try:
        parsed_date_from = date.fromisoformat(date_from)
        parsed_date_to = date.fromisoformat(date_to)
    except ValueError as exc:
        _fail(f"invalid date: {exc}")

    try:
        request = DrawSyncRequest(
            lottery_type=lottery_type, date_from=parsed_date_from, date_to=parsed_date_to
        )
    except InvalidDrawSyncRequestError as exc:
        _fail(str(exc))

    try:
        provider = TaiwanLotteryDrawProvider()
        _, metadata = provider.fetch_draws_with_metadata(
            lottery_type=request.lottery_type,
            date_from=request.date_from,
            date_to=request.date_to,
        )
        written = append_metadata_jsonl(output, metadata)
    except (DrawProviderContractError, DrawProviderUnavailableError) as exc:
        _fail(str(exc))
    except DrawMetadataSidecarError as exc:
        _fail(str(exc))

    typer.echo(
        _render_json(
            {
                "lottery_type": lottery_type.value,
                "date_from": parsed_date_from.isoformat(),
                "date_to": parsed_date_to.isoformat(),
                "fetched_count": len(metadata),
                "written_count": written,
                "output": str(output),
            }
        )
    )


def _render_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _fail(message: str) -> NoReturn:
    typer.echo(f"taiwan-lottery-metadata-backfill error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "TaiwanLotteryMetadataBackfillCliError",
    "taiwan_lottery_metadata_backfill_command",
]
