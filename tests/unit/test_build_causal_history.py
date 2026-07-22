"""Closed-outcome tests for the BuildCausalHistory application use case.

Application-layer only: a fake in-memory DrawHistoryReader is injected, so
none of these tests touch SQLite, draw_schema, repositories, or
replay_history_reader.
"""

from __future__ import annotations

from datetime import date

import pytest

from lottolab.application.ports import TargetDrawNotFoundError
from lottolab.application.use_cases.build_causal_history import (
    BuildCausalHistory,
    BuildCausalHistoryInput,
    BuildCausalHistoryReason,
    BuildCausalHistoryStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow


def _row(draw_number: str, draw_date: date) -> ReplayCausalDrawRow:
    return ReplayCausalDrawRow(
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=7,
    )


class FakeDrawHistoryReader:
    """An in-memory double satisfying the DrawHistoryReader port shape."""

    def __init__(
        self,
        *,
        history_by_target: dict[str, tuple[ReplayCausalDrawRow, ...]] | None = None,
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


def _use_case(reader: FakeDrawHistoryReader) -> BuildCausalHistory:
    return BuildCausalHistory(lambda: reader)


def test_no_test_in_this_module_imports_sqlite_or_persistence_modules() -> None:
    """This module's own source must never import SQLite or persistence modules."""

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
    assert "lottolab.infrastructure.persistence.repositories" not in imported
    assert "lottolab.infrastructure.persistence.replay_history_reader" not in imported


def test_target_not_found_is_a_closed_result() -> None:
    reader = FakeDrawHistoryReader(history_by_target={})
    use_case = _use_case(reader)

    result = use_case.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="999",
        )
    )

    assert result.status is BuildCausalHistoryStatus.TARGET_NOT_FOUND
    assert result.reason_code is BuildCausalHistoryReason.TARGET_DRAW_NOT_FOUND
    assert result.history is None
    assert result.available_history_count is None
    assert result.lottery_type is LotteryType.BIG_LOTTO
    assert result.target_draw_number == "999"


@pytest.mark.parametrize(
    ("maximum", "minimum", "expected_reason"),
    [
        (0, None, BuildCausalHistoryReason.MAXIMUM_HISTORY_DRAWS_NOT_POSITIVE),
        (-1, None, BuildCausalHistoryReason.MAXIMUM_HISTORY_DRAWS_NOT_POSITIVE),
        (None, 0, BuildCausalHistoryReason.MINIMUM_HISTORY_DRAWS_NOT_POSITIVE),
        (None, -5, BuildCausalHistoryReason.MINIMUM_HISTORY_DRAWS_NOT_POSITIVE),
        (5, 10, BuildCausalHistoryReason.MINIMUM_EXCEEDS_MAXIMUM),
    ],
)
def test_invalid_bounds_is_a_closed_result_and_never_calls_the_reader(
    maximum: int | None,
    minimum: int | None,
    expected_reason: BuildCausalHistoryReason,
) -> None:
    reader = FakeDrawHistoryReader()
    use_case = _use_case(reader)

    result = use_case.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="10",
            maximum_history_draws=maximum,
            minimum_history_draws=minimum,
        )
    )

    assert result.status is BuildCausalHistoryStatus.INVALID_BOUNDS
    assert result.reason_code is expected_reason
    assert result.history is None
    assert result.available_history_count is None
    assert reader.calls == []


def test_insufficient_history_is_a_closed_result() -> None:
    history = (_row("1", date(2026, 1, 1)), _row("2", date(2026, 1, 2)))
    reader = FakeDrawHistoryReader(history_by_target={"3": history})
    use_case = _use_case(reader)

    result = use_case.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="3",
            minimum_history_draws=5,
        )
    )

    assert result.status is BuildCausalHistoryStatus.INSUFFICIENT_HISTORY
    assert result.reason_code is BuildCausalHistoryReason.AVAILABLE_HISTORY_BELOW_MINIMUM
    assert result.history is None
    assert result.available_history_count is None


def test_ok_result_preserves_reader_ordering_without_reordering() -> None:
    # Deliberately out of ascending order: the use case must pass it through
    # exactly as the reader returned it, never silently re-sort.
    history = (
        _row("5", date(2026, 1, 5)),
        _row("1", date(2026, 1, 1)),
        _row("3", date(2026, 1, 3)),
    )
    reader = FakeDrawHistoryReader(history_by_target={"10": history})
    use_case = _use_case(reader)

    result = use_case.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="10",
        )
    )

    assert result.status is BuildCausalHistoryStatus.OK
    assert result.reason_code is None
    assert result.history == history
    assert result.available_history_count == 3
    assert result.applied_maximum_history_draws is None


def test_maximum_history_draws_is_passed_through_to_the_reader() -> None:
    history = tuple(_row(str(index), date(2026, 1, index)) for index in range(1, 6))
    reader = FakeDrawHistoryReader(history_by_target={"100": history})
    use_case = _use_case(reader)

    result = use_case.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="100",
            maximum_history_draws=2,
        )
    )

    assert result.status is BuildCausalHistoryStatus.OK
    assert result.applied_maximum_history_draws == 2
    assert result.history == history[-2:]
    assert result.available_history_count == 2
    assert reader.calls == [(LotteryType.BIG_LOTTO, "100", 2)]


def test_ok_result_with_minimum_and_maximum_both_satisfied() -> None:
    history = tuple(_row(str(index), date(2026, 1, index)) for index in range(1, 4))
    reader = FakeDrawHistoryReader(history_by_target={"50": history})
    use_case = _use_case(reader)

    result = use_case.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="50",
            maximum_history_draws=10,
            minimum_history_draws=2,
        )
    )

    assert result.status is BuildCausalHistoryStatus.OK
    assert result.history == history
    assert result.available_history_count == 3


def test_zero_pre_target_history_is_ok_with_empty_tuple_not_insufficient() -> None:
    reader = FakeDrawHistoryReader(history_by_target={"1": ()})
    use_case = _use_case(reader)

    result = use_case.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="1",
        )
    )

    assert result.status is BuildCausalHistoryStatus.OK
    assert result.history == ()
    assert result.available_history_count == 0


def test_result_post_init_rejects_ok_status_without_history() -> None:
    from lottolab.application.use_cases.build_causal_history import BuildCausalHistoryResult

    with pytest.raises(ValueError):
        BuildCausalHistoryResult(
            status=BuildCausalHistoryStatus.OK,
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="1",
            applied_maximum_history_draws=None,
            history=None,
            available_history_count=None,
            reason_code=None,
        )


def test_result_post_init_rejects_non_ok_status_with_history() -> None:
    from lottolab.application.use_cases.build_causal_history import BuildCausalHistoryResult

    with pytest.raises(ValueError):
        BuildCausalHistoryResult(
            status=BuildCausalHistoryStatus.TARGET_NOT_FOUND,
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number="1",
            applied_maximum_history_draws=None,
            history=(),
            available_history_count=0,
            reason_code=BuildCausalHistoryReason.TARGET_DRAW_NOT_FOUND,
        )
