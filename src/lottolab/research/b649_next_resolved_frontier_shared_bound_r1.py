"""Shared K/Z triangle cap for the three highest resolved B649 profiles.

Let G be the 20-vertex ticket-intersection graph. Pair-linearity makes its 93
support edges distinct, and each of the 22 triple supports gives a distinct
triangle. For a profile d, deg_G(v)=6+d_v. The three pinned frontier profiles
all have six d=0 vertices (Z) and fourteen d>0 vertices (K).

For x in K, let sigma_x=|N_G(x) intersect Z|. Each such edge uses a pair
support at x, so 0 <= sigma_x <= 6-d_x. For z in Z, let zeta_z=|N_G(z)
intersect K|. Since G[Z] is simple on six vertices, zeta_z=6-deg_G[Z](z)
lies in 1..6 and its multiset is graphical. The crossing-edge count is
r=sum_K sigma=sum_Z zeta.

Write H=complement(G), M=H[K], and N=H[Z]. Then
  deg_M(x)=7-d_x+sigma_x,  deg_N(z)=zeta_z-1,
  2|E(M)|=32+r,             2|E(N)|=r-6.
Counting triangles of H by their intersection with K and Z gives
  T(H)=54+10r - sum_K sigma_x(7-d_x+sigma_x)
                     - sum_Z zeta_z(zeta_z-1) + P,
where P is the sum of four nonnegative terms: T(M), T(N), and the two
cross-part common-neighbour incidence sums. Every term of P is a cardinality.
Goodman’s identity gives
  T(G)+T(H)=C(20,3)-1/2 sum_v deg_G(v)(19-deg_G(v)).
Therefore, for each legal realization,
  T(G) <= B_d - 54 - 10r
             + sum_K sigma_x(7-d_x+sigma_x)
             + sum_Z zeta_z(zeta_z-1).

The finite relaxation retains only the necessary sigma ranges, equality of
the two crossing-edge sums, and graphicality of G[Z]. Sigma values are
grouped by equal d because their contribution is symmetric. The 102 graphical
degree multisets on six vertices are generated from the 2^15 possible local
graphs G[Z]; no 20-vertex support graph or portfolio is enumerated. Maximizing
the relaxed right side over that complete necessary-condition state set gives
individual caps 238, 242, 241. Thus the one shared cap T<=242 holds for all
three profiles. The proof does not claim any relaxation state is realizable.

The inherited S4 floor remains 112 and is combined with Route-B by MAX; no
S5 certificate is adopted for these profiles. The resulting T envelopes are
conditional projections over the inherited 4,647 resolved rows, 197 cursor
rows, and 282 profiles excluded by the inherited necessary-condition screen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import cast

from . import b649_cursor_41_owner_shared_bound_r1 as prior

TASK_ID = "B649_NEXT_RESOLVED_FRONTIER_SHARED_BOUND_R1"
INPUT_HEAD = "06664eeb1a7ecb8138e15f70bac32681f84bbf55"
INPUT_TREE = "11cf44e93cf921446118edf3b26127ff24e0fd49"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
EXCLUDED_COUNT = 282
EXCLUDED_IDS_SHA256 = "2c4d5b04cf2d4d89876f9c8721e7b73409bda9fb0711d2f3229807c3080296e0"
EXCLUDED_W_RANGE = [822, 861]
EXPECTED_PROFILE_IDS = (
    "65555555555541000000",
    "66655555555431000000",
    "66665555544441000000",
)
EXPECTED_INITIAL_FAMILY = 313392516
EXPECTED_NEXT_BOUND = 313392412
EXPECTED_CURSOR_MAXIMUM = 313391784
SHARED_CAP = 242
EXPECTED_PROFILE_CAPS = {
    "65555555555541000000": 238,
    "66655555555431000000": 242,
    "66665555544441000000": 241,
}
EXPECTED_OLD_CAPS = {
    "65555555555541000000": 265,
    "66655555555431000000": 264,
    "66665555544441000000": 264,
}
EXPECTED_OLD_BOUNDS = {
    "65555555555541000000": 313392516,
    "66655555555431000000": 313392412,
    "66665555544441000000": 313392412,
}
EXPECTED_NEW_BOUNDS = {
    "65555555555541000000": 313186584,
    "66655555555431000000": 313195248,
    "66665555544441000000": 313195248,
}
EXPECTED_NEW_FAMILY = 313392308
EXPECTED_NEW_MAX_OWNERS = ["66665555555421000000"]
EXPECTED_NEW_NEXT_OWNERS = ["65555555555442000000", "66555555554433000000"]
SOURCE = "src/lottolab/research/b649_next_resolved_frontier_shared_bound_r1.py"
TEST = "tests/unit/test_b649_next_resolved_frontier_shared_bound_r1.py"
RESULT = Path("docs/research/matrix-native-results/b649-next-resolved-frontier-shared-bound-r1-result.json")
ROOT = Path(__file__).resolve().parents[3]
S1_MINUS_S2 = 372_228_640 - 63_838_600
type Term = tuple[int, int, int, int, int, int]


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return result.stdout.decode().strip()


def verify_input_identity() -> str:
    pinned_tree = git("rev-parse", f"{INPUT_HEAD}^{{tree}}")
    require(pinned_tree == INPUT_TREE, "pinned input TREE mismatch")
    head = git("rev-parse", "HEAD")
    if head == INPUT_HEAD:
        require(git("rev-parse", "HEAD^{tree}") == INPUT_TREE, "wrong input TREE")
        return "INPUT_HEAD"
    require(git("rev-parse", "HEAD^") == INPUT_HEAD, "wrong input HEAD")
    return "DIRECT_CANDIDATE_CHILD"


def ceil_div(numerator: int, denominator: int) -> int:
    require(type(numerator) is int and type(denominator) is int and denominator > 0, "ceil division")
    return -(-numerator // denominator)


def family_summary(
    resolved: Mapping[str, int], cursor_after: Mapping[str, int]
) -> dict[str, object]:
    require(len(resolved) == 4647, "resolved row count")
    require(len(cursor_after) == 197, "cursor row count")
    require(not (set(resolved) & set(cursor_after)), "resolved/cursor overlap")
    require(all(type(v) is int for v in (*resolved.values(), *cursor_after.values())), "row bound type")
    merged = {**resolved, **cursor_after}
    levels = sorted(set(merged.values()), reverse=True)
    maximum = levels[0]
    owners = sorted(pid for pid, bound in merged.items() if bound == maximum)
    return {
        "MAXIMUM": maximum,
        "ALL_MAX_OWNERS": owners,
        "NEXT_DISTINCT_BOUND": levels[1],
        "ALL_NEXT_DISTINCT_OWNERS": sorted(
            pid for pid, bound in merged.items() if bound == levels[1]
        ),
        "RESOLVED_MAXIMUM": max(resolved.values()),
        "CURSOR_MAXIMUM": max(cursor_after.values()),
        "RESOLVED_ROWS_SCANNED": len(resolved),
        "CURSOR_ROWS_SCANNED": len(cursor_after),
        "TOTAL_PROJECTED_ROWS": len(merged),
    }


def profile_facts(pid: str) -> dict[str, object]:
    require(pid in EXPECTED_PROFILE_IDS, "profile is not in the three-row frontier")
    d = tuple(map(int, pid))
    assumptions = prior.MODEL
    require(
        assumptions.pair_linearity is True
        and assumptions.tickets == 20
        and assumptions.labels_per_ticket == 6
        and assumptions.labels == 49
        and assumptions.triples == 22
        and assumptions.pairs == 27,
        "support model drift",
    )
    require(
        len(d) == 20 and tuple(sorted(d, reverse=True)) == d and all(0 <= x <= 6 for x in d),
        "profile degree sequence",
    )
    require(sum(d) == 3 * assumptions.triples == 66, "triple-degree sum")
    g = tuple(6 + x for x in d)
    edges = 3 * assumptions.triples + assumptions.pairs
    sum_g = sum(g)
    sum_g2 = sum(x * x for x in g)
    wedges = sum(comb(x, 2) for x in g)
    goodman = comb(20, 3) - sum(x * (19 - x) for x in g) // 2
    zero_count = d.count(0)
    k_count = len(d) - zero_count
    a_max = sum(x * (6 + x - 2) for x in d) // 3
    facts = {
        "PROFILE_ID": pid,
        "D": list(d),
        "D_HISTOGRAM": {str(x): n for x, n in sorted(Counter(d).items())},
        "G": list(g),
        "VERTICES": len(d),
        "SUPPORT_EDGES": edges,
        "DEGREE_SUM_D": sum(d),
        "DEGREE_SUM_G": sum_g,
        "SUM_G_SQUARED": sum_g2,
        "WEDGES": wedges,
        "GOODMAN_SUM": goodman,
        "K_COUNT": k_count,
        "Z_COUNT": zero_count,
        "G_MAX": max(g),
        "SUM_C_G_3": sum(comb(x, 3) for x in g),
        "A_MAX": a_max,
        "DISTINCT_TRIPLE_SUPPORTS_LOWER_BOUND": assumptions.triples,
        "WEDGE_TRIANGLE_CAP": wedges // 3,
        "ASSUMPTIONS": {
            "TICKETS": assumptions.tickets,
            "LABELS_PER_TICKET": assumptions.labels_per_ticket,
            "LABELS": assumptions.labels,
            "TRIPLE_LABELS": assumptions.triples,
            "PAIR_LABELS": assumptions.pairs,
            "PAIR_LINEARITY": assumptions.pair_linearity,
        },
    }
    require(edges == 93 and sum_g == 186 and (k_count, zero_count) == (14, 6), "K/Z model facts")
    return facts


@cache
def zeta_graphical_sequences() -> tuple[int, tuple[tuple[int, ...], ...]]:
    """Enumerate only the induced six-vertex graph G[Z], not full support graphs."""
    pairs = tuple(combinations(range(6), 2))
    sequences: set[tuple[int, ...]] = set()
    for mask in range(1 << len(pairs)):
        degrees = [0] * 6
        for index, (u, v) in enumerate(pairs):
            if mask >> index & 1:
                degrees[u] += 1
                degrees[v] += 1
        sequences.add(tuple(sorted(6 - degree for degree in degrees)))
    require(len(pairs) == 15 and 1 << len(pairs) == 32768, "local graph census")
    require(len(sequences) == 102, "graphical six-vertex degree multisets")
    require(all(len(seq) == 6 and all(1 <= x <= 6 for x in seq) for seq in sequences), "zeta ranges")
    return 1 << len(pairs), tuple(sorted(sequences))


def validate_zeta_sequence(zeta: Sequence[int]) -> None:
    require(type(zeta) is tuple, "zeta sequence must be canonical tuple")
    require(zeta in set(zeta_graphical_sequences()[1]), "non-graphical zeta sequence")


def validate_sigma_signature(
    pid: str, signature: Sequence[tuple[int, Sequence[int]]]
) -> None:
    require(pid in EXPECTED_PROFILE_IDS, "sigma profile outside frontier")
    d = tuple(map(int, pid))
    expected = tuple(sorted(Counter(x for x in d if x > 0).items(), reverse=True))
    require(tuple(value for value, _ in signature) == tuple(value for value, _ in expected), "sigma degree classes")
    for (value, values), (_, count) in zip(signature, expected, strict=True):
        require(
            type(values) is tuple
            and len(values) == count
            and tuple(sorted(values)) == values
            and all(type(sigma) is int and 0 <= sigma <= 6 - value for sigma in values),
            "sigma range or multiplicity",
        )


def sigma_signatures(pid: str) -> tuple[tuple[tuple[int, tuple[int, ...]], ...], ...]:
    """Canonicalize labels only within equal-d classes; no state is discarded."""
    d = tuple(map(int, pid))
    groups = tuple(sorted(Counter(x for x in d if x > 0).items(), reverse=True))
    choices = tuple(
        tuple(combinations_with_replacement(range(7 - value), count))
        for value, count in groups
    )
    signatures = tuple(
        tuple((value, tuple(part)) for (value, _), part in zip(groups, parts, strict=True))
        for parts in product(*choices)
    )
    require(len(signatures) == len(set(signatures)), "duplicate sigma signature")
    for signature in signatures:
        validate_sigma_signature(pid, signature)
        require(
            sum(len(values) for _, values in signature) == 14
            and all(
                all(0 <= sigma <= 6 - value for sigma in values)
                for value, values in signature
            ),
            "sigma range or active vertex count",
        )
    return signatures


def relaxed_cap(pid: str, zeta_sequences: Sequence[tuple[int, ...]]) -> dict[str, object]:
    facts = profile_facts(pid)
    require(tuple(zeta_sequences) == zeta_graphical_sequences()[1], "incomplete graphical zeta state set")
    max_sigma_by_r: dict[int, int] = {}
    sigma_argmax_by_r: dict[int, list[tuple[tuple[int, tuple[int, ...]], ...]]] = {}
    signatures = sigma_signatures(pid)
    for signature in signatures:
        r = sum(sum(values) for _, values in signature)
        score = sum(
            sigma * (7 - value + sigma)
            for value, values in signature
            for sigma in values
        )
        previous = max_sigma_by_r.get(r)
        if previous is None or score > previous:
            max_sigma_by_r[r] = score
            sigma_argmax_by_r[r] = [signature]
        elif score == previous:
            sigma_argmax_by_r[r].append(signature)

    max_zeta_by_r: dict[int, int] = {}
    zeta_argmax_by_r: dict[int, list[tuple[int, ...]]] = {}
    for zeta in zeta_sequences:
        validate_zeta_sequence(zeta)
        r = sum(zeta)
        score = sum(x * (x - 1) for x in zeta)
        previous = max_zeta_by_r.get(r)
        if previous is None or score > previous:
            max_zeta_by_r[r] = score
            zeta_argmax_by_r[r] = [zeta]
        elif score == previous:
            zeta_argmax_by_r[r].append(zeta)

    candidates: list[tuple[int, int, int, int]] = []
    for r in sorted(set(max_sigma_by_r) & set(max_zeta_by_r)):
        value = (
            int(facts["GOODMAN_SUM"])
            - 54
            - 10 * r
            + max_sigma_by_r[r]
            + max_zeta_by_r[r]
        )
        candidates.append((value, r, max_sigma_by_r[r], max_zeta_by_r[r]))
    require(bool(candidates), "empty relaxed crossing-edge range")
    cap = max(row[0] for row in candidates)
    argmax_rows: list[dict[str, object]] = []
    for value, r, sigma_score, zeta_score in candidates:
        if value != cap:
            continue
        for sigma in sigma_argmax_by_r[r]:
            for zeta in zeta_argmax_by_r[r]:
                argmax_rows.append(
                    {
                        "R": r,
                        "SIGMA_SCORE": sigma_score,
                        "SIGMA_SIGNATURE_BY_D": [[v, list(values)] for v, values in sigma],
                        "ZETA_SCORE": zeta_score,
                        "ZETA_SEQUENCE": list(zeta),
                        "UPPER_BOUND": value,
                    }
                )
    return {
        "PROFILE_ID": pid,
        "CAP": cap,
        "GOODMAN_SUM": facts["GOODMAN_SUM"],
        "SIGMA_SIGNATURE_COUNT": len(signatures),
        "SIGMA_R_VALUES": sorted(max_sigma_by_r),
        "GRAPHICAL_ZETA_MULTISETS": len(zeta_sequences),
        "COMMON_R_VALUES": sorted(set(max_sigma_by_r) & set(max_zeta_by_r)),
        "RELAXATION_ARGMAX_COUNT": len(argmax_rows),
        "ALL_RELAXATION_ARGMAX": argmax_rows,
        "STATE_ATTAINABILITY": "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION",
    }


def validate_shared_cap(cap: int, profile_caps: Mapping[str, int]) -> None:
    require(type(cap) is int, "shared cap must be an integer")
    require(set(profile_caps) == set(EXPECTED_PROFILE_IDS), "shared cap profile set")
    require(cap == max(profile_caps.values()) == SHARED_CAP, "shared cap is not the class maximum")
    require(all(value <= cap for value in profile_caps.values()), "shared cap does not cover a profile")


def validate_s5_claim(pid: str, base_result: Mapping[str, object], used: bool) -> None:
    require(pid in EXPECTED_PROFILE_IDS, "S5 profile is outside frontier")
    require(type(used) is bool, "S5 used flag must be bool")
    adopted = cast(Mapping[str, object], base_result["CERTIFICATES_ADOPTED"])
    inherited_target = cast(Mapping[str, object], base_result["INHERITED_TARGET_BONFERRONI_5"])
    has_target = pid in adopted or inherited_target.get("PROFILE_ID") == pid
    require(
        base_result["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED" and not has_target,
        "target S5 authority unexpectedly exists; stop and resolve provenance",
    )
    require(not used, "S5 cannot be claimed without an adopted target certificate")


def s4_floor(pid: str) -> int:
    floor = prior.route.r28.profile_s4_floor(tuple(map(int, pid)))
    require(type(floor) is int and floor == 112, "inherited S4 floor drift")
    return floor


def envelope_term(pid: str, t: int, floor: int) -> Term:
    facts = profile_facts(pid)
    d = tuple(map(int, pid))
    g = tuple(6 + x for x in d)
    wedges = int(facts["WEDGES"])
    cap = wedges // 3
    require(type(t) is int and 22 <= t <= cap, "T outside necessary range")
    opened = wedges - 3 * t
    k4 = max(
        0,
        ceil_div(
            sum(comb(x, 3) for x in g) - (max(g) - 2) * opened,
            4,
        ),
    )
    a_max = sum(x * (6 + x - 2) for x in d) // 3
    contained = min(k4, a_max)
    s4 = max(floor, 679 * k4 - 231 * contained)
    s3 = 2800 * opened + 20272 * (t - 22) + 7000 * 22
    exact = Fraction(S1_MINUS_S2 + s3) - Fraction(4 * s4, 7)
    bound = ceil_div(exact.numerator, exact.denominator)
    return (t, bound, k4, contained, s4, s3)


def envelope(pid: str, cap: int, floor: int) -> list[Term]:
    facts = profile_facts(pid)
    require(type(cap) is int and 22 <= cap <= int(facts["WEDGE_TRIANGLE_CAP"]), "T cap range")
    require(type(floor) is int and floor >= 0, "S4 floor range")
    terms = [envelope_term(pid, t, floor) for t in range(22, cap + 1)]
    validate_envelope(pid, cap, floor, terms)
    return terms


def validate_envelope(pid: str, cap: int, floor: int, terms: Sequence[Term]) -> None:
    facts = profile_facts(pid)
    d = tuple(map(int, pid))
    g = tuple(6 + x for x in d)
    wedges = int(facts["WEDGES"])
    choose3 = sum(comb(x, 3) for x in g)
    g_max = max(g)
    a_max = sum(x * (6 + x - 2) for x in d) // 3
    require(type(cap) is int and 22 <= cap <= wedges // 3, "T cap range")
    require(type(floor) is int and floor >= 0, "S4 floor range")
    require([row[0] for row in terms] == list(range(22, cap + 1)), "incomplete T envelope")
    for t, bound, k4, contained, s4, s3 in terms:
        require(all(type(v) is int for v in (t, bound, k4, contained, s4, s3)), "term integer fields")
        opened = wedges - 3 * t
        expected_k4 = max(0, ceil_div(choose3 - (g_max - 2) * opened, 4))
        require(k4 == expected_k4, "K4 ceiling direction")
        require(contained == min(k4, a_max), "A_max floor/containment")
        expected_s4 = max(floor, 679 * k4 - 231 * contained)
        require(s4 == expected_s4, "S4 lower-bound direction/floor")
        expected_s3 = 2800 * opened + 20272 * (t - 22) + 154000
        require(s3 == expected_s3, "S3 identity")
        exact = Fraction(S1_MINUS_S2 + expected_s3) - Fraction(4 * expected_s4, 7)
        require(bound == ceil_div(exact.numerator, exact.denominator), "final exact rational ceiling")


def unique_old_cap(pid: str, old_bound: int, floor: int) -> tuple[int, list[Term]]:
    facts = profile_facts(pid)
    candidates: list[tuple[int, list[Term]]] = []
    for cap in range(22, int(facts["WEDGE_TRIANGLE_CAP"]) + 1):
        terms = envelope(pid, cap, floor)
        if max(row[1] for row in terms) == old_bound:
            candidates.append((cap, terms))
    require(len(candidates) == 1, "old input bound does not identify one Route-B envelope cap")
    return candidates[0]


def inherited_exclusion(base_result: Mapping[str, object]) -> dict[str, object]:
    caveats = cast(Mapping[str, object], base_result["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    preserved = cast(Mapping[str, object], caveats["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])
    snapshots = cast(Mapping[str, object], preserved["DONOR_STATUS_SNAPSHOTS_VERBATIM"])
    authority = cast(Mapping[str, object], snapshots["BASE_AUTHORITY"])
    cursor = cast(Mapping[str, object], authority["CURSOR"])
    partition = cast(Mapping[str, object], cursor["PARTITION"])
    excluded = cast(Mapping[str, object], partition["EXCLUDED_BY_NECESSARY_CONDITION"])
    require(
        excluded["COUNT"] == EXCLUDED_COUNT
        and excluded["IDS_SHA256"] == EXCLUDED_IDS_SHA256
        and excluded["W_RANGE"] == EXCLUDED_W_RANGE,
        "inherited 282-profile exclusion drift",
    )
    return {
        "COUNT": EXCLUDED_COUNT,
        "IDS_SHA256": EXCLUDED_IDS_SHA256,
        "W_RANGE": EXCLUDED_W_RANGE,
        "AUTHORITY_HEAD": BASE_HEAD,
        "AUTHORITY_TREE": BASE_TREE,
        "AUTHORITY_RESULT_PATH": prior.r2.BASE_RESULT,
        "AUTHORITY_RESULT_SHA256": prior.r2.BASE_SHA,
        "PRESERVED_VERBATIM": True,
        "CONCLUSION_SCOPE": "CONDITIONAL_ON_INHERITED_EXCLUSION; NOT_GLOBAL_OVER_ALL_HISTOGRAMS",
    }


def compute_result() -> dict[str, object]:
    verify_input_identity()
    fixed = prior.compute_result()
    fixed_bytes = prior.render(fixed)
    require(prior.RESULT.read_bytes() == fixed_bytes, "41-cursor input result not byte-reproduced")
    require(fixed["FAMILY_AFTER"] == EXPECTED_INITIAL_FAMILY, "original family not reproduced")

    resolved_before = cast(dict[str, int], fixed["RESOLVED_ROW_BOUNDS"])
    cursor_after = cast(dict[str, int], fixed["CURSOR_ROW_BOUNDS_AFTER"])
    require(len(resolved_before) == 4647 and len(cursor_after) == 197, "input row counts")
    require(max(cursor_after.values()) == EXPECTED_CURSOR_MAXIMUM, "cursor after-bounds maximum")
    before = family_summary(resolved_before, cursor_after)
    require(
        before["MAXIMUM"] == EXPECTED_INITIAL_FAMILY
        and before["ALL_MAX_OWNERS"] == [EXPECTED_PROFILE_IDS[0]]
        and before["NEXT_DISTINCT_BOUND"] == EXPECTED_NEXT_BOUND,
        "current family frontier mismatch",
    )
    frontier_ids = [
        *cast(list[str], before["ALL_MAX_OWNERS"]),
        *cast(list[str], before["ALL_NEXT_DISTINCT_OWNERS"]),
    ]
    require(tuple(frontier_ids) == EXPECTED_PROFILE_IDS, "actual frontier owners differ from pinned IDs")

    base_result = json.loads(
        prior.blob(prior.BASE_HEAD, prior.r2.BASE_RESULT, prior.r2.BASE_SHA)
    )
    exclusion = inherited_exclusion(base_result)
    require(
        len(resolved_before) + len(cursor_after) + int(exclusion["COUNT"]) == 5126,
        "resolved/cursor/excluded histogram accounting",
    )

    zeta_graph_count, zeta_sequences = zeta_graphical_sequences()
    profile_caps: dict[str, int] = {}
    profiles: dict[str, dict[str, object]] = {}
    updates: dict[str, int] = {}
    for pid in frontier_ids:
        facts = profile_facts(pid)
        floor = s4_floor(pid)
        validate_s5_claim(pid, base_result, False)
        theorem = relaxed_cap(pid, zeta_sequences)
        profile_caps[pid] = int(theorem["CAP"])
        old_bound = int(resolved_before[pid])
        require(old_bound == EXPECTED_OLD_BOUNDS[pid], "existing frontier row bound drift")
        old_cap, old_terms = unique_old_cap(pid, old_bound, floor)
        require(old_cap == EXPECTED_OLD_CAPS[pid], "old envelope cap drift")
        applied_cap = min(old_cap, SHARED_CAP)
        require(applied_cap == SHARED_CAP, "shared cap does not tighten every frontier row")
        new_terms = envelope(pid, applied_cap, floor)
        new_bound = max(row[1] for row in new_terms)
        new_argmax = [row for row in new_terms if row[1] == new_bound]
        require(new_bound == EXPECTED_NEW_BOUNDS[pid], "new bound drift")
        updates[pid] = new_bound
        fractional = sum((4 * row[4]) % 7 != 0 for row in new_terms)
        profiles[pid] = {
            "PROFILE_FACTS": facts,
            "RELAXATION_CAP": theorem,
            "OLD_EFFECTIVE_T_CAP_RECONSTRUCTED_FROM_INPUT_BOUND": old_cap,
            "OLD_ROW_BOUND": old_bound,
            "OLD_TERM_COUNT": len(old_terms),
            "OLD_ALL_ARGMAX": [row for row in old_terms if row[1] == old_bound],
            "INHERITED_S4_FLOOR": floor,
            "S5_ADOPTED_FOR_PROFILE": False,
            "NEW_SHARED_T_CAP": applied_cap,
            "NEW_ROW_BOUND": new_bound,
            "ROW_DELTA": old_bound - new_bound,
            "NEW_TERM_COUNT": len(new_terms),
            "NEW_T_RANGE": [22, applied_cap],
            "NEW_ALL_ARGMAX": new_argmax,
            "NEW_ALL_T_TERMS": new_terms,
            "FRACTIONAL_S4_CREDIT_TERM_COUNT": fractional,
        }

    validate_shared_cap(SHARED_CAP, profile_caps)
    require(set(updates) == set(frontier_ids), "frontier update set")
    resolved_after = dict(resolved_before)
    resolved_after.update(updates)
    require(set(resolved_after) == set(resolved_before), "resolved profile IDs changed")
    changed_ids = sorted(pid for pid in resolved_before if resolved_before[pid] != resolved_after[pid])
    require(changed_ids == list(EXPECTED_PROFILE_IDS), "updates are not exactly the three frontier rows")
    require(
        {pid: resolved_after[pid] for pid in changed_ids} == EXPECTED_NEW_BOUNDS,
        "frontier replacement rows",
    )
    require(cursor_after == cast(dict[str, int], fixed["CURSOR_ROW_BOUNDS_AFTER"]), "cursor rows changed")
    after = family_summary(resolved_after, cursor_after)
    require(
        after["MAXIMUM"] == EXPECTED_NEW_FAMILY
        and after["ALL_MAX_OWNERS"] == EXPECTED_NEW_MAX_OWNERS
        and after["NEXT_DISTINCT_BOUND"] == 313392232
        and after["ALL_NEXT_DISTINCT_OWNERS"] == EXPECTED_NEW_NEXT_OWNERS,
        "full family maximum recomputation",
    )
    require(
        int(before["MAXIMUM"]) - int(after["MAXIMUM"]) == 208,
        "family delta must be recomputed from all rows",
    )

    source_path = ROOT / SOURCE
    test_path = ROOT / TEST
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PROVEN_FAMILY_GAIN",
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "RESULT_PATH": str(prior.RESULT.relative_to(ROOT)),
            "RESULT_SHA256": sha(fixed_bytes),
            "REPRODUCED_BYTE_FOR_BYTE": True,
        },
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": prior.r2.BASE_RESULT,
            "RESULT_SHA256": prior.r2.BASE_SHA,
        },
        "SOURCE_SHA256": sha(source_path.read_bytes()),
        "TEST_SHA256": sha(test_path.read_bytes()),
        "FRONTIER_OWNER_IDS": frontier_ids,
        "PER_PROFILE_ASSUMPTIONS": {
            pid: profiles[pid]["PROFILE_FACTS"]["ASSUMPTIONS"] for pid in frontier_ids
        },
        "SHARED_THEOREM": {
            "K_VERTICES": 14,
            "Z_VERTICES": 6,
            "LOCAL_GZ_GRAPH_COUNT": zeta_graph_count,
            "GRAPHICAL_ZETA_MULTISETS": len(zeta_sequences),
            "PROFILES": profile_caps,
            "COMMON_T_CAP": SHARED_CAP,
            "UNIVERSALITY_SCOPE": "ALL_LEGAL_REALIZATIONS_OF_EACH_OF_THE_THREE_EXACT_PROFILES",
            "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
            "PORTFOLIOS_ENUMERATED": 0,
            "RELAXATION_STATES_ASSERTED_REALIZABLE": False,
        },
        "PROOF": __doc__,
        "PER_PROFILE_OLD_NEW_CAP": {
            pid: {
                "OLD_EFFECTIVE_T_CAP_RECONSTRUCTED_FROM_INPUT_BOUND": profiles[pid][
                    "OLD_EFFECTIVE_T_CAP_RECONSTRUCTED_FROM_INPUT_BOUND"
                ],
                "NEW_SHARED_T_CAP": SHARED_CAP,
                "PROFILE_RELAXATION_CAP": profiles[pid]["RELAXATION_CAP"]["CAP"],
            }
            for pid in frontier_ids
        },
        "PER_PROFILE_OLD_NEW_BOUND": {
            pid: {
                "OLD_BOUND": profiles[pid]["OLD_ROW_BOUND"],
                "NEW_BOUND": profiles[pid]["NEW_ROW_BOUND"],
                "ROW_DELTA": profiles[pid]["ROW_DELTA"],
            }
            for pid in frontier_ids
        },
        "PROFILES": profiles,
        "FULL_ENVELOPE_TERM_COUNTS": {
            "PROFILE_COUNT": len(profiles),
            "T_RANGE_PER_PROFILE": [22, SHARED_CAP],
            "TERMS_PER_PROFILE": SHARED_CAP - 22 + 1,
            "TOTAL_TERMS": sum(int(profiles[pid]["NEW_TERM_COUNT"]) for pid in frontier_ids),
            "ALL_T_ARGMAX_RECOMPUTED": True,
            "ROUNDING": "K4_CEILING; A_MAX_FLOOR; FINAL_EXACT_RATIONAL_CEILING",
        },
        "S4_S5_AUTHORITY": {
            "S4_FUNCTION": "b649_k20_min_s2_current_cursor_class_owner_chase_r28.profile_s4_floor",
            "S4_RULE": "MAX(inherited floor, Route-B lower bound); subtract nonnegative 4*S4/7 credit",
            "S4_FLOOR_BY_PROFILE": {pid: s4_floor(pid) for pid in frontier_ids},
            "S5_ALL_T_ADOPTION": base_result["ALL_T_BONFERRONI_5_ADOPTION"],
            "S5_ADOPTED_CERTIFICATES": base_result["CERTIFICATES_ADOPTED"],
            "S5_INHERITED_TARGET": base_result["INHERITED_TARGET_BONFERRONI_5"],
            "S5_USED_FOR_FRONTIER": False,
        },
        "FAMILY_BEFORE": before,
        "FAMILY_AFTER": after,
        "FAMILY_DELTA": int(before["MAXIMUM"]) - int(after["MAXIMUM"]),
        "ALL_NEW_MAX_OWNERS": after["ALL_MAX_OWNERS"],
        "NEXT_DISTINCT_BOUND": after["NEXT_DISTINCT_BOUND"],
        "CURSOR_197_PRESERVED": {
            "SOURCE_FIELD": "CURSOR_ROW_BOUNDS_AFTER",
            "COUNT": len(cursor_after),
            "MAXIMUM": max(cursor_after.values()),
            "UNCHANGED": True,
            "ROW_BOUNDS": cursor_after,
        },
        "RESOLVED_ROWS_BEFORE": resolved_before,
        "RESOLVED_ROWS_AFTER": resolved_after,
        "RESOLVED_ROW_COUNT": len(resolved_after),
        "RESOLVED_ROWS_CHANGED": len(changed_ids),
        "OTHER_RESOLVED_ROWS_UNCHANGED": len(resolved_before) - len(changed_ids),
        "INHERITED_EXCLUSION": exclusion,
        "INHERITED_EXCLUSION_PRESERVED": True,
        "CONDITIONAL_PROJECTION_ONLY": True,
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "INCUMBENT": fixed["INCUMBENT"],
        "GAP_TO_INCUMBENT": int(after["MAXIMUM"]) - int(fixed["INCUMBENT"]),
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "FRESH_FOCUSED_REVIEW": "REQUIRED_ON_FROZEN_CANDIDATE_TREE; VERDICT_EXTERNAL_TO_RESULT_JSON",
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def verify_result() -> None:
    expected = render(compute_result())
    require((ROOT / RESULT).read_bytes() == expected, "stored result differs from exact recomputation")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prove a shared cap for the three resolved frontier rows")
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    payload = render(result)
    output = ROOT / RESULT
    if args.write_result:
        if output.exists():
            require(output.read_bytes() == payload, "existing result differs")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as stream:
                stream.write(payload)
    elif args.verify:
        require(output.read_bytes() == payload, "stored result differs")
    print(
        json.dumps(
            {
                "RESULT": str(output),
                "SHA256": sha(payload),
                "STATUS": result["TASK_STATUS"],
                "FAMILY_BEFORE": result["FAMILY_BEFORE"],
                "FAMILY_AFTER": result["FAMILY_AFTER"],
                "FAMILY_DELTA": result["FAMILY_DELTA"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
