"""Focused positive checks and falsifiable negative seams for the one-profile certificate."""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from typing import cast

import pytest

from lottolab.research import b649_next_frontier_66555555555431100000_r1 as cert


def test_full_profile_analytic_certificate() -> None:
    result = cert.analytic_certificate()
    assert result["CAP"] == 255
    assert result["PROOF_SCOPE"] == "FULL_PROFILE"
    assert result["ARGMAX_M"] == [3, 4, 5, 6, 7, 8]
    assert result["CASES"] == [
        {"M": 3, "R": 24, "CORE_CEILING": 48, "ZERO_SQUARE_CEILING": 12, "T_CEILING": 255},
        {"M": 4, "R": 22, "CORE_CEILING": 52, "ZERO_SQUARE_CEILING": 20, "T_CEILING": 255},
        {"M": 5, "R": 20, "CORE_CEILING": 56, "ZERO_SQUARE_CEILING": 28, "T_CEILING": 255},
        {"M": 6, "R": 18, "CORE_CEILING": 60, "ZERO_SQUARE_CEILING": 36, "T_CEILING": 255},
        {"M": 7, "R": 16, "CORE_CEILING": 64, "ZERO_SQUARE_CEILING": 44, "T_CEILING": 255},
        {"M": 8, "R": 14, "CORE_CEILING": 66, "ZERO_SQUARE_CEILING": 54, "T_CEILING": 255},
        {"M": 9, "R": 12, "CORE_CEILING": 64, "ZERO_SQUARE_CEILING": 66, "T_CEILING": 253},
        {"M": 10, "R": 10, "CORE_CEILING": 60, "ZERO_SQUARE_CEILING": 80, "T_CEILING": 251},
    ]
    cert.verify_analytic_certificate(result)
    roundtrip = cast(dict[str, object], json.loads(json.dumps(result)))
    cert.verify_analytic_certificate(roundtrip)


def test_frozen_authority_and_same_profile_prior_art() -> None:
    result = cert.frozen_authority()
    assert result["FROZEN_RESULT_SHA256"] == cert.FROZEN_SHA
    assert result["FROZEN_ROW"] == {
        "CAP": 266,
        "S4_BASE": 112,
        "BOUND": 313394776,
        "SOURCE": cert.SOURCE_LOCATOR,
    }
    prior = cert.prior_art()
    assert prior[0]["CAP"] == 251
    assert prior[0]["RESOURCE_VERDICT"] == "FAIL"
    assert all(row["SEARCH_RERUN"] == "NO" for row in prior)


def test_exact_route_cursor_threshold_and_argmax() -> None:
    old = cert.route_terms(266)
    new = cert.route_terms(255)
    cert.validate_terms(old, 266)
    cert.validate_terms(new, 255)
    assert cert.widest_sufficient_cap(old) == 265
    assert max(row[1] for row in old[:-1]) == 313386008 <= cert.CURSOR_BOUND
    assert old[-1] == (266, 313394776, 508, 196, 299656, 5175968)
    assert max(new, key=lambda row: row[1]) == (255, 313296388, 425, 196, 243299, 5045376)
    assert new == old[: len(new)]
    assert cert.OLD_BOUND - max(row[1] for row in new) == 98388


@pytest.mark.parametrize(
    "model",
    [
        replace(cert.MODEL, pair_linearity=False),
        replace(cert.MODEL, labels_per_ticket=7),
        replace(cert.MODEL, triple_supports=21),
        replace(cert.MODEL, support_sizes=(1, 3)),
    ],
)
def test_negative_missing_premises(model: cert.Premises) -> None:
    with pytest.raises(AssertionError, match="support premises"):
        cert.analytic_certificate(model=model)


def test_negative_wrong_profile_and_false_cap() -> None:
    with pytest.raises(AssertionError, match="wrong exact profile"):
        cert.analytic_certificate("65555555555550000000")
    forged = cert.analytic_certificate()
    forged["CAP"] = 254
    with pytest.raises(AssertionError, match="wrong cap"):
        cert.verify_analytic_certificate(forged)


