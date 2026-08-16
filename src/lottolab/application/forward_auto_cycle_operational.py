"""Lottery-neutral file-backed support for forward auto-cycle adapters.

The orchestration order remains in :mod:`forward_auto_cycle_core`.  This
module only supplies reusable target/history value objects and the boring
operational ledger plumbing needed by thin lottery adapters.  It deliberately
does not know any lottery's ticket shape or scoring rules.
"""

from __future__ import annotations

import json
import os
import sqlite3
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TypeVar, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    FileSystemOperationalTargetAnnouncementSource,
    SQLitePreOutcomeCausalHistoryAuthority,
    TargetAnnouncementSourceStatus,
    resolve_pre_outcome_target_operational_paths,
)
from lottolab.strategies.adapters.base import BetAdapterError

HistoryRowT = TypeVar("HistoryRowT")
HistoryRowFactory = Callable[
    [str, str, tuple[int, ...], tuple[int, ...]], HistoryRowT
]
Clock = Callable[[], datetime]
TargetResolver = Callable[[], "ForwardCycleTarget | None"]
OfficialOutcomeResolver = Callable[
    ["ForwardCycleTarget"], dict[str, object] | None
]
HistoryBuilder = Callable[["ForwardCycleTarget"], object]

TAIPEI = ZoneInfo("Asia/Taipei")


