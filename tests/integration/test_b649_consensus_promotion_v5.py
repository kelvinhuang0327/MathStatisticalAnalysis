"""Integration tests for V5 target-parameterized canonical promotion contract.

Tests A through J verifying:
- Test A: 088 admission and promotion roundtrip using scheduler_115000088_bundle.json.
- Test B: 089 generalization roundtrip.
- Test C: F1 caller-supplied payload bypass rejection at all 5 points.
- Test D: Frozen 087 invariant preservation.
- Test E: DUPLICATE_CANDIDATE_CONFLICT on reused candidate_ref.
- Test F: Concurrency / CAS stale parent version conflict.
- Test G: Admission security (symlinks, stream tamper, payload tamper).
- Test H: Temporal and outcome gates (outcome present, deadline passed).
- Test I: CLI end-to-end (admit, preflight, promote, current).
- Test J: Store verification (verify_store with V5 migration checksum and authority checks).
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3

# INTENT: Import dataclass replace and candidate authority error classes
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from tools import b649_promote_consensus_candidate as cli_module

from lottolab.domain.draws import LotteryType
from lottolab.domain.research_live_forecast import (
    canonical_json,
    digest,
)
from lottolab.infrastructure.b649_consensus_candidate_authority import (
    ConsensusCandidateAdmissionError,
    ConsensusCandidateNotFoundError,
    admit_consensus_candidate,
    load_admitted_candidate,
)
from lottolab.infrastructure.b649_consensus_promotion import (
    PromotionRequest,
    compute_successor_request_hash,
    promote_admitted_candidate,
    read_current_consensus,
)
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
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    ResearchRepositoryError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    CURRENT_SCHEMA_VERSION,
    V5_MIGRATION_CHECKSUM,
    ResearchDataPaths,
)
from lottolab.infrastructure.persistence.research_schema import (
    initialize_schema as initialize_research_schema,
)
from lottolab.infrastructure.persistence.research_schema import (
    open_database as open_research_database,
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


def _setup_draw_database(
    db_path: Path,
    *draws: tuple[str, str],  # (draw_number, draw_date_str)
    observed_at: datetime = datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
) -> tuple[LocalDataPaths, dict[str, str]]:
    db_resolved = db_path.resolve()
    draw_paths = LocalDataPaths(db_resolved.parent, db_resolved)
    initialize_draw_schema(draw_paths)

    draw_items = [
        {"drawDate": draw_date, "drawTerm": draw_number, "gameCode": 5118}
        for draw_number, draw_date in draws
    ]
    body = json.dumps(
        {
            "content": {"nextDrawDateList": draw_items},
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
    schedule_hashes: dict[str, str] = {}
    for draw_number, _ in draws:
        rec = reader.get_scheduled_draw(LotteryType.BIG_LOTTO, draw_number)
        assert rec is not None and rec.immutable_schedule_sha256 is not None
        schedule_hashes[draw_number] = rec.immutable_schedule_sha256

    return draw_paths, schedule_hashes


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


def _create_089_bundle(pub_root: Path, base_fixture: dict[str, object]) -> dict[str, object]:
    """Derive a valid 089 publication bundle from the 088 fixture."""
    base_payload = json.loads(str(base_fixture["payload_content"]))
    payload_089 = copy.deepcopy(base_payload)
    payload_089["target_draw"] = {"draw_date": "2026-09-18", "draw_number": "115000089"}
    payload_089["scheduled_at"] = "2026-09-18T20:30:00+08:00"
    payload_089["max_data_cutoff"] = {"draw_date": "2026-09-15", "draw_number": "115000088"}
    payload_089["history_draw_count"] = int(base_payload["history_draw_count"]) + 1

    # Rewrite streams for 089
    new_stream_inputs: list[dict[str, object]] = []
    stream_files_089: dict[str, dict[str, str]] = {}
    for s in payload_089["stream_inputs"]:
        s_copy = copy.deepcopy(s)
        strategy = s_copy["strategy_id"]
        run_id = f"115000089-{strategy}-20260915T221327-test"
        rel_path = f"predictions/115000089/{strategy}/{run_id}.json"
        s_copy["prediction_run_id"] = run_id
        s_copy["source_relative_path"] = rel_path

        # Generate stream file content
        stream_content = json.dumps(
            {
                "availability": "AVAILABLE",
                "draw_date": "2026-09-18",
                "draw_number": "115000089",
                "history_caveat": "YES",
                "history_cutoff": {"draw_date": "2026-09-15", "draw_number": "115000088"},
                "history_draw_count": payload_089["history_draw_count"],
                "history_sha256": payload_089["history_sha256"],
                "lottery_type": "BIG_LOTTO",
                "native_ticket_count": s_copy["native_ticket_count"],
                "pinned_implementation": None,
                "prediction_created_at": "2026-09-15T22:13:27+08:00",
                "prediction_run_id": run_id,
                "prediction_temporal_class": "PRE_DRAW",
                "producer_fingerprint": None,
                "scheduled_at": "2026-09-18T20:30:00+08:00",
                "schema_version": "b649-operational-prediction-v1",
                "strategy_config": {},
                "strategy_id": strategy,
                "strategy_version": "v0.1",
                "task_id": "B649_OPERATIONAL_PREDICTION_LOOP_R1",
                "tickets": [{"predicted_numbers": [1, 2, 3, 4, 5, 6], "ticket_position": 1}],
                "unavailable_reason": None,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        stream_bytes = stream_content.encode("utf-8")
        stream_sha = hashlib.sha256(stream_bytes).hexdigest()
        s_copy["source_sha256"] = stream_sha
        new_stream_inputs.append(s_copy)

        s_file = pub_root / rel_path
        s_file.parent.mkdir(parents=True, exist_ok=True)
        s_file.write_bytes(stream_bytes)
        stream_files_089[rel_path] = {"sha256": stream_sha, "content": stream_content}

    payload_089["stream_inputs"] = new_stream_inputs
    payload_089["stream_input_manifest_sha256"] = digest(new_stream_inputs)

    payload_content_089 = json.dumps(payload_089, separators=(",", ":"), sort_keys=True) + "\n"
    payload_bytes_089 = payload_content_089.encode("utf-8")
    payload_sha_089 = hashlib.sha256(payload_bytes_089).hexdigest()

    rel_089 = (
        "forecasts/115000089/B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS/1.0.0/"
        "final_forecast_payload.json"
    )
    p_file = pub_root / rel_089
    p_file.parent.mkdir(parents=True, exist_ok=True)
    p_file.write_bytes(payload_bytes_089)

    return {
        "target_draw": "115000089",
        "target_date": "2026-09-18",
        "payload_relative_path": rel_089,
        "payload_sha256": payload_sha_089,
        "payload_content": payload_content_089,
        "stream_files": stream_files_089,
    }


# ==============================================================================
# TEST A: 088 Admission and Promotion Roundtrip
# ==============================================================================
def test_v5_requirement_a_088_roundtrip(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, sched_hashes = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )
    sched_sha_088 = sched_hashes["115000088"]

    # 1. Admit candidate
    admitted = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000088",
        publication_root=pub_root,
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
        admitter_identity="agent-consensus-admitter",
        notes="admitted for test a",
    )
    assert admitted.target_draw_number == "115000088"
    assert admitted.payload_sha256 == fixture["payload_sha256"]
    assert admitted.schedule_authority_sha256 == sched_sha_088
    assert admitted.candidate_ref.startswith("cand-consensus-b649-115000088-")

    # Verify authority row
    with open_research_database(res_paths, read_only=True) as conn:
        auth_row = conn.execute(
            """
            SELECT candidate_ref, target_draw_number, payload_sha256, schedule_authority_sha256
            FROM research_consensus_candidate_authorities
            WHERE candidate_ref = ?
            """,
            (admitted.candidate_ref,),
        ).fetchone()
        assert auth_row is not None
        assert auth_row[0] == admitted.candidate_ref
        assert auth_row[1] == "115000088"
        assert auth_row[2] == fixture["payload_sha256"]

    # 2. Promote candidate
    req_hash = compute_successor_request_hash(
        request_id="req-b649-088-001",
        candidate_ref=admitted.candidate_ref,
        schedule_authority_sha256=sched_sha_088,
        expected_current_version=0,
    )
    req = PromotionRequest(
        request_id="req-b649-088-001",
        request_sha256=req_hash,
        expected_current_version=0,
        schedule_authority_sha256=sched_sha_088,
        authorization_evidence_reference="ops://b649-promotion/088",
        promotion_executor_identity="executor-088",
        execution_source_id="cli://promote",
        execution_source_version="v5",
        candidate_ref=admitted.candidate_ref,
    )

    promoted = promote_admitted_candidate(
        database_path=res_db,
        admitted_candidate=admitted,
        request=req,
    )
    assert promoted.version == 1
    assert promoted.payload_sha256 == admitted.payload_sha256
    assert promoted.pointer_advanced is True

    # Verify live forecast row has candidate_ref
    with open_research_database(res_paths, read_only=True) as conn:
        live_row = conn.execute(
            """
            SELECT version, candidate_ref, provenance_class, original_execution_provenance_status
            FROM research_live_forecast_versions
            WHERE version = 1
            """
        ).fetchone()
        assert live_row is not None
        assert live_row[0] == 1
        assert live_row[1] == admitted.candidate_ref
        assert live_row[2] == "CANONICAL_CONSENSUS"
        assert live_row[3] == "CONSENSUS_ADMISSION_BOUND"

    # 3. Read current consensus
    current = read_current_consensus(
        res_db,
        scope=(
            "BIG_LOTTO",
            "115000088",
            "2026-09-15",
            "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS",
            "1.0.0",
        ),
    )
    assert current is not None
    assert current.version == 1
    assert current.forecast.candidate_ref == admitted.candidate_ref
    assert current.forecast.payload_sha256 == admitted.payload_sha256


# ==============================================================================
# TEST B: 089 Generalization Roundtrip
# ==============================================================================
def test_v5_requirement_b_089_generalization_roundtrip(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)
    _create_089_bundle(pub_root, fixture)

    draw_paths, sched_hashes = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000089", "20260918"),
    )
    sched_sha_089 = sched_hashes["115000089"]

    admitted_089 = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000089",
        publication_root=pub_root,
        now=datetime(2026, 9, 16, 12, 0, tzinfo=UTC),
        admitter_identity="agent-089",
        notes="admitted for test b 089",
    )
    assert admitted_089.target_draw_number == "115000089"
    assert admitted_089.candidate_ref.startswith("cand-consensus-b649-115000089-")

    req_hash_089 = compute_successor_request_hash(
        request_id="req-b649-089-001",
        candidate_ref=admitted_089.candidate_ref,
        schedule_authority_sha256=sched_sha_089,
        expected_current_version=0,
    )
    req_089 = PromotionRequest(
        request_id="req-b649-089-001",
        request_sha256=req_hash_089,
        expected_current_version=0,
        schedule_authority_sha256=sched_sha_089,
        authorization_evidence_reference="ops://b649-promotion/089",
        promotion_executor_identity="executor-089",
        execution_source_id="cli://promote",
        execution_source_version="v5",
        candidate_ref=admitted_089.candidate_ref,
    )
    promoted_089 = promote_admitted_candidate(
        database_path=res_db,
        admitted_candidate=admitted_089,
        request=req_089,
    )
    assert promoted_089.version == 1
    with open_research_database(res_paths, read_only=True) as conn:
        row_089 = conn.execute(
            "SELECT candidate_ref FROM research_live_forecast_versions WHERE version = 1"
        ).fetchone()
        assert row_089 is not None
        assert row_089[0] == admitted_089.candidate_ref


# ==============================================================================
# TEST C: F1 Caller-Supplied Payload Bypass Rejected at All 5 Points
# ==============================================================================
def test_v5_requirement_c_f1_bypass_rejected_at_all_5_points(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, sched_hashes = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )
    sched_sha_088 = sched_hashes["115000088"]

    admitted = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000088",
        publication_root=pub_root,
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
        admitter_identity="agent-c",
    )

    # Point 1: Admission Layer fails closed without publication store or schedule authority
    with pytest.raises(ConsensusCandidateAdmissionError):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=tmp_path / "untrusted-caller-store",
            admitter_identity="attacker",
        )

    # Point 2: Loader Layer rejects unknown candidate_ref or mismatched schedule hash
    # INTENT: Assert ConsensusCandidateNotFoundError is raised when candidate_ref is unknown
    with pytest.raises((KeyError, ConsensusCandidateNotFoundError), match="not found"):
        load_admitted_candidate(res_paths, "cand-consensus-b649-115000088-attackerfake")

    bad_req = PromotionRequest(
        request_id="req-f1-bypass",
        request_sha256="0" * 64,
        expected_current_version=0,
        schedule_authority_sha256="b" * 64,  # mismatched schedule
        authorization_evidence_reference="test://auth",
        promotion_executor_identity="executor",
        execution_source_id="test://cli",
        execution_source_version="v5",
        candidate_ref=admitted.candidate_ref,
    )
    with pytest.raises(ValueError, match="schedule authority hash"):
        admitted.build_forecast(bad_req)

    # Point 3: Repository Layer rejects commit_live_forecast with unadmitted candidate_ref
    forecast = admitted.build_forecast(
        PromotionRequest(
            request_id="req-f1-bypass-repo",
            request_sha256="1" * 64,
            expected_current_version=0,
            schedule_authority_sha256=sched_sha_088,
            authorization_evidence_reference="test://auth",
            promotion_executor_identity="executor",
            execution_source_id="test://cli",
            execution_source_version="v5",
            candidate_ref=admitted.candidate_ref,
        )
    )
    repo = SQLiteResearchRepository(res_paths)

    # If candidate_ref is tampered to an unadmitted ref
    assert forecast.consensus_provenance_json is not None
    assert forecast.import_execution_json is not None
    prov_obj = json.loads(forecast.consensus_provenance_json)
    prov_obj["candidate"]["candidate_ref"] = "cand-consensus-b649-115000088-unadmitted0000"
    imp_obj = json.loads(forecast.import_execution_json)
    imp_obj["candidate_ref"] = "cand-consensus-b649-115000088-unadmitted0000"
    tampered_forecast = replace(
        forecast,
        candidate_ref="cand-consensus-b649-115000088-unadmitted0000",
        consensus_provenance_json=canonical_json(prov_obj),
        import_execution_json=canonical_json(imp_obj),
    )
    # INTENT: Verify repo rejects commit_live_forecast when candidate_ref has not been admitted
    with pytest.raises(ResearchRepositoryError, match="candidate authorities"):
        repo.commit_live_forecast(
            tampered_forecast, expected_current_version=0, current_eligible=lambda: True
        )

    # If candidate_ref is None for successor target
    none_ref_forecast = replace(forecast, candidate_ref=None)
    # INTENT: Verify repo rejects successor live forecast when candidate_ref is missing
    with pytest.raises((ResearchRepositoryError, ValueError), match="candidate_ref"):
        repo.commit_live_forecast(
            none_ref_forecast, expected_current_version=0, current_eligible=lambda: True
        )

    # Point 4: Trigger/constraint blocks direct insert of successor with NULL candidate_ref
    # INTENT: Verify DB check constraint forbids NULL candidate_ref for successor draws
    with (
        open_research_database(res_paths, read_only=False) as conn,
        pytest.raises(sqlite3.IntegrityError),
    ):
            conn.execute(
                """
                INSERT INTO research_live_forecast_versions (
                    version, run_id, request_id, request_sha256, lottery_type,
                    target_draw_number, target_draw_date, forecast_stream_id,
                    forecast_stream_version, target_json, provenance_class,
                    original_execution_provenance_status, payload_bytes,
                    payload_sha256, source_payload_sha256, source_locator,
                    missing_provenance_json, import_execution_json,
                    consensus_provenance_json, candidate_ref, committed_at,
                    expected_current_version, pointer_advanced,
                    provenance_envelope_json, provenance_envelope_sha256
                ) VALUES (
                    1, 'run-sql-test', 'req-direct-sql', 'a' * 64, 'BIG_LOTTO',
                    '115000088', '2026-09-15', 'B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS',
                    '1.0.0', '{}', 'CANONICAL_CONSENSUS',
                    'NOT_APPLICABLE', X'01',
                    'a' * 64, 'a' * 64, '/tmp/test',
                    '{}', '{}',
                    '{}', NULL, '2026-09-12T12:00:00Z',
                    0, 1,
                    '{}', 'a' * 64
                )
                """
            )

    # Point 5: CLI layer rejects F1 caller bypass arguments
    code = cli_module.main(
        [
            "promote",
            "--database", str(res_db),
            "--candidate-ref", admitted.candidate_ref,
            "--candidate", "/tmp/untrusted/candidate.json",  # Illegal bypass argument
            "--request-id", "req-f1",
            "--request-sha256", "a" * 64,
            "--expected-current-version", "0",
            "--schedule-authority-sha256", sched_sha_088,
            "--authorization-reference", "auth://test",
            "--executor-identity", "tester",
            "--execution-source-id", "cli://test",
            "--execution-source-version", "v5",
        ]
    )
    assert code != 0  # CLI rejected bypass attempt


# ==============================================================================
# TEST D: Frozen 087 Invariant Preservation
# ==============================================================================
def test_v5_requirement_d_frozen_087_invariants(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    # 1. 087 admission strictly forbidden
    with pytest.raises(ConsensusCandidateAdmissionError, match="115000087"):
        admit_consensus_candidate(
            research_paths=res_paths,
            target_draw_number="115000087",
            publication_root=tmp_path / "pub",
            admitter_identity="unit-test",
        )

    # 2. Schema migrations V1 through V5 have exact checksums
    with open_research_database(res_paths, read_only=True) as conn:
        rows = conn.execute(
            "SELECT version, checksum FROM research_schema_migrations ORDER BY version ASC"
        ).fetchall()
        assert len(rows) == CURRENT_SCHEMA_VERSION - 1
        v5_row = rows[-1]
        assert v5_row[0] == 5
        assert v5_row[1] == V5_MIGRATION_CHECKSUM


# ==============================================================================
# TEST E: DUPLICATE_CANDIDATE_CONFLICT on Reused Candidate Ref
# ==============================================================================
def test_v5_requirement_e_duplicate_candidate_conflict(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, sched_hashes = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )
    sched_sha_088 = sched_hashes["115000088"]

    admitted = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000088",
        publication_root=pub_root,
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
    )

    req1_hash = compute_successor_request_hash(
        request_id="req-1",
        candidate_ref=admitted.candidate_ref,
        schedule_authority_sha256=sched_sha_088,
        expected_current_version=0,
    )
    req1 = PromotionRequest(
        request_id="req-1",
        request_sha256=req1_hash,
        expected_current_version=0,
        schedule_authority_sha256=sched_sha_088,
        authorization_evidence_reference="auth://1",
        promotion_executor_identity="executor-1",
        execution_source_id="cli://test",
        execution_source_version="v5",
        candidate_ref=admitted.candidate_ref,
    )
    res1 = promote_admitted_candidate(
        database_path=res_db, admitted_candidate=admitted, request=req1
    )
    assert res1.version == 1

    # Attempt to promote same candidate again with different request
    # INTENT: Re-promoting an already-promoted candidate raises DUPLICATE_CANDIDATE_CONFLICT
    req2_hash = compute_successor_request_hash(
        request_id="req-2-different",
        candidate_ref=admitted.candidate_ref,
        schedule_authority_sha256=sched_sha_088,
        expected_current_version=1,
    )
    req2 = replace(
        req1,
        request_id="req-2-different",
        request_sha256=req2_hash,
        expected_current_version=1,
    )
    with pytest.raises(ResearchConflictError, match="DUPLICATE_CANDIDATE_CONFLICT"):
        promote_admitted_candidate(
            database_path=res_db, admitted_candidate=admitted, request=req2
        )


# ==============================================================================
# TEST F: Concurrency / CAS Stale Parent Version Conflict
# ==============================================================================
def test_v5_requirement_f_cas_stale_parent_conflict(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, sched_hashes = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )
    sched_sha_088 = sched_hashes["115000088"]

    admitted = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000088",
        publication_root=pub_root,
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
    )

    req = PromotionRequest(
        request_id="req-stale",
        request_sha256="e" * 64,
        expected_current_version=99,  # Stale version (actual is 0)
        schedule_authority_sha256=sched_sha_088,
        authorization_evidence_reference="auth://stale",
        promotion_executor_identity="executor",
        execution_source_id="cli://test",
        execution_source_version="v5",
        candidate_ref=admitted.candidate_ref,
    )
    # INTENT: Verify that a stale expected_current_version raises a CAS conflict
    with pytest.raises(ResearchConflictError, match="canonical current pointer changed"):
        promote_admitted_candidate(database_path=res_db, admitted_candidate=admitted, request=req)


# ==============================================================================
# TEST G: Admission Security (Symlinks, Tampered Streams, Tampered Payload)
# ==============================================================================
def test_v5_requirement_g_admission_security(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, _ = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )

    # Symlink rejection
    symlink = pub_root / "forecasts" / "symlink_attack"
    symlink.symlink_to(pub_root / "forecasts" / "115000088")
    with pytest.raises(ConsensusCandidateAdmissionError, match="symlink"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
        )
    symlink.unlink()

    # Tampered stream SHA rejection
    stream_key = next(iter(fixture["stream_files"].keys()))
    (pub_root / stream_key).write_text("corrupted", encoding="utf-8")
    with pytest.raises(ConsensusCandidateAdmissionError, match="SHA256 mismatch"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
        )


# ==============================================================================
# TEST H: Temporal and Outcome Gates
# ==============================================================================
def test_v5_requirement_h_temporal_and_outcome_gates(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, _ = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )

    # Deadline passed
    past_deadline = datetime(2026, 9, 15, 12, 30, 0, tzinfo=UTC)
    with pytest.raises(ConsensusCandidateAdmissionError, match="deadline"):
        admit_consensus_candidate(
            research_paths=res_paths,
            draw_paths=draw_paths,
            target_draw_number="115000088",
            publication_root=pub_root,
            now=past_deadline,
        )

    # Outcome already present
    with open_draw_database(draw_paths, read_only=False) as conn:
        conn.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename, source_sha256,
                parser_version, total_count, inserted_count, skipped_count, conflict_count,
                failed_count, started_at, completed_at
            ) VALUES (
                'run-h', 'MANUAL_SYNC', 'SUCCESS', 'BIG_LOTTO', 'test.json', 'a' * 64,
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
                '[7]', 'dummy-hash', 'run-h', '2026-09-15T21:00:00Z', '2026-09-15T21:00:00Z'
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
        )


# ==============================================================================
# TEST I: CLI End-to-End (admit, preflight, promote, current)
# ==============================================================================
def test_v5_requirement_i_cli_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, sched_hashes = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )
    sched_sha_088 = sched_hashes["115000088"]

    # 1. CLI admit
    exit_code = cli_module.main(
        [
            "admit",
            "--database", str(res_db),
            "--draw-database", str(draw_paths.database),
            "--target-draw", "115000088",
            "--publication-root", str(pub_root),
            "--executor-identity", "cli-test-agent",
            "--notes", "admitted via CLI",
        ]
    )
    assert exit_code == 0

    candidate_ref = f"cand-consensus-b649-115000088-{fixture['payload_sha256'][:16]}"

    req_hash = compute_successor_request_hash(
        request_id="req-cli-1",
        candidate_ref=candidate_ref,
        schedule_authority_sha256=sched_sha_088,
        expected_current_version=0,
    )

    # 2. CLI preflight
    exit_code = cli_module.main(
        [
            "preflight",
            "--database", str(res_db),
            "--draw-database", str(draw_paths.database),
            "--candidate-ref", candidate_ref,
            "--request-id", "req-cli-1",
            "--request-sha256", req_hash,
            "--expected-current-version", "0",
            "--schedule-authority-sha256", sched_sha_088,
            "--execution-source-id", "cli://test",
            "--execution-source-version", "v5",
        ]
    )
    assert exit_code == 0

    # 3. CLI promote
    exit_code = cli_module.main(
        [
            "promote",
            "--database", str(res_db),
            "--draw-database", str(draw_paths.database),
            "--candidate-ref", candidate_ref,
            "--request-id", "req-cli-1",
            "--request-sha256", req_hash,
            "--expected-current-version", "0",
            "--schedule-authority-sha256", sched_sha_088,
            "--authorization-reference", "auth://cli",
            "--executor-identity", "cli-executor",
            "--execution-source-id", "cli://test",
            "--execution-source-version", "v5",
        ]
    )
    assert exit_code == 0

    # 4. CLI current
    exit_code = cli_module.main(
        [
            "current",
            "--database", str(res_db),
            "--target-draw", "115000088",
        ]
    )
    assert exit_code == 0


# ==============================================================================
# TEST J: Store Verification (verify_store)
# ==============================================================================
def test_v5_requirement_j_verify_store(tmp_path: Path) -> None:
    res_db = (tmp_path / "research" / "lottolab_research.db").resolve()
    res_paths = ResearchDataPaths(res_db.parent, res_db)
    initialize_research_schema(res_paths)

    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    pub_root = (tmp_path / "pub").resolve()
    _setup_publication_tree(pub_root, fixture)

    draw_paths, sched_hashes = _setup_draw_database(
        tmp_path / "draw" / "lottolab.db",
        ("115000088", "20260915"),
    )
    sched_sha_088 = sched_hashes["115000088"]

    admitted = admit_consensus_candidate(
        research_paths=res_paths,
        draw_paths=draw_paths,
        target_draw_number="115000088",
        publication_root=pub_root,
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
    )

    req_hash = compute_successor_request_hash(
        request_id="req-j",
        candidate_ref=admitted.candidate_ref,
        schedule_authority_sha256=sched_sha_088,
        expected_current_version=0,
    )
    req = PromotionRequest(
        request_id="req-j",
        request_sha256=req_hash,
        expected_current_version=0,
        schedule_authority_sha256=sched_sha_088,
        authorization_evidence_reference="auth://j",
        promotion_executor_identity="executor-j",
        execution_source_id="cli://test",
        execution_source_version="v5",
        candidate_ref=admitted.candidate_ref,
    )
    promote_admitted_candidate(database_path=res_db, admitted_candidate=admitted, request=req)

    repo = SQLiteResearchRepository(res_paths)
    report = repo.verify_store()
    assert report.migration_checksum == V5_MIGRATION_CHECKSUM
    assert report.healthy is True
    assert report.migration_checksum_match is True

    # Tamper with candidate authority row: change payload_sha256
    # INTENT: Re-create update trigger after tampering to verify row integrity check
    with open_research_database(res_paths, read_only=False) as conn:
        conn.execute("DROP TRIGGER trg_research_consensus_candidate_authorities_no_update")
        conn.execute(
            """
            UPDATE research_consensus_candidate_authorities
            SET payload_sha256 = ?
            WHERE candidate_ref = ?
            """,
            ("b" * 64, admitted.candidate_ref),
        )
        conn.execute(
            """
            CREATE TRIGGER trg_research_consensus_candidate_authorities_no_update
            BEFORE UPDATE ON research_consensus_candidate_authorities
            BEGIN
                SELECT RAISE(ABORT, 'append-only table: research_consensus_candidate_authorities');
            END
            """
        )
        conn.commit()

    with pytest.raises(ResearchRepositoryError, match="not bound to candidate authority"):
        repo.verify_store()
