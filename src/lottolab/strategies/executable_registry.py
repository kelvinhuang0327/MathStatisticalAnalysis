"""Adapter loading for executable strategies only — no stubs, ever."""

from __future__ import annotations

import importlib
from collections.abc import Mapping

from lottolab.strategies.catalog import StrategyCatalog


class NotExecutableError(LookupError):
    pass


class ExecutableRegistry:
    def __init__(
        self,
        catalog: StrategyCatalog,
        *,
        replay_only_adapter_paths: Mapping[tuple[str, str], str] | None = None,
    ) -> None:
        self._catalog = catalog
        self._replay_only_adapter_paths = dict(replay_only_adapter_paths or {})

    def executable_ids(self) -> frozenset[str]:
        return frozenset(d.strategy_id for d in self._catalog if d.executable)

    def load_adapter(
        self,
        strategy_id: str,
        strategy_version: str | None = None,
    ) -> object:
        descriptor = self._catalog.get(strategy_id, strategy_version)
        if not descriptor.executable or descriptor.adapter_path is None:
            raise NotExecutableError(
                f"{strategy_id} is {descriptor.lifecycle_status}; "
                "only executable strategies may load adapters"
            )
        return self._load_adapter_path(descriptor.adapter_path)

    def load_replay_adapter(self, strategy_id: str, strategy_version: str) -> object:
        """Load an exact retired source adapter available only to historical replay."""

        descriptor = self._catalog.get(strategy_id, strategy_version)
        if descriptor.executable and descriptor.adapter_path is not None:
            return self.load_adapter(strategy_id, strategy_version)
        adapter_path = self._replay_only_adapter_paths.get((strategy_id, strategy_version))
        if adapter_path is None:
            raise NotExecutableError(
                f"{strategy_id}@{strategy_version} has no replay-only adapter binding"
            )
        return self._load_adapter_path(adapter_path)

    @staticmethod
    def _load_adapter_path(adapter_path: str) -> object:
        module_name, _, attribute = adapter_path.partition(":")
        module = importlib.import_module(module_name)
        return getattr(module, attribute) if attribute else module
