"""Preserved eleven-member Hunter coverage, floors, relaxation, max credit and full R3 replay."""

from __future__ import annotations

import copy
from dataclasses import replace
from math import comb
from pathlib import Path
from typing import Any, NoReturn

import pytest

from lottolab.research import b649_k20_r3_preserved_eleven_hunter_certificate_r1 as cert

EXPECTED = (
    ("[0,9][4,5][5,2][16,1][19,1]", 6_915_433),
    ("[0,9][4,5][5,2][16,1][17,1]", 6_503_392),
    ("[0,9][1,1][4,4][5,2][16,1][19,1]", 6_503_392),
    ("[0,9][1,1][4,4][5,2][16,1][17,1]", 6_503_392),
    ("[0,9][1,2][4,3][5,2][16,1][19,1]", 6_503_392),
    ("[0,9][1,2][4,3][5,2][16,1][17,1]", 6_503_392),
    ("[0,9][1,3][4,2][5,2][16,1][17,1]", 6_503_392),
    ("[0,9][1,4][4,1][5,2][16,1][19,1]", 6_503_392),
    ("[0,9][1,4][4,1][5,2][16,1][17,1]", 6_503_392),
    ("[0,9][1,5][5,2][16,1][19,1]", 6_503_392),
    ("[0,9][1,5][5,2][16,1][17,1]", 6_915_433),
)
DOUBLE_VECTORS = ("[0,9][1,2][4,3][5,2][16,1][17,1]", "[0,9][1,3][4,2][5,2][16,1][19,1]")
PHI = (91_700, 503_741, 1_532_244, 3_162_411)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cert.build_result()


def vectors_of(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for m in result["MEMBER_CERTIFICATES"] for row in m["vector_certificates"]]


def rank_relaxation(floors: tuple[int, ...], mass: int) -> int:
    """Independent dual form: minimise over nonincreasing forest ranks instead of edges."""

    best: int | None = None
    for r1 in range(18):
        for r2 in range(r1 + 1):
            for r3 in range(r2 + 1):
                if sum(min(comb(r + 1, 2), 153) for r in (r1, r2, r3)) < mass:
                    continue
                value = 17 * floors[0] + sum(
                    (floors[k] - floors[k - 1]) * r for k, r in ((1, r1), (2, r2), (3, r3))
                )
                best = value if best is None else min(best, value)
    assert best is not None
    return best


def test_exact_cohort_and_all_twelve_vectors(result: dict[str, Any]) -> None:
    assert Path(cert.__file__ or "").resolve().is_relative_to(cert.REPO_ROOT / "src")
    members = cert.six.region_members()
    priors = cert.current_member_bounds(members)
    cohort = cert.preserved_eleven_members(members, priors)
    assert len(members) == result["REGION_COMPRESSED_MEMBER_COUNT"] == 1_427
    assert sum(m.represented_vector_count for m in members) == 1_543
    assert result["REGION_SHA256"] == cert.REGION_SHA256
    assert [cert.member_id(m.counts) for m in cohort] == [row[0] for row in EXPECTED]
    assert len(cohort) == result["COHORT_MEMBER_COUNT"] == 11
    assert {priors[m.counts] for m in cohort} == {355_630_198}
    records = result["MEMBER_CERTIFICATES"]
    vectors = [cert.dense(v) for row in records for v in row["represented_vectors"]]
    assert len(vectors) == len(set(vectors)) == result["REPRESENTED_VECTOR_COUNT"] == 12
    double = [row for row in records if row["represented_vector_count"] == 2]
    assert len(double) == 1
    assert tuple(row["vector_id"] for row in double[0]["vector_certificates"]) == DOUBLE_VECTORS
    assert result["COVERAGE_STATUS"] == "PASS_11_EXACT_MEMBERS_12_DISTINCT_VECTORS"


