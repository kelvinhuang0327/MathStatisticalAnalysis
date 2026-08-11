"""Explicit-path, read-only source loaders for the shared replay controller.

The loaders translate the two sealed historical storage contracts into the
domain's immutable :class:`ReplaySourceSnapshot`.  They do not create,
migrate, or write a source database, and they intentionally leave prediction
and prize semantics to the existing application adapters.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ReplayCellStatus,
    ReplayDraw,
    ReplaySourceSnapshot,
    ReplayStoredTarget,
    ReplayStoredTicket,
)
from lottolab.infrastructure.persistence.historical_schema import (
    HistoricalSchemaError,
    open_database,
    verify_schema_read_only,
)


class HistoricalReplaySourceError(RuntimeError):
    """A sealed replay source is absent, malformed, or unsafe to read."""


@dataclass(frozen=True, slots=True)
class ReplaySourceStrategyDefinition:
    """Storage-owned strategy identity used to assemble a replay request."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalReplaySourceBundle:
    """A source snapshot plus the source identity needed by a candidate run."""

    database: Path
    run_id: str
    snapshot: ReplaySourceSnapshot
    strategies: tuple[ReplaySourceStrategyDefinition, ...]
    source_sha256: str


T539_REQUIRED_TABLES = frozenset(
    {
        "run_metadata",
        "source_draws",
        "strategy_coverage",
        "prediction_tickets",
        "prediction_scores",
        "failure_ledger",
        "target_completion",
    }
)
P638_REQUIRED_TABLES = frozenset(
    {
        "historical_result_run",
        "historical_draw_snapshot",
        "historical_p638_run",
        "historical_p638_strategy_ledger",
        "historical_p638_target",
        "historical_p638_ticket",
    }
)


class SQLiteT539ReplaySourceLoader:
    """Load a sealed T539 flat-schema run without opening it for writes."""

    def __init__(self, database: Path) -> None:
        self._database = _validate_source_path(database)

    def load(
        self,
        *,
        run_id: str | None = None,
        official_draws: tuple[ReplayDraw, ...] = (),
    ) -> HistoricalReplaySourceBundle:
        with _t539_read_only_connection(self._database) as connection:
            selected_run_id = _select_t539_run(connection, run_id)
            draws = _load_t539_draws(connection, selected_run_id)
            strategies = _load_t539_strategies(connection, selected_run_id)
            stored_targets = _load_t539_targets(
                connection,
                selected_run_id,
                draws,
                _history_fingerprints(draws),
            )
            stored_tickets = _load_t539_tickets(connection, selected_run_id)
        snapshot = ReplaySourceSnapshot(
            lottery_type=LotteryType.DAILY_539,
            historical_draws=draws,
            official_draws=official_draws,
            stored_targets=stored_targets,
            stored_tickets=stored_tickets,
        )
        return HistoricalReplaySourceBundle(
            database=self._database,
            run_id=selected_run_id,
            snapshot=snapshot,
            strategies=strategies,
            source_sha256=_sha256_file(self._database),
        )


class SQLiteP638ReplaySourceLoader:
    """Load a P638 Historical Results V2 run through the verified schema."""

    def __init__(self, database: Path) -> None:
        self._database = _validate_source_path(database)

    def load(
        self,
        *,
        run_id: str | None = None,
        official_draws: tuple[ReplayDraw, ...] = (),
    ) -> HistoricalReplaySourceBundle:
        try:
            if not verify_schema_read_only(self._database):
                raise HistoricalReplaySourceError("P638 source database is absent")
            with open_database(self._database, read_only=True) as connection:
                table_names = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                if not table_names >= P638_REQUIRED_TABLES:
                    raise HistoricalReplaySourceError(
                        "P638 source database is missing required tables"
                    )
                selected_run_id = _select_p638_run(connection, run_id)
                draws = _load_p638_draws(connection, selected_run_id)
                strategies = _load_p638_strategies(connection, selected_run_id)
                stored_targets = _load_p638_targets(
                    connection,
                    selected_run_id,
                    draws,
                    strategies,
                    _history_fingerprints(draws),
                )
                stored_tickets = _load_p638_tickets(connection, selected_run_id)
        except HistoricalReplaySourceError:
            raise
        except (HistoricalSchemaError, sqlite3.Error) as exc:
            raise HistoricalReplaySourceError(
                "P638 source database failed read-only verification"
            ) from exc
        snapshot = ReplaySourceSnapshot(
            lottery_type=LotteryType.POWER_LOTTO,
            historical_draws=draws,
            official_draws=official_draws,
            stored_targets=stored_targets,
            stored_tickets=stored_tickets,
        )
        return HistoricalReplaySourceBundle(
            database=self._database,
            run_id=selected_run_id,
            snapshot=snapshot,
            strategies=strategies,
            source_sha256=_sha256_file(self._database),
        )


