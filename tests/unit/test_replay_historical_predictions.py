"""Closed-outcome tests for the ReplayHistoricalPredictions use case.

Application-layer only: a fake in-memory ``DrawHistoryReader`` and fake
``BetAdapter``s are injected, so none of these tests touch SQLite,
draw_schema, repositories, or replay_history_reader — mirroring
``tests/unit/test_build_causal_history.py`` and
``tests/unit/test_generate_bet_use_case.py``.
"""

from __future__ import annotations

from datetime import date

import pytest

from lottolab.application.ports import TargetDrawNotFoundError
from lottolab.application.use_cases.build_causal_history import BuildCausalHistory
from lottolab.application.use_cases.generate_bet import GenerateOneBet
from lottolab.application.use_cases.replay_historical_predictions import (
    DuplicateReplayStrategyError,
    DuplicateReplayTargetError,
    ReplayHistoricalPredictions,
    ReplayHistoricalPredictionsInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.evidence.replay_artifact import causal_history_sha256
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    RejectPrediction,
)
from lottolab.strategies.catalog import StrategyCatalog

_STRATEGY_A = "fixture_strategy_a"
_STRATEGY_B = "fixture_strategy_b"


def _row(draw_number: str, day: int) -> ReplayCausalDrawRow:
    return ReplayCausalDrawRow(
        draw_number=draw_number,
        draw_date=date(2020, 1, day),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=44,
    )


class FakeDrawHistoryReader:
    """An in-memory double satisfying the DrawHistoryReader port shape."""

    def __init__(
        self, *, history_by_target: dict[str, tuple[ReplayCausalDrawRow, ...]] | None = None
    ) -> None:
        self._history_by_target = history_by_target or {}
        self.calls: list[tuple[LotteryType, str, int | None]] = []

    def read_causal_history(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
        *,
        maximum_history_draws: int | None = None,
    ) -> tuple[ReplayCausalDrawRow, ...]:
        self.calls.append((lottery_type, target_draw_number, maximum_history_draws))
        if target_draw_number not in self._history_by_target:
            raise TargetDrawNotFoundError(target_draw_number)
        full_history = self._history_by_target[target_draw_number]
        if maximum_history_draws is None:
            return full_history
        return full_history[-maximum_history_draws:]


class _OutcomeAdapterA(BetAdapter):
    strategy_id = _STRATEGY_A
    strategy_name = "Fixture Strategy"
    strategy_version = "v1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, outcome: str = "ok") -> None:
        self.outcome = outcome
        self.calls = 0

    def _predict(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[int, ...]:
        self.calls += 1
        if self.outcome == "rejected":
            raise RejectPrediction("declined")
        if self.outcome == "insufficient":
            raise InsufficientHistory("needs more")
        if self.outcome == "invalid":
            raise InvalidOutput("bad output")
        return (1, 2, 3, 4, 5, 6)


class _OutcomeAdapterB(_OutcomeAdapterA):
    strategy_id = _STRATEGY_B


_ADAPTER_CLASSES: dict[str, type[_OutcomeAdapterA]] = {
    _STRATEGY_A: _OutcomeAdapterA,
    _STRATEGY_B: _OutcomeAdapterB,
}


def _descriptor(strategy_id: str) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name="Fixture Strategy",
        version="v1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
        adapter_path="fixture:Adapter",
        min_history=1,
    )


def _use_case(
    *,
    history_by_target: dict[str, tuple[ReplayCausalDrawRow, ...]] | None = None,
    strategy_ids: tuple[str, ...] = (_STRATEGY_A,),
    outcomes: dict[str, str] | None = None,
    reader: FakeDrawHistoryReader | None = None,
) -> tuple[ReplayHistoricalPredictions, FakeDrawHistoryReader]:
    if reader is None:
        reader = FakeDrawHistoryReader(history_by_target=history_by_target)
    catalog = StrategyCatalog(tuple(_descriptor(strategy_id) for strategy_id in strategy_ids))
    outcomes = outcomes or {}
    adapters = {
        strategy_id: _ADAPTER_CLASSES[strategy_id](outcomes.get(strategy_id, "ok"))
        for strategy_id in strategy_ids
    }
    generate_one_bet = GenerateOneBet(catalog, adapters)
    build_causal_history = BuildCausalHistory(lambda: reader)
    return ReplayHistoricalPredictions(build_causal_history, generate_one_bet, catalog), reader


