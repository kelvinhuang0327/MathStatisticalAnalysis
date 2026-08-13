"""Durable create-once storage for pre-outcome target registrations.

Every filesystem operation is rooted in verified directory descriptors.  No
accepted record is opened, linked, removed, or fsynced through a pathname that
can be redirected between a safety check and its use.
"""

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

from lottolab.application.pre_outcome_target import CorruptAuthorityError
from lottolab.domain.pre_outcome_target import PreOutcomeTargetRegistration
from lottolab.domain.prospective_observer import CreateOnceOutcome, ObservationTarget

PRE_OUTCOME_TARGET_AUTHORITY_STORE_SCHEMA_VERSION = "LOTTOLAB_PRE_OUTCOME_TARGET_AUTHORITY_STORE_V1"
_RECORD_TYPE = "pre_outcome_target_registration"
_RECORD_NAME = "registration.json"
_MAX_RECORD_BYTES = 1024 * 1024
_TEMPORARY_ATTEMPTS = 128
_OWNED_TEMPORARY_NAME = re.compile(r"\.registration-[0-9a-f]{32}\.tmp", re.ASCII)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


class PreOutcomeTargetAuthorityStoreCorruptionError(CorruptAuthorityError):
    """An accepted authority path or its self-verifying record is invalid."""


