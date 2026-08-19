"""Minimal operational prediction, outcome correction, and rescore loop for B649.

Predictions are create-only versioned records.  The owner-controlled outcome is
mutable, and every update rebuilds current scores, the performance ledger, and
the compact research summary.  Prediction generation reads only the canonical
local BIG_LOTTO history and never reads an outcome or uses the network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4
from zoneinfo import ZoneInfo

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.prize_evaluation import evaluate_big_lotto_ticket
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    SQLitePreOutcomeCausalHistoryAuthority,
)
from lottolab.strategies.adapters.base import (
    BetAdapter,
    BetAdapterError,
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_batch15 import BigLottoPureColdPredictAdapter
from lottolab.strategies.adapters.biglotto_horizon_minimax import (
    BigLottoHorizonMinimaxDisagreementAdapter,
)
from lottolab.strategies.adapters.biglotto_selected import (
    BigLottoDeviation2BetAdapter,
    BigLottoSocialWisdomAntiPopularityAdapter,
)
from lottolab.strategies.adapters.biglotto_wave1 import BigLottoGraphPredictorAdapter
from lottolab.strategies.adapters.biglotto_wave14 import BigLottoHpsbOptimizerAdapter

TASK_ID = "B649_OPERATIONAL_PREDICTION_LOOP_R1"
LOTTERY_TYPE = LotteryType.BIG_LOTTO.value
TARGET_DRAW_NUMBER = "115000079"
TARGET_DRAW_DATE = "2026-08-14"
TARGET_SCHEDULED_AT = "2026-08-14T20:30:00+08:00"
STRATEGY_ID = "b649_new_horizon_minimax_disagreement_r1"
STRATEGY_VERSION = "v0.1"
PINNED_IMPLEMENTATION = "fc720ea8965faf95021a59d3fe3dae61ae3ef6c3"
PRODUCER_FINGERPRINT = (
    "cf80ae3e6ab8ebeb33c0c1c4e169ab3e0cb800659184bb79898901e244eac007"
)
DEFAULT_OPERATION_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1"
)
TAIPEI = ZoneInfo("Asia/Taipei")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]+", flags=re.ASCII)
_TEMPORAL_CLASSES = ("PRE_DRAW", "POST_DRAW")
_M_KEYS = ("M1+", "M2+", "M3+", "M4+", "M5+", "M6")
_AVAILABILITY_VALUES = ("AVAILABLE", "UNAVAILABLE", "TECHNICAL_FAILURE")
_HEAD_TO_HEAD_METRICS = ("M2+", "official_any_prize")


@dataclass(frozen=True, slots=True)
class HistorySnapshot:
    """Exact causal rows plus the canonical history authority identity."""

    rows: tuple[CausalDrawRow, ...]
    cutoff_draw: str
    cutoff_date: str
    draw_count: int
    history_sha256: str
    history_caveat: str = "YES"


@dataclass(frozen=True, slots=True)
class PredictionTarget:
    """One future draw identity every enabled strategy stream predicts against."""

    lottery_type: str
    draw_number: str
    draw_date: str
    scheduled_at: str


@dataclass(frozen=True, slots=True)
class StrategyStream:
    """One independently configured strategy that produces its own prediction runs.

    ``adapter_factory`` is a zero-argument callable (typically the adapter
    class itself) so onboarding a new stream is one registry entry, never a
    change to the execution loop.
    """

    strategy_id: str
    strategy_version: str
    enabled: bool
    adapter_factory: Callable[[], BetAdapter | PortfolioBetAdapter]
    native_ticket_count: int
    strategy_config: dict[str, object] = field(default_factory=dict[str, object])
    producer_fingerprint: str | None = None
    pinned_implementation: str | None = None


STRATEGY_STREAMS: tuple[StrategyStream, ...] = (
    StrategyStream(
        strategy_id=BigLottoHorizonMinimaxDisagreementAdapter.strategy_id,
        strategy_version=BigLottoHorizonMinimaxDisagreementAdapter.strategy_version,
        enabled=True,
        adapter_factory=BigLottoHorizonMinimaxDisagreementAdapter,
        native_ticket_count=BigLottoHorizonMinimaxDisagreementAdapter.native_ticket_count,
        strategy_config={
            "short_horizon": 30,
            "middle_horizon": 120,
            "full_prefix": True,
            "maximum_cross_ticket_overlap": 2,
        },
        producer_fingerprint=PRODUCER_FINGERPRINT,
        pinned_implementation=PINNED_IMPLEMENTATION,
    ),
    StrategyStream(
        strategy_id=BigLottoSocialWisdomAntiPopularityAdapter.strategy_id,
        strategy_version=BigLottoSocialWisdomAntiPopularityAdapter.strategy_version,
        enabled=True,
        adapter_factory=BigLottoSocialWisdomAntiPopularityAdapter,
        native_ticket_count=1,
    ),
    StrategyStream(
        strategy_id=BigLottoDeviation2BetAdapter.strategy_id,
        strategy_version=BigLottoDeviation2BetAdapter.strategy_version,
        enabled=True,
        adapter_factory=BigLottoDeviation2BetAdapter,
        native_ticket_count=1,
    ),
    StrategyStream(
        strategy_id=BigLottoGraphPredictorAdapter.strategy_id,
        strategy_version=BigLottoGraphPredictorAdapter.strategy_version,
        enabled=True,
        adapter_factory=BigLottoGraphPredictorAdapter,
        native_ticket_count=1,
    ),
    StrategyStream(
        strategy_id=BigLottoPureColdPredictAdapter.strategy_id,
        strategy_version=BigLottoPureColdPredictAdapter.strategy_version,
        enabled=True,
        adapter_factory=BigLottoPureColdPredictAdapter,
        native_ticket_count=1,
    ),
    StrategyStream(
        strategy_id=BigLottoHpsbOptimizerAdapter.strategy_id,
        strategy_version=BigLottoHpsbOptimizerAdapter.strategy_version,
        enabled=True,
        adapter_factory=BigLottoHpsbOptimizerAdapter,
        native_ticket_count=1,
    ),
)


@dataclass(slots=True)
class _MetricAccumulator:
    prediction_count: int = 0
    scored_count: int = 0
    m_counts: dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in _M_KEYS}
    )
    official_any_prize_count: int = 0

    def add(self, score: dict[str, object] | None) -> None:
        self.prediction_count += 1
        if score is None:
            return
        portfolio = _required_object(score, "portfolio_score")
        self.scored_count += 1
        for key in _M_KEYS:
            self.m_counts[key] += int(_required_bool(portfolio, key))
        self.official_any_prize_count += int(
            _required_bool(portfolio, "official_any_prize")
        )

    def canonical_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "prediction_count": self.prediction_count,
            "scored_count": self.scored_count,
            "official_any_prize_count": self.official_any_prize_count,
            "official_any_prize_rate": _rate(
                self.official_any_prize_count, self.scored_count
            ),
        }
        for key in _M_KEYS:
            result[f"{key}_count"] = self.m_counts[key]
            result[f"{key}_rate"] = _rate(self.m_counts[key], self.scored_count)
        return result


@dataclass(slots=True)
class _StrategyAccumulator:
    combined: _MetricAccumulator = field(default_factory=_MetricAccumulator)
    temporal: dict[str, _MetricAccumulator] = field(
        default_factory=lambda: {
            temporal_class: _MetricAccumulator()
            for temporal_class in _TEMPORAL_CLASSES
        }
    )

    def add(self, temporal_class: str, score: dict[str, object] | None) -> None:
        if temporal_class not in self.temporal:
            raise ValueError(f"unsupported prediction_temporal_class: {temporal_class}")
        self.combined.add(score)
        self.temporal[temporal_class].add(score)


def classify_prediction_temporal(
    prediction_created_at: datetime,
    scheduled_at: datetime,
) -> str:
    """Classify by the real timestamp boundary; equality is POST_DRAW."""

    _require_aware_datetime(prediction_created_at, "prediction_created_at")
    _require_aware_datetime(scheduled_at, "scheduled_at")
    return "PRE_DRAW" if prediction_created_at < scheduled_at else "POST_DRAW"


def load_canonical_history(
    database: Path,
    *,
    target_draw_number: str = TARGET_DRAW_NUMBER,
    target_draw_date: str = TARGET_DRAW_DATE,
) -> HistorySnapshot:
    """Load the latest locally available causal BIG_LOTTO history read-only."""

    paths = LocalDataPaths(data_directory=database.parent, database=database)
    target_date = date.fromisoformat(target_draw_date)
    target = ObservationTarget(
        LotteryType.BIG_LOTTO,
        target_draw_number,
        target_date,
    )
    history_ref = SQLitePreOutcomeCausalHistoryAuthority(paths).resolve(target)
    with open_database(paths, read_only=True) as connection:
        raw_rows = connection.execute(
            """
            SELECT draw_number, draw_date, main_numbers_json
            FROM draws
            WHERE lottery_type = ?
              AND (
                    draw_date < ?
                    OR (draw_date = ? AND CAST(draw_number AS INTEGER) < ?)
                  )
            ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC, draw_number ASC, id ASC
            """,
            (LOTTERY_TYPE, target_draw_date, target_draw_date, int(target_draw_number)),
        ).fetchall()

    rows = tuple(
        CausalDrawRow(
            draw=str(raw[0]),
            date=str(raw[1]),
            numbers=_decode_numbers(str(raw[2]), label=f"history draw {raw[0]}"),
        )
        for raw in raw_rows
    )
    if len(rows) != history_ref.draw_count or not rows:
        raise RuntimeError("history rows do not match the canonical causal-history identity")
    cutoff_draw = history_ref.last_draw_number
    cutoff_date = history_ref.last_draw_date
    if cutoff_draw is None or cutoff_date is None:
        raise RuntimeError("canonical causal-history identity has no cutoff")
    if (
        rows[-1].draw != cutoff_draw
        or rows[-1].date != cutoff_date.isoformat()
    ):
        raise RuntimeError("history cutoff does not match the canonical causal-history identity")
    return HistorySnapshot(
        rows=rows,
        cutoff_draw=cutoff_draw,
        cutoff_date=cutoff_date.isoformat(),
        draw_count=history_ref.draw_count,
        history_sha256=history_ref.history_sha256,
    )


def create_prediction_payload(
    history: HistorySnapshot,
    *,
    created_at: datetime | None = None,
    prediction_run_id: str | None = None,
) -> dict[str, object]:
    """Run the canonical adapter and return one create-only prediction record."""

    observed_at = datetime.now(TAIPEI) if created_at is None else created_at
    _require_aware_datetime(observed_at, "created_at")
    scheduled_at = datetime.fromisoformat(TARGET_SCHEDULED_AT)
    run_id = _new_prediction_run_id(observed_at) if prediction_run_id is None else prediction_run_id
    _require_identifier(run_id, "prediction_run_id")

    adapter = BigLottoHorizonMinimaxDisagreementAdapter()
    if (
        adapter.strategy_id != STRATEGY_ID
        or adapter.strategy_version != STRATEGY_VERSION
        or adapter.native_ticket_count != 2
    ):
        raise RuntimeError("canonical Horizon Minimax adapter identity drifted")
    tickets = adapter.get_bets(history.rows, LotteryType.BIG_LOTTO)
    if len(tickets) != 2:
        raise RuntimeError(f"Horizon Minimax emitted {len(tickets)} tickets, expected 2")

    return {
        "schema_version": "b649-operational-prediction-v1",
        "task_id": TASK_ID,
        "prediction_run_id": run_id,
        "lottery_type": LOTTERY_TYPE,
        "draw_number": TARGET_DRAW_NUMBER,
        "draw_date": TARGET_DRAW_DATE,
        "scheduled_at": TARGET_SCHEDULED_AT,
        "prediction_created_at": observed_at.isoformat(timespec="microseconds"),
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "strategy_config": {
            "short_horizon": 30,
            "middle_horizon": 120,
            "full_prefix": True,
            "maximum_cross_ticket_overlap": 2,
        },
        "history_cutoff": {
            "draw_number": history.cutoff_draw,
            "draw_date": history.cutoff_date,
        },
        "history_draw_count": history.draw_count,
        "history_sha256": history.history_sha256,
        "history_caveat": history.history_caveat,
        "producer_fingerprint": PRODUCER_FINGERPRINT,
        "pinned_implementation": PINNED_IMPLEMENTATION,
        "prediction_temporal_class": classify_prediction_temporal(
            observed_at, scheduled_at
        ),
        "tickets": [
            {
                "ticket_position": position,
                "predicted_numbers": list(ticket),
            }
            for position, ticket in enumerate(tickets, start=1)
        ],
    }


def save_prediction(root: Path, prediction: dict[str, object]) -> Path:
    """Persist one prediction under its unique run id without replacement."""

    _ensure_operation_root(root)
    draw_number = _required_identifier(prediction, "draw_number")
    run_id = _required_identifier(prediction, "prediction_run_id")
    path = root / "predictions" / draw_number / f"{run_id}.json"
    _create_json(path, prediction)
    rebuild_performance_ledger(root)
    write_research_summary(root)
    build_head_to_head_summary(root)
    return path


def save_strategy_prediction(root: Path, prediction: dict[str, object]) -> Path:
    """Persist one strategy stream's prediction run without ever replacing a prior run."""

    _ensure_directories(root)
    draw_number = _required_identifier(prediction, "draw_number")
    strategy_id = _required_identifier(prediction, "strategy_id")
    run_id = _required_identifier(prediction, "prediction_run_id")
    path = root / "predictions" / draw_number / strategy_id / f"{run_id}.json"
    _create_json(path, prediction)
    rebuild_performance_ledger(root)
    write_research_summary(root)
    build_head_to_head_summary(root)
    return path


