"""Materialize deterministic pre-outcome B649 K-bucket portfolios."""

from __future__ import annotations

import json
import os
import re
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
from lottolab.evidence.canonical_json import canonical_file_bytes, sha256_hex

PORTFOLIO_SCHEMA_VERSION: Final = "b649-operational-portfolio-v1"
PORTFOLIO_METHOD_ID: Final = "B649_OPERATIONAL_PORTFOLIO_SELECTOR"
PORTFOLIO_METHOD_VERSION: Final = "1.0.0"
PORTFOLIO_FILENAME: Final = "final_portfolio_payload.json"
UPSTREAM_TASK_ID: Final = "B649_OPERATIONAL_PREDICTION_LOOP_R1"
TASK_ID: Final = "B649_OPERATIONAL_PORTFOLIO_AUTOMATION_R1"
LOTTERY_TYPE: Final = "BIG_LOTTO"
BUCKET_SIZES: Final = (5, 10, 20)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]+", flags=re.ASCII)
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
    """An existing portfolio authority differs from the deterministic payload."""


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
    source_path: Path
    source_sha256: str
    candidate: StrategyCandidate


@dataclass(frozen=True, slots=True)
class PortfolioMaterializationResult:
    """Observed publication state and the canonical portfolio payload."""

    status: Literal["CREATED", "ALREADY_PRESENT", "NOT_CREATED_AFTER_OUTCOME"]
    destination: Path
    payload: dict[str, object]

    def health_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "target_draw": self.payload["target_draw"],
            "cutoff_draw": self.payload["cutoff_draw"],
            "pre_outcome_forecast_status": self.payload["pre_outcome_forecast_status"],
            "post_outcome_scoring_status": self.payload["post_outcome_scoring_status"],
            "next_draw_rollover_status": self.payload["next_draw_rollover_status"],
            "k5_status": self.payload["k5_status"],
            "k10_status": self.payload["k10_status"],
            "k20_status": self.payload["k20_status"],
            "upstream_authority_status": self.payload.get("upstream_authority_status", "READY"),
            "upstream_authority_locator": self.payload["upstream_authority_locator"],
            "portfolio_authority_locator": self.payload["portfolio_authority_locator"],
            "outcome_used": self.payload["outcome_used"],
            "k5": self.payload["k5"],
            "k10": self.payload["k10"],
            "k20": self.payload["k20"],
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


def materialize_portfolios(
    *,
    candidate_paths: Sequence[Path],
    expected_strategy_ids: Sequence[str],
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str,
    upstream_authority_locator: str,
    destination: Path,
    quality_by_strategy: Mapping[str, float] | None = None,
    pre_outcome_seal_check: Callable[[], bool] | None = None,
) -> PortfolioMaterializationResult:
    """Read persisted PRE_DRAW candidates and publish one immutable portfolio."""

    _require_identifier(target_draw_number, "target_draw_number")
    _require_text(target_draw_date, "target_draw_date")
    _require_text(scheduled_at, "scheduled_at")
    _require_absolute_path(destination, "destination")
    if type(upstream_authority_locator) is not str or not upstream_authority_locator:
        raise PortfolioMaterializationError(
            "upstream_authority_locator must be the exact non-empty locator text"
        )
    if not Path(upstream_authority_locator).is_absolute():
        raise PortfolioMaterializationError("upstream_authority_locator must be absolute")

    expected = tuple(expected_strategy_ids)
    if not expected or len(set(expected)) != len(expected):
        raise PortfolioMaterializationError("expected strategy ids must be non-empty and unique")

    scheduled_at_value = _parse_aware_datetime(scheduled_at, "scheduled_at")
    seal_check = (
        pre_outcome_seal_check
        if pre_outcome_seal_check is not None
        else lambda: datetime.now(UTC) < scheduled_at_value
    )

    existing = _read_existing_bytes(destination)
    if existing is not None:
        payload, payload_bytes = _build_payload(
            candidate_paths=candidate_paths,
            expected_strategy_ids=expected,
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date,
            scheduled_at=scheduled_at,
            upstream_authority_locator=upstream_authority_locator,
            destination=destination,
            quality_by_strategy=quality_by_strategy,
        )
        if existing != payload_bytes:
            raise PortfolioAuthorityConflictError(
                "existing portfolio authority differs from deterministic inputs"
            )
        return PortfolioMaterializationResult("ALREADY_PRESENT", destination, payload)

    if not _check_pre_outcome_boundary(seal_check):
        return _not_created_after_outcome(
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date,
            scheduled_at=scheduled_at,
            upstream_authority_locator=upstream_authority_locator,
            destination=destination,
        )

    payload, payload_bytes = _build_payload(
        candidate_paths=candidate_paths,
        expected_strategy_ids=expected,
        target_draw_number=target_draw_number,
        target_draw_date=target_draw_date,
        scheduled_at=scheduled_at,
        upstream_authority_locator=upstream_authority_locator,
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
                scheduled_at=scheduled_at,
                upstream_authority_locator=upstream_authority_locator,
                destination=destination,
            )
        if publish_status == "ALREADY_PRESENT":
            observed = _read_existing_bytes(destination)
            if observed != payload_bytes:
                raise PortfolioAuthorityConflictError(
                    "competing portfolio authority differs from deterministic inputs"
                )
            return PortfolioMaterializationResult("ALREADY_PRESENT", destination, payload)
        observed = _read_existing_bytes(destination)
        if observed != payload_bytes:
            raise PortfolioAuthorityConflictError(
                "read-after-write portfolio authority differs from payload"
            )
        return PortfolioMaterializationResult("CREATED", destination, payload)
    finally:
        if staged is not None and staged.temporary.exists():
            with suppress(OSError):
                staged.temporary.unlink()


