"""Unit tests for task-catalog derivation, stages, tombstones, and CLI."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lottolab.infrastructure import task_catalog
from lottolab.infrastructure.task_catalog import (
    REPORT_STRATA,
    TEN_INDICATORS,
    build_catalog,
    classify_task_stratum,
    compute_workflow_metrics,
    determine_project,
    find_in_catalog,
    find_task_folders,
)
from lottolab.interfaces.cli import task_catalog as task_catalog_cli
from lottolab.interfaces.cli.main import app as main_app


def _create_sqlite_db(path: Path, run_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE replay_backfill_runs (run_id TEXT PRIMARY KEY)")
        for rid in run_ids:
            conn.execute("INSERT INTO replay_backfill_runs VALUES (?)", (rid,))


def _tree_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return snapshot
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            snapshot[str(p.relative_to(root))] = (st.st_size, int(st.st_mtime))
    return snapshot


def test_tombstone_formats_and_exclusions(tmp_path: Path) -> None:
    """AC1(a) and AC1(b): Five deletion formats and non-tombstone exclusions."""
    task_root = tmp_path / "task-data" / "20261124" / "SAMPLE_TASK"
    task_root.mkdir(parents=True)
    (task_root / "result.json").write_text(json.dumps({"task_lifecycle_state": "COMPLETED"}))

    existing_file = tmp_path / "existing_source_receipt.json"
    existing_file.write_text("{}")

    # JSON with all formats
    manifest_data = {
        "cleanup_nested": {
            "deleted_db": {
                "path": "/nonexistent/deleted1.sqlite3",
                "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
                "size_bytes": 1000,
                "deleted_at": "2026-11-20T10:00:00Z",
            }
        },
        "action_deleted": {
            "status": "DELETED",
            "path": "/nonexistent/deleted2.sqlite3",
            "sha256": "2222222222222222222222222222222222222222222222222222222222222222",
            "size_bytes": 2000,
            "deleted_at": "2026-11-20T11:00:00Z",
        },
        "deleted_targets": [
            {
                "db_path": "/nonexistent/deleted3.sqlite3",
                "db_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
                "db_size_bytes": 3000,
                "manifest_path": "/nonexistent/deleted3_manifest.json",
                "manifest_sha256": (
                    "4444444444444444444444444444444444444444444444444444444444444444"
                ),
                "manifest_size_bytes": 400,
                "deleted_at": "2026-11-20T12:00:00Z",
                # Under deleted_targets, but path actually exists
                "source_receipt_path": str(existing_file.resolve()),
            }
        ],
        "deleted_artifacts": [
            {
                "path": "/nonexistent/deleted4.sqlite3",
                "sha256": "5555555555555555555555555555555555555555555555555555555555555555",
                "size_bytes": 5000,
                "deleted_at": "2026-11-20T13:00:00Z",
            }
        ],
        # Exclusion: RETAINED status
        "retained_target": {
            "status": "RETAINED",
            "path": "/nonexistent/retained.sqlite3",
            "sha256": "6666666666666666666666666666666666666666666666666666666666666666",
            "size_bytes": 6000,
        },
    }
    (task_root / "manifest.json").write_text(json.dumps(manifest_data))

    # Quarantine manifest with deleted.files
    q_dir = tmp_path / "backups" / "_quarantine_20261120"
    q_dir.mkdir(parents=True)
    q_manifest_data = {
        "task_id": "PURGE_TASK",
        "deleted": {
            "at": "2026-11-20T14:00:00Z",
            "files": ["deleted5.sqlite3"],
        },
    }
    (q_dir / "QUARANTINE_MANIFEST.json").write_text(json.dumps(q_manifest_data))

    out_dir = tmp_path / "_catalog"
    formal_db = tmp_path / "formal.sqlite3"
    _create_sqlite_db(formal_db, [])

    build_catalog(
        roots=[tmp_path / "task-data"],
        output_dir=out_dir,
        formal_db_path=formal_db,
        quarantine_manifest_paths=[q_dir / "QUARANTINE_MANIFEST.json"],
    )

    tombstone_lines = (out_dir / "tombstones.jsonl").read_text().strip().splitlines()
    tombstones = [json.loads(line) for line in tombstone_lines]
    tombstone_paths = {t["path"] for t in tombstones}

    # Verify all 5 formats produced tombstones
    assert "/nonexistent/deleted1.sqlite3" in tombstone_paths
    assert "/nonexistent/deleted2.sqlite3" in tombstone_paths
    assert "/nonexistent/deleted3.sqlite3" in tombstone_paths
    assert "/nonexistent/deleted3_manifest.json" in tombstone_paths
    assert "/nonexistent/deleted4.sqlite3" in tombstone_paths
    q_target = str((q_dir / "deleted5.sqlite3").resolve())
    assert q_target in tombstone_paths
    q_tomb = next(t for t in tombstones if t["path"] == q_target)
    assert q_tomb["deleted_at"] == "2026-11-20T14:00:00Z"
    assert q_tomb["deleted_at_source"] == "ANCESTOR"
    assert q_tomb["sha256"] is None

    # Verify exclusions: retained is not in tombstones
    assert "/nonexistent/retained.sqlite3" not in tombstone_paths
    # Existing source_receipt_path is not in tombstones
    assert str(existing_file.resolve()) not in tombstone_paths

    # Verify deletion_claims_path_exists in meta
    meta = json.loads((out_dir / "catalog_meta.json").read_text())
    claims = meta["deletion_claims_path_exists"]
    assert claims["count"] >= 1
    sample_paths = [s["path"] for s in claims["samples"]]
    assert str(existing_file.resolve()) in sample_paths


def test_tombstone_merge_rules(tmp_path: Path) -> None:
    """AC1(c): Merge rules for tombstones."""
    task_root = tmp_path / "task-data" / "20261124" / "MERGE_TASK"
    task_root.mkdir(parents=True)
    (task_root / "result.json").write_text("{}")

    shared_sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    file1_data = {
        "action": {
            "status": "DELETED",
            "path": "/nonexistent/path_a.sqlite3",
            "sha256": shared_sha,
            "size_bytes": 1234,
            "deleted_at": "2026-11-20T10:00:00Z",
        }
    }
    file2_data = {
        "deleted_targets": [
            {
                # Same (path, sha256)
                "db_path": "/nonexistent/path_a.sqlite3",
                "db_sha256": shared_sha,
                "db_size_bytes": 1234,
                "deleted_at": "2026-11-20T11:00:00Z",
            },
            {
                # Same sha256, different path
                "db_path": "/nonexistent/path_b.sqlite3",
                "db_sha256": shared_sha,
                "db_size_bytes": 1234,
                "deleted_at": "2026-11-20T12:00:00Z",
            },
        ]
    }
    (task_root / "cleanup1.json").write_text(json.dumps(file1_data))
    (task_root / "cleanup2.json").write_text(json.dumps(file2_data))

    out_dir = tmp_path / "_catalog"
    formal_db = tmp_path / "formal.sqlite3"
    _create_sqlite_db(formal_db, [])

    build_catalog(
        roots=[tmp_path / "task-data"],
        output_dir=out_dir,
        formal_db_path=formal_db,
        quarantine_manifest_paths=[],
    )

    tombstones = [
        json.loads(line) for line in (out_dir / "tombstones.jsonl").read_text().strip().splitlines()
    ]
    by_path = {t["path"]: t for t in tombstones}

    # path_a must be merged into 1 row with 2 sources
    assert "/nonexistent/path_a.sqlite3" in by_path
    assert len(by_path["/nonexistent/path_a.sqlite3"]["sources"]) == 2

    # path_b must be a distinct row with 1 source
    assert "/nonexistent/path_b.sqlite3" in by_path
    assert len(by_path["/nonexistent/path_b.sqlite3"]["sources"]) == 1


def test_task_folder_discovery_rules(tmp_path: Path) -> None:
    """AC1(d): Task folder candidate discovery rules."""
    root = tmp_path / "task-data"
    root.mkdir()

    # 1. 8-digit date folder with result.json -> found
    d1 = root / "20261124" / "TASK_WITH_DATE"
    d1.mkdir(parents=True)
    (d1 / "result.json").write_text("{}")

    # 2. Non-date folder with packet.md -> found
    d2 = root / "TASK_NO_DATE"
    d2.mkdir()
    (d2 / "packet.md").write_text("TASK_ID: TASK_NO_DATE")

    # 3. Starts with _ -> skipped
    d3 = root / "_scratch" / "NOT_A_TASK"
    d3.mkdir(parents=True)
    (d3 / "result.json").write_text("{}")

    # 4. Starts with . -> skipped
    d4 = root / ".hidden" / "NOT_A_TASK"
    d4.mkdir(parents=True)
    (d4 / "result.json").write_text("{}")

    # 5. Symlink to directory -> skipped
    real_target = tmp_path / "real_task"
    real_target.mkdir()
    (real_target / "result.json").write_text("{}")
    link_d = root / "LINK_TASK"
    link_d.symlink_to(real_target, target_is_directory=True)

    folders = find_task_folders([root])
    found_ids = {f.task_id for f in folders}
    assert "TASK_WITH_DATE" in found_ids
    assert "TASK_NO_DATE" in found_ids
    assert "NOT_A_TASK" not in found_ids
    assert "LINK_TASK" not in found_ids


def test_project_determination(tmp_path: Path) -> None:
    """AC1(e): Project determination returns MSA, OTHER, and UNKNOWN."""
    msa_root = tmp_path / "msa"
    msa_root.mkdir()

    # 1. Under MSA root -> MSA
    under_msa = msa_root / ".task-data" / "TASK_MSA_1"
    under_msa.mkdir(parents=True)
    assert determine_project(under_msa, msa_root) == "MSA"

    # 2. Outside MSA, packet.md contains MathStatisticalAnalysis -> MSA
    outside_msa_1 = tmp_path / "other" / "TASK_MSA_2"
    outside_msa_1.mkdir(parents=True)
    (outside_msa_1 / "packet.md").write_text("Repository: MathStatisticalAnalysis")
    assert determine_project(outside_msa_1, msa_root) == "MSA"

    # 3. Outside MSA, both readable, neither has string -> OTHER
    outside_msa_2 = tmp_path / "other" / "TASK_OTHER"
    outside_msa_2.mkdir(parents=True)
    (outside_msa_2 / "packet.md").write_text("Project: WordGame")
    (outside_msa_2 / "result.json").write_text('{"project": "WordGame"}')
    assert determine_project(outside_msa_2, msa_root) == "OTHER"

    # 4. Outside MSA, neither readable -> UNKNOWN
    outside_msa_3 = tmp_path / "other" / "TASK_UNKNOWN"
    outside_msa_3.mkdir(parents=True)
    assert determine_project(outside_msa_3, msa_root) == "UNKNOWN"


def test_fact_state_and_write_lease(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1(f): Four fact_state results and SKIPPED_WRITE_LEASE."""
    msa_root = tmp_path / "project"
    scratch = msa_root / ".task-data" / "_scratch"
    scratch.mkdir(parents=True)

    monkeypatch.setattr(task_catalog, "canonical_project_root", lambda: msa_root)

    run1 = "1111111111111111111111111111111111111111111111111111111111111111"
    run2 = "2222222222222222222222222222222222222222222222222222222222222222"
    formal_db = msa_root / "data" / "databases" / "replay-backfill.sqlite3"
    _create_sqlite_db(formal_db, [run1])

    # Case 1: MERGED_STAGE_PRESENT (all run_ids in formal db, db exists)
    db1 = scratch / "stage1.sqlite3"
    db1.write_text("fake db")
    m1 = scratch / "stage1" / "MERGE_PENDING.json"
    m1.parent.mkdir(parents=True)
    m1.write_text(json.dumps({"task_id": "T1", "db_path": str(db1), "run_ids": [run1]}))

    # Case 2: MERGED_DB_MISSING (all run_ids in formal db, db missing)
    m2 = scratch / "stage2" / "MERGE_PENDING.json"
    m2.parent.mkdir(parents=True)
    m2.write_text(
        json.dumps({"task_id": "T2", "db_path": "/missing/stage2.sqlite3", "run_ids": [run1]})
    )

    # Case 3: MERGE_PENDING (run_ids not all in formal db)
    m3 = scratch / "stage3" / "MERGE_PENDING.json"
    m3.parent.mkdir(parents=True)
    m3.write_text(
        json.dumps({"task_id": "T3", "db_path": "/missing/stage3.sqlite3", "run_ids": [run2]})
    )

    # Case 4: UNKNOWN (no run_ids)
    m4 = scratch / "stage4" / "MERGE_PENDING.json"
    m4.parent.mkdir(parents=True)
    m4.write_text(
        json.dumps({"task_id": "T4", "db_path": "/missing/stage4.sqlite3", "run_ids": []})
    )

    out_dir = tmp_path / "_catalog"
    build_catalog(
        roots=[msa_root / ".task-data"],
        output_dir=out_dir,
        formal_db_path=formal_db,
        quarantine_manifest_paths=[],
    )

    stages = [
        json.loads(line) for line in (out_dir / "stages.jsonl").read_text().strip().splitlines()
    ]
    by_task = {s["task_id"]: s for s in stages}
    assert by_task["T1"]["fact_state"] == "MERGED_STAGE_PRESENT"
    assert by_task["T2"]["fact_state"] == "MERGED_DB_MISSING"
    assert by_task["T3"]["fact_state"] == "MERGE_PENDING"
    assert by_task["T4"]["fact_state"] == "UNKNOWN"

    # With write lease lock file present:
    lease_file = msa_root / "data" / "databases" / "locks" / "replay-backfill.sqlite3.lease.json"
    lease_file.parent.mkdir(parents=True, exist_ok=True)
    lease_file.write_text("{}")

    build_catalog(
        roots=[msa_root / ".task-data"],
        output_dir=out_dir,
        formal_db_path=formal_db,
        write_lease_path=lease_file,
        quarantine_manifest_paths=[],
    )
    meta = json.loads((out_dir / "catalog_meta.json").read_text())
    assert meta["formal_db"]["lookup"] == "SKIPPED_WRITE_LEASE"
    stages_leased = [
        json.loads(line) for line in (out_dir / "stages.jsonl").read_text().strip().splitlines()
    ]
    # Without lookup, fact_state must be UNKNOWN
    for s in stages_leased:
        assert s["fact_state"] == "UNKNOWN"


