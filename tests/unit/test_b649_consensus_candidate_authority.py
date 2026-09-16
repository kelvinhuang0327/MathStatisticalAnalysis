"""Unit tests for B649 immutable candidate authority admission and retrieval."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.b649_consensus_candidate_authority import (
    ConsensusCandidateAdmissionError,
    admit_consensus_candidate,
    load_admitted_candidate,
)
from lottolab.infrastructure.b649_consensus_promotion import PromotionRequest
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
)
from lottolab.infrastructure.persistence.draw_schema import (
    initialize_schema as initialize_draw_schema,
)
from lottolab.infrastructure.persistence.draw_schema import (
    open_database as open_draw_database,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteCanonicalScheduleAuthorityRepository,
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.persistence.research_schema import (
    ResearchDataPaths,
)
from lottolab.infrastructure.persistence.research_schema import (
    initialize_schema as initialize_research_schema,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    parse_official_biglotto_schedule_authority,
)

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "b649_consensus_promotion"
    / "scheduler_115000088_bundle.json"
)


def _setup_publication_tree(root: Path, fixture: dict[str, object]) -> Path:
    payload_rel = str(fixture["payload_relative_path"])
    payload_file = root / payload_rel
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_bytes(str(fixture["payload_content"]).encode("utf-8"))

    streams = cast(dict[str, dict[str, str]], fixture["stream_files"])
    for rel_path, stream_info in streams.items():
        s_file = root / rel_path
        s_file.parent.mkdir(parents=True, exist_ok=True)
        s_file.write_bytes(stream_info["content"].encode("utf-8"))
    return root


def _setup_draw_database(
    db_path: Path,
    *,
    target_draw: str = "115000088",
    draw_date: str = "20260915",
    observed_at: datetime = datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
) -> tuple[LocalDataPaths, str]:
    db_resolved = db_path.resolve()
    draw_paths = LocalDataPaths(db_resolved.parent, db_resolved)
    initialize_draw_schema(draw_paths)
    body = json.dumps(
        {
            "content": {
                "nextDrawDateList": [
                    {
                        "drawDate": draw_date,
                        "drawTerm": target_draw,
                        "gameCode": 5118,
                    }
                ]
            },
            "fixtureMarker": 1,
            "rtCode": 0,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    fetch_result = parse_official_biglotto_schedule_authority(body, observed_at=observed_at)
    repo = SQLiteCanonicalScheduleAuthorityRepository(
        draw_paths, initialize=False, clock=lambda: observed_at
    )
    repo.apply_canonical_schedule_authority(fetch_result)
    reader = SQLiteFutureDrawIdentityReader(draw_paths, require_active_authority=True)
    record = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, target_draw)
    assert record is not None and record.immutable_schedule_sha256 is not None
    return draw_paths, record.immutable_schedule_sha256


def test_admit_rejects_frozen_087(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    with pytest.raises(ConsensusCandidateAdmissionError, match="115000087"):
        admit_consensus_candidate(
            research_paths=res_paths,
            target_draw_number="115000087",
            publication_root=(tmp_path / "pub").resolve(),
            admitter_identity="unit-test",
        )


def test_admit_rejects_missing_publication_root(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    draw_paths, _ = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    with pytest.raises(ConsensusCandidateAdmissionError, match="publication_root does not exist"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=tmp_path / "nonexistent",
            admitter_identity="unit-test",
        )


def test_admit_rejects_symlink_in_publication_root(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    symlink = pub_root / "forecasts" / "symlink_dir"
    symlink.symlink_to(pub_root / "forecasts" / "115000088")

    draw_paths, _ = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    with pytest.raises(ConsensusCandidateAdmissionError, match="symlink"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            admitter_identity="unit-test",
        )


def test_admit_rejects_missing_schedule_authority(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_db = (tmp_path / "draw" / "lottolab.db").resolve()
    draw_paths = LocalDataPaths(draw_db.parent, draw_db)
    initialize_draw_schema(draw_paths)

    with pytest.raises(ConsensusCandidateAdmissionError, match="no scheduled draw identity"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            admitter_identity="unit-test",
        )


def test_admit_rejects_past_deadline(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, _ = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    # Deadline is 2026-09-15 12:30:00 UTC (20:30 Taipei)
    past_deadline = datetime(2026, 9, 15, 12, 30, 0, tzinfo=UTC)
    with pytest.raises(ConsensusCandidateAdmissionError, match="deadline"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            now=past_deadline,
            admitter_identity="unit-test",
        )


def test_admit_rejects_outcome_already_present(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, _ = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    # Manually insert completed draw for 115000088 into draws table
    with open_draw_database(draw_paths, read_only=False) as conn:
        conn.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename, source_sha256,
                parser_version, total_count, inserted_count, skipped_count, conflict_count,
                failed_count, started_at, completed_at
            ) VALUES (
                'run-test', 'MANUAL_SYNC', 'SUCCESS', 'BIG_LOTTO', 'test.json', 'a' * 64,
                'v1', 1, 1, 0, 0, 0, '2026-09-15T21:00:00Z', '2026-09-15T21:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, ingestion_run_id,
                created_at, updated_at
            ) VALUES (
                'BIG_LOTTO', '115000088', '2026-09-15', '[1,2,3,4,5,6]',
                '[7]', 'dummy-hash', 'run-test', '2026-09-15T21:00:00Z', '2026-09-15T21:00:00Z'
            )
            """
        )
        conn.commit()

    with pytest.raises(ConsensusCandidateAdmissionError, match="outcome is already present"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
            admitter_identity="unit-test",
        )