def _build_payload(
    *,
    candidate_paths: Sequence[Path],
    expected_strategy_ids: Sequence[str],
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str,
    upstream_authority_locator: str,
    destination: Path,
    quality_by_strategy: Mapping[str, float] | None,
) -> tuple[dict[str, object], bytes]:
    records = _load_candidates(
        candidate_paths,
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

    buckets = build_portfolio(
        tuple(record.candidate for record in records),
        {} if quality_by_strategy is None else quality_by_strategy,
        bucket_sizes=BUCKET_SIZES,
    )
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
        upstream_authority_locator=upstream_authority_locator,
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
    scheduled_at: str,
    upstream_authority_locator: str,
    destination: Path,
) -> PortfolioMaterializationResult:
    payload: dict[str, object] = {
        "schema_version": PORTFOLIO_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "target_draw": {
            "draw_number": target_draw_number,
            "draw_date": target_draw_date,
        },
        "scheduled_at": scheduled_at,
        "cutoff_draw": None,
        "upstream_authority_status": "NOT_CREATED_AFTER_OUTCOME",
        "upstream_authority_locator": upstream_authority_locator,
        "portfolio_authority_locator": str(destination),
        "pre_outcome_forecast_status": "NOT_CREATED_AFTER_OUTCOME",
        "post_outcome_scoring_status": "NOT_DUE",
        "next_draw_rollover_status": "NOT_DUE",
        "k5_status": "NOT_CREATED_AFTER_OUTCOME",
        "k10_status": "NOT_CREATED_AFTER_OUTCOME",
        "k20_status": "NOT_CREATED_AFTER_OUTCOME",
        "outcome_used": "NO",
        "target_result_used": False,
        "k5": [],
        "k10": [],
        "k20": [],
    }
    return PortfolioMaterializationResult("NOT_CREATED_AFTER_OUTCOME", destination, payload)

