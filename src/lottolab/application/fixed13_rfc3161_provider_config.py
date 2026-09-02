"""Canonical production RFC3161 provider/trust-anchor configuration for fixed-13.

Loads exactly two qualified timestamp-authority providers (FreeTSA, DigiCert)
from a version-controlled TOML config and converts each provider's pinned
root certificate into the offline verifier's ``PinnedTrustAnchorSet``
contract.  Every trust decision is fail-closed: a missing config, an
unsupported schema, a provider set that is not exactly FreeTSA + DigiCert, or
a missing/malformed/fingerprint-mismatched root PEM all abort loading rather
than falling back to any system trust store, environment default CA path, or
network-fetched chain.

Certificate parsing is delegated to an ``openssl`` binary resolved and
capability-validated by ``fixed13_crypto_runtime`` (the same canonical
runtime ``fixed13_pre_outcome_timing_receipt`` uses for signature/chain
verification, never an ambient ``PATH`` lookup) rather than a new
third-party X.509 dependency; ``ssl`` stdlib is used only as a second,
independent PEM-to-DER decoder to cross-check that openssl's parse agrees
with a naive base64 unwrap of the same PEM bytes.

This module never sends a timestamp request, never transmits a digest, and
never contacts a network timestamp authority; it only resolves and verifies
public certificate material already committed to ``config/``.
"""

from __future__ import annotations

import hashlib
import ssl
import subprocess
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from lottolab.application.fixed13_crypto_runtime import (
    Fixed13CryptoRuntimeUnavailableError,
    require_capable_openssl_binary,
)
from lottolab.application.fixed13_pre_outcome_timing_receipt import (
    RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE,
    PinnedTrustAnchorSet,
)

LOTTOLAB_FIXED13_RFC3161_PROVIDER_SET_SCHEMA_VERSION: Final = (
    "LOTTOLAB_FIXED13_RFC3161_PROVIDER_SET_V1"
)
FIXED13_RFC3161_MESSAGE_IMPRINT_ALGORITHM: Final = "SHA256"
FIXED13_RFC3161_ISSUANCE_STRATEGY: Final = "ISSUE_TO_ALL"

_EXPECTED_PROVIDER_IDS: Final = ("digicert", "freetsa")
_EXPECTED_ENDPOINT_BY_PROVIDER_ID: Final[dict[str, str]] = {
    "freetsa": "https://freetsa.org/tsr",
    "digicert": "http://timestamp.digicert.com",
}
_REQUIRED_POLICY_STATUS: Final = "SUPPORTED"
_SHA256_HEX_LENGTH: Final = 64
_OPENSSL_TIMEOUT_SECONDS: Final = 15

_DEFAULT_CONFIG_PATH: Final = (
    Path(__file__).resolve().parents[3] / "config" / "fixed13_rfc3161_tsa.toml"
)


class Fixed13Rfc3161ProviderConfigError(RuntimeError):
    """The provider-set config, or one provider's pinned root, fails closed."""


def _require_nonempty_str(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise Fixed13Rfc3161ProviderConfigError(f"{label} must be a non-empty exact string")
    return value


def _require_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise Fixed13Rfc3161ProviderConfigError(f"{label} must be an exact boolean")
    return value


def _require_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise Fixed13Rfc3161ProviderConfigError(f"{label} must be an exact integer")
    return value


def _require_sha256_hex(value: object, label: str) -> str:
    text = _require_nonempty_str(value, label)
    if len(text) != _SHA256_HEX_LENGTH or any(char not in "0123456789abcdef" for char in text):
        raise Fixed13Rfc3161ProviderConfigError(
            f"{label} must be a lowercase 64-character SHA-256 hex digest"
        )
    return text


def _require_safe_relative_path(value: object, label: str) -> str:
    text = _require_nonempty_str(value, label)
    relative = Path(text)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or "\x00" in text
        or text.startswith("~")
    ):
        raise Fixed13Rfc3161ProviderConfigError(
            f"{label} must be a safe repository-root-relative path: {text!r}"
        )
    return text


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise Fixed13Rfc3161ProviderConfigError(f"{label} must be a table")
    return cast(Mapping[str, object], value)


def _absolute_path(path: Path) -> Path:
    return path.expanduser().absolute()


