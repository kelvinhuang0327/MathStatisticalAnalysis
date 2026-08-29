"""Operator CLI for the explicit Next-Draw Recommendation pre-draw seal command.

Mirrors ``lottolab.interfaces.cli.pre_outcome_target``'s composition and
error-mapping shape: compose the canonical local adapters, execute exactly
one explicit attempt, and map every fail-closed exception to a sanitized
operator-facing code. This command is never invoked automatically -- there is
no scheduler or launchd wiring for it; an operator (or a test) runs it
directly.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Annotated, NoReturn

import typer

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
    OutcomePresenceEvidenceUnavailableError,
    PreOutcomeTargetOperationalError,
    TargetAnnouncementAuthorityError,
    TargetAnnouncementDriftError,
)
from lottolab.application.use_cases.seal_next_draw_recommendation import (
    SealCausalHistoryDriftError,
    SealEvidenceLotteryTypeMismatchError,
    SealEvidenceUnavailableError,
    SealNextDrawRecommendationResult,
    SealStoreCorruptionError,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.causal_history_reader import read_full_causal_history
from lottolab.infrastructure.next_draw_recommendation_evidence_reader import (
    NextDrawRecommendationEvidenceUnavailableError,
    PackagedNextDrawRecommendationEvidenceReader,
)
from lottolab.infrastructure.next_draw_recommendation_seal_store import (
    FileSystemNextDrawRecommendationSealStore,
    NextDrawRecommendationSealOperationalComposition,
    NextDrawRecommendationSealStoreError,
    compose_next_draw_recommendation_seal_operational_service,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    SchemaMigrationError,
    resolve_local_data_paths,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog, production_catalog


class NextDrawRecommendationSealCliError(RuntimeError):
    """One sanitized sealing-command failure."""


def run_next_draw_recommendation_seal(
    lottery_type: LotteryType,
    *,
    catalog: StrategyCatalog | None = None,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[NextDrawRecommendationSealOperationalComposition, SealNextDrawRecommendationResult]:
    """Compose and execute one explicit Next-Draw Recommendation seal attempt."""

    resolved_catalog = catalog if catalog is not None else production_catalog()

    def evidence_factory():
        try:
            return PackagedNextDrawRecommendationEvidenceReader().read()
        except NextDrawRecommendationEvidenceUnavailableError:
            return None

    def causal_history_rows_factory(
        selected_lottery_type: LotteryType,
    ) -> tuple[CausalDrawRow, ...]:
        return read_full_causal_history(
            resolve_local_data_paths(environ=environ), selected_lottery_type
        )

    try:
        composition = compose_next_draw_recommendation_seal_operational_service(
            catalog=resolved_catalog,
            evidence_factory=evidence_factory,
            causal_history_rows_factory=causal_history_rows_factory,
            environ=environ,
            clock=clock,
        )
        return composition, composition.seal_command.execute(lottery_type)
    except SealEvidenceUnavailableError as exc:
        raise NextDrawRecommendationSealCliError("SEAL_EVIDENCE_UNAVAILABLE") from exc
    except SealEvidenceLotteryTypeMismatchError as exc:
        raise NextDrawRecommendationSealCliError("SEAL_EVIDENCE_LOTTERY_TYPE_MISMATCH") from exc
    except SealCausalHistoryDriftError as exc:
        raise NextDrawRecommendationSealCliError("SEAL_CAUSAL_HISTORY_DRIFT") from exc
    except SealStoreCorruptionError as exc:
        raise NextDrawRecommendationSealCliError("SEAL_STORE_CORRUPT") from exc
    except NextDrawRecommendationSealStoreError as exc:
        raise NextDrawRecommendationSealCliError("SEAL_STORE_UNAVAILABLE") from exc
    except TargetAnnouncementAuthorityError as exc:
        raise NextDrawRecommendationSealCliError("TARGET_ANNOUNCEMENT_AUTHORITY_INVALID") from exc
    except TargetAnnouncementDriftError as exc:
        raise NextDrawRecommendationSealCliError("TARGET_DRIFT_DETECTED") from exc
    except OutcomePresenceEvidenceUnavailableError as exc:
        raise NextDrawRecommendationSealCliError("OUTCOME_PRESENCE_EVIDENCE_UNAVAILABLE") from exc
    except CausalHistoryAuthorityError as exc:
        raise NextDrawRecommendationSealCliError("CAUSAL_HISTORY_AUTHORITY_INVALID") from exc
    except OutcomeAlreadyAvailableError as exc:
        raise NextDrawRecommendationSealCliError("TARGET_OUTCOME_ALREADY_AVAILABLE") from exc
    except TargetConflictError as exc:
        raise NextDrawRecommendationSealCliError("TARGET_REGISTRATION_CONFLICT") from exc
    except (InvalidScheduleTimeError, InvalidOutcomeAbsenceAttestationError) as exc:
        raise NextDrawRecommendationSealCliError("TARGET_PRE_OUTCOME_WINDOW_INVALID") from exc
    except CorruptAuthorityError as exc:
        raise NextDrawRecommendationSealCliError("TARGET_AUTHORITY_CORRUPT") from exc
    except (LocalDataError, SchemaMigrationError) as exc:
        raise NextDrawRecommendationSealCliError("OPERATIONAL_DATA_AUTHORITY_UNAVAILABLE") from exc
    except (PreOutcomeTargetAuthorityError, PreOutcomeTargetOperationalError) as exc:
        raise NextDrawRecommendationSealCliError("OPERATIONAL_REGISTRATION_REJECTED") from exc
    except (OSError, TypeError, ValueError) as exc:
        raise NextDrawRecommendationSealCliError("OPERATIONAL_BINDING_INVALID") from exc


def render_next_draw_recommendation_seal(
    composition: NextDrawRecommendationSealOperationalComposition,
    result: SealNextDrawRecommendationResult,
    lottery_type: LotteryType,
) -> str:
    """Render an outcome-free deterministic sealing receipt."""

    payload: dict[str, object] = {
        "lottery_type": lottery_type.value,
        "seal_root": str(composition.seal_root),
        "status": result.status.value,
    }
    if result.seal is None:
        payload.update({"record_path": None, "seal": None, "seal_digest": None})
    else:
        record_path = FileSystemNextDrawRecommendationSealStore.record_path_for(
            composition.seal_root, result.seal.target
        )
        payload.update(
            {
                "record_path": str(record_path),
                "seal": result.seal.canonical_dict(),
                "seal_digest": result.seal.seal_digest,
            }
        )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def seal_next_draw_recommendation_command(
    lottery_type: Annotated[
        LotteryType,
        typer.Option(
            "--lottery-type",
            case_sensitive=True,
            help=(
                "Exact lottery identity: BIG_LOTTO, DAILY_539, or POWER_LOTTO. "
                "The earliest eligible canonical target is resolved and sealed."
            ),
        ),
    ],
) -> None:
    """Durably seal one lottery type's Next-Draw Recommendation, or report why not."""

    try:
        composition, result = run_next_draw_recommendation_seal(lottery_type)
        output = render_next_draw_recommendation_seal(composition, result, lottery_type)
    except NextDrawRecommendationSealCliError as exc:
        _fail(str(exc))
    typer.echo(output)


def _fail(code: str) -> NoReturn:
    typer.echo(f"seal-next-draw-recommendation error: {code}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "NextDrawRecommendationSealCliError",
    "render_next_draw_recommendation_seal",
    "run_next_draw_recommendation_seal",
    "seal_next_draw_recommendation_command",
]