def test_type_pairs_exact_rows_and_pair_floors(result: dict[str, Any]) -> None:
    vectors = [cert.dense(row["counts"]) for row in vectors_of(result)]
    pairs = cert.occupied_type_pairs(vectors)
    assert len(pairs) == 24
    assert [list(pair) for pair in pairs] == result["PAIR_TABLE"]["TYPE_PAIRS"]
    rows = cert.exact_pair_rows(pairs)
    assert len(rows) == result["PAIR_TABLE"]["ROW_COUNT"] == 134
    for left, right, *overlap, value in rows:
        cells = (overlap[0], overlap[1], overlap[2], overlap[3])
        assert cert.six.residual_pair_intersection(left, right, cells) == value
    floors = cert.pair_floors(rows)
    assert floors == PHI == tuple(result["PAIR_FLOORS"])
    for total, floor in enumerate(floors):
        assert floor == min(row[6] for row in rows if sum(row[2:6]) == total)
    cert.require_safe_pair_floors(floors, rows)
    with pytest.raises(AssertionError, match="exceeds"):
        cert.require_safe_pair_floors((floors[0] + 1, *floors[1:]), rows)
    with pytest.raises(AssertionError, match="nondecreasing"):
        cert.require_safe_pair_floors((0, 2, 1, 3), rows)
    for vector in vectors:
        assert set(cert.six.occupied_type_pairs(vector)) <= set(pairs)
    assert cert.family_pair_overlap_ceiling() == result["PAIR_OVERLAP_CEILING"] == 3
    with pytest.raises(ValueError, match="outside the R3 range"):
        cert.threshold_edge_counts((1, 4))


def test_residual_events_and_outcome_model(result: dict[str, Any]) -> None:
    lemma = cert.seven_set_lemma_check()
    assert result["OUTCOME_MODEL"] == lemma
    assert lemma["SINGLE_TICKET_OUTCOMES"] == 18_611_432
    assert result["ANCHOR_UNION"] == cert.anchor_union_size()
    for row in vectors_of(result):
        counts = cert.dense(row["counts"])
        residual = sum(n * cert.residual_event_size(i) for i, n in enumerate(counts) if n)
        assert row["anchor_union"] + residual == row["uncorrected_anchor_bound"] == 358_500_198
        assert row["residual_event_definition"] == "R_i = E_i \\ (E_A ∪ E_B)"  # noqa: RUF001
    with pytest.raises(ValueError, match="six labels"):
        cert.count_seven_sets((frozenset(range(5)),), ())


def test_collision_masses_and_small_hunter_relaxation(result: dict[str, Any]) -> None:
    masses = {row["vector_id"]: row["collision_mass"] for row in vectors_of(result)}
    assert sorted(set(masses.values())) == [76, 77, 79]
    for row in vectors_of(result):
        incidences = cert.cell_incidences(cert.dense(row["counts"]))
        assert sum(incidences) == 18 * 6 and list(incidences) == row["cell_incidences"]
        assert sum(cert.cell_collision_floors(incidences)) == row["collision_mass"]
    expected = {76: 6_503_392, 77: 6_503_392, 79: 6_915_433}
    for mass, hunter in expected.items():
        tree = cert.minimum_tree_correction(PHI, mass)
        assert tree.correction == hunter == rank_relaxation(PHI, mass)
        assert tree.edge_counts == (mass, 0, 0)
        assert tree.correction == 17 * PHI[0] + (PHI[1] - PHI[0]) * cert.rank_floor(mass)
    assert {
        row["collision_mass"]: row["hunter_correction"] for row in result["HUNTER_BY_MASS"]
    } == (expected)
    assert (cert.rank_floor(76), cert.rank_floor(78), cert.rank_floor(79)) == (12, 12, 13)
    assert cert.balanced_collision_mass(96, 40) == 72
    assert cert.balanced_collision_mass(7, 3) == 5
    with pytest.raises(ValueError):
        cert.balanced_collision_mass(-1, 3)