def test_json_size_limit_skipped(tmp_path: Path) -> None:
    """AC1(g): Files exceeding size limit are marked as skipped."""
    task_root = tmp_path / "task-data" / "20261124" / "LARGE_TASK"
    task_root.mkdir(parents=True)
    (task_root / "packet.md").write_text("LARGE_TASK packet")
    large_file = task_root / "large_manifest.json"
    large_file.write_text(json.dumps({"key": "value"}))
    large_result = task_root / "result.json"
    large_result.write_text(json.dumps({"too_large": True}))

    out_dir = tmp_path / "_catalog"
    formal_db = tmp_path / "formal.sqlite3"
    _create_sqlite_db(formal_db, [])

    # Lower size limit to 5 bytes
    build_catalog(
        roots=[tmp_path / "task-data"],
        output_dir=out_dir,
        formal_db_path=formal_db,
        quarantine_manifest_paths=[],
        max_json_size_bytes=5,
    )

    meta = json.loads((out_dir / "catalog_meta.json").read_text())
    skipped_by_path = {s["path"]: s for s in meta["skipped"]}
    assert str(large_file.resolve()) in skipped_by_path
    assert skipped_by_path[str(large_file.resolve())]["reason"] == "TOO_LARGE"
    assert skipped_by_path[str(large_file.resolve())]["size_bytes"] == large_file.stat().st_size
    assert skipped_by_path[str(large_result.resolve())]["reason"] == "TOO_LARGE"
    assert skipped_by_path[str(large_result.resolve())]["size_bytes"] == large_result.stat().st_size

    task_rows = [json.loads(line) for line in (out_dir / "tasks.jsonl").read_text().splitlines()]
    large_task = next(row for row in task_rows if row["task_id"] == "LARGE_TASK")
    assert large_task["result_json_status"] == "TOO_LARGE"


