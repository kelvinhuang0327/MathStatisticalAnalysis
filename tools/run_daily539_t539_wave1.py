"""Run the task-owned T539 DAILY_539 migration and causal replay.

The runner deliberately lives in ``tools/run_daily539_*.py`` so the Wave 1
task can be integrated later without changing the shared strategy catalog or
the production persistence layer.  Historical data is fetched from the
official Taiwan Lottery API into a task-runtime cache, then replayed from that
immutable cache.  Prediction adapters never see the network, filesystem, or
database; they receive only an immutable causal tuple.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlencode

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapterError,
    CausalDrawRow,
)
from lottolab.strategies.adapters.daily539_portfolio_f4cold import (
    Daily539F4Cold3BetAdapter,
    Daily539F4Cold5BetAdapter,
)
from lottolab.strategies.adapters.daily539_portfolio_frequency import (
    Daily539MidfreqAcb2BetAdapter,
    Daily539MidfreqFourier2BetAdapter,
)
from lottolab.strategies.adapters.daily539_portfolio_phase2 import (
    Daily539AcbMarkovMidfreq3BetAdapter,
)
from lottolab.strategies.adapters.daily539_single_legacy import (
    Daily539AcbSingleAdapter,
    Daily539Markov1BetAdapter,
)
from lottolab.strategies.adapters.daily539_wave1 import Daily539MarkovColdAdapter

RUN_ID = "T539_ALL_STRATEGIES_MIGRATION_BACKTEST_WAVE1_R1"
LOTTERY_TYPE = LotteryType.DAILY_539.value
SCHEMA_VERSION = "t539-wave1-v1"
SOURCE_CACHE_NAME = "official_daily539_source.json"
DB_NAME = "t539_wave1.sqlite3"
OFFICIAL_SOURCE_ENDPOINT = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Daily539Result"
OFFICIAL_HISTORY_PAGE = "https://www.taiwanlottery.com/lotto/history/history_result/"
OFFICIAL_DOWNLOAD_PAGE = "https://apislb.taiwanlottery.com/lotto/history/result_download/"
DONOR_ARCHIVE_SHA256 = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"
SOURCE_PAGE_SIZE = 1000
DEFAULT_AS_OF_DATE = "2026-08-03"
DEFAULT_RUNTIME_ROOT_NAME = "T539_ALL_STRATEGIES_MIGRATION_BACKTEST_WAVE1_R1"


class PortfolioAdapterProtocol(Protocol):
    def get_bets(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]: ...


class SingleAdapterProtocol(Protocol):
    def get_one_bet(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], None]: ...


AdapterFactory = Callable[[], PortfolioAdapterProtocol | SingleAdapterProtocol]


@dataclass(frozen=True, slots=True)
class StrategySpec:
    """A frozen donor identity and the adapter used for this Wave 1 run."""

    strategy_id: str
    strategy_name: str
    strategy_version: str
    lottery_type: str
    min_history: int
    native_ticket_count: int
    adapter_factory: AdapterFactory
    adapter_source_paths: tuple[str, ...]
    selection_reason: str


@dataclass(frozen=True, slots=True)
class SourceDraw:
    draw_id: str
    draw_date: str
    numbers: tuple[int, ...]


DEFAULT_STRATEGY_SPECS: tuple[StrategySpec, ...] = (
    StrategySpec(
        strategy_id="daily539_markov_cold",
        strategy_name="今彩539 Markov Cold",
        strategy_version="v0.1",
        lottery_type=LOTTERY_TYPE,
        min_history=100,
        native_ticket_count=1,
        adapter_factory=Daily539MarkovColdAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_wave1.py",
            "LotteryNewMeraged/lottery_api/models/replay_strategy_registry.py",
        ),
        selection_reason="Reuse the PR #85 main-ancestor adapter exactly as authorized.",
    ),
    StrategySpec(
        strategy_id="markov_1bet_539",
        strategy_name="今彩539 Markov 1注",
        strategy_version="v0.1-p36",
        lottery_type=LOTTERY_TYPE,
        min_history=30,
        native_ticket_count=1,
        adapter_factory=Daily539Markov1BetAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_single_legacy.py",
            "LotteryNewMeraged/lottery_api/models/p36_wave2_daily539_adapters.py",
        ),
        selection_reason="Complete deterministic P36 single-ticket source.",
    ),
    StrategySpec(
        strategy_id="acb_single_539",
        strategy_name="今彩539 ACB Single 1注",
        strategy_version="v0.1-p36",
        lottery_type=LOTTERY_TYPE,
        min_history=100,
        native_ticket_count=1,
        adapter_factory=Daily539AcbSingleAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_single_legacy.py",
            "LotteryNewMeraged/lottery_api/models/p36_wave2_daily539_adapters.py",
        ),
        selection_reason="Complete deterministic P36 single-ticket source.",
    ),
    StrategySpec(
        strategy_id="midfreq_acb_2bet",
        strategy_name="今彩539 MidFreq+ACB 2注",
        strategy_version="v0.1",
        lottery_type=LOTTERY_TYPE,
        min_history=100,
        native_ticket_count=2,
        adapter_factory=Daily539MidfreqAcb2BetAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_portfolio_frequency.py",
            "LotteryNewMeraged/lottery_api/models/p128_wave2_phase1_adapters.py",
        ),
        selection_reason="Complete P128 native two-ticket output.",
    ),
    StrategySpec(
        strategy_id="midfreq_fourier_2bet",
        strategy_name="今彩539 MidFreq+Fourier 2注",
        strategy_version="v0.1",
        lottery_type=LOTTERY_TYPE,
        min_history=100,
        native_ticket_count=2,
        adapter_factory=Daily539MidfreqFourier2BetAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_portfolio_frequency.py",
            "LotteryNewMeraged/lottery_api/models/p128_wave2_phase1_adapters.py",
        ),
        selection_reason="Complete P128 native two-ticket output.",
    ),
    StrategySpec(
        strategy_id="acb_markov_midfreq_3bet",
        strategy_name="今彩539 ACB+Markov+MidFreq 3注",
        strategy_version="v0.1",
        lottery_type=LOTTERY_TYPE,
        min_history=100,
        native_ticket_count=3,
        adapter_factory=Daily539AcbMarkovMidfreq3BetAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_portfolio_phase2.py",
            "LotteryNewMeraged/lottery_api/models/p128_wave2_phase2_adapters.py",
        ),
        selection_reason="Complete P128 Phase 2 native three-ticket output.",
    ),
    StrategySpec(
        strategy_id="daily539_f4cold_3bet",
        strategy_name="今彩539 F4Cold 3注",
        strategy_version="v0.1",
        lottery_type=LOTTERY_TYPE,
        min_history=100,
        native_ticket_count=3,
        adapter_factory=Daily539F4Cold3BetAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_portfolio_f4cold.py",
            "LotteryNewMeraged/tools/predict_539_5bet_f4cold.py",
            "LotteryNewMeraged/lottery_api/models/p93_tierb_replay_adapters.py",
        ),
        selection_reason="Complete native first-three tickets from the P93 F4Cold source.",
    ),
    StrategySpec(
        strategy_id="daily539_f4cold_5bet",
        strategy_name="今彩539 F4Cold 5注",
        strategy_version="v0.1",
        lottery_type=LOTTERY_TYPE,
        min_history=100,
        native_ticket_count=5,
        adapter_factory=Daily539F4Cold5BetAdapter,
        adapter_source_paths=(
            "src/lottolab/strategies/adapters/daily539_portfolio_f4cold.py",
            "LotteryNewMeraged/tools/predict_539_5bet_f4cold.py",
            "LotteryNewMeraged/lottery_api/models/p93_tierb_replay_adapters.py",
        ),
        selection_reason="Complete native five-ticket output from the P93 F4Cold source.",
    ),
)


BLOCKED_DAILY539_STRATEGIES: tuple[dict[str, str], ...] = (
    {
        "strategy_id": "daily539_f4cold",
        "reason_code": "WAVE1_SELECTION_CAP_DERIVED_DUPLICATE",
        "reason": (
            "Deferred at the eight-strategy Wave 1 cap; its single ticket is the first "
            "ticket of the selected native F4Cold portfolio."
        ),
    },
    {
        "strategy_id": "acb_1bet",
        "reason_code": "SOURCE_PROVENANCE_INCOMPLETE",
        "reason": (
            "Catalog row exists, but the authorized primary donor set does not contain "
            "a complete no-DB producer identity for this alias."
        ),
    },
    {
        "strategy_id": "acb_markov_midfreq",
        "reason_code": "SOURCE_PROVENANCE_INCOMPLETE",
        "reason": (
            "Catalog row exists, but the authorized primary donor set does not contain "
            "a complete no-DB producer identity for this alias."
        ),
    },
    {
        "strategy_id": "zone_gap_3bet_539",
        "reason_code": "INCOMPLETE_NATIVE_TICKET_SOURCE",
        "reason": (
            "P36 source exposes only bet 1 while the task requires the complete native "
            "three-ticket set."
        ),
    },
    {
        "strategy_id": "539_3bet_orthogonal",
        "reason_code": "INCOMPLETE_NATIVE_TICKET_SOURCE",
        "reason": (
            "P36 source exposes only bet 1 while the task requires the complete native "
            "three-ticket set."
        ),
    },
    {
        "strategy_id": "p0b_539_3bet_f_cold_fmid",
        "reason_code": "INCOMPLETE_NATIVE_TICKET_SOURCE",
        "reason": (
            "P36 source exposes only bet 1 and does not provide the complete native "
            "three-ticket variant."
        ),
    },
    {
        "strategy_id": "p0c_539_3bet_f_cold_x2",
        "reason_code": "INCOMPLETE_NATIVE_TICKET_SOURCE",
        "reason": (
            "P36 source exposes only bet 1 and does not provide the complete native "
            "three-ticket variant."
        ),
    },
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_draw_payload(draws: Sequence[SourceDraw]) -> list[dict[str, object]]:
    return [
        {
            "draw_id": draw.draw_id,
            "draw_date": draw.draw_date,
            "main_numbers": list(draw.numbers),
        }
        for draw in draws
    ]


def source_payload_sha256(draws: Sequence[SourceDraw]) -> str:
    """Hash only canonical draw identity, not retrieval time or API metadata."""

    return _sha256_text(_canonical_json(_source_draw_payload(draws)))


def _validate_numbers(numbers: object, context: str) -> tuple[int, ...]:
    if type(numbers) not in (tuple, list):
        raise ValueError(f"{context}: expected a tuple/list of five numbers")
    values = tuple(cast(Sequence[object], numbers))
    if len(values) != 5 or not all(type(value) is int for value in values):
        raise ValueError(f"{context}: expected exactly five built-in integers")
    typed = cast(tuple[int, ...], values)
    if len(set(typed)) != 5 or not all(1 <= value <= 39 for value in typed):
        raise ValueError(f"{context}: numbers must be unique and within 1..39")
    if typed != tuple(sorted(typed)):
        raise ValueError(f"{context}: numbers must be ascending")
    return typed


def _normalise_source_records(
    records: Iterable[dict[str, Any]], as_of_date: str
) -> tuple[SourceDraw, ...]:
    by_draw_id: dict[str, SourceDraw] = {}
    for index, record in enumerate(records):
        raw_period = record.get("period")
        raw_date = record.get("lotteryDate")
        raw_numbers = record.get("drawNumberSize")
        if raw_period is None or not isinstance(raw_date, str):
            raise ValueError(f"official source record {index}: missing period/date")
        draw_date = raw_date[:10]
        if draw_date > as_of_date:
            continue
        draw_id = str(raw_period)
        numbers = _validate_numbers(raw_numbers, f"official source {draw_id}")
        candidate = SourceDraw(draw_id=draw_id, draw_date=draw_date, numbers=numbers)
        prior = by_draw_id.get(draw_id)
        if prior is not None and prior != candidate:
            raise ValueError(f"official source has conflicting duplicate period {draw_id}")
        by_draw_id[draw_id] = candidate
    ordered = sorted(by_draw_id.values(), key=lambda draw: (draw.draw_date, int(draw.draw_id)))
    if not ordered:
        raise ValueError("official source returned no DAILY_539 draws")
    if len({draw.draw_date for draw in ordered}) != len(ordered):
        raise ValueError("official source contains multiple DAILY_539 draws on one date")
    return tuple(ordered)


def _official_page_url(as_of_date: str, page_number: int) -> str:
    query = urlencode(
        {
            "period": "",
            "month": "2000-01",
            "endMonth": as_of_date[:7],
            "pageNum": str(page_number),
            "pageSize": str(SOURCE_PAGE_SIZE),
        }
    )
    return f"{OFFICIAL_SOURCE_ENDPOINT}?{query}"


def _fetch_official_page(url: str) -> dict[str, Any]:
    """Fetch with curl's verified platform TLS stack; never disable verification."""

    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--max-time",
            "60",
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload_value: object = json.loads(result.stdout)
    if not isinstance(payload_value, dict):
        raise ValueError("official source response must be a JSON object")
    return cast(dict[str, Any], payload_value)


