"""Read-only resolution and verification of LottoLab storage authorities.

The registry is deliberately declarative.  It records the identity and
provenance of an accepted artifact, while this module resolves only named
locations from that registry.  It never searches a directory, chooses an
artifact by filesystem metadata, creates a database, or opens SQLite in a
write-capable mode.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Final, cast

from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.draw_schema import (
    verify_schema_read_only as verify_draw_schema_read_only,
)

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_VERSION: Final = 1
_DURABLE_ROOT_TOKEN: Final = "LOTTOLAB_APPLICATION_SUPPORT"
_DEFAULT_REGISTRY_PATH: Final = (
    Path(__file__).resolve().parents[4] / "config" / "storage_authorities.toml"
)

CANONICAL_CURRENT: Final = "CANONICAL_CURRENT"
SOURCE_AUTHORITY: Final = "SOURCE_AUTHORITY"
ADOPTED: Final = "ADOPTED"
UNRESOLVED: Final = "UNRESOLVED"
UNAVAILABLE: Final = "UNAVAILABLE"
SUPERSEDED: Final = "SUPERSEDED"
SUBSET: Final = "SUBSET"
RESEARCH_ONLY: Final = "RESEARCH_ONLY"

_ACTIVE_STATUSES: Final = frozenset({CANONICAL_CURRENT, SOURCE_AUTHORITY, ADOPTED})
_SQLITE_SCHEMAS: Final = frozenset(
    {
        "DRAW_DATA_V3",
        "P638_CURRENT_REPLAY",
        "P638_CURRENT_RANKING",
        "P638_ALL10_RANKING",
        "P638_ALL23_RANKING",
        "P638_HISTORICAL_RESULTS_V2",
        "T539_HISTORICAL",
        "REPLAY_SCORING",
    }
)
_REPLAY_TABLES: Final = frozenset(
    {
        "completion",
        "draws",
        "failures",
        "run_metadata",
        "scores",
        "strategy_ledger",
        "strategy_targets",
        "tickets",
    }
)
_KNOWN_CAPABILITIES: Final = (
    "DRAW_DATA",
    "BIG_LOTTO_RAW_HISTORY",
    "BIG_LOTTO_PACKAGED_RECORDS",
    "POWER_LOTTO_HISTORICAL_RESULTS_V2",
    "POWER_LOTTO_CURRENT_REPLAY",
    "POWER_LOTTO_CURRENT_RANKING",
    "POWER_LOTTO_ALL10",
    "POWER_LOTTO_ALL23",
    "DAILY_539_HISTORICAL",
    "REPLAY_SCORING",
)


class StorageAuthorityError(RuntimeError):
    """Base class for fail-closed storage-authority errors."""


class StorageAuthorityRegistryError(StorageAuthorityError):
    """The registry file is absent, malformed, or internally inconsistent."""


class UnknownStorageAuthorityError(StorageAuthorityError):
    """A caller requested an authority or capability not in the registry."""


class StorageAuthorityPathError(StorageAuthorityError):
    """A registry path or explicit path violates the resolver boundary."""


@dataclass(frozen=True, slots=True)
class StorageAuthority:
    """One registry entry and its evidence identity."""

    authority_id: str
    capability: str
    lottery_type: str
    status: str
    location: str
    schema: str
    relative_path: str | None
    sha256: str | None
    immutable: bool
    env_override: str | None
    run_id: str | None
    source_sha256: str | None
    source_replay_sha256: str | None
    source_draw_sha256: str | None
    source_commit: str | None
    source_authority: str | None
    strategy_count: int | None
    draw_count: int | None
    target_count: int | None
    complete_target_count: int | None
    excluded_target_count: int | None
    ticket_count: int | None
    provenance: str
    evidence: tuple[str, ...]
    supersedes: tuple[str, ...]
    superseded_by: str | None
    notes: str


@dataclass(frozen=True, slots=True)
class AuthorityEvidenceCandidate:
    """A non-selected candidate retained for audit and supersession reporting."""

    candidate_id: str
    capability: str
    status: str
    authority_id: str | None
    source_sha256: str | None
    source_replay_sha256: str | None
    source_draw_sha256: str | None
    run_id: str | None
    evidence: tuple[str, ...]
    superseded_by: str | None
    notes: str


@dataclass(frozen=True, slots=True)
class ResolvedStorageAuthority:
    """The result of resolving one named authority without verifying its bytes."""

    authority: StorageAuthority
    path: Path | None
    via_environment_override: bool
    reason: str | None

    @property
    def resolved(self) -> bool:
        return self.path is not None

    def require_path(self) -> Path:
        if self.path is None:
            raise StorageAuthorityError(
                f"storage authority {self.authority.authority_id!r} is unresolved: "
                f"{self.reason or 'no path is registered'}"
            )
        return self.path


@dataclass(frozen=True, slots=True)
class StorageAuthorityVerification:
    """Read-only verification evidence for one registry entry."""

    authority: StorageAuthority
    path: Path | None
    exists: bool
    actual_sha256: str | None
    sha_match: bool | None
    schema_valid: bool | None
    query_only: bool | None
    integrity_ok: bool | None
    error: str | None

    @property
    def passed(self) -> bool | None:
        """Return None for intentionally unresolved entries."""

        if self.path is None:
            return None
        return (
            self.error is None
            and self.exists
            and self.schema_valid is True
            and self.sha_match is not False
            and self.query_only is not False
            and self.integrity_ok is not False
        )


@dataclass(frozen=True, slots=True)
class StorageAuthorityRegistry:
    """Parsed, validated storage-authority registry."""

    version: int
    registry_path: Path
    repository_root: Path
    durable_root_token: str
    authorities: tuple[StorageAuthority, ...]
    candidates: tuple[AuthorityEvidenceCandidate, ...]
    required_capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        authority_ids = [authority.authority_id for authority in self.authorities]
        if len(authority_ids) != len(set(authority_ids)):
            raise StorageAuthorityRegistryError("authority ids must be unique")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise StorageAuthorityRegistryError("evidence candidate ids must be unique")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise StorageAuthorityRegistryError("required capabilities must be unique")

    @classmethod
    def from_file(
        cls,
        path: Path | str | None = None,
        *,
        repository_root: Path | str | None = None,
    ) -> StorageAuthorityRegistry:
        registry_path = _absolute_path(_DEFAULT_REGISTRY_PATH if path is None else Path(path))
        try:
            document = tomllib.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise StorageAuthorityRegistryError(
                f"cannot read storage-authority registry: {registry_path}"
            ) from exc
        version = _required_int(document, "version")
        if version != _REGISTRY_VERSION:
            raise StorageAuthorityRegistryError(
                f"unsupported storage-authority registry version: {version}"
            )
        durable_root_token = _required_text(document, "durable_root")
        if durable_root_token != _DURABLE_ROOT_TOKEN:
            raise StorageAuthorityRegistryError(
                "durable_root must use the logical LottoLab application-support token"
            )
        root = (
            _absolute_path(Path(repository_root))
            if repository_root is not None
            else _absolute_path(registry_path.parent.parent)
        )
        raw_authorities = document.get("authorities", ())
        authorities = tuple(_parse_authority(item) for item in _authority_tables(raw_authorities))
        raw_candidates = document.get("evidence_candidates", ())
        candidates = tuple(
            _parse_candidate(item) for item in _candidate_tables(raw_candidates)
        )
        raw_required = document.get("required_capabilities", ())
        required = _text_sequence(raw_required, "required_capabilities")
        registry = cls(
            version=version,
            registry_path=registry_path,
            repository_root=root,
            durable_root_token=durable_root_token,
            authorities=authorities,
            candidates=candidates,
            required_capabilities=required,
        )
        missing = set(required) - set(registry.capabilities)
        if missing:
            raise StorageAuthorityRegistryError(
                "required capabilities are missing from the registry: "
                + ", ".join(sorted(missing))
            )
        return registry

    load = from_file

    @property
    def capabilities(self) -> tuple[str, ...]:
        return tuple(authority.capability for authority in self.authorities)

    def get(self, authority_or_capability: str) -> StorageAuthority:
        for authority in self.authorities:
            if authority.authority_id == authority_or_capability:
                return authority
        matches = [
            authority
            for authority in self.authorities
            if authority.capability == authority_or_capability
        ]
        if matches:
            return min(matches, key=_capability_priority)
        raise UnknownStorageAuthorityError(
            f"unknown storage authority or capability: {authority_or_capability}"
        )

    def for_capability(self, capability: str) -> StorageAuthority:
        authority = self.get(capability)
        if authority.capability != capability:
            raise UnknownStorageAuthorityError(f"unknown capability: {capability}")
        return authority

    def resolver(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        home: Path | None = None,
    ) -> StorageAuthorityResolver:
        return StorageAuthorityResolver(self, environ=environ, home=home)

    def resolve(
        self,
        authority_or_capability: str,
        *,
        environ: Mapping[str, str] | None = None,
        home: Path | None = None,
        allow_unresolved_override: bool = False,
    ) -> ResolvedStorageAuthority:
        return self.resolver(environ=environ, home=home).resolve(
            authority_or_capability,
            allow_unresolved_override=allow_unresolved_override,
        )


class StorageAuthorityResolver:
    """Resolve and verify only the exact authority named by the registry."""

    def __init__(
        self,
        registry: StorageAuthorityRegistry | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        home: Path | None = None,
    ) -> None:
        self.registry = registry or StorageAuthorityRegistry.from_file()
        self.environ = os.environ if environ is None else environ
        self.home = Path.home() if home is None else home

    @property
    def durable_root(self) -> Path:
        return self.home / "Library" / "Application Support" / "LottoLab"

    def resolve(
        self,
        authority_or_capability: str,
        *,
        allow_unresolved_override: bool = False,
    ) -> ResolvedStorageAuthority:
        authority = self.registry.get(authority_or_capability)
        override = self._environment_override(authority)
        if override is not None:
            if authority.status in _ACTIVE_STATUSES or allow_unresolved_override:
                return ResolvedStorageAuthority(authority, override, True, None)
            return ResolvedStorageAuthority(
                authority,
                None,
                False,
                "an explicit override cannot promote an unresolved authority without permission",
            )
        if authority.status not in _ACTIVE_STATUSES:
            return ResolvedStorageAuthority(
                authority,
                None,
                False,
                f"authority status is {authority.status}",
            )
        if authority.location == "UNRESOLVED":
            if allow_unresolved_override:
                return ResolvedStorageAuthority(
                    authority,
                    None,
                    False,
                    "no explicit environment override is configured",
                )
            return ResolvedStorageAuthority(
                authority,
                None,
                False,
                "authority has no accepted physical location",
            )
        if authority.location == "DRAW_DATA":
            paths = resolve_local_data_paths(environ=self.environ, home=self.home)
            return ResolvedStorageAuthority(authority, paths.database, False, None)
        if authority.location == "DURABLE":
            return ResolvedStorageAuthority(
                authority,
                _safe_join(self.durable_root, authority.relative_path),
                False,
                None,
            )
        if authority.location == "REPOSITORY":
            return ResolvedStorageAuthority(
                authority,
                _safe_join(self.registry.repository_root, authority.relative_path),
                False,
                None,
            )
        raise StorageAuthorityRegistryError(
            f"unsupported storage-authority location: {authority.location}"
        )

    def verify(
        self,
        authority_or_capability: str,
        *,
        deep: bool = True,
        allow_unresolved_override: bool = False,
    ) -> StorageAuthorityVerification:
        resolution = self.resolve(
            authority_or_capability,
            allow_unresolved_override=allow_unresolved_override,
        )
        authority = resolution.authority
        if resolution.path is None:
            return StorageAuthorityVerification(
                authority=authority,
                path=None,
                exists=False,
                actual_sha256=None,
                sha_match=None,
                schema_valid=None,
                query_only=None,
                integrity_ok=None,
                error=resolution.reason,
            )

        path = resolution.path
        if not path.exists() or not path.is_file():
            return StorageAuthorityVerification(
                authority=authority,
                path=path,
                exists=False,
                actual_sha256=None,
                sha_match=False if authority.sha256 else None,
                schema_valid=None,
                query_only=None,
                integrity_ok=None,
                error="registered authority path is missing",
            )

        before_sha = _sha256_file(path)
        sha_match = authority.sha256 is None or before_sha == authority.sha256
        schema_valid: bool | None = None
        query_only: bool | None = None
        integrity_ok: bool | None = None
        error: str | None = None
        try:
            schema_valid = _verify_schema(authority.schema, path)
            if authority.schema in _SQLITE_SCHEMAS:
                query_only, integrity_ok = _probe_sqlite(path, deep=deep)
        except Exception as exc:
            schema_valid = False
            error = f"schema verification failed: {exc}"

        actual_sha = before_sha
        if deep and authority.immutable:
            after_sha = _sha256_file(path)
            if after_sha != before_sha:
                error = "authority bytes changed during read-only verification"
            actual_sha = after_sha

        if not sha_match:
            error = "authority SHA-256 does not match the registry"
        if schema_valid is False and error is None:
            error = "authority schema verifier returned false"
        return StorageAuthorityVerification(
            authority=authority,
            path=path,
            exists=True,
            actual_sha256=actual_sha,
            sha_match=sha_match,
            schema_valid=schema_valid,
            query_only=query_only,
            integrity_ok=integrity_ok,
            error=error,
        )

    check = verify

    def status(self) -> tuple[StorageAuthorityVerification, ...]:
        """Check every registered capability without a full integrity scan."""

        return tuple(
            self.verify(authority.authority_id, deep=False)
            for authority in self.registry.authorities
        )

    def verify_all(self) -> tuple[StorageAuthorityVerification, ...]:
        """Verify every immutable registry authority in read-only mode."""

        return tuple(
            self.verify(authority.authority_id, deep=True)
            for authority in self.registry.authorities
            if authority.immutable
        )

    def _environment_override(self, authority: StorageAuthority) -> Path | None:
        if authority.env_override is None:
            return None
        configured = self.environ.get(authority.env_override)
        if configured is None or not configured.strip():
            return None
        path = Path(configured).expanduser()
        if not path.is_absolute():
            raise StorageAuthorityPathError(
                f"{authority.env_override} must be an absolute path"
            )
        return path


def _verify_schema(schema: str, path: Path) -> bool:
    if schema == "DRAW_DATA_V3":
        return verify_draw_schema_read_only(LocalDataPaths(path.parent, path))
    if schema == "P638_CURRENT_REPLAY":
        return _verify_p638_replay_schema(path)
    if schema == "P638_CURRENT_RANKING":
        from lottolab.infrastructure.persistence.p638_current_ranking_schema import (
            verify_schema_read_only,
        )

        return verify_schema_read_only(path)
    if schema == "P638_ALL10_RANKING":
        from lottolab.infrastructure.persistence.p638_all10_ranking_schema import (
            verify_schema_read_only,
        )

        return verify_schema_read_only(path)
    if schema == "P638_ALL23_RANKING":
        from lottolab.infrastructure.persistence.p638_all23_ranking_schema import (
            verify_schema_read_only,
        )

        return verify_schema_read_only(path)
    if schema == "P638_HISTORICAL_RESULTS_V2":
        from lottolab.infrastructure.persistence.historical_schema import (
            verify_schema_read_only,
        )

        return verify_schema_read_only(path)
    if schema == "T539_HISTORICAL":
        from lottolab.infrastructure.persistence.t539_historical_repositories import (
            verify_schema_read_only,
        )

        return verify_schema_read_only(path)
    if schema == "REPLAY_SCORING":
        from lottolab.infrastructure.persistence.replay_scoring_schema import (
            verify_schema_read_only,
        )

        return verify_schema_read_only(path)
    if schema == "B649_MULTI_TICKET_HISTORICAL_RECORDS_V2":
        from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
            PackagedB649MultiTicketRecordReader,
        )

        PackagedB649MultiTicketRecordReader().read()
        return True
    if schema == "NONE":
        return True
    raise StorageAuthorityRegistryError(f"unknown authority schema verifier: {schema}")


def _verify_p638_replay_schema(path: Path) -> bool:
    with _open_sqlite_read_only(path) as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if tables != set(_REPLAY_TABLES):
            raise StorageAuthorityError("P638 replay tables do not match the sealed contract")
        views = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'view'"
            )
        }
        if "replay_output" not in views:
            raise StorageAuthorityError("P638 replay output view is missing")
        metadata = connection.execute(
            "SELECT lottery_type, source_count, status FROM run_metadata"
        ).fetchall()
        completion = connection.execute(
            "SELECT status, failed_targets FROM completion"
        ).fetchall()
        if len(metadata) != 1 or len(completion) != 1:
            raise StorageAuthorityError("P638 replay metadata must contain one completed run")
        if metadata[0][0] != "POWER_LOTTO" or metadata[0][2] != "COMPLETE":
            raise StorageAuthorityError("P638 replay metadata is not a completed POWER_LOTTO run")
        if int(metadata[0][1]) <= 0 or completion[0][0] != "COMPLETE":
            raise StorageAuthorityError("P638 replay completion metadata is invalid")
        if int(completion[0][1]) != 0:
            raise StorageAuthorityError("P638 replay has failed targets")
    return True


def _probe_sqlite(path: Path, *, deep: bool) -> tuple[bool, bool | None]:
    with _open_sqlite_read_only(path) as connection:
        query_only = connection.execute("PRAGMA query_only").fetchone()
        if query_only != (1,):
            raise StorageAuthorityError("SQLite query_only was not enabled")
        integrity_ok: bool | None = None
        if deep:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            integrity_ok = result == ("ok",)
            if not integrity_ok:
                raise StorageAuthorityError("SQLite integrity_check did not return ok")
    return True, integrity_ok


def _open_sqlite_read_only(path: Path) -> _ReadOnlyConnection:
    try:
        connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            isolation_level=None,
        )
        connection.execute("PRAGMA query_only = ON")
    except sqlite3.DatabaseError as exc:
        raise StorageAuthorityError("cannot open SQLite authority read-only") from exc
    return _ReadOnlyConnection(connection)


class _ReadOnlyConnection:
    """Context manager wrapper that closes a read-only SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __enter__(self) -> sqlite3.Connection:
        return self._connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._connection.close()


