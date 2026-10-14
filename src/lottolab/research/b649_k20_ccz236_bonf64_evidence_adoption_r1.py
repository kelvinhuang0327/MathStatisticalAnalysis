"""Bounded, local evidence for the accepted K20 CCZ236 / Bonf64 profile.

This module records one profile-specific certificate. It does not run the
historical solver, enumerate outcomes, or assert closure of the full family.
All authority values are pinned here so a result cannot make itself trusted.
The public validator is intentionally fail-closed and accepts only the exact
certificate represented by :func:`expected_certificate`.
"""

from __future__ import annotations

from math import comb
from typing import Any, Dict, List, Tuple


TASK_ID = "B649_K20_555555555555510_CCZ236_BONF64_ADOPTION_R1"
PROFILE_ID = "55555555555551000000"
FROZEN_HEAD = "e6fee5ebbfb972a1432bbc10ab5a337feac38478"
FROZEN_TREE = "0f32a6e5c813953bb902cce395b5b6fea0a77c59"
FROZEN_FAMILY_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-neighbor-deficit-sts13-family-closure-r1-result.json"
)
FROZEN_RESULT_SHA256 = "fef709c5168afa6da26ce18e0be78c40a12c6a711dec364e42659e1bb309d7b6"
BONF64_SOURCE_PATH = "src/lottolab/research/b649_k20_min_s2_realizable_core_class_bound_r4.py"
BONF64_SOURCE_SHA256 = "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
BONF64_SUPPORT_SOURCE_PATH = "src/lottolab/research/b649_k20_min_s2_higher_order_closure_r2.py"
BONF64_SUPPORT_SOURCE_SHA256 = "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
MATHEMATICS_ACCEPTANCE_TASK = (
    "B649_K20_E6FEE5EB_555555555555510_CCZ_DIRECT_ACCEPTANCE_R3"
)
SOURCE_METHOD = "K20_SUPPORT_LINEARITY_S4_PER_PAIR_THIRD_ORDER_BONFERRONI"
PROOF_SCOPE = "PROFILE_55555555555551000000_LOCAL_BOUND_ONLY"
BONF64_METHOD_IDENTITY = (
    "U64(T)=B3(W,T)-64*Phi93(3*T-66); W=826; 22<=T<=236"
)

I_FLOOR = 56
T_CAP = 236
HISTORICAL_T_CAP = 265
W = 826
T_PLUS_I = 292
B3_AT_236 = 313_212_648
P_MIN_AT_236 = 1_899
BONF64_UPPER_BOUND = 313_091_112
INCUMBENT = 313_263_888
MARGIN_BELOW_INCUMBENT = 172_776
FROZEN_FAMILY_ROW_BOUND = 313_250_644
HISTORICAL_R30_ROW_BOUND = 313_556_872

_S1 = 372_228_640
_S2 = 63_838_600
_S3_WEDGE_COEFFICIENT = 2_800
_S3_TRIANGLE_COEFFICIENT = 11_872
_S3_CONSTANT = 30_800
_CORE_TRIANGLES = 22
_PHI_BINS = 93
_S4_PER_PAIR_FLOOR = 112
_BONF64_FACTOR = 64
_FIRST_T = 22
_RESOURCE_GATE_VERDICT = "FAIL"


def phi93(total: int) -> int:
    """Minimum sum of ``comb(q, 2)`` over 93 nonnegative integer bins.

    Convexity makes the minimum the balanced allocation: ``total % 93`` bins
    receive one more unit than the others.
    """

    if type(total) is not int or total < 0:
        raise ValueError("total must be a nonnegative integer")
    quotient, remainder = divmod(total, _PHI_BINS)
    return (
        (_PHI_BINS - remainder) * comb(quotient, 2)
        + remainder * comb(quotient + 1, 2)
    )


