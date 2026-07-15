"""Hash-pinned snapshot intake from the legacy system.

The legacy repo (~/Kelvin-WorkSpace/LotteryNew) is never written or imported.
It exports files; we verify every file against a committed manifest before
use. Payloads live under data/ (gitignored); manifests under data/manifests/
are committed. Populated for real in migration batch 3.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    relative_path: str
    sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_snapshot(root: Path, entries: tuple[SnapshotEntry, ...]) -> None:
    """Raise ValueError on the first hash mismatch; silence means verified."""
    for entry in entries:
        actual = file_sha256(root / entry.relative_path)
        if actual != entry.sha256:
            raise ValueError(
                f"snapshot hash mismatch for {entry.relative_path}: "
                f"expected {entry.sha256}, got {actual}"
            )
