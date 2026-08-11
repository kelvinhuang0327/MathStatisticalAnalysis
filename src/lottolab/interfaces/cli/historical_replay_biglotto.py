"""Read-only operator CLI for the complete BIG_LOTTO replay universe."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.draw_data import (
    DrawDataApplicationError,
    DrawHistoryQuery,
    DrawRecord,
)
from lottolab.application.use_cases.b649_historical_replay import (
    B649HistoricalReplayRequest,
    B649HistoricalReplayResult,
    B649HistoricalReplayUseCase,
    B649IdentityStatus,
    B649RawHistoryError,
    B649ReplayContractError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    ReplayCellStatus,
    ReplayDraw,
    ReplaySourceSnapshot,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    resolve_local_data_paths,
    verify_schema_read_only,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository


class B649ReplayCliError(RuntimeError):
    """A caller-safe failure while composing or running the B649 replay."""


class B649ReplayOutputMode(StrEnum):
    SUMMARY = "SUMMARY"
    RECORDS_JSONL = "RECORDS_JSONL"


_DRAW_PAGE_SIZE = 1_000


def build_b649_replay_source_snapshot(
    *,
    paths: LocalDataPaths | None = None,
) -> ReplaySourceSnapshot:
    """Read the owner-maintained local BIG_LOTTO draw source without mutation."""

    try:
        resolved_paths = resolve_local_data_paths() if paths is None else paths
        if not verify_schema_read_only(resolved_paths):
            raise B649ReplayCliError("local BIG_LOTTO draw database is unavailable")

        repository = SQLiteDrawDataRepository(resolved_paths)
        first_page = repository.list_draws(
            DrawHistoryQuery(
                lottery_type=LotteryType.BIG_LOTTO,
                page=1,
                page_size=_DRAW_PAGE_SIZE,
            )
        )
        records = list(first_page.records)
        for page_number in range(2, first_page.total_pages + 1):
            page = repository.list_draws(
                DrawHistoryQuery(
                    lottery_type=LotteryType.BIG_LOTTO,
                    page=page_number,
                    page_size=_DRAW_PAGE_SIZE,
                )
            )
            if page.total_count != first_page.total_count:
                raise B649ReplayCliError("local BIG_LOTTO draw source changed during read")
            records.extend(page.records)
    except B649ReplayCliError:
        raise
    except (
        DrawDataApplicationError,
        LocalDataError,
        OSError,
        SchemaMigrationError,
    ) as exc:
        raise B649ReplayCliError("local BIG_LOTTO draw database is unavailable") from exc

    if not records:
        raise B649ReplayCliError("local BIG_LOTTO draw source contains no draws")

    try:
        draws = tuple(
            _replay_draw(record)
            for record in sorted(records, key=lambda row: (row.draw_date, int(row.draw_number)))
        )
    except (TypeError, ValueError, IndexError) as exc:
        raise B649ReplayCliError("local BIG_LOTTO draw source is invalid") from exc

    return ReplaySourceSnapshot(
        lottery_type=LotteryType.BIG_LOTTO,
        historical_draws=draws,
    )


def build_b649_historical_replay_result(
    *,
    raw_history_root: Path,
    strategy_id: str | None = None,
    cutoff_draw_number: str | None = None,
) -> B649HistoricalReplayResult:
    """Compose the existing B649 use case for one or all identities."""

    if strategy_id is not None and not strategy_id.strip():
        raise B649ReplayCliError("strategy ID must not be blank")
    if cutoff_draw_number is not None and not cutoff_draw_number.strip():
        raise B649ReplayCliError("cutoff draw number must not be blank")

    try:
        use_case = B649HistoricalReplayUseCase(raw_history_root)
        return use_case.execute(
            B649HistoricalReplayRequest(
                source=build_b649_replay_source_snapshot(),
                mode=HistoricalReplayMode.FULL_REPLAY,
                strategy_id=strategy_id,
                cutoff_draw_number=cutoff_draw_number,
            )
        )
    except B649ReplayCliError:
        raise
    except (B649RawHistoryError, B649ReplayContractError, ValueError) as exc:
        raise B649ReplayCliError(str(exc)) from exc


def serialize_b649_summary(result: B649HistoricalReplayResult) -> str:
    """Serialize live identity-accounting values for bounded default output."""

    payload = {
        "currently_replayable_identity_count": result.currently_replayable_identity_count,
        "historical_raw_only_identity_count": result.historical_raw_only_identity_count,
        "keep_unresolved_alias_count": result.keep_unresolved_alias_count,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "mode": result.mode.value,
        "resolved_alias_count": result.resolved_alias_count,
        "selected_strategy_count": len(result.selected_strategy_ids),
        "terminal_unavailable_identity_count": result.terminal_unavailable_identity_count,
        "total_identity_count": result.total_identity_count,
    }
    return _canonical_json(payload)


def iter_b649_record_payloads(
    result: B649HistoricalReplayResult,
) -> Iterator[dict[str, object]]:
    """Yield explicit identity/cell/ticket records without building a universe list."""

    for item in result.iter_strategy_results():
        if item.replay is None:
            yield _blocked_identity_payload(
                strategy_id=item.identity.strategy_id,
                identity_status=item.identity.status,
                reason=item.blocked_reason,
            )
            continue

        for cell in item.replay.records:
            common = {
                "actual_main_numbers": list(cell.target.main_numbers),
                "actual_special_number": cell.target.special_number,
                "identity_status": item.identity.status.value,
                "native_ticket_count": cell.expected_native_ticket_count,
                "reason": cell.reason,
                "replay_status": cell.status.value,
                "strategy_id": item.identity.strategy_id,
                "target_draw_date": cell.target.draw_date.isoformat(),
                "target_draw_number": cell.target.draw_number,
            }
            if cell.status is not ReplayCellStatus.COMPLETE:
                yield {
                    **common,
                    "is_winner": None,
                    "main_hit_count": None,
                    "predicted_main_numbers": None,
                    "prize_tier": None,
                    "special_hit": None,
                    "ticket_position": None,
                }
                continue

            for ticket, evaluation in zip(cell.tickets, cell.evaluations, strict=True):
                yield {
                    **common,
                    "is_winner": evaluation.is_winner,
                    "main_hit_count": evaluation.zone1_hits,
                    "predicted_main_numbers": list(ticket.main_numbers),
                    "prize_tier": evaluation.prize_tier,
                    "special_hit": evaluation.zone2_hit,
                    "ticket_position": ticket.ticket_position,
                }


def historical_replay_biglotto_command(
    raw_history_root: Annotated[
        Path,
        typer.Option(
            "--raw-history-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Explicit read-only B649 raw-history foundation root.",
        ),
    ],
    strategy_id: Annotated[
        str | None,
        typer.Option("--strategy-id", help="One canonical B649 identity; omit for all."),
    ] = None,
    cutoff_draw_number: Annotated[
        str | None,
        typer.Option("--cutoff-draw-number", help="Inclusive numeric replay cutoff."),
    ] = None,
    output_mode: Annotated[
        str,
        typer.Option(
            "--output-mode",
            help="SUMMARY (default) or RECORDS_JSONL for explicit streaming details.",
        ),
    ] = B649ReplayOutputMode.SUMMARY.value,
) -> None:
    """Run the read-only BIG_LOTTO historical replay operator entry point."""

    try:
        selected_mode = _parse_output_mode(output_mode)
        result = build_b649_historical_replay_result(
            raw_history_root=raw_history_root,
            strategy_id=strategy_id,
            cutoff_draw_number=cutoff_draw_number,
        )
        if selected_mode is B649ReplayOutputMode.SUMMARY:
            typer.echo(serialize_b649_summary(result))
            return

        for payload in iter_b649_record_payloads(result):
            typer.echo(_canonical_json(payload))
    except B649ReplayCliError as exc:
        _fail(str(exc))
    except Exception:
        _fail("replay request failed safely")


def _parse_output_mode(value: str) -> B649ReplayOutputMode:
    normalized = value.strip().upper().replace("-", "_")
    try:
        return B649ReplayOutputMode(normalized)
    except ValueError as exc:
        raise B649ReplayCliError(
            "output mode must be SUMMARY or RECORDS_JSONL"
        ) from exc


def _replay_draw(record: DrawRecord) -> ReplayDraw:
    if record.lottery_type is not LotteryType.BIG_LOTTO:
        raise ValueError("draw is not BIG_LOTTO")
    if len(record.special_numbers) != 1:
        raise ValueError("BIG_LOTTO draw must have exactly one special number")
    return ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=record.draw_number,
        draw_date=record.draw_date,
        main_numbers=record.main_numbers,
        special_number=record.special_numbers[0],
    )


def _blocked_identity_payload(
    *,
    strategy_id: str,
    identity_status: B649IdentityStatus,
    reason: str | None,
) -> dict[str, object]:
    return {
        "actual_main_numbers": None,
        "actual_special_number": None,
        "identity_status": identity_status.value,
        "is_winner": None,
        "main_hit_count": None,
        "native_ticket_count": None,
        "predicted_main_numbers": None,
        "prize_tier": None,
        "reason": reason,
        "replay_status": "IDENTITY_UNAVAILABLE",
        "special_hit": None,
        "strategy_id": strategy_id,
        "target_draw_date": None,
        "target_draw_number": None,
        "ticket_position": None,
    }


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _fail(message: str) -> NoReturn:
    typer.echo(f"historical-replay-biglotto error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "B649ReplayCliError",
    "B649ReplayOutputMode",
    "build_b649_historical_replay_result",
    "build_b649_replay_source_snapshot",
    "historical_replay_biglotto_command",
    "iter_b649_record_payloads",
    "serialize_b649_summary",
]
