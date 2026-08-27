"""B649 composition for the lottery-agnostic forward auto-cycle core."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from lottolab.application.forward_auto_cycle_core import ForwardAutoCycleResult
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_scoring import ReplayTargetOutcomeReadStatus
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.persistence.replay_target_outcome_reader import (
    SQLiteReplayTargetOutcomeReader,
)
from tools.b649_operational_prediction_loop import (
    DEFAULT_OPERATION_ROOT,
    LOTTERY_TYPE,
    STRATEGY_STREAMS,
    TAIPEI,
    HistorySnapshot,
    PredictionTarget,
    StrategyStream,
    build_head_to_head_summary,
    compute_history_freshness,
    ensure_operation_root,
    iter_prediction_files,
    load_canonical_history,
    rebuild_history_freshness_ledger,
    rebuild_performance_ledger,
    rescore_draw,
    resolve_latest_known_draw,
    run_all_enabled_streams,
    write_research_summary,
)
from tools.b649_operational_prediction_loop import (
    score_prediction as score_b649_prediction,
)
from tools.b649_operational_prediction_loop import (
    update_outcome as update_b649_outcome,
)

OfficialOutcomeResolver = Callable[[PredictionTarget], dict[str, object] | None]
HistoryBuilder = Callable[[PredictionTarget], HistorySnapshot]
TargetResolver = Callable[[], PredictionTarget | None]
Clock = Callable[[], datetime]


class B649ForwardAutoCycleAdapter:
    """Adapt the existing B649 operational loop to the shared core."""

    lottery_type = LOTTERY_TYPE

    def __init__(
        self,
        root: Path = DEFAULT_OPERATION_ROOT,
        *,
        database: Path | None = None,
        target: PredictionTarget | None = None,
        target_resolver: TargetResolver | None = None,
        official_outcome_resolver: OfficialOutcomeResolver | None = None,
        history_builder: HistoryBuilder | None = None,
        streams: Sequence[StrategyStream] = STRATEGY_STREAMS,
        clock: Clock | None = None,
    ) -> None:
        if target is not None and target_resolver is not None:
            raise ValueError("target and target_resolver are mutually exclusive")
        self.root = root
        self.database = (
            resolve_local_data_paths().database if database is None else database
        )
        self._target = target
        self._target_resolver = target_resolver
        self._official_outcome_resolver = official_outcome_resolver
        self._history_builder = history_builder
        self._streams = tuple(streams)
        self._clock = _taipei_now if clock is None else clock

    def resolve_next_target(self) -> PredictionTarget | None:
        if self._target is not None:
            return self._target
        if self._target_resolver is not None:
            return self._target_resolver()
        return self._resolve_canonical_due_or_future_target()

    def list_enabled_strategy_streams(self) -> tuple[StrategyStream, ...]:
        return tuple(stream for stream in self._streams if stream.enabled)

    def build_history_snapshot(self, target: PredictionTarget) -> HistorySnapshot:
        if self._history_builder is not None:
            return self._history_builder(target)
        return load_canonical_history(
            self.database,
            target_draw_number=target.draw_number,
            target_draw_date=target.draw_date,
        )

    def run_strategy(
        self,
        stream: StrategyStream,
        target: PredictionTarget,
        history: HistorySnapshot,
    ) -> dict[str, object]:
        results = run_all_enabled_streams(
            self.root,
            target=target,
            history=history,
            streams=(stream,),
            created_at=self._clock(),
        )
        if len(results) != 1:
            raise RuntimeError(f"expected one B649 stream result, got {len(results)}")
        return results[0]

    def prediction_exists(self, target: PredictionTarget, stream: StrategyStream) -> bool:
        for path in iter_prediction_files(self.root, target.draw_number):
            prediction = _read_json_object(path)
            if prediction.get("strategy_id") == stream.strategy_id:
                return True
        return False

    def read_current_outcome(self, target: PredictionTarget) -> dict[str, object] | None:
        path = self.root / "outcomes" / f"{target.draw_number}.json"
        if not path.exists():
            return None
        return _read_json_object(path)

    def resolve_official_outcome(self, target: PredictionTarget) -> dict[str, object] | None:
        if self._official_outcome_resolver is not None:
            return self._official_outcome_resolver(target)

        paths = LocalDataPaths(data_directory=self.database.parent, database=self.database)
        result = SQLiteReplayTargetOutcomeReader(paths).load_target_outcome(
            LotteryType.BIG_LOTTO,
            target.draw_number,
        )
        if result.status is not ReplayTargetOutcomeReadStatus.FOUND:
            return None
        if result.outcome is None:
            raise RuntimeError("official outcome reader returned FOUND without an outcome")
        return {
            "lottery_type": LOTTERY_TYPE,
            "draw_number": result.outcome.target_draw_number,
            "draw_date": result.outcome.target_draw_date.isoformat(),
            "main_numbers": list(result.outcome.winning_main_numbers),
            "special_number": result.outcome.winning_special_number,
            "source": "official:TAIWAN_LOTTERY_OFFICIAL_API",
        }

    def update_outcome(
        self,
        target: PredictionTarget,
        outcome: dict[str, object],
    ) -> dict[str, object]:
        source = outcome.get("source", "official:TAIWAN_LOTTERY_OFFICIAL_API")
        if type(source) is not str or not source.strip():
            raise ValueError("outcome source must be non-empty text")
        main_numbers = _numbers(outcome, "main_numbers")
        special_number = outcome.get("special_number")
        if type(special_number) is not int:
            raise ValueError("special_number must be an integer")
        update_b649_outcome(
            self.root,
            draw_number=target.draw_number,
            main_numbers=main_numbers,
            special_number=special_number,
            source=source,
            updated_at=self._clock(),
        )
        updated = self.read_current_outcome(target)
        if updated is None:
            raise RuntimeError("B649 outcome update did not create a current outcome")
        return updated

    def outcomes_equal(
        self,
        left: dict[str, object],
        right: dict[str, object],
    ) -> bool:
        return (
            left.get("lottery_type") == right.get("lottery_type")
            and left.get("draw_number") == right.get("draw_number")
            and left.get("main_numbers") == right.get("main_numbers")
            and left.get("special_number") == right.get("special_number")
        )

    def should_update_outcome(
        self,
        _target: PredictionTarget,
        current: dict[str, object],
        official: dict[str, object],
    ) -> bool:
        if self.outcomes_equal(current, official):
            return False
        source = current.get("source")
        return type(source) is str and source.startswith("official:")

    def score_prediction(
        self,
        prediction: dict[str, object],
        outcome: dict[str, object],
    ) -> dict[str, object]:
        return score_b649_prediction(prediction, outcome, self._clock())

    def rescore_target(
        self,
        target: PredictionTarget,
        outcome: dict[str, object],
    ) -> tuple[Path, ...]:
        _ = outcome
        return rescore_draw(self.root, target.draw_number, scored_at=self._clock())

    def refresh_reporting(self) -> dict[str, str]:
        ensure_operation_root(self.root)
        paths = {
            "performance": rebuild_performance_ledger(self.root),
            "research_summary": write_research_summary(self.root),
            "head_to_head": build_head_to_head_summary(self.root),
            "history_freshness": rebuild_history_freshness_ledger(
                self.root,
                database=self.database,
            ),
        }
        return {name: str(path) for name, path in paths.items()}

    def history_warnings(self, history: HistorySnapshot) -> tuple[str, ...]:
        latest_known_draw = resolve_latest_known_draw(self.root, self.database)
        freshness = compute_history_freshness(history.cutoff_draw, latest_known_draw)
        warning = cast(str, freshness["history_freshness_warning"])
        return () if warning == "NONE" else (warning,)

    def target_dict(self, target: PredictionTarget) -> dict[str, object]:
        return {
            "lottery_type": target.lottery_type,
            "draw_number": target.draw_number,
            "draw_date": target.draw_date,
            "scheduled_at": target.scheduled_at,
        }

    def stream_dict(self, stream: StrategyStream) -> dict[str, object]:
        return {
            "strategy_id": stream.strategy_id,
            "strategy_version": stream.strategy_version,
            "enabled": stream.enabled,
            "native_ticket_count": stream.native_ticket_count,
        }

    def _resolve_canonical_future_target(self) -> PredictionTarget | None:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        paths = LocalDataPaths(
            data_directory=self.database.parent,
            database=self.database,
        )
        record = SQLiteFutureDrawIdentityReader(
            paths
        ).find_earliest_unpopulated_future(
            LotteryType.BIG_LOTTO,
            now.astimezone(UTC),
        )
        if record is None:
            return None
        selected = record.announcement
        return PredictionTarget(
            lottery_type=LOTTERY_TYPE,
            draw_number=selected.target.draw_number,
            draw_date=selected.target.draw_date.isoformat(),
            scheduled_at=selected.scheduled_at.astimezone(TAIPEI).isoformat(),
        )

    def _resolve_canonical_due_or_future_target(self) -> PredictionTarget | None:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        paths = LocalDataPaths(
            data_directory=self.database.parent,
            database=self.database,
        )
        reader = SQLiteFutureDrawIdentityReader(paths)
        as_of = now.astimezone(UTC)
        record = reader.find_earliest_unpopulated_due(
            LotteryType.BIG_LOTTO,
            as_of,
        )
        if record is None:
            record = reader.find_earliest_unpopulated_future(
                LotteryType.BIG_LOTTO,
                as_of,
            )
        if record is None:
            return None
        selected = record.announcement
        return PredictionTarget(
            lottery_type=LOTTERY_TYPE,
            draw_number=selected.target.draw_number,
            draw_date=selected.target.draw_date.isoformat(),
            scheduled_at=selected.scheduled_at.astimezone(TAIPEI).isoformat(),
        )


def serialize_cycle_result(
    result: ForwardAutoCycleResult[
        PredictionTarget,
        StrategyStream,
        HistorySnapshot,
        dict[str, object],
        dict[str, object],
    ],
    adapter: B649ForwardAutoCycleAdapter,
) -> dict[str, object]:
    """Render the opaque core result for the B649 CLI."""

    return {
        "lottery_type": result.lottery_type,
        "target": None if result.target is None else adapter.target_dict(result.target),
        "outcome_status": result.outcome_status,
        "next_action": result.next_action,
        "warnings": list(result.warnings),
        "existing_streams": [
            adapter.stream_dict(stream) for stream in result.existing_streams
        ],
        "created_predictions": list(result.created_predictions),
        "strategy_failures": [
            {
                "strategy_id": failure.stream.strategy_id,
                "error_type": failure.error_type,
                "error_message": failure.error_message,
            }
            for failure in result.strategy_failures
        ],
        "score_failures": [
            {
                "error_type": failure.error_type,
                "error_message": failure.error_message,
            }
            for failure in result.score_failures
        ],
        "rescore_results": [str(value) for value in result.rescore_results],
        "reporting": result.reporting,
    }


def _read_json_object(path: Path) -> dict[str, object]:
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return cast(dict[str, object], parsed)


def _numbers(value: dict[str, object], key: str) -> tuple[int, ...]:
    raw = value.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be an integer list")
    raw_items = cast(list[object], raw)
    if any(type(item) is not int for item in raw_items):
        raise ValueError(f"{key} must be an integer list")
    return tuple(cast(list[int], raw_items))


def _taipei_now() -> datetime:
    return datetime.now(TAIPEI)


__all__ = [
    "B649ForwardAutoCycleAdapter",
    "serialize_cycle_result",
]