def fetch_official_daily539(as_of_date: str) -> tuple[SourceDraw, ...]:
    """Fetch all pages of the official public source and pin causal history."""

    raw_records: list[dict[str, Any]] = []
    page_number = 1
    total_size: int | None = None
    while total_size is None or len(raw_records) < total_size:
        payload = _fetch_official_page(_official_page_url(as_of_date, page_number))
        if payload.get("rtCode") != 0:
            raise ValueError(f"official source returned rtCode={payload.get('rtCode')!r}")
        content_value: object = payload.get("content")
        if not isinstance(content_value, dict):
            raise ValueError("official source response has no content object")
        content = cast(dict[str, object], content_value)
        raw_total: object = content.get("totalSize")
        raw_page: object = content.get("daily539Res")
        if not isinstance(raw_total, int) or not isinstance(raw_page, list):
            raise ValueError("official source response has invalid pagination fields")
        total_size = raw_total
        page_records = cast(list[dict[str, Any]], raw_page)
        raw_records.extend(page_records)
        if not page_records or len(page_records) >= total_size:
            break
        page_number += 1
        if page_number > 100:
            raise ValueError("official source pagination exceeded safe page bound")
    return _normalise_source_records(raw_records, as_of_date)


def default_runtime_root() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root.parents[2] / ".runs" / "MathStatisticalAnalysis" / DEFAULT_RUNTIME_ROOT_NAME


