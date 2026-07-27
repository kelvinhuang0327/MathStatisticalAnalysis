"""Canonical-byte and tamper tests for ordered-emission artifacts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.evidence.canonical_json import (
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
)
from lottolab.evidence.ordered_candidate_emission_artifact import (
    OrderedCandidateEmissionArtifactShapeError,
    OrderedCandidateEmissionArtifactTamperError,
    build_ordered_candidate_emission_artifact,
    deserialize_ordered_candidate_emission_artifact,
    recompute_ordered_candidate_emission_payload_sha256,
    serialize_ordered_candidate_emission_artifact,
)


def _emission(
    *,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
    kind: AuxiliaryOperandKind = AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
    availability: AuxiliaryOperandAvailability = (
        AuxiliaryOperandAvailability.EXPLICITLY_MISSING
    ),
    value: int | None = None,
) -> OrderedCandidateEmission:
    return OrderedCandidateEmission(
        schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
        lottery_type=lottery_type,
        strategy_id="fixture_strategy",
        strategy_version="v1",
        replicate=1,
        target_draw="101",
        history_cutoff="100",
        emitted_main_numbers=(9, 4, 9, 2),
        auxiliary_operand_kind=kind,
        auxiliary_operand_availability=availability,
        auxiliary_operand_value=value,
    )


def _artifact_bytes() -> bytes:
    return serialize_ordered_candidate_emission_artifact(
        build_ordered_candidate_emission_artifact(_emission())
    )


def _rehashed_mutation(
    mutate: Callable[[dict[str, Any]], None],
) -> bytes:
    parsed = cast(dict[str, Any], loads_canonical(_artifact_bytes()))
    mutate(parsed)
    parsed["payload_sha256"] = self_key_removed_sha256(
        parsed,
        "payload_sha256",
    )
    return canonical_bytes(parsed)


def test_same_materialized_emission_produces_identical_canonical_bytes() -> None:
    first = _artifact_bytes()
    second = _artifact_bytes()

    assert first == second
    assert b"null" not in first
    assert b'"emitted_main_numbers":[9,4,9,2]' in first


def test_declared_payload_hash_matches_self_key_removed_recomputation() -> None:
    artifact = build_ordered_candidate_emission_artifact(_emission())

    assert (
        recompute_ordered_candidate_emission_payload_sha256(artifact)
        == artifact.payload_sha256
    )


def test_serialize_parse_serialize_is_byte_identical() -> None:
    data = _artifact_bytes()
    restored = deserialize_ordered_candidate_emission_artifact(data)

    assert restored.emission == _emission()
    assert serialize_ordered_candidate_emission_artifact(restored) == data


def test_present_auxiliary_value_round_trips_in_closed_form() -> None:
    emission = _emission(
        lottery_type=LotteryType.POWER_LOTTO,
        kind=AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
        availability=AuxiliaryOperandAvailability.PRESENT,
        value=8,
    )
    data = serialize_ordered_candidate_emission_artifact(
        build_ordered_candidate_emission_artifact(emission)
    )

    assert b'"value":8' in data
    assert deserialize_ordered_candidate_emission_artifact(data).emission == emission


def test_semantic_one_byte_mutation_fails_hash_verification() -> None:
    data = _artifact_bytes()
    tampered = data.replace(b'"replicate":1', b'"replicate":2')

    assert len(tampered) == len(data)
    assert tampered != data
    with pytest.raises(OrderedCandidateEmissionArtifactTamperError):
        deserialize_ordered_candidate_emission_artifact(tampered)


def test_noncanonical_one_byte_mutation_fails_closed() -> None:
    with pytest.raises(OrderedCandidateEmissionArtifactShapeError):
        deserialize_ordered_candidate_emission_artifact(_artifact_bytes() + b"\n")


def test_unknown_top_level_key_is_rejected_even_with_a_valid_recomputed_hash() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        payload["repository"] = "forbidden/self-reference"

    with pytest.raises(OrderedCandidateEmissionArtifactShapeError):
        deserialize_ordered_candidate_emission_artifact(
            _rehashed_mutation(mutate)
        )


def test_missing_emission_key_is_rejected_even_with_a_valid_recomputed_hash() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        emission = cast(dict[str, Any], payload["emission"])
        del emission["target_draw"]

    with pytest.raises(OrderedCandidateEmissionArtifactShapeError):
        deserialize_ordered_candidate_emission_artifact(
            _rehashed_mutation(mutate)
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("lottery_type", "UNKNOWN"),
        ("schema_version", "2.0.0"),
        ("replicate", 0),
        ("target_draw", "not-a-draw"),
    ),
)
def test_malformed_emission_values_are_rejected_after_hash_verification(
    field: str,
    value: object,
) -> None:
    def mutate(payload: dict[str, Any]) -> None:
        emission = cast(dict[str, Any], payload["emission"])
        emission[field] = value

    with pytest.raises(OrderedCandidateEmissionArtifactShapeError):
        deserialize_ordered_candidate_emission_artifact(
            _rehashed_mutation(mutate)
        )


def test_malformed_auxiliary_enum_is_rejected_after_hash_verification() -> None:
    def mutate(payload: dict[str, Any]) -> None:
        emission = cast(dict[str, Any], payload["emission"])
        auxiliary = cast(dict[str, Any], emission["auxiliary_operand"])
        auxiliary["availability"] = "UNKNOWN"

    with pytest.raises(OrderedCandidateEmissionArtifactShapeError):
        deserialize_ordered_candidate_emission_artifact(
            _rehashed_mutation(mutate)
        )


def test_missing_auxiliary_value_for_present_state_is_rejected() -> None:
    present = _emission(
        availability=AuxiliaryOperandAvailability.PRESENT,
        value=7,
    )
    data = serialize_ordered_candidate_emission_artifact(
        build_ordered_candidate_emission_artifact(present)
    )

    def mutate(payload: dict[str, Any]) -> None:
        emission = cast(dict[str, Any], payload["emission"])
        auxiliary = cast(dict[str, Any], emission["auxiliary_operand"])
        del auxiliary["value"]

    parsed = cast(dict[str, Any], loads_canonical(data))
    mutate(parsed)
    parsed["payload_sha256"] = self_key_removed_sha256(
        parsed,
        "payload_sha256",
    )
    with pytest.raises(OrderedCandidateEmissionArtifactShapeError):
        deserialize_ordered_candidate_emission_artifact(canonical_bytes(parsed))


def test_artifact_never_embeds_external_or_self_referential_locator_identity() -> None:
    data = _artifact_bytes()

    for forbidden_key in (
        b'"repository"',
        b'"commit_oid"',
        b'"path"',
        b'"artifact_sha256"',
        b'"final_serialized_bytes_sha256"',
    ):
        assert forbidden_key not in data
