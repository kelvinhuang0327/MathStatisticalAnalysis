"""SQLite integration proof for target-atomic resumable research backtests."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from lottolab.application.research_backtest_runner import (
    BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1,
    BigLottoResearchBacktestManifest,
    RunBigLottoResearchBacktest,
)
from lottolab.application.research_store import (
    CompletedTargetCursor,
    QueryPage,
    ResearchStore,
    RunProgress,
    StrategySnapshotInput,
    TargetCommitInput,
    TargetCommitResult,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetReason,
    GenerateOneBetResult,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioResult,
    GeneratePortfolioStatus,
)
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    GenerateOrderedCandidateEmission,
    GenerateOrderedCandidateEmissionInput,
    GenerateOrderedCandidateEmissionResult,
    GenerateOrderedPortfolioEmission,
    GenerateOrderedPortfolioEmissionInput,
    GenerateOrderedPortfolioEmissionResult,
    build_production_generate_ordered_candidate_emission,
    build_production_generate_ordered_portfolio_emission,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    BigLottoPrizeTier,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.domain.research import (
    ResearchExecutionStatus,
    ResearchRunKind,
    ResearchRunStatus,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.ordered_candidate_materialization_reader import (
    SQLiteOrderedCandidateMaterializationReader,
)
from lottolab.infrastructure.persistence.repositories import (
    SQLiteDrawDataRepository,
)
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    RESEARCH_DATABASE_FILENAME,
    ResearchDataPaths,
    open_database,
)
from lottolab.infrastructure.strategy_source_provenance import (
    PythonStrategySourceIdentityResolver,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

ROOT = Path(__file__).resolve().parents[2]
_COMMIT = "c" * 40
_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_STRATEGIES = (
    "biglotto_social_wisdom_anti_popularity",
    "biglotto_zone_split_3bet_bet1",
)
_PORTFOLIO_STRATEGY = "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4"
_PORTFOLIO_NATIVE_TICKET_COUNT = 5


class _RecordingGenerate(GenerateOrderedCandidateEmission):
    def __init__(self, delegate: GenerateOrderedCandidateEmission) -> None:
        self.delegate = delegate
        self.calls: list[tuple[str, str]] = []

    def execute(
        self,
        request: GenerateOrderedCandidateEmissionInput,
    ) -> GenerateOrderedCandidateEmissionResult:
        self.calls.append((request.target_draw, request.strategy_id))
        return self.delegate.execute(request)


class _FixedGenerate(GenerateOrderedCandidateEmission):
    def __init__(self, status: GenerateOneBetStatus) -> None:
        self.status = status

    def execute(
        self,
        request: GenerateOrderedCandidateEmissionInput,
    ) -> GenerateOrderedCandidateEmissionResult:
        reason_by_status = {
            GenerateOneBetStatus.REJECTED: (
                GenerateOneBetReason.REJECTED_BY_STRATEGY
            ),
            GenerateOneBetStatus.INSUFFICIENT_HISTORY: (
                GenerateOneBetReason.INSUFFICIENT_HISTORY
            ),
            GenerateOneBetStatus.STRATEGY_UNAVAILABLE: (
                GenerateOneBetReason.ADAPTER_NOT_INJECTED
            ),
            GenerateOneBetStatus.INVALID_OUTPUT: (
                GenerateOneBetReason.INVALID_OUTPUT
            ),
            GenerateOneBetStatus.REPLAY_ERROR: GenerateOneBetReason.REPLAY_ERROR,
            GenerateOneBetStatus.WRONG_RESPONSE_PATH: (
                GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
            ),
        }
        return GenerateOrderedCandidateEmissionResult(
            legal_bet=GenerateOneBetResult(
                status=self.status,
                numbers=None,
                special_number=None,
                reason_code=reason_by_status[self.status],
            ),
            emission=None,
        )


class _RaisingGenerate(GenerateOrderedCandidateEmission):
    def __init__(self) -> None:
        pass

    def execute(
        self,
        request: GenerateOrderedCandidateEmissionInput,
    ) -> GenerateOrderedCandidateEmissionResult:
        raise RuntimeError("sensitive fixture detail")


class _RecordingPortfolioGenerate(GenerateOrderedPortfolioEmission):
    def __init__(self, delegate: GenerateOrderedPortfolioEmission) -> None:
        self.delegate = delegate
        self.calls: list[tuple[str, str]] = []

    def execute(
        self,
        request: GenerateOrderedPortfolioEmissionInput,
    ) -> GenerateOrderedPortfolioEmissionResult:
        self.calls.append((request.target_draw, request.strategy_id))
        return self.delegate.execute(request)


class _FixedPortfolioGenerate(GenerateOrderedPortfolioEmission):
    def __init__(self, status: GeneratePortfolioStatus) -> None:
        self.status = status

    def execute(
        self,
        request: GenerateOrderedPortfolioEmissionInput,
    ) -> GenerateOrderedPortfolioEmissionResult:
        reason_by_status = {
            GeneratePortfolioStatus.INSUFFICIENT_HISTORY: (
                GeneratePortfolioReason.INSUFFICIENT_HISTORY
            ),
            GeneratePortfolioStatus.STRATEGY_UNAVAILABLE: (
                GeneratePortfolioReason.ADAPTER_NOT_INJECTED
            ),
            GeneratePortfolioStatus.INVALID_OUTPUT: (
                GeneratePortfolioReason.INVALID_OUTPUT
            ),
            GeneratePortfolioStatus.REPLAY_ERROR: (
                GeneratePortfolioReason.REPLAY_ERROR
            ),
            GeneratePortfolioStatus.WRONG_RESPONSE_PATH: (
                GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO
            ),
        }
        return GenerateOrderedPortfolioEmissionResult(
            legal_bets=GeneratePortfolioResult(
                status=self.status,
                numbers=None,
                special_number=None,
                reason_code=reason_by_status[self.status],
            ),
            emissions=None,
        )


class _RaisingPortfolioGenerate(GenerateOrderedPortfolioEmission):
    def __init__(self) -> None:
        pass

    def execute(
        self,
        request: GenerateOrderedPortfolioEmissionInput,
    ) -> GenerateOrderedPortfolioEmissionResult:
        raise RuntimeError("sensitive fixture detail")


class _FixedOkPortfolioGenerate(GenerateOrderedPortfolioEmission):
    """Force a specific OK native ticket set without an injected adapter."""

    def __init__(
        self,
        ticket_numbers: tuple[tuple[int, ...], ...],
        *,
        emitted_numbers: tuple[tuple[int, ...], ...] | None = None,
    ) -> None:
        self.ticket_numbers = ticket_numbers
        self.emitted_numbers = emitted_numbers or ticket_numbers

    def execute(
        self,
        request: GenerateOrderedPortfolioEmissionInput,
    ) -> GenerateOrderedPortfolioEmissionResult:
        emissions = tuple(
            OrderedCandidateEmission(
                schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
                lottery_type=request.lottery_type,
                strategy_id=request.strategy_id,
                strategy_version="test-fixture-v1",
                replicate=request.replicate,
                target_draw=request.target_draw,
                history_cutoff=request.history_cutoff,
                emitted_main_numbers=emitted,
                auxiliary_operand_kind=AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
                auxiliary_operand_availability=(
                    AuxiliaryOperandAvailability.EXPLICITLY_MISSING
                ),
                auxiliary_operand_value=None,
            )
            for emitted in self.emitted_numbers
        )
        return GenerateOrderedPortfolioEmissionResult(
            legal_bets=GeneratePortfolioResult(
                status=GeneratePortfolioStatus.OK,
                numbers=tuple(
                    tuple(sorted(numbers)) for numbers in self.ticket_numbers
                ),
                special_number=None,
                reason_code=None,
            ),
            emissions=emissions,
        )


class _PausingRepository(SQLiteResearchRepository):
    def __init__(
        self,
        paths: ResearchDataPaths,
        stop: Event,
        *,
        pause_after: int,
    ) -> None:
        super().__init__(paths)
        self._stop = stop
        self._pause_after = pause_after
        self._commits = 0

    def commit_target(
        self,
        value: TargetCommitInput,
        *,
        idempotency_key: str,
    ) -> TargetCommitResult:
        result = super().commit_target(
            value,
            idempotency_key=idempotency_key,
        )
        self._commits += 1
        if self._commits == self._pause_after:
            self._stop.set()
        return result


class _FailFirstCommitRepository(SQLiteResearchRepository):
    def __init__(self, paths: ResearchDataPaths) -> None:
        super().__init__(paths)
        self.failed = False

    def commit_target(
        self,
        value: TargetCommitInput,
        *,
        idempotency_key: str,
    ) -> TargetCommitResult:
        if not self.failed:
            self.failed = True
            raise RuntimeError("injected target transaction failure")
        return super().commit_target(
            value,
            idempotency_key=idempotency_key,
        )


class _ConflictingProvenanceRepository(SQLiteResearchRepository):
    def register_strategy_snapshot(
        self,
        run_id: str,
        value: StrategySnapshotInput,
        *,
        idempotency_key: str,
        snapshot_id: str | None = None,
    ) -> str:
        return super().register_strategy_snapshot(
            run_id,
            replace(value, producer_version="conflicting-version"),
            idempotency_key=idempotency_key,
            snapshot_id=snapshot_id,
        )


class _BlindCompletedTargetRepository(SQLiteResearchRepository):
    """Adversarial resume view used only to force repository byte verification."""

    def __init__(
        self,
        paths: ResearchDataPaths,
        *,
        strategy_id: str,
    ) -> None:
        super().__init__(paths)
        self._strategy_id = strategy_id

    def find_progress(self, run_id: str) -> RunProgress | None:
        progress = super().find_progress(run_id)
        if progress is None:
            return None
        zero_counts = {
            status.value: 0 for status in ResearchExecutionStatus
        }
        cursor = json.dumps(
            {
                "completed_target_count": 0,
                "schema_version": "BIG_LOTTO_RESEARCH_BACKTEST_PROGRESS_V1",
                "status_counts": zero_counts,
                "strategy_status_counts": {
                    self._strategy_id: zero_counts,
                },
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return replace(
            progress,
            completed_target_count=0,
            progress_cursor=cursor,
        )

    def completed_target_keys(
        self,
        run_id: str,
        *,
        limit: int = 100,
        after: CompletedTargetCursor | None = None,
    ) -> QueryPage[tuple[str, str, str]]:
        return QueryPage(items=(), next_cursor=None)


def _draw_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "draw-data")}
    )


def _research_paths(tmp_path: Path, name: str = "research-data") -> ResearchDataPaths:
    directory = tmp_path / name
    directory.mkdir(mode=0o700)
    return ResearchDataPaths(
        directory,
        directory / RESEARCH_DATABASE_FILENAME,
    )


def _seed_draws(paths: LocalDataPaths, count: int = 8) -> None:
    rows = [_HEADER]
    for index in range(1, count + 1):
        main = "|".join(str(number) for number in range(index, index + 6))
        rows.append(
            f"BIG_LOTTO,{index},2026-01-{index:02d},{main},{index + 6},fixture"
        )
    rows.append("")
    parsed = parse_draw_csv("\n".join(rows), filename="runner-fixture.csv")
    assert parsed.is_valid, parsed.errors
    SQLiteDrawDataRepository(paths).apply_valid_import(parsed)


def _manifest(
    draw_paths: LocalDataPaths,
    *,
    targets: tuple[str, ...] = ("2", "3", "4", "5", "6"),
    strategies: tuple[str, ...] = _STRATEGIES,
    minimum: int = 2,
    maximum: int = 4,
) -> BigLottoResearchBacktestManifest:
    snapshot = SQLiteOrderedCandidateMaterializationReader(
        draw_paths
    ).read_source_snapshot(LotteryType.BIG_LOTTO)
    return BigLottoResearchBacktestManifest(
        schema_version=BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1,
        lottery_type=LotteryType.BIG_LOTTO,
        run_kind=ResearchRunKind.HISTORICAL_BACKTEST,
        dataset_id="sqlite-fixture",
        dataset_version="v1",
        expected_source_snapshot_sha256=snapshot.source_snapshot_sha256,
        target_draws=targets,
        strategy_ids=strategies,
        minimum_history_draws=minimum,
        maximum_history_draws=maximum,
        replicate=1,
    )


def _runner(
    draw_paths: LocalDataPaths,
    repository_factory: Callable[[], ResearchStore],
    *,
    generate: GenerateOrderedCandidateEmission | None = None,
    generate_portfolio: GenerateOrderedPortfolioEmission | None = None,
) -> RunBigLottoResearchBacktest:
    catalog = production_catalog()
    return RunBigLottoResearchBacktest(
        repository_factory=repository_factory,
        source_reader=SQLiteOrderedCandidateMaterializationReader(draw_paths),
        catalog=catalog,
        executable_registry=ExecutableRegistry(catalog),
        generate_ordered_candidate_emission=(
            generate
            or build_production_generate_ordered_candidate_emission()
        ),
        generate_ordered_portfolio_emission=(
            generate_portfolio
            or build_production_generate_ordered_portfolio_emission()
        ),
        source_commit_resolver=lambda: _COMMIT,
        strategy_source_identity_resolver=(
            PythonStrategySourceIdentityResolver(ROOT)
        ),
    )


def _counts(paths: ResearchDataPaths) -> dict[str, int]:
    tables = (
        "research_runs",
        "research_strategy_snapshots",
        "research_prediction_targets",
        "research_prediction_tickets",
        "research_ticket_results",
        "research_execution_closures",
        "research_run_status_events",
        "research_run_summaries",
        "research_idempotency_keys",
        "research_run_current_pointer",
    )
    with open_database(paths, read_only=True) as connection:
        return {
            table: int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            )
            for table in tables
        }


def _assert_no_sidecars(paths: ResearchDataPaths) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        assert not Path(f"{paths.database}{suffix}").exists()


def test_real_sqlite_run_persists_nonzero_cutoff_scores_and_complete_provenance(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("2", "3", "4"),
    )
    runner = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
    )

    result = runner.execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    assert result.expected_target_count == 6
    assert result.completed_target_count == 6
    assert result.targets_created == 6
    assert result.tickets_created >= 1
    assert result.results_created == result.tickets_created
    progress = SQLiteResearchRepository(
        research_paths,
        initialize=False,
    ).progress(result.run_id)
    assert progress.status is ResearchRunStatus.COMPLETED
    assert progress.completed_target_count == 6

    with open_database(research_paths, read_only=True) as connection:
        raw_status = connection.execute(
            "SELECT status FROM research_runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        latest_status = connection.execute(
            """
            SELECT status
            FROM research_run_status_events
            WHERE run_id = ?
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (result.run_id,),
        ).fetchone()
        assert raw_status == (ResearchRunStatus.RUNNING.value,)
        assert latest_status == (ResearchRunStatus.COMPLETED.value,)

        insufficient = connection.execute(
            """
            SELECT target_draw_number, history_cutoff_draw_number,
                   history_draw_count, execution_status, causal_eligible
            FROM research_prediction_targets
            WHERE target_draw_number = '2'
            ORDER BY strategy_snapshot_id
            """
        ).fetchall()
        assert len(insufficient) == 2
        assert {
            tuple(row) for row in insufficient
        } == {
            (
                "2",
                "1",
                1,
                ResearchExecutionStatus.INSUFFICIENT_HISTORY.value,
                0,
            )
        }
        assert (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM research_prediction_tickets AS ticket
                JOIN research_prediction_targets AS target
                  ON target.id = ticket.target_id
                WHERE target.target_draw_number = '2'
                """
            ).fetchone()
            == (0,)
        )
        assert (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM research_ticket_results AS result
                JOIN research_prediction_targets AS target
                  ON target.id = result.target_id
                WHERE target.target_draw_number = '2'
                """
            ).fetchone()
            == (0,)
        )
        assert (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM research_prediction_targets
                WHERE history_cutoff_draw_date >= target_draw_date
                   OR history_cutoff_draw_number = target_draw_number
                """
            ).fetchone()
            == (0,)
        )

        scored = connection.execute(
            """
            SELECT ticket.main_numbers_json,
                   target_binding.main_numbers_json,
                   target_binding.special_numbers_json,
                   result.main_hit_count,
                   result.special_hit_count,
                   result.prize_tier_id,
                   result.hit_numbers_json
            FROM research_ticket_results AS result
            JOIN research_prediction_tickets AS ticket
              ON ticket.id = result.ticket_id
            JOIN research_prediction_targets AS target
              ON target.id = result.target_id
            JOIN research_draw_bindings AS target_binding
              ON target_binding.id = target.target_draw_binding_id
            ORDER BY target.target_order
            LIMIT 1
            """
        ).fetchone()
        assert scored is not None
        predicted = tuple(json.loads(str(scored[0])))
        winning = tuple(json.loads(str(scored[1])))
        special = int(json.loads(str(scored[2]))[0])
        expected_score = score_big_lotto_ticket(
            predicted_main_numbers=predicted,
            winning_main_numbers=winning,
            winning_special_number=special,
        )
        expected_prize = resolve_big_lotto_prize_tier(
            expected_score.main_hits,
            expected_score.special_hit,
        )
        expected_prize_id = (
            expected_prize.tier_id.value
            if isinstance(expected_prize, BigLottoPrizeTier)
            else expected_prize.value
        )
        assert scored[3:] == (
            expected_score.main_hits,
            int(expected_score.special_hit),
            expected_prize_id,
            json.dumps(
                sorted(set(predicted).intersection(winning)),
                separators=(",", ":"),
            ),
        )

        provenance = connection.execute(
            """
            SELECT strategy_id, provenance_availability, source_commit_oid,
                   strategy_source_sha256, runtime_fingerprint,
                   parameters_json, parameters_sha256, seed_protocol,
                   replicate, execution_code_version,
                   governance_status, lifecycle_status
            FROM research_strategy_snapshots
            ORDER BY strategy_id
            """
        ).fetchall()
        assert len(provenance) == 2
        catalog = production_catalog()
        registry = ExecutableRegistry(catalog)
        source_resolver = PythonStrategySourceIdentityResolver(ROOT)
        for row in provenance:
            loaded_adapter = registry.load_adapter(str(row[0]))
            assert isinstance(loaded_adapter, type)
            expected_source = source_resolver.resolve(
                strategy_id=str(row[0]),
                loaded_adapter=loaded_adapter,
            )
            assert row[1] == "COMPLETE"
            assert row[2] == _COMMIT
            assert row[3] == expected_source.strategy_source_sha256
            assert isinstance(row[3], str) and len(row[3]) == 64
            assert set(str(row[3])) != {"0"}
            assert json.loads(str(row[4]))["schema_version"] == (
                "LOTTOLAB_PYTHON_RUNTIME_FINGERPRINT_V1"
            )
            assert json.loads(str(row[5]))["manifest_sha256"] == (
                manifest.manifest_sha256
            )
            assert isinstance(row[6], str) and len(row[6]) == 64
            assert row[7] == "DETERMINISTIC_HISTORY_ONLY_NO_RANDOM_SEED_V1"
            assert row[8] == 1
            assert row[9] == "1.0.0"
            assert row[10]
            assert row[11] == "ONLINE"

        assert (
            connection.execute(
                "SELECT COUNT(*) FROM research_run_current_pointer"
            ).fetchone()
            == (0,)
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM research_run_summaries"
            ).fetchone()
            == (3,)
        )

    report = SQLiteResearchRepository(
        research_paths,
        initialize=False,
    ).verify_store()
    assert report.healthy
    _assert_no_sidecars(research_paths)


def test_pause_resume_skips_completed_keys_and_completed_third_run_is_exact_no_op(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(draw_paths)
    stop = Event()
    first_generate = _RecordingGenerate(
        build_production_generate_ordered_candidate_emission()
    )
    pausing_repository = _PausingRepository(
        research_paths,
        stop,
        pause_after=5,
    )

    first = _runner(
        draw_paths,
        lambda: pausing_repository,
        generate=first_generate,
    ).execute(manifest, stop_requested=stop)

    assert first.status is ResearchRunStatus.PAUSED
    assert first.interrupted is True
    assert first.completed_target_count == 5
    assert _counts(research_paths)["research_prediction_targets"] == 5
    assert SQLiteResearchRepository(
        research_paths,
        initialize=False,
    ).progress(first.run_id).status is ResearchRunStatus.PAUSED
    _assert_no_sidecars(research_paths)

    second_generate = _RecordingGenerate(
        build_production_generate_ordered_candidate_emission()
    )
    second = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate=second_generate,
    ).execute(manifest)

    assert second.status is ResearchRunStatus.COMPLETED
    assert second.completed_target_count == 10
    assert second.targets_created == 5
    all_execution_calls = first_generate.calls + second_generate.calls
    assert len(all_execution_calls) == len(set(all_execution_calls))
    assert all(target != "2" for target, _strategy in all_execution_calls)
    completed_counts = _counts(research_paths)
    assert completed_counts["research_prediction_targets"] == 10
    with open_database(research_paths, read_only=True) as connection:
        assert (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT strategy_snapshot_id, target_draw_number, COUNT(*) AS count
                    FROM research_prediction_targets
                    GROUP BY strategy_snapshot_id, target_draw_number
                    HAVING count != 1
                )
                """
            ).fetchone()
            == (0,)
        )

    third_generate = _RecordingGenerate(
        build_production_generate_ordered_candidate_emission()
    )
    third = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate=third_generate,
    ).execute(manifest)

    assert third.status is ResearchRunStatus.COMPLETED
    assert third.idempotent_no_op is True
    assert third.targets_created == 0
    assert third.tickets_created == 0
    assert third.results_created == 0
    assert third_generate.calls == []
    assert _counts(research_paths) == completed_counts
    assert SQLiteResearchRepository(
        research_paths,
        initialize=False,
    ).verify_store().healthy
    _assert_no_sidecars(research_paths)


