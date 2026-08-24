"""Operator CLI for the canonical multi-lottery pre-outcome binding."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Annotated, NoReturn

import typer

from lottolab.application.future_draw_identity import FutureDrawIdentityUnavailableError
from lottolab.application.pre_outcome_target import (
    CorruptAuthorityError,
    InvalidOutcomeAbsenceAttestationError,
    InvalidScheduleTimeError,
    OutcomeAlreadyAvailableError,
    PreOutcomeTargetAuthorityError,
    TargetConflictError,
)
from lottolab.application.pre_outcome_target_operational import (
    CausalHistoryAuthorityError,
    OperationalRegistrationResult,
    OutcomePresenceEvidenceUnavailableError,
    PreOutcomeTargetOperationalError,
    TargetAnnouncementAuthorityError,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    SchemaMigrationError,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    PreOutcomeTargetOperationalComposition,
    compose_pre_outcome_target_operational_service,
)
from lottolab.infrastructure.pre_outcome_target_store import (
    FileSystemPreOutcomeTargetAuthorityStore,
)


class PreOutcomeTargetCliError(RuntimeError):
    """One sanitized operational registration failure."""


def run_pre_outcome_target_registration(
    lottery_type: LotteryType,
    *,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[PreOutcomeTargetOperationalComposition, OperationalRegistrationResult]:
    """Compose and execute one explicit earliest-target registration attempt."""

    try:
        composition = compose_pre_outcome_target_operational_service(
            environ=environ,
            clock=clock,
        )
        return composition, composition.service.register_earliest(lottery_type)
    except TargetAnnouncementAuthorityError as exc:
        raise PreOutcomeTargetCliError("TARGET_ANNOUNCEMENT_AUTHORITY_INVALID") from exc
    except OutcomePresenceEvidenceUnavailableError as exc:
        raise PreOutcomeTargetCliError("OUTCOME_PRESENCE_EVIDENCE_UNAVAILABLE") from exc
    except CausalHistoryAuthorityError as exc:
        raise PreOutcomeTargetCliError("CAUSAL_HISTORY_AUTHORITY_INVALID") from exc
    except OutcomeAlreadyAvailableError as exc:
        raise PreOutcomeTargetCliError("TARGET_OUTCOME_ALREADY_AVAILABLE") from exc
    except TargetConflictError as exc:
        raise PreOutcomeTargetCliError("TARGET_REGISTRATION_CONFLICT") from exc
    except (InvalidScheduleTimeError, InvalidOutcomeAbsenceAttestationError) as exc:
        raise PreOutcomeTargetCliError("TARGET_PRE_OUTCOME_WINDOW_INVALID") from exc
    except CorruptAuthorityError as exc:
        raise PreOutcomeTargetCliError("TARGET_AUTHORITY_CORRUPT") from exc
    except (
        FutureDrawIdentityUnavailableError,
        LocalDataError,
        SchemaMigrationError,
    ) as exc:
        raise PreOutcomeTargetCliError("OPERATIONAL_DATA_AUTHORITY_UNAVAILABLE") from exc
    except (PreOutcomeTargetAuthorityError, PreOutcomeTargetOperationalError) as exc:
        raise PreOutcomeTargetCliError("OPERATIONAL_REGISTRATION_REJECTED") from exc
    except (OSError, TypeError, ValueError) as exc:
        raise PreOutcomeTargetCliError("OPERATIONAL_BINDING_INVALID") from exc


def render_pre_outcome_target_registration(
    composition: PreOutcomeTargetOperationalComposition,
    result: OperationalRegistrationResult,
    lottery_type: LotteryType,
) -> str:
    """Render an outcome-free deterministic registration receipt."""

    payload: dict[str, object] = {
        "authority_root": str(composition.paths.authority_root),
        "future_identity_database": str(composition.paths.local_data.database),
        "lottery_type": lottery_type.value,
        "status": result.status.value,
    }
    if result.registration is None:
        payload.update(
            {
                "causal_history": None,
                "record_path": None,
                "record_sha256": None,
                "registration": None,
                "target": None,
            }
        )
    else:
        assert result.announcement is not None
        assert result.causal_history is not None
        record_path = FileSystemPreOutcomeTargetAuthorityStore.record_path_for(
            composition.paths.authority_root,
            result.registration.target,
        )
        payload.update(
            {
                "causal_history": result.causal_history.canonical_dict(),
                "record_path": str(record_path),
                "record_sha256": (
                    FileSystemPreOutcomeTargetAuthorityStore.canonical_record_sha256(
                        result.registration
                    )
                ),
                "registration": result.registration.canonical_dict(),
                "target": result.announcement.canonical_dict(),
            }
        )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def register_pre_outcome_target_command(
    lottery_type: Annotated[
        LotteryType,
        typer.Option(
            "--lottery-type",
            case_sensitive=True,
            help=(
                "Exact lottery identity: BIG_LOTTO, DAILY_539, or POWER_LOTTO. "
                "The earliest eligible explicit announcement is selected."
            ),
        ),
    ],
) -> None:
    """Create one canonical pre-outcome target registration, or a closed no-op result."""

    try:
        composition, result = run_pre_outcome_target_registration(lottery_type)
        output = render_pre_outcome_target_registration(
            composition,
            result,
            lottery_type,
        )
    except PreOutcomeTargetCliError as exc:
        _fail(str(exc))
    typer.echo(output)


def _fail(code: str) -> NoReturn:
    typer.echo(f"register-pre-outcome-target error: {code}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "PreOutcomeTargetCliError",
    "register_pre_outcome_target_command",
    "render_pre_outcome_target_registration",
    "run_pre_outcome_target_registration",
]