def run_strategy_stream(
    stream: StrategyStream,
    history: HistorySnapshot,
    target: PredictionTarget,
    *,
    created_at: datetime,
    prediction_run_id: str,
) -> dict[str, object]:
    """Execute one strategy stream in isolation against one shared target/history.

    Both an expected adapter decline (``BetAdapterError``) and an unexpected
    technical failure become a stored ``UNAVAILABLE``/``TECHNICAL_FAILURE``
    record instead of propagating, so one stream can never suppress another.
    """

    _require_aware_datetime(created_at, "created_at")
    _require_identifier(prediction_run_id, "prediction_run_id")
    scheduled_at = datetime.fromisoformat(target.scheduled_at)
    record: dict[str, object] = {
        "schema_version": "b649-operational-prediction-v1",
        "task_id": TASK_ID,
        "prediction_run_id": prediction_run_id,
        "lottery_type": target.lottery_type,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "scheduled_at": target.scheduled_at,
        "prediction_created_at": created_at.isoformat(timespec="microseconds"),
        "strategy_id": stream.strategy_id,
        "strategy_version": stream.strategy_version,
        "strategy_config": dict(stream.strategy_config),
        "history_cutoff": {
            "draw_number": history.cutoff_draw,
            "draw_date": history.cutoff_date,
        },
        "history_draw_count": history.draw_count,
        "history_sha256": history.history_sha256,
        "history_caveat": history.history_caveat,
        "producer_fingerprint": stream.producer_fingerprint,
        "pinned_implementation": stream.pinned_implementation,
        "prediction_temporal_class": classify_prediction_temporal(
            created_at, scheduled_at
        ),
        "native_ticket_count": stream.native_ticket_count,
    }
    try:
        lottery_type_enum = LotteryType(target.lottery_type)
        adapter = stream.adapter_factory()
        if (
            adapter.strategy_id != stream.strategy_id
            or adapter.strategy_version != stream.strategy_version
        ):
            raise RuntimeError(
                f"{stream.strategy_id}: adapter identity drifted from its stream config"
            )
        if isinstance(adapter, PortfolioBetAdapter):
            tickets: tuple[tuple[int, ...], ...] = adapter.get_bets(
                history.rows, lottery_type_enum
            )
        else:
            single_ticket, _ = adapter.get_one_bet(history.rows, lottery_type_enum)
            tickets = (single_ticket,)
        if len(tickets) != stream.native_ticket_count:
            raise RuntimeError(
                f"{stream.strategy_id}: emitted {len(tickets)} tickets, "
                f"expected {stream.native_ticket_count}"
            )
        record["availability"] = "AVAILABLE"
        record["unavailable_reason"] = None
        record["tickets"] = [
            {"ticket_position": position, "predicted_numbers": list(ticket)}
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
    return record


def run_all_enabled_streams(
    root: Path,
    *,
    target: PredictionTarget,
    history: HistorySnapshot,
    streams: Sequence[StrategyStream] = STRATEGY_STREAMS,
    created_at: datetime | None = None,
) -> tuple[dict[str, object], ...]:
    """Run every enabled strategy stream independently against one shared
    target and history snapshot, saving each stream's own prediction record.

    The protected ``TARGET_DRAW_NUMBER`` draw is refused outright so its one
    valid PRE_DRAW record can never gain new siblings from this entry point.
    A save/IO failure for one stream is isolated the same way an adapter
    failure is: it becomes a record, never an exception that stops the rest.
    """

    if target.draw_number == TARGET_DRAW_NUMBER:
        raise ValueError(
            f"draw_number {TARGET_DRAW_NUMBER!r} already holds the protected "
            "single-strategy forward record; target a later draw"
        )
    if target.lottery_type != LOTTERY_TYPE:
        raise ValueError(f"unsupported lottery_type: {target.lottery_type!r}")

    observed_at = datetime.now(TAIPEI) if created_at is None else created_at
    _require_aware_datetime(observed_at, "created_at")

    results: list[dict[str, object]] = []
    for stream in streams:
        if not stream.enabled:
            continue
        try:
            run_id = _new_strategy_prediction_run_id(
                target.draw_number, stream.strategy_id, observed_at
            )
            record = run_strategy_stream(
                stream,
                history,
                target,
                created_at=observed_at,
                prediction_run_id=run_id,
            )
            path = save_strategy_prediction(root, record)
            results.append({**record, "prediction_path": str(path)})
        except Exception as exc:
            results.append(
                {
                    "strategy_id": stream.strategy_id,
                    "strategy_version": stream.strategy_version,
                    "availability": "TECHNICAL_FAILURE",
                    "unavailable_reason": f"{type(exc).__name__}: {exc}",
                    "tickets": [],
                    "prediction_path": None,
                }
            )
    return tuple(results)


def update_outcome(
    root: Path,
    *,
    draw_number: str,
    main_numbers: tuple[int, ...],
    special_number: int,
    source: str,
    updated_at: datetime | None = None,
) -> tuple[Path, tuple[Path, ...]]:
    """Create or correct the owner's current outcome, then rescore all runs."""

    _ensure_operation_root(root)
    _require_identifier(draw_number, "draw_number")
    _validate_winning_numbers(main_numbers, special_number)
    if not source.strip():
        raise ValueError("source must be non-empty")
    observed_at = datetime.now(TAIPEI) if updated_at is None else updated_at
    _require_aware_datetime(observed_at, "updated_at")
    outcome_path = root / "outcomes" / f"{draw_number}.json"
    revision = 1
    if outcome_path.exists():
        revision = _required_int(_read_json_object(outcome_path), "revision") + 1
    outcome: dict[str, object] = {
        "schema_version": "b649-operational-outcome-v1",
        "lottery_type": LOTTERY_TYPE,
        "draw_number": draw_number,
        "main_numbers": list(main_numbers),
        "special_number": special_number,
        "source": source,
        "updated_at": observed_at.isoformat(timespec="microseconds"),
        "revision": revision,
    }
    _write_json_atomic(outcome_path, outcome)
    return outcome_path, rescore_draw(root, draw_number, scored_at=observed_at)


def rescore_draw(
    root: Path,
    draw_number: str,
    *,
    scored_at: datetime | None = None,
) -> tuple[Path, ...]:
    """Recompute current scores for every stored prediction of one draw."""

    _require_identifier(draw_number, "draw_number")
    outcome_path = root / "outcomes" / f"{draw_number}.json"
    if not outcome_path.exists():
        raise FileNotFoundError(f"outcome does not exist: {outcome_path}")
    outcome = _read_json_object(outcome_path)
    observed_at = datetime.now(TAIPEI) if scored_at is None else scored_at
    _require_aware_datetime(observed_at, "scored_at")
    score_paths: list[Path] = []
    for prediction_path in _iter_prediction_files(root, draw_number):
        prediction = _read_json_object(prediction_path)
        if not _required_object_list(prediction, "tickets"):
            continue  # UNAVAILABLE/TECHNICAL_FAILURE runs have nothing to score
        score = _score_prediction(prediction, outcome, observed_at)
        run_id = _required_identifier(prediction, "prediction_run_id")
        score_path = root / "scores" / draw_number / f"{run_id}.json"
        _write_json_atomic(score_path, score)
        score_paths.append(score_path)
    rebuild_performance_ledger(root)
    write_research_summary(root)
    build_head_to_head_summary(root)
    return tuple(score_paths)


def rebuild_performance_ledger(root: Path) -> Path:
    """Rebuild update-friendly JSONL aggregates from current predictions/scores."""

    accumulators: dict[tuple[str, str], _StrategyAccumulator] = {}
    availability_counts: dict[tuple[str, str], dict[str, int]] = {}
    for prediction_path in _iter_all_prediction_files(root):
        prediction = _read_json_object(prediction_path)
        strategy_key = (
            _required_str(prediction, "strategy_id"),
            _required_str(prediction, "strategy_version"),
        )
        temporal_class = _required_str(prediction, "prediction_temporal_class")
        draw_number = _required_identifier(prediction, "draw_number")
        run_id = _required_identifier(prediction, "prediction_run_id")
        score_path = root / "scores" / draw_number / f"{run_id}.json"
        score = _read_json_object(score_path) if score_path.exists() else None
        accumulators.setdefault(strategy_key, _StrategyAccumulator()).add(
            temporal_class, score
        )
        counts = availability_counts.setdefault(
            strategy_key, {value: 0 for value in _AVAILABILITY_VALUES}
        )
        counts[_prediction_availability(prediction)] += 1

    rows: list[dict[str, object]] = []
    for (strategy_id, strategy_version), accumulator in sorted(accumulators.items()):
        rows.append(
            {
                "schema_version": "b649-operational-performance-v1",
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "prediction_count": accumulator.combined.prediction_count,
                "scored_count": accumulator.combined.scored_count,
                "PRE_DRAW_count": accumulator.temporal["PRE_DRAW"].prediction_count,
                "POST_DRAW_count": accumulator.temporal["POST_DRAW"].prediction_count,
                "availability_counts": availability_counts[(strategy_id, strategy_version)],
                "combined": accumulator.combined.canonical_dict(),
                "by_temporal_class": {
                    temporal_class: accumulator.temporal[
                        temporal_class
                    ].canonical_dict()
                    for temporal_class in _TEMPORAL_CLASSES
                },
            }
        )
    text = "".join(_canonical_json(row) + "\n" for row in rows)
    path = root / "performance.jsonl"
    _write_text_atomic(path, text)
    return path


def write_research_summary(root: Path) -> Path:
    """Write the compact forward-only summary consumed by research workstreams."""

    score_records: list[dict[str, object]] = []
    hit_distribution = {str(hit_count): 0 for hit_count in range(7)}
    for score_path in sorted((root / "scores").glob("*/*.json")):
        score = _read_json_object(score_path)
        if (
            _required_str(score, "strategy_id") != STRATEGY_ID
            or _required_str(score, "strategy_version") != STRATEGY_VERSION
        ):
            continue  # this summary is scoped to the one mandatory current_strategy
        if _required_str(score, "prediction_temporal_class") != "PRE_DRAW":
            continue
        score_records.append(score)
        for ticket in _required_object_list(score, "ticket_scores"):
            hit_distribution[str(_required_int(ticket, "main_hits"))] += 1

    ledger_rows = _read_json_lines(root / "performance.jsonl")
    strategy_row = next(
        (
            row
            for row in ledger_rows
            if row.get("strategy_id") == STRATEGY_ID
            and row.get("strategy_version") == STRATEGY_VERSION
        ),
        None,
    )
    pre_draw = (
        _required_object(_required_object(strategy_row, "by_temporal_class"), "PRE_DRAW")
        if strategy_row is not None
        else _MetricAccumulator().canonical_dict()
    )
    recent = [
        {
            "draw_number": _required_str(score, "draw_number"),
            "prediction_run_id": _required_str(score, "prediction_run_id"),
            "scored_at": _required_str(score, "scored_at"),
            "portfolio_main_hits": _required_int(
                _required_object(score, "portfolio_score"), "max_main_hits"
            ),
            "official_any_prize": _required_bool(
                _required_object(score, "portfolio_score"), "official_any_prize"
            ),
        }
        for score in score_records[-10:]
    ]
    summary: dict[str, object] = {
        "schema_version": "b649-operational-research-summary-v1",
        "current_strategy": {
            "strategy_id": STRATEGY_ID,
            "strategy_version": STRATEGY_VERSION,
        },
        "number_of_forward_observations": _required_int(pre_draw, "scored_count"),
        "M2+_rate": pre_draw.get("M2+_rate"),
        "official_any_prize_rate": pre_draw.get("official_any_prize_rate"),
        "recent_rolling_results": recent,
        "ticket_level_hit_distribution": hit_distribution,
        "interpretation": (
            "Descriptive forward observations only; small samples do not establish "
            "predictive advantage."
        ),
    }
    path = root / "research-summary.json"
    _write_json_atomic(path, summary)
    return path


def build_head_to_head_summary(root: Path) -> Path:
    """Rebuild pairwise PRE_DRAW forward comparisons across strategy streams.

    Uses each strategy's most-recently-scored PRE_DRAW run per draw as that
    strategy's one observation for the target, so re-running a strategy
    before draw time never double-counts the same target. Descriptive only;
    no significance test.
    """

    latest: dict[tuple[str, str, str], dict[str, object]] = {}
    for score_path in sorted((root / "scores").glob("*/*.json")):
        score = _read_json_object(score_path)
        if _required_str(score, "prediction_temporal_class") != "PRE_DRAW":
            continue
        draw_number = _required_str(score, "draw_number")
        strategy_id = _required_str(score, "strategy_id")
        strategy_version = _required_str(score, "strategy_version")
        scored_at = _required_str(score, "scored_at")
        key = (draw_number, strategy_id, strategy_version)
        existing = latest.get(key)
        if existing is None or scored_at >= _required_str(existing, "scored_at"):
            latest[key] = score

    by_draw: dict[str, dict[tuple[str, str], dict[str, object]]] = {}
    for (draw_number, strategy_id, strategy_version), score in latest.items():
        by_draw.setdefault(draw_number, {})[(strategy_id, strategy_version)] = score

    pair_stats: dict[tuple[tuple[str, str], tuple[str, str], str], dict[str, int]] = {}
    for strategies in by_draw.values():
        keys = sorted(strategies)
        for index, key_a in enumerate(keys):
            for key_b in keys[index + 1 :]:
                portfolio_a = _required_object(strategies[key_a], "portfolio_score")
                portfolio_b = _required_object(strategies[key_b], "portfolio_score")
                for metric in _HEAD_TO_HEAD_METRICS:
                    stats = pair_stats.setdefault(
                        (key_a, key_b, metric),
                        {
                            "common_scored_targets": 0,
                            "a_better": 0,
                            "b_better": 0,
                            "ties": 0,
                        },
                    )
                    stats["common_scored_targets"] += 1
                    value_a = _required_bool(portfolio_a, metric)
                    value_b = _required_bool(portfolio_b, metric)
                    if value_a and not value_b:
                        stats["a_better"] += 1
                    elif value_b and not value_a:
                        stats["b_better"] += 1
                    else:
                        stats["ties"] += 1

    rows: list[dict[str, object]] = [
        {
            "schema_version": "b649-operational-head-to-head-v1",
            "strategy_a": key_a[0],
            "strategy_a_version": key_a[1],
            "strategy_b": key_b[0],
            "strategy_b_version": key_b[1],
            "metric": metric,
            **stats,
        }
        for (key_a, key_b, metric), stats in sorted(pair_stats.items())
    ]
    text = "".join(_canonical_json(row) + "\n" for row in rows)
    path = root / "head_to_head.jsonl"
    _write_text_atomic(path, text)
    return path


def _read_ingested_draws(database: Path) -> tuple[tuple[str, datetime], ...]:
    """Every local BIG_LOTTO draw_number with its own row ``created_at``.

    ``created_at`` is when the row was inserted into the local database, not
    the real-world draw date, so a bulk re-ingestion of old history does not
    retroactively change when a draw first became locally available.
    """

    if not database.exists():
        return ()
    paths = LocalDataPaths(data_directory=database.parent, database=database)
    with open_database(paths, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT draw_number, created_at
            FROM draws
            WHERE lottery_type = ?
            ORDER BY CAST(draw_number AS INTEGER) DESC
            """,
            (LOTTERY_TYPE,),
        ).fetchall()
    return tuple(
        (str(draw_number), datetime.fromisoformat(str(created_at)))
        for draw_number, created_at in rows
    )


def _read_recorded_outcomes(root: Path) -> tuple[tuple[str, datetime], ...]:
    """Every owner-recorded outcome's draw_number and its own ``updated_at``."""

    outcomes_dir = root / "outcomes"
    if not outcomes_dir.is_dir():
        return ()
    return tuple(
        (
            _required_str(outcome, "draw_number"),
            datetime.fromisoformat(_required_str(outcome, "updated_at")),
        )
        for outcome in (
            _read_json_object(outcome_path) for outcome_path in outcomes_dir.glob("*.json")
        )
    )


def _latest_known_draw_before(
    ingested_draws: tuple[tuple[str, datetime], ...],
    recorded_outcomes: tuple[tuple[str, datetime], ...],
    as_of: datetime,
) -> str | None:
    """The latest draw_number whose own timestamp is at or before ``as_of``.

    Pure: takes already-fetched candidates instead of doing I/O, so it can be
    reused per-prediction without reopening the database or re-reading every
    outcome file once per prediction.
    """

    _require_aware_datetime(as_of, "as_of")
    candidates = [
        draw_number
        for draw_number, known_at in (*ingested_draws, *recorded_outcomes)
        if known_at <= as_of
    ]
    return None if not candidates else max(candidates, key=int)


def resolve_latest_known_draw_at(root: Path, database: Path, as_of: datetime) -> str | None:
    """The latest BIG_LOTTO draw actually known locally before ``as_of``.

    Compares the canonical database's own row ``created_at`` and every
    owner-recorded outcome's own ``updated_at`` against ``as_of``, so an old
    prediction's freshness reflects what was known when it was generated —
    never inflated by a draw or outcome that only became known later. Read-only;
    never touches the network.
    """

    return _latest_known_draw_before(
        _read_ingested_draws(database), _read_recorded_outcomes(root), as_of
    )


def resolve_latest_known_draw(root: Path, database: Path) -> str | None:
    """Compatibility alias: the latest known draw as of right now.

    Prefer :func:`resolve_latest_known_draw_at` for classifying a specific
    prediction's freshness — "now" keeps advancing, so using it to classify
    an old prediction makes that prediction look increasingly stale purely
    because time has passed, not because its history actually changed.
    """

    return resolve_latest_known_draw_at(root, database, datetime.now(TAIPEI))


def compute_history_freshness(
    history_cutoff_draw: str, latest_known_draw: str | None
) -> dict[str, object]:
    """Compare one causal-history cutoff against a given latest known draw.

    Warning-only classification: the caller must never use this to block
    prediction generation, saving, or rescoring. Generic: the caller decides
    what "latest known" means (e.g. as of now, or as of prediction time).
    """

    lag = (
        None
        if latest_known_draw is None
        else int(latest_known_draw) - int(history_cutoff_draw)
    )
    if lag is None:
        status, warning = "UNKNOWN", "HISTORY_FRESHNESS_UNKNOWN"
    elif lag > 0:
        status, warning = "STALE_HISTORY", "LATEST_DRAW_NOT_INCLUDED"
    else:
        status, warning = "FRESH", "NONE"
    return {
        "history_cutoff_draw": history_cutoff_draw,
        "latest_known_draw": latest_known_draw,
        "history_lag_draws": lag,
        "history_freshness_status": status,
        "history_freshness_warning": warning,
    }


def compute_history_freshness_at_prediction_time(
    history_cutoff_draw: str, latest_known_draw_at_prediction_time: str | None
) -> dict[str, object]:
    """Freshness computed against what was known when a prediction was made.

    Delegates classification to :func:`compute_history_freshness` and
    republishes the result under prediction-time field names, keeping the
    original generic names as compatibility aliases.
    """

    base = compute_history_freshness(history_cutoff_draw, latest_known_draw_at_prediction_time)
    return {
        **base,
        "latest_known_draw_at_prediction_time": base["latest_known_draw"],
        "history_lag_draws_at_prediction_time": base["history_lag_draws"],
        "history_freshness_status_at_prediction_time": base["history_freshness_status"],
        "history_freshness_warning_at_prediction_time": base["history_freshness_warning"],
    }


def build_current_target_freshness_report(
    root: Path, *, draw_number: str, database: Path
) -> dict[str, object]:
    """Prediction-time freshness of the most-recently-created stored
    prediction for one target.

    Purely descriptive: reads already-saved prediction files and never
    creates, rewrites, or rescores anything.
    """

    prediction_files = _iter_prediction_files(root, draw_number)
    if not prediction_files:
        raise FileNotFoundError(f"no stored predictions for draw_number {draw_number!r}")
    latest_prediction = max(
        (_read_json_object(path) for path in prediction_files),
        key=lambda prediction: datetime.fromisoformat(
            _required_str(prediction, "prediction_created_at")
        ),
    )
    history_cutoff_draw = _required_str(
        _required_object(latest_prediction, "history_cutoff"), "draw_number"
    )
    prediction_created_at = datetime.fromisoformat(
        _required_str(latest_prediction, "prediction_created_at")
    )
    latest_known_draw_at_prediction_time = resolve_latest_known_draw_at(
        root, database, prediction_created_at
    )
    return {
        "draw_number": draw_number,
        **compute_history_freshness_at_prediction_time(
            history_cutoff_draw, latest_known_draw_at_prediction_time
        ),
    }


def rebuild_history_freshness_ledger(root: Path, *, database: Path) -> Path:
    """Rebuild per-strategy freshness counts across every stored prediction.

    Each prediction is classified against what was known at its own
    ``prediction_created_at``, not against today's latest known draw, so an
    old prediction's freshness never drifts as new outcomes arrive later. A
    pure reporting overlay derived from files already on disk: it never edits
    a prediction record and is never invoked from the write path, so stale or
    unknown freshness can never block prediction, saving, or rescoring.
    Buckets stale counts by lag so later research can compare FRESH vs
    STALE_1_DRAW vs STALE_2_PLUS without recomputing history.
    """

    ingested_draws = _read_ingested_draws(database)
    recorded_outcomes = _read_recorded_outcomes(root)

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for prediction_path in _iter_all_prediction_files(root):
        prediction = _read_json_object(prediction_path)
        strategy_key = (
            _required_str(prediction, "strategy_id"),
            _required_str(prediction, "strategy_version"),
        )
        history_cutoff_draw = _required_str(
            _required_object(prediction, "history_cutoff"), "draw_number"
        )
        prediction_created_at = datetime.fromisoformat(
            _required_str(prediction, "prediction_created_at")
        )
        latest_known_draw_at_prediction_time = _latest_known_draw_before(
            ingested_draws, recorded_outcomes, prediction_created_at
        )
        freshness = compute_history_freshness_at_prediction_time(
            history_cutoff_draw, latest_known_draw_at_prediction_time
        )
        bucket = counts.setdefault(
            strategy_key,
            {
                "fresh_prediction_count": 0,
                "stale_prediction_count": 0,
                "unknown_freshness_count": 0,
                "stale_1_draw_count": 0,
                "stale_2_plus_count": 0,
            },
        )
        status = cast(str, freshness["history_freshness_status_at_prediction_time"])
        if status == "FRESH":
            bucket["fresh_prediction_count"] += 1
        elif status == "UNKNOWN":
            bucket["unknown_freshness_count"] += 1
        else:
            bucket["stale_prediction_count"] += 1
            if cast(int, freshness["history_lag_draws_at_prediction_time"]) == 1:
                bucket["stale_1_draw_count"] += 1
            else:
                bucket["stale_2_plus_count"] += 1

    rows: list[dict[str, object]] = [
        {
            "schema_version": "b649-operational-history-freshness-v2",
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            **bucket,
        }
        for (strategy_id, strategy_version), bucket in sorted(counts.items())
    ]
    text = "".join(_canonical_json(row) + "\n" for row in rows)
    path = root / "history_freshness.jsonl"
    _write_text_atomic(path, text)
    return path


def _most_recent_target_draw_number(root: Path) -> str:
    """The numerically largest draw_number with any stored prediction."""

    predictions_root = root / "predictions"
    draw_numbers = (
        [entry.name for entry in predictions_root.iterdir() if entry.is_dir()]
        if predictions_root.is_dir()
        else []
    )
    if not draw_numbers:
        raise FileNotFoundError(f"no stored predictions under {predictions_root}")
    return max(draw_numbers, key=int)


def _score_prediction(
    prediction: dict[str, object],
    outcome: dict[str, object],
    scored_at: datetime,
) -> dict[str, object]:
    draw_number = _required_str(prediction, "draw_number")
    if draw_number != _required_str(outcome, "draw_number"):
        raise ValueError("prediction and outcome draw_number differ")
    winning_main = _numbers_from_object(outcome, "main_numbers")
    winning_special = _required_int(outcome, "special_number")
    ticket_scores: list[dict[str, object]] = []
    for ticket in _required_object_list(prediction, "tickets"):
        predicted = _numbers_from_object(ticket, "predicted_numbers")
        evaluation = evaluate_big_lotto_ticket(
            predicted_main_numbers=predicted,
            predicted_special_number=None,
            winning_main_numbers=winning_main,
            winning_special_number=winning_special,
        )
        ticket_score: dict[str, object] = {
            "ticket_position": _required_int(ticket, "ticket_position"),
            "predicted_numbers": list(predicted),
            "main_hits": evaluation.zone1_hits,
            "special_hit": evaluation.zone2_hit,
            "official_any_prize": evaluation.is_winner,
            "official_prize_tier": evaluation.prize_tier,
        }
        ticket_score.update(_m_flags(evaluation.zone1_hits))
        ticket_scores.append(ticket_score)

    portfolio: dict[str, object] = {
        "max_main_hits": max(_required_int(ticket, "main_hits") for ticket in ticket_scores),
        "special_hit": any(_required_bool(ticket, "special_hit") for ticket in ticket_scores),
        "official_any_prize": any(
            _required_bool(ticket, "official_any_prize") for ticket in ticket_scores
        ),
        "winning_ticket_count": sum(
            int(_required_bool(ticket, "official_any_prize")) for ticket in ticket_scores
        ),
    }
    for key in _M_KEYS:
        portfolio[key] = any(_required_bool(ticket, key) for ticket in ticket_scores)
    return {
        "schema_version": "b649-operational-score-v1",
        "lottery_type": LOTTERY_TYPE,
        "draw_number": draw_number,
        "prediction_run_id": _required_str(prediction, "prediction_run_id"),
        "strategy_id": _required_str(prediction, "strategy_id"),
        "strategy_version": _required_str(prediction, "strategy_version"),
        "prediction_temporal_class": _required_str(
            prediction, "prediction_temporal_class"
        ),
        "outcome_revision": _required_int(outcome, "revision"),
        "outcome_updated_at": _required_str(outcome, "updated_at"),
        "outcome_source": _required_str(outcome, "source"),
        "scored_at": scored_at.isoformat(timespec="microseconds"),
        "ticket_scores": ticket_scores,
        "portfolio_score": portfolio,
    }


def ensure_operation_root(root: Path) -> None:
    """Public adapter hook that preserves the existing B649 root contract."""

    _ensure_operation_root(root)


def iter_prediction_files(root: Path, draw_number: str) -> tuple[Path, ...]:
    """Public adapter hook for the legacy flat/nested prediction layout."""

    return _iter_prediction_files(root, draw_number)


def score_prediction(
    prediction: dict[str, object],
    outcome: dict[str, object],
    scored_at: datetime,
) -> dict[str, object]:
    """Public adapter hook for the existing B649 scoring implementation."""

    return _score_prediction(prediction, outcome, scored_at)


def _ensure_directories(root: Path) -> None:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ("predictions", "outcomes", "scores"):
        (root / name).mkdir(mode=0o700, exist_ok=True)


def _ensure_operation_root(root: Path) -> None:
    _ensure_directories(root)
    expected: dict[str, object] = {
        "schema_version": "b649-operational-config-v1",
        "task_id": TASK_ID,
        "operation_root": str(root),
        "target": {
            "lottery_type": LOTTERY_TYPE,
            "draw_number": TARGET_DRAW_NUMBER,
            "draw_date": TARGET_DRAW_DATE,
            "scheduled_at": TARGET_SCHEDULED_AT,
        },
        "strategy": {
            "strategy_id": STRATEGY_ID,
            "strategy_version": STRATEGY_VERSION,
            "expected_native_tickets": 2,
            "pinned_implementation": PINNED_IMPLEMENTATION,
            "producer_fingerprint": PRODUCER_FINGERPRINT,
        },
        "history_caveat": "YES",
    }
    config_path = root / "config.json"
    if config_path.exists():
        if _read_json_object(config_path) != expected:
            raise RuntimeError("existing operation config conflicts with this task")
    else:
        _write_json_atomic(config_path, expected)


def _iter_prediction_files(root: Path, draw_number: str) -> tuple[Path, ...]:
    """Discover one draw's prediction files: flat legacy plus nested per-strategy."""

    base = root / "predictions" / draw_number
    if not base.is_dir():
        return ()
    return tuple(sorted((*base.glob("*.json"), *base.glob("*/*.json")), key=str))


def _iter_all_prediction_files(root: Path) -> tuple[Path, ...]:
    """Discover every stored prediction file: flat legacy plus nested per-strategy."""

    predictions_root = root / "predictions"
    if not predictions_root.is_dir():
        return ()
    return tuple(
        sorted(
            (*predictions_root.glob("*/*.json"), *predictions_root.glob("*/*/*.json")),
            key=str,
        )
    )


def _prediction_availability(prediction: dict[str, object]) -> str:
    """Legacy records predate this field; a missing value means AVAILABLE."""

    value = prediction.get("availability", "AVAILABLE")
    if value not in _AVAILABILITY_VALUES:
        raise ValueError(f"unsupported availability: {value!r}")
    return cast(str, value)


def _validate_winning_numbers(
    main_numbers: tuple[int, ...], special_number: int
) -> None:
    rule = BIG_LOTTO_RULE_CONTRACT
    if (
        type(main_numbers) is not tuple
        or len(main_numbers) != rule.main_number_count
        or any(type(number) is not int for number in main_numbers)
        or main_numbers != tuple(sorted(main_numbers))
        or len(set(main_numbers)) != len(main_numbers)
        or any(
            not rule.main_number_min <= number <= rule.main_number_max
            for number in main_numbers
        )
    ):
        raise ValueError("main_numbers must be six unique ascending BIG_LOTTO numbers")
    if type(special_number) is not int or not 1 <= special_number <= 49:
        raise ValueError("special_number must be an integer from 1 through 49")
    if special_number in main_numbers:
        raise ValueError("special_number must not overlap main_numbers")


def _decode_numbers(raw: str, *, label: str) -> tuple[int, ...]:
    parsed: object = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"{label} must contain a JSON integer list")
    parsed_list = cast(list[object], parsed)
    if any(type(item) is not int for item in parsed_list):
        raise ValueError(f"{label} must contain a JSON integer list")
    return tuple(cast(list[int], parsed_list))


def _numbers_from_object(value: dict[str, object], key: str) -> tuple[int, ...]:
    raw = value.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be an integer list")
    raw_list = cast(list[object], raw)
    if any(type(item) is not int for item in raw_list):
        raise ValueError(f"{key} must be an integer list")
    return tuple(cast(list[int], raw_list))


def _m_flags(main_hits: int) -> dict[str, bool]:
    return {
        "M1+": main_hits >= 1,
        "M2+": main_hits >= 2,
        "M3+": main_hits >= 3,
        "M4+": main_hits >= 4,
        "M5+": main_hits >= 5,
        "M6": main_hits == 6,
    }


def _rate(count: int, total: int) -> float | None:
    return None if total == 0 else round(count / total, 8)


def _new_prediction_run_id(created_at: datetime) -> str:
    stamp = created_at.strftime("%Y%m%dT%H%M%S%f%z").replace("+", "p").replace("-", "m")
    return f"{TARGET_DRAW_NUMBER}-{stamp}-{uuid4().hex[:8]}"


def _new_strategy_prediction_run_id(
    draw_number: str, strategy_id: str, created_at: datetime
) -> str:
    stamp = created_at.strftime("%Y%m%dT%H%M%S%f%z").replace("+", "p").replace("-", "m")
    return f"{draw_number}-{strategy_id}-{stamp}-{uuid4().hex[:8]}"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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


def _read_json_object(path: Path) -> dict[str, object]:
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} must contain one JSON object")
    parsed_dict = cast(dict[object, object], parsed)
    if any(type(key) is not str for key in parsed_dict):
        raise ValueError(f"{path} must contain one JSON object")
    return cast(dict[str, object], parsed_dict)


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            parsed: object = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError(f"{path} contains a non-object JSONL row")
            rows.append(cast(dict[str, object], parsed))
    return rows


