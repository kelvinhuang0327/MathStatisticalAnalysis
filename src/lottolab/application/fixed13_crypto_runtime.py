"""Canonical OpenSSL runtime resolution for fixed-13 RFC3161 verification.

macOS ships ``/usr/bin/openssl`` as LibreSSL, not OpenSSL; on this and other
hosts, letting an ambient ``shutil.which`` lookup pick whichever ``openssl``
resolves first on ``PATH`` can silently hand fixed-13 RFC3161 verification
a backend that
*looks* like it works (it happily verifies a narrow, legacy 2-tier /
implicit-SHA-1-ESS profile) but cannot correctly verify the
ESSCertIDv2 / multi-tier-chain profile fixed-13 production receipts
actually use. That gap is invisible from a test suite that both mints and
verifies its own tokens with the same ambient backend.

This module replaces that ambient lookup with an explicit, ordered
resolution that never searches ``PATH`` and never trusts version-string
identification alone: every candidate must also independently pass the
committed production-profile golden-vector self-test in
``tests/fixtures/fixed13_rfc3161/`` before it can be used. See
:func:`resolve_openssl_binary` for the exact resolution order.

Every public entry point here is fail-closed and does not raise for an
expected/foreseeable unavailable-runtime condition: :func:`resolve_openssl_binary`
always returns a typed :class:`Fixed13CryptoRuntimeResolution`, so a caller
that wants return-value-style fail-closed handling (as
``fixed13_pre_outcome_timing_receipt`` does) never needs to catch anything.
:func:`require_capable_openssl_binary` is a thin exception-raising
convenience for callers that already use an exception-based fail-closed
convention (as ``fixed13_rfc3161_provider_config`` does).

This module never sends a timestamp request, never transmits a digest, and
never contacts a network timestamp authority; the golden-vector self-test
only runs ``openssl ts -verify`` against already-committed, already-issued
public certificate/token fixture data.
"""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

LOTTOLAB_FIXED13_CRYPTO_RUNTIME_SCHEMA_VERSION: Final = "LOTTOLAB_FIXED13_CRYPTO_RUNTIME_V1"

_ENV_OPENSSL_BINARY: Final = "LOTTOLAB_FIXED13_OPENSSL_BINARY"
_MINIMUM_OPENSSL_MAJOR: Final = 3
_OPENSSL_PROBE_TIMEOUT_SECONDS: Final = 15

_DEFAULT_CONFIG_PATH: Final = (
    Path(__file__).resolve().parents[3] / "config" / "fixed13_crypto_runtime.toml"
)
_DEFAULT_GOLDEN_VECTOR_DIR: Final = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "fixed13_rfc3161"
)

_GOLDEN_VECTOR_METADATA_FILENAME: Final = "golden_vector.json"
_GOLDEN_VECTOR_TOKEN_FILENAME: Final = "token.tsr"
_GOLDEN_VECTOR_ROOT_FILENAME: Final = "root_cert.pem"
_GOLDEN_VECTOR_INTERMEDIATE_FILENAME: Final = "intermediate_cert.pem"

_SOURCE_TIER_EXPLICIT_ARGUMENT: Final = "EXPLICIT_ARGUMENT"
_SOURCE_TIER_ENVIRONMENT_OVERRIDE: Final = "ENVIRONMENT_OVERRIDE"
_SOURCE_TIER_CONFIGURED_PINNED_BINARY: Final = "CONFIGURED_PINNED_BINARY"
_SOURCE_TIER_DECLARED_CANDIDATE: Final = "DECLARED_CANDIDATE"


class Fixed13CryptoRuntimeUnavailableReason(StrEnum):
    """Why :func:`resolve_openssl_binary` could not qualify a binary."""

    NO_RUNTIME_CONFIGURED = "NO_RUNTIME_CONFIGURED"
    BINARY_NOT_FOUND = "BINARY_NOT_FOUND"
    BINARY_NOT_EXECUTABLE = "BINARY_NOT_EXECUTABLE"
    VERSION_PROBE_FAILED = "VERSION_PROBE_FAILED"
    NOT_OPENSSL = "NOT_OPENSSL"
    OPENSSL_MAJOR_TOO_OLD = "OPENSSL_MAJOR_TOO_OLD"
    GOLDEN_VECTOR_MISSING = "GOLDEN_VECTOR_MISSING"
    GOLDEN_VECTOR_PROBE_FAILED = "GOLDEN_VECTOR_PROBE_FAILED"
    GOLDEN_VECTOR_REJECTED = "GOLDEN_VECTOR_REJECTED"
    NO_CAPABLE_CANDIDATE_FOUND = "NO_CAPABLE_CANDIDATE_FOUND"