@dataclass(frozen=True, slots=True)
class Fixed13Rfc3161ProviderConfig:
    """One qualified RFC3161 provider's pinned identity and root anchor."""

    provider_id: str
    official_endpoint: str
    enabled: bool
    policy_status: str
    root_certificate_path: str
    root_certificate_der_sha256: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.provider_id, "provider_id")
        if self.provider_id not in _EXPECTED_PROVIDER_IDS:
            raise Fixed13Rfc3161ProviderConfigError(
                f"unsupported fixed13 RFC3161 provider_id: {self.provider_id!r}"
            )
        expected_endpoint = _EXPECTED_ENDPOINT_BY_PROVIDER_ID[self.provider_id]
        if self.official_endpoint != expected_endpoint:
            raise Fixed13Rfc3161ProviderConfigError(
                f"provider {self.provider_id!r} official_endpoint must be exactly "
                f"{expected_endpoint!r}, got {self.official_endpoint!r}"
            )
        if type(self.enabled) is not bool or not self.enabled:
            raise Fixed13Rfc3161ProviderConfigError(
                f"provider {self.provider_id!r} must be enabled=true"
            )
        if self.policy_status != _REQUIRED_POLICY_STATUS:
            raise Fixed13Rfc3161ProviderConfigError(
                f"provider {self.provider_id!r} policy_status must be "
                f"{_REQUIRED_POLICY_STATUS!r}"
            )
        _require_safe_relative_path(self.root_certificate_path, "root_certificate_path")
        _require_sha256_hex(self.root_certificate_der_sha256, "root_certificate_der_sha256")

    def pinned_trust_anchor(
        self,
        *,
        repository_root: Path,
        openssl_binary: str | None = None,
    ) -> PinnedTrustAnchorSet:
        """Fail-closed: parse, DER-convert, and fingerprint-check the pinned root.

        Always re-reads and re-verifies the root PEM from disk; never trusts a
        cached result from a previous call or from load time.
        """

        pem_text = _load_and_verify_pinned_root(
            provider_id=self.provider_id,
            root_certificate_path=self.root_certificate_path,
            expected_der_sha256=self.root_certificate_der_sha256,
            repository_root=repository_root,
            openssl_binary=openssl_binary,
        )
        return PinnedTrustAnchorSet((pem_text,))