def test_injected_target_commit_failure_exposes_no_partial_target_and_clean_rerun(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_STRATEGIES[0],),
        minimum=1,
    )
    failing_repository = _FailFirstCommitRepository(research_paths)

    with pytest.raises(RuntimeError, match="injected target transaction failure"):
        _runner(
            draw_paths,
            lambda: failing_repository,
        ).execute(manifest)

    failed_counts = _counts(research_paths)
    assert failed_counts["research_prediction_targets"] == 0
    assert failed_counts["research_prediction_tickets"] == 0
    assert failed_counts["research_ticket_results"] == 0
    assert failed_counts["research_execution_closures"] == 0
    _assert_no_sidecars(research_paths)

    completed = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
    ).execute(manifest)

    assert completed.status is ResearchRunStatus.COMPLETED
    final_counts = _counts(research_paths)
    assert final_counts["research_prediction_targets"] == 1
    assert final_counts["research_prediction_tickets"] == 1
    assert final_counts["research_ticket_results"] == 1
    _assert_no_sidecars(research_paths)


@pytest.mark.parametrize(
    ("generated_status", "stored_status"),
    [
        (
            GenerateOneBetStatus.REJECTED,
            ResearchExecutionStatus.REJECTED,
        ),
        (
            GenerateOneBetStatus.INSUFFICIENT_HISTORY,
            ResearchExecutionStatus.INSUFFICIENT_HISTORY,
        ),
        (
            GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
            ResearchExecutionStatus.STRATEGY_UNAVAILABLE,
        ),
        (
            GenerateOneBetStatus.INVALID_OUTPUT,
            ResearchExecutionStatus.INVALID_OUTPUT,
        ),
        (
            GenerateOneBetStatus.REPLAY_ERROR,
            ResearchExecutionStatus.EXECUTION_ERROR,
        ),
        (
            GenerateOneBetStatus.WRONG_RESPONSE_PATH,
            ResearchExecutionStatus.STRATEGY_UNAVAILABLE,
        ),
    ],
)
def test_strategy_level_failures_become_typed_terminal_targets(
    tmp_path: Path,
    generated_status: GenerateOneBetStatus,
    stored_status: ResearchExecutionStatus,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_STRATEGIES[0],),
        minimum=1,
    )

    result = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate=_FixedGenerate(generated_status),
    ).execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    with open_database(research_paths, read_only=True) as connection:
        target = connection.execute(
            """
            SELECT execution_status, native_ticket_count
            FROM research_prediction_targets
            """
        ).fetchone()
        closure = connection.execute(
            """
            SELECT closure_type, reason_code, sanitized_detail
            FROM research_execution_closures
            """
        ).fetchone()
        assert target == (stored_status.value, 0)
        assert closure is not None
        assert closure[0] == stored_status.value
        assert closure[1]
        assert closure[2] is None
        assert connection.execute(
            "SELECT COUNT(*) FROM research_prediction_tickets"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_ticket_results"
        ).fetchone() == (0,)


