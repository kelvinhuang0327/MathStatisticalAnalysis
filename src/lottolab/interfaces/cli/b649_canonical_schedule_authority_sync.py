"""Executable pre-draw BIG_LOTTO canonical schedule-authority synchronization."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import NoReturn

import typer

from lottolab.application.future_draw_identity import FutureDrawIdentityUnavailableError
from lottolab.application.schedule_sync import (
    BIG_LOTTO_SCHEDULE_GAME_CODE,
    CanonicalScheduleAuthorityProvider,
    CanonicalScheduleAuthorityRepository,
    CanonicalScheduleAuthoritySyncResult,
    OfficialScheduleProviderError,
    ScheduleAuthorityApplyStatus,
    SynchronizeCanonicalScheduleAuthority,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteCanonicalScheduleAuthorityRepository,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider,
)


class B649CanonicalScheduleAuthorityCliError(RuntimeError):
    """One sanitized B649 canonical-authority CLI failure."""


def run_b649_canonical_schedule_authority_sync(
    *,
    environ: Mapping[str, str] | None = None,
    provider: CanonicalScheduleAuthorityProvider | None = None,
    repository: CanonicalScheduleAuthorityRepository | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[LocalDataPaths, CanonicalScheduleAuthoritySyncResult]:
    """Run the real B649 provider/use-case/repository path without schema migration."""

    selected_clock = _runtime_clock if clock is None else clock
    try:
        paths = resolve_local_data_paths(environ=environ)
        selected_provider = (
            TaiwanLotteryBigLottoCanonicalScheduleAuthorityProvider()
            if provider is None
            else provider
        )
        selected_repository = (
            SQLiteCanonicalScheduleAuthorityRepository(
                paths,
                initialize=False,
                clock=selected_clock,
            )
            if repository is None
            else repository
        )
        result = SynchronizeCanonicalScheduleAuthority(
            selected_provider,
            selected_repository,
        ).execute(observed_at=selected_clock())
        if len(result.game_results) != 1:
            raise ValueError("B649 canonical entrypoint requires exactly one game result")
        game = result.game_results[0]
        if (
            game.lottery_type is not LotteryType.BIG_LOTTO
            or game.official_game_code != BIG_LOTTO_SCHEDULE_GAME_CODE
        ):
            raise ValueError("B649 canonical entrypoint returned a non-BIG_LOTTO contract")
        return paths, result
    except B649CanonicalScheduleAuthorityCliError:
        raise
    except FutureDrawIdentityUnavailableError as exc:
        raise B649CanonicalScheduleAuthorityCliError(
            "CANONICAL_DATA_AUTHORITY_UNAVAILABLE"
        ) from exc
    except OfficialScheduleProviderError as exc:
        raise B649CanonicalScheduleAuthorityCliError(
            "B649_SCHEDULE_SOURCE_UNAVAILABLE"
        ) from exc
    except (LocalDataError, SchemaMigrationError) as exc:
        raise B649CanonicalScheduleAuthorityCliError(
            "CANONICAL_DATA_AUTHORITY_UNAVAILABLE"
        ) from exc
    except (OSError, TypeError, ValueError) as exc:
        raise B649CanonicalScheduleAuthorityCliError("B649_SCHEDULE_SYNC_INVALID") from exc


def render_b649_canonical_schedule_authority_sync(
    paths: LocalDataPaths,
    result: CanonicalScheduleAuthoritySyncResult,
) -> str:
    """Render a bounded machine-readable synchronization receipt."""

    if len(result.game_results) != 1:
        raise ValueError("B649 canonical result must contain exactly one game result")
    game = result.game_results[0]
    hashes = list(game.immutable_schedule_hashes)
    if game.inserted_count:
        disposition = "INSERTED"
    elif game.reobserved_count:
        disposition = "REOBSERVED"
    elif game.apply_status is ScheduleAuthorityApplyStatus.VETOED:
        disposition = "VETOED"
    elif game.apply_status is ScheduleAuthorityApplyStatus.CONFLICT:
        disposition = "CONFLICT"
    else:
        disposition = game.authority_status.value
    payload: dict[str, object] = {
        "canonical_database": str(paths.database),
        "command": "b649-canonical-schedule-authority-sync",
        "disposition": disposition,
        "evidence_count": game.evidence_count,
        "immutable_schedule_hash": hashes[0] if len(hashes) == 1 else None,
        "immutable_schedule_hashes": hashes,
        "inserted_count": game.inserted_count,
        "lottery_type": game.lottery_type.value,
        "official_game_code": game.official_game_code,
        "reobserved_count": game.reobserved_count,
        "run_id": game.run_id,
        "source_payload_sha256": result.source_payload_sha256,
        "observed_at": result.observed_at.isoformat().replace("+00:00", "Z"),
        "status": game.apply_status.value,
        "target_draw_numbers": list(game.target_draw_numbers),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def b649_canonical_schedule_authority_sync_command() -> None:
    """Materialize official BIG_LOTTO schedule authority before the draw outcome."""

    try:
        paths, result = run_b649_canonical_schedule_authority_sync()
    except B649CanonicalScheduleAuthorityCliError as exc:
        _fail(str(exc))
    typer.echo(render_b649_canonical_schedule_authority_sync(paths, result))
    if result.game_results[0].apply_status is not ScheduleAuthorityApplyStatus.ACCEPTED:
        raise typer.Exit(code=1)


def _runtime_clock() -> datetime:
    return datetime.now(UTC)


def _fail(code: str) -> NoReturn:
    typer.echo(f"b649-canonical-schedule-authority-sync error: {code}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "B649CanonicalScheduleAuthorityCliError",
    "b649_canonical_schedule_authority_sync_command",
    "render_b649_canonical_schedule_authority_sync",
    "run_b649_canonical_schedule_authority_sync",
]
