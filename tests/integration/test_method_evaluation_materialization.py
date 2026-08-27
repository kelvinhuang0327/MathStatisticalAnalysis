"""Real-SQLite coverage for the full V1B vertical.

Drives the whole chain end to end with nothing simulated between the ends: the
committed synthetic BIG_LOTTO fixture seeds a task-owned temporary database, a
real strategy adapter replays real causal history through
``ReplayResearchSession``, the unmodified evaluator produces the record, and
the V1B materializer turns that record into four canonical evidence documents
which are then written as LCJ-1 files and re-validated from disk exactly as an
external reader would.

Every outcome comes from the committed fixture, never from a production draw
database, so this exercises the vertical with no empirical access of any kind.
The database is snapshotted before and after to prove the whole
evaluate-and-materialize path stays strictly read-only.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT, score_big_lotto_ticket
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
from lottolab.evidence import canonical_json, validator
from lottolab.evidence.method_evaluation_materialization import (
    V1B_METRIC_IDS,
    EvidenceProducerIdentity,
    load_metric_definition_bindings,
    materialize_method_evaluation_evidence,
)
from lottolab.evidence.models import (
    DatasetSnapshot,
    DrawEntry,
    EvidenceStatus,
    ExactRational,
    RuleParameters,
    StrategyEvaluationEvidence,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.research.replay_research_session import ReplayResearchSession
from lottolab.research.base_method_evaluation import WINDOW_SIZES, ReplayStatus
from lottolab.research.replay_method_evaluation import (
    ReplayTargetOutcome,
    evaluate_replayed_single_ticket_method,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_DATASET_ID = "SYNTHETIC_BIG_LOTTO_METHOD_EVALUATION_V1B"
_DATASET_VERSION = "1"
_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_METHOD_FAMILY = "SYNTHETIC_REPLAY_EVALUATION_V1B"
_TARGET_DRAW_NUMBERS = tuple(str(1000100 + offset) for offset in range(10))
_TABLES = ("draws", "schema_migrations", "ingestion_runs", "ingestion_items")


def _task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "v1b-materialization-sqlite")}
    )


def _fixture_rows() -> list[dict[str, Any]]:
    fixture: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast("list[dict[str, Any]]", fixture["history_rows"])


def _seed_canonical_draws(paths: LocalDataPaths) -> None:
    rows = [
        ",".join(
            (
                LotteryType.BIG_LOTTO.value,
                row["draw_number"],
                row["draw_date"],
                "|".join(str(number) for number in row["main_numbers"]),
                str(row["special_number"]),
                "synthetic-v1b-materialization",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")), filename="synthetic-v1b-materialization.csv"
    )
    assert document.is_valid, document.errors
    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)
    assert result.inserted_count == len(rows) == 110
    assert result.skipped_count == result.conflict_count == result.failed_count == 0


def _table_snapshot(paths: LocalDataPaths) -> dict[str, tuple[tuple[object, ...], ...]]:
    with open_database(paths, read_only=True) as connection:
        return {
            table: tuple(
                tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
            )
            for table in _TABLES
        }


def _dataset_snapshot() -> DatasetSnapshot:
    """The same committed fixture rows, expressed as the authoritative snapshot."""

    contract = BIG_LOTTO_RULE_CONTRACT
    rule_payload: dict[str, Any] = {
        "main_number_count": contract.main_number_count,
        "main_number_min": contract.main_number_min,
        "main_number_max": contract.main_number_max,
        "main_numbers_unique": contract.main_numbers_unique,
        "special_number_count": contract.special_number_count,
        "special_number_min": contract.special_number_min,
        "special_number_max": contract.special_number_max,
        "special_numbers_unique": contract.special_numbers_unique,
        "main_special_overlap_allowed": contract.main_special_overlap_allowed,
        "rule_contract_version": contract.contract_version,
    }
    rule_payload["rule_parameters_sha256"] = canonical_json.self_key_removed_sha256(
        RuleParameters.model_validate(
            {**rule_payload, "rule_parameters_sha256": "0" * 64}
        ).model_dump(mode="json", exclude_none=True),
        "rule_parameters_sha256",
    )
    draws = [
        DrawEntry(
            draw_id=row["draw_number"],
            draw_sequence=index,
            draw_date=date.fromisoformat(row["draw_date"]),
            main_numbers=tuple(row["main_numbers"]),
            special_numbers=(row["special_number"],),
        )
        for index, row in enumerate(_fixture_rows())
    ]
    payload: dict[str, Any] = {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": _DATASET_ID,
        "dataset_version": _DATASET_VERSION,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "rule_binding": rule_payload,
        "source_provenance": {
            "kind": "SYNTHETIC",
            "declared_description": "committed synthetic BIG_LOTTO causal-history fixture",
        },
        "draws": [draw.model_dump(mode="json", exclude_none=True) for draw in draws],
    }
    payload["dataset_sha256"] = canonical_json.sha256_hex(canonical_json.canonical_bytes(payload))
    return DatasetSnapshot.model_validate(payload)


def _replayed_snapshots(paths: LocalDataPaths) -> tuple[ReplayPredictionSnapshot, ...]:
    session = ReplayResearchSession(paths=paths)
    result = session.replay_targets(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        target_draw_numbers=_TARGET_DRAW_NUMBERS,
        strategy_ids=(_STRATEGY_ID,),
    )
    return result.snapshots


def _producer() -> EvidenceProducerIdentity:
    definition = REPO_ROOT / "contracts/evidence/metric_definitions/avg_match.json"
    return EvidenceProducerIdentity(
        artifact_id_prefix="SYNTHETIC_V1B_INTEGRATION",
        evidence_status=EvidenceStatus.SYNTHETIC_TEST_ONLY,
        produced_at=datetime(2026, 8, 26, tzinfo=UTC),
        producer_name="lottolab-method-evaluation-materializer",
        method_source_git_oid="b" * 40,
        feature_version="v1",
        feature_definition_path="contracts/evidence/metric_definitions/avg_match.json",
        feature_definition_sha256=canonical_json.sha256_hex(definition.read_bytes()),
    )


def _materialize_from_real_replay(
    paths: LocalDataPaths, dataset: DatasetSnapshot
) -> tuple[StrategyEvaluationEvidence, ...]:
    snapshots = _replayed_snapshots(paths)
    by_draw_id = {draw.draw_id: draw for draw in dataset.draws}
    outcomes = tuple(
        ReplayTargetOutcome(
            draw_number=draw_number,
            draw_date=by_draw_id[draw_number].draw_date,
            main_numbers=by_draw_id[draw_number].main_numbers,
        )
        for draw_number in _TARGET_DRAW_NUMBERS
    )
    record = evaluate_replayed_single_ticket_method(
        snapshots,
        outcomes,
        method_family=_METHOD_FAMILY,
        replay_status=ReplayStatus.BASELINE_RECORDED,
    )
    return materialize_method_evaluation_evidence(
        dataset=dataset,
        snapshots=snapshots,
        evaluation=record,
        metric_definitions=load_metric_definition_bindings(REPO_ROOT),
        producer=_producer(),
    )


def test_real_replay_materializes_four_validated_evidence_artifacts(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    dataset = _dataset_snapshot()

    before = _table_snapshot(paths)
    artifacts = _materialize_from_real_replay(paths, dataset)
    after = _table_snapshot(paths)

    assert after == before, "materialization must never write to the draw database"
    assert len(artifacts) == 4
    assert [artifact.artifact_id for artifact in artifacts] == [
        f"SYNTHETIC_V1B_INTEGRATION_{kind.value}" for kind, _ in WINDOW_SIZES
    ]

    dataset_path = tmp_path / "dataset_snapshot.json"
    dataset_path.write_bytes(
        canonical_json.canonical_file_bytes(dataset.model_dump(mode="json", exclude_none=True))
    )

    for artifact in artifacts:
        assert len(artifact.records) == len(_TARGET_DRAW_NUMBERS)
        assert [result.metric_id for result in artifact.metric_results] == list(V1B_METRIC_IDS)
        assert artifact.rule_parameters.ticket_special_number_count == 0

        evidence_path = tmp_path / f"{artifact.artifact_id}.json"
        original = canonical_json.canonical_file_bytes(
            artifact.model_dump(mode="json", exclude_none=True)
        )
        evidence_path.write_bytes(original)

        report = validator.validate_evidence_file(
            evidence_path, repo_root=REPO_ROOT, dataset_path=dataset_path
        )
        assert report.schema_valid
        assert report.findings == (), (artifact.artifact_id, report.findings)

        reloaded, load_findings = validator.load_evidence(evidence_path)
        assert load_findings == []
        assert reloaded is not None
        assert (
            canonical_json.canonical_file_bytes(
                reloaded.model_dump(mode="json", exclude_none=True)
            )
            == original
        )


def test_real_replay_tickets_carry_no_special_number_and_score_by_domain_rule(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    dataset = _dataset_snapshot()
    by_draw_id = {draw.draw_id: draw for draw in dataset.draws}

    compared = 0
    for artifact in _materialize_from_real_replay(paths, dataset):
        for record in artifact.records:
            draw = by_draw_id[record.target.draw_id]
            assert record.actual_main_numbers == draw.main_numbers
            assert record.actual_special_numbers == draw.special_numbers
            for ticket in record.tickets:
                assert ticket.special_numbers == ()
                expected = score_big_lotto_ticket(
                    predicted_main_numbers=ticket.main_numbers,
                    winning_main_numbers=draw.main_numbers,
                    winning_special_number=draw.special_numbers[0],
                )
                assert ticket.special_hit is expected.special_hit
                assert ticket.main_hit_count == expected.main_hits
                compared += 1
    assert compared == 4 * len(_TARGET_DRAW_NUMBERS)


def test_real_replay_materialization_is_deterministic(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    dataset = _dataset_snapshot()

    first = _materialize_from_real_replay(paths, dataset)
    second = _materialize_from_real_replay(paths, dataset)

    for left, right in zip(first, second, strict=True):
        left_bytes = canonical_json.canonical_file_bytes(
            left.model_dump(mode="json", exclude_none=True)
        )
        right_bytes = canonical_json.canonical_file_bytes(
            right.model_dump(mode="json", exclude_none=True)
        )
        assert left_bytes == right_bytes
        assert left.artifact_content_sha256 == right.artifact_content_sha256

    for artifact in first:
        for result in artifact.metric_results:
            assert isinstance(result.value, ExactRational)
