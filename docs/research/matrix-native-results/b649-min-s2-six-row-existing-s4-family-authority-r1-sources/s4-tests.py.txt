"""Focused exact-owner, retained-certificate and complete-family correctness guards."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import ceil, comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_current_owner_motif_exact_refinement_r1 as x


@pytest.fixture(scope="module")
def authority() -> x.Authority:
    return x.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.Authority) -> dict[str, object]:
    return x.compute_result(authority)


def cap_proof(authority: x.Authority) -> dict[str, object]:
    return x.object_row(x.rows(authority.inherited.r30["GROUP_ATTEMPTS"])[x.CAP_INDEX])


def test_exact_source_and_complete_base_identity(authority: x.Authority) -> None:
    sealed = x.integration.pinned(x.BASE_HEAD, x.previous.RESULT_FILENAME, x.BASE_RESULT_SHA256)
    assert sealed == authority.sealed
    assert x.chase.git("rev-parse", f"{x.BASE_HEAD}^{{tree}}").decode().strip() == x.BASE_TREE
    assert len(authority.provenance) == 30
    assert x.previous.corrected_provenance() == sealed["MODULE_PROVENANCE"]
    name = Path(x.previous.__file__ or "").relative_to(x.chase.ROOT).as_posix()
    assert authority.provenance[name] == sealed["SOURCE_SHA256"]
    assert (
        hashlib.sha256(Path(x.previous.__file__ or "").read_bytes()).hexdigest()
        == (sealed["SOURCE_SHA256"])
    )
    assert (
        x.integration.family(authority.ledger, authority.inherited.inherited)
        == (sealed["FINAL_FAMILY"])
    )
    assert x.object_row(sealed["FINAL_FAMILY"])["OWNER_IDS"] == [x.OWNER_PROFILE]


def test_predecessor_source_tampering_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    path, original = Path(x.previous.__file__ or "").resolve(), Path.read_bytes

    def changed(p: Path) -> bytes:
        return original(p) + (b"\n# changed predecessor\n" if p == path else b"")

    x.load_authority.cache_clear()
    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(AssertionError, match="predecessor source identity"):
        x.load_authority()


def test_current_owner_cap_and_load_bearing_identity(authority: x.Authority) -> None:
    row, proof = authority.ledger[x.OWNER_PROFILE], cap_proof(authority)
    x.check_cap(row, proof)
    assert (row.cap, row.bound, row.s4_base) == (264, 313401076, 112)
    assert row.source.endswith("NB_CERTIFICATES[497]")
    assert (proof["ATTEMPT_INDEX"], proof["REFUTED_GRAPH_TRIANGLE_COUNT"]) == (2779, 265)
    for bad in (replace(row, cap=263), replace(row, cap=264.0), replace(row, source="other")):
        with pytest.raises(AssertionError, match="cap-source identity"):
            x.owner_certificate(bad, proof)
    with pytest.raises(AssertionError, match="sealed ledger"):
        x.owner_certificate(replace(row, bound=row.bound - 1), proof)


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("ATTEMPT_INDEX", 2781),
        ("PROFILE_IDS", ["66665555555421000000"]),
        ("STATUS", "UNKNOWN"),
        ("CERTIFICATE_KIND", "CP_SAT_FEASIBLE"),
        ("ROUTE", "OTHER"),
        ("WEDGE_COUNT", 834),
        ("TARGET_TRIANGLE_CAP", 264.0),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 264),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 265),
        ("OPEN_WEDGE_CEILING_REFUTED", 39),
        ("CERTIFIED_OPEN_WEDGE_LOWER_BOUND", 38),
    ],
)
def test_cap_source_substitutions_fail_closed(
    key: str, bad: object, authority: x.Authority
) -> None:
    with pytest.raises(AssertionError, match="cap-source identity"):
        x.owner_certificate(authority.ledger[x.OWNER_PROFILE], {**cap_proof(authority), key: bad})


def test_minimum_s2_applicability_and_degree_incidence(authority: x.Authority) -> None:
    p = x.split.profile_values(x.OWNER_PROFILE)
    assert p == (6,) * 5 + (5,) * 5 + (4,) * 2 + (1,) * 3 + (0,) * 5
    g = [6 + d for d in p]
    assert g == [12] * 5 + [11] * 5 + [10] * 2 + [7] * 3 + [6] * 5
    assert sum(p) == 66 and sum(g) == 186
    witness = authority.ledger[x.OWNER_PROFILE].realization
    assert witness is not None
    triples, pairs = witness
    assert len(triples) == 22 and len(pairs) == 27
    x.chase.prior.r5.validate_k20_support_realization(triples, pairs, p)
    with pytest.raises(ValueError, match="22 triple"):
        x.chase.prior.r5.validate_k20_support_realization(triples[:-1], pairs, p)
    with pytest.raises(ValueError):
        x.chase.prior.r5.validate_k20_support_realization(triples, [*pairs[:-1], pairs[0]], p)
    with pytest.raises(ValueError, match="degree sequence"):
        x.chase.prior.r5.validate_k20_support_realization(triples, pairs, p[::-1])
    floor = x.motif.degree_floor(p, 264)
    assert floor == {
        "W": 833,
        "J": 2370,
        "B": 604,
        "OW": 41,
        "R_MAX": 410,
        "K4_BOUND": 490,
        "S4_CONSTANT": 195972,
        "S4_CERTIFIED_FLOOR": 309162,
    }
    assert floor["W"] == sum(comb(v, 2) for v in g)
    assert floor["J"] == sum(comb(v, 3) for v in g)
    assert floor["B"] == sum(d * (v - 2) for d, v in zip(p, g, strict=True))
    assert floor["OW"] == floor["W"] - 3 * 264
    assert floor["K4_BOUND"] == ceil(Fraction(floor["J"] - floor["R_MAX"], 4))
    incidence = x.integration.incidence_floor(p, 264)
    assert (incidence["A_MAX"], incidence["S4_FLOOR"]) == (201, 309183)
    # Independent rational minimization over the allowed wedge incidence load.
    values = [
        231 * ceil(Fraction(2370 - load, 4)) - 63 * 201 + 56 * (2 * 2370 - load - 604)
        for load in range(411)
    ]
    assert min(values) == values[-1] == 309183


def test_canonical_primitive_and_dropped_terms() -> None:
    local = x.motif.local_identity_check()
    assert local["LOCAL_CASES"] == 96 and local["STATUS"] == "PASS"
    assert {x.rows(row)[-1] for row in x.rows(local["TABLE"])} == {0, 112, 448, 679}
    assert x.integration.incidence_identity_check()["LOCAL_CASES"] == 96
    edges = set(combinations(range(4), 2))
    assert x.motif.local_weight(edges, None) == 679
    assert x.motif.local_weight(edges, (0, 1, 2)) == 448
    assert x.motif.local_weight(edges - {(2, 3)}, None) == 112
    for m in (
        x.motif.Motifs(k=1),
        x.motif.Motifs(d=1),
        x.motif.Motifs(p=1),
        x.motif.Motifs(c=1),
        x.motif.Motifs(k=1, a=1),
        x.motif.Motifs(d=1, d1=1),
        x.motif.Motifs(p=1, p1=1),
    ):
        assert 4 * m.k == m.j - m.r + m.p + 2 * m.c
        assert m.b == 3 * m.a + 2 * m.d1 + m.p1
        assert m.dropped == 42 * m.d1 + 77 * m.p1 + 56 * m.c >= 0
        assert m.s4 == 231 * m.k + 112 * m.j - 56 * m.r - 77 * m.b + m.dropped


def assert_owner_envelope(authority: x.Authority) -> None:
    row = authority.ledger[x.OWNER_PROFILE]
    cert = x.owner_certificate(row, cap_proof(authority))
    assert tuple(
        cert[k]
        for k in (
            "LOAD_BEARING_T",
            "OLD_ROUTE_B_S4_FLOOR",
            "NEW_S4_FLOOR",
            "OLD_INTEGER_CREDIT",
            "NEW_INTEGER_CREDIT",
            "EXACT_ADDITIONAL_CREDIT",
            "CAP_OLD_BOUND",
            "CAP_NEW_BOUND",
            "RETAINED_LOWER_T_MAX",
            "CERTIFIED_PROFILE_BOUND",
        )
    ) == (264, 286279, 309183, 163588, 176676, 13088, 313401076, 313387988, 313391920, 313391920)
    old = x.split.route_b_terms(x.split.profile_values(x.OWNER_PROFILE), row.cap, row.s4_base)
    terms = [x.rows(term) for term in x.rows(cert["ALL_T_TERMS"])]
    assert terms[:-1] == [list(term) for term in old[:-1]]
    assert cert["RETAINED_TERMS_SHA256"] == x.digest(old[:-1])
    assert cert["NEW_S4_FLOOR"] == max(
        x.integer(cert["OLD_ROUTE_B_S4_FLOOR"]),
        x.integer(x.object_row(cert["DEGREE_FLOOR"])["S4_CERTIFIED_FLOOR"]),
        x.integer(x.object_row(cert["INCIDENCE_FLOOR"])["S4_FLOOR"]),
    )
    assert [term[0] for term in terms] == list(range(22, 265))
    for t, bound, _k, _a, s4, s3 in terms:
        rational = (
            x.motif.event.K20_S1
            - x.motif.event.K20_S2
            + x.integer(s3)
            - Fraction(4 * x.integer(s4), 7)
        )
        assert x.integer(bound) == ceil(rational)
        assert x.integer(s3) == 2800 * 833 + 11872 * (x.integer(t) - 22) - 30800


def test_all_t_equivalence_retention_and_exact_credit(authority: x.Authority) -> None:
    assert_owner_envelope(authority)


def test_stronger_sts13_floor_is_preserved(authority: x.Authority) -> None:
    cert = x.competitor_check(authority)
    assert (cert["EXISTING_S4_FLOOR"], cert["ADOPTED_S4_FLOOR"]) == (331240, 331240)
    assert x.object_row(cert["INCIDENCE_FLOOR"])["S4_FLOOR"] == 328510
    assert (cert["CERTIFIED_PROFILE_BOUND"], cert["EXACT_ADDITIONAL_CREDIT"]) == (313399016, 0)


def test_certificate_tampering_and_double_count_rejection(authority: x.Authority) -> None:
    row, proof = authority.ledger[x.OWNER_PROFILE], cap_proof(authority)
    cert = x.owner_certificate(row, proof)
    for key in ("NEW_S4_FLOOR", "EXACT_ADDITIONAL_CREDIT", "CERTIFIED_PROFILE_BOUND"):
        with pytest.raises(AssertionError, match="tampered current owner"):
            x.verify_certificate({**cert, key: x.integer(cert[key]) + 1}, row, proof)
    bad = copy.deepcopy(cert)
    bad["NEW_S4_FLOOR"] = x.integer(cert["NEW_S4_FLOOR"]) + x.integer(cert["OLD_ROUTE_B_S4_FLOOR"])
    with pytest.raises(AssertionError, match="tampered current owner"):
        x.verify_certificate(bad, row, proof)
    with pytest.raises(AssertionError, match="all-t coverage"):
        x.exact_terms(
            x.split.profile_values(x.OWNER_PROFILE), [x.rows(x.rows(cert["ALL_T_TERMS"])[-1])], 264
        )


def test_complete_family_max_coverage_and_one_row_changes(
    authority: x.Authority, result: dict[str, object]
) -> None:
    start, final = x.object_row(result["START_FAMILY"]), x.object_row(result["FINAL_FAMILY"])
    assert (start["FAMILY_UB"], start["OWNER_IDS"], start["NEXT_COMPETING_BOUND"]) == (
        313401076,
        [x.OWNER_PROFILE],
        313399016,
    )
    assert (final["FAMILY_UB"], final["OWNER_IDS"], final["REMAINING_GAP"]) == (
        313399016,
        [x.COMPETITOR_PROFILE],
        135128,
    )
    assert (final["NEXT_COMPETING_BOUND"], final["NEXT_COMPETING_IDS"]) == (
        313398920,
        ["66555555555540000000"],
    )
    assert (result["START_COMPLETE_FAMILY_UB"], result["FINAL_COMPLETE_FAMILY_UB"]) == (
        start["FAMILY_UB"],
        final["FAMILY_UB"],
    )
    assert result["FINAL_OWNER_IDS"] == final["OWNER_IDS"]
    coverage = x.object_row(final["COVERAGE"])
    assert tuple(
        coverage[k]
        for k in (
            "ADMISSIBLE_PROFILE_COUNT",
            "RESOLVED_ROW_COUNT",
            "UNDER_CURSOR_PROFILE_COUNT",
            "UNCOVERED_PROFILE_COUNT",
        )
    ) == (4844, 4647, 197, 0)
    assert start["COVERAGE"] == final["COVERAGE"]
    ledger = x.integration.install(authority.ledger, x.OWNER_PROFILE, 313391920, "test")
    assert x.integration.family(ledger, authority.inherited.inherited)["FAMILY_UB"] == 313399016
    assert {pid for pid in ledger if ledger[pid] != authority.ledger[pid]} == {x.OWNER_PROFILE}
    assert result["OTHER_PROFILE_ROWS_UNCHANGED"] == 4646
    assert result["OTHER_ROWS_SHA256"] == x.digest(
        {pid: r.bound for pid, r in authority.ledger.items() if pid != x.OWNER_PROFILE}
    )
    with pytest.raises(AssertionError, match="coverage changed"):
        x.integration.family(
            {pid: r for pid, r in ledger.items() if pid != x.COMPETITOR_PROFILE},
            authority.inherited.inherited,
        )
    with pytest.raises(AssertionError, match="strictly improve"):
        x.integration.install(ledger, x.OWNER_PROFILE, 313391920, "double")
    assert result["INHERITED_CERTIFICATES"] == authority.sealed["INHERITED_CERTIFICATES"]


def test_sts13_p2_canonical_and_owner_witness_soundness(result: dict[str, object]) -> None:
    seen = x.object_row(result["OWNER_SUPPORT_REALIZATION"])
    assert seen["PROFILE_ID"] == x.OWNER_PROFILE and seen["STATUS"] == "PASS"
    assert x.integer(seen["TRIANGLES"]) <= 264
    soundness = x.object_row(result["WITNESS_SOUNDNESS"])
    assert soundness["STATUS"] == "PASS"
    named = x.object_row(soundness["INCIDENCE_FLOOR_REALIZATIONS"])
    assert x.object_row(named["P2"])["TRIANGLES"] == 250
    assert (
        x.object_row(named["STS13"])["TRIANGLES"],
        x.object_row(named["STS13"])["EXACT_S4"],
    ) == (270, 331240)
    assert x.object_row(soundness["CANONICAL_WITNESS"])["INCUMBENT"] == 313263888
    assert result["SOLVER_CALLS"] == result["OUTCOME_ENUMERATIONS"] == 0
    assert result["NEW_HEAVY_SOLVER_STARTED"] == result["NEW_PROFILE_CENSUS_STARTED"] == "NO"


# Execute non-equivalent source mutations in memory; task and historical files stay intact.
MUTATIONS = {
    "add_overlapping_floors": (
        's4 = max(old_s4, degree["S4_CERTIFIED_FLOOR"], incidence["S4_FLOOR"])',
        's4 = old_s4 + incidence["S4_FLOOR"]',
    ),
    "replace_stronger_floor_with_base": (
        's4 = max(old_s4, degree["S4_CERTIFIED_FLOOR"], incidence["S4_FLOOR"])',
        "s4 = row.s4_base",
    ),
    "drop_lower_t_terms": ("terms = [*lower, (t, bound,", "terms = [(t, bound,"),
    "report_cap_as_profile_max": (
        '"CERTIFIED_PROFILE_BOUND": max(term[1] for term in terms)',
        '"CERTIFIED_PROFILE_BOUND": bound',
    ),
    "credit_without_existing_deduction": (
        "4 * s4 // 7 - 4 * old_s4 // 7",
        "4 * s4 // 7",
    ),
    "change_credit_coefficient": (
        '"NEW_INTEGER_CREDIT": 4 * s4 // 7',
        '"NEW_INTEGER_CREDIT": 3 * s4 // 7',
    ),
}


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_targeted_non_equivalent_mutations_are_killed(
    mutation: str, authority: x.Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert_owner_envelope(authority)
    old, new = MUTATIONS[mutation]
    source = inspect.getsource(x.owner_certificate)
    assert source.count(old) == 1
    namespace: dict[str, object] = dict(vars(x))
    exec(compile(source.replace(old, new), f"<mutation:{mutation}>", "exec"), namespace)
    mutant = cast(Callable[..., dict[str, object]], namespace["owner_certificate"])
    with monkeypatch.context() as patch:
        patch.setattr(x, "owner_certificate", mutant)
        with pytest.raises(AssertionError):
            assert_owner_envelope(authority)
    assert_owner_envelope(authority)


def test_machine_result_replay_and_tampering(
    result: dict[str, object], authority: x.Authority
) -> None:
    x.verify_result(result, authority)
    with pytest.raises(AssertionError, match="tampered immutable current-owner"):
        x.verify_result({**result, "FINAL_COMPLETE_FAMILY_UB": 313391920}, authority)
    if x.RESULT_PATH.exists():
        assert json.loads(x.RESULT_PATH.read_text()) == result
        with pytest.raises(AssertionError, match="immutable current-owner result already exists"):
            x.main()