def test_explicit_root_controls_scratch_stage_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical_root = tmp_path / "canonical-project"
    selected_root = tmp_path / "selected-data"
    monkeypatch.setattr(task_catalog, "canonical_project_root", lambda: canonical_root)
    monkeypatch.setattr(task_catalog_cli, "canonical_project_root", lambda: canonical_root)

    canonical_manifest = (
        canonical_root / ".task-data" / "_scratch" / "canonical" / "MERGE_PENDING.json"
    )
    canonical_manifest.parent.mkdir(parents=True)
    canonical_manifest.write_text(json.dumps({"task_id": "CANONICAL_ROOT", "run_ids": []}))

    selected_manifest = selected_root / "_scratch" / "selected" / "MERGE_PENDING.json"
    selected_manifest.parent.mkdir(parents=True)
    selected_manifest.write_text(json.dumps({"task_id": "SELECTED_ROOT", "run_ids": []}))

    out_dir = tmp_path / "_catalog"
    result = CliRunner().invoke(
        main_app,
        [
            "task-catalog",
            "build",
            "--root",
            str(selected_root),
            "--output-dir",
            str(out_dir),
            "--formal-db",
            str(tmp_path / "unused-formal.sqlite3"),
            "--no-formal-lookup",
        ],
    )
    assert result.exit_code == 0, result.output

    stages = [json.loads(line) for line in (out_dir / "stages.jsonl").read_text().splitlines()]
    assert [stage["task_id"] for stage in stages] == ["SELECTED_ROOT"]
    assert stages[0]["manifest_path"] == str(selected_manifest.resolve())