class FileSystemPreOutcomeTargetAuthorityStore:
    """Caller-rooted, restart-safe create-once target-authority store."""

    def __init__(self, root: str | Path) -> None:
        if not str(root):
            raise ValueError("root must be a non-empty filesystem path")
        _require_platform_safety()
        self._root = Path(root).absolute()
        self._root_fd = -1
        self._root_identity: tuple[int, int] | None = None
        descriptor = _open_absolute_directory(self._root, create=True)
        try:
            pathname_descriptor = _open_absolute_directory(self._root, create=False)
            try:
                if not _descriptors_match(descriptor, pathname_descriptor):
                    raise PreOutcomeTargetAuthorityStoreCorruptionError(
                        "storage root pathname does not match its verified inode"
                    )
            finally:
                os.close(pathname_descriptor)
            metadata = os.fstat(descriptor)
            self._root_identity = (metadata.st_dev, metadata.st_ino)
            self._root_fd = descriptor
        except BaseException:
            os.close(descriptor)
            raise

    @property
    def root(self) -> Path:
        return self._root

    def close(self) -> None:
        """Release the pinned root descriptor; accepted records remain durable."""

        descriptor = getattr(self, "_root_fd", -1)
        self._root_fd = -1
        self._root_identity = None
        if descriptor >= 0:
            os.close(descriptor)

    def __del__(self) -> None:
        with suppress(OSError):
            self.close()

    def get_registration(
        self,
        target: ObservationTarget,
    ) -> PreOutcomeTargetRegistration | None:
        _require_target(target)
        try:
            root_fd = self._open_root()
            try:
                target_fd = self._open_target_directory(root_fd, target, create=False)
                if target_fd is None:
                    return None
                try:
                    registration = self._read_optional_at(target_fd, target=target)
                    self._verify_target_anchor(root_fd, target, target_fd)
                    return registration
                finally:
                    os.close(target_fd)
            finally:
                os.close(root_fd)
        except PreOutcomeTargetAuthorityStoreCorruptionError:
            raise
        except OSError as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"cannot safely read target authority: {exc}"
            ) from exc

    def create_registration(
        self,
        registration: PreOutcomeTargetRegistration,
    ) -> CreateOnceOutcome:
        if type(registration) is not PreOutcomeTargetRegistration:
            raise ValueError("registration must be a PreOutcomeTargetRegistration")

        target = registration.target
        payload = _encode_registration(registration)
        if len(payload) > _MAX_RECORD_BYTES:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                "encoded target registration exceeds the bounded size limit"
            )

        try:
            root_fd = self._open_root()
            try:
                target_fd = self._open_target_directory(root_fd, target, create=True)
                if target_fd is None:  # pragma: no cover - create=True makes this impossible
                    raise PreOutcomeTargetAuthorityStoreCorruptionError(
                        "target authority directory was not created"
                    )
                try:
                    outcome = self._create_at(
                        root_fd,
                        target_fd,
                        registration,
                        payload,
                    )
                    self._verify_target_anchor(root_fd, target, target_fd)
                    return outcome
                finally:
                    os.close(target_fd)
            finally:
                os.close(root_fd)
        except PreOutcomeTargetAuthorityStoreCorruptionError:
            raise
        except OSError as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"cannot safely create target authority: {exc}"
            ) from exc

    def _open_root(self) -> int:
        pinned_fd = self._root_fd
        identity = self._root_identity
        if pinned_fd < 0 or identity is None:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                "storage root anchor is unavailable"
            )
        try:
            pinned_metadata = os.fstat(pinned_fd)
            _validate_directory_descriptor(
                pinned_fd,
                self._root.name,
                owner_only=True,
            )
            if (pinned_metadata.st_dev, pinned_metadata.st_ino) != identity:
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    "pinned storage root inode changed"
                )
            pathname_fd = _open_absolute_directory(self._root, create=False)
            try:
                if not _descriptors_match(pinned_fd, pathname_fd):
                    raise PreOutcomeTargetAuthorityStoreCorruptionError(
                        "storage root pathname changed after startup"
                    )
            finally:
                os.close(pathname_fd)
            return os.dup(pinned_fd)
        except PreOutcomeTargetAuthorityStoreCorruptionError:
            raise
        except OSError as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"cannot reopen storage root safely: {exc}"
            ) from exc

    def _open_target_directory(
        self,
        root_fd: int,
        target: ObservationTarget,
        *,
        create: bool,
    ) -> int | None:
        lottery_key, target_key = self._target_segments(target)
        try:
            lottery_fd = _open_child_directory(root_fd, lottery_key, create=create)
        except FileNotFoundError:
            return None
        try:
            try:
                return _open_child_directory(lottery_fd, target_key, create=create)
            except FileNotFoundError:
                return None
        finally:
            os.close(lottery_fd)

    def _create_at(
        self,
        root_fd: int,
        target_fd: int,
        registration: PreOutcomeTargetRegistration,
        payload: bytes,
    ) -> CreateOnceOutcome:
        descriptor, temporary_name = _create_exclusive_file_at(target_fd)
        installed = False
        try:
            os.fchmod(descriptor, 0o600)
            _validate_owned_regular_descriptor(
                descriptor,
                temporary_name,
                require_one_link=True,
            )
            _write_all(descriptor, payload)
            os.fsync(descriptor)
            if not _entry_matches_descriptor(target_fd, temporary_name, descriptor):
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    "temporary authority entry changed before installation"
                )
            self._verify_target_anchor(root_fd, registration.target, target_fd)
            try:
                os.link(
                    temporary_name,
                    _RECORD_NAME,
                    src_dir_fd=target_fd,
                    dst_dir_fd=target_fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                pass
            except OSError as exc:
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    f"cannot atomically install target registration: {exc}"
                ) from exc
            else:
                installed = True
                if not _entry_matches_descriptor(target_fd, _RECORD_NAME, descriptor):
                    raise PreOutcomeTargetAuthorityStoreCorruptionError(
                        "installed authority entry does not match its written inode"
                    )
            os.fsync(target_fd)
        finally:
            self._remove_owned_temporary(target_fd, temporary_name, descriptor)

        persisted = self._read_optional_at(target_fd, target=registration.target)
        if persisted is None:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                "accepted target registration disappeared"
            )
        if installed:
            if not _records_equal(persisted, registration):
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    "new target registration failed exact read-after-write"
                )
            return CreateOnceOutcome.INSERTED
        return (
            CreateOnceOutcome.ALREADY_PRESENT
            if _records_equal(persisted, registration)
            else CreateOnceOutcome.CONFLICT
        )

    def _verify_target_anchor(
        self,
        root_fd: int,
        target: ObservationTarget,
        target_fd: int,
    ) -> None:
        self._verify_root_anchor(root_fd)
        reopened_fd = self._open_target_directory(root_fd, target, create=False)
        if reopened_fd is None:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                "target authority directory disappeared during the operation"
            )
        try:
            if not _descriptors_match(reopened_fd, target_fd):
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    "target authority directory inode changed during the operation"
                )
        finally:
            os.close(reopened_fd)

    def _verify_root_anchor(self, root_fd: int) -> None:
        try:
            pathname_fd = _open_absolute_directory(self._root, create=False)
        except (OSError, PreOutcomeTargetAuthorityStoreCorruptionError) as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"storage root pathname changed during the operation: {exc}"
            ) from exc
        try:
            if not _descriptors_match(pathname_fd, root_fd):
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    "storage root inode changed during the operation"
                )
        finally:
            os.close(pathname_fd)

    @staticmethod
    def _remove_owned_temporary(
        target_fd: int,
        temporary_name: str,
        descriptor: int,
    ) -> None:
        try:
            if not _entry_matches_descriptor(target_fd, temporary_name, descriptor):
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    "temporary authority entry changed; preserving the unowned entry"
                )
            try:
                os.unlink(temporary_name, dir_fd=target_fd)
            except OSError as exc:
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    f"cannot remove completed temporary authority record: {exc}"
                ) from exc
            os.fsync(target_fd)
        finally:
            os.close(descriptor)

    def _read_optional_at(
        self,
        target_fd: int,
        *,
        target: ObservationTarget,
    ) -> PreOutcomeTargetRegistration | None:
        try:
            encoded = _read_owned_regular_at(target_fd, _RECORD_NAME)
        except FileNotFoundError:
            return None
        path = self._record_path(target)
        try:
            envelope = _decode_json_object(encoded)
            if encoded != _canonical_bytes(envelope):
                raise ValueError("stored envelope bytes are not canonical JSON")
            _expect_keys(
                envelope,
                {"envelope_sha256", "record", "record_type", "schema_version"},
                "envelope",
            )
            _expect_exact(
                envelope["schema_version"],
                PRE_OUTCOME_TARGET_AUTHORITY_STORE_SCHEMA_VERSION,
                "store schema_version",
            )
            _expect_exact(envelope["record_type"], _RECORD_TYPE, "record_type")
            material = {
                "record": envelope["record"],
                "record_type": envelope["record_type"],
                "schema_version": envelope["schema_version"],
            }
            expected_digest = hashlib.sha256(_canonical_bytes(material)).hexdigest()
            if _string(envelope["envelope_sha256"], "envelope_sha256") != expected_digest:
                raise ValueError("envelope_sha256 does not match the complete stored record")
            record = _decode_registration(_object(envelope["record"], "record"))
            if record.target != target:
                raise ValueError("record target does not match its storage key")
            return record
        except PreOutcomeTargetAuthorityStoreCorruptionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"corrupt target registration at {path}: {exc}"
            ) from exc

    def _record_path(self, target: ObservationTarget) -> Path:
        lottery_key, target_key = self._target_segments(target)
        return self._root / lottery_key / target_key / _RECORD_NAME

    @staticmethod
    def _target_segments(target: ObservationTarget) -> tuple[str, str]:
        _require_target(target)
        lottery_key = target.lottery_type.value.lower()
        target_key = (
            f"target-{target.draw_date.isoformat()}-{_digest_segment(target.canonical_dict())}"
        )
        _require_safe_name(lottery_key)
        _require_safe_name(target_key)
        return lottery_key, target_key


