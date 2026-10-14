"""Universal conditional bounds for the three exact next-owner profiles.

MODEL AND GOODMAN. Twenty tickets each use six distinct labels: 22 labels
have triple supports, 27 pair supports, and ticket pairs share at most one
label. For triple degrees d, g=6+d, sum d=66, sum g=186, and e(G)=93.
The 22 supports give edge-disjoint triangles, hence 22<=T(G)<=W//3.
Every nonhomogeneous three-set contributes two to sum g(19-g), while a
homogeneous three-set contributes zero. Thus T(G)+T(H)=1140-sum g(19-g)/2
for H=complement(G). All histograms and constants are derived per profile.

GENERAL K/Z SPLIT. Put k=|K|, z=|Z|, K={d>0}, Z={d=0}, k+z=20.
Let sigma_x=|N_G(x) intersect Z| and zeta_v=|N_G(v) intersect K|.
Every K-Z edge uses a pair label, so 0<=sigma_x<=min(z,6-d_x).
Every Z vertex has degree six, so max(0,7-z)<=zeta_v<=min(k,6).
Both crossing sums equal r. For M=H[K], N=H[Z], their degrees are
  m_x=k-7-d_x+sigma_x, n_v=z-7+zeta_v,
  2e(M)=k(k-7)-66+r, 2e(N)=z(z-7)+r.
For an M edge xy the H common neighbours in Z number exactly
z-sigma_x-sigma_y+c_Z(xy), where c_Z is the cardinality of the common
G-neighbours in Z. For an N edge uv the analogous count is
k-zeta_u-zeta_v+c_K(uv). Classifying triangles by their two shores yields
  T(H)=3z(k-11)+10r-sum sigma*m-sum zeta*n+P,
  P=T(M)+T(N)+sum_E(M) c_Z+sum_E(N) c_K.
All FOUR remainder contributions are nonnegative cardinalities. In particular
A/C use m=8-d+sigma, n=zeta-2, constant 60; B uses m=7-d+sigma,
n=zeta-1, constant 54. Equal W does not identify a split theorem.

REMAINDER LOWER BOUNDS. For any simple graph F on n vertices with degrees
a_i and e edges, and a subset S of size s, at most sum_{outside S} a_i
edges have an outside endpoint. Therefore
  e(F[S])>=I(a,s)=max(0,e-sum of the n-s largest degrees).
Replacing the actual outside-degree sum by its maximum lowers this lower
bound. Double-counting the incidence remainders gives exactly
  sum_E(N)c_K=sum_x e(N[N_G(x) intersect Z]),
  sum_E(M)c_Z=sum_v e(M[N_G(v) intersect K]).
Thus their respective lower bounds are sum_x I(n,sigma_x) and
sum_v I(m,zeta_v). These are separate contributions, so may be added.

For an edge ij of F, common neighbours >=a_i+a_j-n. Summing gives
3T(F)>=sum a_i^2-ne, hence the nonnegative integer ceiling is a lower
bound. A stronger bound uses any prefix L of h largest degrees. Crossing
edges <=sum_{i outside L} min(h,a_i), so
  e(F[L])>=ell=max(0,ceil((sum_L a_i-sum_outside min(h,a_i))/2)).
Give every possible pair in L weight max(0,a_i+a_j-n). Their actual edge
weight sum is at least the sum of the ell smallest weights (weights are
nonnegative). If C is the common-neighbour count over edges in L, then
C=3T(F[L])+T(two vertices in L). Consequently
  T(F)>=C-2T(F[L])>=sum of ell smallest weights-2*C(h,3).
Take MAX with zero and the global ceiling, over every h. This never asserts
that independently minimal edges or neighbourhoods can occur together.
Apply these bounds to all four parts of P; subtracting their sum raises
the G upper bound relative to subtracting the true P, hence is sound.

UNIVERSAL FINITE RELAXATION. Enumerate every sigma multiset in every equal-d
class and every sorted zeta in its derived range. Retain only induced degree
sequences satisfying all simple-graph edge-count inequalities, crossing-sum
equality and all bipartite subset edge-count inequalities. All are necessary:
the first inequalities count edges from the highest-degree vertices, and the
second count edges from any k vertices on a bipartite shore. Every legal
realization maps to a retained state. Relabeling equal-d vertices and Z
preserves every score and bound. We omit simultaneous graph realization and
triple-decomposition constraints, which enlarges the feasible set. Maximizing
the derived upper expression over EVERY retained state, with all argmax
retained, proves the caps; this is not a sample maximum of actual T. No full
support graph or portfolio is enumerated. Supersets with remainder omitted
are also recorded as ablations, never adopted as stronger certificates.

BASE ENVELOPES. Use the pinned Base Route-B implementation and its full
22-source closure. At each true t, open wedges o=W-3t. Each nonedge in a
vertex neighbourhood spoils at most g_max-2 triples, giving
q>=max(0,ceil((sum C(g,3)-(g_max-2)o)/4)). The larger spoil coefficient
weakens the lower bound. A K4 contains at most one triple support, and their
number is at most floor(sum d(g-2)/3)=A_max. The fixed local weights are
448 with a triple and 679 without. Non-K4 S4 terms are nonnegative. Thus
S4>=679q-231*min(q,A_max), increasing in q; combine existing floors by MAX.
Query the exact Base S4 authority for each profile. C's inherited floor at
t=264 is preserved ONLY there, without extending its adoption to other t.
S5 is absent for these exact profiles and unused. S3=2800o+20272(t-22)+154000.
At most seven tickets win in one seven-label outcome, since chosen winning
three-subsets use distinct pairs; 3r<=C(7,2). For integer r=0..7,
1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)C(r,4). Subtract the LOWER S4 bound and
round the resulting Fraction UP. Every t in both closed intervals is
evaluated; no assumption of monotonicity or attainability is made.

AUTHORITY AND SCOPE. Replay the complete R2/two-owner/single-owner/cursor
upstream, rederive the intervening three-row certificate, and byte-replay
the direct certificate. Reproduce old caps from accepted pinned R30
refutations, NB and class bounds, not by inferring caps from row bounds.
C's adopted cap-term S4 remains a fixed inherited certificate. Aggregate all
4647 resolved and 197 cursor rows before and after changing only A/B/C.
The 282 exclusions, failures and historical caveats remain inherited with
immutable byte pins, never recertified or upgraded. CONDITIONAL_PROJECTION
does not assert canonical adoption, global optimality or prediction gains.
The one fresh Judge verdict is external to this self-hashed result JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_cursor_41_owner_shared_bound_r1 as upstream
from . import b649_next_frontier_three_profile_bound_r1 as direct
from . import b649_next_resolved_frontier_shared_bound_r1 as middle

TASK_ID = "B649_NEXT_TWO_OWNER_SHARED_BOUND_R1"
INPUT_HEAD = "0f0c9a32dbed811eddbefc55fd5093a8ee0e914d"
INPUT_TREE = "2092a1dc434e210f28455f9de3c59947217db889"
BASE_HEAD, BASE_TREE = direct.BASE_HEAD, direct.BASE_TREE
BASE_RESULT, BASE_SHA = direct.BASE_RESULT, direct.BASE_SHA
INPUT_RESULT = direct.RESULT
INPUT_SHA = "9769ee3e125ce8b3e66b810f9683d28b9e93c06e601b36959f86c0d3a2812c76"
PROFILE_IDS = ("66555555555521100000", "66655555554432000000", "66666555554411100000")
SOURCE = "src/lottolab/research/b649_next_two_owner_shared_bound_r1.py"
TEST = "tests/unit/test_b649_next_two_owner_shared_bound_r1.py"
RESULT = direct.DIRECTORY + "b649-next-two-owner-shared-bound-r1-result.json"
ROOT = Path(__file__).resolve().parents[3]
require, sha, render = direct.require, direct.sha, direct.render
git, blob, pinned_blob = direct.git, direct.blob, direct.pinned_blob
ceil_div, graphical, bipartite_necessary = (
    direct.ceil_div,
    direct.graphical,
    direct.bipartite_necessary,
)
family_summary = direct.family_summary
UPSTREAM_CODE_PINS = {
    direct.SOURCE: "7fe17d688b9d23fe971178f751c22558c8f4da156b82a4c50607db216bf63814",
    direct.TEST: "abb9ed01ec7ad6266a6b8c783d9c6f5f4d1174c4b970975e445938794e1f7180",
    middle.SOURCE: "c93c5a421ebf78a208d47849b1198f3756092e17fbfa9cf7a1aa6a83f4e015a7",
    middle.TEST: "00b1167cc2accb7c5b4c878a871ca2d5193230786db7f786bbdd2dc5345c1e8a",
    upstream.SOURCE: "c1e65bd5300fbd83be743e0a963622bd2686d23a855039cadadc6deb8f514e65",
    upstream.TEST: "61d3ed10d7c0b8b94c3a8da540a1a3a1e229978f8204ada63ccd3b32a8e79fa7",
}


def verify_identity(candidate="HEAD", repo=ROOT):
    require(sys.version_info >= (3, 13), "Python 3.13 required")
    for head, tree in ((INPUT_HEAD, INPUT_TREE), (BASE_HEAD, BASE_TREE)):
        require(git("rev-parse", head + "^{tree}", repo=repo) == tree, "Git TREE pin")
    head = git("rev-parse", candidate, repo=repo)
    if head == INPUT_HEAD:
        return "INPUT_HEAD_WITH_WORKING_CANDIDATE"
    parents = git("rev-list", "--parents", "-n", "1", head, repo=repo).split()
    require(parents[1:] == [INPUT_HEAD], "direct single-parent child required")
    changed = git("diff-tree", "--no-commit-id", "--name-status", "-r", head, repo=repo)
    require(
        sorted(changed.splitlines()) == sorted(f"A\t{p}" for p in (SOURCE, TEST, RESULT)),
        "exactly three authorized additions required",
    )
    return "FIXED_DIRECT_CHILD"


@cache
def profile_facts(pid):
    require(pid in PROFILE_IDS, "wrong exact profile")
    d = tuple(map(int, pid))
    require(len(d) == 20 and tuple(sorted(d, reverse=True)) == d, "histogram order/size")
    require(all(0 <= x <= 6 for x in d) and sum(d) == 66, "triple degree histogram")
    g = tuple(6 + x for x in d)
    k, z = sum(x > 0 for x in d), d.count(0)
    numerator = sum(x * (19 - x) for x in g)
    require(sum(g) == 186 and numerator % 2 == 0, "degree/Goodman integrality")
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "D_HISTOGRAM": {str(x): n for x, n in sorted(Counter(d).items())},
        "DEGREE_SUM_D": sum(d),
        "DEGREE_SUM_G": sum(g),
        "EDGES": sum(g) // 2,
        "WEDGES": sum(comb(x, 2) for x in g),
        "GOODMAN": comb(20, 3) - numerator // 2,
        "K": k,
        "Z": z,
        "M_DEGREE_OFFSET": k - 7,
        "N_DEGREE_OFFSET": z - 7,
        "M_EDGE_SUM_CONSTANT": k * (k - 7) - sum(d),
        "N_EDGE_SUM_CONSTANT": z * (z - 7),
        "SPLIT_H_CONSTANT": 3 * z * (k - 11),
        "ZETA_MIN": max(0, 7 - z),
        "ZETA_MAX": min(k, 6),
        "J": sum(comb(x, 3) for x in g),
        "G_MAX": max(g),
        "A_MAX": sum(x * (x + 4) for x in d) // 3,
        "PAIR_DEGREES": [6 - x for x in d],
        "ASSUMPTIONS": {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "LABELS": 49,
            "TRIPLE_LABELS": 22,
            "PAIR_LABELS": 27,
            "PAIR_LINEARITY": True,
        },
    }


def validate_facts(pid, claimed):
    require(render(claimed) == render(profile_facts(pid)), "profile/split facts mismatch")


def induced_edge_lower(degrees, subset_size):
    require(type(subset_size) is int and 0 <= subset_size <= len(degrees), "subset size")
    ds = sorted(degrees, reverse=True)
    return max(0, sum(ds) // 2 - sum(ds[: len(ds) - subset_size]))


@cache
def triangle_lower(degrees):
    ds = sorted(degrees, reverse=True)
    n, e = len(ds), sum(ds) // 2
    lower = max(0, ceil_div(sum(x * x for x in ds) - n * e, 3))
    for h in range(1, n + 1):
        ell = max(0, ceil_div(sum(ds[:h]) - sum(min(h, x) for x in ds[h:]), 2))
        weights = sorted(max(0, a + b - n) for a, b in combinations(ds[:h], 2))
        require(ell <= len(weights), "impossible necessary degree sequence")
        lower = max(lower, sum(weights[:ell]) - 2 * comb(h, 3))
    return lower


@cache
def zeta_sequences(z):
    return tuple(
        ze
        for ze in combinations_with_replacement(range(max(0, 7 - z), 7), z)
        if graphical(tuple(6 - x for x in ze))
    )


@cache
def relaxation(pid):
    f = profile_facts(pid)
    k, z = f["K"], f["Z"]
    groups = tuple(sorted(Counter(x for x in f["D"] if x).items(), reverse=True))
    choices = [tuple(combinations_with_replacement(range(min(z, 6 - d) + 1), n)) for d, n in groups]
    states, signatures = [], 0
    for parts in product(*choices):
        signatures += 1
        ds = tuple(d for (d, _), ss in zip(groups, parts, strict=True) for _ in ss)
        sigma = tuple(s for ss in parts for s in ss)
        m = tuple(k - 7 - d + s for d, s in zip(ds, sigma, strict=True))
        if not graphical(m):
            continue
        r = sum(sigma)
        ss = sum(a * b for a, b in zip(sigma, m, strict=True))
        for ze in zeta_sequences(z):
            if not bipartite_necessary(sigma, ze):
                continue
            n = tuple(z - 7 + x for x in ze)
            zs = sum(a * b for a, b in zip(ze, n, strict=True))
            raw = f["GOODMAN"] - f["SPLIT_H_CONSTANT"] - 10 * r + ss + zs
            ck = sum(induced_edge_lower(n, s) for s in sigma)
            cz = sum(induced_edge_lower(m, q) for q in ze)
            tm, tn = triangle_lower(m), triangle_lower(n)
            weak_tm = max(0, ceil_div(sum(x * x for x in m) - k * sum(m) // 2, 3))
            weak_tn = max(0, ceil_div(sum(x * x for x in n) - z * sum(n) // 2, 3))
            states.append(
                {
                    "R": r,
                    "SIGMA_BY_D": [[d, list(s)] for (d, _), s in zip(groups, parts, strict=True)],
                    "ZETA": list(ze),
                    "M_DEGREES": list(m),
                    "N_DEGREES": list(n),
                    "SIGMA_SCORE": ss,
                    "ZETA_SCORE": zs,
                    "REMAINDER_LOWER": {"T_M": tm, "T_N": tn, "C_K": ck, "C_Z": cz},
                    "WITHOUT_REMAINDER": raw,
                    "WITHOUT_PREFIX_TRIANGLE_BOUND": raw - ck - cz - weak_tm - weak_tn,
                    "UPPER": raw - ck - cz - tm - tn,
                }
            )
    require(states, "empty necessary-condition relaxation")
    cap = max(s["UPPER"] for s in states)
    return {
        "CAP": cap,
        "SIGMA_SIGNATURES": signatures,
        "ZETA_MULTISET_COUNT": len(zeta_sequences(z)),
        "RETAINED_STATE_COUNT": len(states),
        "ALL_RETAINED_STATES": states,
        "STATES_SHA256": sha(render(states)),
        "ALL_ARGMAX": [s for s in states if s["UPPER"] == cap],
        "PER_R_MAXIMUM": {
            str(r): max(s["UPPER"] for s in states if s["R"] == r)
            for r in sorted({s["R"] for s in states})
        },
        "ABLATION_CAPS": {
            key: max(s[key] for s in states)
            for key in ("WITHOUT_REMAINDER", "WITHOUT_PREFIX_TRIANGLE_BOUND", "UPPER")
        },
        "REALIZABILITY": "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION",
    }


@cache
def replay_upstream(repo=ROOT):
    for path, digest in UPSTREAM_CODE_PINS.items():
        require(
            (ROOT / path).read_bytes() == pinned_blob(INPUT_HEAD, path, digest, repo),
            "upstream code identity",
        )
    pins = upstream.r2.source_pins()
    cursor = upstream.compute_result()
    require(render(cursor) == upstream.RESULT.read_bytes(), "full upstream byte replay")
    require(
        git("rev-parse", middle.INPUT_HEAD + "^{tree}", repo=repo) == middle.INPUT_TREE,
        "middle input TREE pin",
    )
    mid = json.loads(pinned_blob(direct.INPUT_HEAD, direct.INPUT_RESULT, direct.INPUT_SHA, repo))
    require(mid["RESOLVED_ROWS_BEFORE"] == cursor["RESOLVED_ROW_BOUNDS"], "middle resolved input")
    require(
        mid["CURSOR_197_PRESERVED"]["ROW_BOUNDS"] == cursor["CURSOR_ROW_BOUNDS_AFTER"],
        "middle cursor input",
    )
    require(
        family_summary(mid["RESOLVED_ROWS_BEFORE"], cursor["CURSOR_ROW_BOUNDS_AFTER"])
        == mid["FAMILY_BEFORE"],
        "middle before aggregation",
    )
    zs = middle.zeta_graphical_sequences()[1]
    rows = dict(mid["RESOLVED_ROWS_BEFORE"])
    for pid in mid["FRONTIER_OWNER_IDS"]:
        p = mid["PROFILES"][pid]
        require(middle.profile_facts(pid) == p["PROFILE_FACTS"], "middle histogram replay")
        require(middle.relaxed_cap(pid, zs) == p["RELAXATION_CAP"], "middle theorem replay")
        old_cap, old_terms = middle.unique_old_cap(pid, rows[pid], p["INHERITED_S4_FLOOR"])
        require(
            old_cap == p["OLD_EFFECTIVE_T_CAP_RECONSTRUCTED_FROM_INPUT_BOUND"],
            "middle old cap replay",
        )
        require(
            [list(t) for t in old_terms if t[1] == rows[pid]] == p["OLD_ALL_ARGMAX"],
            "middle old argmax replay",
        )
        terms = middle.envelope(pid, p["NEW_SHARED_T_CAP"], p["INHERITED_S4_FLOOR"])
        require([list(t) for t in terms] == p["NEW_ALL_T_TERMS"], "middle complete envelope")
        rows[pid] = max(t[1] for t in terms)
        require(rows[pid] == p["NEW_ROW_BOUND"], "middle row bound")
    require(
        rows == mid["RESOLVED_ROWS_AFTER"]
        and family_summary(rows, cursor["CURSOR_ROW_BOUNDS_AFTER"]) == mid["FAMILY_AFTER"],
        "middle complete family replay",
    )
    direct.verify_result(INPUT_HEAD, repo)
    fixed = json.loads(pinned_blob(INPUT_HEAD, INPUT_RESULT, INPUT_SHA, repo))
    require(fixed["RESOLVED_ROWS_BEFORE"] == rows, "direct upstream ledger")
    return fixed, {
        "R2_TWO_OWNER_SINGLE_OWNER_CURSOR": "BYTE_REPLAYED_UNMODIFIED",
        "INTERVENING_THREE_ROW_CERTIFICATE": "THEOREM_ALL_TERMS_AND_COMPLETE_LEDGER_REPLAYED",
        "DIRECT_CERTIFICATE": "BYTE_REPLAYED_UNMODIFIED",
        "UPSTREAM_CODE_SHA256": UPSTREAM_CODE_PINS,
        "BASE_EVALUATOR_SOURCE_CLOSURE_SHA256": pins,
        "BASE_EVALUATOR_SOURCE_COUNT": len(pins),
        "INTERMEDIATE_INPUT_HEAD": middle.INPUT_HEAD,
        "INTERMEDIATE_INPUT_TREE": middle.INPUT_TREE,
        "INTERMEDIATE_HEAD": direct.INPUT_HEAD,
        "INTERMEDIATE_TREE": direct.INPUT_TREE,
        "INTERMEDIATE_RESULT_SHA256": direct.INPUT_SHA,
        "HISTORICAL_SOLVERS_RERUN": False,
    }


def base_authority(repo=ROOT):
    base = json.loads(pinned_blob(BASE_HEAD, BASE_RESULT, BASE_SHA, repo))
    refs = upstream.decode(upstream.blob(BASE_HEAD, upstream.r2.R30_PATH, upstream.r2.R30_SHA))
    authority = {}
    for pid in PROFILE_IDS:
        d = tuple(map(int, pid))
        records = [
            a
            for a in refs["GROUP_ATTEMPTS"]
            if a.get("PROFILE_IDS") == [pid] and a.get("STATUS") == "INFEASIBLE"
        ]
        require(records, "missing exact-profile R30 authority")
        ref = min(records, key=lambda a: a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        accepted = ref["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]
        require(
            upstream.route.r28.r26.accepted_cap(ref, (d,), accepted) == accepted,
            "Base rejected R30 cap",
        )
        nb, cls = upstream.r2.nb.profile_nb_cap(d)[2], upstream.r2.nb.r18_cap(d)
        floor = upstream.route.r28.profile_s4_floor(d)
        require(
            pid not in base["CERTIFICATES_ADOPTED"]
            and pid not in base["PROFILE_CERTIFICATES"]
            and base["INHERITED_TARGET_BONFERRONI_5"]["PROFILE_ID"] != pid
            and base["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED",
            "unexpected adopted target S5",
        )
        authority[pid] = {
            "ACCEPTED_R30_CAP": accepted,
            "R30_ATTEMPT": ref,
            "R30_RESULT_SHA256": upstream.r2.R30_SHA,
            "NB_CAP": nb,
            "CLASS_CAP": cls,
            "OLD_CAP": min(accepted, nb, cls),
            "S4_BASE": floor,
            "S4_BY_T": {},
            "S5_USED": False,
        }
    preserved = base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"][
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM"
    ]["DONOR_STATUS_SNAPSHOTS_VERBATIM"]["BASE_AUTHORITY"]
    cert = preserved["INHERITED_CAVEATS"]["SIX_ROW_AUTHORITY_VERBATIM"]["CERTIFICATE_F"]
    require(
        cert["PROFILE_ID"] == PROFILE_IDS[2] and cert["STATUS"] == "PASS",
        "inherited C cap-term S4 certificate",
    )
    t, s4 = cert["LOAD_BEARING_T"], cert["NEW_S4_FLOOR"]
    require(t == authority[PROFILE_IDS[2]]["OLD_CAP"], "C floor adoption scope")
    authority[PROFILE_IDS[2]]["S4_BY_T"][str(t)] = s4
    return base, authority, cert


def envelope(pid, cap, auth):
    f = profile_facts(pid)
    require(type(cap) is int and 22 <= cap <= f["WEDGES"] // 3, "T cap")
    terms = []
    for t in range(22, cap + 1):
        floor = max(auth["S4_BASE"], auth["S4_BY_T"].get(str(t), 0))
        term = upstream.route.envelope_term(tuple(f["D"]), t, floor, f["A_MAX"])
        terms.append(list(term))
    return terms


def compute_result(candidate="HEAD", repo=ROOT):
    mode = verify_identity(candidate, repo)
    fixed, replay = replay_upstream(repo)
    resolved, cursor = fixed["RESOLVED_ROWS_AFTER"], fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    before = family_summary(resolved, cursor)
    require(
        before == fixed["FAMILY_AFTER"]
        and before["MAXIMUM"] == 313392128
        and before["ALL_MAX_OWNERS"] == sorted(PROFILE_IDS[:2])
        and before["NEXT_DISTINCT_BOUND"] == 313391920
        and before["ALL_NEXT_DISTINCT_OWNERS"] == [PROFILE_IDS[2]]
        and before["CURSOR_MAXIMUM"] == 313391784,
        "complete input family frontier",
    )
    base, auth, c_cert = base_authority(repo)
    after_rows, profiles = dict(resolved), {}
    for pid in PROFILE_IDS:
        a, theorem = auth[pid], relaxation(pid)
        old = envelope(pid, a["OLD_CAP"], a)
        require(
            max(t[1] for t in old) == resolved[pid] == base["RESOLVED_ROW_BOUNDS"][pid],
            "old full Base envelope replay",
        )
        if pid == PROFILE_IDS[2]:
            require(old == c_cert["ALL_T_TERMS"], "complete inherited C envelope replay")
        cap = min(a["OLD_CAP"], theorem["CAP"], profile_facts(pid)["WEDGES"] // 3)
        new = envelope(pid, cap, a)
        bound = max(t[1] for t in new)
        after_rows[pid] = min(resolved[pid], bound)
        profiles[pid] = {
            "FACTS": profile_facts(pid),
            "RELAXATION": theorem,
            "OLD_CAP": a["OLD_CAP"],
            "NEW_CAP": cap,
            "OLD_BOUND": resolved[pid],
            "NEW_BOUND": bound,
            "ADOPTED_PROJECTED_BOUND": after_rows[pid],
            "OLD_ALL_T_TERMS": old,
            "NEW_ALL_T_TERMS": new,
            "OLD_ALL_ARGMAX": [t for t in old if t[1] == resolved[pid]],
            "NEW_ALL_ARGMAX": [t for t in new if t[1] == bound],
            "S4_BASE": a["S4_BASE"],
            "S4_BY_T": a["S4_BY_T"],
            "S5_USED": False,
            "FRACTIONAL_CREDIT_TERMS": sum((4 * t[4]) % 7 != 0 for t in new),
        }
    after = family_summary(after_rows, cursor)
    changed = sorted(p for p in resolved if resolved[p] != after_rows[p])
    require(set(changed) <= set(PROFILE_IDS), "unscoped resolved update")

    def code_bytes(path):
        return (
            (ROOT / path).read_bytes()
            if mode.startswith("INPUT_HEAD")
            else blob(candidate, path, repo)
        )

    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PROVEN_FAMILY_GAIN"
        if after["MAXIMUM"] < before["MAXIMUM"]
        else "NO_PROVEN_FAMILY_GAIN",
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "PATH": INPUT_RESULT,
            "SHA256": INPUT_SHA,
        },
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PATH": BASE_RESULT,
            "SHA256": BASE_SHA,
        },
        "SOURCE_SHA256": sha(code_bytes(SOURCE)),
        "TEST_SHA256": sha(code_bytes(TEST)),
        "PROOF": __doc__,
        "UPSTREAM_REPLAY": replay,
        "PROFILE_ORDER": list(PROFILE_IDS),
        "PROFILES": profiles,
        "SHARED_THEOREM": {
            "COMMON_T_CAP": max(p["RELAXATION"]["CAP"] for p in profiles.values()),
            "PER_PROFILE_CAPS": {p: profiles[p]["RELAXATION"]["CAP"] for p in PROFILE_IDS},
            "UNIVERSALITY": "ALL_LEGAL_REALIZATIONS_OF_EACH_EXACT_PROFILE",
            "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
            "PORTFOLIOS_ENUMERATED": 0,
            "RELAXED_STATES_ASSERTED_REALIZABLE": False,
        },
        "S4_S5_AUTHORITY": {
            "PER_PROFILE": auth,
            "C_INHERITED_CERTIFICATE_VERBATIM": c_cert,
            "S4_RULE": "MAX; NEVER ADD; C ADOPTED FLOOR ONLY AT T264",
            "S5_ADOPTED_CERTIFICATES": base["CERTIFICATES_ADOPTED"],
            "S5_ALL_T_ADOPTION": base["ALL_T_BONFERRONI_5_ADOPTION"],
            "S5_INHERITED_TARGET": base["INHERITED_TARGET_BONFERRONI_5"],
        },
        "TERM_COLUMNS": fixed["TERM_COLUMNS"],
        "FULL_ENVELOPE_TERM_COUNTS": {
            "OLD_PER_PROFILE": {p: len(profiles[p]["OLD_ALL_T_TERMS"]) for p in PROFILE_IDS},
            "NEW_PER_PROFILE": {p: len(profiles[p]["NEW_ALL_T_TERMS"]) for p in PROFILE_IDS},
            "OLD_TOTAL": sum(len(p["OLD_ALL_T_TERMS"]) for p in profiles.values()),
            "NEW_TOTAL": sum(len(p["NEW_ALL_T_TERMS"]) for p in profiles.values()),
            "NEW_T_RANGES": {p: [22, profiles[p]["NEW_CAP"]] for p in PROFILE_IDS},
        },
        "FAMILY_BEFORE": before,
        "FAMILY_AFTER": after,
        "FAMILY_DELTA": before["MAXIMUM"] - after["MAXIMUM"],
        "ALL_NEW_MAX_OWNERS": after["ALL_MAX_OWNERS"],
        "NEXT_DISTINCT_BOUND": after["NEXT_DISTINCT_BOUND"],
        "RESOLVED_ROWS_BEFORE": resolved,
        "RESOLVED_ROWS_AFTER": after_rows,
        "RESOLVED_ROWS_CHANGED": changed,
        "OTHER_RESOLVED_ROWS_UNCHANGED": len(resolved) - len(changed),
        "CURSOR_197_PRESERVED": fixed["CURSOR_197_PRESERVED"],
        "INHERITED_EXCLUSION_PRESERVED": True,
        "INHERITED_EXCLUSION": fixed["INHERITED_EXCLUSION"],
        "INHERITED_CAVEATS_REFERENCE": fixed["INHERITED_CAVEATS_REFERENCE"],
        "UPSTREAM_PRIOR_REVIEW_CAVEAT_VERBATIM": fixed["PRIOR_REVIEW_CAVEAT"],
        "UPSTREAM_WORKER_ATTEMPT_HISTORY_VERBATIM": fixed["WORKER_ATTEMPT_HISTORY"],
        "WORKER_ATTEMPT_HISTORY": [
            {
                "OBSERVED": (
                    "A new goal was rejected because this same Owner goal was already active"
                ),
                "DISPOSITION": "existing goal retained",
                "SCIENTIFIC_FAILURE": False,
            },
            {
                "OBSERVED": (
                    "initial source lookups used absent scripts/research and historical filenames"
                ),
                "DISPOSITION": "exact tracked source paths and immutable Git blobs used",
                "SCIENTIFIC_FAILURE": False,
            },
            {
                "OBSERVED": "system Python 3.13 upstream import lacked numpy",
                "DISPOSITION": (
                    "existing repository Python 3.13.8 environment used; no installation"
                ),
                "SCIENTIFIC_FAILURE": False,
            },
            {
                "OBSERVED": "first focused lint exited 1 with three E501 long history strings",
                "DISPOSITION": "literal formatting repaired before scientific acceptance tests",
                "SCIENTIFIC_FAILURE": False,
            },
        ],
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "INCUMBENT": fixed["INCUMBENT"],
        "GAP_TO_INCUMBENT": after["MAXIMUM"] - fixed["INCUMBENT"],
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "FRESH_JUDGE": "ONE_FRESH_FOCUSED_REVIEW_ON_FINAL_TREE; VERDICT_EXTERNAL_TO_JSON",
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NONE",
        "PRODUCTION_MUTATION": "NONE",
    }


def validate_payload(payload, expected):
    require(render(payload) == render(expected), "result differs from complete exact recomputation")


def verify_result(candidate="HEAD", repo=ROOT):
    expected = compute_result(candidate, repo)
    data = (
        (ROOT / RESULT).read_bytes()
        if git("rev-parse", candidate, repo=repo) == INPUT_HEAD
        else blob(candidate, RESULT, repo)
    )
    require(data == render(expected), "stored result differs from complete exact recomputation")


def main():
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    if args.write_result:
        require(not (ROOT / RESULT).exists(), "result already exists; retain prior attempts")
        (ROOT / RESULT).write_bytes(render(result))
    if args.verify:
        verify_result()
    print(
        json.dumps(
            {k: result[k] for k in ("TASK_STATUS", "FAMILY_BEFORE", "FAMILY_AFTER", "FAMILY_DELTA")}
        )
    )


if __name__ == "__main__":
    main()
