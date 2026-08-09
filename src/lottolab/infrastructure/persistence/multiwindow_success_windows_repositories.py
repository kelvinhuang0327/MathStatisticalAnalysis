"""Read-only adapters for the sealed T539 and P638 R2 replay databases."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lottolab.application.multiwindow_success_windows import (
    MultiWindowSource,
    MultiWindowSuccessResultsUnavailableError,
    StrategySource,
    TargetOutcome,
    source_with_default_null_contract,
)
from lottolab.application.t539_historical import t539_strategy_set_fingerprint
from lottolab.domain.prize_evaluation import (
    evaluate_daily_539_ticket,
    evaluate_power_lotto_ticket,
)

BUSY_TIMEOUT_MS = 5_000

_T539_REQUIRED_TABLES = frozenset(
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
_P638_REQUIRED_TABLES = frozenset(
    {
        "run_metadata",
        "draws",
        "strategy_ledger",
        "strategy_targets",
        "tickets",
        "scores",
        "completion",
        "failures",
    }
)
_P638_ALLOWED_EXCLUDED_STATUSES = frozenset(
    {
        "EXCLUDED_INSUFFICIENT_HISTORY",
        "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE",
    }
)


@contextmanager
def _read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    if not database.exists() or not database.is_file():
        raise MultiWindowSuccessResultsUnavailableError("multi-window replay source is unavailable")
    uri = f"{database.resolve().as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(
            uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1_000, isolation_level=None
        )
    except sqlite3.Error as exc:
        raise MultiWindowSuccessResultsUnavailableError(
            "multi-window replay source cannot be opened read-only"
        ) from exc
    try:
        connection.execute("PRAGMA query_only = ON")
        yield connection
    except sqlite3.Error as exc:
        raise MultiWindowSuccessResultsUnavailableError(
            "multi-window replay source returned an invalid result"
        ) from exc
    finally:
        connection.close()


def _required_schema(connection: sqlite3.Connection, required: frozenset[str]) -> None:
    names = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
    }
    missing = sorted(required - names)
    if missing:
        raise MultiWindowSuccessResultsUnavailableError(
            f"multi-window replay source is missing required tables: {','.join(missing)}"
        )


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise MultiWindowSuccessResultsUnavailableError(f"multi-window source has invalid {label}")
    return value


def _integer(value: object, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise MultiWindowSuccessResultsUnavailableError(f"multi-window source has invalid {label}")
    return value


def _json_list(value: object, label: str) -> tuple[int, ...]:
    raw = _text(value, label)
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MultiWindowSuccessResultsUnavailableError(
            f"multi-window source has malformed {label}"
        ) from exc
    if not isinstance(decoded, list):
        raise MultiWindowSuccessResultsUnavailableError(f"multi-window source has invalid {label}")
    items = cast(list[object], decoded)
    if any(type(item) is not int for item in items):
        raise MultiWindowSuccessResultsUnavailableError(f"multi-window source has invalid {label}")
    return tuple(cast(list[int], items))


def _strategy_set_fingerprint(identities: tuple[str, ...]) -> str:
    canonical = json.dumps(sorted(identities), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class _StrategyMeta:
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    expected_target_count: int
    processed_target_count: int


@dataclass(slots=True)
class _TargetAccumulator:
    target_id: str
    target_date: str
    cutoff_draw_id: str | None
    cutoff_draw_date: str | None
    target_order: int
    cutoff_order: int | None
    native_ticket_count: int
    ticket_positions: list[int]
    winning_ticket_count: int
    tier_counts: dict[tuple[str, int], int]

    @property
    def ticket_count(self) -> int:
        return len(self.ticket_positions)


class SQLiteMultiWindowSuccessSourceReader:
    """Read one exact T539 or P638 replay bundle without opening a write handle."""

    def __init__(self, database: Path, lottery_type: str) -> None:
        if lottery_type not in {"DAILY_539", "POWER_LOTTO"}:
            raise ValueError("multi-window reader lottery_type is unsupported")
        self.database = database
        self.lottery_type = lottery_type

    def load_source(self, run_id: str) -> MultiWindowSource | None:
        if type(run_id) is not str or not run_id:
            raise ValueError("run_id must be a non-empty string")
        try:
            with _read_only_connection(self.database) as connection:
                if self.lottery_type == "DAILY_539":
                    return self._read_t539(connection, run_id)
                return self._read_p638(connection, run_id)
        except MultiWindowSuccessResultsUnavailableError:
            raise
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MultiWindowSuccessResultsUnavailableError(
                "multi-window replay source failed validation"
            ) from exc

    def _read_t539(
        self, connection: sqlite3.Connection, run_id: str
    ) -> MultiWindowSource | None:
        _required_schema(connection, _T539_REQUIRED_TABLES)
        metadata = connection.execute(
            """
            SELECT schema_version, lottery_type, source_sha256, adapter_source_commit,
                   strategy_set_json, status
            FROM run_metadata WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if metadata is None:
            return None
        schema_version = _text(metadata[0], "T539 schema_version")
        lottery_type = _text(metadata[1], "T539 lottery_type")
        source_sha256 = _text(metadata[2], "T539 source_sha256")
        source_commit = _text(metadata[3], "T539 adapter_source_commit")
        strategy_set_json = _text(metadata[4], "T539 strategy_set_json")
        status = _text(metadata[5], "T539 status")
        if lottery_type != "DAILY_539" or status != "COMPLETE":
            raise MultiWindowSuccessResultsUnavailableError("T539 replay run is not complete")

        strategy_metadata = self._read_t539_strategy_metadata(connection, run_id)
        metadata_identities = _decode_strategy_identities(strategy_set_json, "T539")
        actual_identities = tuple(
            _identity(item.strategy_id, item.strategy_version) for item in strategy_metadata
        )
        if sorted(metadata_identities) != sorted(actual_identities):
            raise MultiWindowSuccessResultsUnavailableError(
                "T539 strategy-set identity does not match its coverage ledger"
            )
        failure_count = _count(
            connection,
            "SELECT COUNT(*) FROM failure_ledger WHERE run_id = ?",
            run_id,
        )
        failed_target_count = _count(
            connection,
            "SELECT COUNT(*) FROM target_completion WHERE run_id = ? AND status <> 'SUCCESS'",
            run_id,
        )
        if failure_count != 0 or failed_target_count != 0:
            raise MultiWindowSuccessResultsUnavailableError(
                "T539 replay contains failed normal evidence"
            )
        draw_count = _count(connection, "SELECT COUNT(*) FROM source_draws")
        observations = self._read_t539_observations(connection, run_id, strategy_metadata)
        strategies = tuple(
            StrategySource(
                strategy_id=meta.strategy_id,
                strategy_version=meta.strategy_version,
                native_ticket_count=meta.native_ticket_count,
                min_history=meta.min_history,
                observations=observations[(meta.strategy_id, meta.strategy_version)],
            )
            for meta in strategy_metadata
        )
        return source_with_default_null_contract(
            lottery_type="DAILY_539",
            run_id=run_id,
            schema_version=schema_version,
            source_sha256=source_sha256,
            source_commit=source_commit,
            strategy_set_fingerprint=t539_strategy_set_fingerprint(actual_identities),
            status=status,
            draw_count=draw_count,
            strategies=strategies,
            source_authority=(
                "T539_R2_READ_ONLY_FLAT_REPLAY;official-evaluator-validated;"
                "official-any-prize-target-event"
            ),
        )

    def _read_t539_strategy_metadata(
        self, connection: sqlite3.Connection, run_id: str
    ) -> tuple[_StrategyMeta, ...]:
        rows = connection.execute(
            """
            SELECT strategy_id, strategy_version, native_ticket_count, min_history,
                   expected_target_draw_count, processed_target_draw_count,
                   failed_target_draw_count, status
            FROM strategy_coverage
            WHERE run_id = ?
            ORDER BY strategy_id, strategy_version
            """,
            (run_id,),
        ).fetchall()
        if not rows:
            raise MultiWindowSuccessResultsUnavailableError("T539 replay has no strategy coverage")
        result: list[_StrategyMeta] = []
        for row in rows:
            strategy_id = _text(row[0], "T539 strategy_id")
            strategy_version = _text(row[1], "T539 strategy_version")
            native = _integer(row[2], "T539 native_ticket_count", minimum=1)
            min_history = _integer(row[3], "T539 min_history", minimum=0)
            expected = _integer(row[4], "T539 expected_target_draw_count", minimum=0)
            processed = _integer(row[5], "T539 processed_target_draw_count", minimum=0)
            failed = _integer(row[6], "T539 failed_target_draw_count", minimum=0)
            status = _text(row[7], "T539 strategy status")
            if status != "COMPLETE" or failed != 0 or processed != expected:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 strategy coverage is not complete"
                )
            result.append(
                _StrategyMeta(
                    strategy_id,
                    strategy_version,
                    native,
                    min_history,
                    expected,
                    processed,
                )
            )
        return tuple(result)

    def _read_t539_observations(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        strategy_metadata: tuple[_StrategyMeta, ...],
    ) -> dict[tuple[str, str], tuple[TargetOutcome, ...]]:
        metadata_by_identity = {
            (item.strategy_id, item.strategy_version): item for item in strategy_metadata
        }
        result: dict[tuple[str, str], list[TargetOutcome]] = {
            key: [] for key in metadata_by_identity
        }
        current_identity: tuple[str, str] | None = None
        current_target: _TargetAccumulator | None = None
        last_target_order: dict[tuple[str, str], int] = {}

        def finish_target() -> None:
            nonlocal current_target
            if current_target is None or current_identity is None:
                return
            meta = metadata_by_identity[current_identity]
            positions = sorted(current_target.ticket_positions)
            expected_positions = list(range(1, meta.native_ticket_count + 1))
            if positions != expected_positions:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 complete target does not contain its exact native ticket set"
                )
            if current_target.native_ticket_count != meta.native_ticket_count:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 target native ticket count conflicts with strategy coverage"
                )
            result[current_identity].append(
                TargetOutcome(
                    target_id=current_target.target_id,
                    target_date=current_target.target_date,
                    cutoff_draw_id=current_target.cutoff_draw_id,
                    cutoff_draw_date=current_target.cutoff_draw_date,
                    target_order=current_target.target_order,
                    cutoff_order=current_target.cutoff_order,
                    native_ticket_count=current_target.native_ticket_count,
                    ticket_count=current_target.ticket_count,
                    winning_ticket_count=current_target.winning_ticket_count,
                    tier_counts=tuple(
                        (tier_id, order, count)
                        for (tier_id, order), count in sorted(
                            current_target.tier_counts.items(), key=lambda item: item[0][1]
                        )
                    ),
                )
            )
            current_target = None

        rows = connection.execute(
            """
            SELECT pt.strategy_id, pt.strategy_version, pt.target_draw_id,
                   pt.target_draw_date, pt.cutoff_draw_id, pt.cutoff_draw_date,
                   pt.native_ticket_count, pt.ticket_position, pt.main_numbers_json,
                   pt.hits, pt.execution_status, tc.status, tc.native_ticket_count,
                   sd.draw_order, sd.draw_date, cd.draw_order, cd.draw_date,
                   ps.actual_main_numbers_json, ps.hit_numbers_json, ps.hits
            FROM prediction_tickets pt
            JOIN target_completion tc
              ON tc.run_id = pt.run_id
             AND tc.strategy_id = pt.strategy_id
             AND tc.strategy_version = pt.strategy_version
             AND tc.target_draw_id = pt.target_draw_id
            JOIN prediction_scores ps
              ON ps.run_id = pt.run_id
             AND ps.strategy_id = pt.strategy_id
             AND ps.strategy_version = pt.strategy_version
             AND ps.target_draw_id = pt.target_draw_id
             AND ps.ticket_position = pt.ticket_position
            JOIN source_draws sd ON sd.draw_id = pt.target_draw_id
            LEFT JOIN source_draws cd ON cd.draw_id = pt.cutoff_draw_id
            WHERE pt.run_id = ? AND tc.status = 'SUCCESS'
            ORDER BY pt.strategy_id, pt.strategy_version, sd.draw_order, pt.ticket_position
            """,
            (run_id,),
        )
        for row in rows:
            identity = (_text(row[0], "T539 strategy_id"), _text(row[1], "T539 strategy_version"))
            if identity not in metadata_by_identity:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 replay row references an unknown strategy"
                )
            target_id = _text(row[2], "T539 target_draw_id")
            target_order = _integer(row[13], "T539 target draw order", minimum=0)
            cutoff_order = (
                None
                if row[15] is None
                else _integer(row[15], "T539 cutoff order", minimum=0)
            )
            if cutoff_order is not None and cutoff_order >= target_order:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 replay violates causal cutoff ordering"
                )
            if (
                current_identity != identity
                or current_target is None
                or current_target.target_id != target_id
            ):
                finish_target()
                previous_order = last_target_order.get(identity)
                if previous_order is not None and target_order <= previous_order:
                    raise MultiWindowSuccessResultsUnavailableError(
                        "T539 replay targets are not strictly chronological"
                    )
                last_target_order[identity] = target_order
                current_identity = identity
                current_target = _TargetAccumulator(
                    target_id=target_id,
                    target_date=_text(row[14], "T539 target date"),
                    cutoff_draw_id=None if row[4] is None else _text(row[4], "T539 cutoff draw id"),
                    cutoff_draw_date=(
                        None if row[5] is None else _text(row[5], "T539 cutoff draw date")
                    ),
                    target_order=target_order,
                    cutoff_order=cutoff_order,
                    native_ticket_count=_integer(
                        row[12], "T539 target native ticket count", minimum=1
                    ),
                    ticket_positions=[],
                    winning_ticket_count=0,
                    tier_counts={},
                )
            assert current_target is not None
            if _text(row[10], "T539 ticket execution status") != "SUCCESS" or _text(
                row[11], "T539 target status"
            ) != "SUCCESS":
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 normal evidence is not successful"
                )
            position = _integer(row[7], "T539 ticket position", minimum=1)
            if position in current_target.ticket_positions:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 replay has duplicate ticket positions"
                )
            expected_hits = _integer(row[19], "T539 persisted hit count", minimum=0)
            if row[9] is not None and _integer(
                row[9], "T539 ticket hit count", minimum=0
            ) != expected_hits:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 ticket score columns disagree"
                )
            hit_numbers = _json_list(row[18], "T539 hit_numbers_json")
            if len(hit_numbers) != expected_hits:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 hit-number count disagrees with score"
                )
            predicted = _json_list(row[8], "T539 main_numbers_json")
            actual = _json_list(row[17], "T539 actual_main_numbers_json")
            evaluation = evaluate_daily_539_ticket(
                predicted_main_numbers=predicted,
                winning_main_numbers=actual,
            )
            if evaluation.zone1_hits != expected_hits:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 persisted score disagrees with the official evaluator"
                )
            if evaluation.prize_tier is not None:
                key = (evaluation.prize_tier, evaluation.prize_tier_order or 0)
                current_target.tier_counts[key] = current_target.tier_counts.get(key, 0) + 1
                current_target.winning_ticket_count += 1
            current_target.ticket_positions.append(position)
        finish_target()
        for meta in strategy_metadata:
            key = (meta.strategy_id, meta.strategy_version)
            if len(result[key]) != meta.processed_target_count:
                raise MultiWindowSuccessResultsUnavailableError(
                    "T539 replay target count disagrees with the coverage ledger"
                )
        return {key: tuple(value) for key, value in result.items()}

    def _read_p638(
        self, connection: sqlite3.Connection, run_id: str
    ) -> MultiWindowSource | None:
        _required_schema(connection, _P638_REQUIRED_TABLES)
        metadata = connection.execute(
            """
            SELECT lottery_type, runner_version, source_sha256, source_count,
                   source_commit, status
            FROM run_metadata WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if metadata is None:
            return None
        lottery_type = _text(metadata[0], "P638 lottery_type")
        schema_version = _text(metadata[1], "P638 runner_version")
        source_sha256 = _text(metadata[2], "P638 source_sha256")
        source_count = _integer(metadata[3], "P638 source_count", minimum=0)
        source_commit = _text(metadata[4], "P638 source_commit")
        status = _text(metadata[5], "P638 status")
        if lottery_type != "POWER_LOTTO" or status != "COMPLETE":
            raise MultiWindowSuccessResultsUnavailableError("P638 replay run is not complete")
        strategies = self._read_p638_strategy_metadata(connection, run_id)
        completion = connection.execute(
            """
            SELECT total_source_targets, selected_strategies, eligible_attempts,
                   complete_targets, excluded_targets, failed_targets, ticket_rows, status
            FROM completion WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if completion is None or _text(completion[7], "P638 completion status") != "COMPLETE":
            raise MultiWindowSuccessResultsUnavailableError("P638 replay completion is not sealed")
        if _integer(completion[1], "P638 selected strategy count", minimum=0) != len(strategies):
            raise MultiWindowSuccessResultsUnavailableError(
                "P638 completion strategy count disagrees"
            )
        failed_count = _integer(completion[5], "P638 failed target count", minimum=0)
        failure_statuses = {
            _text(row[0], "P638 failure status")
            for row in connection.execute(
                "SELECT DISTINCT status FROM failures WHERE run_id = ?", (run_id,)
            ).fetchall()
        }
        target_statuses = {
            _text(row[0], "P638 target status")
            for row in connection.execute(
                "SELECT DISTINCT status FROM strategy_targets WHERE run_id = ?", (run_id,)
            ).fetchall()
        }
        allowed_statuses = {"COMPLETE", *_P638_ALLOWED_EXCLUDED_STATUSES}
        if (
            failed_count != 0
            or not failure_statuses.issubset(_P638_ALLOWED_EXCLUDED_STATUSES)
            or not target_statuses.issubset(allowed_statuses)
        ):
            raise MultiWindowSuccessResultsUnavailableError(
                "P638 replay contains failed normal evidence"
            )
        draws, draw_count = self._read_p638_draws(connection, run_id)
        if source_count != draw_count:
            raise MultiWindowSuccessResultsUnavailableError(
                "P638 source count disagrees with draw authority"
            )
        observations = self._read_p638_observations(connection, run_id, strategies, draws)
        complete_count = _count(
            connection,
            "SELECT COUNT(*) FROM strategy_targets WHERE run_id = ? AND status = 'COMPLETE'",
            run_id,
        )
        excluded_count = _count(
            connection,
            "SELECT COUNT(*) FROM strategy_targets WHERE run_id = ? AND status <> 'COMPLETE'",
            run_id,
        )
        ticket_count = _count(connection, "SELECT COUNT(*) FROM tickets WHERE run_id = ?", run_id)
        if (
            complete_count != _integer(completion[3], "P638 complete target count", minimum=0)
            or excluded_count != _integer(completion[4], "P638 excluded target count", minimum=0)
            or ticket_count != _integer(completion[6], "P638 ticket row count", minimum=0)
        ):
            raise MultiWindowSuccessResultsUnavailableError(
                "P638 completion counts disagree with replay tables"
            )
        source_strategies = tuple(
            StrategySource(
                strategy_id=meta.strategy_id,
                strategy_version=meta.strategy_version,
                native_ticket_count=meta.native_ticket_count,
                min_history=meta.min_history,
                observations=observations[(meta.strategy_id, meta.strategy_version)],
            )
            for meta in strategies
        )
        identities = tuple(
            _identity(item.strategy_id, item.strategy_version) for item in strategies
        )
        return source_with_default_null_contract(
            lottery_type="POWER_LOTTO",
            run_id=run_id,
            schema_version=schema_version,
            source_sha256=source_sha256,
            source_commit=source_commit,
            strategy_set_fingerprint=_strategy_set_fingerprint(identities),
            status=status,
            draw_count=draw_count,
            strategies=source_strategies,
            source_authority=(
                "P638_R2_READ_ONLY_FLAT_REPLAY;official-evaluator-validated;"
                "official-any-prize-target-event"
            ),
        )

    def _read_p638_strategy_metadata(
        self, connection: sqlite3.Connection, run_id: str
    ) -> tuple[_StrategyMeta, ...]:
        rows = connection.execute(
            """
            SELECT strategy_id, strategy_version, native_ticket_count, min_history,
                   selected, blocked_reason
            FROM strategy_ledger
            WHERE run_id = ?
            ORDER BY strategy_id, strategy_version
            """,
            (run_id,),
        ).fetchall()
        result: list[_StrategyMeta] = []
        for row in rows:
            selected = _integer(row[4], "P638 selected flag", minimum=0)
            if selected != 1:
                continue
            if row[5] is not None:
                raise MultiWindowSuccessResultsUnavailableError("P638 selected strategy is blocked")
            result.append(
                _StrategyMeta(
                    strategy_id=_text(row[0], "P638 strategy_id"),
                    strategy_version=_text(row[1], "P638 strategy_version"),
                    native_ticket_count=_integer(row[2], "P638 native_ticket_count", minimum=1),
                    min_history=_integer(row[3], "P638 min_history", minimum=0),
                    expected_target_count=0,
                    processed_target_count=0,
                )
            )
        if not result:
            raise MultiWindowSuccessResultsUnavailableError(
                "P638 replay has no selected strategies"
            )
        return tuple(result)

    def _read_p638_draws(
        self, connection: sqlite3.Connection, run_id: str
    ) -> tuple[dict[str, tuple[str, int, tuple[int, ...], int]], int]:
        rows = connection.execute(
            """
            SELECT draw_number, draw_date, main_numbers_json, second_number
            FROM draws WHERE run_id = ?
            ORDER BY draw_date, CAST(draw_number AS INTEGER)
            """,
            (run_id,),
        ).fetchall()
        draws: dict[str, tuple[str, int, tuple[int, ...], int]] = {}
        for order, row in enumerate(rows):
            draw_number = _text(row[0], "P638 draw_number")
            if draw_number in draws:
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 draw authority has duplicate draws"
                )
            main_numbers = _json_list(row[2], "P638 draw main_numbers_json")
            special = _integer(row[3], "P638 draw second_number", minimum=1)
            draws[draw_number] = (_text(row[1], "P638 draw_date"), order, main_numbers, special)
        if not draws:
            raise MultiWindowSuccessResultsUnavailableError("P638 replay has no draws")
        return draws, len(draws)

    def _read_p638_observations(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        strategy_metadata: tuple[_StrategyMeta, ...],
        draws: dict[str, tuple[str, int, tuple[int, ...], int]],
    ) -> dict[tuple[str, str], tuple[TargetOutcome, ...]]:
        metadata_by_identity = {
            (item.strategy_id, item.strategy_version): item for item in strategy_metadata
        }
        result: dict[tuple[str, str], list[TargetOutcome]] = {
            key: [] for key in metadata_by_identity
        }
        current_identity: tuple[str, str] | None = None
        current_target: _TargetAccumulator | None = None
        last_target_order: dict[tuple[str, str], int] = {}

        def finish_target() -> None:
            nonlocal current_target
            if current_target is None or current_identity is None:
                return
            meta = metadata_by_identity[current_identity]
            positions = sorted(current_target.ticket_positions)
            expected_positions = list(range(1, meta.native_ticket_count + 1))
            if positions != expected_positions:
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 complete target does not contain its exact native ticket set"
                )
            if current_target.native_ticket_count != meta.native_ticket_count:
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 target native ticket count conflicts with strategy ledger"
                )
            result[current_identity].append(
                TargetOutcome(
                    target_id=current_target.target_id,
                    target_date=current_target.target_date,
                    cutoff_draw_id=current_target.cutoff_draw_id,
                    cutoff_draw_date=current_target.cutoff_draw_date,
                    target_order=current_target.target_order,
                    cutoff_order=current_target.cutoff_order,
                    native_ticket_count=current_target.native_ticket_count,
                    ticket_count=current_target.ticket_count,
                    winning_ticket_count=current_target.winning_ticket_count,
                    tier_counts=tuple(
                        (tier_id, order, count)
                        for (tier_id, order), count in sorted(
                            current_target.tier_counts.items(), key=lambda item: item[0][1]
                        )
                    ),
                )
            )
            current_target = None

        rows = connection.execute(
            """
            SELECT st.strategy_id, st.strategy_version, st.target_draw_number,
                   st.cutoff_draw_number, st.cutoff_index, st.expected_ticket_count,
                   st.status, d.draw_date, d.main_numbers_json, d.second_number,
                   t.ticket_position, t.predicted_main_numbers_json,
                   t.predicted_second_number, t.native_ticket_count, t.status,
                   s.zone1_hits, s.zone2_hit
            FROM strategy_targets st
            JOIN tickets t
              ON t.run_id = st.run_id
             AND t.strategy_id = st.strategy_id
             AND t.strategy_version = st.strategy_version
             AND t.target_draw_number = st.target_draw_number
            JOIN scores s
              ON s.run_id = t.run_id
             AND s.strategy_id = t.strategy_id
             AND s.strategy_version = t.strategy_version
             AND s.target_draw_number = t.target_draw_number
             AND s.ticket_position = t.ticket_position
            JOIN draws d ON d.run_id = st.run_id AND d.draw_number = st.target_draw_number
            WHERE st.run_id = ? AND st.status = 'COMPLETE'
            ORDER BY st.strategy_id, st.strategy_version, d.draw_date,
                     CAST(st.target_draw_number AS INTEGER), t.ticket_position
            """,
            (run_id,),
        )
        for row in rows:
            identity = (_text(row[0], "P638 strategy_id"), _text(row[1], "P638 strategy_version"))
            if identity not in metadata_by_identity:
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 replay row references an unknown strategy"
                )
            target_id = _text(row[2], "P638 target_draw_number")
            actual_draw = draws.get(target_id)
            if actual_draw is None:
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 target has no draw authority row"
                )
            target_date, target_order, actual_main, actual_special = actual_draw
            cutoff_id = None if row[3] is None else _text(row[3], "P638 cutoff_draw_number")
            cutoff_order = None
            if cutoff_id is not None:
                cutoff = draws.get(cutoff_id)
                if cutoff is None:
                    raise MultiWindowSuccessResultsUnavailableError(
                        "P638 cutoff has no draw authority row"
                    )
                cutoff_order = cutoff[1]
                if cutoff_order >= target_order:
                    raise MultiWindowSuccessResultsUnavailableError(
                        "P638 replay violates causal cutoff ordering"
                    )
            if (
                current_identity != identity
                or current_target is None
                or current_target.target_id != target_id
            ):
                finish_target()
                previous_order = last_target_order.get(identity)
                if previous_order is not None and target_order <= previous_order:
                    raise MultiWindowSuccessResultsUnavailableError(
                        "P638 replay targets are not strictly chronological"
                    )
                last_target_order[identity] = target_order
                current_identity = identity
                current_target = _TargetAccumulator(
                    target_id=target_id,
                    target_date=target_date,
                    cutoff_draw_id=cutoff_id,
                    cutoff_draw_date=(None if cutoff_id is None else draws[cutoff_id][0]),
                    target_order=target_order,
                    cutoff_order=cutoff_order,
                    native_ticket_count=_integer(row[5], "P638 expected ticket count", minimum=1),
                    ticket_positions=[],
                    winning_ticket_count=0,
                    tier_counts={},
                )
            assert current_target is not None
            if _text(row[6], "P638 target status") != "COMPLETE" or _text(
                row[14], "P638 ticket status"
            ) != "COMPLETE":
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 normal evidence is not complete"
                )
            ticket_native = _integer(row[13], "P638 ticket native_ticket_count", minimum=1)
            if ticket_native != current_target.native_ticket_count:
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 ticket native count disagrees with target"
                )
            position = _integer(row[10], "P638 ticket position", minimum=1)
            if position in current_target.ticket_positions:
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 replay has duplicate ticket positions"
                )
            predicted_main = _json_list(row[11], "P638 predicted_main_numbers_json")
            predicted_special = _integer(row[12], "P638 predicted_second_number", minimum=1)
            persisted_zone1 = _integer(row[15], "P638 persisted zone1_hits", minimum=0)
            persisted_zone2 = _integer(row[16], "P638 persisted zone2_hit", minimum=0)
            evaluation = evaluate_power_lotto_ticket(
                predicted_main_numbers=predicted_main,
                predicted_special_number=predicted_special,
                winning_main_numbers=actual_main,
                winning_special_number=actual_special,
            )
            if (
                evaluation.zone1_hits != persisted_zone1
                or int(evaluation.zone2_hit) != persisted_zone2
            ):
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 persisted score disagrees with the official evaluator"
                )
            if evaluation.prize_tier is not None:
                key = (evaluation.prize_tier, evaluation.prize_tier_order or 0)
                current_target.tier_counts[key] = current_target.tier_counts.get(key, 0) + 1
                current_target.winning_ticket_count += 1
            current_target.ticket_positions.append(position)
        finish_target()
        complete_counts = {
            (str(row[0]), str(row[1])): int(row[2])
            for row in connection.execute(
                """
                SELECT strategy_id, strategy_version, COUNT(*)
                FROM strategy_targets
                WHERE run_id = ? AND status = 'COMPLETE'
                GROUP BY strategy_id, strategy_version
                """,
                (run_id,),
            ).fetchall()
        }
        for key in metadata_by_identity:
            if len(result[key]) != complete_counts.get(key, 0):
                raise MultiWindowSuccessResultsUnavailableError(
                    "P638 replay target count disagrees with strategy targets"
                )
        return {key: tuple(value) for key, value in result.items()}


