"""Checks for the exact structural S4 certificate of the STS(13) profile at t=270."""

from __future__ import annotations

import copy
import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import replace
from itertools import combinations
from pathlib import Path

import pytest

from lottolab.research import b649_k20_min_s2_sts13_isolation_s4_certificate_r1 as x

SOURCE = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1732]"
ROW = x.chase.Row(313_402_304, 270, 112, SOURCE)
OWNER = "66666555555311100000"
NEXT = "66655555555440000000"
Blocks = list[tuple[int, ...]]
Supports = Sequence[x.split.Support]


def cyclic_sts13() -> Blocks:
    base = ((0, 1, 4), (0, 2, 7))
    return [tuple(sorted((v + s) % 13 for v in b)) for b in base for s in range(13)]


def pasch_count(blocks: Blocks) -> int:
    count = 0
    for quad in combinations(blocks, 4):
        points = [v for b in quad for v in b]
        if len(set(points)) == 6 and all(points.count(v) == 2 for v in points):
            count += 1
    return count


def pasch_switch(blocks: Blocks) -> Blocks:
    """Trade the first quadrilateral xyz,xuv,wyu,wzv for xyu,xzv,wyz,wuv."""

    for quad in combinations(blocks, 4):
        points = [v for b in quad for v in b]
        if len(set(points)) != 6 or any(points.count(v) != 2 for v in points):
            continue
        first, *rest = quad
        x0 = first[0]
        b2 = next(b for b in rest if x0 in b)
        y, z = (v for v in first if v != x0)
        u, v = (p for p in b2 if p != x0)
        b3 = next(b for b in rest if b != b2 and y in b)
        if u not in b3:
            u, v = v, u
        w = next(p for p in b3 if p not in (y, u))
        new = [(x0, y, u), (x0, z, v), (w, y, z), (w, u, v)]
        kept = [b for b in blocks if b not in quad]
        return sorted([*kept, *(tuple(sorted(b)) for b in new)])
    raise AssertionError("no Pasch configuration")


def realization(blocks: Blocks, point: int) -> tuple[list[x.split.Support], list[x.split.Support]]:
    """STS(13) minus one point on tickets 0..11, plus the unique K8-e side."""

    label = {v: i for i, v in enumerate(p for p in range(13) if p != point)}
    triples = [tuple(sorted(label[v] for v in b)) for b in blocks if point not in b]
    triples += [(12, 13, 14), (15, 16, 17)]
    shadow = x.split.edges_of(triples)
    pairs = [e for e in combinations(range(12), 2) if e not in shadow]
    pairs += [e for e in combinations(range(12, 20), 2) if e not in shadow and e != (18, 19)]
    return triples, pairs


def components(adj: x.Adjacency) -> list[set[int]]:
    out: list[set[int]] = []
    for v in range(len(adj)):
        if not any(v in c for c in out):
            comp, frontier = {v}, {v}
            while frontier:
                frontier = {y for f in frontier for y in adj[f]} - comp
                comp |= frontier
            out.append(comp)
    return out


def test_lemma1_injection_on_random_graphs() -> None:
    rng = random.Random(20261010)
    checked = 0
    for _ in range(240):
        n = rng.randint(5, 12)
        density = rng.uniform(0.15, 0.85)
        edges = [e for e in combinations(range(n), 2) if rng.random() < density]
        adj = x.adjacency(n, edges)
        total = len(x.open_wedges(adj))
        for a, b in combinations(range(n), 2):
            if b in adj[a] or not adj[a] & adj[b]:
                continue
            wedges = x.lemma1_wedges(adj, a, b)
            assert len(wedges) == len(adj[a]) + len(adj[b]) - len(adj[a] & adj[b]) <= total
            checked += 1
    assert checked > 1000
    star = x.adjacency(4, [(0, 1), (0, 2), (0, 3)])
    with pytest.raises(ValueError, match="nonadjacent pair"):
        x.lemma1_wedges(star, 0, 1)
    with pytest.raises(ValueError, match="nonadjacent pair"):
        x.lemma1_wedges(x.adjacency(4, [(0, 1), (2, 3)]), 0, 2)


