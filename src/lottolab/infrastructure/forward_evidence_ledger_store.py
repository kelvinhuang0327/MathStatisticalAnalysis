"""Durable create-once filesystem storage for forward evidence ledger entries.

Implements crash-safe, atomic file writes using temporary hard links and fsyncs,
canonical envelope hashing, and deterministic retrieval by member or cohort.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.forward_evidence_ledger import (
    FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION,
    ForwardEvidenceLedgerEntry,
    ForwardEvidenceLedgerEntryIdentity,
    ForwardEvidenceLedgerError,
    LedgerTicketEvidence,
)
from lottolab.domain.prospective_observer import (
    CreateOnceOutcome,
    DiagnosticEvent,
    ScoreAvailability,
    TemporalProvenance,
)

FORWARD_EVIDENCE_LEDGER_STORE_SCHEMA_VERSION = "LOTTOLAB_FORWARD_EVIDENCE_LEDGER_STORE_V1"
_MAX_RECORD_BYTES = 16 * 1024 * 1024
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_T = TypeVar("_T")


class ForwardEvidenceLedgerStoreCorruptionError(ForwardEvidenceLedgerError):
    """An accepted ledger entry file or its stored envelope authority is corrupt."""


class FileSystemForwardEvidenceLedgerStore:
    """Caller-rooted, restart-safe create-once storage for forward evidence entries."""

    def __init__(self, root: str | Path) -> None:
        if not str(root):
            raise ValueError("root must be a non-empty filesystem path")
        self._root = Path(root).absolute()
        _materialize_directory(self._root)

    @property
    def root(self) -> Path:
        return self._root

    def get_entry(
        self,
        identity: ForwardEvidenceLedgerEntryIdentity,
    ) -> ForwardEvidenceLedgerEntry | None:
        _require_identity(identity)
        path = self._entry_path(identity)
        return self._read_optional(path, expected_identity=identity)

    def create_entry(self, entry: ForwardEvidenceLedgerEntry) -> CreateOnceOutcome:
        if type(entry) is not ForwardEvidenceLedgerEntry:
            raise ValueError("entry must be a ForwardEvidenceLedgerEntry")
        path = self._entry_path(entry.identity)
        payload = _encode_entry(entry)
        outcome = self._create_once(
            path,
            identity=entry.identity,
            payload=payload,
            expected=entry,
            equal=lambda existing, candidate: (
                existing.ledger_entry_hash == candidate.ledger_entry_hash
                and existing.canonical_material() == candidate.canonical_material()
            ),
        )
        if outcome is not CreateOnceOutcome.CONFLICT:
            persisted = self.get_entry(entry.identity)
            if persisted is None:
                raise ForwardEvidenceLedgerStoreCorruptionError(
                    "accepted ledger entry disappeared after durable creation"
                )
        return outcome

    def list_member_entries(
        self,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
        member_id: str,
    ) -> tuple[ForwardEvidenceLedgerEntry, ...]:
        """List all entries for a specific member sorted by (draw_date, draw_number)."""
        if type(lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        _require_text(cohort_id, "cohort_id")
        _require_text(cohort_version, "cohort_version")
        _require_text(member_id, "member_id")

        member_dir = self._member_directory(
            lottery_type=lottery_type,
            cohort_id=cohort_id,
            cohort_version=cohort_version,
            member_id=member_id,
        )
        if not member_dir.is_dir():
            return ()

        entries: list[ForwardEvidenceLedgerEntry] = []
        for file_path in member_dir.glob("entry-*.json"):
            if file_path.name.startswith("."):
                continue
            entry = self._read_file(file_path)
            if (
                entry.identity.lottery_type is lottery_type
                and entry.identity.cohort_id == cohort_id
                and entry.identity.cohort_version == cohort_version
                and entry.identity.member_id == member_id
            ):
                entries.append(entry)

        entries.sort(
            key=lambda e: (e.identity.target_draw_date, int(e.identity.target_draw_number))
        )
        return tuple(entries)

    def list_cohort_entries(
        self,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
    ) -> tuple[ForwardEvidenceLedgerEntry, ...]:
        """List all entries for an entire cohort sorted by (draw_date, draw_number, member_id)."""
        if type(lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        _require_text(cohort_id, "cohort_id")
        _require_text(cohort_version, "cohort_version")

        cohort_dir = self._cohort_directory(
            lottery_type=lottery_type,
            cohort_id=cohort_id,
            cohort_version=cohort_version,
        )
        if not cohort_dir.is_dir():
            return ()

        entries: list[ForwardEvidenceLedgerEntry] = []
        for member_dir in cohort_dir.iterdir():
            if not member_dir.is_dir() or member_dir.name.startswith("."):
                continue
            for file_path in member_dir.glob("entry-*.json"):
                if file_path.name.startswith("."):
                    continue
                entry = self._read_file(file_path)
                if (
                    entry.identity.lottery_type is lottery_type
                    and entry.identity.cohort_id == cohort_id
                    and entry.identity.cohort_version == cohort_version
                ):
                    entries.append(entry)

        entries.sort(
            key=lambda e: (
                e.identity.target_draw_date,
                int(e.identity.target_draw_number),
                e.identity.member_id,
            )
        )
        return tuple(entries)

    def entry_path(self, identity: ForwardEvidenceLedgerEntryIdentity) -> Path:
        """Return the canonical filesystem path for a ledger entry."""
        return self._entry_path(identity)

    def _cohort_directory(
        self,
        *,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
    ) -> Path:
        cohort_key = _digest_segment(
            {
                "cohort_id": cohort_id,
                "cohort_version": cohort_version,
            }
        )
        return self._root / lottery_type.value.lower() / f"cohort-{cohort_key}"

    def _member_directory(
        self,
        *,
        lottery_type: LotteryType,
        cohort_id: str,
        cohort_version: str,
        member_id: str,
    ) -> Path:
        cohort_dir = self._cohort_directory(
            lottery_type=lottery_type,
            cohort_id=cohort_id,
            cohort_version=cohort_version,
        )
        member_key = _digest_segment({"member_id": member_id})
        return cohort_dir / f"member-{member_key}"

    def _entry_path(self, identity: ForwardEvidenceLedgerEntryIdentity) -> Path:
        member_dir = self._member_directory(
            lottery_type=identity.lottery_type,
            cohort_id=identity.cohort_id,
            cohort_version=identity.cohort_version,
            member_id=identity.member_id,
        )
        target_key = _digest_segment(identity.canonical_dict())
        return member_dir / f"entry-{identity.target_draw_date.isoformat()}-{target_key}.json"

    def _read_optional(
        self,
        path: Path,
        *,
        expected_identity: ForwardEvidenceLedgerEntryIdentity,
    ) -> ForwardEvidenceLedgerEntry | None:
        try:
            return self._read_file(path, expected_identity=expected_identity)
        except FileNotFoundError:
            return None

    def _read_file(
        self,
        path: Path,
        *,
        expected_identity: ForwardEvidenceLedgerEntryIdentity | None = None,
    ) -> ForwardEvidenceLedgerEntry:
        encoded = _read_regular_file(path)
        try:
            envelope = _decode_json_object(encoded)
            _expect_keys(
                envelope,
                {"envelope_sha256", "record", "record_type", "schema_version"},
                "envelope",
            )
            _expect_exact(
                envelope["schema_version"],
                FORWARD_EVIDENCE_LEDGER_STORE_SCHEMA_VERSION,
                "store schema_version",
            )
            _expect_exact(envelope["record_type"], "ledger_entry", "record_type")
            envelope_material = {
                "record": envelope["record"],
                "record_type": envelope["record_type"],
                "schema_version": envelope["schema_version"],
            }
            expected_envelope_hash = hashlib.sha256(
                _canonical_bytes(envelope_material)
            ).hexdigest()
            if (
                _string(envelope["envelope_sha256"], "envelope_sha256")
                != expected_envelope_hash
            ):
                raise ValueError("envelope_sha256 does not match the stored ledger entry")
            entry = _decode_entry(_object(envelope["record"], "record"))
            if expected_identity is not None and entry.identity != expected_identity:
                raise ValueError("entry identity does not match expected storage key")
            return entry
        except ForwardEvidenceLedgerStoreCorruptionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ForwardEvidenceLedgerStoreCorruptionError(
                f"corrupt ledger entry at {path}: {exc}"
            ) from exc

    def _create_once(
        self,
        path: Path,
        *,
        identity: ForwardEvidenceLedgerEntryIdentity,
        payload: bytes,
        expected: ForwardEvidenceLedgerEntry,
        equal: Callable[[ForwardEvidenceLedgerEntry, ForwardEvidenceLedgerEntry], bool],
    ) -> CreateOnceOutcome:
        _materialize_directory(path.parent)
        temporary = path.parent / f".entry-{secrets.token_hex(16)}.tmp"
        descriptor = -1
        installed = False
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o600,
            )
            _write_all(descriptor, payload)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            try:
                os.link(temporary, path, follow_symlinks=False)
                installed = True
                _fsync_directory(path.parent)
            except FileExistsError:
                _fsync_directory(path.parent)
        except OSError as exc:
            raise ForwardEvidenceLedgerStoreCorruptionError(
                f"failed to persist ledger entry at {path}: {exc}"
            ) from exc
        finally:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            with suppress(FileNotFoundError, OSError):
                os.unlink(temporary)

        if installed:
            return CreateOnceOutcome.INSERTED

        existing = self.get_entry(identity)
        if existing is None:
            raise ForwardEvidenceLedgerStoreCorruptionError(
                f"concurrent writer left no readable ledger entry at {path}"
            )
        if equal(existing, expected):
            return CreateOnceOutcome.ALREADY_PRESENT
        return CreateOnceOutcome.CONFLICT


def _require_identity(identity: ForwardEvidenceLedgerEntryIdentity) -> None:
    if type(identity) is not ForwardEvidenceLedgerEntryIdentity:
        raise ValueError("identity must be a ForwardEvidenceLedgerEntryIdentity")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _digest_segment(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()[:16]


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _encode_entry(entry: ForwardEvidenceLedgerEntry) -> bytes:
    record = entry.canonical_dict()
    envelope_material = {
        "record": record,
        "record_type": "ledger_entry",
        "schema_version": FORWARD_EVIDENCE_LEDGER_STORE_SCHEMA_VERSION,
    }
    envelope = {
        **envelope_material,
        "envelope_sha256": hashlib.sha256(_canonical_bytes(envelope_material)).hexdigest(),
    }
    return _canonical_bytes(envelope)


def _decode_entry(payload: Mapping[str, object]) -> ForwardEvidenceLedgerEntry:
    _expect_keys(
        payload,
        {
            "availability",
            "cohort_authority_sha256",
            "diagnostic_events",
            "entry_created_at",
            "identity",
            "is_winner",
            "ledger_entry_hash",
            "matched_baseline_id",
            "outcome_hash",
            "prediction_hash",
            "prize_rule_provenance",
            "prize_rule_version",
            "producer_fingerprint_digest",
            "schema_version",
            "score_hash",
            "temporal_provenance",
            "tickets",
            "unavailable_reason",
        },
        "ledger entry",
    )
    _expect_exact(
        payload["schema_version"],
        FORWARD_EVIDENCE_LEDGER_ENTRY_SCHEMA_VERSION,
        "entry schema_version",
    )
    identity_data = _object(payload["identity"], "identity")
    _expect_keys(
        identity_data,
        {
            "cohort_id",
            "cohort_version",
            "lottery_type",
            "member_id",
            "target_draw_date",
            "target_draw_number",
        },
        "identity",
    )
    identity = ForwardEvidenceLedgerEntryIdentity(
        lottery_type=LotteryType(_string(identity_data["lottery_type"], "lottery_type")),
        cohort_id=_string(identity_data["cohort_id"], "cohort_id"),
        cohort_version=_string(identity_data["cohort_version"], "cohort_version"),
        member_id=_string(identity_data["member_id"], "member_id"),
        target_draw_date=date.fromisoformat(
            _string(identity_data["target_draw_date"], "target_draw_date")
        ),
        target_draw_number=_string(
            identity_data["target_draw_number"], "target_draw_number"
        ),
    )

    tickets_data = _sequence(payload["tickets"], "tickets")
    tickets: list[LedgerTicketEvidence] = []
    for item in tickets_data:
        ticket_map = _object(item, "ticket")
        _expect_keys(
            ticket_map,
            {
                "is_winner",
                "main_numbers",
                "prize_tier",
                "prize_tier_order",
                "selection_index",
                "special_number",
                "zone1_hits",
                "zone2_hit",
            },
            "ticket",
        )
        main_numbers = tuple(
            _int(num, "main_number")
            for num in _sequence(ticket_map["main_numbers"], "main_numbers")
        )
        special_number = (
            _int(ticket_map["special_number"], "special_number")
            if ticket_map["special_number"] is not None
            else None
        )
        prize_tier = (
            _string(ticket_map["prize_tier"], "prize_tier")
            if ticket_map["prize_tier"] is not None
            else None
        )
        prize_tier_order = (
            _int(ticket_map["prize_tier_order"], "prize_tier_order")
            if ticket_map["prize_tier_order"] is not None
            else None
        )
        tickets.append(
            LedgerTicketEvidence(
                selection_index=_int(ticket_map["selection_index"], "selection_index"),
                main_numbers=main_numbers,
                special_number=special_number,
                zone1_hits=_int(ticket_map["zone1_hits"], "zone1_hits"),
                zone2_hit=_bool(ticket_map["zone2_hit"], "zone2_hit"),
                prize_tier=prize_tier,
                prize_tier_order=prize_tier_order,
                is_winner=_bool(ticket_map["is_winner"], "is_winner"),
            )
        )

    diag_data = _sequence(payload["diagnostic_events"], "diagnostic_events")
    diagnostics: list[DiagnosticEvent] = []
    for item in diag_data:
        diag_map = _object(item, "diagnostic_event")
        _expect_keys(diag_map, {"name", "occurred"}, "diagnostic_event")
        occurred = (
            _bool(diag_map["occurred"], "occurred")
            if diag_map["occurred"] is not None
            else None
        )
        diagnostics.append(
            DiagnosticEvent(
                name=_string(diag_map["name"], "name"),
                occurred=occurred,
            )
        )

    is_winner = (
        _bool(payload["is_winner"], "is_winner") if payload["is_winner"] is not None else None
    )
    unavailable_reason = (
        _string(payload["unavailable_reason"], "unavailable_reason")
        if payload["unavailable_reason"] is not None
        else None
    )
    matched_baseline_id = (
        _string(payload["matched_baseline_id"], "matched_baseline_id")
        if payload["matched_baseline_id"] is not None
        else None
    )
    prize_rule_version = (
        _string(payload["prize_rule_version"], "prize_rule_version")
        if payload["prize_rule_version"] is not None
        else None
    )
    prize_rule_provenance = (
        _string(payload["prize_rule_provenance"], "prize_rule_provenance")
        if payload["prize_rule_provenance"] is not None
        else None
    )

    return ForwardEvidenceLedgerEntry(
        schema_version=_string(payload["schema_version"], "schema_version"),
        identity=identity,
        prediction_hash=_string(payload["prediction_hash"], "prediction_hash"),
        outcome_hash=_string(payload["outcome_hash"], "outcome_hash"),
        score_hash=_string(payload["score_hash"], "score_hash"),
        producer_fingerprint_digest=_string(
            payload["producer_fingerprint_digest"], "producer_fingerprint_digest"
        ),
        cohort_authority_sha256=_string(
            payload["cohort_authority_sha256"], "cohort_authority_sha256"
        ),
        temporal_provenance=TemporalProvenance(
            _string(payload["temporal_provenance"], "temporal_provenance")
        ),
        availability=ScoreAvailability(_string(payload["availability"], "availability")),
        unavailable_reason=unavailable_reason,
        matched_baseline_id=matched_baseline_id,
        prize_rule_version=prize_rule_version,
        prize_rule_provenance=prize_rule_provenance,
        tickets=tuple(tickets),
        diagnostic_events=tuple(diagnostics),
        is_winner=is_winner,
        entry_created_at=_parse_utc_datetime(
            _string(payload["entry_created_at"], "entry_created_at"),
            "entry_created_at",
        ),
        ledger_entry_hash=_string(payload["ledger_entry_hash"], "ledger_entry_hash"),
    )


def _materialize_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        _fsync_directory(path)
    except OSError as exc:
        raise ForwardEvidenceLedgerStoreCorruptionError(
            f"failed to materialize directory {path}: {exc}"
        ) from exc


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | _CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    total = len(payload)
    while offset < total:
        written = os.write(descriptor, memoryview(payload)[offset:])
        if written <= 0:
            raise OSError("zero bytes written to store record")
        offset += written


def _read_regular_file(path: Path) -> bytes:
    try:
        stats = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ForwardEvidenceLedgerStoreCorruptionError(f"cannot inspect {path}: {exc}") from exc
    if not stat.S_ISREG(stats.st_mode):
        raise ForwardEvidenceLedgerStoreCorruptionError(f"{path} is not a regular file")
    if stats.st_size > _MAX_RECORD_BYTES:
        raise ForwardEvidenceLedgerStoreCorruptionError(
            f"{path} exceeds maximum size limit of {_MAX_RECORD_BYTES} bytes"
        )
    try:
        with open(path, "rb") as file:
            return file.read()
    except OSError as exc:
        raise ForwardEvidenceLedgerStoreCorruptionError(f"cannot read {path}: {exc}") from exc


def _decode_json_object(payload: bytes) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON payload: {exc}") from exc
    if type(value) is not dict:
        raise ValueError("JSON payload must be an object")
    return cast(dict[str, object], value)


def _expect_keys(payload: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(payload.keys())
    if actual != expected:
        missing = expected - actual
        extra = actual - expected
        raise ValueError(f"{label} has invalid keys: missing {missing}, extra {extra}")


def _expect_exact(value: object, expected: str, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} must be exactly '{expected}', got '{value}'")


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return value


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")
    return value


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object mapping")
    return cast(Mapping[str, object], value)


def _sequence(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return cast(list[object], value)


def _parse_utc_datetime(value: str, label: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError(f"{label} must end with 'Z'")
    normalized = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{label} must be in UTC timezone")
    return parsed


__all__ = [
    "FORWARD_EVIDENCE_LEDGER_STORE_SCHEMA_VERSION",
    "FileSystemForwardEvidenceLedgerStore",
    "ForwardEvidenceLedgerStoreCorruptionError",
]
