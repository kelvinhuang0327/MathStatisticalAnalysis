"""Synthetic end-to-end contracts for sealed Next-Draw P4 attribution."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.main import get_command
from typer.testing import CliRunner

from lottolab.application.use_cases.attribute_sealed_next_draw_outcome import (
    AttributeSealedNextDrawOutcome,
    AttributeSealedNextDrawOutcomeRequest,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_outcome_attribution import (
    BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256,
    NextDrawOutcomeAttribution,
    NextDrawP4PersistenceOutcome,
    VerifiedNextDrawRecommendationSeal,
    compute_draw_data_v3_normalized_record_hash,
    serialize_next_draw_outcome_attribution,
)
from lottolab.domain.next_draw_recommendation import NATIVE_TICKET_COUNT_BUCKETS
from lottolab.domain.next_draw_recommendation_seal import (
    NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1,
    NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V2,
    NextDrawRecommendationSeal,
    NextDrawRecommendationSealV1,
    SealedRecommendationBucket,
    SealedStrategyTickets,
    TicketSealStatus,
)
from lottolab.domain.prize_evaluation import LOTTERY_PRIZE_EVALUATOR
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.next_draw_p4_authority_readers import (
    FileSystemVerifiedNextDrawRecommendationSealReader,
    NextDrawP4OfficialOutcomeStorageError,
    SQLiteNextDrawOfficialOutcomeReader,
)
from lottolab.infrastructure.next_draw_recommendation_seal_store import (
    FileSystemNextDrawRecommendationSealStore,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
)
from lottolab.infrastructure.persistence.draw_schema import (
    initialize_schema as initialize_draw_schema,
)
from lottolab.infrastructure.persistence.next_draw_p4_repository import (
    SQLiteNextDrawP4AttributionRepository,
)
from lottolab.infrastructure.persistence.next_draw_p4_schema import (
    NextDrawP4SchemaError,
)
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.local_app import (
    NEXT_DRAW_P4_ATTRIBUTION_DB_ENV,
    local_next_draw_p4_attribution_composition,
)
from lottolab.interfaces.cli.main import app as cli_app
from lottolab.interfaces.cli.next_draw_p4_attribution import (
    run_next_draw_p4_attribution,
)

TARGET = ObservationTarget(
    lottery_type=LotteryType.BIG_LOTTO,
    draw_number="209900777",
    draw_date=date(2099, 9, 2),
)
SCHEDULED_AT = datetime(2099, 9, 2, 12, 0, tzinfo=UTC)
SEALED_AT = datetime(2099, 9, 1, 12, 0, tzinfo=UTC)
WINNING_MAIN_NUMBERS = (1, 2, 3, 4, 5, 6)
WINNING_SPECIAL_NUMBER = 7


def _strategy(
    rank: int,
    strategy_id: str,
    status: TicketSealStatus,
    tickets: tuple[tuple[int, ...], ...] = (),
) -> SealedStrategyTickets:
    return SealedStrategyTickets(
        rank=rank,
        strategy_id=strategy_id,
        strategy_name=f"Synthetic {strategy_id}",
        status=status,
        tickets=tickets,
        detail="synthetic fixture",
    )


def _buckets() -> tuple[SealedRecommendationBucket, ...]:
    by_count = {
        1: SealedRecommendationBucket(
            native_ticket_count=1,
            availability="AVAILABLE",
            total_candidate_count=4,
            ranked_strategy_ids=("one-ok", "one-declined", "one-unreachable"),
            ranking_projection_sha256="1" * 64,
            sealed_tickets=(
                _strategy(1, "one-ok", TicketSealStatus.OK, (WINNING_MAIN_NUMBERS,)),
                _strategy(2, "one-declined", TicketSealStatus.DECLINED),
                _strategy(3, "one-unreachable", TicketSealStatus.UNREACHABLE),
            ),
        ),
        2: SealedRecommendationBucket(
            native_ticket_count=2,
            availability="LIMITED_POOL",
            total_candidate_count=1,
            ranked_strategy_ids=("two-ok",),
            ranking_projection_sha256="2" * 64,
            sealed_tickets=(
                _strategy(
                    1,
                    "two-ok",
                    TicketSealStatus.OK,
                    ((1, 2, 3, 4, 5, 8), (10, 11, 12, 13, 14, 15)),
                ),
            ),
        ),
        3: SealedRecommendationBucket(
            native_ticket_count=3,
            availability="UNAVAILABLE",
            total_candidate_count=0,
            ranked_strategy_ids=(),
            ranking_projection_sha256="3" * 64,
            sealed_tickets=(),
        ),
        5: SealedRecommendationBucket(
            native_ticket_count=5,
            availability="LIMITED_POOL",
            total_candidate_count=1,
            ranked_strategy_ids=("five-declined",),
            ranking_projection_sha256="5" * 64,
            sealed_tickets=(
                _strategy(1, "five-declined", TicketSealStatus.DECLINED),
            ),
        ),
        10: SealedRecommendationBucket(
            native_ticket_count=10,
            availability="LIMITED_POOL",
            total_candidate_count=1,
            ranked_strategy_ids=("ten-unreachable",),
            ranking_projection_sha256="a" * 64,
            sealed_tickets=(
                _strategy(1, "ten-unreachable", TicketSealStatus.UNREACHABLE),
            ),
        ),
        20: SealedRecommendationBucket(
            native_ticket_count=20,
            availability="LIMITED_POOL",
            total_candidate_count=1,
            ranked_strategy_ids=("twenty-declined",),
            ranking_projection_sha256="b" * 64,
            sealed_tickets=(
                _strategy(1, "twenty-declined", TicketSealStatus.DECLINED),
            ),
        ),
    }
    return tuple(by_count[count] for count in NATIVE_TICKET_COUNT_BUCKETS)


def _seal() -> NextDrawRecommendationSeal:
    return NextDrawRecommendationSeal.create(
        target=TARGET,
        target_scheduled_at=SCHEDULED_AT,
        sealed_at=SEALED_AT,
        source_head="c" * 40,
        source_tree="d" * 40,
        target_registration_digest="e" * 64,
        evidence_artifact_sha256="f" * 64,
        causal_history_sha256="0" * 64,
        causal_history_draw_count=2_000,
        buckets=_buckets(),
    )


def _write_seal(tmp_path: Path, *, version: int = 2) -> tuple[Path, str, str]:
    seal = _seal()
    root = tmp_path / f"seals-v{version}"
    path = FileSystemNextDrawRecommendationSealStore.record_path_for(root, TARGET)
    if version == 2:
        FileSystemNextDrawRecommendationSealStore(root).create_seal(seal)
        digest = seal.seal_digest
    else:
        material = dict(seal.canonical_material())
        material["schema_version"] = NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1
        material.pop("source_head")
        material.pop("source_tree")
        digest = hashlib.sha256(_canonical_bytes(material)).hexdigest()
        payload = {**material, "seal_digest": digest}
        path.parent.mkdir(parents=True)
        path.write_bytes(_canonical_bytes(payload) + b"\n")
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), digest


def _draw_database(tmp_path: Path) -> Path:
    database = tmp_path / "draw-authority" / "lottolab.db"
    paths = LocalDataPaths(data_directory=database.parent, database=database)
    initialize_draw_schema(paths)
    normalized_hash = compute_draw_data_v3_normalized_record_hash(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=TARGET.draw_number,
        draw_date_value=TARGET.draw_date,
        main_numbers=WINNING_MAIN_NUMBERS,
        special_numbers=(WINNING_SPECIAL_NUMBER,),
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, 'SUCCESS', 'BIG_LOTTO', ?, ?, ?, 1, 1, 0, 0, 0,
                      ?, ?, ?, ?, NULL)
            """,
            (
                "synthetic-p4-run",
                "DRAW_CSV_IMPORT",
                "synthetic-p4.csv",
                "a" * 64,
                "synthetic-parser-v1",
                TARGET.draw_number,
                TARGET.draw_number,
                "2099-09-02T11:00:00Z",
                "2099-09-02T11:01:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                LotteryType.BIG_LOTTO.value,
                TARGET.draw_number,
                TARGET.draw_date.isoformat(),
                json.dumps(WINNING_MAIN_NUMBERS, separators=(",", ":")),
                json.dumps((WINNING_SPECIAL_NUMBER,), separators=(",", ":")),
                normalized_hash,
                "synthetic-authority",
                "fixture://next-draw-p4",
                "synthetic-p4-run",
                "2099-09-02T11:01:00Z",
                "2099-09-02T11:01:00Z",
            ),
        )
    return database


