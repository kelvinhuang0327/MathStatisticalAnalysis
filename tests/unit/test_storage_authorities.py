"""Contract tests for named, read-only storage authorities."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from lottolab.infrastructure.persistence.storage_authorities import (
    StorageAuthorityPathError,
    StorageAuthorityRegistry,
    StorageAuthorityResolver,
    UnknownStorageAuthorityError,
)


def _registry_text(
    *,
    relative_path: str = "replay.sqlite3",
    digest: str | None = None,
    schema: str = "P638_CURRENT_REPLAY",
    env_override: str | None = None,
) -> str:
    override = "" if env_override is None else f'\nenv_override = "{env_override}"'
    expected = "" if digest is None else f'\nsha256 = "{digest}"'
    return f"""version = 1
durable_root = "LOTTOLAB_APPLICATION_SUPPORT"
required_capabilities = ["TEST_REPLAY"]

[[authorities]]
id = "test-replay"
capability = "TEST_REPLAY"
lottery_type = "POWER_LOTTO"
status = "CANONICAL_CURRENT"
location = "DURABLE"
relative_path = "{relative_path}"
schema = "{schema}"
immutable = true{expected}{override}
"""


def _write_registry(tmp_path: Path, text: str) -> Path:
    registry_dir = tmp_path / "config"
    registry_dir.mkdir()
    registry_path = registry_dir / "storage_authorities.toml"
    registry_path.write_text(text, encoding="utf-8")
    return registry_path


def _write_replay(path: Path, *, valid: bool) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        if valid:
            connection.executescript(
                """
                CREATE TABLE completion (
                    status TEXT NOT NULL,
                    failed_targets INTEGER NOT NULL
                );
                CREATE TABLE draws (id INTEGER);
                CREATE TABLE failures (id INTEGER);
                CREATE TABLE run_metadata (
                    lottery_type TEXT NOT NULL,
                    source_count INTEGER NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE scores (id INTEGER);
                CREATE TABLE strategy_ledger (id INTEGER);
                CREATE TABLE strategy_targets (id INTEGER);
                CREATE TABLE tickets (id INTEGER);
                INSERT INTO completion(status, failed_targets) VALUES ('COMPLETE', 0);
                INSERT INTO run_metadata(lottery_type, source_count, status)
                VALUES ('POWER_LOTTO', 1, 'COMPLETE');
                CREATE VIEW replay_output AS SELECT id FROM tickets;
                """
            )
        else:
            connection.execute("CREATE TABLE wrong_schema (id INTEGER)")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def test_registry_prefers_canonical_authority_for_duplicate_capability() -> None:
    registry = StorageAuthorityRegistry.from_file()

    assert registry.get("POWER_LOTTO_CURRENT_REPLAY").authority_id == (
        "power-lotto-current-replay-r2"
    )
    assert registry.get("POWER_LOTTO_ALL10").authority_id == "power-lotto-all10-ranking-r3"
    assert "POWER_LOTTO_ALL23" in registry.required_capabilities


def test_unknown_authority_is_rejected() -> None:
    registry = StorageAuthorityRegistry.from_file()

    with pytest.raises(UnknownStorageAuthorityError):
        registry.get("not-registered")


def test_unresolved_authority_does_not_resolve_without_explicit_override() -> None:
    registry = StorageAuthorityRegistry.from_file()
    resolver = StorageAuthorityResolver(registry, environ={})

    result = resolver.resolve("BIG_LOTTO_RAW_HISTORY")

    assert result.path is None
    assert result.reason == "authority status is UNRESOLVED"


def test_explicit_environment_override_is_not_a_directory_scan(tmp_path: Path) -> None:
    override = tmp_path / "operator-selected.sqlite3"
    registry = StorageAuthorityRegistry.from_file()
    resolver = StorageAuthorityResolver(
        registry,
        environ={"LOTTOLAB_P638_CURRENT_REPLAY_DB": str(override)},
    )

    result = resolver.resolve("POWER_LOTTO_CURRENT_REPLAY")

    assert result.path == override
    assert result.via_environment_override is True


def test_missing_authority_is_reported_without_creating_a_file(tmp_path: Path) -> None:
    registry_path = _write_registry(tmp_path, _registry_text(digest="0" * 64))
    registry = StorageAuthorityRegistry.from_file(registry_path)
    resolver = StorageAuthorityResolver(registry, home=tmp_path)

    result = resolver.verify("TEST_REPLAY", deep=False)

    assert result.passed is False
    assert result.exists is False
    assert not (tmp_path / "Library" / "Application Support" / "LottoLab").exists()


def test_valid_replay_is_verified_read_only_and_bytes_are_unchanged(tmp_path: Path) -> None:
    database = tmp_path / "Library" / "Application Support" / "LottoLab" / "replay.sqlite3"
    digest = _write_replay(database, valid=True)
    registry_path = _write_registry(tmp_path, _registry_text(digest=digest))
    registry = StorageAuthorityRegistry.from_file(registry_path)
    resolver = StorageAuthorityResolver(registry, home=tmp_path)

    result = resolver.verify("TEST_REPLAY")

    assert result.passed is True
    assert result.schema_valid is True
    assert result.query_only is True
    assert result.integrity_ok is True
    assert result.actual_sha256 == digest
    assert hashlib.sha256(database.read_bytes()).hexdigest() == digest


def test_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "Library" / "Application Support" / "LottoLab" / "replay.sqlite3"
    _write_replay(database, valid=True)
    registry_path = _write_registry(tmp_path, _registry_text(digest="0" * 64))
    resolver = StorageAuthorityResolver(
        StorageAuthorityRegistry.from_file(registry_path), home=tmp_path
    )

    result = resolver.verify("TEST_REPLAY", deep=False)

    assert result.passed is False
    assert result.sha_match is False
    assert result.schema_valid is True


def test_schema_mismatch_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "Library" / "Application Support" / "LottoLab" / "replay.sqlite3"
    digest = _write_replay(database, valid=False)
    registry_path = _write_registry(tmp_path, _registry_text(digest=digest))
    resolver = StorageAuthorityResolver(
        StorageAuthorityRegistry.from_file(registry_path), home=tmp_path
    )

    result = resolver.verify("TEST_REPLAY", deep=False)

    assert result.passed is False
    assert result.schema_valid is False
    assert result.error is not None
    assert "schema verification failed" in result.error


def test_registry_rejects_root_traversal(tmp_path: Path) -> None:
    registry_path = _write_registry(tmp_path, _registry_text(relative_path="../escape.sqlite3"))

    with pytest.raises(StorageAuthorityPathError):
        StorageAuthorityRegistry.from_file(registry_path)


def test_unresolved_historical_authority_can_only_use_explicit_override(tmp_path: Path) -> None:
    selected = tmp_path / "selected.sqlite3"
    registry = StorageAuthorityRegistry.from_file()
    resolver = StorageAuthorityResolver(registry, environ={})

    unresolved = resolver.resolve("POWER_LOTTO_HISTORICAL_RESULTS_V2")
    explicit = StorageAuthorityResolver(
        registry,
        environ={"LOTTOLAB_HISTORICAL_RESULTS_DB": str(selected)},
    ).resolve(
        "POWER_LOTTO_HISTORICAL_RESULTS_V2",
        allow_unresolved_override=True,
    )

    assert unresolved.path is None
    assert explicit.path == selected


def test_fixed13_prospective_storage_authority_registration() -> None:
    registry = StorageAuthorityRegistry.from_file()

    matches = [
        auth
        for auth in registry.authorities
        if auth.capability == "BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION"
    ]
    assert len(matches) == 1
    authority = matches[0]

    assert authority.authority_id == "biglotto-fixed13-prospective-observation"
    assert authority.capability == "BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION"
    assert authority.lottery_type == "BIG_LOTTO"
    assert authority.status == "CANONICAL_CURRENT"
    assert authority.location == "DURABLE"
    assert authority.relative_path == "prospective/biglotto_fixed13/"
    assert authority.schema == "LOTTOLAB_PROSPECTIVE_OBSERVATION_STORE_V1"
    assert authority.immutable is False
    assert authority.sha256 is None
    assert "BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION" in registry.required_capabilities
    assert registry.required_capabilities.count("BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION") == 1


def test_fixed13_prospective_storage_authority_resolution(tmp_path: Path) -> None:
    registry = StorageAuthorityRegistry.from_file()
    resolver = StorageAuthorityResolver(registry, home=tmp_path)

    resolution = resolver.resolve("BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION")

    assert resolution.resolved is True
    assert resolution.path is not None
    expected_path = (
        tmp_path
        / "Library"
        / "Application Support"
        / "LottoLab"
        / "prospective"
        / "biglotto_fixed13"
    )
    assert resolution.path == expected_path
    assert resolution.via_environment_override is False
    assert resolution.reason is None
    assert not expected_path.exists()


def test_fixed13_prospective_storage_authority_verification_read_only(tmp_path: Path) -> None:
    registry = StorageAuthorityRegistry.from_file()
    resolver = StorageAuthorityResolver(registry, home=tmp_path)

    # Missing directory -> reported as exists=False without creating the directory
    unmaterialized = resolver.verify("BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION", deep=False)
    assert unmaterialized.exists is False
    assert unmaterialized.passed is False
    target_dir = (
        tmp_path
        / "Library"
        / "Application Support"
        / "LottoLab"
        / "prospective"
        / "biglotto_fixed13"
    )

    assert not target_dir.exists()

    # Materialized valid directory -> verify passes
    target_dir.mkdir(parents=True)
    materialized = resolver.verify("BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION", deep=False)
    assert materialized.exists is True
    assert materialized.schema_valid is True
    assert materialized.passed is True
    assert materialized.error is None

    # Materialized as a file instead of directory -> schema verification fails
    target_dir.rmdir()
    target_dir.write_text("not a directory", encoding="utf-8")
    as_file = resolver.verify("BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION", deep=False)
    assert as_file.exists is True
    assert as_file.schema_valid is False
    assert as_file.passed is False


def test_all_required_capabilities_intact() -> None:
    registry = StorageAuthorityRegistry.from_file()
    expected_capabilities = (
        "DRAW_DATA",
        "BIG_LOTTO_RAW_HISTORY",
        "BIG_LOTTO_PACKAGED_RECORDS",
        "BIGLOTTO_FIXED13_PROSPECTIVE_OBSERVATION",
        "POWER_LOTTO_HISTORICAL_RESULTS_V2",
        "POWER_LOTTO_CURRENT_REPLAY",
        "POWER_LOTTO_CURRENT_RANKING",
        "POWER_LOTTO_ALL10",
        "POWER_LOTTO_ALL23",
        "DAILY_539_HISTORICAL",
        "REPLAY_SCORING",
    )
    assert registry.required_capabilities == expected_capabilities
    for cap in expected_capabilities:
        assert registry.get(cap) is not None
