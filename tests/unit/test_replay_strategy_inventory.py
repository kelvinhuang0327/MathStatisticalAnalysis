from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

import pytest

from lottolab.application.historical_replay_adapters import (
    PowerLottoReplayAdapter,
    binding_from_implementation,
)
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
    ReplayStrategyIdentityMapping,
    ReplayStrategyInventoryItem,
)


def test_inventory_conserves_sources_and_executable_identities() -> None:
    inventory = load_replay_strategy_inventory()
    source_counts = {source.source_kind: source for source in inventory.source_counts}

    assert inventory.total_discovered_strategies == 658
    assert inventory.total_unique_strategies == 442
    assert len(inventory.executable_items) == 209
    assert inventory.unresolved_source_count == 9
    assert source_counts["PRODUCTION_CATALOG"].source_identity_count == 137
    assert source_counts["B649_RESEARCH_CATALOG"].source_identity_count == 221
    assert source_counts["B649_REPLAY_BATCH_REGISTRY"].source_identity_count == 11
    assert source_counts["T539_REPLAY_ADAPTER"].source_identity_count == 62
    assert source_counts["P638_REPLAY_ADAPTER"].source_identity_count == 23
    assert source_counts["STRATEGY_ADAPTER_CODE"].source_identity_count == 98
    assert source_counts["STRATEGY_ADAPTER_CODE"].source_row_count == 99

    lottery_counts = Counter(item.lottery_type for item in inventory.items)
    executable_by_lottery = Counter(item.lottery_type for item in inventory.executable_items)
    assert lottery_counts == {
        LotteryType.BIG_LOTTO: 356,
        LotteryType.DAILY_539: 62,
        LotteryType.POWER_LOTTO: 24,
    }
    assert executable_by_lottery == {
        LotteryType.BIG_LOTTO: 124,
        LotteryType.DAILY_539: 62,
        LotteryType.POWER_LOTTO: 23,
    }

    research_sources = [
        source
        for item in inventory.items
        for source in item.alias_or_identity_mapping
        if source.source_kind == "B649_RESEARCH_CATALOG"
    ]
    assert len(research_sources) == 221
    assert (
        len({(source.strategy_id, source.strategy_version) for source in research_sources}) == 221
    )
    assert all(
        source.source_locator.startswith("src/lottolab/strategies/data/")
        for source in research_sources
    )

    for item in inventory.executable_items:
        assert item.adapter_mapping is not None
        assert item.adapter_mapping.strategy_id == item.strategy_id
        assert item.adapter_mapping.strategy_version == item.strategy_version


def test_inventory_keeps_status_dimensions_and_unavailable_cases_separate() -> None:
    inventory = load_replay_strategy_inventory()
    by_data_status = Counter(item.replay_data_status for item in inventory.items)
    assert by_data_status == {
        ReplayDataStatus.REBUILDABLE: 209,
        ReplayDataStatus.ARTIFACT_ONLY: 98,
        ReplayDataStatus.REJECTED: 74,
        ReplayDataStatus.NO_HISTORY: 59,
        ReplayDataStatus.CODE_ONLY: 2,
    }

    rejected = [
        item for item in inventory.items if item.replay_data_status is ReplayDataStatus.REJECTED
    ]
    assert len(rejected) == 74
    assert all(item.lifecycle_status is ReplayLifecycleStatus.REJECTED for item in rejected)
    assert all(
        item.execution_capability is ReplayExecutionCapability.UNAVAILABLE for item in rejected
    )
    assert all("CLOSED_UNEXECUTABLE:" in item.reconstruction_reason for item in rejected)

    artifact_only = [
        item
        for item in inventory.items
        if item.replay_data_status is ReplayDataStatus.ARTIFACT_ONLY
    ]
    assert len(artifact_only) == 98
    assert all(item.historical_data_count == 0 for item in artifact_only)
    assert all(
        item.execution_capability is not ReplayExecutionCapability.EXECUTABLE
        for item in artifact_only
    )
    assert all(item.historical_execution_count > 0 for item in artifact_only)

    code_only_lifecycle = [
        item for item in inventory.items if item.lifecycle_status is ReplayLifecycleStatus.CODE_ONLY
    ]
    assert {(i.strategy_id, i.strategy_version) for i in code_only_lifecycle} == {
        ("research_biglotto__quick_ml_corrected_successor_v1", "v1"),
        ("legacy_biglotto__evolution_engine__3df019c31ce4", "v0.2"),
    }
    assert all(i.replay_data_status is ReplayDataStatus.CODE_ONLY for i in code_only_lifecycle)
    assert all(
        i.execution_capability is ReplayExecutionCapability.UNAVAILABLE for i in code_only_lifecycle
    )

    online = [
        item for item in inventory.items if item.lifecycle_status is ReplayLifecycleStatus.ONLINE
    ]
    assert len(online) == 137
    assert all(item.historical_data_count == 0 for item in online)
    assert all(item.replay_data_status is not ReplayDataStatus.HAS_HISTORY for item in online)

    unresolved_batch_items = [
        item for item in inventory.items if item.source_kind == "B649_REPLAY_BATCH_REGISTRY"
    ]
    exact_symbol_mappings = [
        source
        for item in inventory.items
        for source in item.alias_or_identity_mapping
        if source.mapping_kind == "EXACT_SOURCE_SYMBOL_MATCH"
    ]
    assert len(unresolved_batch_items) == 9
    assert all(item.strategy_version is None for item in unresolved_batch_items)
    assert len(exact_symbol_mappings) == 2

    duplicate_aliases = [
        source
        for item in inventory.items
        for source in item.alias_or_identity_mapping
        if source.mapping_kind.startswith("DUPLICATE_ALIAS_TARGET:")
    ]
    assert len(duplicate_aliases) == 12
    assert all(
        source.mapping_kind.removeprefix("DUPLICATE_ALIAS_TARGET:") for source in duplicate_aliases
    )

    same_id_versions: dict[tuple[LotteryType, str], set[str | None]] = defaultdict(set)
    for item in inventory.items:
        same_id_versions[(item.lottery_type, item.strategy_id)].add(item.strategy_version)
    split_versions = {
        key: versions for key, versions in same_id_versions.items() if len(versions) > 1
    }
    assert split_versions[(LotteryType.BIG_LOTTO, "biglotto_deviation_2bet")] == {None, "v0.1"}

    assert all(item.reconstruction_reason.strip() for item in inventory.items)
    assert all(
        item.execution_capability is ReplayExecutionCapability.EXECUTABLE
        or item.adapter_mapping is None
        for item in inventory.items
    )
    assert len(inventory.source_integrity_issues) == 12