def _execute(tmp_path: Path, *, seal_version: int = 2) -> NextDrawOutcomeAttribution:
    seal_path, file_sha256, seal_digest = _write_seal(
        tmp_path, version=seal_version
    )
    use_case = AttributeSealedNextDrawOutcome(
        seal_reader=FileSystemVerifiedNextDrawRecommendationSealReader(),
        outcome_reader=SQLiteNextDrawOfficialOutcomeReader(_draw_database(tmp_path)),
        prize_evaluator=LOTTERY_PRIZE_EVALUATOR,
    )
    return use_case.execute(
        AttributeSealedNextDrawOutcomeRequest(
            seal_file=seal_path,
            expected_seal_file_sha256=file_sha256,
            expected_seal_digest=seal_digest,
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number=TARGET.draw_number,
            target_draw_date=TARGET.draw_date,
        )
    )


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@pytest.mark.parametrize(
    ("version", "schema", "expected_type"),
    (
        (1, NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1, NextDrawRecommendationSealV1),
        (2, NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V2, NextDrawRecommendationSeal),
    ),
)
def test_verified_reader_permanently_supports_v1_and_v2_without_conversion(
    tmp_path: Path,
    version: int,
    schema: str,
    expected_type: type[NextDrawRecommendationSealV1 | NextDrawRecommendationSeal],
) -> None:
    path, file_sha256, seal_digest = _write_seal(tmp_path, version=version)

    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(
        expected_type.from_canonical_dict(parsed),
        expected_type,
    )
    verified = FileSystemVerifiedNextDrawRecommendationSealReader().read_verified_seal(
        path,
        expected_file_sha256=file_sha256,
        expected_seal_digest=seal_digest,
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number=TARGET.draw_number,
        target_draw_date=TARGET.draw_date,
    )

    assert verified.schema_version == schema
    if version == 1:
        assert verified.source_head is None
        assert verified.source_tree is None
    else:
        assert verified.source_head == "c" * 40
        assert verified.source_tree == "d" * 40