def test_deterministic_build_and_input_preservation(tmp_path: Path) -> None:
    """AC1(h) and AC1(j): Byte-for-byte identical output and unchanged inputs."""
    task_root = tmp_path / "task-data" / "20261124" / "TASK_DET"
    task_root.mkdir(parents=True)
    (task_root / "packet.md").write_text("Deterministic test")
    (task_root / "result.json").write_text(
        json.dumps(
            {
                "task_lifecycle_state": "COMPLETED",
                "run_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            }
        )
    )

    formal_db = tmp_path / "formal.sqlite3"
    _create_sqlite_db(
        formal_db, ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
    )

    out_dir1 = tmp_path / "_catalog1"
    out_dir2 = tmp_path / "_catalog2"

    snap_before = _tree_snapshot(tmp_path / "task-data")

    build_catalog(
        roots=[tmp_path / "task-data"],
        output_dir=out_dir1,
        formal_db_path=formal_db,
        quarantine_manifest_paths=[],
    )
    build_catalog(
        roots=[tmp_path / "task-data"],
        output_dir=out_dir2,
        formal_db_path=formal_db,
        quarantine_manifest_paths=[],
    )

    snap_after = _tree_snapshot(tmp_path / "task-data")
    assert snap_before == snap_after

    for fname in ["tasks.jsonl", "stages.jsonl", "tombstones.jsonl"]:
        b1 = (out_dir1 / fname).read_bytes()
        b2 = (out_dir2 / fname).read_bytes()
        assert b1 == b2, f"{fname} differs across runs"


def test_find_command_kinds_and_missing_catalog(tmp_path: Path) -> None:
    """AC1(i): find command kinds and missing catalog handling."""
    cat_dir = tmp_path / "_catalog"
    cat_dir.mkdir()

    (cat_dir / "tasks.jsonl").write_text('{"task_id": "T_FIND_1"}\n')
    (cat_dir / "stages.jsonl").write_text('{"manifest_path": "/stage/find_2"}\n')
    (cat_dir / "tombstones.jsonl").write_text('{"path": "/tomb/find_3"}\n')

    count_all, _ = find_in_catalog("find", "all", cat_dir)
    assert count_all == 3

    count_tasks, matches_tasks = find_in_catalog("find", "tasks", cat_dir)
    assert count_tasks == 1
    assert matches_tasks[0][0] == "tasks"

    count_stages, matches_stages = find_in_catalog("find", "stages", cat_dir)
    assert count_stages == 1
    assert matches_stages[0][0] == "stages"

    count_tomb, matches_tomb = find_in_catalog("find", "tombstones", cat_dir)
    assert count_tomb == 1
    assert matches_tomb[0][0] == "tombstones"

    # Missing catalog
    with pytest.raises(FileNotFoundError):
        find_in_catalog("find", "tasks", tmp_path / "missing_dir")


def test_cli_help() -> None:
    """AC1(k): task-catalog --help exit code is 0."""
    runner = CliRunner()
    result = runner.invoke(main_app, ["task-catalog", "--help"])
    assert result.exit_code == 0
    assert "task-catalog" in result.output


def test_stratum_classification_mapping(tmp_path: Path) -> None:
    """AC4: Verify stratum classification maps tasks to S1..S6 and handles UNKNOWN."""
    # S1: FAST
    assert classify_task_stratum({"stratum": "S1"}) == "S1"
    assert classify_task_stratum({"route": {"worker_route": "FAST"}}) == "S1"
    assert classify_task_stratum({"task_id": "TASK_FAST_TEST"}) is None

    # S2: STANDARD/NORMAL
    assert classify_task_stratum({"stratum": "S2"}) == "S2"
    assert (
        classify_task_stratum(
            {"route": {"worker_route": "STANDARD", "implementation_depth": "NORMAL"}}
        )
        == "S2"
    )
    assert classify_task_stratum({"task_id": "TASK_STANDARD_NORMAL"}) is None

    # S3: STANDARD/ENHANCED
    assert classify_task_stratum({"stratum": "S3"}) == "S3"
    assert (
        classify_task_stratum(
            {"route": {"worker_route": "STANDARD", "implementation_depth": "ENHANCED"}}
        )
        == "S3"
    )
    assert classify_task_stratum({"task_id": "TASK_ENHANCED_EXPLORATION"}) is None

    # S4: JUDGED
    assert classify_task_stratum({"stratum": "S4"}) == "S4"
    assert classify_task_stratum({"route": {"judge_mode": "FRESH_CONTEXT"}}) == "S4"
    assert classify_task_stratum({"route": {"worker_route": "STANDARD_JUDGED"}}) == "S4"
    assert classify_task_stratum({"task_id": "TASK_JUDGED_RUN"}) is None

    # S5: RESEARCH
    assert classify_task_stratum({"stratum": "S5"}) == "S5"
    assert classify_task_stratum({"route": {"task_class": "RESEARCH"}}) == "S5"
    assert classify_task_stratum({"stage_manifests": ["/path/to/stage.json"]}) == "S5"
    assert (
        classify_task_stratum(
            {
                "route": {
                    "task_class": "RESEARCH",
                    "worker_route": "STANDARD",
                    "implementation_depth": "ENHANCED",
                }
            }
        )
        == "S5"
    )
    assert (
        classify_task_stratum(
            {
                "stratum": "S2",
                "route": {
                    "task_class": "RESEARCH",
                    "worker_route": "STANDARD",
                    "implementation_depth": "ENHANCED",
                },
            }
        )
        is None
    )
    assert classify_task_stratum({"task_id": "TASK_RESEARCH_REPLAY"}) is None

    # S6: RELEASE_CLOSEOUT
    assert classify_task_stratum({"stratum": "S6"}) == "S6"
    assert classify_task_stratum({"route": {"task_class": "RELEASE_CLOSEOUT"}}) == "S6"
    assert (
        classify_task_stratum(
            {
                "route": {
                    "task_class": "RELEASE_CLOSEOUT",
                    "worker_route": "STANDARD",
                    "implementation_depth": "NORMAL",
                }
            }
        )
        == "S6"
    )
    assert classify_task_stratum({"task_id": "TASK_RELEASE_CLOSEOUT_PR88"}) is None

    # Indeterminate / unknown stratum
    assert classify_task_stratum({"task_id": "UNCATEGORIZED_RANDOM_NAME"}) is None

    # On-disk packet / result resolution
    task_dir = tmp_path / "on_disk_task"
    task_dir.mkdir()
    (task_dir / "packet.md").write_text("WORKER_ROUTE: FAST\nIMPLEMENTATION_DEPTH: NORMAL\n")
    assert classify_task_stratum({"task_id": "SOME_ID", "path": str(task_dir)}) is None


def test_boundary_dates_inclusion_and_exclusion() -> None:
    """AC4: Verify boundary dates for fixed window 2026-11-18 to 2026-11-24."""
    tasks: list[dict[str, object]] = [
        {"task_id": "T_BEFORE", "date_folder": "20261117", "stratum": "S1"},
        {"task_id": "T_START", "date_folder": "20261118", "stratum": "S1"},
        {"task_id": "T_MID", "date_folder": "20261121", "stratum": "S2"},
        {"task_id": "T_END", "date_folder": "20261124", "stratum": "S3"},
        {"task_id": "T_AFTER", "date_folder": "20261125", "stratum": "S1"},
    ]

    report = compute_workflow_metrics(
        catalog_dir=Path("/dummy"),
        start_date="2026-11-18",
        end_date="2026-11-24",
        read_folder_receipts=False,
        tasks_data=tasks,
    )

    assert report.total_tasks_evaluated == 3
    assert report.tasks_by_stratum["S1"] == 1  # only T_START, T_BEFORE & T_AFTER excluded
    assert report.tasks_by_stratum["S2"] == 1
    assert report.tasks_by_stratum["S3"] == 1
    assert report.tasks_by_stratum["S4"] == 0
    assert report.window_start == "2026-11-18"
    assert report.window_end == "2026-11-24"


def test_family_rates_measurable_and_missing_cases() -> None:
    """AC4: Calculation family 1 (Rates): measurable vs missing evidence cases."""
    # Case A: Fully measurable S2 stratum tasks (1 pass, 1 fail, 1 blocked avoidable)
    measurable_tasks: list[dict[str, object]] = [
        {
            "task_id": "T1_PASS",
            "date_folder": "20261120",
            "stratum": "S2",
            "task_lifecycle_state": "COMPLETED",
            "is_continuation": False,
            "continues_from": "NONE",
            "result_json_status": "OK",
            "regression_escape": False,
            "acceptance_confirmed": True,
            "first_pass_accepted": True,
            "goal_72h_completed": True,
        },
        {
            "task_id": "T2_FAIL",
            "date_folder": "20261120",
            "stratum": "S2",
            "task_lifecycle_state": "COMPLETED",
            "is_continuation": False,
            "continues_from": "NONE",
            "result_json_status": "OK",
            "regression_escape": True,
            "acceptance_confirmed": True,
            "first_pass_accepted": False,
            "goal_72h_completed": True,
        },
        {
            "task_id": "T3_BLOCKED",
            "date_folder": "20261120",
            "stratum": "S2",
            "task_lifecycle_state": "BLOCKED",
            "issue_type": "AUTH",
            "avoidable_block": True,
            "first_pass_accepted": False,
            "goal_72h_completed": False,
            "is_continuation": False,
            "continues_from": "NONE",
            "result_json_status": "OK",
        },
    ]

    rep_a = compute_workflow_metrics(
        catalog_dir=Path("/dummy"),
        read_folder_receipts=False,
        tasks_data=measurable_tasks,
    )

    by_ind_a = {m.indicator: m for m in rep_a.metrics if m.stratum == "S2"}

    # FIRST_PASS_ACCEPTANCE_RATE: 1 pass out of 3 evaluated (one pass, one fail, one blocked)
    fp_a = by_ind_a["FIRST_PASS_ACCEPTANCE_RATE"]
    assert fp_a.status == "MEASURED"
    assert fp_a.numerator == 1
    assert fp_a.denominator == 3
    assert fp_a.unknown_count == 0
    assert fp_a.value == 0.3333

    # FINAL_GOAL_COMPLETION_RATE: 2 completed (T1, T2) out of 3
    fg_a = by_ind_a["FINAL_GOAL_COMPLETION_RATE"]
    assert fg_a.status == "MEASURED"
    assert fg_a.numerator == 2
    assert fg_a.denominator == 3
    assert fg_a.unknown_count == 0

    # AVOIDABLE_BLOCK_RATE: 1 blocked, issue_type=AUTH -> 1/1 avoidable
    ab_a = by_ind_a["AVOIDABLE_BLOCK_RATE"]
    assert ab_a.status == "MEASURED"
    assert ab_a.numerator == 1
    assert ab_a.denominator == 1
    assert ab_a.unknown_count == 0

    # REGRESSION_ESCAPE_RATE: 1 escape out of 2 completed
    re_a = by_ind_a["REGRESSION_ESCAPE_RATE"]
    assert re_a.status == "PARTIAL"
    assert re_a.numerator == 1
    assert re_a.denominator == 2
    assert re_a.unknown_count == 1

    # Case B: Missing / ambiguous evidence: unknowns remain visible, denominator does not shrink
    ambiguous_tasks: list[dict[str, object]] = [
        {
            "task_id": "T_UNKNOWN_RECEIPT",
            "date_folder": "20261120",
            "stratum": "S2",
            "result_json_status": "MISSING",
            "task_lifecycle_state": None,
        },
        {
            "task_id": "T_BLOCKED_INDETERMINATE",
            "date_folder": "20261120",
            "stratum": "S2",
            "result_json_status": "OK",
            "task_lifecycle_state": "BLOCKED",
            # issue_type missing!
        },
    ]

    rep_b = compute_workflow_metrics(
        catalog_dir=Path("/dummy"),
        read_folder_receipts=False,
        tasks_data=ambiguous_tasks,
    )

    by_ind_b = {m.indicator: m for m in rep_b.metrics if m.stratum == "S2"}

    # Missing initial-lineage evidence keeps both rows UNKNOWN.
    fp_b = by_ind_b["FIRST_PASS_ACCEPTANCE_RATE"]
    assert fp_b.status == "UNKNOWN"
    assert fp_b.denominator == 0
    assert fp_b.unknown_count == 2
    assert fp_b.eligible_count == 2  # Denominator did not shrink eligible count!

    # AVOIDABLE_BLOCK_RATE: 1 blocked, but issue_type is missing -> UNKNOWN
    ab_b = by_ind_b["AVOIDABLE_BLOCK_RATE"]
    assert ab_b.status == "UNKNOWN"
    assert ab_b.unknown_count == 2
    assert ab_b.eligible_count == 2
    assert ab_b.value is None


def test_family_counts_durations_costs_measurable_and_missing_cases() -> None:
    """AC4: Calculation families 2 (Counts), 3 (Durations), 4 (Costs)."""
    measurable_tasks: list[dict[str, object]] = [
        {
            "task_id": "T_MEAS_1",
            "date_folder": "20261122",
            "stratum": "S3",
            "task_lifecycle_state": "COMPLETED",
            "unproductive_continuation_count": 2,
            "owner_intervention_count": 1,
            "dispatch_to_acceptance_seconds": 1200.0,
            "acceptance_to_adoption_seconds": 3600.0,
            "tokens": 50000,
            "model_tier": "strong",
            "model_identity": "model-alpha",
            "route": {"worker_route": "STANDARD", "implementation_depth": "ENHANCED"},
            "adopted_outcome": True,
            "resource_cost_measured": 1048576,
            "task_folder_bytes_reported": 1048576,
        },
        {
            "task_id": "T_MEAS_2",
            "date_folder": "20261122",
            "stratum": "S3",
            "task_lifecycle_state": "COMPLETED",
            "unproductive_continuation_count": 0,
            "owner_intervention_count": 0,
            "dispatch_to_acceptance_seconds": 1800.0,
            "acceptance_to_adoption_seconds": 7200.0,
            "tokens": 70000,
            "model_tier": "strong",
            "model_identity": "model-alpha",
            "route": {"worker_route": "STANDARD", "implementation_depth": "ENHANCED"},
            "adopted_outcome": True,
            "resource_cost_measured": 2097152,
            "task_folder_bytes_reported": 2097152,
        },
    ]

    rep_a = compute_workflow_metrics(
        catalog_dir=Path("/dummy"),
        read_folder_receipts=False,
        tasks_data=measurable_tasks,
    )
    by_ind_a = {m.indicator: m for m in rep_a.metrics if m.stratum == "S3"}

    # Counts
    up_a = by_ind_a["UNPRODUCTIVE_CONTINUATION_COUNT"]
    assert up_a.status == "MEASURED"
    assert up_a.value == 2
    assert up_a.unknown_count == 0

    oi_a = by_ind_a["OWNER_INTERVENTION_COUNT"]
    assert oi_a.status == "MEASURED"
    assert oi_a.value == 1
    assert oi_a.unknown_count == 0

    # Durations: mean of 1200 and 1800 is 1500; mean of 3600 and 7200 is 5400
    da_a = by_ind_a["DISPATCH_TO_ACCEPTANCE_TIME"]
    assert da_a.status == "MEASURED"
    assert da_a.value == 1500.0
    assert da_a.unknown_count == 0

    aa_a = by_ind_a["ACCEPTANCE_TO_ADOPTION_TIME"]
    assert aa_a.status == "MEASURED"
    assert aa_a.value == 5400.0
    assert aa_a.unknown_count == 0

    # Costs: tokens per accepted outcome = 120000 / 2 = 60000
    mc_a = by_ind_a["MODEL_COST_PER_ACCEPTED_OUTCOME"]
    assert mc_a.status == "MEASURED"
    assert mc_a.value == 60000.0
    assert mc_a.unknown_count == 0

    # Legacy scalar bytes and folder size do not form the required resource vector.
    rc_a = by_ind_a["RESOURCE_COST"]
    assert rc_a.status == "UNKNOWN"
    assert rc_a.value is None
    assert rc_a.unknown_count == 2

    # Missing cases
    missing_tasks: list[dict[str, object]] = [
        {
            "task_id": "T_MISSING_DATA",
            "date_folder": "20261122",
            "stratum": "S3",
            "task_lifecycle_state": "COMPLETED",
        }
    ]
    rep_b = compute_workflow_metrics(
        catalog_dir=Path("/dummy"),
        read_folder_receipts=False,
        tasks_data=missing_tasks,
    )
    by_ind_b = {m.indicator: m for m in rep_b.metrics if m.stratum == "S3"}

    assert by_ind_b["UNPRODUCTIVE_CONTINUATION_COUNT"].status == "UNKNOWN"
    assert by_ind_b["UNPRODUCTIVE_CONTINUATION_COUNT"].unknown_count == 1
    assert by_ind_b["OWNER_INTERVENTION_COUNT"].status == "UNKNOWN"
    assert by_ind_b["DISPATCH_TO_ACCEPTANCE_TIME"].status == "UNKNOWN"
    assert by_ind_b["ACCEPTANCE_TO_ADOPTION_TIME"].status == "UNKNOWN"
    assert by_ind_b["MODEL_COST_PER_ACCEPTED_OUTCOME"].status == "UNKNOWN"
    assert by_ind_b["RESOURCE_COST"].status == "UNKNOWN"


def test_cli_task_catalog_metrics_command(tmp_path: Path) -> None:
    """AC1 and AC4: CLI task-catalog metrics invocation, formats, and file output."""
    cat_dir = tmp_path / "_catalog"
    cat_dir.mkdir()

    sample_tasks = [
        {
            "task_id": "SAMPLE_TASK_S1",
            "date_folder": "20261119",
            "stratum": "S1",
            "task_lifecycle_state": "COMPLETED",
            "is_continuation": False,
            "result_json_status": "OK",
            "task_folder_bytes_reported": 5000,
        },
        {
            "task_id": "SAMPLE_TASK_S5",
            "date_folder": "20261120",
            "stratum": "S5",
            "task_lifecycle_state": "COMPLETED",
            "is_continuation": False,
            "result_json_status": "OK",
            "stage_manifests": ["/stage.json"],
        },
    ]

    with open(cat_dir / "tasks.jsonl", "w", encoding="utf-8") as f:
        for t in sample_tasks:
            f.write(json.dumps(t) + "\n")

    report_file = tmp_path / "baseline_report.md"
    runner = CliRunner()

    # 1. Markdown output with --output-file
    res_md = runner.invoke(
        main_app,
        [
            "task-catalog",
            "metrics",
            "--catalog-dir",
            str(cat_dir),
            "--output-format",
            "markdown",
            "--output-file",
            str(report_file),
            "--no-receipt-lookup",
        ],
    )
    assert res_md.exit_code == 0
    assert report_file.is_file()
    md_content = report_file.read_text(encoding="utf-8")
    assert "# Task Workflow Effect Metrics Baseline Report" in md_content
    for ind in TEN_INDICATORS:
        assert ind in md_content
    for st in REPORT_STRATA:
        assert f"| {st} |" in md_content

    # 2. JSON output
    res_json = runner.invoke(
        main_app,
        [
            "task-catalog",
            "metrics",
            "--catalog-dir",
            str(cat_dir),
            "--output-format",
            "json",
            "--no-receipt-lookup",
        ],
    )
    assert res_json.exit_code == 0
    parsed = json.loads(res_json.output)
    assert parsed["window_start"] == "2026-11-18"
    assert parsed["window_end"] == "2026-11-24"
    assert len(parsed["metrics"]) == 60  # 10 indicators * 6 strata

    # 3. Text output
    res_txt = runner.invoke(
        main_app,
        [
            "task-catalog",
            "metrics",
            "--catalog-dir",
            str(cat_dir),
            "--output-format",
            "text",
            "--no-receipt-lookup",
        ],
    )
    assert res_txt.exit_code == 0
    assert "WORKFLOW EFFECT METRICS BASELINE" in res_txt.output


def test_explicit_evidence_not_lifecycle_or_incident_proxies() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "T_R2",
            "date_folder": "20261120",
            "stratum": "S1",
            "task_lifecycle_state": "COMPLETED",
            "is_continuation": False,
            "acceptance_confirmed": False,
            "issue_type": "AUTH",
        },
        {
            "task_id": "T_CONT",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "T_R2",
            "same_original_task": True,
            "goal_72h_completed": True,
            "is_continuation": True,
            "task_lifecycle_state": "COMPLETED",
        },
        {
            "task_id": "T_LOCAL",
            "date_folder": "20261120",
            "stratum": "S1",
            "project_goal_completed": True,
            "task_lifecycle_state": "COMPLETED",
            "acceptance_confirmed": False,
        },
        {
            "task_id": "T_REG",
            "date_folder": "20261120",
            "stratum": "S1",
            "acceptance_confirmed": True,
            "regression_escape": True,
        },
    ]
    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S1"}
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].unknown_count == 3
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].unknown_count == 2
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].numerator == 1
    assert metrics["REGRESSION_ESCAPE_RATE"].numerator == 1
    assert metrics["REGRESSION_ESCAPE_RATE"].denominator == 1
    assert metrics["REGRESSION_ESCAPE_RATE"].unknown_count == 0
    assert classify_task_stratum({"route": {"worker_route": "STANDARD"}}) is None