def load_or_fetch_source(runtime_root: Path, as_of_date: str) -> tuple[SourceDraw, ...]:
    runtime_root.mkdir(parents=True, exist_ok=True)
    cache_path = runtime_root / SOURCE_CACHE_NAME
    if cache_path.exists():
        payload_value: object = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload_value, dict):
            raise ValueError("source cache must be a JSON object")
        payload = cast(dict[str, object], payload_value)
        if payload.get("source_endpoint") != OFFICIAL_SOURCE_ENDPOINT:
            raise ValueError("source cache endpoint mismatch")
        if payload.get("as_of_date") != as_of_date:
            raise ValueError("source cache as_of_date mismatch; use a new runtime root")
        raw_draws: object = payload.get("draws")
        if not isinstance(raw_draws, list):
            raise ValueError("source cache has no draws list")
        cached_draws = cast(list[dict[str, Any]], raw_draws)
        records = [
            {
                "period": item.get("draw_id"),
                "lotteryDate": item.get("draw_date"),
                "drawNumberSize": item.get("main_numbers"),
            }
            for item in cached_draws
        ]
        draws = _normalise_source_records(records, as_of_date)
        if payload.get("source_sha256") != source_payload_sha256(draws):
            raise ValueError("source cache digest mismatch")
        return draws

    draws = fetch_official_daily539(as_of_date)
    cache_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_endpoint": OFFICIAL_SOURCE_ENDPOINT,
        "official_history_page": OFFICIAL_HISTORY_PAGE,
        "official_download_page": OFFICIAL_DOWNLOAD_PAGE,
        "query": {"month": "2000-01", "endMonth": as_of_date[:7], "page_size": SOURCE_PAGE_SIZE},
        "as_of_date": as_of_date,
        "lottery_type": LOTTERY_TYPE,
        "source_sha256": source_payload_sha256(draws),
        "draws": _source_draw_payload(draws),
    }
    cache_path.write_text(_canonical_json(cache_payload) + "\n", encoding="utf-8")
    return draws


