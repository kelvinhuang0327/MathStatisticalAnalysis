"""Offline Sigstore/Rekor adapter for T539 PRETARGET seal receipts.

No method in this module signs an artifact, publishes an entry, or performs a
Rekor lookup.  The official verifier is configured with ``offline=True`` and
validates a complete supplied bundle under the Sigstore public-good trust root.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from typing import Protocol, cast

from sigstore.models import Bundle, ClientTrustConfig, TrustedRoot
from sigstore.verify import Verifier
from sigstore.verify.policy import VerificationPolicy

from lottolab.domain.t539_pretarget_external_seal import (
    SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY,
    ExternalReceiptVerificationError,
    RekorReceiptEvidence,
    RekorVerificationReference,
    T539PretargetSeal,
    VerifiedRekorReceipt,
    canonical_json_bytes,
)


class SigstoreBundleVerifierBackend(Protocol):
    """Narrow seam for deterministic offline fixtures and the official client."""

    def verify_artifact(
        self, artifact: bytes, bundle_json: str
    ) -> RekorVerificationReference: ...


@dataclass(frozen=True, slots=True)
class OfficialSigstoreBundleVerifier:
    """Official Sigstore verification with network refresh explicitly disabled."""

    policy: VerificationPolicy

    def verify_artifact(
        self, artifact: bytes, bundle_json: str
    ) -> RekorVerificationReference:
        bundle = Bundle.from_json(bundle_json)
        trust_config = ClientTrustConfig.production(offline=True)
        trusted_root = trust_config.trusted_root
        Verifier(trusted_root=trusted_root).verify_artifact(artifact, bundle, self.policy)
        return official_sigstore_verification_reference(trusted_root=trusted_root)


@dataclass(frozen=True, slots=True)
class _BundleEvidence:
    rekor_uuid: str
    log_id: str | None
    log_index: int
    integrated_time: int
    entry_kind: str
    entry_version: str
    canonical_entry_body: str
    signing_material_sha256: str
    signed_entry_timestamp: str | None
    inclusion_proof: Mapping[str, object]
    bundle: Mapping[str, object]


class SigstoreRekorReceiptVerifier:
    """Validate exact receipt metadata and delegate all cryptography to Sigstore."""

    def __init__(
        self,
        *,
        backend: SigstoreBundleVerifierBackend,
    ) -> None:
        self._backend = backend

    def verify(
        self,
        seal: T539PretargetSeal,
        receipt: RekorReceiptEvidence,
    ) -> VerifiedRekorReceipt:
        if type(seal) is not T539PretargetSeal:
            raise ValueError("seal must be a T539PretargetSeal")
        if type(receipt) is not RekorReceiptEvidence:
            raise ExternalReceiptVerificationError(
                "a raw Rekor UUID is not complete receipt evidence"
            )
        if receipt.seal_digest != seal.seal_digest:
            raise ExternalReceiptVerificationError(
                "receipt seal_digest does not match canonical seal bytes"
            )

        try:
            extracted = _extract_bundle_evidence(receipt.sigstore_bundle_json)
            _require_exact_receipt_metadata(receipt, extracted)
            verification = self._backend.verify_artifact(
                seal.canonical_bytes(), receipt.sigstore_bundle_json
            )
            if type(verification) is not RekorVerificationReference:
                raise ExternalReceiptVerificationError(
                    "Sigstore backend did not return its successful trust reference"
                )
        except ExternalReceiptVerificationError:
            raise
        except Exception as exc:
            raise ExternalReceiptVerificationError(
                "official Sigstore bundle verification failed closed"
            ) from exc
        return VerifiedRekorReceipt(receipt=receipt, verification=verification)


def official_sigstore_verification_reference(
    *, trusted_root: TrustedRoot
) -> RekorVerificationReference:
    """Fingerprint the exact public-good trusted-root object used by Sigstore."""

    return RekorVerificationReference(
        trust_root_identity=SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY,
        trust_root_version=_trusted_root_version(trusted_root),
        verifier="sigstore-python",
        verifier_version=version("sigstore"),
    )


def receipt_from_sigstore_bundle(
    *,
    rekor_entry_id: str,
    seal_digest: str,
    sigstore_bundle_json: str,
) -> RekorReceiptEvidence:
    """Normalize a complete supplied bundle; this does not mark it verified."""

    evidence = _extract_bundle_evidence(sigstore_bundle_json)
    if rekor_entry_id != evidence.rekor_uuid:
        raise ExternalReceiptVerificationError(
            "Rekor EntryID must equal the RFC6962 leaf hash of canonicalizedBody"
        )
    return RekorReceiptEvidence.create(
        rekor_entry_id=rekor_entry_id,
        log_id=evidence.log_id,
        log_index=evidence.log_index,
        integrated_time=evidence.integrated_time,
        entry_kind=evidence.entry_kind,
        entry_version=evidence.entry_version,
        canonical_entry_body=evidence.canonical_entry_body,
        seal_digest=seal_digest,
        signing_material_sha256=evidence.signing_material_sha256,
        signed_entry_timestamp=evidence.signed_entry_timestamp,
        inclusion_proof=evidence.inclusion_proof,
        sigstore_bundle=evidence.bundle,
    )


def _extract_bundle_evidence(bundle_json: str) -> _BundleEvidence:
    if type(bundle_json) is not str or not bundle_json:
        raise ExternalReceiptVerificationError("Sigstore bundle must be non-empty JSON")
    try:
        parsed = json.loads(bundle_json)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ExternalReceiptVerificationError("Sigstore bundle is invalid JSON") from exc
    bundle = _mapping(parsed, "sigstore_bundle")
    verification_material = _mapping(
        bundle.get("verificationMaterial"), "sigstore_bundle.verificationMaterial"
    )
    raw_entries = verification_material.get("tlogEntries")
    if raw_entries is None:
        raw_entries = verification_material.get("transparencyLogEntries")
    entries = _sequence(raw_entries, "sigstore_bundle.verificationMaterial.tlogEntries")
    if len(entries) != 1:
        raise ExternalReceiptVerificationError(
            "Sigstore bundle must contain exactly one transparency-log entry"
        )
    entry = _mapping(entries[0], "sigstore_bundle.tlogEntries[0]")

    kind_version = _mapping(entry.get("kindVersion"), "tlog_entry.kindVersion")
    entry_kind = _text(kind_version.get("kind"), "tlog_entry.kindVersion.kind")
    entry_version = _text(kind_version.get("version"), "tlog_entry.kindVersion.version")
    if entry_kind != "hashedrekord":
        raise ExternalReceiptVerificationError("Rekor entry kind must be hashedrekord")

    log_id_mapping = _mapping(entry.get("logId"), "tlog_entry.logId")
    raw_log_id = log_id_mapping.get("keyId")
    log_id = None if raw_log_id is None else _text(raw_log_id, "tlog_entry.logId.keyId")
    log_index = _proto_integer(entry.get("logIndex"), "tlog_entry.logIndex")
    integrated_time = _proto_integer(
        entry.get("integratedTime"), "tlog_entry.integratedTime", minimum=1
    )
    canonical_body = _canonical_base64(
        entry.get("canonicalizedBody"), "tlog_entry.canonicalizedBody"
    )
    canonical_body_bytes = _base64_bytes(
        canonical_body, "tlog_entry.canonicalizedBody"
    )

    inclusion_proof = _mapping(entry.get("inclusionProof"), "tlog_entry.inclusionProof")
    promise_value = entry.get("inclusionPromise")
    signed_entry_timestamp: str | None = None
    if promise_value is not None:
        promise = _mapping(promise_value, "tlog_entry.inclusionPromise")
        raw_set = promise.get("signedEntryTimestamp")
        if raw_set is not None:
            signed_entry_timestamp = _canonical_base64(
                raw_set, "tlog_entry.inclusionPromise.signedEntryTimestamp"
            )

    signing_material = _signing_material_bytes(verification_material)
    canonical_bundle = _mapping(
        json.loads(canonical_json_bytes(bundle)), "sigstore_bundle"
    )
    canonical_proof = _mapping(
        json.loads(canonical_json_bytes(inclusion_proof)), "tlog_entry.inclusionProof"
    )
    return _BundleEvidence(
        rekor_uuid=hashlib.sha256(b"\x00" + canonical_body_bytes).hexdigest(),
        log_id=log_id,
        log_index=log_index,
        integrated_time=integrated_time,
        entry_kind=entry_kind,
        entry_version=entry_version,
        canonical_entry_body=canonical_body,
        signing_material_sha256=hashlib.sha256(signing_material).hexdigest(),
        signed_entry_timestamp=signed_entry_timestamp,
        inclusion_proof=canonical_proof,
        bundle=canonical_bundle,
    )


def _signing_material_bytes(verification_material: Mapping[str, object]) -> bytes:
    raw_certificate = verification_material.get("certificate")
    if raw_certificate is not None:
        certificate = _mapping(raw_certificate, "verificationMaterial.certificate")
        return _base64_bytes(certificate.get("rawBytes"), "certificate.rawBytes")

    raw_chain = verification_material.get("x509CertificateChain")
    if raw_chain is None:
        raise ExternalReceiptVerificationError(
            "Sigstore bundle is missing certificate signing material"
        )
    chain = _mapping(raw_chain, "verificationMaterial.x509CertificateChain")
    certificates = _sequence(chain.get("certificates"), "x509CertificateChain.certificates")
    if not certificates:
        raise ExternalReceiptVerificationError("Sigstore certificate chain is empty")
    certificate = _mapping(certificates[0], "x509CertificateChain.certificates[0]")
    return _base64_bytes(certificate.get("rawBytes"), "certificate.rawBytes")


def _require_exact_receipt_metadata(
    receipt: RekorReceiptEvidence,
    extracted: _BundleEvidence,
) -> None:
    expected_bundle_json = canonical_json_bytes(extracted.bundle).decode("utf-8")
    expected_proof_json = canonical_json_bytes(extracted.inclusion_proof).decode("utf-8")
    if (
        receipt.rekor_entry_id != extracted.rekor_uuid
        or receipt.log_id != extracted.log_id
        or receipt.log_index != extracted.log_index
        or receipt.integrated_time != extracted.integrated_time
        or receipt.entry_kind != extracted.entry_kind
        or receipt.entry_version != extracted.entry_version
        or receipt.canonical_entry_body != extracted.canonical_entry_body
        or receipt.signing_material_sha256 != extracted.signing_material_sha256
        or receipt.signed_entry_timestamp != extracted.signed_entry_timestamp
        or receipt.inclusion_proof_json != expected_proof_json
        or receipt.sigstore_bundle_json != expected_bundle_json
    ):
        raise ExternalReceiptVerificationError(
            "persisted Rekor receipt metadata differs from its Sigstore bundle"
        )


class _CanonicalJsonModel(Protocol):
    def to_json(self) -> str: ...


def _trusted_root_version(trusted_root: TrustedRoot) -> str:
    inner = cast(_CanonicalJsonModel | None, vars(trusted_root).get("_inner"))
    if inner is None:
        raise ExternalReceiptVerificationError(
            "Sigstore trusted root cannot be canonically fingerprinted"
        )
    try:
        root = _mapping(json.loads(inner.to_json()), "sigstore_trusted_root")
    except (json.JSONDecodeError, ValueError) as exc:
        raise ExternalReceiptVerificationError(
            "Sigstore trusted root cannot be canonically fingerprinted"
        ) from exc
    digest = hashlib.sha256(canonical_json_bytes(root)).hexdigest()
    return f"sha256:{digest}"


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ExternalReceiptVerificationError(f"{label} must be an object")
    object_mapping = cast(Mapping[object, object], value)
    if any(type(key) is not str for key in object_mapping):
        raise ExternalReceiptVerificationError(f"{label} keys must be strings")
    return cast(Mapping[str, object], object_mapping)


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ExternalReceiptVerificationError(f"{label} must be an array")
    return cast(Sequence[object], value)


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ExternalReceiptVerificationError(f"{label} must be non-empty text")
    return value


def _proto_integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is int:
        parsed = value
    elif type(value) is str and value.isascii() and value.isdecimal():
        parsed = int(value)
    else:
        raise ExternalReceiptVerificationError(f"{label} must be an integer")
    if parsed < minimum:
        raise ExternalReceiptVerificationError(f"{label} must be >= {minimum}")
    return parsed


def _base64_bytes(value: object, label: str) -> bytes:
    text = _text(value, label)
    try:
        decoded = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ExternalReceiptVerificationError(f"{label} must be canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != text:
        raise ExternalReceiptVerificationError(f"{label} must be canonical base64")
    return decoded


def _canonical_base64(value: object, label: str) -> str:
    decoded = _base64_bytes(value, label)
    return base64.b64encode(decoded).decode("ascii")


__all__ = [
    "OfficialSigstoreBundleVerifier",
    "SigstoreBundleVerifierBackend",
    "SigstoreRekorReceiptVerifier",
    "official_sigstore_verification_reference",
    "receipt_from_sigstore_bundle",
]
