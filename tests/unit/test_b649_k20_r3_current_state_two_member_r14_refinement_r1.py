"""Two exact R14 owners, surgical preservation, semantic mutations and byte replay."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_current_state_two_member_r14_refinement_r1 as cert


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def test_exact_source_and_region_identity(result: dict[str, Any]) -> None:
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    assert result["BASE_HEAD"] == "37712cb60fdfeaef9d6b274a122b55217890b022"
    assert result["BASE_TREE"] == "9361e59808f7143173c13893278639ca1a41ee89"
    assert result["BASE_RESULT_SHA256"] == cert.BASE_RESULT_SHA256
    assert result["TWO_MEMBER_IDS"] == list(cert.TARGET_IDS)
    assert result["REPRESENTED_VECTOR_COVERAGE"] == [1, 1]
    assert result["REGION_SHA256"] == cert.REGION_SHA256
    assert result["REGION_COMPRESSED_MEMBER_COUNT"] == 1427
    assert result["REGION_REPRESENTED_VECTOR_COUNT"] == 1543
    assert result["PRESERVED_MEMBER_COUNT"] == 1425
    assert cert.source_authority()["FINAL_OWNER_IDS"] == [cert.TARGET_STATE_ID]


def test_each_own_exact_residual_pair_arithmetic(result: dict[str, Any]) -> None:
    occupied_sets: list[set[tuple[int, int]]] = []
    for member in result["MEMBER_CERTIFICATES"]:
        vector = cert.dense(member["witness_counts"])
        row = member["vector_certificates"][0]
        moment = row["moment_certificate"]
        assert cert.exact_moment_certificate(vector) == moment
        occupied = cert.six.occupied_type_pairs(vector)
        occupied_sets.append(set(occupied))
        assert {tuple(p["types"]) for p in moment["pair_table_rows"]} == set(occupied)
        minima = 0
        slopes: list[Fraction] = []
        for pair in moment["pair_table_rows"]:
            left, right = pair["types"]
            multiplicity = comb(vector[left], 2) if left == right else vector[left] * vector[right]
            assert pair["pair_count"] == multiplicity
            rows = pair["exact_residual_rows"]
            overlaps = cert.hunter.feasible_cell_overlaps(
                cert.hunter.type_cells(left), cert.hunter.type_cells(right)
            )
            assert {tuple(r[2:6]) for r in rows} == set(overlaps)
            for r in rows:
                overlap = tuple(r[2:6])
                direct = cert.hunter.outcome_count(
                    cert.hunter.realize_pair(
                        cert.hunter.type_cells(left), cert.hunter.type_cells(right), overlap
                    ),
                    (cert.hunter.ANCHOR_A, cert.hunter.ANCHOR_B),
                )
                assert direct == r[6] == cert.six.residual_pair_intersection(left, right, overlap)
            minimum = min(r[6] for r in rows)
            slope = min(Fraction(r[6] - minimum, r[5]) for r in rows if r[5])
            assert pair["pair_minimum"] == minimum
            assert pair["outside_slope"] == [slope.numerator, slope.denominator]
            assert all(r[6] >= minimum + slope * r[5] for r in rows)
            minima += multiplicity * minimum
            slopes.append(slope)
        assert moment["pair_count_total"] == 153
        assert minima == moment["pair_minimum_sum"] == 16_397_640
        outside = sum(n * cert.hunter.type_cells(i)[3] for i, n in enumerate(vector))
        assert outside == moment["outside_incidence_total"] == 95
        q, r = divmod(outside, 40)
        mass = (40 - r) * comb(q, 2) + r * comb(q + 1, 2)
        assert mass == moment["outside_pair_mass_floor"] == 70
        slope = min(slopes)
        assert slope == Fraction(433_006)
        assert (
            minima + cert.ceil_fraction(slope * mass) == row["residual_pair_moment"] == 46_708_060
        )
        assert row["r14_correction"] == cert.ceil_fraction(Fraction(46_708_060, 9)) == 5_189_785
        assert row["r14_correction"] != 46_708_060 // 9
        assert moment["multiplicity_dual"] == [1, 9]
        assert moment["multiplicity_cap"] == 18
        assert all(Fraction(comb(m, 2), 9) <= max(0, m - 1) for m in range(19))
    # The A-only and B-only events require distinct tables even when their floors coincide.
    assert occupied_sets[0] != occupied_sets[1]


def test_exact_integer_ceiling_above_float_precision() -> None:
    for n in (0, 9, 10, 46_708_060, 9 * 2**70 + 1):
        assert cert.ceil_fraction(Fraction(n, 9)) == (n + 8) // 9
    with pytest.raises(ValueError, match="nonnegative"):
        cert.ceil_fraction(Fraction(-1))


def test_max_single_credit_and_exact_witnesses(result: dict[str, Any]) -> None:
    for member in result["MEMBER_CERTIFICATES"]:
        vector = cert.dense(member["witness_counts"])
        row = member["vector_certificates"][0]
        corrections = row["corrections"]
        assert corrections == {
            "R6_PAIR": 1_829_458,
            "FOREST": 4_018_000,
            "R14": 5_189_785,
            "NINE_EVENT_HUNTER": 3_193_400,
            "ELEVEN_EVENT_HUNTER": 4_341_400,
        }
        assert row["prior_applied_correction"] == 4_018_000
        assert row["combined_correction"] == max(corrections.values()) != sum(corrections.values())
        assert row["uncorrected_anchor_bound"] == row["anchor_union"] + row["residual_event_sum"]
        assert row["uncorrected_anchor_bound"] - row["prior_applied_correction"] == 355_595_786
        assert row["uncorrected_anchor_bound"] - row["combined_correction"] == 354_424_001
        assert member["member_new_bound"] == 354_424_001
        assert member["member_certified_correction"] == min(
            v["combined_correction"] for v in member["vector_certificates"]
        )
        support = tuple(tuple(t) for t in row["support_witness"])
        assert cert.r8.validate_support_assignment(vector, support)
        assert cert.digest(support) == row["support_sha256"]
        residual, s4 = cert.r8.witness_costs(vector, support)
        assert residual == row["support_residual_pair_moment"] >= row["residual_pair_moment"]
        assert (
            s4
            == row["support_s4_pair_moment"]
            >= row["moment_certificate"]["s4_pairwise_lower_bound"]
        )
        for key, n, floor in (
            ("nine_event_witness_analysis", 9, 3_193_400),
            ("eleven_event_witness_analysis", 11, 4_341_400),
        ):
            analysis = row[key]
            assert len(analysis["subset_tree"]) == n - 1
            assert len(analysis["extended_tree"]) == 17
            assert analysis["exact_tree_weight"] >= analysis["phi_tree_weight"] >= floor


def test_all_other_members_and_previous_certificates_preserved(result: dict[str, Any]) -> None:
    source = cert.region_authority()
    before = {r["member_id"]: r for r in source["COMPLETE_REGION_MEMBERS"]}
    after = result["COMPLETE_REGION_MEMBERS"]
    assert len(after) == len({r["member_id"] for r in after}) == 1427
    assert sum(r["represented_vector_count"] for r in after) == 1543
    changed: set[str] = set()
    for row in after:
        old = before[row["member_id"]]
        assert row["prior_bound"] == old["final_bound"]
        for key in ("member_id", "witness_counts", "raw_bound", "represented_vector_count"):
            assert row[key] == old[key]
        if row["final_bound"] != old["final_bound"]:
            changed.add(row["member_id"])
    assert changed == set(cert.TARGET_IDS)
    assert result["PREVIOUS_REGION_CERTIFICATES"] == {
        k: v for k, v in source.items() if "CERTIFICATES" in k
    }
    assert result["PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"] == cert.digest(
        cert.source_authority()["MEMBER_CERTIFICATES"]
    )
    assert (
        result["DONOR_SOURCE_IDENTITIES"]["NINE_EVENT"]["proof"]
        == cert.source_authority()["NINE_EVENT_PROOF"]
    )
    assert (
        result["DONOR_SOURCE_IDENTITIES"]["ELEVEN_EVENT"]["proof"]
        == cert.base.prior.eleven_event_proof()
    )


def test_complete_23_state_maximum_and_regression_targets(result: dict[str, Any]) -> None:
    start = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    final = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(start) == len(final) == 23
    assert {k for k in start if start[k] != final[k]} == {cert.TARGET_STATE_ID}
    assert result["START_STATE_TERMS"] == cert.source_authority()["FINAL_STATE_TERMS"]
    assert result["START_STATE_BOUND"] == result["START_COMPLETE_R3_UB"] == 355_595_786
    assert result["FINAL_STATE_BOUND"] == max(
        r["final_bound"] for r in result["COMPLETE_REGION_MEMBERS"]
    )
    assert result["FINAL_STATE_BOUND"] == result["FINAL_COMPLETE_R3_UB"] == 355_595_338
    assert result["FINAL_COMPLETE_R3_UB"] == max(
        max(final.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"]
    )
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    assert result["REMAINING_GAP"] == result["FINAL_COMPLETE_R3_UB"] - 313_263_888 == 42_331_450
    for key in ("TAIL_BOUND", "CLASSIFIED_AGGREGATE", "CLASSIFIED_MAX", "CLASSIFIED_TERMS_SHA256"):
        assert result[key] == cert.source_authority()[key]
    assert result["CLASSIFIED_TERM_COUNT"] == 56_550
    assert (
        cert.recompute_family(result["FINAL_STATE_BOUND"])["final"]
        == result["FINAL_FAMILY_MAX_RECOMPUTATION"]
    )


def test_byte_for_byte_result_replay(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_bytes() == cert.hunter.encode(result).encode()
    assert cert.verify_result(result) == {
        "status": "PASS",
        "members": 2,
        "vectors": 2,
        "region_members": 1427,
    }


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("source", "source identity"),
        ("missing_member", "two member"),
        ("duplicate_member", "two member"),
        ("missing_vector", "represented-vector"),
        ("foreign_vector", "identity or compression"),
        ("signature", "identity or compression"),
        ("pair_event", "residual moment"),
        ("pair_minimum", "residual moment"),
        ("slope", "residual moment"),
        ("mass", "residual moment"),
        ("moment", "residual moment"),
        ("ceiling", "integer ceiling"),
        ("multiplicity", "residual moment"),
        ("sum_credit", "max single"),
        ("double_subtraction", "max single"),
        ("hunter_credit", "max single"),
        ("witness", "support witness is invalid"),
        ("preserved_member", "region preservation"),
        ("region_coverage", "region preservation"),
        ("state_term", "23-State"),
        ("owner", "23-State"),
        ("tail", "23-State"),
        ("aggregate", "23-State"),
    ],
)
def test_semantic_mutations_rejected(result: dict[str, Any], mutation: str, reason: str) -> None:
    bad = copy.deepcopy(result)
    member = bad["MEMBER_CERTIFICATES"][0]
    row = member["vector_certificates"][0]
    moment = row["moment_certificate"]
    if mutation == "source":
        bad["BASE_HEAD"] = "0" * 40
    elif mutation == "missing_member":
        bad["MEMBER_CERTIFICATES"].pop()
    elif mutation == "duplicate_member":
        bad["MEMBER_CERTIFICATES"].append(copy.deepcopy(member))
    elif mutation == "missing_vector":
        member["vector_certificates"].pop()
    elif mutation == "foreign_vector":
        row["counts"] = bad["MEMBER_CERTIFICATES"][1]["witness_counts"]
    elif mutation == "signature":
        row["compression_signature"][0] += 1
    elif mutation == "pair_event":
        moment["pair_table_rows"][0]["exact_residual_rows"][0][6] += 1
    elif mutation == "pair_minimum":
        moment["pair_table_rows"][0]["pair_minimum"] += 1
    elif mutation == "slope":
        moment["outside_slope"][0] += 1
    elif mutation == "mass":
        moment["outside_pair_mass_floor"] -= 1
    elif mutation == "moment":
        row["residual_pair_moment"] += 1
    elif mutation == "ceiling":
        row["r14_correction"] -= 1
    elif mutation == "multiplicity":
        moment["multiplicity_cap"] = 17
    elif mutation == "sum_credit":
        row["combined_correction"] = sum(row["corrections"].values())
    elif mutation == "double_subtraction":
        row["vector_new_bound"] -= row["prior_applied_correction"]
    elif mutation == "hunter_credit":
        row["corrections"]["ELEVEN_EVENT_HUNTER"] += 1
    elif mutation == "witness":
        row["support_witness"][0][0] = 99
        # Recompute the digest: a hash-only rejection cannot pass this test.
        row["support_sha256"] = cert.digest(tuple(tuple(t) for t in row["support_witness"]))
    elif mutation == "preserved_member":
        bad["COMPLETE_REGION_MEMBERS"][0]["final_bound"] -= 1
    elif mutation == "region_coverage":
        bad["COMPLETE_REGION_MEMBERS"].pop()
    elif mutation == "state_term":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "owner":
        bad["FINAL_OWNER_IDS"] = [cert.base.TARGET_STATE_ID]
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    else:
        bad["CLASSIFIED_AGGREGATE"][0]["bound"] -= 1
    with pytest.raises(AssertionError, match=reason):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("pair_counter", "inclusion/exclusion"),
        ("ceil_floor", "integer ceiling"),
        ("max_sum", "max single"),
    ],
)
def test_implementation_mutations_killed(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str, reason: str
) -> None:
    member = next(
        m for m in cert.six.region_members() if cert.member_id(m.counts) == cert.TARGET_IDS[0]
    )
    if mutation == "pair_counter":
        original = cert.six.residual_pair_intersection

        def wrong_pair(left: int, right: int, overlap: tuple[int, int, int, int]) -> int:
            return original(left, right, overlap) + 1

        monkeypatch.setattr(cert.six, "residual_pair_intersection", wrong_pair)
    elif mutation == "ceil_floor":

        def wrong_ceiling(value: Fraction) -> int:
            return int(value)

        monkeypatch.setattr(cert, "ceil_fraction", wrong_ceiling)
    else:

        def wrong_combine(values: Mapping[str, int]) -> int:
            return sum(values.values())

        monkeypatch.setattr(cert.hunter, "combine_corrections", wrong_combine)
    with pytest.raises(AssertionError, match=reason):
        cert.certify_member(
            member, cert.represented_vectors()[member.counts], result["START_STATE_BOUND"]
        )


def test_missing_target_and_wrong_source_without_hash_gate(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    members = cert.six.region_members()
    bounds = cert.current_member_bounds(members)
    target = next(m for m in members if cert.member_id(m.counts) == cert.TARGET_IDS[0])
    with pytest.raises(AssertionError, match="coverage"):
        cert.target_members(tuple(m for m in members if m != target), bounds)
    read = Path.read_text

    def wrong_identity(path: Path, *args: Any, **kwargs: Any) -> str:
        text = read(path, *args, **kwargs)
        if path == cert.REPO_ROOT / cert.base.RESULT_RELATIVE:
            source = json.loads(text)
            source["TASK_ID"] = "FOREIGN_SOURCE"
            return json.dumps(source)
        return text

    monkeypatch.setattr(Path, "read_text", wrong_identity)
    cert.source_authority.cache_clear()
    try:
        with pytest.raises(AssertionError, match="source identity"):
            cert.source_authority()
    finally:
        monkeypatch.undo()
        cert.source_authority.cache_clear()
    assert cert.build_result() == result


def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
    pytest.fail("forbidden census, solver, portfolio search or outcome enumeration")


def test_cold_replay_without_solver_census_or_search(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cert.hunter.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(cert.r14, "owner_region", forbidden)
    monkeypatch.setattr(cert.r14, "s4_child", forbidden)
    monkeypatch.setattr(cert.r8, "support_model_status", forbidden)
    monkeypatch.setattr(cert.r8, "solver_runtime_preflight", forbidden)
    monkeypatch.setattr(cert.catalog.r24, "run_chase", forbidden)
    for module in (cert, cert.base, cert.base.prior, cert.region):
        module.source_authority.cache_clear()
    cert.region_authority.cache_clear()
    cert.represented_vectors.cache_clear()
    cert.base.region_members.cache_clear()
    cert.base.region_vectors.cache_clear()
    assert cert.build_result() == result
    assert result["R7_CENSUS_REBUILD_CALLS"] == 0
    assert result["OUTCOME_ENUMERATION_USED"] is False
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == result["PUSH_PR_MERGE"] == "NONE"
