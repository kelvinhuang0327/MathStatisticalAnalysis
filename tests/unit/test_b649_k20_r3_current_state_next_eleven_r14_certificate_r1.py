"""Exact eleven-member coverage, weakest compression, one correction, and full R3 replay."""

from __future__ import annotations

import copy
import math
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_current_state_next_eleven_r14_certificate_r1 as cert

EXPECTED = (
    ("[0,9][4,5][5,3][19,1]", 5_012_214),
    ("[0,9][4,5][5,3][17,1]", 5_017_736),
    ("[0,9][1,1][4,4][5,3][19,1]", 5_014_562),
    ("[0,9][1,1][4,4][5,3][17,1]", 5_017_876),
    ("[0,9][1,2][4,3][5,3][19,1]", 5_016_289),
    ("[0,9][1,2][4,3][5,3][17,1]", 5_017_394),
    ("[0,9][1,3][4,2][5,3][17,1]", 5_016_289),
    ("[0,9][1,4][4,1][5,3][19,1]", 5_017_876),
    ("[0,9][1,4][4,1][5,3][17,1]", 5_014_562),
    ("[0,9][1,5][5,3][19,1]", 5_017_736),
    ("[0,9][1,5][5,3][17,1]", 5_012_214),
)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_exact_cohort_and_all_twelve_vectors(result: dict[str, Any]) -> None:
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    members = cert.six.region_members()
    priors = cert.current_member_bounds(members)
    cohort = cert.next_eleven_members(members, priors)
    assert len(members) == result["REGION_COMPRESSED_MEMBER_COUNT"] == 1_427
    assert sum(m.represented_vector_count for m in members) == 1_543
    assert result["REGION_IDENTITY"] == cert.REGION_SHA256
    assert [cert.member_id(m.counts) for m in cohort] == [row[0] for row in EXPECTED]
    assert len(cohort) == result["NEXT_ELEVEN_MEMBER_COUNT"] == 11
    assert {priors[m.counts] for m in cohort} == {355_630_646}
    records = result["MEMBER_CERTIFICATES"]
    vectors = [cert.dense(v) for row in records for v in row["represented_vectors"]]
    assert len(vectors) == len(set(vectors)) == result["REPRESENTED_VECTOR_COUNT"] == 12
    double = [row for row in records if row["represented_vector_count"] == 2]
    assert len(double) == 1
    assert double[0]["member_id"] == "[0,9][1,2][4,3][5,3][17,1]"
    assert [cert.member_id(cert.dense(v)) for v in double[0]["represented_vectors"]] == [
        "[0,9][1,2][4,3][5,3][17,1]",
        "[0,9][1,3][4,2][5,3][19,1]",
    ]
    assert result["COVERAGE_STATUS"] == "PASS_11_EXACT_MEMBERS_12_DISTINCT_VECTORS"


def test_residual_event_identity_over_every_used_pair(result: dict[str, Any]) -> None:
    occupied = {
        pair
        for row in result["MEMBER_CERTIFICATES"]
        for vector in row["represented_vectors"]
        for pair in cert.six.occupied_type_pairs(cert.dense(vector))
    }
    table_api = "_pair_event_correction_table"
    for left, right in sorted(occupied):
        table = getattr(cert.r8, table_api)(left, right)
        assert table
        for a, b, c, d, residual, _s4 in table:
            assert cert.six.residual_pair_intersection(left, right, (a, b, c, d)) == residual
    assert result["RESIDUAL_EVENT_DEFINITION"] == "R_i = E_i \\ (E_A ∪ E_B)"  # noqa: RUF001


def test_exact_rounding_and_correction_replacement(result: dict[str, Any]) -> None:
    assert [
        (r["member_id"], r["member_certified_correction"]) for r in result["MEMBER_CERTIFICATES"]
    ] == list(EXPECTED)
    for record in result["MEMBER_CERTIFICATES"]:
        for row in record["vector_certificates"]:
            moment = cert.exact_residual_pair_moment(cert.dense(row["counts"]))
            floor = math.ceil(Fraction(moment, 9))
            assert moment == row["residual_pair_moment"]
            assert cert.ceiling_divide_by_9(moment) == floor == row["r14_correction"]
            if moment % 9:
                assert floor != moment // 9
            prior = max(row["r6_pair_correction"], row["forest_correction"])
            assert prior == row["prior_applied_correction"] == 2_870_000
            correction = cert.combine_corrections(
                row["r6_pair_correction"], row["forest_correction"], floor
            )
            assert correction == max(prior, floor) == row["combined_correction"]
            assert (
                cert.member_bound(row["uncorrected_anchor_bound"], correction)
                == row["vector_new_bound"]
            )
            assert record["member_raw_bound"] == row["uncorrected_anchor_bound"] - prior
            assert row["vector_new_bound"] != row["uncorrected_anchor_bound"] - prior - floor
            assert row["moment_certificate"]["multiplicity_cap"] == 18
            assert row["moment_certificate"]["multiplicity_dual"] == [1, 9]
            for m in range(19):
                assert Fraction(math.comb(m, 2), 9) <= max(0, m - 1)
    assert cert.ceiling_divide_by_9(9) == 1
    assert cert.ceiling_divide_by_9(10) == 2
    with pytest.raises(ValueError):
        cert.ceiling_divide_by_9(-1)