def _open_absolute_directory(path: Path, *, create: bool) -> int:
    if not path.is_absolute() or len(path.parts) < 2:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            "storage root must be a non-root absolute path"
        )
    flags = os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
    try:
        parent_fd = os.open(path.anchor, flags)
    except OSError as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"cannot anchor storage filesystem root: {exc}"
        ) from exc
    try:
        components = path.parts[1:]
        for index, component in enumerate(components):
            _require_safe_name(component)
            created = False
            try:
                next_fd = os.open(component, flags, dir_fd=parent_fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o700, dir_fd=parent_fd)
                    created = True
                    os.fsync(parent_fd)
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise PreOutcomeTargetAuthorityStoreCorruptionError(
                        f"cannot create storage directory safely ({component}): {exc}"
                    ) from exc
                try:
                    next_fd = os.open(component, flags, dir_fd=parent_fd)
                except OSError as exc:
                    raise PreOutcomeTargetAuthorityStoreCorruptionError(
                        "storage path is not a real directory or cannot be opened "
                        f"safely ({component}): {exc}"
                    ) from exc
            except OSError as exc:
                raise PreOutcomeTargetAuthorityStoreCorruptionError(
                    "storage path is not a real directory or cannot be opened "
                    f"safely ({component}): {exc}"
                ) from exc
            try:
                if created:
                    os.fchmod(next_fd, 0o700)
                _validate_directory_descriptor(
                    next_fd,
                    component,
                    owner_only=index == len(components) - 1,
                )
                if not _entry_matches_descriptor(parent_fd, component, next_fd):
                    raise PreOutcomeTargetAuthorityStoreCorruptionError(
                        f"storage directory entry changed while anchoring ({component})"
                    )
            except BaseException:
                os.close(next_fd)
                raise
            os.close(parent_fd)
            parent_fd = next_fd
        return parent_fd
    except BaseException:
        os.close(parent_fd)
        raise


