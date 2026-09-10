"""Atomic, no-overwrite writer for the B649 canonical forecast authority."""

from __future__ import annotations

import os
import re
import stat
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal
from uuid import uuid4

_OUTPUT_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", flags=re.ASCII)
_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)
_ODIRECTORY: Final = getattr(os, "O_DIRECTORY", 0)
_CREATED_MODE: Final = 0o700
_FILE_MODE: Final = 0o600


class CanonicalForecastWriterError(RuntimeError):
    """The authority could not be staged or published safely."""


class CanonicalForecastConflictError(CanonicalForecastWriterError):
    """An existing authority path is malformed or has different content."""


@dataclass(frozen=True, slots=True)
class StagedCanonicalForecast:
    """A fully fsynced temporary file waiting for one atomic hard-link call."""

    destination: Path
    temporary: Path
    payload_bytes: bytes


@dataclass(frozen=True, slots=True)
class CanonicalForecastWriteResult:
    """The observed result of one no-overwrite publication attempt."""

    status: Literal["CREATED", "ALREADY_PRESENT"]
    destination: Path


def ensure_output_parent(destination: Path) -> None:
    """Create only missing owner directories below an already safe path."""

    _validate_destination_shape(destination)
    parent = destination.parent
    _ensure_directory_chain(parent)


def read_existing_bytes(destination: Path) -> bytes | None:
    """Read an existing regular authority file without following a symlink."""

    _validate_destination_shape(destination)
    try:
        metadata = destination.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CanonicalForecastConflictError("cannot inspect the authority path") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise CanonicalForecastConflictError("authority path is not an owned regular file")
    try:
        return destination.read_bytes()
    except OSError as exc:
        raise CanonicalForecastConflictError("cannot read the existing authority") from exc


def stage_payload(destination: Path, payload_bytes: bytes) -> StagedCanonicalForecast:
    """Write and fsync a temporary payload while leaving the final path absent."""

    _validate_destination_shape(destination)
    if type(payload_bytes) is not bytes:
        raise CanonicalForecastWriterError("payload_bytes must be exact bytes")
    ensure_output_parent(destination)
    if os.path.lexists(destination):
        raise CanonicalForecastConflictError("authority path appeared before staging")

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
            offset += os.write(descriptor, view[offset:])
        os.fsync(descriptor)
        staged = True
        return StagedCanonicalForecast(destination, temporary, payload_bytes)
    except FileExistsError as exc:
        raise CanonicalForecastWriterError("temporary staging name unexpectedly collided") from exc
    except OSError as exc:
        raise CanonicalForecastWriterError("cannot stage canonical forecast safely") from exc
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        if not staged:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def publish_staged(staged: StagedCanonicalForecast) -> CanonicalForecastWriteResult:
    """Atomically create the destination, preserving any competing authority."""

    if type(staged) is not StagedCanonicalForecast:
        raise CanonicalForecastWriterError("staged value has the wrong type")
    destination = staged.destination
    temporary = staged.temporary
    if temporary.parent != destination.parent:
        raise CanonicalForecastWriterError("staged temporary is outside the destination parent")
    try:
        # Keep this as the first operation: the caller samples pre_publish_now
        # immediately before invoking this function.
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            return CanonicalForecastWriteResult("ALREADY_PRESENT", destination)
        _fsync_directory(destination.parent)
        return CanonicalForecastWriteResult("CREATED", destination)
    except OSError as exc:
        raise CanonicalForecastWriterError("atomic authority creation failed") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise CanonicalForecastWriterError("staged temporary cleanup failed") from exc


def _validate_destination_shape(destination: Path) -> None:
    if not destination.is_absolute():
        raise CanonicalForecastWriterError("destination must be an absolute Path")
    if destination == Path(destination.anchor):
        raise CanonicalForecastWriterError("filesystem root is not a valid authority")
    if _OUTPUT_NAME.fullmatch(destination.name) is None:
        raise CanonicalForecastWriterError("destination basename is not canonical")
    if any(part in {"", ".", "..", ".git"} for part in destination.parts):
        raise CanonicalForecastWriterError("destination contains a forbidden path component")
    if any((ancestor / ".git").is_dir() for ancestor in destination.parents):
        raise CanonicalForecastWriterError("authority must be outside every Git worktree")


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
            raise CanonicalForecastWriterError("cannot inspect output directory") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise CanonicalForecastWriterError("output path contains a non-directory component")
        # Existing ancestors may be system-owned (for example ``/Users`` or
        # ``/tmp``).  Ownership is enforced for directories created by this
        # writer through the restrictive mode; existing directories are only
        # required to be real directories rather than symlinks.


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | _ODIRECTORY | _NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "CanonicalForecastConflictError",
    "CanonicalForecastWriteResult",
    "CanonicalForecastWriterError",
    "StagedCanonicalForecast",
    "ensure_output_parent",
    "publish_staged",
    "read_existing_bytes",
    "stage_payload",
]
