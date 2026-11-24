"""Unit tests for task-catalog derivation, stages, tombstones, and CLI."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lottolab.infrastructure import task_catalog
from lottolab.infrastructure.task_catalog import (
    build_catalog,
    determine_project,
    find_in_catalog,
    find_task_folders,
)
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
        roots=[],
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
        roots=[],
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
    skipped_paths = {s["path"]: s["reason"] for s in meta["skipped"]}
    assert str(large_file.resolve()) in skipped_paths
    assert skipped_paths[str(large_file.resolve())] == "TOO_LARGE"


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