def _adapter_tickets(
    adapter: object, history: tuple[CausalDrawRow, ...]
) -> tuple[tuple[int, ...], ...]:
    if hasattr(adapter, "get_bets"):
        portfolio = cast(PortfolioAdapterProtocol, adapter)
        raw_tickets = portfolio.get_bets(history, LotteryType.DAILY_539)
    elif hasattr(adapter, "get_one_bet"):
        single = cast(SingleAdapterProtocol, adapter)
        one_bet, special = single.get_one_bet(history, LotteryType.DAILY_539)
        if special is not None:
            raise ValueError("DAILY_539 adapter emitted a special number")
        raw_tickets = (one_bet,)
    else:
        raise ValueError("adapter exposes neither get_bets nor get_one_bet")
    if type(raw_tickets) is not tuple:
        raise ValueError("adapter must return an ordered tuple of tickets")
    return tuple(
        _validate_numbers(ticket, f"adapter ticket {position}")
        for position, ticket in enumerate(cast(tuple[object, ...], raw_tickets), start=1)
    )


def _failure_code(error: Exception) -> str:
    if isinstance(error, BetAdapterError):
        return type(error).__name__.upper()
    if isinstance(error, ValueError):
        return "INVALID_OUTPUT"
    return "UNEXPECTED_EXCEPTION"