@pytest.mark.parametrize("seal_version", (1, 2))
def test_use_case_scores_only_actual_sealed_tickets_and_preserves_bucket_states(
    tmp_path: Path, seal_version: int
) -> None:
    artifact = _execute(tmp_path, seal_version=seal_version)

    assert tuple(item.native_ticket_count for item in artifact.buckets) == (
        NATIVE_TICKET_COUNT_BUCKETS
    )
    assert tuple(item.availability.value for item in artifact.buckets) == (
        "AVAILABLE",
        "LIMITED_POOL",
        "UNAVAILABLE",
        "LIMITED_POOL",
        "LIMITED_POOL",
        "LIMITED_POOL",
    )
    assert artifact.scoring_contract_sha256 == BIG_LOTTO_PRIZE_EVALUATION_CONTRACT_SHA256
    assert artifact.seal_schema_version == (
        NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V1
        if seal_version == 1
        else NEXT_DRAW_RECOMMENDATION_SEAL_SCHEMA_VERSION_V2
    )
    expected_source_head = None if seal_version == 1 else "c" * 40
    assert artifact.seal_source_head == expected_source_head
    first_bucket = artifact.buckets[0]
    assert tuple(item.seal_status for item in first_bucket.strategies) == (
        TicketSealStatus.OK,
        TicketSealStatus.DECLINED,
        TicketSealStatus.UNREACHABLE,
    )
    assert first_bucket.strategies[0].ticket_attributions[0].prize_tier == "FIRST"
    assert first_bucket.strategies[0].ticket_attributions[0].is_winner is True
    assert first_bucket.strategies[1].ticket_attributions == ()
    assert first_bucket.strategies[2].ticket_attributions == ()
    assert artifact.buckets[2].strategies == ()
    assert len(artifact.buckets[1].strategies[0].ticket_attributions) == 2