def test_receipt_scope_identity_and_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    task_dir = project / ".task-data" / "20261120" / "TASK"
    task_dir.mkdir(parents=True)
    monkeypatch.setattr(task_catalog, "canonical_project_root", lambda: project)
    record: dict[str, object] = {"task_id": "TASK", "path": str(task_dir)}
    (task_dir / "result.json").write_text(
        json.dumps(
            {"task_id": "OTHER", "route": {"worker_route": "FAST"}, "first_pass_accepted": True}
        )
    )
    assert classify_task_stratum(record) is None
    assert "first_pass_accepted" not in task_catalog._enrich_task_data(record, True)
    (task_dir / "result.json").write_bytes(b" " * (task_catalog.MAX_JSON_SIZE_BYTES + 1))
    assert "first_pass_accepted" not in task_catalog._enrich_task_data(record, True)
    (task_dir / "packet.md").write_text("TASK_ID: OTHER\nWORKER_ROUTE: FAST\n")
    assert classify_task_stratum(record) is None
    outside = tmp_path / "TASK"
    outside.mkdir()
    (outside / "packet.md").write_text("TASK_ID: TASK\nWORKER_ROUTE: FAST\n")
    assert classify_task_stratum({"task_id": "TASK", "path": str(outside)}) is None
    alias = project / ".task-data" / "20261120" / "ALIAS"
    alias.symlink_to(task_dir, target_is_directory=True)
    assert not task_catalog._is_safe_receipt_dir(str(alias), "ALIAS")


