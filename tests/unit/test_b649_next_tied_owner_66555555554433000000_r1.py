"""Focused proof, complete finite relaxation, source and arithmetic checks."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations, product

import pytest

from lottolab.research import b649_next_tied_owner_66555555554433000000_r1 as cert


def test_profile_and_two_goodman_recounts() -> None:
    p = cert.premises()
    assert p["GOODMAN_CONSTANT"] == 290
    assert (p["CORE_COUNT"], p["ZERO_COUNT"]) == (14, 6)
    assert (p["DEGREE_SUM"], p["DEGREE_SQUARE_SUM"]) == (66, 322)


def test_enumeration_is_complete_without_graph_or_support_filters() -> None:
    # Independent labeled domains, then quotient by precisely the stated symmetries.
    five = {tuple(sorted(a)) for a in product(range(2), repeat=8)}
    four = {tuple(sorted(a)) for a in product(range(3), repeat=2)}
    three = {tuple(sorted(a)) for a in product(range(4), repeat=2)}
    zeros = {tuple(sorted(a)) for a in product(range(1, 7), repeat=6)}
    expected = {
        ((0, 0, *a, *b, *c), z)
        for a, b, c in product(five, four, three)
        for z in zeros
        if sum(a) + sum(b) + sum(c) == sum(z) and sum(z) % 2 == 0
    }
    actual = list(cert.relaxation_states())
    assert len(expected) == len(actual) == len(set(actual)) == 1507
    assert set(actual) == expected


def test_full_superset_maximum_and_analytic_fallback() -> None:
    proof = cert.finite_certificate()
    assert proof["PROOF_SCOPE"] == "FULL_PROFILE"
    assert proof["PROVED_T_CAP"] == 218
    assert proof["ANALYTIC_FALLBACK_CAP"] == 222
    assert len(cert.frozen.rows(proof["RELAXED_MAXIMIZERS"])) == 2
    assert proof["UNPROVED_ASSUMPTIONS"] == []
    assert proof["ATTAINMENT_OF_218"] == "NOT_ESTABLISHED"


def test_d3_terms_cannot_be_treated_as_nonpositive() -> None:
    # The older d>=4 argument would be invalid at this profile's d=3 vertices.
    assert 3 * (3 + 2 - 3) == 6 > 0
    assert max(s * (s + 3 - 3) for s in range(4)) == 9
    assert max(s * (s + 3 - 4) for s in range(3)) == 2


def test_generic_graph_identity_exhaustively_on_five_vertices() -> None:
    edges = list(combinations(range(5), 2))
    for mask in range(1 << len(edges)):
        graph = {e for i, e in enumerate(edges) if mask & (1 << i)}
        seen = cert.graph_identity((0, 1, 2), (3, 4), graph)
        assert seen["T_H"] == seen["WEIGHTED"] + seen["P"]
        assert seen["P"] >= 0


def test_remainder_includes_triangles_in_both_parts() -> None:
    seen = cert.graph_identity((0, 1, 2), (3, 4, 5), set())
    assert seen == {"T": 0, "T_H": 20, "P": 2, "WEIGHTED": 18}


def test_relaxed_equality_is_an_upper_bound_not_a_realizability_claim() -> None:
    sigma, zeta = (0,) * 12 + (3, 3), (1,) * 6
    assert cert.triangle_from_state(sigma, zeta, 0) == 218
    assert cert.triangle_from_state(sigma, zeta, 7) == 211


@pytest.mark.parametrize(
    ("sigma", "zeta", "remainder", "failure"),
    [
        ((0,) * 14, (0,) * 6, 0, "zero degree capacity"),
        ((0,) * 14, (6,) * 6, 0, "cross-edge balance"),
        ((0,) * 12 + (3, 3), (1,) * 5 + (7,), 0, "zero degree capacity"),
        ((0,) * 12 + (4, 2), (1,) * 6, 0, "core pair capacity"),
        ((0,) * 10 + (3, 0, 3, 0), (1,) * 6, 0, "core pair capacity"),
        ((0,) * 12 + (3, 3), (1,) * 6, -1, "negative remainder"),
        ((0,) * 11 + (1, 3, 3), (1,) * 5 + (2,), 0, "within-part edge parity"),
        ((0,) * 13, (1,) * 6, 0, "cross-degree dimensions"),
        ((0,) * 12 + (True, 3), (1,) * 6, 0, "core pair capacity"),
    ],
)
def test_load_bearing_premises_reject_invalid_states(
    sigma: tuple[int, ...], zeta: tuple[int, ...], remainder: int, failure: str
) -> None:
    with pytest.raises(AssertionError, match=failure):
        cert.triangle_from_state(sigma, zeta, remainder)


def test_removed_balance_and_zero_capacity_would_break_t218() -> None:
    assert cert.objective((0,) * 14, (0,) * 6) == 236 > 218
    assert cert.objective((0,) * 14, (6,) * 6) == 452 > 218


def test_pair_linearity_is_a_checked_premise() -> None:
    with pytest.raises(AssertionError, match="pair-linearity"):
        cert.validate_supports([(0, 1, 2)] * 22, [(3, 4)] * 27)
    with pytest.raises(AssertionError, match="support counts"):
        cert.validate_supports([], [])


def test_false_stronger_cap_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cert, "PROVED_CAP", 217)
    with pytest.raises(AssertionError, match="finite relaxation cap/count mismatch"):
        cert.finite_certificate()


def test_frozen_authority_and_full_ledger_row() -> None:
    source = cert.source_authority()
    assert source["FROZEN_HEAD_TREE"] == source["FROZEN_RESULT_SHA256_STATUS"] == "MATCH"
    assert source["COMPLETE_LEDGER_ROWS"] == 4647
    assert source["COMPLETE_LEDGER_FULL_SHA256"] == (
        "70e2c1bb28f223566cb54799fd1b325368b90d58c5fc5001cacfbba9d2996de6"
    )
    assert source["FROZEN_LEDGER_MUTATED"] is False
    assert source["SOURCE_LOCATOR"] == cert.SOURCE_LOCATOR
    assert source["RECORDED_REALIZATION"] is None
    assert source["NEXT_COMPETITOR"] == 313392128
    assert cert.object_row(source["SOURCE_ROW"])["cap"] == 266
    assert cert.object_row(source["PRIOR_ART"])["R21_USED_TO_SET_CLOSURE_BOUND"] is False


def test_negative_frozen_identity() -> None:
    raw = (cert.ROOT / cert.FROZEN_RESULT).read_bytes()
    cert.check_fingerprint(raw, cert.FROZEN_TREE)
    with pytest.raises(AssertionError, match="frozen result digest mismatch"):
        cert.check_fingerprint(raw + b" ", cert.FROZEN_TREE)
    with pytest.raises(AssertionError, match="frozen tree mismatch"):
        cert.check_fingerprint(raw, "0" * 40)


@pytest.mark.parametrize(
    "row",
    [
        cert.frozen.Row(313392232, 265, 112, cert.SOURCE_LOCATOR),
        cert.frozen.Row(313392232, 266, 0, cert.SOURCE_LOCATOR),
        cert.frozen.Row(313392128, 266, 112, cert.SOURCE_LOCATOR),
        cert.frozen.Row(313392232, 266, 112, "NB_CERTIFICATES[0]"),
    ],
)
def test_negative_source_row(row: cert.frozen.Row) -> None:
    with pytest.raises(AssertionError, match="source cap/S4/bound/locator mismatch"):
        cert.check_source(cert.PROFILE_ID, row)


def test_negative_source_profile() -> None:
    row = cert.frozen.Row(cert.OLD_BOUND, 266, 112, cert.SOURCE_LOCATOR)
    cert.check_source(cert.PROFILE_ID, replace(row))
    with pytest.raises(AssertionError, match="source profile mismatch"):
        cert.check_source("wrong-profile", row)


def test_old_target_and_new_all_t_route_b_envelopes() -> None:
    old, before = cert.route_b(266)
    target, expected = cert.route_b(265)
    new, after = cert.route_b(218)
    assert before["ARGMAX_TERM"] == [266, 313392232, 507, 195, 299208, 5173168]
    assert expected["ARGMAX_TERM"] == [265, 313383076, 500, 195, 294455, 5161296]
    assert after["ARGMAX_TERM"] == [218, 312955720, 147, 147, 65856, 4603312]
    assert new == old[:197] and target == old[:-1]
    assert len(old) == 245 and len(new) == 197
    assert after["EXACT_RATIONAL_CHECK"] == after["ROUNDING_CHECK"] == "PASS"
    assert cert.OLD_BOUND - cert.integer(after["BOUND"]) == 436512


def test_result_claims_are_limited_to_this_row() -> None:
    result = cert.compute_result()
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert result["NEW_ADMISSIBLE_BOUND"] == 312955720
    assert result["BELOW_NEXT_COMPETITOR"] is True
    assert result["FAMILY_GAIN_CLAIMED"] == result["NEW_WINNING_OUTCOMES"] == 0
    assert result["FAMILY_LEDGER_UPDATED"] is False
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["HEAVY_SOLVER_STARTED"] == "NO"
    assert result["JUDGE_MODE"] == "SELF_CHECK_ONLY"
