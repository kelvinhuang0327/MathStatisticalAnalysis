"""Durable create-once filesystem storage for Next-Draw Recommendation seals.

Scope note: ``lottolab.infrastructure.pre_outcome_target_store`` defends its
create-once target-authority record against adversarial concurrent-writer and
symlink-race conditions with directory-descriptor-pinned syscalls, because
that store is the sole immutable authority a *prediction* is later scored
against. This seal store sits one layer above an already-accepted
registration (see ``lottolab.application.use_cases.seal_next_draw_recommendation``)
in the same local, single-operator research tool; it is durable (fsynced) and
create-once (an existing record path is never opened for writing), and every
record is self-verifying (``NextDrawRecommendationSeal.seal_digest`` -- a
tampered file fails closed on read), but it does not re-implement that
sibling module's full filesystem-adversary hardening. If this store is ever
exposed to a multi-writer or hostile-filesystem environment, extend it (or
delegate to) that hardened pattern rather than assuming this scope still
applies.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lottolab.application.use_cases.get_next_draw_recommendation_lifecycle import (
    GetNextDrawRecommendationLifecycle,
)
from lottolab.application.use_cases.seal_next_draw_recommendation import (
    SealNextDrawRecommendation,
)
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationSeal,
)
from lottolab.domain.prospective_observer import CreateOnceOutcome, ObservationTarget
from lottolab.evidence.next_draw_recommendation_evidence import (
    NextDrawRecommendationEvidenceArtifact,
)
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths, resolve_local_data_paths
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    SQLiteOfficialOutcomePresenceProbe,
    SQLitePreOutcomeCausalHistoryAuthority,
    compose_pre_outcome_target_operational_service,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog

NEXT_DRAW_RECOMMENDATION_SEAL_DIRECTORY_NAME = "next-draw-recommendation-seals-v1"
_RECORD_NAME = "seal.json"
_MAX_RECORD_BYTES = 4 * 1024 * 1024


class NextDrawRecommendationSealStoreError(RuntimeError):
    """Base class for seal-store failures owned by this module."""


class NextDrawRecommendationSealStoreCorruptionError(NextDrawRecommendationSealStoreError):
    """The store's own on-disk layout violates its create-once contract."""


