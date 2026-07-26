"""Invariant tests — these replace legacy exact-count/blob-pin assertions.

Adding a strategy must NEVER require editing these tests.
"""

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.strategies.adapters import (
    BigLottoP02BetBet1Adapter,
    BigLottoP02BetBet2Adapter,
)
from lottolab.strategies.catalog import (
    DuplicateStrategyIdError,
    StrategyCatalog,
    UnknownStrategyError,
    production_catalog,
)
from lottolab.strategies.executable_registry import ExecutableRegistry, NotExecutableError


def make_descriptor(
    strategy_id: str,
    *,
    status: LifecycleStatus,
    executable: bool,
    adapter_path: str | None = None,
    min_history: int = 1,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=strategy_id,
        version="v0.1",
        lottery_types=(LotteryType.DAILY_539,),
        lifecycle_status=status,
        executable=executable,
        adapter_path=adapter_path,
        min_history=min_history,
    )


def test_duplicate_ids_rejected() -> None:
    first = make_descriptor("dup", status=LifecycleStatus.OBSERVATION, executable=False)
    with pytest.raises(DuplicateStrategyIdError):
        StrategyCatalog([first, first])


def test_only_online_may_be_executable() -> None:
    with pytest.raises(ValueError, match="iff lifecycle_status is ONLINE"):
        make_descriptor(
            "obs", status=LifecycleStatus.OBSERVATION, executable=True, adapter_path="x:y"
        )


def test_executable_requires_adapter_path() -> None:
    with pytest.raises(ValueError, match="requires adapter_path"):
        make_descriptor("online", status=LifecycleStatus.ONLINE, executable=True)


def test_online_status_requires_executable_descriptor() -> None:
    with pytest.raises(ValueError, match="iff lifecycle_status is ONLINE"):
        make_descriptor("online", status=LifecycleStatus.ONLINE, executable=False)


def test_non_executable_rejects_adapter_path() -> None:
    with pytest.raises(ValueError, match="cannot declare adapter_path"):
        make_descriptor(
            "obs",
            status=LifecycleStatus.OBSERVATION,
            executable=False,
            adapter_path="x:y",
        )


