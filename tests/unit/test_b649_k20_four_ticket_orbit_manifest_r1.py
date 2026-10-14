from __future__ import annotations

import copy
import itertools
from dataclasses import replace

import pytest

from lottolab.research import b649_k20_four_ticket_orbit_manifest_r1 as orbit_manifest


@pytest.fixture(scope="module")
def authority_inputs() -> orbit_manifest.AuthorityInputs:
    return orbit_manifest.load_authority_inputs()


@pytest.fixture(scope="module")
def manifest(
    authority_inputs: orbit_manifest.AuthorityInputs,
) -> dict[str, object]:
    return orbit_manifest.build_manifest(authority_inputs)


def test_frozen_identities_and_exact_orbit_partition(
    manifest: dict[str, object],
) -> None:
    source = manifest["source_identity"]
    assert source["source_commit"] == orbit_manifest.SOURCE_COMMIT
    assert source["source_tree"] == orbit_manifest.SOURCE_TREE
    assert source["predicate"]["sha256"] == orbit_manifest.PREDICATE_SHA256
    assert source["driver"]["sha256"] == orbit_manifest.DRIVER_SHA256
    assert source["evaluator"]["sha256"] == orbit_manifest.EVALUATOR_SHA256
    assert source["historical_journal"]["sha256"] == orbit_manifest.JOURNAL_SHA256

    group = manifest["group_action"]["automorphisms"]
    assert manifest["group_action"]["automorphism_count"] == 288
    assert len(group) == 288
    orbits = manifest["orbits"]
    assert len(orbits) == 670
    members = [tuple(member) for row in orbits for member in row["members"]]
    assert len(members) == 4_845
    assert len(set(members)) == 4_845
    assert set(members) == set(itertools.combinations(range(20), 4))

    elements = [
        orbit_manifest.Automorphism(tuple(item["slots"]), tuple(item["numbers"]))
        for item in group
    ]
    for row in orbits:
        representative = tuple(row["representative"])
        expected_members = sorted(
            {tuple(sorted(element.slots[index] for index in representative)) for element in elements}
        )
        assert row["members"] == [list(member) for member in expected_members]
        assert tuple(row["representative"]) == expected_members[0]


def test_journal_coverage_is_distinct_from_direct_execution(
    manifest: dict[str, object],
) -> None:
    coverage = manifest["coverage"]
    execution = manifest["execution"]
    assert coverage["historically_covered_orbits"] == 240
    assert coverage["unvisited_orbits"] == 430
    assert coverage["remaining_raw_attempts"] == 3_343_680
    assert coverage["uncovered_mixed_side_orbits"] == 308
    assert execution["new_scientific_execution"] == "NOT_RUN"
    assert execution["directly_scored_quadruple_count"] == 623
    assert execution["historically_executed_raw_attempts"] == 4_844_448
    assert execution["mathematical_coverage_does_not_imply_each_member_was_scored"] is True

    orbits = manifest["orbits"]
    assert sum(len(row["journal_record_indices"]) for row in orbits) == 623
    covered = [row for row in orbits if row["mathematical_coverage"] == "HISTORICALLY_COVERED_BY_SYMMETRY"]
    assert len(covered) == 240
    unvisited = [row for row in orbits if row["mathematical_coverage"] == "UNVISITED"]
    assert len(unvisited) == 430
    assert all(not row["journal_record_indices"] for row in unvisited)
    assert all(
        set(row["directly_scored_member_indices"]).issubset(set(row["member_indices"]))
        for row in orbits
    )
    assert any(
        len(row["directly_scored_member_indices"]) < len(row["member_indices"])
        for row in covered
    )


def test_remaining_representatives_match_frozen_digest(
    manifest: dict[str, object],
) -> None:
    remaining = manifest["remaining_representatives"]
    assert len(remaining) == 430
    assert all(set(item) == {"index", "quadruple"} for item in remaining)
    assert [item["index"] for item in remaining] == sorted(item["index"] for item in remaining)
    tuples = [item["quadruple"] for item in remaining]
    assert manifest["remaining_representative_tuple_sha256"] == (
        orbit_manifest.EXPECTED_REMAINING_TUPLE_SHA256
    )
    assert orbit_manifest._representative_tuple_digest(tuples) == (
        orbit_manifest.EXPECTED_REMAINING_TUPLE_SHA256
    )


@pytest.mark.parametrize("field", ["predicate", "driver", "evaluator", "journal", "baseline_artifact"])
def test_authority_byte_corruption_fails_closed(
    authority_inputs: orbit_manifest.AuthorityInputs,
    field: str,
) -> None:
    corrupted = replace(authority_inputs, **{field: getattr(authority_inputs, field) + b"x"})
    with pytest.raises(orbit_manifest.ManifestError, match="SHA-256 differs"):
        orbit_manifest.build_manifest(corrupted)


def test_corrupted_representative_mapping_is_detected_after_rehash(
    authority_inputs: orbit_manifest.AuthorityInputs,
    manifest: dict[str, object],
) -> None:
    corrupted = copy.deepcopy(manifest)
    representative = corrupted["orbits"][0]["representative"]
    representative[-1] = (representative[-1] + 1) % 20
    unsigned = {
        key: value
        for key, value in corrupted.items()
        if key != "manifest_content_sha256"
    }
    corrupted["manifest_content_sha256"] = orbit_manifest._sha256(
        orbit_manifest._canonical_json_bytes(unsigned)
    )
    with pytest.raises(
        orbit_manifest.ManifestError,
        match="deterministic authority reconstruction",
    ):
        orbit_manifest.verify_manifest_object(corrupted, authority_inputs)


def test_frozen_driver_tie_policy_and_gain_threshold(
    manifest: dict[str, object],
) -> None:
    assert manifest["tie_policy"] == {
        "frozen_driver_sha256": orbit_manifest.DRIVER_SHA256,
        "incumbent_update_condition": "candidate_official_count > current_best_count",
        "equal_count_replaces_incumbent": False,
        "strict_gain_condition": "exact_official_count >= 313263889",
    }
    assert orbit_manifest.STRICT_GAIN_MINIMUM_COUNT == orbit_manifest.BASELINE_COUNT + 1
