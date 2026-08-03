"""Task-owned POWER_LOTTO Wave 1 source, replay, and evidence pipeline.

This module deliberately does not use the production draw database or the
shared strategy catalog.  It normalizes the official public POWER_LOTTO API
into an immutable, task-owned source sequence and writes a resumable SQLite
replay store under the caller-provided task runtime root.

Strategy code is injected by the task-local adapter module.  The runner owns
the second-zone composition, scoring, persistence, and evidence artifacts so
every attempted strategy/target remains auditable even when one strategy is
blocked or fails.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from lottolab.domain.draws import LotteryType

LOTTERY_TYPE = LotteryType.POWER_LOTTO.value
RUNNER_VERSION = "p638-wave1-runner-v1"
SOURCE_API_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/SuperLotto638Result"
SOURCE_START_MONTH = "2008-01"
SOURCE_END_MONTH = "2026-07"
BASE_SOURCE_COMMIT = "2573900481c376e3229b4d413f60c91cc54a1295"

# The two RSR-6 identities are retained in the research ledger as explicit
# blocked alternatives.  Wave 1 selects the eight reconstructable identities
# with complete first-zone sources after that exclusion.
WAVE1_SELECTED_STRATEGY_IDS = (
    "zonal_entropy_2bet",
    "cold_complement_2bet",
    "midfreq_fourier_2bet",
    "fourier30_markov30_2bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "power_precision_3bet",
    "pp3_freqort_4bet",
)

WAVE1_DONOR_BLOCKED_STRATEGIES = (
    {
        "strategy_id": "power_orthogonal_5bet",
        "source_paths": ["lottery_api/models/p128_wave2_phase2_adapters.py"],
        "reason": (
            "RSR-6 donor ledger retains 20 orphan bet-index=2 rows; deferred until reconciliation"
        ),
        "disposition": "BLOCKED_DEFERRED_WAVE",
    },
    {
        "strategy_id": "power_fourier_rhythm_2bet",
        "source_paths": ["lottery_api/models/p93_tierb_replay_adapters.py"],
        "reason": "reconstructable donor is outside the bounded P47/P56/P128 adapter wave",
        "disposition": "DEFERRED_WAVE_2",
    },
)


class StrategyCallable(Protocol):
    def __call__(self, history: Sequence[Mapping[str, object]], lottery_type: object) -> object:
        """Return the native ordered ticket portfolio."""


@dataclass(frozen=True, slots=True)
class PowerLottoDrawRecord:
    """One normalized official draw in chronological order."""

    draw_number: str
    draw_date: str
    main_numbers: tuple[int, ...]
    second_number: int
    source_reference: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_date": self.draw_date,
            "draw_number": self.draw_number,
            "main_numbers": list(self.main_numbers),
            "second_number": self.second_number,
            "source_reference": self.source_reference,
        }


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    """Stable strategy identity used by the task-owned replay store."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    source_paths: tuple[str, ...]
    algorithm_family: str
    provenance: str
    callable_object: object | None = None
    blocked_reason: str | None = None

    @property
    def selected(self) -> bool:
        return self.blocked_reason is None


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Closed run counters and artifact locations."""

    run_id: str
    source_sha256: str
    source_count: int
    selected_count: int
    eligible_attempt_count: int
    complete_target_count: int
    excluded_target_count: int
    failed_target_count: int
    ticket_count: int
    db_path: Path
    artifact_paths: tuple[Path, ...]


def _exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact built-in integer")
    return value


def _validate_draw(draw: PowerLottoDrawRecord) -> PowerLottoDrawRecord:
    if type(draw.draw_number) is not str or not draw.draw_number:
        raise ValueError("draw_number must be a non-empty string")
    try:
        int(draw.draw_number)
        date.fromisoformat(draw.draw_date)
    except ValueError as exc:
        raise ValueError("draw_number/draw_date are not canonical") from exc
    if len(draw.main_numbers) != 6:
        raise ValueError("POWER_LOTTO needs exactly six first-zone numbers")
    if any(type(number) is not int for number in draw.main_numbers):
        raise ValueError("POWER_LOTTO main numbers must be exact built-in integers")
    if len(set(draw.main_numbers)) != 6:
        raise ValueError("POWER_LOTTO main numbers must be unique")
    if tuple(sorted(draw.main_numbers)) != draw.main_numbers:
        raise ValueError("POWER_LOTTO main numbers must be ascending")
    if any(number < 1 or number > 38 for number in draw.main_numbers):
        raise ValueError("POWER_LOTTO main numbers must be in [1, 38]")
    if type(draw.second_number) is not int or not 1 <= draw.second_number <= 8:
        raise ValueError("POWER_LOTTO second number must be an exact integer in [1, 8]")
    if type(draw.source_reference) is not str or not draw.source_reference:
        raise ValueError("source_reference must be a non-empty string")
    return draw


def normalize_draws(draws: Iterable[PowerLottoDrawRecord]) -> tuple[PowerLottoDrawRecord, ...]:
    """Validate, sort, and reject duplicate official draw identities."""

    values = tuple(_validate_draw(draw) for draw in draws)
    ordered = tuple(sorted(values, key=lambda item: (item.draw_date, int(item.draw_number))))
    if not ordered:
        raise ValueError("POWER_LOTTO source is empty")
    if len({draw.draw_number for draw in ordered}) != len(ordered):
        raise ValueError("POWER_LOTTO source contains duplicate draw numbers")
    return ordered


def canonical_source_bytes(draws: Sequence[PowerLottoDrawRecord]) -> bytes:
    payload = [draw.canonical_dict() for draw in normalize_draws(draws)]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def source_sha256(draws: Sequence[PowerLottoDrawRecord]) -> str:
    return hashlib.sha256(canonical_source_bytes(draws)).hexdigest()


def _api_payload_rows(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("official POWER_LOTTO API payload must be an object")
    raw_payload = cast(dict[str, Any], payload)
    if raw_payload.get("rtCode") != 0:
        raise ValueError(f"official POWER_LOTTO API rejected request: {raw_payload.get('rtMsg')!r}")
    content = raw_payload.get("content")
    if not isinstance(content, dict):
        raise ValueError("official POWER_LOTTO API payload has no content object")
    raw_content = cast(dict[str, Any], content)
    rows = raw_content.get("superLotto638Res")
    if not isinstance(rows, list):
        raise ValueError("official POWER_LOTTO API payload has no result rows")
    raw_rows = cast(list[object], rows)
    if not all(isinstance(row, dict) for row in raw_rows):
        raise ValueError("official POWER_LOTTO API payload has malformed result rows")
    return [cast(dict[str, Any], row) for row in raw_rows]


def _normalize_api_row(row: Mapping[str, Any], source_reference: str) -> PowerLottoDrawRecord:
    period = _exact_int(row.get("period"), "period")
    lottery_date = row.get("lotteryDate")
    if not isinstance(lottery_date, str) or len(lottery_date) < 10:
        raise ValueError("official POWER_LOTTO row has no lotteryDate")
    sized = row.get("drawNumberSize")
    if not isinstance(sized, list):
        raise ValueError("official POWER_LOTTO row must have seven drawNumberSize values")
    raw_sized = cast(list[object], sized)
    if len(raw_sized) != 7:
        raise ValueError("official POWER_LOTTO row must have seven drawNumberSize values")
    main_numbers = tuple(sorted(_exact_int(value, "drawNumberSize") for value in raw_sized[:6]))
    second_number = _exact_int(raw_sized[6], "drawNumberSize second number")
    return _validate_draw(
        PowerLottoDrawRecord(
            draw_number=str(period),
            draw_date=lottery_date[:10],
            main_numbers=main_numbers,
            second_number=second_number,
            source_reference=source_reference,
        )
    )


def fetch_official_powerlotto_draws(
    *,
    start_month: str = SOURCE_START_MONTH,
    end_month: str = SOURCE_END_MONTH,
    page_size: int = 1000,
) -> tuple[tuple[PowerLottoDrawRecord, ...], dict[str, object]]:
    """Fetch a bounded, paginated official source without touching a database."""

    if not (1 <= page_size <= 1000):
        raise ValueError("page_size must be between 1 and 1000")
    pages: list[dict[str, object]] = []
    all_draws: list[PowerLottoDrawRecord] = []
    total_size: int | None = None
    page_number = 1
    while total_size is None or len(all_draws) < total_size:
        query = urlencode(
            {
                "period": "",
                "month": start_month,
                "endMonth": end_month,
                "pageNum": page_number,
                "pageSize": page_size,
            }
        )
        url = f"{SOURCE_API_URL}?{query}"
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "LottoLab-P638/1.0"},
        )
        try:
            with urlopen(request, timeout=45) as response:
                raw = response.read()
            transport = "python-urllib"
        except URLError as urllib_error:
            # The macOS Python runtime in this workspace rejects the public
            # proxy's otherwise reachable certificate because of its missing
            # Subject Key Identifier.  curl uses the system trust path and
            # succeeds without disabling certificate verification.  This
            # fallback remains HTTPS-only and does not use a shell.
            completed = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    "45",
                    "--proto",
                    "=https",
                    "--tlsv1.2",
                    "-H",
                    "Accept: application/json",
                    "-A",
                    "LottoLab-P638/1.0",
                    url,
                ],
                check=False,
                capture_output=True,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(
                    f"official POWER_LOTTO source transport failed after urllib error "
                    f"{urllib_error}: {stderr}"
                ) from urllib_error
            raw = completed.stdout
            transport = "system-curl-after-urllib-tls-failure"
        payload = json.loads(raw.decode("utf-8"))
        rows = _api_payload_rows(payload)
        if total_size is None:
            content = cast(dict[str, Any], cast(dict[str, Any], payload)["content"])
            total_size = _exact_int(content.get("totalSize"), "totalSize")
        all_draws.extend(_normalize_api_row(row, f"{SOURCE_API_URL}?{query}") for row in rows)
        pages.append(
            {
                "page": page_number,
                "row_count": len(rows),
                "response_sha256": hashlib.sha256(raw).hexdigest(),
                "transport": transport,
                "url": url,
            }
        )
        if not rows:
            break
        page_number += 1
    normalized = normalize_draws(all_draws)
    if len(normalized) != total_size:
        raise ValueError(
            f"official POWER_LOTTO pagination incomplete: expected {total_size}, "
            f"got {len(normalized)}"
        )
    return normalized, {
        "source_kind": "OFFICIAL_PUBLIC_API",
        "source_url": SOURCE_API_URL,
        "query": {"month": start_month, "endMonth": end_month, "page_size": page_size},
        "total_size": total_size,
        "pages": pages,
        "normalized_sha256": source_sha256(normalized),
    }


def load_normalized_source(
    path: Path,
) -> tuple[tuple[PowerLottoDrawRecord, ...], dict[str, object]]:
    """Load a task-owned normalized JSON source for offline/reproducible runs."""

    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    raw_rows: object
    if isinstance(payload, dict):
        raw_file_payload = cast(dict[str, Any], payload)
        raw_rows = raw_file_payload.get("draws")
    else:
        raw_rows = payload
    if not isinstance(raw_rows, list):
        raise ValueError("normalized POWER_LOTTO source must be a list or {draws: list}")
    rows = cast(list[object], raw_rows)
    draws: list[PowerLottoDrawRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("normalized POWER_LOTTO source row must be an object")
        raw_row = cast(dict[str, Any], row)
        main = raw_row.get("main_numbers", raw_row.get("numbers"))
        if not isinstance(main, list):
            raise ValueError("normalized source row has no main_numbers")
        raw_main = cast(list[object], main)
        second = raw_row.get("second_number", raw_row.get("special"))
        draws.append(
            PowerLottoDrawRecord(
                draw_number=str(raw_row.get("draw_number", raw_row.get("draw"))),
                draw_date=str(raw_row.get("draw_date", raw_row.get("date"))),
                main_numbers=tuple(_exact_int(value, "main_numbers") for value in raw_main),
                second_number=_exact_int(second, "second_number"),
                source_reference=str(raw_row.get("source_reference", path.name)),
            )
        )
    normalized = normalize_draws(draws)
    return normalized, {
        "source_kind": "TASK_OWNED_NORMALIZED_EXPORT",
        "source_path": str(path),
        "normalized_sha256": source_sha256(normalized),
        "row_count": len(normalized),
    }


def _metadata_value(obj: object, *names: str, default: object = None) -> object:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def coerce_strategy_metadata(obj: object) -> StrategyMetadata:
    """Read the card's strategy metadata without importing the shared catalog."""

    strategy_id = _metadata_value(obj, "strategy_id", "id")
    if not isinstance(strategy_id, str) or not strategy_id:
        raise ValueError("strategy object has no strategy_id")
    version = _metadata_value(obj, "strategy_version", "version", default="v1")
    native_count = _metadata_value(obj, "native_ticket_count", "bet_count", default=1)
    min_history = _metadata_value(obj, "min_history", default=0)
    paths = _metadata_value(obj, "source_paths", "provenance_paths", default=())
    family = _metadata_value(obj, "algorithm_family", "family", default="DONOR_PORT")
    provenance = _metadata_value(obj, "provenance", "source", default="P638_WAVE1")
    blocked = _metadata_value(obj, "blocked_reason", default=None)
    if not isinstance(version, str) or not version:
        raise ValueError(f"{strategy_id}: invalid strategy version")
    if type(native_count) is not int or native_count <= 0:
        raise ValueError(f"{strategy_id}: native_ticket_count must be positive")
    if type(min_history) is not int or min_history < 0:
        raise ValueError(f"{strategy_id}: min_history must be non-negative")
    if isinstance(paths, str):
        paths = (paths,)
    if not isinstance(paths, Iterable):
        paths = ()
    source_paths = tuple(str(path) for path in cast(Iterable[object], paths))
    return StrategyMetadata(
        strategy_id=strategy_id,
        strategy_version=version,
        native_ticket_count=native_count,
        min_history=min_history,
        source_paths=source_paths,
        algorithm_family=str(family),
        provenance=str(provenance),
        callable_object=obj,
        blocked_reason=str(blocked) if blocked is not None else None,
    )


