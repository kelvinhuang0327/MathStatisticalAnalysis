"""Acceptance tests for the DB-free P600B legacy metadata fixtures."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "legacy" / "p600b"
EXPORTER = ROOT / "tools" / "export_legacy_p600b_fixtures.py"
TARGET_IDS = [
    "biglotto_social_wisdom_anti_popularity",
    "biglotto_zone_split_3bet_bet1",
]
EXPECTED_FILE_HASHES = {
    "strategy_catalog.json": "f78891865cc03d800ef1da1840150427d8e61e08aa06e1b8a7b16da9600ee9af",
    "lifecycle_metadata.json": "c22178bd41d005dff8d1bcd0b8b0c7c6d71414ac2dc1d5aac17d53bcd4567e33",
}
EXPECTED_AGGREGATE_HASH = "8ba8d43fe046ff2eb1b46fbcb71bc5d14a18208aada3473379729f17c47e76ec"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _aggregate_sha256(payloads: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(payloads):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(payloads[name])
    return digest.hexdigest()


def test_exporter_is_static_and_has_no_database_or_runtime_import() -> None:
    source = EXPORTER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not imported.intersection({"sqlite3", "importlib", "lottery_api"})
    assert not any(module.startswith("lottolab") for module in imported)
    assert "--snapshot" not in source
    assert "sqlite3" not in source


def test_manifest_binds_exporter_and_both_reproducible_runs() -> None:
    manifest = cast(dict[str, object], _json(FIXTURE_DIR / "manifest.json"))
    extraction = cast(dict[str, object], manifest["extraction"])
    exporter = cast(dict[str, object], manifest["exporter"])
    runs = cast(list[dict[str, object]], manifest["verification_runs"])
    canonical = cast(dict[str, object], manifest["canonical_output"])
    canonical_files = cast(dict[str, dict[str, object]], canonical["files"])
    payloads = {name: (FIXTURE_DIR / name).read_bytes() for name in EXPECTED_FILE_HASHES}

    assert extraction["database_access"] == "NONE"
    assert extraction["legacy_module_imported"] is False
    assert extraction["legacy_runtime_executed"] is False
    assert extraction["prediction_adapters_executed"] is False
    assert exporter["sha256"] == _sha256(EXPORTER)
    assert len(runs) == 2
    assert {run["aggregate_sha256"] for run in runs} == {canonical["aggregate_sha256"]}
    assert canonical["aggregate_sha256"] == EXPECTED_AGGREGATE_HASH
    assert _aggregate_sha256(payloads) == EXPECTED_AGGREGATE_HASH
    for name, expected_hash in EXPECTED_FILE_HASHES.items():
        claim = canonical_files[name]
        assert claim["sha256"] == expected_hash
        assert claim["bytes"] == len(payloads[name])
        assert hashlib.sha256(payloads[name]).hexdigest() == expected_hash
        for run in runs:
            run_files = cast(dict[str, dict[str, object]], run["files"])
            assert run_files[name] == claim


def test_fixture_payloads_have_expected_order_and_non_executable_lifecycle() -> None:
    catalog = cast(list[dict[str, object]], _json(FIXTURE_DIR / "strategy_catalog.json"))
    lifecycle = cast(dict[str, object], _json(FIXTURE_DIR / "lifecycle_metadata.json"))
    lifecycle_records = cast(list[dict[str, object]], lifecycle["strategies"])

    assert [record["strategy_id"] for record in catalog] == TARGET_IDS
    assert [record["strategy_id"] for record in lifecycle_records] == TARGET_IDS
    assert all(record["lifecycle_status"] == "OBSERVATION" for record in catalog)
    assert all(record["executable"] is False for record in catalog)
    assert all(record["min_history"] == 1 for record in lifecycle_records)
    assert lifecycle["executable_strategy_ids"] == []
    assert lifecycle["non_executable_strategy_ids"] == TARGET_IDS
