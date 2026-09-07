"""Unit tests for the BIG_LOTTO prospective campaign seal runner."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Final, cast

import pytest

from lottolab.application.b649_prospective_campaign_seal import (
    EXPECTED_BASELINE_ADAPTER_IDENTITY,
    EXPECTED_BASELINE_METHOD,
    EXPECTED_BASELINE_STRATEGY_ID,
    EXPECTED_CAMPAIGN_ID,
    EXPECTED_CANDIDATE_ID,
    EXPECTED_CANDIDATE_SHIFT,
    EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD,
    EXPECTED_ORDINAL_1_SEAL_SHA256,
    EXPECTED_PRIMARY_METRIC,
    B649CampaignSealResult,
    CampaignBaselineDriftError,
    CampaignIdMismatchError,
    CampaignOrdinalRangeError,
    CampaignSequenceError,
    CampaignSpecShaMismatchError,
    CampaignTargetMismatchError,
    load_and_validate_campaign_spec,
    run_b649_prospective_campaign_seal,
    verify_baseline_adapter_frozen_semantics,
)
from lottolab.application.future_draw_identity import normalized_announcement_sha256
from lottolab.application.pre_outcome_target import OutcomeAlreadyAvailableError
from lottolab.application.prospective_observer import PredictionConflictError
from lottolab.application.prospective_prediction_seal import (
    PredictionSealCausalityError,
    RunnablePredictionSealStatus,
)
from lottolab.application.schedule_sync import (
    SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES,
    CanonicalScheduleFact,
    expected_schedule_game_code,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_ID as OFFICIAL_DRAW_PROVIDER_ID,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_VERSION as OFFICIAL_DRAW_PROVIDER_VERSION,
)

_FIXED_CLOCK: Final = datetime(2026, 9, 10, 8, 0, 0, tzinfo=UTC)
_SCHEDULED_AT: Final = datetime(2026, 9, 11, 12, 30, 0, tzinfo=UTC)
_TARGET_DATE: Final = date(2026, 9, 11)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _setup_synthetic_db(db_dir: Path) -> LocalDataPaths:
    paths = resolve_local_data_paths(environ={"LOTTOLAB_DATA_DIR": str(db_dir)})
    initialize_schema(paths)

    history_run_id = "synthetic-history-sync"
    presence_run_id = "synthetic-presence-sync"
    now_iso = "2026-09-08T07:00:00.000000Z"

    with open_database(paths, read_only=False) as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Ingestion run for history
        conn.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 2, 2, 0, 0, 0, '115000085', '115000086', ?, ?, NULL)
            """,
            (
                history_run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                IngestionRunStatus.SUCCESS.value,
                LotteryType.BIG_LOTTO.value,
                "history.json",
                _sha256(history_run_id),
                "v1",
                now_iso,
                now_iso,
            ),
        )
        conn.execute(
            """
            INSERT INTO ingestion_run_context (
                ingestion_run_id, trigger, requested_start, requested_end, fetched_count
            ) VALUES (?, 'MANUAL', '2026-09-01', '2026-09-08', 2)
            """,
            (history_run_id,),
        )
        # Draws: 115000085 and 115000086
        conn.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                LotteryType.BIG_LOTTO.value,
                "115000085",
                "2026-09-04",
                json.dumps([2, 10, 18, 25, 33, 41]),
                json.dumps([7]),
                _sha256("draw85"),
                "synthetic",
                history_run_id,
                now_iso,
                now_iso,
            ),
        )
        conn.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                LotteryType.BIG_LOTTO.value,
                "115000086",
                "2026-09-08",
                json.dumps([1, 8, 15, 22, 29, 36]),
                json.dumps([12]),
                _sha256("draw86"),
                "synthetic",
                history_run_id,
                now_iso,
                now_iso,
            ),
        )
        # Presence run for target date 2026-09-11
        conn.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, NULL, NULL, ?, ?, NULL)
            """,
            (
                presence_run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                IngestionRunStatus.SUCCESS.value,
                LotteryType.BIG_LOTTO.value,
                "presence.json",
                _sha256(presence_run_id),
                "v1",
                now_iso,
                now_iso,
            ),
        )
        conn.execute(
            """
            INSERT INTO ingestion_run_context (
                ingestion_run_id, trigger, provider, provider_version,
                requested_start, requested_end, fetched_count
            ) VALUES (?, 'MANUAL', ?, ?, '2026-09-11', '2026-09-11', 0)
            """,
            (presence_run_id, OFFICIAL_DRAW_PROVIDER_ID, OFFICIAL_DRAW_PROVIDER_VERSION),
        )
        # Scheduled draw: 115000087
        announcement = TargetAnnouncement(
            target=ObservationTarget(LotteryType.BIG_LOTTO, "115000087", _TARGET_DATE),
            schedule_timezone="Asia/Taipei",
            scheduled_at=_SCHEDULED_AT,
            source=TargetSourceProvenance(
                source_id=OFFICIAL_SCHEDULE_SOURCE_ID,
                source_version=OFFICIAL_SCHEDULE_SOURCE_VERSION,
                source_locator="https://www.taiwanlottery.com/lotto/results",
                source_sha256=_sha256("official-schedule:BIG_LOTTO:115000087"),
                observed_at=datetime(2026, 9, 8, 6, tzinfo=UTC),
            ),
        )
        inserted = conn.execute(
            """
            INSERT INTO draw_schedules (
                lottery_type, draw_number, draw_date, scheduled_at,
                schedule_timezone, source_id, source_version, source_locator,
                source_payload_sha256, source_observed_at,
                normalized_announcement_hash, ingestion_run_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                LotteryType.BIG_LOTTO.value,
                "115000087",
                _TARGET_DATE.isoformat(),
                _SCHEDULED_AT.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                announcement.schedule_timezone,
                announcement.source.source_id,
                announcement.source.source_version,
                announcement.source.source_locator,
                announcement.source.source_payload_sha256,
                "2026-09-08T06:00:00.000000Z",
                normalized_announcement_sha256(announcement),
                presence_run_id,
                "2026-09-08T06:30:00.000000Z",
            ),
        )
        if LotteryType.BIG_LOTTO in SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES:
            fact = CanonicalScheduleFact(
                announcement=announcement,
                official_game_code=expected_schedule_game_code(LotteryType.BIG_LOTTO),
                scheduled_local_time=time(20, 30),
                source_period_identifier="115000087",
            )
            conn.execute(
                """
                INSERT INTO draw_schedule_facts (
                    schedule_id, official_game_code, scheduled_local_time,
                    source_period_identifier, immutable_schedule_hash, authority_origin
                ) VALUES (?, ?, ?, ?, ?, 'OFFICIAL')
                """,
                (
                    inserted.lastrowid,
                    fact.official_game_code,
                    fact.scheduled_local_time.isoformat(timespec="seconds"),
                    fact.source_period_identifier,
                    fact.immutable_schedule_sha256,
                ),
            )
        conn.commit()

    return paths


