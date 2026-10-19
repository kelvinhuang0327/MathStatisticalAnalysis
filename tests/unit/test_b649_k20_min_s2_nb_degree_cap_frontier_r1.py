"""NB degree cap, certificate-source identity, the W=809 class, and the family replay."""

from __future__ import annotations

import copy
import json
from math import comb
from time import monotonic
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_class_dominance_or_descent_r13 as r13
from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25
from lottolab.research import b649_k20_min_s2_nb_degree_cap_frontier_r1 as x

Start = tuple[x.Chase, str, dict[str, object]]
CURSOR_BOUND = 313_136_772
W809_CLASS_MAX = 313_343_868
RESOLVED_MAX = 313_404_784
FAMILY_BOUND = 313_553_960
REMAINING_GAP = 290_072
NEXT_CURSOR = "66666652222222222221"


@pytest.fixture(scope="module")
def start() -> Start:
    return x.start_chase(monotonic() + 600)


@pytest.fixture(scope="module")
def authorities() -> x.CapAuthorities:
    return x.load_cap_authorities()


@pytest.fixture(scope="module")
def kinds(start: Start, authorities: x.CapAuthorities) -> dict[x.DegreeProfile, str]:
    return x.classify_ledger(start[0], authorities)


@pytest.fixture
def chase(start: Start) -> x.Chase:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 600
    return fresh


def test_floor_top_degree_order_and_ties() -> None:
    ordered = (2, 2, 1, 1)
    assert x.neighbourhood_capacity(ordered, 0) == 1
    assert x.neighbourhood_capacity(ordered, 1) == 1
    assert x.neighbourhood_capacity((3, 2, 2, 1), 0) == 2
    terms = x.nb_vertex_terms(ordered)
    for degree, capacity, closed, open_wedges in terms:
        assert 2 * closed <= capacity < 2 * closed + 2
        assert open_wedges == comb(degree, 2) - closed
    permuted = x.nb_vertex_terms((1, 2, 1, 2))
    assert sorted(terms) == sorted(permuted)
    triangle = x.graph_nb_rows([{1, 2}, {0, 2}, {0, 1}])
    assert len(triangle) == 3
    assert all(2 * inside <= capacity for _degree, inside, capacity in triangle)


def test_impossible_degree_sequences_are_rejected() -> None:
    with pytest.raises(ValueError, match="not graphical"):
        x.nb_triangle_cap((1, 1, 1))
    with pytest.raises(ValueError, match="not graphical"):
        x.graph_degree_list((2, 0, 0))
    with pytest.raises(ValueError, match="too few possible neighbours"):
        x.neighbourhood_capacity((1, 0), 0)


def test_cursor_closed_form_and_cap_minimum() -> None:
    row = x.cursor_certificate()
    assert row["PROFILE_ID"] == x.profile_id(x.CURSOR)
    assert int(str(row["NB_OPEN_WEDGE_FLOOR"])) >= 80
    assert int(str(row["NB_TRIANGLE_CAP"])) <= 243
    assert row["NB_OPEN_WEDGE_FLOOR"] == 80
    assert row["TRIANGLE_CAP"] == 243
    assert row["ALL_T_MAX_BOUND"] == CURSOR_BOUND
    assert row["ENVELOPE_STRICTLY_INCREASING_IN_T"] is True
    assert x.combined_triangle_cap(300, 268, 240) == 240
    assert x.combined_triangle_cap(300, 268, 270) == 268


def test_small_graphs_obey_the_nb_cap() -> None:
    report = x.small_graph_soundness()
    assert report["STATUS"] == "PASS"
    assert report["MAX_VERTICES"] == 6
    assert report["LABELLED_GRAPHS_CHECKED"] == 33_867


def test_catalog_sources_and_inherited_r10_scope(
    chase: x.Chase, authorities: x.CapAuthorities, kinds: dict[x.DegreeProfile, str]
) -> None:
    assert x.catalog_source_counts(chase, authorities) == {
        x.VERIFY_REFUTATION: 1_240,
        x.VERIFY_R18: 523,
        x.VERIFY_R25: 32,
    }
    scope = x.inherited_r10_scope(chase, authorities, kinds)
    profiles = cast(list[object], scope["PROFILES"])
    assert scope["STATUS"] == "PASS" and scope["CENSUS_REBUILT"] is False
    assert len(profiles) == 12
    assert {x.object_row(row)["CAP_SOURCE"] for row in profiles} <= {
        x.VERIFY_REFUTATION,
        x.VERIFY_R18,
        x.VERIFY_R25,
    }