@pytest.mark.parametrize(
    ("strategy_id", "min_history", "message"),
    [("", 1, "strategy_id"), ("valid", 0, "min_history")],
)
def test_descriptor_rejects_invalid_identity_or_history(
    strategy_id: str, min_history: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        make_descriptor(
            strategy_id,
            status=LifecycleStatus.OBSERVATION,
            executable=False,
            min_history=min_history,
        )


def test_registry_never_loads_non_executable() -> None:
    catalog = StrategyCatalog(
        [make_descriptor("obs", status=LifecycleStatus.OBSERVATION, executable=False)]
    )
    registry = ExecutableRegistry(catalog)
    assert registry.executable_ids() == frozenset()
    with pytest.raises(NotExecutableError):
        registry.load_adapter("obs")


def test_list_filters_by_status_and_type() -> None:
    catalog = StrategyCatalog(
        [
            make_descriptor("obs", status=LifecycleStatus.OBSERVATION, executable=False),
            make_descriptor("retired", status=LifecycleStatus.RETIRED, executable=False),
        ]
    )
    listed = catalog.list(lifecycle_status=LifecycleStatus.OBSERVATION)
    assert [d.strategy_id for d in listed] == ["obs"]
    assert len(catalog.list(lottery_type=LotteryType.DAILY_539)) == 2


def test_list_order_deterministically_preserves_descriptor_declaration() -> None:
    catalog = StrategyCatalog(
        [
            make_descriptor("zeta", status=LifecycleStatus.RETIRED, executable=False),
            make_descriptor("alpha", status=LifecycleStatus.OBSERVATION, executable=False),
        ]
    )
    assert [descriptor.strategy_id for descriptor in catalog.list()] == ["zeta", "alpha"]
    assert [descriptor.strategy_id for descriptor in catalog] == ["zeta", "alpha"]


def test_unknown_strategy_behavior_is_explicit() -> None:
    catalog = StrategyCatalog(())
    registry = ExecutableRegistry(catalog)
    with pytest.raises(UnknownStrategyError, match="missing"):
        catalog.get("missing")
    with pytest.raises(UnknownStrategyError, match="missing"):
        registry.load_adapter("missing")


def test_production_catalog_invariants() -> None:
    """Holds for any future content: ids unique (by construction), and every
    executable descriptor must be loadable metadata-wise."""
    catalog = production_catalog()
    executable_ids = ExecutableRegistry(catalog).executable_ids()
    catalog_ids = {descriptor.strategy_id for descriptor in catalog}
    observation_ids = {
        descriptor.strategy_id
        for descriptor in catalog
        if descriptor.lifecycle_status is LifecycleStatus.OBSERVATION
    }

    assert executable_ids <= catalog_ids
    assert executable_ids.isdisjoint(observation_ids)
    for descriptor in catalog:
        assert descriptor.provenance
        assert descriptor.executable is (descriptor.lifecycle_status is LifecycleStatus.ONLINE)
        if descriptor.executable:
            assert descriptor.adapter_path, descriptor.strategy_id
        else:
            assert descriptor.adapter_path is None


def test_catalog_appends_p0_bet2_after_bet1_without_reordering_existing_strategies() -> None:
    catalog = production_catalog()
    ids = [descriptor.strategy_id for descriptor in catalog]
    assert ids == [
        "biglotto_social_wisdom_anti_popularity",
        "biglotto_zone_split_3bet_bet1",
        "biglotto_deviation_2bet",
        "biglotto_p0_2bet_bet1",
        "biglotto_p0_2bet_bet2",
    ]
    online_ids = {
        descriptor.strategy_id
        for descriptor in catalog
        if descriptor.lifecycle_status is LifecycleStatus.ONLINE
    }
    assert online_ids == set(ids)
    assert ExecutableRegistry(catalog).executable_ids() == frozenset(ids)


def test_p0_bet1_descriptor_and_adapter_identity_match_exactly() -> None:
    descriptor = production_catalog().get(BigLottoP02BetBet1Adapter.strategy_id)
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
    ) == (
        BigLottoP02BetBet1Adapter.strategy_id,
        BigLottoP02BetBet1Adapter.strategy_name,
        BigLottoP02BetBet1Adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoP02BetBet1Adapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_selected:BigLottoP02BetBet1Adapter",
    )
    assert "evidence_status:HISTORICAL_RESEARCH_ONLY" in descriptor.provenance
    assert "current_significance:NOT_ESTABLISHED" in descriptor.provenance


def test_p0_bet2_descriptor_and_adapter_identity_match_exactly() -> None:
    descriptor = production_catalog().get(BigLottoP02BetBet2Adapter.strategy_id)
    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.min_history,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.adapter_path,
    ) == (
        BigLottoP02BetBet2Adapter.strategy_id,
        BigLottoP02BetBet2Adapter.strategy_name,
        BigLottoP02BetBet2Adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        BigLottoP02BetBet2Adapter.min_history,
        LifecycleStatus.ONLINE,
        True,
        "lottolab.strategies.adapters.biglotto_selected:BigLottoP02BetBet2Adapter",
    )
    assert descriptor.provenance == (
        "legacy_commit:44a9067b73cc38fcd517673f5187e98080997aef",
        "legacy_source:tools/quick_predict.py",
        "legacy_source:recovered_strategies/biglotto/historical_adapters.py",
        "evidence_status:HISTORICAL_RESEARCH_ONLY",
        "current_significance:NOT_ESTABLISHED",
        "migration_task:MATHSTATISTICALANALYSIS_BIGLOTTO_P0_2BET_BET2_ADAPTER_MIGRATION_R1",
    )
