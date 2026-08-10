"""Read-only SQLite repository over a sealed T539 DAILY_539 database.

This vertical has no forwarding step and no shared migration-versioned
schema: it reads the frozen run's own flat tables directly
(``run_metadata``/``source_draws``/``strategy_coverage``/
``prediction_tickets``/``prediction_scores``/``failure_ledger``/
``target_completion``). The database is opened strictly read-only
(``mode=ro`` plus ``PRAGMA query_only = ON``) and is never created,
migrated, or written to by this module.

The static coverage ledger below (executed selection reasons and the full
blocked catalog) is transcribed from ``tools/run_daily539_t539_wave1.py``'s
strategy-set configurations, which is a task-owned runner script, not an
importable package module. Which catalog identities are actually blocked for
a given run is derived at read time against that run's own
``strategy_coverage`` rows, so one sealed database's blocked list shrinks as
later named configurations execute more of the catalog.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lottolab.application.t539_historical import (
    T539CoverageBlockedEntry,
    T539CoverageExecutedEntry,
    T539CoverageLedger,
    T539DrawPage,
    T539DrawRecord,
    T539HistoricalResultsUnavailableError,
    T539RankingPage,
    T539RankingRecord,
    T539ReplayPage,
    T539ReplayQuery,
    T539ReplayRecord,
    T539RunPage,
    T539RunSummary,
    T539StrategyMetrics,
    T539StrategyPage,
    T539StrategyRecord,
    T539TargetDetail,
    T539TicketRecord,
    t539_strategy_set_fingerprint,
)
from lottolab.domain.prize_evaluation import DAILY_FIVE39_PRIZE_RULE_CONTRACT

BUSY_TIMEOUT_MS = 5_000

REQUIRED_TABLES = frozenset(
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

_TIER_ORDER_IDS: tuple[str, ...] = tuple(
    tier.tier_id.value for tier in DAILY_FIVE39_PRIZE_RULE_CONTRACT.tiers
)
_WINNING_HIT_VALUES: frozenset[int] = frozenset(
    match_count
    for match_count in range(6)
    if DAILY_FIVE39_PRIZE_RULE_CONTRACT.resolve(match_count=match_count) is not None
)

_EXECUTED_SELECTION_REASONS: Mapping[str, str] = {
    "daily539_markov_cold": "Reuse the PR #85 main-ancestor adapter exactly as authorized.",
    "markov_1bet_539": "Complete deterministic P36 single-ticket source.",
    "acb_single_539": "Complete deterministic P36 single-ticket source.",
    "midfreq_acb_2bet": "Complete P128 native two-ticket output.",
    "midfreq_fourier_2bet": "Complete P128 native two-ticket output.",
    "acb_markov_midfreq_3bet": "Complete P128 Phase 2 native three-ticket output.",
    "daily539_f4cold_3bet": "Complete native first-three tickets from the P93 F4Cold source.",
    "daily539_f4cold_5bet": "Complete native five-ticket output from the P93 F4Cold source.",
    "daily539_f4cold": (
        "Wave 2 single-ticket coverage closure: equals native ticket 1 of the same "
        "complete F4Cold portfolio selected for the 3-bet and 5-bet identities."
    ),
    "acb_1bet": (
        "Wave 3 alias coverage closure: the P31A-retired donor (strategy_version "
        "v0.1-p31a) computes the identical ACB formula already exposed as "
        "acb_single_539's producer, so this identity reuses that one producer "
        "without duplicating the algorithm under a second name."
    ),
    "acb_markov_midfreq": (
        "Wave 4 batch coverage closure: standalone ACB+Markov midfreq-boosted "
        "fusion, a new distinct producer from the already-migrated "
        "acb_markov_midfreq_3bet family, donor-parity verified against real "
        "numpy execution."
    ),
    "zone_gap_3bet_539": (
        "Wave 4 batch coverage closure: a new distinct producer, bet-1 only -- no "
        "donor script anywhere in the archive implements a bet-2/bet-3 algorithm "
        "for this named 3-bet identity, so nothing was invented to fill that gap."
    ),
    "539_3bet_orthogonal": (
        "Wave 4 batch coverage closure: bet-1 is an exact alias of acb_single_539's "
        "producer -- the donor's own predict_acb_markov_fourier_bet1 is defined as "
        "exactly predict_acb_single -- so this identity reuses that one producer "
        "instead of duplicating the algorithm under a second name."
    ),
    "p0b_539_3bet_f_cold_fmid": (
        "Wave 4 batch coverage closure: a new distinct producer, bet-1 only -- no "
        "donor script anywhere in the archive implements a bet-2/bet-3 algorithm "
        "for this named 3-bet identity, so nothing was invented to fill that gap."
    ),
    "p0c_539_3bet_f_cold_x2": (
        "Wave 4 batch coverage closure: a new distinct producer, bet-1 only -- no "
        "donor script anywhere in the archive implements a bet-2/bet-3 algorithm "
        "for this named 3-bet identity, so nothing was invented to fill that gap."
    ),
}


def _selection_reason(strategy_id: str) -> str:
    """Return a stable explanation for legacy and R2 target identities."""

    configured = _EXECUTED_SELECTION_REASONS.get(strategy_id)
    if configured is not None:
        return configured
    if strategy_id.startswith("t539_biglotto_"):
        return (
            "BIGLOTTO68 R2 exhaustive closure: target-native DAILY_539 GameSpec "
            "port of a verified portable BIG_LOTTO donor family."
        )
    return ""


_ALL_BLOCKED_STRATEGIES: tuple[T539CoverageBlockedEntry, ...] = (
    T539CoverageBlockedEntry(
        strategy_id="daily539_f4cold",
        reason_code="WAVE1_SELECTION_CAP_DERIVED_DUPLICATE",
        reason=(
            "Deferred at the eight-strategy Wave 1 cap; its single ticket is the first "
            "ticket of the selected native F4Cold portfolio."
        ),
    ),
    T539CoverageBlockedEntry(
        strategy_id="acb_1bet",
        reason_code="SOURCE_PROVENANCE_INCOMPLETE",
        reason=(
            "Catalog row exists, but the authorized primary donor set does not contain "
            "a complete no-DB producer identity for this alias."
        ),
    ),
    T539CoverageBlockedEntry(
        strategy_id="acb_markov_midfreq",
        reason_code="SOURCE_PROVENANCE_INCOMPLETE",
        reason=(
            "Catalog row exists, but the authorized primary donor set does not contain "
            "a complete no-DB producer identity for this alias."
        ),
    ),
    T539CoverageBlockedEntry(
        strategy_id="zone_gap_3bet_539",
        reason_code="INCOMPLETE_NATIVE_TICKET_SOURCE",
        reason=(
            "P36 source exposes only bet 1 while the task requires the complete native "
            "three-ticket set."
        ),
    ),
    T539CoverageBlockedEntry(
        strategy_id="539_3bet_orthogonal",
        reason_code="INCOMPLETE_NATIVE_TICKET_SOURCE",
        reason=(
            "P36 source exposes only bet 1 while the task requires the complete native "
            "three-ticket set."
        ),
    ),
    T539CoverageBlockedEntry(
        strategy_id="p0b_539_3bet_f_cold_fmid",
        reason_code="INCOMPLETE_NATIVE_TICKET_SOURCE",
        reason=(
            "P36 source exposes only bet 1 and does not provide the complete native "
            "three-ticket variant."
        ),
    ),
    T539CoverageBlockedEntry(
        strategy_id="p0c_539_3bet_f_cold_x2",
        reason_code="INCOMPLETE_NATIVE_TICKET_SOURCE",
        reason=(
            "P36 source exposes only bet 1 and does not provide the complete native "
            "three-ticket variant."
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class _RankingCandidate:
    """Internal, strictly-typed intermediate for one strategy's ranking inputs."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    eligible_target_count: int
    winning_target_count: int
    winning_target_rate: float
    total_ticket_count: int
    winning_ticket_count: int
    ticket_winning_rate: float
    prize_tier_counts: tuple[tuple[str, int], ...]
    highest_prize_tier_achieved: str | None
    first_eligible_draw: str | None
    last_eligible_draw: str | None


