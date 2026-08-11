"""Owner-authorized BIG_LOTTO historical replay application boundary.

The current production catalog and the frozen full BIG_LOTTO identity catalog
are separate authorities.  This use case joins them without inventing
adapters for identities that are not executable.  Current identities execute
through the existing registry; historical-raw-only identities stream the
preserved native rows supplied by a caller-configured read-only source.

The returned run is lazy.  Iterating all identities constructs one controller
run at a time, so the application does not need to hold the foundation's
2.59-million-row raw dataset or every target result in memory simultaneously.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack, closing
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import IO, cast

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    ReplayStrategyBinding,
)
from lottolab.application.use_cases.generate_bet import (
    instantiate_adapter,
    instantiate_portfolio_adapter,
)
from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayController,
    ReplayTypedClosure,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalog,
    FullStrategyCatalogRecord,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    HistoricalReplayRequest,
    HistoricalReplayResult,
    ReplayBehavior,
    ReplayDraw,
    ReplaySourceSnapshot,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.strategies import ResponseShape, StrategyDescriptor
from lottolab.strategies.catalog import StrategyCatalog, production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry


class B649ReplayContractError(ValueError):
    """The B649 identity/source contract cannot be resolved safely."""


class B649IdentityStatus(StrEnum):
    """Mutually exclusive execution/accounting status for one B649 identity."""

    CURRENTLY_REPLAYABLE = "CURRENTLY_REPLAYABLE"
    HISTORICAL_RAW_ONLY = "HISTORICAL_RAW_ONLY"
    TERMINAL_UNAVAILABLE = "TERMINAL_UNAVAILABLE"
    RESOLVED_ALIAS = "RESOLVED_ALIAS"
    KEEP_UNRESOLVED_ALIAS = "KEEP_UNRESOLVED_ALIAS"


@dataclass(frozen=True, slots=True)
class B649IdentityAccount:
    """One canonical full-catalog identity and its non-overlapping status."""

    strategy_id: str
    status: B649IdentityStatus
    strategy_version: str
    canonical_strategy_id: str | None = None
    raw_history_available: bool = False
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.strategy_id or not self.strategy_version:
            raise ValueError("B649 identity fields must be non-empty")
        if type(self.status) is not B649IdentityStatus:
            raise ValueError("status must be a B649IdentityStatus")
        if self.canonical_strategy_id is not None and not self.canonical_strategy_id:
            raise ValueError("canonical_strategy_id must be non-empty when supplied")
        if type(self.raw_history_available) is not bool:
            raise ValueError("raw_history_available must be a boolean")


@dataclass(frozen=True, slots=True)
class B649HistoricalReplayRequest:
    """One application-level B649 replay selection and mode."""

    source: ReplaySourceSnapshot
    mode: HistoricalReplayMode = HistoricalReplayMode.FULL_REPLAY
    strategy_id: str | None = None
    cutoff_draw_number: str | None = None

    def __post_init__(self) -> None:
        if self.source.lottery_type is not LotteryType.BIG_LOTTO:
            raise B649ReplayContractError("B649 replay requires a BIG_LOTTO source")
        if type(self.mode) is not HistoricalReplayMode:
            raise B649ReplayContractError("mode must be a HistoricalReplayMode")
        if self.strategy_id is not None and not self.strategy_id:
            raise B649ReplayContractError("strategy_id must be non-empty when supplied")
        if self.cutoff_draw_number is not None and not self.cutoff_draw_number:
            raise B649ReplayContractError(
                "cutoff_draw_number must be non-empty when supplied"
            )


@dataclass(frozen=True, slots=True)
class B649StrategyReplayResult:
    """One identity's accounting record and optional controller result."""

    identity: B649IdentityAccount
    replay: HistoricalReplayResult | None
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        if self.replay is not None and self.blocked_reason is not None:
            raise ValueError("completed replay results must not have blocked_reason")
        if self.replay is None and not self.blocked_reason:
            raise ValueError("non-replayed identities require blocked_reason")


