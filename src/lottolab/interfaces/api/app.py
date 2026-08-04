"""FastAPI application factory.

Run locally:
    uv run uvicorn --factory lottolab.interfaces.api.app:create_app --reload
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from lottolab.application.ports import (
    B649MultiTicketRecordReaderFactory,
    DrawDataProviderFactory,
    HistoricalPrefixSuccessWindowSourceReaderFactory,
    HistoricalResultQueryRepositoryFactory,
    ReplayScoringProjectionReaderFactory,
    StrategyEvidenceRegistryReader,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    build_production_generate_one_bet,
)
from lottolab.application.use_cases.generate_live_zone_split_bets import (
    GenerateLiveZoneSplitBets,
    build_production_generate_live_zone_split_bets,
)
from lottolab.application.use_cases.historical_draw_import import HistoricalDrawImportService
from lottolab.domain.biglotto_full_strategy_catalog import load_full_strategy_catalog
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    PackagedB649MultiTicketRecordReader,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.infrastructure.strategy_evidence_registry import (
    CommittedStrategyEvidenceRegistry,
)
from lottolab.interfaces.api.b649_multi_ticket_records import (
    create_b649_multi_ticket_records_router,
)
from lottolab.interfaces.api.draw_data import (
    ApiValidationErrorResponse,
    RequestValidationIssueView,
    create_draw_data_router,
)
from lottolab.interfaces.api.generate_bet import create_generate_bet_router
from lottolab.interfaces.api.historical_draw_imports import (
    create_historical_draw_import_router,
)
from lottolab.interfaces.api.historical_prefix_analytics import (
    HistoricalPrefixAnalyticsResultProvider,
    create_historical_prefix_analytics_router,
)
from lottolab.interfaces.api.historical_prefix_success_windows import (
    create_historical_prefix_success_windows_router,
)
from lottolab.interfaces.api.historical_results import create_historical_results_router
from lottolab.interfaces.api.live_zone_split import create_live_zone_split_router
from lottolab.interfaces.api.replay_portfolio_rankings import (
    create_replay_portfolio_rankings_router,
)
from lottolab.interfaces.api.replay_scoring_projections import (
    create_replay_scoring_projections_router,
)
from lottolab.interfaces.api.strategy_catalog import (
    API_VERSION,
    create_strategy_catalog_router,
)
from lottolab.interfaces.api.strategy_evidence import create_strategy_evidence_router
from lottolab.strategies.catalog import StrategyCatalog, production_catalog

LocalDataPathsProvider = Callable[[], LocalDataPaths]


def create_app(
    catalog: StrategyCatalog | None = None,
    data_paths_provider: LocalDataPathsProvider | None = None,
    generate_one_bet: GenerateOneBet | None = None,
    generate_live_zone_split_bets: GenerateLiveZoneSplitBets | None = None,
    historical_query_repository_factory: HistoricalResultQueryRepositoryFactory | None = None,
    historical_prefix_analytics_result_provider: (
        HistoricalPrefixAnalyticsResultProvider | None
    ) = None,
    replay_scoring_projection_reader_factory: (
        ReplayScoringProjectionReaderFactory | None
    ) = None,
    historical_prefix_success_window_source_reader_factory: (
        HistoricalPrefixSuccessWindowSourceReaderFactory | None
    ) = None,
    draw_data_provider_factory: DrawDataProviderFactory | None = None,
    strategy_evidence_registry_reader: StrategyEvidenceRegistryReader | None = None,
    b649_multi_ticket_record_reader_factory: (
        B649MultiTicketRecordReaderFactory | None
    ) = None,
    historical_draw_import_service: HistoricalDrawImportService | None = None,
) -> FastAPI:
    app = FastAPI(title="LottoLab API", version="0.1.0")
    resolved_catalog = catalog if catalog is not None else production_catalog()
    resolved_paths_provider = (
        data_paths_provider if data_paths_provider is not None else resolve_local_data_paths
    )
    resolved_generate_one_bet = (
        generate_one_bet if generate_one_bet is not None else build_production_generate_one_bet()
    )
    resolved_generate_live_zone_split_bets = (
        generate_live_zone_split_bets
        if generate_live_zone_split_bets is not None
        else build_production_generate_live_zone_split_bets()
    )
    resolved_strategy_evidence_registry = (
        strategy_evidence_registry_reader
        if strategy_evidence_registry_reader is not None
        else CommittedStrategyEvidenceRegistry.default()
    )
    resolved_b649_reader_factory = (
        b649_multi_ticket_record_reader_factory
        if b649_multi_ticket_record_reader_factory is not None
        else PackagedB649MultiTicketRecordReader
    )

    def repository_factory() -> SQLiteDrawDataRepository:
        return SQLiteDrawDataRepository(resolved_paths_provider())

    @app.exception_handler(RequestValidationError)
    async def sanitized_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del request
        fields = [
            RequestValidationIssueView(
                location=".".join(str(part) for part in issue.get("loc", ())),
                type=str(issue.get("type", "validation_error")),
            )
            for issue in error.errors()
        ]
        response = ApiValidationErrorResponse(
            error_code="REQUEST_VALIDATION_FAILED",
            message="Request validation failed.",
            fields=fields,
        )
        return JSONResponse(
            status_code=422,
            content=response.model_dump(mode="json"),
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "api_version": API_VERSION}

    app.include_router(create_strategy_catalog_router(resolved_catalog))
    app.include_router(
        create_b649_multi_ticket_records_router(
            load_full_strategy_catalog(),
            resolved_b649_reader_factory,
        )
    )
    app.include_router(
        create_strategy_evidence_router(
            resolved_catalog,
            resolved_strategy_evidence_registry,
        )
    )
    app.include_router(
        create_draw_data_router(
            repository_factory,
            provider_factory=draw_data_provider_factory,
        )
    )
    app.include_router(create_generate_bet_router(resolved_generate_one_bet))
    app.include_router(create_live_zone_split_router(resolved_generate_live_zone_split_bets))
    app.include_router(create_historical_results_router(historical_query_repository_factory))
    app.include_router(create_historical_draw_import_router(historical_draw_import_service))
    app.include_router(
        create_historical_prefix_analytics_router(
            historical_prefix_analytics_result_provider
        )
    )
    app.include_router(
        create_historical_prefix_success_windows_router(
            historical_prefix_success_window_source_reader_factory
        )
    )
    app.include_router(
        create_replay_portfolio_rankings_router(replay_scoring_projection_reader_factory)
    )
    app.include_router(
        create_replay_scoring_projections_router(
            replay_scoring_projection_reader_factory
        )
    )

    return app