def test_weakest_compression_and_signature(result: dict[str, Any]) -> None:
    members = {m.counts: m for m in cert.six.region_members()}
    for record in result["MEMBER_CERTIFICATES"]:
        member = members[cert.dense(record["witness_counts"])]
        state = cert.catalog.rebuild_member(member)
        rows = record["vector_certificates"]
        assert record["member_new_bound"] == max(r["vector_new_bound"] for r in rows)
        assert record["minimum_vector_r14_correction"] == min(r["r14_correction"] for r in rows)
        for row in rows:
            vector_state = cert.catalog.rebuild_member(
                replace(member, counts=cert.dense(row["counts"]))
            )
            assert cert.compression_signature(vector_state) == cert.compression_signature(state)
    # The actual double member has equal floors; unequal inputs discriminate min from max.
    assert cert.compressed_correction((9, 12)) == 9
    assert cert.compressed_correction((12, 9)) == 9
    assert cert.compressed_correction((9, 9)) == 9
    with pytest.raises(ValueError):
        cert.compressed_correction(())
    with pytest.raises(ValueError):
        cert.compressed_correction((-1, 9))


def test_all_exact_support_witnesses(result: dict[str, Any]) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            counts = cert.dense(row["counts"])
            support = tuple(tuple(ticket) for ticket in row["support_witness"])
            assert len(support) == 18
            assert cert.r8.validate_support_assignment(counts, support)
            assert cert.digest(support) == row["support_sha256"]
            residual, s4 = cert.r8.witness_costs(counts, support)
            assert residual == row["support_residual_pair_moment"] >= row["residual_pair_moment"]
            assert (
                s4
                == row["support_s4_pair_moment"]
                >= row["moment_certificate"]["s4_pairwise_lower_bound"]
            )


