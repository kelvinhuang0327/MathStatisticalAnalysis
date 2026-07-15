"""Invariant tests — these replace legacy exact-count/blob-pin assertions.

Adding a strategy must NEVER require editing these tests.
"""

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.strategies.catalog import (
    DuplicateStrategyIdError,
    StrategyCatalog,
    production_catalog,
)
from lottolab.strategies.executable_registry import ExecutableRegistry, NotExecutableError


def make_descriptor(
    strategy_id: str,
    *,
    status: LifecycleStatus,
    executable: bool,
    adapter_path: str | None = None,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=strategy_id,
        version="v0.1",
        lottery_types=(LotteryType.DAILY_539,),
        lifecycle_status=status,
        executable=executable,
        adapter_path=adapter_path,
    )


def test_duplicate_ids_rejected() -> None:
    first = make_descriptor("dup", status=LifecycleStatus.OBSERVATION, executable=False)
    with pytest.raises(DuplicateStrategyIdError):
        StrategyCatalog([first, first])


def test_only_online_may_be_executable() -> None:
    with pytest.raises(ValueError, match="may be executable"):
        make_descriptor(
            "obs", status=LifecycleStatus.OBSERVATION, executable=True, adapter_path="x:y"
        )


def test_executable_requires_adapter_path() -> None:
    with pytest.raises(ValueError, match="requires adapter_path"):
        make_descriptor("online", status=LifecycleStatus.ONLINE, executable=True)


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


def test_production_catalog_invariants() -> None:
    """Holds for any future content: ids unique (by construction), and every
    executable descriptor must be loadable metadata-wise."""
    catalog = production_catalog()
    for descriptor in catalog:
        if descriptor.executable:
            assert descriptor.adapter_path, descriptor.strategy_id