def test_admit_rejects_tampered_payload_sha(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    # Tamper payload content: change history_draw_count
    payload_file = pub_root / str(fixture["payload_relative_path"])
    payload_obj = json.loads(payload_file.read_text(encoding="utf-8"))
    payload_obj["history_draw_count"] = 9999
    payload_file.write_text(json.dumps(payload_obj), encoding="utf-8")

    draw_paths, _ = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    with pytest.raises(ConsensusCandidateAdmissionError, match="SHA256 mismatch"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            expected_payload_sha256=fixture["payload_sha256"],
            now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
            admitter_identity="unit-test",
        )


def test_admit_rejects_corrupted_payload_bytes(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    payload_file = pub_root / str(fixture["payload_relative_path"])
    payload_file.write_bytes(b"not json at all {")

    draw_paths, _ = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    with pytest.raises(ConsensusCandidateAdmissionError, match="valid JSON"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
            admitter_identity="unit-test",
        )


def test_admit_rejects_tampered_stream_sha(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    # Corrupt one stream file
    first_stream_rel = next(iter(fixture["stream_files"].keys()))
    stream_file = pub_root / first_stream_rel
    stream_file.write_text('{"tampered": true}', encoding="utf-8")

    draw_paths, _ = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    with pytest.raises(ConsensusCandidateAdmissionError, match="SHA256 mismatch"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
            admitter_identity="unit-test",
        )


def test_admit_and_load_roundtrip_088(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, expected_schedule_sha = _setup_draw_database(tmp_path / "draw" / "lottolab.db")

    admitted = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000088",
        publication_root=pub_root,
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
        admitter_identity="test-agent",
        notes="admitted via test",
    )

    assert admitted.target_draw_number == "115000088"
    assert admitted.payload_sha256 == fixture["payload_sha256"]
    assert admitted.schedule_authority_sha256 == expected_schedule_sha
    assert admitted.candidate_ref.startswith("cand-consensus-b649-115000088-")

    # Idempotent re-admission
    admitted2 = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000088",
        publication_root=pub_root,
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
        admitter_identity="test-agent",
        notes="admitted via test",
    )
    assert admitted2.candidate_ref == admitted.candidate_ref

    # Load back
    loaded = load_admitted_candidate(res_paths, admitted.candidate_ref)
    assert loaded.candidate_ref == admitted.candidate_ref
    assert loaded.payload_sha256 == admitted.payload_sha256
    assert loaded.schedule_authority_sha256 == expected_schedule_sha
    assert loaded.target_draw_date == "2026-09-15"
    assert len(loaded.streams) == 11

    req = PromotionRequest(
        request_id="req-unit-088",
        request_sha256="c" * 64,
        expected_current_version=0,
        schedule_authority_sha256=expected_schedule_sha,
        authorization_evidence_reference="test://auth",
        promotion_executor_identity="executor",
        execution_source_id="test://cli",
        execution_source_version="v1",
        candidate_ref=admitted.candidate_ref,
    )
    forecast = loaded.build_forecast(req)
    assert forecast.candidate_ref == admitted.candidate_ref
    assert forecast.payload_sha256 == admitted.payload_sha256

    bad_req = PromotionRequest(
        request_id="req-unit-088-bad",
        request_sha256="d" * 64,
        expected_current_version=0,
        schedule_authority_sha256="e" * 64,
        authorization_evidence_reference="test://auth",
        promotion_executor_identity="executor",
        execution_source_id="test://cli",
        execution_source_version="v1",
        candidate_ref=admitted.candidate_ref,
    )
    with pytest.raises(ValueError, match="schedule authority hash"):
        loaded.build_forecast(bad_req)
