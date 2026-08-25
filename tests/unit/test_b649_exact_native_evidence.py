"""Contract tests for the canonical exact-native K2/K3 evidence reader."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from lottolab.infrastructure.persistence.b649_exact_native_evidence import (
    EXACT_NATIVE_K2_K3_CAPABILITY,
    ExactNativeEvidenceReader,
    ExactNativeEvidenceUnavailableError,
)
from lottolab.infrastructure.persistence.storage_authorities import (
    StorageAuthorityRegistry,
)

_WINDOWS = {"RECENT_50": 50, "RECENT_300": 300, "RECENT_750": 750}
_RELATIVE_PATH = "authorities/big_lotto/exact_native_k2_k3/target_evidence.jsonl"


def _write_json(path: Path, value: Mapping[str, object]) -> str:
    payload = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        + b"\n"
    )
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _write_fixture(tmp_path: Path) -> StorageAuthorityRegistry:
    bundle = tmp_path / "Library" / "Application Support" / "LottoLab" / _RELATIVE_PATH
    bundle.parent.mkdir(parents=True)
    replay = b'{"fixture":true}\n'
    replay_path = bundle
    replay_path.write_bytes(replay)
    replay_sha256 = hashlib.sha256(replay).hexdigest()
    draw_sha256 = "d" * 64
    manifest = {
        "schema_version": "B649_EXACT_NATIVE_REPLAY_SEALED_MANIFEST_V1",
        "run_id": "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1",
        "source": {"branch": "fixture", "head": "a" * 40, "tree": "b" * 40},
        "draw_authority": {
            "draw_count": 2163,
            "sha256_before": draw_sha256,
            "sha256_after": draw_sha256,
        },
        "universe": {
            "attempted_cell_count": 28500,
            "k2_strategy_ids": [f"k2_{index}" for index in range(19)],
            "k3_strategy_ids": [f"k3_{index}" for index in range(19)],
        },
        "target_windows": {
            window: {
                "observations_required": size,
                "draw_numbers": [f"{window}_{index}" for index in range(size)],
                "first_target": f"{window}_0",
                "last_target": f"{window}_{size - 1}",
            }
            for window, size in _WINDOWS.items()
        },
        "execution_contract": {
            "primary_metric": "OFFICIAL_ANY_PRIZE at distinct target-draw level",
            "target_outcome_excluded": True,
        },
        "evidence": {
            "file": "target_evidence.jsonl",
            "byte_size": len(replay),
            "record_count": 28500,
            "sha256": replay_sha256,
        },
    }
    manifest_sha256 = _write_json(bundle.parent / "sealed_manifest.json", manifest)
    leaderboards: dict[str, object] = {}
    for family, ticket_count in (("K2", 2), ("K3", 3)):
        family_rows: dict[str, object] = {}
        strategy_ids = [f"{family.lower()}_{index}" for index in range(19)]
        for window, size in _WINDOWS.items():
            rows = [
                {
                    "rank": index,
                    "strategy_id": strategy_ids[index - 1],
                    "native_ticket_count": ticket_count,
                    "observations": size,
                    "observations_required": size,
                }
                for index in range(1, 6)
            ]
            family_rows[window] = {
                "status": "COMPLETE",
                "eligible_count": len(rows),
                "eligible_rankings": rows,
                "top5": rows,
            }
        leaderboards[family] = family_rows
    ranking = cast(
        dict[str, object],
        {
            "schema_version": "B649_EXACT_NATIVE_RANKING_PROJECTION_V1",
            "run_id": "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1",
            "sealed_evidence_sha256": replay_sha256,
            "sealed_manifest_sha256": manifest_sha256,
            "ranking_contract": {"primary_metric": "OFFICIAL_ANY_PRIZE_RATE"},
            "coverage": {"K2": [], "K3": []},
            "cross_window": {"K2": {}, "K3": {}},
            "leaderboards": leaderboards,
        },
    )
    ranking_sha256 = _write_json(bundle.parent / "ranking.json", ranking)
    provenance = {
        "schema_version": "B649_EXACT_NATIVE_EVIDENCE_PROMOTION_PROVENANCE_V1",
        "source_task": "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1",
        "source_branch": "fixture",
        "source_head": "a" * 40,
        "source_tree": "b" * 40,
        "draw_authority_sha256": draw_sha256,
        "replay_sha256": replay_sha256,
        "manifest_sha256": manifest_sha256,
        "ranking_sha256": ranking_sha256,
        "k2": 19,
        "k3": 19,
        "windows": list(_WINDOWS),
        "metric": "OFFICIAL_ANY_PRIZE",
        "upstream_judge": "VERIFIED",
        "two_run_byte_identity": "VERIFIED",
        "capability": EXACT_NATIVE_K2_K3_CAPABILITY,
        "canonical_relative_path": _RELATIVE_PATH,
    }
    provenance_sha256 = _write_json(bundle.parent / "promotion_provenance.json", provenance)

    config = tmp_path / "config"
    config.mkdir()
    (config / "storage_authorities.toml").write_text(
        f'''version = 1
durable_root = "LOTTOLAB_APPLICATION_SUPPORT"
required_capabilities = ["{EXACT_NATIVE_K2_K3_CAPABILITY}"]

[[authorities]]
id = "fixture-exact-native"
capability = "{EXACT_NATIVE_K2_K3_CAPABILITY}"
lottery_type = "BIG_LOTTO"
status = "CANONICAL_CURRENT"
location = "DURABLE"
relative_path = "{_RELATIVE_PATH}"
schema = "B649_EXACT_NATIVE_K2_K3_REPLAY_V1"
sha256 = "{replay_sha256}"
manifest_sha256 = "{manifest_sha256}"
ranking_sha256 = "{ranking_sha256}"
provenance_sha256 = "{provenance_sha256}"
immutable = true
''',
        encoding="utf-8",
    )
    return StorageAuthorityRegistry.from_file(
        config / "storage_authorities.toml", repository_root=tmp_path
    )


def test_reader_resolves_full_k2_k3_rankings_without_a_scratch_source(tmp_path: Path) -> None:
    registry = _write_fixture(tmp_path)
    reader = ExactNativeEvidenceReader(registry.resolver(home=tmp_path))

    for family, expected_ticket_count in (("K2", 2), ("K3", 3)):
        for window, expected_observations in _WINDOWS.items():
            projection = reader.ranking(family, window)
            raw_rows = cast(list[object], projection["eligible_rankings"])
            assert isinstance(raw_rows, list)
            rows = [cast(dict[str, object], row) for row in raw_rows]
            assert len(rows) == 5
            assert reader.top5(family, window) == tuple(rows)
            assert all(row["native_ticket_count"] == expected_ticket_count for row in rows)
            assert all(row["observations"] == expected_observations for row in rows)

    assert not (tmp_path / ".task-data").exists()


def test_registry_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    registry = _write_fixture(tmp_path)
    registry_path = registry.registry_path
    broken = registry_path.read_text(encoding="utf-8").replace(
        registry.for_capability(EXACT_NATIVE_K2_K3_CAPABILITY).sha256 or "",
        "0" * 64,
    )
    registry_path.write_text(broken, encoding="utf-8")

    result = (
        StorageAuthorityRegistry.from_file(registry_path, repository_root=tmp_path)
        .resolver(home=tmp_path)
        .verify(EXACT_NATIVE_K2_K3_CAPABILITY, deep=False)
    )

    assert result.passed is False
    assert result.sha_match is False


def test_unavailable_exact_native_authority_fails_closed(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "storage_authorities.toml").write_text(
        f'''version = 1
durable_root = "LOTTOLAB_APPLICATION_SUPPORT"
required_capabilities = ["{EXACT_NATIVE_K2_K3_CAPABILITY}"]

[[authorities]]
id = "fixture-exact-native"
capability = "{EXACT_NATIVE_K2_K3_CAPABILITY}"
lottery_type = "BIG_LOTTO"
status = "CANONICAL_CURRENT"
location = "DURABLE"
relative_path = "{_RELATIVE_PATH}"
schema = "B649_EXACT_NATIVE_K2_K3_REPLAY_V1"
sha256 = "{"0" * 64}"
immutable = true
''',
        encoding="utf-8",
    )
    registry = StorageAuthorityRegistry.from_file(
        config / "storage_authorities.toml", repository_root=tmp_path
    )

    with pytest.raises(ExactNativeEvidenceUnavailableError):
        ExactNativeEvidenceReader(registry.resolver(home=tmp_path)).read()