@pytest.fixture
def campaign_env(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Source code mirror for frozen adapter check
    src_dir = repo_root / "src/lottolab/strategies/adapters"
    src_dir.mkdir(parents=True)
    real_adapter = Path("src/lottolab/strategies/adapters/biglotto_wave6.py").resolve()
    (src_dir / "biglotto_wave6.py").write_bytes(real_adapter.read_bytes())

    # Task data directory
    campaign_dir = (
        repo_root
        / ".task-data/BRANCH2_TABU7_FIXED_K10_VS_10BET_PROSPECTIVE_104DRAW_CAMPAIGN_R1"
    )
    campaign_dir.mkdir(parents=True)
    real_spec = Path(
        ".task-data/BRANCH2_TABU7_FIXED_K10_VS_10BET_PROSPECTIVE_104DRAW_CAMPAIGN_R1/campaign_spec.json"
    ).resolve()
    spec_path = campaign_dir / "campaign_spec.json"
    spec_path.write_bytes(real_spec.read_bytes())

    # Ordinal 1 seal
    ord1_dir = (
        repo_root
        / ".task-data/BRANCH2_TABU7_FIXED_K10_VS_10BET_DRAW086_PROSPECTIVE_SEAL_R1"
    )
    ord1_dir.mkdir(parents=True)
    real_ord1 = Path(
        ".task-data/BRANCH2_TABU7_FIXED_K10_VS_10BET_DRAW086_PROSPECTIVE_SEAL_R1/prediction_seal.json"
    ).resolve()
    ord1_path = ord1_dir / "prediction_seal.json"
    ord1_path.write_bytes(real_ord1.read_bytes())

    # Draw seals directory
    draw_seals_dir = campaign_dir / "draw_seals"
    draw_seals_dir.mkdir()

    # DB directory
    db_dir = tmp_path / "db"
    db_dir.mkdir(mode=0o700)
    db_dir.chmod(0o700)
    _setup_synthetic_db(db_dir)

    return {
        "repo_root": repo_root,
        "spec_path": spec_path,
        "ord1_path": ord1_path,
        "draw_seals_dir": draw_seals_dir,
        "db_dir": db_dir,
    }


def test_campaign_spec_loading_and_constants(campaign_env: dict[str, Path]) -> None:
    spec = load_and_validate_campaign_spec(campaign_env["spec_path"])
    assert spec.campaign_id == EXPECTED_CAMPAIGN_ID
    assert spec.frozen_source_head == EXPECTED_FROZEN_RESEARCH_SOURCE_HEAD
    assert spec.start_target_draw == "115000086"
    assert spec.target_draw_count == 104
    assert spec.candidate_id == EXPECTED_CANDIDATE_ID
    assert spec.candidate_shift == EXPECTED_CANDIDATE_SHIFT
    assert len(spec.candidate_portfolio) == 10
    assert spec.baseline_method == EXPECTED_BASELINE_METHOD
    assert spec.baseline_strategy_id == EXPECTED_BASELINE_STRATEGY_ID
    assert spec.baseline_adapter_identity == EXPECTED_BASELINE_ADAPTER_IDENTITY
    assert spec.primary_metric == EXPECTED_PRIMARY_METRIC
    assert spec.ordinal_1_seal_sha256 == EXPECTED_ORDINAL_1_SEAL_SHA256


def test_campaign_spec_sha_mismatch_fails(campaign_env: dict[str, Path]) -> None:
    spec_path = campaign_env["spec_path"]
    spec_path.write_text(spec_path.read_text() + " ", encoding="utf-8")
    with pytest.raises(CampaignSpecShaMismatchError):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=2,
            target_draw="115000087",
            campaign_spec_path=spec_path,
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


def test_campaign_id_mismatch_fails(campaign_env: dict[str, Path]) -> None:
    with pytest.raises(CampaignIdMismatchError):
        run_b649_prospective_campaign_seal(
            campaign_id="WRONG_CAMPAIGN_ID",
            campaign_ordinal=2,
            target_draw="115000087",
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


def test_ordinal_1_cannot_be_rewritten(campaign_env: dict[str, Path]) -> None:
    with pytest.raises(CampaignOrdinalRangeError, match="ordinal 1 is sealed externally"):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=1,
            target_draw="115000086",
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


@pytest.mark.parametrize("invalid_ordinal", [0, -1, 105, 999])
def test_ordinal_out_of_range_fails(
    campaign_env: dict[str, Path], invalid_ordinal: int
) -> None:
    with pytest.raises(CampaignOrdinalRangeError):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=invalid_ordinal,
            target_draw="115000087",
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


def test_target_mismatch_fails(campaign_env: dict[str, Path]) -> None:
    with pytest.raises(CampaignTargetMismatchError):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=2,
            target_draw="115000099",  # Not in schedule authority
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


def test_late_execution_fails_before_producer(campaign_env: dict[str, Path]) -> None:
    late_clock = datetime(2026, 9, 11, 13, 0, 0, tzinfo=UTC)  # After scheduled_at 12:30
    with pytest.raises(PredictionSealCausalityError, match="not strictly before scheduled_at"):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=2,
            target_draw="115000087",
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: late_clock,
        )


def test_outcome_already_available_fails_before_producer(
    campaign_env: dict[str, Path],
) -> None:
    # Insert outcome for 115000087 into draws table
    paths = resolve_local_data_paths(
        environ={"LOTTOLAB_DATA_DIR": str(campaign_env["db_dir"])}
    )
    with open_database(paths, read_only=False) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, NULL, 'synthetic-history-sync',
                '2026-09-11T12:00:00.000000Z', '2026-09-11T12:00:00.000000Z'
            )
            """,
            (
                LotteryType.BIG_LOTTO.value,
                "115000087",
                "2026-09-11",
                json.dumps([3, 7, 14, 21, 28, 35]),
                json.dumps([49]),
                _sha256("draw87"),
                "synthetic",
            ),
        )
        conn.commit()

    with pytest.raises(OutcomeAlreadyAvailableError):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=2,
            target_draw="115000087",
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


def test_unsealed_preceding_ordinal_fails(campaign_env: dict[str, Path]) -> None:
    # Attempt ordinal 3 when ordinal 2 has not been sealed
    with pytest.raises(
        CampaignSequenceError, match="preceding campaign ordinal 2 has not been sealed"
    ):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=3,
            target_draw="115000087",
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


def test_baseline_adapter_drift_fails(campaign_env: dict[str, Path]) -> None:
    adapter_path = (
        campaign_env["repo_root"]
        / "src/lottolab/strategies/adapters/biglotto_wave6.py"
    )
    adapter_path.write_text(adapter_path.read_text() + "\n# drift\n", encoding="utf-8")
    with pytest.raises(CampaignBaselineDriftError, match="adapter source file drifted"):
        verify_baseline_adapter_frozen_semantics(campaign_env["repo_root"])


def test_valid_seal_creation_idempotency_and_no_db_write(
    campaign_env: dict[str, Path],
) -> None:
    db_file = campaign_env["db_dir"] / "lottolab.db"
    ord1_file = campaign_env["ord1_path"]
    db_sha_before = _sha256_file(db_file)
    ord1_sha_before = _sha256_file(ord1_file)

    # 1. Execute ordinal 2 sealing
    res: B649CampaignSealResult = run_b649_prospective_campaign_seal(
        campaign_id=EXPECTED_CAMPAIGN_ID,
        campaign_ordinal=2,
        target_draw="115000087",
        campaign_spec_path=campaign_env["spec_path"],
        draw_seals_dir=campaign_env["draw_seals_dir"],
        data_directory=campaign_env["db_dir"],
        repo_root=campaign_env["repo_root"],
        clock=lambda: _FIXED_CLOCK,
    )

    assert res.status == RunnablePredictionSealStatus.CREATED
    assert res.campaign_id == EXPECTED_CAMPAIGN_ID
    assert res.campaign_ordinal == 2
    assert res.target_draw == "115000087"
    assert res.history_cutoff_draw == "115000086"
    assert res.seal_path.is_file()

    # Verify wrapper fields conform to per_draw_seal_protocol
    payload = res.wrapper_payload
    for req_field in [
        "campaign_id",
        "campaign_ordinal",
        "target_draw",
        "history_cutoff_draw",
        "frozen_source_head",
        "candidate_id",
        "candidate_portfolio",
        "baseline_method",
        "baseline_strategy_id",
        "baseline_adapter_identity",
        "baseline_portfolio",
        "history_authority_locator",
        "history_authority_identity",
        "seal_created_at_asia_taipei",
        "target_outcome_read",
        "database_writes",
    ]:
        assert req_field in payload, f"missing required field: {req_field}"

    assert payload["target_outcome_read"] is False
    assert payload["database_writes"] == "none"

    # Verify candidate portfolio is static K10
    raw_candidate = payload["candidate_portfolio"]
    assert isinstance(raw_candidate, list)
    candidate_portfolio = cast(list[list[int]], raw_candidate)
    assert len(candidate_portfolio) == 10
    for ticket in candidate_portfolio:
        assert isinstance(ticket, list)
        assert len(ticket) == 6
        assert all(1 <= x <= 49 for x in ticket)
        assert ticket == sorted(ticket)

    # Verify baseline portfolio is K10
    raw_baseline = payload["baseline_portfolio"]
    assert isinstance(raw_baseline, list)
    baseline_portfolio = cast(list[list[int]], raw_baseline)
    assert len(baseline_portfolio) == 10
    for ticket in baseline_portfolio:
        assert isinstance(ticket, list)
        assert len(ticket) == 6
        assert all(1 <= x <= 49 for x in ticket)
        assert ticket == sorted(ticket)

    # Verify database was NOT written to
    db_sha_after = _sha256_file(db_file)
    assert db_sha_before == db_sha_after, "database was modified during sealing!"

    # Verify ordinal 1 seal was NOT modified
    ord1_sha_after = _sha256_file(ord1_file)
    assert ord1_sha_before == ord1_sha_after, "ordinal 1 seal was modified!"

    # 2. Idempotent rerun
    res2: B649CampaignSealResult = run_b649_prospective_campaign_seal(
        campaign_id=EXPECTED_CAMPAIGN_ID,
        campaign_ordinal=2,
        target_draw="115000087",
        campaign_spec_path=campaign_env["spec_path"],
        draw_seals_dir=campaign_env["draw_seals_dir"],
        data_directory=campaign_env["db_dir"],
        repo_root=campaign_env["repo_root"],
        clock=lambda: _FIXED_CLOCK,
    )
    assert res2.status == RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP
    assert res2.seal_sha256 == res.seal_sha256

    # 3. Conflicting content rerun fails
    corrupt_payload = dict(payload)
    corrupt_payload["baseline_method"] = "altered_method"
    res.seal_path.write_text(json.dumps(corrupt_payload), encoding="utf-8")

    with pytest.raises(PredictionConflictError):
        run_b649_prospective_campaign_seal(
            campaign_id=EXPECTED_CAMPAIGN_ID,
            campaign_ordinal=2,
            target_draw="115000087",
            campaign_spec_path=campaign_env["spec_path"],
            draw_seals_dir=campaign_env["draw_seals_dir"],
            data_directory=campaign_env["db_dir"],
            repo_root=campaign_env["repo_root"],
            clock=lambda: _FIXED_CLOCK,
        )


def test_cli_main_execution(campaign_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from tools.b649_prospective_campaign_seal import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tools/b649_prospective_campaign_seal.py",
            "--campaign-id",
            EXPECTED_CAMPAIGN_ID,
            "--campaign-ordinal",
            "2",
            "--target-draw",
            "115000087",
            "--campaign-spec",
            str(campaign_env["spec_path"]),
            "--draw-seals-dir",
            str(campaign_env["draw_seals_dir"]),
            "--data-directory",
            str(campaign_env["db_dir"]),
            "--repo-root",
            str(campaign_env["repo_root"]),
        ],
    )
    exit_code = main(clock=lambda: _FIXED_CLOCK)
    assert exit_code == 0
