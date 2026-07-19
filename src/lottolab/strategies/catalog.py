"""Read-only strategy catalog: metadata lookup without importing adapters."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor


class DuplicateStrategyIdError(ValueError):
    pass


class UnknownStrategyError(KeyError):
    pass


class StrategyCatalog:
    def __init__(self, descriptors: Iterable[StrategyDescriptor]) -> None:
        self._by_id: dict[str, StrategyDescriptor] = {}
        for descriptor in descriptors:
            if descriptor.strategy_id in self._by_id:
                raise DuplicateStrategyIdError(descriptor.strategy_id)
            self._by_id[descriptor.strategy_id] = descriptor

    def __iter__(self) -> Iterator[StrategyDescriptor]:
        return iter(self.list())

    def __len__(self) -> int:
        return len(self._by_id)

    def get(self, strategy_id: str) -> StrategyDescriptor:
        try:
            return self._by_id[strategy_id]
        except KeyError as exc:
            raise UnknownStrategyError(strategy_id) from exc

    def list(
        self,
        *,
        lottery_type: LotteryType | None = None,
        lifecycle_status: LifecycleStatus | None = None,
    ) -> tuple[StrategyDescriptor, ...]:
        """Return matches in the descriptor declaration order pinned by provenance."""
        return tuple(
            descriptor
            for descriptor in self._by_id.values()
            if (lottery_type is None or lottery_type in descriptor.lottery_types)
            and (lifecycle_status is None or descriptor.lifecycle_status is lifecycle_status)
        )


_PRODUCTION_DESCRIPTORS = (
    StrategyDescriptor(
        strategy_id="biglotto_social_wisdom_anti_popularity",
        strategy_name="大樂透 Social Wisdom Anti-Popularity",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:"
            "BigLottoSocialWisdomAntiPopularityAdapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f",
            "legacy_source:lottery_api/models/replay_strategy_registry.py",
            "legacy_task:P541F_R2",
            "legacy_pr:690",
            "migration_task:P600B_R2",
            "migration_task:P602B",
        ),
    ),
    StrategyDescriptor(
        strategy_id="biglotto_zone_split_3bet_bet1",
        strategy_name="大樂透 Zone Split 3注（Replay Bet 1）",  # noqa: RUF001
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path=(
            "lottolab.strategies.adapters.biglotto_selected:BigLottoZoneSplit3BetBet1Adapter"
        ),
        min_history=1,
        provenance=(
            "legacy_commit:520c3922a7c8f47e5b6196fb4b0d54716fa5fd9f",
            "legacy_source:lottery_api/models/replay_strategy_registry.py",
            "legacy_task:P541F_R2",
            "legacy_pr:690",
            "migration_task:P600B_R2",
            "migration_task:P602B",
        ),
    ),
)


def production_catalog() -> StrategyCatalog:
    """Return metadata in the pinned legacy descriptor declaration order."""
    return StrategyCatalog(_PRODUCTION_DESCRIPTORS)