_REPLAY_FROM_JOIN = """
FROM target_completion tc
LEFT JOIN (
    SELECT DISTINCT run_id, strategy_id, strategy_version, target_draw_id,
           target_draw_date, cutoff_draw_id, cutoff_draw_date
    FROM prediction_tickets
) pt ON pt.run_id = tc.run_id AND pt.strategy_id = tc.strategy_id
     AND pt.strategy_version = tc.strategy_version AND pt.target_draw_id = tc.target_draw_id
LEFT JOIN failure_ledger fl ON fl.run_id = tc.run_id AND fl.strategy_id = tc.strategy_id
     AND fl.strategy_version = tc.strategy_version AND fl.target_draw_id = tc.target_draw_id
"""


@contextmanager
def _read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    if not database.exists() or not database.is_file():
        raise T539HistoricalResultsUnavailableError("T539 Wave 1 database is unavailable")
    uri = f"{database.resolve().as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(
            uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1_000, isolation_level=None
        )
    except sqlite3.Error as exc:
        raise T539HistoricalResultsUnavailableError(
            "cannot open the T539 Wave 1 database safely"
        ) from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA query_only = ON")
            table_names = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            if not REQUIRED_TABLES.issubset(table_names):
                raise T539HistoricalResultsUnavailableError(
                    "T539 Wave 1 database is missing required tables"
                )
        except sqlite3.Error as exc:
            raise T539HistoricalResultsUnavailableError(
                "cannot verify the T539 Wave 1 database safely"
            ) from exc
        yield connection
    finally:
        connection.close()