def test_tampered_refutation_is_rejected(
    start: Start, authorities: x.CapAuthorities, kinds: dict[x.DegreeProfile, str]
) -> None:
    profile = next(item for item, kind in kinds.items() if kind == x.VERIFY_REFUTATION)
    cert = start[0].catalog[profile]
    status = copy.deepcopy(authorities)
    for proof in status.proofs:
        proof["STATUS"] = "FEASIBLE"
    with pytest.raises(AssertionError, match="SOURCE_PROOF_NOT_INFEASIBLE"):
        x.classify_catalog_source(profile, cert, status)
    print("MUTATION_KILLED proof-status")
    identity = copy.deepcopy(authorities)
    for proof in identity.proofs:
        proof["PROFILE_IDS"] = []
    with pytest.raises(AssertionError, match="SOURCE_PROOF_IDENTITY_MISMATCH"):
        x.classify_catalog_source(profile, cert, identity)
    print("MUTATION_KILLED proof-profile-ids")
    forged = copy.replace(cert, source_result=x.R30_RESULT, source_row="GROUP_ATTEMPTS[999999]")
    with pytest.raises(AssertionError, match="index out of range"):
        x.classify_catalog_source(profile, forged, authorities)
    print("MUTATION_KILLED source-row")


def test_tampered_r25_and_plateau_rows_are_rejected(
    start: Start, authorities: x.CapAuthorities, kinds: dict[x.DegreeProfile, str]
) -> None:
    pinned = next(item for item, kind in kinds.items() if kind == x.VERIFY_R25)
    cheap = copy.deepcopy(authorities)
    for row in cheap.cheap:
        x.object_row(row["R13_RELAXATION"])["SOLVER_STATUS"] = "FEASIBLE"
    with pytest.raises(AssertionError, match="not OPTIMAL"):
        x.classify_catalog_source(pinned, start[0].catalog[pinned], cheap)
    print("MUTATION_KILLED r25-status")
    missing = copy.deepcopy(authorities)
    for row in missing.plateaus:
        row["PLATEAU_PROFILE_IDS"] = []
    plateau_failures = 0
    for profile, kind in kinds.items():
        if kind != x.VERIFY_R18:
            continue
        try:
            x.classify_catalog_source(profile, start[0].catalog[profile], missing)
        except AssertionError as exc:
            assert "plateau certificate does not contain the profile" in str(exc)
            plateau_failures += 1
    assert plateau_failures >= 1
    print("MUTATION_KILLED plateau-profile-ids")
    wrong_cap = copy.deepcopy(authorities)
    for row in wrong_cap.plateaus:
        row["GRAPH_TRIANGLE_UPPER_BOUND"] = -1
    cap_failures = 0
    for profile, kind in kinds.items():
        if kind != x.VERIFY_R18:
            continue
        try:
            x.classify_catalog_source(profile, start[0].catalog[profile], wrong_cap)
        except AssertionError as exc:
            assert "plateau cap mismatch" in str(exc)
            cap_failures += 1
    assert cap_failures == plateau_failures
    print("MUTATION_KILLED plateau-cap")