def test_hunter_theorem_finite_checks(result: dict[str, Any]) -> None:
    assert cert.hunter_theorem_checks() == result["HUNTER_THEOREM_CHECKS"]
    triangle = ((0, 1), (0, 2), (1, 2))
    assert cert.graph_rank(3, triangle) == cert.rank_floor(3) == 2
    assert cert.verify_hunter_exhaustively(2, 3) == 16 * 4 * 3
    weights = {(0, 1): 0, (0, 2): 3, (1, 2): 2, (0, 3): 1, (1, 3): 3, (2, 3): 0}
    assert sum(weights[edge] for edge in cert.threshold_tree(4, weights)) == 8


def test_compressed_member_takes_weakest_vector(result: dict[str, Any]) -> None:
    members = {m.counts: m for m in cert.six.region_members()}
    for record in result["MEMBER_CERTIFICATES"]:
        member = members[cert.dense(record["witness_counts"])]
        rows = record["vector_certificates"]
        assert record["member_new_bound"] == max(r["vector_new_bound"] for r in rows)
        assert record["member_certified_correction"] == min(r["combined_correction"] for r in rows)
        state = cert.catalog.rebuild_member(member)
        for row in rows:
            vector_state = cert.catalog.rebuild_member(
                replace(member, counts=cert.dense(row["counts"]))
            )
            assert cert.eleven.compression_signature(vector_state) == (
                cert.eleven.compression_signature(state)
            )
    assert cert.member_correction((9, 12)) == 9
    assert cert.member_correction((12, 9)) == 9
    with pytest.raises(ValueError):
        cert.member_correction(())
    with pytest.raises(ValueError):
        cert.member_correction((-1, 9))


def test_max_not_sum_single_replacement(result: dict[str, Any]) -> None:
    by_member = dict(EXPECTED)
    for record in result["MEMBER_CERTIFICATES"]:
        assert record["member_certified_correction"] == by_member[record["member_id"]]
        assert record["member_new_bound"] == 358_500_198 - by_member[record["member_id"]]
        assert record["hunter_correction_applied"] is True
        for row in record["vector_certificates"]:
            parts = (
                row["r6_pair_correction"],
                row["forest_correction"],
                row["r14_correction"],
                row["hunter_correction"],
            )
            assert row["combined_correction"] == max(parts) == row["hunter_correction"]
            assert row["combined_correction"] != sum(parts)
            assert row["correction_source"] == "HUNTER_TREE"
            assert row["prior_applied_correction"] == row["forest_correction"] == 2_870_000
            assert row["hunter_correction"] > row["r14_correction"] >= 5_103_875
            assert row["vector_new_bound"] == row["uncorrected_anchor_bound"] - max(parts)
            assert record["member_raw_bound"] == row["uncorrected_anchor_bound"] - 2_870_000
    assert result["MINIMUM_R14_CORRECTION"] == 5_103_875
    assert result["MINIMUM_HUNTER_CORRECTION"] == 6_503_392
    assert cert.combine_corrections({"a": 1, "b": 5, "c": 3}) == 5
    with pytest.raises(ValueError):
        cert.combine_corrections({})
    with pytest.raises(ValueError):
        cert.combine_corrections({"a": -1})
    assert result["DUPLICATE_CORRECTIONS"] == 0


def test_witness_soundness(result: dict[str, Any]) -> None:
    rows = cert.exact_pair_rows(
        cert.occupied_type_pairs(cert.dense(r["counts"]) for r in vectors_of(result))
    )
    values = {(r[0], r[1], (r[2], r[3], r[4], r[5])): r[6] for r in rows}
    for row in vectors_of(result):
        counts = cert.dense(row["counts"])
        support = tuple(tuple(ticket) for ticket in row["support_witness"])
        assert len(support) == 18
        assert cert.r8.validate_support_assignment(counts, support)
        assert cert.digest(support) == row["support_sha256"]
        witness = cert.witness_analysis(counts, support, PHI, values)
        assert witness == row["witness_analysis"]
        assert witness["collision_mass"] >= row["collision_mass"]
        assert (
            witness["exact_tree_weight"] >= witness["phi_tree_weight"] >= row["hunter_correction"]
        )
        moment = cert.r8.witness_costs(counts, support)[0]
        assert witness["exact_residual_pair_moment"] == moment >= row["residual_pair_moment"]