def test_continuation_does_not_reuse_single_run_cost_as_total() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "A",
            "date_folder": "20261120",
            "stratum": "S1",
            "tokens": 100,
            "model_tier": "high",
            "model_identity": "model-alpha",
            "route": {"worker_route": "FAST"},
            "adopted_outcome": True,
            "owner_intervention_count": 1,
            "is_continuation": False,
            "continues_from": "NONE",
            "first_pass_accepted": False,
        },
        {
            "task_id": "B",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "A",
            "same_original_task": True,
            "goal_72h_completed": True,
            "tokens": 100,
            "model_tier": "high",
            "model_identity": "model-alpha",
            "adopted_outcome": True,
        },
    ]
    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S1"}
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].denominator == 1
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].numerator == 0
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].numerator == 1
    assert metrics["MODEL_COST_PER_ACCEPTED_OUTCOME"].unknown_count == 1
    assert metrics["OWNER_INTERVENTION_COUNT"].unknown_count == 1


def test_first_pass_is_not_promoted_by_a_successful_continuation() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "ORIGINAL",
            "date_folder": "20261120",
            "stratum": "S1",
            "is_continuation": False,
            "continues_from": "NONE",
            "first_pass_accepted": False,
            "task_lifecycle_state": "BLOCKED",
        },
        {
            "task_id": "FOLLOWUP",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "ORIGINAL",
            "same_original_task": True,
            "is_continuation": True,
            # A terminal follow-up's own status cannot replace the original first pass.
            "first_pass_accepted": True,
            "goal_72h_completed": True,
            "task_lifecycle_state": "COMPLETED",
        },
    ]

    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S1"}

    assert report.total_tasks_evaluated == 1
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].status == "MEASURED"
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].numerator == 0
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].denominator == 1
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].numerator == 1
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].denominator == 1


def test_first_pass_requires_explicit_none_lineage() -> None:
    report = compute_workflow_metrics(
        Path("/dummy"),
        read_folder_receipts=False,
        tasks_data=[
            {
                "task_id": "NO_LINEAGE_RECEIPT",
                "date_folder": "20261120",
                "stratum": "S1",
                "first_pass_accepted": True,
            }
        ],
    )
    first_pass = next(
        m
        for m in report.metrics
        if m.stratum == "S1" and m.indicator == "FIRST_PASS_ACCEPTANCE_RATE"
    )

    assert first_pass.status == "UNKNOWN"
    assert first_pass.numerator == 0
    assert first_pass.denominator == 0
    assert first_pass.eligible_count == 1
    assert first_pass.unknown_count == 1


def test_missing_parent_and_unconfirmed_continuation_stay_unknown() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "ORPHAN_CONTINUATION",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "MISSING_PARENT",
            "same_original_task": True,
            "is_continuation": True,
            "first_pass_accepted": True,
            "goal_72h_completed": True,
        },
        {
            "task_id": "UNLINKED_CONTINUATION",
            "date_folder": "20261120",
            "stratum": "S1",
            "is_continuation": True,
            "first_pass_accepted": True,
            "goal_72h_completed": True,
        },
    ]

    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S1"}

    assert report.tasks_by_stratum["S1"] == 2
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].status == "UNKNOWN"
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].denominator == 0
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].eligible_count == 2
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].unknown_count == 2
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].status == "UNKNOWN"
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].unknown_count == 2


def test_duplicate_receipts_are_counted_once_and_conflicts_are_unknown() -> None:
    duplicate = {
        "task_id": "DUPLICATE",
        "date_folder": "20261120",
        "stratum": "S1",
        "continues_from": "NONE",
        "first_pass_accepted": True,
    }
    duplicated_report = compute_workflow_metrics(
        Path("/dummy"),
        read_folder_receipts=False,
        tasks_data=[dict(duplicate), dict(duplicate)],
    )
    first_pass = next(
        m
        for m in duplicated_report.metrics
        if m.stratum == "S1" and m.indicator == "FIRST_PASS_ACCEPTANCE_RATE"
    )

    assert duplicated_report.total_tasks_evaluated == 1
    assert duplicated_report.duplicate_receipts_ignored == 1
    assert first_pass.numerator == 1
    assert first_pass.denominator == 1

    conflicting_report = compute_workflow_metrics(
        Path("/dummy"),
        read_folder_receipts=False,
        tasks_data=[dict(duplicate), {**duplicate, "first_pass_accepted": False}],
    )
    assert conflicting_report.total_tasks_evaluated == 1
    assert conflicting_report.conflicting_task_ids == 1
    assert conflicting_report.unknown_stratum_tasks == 1
    assert conflicting_report.tasks_by_stratum["S1"] == 0


def test_unknown_dates_and_conflicting_strata_remain_visible() -> None:
    tasks: list[dict[str, object]] = [
        {"task_id": "START", "date_folder": "20261118", "stratum": "S1"},
        {"task_id": "END", "date_folder": "20261124", "stratum": "S2"},
        {"task_id": "OUTSIDE", "date_folder": "20261125", "stratum": "S1"},
        {"task_id": "NO_DATE", "stratum": "S3"},
        {"task_id": "BAD_DATE", "date_folder": "20261199", "stratum": "S3"},
        {
            "task_id": "CONFLICTING_STRATUM",
            "date_folder": "20261120",
            "stratum": "S2",
            "route": {"worker_route": "STANDARD", "implementation_depth": "ENHANCED"},
        },
    ]

    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)

    assert report.total_tasks_evaluated == 3
    assert report.unknown_window_date_tasks == 2
    assert report.unknown_stratum_tasks == 1
    assert report.tasks_by_stratum["S1"] == 1
    assert report.tasks_by_stratum["S2"] == 1
    assert report.tasks_by_stratum["S3"] == 0


def test_resource_cost_requires_explicit_three_component_evidence() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "RESOURCE_VECTOR",
            "date_folder": "20261120",
            "stratum": "S3",
            "resource_cost_measured": {
                "available_disk_bytes": 20_000,
                "orphan_worktree_count": 2,
                "temporary_residue_bytes": 4_000,
            },
            # Folder size alone is not a substitute for the resource vector.
            "task_folder_bytes_reported": 4_000,
        },
        {
            "task_id": "RESOURCE_PARTIAL",
            "date_folder": "20261120",
            "stratum": "S3",
            "resource_cost_measured": {"available_disk_bytes": 18_000},
        },
    ]

    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    resource = next(
        m for m in report.metrics if m.stratum == "S3" and m.indicator == "RESOURCE_COST"
    )

    assert resource.status == "PARTIAL"
    assert resource.eligible_count == 2
    assert resource.unknown_count == 1
    assert resource.value is None
    assert resource.components is not None
    assert resource.components["available_disk_bytes"]["observations"] == 2
    assert resource.components["orphan_worktree_count"]["observations"] == 1
    assert resource.components["temporary_residue_bytes"]["observations"] == 1

    complete_report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=False, tasks_data=[tasks[0]]
    )
    complete_resource = next(
        m for m in complete_report.metrics if m.stratum == "S3" and m.indicator == "RESOURCE_COST"
    )
    assert complete_resource.status == "MEASURED"
    assert complete_resource.unknown_count == 0
    assert complete_resource.components is not None
    assert complete_resource.components["orphan_worktree_count"]["minimum"] == 2