def _target(draw_number: str, day: int) -> ReplayTarget:
    return ReplayTarget(draw_number=draw_number, draw_date=date(2020, 1, day))


# --------------------------------------------------------------------------
# Input validation: duplicate rejection
# --------------------------------------------------------------------------


def test_duplicate_targets_are_rejected_at_construction() -> None:
    with pytest.raises(DuplicateReplayTargetError):
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5), _target("10", 6)),
            strategy_ids=(_STRATEGY_A,),
        )


def test_duplicate_strategy_ids_are_rejected_at_construction() -> None:
    with pytest.raises(DuplicateReplayStrategyError):
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(_STRATEGY_A, _STRATEGY_A),
        )


def test_empty_targets_or_strategy_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="targets"):
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(),
            strategy_ids=(_STRATEGY_A,),
        )
    with pytest.raises(ValueError, match="strategy_ids"):
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(),
        )


# --------------------------------------------------------------------------
# Typed history closed-result propagation
# --------------------------------------------------------------------------


def test_target_not_found_propagates_as_a_closed_history_result_with_no_prediction() -> None:
    use_case, _ = _use_case(history_by_target={})
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("999", 5),),
            strategy_ids=(_STRATEGY_A,),
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.history_status == "TARGET_NOT_FOUND"
    assert snapshot.history_reason_code == "TARGET_DRAW_NOT_FOUND"
    assert snapshot.prediction_status is None
    assert snapshot.prediction_reason_code is None
    assert snapshot.predicted_main_numbers is None


def test_insufficient_history_propagates_as_a_closed_history_result() -> None:
    history = {"10": (_row("1", 1), _row("2", 2))}
    use_case, _ = _use_case(history_by_target=history)
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(_STRATEGY_A,),
            minimum_history_draws=5,
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.history_status == "INSUFFICIENT_HISTORY"
    assert snapshot.history_reason_code == "AVAILABLE_HISTORY_BELOW_MINIMUM"
    assert snapshot.prediction_status is None


def test_invalid_bounds_propagates_as_a_closed_history_result_and_never_calls_the_reader() -> None:
    use_case, reader = _use_case(history_by_target={"10": (_row("1", 1),)})
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(_STRATEGY_A,),
            maximum_history_draws=0,
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.history_status == "INVALID_BOUNDS"
    assert snapshot.history_reason_code == "MAXIMUM_HISTORY_DRAWS_NOT_POSITIVE"
    assert reader.calls == []


# --------------------------------------------------------------------------
# Typed prediction closed-result propagation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_reason"),
    [
        ("rejected", "REJECTED", "REJECTED_BY_STRATEGY"),
        ("insufficient", "INSUFFICIENT_HISTORY", "INSUFFICIENT_HISTORY"),
        ("invalid", "INVALID_OUTPUT", "INVALID_OUTPUT"),
    ],
)
def test_adapter_outcomes_propagate_as_closed_prediction_results(
    outcome: str, expected_status: str, expected_reason: str
) -> None:
    history = {"10": (_row("1", 1),)}
    use_case, _ = _use_case(history_by_target=history, outcomes={_STRATEGY_A: outcome})
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(_STRATEGY_A,),
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.history_status == "OK"
    assert snapshot.prediction_status == expected_status
    assert snapshot.prediction_reason_code == expected_reason
    assert snapshot.predicted_main_numbers is None


def test_ok_prediction_carries_predicted_main_numbers() -> None:
    history = {"10": (_row("1", 1),)}
    use_case, _ = _use_case(history_by_target=history)
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(_STRATEGY_A,),
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.prediction_status == "OK"
    assert snapshot.predicted_main_numbers == (1, 2, 3, 4, 5, 6)


def test_ok_history_with_empty_causal_history_has_no_cutoff_and_still_attempts_prediction() -> None:
    # The target is the first draw in the dataset: BuildCausalHistory legitimately
    # returns OK with an empty tuple (no minimum_history_draws is set). A prediction
    # is still attempted under existing rules — the fixture adapter's own
    # min_history=1 floor means that attempt closes as INSUFFICIENT_HISTORY, not a
    # crash and not a fabricated OK.
    use_case, _ = _use_case(history_by_target={"1": ()})
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("1", 1),),
            strategy_ids=(_STRATEGY_A,),
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.history_status == "OK"
    assert snapshot.causal_history_count == 0
    assert snapshot.causal_history_sha256 == causal_history_sha256(())
    assert snapshot.cutoff_draw_number is None
    assert snapshot.cutoff_draw_date is None
    assert snapshot.prediction_status == "INSUFFICIENT_HISTORY"
    assert snapshot.prediction_reason_code == "INSUFFICIENT_HISTORY"
    assert snapshot.predicted_main_numbers is None


