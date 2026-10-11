"""Exact coverage, arithmetic, provenance, no-solver and mutant checks."""

from __future__ import annotations

import itertools
import json
from collections.abc import Callable, Iterator
from copy import deepcopy
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_state_14122976_top16_exact_certificate_r1 as cert


def stored_result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(cert.RESULT_PATH.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return stored_result()


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("forbidden census/solver/tail/portfolio dispatch")


@pytest.mark.parametrize("tickets", [0, 1, 2, 4])
@pytest.mark.parametrize(("lower", "upper", "cutoff"), [(0, 12, 9), (3, 7, 8), (4, 4, 20)])
def test_both_enumerators_against_independent_small_exhaustive_oracle(
    tickets: int, lower: int, upper: int, cutoff: int
) -> None:
    weights, losses = (0, 2, 3, 7), (0, 3, 2, 8)
    expected = {
        v
        for v in itertools.product(range(tickets + 1), repeat=4)
        if sum(v) == tickets
        and lower <= sum(a * b for a, b in zip(v, weights, strict=True)) <= upper
        and sum(a * b for a, b in zip(v, losses, strict=True)) <= cutoff
    }
    for enumerate_vectors in (cert.ascending_vectors, cert.descending_vectors):
        actual = tuple(enumerate_vectors(weights, losses, tickets, lower, upper, cutoff))
        assert len(actual) == len(set(actual))
        assert set(actual) == expected


def test_invalid_enumeration_domain_fails_closed() -> None:
    for generator in (cert.ascending_vectors, cert.descending_vectors):
        with pytest.raises(ValueError, match="invalid bounded"):
            tuple(generator((0, 2), (0, 0), 18, 1, 2, 3))


def test_exact_region_digest_and_all_seven_compressed_pairs() -> None:
    members = cert.project_region()
    assert len(members) == 214
    assert sum(len(m.vectors) for m in members) == 221
    assert cert.digest(tuple((m.state.witness_counts, m.raw_bound) for m in members)) == (
        "785409687cbaca559e536cf63ff87fb0e5f972796025ef03743e13ba5a88555e"
    )
    pairs = [m for m in members if len(m.vectors) == 2]
    assert len(pairs) == 7
    expected_pairs = [
        ([[0, 13], [1, 1], [4, 2], [6, 1], [25, 1]], [[0, 13], [1, 2], [4, 1], [9, 1], [25, 1]]),
        ([[0, 15], [4, 1], [17, 1], [25, 1]], [[0, 15], [1, 1], [19, 1], [25, 1]]),
        ([[0, 13], [1, 1], [4, 2], [5, 1], [21, 1]], [[0, 13], [1, 2], [4, 1], [5, 1], [23, 1]]),
        ([[0, 13], [1, 1], [4, 2], [16, 1], [21, 1]], [[0, 13], [1, 2], [4, 1], [16, 1], [23, 1]]),
        ([[0, 14], [1, 1], [6, 1], [8, 1], [25, 1]], [[0, 14], [2, 1], [4, 1], [9, 1], [25, 1]]),
        ([[0, 15], [6, 1], [19, 1], [20, 1]], [[0, 15], [9, 1], [17, 1], [20, 1]]),
        ([[0, 16], [6, 1], [23, 1]], [[0, 16], [9, 1], [21, 1]]),
    ]
    actual = {frozenset(m.vectors) for m in pairs}
    expected = {frozenset(cert.dense(v) for v in pair) for pair in expected_pairs}
    assert actual == expected
    for m in members:
        assert m.state.witness_counts == min(m.vectors)
        assert m.state.represented_vector_count == len(m.vectors)
        assert cert.S3_LOWER < m.state.joint_s3 <= cert.S3_UPPER
        assert m.state.joint_s2 >= cert.S2_MIN
        assert m.state.local_loss <= 6_695_798
        assert all(cert.signature(cert.make_state(v)) == cert.signature(m.state) for v in m.vectors)


def test_all_sixteen_members_and_refined_bounds(result: dict[str, Any]) -> None:
    members = cert.project_region()
    band = cert.top_band(members)
    expected = {
        cert.dense([[0, 9], [1, i], [4, 7 - i], [special, 1], [25, 1]])
        for special in (5, 16)
        for i in range(8)
    }
    assert {m.state.witness_counts for m in band} == expected
    assert [m.raw_bound for m in band] == [355_640_810] * 8 + [355_641_258] * 8
    expected_bounds = [
        353_298_821,
        353_296_954,
        353_295_710,
        353_295_088,
        353_295_088,
        353_295_710,
        353_296_954,
        353_298_821,
        353_458_878,
        353_457_012,
        353_455_767,
        353_455_145,
        353_455_145,
        353_455_767,
        353_457_012,
        353_458_878,
    ]
    records = result["NEW_MEMBER_CERTIFICATES"]
    assert [r["member_new_bound"] for r in records] == expected_bounds
    for m, r in zip(band, records, strict=True):
        cert.check_certificate(r, m)
        assert r["prior_applied_correction"] == 2_870_000
        assert r["member_certified_correction"] == r["minimum_vector_rational_correction"]
        assert r["member_drop"] == r["member_certified_correction"] - 2_870_000


def test_complete_maximum_and_198_unchanged_members(result: dict[str, Any]) -> None:
    members = cert.project_region()
    records = result["NEW_MEMBER_CERTIFICATES"]
    bounds = cert.recompute_state(members, records)
    top_keys = {m.state.witness_counts for m in cert.top_band(members)}
    remainder = [m for m in members if m.state.witness_counts not in top_keys]
    assert len(remainder) == 198
    assert all(bounds[m.state.witness_counts] == m.raw_bound for m in remainder)
    assert max(m.raw_bound for m in remainder) == max(bounds.values()) == 355_510_148
    assert result["TOP_BAND_MAX"] == 353_458_878
    assert result["STATE_DROP"] == 131_110
    assert cert.r24.carried_member_certificates(cert.STATE_ID) == ()
    assert result["CARRIED_MEMBERS_PRESERVED"] is True
    assert result["CARRIED_CERTIFIED_MEMBER_COUNT"] == 0
    assert len(result["COMPLETE_REGION_MEMBERS"]) == 214


def test_support_identity_and_compressed_minimum_correction(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert len(result["TWO_VECTOR_MEMBERS"]) == 7
    for row in result["TWO_VECTOR_MEMBERS"]:
        assert len(row["support_witnesses"]) == 2
        for vector, witness in zip(
            row["represented_vectors"], row["support_witnesses"], strict=True
        ):
            assert witness["counts"] == vector
            assert witness == cert.normalized(cert.support_record(cert.dense(vector)))
    member = next(m for m in cert.project_region() if len(m.vectors) == 2)
    record = cert.normalized(cert.certify_member(member))
    cert.check_certificate(record, member)
    assert record["minimum_vector_rational_correction"] == min(
        r["correction_lower_bound"] for r in record["vector_certificates"]
    )
    original = cert.r14.moment_certificate
    baseline = int(original(member.vectors[0])["correction_lower_bound"])

    def asymmetric(vector: cert.CountVector) -> dict[str, Any]:
        moment = original(vector)
        return moment | {
            "correction_lower_bound": baseline + (1_000 if vector == member.vectors[1] else 0)
        }

    monkeypatch.setattr(cert.r14, "moment_certificate", asymmetric)
    changed = cert.certify_member(member)
    assert changed["minimum_vector_rational_correction"] == baseline
    assert changed["member_certified_correction"] == max(
        member.state.applied_residual_union_penalty, baseline
    )
    monkeypatch.undo()
    cert.check_certificate(record, member)


def test_missing_witness_does_not_delete_a_raw_member(monkeypatch: pytest.MonkeyPatch) -> None:
    # No support-construction call is needed to project or retain the raw region.
    monkeypatch.setattr(cert.r12, "construct_support_witness", forbidden)
    cert.project_region.cache_clear()
    assert len(cert.project_region()) == 214
    member = cert.top_band(cert.project_region())[0]

    def no_support(_: cert.CountVector) -> None:
        return None

    monkeypatch.setattr(cert.r12, "construct_support_witness", no_support)
    with pytest.raises(AssertionError, match="support witness"):
        cert.certify_member(member)


def test_base_family_authority_and_source_provenance(result: dict[str, Any]) -> None:
    assert cert.verify_sources() == result["UPSTREAM_FINGERPRINTS_SHA256"]
    assert result["UPSTREAM_FINGERPRINTS_SHA256"][cert.R7_RELATIVE] == (
        "463f0e1d577e5e175822d7fc52b1237fd7eb750fbd8ac654280993c160051f02"
    )
    assert result["BASE_STATE_TERMS"] == cert.stored(cert.BASE_RELATIVE)["FINAL_STATE_TERMS"]
    assert result["R3_FAMILY_BOUND_FROM_BASE"] == 355_722_668
    assert result["NEXT_COMPETING_OWNER"] == {
        "stable_id": "state:s2-12692531-s3-681744",
        "bound": 355_722_668,
    }
    assert result["PACKET_COMPETING_STATE_IDS"] == ["state:s2-13548976-s3-951748"]
    assert result["R3_CLAIM"] == "NONE_STATE_LOCAL_CERTIFICATE_ONLY"


def test_zero_solver_scoped_build_and_byte_reproduction(
    monkeypatch: pytest.MonkeyPatch, result: dict[str, Any]
) -> None:
    for module, name in (
        (cert.r7, "joint_residual_census"),
        (cert.r6, "iter_type_count_vectors"),
        (cert.r6, "candidate_type_count_vectors"),
        (cert.r14, "owner_region"),
        (cert.r14, "s4_child"),
        (cert.r8, "solver_runtime_preflight"),
        (cert.r24, "pinned_r7_census"),
        (cert.r24, "state_region"),
        (cert.r24.r22, "pinned_r7_census"),
        (cert.r24.r22, "state_region"),
        (cert.r24, "run_chase"),
        (cert.r24, "advance_tail"),
        (cert.r24.r13, "classify_vector"),
        (cert.r24.r16, "iter_interval_vectors"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    cert.project_region.cache_clear()
    rebuilt = cert.build_result()
    assert cert.encode(rebuilt) == cert.RESULT_PATH.read_text(encoding="utf-8")
    assert rebuilt == result
    assert cert.verify_result(rebuilt) == {
        "status": "PASS",
        "certified_members": 16,
        "state_bound": 355_510_148,
    }


@pytest.mark.parametrize("which", ["ascending_vectors", "descending_vectors", "both"])
def test_projection_completeness_mutants_killed(
    monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    def omit(
        original: Callable[..., Iterator[cert.CountVector]],
    ) -> Callable[..., Iterator[cert.CountVector]]:
        def mutated(*args: Any) -> Iterator[cert.CountVector]:
            return iter(tuple(original(*args))[:-1])

        return mutated

    targets = ("ascending_vectors", "descending_vectors") if which == "both" else (which,)
    for name in targets:
        monkeypatch.setattr(cert, name, omit(getattr(cert, name)))
    cert.project_region.cache_clear()
    try:
        with pytest.raises(AssertionError, match="completeness"):
            cert.project_region()
    finally:
        monkeypatch.undo()
        cert.project_region.cache_clear()
    assert len(cert.project_region()) == 214


def mutate_result(result: dict[str, Any], mutation: str) -> None:
    row = result["NEW_MEMBER_CERTIFICATES"][0]
    if mutation == "top_band_omission":
        del result["NEW_MEMBER_CERTIFICATES"][-1]
    elif mutation == "duplicate_member":
        result["NEW_MEMBER_CERTIFICATES"].append(deepcopy(row))
    elif mutation == "double_credit":
        applied = row["prior_applied_correction"]
        row["member_certified_correction"] += applied
        row["member_new_bound"] -= applied
        row["member_drop"] += applied
    elif mutation == "wrong_max":
        result["FINAL_CERTIFIED_STATE_BOUND"] = result["TOP_BAND_MAX"]
    elif mutation == "support_collision":
        support = row["support_witnesses"][0]["support_witness"]
        support[1] = list(support[0])
    elif mutation == "moment_inflation":
        row["vector_certificates"][0]["residual_s2_lower_bound"] += 9
        row["vector_certificates"][0]["correction_lower_bound"] += 1
    elif mutation == "compression_omission":
        del result["TWO_VECTOR_MEMBERS"][0]["represented_vectors"][-1]
    elif mutation == "region_omission":
        del result["COMPLETE_REGION_MEMBERS"][-1]
    elif mutation == "remainder_credit":
        result["COMPLETE_REGION_MEMBERS"][-1]["final_bound"] -= 1
    elif mutation == "wrong_family_claim":
        result["R3_FAMILY_BOUND_FROM_BASE"] = 355_637_030
    elif mutation == "wrong_source":
        result["UPSTREAM_FINGERPRINTS_SHA256"][cert.R7_RELATIVE] = "0" * 64
    else:
        raise AssertionError(f"unknown mutant {mutation}")


@pytest.mark.parametrize(
    "mutation",
    [
        "top_band_omission",
        "duplicate_member",
        "double_credit",
        "wrong_max",
        "support_collision",
        "moment_inflation",
        "compression_omission",
        "region_omission",
        "remainder_credit",
        "wrong_family_claim",
        "wrong_source",
    ],
)
def test_result_mutants_killed(result: dict[str, Any], mutation: str) -> None:
    mutated = deepcopy(result)
    mutate_result(mutated, mutation)
    with pytest.raises(AssertionError):
        cert.verify_result(mutated)
    # A controlled fixture mutation cannot leak into the restored candidate.
    assert result == stored_result()


def test_source_fingerprint_mutant_killed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cert, "UPSTREAM_SHA256", cert.UPSTREAM_SHA256 | {cert.R7_RELATIVE: "0" * 64}
    )
    with pytest.raises(AssertionError, match="immutable source fingerprint"):
        cert.verify_sources()


def test_final_restored_candidate_replays(result: dict[str, Any]) -> None:
    assert cert.verify_result(result)["status"] == "PASS"