def _git_source_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _connect(db_path: Path, runtime_root: Path) -> sqlite3.Connection:
    if db_path != runtime_root / DB_NAME:
        raise ValueError(f"task DB must be exactly {runtime_root / DB_NAME}")
    runtime_root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = DELETE")
    connection.execute("PRAGMA synchronous = FULL")
    return connection


def _init_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS run_metadata (
            run_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
            source_endpoint TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            adapter_source_commit TEXT NOT NULL,
            strategy_set_json TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_draws (
            draw_id TEXT PRIMARY KEY,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
            draw_date TEXT NOT NULL UNIQUE,
            main_numbers_json TEXT NOT NULL,
            draw_order INTEGER NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS strategy_coverage (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
            native_ticket_count INTEGER NOT NULL,
            min_history INTEGER NOT NULL,
            first_eligible_target_draw_id TEXT,
            expected_target_draw_count INTEGER NOT NULL,
            processed_target_draw_count INTEGER NOT NULL DEFAULT 0,
            successful_target_draw_count INTEGER NOT NULL DEFAULT 0,
            failed_target_draw_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            PRIMARY KEY (run_id, strategy_id, strategy_version)
        );
        CREATE TABLE IF NOT EXISTS prediction_tickets (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
            target_draw_id TEXT NOT NULL,
            target_draw_date TEXT NOT NULL,
            cutoff_draw_id TEXT NOT NULL,
            cutoff_draw_date TEXT NOT NULL,
            native_ticket_count INTEGER NOT NULL,
            ticket_position INTEGER NOT NULL,
            main_numbers_json TEXT,
            special_number INTEGER,
            hits INTEGER,
            execution_status TEXT NOT NULL,
            failure_reason TEXT,
            provenance_json TEXT NOT NULL,
            adapter_source_commit TEXT NOT NULL,
            PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id, ticket_position)
        );
        CREATE TABLE IF NOT EXISTS prediction_scores (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            target_draw_id TEXT NOT NULL,
            ticket_position INTEGER NOT NULL,
            actual_main_numbers_json TEXT NOT NULL,
            hit_numbers_json TEXT NOT NULL,
            hits INTEGER NOT NULL,
            score_version TEXT NOT NULL,
            PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id, ticket_position)
        );
        CREATE TABLE IF NOT EXISTS failure_ledger (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            target_draw_id TEXT NOT NULL,
            target_draw_date TEXT NOT NULL,
            cutoff_draw_id TEXT NOT NULL,
            failure_code TEXT NOT NULL,
            failure_message TEXT NOT NULL,
            expected_ticket_count INTEGER NOT NULL,
            provenance_json TEXT NOT NULL,
            adapter_source_commit TEXT NOT NULL,
            PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id)
        );
        CREATE TABLE IF NOT EXISTS target_completion (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            target_draw_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED')),
            native_ticket_count INTEGER NOT NULL,
            PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id)
        );
        """
    )


def _strategy_set_payload(specs: Sequence[StrategySpec]) -> list[dict[str, object]]:
    return [
        {
            "strategy_id": spec.strategy_id,
            "strategy_version": spec.strategy_version,
            "lottery_type": spec.lottery_type,
            "native_ticket_count": spec.native_ticket_count,
            "min_history": spec.min_history,
        }
        for spec in specs
    ]


def _ensure_run_metadata(
    connection: sqlite3.Connection,
    source_sha256: str,
    as_of_date: str,
    adapter_source_commit: str,
    specs: Sequence[StrategySpec],
) -> None:
    strategy_set_json = _canonical_json(_strategy_set_payload(specs))
    existing = connection.execute(
        "SELECT schema_version, lottery_type, source_endpoint, source_sha256, as_of_date, "
        "adapter_source_commit, strategy_set_json FROM run_metadata WHERE run_id = ?",
        (RUN_ID,),
    ).fetchone()
    if existing is not None:
        expected = (
            SCHEMA_VERSION,
            LOTTERY_TYPE,
            OFFICIAL_SOURCE_ENDPOINT,
            source_sha256,
            as_of_date,
            adapter_source_commit,
            strategy_set_json,
        )
        if tuple(existing) != expected:
            raise ValueError("existing task DB metadata does not match this deterministic run")
        return
    connection.execute(
        "INSERT INTO run_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            RUN_ID,
            SCHEMA_VERSION,
            LOTTERY_TYPE,
            OFFICIAL_SOURCE_ENDPOINT,
            source_sha256,
            as_of_date,
            adapter_source_commit,
            strategy_set_json,
            "RUNNING",
        ),
    )
    connection.commit()


def _insert_source_draws(connection: sqlite3.Connection, draws: Sequence[SourceDraw]) -> None:
    connection.executemany(
        "INSERT OR IGNORE INTO source_draws VALUES (?, ?, ?, ?, ?)",
        [
            (
                draw.draw_id,
                LOTTERY_TYPE,
                draw.draw_date,
                _canonical_json(list(draw.numbers)),
                index,
            )
            for index, draw in enumerate(draws)
        ],
    )
    connection.commit()


def _ensure_coverage_rows(
    connection: sqlite3.Connection,
    draws: Sequence[SourceDraw],
    specs: Sequence[StrategySpec],
) -> None:
    for spec in specs:
        expected_count = max(0, len(draws) - spec.min_history)
        first_target = draws[spec.min_history].draw_id if expected_count else None
        connection.execute(
            "INSERT OR IGNORE INTO strategy_coverage VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)",
            (
                RUN_ID,
                spec.strategy_id,
                spec.strategy_version,
                spec.lottery_type,
                spec.native_ticket_count,
                spec.min_history,
                first_target,
                expected_count,
                "PENDING",
            ),
        )
    connection.commit()


def _provenance(
    spec: StrategySpec,
    source_sha256: str,
    adapter_source_commit: str,
    target: SourceDraw,
    cutoff: SourceDraw,
    history_count: int,
) -> str:
    return _canonical_json(
        {
            "run_id": RUN_ID,
            "lottery_type": LOTTERY_TYPE,
            "strategy_id": spec.strategy_id,
            "strategy_version": spec.strategy_version,
            "adapter_source_commit": adapter_source_commit,
            "adapter_source_paths": list(spec.adapter_source_paths),
            "donor_archive_sha256": DONOR_ARCHIVE_SHA256,
            "official_source_endpoint": OFFICIAL_SOURCE_ENDPOINT,
            "official_history_page": OFFICIAL_HISTORY_PAGE,
            "official_download_page": OFFICIAL_DOWNLOAD_PAGE,
            "source_sha256": source_sha256,
            "target_draw_id": target.draw_id,
            "target_draw_date": target.draw_date,
            "cutoff_draw_id": cutoff.draw_id,
            "cutoff_draw_date": cutoff.draw_date,
            "causal_history_count": history_count,
            "future_draws_visible": False,
        }
    )


def _target_rows(
    connection: sqlite3.Connection,
    draws: Sequence[SourceDraw],
    spec: StrategySpec,
    adapter_source_commit: str,
    source_sha256: str,
    target_index: int,
) -> None:
    target = draws[target_index]
    cutoff = draws[target_index - 1]
    history = tuple(
        CausalDrawRow(draw=draw.draw_id, date=draw.draw_date, numbers=draw.numbers)
        for draw in draws[:target_index]
    )
    provenance = _provenance(
        spec, source_sha256, adapter_source_commit, target, cutoff, len(history)
    )
    status = "SUCCESS"
    failure: Exception | None = None
    tickets: tuple[tuple[int, ...], ...] = ()
    try:
        tickets = _adapter_tickets(spec.adapter_factory(), history)
        if len(tickets) != spec.native_ticket_count:
            raise ValueError(
                f"{spec.strategy_id}: expected {spec.native_ticket_count} tickets, "
                f"got {len(tickets)}"
            )
    except Exception as error:
        status = "FAILED"
        failure = error

    actual = set(target.numbers)
    for position in range(1, spec.native_ticket_count + 1):
        ticket = tickets[position - 1] if failure is None else None
        hit_numbers = sorted(set(ticket) & actual) if ticket is not None else []
        connection.execute(
            "INSERT INTO prediction_tickets VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                RUN_ID,
                spec.strategy_id,
                spec.strategy_version,
                LOTTERY_TYPE,
                target.draw_id,
                target.draw_date,
                cutoff.draw_id,
                cutoff.draw_date,
                spec.native_ticket_count,
                position,
                _canonical_json(list(ticket)) if ticket is not None else None,
                None,
                len(hit_numbers) if ticket is not None else None,
                status,
                str(failure) if failure is not None else None,
                provenance,
                adapter_source_commit,
            ),
        )
        if ticket is not None:
            connection.execute(
                "INSERT INTO prediction_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    RUN_ID,
                    spec.strategy_id,
                    spec.strategy_version,
                    target.draw_id,
                    position,
                    _canonical_json(list(target.numbers)),
                    _canonical_json(hit_numbers),
                    len(hit_numbers),
                    "main-hit-count-v1",
                ),
            )
    if failure is not None:
        connection.execute(
            "INSERT INTO failure_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                RUN_ID,
                spec.strategy_id,
                spec.strategy_version,
                target.draw_id,
                target.draw_date,
                cutoff.draw_id,
                _failure_code(failure),
                str(failure),
                spec.native_ticket_count,
                provenance,
                adapter_source_commit,
            ),
        )
    connection.execute(
        "INSERT INTO target_completion VALUES (?, ?, ?, ?, ?, ?)",
        (
            RUN_ID,
            spec.strategy_id,
            spec.strategy_version,
            target.draw_id,
            status,
            spec.native_ticket_count,
        ),
    )


def _refresh_coverage(connection: sqlite3.Connection, specs: Sequence[StrategySpec]) -> None:
    for spec in specs:
        row = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(status = 'SUCCESS'), 0), "
            "COALESCE(SUM(status = 'FAILED'), 0) FROM target_completion "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
            (RUN_ID, spec.strategy_id, spec.strategy_version),
        ).fetchone()
        processed, successful, failed = cast(tuple[int, int, int], row)
        expected = connection.execute(
            "SELECT expected_target_draw_count FROM strategy_coverage "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
            (RUN_ID, spec.strategy_id, spec.strategy_version),
        ).fetchone()[0]
        status = "COMPLETE" if processed == expected else "PARTIAL"
        connection.execute(
            "UPDATE strategy_coverage SET processed_target_draw_count = ?, "
            "successful_target_draw_count = ?, failed_target_draw_count = ?, status = ? "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
            (
                processed,
                successful,
                failed,
                status,
                RUN_ID,
                spec.strategy_id,
                spec.strategy_version,
            ),
        )
    connection.commit()


def _write_reports(
    runtime_root: Path,
    connection: sqlite3.Connection,
    draws: Sequence[SourceDraw],
    specs: Sequence[StrategySpec],
    source_sha256: str,
    adapter_source_commit: str,
    as_of_date: str,
) -> dict[str, object]:
    coverage_rows = connection.execute(
        "SELECT strategy_id, strategy_version, lottery_type, native_ticket_count, min_history, "
        "first_eligible_target_draw_id, expected_target_draw_count, processed_target_draw_count, "
        "successful_target_draw_count, failed_target_draw_count, status "
        "FROM strategy_coverage ORDER BY strategy_id, strategy_version"
    ).fetchall()
    coverage = [
        {
            "strategy_id": row[0],
            "strategy_version": row[1],
            "lottery_type": row[2],
            "native_ticket_count": row[3],
            "min_history": row[4],
            "first_eligible_target_draw_id": row[5],
            "expected_target_draw_count": row[6],
            "processed_target_draw_count": row[7],
            "successful_target_draw_count": row[8],
            "failed_target_draw_count": row[9],
            "status": row[10],
        }
        for row in coverage_rows
    ]
    failures = [
        dict(row)
        for row in connection.execute(
            "SELECT run_id, strategy_id, strategy_version, target_draw_id, target_draw_date, "
            "cutoff_draw_id, failure_code, failure_message, expected_ticket_count, "
            "provenance_json, adapter_source_commit FROM failure_ledger "
            "ORDER BY strategy_id, target_draw_id"
        ).fetchall()
    ]
    for item in failures:
        item["provenance"] = json.loads(cast(str, item.pop("provenance_json")))
    selected = _strategy_set_payload(specs)
    all_complete = all(item["status"] == "COMPLETE" for item in coverage)
    run_summary: dict[str, object] = {
        "run_id": RUN_ID,
        "schema_version": SCHEMA_VERSION,
        "lottery_type": LOTTERY_TYPE,
        "as_of_date": as_of_date,
        "source_endpoint": OFFICIAL_SOURCE_ENDPOINT,
        "source_sha256": source_sha256,
        "adapter_source_commit": adapter_source_commit,
        "draw_count": len(draws),
        "selected_strategy_count": len(specs),
        "selected_strategies": selected,
        "blocked_strategies": list(BLOCKED_DAILY539_STRATEGIES),
        "failure_count": len(failures),
        "status": "COMPLETE" if all_complete else "PARTIAL",
    }
    source_ledger = {
        "run_id": RUN_ID,
        "lottery_type": LOTTERY_TYPE,
        "source_kind": "OFFICIAL_PUBLIC_TAIWAN_LOTTERY_API",
        "source_endpoint": OFFICIAL_SOURCE_ENDPOINT,
        "official_history_page": OFFICIAL_HISTORY_PAGE,
        "official_download_page": OFFICIAL_DOWNLOAD_PAGE,
        "query": {"month": "2000-01", "endMonth": as_of_date[:7], "page_size": SOURCE_PAGE_SIZE},
        "as_of_date": as_of_date,
        "draw_count": len(draws),
        "first_draw": draws[0].draw_id,
        "first_draw_date": draws[0].draw_date,
        "last_draw": draws[-1].draw_id,
        "last_draw_date": draws[-1].draw_date,
        "source_sha256": source_sha256,
        "donor_archive_sha256": DONOR_ARCHIVE_SHA256,
        "adapter_source_commit": adapter_source_commit,
        "future_draws_included": False,
    }
    reports = {
        "strategy_coverage.json": coverage,
        "run_summary.json": run_summary,
        "failure_ledger.json": failures,
        "source_ledger.json": source_ledger,
    }
    for name, payload in reports.items():
        (runtime_root / name).write_text(_canonical_json(payload) + "\n", encoding="utf-8")
    return run_summary


def run_batch(
    runtime_root: Path,
    draws: Sequence[SourceDraw],
    *,
    adapter_source_commit: str,
    as_of_date: str,
    specs: Sequence[StrategySpec] = DEFAULT_STRATEGY_SPECS,
    max_targets_per_strategy: int | None = None,
) -> dict[str, object]:
    """Run or resume a deterministic batch against a task-owned SQLite file."""

    if not draws:
        raise ValueError("DAILY_539 source history cannot be empty")
    if any(draw.draw_date > as_of_date for draw in draws):
        raise ValueError("source contains a draw after the authorized as-of date")
    if any(spec.lottery_type != LOTTERY_TYPE for spec in specs):
        raise ValueError("T539 runner accepts DAILY_539 strategies only")
    db_path = runtime_root / DB_NAME
    source_sha256 = source_payload_sha256(draws)
    connection = _connect(db_path, runtime_root)
    try:
        _init_schema(connection)
        _ensure_run_metadata(connection, source_sha256, as_of_date, adapter_source_commit, specs)
        _insert_source_draws(connection, draws)
        _ensure_coverage_rows(connection, draws, specs)
        for spec in specs:
            processed_this_invocation = 0
            for target_index in range(spec.min_history, len(draws)):
                target_id = draws[target_index].draw_id
                already_done = connection.execute(
                    "SELECT 1 FROM target_completion WHERE run_id = ? AND strategy_id = ? "
                    "AND strategy_version = ? AND target_draw_id = ?",
                    (RUN_ID, spec.strategy_id, spec.strategy_version, target_id),
                ).fetchone()
                if already_done is not None:
                    continue
                with connection:
                    _target_rows(
                        connection,
                        draws,
                        spec,
                        adapter_source_commit,
                        source_sha256,
                        target_index,
                    )
                processed_this_invocation += 1
                if (
                    max_targets_per_strategy is not None
                    and processed_this_invocation >= max_targets_per_strategy
                ):
                    break
        _refresh_coverage(connection, specs)
        summary = _write_reports(
            runtime_root,
            connection,
            draws,
            specs,
            source_sha256,
            adapter_source_commit,
            as_of_date,
        )
        connection.execute(
            "UPDATE run_metadata SET status = ? WHERE run_id = ?",
            (summary["status"], RUN_ID),
        )
        connection.commit()
        return summary
    finally:
        connection.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=default_runtime_root())
    parser.add_argument("--as-of-date", default=DEFAULT_AS_OF_DATE)
    parser.add_argument("--adapter-source-commit")
    parser.add_argument("--max-targets-per-strategy", type=int)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.max_targets_per_strategy is not None and args.max_targets_per_strategy < 1:
        raise SystemExit("--max-targets-per-strategy must be positive")
    runtime_root = cast(Path, args.runtime_root)
    draws = load_or_fetch_source(runtime_root, cast(str, args.as_of_date))
    source_commit = args.adapter_source_commit
    if source_commit is None:
        source_commit = _git_source_commit(Path(__file__).resolve().parents[1])
    summary = run_batch(
        runtime_root,
        draws,
        adapter_source_commit=source_commit,
        as_of_date=cast(str, args.as_of_date),
        max_targets_per_strategy=args.max_targets_per_strategy,
    )
    print(_canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