class FileSystemNextDrawRecommendationSealStore:
    """Caller-rooted, restart-safe create-once seal store, keyed by target.

    Construction performs no filesystem I/O and never creates the root
    directory -- a read-only lookup against a lottery type with no accepted
    seal yet must have zero persistence side effects. ``create_seal`` is the
    only method that ever creates a directory, lazily, at write time.
    """

    def __init__(self, root: str | Path) -> None:
        if not str(root):
            raise ValueError("root must be a non-empty filesystem path")
        self._root = Path(root).absolute()

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def record_path_for(root: Path, target: ObservationTarget) -> Path:
        return root / _target_directory(target) / _RECORD_NAME

    def get_seal(self, target: ObservationTarget) -> NextDrawRecommendationSeal | None:
        path = self.record_path_for(self._root, target)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            # No seal for this target -- including the common case where the
            # store root itself has never been created, because no seal has
            # ever been accepted for this lottery type.
            return None
        except (IsADirectoryError, NotADirectoryError) as exc:
            raise NextDrawRecommendationSealStoreCorruptionError(
                f"seal record path is not a plain file: {path}"
            ) from exc
        if len(raw) > _MAX_RECORD_BYTES:
            raise NextDrawRecommendationSealStoreCorruptionError(
                f"seal record exceeds the maximum accepted size: {path}"
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NextDrawRecommendationSealStoreCorruptionError(
                f"seal record is not valid UTF-8 JSON: {path}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise NextDrawRecommendationSealStoreCorruptionError(
                f"seal record does not decode to a JSON object: {path}"
            )
        # NextDrawRecommendationSeal.from_canonical_dict self-verifies
        # seal_digest; a tampered or hand-edited record fails closed here
        # with NextDrawRecommendationSealTamperError (a ValueError, not
        # caught -- callers must see tamper as a hard failure, never a
        # silent None).
        seal = NextDrawRecommendationSeal.from_canonical_dict(payload)
        if seal.target != target:
            raise NextDrawRecommendationSealStoreCorruptionError(
                f"seal record at {path} is bound to a different target than its own path"
            )
        return seal

    def create_seal(self, seal: NextDrawRecommendationSeal) -> CreateOnceOutcome:
        if type(seal) is not NextDrawRecommendationSeal:
            raise ValueError("seal must be a NextDrawRecommendationSeal")
        if self._root.exists() and (not self._root.is_dir() or self._root.is_symlink()):
            raise NextDrawRecommendationSealStoreCorruptionError(
                f"seal store root is not a plain directory: {self._root}"
            )
        target_dir = self._root / _target_directory(seal.target)
        os.makedirs(target_dir, exist_ok=True)
        path = target_dir / _RECORD_NAME
        payload = (
            json.dumps(
                seal.canonical_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
            + "\n"
        ).encode("utf-8")
        try:
            # O_EXCL makes the create atomic and exclusive: a record that
            # already exists at this exact path is never opened for writing,
            # truncated, or overwritten by this call.
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        except FileExistsError:
            return CreateOnceOutcome.CONFLICT
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        _best_effort_fsync_directory(target_dir)
        return CreateOnceOutcome.INSERTED


def _target_directory(target: ObservationTarget) -> Path:
    # lottery_type is a closed enum value, draw_date is machine-formatted
    # ISO-8601, and ObservationTarget.__post_init__ already restricts
    # draw_number to 1-32 ASCII decimal digits -- every segment is a safe,
    # collision-isolated path component before it ever reaches this module.
    return Path(target.lottery_type.value) / f"{target.draw_date.isoformat()}_{target.draw_number}"


def _best_effort_fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def resolve_next_draw_recommendation_seal_root(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve the one canonical local seal-store root without creating it."""

    local_data = resolve_local_data_paths(environ=environ, home=home)
    return local_data.data_directory / NEXT_DRAW_RECOMMENDATION_SEAL_DIRECTORY_NAME


@dataclass(frozen=True, slots=True)
class NextDrawRecommendationSealOperationalComposition:
    """Wired, ready-to-use seal command and read-only lifecycle reader."""

    seal_root: Path
    local_data: LocalDataPaths
    seal_command: SealNextDrawRecommendation
    lifecycle_reader: GetNextDrawRecommendationLifecycle


CausalHistoryRowsFactory = Callable[..., tuple[CausalDrawRow, ...]]
EvidenceArtifactFactory = Callable[[], NextDrawRecommendationEvidenceArtifact | None]


def compose_next_draw_recommendation_seal_operational_service(
    *,
    catalog: StrategyCatalog,
    evidence_factory: EvidenceArtifactFactory,
    causal_history_rows_factory: CausalHistoryRowsFactory,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> NextDrawRecommendationSealOperationalComposition:
    """Compose the canonical local adapters without reading or writing state.

    Reuses the existing pre-outcome target authority composition for target
    resolution, causal-history authority, and outcome-presence evidence --
    the seal layer adds only its own durable store and orchestration.
    """

    target_composition = compose_pre_outcome_target_operational_service(
        environ=environ, home=home, clock=clock
    )
    selected_clock = _utc_now if clock is None else clock
    seal_root = resolve_next_draw_recommendation_seal_root(environ=environ, home=home)
    store = FileSystemNextDrawRecommendationSealStore(seal_root)
    presence_probe = SQLiteOfficialOutcomePresenceProbe(target_composition.paths.local_data)
    causal_history_authority = SQLitePreOutcomeCausalHistoryAuthority(
        target_composition.paths.local_data
    )
    future_draw_identity_reader = SQLiteFutureDrawIdentityReader(
        target_composition.paths.local_data
    )

    seal_command = SealNextDrawRecommendation(
        catalog=catalog,
        operational_service=target_composition.service,
        causal_history_authority=causal_history_authority,
        causal_history_rows_factory=causal_history_rows_factory,
        evidence_factory=evidence_factory,
        outcome_presence_probe=presence_probe,
        seal_store=store,
        clock=selected_clock,
    )
    lifecycle_reader = GetNextDrawRecommendationLifecycle(
        future_draw_identity_reader=future_draw_identity_reader,
        outcome_presence_probe=presence_probe,
        seal_reader=store,
        clock=selected_clock,
    )
    return NextDrawRecommendationSealOperationalComposition(
        seal_root=seal_root,
        local_data=target_composition.paths.local_data,
        seal_command=seal_command,
        lifecycle_reader=lifecycle_reader,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "NEXT_DRAW_RECOMMENDATION_SEAL_DIRECTORY_NAME",
    "CausalHistoryRowsFactory",
    "EvidenceArtifactFactory",
    "FileSystemNextDrawRecommendationSealStore",
    "NextDrawRecommendationSealOperationalComposition",
    "NextDrawRecommendationSealStoreCorruptionError",
    "NextDrawRecommendationSealStoreError",
    "compose_next_draw_recommendation_seal_operational_service",
    "resolve_next_draw_recommendation_seal_root",
]