def select_wave1_strategies(strategy_objects: Iterable[object]) -> tuple[StrategyMetadata, ...]:
    """Select the packet's stable eight-ID wave while surfacing missing/blocked entries."""

    by_id: dict[str, object] = {}
    for obj in strategy_objects:
        metadata = coerce_strategy_metadata(obj)
        if metadata.strategy_id in by_id:
            raise ValueError(f"duplicate P638 strategy id {metadata.strategy_id}")
        by_id[metadata.strategy_id] = obj
    selected: list[StrategyMetadata] = []
    for strategy_id in WAVE1_SELECTED_STRATEGY_IDS:
        obj = by_id.get(strategy_id)
        if obj is None:
            selected.append(
                StrategyMetadata(
                    strategy_id=strategy_id,
                    strategy_version="UNAVAILABLE",
                    native_ticket_count=1,
                    min_history=0,
                    source_paths=(),
                    algorithm_family="UNRECONSTRUCTABLE",
                    provenance="donor-ledger-missing-adapter",
                    blocked_reason="MISSING_RECONSTRUCTABLE_ADAPTER",
                )
            )
            continue
        selected.append(coerce_strategy_metadata(obj))
    return tuple(selected)


def _strategy_callable(metadata: StrategyMetadata) -> Callable[..., object]:
    target = metadata.callable_object
    if target is None:
        raise ValueError(f"{metadata.strategy_id}: no executable adapter")
    for name in ("predict_tickets", "get_bets", "predict", "get_one_bet"):
        candidate = getattr(target, name, None)
        if callable(candidate):
            return candidate
    if callable(target):
        return target
    raise ValueError(f"{metadata.strategy_id}: no executable prediction callable")


