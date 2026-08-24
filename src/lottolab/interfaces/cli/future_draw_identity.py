"""Owner-only preview/commit CLI for one canonical future draw identity."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.future_draw_identity import (
    FutureDrawIdentityConflictError,
    FutureDrawIdentityNotFutureError,
    FutureDrawIdentityPreviewConflictError,
    FutureDrawIdentityUnavailableError,
    ManualFutureDrawIdentitySupplementPreview,
    ManualFutureDrawIdentitySupplementResult,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteManualFutureDrawIdentitySupplementRepository,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    TargetAnnouncementAuthorityError,
    read_owner_certified_future_draw_identity_input,
    select_owner_certified_future_draw_identity,
)

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class FutureDrawIdentityCliError(RuntimeError):
    """One sanitized manual-supplement CLI failure."""


def run_future_draw_identity_supplement(
    *,
    input_path: Path,
    expected_input_sha256: str,
    lottery_type: LotteryType,
    draw_number: str,
    commit: bool,
    environ: Mapping[str, str] | None = None,
) -> tuple[
    LocalDataPaths,
    ManualFutureDrawIdentitySupplementPreview
    | ManualFutureDrawIdentitySupplementResult,
]:
    """Parse, select, preview, and only then optionally commit one target."""

    try:
        if not input_path.is_absolute():
            raise TargetAnnouncementAuthorityError("manual supplement input must be absolute")
        if _SHA256.fullmatch(expected_input_sha256) is None:
            raise TargetAnnouncementAuthorityError(
                "expected input SHA-256 must be 64 lowercase hexadecimal characters"
            )
        parsed_input = read_owner_certified_future_draw_identity_input(input_path)
        selected_target = select_owner_certified_future_draw_identity(
            parsed_input,
            lottery_type=lottery_type,
            draw_number=draw_number,
        )
        paths = resolve_local_data_paths(environ=environ)
        repository = SQLiteManualFutureDrawIdentitySupplementRepository(paths)
        if commit:
            result = repository.apply_owner_certified_supplement(
                parsed_input,
                selected_target,
                expected_input_sha256,
            )
        else:
            result = repository.preview_owner_certified_supplement(
                parsed_input,
                selected_target,
                expected_input_sha256,
            )
        return paths, result
    except FutureDrawIdentityConflictError:
        raise
    except FutureDrawIdentityPreviewConflictError as exc:
        raise FutureDrawIdentityCliError("IDENTITY_CONFLICT") from exc
    except FutureDrawIdentityNotFutureError as exc:
        raise FutureDrawIdentityCliError("NOT_A_FUTURE_IDENTITY") from exc
    except FutureDrawIdentityUnavailableError as exc:
        raise FutureDrawIdentityCliError("CANONICAL_DATA_AUTHORITY_UNAVAILABLE") from exc
    except TargetAnnouncementAuthorityError as exc:
        raise FutureDrawIdentityCliError("OWNER_CERTIFIED_INPUT_INVALID") from exc
    except (LocalDataError, SchemaMigrationError) as exc:
        raise FutureDrawIdentityCliError("CANONICAL_DATA_AUTHORITY_UNAVAILABLE") from exc
    except (OSError, TypeError, ValueError) as exc:
        raise FutureDrawIdentityCliError("MANUAL_SUPPLEMENT_REQUEST_INVALID") from exc


def render_future_draw_identity_supplement(
    paths: LocalDataPaths,
    result: ManualFutureDrawIdentitySupplementPreview
    | ManualFutureDrawIdentitySupplementResult,
) -> str:
    """Render an outcome-free preview or audited commit receipt."""

    announcement = result.announcement
    committed = isinstance(result, ManualFutureDrawIdentitySupplementResult)
    payload: dict[str, object] = {
        "canonical_database": str(paths.database),
        "commit_requested": committed,
        "conflict_count": result.conflict_count if committed else 0,
        "disposition": result.disposition.value,
        "draw_date": announcement.target.draw_date.isoformat(),
        "draw_number": announcement.target.draw_number,
        "input_sha256": result.input_sha256,
        "inserted_count": result.inserted_count if committed else 0,
        "lottery_type": announcement.target.lottery_type.value,
        "normalized_announcement_hash": result.normalized_announcement_hash,
        "run_id": result.run_id if committed else None,
        "scheduled_at": announcement.scheduled_at.isoformat().replace("+00:00", "Z"),
        "skipped_count": result.skipped_count if committed else 0,
        "status": result.status.value if committed else "PREVIEW_ONLY",
        "zero_write": not committed,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def supplement_future_draw_identity_command(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            dir_okay=False,
            help="Absolute owner-certified announcement JSON input.",
        ),
    ],
    expected_input_sha256: Annotated[
        str,
        typer.Option(
            "--expected-input-sha256",
            help="Exact 64-character lowercase SHA-256 of --input.",
        ),
    ],
    lottery_type: Annotated[
        LotteryType,
        typer.Option(
            "--lottery-type",
            case_sensitive=True,
            help="Must be BIG_LOTTO for this manual supplement contract.",
        ),
    ],
    draw_number: Annotated[
        str,
        typer.Option(
            "--draw-number",
            help="Explicit official draw number; never inferred.",
        ),
    ],
    commit: Annotated[
        bool,
        typer.Option(
            "--commit",
            help="Commit the previewed target; omitted means zero-write preview.",
        ),
    ] = False,
) -> None:
    """Preview or explicitly commit one audited canonical future draw identity."""

    try:
        paths, result = run_future_draw_identity_supplement(
            input_path=input_path,
            expected_input_sha256=expected_input_sha256,
            lottery_type=lottery_type,
            draw_number=draw_number,
            commit=commit,
        )
    except FutureDrawIdentityConflictError as exc:
        paths = resolve_local_data_paths()
        typer.echo(render_future_draw_identity_supplement(paths, exc.result))
        _fail("IDENTITY_CONFLICT")
    except FutureDrawIdentityCliError as exc:
        _fail(str(exc))
    typer.echo(render_future_draw_identity_supplement(paths, result))


def _fail(code: str) -> NoReturn:
    typer.echo(f"supplement-future-draw-identity error: {code}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "FutureDrawIdentityCliError",
    "render_future_draw_identity_supplement",
    "run_future_draw_identity_supplement",
    "supplement_future_draw_identity_command",
]