def test_twin_endpoint_graphs_are_cliques_and_one_near_clique_exhaustive() -> None:
    n = 6
    pairs = list(combinations(range(n), 2))
    matched = 0
    for mask in range(1 << len(pairs)):
        adj = x.adjacency(n, [e for i, e in enumerate(pairs) if mask >> i & 1])
        ends = {(lo, hi) for _c, lo, hi in x.open_wedges(adj)}
        if ends != {(0, 1)}:
            continue
        matched += 1
        for comp in components(adj):
            missing = [(p, q) for p, q in combinations(sorted(comp), 2) if q not in adj[p]]
            assert missing == ([(0, 1)] if 0 in comp else [])
    # One near-clique K_m-e (m=3..6) plus any clique partition of the rest:
    # sum C(4,m-2)*Bell(6-m) = 4*5 + 6*2 + 4*1 + 1 = 37.
    assert matched == 37


def test_isolation_forces_k12_plus_k8_minus_e() -> None:
    iso = x.isolation(x.PROFILE, 270)
    assert (iso["W"], iso["OPEN_WEDGES"], iso["FEASIBLE_ENDPOINTS"]) == (816, 6, [[6, 6, 6]])
    assert iso["DEGREE_COUNTS"] == {"11": 12, "7": 6, "6": 2}
    assert (iso["NEAR_CLIQUE_ORDER"], iso["CLIQUE_ORDERS"]) == (8, [12])
    assert iso["STRUCTURE"] == "K12 + (K8-e)" and iso["STRUCTURE_TRIANGLES"] == 270
    adj = x.forced_graph(x.PROFILE, iso)
    assert [len(n) for n in adj] == [11] * 12 + [7] * 6 + [6] * 2
    assert sorted(len(c) for c in components(adj)) == [8, 12]
    assert x.open_wedges(adj) == [(v, 18, 19) for v in range(12, 18)]
    assert len(x.lemma1_wedges(adj, 18, 19)) == 6
    with pytest.raises(AssertionError, match="not forced"):
        x.isolation(x.PROFILE, 269)  # OW=9 admits endpoint degrees (6,6), (6,7), (7,7)
    with pytest.raises(AssertionError, match="not forced"):
        x.isolation(x.PROFILE, 271)  # OW=3 < 6 admits no open wedge at all
    with pytest.raises(AssertionError, match="at least one open wedge"):
        x.isolation(x.PROFILE, 272)
    # Each profile below has OW=6 and breaks exactly one later step of Lemma 2.
    with pytest.raises(AssertionError, match="unique twin pair"):
        x.isolation("55555555555531110000", 271)  # four degree-6 tickets
    with pytest.raises(AssertionError, match="near-clique interior"):
        x.isolation("55555555555421111100", 269)  # five degree-7 tickets, not six
    with pytest.raises(AssertionError, match="split into cliques"):
        x.isolation("66655555544411111100", 271)  # three degree-12 tickets cannot form K13


def test_label_supports_force_k4_a_d_and_s4() -> None:
    lab = x.labels(x.PROFILE, x.isolation(x.PROFILE, 270))
    assert lab["CLIQUE_TRIPLE_SUPPORTS"] == [20] and lab["NEAR_CLIQUE_TRIPLE_SUPPORTS"] == 2
    assert lab["COMPONENT_PAIR_LABELS"] == [6, 21]
    counts = (lab["K4_COUNT"], lab["TRIPLE_CONTAINING_K4_COUNT"], lab["DIAMOND_COUNT"])
    assert counts == (550, 190, 15)
    assert lab["STAR_COUNT"] == 2230 == 4 * 550 + 2 * 15
    assert lab["EXACT_S4"] == 679 * 360 + 448 * 190 + 112 * 15 == 331_240
    assert [x.table_weight(e, b) for e, b in ((6, 0), (6, 1), (5, 0), (5, 1), (4, 0))] == [
        679,
        448,
        112,
        0,
        0,
    ]


def test_every_sts13_point_deletion_has_the_structural_s4() -> None:
    iso = x.isolation(x.PROFILE, 270)
    cyclic = cyclic_sts13()
    noncyclic = pasch_switch(cyclic)
    assert (pasch_count(cyclic), pasch_count(noncyclic)) == (13, 8)
    seen = x.witness(*realization(cyclic, 0), iso)
    assert seen["QUARTET_CLASSES"] == {
        "1E0T": 66, "2E0T": 1854, "3E0T": 2176, "3E1T": 184,
        "5E0T": 15, "6E0T": 360, "6E1T": 190,
    }  # fmt: skip
    assert sum(x.integer(n) for n in x.object_row(seen["QUARTET_CLASSES"]).values()) == 4845
    assert seen["DP_PROFILE_COUNT"] == 13
    assert x.witness(*x.split.witness_supports("STS13"), iso) == seen
    for point in range(13):
        other = x.witness(*realization(noncyclic, point), iso)
        assert (other["S4_CLASS_DP"], other["S4_DECOMPOSITION"]) == (331_240, 331_240)
        assert other["DECOMPOSITION"] == [360, 190, 15]