def _validate_source_path(database: Path) -> Path:
    if not database.is_absolute():
        raise HistoricalReplaySourceError("replay source path must be absolute")
    if "\x00" in str(database):
        raise HistoricalReplaySourceError("replay source path contains a null byte")
    if any(part.casefold() == "lotterynew" for part in database.parts):
        raise HistoricalReplaySourceError("LotteryNew source paths are forbidden")
    if "b649" in str(database).casefold():
        raise HistoricalReplaySourceError("B649 source paths are protected")
    resolved = database.resolve()
    if not resolved.is_file():
        raise HistoricalReplaySourceError("replay source database is unavailable")
    return resolved


@contextmanager
def _t539_read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    uri = f"{database.as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
    except sqlite3.Error as exc:
        raise HistoricalReplaySourceError("cannot open T539 source read-only") from exc
    try:
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA query_only = ON")
            table_names = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if not table_names >= T539_REQUIRED_TABLES:
                raise HistoricalReplaySourceError(
                    "T539 source database is missing required tables"
                )
        except HistoricalReplaySourceError:
            raise
        except sqlite3.Error as exc:
            raise HistoricalReplaySourceError("cannot verify T539 source safely") from exc
        yield connection
    finally:
        connection.close()


def _select_t539_run(connection: sqlite3.Connection, run_id: str | None) -> str:
    if run_id is not None:
        row = connection.execute(
            "SELECT run_id, lottery_type, status FROM run_metadata WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None or str(row[1]) != LotteryType.DAILY_539.value or str(row[2]) != "COMPLETE":
            raise HistoricalReplaySourceError("requested T539 run is not COMPLETE DAILY_539")
        return str(row[0])
    rows = connection.execute(
        "SELECT run_id FROM run_metadata WHERE lottery_type = ? AND status = 'COMPLETE' "
        "ORDER BY run_id ASC",
        (LotteryType.DAILY_539.value,),
    ).fetchall()
    if len(rows) != 1:
        raise HistoricalReplaySourceError(
            "T539 source must identify exactly one COMPLETE DAILY_539 run"
        )
    return str(rows[0][0])


def _load_t539_draws(
    connection: sqlite3.Connection, run_id: str
) -> tuple[ReplayDraw, ...]:
    rows = connection.execute(
        """
        SELECT draw_id, draw_date, main_numbers_json
        FROM source_draws
        WHERE lottery_type = ?
        ORDER BY draw_order ASC, draw_id ASC
        """,
        (LotteryType.DAILY_539.value,),
    ).fetchall()
    del run_id
    draws: list[ReplayDraw] = []
    seen: set[str] = set()
    for draw_id, draw_date, numbers_json in rows:
        number = str(draw_id)
        if number in seen:
            raise HistoricalReplaySourceError("T539 source draw identities are duplicated")
        seen.add(number)
        draws.append(
            ReplayDraw(
                lottery_type=LotteryType.DAILY_539,
                draw_number=number,
                draw_date=_parse_date(draw_date, "T539 draw date"),
                main_numbers=_decode_numbers(numbers_json, "T539 draw numbers"),
            )
        )
    if not draws:
        raise HistoricalReplaySourceError("T539 source has no official draws")
    return tuple(draws)


def _load_t539_strategies(
    connection: sqlite3.Connection, run_id: str
) -> tuple[ReplaySourceStrategyDefinition, ...]:
    rows = connection.execute(
        """
        SELECT strategy_id, strategy_version, native_ticket_count, min_history
        FROM strategy_coverage
        WHERE run_id = ? AND lottery_type = ?
        ORDER BY strategy_id ASC, strategy_version ASC
        """,
        (run_id, LotteryType.DAILY_539.value),
    ).fetchall()
    if not rows:
        raise HistoricalReplaySourceError("T539 source has no strategy coverage")
    return tuple(
        ReplaySourceStrategyDefinition(
            strategy_id=str(row[0]),
            strategy_version=str(row[1]),
            native_ticket_count=_exact_positive_int(row[2], "T539 native ticket count"),
            min_history=_exact_nonnegative_int(row[3], "T539 minimum history"),
        )
        for row in rows
    )


def _load_t539_targets(
    connection: sqlite3.Connection,
    run_id: str,
    draws: tuple[ReplayDraw, ...],
    history_fingerprints: dict[str, str],
) -> tuple[ReplayStoredTarget, ...]:
    draw_by_number = {draw.draw_number: draw for draw in draws}
    rows = connection.execute(
        """
        SELECT
            tc.strategy_id, tc.strategy_version, tc.target_draw_id,
            tc.status, tc.native_ticket_count,
            COALESCE(pt.cutoff_draw_id, fl.cutoff_draw_id)
        FROM target_completion AS tc
        LEFT JOIN (
            SELECT run_id, strategy_id, strategy_version, target_draw_id,
                   MIN(cutoff_draw_id) AS cutoff_draw_id
            FROM prediction_tickets
            GROUP BY run_id, strategy_id, strategy_version, target_draw_id
        ) AS pt
          ON pt.run_id = tc.run_id AND pt.strategy_id = tc.strategy_id
         AND pt.strategy_version = tc.strategy_version
         AND pt.target_draw_id = tc.target_draw_id
        LEFT JOIN (
            SELECT run_id, strategy_id, strategy_version, target_draw_id,
                   MIN(cutoff_draw_id) AS cutoff_draw_id
            FROM failure_ledger
            GROUP BY run_id, strategy_id, strategy_version, target_draw_id
        ) AS fl
          ON fl.run_id = tc.run_id AND fl.strategy_id = tc.strategy_id
         AND fl.strategy_version = tc.strategy_version
         AND fl.target_draw_id = tc.target_draw_id
        WHERE tc.run_id = ?
        ORDER BY CAST(tc.target_draw_id AS INTEGER), tc.strategy_id ASC
        """,
        (run_id,),
    ).fetchall()
    score_counts = {
        (str(row[0]), str(row[1]), str(row[2])): _exact_nonnegative_int(
            row[3], "T539 score count"
        )
        for row in connection.execute(
            """
            SELECT strategy_id, strategy_version, target_draw_id, COUNT(*)
            FROM prediction_scores
            WHERE run_id = ?
            GROUP BY strategy_id, strategy_version, target_draw_id
            """,
            (run_id,),
        ).fetchall()
    }
    result: list[ReplayStoredTarget] = []
    for strategy_id, version, target_id, status, native_count, cutoff_id in rows:
        target_number = str(target_id)
        target = draw_by_number.get(target_number)
        if target is None:
            raise HistoricalReplaySourceError("T539 target references an unknown draw")
        mapped_status = {
            "SUCCESS": ReplayCellStatus.COMPLETE,
            "FAILED": ReplayCellStatus.FAILED,
        }.get(str(status))
        if mapped_status is None:
            raise HistoricalReplaySourceError("T539 target status is not recognized")
        expected = _exact_positive_int(native_count, "T539 expected ticket count")
        result.append(
            ReplayStoredTarget(
                lottery_type=LotteryType.DAILY_539,
                target_draw_number=target_number,
                target_draw_date=target.draw_date,
                strategy_id=str(strategy_id),
                strategy_version=str(version),
                expected_ticket_count=expected,
                status=mapped_status,
                cutoff_draw_number=None if cutoff_id is None else str(cutoff_id),
                history_fingerprint=history_fingerprints[target_number],
                evaluation_complete=(
                    score_counts.get((str(strategy_id), str(version), target_number), 0)
                    == expected
                    if mapped_status is ReplayCellStatus.COMPLETE
                    else None
                ),
            )
        )
    return tuple(result)


def _load_t539_tickets(
    connection: sqlite3.Connection, run_id: str
) -> tuple[ReplayStoredTicket, ...]:
    rows = connection.execute(
        """
        SELECT pt.strategy_id, pt.strategy_version, pt.target_draw_id,
               pt.ticket_position, pt.main_numbers_json, pt.special_number,
               ps.target_draw_id
        FROM prediction_tickets AS pt
        LEFT JOIN prediction_scores AS ps
          ON ps.run_id = pt.run_id AND ps.strategy_id = pt.strategy_id
         AND ps.strategy_version = pt.strategy_version
         AND ps.target_draw_id = pt.target_draw_id
         AND ps.ticket_position = pt.ticket_position
        WHERE pt.run_id = ?
        ORDER BY CAST(pt.target_draw_id AS INTEGER), pt.strategy_id, pt.ticket_position
        """,
        (run_id,),
    ).fetchall()
    tickets: list[ReplayStoredTicket] = []
    for strategy_id, version, target_id, position, numbers_json, special, eval_target in rows:
        tickets.append(
            ReplayStoredTicket(
                lottery_type=LotteryType.DAILY_539,
                target_draw_number=str(target_id),
                strategy_id=str(strategy_id),
                strategy_version=str(version),
                ticket_position=_exact_positive_int(position, "T539 ticket position"),
                main_numbers=(
                    None
                    if numbers_json is None
                    else _decode_numbers(numbers_json, "T539 ticket numbers")
                ),
                special_number=None if special is None else _exact_int(special, "T539 special"),
                evaluation_target_draw_number=(
                    None if eval_target is None else str(eval_target)
                ),
            )
        )
    return tuple(tickets)


def _select_p638_run(connection: sqlite3.Connection, run_id: str | None) -> str:
    if run_id is not None:
        row = connection.execute(
            """
            SELECT p.run_id
            FROM historical_p638_run AS p
            JOIN historical_result_run AS r ON r.id = p.run_id
            WHERE p.run_id = ? AND p.lottery_type = 'POWER_LOTTO'
              AND r.lottery_type = 'POWER_LOTTO' AND r.status = 'COMPLETED'
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise HistoricalReplaySourceError("requested P638 run is not COMPLETE")
        return str(row[0])
    rows = connection.execute(
        """
        SELECT p.run_id
        FROM historical_p638_run AS p
        JOIN historical_result_run AS r ON r.id = p.run_id
        WHERE p.lottery_type = 'POWER_LOTTO'
          AND r.lottery_type = 'POWER_LOTTO' AND r.status = 'COMPLETED'
        ORDER BY r.completed_at ASC, p.run_id ASC
        """
    ).fetchall()
    if len(rows) != 1:
        raise HistoricalReplaySourceError(
            "P638 source must identify exactly one COMPLETE POWER_LOTTO run"
        )
    return str(rows[0][0])


def _load_p638_draws(
    connection: sqlite3.Connection, run_id: str
) -> tuple[ReplayDraw, ...]:
    rows = connection.execute(
        """
        SELECT draw_number, draw_date, main_numbers_json, special_numbers_json
        FROM historical_draw_snapshot
        WHERE run_id = ? AND lottery_type = 'POWER_LOTTO'
        ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
        """,
        (run_id,),
    ).fetchall()
    draws: list[ReplayDraw] = []
    seen: set[str] = set()
    for draw_number, draw_date, main_json, special_json in rows:
        number = str(draw_number)
        if number in seen:
            raise HistoricalReplaySourceError("P638 source draw identities are duplicated")
        seen.add(number)
        special = _decode_numbers(special_json, "P638 second-zone numbers")
        if len(special) != 1:
            raise HistoricalReplaySourceError("P638 source must preserve one second-zone number")
        draws.append(
            ReplayDraw(
                lottery_type=LotteryType.POWER_LOTTO,
                draw_number=number,
                draw_date=_parse_date(draw_date, "P638 draw date"),
                main_numbers=_decode_numbers(main_json, "P638 first-zone numbers"),
                special_number=special[0],
            )
        )
    if not draws:
        raise HistoricalReplaySourceError("P638 source has no official draws")
    return tuple(draws)


def _load_p638_strategies(
    connection: sqlite3.Connection, run_id: str
) -> tuple[ReplaySourceStrategyDefinition, ...]:
    rows = connection.execute(
        """
        SELECT strategy_id, strategy_version, native_ticket_count, min_history, provenance
        FROM historical_p638_strategy_ledger
        WHERE run_id = ? AND lottery_type = 'POWER_LOTTO'
        ORDER BY strategy_id ASC, strategy_version ASC
        """,
        (run_id,),
    ).fetchall()
    if not rows:
        raise HistoricalReplaySourceError("P638 source has no strategy ledger")
    definitions: list[ReplaySourceStrategyDefinition] = []
    for strategy_id, version, native_count, min_history, provenance in rows:
        definitions.append(
            ReplaySourceStrategyDefinition(
                strategy_id=str(strategy_id),
                strategy_version=str(version),
                native_ticket_count=_exact_positive_int(
                    native_count, "P638 native ticket count"
                )
                if native_count is not None
                else 1,
                min_history=_exact_nonnegative_int(min_history, "P638 minimum history")
                if min_history is not None
                else 0,
                fingerprint=(
                    None
                    if provenance is None
                    else hashlib.sha256(str(provenance).encode("utf-8")).hexdigest()
                ),
            )
        )
    return tuple(definitions)


def _load_p638_targets(
    connection: sqlite3.Connection,
    run_id: str,
    draws: tuple[ReplayDraw, ...],
    strategies: tuple[ReplaySourceStrategyDefinition, ...],
    history_fingerprints: dict[str, str],
) -> tuple[ReplayStoredTarget, ...]:
    draw_by_number = {draw.draw_number: draw for draw in draws}
    fingerprints = {strategy.strategy_id: strategy.fingerprint for strategy in strategies}
    rows = connection.execute(
        """
        SELECT strategy_id, strategy_version, target_draw_number, target_draw_date,
               expected_ticket_count, status, cutoff_draw_snapshot_id,
               history_boundary_draw_number
        FROM historical_p638_target
        WHERE run_id = ?
        ORDER BY target_draw_date ASC, CAST(target_draw_number AS INTEGER), strategy_id ASC
        """,
        (run_id,),
    ).fetchall()
    cutoff_rows = {
        int(row[0]): str(row[1])
        for row in connection.execute(
            "SELECT id, draw_number FROM historical_draw_snapshot WHERE run_id = ?",
            (run_id,),
        ).fetchall()
    }
    status_map = {
        "COMPLETE": ReplayCellStatus.COMPLETE,
        "EXCLUDED_INSUFFICIENT_HISTORY": ReplayCellStatus.NOT_ELIGIBLE,
        "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE": ReplayCellStatus.TYPED_CLOSURE,
        "FAILED": ReplayCellStatus.FAILED,
    }
    result: list[ReplayStoredTarget] = []
    for (
        strategy_id,
        version,
        target_number,
        target_date,
        expected,
        status,
        cutoff_id,
        _boundary,
    ) in rows:
        number = str(target_number)
        target = draw_by_number.get(number)
        if target is None:
            raise HistoricalReplaySourceError("P638 target references an unknown draw")
        mapped_status = status_map.get(str(status))
        if mapped_status is None:
            raise HistoricalReplaySourceError("P638 target status is not recognized")
        cutoff_number = None if cutoff_id is None else cutoff_rows.get(int(cutoff_id))
        result.append(
            ReplayStoredTarget(
                lottery_type=LotteryType.POWER_LOTTO,
                target_draw_number=number,
                target_draw_date=_parse_date(target_date, "P638 target date"),
                strategy_id=str(strategy_id),
                strategy_version=str(version),
                expected_ticket_count=_exact_positive_int(expected, "P638 expected ticket count"),
                status=mapped_status,
                cutoff_draw_number=cutoff_number,
                strategy_fingerprint=fingerprints.get(str(strategy_id)),
                history_fingerprint=history_fingerprints[number],
                evaluation_complete=(
                    mapped_status is ReplayCellStatus.COMPLETE
                ),
            )
        )
    return tuple(result)


def _load_p638_tickets(
    connection: sqlite3.Connection, run_id: str
) -> tuple[ReplayStoredTicket, ...]:
    rows = connection.execute(
        """
        SELECT strategy_id, strategy_version, target_draw_number, ticket_position,
               predicted_zone1_numbers_json, predicted_zone2_number
        FROM historical_p638_ticket
        WHERE run_id = ?
        ORDER BY target_draw_number ASC, strategy_id ASC, ticket_position ASC
        """,
        (run_id,),
    ).fetchall()
    return tuple(
        ReplayStoredTicket(
            lottery_type=LotteryType.POWER_LOTTO,
            target_draw_number=str(row[2]),
            strategy_id=str(row[0]),
            strategy_version=str(row[1]),
            ticket_position=_exact_positive_int(row[3], "P638 ticket position"),
            main_numbers=_decode_numbers(row[4], "P638 ticket first zone"),
            special_number=_exact_int(row[5], "P638 ticket second zone"),
            evaluation_target_draw_number=str(row[2]),
        )
        for row in rows
    )


def _parse_date(value: object, context: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise HistoricalReplaySourceError(f"{context} is malformed") from exc


def _decode_numbers(value: object, context: str) -> tuple[int, ...]:
    try:
        raw = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise HistoricalReplaySourceError(f"{context} is malformed") from exc
    if not isinstance(raw, list):
        raise HistoricalReplaySourceError(f"{context} is malformed")
    numbers = cast(list[object], raw)
    if not numbers or not all(type(item) is int for item in numbers):
        raise HistoricalReplaySourceError(f"{context} is malformed")
    return tuple(cast(list[int], numbers))


def _exact_int(value: object, context: str) -> int:
    if type(value) is not int:
        raise HistoricalReplaySourceError(f"{context} is malformed")
    return value


def _exact_positive_int(value: object, context: str) -> int:
    result = _exact_int(value, context)
    if result <= 0:
        raise HistoricalReplaySourceError(f"{context} is malformed")
    return result


def _exact_nonnegative_int(value: object, context: str) -> int:
    result = _exact_int(value, context)
    if result < 0:
        raise HistoricalReplaySourceError(f"{context} is malformed")
    return result


def _history_fingerprint(history: tuple[ReplayDraw, ...]) -> str:
    payload = [
        {
            "draw_number": draw.draw_number,
            "draw_date": draw.draw_date.isoformat(),
            "lottery_type": draw.lottery_type.value,
            "main_numbers": draw.main_numbers,
            "special_number": draw.special_number,
        }
        for draw in history
    ]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _history_fingerprints(draws: tuple[ReplayDraw, ...]) -> dict[str, str]:
    """Compute each target boundary once instead of once per strategy cell."""

    result: dict[str, str] = {}
    history: list[ReplayDraw] = []
    for draw in draws:
        result[draw.draw_number] = _history_fingerprint(tuple(history))
        history.append(draw)
    return result


def _sha256_file(database: Path) -> str:
    digest = hashlib.sha256()
    try:
        with database.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise HistoricalReplaySourceError("cannot hash replay source") from exc
    return digest.hexdigest()


__all__ = [
    "HistoricalReplaySourceBundle",
    "HistoricalReplaySourceError",
    "ReplaySourceStrategyDefinition",
    "SQLiteP638ReplaySourceLoader",
    "SQLiteT539ReplaySourceLoader",
]