def test_unexpected_strategy_exception_is_sanitized_execution_error(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_STRATEGIES[0],),
        minimum=1,
    )

    _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate=_RaisingGenerate(),
    ).execute(manifest)

    with open_database(research_paths, read_only=True) as connection:
        closure = connection.execute(
            """
            SELECT closure_type, reason_code, sanitized_detail
            FROM research_execution_closures
            """
        ).fetchone()
        assert closure == (
            ResearchExecutionStatus.EXECUTION_ERROR.value,
            "REPLAY_ERROR",
            "strategy execution failed safely",
        )
        assert "sensitive fixture detail" not in str(closure)


def test_conflicting_native_strategy_provenance_stops_resume(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3", "4"),
        strategies=(_STRATEGIES[0],),
        minimum=1,
    )
    stop = Event()
    paused = _runner(
        draw_paths,
        lambda: _PausingRepository(
            research_paths,
            stop,
            pause_after=1,
        ),
    ).execute(manifest, stop_requested=stop)
    assert paused.status is ResearchRunStatus.PAUSED

    with pytest.raises(
        ResearchConflictError,
        match="strategy snapshot identity conflicts",
    ):
        _runner(
            draw_paths,
            lambda: _ConflictingProvenanceRepository(research_paths),
        ).execute(manifest)

    assert _counts(research_paths)["research_prediction_targets"] == 1


