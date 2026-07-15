"""Adapter loading for executable strategies only — no stubs, ever."""

from __future__ import annotations

import importlib

from quantlab.strategies.catalog import StrategyCatalog


class NotExecutableError(LookupError):
    pass


class ExecutableRegistry:
    def __init__(self, catalog: StrategyCatalog) -> None:
        self._catalog = catalog

    def executable_ids(self) -> frozenset[str]:
        return frozenset(d.strategy_id for d in self._catalog if d.executable)

    def load_adapter(self, strategy_id: str) -> object:
        descriptor = self._catalog.get(strategy_id)
        if not descriptor.executable or descriptor.adapter_path is None:
            raise NotExecutableError(
                f"{strategy_id} is {descriptor.lifecycle_status}; "
                "only executable strategies may load adapters"
            )
        module_name, _, attribute = descriptor.adapter_path.partition(":")
        module = importlib.import_module(module_name)
        return getattr(module, attribute) if attribute else module
