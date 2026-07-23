"""Read one exact Historical Results import for success-window evaluation.

The adapter opens only the explicit historical-results database in SQLite
read-only mode.  It independently rechecks persisted descriptor, draw,
ticket, portfolio, prefix, and import identities before returning the narrow
application source model.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessDrawIdentity,
    HistoricalPrefixSuccessSourceObservation,
    HistoricalPrefixSuccessSourceStrategy,
    HistoricalPrefixSuccessStrategyIdentity,
    HistoricalPrefixSuccessTicketOutcome,
    HistoricalPrefixSuccessWindowsContractError,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixSuccessWindowSourceMetadata,
    HistoricalPrefixSuccessWindowsUnavailableError,
)
from lottolab.domain.historical_results import (
    HistoricalGovernanceStatus,
    HistoricalIdentityKind,
    HistoricalLotteryType,
    HistoricalSourceKind,
)
from lottolab.evidence.canonical_json import canonical_bytes, sha256_hex
from lottolab.infrastructure.persistence.historical_schema import (
    HistoricalSchemaError,
    open_database,
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_SHA1_PATTERN = re.compile(r"[0-9a-f]{40}", flags=re.ASCII)
_DRAW_NUMBER_PATTERN = re.compile(r"[0-9]+", flags=re.ASCII)


@dataclass(frozen=True, slots=True)
class _Descriptor:
    snapshot_id: str
    identity: HistoricalPrefixSuccessStrategyIdentity


@dataclass(frozen=True, slots=True)
class _Draw:
    row_id: int
    identity: HistoricalPrefixSuccessDrawIdentity
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Ticket:
    outcome: HistoricalPrefixSuccessTicketOutcome
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]


def _unavailable(message: str) -> HistoricalPrefixSuccessWindowsUnavailableError:
    return HistoricalPrefixSuccessWindowsUnavailableError(message)


def _text(raw: object, name: str) -> str:
    if type(raw) is not str or not raw or raw != raw.strip():
        raise _unavailable(f"stored {name} is malformed")
    return raw


def _optional_text(raw: object, name: str) -> str | None:
    if raw is None:
        return None
    return _text(raw, name)


def _sha256(raw: object, name: str) -> str:
    value = _text(raw, name)
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise _unavailable(f"stored {name} is not an exact lowercase SHA-256")
    return value


def _integer(raw: object, name: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise _unavailable(f"stored {name} is not an integer")
    return raw


def _boolean(raw: object, name: str) -> bool:
    value = _integer(raw, name)
    if value not in (0, 1):
        raise _unavailable(f"stored {name} is not a SQLite boolean")
    return bool(value)


def _numbers(raw: object, name: str) -> tuple[int, ...]:
    if type(raw) is not str:
        raise _unavailable(f"stored {name} is malformed")
    try:
        parsed: object = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _unavailable(f"stored {name} is malformed") from exc
    if not isinstance(parsed, list):
        raise _unavailable(f"stored {name} is malformed")
    values = tuple(_integer(item, name) for item in cast(list[object], parsed))
    return values


def _validate_big_lotto_numbers(
    main_numbers: tuple[int, ...], special_numbers: tuple[int, ...]
) -> None:
    if len(main_numbers) != 6 or len(set(main_numbers)) != 6:
        raise _unavailable("stored Big Lotto main numbers are malformed")
    if len(special_numbers) != 1:
        raise _unavailable("stored Big Lotto special number is malformed")
    if main_numbers != tuple(sorted(main_numbers)) or special_numbers != tuple(
        sorted(special_numbers)
    ):
        raise _unavailable("stored Big Lotto numbers are not canonical")
    if any(not 1 <= value <= 49 for value in (*main_numbers, *special_numbers)):
        raise _unavailable("stored Big Lotto number is outside the legal range")
    if set(main_numbers) & set(special_numbers):
        raise _unavailable("stored Big Lotto main and special numbers overlap")


def _draw_number(raw: object) -> int:
    value = _text(raw, "draw_number")
    if _DRAW_NUMBER_PATTERN.fullmatch(value) is None:
        raise _unavailable("stored draw_number is malformed")
    number = int(value)
    if number < 1 or str(number) != value:
        raise _unavailable("stored draw_number is not canonical numeric text")
    return number


def _draw_date(raw: object) -> str:
    value = _text(raw, "draw_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise _unavailable("stored draw_date is malformed") from exc
    if parsed.isoformat() != value:
        raise _unavailable("stored draw_date is not canonical")
    return value


def _descriptor_hash(identity: HistoricalPrefixSuccessStrategyIdentity) -> str:
    payload: dict[str, object] = {
        "strategy_id": identity.strategy_id,
        "effective_strategy_id": identity.effective_strategy_id,
        "strategy_version": identity.strategy_version,
        "replicate": identity.replicate,
        "identity_kind": identity.identity_kind,
        "governance_status": identity.governance_status,
        "nested_prefix_supported": identity.nested_prefix_supported,
    }
    if identity.alias_of_strategy_id is not None:
        payload["alias_of_strategy_id"] = identity.alias_of_strategy_id
    if identity.equivalence_group is not None:
        payload["equivalence_group"] = identity.equivalence_group
    return sha256_hex(canonical_bytes(payload))


def _draw_hash(draw: _Draw) -> str:
    return sha256_hex(
        canonical_bytes(
            {
                "draw_number": draw.identity.draw_number,
                "draw_date": draw.identity.draw_date,
                "main_numbers": sorted(draw.main_numbers),
                "special_numbers": sorted(draw.special_numbers),
            }
        )
    )


def _ticket_hash(ticket: _Ticket) -> str:
    return sha256_hex(
        canonical_bytes(
            {
                "portfolio_position": ticket.outcome.portfolio_position,
                "main_numbers": sorted(ticket.main_numbers),
                "special_numbers": sorted(ticket.special_numbers),
                "main_hit_count": ticket.outcome.main_hit_count,
                "special_hit": ticket.outcome.special_hit,
            }
        )
    )


def _portfolio_hash(
    *,
    identity: HistoricalPrefixSuccessStrategyIdentity,
    target: _Draw,
    cutoff: _Draw,
    constructor_identifier: str,
    ticket_hashes: list[str],
) -> str:
    return sha256_hex(
        canonical_bytes(
            {
                "strategy_id": identity.strategy_id,
                "strategy_version": identity.strategy_version,
                "replicate": identity.replicate,
                "target_draw_number": target.identity.draw_number,
                "cutoff_draw_number": cutoff.identity.draw_number,
                "constructor_identifier": constructor_identifier,
                "ticket_hashes": ticket_hashes,
            }
        )
    )


def _prefix_hash(ticket_hashes: list[str]) -> str:
    return sha256_hex(canonical_bytes({"ticket_hashes": ticket_hashes}))


class SQLiteHistoricalPrefixSuccessWindowSourceReader:
    """Dedicated read-only SQLite adapter for one exact COMPLETED import."""

    def __init__(self, database: Path) -> None:
        self._database = database

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        if (
            type(import_identity_sha256) is not str
            or _SHA256_PATTERN.fullmatch(import_identity_sha256) is None
        ):
            raise _unavailable("import selector is not an exact lowercase SHA-256")
        if not self._database.exists():
            return None
        try:
            with open_database(self._database, read_only=True) as connection:
                return self._load_from_connection(connection, import_identity_sha256)
        except HistoricalPrefixSuccessWindowsUnavailableError:
            raise
        except (
            HistoricalPrefixSuccessWindowsContractError,
            HistoricalSchemaError,
            sqlite3.Error,
            TypeError,
            ValueError,
        ) as exc:
            raise _unavailable("historical success-window source is unavailable") from exc

    def _load_from_connection(
        self,
        connection: sqlite3.Connection,
        import_identity_sha256: str,
    ) -> HistoricalPrefixSuccessWindowSource | None:
        if connection.execute("PRAGMA query_only").fetchone() != (1,):
            raise _unavailable("historical source connection is not read-only")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise _unavailable("historical source violates relational integrity")

        run_row = connection.execute(
            """
            SELECT id, contract_version, import_identity_sha256,
                   source_kind, source_repository, source_commit_oid,
                   source_artifact_sha256, dataset_identity, dataset_sha256, lottery_type
            FROM historical_result_run
            WHERE import_identity_sha256 = ? AND status = 'COMPLETED'
            """,
            (import_identity_sha256,),
        ).fetchone()
        if run_row is None:
            return None
        metadata = self._metadata(run_row)
        descriptors = self._descriptors(connection, metadata.run_id)
        draws = self._draws(connection, metadata.run_id)
        strategies, portfolio_hashes, target_numbers, target_cutoff_pairs = self._strategies(
            connection,
            metadata.run_id,
            descriptors,
            draws,
        )
        actual_import_identity = sha256_hex(
            canonical_bytes(
                {
                    "contract_version": metadata.contract_version,
                    "source_kind": metadata.source_kind,
                    "source_repository": metadata.source_repository,
                    "source_commit_oid": metadata.source_commit_oid,
                    "source_artifact_sha256": metadata.source_artifact_sha256,
                    "dataset_identity": metadata.dataset_identity,
                    "dataset_sha256": metadata.dataset_sha256,
                    "strategy_descriptor_identities": sorted(
                        item.identity.descriptor_sha256 for item in descriptors
                    ),
                    "draw_snapshot_identities": [
                        draw.identity.draw_sha256
                        for draw in sorted(
                            draws.values(), key=lambda item: item.identity.draw_number
                        )
                    ],
                    "target_draw_numbers": sorted(target_numbers),
                    "target_cutoff_pairs": [
                        [target, cutoff]
                        for target, cutoff in sorted(target_cutoff_pairs)
                    ],
                    "portfolio_payload_hashes": sorted(portfolio_hashes),
                }
            )
        )
        if actual_import_identity != metadata.import_identity_sha256:
            raise _unavailable("persisted import identity does not match reconstructed content")
        return HistoricalPrefixSuccessWindowSource(
            metadata=metadata,
            strategies=strategies,
        )

    @staticmethod
    def _metadata(row: tuple[object, ...]) -> HistoricalPrefixSuccessWindowSourceMetadata:
        (
            run_id,
            contract_version,
            import_identity_sha256,
            source_kind,
            source_repository,
            source_commit_oid,
            source_artifact_sha256,
            dataset_identity,
            dataset_sha256,
            lottery_type,
        ) = row
        source_kind_value = HistoricalSourceKind(_text(source_kind, "source_kind")).value
        source_commit = _text(source_commit_oid, "source_commit_oid")
        if _SHA1_PATTERN.fullmatch(source_commit) is None:
            raise _unavailable("stored source_commit_oid is not an exact lowercase SHA-1")
        return HistoricalPrefixSuccessWindowSourceMetadata(
            run_id=_text(run_id, "run_id"),
            contract_version=_text(contract_version, "contract_version"),
            import_identity_sha256=_sha256(
                import_identity_sha256, "import_identity_sha256"
            ),
            source_kind=source_kind_value,
            source_repository=_text(source_repository, "source_repository"),
            source_commit_oid=source_commit,
            source_artifact_sha256=_sha256(
                source_artifact_sha256, "source_artifact_sha256"
            ),
            dataset_identity=_text(dataset_identity, "dataset_identity"),
            dataset_sha256=_sha256(dataset_sha256, "dataset_sha256"),
            lottery_type=HistoricalLotteryType(_text(lottery_type, "lottery_type")),
        )

    @staticmethod
    def _descriptors(
        connection: sqlite3.Connection, run_id: str
    ) -> tuple[_Descriptor, ...]:
        rows = connection.execute(
            """
            SELECT id, strategy_id, effective_strategy_id, strategy_version, replicate,
                   identity_kind, governance_status, alias_of_strategy_id,
                   equivalence_group, nested_prefix_supported, descriptor_sha256
            FROM historical_strategy_snapshot
            WHERE run_id = ?
            ORDER BY rowid ASC
            """,
            (run_id,),
        ).fetchall()
        descriptors: list[_Descriptor] = []
        for row in rows:
            (
                snapshot_id,
                strategy_id,
                effective_strategy_id,
                strategy_version,
                replicate,
                identity_kind,
                governance_status,
                alias_of_strategy_id,
                equivalence_group,
                nested_prefix_supported,
                descriptor_sha256,
            ) = row
            identity = HistoricalPrefixSuccessStrategyIdentity(
                strategy_id=_text(strategy_id, "strategy_id"),
                effective_strategy_id=_text(
                    effective_strategy_id, "effective_strategy_id"
                ),
                strategy_version=_text(strategy_version, "strategy_version"),
                replicate=_integer(replicate, "replicate"),
                identity_kind=HistoricalIdentityKind(
                    _text(identity_kind, "identity_kind")
                ).value,
                governance_status=HistoricalGovernanceStatus(
                    _text(governance_status, "governance_status")
                ).value,
                alias_of_strategy_id=_optional_text(
                    alias_of_strategy_id, "alias_of_strategy_id"
                ),
                equivalence_group=_optional_text(
                    equivalence_group, "equivalence_group"
                ),
                nested_prefix_supported=_boolean(
                    nested_prefix_supported, "nested_prefix_supported"
                ),
                descriptor_sha256=_sha256(descriptor_sha256, "descriptor_sha256"),
            )
            if _descriptor_hash(identity) != identity.descriptor_sha256:
                raise _unavailable("persisted strategy descriptor hash mismatch")
            descriptors.append(
                _Descriptor(
                    snapshot_id=_text(snapshot_id, "strategy_snapshot_id"),
                    identity=identity,
                )
            )
        return tuple(descriptors)

    @staticmethod
    def _draws(connection: sqlite3.Connection, run_id: str) -> dict[int, _Draw]:
        rows = connection.execute(
            """
            SELECT id, draw_number, draw_date, main_numbers_json,
                   special_numbers_json, draw_sha256
            FROM historical_draw_snapshot
            WHERE run_id = ?
            ORDER BY CAST(draw_number AS INTEGER) ASC, rowid ASC
            """,
            (run_id,),
        ).fetchall()
        draws: dict[int, _Draw] = {}
        seen_numbers: set[int] = set()
        for row in rows:
            row_id, draw_number, draw_date, main_json, special_json, draw_sha256 = row
            main_numbers = _numbers(main_json, "draw main_numbers_json")
            special_numbers = _numbers(special_json, "draw special_numbers_json")
            _validate_big_lotto_numbers(main_numbers, special_numbers)
            numeric_draw_number = _draw_number(draw_number)
            if numeric_draw_number in seen_numbers:
                raise _unavailable("persisted source contains a duplicate numeric draw")
            seen_numbers.add(numeric_draw_number)
            draw = _Draw(
                row_id=_integer(row_id, "draw row id"),
                identity=HistoricalPrefixSuccessDrawIdentity(
                    draw_number=numeric_draw_number,
                    draw_date=_draw_date(draw_date),
                    draw_sha256=_sha256(draw_sha256, "draw_sha256"),
                ),
                main_numbers=main_numbers,
                special_numbers=special_numbers,
            )
            if _draw_hash(draw) != draw.identity.draw_sha256:
                raise _unavailable("persisted draw hash mismatch")
            draws[draw.row_id] = draw
        return draws

    @staticmethod
    def _strategies(
        connection: sqlite3.Connection,
        run_id: str,
        descriptors: tuple[_Descriptor, ...],
        draws: dict[int, _Draw],
    ) -> tuple[
        tuple[HistoricalPrefixSuccessSourceStrategy, ...],
        list[str],
        set[int],
        set[tuple[int, int]],
    ]:
        descriptor_by_id = {item.snapshot_id: item for item in descriptors}
        portfolio_rows = connection.execute(
            """
            SELECT id, strategy_snapshot_id, target_draw_snapshot_id,
                   cutoff_draw_snapshot_id, constructor_identifier,
                   portfolio_sha256, prefix10_sha256, prefix15_sha256
            FROM historical_portfolio
            WHERE run_id = ?
            ORDER BY rowid ASC
            """,
            (run_id,),
        ).fetchall()
        ticket_rows = connection.execute(
            """
            SELECT t.portfolio_id, t.portfolio_position, t.main_numbers_json,
                   t.special_numbers_json, t.main_hit_count, t.special_hit,
                   t.ticket_sha256
            FROM historical_ticket t
            JOIN historical_portfolio p ON p.id = t.portfolio_id
            WHERE p.run_id = ?
            ORDER BY p.rowid ASC, t.portfolio_position ASC
            """,
            (run_id,),
        ).fetchall()
        tickets_by_portfolio: dict[str, list[_Ticket]] = defaultdict(list)
        for row in ticket_rows:
            (
                portfolio_id,
                portfolio_position,
                main_json,
                special_json,
                main_hit_count,
                special_hit,
                ticket_sha256,
            ) = row
            main_numbers = _numbers(main_json, "ticket main_numbers_json")
            special_numbers = _numbers(special_json, "ticket special_numbers_json")
            _validate_big_lotto_numbers(main_numbers, special_numbers)
            ticket = _Ticket(
                outcome=HistoricalPrefixSuccessTicketOutcome(
                    portfolio_position=_integer(
                        portfolio_position, "portfolio_position"
                    ),
                    main_hit_count=_integer(main_hit_count, "main_hit_count"),
                    special_hit=_boolean(special_hit, "special_hit"),
                    ticket_sha256=_sha256(ticket_sha256, "ticket_sha256"),
                ),
                main_numbers=main_numbers,
                special_numbers=special_numbers,
            )
            if _ticket_hash(ticket) != ticket.outcome.ticket_sha256:
                raise _unavailable("persisted ticket hash mismatch")
            tickets_by_portfolio[_text(portfolio_id, "portfolio_id")].append(ticket)

        observations_by_descriptor: dict[
            str, list[HistoricalPrefixSuccessSourceObservation]
        ] = defaultdict(list)
        portfolio_hashes: list[str] = []
        target_numbers: set[int] = set()
        target_cutoff_pairs: set[tuple[int, int]] = set()
        seen_portfolio_ids: set[str] = set()
        seen_targets_by_descriptor: dict[str, set[int]] = defaultdict(set)
        for row in portfolio_rows:
            (
                portfolio_id_raw,
                snapshot_id_raw,
                target_id_raw,
                cutoff_id_raw,
                constructor_identifier_raw,
                portfolio_sha256_raw,
                prefix10_sha256_raw,
                prefix15_sha256_raw,
            ) = row
            portfolio_id = _text(portfolio_id_raw, "portfolio_id")
            if portfolio_id in seen_portfolio_ids:
                raise _unavailable("persisted source contains a duplicate portfolio identity")
            seen_portfolio_ids.add(portfolio_id)
            snapshot_id = _text(snapshot_id_raw, "strategy_snapshot_id")
            descriptor = descriptor_by_id.get(snapshot_id)
            target = draws.get(_integer(target_id_raw, "target_draw_snapshot_id"))
            cutoff = draws.get(_integer(cutoff_id_raw, "cutoff_draw_snapshot_id"))
            if descriptor is None or target is None or cutoff is None:
                raise _unavailable("persisted portfolio references missing source identity")
            target_number = target.identity.draw_number
            if target_number in seen_targets_by_descriptor[snapshot_id]:
                raise _unavailable(
                    "persisted source contains duplicate exact strategy/target data"
                )
            seen_targets_by_descriptor[snapshot_id].add(target_number)
            constructor_identifier = _text(
                constructor_identifier_raw, "constructor_identifier"
            )
            tickets = tickets_by_portfolio.pop(portfolio_id, [])
            if len(tickets) != 20 or tuple(
                item.outcome.portfolio_position for item in tickets
            ) != tuple(range(1, 21)):
                raise _unavailable("persisted portfolio does not contain tickets 1..20")
            ticket_hashes = [item.outcome.ticket_sha256 for item in tickets]
            portfolio_sha256 = _sha256(portfolio_sha256_raw, "portfolio_sha256")
            if (
                _portfolio_hash(
                    identity=descriptor.identity,
                    target=target,
                    cutoff=cutoff,
                    constructor_identifier=constructor_identifier,
                    ticket_hashes=ticket_hashes,
                )
                != portfolio_sha256
            ):
                raise _unavailable("persisted portfolio hash mismatch")
            if _prefix_hash(ticket_hashes[:10]) != _sha256(
                prefix10_sha256_raw, "prefix10_sha256"
            ):
                raise _unavailable("persisted prefix-10 hash mismatch")
            if _prefix_hash(ticket_hashes[:15]) != _sha256(
                prefix15_sha256_raw, "prefix15_sha256"
            ):
                raise _unavailable("persisted prefix-15 hash mismatch")
            observations_by_descriptor[snapshot_id].append(
                HistoricalPrefixSuccessSourceObservation(
                    target=target.identity,
                    cutoff=cutoff.identity,
                    constructor_identifier=constructor_identifier,
                    portfolio_sha256=portfolio_sha256,
                    tickets=tuple(item.outcome for item in tickets),
                )
            )
            portfolio_hashes.append(portfolio_sha256)
            target_numbers.add(target_number)
            target_cutoff_pairs.add((target_number, cutoff.identity.draw_number))
        if tickets_by_portfolio:
            raise _unavailable("persisted source contains unbound ticket rows")
        return (
            tuple(
                HistoricalPrefixSuccessSourceStrategy(
                    identity=descriptor.identity,
                    observations=tuple(observations_by_descriptor[descriptor.snapshot_id]),
                )
                for descriptor in descriptors
            ),
            portfolio_hashes,
            target_numbers,
            target_cutoff_pairs,
        )


__all__ = ["SQLiteHistoricalPrefixSuccessWindowSourceReader"]