def verify_schema_read_only(database: Path) -> bool:
    """Return False for an absent DB; raise for an existing DB with a bad schema."""

    if not database.exists() or not database.is_file():
        return False
    with _read_only_connection(database):
        pass
    return True


def _scalar(connection: sqlite3.Connection, sql: str, params: Sequence[object] = ()) -> int:
    row = connection.execute(sql, params).fetchone()
    value = row[0] if row is not None else None
    if value is None:
        return 0
    if type(value) is not int:
        raise T539HistoricalResultsUnavailableError(
            "T539 Wave 1 database returned a non-integer count"
        )
    return value


def _db_int(value: object) -> int:
    if type(value) is not int:
        raise T539HistoricalResultsUnavailableError(
            "T539 Wave 1 database returned a non-integer value"
        )
    return value


def _text(value: object) -> str:
    if type(value) is not str:
        raise T539HistoricalResultsUnavailableError(
            "T539 Wave 1 database returned a non-text value"
        )
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value)


def _strategy_set_fingerprint_from_json(value: object) -> str:
    """Decode the runner's canonical strategy payload without trusting its order."""

    raw = _text(value)
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise T539HistoricalResultsUnavailableError(
            "T539 database has malformed strategy-set JSON"
        ) from exc
    if not isinstance(decoded, list):
        raise T539HistoricalResultsUnavailableError("T539 database strategy-set JSON is not a list")
    identities: list[str] = []
    items = cast(list[object], decoded)
    for raw_item in items:
        if not isinstance(raw_item, Mapping):
            raise T539HistoricalResultsUnavailableError(
                "T539 database strategy-set JSON has an invalid entry"
            )
        item = cast(Mapping[str, object], raw_item)
        strategy_id = item.get("strategy_id")
        strategy_version = item.get("strategy_version")
        if not isinstance(strategy_id, str) or not isinstance(strategy_version, str):
            raise T539HistoricalResultsUnavailableError(
                "T539 database strategy-set JSON has an invalid identity"
            )
        identities.append(f"{strategy_id}@{strategy_version}")
    return t539_strategy_set_fingerprint(identities)


def _decode_numbers_json(value: object) -> tuple[int, ...]:
    if type(value) is not str:
        raise T539HistoricalResultsUnavailableError(
            "T539 Wave 1 database has a non-text numbers column"
        )
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise T539HistoricalResultsUnavailableError(
            "T539 Wave 1 database has malformed numbers JSON"
        ) from exc
    if not isinstance(decoded, list):
        raise T539HistoricalResultsUnavailableError(
            "T539 Wave 1 database numbers JSON is not an integer list"
        )
    items = cast(list[object], decoded)
    if not all(type(item) is int for item in items):
        raise T539HistoricalResultsUnavailableError(
            "T539 Wave 1 database numbers JSON is not an integer list"
        )
    return tuple(cast(list[int], items))


def _prize_tier_counts(
    hit_distribution: tuple[tuple[int, int], ...],
) -> tuple[tuple[str, int], ...]:
    counts = dict.fromkeys(_TIER_ORDER_IDS, 0)
    for hits, count in hit_distribution:
        tier = DAILY_FIVE39_PRIZE_RULE_CONTRACT.resolve(match_count=hits)
        if tier is not None:
            counts[tier.tier_id.value] += count
    return tuple((tier_id, counts[tier_id]) for tier_id in _TIER_ORDER_IDS)


def _parse_target_id(target_id: str) -> tuple[str, str, str] | None:
    parts = target_id.split(":")
    if len(parts) != 3 or not all(parts):
        return None
    strategy_id, strategy_version, target_draw_id = parts
    return strategy_id, strategy_version, target_draw_id


def _replay_predicate(run_id: str, query: T539ReplayQuery) -> tuple[str, tuple[object, ...]]:
    clauses = ["tc.run_id = ?"]
    params: list[object] = [run_id]
    if query.strategy_id is not None:
        clauses.append("tc.strategy_id = ?")
        params.append(query.strategy_id)
    if query.status is not None:
        clauses.append("tc.status = ?")
        params.append(
            {
                "COMPLETE_CAUSAL_REPLAY": "SUCCESS",
                # Pre-eligibility cells are derived from coverage plus draws
                # and are intentionally not present in target_completion.
                "PRE_ELIGIBILITY": "__PRE_ELIGIBILITY_NOT_PERSISTED__",
            }.get(query.status, query.status)
        )
    if query.date_from is not None:
        clauses.append("COALESCE(pt.target_draw_date, fl.target_draw_date) >= ?")
        params.append(query.date_from)
    if query.date_to is not None:
        clauses.append("COALESCE(pt.target_draw_date, fl.target_draw_date) <= ?")
        params.append(query.date_to)
    return " AND ".join(clauses), tuple(params)