@pytest.mark.parametrize(
    "triples,pairs,reason",
    [
        ((), (), "support counts"),
        (((0, 0, 1),) * 22, ((0, 1),) * 27, "support vertices"),
        (((0, 1, 2),) * 22, ((0, 1),) * 27, "pair reuse"),
        (((0, 1, 20),) * 22, ((0, 1),) * 27, "support vertices"),
    ],
)
def test_negative_illegal_support(
    triples: tuple[tuple[int, ...], ...],
    pairs: tuple[tuple[int, ...], ...],
    reason: str,
) -> None:
    with pytest.raises(AssertionError, match=reason):
        cert.support_graph(triples, pairs)


def test_negative_simple_zero_graph_premise() -> None:
    with pytest.raises(AssertionError, match="simple five-vertex"):
        cert.zero_square_ceiling(5, simple=False)
    with pytest.raises(AssertionError, match="necessary range"):
        cert.zero_square_ceiling(2)


def test_negative_k4_ceiling_and_incomplete_envelope() -> None:
    terms = cert.route_terms(255)
    t, bound, k4, a, s4, s3 = terms[-1]
    terms[-1] = t, bound, k4 - 1, a, s4, s3
    with pytest.raises(AssertionError, match="K4 ceiling"):
        cert.validate_terms(terms, 255)
    with pytest.raises(AssertionError, match="incomplete T coverage"):
        cert.validate_terms(cert.route_terms(255)[:-1], 255)


def test_negative_final_floor_instead_of_ceiling() -> None:
    # The legitimate 112 base gives integral terms; base 113 is a deliberate
    # fractional rounding seam, preventing a vacuous floor-versus-ceiling test.
    terms = cert.route_terms(22, base=113)
    cert.validate_terms(terms, 22, base=113)
    t, _, k4, a, s4, s3 = terms[0]
    exact = Fraction(cert.S1 - cert.S2 + s3) - Fraction(4 * s4, 7)
    assert exact.denominator == 7
    wrong = exact.numerator // exact.denominator
    terms[0] = t, wrong, k4, a, s4, s3
    with pytest.raises(AssertionError, match="final rounding"):
        cert.validate_terms(terms, 22, base=113)


def test_negative_s4_credit_and_wrong_source_sha() -> None:
    terms = cert.route_terms(22)
    t, bound, k4, a, s4, s3 = terms[0]
    terms[0] = t, bound, k4, a, s4 + 1, s3
    with pytest.raises(AssertionError, match="S4 floor"):
        cert.validate_terms(terms, 22)
    with pytest.raises(AssertionError, match="source SHA mismatch"):
        cert.pinned(cert.FROZEN_RESULT, "0" * 64)


def test_omitting_m5_correction_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mutation is isolated in a controlled seam and restored by pytest.
    accepted = cert.analytic_certificate()
    cert.verify_analytic_certificate(accepted)
    actual = cert.zero_square_ceiling

    def broken(m: int, *, vertices: int = 5, simple: bool = True) -> int:
        return 30 if m == 5 else actual(m, vertices=vertices, simple=simple)

    monkeypatch.setattr(cert, "zero_square_ceiling", broken)
    assert cert.analytic_certificate()["CAP"] == 257
    with pytest.raises(AssertionError, match="wrong cap"):
        cert.verify_analytic_certificate(accepted)


def test_source_recount_and_full_result() -> None:
    result = cert.compute_result()
    assert result["NEW_ADMISSIBLE_BOUND"] == 313296388
    assert result["BOUND_AT_OR_BELOW_CURSOR"] is True
    assert result["ARGMAX_S4_CREDIT"] == 139028
    assert result["ALL_ARGMAX_T"] == [255]
    assert result["FAMILY_GAIN_CLAIMED"] == 0
    assert result["FAMILY_REPLAY"] == "NOT_RUN"
    assert result["PRIOR_ART_SUPERSEDED"] != "YES"
