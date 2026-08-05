"""Offline, idempotent forwarder from the authoritative P638 R4 stores.

The two source databases are opened through SQLite's read-only URI mode and
are never used as write targets.  Only the caller-provided Historical Results
V2 database is mutated, and one deterministic import identity protects the
forwarding transaction from duplicate reruns.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from lottolab.application.p638_historical import P638_LOTTERY_TYPE, P638ForwardingResult
from lottolab.infrastructure.persistence.historical_schema import (
    initialize_schema,
    open_database,
)

SOURCE_REPLAY_RUN_ID = "p638-wave1-0f2f67c21f7a1921"
SOURCE_REPLAY_DB_SHA256 = "9a697b3384d469f032d0649e8fd05b9a9900beb46e5527b129e3b1a6624d434a"
SOURCE_REPLAY_DB_BYTES = 30_658_560
SOURCE_DRAW_DB_SHA256 = "457a52baba575463c78dbe62f0d5b406101d24b250e26bbcc2d0eba648179af4"
SOURCE_DRAW_DB_BYTES = 1_806_336
SOURCE_COMMIT_OID = "2573900481c376e3229b4d413f60c91cc54a1295"
SOURCE_REPOSITORY = "kelvinhuang0327/MathStatisticalAnalysis"
FORWARDING_CONTRACT_VERSION = "P638_HISTORICAL_RESULTS_V2"
ADAPTER_PATH = "src/lottolab/strategies/adapters/powerlotto_wave1.py"
ZONE1_CONTRACT = "POWER_LOTTO zone-1: exactly six distinct ascending integers in [1..38]"
ZONE2_CONTRACT = (
    "POWER_LOTTO zone-2: one integer in [1..8], p638-powerlotto-second-zone-v1, causal-only"
)


class P638ForwardingError(RuntimeError):
    """The authoritative P638 sources failed reconciliation or forwarding."""


@dataclass(frozen=True, slots=True)
class _SourceDraw:
    draw_number: str
    draw_date: str
    zone1: tuple[int, ...]
    zone2: int
    source_reference: str
    draw_sha256: str


@dataclass(frozen=True, slots=True)
class _ReplayStrategy:
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    source_paths: tuple[str, ...]
    algorithm_family: str
    provenance: str


@dataclass(frozen=True, slots=True)
class _ReplayTarget:
    strategy_id: str
    strategy_version: str
    target_draw_number: str
    cutoff_draw_number: str | None
    cutoff_index: int
    expected_ticket_count: int
    status: str
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class _ReplayTicket:
    strategy_id: str
    strategy_version: str
    target_draw_number: str
    position: int
    predicted_zone1: tuple[int, ...]
    predicted_zone2: int
    status: str
    ssot_version: str
    provenance: str
    zone1_hits: int
    zone2_hit: bool


@dataclass(frozen=True, slots=True)
class _ReplayBundle:
    source_run_id: str
    source_content_sha256: str
    second_zone_ssot_version: str
    second_zone_ssot_provenance: str
    draws: tuple[_SourceDraw, ...]
    strategies: tuple[_ReplayStrategy, ...]
    targets: tuple[_ReplayTarget, ...]
    tickets: tuple[_ReplayTicket, ...]
    completion: dict[str, int | str]


@dataclass(frozen=True, slots=True)
class _DrawAuthority:
    migration_id: str
    source_run_id: str
    draws: tuple[_SourceDraw, ...]


@dataclass(frozen=True, slots=True)
class _RegistryEntry:
    strategy_id: str
    strategy_version: str
    display_label: str
    executable: bool
    adapter_path: str | None
    native_ticket_count: int | None
    min_history: int | None
    source_paths: tuple[str, ...]
    lifecycle_status: str
    replay_status: str
    provenance: str
    exclusion_reason: str | None
    source_strategy: _ReplayStrategy | None


class P638HistoricalForwarder:
    """Forward one exact P638 source pair into an explicit Historical V2 DB."""

    def __init__(
        self,
        *,
        source_replay_db: Path,
        source_draw_db: Path,
        output_db: Path,
        expected_source_replay_sha256: str = SOURCE_REPLAY_DB_SHA256,
        expected_source_replay_bytes: int = SOURCE_REPLAY_DB_BYTES,
        expected_source_draw_sha256: str = SOURCE_DRAW_DB_SHA256,
        expected_source_draw_bytes: int = SOURCE_DRAW_DB_BYTES,
    ) -> None:
        self._source_replay_db = source_replay_db
        self._source_draw_db = source_draw_db
        self._output_db = output_db
        self._expected_source_replay_sha256 = expected_source_replay_sha256
        self._expected_source_replay_bytes = expected_source_replay_bytes
        self._expected_source_draw_sha256 = expected_source_draw_sha256
        self._expected_source_draw_bytes = expected_source_draw_bytes

    def forward(self) -> P638ForwardingResult:
        replay_sha256 = _verify_source_file(
            self._source_replay_db,
            expected_sha256=self._expected_source_replay_sha256,
            expected_bytes=self._expected_source_replay_bytes,
            label="P638 R4 replay source",
        )
        draw_sha256 = _verify_source_file(
            self._source_draw_db,
            expected_sha256=self._expected_source_draw_sha256,
            expected_bytes=self._expected_source_draw_bytes,
            label="P638 draw authority source",
        )
        replay = _load_replay_bundle(self._source_replay_db)
        authority = _load_draw_authority(
            self._source_draw_db,
            expected_replay_sha256=replay_sha256,
            expected_source_run_id=replay.source_run_id,
        )
        _reconcile_draws(replay.draws, authority.draws)
        registry = _current_registry(replay)
        identity_payload = _identity_payload(
            replay=replay,
            authority=authority,
            registry=registry,
            replay_sha256=replay_sha256,
            draw_sha256=draw_sha256,
        )
        import_identity = _sha256_json(identity_payload)
        run_id = f"p638-historical-v2-{import_identity[:16]}"
        manifest_sha256 = _sha256_json(
            {
                "contract_version": FORWARDING_CONTRACT_VERSION,
                "import_identity_sha256": import_identity,
                "source_run_id": replay.source_run_id,
                "source_replay_sha256": replay_sha256,
                "source_draw_db_sha256": draw_sha256,
                "registry": identity_payload["registry"],
            }
        )

        _validate_output_path(self._output_db)
        initialize_schema(self._output_db)
        with open_database(self._output_db) as connection:
            existing = connection.execute(
                """
                SELECT id, status FROM historical_result_run
                WHERE import_identity_sha256 = ?
                """,
                (import_identity,),
            ).fetchone()
            if existing is not None:
                if str(existing[1]) != "COMPLETED":
                    raise P638ForwardingError(
                        "a previous P638 forwarding transaction is present but incomplete"
                    )
                return _result_from_output(
                    connection,
                    run_id=str(existing[0]),
                    source_run_id=replay.source_run_id,
                    source_replay_sha256=replay_sha256,
                    source_draw_db_sha256=draw_sha256,
                    is_idempotent_replay=True,
                )
            if connection.execute(
                "SELECT 1 FROM historical_result_run WHERE id = ?", (run_id,)
            ).fetchone():
                raise P638ForwardingError(
                    "deterministic P638 run identity already belongs to another import"
                )

            connection.execute("BEGIN IMMEDIATE")
            try:
                now = _utc_now()
                connection.execute(
                    """
                    INSERT INTO historical_result_run (
                        id, import_identity_sha256, manifest_sha256, contract_version,
                        source_kind, source_repository, source_commit_oid,
                        source_artifact_sha256, dataset_identity, dataset_sha256,
                        legacy_run_id, lottery_type, status, started_at, completed_at,
                        error_code, error_summary, created_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_PROGRESS', ?, NULL, NULL, NULL, ?
                    )
                    """,
                    (
                        run_id,
                        import_identity,
                        manifest_sha256,
                        FORWARDING_CONTRACT_VERSION,
                        "P638_R4_REPLAY_FORWARD",
                        SOURCE_REPOSITORY,
                        SOURCE_COMMIT_OID,
                        replay_sha256,
                        "P638_SOURCE_DRAW_DB",
                        draw_sha256,
                        replay.source_run_id,
                        P638_LOTTERY_TYPE,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO historical_p638_run (
                        run_id, lottery_type, source_run_id, source_replay_sha256,
                        source_draw_db_sha256, source_content_sha256,
                        second_zone_ssot_version, total_source_targets,
                        selected_strategy_count, draw_count, eligible_attempts,
                        complete_targets, excluded_targets, failed_targets, ticket_rows,
                        provenance_json, created_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        P638_LOTTERY_TYPE,
                        replay.source_run_id,
                        replay_sha256,
                        draw_sha256,
                        replay.source_content_sha256,
                        replay.second_zone_ssot_version,
                        len(replay.targets),
                        len(registry),
                        len(replay.draws),
                        int(replay.completion["eligible_attempts"]),
                        int(replay.completion["complete_targets"]),
                        int(replay.completion["excluded_targets"]),
                        int(replay.completion["failed_targets"]),
                        int(replay.completion["ticket_rows"]),
                        json.dumps(
                            {
                                "source_replay_db": str(self._source_replay_db),
                                "source_draw_db": str(self._source_draw_db),
                                "source_commit": SOURCE_COMMIT_OID,
                                "source_content_sha256": replay.source_content_sha256,
                                "second_zone_ssot_provenance": replay.second_zone_ssot_provenance,
                                "registry": [_registry_dict(entry) for entry in registry],
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        now,
                        now,
                    ),
                )

                snapshot_ids = _insert_registry(
                    connection,
                    run_id=run_id,
                    registry=registry,
                    created_at=now,
                    source_replay_sha256=replay_sha256,
                )
                draw_snapshot_ids = _insert_draws(
                    connection,
                    run_id=run_id,
                    draws=authority.draws,
                    created_at=now,
                )
                _insert_targets_and_tickets(
                    connection,
                    run_id=run_id,
                    replay=replay,
                    authority=authority,
                    registry=registry,
                    snapshot_ids=snapshot_ids,
                    draw_snapshot_ids=draw_snapshot_ids,
                    source_replay_sha256=replay_sha256,
                )
                connection.execute(
                    """
                    UPDATE historical_result_run
                    SET status = 'COMPLETED', completed_at = ?
                    WHERE id = ?
                    """,
                    (now, run_id),
                )
                result = _result_from_output(
                    connection,
                    run_id=run_id,
                    source_run_id=replay.source_run_id,
                    source_replay_sha256=replay_sha256,
                    source_draw_db_sha256=draw_sha256,
                    is_idempotent_replay=False,
                )
                _assert_forwarded_totals(result, replay, registry, authority)
                connection.commit()
                return result
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise


def _load_replay_bundle(path: Path) -> _ReplayBundle:
    with _source_connection(path) as connection:
        metadata = connection.execute(
            "SELECT * FROM run_metadata WHERE run_id = ? AND lottery_type = ?",
            (SOURCE_REPLAY_RUN_ID, P638_LOTTERY_TYPE),
        ).fetchone()
        if metadata is None or str(metadata["status"]) != "COMPLETE":
            raise P638ForwardingError("P638 R4 source run is missing or not COMPLETE")
        source_count = int(metadata["source_count"])
        source_content_sha256 = str(metadata["source_sha256"])
        ssot_version = str(metadata["second_zone_ssot_version"])
        ssot_provenance = str(metadata["second_zone_ssot_provenance"])

        draw_rows = connection.execute(
            """
            SELECT draw_number, draw_date, main_numbers_json, second_number,
                   source_reference
            FROM draws WHERE run_id = ?
            ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
            """,
            (SOURCE_REPLAY_RUN_ID,),
        ).fetchall()
        draws = tuple(
            _SourceDraw(
                draw_number=str(row["draw_number"]),
                draw_date=str(row["draw_date"]),
                zone1=_decode_numbers(row["main_numbers_json"], expected_count=6),
                zone2=_exact_int(row["second_number"], "source second zone"),
                source_reference=str(row["source_reference"]),
                draw_sha256=_sha256_json(
                    {
                        "draw_number": row["draw_number"],
                        "draw_date": row["draw_date"],
                        "zone1": _decode_numbers(row["main_numbers_json"], expected_count=6),
                        "zone2": row["second_number"],
                    }
                ),
            )
            for row in draw_rows
        )
        if len(draws) != source_count or len({draw.draw_number for draw in draws}) != len(draws):
            raise P638ForwardingError("P638 R4 source draw identities do not reconcile")

        strategy_rows = connection.execute(
            """
            SELECT * FROM strategy_ledger
            WHERE run_id = ? AND lottery_type = ? AND selected = 1
            ORDER BY strategy_id ASC, strategy_version ASC
            """,
            (SOURCE_REPLAY_RUN_ID, P638_LOTTERY_TYPE),
        ).fetchall()
        strategies = tuple(
            _ReplayStrategy(
                strategy_id=str(row["strategy_id"]),
                strategy_version=str(row["strategy_version"]),
                native_ticket_count=_exact_int(
                    row["native_ticket_count"], "source native ticket count"
                ),
                min_history=_exact_int(row["min_history"], "source min history"),
                source_paths=tuple(_decode_text_list(row["source_paths_json"])),
                algorithm_family=str(row["algorithm_family"]),
                provenance=str(row["provenance"]),
            )
            for row in strategy_rows
        )
        target_rows = connection.execute(
            """
            SELECT * FROM strategy_targets
            WHERE run_id = ? AND lottery_type = ?
            ORDER BY strategy_id, strategy_version, target_draw_number
            """,
            (SOURCE_REPLAY_RUN_ID, P638_LOTTERY_TYPE),
        ).fetchall()
        targets = tuple(
            _ReplayTarget(
                strategy_id=str(row["strategy_id"]),
                strategy_version=str(row["strategy_version"]),
                target_draw_number=str(row["target_draw_number"]),
                cutoff_draw_number=(
                    None if row["cutoff_draw_number"] is None else str(row["cutoff_draw_number"])
                ),
                cutoff_index=_exact_int(row["cutoff_index"], "source cutoff index"),
                expected_ticket_count=_exact_int(
                    row["expected_ticket_count"], "source expected ticket count"
                ),
                status=str(row["status"]),
                failure_reason=(
                    None if row["failure_reason"] is None else str(row["failure_reason"])
                ),
            )
            for row in target_rows
        )
        if len(
            {
                (target.strategy_id, target.strategy_version, target.target_draw_number)
                for target in targets
            }
        ) != len(targets):
            raise P638ForwardingError("P638 R4 target natural keys are duplicated")

        ticket_rows = connection.execute(
            """
            SELECT * FROM tickets
            WHERE run_id = ? AND lottery_type = ?
            ORDER BY strategy_id, strategy_version, target_draw_number, ticket_position
            """,
            (SOURCE_REPLAY_RUN_ID, P638_LOTTERY_TYPE),
        ).fetchall()
        raw_score_rows = connection.execute(
            """
            SELECT * FROM scores
            WHERE run_id = ? AND lottery_type = ?
            """,
            (SOURCE_REPLAY_RUN_ID, P638_LOTTERY_TYPE),
        ).fetchall()
        score_rows: dict[tuple[str, str, str, int], sqlite3.Row] = {}
        for row in raw_score_rows:
            key = (
                str(row["strategy_id"]),
                str(row["strategy_version"]),
                str(row["target_draw_number"]),
                _exact_int(row["ticket_position"], "source score position"),
            )
            if key in score_rows:
                raise P638ForwardingError("P638 R4 score natural keys are duplicated")
            score_rows[key] = row
        if len(score_rows) != int(
            connection.execute(
                "SELECT COUNT(*) FROM scores WHERE run_id = ?", (SOURCE_REPLAY_RUN_ID,)
            ).fetchone()[0]
        ):
            raise P638ForwardingError("P638 R4 score natural keys are duplicated")
        tickets: list[_ReplayTicket] = []
        for row in ticket_rows:
            key = (
                str(row["strategy_id"]),
                str(row["strategy_version"]),
                str(row["target_draw_number"]),
                _exact_int(row["ticket_position"], "source ticket position"),
            )
            score = score_rows.get(key)
            if score is None:
                raise P638ForwardingError("P638 R4 ticket is missing its score row")
            tickets.append(
                _ReplayTicket(
                    strategy_id=key[0],
                    strategy_version=key[1],
                    target_draw_number=key[2],
                    position=key[3],
                    predicted_zone1=_decode_numbers(
                        row["predicted_main_numbers_json"], expected_count=6
                    ),
                    predicted_zone2=_exact_int(
                        row["predicted_second_number"], "source predicted second zone"
                    ),
                    status=str(row["status"]),
                    ssot_version=str(row["ssot_version"]),
                    provenance=str(row["provenance"]),
                    zone1_hits=_exact_int(score["zone1_hits"], "source zone-1 hits"),
                    zone2_hit=bool(_exact_int(score["zone2_hit"], "source zone-2 hit")),
                )
            )
        completion_row = connection.execute(
            "SELECT * FROM completion WHERE run_id = ?", (SOURCE_REPLAY_RUN_ID,)
        ).fetchone()
        if completion_row is None or str(completion_row["status"]) != "COMPLETE":
            raise P638ForwardingError("P638 R4 completion row is missing or not COMPLETE")
        completion = {
            name: cast(int | str, completion_row[name])
            for name in (
                "total_source_targets",
                "selected_strategies",
                "eligible_attempts",
                "complete_targets",
                "excluded_targets",
                "failed_targets",
                "ticket_rows",
                "status",
            )
        }
    _validate_replay_totals(draws, strategies, targets, tickets, completion)
    return _ReplayBundle(
        source_run_id=SOURCE_REPLAY_RUN_ID,
        source_content_sha256=source_content_sha256,
        second_zone_ssot_version=ssot_version,
        second_zone_ssot_provenance=ssot_provenance,
        draws=draws,
        strategies=strategies,
        targets=targets,
        tickets=tuple(tickets),
        completion=completion,
    )


def _load_draw_authority(
    path: Path, *, expected_replay_sha256: str, expected_source_run_id: str
) -> _DrawAuthority:
    with _source_connection(path) as connection:
        migration = connection.execute(
            "SELECT * FROM migration_run WHERE migration_id = ?",
            ("P638_OLD_DB_DRAW_MIGRATION_R1",),
        ).fetchone()
        if migration is None:
            raise P638ForwardingError("P638 draw authority migration row is missing")
        required = {
            "source_run_id": expected_source_run_id,
            "source_sha256": expected_replay_sha256,
            "status": "COMPLETED",
            "expected_draw_count": 1933,
            "inserted_draw_count": 1933,
            "zone1_number_count": 11_598,
            "zone2_number_count": 1_933,
            "failed_draw_count": 0,
        }
        for name, expected in required.items():
            if migration[name] != expected:
                raise P638ForwardingError(f"P638 draw authority migration mismatch for {name}")
        draw_rows = connection.execute(
            """
            SELECT draw_id, draw_number, draw_date, source_reference,
                   source_record_sha256, status
            FROM lottery_draw
            WHERE migration_id = ? AND lottery_type = 'POWER_LOTTO'
            ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
            """,
            ("P638_OLD_DB_DRAW_MIGRATION_R1",),
        ).fetchall()
        number_rows = connection.execute(
            """
            SELECT draw_id, zone, position, number
            FROM lottery_draw_number
            WHERE draw_id IN (
                SELECT draw_id FROM lottery_draw
                WHERE migration_id = ? AND lottery_type = 'POWER_LOTTO'
            )
            ORDER BY draw_id ASC, zone ASC, position ASC
            """,
            ("P638_OLD_DB_DRAW_MIGRATION_R1",),
        ).fetchall()
        numbers: dict[int, dict[int, list[int]]] = {}
        for row in number_rows:
            numbers.setdefault(int(row["draw_id"]), {}).setdefault(int(row["zone"]), []).append(
                _exact_int(row["number"], "draw authority number")
            )
        draws: list[_SourceDraw] = []
        for row in draw_rows:
            if str(row["status"]) != "COMPLETE":
                raise P638ForwardingError("P638 draw authority contains a non-COMPLETE draw")
            grouped = numbers.get(int(row["draw_id"]), {})
            zone1 = tuple(grouped.get(1, []))
            zone2_values = grouped.get(2, [])
            if len(zone1) != 6 or len(zone2_values) != 1:
                raise P638ForwardingError("P638 draw authority has an incomplete draw")
            draws.append(
                _SourceDraw(
                    draw_number=str(row["draw_number"]),
                    draw_date=str(row["draw_date"]),
                    zone1=zone1,
                    zone2=zone2_values[0],
                    source_reference=str(row["source_reference"]),
                    draw_sha256=str(row["source_record_sha256"]),
                )
            )
    if len(draws) != 1933 or len({draw.draw_number for draw in draws}) != len(draws):
        raise P638ForwardingError("P638 draw authority draw count or identities mismatch")
    return _DrawAuthority(
        migration_id="P638_OLD_DB_DRAW_MIGRATION_R1",
        source_run_id=expected_source_run_id,
        draws=tuple(draws),
    )


def _current_registry(replay: _ReplayBundle) -> tuple[_RegistryEntry, ...]:
    from lottolab.research.powerlotto_wave1 import WAVE1_DONOR_BLOCKED_STRATEGIES
    from lottolab.strategies.adapters.powerlotto_wave1 import (
        WAVE1_BLOCKED_STRATEGIES,
        WAVE1_STRATEGY_BY_ID,
    )

    # This forwarder is pinned to one frozen R4 source bundle
    # (SOURCE_REPLAY_RUN_ID) that only ever covered its own strategy set.
    # The live executable registry may have grown since (e.g. the P638
    # all-10 vertical added power_fourier_rhythm_2bet and
    # power_orthogonal_5bet), so this only checks that every strategy the
    # frozen bundle DOES contain still matches its live identity -- it does
    # not require the live registry to be limited to that frozen set.
    source_by_id = {strategy.strategy_id: strategy for strategy in replay.strategies}
    entries: list[_RegistryEntry] = []
    for strategy_id in sorted(source_by_id):
        source = source_by_id[strategy_id]
        spec = WAVE1_STRATEGY_BY_ID.get(strategy_id)
        if spec is None or spec.strategy_version != source.strategy_version:
            raise P638ForwardingError(f"P638 strategy identity conflict: {strategy_id}")
        entries.append(
            _RegistryEntry(
                strategy_id=spec.strategy_id,
                strategy_version=spec.strategy_version,
                display_label=spec.strategy_id,
                executable=True,
                adapter_path=ADAPTER_PATH,
                native_ticket_count=source.native_ticket_count,
                min_history=source.min_history,
                source_paths=source.source_paths,
                lifecycle_status="ONLINE",
                replay_status="R4_RESULT_REUSABLE",
                provenance=source.provenance,
                exclusion_reason=None,
                source_strategy=source,
            )
        )

    blocked: dict[str, tuple[str, tuple[str, ...], str]] = {}
    for item in WAVE1_BLOCKED_STRATEGIES:
        blocked[item.strategy_id] = (
            item.reason,
            item.source_paths,
            "EXCLUDED_DONOR_DEFECT",
        )
    for item in WAVE1_DONOR_BLOCKED_STRATEGIES:
        strategy_id = str(item["strategy_id"])
        reason = str(item["reason"])
        source_paths = tuple(str(path) for path in cast(Iterable[object], item["source_paths"]))
        replay_status = (
            "EXCLUDED_DONOR_DEFECT"
            if "orphan" in reason.casefold() or "blocker" in reason.casefold()
            else "EXCLUDED_UNRESOLVED_CONTRACT"
        )
        if strategy_id in blocked:
            prior_reason, prior_paths, prior_status = blocked[strategy_id]
            blocked[strategy_id] = (
                f"{prior_reason}; research ledger: {reason}",
                tuple(dict.fromkeys((*prior_paths, *source_paths))),
                prior_status,
            )
        else:
            blocked[strategy_id] = (reason, source_paths, replay_status)
    for strategy_id in sorted(blocked):
        reason, source_paths, replay_status = blocked[strategy_id]
        entries.append(
            _RegistryEntry(
                strategy_id=strategy_id,
                strategy_version="UNRESOLVED_CONTRACT",
                display_label=strategy_id,
                executable=False,
                adapter_path=None,
                native_ticket_count=None,
                min_history=None,
                source_paths=source_paths,
                lifecycle_status="BLOCKED",
                replay_status=replay_status,
                provenance=(
                    "P638 current donor ledger identity retained without invented behavior; "
                    f"{reason}"
                ),
                exclusion_reason=reason,
                source_strategy=None,
            )
        )
    identities = [(entry.strategy_id, entry.strategy_version) for entry in entries]
    if len(set(identities)) != len(identities):
        raise P638ForwardingError("P638 current registry contains duplicate identities")
    return tuple(sorted(entries, key=lambda entry: (entry.strategy_id, entry.strategy_version)))


def _identity_payload(
    *,
    replay: _ReplayBundle,
    authority: _DrawAuthority,
    registry: tuple[_RegistryEntry, ...],
    replay_sha256: str,
    draw_sha256: str,
) -> dict[str, object]:
    return {
        "contract_version": FORWARDING_CONTRACT_VERSION,
        "lottery_type": P638_LOTTERY_TYPE,
        "source_run_id": replay.source_run_id,
        "source_content_sha256": replay.source_content_sha256,
        "source_replay_sha256": replay_sha256,
        "source_draw_db_sha256": draw_sha256,
        "source_draw_migration_id": authority.migration_id,
        "source_commit": SOURCE_COMMIT_OID,
        "source_completion": replay.completion,
        "registry": [_registry_dict(entry) for entry in registry],
    }


def _registry_dict(entry: _RegistryEntry) -> dict[str, object]:
    return {
        "strategy_id": entry.strategy_id,
        "strategy_version": entry.strategy_version,
        "display_label": entry.display_label,
        "executable": entry.executable,
        "adapter_path": entry.adapter_path,
        "native_ticket_count": entry.native_ticket_count,
        "min_history": entry.min_history,
        "source_paths": list(entry.source_paths),
        "lifecycle_status": entry.lifecycle_status,
        "replay_status": entry.replay_status,
        "provenance": entry.provenance,
        "exclusion_reason": entry.exclusion_reason,
    }


def _insert_registry(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    registry: tuple[_RegistryEntry, ...],
    created_at: str,
    source_replay_sha256: str,
) -> dict[tuple[str, str], str]:
    snapshot_ids: dict[tuple[str, str], str] = {}
    for entry in registry:
        identity = f"{run_id}|{entry.strategy_id}|{entry.strategy_version}"
        snapshot_id = f"p638-strategy-{hashlib.sha256(identity.encode()).hexdigest()[:24]}"
        descriptor_sha256 = _sha256_json(_registry_dict(entry))
        governance_status = "ONLINE" if entry.executable else "REJECTED"
        connection.execute(
            """
            INSERT INTO historical_strategy_snapshot (
                id, run_id, strategy_id, effective_strategy_id, strategy_version,
                replicate, identity_kind, governance_status, alias_of_strategy_id,
                equivalence_group, nested_prefix_supported, descriptor_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, 1, 'REAL', ?, NULL, 'P638', 0, ?, ?)
            """,
            (
                snapshot_id,
                run_id,
                entry.strategy_id,
                entry.strategy_id,
                entry.strategy_version,
                governance_status,
                descriptor_sha256,
                created_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO historical_p638_strategy_ledger (
                strategy_snapshot_id, run_id, strategy_id, strategy_version, lottery_type,
                display_label, executable, adapter_path, native_ticket_count, min_history,
                zone1_contract, zone2_contract, lifecycle_status, replay_status,
                source_run_id, source_replay_sha256, source_paths_json, provenance,
                exclusion_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                run_id,
                entry.strategy_id,
                entry.strategy_version,
                P638_LOTTERY_TYPE,
                entry.display_label,
                int(entry.executable),
                entry.adapter_path,
                entry.native_ticket_count,
                entry.min_history,
                ZONE1_CONTRACT,
                ZONE2_CONTRACT,
                entry.lifecycle_status,
                entry.replay_status,
                SOURCE_REPLAY_RUN_ID if entry.source_strategy is not None else None,
                source_replay_sha256 if entry.source_strategy is not None else None,
                json.dumps(entry.source_paths, ensure_ascii=False, separators=(",", ":")),
                entry.provenance,
                entry.exclusion_reason,
            ),
        )
        snapshot_ids[(entry.strategy_id, entry.strategy_version)] = snapshot_id
    return snapshot_ids


def _insert_draws(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    draws: tuple[_SourceDraw, ...],
    created_at: str,
) -> dict[str, int]:
    snapshot_ids: dict[str, int] = {}
    for draw in draws:
        cursor = connection.execute(
            """
            INSERT INTO historical_draw_snapshot (
                run_id, lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, draw_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                P638_LOTTERY_TYPE,
                draw.draw_number,
                draw.draw_date,
                json.dumps(draw.zone1, separators=(",", ":")),
                json.dumps([draw.zone2], separators=(",", ":")),
                draw.draw_sha256,
                created_at,
            ),
        )
        if cursor.lastrowid is None:
            raise P638ForwardingError("P638 Historical draw snapshot insert has no row id")
        snapshot_ids[draw.draw_number] = int(cursor.lastrowid)
    return snapshot_ids


