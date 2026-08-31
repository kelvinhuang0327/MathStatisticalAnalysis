"""Outcome-free T539 PRETARGET external seal and receipt contracts.

The canonical seal deliberately excludes every clock value.  Only a verified
Rekor transparency-log integrated time can qualify the seal as prospective.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import PreOutcomeTargetRegistration
from lottolab.domain.prospective_observer import ObservationTarget

T539_PRETARGET_SEAL_SCHEMA_VERSION = "T539_PRETARGET_SEAL_V1"
T539_PRETARGET_RECEIPT_SCHEMA_VERSION = "T539_REKOR_RECEIPT_V1"
T539_PRETARGET_RECORD_SCHEMA_VERSION = "T539_PRETARGET_EXTERNAL_SEAL_RECEIPT_RECORD_V1"
T539_PRETARGET_SNAPSHOT_SCHEMA_VERSION = "T539_PROSPECTIVE_PRETARGET_SNAPSHOT_V1"

T539_FREEZE_BOUNDARY = "115000186"
T539_FREEZE_MANIFEST_SHA256 = (
    "f1b299ace019393440bce8bd2768f6618b2362d220d81b4cc14151a5080908a8"
)
T539_RULE_FINGERPRINT = (
    "eb4eb89082cd782041c240e80858efd8453c3bbf08edec3b76e98e2e8051f446"
)
T539_INTEGRATED_STACK_COMMIT = "1fdb2d53a7ef62baa8bdbd5ce962f7aeb0176c62"
T539_INTEGRATED_STACK_TREE = "7a3e0a6892cf666ef9f20826225ccfffab455e07"
SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY = "SIGSTORE_PUBLIC_GOOD_TUF_ROOT"

_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_GIT_OBJECT_ID = re.compile(r"[0-9a-f]{40}", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_REKOR_UUID = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_TRUST_ROOT_VERSION = re.compile(r"sha256:[0-9a-f]{64}", flags=re.ASCII)
_PROHIBITED_OUTCOME_KEYS = frozenset(
    {
        "main_numbers",
        "official_numbers",
        "official_outcome",
        "outcome",
        "outcome_hash",
        "outcome_numbers",
        "target_official_outcome",
        "target_outcome",
        "winning_numbers",
    }
)
_PROHIBITED_SECRET_KEYS = frozenset(
    {
        "access_token",
        "credential",
        "credentials",
        "password",
        "private_key",
        "privatekey",
        "secret",
        "secret_key",
        "token",
    }
)


class PretargetSealStatus(StrEnum):
    """Durable terminal states plus the transient pre-deadline state."""

    PENDING = "PENDING_EXTERNAL_PRETARGET_SEAL"
    SEALED = "PRETARGET_SEAL_CONFIRMED_BEFORE_OUTCOME"
    MISSED = "MISSED_PRETARGET_SEAL"


class SealRecordCreateOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    CONFLICT = "CONFLICT"


class PretargetSealConflictError(RuntimeError):
    """A canonical target already has a different durable state."""


class ExternalReceiptVerificationError(ValueError):
    """Rekor/Sigstore evidence did not verify for the exact seal."""


def canonical_json_bytes(value: object) -> bytes:
    """Sorted-key compact UTF-8 JSON with no trailing newline."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} fields differ; missing={missing}, unknown={unknown}")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    object_mapping = cast(Mapping[object, object], value)
    if any(type(key) is not str for key in object_mapping):
        raise ValueError(f"{label} keys must be strings")
    return cast(Mapping[str, object], object_mapping)


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _sha256(value: object, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _git_object_id(value: object, label: str) -> str:
    text = _text(value, label)
    if _GIT_OBJECT_ID.fullmatch(text) is None:
        raise ValueError(f"{label} must be a lowercase 40-character Git object ID")
    return text


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{label} must use UTC")
    return value


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _datetime_from_text(value: object, label: str) -> datetime:
    text = _text(value, label)
    if not text.endswith("Z"):
        raise ValueError(f"{label} must use canonical UTC text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} must use canonical UTC text") from exc
    _utc(parsed, label)
    if _utc_text(parsed) != text:
        raise ValueError(f"{label} must use canonical UTC text")
    return parsed


def _date_from_text(value: object, label: str) -> date:
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a canonical ISO date") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{label} must be a canonical ISO date")
    return parsed


