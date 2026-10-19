"""Formal cap-term certificate for 65555555555550000000; no search or ledger write.

MODEL. There are twenty six-label tickets on 49 labels: 22 supports of size
three and 27 of size two. Distinct tickets share at most one label. Thus the
overlap graph has 93 edges and degrees g=6+d, sum d=66. Official any-prize
events mean at least three hits among main|special. Every seven-set has seven
choices of special. Choose three hit labels for each winning ticket: their
three label pairs cannot recur in another winner, so r<=C(7,2)/3=7.

SIGNS. Si=sum_outcomes C(r,i). The order-five alternating sum minus the union
indicator is C(r-1,5)>=0 (zero at r=0). Its signs are +,-,+,-,+. Independently,
7*(r-C(r,2)+C(r,3)-1[r>0])-4*C(r,4)>=0 for 0<=r<=7.
Hence U<=S1-S2+S3-(4/7)S4 and U<=S1-S2+S3-S4+S5. Substituting an S4
LOWER bound and an S5 UPPER bound preserves both directions.

S3/S4. The pinned three-ticket counts yield S3=2800W+11872(T-22)-30800.
Every neighbour triple missing an edge charges an open wedge at its centre;
there are at most (max g-2) choices of its third neighbour. Thus
J<=4*K4+(max g-2)*(W-3T). A K4 contains at most one linear triple support.
Its fourth-order weight is 448 if it contains one, otherwise 679. The number
of contained K4s is at most sum_tau m_tau<=sum_v d_v*(4+d_v)/3. All other
quartet weights are nonnegative. This proves the K4 floor in every T term.
The existing seven-inactive-ticket S4 floor 1680 is inherited unchanged.

S5. A linear packing on five vertices has at most two triples: each vertex
has degree <=2, and three triples would force at least four degree-two
vertices but only three pairs of triples are available. Two meet once.
With zero triples seven labels give at most fourteen hits, less than fifteen.
With one triple, the unique winning seven-set uses that label and all six
cross edges to two common outside neighbours; their mutual edge is irrelevant.
With two triples meeting at c, all four cross edges between their exclusive
pairs must occur. Select the two triple labels, four cross labels and one
of four labels projecting to c: weight 28. These require K5 and were counted
twice by sum_tau C(m_tau,2), so add TWO, not zero or minus two.
Partial external triples project to pair/singleton labels; they are retained.
The independent seven-label DP checks all induced graphs and linear packings.
Summing the local identity proves S5=7*(sum_tau C(m_tau,2)+2*N_2T).

DEGREE CAP. m_tau<=min(g_v-2)=4+min(d_v). For H_k, the number of triples
with all three degrees >=k, 3H_k<=sum_{d>=k}d; H_k<=22-max_{0<d<k}d;
and H_k=0 with fewer than three high vertices. Threshold telescoping bounds
sum C(m_tau,2). Every intersecting triple pair has a unique common vertex,
so N_2T<=sum C(d_v,2). For the target these bounds are 792 and 135,
giving S5<=7434. This is an upper bound, with no attainment claim.

SCOPE. Verify the historical R30 refutation of T>=265 by immutable identity
and its accepted-cap predicate, without executing any solver. Replace ONLY
the T=264 BOUND with min(U4,U5). Preserve all 242 lower-T terms; independently
maximize all 243 terms. T263, not T264, determines the full-profile bound.
The donor's SELF_CHECK_ONLY status and the base's inherited caveats remain
verbatim. Family effects are projections over a frozen ledger; hypothetical
T249 is expressly not certified or installed. The stronger all-T U5 result
is outside this certificate. Fresh Judge disposition is external to this
immutable mathematical result and must match its exact committed tree.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_higher_order_closure_r2 as event
from . import b649_min_s2_two_tied_owner_exact_cert_r1 as base

prior, split, official = base.prior, base.split, base.official
require, obj, items, integer = prior.require, prior.obj, prior.items, prior.integer
sha, render, git, decode = prior.sha, prior.render, prior.git, prior.decode
ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = base.DIRECTORY
TASK_ID = "B649_MIN_S2_BONFERRONI5_TARGET_FORMAL_CERT_R1"
BASE_HEAD = "d0785605aefeff33d55d2763e9e8660ba298762d"
BASE_TREE = "d6e08905b87f1e8208ac7fe892f5b51278e1a9f7"
DONOR_HEAD = "e3a9843db4339167bffcdc92fb782ff6bb663ed8"
DONOR_PARENT = "919017c80f7f62adeb89d8faaaaaad41eed9f511"
DONOR_TREE = "f63545acbc883f13ec9c50eea0b3a7e6a2190d3b"
TARGET = "65555555555550000000"
CAP, S4_BASE = 264, 1680
DONOR_MODULE = "b649_k20_min_s2_three_competing_profiles_bonferroni5_r1"
DONOR_RESULT = f"{DIRECTORY}/b649-k20-min-s2-three-competing-profiles-bonferroni5-r1-result.json"
BASE_RESULT = f"{DIRECTORY}/b649-min-s2-two-tied-owner-exact-cert-r1-result.json"
R30_RESULT = f"{DIRECTORY}/{official.CAP_SOURCE_RESULT}"
S4_RESULT = base.S4_ROWS
PINS = {
    DONOR_RESULT: (
        DONOR_HEAD,
        "2382171ed2a47f14f8fcb4cca70c5a77f40e3cc6",
        "cfd541c6492d13156618a568505106f3686224731bf1df73f2af3c1d709f54a9",
    ),
    f"src/lottolab/research/{DONOR_MODULE}.py": (
        DONOR_HEAD,
        "ad33029bb27e65fee047da0181fe7cfbc27c4171",
        "c1813625148b95e0728c54b5e88f844640705575e1d969a14909d0e8f0033bf0",
    ),
    f"tests/unit/test_{DONOR_MODULE}.py": (
        DONOR_HEAD,
        "6a9de2013a812380676628f2c0b860807acc3b7f",
        "7fa8c2ffa0d446ab6659c99b3bbb852a4bf2bbf60472d19c29972470a6c8ea22",
    ),
    BASE_RESULT: (
        BASE_HEAD,
        "",
        "a56c20bcabb430e9d84b177e3ad4dc27c82b25a0befa516cbbd6046030c0a7cd",
    ),
    R30_RESULT: (BASE_HEAD, "6ab638ef2e2f7094d304da43d2d0aea8821b759b", official.R30_SHA256),
    S4_RESULT: (BASE_HEAD, "4724ded48e67f9614a5d74fa3d68735322373ec8", base.S4_ROWS_SHA),
}
RESULT_PATH = ROOT / DIRECTORY / "b649-min-s2-bonferroni5-target-cert-r1-result.json"
HELPERS = tuple(
    Path(module.__file__).resolve()
    for name, module in sorted(sys.modules.copy().items())
    if name.startswith("lottolab.research.") and name != __name__ and module.__file__
)
type Pair = tuple[int, int]
type Triple = tuple[int, int, int]
type Term = tuple[int, int, int, int, int, int]


def pinned_bytes(path: str) -> bytes:
    head, blob_id, digest = PINS[path]
    metadata = git("ls-tree", head, "--", path).decode().split()
    require(len(metadata) == 4 and metadata[:2] == ["100644", "blob"], "unsafe pinned blob")
    require(not blob_id or metadata[2] == blob_id, "pinned blob identity mismatch")
    raw = git("show", f"{head}:{path}")
    require(sha(raw) == digest, "tampered pinned bytes")
    if head == BASE_HEAD:
        require((ROOT / path).read_bytes() == raw, "base authority bytes changed")
    return raw


def authority() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    for head, tree in ((BASE_HEAD, BASE_TREE), (DONOR_HEAD, DONOR_TREE)):
        require(git("cat-file", "-t", head).strip() == b"commit", "wrong commit identity")
        require(
            git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "wrong tree identity"
        )
    require(
        git("rev-parse", f"{DONOR_HEAD}^").decode().strip() == DONOR_PARENT, "wrong donor parent"
    )
    loaded = {path: pinned_bytes(path) for path in PINS}
    donor, sealed, r30 = (decode(loaded[p]) for p in (DONOR_RESULT, BASE_RESULT, R30_RESULT))
    require(
        donor["JUDGE_MODE"] == "SELF_CHECK_ONLY"
        and donor["TASK_STATUS"] == "COMPLETE_SELF_CHECK_ONLY",
        "donor disposition altered",
    )
    require(
        donor["SOURCE_SHA256"] == PINS[f"src/lottolab/research/{DONOR_MODULE}.py"][2],
        "donor source/result link differs",
    )
    recorded = [
        obj(x) for x in items(obj(decode(loaded[S4_RESULT])["START_FAMILY"])["ROWS_ABOVE_CURSOR"])
    ]
    target = [row for row in recorded if row["PROFILE_ID"] == TARGET]
    require(
        len(target) == 1
        and target[0]["BOUND"] == 313396120
        and target[0]["TRIANGLE_CAP"] == CAP
        and target[0]["SOURCE"] == obj(obj(donor["PROFILE_CERTIFICATES"])[TARGET])["CAP_SOURCE"],
        "existing target row identity differs",
    )
    return donor, sealed, r30


def helper_identity() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in HELPERS:
        require(path.is_relative_to(ROOT), "helper outside isolated worktree")
        relative = path.relative_to(ROOT).as_posix()
        metadata = git("ls-tree", BASE_HEAD, "--", relative).decode().split()
        require(len(metadata) == 4 and metadata[:2] == ["100644", "blob"], "unsafe helper")
        raw = git("show", f"{BASE_HEAD}:{relative}")
        require(raw == path.read_bytes(), "helper differs from pinned base")
        out[relative] = sha(raw)
    return out


def target_degrees(pid: str = TARGET) -> tuple[int, ...]:
    require(pid == TARGET, "wrong target profile")
    d = split.profile_values(pid)
    require(len(d) == 20 and sum(d) == 66 and d.count(0) == 7, "support degrees differ")
    model = split.prior.r5
    require(
        (
            model.K20_TICKET_COUNT,
            model.K20_TICKET_CAPACITY,
            model.K20_LABEL_COUNT,
            model.K20_TRIPLE_SUPPORT_COUNT,
            model.K20_DOUBLE_SUPPORT_COUNT,
        )
        == (20, 6, 49, 22, 27),
        "support semantics differ",
    )
    require(official.r28.profile_s4_floor(d) == S4_BASE, "inherited S4 floor differs")
    return d


def multiplicity_proof(signs: Sequence[int] = (1, -1, 1, -1, 1)) -> dict[str, object]:
    require(tuple(signs) == (1, -1, 1, -1, 1), "incorrect Bonferroni signs")
    table: list[list[int]] = []
    for r in range(8):
        partial = sum(s * comb(r, k) for k, s in enumerate(signs, 1))
        excess = partial - int(r > 0)
        fourth7 = 7 * (r - comb(r, 2) + comb(r, 3) - int(r > 0)) - 4 * comb(r, 4)
        require(
            excess == (comb(r - 1, 5) if r else 0) and excess >= 0 and fourth7 >= 0,
            "unsafe moment inequality",
        )
        table.append([r, partial, int(r > 0), excess, fourth7])
    return {
        "R_CAP": comb(7, 2) // comb(3, 2),
        "SIGNS": list(signs),
        "TABLE": table,
        "S4_DIRECTION": "LOWER_BOUND_SUBTRACTED",
        "S5_DIRECTION": "UPPER_BOUND_ADDED",
    }


def local_profile(n: int, edges: set[Pair], packing: Sequence[Triple]) -> tuple[int, ...]:
    require(1 <= n <= 5 and edges <= set(combinations(range(n), 2)), "invalid local graph")
    remaining = set(edges)
    masks: list[int] = []
    for tau in packing:
        require(len(set(tau)) == 3 and tuple(sorted(tau)) == tau, "invalid triple")
        shadow = set(combinations(tau, 2))
        require(shadow <= remaining, "nonlinear or unsupported packing")
        remaining -= shadow
        masks.append(sum(1 << v for v in tau))
    masks.extend(sum(1 << v for v in edge) for edge in sorted(remaining))
    for v in range(n):
        used = sum(bool(mask & (1 << v)) for mask in masks)
        require(used <= 6, "local capacity exceeded")
        masks.extend([1 << v] * (6 - used))
    counts = Counter(masks)
    require(len(masks) <= 49, "local label pool exceeded")
    counts[0] = 49 - len(masks)
    return tuple(counts[mask] for mask in range(1 << n))


@cache
def selected_label_count(profile: tuple[int, ...]) -> int:
    """Small local DP, independent of donor code; counts seven-sets then specials."""
    n = len(profile).bit_length() - 1
    require(
        1 <= n <= 5 and len(profile) == 1 << n and sum(profile) == 49, "invalid local dimension"
    )
    require(all(type(c) is int and c >= 0 for c in profile), "invalid local counts")
    require(
        all(sum(c for m, c in enumerate(profile) if m & (1 << v)) == 6 for v in range(n)),
        "local ticket does not have six labels",
    )
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, (0,) * n): 1}
    for mask in sorted(range(1 << n), key=lambda m: (m.bit_count(), m), reverse=True):
        count = profile[mask]
        if not count:
            continue
        following: dict[tuple[int, tuple[int, ...]], int] = {}
        for (used, hits), ways in states.items():
            for take in range(min(count, 7 - used) + 1):
                hit = tuple(min(3, h + take * bool(mask & (1 << v))) for v, h in enumerate(hits))
                if sum(3 - h for h in hit) > 3 * (7 - used - take):
                    continue
                key = used + take, hit
                following[key] = following.get(key, 0) + ways * comb(count, take)
        states = following
    return 7 * states.get((7, (3,) * n), 0)


def s123_proof() -> dict[str, object]:
    s1 = 20 * 7 * sum(comb(6, k) * comb(43, 7 - k) for k in range(3, 7))
    pair = [
        selected_label_count(local_profile(2, set() if k == 0 else {(0, 1)}, ())) for k in range(2)
    ]
    s2 = 97 * pair[0] + 93 * pair[1]
    tri = [
        selected_label_count(local_profile(3, set(tuple(combinations(range(3), 2))[:k]), ()))
        for k in range(4)
    ]
    core = selected_label_count(local_profile(3, set(combinations(range(3), 2)), ((0, 1, 2),)))
    require(
        s1 == event.K20_S1 == 372228640 and s2 == event.K20_S2 == 63838600, "S1/S2 counts differ"
    )
    require(tri == [0, 0, 2800, 20272] and core == 7000, "S3 local counts differ")
    # W=N2+3T, N3(noncore)=T-22, and 22 core triples.
    require(
        tri[3] - 3 * tri[2] == 11872 and 22 * (core - tri[3]) == -291984, "S3 coefficients differ"
    )
    require(22 * (core - tri[3]) == -11872 * 22 - 30800, "S3 constant differs")
    return {
        "S1": s1,
        "S2": s2,
        "PAIR_WEIGHTS_0_1": pair,
        "TRIPLE_WEIGHTS_0_TO_3_EDGES": tri,
        "CORE_TRIPLE_WEIGHT": core,
    }


def s4_weights() -> dict[str, int]:
    pairs = set(combinations(range(4), 2))
    out: dict[str, int] = {}
    for name, edges, packing, expected in (
        ("K4_NO_TRIPLE", pairs, (), 679),
        ("K4_CONTAINED_TRIPLE", pairs, ((0, 1, 2),), 448),
        ("K4_MINUS_EDGE", pairs - {(0, 1)}, (), 112),
    ):
        profile = local_profile(4, edges, packing)
        weight = event.compressed_four_ticket_intersection_count(
            profile, pool_size=49, draw_size=6, outright_matches=3
        )
        require(weight == selected_label_count(profile) == expected, "S4 local weight differs")
        out[name] = weight
    return out


def local_identity_value(edges: set[Pair], packing: Sequence[Triple]) -> tuple[int, int, int]:
    common = [
        sum(all(tuple(sorted((u, v))) in edges for u in tau) for v in range(5) if v not in tau)
        for tau in packing
    ]
    common_pairs = sum(comb(m, 2) for m in common)
    two = int(len(packing) == 2 and len(edges) == 10)
    return common_pairs, two, 7 * (common_pairs + 2 * two)


@cache
def five_ticket_table() -> tuple[tuple[int, ...], ...]:
    pairs, triples = tuple(combinations(range(5), 2)), tuple(combinations(range(5), 3))
    # Exhaust all 2^10 triple subsets; no assumed 2-triple loop cutoff.
    packings: list[tuple[Triple, ...]] = []
    for mask in range(1 << len(triples)):
        packing = tuple(t for i, t in enumerate(triples) if mask >> i & 1)
        shadow = {e for tau in packing for e in combinations(tau, 2)}
        if len(shadow) == 3 * len(packing):
            packings.append(packing)
    require(max(map(len, packings)) == 2, "five-ticket packing maximum differs")
    out: list[tuple[int, ...]] = []
    for packing in sorted(packings, key=lambda p: (len(p), p)):
        shadow = {e for tau in packing for e in combinations(tau, 2)}
        free = tuple(e for e in pairs if e not in shadow)
        for mask in range(1 << len(free)):
            edges = shadow | {e for i, e in enumerate(free) if mask >> i & 1}
            common, two, predicted = local_identity_value(edges, packing)
            exact = selected_label_count(local_profile(5, edges, packing))
            require(predicted == exact, "S5 local identity failed")
            edge_mask = sum(1 << i for i, e in enumerate(pairs) if e in edges)
            triple_mask = sum(1 << i for i, t in enumerate(triples) if t in packing)
            out.append((edge_mask, triple_mask, len(packing), common, two, exact))
    require(len(out) == len({row[:2] for row in out}) == 2544, "local pattern coverage differs")
    return tuple(out)


def s5_proof(donor: Mapping[str, object]) -> dict[str, object]:
    table = five_ticket_table()
    counts = [sum(row[2] == k for row in table) for k in range(3)]
    histogram = [
        [k, weight, sum(row[2] == k and row[5] == weight for row in table)]
        for k in range(3)
        for weight in sorted({row[5] for row in table if row[2] == k})
    ]
    digest = sha(json.dumps(table, sort_keys=True).encode())
    original = obj(donor["S5_IDENTITY"])
    require(
        counts == original["LOCAL_CASE_COUNTS_0_1_2_TRIPLES"] == [1024, 1280, 240]
        and histogram == original["LOCAL_WEIGHT_HISTOGRAM"]
        and digest == original["LOCAL_WEIGHT_TABLE_SHA256"],
        "donor local identity differs",
    )
    d = target_degrees()
    thresholds: list[list[int]] = []
    for k in range(1, 7):
        high, low = [v for v in d if v >= k], [v for v in d if 0 < v < k]
        incidence = sum(high) // 3 if len(high) >= 3 else 0
        low_cap = 22 - max(low, default=0)
        thresholds.append([k, len(high), sum(high), incidence, low_cap, min(incidence, low_cap)])
    weights = [comb(4 + k, 2) for k in range(1, 7)]
    common = 22 * weights[0] + sum(
        thresholds[k - 1][5] * (weights[k - 1] - weights[k - 2]) for k in range(2, 7)
    )
    n2 = sum(comb(v, 2) for v in d)
    cap = 7 * (common + 2 * n2)
    require((common, n2, cap) == (792, 135, 7434), "S5 upper bound differs")
    published = obj(obj(obj(donor["PROFILE_CERTIFICATES"])[TARGET])["DEGREE_S5_PROOF"])
    require(
        published["THRESHOLD_CAPS"] == thresholds and published["S5_CAP"] == cap,
        "published degree proof differs",
    )
    return {
        "IDENTITY": original["IDENTITY"],
        "LOCAL_CASE_COUNT": len(table),
        "LOCAL_COUNTS": counts,
        "LOCAL_HISTOGRAM": histogram,
        "LOCAL_TABLE_SHA256": digest,
        "THRESHOLD_CAPS": thresholds,
        "COMMON_PAIR_SUM_CAP": common,
        "N_2T_CAP": n2,
        "S5_CAP": cap,
        "TWO_TRIPLE_K5_WEIGHT": 28,
    }


def cap_authority(proof: Mapping[str, object], pid: str = TARGET, cap: int = CAP) -> None:
    d = target_degrees(pid)
    require(type(cap) is int and cap == CAP, "wrong cap")
    w = sum(comb(6 + v, 2) for v in d)
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": 3627,
        "PROFILE_IDS": [TARGET],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "ROUTE": official.CAP_SOURCE_ROUTE,
        "WEDGE_COUNT": w,
        "TARGET_TRIANGLE_CAP": cap,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap,
        "OPEN_WEDGE_CEILING_REFUTED": w - 3 * (cap + 1),
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": w - 3 * (cap + 1) + 1,
        "EXTERNAL_TIMEOUT_EXIT_CODE": 0,
    }
    require(
        all(type(proof.get(k)) is type(v) and proof.get(k) == v for k, v in expected.items()),
        "cap authority mismatch",
    )
    require(official.r28.r26.accepted_cap(proof, (d,), cap) == cap, "cap not accepted")


def moment_bounds(s3: int, s4_floor: int, s5_cap: int) -> tuple[int, int]:
    fixed = event.K20_S1 - event.K20_S2 + s3
    exact = Fraction(fixed) - Fraction(4 * s4_floor, 7)
    return -(-exact.numerator // exact.denominator), fixed - s4_floor + s5_cap


def original_terms() -> list[Term]:
    d = target_degrees()
    g = tuple(6 + v for v in d)
    w, j, b = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g), sum(v * (4 + v) for v in d)
    out: list[Term] = []
    for t in range(22, CAP + 1):
        k4 = max(0, -(-(j - (max(g) - 2) * (w - 3 * t)) // 4))
        contained = min(k4, b // 3)
        s4 = max(S4_BASE, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound, _ = moment_bounds(s3, s4, 0)
        out.append((t, bound, k4, contained, s4, s3))
    require(
        out == split.route_b_terms(d, CAP, S4_BASE) == official.route_b_envelope(d, CAP, S4_BASE),
        "existing T terms differ",
    )
    return out


def envelope(donor: Mapping[str, object], s5_cap: int) -> dict[str, object]:
    old = original_terms()
    t, before, k4, a, s4, s3 = old[-1]
    fourth, fifth = moment_bounds(s3, s4, s5_cap)
    require(fourth == before and t == CAP, "cap term differs")
    terms = [*old[:-1], (t, min(before, fifth), k4, a, s4, s3)]
    cert = obj(obj(donor["PROFILE_CERTIFICATES"])[TARGET])
    lower_hash = sha(json.dumps(old[:-1], sort_keys=True).encode())
    require(
        [list(term) for term in terms] == cert["ALL_T_TERMS"]
        and lower_hash == cert["RETAINED_TERMS_SHA256"],
        "donor envelope or lower terms differ",
    )
    best = max(terms, key=lambda row: (row[1], row[0]))
    require(
        (len(terms), best[0], best[1], terms[-1][1]) == (243, 263, 313387352, 313281346),
        "complete envelope differs",
    )
    return {
        "OLD_TERMS": [list(row) for row in old],
        "ALL_T_TERMS": [list(row) for row in terms],
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "COMPLETE_T_RANGE": [22, CAP],
        "TERM_COUNT": len(terms),
        "MAX_T": best[0],
        "FULL_PROFILE_BOUND": best[1],
        "T264_TERM_BOUND": fifth,
        "OLD_PROFILE_BOUND": max(row[1] for row in old),
        "PROFILE_DELTA": max(row[1] for row in old) - best[1],
        "LOWER_T_SHA256": lower_hash,
        "CHANGED_FIELDS": [[CAP, "BOUND"]],
        "ALL_T_BONFERRONI5_ADOPTION": "OUT_OF_SCOPE_NOT_VERIFIED",
    }


def family_effect(sealed: Mapping[str, object], bound: int) -> dict[str, object]:
    bounds = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(sealed["CURSOR"])
    base.validate_cursor(cursor, cursor)
    require(len(bounds) == 4647 and bounds[TARGET] == 313396120, "base projection differs")
    before = sha(prior.projection(bounds))
    require(before == sealed["BOUNDS_SHA256_AFTER"], "base ledger digest differs")
    current = {**bounds, TARGET: bound}
    owner = "66665555554421100000"
    hypothetical = split.route_b_terms(split.profile_values(owner), 249, 112)
    t249 = max(row[1] for row in hypothetical)
    projected_before = {**bounds, owner: t249}
    projected = {**projected_before, TARGET: bound}
    views = {
        name: prior.family(rows, cursor)
        for name, rows in (
            ("BASE", bounds),
            ("CURRENT_BASE_WITH_TARGET", current),
            ("HYPOTHETICAL_T249_ONLY", projected_before),
            ("HYPOTHETICAL_T249_AND_TARGET", projected),
        )
    }
    require(
        views["BASE"] == views["CURRENT_BASE_WITH_TARGET"] == (313397860, [owner])
        and views["HYPOTHETICAL_T249_ONLY"][0] == 313396120
        and views["HYPOTHETICAL_T249_AND_TARGET"]
        == (313395448, ["66555555555441000000", "66555555555522000000"]),
        "family projection differs",
    )
    for name, rows in (
        ("CURRENT_BASE_WITH_TARGET", current),
        ("HYPOTHETICAL_T249_AND_TARGET", projected),
    ):
        all_bounds = [*rows.values(), integer(cursor["BOUND"])]
        require(max(all_bounds) == views[name][0], "independent family maximum differs")
    require(before == sha(prior.projection(bounds)), "input ledger mutated")
    return {
        "VIEWS": {
            name: {"BOUND": value, "OWNERS": owners} for name, (value, owners) in views.items()
        },
        "BASE_LEDGER_SHA256_BEFORE": before,
        "BASE_LEDGER_SHA256_AFTER": before,
        "OTHER_4646_BOUNDS_SHA256": sha(
            prior.projection({p: b for p, b in bounds.items() if p != TARGET})
        ),
        "RESOLVED_ROWS": 4647,
        "CURSOR_PROFILES": cursor["PROFILE_COUNT"],
        "HYPOTHETICAL_T249_PROFILE_BOUND": t249,
        "PROJECTED_DELTA_VS_T249": 672,
        "T249_AUTHORITY": "HYPOTHETICAL_CAP_ONLY_NOT_CERTIFIED_OR_ADOPTED",
        "SHARED_LEDGER_ADOPTION": "NONE",
        "BASE_CAVEATS_VERBATIM": sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "BASE_ORIGINAL_TASK_STATUS": sealed["TASK_STATUS"],
    }


def compute_result() -> dict[str, object]:
    helpers = helper_identity()
    donor, sealed, r30 = authority()
    proof = obj(items(r30["GROUP_ATTEMPTS"])[3627])
    cap_authority(proof)
    published = obj(obj(donor["PROFILE_CERTIFICATES"])[TARGET])
    require(
        proof == published["CAP_SOURCE_IDENTITY"] and published["S4_BASE"] == S4_BASE,
        "donor/R30 cap identity differs",
    )
    s5 = s5_proof(donor)
    terms = envelope(donor, integer(s5["S5_CAP"]))
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "MATHEMATICAL_CERTIFICATE_REQUIRES_EXACT_TREE_FRESH_JUDGE",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_JUDGE_COMMIT_MESSAGE_VERBATIM": prior.commit_identity(BASE_HEAD, BASE_TREE),
        "DONOR_HEAD": DONOR_HEAD,
        "DONOR_TREE": DONOR_TREE,
        "DONOR_PARENT": DONOR_PARENT,
        "DONOR_ORIGINAL_STATUS": {
            "JUDGE_MODE": donor["JUDGE_MODE"],
            "TASK_STATUS": donor["TASK_STATUS"],
        },
        "BLOB_PINS": {
            p: {"HEAD": h, "BLOB": git("rev-parse", f"{h}:{p}").decode().strip(), "SHA256": s}
            for p, (h, _, s) in PINS.items()
        },
        "HELPER_SHA256": helpers,
        "SOURCE_SHA256": sha(Path(__file__).read_bytes()),
        "PROOF": __doc__,
        "PROFILE_ID": TARGET,
        "TRIANGLE_CAP": CAP,
        "CAP_AUTHORITY": proof,
        "MODEL": {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "POOL": 49,
            "TRIPLES": 22,
            "PAIRS": 27,
            "PAIR_LINEARITY": True,
        },
        "BONFERRONI_PROOF": multiplicity_proof(),
        "S123": s123_proof(),
        "S4_WEIGHTS": s4_weights(),
        "S5_PROOF": s5,
        "ENVELOPE": terms,
        "FAMILY_EFFECT": family_effect(sealed, integer(terms["FULL_PROFILE_BOUND"])),
        "SOLVER_CALLS": 0,
        "PORTFOLIO_ENUMERATIONS": 0,
        "SHARED_LEDGER_WRITES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def verify_result(value: Mapping[str, object]) -> None:
    require(render(value) == render(compute_result()), "tampered formal certificate")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if args.verify:
        require(RESULT_PATH.read_bytes() == raw, "sealed result bytes differ")
    else:
        require(not RESULT_PATH.exists(), "result already exists")
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(
        json.dumps(
            {
                "STATUS": "PASS",
                "S5_BOUND": obj(result["S5_PROOF"])["S5_CAP"],
                "ENVELOPE": {
                    k: obj(result["ENVELOPE"])[k]
                    for k in ("FULL_PROFILE_BOUND", "MAX_T", "T264_TERM_BOUND", "PROFILE_DELTA")
                },
            }
        )
    )


if __name__ == "__main__":
    main()
