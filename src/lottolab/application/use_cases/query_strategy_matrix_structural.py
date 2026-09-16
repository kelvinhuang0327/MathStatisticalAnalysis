"""Query the packaged structural Matrix projection without replay or ranking."""

from __future__ import annotations

from lottolab.application.ports import StrategyMatrixStructuralReaderFactory
from lottolab.application.strategy_matrix_structural import (
    StrategyMatrixStructuralDataset,
    StrategyMatrixStructuralQuery,
    query_strategy_matrix_structural,
)


class QueryStrategyMatrixStructural:
    def __init__(self, reader_factory: StrategyMatrixStructuralReaderFactory) -> None:
        self._reader_factory = reader_factory

    def execute(self, query: StrategyMatrixStructuralQuery) -> StrategyMatrixStructuralDataset:
        dataset = self._reader_factory().read()
        return query_strategy_matrix_structural(dataset, query)
