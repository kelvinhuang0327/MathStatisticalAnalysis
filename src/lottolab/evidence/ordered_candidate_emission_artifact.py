"""LCJ-1 serialization and tamper verification for ordered emissions."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.evidence.canonical_json import (
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
)

ORDERED_CANDIDATE_EMISSION_ARTIFACT_SCHEMA_VERSION = "1.0.0"

_PLACEHOLDER_SHA256 = "0" * 64
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class OrderedCandidateEmissionArtifactShapeError(ValueError):
    """Artifact bytes do not match the exact closed schema."""


class OrderedCandidateEmissionArtifactTamperError(ValueError):
    """The declared self-key-removed hash does not match the payload."""


@dataclass(frozen=True, slots=True)
class OrderedCandidateEmissionArtifact:
    artifact_schema_version: str
    emission: OrderedCandidateEmission
    payload_sha256: str

    def __post_init__(self) -> None:
        if (
            self.artifact_schema_version
            != ORDERED_CANDIDATE_EMISSION_ARTIFACT_SCHEMA_VERSION
        ):
            raise ValueError(
                "artifact_schema_version must be exactly "
                f"{ORDERED_CANDIDATE_EMISSION_ARTIFACT_SCHEMA_VERSION}"
            )
        if type(self.emission) is not OrderedCandidateEmission:
            raise ValueError("emission must be an OrderedCandidateEmission")
        if type(self.payload_sha256) is not str or _SHA256.fullmatch(
            self.payload_sha256
        ) is None:
            raise ValueError("payload_sha256 must be an exact lowercase SHA-256")


def _emission_content_dict(emission: OrderedCandidateEmission) -> dict[str, Any]:
    auxiliary: dict[str, Any] = {
        "availability": emission.auxiliary_operand_availability.value,
        "kind": emission.auxiliary_operand_kind.value,
    }
    if emission.auxiliary_operand_availability is AuxiliaryOperandAvailability.PRESENT:
        assert emission.auxiliary_operand_value is not None
        auxiliary["value"] = emission.auxiliary_operand_value
    return {
        "auxiliary_operand": auxiliary,
        "emitted_main_numbers": list(emission.emitted_main_numbers),
        "history_cutoff": emission.history_cutoff,
        "lottery_type": emission.lottery_type.value,
        "replicate": emission.replicate,
        "schema_version": emission.schema_version,
        "strategy_id": emission.strategy_id,
        "strategy_version": emission.strategy_version,
        "target_draw": emission.target_draw,
    }


def _artifact_content_dict(
    *,
    artifact_schema_version: str,
    emission: OrderedCandidateEmission,
    payload_sha256: str,
) -> dict[str, Any]:
    return {
        "artifact_schema_version": artifact_schema_version,
        "emission": _emission_content_dict(emission),
        "payload_sha256": payload_sha256,
    }


def build_ordered_candidate_emission_artifact(
    emission: OrderedCandidateEmission,
) -> OrderedCandidateEmissionArtifact:
    content = _artifact_content_dict(
        artifact_schema_version=ORDERED_CANDIDATE_EMISSION_ARTIFACT_SCHEMA_VERSION,
        emission=emission,
        payload_sha256=_PLACEHOLDER_SHA256,
    )
    payload_sha256 = self_key_removed_sha256(content, "payload_sha256")
    return OrderedCandidateEmissionArtifact(
        artifact_schema_version=ORDERED_CANDIDATE_EMISSION_ARTIFACT_SCHEMA_VERSION,
        emission=emission,
        payload_sha256=payload_sha256,
    )


def recompute_ordered_candidate_emission_payload_sha256(
    artifact: OrderedCandidateEmissionArtifact,
) -> str:
    content = _artifact_content_dict(
        **{
            field.name: getattr(artifact, field.name)
            for field in dataclasses.fields(artifact)
        }
    )
    return self_key_removed_sha256(content, "payload_sha256")


def serialize_ordered_candidate_emission_artifact(
    artifact: OrderedCandidateEmissionArtifact,
) -> bytes:
    return canonical_bytes(
        _artifact_content_dict(
            artifact_schema_version=artifact.artifact_schema_version,
            emission=artifact.emission,
            payload_sha256=artifact.payload_sha256,
        )
    )


def _require_exact_keys(
    payload: dict[str, Any],
    required: set[str],
    location: str,
) -> None:
    missing = required - payload.keys()
    unknown = payload.keys() - required
    if missing or unknown:
        raise OrderedCandidateEmissionArtifactShapeError(
            f"{location} keys are not closed: "
            f"missing={sorted(missing)} unknown={sorted(unknown)}"
        )


def _emission_from_payload(payload: object) -> OrderedCandidateEmission:
    if not isinstance(payload, dict):
        raise OrderedCandidateEmissionArtifactShapeError(
            "emission must be a JSON object"
        )
    emission = cast(dict[str, Any], payload)
    _require_exact_keys(
        emission,
        {
            "auxiliary_operand",
            "emitted_main_numbers",
            "history_cutoff",
            "lottery_type",
            "replicate",
            "schema_version",
            "strategy_id",
            "strategy_version",
            "target_draw",
        },
        "emission",
    )

    raw_auxiliary = emission["auxiliary_operand"]
    if not isinstance(raw_auxiliary, dict):
        raise OrderedCandidateEmissionArtifactShapeError(
            "auxiliary_operand must be a JSON object"
        )
    auxiliary = cast(dict[str, Any], raw_auxiliary)
    availability = auxiliary.get("availability")
    auxiliary_keys = {"availability", "kind"}
    if availability == AuxiliaryOperandAvailability.PRESENT.value:
        auxiliary_keys.add("value")
    _require_exact_keys(auxiliary, auxiliary_keys, "auxiliary_operand")

    try:
        return OrderedCandidateEmission(
            schema_version=emission["schema_version"],
            lottery_type=LotteryType(emission["lottery_type"]),
            strategy_id=emission["strategy_id"],
            strategy_version=emission["strategy_version"],
            replicate=emission["replicate"],
            target_draw=emission["target_draw"],
            history_cutoff=emission["history_cutoff"],
            emitted_main_numbers=tuple(emission["emitted_main_numbers"]),
            auxiliary_operand_kind=AuxiliaryOperandKind(auxiliary["kind"]),
            auxiliary_operand_availability=AuxiliaryOperandAvailability(
                auxiliary["availability"]
            ),
            auxiliary_operand_value=auxiliary.get("value"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OrderedCandidateEmissionArtifactShapeError(
            "emission contains malformed enum or field values"
        ) from exc


def deserialize_ordered_candidate_emission_artifact(
    data: bytes,
) -> OrderedCandidateEmissionArtifact:
    raw_parsed = loads_canonical(data)
    if not isinstance(raw_parsed, dict):
        raise OrderedCandidateEmissionArtifactShapeError(
            "artifact payload must be a JSON object"
        )
    parsed = cast(dict[str, Any], raw_parsed)
    _require_exact_keys(
        parsed,
        {"artifact_schema_version", "emission", "payload_sha256"},
        "artifact",
    )

    declared_sha256 = parsed["payload_sha256"]
    if type(declared_sha256) is not str or _SHA256.fullmatch(
        declared_sha256
    ) is None:
        raise OrderedCandidateEmissionArtifactShapeError(
            "payload_sha256 must be an exact lowercase SHA-256"
        )
    recomputed_sha256 = self_key_removed_sha256(parsed, "payload_sha256")
    if recomputed_sha256 != declared_sha256:
        raise OrderedCandidateEmissionArtifactTamperError(
            "payload_sha256 does not match the canonical payload"
        )
    if canonical_bytes(parsed) != data:
        raise OrderedCandidateEmissionArtifactShapeError(
            "artifact bytes are not the exact LCJ-1 canonical serialization"
        )

    emission = _emission_from_payload(parsed["emission"])
    try:
        return OrderedCandidateEmissionArtifact(
            artifact_schema_version=parsed["artifact_schema_version"],
            emission=emission,
            payload_sha256=declared_sha256,
        )
    except (TypeError, ValueError) as exc:
        raise OrderedCandidateEmissionArtifactShapeError(
            "artifact contains malformed field values"
        ) from exc


__all__ = [
    "ORDERED_CANDIDATE_EMISSION_ARTIFACT_SCHEMA_VERSION",
    "OrderedCandidateEmissionArtifact",
    "OrderedCandidateEmissionArtifactShapeError",
    "OrderedCandidateEmissionArtifactTamperError",
    "build_ordered_candidate_emission_artifact",
    "deserialize_ordered_candidate_emission_artifact",
    "recompute_ordered_candidate_emission_payload_sha256",
    "serialize_ordered_candidate_emission_artifact",
]