def _load_candidates(
    candidate_paths: Sequence[Path],
    *,
    expected_strategy_ids: Sequence[str],
    target_draw_number: str,
    target_draw_date: str,
    scheduled_at: str,
) -> tuple[_CandidateRecord, ...]:
    records: dict[str, _CandidateRecord] = {}
    expected = frozenset(expected_strategy_ids)
    for path in candidate_paths:
        raw, value = _read_json_object(path)
        _reject_forbidden_keys(value, path)
        if value.get("schema_version") != "b649-operational-prediction-v1":
            raise PortfolioMaterializationError(f"{path}: prediction schema is not canonical")
        if value.get("task_id") != UPSTREAM_TASK_ID:
            raise PortfolioMaterializationError(f"{path}: prediction task is not canonical")
        if value.get("lottery_type") != LOTTERY_TYPE:
            raise PortfolioMaterializationError(f"{path}: lottery type conflicts")
        if value.get("draw_number") != target_draw_number:
            raise PortfolioMaterializationError(f"{path}: target draw conflicts")
        if value.get("draw_date") != target_draw_date:
            raise PortfolioMaterializationError(f"{path}: target draw date conflicts")
        if value.get("scheduled_at") != scheduled_at:
            raise PortfolioMaterializationError(f"{path}: target schedule conflicts")
        if value.get("prediction_temporal_class") != "PRE_DRAW":
            raise PortfolioMaterializationError(f"{path}: candidate is not PRE_DRAW")
        if value.get("availability", "AVAILABLE") != "AVAILABLE":
            raise PortfolioMaterializationError(f"{path}: candidate is not available")
        if "unavailable_reason" in value and value["unavailable_reason"] is not None:
            raise PortfolioMaterializationError(f"{path}: available candidate has a failure reason")

        strategy_id = _required_text(value, "strategy_id", path)
        if strategy_id not in expected:
            raise PortfolioMaterializationError(f"{path}: strategy is outside the registry")
        if strategy_id in records:
            raise PortfolioMaterializationError(f"{path}: multiple candidates for {strategy_id}")
        strategy_version = _required_text(value, "strategy_version", path)
        run_id = _required_text(value, "prediction_run_id", path)
        created_at = _required_text(value, "prediction_created_at", path)
        created_at_value = _parse_aware_datetime(created_at, f"{path}.prediction_created_at")
        scheduled_at_value = _parse_aware_datetime(scheduled_at, f"{path}.scheduled_at")
        if created_at_value >= scheduled_at_value:
            raise PortfolioMaterializationError(f"{path}: prediction was not created before draw")
        native_count = _required_int(value, "native_ticket_count", path)
        tickets = _read_tickets(value, path, native_count)
        cutoff = _read_cutoff(value, path)
        _validate_cutoff(cutoff, target_draw_number, target_draw_date, path)
        history_draw_count = _required_int(value, "history_draw_count", path)
        history_sha256 = _required_digest(value, "history_sha256", path)
        history_caveat = _required_text(value, "history_caveat", path)
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
            source_path=path,
            source_sha256=sha256_hex(raw),
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
    upstream_authority_locator: str,
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
        "upstream_authority_status": "READY",
        "upstream_authority_locator": upstream_authority_locator,
        "portfolio_authority_locator": str(destination),
        "pre_outcome_forecast_status": "COMPLETE",
        "post_outcome_scoring_status": "NOT_DUE",
        "next_draw_rollover_status": "NOT_DUE",
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
                "prediction_path": str(record.source_path),
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


def _read_tickets(
    value: Mapping[str, object],
    path: Path,
    expected_count: int,
) -> tuple[tuple[int, ...], ...]:
    raw = value.get("tickets")
    if not isinstance(raw, list):
        raise PortfolioMaterializationError(
            f"{path}: ticket count does not match native_ticket_count"
        )
    raw_tickets = cast(list[object], raw)
    if len(raw_tickets) != expected_count:
        raise PortfolioMaterializationError(
            f"{path}: ticket count does not match native_ticket_count"
        )
    tickets: list[tuple[int, ...]] = []
    for position, item in enumerate(raw_tickets, start=1):
        if not isinstance(item, dict):
            raise PortfolioMaterializationError(f"{path}: ticket row is not an object")
        row = cast(Mapping[str, object], item)
        if row.get("ticket_position") != position:
            raise PortfolioMaterializationError(f"{path}: ticket positions are not contiguous")
        numbers = row.get("predicted_numbers")
        if not isinstance(numbers, list):
            raise PortfolioMaterializationError(f"{path}: ticket is not six integers")
        number_values = cast(list[object], numbers)
        if len(number_values) != 6:
            raise PortfolioMaterializationError(f"{path}: ticket is not six integers")
        if any(type(number) is not int or not 1 <= number <= 49 for number in number_values):
            raise PortfolioMaterializationError(f"{path}: ticket contains illegal numbers")
        ticket = tuple(cast(list[int], number_values))
        if len(set(ticket)) != 6:
            raise PortfolioMaterializationError(f"{path}: ticket contains duplicate numbers")
        tickets.append(ticket)
    return tuple(tickets)