def _safe_join(root: Path, relative_path: str | None) -> Path:
    if relative_path is None:
        raise StorageAuthorityPathError("a registered location is missing relative_path")
    relative = Path(relative_path)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or "\x00" in relative_path
        or relative_path.startswith("~")
    ):
        raise StorageAuthorityPathError(
            f"registry path must be a safe root-relative path: {relative_path!r}"
        )
    root_resolved = root.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise StorageAuthorityPathError("registry path escapes its declared root")
    return candidate


def _capability_priority(authority: StorageAuthority) -> int:
    if authority.status == CANONICAL_CURRENT:
        return 0
    if authority.status == ADOPTED:
        return 1
    if authority.status == SOURCE_AUTHORITY:
        return 2
    return 3


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_path(path: Path) -> Path:
    return path.expanduser().absolute()


def _authority_tables(value: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, Mapping):
        tables: list[Mapping[str, object]] = []
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            if not isinstance(key, str) or not isinstance(item, Mapping):
                raise StorageAuthorityRegistryError("authorities must contain tables")
            table = dict(cast(Mapping[str, object], item))
            table.setdefault("id", key)
            tables.append(table)
        return tuple(tables)
    if isinstance(value, list):
        items = cast(list[object], value)
        return tuple(_mapping(item, "authorities[]") for item in items)
    if value == ():
        return ()
    raise StorageAuthorityRegistryError("authorities must be an array of tables")