def test_tampered_r19_digest_and_scope_fail_closed(
    chase: x.Chase,
    authorities: x.CapAuthorities,
    kinds: dict[x.DegreeProfile, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(x, "R19_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="sealed R19 fingerprint changed"):
        x.load_cap_authorities()
    print("MUTATION_KILLED r19-digest")
    census = copy.deepcopy(authorities)
    census.inherited["FULL_4850_PROFILE_CENSUS_REBUILT"] = True
    with pytest.raises(AssertionError, match="rebuilt a census"):
        x.inherited_r10_scope(chase, census, kinds)
    print("MUTATION_KILLED r10-census")


def _zero_floor(_degrees: object) -> int:
    return 0


def _zero_capacity(_degrees: object, _vertex: object) -> int:
    return 0


def test_cursor_floor_and_capacity_mutations_are_killed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(x, "nb_open_wedge_floor", _zero_floor)
    with pytest.raises(AssertionError, match="cursor NB regression"):
        x.cursor_certificate()
    print("MUTATION_KILLED cursor-open-wedge-floor")
    monkeypatch.setattr(x, "neighbourhood_capacity", _zero_capacity)
    with pytest.raises(ValueError, match="too few possible neighbours"):
        x.assert_nb_capacity(x.profile_degrees(x.CURSOR))
    print("MUTATION_KILLED neighbourhood-capacity")


def test_witness_floor_and_family_recompute_mutations(
    chase: x.Chase, authorities: x.CapAuthorities, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = x.witness_soundness(authorities.witness)
    assert report["STATUS"] == "PASS"
    assert report["EXACT_ANY_PRIZE_UNION"] == x.WITNESS_UNION
    assert int(str(report["ROUTE_B_BOUND_AT_REALIZED_CAP"])) >= x.WITNESS_UNION

    def undercut(_witness: object) -> dict[str, object]:
        return {
            "STATUS": "PASS",
            "EXACT_ANY_PRIZE_UNION": x.WITNESS_UNION,
            "ROUTE_B_BOUND_AT_REALIZED_CAP": x.WITNESS_UNION - 1,
        }

    monkeypatch.setattr(x.r32, "witness_route_b", undercut)
    with pytest.raises(AssertionError, match="fell below the realized witness portfolio"):
        x.witness_soundness(authorities.witness)
    print("MUTATION_KILLED witness-floor")
    def broken_family(_chase: object) -> tuple[int, tuple[()]]:
        return (0, ())

    monkeypatch.setattr(x.r28, "family_state", broken_family)
    with pytest.raises(AssertionError, match="family recompute disagreement"):
        x.assert_family_agreement(chase)
    print("MUTATION_KILLED family-recompute")


def test_weaker_route_b_does_not_replace_a_certificate(
    chase: x.Chase, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = {profile: (cert.source_row, cert.bound) for profile, cert in chase.catalog.items()}

    def weaker(profile: x.DegreeProfile, cap: int, base: int) -> list[x.Term]:
        current = chase.catalog[profile].bound
        coarse = x.coarse_profile_envelope(profile).family_upper_bound
        offered = current + 1 if current + 1 <= coarse else current
        return [(cap, offered, 0, 0, base, 0)]

    monkeypatch.setattr(x.r32, "route_b_envelope", weaker)
    adopted, retained = x.refine_resolved(chase)
    assert adopted == 0 and retained == x.LEDGER_COUNT
    after = {profile: (cert.source_row, cert.bound) for profile, cert in chase.catalog.items()}
    assert after == before
    print("MUTATION_KILLED weaker-route-b-retained")


def _forbid_solvers(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a solver or outcome enumeration was called")

    monkeypatch.setattr(x.r28, "bounded_batch", forbidden)
    monkeypatch.setattr(x.r28, "solve_group", forbidden)
    monkeypatch.setattr(x.r30, "evaluate_portfolio", forbidden)
    monkeypatch.setattr(r13, "degree_class_open_wedge_relaxation", forbidden)
    monkeypatch.setattr(r25, "degree_class_open_wedge_relaxation", forbidden)


def test_family_replay_matches_and_solvers_stay_idle(
    chase: x.Chase, authorities: x.CapAuthorities, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_solvers(monkeypatch)
    primitives = x.r28.canonical_primitive_preflight()
    assert primitives["STATUS"] == "PASS"
    deadline = monotonic() + 600
    first = x.certify_family(copy.deepcopy(chase), authorities, deadline)
    second = x.certify_family(copy.deepcopy(chase), authorities, deadline)
    assert x.same_result(first, second)
    digest = x.write_result(first)
    path = x.r28.repo_root() / x.RESULT_DIRECTORY / x.RESULT_FILENAME
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert x.same_result(loaded, first)
    assert x.write_result(second) == digest
    assert first["CURSOR_CERTIFIED_BOUND"] == CURSOR_BOUND
    assert first["W809_CLASS_COUNT"] == 133
    assert first["W809_CLASS_MAX"] == W809_CLASS_MAX
    assert first["RESOLVED_LEDGER_MAX"] == RESOLVED_MAX
    assert first["RESOLVED_LEDGER_MAX"] != x.TARGET_RESOLVED_MAX
    assert first["FINAL_FAMILY_UPPER_BOUND"] == first["FAMILY_UPPER_BOUND"] == FAMILY_BOUND
    assert first["REMAINING_GAP"] == REMAINING_GAP
    assert first["FINAL_OWNER_CLASS"] == NEXT_CURSOR
    assert first["NEXT_CURSOR_SQUARE_SUM"] == 290
    assert first["CAP_SOURCE_COUNTS"] == {
        x.VERIFY_REFUTATION: 1_240,
        x.VERIFY_R18: 523,
        x.VERIFY_R25: 32,
    }
    assert first["INHERITED_R10_SCOPE_STATUS"] == "PASS"
    assert first["NB_LEMMA_STATUS"] == "PROVED_CLOSED_FORM"
    assert first["CANONICAL_PRIMITIVE_STATUS"] == first["WITNESS_SOUNDNESS_STATUS"] == "PASS"
    assert (first["NEW_HEAVY_SOLVER_STARTED"], first["PRODUCTION_MUTATION"]) == ("NO", "NONE")
    assert (first["SOLVER_CALLS"], first["OUTCOME_ENUMERATIONS"], first["FULL_CENSUS_STARTED"]) == (
        0,
        0,
        "NO",
    )
    eligible = x.enumerate_degree_square_class(x.CURSOR_SQUARE_SUM)
    profile_ids = cast(list[object], first["W809_PROFILE_IDS"])
    assert profile_ids == list(map(x.profile_id, eligible))
    assert profile_ids[0] == x.profile_id(x.CURSOR)
    print(
        "CERTIFIED"
        f" cursor={first['CURSOR_CERTIFIED_BOUND']}"
        f" w809_max={first['W809_CLASS_MAX']}"
        f" w809_count={first['W809_CLASS_COUNT']}"
        f" resolved_max={first['RESOLVED_LEDGER_MAX']}"
        f" family={first['FINAL_FAMILY_UPPER_BOUND']}"
        f" gap={first['REMAINING_GAP']}"
        f" owner={first['FINAL_OWNER_CLASS']}"
    )
    print("MUTATION_KILLED solver-not-called")