def b3_bound(total_triangles: int) -> int:
    """Return the pinned third-order union bound for a legal total triangle count."""

    if type(total_triangles) is not int or not _FIRST_T <= total_triangles <= T_CAP:
        raise ValueError("total_triangles must be an integer in 22..236")
    noncore_triangles = total_triangles - _CORE_TRIANGLES
    s3 = (
        _S3_WEDGE_COEFFICIENT * W
        + _S3_TRIANGLE_COEFFICIENT * noncore_triangles
        - _S3_CONSTANT
    )
    return _S1 - _S2 + s3


def bonf64_bound(total_triangles: int) -> int:
    """Return ``B3(W,T) - 64*Phi93(3*T-66)`` on the legal T interval."""

    if type(total_triangles) is not int or not _FIRST_T <= total_triangles <= T_CAP:
        raise ValueError("total_triangles must be an integer in 22..236")
    return b3_bound(total_triangles) - _BONF64_FACTOR * phi93(
        3 * total_triangles - 66
    )


def integer_ccz_cases() -> List[Dict[str, int]]:
    """Return the seven capacity cases in the analytic CCZ argument."""

    rows: List[Dict[str, int]] = []
    for m in range(7):
        a_max = 94 - 6 * m
        rows.append(
            {
                "M": m,
                "A_MAX": a_max,
                "I_CCZ_FLOOR": 6 * (25 - m) - a_max,
            }
        )
    return rows


def t_range_values() -> List[Tuple[int, int]]:
    """Compute all 215 legal integer-T Bonf64 bounds in increasing T order."""

    return [(total_triangles, bonf64_bound(total_triangles)) for total_triangles in range(_FIRST_T, T_CAP + 1)]


def t_range_summary() -> Dict[str, Any]:
    """Summarize the full deterministic T regression and its endpoint maximum."""

    values = t_range_values()
    bounds = [bound for _, bound in values]
    steps = [right - left for left, right in zip(bounds, bounds[1:])]
    return {
        "FIRST_T": values[0][0],
        "LAST_T": values[-1][0],
        "COUNT": len(values),
        "STRICTLY_INCREASING": all(step > 0 for step in steps),
        "MINIMUM_STEP": min(steps),
        "FIRST_UPPER_BOUND": values[0][1],
        "ENDPOINT_UPPER_BOUND": values[-1][1],
        "MAXIMUM_AT_ENDPOINT": bounds[-1] == max(bounds),
    }