def test_altered_completed_target_payload_raises_repository_conflict(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3", "4"),
        strategies=(_STRATEGIES[0],),
        minimum=1,
    )
    stop = Event()
    paused = _runner(
        draw_paths,
        lambda: _PausingRepository(
            research_paths,
            stop,
            pause_after=1,
        ),
    ).execute(manifest, stop_requested=stop)
    assert paused.status is ResearchRunStatus.PAUSED

    with pytest.raises(
        ResearchConflictError,
        match="completed target conflicts",
    ):
        _runner(
            draw_paths,
            lambda: _BlindCompletedTargetRepository(
                research_paths,
                strategy_id=_STRATEGIES[0],
            ),
            generate=_FixedGenerate(GenerateOneBetStatus.REJECTED),
        ).execute(manifest)

    assert _counts(research_paths)["research_prediction_targets"] == 1


def test_real_sqlite_portfolio_run_persists_all_native_tickets_ordered_and_scored(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3", "4"),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=2,
        maximum=4,
    )

    result = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
    ).execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    assert result.expected_target_count == 2
    assert result.completed_target_count == 2
    assert result.tickets_created == 2 * _PORTFOLIO_NATIVE_TICKET_COUNT
    assert result.results_created == result.tickets_created

    with open_database(research_paths, read_only=True) as connection:
        targets = connection.execute(
            """
            SELECT id, execution_status, native_ticket_count, candidate_k,
                   combination_count, ticket_count_prefix
            FROM research_prediction_targets
            ORDER BY target_order
            """
        ).fetchall()
        assert len(targets) == 2
        for target in targets:
            assert target[1] == ResearchExecutionStatus.OK.value
            assert target[2] == _PORTFOLIO_NATIVE_TICKET_COUNT
            assert target[3] == BIG_LOTTO_RULE_CONTRACT.main_number_count
            assert target[4] == _PORTFOLIO_NATIVE_TICKET_COUNT
            assert target[5] == _PORTFOLIO_NATIVE_TICKET_COUNT

        first_target_id = str(targets[0][0])
        tickets = connection.execute(
            """
            SELECT native_position, ordered_portfolio_position, main_numbers_json
            FROM research_prediction_tickets
            WHERE target_id = ?
            ORDER BY native_position
            """,
            (first_target_id,),
        ).fetchall()
        assert [row[0] for row in tickets] == [1, 2, 3, 4, 5]
        assert [row[1] for row in tickets] == [1, 2, 3, 4, 5]

        results = connection.execute(
            """
            SELECT ticket.native_position, result.main_hit_count,
                   result.special_hit_count, result.prize_tier_id,
                   result.ticket_count_prefix, result.hit_numbers_json
            FROM research_ticket_results AS result
            JOIN research_prediction_tickets AS ticket
              ON ticket.id = result.ticket_id
            WHERE result.target_id = ?
            ORDER BY ticket.native_position
            """,
            (first_target_id,),
        ).fetchall()
        assert len(results) == _PORTFOLIO_NATIVE_TICKET_COUNT
        assert [row[0] for row in results] == [1, 2, 3, 4, 5]
        assert all(
            row[4] == _PORTFOLIO_NATIVE_TICKET_COUNT for row in results
        )

        target_binding = connection.execute(
            """
            SELECT target_binding.main_numbers_json,
                   target_binding.special_numbers_json
            FROM research_prediction_targets AS target
            JOIN research_draw_bindings AS target_binding
              ON target_binding.id = target.target_draw_binding_id
            WHERE target.id = ?
            """,
            (first_target_id,),
        ).fetchone()
        winning = tuple(json.loads(str(target_binding[0])))
        special = int(json.loads(str(target_binding[1]))[0])

        for row, (_, main_hit_count, special_hit_count, prize_tier_id, _, hit_json) in zip(
            tickets, results, strict=True
        ):
            predicted = tuple(json.loads(str(row[2])))
            expected_score = score_big_lotto_ticket(
                predicted_main_numbers=predicted,
                winning_main_numbers=winning,
                winning_special_number=special,
            )
            expected_prize = resolve_big_lotto_prize_tier(
                expected_score.main_hits,
                expected_score.special_hit,
            )
            expected_prize_id = (
                expected_prize.tier_id.value
                if isinstance(expected_prize, BigLottoPrizeTier)
                else expected_prize.value
            )
            assert main_hit_count == expected_score.main_hits
            assert special_hit_count == int(expected_score.special_hit)
            assert prize_tier_id == expected_prize_id
            assert json.loads(str(hit_json)) == sorted(
                set(predicted).intersection(winning)
            )

    report = SQLiteResearchRepository(
        research_paths,
        initialize=False,
    ).verify_store()
    assert report.healthy
    _assert_no_sidecars(research_paths)


