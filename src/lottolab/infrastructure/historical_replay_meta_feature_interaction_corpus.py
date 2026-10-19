"""Read-only adapter for the R2 discovery-bounded historical replay corpus."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lottolab.infrastructure.persistence.research_repository import (
    HistoricalReplayDiscoveryCorpusRows,
    fetch_historical_replay_discovery_corpus_rows,
    fetch_research_table_names,
)
from lottolab.research.historical_replay_meta_feature_interaction_discovery import (
    R1_DISCOVERY_PARTITION,
    CorpusDraw,
    CorpusProfile,
    DiscoveryPartition,
    DrawIdentity,
    HistoricalReplayDiscoveryCorpus,
    InteractionDiscoveryError,
    RunInventory,
    StrategyPrediction,
    StrategyTargetObservation,
    TicketPrediction,
)


class HistoricalReplayDiscoveryCorpusStorageError(InteractionDiscoveryError):
    """The read-only store does not satisfy the bounded R2 corpus contract."""


@dataclass(frozen=True, slots=True)
class LoadedHistoricalReplayDiscoveryCorpus:
    corpus: HistoricalReplayDiscoveryCorpus
    database_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HistoricalReplayDiscoveryCorpusStorageError(message)


def _text(value: object, name: str) -> str:
    _require(type(value) is str and bool(value), f"{name} must be non-empty text")
    assert isinstance(value, str)
    return value


def _integer(value: object, name: str) -> int:
    _require(type(value) is int, f"{name} must be an integer")
    assert isinstance(value, int)
    return value


def _decode_numbers(value: object, name: str) -> tuple[int, ...]:
    raw = _text(value, name)
    try:
        decoded = cast(object, json.loads(raw))
    except json.JSONDecodeError as exc:
        raise HistoricalReplayDiscoveryCorpusStorageError(f"{name} is invalid JSON") from exc
    _require(
        isinstance(decoded, list)
        and all(type(item) is int for item in cast("list[object]", decoded)),
        f"{name} must decode to an integer array",
    )
    return tuple(cast("list[int]", decoded))


def _open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("BEGIN")
    return connection


_REQUIRED_TABLES = {
    "research_draw_bindings",
    "research_prediction_targets",
    "research_prediction_tickets",
    "research_runs",
    "research_run_status_events",
    "research_strategy_snapshots",
    "research_ticket_results",
}


def _run_inventory(rows: HistoricalReplayDiscoveryCorpusRows) -> tuple[RunInventory, ...]:
    result: list[RunInventory] = []
    for row in rows.run_inventory_rows:
        run_id = _text(row[0], "run_id")
        _require(row[2] is not None, f"run {run_id!r} has no status event")
        result.append(
            RunInventory(
                run_id=run_id,
                run_kind=_text(row[1], "run_kind"),
                latest_status=_text(row[2], "latest run status"),
                strategy_count=_integer(row[3], "strategy_count"),
                target_row_count=_integer(row[4], "target_row_count"),
                distinct_target_count=_integer(row[5], "distinct_target_count"),
            )
        )
    return tuple(result)


def _source_metadata(
    rows: HistoricalReplayDiscoveryCorpusRows,
) -> tuple[str, str, str, str]:
    row = rows.source_metadata
    _require(row is not None, "source run does not exist")
    assert row is not None
    return (
        _text(row[0], "run_kind"),
        _text(row[1], "input_dataset_identity"),
        _text(row[2], "input_dataset_sha256"),
        _text(row[3], "rule_contract_id"),
    )


def _strategy_rows(
    rows: HistoricalReplayDiscoveryCorpusRows,
) -> tuple[tuple[str, str], ...]:
    result = tuple(
        (_text(row[0], "strategy_id"), _text(row[1], "strategy_version"))
        for row in rows.strategy_rows
    )
    _require(bool(result), "source run has no strategies")
    _require(
        len({item[0] for item in result}) == len(result),
        "R2 requires one exact snapshot per strategy_id",
    )
    return result


def _profile(
    rows: HistoricalReplayDiscoveryCorpusRows,
    *,
    strategy_count: int,
    common_draw_count: int,
    run_inventory: tuple[RunInventory, ...],
) -> CorpusProfile:
    counts = rows.bounded_profile_counts
    _require(len(counts) == 9, "bounded profile count shape is invalid")
    bounded_target_count = _integer(counts[0], "bounded_target_row_count")
    bounded_ticket_count = _integer(counts[1], "bounded_ticket_row_count")
    bounded_result_count = _integer(counts[2], "bounded_result_row_count")
    duplicate_position_count = _integer(counts[3], "duplicate_native_ticket_position_count")
    result_extra_count = _integer(counts[4], "result_version_extra_count")
    required_null_count = _integer(counts[5], "required_null_count")
    invalid_json_count = _integer(counts[6], "invalid_json_count")
    hit_mismatch_count = _integer(counts[7], "recomputed_hit_mismatch_count")
    causal_violation_count = _integer(counts[8], "causal_date_violation_count")
    return CorpusProfile(
        bounded_target_row_count=bounded_target_count,
        bounded_ticket_row_count=bounded_ticket_count,
        bounded_result_row_count=bounded_result_count,
        common_draw_count=common_draw_count,
        rows_excluded_outside_common_intersection=(
            bounded_target_count - common_draw_count * strategy_count
        ),
        duplicate_native_ticket_position_count=duplicate_position_count,
        result_version_extra_count=result_extra_count,
        required_null_count=required_null_count,
        invalid_json_count=invalid_json_count,
        recomputed_hit_mismatch_count=hit_mismatch_count,
        causal_date_violation_count=causal_violation_count,
        run_inventory=run_inventory,
    )


def _build_draws(
    rows: tuple[dict[str, object], ...], strategy_rows: tuple[tuple[str, str], ...]
) -> tuple[CorpusDraw, ...]:
    by_draw: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = (
            _text(row["target_draw_date"], "target_draw_date"),
            int(_text(row["target_draw_number"], "target_draw_number")),
        )
        by_draw[key].append(row)

    expected_strategies = tuple(item[0] for item in strategy_rows)
    version_by_strategy = dict(strategy_rows)
    draws: list[CorpusDraw] = []
    for key in sorted(by_draw):
        draw_rows = by_draw[key]
        by_strategy: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in draw_rows:
            by_strategy[_text(row["strategy_id"], "strategy_id")].append(row)
        _require(
            tuple(sorted(by_strategy)) == expected_strategies,
            "common target strategy intersection is malformed",
        )

        first_row = draw_rows[0]
        target = DrawIdentity(
            draw_date=key[0],
            draw_number=key[1],
            draw_sha256=_text(first_row["target_draw_sha256"], "target_draw_sha256"),
        )
        cutoff = DrawIdentity(
            draw_date=_text(first_row["history_cutoff_draw_date"], "cutoff date"),
            draw_number=int(
                _text(first_row["history_cutoff_draw_number"], "cutoff draw number")
            ),
            draw_sha256=_text(first_row["cutoff_draw_sha256"], "cutoff_draw_sha256"),
        )
        winning_numbers = _decode_numbers(
            first_row["winning_main_numbers_json"], "winning_main_numbers_json"
        )
        strategy_observations: list[StrategyTargetObservation] = []
        for strategy_id in expected_strategies:
            strategy_ticket_rows = by_strategy[strategy_id]
            target_ids = {_text(row["target_id"], "target_id") for row in strategy_ticket_rows}
            _require(len(target_ids) == 1, "strategy target identity is duplicated")
            versions = {
                _integer(row["result_version"], "result_version")
                for row in strategy_ticket_rows
            }
            _require(versions == {1}, "R2 requires exactly result_version 1")
            native_counts = {
                _integer(row["native_ticket_count"], "native_ticket_count")
                for row in strategy_ticket_rows
            }
            _require(len(native_counts) == 1, "native ticket count changed within target")
            native_count = next(iter(native_counts))
            _require(
                len(strategy_ticket_rows) == native_count,
                "ticket/result row count contradicts native_ticket_count",
            )
            _require(
                all(
                    _text(row["target_draw_sha256"], "target_draw_sha256")
                    == target.draw_sha256
                    and _text(row["history_cutoff_draw_date"], "cutoff date")
                    == cutoff.draw_date
                    and int(_text(row["history_cutoff_draw_number"], "cutoff draw number"))
                    == cutoff.draw_number
                    and _text(row["cutoff_draw_sha256"], "cutoff_draw_sha256")
                    == cutoff.draw_sha256
                    and _decode_numbers(
                        row["winning_main_numbers_json"], "winning_main_numbers_json"
                    )
                    == winning_numbers
                    for row in strategy_ticket_rows
                ),
                "target/cutoff binding differs across the common cohort",
            )

            tickets: list[TicketPrediction] = []
            first_ticket_hit_count = -1
            for row in strategy_ticket_rows:
                position = _integer(row["native_position"], "native_position")
                numbers = _decode_numbers(
                    row["ticket_main_numbers_json"], "ticket_main_numbers_json"
                )
                hit_count = _integer(row["main_hit_count"], "main_hit_count")
                _require(
                    hit_count == len(set(numbers) & set(winning_numbers)),
                    "stored main_hit_count does not recompute",
                )
                tickets.append(
                    TicketPrediction(
                        native_position=position,
                        main_numbers=numbers,
                        ticket_sha256=_text(row["ticket_sha256"], "ticket_sha256"),
                    )
                )
                if position == 1:
                    first_ticket_hit_count = hit_count
            tickets.sort(key=lambda item: item.native_position)
            _require(first_ticket_hit_count >= 0, "canonical first ticket is missing")
            version = _text(strategy_ticket_rows[0]["strategy_version"], "strategy_version")
            _require(
                version == version_by_strategy[strategy_id],
                "strategy version changed inside source run",
            )
            strategy_observations.append(
                StrategyTargetObservation(
                    prediction=StrategyPrediction(
                        strategy_id=strategy_id,
                        strategy_version=version,
                        tickets=tuple(tickets),
                    ),
                    first_ticket_main_hit_count=first_ticket_hit_count,
                )
            )
        draws.append(
            CorpusDraw(
                target=target,
                cutoff=cutoff,
                winning_main_numbers=winning_numbers,
                strategies=tuple(strategy_observations),
            )
        )
    return tuple(draws)


def load_historical_replay_discovery_corpus(
    database_path: Path,
    *,
    expected_database_sha256: str,
    source_run_id: str,
    partition: DiscoveryPartition = R1_DISCOVERY_PARTITION,
) -> LoadedHistoricalReplayDiscoveryCorpus:
    """Load exactly the warmup plus R1 discovery rows without any database write."""

    _require(not database_path.is_symlink(), "database path must not be a symlink")
    path = database_path.resolve(strict=True)
    _require(stat.S_ISREG(path.stat().st_mode), "database path must be a regular file")
    _require(
        len(expected_database_sha256) == 64
        and all(character in "0123456789abcdef" for character in expected_database_sha256),
        "expected_database_sha256 is invalid",
    )
    before_sha256 = sha256_file(path)
    _require(before_sha256 == expected_database_sha256, "database SHA-256 does not match pin")

    connection = _open_read_only(path)
    try:
        table_names = fetch_research_table_names(connection)
        missing_tables = _REQUIRED_TABLES - table_names
        _require(not missing_tables, f"research schema is missing tables: {sorted(missing_tables)}")
        rows = fetch_historical_replay_discovery_corpus_rows(
            connection,
            source_run_id=source_run_id,
            last_target_draw_date=partition.discovery_last_target.draw_date,
            last_target_draw_number=partition.discovery_last_target.draw_number,
        )
        _require(rows.table_names == table_names, "research table inventory changed during read")
        source_run_kind, dataset_identity, dataset_sha256, rule_contract_id = _source_metadata(rows)
        _require(
            rows.source_latest_status is not None,
            f"run {source_run_id!r} has no status event",
        )
        latest_status = _text(rows.source_latest_status, "latest run status")
        _require(source_run_kind == "REFERENCE_BASELINE", "source run kind is not reference")
        _require(latest_status == "COMPLETED", "source run latest status is not COMPLETED")
        strategies_with_versions = _strategy_rows(rows)
        strategy_count = len(strategies_with_versions)
        draws = _build_draws(rows.common_rows, strategies_with_versions)
        inventory = _run_inventory(rows)
        profile = _profile(
            rows,
            strategy_count=strategy_count,
            common_draw_count=len(draws),
            run_inventory=inventory,
        )
        _require(profile.required_null_count == 0, "bounded corpus fields contain nulls")
        _require(profile.invalid_json_count == 0, "bounded ticket or draw JSON is malformed")
        _require(
            profile.recomputed_hit_mismatch_count == 0,
            "bounded stored results disagree with recomputed hits",
        )
        _require(
            profile.causal_date_violation_count == 0,
            "bounded corpus contains causal violations",
        )
        _require(profile.result_version_extra_count == 0, "multiple result versions are present")
        _require(
            len(draws) == partition.source_draw_count,
            "bounded corpus row count does not equal warmup plus discovery",
        )
        _require(
            draws[partition.warmup_count].target == partition.discovery_first_target,
            "bounded corpus discovery first identity changed",
        )
        _require(
            draws[-1].target == partition.discovery_last_target,
            "bounded corpus discovery last identity changed",
        )
        corpus = HistoricalReplayDiscoveryCorpus(
            source_run_id=source_run_id,
            source_run_kind=source_run_kind,
            source_dataset_identity=dataset_identity,
            source_dataset_sha256=dataset_sha256,
            source_rule_contract_id=rule_contract_id,
            latest_run_status=latest_status,
            strategies=tuple(item[0] for item in strategies_with_versions),
            draws=draws,
            profile=profile,
        )
    finally:
        connection.rollback()
        connection.close()

    after_sha256 = sha256_file(path)
    _require(after_sha256 == before_sha256, "database changed during read-only load")
    return LoadedHistoricalReplayDiscoveryCorpus(
        corpus=corpus,
        database_sha256=after_sha256,
    )


__all__ = [
    "HistoricalReplayDiscoveryCorpusStorageError",
    "LoadedHistoricalReplayDiscoveryCorpus",
    "load_historical_replay_discovery_corpus",
    "sha256_file",
]
