"""Semantic parity between DB-free legacy fixtures and the LottoLab catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from lottolab.application.dto import StrategyView
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.strategies.adapters import BetAdapter
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry, NotExecutableError

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "legacy" / "p600b"

# P602B is an approved, intentional divergence from the frozen P600B legacy
# snapshot below: these two strategies are promoted to ONLINE/executable via
# the production CLI execution vertical. Every other P600B-scoped strategy
# must still match the legacy snapshot byte-for-byte (see characterization/README.md).
PROMOTED_STRATEGY_IDS = frozenset(
    {
        "biglotto_zone_split_3bet_bet1",
        "biglotto_social_wisdom_anti_popularity",
    }
)
APPROVED_P602B_ADAPTER_MODULE = "lottolab.strategies.adapters.biglotto_selected"
P602B_PROVENANCE_MARKER = "migration_task:P602B"


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_descriptors() -> list[StrategyDescriptor]:
    manifest = cast(dict[str, object], _json(FIXTURE_DIR / "manifest.json"))
    scope = cast(dict[str, object], manifest["scope"])
    target_ids = cast(list[str], scope["strategy_ids"])
    by_id = {descriptor.strategy_id: descriptor for descriptor in production_catalog()}
    return [by_id[strategy_id] for strategy_id in target_ids]


def _legacy_expected_catalog() -> list[dict[str, object]]:
    """The frozen P600B snapshot, with the two approved P602B promotions applied.

    Every field but ``lifecycle_status``/``executable`` still comes straight
    from the byte-exact legacy fixture — only the two named IDs diverge, and
    only in the two fields P602B is authorized to change.
    """

    legacy_catalog = cast(list[dict[str, object]], _json(FIXTURE_DIR / "strategy_catalog.json"))
    lifecycle = cast(dict[str, object], _json(FIXTURE_DIR / "lifecycle_metadata.json"))
    lifecycle_records = cast(list[dict[str, object]], lifecycle["strategies"])
    lifecycle_by_id = {str(record["strategy_id"]): record for record in lifecycle_records}
    records = [
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
    for record in records:
        if record["strategy_id"] in PROMOTED_STRATEGY_IDS:
            record["lifecycle_status"] = "ONLINE"
            record["executable"] = True
    return records


def test_strategy_catalog_matches_canonicalized_fixture() -> None:
    actual = [
        StrategyView.from_descriptor(descriptor).model_dump(mode="json")
        for descriptor in _target_descriptors()
    ]
    assert actual == _legacy_expected_catalog()


def test_lifecycle_fixture_matches_descriptor_source_of_truth() -> None:
    lifecycle = cast(dict[str, object], _json(FIXTURE_DIR / "lifecycle_metadata.json"))
    legacy_records = cast(list[dict[str, object]], lifecycle["strategies"])
    expected = [
        {**record, "lifecycle_status": "ONLINE", "is_executable": True}
        if record["strategy_id"] in PROMOTED_STRATEGY_IDS
        else record
        for record in legacy_records
    ]
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


def test_promoted_strategies_load_the_approved_p602b_adapter() -> None:
    """The two P602B-approved IDs are the only authorized executable divergence."""

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    promoted = [d for d in _target_descriptors() if d.strategy_id in PROMOTED_STRATEGY_IDS]
    assert {d.strategy_id for d in promoted} == PROMOTED_STRATEGY_IDS

    for descriptor in promoted:
        assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
        assert descriptor.executable is True
        assert descriptor.adapter_path is not None
        assert descriptor.adapter_path.split(":")[0] == APPROVED_P602B_ADAPTER_MODULE
        assert P602B_PROVENANCE_MARKER in descriptor.provenance

        adapter_class = registry.load_adapter(descriptor.strategy_id)
        assert isinstance(adapter_class, type)
        assert issubclass(adapter_class, BetAdapter)


def test_non_promoted_p600b_strategies_remain_observation_and_cannot_load_adapters() -> None:
    """Every P600B strategy P602B did not name stays frozen at legacy parity."""

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    non_promoted = [
        d for d in _target_descriptors() if d.strategy_id not in PROMOTED_STRATEGY_IDS
    ]
    non_promoted_ids = {descriptor.strategy_id for descriptor in non_promoted}
    assert non_promoted_ids.isdisjoint(registry.executable_ids())
    for descriptor in non_promoted:
        assert descriptor.lifecycle_status is LifecycleStatus.OBSERVATION
        assert descriptor.adapter_path is None
        with pytest.raises(NotExecutableError, match="only executable"):
            registry.load_adapter(descriptor.strategy_id)
