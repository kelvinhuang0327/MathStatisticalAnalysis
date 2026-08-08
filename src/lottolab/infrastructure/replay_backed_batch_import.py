"""Read-only materialization of the two exact-mapped legacy replay methods."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast
from urllib.parse import quote

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.application.replay_backed_native_reproduction import (
    SUPPORTED_REPLAY_REGISTRY_IDS,
    TRIPLE_STRIKE_REGISTRY_ID,
    TS3_MARKOV_4BET_REGISTRY_ID,
    CausalMainDraw,
    ReplayBackedNativeReproductionError,
    reproduce_native_tickets,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
    ConstructorRequest,
    ConstructorSuccess,
    construct_strategy_preserving_20_ticket,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    ReplayBatchMappingStatus,
    load_full_strategy_catalog,
)

MATERIALIZATION_SCHEMA_VERSION = "BIG_LOTTO_EXACT_REPLAY_BATCH_MATERIALIZATION_V1"
USER_SEED_NAMESPACE = "p20c-v1-historical-validation"
_REQUIRED_DRAW_COLUMNS = {"draw", "date", "numbers", "special"}
_REQUIRED_REPLAY_COLUMNS = {
    "id",
    "target_draw",
    "target_date",
    "strategy_id",
    "strategy_version",
    "history_cutoff_draw",
    "replay_status",
    "reject_reason",
    "predicted_numbers",
    "actual_numbers",
    "actual_special",
    "replay_run_id",
    "bet_index",
}


class ReplayBatchImportError(ValueError):
    """The pinned legacy database cannot satisfy the exact replay contract."""


@dataclass(frozen=True, slots=True)
class PinnedBigLottoDraw:
    draw_number: str
    draw_date: date
    numbers: tuple[int, int, int, int, int, int]
    special: int


@dataclass(frozen=True, slots=True)
class PinnedBigLottoHistory:
    draws: tuple[PinnedBigLottoDraw, ...]
    database_sha256_before: str
    database_sha256_after: str
    replay_truth_supplemented_draw_count: int


@dataclass(frozen=True, slots=True)
class _Replay:
    row_id: int
    target_draw: str
    target_date: date
    strategy_id: str
    strategy_version: str
    history_cutoff_draw: str
    predicted_numbers: tuple[int, int, int, int, int, int]
    actual_numbers: tuple[int, int, int, int, int, int]
    actual_special: int
    replay_run_id: str
    bet_index: int


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_date(raw: object, context: str) -> date:
    if type(raw) is not str:
        raise ReplayBatchImportError(f"{context}: date is missing")
    normalized = raw.replace("/", "-")
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ReplayBatchImportError(f"{context}: date is invalid") from exc
    return parsed


def _parse_ticket(raw: object, context: str) -> tuple[int, int, int, int, int, int]:
    try:
        value: object = json.loads(cast(str, raw))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ReplayBatchImportError(f"{context}: ticket JSON is invalid") from exc
    if not isinstance(value, list):
        raise ReplayBatchImportError(f"{context}: ticket must contain six integers")
    items = cast(list[object], value)
    if len(items) != 6 or any(type(number) is not int for number in items):
        raise ReplayBatchImportError(f"{context}: ticket must contain six integers")
    numbers = cast(list[int], items)
    ticket = tuple(numbers)
    if (
        ticket != tuple(sorted(ticket))
        or len(set(ticket)) != 6
        or any(not 1 <= number <= 49 for number in ticket)
    ):
        raise ReplayBatchImportError(f"{context}: ticket is not canonical")
    return cast(tuple[int, int, int, int, int, int], ticket)


def _columns(connection: sqlite3.Connection, relation: str) -> set[str]:
    return {
        cast(str, row[1])
        for row in connection.execute(f"PRAGMA table_info({relation})")
    }


def _read_draws(
    connection: sqlite3.Connection,
    replays: tuple[_Replay, ...],
) -> tuple[tuple[PinnedBigLottoDraw, ...], int]:
    if not _columns(
        connection, "draws_big_lotto_canonical_main"
    ) >= _REQUIRED_DRAW_COLUMNS:
        raise ReplayBatchImportError("canonical BIG_LOTTO view schema is incomplete")
    rows = connection.execute(
        "SELECT draw,date,numbers,special "
        "FROM draws_big_lotto_canonical_main ORDER BY date,draw"
    )
    canonical_draws = tuple(
        PinnedBigLottoDraw(
            draw_number=cast(str, row[0]),
            draw_date=_parse_date(row[1], f"draw {row[0]}"),
            numbers=_parse_ticket(row[2], f"draw {row[0]}"),
            special=cast(int, row[3]),
        )
        for row in rows
    )
    if not canonical_draws or len(
        {draw.draw_number for draw in canonical_draws}
    ) != len(canonical_draws):
        raise ReplayBatchImportError("canonical draw history is empty or duplicated")
    by_number = {draw.draw_number: draw for draw in canonical_draws}
    truth_by_target: dict[str, PinnedBigLottoDraw] = {}
    for replay in replays:
        truth = PinnedBigLottoDraw(
            draw_number=replay.target_draw,
            draw_date=replay.target_date,
            numbers=replay.actual_numbers,
            special=replay.actual_special,
        )
        previous = truth_by_target.setdefault(replay.target_draw, truth)
        if previous != truth:
            raise ReplayBatchImportError("replay rows disagree on target truth")
    supplemented = 0
    for target_number, truth in truth_by_target.items():
        if target_number in by_number:
            continue
        matching_raw_rows: list[PinnedBigLottoDraw] = []
        for row in connection.execute(
            "SELECT date,numbers,special FROM draws "
            "WHERE lottery_type='BIG_LOTTO' AND draw=?",
            (target_number,),
        ):
            candidate = PinnedBigLottoDraw(
                draw_number=target_number,
                draw_date=_parse_date(row[0], f"raw draw {target_number}"),
                numbers=_parse_ticket(row[1], f"raw draw {target_number}"),
                special=cast(int, row[2]),
            )
            if candidate == truth:
                matching_raw_rows.append(candidate)
        if len(matching_raw_rows) != 1:
            raise ReplayBatchImportError(
                "canonical omission lacks one exact raw/replay truth match"
            )
        by_number[target_number] = truth
        supplemented += 1
    draws = tuple(
        sorted(by_number.values(), key=lambda draw: (draw.draw_date, draw.draw_number))
    )
    if len({draw.draw_date for draw in draws}) != len(draws):
        raise ReplayBatchImportError("augmented draw history has duplicate dates")
    for draw in draws:
        if (
            type(draw.special) is not int
            or not 1 <= draw.special <= 49
            or draw.special in draw.numbers
        ):
            raise ReplayBatchImportError(
                f"draw {draw.draw_number}: special number is invalid"
            )
    return draws, supplemented


def _read_replays(connection: sqlite3.Connection) -> tuple[_Replay, ...]:
    if not _columns(
        connection, "strategy_prediction_replays"
    ) >= _REQUIRED_REPLAY_COLUMNS:
        raise ReplayBatchImportError("strategy replay table schema is incomplete")
    placeholders = ",".join("?" for _ in SUPPORTED_REPLAY_REGISTRY_IDS)
    query = (
        "SELECT id,target_draw,target_date,strategy_id,strategy_version,"
        "history_cutoff_draw,replay_status,reject_reason,predicted_numbers,"
        "actual_numbers,actual_special,replay_run_id,bet_index "
        "FROM strategy_prediction_replays "
        f"WHERE strategy_id IN ({placeholders}) "
        "ORDER BY target_date,target_draw,strategy_id,bet_index,id"
    )
    output: list[_Replay] = []
    for row in connection.execute(query, SUPPORTED_REPLAY_REGISTRY_IDS):
        context = f"replay row {row[0]}"
        if row[6] != "PREDICTED" or row[7] not in (None, ""):
            raise ReplayBatchImportError(f"{context}: replay is not PREDICTED")
        required_text = (row[1], row[3], row[4], row[5])
        if any(type(value) is not str or not value for value in required_text):
            raise ReplayBatchImportError(f"{context}: replay identity is incomplete")
        if type(row[10]) is not int or type(row[12]) is not int or row[12] <= 0:
            raise ReplayBatchImportError(f"{context}: replay index/outcome is invalid")
        output.append(
            _Replay(
                row_id=cast(int, row[0]),
                target_draw=cast(str, row[1]),
                target_date=_parse_date(row[2], context),
                strategy_id=cast(str, row[3]),
                strategy_version=cast(str, row[4]),
                history_cutoff_draw=cast(str, row[5]),
                predicted_numbers=_parse_ticket(row[8], context),
                actual_numbers=_parse_ticket(row[9], context),
                actual_special=cast(int, row[10]),
                replay_run_id="" if row[11] is None else cast(str, row[11]),
                bet_index=cast(int, row[12]),
            )
        )
    if not output or {row.strategy_id for row in output} != set(
        SUPPORTED_REPLAY_REGISTRY_IDS
    ):
        raise ReplayBatchImportError("both exact-mapped replay strategies are required")
    return tuple(output)


def _readonly_connection(database: Path) -> sqlite3.Connection:
    resolved = database.resolve(strict=True)
    uri = f"file:{quote(str(resolved), safe='/')}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _load_pinned_replay_source(
    *,
    database: Path,
    expected_database_sha256: str,
    require_replay_authority: bool = True,
) -> tuple[PinnedBigLottoHistory, tuple[_Replay, ...]]:
    if database.is_symlink() or not database.is_file():
        raise ReplayBatchImportError("database must be a regular non-symlink file")
    if (
        len(expected_database_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_database_sha256)
    ):
        raise ReplayBatchImportError("expected database SHA-256 is invalid")
    before_sha256 = _file_sha256(database)
    if before_sha256 != expected_database_sha256:
        raise ReplayBatchImportError("database SHA-256 does not match caller pin")

    try:
        with _readonly_connection(database) as connection:
            replays = _read_replays(connection) if require_replay_authority else ()
            draws, supplemented_draw_count = _read_draws(connection, replays)
    except sqlite3.Error as exc:
        raise ReplayBatchImportError("legacy database read failed") from exc
    after_sha256 = _file_sha256(database)
    if after_sha256 != before_sha256:
        raise ReplayBatchImportError("legacy database changed during read")
    return (
        PinnedBigLottoHistory(
            draws=draws,
            database_sha256_before=before_sha256,
            database_sha256_after=after_sha256,
            replay_truth_supplemented_draw_count=supplemented_draw_count,
        ),
        replays,
    )


def load_pinned_biglotto_history(
    *,
    database: Path,
    expected_database_sha256: str,
    require_replay_authority: bool = True,
) -> PinnedBigLottoHistory:
    """Read all validated draws without exposing replay prediction outputs.

    ``require_replay_authority`` defaults to True, preserving the original
    strict gate: the database must carry a valid ``strategy_prediction_replays``
    table for the two exact-mapped replay strategies. ``PinnedBigLottoHistory``
    has no field that can carry replay ticket data, so callers that only ever
    read draw history may pass ``require_replay_authority=False`` to read a
    database that carries no replay table at all (e.g. a draw-history-only
    reconstruction source). ``materialize_exact_replay_batch`` never sets this
    and always requires replay authority.
    """

    history, _replays = _load_pinned_replay_source(
        database=database,
        expected_database_sha256=expected_database_sha256,
        require_replay_authority=require_replay_authority,
    )
    return history


def materialize_exact_replay_batch(
    *,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Build evaluator input without writing to or outcome-feeding the source DB."""

    history, replays = _load_pinned_replay_source(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    draws = history.draws
    before_sha256 = history.database_sha256_before
    after_sha256 = history.database_sha256_after
    supplemented_draw_count = history.replay_truth_supplemented_draw_count

    catalog = load_full_strategy_catalog()
    mapping_by_registry = {
        mapping.registry_strategy_id: mapping
        for mapping in catalog.first_batch_mappings
        if mapping.mapping_status is ReplayBatchMappingStatus.EXACT_SOURCE_SYMBOL_MATCH
    }
    if set(mapping_by_registry) != set(SUPPORTED_REPLAY_REGISTRY_IDS):
        raise ReplayBatchImportError("catalog exact mappings changed")
    draw_by_number = {draw.draw_number: draw for draw in draws}
    draw_index = {draw.draw_number: index for index, draw in enumerate(draws)}
    grouped: dict[tuple[str, str], list[_Replay]] = defaultdict(list)
    for replay in replays:
        grouped[(replay.strategy_id, replay.target_draw)].append(replay)

    executions: list[dict[str, object]] = []
    target_numbers: set[str] = set()
    registry_counts: dict[str, int] = defaultdict(int)
    for (registry_id, target_number), group in sorted(
        grouped.items(),
        key=lambda item: (
            item[1][0].target_date,
            item[0][1],
            item[0][0],
        ),
    ):
        target = draw_by_number.get(target_number)
        cutoff_number = group[0].history_cutoff_draw
        cutoff = draw_by_number.get(cutoff_number)
        if target is None or cutoff is None:
            raise ReplayBatchImportError("replay target or cutoff leaves canonical history")
        target_position = draw_index[target_number]
        cutoff_position = draw_index[cutoff_number]
        if cutoff_position >= target_position or cutoff.draw_date >= target.draw_date:
            raise ReplayBatchImportError("replay history cutoff is not causal")
        for replay in group:
            if (
                replay.target_date != target.draw_date
                or replay.history_cutoff_draw != cutoff_number
                or replay.actual_numbers != target.numbers
                or replay.actual_special != target.special
            ):
                raise ReplayBatchImportError("replay row contradicts canonical draw")

        if registry_id == TRIPLE_STRIKE_REGISTRY_ID:
            unique_replay = tuple(
                dict.fromkeys(replay.predicted_numbers for replay in group)
            )
            replay_tickets = unique_replay
        elif registry_id == TS3_MARKOV_4BET_REGISTRY_ID:
            if [replay.bet_index for replay in group] != [1, 2, 3, 4]:
                raise ReplayBatchImportError(
                    "TS3+Markov must preserve bet_index 1..4 exactly"
                )
            replay_tickets = tuple(replay.predicted_numbers for replay in group)
        else:
            raise ReplayBatchImportError("unexpected replay strategy")
        causal_history = tuple(
            CausalMainDraw(draw.draw_number, draw.numbers)
            for draw in draws[: cutoff_position + 1]
        )
        try:
            native_tickets = reproduce_native_tickets(
                registry_strategy_id=registry_id,
                replay_tickets=replay_tickets,
                causal_history=causal_history,
            )
        except ReplayBackedNativeReproductionError as exc:
            raise ReplayBatchImportError(str(exc)) from exc
        constructed = construct_strategy_preserving_20_ticket(
            ConstructorRequest(
                strategy_id=registry_id,
                draw_id=target_number,
                replicate_id=0,
                raw_tickets=native_tickets,
                historical_cutoff_identity=cutoff_number,
                user_seed=USER_SEED_NAMESPACE,
            )
        )
        if not isinstance(constructed, ConstructorSuccess):
            raise ReplayBatchImportError(
                f"ordered-20 construction failed: {constructed.reason.value}"
            )
        mapping = mapping_by_registry[registry_id]
        if mapping.catalog_strategy_id is None:
            raise ReplayBatchImportError("exact mapping lacks catalog strategy ID")
        record = catalog.get(mapping.catalog_strategy_id)
        executions.append(
            {
                "history_cutoff_draw_date": cutoff.draw_date.isoformat(),
                "history_cutoff_draw_number": cutoff_number,
                "native_ticket_count": len(native_tickets),
                "native_tickets": [list(ticket) for ticket in native_tickets],
                "ordered_portfolio": [
                    list(ticket) for ticket in constructed.tickets
                ],
                "portfolio_derivation": CONSTRUCTOR_IDENTIFIER,
                "portfolio_ticket_count": 20,
                "status": "OK",
                "strategy_id": record.strategy_id,
                "strategy_version": record.strategy_version,
                "target_draw_number": target_number,
            }
        )
        target_numbers.add(target_number)
        registry_counts[registry_id] += 1

    targets = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "winning_main_numbers": list(draw.numbers),
            "winning_special_number": draw.special,
        }
        for draw in draws
        if draw.draw_number in target_numbers
    ]
    return {
        "dataset_id": f"legacy-biglotto-replay-exact2-{before_sha256[:12]}",
        "dataset_sha256": before_sha256,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "database_sha256_before": before_sha256,
            "database_sha256_after": after_sha256,
            "exact_mapping_count": 2,
            "replay_truth_supplemented_draw_count": supplemented_draw_count,
            "registry_execution_counts": dict(sorted(registry_counts.items())),
            "source_read_mode": "sqlite-mode=ro,immutable=1,query_only=ON",
            "user_seed_namespace": USER_SEED_NAMESPACE,
        },
        "targets": targets,
    }


__all__ = [
    "MATERIALIZATION_SCHEMA_VERSION",
    "USER_SEED_NAMESPACE",
    "PinnedBigLottoDraw",
    "PinnedBigLottoHistory",
    "ReplayBatchImportError",
    "load_pinned_biglotto_history",
    "materialize_exact_replay_batch",
]