def test_auth_incident_and_model_tier_are_not_metric_evidence() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "BLOCKED_AUTH_ONLY",
            "date_folder": "20261120",
            "stratum": "S2",
            "task_lifecycle_state": "BLOCKED",
            "issue_type": "AUTH",
        },
        {
            "task_id": "COST_TIER_ONLY",
            "date_folder": "20261120",
            "stratum": "S2",
            "task_lifecycle_state": "COMPLETED",
            "tokens": 100,
            "model_tier": "high",
            "route": {"worker_route": "STANDARD", "implementation_depth": "NORMAL"},
            "adopted_outcome": True,
        },
        {
            "task_id": "COST_ROUTE_INCOMPLETE",
            "date_folder": "20261120",
            "stratum": "S2",
            "task_lifecycle_state": "COMPLETED",
            "tokens": 200,
            "model_identity": "model-alpha",
            "route": {"worker_route": "STANDARD"},
            "adopted_outcome": True,
        },
    ]
    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S2"}

    assert metrics["AVOIDABLE_BLOCK_RATE"].status == "UNKNOWN"
    assert metrics["AVOIDABLE_BLOCK_RATE"].denominator == 0
    assert metrics["AVOIDABLE_BLOCK_RATE"].unknown_count == 1
    assert metrics["MODEL_COST_PER_ACCEPTED_OUTCOME"].status == "UNKNOWN"
    assert metrics["MODEL_COST_PER_ACCEPTED_OUTCOME"].unknown_count == 3


def test_r5_aggregate_is_not_treated_as_three_task_rows_or_baseline() -> None:
    # R5 is one aggregate receipt, not three row-level task records. Its summary
    # values must not be expanded into fabricated task identities or outcomes.
    r5_aggregate: list[dict[str, object]] = [
        {
            "task_id": "NUMBER2_L4_R5_METRICS_MINIMUM_COHORT_20261125_R1",
            "date_folder": "20261125",
            "cohort_size": 3,
            "route": {
                "task_class": "READ_ONLY_COMPLETION_REVIEW",
                "worker_route": "NOT_APPLICABLE",
                "judge_mode": "NOT_APPLICABLE",
            },
            "metric_summary": {
                "first_pass_acceptance_rate": {"numerator": 2, "denominator": 3},
                "local_terminal_completion_rate": {"numerator": 3, "denominator": 3},
                "formal_adoption_rate": {"numerator": 0, "denominator": 3},
                "continuation_sample": {"numerator": 1, "denominator": 3},
            },
        }
    ]
    post_window_report = compute_workflow_metrics(
        Path("/dummy"),
        start_date="2026-11-25",
        end_date="2026-11-25",
        read_folder_receipts=False,
        tasks_data=r5_aggregate,
    )
    baseline_report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=False, tasks_data=r5_aggregate
    )

    assert post_window_report.total_tasks_evaluated == 1
    assert post_window_report.unknown_stratum_tasks == 1
    assert sum(post_window_report.tasks_by_stratum.values()) == 0
    assert baseline_report.total_tasks_evaluated == 0


def test_before_attempt_blocked_distinguishes_first_pass_failure_from_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    task_dir = project / ".task-data" / "20261120" / "TASK"
    task_dir.mkdir(parents=True)
    monkeypatch.setattr(task_catalog, "canonical_project_root", lambda: project)
    (task_dir / "packet.md").write_text(
        "TASK_ID: TASK\nCONTINUES_FROM: NONE\nWORKER_ROUTE: FAST\n",
        encoding="utf-8",
    )
    (task_dir / "result.before_1.json").write_text(
        json.dumps({"task_id": "TASK", "task_lifecycle_state": "BLOCKED"}),
        encoding="utf-8",
    )
    (task_dir / "result.json").write_text(
        json.dumps(
            {
                "task_id": "TASK",
                "task_lifecycle_state": "COMPLETED",
                "goal_72h_completed": True,
            }
        ),
        encoding="utf-8",
    )

    enriched = task_catalog._enrich_task_data(
        {"task_id": "TASK", "date_folder": "20261120", "path": str(task_dir)}, True
    )
    report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=True, tasks_data=[enriched]
    )
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S1"}

    assert enriched["first_pass_accepted"] is False
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].numerator == 0
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].denominator == 1
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].unknown_count == 0
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].numerator == 1
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].denominator == 1

    conflict_dir = project / ".task-data" / "20261120" / "CONFLICT_TASK"
    conflict_dir.mkdir(parents=True)
    (conflict_dir / "packet.md").write_text(
        "TASK_ID: CONFLICT_TASK\nCONTINUES_FROM: NONE\nWORKER_ROUTE: FAST\n",
        encoding="utf-8",
    )
    (conflict_dir / "result.before_1.json").write_text(
        json.dumps(
            {
                "task_id": "CONFLICT_TASK",
                "first_pass_accepted": True,
                "task_lifecycle_state": "BLOCKED",
            }
        ),
        encoding="utf-8",
    )
    (conflict_dir / "result.json").write_text(
        json.dumps({"task_id": "CONFLICT_TASK", "task_lifecycle_state": "COMPLETED"}),
        encoding="utf-8",
    )
    conflict_record = task_catalog._enrich_task_data(
        {
            "task_id": "CONFLICT_TASK",
            "date_folder": "20261120",
            "path": str(conflict_dir),
        },
        True,
    )
    conflict_report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=True, tasks_data=[conflict_record]
    )
    conflict_first_pass = next(
        m
        for m in conflict_report.metrics
        if m.stratum == "S1" and m.indicator == "FIRST_PASS_ACCEPTANCE_RATE"
    )
    assert "first_pass_accepted" not in conflict_record
    assert conflict_first_pass.status == "UNKNOWN"
    assert conflict_first_pass.unknown_count == 1

    missing_identity_dir = project / ".task-data" / "20261120" / "MISSING_IDENTITY"
    missing_identity_dir.mkdir(parents=True)
    (missing_identity_dir / "packet.md").write_text(
        "TASK_ID: MISSING_IDENTITY\nCONTINUES_FROM: NONE\nWORKER_ROUTE: FAST\n",
        encoding="utf-8",
    )
    (missing_identity_dir / "result.before_1.json").write_text(
        json.dumps({"task_lifecycle_state": "BLOCKED"}), encoding="utf-8"
    )
    (missing_identity_dir / "result.json").write_text(
        json.dumps(
            {
                "task_id": "MISSING_IDENTITY",
                "task_lifecycle_state": "COMPLETED",
                "first_pass_accepted": True,
            }
        ),
        encoding="utf-8",
    )
    missing_identity = task_catalog._enrich_task_data(
        {
            "task_id": "MISSING_IDENTITY",
            "date_folder": "20261120",
            "path": str(missing_identity_dir),
        },
        True,
    )
    assert "first_pass_accepted" not in missing_identity

    unreadable_dir = project / ".task-data" / "20261120" / "UNREADABLE"
    unreadable_dir.mkdir(parents=True)
    (unreadable_dir / "packet.md").write_text(
        "TASK_ID: UNREADABLE\nCONTINUES_FROM: NONE\nWORKER_ROUTE: FAST\n",
        encoding="utf-8",
    )
    (unreadable_dir / "result.before_1.json").write_text("{", encoding="utf-8")
    (unreadable_dir / "result.json").write_text(
        json.dumps(
            {
                "task_id": "UNREADABLE",
                "task_lifecycle_state": "COMPLETED",
                "first_pass_accepted": True,
            }
        ),
        encoding="utf-8",
    )
    unreadable = task_catalog._enrich_task_data(
        {"task_id": "UNREADABLE", "date_folder": "20261120", "path": str(unreadable_dir)},
        True,
    )
    assert "first_pass_accepted" not in unreadable