def _invoke_strategy(
    metadata: StrategyMetadata,
    history: Sequence[Mapping[str, object]],
) -> tuple[tuple[tuple[int, ...], int], ...]:
    function = _strategy_callable(metadata)
    try:
        parameter_count = len(inspect.signature(function).parameters)
    except (TypeError, ValueError):
        parameter_count = 2
    if parameter_count <= 1:
        raw = function(history)
    else:
        try:
            raw = function(history, LotteryType.POWER_LOTTO)
        except TypeError:
            raw = function(history, LOTTERY_TYPE)
    if isinstance(raw, tuple):
        raw_tuple = cast(tuple[object, ...], raw)
        if (
            len(raw_tuple) == 2
            and isinstance(raw_tuple[0], (tuple, list))
            and type(raw_tuple[1]) is int
        ):
            raw_tickets: Sequence[object] = (raw_tuple,)
        else:
            raw_tickets = raw_tuple
    elif isinstance(raw, list):
        raw_tickets = cast(list[object], raw)
    else:
        raise ValueError(f"{metadata.strategy_id}: prediction is not a ticket sequence")
    tickets: list[tuple[tuple[int, ...], int]] = []
    for position, candidate in enumerate(raw_tickets, start=1):
        if not isinstance(candidate, (tuple, list)):
            raise ValueError(
                f"{metadata.strategy_id}: complete ticket {position} is not a sequence"
            )
        complete_values = tuple(cast(Sequence[object], candidate))
        if len(complete_values) != 2:
            raise ValueError(f"{metadata.strategy_id}: ticket {position} is not complete")
        main_values = complete_values[0]
        second_zone = complete_values[1]
        if not isinstance(main_values, (tuple, list)) or type(second_zone) is not int:
            raise ValueError(f"{metadata.strategy_id}: ticket {position} is malformed")
        ticket_values = tuple(cast(Sequence[object], main_values))
        if len(ticket_values) != 6 or any(type(value) is not int for value in ticket_values):
            raise ValueError(f"{metadata.strategy_id}: ticket {position} first zone is malformed")
        ticket = cast(tuple[int, ...], ticket_values)
        if tuple(sorted(ticket)) != ticket or len(set(ticket)) != 6:
            raise ValueError(
                f"{metadata.strategy_id}: ticket {position} first zone is not canonical"
            )
        if any(value < 1 or value > 38 for value in ticket):
            raise ValueError(
                f"{metadata.strategy_id}: ticket {position} first zone is out of range"
            )
        if not 1 <= second_zone <= 8:
            raise ValueError(
                f"{metadata.strategy_id}: ticket {position} second zone is out of range"
            )
        tickets.append((ticket, second_zone))
    if len(tickets) != metadata.native_ticket_count:
        raise ValueError(
            f"{metadata.strategy_id}: expected {metadata.native_ticket_count} native tickets, "
            f"got {len(tickets)}"
        )
    return tuple(tickets)