def test_portfolio_native_order_and_positional_duplicates_are_preserved(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=1,
    )
    ticket_numbers = (
        (6, 1, 5, 2, 4, 3),
        (6, 1, 5, 2, 4, 3),
        (12, 11, 10, 9, 8, 7),
        (12, 11, 10, 9, 8, 7),
        (18, 17, 16, 15, 14, 13),
    )

    result = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate_portfolio=_FixedOkPortfolioGenerate(ticket_numbers),
    ).execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    assert result.tickets_created == 5
    with open_database(research_paths, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT native_position, ordered_portfolio_position, main_numbers_json,
                   native_duplicate_of_position, portfolio_duplicate_of_position
            FROM research_prediction_tickets
            ORDER BY native_position
            """
        ).fetchall()
        assert [row[0] for row in rows] == [1, 2, 3, 4, 5]
        assert [row[1] for row in rows] == [1, 2, 3, 4, 5]
        assert [json.loads(str(row[2])) for row in rows] == [
            [1, 2, 3, 4, 5, 6],
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [7, 8, 9, 10, 11, 12],
            [13, 14, 15, 16, 17, 18],
        ]
        assert [row[3] for row in rows] == [None, 1, None, 3, None]
        assert [row[4] for row in rows] == [None, 1, None, 3, None]

    report = SQLiteResearchRepository(
        research_paths,
        initialize=False,
    ).verify_store()
    assert report.healthy


def test_portfolio_candidate_k_mismatch_fails_closed_as_invalid_output(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=1,
    )
    legal_numbers = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
    )
    emitted_numbers = (
        (6, 1, 5, 2, 4, 3),
        (12, 11, 10, 9, 8, 7),
        (18, 17, 16, 15, 14, 13, 19),
        (24, 23, 22, 21, 20, 19),
        (30, 29, 28, 27, 26, 25),
    )

    result = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate_portfolio=_FixedOkPortfolioGenerate(
            legal_numbers,
            emitted_numbers=emitted_numbers,
        ),
    ).execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    with open_database(research_paths, read_only=True) as connection:
        target = connection.execute(
            """
            SELECT execution_status, native_ticket_count
            FROM research_prediction_targets
            """
        ).fetchone()
        closure = connection.execute(
            """
            SELECT closure_type, reason_code
            FROM research_execution_closures
            """
        ).fetchone()
        assert target == (ResearchExecutionStatus.INVALID_OUTPUT.value, 0)
        assert closure == (
            ResearchExecutionStatus.INVALID_OUTPUT.value,
            "INVALID_OUTPUT",
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM research_prediction_tickets"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_ticket_results"
        ).fetchone() == (0,)


def test_mixed_single_and_portfolio_manifest_routes_each_strategy_by_response_shape(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_STRATEGIES[0], _PORTFOLIO_STRATEGY),
        minimum=1,
    )

    result = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
    ).execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    assert result.expected_target_count == 2
    assert result.tickets_created == 1 + _PORTFOLIO_NATIVE_TICKET_COUNT
    with open_database(research_paths, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT snapshot.strategy_id, target.native_ticket_count,
                   target.execution_status
            FROM research_prediction_targets AS target
            JOIN research_strategy_snapshots AS snapshot
              ON snapshot.id = target.strategy_snapshot_id
            ORDER BY snapshot.strategy_id
            """
        ).fetchall()
        by_strategy = {row[0]: (row[1], row[2]) for row in rows}
        assert by_strategy[_STRATEGIES[0]] == (
            1,
            ResearchExecutionStatus.OK.value,
        )
        assert by_strategy[_PORTFOLIO_STRATEGY] == (
            _PORTFOLIO_NATIVE_TICKET_COUNT,
            ResearchExecutionStatus.OK.value,
        )