def _candidate_tables(value: object) -> tuple[Mapping[str, object], ...]:
    if value == ():
        return ()
    return _authority_tables(value)


def _parse_authority(raw: Mapping[str, object]) -> StorageAuthority:
    relative_path = _optional_text(raw, "relative_path")
    if relative_path is not None:
        _safe_relative_definition(relative_path)
    sha256 = _optional_sha(raw, "sha256")
    status = _required_text(raw, "status")
    if status not in _ACTIVE_STATUSES | {
        UNRESOLVED,
        UNAVAILABLE,
        SUPERSEDED,
        SUBSET,
        RESEARCH_ONLY,
    }:
        raise StorageAuthorityRegistryError(f"unsupported authority status: {status}")
    location = _required_text(raw, "location").upper()
    if location in {"DURABLE", "REPOSITORY"} and relative_path is None:
        raise StorageAuthorityRegistryError(
            f"authority {_required_text(raw, 'id')} needs relative_path for {location}"
        )
    return StorageAuthority(
        authority_id=_required_text(raw, "id"),
        capability=_required_text(raw, "capability"),
        lottery_type=_required_text(raw, "lottery_type"),
        status=status,
        location=location,
        schema=_required_text(raw, "schema"),
        relative_path=relative_path,
        sha256=sha256,
        immutable=_optional_bool(raw, "immutable", default=False),
        env_override=_optional_text(raw, "env_override"),
        run_id=_optional_text(raw, "run_id"),
        source_sha256=_optional_sha(raw, "source_sha256"),
        source_replay_sha256=_optional_sha(raw, "source_replay_sha256"),
        source_draw_sha256=_optional_sha(raw, "source_draw_sha256"),
        source_commit=_optional_text(raw, "source_commit"),
        source_authority=_optional_text(raw, "source_authority"),
        strategy_count=_optional_int(raw, "strategy_count"),
        draw_count=_optional_int(raw, "draw_count"),
        target_count=_optional_int(raw, "target_count"),
        complete_target_count=_optional_int(raw, "complete_target_count"),
        excluded_target_count=_optional_int(raw, "excluded_target_count"),
        ticket_count=_optional_int(raw, "ticket_count"),
        provenance=_optional_text(raw, "provenance") or "",
        evidence=_text_sequence(raw.get("evidence", ()), "evidence"),
        supersedes=_text_sequence(raw.get("supersedes", ()), "supersedes"),
        superseded_by=_optional_text(raw, "superseded_by"),
        notes=_optional_text(raw, "notes") or "",
    )


