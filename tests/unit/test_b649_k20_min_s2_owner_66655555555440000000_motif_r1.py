"""Focused local incidence, authority, rounding, preservation and soundness checks."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from fractions import Fraction
from itertools import combinations

import pytest

from lottolab.research import b649_k20_min_s2_owner_66655555555440000000_motif_r1 as x


@pytest.fixture(scope="module")
def proof() -> dict[str, object]:
    result = x.pinned_result(x.r32.CAP_SOURCE_RESULT, x.r32.R30_SHA256)
    return x.object_row(x.rows(result["GROUP_ATTEMPTS"])[x.CAP_INDEX])


@pytest.fixture(scope="module")
def old_row() -> x.base.Row:
    return x.base.Row(
        313_401_852,
        264,
        1680,
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1200]",
    )


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return x.compute_result()


def test_local_graph_support_identities_and_exact_event_weights() -> None:
    checked = x.local_identity_check()
    assert checked["STATUS"] == "PASS" and checked["LOCAL_CASES"] == 96
    table = x.rows(checked["TABLE"])
    assert len({tuple(x.rows(row)[:2]) for row in table}) == 96
    assert {x.rows(row)[-1] for row in table} == {679, 448, 112, 0}
    assert x.WEIGHTS == {"K": 679, "A": 448, "D": 112, "ZERO": 0}
    assert x.r32.r30.k4_quartet_weights() == x.r32.K4_WEIGHTS
    k4 = set(combinations(range(4), 2))
    assert x.local_weight(k4, None) == 679
    assert x.local_weight(k4, (0, 1, 2)) == 448
    diamond = k4 - {(2, 3)}
    assert x.local_weight(diamond, None) == 112
    assert x.local_weight(diamond, (0, 1, 2)) == 0
    with pytest.raises(ValueError, match="induce a triangle"):
        x.local_weight(set(), (0, 1, 2))


def test_motif_elimination_and_nonnegative_dropped_terms() -> None:
    # Independent coefficient probes, including all three nonzero dropped terms.
    for m in (
        x.Motifs(k=1),
        x.Motifs(d=1),
        x.Motifs(p=1),
        x.Motifs(c=1),
        x.Motifs(k=1, a=1),
        x.Motifs(d=1, d1=1),
        x.Motifs(p=1, p1=1),
    ):
        assert 4 * m.k == m.j - m.r + m.p + 2 * m.c
        assert m.s4 == 231 * m.k + 112 * m.j - 56 * m.r - 77 * m.b + m.dropped
        assert m.dropped >= 0
    assert (x.Motifs(c=1).dropped, x.Motifs(d1=1).dropped, x.Motifs(p1=1).dropped) == (56, 42, 77)


def test_degree_constants_and_integer_k4_ceiling() -> None:
    assert x.PROFILE == (6,) * 3 + (5,) * 8 + (4,) * 2 + (0,) * 7
    assert [6 + d for d in x.PROFILE] == [12] * 3 + [11] * 8 + [10] * 2 + [6] * 7
    floor = x.degree_floor(x.PROFILE, 264)
    assert floor == {
        "W": 833,
        "J": 2360,
        "B": 604,
        "OW": 41,
        "R_MAX": 410,
        "K4_BOUND": 488,
        "S4_CONSTANT": 194852,
        "S4_CERTIFIED_FLOOR": 307580,
    }
    assert Fraction(487) < Fraction(2360 - 410, 4) <= Fraction(488)
    with pytest.raises(ValueError, match="negative open-wedge"):
        x.degree_floor(x.PROFILE, 278)


def test_t264_credit_bound_and_every_lower_t_preserved(
    old_row: x.base.Row,
    proof: dict[str, object],
) -> None:
    c = x.owner_certificate(old_row, proof)
    assert c["OLD_ROUTE_B_S4_FLOOR"] == 284921
    assert (c["OLD_ROUTE_B_CREDIT"], c["NEW_ROUTE_B_CREDIT"], c["EXTRA_CREDIT"]) == (
        162812,
        175760,
        12948,
    )
    assert (
        c["T264_OLD_BOUND"],
        c["T264_NEW_BOUND"],
        c["T263_RETAINED_MAX"],
        c["CERTIFIED_OWNER_BOUND"],
    ) == (313401852, 313388904, 313393084, 313393084)
    old = x.split.route_b_terms(x.PROFILE, old_row.cap, old_row.s4_base)
    new = x.rows(c["ALL_T_TERMS"])
    assert len(new) == 243 and [x.rows(t)[0] for t in new] == list(range(22, 265))
    assert new[:-1] == [list(t) for t in old[:-1]]
    assert c["RETAINED_TERMS_SHA256"] == x.digest(old[:-1])
    assert max(t[1] for t in old[:-1]) == 313393084
    assert new[-1] == [264, 313388904, 488, None, 307580, 5174624]
    exact = x.event.K20_S1 - x.event.K20_S2 + 5174624 - Fraction(4 * 307580, 7)
    assert exact == 313388904
    assert Fraction(4 * 284921, 7) == Fraction(1139684, 7)
    # Exercise a nonintegral credit independently of the quartet weights.
    for s4 in (307579, 307581):
        s3, rounded = x.base.r20.bound_from_cap(x.PROFILE, 264, s4)
        rational = x.event.K20_S1 - x.event.K20_S2 + s3 - Fraction(4 * s4, 7)
        assert 0 < rounded - rational < 1
        assert rounded == x.event.K20_S1 - x.event.K20_S2 + s3 - (4 * s4) // 7
    x.verify_certificate(c, old_row, proof)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("STATUS", "FEASIBLE"),
        ("STATUS", "UNKNOWN"),
        ("STATUS", "TIMEOUT"),
        ("ATTEMPT_INDEX", 2980),
        ("PROFILE_IDS", ["66666555555311100000"]),
        ("ROUTE", "OTHER"),
        ("CERTIFICATE_KIND", "CP_SAT_FEASIBLE"),
        ("TARGET_TRIANGLE_CAP", 263),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 265),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 264),
        ("OPEN_WEDGE_CEILING_REFUTED", 41),
        ("CERTIFIED_OPEN_WEDGE_LOWER_BOUND", 41),
        ("WEDGE_COUNT", 834),
        ("TARGET_TRIANGLE_CAP", 264.0),
    ],
)
def test_cap_source_tampering_rejected(
    key: str, value: object, proof: dict[str, object], old_row: x.base.Row
) -> None:
    with pytest.raises(AssertionError, match="cap-source"):
        x.owner_certificate(old_row, {**proof, key: value})


@pytest.mark.parametrize(
    "key",
    [
        "K4_BOUND",
        "S4_CERTIFIED_FLOOR",
        "B",
        "OW",
        "R_MAX",
        "NEW_ROUTE_B_CREDIT",
        "T264_NEW_BOUND",
        "T263_RETAINED_MAX",
        "CERTIFIED_OWNER_BOUND",
        "EXTRA_CREDIT",
    ],
)
def test_tampered_arithmetic_rejected(
    key: str, proof: dict[str, object], old_row: x.base.Row
) -> None:
    cert = x.owner_certificate(old_row, proof)
    cert[key] = x.integer(cert[key]) + 1
    with pytest.raises(AssertionError, match="tampered owner"):
        x.verify_certificate(cert, old_row, proof)


def test_tampered_lower_t_and_wrong_ledger_rejected(
    proof: dict[str, object], old_row: x.base.Row
) -> None:
    cert = copy.deepcopy(x.owner_certificate(old_row, proof))
    term = x.rows(x.rows(cert["ALL_T_TERMS"])[0])
    term[1] = x.integer(term[1]) - 1
    with pytest.raises(AssertionError, match="tampered owner"):
        x.verify_certificate(cert, old_row, proof)
    with pytest.raises(AssertionError, match="cap-source"):
        x.owner_certificate(replace(old_row, cap=263), proof)
    with pytest.raises(AssertionError, match="base ledger"):
        x.owner_certificate(replace(old_row, bound=313401851), proof)


def test_float_certificate_rejected(proof: dict[str, object], old_row: x.base.Row) -> None:
    cert = x.owner_certificate(old_row, proof)
    cert["K4_BOUND"] = 488.0
    with pytest.raises(AssertionError, match="tampered owner"):
        x.verify_certificate(cert, old_row, proof)


def test_actual_base_complete_family_and_4844_coverage(result: dict[str, object]) -> None:
    auth = x.load_authority()
    assert len(auth.ledger) == 4647
    assert auth.ledger[x.PROFILE_ID].bound == 313401852
    assert result["COMPLETE_FAMILY_BOUND_FROM_BASE"] == 313404008
    assert result["OTHER_COMMITTED_PROFILE_ROWS_UNCHANGED"] == 4646
    assert result["OTHER_ROWS_SHA256"] == x.digest(
        {p: r.bound for p, r in auth.ledger.items() if p != x.PROFILE_ID}
    )
    c = x.object_row(result["COVERAGE"])
    assert (
        c["ADMISSIBLE_PROFILE_COUNT"],
        c["RESOLVED_ROW_COUNT"],
        c["UNDER_CURSOR_PROFILE_COUNT"],
        c["UNCOVERED_PROFILE_COUNT"],
    ) == (4844, 4647, 197, 0)
    recompute = x.object_row(result["FAMILY_RECOMPUTATION"])
    assert recompute["FINAL_OWNER_IDS"] == ["66666555555311100000"]
    assert recompute["NEXT_COMPETING_BOUND"] == 313402304
    assert auth.ledger["55555555555511111100"].bound == 313402304
    assert len(x.object_row(result["MODULE_PROVENANCE"])) > 20
    with pytest.raises(AssertionError, match="digest"):
        x.pinned_result(x.base.RESULT_FILENAME, "0" * 64)


def test_legal_realization_soundness_and_invalid_support_rejected(
    result: dict[str, object],
) -> None:
    witnesses = x.object_row(result["LEGAL_REALIZATIONS"])
    assert result["WITNESS_SOUNDNESS_STATUS"] == "PASS"
    owner = x.object_row(witnesses["OWNER"])
    assert owner["PROFILE_ID"] == x.PROFILE_ID and x.integer(owner["TRIANGLES"]) <= 264
    assert x.object_row(witnesses["P2"])["TRIANGLES"] == 250
    assert x.object_row(witnesses["STS13"])["TRIANGLES"] == 270
    sealed = x.pinned_result(x.r32.CAP_SOURCE_RESULT, x.r32.R30_SHA256)
    sts = x.object_row(witnesses["STS13"])
    assert (
        sts["EXACT_S4_FROM_PINNED_LOCAL_TABLE"]
        == x.object_row(sealed["SOUNDNESS_WITNESS"])["EXACT_S4"]
    )
    for raw in witnesses.values():
        w = x.object_row(raw)
        assert w["STATUS"] == "PASS"
        f = x.object_row(w["DEGREE_FLOOR"])
        assert x.integer(w["R"]) <= x.integer(f["R_MAX"])
        assert x.integer(w["EXACT_S4_FROM_PINNED_LOCAL_TABLE"]) >= x.integer(
            f["S4_CERTIFIED_FLOOR"]
        )
    triples, pairs = x.split.witness_supports("P2")
    with pytest.raises(ValueError, match="reuse a core ticket pair"):
        x.realization_check(triples, ((triples[0][0], triples[0][1]), *pairs[1:]))


def test_immutable_result_reproduces_and_never_starts_forbidden_work(
    result: dict[str, object],
) -> None:
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == result["FULL_CENSUS_STARTED"] == "NO"
    assert (
        result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO" and result["PRODUCTION_MUTATION"] == "NONE"
    )
    x.verify_result(result)
    tampered = {**result, "COMPLETE_FAMILY_BOUND_FROM_BASE": 313401464}
    with pytest.raises(AssertionError, match="tampered immutable"):
        x.verify_result(tampered)
    tampered = copy.deepcopy(result)
    x.object_row(tampered["COVERAGE"])["ADMISSIBLE_PROFILE_COUNT"] = 4843
    with pytest.raises(AssertionError, match="tampered immutable"):
        x.verify_result(tampered)
    if x.RESULT_PATH.exists():
        assert x.object_row(json.loads(x.RESULT_PATH.read_text())) == result
        with pytest.raises(AssertionError, match="immutable result already exists"):
            x.main()
