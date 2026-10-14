"""Focused validation for the pinned T-cap evidence adoption."""

from __future__ import annotations

import copy
import json

import pytest

from lottolab.research import b649_k20_t251_evidence_adoption_r2 as adoption


def _result() -> dict[str, object]:
    value = json.loads(adoption.RESULT_PATH.read_bytes())
    assert type(value) is dict
    return value


def test_public_validator_accepts_saved_evidence() -> None:
    assert adoption.validate_evidence_adoption() is None


def test_analytic_proof_and_disjoint_counting_are_preserved() -> None:
    result = _result()
    proof = result["PROOF"]
    assert result["W"] == 829
    assert proof["CORE_CAPACITIES"] == "(0^2,1^10,3,5)"
    assert proof["Y_RANGE"] == [0, 6]
    assert proof["CORE_ZERO_EDGES"] == "18-2*y"
    assert proof["ZERO_ZERO_EDGES"] == "9+y"
    assert proof["CORE_COMPLEMENT_EDGES"] == "25-y"
    assert proof["INDEPENDENT_CCZ_BOUND"] == (
        "I_CCZ >= 6*(25-y)-sum_c a_c*(1+r_c+a_c)"
    )
    assert proof["CORRECTION_TERM_BOUND"] == (
        "sum_c a_c*(1+r_c+a_c) <= 3*(18-2*y)+52"
    )
    assert proof["SIMPLIFIED_FLOOR"] == "6*(25-y)-[3*(18-2*y)+52]=44"
    assert proof["COUNT_IDENTITY"] == "T+I=295"
    assert proof["CAP_DERIVATION"] == "T<=295-44=251"
    assert "disjoint event classes" in proof["NO_DOUBLE_COUNTING_REASON"]
    constant_term = 6 * 25 - (3 * 18 + 52)
    y_coefficient = -6 - (3 * -2)
    assert constant_term == 44 and y_coefficient == 0


def test_source_bound_reduction_and_term_digest_are_recorded() -> None:
    result = _result()
    assert result["OLD_ROW_BOUND"] == 313261354
    assert result["NEW_ROW_BOUND"] == 313142921
    assert result["ROW_DELTA"] == 118433
    assert result["OLD_TERM_COUNT"] == 244
    assert result["TERM_COUNT"] == 230
    assert result["ARGMAX_NEW_T"] == 251
    assert result["TERM_DIGEST"] == (
        "bee307b6d1bb35e59fae704f8b1c523048f641e798aa2ea534d487c10b17a6c1"
    )


NEGATIVE_CASES = (
    "WRONG_PROFILE",
    "WRONG_FROZEN_HEAD",
    "WRONG_FROZEN_TREE",
    "WRONG_INPUT_DIGEST",
    "COUPLED_SOURCE_TAMPERING",
    "WRONG_SOURCE_METHOD",
    "WRONG_SOURCE_COLUMN",
    "WRONG_CAP",
    "WRONG_ROW_BOUND",
    "WRONG_TERM_COUNT",
    "WRONG_TERM_DIGEST",
    "MISSING_REQUIRED_FIELD",
    "WRONG_REQUIRED_FIELD_TYPE",
    "RESOURCE_FAIL_TO_PASS",
    "FALSE_FAMILY_CLOSURE",
    "OTHER_PROFILE_MUTATION",
)


def _mutate(case: str, result: dict[str, object]) -> None:
    provenance = result["PROVENANCE"]
    historical = result["HISTORICAL_STATUS"]
    if case == "WRONG_PROFILE":
        result["PROFILE"] = "66555555555532000000"
    elif case == "WRONG_FROZEN_HEAD":
        provenance["FROZEN_HEAD"] = "0" * 40
    elif case == "WRONG_FROZEN_TREE":
        provenance["FROZEN_TREE"] = "0" * 40
    elif case == "WRONG_INPUT_DIGEST":
        provenance["SOURCE_INPUT_SHA256"] = "0" * 64
    elif case == "COUPLED_SOURCE_TAMPERING":
        provenance["FROZEN_RESULT_SHA256"] = "0" * 64
        provenance["SOURCE_INPUT_SHA256"] = "1" * 64
        provenance["SOURCE_METHOD_SHA256"] = "2" * 64
        provenance["SOURCE_INPUT_PATH"] = "docs/other-lineage.json"
    elif case == "WRONG_SOURCE_METHOD":
        provenance["SOURCE_METHOD"] = "bonf64_or_other_lineage"
    elif case == "WRONG_SOURCE_COLUMN":
        provenance["SOURCE_COLUMN"] = "FIFTH_ORDER_BOUND"
    elif case == "WRONG_CAP":
        result["T_CAP"] = 252
    elif case == "WRONG_ROW_BOUND":
        result["NEW_ROW_BOUND"] += 1
    elif case == "WRONG_TERM_COUNT":
        result["TERM_COUNT"] -= 1
    elif case == "WRONG_TERM_DIGEST":
        result["TERM_DIGEST"] = "0" * 64
    elif case == "MISSING_REQUIRED_FIELD":
        result.pop("ROW_DELTA")
    elif case == "WRONG_REQUIRED_FIELD_TYPE":
        result["I_FLOOR"] = True
    elif case == "RESOURCE_FAIL_TO_PASS":
        result["RESOURCE"]["NICE_PRIORITY"] = 14
    elif case == "FALSE_FAMILY_CLOSURE":
        historical["FULL_FAMILY_CLOSURE"] = "CLAIMED"
    elif case == "OTHER_PROFILE_MUTATION":
        result["PROFILE_UPDATES"].append(
            ["66555555555532000000", 313261000, 313141000]
        )
    else:
        raise AssertionError(f"unknown negative case: {case}")


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=NEGATIVE_CASES)
def test_fail_closed_negative_matrix(case: str) -> None:
    candidate = copy.deepcopy(_result())
    _mutate(case, candidate)
    with pytest.raises(adoption.EvidenceValidationError):
        adoption.validate_evidence_adoption(candidate)
