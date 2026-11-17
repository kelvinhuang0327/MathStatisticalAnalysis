from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import ReplayExecutionCapability


def test_nonoverlap_candidates_are_bound_without_replacing_native_strategies() -> None:
    inventory = load_replay_strategy_inventory()
    items = {
        (item.strategy_id, item.strategy_version): item
        for item in inventory.items
        if item.lottery_type is LotteryType.BIG_LOTTO
    }
    candidates = (
        "research_biglotto__k3_nonoverlap_optimizer_candidate_20261116",
        "research_biglotto__k3_nonoverlap_ecp_candidate_20261116",
    )
    for strategy_id in candidates:
        item = items[(strategy_id, "v1.0.0")]
        assert item.execution_capability is ReplayExecutionCapability.EXECUTABLE
        assert item.adapter_mapping is not None
        assert item.adapter_mapping.strategy_id == strategy_id
        assert item.adapter_mapping.strategy_version == "v1.0.0"
    for strategy_id in (
        "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
        "legacy_biglotto__test_ecp__c9d5ac6decdd",
    ):
        assert (strategy_id, "v0.1") in items
