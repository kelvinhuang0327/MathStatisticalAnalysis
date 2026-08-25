"""Focused contract tests for the generic read-only LottoLab MCP query layer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest
from tests.fixtures.historical.builder import (
    REAL_STRATEGY_IDS,
    build_baseline_envelope,
    envelope_bytes,
)

from lottolab.application.historical_queries import (
    HistoricalDrawIdentity,
    HistoricalPortfolioRecord,
    HistoricalReplayPage,
    HistoricalReplayQuery,
    HistoricalResultsUnavailableError,
    HistoricalRunPage,
    HistoricalRunQuery,
    HistoricalRunSummary,
    HistoricalStrategySummary,
    HistoricalStrategySummaryList,
    HistoricalTicketRecord,
)
from lottolab.application.lottolab_mcp import (
    AUTHORITY_UNRESOLVED,
    INVALID_LOTTERY_TYPE,
    MULTIPLE_AUTHORITIES_REQUIRES_SELECTION,
    STORAGE_UNAVAILABLE,
    LottoLabMcpQueryError,
    LottoLabMcpQueryService,
    ReadOnlyHistoricalSources,
)
from lottolab.application.p638_historical import (
    P638ReplayPage,
    P638ReplayQuery,
    P638ReplayRecord,
    P638StrategyPage,
    P638StrategyRecord,
    P638TicketRecord,
)
from lottolab.application.ports import (
    HistoricalResultQueryRepository,
    P638HistoricalQueryRepository,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_results import HistoricalRunStatus
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
    SQLiteHistoricalResultRepository,
)
from lottolab.interfaces.mcp.server import (
    HISTORICAL_RESULTS_DB_ENV,
    LottoLabMcpServer,
    build_production_service,
)
from lottolab.normalization.historical_import import verify_and_normalize_historical_import


def _draw(
    draw_number: str,
    draw_date: str,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
) -> HistoricalDrawIdentity:
    return HistoricalDrawIdentity(
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=main_numbers,
        special_numbers=special_numbers,
        draw_sha256="a" * 64,
    )


def _ticket(
    position: int,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
    main_hit_count: int,
    special_hit: bool,
) -> HistoricalTicketRecord:
    return HistoricalTicketRecord(
        portfolio_position=position,
        main_numbers=main_numbers,
        special_numbers=special_numbers,
        main_hit_count=main_hit_count,
        special_hit=special_hit,
        ticket_sha256="b" * 64,
        legacy_row_id=None,
        legacy_storage_bet_index=None,
    )


def _portfolio(
    lottery_type: LotteryType,
    *,
    draw_number: str = "100",
    tickets: tuple[HistoricalTicketRecord, ...],
) -> HistoricalPortfolioRecord:
    if lottery_type is LotteryType.DAILY_539:
        main_numbers = (1, 2, 3, 4, 5)
        special_numbers: tuple[int, ...] = ()
    elif lottery_type is LotteryType.POWER_LOTTO:
        main_numbers = (1, 2, 3, 4, 5, 6)
        special_numbers = (7,)
    else:
        main_numbers = (1, 2, 3, 4, 5, 6)
        special_numbers = (7,)
    target = _draw(draw_number, "2026-01-01", main_numbers, special_numbers)
    cutoff = _draw("99", "2025-12-30", main_numbers, special_numbers)
    return HistoricalPortfolioRecord(
        portfolio_id=f"portfolio-{lottery_type.value}-{draw_number}",
        run_id=f"run-{lottery_type.value}",
        strategy_snapshot_id="snapshot-strategy-1",
        strategy_id="strategy-1",
        effective_strategy_id="strategy-1",
        strategy_version="v1",
        replicate=1,
        constructor_identifier="SYNTHETIC_TEST_ONLY",
        source_record_locator=None,
        portfolio_sha256="c" * 64,
        prefix10_sha256="d" * 64,
        prefix15_sha256="e" * 64,
        target_draw=target,
        cutoff_draw=cutoff,
        requested_ticket_count=20,
        m4plus=False,
        tickets=tickets,
    )


def _run(lottery_type: LotteryType, run_id: str | None = None) -> HistoricalRunSummary:
    selected_run_id = run_id or f"run-{lottery_type.value}"
    return HistoricalRunSummary(
        run_id=selected_run_id,
        import_identity_sha256=f"{selected_run_id:<64}"[:64].replace(" ", "0"),
        manifest_sha256="1" * 64,
        contract_version="1.0.0",
        source_kind="SYNTHETIC_TEST_ONLY",
        source_repository="tests",
        source_commit_oid="2" * 40,
        source_artifact_sha256="3" * 64,
        dataset_identity="synthetic",
        dataset_sha256="4" * 64,
        legacy_run_id=None,
        lottery_type=lottery_type.value,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-02T00:00:00Z",
        status=HistoricalRunStatus.COMPLETED.value,
        strategy_count=1,
        draw_count=1,
        portfolio_count=1,
    )


class _FakeHistoricalRepository:
    def __init__(
        self,
        runs: tuple[HistoricalRunSummary, ...],
        portfolios: tuple[HistoricalPortfolioRecord, ...],
        draw: HistoricalDrawIdentity,
    ) -> None:
        self._runs = runs
        self._portfolios = portfolios
        self._draw = draw

    def list_runs(self, query: HistoricalRunQuery) -> HistoricalRunPage:
        selected = tuple(
            item
            for item in self._runs
            if query.lottery_type is None or item.lottery_type == query.lottery_type.value
        )
        return HistoricalRunPage(
            items=selected[query.offset : query.offset + query.limit],
            total_count=len(selected),
            limit=query.limit,
            offset=query.offset,
        )

    def get_draw(self, run_id: str, draw_number: str) -> HistoricalDrawIdentity | None:
        if run_id == self._runs[0].run_id and draw_number == self._draw.draw_number:
            return self._draw
        return None

    def list_strategies(
        self, run_id: str, *, ticket_count: int
    ) -> HistoricalStrategySummaryList | None:
        if run_id != self._runs[0].run_id:
            return None
        return HistoricalStrategySummaryList(
            run_id=run_id,
            ticket_count=ticket_count,
            items=(
                HistoricalStrategySummary(
                    strategy_snapshot_id="snapshot-strategy-1",
                    strategy_id="strategy-1",
                    effective_strategy_id="strategy-1",
                    strategy_version="v1",
                    replicate=1,
                    identity_kind="SYNTHETIC_TEST_ONLY",
                    governance_status="UNKNOWN",
                    alias_of_strategy_id=None,
                    equivalence_group=None,
                    nested_prefix_supported=True,
                    ticket_count=ticket_count,
                    evaluated_draws=len(self._portfolios),
                    complete_portfolios=len(self._portfolios),
                    m4plus_hit_count=0,
                ),
            ),
        )

    def list_replay_portfolios(
        self, run_id: str, query: HistoricalReplayQuery
    ) -> HistoricalReplayPage | None:
        if run_id != self._runs[0].run_id:
            return None
        selected = tuple(item for item in self._portfolios if item.strategy_id == query.strategy_id)
        return HistoricalReplayPage(
            run_id=run_id,
            strategy_id=query.strategy_id,
            ticket_count=query.ticket_count,
            items=selected[query.offset : query.offset + query.limit],
            total_count=len(selected),
            limit=query.limit,
            offset=query.offset,
        )

    def get_portfolio(
        self, portfolio_id: str, *, ticket_count: int
    ) -> HistoricalPortfolioRecord | None:
        del ticket_count
        return next((item for item in self._portfolios if item.portfolio_id == portfolio_id), None)


class _FakeP638Repository:
    def __init__(self) -> None:
        ticket = P638TicketRecord(
            ticket_id="p638-ticket-1",
            ticket_position=1,
            predicted_zone1_numbers=(1, 2, 3, 4, 5, 6),
            predicted_zone2_number=7,
            actual_zone1_numbers=(1, 2, 3, 4, 5, 6),
            actual_zone2_number=7,
            zone1_hit_count=6,
            zone2_hit=True,
            status="COMPLETE",
            source_run_id="p638-source",
            source_replay_sha256="a" * 64,
            source_record_locator=None,
            second_zone_ssot_version="p638-test-v1",
            provenance="SYNTHETIC_TEST_ONLY",
        )
        self._strategy = P638StrategyRecord(
            strategy_snapshot_id="p638-snapshot-1",
            run_id="run-POWER_LOTTO",
            strategy_id="strategy-1",
            display_label="P638 synthetic strategy",
            strategy_version="p638-v1",
            executable=False,
            adapter_path=None,
            native_ticket_count=1,
            min_history=None,
            zone1_contract="6-of-38",
            zone2_contract="1-of-8",
            lifecycle_status="HISTORICAL_ONLY",
            replay_status="R4_RESULT_REUSABLE",
            source_run_id="p638-source",
            source_replay_sha256="b" * 64,
            source_paths=(),
            provenance="SYNTHETIC_TEST_ONLY",
            exclusion_reason=None,
            complete_target_count=1,
            excluded_target_count=0,
            failed_target_count=0,
            ticket_count=1,
            zone1_hit_distribution=((6, 1),),
            zone2_hit_distribution=((1, 1),),
            first_draw_number="100",
            first_draw_date="2026-01-01",
            last_draw_number="100",
            last_draw_date="2026-01-01",
        )
        self._replay = P638ReplayRecord(
            target_id="p638-target-1",
            run_id="run-POWER_LOTTO",
            strategy_snapshot_id="p638-snapshot-1",
            strategy_id="strategy-1",
            strategy_version="p638-v1",
            target_draw_number="100",
            target_draw_date="2026-01-01",
            history_boundary_draw_number="99",
            history_boundary_date="2025-12-30",
            history_length=100,
            expected_ticket_count=1,
            status="COMPLETE",
            exclusion_reason=None,
            failure_reason=None,
            actual_zone1_numbers=(1, 2, 3, 4, 5, 6),
            actual_zone2_number=7,
            source_target_locator=None,
            source_run_id="p638-source",
            source_replay_sha256="b" * 64,
            provenance="SYNTHETIC_TEST_ONLY",
            tickets=(ticket,),
        )

    def list_strategies(
        self, run_id: str, *, limit: int, offset: int
    ) -> P638StrategyPage | None:
        if run_id != "run-POWER_LOTTO":
            return None
        return P638StrategyPage(
            run_id=run_id,
            items=(self._strategy,),
            total_count=1,
            limit=limit,
            offset=offset,
        )

    def list_replay(self, run_id: str, query: P638ReplayQuery) -> P638ReplayPage | None:
        if run_id != "run-POWER_LOTTO":
            return None
        return P638ReplayPage(
            run_id=run_id,
            items=(self._replay,),
            total_count=1,
            limit=query.limit,
            offset=query.offset,
        )


def _service(
    lottery_type: LotteryType,
    *,
    runs: tuple[HistoricalRunSummary, ...] | None = None,
    portfolios: tuple[HistoricalPortfolioRecord, ...] | None = None,
) -> LottoLabMcpQueryService:
    selected_portfolios: tuple[HistoricalPortfolioRecord, ...] = (
        portfolios if portfolios is not None else ()
    )
    if selected_portfolios:
        selected_draw = selected_portfolios[0].target_draw
    elif lottery_type is LotteryType.DAILY_539:
        selected_draw = _draw("100", "2026-01-01", (1, 2, 3, 4, 5), ())
    else:
        selected_draw = _draw("100", "2026-01-01", (1, 2, 3, 4, 5, 6), (7,))
    repository = _FakeHistoricalRepository(
        runs or (_run(lottery_type),),
        selected_portfolios,
        selected_draw,
    )

    def factory() -> HistoricalResultQueryRepository:
        return repository

    return LottoLabMcpQueryService(
        ReadOnlyHistoricalSources(generic_factory=factory),
        strategy_name_resolver=lambda strategy_id: "Synthetic strategy",
    )


def test_unconfigured_server_exposes_only_canonical_read_only_tools() -> None:
    service = build_production_service({HISTORICAL_RESULTS_DB_ENV: ""})
    response = LottoLabMcpServer(service).dispatch(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )

    assert response is not None
    raw_result = response.get("result")
    assert isinstance(raw_result, dict)
    typed_result = cast(dict[str, object], raw_result)
    raw_tools = typed_result.get("tools")
    assert isinstance(raw_tools, list)
    names: set[str] = set()
    for item in cast(list[object], raw_tools):
        if isinstance(item, dict):
            name = cast(dict[str, object], item).get("name")
            if isinstance(name, str):
                names.add(name)
    assert names == {
        "list_lottery_types",
        "list_historical_runs",
        "get_strategy_window_ranking",
        "get_strategy_replay_summary",
        "get_strategy_match_summary",
        "get_strategies_by_match_threshold",
        "get_strategy_best_prize",
        "get_draw",
    }
    serialized = str(response)
    assert "database" not in serialized
    assert "sql" not in serialized.lower()


@pytest.mark.parametrize("forbidden_argument", ["database_path", "sql", "filesystem_path"])
def test_server_rejects_arbitrary_storage_arguments(forbidden_argument: str) -> None:
    service = _service(LotteryType.BIG_LOTTO)
    response = LottoLabMcpServer(service).dispatch(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "get_draw",
                "arguments": {
                    "lottery_type": LotteryType.BIG_LOTTO.value,
                    "draw_number": "100",
                    forbidden_argument: "/owner/private.db"
                    if forbidden_argument != "sql"
                    else "SELECT * FROM draws",
                },
            },
        }
    )

    assert response is not None
    result = cast(dict[str, object], response["result"])
    assert result["isError"] is True
    assert "INVALID_ARGUMENTS" in str(response)
    assert "/owner/private.db" not in str(response)
    assert "SELECT * FROM draws" not in str(response)


def test_invalid_lottery_type_is_fail_closed() -> None:
    service = _service(LotteryType.BIG_LOTTO)
    with pytest.raises(LottoLabMcpQueryError) as error:
        service.list_historical_runs(lottery_type="NOT_CANONICAL")
    assert error.value.code == INVALID_LOTTERY_TYPE


def test_multiple_authorities_require_exact_selection() -> None:
    first = _run(LotteryType.BIG_LOTTO, "run-a")
    second = _run(LotteryType.BIG_LOTTO, "run-b")
    portfolio = _portfolio(
        LotteryType.BIG_LOTTO,
        tickets=(_ticket(1, (1, 2, 3, 10, 11, 12), (7,), 3, True),),
    )
    service = _service(
        LotteryType.BIG_LOTTO,
        runs=(first, second),
        portfolios=(portfolio,),
    )

    with pytest.raises(LottoLabMcpQueryError) as error:
        service.get_strategy_replay_summary(
            lottery_type=LotteryType.BIG_LOTTO.value,
            strategy_id="strategy-1",
        )
    assert error.value.code == MULTIPLE_AUTHORITIES_REQUIRES_SELECTION
    selected = service.get_strategy_replay_summary(
        lottery_type=LotteryType.BIG_LOTTO.value,
        strategy_id="strategy-1",
        authority="run-a",
    )
    authority = cast(dict[str, object], selected["authority"])
    assert authority["run_id"] == "run-a"


def test_match_summary_keeps_distinct_draws_separate_from_ticket_hits() -> None:
    portfolio = _portfolio(
        LotteryType.BIG_LOTTO,
        tickets=(
            _ticket(1, (1, 2, 3, 10, 11, 12), (7,), 3, True),
            _ticket(2, (1, 2, 3, 13, 14, 15), (8,), 3, False),
        ),
    )
    result = _service(LotteryType.BIG_LOTTO, portfolios=(portfolio,)).get_strategy_match_summary(
        lottery_type=LotteryType.BIG_LOTTO.value,
        strategy_id="strategy-1",
        min_main_matches=3,
    )

    assert result["threshold_distinct_draw_count"] == 1
    assert result["threshold_ticket_hit_count"] == 2
    distribution = cast(list[dict[str, object]], result["exact_main_match_distribution"])
    assert {row["special_hit"] for row in distribution} == {
        True,
        False,
    }


@pytest.mark.parametrize(
    ("lottery_type", "main_numbers", "special_numbers", "ticket_special", "expected_special"),
    [
        (LotteryType.BIG_LOTTO, (1, 2, 3, 4, 5, 6), (7,), (8,), False),
        (LotteryType.POWER_LOTTO, (1, 2, 3, 4, 5, 6), (7,), (7,), True),
        (LotteryType.DAILY_539, (1, 2, 3, 4, 5), (), (), None),
    ],
)
def test_best_prize_uses_each_lottery_canonical_evaluator(
    lottery_type: LotteryType,
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
    ticket_special: tuple[int, ...],
    expected_special: bool | None,
) -> None:
    portfolio = _portfolio(
        lottery_type,
        tickets=(
            _ticket(1, main_numbers, ticket_special, len(main_numbers), bool(ticket_special)),
        ),
    )
    result = _service(lottery_type, portfolios=(portfolio,)).get_strategy_best_prize(
        lottery_type=lottery_type.value,
        strategy_id="strategy-1",
    )

    assert result["highest_official_prize"] is not None
    match = cast(dict[str, object], result["canonical_match_information"])
    assert match["special_match"] is expected_special
    assert match["secondary_match"] is (
        expected_special if lottery_type is LotteryType.POWER_LOTTO else None
    )


def test_power_lotto_prefers_existing_p638_replay_projection() -> None:
    generic_portfolio = _portfolio(
        LotteryType.POWER_LOTTO,
        tickets=(_ticket(1, (30, 31, 32, 33, 34, 35), (1,), 0, False),),
    )
    generic_repository = _FakeHistoricalRepository(
        (_run(LotteryType.POWER_LOTTO),),
        (generic_portfolio,),
        generic_portfolio.target_draw,
    )
    p638_repository = _FakeP638Repository()

    def generic_factory() -> HistoricalResultQueryRepository:
        return generic_repository

    def p638_factory() -> P638HistoricalQueryRepository:
        return cast(P638HistoricalQueryRepository, p638_repository)

    service = LottoLabMcpQueryService(
        ReadOnlyHistoricalSources(
            generic_factory=generic_factory,
            p638_factory=p638_factory,
        )
    )
    result = service.get_strategy_best_prize(
        lottery_type=LotteryType.POWER_LOTTO.value,
        strategy_id="strategy-1",
    )

    prize = cast(dict[str, object], result["highest_official_prize"])
    assert prize["prize_tier"] == "FIRST"


def test_querying_existing_repository_does_not_change_database_bytes(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    normalized = verify_and_normalize_historical_import(
        envelope_bytes(build_baseline_envelope())
    )
    assert normalized.normalized_import is not None
    committed = SQLiteHistoricalResultRepository(database).commit_import(
        normalized.normalized_import
    )
    assert committed.status is HistoricalRunStatus.COMPLETED
    before = database.read_bytes()
    before_size = database.stat().st_size
    before_mtime_ns = database.stat().st_mtime_ns
    repository = SQLiteHistoricalResultQueryRepository(database)

    def factory() -> HistoricalResultQueryRepository:
        return repository

    service = LottoLabMcpQueryService(ReadOnlyHistoricalSources(generic_factory=factory))
    service.list_lottery_types()
    service.list_historical_runs(lottery_type=LotteryType.BIG_LOTTO.value)
    service.get_draw(lottery_type=LotteryType.BIG_LOTTO.value, draw_number="105")
    service.get_strategy_replay_summary(
        lottery_type=LotteryType.BIG_LOTTO.value,
        strategy_id=REAL_STRATEGY_IDS[0],
    )
    assert database.read_bytes() == before
    assert database.stat().st_size == before_size
    assert database.stat().st_mtime_ns == before_mtime_ns
    assert hashlib.sha256(database.read_bytes()).hexdigest() == hashlib.sha256(before).hexdigest()


def test_missing_historical_storage_is_not_reported_as_empty_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing" / "historical.db"
    repository = SQLiteHistoricalResultQueryRepository(database)

    with pytest.raises(HistoricalResultsUnavailableError):
        repository.list_runs(HistoricalRunQuery())

    def factory() -> HistoricalResultQueryRepository:
        return repository

    response = LottoLabMcpServer(
        LottoLabMcpQueryService(ReadOnlyHistoricalSources(generic_factory=factory))
    ).dispatch(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "list_historical_runs",
                "arguments": {"lottery_type": LotteryType.BIG_LOTTO.value},
            },
        }
    )

    assert response is not None
    result = cast(dict[str, object], response["result"])
    assert result["isError"] is True
    content = cast(list[object], result["content"])
    text = cast(dict[str, object], content[0])["text"]
    payload = cast(dict[str, object], json.loads(cast(str, text)))
    assert payload == {
        "details": {},
        "error_code": STORAGE_UNAVAILABLE,
        "message": "Historical Results storage is unavailable.",
    }
    assert str(database) not in str(response)
    assert "items" not in payload


def test_unresolved_authority_is_structured_without_leaking_path(tmp_path: Path) -> None:
    configured_path = tmp_path / "missing.db"
    service = build_production_service({HISTORICAL_RESULTS_DB_ENV: str(configured_path)})
    server = LottoLabMcpServer(service)
    packaged_response = server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "list_historical_runs",
                "arguments": {"lottery_type": LotteryType.BIG_LOTTO.value},
            },
        }
    )

    assert packaged_response is not None
    assert "isError" not in cast(dict[str, object], packaged_response["result"])
    assert "big-lotto-packaged-records" in str(packaged_response)

    unresolved_response = server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_historical_runs",
                "arguments": {
                    "lottery_type": LotteryType.POWER_LOTTO.value,
                    "authority": "POWER_LOTTO_HISTORICAL_RESULTS_V2",
                },
            },
        }
    )

    assert unresolved_response is not None
    assert unresolved_response["result"]["isError"] is True  # type: ignore[index]
    assert "AUTHORITY_UNRESOLVED" in str(unresolved_response)
    assert str(configured_path) not in str(packaged_response)
    assert str(configured_path) not in str(unresolved_response)


def test_absent_historical_configuration_does_not_fallback_to_draw_data(
    tmp_path: Path,
) -> None:
    server = LottoLabMcpServer(
        build_production_service({"LOTTOLAB_DATA_DIR": str(tmp_path)})
    )
    response = server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "list_historical_runs",
                "arguments": {
                    "lottery_type": LotteryType.POWER_LOTTO.value,
                    "authority": "POWER_LOTTO_HISTORICAL_RESULTS_V2",
                },
            },
        }
    )

    assert response is not None
    result = cast(dict[str, object], response["result"])
    assert result["isError"] is True
    content = cast(list[object], result["content"])
    text = cast(dict[str, object], content[0])["text"]
    payload = cast(dict[str, object], json.loads(cast(str, text)))
    assert payload["error_code"] == AUTHORITY_UNRESOLVED
    assert payload["details"] == {"capability": "POWER_LOTTO_HISTORICAL_RESULTS_V2"}
    assert "items" not in payload
    assert str(tmp_path) not in str(response)
