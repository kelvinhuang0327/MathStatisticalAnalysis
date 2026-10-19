"""W=808 class, NB caps, all-t Route B, frontier completeness, and the family replay."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from fractions import Fraction
from time import monotonic
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_class_dominance_or_descent_r13 as r13
from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25
from lottolab.research import b649_k20_min_s2_nb_w808_frontier_r1 as x

Start = tuple[x.Chase, x.CapAuthorities, dict[str, object]]
W808_CLASS_MAX = 313_340_936
W808_MAX_PROFILE = "55555555554411111111"
CURSOR_BOUND = 313_106_760
NEXT_PROFILE = "66666643322222222211"
NEXT_BOUND = 313_551_160
FAMILY_BOUND = 313_551_160
REMAINING_GAP = 287_272
RESOLVED_MAX = 313_404_784


@pytest.fixture(scope="module")
def start() -> Start:
    return x.start_chase(monotonic() + 600)


@pytest.fixture
def chase(start: Start) -> x.Chase:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 600
    return fresh


@pytest.fixture(scope="module")
def plateau(start: Start) -> x.PlateauFrontier:
    return x.r30.freeze_plateau(x.CURSOR, x.START_BOUND, start[0].bounds, monotonic() + 600)


@pytest.fixture(scope="module")
def certificates(plateau: x.PlateauFrontier) -> list[dict[str, object]]:
    return [x.member_certificate(profile) for profile in plateau.profiles]


def test_exact_class_enumeration(
    start: Start, plateau: x.PlateauFrontier, monkeypatch: pytest.MonkeyPatch
) -> None:
    members, rejected, raw = x.assert_class_membership(start[0], plateau)
    assert len(members) == x.TARGET_W808_COUNT == raw
    assert rejected == {}
    assert members[0] == x.CURSOR
    assert members == x.nb.enumerate_degree_square_class(290)
    assert all(x.overlap_wedge_count(profile) == 808 for profile in members)
    w809, _rejected, _raw = x.independent_class(292)
    assert w809 == x.nb.enumerate_degree_square_class(292)
    assert len(w809) == x.nb.TARGET_W809_COUNT
    short = replace(plateau, profiles=plateau.profiles[:-1])
    with pytest.raises(AssertionError, match="W=808 plateau disagrees"):
        x.assert_class_membership(start[0], short)
    print("MUTATION_KILLED class-member-dropped")
    resolved = copy.deepcopy(start[0])
    resolved.bounds[members[-1]] = 0
    with pytest.raises(AssertionError, match="already in the resolved ledger"):
        x.assert_class_membership(resolved, plateau)
    print("MUTATION_KILLED class-member-already-resolved")

    def pruned(_square_sum: int) -> tuple[x.DegreeProfile, ...]:
        return members[1:]

    monkeypatch.setattr(x.nb, "enumerate_degree_square_class", pruned)
    with pytest.raises(AssertionError, match="pruned and unpruned W=808 class"):
        x.assert_class_membership(start[0], plateau)
    print("MUTATION_KILLED pruned-enumerator")


def _ascending_capacity(degrees: object, vertex: int) -> int:
    values = cast(tuple[int, ...], degrees)
    own = values[vertex]
    others = sorted(g for i, g in enumerate(values) if i != vertex)[:own]
    return sum(min(g - 1, own - 1) for g in others)


def _zero_floor(_degrees: object) -> int:
    return 0


def test_degree_sequence_nb_lemma(monkeypatch: pytest.MonkeyPatch) -> None:
    report = x.nb.small_graph_soundness(5)
    assert report["STATUS"] == "PASS"
    assert report["LABELLED_GRAPHS_CHECKED"] == 1 + 2 + 8 + 64 + 1024
    row = x.member_certificate(x.CURSOR)
    assert (row["NB_OPEN_WEDGE_FLOOR"], row["NB_TRIANGLE_CAP"]) == (86, 240)
    assert row["R18_TRIANGLE_CAP"] == 267
    monkeypatch.setattr(x.nb, "neighbourhood_capacity", _ascending_capacity)
    with pytest.raises(AssertionError, match="disagrees with the closed form"):
        x.nb.assert_nb_capacity(x.nb.profile_degrees(x.CURSOR))
    print("MUTATION_KILLED nb-capacity-smallest-degrees")
    monkeypatch.undo()
    monkeypatch.setattr(x.nb, "nb_open_wedge_floor", _zero_floor)
    with pytest.raises(AssertionError, match="cursor NB regression"):
        x.member_certificate(x.CURSOR)
    print("MUTATION_KILLED cursor-open-wedge-floor")


def test_triangle_cap_provenance(
    start: Start, plateau: x.PlateauFrontier, certificates: list[dict[str, object]]
) -> None:
    members = tuple(plateau.profiles)
    scan = x.prior_cap_scan(start[0], start[1], members)
    assert scan["STATUS"] == "NO_PRIOR_CERTIFIED_CAP_FOR_ANY_MEMBER"
    assert scan["ROWS_NAMING_A_MEMBER"] == 0
    for row in certificates:
        nb_cap, r18 = int(str(row["NB_TRIANGLE_CAP"])), int(str(row["R18_TRIANGLE_CAP"]))
        assert row["TRIANGLE_CAP"] == min(nb_cap, r18)
        assert row["PRIOR_CERTIFIED_CAP"] is None
        assert row["CAP_ORIGIN"] in (x.CAP_NB, x.CAP_R18, x.CAP_TIE)
    assert {row["CAP_ORIGIN"] for row in certificates} == {x.CAP_NB}
    forged = copy.deepcopy(start[1])
    forged.cheap.append({"PROFILE_ID": x.profile_id(members[3]), "CAP": 200})
    with pytest.raises(AssertionError, match="cap is unclassified"):
        x.prior_cap_scan(start[0], forged, members)
    print("MUTATION_KILLED unknown-source-cap")


def test_weaker_cap_choice_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def weakest(nb_cap: int, class_cap: int, _catalog_cap: int | None = None) -> int:
        return max(nb_cap, class_cap)

    monkeypatch.setattr(x.nb, "combined_triangle_cap", weakest)
    with pytest.raises(AssertionError, match="not the strongest verified cap"):
        x.member_certificate(x.CURSOR)
    print("MUTATION_KILLED weaker-cap")


def test_all_t_envelope(
    certificates: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    for row in certificates:
        cap = int(str(row["TRIANGLE_CAP"]))
        assert row["T_RANGE"] == [22, cap]
        assert row["TERM_COUNT"] == cap - 21
        assert row["ARGMAX_TRIANGLES"] == cap
        assert row["ENVELOPE_STRICTLY_INCREASING_IN_T"] is True
    original = x.r32.route_b_envelope

    def cap_only(profile: x.DegreeProfile, cap: int, base: int) -> list[x.Term]:
        return original(profile, cap, base)[-1:]

    monkeypatch.setattr(x.r32, "route_b_envelope", cap_only)
    with pytest.raises(AssertionError, match="does not cover every t"):
        x.member_certificate(x.CURSOR)
    print("MUTATION_KILLED cap-only-envelope")


def test_integer_rounding(
    certificates: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (x.ceil_fraction(Fraction(-7, 2)), x.floor_fraction(Fraction(-7, 2))) == (-3, -4)
    assert (x.ceil_fraction(Fraction(7, 2)), x.floor_fraction(Fraction(7, 2))) == (4, 3)
    # 679 = 7 * 97, 231 = 7 * 33 and 112 = 7 * 16, so the S4 credit 4 * S4 / 7 is exact.
    assert all(int(str(row["S4_FLOOR_AT_ARGMAX"])) % 7 == 0 for row in certificates)
    profile = x.decode_profile(W808_MAX_PROFILE)
    row = x.member_certificate(profile)
    s4 = int(str(row["S4_FLOOR_AT_ARGMAX"]))
    s3 = int(str(row["S3_AT_ARGMAX"]))
    exact = x.K20_S1 - x.K20_S2 + s3 - Fraction(4 * s4, 7)
    assert exact.denominator == 1
    assert row["ALL_T_MAX_BOUND"] == x.ceil_fraction(exact) == W808_CLASS_MAX
    original = x.r32.route_b_envelope

    def off_by_one(profile: x.DegreeProfile, cap: int, base: int) -> list[x.Term]:
        return [(t, b - 1, k, c, w, s) for t, b, k, c, w, s in original(profile, cap, base)]

    monkeypatch.setattr(x.r32, "route_b_envelope", off_by_one)
    with pytest.raises(AssertionError, match="integer rounding disagrees"):
        x.member_certificate(profile)
    print("MUTATION_KILLED bound-off-by-one")
    monkeypatch.undo()
    monkeypatch.setattr(x, "ceil_fraction", x.floor_fraction)
    with pytest.raises(AssertionError, match="integer rounding disagrees"):
        x.member_certificate(profile)
    print("MUTATION_KILLED k4-floor-instead-of-ceiling")


def test_witness_soundness(start: Start, monkeypatch: pytest.MonkeyPatch) -> None:
    report = x.witness_nb_soundness(start[1].witness)
    assert report["STATUS"] == "PASS"
    assert report["REALIZED_TRIANGLES"] == x.WITNESS_TRIANGLES
    triangles = int(str(report["REALIZED_TRIANGLES"]))
    assert triangles <= int(str(report["NB_TRIANGLE_CAP"]))
    assert int(str(report["NB_ROUTE_B_ALL_T_BOUND"])) >= x.WITNESS_UNION

    def tight(_degrees: object) -> tuple[int, int, int]:
        return (0, 0, x.WITNESS_TRIANGLES - 1)

    monkeypatch.setattr(x.nb, "profile_nb_cap", tight)
    with pytest.raises(AssertionError, match="NB cap fails on the realized witness"):
        x.witness_nb_soundness(start[1].witness)
    print("MUTATION_KILLED witness-nb-cap")


def test_frontier_completeness(
    chase: x.Chase, plateau: x.PlateauFrontier, certificates: list[dict[str, object]]
) -> None:
    nxt = x.install_frontier(chase, plateau, certificates)
    assert x.profile_id(nxt) == NEXT_PROFILE
    assert chase.cursor_bound == NEXT_BOUND == x.NEXT_COARSE_REFERENCE
    assert x.overlap_wedge_count(nxt) == 807
    report = x.frontier_completeness(chase, nxt)
    assert report["STATUS"] == "PASS" and report["NEXT_CLASS_SQUARE_SUM"] == 288
    dominance = x.coarse_dominance(nxt, NEXT_BOUND)
    assert (dominance["W_MIN"], dominance["W_MAX"]) == (774, 807)
    with pytest.raises(AssertionError, match="disagree with the W formula"):
        x.coarse_dominance(nxt, NEXT_BOUND - 1)
    print("MUTATION_KILLED next-bound-mismatch")
    formula = x.coarse_bound_at_wedges

    def bumped(wedges: int) -> int:
        return formula(wedges) + (10**6 if wedges == 774 else 0)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(x, "coarse_bound_at_wedges", bumped)
        with pytest.raises(AssertionError, match="exceeds the next frontier bound"):
            x.coarse_dominance(nxt, NEXT_BOUND)
    print("MUTATION_KILLED coarse-dominance")
    skipped = copy.deepcopy(chase)
    following = x.nb.enumerate_degree_square_class(288)[1]
    skipped.cursor = following
    with pytest.raises(AssertionError, match="not the first unresolved profile"):
        x.frontier_completeness(skipped, following)
    print("MUTATION_KILLED skipped-next-cursor")
    reopened = copy.deepcopy(chase)
    del reopened.bounds[x.nb.CURSOR]
    with pytest.raises(AssertionError, match="W=809 profile is unresolved"):
        x.frontier_completeness(reopened, nxt)
    print("MUTATION_KILLED w809-reopened")


def test_authority_and_provenance_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    provenance = x.module_provenance()
    assert len(provenance) == len(x.PROVENANCE_MODULES)
    monkeypatch.setattr(x, "PROVENANCE_MODULES", (x,))
    with pytest.raises(AssertionError, match="not committed at the base"):
        x.module_provenance()
    print("MUTATION_KILLED uncommitted-source")
    monkeypatch.setattr(x, "NB_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="sealed NB fingerprint changed"):
        x.nb_authority()
    print("MUTATION_KILLED nb-digest")


def _forbid_solvers(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a solver or outcome enumeration was called")

    monkeypatch.setattr(x.r28, "bounded_batch", forbidden)
    monkeypatch.setattr(x.r28, "solve_group", forbidden)
    monkeypatch.setattr(x.r30, "evaluate_portfolio", forbidden)
    monkeypatch.setattr(r13, "degree_class_open_wedge_relaxation", forbidden)
    monkeypatch.setattr(r25, "degree_class_open_wedge_relaxation", forbidden)


def test_family_replay_matches_and_solvers_stay_idle(
    start: Start, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_solvers(monkeypatch)
    deadline = monotonic() + 600
    first = x.certify_w808(copy.deepcopy(start[0]), start[1], deadline)
    second = x.certify_w808(copy.deepcopy(start[0]), start[1], deadline)
    assert x.nb.same_result(first, second)
    digest = x.write_result(first)
    loaded = json.loads(x.result_path().read_text(encoding="utf-8"))
    assert x.nb.same_result(loaded, first)
    assert x.write_result(second) == digest
    assert first["W808_PROFILE_COUNT"] == first["W808_CERTIFIED_COUNT"] == 147
    assert first["W808_CLASS_MAX"] == W808_CLASS_MAX
    assert first["W808_CLASS_MAX_PROFILE_IDS"] == [W808_MAX_PROFILE]
    assert first["PRE_EXISTING_RESOLVED_MAX"] == RESOLVED_MAX
    assert (first["NEXT_FRONTIER_W"], first["NEXT_FRONTIER_BOUND"]) == (807, NEXT_BOUND)
    assert first["FINAL_FAMILY_UPPER_BOUND"] == first["FAMILY_UPPER_BOUND"] == FAMILY_BOUND
    assert first["FINAL_OWNER_CLASS"] == NEXT_PROFILE
    assert first["FINAL_OWNER_TYPE"] == "UNRESOLVED_CURSOR_COARSE_ENVELOPE"
    assert first["REMAINING_GAP"] == REMAINING_GAP
    assert first["FINAL_LEDGER_COUNT"] == x.START_LEDGER_COUNT + 147 == 2_075
    assert first["TASK_STATUS"] == x.SUCCESS_A
    certificates = cast(list[dict[str, object]], first["W808_CERTIFICATES"])
    cursor_row = next(r for r in certificates if r["PROFILE_ID"] == x.profile_id(x.CURSOR))
    assert cursor_row["ALL_T_MAX_BOUND"] == CURSOR_BOUND
    assert (first["SOLVER_CALLS"], first["OUTCOME_ENUMERATIONS"]) == (0, 0)
    assert (first["NEW_HEAVY_SOLVER_STARTED"], first["PRODUCTION_MUTATION"]) == ("NO", "NONE")

    def broken_family(_chase: object) -> tuple[int, tuple[()]]:
        return (0, ())

    monkeypatch.setattr(x.r28, "family_state", broken_family)
    with pytest.raises(AssertionError, match="family recompute disagreement"):
        x.nb.assert_family_agreement(copy.deepcopy(start[0]))
    print("MUTATION_KILLED family-recompute")
    print(
        "CERTIFIED"
        f" w808_count={first['W808_PROFILE_COUNT']}"
        f" w808_max={first['W808_CLASS_MAX']}"
        f" next={first['NEXT_FRONTIER_PROFILE']}@{first['NEXT_FRONTIER_BOUND']}"
        f" family={first['FINAL_FAMILY_UPPER_BOUND']}"
        f" gap={first['REMAINING_GAP']}"
    )
