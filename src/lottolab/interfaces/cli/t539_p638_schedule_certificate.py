"""Preview-first, hash-pinned Owner schedule-certificate CLI for T539/P638."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.schedule_certificate import (
    ManualScheduleCertificatePreview,
    ManualScheduleCertificateResult,
    ScheduleCertificateCompletedOutcomeError,
    ScheduleCertificateConflictError,
    ScheduleCertificateInputError,
    ScheduleCertificateUnavailableError,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteCanonicalScheduleAuthorityRepository,
)
from lottolab.infrastructure.t539_p638_schedule_certificate import (
    read_owner_schedule_certificate,
)

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class ScheduleCertificateCliError(RuntimeError):
    """One sanitized owner schedule-certificate CLI failure."""


def run_t539_p638_schedule_certificate(
    *,
    certificate_path: Path,
    supporting_artifact_path: Path,
    expected_certificate_sha256: str,
    apply_certificate: bool,
    environ: Mapping[str, str] | None = None,
) -> tuple[
    LocalDataPaths,
    ManualScheduleCertificatePreview | ManualScheduleCertificateResult,
]:
    """Always preview, then optionally apply the exact same hash-pinned certificate."""

    try:
        if not certificate_path.is_absolute() or not supporting_artifact_path.is_absolute():
            raise ScheduleCertificateInputError(
                "certificate and supporting artifact paths must be absolute"
            )
        if (
            type(expected_certificate_sha256) is not str
            or _SHA256.fullmatch(expected_certificate_sha256) is None
        ):
            raise ScheduleCertificateInputError(
                "expected certificate SHA-256 must be lowercase hexadecimal"
            )
        certificate = read_owner_schedule_certificate(
            certificate_path,
            supporting_artifact_path,
        )
        paths = resolve_local_data_paths(environ=environ)
        repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
        preview = repository.preview_owner_schedule_certificate(
            certificate,
            expected_certificate_sha256,
        )
        if not apply_certificate:
            return paths, preview
        return (
            paths,
            repository.apply_owner_schedule_certificate(
                certificate,
                expected_certificate_sha256,
            ),
        )
    except ScheduleCertificateConflictError:
        raise
    except ScheduleCertificateCompletedOutcomeError as exc:
        raise ScheduleCertificateCliError("COMPLETED_OUTCOME_ALREADY_EXISTS") from exc
    except ScheduleCertificateInputError as exc:
        raise ScheduleCertificateCliError("OWNER_SCHEDULE_CERTIFICATE_INVALID") from exc
    except ScheduleCertificateUnavailableError as exc:
        raise ScheduleCertificateCliError("CANONICAL_DATA_AUTHORITY_UNAVAILABLE") from exc
    except (LocalDataError, SchemaMigrationError, OSError, TypeError, ValueError) as exc:
        raise ScheduleCertificateCliError("SCHEDULE_CERTIFICATE_REQUEST_INVALID") from exc


def render_t539_p638_schedule_certificate(
    paths: LocalDataPaths,
    result: ManualScheduleCertificatePreview | ManualScheduleCertificateResult,
) -> str:
    """Render a deterministic preview or audited application receipt."""

    certificate = result.certificate
    fact = certificate.fact
    target = fact.announcement.target
    applied = isinstance(result, ManualScheduleCertificateResult)
    payload: dict[str, object] = {
        "apply_certificate_requested": applied,
        "canonical_database": str(paths.database),
        "certificate_document_sha256": certificate.certificate_document_sha256,
        "certificate_input_sha256": certificate.certificate_input_sha256,
        "certification_reason": certificate.certification_reason.value,
        "certified_at": certificate.certified_at.isoformat().replace("+00:00", "Z"),
        "certifying_authority": certificate.certifying_authority,
        "confirmed_count": result.confirmed_count if applied else 0,
        "conflict_count": result.conflict_count if applied else 0,
        "disposition": result.disposition.value,
        "draw_date": target.draw_date.isoformat(),
        "draw_number": target.draw_number,
        "immutable_schedule_hash": fact.immutable_schedule_sha256,
        "inserted_count": result.inserted_count if applied else 0,
        "lottery_type": target.lottery_type.value,
        "official_game_code": fact.official_game_code,
        "run_id": result.run_id if applied else None,
        "scheduled_at": fact.announcement.scheduled_at.isoformat().replace("+00:00", "Z"),
        "status": result.status.value if applied else "PREVIEW_ONLY",
        "supporting_artifact_sha256": certificate.supporting_artifact_sha256,
        "zero_write": not applied,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def t539_p638_schedule_certificate_command(
    certificate_path: Annotated[
        Path,
        typer.Option(
            "--certificate",
            exists=True,
            dir_okay=False,
            help="Absolute 0600 Owner schedule-certificate JSON path.",
        ),
    ],
    supporting_artifact_path: Annotated[
        Path,
        typer.Option(
            "--supporting-artifact",
            exists=True,
            dir_okay=False,
            help="Absolute 0600 exact official supporting artifact path.",
        ),
    ],
    expected_certificate_sha256: Annotated[
        str,
        typer.Option(
            "--expected-certificate-sha256",
            help="Exact lowercase SHA-256 of --certificate.",
        ),
    ],
    apply_certificate: Annotated[
        bool,
        typer.Option(
            "--apply-certificate",
            help="Apply after a successful preview; omitted means zero-write preview.",
        ),
    ] = False,
) -> None:
    """Preview or explicitly apply one canonical T539/P638 schedule certificate."""

    try:
        paths, result = run_t539_p638_schedule_certificate(
            certificate_path=certificate_path,
            supporting_artifact_path=supporting_artifact_path,
            expected_certificate_sha256=expected_certificate_sha256,
            apply_certificate=apply_certificate,
        )
    except ScheduleCertificateConflictError as exc:
        if exc.result is not None:
            paths = resolve_local_data_paths()
            typer.echo(render_t539_p638_schedule_certificate(paths, exc.result))
        _fail("SCHEDULE_AUTHORITY_CONFLICT")
    except ScheduleCertificateCliError as exc:
        _fail(str(exc))
    typer.echo(render_t539_p638_schedule_certificate(paths, result))


def _fail(code: str) -> NoReturn:
    typer.echo(f"t539-p638-schedule-certificate error: {code}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "ScheduleCertificateCliError",
    "render_t539_p638_schedule_certificate",
    "run_t539_p638_schedule_certificate",
    "t539_p638_schedule_certificate_command",
]
