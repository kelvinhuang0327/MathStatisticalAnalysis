"""One-owner contained-triple K4 cap refinement, with integer-only arithmetic.

For every MIN-S2 realization of 66555555555540000000, there are 22 distinct
three-ticket label supports, pair overlaps <= 1, and graph degrees g=6+d.
For a support S, every K4 containing S has an outside vertex adjacent to all
three vertices of S. Its count is <= min_{v in S}(g_v-2)=4+min_{v in S}d_v.
There are only two d=6 vertices, so every support has minimum d <= 5. The
unique d=4 vertex belongs to exactly four supports; those four have minimum
d=4. Thus the number A of K4s containing a support is <= 4*8+18*9=194.
Pair linearity ensures that a K4 contains at most one support, so no K4 is
counted twice. This replaces the average-degree cap floor(602/3)=200.

Retain the frozen triangle cap 264 (R30 GROUP_ATTEMPTS[3291]), without
executing any solver or replay. For each integer t in 22..264, W=832,
OW=W-3t, J=sum C(g,3)=2350, and K4 >= max(0,ceil((J-10*OW)/4)). Indeed a
missing neighbourhood pair destroys at most g-2 triples; sum the resulting
neighbourhood triangle lower bounds and count every K4 at its four vertices.
Write K for this lower bound. K4 profiles containing a support weigh 448;
other K4s weigh 679. All other S4 terms are nonnegative. Consequently
S4 >= max(112,679*K-231*min(K,194)). The RHS increases with K and decreases
with A, so substituting a lower K and upper A has the required direction.
These floors overlap the old floors: take their maximum, never their sum.

An outcome has at most seven winning tickets: three hit labels from each
winner use three disjoint pairs among the seven drawn labels. For r<=7,
7*(r-C(r,2)+C(r,3)-1[r>0]) >= 4*C(r,4). Summing yields the admissible bound
S1-S2+S3-floor(4*S4_floor/7), where S1=372228640, S2=63838600, and
S3=2800*W+11872*(t-22)-30800. Keeping the old conservative floor convention
reproduces 313398920. The full new envelope is 313398128, attained at t=264.

This is a necessary-condition proof for the entire designated owner; it does
not assume any support arrangement, witness, realization of the cap, new
winning outcomes, or global optimality. The inherited solver cap remains a
frozen authority premise, not a newly reproduced solver proof. No other
profile is refined and no existing proof ledger or runtime code is imported.
"""

from __future__ import annotations

import hashlib
import json
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any