def _history_payload(draws: Sequence[PowerLottoDrawRecord]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "lottery_type": LOTTERY_TYPE,
            "draw_number": draw.draw_number,
            "draw": draw.draw_number,
            "draw_date": draw.draw_date,
            "date": draw.draw_date,
            "numbers": list(draw.main_numbers),
            "main_numbers": list(draw.main_numbers),
            "special": draw.second_number,
            "second_number": draw.second_number,
        }
        for draw in draws
    )


def _task_db_path(db_path: Path, runtime_root: Path) -> Path:
    resolved_db = db_path.resolve()
    resolved_root = runtime_root.resolve()
    if not resolved_db.is_relative_to(resolved_root):
        raise ValueError("P638 task DB must remain inside the task runtime root")
    if resolved_db.name in {"lottery_v2.db", "production.db"}:
        raise ValueError("P638 task runner refuses canonical/production database names")
    return resolved_db


def _run_id(source_digest: str, strategies: Sequence[StrategyMetadata], ssot_version: str) -> str:
    identity = {
        "runner_version": RUNNER_VERSION,
        "source_sha256": source_digest,
        "strategies": [
            {
                "id": strategy.strategy_id,
                "version": strategy.strategy_version,
                "native": strategy.native_ticket_count,
                "min_history": strategy.min_history,
            }
            for strategy in strategies
        ],
        "second_zone_ssot_version": ssot_version,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"p638-wave1-{digest}"


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS run_metadata (
            run_id TEXT PRIMARY KEY,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
            runner_version TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            source_count INTEGER NOT NULL,
            source_commit TEXT NOT NULL,
            second_zone_ssot_version TEXT NOT NULL,
            second_zone_ssot_provenance TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE (run_id, lottery_type)
        );
        CREATE TABLE IF NOT EXISTS strategy_ledger (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
            native_ticket_count INTEGER NOT NULL,
            min_history INTEGER NOT NULL,
            source_paths_json TEXT NOT NULL,
            algorithm_family TEXT NOT NULL,
            provenance TEXT NOT NULL,
            selected INTEGER NOT NULL,
            blocked_reason TEXT,
            PRIMARY KEY (run_id, strategy_id, strategy_version),
            FOREIGN KEY (run_id) REFERENCES run_metadata(run_id)
        );
        CREATE TABLE IF NOT EXISTS draws (
            run_id TEXT NOT NULL,
            draw_number TEXT NOT NULL,
            draw_date TEXT NOT NULL,
            main_numbers_json TEXT NOT NULL,
            second_number INTEGER NOT NULL CHECK (second_number BETWEEN 1 AND 8),
            source_reference TEXT NOT NULL,
            PRIMARY KEY (run_id, draw_number),
            FOREIGN KEY (run_id) REFERENCES run_metadata(run_id)
        );
        CREATE TABLE IF NOT EXISTS strategy_targets (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
            target_draw_number TEXT NOT NULL,
            cutoff_draw_number TEXT,
            cutoff_index INTEGER NOT NULL,
            expected_ticket_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            failure_reason TEXT,
            PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_number),
            FOREIGN KEY (run_id, strategy_id, strategy_version)
                REFERENCES strategy_ledger(run_id, strategy_id, strategy_version)
        );
        CREATE TABLE IF NOT EXISTS tickets (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
            target_draw_number TEXT NOT NULL,
            ticket_position INTEGER NOT NULL,
            predicted_main_numbers_json TEXT NOT NULL,
            predicted_second_number INTEGER NOT NULL CHECK (
                predicted_second_number BETWEEN 1 AND 8
            ),
            native_ticket_count INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (status = 'COMPLETE'),
            ssot_version TEXT NOT NULL,
            provenance TEXT NOT NULL,
            PRIMARY KEY (
                run_id, strategy_id, strategy_version, target_draw_number, ticket_position
            ),
            FOREIGN KEY (run_id, strategy_id, strategy_version, target_draw_number)
                REFERENCES strategy_targets(
                    run_id, strategy_id, strategy_version, target_draw_number
                )
        );
        CREATE TABLE IF NOT EXISTS scores (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
            target_draw_number TEXT NOT NULL,
            ticket_position INTEGER NOT NULL,
            zone1_hits INTEGER NOT NULL CHECK (zone1_hits BETWEEN 0 AND 6),
            zone2_hit INTEGER NOT NULL CHECK (zone2_hit IN (0, 1)),
            PRIMARY KEY (
                run_id, strategy_id, strategy_version, target_draw_number, ticket_position
            ),
            FOREIGN KEY (
                run_id, strategy_id, strategy_version, target_draw_number, ticket_position
            ) REFERENCES tickets(
                run_id, strategy_id, strategy_version, target_draw_number, ticket_position
            )
        );
        CREATE TABLE IF NOT EXISTS failures (
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
            target_draw_number TEXT NOT NULL,
            status TEXT NOT NULL,
            failure_reason TEXT NOT NULL,
            PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_number),
            FOREIGN KEY (run_id, strategy_id, strategy_version, target_draw_number)
                REFERENCES strategy_targets(
                    run_id, strategy_id, strategy_version, target_draw_number
                )
        );
        CREATE TABLE IF NOT EXISTS completion (
            run_id TEXT PRIMARY KEY,
            total_source_targets INTEGER NOT NULL,
            selected_strategies INTEGER NOT NULL,
            eligible_attempts INTEGER NOT NULL,
            complete_targets INTEGER NOT NULL,
            excluded_targets INTEGER NOT NULL,
            failed_targets INTEGER NOT NULL,
            ticket_rows INTEGER NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES run_metadata(run_id)
        );
        """
    )
    for table in ("strategy_targets", "tickets", "scores", "failures"):
        columns = {
            str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if "lottery_type" not in columns:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN lottery_type TEXT NOT NULL DEFAULT 'POWER_LOTTO'"
            )
    connection.execute(
        """
        CREATE VIEW IF NOT EXISTS replay_output AS
        SELECT
            ticket.run_id,
            target.lottery_type,
            ticket.strategy_id,
            ticket.strategy_version,
            target.target_draw_number,
            target.cutoff_draw_number,
            target.cutoff_index,
            ticket.native_ticket_count,
            ticket.ticket_position,
            ticket.predicted_main_numbers_json,
            ticket.predicted_second_number,
            draw.main_numbers_json AS actual_main_numbers_json,
            draw.second_number AS actual_second_number,
            score.zone1_hits,
            score.zone2_hit,
            target.status,
            target.failure_reason,
            ticket.provenance,
            ticket.ssot_version,
            run.source_commit,
            run.source_sha256
        FROM tickets AS ticket
        JOIN strategy_targets AS target
          ON target.run_id = ticket.run_id
         AND target.strategy_id = ticket.strategy_id
         AND target.strategy_version = ticket.strategy_version
         AND target.target_draw_number = ticket.target_draw_number
        JOIN scores AS score
          ON score.run_id = ticket.run_id
         AND score.strategy_id = ticket.strategy_id
         AND score.strategy_version = ticket.strategy_version
         AND score.target_draw_number = ticket.target_draw_number
         AND score.ticket_position = ticket.ticket_position
        JOIN draws AS draw
          ON draw.run_id = target.run_id
         AND draw.draw_number = target.target_draw_number
        JOIN run_metadata AS run ON run.run_id = ticket.run_id
        """
    )


def _insert_strategy_ledger(
    connection: sqlite3.Connection,
    run_id: str,
    strategies: Sequence[StrategyMetadata],
) -> None:
    for strategy in strategies:
        connection.execute(
            """
            INSERT OR IGNORE INTO strategy_ledger (
                run_id, strategy_id, strategy_version, lottery_type,
                native_ticket_count, min_history, source_paths_json,
                algorithm_family, provenance, selected, blocked_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                strategy.strategy_id,
                strategy.strategy_version,
                LOTTERY_TYPE,
                strategy.native_ticket_count,
                strategy.min_history,
                json.dumps(strategy.source_paths, ensure_ascii=False, sort_keys=True),
                strategy.algorithm_family,
                strategy.provenance,
                int(strategy.selected),
                strategy.blocked_reason,
            ),
        )