def test_legal_multilevel_continuation_chain_counts_one_original_outcome() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "ORIGINAL",
            "date_folder": "20261120",
            "stratum": "S2",
            "continues_from": "NONE",
            "is_continuation": False,
            "first_pass_accepted": False,
            "task_lifecycle_state": "BLOCKED",
        },
        {
            "task_id": "FOLLOWUP_1",
            "date_folder": "20261120",
            "stratum": "S2",
            "continues_from": "ORIGINAL",
            "same_original_task": True,
            "is_continuation": True,
            "first_pass_accepted": True,
            "goal_72h_completed": False,
            "adopted_outcome": False,
            "tokens": 120,
            "model_identity": "model-alpha",
            "route": {"worker_route": "STANDARD", "implementation_depth": "NORMAL"},
        },
        {
            "task_id": "FOLLOWUP_2",
            "date_folder": "20261120",
            "stratum": "S2",
            "continues_from": "FOLLOWUP_1",
            "same_original_task": True,
            "is_continuation": True,
            "first_pass_accepted": True,
            "goal_72h_completed": True,
            "acceptance_confirmed": True,
            "adopted_outcome": True,
            "tokens": 180,
            "model_identity": "model-alpha",
            "route": {"worker_route": "STANDARD", "implementation_depth": "NORMAL"},
        },
    ]

    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S2"}

    assert report.total_tasks_evaluated == 1
    assert report.tasks_by_stratum["S2"] == 1
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].numerator == 0
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].denominator == 1
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].numerator == 1
    assert metrics["FINAL_GOAL_COMPLETION_RATE"].denominator == 1
    assert metrics["MODEL_COST_PER_ACCEPTED_OUTCOME"].status == "UNKNOWN"
    assert metrics["MODEL_COST_PER_ACCEPTED_OUTCOME"].numerator is None
    assert metrics["MODEL_COST_PER_ACCEPTED_OUTCOME"].denominator == 1
    assert metrics["MODEL_COST_PER_ACCEPTED_OUTCOME"].unknown_count == 1

    conflicted_chain: list[dict[str, object]] = [
        {
            "task_id": "CONFLICTED_ROOT",
            "date_folder": "20261120",
            "stratum": "S2",
            "continues_from": "NONE",
            "is_continuation": False,
            "lineage_evidence_conflict": True,
            "goal_72h_completed": False,
        },
        {
            "task_id": "CONFLICTED_FOLLOWUP",
            "date_folder": "20261120",
            "stratum": "S2",
            "continues_from": "CONFLICTED_ROOT",
            "same_original_task": True,
            "is_continuation": True,
            "goal_72h_completed": True,
        },
    ]
    conflicted_report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=False, tasks_data=conflicted_chain
    )
    conflicted_final_goal = next(
        m
        for m in conflicted_report.metrics
        if m.stratum == "S2" and m.indicator == "FINAL_GOAL_COMPLETION_RATE"
    )
    assert conflicted_report.tasks_by_stratum["S2"] == 2
    assert conflicted_final_goal.denominator == 0
    assert conflicted_final_goal.unknown_count == 2


def test_receipt_retry_and_incident_signals_do_not_prove_first_pass_or_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    task_dir = project / ".task-data" / "20261120" / "TASK"
    task_dir.mkdir(parents=True)
    monkeypatch.setattr(task_catalog, "canonical_project_root", lambda: project)
    (task_dir / "packet.md").write_text(
        "TASK_ID: TASK\nCONTINUES_FROM: NONE\nWORKER_ROUTE: FAST\n",
        encoding="utf-8",
    )
    (task_dir / "result.json").write_text(
        json.dumps(
            {
                "task_id": "TASK",
                "task_lifecycle_state": "COMPLETED",
                "first_pass_accepted": True,
                "acceptance_confirmed": True,
                "process_signal": {
                    "regression_escape": True,
                    "issue": {"type": "AUTH"},
                },
            }
        ),
        encoding="utf-8",
    )
    record: dict[str, object] = {
        "task_id": "TASK",
        "date_folder": "20261120",
        "path": str(task_dir),
    }
    (task_dir / "result.before_1.json").write_text("{}", encoding="utf-8")

    enriched = task_catalog._enrich_task_data(record, True)
    report = compute_workflow_metrics(
        Path("/dummy"),
        read_folder_receipts=True,
        tasks_data=[enriched],
    )
    metrics = {m.indicator: m for m in report.metrics if m.stratum == "S1"}

    assert enriched.get("first_pass_accepted") is None
    assert metrics["FIRST_PASS_ACCEPTANCE_RATE"].status == "UNKNOWN"
    assert metrics["REGRESSION_ESCAPE_RATE"].numerator == 0
    assert metrics["REGRESSION_ESCAPE_RATE"].unknown_count == 1


def test_unit_test_reruns_do_not_create_task_continuations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    task_dir = project / ".task-data" / "20261120" / "TASK"
    task_dir.mkdir(parents=True)
    monkeypatch.setattr(task_catalog, "canonical_project_root", lambda: project)
    (task_dir / "packet.md").write_text(
        "TASK_ID: TASK\nCONTINUES_FROM: NONE\nWORKER_ROUTE: FAST\n",
        encoding="utf-8",
    )
    (task_dir / "result.json").write_text(
        json.dumps(
            {
                "task_id": "TASK",
                "task_lifecycle_state": "COMPLETED",
                "first_pass_accepted": True,
                "pytest_rerun_count": 4,
            }
        ),
        encoding="utf-8",
    )

    record: dict[str, object] = {
        "task_id": "TASK",
        "date_folder": "20261120",
        "path": str(task_dir),
    }
    enriched = task_catalog._enrich_task_data(record, True)
    report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=True, tasks_data=[enriched]
    )
    first_pass = next(
        m
        for m in report.metrics
        if m.stratum == "S1" and m.indicator == "FIRST_PASS_ACCEPTANCE_RATE"
    )

    assert enriched["is_continuation"] is False
    assert enriched["first_pass_accepted"] is True
    assert first_pass.numerator == 1
    assert first_pass.denominator == 1
    assert first_pass.unknown_count == 0


def test_contradictory_original_and_continuation_markers_stay_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    task_dir = project / ".task-data" / "20261120" / "TASK"
    task_dir.mkdir(parents=True)
    monkeypatch.setattr(task_catalog, "canonical_project_root", lambda: project)
    (task_dir / "packet.md").write_text(
        "TASK_ID: TASK\nCONTINUES_FROM: NONE\nWORKER_ROUTE: FAST\n",
        encoding="utf-8",
    )
    (task_dir / "result.json").write_text(
        json.dumps(
            {
                "task_id": "TASK",
                "task_lifecycle_state": "COMPLETED",
                "first_pass_accepted": True,
                "is_continuation": True,
            }
        ),
        encoding="utf-8",
    )

    enriched = task_catalog._enrich_task_data(
        {"task_id": "TASK", "date_folder": "20261120", "path": str(task_dir)}, True
    )
    report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=True, tasks_data=[enriched]
    )
    first_pass = next(
        m
        for m in report.metrics
        if m.stratum == "S1" and m.indicator == "FIRST_PASS_ACCEPTANCE_RATE"
    )

    assert enriched.get("lineage_evidence_conflict") is True
    assert first_pass.status == "UNKNOWN"
    assert first_pass.numerator == 0
    assert first_pass.denominator == 0
    assert first_pass.unknown_count == 1


def test_ambiguous_cycles_and_branches_are_not_collapsed() -> None:
    tasks: list[dict[str, object]] = [
        {
            "task_id": "A",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "B",
            "same_original_task": True,
            "first_pass_accepted": True,
        },
        {
            "task_id": "B",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "A",
            "same_original_task": True,
        },
    ]
    report = compute_workflow_metrics(Path("/dummy"), read_folder_receipts=False, tasks_data=tasks)
    assert report.tasks_by_stratum["S1"] == 2
    metric = next(
        m
        for m in report.metrics
        if m.stratum == "S1" and m.indicator == "FIRST_PASS_ACCEPTANCE_RATE"
    )
    assert metric.unknown_count == 2

    branched_tasks: list[dict[str, object]] = [
        {
            "task_id": "ROOT",
            "date_folder": "20261120",
            "stratum": "S1",
            "is_continuation": False,
            "first_pass_accepted": False,
        },
        {
            "task_id": "CHILD_A",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "ROOT",
            "same_original_task": True,
            "is_continuation": True,
            "first_pass_accepted": True,
        },
        {
            "task_id": "CHILD_B",
            "date_folder": "20261120",
            "stratum": "S1",
            "continues_from": "ROOT",
            "same_original_task": True,
            "is_continuation": True,
            "first_pass_accepted": True,
        },
    ]
    branch_report = compute_workflow_metrics(
        Path("/dummy"), read_folder_receipts=False, tasks_data=branched_tasks
    )
    branch_metric = next(
        m
        for m in branch_report.metrics
        if m.stratum == "S1" and m.indicator == "FIRST_PASS_ACCEPTANCE_RATE"
    )
    assert branch_report.tasks_by_stratum["S1"] == 3
    assert branch_metric.denominator == 0
    assert branch_metric.unknown_count == 3