def _decode_base64(value: object, label: str) -> bytes:
    text = _text(value, label)
    try:
        decoded = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{label} must be canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != text:
        raise ValueError(f"{label} must be canonical base64")
    return decoded


def _json_object_text(value: object, label: str) -> str:
    if type(value) is str:
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{label} must be valid JSON") from exc
    else:
        parsed = value
    mapping = _mapping(parsed, label)
    return canonical_json_bytes(mapping).decode("utf-8")


def _json_object(text: str, label: str) -> Mapping[str, object]:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:  # pragma: no cover - guarded on creation
        raise ValueError(f"{label} must be valid JSON") from exc
    return _mapping(parsed, label)


def _reject_named_keys(value: object, prohibited: frozenset[str], label: str) -> None:
    if isinstance(value, Mapping):
        object_mapping = cast(Mapping[object, object], value)
        for raw_key, item in object_mapping.items():
            if type(raw_key) is not str:
                raise ValueError(f"{label} keys must be strings")
            normalized = raw_key.casefold().replace("-", "_")
            if normalized in prohibited:
                raise ValueError(f"{label} contains prohibited field {raw_key!r}")
            _reject_named_keys(item, prohibited, f"{label}.{raw_key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        object_sequence = cast(Sequence[object], value)
        for index, item in enumerate(object_sequence):
            _reject_named_keys(item, prohibited, f"{label}[{index}]")


def _target_from_dict(value: object) -> ObservationTarget:
    target = _mapping(value, "seal.target")
    _expect_keys(target, {"draw_date", "draw_number", "lottery_type"}, "seal.target")
    try:
        lottery_type = LotteryType(_text(target["lottery_type"], "seal.target.lottery_type"))
    except ValueError as exc:
        raise ValueError("seal.target.lottery_type is unsupported") from exc
    return ObservationTarget(
        lottery_type=lottery_type,
        draw_number=_text(target["draw_number"], "seal.target.draw_number"),
        draw_date=_date_from_text(target["draw_date"], "seal.target.draw_date"),
    )


@dataclass(frozen=True, slots=True)
class T539PretargetSnapshotBinding:
    """Verified identity projection of an existing deterministic PRETARGET snapshot."""

    target: ObservationTarget
    snapshot_content_hash: str
    rule_fingerprint: str
    freeze_boundary: str
    freeze_manifest_sha256: str

    def __post_init__(self) -> None:
        if type(self.target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        if self.target.lottery_type is not LotteryType.DAILY_539:
            raise ValueError("T539 PRETARGET seal requires DAILY_539")
        if int(self.target.draw_number) <= int(T539_FREEZE_BOUNDARY):
            raise ValueError("T539 PRETARGET target must be strictly after the freeze boundary")
        _sha256(self.snapshot_content_hash, "snapshot_content_hash")
        if self.rule_fingerprint != T539_RULE_FINGERPRINT:
            raise ValueError("rule_fingerprint does not match the frozen T539 rule")
        if self.freeze_boundary != T539_FREEZE_BOUNDARY:
            raise ValueError("freeze_boundary does not match the frozen T539 boundary")
        if self.freeze_manifest_sha256 != T539_FREEZE_MANIFEST_SHA256:
            raise ValueError("freeze_manifest_sha256 does not match the frozen T539 manifest")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Mapping[str, object],
        registration: PreOutcomeTargetRegistration,
    ) -> T539PretargetSnapshotBinding:
        if type(registration) is not PreOutcomeTargetRegistration:
            raise ValueError("registration must be a PreOutcomeTargetRegistration")
        value = _mapping(snapshot, "snapshot")
        _reject_named_keys(value, _PROHIBITED_OUTCOME_KEYS, "snapshot")
        if value.get("schema_version") != T539_PRETARGET_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("PRETARGET snapshot schema_version mismatch")

        supplied_hash = _sha256(
            value.get("snapshot_content_hash"), "snapshot.snapshot_content_hash"
        )
        material = dict(value)
        material.pop("snapshot_content_hash", None)
        if supplied_hash != canonical_sha256(material):
            raise ValueError("PRETARGET snapshot_content_hash mismatch")

        target_identity = _text(value.get("target_identity"), "snapshot.target_identity")
        if _DRAW_NUMBER.fullmatch(target_identity) is None:
            raise ValueError("snapshot.target_identity must be an ASCII decimal draw number")
        if target_identity != registration.target.draw_number:
            raise ValueError("snapshot target does not match pre-outcome registration")

        freeze = _mapping(value.get("freeze"), "snapshot.freeze")
        boundary = _text(
            freeze.get("freeze_boundary_target_identity"),
            "snapshot.freeze.freeze_boundary_target_identity",
        )
        manifest = _sha256(
            freeze.get("freeze_manifest_sha256"),
            "snapshot.freeze.freeze_manifest_sha256",
        )
        rule = _sha256(value.get("rule_fingerprint"), "snapshot.rule_fingerprint")
        return cls(
            target=registration.target,
            snapshot_content_hash=supplied_hash,
            rule_fingerprint=rule,
            freeze_boundary=boundary,
            freeze_manifest_sha256=manifest,
        )


@dataclass(frozen=True, slots=True)
class T539PretargetSeal:
    """Canonical T539_PRETARGET_SEAL_V1 identity."""

    schema_version: str
    target: ObservationTarget
    snapshot_content_hash: str
    rule_fingerprint: str
    freeze_boundary: str
    freeze_manifest_sha256: str
    integrated_stack_commit: str
    integrated_stack_tree: str
    pre_outcome_registration_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != T539_PRETARGET_SEAL_SCHEMA_VERSION:
            raise ValueError("unsupported T539 PRETARGET seal schema_version")
        if type(self.target) is not ObservationTarget:
            raise ValueError("target must be an ObservationTarget")
        if self.target.lottery_type is not LotteryType.DAILY_539:
            raise ValueError("T539 PRETARGET seal requires DAILY_539")
        if int(self.target.draw_number) <= int(T539_FREEZE_BOUNDARY):
            raise ValueError("T539 PRETARGET target must be strictly after the freeze boundary")
        _sha256(self.snapshot_content_hash, "snapshot_content_hash")
        if self.rule_fingerprint != T539_RULE_FINGERPRINT:
            raise ValueError("rule_fingerprint does not match the frozen T539 rule")
        if self.freeze_boundary != T539_FREEZE_BOUNDARY:
            raise ValueError("freeze_boundary does not match the frozen T539 boundary")
        if self.freeze_manifest_sha256 != T539_FREEZE_MANIFEST_SHA256:
            raise ValueError("freeze_manifest_sha256 does not match the frozen T539 manifest")
        if self.integrated_stack_commit != T539_INTEGRATED_STACK_COMMIT:
            raise ValueError("integrated_stack_commit does not match the approved stack")
        if self.integrated_stack_tree != T539_INTEGRATED_STACK_TREE:
            raise ValueError("integrated_stack_tree does not match the approved stack")
        _sha256(self.pre_outcome_registration_digest, "pre_outcome_registration_digest")

    @classmethod
    def create(
        cls,
        registration: PreOutcomeTargetRegistration,
        snapshot: T539PretargetSnapshotBinding,
    ) -> T539PretargetSeal:
        if type(registration) is not PreOutcomeTargetRegistration:
            raise ValueError("registration must be a PreOutcomeTargetRegistration")
        if type(snapshot) is not T539PretargetSnapshotBinding:
            raise ValueError("snapshot must be a T539PretargetSnapshotBinding")
        if registration.target != snapshot.target:
            raise ValueError("snapshot target does not match pre-outcome registration")
        return cls(
            schema_version=T539_PRETARGET_SEAL_SCHEMA_VERSION,
            target=registration.target,
            snapshot_content_hash=snapshot.snapshot_content_hash,
            rule_fingerprint=snapshot.rule_fingerprint,
            freeze_boundary=snapshot.freeze_boundary,
            freeze_manifest_sha256=snapshot.freeze_manifest_sha256,
            integrated_stack_commit=T539_INTEGRATED_STACK_COMMIT,
            integrated_stack_tree=T539_INTEGRATED_STACK_TREE,
            pre_outcome_registration_digest=registration.registration_digest,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "freeze_boundary": self.freeze_boundary,
            "freeze_manifest_sha256": self.freeze_manifest_sha256,
            "integrated_stack_commit": self.integrated_stack_commit,
            "integrated_stack_tree": self.integrated_stack_tree,
            "pre_outcome_registration_digest": self.pre_outcome_registration_digest,
            "rule_fingerprint": self.rule_fingerprint,
            "schema_version": self.schema_version,
            "snapshot_content_hash": self.snapshot_content_hash,
            "target": self.target.canonical_dict(),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.canonical_dict())

    @property
    def seal_digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def validate_against(
        self,
        registration: PreOutcomeTargetRegistration,
        snapshot: T539PretargetSnapshotBinding,
    ) -> None:
        expected = T539PretargetSeal.create(registration, snapshot)
        if self != expected or self.seal_digest != expected.seal_digest:
            raise PretargetSealConflictError(
                "stored seal does not match registration and deterministic snapshot"
            )

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> T539PretargetSeal:
        mapping = _mapping(value, "seal")
        _expect_keys(
            mapping,
            {
                "freeze_boundary",
                "freeze_manifest_sha256",
                "integrated_stack_commit",
                "integrated_stack_tree",
                "pre_outcome_registration_digest",
                "rule_fingerprint",
                "schema_version",
                "snapshot_content_hash",
                "target",
            },
            "seal",
        )
        return cls(
            schema_version=_text(mapping["schema_version"], "seal.schema_version"),
            target=_target_from_dict(mapping["target"]),
            snapshot_content_hash=_sha256(
                mapping["snapshot_content_hash"], "seal.snapshot_content_hash"
            ),
            rule_fingerprint=_sha256(mapping["rule_fingerprint"], "seal.rule_fingerprint"),
            freeze_boundary=_text(mapping["freeze_boundary"], "seal.freeze_boundary"),
            freeze_manifest_sha256=_sha256(
                mapping["freeze_manifest_sha256"], "seal.freeze_manifest_sha256"
            ),
            integrated_stack_commit=_git_object_id(
                mapping["integrated_stack_commit"], "seal.integrated_stack_commit"
            ),
            integrated_stack_tree=_git_object_id(
                mapping["integrated_stack_tree"], "seal.integrated_stack_tree"
            ),
            pre_outcome_registration_digest=_sha256(
                mapping["pre_outcome_registration_digest"],
                "seal.pre_outcome_registration_digest",
            ),
        )


@dataclass(frozen=True, slots=True)
class RekorReceiptEvidence:
    """Immutable evidence needed to re-fetch and reverify one Rekor entry."""

    schema_version: str
    rekor_entry_id: str
    log_id: str | None
    log_index: int
    integrated_time: int
    entry_kind: str
    entry_version: str
    canonical_entry_body: str
    canonical_entry_body_sha256: str
    seal_digest: str
    signing_material_sha256: str
    signed_entry_timestamp: str | None
    inclusion_proof_json: str
    sigstore_bundle_json: str
    sigstore_bundle_sha256: str
    receipt_identity: str

    def __post_init__(self) -> None:
        if self.schema_version != T539_PRETARGET_RECEIPT_SCHEMA_VERSION:
            raise ValueError("unsupported T539 Rekor receipt schema_version")
        if _REKOR_UUID.fullmatch(self.rekor_entry_id) is None:
            raise ValueError("rekor_entry_id must be the canonical RFC6962 leaf-hash UUID")
        if self.log_id is not None:
            _decode_base64(self.log_id, "log_id")
        _integer(self.log_index, "log_index")
        _integer(self.integrated_time, "integrated_time", minimum=1)
        if self.entry_kind != "hashedrekord":
            raise ValueError("Rekor receipt entry_kind must be hashedrekord")
        if self.entry_version not in {"0.0.1", "0.0.2"}:
            raise ValueError("Rekor receipt entry_version is unsupported")
        body = _decode_base64(self.canonical_entry_body, "canonical_entry_body")
        if hashlib.sha256(body).hexdigest() != self.canonical_entry_body_sha256:
            raise ValueError("canonical_entry_body_sha256 mismatch")
        _sha256(self.seal_digest, "seal_digest")
        _sha256(self.signing_material_sha256, "signing_material_sha256")
        if self.signed_entry_timestamp is not None:
            _decode_base64(self.signed_entry_timestamp, "signed_entry_timestamp")

        proof = _json_object(self.inclusion_proof_json, "inclusion_proof")
        if canonical_json_bytes(proof).decode("utf-8") != self.inclusion_proof_json:
            raise ValueError("inclusion_proof_json must use canonical JSON")
        bundle = _json_object(self.sigstore_bundle_json, "sigstore_bundle")
        _reject_named_keys(bundle, _PROHIBITED_SECRET_KEYS, "sigstore_bundle")
        if canonical_json_bytes(bundle).decode("utf-8") != self.sigstore_bundle_json:
            raise ValueError("sigstore_bundle_json must use canonical JSON")
        if hashlib.sha256(self.sigstore_bundle_json.encode("utf-8")).hexdigest() != (
            self.sigstore_bundle_sha256
        ):
            raise ValueError("sigstore_bundle_sha256 mismatch")
        _sha256(self.receipt_identity, "receipt_identity")
        if self.receipt_identity != canonical_sha256(self.canonical_material()):
            raise ValueError("receipt_identity does not match receipt evidence")

        try:
            datetime.fromtimestamp(self.integrated_time, tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("integrated_time is outside the supported UTC range") from exc

    @property
    def external_authority_time(self) -> datetime:
        return datetime.fromtimestamp(self.integrated_time, tz=UTC)

    def canonical_material(self) -> dict[str, object]:
        return {
            "canonical_entry_body": self.canonical_entry_body,
            "canonical_entry_body_sha256": self.canonical_entry_body_sha256,
            "entry_kind": self.entry_kind,
            "entry_version": self.entry_version,
            "inclusion_proof": dict(_json_object(self.inclusion_proof_json, "inclusion_proof")),
            "integrated_time": self.integrated_time,
            "log_id": self.log_id,
            "log_index": self.log_index,
            "rekor_entry_id": self.rekor_entry_id,
            "schema_version": self.schema_version,
            "seal_digest": self.seal_digest,
            "signed_entry_timestamp": self.signed_entry_timestamp,
            "signing_material_sha256": self.signing_material_sha256,
            "sigstore_bundle": dict(_json_object(self.sigstore_bundle_json, "sigstore_bundle")),
            "sigstore_bundle_sha256": self.sigstore_bundle_sha256,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_material(), "receipt_identity": self.receipt_identity}

    @classmethod
    def create(
        cls,
        *,
        rekor_entry_id: str,
        log_id: str | None,
        log_index: int,
        integrated_time: int,
        entry_kind: str,
        entry_version: str,
        canonical_entry_body: str,
        seal_digest: str,
        signing_material_sha256: str,
        signed_entry_timestamp: str | None,
        inclusion_proof: Mapping[str, object],
        sigstore_bundle: Mapping[str, object],
    ) -> RekorReceiptEvidence:
        body = _decode_base64(canonical_entry_body, "canonical_entry_body")
        proof_json = _json_object_text(inclusion_proof, "inclusion_proof")
        bundle_json = _json_object_text(sigstore_bundle, "sigstore_bundle")
        material: dict[str, object] = {
            "canonical_entry_body": canonical_entry_body,
            "canonical_entry_body_sha256": hashlib.sha256(body).hexdigest(),
            "entry_kind": entry_kind,
            "entry_version": entry_version,
            "inclusion_proof": dict(_json_object(proof_json, "inclusion_proof")),
            "integrated_time": integrated_time,
            "log_id": log_id,
            "log_index": log_index,
            "rekor_entry_id": rekor_entry_id,
            "schema_version": T539_PRETARGET_RECEIPT_SCHEMA_VERSION,
            "seal_digest": seal_digest,
            "signed_entry_timestamp": signed_entry_timestamp,
            "signing_material_sha256": signing_material_sha256,
            "sigstore_bundle": dict(_json_object(bundle_json, "sigstore_bundle")),
            "sigstore_bundle_sha256": hashlib.sha256(bundle_json.encode("utf-8")).hexdigest(),
        }
        return cls(
            schema_version=T539_PRETARGET_RECEIPT_SCHEMA_VERSION,
            rekor_entry_id=rekor_entry_id,
            log_id=log_id,
            log_index=log_index,
            integrated_time=integrated_time,
            entry_kind=entry_kind,
            entry_version=entry_version,
            canonical_entry_body=canonical_entry_body,
            canonical_entry_body_sha256=cast(str, material["canonical_entry_body_sha256"]),
            seal_digest=seal_digest,
            signing_material_sha256=signing_material_sha256,
            signed_entry_timestamp=signed_entry_timestamp,
            inclusion_proof_json=proof_json,
            sigstore_bundle_json=bundle_json,
            sigstore_bundle_sha256=cast(str, material["sigstore_bundle_sha256"]),
            receipt_identity=canonical_sha256(material),
        )

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> RekorReceiptEvidence:
        mapping = _mapping(value, "receipt")
        _expect_keys(
            mapping,
            {
                "canonical_entry_body",
                "canonical_entry_body_sha256",
                "entry_kind",
                "entry_version",
                "inclusion_proof",
                "integrated_time",
                "log_id",
                "log_index",
                "receipt_identity",
                "rekor_entry_id",
                "schema_version",
                "seal_digest",
                "signed_entry_timestamp",
                "signing_material_sha256",
                "sigstore_bundle",
                "sigstore_bundle_sha256",
            },
            "receipt",
        )
        return cls(
            schema_version=_text(mapping["schema_version"], "receipt.schema_version"),
            rekor_entry_id=_text(mapping["rekor_entry_id"], "receipt.rekor_entry_id"),
            log_id=_optional_text(mapping["log_id"], "receipt.log_id"),
            log_index=_integer(mapping["log_index"], "receipt.log_index"),
            integrated_time=_integer(
                mapping["integrated_time"], "receipt.integrated_time", minimum=1
            ),
            entry_kind=_text(mapping["entry_kind"], "receipt.entry_kind"),
            entry_version=_text(mapping["entry_version"], "receipt.entry_version"),
            canonical_entry_body=_text(
                mapping["canonical_entry_body"], "receipt.canonical_entry_body"
            ),
            canonical_entry_body_sha256=_sha256(
                mapping["canonical_entry_body_sha256"],
                "receipt.canonical_entry_body_sha256",
            ),
            seal_digest=_sha256(mapping["seal_digest"], "receipt.seal_digest"),
            signing_material_sha256=_sha256(
                mapping["signing_material_sha256"], "receipt.signing_material_sha256"
            ),
            signed_entry_timestamp=_optional_text(
                mapping["signed_entry_timestamp"], "receipt.signed_entry_timestamp"
            ),
            inclusion_proof_json=_json_object_text(
                mapping["inclusion_proof"], "receipt.inclusion_proof"
            ),
            sigstore_bundle_json=_json_object_text(
                mapping["sigstore_bundle"], "receipt.sigstore_bundle"
            ),
            sigstore_bundle_sha256=_sha256(
                mapping["sigstore_bundle_sha256"], "receipt.sigstore_bundle_sha256"
            ),
            receipt_identity=_sha256(mapping["receipt_identity"], "receipt.receipt_identity"),
        )


@dataclass(frozen=True, slots=True)
class RekorVerificationReference:
    """Identity of the approved trust root and official verifier that succeeded."""

    trust_root_identity: str
    trust_root_version: str
    verifier: str
    verifier_version: str

    def __post_init__(self) -> None:
        if self.trust_root_identity != SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY:
            raise ValueError("receipt was not verified under the approved Sigstore trust root")
        if _TRUST_ROOT_VERSION.fullmatch(self.trust_root_version) is None:
            raise ValueError("trust_root_version must be an exact canonical root SHA256")
        if self.verifier != "sigstore-python":
            raise ValueError("receipt verifier must be sigstore-python")
        _text(self.verifier_version, "verifier_version")

    def canonical_dict(self) -> dict[str, str]:
        return {
            "trust_root_identity": self.trust_root_identity,
            "trust_root_version": self.trust_root_version,
            "verifier": self.verifier,
            "verifier_version": self.verifier_version,
        }

    @classmethod
    def from_canonical_dict(
        cls, value: Mapping[str, object]
    ) -> RekorVerificationReference:
        mapping = _mapping(value, "receipt_verification")
        _expect_keys(
            mapping,
            {"trust_root_identity", "trust_root_version", "verifier", "verifier_version"},
            "receipt_verification",
        )
        return cls(
            trust_root_identity=_text(
                mapping["trust_root_identity"], "receipt_verification.trust_root_identity"
            ),
            trust_root_version=_text(
                mapping["trust_root_version"], "receipt_verification.trust_root_version"
            ),
            verifier=_text(mapping["verifier"], "receipt_verification.verifier"),
            verifier_version=_text(
                mapping["verifier_version"], "receipt_verification.verifier_version"
            ),
        )


@dataclass(frozen=True, slots=True)
class VerifiedRekorReceipt:
    receipt: RekorReceiptEvidence
    verification: RekorVerificationReference

    def __post_init__(self) -> None:
        if type(self.receipt) is not RekorReceiptEvidence:
            raise ValueError("receipt must be RekorReceiptEvidence")
        if type(self.verification) is not RekorVerificationReference:
            raise ValueError("verification must be RekorVerificationReference")


@dataclass(frozen=True, slots=True)
class T539PretargetSealRecord:
    """Restart-safe first-wins state; contains no local operational timestamp."""

    schema_version: str
    status: PretargetSealStatus
    seal: T539PretargetSeal
    seal_digest: str
    prediction_input_identity: str
    outcome_binding_identity: str
    outcome_authority_time: datetime
    receipt: RekorReceiptEvidence | None
    receipt_verification: RekorVerificationReference | None

    def __post_init__(self) -> None:
        if self.schema_version != T539_PRETARGET_RECORD_SCHEMA_VERSION:
            raise ValueError("unsupported T539 PRETARGET seal record schema_version")
        if self.status not in {PretargetSealStatus.SEALED, PretargetSealStatus.MISSED}:
            raise ValueError("a durable seal record must be SEALED or MISSED")
        if type(self.seal) is not T539PretargetSeal:
            raise ValueError("seal must be a T539PretargetSeal")
        if self.seal_digest != self.seal.seal_digest:
            raise ValueError("seal_digest does not match canonical seal bytes")
        _sha256(self.prediction_input_identity, "prediction_input_identity")
        _sha256(self.outcome_binding_identity, "outcome_binding_identity")
        _utc(self.outcome_authority_time, "outcome_authority_time")

        if self.status is PretargetSealStatus.SEALED:
            if type(self.receipt) is not RekorReceiptEvidence:
                raise ValueError("SEALED record requires Rekor receipt evidence")
            if type(self.receipt_verification) is not RekorVerificationReference:
                raise ValueError("SEALED record requires a receipt verification reference")
            if self.receipt.seal_digest != self.seal_digest:
                raise ValueError("receipt does not bind the record seal_digest")
            if self.receipt.external_authority_time >= self.outcome_authority_time:
                raise ValueError("Rekor integrated time is not strictly before outcome authority")
        elif self.receipt is not None or self.receipt_verification is not None:
            raise ValueError("MISSED record must not carry a receipt")

    @classmethod
    def sealed(
        cls,
        registration: PreOutcomeTargetRegistration,
        seal: T539PretargetSeal,
        verified_receipt: VerifiedRekorReceipt,
    ) -> T539PretargetSealRecord:
        return cls(
            schema_version=T539_PRETARGET_RECORD_SCHEMA_VERSION,
            status=PretargetSealStatus.SEALED,
            seal=seal,
            seal_digest=seal.seal_digest,
            prediction_input_identity=registration.prediction_input_identity,
            outcome_binding_identity=registration.outcome_binding_identity,
            outcome_authority_time=registration.announcement.scheduled_at,
            receipt=verified_receipt.receipt,
            receipt_verification=verified_receipt.verification,
        )

    @classmethod
    def missed(
        cls,
        registration: PreOutcomeTargetRegistration,
        seal: T539PretargetSeal,
    ) -> T539PretargetSealRecord:
        return cls(
            schema_version=T539_PRETARGET_RECORD_SCHEMA_VERSION,
            status=PretargetSealStatus.MISSED,
            seal=seal,
            seal_digest=seal.seal_digest,
            prediction_input_identity=registration.prediction_input_identity,
            outcome_binding_identity=registration.outcome_binding_identity,
            outcome_authority_time=registration.announcement.scheduled_at,
            receipt=None,
            receipt_verification=None,
        )

    def validate_against(
        self,
        registration: PreOutcomeTargetRegistration,
        snapshot: T539PretargetSnapshotBinding,
    ) -> None:
        self.seal.validate_against(registration, snapshot)
        if (
            self.prediction_input_identity != registration.prediction_input_identity
            or self.outcome_binding_identity != registration.outcome_binding_identity
            or self.seal.pre_outcome_registration_digest != registration.registration_digest
            or self.outcome_authority_time != registration.announcement.scheduled_at
        ):
            raise PretargetSealConflictError(
                "stored record does not match existing pre-outcome registration authority"
            )

    @property
    def external_seal_authority_time(self) -> datetime | None:
        return self.receipt.external_authority_time if self.receipt is not None else None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "outcome_authority_time": _utc_text(self.outcome_authority_time),
            "outcome_binding_identity": self.outcome_binding_identity,
            "prediction_input_identity": self.prediction_input_identity,
            "receipt": self.receipt.canonical_dict() if self.receipt is not None else None,
            "receipt_verification": (
                self.receipt_verification.canonical_dict()
                if self.receipt_verification is not None
                else None
            ),
            "schema_version": self.schema_version,
            "seal": self.seal.canonical_dict(),
            "seal_digest": self.seal_digest,
            "status": self.status.value,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.canonical_dict())

    @classmethod
    def from_canonical_dict(cls, value: Mapping[str, object]) -> T539PretargetSealRecord:
        mapping = _mapping(value, "seal_record")
        _expect_keys(
            mapping,
            {
                "outcome_authority_time",
                "outcome_binding_identity",
                "prediction_input_identity",
                "receipt",
                "receipt_verification",
                "schema_version",
                "seal",
                "seal_digest",
                "status",
            },
            "seal_record",
        )
        try:
            status = PretargetSealStatus(_text(mapping["status"], "seal_record.status"))
        except ValueError as exc:
            raise ValueError("seal_record.status is unsupported") from exc
        raw_receipt = mapping["receipt"]
        raw_verification = mapping["receipt_verification"]
        return cls(
            schema_version=_text(mapping["schema_version"], "seal_record.schema_version"),
            status=status,
            seal=T539PretargetSeal.from_canonical_dict(
                _mapping(mapping["seal"], "seal_record.seal")
            ),
            seal_digest=_sha256(mapping["seal_digest"], "seal_record.seal_digest"),
            prediction_input_identity=_sha256(
                mapping["prediction_input_identity"],
                "seal_record.prediction_input_identity",
            ),
            outcome_binding_identity=_sha256(
                mapping["outcome_binding_identity"],
                "seal_record.outcome_binding_identity",
            ),
            outcome_authority_time=_datetime_from_text(
                mapping["outcome_authority_time"], "seal_record.outcome_authority_time"
            ),
            receipt=(
                None
                if raw_receipt is None
                else RekorReceiptEvidence.from_canonical_dict(
                    _mapping(raw_receipt, "seal_record.receipt")
                )
            ),
            receipt_verification=(
                None
                if raw_verification is None
                else RekorVerificationReference.from_canonical_dict(
                    _mapping(raw_verification, "seal_record.receipt_verification")
                )
            ),
        )


__all__ = [
    "SIGSTORE_PUBLIC_GOOD_TUF_ROOT_IDENTITY",
    "T539_FREEZE_BOUNDARY",
    "T539_FREEZE_MANIFEST_SHA256",
    "T539_INTEGRATED_STACK_COMMIT",
    "T539_INTEGRATED_STACK_TREE",
    "T539_PRETARGET_RECEIPT_SCHEMA_VERSION",
    "T539_PRETARGET_RECORD_SCHEMA_VERSION",
    "T539_PRETARGET_SEAL_SCHEMA_VERSION",
    "T539_RULE_FINGERPRINT",
    "ExternalReceiptVerificationError",
    "PretargetSealConflictError",
    "PretargetSealStatus",
    "RekorReceiptEvidence",
    "RekorVerificationReference",
    "SealRecordCreateOutcome",
    "T539PretargetSeal",
    "T539PretargetSealRecord",
    "T539PretargetSnapshotBinding",
    "VerifiedRekorReceipt",
    "canonical_json_bytes",
    "canonical_sha256",
]