class SQLiteT539HistoricalQueryRepository:
    """Read-only :class:`T539HistoricalQueryRepository` over a sealed T539 DB."""

    def __init__(self, database: Path) -> None:
        self._database = database

    def list_runs(self, *, limit: int, offset: int) -> T539RunPage:
        with _read_only_connection(self._database) as connection:
            total_count = _scalar(connection, "SELECT COUNT(*) FROM run_metadata")
            rows = connection.execute(
                "SELECT run_id, schema_version, lottery_type, source_endpoint, source_sha256, "
                "as_of_date, adapter_source_commit, status, strategy_set_json "
                "FROM run_metadata "
                "ORDER BY run_id ASC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            items = tuple(self._row_to_run_summary(connection, row) for row in rows)
        return T539RunPage(items=items, total_count=total_count, limit=limit, offset=offset)

    def _row_to_run_summary(
        self, connection: sqlite3.Connection, row: Sequence[object]
    ) -> T539RunSummary:
        (
            run_id,
            schema_version,
            lottery_type,
            source_endpoint,
            source_sha256,
            as_of_date,
            adapter_source_commit,
            status,
            strategy_set_json,
        ) = row
        strategy_count = _scalar(
            connection, "SELECT COUNT(*) FROM strategy_coverage WHERE run_id = ?", (run_id,)
        )
        draw_count = _scalar(connection, "SELECT COUNT(*) FROM source_draws")
        eligible_target_count = _scalar(
            connection, "SELECT COUNT(*) FROM target_completion WHERE run_id = ?", (run_id,)
        )
        ticket_count = _scalar(
            connection, "SELECT COUNT(*) FROM prediction_tickets WHERE run_id = ?", (run_id,)
        )
        failure_count = _scalar(
            connection, "SELECT COUNT(*) FROM failure_ledger WHERE run_id = ?", (run_id,)
        )
        first = connection.execute(
            "SELECT draw_id, draw_date FROM source_draws ORDER BY draw_order ASC LIMIT 1"
        ).fetchone()
        last = connection.execute(
            "SELECT draw_id, draw_date FROM source_draws ORDER BY draw_order DESC LIMIT 1"
        ).fetchone()
        return T539RunSummary(
            run_id=_text(run_id),
            schema_version=_text(schema_version),
            lottery_type=_text(lottery_type),
            source_endpoint=_text(source_endpoint),
            source_sha256=_text(source_sha256),
            as_of_date=_text(as_of_date),
            adapter_source_commit=_text(adapter_source_commit),
            strategy_set_fingerprint=_strategy_set_fingerprint_from_json(strategy_set_json),
            status=_text(status),
            strategy_count=strategy_count,
            draw_count=draw_count,
            eligible_target_count=eligible_target_count,
            ticket_count=ticket_count,
            failure_count=failure_count,
            first_draw_id=_optional_text(first[0]) if first is not None else None,
            first_draw_date=_optional_text(first[1]) if first is not None else None,
            last_draw_id=_optional_text(last[0]) if last is not None else None,
            last_draw_date=_optional_text(last[1]) if last is not None else None,
        )

    def list_strategies(self, run_id: str, *, limit: int, offset: int) -> T539StrategyPage | None:
        with _read_only_connection(self._database) as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM run_metadata WHERE run_id = ?", (run_id,)
                ).fetchone()
                is None
            ):
                return None
            total_count = _scalar(
                connection, "SELECT COUNT(*) FROM strategy_coverage WHERE run_id = ?", (run_id,)
            )
            rows = connection.execute(
                "SELECT strategy_id, strategy_version, native_ticket_count, min_history, "
                "first_eligible_target_draw_id, expected_target_draw_count, "
                "processed_target_draw_count, successful_target_draw_count, "
                "failed_target_draw_count, status FROM strategy_coverage WHERE run_id = ? "
                "ORDER BY strategy_id ASC, strategy_version ASC LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            ).fetchall()
            items = tuple(self._row_to_strategy_record(connection, run_id, row) for row in rows)
        return T539StrategyPage(
            run_id=run_id, items=items, total_count=total_count, limit=limit, offset=offset
        )

    def list_draws(self, run_id: str, *, limit: int, offset: int) -> T539DrawPage | None:
        with _read_only_connection(self._database) as connection:
            if connection.execute(
                "SELECT 1 FROM run_metadata WHERE run_id = ?", (run_id,)
            ).fetchone() is None:
                return None
            total_count = _scalar(connection, "SELECT COUNT(*) FROM source_draws")
            rows = connection.execute(
                "SELECT draw_id, draw_date, main_numbers_json FROM source_draws "
                "ORDER BY draw_order ASC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return T539DrawPage(
            run_id=run_id,
            items=tuple(
                T539DrawRecord(
                    draw_id=_text(draw_id),
                    draw_date=_text(draw_date),
                    winning_numbers=_decode_numbers_json(numbers_json),
                )
                for draw_id, draw_date, numbers_json in rows
            ),
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def get_draw(self, run_id: str, draw_id: str) -> T539DrawRecord | None:
        with _read_only_connection(self._database) as connection:
            if connection.execute(
                "SELECT 1 FROM run_metadata WHERE run_id = ?", (run_id,)
            ).fetchone() is None:
                return None
            row = connection.execute(
                "SELECT draw_id, draw_date, main_numbers_json FROM source_draws WHERE draw_id = ?",
                (draw_id,),
            ).fetchone()
        if row is None:
            return None
        return T539DrawRecord(
            draw_id=_text(row[0]),
            draw_date=_text(row[1]),
            winning_numbers=_decode_numbers_json(row[2]),
        )

    def _row_to_strategy_record(
        self, connection: sqlite3.Connection, run_id: str, row: Sequence[object]
    ) -> T539StrategyRecord:
        (
            strategy_id,
            strategy_version,
            native_ticket_count,
            min_history,
            first_eligible_target_draw_id,
            expected,
            processed,
            successful,
            failed,
            status,
        ) = row
        ticket_count = _scalar(
            connection,
            "SELECT COUNT(*) FROM prediction_tickets "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
            (run_id, strategy_id, strategy_version),
        )
        hit_rows = connection.execute(
            "SELECT hits, COUNT(*) FROM prediction_scores "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ? "
            "GROUP BY hits ORDER BY hits",
            (run_id, strategy_id, strategy_version),
        ).fetchall()
        hit_distribution = tuple((_db_int(hits), _db_int(count)) for hits, count in hit_rows)
        winning_ticket_count = sum(
            count for hits, count in hit_distribution if hits in _WINNING_HIT_VALUES
        )
        dates = connection.execute(
            "SELECT MIN(target_draw_date), MAX(target_draw_date) FROM prediction_tickets "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
            (run_id, strategy_id, strategy_version),
        ).fetchone()
        return T539StrategyRecord(
            run_id=run_id,
            strategy_id=_text(strategy_id),
            strategy_version=_text(strategy_version),
            native_ticket_count=_db_int(native_ticket_count),
            min_history=_db_int(min_history),
            first_eligible_target_draw_id=_optional_text(first_eligible_target_draw_id),
            expected_target_draw_count=_db_int(expected),
            processed_target_draw_count=_db_int(processed),
            successful_target_draw_count=_db_int(successful),
            failed_target_draw_count=_db_int(failed),
            status=_text(status),
            ticket_count=ticket_count,
            winning_ticket_count=winning_ticket_count,
            hit_distribution=hit_distribution,
            first_target_draw_date=_optional_text(dates[0]) if dates is not None else None,
            last_target_draw_date=_optional_text(dates[1]) if dates is not None else None,
        )

    def list_replay(self, run_id: str, query: T539ReplayQuery) -> T539ReplayPage | None:
        with _read_only_connection(self._database) as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM run_metadata WHERE run_id = ?", (run_id,)
                ).fetchone()
                is None
            ):
                return None
            where_sql, params = _replay_predicate(run_id, query)
            total_count = _scalar(
                connection, f"SELECT COUNT(*) {_REPLAY_FROM_JOIN} WHERE {where_sql}", params
            )
            rows = connection.execute(
                f"""
                SELECT tc.strategy_id, tc.strategy_version, tc.target_draw_id, tc.status,
                       tc.native_ticket_count,
                       COALESCE(pt.target_draw_date, fl.target_draw_date) AS target_draw_date,
                       COALESCE(pt.cutoff_draw_id, fl.cutoff_draw_id) AS cutoff_draw_id,
                       pt.cutoff_draw_date
                {_REPLAY_FROM_JOIN}
                WHERE {where_sql}
                ORDER BY target_draw_date ASC, CAST(tc.target_draw_id AS INTEGER) ASC,
                         tc.strategy_id ASC, tc.strategy_version ASC
                LIMIT ? OFFSET ?
                """,
                (*params, query.limit, query.offset),
            ).fetchall()
            items = tuple(self._row_to_replay_record(connection, run_id, row) for row in rows)
        return T539ReplayPage(
            run_id=run_id,
            items=items,
            total_count=total_count,
            limit=query.limit,
            offset=query.offset,
        )

    def get_target(self, run_id: str, target_id: str) -> T539TargetDetail | None:
        parsed = _parse_target_id(target_id)
        if parsed is None:
            return None
        strategy_id, strategy_version, target_draw_id = parsed
        with _read_only_connection(self._database) as connection:
            row = connection.execute(
                f"""
                SELECT tc.strategy_id, tc.strategy_version, tc.target_draw_id, tc.status,
                       tc.native_ticket_count,
                       COALESCE(pt.target_draw_date, fl.target_draw_date) AS target_draw_date,
                       COALESCE(pt.cutoff_draw_id, fl.cutoff_draw_id) AS cutoff_draw_id,
                       pt.cutoff_draw_date
                {_REPLAY_FROM_JOIN}
                WHERE tc.run_id = ? AND tc.strategy_id = ? AND tc.strategy_version = ?
                      AND tc.target_draw_id = ?
                """,
                (run_id, strategy_id, strategy_version, target_draw_id),
            ).fetchone()
            if row is None:
                strategy_row = connection.execute(
                    "SELECT strategy_id, strategy_version, native_ticket_count, min_history, "
                    "first_eligible_target_draw_id FROM strategy_coverage "
                    "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
                    (run_id, strategy_id, strategy_version),
                ).fetchone()
                draw_row = connection.execute(
                    "SELECT draw_id, draw_date, draw_order FROM source_draws WHERE draw_id = ?",
                    (target_draw_id,),
                ).fetchone()
                if strategy_row is None or draw_row is None:
                    return None
                first_eligible = strategy_row[4]
                first_eligible_row = connection.execute(
                    "SELECT draw_order FROM source_draws WHERE draw_id = ?",
                    (first_eligible,),
                ).fetchone()
                if first_eligible_row is None or int(draw_row[2]) >= int(first_eligible_row[0]):
                    return None
                cutoff = connection.execute(
                    "SELECT draw_id, draw_date FROM source_draws "
                    "WHERE draw_order < ? ORDER BY draw_order DESC LIMIT 1",
                    (draw_row[2],),
                ).fetchone()
                return T539ReplayRecord(
                    target_id=f"{strategy_id}:{strategy_version}:{target_draw_id}",
                    run_id=run_id,
                    strategy_id=_text(strategy_id),
                    strategy_version=_text(strategy_version),
                    target_draw_id=_text(target_draw_id),
                    target_draw_date=_text(draw_row[1]),
                    cutoff_draw_id=None if cutoff is None else _text(cutoff[0]),
                    cutoff_draw_date=None if cutoff is None else _text(cutoff[1]),
                    status="PRE_ELIGIBILITY",
                    native_ticket_count=_db_int(strategy_row[2]),
                    tickets=(),
                    history_length=int(draw_row[2]),
                    reason_type="INSUFFICIENT_CAUSAL_HISTORY",
                    reason=(
                        f"strategy requires {_db_int(strategy_row[3])} historical draws "
                        f"before this target"
                    ),
                )
            return self._row_to_replay_record(connection, run_id, row)

    def _row_to_replay_record(
        self, connection: sqlite3.Connection, run_id: str, row: Sequence[object]
    ) -> T539ReplayRecord:
        (
            strategy_id,
            strategy_version,
            target_draw_id,
            status,
            native_ticket_count,
            target_draw_date,
            cutoff_draw_id,
            cutoff_draw_date,
        ) = row
        tickets: tuple[T539TicketRecord, ...] = ()
        if status == "SUCCESS":
            ticket_rows = connection.execute(
                "SELECT pt.ticket_position, pt.main_numbers_json, "
                "ps.actual_main_numbers_json, ps.hit_numbers_json, ps.hits "
                "FROM prediction_tickets pt JOIN prediction_scores ps "
                "ON ps.run_id = pt.run_id AND ps.strategy_id = pt.strategy_id "
                "AND ps.strategy_version = pt.strategy_version "
                "AND ps.target_draw_id = pt.target_draw_id "
                "AND ps.ticket_position = pt.ticket_position "
                "WHERE pt.run_id = ? AND pt.strategy_id = ? AND pt.strategy_version = ? "
                "AND pt.target_draw_id = ? ORDER BY pt.ticket_position ASC",
                (run_id, strategy_id, strategy_version, target_draw_id),
            ).fetchall()
            tickets = tuple(self._row_to_ticket_record(r) for r in ticket_rows)
        return T539ReplayRecord(
            target_id=f"{strategy_id}:{strategy_version}:{target_draw_id}",
            run_id=run_id,
            strategy_id=_text(strategy_id),
            strategy_version=_text(strategy_version),
            target_draw_id=_text(target_draw_id),
            target_draw_date=_optional_text(target_draw_date),
            cutoff_draw_id=_optional_text(cutoff_draw_id),
            cutoff_draw_date=_optional_text(cutoff_draw_date),
            status=_text(status),
            native_ticket_count=_db_int(native_ticket_count),
            tickets=tickets,
            target_success=_text(status) == "SUCCESS",
        )

    def _row_to_ticket_record(self, row: Sequence[object]) -> T539TicketRecord:
        ticket_position, main_numbers_json, actual_main_numbers_json, hit_numbers_json, hits = row
        predicted = _decode_numbers_json(main_numbers_json)
        actual = _decode_numbers_json(actual_main_numbers_json)
        hit_numbers = _decode_numbers_json(hit_numbers_json)
        hits_int = _db_int(hits)
        tier = DAILY_FIVE39_PRIZE_RULE_CONTRACT.resolve(match_count=hits_int)
        return T539TicketRecord(
            ticket_position=_db_int(ticket_position),
            predicted_numbers=predicted,
            actual_numbers=actual,
            hit_numbers=hit_numbers,
            hits=hits_int,
            is_winner=tier is not None,
            prize_tier=tier.tier_id.value if tier is not None else None,
            prize_tier_order=tier.tier_order if tier is not None else None,
            prize_amount=tier.prize_amount if tier is not None else None,
        )

    def get_metrics(
        self, run_id: str, *, strategy_id: str | None = None
    ) -> T539StrategyMetrics | None:
        with _read_only_connection(self._database) as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM run_metadata WHERE run_id = ?", (run_id,)
                ).fetchone()
                is None
            ):
                return None
            if (
                strategy_id is not None
                and connection.execute(
                    "SELECT 1 FROM strategy_coverage WHERE run_id = ? AND strategy_id = ?",
                    (run_id, strategy_id),
                ).fetchone()
                is None
            ):
                return None

            clauses = ["run_id = ?"]
            params: list[object] = [run_id]
            if strategy_id is not None:
                clauses.append("strategy_id = ?")
                params.append(strategy_id)
            where_sql = " AND ".join(clauses)

            target_count = _scalar(
                connection, f"SELECT COUNT(*) FROM target_completion WHERE {where_sql}", params
            )
            ticket_count = _scalar(
                connection, f"SELECT COUNT(*) FROM prediction_tickets WHERE {where_sql}", params
            )
            hit_rows = connection.execute(
                f"SELECT hits, COUNT(*) FROM prediction_scores WHERE {where_sql} "
                "GROUP BY hits ORDER BY hits",
                params,
            ).fetchall()
            hit_distribution = tuple((_db_int(hits), _db_int(count)) for hits, count in hit_rows)
            winning_ticket_count = sum(
                count for hits, count in hit_distribution if hits in _WINNING_HIT_VALUES
            )
            placeholders = ",".join("?" * len(_WINNING_HIT_VALUES))
            winning_target_count = _scalar(
                connection,
                "SELECT COUNT(DISTINCT strategy_id || ':' || strategy_version || ':' || "
                f"target_draw_id) FROM prediction_scores WHERE {where_sql} "
                f"AND hits IN ({placeholders})",
                (*params, *_WINNING_HIT_VALUES),
            )
            prize_tier_counts = _prize_tier_counts(hit_distribution)
            dates = connection.execute(
                f"SELECT MIN(target_draw_date), MAX(target_draw_date) FROM prediction_tickets "
                f"WHERE {where_sql}",
                params,
            ).fetchone()
        return T539StrategyMetrics(
            run_id=run_id,
            strategy_id=strategy_id,
            target_count=target_count,
            ticket_count=ticket_count,
            winning_ticket_count=winning_ticket_count,
            winning_target_count=winning_target_count,
            hit_distribution=hit_distribution,
            prize_tier_counts=prize_tier_counts,
            first_target_draw_date=_optional_text(dates[0]) if dates is not None else None,
            last_target_draw_date=_optional_text(dates[1]) if dates is not None else None,
        )

    def list_rankings(self, run_id: str) -> T539RankingPage | None:
        with _read_only_connection(self._database) as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM run_metadata WHERE run_id = ?", (run_id,)
                ).fetchone()
                is None
            ):
                return None
            strategy_rows = connection.execute(
                "SELECT strategy_id, strategy_version, native_ticket_count, "
                "successful_target_draw_count FROM strategy_coverage WHERE run_id = ? "
                "ORDER BY strategy_id ASC",
                (run_id,),
            ).fetchall()
            candidates = [self._ranking_candidate(connection, run_id, row) for row in strategy_rows]

        def sort_key(candidate: _RankingCandidate) -> tuple[object, ...]:
            tier_vector = tuple(-count for _, count in candidate.prize_tier_counts)
            return (
                tier_vector,
                -candidate.ticket_winning_rate,
                -candidate.winning_target_count,
                -candidate.eligible_target_count,
                candidate.strategy_id,
            )

        ordered = sorted(candidates, key=sort_key)
        items = tuple(
            T539RankingRecord(
                run_id=run_id,
                rank=index + 1,
                strategy_id=candidate.strategy_id,
                strategy_version=candidate.strategy_version,
                native_ticket_count=candidate.native_ticket_count,
                eligible_target_count=candidate.eligible_target_count,
                winning_target_count=candidate.winning_target_count,
                winning_target_rate=candidate.winning_target_rate,
                total_ticket_count=candidate.total_ticket_count,
                winning_ticket_count=candidate.winning_ticket_count,
                ticket_winning_rate=candidate.ticket_winning_rate,
                prize_tier_counts=candidate.prize_tier_counts,
                highest_prize_tier_achieved=candidate.highest_prize_tier_achieved,
                first_eligible_draw=candidate.first_eligible_draw,
                last_eligible_draw=candidate.last_eligible_draw,
                prize_rule_version=DAILY_FIVE39_PRIZE_RULE_CONTRACT.schema_version,
                prize_rule_provenance=(
                    f"{DAILY_FIVE39_PRIZE_RULE_CONTRACT.source_locator} "
                    f"(sha256={DAILY_FIVE39_PRIZE_RULE_CONTRACT.source_sha256})"
                ),
            )
            for index, candidate in enumerate(ordered)
        )
        return T539RankingPage(run_id=run_id, items=items)

    def _ranking_candidate(
        self, connection: sqlite3.Connection, run_id: str, row: Sequence[object]
    ) -> _RankingCandidate:
        strategy_id, strategy_version, native_ticket_count, eligible_target_count = row
        ticket_count = _scalar(
            connection,
            "SELECT COUNT(*) FROM prediction_tickets "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
            (run_id, strategy_id, strategy_version),
        )
        hit_rows = connection.execute(
            "SELECT hits, COUNT(*) FROM prediction_scores "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ? "
            "GROUP BY hits ORDER BY hits",
            (run_id, strategy_id, strategy_version),
        ).fetchall()
        hit_distribution = tuple((_db_int(hits), _db_int(count)) for hits, count in hit_rows)
        winning_ticket_count = sum(
            count for hits, count in hit_distribution if hits in _WINNING_HIT_VALUES
        )
        placeholders = ",".join("?" * len(_WINNING_HIT_VALUES))
        winning_target_count = _scalar(
            connection,
            "SELECT COUNT(DISTINCT target_draw_id) FROM prediction_scores "
            f"WHERE run_id = ? AND strategy_id = ? AND strategy_version = ? "
            f"AND hits IN ({placeholders})",
            (run_id, strategy_id, strategy_version, *_WINNING_HIT_VALUES),
        )
        prize_tier_counts = _prize_tier_counts(hit_distribution)
        dates = connection.execute(
            "SELECT MIN(target_draw_date), MAX(target_draw_date) FROM prediction_tickets "
            "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?",
            (run_id, strategy_id, strategy_version),
        ).fetchone()
        eligible_target_count_int = _db_int(eligible_target_count)
        winning_target_rate = (
            winning_target_count / eligible_target_count_int if eligible_target_count_int else 0.0
        )
        ticket_winning_rate = winning_ticket_count / ticket_count if ticket_count else 0.0
        tier_counts_by_id = dict(prize_tier_counts)
        highest_tier = next(
            (tier_id for tier_id in _TIER_ORDER_IDS if tier_counts_by_id.get(tier_id, 0) > 0),
            None,
        )
        return _RankingCandidate(
            strategy_id=_text(strategy_id),
            strategy_version=_text(strategy_version),
            native_ticket_count=_db_int(native_ticket_count),
            eligible_target_count=eligible_target_count_int,
            winning_target_count=winning_target_count,
            winning_target_rate=winning_target_rate,
            total_ticket_count=ticket_count,
            winning_ticket_count=winning_ticket_count,
            ticket_winning_rate=ticket_winning_rate,
            prize_tier_counts=prize_tier_counts,
            highest_prize_tier_achieved=highest_tier,
            first_eligible_draw=_optional_text(dates[0]) if dates is not None else None,
            last_eligible_draw=_optional_text(dates[1]) if dates is not None else None,
        )

    def get_coverage_ledger(self, run_id: str) -> T539CoverageLedger | None:
        with _read_only_connection(self._database) as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM run_metadata WHERE run_id = ?", (run_id,)
                ).fetchone()
                is None
            ):
                return None
            rows = connection.execute(
                "SELECT strategy_id, strategy_version, native_ticket_count, min_history "
                "FROM strategy_coverage WHERE run_id = ? ORDER BY strategy_id ASC",
                (run_id,),
            ).fetchall()
        executed = tuple(
            T539CoverageExecutedEntry(
                strategy_id=_text(strategy_id),
                strategy_version=_text(strategy_version),
                native_ticket_count=_db_int(native_ticket_count),
                min_history=_db_int(min_history),
                selection_reason=_selection_reason(_text(strategy_id)),
            )
            for strategy_id, strategy_version, native_ticket_count, min_history in rows
        )
        executed_ids = {entry.strategy_id for entry in executed}
        blocked = tuple(
            entry for entry in _ALL_BLOCKED_STRATEGIES if entry.strategy_id not in executed_ids
        )
        return T539CoverageLedger(
            run_id=run_id,
            executed=executed,
            blocked=blocked,
            coverage_complete=len(blocked) == 0,
        )
