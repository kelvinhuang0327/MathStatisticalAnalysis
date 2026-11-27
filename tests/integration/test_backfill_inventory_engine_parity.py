"""Cross-check exposed capabilities against the exact Backfill worker bindings."""

from pathlib import Path

import pytest

from lottolab.application.historical_replay_adapters import ReplayStrategyBinding
from lottolab.application.native_replay_inventory import native_strategy_inventory
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import ReplayExecutionCapability
from lottolab.interfaces.cli import replay_backfill as worker


def test_inventory_capabilities_match_real_worker_bindings() -> None:
    inventory = load_replay_strategy_inventory()
    rows = {(r.lottery_type, r.strategy_id, r.strategy_version): r for r in inventory.items}
    engine: dict[tuple[LotteryType, str, str], ReplayStrategyBinding] = {}
    for lottery in LotteryType:
        bindings, _ = native_strategy_inventory(lottery)
        engine.update(
            {(lottery, b.strategy.strategy_id, b.strategy.strategy_version): b for b in bindings}
        )
    expected_new_identities = {
        (
            LotteryType.BIG_LOTTO,
            "research_causal_renewal_hazard_k2",
            "FIXED_DISCRETE_RENEWAL_HAZARD_V1",
        ),
        (
            LotteryType.BIG_LOTTO,
            "research_causal_renewal_hazard_k3",
            "FIXED_DISCRETE_RENEWAL_HAZARD_V1",
        ),
        (
            LotteryType.BIG_LOTTO,
            "research_causal_renewal_hazard_k5",
            "FIXED_DISCRETE_RENEWAL_HAZARD_V1",
        ),
        (LotteryType.BIG_LOTTO, "research_conditional_transfer_entropy_k2", "EH02_V1"),
        (LotteryType.BIG_LOTTO, "research_conditional_transfer_entropy_k3", "EH02_V1"),
        (LotteryType.BIG_LOTTO, "research_conditional_transfer_entropy_k5", "EH02_V1"),
    }
    exposed = {key for key, row in rows.items() if row.backfill_runnable}
    assert exposed == set(engine)
    assert len(expected_new_identities) == 6
    assert expected_new_identities <= exposed
    assert expected_new_identities <= set(engine)
    assert len(expected_new_identities & exposed) == 6
    assert len(expected_new_identities & set(engine)) == 6
    assert len(exposed) == 217
    assert len(exposed - expected_new_identities) == 211
    for identity, binding in engine.items():
        row = rows[identity]
        assert row.backfill_native_binding is True
        assert row.wrapper_callable is True
        assert row.reconstructable is True
        assert row.execution_block_reason is None
        assert any(
            source.identity == identity
            and source.source_kind == "NATIVE_BACKFILL_ENGINE"
            and f"fingerprint={binding.strategy.fingerprint}" in source.source_locator
            for source in row.backfill_native_binding_sources
        )


def test_versioned_seeded_wrappers_and_existing_history_identities_are_preserved() -> None:
    inventory = load_replay_strategy_inventory()
    rows = {(r.lottery_type, r.strategy_id, r.strategy_version): r for r in inventory.items}
    legacy_id = "legacy_biglotto__frontend_monte_carlo_strategy__9d8fe030546e"
    old = rows[(LotteryType.BIG_LOTTO, legacy_id, "v0.1")]
    seeded = rows[(LotteryType.BIG_LOTTO, legacy_id, "v0.1+seeded-replay-v1")]
    assert old.backfill_native_binding is None
    assert old.backfill_runnable is False
    assert old.execution_block_reason is not None
    assert old.execution_block_reason.startswith("NATIVE_BINDING_VERSION_MISMATCH")
    assert seeded.backfill_runnable is True
    graph = rows[(LotteryType.POWER_LOTTO, "power_graph_synergy_seed42_2bet", "v0.1-seed42")]
    assert graph.backfill_runnable is False
    assert graph.execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert graph.execution_block_reason == "NO_COMPLETE_SECOND_ZONE_REPLAY_SOURCE"
    for sid, version in (
        ("research_biglotto__k9_optimal_coverage_candidate", "v0.1-research"),
        ("research_biglotto__k30_fixed_random_control_20261119_r1", "v1.0.0"),
    ):
        assert (LotteryType.BIG_LOTTO, sid, version) in rows


def test_execution_identity_covers_native_binding_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "lottolab"
    paths = (
        "interfaces/cli/replay_backfill.py",
        "application/historical_replay_adapters.py",
        "application/native_replay_inventory.py",
        "application/use_cases/historical_replay_controller.py",
        "application/use_cases/replay_backfill.py",
        "infrastructure/persistence/replay_backfill_store.py",
    )
    for name in paths:
        file = package / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("initial\n")
    monkeypatch.setattr(worker, "__file__", str(package / paths[0]))
    before = worker.execution_source_identity()
    (package / "application/native_replay_inventory.py").write_text("changed\n")
    assert worker.execution_source_identity() != before


def test_evolution_ticket_validator_keeps_exact_builtin_container_rules() -> None:
    from lottolab.strategies.adapters.biglotto_evolution_causal import (
        _valid_ticket,  # pyright: ignore[reportPrivateUsage]
    )

    class ListSubclass(list[int]):
        pass

    assert _valid_ticket([1, 2, 3, 4, 5, 6])
    assert _valid_ticket((1, 2, 3, 4, 5, 6))
    assert not _valid_ticket(ListSubclass([1, 2, 3, 4, 5, 6]))
    assert not _valid_ticket([True, 2, 3, 4, 5, 6])
    assert not _valid_ticket([1, 2, 3, 4, 5, 5])
