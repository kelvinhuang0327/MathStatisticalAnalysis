"""Pre-outcome commitment envelope and offline RFC3161 receipt verification.

This module never issues a timestamp request and never contacts a network
timestamp authority.  It only (a) builds the canonical commitment envelope
that a real RFC3161 request's ``messageImprint`` must bind to, and (b)
verifies an already-obtained RFC3161 token against that commitment and a
caller-supplied, explicitly pinned trust-anchor set.

The commitment intentionally excludes ``eligibility_record_digest``: that
digest already embeds ``pre_outcome_timing_proof_ref``, so binding the
timestamp to it would make the receipt a precondition of the value it is
supposed to timestamp.

Signature and certificate-chain verification are delegated to
``openssl ts -verify`` on a binary resolved and capability-validated by
:mod:`lottolab.application.fixed13_crypto_runtime` (never an ambient
``PATH`` lookup), which already implements the CMS
signed-attributes-vs-econtent signing convention (RFC 5652 section 5.4) and
X.509 path validation correctly; this module does not reimplement either.
This module's own DER reader only extracts the non-cryptographic TSTInfo
fields (messageImprint, genTime, accuracy) needed for the application-level
checks that ``openssl ts -verify`` does not make on its own (algorithm
pinning, exact commitment binding, and the strict pre-outcome cutoff).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from lottolab.application.fixed13_crypto_runtime import resolve_openssl_binary
from lottolab.domain.draws import LotteryType

LOTTOLAB_FIXED13_PRE_OUTCOME_COMMITMENT_SCHEMA_VERSION = (
    "LOTTOLAB_FIXED13_PRE_OUTCOME_COMMITMENT_V1"
)
RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE = "RFC3161_TSA_TOKEN_V1"

_OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
_OID_TST_INFO_CONTENT_TYPE = "1.2.840.113549.1.9.16.1.4"
_OID_SHA256 = "2.16.840.1.101.3.4.2.1"

_TAG_BOOLEAN = 0x01
_TAG_INTEGER = 0x02
_TAG_OCTET_STRING = 0x04
_TAG_OID = 0x06
_TAG_GENERALIZED_TIME = 0x18
_TAG_SEQUENCE = 0x10
_CLASS_UNIVERSAL = 0
_CLASS_CONTEXT = 2

_OPENSSL_VERIFY_TIMEOUT_SECONDS = 15


def _require_str(value: object, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty exact string")


def _require_sha256_hex(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{label} must be a lowercase 64-character SHA-256 hex digest")


def _require_utc(value: object, label: str) -> None:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class Fixed13PreOutcomeCommitment:
    """``LOTTOLAB_FIXED13_PRE_OUTCOME_COMMITMENT_V1`` canonical commitment envelope.

    Deliberately excludes every optional/operational field; only the eight
    values the CTO decision names are signed material.
    """

    schema_version: str
    lottery_type: LotteryType
    official_draw_identity: str
    target_scheduled_at: datetime
    target_registration_digest: str
    prediction_record_digest: str
    freeze_artifact_file_sha256: str
    cohort_membership_strategy_ids_lcj1_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != LOTTOLAB_FIXED13_PRE_OUTCOME_COMMITMENT_SCHEMA_VERSION:
            raise ValueError("unsupported pre-outcome commitment schema_version")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("pre-outcome commitment lottery_type must be BIG_LOTTO")
        _require_str(self.official_draw_identity, "official_draw_identity")
        _require_utc(self.target_scheduled_at, "target_scheduled_at")
        for label, digest in (
            ("target_registration_digest", self.target_registration_digest),
            ("prediction_record_digest", self.prediction_record_digest),
            ("freeze_artifact_file_sha256", self.freeze_artifact_file_sha256),
            (
                "cohort_membership_strategy_ids_lcj1_sha256",
                self.cohort_membership_strategy_ids_lcj1_sha256,
            ),
        ):
            _require_sha256_hex(digest, label)

    @classmethod
    def create(
        cls,
        *,
        official_draw_identity: str,
        target_scheduled_at: datetime,
        target_registration_digest: str,
        prediction_record_digest: str,
        freeze_artifact_file_sha256: str,
        cohort_membership_strategy_ids_lcj1_sha256: str,
    ) -> Fixed13PreOutcomeCommitment:
        return cls(
            schema_version=LOTTOLAB_FIXED13_PRE_OUTCOME_COMMITMENT_SCHEMA_VERSION,
            lottery_type=LotteryType.BIG_LOTTO,
            official_draw_identity=official_draw_identity,
            target_scheduled_at=target_scheduled_at,
            target_registration_digest=target_registration_digest,
            prediction_record_digest=prediction_record_digest,
            freeze_artifact_file_sha256=freeze_artifact_file_sha256,
            cohort_membership_strategy_ids_lcj1_sha256=(
                cohort_membership_strategy_ids_lcj1_sha256
            ),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cohort_membership_strategy_ids_lcj1_sha256": (
                self.cohort_membership_strategy_ids_lcj1_sha256
            ),
            "freeze_artifact_file_sha256": self.freeze_artifact_file_sha256,
            "lottery_type": self.lottery_type.value,
            "official_draw_identity": self.official_draw_identity,
            "prediction_record_digest": self.prediction_record_digest,
            "schema_version": self.schema_version,
            "target_registration_digest": self.target_registration_digest,
            "target_scheduled_at": _utc_text(self.target_scheduled_at),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def commitment_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class PinnedTrustAnchorSet:
    """Caller-supplied, explicitly pinned RFC3161 trust anchors.

    Never populated from a system trust store or a network-discovered chain;
    the caller must name every root it accepts.
    """

    ca_certificates_pem: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.ca_certificates_pem) is not tuple or not self.ca_certificates_pem:
            raise ValueError("ca_certificates_pem must be a non-empty tuple of PEM text")
        for item in self.ca_certificates_pem:
            if type(item) is not str or "BEGIN CERTIFICATE" not in item:
                raise ValueError("ca_certificates_pem entries must be PEM-encoded certificates")

    def bundle_text(self) -> str:
        return "\n".join(self.ca_certificates_pem)


class PreOutcomeTimingReceiptReasonCode(StrEnum):
    OK = "OK"
    UNSUPPORTED_PROOF_TYPE = "UNSUPPORTED_PROOF_TYPE"
    RECEIPT_FILE_NOT_FOUND = "RECEIPT_FILE_NOT_FOUND"
    REFERENCE_SHA256_MISMATCH = "REFERENCE_SHA256_MISMATCH"
    TOKEN_MALFORMED = "TOKEN_MALFORMED"
    MESSAGE_IMPRINT_ALGORITHM_UNSUPPORTED = "MESSAGE_IMPRINT_ALGORITHM_UNSUPPORTED"
    MESSAGE_IMPRINT_MISMATCH = "MESSAGE_IMPRINT_MISMATCH"
    GENTIME_UNPARSEABLE = "GENTIME_UNPARSEABLE"
    GENTIME_NOT_BEFORE_TARGET_SCHEDULE = "GENTIME_NOT_BEFORE_TARGET_SCHEDULE"
    GENTIME_ACCURACY_MARGIN_NOT_BEFORE_TARGET_SCHEDULE = (
        "GENTIME_ACCURACY_MARGIN_NOT_BEFORE_TARGET_SCHEDULE"
    )
    SIGNATURE_OR_CHAIN_INVALID = "SIGNATURE_OR_CHAIN_INVALID"
    VERIFIER_BACKEND_UNAVAILABLE = "VERIFIER_BACKEND_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PreOutcomeTimingReceiptVerdict:
    """Deterministic outcome of :func:`verify_rfc3161_pre_outcome_receipt`."""

    verified: bool
    reason_code: PreOutcomeTimingReceiptReasonCode
    commitment_sha256: str | None
    gen_time: datetime | None

    def __post_init__(self) -> None:
        if type(self.verified) is not bool:
            raise ValueError("verified must be an exact boolean")
        if type(self.reason_code) is not PreOutcomeTimingReceiptReasonCode:
            raise ValueError("reason_code is unsupported")
        if self.verified != (self.reason_code is PreOutcomeTimingReceiptReasonCode.OK):
            raise ValueError("verified must be exactly (reason_code is OK)")
        if self.commitment_sha256 is not None:
            _require_sha256_hex(self.commitment_sha256, "commitment_sha256")
        if self.gen_time is not None:
            _require_utc(self.gen_time, "gen_time")


class _TokenParseError(ValueError):
    """The token bytes are not a well-formed RFC3161 TimeStampToken."""


@dataclass(frozen=True, slots=True)
class _DerNode:
    tag_class: int
    tag_number: int
    is_constructed: bool
    content: bytes


def _read_der_tlv(data: bytes, offset: int) -> tuple[_DerNode, int]:
    if offset >= len(data):
        raise _TokenParseError("truncated DER: missing tag octet")
    first = data[offset]
    tag_class = (first & 0xC0) >> 6
    is_constructed = bool(first & 0x20)
    tag_number = first & 0x1F
    if tag_number == 0x1F:
        raise _TokenParseError("unsupported high-tag-number DER form")
    pos = offset + 1
    if pos >= len(data):
        raise _TokenParseError("truncated DER: missing length octet")
    length_byte = data[pos]
    pos += 1
    if length_byte & 0x80:
        octet_count = length_byte & 0x7F
        if octet_count == 0:
            raise _TokenParseError("indefinite-length DER is not supported")
        if pos + octet_count > len(data):
            raise _TokenParseError("truncated DER: missing long-form length octets")
        length = int.from_bytes(data[pos : pos + octet_count], "big")
        pos += octet_count
    else:
        length = length_byte
    if pos + length > len(data):
        raise _TokenParseError("truncated DER: content exceeds buffer")
    return (
        _DerNode(
            tag_class=tag_class,
            tag_number=tag_number,
            is_constructed=is_constructed,
            content=data[pos : pos + length],
        ),
        pos + length,
    )


def _read_der_children(content: bytes) -> list[_DerNode]:
    children: list[_DerNode] = []
    offset = 0
    while offset < len(content):
        node, offset = _read_der_tlv(content, offset)
        children.append(node)
    return children


def _expect_tag(node: _DerNode, tag_class: int, tag_number: int, label: str) -> _DerNode:
    if node.tag_class != tag_class or node.tag_number != tag_number:
        raise _TokenParseError(f"{label} has an unexpected DER tag")
    return node


def _decode_oid(content: bytes) -> str:
    if not content:
        raise _TokenParseError("empty OBJECT IDENTIFIER")
    first = content[0]
    if first < 40:
        arcs = [0, first]
    elif first < 80:
        arcs = [1, first - 40]
    else:
        arcs = [2, first - 80]
    value = 0
    for byte in content[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            arcs.append(value)
            value = 0
    if value != 0:
        raise _TokenParseError("truncated OBJECT IDENTIFIER arc")
    return ".".join(str(arc) for arc in arcs)


def _decode_integer(content: bytes) -> int:
    if not content:
        raise _TokenParseError("empty INTEGER")
    return int.from_bytes(content, "big", signed=True)


def _decode_generalized_time(content: bytes) -> datetime:
    try:
        text = content.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _TokenParseError("genTime is not ASCII") from exc
    try:
        parsed = datetime.strptime(text, "%Y%m%d%H%M%SZ")
    except ValueError as exc:
        raise _TokenParseError(f"genTime is not canonical GeneralizedTime: {exc}") from exc
    return parsed.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _ParsedTstInfo:
    message_imprint_algorithm_oid: str
    message_imprint_hashed_message: bytes
    gen_time: datetime
    accuracy_seconds: int
    accuracy_millis: int
    accuracy_micros: int


def _parse_tst_info(token_bytes: bytes) -> _ParsedTstInfo:
    try:
        content_info, end = _read_der_tlv(token_bytes, 0)
        if end != len(token_bytes):
            raise _TokenParseError("trailing bytes after ContentInfo")
        _expect_tag(content_info, _CLASS_UNIVERSAL, _TAG_SEQUENCE, "ContentInfo")
        top = _read_der_children(content_info.content)
        if len(top) != 2:
            raise _TokenParseError("ContentInfo must carry exactly two elements")
        content_type_node, wrapped = top
        _expect_tag(content_type_node, _CLASS_UNIVERSAL, _TAG_OID, "ContentInfo.contentType")
        if _decode_oid(content_type_node.content) != _OID_SIGNED_DATA:
            raise _TokenParseError("ContentInfo.contentType is not signedData")
        _expect_tag(wrapped, _CLASS_CONTEXT, 0, "ContentInfo.content")

        signed_data_node, sd_end = _read_der_tlv(wrapped.content, 0)
        if sd_end != len(wrapped.content):
            raise _TokenParseError("trailing bytes after SignedData")
        _expect_tag(signed_data_node, _CLASS_UNIVERSAL, _TAG_SEQUENCE, "SignedData")
        signed_data_children = _read_der_children(signed_data_node.content)
        if len(signed_data_children) < 3:
            raise _TokenParseError("SignedData is missing required fields")
        encap_content_info = signed_data_children[2]
        _expect_tag(
            encap_content_info, _CLASS_UNIVERSAL, _TAG_SEQUENCE, "SignedData.encapContentInfo"
        )
        encap_children = _read_der_children(encap_content_info.content)
        if len(encap_children) < 2:
            raise _TokenParseError("encapContentInfo is missing eContentType or eContent")
        econtent_type_node, econtent_wrapper = encap_children[0], encap_children[1]
        _expect_tag(
            econtent_type_node,
            _CLASS_UNIVERSAL,
            _TAG_OID,
            "encapContentInfo.eContentType",
        )
        if _decode_oid(econtent_type_node.content) != _OID_TST_INFO_CONTENT_TYPE:
            raise _TokenParseError("encapContentInfo.eContentType is not id-ct-TSTInfo")
        _expect_tag(econtent_wrapper, _CLASS_CONTEXT, 0, "encapContentInfo.eContent")
        octet_node, oct_end = _read_der_tlv(econtent_wrapper.content, 0)
        if oct_end != len(econtent_wrapper.content):
            raise _TokenParseError("trailing bytes after eContent")
        _expect_tag(octet_node, _CLASS_UNIVERSAL, _TAG_OCTET_STRING, "encapContentInfo.eContent")

        tst_info_node, tst_end = _read_der_tlv(octet_node.content, 0)
        if tst_end != len(octet_node.content):
            raise _TokenParseError("trailing bytes after TSTInfo")
        _expect_tag(tst_info_node, _CLASS_UNIVERSAL, _TAG_SEQUENCE, "TSTInfo")
        tst_children = _read_der_children(tst_info_node.content)
        if len(tst_children) < 5:
            raise _TokenParseError("TSTInfo is missing required fields")

        message_imprint_node = tst_children[2]
        _expect_tag(
            message_imprint_node, _CLASS_UNIVERSAL, _TAG_SEQUENCE, "TSTInfo.messageImprint"
        )
        mi_children = _read_der_children(message_imprint_node.content)
        if len(mi_children) != 2:
            raise _TokenParseError("messageImprint must carry exactly two elements")
        hash_alg_node, hashed_message_node = mi_children
        _expect_tag(
            hash_alg_node,
            _CLASS_UNIVERSAL,
            _TAG_SEQUENCE,
            "messageImprint.hashAlgorithm",
        )
        alg_children = _read_der_children(hash_alg_node.content)
        if not alg_children:
            raise _TokenParseError("hashAlgorithm is missing its algorithm OID")
        algorithm_oid = _decode_oid(
            _expect_tag(
                alg_children[0], _CLASS_UNIVERSAL, _TAG_OID, "hashAlgorithm.algorithm"
            ).content
        )
        hashed_message = _expect_tag(
            hashed_message_node,
            _CLASS_UNIVERSAL,
            _TAG_OCTET_STRING,
            "messageImprint.hashedMessage",
        ).content

        gen_time = _decode_generalized_time(
            _expect_tag(
                tst_children[4], _CLASS_UNIVERSAL, _TAG_GENERALIZED_TIME, "TSTInfo.genTime"
            ).content
        )

        accuracy_seconds = accuracy_millis = accuracy_micros = 0
        if len(tst_children) > 5:
            candidate = tst_children[5]
            if candidate.tag_class == _CLASS_UNIVERSAL and candidate.tag_number == _TAG_SEQUENCE:
                for child in _read_der_children(candidate.content):
                    if child.tag_class == _CLASS_UNIVERSAL and child.tag_number == _TAG_INTEGER:
                        accuracy_seconds = _decode_integer(child.content)
                    elif child.tag_class == _CLASS_CONTEXT and child.tag_number == 0:
                        accuracy_millis = _decode_integer(child.content)
                    elif child.tag_class == _CLASS_CONTEXT and child.tag_number == 1:
                        accuracy_micros = _decode_integer(child.content)
                if accuracy_seconds < 0 or accuracy_millis < 0 or accuracy_micros < 0:
                    raise _TokenParseError("Accuracy components must be non-negative")

        return _ParsedTstInfo(
            message_imprint_algorithm_oid=algorithm_oid,
            message_imprint_hashed_message=hashed_message,
            gen_time=gen_time,
            accuracy_seconds=accuracy_seconds,
            accuracy_millis=accuracy_millis,
            accuracy_micros=accuracy_micros,
        )
    except _TokenParseError:
        raise
    except (IndexError, UnicodeDecodeError) as exc:
        raise _TokenParseError(str(exc)) from exc


def verify_rfc3161_pre_outcome_receipt(
    *,
    commitment: Fixed13PreOutcomeCommitment,
    proof_type: str,
    reference_sha256: str,
    token_path: Path,
    trust_anchors: PinnedTrustAnchorSet,
    chain_path: Path | None = None,
    openssl_binary: str | None = None,
) -> PreOutcomeTimingReceiptVerdict:
    """Verify one RFC3161 receipt against ``commitment``, fully offline.

    ``proof_type``/``reference_sha256`` are passed as plain values (rather
    than a ``PreOutcomeTimingProofRef``) so this module never needs to import
    the eligibility module's types; the caller supplies both structural and
    semantic inputs, and both are required to reach ``verified=True``.
    """

    if type(commitment) is not Fixed13PreOutcomeCommitment:
        raise ValueError("commitment must be a Fixed13PreOutcomeCommitment")
    if type(trust_anchors) is not PinnedTrustAnchorSet:
        raise ValueError("trust_anchors must be a PinnedTrustAnchorSet")
    _require_str(proof_type, "proof_type")
    _require_sha256_hex(reference_sha256, "reference_sha256")

    commitment_sha256 = commitment.commitment_sha256()

    def _fail(
        reason: PreOutcomeTimingReceiptReasonCode,
        *,
        gen_time: datetime | None = None,
    ) -> PreOutcomeTimingReceiptVerdict:
        return PreOutcomeTimingReceiptVerdict(
            verified=False,
            reason_code=reason,
            commitment_sha256=commitment_sha256,
            gen_time=gen_time,
        )

    if proof_type != RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE:
        return _fail(PreOutcomeTimingReceiptReasonCode.UNSUPPORTED_PROOF_TYPE)

    token_path = Path(token_path)
    try:
        if not token_path.is_file():
            return _fail(PreOutcomeTimingReceiptReasonCode.RECEIPT_FILE_NOT_FOUND)
        token_bytes = token_path.read_bytes()
    except OSError:
        return _fail(PreOutcomeTimingReceiptReasonCode.RECEIPT_FILE_NOT_FOUND)

    if hashlib.sha256(token_bytes).hexdigest() != reference_sha256:
        return _fail(PreOutcomeTimingReceiptReasonCode.REFERENCE_SHA256_MISMATCH)

    try:
        parsed = _parse_tst_info(token_bytes)
    except _TokenParseError:
        return _fail(PreOutcomeTimingReceiptReasonCode.TOKEN_MALFORMED)

    if parsed.message_imprint_algorithm_oid != _OID_SHA256:
        return _fail(
            PreOutcomeTimingReceiptReasonCode.MESSAGE_IMPRINT_ALGORITHM_UNSUPPORTED,
            gen_time=parsed.gen_time,
        )
    if parsed.message_imprint_hashed_message != bytes.fromhex(commitment_sha256):
        return _fail(
            PreOutcomeTimingReceiptReasonCode.MESSAGE_IMPRINT_MISMATCH,
            gen_time=parsed.gen_time,
        )

    if parsed.gen_time >= commitment.target_scheduled_at:
        return _fail(
            PreOutcomeTimingReceiptReasonCode.GENTIME_NOT_BEFORE_TARGET_SCHEDULE,
            gen_time=parsed.gen_time,
        )
    accuracy_upper_seconds = (
        parsed.accuracy_seconds
        + parsed.accuracy_millis / 1_000.0
        + parsed.accuracy_micros / 1_000_000.0
    )
    conservative_gen_time = parsed.gen_time + timedelta(seconds=accuracy_upper_seconds)
    if conservative_gen_time >= commitment.target_scheduled_at:
        return _fail(
            PreOutcomeTimingReceiptReasonCode.GENTIME_ACCURACY_MARGIN_NOT_BEFORE_TARGET_SCHEDULE,
            gen_time=parsed.gen_time,
        )

    resolution = resolve_openssl_binary(openssl_binary)
    if not resolution.capable or resolution.binary_path is None:
        return _fail(
            PreOutcomeTimingReceiptReasonCode.VERIFIER_BACKEND_UNAVAILABLE,
            gen_time=parsed.gen_time,
        )
    openssl_path = resolution.binary_path

    with tempfile.TemporaryDirectory(prefix="lottolab-rfc3161-verify-") as raw_tmp_dir:
        tmp_dir = Path(raw_tmp_dir)
        ca_bundle_path = tmp_dir / "trust-anchors.pem"
        ca_bundle_path.write_text(trust_anchors.bundle_text(), encoding="ascii")
        args = [
            openssl_path,
            "ts",
            "-verify",
            "-digest",
            commitment_sha256,
            "-in",
            str(token_path),
            "-token_in",
            "-CAfile",
            str(ca_bundle_path),
        ]
        if chain_path is not None and Path(chain_path).is_file():
            args += ["-untrusted", str(chain_path)]
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                timeout=_OPENSSL_VERIFY_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return _fail(
                PreOutcomeTimingReceiptReasonCode.SIGNATURE_OR_CHAIN_INVALID,
                gen_time=parsed.gen_time,
            )

    if result.returncode != 0:
        return _fail(
            PreOutcomeTimingReceiptReasonCode.SIGNATURE_OR_CHAIN_INVALID,
            gen_time=parsed.gen_time,
        )

    return PreOutcomeTimingReceiptVerdict(
        verified=True,
        reason_code=PreOutcomeTimingReceiptReasonCode.OK,
        commitment_sha256=commitment_sha256,
        gen_time=parsed.gen_time,
    )


__all__ = [
    "LOTTOLAB_FIXED13_PRE_OUTCOME_COMMITMENT_SCHEMA_VERSION",
    "RFC3161_PRE_OUTCOME_TIMING_PROOF_TYPE",
    "Fixed13PreOutcomeCommitment",
    "PinnedTrustAnchorSet",
    "PreOutcomeTimingReceiptReasonCode",
    "PreOutcomeTimingReceiptVerdict",
    "verify_rfc3161_pre_outcome_receipt",
]