def _read_cutoff(value: Mapping[str, object], path: Path) -> dict[str, str]:
    raw = value.get("history_cutoff")
    if not isinstance(raw, dict):
        raise PortfolioMaterializationError(f"{path}: history_cutoff is missing")
    mapping = cast(Mapping[str, object], raw)
    draw_number = mapping.get("draw_number")
    draw_date = mapping.get("draw_date")
    if (
        type(draw_number) is not str
        or not draw_number
        or type(draw_date) is not str
        or not draw_date
    ):
        raise PortfolioMaterializationError(f"{path}: history_cutoff is invalid")
    return {"draw_number": draw_number, "draw_date": draw_date}


def _validate_cutoff(
    cutoff: Mapping[str, str],
    target_draw_number: str,
    target_draw_date: str,
    path: Path,
) -> None:
    try:
        cutoff_key = (date.fromisoformat(cutoff["draw_date"]), int(cutoff["draw_number"]))
        target_key = (date.fromisoformat(target_draw_date), int(target_draw_number))
    except ValueError as exc:
        raise PortfolioMaterializationError(
            f"{path}: cutoff or target identity is invalid"
        ) from exc
    if cutoff_key >= target_key:
        raise PortfolioMaterializationError(f"{path}: history cutoff must precede target draw")


def _read_json_object(path: Path) -> tuple[bytes, dict[str, object]]:
    if not path.is_absolute():
        raise PortfolioMaterializationError(f"{path}: candidate path must be absolute")
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise PortfolioMaterializationError(f"{path}: candidate is not a regular file")
        raw = path.read_bytes()
    except PortfolioMaterializationError:
        raise
    except OSError as exc:
        raise PortfolioMaterializationError(f"{path}: candidate cannot be read") from exc
    try:
        parsed: object = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise PortfolioMaterializationError(f"{path}: candidate is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise PortfolioMaterializationError(f"{path}: candidate is not one JSON object")
    return raw, cast(dict[str, object], parsed)


def _reject_forbidden_keys(value: object, path: Path) -> None:
    if isinstance(value, dict):
        for key, item in cast(Mapping[str, object], value).items():
            if key in _FORBIDDEN_KEYS:
                raise PortfolioMaterializationError(
                    f"{path}: outcome/scoring key is forbidden: {key}"
                )
            _reject_forbidden_keys(item, path)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _reject_forbidden_keys(item, path)


def _required_text(value: Mapping[str, object], key: str, path: Path) -> str:
    item = value.get(key)
    if type(item) is not str or not item.strip():
        raise PortfolioMaterializationError(f"{path}: {key} must be non-empty text")
    return item


def _required_int(value: Mapping[str, object], key: str, path: Path) -> int:
    item = value.get(key)
    if type(item) is not int or item < 1:
        raise PortfolioMaterializationError(f"{path}: {key} must be a positive integer")
    return item


def _required_digest(value: Mapping[str, object], key: str, path: Path) -> str:
    item = _required_text(value, key, path)
    if _SHA256.fullmatch(item) is None:
        raise PortfolioMaterializationError(f"{path}: {key} must be a lowercase SHA-256 digest")
    return item


def _require_identifier(value: str, label: str) -> None:
    if _IDENTIFIER.fullmatch(value) is None:
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


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


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
    if _IDENTIFIER.fullmatch(destination.name) is None:
        raise PortfolioMaterializationError("destination basename is not canonical")
    if any(part in {"", ".", "..", ".git"} for part in destination.parts):
        raise PortfolioMaterializationError("destination contains a forbidden path component")
    if any(os.path.lexists(ancestor / ".git") for ancestor in destination.parents):
        raise PortfolioMaterializationError("authority must be outside every Git worktree")


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
    if type(staged) is not _StagedPayload:
        raise PortfolioMaterializationError("staged value has the wrong type")
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
    "PortfolioAuthorityConflictError",
    "PortfolioMaterializationError",
    "PortfolioMaterializationResult",
    "default_portfolio_destination",
    "materialize_portfolios",
]