def _open_child_directory(parent_fd: int, name: str, *, create: bool) -> int:
    _require_safe_name(name)
    flags = os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC
    created = False
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            created = True
            os.fsync(parent_fd)
        except FileExistsError:
            pass
        except OSError as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"cannot create target authority directory safely ({name}): {exc}"
            ) from exc
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"storage path is not a real directory or cannot be opened safely ({name}): {exc}"
        ) from exc
    try:
        if created:
            os.fchmod(descriptor, 0o700)
        _validate_directory_descriptor(descriptor, name, owner_only=True)
        if not _entry_matches_descriptor(parent_fd, name, descriptor):
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"storage directory entry changed while anchoring ({name})"
            )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _validate_directory_descriptor(
    descriptor: int,
    name: str,
    *,
    owner_only: bool,
) -> None:
    try:
        metadata = os.fstat(descriptor)
    except OSError as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"cannot inspect storage directory descriptor ({name}): {exc}"
        ) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"storage path is not a real directory: {name}"
        )
    if owner_only and metadata.st_uid != os.getuid():
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"storage directory has a foreign owner: {name}"
        )
    if owner_only and stat.S_IMODE(metadata.st_mode) != 0o700:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"storage directory mode must be exactly 0700: {name}"
        )


def _create_exclusive_file_at(directory_fd: int) -> tuple[int, str]:
    for _ in range(_TEMPORARY_ATTEMPTS):
        name = f".registration-{secrets.token_hex(16)}.tmp"
        _require_safe_name(name)
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o600,
                dir_fd=directory_fd,
            )
        except FileExistsError:
            continue
        except OSError as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"cannot create fresh temporary authority record ({name}): {exc}"
            ) from exc
        return descriptor, name
    raise PreOutcomeTargetAuthorityStoreCorruptionError(
        "cannot allocate an exclusive temporary authority filename"
    )


def _read_owned_regular_at(directory_fd: int, name: str) -> bytes:
    _require_safe_name(name)
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | _NONBLOCK | _NOFOLLOW | _CLOEXEC,
            dir_fd=directory_fd,
        )
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"cannot open accepted authority record safely ({name}): {exc}"
        ) from exc
    try:
        metadata = _validate_owned_regular_descriptor(
            descriptor,
            name,
            require_one_link=False,
        )
        _validate_accepted_link_state(directory_fd, descriptor)
        if metadata.st_size > _MAX_RECORD_BYTES:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"accepted authority record exceeds the bounded size limit: {name}"
            )
        if not _entry_matches_descriptor(directory_fd, name, descriptor):
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"accepted authority entry changed before reading: {name}"
            )
        chunks: list[bytes] = []
        remaining = _MAX_RECORD_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        encoded = b"".join(chunks)
        if len(encoded) > _MAX_RECORD_BYTES:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"accepted authority record exceeds the bounded size limit: {name}"
            )
        if not _entry_matches_descriptor(directory_fd, name, descriptor):
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"accepted authority entry changed while reading: {name}"
            )
        return encoded
    finally:
        os.close(descriptor)


def _validate_owned_regular_descriptor(
    descriptor: int,
    name: str,
    *,
    require_one_link: bool,
) -> os.stat_result:
    try:
        metadata = os.fstat(descriptor)
    except OSError as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"cannot inspect authority record descriptor ({name}): {exc}"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"accepted authority path is not a regular file: {name}"
        )
    if metadata.st_uid != os.getuid():
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"accepted authority record has a foreign owner: {name}"
        )
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"accepted authority record mode must be exactly 0600: {name}"
        )
    if require_one_link and metadata.st_nlink != 1:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"accepted authority record must have one link: {name}"
        )
    return metadata