@dataclass(frozen=True, slots=True)
class Fixed13Rfc3161ProviderSet:
    """Parsed, validated fixed-13 RFC3161 production provider set."""

    schema: str
    proof_type: str
    message_imprint_algorithm: str
    issuance_strategy: str
    minimum_valid_receipts: int
    providers: tuple[Fixed13Rfc3161ProviderConfig, ...]
    repository_root: Path

    def __post_init__(self) -> None:
        if self.schema != LOTTOLAB_FIXED13_RFC3161_PROVIDER_SET_SCHEMA_VERSION:
            raise Fixed13Rfc3161ProviderConfigError(
                "unsupported fixed13 RFC3161 provider-set schema"
            )
        if self.proof_type != RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE:
            raise Fixed13Rfc3161ProviderConfigError("unsupported fixed13 RFC3161 proof_type")
        if self.message_imprint_algorithm != FIXED13_RFC3161_MESSAGE_IMPRINT_ALGORITHM:
            raise Fixed13Rfc3161ProviderConfigError(
                "unsupported fixed13 RFC3161 message_imprint_algorithm"
            )
        if self.issuance_strategy != FIXED13_RFC3161_ISSUANCE_STRATEGY:
            raise Fixed13Rfc3161ProviderConfigError(
                "unsupported fixed13 RFC3161 issuance_strategy"
            )
        if type(self.providers) is not tuple or len(self.providers) != len(_EXPECTED_PROVIDER_IDS):
            raise Fixed13Rfc3161ProviderConfigError(
                f"fixed13 RFC3161 provider set must contain exactly "
                f"{len(_EXPECTED_PROVIDER_IDS)} providers"
            )
        provider_ids = [provider.provider_id for provider in self.providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise Fixed13Rfc3161ProviderConfigError("fixed13 RFC3161 provider ids must be unique")
        if set(provider_ids) != set(_EXPECTED_PROVIDER_IDS):
            raise Fixed13Rfc3161ProviderConfigError(
                "fixed13 RFC3161 provider set must contain exactly FreeTSA and DigiCert"
            )
        if type(self.minimum_valid_receipts) is not int or not (
            1 <= self.minimum_valid_receipts <= len(self.providers)
        ):
            raise Fixed13Rfc3161ProviderConfigError(
                "minimum_valid_receipts must be between 1 and the configured provider count"
            )

    def provider(self, provider_id: str) -> Fixed13Rfc3161ProviderConfig:
        for provider in self.providers:
            if provider.provider_id == provider_id:
                return provider
        raise Fixed13Rfc3161ProviderConfigError(
            f"unknown fixed13 RFC3161 provider_id: {provider_id!r}"
        )

    def pinned_trust_anchor(
        self, provider_id: str, *, openssl_binary: str | None = None
    ) -> PinnedTrustAnchorSet:
        return self.provider(provider_id).pinned_trust_anchor(
            repository_root=self.repository_root, openssl_binary=openssl_binary
        )


def load_fixed13_rfc3161_provider_set(
    path: Path | str | None = None,
    *,
    repository_root: Path | str | None = None,
    openssl_binary: str | None = None,
    verify_roots: bool = True,
) -> Fixed13Rfc3161ProviderSet:
    """Load and fail-closed-validate the canonical fixed-13 RFC3161 provider set.

    When ``verify_roots`` is true (the default), every provider's pinned root
    PEM is parsed and fingerprint-checked immediately so a bad config never
    loads successfully only to fail later at first use.
    """

    config_path = _absolute_path(_DEFAULT_CONFIG_PATH if path is None else Path(path))
    try:
        document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise Fixed13Rfc3161ProviderConfigError(
            f"cannot read fixed13 RFC3161 provider-set config: {config_path}"
        ) from exc

    schema = _require_nonempty_str(document.get("schema"), "schema")
    proof_type = _require_nonempty_str(document.get("proof_type"), "proof_type")
    message_imprint_algorithm = _require_nonempty_str(
        document.get("message_imprint_algorithm"), "message_imprint_algorithm"
    )
    issuance_strategy = _require_nonempty_str(
        document.get("issuance_strategy"), "issuance_strategy"
    )
    minimum_valid_receipts = _require_int(
        document.get("minimum_valid_receipts"), "minimum_valid_receipts"
    )

    raw_providers = document.get("providers")
    if not isinstance(raw_providers, list) or not raw_providers:
        raise Fixed13Rfc3161ProviderConfigError(
            "fixed13 RFC3161 config must declare a non-empty providers array"
        )
    providers = tuple(
        _parse_provider(_mapping(item, "providers[]")) for item in cast(list[object], raw_providers)
    )

    resolved_root = (
        _absolute_path(Path(repository_root))
        if repository_root is not None
        else _absolute_path(config_path.parent.parent)
    )

    provider_set = Fixed13Rfc3161ProviderSet(
        schema=schema,
        proof_type=proof_type,
        message_imprint_algorithm=message_imprint_algorithm,
        issuance_strategy=issuance_strategy,
        minimum_valid_receipts=minimum_valid_receipts,
        providers=providers,
        repository_root=resolved_root,
    )

    if verify_roots:
        for provider in provider_set.providers:
            provider.pinned_trust_anchor(
                repository_root=resolved_root, openssl_binary=openssl_binary
            )

    return provider_set


def _parse_provider(raw: Mapping[str, object]) -> Fixed13Rfc3161ProviderConfig:
    return Fixed13Rfc3161ProviderConfig(
        provider_id=_require_nonempty_str(raw.get("provider_id"), "provider_id"),
        official_endpoint=_require_nonempty_str(raw.get("official_endpoint"), "official_endpoint"),
        enabled=_require_bool(raw.get("enabled"), "enabled"),
        policy_status=_require_nonempty_str(raw.get("policy_status"), "policy_status"),
        root_certificate_path=_require_safe_relative_path(
            raw.get("root_certificate_path"), "root_certificate_path"
        ),
        root_certificate_der_sha256=_require_sha256_hex(
            raw.get("root_certificate_der_sha256"), "root_certificate_der_sha256"
        ),
    )


def _resolve_root_certificate_path(repository_root: Path, relative_path: str) -> Path:
    root_resolved = repository_root.resolve()
    candidate = (repository_root / relative_path).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise Fixed13Rfc3161ProviderConfigError(
            f"root_certificate_path escapes the repository root: {relative_path!r}"
        )
    return candidate


def _run_openssl(args: list[str], *, openssl_binary: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [openssl_binary, *args],
            capture_output=True,
            timeout=_OPENSSL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise Fixed13Rfc3161ProviderConfigError(f"cannot run openssl: {exc}") from exc


def _load_and_verify_pinned_root(
    *,
    provider_id: str,
    root_certificate_path: str,
    expected_der_sha256: str,
    repository_root: Path,
    openssl_binary: str | None,
) -> str:
    try:
        resolved_openssl = require_capable_openssl_binary(openssl_binary)
    except Fixed13CryptoRuntimeUnavailableError as exc:
        raise Fixed13Rfc3161ProviderConfigError(
            f"no capable openssl runtime to parse and pin fixed13 RFC3161 provider roots: {exc}"
        ) from exc
    path = _resolve_root_certificate_path(repository_root, root_certificate_path)
    try:
        pem_text = path.read_text(encoding="ascii")
    except OSError as exc:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate is missing: {path}"
        ) from exc
    if "BEGIN CERTIFICATE" not in pem_text:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate is not PEM-encoded: {path}"
        )

    der_result = _run_openssl(
        ["x509", "-in", str(path), "-outform", "DER"], openssl_binary=resolved_openssl
    )
    if der_result.returncode != 0 or not der_result.stdout:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate is malformed: {path}"
        )
    der_bytes = der_result.stdout

    try:
        stdlib_der_bytes = ssl.PEM_cert_to_DER_cert(pem_text)
    except ssl.SSLError as exc:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate PEM is malformed: {path}"
        ) from exc
    if stdlib_der_bytes != der_bytes:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} PEM does not decode to openssl's own DER for its "
            f"root: {path}"
        )

    actual_der_sha256 = hashlib.sha256(der_bytes).hexdigest()
    if actual_der_sha256 != expected_der_sha256:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate fingerprint mismatch: "
            f"expected {expected_der_sha256}, computed {actual_der_sha256} ({path})"
        )

    text_result = _run_openssl(
        ["x509", "-in", str(path), "-noout", "-text"], openssl_binary=resolved_openssl
    )
    if text_result.returncode != 0:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate could not be inspected: {path}"
        )
    if "CA:TRUE" not in text_result.stdout.decode("ascii", errors="replace").upper():
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate is not a CA certificate: {path}"
        )

    subject_result = _run_openssl(
        ["x509", "-in", str(path), "-noout", "-subject"], openssl_binary=resolved_openssl
    )
    issuer_result = _run_openssl(
        ["x509", "-in", str(path), "-noout", "-issuer"], openssl_binary=resolved_openssl
    )
    if subject_result.returncode != 0 or issuer_result.returncode != 0:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate could not be inspected: {path}"
        )
    subject_text = (
        subject_result.stdout.decode("ascii", errors="replace").removeprefix("subject=").strip()
    )
    issuer_text = (
        issuer_result.stdout.decode("ascii", errors="replace").removeprefix("issuer=").strip()
    )
    if subject_text != issuer_text:
        raise Fixed13Rfc3161ProviderConfigError(
            f"provider {provider_id!r} root certificate is not self-signed: {path}"
        )

    return pem_text


