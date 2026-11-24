from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

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
    seed_identity_set = _seed_identity_tuples()
    seed_identity_count = len(seed_identity_set)
    actual_identity_set = {
        (item.lottery_type, item.strategy_id, item.strategy_version) for item in inventory.items
    }
    preserved_main_identities = actual_identity_set - seed_identity_set

    assert seed_identity_count == 1000
    assert inventory.total_discovered_strategies == 765 + seed_identity_count
    assert inventory.total_unique_strategies == _BASE_MAIN_IDENTITY_COUNT + seed_identity_count
    assert (
        len(actual_identity_set)
        == len(inventory.items)
        == _BASE_MAIN_IDENTITY_COUNT + seed_identity_count
    )
    assert len(actual_identity_set) == len(preserved_main_identities) + len(seed_identity_set)
    assert seed_identity_set.isdisjoint(preserved_main_identities)
    assert actual_identity_set == preserved_main_identities | seed_identity_set
    assert len(preserved_main_identities) == _BASE_MAIN_IDENTITY_COUNT
    assert _identity_set_sha256(preserved_main_identities) == (
        "d57aff547491e137fa31bdd509177ad64abdaa18311a07914cf9c46780653809"
    )
    assert len(inventory.executable_items) == 224
    assert inventory.unresolved_source_count == 9
    assert source_counts["PRODUCTION_CATALOG"].source_identity_count == 138
    assert source_counts["B649_RESEARCH_CATALOG"].source_identity_count == 221
    assert source_counts["B649_REPLAY_BATCH_REGISTRY"].source_identity_count == 11
    assert source_counts["T539_REPLAY_ADAPTER"].source_identity_count == 62
    assert source_counts["P638_REPLAY_ADAPTER"].source_identity_count == 23
    assert source_counts["STRATEGY_ADAPTER_CODE"].source_identity_count == 106
    assert source_counts["STRATEGY_ADAPTER_CODE"].source_row_count == 107
    assert source_counts["REPLAY_BACKFILL_IMPORTED_RESULT"].source_identity_count == 50
    assert source_counts["REPLAY_BACKFILL_IMPORTED_RESULT"].source_row_count == 50
    assert (
        source_counts["REPLAY_BACKFILL_STAGE_CANDIDATE"].source_identity_count
        == seed_identity_count
    )
    assert source_counts["REPLAY_BACKFILL_STAGE_CANDIDATE"].source_row_count == 1200

    lottery_counts = Counter(item.lottery_type for item in inventory.items)
    executable_by_lottery = Counter(item.lottery_type for item in inventory.executable_items)
    assert lottery_counts == {
        LotteryType.BIG_LOTTO: 414 + seed_identity_count,
        LotteryType.DAILY_539: 62,
        LotteryType.POWER_LOTTO: 34,
    }
    assert executable_by_lottery == {
        LotteryType.BIG_LOTTO: 139,
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
        ReplayDataStatus.REBUILDABLE: 224,
        ReplayDataStatus.ARTIFACT_ONLY: 135,
        ReplayDataStatus.REJECTED: 74,
        ReplayDataStatus.NO_HISTORY: 72 + len(_seed_identity_tuples()),
        ReplayDataStatus.CODE_ONLY: 5,
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
    assert len(artifact_only) == 135
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
        ("research_biglotto__quick_ml_pattern_bounds_v1", "v0.1-research"),
        ("legacy_biglotto__evolution_engine__3df019c31ce4", "v0.2"),
        ("research_biglotto__k30_geometry_exact_swap_history_v1", "v1"),
        ("research_biglotto__k3_nonoverlap_optimizer_candidate_20261116", "v1.0.0"),
        ("research_biglotto__k3_nonoverlap_ecp_candidate_20261116", "v1.0.0"),
        ("legacy_biglotto__evolution_engine__3df019c31ce4", "v0.5-prefix-isolated-r1"),
        ("tasklocal_evolution_h1_duplicate_completion_20261105", "h1-prefix-isolated-r1"),
        ("tasklocal_evolution_h2_uniform_cover_20261105", "h2-prefix-isolated-r1"),
    }
    code_only_replay_data = [
        item
        for item in code_only_lifecycle
        if item.replay_data_status is ReplayDataStatus.CODE_ONLY
    ]
    assert len(code_only_replay_data) == 5
    assert all(
        i.execution_capability is ReplayExecutionCapability.UNAVAILABLE
        for i in code_only_replay_data
    )
    executable_code_only = [
        item
        for item in code_only_lifecycle
        if item.replay_data_status is ReplayDataStatus.REBUILDABLE
    ]
    assert {item.strategy_id for item in executable_code_only} == {
        "research_biglotto__quick_ml_corrected_successor_v1",
        "research_biglotto__quick_ml_pattern_bounds_v1",
        "research_biglotto__k3_nonoverlap_optimizer_candidate_20261116",
        "research_biglotto__k3_nonoverlap_ecp_candidate_20261116",
    }
    assert all(
        item.execution_capability is ReplayExecutionCapability.EXECUTABLE
        for item in executable_code_only
    )

    online = [
        item for item in inventory.items if item.lifecycle_status is ReplayLifecycleStatus.ONLINE
    ]
    assert len(online) == 138
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
    assert inventory.source_integrity_issues == ()