def _validate_accepted_link_state(
    directory_fd: int,
    descriptor: int,
) -> None:
    metadata = os.fstat(descriptor)
    if metadata.st_nlink == 1:
        return
    if metadata.st_nlink != 2:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            "accepted authority record has an invalid hard-link count"
        )
    try:
        names = os.listdir(directory_fd)
    except OSError as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"cannot inspect accepted authority link state: {exc}"
        ) from exc
    matching_temporary_names: list[str] = []
    for candidate in names:
        if _OWNED_TEMPORARY_NAME.fullmatch(candidate) is None:
            continue
        try:
            entry = os.stat(candidate, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                f"cannot inspect temporary authority link ({candidate}): {exc}"
            ) from exc
        if (entry.st_dev, entry.st_ino) == (metadata.st_dev, metadata.st_ino):
            matching_temporary_names.append(candidate)

    settled = os.fstat(descriptor)
    if settled.st_nlink == 1:
        return
    if settled.st_nlink != 2 or len(matching_temporary_names) != 1:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            "accepted authority record has an invalid hard-link count"
        )
    if not _entry_matches_descriptor(
        directory_fd,
        matching_temporary_names[0],
        descriptor,
    ):
        final = os.fstat(descriptor)
        if final.st_nlink == 1:
            return
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            "accepted authority temporary link changed without settling"
        )


def _entry_matches_descriptor(directory_fd: int, name: str, descriptor: int) -> bool:
    try:
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"cannot inspect anchored storage entry ({name}): {exc}"
        ) from exc
    opened = os.fstat(descriptor)
    return (entry.st_dev, entry.st_ino) == (opened.st_dev, opened.st_ino)


def _descriptors_match(first: int, second: int) -> bool:
    first_metadata = os.fstat(first)
    second_metadata = os.fstat(second)
    return (first_metadata.st_dev, first_metadata.st_ino) == (
        second_metadata.st_dev,
        second_metadata.st_ino,
    )


def _records_equal(
    first: PreOutcomeTargetRegistration,
    second: PreOutcomeTargetRegistration,
) -> bool:
    return first.canonical_dict() == second.canonical_dict()


def _encode_registration(record: PreOutcomeTargetRegistration) -> bytes:
    material = {
        "record": record.canonical_dict(),
        "record_type": _RECORD_TYPE,
        "schema_version": PRE_OUTCOME_TARGET_AUTHORITY_STORE_SCHEMA_VERSION,
    }
    return _canonical_bytes(
        {
            **material,
            "envelope_sha256": hashlib.sha256(_canonical_bytes(material)).hexdigest(),
        }
    )


def _decode_registration(
    value: Mapping[str, object],
) -> PreOutcomeTargetRegistration:
    return PreOutcomeTargetRegistration.from_canonical_dict(value)


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise PreOutcomeTargetAuthorityStoreCorruptionError(
                "authority record write made no progress"
            )
        remaining = remaining[written:]


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def _digest_segment(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()[:32]


def _decode_json_object(encoded: bytes) -> Mapping[str, object]:
    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    try:
        decoded = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            f"accepted authority record contains malformed JSON: {exc}"
        ) from exc
    return _object(decoded, "envelope")


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} fields differ; missing={missing}, unknown={unknown}")


def _expect_exact(value: object, expected: str, label: str) -> None:
    if type(value) is not str or value != expected:
        raise ValueError(f"unsupported {label}")


def _object(value: object, label: str) -> Mapping[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} must be a string")
    return value


def _require_safe_name(name: str) -> None:
    path = Path(name)
    if not name or path.name != name or name in {".", ".."}:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            "storage path component must be one safe relative name"
        )


def _require_target(value: object) -> None:
    if type(value) is not ObservationTarget:
        raise ValueError("target must be an ObservationTarget")


def _require_platform_safety() -> None:
    if _DIRECTORY == 0 or _NOFOLLOW == 0 or _NONBLOCK == 0:
        raise PreOutcomeTargetAuthorityStoreCorruptionError(
            "required directory, no-follow, or nonblocking filesystem safety is unavailable"
        )
