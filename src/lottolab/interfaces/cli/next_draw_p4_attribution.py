"""Explicit preview/commit CLI for sealed Next-Draw P4 attribution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.use_cases.attribute_sealed_next_draw_outcome import (
    AttributeSealedNextDrawOutcome,
    AttributeSealedNextDrawOutcomeRequest,
    NextDrawP4ScoringContractDriftError,
    OfficialNextDrawOutcomeNotFoundError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_outcome_attribution import (
    NextDrawOutcomeAttribution,
    NextDrawOutcomeAttributionContractError,
    NextDrawP4PersistenceOutcome,
    serialize_next_draw_outcome_attribution,
)
from lottolab.domain.prize_evaluation import LOTTERY_PRIZE_EVALUATOR
from lottolab.infrastructure.next_draw_p4_authority_readers import (
    FileSystemVerifiedNextDrawRecommendationSealReader,
    NextDrawP4OfficialOutcomeStorageError,
    NextDrawP4SealAuthorityError,
    SQLiteNextDrawOfficialOutcomeReader,
)
from lottolab.infrastructure.persistence.next_draw_p4_repository import (
    NextDrawP4StorageError,
    SQLiteNextDrawP4AttributionRepository,
)
from lottolab.infrastructure.persistence.next_draw_p4_schema import (
    NextDrawP4SchemaError,
    resolve_next_draw_p4_database_paths,
)


class NextDrawP4AttributionCliError(RuntimeError):
    """One sanitized P4 attribution command failure."""


@dataclass(frozen=True, slots=True)
class NextDrawP4AttributionCliResult:
    """Complete preview or persistence receipt for one explicit target."""

    artifact: NextDrawOutcomeAttribution
    database: Path
    commit_requested: bool
    persistence_outcome: NextDrawP4PersistenceOutcome | None


def run_next_draw_p4_attribution(
    *,
    lottery_type: LotteryType,
    draw_number: str,
    draw_date: date,
    seal_file: Path,
    expected_seal_file_sha256: str,
    expected_seal_digest: str,
    draw_database: Path,
    database: Path,
    commit: bool,
) -> NextDrawP4AttributionCliResult:
    """Attribute verified sealed tickets and write only after explicit ``--commit``."""

    try:
        attribution_paths = resolve_next_draw_p4_database_paths(database)
        use_case = AttributeSealedNextDrawOutcome(
            seal_reader=FileSystemVerifiedNextDrawRecommendationSealReader(),
            outcome_reader=SQLiteNextDrawOfficialOutcomeReader(draw_database),
            prize_evaluator=LOTTERY_PRIZE_EVALUATOR,
        )
        artifact = use_case.execute(
            AttributeSealedNextDrawOutcomeRequest(
                seal_file=seal_file,
                expected_seal_file_sha256=expected_seal_file_sha256,
                expected_seal_digest=expected_seal_digest,
                lottery_type=lottery_type,
                target_draw_number=draw_number,
                target_draw_date=draw_date,
            )
        )
        persistence_outcome = None
        if commit:
            repository = SQLiteNextDrawP4AttributionRepository(
                attribution_paths.database
            )
            persistence_outcome = repository.persist_next_draw_outcome_attribution(
                artifact,
                serialize_next_draw_outcome_attribution(artifact),
            ).outcome
        return NextDrawP4AttributionCliResult(
            artifact=artifact,
            database=attribution_paths.database,
            commit_requested=commit,
            persistence_outcome=persistence_outcome,
        )
    except OfficialNextDrawOutcomeNotFoundError as exc:
        raise NextDrawP4AttributionCliError("OFFICIAL_OUTCOME_NOT_FOUND") from exc
    except NextDrawP4ScoringContractDriftError as exc:
        raise NextDrawP4AttributionCliError("SCORING_CONTRACT_DRIFT") from exc
    except NextDrawP4SealAuthorityError as exc:
        raise NextDrawP4AttributionCliError("SEALED_RECOMMENDATION_INVALID") from exc
    except NextDrawP4OfficialOutcomeStorageError as exc:
        raise NextDrawP4AttributionCliError("OFFICIAL_OUTCOME_AUTHORITY_INVALID") from exc
    except NextDrawP4StorageError as exc:
        raise NextDrawP4AttributionCliError("ATTRIBUTION_STORAGE_INVALID") from exc
    except NextDrawP4SchemaError as exc:
        raise NextDrawP4AttributionCliError("ATTRIBUTION_DATABASE_INVALID") from exc
    except (NextDrawOutcomeAttributionContractError, OSError, TypeError, ValueError) as exc:
        raise NextDrawP4AttributionCliError("ATTRIBUTION_REQUEST_INVALID") from exc


def render_next_draw_p4_attribution(result: NextDrawP4AttributionCliResult) -> str:
    """Render the complete deterministic artifact plus explicit write disposition."""

    status = (
        "PREVIEW_ONLY"
        if result.persistence_outcome is None
        else result.persistence_outcome.value
    )
    payload = {
        "artifact": result.artifact.canonical_dict(),
        "commit_requested": result.commit_requested,
        "database": str(result.database),
        "status": status,
        "zero_write": not result.commit_requested,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def attribute_sealed_next_draw_outcome_command(
    lottery_type: Annotated[
        LotteryType,
        typer.Option(
            "--lottery-type",
            case_sensitive=True,
            help="Exact lottery identity; P4 currently accepts BIG_LOTTO only.",
        ),
    ],
    draw_number: Annotated[
        str,
        typer.Option("--draw-number", help="Exact sealed official draw number."),
    ],
    draw_date: Annotated[
        str,
        typer.Option("--draw-date", help="Exact sealed draw date in YYYY-MM-DD form."),
    ],
    seal_file: Annotated[
        Path,
        typer.Option(
            "--seal-file",
            exists=True,
            dir_okay=False,
            help="Explicit absolute target-bound V1/V2 seal.json path.",
        ),
    ],
    expected_seal_file_sha256: Annotated[
        str,
        typer.Option(
            "--expected-seal-file-sha256",
            help="Expected lowercase SHA-256 of the exact seal file bytes.",
        ),
    ],
    expected_seal_digest: Annotated[
        str,
        typer.Option(
            "--expected-seal-digest",
            help="Expected seal self digest from the pre-outcome authority.",
        ),
    ],
    draw_database: Annotated[
        Path,
        typer.Option(
            "--draw-database",
            exists=True,
            dir_okay=False,
            help="Explicit absolute DRAW_DATA_V3 SQLite database.",
        ),
    ],
    database: Annotated[
        Path,
        typer.Option(
            "--database",
            dir_okay=False,
            help="Explicit absolute isolated P4 attribution SQLite database.",
        ),
    ],
    commit: Annotated[
        bool,
        typer.Option(
            "--commit",
            help="Persist create-once; omitted means a zero-write attribution preview.",
        ),
    ] = False,
) -> None:
    """Attribute only already-sealed tickets to one exact official outcome."""

    try:
        parsed_draw_date = _parse_draw_date(draw_date)
        result = run_next_draw_p4_attribution(
            lottery_type=lottery_type,
            draw_number=draw_number,
            draw_date=parsed_draw_date,
            seal_file=seal_file,
            expected_seal_file_sha256=expected_seal_file_sha256,
            expected_seal_digest=expected_seal_digest,
            draw_database=draw_database,
            database=database,
            commit=commit,
        )
    except NextDrawP4AttributionCliError as exc:
        _fail(str(exc))
    typer.echo(render_next_draw_p4_attribution(result))
    if result.persistence_outcome is NextDrawP4PersistenceOutcome.CONFLICT:
        _fail("ATTRIBUTION_CONFLICT")


def _parse_draw_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise NextDrawP4AttributionCliError("ATTRIBUTION_REQUEST_INVALID") from exc
    if parsed.isoformat() != value:
        raise NextDrawP4AttributionCliError("ATTRIBUTION_REQUEST_INVALID")
    return parsed


def _fail(code: str) -> NoReturn:
    typer.echo(f"attribute-sealed-next-draw-outcome error: {code}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "NextDrawP4AttributionCliError",
    "NextDrawP4AttributionCliResult",
    "attribute_sealed_next_draw_outcome_command",
    "render_next_draw_p4_attribution",
    "run_next_draw_p4_attribution",
]