@dataclass(frozen=True, slots=True)
class ForwardCycleTarget:
    """One announced draw identity shared by the file-backed adapters."""

    lottery_type: str
    draw_number: str
    draw_date: str
    scheduled_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("lottery_type", self.lottery_type),
            ("draw_number", self.draw_number),
            ("draw_date", self.draw_date),
            ("scheduled_at", self.scheduled_at),
        ):
            if type(value) is not str or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not self.draw_number.isdigit():
            raise ValueError("draw_number must contain only digits")
        date.fromisoformat(self.draw_date)
        scheduled = datetime.fromisoformat(self.scheduled_at)
        if scheduled.tzinfo is None or scheduled.utcoffset() is None:
            raise ValueError("scheduled_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ForwardCycleHistorySnapshot[HistoryRowT_co]:
    """Causal history plus prediction-time freshness identity."""

    rows: tuple[HistoryRowT_co, ...]
    cutoff_draw: str
    cutoff_date: str
    draw_count: int
    history_sha256: str
    latest_known_draw_at_prediction_time: str | None
    history_lag_draws: int | None
    freshness_status: str
    freshness_warning: str
    history_caveat: str = "YES"

    def __post_init__(self) -> None:
        if type(self.rows) is not tuple or not self.rows:
            raise ValueError("history rows must be a non-empty tuple")
        if self.draw_count != len(self.rows):
            raise ValueError("draw_count must equal the number of history rows")
        if type(self.cutoff_draw) is not str or not self.cutoff_draw:
            raise ValueError("cutoff_draw must be non-empty text")
        if type(self.cutoff_date) is not str or not self.cutoff_date:
            raise ValueError("cutoff_date must be non-empty text")
        if type(self.history_sha256) is not str or len(self.history_sha256) != 64:
            raise ValueError("history_sha256 must be a SHA-256 digest")
        if self.history_lag_draws is not None and type(self.history_lag_draws) is not int:
            raise ValueError("history_lag_draws must be an integer or None")


@dataclass(frozen=True, slots=True)
class ForwardCycleStrategyStream:
    """One independently executable strategy stream."""

    strategy_id: str
    strategy_version: str
    enabled: bool
    adapter_factory: Callable[[], object]
    native_ticket_count: int
    strategy_config: dict[str, object] = field(default_factory=dict[str, object])
    producer_fingerprint: str | None = None
    pinned_implementation: str | None = None

    def __post_init__(self) -> None:
        if type(self.strategy_id) is not str or not self.strategy_id.strip():
            raise ValueError("strategy_id must be non-empty text")
        if type(self.strategy_version) is not str or not self.strategy_version.strip():
            raise ValueError("strategy_version must be non-empty text")
        if type(self.native_ticket_count) is not int or self.native_ticket_count <= 0:
            raise ValueError("native_ticket_count must be positive")


def load_causal_history[HistoryRowT](
    database: Path,
    *,
    target: ForwardCycleTarget,
    lottery_type: LotteryType,
    operation_root: Path,
    row_factory: HistoryRowFactory[HistoryRowT],
    as_of: datetime,
) -> ForwardCycleHistorySnapshot[HistoryRowT]:
    """Load one immutable causal prefix from the canonical local draw DB."""

    _require_aware_datetime(as_of, "as_of")
    target_date = date.fromisoformat(target.draw_date)
    observation_target = ObservationTarget(
        lottery_type,
        target.draw_number,
        target_date,
    )
    paths = LocalDataPaths(data_directory=database.parent, database=database)
    history_ref = SQLitePreOutcomeCausalHistoryAuthority(paths).resolve(observation_target)
    with open_database(paths, read_only=True) as connection:
        raw_rows = connection.execute(
            """
            SELECT draw_number, draw_date, main_numbers_json,
                   special_numbers_json
            FROM draws
            WHERE lottery_type = ? AND draw_date <= ?
            """,
            (lottery_type.value, target.draw_date),
        ).fetchall()
        ordered_rows = sorted(
            (
                (
                    str(raw[0]),
                    str(raw[1]),
                    _decode_int_list(raw[2], "main_numbers_json"),
                    _decode_int_list(raw[3], "special_numbers_json"),
                )
                for raw in raw_rows
                if (str(raw[1]), int(str(raw[0])))
                < (target.draw_date, int(target.draw_number))
            ),
            key=lambda row: (row[1], int(row[0]), row[0]),
        )
        if len(ordered_rows) != history_ref.draw_count or not ordered_rows:
            raise RuntimeError("history rows do not match the causal-history identity")
        rows = tuple(row_factory(*row) for row in ordered_rows)
        latest_known_draw = _latest_known_draw_at_prediction_time(
            connection,
            lottery_type=lottery_type,
            as_of=as_of,
        )

    recorded_outcome = _latest_recorded_outcome_at_prediction_time(
        operation_root,
        lottery_type=lottery_type.value,
        as_of=as_of,
    )
    if recorded_outcome is not None and (
        latest_known_draw is None or int(recorded_outcome) > int(latest_known_draw)
    ):
        latest_known_draw = recorded_outcome

    cutoff_draw = history_ref.last_draw_number
    cutoff_date = history_ref.last_draw_date
    if cutoff_draw is None or cutoff_date is None:
        raise RuntimeError("causal-history identity has no cutoff")
    lag, status, warning = _freshness(cutoff_draw, latest_known_draw)
    return ForwardCycleHistorySnapshot(
        rows=rows,
        cutoff_draw=cutoff_draw,
        cutoff_date=cutoff_date.isoformat(),
        draw_count=len(rows),
        history_sha256=history_ref.history_sha256,
        latest_known_draw_at_prediction_time=latest_known_draw,
        history_lag_draws=lag,
        freshness_status=status,
        freshness_warning=warning,
    )


class FileForwardAutoCycleAdapter(ABC):
    """Reusable operational adapter shell with lottery-specific hooks."""

    lottery_type: str
    task_id: str
    default_operation_root: Path
    default_streams: tuple[ForwardCycleStrategyStream, ...]

    def __init__(
        self,
        root: Path | None = None,
        *,
        database: Path | None = None,
        target: ForwardCycleTarget | None = None,
        target_resolver: TargetResolver | None = None,
        official_outcome_resolver: OfficialOutcomeResolver | None = None,
        history_builder: HistoryBuilder | None = None,
        streams: Sequence[ForwardCycleStrategyStream] | None = None,
        clock: Clock | None = None,
    ) -> None:
        if target is not None and target_resolver is not None:
            raise ValueError("target and target_resolver are mutually exclusive")
        self.root = self.default_operation_root if root is None else root
        self.database = (
            resolve_local_data_paths().database if database is None else database
        )
        self._target = target
        self._target_resolver = target_resolver
        self._official_outcome_resolver = official_outcome_resolver
        self._history_builder = history_builder
        self._streams = tuple(self.default_streams if streams is None else streams)
        self._clock = _taipei_now if clock is None else clock

    def resolve_next_target(self) -> ForwardCycleTarget | None:
        if self._target is not None:
            return self._target
        if self._target_resolver is not None:
            return self._target_resolver()
        stored = self._resolve_stored_unfinished_target()
        return stored if stored is not None else self._resolve_announced_target()

    def list_enabled_strategy_streams(self) -> tuple[ForwardCycleStrategyStream, ...]:
        return tuple(stream for stream in self._streams if stream.enabled)

    def build_history_snapshot(
        self, target: ForwardCycleTarget
    ) -> ForwardCycleHistorySnapshot[object]:
        if self._history_builder is not None:
            snapshot = self._history_builder(target)
            if type(snapshot) is not ForwardCycleHistorySnapshot:
                raise TypeError("history_builder must return a ForwardCycleHistorySnapshot")
            return cast(ForwardCycleHistorySnapshot[object], snapshot)
        return self._build_history_snapshot(target)

    @abstractmethod
    def _build_history_snapshot(
        self, target: ForwardCycleTarget
    ) -> ForwardCycleHistorySnapshot[object]:
        """Load the lottery-specific causal row shape."""

    def history_warnings(
        self, history: ForwardCycleHistorySnapshot[object]
    ) -> tuple[str, ...]:
        return () if history.freshness_warning == "NONE" else (history.freshness_warning,)

    def run_strategy(
        self,
        stream: ForwardCycleStrategyStream,
        target: ForwardCycleTarget,
        history: ForwardCycleHistorySnapshot[object],
    ) -> dict[str, object]:
        self._ensure_operation_root()
        observed_at = self._clock()
        _require_aware_datetime(observed_at, "prediction_created_at")
        record: dict[str, object] = {
            "schema_version": "forward-operational-prediction-v1",
            "task_id": self.task_id,
            "prediction_run_id": self._new_prediction_run_id(
                target.draw_number, stream.strategy_id, observed_at
            ),
            "lottery_type": self.lottery_type,
            "draw_number": target.draw_number,
            "draw_date": target.draw_date,
            "scheduled_at": target.scheduled_at,
            "prediction_created_at": observed_at.isoformat(timespec="microseconds"),
            "strategy_id": stream.strategy_id,
            "strategy_version": stream.strategy_version,
            "strategy_config": dict(stream.strategy_config),
            "history_cutoff": {
                "draw_number": history.cutoff_draw,
                "draw_date": history.cutoff_date,
            },
            "history_cutoff_draw": history.cutoff_draw,
            "history_cutoff_date": history.cutoff_date,
            "history_draw_count": history.draw_count,
            "history_sha256": history.history_sha256,
            "latest_known_draw_at_prediction_time": (
                history.latest_known_draw_at_prediction_time
            ),
            "history_lag_draws": history.history_lag_draws,
            "freshness_status": history.freshness_status,
            "history_freshness_warning": history.freshness_warning,
            "history_caveat": history.history_caveat,
            "producer_fingerprint": stream.producer_fingerprint,
            "pinned_implementation": stream.pinned_implementation,
            "prediction_temporal_class": _prediction_temporal_class(
                observed_at, datetime.fromisoformat(target.scheduled_at)
            ),
            "native_ticket_count": stream.native_ticket_count,
        }
        try:
            tickets = self._execute_stream(stream, history)
            if len(tickets) != stream.native_ticket_count:
                raise RuntimeError(
                    f"{stream.strategy_id}: emitted {len(tickets)} tickets, "
                    f"expected {stream.native_ticket_count}"
                )
            record["availability"] = "AVAILABLE"
            record["unavailable_reason"] = None
            record["tickets"] = [
                {
                    "ticket_position": position,
                    **self._ticket_to_record(ticket),
                }
                for position, ticket in enumerate(tickets, start=1)
            ]
        except BetAdapterError as exc:
            record["availability"] = "UNAVAILABLE"
            record["unavailable_reason"] = f"{type(exc).__name__}: {exc}"
            record["tickets"] = []
        except Exception as exc:
            record["availability"] = "TECHNICAL_FAILURE"
            record["unavailable_reason"] = f"{type(exc).__name__}: {exc}"
            record["tickets"] = []

        path = self._save_prediction(record)
        return {**record, "prediction_path": str(path)}

    def prediction_exists(
        self,
        target: ForwardCycleTarget,
        stream: ForwardCycleStrategyStream,
    ) -> bool:
        self._ensure_operation_root()
        return any(
            prediction.get("lottery_type") == self.lottery_type
            and prediction.get("strategy_id") == stream.strategy_id
            for prediction in (
                _read_json_object(path)
                for path in iter_prediction_files(self.root, target.draw_number)
            )
        )

    def read_current_outcome(self, target: ForwardCycleTarget) -> dict[str, object] | None:
        self._ensure_operation_root()
        path = self.root / "outcomes" / f"{target.draw_number}.json"
        if not path.exists():
            return None
        outcome = _read_json_object(path)
        if outcome.get("lottery_type") != self.lottery_type:
            raise ValueError("stored outcome belongs to another lottery")
        return outcome

    def resolve_official_outcome(
        self, target: ForwardCycleTarget
    ) -> dict[str, object] | None:
        if self._official_outcome_resolver is not None:
            return self._official_outcome_resolver(target)
        try:
            paths = LocalDataPaths(
                data_directory=self.database.parent,
                database=self.database,
            )
            with open_database(paths, read_only=True) as connection:
                row = connection.execute(
                    """
                    SELECT draw_date, main_numbers_json, special_numbers_json
                    FROM draws WHERE lottery_type = ? AND draw_number = ?
                    """,
                    (self.lottery_type, target.draw_number),
                ).fetchone()
            if row is None:
                return None
            draw_date = str(row[0])
            if draw_date != target.draw_date:
                raise ValueError("stored target draw date conflicts with target")
            return self._format_draw_outcome(
                target,
                _decode_int_list(row[1], "main_numbers_json"),
                _decode_int_list(row[2], "special_numbers_json"),
                "official:canonical_local_draw_database",
            )
        except (OSError, sqlite3.Error, RuntimeError, ValueError):
            return None

    @abstractmethod
    def _format_draw_outcome(
        self,
        target: ForwardCycleTarget,
        main_numbers: tuple[int, ...],
        special_numbers: tuple[int, ...],
        source: str,
    ) -> dict[str, object]:
        """Format one official draw using the lottery's native outcome shape."""

    def update_outcome(
        self,
        target: ForwardCycleTarget,
        outcome: dict[str, object],
    ) -> dict[str, object]:
        self._ensure_operation_root()
        normalized = self._normalize_outcome(target, outcome)
        path = self.root / "outcomes" / f"{target.draw_number}.json"
        revision = 1
        if path.exists():
            revision = _required_int(_read_json_object(path), "revision") + 1
        updated_at = self._clock()
        _require_aware_datetime(updated_at, "outcome_updated_at")
        payload = {
            "schema_version": "forward-operational-outcome-v1",
            "task_id": self.task_id,
            **normalized,
            "updated_at": updated_at.isoformat(timespec="microseconds"),
            "revision": revision,
        }
        _write_json_atomic(path, payload)
        stored = self.read_current_outcome(target)
        if stored is None:
            raise RuntimeError("outcome update did not create a current outcome")
        return stored

    @abstractmethod
    def _normalize_outcome(
        self,
        target: ForwardCycleTarget,
        outcome: dict[str, object],
    ) -> dict[str, object]:
        """Validate and normalize an owner or official outcome."""

    def outcomes_equal(
        self,
        left: dict[str, object],
        right: dict[str, object],
    ) -> bool:
        return (
            left.get("lottery_type") == self.lottery_type
            and right.get("lottery_type") == self.lottery_type
            and left.get("draw_number") == right.get("draw_number")
            and self._outcome_identity(left) == self._outcome_identity(right)
        )

    @abstractmethod
    def _outcome_identity(self, outcome: dict[str, object]) -> object:
        """Return only native winning values used for equality."""

    def should_update_outcome(
        self,
        _target: ForwardCycleTarget,
        current: dict[str, object],
        official: dict[str, object],
    ) -> bool:
        return not self.outcomes_equal(current, official)

    def score_prediction(
        self,
        prediction: dict[str, object],
        outcome: dict[str, object],
    ) -> dict[str, object]:
        scored_at = self._clock()
        _require_aware_datetime(scored_at, "scored_at")
        return self._score_prediction(prediction, outcome, scored_at)

    @abstractmethod
    def _score_prediction(
        self,
        prediction: dict[str, object],
        outcome: dict[str, object],
        scored_at: datetime,
    ) -> dict[str, object]:
        """Apply the lottery-specific official scoring contract."""

    def rescore_target(
        self,
        target: ForwardCycleTarget,
        outcome: dict[str, object],
    ) -> tuple[Path, ...]:
        self._ensure_operation_root()
        scored_at = self._clock()
        _require_aware_datetime(scored_at, "scored_at")
        score_paths: list[Path] = []
        for prediction_path in iter_prediction_files(self.root, target.draw_number):
            prediction = _read_json_object(prediction_path)
            if prediction.get("lottery_type") != self.lottery_type:
                continue
            try:
                score = self._score_prediction(prediction, outcome, scored_at)
            except Exception as exc:
                score = {
                    "schema_version": "forward-operational-score-v1",
                    "lottery_type": self.lottery_type,
                    "draw_number": target.draw_number,
                    "prediction_run_id": prediction.get("prediction_run_id"),
                    "strategy_id": prediction.get("strategy_id"),
                    "strategy_version": prediction.get("strategy_version"),
                    "score_status": "SCORE_FAILURE",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "scored_at": scored_at.isoformat(timespec="microseconds"),
                }
            path = _score_path(self.root, prediction)
            _write_json_atomic(path, score)
            score_paths.append(path)
        self._write_reporting_files()
        return tuple(score_paths)

    def refresh_reporting(self) -> dict[str, str]:
        self._ensure_operation_root()
        return {name: str(path) for name, path in self._write_reporting_files().items()}

    def target_dict(self, target: ForwardCycleTarget) -> dict[str, object]:
        return {
            "lottery_type": target.lottery_type,
            "draw_number": target.draw_number,
            "draw_date": target.draw_date,
            "scheduled_at": target.scheduled_at,
        }

    def stream_dict(self, stream: ForwardCycleStrategyStream) -> dict[str, object]:
        return {
            "strategy_id": stream.strategy_id,
            "strategy_version": stream.strategy_version,
            "enabled": stream.enabled,
            "native_ticket_count": stream.native_ticket_count,
        }

    @abstractmethod
    def _ticket_to_record(self, ticket: object) -> dict[str, object]:
        """Preserve one native ticket without changing portfolio order."""

    def _execute_stream(
        self,
        stream: ForwardCycleStrategyStream,
        history: ForwardCycleHistorySnapshot[object],
    ) -> tuple[object, ...]:
        adapter = stream.adapter_factory()
        if getattr(adapter, "strategy_id", None) != stream.strategy_id:
            raise RuntimeError(f"{stream.strategy_id}: adapter identity drifted")
        if getattr(adapter, "strategy_version", None) != stream.strategy_version:
            raise RuntimeError(f"{stream.strategy_id}: adapter version drifted")
        lottery_type = LotteryType(self.lottery_type)
        rows = history.rows
        get_bets = getattr(adapter, "get_bets", None)
        if callable(get_bets):
            result = cast(Callable[[object, LotteryType], object], get_bets)(
                rows, lottery_type
            )
            if type(result) is not tuple:
                raise RuntimeError(f"{stream.strategy_id}: get_bets must return a tuple")
            return cast(tuple[object, ...], result)
        get_one_bet = getattr(adapter, "get_one_bet", None)
        if not callable(get_one_bet):
            raise RuntimeError(f"{stream.strategy_id}: adapter has no bet method")
        result = cast(Callable[[object, LotteryType], object], get_one_bet)(
            rows, lottery_type
        )
        if type(result) is not tuple:
            raise RuntimeError(f"{stream.strategy_id}: get_one_bet returned an invalid tuple")
        single_result = cast(tuple[object, ...], result)
        if len(single_result) != 2:
            raise RuntimeError(f"{stream.strategy_id}: get_one_bet returned an invalid tuple")
        return (single_result[0],)

    def _save_prediction(self, prediction: dict[str, object]) -> Path:
        draw_number = _required_text(prediction, "draw_number")
        strategy_id = _required_text(prediction, "strategy_id")
        run_id = _required_text(prediction, "prediction_run_id")
        path = self.root / "predictions" / draw_number / strategy_id / f"{run_id}.json"
        _create_json(path, prediction)
        return path

    def _ensure_operation_root(self) -> None:
        config = {
            "schema_version": "forward-operational-config-v1",
            "task_id": self.task_id,
            "lottery_type": self.lottery_type,
            "operation_root": str(self.root),
            "enabled_strategy_ids": [
                stream.strategy_id for stream in self.list_enabled_strategy_streams()
            ],
        }
        ensure_operation_root(self.root, config=config)

    def _new_prediction_run_id(
        self,
        draw_number: str,
        strategy_id: str,
        created_at: datetime,
    ) -> str:
        stamp = created_at.strftime("%Y%m%dT%H%M%S%f%z").replace("+", "p").replace("-", "m")
        return f"{draw_number}-{strategy_id}-{stamp}-{uuid4().hex[:8]}"

    def _resolve_stored_unfinished_target(self) -> ForwardCycleTarget | None:
        predictions_root = self.root / "predictions"
        if not predictions_root.is_dir():
            return None
        candidates: list[ForwardCycleTarget] = []
        for path in iter_all_prediction_files(self.root):
            prediction = _read_json_object(path)
            if prediction.get("lottery_type") != self.lottery_type:
                continue
            draw_number = _required_text(prediction, "draw_number")
            if (self.root / "outcomes" / f"{draw_number}.json").exists():
                continue
            candidates.append(
                ForwardCycleTarget(
                    lottery_type=self.lottery_type,
                    draw_number=draw_number,
                    draw_date=_required_text(prediction, "draw_date"),
                    scheduled_at=_required_text(prediction, "scheduled_at"),
                )
            )
        return min(candidates, key=lambda value: int(value.draw_number)) if candidates else None

    def _resolve_announced_target(self) -> ForwardCycleTarget | None:
        paths = resolve_pre_outcome_target_operational_paths()
        inventory = FileSystemOperationalTargetAnnouncementSource(
            paths.announcement_file
        ).read()
        if inventory.status is TargetAnnouncementSourceStatus.NOT_CONFIGURED:
            return None
        now = self._clock()
        _require_aware_datetime(now, "clock")
        candidates = tuple(
            announcement
            for announcement in inventory.announcements
            if announcement.target.lottery_type.value == self.lottery_type
            and announcement.scheduled_at > now
        )
        if not candidates:
            return None
        selected = min(
            candidates,
            key=lambda announcement: (
                announcement.scheduled_at,
                int(announcement.target.draw_number),
            ),
        )
        return ForwardCycleTarget(
            lottery_type=self.lottery_type,
            draw_number=selected.target.draw_number,
            draw_date=selected.target.draw_date.isoformat(),
            scheduled_at=selected.scheduled_at.astimezone(TAIPEI).isoformat(),
        )

    def _write_reporting_files(self) -> dict[str, Path]:
        prediction_paths = tuple(iter_all_prediction_files(self.root))
        by_strategy: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {"prediction_count": 0, "available_count": 0, "scored_count": 0}
        )
        freshness_rows: list[dict[str, object]] = []
        for path in prediction_paths:
            prediction = _read_json_object(path)
            key = (
                _required_text(prediction, "strategy_id"),
                _required_text(prediction, "strategy_version"),
            )
            bucket = by_strategy[key]
            bucket["prediction_count"] += 1
            if prediction.get("availability") == "AVAILABLE":
                bucket["available_count"] += 1
            score_path = _score_path(self.root, prediction)
            if score_path.exists():
                score = _read_json_object(score_path)
                if score.get("score_status") == "SCORED":
                    bucket["scored_count"] += 1
            freshness_rows.append(
                {
                    "lottery_type": self.lottery_type,
                    "draw_number": prediction.get("draw_number"),
                    "strategy_id": prediction.get("strategy_id"),
                    "prediction_run_id": prediction.get("prediction_run_id"),
                    "history_cutoff": prediction.get("history_cutoff"),
                    "history_sha256": prediction.get("history_sha256"),
                    "latest_known_draw_at_prediction_time": prediction.get(
                        "latest_known_draw_at_prediction_time"
                    ),
                    "history_lag_draws": prediction.get("history_lag_draws"),
                    "freshness_status": prediction.get("freshness_status"),
                    "history_freshness_warning": prediction.get(
                        "history_freshness_warning"
                    ),
                }
            )
        performance_rows = [
            {
                "lottery_type": self.lottery_type,
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                **values,
            }
            for (strategy_id, strategy_version), values in sorted(by_strategy.items())
        ]
        performance_path = self.root / "performance.jsonl"
        freshness_path = self.root / "history_freshness.jsonl"
        summary_path = self.root / "reporting_summary.json"
        _write_text_atomic(
            performance_path,
            "".join(_canonical_json(row) + "\n" for row in performance_rows),
        )
        _write_text_atomic(
            freshness_path,
            "".join(_canonical_json(row) + "\n" for row in freshness_rows),
        )
        _write_json_atomic(
            summary_path,
            {
                "schema_version": "forward-operational-reporting-v1",
                "task_id": self.task_id,
                "lottery_type": self.lottery_type,
                "prediction_count": len(prediction_paths),
                "strategy_count": len(performance_rows),
                "performance_path": str(performance_path),
                "history_freshness_path": str(freshness_path),
            },
        )
        return {
            "performance": performance_path,
            "history_freshness": freshness_path,
            "summary": summary_path,
        }


