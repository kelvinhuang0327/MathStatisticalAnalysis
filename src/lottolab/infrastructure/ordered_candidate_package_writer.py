"""Owner-only atomic absent-root writer for ordered-candidate packages."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lottolab.evidence.canonical_json import sha256_hex
from lottolab.evidence.ordered_candidate_emission_package import (
    OrderedCandidateEmissionPackage,
    sha256sums_bytes,
    verify_ordered_candidate_emission_package,
)

_OUTPUT_BASENAME = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
    flags=re.ASCII,
)
_PROTECTED_BINARY_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
}


class OrderedCandidatePackageWriterError(RuntimeError):
    """The package could not be sealed without violating writer safety."""


class OrderedCandidatePackageCleanupError(OrderedCandidatePackageWriterError):
    """Failure cleanup stopped because staging ownership was no longer exact."""


@dataclass(frozen=True, slots=True)
class _CreatedEntry:
    path: Path
    kind: str
    device: int
    inode: int


class OrderedCandidatePackageWriter:
    """Write, re-read, verify, and atomically seal one package."""

    def write_package(
        self,
        output_directory: Path,
        package: OrderedCandidateEmissionPackage,
    ) -> None:
        verify_ordered_candidate_emission_package(package)
        output = _validated_output_directory(output_directory)
        parent = output.parent
        staging = parent / f".{output.name}.p336-staging"
        if _lexists(staging):
            raise OrderedCandidatePackageWriterError(
                "the exact staging sibling already exists"
            )

        created: dict[Path, _CreatedEntry] = {}
        renamed = False
        try:
            _mkdir_recorded(staging, created)
            for item in package.emission_files:
                destination = staging.joinpath(*item.relative_path.split("/"))
                _ensure_recorded_directories(staging, destination.parent, created)
                _write_recorded_file(destination, item.data, created)

            manifest_path = staging / "manifest.json"
            _write_recorded_file(manifest_path, package.manifest_bytes, created)
            if manifest_path.read_bytes() != package.manifest_bytes:
                raise OrderedCandidatePackageWriterError(
                    "manifest reread differs from the canonical bytes"
                )
            verify_ordered_candidate_emission_package(package)

            sums_path = staging / "SHA256SUMS"
            _write_recorded_file(sums_path, sha256sums_bytes(package), created)
            _verify_staged_files(staging, package)
            _fsync_directories(staging)

            if _lexists(output):
                raise OrderedCandidatePackageWriterError(
                    "the final output root appeared before sealing"
                )
            os.rename(staging, output)
            renamed = True
            _fsync_directory(parent)
        except BaseException as exc:
            if not renamed and _lexists(staging):
                try:
                    _cleanup_recorded_staging(staging, created)
                except OrderedCandidatePackageCleanupError as cleanup_exc:
                    raise cleanup_exc from exc
            if isinstance(exc, OrderedCandidatePackageWriterError):
                raise
            raise OrderedCandidatePackageWriterError(
                "package sealing failed safely"
            ) from exc


def _validated_output_directory(output_directory: Path) -> Path:
    if not isinstance(cast(object, output_directory), Path):
        raise OrderedCandidatePackageWriterError("output_directory must be a Path")
    raw = str(output_directory)
    if not output_directory.is_absolute():
        raise OrderedCandidatePackageWriterError("output root must be absolute")
    if output_directory == Path(output_directory.anchor):
        raise OrderedCandidatePackageWriterError("filesystem root is forbidden")
    if _OUTPUT_BASENAME.fullmatch(output_directory.name) is None:
        raise OrderedCandidatePackageWriterError("output basename is not canonical")
    if "/./" in raw or "/../" in raw or raw.endswith(("/.", "/..")):
        raise OrderedCandidatePackageWriterError("path traversal is forbidden")
    if any(part in {".git", "LotteryNew"} for part in output_directory.parts):
        raise OrderedCandidatePackageWriterError("protected path component is forbidden")
    if any(raw.lower().endswith(suffix) for suffix in _PROTECTED_BINARY_SUFFIXES):
        raise OrderedCandidatePackageWriterError("database-like output roots are forbidden")
    if _lexists(output_directory):
        raise OrderedCandidatePackageWriterError("final output root must be absent")

    parent = output_directory.parent
    _validate_existing_directory(parent, require_owner_mode=True)
    _reject_symlink_components(parent)
    for ancestor in (parent, *parent.parents):
        marker = ancestor / ".git"
        if _lexists(marker):
            raise OrderedCandidatePackageWriterError(
                "output root must be outside every Git worktree"
            )
    return output_directory


def _validate_existing_directory(path: Path, *, require_owner_mode: bool) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise OrderedCandidatePackageWriterError(
            "output parent must pre-exist"
        ) from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise OrderedCandidatePackageWriterError(
            "output parent must be a non-symlink directory"
        )
    if metadata.st_uid != os.getuid():
        raise OrderedCandidatePackageWriterError(
            "output parent must be owned by the current user"
        )
    if require_owner_mode and stat.S_IMODE(metadata.st_mode) != 0o700:
        raise OrderedCandidatePackageWriterError(
            "output parent mode must be exactly 0700"
        )


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise OrderedCandidatePackageWriterError(
                "output parent path is not fully present"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise OrderedCandidatePackageWriterError(
                "symlinked output path components are forbidden"
            )


def _mkdir_recorded(
    path: Path,
    created: dict[Path, _CreatedEntry],
) -> None:
    os.mkdir(path, 0o700)
    os.chmod(path, 0o700, follow_symlinks=False)
    _record_created(path, "directory", created)


def _ensure_recorded_directories(
    root: Path,
    directory: Path,
    created: dict[Path, _CreatedEntry],
) -> None:
    relative = directory.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if current in created:
            continue
        if _lexists(current):
            raise OrderedCandidatePackageWriterError(
                "unexpected content appeared in staging"
            )
        _mkdir_recorded(current, created)


def _write_recorded_file(
    path: Path,
    data: bytes,
    created: dict[Path, _CreatedEntry],
) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        _record_created(path, "file", created)
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(descriptor, view[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _record_created(
    path: Path,
    kind: str,
    created: dict[Path, _CreatedEntry],
) -> None:
    metadata = path.lstat()
    actual_kind = (
        "directory"
        if stat.S_ISDIR(metadata.st_mode)
        else "file"
        if stat.S_ISREG(metadata.st_mode)
        else "other"
    )
    if actual_kind != kind:
        raise OrderedCandidatePackageWriterError(
            "created staging entry has an unexpected type"
        )
    created[path] = _CreatedEntry(
        path=path,
        kind=kind,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )


def _verify_staged_files(
    staging: Path,
    package: OrderedCandidateEmissionPackage,
) -> None:
    expected = {
        item.relative_path: item.file_sha256 for item in package.emission_files
    }
    expected["manifest.json"] = sha256_hex(package.manifest_bytes)
    for relative_path, digest in expected.items():
        path = staging.joinpath(*relative_path.split("/"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise OrderedCandidatePackageWriterError(
                "staged file digest verification failed"
            )
    if (staging / "SHA256SUMS").read_bytes() != sha256sums_bytes(package):
        raise OrderedCandidatePackageWriterError("SHA256SUMS reread verification failed")


def _fsync_directories(root: Path) -> None:
    directories = [root]
    directories.extend(path for path in root.rglob("*") if path.is_dir())
    for directory in sorted(
        directories,
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        _fsync_directory(directory)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _cleanup_recorded_staging(
    staging: Path,
    created: dict[Path, _CreatedEntry],
) -> None:
    observed: dict[Path, tuple[str, int, int]] = {}
    for root, directory_names, file_names in os.walk(staging, topdown=True):
        root_path = Path(root)
        metadata = root_path.lstat()
        observed[root_path] = ("directory", metadata.st_dev, metadata.st_ino)
        for name in (*directory_names, *file_names):
            child = root_path / name
            child_metadata = child.lstat()
            kind = (
                "directory"
                if stat.S_ISDIR(child_metadata.st_mode)
                else "file"
                if stat.S_ISREG(child_metadata.st_mode)
                else "other"
            )
            observed[child] = (kind, child_metadata.st_dev, child_metadata.st_ino)
    expected = {
        path: (entry.kind, entry.device, entry.inode)
        for path, entry in created.items()
    }
    if observed != expected:
        raise OrderedCandidatePackageCleanupError(
            "unexpected or replaced staging content prevents safe cleanup"
        )
    for path, entry in sorted(
        created.items(),
        key=lambda pair: len(pair[0].parts),
        reverse=True,
    ):
        if entry.kind == "file":
            path.unlink()
        else:
            path.rmdir()


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


__all__ = [
    "OrderedCandidatePackageCleanupError",
    "OrderedCandidatePackageWriter",
    "OrderedCandidatePackageWriterError",
]