def compute_der_sha256(pem_certificate_text: str, *, openssl_binary: str | None = None) -> str:
    """Compute the lowercase DER SHA-256 fingerprint of one PEM certificate.

    Used to fingerprint an archived receipt chain's root before comparing it
    against a provider's pinned root via :func:`bind_archived_chain_root`.
    """

    try:
        resolved_openssl = require_capable_openssl_binary(openssl_binary)
    except Fixed13CryptoRuntimeUnavailableError as exc:
        raise Fixed13Rfc3161ProviderConfigError(
            f"no capable openssl runtime to fingerprint a certificate: {exc}"
        ) from exc
    if "BEGIN CERTIFICATE" not in pem_certificate_text:
        raise Fixed13Rfc3161ProviderConfigError("input is not a PEM-encoded certificate")
    with tempfile.TemporaryDirectory(prefix="lottolab-fixed13-rfc3161-fingerprint-") as raw_dir:
        temp_path = Path(raw_dir) / "candidate.pem"
        temp_path.write_text(pem_certificate_text, encoding="ascii")
        result = _run_openssl(
            ["x509", "-in", str(temp_path), "-outform", "DER"], openssl_binary=resolved_openssl
        )
    if result.returncode != 0 or not result.stdout:
        raise Fixed13Rfc3161ProviderConfigError("certificate is malformed")
    return hashlib.sha256(result.stdout).hexdigest()


def bind_archived_chain_root(
    provider: Fixed13Rfc3161ProviderConfig,
    *,
    repository_root: Path,
    archived_chain_root_der_sha256: str,
    openssl_binary: str | None = None,
) -> PinnedTrustAnchorSet:
    """Fail-closed: the archived receipt chain's root must match this provider's pin.

    Does not change the verifier's own signature semantics; it only decides
    whether the caller may build a :class:`PinnedTrustAnchorSet` for
    ``provider`` from one already-archived receipt chain.
    """

    expected = _require_sha256_hex(
        archived_chain_root_der_sha256, "archived_chain_root_der_sha256"
    )
    if expected != provider.root_certificate_der_sha256:
        raise Fixed13Rfc3161ProviderConfigError(
            f"archived chain root fingerprint does not match provider "
            f"{provider.provider_id!r}'s pinned root: archived={expected}, "
            f"pinned={provider.root_certificate_der_sha256}"
        )
    return provider.pinned_trust_anchor(
        repository_root=repository_root, openssl_binary=openssl_binary
    )


__all__ = [
    "FIXED13_RFC3161_ISSUANCE_STRATEGY",
    "FIXED13_RFC3161_MESSAGE_IMPRINT_ALGORITHM",
    "LOTTOLAB_FIXED13_RFC3161_PROVIDER_SET_SCHEMA_VERSION",
    "Fixed13Rfc3161ProviderConfig",
    "Fixed13Rfc3161ProviderConfigError",
    "Fixed13Rfc3161ProviderSet",
    "bind_archived_chain_root",
    "compute_der_sha256",
    "load_fixed13_rfc3161_provider_set",
]