@pytest.mark.parametrize(
    ("strategy_id", "version"),
    [
        ("legacy_biglotto__test_ecp__c9d5ac6decdd", "v0.2"),
        ("legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5", "v0.2"),
        ("research_biglotto__radical_gap_complete_v2", "v2"),
    ],
)
def test_staged_research_identity_is_not_executable_or_claimed_imported(
    strategy_id: str, version: str
) -> None:
    matches = [
        item
        for item in load_replay_strategy_inventory().items
        if item.lottery_type is LotteryType.BIG_LOTTO
        and item.strategy_id == strategy_id
        and item.strategy_version == version
    ]
    assert len(matches) == 1
    assert matches[0].replay_data_status is ReplayDataStatus.NO_HISTORY
    assert matches[0].execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert matches[0].adapter_mapping is None


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


_BASE_MAIN_IDENTITY_COUNT = 510

def _multiseed_fixture() -> dict[str, Any]:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "k30_multiseed_stage_sources.json"
    return json.loads(json.dumps(json.loads(fixture_path.read_text(encoding="utf-8"))))


def _seed_identity_tuples() -> set[tuple[LotteryType, str, str | None]]:
    fixture = _multiseed_fixture()
    return {
        (LotteryType.BIG_LOTTO, row["strategy_id"], row["strategy_version"])
        for row in fixture["seed_identities"]
    }