def expected_certificate() -> Dict[str, Any]:
    """Return the validator-owned canonical result for the pinned packet."""

    return {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "PROFILE_ID": PROFILE_ID,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_FAMILY_RESULT_PATH": FROZEN_FAMILY_RESULT_PATH,
        "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
        "BONF64_SOURCE_PATH": BONF64_SOURCE_PATH,
        "BONF64_SOURCE_SHA256": BONF64_SOURCE_SHA256,
        "BONF64_SUPPORT_SOURCE_PATH": BONF64_SUPPORT_SOURCE_PATH,
        "BONF64_SUPPORT_SOURCE_SHA256": BONF64_SUPPORT_SOURCE_SHA256,
        "MATHEMATICS_ACCEPTANCE_TASK": MATHEMATICS_ACCEPTANCE_TASK,
        "SOURCE_METHOD": SOURCE_METHOD,
        "PROOF_SCOPE": PROOF_SCOPE,
        "SOURCE_AUTHORITY_GATE": "PASS",
        "PROVENANCE_GATE": "PASS",
        "METHOD_ISOLATION_GATE": "PASS",
        "MATHEMATICAL_PROOF_SAVED": "YES",
        "I_FLOOR": I_FLOOR,
        "T_CAP": T_CAP,
        "HISTORICAL_T_CAP": HISTORICAL_T_CAP,
        "W": W,
        "T_PLUS_I": T_PLUS_I,
        "B3_AT_236": b3_bound(T_CAP),
        "P_MIN_AT_236": phi93(3 * T_CAP - 66),
        "BONF64_UPPER_BOUND": bonf64_bound(T_CAP),
        "BONF64_CERTIFIED_BOUND": bonf64_bound(T_CAP),
        "INCUMBENT": INCUMBENT,
        "MARGIN_BELOW_INCUMBENT": INCUMBENT - bonf64_bound(T_CAP),
        "FROZEN_FAMILY_ROW_BOUND": FROZEN_FAMILY_ROW_BOUND,
        "HISTORICAL_R30_CAP": HISTORICAL_T_CAP,
        "HISTORICAL_R30_ROW_BOUND": HISTORICAL_R30_ROW_BOUND,
        "BONF64_METHOD_IDENTITY": BONF64_METHOD_IDENTITY,
        "INTEGER_CASES": integer_ccz_cases(),
        "WHOLE_T_RANGE": t_range_summary(),
        "MATHEMATICAL_PROOF": {
            "PROFILE_DEGREES": "5^13,1,0^6",
            "CORE_ZERO_COUNTS": {"CORE": 14, "ZERO": 6},
            "PROFILE_TOTALS": {"E": 93, "W": 826, "T_PLUS_I": 292},
            "CORE_CAPACITIES": "1^13,5",
            "LEGAL_DOMAIN": (
                "m is an integer with 0<=m<=6; for each core vertex u, "
                "0<=b_u<=r_u; sum_u(r_u-b_u)=2m."
            ),
            "EDGE_ACCOUNTING": {
                "CORE_CORE_DOUBLE_EDGES": "m",
                "CORE_ZERO_EDGES": "18-2m",
                "ZERO_ZERO_EDGES": "9+m",
                "CORE_COMPLEMENT_EDGES": "25-m",
            },
            "A_DEFINITION": "A=sum_u b_u(1+r_u+b_u)",
            "CCZ_INEQUALITY": "I_CCZ>=6(25-m)-A",
            "CCZ_COUNTING_UNIT": (
                "A candidate is a core-complement edge tagged by one of the six "
                "zero vertices; the loss term A bounds candidates that do not "
                "certify a CCZ instance."
            ),
            "CCZ_NO_DOUBLE_COUNTING": (
                "Each counted CCZ instance has a unique core-complement edge and "
                "zero-vertex tag, so one candidate contributes at most once."
            ),
            "INTEGER_CAPACITY_LOSS": (
                "A_FULL=sum_u r_u(1+2r_u)=94. If x=r_u-b_u units are removed, "
                "the loss is x(1+3r_u-x): one removed unit from capacity 1 costs "
                "3, while x removed units from capacity 5 cost x(16-x). Since "
                "2m<=12<13, the least loss for 2m integer units removes only "
                "capacity-1 units, so A<=94-6m."
            ),
            "GOODMAN_IDENTITY_INFERENCE": (
                "Every listed integer case gives I_CCZ>=56; with T+I=292, "
                "Goodman's identity implies T<=236."
            ),
            "BONF64_SUPPORT_LINEARITY": (
                "The 22 triple supports form a linear 3-uniform hypergraph. "
                "Their 66 ticket-pair incidences are distinct and disjoint from "
                "the 27 double-support pairs, giving 93 overlap-edge classes."
            ),
            "S4_LOWER_BOUND_PROOF": (
                "For the 20 triple-support degrees t_i with sum 66, the balanced "
                "integer allocation has sum(t_i^2)=222. If S4 were zero, the "
                "cross-incidence lower bound 4*66+222=486 across 22*17=374 "
                "core/outside pairs forces at least 112 pairs with two incidences. "
                "Those pairs inject into 66 core edges: two outside common "
                "neighbors on one core edge would make a contributing quartet. "
                "This contradiction gives a contributing quartet, and the pinned "
                "local table's smallest positive count is 112, hence S4>=112P "
                "for the P distinct pair certificates."
            ),
            "P_DEFINITION": (
                "P=sum_{j=1}^{93} binom(q_j,2), where q_j are the excess "
                "noncore-triangle incidences assigned to the 93 distinct "
                "overlap-edge classes and sum_j q_j=3T-66."
            ),
            "P_NO_DOUBLE_COUNTING": (
                "Each unordered pair counted by binom(q_j,2) belongs to one "
                "unique overlap-edge class; linearity prevents a support pair "
                "from appearing in two classes. The counted pair certificates "
                "are credited once in S4."
            ),
            "P_LOWER_BOUND": "P>=Phi93(3T-66)",
            "PHI93_DEFINITION": (
                "For n>=0, write n=93q+r with 0<=r<93; "
                "Phi93(n)=(93-r)*binom(q,2)+r*binom(q+1,2)."
            ),
            "WINNER_MULTIPLICITY_PROOF": (
                "At most seven tickets can win on one outcome: select three of "
                "the seven hit labels from each winner; the resulting triples "
                "are pairwise linear, so they use distinct pairs and number at "
                "most binom(7,2)/binom(3,2)=7."
            ),
            "BONFERRONI_UNION_PROOF": (
                "For multiplicity r<=3, the third-order Bonferroni excess over "
                "the union indicator is zero. For 4<=r<=7 it is at least "
                "(4/7)*binom(r,4). Summing and using S4>=112P gives "
                "Union<=B3-(4/7)*112P=B3-64P."
            ),
            "B3_DEFINITION": (
                "B3(W,T)=S1-S2+2800W+11872*(T-22)-30800, with "
                "S1=372228640, S2=63838600, and W=826."
            ),
            "ENDPOINT_MONOTONICITY_PROOF": (
                "For each legal T step, B3 increases by 11872. In this range "
                "3T-66<=642, so Phi93(n+3)-Phi93(n)<=18; therefore U64 "
                "increases by at least 11872-64*18=10720 at every step. Its "
                "maximum is the T=236 endpoint."
            ),
        },
        "MATHEMATICS": "ACCEPTED",
        "OFFICIAL_OBJECTIVE": "ACCEPTED",
        "HISTORICAL_R30_ADMISSIBILITY": "PROVED",
        "HISTORICAL_RESOURCE": "FAIL",
        "NEW_IMPLEMENTATION": "SELF_CHECK_ONLY",
        "NEW_ARTIFACT_JUDGE": "NOT_RUN",
        "NEW_RESOURCE_VERDICT": _RESOURCE_GATE_VERDICT,
        "NEW_RESOURCE_FINDING": (
            "The first external shell command, the required attachment read, "
            "ran without niceness 15; later shell commands were observed at "
            "niceness 15. The first-command requirement cannot be retroactively "
            "satisfied."
        ),
        "FULL_FAMILY_CLOSURE": "NOT_CLAIMED",
        "GLOBAL_OPTIMUM": "NOT_CLAIMED",
        "FAMILY_MAXIMUM_REDUCED": False,
    }