TASK_ID = "B649_MIN_S2_CURRENT_FAMILY_OWNER_EXACT_BOUND_R1"
FROZEN_HEAD = "83ddad7ade4ae286d12890efdbf3ea7768103d5e"
FROZEN_TREE = "8939ae0a9150e269bbdb787a75ceb699b0cc3bca"
OWNER = "66555555555540000000"
D = tuple(map(int, OWNER))
OLD_BOUND = 313_398_920
NEW_BOUND = 313_398_128
NEXT_BOUND = 313_398_532
INCUMBENT = 313_263_888
TRIANGLE_CAP = 264
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIRECTORY = "docs/research/matrix-native-results"
AUTHORITY_PATH = (
    f"{RESULT_DIRECTORY}/b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
)
CAP_PATH = f"{RESULT_DIRECTORY}/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
RESULT_PATH = (
    ROOT / RESULT_DIRECTORY / "b649-min-s2-current-family-owner-exact-bound-r1-result.json"
)
INPUT_SHA256 = dict(
    [
        (AUTHORITY_PATH, "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"),
        (CAP_PATH, "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"),
        (
            "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
            "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d",
        ),
        (
            "src/lottolab/research/b649_k20_min_s2_current_cursor_dynamic_family_max_r30.py",
            "230cb455bb162f6c8ab428afbbc8e7d9cbc7ee3c88575ef247e8d57ae925acb5",
        ),
        (
            "src/lottolab/research/b649_k20_min_s2_higher_order_closure_r2.py",
            "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45",
        ),
        (
            "src/lottolab/research/b649_k20_min_s2_resolved_above_cursor_owner_chase_r20.py",
            "b63081af598a6366ab9989f00f3e269052e8edbc41956a0771941dc03891b74e",
        ),
    ]
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_authority(authority: dict[str, Any], cap: dict[str, Any]) -> None:
    """Reject a different owner, baseline, or non-certifying inherited cap."""
    expected = {
        "FAMILY_OWNER_IDS": [OWNER],
        "FAMILY_BOUND_AFTER": OLD_BOUND,
        "NEXT_COMPETING_BOUND": NEXT_BOUND,
        "INCUMBENT": INCUMBENT,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
    }
    require(all(authority.get(k) == v for k, v in expected.items()), "family authority mismatch")
    require(authority["RESOLVED_ROW_BOUNDS"][OWNER] == OLD_BOUND, "owner baseline mismatch")
    expected_cap = {
        "ATTEMPT_INDEX": 3291,
        "PROFILE_IDS": [OWNER],
        "ROUTE": "A_EXACT_SUPPORT_UNION_OPEN_WEDGE_REFUTATION",
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "REFUTED_GRAPH_TRIANGLE_COUNT": 265,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": TRIANGLE_CAP,
        "WEDGE_COUNT": 832,
        "OPEN_WEDGE_CEILING_REFUTED": 37,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": 38,
        "EXTERNAL_TIMEOUT_EXIT_CODE": 0,
    }
    require(all(cap.get(k) == v for k, v in expected_cap.items()), "cap certificate mismatch")
    require(cap["WEDGE_COUNT"] - 3 * TRIANGLE_CAP == 40, "cap wedge rounding mismatch")


def authorities(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind only frozen inputs; do not rebuild a ledger or run donor code."""
    blobs = {}
    for path, digest in INPUT_SHA256.items():
        raw = (root / path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, f"frozen input changed: {path}")
        blobs[path] = raw
    authority = json.loads(blobs[AUTHORITY_PATH])
    cap = json.loads(blobs[CAP_PATH])["GROUP_ATTEMPTS"][3291]
    validate_authority(authority, cap)
    return authority, cap


def contained_cap(profile: tuple[int, ...] = D) -> int:
    """The support minimum lemma is deliberately restricted to this owner."""
    require(profile == D and all(type(d) is int for d in profile), "outside designated owner")
    require(sum(profile) == 3 * 22 and profile.count(6) == 2, "support incidence mismatch")
    require(profile.count(4) == 1 and profile.count(5) == 10, "degree multiplicity mismatch")
    return 4 * (6 + 4 - 2) + (22 - 4) * (6 + 5 - 2)


def envelope(a_cap: int) -> list[list[int]]:
    """Columns: T, bound, K4_floor, contained_K4_cap, S4_floor, S3, credit."""
    require(type(a_cap) is int and a_cap in (200, contained_cap()), "unproved A cap")
    degrees = tuple(6 + d for d in D)
    wedges = sum(comb(g, 2) for g in degrees)
    choose3 = sum(comb(g, 3) for g in degrees)
    terms = []
    for t in range(22, TRIANGLE_CAP + 1):
        ow = wedges - 3 * t
        require(ow >= 0, "negative open wedges")
        excess = choose3 - (max(degrees) - 2) * ow
        k4 = max(0, -(-excess // 4))
        require(4 * k4 >= excess, "K4 lower-bound ceiling direction")
        require(k4 == 0 or 4 * (k4 - 1) < excess, "K4 ceiling is not minimal")
        contained = min(k4, a_cap)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        credit = (4 * s4) // 7
        require(7 * credit <= 4 * s4 < 7 * (credit + 1), "S4 credit rounding direction")
        s3 = 2800 * wedges + 11872 * (t - 22) - 30800
        bound = 372_228_640 - 63_838_600 + s3 - credit
        terms.append([t, bound, k4, contained, s4, s3, credit])
    return terms


def k4_weight(contained_triple: bool) -> int:
    """Independent exact label-selection DP for the two relevant K4 profiles.

    Select seven of 49 labels, require three hits per ticket, then multiply by
    seven choices of special label. The DP does not import the frozen counter.
    """
    supports = {mask: 1 for mask in (3, 5, 9, 6, 10, 12)}
    if contained_triple:
        for mask in (3, 5, 6):
            del supports[mask]
        supports[7] = 1
    for i in range(4):
        supports[1 << i] = 6 - sum(n for mask, n in supports.items() if mask & (1 << i))
    supports[0] = 49 - sum(supports.values())
    states: dict[tuple[int, ...], int] = {(0, 0, 0, 0, 0): 1}
    for mask, count in supports.items():
        after: dict[tuple[int, ...], int] = {}
        for (used, *hits), ways in states.items():
            for take in range(min(count, 7 - used) + 1):
                key = (
                    used + take,
                    *(min(3, h + take * bool(mask & (1 << i))) for i, h in enumerate(hits)),
                )
                after[key] = after.get(key, 0) + ways * comb(count, take)
        states = after
    return 7 * states.get((7, 3, 3, 3, 3), 0)


def self_check() -> dict[str, Any]:
    """Local exhaustive checks support, but do not replace, the universal proof."""
    positive = [i for i, d in enumerate(D) if d]
    supports = list(combinations(positive, 3))
    for support in supports:
        low = min(D[i] for i in support)
        require(low <= (4 if 12 in support else 5), "support minimum inequality")
    weights = {"WITH_TRIPLE": k4_weight(True), "WITHOUT_TRIPLE": k4_weight(False)}
    require(weights == {"WITH_TRIPLE": 448, "WITHOUT_TRIPLE": 679}, "K4 weights mismatch")
    slacks = [7 * (r - comb(r, 2) + comb(r, 3) - int(r > 0)) - 4 * comb(r, 4) for r in range(8)]
    require(min(slacks) >= 0, "Bonferroni inequality direction")
    return {
        "STATUS": "PASS",
        "SUPPORT_CANDIDATES_CHECKED": len(supports),
        "K4_EXACT_WEIGHTS": weights,
        "BONFERRONI_INTEGER_SLACKS_R0_TO_R7": slacks,
    }


def compute_result() -> dict[str, Any]:
    _authority, cap = authorities()
    checks = self_check()
    old, new = envelope(200), envelope(contained_cap())
    require(max(row[1] for row in old) == OLD_BOUND, "old envelope does not reproduce baseline")
    require(max(row[1] for row in new) == NEW_BOUND, "new envelope mismatch")
    require(all(n[1] <= o[1] for o, n in zip(old, new, strict=True)), "bound direction mismatch")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY_OWNER_BOUND_REDUCED",
        "FROZEN_AUTHORITY": {
            "HEAD": FROZEN_HEAD,
            "TREE": FROZEN_TREE,
            "RESULT": AUTHORITY_PATH,
            "INPUT_SHA256": INPUT_SHA256,
        },
        "OWNER_PROFILE": OWNER,
        "OLD_OWNER_BOUND": OLD_BOUND,
        "NEW_ADMISSIBLE_OWNER_BOUND": NEW_BOUND,
        "BOUND_DELTA": OLD_BOUND - NEW_BOUND,
        "PROOF_METHOD": "SUPPORT_MINIMUM_DEGREE_CONTAINED_K4_CAP_200_TO_194",
        "PROOF": __doc__,
        "MIN_S2_PREMISES": {
            "TICKETS": 20,
            "TICKET_CAPACITY": 6,
            "LABELS": 49,
            "TRIPLE_SUPPORTS": 22,
            "PAIR_SUPPORTS": 27,
            "PAIR_LINEARITY": True,
            "GRAPH_DEGREES": [6 + d for d in D],
        },
        "INHERITED_TRIANGLE_CAP": {
            "VALUE": TRIANGLE_CAP,
            "SOURCE": f"{CAP_PATH}:GROUP_ATTEMPTS[3291]",
            "CERTIFICATE": cap,
            "VERIFICATION": "FROZEN_IDENTITY_REUSED_NO_SOLVER_EXECUTION",
        },
        "LOCAL_COUNTS": {
            "W": 832,
            "J": 2350,
            "OLD_A_CAP": 200,
            "NEW_A_CAP": 194,
            "SUPPORTS_CONTAINING_UNIQUE_D4": 4,
            "OTHER_SUPPORTS": 18,
            "S4_AT_CAP_BEFORE": old[-1][4],
            "S4_AT_CAP_AFTER": new[-1][4],
            "S4_INCREASE_AT_CAP": new[-1][4] - old[-1][4],
        },
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3", "CREDIT"],
        "OLD_ALL_T_TERMS": old,
        "NEW_ALL_T_TERMS": new,
        "SCOPE_COMPLETENESS": "ALL_REALIZATIONS_OF_DESIGNATED_OWNER_ALL_243_T_VALUES_22_TO_264",
        "EXACT_INTEGER_TESTS": checks,
        "UNPROVED_ASSUMPTIONS": [],
        "INHERITED_PROOF_LIMIT": "Accepted frozen MIN-S2 premises, cap and local formulas; "
        "historical cap solver proof not independently re-executed.",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "INHERITED_AUTHORITY_CAVEATS": "PRESERVED_NO_VERDICT_UPGRADE",
        "FAMILY_BOUND_EFFECT": {
            "BEFORE": OLD_BOUND,
            "AFTER": max(NEW_BOUND, NEXT_BOUND),
            "DELTA": OLD_BOUND - max(NEW_BOUND, NEXT_BOUND),
            "NEXT_COMPETING_BOUND": NEXT_BOUND,
            "OWNER_BELOW_NEXT_BY": NEXT_BOUND - NEW_BOUND,
            "METHOD": "MAX_NEW_OWNER_AND_FROZEN_NEXT_NO_PIPELINE_REPLAY",
        },
        "INCUMBENT": INCUMBENT,
        "STRICT_WINNER_DISCOVERED": "NO",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "RESULT_LOCATOR": str(RESULT_PATH),
        "HEAVY_PROCESS_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "PRODUCTION_MUTATION": "NONE",
        "FROZEN_LEDGER_MUTATED": "NO",
        "CERTIFICATE_F_MUTATED_OR_RECOMPUTED": "NO",
        "REMOTE_WRITE": "NO",
        "REMAINING_TASK_MODEL": {
            "最強模型": "下一個仍 active 的最小 owner 或單一 admissible-bound 研究。",
            "強模型": "有效數學證據的獨立 correctness review 與必要工程整合。",
            "中弱模型": "Frozen result 的機械性記錄、Git 發布及交接。",
        },
    }
