"""Read-only use cases for local draw and ingestion history."""

from __future__ import annotations

from lottolab.application.draw_data import (
    DrawHistoryPage,
    DrawHistoryQuery,
    DrawRecord,
    IngestionRunDetail,
    IngestionRunPage,
    IngestionRunQuery,
)
from lottolab.application.ports import DrawDataRepositoryFactory
from lottolab.domain.draws import LotteryType


class ListDraws:
    def __init__(self, repository_factory: DrawDataRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, query: DrawHistoryQuery) -> DrawHistoryPage:
        return self._repository_factory().list_draws(query)


class GetDraw:
    def __init__(self, repository_factory: DrawDataRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None:
        return self._repository_factory().get_draw(lottery_type, draw_number)


class ListIngestionRuns:
    def __init__(self, repository_factory: DrawDataRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, query: IngestionRunQuery) -> IngestionRunPage:
        return self._repository_factory().list_ingestion_runs(query)


class GetIngestionRun:
    def __init__(self, repository_factory: DrawDataRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str) -> IngestionRunDetail | None:
        return self._repository_factory().get_ingestion_run(run_id)