def _required_str(value: dict[str, object], key: str) -> str:
    result = value.get(key)
    if type(result) is not str or not result:
        raise ValueError(f"{key} must be a non-empty string")
    return result


def _required_identifier(value: dict[str, object], key: str) -> str:
    result = _required_str(value, key)
    _require_identifier(result, key)
    return result


def _required_int(value: dict[str, object], key: str) -> int:
    result = value.get(key)
    if type(result) is not int:
        raise ValueError(f"{key} must be an integer")
    return result


def _required_bool(value: dict[str, object], key: str) -> bool:
    result = value.get(key)
    if type(result) is not bool:
        raise ValueError(f"{key} must be a boolean")
    return result


def _required_object(value: dict[str, object] | None, key: str) -> dict[str, object]:
    if value is None:
        raise ValueError(f"{key} is unavailable")
    result = value.get(key)
    if not isinstance(result, dict):
        raise ValueError(f"{key} must be an object")
    result_dict = cast(dict[object, object], result)
    if any(type(item) is not str for item in result_dict):
        raise ValueError(f"{key} must be an object")
    return cast(dict[str, object], result_dict)


def _required_object_list(
    value: dict[str, object], key: str
) -> list[dict[str, object]]:
    result = value.get(key)
    if not isinstance(result, list):
        raise ValueError(f"{key} must be an object list")
    result_list = cast(list[object], result)
    if any(not isinstance(item, dict) for item in result_list):
        raise ValueError(f"{key} must be an object list")
    return cast(list[dict[str, object]], result_list)