def test_portfolio_insufficient_manifest_history_closes_with_zero_tickets(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths, count=3)
    manifest = _manifest(
        draw_paths,
        targets=("2",),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=5,
        maximum=5,
    )

    result = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
    ).execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    with open_database(research_paths, read_only=True) as connection:
        target = connection.execute(
            """
            SELECT execution_status, native_ticket_count, causal_eligible
            FROM research_prediction_targets
            """
        ).fetchone()
        closure = connection.execute(
            """
            SELECT closure_type, reason_code
            FROM research_execution_closures
            """
        ).fetchone()
        assert target == (
            ResearchExecutionStatus.INSUFFICIENT_HISTORY.value,
            0,
            0,
        )
        assert closure == (
            ResearchExecutionStatus.INSUFFICIENT_HISTORY.value,
            "AVAILABLE_HISTORY_BELOW_MINIMUM",
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM research_prediction_tickets"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    ("generated_status", "stored_status"),
    [
        (
            GeneratePortfolioStatus.INSUFFICIENT_HISTORY,
            ResearchExecutionStatus.INSUFFICIENT_HISTORY,
        ),
        (
            GeneratePortfolioStatus.STRATEGY_UNAVAILABLE,
            ResearchExecutionStatus.STRATEGY_UNAVAILABLE,
        ),
        (
            GeneratePortfolioStatus.INVALID_OUTPUT,
            ResearchExecutionStatus.INVALID_OUTPUT,
        ),
        (
            GeneratePortfolioStatus.REPLAY_ERROR,
            ResearchExecutionStatus.EXECUTION_ERROR,
        ),
        (
            GeneratePortfolioStatus.WRONG_RESPONSE_PATH,
            ResearchExecutionStatus.STRATEGY_UNAVAILABLE,
        ),
    ],
)
def test_portfolio_strategy_level_failures_become_typed_terminal_targets(
    tmp_path: Path,
    generated_status: GeneratePortfolioStatus,
    stored_status: ResearchExecutionStatus,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=1,
    )

    result = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate_portfolio=_FixedPortfolioGenerate(generated_status),
    ).execute(manifest)

    assert result.status is ResearchRunStatus.COMPLETED
    with open_database(research_paths, read_only=True) as connection:
        target = connection.execute(
            """
            SELECT execution_status, native_ticket_count
            FROM research_prediction_targets
            """
        ).fetchone()
        closure = connection.execute(
            """
            SELECT closure_type, reason_code, sanitized_detail
            FROM research_execution_closures
            """
        ).fetchone()
        assert target == (stored_status.value, 0)
        assert closure is not None
        assert closure[0] == stored_status.value
        assert closure[1]
        assert closure[2] is None
        assert connection.execute(
            "SELECT COUNT(*) FROM research_prediction_tickets"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_ticket_results"
        ).fetchone() == (0,)


