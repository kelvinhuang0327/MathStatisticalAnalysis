"""Application/domain tests for the complete ordered attempt ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from lottolab.application.use_cases.generate_bet import GenerateOneBet
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    GenerateOrderedCandidateEmission,
)
from lottolab.application.use_cases.materialize_ordered_candidate_emissions import (
    MaterializeOrderedCandidateEmissions,
    MaterializeOrderedCandidateEmissionsInput,
    OrderedCandidateMaterializationInputError,
    SourceSnapshotMismatchError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateMaterializationStatus,
    OrderedCandidateSourceRow,
    OrderedCandidateSourceSnapshot,
    build_candidate_source_artifact_identity,
)
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.evidence.ordered_candidate_emission_package import (
    OrderedCandidateEmissionPackage,
    source_snapshot_sha256,
)
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    RejectPrediction,
)
from lottolab.strategies.catalog import StrategyCatalog

_STRATEGY_IDS = ("fixture_alpha", "fixture_beta")


def _source_row(draw: str) -> OrderedCandidateSourceRow:
    number = int(draw)
    return OrderedCandidateSourceRow(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_date=date(2026, 1, number),
        draw_number=draw,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(7,),
        normalized_record_hash=f"{number:064x}",
    )


def _snapshot() -> OrderedCandidateSourceSnapshot:
    rows = tuple(_source_row(str(number)) for number in range(1, 5))
    return OrderedCandidateSourceSnapshot(
        lottery_type=LotteryType.BIG_LOTTO,
        rows=rows,
        source_snapshot_sha256=source_snapshot_sha256(rows),
    )


class _Reader:
    def __init__(self, snapshot: OrderedCandidateSourceSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def read_source_snapshot(
        self,
        lottery_type: LotteryType,
    ) -> OrderedCandidateSourceSnapshot:
        self.calls += 1
        assert lottery_type is LotteryType.BIG_LOTTO
        return self.snapshot


class _Writer:
    def __init__(self) -> None:
        self.calls = 0
        self.package: OrderedCandidateEmissionPackage | None = None
        self.output: Path | None = None

    def write_package(
        self,
        output_directory: Path,
        package: OrderedCandidateEmissionPackage,
    ) -> None:
        self.calls += 1
        self.output = output_directory
        self.package = package


class _Adapter(BetAdapter):
    strategy_id = "fixture"
    strategy_name = "Fixture"
    strategy_version = "v1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.calls: list[tuple[str, ...]] = []

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        self.calls.append(tuple(row.draw for row in history))
        if self.reject:
            raise RejectPrediction
        return (6, 1, 5, 2, 4, 3)


class _AlphaAdapter(_Adapter):
    strategy_id = _STRATEGY_IDS[0]
    strategy_name = f"Fixture {_STRATEGY_IDS[0]}"


class _BetaAdapter(_Adapter):
    strategy_id = _STRATEGY_IDS[1]
    strategy_name = f"Fixture {_STRATEGY_IDS[1]}"


def _descriptor(
    strategy_id: str,
    *,
    response_shape: ResponseShape = ResponseShape.SINGLE_TICKET,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=f"Fixture {strategy_id}",
        version="v1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.OBSERVATION,
        executable=False,
        min_history=1,
        provenance=("fixture",),
        response_shape=response_shape,
        native_ticket_count=(
            2 if response_shape is ResponseShape.PORTFOLIO else 1
        ),
    )


@dataclass
class _Fixture:
    use_case: MaterializeOrderedCandidateEmissions
    reader: _Reader
    writer: _Writer
    adapters: tuple[_Adapter, ...]


def _fixture(*, reject_second: bool = False) -> _Fixture:
    reader = _Reader(_snapshot())
    writer = _Writer()
    adapters = (
        _AlphaAdapter(),
        _BetaAdapter(reject=reject_second),
    )
    generator = GenerateOrderedCandidateEmission(
        GenerateOneBet(
            StrategyCatalog(tuple(_descriptor(item) for item in _STRATEGY_IDS)),
            {adapter.strategy_id: adapter for adapter in adapters},
        )
    )
    return _Fixture(
        use_case=MaterializeOrderedCandidateEmissions(
            reader_factory=lambda: reader,
            writer_factory=lambda: writer,
            generate_ordered_candidate_emission=generator,
        ),
        reader=reader,
        writer=writer,
        adapters=adapters,
    )


def _request(
    tmp_path: Path,
    *,
    replicate: int = 1,
    expected_hash: str | None = None,
) -> MaterializeOrderedCandidateEmissionsInput:
    return MaterializeOrderedCandidateEmissionsInput(
        lottery_type=LotteryType.BIG_LOTTO,
        dataset_id="fixture-dataset",
        dataset_version="v1",
        expected_source_snapshot_sha256=(
            _snapshot().source_snapshot_sha256
            if expected_hash is None
            else expected_hash
        ),
        target_draws=("3", "4"),
        strategy_ids=_STRATEGY_IDS,
        minimum_history_draws=1,
        maximum_history_draws=2,
        replicate=replicate,
        output_directory=tmp_path / "package",
    )


def test_executes_every_attempt_once_in_caller_order_with_exact_cutoff(
    tmp_path: Path,
) -> None:
    fixture = _fixture()

    result = fixture.use_case.execute(_request(tmp_path))

    assert fixture.reader.calls == 1
    assert fixture.writer.calls == 1
    assert [adapter.calls for adapter in fixture.adapters] == [
        [("1", "2"), ("2", "3")],
        [("1", "2"), ("2", "3")],
    ]
    assert result.attempt_count == 4
    assert result.ok_attempt_count == 4
    assert fixture.writer.package is not None
    attempts = fixture.writer.package.attempts
    assert [
        (
            attempt.ordinal,
            attempt.target_draw,
            attempt.strategy_id,
            attempt.history_cutoff,
        )
        for attempt in attempts
    ] == [
        (0, "3", "fixture_alpha", "2"),
        (1, "3", "fixture_beta", "2"),
        (2, "4", "fixture_alpha", "3"),
        (3, "4", "fixture_beta", "3"),
    ]
    assert all(
        attempt.status is OrderedCandidateMaterializationStatus.OK
        and attempt.emission_relative_path is not None
        and attempt.emission_file_sha256 is not None
        and attempt.emission_payload_sha256 is not None
        for attempt in attempts
    )


def test_non_ok_attempt_is_retained_without_artifact_and_package_still_succeeds(
    tmp_path: Path,
) -> None:
    fixture = _fixture(reject_second=True)

    result = fixture.use_case.execute(_request(tmp_path))

    assert result.attempt_count == 4
    assert result.ok_attempt_count == 2
    assert fixture.writer.package is not None
    rejected = fixture.writer.package.attempts[1::2]
    assert all(
        attempt.status is OrderedCandidateMaterializationStatus.REJECTED
        and attempt.emission_relative_path is None
        and attempt.emission_file_sha256 is None
        and attempt.emission_payload_sha256 is None
        for attempt in rejected
    )
    assert len(fixture.writer.package.emission_files) == 2


def test_portfolio_shaped_strategy_is_retained_as_strategy_unavailable(
    tmp_path: Path,
) -> None:
    """A PORTFOLIO-shaped strategy fails closed with WRONG_RESPONSE_PATH before
    ever reaching an adapter; this must be retained as an ordinary closed
    attempt (STRATEGY_UNAVAILABLE), not crash the whole materialization run."""
    reader = _Reader(_snapshot())
    writer = _Writer()
    portfolio_id = "fixture_portfolio"
    generator = GenerateOrderedCandidateEmission(
        GenerateOneBet(
            StrategyCatalog(
                (_descriptor(portfolio_id, response_shape=ResponseShape.PORTFOLIO),)
            ),
            {},
        )
    )
    use_case = MaterializeOrderedCandidateEmissions(
        reader_factory=lambda: reader,
        writer_factory=lambda: writer,
        generate_ordered_candidate_emission=generator,
    )

    result = use_case.execute(
        MaterializeOrderedCandidateEmissionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="fixture-dataset",
            dataset_version="v1",
            expected_source_snapshot_sha256=_snapshot().source_snapshot_sha256,
            target_draws=("3", "4"),
            strategy_ids=(portfolio_id,),
            minimum_history_draws=1,
            maximum_history_draws=10,
            replicate=1,
            output_directory=tmp_path / "package",
        )
    )

    assert result.attempt_count == 2
    assert result.ok_attempt_count == 0
    assert writer.package is not None
    assert all(
        attempt.status is OrderedCandidateMaterializationStatus.STRATEGY_UNAVAILABLE
        for attempt in writer.package.attempts
    )


def test_source_hash_mismatch_calls_no_strategy_and_never_accesses_writer(
    tmp_path: Path,
) -> None:
    fixture = _fixture()

    with pytest.raises(SourceSnapshotMismatchError):
        fixture.use_case.execute(_request(tmp_path, expected_hash="f" * 64))

    assert fixture.reader.calls == 1
    assert fixture.writer.calls == 0
    assert all(adapter.calls == [] for adapter in fixture.adapters)


def test_replicate_other_than_one_accesses_neither_reader_nor_writer(
    tmp_path: Path,
) -> None:
    fixture = _fixture()

    with pytest.raises(OrderedCandidateMaterializationInputError):
        fixture.use_case.execute(_request(tmp_path, replicate=2))

    assert fixture.reader.calls == 0
    assert fixture.writer.calls == 0
    assert all(adapter.calls == [] for adapter in fixture.adapters)


def test_missing_target_and_insufficient_history_each_keep_all_attempts(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    base = _request(tmp_path)
    request = MaterializeOrderedCandidateEmissionsInput(
        lottery_type=base.lottery_type,
        dataset_id=base.dataset_id,
        dataset_version=base.dataset_version,
        expected_source_snapshot_sha256=base.expected_source_snapshot_sha256,
        target_draws=("999", "1"),
        strategy_ids=base.strategy_ids,
        minimum_history_draws=1,
        maximum_history_draws=2,
        replicate=1,
        output_directory=base.output_directory,
    )

    result = fixture.use_case.execute(request)

    assert result.attempt_count == 4
    assert fixture.writer.package is not None
    assert [attempt.status for attempt in fixture.writer.package.attempts] == [
        OrderedCandidateMaterializationStatus.TARGET_NOT_FOUND,
        OrderedCandidateMaterializationStatus.TARGET_NOT_FOUND,
        OrderedCandidateMaterializationStatus.INSUFFICIENT_HISTORY,
        OrderedCandidateMaterializationStatus.INSUFFICIENT_HISTORY,
    ]
    assert all(adapter.calls == [] for adapter in fixture.adapters)


def test_mixed_matrix_establishes_executable_cell_call_cardinality_identity(
    tmp_path: Path,
) -> None:
    fixture = _fixture(reject_second=True)
    base = _request(tmp_path)
    request = MaterializeOrderedCandidateEmissionsInput(
        lottery_type=base.lottery_type,
        dataset_id=base.dataset_id,
        dataset_version=base.dataset_version,
        expected_source_snapshot_sha256=base.expected_source_snapshot_sha256,
        target_draws=("999", "1", "3", "4"),
        strategy_ids=base.strategy_ids,
        minimum_history_draws=1,
        maximum_history_draws=2,
        replicate=1,
        output_directory=base.output_directory,
    )

    result = fixture.use_case.execute(request)

    assert fixture.reader.calls == 1
    assert fixture.writer.calls == 1
    assert fixture.writer.package is not None
    attempts = fixture.writer.package.attempts
    total_matrix_cells = len(request.target_draws) * len(request.strategy_ids)
    assert total_matrix_cells == 8
    assert result.attempt_count == total_matrix_cells

    preflight_closed_statuses = {
        OrderedCandidateMaterializationStatus.TARGET_NOT_FOUND,
        OrderedCandidateMaterializationStatus.INSUFFICIENT_HISTORY,
    }
    preflight_closed = [a for a in attempts if a.status in preflight_closed_statuses]
    executable = [a for a in attempts if a.status not in preflight_closed_statuses]

    # "999" is absent and "1" has no draws before it, so both target draws
    # are preflight-closed for every strategy; "3" and "4" are executable.
    assert [attempt.status for attempt in attempts] == [
        OrderedCandidateMaterializationStatus.TARGET_NOT_FOUND,
        OrderedCandidateMaterializationStatus.TARGET_NOT_FOUND,
        OrderedCandidateMaterializationStatus.INSUFFICIENT_HISTORY,
        OrderedCandidateMaterializationStatus.INSUFFICIENT_HISTORY,
        OrderedCandidateMaterializationStatus.OK,
        OrderedCandidateMaterializationStatus.REJECTED,
        OrderedCandidateMaterializationStatus.OK,
        OrderedCandidateMaterializationStatus.REJECTED,
    ]
    assert [attempt.ordinal for attempt in attempts] == list(range(total_matrix_cells))
    assert len(preflight_closed) == 4
    assert len(executable) == 4

    # GenerateOrderedCandidateEmission.execute() and GenerateOneBet each make
    # exactly one downstream call per invocation (no retry), so the adapter's
    # exact call list is a 1:1 proxy for calls to the merged P335 use case.
    assert [adapter.calls for adapter in fixture.adapters] == [
        [("1", "2"), ("2", "3")],
        [("1", "2"), ("2", "3")],
    ]
    total_p335_calls = sum(len(adapter.calls) for adapter in fixture.adapters)
    assert total_p335_calls == len(executable) == 4
    assert len(attempts) == total_matrix_cells
    assert len(preflight_closed) + len(executable) == total_matrix_cells

    assert all(attempt.history_cutoff is None for attempt in preflight_closed)
    assert all(
        attempt.emission_relative_path is None
        and attempt.emission_file_sha256 is None
        and attempt.emission_payload_sha256 is None
        for attempt in preflight_closed
    )
    assert len(fixture.writer.package.emission_files) == 2


def test_future_publication_binding_uses_package_path_and_exact_file_hash(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    fixture.use_case.execute(_request(tmp_path))
    assert fixture.writer.package is not None
    attempt = fixture.writer.package.attempts[0]

    identity = build_candidate_source_artifact_identity(
        attempt=attempt,
        publication_repository="kelvinhuang0327/MathStatisticalAnalysis",
        publication_commit_oid="1" * 40,
        publication_package_path="evidence/p336/package",
    )

    assert identity.path == (
        "evidence/p336/package/"
        "emissions/target-3/strategy-fixture_alpha/version-v1/"
        "replicate-000001.json"
    )
    assert identity.sha256 == attempt.emission_file_sha256