def test_preserves_earlier_certificates_and_all_other_members(result: dict[str, Any]) -> None:
    source = cert.eleven_authority()
    rows = result["COMPLETE_REGION_MEMBERS"]
    final = {r["member_id"]: r["final_bound"] for r in rows}
    batches = [r["batch"] for r in result["EARLIER_CERTIFICATES"]]
    assert batches.count("SIX_R14") == 6 and batches.count("ELEVEN_R14") == 11
    for row in result["EARLIER_CERTIFICATES"]:
        assert final[row["member_id"]] == row["member_new_bound"]
    assert result["EARLIER_CERTIFICATES_PRESERVED"] is True
    old = {r["member_id"]: r for r in source["COMPLETE_REGION_MEMBERS"]}
    certified = {r["member_id"] for r in result["MEMBER_CERTIFICATES"]}
    assert len(rows) == len(final) == 1_427
    for row in rows:
        assert row["prior_bound"] == old[row["member_id"]]["final_bound"]
        assert row["raw_bound"] == old[row["member_id"]]["raw_bound"]
        if row["member_id"] not in certified:
            assert row["final_bound"] == row["prior_bound"]
    preserved = [r for r in rows if r["member_id"] not in certified]
    assert len(preserved) == result["PRESERVED_MEMBER_COUNT"] == 1_416
    assert max(r["final_bound"] for r in preserved) == result["PRESERVED_REMAINDER_MAX"]
    assert result["PRESERVED_REMAINDER_MAX"] == 355_629_750
    assert result["CERTIFIED_COHORT_MAX"] == 351_996_806
    assert result["FINAL_STATE_BOUND"] == max(r["final_bound"] for r in rows) == 355_629_750


def test_complete_r3_family_recomputation(result: dict[str, Any]) -> None:
    replay = cert.recompute_family(result["FINAL_STATE_BOUND"])
    assert replay["start"] == result["START_FAMILY_MAX_RECOMPUTATION"]
    assert replay["final"] == result["FINAL_FAMILY_MAX_RECOMPUTATION"]
    assert result["START_COMPLETE_R3_UB"] == 355_630_198
    assert result["FINAL_COMPLETE_R3_UB"] == replay["final"]["R3_BOUND"] == 355_629_750
    assert result["REMAINING_GAP"] == 42_365_862
    assert result["FINAL_COMPLETE_R3_UB"] - result["CURRENT_INCUMBENT"] == result["REMAINING_GAP"]
    assert result["FINAL_OWNER_IDS"] == ["state:s2-13548976-s3-951748"]
    before = {r["stable_id"]: r["bound"] for r in result["START_STATE_TERMS"]}
    after = {r["stable_id"]: r["bound"] for r in result["FINAL_STATE_TERMS"]}
    assert len(before) == len(after) == result["STATE_TERM_COUNT"] == 23
    assert {key for key in before if before[key] != after[key]} == {cert.TARGET_STATE_ID}
    assert result["NEXT_COMPETING_STATE"] == {
        "stable_id": "state:s2-13169800-s3-789320",
        "bound": 355_628_469,
    }
    assert result["TAIL_BOUND"] == 354_039_277
    assert result["CLASSIFIED_MAX"] == 355_468_904
    assert result["FINAL_COMPLETE_R3_UB"] == max(
        max(after.values()), result["TAIL_BOUND"], result["CLASSIFIED_MAX"]
    )


def test_stored_result_and_full_replay(result: dict[str, Any]) -> None:
    assert cert.RESULT_PATH.read_text() == cert.encode(result)
    assert cert.verify_result(result) == {"status": "PASS", "certificates": 11, "vectors": 12}