def test_portfolio_unexpected_strategy_exception_is_sanitized_execution_error(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=1,
    )

    _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate_portfolio=_RaisingPortfolioGenerate(),
    ).execute(manifest)

    with open_database(research_paths, read_only=True) as connection:
        closure = connection.execute(
            """
            SELECT closure_type, reason_code, sanitized_detail
            FROM research_execution_closures
            """
        ).fetchone()
        assert closure == (
            ResearchExecutionStatus.EXECUTION_ERROR.value,
            "REPLAY_ERROR",
            "strategy execution failed safely",
        )
        assert "sensitive fixture detail" not in str(closure)


def test_portfolio_injected_target_commit_failure_exposes_no_partial_portfolio_and_clean_rerun(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3",),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=1,
    )
    failing_repository = _FailFirstCommitRepository(research_paths)

    with pytest.raises(RuntimeError, match="injected target transaction failure"):
        _runner(
            draw_paths,
            lambda: failing_repository,
        ).execute(manifest)

    failed_counts = _counts(research_paths)
    assert failed_counts["research_prediction_targets"] == 0
    assert failed_counts["research_prediction_tickets"] == 0
    assert failed_counts["research_ticket_results"] == 0
    assert failed_counts["research_execution_closures"] == 0
    _assert_no_sidecars(research_paths)

    completed = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
    ).execute(manifest)

    assert completed.status is ResearchRunStatus.COMPLETED
    final_counts = _counts(research_paths)
    assert final_counts["research_prediction_targets"] == 1
    assert final_counts["research_prediction_tickets"] == (
        _PORTFOLIO_NATIVE_TICKET_COUNT
    )
    assert final_counts["research_ticket_results"] == (
        _PORTFOLIO_NATIVE_TICKET_COUNT
    )
    _assert_no_sidecars(research_paths)