def _insert_targets_and_tickets(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    replay: _ReplayBundle,
    authority: _DrawAuthority,
    registry: tuple[_RegistryEntry, ...],
    snapshot_ids: dict[tuple[str, str], str],
    draw_snapshot_ids: dict[str, int],
    source_replay_sha256: str,
) -> None:
    del registry
    source_draws = {draw.draw_number: draw for draw in authority.draws}
    target_ids: dict[tuple[str, str, str], str] = {}
    for target in replay.targets:
        strategy_key = (target.strategy_id, target.strategy_version)
        snapshot_id = snapshot_ids.get(strategy_key)
        if snapshot_id is None:
            raise P638ForwardingError("P638 target has no current strategy snapshot")
        actual = source_draws.get(target.target_draw_number)
        if actual is None:
            raise P638ForwardingError("P638 target has no reconciled draw authority row")
        boundary = (
            None
            if target.cutoff_draw_number is None
            else source_draws.get(target.cutoff_draw_number)
        )
        if target.cutoff_draw_number is not None and boundary is None:
            raise P638ForwardingError("P638 target has no reconciled history boundary")
        target_identity = (
            f"{run_id}|{target.strategy_id}|{target.strategy_version}|{target.target_draw_number}"
        )
        target_id = f"p638-target-{hashlib.sha256(target_identity.encode()).hexdigest()[:24]}"
        target_ids[(target.strategy_id, target.strategy_version, target.target_draw_number)] = (
            target_id
        )
        connection.execute(
            """
            INSERT INTO historical_p638_target (
                id, run_id, strategy_snapshot_id, strategy_id, strategy_version,
                target_draw_snapshot_id, cutoff_draw_snapshot_id, target_draw_number,
                target_draw_date, history_boundary_draw_number, history_boundary_date,
                history_length, expected_ticket_count, status, exclusion_reason,
                failure_reason, source_target_locator
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_id,
                run_id,
                snapshot_id,
                target.strategy_id,
                target.strategy_version,
                draw_snapshot_ids[target.target_draw_number],
                None if boundary is None else draw_snapshot_ids[target.cutoff_draw_number or ""],
                target.target_draw_number,
                actual.draw_date,
                target.cutoff_draw_number,
                None if boundary is None else boundary.draw_date,
                target.cutoff_index,
                target.expected_ticket_count,
                target.status,
                target.failure_reason if target.status == "EXCLUDED_INSUFFICIENT_HISTORY" else None,
                target.failure_reason if target.status == "FAILED" else None,
                (
                    f"p638_wave1_replay_r4.sqlite3::strategy_targets::"
                    f"{target.strategy_id}:{target.strategy_version}:{target.target_draw_number}"
                ),
            ),
        )

    for ticket in replay.tickets:
        target_key = (
            ticket.strategy_id,
            ticket.strategy_version,
            ticket.target_draw_number,
        )
        target_id = target_ids.get(target_key)
        actual = source_draws.get(ticket.target_draw_number)
        if target_id is None or actual is None:
            raise P638ForwardingError("P638 ticket has no target or draw authority row")
        ticket_identity = f"{target_id}|{ticket.position}"
        ticket_id = f"p638-ticket-{hashlib.sha256(ticket_identity.encode()).hexdigest()[:24]}"
        connection.execute(
            """
            INSERT INTO historical_p638_ticket (
                id, target_id, run_id, strategy_id, strategy_version, target_draw_number,
                ticket_position, predicted_zone1_numbers_json, predicted_zone2_number,
                actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count, zone2_hit,
                status, source_run_id, source_replay_sha256, source_record_locator,
                second_zone_ssot_version, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                target_id,
                run_id,
                ticket.strategy_id,
                ticket.strategy_version,
                ticket.target_draw_number,
                ticket.position,
                json.dumps(ticket.predicted_zone1, separators=(",", ":")),
                ticket.predicted_zone2,
                json.dumps(actual.zone1, separators=(",", ":")),
                actual.zone2,
                ticket.zone1_hits,
                int(ticket.zone2_hit),
                ticket.status,
                SOURCE_REPLAY_RUN_ID,
                source_replay_sha256,
                (
                    f"p638_wave1_replay_r4.sqlite3::tickets::"
                    f"{ticket.strategy_id}:{ticket.strategy_version}:"
                    f"{ticket.target_draw_number}:{ticket.position}"
                ),
                ticket.ssot_version,
                ticket.provenance,
            ),
        )