def _type_sensitive_differences(actual: Any, expected: Any, path: str) -> List[str]:
    """Return fail-closed, JSON-path diagnostics for a canonical comparison."""

    if type(actual) is not type(expected):
        return ["TYPE_MISMATCH:" + path]
    if isinstance(expected, dict):
        differences: List[str] = []
        for key in expected:
            if key not in actual:
                differences.append("MISSING:" + path + "." + key)
            else:
                differences.extend(
                    _type_sensitive_differences(actual[key], expected[key], path + "." + key)
                )
        for key in actual:
            if key not in expected:
                differences.append("UNEXPECTED:" + path + "." + str(key))
        return differences
    if isinstance(expected, list):
        differences = []
        if len(actual) != len(expected):
            differences.append("LENGTH_MISMATCH:" + path)
        for index, (actual_value, expected_value) in enumerate(zip(actual, expected)):
            differences.extend(
                _type_sensitive_differences(
                    actual_value, expected_value, path + "[" + str(index) + "]"
                )
            )
        return differences
    if actual != expected:
        return ["VALUE_MISMATCH:" + path]
    return []


def validate_certificate(certificate: Any) -> Tuple[str, ...]:
    """Validate the complete certificate through the public fail-closed gate.

    The result supplies evidence fields only. Trusted expected values and the
    215-value Bonf64 regression are rebuilt from this module's pinned
    definitions; omitted, mistyped, changed, or extra fields are rejected.
    """

    if type(certificate) is not dict:
        return ("ROOT_TYPE_MISMATCH:$",)
    return tuple(_type_sensitive_differences(certificate, expected_certificate(), "$"))
