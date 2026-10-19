"""W=807..786 classes, NB caps, all-t Route B, tamper detection, ledger and family replay."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from fractions import Fraction
from time import monotonic
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_class_dominance_or_descent_r13 as r13
from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25
from lottolab.research import b649_k20_min_s2_nb_w807_w786_batch_certificate_r1 as x

Start = tuple[x.Chase, x.CapAuthorities, dict[str, object]]
Batch = tuple[dict[str, object], x.Chase]
CLASS_MAXIMA = {
    807: 313_311_444, 806: 313_307_736, 805: 313_304_804, 804: 313_293_236,
    803: 313_290_304, 802: 313_287_372, 801: 313_294_892, 800: 313_290_796,
    799: 313_268_776, 798: 313_276_296, 797: 313_272_200, 796: 313_278_424,
    795: 313_258_088, 794: 313_263_148, 793: 313_260_216, 792: 313_257_028,
    791: 313_244_940, 790: 313_241_620, 789: 313_238_820, 788: 313_235_500,
    787: 313_223_412, 786: 313_220_224,
}  # fmt: skip
BATCH_MAX = 313_311_444
BATCH_MAX_PROFILE = "55555544444444310000"
NEXT_PROFILE = "66544333333333332222"
NEXT_BOUND = 313_394_584
FAMILY_BOUND = 313_404_784
FAMILY_OWNERS = ["66665555554440000000", "66655555555530000000"]
NEXT_COMPETING = 313_404_396
REMAINING_GAP = 140_896
FINAL_LEDGER_SHA256 = "d7f3f1cb70e3f16f90210cd229e5178855d3e466ef595b4d0d15feebd5253e1f"
UNLEDGERED_MAX = 313_476_764
UNLEDGERED_MAX_PROFILE = "66665555555520000000"
SMALL_CLASS = 786


@pytest.fixture(scope="module")
def start() -> Start:
    return x.start_chase(monotonic() + 900)


@pytest.fixture
def chase(start: Start) -> x.Chase:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 900
    return fresh


@pytest.fixture(scope="module")
def batch(start: Start) -> Batch:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 900
    result = x.certify_batch(fresh, start[1], monotonic() + 900)
    return result, fresh


@pytest.fixture(scope="module")
def plateau(start: Start) -> x.PlateauFrontier:
    return x.r30.freeze_plateau(
        x.decode_profile(x.START_CURSOR_ID), x.START_BOUND, start[0].bounds, monotonic() + 900
    )


def _class_rows(result: dict[str, object], wedges: int) -> list[list[object]]:
    classes = x.object_row(result["W_CLASSES"])
    return [
        list(cast("list[object]", r))
        for r in x.rows(x.object_row(classes[str(wedges)])["CERTIFICATES"])
    ]


def _cell(row: list[object], column: str) -> object:
    return row[x.ROW_COLUMNS.index(column)]


def _sealed_class(result: dict[str, object], wedges: int) -> dict[str, object]:
    return copy.deepcopy(x.object_row(x.object_row(result["W_CLASSES"])[str(wedges)]))


def test_exact_class_enumeration(
    start: Start, plateau: x.PlateauFrontier, monkeypatch: pytest.MonkeyPatch
) -> None:
    total = 0
    for wedges in x.CLASS_WEDGES:
        level = x.class_level(wedges)
        members = x.nb.enumerate_degree_square_class(level)
        independent, _rejected, raw = x.w8.independent_class(level)
        assert members == independent
        assert len(members) == x.CLASS_COUNTS[wedges] and raw >= len(members)
        assert list(members) == sorted(members, reverse=True)
        assert all(x.overlap_wedge_count(profile) == wedges for profile in members)
        assert all(profile not in start[0].bounds for profile in members)
        total += len(members)
    assert total == x.TOTAL_PROFILES == 2_560
    assert len(x.CLASS_WEDGES) == 22 and (x.CLASS_WEDGES[0], x.CLASS_WEDGES[-1]) == (807, 786)
    members = x.assert_class_membership(start[0], plateau, 807)[0]
    assert members[0] == start[0].cursor and len(members) == 147
    short = replace(plateau, profiles=plateau.profiles[:-1])
    with pytest.raises(AssertionError, match="W=807 plateau disagrees"):
        x.assert_class_membership(start[0], short, 807)
    print("MUTATION_KILLED class-member-dropped")
    resolved = copy.deepcopy(start[0])
    resolved.bounds[members[-1]] = 0
    with pytest.raises(AssertionError, match="already in the resolved ledger"):
        x.assert_class_membership(resolved, plateau, 807)
    print("MUTATION_KILLED class-member-already-resolved")
    monkeypatch.setitem(x.CLASS_COUNTS, 807, 146)
    with pytest.raises(AssertionError, match="W=807 class size differs"):
        x.assert_class_membership(start[0], plateau, 807)
    print("MUTATION_KILLED pinned-class-count")
    monkeypatch.undo()

    def pruned(_square_sum: int) -> tuple[x.DegreeProfile, ...]:
        return members[1:]

    monkeypatch.setattr(x.nb, "enumerate_degree_square_class", pruned)
    with pytest.raises(AssertionError, match="pruned and unpruned W=807 class"):
        x.assert_class_membership(start[0], plateau, 807)
    print("MUTATION_KILLED pruned-enumerator")


def _ascending_capacity(degrees: object, vertex: int) -> int:
    values = cast("tuple[int, ...]", degrees)
    own = values[vertex]
    others = sorted(g for i, g in enumerate(values) if i != vertex)[:own]
    return sum(min(g - 1, own - 1) for g in others)


def _zero_floor(_degrees: object) -> int:
    return 0


def test_degree_sequence_nb_lemma(monkeypatch: pytest.MonkeyPatch) -> None:
    report = x.nb.small_graph_soundness(5)
    assert report["STATUS"] == "PASS"
    assert report["LABELLED_GRAPHS_CHECKED"] == 1 + 2 + 8 + 64 + 1024
    checked = 0
    for wedges in x.CLASS_WEDGES:
        for profile in x.nb.enumerate_degree_square_class(x.class_level(wedges)):
            assert x.exact_nb_cap(profile) == x.nb.profile_nb_cap(profile)
            checked += 1
    assert checked == x.TOTAL_PROFILES
    first = x.decode_profile(x.START_CURSOR_ID)
    with pytest.raises(ValueError, match="impossible degree sequence"):
        x.nb.nb_triangle_cap([7, 7, 7, 7, 7, 7, 7])
    monkeypatch.setattr(x.nb, "neighbourhood_capacity", _ascending_capacity)
    with pytest.raises(AssertionError, match="disagrees with the closed form"):
        x.nb.assert_nb_capacity(x.nb.profile_degrees(first))
    print("MUTATION_KILLED nb-capacity-smallest-degrees")
    monkeypatch.undo()
    monkeypatch.setattr(x.nb, "nb_open_wedge_floor", _zero_floor)
    with pytest.raises(AssertionError, match="NB cap disagrees with the independent derivation"):
        x.member_certificate(first, 807)
    print("MUTATION_KILLED open-wedge-floor-zero")
    monkeypatch.undo()

    real = x.nb.profile_nb_cap

    def one_more(profile: x.DegreeProfile) -> tuple[int, int, int]:
        wedges, floor, cap = real(profile)
        return wedges, floor, cap + 1

    monkeypatch.setattr(x.nb, "profile_nb_cap", one_more)
    with pytest.raises(AssertionError, match="NB cap disagrees with the independent derivation"):
        x.member_certificate(first, 807)
    print("MUTATION_KILLED nb-cap-plus-one")


def test_triangle_cap_provenance(
    start: Start, batch: Batch, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = batch[0]
    for wedges in x.CLASS_WEDGES:
        members = x.nb.enumerate_degree_square_class(x.class_level(wedges))
        sealed = _class_rows(result, wedges)
        assert [r[0] for r in sealed] == [x.profile_id(p) for p in members]
        for row in sealed:
            nb_cap, r18 = (
                int(str(_cell(row, "NB_TRIANGLE_CAP"))),
                int(str(_cell(row, "R18_TRIANGLE_CAP"))),
            )
            assert _cell(row, "TRIANGLE_CAP") == min(nb_cap, r18)
            assert _cell(row, "CAP_ORIGIN") in (x.CAP_NB, x.CAP_R18, x.CAP_TIE)
    summary = cast("list[dict[str, object]]", result["CLASS_SUMMARY"])
    assert all(item["PRIOR_CAP_SCAN_ROWS_NAMING_A_MEMBER"] == 0 for item in summary)
    assert sum(cast("dict[str, int]", result["CAP_ORIGIN_COUNTS"]).values()) == x.TOTAL_PROFILES
    members = x.nb.enumerate_degree_square_class(x.class_level(SMALL_CLASS))
    scan = x.w8.prior_cap_scan(start[0], start[1], members)
    assert scan["STATUS"] == "NO_PRIOR_CERTIFIED_CAP_FOR_ANY_MEMBER"
    forged = copy.deepcopy(start[1])
    forged.route_b.append({"PROFILE_ID": x.profile_id(members[3]), "CERTIFIED_TRIANGLE_CAP": 200})
    with pytest.raises(AssertionError, match="cap is unclassified"):
        x.w8.prior_cap_scan(start[0], forged, members)
    print("MUTATION_KILLED unknown-source-cap")
    listed = copy.deepcopy(start[0])
    listed.catalog[members[0]] = next(iter(start[0].catalog.values()))
    with pytest.raises(AssertionError, match="cap is unclassified"):
        x.w8.prior_cap_scan(listed, start[1], members)
    print("MUTATION_KILLED member-already-catalogued")

    def weakest(nb_cap: int, class_cap: int, _catalog_cap: int | None = None) -> int:
        return max(nb_cap, class_cap)

    monkeypatch.setattr(x.nb, "combined_triangle_cap", weakest)
    mixed = next(p for p in members if x.nb.profile_nb_cap(p)[2] != x.nb.r18_cap(p))
    with pytest.raises(AssertionError, match="not the strongest verified cap"):
        x.member_certificate(mixed, SMALL_CLASS)
    print("MUTATION_KILLED weaker-cap")


def test_all_t_envelope_and_integer_rounding(batch: Batch, monkeypatch: pytest.MonkeyPatch) -> None:
    result = batch[0]
    for wedges in x.CLASS_WEDGES:
        for row in _class_rows(result, wedges):
            cap = int(str(_cell(row, "TRIANGLE_CAP")))
            full = x.expand_row(wedges, row)
            assert full["T_RANGE"] == [22, cap] and full["TERM_COUNT"] == cap - 21
            assert _cell(row, "ARGMAX_TRIANGLES") == cap
            assert _cell(row, "ENVELOPE_STRICTLY_INCREASING_IN_T") is True
            s3, s4 = (
                int(str(_cell(row, "S3_AT_ARGMAX"))),
                int(str(_cell(row, "S4_FLOOR_AT_ARGMAX"))),
            )
            assert s4 % 7 == 0  # 448, 679, 231 and 112 are multiples of 7, so 4 * S4 / 7 is exact
            exact = x.K20_S1 - x.K20_S2 + s3 - Fraction(4 * s4, 7)
            assert exact.denominator == 1
            assert _cell(row, "ALL_T_MAX_BOUND") == x.w8.ceil_fraction(exact)
    assert (x.w8.ceil_fraction(Fraction(-7, 2)), x.w8.floor_fraction(Fraction(-7, 2))) == (-3, -4)
    profile = x.decode_profile(BATCH_MAX_PROFILE)
    assert x.member_certificate(profile, 807)["ALL_T_MAX_BOUND"] == BATCH_MAX
    original = x.r32.route_b_envelope

    def cap_only(profile: x.DegreeProfile, cap: int, base: int) -> list[x.w8.Term]:
        return original(profile, cap, base)[-1:]

    monkeypatch.setattr(x.r32, "route_b_envelope", cap_only)
    with pytest.raises(AssertionError, match="does not cover every t"):
        x.member_certificate(profile, 807)
    print("MUTATION_KILLED cap-only-envelope")
    monkeypatch.undo()

    def off_by_one(profile: x.DegreeProfile, cap: int, base: int) -> list[x.w8.Term]:
        return [(t, b - 1, k, c, w, s) for t, b, k, c, w, s in original(profile, cap, base)]

    monkeypatch.setattr(x.r32, "route_b_envelope", off_by_one)
    with pytest.raises(AssertionError, match="integer rounding disagrees"):
        x.member_certificate(profile, 807)
    print("MUTATION_KILLED bound-off-by-one")
    monkeypatch.undo()
    monkeypatch.setattr(x.w8, "ceil_fraction", x.w8.floor_fraction)
    with pytest.raises(AssertionError, match="integer rounding disagrees"):
        x.member_certificate(profile, 807)
    print("MUTATION_KILLED k4-floor-instead-of-ceiling")


def test_k4_quartet_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = x.decode_profile(BATCH_MAX_PROFILE)
    assert x.r32.K4_WEIGHTS == {x.r32.WITH_TRIPLE: 448, x.r32.WITHOUT_TRIPLE: 679}
    heavier = {x.r32.WITH_TRIPLE: 448, x.r32.WITHOUT_TRIPLE: 680}
    monkeypatch.setattr(x.r32, "K4_WEIGHTS", heavier)
    with pytest.raises(AssertionError, match="K4 quartet weights changed"):
        x.member_certificate(profile, 807)
    print("MUTATION_KILLED k4-weight-heavy")
    monkeypatch.undo()
    monkeypatch.setattr(x.r30, "k4_quartet_weights", lambda: heavier)
    with pytest.raises(AssertionError, match="K4 quartet weights changed"):
        x.member_certificate(profile, 807)
    print("MUTATION_KILLED k4-weight-source")


def test_witness_soundness(start: Start, monkeypatch: pytest.MonkeyPatch) -> None:
    report = x.w8.witness_nb_soundness(start[1].witness)
    assert report["STATUS"] == "PASS"
    assert report["REALIZED_TRIANGLES"] == x.nb.WITNESS_TRIANGLES
    assert int(str(report["NB_ROUTE_B_ALL_T_BOUND"])) >= x.WITNESS_UNION
    assert x.overlap_wedge_count(x.WITNESS_PROFILE) == 816 > x.HIGH_W

    def tight(_degrees: object) -> tuple[int, int, int]:
        return (0, 0, x.nb.WITNESS_TRIANGLES - 1)

    monkeypatch.setattr(x.nb, "profile_nb_cap", tight)
    with pytest.raises(AssertionError, match="NB cap fails on the realized witness"):
        x.w8.witness_nb_soundness(start[1].witness)
    print("MUTATION_KILLED witness-nb-cap")
    monkeypatch.undo()

    def lowered(_profile: x.DegreeProfile, cap: int, _base: int) -> list[x.w8.Term]:
        return [(t, 0, 0, 0, 0, 0) for t in range(22, cap + 1)]

    monkeypatch.setattr(x.r32, "route_b_envelope", lowered)
    monkeypatch.setattr(x.w8, "exact_route_b_terms", lowered)
    with pytest.raises(AssertionError, match="Route B fell below the realized witness"):
        x.member_certificate(x.WITNESS_PROFILE, 816)
    print("MUTATION_KILLED witness-route-b")


def test_frontier_ledger_and_partition(
    start: Start, batch: Batch, plateau: x.PlateauFrontier, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = batch[1]
    census = x.census_by_wedges()
    assert (len(census), min(census), max(census)) == (64, 774, 837)
    assert x.ledger_universe_check(final, census, x.LOW_W)["LEDGERED"] == 4_635
    assert x.ledger_universe_check(start[0], census, 808)["LEDGERED"] == 2_075
    coverage = x.frontier_below(final, census)
    assert coverage["UNRESOLVED_PROFILES"] == 197 and coverage["COARSE_AT_W_MAX"] == NEXT_BOUND
    assert x.profile_id(cast("x.DegreeProfile", final.cursor)) == NEXT_PROFILE
    missing = copy.deepcopy(final)
    del missing.bounds[x.nb.enumerate_degree_square_class(x.class_level(SMALL_CLASS))[5]]
    with pytest.raises(AssertionError, match="ledger is not exactly the admissible classes"):
        x.ledger_universe_check(missing, census, x.LOW_W)
    print("MUTATION_KILLED ledger-profile-lost")
    extra = copy.deepcopy(final)
    following = x.nb.enumerate_degree_square_class(x.class_level(785))[1]
    extra.bounds[following] = 0
    with pytest.raises(AssertionError, match="ledger is not exactly the admissible classes"):
        x.ledger_universe_check(extra, census, x.LOW_W)
    print("MUTATION_KILLED ledger-extra-profile")
    skipped = copy.deepcopy(final)
    skipped.cursor = following
    with pytest.raises(AssertionError, match="not the first W=785 profile"):
        x.frontier_below(skipped, census)
    print("MUTATION_KILLED skipped-next-cursor")
    formula = x.coarse_at

    def bumped(wedges: int) -> int:
        return formula(wedges) + (10**6 if wedges == 774 else 0)

    monkeypatch.setattr(x, "coarse_at", bumped)
    with pytest.raises(AssertionError, match="unresolved profile exceeds the cursor coarse"):
        x.frontier_below(final, census)
    print("MUTATION_KILLED coarse-dominance")
    monkeypatch.undo()
    fresh = copy.deepcopy(start[0])
    cursor_class = x.nb.enumerate_degree_square_class(x.class_level(807))
    assert fresh.cursor == cursor_class[0]
    certificates = [x.member_certificate(p, 807) for p in cursor_class]
    nxt = x.install_class(fresh, plateau, 807, certificates)
    assert x.class_completeness(fresh, 807, nxt)["STATUS"] == "PASS"
    assert fresh.cursor_bound == x.coarse_at(806)
    wrong = x.nb.enumerate_degree_square_class(x.class_level(806))[1]
    with pytest.raises(AssertionError, match="not the first unresolved profile"):
        x.class_completeness(fresh, 807, wrong)
    print("MUTATION_KILLED skipped-class-cursor")
    far = x.nb.enumerate_degree_square_class(x.class_level(805))[0]
    with pytest.raises(AssertionError, match="not the adjacent lower square-sum class"):
        x.class_completeness(fresh, 807, far)
    print("MUTATION_KILLED non-adjacent-class")
    jumped = replace(plateau, next_profile=far, next_bound=x.coarse_at(805))
    with pytest.raises(AssertionError, match="class after W=807 is not W=806"):
        x.install_class(copy.deepcopy(start[0]), jumped, 807, certificates)
    print("MUTATION_KILLED plateau-jumps-a-class")
    wrong_bound = replace(plateau, next_bound=x.coarse_at(806) - 1)
    with pytest.raises(AssertionError, match="next cursor coarse envelope disagrees"):
        x.install_class(copy.deepcopy(start[0]), wrong_bound, 807, certificates)
    print("MUTATION_KILLED next-bound-mismatch")
    reopened = copy.deepcopy(fresh)
    del reopened.bounds[cursor_class[0]]
    with pytest.raises(AssertionError, match="W=807 profile is unresolved"):
        x.class_completeness(reopened, 807, nxt)
    print("MUTATION_KILLED class-reopened")
    collide = copy.deepcopy(start[0])
    collide.bounds[cursor_class[2]] = 0
    with pytest.raises(AssertionError, match="collides with the ledger"):
        x.install_class(collide, plateau, 807, certificates)
    print("MUTATION_KILLED ledger-collision")


def test_sealed_result_tamper_detection(batch: Batch, monkeypatch: pytest.MonkeyPatch) -> None:
    result = batch[0]
    wedges = SMALL_CLASS
    clean = _sealed_class(result, wedges)
    assert x.audit_class(wedges, clean) == x.CLASS_COUNTS[wedges]

    def tamper_row(index: int, column: str, value: object) -> dict[str, object]:
        sealed = copy.deepcopy(clean)
        stored = cast("list[list[object]]", sealed["CERTIFICATES"])
        stored[index][x.ROW_COLUMNS.index(column)] = value
        return sealed

    bound = cast("int", _cell(_class_rows(result, wedges)[4], "ALL_T_MAX_BOUND"))
    cap = cast("int", _cell(_class_rows(result, wedges)[4], "TRIANGLE_CAP"))
    other_id = _cell(_class_rows(result, wedges)[5], "PROFILE_ID")
    cases: list[tuple[str, dict[str, object]]] = [
        ("bound-lowered", tamper_row(4, "ALL_T_MAX_BOUND", bound - 1)),
        ("bound-raised", tamper_row(4, "ALL_T_MAX_BOUND", bound + 1)),
        ("triangle-cap-raised", tamper_row(4, "TRIANGLE_CAP", cap + 1)),
        ("triangle-cap-lowered", tamper_row(4, "TRIANGLE_CAP", cap - 1)),
        ("nb-cap", tamper_row(4, "NB_TRIANGLE_CAP", cap + 7)),
        ("floor", tamper_row(4, "NB_OPEN_WEDGE_FLOOR", 0)),
        ("origin", tamper_row(4, "CAP_ORIGIN", x.CAP_R18)),
        ("s3", tamper_row(4, "S3_AT_ARGMAX", 1)),
        ("s4", tamper_row(4, "S4_FLOOR_AT_ARGMAX", 0)),
        ("a-max", tamper_row(4, "A_MAX", 0)),
        ("argmax", tamper_row(4, "ARGMAX_TRIANGLES", cap - 1)),
        ("monotone-flag", tamper_row(4, "ENVELOPE_STRICTLY_INCREASING_IN_T", False)),
        ("profile-id", tamper_row(4, "PROFILE_ID", other_id)),
    ]
    for name, sealed in cases:
        with pytest.raises(AssertionError):
            x.audit_class(wedges, sealed)
        print(f"MUTATION_KILLED sealed-{name}")
    dropped = copy.deepcopy(clean)
    del cast("list[object]", dropped["CERTIFICATES"])[7]
    with pytest.raises(AssertionError, match="rows are not the exact class in order"):
        x.audit_class(wedges, dropped)
    print("MUTATION_KILLED sealed-row-dropped")
    swapped = copy.deepcopy(clean)
    stored_rows = cast("list[object]", swapped["CERTIFICATES"])
    stored_rows[1], stored_rows[2] = stored_rows[2], stored_rows[1]
    with pytest.raises(AssertionError, match="rows are not the exact class in order"):
        x.audit_class(wedges, swapped)
    print("MUTATION_KILLED sealed-rows-swapped")
    for key, value in (
        ("CLASS_MAX", cast("int", clean["CLASS_MAX"]) - 1),
        ("CLASS_MAX_PROFILE_IDS", ["44444444444444444444"]),
        ("PROFILE_COUNT", x.CLASS_COUNTS[wedges] - 1),
        ("COARSE_FAMILY_UPPER_BOUND", x.coarse_at(wedges) + 1),
        ("CAP_ORIGIN_COUNTS", {x.CAP_NB: x.CLASS_COUNTS[wedges]}),
        ("W", wedges + 1),
    ):
        header = copy.deepcopy(clean)
        header[key] = value
        with pytest.raises(AssertionError, match=r"class (header|summary) is wrong"):
            x.audit_class(wedges, header)
        print(f"MUTATION_KILLED sealed-header-{key.lower()}")

    def skip_rows(_wedges: int, _class_row: object) -> int:
        return 0

    monkeypatch.setattr(x, "audit_class", skip_rows)
    for key, value in (
        ("PROFILES_CERTIFIED", x.TOTAL_PROFILES - 1),
        ("CLASSES_PROCESSED", 21),
        ("BATCH_CLASS_MAX", BATCH_MAX - 1),
        ("BATCH_CLASS_MAX_W", 806),
    ):
        forged = copy.deepcopy(result)
        forged[key] = value
        with pytest.raises(AssertionError, match=r"batch totals are wrong"):
            x.audit_sealed_result(forged)
        print(f"MUTATION_KILLED sealed-total-{key.lower()}")
    missing = copy.deepcopy(result)
    del cast("dict[str, object]", missing["W_CLASSES"])["800"]
    with pytest.raises(AssertionError, match=r"class set is not exactly W=807\.\.786"):
        x.audit_sealed_result(missing)
    print("MUTATION_KILLED sealed-class-missing")
    extra = copy.deepcopy(result)
    cast("dict[str, object]", extra["W_CLASSES"])["785"] = {}
    with pytest.raises(AssertionError, match=r"class set is not exactly W=807\.\.786"):
        x.audit_sealed_result(extra)
    print("MUTATION_KILLED sealed-class-extra")
    narrowed = copy.deepcopy(result)
    narrowed["CERTIFICATE_COLUMNS"] = list(x.ROW_COLUMNS[:-1])
    with pytest.raises(AssertionError, match="certificate columns changed"):
        x.audit_sealed_result(narrowed)
    print("MUTATION_KILLED sealed-columns")


def test_authority_and_provenance_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    provenance = x.module_provenance()
    assert len(provenance) == len(x.PROVENANCE_MODULES) == 6
    sealed, digest = x.w808_authority()
    assert digest == x.W808_SHA256 and sealed["FINAL_BOUND_OWNER_IDS"] == [x.START_CURSOR_ID]
    monkeypatch.setattr(x, "PROVENANCE_MODULES", (x,))
    with pytest.raises(AssertionError, match="not committed at the base"):
        x.module_provenance()
    print("MUTATION_KILLED uncommitted-source")
    monkeypatch.undo()
    monkeypatch.setattr(x, "W808_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="sealed W808 fingerprint changed"):
        x.w808_authority()
    print("MUTATION_KILLED w808-digest")
    monkeypatch.undo()
    monkeypatch.setattr(x, "START_BOUND", x.START_BOUND + 1)
    with pytest.raises(AssertionError, match="W808 authority mismatch: FINAL_FAMILY_UPPER_BOUND"):
        x.w808_authority()
    print("MUTATION_KILLED w808-start-bound")
    monkeypatch.undo()
    monkeypatch.setattr(x, "BASE_TREE", "0" * 40)
    with pytest.raises(AssertionError, match="the base tree changed"):
        x.w808_authority()
    print("MUTATION_KILLED base-tree")
    monkeypatch.undo()
    monkeypatch.setattr(x, "UNLEDGERED_IDS_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="unledgered top identities changed"):
        x.unledgered_cross_check(x.census_by_wedges(), set())
    print("MUTATION_KILLED unledgered-identities")


def test_w808_replay_must_match_sealed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = x.w8.certify_w808

    def drifted(
        chase: x.Chase, authorities: x.CapAuthorities, deadline: float
    ) -> dict[str, object]:
        out = original(chase, authorities, deadline)
        out["W808_CLASS_MAX"] = x.integer(out["W808_CLASS_MAX"]) + 1
        return out

    monkeypatch.setattr(x.w8, "certify_w808", drifted)
    with pytest.raises(AssertionError, match="W808 replay diverged from the sealed W808 result"):
        x.start_chase(monotonic() + 900)
    print("MUTATION_KILLED w808-replay-drift")


def _forbid_solvers(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a solver or outcome enumeration was called")

    monkeypatch.setattr(x.r28, "bounded_batch", forbidden)
    monkeypatch.setattr(x.r28, "solve_group", forbidden)
    monkeypatch.setattr(x.r30, "evaluate_portfolio", forbidden)
    monkeypatch.setattr(r13, "degree_class_open_wedge_relaxation", forbidden)
    monkeypatch.setattr(r25, "degree_class_open_wedge_relaxation", forbidden)


def test_render_is_deterministic_and_round_trips(monkeypatch: pytest.MonkeyPatch) -> None:
    sample: dict[str, object] = {"b": [1, 2], "a": {"z": None, "y": [[1, "x"], [2, "y"]]}, "c": []}
    assert x.render(sample) == x.render(copy.deepcopy(sample))
    assert json.loads(x.render(sample)) == sample
    assert x.render({"k": [[1, 2], [3, 4]]}) == '{\n  "k": [\n    [1, 2],\n    [3, 4]\n  ]\n}'

    def forged_render(_value: object, _level: int = 0) -> str:
        return '{"TASK_ID": "forged"}'

    monkeypatch.setattr(x, "render", forged_render)
    with pytest.raises(AssertionError, match="does not round-trip"):
        x.write_result({"TASK_ID": x.TASK_ID})
    print("MUTATION_KILLED renderer-drift")


def test_batch_replay_matches_and_solvers_stay_idle(
    start: Start, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_solvers(monkeypatch)
    deadline = monotonic() + 900
    first_chase = copy.deepcopy(start[0])
    first = x.certify_batch(first_chase, start[1], deadline)
    second = x.certify_batch(copy.deepcopy(start[0]), start[1], deadline)
    assert x.nb.same_result(first, second)
    digest = x.write_result(first)
    loaded = json.loads(x.result_path().read_text(encoding="utf-8"))
    assert x.nb.same_result(loaded, first)
    assert x.write_result(second) == digest
    assert hashlib.sha256(x.result_path().read_bytes()).hexdigest() == digest
    assert x.audit_sealed_result(loaded) == {
        "STATUS": "PASS",
        "ROWS_AUDITED": x.TOTAL_PROFILES,
        "BATCH_CLASS_MAX": BATCH_MAX,
    }
    assert first["TASK_STATUS"] == x.SUCCESS_A
    assert (first["CLASSES_PROCESSED"], first["PROFILES_CERTIFIED"]) == (22, 2_560)
    assert (first["HIGHEST_CERTIFIED_W"], first["LOWEST_CERTIFIED_W"]) == (807, 786)
    summary = cast("list[dict[str, object]]", first["CLASS_SUMMARY"])
    assert {int(str(item["W"])): item["CLASS_MAX"] for item in summary} == CLASS_MAXIMA
    assert all(item["PROFILE_COUNT"] == item["CERTIFIED_COUNT"] for item in summary)
    assert first["BATCH_CLASS_MAX"] == BATCH_MAX and first["BATCH_CLASS_MAX_W"] == 807
    assert first["BATCH_CLASS_MAX_PROFILE_IDS"] == [BATCH_MAX_PROFILE]
    assert first["PRE_EXISTING_RESOLVED_MAX"] == first["RESOLVED_LEDGER_MAX"] == FAMILY_BOUND
    assert BATCH_MAX < FAMILY_BOUND
    assert (first["NEXT_FRONTIER_W"], first["NEXT_FRONTIER_BOUND"]) == (785, NEXT_BOUND)
    assert first["NEXT_FRONTIER_PROFILE"] == NEXT_PROFILE
    assert first["NEXT_FRONTIER_MATCHES_REFERENCE"] is True
    assert first["FINAL_FAMILY_UPPER_BOUND"] == first["FAMILY_UPPER_BOUND"] == FAMILY_BOUND
    assert first["FINAL_OWNER_TYPE"] == "RESOLVED_LEDGER"
    assert first["FINAL_BOUND_OWNER_IDS"] == FAMILY_OWNERS
    assert first["NEXT_COMPETING_RESOLVED_BOUND"] == NEXT_COMPETING
    assert first["START_FAMILY_BOUND"] == x.START_BOUND == 313_551_160
    assert (first["CURRENT_INCUMBENT"], first["REMAINING_GAP"]) == (313_263_888, REMAINING_GAP)
    assert first["FINAL_LEDGER_COUNT"] == x.START_LEDGER_COUNT + 2_560 == 4_635
    assert first["FINAL_LEDGER_SHA256"] == FINAL_LEDGER_SHA256
    assert first["WITNESS_SOUNDNESS_STATUS"] == "PASS"
    assert first["ALL_T_CERTIFICATE_STATUS"] == "PASS_EXACT_RATIONAL_REDERIVATION_EVERY_T"
    cross = cast("dict[str, object]", first["UNLEDGERED_TOP_CROSS_CHECK"])
    assert cross["PROFILE_COUNT"] == 12 and cross["W_VALUES"] == [835, 836, 837]
    assert cross["CLOSED_FORM_MAX"] == UNLEDGERED_MAX
    assert cross["CLOSED_FORM_MAX_PROFILE_IDS"] == [UNLEDGERED_MAX_PROFILE]
    assert first["FINAL_FAMILY_UPPER_BOUND_WITH_UNLEDGERED_TOP_CLOSED_FORM"] == UNLEDGERED_MAX
    assert first["UNLEDGERED_TOP_EXPOSURE"] == UNLEDGERED_MAX - FAMILY_BOUND
    assert (first["SOLVER_CALLS"], first["OUTCOME_ENUMERATIONS"]) == (0, 0)
    assert (first["NEW_HEAVY_SOLVER_STARTED"], first["PRODUCTION_MUTATION"]) == ("NO", "NONE")
    for profile, cert in first_chase.catalog.items():
        if cert.source_result != x.RESULT_FILENAME:
            continue
        label, _, index = cert.source_row.partition("_CERTIFICATES[")
        sealed_row = _class_rows(loaded, int(label[1:]))[int(index[:-1])]
        assert sealed_row[0] == x.profile_id(profile)
        assert _cell(sealed_row, "ALL_T_MAX_BOUND") == cert.bound == first_chase.bounds[profile]
        assert cert.triangle_cap == _cell(sealed_row, "TRIANGLE_CAP")
    assert sum(c.source_result == x.RESULT_FILENAME for c in first_chase.catalog.values()) == 2_560

    def broken_family(_chase: object) -> tuple[int, tuple[()]]:
        return (0, ())

    monkeypatch.setattr(x.r28, "family_state", broken_family)
    with pytest.raises(AssertionError, match="family recompute disagreement"):
        x.nb.assert_family_agreement(copy.deepcopy(start[0]))
    print("MUTATION_KILLED family-recompute")
    print(
        "CERTIFIED"
        f" classes={first['CLASSES_PROCESSED']}"
        f" profiles={first['PROFILES_CERTIFIED']}"
        f" batch_max={first['BATCH_CLASS_MAX']}"
        f" next={first['NEXT_FRONTIER_PROFILE']}@{first['NEXT_FRONTIER_BOUND']}"
        f" family={first['FINAL_FAMILY_UPPER_BOUND']}"
        f" gap={first['REMAINING_GAP']}"
    )