def test_portfolio_pause_resume_skips_completed_keys_and_completed_third_run_is_exact_no_op(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    research_paths = _research_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3", "4"),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=1,
    )
    stop = Event()
    first_generate = _RecordingPortfolioGenerate(
        build_production_generate_ordered_portfolio_emission()
    )
    pausing_repository = _PausingRepository(
        research_paths,
        stop,
        pause_after=1,
    )

    first = _runner(
        draw_paths,
        lambda: pausing_repository,
        generate_portfolio=first_generate,
    ).execute(manifest, stop_requested=stop)

    assert first.status is ResearchRunStatus.PAUSED
    assert first.interrupted is True
    assert first.completed_target_count == 1
    assert _counts(research_paths)["research_prediction_targets"] == 1
    assert _counts(research_paths)["research_prediction_tickets"] == (
        _PORTFOLIO_NATIVE_TICKET_COUNT
    )
    _assert_no_sidecars(research_paths)

    second_generate = _RecordingPortfolioGenerate(
        build_production_generate_ordered_portfolio_emission()
    )
    second = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate_portfolio=second_generate,
    ).execute(manifest)

    assert second.status is ResearchRunStatus.COMPLETED
    assert second.completed_target_count == 2
    assert second.targets_created == 1
    all_execution_calls = first_generate.calls + second_generate.calls
    assert len(all_execution_calls) == len(set(all_execution_calls))
    completed_counts = _counts(research_paths)
    assert completed_counts["research_prediction_targets"] == 2
    assert completed_counts["research_prediction_tickets"] == (
        2 * _PORTFOLIO_NATIVE_TICKET_COUNT
    )

    third_generate = _RecordingPortfolioGenerate(
        build_production_generate_ordered_portfolio_emission()
    )
    third = _runner(
        draw_paths,
        lambda: SQLiteResearchRepository(research_paths),
        generate_portfolio=third_generate,
    ).execute(manifest)

    assert third.status is ResearchRunStatus.COMPLETED
    assert third.idempotent_no_op is True
    assert third.targets_created == 0
    assert third.tickets_created == 0
    assert third.results_created == 0
    assert third_generate.calls == []
    assert _counts(research_paths) == completed_counts
    assert SQLiteResearchRepository(
        research_paths,
        initialize=False,
    ).verify_store().healthy
    _assert_no_sidecars(research_paths)


def test_portfolio_run_is_deterministic_across_independent_runs(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed_draws(draw_paths)
    manifest = _manifest(
        draw_paths,
        targets=("3", "4"),
        strategies=(_PORTFOLIO_STRATEGY,),
        minimum=2,
        maximum=4,
    )

    def _ticket_numbers(research_paths: ResearchDataPaths) -> list[tuple[str, ...]]:
        _runner(
            draw_paths,
            lambda: SQLiteResearchRepository(research_paths),
        ).execute(manifest)
        with open_database(research_paths, read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT target.target_draw_number, ticket.native_position,
                       ticket.main_numbers_json
                FROM research_prediction_tickets AS ticket
                JOIN research_prediction_targets AS target
                  ON target.id = ticket.target_id
                ORDER BY target.target_draw_number, ticket.native_position
                """
            ).fetchall()
        return [tuple(str(value) for value in row) for row in rows]

    first_run = _ticket_numbers(_research_paths(tmp_path, "research-data-first"))
    second_run = _ticket_numbers(_research_paths(tmp_path, "research-data-second"))

    assert first_run
    assert first_run == second_run