def ensure_operation_root(root: Path, *, config: Mapping[str, object]) -> None:
    """Create one operation root and fail closed on cross-lottery reuse."""

    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ("predictions", "outcomes", "scores"):
        (root / name).mkdir(mode=0o700, exist_ok=True)
    config_path = root / "config.json"
    if config_path.exists():
        existing = _read_json_object(config_path)
        if existing.get("lottery_type") != config.get("lottery_type"):
            raise ValueError("operation root is already owned by another lottery")
        if existing.get("task_id") != config.get("task_id"):
            raise ValueError("operation root is already owned by another task")
        return
    _create_json(config_path, config)


def iter_prediction_files(root: Path, draw_number: str) -> tuple[Path, ...]:
    draw_root = root / "predictions" / draw_number
    if not draw_root.is_dir():
        return ()
    return tuple(sorted(path for path in draw_root.rglob("*.json") if path.is_file()))


def iter_all_prediction_files(root: Path) -> Iterator[Path]:
    predictions_root = root / "predictions"
    if not predictions_root.is_dir():
        return iter(())
    return iter(sorted(path for path in predictions_root.rglob("*.json") if path.is_file()))


def _score_path(root: Path, prediction: dict[str, object]) -> Path:
    draw_number = _required_text(prediction, "draw_number")
    strategy_id = _required_text(prediction, "strategy_id")
    run_id = _required_text(prediction, "prediction_run_id")
    return root / "scores" / draw_number / strategy_id / f"{run_id}.json"