@dataclass(frozen=True, slots=True)
class Fixed13CryptoRuntimeResolution:
    """Outcome of resolving and capability-validating one openssl binary.

    ``source_tier`` records which resolution tier produced ``binary_path``
    (or, on failure, which tier was being attempted) for diagnostics; it is
    not part of the pass/fail contract itself.
    """

    capable: bool
    binary_path: str | None
    openssl_version_text: str | None
    source_tier: str | None
    reason: Fixed13CryptoRuntimeUnavailableReason | None

    def __post_init__(self) -> None:
        if type(self.capable) is not bool:
            raise ValueError("capable must be an exact boolean")
        if self.capable:
            if self.binary_path is None or self.openssl_version_text is None:
                raise ValueError(
                    "a capable resolution must carry binary_path and openssl_version_text"
                )
            if self.reason is not None:
                raise ValueError("a capable resolution must not carry a reason code")
        else:
            if self.binary_path is not None or self.openssl_version_text is not None:
                raise ValueError(
                    "an incapable resolution must not carry binary_path or version text"
                )
            if self.reason is None:
                raise ValueError("an incapable resolution must carry a reason code")


class Fixed13CryptoRuntimeUnavailableError(RuntimeError):
    """Raised only by :func:`require_capable_openssl_binary`, never by
    :func:`resolve_openssl_binary` itself."""


_capability_cache: dict[str, Fixed13CryptoRuntimeResolution] = {}
"""Process-local, unbounded for the life of the process. Not part of the
public API; tests that need isolation import this dict directly and clear
it (mirrors how this project's other fixed-13 tests reach private module
state, e.g. ``fixed13_pre_outcome_timing_receipt._parse_tst_info``)."""


