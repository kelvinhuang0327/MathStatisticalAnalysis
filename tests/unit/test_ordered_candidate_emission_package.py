"""Manifest, checksum, and deterministic-byte tests for P336 packages."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateMaterializationAttempt,
    OrderedCandidateMaterializationStatus,
    attempt_from_emission,
)
from lottolab.evidence.canonical_json import loads_canonical, sha256_hex
from lottolab.evidence.ordered_candidate_emission_artifact import (
    build_ordered_candidate_emission_artifact,
    serialize_ordered_candidate_emission_artifact,
)
from lottolab.evidence.ordered_candidate_emission_package import (
    OrderedCandidateEmissionFile,
    OrderedCandidateEmissionPackageError,
    build_ordered_candidate_emission_package,
    sha256sums_bytes,
    verify_ordered_candidate_emission_package,
)


def _ok() -> tuple[
    OrderedCandidateMaterializationAttempt,
    OrderedCandidateEmissionFile,
]:
    emission = OrderedCandidateEmission(
        schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="fixture_strategy",
        strategy_version="v1",
        replicate=1,
        target_draw="101",
        history_cutoff="100",
        emitted_main_numbers=(6, 1, 5, 2, 4, 3),
        auxiliary_operand_kind=AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
        auxiliary_operand_availability=(
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING
        ),
        auxiliary_operand_value=None,
    )
    artifact = build_ordered_candidate_emission_artifact(emission)
    data = serialize_ordered_candidate_emission_artifact(artifact)
    file_hash = sha256_hex(data)
    attempt = attempt_from_emission(
        ordinal=0,
        target_ordinal=0,
        strategy_ordinal=0,
        emission=emission,
        emission_payload_sha256=artifact.payload_sha256,
        emission_file_sha256=file_hash,
    )
    assert attempt.emission_relative_path is not None
    return (
        attempt,
        OrderedCandidateEmissionFile(
            relative_path=attempt.emission_relative_path,
            data=data,
            payload_sha256=artifact.payload_sha256,
            file_sha256=file_hash,
        ),
    )


def _package():
    attempt, emission_file = _ok()
    return build_ordered_candidate_emission_package(
        dataset_id="dataset",
        dataset_version="v1",
        source_snapshot_sha256_value="a" * 64,
        target_draws=("101",),
        strategy_ids=("fixture_strategy",),
        minimum_history_draws=1,
        maximum_history_draws=100,
        replicate=1,
        attempts=(attempt,),
        emission_files=(emission_file,),
    )


def test_identical_materialized_inputs_produce_byte_identical_package_files() -> None:
    first = _package()
    second = _package()

    assert first.manifest_bytes == second.manifest_bytes
    assert first.emission_files == second.emission_files
    assert sha256sums_bytes(first) == sha256sums_bytes(second)


def test_manifest_is_closed_has_no_null_and_counts_match_complete_ledger() -> None:
    package = _package()

    manifest = verify_ordered_candidate_emission_package(package)

    assert b"null" not in package.manifest_bytes
    assert manifest["attempt_count"] == 1
    assert manifest["ok_attempt_count"] == 1
    assert manifest["status_counts"] == {
        "insufficient_history": 0,
        "invalid_output": 0,
        "ok": 1,
        "rejected": 0,
        "replay_error": 0,
        "storage_error": 0,
        "strategy_unavailable": 0,
        "target_not_found": 0,
    }
    assert manifest["attempts"][0]["status"] == "OK"
    assert manifest["attempts"][0]["emission_file_sha256"] == (
        package.emission_files[0].file_sha256
    )
    assert manifest["attempts"][0]["emission_payload_sha256"] == (
        package.emission_files[0].payload_sha256
    )
    for forbidden in ("repository", "commit_oid", "publication_path"):
        assert forbidden.encode() not in package.manifest_bytes


def test_sha256sums_covers_manifest_and_all_only_emissions_in_utf8_path_order() -> None:
    package = _package()

    lines = sha256sums_bytes(package).decode("utf-8").splitlines()

    expected_paths = sorted(
        ["manifest.json", package.emission_files[0].relative_path],
        key=lambda value: value.encode("utf-8"),
    )
    assert [line.split("  ", maxsplit=1)[1] for line in lines] == expected_paths
    assert all(len(line.split("  ", maxsplit=1)[0]) == 64 for line in lines)
    assert all("SHA256SUMS" not in line for line in lines)


def test_non_ok_attempt_has_no_artifact_keys_but_remains_in_manifest() -> None:
    attempt = OrderedCandidateMaterializationAttempt(
        ordinal=0,
        target_ordinal=0,
        strategy_ordinal=0,
        target_draw="101",
        strategy_id="fixture_strategy",
        status=OrderedCandidateMaterializationStatus.REJECTED,
        reason_code="REJECTED_BY_STRATEGY",
        history_cutoff="100",
    )
    package = build_ordered_candidate_emission_package(
        dataset_id="dataset",
        dataset_version="v1",
        source_snapshot_sha256_value="a" * 64,
        target_draws=("101",),
        strategy_ids=("fixture_strategy",),
        minimum_history_draws=1,
        maximum_history_draws=100,
        replicate=1,
        attempts=(attempt,),
        emission_files=(),
    )

    manifest_value: object = loads_canonical(package.manifest_bytes)
    assert isinstance(manifest_value, dict)
    manifest = cast(dict[str, object], manifest_value)
    attempts_value = manifest["attempts"]
    assert isinstance(attempts_value, list)
    attempts = cast(list[object], attempts_value)
    ledger_value = attempts[0]
    assert isinstance(ledger_value, dict)
    ledger = cast(dict[str, object], ledger_value)
    assert ledger["status"] == "REJECTED"
    assert all(
        key not in ledger
        for key in (
            "emission_relative_path",
            "emission_file_sha256",
            "emission_payload_sha256",
        )
    )


def test_attempt_hash_tamper_is_rejected_even_when_emission_bytes_are_unchanged() -> None:
    package = _package()
    tampered_attempt = replace(
        package.attempts[0],
        emission_file_sha256="f" * 64,
    )

    with pytest.raises(OrderedCandidateEmissionPackageError):
        verify_ordered_candidate_emission_package(
            replace(package, attempts=(tampered_attempt,))
        )