def _latest_known_draw_at_prediction_time(
    connection: sqlite3.Connection,
    *,
    lottery_type: LotteryType,
    as_of: datetime,
) -> str | None:
    candidates: list[str] = []
    for draw_number, created_at in connection.execute(
        "SELECT draw_number, created_at FROM draws WHERE lottery_type = ?",
        (lottery_type.value,),
    ).fetchall():
        try:
            stored_at = _parse_datetime(str(created_at))
        except ValueError:
            continue
        if stored_at <= as_of:
            candidates.append(str(draw_number))
    return None if not candidates else max(candidates, key=int)


def _latest_recorded_outcome_at_prediction_time(
    root: Path,
    *,
    lottery_type: str,
    as_of: datetime,
) -> str | None:
    candidates: list[str] = []
    outcomes_root = root / "outcomes"
    if not outcomes_root.is_dir():
        return None
    for path in outcomes_root.glob("*.json"):
        try:
            outcome = _read_json_object(path)
            if outcome.get("lottery_type") != lottery_type:
                continue
            updated_at = _parse_datetime(_required_text(outcome, "updated_at"))
            if updated_at <= as_of:
                candidates.append(_required_text(outcome, "draw_number"))
        except (OSError, ValueError, TypeError):
            continue
    return None if not candidates else max(candidates, key=int)