def _decode_strategy_identities(value: str, label: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise MultiWindowSuccessResultsUnavailableError(
            f"{label} strategy-set JSON is malformed"
        ) from exc
    if not isinstance(decoded, list):
        raise MultiWindowSuccessResultsUnavailableError(f"{label} strategy-set JSON is not a list")
    identities: list[str] = []
    items = cast(list[object], decoded)
    for raw_item in items:
        if not isinstance(raw_item, Mapping):
            raise MultiWindowSuccessResultsUnavailableError(f"{label} strategy identity is invalid")
        item = cast(Mapping[str, object], raw_item)
        strategy_id = item.get("strategy_id")
        strategy_version = item.get("strategy_version")
        if not isinstance(strategy_id, str) or not isinstance(strategy_version, str):
            raise MultiWindowSuccessResultsUnavailableError(f"{label} strategy identity is invalid")
        identities.append(_identity(strategy_id, strategy_version))
    return tuple(identities)


def _identity(strategy_id: str, strategy_version: str) -> str:
    return f"{strategy_id}@{strategy_version}"


def _count(connection: sqlite3.Connection, query: str, *parameters: object) -> int:
    row = connection.execute(query, parameters).fetchone()
    if row is None:
        raise MultiWindowSuccessResultsUnavailableError("multi-window source count is missing")
    return _integer(row[0], "multi-window source count", minimum=0)


__all__ = ["SQLiteMultiWindowSuccessSourceReader"]