def _result_from_output(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    source_run_id: str,
    source_replay_sha256: str,
    source_draw_db_sha256: str,
    is_idempotent_replay: bool,
) -> P638ForwardingResult:
    ledger_count = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM historical_p638_strategy_ledger
            WHERE run_id = ? AND lottery_type = ?
            """,
            (run_id, P638_LOTTERY_TYPE),
        ).fetchone()[0]
    )
    draw_count = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM historical_draw_snapshot
            WHERE run_id = ? AND lottery_type = ?
            """,
            (run_id, P638_LOTTERY_TYPE),
        ).fetchone()[0]
    )
    target_counts = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            """
            SELECT status, COUNT(*) FROM historical_p638_target
            WHERE run_id = ?
            GROUP BY status
            """,
            (run_id,),
        ).fetchall()
    }
    ticket_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM historical_p638_ticket WHERE run_id = ? AND status = 'COMPLETE'",
            (run_id,),
        ).fetchone()[0]
    )
    excluded_strategy_count = int(
        connection.execute(
            """
            SELECT COUNT(*) FROM historical_p638_strategy_ledger
            WHERE run_id = ? AND executable = 0
            """,
            (run_id,),
        ).fetchone()[0]
    )
    return P638ForwardingResult(
        run_id=run_id,
        import_identity_sha256=str(
            connection.execute(
                "SELECT import_identity_sha256 FROM historical_result_run WHERE id = ?",
                (run_id,),
            ).fetchone()[0]
        ),
        source_run_id=source_run_id,
        source_replay_sha256=source_replay_sha256,
        source_draw_db_sha256=source_draw_db_sha256,
        strategy_count=ledger_count,
        draw_count=draw_count,
        source_target_count=int(
            connection.execute(
                "SELECT total_source_targets FROM historical_p638_run WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        ),
        source_complete_target_count=int(
            connection.execute(
                "SELECT complete_targets FROM historical_p638_run WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        ),
        source_excluded_target_count=int(
            connection.execute(
                "SELECT excluded_targets FROM historical_p638_run WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        ),
        source_failed_target_count=int(
            connection.execute(
                "SELECT failed_targets FROM historical_p638_run WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        ),
        source_ticket_count=int(
            connection.execute(
                "SELECT ticket_rows FROM historical_p638_run WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        ),
        forwarded_target_count=sum(target_counts.values()),
        forwarded_complete_target_count=target_counts.get("COMPLETE", 0),
        forwarded_excluded_target_count=target_counts.get("EXCLUDED_INSUFFICIENT_HISTORY", 0),
        forwarded_failed_target_count=target_counts.get("FAILED", 0),
        forwarded_ticket_count=ticket_count,
        excluded_strategy_count=excluded_strategy_count,
        is_idempotent_replay=is_idempotent_replay,
    )


def _assert_forwarded_totals(
    result: P638ForwardingResult,
    replay: _ReplayBundle,
    registry: tuple[_RegistryEntry, ...],
    authority: _DrawAuthority,
) -> None:
    if result.draw_count != len(authority.draws):
        raise P638ForwardingError("P638 forwarded draw count does not reconcile")
    if result.forwarded_target_count != len(replay.targets):
        raise P638ForwardingError("P638 forwarded target count does not reconcile")
    if result.forwarded_complete_target_count != int(replay.completion["complete_targets"]):
        raise P638ForwardingError("P638 forwarded COMPLETE target count does not reconcile")
    if result.forwarded_excluded_target_count != int(replay.completion["excluded_targets"]):
        raise P638ForwardingError("P638 forwarded exclusion count does not reconcile")
    if result.forwarded_failed_target_count != int(replay.completion["failed_targets"]):
        raise P638ForwardingError("P638 forwarded failure count does not reconcile")
    if result.forwarded_ticket_count != int(replay.completion["ticket_rows"]):
        raise P638ForwardingError("P638 forwarded ticket count does not reconcile")
    if result.strategy_count != len(registry):
        raise P638ForwardingError("P638 forwarded strategy ledger count does not reconcile")


def _validate_replay_totals(
    draws: tuple[_SourceDraw, ...],
    strategies: tuple[_ReplayStrategy, ...],
    targets: tuple[_ReplayTarget, ...],
    tickets: list[_ReplayTicket],
    completion: dict[str, int | str],
) -> None:
    if int(completion["total_source_targets"]) != len(draws):
        raise P638ForwardingError("P638 R4 source draw total does not reconcile")
    if int(completion["selected_strategies"]) != len(strategies):
        raise P638ForwardingError("P638 R4 source strategy total does not reconcile")
    counts = {
        "COMPLETE": sum(target.status == "COMPLETE" for target in targets),
        "EXCLUDED_INSUFFICIENT_HISTORY": sum(
            target.status == "EXCLUDED_INSUFFICIENT_HISTORY" for target in targets
        ),
        "FAILED": sum(target.status == "FAILED" for target in targets),
    }
    if counts["COMPLETE"] != int(completion["complete_targets"]):
        raise P638ForwardingError("P638 R4 COMPLETE target count does not reconcile")
    if counts["EXCLUDED_INSUFFICIENT_HISTORY"] != int(completion["excluded_targets"]):
        raise P638ForwardingError("P638 R4 exclusion count does not reconcile")
    if counts["FAILED"] != int(completion["failed_targets"]):
        raise P638ForwardingError("P638 R4 failure count does not reconcile")
    if counts["FAILED"] != 0:
        raise P638ForwardingError("P638 R4 source contains failed targets")
    if int(completion["eligible_attempts"]) != counts["COMPLETE"] + counts["FAILED"]:
        raise P638ForwardingError("P638 R4 eligible-attempt total does not reconcile")
    if len(tickets) != int(completion["ticket_rows"]):
        raise P638ForwardingError("P638 R4 ticket total does not reconcile")
    strategy_ids = {(strategy.strategy_id, strategy.strategy_version) for strategy in strategies}
    target_keys = {
        (target.strategy_id, target.strategy_version, target.target_draw_number)
        for target in targets
    }
    ticket_keys = {
        (ticket.strategy_id, ticket.strategy_version, ticket.target_draw_number, ticket.position)
        for ticket in tickets
    }
    if len(ticket_keys) != len(tickets):
        raise P638ForwardingError("P638 R4 ticket natural keys are duplicated")
    draw_numbers = {draw.draw_number for draw in draws}
    for target in targets:
        if (target.strategy_id, target.strategy_version) not in strategy_ids:
            raise P638ForwardingError("P638 R4 target references an unknown strategy")
        if target.target_draw_number not in draw_numbers:
            raise P638ForwardingError("P638 R4 target references an unknown draw")
        expected = 0 if target.status != "COMPLETE" else target.expected_ticket_count
        actual = sum(
            ticket.strategy_id == target.strategy_id
            and ticket.strategy_version == target.strategy_version
            and ticket.target_draw_number == target.target_draw_number
            for ticket in tickets
        )
        if actual != expected:
            raise P638ForwardingError("P638 R4 target ticket count does not reconcile")
    if len(target_keys) != len(targets):
        raise P638ForwardingError("P638 R4 target natural keys are duplicated")


def _reconcile_draws(
    replay_draws: tuple[_SourceDraw, ...], authority_draws: tuple[_SourceDraw, ...]
) -> None:
    replay_by_number = {draw.draw_number: draw for draw in replay_draws}
    authority_by_number = {draw.draw_number: draw for draw in authority_draws}
    if set(replay_by_number) != set(authority_by_number):
        raise P638ForwardingError("P638 R4/source draw identity sets differ")
    for number, replay in replay_by_number.items():
        authority = authority_by_number[number]
        if replay.draw_date != authority.draw_date:
            raise P638ForwardingError(f"P638 draw date mismatch for {number}")
        if replay.zone1 != authority.zone1:
            raise P638ForwardingError(f"P638 zone-1 mismatch for {number}")
        if replay.zone2 != authority.zone2:
            raise P638ForwardingError(f"P638 zone-2 mismatch for {number}")


def _verify_source_file(
    path: Path, *, expected_sha256: str, expected_bytes: int, label: str
) -> str:
    if not path.is_absolute() or not path.is_file():
        raise P638ForwardingError(f"{label} is not an existing file")
    if path.stat().st_size != expected_bytes:
        raise P638ForwardingError(f"{label} byte size does not match its pinned authority")
    digest = _file_sha256(path)
    if digest != expected_sha256:
        raise P638ForwardingError(f"{label} SHA-256 does not match its pinned authority")
    return digest


def _validate_output_path(path: Path) -> None:
    if not path.is_absolute() or path.name in {"lottery_v2.db", "production.db"}:
        raise P638ForwardingError("P638 Historical Results output must be an explicit task path")
    if any(part.casefold() == "lotterynew" for part in path.parts):
        raise P638ForwardingError("P638 Historical Results output path is protected")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_connection(path: Path):
    class _ConnectionContext:
        def __enter__(self) -> sqlite3.Connection:
            if not path.is_absolute() or not path.is_file():
                raise P638ForwardingError("P638 source database is unavailable")
            uri = f"{path.resolve().as_uri()}?mode=ro"
            try:
                self.connection = sqlite3.connect(uri, uri=True)
                self.connection.row_factory = sqlite3.Row
                self.connection.execute("PRAGMA query_only = ON")
                query_only = self.connection.execute("PRAGMA query_only").fetchone()
                if query_only is None or int(query_only[0]) != 1:
                    raise P638ForwardingError("P638 source database is not query-only")
                return self.connection
            except (sqlite3.Error, P638ForwardingError) as exc:
                if hasattr(self, "connection"):
                    self.connection.close()
                if isinstance(exc, P638ForwardingError):
                    raise
                raise P638ForwardingError(
                    "P638 source database cannot be opened read-only"
                ) from exc

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            self.connection.close()

    return _ConnectionContext()


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _decode_numbers(raw: object, *, expected_count: int) -> tuple[int, ...]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise P638ForwardingError("P638 source numbers are malformed") from exc
    if not isinstance(value, list):
        raise P638ForwardingError("P638 source numbers are malformed")
    items = cast(list[object], value)
    if len(items) != expected_count or not all(type(item) is int for item in items):
        raise P638ForwardingError("P638 source numbers are malformed")
    return tuple(cast(list[int], items))


def _decode_text_list(raw: object) -> list[str]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise P638ForwardingError("P638 source paths are malformed") from exc
    if not isinstance(value, list):
        raise P638ForwardingError("P638 source paths are malformed")
    items = cast(list[object], value)
    if not all(type(item) is str for item in items):
        raise P638ForwardingError("P638 source paths are malformed")
    return cast(list[str], items)


def _exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise P638ForwardingError(f"{label} is not an integer")
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "FORWARDING_CONTRACT_VERSION",
    "SOURCE_DRAW_DB_BYTES",
    "SOURCE_DRAW_DB_SHA256",
    "SOURCE_REPLAY_DB_BYTES",
    "SOURCE_REPLAY_DB_SHA256",
    "SOURCE_REPLAY_RUN_ID",
    "P638ForwardingError",
    "P638HistoricalForwarder",
]