def _freshness(
    cutoff_draw: str,
    latest_known_draw: str | None,
) -> tuple[int | None, str, str]:
    if latest_known_draw is None:
        return None, "UNKNOWN", "HISTORY_FRESHNESS_UNKNOWN"
    lag = int(latest_known_draw) - int(cutoff_draw)
    if lag > 0:
        return lag, "STALE_HISTORY", "LATEST_DRAW_NOT_INCLUDED"
    return lag, "FRESH", "NONE"


def _decode_int_list(raw: object, label: str) -> tuple[int, ...]:
    parsed: object = json.loads(raw) if type(raw) is str else raw
    if type(parsed) not in (list, tuple):
        raise ValueError(f"{label} must contain an integer list")
    values = cast(list[object] | tuple[object, ...], parsed)
    if any(type(value) is not int for value in values):
        raise ValueError(f"{label} must contain an integer list")
    return tuple(cast(tuple[int, ...], tuple(values)))


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


def _prediction_temporal_class(created_at: datetime, scheduled_at: datetime) -> str:
    _require_aware_datetime(created_at, "created_at")
    _require_aware_datetime(scheduled_at, "scheduled_at")
    return "PRE_DRAW" if created_at < scheduled_at else "POST_DRAW"


def _require_aware_datetime(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _required_text(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if type(result) is not str or not result:
        raise ValueError(f"{key} must be non-empty text")
    return result


def _required_int(value: dict[str, object], key: str) -> int:
    result = value.get(key)
    if type(result) is not int:
        raise ValueError(f"{key} must be an integer")
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_json_object(path: Path) -> dict[str, object]:
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    if type(parsed) is not dict:
        raise ValueError(f"{path} must contain one JSON object")
    raw = cast(dict[object, object], parsed)
    if any(type(key) is not str for key in raw):
        raise ValueError(f"{path} must contain string keys")
    return cast(dict[str, object], raw)


def _create_json(path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            os.chmod(path, 0o600)
            handle.write(_canonical_json(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        if path.exists():
            path.unlink()
        raise


def _write_json_atomic(path: Path, value: object) -> None:
    _write_text_atomic(path, _canonical_json(value) + "\n")


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            os.chmod(temporary, 0o600)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _taipei_now() -> datetime:
    return datetime.now(TAIPEI)


__all__ = [
    "FileForwardAutoCycleAdapter",
    "ForwardCycleHistorySnapshot",
    "ForwardCycleStrategyStream",
    "ForwardCycleTarget",
    "ensure_operation_root",
    "iter_all_prediction_files",
    "iter_prediction_files",
    "load_causal_history",
]