@pytest.mark.parametrize(
    "field",
    [
        "member_new_bound",
        "hunter_correction",
        "collision_mass",
        "combined_correction",
        "r14_correction",
        "phi_tree_weight",
    ],
)
def test_rejects_vector_arithmetic_tampering(result: dict[str, Any], field: str) -> None:
    tampered = copy.deepcopy(result)
    row = tampered["MEMBER_CERTIFICATES"][0]["vector_certificates"][0]
    if field == "member_new_bound":
        tampered["MEMBER_CERTIFICATES"][0][field] -= 1
    elif field == "phi_tree_weight":
        row["witness_analysis"][field] += 1
    else:
        row[field] += 1
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
        "earlier",
        "pair_floor",
        "pair_row",
        "family",
        "tail",
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
    elif mutation == "earlier":
        bad["EARLIER_CERTIFICATES"][0]["member_new_bound"] -= 1
    elif mutation == "pair_floor":
        bad["PAIR_FLOORS"][3] -= 1
    elif mutation == "pair_row":
        bad["PAIR_TABLE"]["ROWS"][0][6] += 1
    elif mutation == "family":
        bad["FINAL_STATE_TERMS"].pop()
    elif mutation == "tail":
        bad["TAIL_BOUND"] -= 1
    else:
        bad["CERTIFIED_COHORT_MAX"] -= 1
    with pytest.raises(AssertionError, match=r"support witness|replay"):
        cert.verify_result(bad)


@pytest.mark.parametrize(
    "relative",
    [
        cert.eleven.RESULT_RELATIVE,
        "src/lottolab/research/b649_k20_r3_current_state_next_eleven_r14_certificate_r1.py",
        "src/lottolab/research/b649_k20_r3_current_owner_six_member_r14_certificate_r1.py",
        "src/lottolab/research/b649_k20_r3_frontier_realizability_bound_r8.py",
        "src/lottolab/research/b649_k20_outside_min_s2_global_penalty_bound_r1.py",
        "src/lottolab/research/b649_k20_heavy_pair_r3plus_global_bound_r3.py",
        "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py",
        "src/lottolab/research/b649_k20_r3_anchor_incidence_bound_r5.py",
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
    cohort = cert.preserved_eleven_members(members, priors)
    priors[cohort[-1].counts] -= 1
    with pytest.raises(AssertionError, match="coverage"):
        cert.preserved_eleven_members(members, priors)


def test_vector_recovery_and_signature_rejection(result: dict[str, Any]) -> None:
    members = {m.counts: m for m in cert.six.region_members()}
    row = next(r for r in result["MEMBER_CERTIFICATES"] if r["represented_vector_count"] == 2)
    member = members[cert.dense(row["witness_counts"])]
    vectors = tuple(cert.dense(v) for v in row["represented_vectors"])
    rows = cert.exact_pair_rows(cert.occupied_type_pairs(vectors))
    values = {(r[0], r[1], (r[2], r[3], r[4], r[5])): r[6] for r in rows}
    with pytest.raises(AssertionError, match="represented vectors"):
        cert.certify_member(member, vectors[:1], PHI, values)
    unrelated = cert.dense(result["MEMBER_CERTIFICATES"][0]["witness_counts"])
    with pytest.raises(AssertionError, match=r"represented vectors|compression signature"):
        cert.certify_member(member, tuple(sorted((member.counts, unrelated))), PHI, values)


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
        "EXPECTED_CERTIFIED_MAX",
        "EXPECTED_R14_FLOOR",
        "EXPECTED_REMAINING_GAP",
    ):
        monkeypatch.setattr(cert, name, -1)
    monkeypatch.setattr(cert, "EXPECTED_PAIR_FLOORS", ())
    monkeypatch.setattr(cert, "EXPECTED_HUNTER_BY_MASS", {})
    assert cert.build_result() == result
    assert result["NEW_HEAVY_SOLVER_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
