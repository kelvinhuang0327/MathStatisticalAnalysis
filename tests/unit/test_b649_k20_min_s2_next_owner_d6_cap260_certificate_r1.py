"""Deterministic theorem counts, disjointness, authority and exact R32 envelope."""

from __future__ import annotations

import sys
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, product
from math import ceil, comb, floor

import pytest

from lottolab.research import b649_k20_min_s2_next_owner_d6_cap260_certificate_r1 as x

ROW = x.current.Row(313_401_180, 265, 112, "test")


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    # Abort at the forbidden entry points, even if a replay regresses to solving.
    with pytest.MonkeyPatch.context() as patch:

        def forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("solver or family chase is forbidden")

        for module, name in (
            (x.current, "chase"),
            (x.current.prior.r28, "support_union_model"),
            (x.current.prior.r28, "solve_group"),
        ):
            patch.setattr(module, name, forbidden)
        derived = x.compute_result()
    assert not any(name.startswith("ortools") for name in sys.modules)
    return derived


def test_all_counting_obligations_and_necessary_parameter_extrema() -> None:
    a = x.verify_arithmetic()
    assert [
        a[k]
        for k in (
            "INACTIVE_DOUBLE_ENDS",
            "INACTIVE_INTERNAL_DOUBLE_MAX",
            "M_MIN",
            "M_MAX",
            "D6_MISSING_ACTIVE_NEIGHBOURS",
            "PER_VERTEX_MIN",
            "OPEN_WEDGES_MIN",
            "W",
            "T_MAX",
        )
    ] == [36, 15, 6, 18, 1, 12, 48, 830, 260]
    counts: list[int] = []
    for m, d in product(range(6, 19, 2), range(2, 7)):
        for mixed_at_u in range(7 - d):
            category_a, category_b = x.family_counts(m, d, mixed_at_u)
            # Independently subtract nonedges meeting v or u from all active nonedges.
            active_non_edges = comb(14, 2) - (3 * 22 + (18 - m) // 2)
            missing_at_u = 13 - (6 + d - mixed_at_u)
            assert category_a == active_non_edges - (1 + missing_at_u - 1)
            assert category_b == m - mixed_at_u
            assert category_a + category_b >= 3 * d - 3 + 3 * m // 2
            counts.append(category_a + category_b)
    assert len(counts) == 105 and min(counts) == 12
    assert (830 - 48) // 3 == 260 and 830 - 3 * 261 == 47 < 48
    assert a["NECESSARY_PARAMETER_CASES_CHECKED"] == 77


def test_eight_wedge_families_are_disjoint_by_structural_types() -> None:
    # Supersets of A_v and B_v suffice. B centres have a double label, so d<6.
    # This covers every missing-neighbour choice, including another d=6 vertex.
    families: list[set[tuple[int, tuple[int, int]]]] = []
    for v in range(4):
        active_pairs = combinations([a for a in range(14) if a != v], 2)
        families.append({(v, ends) for ends in active_pairs})
        families.append({(a, (v, i)) for a, i in product(range(4, 14), range(14, 20))})
    assert all(not a & b for a, b in combinations(families, 2))
    assert len(families[0].union(*families[1:])) == sum(map(len, families))


def test_exact_r32_profile_envelope_and_delta() -> None:
    cert = x.profile_certificate(ROW)
    assert cert["CURRENT_CERTIFIED_T_CAP"] == 265 and cert["PROVEN_T_CAP"] == 260
    assert cert["CURRENT_R32_PROFILE_BOUND"] == 313_401_180
    assert cert["NEW_R32_PROFILE_BOUND"] == 313_356_176
    assert cert["EXACT_PROFILE_DELTA"] == cert["BELOW_KNOWN_FOUR_ROW_OWNER_BOUND_BY"] == 45_004
    assert cert["S4_BASE"] == 112 and cert["A_MAX"] == 199
    assert cert["CURRENT_ARGMAX_TERM"] == [265, 313_401_180, 498, 199, 292_173, 5_178_096]
    assert cert["TERM_COUNT"] == 239 and cert["ARGMAX_TRIANGLES"] == 260
    observed = x.current.rows(cert["ALL_T_TERMS"])
    expected: list[list[int]] = []
    # Re-derive all floors and ceilings independently in exact rationals.
    for t in range(22, 261):
        k4 = max(0, ceil(Fraction(2342 - 10 * (830 - 3 * t), 4)))
        contained = min(k4, 199)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * 830 + 11872 * (t - 22) - 30800
        bound = 372228640 - 63838600 + s3 - floor(Fraction(4 * s4, 7))
        expected.append([t, bound, k4, contained, s4, s3])
    assert observed == expected
    assert expected[-1] == [260, 313_356_176, 461, 199, 267_050, 5_118_736]
    assert max(term[1] for term in expected) == 313_356_176


def test_pinned_ledger_source_theorem_and_stronger_existing_proof(
    result: dict[str, object],
) -> None:
    authority = x.current.object_row(result["CURRENT_AUTHORITY"])
    assert authority["LEDGER_DIGEST"] == x.LEDGER_DIGEST
    assert authority["RESOLVED_ROW_COUNT"] == 4647
    assert authority["STORED_TARGET_CAP_AT_MOST_260"] is False
    assert authority["CURRENT_ROW_SOURCE"] == (
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[882]"
    )
    stronger = x.current.object_row(authority["EXISTING_GENERAL_SPLIT_THEOREM"])
    assert stronger["TRIANGLE_CAP"] == 238
    assert stronger["BRANCH_COUNTS"] == {x.current.BRANCH_A: 620}
    assert stronger["ADOPTED_IN_PINNED_LEDGER"] is False
    assert stronger["APPLIED_IN_THIS_D6_RESULT"] is False
    provenance = x.current.object_row(result["THEOREM_PROVENANCE"])
    assert provenance["ORIGINAL_PROFILE"] != x.TARGET_PROFILE
    assert provenance["ORIGINAL_W"] == 831
    assert provenance["MODEL_FUNCTION_AST_IDENTICAL"] is True
    assert result["THEOREM_TRANSFER"] == result["MODEL_SEMANTICS"] == "PASS"


def test_fail_closed_scope_parameters_provenance_and_stale_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="only the target"):
        x.verify_arithmetic("66665555555322000000")
    for m, d, mixed in [(4, 2, 4), (7, 2, 4), (20, 2, 4), (6, 1, 5), (6, 2, 5)]:
        with pytest.raises(ValueError, match="premises"):
            x.family_counts(m, d, mixed)
    with pytest.raises(AssertionError, match="does not reproduce"):
        x.profile_certificate(replace(ROW, bound=ROW.bound - 1))
    monkeypatch.setattr(x, "THEOREM_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="theorem digest"):
        x.theorem_provenance()
    monkeypatch.undo()
    monkeypatch.setattr(x, "MODEL_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="model or scope"):
        x.theorem_provenance()


def test_result_reproduction_and_forbidden_work_guards(result: dict[str, object]) -> None:
    assert x.RESULT_PATH.read_text(encoding="utf-8") == x.render(result)
    assert result["PROOF_SHA256"] == x.digest(x.PROOF.encode())
    assert result["POTENTIAL_FAMILY_EFFECT"] == "NOT_VERIFIED"
    for key in (
        "EXISTING_CERTIFICATES_MUTATED",
        "RUN1_MUTATED",
        "HEAVY_SOLVER_STARTED",
        "REMOTE_WRITE",
    ):
        assert result[key] == "NO"
    for key in ("SOLVER_CALLS", "SUPPORT_MODELS_BUILT", "PORTFOLIO_ENUMERATIONS"):
        assert result[key] == 0
