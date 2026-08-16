"""Focused acceptance tests for the lottery-agnostic forward cycle core."""

from __future__ import annotations

from dataclasses import dataclass

from lottolab.application.forward_auto_cycle_core import (
    ForwardAutoCycleCore,
    ForwardAutoCycleResult,
)


@dataclass(frozen=True, slots=True)
class _Target:
    name: str = "target-1"


class _FakeAdapter:
    lottery_type = "FAKE"

    def __init__(self) -> None:
        self.target = _Target()
        self.streams = ("first", "broken", "second")
        self.existing: set[str] = set()
        self.current: dict[str, str] | None = None
        self.official: dict[str, str] | None = {"result": "v1"}
        self.events: list[str] = []
        self.stale = True

    def resolve_next_target(self) -> _Target | None:
        self.events.append("resolve_target")
        return self.target

    def list_enabled_strategy_streams(self) -> tuple[str, ...]:
        return self.streams

    def build_history_snapshot(self, target: _Target) -> dict[str, str]:
        assert target == self.target
        self.events.append("build_history")
        return {"cutoff": "old"}

    def history_warnings(self, _history: dict[str, str]) -> tuple[str, ...]:
        return ("STALE_HISTORY",) if self.stale else ()

    def run_strategy(
        self,
        stream: str,
        target: _Target,
        history: dict[str, str],
    ) -> dict[str, str]:
        assert target == self.target
        assert history == {"cutoff": "old"}
        self.events.append(f"run:{stream}")
        if stream == "broken":
            self.existing.add(stream)
            raise RuntimeError("synthetic stream failure")
        self.existing.add(stream)
        return {"stream": stream}

    def prediction_exists(self, target: _Target, stream: str) -> bool:
        assert target == self.target
        return stream in self.existing

    def read_current_outcome(self, target: _Target) -> dict[str, str] | None:
        assert target == self.target
        return self.current

    def resolve_official_outcome(self, target: _Target) -> dict[str, str] | None:
        assert target == self.target
        return self.official

    def update_outcome(
        self,
        target: _Target,
        outcome: dict[str, str],
    ) -> dict[str, str]:
        assert target == self.target
        self.events.append("update_outcome")
        self.current = dict(outcome)
        return self.current

    def outcomes_equal(
        self,
        left: dict[str, str],
        right: dict[str, str],
    ) -> bool:
        return left == right

    def score_prediction(
        self,
        prediction: dict[str, str],
        outcome: dict[str, str],
    ) -> str:
        assert outcome
        self.events.append(f"score:{prediction['stream']}")
        return f"score:{prediction['stream']}"

    def rescore_target(
        self,
        target: _Target,
        outcome: dict[str, str],
    ) -> tuple[str, ...]:
        assert target == self.target
        assert outcome
        self.events.append("rescore_target")
        return ("rescored",)

    def refresh_reporting(self) -> str:
        self.events.append("refresh_reporting")
        return "refreshed"


class _NoTargetAdapter(_FakeAdapter):
    def resolve_next_target(self) -> _Target | None:
        return None


def _run(
    adapter: _FakeAdapter,
) -> ForwardAutoCycleResult[
    _Target,
    str,
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    return ForwardAutoCycleCore[
        _Target,
        str,
        dict[str, str],
        dict[str, str],
        dict[str, str],
    ](adapter).run()


def test_core_uses_fake_adapter_and_isolates_one_strategy_failure() -> None:
    adapter = _FakeAdapter()

    result = _run(adapter)

    assert [prediction["stream"] for prediction in result.created_predictions] == [
        "first",
        "second",
    ]
    assert [failure.stream for failure in result.strategy_failures] == ["broken"]
    assert result.warnings == ("STALE_HISTORY",)
    assert result.outcome_status == "NEW_OUTCOME"
    assert result.rescore_results == ("rescored",)
    assert result.next_action == "PREDICTIONS_CREATED_AND_OUTCOME_RECORDED"
    assert adapter.events[-1] == "refresh_reporting"


def test_core_repeated_cycle_is_idempotent_for_predictions_and_identical_outcome() -> None:
    adapter = _FakeAdapter()

    first = _run(adapter)
    events_after_first = len(adapter.events)
    second = _run(adapter)

    assert len(first.created_predictions) == 2
    assert second.created_predictions == ()
    assert set(second.existing_streams) == {"first", "broken", "second"}
    assert second.outcome_status == "IDENTICAL_OUTCOME"
    assert second.rescore_results == ()
    assert second.next_action == "NO_OP"
    assert adapter.events[events_after_first:] == [
        "resolve_target",
        "build_history",
        "refresh_reporting",
    ]


def test_core_corrected_outcome_is_updated_and_rescored() -> None:
    adapter = _FakeAdapter()
    adapter.existing.update({"first", "second"})
    adapter.current = {"result": "v1"}
    adapter.official = {"result": "v2"}

    result = _run(adapter)

    assert result.created_predictions == ()
    assert result.outcome_status == "CORRECTED_OUTCOME"
    assert result.current_outcome == {"result": "v2"}
    assert result.rescore_results == ("rescored",)
    assert result.next_action == "OUTCOME_CORRECTED_AND_RESCORED"
    assert "update_outcome" in adapter.events


def test_core_stale_history_warning_does_not_block_prediction() -> None:
    adapter = _FakeAdapter()
    adapter.official = None

    result = _run(adapter)

    assert len(result.created_predictions) == 2
    assert result.outcome_status == "OUTCOME_PENDING"
    assert result.next_action == "PREDICTIONS_CREATED_WAITING_FOR_OUTCOME"
    assert result.warnings == ("STALE_HISTORY",)


def test_core_returns_no_target_without_invoking_the_cycle() -> None:
    adapter = _NoTargetAdapter()

    result = _run(adapter)

    assert result.next_action == "NO_TARGET"
    assert result.target is None
    assert result.reporting is None