def _require_identifier(value: str, label: str) -> None:
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} contains unsupported characters")


def _require_aware_datetime(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _parse_main_numbers(raw: str) -> tuple[int, ...]:
    try:
        return tuple(int(item.strip()) for item in raw.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("main numbers must be comma-separated integers") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--operation-root",
        type=Path,
        default=DEFAULT_OPERATION_ROOT,
        help="Task-owned operation root.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    predict = subparsers.add_parser("predict", help="Generate and save a new prediction run.")
    predict.add_argument("--database", type=Path)
    predict.add_argument(
        "--all-enabled",
        action="store_true",
        help=(
            "Run every enabled strategy stream against one explicit --target-* "
            "future draw, instead of the single legacy Horizon Minimax run."
        ),
    )
    predict.add_argument("--target-lottery-type", default=LOTTERY_TYPE)
    predict.add_argument("--target-draw-number")
    predict.add_argument("--target-draw-date")
    predict.add_argument("--target-scheduled-at")
    outcome = subparsers.add_parser(
        "update-outcome", help="Create/correct an outcome and automatically rescore."
    )
    outcome.add_argument("--draw-number", default=TARGET_DRAW_NUMBER)
    outcome.add_argument("--main-numbers", required=True, type=_parse_main_numbers)
    outcome.add_argument("--special-number", required=True, type=int)
    outcome.add_argument("--source", required=True)
    rescore = subparsers.add_parser("rescore", help="Recompute scores for one draw.")
    rescore.add_argument("--draw-number", default=TARGET_DRAW_NUMBER)
    subparsers.add_parser(
        "summary", help="Print the performance ledger and head-to-head comparison table."
    )
    freshness = subparsers.add_parser(
        "freshness",
        help=(
            "Report whether stored predictions' causal history includes the "
            "latest known draw. Warning only; never blocks prediction."
        ),
    )
    freshness.add_argument("--database", type=Path)
    freshness.add_argument(
        "--draw-number",
        help=(
            "Target draw number to report on; defaults to the most recent "
            "draw with any stored prediction."
        ),
    )
    auto_cycle = subparsers.add_parser(
        "auto-cycle",
        help="Run one shared forward auto-cycle for a supported lottery adapter.",
    )
    auto_cycle.add_argument(
        "--lottery",
        required=True,
        type=str.upper,
        choices=("B649", "T539", "P638", "ALL"),
    )
    auto_cycle.add_argument("--database", type=Path)
    auto_cycle.add_argument("--target-draw-number")
    auto_cycle.add_argument("--target-draw-date")
    auto_cycle.add_argument("--target-scheduled-at")
    return parser


def _target_from_args(args: argparse.Namespace) -> PredictionTarget:
    draw_number = cast(str | None, args.target_draw_number)
    draw_date = cast(str | None, args.target_draw_date)
    scheduled_at = cast(str | None, args.target_scheduled_at)
    if draw_number is None or draw_date is None or scheduled_at is None:
        raise SystemExit(
            "--all-enabled requires --target-draw-number, --target-draw-date, "
            "and --target-scheduled-at"
        )
    return PredictionTarget(
        lottery_type=cast(str, args.target_lottery_type),
        draw_number=draw_number,
        draw_date=draw_date,
        scheduled_at=scheduled_at,
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = cast(Path, args.operation_root)
    command = cast(str, args.command)
    if command == "auto-cycle":
        lottery = cast(str, args.lottery)
        if lottery != "B649":
            raise SystemExit(
                f"auto-cycle adapter for {lottery} is not implemented by design in R1"
            )
        supplied_database = cast(Path | None, args.database)
        database = (
            resolve_local_data_paths().database
            if supplied_database is None
            else supplied_database
        )
        target_values = (
            cast(str | None, args.target_draw_number),
            cast(str | None, args.target_draw_date),
            cast(str | None, args.target_scheduled_at),
        )
        if any(value is not None for value in target_values) and not all(
            value is not None for value in target_values
        ):
            raise SystemExit(
                "auto-cycle target override requires --target-draw-number, "
                "--target-draw-date, and --target-scheduled-at together"
            )
        from lottolab.application.forward_auto_cycle_core import ForwardAutoCycleCore
        from tools.b649_forward_auto_cycle_adapter import (
            B649ForwardAutoCycleAdapter,
            serialize_cycle_result,
        )

        target = (
            None
            if not all(value is not None for value in target_values)
            else PredictionTarget(
                lottery_type=LOTTERY_TYPE,
                draw_number=cast(str, target_values[0]),
                draw_date=cast(str, target_values[1]),
                scheduled_at=cast(str, target_values[2]),
            )
        )
        adapter = B649ForwardAutoCycleAdapter(
            root,
            database=database,
            target=target,
        )
        result = ForwardAutoCycleCore[
            PredictionTarget,
            StrategyStream,
            HistorySnapshot,
            dict[str, object],
            dict[str, object],
        ](adapter).run()
        print(_canonical_json(serialize_cycle_result(result, adapter)))
        return 0
    if command == "predict":
        supplied_database = cast(Path | None, args.database)
        database = (
            resolve_local_data_paths().database
            if supplied_database is None
            else supplied_database
        )
        if cast(bool, args.all_enabled):
            target = _target_from_args(args)
            history = load_canonical_history(
                database,
                target_draw_number=target.draw_number,
                target_draw_date=target.draw_date,
            )
            results = run_all_enabled_streams(root, target=target, history=history)
            print(_canonical_json({"results": results}))
            return 0
        prediction = create_prediction_payload(load_canonical_history(database))
        path = save_prediction(root, prediction)
        print(
            _canonical_json(
                {
                    "prediction_path": str(path),
                    "prediction_run_id": prediction["prediction_run_id"],
                    "prediction_created_at": prediction["prediction_created_at"],
                    "prediction_temporal_class": prediction[
                        "prediction_temporal_class"
                    ],
                    "tickets": prediction["tickets"],
                }
            )
        )
        return 0
    if command == "update-outcome":
        outcome_path, score_paths = update_outcome(
            root,
            draw_number=cast(str, args.draw_number),
            main_numbers=cast(tuple[int, ...], args.main_numbers),
            special_number=cast(int, args.special_number),
            source=cast(str, args.source),
        )
        print(
            _canonical_json(
                {
                    "outcome_path": str(outcome_path),
                    "score_paths": [str(path) for path in score_paths],
                }
            )
        )
        return 0
    if command == "summary":
        print(
            _canonical_json(
                {
                    "performance": _read_json_lines(root / "performance.jsonl"),
                    "head_to_head": _read_json_lines(root / "head_to_head.jsonl"),
                }
            )
        )
        return 0
    if command == "freshness":
        supplied_database = cast(Path | None, args.database)
        database = (
            resolve_local_data_paths().database
            if supplied_database is None
            else supplied_database
        )
        draw_number = cast(str | None, args.draw_number)
        if draw_number is None:
            draw_number = _most_recent_target_draw_number(root)
        current_target = build_current_target_freshness_report(
            root, draw_number=draw_number, database=database
        )
        ledger_path = rebuild_history_freshness_ledger(root, database=database)
        print(
            _canonical_json(
                {
                    "current_target": current_target,
                    "performance_freshness": _read_json_lines(ledger_path),
                }
            )
        )
        return 0
    score_paths = rescore_draw(root, cast(str, args.draw_number))
    print(_canonical_json({"score_paths": [str(path) for path in score_paths]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