def _probe_openssl_version(binary_path: str) -> str | None:
    try:
        result = subprocess.run(
            [binary_path, "version"],
            capture_output=True,
            timeout=_OPENSSL_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    text = result.stdout.decode("ascii", errors="replace").strip()
    return text or None


def _parse_openssl_version(version_text: str) -> tuple[bool, int | None]:
    """Return ``(is_openssl_not_libressl, major_version)``.

    LibreSSL's ``version`` output starts with ``"LibreSSL "``, never
    ``"OpenSSL "`` -- this is the same textual distinction the CTO's own
    host inspection used to identify the defect, made exact and load-bearing
    here rather than left as an informal read of the banner.
    """

    if not version_text.startswith("OpenSSL "):
        return False, None
    remainder = version_text.removeprefix("OpenSSL ")
    dotted = remainder.split(" ", 1)[0]
    major_text = dotted.split(".", 1)[0]
    if not major_text.isdigit():
        return True, None
    return True, int(major_text)


def _run_golden_vector_self_test(
    binary_path: str, golden_vector_dir: Path
) -> Fixed13CryptoRuntimeUnavailableReason | None:
    """Return ``None`` on success, else the specific rejection reason."""

    metadata_path = golden_vector_dir / _GOLDEN_VECTOR_METADATA_FILENAME
    token_path = golden_vector_dir / _GOLDEN_VECTOR_TOKEN_FILENAME
    root_path = golden_vector_dir / _GOLDEN_VECTOR_ROOT_FILENAME
    intermediate_path = golden_vector_dir / _GOLDEN_VECTOR_INTERMEDIATE_FILENAME
    for path in (metadata_path, token_path, root_path, intermediate_path):
        if not path.is_file():
            return Fixed13CryptoRuntimeUnavailableReason.GOLDEN_VECTOR_MISSING

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest_hex = metadata["message_imprint_sha256_hex"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return Fixed13CryptoRuntimeUnavailableReason.GOLDEN_VECTOR_MISSING
    if (
        type(digest_hex) is not str
        or len(digest_hex) != 64
        or any(char not in "0123456789abcdef" for char in digest_hex)
    ):
        return Fixed13CryptoRuntimeUnavailableReason.GOLDEN_VECTOR_MISSING

    args = [
        binary_path,
        "ts",
        "-verify",
        "-digest",
        digest_hex,
        "-in",
        str(token_path),
        "-token_in",
        "-CAfile",
        str(root_path),
        "-untrusted",
        str(intermediate_path),
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=_OPENSSL_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return Fixed13CryptoRuntimeUnavailableReason.GOLDEN_VECTOR_PROBE_FAILED
    if result.returncode != 0:
        return Fixed13CryptoRuntimeUnavailableReason.GOLDEN_VECTOR_REJECTED
    return None


def _validate_candidate(
    raw_path: str,
    *,
    source_tier: str,
    golden_vector_dir: Path,
) -> Fixed13CryptoRuntimeResolution:
    def _fail(reason: Fixed13CryptoRuntimeUnavailableReason) -> Fixed13CryptoRuntimeResolution:
        return Fixed13CryptoRuntimeResolution(
            capable=False,
            binary_path=None,
            openssl_version_text=None,
            source_tier=source_tier,
            reason=reason,
        )

    candidate_path = Path(raw_path)
    if not candidate_path.is_file():
        return _fail(Fixed13CryptoRuntimeUnavailableReason.BINARY_NOT_FOUND)

    resolved_key = str(candidate_path.resolve())

    cached = _capability_cache.get(resolved_key)
    if cached is not None:
        assert cached.capable and cached.binary_path is not None
        return Fixed13CryptoRuntimeResolution(
            capable=True,
            binary_path=cached.binary_path,
            openssl_version_text=cached.openssl_version_text,
            source_tier=source_tier,
            reason=None,
        )

    if not os.access(candidate_path, os.X_OK):
        return _fail(Fixed13CryptoRuntimeUnavailableReason.BINARY_NOT_EXECUTABLE)

    version_text = _probe_openssl_version(resolved_key)
    if version_text is None:
        return _fail(Fixed13CryptoRuntimeUnavailableReason.VERSION_PROBE_FAILED)

    is_openssl, major = _parse_openssl_version(version_text)
    if not is_openssl:
        return _fail(Fixed13CryptoRuntimeUnavailableReason.NOT_OPENSSL)
    if major is None or major < _MINIMUM_OPENSSL_MAJOR:
        return _fail(Fixed13CryptoRuntimeUnavailableReason.OPENSSL_MAJOR_TOO_OLD)

    vector_failure = _run_golden_vector_self_test(resolved_key, golden_vector_dir)
    if vector_failure is not None:
        return _fail(vector_failure)

    resolution = Fixed13CryptoRuntimeResolution(
        capable=True,
        binary_path=resolved_key,
        openssl_version_text=version_text,
        source_tier=source_tier,
        reason=None,
    )
    _capability_cache[resolved_key] = resolution
    return resolution


def _load_runtime_config(config_path: Path) -> tuple[str | None, tuple[str, ...]]:
    """Best-effort load of ``pinned_binary_path``/``candidate_paths``.

    A missing, unreadable, or schema-mismatched config file is treated the
    same as an empty one (tiers 3/4 simply contribute no candidate) rather
    than raised: this module's contract is to always return a typed
    :class:`Fixed13CryptoRuntimeResolution`, never to throw for an
    expected/foreseeable condition. This can never produce a false
    *capable* result -- an empty config only ever removes candidates.
    """

    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return None, ()
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None, ()
    if document.get("schema") != LOTTOLAB_FIXED13_CRYPTO_RUNTIME_SCHEMA_VERSION:
        return None, ()

    pinned_raw = document.get("pinned_binary_path")
    pinned = pinned_raw if type(pinned_raw) is str and pinned_raw != "" else None

    candidates_raw = document.get("candidate_paths")
    if type(candidates_raw) is not list:
        return pinned, ()
    candidates: list[str] = []
    for item in cast(list[object], candidates_raw):
        if type(item) is str and item != "":
            candidates.append(item)
    return pinned, tuple(candidates)


def resolve_openssl_binary(
    openssl_binary: str | None = None,
    *,
    config_path: Path | str | None = None,
    golden_vector_dir: Path | str | None = None,
) -> Fixed13CryptoRuntimeResolution:
    """Resolve the one openssl binary fixed-13 RFC3161 code may use.

    Resolution order -- never a ``PATH`` search at any step:

    1. ``openssl_binary``, when supplied by the caller;
    2. the ``LOTTOLAB_FIXED13_OPENSSL_BINARY`` environment variable, when set
       to a non-empty value;
    3. ``pinned_binary_path`` from the crypto-runtime config, when set;
    4. ``candidate_paths`` from the crypto-runtime config, tried in order.

    Tiers 1-3 each name a single, authoritative candidate: if that tier is
    present but its candidate does not qualify (missing, not executable,
    not a capable OpenSSL, or fails the golden-vector self-test), resolution
    fails closed immediately rather than silently trying a lower-priority
    tier -- an explicit override that turns out to be wrong is a
    configuration error to surface, not a hint to ignore.

    Tier 4 is a single ordered *list* of candidates for different supported
    host layouts (Apple Silicon Homebrew, x86 Homebrew, common Linux
    locations, ...); on any one host only one or two of these will even
    exist, so a listed path that is missing, or that exists but is not
    capable, is skipped in favor of the next listed path. Resolution fails
    closed only once every tier is exhausted.

    Every returned :class:`Fixed13CryptoRuntimeResolution` is fully typed;
    this function never raises for an expected/foreseeable unavailable-
    runtime condition.
    """

    resolved_golden_dir = (
        Path(golden_vector_dir) if golden_vector_dir is not None else _DEFAULT_GOLDEN_VECTOR_DIR
    )

    if openssl_binary is not None and openssl_binary != "":
        return _validate_candidate(
            openssl_binary,
            source_tier=_SOURCE_TIER_EXPLICIT_ARGUMENT,
            golden_vector_dir=resolved_golden_dir,
        )

    env_value = os.environ.get(_ENV_OPENSSL_BINARY)
    if env_value:
        return _validate_candidate(
            env_value,
            source_tier=_SOURCE_TIER_ENVIRONMENT_OVERRIDE,
            golden_vector_dir=resolved_golden_dir,
        )

    resolved_config_path = (
        Path(config_path) if config_path is not None else _DEFAULT_CONFIG_PATH
    )
    pinned_path, candidate_paths = _load_runtime_config(resolved_config_path)

    if pinned_path is not None:
        return _validate_candidate(
            pinned_path,
            source_tier=_SOURCE_TIER_CONFIGURED_PINNED_BINARY,
            golden_vector_dir=resolved_golden_dir,
        )

    if not candidate_paths:
        return Fixed13CryptoRuntimeResolution(
            capable=False,
            binary_path=None,
            openssl_version_text=None,
            source_tier=None,
            reason=Fixed13CryptoRuntimeUnavailableReason.NO_RUNTIME_CONFIGURED,
        )

    for candidate in candidate_paths:
        result = _validate_candidate(
            candidate,
            source_tier=_SOURCE_TIER_DECLARED_CANDIDATE,
            golden_vector_dir=resolved_golden_dir,
        )
        if result.capable:
            return result

    return Fixed13CryptoRuntimeResolution(
        capable=False,
        binary_path=None,
        openssl_version_text=None,
        source_tier=_SOURCE_TIER_DECLARED_CANDIDATE,
        reason=Fixed13CryptoRuntimeUnavailableReason.NO_CAPABLE_CANDIDATE_FOUND,
    )


def require_capable_openssl_binary(
    openssl_binary: str | None = None,
    *,
    config_path: Path | str | None = None,
    golden_vector_dir: Path | str | None = None,
) -> str:
    """Resolve a capable openssl binary path, or raise.

    Convenience wrapper around :func:`resolve_openssl_binary` for callers
    that use an exception-based fail-closed convention (mirrors this
    project's ``Fixed13Rfc3161ProviderConfigError``-raising style) instead of
    inspecting a typed result directly.
    """

    resolution = resolve_openssl_binary(
        openssl_binary, config_path=config_path, golden_vector_dir=golden_vector_dir
    )
    if not resolution.capable or resolution.binary_path is None:
        raise Fixed13CryptoRuntimeUnavailableError(
            f"no capable fixed13 OpenSSL runtime available: {resolution.reason}"
        )
    return resolution.binary_path


__all__ = [
    "LOTTOLAB_FIXED13_CRYPTO_RUNTIME_SCHEMA_VERSION",
    "Fixed13CryptoRuntimeResolution",
    "Fixed13CryptoRuntimeUnavailableError",
    "Fixed13CryptoRuntimeUnavailableReason",
    "require_capable_openssl_binary",
    "resolve_openssl_binary",
]