# --------------------------------------------------------------------------
# Identity mismatch fail-closed
# --------------------------------------------------------------------------


def test_unknown_strategy_id_is_a_closed_result_not_a_crash() -> None:
    history = {"10": (_row("1", 1),)}
    use_case, _ = _use_case(history_by_target=history, strategy_ids=(_STRATEGY_A,))
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=("does_not_exist",),
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.history_status == "OK"
    assert snapshot.prediction_status == "STRATEGY_UNAVAILABLE"
    assert snapshot.prediction_reason_code == "UNKNOWN_STRATEGY"
    assert snapshot.strategy_version is None
    assert snapshot.adapter_strategy_id is None
    assert snapshot.strategy_id == "does_not_exist"


# --------------------------------------------------------------------------
# Ordering, one-per-pair, history reuse, determinism
# --------------------------------------------------------------------------


def test_deterministic_target_major_strategy_minor_pair_ordering() -> None:
    history = {"10": (_row("1", 1),), "20": (_row("1", 1),)}
    use_case, _ = _use_case(history_by_target=history, strategy_ids=(_STRATEGY_A, _STRATEGY_B))
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("20", 6), _target("10", 5)),
            strategy_ids=(_STRATEGY_B, _STRATEGY_A),
        )
    )
    pairs = [(snapshot.target_draw_number, snapshot.strategy_id) for snapshot in result.snapshots]
    assert pairs == [
        ("20", _STRATEGY_B),
        ("20", _STRATEGY_A),
        ("10", _STRATEGY_B),
        ("10", _STRATEGY_A),
    ]


def test_exactly_one_snapshot_per_target_times_strategy_pair() -> None:
    history = {"10": (_row("1", 1),), "20": (_row("1", 1),)}
    use_case, _ = _use_case(history_by_target=history, strategy_ids=(_STRATEGY_A, _STRATEGY_B))
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5), _target("20", 6)),
            strategy_ids=(_STRATEGY_A, _STRATEGY_B),
        )
    )
    assert len(result.snapshots) == 4
    assert len({(s.target_draw_number, s.strategy_id) for s in result.snapshots}) == 4


def test_history_is_built_once_per_target_across_multiple_strategies() -> None:
    history = {"10": (_row("1", 1),)}
    use_case, reader = _use_case(history_by_target=history, strategy_ids=(_STRATEGY_A, _STRATEGY_B))
    use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(_STRATEGY_A, _STRATEGY_B),
        )
    )
    assert reader.calls == [(LotteryType.BIG_LOTTO, "10", None)]


def test_two_identical_runs_produce_identical_snapshots() -> None:
    history = {"10": (_row("1", 1), _row("2", 2))}
    use_case, _ = _use_case(history_by_target=history)
    request = ReplayHistoricalPredictionsInput(
        lottery_type=LotteryType.BIG_LOTTO,
        dataset_id="DS1",
        dataset_version="1",
        targets=(_target("10", 5),),
        strategy_ids=(_STRATEGY_A,),
    )
    first = use_case.execute(request)
    second = use_case.execute(request)
    assert first == second


# --------------------------------------------------------------------------
# No target/future leakage in provenance
# --------------------------------------------------------------------------


def test_history_after_the_target_is_never_visible_to_the_snapshot() -> None:
    # The fake reader only ever returns rows strictly before the target — the
    # same causal contract SQLiteDrawHistoryReader implements. Any row dated
    # on/after the target simply never enters the tuple the reader returns.
    causal_history = (_row("1", 1), _row("2", 2))
    use_case, _ = _use_case(history_by_target={"10": causal_history})
    result = use_case.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id="DS1",
            dataset_version="1",
            targets=(_target("10", 5),),
            strategy_ids=(_STRATEGY_A,),
        )
    )
    snapshot = result.snapshots[0]
    assert snapshot.causal_history_count == 2


def test_this_module_never_imports_sqlite_or_persistence_modules() -> None:
    import ast
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "sqlite3" not in imported
    assert "lottolab.infrastructure.persistence.draw_schema" not in imported
    assert "lottolab.infrastructure.persistence.replay_history_reader" not in imported