def test_witness_and_structure_must_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    real = x.witness

    def drifted(triples: Supports, pairs: Supports, iso: Mapping[str, object]) -> dict[str, object]:
        seen = real(triples, pairs, iso)
        return {**seen, "S4_CLASS_DP": x.integer(seen["S4_CLASS_DP"]) + 7}

    monkeypatch.setattr(x, "witness", drifted)
    with pytest.raises(AssertionError, match="witness S4 differs"):
        x.certificate(ROW)

    def recount(triples: Supports, pairs: Supports, iso: Mapping[str, object]) -> dict[str, object]:
        return {**real(triples, pairs, iso), "DECOMPOSITION": [361, 189, 15]}

    monkeypatch.setattr(x, "witness", recount)
    with pytest.raises(AssertionError, match="quartet counts differ"):
        x.certificate(ROW)


def test_t270_adoption_keeps_cap_and_lower_terms() -> None:
    lab = x.labels(x.PROFILE, x.isolation(x.PROFILE, 270))
    out = x.adoption(ROW, lab)
    old = x.split.route_b_terms(x.split.profile_values(x.PROFILE), 270, 112)
    terms = x.rows(out["ALL_T_TERMS"])
    assert terms[:-1] == [list(t) for t in old[:-1]] and len(terms) == 249
    assert old[-1] == (270, 313_402_304, 544, 190, 325_486, 5_198_256)
    assert terms[-1] == [270, 313_399_016, 550, 190, 331_240, 5_198_256]
    assert out["T270_NEW_BOUND"] == 308_390_040 + 5_198_256 - 4 * 331_240 // 7
    assert (out["LOWER_T_MAX_BOUND"], out["FULL_PROFILE_BOUND"]) == (313_392_760, 313_399_016)
    assert (out["TRIANGLE_CAP"], out["CAP_AUTHORITY"], out["S4_BASE"]) == (270, SOURCE, 112)
    with pytest.raises(AssertionError, match="cap authority changed"):
        x.adoption(replace(ROW, cap=271), lab)
    with pytest.raises(AssertionError, match="does not reproduce"):
        x.adoption(replace(ROW, bound=ROW.bound - 1), lab)
    with pytest.raises(AssertionError, match="below the proved floor"):
        x.adoption(ROW, {**lab, "EXACT_S4": 325_479})
    with pytest.raises(AssertionError, match="floor premises"):
        x.adoption(ROW, {**lab, "K4_COUNT": 543})


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("LABEL_SUPPORTS", "K4_COUNT"), 551),
        (("LABEL_SUPPORTS", "TRIPLE_CONTAINING_K4_COUNT"), 180),
        (("LABEL_SUPPORTS", "DIAMOND_COUNT"), 14),
        (("LABEL_SUPPORTS", "EXACT_S4"), 331_247),
        (("GRAPH_ISOLATION", "CLIQUE_ORDERS"), [11]),
        (("WITNESS", "S4_CLASS_DP"), 325_486),
        (("ADOPTION", "T270_NEW_BOUND"), 313_399_015),
        (("ADOPTION", "FULL_PROFILE_BOUND"), 313_392_760),
        (("STATUS",), "FAIL"),
    ],
)
def test_tampered_certificate_rejected(path: Sequence[str], value: object) -> None:
    cert = x.certificate(ROW)
    x.verify_certificate(cert, ROW)
    forged = copy.deepcopy(cert)
    target = forged
    for key in path[:-1]:
        target = x.object_row(target[key])
    target[path[-1]] = value
    with pytest.raises(AssertionError, match="certificate rejected"):
        x.verify_certificate(forged, ROW)
    lower = copy.deepcopy(cert)
    first = x.rows(x.rows(x.object_row(lower["ADOPTION"])["ALL_T_TERMS"])[0])
    first[1] = x.integer(first[1]) + 1
    with pytest.raises(AssertionError, match="certificate rejected"):
        x.verify_certificate(lower, ROW)