def test_online_lifecycle_can_coexist_with_no_history() -> None:
    source = ReplayStrategyIdentityMapping(
        source_kind="TEST",
        source_locator="test://strategy",
        strategy_id="online-without-history",
        strategy_version="v1",
        mapping_kind="EXACT_TEST_IDENTITY",
    )
    item = ReplayStrategyInventoryItem(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="online-without-history",
        display_name="Online without history",
        strategy_version="v1",
        source_kind="TEST",
        source_locator="test://strategy",
        lifecycle_status=ReplayLifecycleStatus.ONLINE,
        replay_data_status=ReplayDataStatus.NO_HISTORY,
        execution_capability=ReplayExecutionCapability.UNAVAILABLE,
        reconstruction_reason="No retained data or adapter is available.",
        historical_data_count=0,
        alias_or_identity_mapping=(source,),
    )

    assert item.lifecycle_status is ReplayLifecycleStatus.ONLINE
    assert item.replay_data_status is ReplayDataStatus.NO_HISTORY
    assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE


def test_code_only_and_has_history_contracts_require_explicit_evidence() -> None:
    source = ReplayStrategyIdentityMapping(
        source_kind="TEST_CODE",
        source_locator="src/test_only_strategy.py#TestOnlyStrategy",
        strategy_id="test_code_only",
        strategy_version="v1",
        mapping_kind="DIRECT_CODE_IDENTITY",
    )
    code_only = ReplayStrategyInventoryItem(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="test_code_only",
        display_name="Unbound source-only strategy",
        strategy_version="v1",
        source_kind="CODE_ONLY",
        source_locator=source.source_locator,
        lifecycle_status=ReplayLifecycleStatus.CODE_ONLY,
        replay_data_status=ReplayDataStatus.CODE_ONLY,
        execution_capability=ReplayExecutionCapability.UNAVAILABLE,
        reconstruction_reason="The identity is known from source, but no Replay adapter exists.",
        historical_data_count=0,
        alias_or_identity_mapping=(source,),
    )
    assert code_only.replay_data_status is ReplayDataStatus.CODE_ONLY
    assert code_only.execution_capability is ReplayExecutionCapability.UNAVAILABLE

    with pytest.raises(ValueError, match="HAS_HISTORY requires"):
        ReplayStrategyInventoryItem(
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id="test_code_only",
            display_name="Unverified history",
            strategy_version="v1",
            source_kind="CODE_ONLY",
            source_locator=source.source_locator,
            lifecycle_status=ReplayLifecycleStatus.ONLINE,
            replay_data_status=ReplayDataStatus.HAS_HISTORY,
            execution_capability=ReplayExecutionCapability.UNAVAILABLE,
            reconstruction_reason="No row-level records were found.",
            historical_data_count=0,
            alias_or_identity_mapping=(source,),
        )

    with pytest.raises(ValueError, match="require a concrete adapter_mapping"):
        ReplayStrategyInventoryItem(
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id="test_code_only",
            display_name="Unbound executable",
            strategy_version="v1",
            source_kind="CODE_ONLY",
            source_locator=source.source_locator,
            lifecycle_status=ReplayLifecycleStatus.CODE_ONLY,
            replay_data_status=ReplayDataStatus.RECONSTRUCTABLE,
            execution_capability=ReplayExecutionCapability.EXECUTABLE,
            reconstruction_reason="No deterministic adapter exists.",
            historical_data_count=0,
            alias_or_identity_mapping=(source,),
        )


class _PowerLottoGetOneBetAdapter:
    strategy_id = "test_power_get_one_bet"
    strategy_name = "Test P638 one-bet adapter"
    strategy_version = "v1"
    min_history = 0

    def get_one_bet(self, rows: object, lottery_type: LotteryType) -> tuple[tuple[int, ...], int]:
        assert rows == ()
        assert lottery_type is LotteryType.POWER_LOTTO
        return (1, 2, 3, 4, 5, 6), 7


def test_powerlotto_wrapper_preserves_second_zone_for_generic_adapter() -> None:
    implementation = _PowerLottoGetOneBetAdapter()
    binding = binding_from_implementation(
        implementation,
        behavior=ReplayBehavior.DETERMINISTIC,
    )
    adapter = PowerLottoReplayAdapter((binding,))
    target = ReplayDraw(
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number="1",
        draw_date=date(2026, 1, 1),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
    )

    tickets = adapter.generate(binding.strategy, (), target)

    assert len(tickets) == 1
    assert tickets[0].main_numbers == (1, 2, 3, 4, 5, 6)
    assert tickets[0].special_number == 7