def test_preserves_six_and_all_other_members(result: dict[str, Any]) -> None:
    original = cert.six_authority()
    assert result["ORIGINAL_SIX_CERTIFICATES"] == original["MEMBER_CERTIFICATES"]
    assert result["ORIGINAL_SIX_CERTIFICATES_PRESERVED"] is True
    old = {r["member_id"]: r for r in original["COMPLETE_REGION_MEMBERS"]}
    certified = {r["member_id"] for r in result["MEMBER_CERTIFICATES"]}
    rows = result["COMPLETE_REGION_MEMBERS"]
    assert len(rows) == len({r["member_id"] for r in rows}) == 1_427
    for row in rows:
        assert row["prior_bound"] == old[row["member_id"]]["final_bound"]
        assert row["raw_bound"] == old[row["member_id"]]["raw_bound"]
        if row["member_id"] not in certified:
            assert row["final_bound"] == row["prior_bound"]
    preserved = [r for r in rows if r["member_id"] not in certified]
    assert len(preserved) == result["PRESERVED_MEMBER_COUNT"] == 1_416
    assert max(r["final_bound"] for r in preserved) == result["PRESERVED_COHORT_MAX"] == 355_630_198
    assert result["CERTIFIED_MEMBER_MAX"] == 353_488_432
    assert result["FINAL_STATE_BOUND"] == max(r["final_bound"] for r in rows) == 355_630_198
    for row in result["MEMBER_CERTIFICATES"]:
        assert row["hunter_correction_applied"] is False
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_complete_r3_family_recomputation(result: dict[str, Any]) -> None:
    replay = cert.recompute_family(result["FINAL_STATE_BOUND"])
    assert replay["start"] == result["START_FAMILY_MAX_RECOMPUTATION"]
    assert replay["final"] == result["FINAL_FAMILY_MAX_RECOMPUTATION"]
    assert result["START_R3_FAMILY_UB"] == 355_630_646
    assert result["FINAL_R3_FAMILY_UB"] == replay["final"]["R3_BOUND"] == 355_630_198
    assert result["REMAINING_GAP"] == 42_366_310
    assert result["FINAL_R3_FAMILY_UB"] - result["CURRENT_INCUMBENT"] == result["REMAINING_GAP"]
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert {key for key in before if before[key] != after[key]} == {cert.TARGET_STATE_ID}
    assert after["state:s2-13169800-s3-789320"] == 355_628_469
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_MAX"] == 355_468_904
    assert result["CLASSIFIED_AGGREGATE"] == [
        {"stable_id": "carried-r12-other-levels", "bound": 355_468_904}
    ]
    assert result["CLASSIFIED_TERMS_SHA256"] == cert.six_authority()["CLASSIFIED_TERMS_SHA256"]
    assert result["FINAL_R3_FAMILY_UB"] == max(
        max(after.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"]
    )


def test_stored_result_and_full_replay(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_text() == cert.encode(result)
    assert cert.verify_result(result) == {"status": "PASS", "certificates": 11, "vectors": 12}


@pytest.mark.parametrize(
    "field",
    [
        "member_new_bound",
        "r14_correction",
        "residual_pair_moment",
        "prior_applied_correction",
        "combined_correction",
        "support_residual_pair_moment",
    ],
)
def test_rejects_vector_arithmetic_tampering(result: dict[str, Any], field: str) -> None:
    tampered = copy.deepcopy(result)
    if field == "member_new_bound":
        tampered["MEMBER_CERTIFICATES"][0][field] -= 1
    else:
        tampered["MEMBER_CERTIFICATES"][0]["vector_certificates"][0][field] += 1
    with pytest.raises(AssertionError, match="replay"):
        cert.verify_result(tampered)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_member",
        "duplicate_member",
        "missing_vector",
        "witness",
        "digest",
        "preserved_bound",
        "family",
        "tail",
        "six",
        "summary",
    ],
)
def test_rejects_coverage_witness_catalog_and_family_tampering(
    result: dict[str, Any], mutation: str
) -> None:
    bad = copy.deepcopy(result)
    first = bad["MEMBER_CERTIFICATES"][0]
    if mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(first))
    elif mutation == "missing_vector":
        double = next(r for r in bad["MEMBER_CERTIFICATES"] if r["represented_vector_count"] == 2)
        double["represented_vectors"].pop()
        double["vector_certificates"].pop()
    elif mutation == "witness":
        first["vector_certificates"][0]["support_witness"][0][0] = 99
    elif mutation == "digest":
        first["vector_certificates"][0]["support_sha256"] = "0" * 64
    elif mutation == "preserved_bound":
        next(
            r
            for r in bad["COMPLETE_REGION_MEMBERS"]
            if r["member_id"] not in {x[0] for x in EXPECTED}
        )["final_bound"] -= 1
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    elif mutation == "six":
        bad["ORIGINAL_SIX_CERTIFICATES"][0]["member_new_bound"] -= 1
    else:
        bad["CORRECTION_FLOORS"][0] += 1
    with pytest.raises(AssertionError, match=r"support witness|replay"):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "relative",
    [
        cert.six.RESULT_RELATIVE,
        "src/lottolab/research/b649_k20_r3_current_owner_six_member_r14_certificate_r1.py",
        "src/lottolab/research/b649_k20_r3_tail_state_owner_chase_r16.py",
        "src/lottolab/research/b649_k20_r3_exact_anchor_neighborhood_envelope_r6.py",
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py",
        "src/lottolab/research/b649_k20_r3_frontier_realizability_bound_r8.py",
        cert.catalog.R24_RESULT_RELATIVE,
    ],
)
def test_source_tamper_rejection(relative: str, monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_bytes

    def read(path: Path) -> bytes:
        data = original(path)
        return data + b"\n" if path.as_posix().endswith(relative) else data

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(AssertionError, match="fingerprint"):
        cert.verify_upstream_fingerprints()


def test_cohort_rejects_missing_member() -> None:
    members = cert.six.region_members()
    priors = cert.current_member_bounds(members)
    cohort = cert.next_eleven_members(members, priors)
    priors[cohort[-1].counts] -= 1
    with pytest.raises(AssertionError, match="coverage"):
        cert.next_eleven_members(members, priors)


def test_vector_recovery_and_signature_rejection(result: dict[str, Any]) -> None:
    members = {m.counts: m for m in cert.six.region_members()}
    row = next(r for r in result["MEMBER_CERTIFICATES"] if r["represented_vector_count"] == 2)
    member = members[cert.dense(row["witness_counts"])]
    vectors = tuple(cert.dense(v) for v in row["represented_vectors"])
    with pytest.raises(AssertionError, match="represented vectors"):
        cert.certify_member(member, vectors[:1])
    unrelated = cert.dense(result["MEMBER_CERTIFICATES"][0]["witness_counts"])
    with pytest.raises(
        AssertionError, match=r"represented vectors|compression signature|raw bound"
    ):
        cert.certify_member(member, tuple(sorted((member.counts, unrelated))))


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, or official outcome enumeration")


def test_no_census_solver_and_no_hardcoded_bound_inputs(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cert.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(cert.r14, "owner_region", forbidden)
    monkeypatch.setattr(cert.r14, "s4_child", forbidden)
    monkeypatch.setattr(cert.r8, "support_model_status", forbidden)
    monkeypatch.setattr(cert.r8, "solver_runtime_preflight", forbidden)

    def skip_regression(_result: dict[str, Any]) -> None:
        pass

    monkeypatch.setattr(cert, "check_regression", skip_regression)
    for name in (
        "EXPECTED_START_UB",
        "EXPECTED_FINAL_UB",
        "EXPECTED_CORRECTION_FLOOR",
        "EXPECTED_CERTIFIED_MAX",
        "EXPECTED_REMAINING_GAP",
    ):
        monkeypatch.setattr(cert, name, -1)
    assert cert.build_result() == result
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