@pytest.fixture(scope="module")
def authority() -> x.chase.Authority:
    return x.chase.load_authority()


@pytest.fixture(scope="module")
def derived(authority: x.chase.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def test_family_recomputed_from_base_with_complete_coverage(
    authority: x.chase.Authority, derived: dict[str, object]
) -> None:
    base = x.pinned_base()
    ledger = x.base_ledger(authority, base)
    assert ledger[x.PROFILE] == ROW and x.rows_digest(ledger) == base["FINAL_RESOLVED_ROWS_SHA256"]
    assert (derived["K4_COUNT"], derived["TRIPLE_CONTAINING_K4_COUNT"]) == (550, 190)
    assert (derived["DIAMOND_COUNT"], derived["EXACT_S4"]) == (15, 331_240)
    assert (derived["T270_OLD_BOUND"], derived["T270_NEW_BOUND"]) == (313_402_304, 313_399_016)
    assert derived["FULL_PROFILE_BOUND"] == 313_399_016
    assert derived["FINAL_FAMILY_UB_FROM_BASE"] == 313_404_008
    assert derived["FINAL_OWNER_IDS"] == [OWNER] and derived["MOTIF_T264_RESULT_INCLUDED"] is False
    assert derived["NEXT_COMPETING_BOUND"] == 313_401_852
    assert derived["NEXT_COMPETING_IDS"] == [NEXT]
    assert derived["REMAINING_GAP"] == 140_120 and derived["CURRENT_INCUMBENT"] == 313_263_888
    covered = x.object_row(derived["COVERAGE"])
    assert covered["ADMISSIBLE_PROFILE_COUNT"] == 4844 and covered["UNCOVERED_PROFILE_COUNT"] == 0
    assert (covered["RESOLVED_ROW_COUNT"], covered["UNDER_CURSOR_PROFILE_COUNT"]) == (4647, 197)
    assert derived["FINAL_RESOLVED_ROWS_SHA256"] != base["FINAL_RESOLVED_ROWS_SHA256"]
    updated, _fam = x.family(authority, ledger, 313_399_016)
    assert {p for p in updated if updated[p] != ledger[p]} == {x.PROFILE}
    assert updated[x.PROFILE].cap == 270 and updated[x.PROFILE].s4_base == 112
    smaller = dict(ledger)
    del smaller[NEXT]
    with pytest.raises(AssertionError, match="coverage changed"):
        x.family(authority, smaller, 313_399_016)


def test_base_identity_and_tampered_inputs_rejected(
    authority: x.chase.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = x.pinned_base()
    forged = copy.deepcopy(base)
    forged["FINAL_RESOLVED_ROWS_SHA256"] = "0" * 64
    with pytest.raises(AssertionError, match="row digest"):
        x.base_ledger(authority, forged)
    forged = copy.deepcopy(base)
    x.object_row(x.rows(forged["CERTIFICATES"])[0])["ALL_T_MAX_BOUND"] = 313_351_011
    with pytest.raises(AssertionError, match="envelope changed"):
        x.base_ledger(authority, forged)
    twice = x.rows(base["CERTIFICATES"])[:1] * 2
    with pytest.raises(AssertionError, match="does not start from the replay"):
        x.base_ledger(authority, base | {"CERTIFICATES": twice})
    monkeypatch.setattr(x, "BASE_RESULT_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="digest mismatch"):
        x.pinned_base()


def test_result_file_and_source_identity(derived: dict[str, object]) -> None:
    source = hashlib.sha256(Path(x.__file__).read_bytes()).hexdigest()
    assert derived["SOURCE_SHA256"] == source and derived["BASE_HEAD"] == x.BASE_HEAD
    provenance = x.object_row(derived["MODULE_PROVENANCE"])
    assert "src/lottolab/research/b649_k20_min_s2_higher_order_closure_r2.py" in provenance
    assert "src/lottolab/research/b649_k20_min_s2_split_cap_current_owner_chase_r1.py" in provenance
    assert (derived["SOLVER_CALLS"], derived["OUTCOME_ENUMERATIONS"]) == (0, 0)
    assert x.RESULT_PATH.read_text(encoding="utf-8") == x.render(derived)