def _insert_draws(
    connection: sqlite3.Connection,
    run_id: str,
    draws: Sequence[PowerLottoDrawRecord],
) -> None:
    for draw in draws:
        connection.execute(
            """
            INSERT OR IGNORE INTO draws (
                run_id, draw_number, draw_date, main_numbers_json,
                second_number, source_reference
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                draw.draw_number,
                draw.draw_date,
                json.dumps(draw.main_numbers, separators=(",", ":")),
                draw.second_number,
                draw.source_reference,
            ),
        )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _import_ssot() -> tuple[str, str, int, Callable[[Sequence[Mapping[str, object]]], int]]:
    from lottolab.strategies import powerlotto_second_zone

    predictor = getattr(powerlotto_second_zone, "second_zone_predict", None)
    if not callable(predictor):
        raise ValueError("P638 second-zone SSOT does not export second_zone_predict")
    version = getattr(powerlotto_second_zone, "SSOT_VERSION", "p638-second-zone-v1")
    raw_provenance = getattr(
        powerlotto_second_zone,
        "SSOT_PROVENANCE",
        "donor:power_lotto_second_zone.py;policy:causal-forward-only",
    )
    if isinstance(raw_provenance, Mapping):
        provenance = json.dumps(
            dict(cast(Mapping[str, object], raw_provenance)),
            ensure_ascii=False,
            sort_keys=True,
        )
    elif isinstance(raw_provenance, str):
        provenance = raw_provenance
    else:
        provenance = str(raw_provenance)
    if not isinstance(version, str) or not provenance:
        raise ValueError("P638 second-zone SSOT metadata is malformed")
    min_history = getattr(powerlotto_second_zone, "MIN_HISTORY", 30)
    if type(min_history) is not int or min_history < 0:
        raise ValueError("P638 second-zone SSOT MIN_HISTORY is malformed")
    return (
        version,
        provenance,
        min_history,
        cast(Callable[[Sequence[Mapping[str, object]]], int], predictor),
    )


def _write_reports(
    *,
    runtime_root: Path,
    result: ReplayResult,
    source_manifest: Mapping[str, object],
    coverage: Sequence[Mapping[str, object]],
    failures: Sequence[Mapping[str, object]],
    ssot_version: str,
    ssot_provenance: str,
) -> tuple[Path, ...]:
    db_digest = hashlib.sha256(result.db_path.read_bytes()).hexdigest()
    coverage_payload = {
        "run_id": result.run_id,
        "lottery_type": LOTTERY_TYPE,
        "source_sha256": result.source_sha256,
        "strategies": list(coverage),
        "blocked_donor_strategies": list(WAVE1_DONOR_BLOCKED_STRATEGIES),
        "completion_accounting": {
            "selected": result.selected_count,
            "eligible_attempts": result.eligible_attempt_count,
            "complete": result.complete_target_count,
            "excluded": result.excluded_target_count,
            "failed": result.failed_target_count,
        },
    }
    summary_payload = {
        "run_id": result.run_id,
        "lottery_type": LOTTERY_TYPE,
        "runner_version": RUNNER_VERSION,
        "source_sha256": result.source_sha256,
        "source_count": result.source_count,
        "task_db": str(result.db_path),
        "task_db_sha256": db_digest,
        "selected_strategy_count": result.selected_count,
        "eligible_attempt_count": result.eligible_attempt_count,
        "complete_target_count": result.complete_target_count,
        "excluded_target_count": result.excluded_target_count,
        "failed_target_count": result.failed_target_count,
        "ticket_row_count": result.ticket_count,
        "resume_idempotence": "TERMINAL_NATURAL_KEYS_AND_CONDITIONAL_COMPLETION_UPSERT",
        "deterministic_identity": "SOURCE_SHA256_AND_STRATEGY_VERSION_BOUND",
    }
    source_payload = {
        **dict(source_manifest),
        "lottery_type": LOTTERY_TYPE,
        "normalized_sha256": result.source_sha256,
        "source_commit": BASE_SOURCE_COMMIT,
        "historical_source_policy": "OFFICIAL_PUBLIC_TAIWAN_LOTTERY_API",
        "database_access": "NONE",
        "blocked_donor_strategies": list(WAVE1_DONOR_BLOCKED_STRATEGIES),
    }
    failure_payload = {
        "run_id": result.run_id,
        "lottery_type": LOTTERY_TYPE,
        "failures": [{"lottery_type": LOTTERY_TYPE, **dict(row)} for row in failures],
    }
    ssot_payload = {
        "lottery_type": LOTTERY_TYPE,
        "version": ssot_version,
        "provenance": ssot_provenance,
        "min_history": getattr(
            __import__("lottolab.strategies.powerlotto_second_zone", fromlist=["MIN_HISTORY"]),
            "MIN_HISTORY",
            30,
        ),
        "causal_input": "draws strictly before target",
        "output": {"type": "built-in int", "min": 1, "max": 8},
        "failure_policy": "exact failure on malformed or insufficient history",
        "lookahead": "FORBIDDEN",
        "alternatives": {
            "p47_p56_frequency_mean_reversion": "CONFLICTING_ALTERNATIVE_RECORDED",
            "p335a_live_fused_predictor": "BLOCKED_FOR_TASK_REPRODUCIBILITY",
        },
    }
    paths = (
        runtime_root / "strategy_coverage.json",
        runtime_root / "run_summary.json",
        runtime_root / "failure_ledger.json",
        runtime_root / "source_ledger.json",
        runtime_root / "second_zone_contract.json",
    )
    for path, payload in zip(
        paths,
        (coverage_payload, summary_payload, failure_payload, source_payload, ssot_payload),
        strict=True,
    ):
        _write_json(path, payload)
    return paths


def run_replay(
    *,
    draws: Sequence[PowerLottoDrawRecord],
    strategy_objects: Iterable[object],
    runtime_root: Path,
    db_path: Path | None = None,
    source_manifest: Mapping[str, object] | None = None,
) -> ReplayResult:
    """Run/resume the complete selected Wave 1 replay into the task DB."""

    normalized_draws = normalize_draws(draws)
    runtime_root = runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    resolved_db = _task_db_path(
        db_path or runtime_root / "p638_wave1.sqlite3",
        runtime_root,
    )
    strategies = select_wave1_strategies(strategy_objects)
    ssot_version, ssot_provenance, ssot_min_history, ssot_predict = _import_ssot()
    strategies = tuple(
        replace(
            strategy,
            min_history=max(strategy.min_history, ssot_min_history),
        )
        for strategy in strategies
    )
    digest = source_sha256(normalized_draws)
    run_id = _run_id(digest, strategies, ssot_version)
    manifest = dict(source_manifest or {})
    manifest.setdefault("source_kind", "TASK_INPUT")
    manifest.setdefault("normalized_sha256", digest)

    coverage_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []
    eligible_attempts = 0
    complete_targets = 0
    excluded_targets = 0
    failed_targets = 0
    ticket_count = 0

    connection = sqlite3.connect(resolved_db)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        _create_schema(connection)
        connection.execute(
            """
            INSERT OR IGNORE INTO run_metadata (
                run_id, lottery_type, runner_version, source_sha256, source_count,
                source_commit, second_zone_ssot_version, second_zone_ssot_provenance, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                LOTTERY_TYPE,
                RUNNER_VERSION,
                digest,
                len(normalized_draws),
                BASE_SOURCE_COMMIT,
                ssot_version,
                ssot_provenance,
                "RUNNING",
            ),
        )
        _insert_strategy_ledger(connection, run_id, strategies)
        _insert_draws(connection, run_id, normalized_draws)
        connection.commit()

        for strategy in strategies:
            if not strategy.selected:
                coverage_rows.append(
                    {
                        "strategy_id": strategy.strategy_id,
                        "strategy_version": strategy.strategy_version,
                        "selected": True,
                        "status": "BLOCKED",
                        "blocked_reason": strategy.blocked_reason,
                        "total_targets": len(normalized_draws),
                        "eligible_targets": 0,
                        "complete_targets": 0,
                        "excluded_targets": 0,
                        "failed_targets": 0,
                        "native_ticket_count": strategy.native_ticket_count,
                        "effective_min_history": strategy.min_history,
                    }
                )
                continue

            strategy_complete = 0
            strategy_excluded = 0
            strategy_failed = 0
            strategy_eligible = 0
            strategy_tickets = 0
            for target_index, target in enumerate(normalized_draws):
                history = normalized_draws[:target_index]
                cutoff = history[-1].draw_number if history else None
                existing = connection.execute(
                    """
                    SELECT status FROM strategy_targets
                    WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
                      AND target_draw_number = ?
                    """,
                    (run_id, strategy.strategy_id, strategy.strategy_version, target.draw_number),
                ).fetchone()
                if existing is not None and existing[0] in {
                    "COMPLETE",
                    "EXCLUDED_INSUFFICIENT_HISTORY",
                    "FAILED",
                }:
                    status = str(existing[0])
                    if status == "COMPLETE":
                        strategy_complete += 1
                        strategy_tickets += strategy.native_ticket_count
                    elif status == "EXCLUDED_INSUFFICIENT_HISTORY":
                        strategy_excluded += 1
                    else:
                        strategy_failed += 1
                    if status != "COMPLETE":
                        failure_rows.append(
                            {
                                "strategy_id": strategy.strategy_id,
                                "strategy_version": strategy.strategy_version,
                                "target_draw_number": target.draw_number,
                                "status": status,
                                "failure_reason": "RESUMED_EXISTING_TERMINAL_ROW",
                            }
                        )
                    continue

                strategy_eligible += int(len(history) >= strategy.min_history)
                eligible_attempts += int(len(history) >= strategy.min_history)
                connection.execute(
                    """
                    INSERT INTO strategy_targets (
                        run_id, strategy_id, strategy_version, lottery_type, target_draw_number,
                        cutoff_draw_number, cutoff_index, expected_ticket_count,
                        status, failure_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING', NULL)
                    ON CONFLICT (run_id, strategy_id, strategy_version, target_draw_number)
                    DO UPDATE SET status = 'RUNNING', failure_reason = NULL
                    """,
                    (
                        run_id,
                        strategy.strategy_id,
                        strategy.strategy_version,
                        LOTTERY_TYPE,
                        target.draw_number,
                        cutoff,
                        target_index,
                        strategy.native_ticket_count,
                    ),
                )
                connection.execute(
                    """
                    DELETE FROM scores WHERE run_id = ? AND strategy_id = ?
                      AND strategy_version = ? AND target_draw_number = ?
                    """,
                    (run_id, strategy.strategy_id, strategy.strategy_version, target.draw_number),
                )
                connection.execute(
                    """
                    DELETE FROM tickets WHERE run_id = ? AND strategy_id = ?
                      AND strategy_version = ? AND target_draw_number = ?
                    """,
                    (run_id, strategy.strategy_id, strategy.strategy_version, target.draw_number),
                )
                connection.execute(
                    """
                    DELETE FROM failures WHERE run_id = ? AND strategy_id = ?
                      AND strategy_version = ? AND target_draw_number = ?
                    """,
                    (run_id, strategy.strategy_id, strategy.strategy_version, target.draw_number),
                )
                if len(history) < strategy.min_history:
                    reason = (
                        f"INSUFFICIENT_CAUSAL_HISTORY_REQUIRED_{strategy.min_history}_GOT_"
                        f"{len(history)}"
                    )
                    connection.execute(
                        """
                        UPDATE strategy_targets
                        SET status = 'EXCLUDED_INSUFFICIENT_HISTORY', failure_reason = ?
                        WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
                          AND target_draw_number = ?
                        """,
                        (
                            reason,
                            run_id,
                            strategy.strategy_id,
                            strategy.strategy_version,
                            target.draw_number,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO failures (
                            run_id, strategy_id, strategy_version, lottery_type,
                            target_draw_number,
                            status, failure_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            strategy.strategy_id,
                            strategy.strategy_version,
                            LOTTERY_TYPE,
                            target.draw_number,
                            "EXCLUDED_INSUFFICIENT_HISTORY",
                            reason,
                        ),
                    )
                    connection.commit()
                    strategy_excluded += 1
                    excluded_targets += 1
                    failure_rows.append(
                        {
                            "strategy_id": strategy.strategy_id,
                            "strategy_version": strategy.strategy_version,
                            "target_draw_number": target.draw_number,
                            "status": "EXCLUDED_INSUFFICIENT_HISTORY",
                            "failure_reason": reason,
                        }
                    )
                    continue

                history_payload = _history_payload(history)
                try:
                    tickets = _invoke_strategy(strategy, history_payload)
                    predicted_second = _exact_int(
                        ssot_predict(list(history_payload)), "predicted second zone"
                    )
                    if not 1 <= predicted_second <= 8:
                        raise ValueError("P638 second-zone SSOT output out of range")
                    if any(second_zone != predicted_second for _ticket, second_zone in tickets):
                        raise ValueError("strategy ticket second zones disagree with P638 SSOT")
                    for position, (ticket, ticket_second_zone) in enumerate(tickets, start=1):
                        connection.execute(
                            """
                        INSERT INTO tickets (
                                run_id, strategy_id, strategy_version, lottery_type,
                                target_draw_number,
                            ticket_position, predicted_main_numbers_json,
                            predicted_second_number,
                                native_ticket_count, status, ssot_version, provenance
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETE', ?, ?)
                            """,
                            (
                                run_id,
                                strategy.strategy_id,
                                strategy.strategy_version,
                                LOTTERY_TYPE,
                                target.draw_number,
                                position,
                                json.dumps(ticket, separators=(",", ":")),
                                ticket_second_zone,
                                strategy.native_ticket_count,
                                ssot_version,
                                strategy.provenance,
                            ),
                        )
                        zone1_hits = len(set(ticket).intersection(target.main_numbers))
                        zone2_hit = int(ticket_second_zone == target.second_number)
                        connection.execute(
                            """
                            INSERT INTO scores (
                                run_id, strategy_id, strategy_version, lottery_type,
                                target_draw_number,
                                ticket_position, zone1_hits, zone2_hit
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                run_id,
                                strategy.strategy_id,
                                strategy.strategy_version,
                                LOTTERY_TYPE,
                                target.draw_number,
                                position,
                                zone1_hits,
                                zone2_hit,
                            ),
                        )
                    connection.execute(
                        """
                        UPDATE strategy_targets SET status = 'COMPLETE', failure_reason = NULL
                        WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
                          AND target_draw_number = ?
                        """,
                        (
                            run_id,
                            strategy.strategy_id,
                            strategy.strategy_version,
                            target.draw_number,
                        ),
                    )
                    connection.commit()
                    strategy_complete += 1
                    complete_targets += 1
                    strategy_tickets += len(tickets)
                    ticket_count += len(tickets)
                except Exception as exc:
                    reason = f"{type(exc).__name__}: {exc}"
                    connection.rollback()
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO strategy_targets (
                            run_id, strategy_id, strategy_version, lottery_type,
                            target_draw_number,
                            cutoff_draw_number, cutoff_index, expected_ticket_count,
                            status, failure_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'FAILED', ?)
                        """,
                        (
                            run_id,
                            strategy.strategy_id,
                            strategy.strategy_version,
                            LOTTERY_TYPE,
                            target.draw_number,
                            cutoff,
                            target_index,
                            strategy.native_ticket_count,
                            reason,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO failures (
                            run_id, strategy_id, strategy_version, lottery_type,
                            target_draw_number,
                            status, failure_reason
                        ) VALUES (?, ?, ?, ?, ?, 'FAILED', ?)
                        """,
                        (
                            run_id,
                            strategy.strategy_id,
                            strategy.strategy_version,
                            LOTTERY_TYPE,
                            target.draw_number,
                            reason,
                        ),
                    )
                    connection.commit()
                    strategy_failed += 1
                    failed_targets += 1
                    failure_rows.append(
                        {
                            "strategy_id": strategy.strategy_id,
                            "strategy_version": strategy.strategy_version,
                            "target_draw_number": target.draw_number,
                            "status": "FAILED",
                            "failure_reason": reason,
                        }
                    )

            coverage_rows.append(
                {
                    "strategy_id": strategy.strategy_id,
                    "strategy_version": strategy.strategy_version,
                    "selected": True,
                    "status": "COMPLETE" if strategy_failed == 0 else "COMPLETE_WITH_FAILURES",
                    "source_paths": list(strategy.source_paths),
                    "algorithm_family": strategy.algorithm_family,
                    "provenance": strategy.provenance,
                    "total_targets": len(normalized_draws),
                    "eligible_targets": strategy_eligible,
                    "complete_targets": strategy_complete,
                    "excluded_targets": strategy_excluded,
                    "failed_targets": strategy_failed,
                    "native_ticket_count": strategy.native_ticket_count,
                    "effective_min_history": strategy.min_history,
                    "ticket_rows": strategy_tickets,
                }
            )

        # Reconcile from the durable task DB rather than in-memory counters.
        # This makes a second invocation produce the same reports after it
        # skips terminal natural keys from the first invocation.
        coverage_rows = []
        failure_rows = []
        for strategy in strategies:
            if not strategy.selected:
                coverage_rows.append(
                    {
                        "strategy_id": strategy.strategy_id,
                        "strategy_version": strategy.strategy_version,
                        "selected": True,
                        "status": "BLOCKED",
                        "blocked_reason": strategy.blocked_reason,
                        "total_targets": len(normalized_draws),
                        "eligible_targets": 0,
                        "complete_targets": 0,
                        "excluded_targets": 0,
                        "failed_targets": 0,
                        "native_ticket_count": strategy.native_ticket_count,
                        "effective_min_history": strategy.min_history,
                    }
                )
                continue
            counts = {
                str(status): int(count)
                for status, count in connection.execute(
                    """
                    SELECT status, COUNT(*) FROM strategy_targets
                    WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
                    GROUP BY status
                    """,
                    (run_id, strategy.strategy_id, strategy.strategy_version),
                ).fetchall()
            }
            strategy_tickets = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM tickets
                    WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
                    """,
                    (run_id, strategy.strategy_id, strategy.strategy_version),
                ).fetchone()[0]
            )
            strategy_complete = counts.get("COMPLETE", 0)
            strategy_excluded = counts.get("EXCLUDED_INSUFFICIENT_HISTORY", 0)
            strategy_failed = counts.get("FAILED", 0)
            coverage_rows.append(
                {
                    "strategy_id": strategy.strategy_id,
                    "strategy_version": strategy.strategy_version,
                    "selected": True,
                    "status": "COMPLETE" if strategy_failed == 0 else "COMPLETE_WITH_FAILURES",
                    "source_paths": list(strategy.source_paths),
                    "algorithm_family": strategy.algorithm_family,
                    "provenance": strategy.provenance,
                    "total_targets": len(normalized_draws),
                    "eligible_targets": strategy_complete + strategy_failed,
                    "complete_targets": strategy_complete,
                    "excluded_targets": strategy_excluded,
                    "failed_targets": strategy_failed,
                    "native_ticket_count": strategy.native_ticket_count,
                    "effective_min_history": strategy.min_history,
                    "ticket_rows": strategy_tickets,
                }
            )
        failure_rows = [
            {
                "strategy_id": str(row[0]),
                "strategy_version": str(row[1]),
                "target_draw_number": str(row[2]),
                "status": str(row[3]),
                "failure_reason": str(row[4]),
            }
            for row in connection.execute(
                """
                SELECT strategy_id, strategy_version, target_draw_number, status, failure_reason
                FROM failures WHERE run_id = ?
                ORDER BY strategy_id, strategy_version, target_draw_number
                """,
                (run_id,),
            ).fetchall()
        ]
        eligible_attempts = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM strategy_targets
                WHERE run_id = ? AND status IN ('COMPLETE', 'FAILED')
                """,
                (run_id,),
            ).fetchone()[0]
        )
        complete_targets = int(
            connection.execute(
                "SELECT COUNT(*) FROM strategy_targets WHERE run_id = ? AND status = 'COMPLETE'",
                (run_id,),
            ).fetchone()[0]
        )
        excluded_targets = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM strategy_targets
                WHERE run_id = ? AND status = 'EXCLUDED_INSUFFICIENT_HISTORY'
                """,
                (run_id,),
            ).fetchone()[0]
        )
        failed_targets = int(
            connection.execute(
                "SELECT COUNT(*) FROM strategy_targets WHERE run_id = ? AND status = 'FAILED'",
                (run_id,),
            ).fetchone()[0]
        )
        ticket_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM tickets WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        )
        total_selected = len(strategies)
        run_status = "COMPLETE" if failed_targets == 0 else "COMPLETE_WITH_FAILURES"
        connection.execute(
            """
            INSERT INTO completion (
                run_id, total_source_targets, selected_strategies, eligible_attempts,
                complete_targets, excluded_targets, failed_targets, ticket_rows, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                total_source_targets = excluded.total_source_targets,
                selected_strategies = excluded.selected_strategies,
                eligible_attempts = excluded.eligible_attempts,
                complete_targets = excluded.complete_targets,
                excluded_targets = excluded.excluded_targets,
                failed_targets = excluded.failed_targets,
                ticket_rows = excluded.ticket_rows,
                status = excluded.status
            WHERE completion.total_source_targets != excluded.total_source_targets
               OR completion.selected_strategies != excluded.selected_strategies
               OR completion.eligible_attempts != excluded.eligible_attempts
               OR completion.complete_targets != excluded.complete_targets
               OR completion.excluded_targets != excluded.excluded_targets
               OR completion.failed_targets != excluded.failed_targets
               OR completion.ticket_rows != excluded.ticket_rows
               OR completion.status != excluded.status
            """,
            (
                run_id,
                len(normalized_draws),
                total_selected,
                eligible_attempts,
                complete_targets,
                excluded_targets,
                failed_targets,
                ticket_count,
                run_status,
            ),
        )
        connection.execute(
            "UPDATE run_metadata SET status = ? WHERE run_id = ? AND status <> ?",
            (run_status, run_id, run_status),
        )
        connection.commit()
    finally:
        connection.close()

    provisional = ReplayResult(
        run_id=run_id,
        source_sha256=digest,
        source_count=len(normalized_draws),
        selected_count=len(strategies),
        eligible_attempt_count=eligible_attempts,
        complete_target_count=complete_targets,
        excluded_target_count=excluded_targets,
        failed_target_count=failed_targets,
        ticket_count=ticket_count,
        db_path=resolved_db,
        artifact_paths=(),
    )
    artifact_paths = _write_reports(
        runtime_root=runtime_root,
        result=provisional,
        source_manifest=manifest,
        coverage=coverage_rows,
        failures=failure_rows,
        ssot_version=ssot_version,
        ssot_provenance=ssot_provenance,
    )
    return replace(provisional, artifact_paths=artifact_paths)


__all__ = [
    "BASE_SOURCE_COMMIT",
    "LOTTERY_TYPE",
    "RUNNER_VERSION",
    "SOURCE_API_URL",
    "WAVE1_DONOR_BLOCKED_STRATEGIES",
    "WAVE1_SELECTED_STRATEGY_IDS",
    "PowerLottoDrawRecord",
    "ReplayResult",
    "StrategyMetadata",
    "canonical_source_bytes",
    "fetch_official_powerlotto_draws",
    "load_normalized_source",
    "normalize_draws",
    "run_replay",
    "select_wave1_strategies",
    "source_sha256",
]