def _parse_candidate(raw: Mapping[str, object]) -> AuthorityEvidenceCandidate:
    return AuthorityEvidenceCandidate(
        candidate_id=_required_text(raw, "id"),
        capability=_required_text(raw, "capability"),
        status=_required_text(raw, "status"),
        authority_id=_optional_text(raw, "authority_id"),
        source_sha256=_optional_sha(raw, "source_sha256"),
        source_replay_sha256=_optional_sha(raw, "source_replay_sha256"),
        source_draw_sha256=_optional_sha(raw, "source_draw_sha256"),
        run_id=_optional_text(raw, "run_id"),
        evidence=_text_sequence(raw.get("evidence", ()), "evidence"),
        superseded_by=_optional_text(raw, "superseded_by"),
        notes=_optional_text(raw, "notes") or "",
    )


def _safe_relative_definition(value: str) -> None:
    relative = Path(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or "\x00" in value
        or value.startswith("~")
    ):
        raise StorageAuthorityPathError(
            f"registry path must be a safe root-relative path: {value!r}"
        )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StorageAuthorityRegistryError(f"{label} must be a table")
    return cast(Mapping[str, object], value)


def _required_text(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StorageAuthorityRegistryError(f"registry field {key!r} must be a non-empty string")
    return value


def _optional_text(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StorageAuthorityRegistryError(f"registry field {key!r} must be a string")
    return value


def _required_int(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StorageAuthorityRegistryError(f"registry field {key!r} must be an integer")
    return value


def _optional_int(mapping: Mapping[str, object], key: str) -> int | None:
    value = mapping.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise StorageAuthorityRegistryError(f"registry field {key!r} must be an integer")
    return value


def _optional_bool(mapping: Mapping[str, object], key: str, *, default: bool) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise StorageAuthorityRegistryError(f"registry field {key!r} must be boolean")
    return value


def _optional_sha(mapping: Mapping[str, object], key: str) -> str | None:
    value = _optional_text(mapping, key)
    if value is not None and _SHA256.fullmatch(value) is None:
        raise StorageAuthorityRegistryError(f"registry field {key!r} must be a SHA-256 hex digest")
    return value


def _text_sequence(value: object, label: str) -> tuple[str, ...]:
    if value == () or value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise StorageAuthorityRegistryError(f"registry field {label!r} must be an array of strings")
    values: list[str] = []
    items = cast(Sequence[object], value)
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise StorageAuthorityRegistryError(
                f"registry field {label!r} must contain non-empty strings"
            )
        values.append(item)
    return tuple(values)


__all__ = [
    "ADOPTED",
    "CANONICAL_CURRENT",
    "RESEARCH_ONLY",
    "SOURCE_AUTHORITY",
    "SUBSET",
    "SUPERSEDED",
    "UNAVAILABLE",
    "UNRESOLVED",
    "AuthorityEvidenceCandidate",
    "ResolvedStorageAuthority",
    "StorageAuthority",
    "StorageAuthorityError",
    "StorageAuthorityPathError",
    "StorageAuthorityRegistry",
    "StorageAuthorityRegistryError",
    "StorageAuthorityResolver",
    "StorageAuthorityVerification",
]
