"""Focused adversarial checks of the actual exact-profile verifier."""

from __future__ import annotations

import json
from copy import deepcopy
from fractions import Fraction
from math import ceil
from typing import cast

import pytest

from lottolab.research import b649_s3_t208_exact_profile_certificate_r2 as cert


@pytest.fixture(scope="module")
def candidate() -> cert.Document:
    return cert.obj(json.loads(cert.render(cert.compute_result())))


def test_positive_certificate(candidate: cert.Document) -> None:
    cert.verify_result(candidate)
    assert candidate["UNIVERSAL_T_CAP"] == 208
    assert candidate["FULL_PROFILE_BOUND"] == 312835000
    assert candidate["PROFILE_DELTA"] == 555396
    assert candidate["R_CLASS_MAXIMA"] == [
        [6, -31, 6, 208],
        [8, -44, 12, 201],
        [10, -60, 20, 193],
        [12, -76, 30, 187],
        [14, -92, 42, 183],
        [16, -108, 56, 181],
        [18, -124, 66, 175],
    ]
    core = cert.obj(candidate["CORE"])
    assert core["CLASS_COUNT"] == 432
    assert core["LABELLED_ASSIGNMENT_COUNT"] == 2**11 * 3**2 * 4
    assert cert.obj(candidate["ZERO"])["MASK_COUNT"] == 32768


def test_profile_invariants(candidate: cert.Document) -> None:
    facts = cert.obj(candidate["FACTS"])
    assert {k: facts[k] for k in ("SUM_D", "SUM_D2", "E_G", "W", "J", "GOODMAN", "A_MAX")} == {
        "SUM_D": 66,
        "SUM_D2": 316,
        "E_G": 93,
        "W": 821,
        "J": 2259,
        "GOODMAN": 287,
        "A_MAX": 193,
    }
    assert facts["DEGREE_HISTOGRAM"] == {"5": 11, "4": 2, "3": 1, "0": 6}
    assert (facts["CORE_VERTICES"], facts["ZERO_VERTICES"], facts["G_MAX"]) == (14, 6, 11)


def test_route_b_stronger_evidence(candidate: cert.Document) -> None:
    route = cert.obj(candidate["ROUTE_B"])
    terms = cast(list[list[int]], route["TERMS"])
    assert len(terms) == 187
    assert [row[0] for row in terms] == list(range(22, 209))
    assert terms[-1] == [208, 312835000, 122, 122, 54656, 4476192]
    assert route["ARGMAX"] == [208]
    assert route["REFERENCE_FULL_BOUND"] == 312847544
    assert cert.obj(route["STRONGER_BOUND_EVIDENCE"])["REFERENCE_DIFFERENCE"] == 12544
    for _, bound, _, _, s4, s3 in terms:
        assert bound == ceil(Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7))
    assert candidate["LEGAL_ATTAINMENT"] == "UNKNOWN"
    assert candidate["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"


def mutate(value: cert.Document, defect: str) -> None:
    facts = cert.obj(value["FACTS"])
    core, zero = cert.obj(value["CORE"]), cert.obj(value["ZERO"])
    route = cert.obj(value["ROUTE_B"])
    terms = cast(list[list[int]], route["TERMS"])
    if defect == "wrong_exact_profile":
        facts["PROFILE"] = "55555555555434000000"
    elif defect == "wrong_degree_histogram":
        cert.obj(facts["DEGREE_HISTOGRAM"])["5"] = 10
    elif defect == "missing_core_class":
        cast(list[object], core["CLASS_ROWS"]).pop()
    elif defect == "missing_zero_graph":
        zero["MASK_COUNT"] = 32767
    elif defect == "incorrect_r_parity":
        cast(list[int], facts["R_DOMAIN"])[1] = 7
    elif defect == "wrong_residual_capacity":
        cast(list[int], facts["RESIDUAL_CAPACITIES"])[0] = 2
    elif defect == "negative_remainder":
        cert.obj(value["REMAINDER_TERMS"])["T(M)"] = -1
    elif defect == "wrong_s4_sign":
        route["S4_SIGN"] = 1
    elif defect == "unsupported_stronger_s4":
        cert.obj(route["STRONGER_BOUND_EVIDENCE"])["OPEN_WEDGE_MULTIPLIER"] = 8
        terms[-1][4] += 7
    elif defect == "fraction_ceiling":
        # In this T domain S4 is a multiple of seven, but the K4 ceiling
        # still has genuine fractional cases. Round one of those down.
        row = next(row for row in terms if row[2] > 0 and (2259 - 9 * (821 - 3 * row[0])) % 4)
        row[2] -= 1
    elif defect == "incomplete_t_range":
        terms.pop(90)
    elif defect == "wrong_base_sha256":
        cert.obj(value["BASE"])["RESULT_SHA256"] = "0" * 64
    elif defect == "missing_stronger_bound_evidence":
        route.pop("STRONGER_BOUND_EVIDENCE")
    elif defect == "candidate_result_inconsistency":
        value["SOURCE_SHA256"] = "0" * 64
    elif defect == "unsupported_s5":
        route["S5"] = "POSITIVE_CORRECTION"
    elif defect == "inconsistent_independent_recount":
        cast(list[list[int]], value["R_CLASS_MAXIMA"])[0][1] = -32
    else:
        raise AssertionError(defect)


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_exact_profile",
        "wrong_degree_histogram",
        "missing_core_class",
        "missing_zero_graph",
        "incorrect_r_parity",
        "wrong_residual_capacity",
        "negative_remainder",
        "wrong_s4_sign",
        "unsupported_stronger_s4",
        "fraction_ceiling",
        "incomplete_t_range",
        "wrong_base_sha256",
        "missing_stronger_bound_evidence",
        "candidate_result_inconsistency",
        "unsupported_s5",
        "inconsistent_independent_recount",
    ],
)
def test_production_verifier_rejects_defect(candidate: cert.Document, defect: str) -> None:
    damaged = deepcopy(candidate)
    mutate(damaged, defect)
    with pytest.raises(ValueError, match="candidate/result inconsistency"):
        cert.verify_result(damaged)


def test_actual_base_hash_guard(monkeypatch: pytest.MonkeyPatch, candidate: cert.Document) -> None:
    monkeypatch.setattr(cert, "BASE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="wrong Base SHA256"):
        cert.verify_result(candidate)
