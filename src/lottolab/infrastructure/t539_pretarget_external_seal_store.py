"""Atomic create-once local storage for T539 external seal receipt records."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.domain.t539_pretarget_external_seal import (
    PretargetSealStatus,
    SealRecordCreateOutcome,
    T539PretargetSealRecord,
    canonical_json_bytes,
)

T539_PRETARGET_SEAL_STORE_SCHEMA_VERSION = "T539_PRETARGET_EXTERNAL_SEAL_STORE_V1"
_RECORD_TYPE = "t539_pretarget_external_seal_receipt"
_MAX_RECORD_BYTES = 8 * 1024 * 1024
_TEMPORARY_ATTEMPTS = 128
_TEMPORARY_NAME = re.compile(r"\.t539-seal-[0-9a-f]{32}\.tmp", flags=re.ASCII)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


class PretargetSealStoreCorruptionError(RuntimeError):
    """A durable receipt path or self-verifying record failed closed."""


class FileSystemT539PretargetSealRecordStore:
    """Pinned-root, hard-link-committed first-wins receipt store."""

    def __init__(self, root: str | Path) -> None:
        if not str(root):
            raise ValueError("root must be a non-empty filesystem path")
        self._root = Path(root).absolute()
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                self._root,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
            )
        except OSError as exc:
            raise PretargetSealStoreCorruptionError(
                f"cannot open receipt store root safely: {exc}"
            ) from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise PretargetSealStoreCorruptionError("receipt store root is not a directory")
            if metadata.st_mode & 0o022:
                raise PretargetSealStoreCorruptionError(
                    "receipt store root must not be group/world writable"
                )
            self._root_identity = (metadata.st_dev, metadata.st_ino)
            self._root_fd = descriptor
        except BaseException:
            os.close(descriptor)
            raise

    @property
    def root(self) -> Path:
        return self._root

    @classmethod
    def record_path_for(cls, root: str | Path, target: ObservationTarget) -> Path:
        return Path(root).absolute() / cls._record_name(target)

    def close(self) -> None:
        descriptor = getattr(self, "_root_fd", -1)
        self._root_fd = -1
        if descriptor >= 0:
            os.close(descriptor)

    def __del__(self) -> None:
        with suppress(OSError):
            self.close()

    def get_record(self, target: ObservationTarget) -> T539PretargetSealRecord | None:
        name = self._record_name(target)
        root_fd = self._open_root()
        try:
            return self._read_optional_at(root_fd, name, target)
        finally:
            os.close(root_fd)

    def create_record(self, record: T539PretargetSealRecord) -> SealRecordCreateOutcome:
        if type(record) is not T539PretargetSealRecord:
            raise ValueError("record must be a T539PretargetSealRecord")
        payload = _encode_record(record)
        if len(payload) > _MAX_RECORD_BYTES:
            raise PretargetSealStoreCorruptionError(
                "encoded T539 receipt record exceeds the bounded size limit"
            )

        root_fd = self._open_root()
        temporary_name: str | None = None
        try:
            name = self._record_name(record.seal.target)
            existing = self._read_optional_at(root_fd, name, record.seal.target)
            if existing is not None:
                return _compare_records(existing, record)

            temporary_name, descriptor = self._create_temporary(root_fd)
            try:
                _write_all(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

            try:
                os.link(
                    temporary_name,
                    name,
                    src_dir_fd=root_fd,
                    dst_dir_fd=root_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                winner = self._read_optional_at(root_fd, name, record.seal.target)
                if winner is None:  # pragma: no cover - FileExistsError establishes the name
                    raise PretargetSealStoreCorruptionError(
                        "receipt winner disappeared during create-once resolution"
                    ) from exc
                return _compare_records(winner, record)

            os.fsync(root_fd)
            os.unlink(temporary_name, dir_fd=root_fd)
            temporary_name = None
            os.fsync(root_fd)
            accepted = self._read_optional_at(root_fd, name, record.seal.target)
            if accepted is None or accepted.canonical_dict() != record.canonical_dict():
                raise PretargetSealStoreCorruptionError(
                    "newly linked receipt record cannot be read back exactly"
                )
            return SealRecordCreateOutcome.INSERTED
        except PretargetSealStoreCorruptionError:
            raise
        except OSError as exc:
            raise PretargetSealStoreCorruptionError(
                f"cannot safely create T539 receipt record: {exc}"
            ) from exc
        finally:
            if temporary_name is not None:
                with suppress(OSError):
                    os.unlink(temporary_name, dir_fd=root_fd)
                    os.fsync(root_fd)
            os.close(root_fd)

    def find_associated_receipt(
        self,
        *,
        target: ObservationTarget,
        seal_digest: str,
        rekor_entry_id: str,
    ) -> T539PretargetSealRecord | None:
        """Return only an exact target + seal digest + Rekor EntryID association."""

        record = self.get_record(target)
        if (
            record is None
            or record.status is not PretargetSealStatus.SEALED
            or record.seal_digest != seal_digest
            or record.receipt is None
            or record.receipt.rekor_entry_id != rekor_entry_id
        ):
            return None
        return record

    def _open_root(self) -> int:
        descriptor = getattr(self, "_root_fd", -1)
        if descriptor < 0:
            raise PretargetSealStoreCorruptionError("receipt store is closed")
        try:
            pinned = os.fstat(descriptor)
            if (pinned.st_dev, pinned.st_ino) != self._root_identity:
                raise PretargetSealStoreCorruptionError("pinned receipt root identity changed")
            if not stat.S_ISDIR(pinned.st_mode) or pinned.st_mode & 0o022:
                raise PretargetSealStoreCorruptionError(
                    "pinned receipt root permissions are unsafe"
                )
            pathname_fd = os.open(
                self._root,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
            )
            try:
                pathname = os.fstat(pathname_fd)
                if (pathname.st_dev, pathname.st_ino) != self._root_identity:
                    raise PretargetSealStoreCorruptionError(
                        "receipt root pathname no longer names the pinned directory"
                    )
                if not stat.S_ISDIR(pathname.st_mode) or pathname.st_mode & 0o022:
                    raise PretargetSealStoreCorruptionError(
                        "receipt root pathname permissions are unsafe"
                    )
            finally:
                os.close(pathname_fd)
            return os.dup(descriptor)
        except PretargetSealStoreCorruptionError:
            raise
        except OSError as exc:
            raise PretargetSealStoreCorruptionError(
                f"cannot reopen receipt store root safely: {exc}"
            ) from exc

    def _read_optional_at(
        self,
        root_fd: int,
        name: str,
        target: ObservationTarget,
    ) -> T539PretargetSealRecord | None:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | _NOFOLLOW | _CLOEXEC | _NONBLOCK,
                dir_fd=root_fd,
            )
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise PretargetSealStoreCorruptionError(
                f"cannot open accepted receipt record safely: {exc}"
            ) from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise PretargetSealStoreCorruptionError(
                    "accepted receipt record is not a regular file"
                )
            self._settle_owned_links(root_fd, descriptor)
            if os.fstat(descriptor).st_nlink != 1:
                raise PretargetSealStoreCorruptionError(
                    "accepted receipt record has an unexpected hard-link count"
                )
            if not _entry_matches_descriptor(root_fd, name, descriptor):
                raise PretargetSealStoreCorruptionError(
                    "accepted receipt pathname changed before read"
                )
            payload = _read_bounded(descriptor)
            if not _entry_matches_descriptor(root_fd, name, descriptor):
                raise PretargetSealStoreCorruptionError(
                    "accepted receipt pathname changed during read"
                )
        finally:
            os.close(descriptor)
        record = _decode_record(payload)
        if record.seal.target != target:
            raise PretargetSealStoreCorruptionError(
                "accepted receipt record target differs from its canonical pathname"
            )
        return record

    def _settle_owned_links(self, root_fd: int, descriptor: int) -> None:
        accepted = os.fstat(descriptor)
        removed = False
        try:
            names = os.listdir(root_fd)
        except OSError as exc:
            raise PretargetSealStoreCorruptionError(
                f"cannot inspect receipt store temporary links: {exc}"
            ) from exc
        for name in names:
            if _TEMPORARY_NAME.fullmatch(name) is None:
                continue
            try:
                candidate = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if (candidate.st_dev, candidate.st_ino) != (accepted.st_dev, accepted.st_ino):
                continue
            os.unlink(name, dir_fd=root_fd)
            removed = True
        if removed:
            os.fsync(root_fd)

    @staticmethod
    def _create_temporary(root_fd: int) -> tuple[str, int]:
        for _ in range(_TEMPORARY_ATTEMPTS):
            name = f".t539-seal-{secrets.token_hex(16)}.tmp"
            try:
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                    0o600,
                    dir_fd=root_fd,
                )
            except FileExistsError:
                continue
            return name, descriptor
        raise PretargetSealStoreCorruptionError(
            "cannot allocate a unique task-owned receipt temporary file"
        )

    @staticmethod
    def _record_name(target: ObservationTarget) -> str:
        if type(target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        if target.lottery_type is not LotteryType.DAILY_539:
            raise ValueError("T539 receipt store accepts DAILY_539 targets only")
        return f"DAILY_539-{target.draw_date.isoformat()}-{target.draw_number}.json"


def _compare_records(
    first: T539PretargetSealRecord,
    second: T539PretargetSealRecord,
) -> SealRecordCreateOutcome:
    if first.canonical_dict() == second.canonical_dict():
        return SealRecordCreateOutcome.ALREADY_PRESENT
    return SealRecordCreateOutcome.CONFLICT


def _encode_record(record: T539PretargetSealRecord) -> bytes:
    material: dict[str, object] = {
        "record": record.canonical_dict(),
        "record_type": _RECORD_TYPE,
        "schema_version": T539_PRETARGET_SEAL_STORE_SCHEMA_VERSION,
    }
    envelope = {
        **material,
        "envelope_sha256": hashlib.sha256(canonical_json_bytes(material)).hexdigest(),
    }
    return canonical_json_bytes(envelope) + b"\n"


def _decode_record(payload: bytes) -> T539PretargetSealRecord:
    if not payload or len(payload) > _MAX_RECORD_BYTES:
        raise PretargetSealStoreCorruptionError("receipt record size is invalid")

    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(payload, object_pairs_hook=pairs_hook)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PretargetSealStoreCorruptionError("receipt record is not valid JSON") from exc
    mapping = _mapping(decoded, "receipt_store_envelope")
    expected = {"envelope_sha256", "record", "record_type", "schema_version"}
    if set(mapping) != expected:
        raise PretargetSealStoreCorruptionError("receipt record envelope fields differ")
    if mapping["record_type"] != _RECORD_TYPE:
        raise PretargetSealStoreCorruptionError("receipt record type differs")
    if mapping["schema_version"] != T539_PRETARGET_SEAL_STORE_SCHEMA_VERSION:
        raise PretargetSealStoreCorruptionError("receipt store schema_version differs")
    material: dict[str, object] = {
        "record": mapping["record"],
        "record_type": mapping["record_type"],
        "schema_version": mapping["schema_version"],
    }
    expected_digest = hashlib.sha256(canonical_json_bytes(material)).hexdigest()
    if mapping["envelope_sha256"] != expected_digest:
        raise PretargetSealStoreCorruptionError("receipt record envelope hash mismatch")
    try:
        record = T539PretargetSealRecord.from_canonical_dict(
            _mapping(mapping["record"], "receipt_store_envelope.record")
        )
    except ValueError as exc:
        raise PretargetSealStoreCorruptionError(
            "receipt record domain validation failed"
        ) from exc
    if payload != _encode_record(record):
        raise PretargetSealStoreCorruptionError("receipt record bytes are not canonical")
    return record


def _read_bounded(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = os.read(descriptor, min(64 * 1024, _MAX_RECORD_BYTES + 1 - size))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > _MAX_RECORD_BYTES:
            raise PretargetSealStoreCorruptionError("receipt record exceeds size limit")


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise PretargetSealStoreCorruptionError("receipt record write made no progress")
        remaining = remaining[written:]


def _entry_matches_descriptor(root_fd: int, name: str, descriptor: int) -> bool:
    try:
        entry = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise PretargetSealStoreCorruptionError(
            f"cannot inspect accepted receipt pathname: {exc}"
        ) from exc
    opened = os.fstat(descriptor)
    return (entry.st_dev, entry.st_ino) == (opened.st_dev, opened.st_ino)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PretargetSealStoreCorruptionError(f"{label} must be an object")
    object_mapping = cast(Mapping[object, object], value)
    if any(type(key) is not str for key in object_mapping):
        raise PretargetSealStoreCorruptionError(f"{label} keys must be strings")
    return cast(Mapping[str, object], object_mapping)


__all__ = [
    "T539_PRETARGET_SEAL_STORE_SCHEMA_VERSION",
    "FileSystemT539PretargetSealRecordStore",
    "PretargetSealStoreCorruptionError",
]
