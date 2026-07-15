"""Semantic parity between DB-free legacy fixtures and the LottoLab catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.dto import StrategyView
from lottolab.domain.strategies import StrategyDescriptor
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry, NotExecutableError

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "legacy" / "p600b"


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_descriptors() -> list[StrategyDescriptor]:
    manifest = cast(dict[str, object], _json(FIXTURE_DIR / "manifest.json"))
    scope = cast(dict[str, object], manifest["scope"])
    target_ids = cast(list[str], scope["strategy_ids"])
    by_id = {descriptor.strategy_id: descriptor for descriptor in production_catalog()}
    return [by_id[strategy_id] for strategy_id in target_ids]


def test_strategy_catalog_matches_canonicalized_fixture() -> None:
    legacy_catalog = cast(list[dict[str, object]], _json(FIXTURE_DIR / "strategy_catalog.json"))
    lifecycle = cast(dict[str, object], _json(FIXTURE_DIR / "lifecycle_metadata.json"))
    lifecycle_records = cast(list[dict[str, object]], lifecycle["strategies"])
    lifecycle_by_id = {str(record["strategy_id"]): record for record in lifecycle_records}
    expected = [
        {
            "strategy_id": record["strategy_id"],
            "display_name": record["strategy_name"],
            "version": record["version"],
            "supported_lottery_types": record["lottery_types"],
            "minimum_history": lifecycle_by_id[str(record["strategy_id"])]["min_history"],
            "lifecycle_status": record["lifecycle_status"],
            "executable": record["executable"],
        }
        for record in legacy_catalog
    ]
    actual = [
        StrategyView.from_descriptor(descriptor).model_dump(mode="json")
        for descriptor in _target_descriptors()
    ]
    assert actual == expected


def test_lifecycle_fixture_matches_descriptor_source_of_truth() -> None:
    lifecycle = cast(dict[str, object], _json(FIXTURE_DIR / "lifecycle_metadata.json"))
    expected = cast(list[dict[str, object]], lifecycle["strategies"])
    actual = [
        {
            "strategy_id": descriptor.strategy_id,
            "strategy_name": descriptor.strategy_name,
            "strategy_version": descriptor.version,
            "supported_lottery_types": [str(item) for item in descriptor.lottery_types],
            "min_history": descriptor.min_history,
            "lifecycle_status": str(descriptor.lifecycle_status),
            "is_executable": descriptor.executable,
        }
        for descriptor in _target_descriptors()
    ]
    assert actual == expected


def test_observation_strategies_cannot_load_generation_adapters() -> None:
    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    target_descriptors = _target_descriptors()
    target_ids = {descriptor.strategy_id for descriptor in target_descriptors}
    assert target_ids.isdisjoint(registry.executable_ids())
    for descriptor in target_descriptors:
        assert descriptor.adapter_path is None
        with pytest.raises(NotExecutableError, match="only executable"):
            registry.load_adapter(descriptor.strategy_id)