def _identity_set_sha256(
    identities: set[tuple[LotteryType, str, str | None]],
) -> str:
    rows = sorted(
        ((lottery.value, strategy_id, version) for lottery, strategy_id, version in identities),
        key=lambda row: (row[0], row[1], row[2] or ""),
    )
    round_tripped = json.loads(json.dumps(rows, ensure_ascii=False))
    payload = json.dumps(round_tripped, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _candidate_multiseed_rows() -> list[dict[str, Any]]:
    fixture = _multiseed_fixture()
    inventory = load_replay_strategy_inventory()
    rows: list[dict[str, Any]] = []
    for item in inventory.items:
        if item.source_kind != "REPLAY_BACKFILL_STAGE_CANDIDATE":
            continue
        for source in item.alias_or_identity_mapping:
            if source.source_kind != "REPLAY_BACKFILL_STAGE_CANDIDATE":
                continue
            stage_group, query = source.source_locator.removeprefix(
                "replay-backfill-stage:"
            ).split("/MERGE_PENDING.json#", 1)
            values = dict(parse_qsl(query, keep_blank_values=True))
            if "run_id" in values:
                run_ids = [values["run_id"]]
                run_binding = None
            elif "initial_run_id" in values:
                run_ids = [
                    values["initial_run_id"],
                    values["continuation_shared_run_id"],
                ]
                run_binding = {
                    "binding_status": "VERIFIED_PER_STRATEGY_PARTITION",
                    "initial_run_id": values["initial_run_id"],
                    "continuation_shared_run_id": values["continuation_shared_run_id"],
                    "initial_targets_per_strategy": int(
                        values["initial_targets_per_strategy"].split("/", 1)[0]
                    ),
                    "initial_expected_targets_per_strategy": int(
                        values["initial_targets_per_strategy"].split("/", 1)[1]
                    ),
                    "continuation_shared_targets_per_strategy": int(
                        values["continuation_shared_targets_per_strategy"]
                    ),
                    "overlap_cells_across_25_strategies": int(values["overlap_cells"]),
                    "link_verified": values["link_verified"] == "true",
                    "source_result_sha256": values["run_partition_source_sha256"],
                    "manifest_sha256": fixture["manifest_sha256_by_stage"][stage_group],
                }
            else:
                run_ids = values["run_ids"].split(",")
                run_binding = None
            draw_start, draw_end = values["target_draw_range"].split("..", 1)
            rows.append(
                {
                    "strategy_id": source.strategy_id,
                    "strategy_version": source.strategy_version,
                    "stage_group": stage_group,
                    "run_ids": run_ids,
                    "target_draw_range": [draw_start, draw_end],
                    "source_history_provenance_status": values[
                        "source_history_provenance_status"
                    ],
                    "run_binding": run_binding,
                }
            )
    return rows


def _validate_multiseed_projection(
    *,
    seed_identities: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    manifest_sha256_by_stage: dict[str, str],
    frozen_root_seed_sha256: str,
    run_partition_resolution: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
) -> None:
    fixture = _multiseed_fixture()
    if frozen_root_seed_sha256 != fixture["frozen_root_seed_sha256"]:
        raise ValueError("frozen seed source hash mismatch")
    expected_partition = fixture["run_partition_resolution"]
    if run_partition_resolution != expected_partition:
        raise ValueError("run partition evidence mismatch")
    if (
        run_partition_resolution["run_ids"]
        != [
            run_partition_resolution["initial_run_id"],
            run_partition_resolution["continuation_shared_run_id"],
        ]
        or run_partition_resolution["initial_run_status"] != "COMPLETED"
        or run_partition_resolution["continuation_run_status"] != "COMPLETED"
        or run_partition_resolution["initial_run_complete_targets_per_strategy"]
        != run_partition_resolution["initial_run_expected_targets_per_strategy"]
        or run_partition_resolution["manifest_cells_per_strategy"]
        != run_partition_resolution["initial_run_complete_targets_per_strategy"]
        or run_partition_resolution["strategy_count"] != 25
        or run_partition_resolution["continuation_shared_targets_per_strategy"] != 568
        or run_partition_resolution["overlap_cells_across_25_strategies"]
        != run_partition_resolution["strategy_count"]
        * run_partition_resolution["continuation_shared_targets_per_strategy"]
        or run_partition_resolution["target_draw_range"]
        != ["96000001", "115000056"]
        or run_partition_resolution["manifest_sha256"]
        != manifest_sha256_by_stage.get(run_partition_resolution["stage_group"])
        or run_partition_resolution["source_result_sha256"]
        != "85a6349318e12674e07851daa960799da3075adc3965b39fb777492554024847"
        or run_partition_resolution["link_verified"] is not True
    ):
        raise ValueError("run partition evidence mismatch")
    partition_rows = [
        row
        for row in source_records
        if row["stage_group"] == run_partition_resolution["stage_group"]
    ]
    if len(partition_rows) != run_partition_resolution["strategy_count"]:
        raise ValueError("run partition strategy count mismatch")
    expected_binding = {
        "binding_status": "VERIFIED_PER_STRATEGY_PARTITION",
        "initial_run_id": run_partition_resolution["initial_run_id"],
        "continuation_shared_run_id": run_partition_resolution[
            "continuation_shared_run_id"
        ],
        "initial_targets_per_strategy": run_partition_resolution[
            "initial_run_complete_targets_per_strategy"
        ],
        "initial_expected_targets_per_strategy": run_partition_resolution[
            "initial_run_expected_targets_per_strategy"
        ],
        "continuation_shared_targets_per_strategy": run_partition_resolution[
            "continuation_shared_targets_per_strategy"
        ],
        "overlap_cells_across_25_strategies": run_partition_resolution[
            "overlap_cells_across_25_strategies"
        ],
        "link_verified": True,
        "source_result_sha256": run_partition_resolution["source_result_sha256"],
        "manifest_sha256": run_partition_resolution["manifest_sha256"],
    }
    if any(
        row["run_ids"] != run_partition_resolution["run_ids"]
        or row["run_binding"] != expected_binding
        or row["target_draw_range"] != run_partition_resolution["target_draw_range"]
        for row in partition_rows
    ):
        raise ValueError("run partition binding mismatch")
    identity_keys = [
        (row["strategy_id"], row["strategy_version"]) for row in seed_identities
    ]
    if len(identity_keys) != len(set(identity_keys)):
        raise ValueError("duplicate seed identity")
    if len(seed_identities) != fixture["seed_identity_count"]:
        raise ValueError("seed identity count mismatch")
    allowed_identities = set(identity_keys)

    expected_sources: list[tuple[Any, ...]] = []
    for row in source_records:
        stage_group = row["stage_group"]
        if stage_group not in manifest_sha256_by_stage:
            raise ValueError("missing stage manifest")
        if manifest_sha256_by_stage[stage_group] != row["manifest_sha256"]:
            raise ValueError("stage manifest hash mismatch")
        identity = (row["strategy_id"], row["strategy_version"])
        if identity not in allowed_identities:
            raise ValueError("source record references an unknown seed identity")
        expected_sources.append(
            (
                row["strategy_id"],
                row["strategy_version"],
                stage_group,
                tuple(row["run_ids"]),
                tuple(row["target_draw_range"]),
                row["source_history_provenance_status"],
                json.dumps(row.get("run_binding"), sort_keys=True, separators=(",", ":")),
            )
        )
    if len(expected_sources) != fixture["source_record_count"]:
        raise ValueError("source record count mismatch")
    if len(expected_sources) != len(set(expected_sources)):
        raise ValueError("duplicate source record")

    candidate_sources = [
        (
            row["strategy_id"],
            row["strategy_version"],
            row["stage_group"],
            tuple(row["run_ids"]),
            tuple(row["target_draw_range"]),
            row["source_history_provenance_status"],
            json.dumps(row.get("run_binding"), sort_keys=True, separators=(",", ":")),
        )
        for row in candidate_rows
    ]
    if len(candidate_sources) != len(set(candidate_sources)):
        raise ValueError("duplicate candidate source record")
    if Counter(candidate_sources) != Counter(expected_sources):
        raise ValueError("candidate source mapping mismatch")

def _source_locator(row: dict[str, Any]) -> str:
    run_ids = row["run_ids"]
    if len(run_ids) == 1:
        run_binding = f"run_id={run_ids[0]}"
    elif row.get("run_binding", {}).get("binding_status") == (
        "VERIFIED_PER_STRATEGY_PARTITION"
    ):
        binding = row["run_binding"]
        run_binding = (
            f"initial_run_id={binding['initial_run_id']}"
            f"&continuation_shared_run_id={binding['continuation_shared_run_id']}"
            f"&initial_targets_per_strategy="
            f"{binding['initial_targets_per_strategy']}"
            f"/{binding['initial_expected_targets_per_strategy']}"
            f"&continuation_shared_targets_per_strategy="
            f"{binding['continuation_shared_targets_per_strategy']}"
            f"&overlap_cells={binding['overlap_cells_across_25_strategies']}"
            f"&link_verified=true"
            f"&run_partition_source_sha256={binding['source_result_sha256']}"
        )
    else:
        run_binding = f"run_ids={','.join(run_ids)}&seed_to_run_binding=UNRESOLVED"
    start, end = row["target_draw_range"]
    return (
        f"replay-backfill-stage:{row['stage_group']}/MERGE_PENDING.json#{run_binding}"
        f"&target_draw_range={start}..{end}"
        f"&source_history_provenance_status={row['source_history_provenance_status']}"
    )

def test_k30_multiseed_candidates_keep_exact_stage_identity_and_status_separate() -> None:
    fixture = _multiseed_fixture()
    round_tripped_fixture = json.loads(json.dumps(fixture))
    _validate_multiseed_projection(
        seed_identities=round_tripped_fixture["seed_identities"],
        source_records=round_tripped_fixture["source_records"],
        manifest_sha256_by_stage=round_tripped_fixture["manifest_sha256_by_stage"],
        frozen_root_seed_sha256=round_tripped_fixture["frozen_root_seed_sha256"],
        run_partition_resolution=round_tripped_fixture["run_partition_resolution"],
        candidate_rows=_candidate_multiseed_rows(),
    )

    expected_ids = {
        (row["strategy_id"], row["strategy_version"])
        for row in round_tripped_fixture["seed_identities"]
    }
    inventory = load_replay_strategy_inventory()
    items = {
        (item.strategy_id, item.strategy_version): item
        for item in inventory.items
        if item.strategy_id.startswith("research_biglotto__k30_histseed_")
    }
    assert set(items) == expected_ids
    assert len(items) == round_tripped_fixture["seed_identity_count"] == 1000
    assert {version for _, version in expected_ids} == {"v1"}
    assert round_tripped_fixture["completion_windows"] == {
        "recent50_complete_seed_count": 1000,
        "full_history_complete_seed_count": 200,
        "full_history_unfinished_seed_count": 800,
        "full_history_receipt_status": "PASS",
        "recent50_receipt_status": "PASS",
    }
    expected_sources: dict[tuple[Any, Any], set[tuple[str, str | None]]] = defaultdict(set)
    for row in round_tripped_fixture["source_records"]:
        expected_sources[(row["strategy_id"], row["strategy_version"])].add(
            (
                _source_locator(row),
                row["source_history_provenance_status"],
            )
        )
    for identity, item in items.items():
        assert item.replay_data_status is ReplayDataStatus.NO_HISTORY
        assert item.historical_data_count == 0
        assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
        assert item.adapter_mapping is None
        assert item.backfill_runnable is False
        assert "RESEARCH_STRATEGY" in item.source_statuses
        actual_sources = {
            (source.source_locator, source.source_status)
            for source in item.alias_or_identity_mapping
            if source.source_kind == "REPLAY_BACKFILL_STAGE_CANDIDATE"
        }
        assert actual_sources == expected_sources[identity]
        assert all(
            source_status in item.source_statuses
            for _, source_status in actual_sources
            if source_status is not None
        )

def test_k30_multiseed_source_validation_rejects_corrupt_evidence() -> None:
    fixture = _multiseed_fixture()
    seed_identities = fixture["seed_identities"]
    source_records = fixture["source_records"]
    manifest_hashes = fixture["manifest_sha256_by_stage"]
    valid: dict[str, Any] = {
        "seed_identities": seed_identities,
        "source_records": source_records,
        "manifest_sha256_by_stage": manifest_hashes,
        "frozen_root_seed_sha256": fixture["frozen_root_seed_sha256"],
        "run_partition_resolution": fixture["run_partition_resolution"],
        "candidate_rows": _candidate_multiseed_rows(),
    }
    _validate_multiseed_projection(**valid)

    duplicate = dict(valid)
    duplicate["seed_identities"] = [*seed_identities, seed_identities[0]]
    with pytest.raises(ValueError, match="duplicate seed identity"):
        _validate_multiseed_projection(**duplicate)

    for field, replacement in (
        ("strategy_version", "wrong-version"),
        ("run_ids", ["wrong-run"]),
        ("target_draw_range", ["wrong-start", "wrong-end"]),
    ):
        altered = dict(valid)
        rows = [dict(row) for row in valid["candidate_rows"]]
        rows[0][field] = replacement
        altered["candidate_rows"] = rows
        with pytest.raises(ValueError, match="candidate source mapping mismatch"):
            _validate_multiseed_projection(**altered)

    missing_manifest = dict(valid)
    hashes = dict(manifest_hashes)
    del hashes[source_records[0]["stage_group"]]
    missing_manifest["manifest_sha256_by_stage"] = hashes
    with pytest.raises(ValueError, match="missing stage manifest"):
        _validate_multiseed_projection(**missing_manifest)

    wrong_seed_hash = dict(valid)
    wrong_seed_hash["frozen_root_seed_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="frozen seed source hash mismatch"):
        _validate_multiseed_projection(**wrong_seed_hash)

    wrong_manifest_sha = dict(valid)
    wrong_manifest_hashes = dict(manifest_hashes)
    wrong_manifest_hashes[source_records[0]["stage_group"]] = "0" * 64
    wrong_manifest_sha["manifest_sha256_by_stage"] = wrong_manifest_hashes
    with pytest.raises(ValueError, match="stage manifest hash mismatch"):
        _validate_multiseed_projection(**wrong_manifest_sha)

    wrong_source_sha = dict(valid)
    wrong_source_sha["run_partition_resolution"] = dict(
        valid["run_partition_resolution"]
    )
    wrong_source_sha["run_partition_resolution"]["source_result_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="run partition evidence mismatch"):
        _validate_multiseed_projection(**wrong_source_sha)

    wrong_partition = dict(valid)
    wrong_partition["run_partition_resolution"] = dict(
        valid["run_partition_resolution"]
    )
    wrong_partition["run_partition_resolution"][
        "continuation_shared_targets_per_strategy"
    ] = 567
    with pytest.raises(ValueError, match="run partition evidence mismatch"):
        _validate_multiseed_projection(**wrong_partition)

    wrong_seed_run = dict(valid)
    wrong_run_rows = [dict(row) for row in valid["candidate_rows"]]
    partition_row = next(
        row
        for row in wrong_run_rows
        if row["stage_group"]
        == valid["run_partition_resolution"]["stage_group"]
    )
    partition_row["run_binding"] = dict(partition_row["run_binding"])
    partition_row["run_binding"]["initial_run_id"] = "wrong-run"
    wrong_seed_run["candidate_rows"] = wrong_run_rows
    with pytest.raises(ValueError, match="candidate source mapping mismatch"):
        _validate_multiseed_projection(**wrong_seed_run)

    inventory = load_replay_strategy_inventory()
    seed_item = next(
        item
        for item in inventory.items
        if item.strategy_id.startswith("research_biglotto__k30_histseed_")
    )
    with pytest.raises(ValueError, match="HAS_HISTORY requires"):
        replace(
            seed_item,
            replay_data_status=ReplayDataStatus.HAS_HISTORY,
            historical_data_count=0,
        )

    foreign_adapter = next(
        item.adapter_mapping
        for item in inventory.items
        if item.execution_capability is ReplayExecutionCapability.EXECUTABLE
    )
    with pytest.raises(ValueError, match="adapter_mapping identity"):
        replace(
            seed_item,
            execution_capability=ReplayExecutionCapability.EXECUTABLE,
            adapter_mapping=foreign_adapter,
        )

def test_existing_k30_controls_and_fifteen_historical_controls_remain_unavailable() -> None:
    inventory = load_replay_strategy_inventory()
    identities = {
        (item.strategy_id, item.strategy_version): item for item in inventory.items
    }
    historical_controls = {
        (f"research_biglotto__historical_random_k{k}_20261119_r1", "v1.0.0")
        for k in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 25, 40, 54)
    }
    k30_controls = {
        ("research_biglotto__k30_fixed_414665013", "v1"),
        ("research_biglotto__k30_fixed_414671103", "v1"),
        ("research_biglotto__k30_fixed_random_control_20261119_r1", "v1.0.0"),
    }
    assert historical_controls | k30_controls <= identities.keys()
    for identity in historical_controls | k30_controls:
        item = identities[identity]
        assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
        assert item.adapter_mapping is None
        with pytest.raises(ValueError, match="require a concrete adapter_mapping"):
            replace(
                item,
                replay_data_status=ReplayDataStatus.RECONSTRUCTABLE,
                execution_capability=ReplayExecutionCapability.EXECUTABLE,
            )