def test_official_outcome_reader_rejects_normalized_hash_drift(tmp_path: Path) -> None:
    database = _draw_database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE draws SET normalized_record_hash = ? WHERE draw_number = ?",
            ("f" * 64, TARGET.draw_number),
        )

    with pytest.raises(NextDrawP4OfficialOutcomeStorageError):
        SQLiteNextDrawOfficialOutcomeReader(database).read_official_outcome(
            LotteryType.BIG_LOTTO,
            TARGET.draw_number,
            TARGET.draw_date,
        )


def test_repository_is_create_once_idempotent_conflict_safe_and_immutable(
    tmp_path: Path,
) -> None:
    artifact = _execute(tmp_path)
    database = tmp_path / "p4" / "attributions.db"
    repository = SQLiteNextDrawP4AttributionRepository(database)
    canonical_bytes = serialize_next_draw_outcome_attribution(artifact)

    inserted = repository.persist_next_draw_outcome_attribution(
        artifact, canonical_bytes
    )
    repeated = repository.persist_next_draw_outcome_attribution(
        artifact, canonical_bytes
    )
    different_seal = VerifiedNextDrawRecommendationSeal(
        schema_version=artifact.seal_schema_version,
        target=artifact.target,
        source_head=artifact.seal_source_head,
        source_tree=artifact.seal_source_tree,
        buckets=_seal().buckets,
        seal_digest=artifact.seal_digest,
        seal_file_sha256="9" * 64,
    )
    conflicting_artifact = NextDrawOutcomeAttribution.create(
        seal=different_seal,
        official_outcome=artifact.official_outcome,
        buckets=artifact.buckets,
    )
    conflict = repository.persist_next_draw_outcome_attribution(
        conflicting_artifact,
        serialize_next_draw_outcome_attribution(conflicting_artifact),
    )

    assert inserted.outcome is NextDrawP4PersistenceOutcome.INSERTED
    assert repeated.outcome is NextDrawP4PersistenceOutcome.ALREADY_PRESENT
    assert conflict.outcome is NextDrawP4PersistenceOutcome.CONFLICT
    assert repository.get_attribution(
        LotteryType.BIG_LOTTO, TARGET.draw_number, TARGET.draw_date
    ) == artifact
    page = repository.list_attributions(
        lottery_type=LotteryType.BIG_LOTTO,
        page=1,
        page_size=1,
    )
    assert page.records == (artifact,)
    assert page.total_count == 1
    assert page.total_pages == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM next_draw_p4_attributions"
        ).fetchone() == (1,)
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            connection.execute(
                "UPDATE next_draw_p4_attributions SET seal_digest = ?",
                ("8" * 64,),
            )
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            connection.execute("DELETE FROM next_draw_p4_attributions")


def test_get_api_reads_exact_and_history_without_changing_database_bytes(
    tmp_path: Path,
) -> None:
    artifact = _execute(tmp_path)
    database = tmp_path / "p4-api" / "attributions.db"
    repository = SQLiteNextDrawP4AttributionRepository(database)
    repository.persist_next_draw_outcome_attribution(
        artifact,
        serialize_next_draw_outcome_attribution(artifact),
    )
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    client: Any = TestClient(
        create_app(next_draw_p4_attribution_reader_factory=lambda: repository)
    )

    exact = client.get(
        "/api/v1/next-draw-p4-attributions/"
        f"BIG_LOTTO/{TARGET.draw_number}/{TARGET.draw_date.isoformat()}"
    )
    history = client.get(
        "/api/v1/next-draw-p4-attributions",
        params={"lottery_type": "BIG_LOTTO", "page": 1, "page_size": 10},
    )

    assert exact.status_code == 200
    assert exact.json() == artifact.canonical_dict()
    assert history.status_code == 200
    assert history.json()["records"] == [artifact.canonical_dict()]
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_get_api_does_not_initialize_an_absent_database(tmp_path: Path) -> None:
    database = tmp_path / "absent" / "p4.db"
    repository = SQLiteNextDrawP4AttributionRepository(database)
    client: Any = TestClient(
        create_app(next_draw_p4_attribution_reader_factory=lambda: repository)
    )

    history = client.get("/api/v1/next-draw-p4-attributions")
    exact = client.get(
        "/api/v1/next-draw-p4-attributions/"
        f"BIG_LOTTO/{TARGET.draw_number}/{TARGET.draw_date.isoformat()}"
    )

    assert history.status_code == 200
    assert history.json()["records"] == []
    assert exact.status_code == 404
    assert not database.exists()
    assert not database.parent.exists()