@dataclass(frozen=True, slots=True)
class B649HistoricalReplayResult:
    """Lazy all-identity result with explicit category counts."""

    mode: HistoricalReplayMode
    identities: tuple[B649IdentityAccount, ...]
    selected_strategy_ids: tuple[str, ...]
    _result_factory: Callable[[], Iterator[B649StrategyReplayResult]] = field(
        repr=False,
        compare=False,
    )

    @property
    def total_identity_count(self) -> int:
        return len(self.identities)

    def count(self, status: B649IdentityStatus) -> int:
        return sum(identity.status is status for identity in self.identities)

    @property
    def currently_replayable_identity_count(self) -> int:
        return self.count(B649IdentityStatus.CURRENTLY_REPLAYABLE)

    @property
    def historical_raw_only_identity_count(self) -> int:
        return self.count(B649IdentityStatus.HISTORICAL_RAW_ONLY)

    @property
    def terminal_unavailable_identity_count(self) -> int:
        return self.count(B649IdentityStatus.TERMINAL_UNAVAILABLE)

    @property
    def resolved_alias_count(self) -> int:
        return self.count(B649IdentityStatus.RESOLVED_ALIAS)

    @property
    def keep_unresolved_alias_count(self) -> int:
        return self.count(B649IdentityStatus.KEEP_UNRESOLVED_ALIAS)

    def iter_strategy_results(self) -> Iterator[B649StrategyReplayResult]:
        """Yield one identity result at a time with bounded replay memory."""

        return self._result_factory()


class B649RawHistoryError(ValueError):
    """A preserved raw-history source violates its read-only row contract."""


class B649RawHistoryClosure(ReplayTypedClosure):
    """A target has no safely replayable preserved output row."""


@dataclass(frozen=True, slots=True)
class _RawTicketRow:
    strategy_id: str
    strategy_version: str
    target_draw_number: str
    target_draw_date: date
    cutoff_draw_number: str | None
    cutoff_draw_date: date | None
    actual_main_numbers: tuple[int, ...]
    actual_special_number: int
    predicted_numbers: tuple[int, ...]
    ticket_position: int
    native_ticket_count: int
    replay_status: str


class B649RawHistorySource:
    """Lazy reader for caller-supplied ``raw_records/*.jsonl.gz`` rows."""

    def __init__(self, root: Path | str) -> None:
        source_root = Path(root)
        records_root = source_root / "raw_records"
        if not records_root.is_dir():
            raise B649RawHistoryError(
                f"raw history source must contain a raw_records directory: {records_root}"
            )
        self.root = source_root
        self._records_root = records_root
        self._native_count_hints = self._load_native_count_hints()

    @property
    def available_strategy_ids(self) -> frozenset[str]:
        return frozenset(
            path.name[: -len(".jsonl.gz")]
            for path in self._records_root.glob("*.jsonl.gz")
            if path.is_file()
        )

    def has_raw_history(self, strategy_id: str) -> bool:
        return self._path_for(strategy_id).is_file()

    def native_ticket_count_hint(self, strategy_id: str) -> int:
        return self._native_count_hints.get(strategy_id, 1)

    def implementation(self, strategy_id: str, strategy_version: str) -> object:
        if not self.has_raw_history(strategy_id):
            raise B649ReplayContractError(
                f"{strategy_id}: no preserved raw-history file is available"
            )
        return _B649RawReplayImplementation(self, strategy_id, strategy_version)

    def _path_for(self, strategy_id: str) -> Path:
        if not strategy_id or Path(strategy_id).name != strategy_id:
            raise B649RawHistoryError("strategy_id must be a simple raw-record filename stem")
        return self._records_root / f"{strategy_id}.jsonl.gz"

    def path_for(self, strategy_id: str) -> Path:
        """Return one validated raw-record path for an adapter cursor."""

        return self._path_for(strategy_id)

    def _load_native_count_hints(self) -> dict[str, int]:
        coverage_path = self.root / "strategy_coverage.csv"
        if not coverage_path.is_file():
            return {}
        hints: dict[str, int] = {}
        with coverage_path.open(newline="", encoding="utf-8") as handle:
            for raw_row in csv.DictReader(handle):
                row = cast(dict[str, str | None], raw_row)
                strategy_id = row.get("strategy_id")
                maximum = row.get("max_ticket_count")
                if not strategy_id or not maximum:
                    raise B649RawHistoryError(
                        "strategy_coverage.csv rows require strategy_id and max_ticket_count"
                    )
                try:
                    count = int(maximum)
                except ValueError as exc:
                    raise B649RawHistoryError(
                        f"{strategy_id}: max_ticket_count is not an integer"
                    ) from exc
                if count <= 0:
                    raise B649RawHistoryError(
                        f"{strategy_id}: max_ticket_count must be positive"
                    )
                hints[strategy_id] = count
        return hints


