"""Materialize deterministic pre-outcome B649 K5/K10/K20 portfolios.

A portfolio pools the same eleven PRE_DRAW strategy predictions the canonical
forecast (Authority B) consumes, but is a distinct authority with its own
lifecycle: Authority B publishes one consensus ticket, this module publishes
three nested bettable ticket sets. The two must never gate each other -- see
``materialize_predraw_portfolios`` in ``tools/b649_goalc_local_scheduler.py``.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, Literal, cast
from uuid import uuid4

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    build_portfolio,
)
from lottolab.evidence.canonical_json import (
    canonical_file_bytes,
    loads_canonical,
    sha256_hex,
)

PORTFOLIO_SCHEMA_VERSION: Final = "b649-operational-portfolio-v1"
PORTFOLIO_METHOD_ID: Final = "B649_OPERATIONAL_PORTFOLIO_SELECTOR"
PORTFOLIO_METHOD_VERSION: Final = "1.0.0"
PORTFOLIO_FILENAME: Final = "final_portfolio_payload.json"
UPSTREAM_TASK_ID: Final = "B649_OPERATIONAL_PREDICTION_LOOP_R1"
TASK_ID: Final = "B649_OPERATIONAL_PORTFOLIO_AUTOMATION_R1"
LOTTERY_TYPE: Final = "BIG_LOTTO"
BUCKET_SIZES: Final = (5, 10, 20)
_FORBIDDEN_KEYS = frozenset(
    {
        "outcome",
        "result",
        "score",
        "official_outcome",
        "winning_numbers",
        "main_numbers",
        "special_number",
    }
)


class PortfolioMaterializationError(RuntimeError):
    """The requested pre-outcome portfolio cannot be materialized safely."""


class PortfolioAuthorityConflictError(PortfolioMaterializationError):
    """An existing portfolio authority fails intrinsic validation or conflicts."""


@dataclass(frozen=True, slots=True)
class PersistedPortfolioCandidate:
    """One already-validated PRE_DRAW prediction, reused without a second scan.

    Callers (the scheduler) already read and validated this record while
    building the prediction inventory; this module never reopens the source
    file itself.
    """

    strategy_id: str
    source_relative_path: str
    raw_bytes: bytes
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _CandidateRecord:
    strategy_id: str
    strategy_version: str
    prediction_run_id: str
    prediction_created_at: str
    native_ticket_count: int
    history_cutoff: dict[str, str]
    history_draw_count: int
    history_sha256: str
    history_caveat: str
    source_relative_path: str
    source_sha256: str
    candidate: StrategyCandidate


@dataclass(frozen=True, slots=True)
class PortfolioMaterializationResult:
    """Observed publication state and the canonical portfolio payload."""

    status: Literal["CREATED", "ALREADY_PRESENT", "NOT_CREATED_AFTER_OUTCOME"]
    destination: Path
    payload: dict[str, object]

    def health_dict(self) -> dict[str, object]:
        payload = self.payload
        return {
            "status": self.status,
            "target_draw": payload["target_draw"],
            "cutoff_draw": payload["cutoff_draw"],
            "portfolio_status": payload["portfolio_status"],
            "k5_status": payload["k5_status"],
            "k10_status": payload["k10_status"],
            "k20_status": payload["k20_status"],
            "portfolio_authority_locator": payload["portfolio_authority_locator"],
            "outcome_used": payload["outcome_used"],
            "candidate_count": payload["candidate_count"],
            "k5": payload["k5"],
            "k10": payload["k10"],
            "k20": payload["k20"],
        }


def default_portfolio_destination(operation_root: Path, target_draw_number: str) -> Path:
    """Return the established target forecast sibling for the portfolio."""

    return (
        operation_root
        / "forecasts"
        / target_draw_number
        / PORTFOLIO_METHOD_ID
        / PORTFOLIO_METHOD_VERSION
        / PORTFOLIO_FILENAME
    )


def read_portfolio_if_present(destination: Path) -> PortfolioMaterializationResult | None:
    """Read and intrinsically validate an existing portfolio; never creates one.

    This is the only capability the post-outcome path may use: it has no
    branch that stages, publishes, or otherwise mutates ``destination``.
    """

    raw = _read_existing_bytes(destination)
    if raw is None:
        return None
    payload = _parse_and_validate_existing(raw, destination)
    return PortfolioMaterializationResult("ALREADY_PRESENT", destination, payload)


def materialize_portfolios(
    *,
    candidates: Sequence[PersistedPortfolioCandidate],
    expected_strategy_ids: Sequence[str],
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str,
    destination: Path,
    quality_by_strategy: Mapping[str, float] | None = None,
    pre_outcome_seal_check: Callable[[], bool] | None = None,
) -> PortfolioMaterializationResult:
    """Read already-validated PRE_DRAW candidates and publish one immutable portfolio.

    An existing authority is always read, intrinsically validated, and reused
    -- it is never rebuilt from ``candidates`` and byte-compared. Only when no
    authority exists yet does this function evaluate the pre-outcome boundary
    and attempt one atomic first creation.
    """

    _require_identifier(target_draw_number, "target_draw_number")
    _require_text(target_draw_date, "target_draw_date")
    _require_text(scheduled_at, "scheduled_at")
    _require_absolute_path(destination, "destination")

    expected = tuple(expected_strategy_ids)
    if not expected or len(set(expected)) != len(expected):
        raise PortfolioMaterializationError("expected strategy ids must be non-empty and unique")

    existing = read_portfolio_if_present(destination)
    if existing is not None:
        target = cast(Mapping[str, object], existing.payload["target_draw"])
        if target.get("draw_number") != target_draw_number or target.get(
            "draw_date"
        ) != target_draw_date:
            raise PortfolioAuthorityConflictError(
                "existing portfolio authority targets a different draw"
            )
        return existing

    scheduled_at_value = _parse_aware_datetime(scheduled_at, "scheduled_at")
    seal_check = (
        pre_outcome_seal_check
        if pre_outcome_seal_check is not None
        else lambda: datetime.now(UTC) < scheduled_at_value
    )

    if not _check_pre_outcome_boundary(seal_check):
        return _not_created_after_outcome(
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date,
            destination=destination,
        )

    payload, payload_bytes = _build_payload(
        candidates=candidates,
        expected_strategy_ids=expected,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        scheduled_at=scheduled_at,
        destination=destination,
        quality_by_strategy=quality_by_strategy,
    )

    staged: _StagedPayload | None = None
    try:
        staged = _stage_payload(destination, payload_bytes)
        publish_status = _publish_staged(staged, seal_check)
        if publish_status == "NOT_CREATED_AFTER_OUTCOME":
            return _not_created_after_outcome(
                target_draw_number=target_draw_number,
                target_draw_date=target_draw_date,
                destination=destination,
            )
        if publish_status == "ALREADY_PRESENT":
            observed = read_portfolio_if_present(destination)
            if observed is None:
                raise PortfolioAuthorityConflictError(
                    "competing portfolio authority vanished after publish race"
                )
            return observed
        return PortfolioMaterializationResult("CREATED", destination, payload)
    finally:
        if staged is not None and staged.temporary.exists():
            with suppress(OSError):
                staged.temporary.unlink()


def _build_payload(
    *,
    candidates: Sequence[PersistedPortfolioCandidate],
    expected_strategy_ids: Sequence[str],
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str,
    destination: Path,
    quality_by_strategy: Mapping[str, float] | None,
) -> tuple[dict[str, object], bytes]:
    records = _load_candidates(
        candidates,
        expected_strategy_ids=expected_strategy_ids,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        scheduled_at=scheduled_at,
    )
    if tuple(record.strategy_id for record in records) != tuple(sorted(expected_strategy_ids)):
        raise PortfolioMaterializationError("candidate strategy set does not match the registry")

    cutoff = records[0].history_cutoff
    history_sha256 = records[0].history_sha256
    history_draw_count = records[0].history_draw_count
    history_caveat = records[0].history_caveat
    if any(
        record.history_cutoff != cutoff
        or record.history_sha256 != history_sha256
        or record.history_draw_count != history_draw_count
        or record.history_caveat != history_caveat
        for record in records
    ):
        raise PortfolioMaterializationError("candidate pre-outcome provenance disagrees")

    try:
        buckets = build_portfolio(
            tuple(record.candidate for record in records),
            {} if quality_by_strategy is None else quality_by_strategy,
            bucket_sizes=BUCKET_SIZES,
        )
    except ValueError as exc:
        raise PortfolioMaterializationError(str(exc)) from exc
    _validate_buckets(buckets)
    payload = _payload(
        records,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        scheduled_at=scheduled_at,
        cutoff=cutoff,
        history_sha256=history_sha256,
        history_draw_count=history_draw_count,
        history_caveat=history_caveat,
        destination=destination,
        buckets=buckets,
    )
    return payload, canonical_file_bytes(payload)


def _check_pre_outcome_boundary(check: Callable[[], bool]) -> bool:
    try:
        allowed = check()
    except PortfolioMaterializationError:
        raise
    except Exception as exc:
        raise PortfolioMaterializationError(
            "pre-outcome authority check failed closed"
        ) from exc
    if type(allowed) is not bool:
        raise PortfolioMaterializationError(
            "pre-outcome authority check must return an exact bool"
        )
    return allowed


def _not_created_after_outcome(
    *,
    target_draw_number: str,
    target_draw_date: str,
    destination: Path,
) -> PortfolioMaterializationResult:
    payload = _empty_payload(
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        scheduled_at=None,
        destination=destination,
        status="NOT_CREATED_AFTER_OUTCOME",
    )
    return PortfolioMaterializationResult("NOT_CREATED_AFTER_OUTCOME", destination, payload)


def _empty_payload(
    *,
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str | None,
    destination: Path,
    status: str,
) -> dict[str, object]:
    return {
        "schema_version": PORTFOLIO_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "upstream_task_id": UPSTREAM_TASK_ID,
        "lottery_type": LOTTERY_TYPE,
        "portfolio_method_id": PORTFOLIO_METHOD_ID,
        "portfolio_method_version": PORTFOLIO_METHOD_VERSION,
        "target_draw": {
            "draw_number": target_draw_number,
            "draw_date": target_draw_date,
        },
        "scheduled_at": scheduled_at,
        "cutoff_draw": None,
        "history_sha256": None,
        "history_draw_count": None,
        "history_caveat": None,
        "portfolio_authority_locator": str(destination),
        "portfolio_status": status,
        "k5_status": status,
        "k10_status": status,
        "k20_status": status,
        "outcome_used": "NO",
        "target_result_used": False,
        "candidate_count": 0,
        "candidate_manifest": [],
        "k5": [],
        "k10": [],
        "k20": [],
    }


def _load_candidates(
    candidates: Sequence[PersistedPortfolioCandidate],
    *,
    expected_strategy_ids: Sequence[str],
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str,
) -> tuple[_CandidateRecord, ...]:
    records: dict[str, _CandidateRecord] = {}
    expected = frozenset(expected_strategy_ids)
    scheduled_at_value = _parse_aware_datetime(scheduled_at, "scheduled_at")
    for candidate in candidates:
        value = candidate.payload
        label = candidate.source_relative_path
        _reject_forbidden_keys(value, label)
        if value.get("schema_version") != "b649-operational-prediction-v1":
            raise PortfolioMaterializationError(f"{label}: prediction schema is not canonical")
        if value.get("task_id") != UPSTREAM_TASK_ID:
            raise PortfolioMaterializationError(f"{label}: prediction task is not canonical")
        if value.get("lottery_type") != LOTTERY_TYPE:
            raise PortfolioMaterializationError(f"{label}: lottery type conflicts")
        if value.get("draw_number") != target_draw_number:
            raise PortfolioMaterializationError(f"{label}: target draw conflicts")
        if value.get("draw_date") != target_draw_date:
            raise PortfolioMaterializationError(f"{label}: target draw date conflicts")
        if value.get("scheduled_at") != scheduled_at:
            raise PortfolioMaterializationError(f"{label}: target schedule conflicts")
        if value.get("prediction_temporal_class") != "PRE_DRAW":
            raise PortfolioMaterializationError(f"{label}: candidate is not PRE_DRAW")
        if value.get("availability", "AVAILABLE") != "AVAILABLE":
            raise PortfolioMaterializationError(f"{label}: candidate is not available")
        if candidate.strategy_id != value.get("strategy_id"):
            raise PortfolioMaterializationError(f"{label}: strategy identity conflicts")

        strategy_id = _required_text(value, "strategy_id", label)
        if strategy_id not in expected:
            raise PortfolioMaterializationError(f"{label}: strategy is outside the registry")
        if strategy_id in records:
            raise PortfolioMaterializationError(f"{label}: multiple candidates for {strategy_id}")
        strategy_version = _required_text(value, "strategy_version", label)
        run_id = _required_text(value, "prediction_run_id", label)
        created_at = _required_text(value, "prediction_created_at", label)
        created_at_value = _parse_aware_datetime(created_at, f"{label}.prediction_created_at")
        if created_at_value >= scheduled_at_value:
            raise PortfolioMaterializationError(f"{label}: prediction was not created before draw")
        native_count = _required_int(value, "native_ticket_count", label)
        tickets = _read_tickets(value, label, native_count)
        cutoff = _read_cutoff(value, label)
        _validate_cutoff(cutoff, target_draw_number, target_draw_date, label)
        history_draw_count = _required_int(value, "history_draw_count", label)
        history_sha256 = _required_digest(value, "history_sha256", label)
        history_caveat = _required_text(value, "history_caveat", label)
        records[strategy_id] = _CandidateRecord(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            prediction_run_id=run_id,
            prediction_created_at=created_at,
            native_ticket_count=native_count,
            history_cutoff=cutoff,
            history_draw_count=history_draw_count,
            history_sha256=history_sha256,
            history_caveat=history_caveat,
            source_relative_path=label,
            source_sha256=sha256_hex(candidate.raw_bytes),
            candidate=StrategyCandidate(strategy_id, tickets),
        )

    missing = [strategy_id for strategy_id in expected_strategy_ids if strategy_id not in records]
    if missing:
        raise PortfolioMaterializationError(f"missing usable PRE_DRAW candidates: {missing}")
    return tuple(records[strategy_id] for strategy_id in sorted(records))


def _payload(
    records: Sequence[_CandidateRecord],
    *,
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str,
    cutoff: dict[str, str],
    history_sha256: str,
    history_draw_count: int,
    history_caveat: str,
    destination: Path,
    buckets: Mapping[int, Sequence[tuple[int, ...]]],
) -> dict[str, object]:
    return {
        "schema_version": PORTFOLIO_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "upstream_task_id": UPSTREAM_TASK_ID,
        "lottery_type": LOTTERY_TYPE,
        "portfolio_method_id": PORTFOLIO_METHOD_ID,
        "portfolio_method_version": PORTFOLIO_METHOD_VERSION,
        "target_draw": {
            "draw_number": target_draw_number,
            "draw_date": target_draw_date,
        },
        "scheduled_at": scheduled_at,
        "cutoff_draw": cutoff,
        "history_sha256": history_sha256,
        "history_draw_count": history_draw_count,
        "history_caveat": history_caveat,
        "portfolio_authority_locator": str(destination),
        "portfolio_status": "COMPLETE",
        "k5_status": "COMPLETE",
        "k10_status": "COMPLETE",
        "k20_status": "COMPLETE",
        "outcome_used": "NO",
        "target_result_used": False,
        "candidate_count": len(records),
        "candidate_manifest": [
            {
                "strategy_id": record.strategy_id,
                "strategy_version": record.strategy_version,
                "prediction_run_id": record.prediction_run_id,
                "prediction_created_at": record.prediction_created_at,
                "native_ticket_count": record.native_ticket_count,
                "prediction_path": record.source_relative_path,
                "prediction_sha256": record.source_sha256,
            }
            for record in records
        ],
        "k5": _tickets_payload(buckets[5]),
        "k10": _tickets_payload(buckets[10]),
        "k20": _tickets_payload(buckets[20]),
    }


def _tickets_payload(tickets: Sequence[tuple[int, ...]]) -> list[dict[str, object]]:
    return [
        {"ticket_position": position, "predicted_numbers": list(ticket)}
        for position, ticket in enumerate(tickets, start=1)
    ]


def _validate_buckets(buckets: Mapping[int, Sequence[tuple[int, ...]]]) -> None:
    if tuple(sorted(buckets)) != BUCKET_SIZES:
        raise PortfolioMaterializationError("selector did not return exactly K5/K10/K20")
    prior: tuple[tuple[int, ...], ...] = ()
    for size in BUCKET_SIZES:
        current = tuple(buckets[size])
        if len(current) != size or len(set(current)) != size:
            raise PortfolioMaterializationError(f"K{size} has invalid cardinality or duplicates")
        if prior and current[: len(prior)] != prior:
            raise PortfolioMaterializationError("K-buckets are not nested prefixes")
        prior = current


def _validate_ticket_rows(rows: object, label: str) -> None:
    if not isinstance(rows, list):
        raise PortfolioAuthorityConflictError(f"{label}: bucket is not a list")
    row_list = cast(list[object], rows)
    for position, item in enumerate(row_list, start=1):
        if not isinstance(item, dict):
            raise PortfolioAuthorityConflictError(f"{label}: ticket row is not an object")
        row = cast(Mapping[str, object], item)
        if row.get("ticket_position") != position:
            raise PortfolioAuthorityConflictError(f"{label}: ticket positions are not contiguous")
        numbers = row.get("predicted_numbers")
        if not isinstance(numbers, list):
            raise PortfolioAuthorityConflictError(f"{label}: ticket is not six integers")
        number_values = cast(list[object], numbers)
        if (
            len(number_values) != 6
            or any(type(number) is not int or not 1 <= number <= 49 for number in number_values)
            or len(set(number_values)) != 6
        ):
            raise PortfolioAuthorityConflictError(f"{label}: ticket contains illegal numbers")


def _read_tickets(
    value: Mapping[str, object],
    label: str,
    expected_count: int,
) -> tuple[tuple[int, ...], ...]:
    raw = value.get("tickets")
    if not isinstance(raw, list):
        raise PortfolioMaterializationError(
            f"{label}: ticket count does not match native_ticket_count"
        )
    raw_tickets = cast(list[object], raw)
    if len(raw_tickets) != expected_count:
        raise PortfolioMaterializationError(
            f"{label}: ticket count does not match native_ticket_count"
        )
    tickets: list[tuple[int, ...]] = []
    for position, item in enumerate(raw_tickets, start=1):
        if not isinstance(item, dict):
            raise PortfolioMaterializationError(f"{label}: ticket row is not an object")
        row = cast(Mapping[str, object], item)
        if row.get("ticket_position") != position:
            raise PortfolioMaterializationError(f"{label}: ticket positions are not contiguous")
        numbers = row.get("predicted_numbers")
        if not isinstance(numbers, list):
            raise PortfolioMaterializationError(f"{label}: ticket is not six integers")
        number_values = cast(list[object], numbers)
        if len(number_values) != 6:
            raise PortfolioMaterializationError(f"{label}: ticket is not six integers")
        if any(type(number) is not int or not 1 <= number <= 49 for number in number_values):
            raise PortfolioMaterializationError(f"{label}: ticket contains illegal numbers")
        ticket = tuple(cast(list[int], number_values))
        if len(set(ticket)) != 6:
            raise PortfolioMaterializationError(f"{label}: ticket contains duplicate numbers")
        tickets.append(ticket)
    return tuple(tickets)


def _read_cutoff(value: Mapping[str, object], label: str) -> dict[str, str]:
    raw = value.get("history_cutoff")
    if not isinstance(raw, dict):
        raise PortfolioMaterializationError(f"{label}: history_cutoff is missing")
    mapping = cast(Mapping[str, object], raw)
    draw_number = mapping.get("draw_number")
    draw_date = mapping.get("draw_date")
    if (
        type(draw_number) is not str
        or not draw_number
        or type(draw_date) is not str
        or not draw_date
    ):
        raise PortfolioMaterializationError(f"{label}: history_cutoff is invalid")
    return {"draw_number": draw_number, "draw_date": draw_date}


def _validate_cutoff(
    cutoff: Mapping[str, str],
    target_draw_number: str,
    target_draw_date: str,
    label: str,
) -> None:
    try:
        cutoff_key = (date.fromisoformat(cutoff["draw_date"]), int(cutoff["draw_number"]))
        target_key = (date.fromisoformat(target_draw_date), int(target_draw_number))
    except ValueError as exc:
        raise PortfolioMaterializationError(
            f"{label}: cutoff or target identity is invalid"
        ) from exc
    if cutoff_key >= target_key:
        raise PortfolioMaterializationError(f"{label}: history cutoff must precede target draw")


def _parse_and_validate_existing(raw: bytes, destination: Path) -> dict[str, object]:
    try:
        parsed = loads_canonical(raw)
    except Exception as exc:
        raise PortfolioAuthorityConflictError(
            f"existing portfolio authority is not valid canonical JSON: {destination}"
        ) from exc
    if not isinstance(parsed, dict):
        raise PortfolioAuthorityConflictError(
            f"existing portfolio authority is not one JSON object: {destination}"
        )
    payload = cast(dict[str, object], parsed)
    label = str(destination)
    if payload.get("schema_version") != PORTFOLIO_SCHEMA_VERSION:
        raise PortfolioAuthorityConflictError(
            f"{label}: existing authority schema is not canonical"
        )
    if payload.get("task_id") != TASK_ID:
        raise PortfolioAuthorityConflictError(f"{label}: existing authority task is not canonical")
    if payload.get("portfolio_authority_locator") != label:
        raise PortfolioAuthorityConflictError(f"{label}: existing authority locator conflicts")
    if payload.get("portfolio_status") != "COMPLETE":
        raise PortfolioAuthorityConflictError(f"{label}: existing authority is not COMPLETE")
    target = payload.get("target_draw")
    if not isinstance(target, dict):
        raise PortfolioAuthorityConflictError(f"{label}: existing authority target is invalid")
    _validate_ticket_rows(payload.get("k5"), f"{label}:k5")
    _validate_ticket_rows(payload.get("k10"), f"{label}:k10")
    _validate_ticket_rows(payload.get("k20"), f"{label}:k20")
    buckets = {
        5: tuple(
            tuple(cast(list[int], cast(dict[str, object], row)["predicted_numbers"]))
            for row in cast(list[object], payload["k5"])
        ),
        10: tuple(
            tuple(cast(list[int], cast(dict[str, object], row)["predicted_numbers"]))
            for row in cast(list[object], payload["k10"])
        ),
        20: tuple(
            tuple(cast(list[int], cast(dict[str, object], row)["predicted_numbers"]))
            for row in cast(list[object], payload["k20"])
        ),
    }
    try:
        _validate_buckets(buckets)
    except PortfolioMaterializationError as exc:
        raise PortfolioAuthorityConflictError(str(exc)) from exc
    return payload


def _reject_forbidden_keys(value: object, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in cast(Mapping[str, object], value).items():
            if key in _FORBIDDEN_KEYS:
                raise PortfolioMaterializationError(
                    f"{label}: outcome/scoring key is forbidden: {key}"
                )
            _reject_forbidden_keys(item, label)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _reject_forbidden_keys(item, label)


def _required_text(value: Mapping[str, object], key: str, label: str) -> str:
    item = value.get(key)
    if type(item) is not str or not item.strip():
        raise PortfolioMaterializationError(f"{label}: {key} must be non-empty text")
    return item


def _required_int(value: Mapping[str, object], key: str, label: str) -> int:
    item = value.get(key)
    if type(item) is not int or item < 1:
        raise PortfolioMaterializationError(f"{label}: {key} must be a positive integer")
    return item


def _required_digest(value: Mapping[str, object], key: str, label: str) -> str:
    item = _required_text(value, key, label)
    if len(item) != 64 or any(char not in "0123456789abcdef" for char in item):
        raise PortfolioMaterializationError(f"{label}: {key} must be a lowercase SHA-256 digest")
    return item


def _require_identifier(value: str, label: str) -> None:
    if type(value) is not str or not value or not all(
        char.isalnum() or char in "_.-" for char in value
    ):
        raise PortfolioMaterializationError(f"{label} is not canonical")


def _require_text(value: str, label: str) -> None:
    if type(value) is not str or not value.strip():
        raise PortfolioMaterializationError(f"{label} must be non-empty text")


def _require_absolute_path(value: Path, label: str) -> None:
    if not value.is_absolute():
        raise PortfolioMaterializationError(f"{label} must be absolute")


def _parse_aware_datetime(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PortfolioMaterializationError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortfolioMaterializationError(f"{label} must be timezone-aware")
    return parsed


_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_ODIRECTORY = getattr(os, "O_DIRECTORY", 0)
_CREATED_MODE = 0o700
_FILE_MODE = 0o600


@dataclass(frozen=True, slots=True)
class _StagedPayload:
    destination: Path
    temporary: Path
    payload_bytes: bytes


def _validate_destination_shape(destination: Path) -> None:
    if not destination.is_absolute():
        raise PortfolioMaterializationError("destination must be an absolute Path")
    if destination == Path(destination.anchor):
        raise PortfolioMaterializationError("filesystem root is not a valid authority")
    if any(part in {"", ".", "..", ".git"} for part in destination.parts):
        raise PortfolioMaterializationError("destination contains a forbidden path component")


def _ensure_directory_chain(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            try:
                os.mkdir(current, _CREATED_MODE)
            except FileExistsError:
                metadata = current.lstat()
            else:
                continue
        except OSError as exc:
            raise PortfolioMaterializationError("cannot inspect output directory") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise PortfolioMaterializationError("output path contains a non-directory component")


def _read_existing_bytes(destination: Path) -> bytes | None:
    _validate_destination_shape(destination)
    try:
        metadata = destination.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PortfolioMaterializationError("cannot inspect the authority path") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PortfolioMaterializationError("authority path is not an owned regular file")
    try:
        return destination.read_bytes()
    except OSError as exc:
        raise PortfolioMaterializationError("cannot read the existing authority") from exc


def _stage_payload(destination: Path, payload_bytes: bytes) -> _StagedPayload:
    _validate_destination_shape(destination)
    if type(payload_bytes) is not bytes:
        raise PortfolioMaterializationError("payload_bytes must be exact bytes")
    _ensure_directory_chain(destination.parent)
    if os.path.lexists(destination):
        raise PortfolioAuthorityConflictError("authority path appeared before staging")

    temporary = destination.parent / f".{destination.name}.{uuid4().hex}.tmp"
    descriptor: int | None = None
    staged = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW
        descriptor = os.open(temporary, flags, _FILE_MODE)
        os.fchmod(descriptor, _FILE_MODE)
        view = memoryview(payload_bytes)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise PortfolioMaterializationError("authority staging made no progress")
            offset += written
        os.fsync(descriptor)
        staged = True
        return _StagedPayload(destination, temporary, payload_bytes)
    except FileExistsError as exc:
        raise PortfolioMaterializationError("temporary staging name unexpectedly collided") from exc
    except OSError as exc:
        raise PortfolioMaterializationError("cannot stage portfolio authority safely") from exc
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        if not staged:
            with suppress(OSError):
                temporary.unlink()


def _publish_staged(
    staged: _StagedPayload,
    allow_publish: Callable[[], bool],
) -> Literal["CREATED", "ALREADY_PRESENT", "NOT_CREATED_AFTER_OUTCOME"]:
    if staged.temporary.parent != staged.destination.parent:
        raise PortfolioMaterializationError("staged temporary is outside the destination parent")
    if not _check_pre_outcome_boundary(allow_publish):
        return "NOT_CREATED_AFTER_OUTCOME"
    try:
        try:
            os.link(staged.temporary, staged.destination, follow_symlinks=False)
        except FileExistsError:
            return "ALREADY_PRESENT"
        _fsync_directory(staged.destination.parent)
        return "CREATED"
    except OSError as exc:
        raise PortfolioMaterializationError("atomic authority creation failed") from exc
    finally:
        try:
            staged.temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise PortfolioMaterializationError("staged temporary cleanup failed") from exc


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | _ODIRECTORY | _NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "BUCKET_SIZES",
    "LOTTERY_TYPE",
    "PORTFOLIO_FILENAME",
    "PORTFOLIO_METHOD_ID",
    "PORTFOLIO_METHOD_VERSION",
    "PORTFOLIO_SCHEMA_VERSION",
    "TASK_ID",
    "UPSTREAM_TASK_ID",
    "PersistedPortfolioCandidate",
    "PortfolioAuthorityConflictError",
    "PortfolioMaterializationError",
    "PortfolioMaterializationResult",
    "default_portfolio_destination",
    "materialize_portfolios",
    "read_portfolio_if_present",
]