def test_cli_preview_is_zero_write_and_commit_is_create_once(tmp_path: Path) -> None:
    seal_path, file_sha256, seal_digest = _write_seal(tmp_path)
    draw_database = _draw_database(tmp_path)
    database = tmp_path / "p4-cli" / "attributions.db"
    request = {
        "lottery_type": LotteryType.BIG_LOTTO,
        "draw_number": TARGET.draw_number,
        "draw_date": TARGET.draw_date,
        "seal_file": seal_path,
        "expected_seal_file_sha256": file_sha256,
        "expected_seal_digest": seal_digest,
        "draw_database": draw_database,
        "database": database,
    }

    preview = run_next_draw_p4_attribution(**request, commit=False)  # type: ignore[arg-type]
    assert preview.persistence_outcome is None
    assert not database.exists()
    assert not database.parent.exists()

    command_preview = CliRunner().invoke(
        cli_app,
        [
            "attribute-sealed-next-draw-outcome",
            "--lottery-type",
            "BIG_LOTTO",
            "--draw-number",
            TARGET.draw_number,
            "--draw-date",
            TARGET.draw_date.isoformat(),
            "--seal-file",
            str(seal_path),
            "--expected-seal-file-sha256",
            file_sha256,
            "--expected-seal-digest",
            seal_digest,
            "--draw-database",
            str(draw_database),
            "--database",
            str(database),
        ],
    )
    assert command_preview.exit_code == 0
    assert json.loads(command_preview.stdout)["status"] == "PREVIEW_ONLY"
    assert not database.exists()
    assert not database.parent.exists()

    committed = run_next_draw_p4_attribution(**request, commit=True)  # type: ignore[arg-type]
    repeated = run_next_draw_p4_attribution(**request, commit=True)  # type: ignore[arg-type]
    assert committed.persistence_outcome is NextDrawP4PersistenceOutcome.INSERTED
    assert repeated.persistence_outcome is NextDrawP4PersistenceOutcome.ALREADY_PRESENT
    assert database.is_file()


def test_cli_registers_the_exact_explicit_command_surface() -> None:
    result = CliRunner().invoke(
        cli_app,
        ["attribute-sealed-next-draw-outcome", "--help"],
        color=False,
        terminal_width=240,
    )

    assert result.exit_code == 0
    root_command: Any = get_command(cli_app)
    command = root_command.commands["attribute-sealed-next-draw-outcome"]
    option_names = {
        option
        for parameter in command.params
        for option in getattr(parameter, "opts", ())
    }
    assert option_names.issuperset(
        {
        "--lottery-type",
        "--draw-number",
        "--draw-date",
        "--seal-file",
        "--expected-seal-file-sha256",
        "--expected-seal-digest",
        "--draw-database",
        "--database",
        "--commit",
        }
    )


def test_local_api_composition_requires_one_explicit_absolute_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "configured" / "p4.db"
    composition = local_next_draw_p4_attribution_composition(
        {NEXT_DRAW_P4_ATTRIBUTION_DB_ENV: str(database)}
    )

    assert composition is not None
    assert composition.database == database
    assert not database.exists()
    assert local_next_draw_p4_attribution_composition({}) is None
    with pytest.raises(NextDrawP4SchemaError):
        local_next_draw_p4_attribution_composition(
            {NEXT_DRAW_P4_ATTRIBUTION_DB_ENV: "relative/p4.db"}
        )


def test_p4_fixture_never_uses_the_protected_production_target() -> None:
    assert TARGET.draw_number != "115000084"