class _B649RawReplayImplementation:
    """One-pass target cursor over one strategy's preserved raw stream."""

    def __init__(
        self,
        source: B649RawHistorySource,
        strategy_id: str,
        strategy_version: str,
    ) -> None:
        self._source = source
        self._strategy_id = strategy_id
        self._strategy_version = strategy_version
        self.strategy_id = strategy_id
        self.strategy_version = strategy_version
        self._cursor = _RawHistoryCursor(source.path_for(strategy_id), strategy_id)

    def expected_native_ticket_count(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> int:
        del history, strategy
        group = self._cursor.group_for(target.draw_number)
        if group is None:
            return self._source.native_ticket_count_hint(self._strategy_id)
        return len(group)

    def get_replay_tickets(
        self,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        group = self._cursor.group_for(target.draw_number)
        if group is None:
            raise B649RawHistoryClosure(
                f"{self._strategy_id}: no preserved output for target "
                f"{target.draw_number}"
            )

        first = group[0]
        if first.strategy_version != self._strategy_version:
            raise B649RawHistoryClosure(
                f"{self._strategy_id}: preserved strategy version does not match replay"
            )
        if first.target_draw_date != target.draw_date:
            raise B649RawHistoryClosure(
                f"{self._strategy_id}: preserved target date does not match source"
            )
        if first.actual_main_numbers != target.main_numbers or (
            first.actual_special_number != target.special_number
        ):
            raise B649RawHistoryClosure(
                f"{self._strategy_id}: preserved official target does not match source"
            )

        last_history = history[-1] if history else None
        if last_history is None:
            if first.cutoff_draw_number is not None:
                raise B649RawHistoryClosure(
                    f"{self._strategy_id}: preserved output requires unavailable history"
                )
        elif first.cutoff_draw_number != last_history.draw_number:
            raise B649RawHistoryClosure(
                f"{self._strategy_id}: preserved causal cutoff is not the prior draw"
            )
        if last_history is not None and first.cutoff_draw_date not in (
            None,
            last_history.draw_date,
        ):
            raise B649RawHistoryClosure(
                f"{self._strategy_id}: preserved cutoff date is not causal"
            )

        return tuple(
            ReplayTicket(
                ticket_position=row.ticket_position,
                main_numbers=row.predicted_numbers,
            )
            for row in group
        )

class _RawHistoryCursor:
    """Read and validate one raw file incrementally, grouped by target."""

    def __init__(self, path: Path, strategy_id: str) -> None:
        self._path = path
        self._strategy_id = strategy_id
        self._handle: IO[str] | None = None
        self._exit_stack = ExitStack()
        self._iterator: Iterator[str] | None = None
        self._pending: _RawTicketRow | None = None
        self._last_requested_number: int | None = None
        self._last_group_number: str | None = None
        self._last_group: tuple[_RawTicketRow, ...] | None = None

    def group_for(self, target_draw_number: str) -> tuple[_RawTicketRow, ...] | None:
        try:
            target_number = int(target_draw_number)
        except ValueError as exc:
            raise B649RawHistoryError("target draw numbers must be integer strings") from exc
        if (
            self._last_requested_number is not None
            and target_number < self._last_requested_number
        ):
            raise B649RawHistoryError(
                f"{self._strategy_id}: target requests must be monotonic"
            )
        self._last_requested_number = target_number
        if self._last_group_number == target_draw_number:
            assert self._last_group is not None
            return self._last_group

        while True:
            if self._pending is None:
                self._pending = self._next_row()
            if self._pending is None:
                return None
            pending_number = int(self._pending.target_draw_number)
            if pending_number > target_number:
                return None
            group = self._consume_group()
            if pending_number == target_number:
                self._last_group_number = target_draw_number
                self._last_group = group
                return group

    def _consume_group(self) -> tuple[_RawTicketRow, ...]:
        assert self._pending is not None
        target_draw_number = self._pending.target_draw_number
        rows = [self._pending]
        self._pending = None
        while True:
            candidate = self._next_row()
            if candidate is None:
                break
            if candidate.target_draw_number != target_draw_number:
                self._pending = candidate
                break
            rows.append(candidate)

        positions = tuple(row.ticket_position for row in rows)
        expected_positions = tuple(range(1, len(rows) + 1))
        if positions != expected_positions:
            raise B649RawHistoryError(
                f"{self._strategy_id}/{target_draw_number}: native positions are not contiguous"
            )
        declared_counts = {row.native_ticket_count for row in rows}
        if declared_counts != {len(rows)}:
            raise B649RawHistoryError(
                f"{self._strategy_id}/{target_draw_number}: native count is inconsistent"
            )
        return tuple(rows)

    def _next_row(self) -> _RawTicketRow | None:
        if self._iterator is None:
            if not self._path.is_file():
                return None
            self._handle = self._exit_stack.enter_context(
                closing(gzip.open(self._path, "rt", encoding="utf-8"))  # noqa: SIM115
            )
            self._iterator = iter(self._handle)
        try:
            line = next(self._iterator)
        except StopIteration:
            self.close()
            return None
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise B649RawHistoryError(
                f"{self._strategy_id}: raw record is not valid JSON"
            ) from exc
        if not isinstance(raw, dict):
            raise B649RawHistoryError(f"{self._strategy_id}: raw record must be an object")
        return _parse_raw_ticket_row(cast(dict[str, object], raw), self._strategy_id)

    def close(self) -> None:
        if self._handle is not None:
            self._exit_stack.close()
            self._handle = None
            self._exit_stack = ExitStack()
        self._iterator = None

    def __del__(self) -> None:
        self.close()


def _parse_raw_ticket_row(raw: dict[str, object], strategy_id: str) -> _RawTicketRow:
    row_strategy_id = _required_text(raw, "canonical_strategy_id", strategy_id)
    if row_strategy_id != strategy_id:
        raise B649RawHistoryError(
            f"{strategy_id}: raw row belongs to {row_strategy_id}, not this identity"
        )
    strategy_version = _required_text(raw, "strategy_version", strategy_id)
    target_draw_number = _required_text(raw, "target_draw_number", strategy_id)
    target_draw_date = _required_date(raw, "target_draw_date", strategy_id)
    cutoff_draw_number = _optional_text(raw, "historical_input_cutoff_draw", strategy_id)
    cutoff_draw_date = _optional_date(raw, "historical_input_cutoff_date", strategy_id)
    actual_main_numbers = _biglotto_numbers(
        raw.get("actual_main_numbers"), "actual_main_numbers", strategy_id
    )
    actual_special_number = _biglotto_special(
        raw.get("actual_special_number"), "actual_special_number", strategy_id
    )
    predicted_numbers = _biglotto_numbers(
        raw.get("predicted_numbers"), "predicted_numbers", strategy_id
    )
    ticket_position = _positive_int(raw.get("ticket_position"), "ticket_position", strategy_id)
    native_ticket_count = _positive_int(
        raw.get("native_ticket_count"), "native_ticket_count", strategy_id
    )
    replay_status = _required_text(raw, "replay_status", strategy_id)
    return _RawTicketRow(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        cutoff_draw_number=cutoff_draw_number,
        cutoff_draw_date=cutoff_draw_date,
        actual_main_numbers=actual_main_numbers,
        actual_special_number=actual_special_number,
        predicted_numbers=predicted_numbers,
        ticket_position=ticket_position,
        native_ticket_count=native_ticket_count,
        replay_status=replay_status,
    )


def _required_text(raw: dict[str, object], key: str, strategy_id: str) -> str:
    value = raw.get(key)
    if type(value) is not str or not value:
        raise B649RawHistoryError(f"{strategy_id}: {key} must be non-empty text")
    return value


def _optional_text(raw: dict[str, object], key: str, strategy_id: str) -> str | None:
    value = raw.get(key)
    if value is None or value == "":
        return None
    if type(value) is not str:
        raise B649RawHistoryError(f"{strategy_id}: {key} must be text when supplied")
    return value


def _required_date(raw: dict[str, object], key: str, strategy_id: str) -> date:
    value = _required_text(raw, key, strategy_id)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise B649RawHistoryError(f"{strategy_id}: {key} must be ISO date text") from exc


def _optional_date(raw: dict[str, object], key: str, strategy_id: str) -> date | None:
    value = _optional_text(raw, key, strategy_id)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise B649RawHistoryError(f"{strategy_id}: {key} must be ISO date text") from exc


def _positive_int(value: object, key: str, strategy_id: str) -> int:
    if type(value) is not int or value <= 0:
        raise B649RawHistoryError(f"{strategy_id}: {key} must be a positive integer")
    return value


def _biglotto_numbers(value: object, key: str, strategy_id: str) -> tuple[int, ...]:
    if type(value) is not list:
        raise B649RawHistoryError(f"{strategy_id}: {key} must be a JSON list")
    raw_numbers = cast(list[object], value)
    if not all(type(number) is int for number in raw_numbers):
        raise B649RawHistoryError(
            f"{strategy_id}: {key} must contain six exact integer numbers"
        )
    numbers = tuple(cast(int, number) for number in raw_numbers)
    rule = BIG_LOTTO_RULE_CONTRACT
    if len(numbers) != rule.main_number_count:
        raise B649RawHistoryError(
            f"{strategy_id}: {key} must contain six exact integer numbers"
        )
    if any(not rule.main_number_min <= number <= rule.main_number_max for number in numbers):
        raise B649RawHistoryError(f"{strategy_id}: {key} contains an out-of-range number")
    if len(set(numbers)) != len(numbers) or numbers != tuple(sorted(numbers)):
        raise B649RawHistoryError(f"{strategy_id}: {key} must be canonical and unique")
    return numbers


def _biglotto_special(value: object, key: str, strategy_id: str) -> int:
    if type(value) is not int:
        raise B649RawHistoryError(f"{strategy_id}: {key} must be an exact integer")
    rule = BIG_LOTTO_RULE_CONTRACT
    if not rule.special_number_min <= value <= rule.special_number_max:
        raise B649RawHistoryError(f"{strategy_id}: {key} is out of range")
    return value


class B649HistoricalReplayUseCase:
    """Resolve the full B649 universe and run selected identities lazily."""

    def __init__(
        self,
        raw_history_root: Path | str,
        *,
        production: StrategyCatalog | None = None,
        full_catalog: FullStrategyCatalog | None = None,
    ) -> None:
        self._raw_source = B649RawHistorySource(raw_history_root)
        self._production = production or production_catalog()
        self._full_catalog = full_catalog or load_full_strategy_catalog()
        self._full_by_id = {
            record.strategy_id: record for record in self._full_catalog.records
        }
        self._current_by_id = self._resolve_current_catalog()
        self._identities = self._build_identity_accounts()

    @property
    def identity_accounts(self) -> tuple[B649IdentityAccount, ...]:
        return self._identities

    def execute(
        self,
        request: B649HistoricalReplayRequest,
    ) -> B649HistoricalReplayResult:
        """Return a lazy run for one identity or the complete canonical universe."""

        selected = self._select_identities(request.strategy_id)
        selected_ids = tuple(identity.strategy_id for identity in selected)
        return B649HistoricalReplayResult(
            mode=request.mode,
            identities=self._identities,
            selected_strategy_ids=selected_ids,
            _result_factory=lambda: self._iter_results(request, selected),
        )

    def _iter_results(
        self,
        request: B649HistoricalReplayRequest,
        selected: tuple[B649IdentityAccount, ...],
    ) -> Iterator[B649StrategyReplayResult]:
        for identity in selected:
            if identity.status not in (
                B649IdentityStatus.CURRENTLY_REPLAYABLE,
                B649IdentityStatus.HISTORICAL_RAW_ONLY,
            ):
                yield B649StrategyReplayResult(
                    identity=identity,
                    replay=None,
                    blocked_reason=identity.reason or identity.status.value,
                )
                continue

            try:
                binding = self._binding_for(identity)
                adapter = BigLottoReplayAdapter((binding,))
                replay_request = HistoricalReplayRequest(
                    lottery_type=LotteryType.BIG_LOTTO,
                    mode=request.mode,
                    source=request.source,
                    strategies=(binding.strategy,),
                    cutoff_draw_number=request.cutoff_draw_number,
                )
                replay = HistoricalReplayController(adapter).execute(replay_request)
            except Exception as exc:  # Every unavailable producer remains explicit.
                yield B649StrategyReplayResult(
                    identity=identity,
                    replay=None,
                    blocked_reason=(
                        f"REPLAY_BINDING_FAILED: {type(exc).__name__}: "
                        f"{_short_message(exc)}"
                    ),
                )
                continue
            yield B649StrategyReplayResult(identity=identity, replay=replay)

    def _select_identities(self, strategy_id: str | None) -> tuple[B649IdentityAccount, ...]:
        if strategy_id is None:
            return self._identities
        if strategy_id not in self._full_by_id:
            raise B649ReplayContractError(
                f"{strategy_id}: selector must name one of the "
                f"{len(self._full_catalog.records)} canonical identities"
            )
        return tuple(
            identity for identity in self._identities if identity.strategy_id == strategy_id
        )

    def _resolve_current_catalog(self) -> dict[str, StrategyDescriptor]:
        resolved: dict[str, StrategyDescriptor] = {}
        for descriptor in self._production.list(lottery_type=LotteryType.BIG_LOTTO):
            full_ids = tuple(
                provenance.split(":", 1)[1]
                for provenance in descriptor.provenance
                if provenance.startswith("full_strategy_catalog_id:")
            )
            if len(full_ids) != 1:
                continue
            full_id = full_ids[0]
            if full_id != descriptor.strategy_id or full_id not in self._full_by_id:
                continue
            if full_id in resolved:
                raise B649ReplayContractError(f"duplicate current mapping for {full_id}")
            resolved[full_id] = descriptor
        return resolved

    def _build_identity_accounts(self) -> tuple[B649IdentityAccount, ...]:
        accounts: list[B649IdentityAccount] = []
        for record in self._full_catalog.records:
            if record.reproduction_status is ReproductionStatus.DUPLICATE_ALIAS:
                target = record.duplicate_alias_target
                if target is None:
                    raise B649ReplayContractError(
                        f"{record.strategy_id}: duplicate alias has no canonical target"
                    )
                if target in self._full_by_id:
                    status = B649IdentityStatus.RESOLVED_ALIAS
                    reason = f"RESOLVED_CANONICAL_ALIAS:{target}"
                else:
                    status = B649IdentityStatus.KEEP_UNRESOLVED_ALIAS
                    reason = f"OWNER_KEEP_UNRESOLVED:{target}"
                accounts.append(
                    B649IdentityAccount(
                        strategy_id=record.strategy_id,
                        status=status,
                        strategy_version=record.strategy_version,
                        canonical_strategy_id=target,
                        reason=reason,
                    )
                )
                continue

            if record.strategy_id in self._current_by_id:
                accounts.append(
                    B649IdentityAccount(
                        strategy_id=record.strategy_id,
                        status=B649IdentityStatus.CURRENTLY_REPLAYABLE,
                        strategy_version=record.strategy_version,
                        reason="CURRENT_PRODUCTION_ADAPTER",
                    )
                )
                continue

            if (
                record.reproduction_status is ReproductionStatus.BACKTESTED
                and self._raw_source.has_raw_history(record.strategy_id)
            ):
                accounts.append(
                    B649IdentityAccount(
                        strategy_id=record.strategy_id,
                        status=B649IdentityStatus.HISTORICAL_RAW_ONLY,
                        strategy_version=record.strategy_version,
                        raw_history_available=True,
                        reason="PRESERVED_RAW_HISTORY",
                    )
                )
                continue

            accounts.append(
                B649IdentityAccount(
                    strategy_id=record.strategy_id,
                    status=B649IdentityStatus.TERMINAL_UNAVAILABLE,
                    strategy_version=record.strategy_version,
                    reason=_terminal_reason(record),
                )
            )
        return tuple(accounts)

    def _binding_for(self, identity: B649IdentityAccount) -> ReplayStrategyBinding:
        record = self._full_by_id[identity.strategy_id]
        if identity.status is B649IdentityStatus.HISTORICAL_RAW_ONLY:
            implementation = self._raw_source.implementation(
                identity.strategy_id,
                record.strategy_version,
            )
            strategy = ReplayStrategy(
                strategy_id=record.strategy_id,
                strategy_name=record.legacy_method_id,
                strategy_version=record.strategy_version,
                behavior=ReplayBehavior.DETERMINISTIC,
                native_ticket_count=self._raw_source.native_ticket_count_hint(
                    record.strategy_id
                ),
                min_history=0,
                fingerprint=record.source_sha256,
                seed_contract=record.native_ticket_semantics,
            )
            return ReplayStrategyBinding(strategy=strategy, implementation=implementation)

        descriptor = self._current_descriptor(identity.strategy_id)
        registry = ExecutableRegistry(self._production)
        adapter_class = registry.load_adapter(descriptor.strategy_id)
        if descriptor.response_shape is ResponseShape.SINGLE_TICKET:
            implementation = instantiate_adapter(descriptor.strategy_id, adapter_class)
        else:
            implementation = instantiate_portfolio_adapter(
                descriptor.strategy_id,
                adapter_class,
            )
        actual_identity = (
            getattr(implementation, "strategy_id", None),
            getattr(implementation, "strategy_name", None),
            getattr(implementation, "strategy_version", None),
        )
        expected_identity = (
            descriptor.strategy_id,
            descriptor.strategy_name,
            descriptor.version,
        )
        if actual_identity != expected_identity:
            raise B649ReplayContractError(
                f"{descriptor.strategy_id}: current adapter identity does not match catalog"
            )
        if descriptor.response_shape is ResponseShape.PORTFOLIO and getattr(
            implementation, "native_ticket_count", None
        ) != descriptor.native_ticket_count:
            raise B649ReplayContractError(
                f"{descriptor.strategy_id}: current native count does not match catalog"
            )
        strategy = ReplayStrategy(
            strategy_id=descriptor.strategy_id,
            strategy_name=descriptor.strategy_name,
            strategy_version=descriptor.version,
            behavior=ReplayBehavior.DETERMINISTIC,
            native_ticket_count=descriptor.native_ticket_count,
            min_history=descriptor.min_history,
            fingerprint=_descriptor_fingerprint(descriptor),
        )
        return ReplayStrategyBinding(strategy=strategy, implementation=implementation)

    def _current_descriptor(self, strategy_id: str) -> StrategyDescriptor:
        try:
            return self._current_by_id[strategy_id]
        except KeyError as exc:
            raise B649ReplayContractError(
                f"{strategy_id}: no current production descriptor is bound"
            ) from exc


def _terminal_reason(record: FullStrategyCatalogRecord) -> str:
    if record.reproduction_status is ReproductionStatus.CLOSED_UNEXECUTABLE:
        return f"CLOSED_UNEXECUTABLE:{record.status_reason}"
    if record.reproduction_status is ReproductionStatus.OWNER_DECISION_REQUIRED:
        return f"OWNER_DECISION_REQUIRED:{record.status_reason}"
    return "RAW_HISTORY_NOT_AVAILABLE_FOR_REPLAY"


def _descriptor_fingerprint(descriptor: StrategyDescriptor) -> str:
    payload = {
        "strategy_id": descriptor.strategy_id,
        "version": descriptor.version,
        "provenance": descriptor.provenance,
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _short_message(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    return message[:240] if message else "no detail"


__all__ = [
    "B649HistoricalReplayRequest",
    "B649HistoricalReplayResult",
    "B649HistoricalReplayUseCase",
    "B649IdentityAccount",
    "B649IdentityStatus",
    "B649RawHistoryClosure",
    "B649RawHistoryError",
    "B649RawHistorySource",
    "B649ReplayContractError",
    "B649StrategyReplayResult",
]
