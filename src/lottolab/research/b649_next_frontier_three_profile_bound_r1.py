"""Conditional shared bound for exactly the A/B/C frontier profiles.

MODEL. Twenty six-label tickets use 22 triple labels and 27 pair labels on
49 labels, with pair-linearity (two tickets share at most one label). If d_v
counts triple labels at v, its pair-label degree is 6-d_v and its simple
support-graph degree is g_v=2d_v+(6-d_v)=6+d_v. Thus sum d=66, sum g=186,
|E(G)|=93. The 22 triple supports are distinct, edge-disjoint triangles.
All facts, including each histogram, W=sum C(g_v,2), and Goodman constant
B=C(20,3)-sum g_v(19-g_v)/2, are recomputed separately below.

SHARED K/Z IDENTITY. For these three profiles K={d>0} has size 14 and
Z={d=0} size 6. Put sigma_x=|N_G(x) intersect Z|, zeta_z=|N_G(z) intersect K|,
r=sum sigma=sum zeta. Edges to Z must be pair labels, so 0<=sigma_x<=6-d_x.
Since z has degree 6 and at most five neighbours in Z, 1<=zeta_z<=6.
For H=complement(G), M=H[K], N=H[Z],
  deg_M(x)=7-d_x+sigma_x, deg_N(z)=zeta_z-1,
  2|E(M)|=32+r, 2|E(N)|=r-6.
For an edge xy of M, its common H-neighbours in Z number
6-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|. The analogous
count for zz' in N is 14-zeta_z-zeta_z'+|N_G(z) intersect N_G(z') intersect K|.
Consequently
  T(H)=54+10r-sum sigma_x(7-d_x+sigma_x)-sum zeta_z(zeta_z-1)+P,
where P is T(M)+T(N) plus the two displayed common-G-neighbour incidence
sums over E(M), E(N). Each summand is a cardinality, hence nonnegative.
Goodman's identity T(G)+T(H)=B then gives T(G)<=B-54-10r+scores.
Dropping P lowers the H lower bound and raises the G upper bound.

COMPLETE NECESSARY-CONDITION RELAXATION. Enumerate every sigma multiset
within equal-d classes, every sorted zeta in [1,6]^6 with graphical
(6-zeta), equal crossing sums, graphical (7-d+sigma) on K, and the full
bipartite degree inequalities sum of the k largest sigma <= sum min(k,zeta)
for k=1..14. These inequalities follow by counting edges from any k K
vertices; the induced graphical inequalities follow by counting edges within
the k highest-degree vertices. Every legal realization maps to a retained
state. Permuting vertices with equal d preserves every constraint and score.
The maximum scores give caps A=250, B=222, C=218, so T<=250 is one shared
bound. The state set remains a relaxation: neither simultaneous induced
graphs nor decomposition into 22 edge-disjoint triple supports is asserted.
No full support graph, portfolio, or historical cursor census is enumerated.

ROUTE B FROM THE FIXED BASE. At the TRUE t, o=W-3t>=0 is the number of open
wedges. In N_G(v), each nonedge spoils at most g_v-2 triples. Summing the
remaining triples counts each K4 four times. Hence
  q>=max(0,ceil((J-(g_max-2)o)/4)), J=sum C(g_v,3).
Replacing sum (g_v-2)o_v by (g_max-2)o only weakens this lower bound.
A K4 contains at most one triple support by pair-linearity. A triple S has
at most min_{v in S}(g_v-2) common outside neighbours; summing gives
  a<=A_max=floor(sum d_v(g_v-2)/3), and a<=q.
The fixed Base local weights are 448 for a K4 with a triple and 679 without.
Other S4 intersections count outcomes and are nonnegative. Therefore
  S4>=679q-231 min(q,A_max).
This expression increases with q (increments 448 or 679), so its integer
K4 lower bound can be substituted. Combine with the actual fixed r28 S4
function by MAX, never addition. All three have six zero degrees, so that
function returns 112. The fixed Base has no adopted S5 for A, B, or C; no S5
term is used. Existing cap-term-only S5 certificates do not imply all-t S5.

The Base S3 identity is S3=2800o+20272(t-22)+7000*22. An outcome has at most
seven winning tickets: chosen three-hit subsets are pair-linear on seven
drawn labels and use distinct pairs, giving at most C(7,2)/3=7. For r=0..7,
1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)C(r,4). Summing and substituting LOWER S4
therefore gives the valid (conservatively rounded) upper bound
  ceil(S1-S2+S3-4 max(112,S4_B)/7).
Every integer t from 22 through the shared cap is evaluated, including t
whose realizability is unknown. Integer K4 uses CEILING; A_max uses FLOOR;
the final Fraction uses CEILING. The full old envelopes are also retained;
their effective caps are reconstructed uniquely from the input row bounds
for comparison only, and are NOT new cap proofs or used to prove T<=250.

FAMILY. Read the pinned input JSON, independently aggregate all 4,647
resolved rows and 197 cursor rows BEFORE replacing exactly A/B/C, then
aggregate every row again. The inherited 282 exclusions and original caveats
remain conditional inputs, pinned to their original bytes, never re-certified.
This is CONDITIONAL_PROJECTION, not canonical adoption, a global optimum,
or a prediction improvement. Final-tree Judge verdicts live outside this
self-hashed JSON, so recording a verdict cannot change the reviewed tree.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from fractions import Fraction
from functools import cache
from itertools import combinations_with_replacement, product
from math import comb
from pathlib import Path

TASK_ID = "B649_NEXT_FRONTIER_THREE_PROFILE_BOUND_R1"
INPUT_HEAD = "600a9aadba5880088ffe2a69abf183b59819a860"
INPUT_TREE = "33d36fe2d183600a1557e842e2682df52a75419d"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
DIRECTORY = "docs/research/matrix-native-results/"
INPUT_RESULT = DIRECTORY + "b649-next-resolved-frontier-shared-bound-r1-result.json"
INPUT_SHA = "073a27d95b399e1c2e3cb0bb1a3441157ebc1d0e45a7c9348000902494f546fa"
BASE_SHA = "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632"
BASE_RESULT = (
    DIRECTORY + f"b649-min-s2-two-bonf5-owners-exact-composition-r1-result-{BASE_SHA}.json"
)
SOURCE = "src/lottolab/research/b649_next_frontier_three_profile_bound_r1.py"
TEST = "tests/unit/test_b649_next_frontier_three_profile_bound_r1.py"
RESULT = DIRECTORY + "b649-next-frontier-three-profile-bound-r1-result.json"
ROOT = Path(__file__).resolve().parents[3]
PROFILE_IDS = ("66665555555421000000", "65555555555442000000", "66555555554433000000")
SHARED_CAP = 250
AUTHORITY_SOURCES = {
    "b649_k20_min_s2_route_b_current_owner_refinement_r32.py": (
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d"
    ),
    "b649_k20_min_s2_current_cursor_class_owner_chase_r28.py": (
        "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0"
    ),
    "b649_k20_min_s2_higher_order_closure_r2.py": (
        "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
    ),
    "b649_k20_min_s2_dangerous_core_realizability_r5.py": (
        "ad2c524bcdb716af1f1f744435576376499e3f39c3a744aec613542c41964487"
    ),
    "b649_k20_min_s2_next_distinct_plateau_r10.py": (
        "7a5dab79591f1fa59c2012a55ab89d3711ec4fc93ddfeb05245260c0bbd92ffb"
    ),
    "b649_k20_min_s2_current_cursor_dynamic_family_max_r30.py": (
        "230cb455bb162f6c8ab428afbbc8e7d9cbc7ee3c88575ef247e8d57ae925acb5"
    ),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def render(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def git(*args, repo=ROOT):
    return (
        subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.PIPE).decode().strip()
    )


def blob(ref, path, repo=ROOT):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=repo)


def pinned_blob(ref, path, digest, repo=ROOT):
    data = blob(ref, path, repo)
    require(sha(data) == digest, f"authority blob identity: {path}")
    return data


def verify_identity(candidate="HEAD", repo=ROOT):
    require(
        git("rev-parse", INPUT_HEAD + "^{tree}", repo=repo) == INPUT_TREE, "input TREE identity"
    )
    require(
        git("rev-parse", BASE_HEAD + "^{tree}", repo=repo) == BASE_TREE,
        "mathematical Base TREE identity",
    )
    head = git("rev-parse", candidate, repo=repo)
    if head == INPUT_HEAD:
        return "INPUT_HEAD_WITH_WORKING_CANDIDATE"
    parents = git("rev-list", "--parents", "-n", "1", head, repo=repo).split()
    require(parents[1:] == [INPUT_HEAD], "candidate must be a direct single-parent input child")
    changed = git(
        "diff-tree", "--no-commit-id", "--name-status", "-r", head, repo=repo
    ).splitlines()
    require(
        sorted(changed) == sorted(f"A\t{p}" for p in (SOURCE, TEST, RESULT)),
        "candidate must add exactly the three authorized files",
    )
    return "FIXED_DIRECT_CHILD"


def ceil_div(n, d):
    require(type(n) is int and type(d) is int and d > 0, "integer ceiling arguments")
    return -(-n // d)


@cache
def profile_facts(pid):
    require(pid in PROFILE_IDS, "exact frontier histogram")
    d = tuple(map(int, pid))
    require(
        len(d) == 20
        and tuple(sorted(d, reverse=True)) == d
        and all(0 <= x <= 6 for x in d)
        and sum(d) == 66,
        "triple degree histogram",
    )
    g = tuple(6 + x for x in d)
    require(sum(g) == 186 and d.count(0) == 6, "support degree and K/Z identity")
    numerator = sum(x * (19 - x) for x in g)
    require(numerator % 2 == 0, "Goodman integrality")
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "D_HISTOGRAM": {str(x): n for x, n in sorted(Counter(d).items())},
        "ASSUMPTIONS": {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "LABELS": 49,
            "TRIPLE_LABELS": 22,
            "PAIR_LABELS": 27,
            "PAIR_LINEARITY": True,
        },
        "DEGREE_SUM_D": sum(d),
        "DEGREE_SUM_G": sum(g),
        "EDGES": 3 * 22 + 27,
        "K": 14,
        "Z": 6,
        "WEDGES": sum(comb(x, 2) for x in g),
        "GOODMAN": comb(20, 3) - numerator // 2,
        "J": sum(comb(x, 3) for x in g),
        "G_MAX": max(g),
        "A_MAX": sum(x * (x + 4) for x in d) // 3,
        "PAIR_DEGREES": [6 - x for x in d],
    }


def graphical(degrees):
    """Full induced-graph edge-count inequalities, including parity and range."""
    d = sorted(degrees, reverse=True)
    n = len(d)
    return (
        all(type(x) is int and 0 <= x < n for x in d)
        and sum(d) % 2 == 0
        and all(sum(d[:k]) <= k * (k - 1) + sum(min(k, x) for x in d[k:]) for k in range(1, n + 1))
    )


@cache
def zeta_sequences():
    # All 462 sorted 6-tuples in 1..6 are considered; no graph is enumerated.
    return tuple(
        z
        for z in combinations_with_replacement(range(1, 7), 6)
        if graphical(tuple(6 - x for x in z))
    )


def bipartite_necessary(sigma, zeta):
    d = sorted(sigma, reverse=True)
    return sum(d) == sum(zeta) and all(
        sum(d[:k]) <= sum(min(k, z) for z in zeta) for k in range(1, len(d) + 1)
    )


@cache
def relaxed_cap(pid):
    f = profile_facts(pid)
    groups = tuple(sorted(Counter(x for x in f["D"] if x).items(), reverse=True))
    choices = [tuple(combinations_with_replacement(range(7 - d), n)) for d, n in groups]
    all_states = []
    signatures = 0
    for parts in product(*choices):
        signatures += 1
        ds = tuple(d for (d, _), sigmas in zip(groups, parts, strict=True) for _ in sigmas)
        sigma = tuple(s for sigmas in parts for s in sigmas)
        m = tuple(7 - d + s for d, s in zip(ds, sigma, strict=True))
        if not graphical(m):
            continue
        r = sum(sigma)
        sigma_score = sum(s * degree for s, degree in zip(sigma, m, strict=True))
        for zeta in zeta_sequences():
            if not bipartite_necessary(sigma, zeta):
                continue
            zeta_score = sum(z * (z - 1) for z in zeta)
            upper = f["GOODMAN"] - 54 - 10 * r + sigma_score + zeta_score
            all_states.append(
                {
                    "R": r,
                    "SIGMA_BY_D": [[d, list(s)] for (d, _), s in zip(groups, parts, strict=True)],
                    "ZETA": list(zeta),
                    "SIGMA_SCORE": sigma_score,
                    "ZETA_SCORE": zeta_score,
                    "UPPER": upper,
                }
            )
    require(all_states, "empty necessary-condition relaxation")
    cap = max(s["UPPER"] for s in all_states)
    return {
        "CAP": cap,
        "SIGMA_SIGNATURES": signatures,
        "ZETA_MULTISET_COUNT": len(zeta_sequences()),
        "RETAINED_STATE_COUNT": len(all_states),
        "STATES_SHA256": sha(render(all_states)),
        "ALL_ARGMAX": [s for s in all_states if s["UPPER"] == cap],
        "PER_R_MAXIMUM": {
            str(r): max(s["UPPER"] for s in all_states if s["R"] == r)
            for r in sorted({s["R"] for s in all_states})
        },
        "REALIZABILITY": "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION",
    }


def literal_assignment(source, name):
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"missing fixed Base constant {name}")


def fixed_authority(repo=ROOT):
    sources = {
        p: pinned_blob(BASE_HEAD, "src/lottolab/research/" + p, h, repo).decode()
        for p, h in AUTHORITY_SOURCES.items()
    }
    s4_source = sources["b649_k20_min_s2_current_cursor_class_owner_chase_r28.py"]
    fn = next(
        n
        for n in ast.parse(s4_source).body
        if isinstance(n, ast.FunctionDef) and n.name == "profile_s4_floor"
    )
    namespace = {
        "DegreeProfile": tuple,
        "K20_REUSED_S4_LOWER_BOUND": literal_assignment(
            sources["b649_k20_min_s2_dangerous_core_realizability_r5.py"],
            "K20_REUSED_S4_LOWER_BOUND",
        ),
        "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND": literal_assignment(
            sources["b649_k20_min_s2_next_distinct_plateau_r10.py"],
            "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND",
        ),
    }
    # Execute only this pinned, opened function with its pinned literal constants.
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "fixed-r28-S4", "exec"), namespace)
    floors = {pid: namespace["profile_s4_floor"](tuple(map(int, pid))) for pid in PROFILE_IDS}
    require(set(floors.values()) == {112}, "per-profile fixed Base S4 floor")
    moments = sources["b649_k20_min_s2_higher_order_closure_r2.py"]
    s1, s2 = (literal_assignment(moments, k) for k in ("K20_S1", "K20_S2"))
    require((s1, s2) == (372228640, 63838600), "fixed Base S1/S2")
    base = json.loads(pinned_blob(BASE_HEAD, BASE_RESULT, BASE_SHA, repo))
    for pid in PROFILE_IDS:
        validate_s5(pid, base, False)
    return base, {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "SOURCE_SHA256": AUTHORITY_SOURCES,
        "S4_FUNCTION_SOURCE": ast.get_source_segment(s4_source, fn),
        "S4_CONSTANTS": {k: v for k, v in namespace.items() if k.endswith("LOWER_BOUND")},
        "S4_FLOOR_BY_PROFILE": floors,
        "S4_RULE": "MAX(Base floor, Route-B floor); never add floors",
        "S5_ALL_T_ADOPTION": base["ALL_T_BONFERRONI_5_ADOPTION"],
        "S5_ADOPTED_CERTIFICATES": base["CERTIFICATES_ADOPTED"],
        "S5_INHERITED_TARGET": base["INHERITED_TARGET_BONFERRONI_5"],
        "S5_USED_BY_PROFILE": dict.fromkeys(PROFILE_IDS, False),
        "S1": s1,
        "S2": s2,
    }


def validate_s5(pid, base, used):
    require(pid in PROFILE_IDS and type(used) is bool, "S5 claim type/profile")
    require(
        base["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED"
        and pid not in base["CERTIFICATES_ADOPTED"]
        and base["INHERITED_TARGET_BONFERRONI_5"]["PROFILE_ID"] != pid,
        "fixed Base target S5 authority changed",
    )
    require(not used, "no adopted S5 for this profile")


def envelope_term(pid, t, floor=112):
    f = profile_facts(pid)
    require(type(t) is int and 22 <= t <= f["WEDGES"] // 3, "T range")
    require(type(floor) is int and floor >= 0, "S4 floor")
    opened = f["WEDGES"] - 3 * t
    k4 = max(0, ceil_div(f["J"] - (f["G_MAX"] - 2) * opened, 4))
    contained = min(k4, f["A_MAX"])
    s4 = max(floor, 679 * k4 - 231 * contained)
    s3 = 2800 * opened + 20272 * (t - 22) + 154000
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    return [t, ceil_div(exact.numerator, exact.denominator), k4, contained, s4, s3]


def envelope(pid, cap, floor=112):
    require(type(cap) is int and 22 <= cap <= profile_facts(pid)["WEDGES"] // 3, "T cap")
    return [envelope_term(pid, t, floor) for t in range(22, cap + 1)]


def family_summary(resolved, cursor):
    require(len(resolved) == 4647 and len(cursor) == 197, "complete family row counts")
    require(not (set(resolved) & set(cursor)), "resolved/cursor disjointness")
    require(
        all(type(x) is int for x in (*resolved.values(), *cursor.values())), "integer row bounds"
    )
    merged = {**resolved, **cursor}
    levels = sorted(set(merged.values()), reverse=True)
    return {
        "MAXIMUM": levels[0],
        "ALL_MAX_OWNERS": sorted(p for p, b in merged.items() if b == levels[0]),
        "NEXT_DISTINCT_BOUND": levels[1],
        "ALL_NEXT_DISTINCT_OWNERS": sorted(p for p, b in merged.items() if b == levels[1]),
        "RESOLVED_MAXIMUM": max(resolved.values()),
        "CURSOR_MAXIMUM": max(cursor.values()),
        "RESOLVED_ROWS_SCANNED": len(resolved),
        "CURSOR_ROWS_SCANNED": len(cursor),
        "TOTAL_PROJECTED_ROWS": len(merged),
    }


def compute_result(candidate="HEAD", repo=ROOT):
    mode = verify_identity(candidate, repo)
    fixed = json.loads(pinned_blob(INPUT_HEAD, INPUT_RESULT, INPUT_SHA, repo))
    resolved = fixed["RESOLVED_ROWS_AFTER"]
    cursor = fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    before = family_summary(resolved, cursor)
    require(
        before == fixed["FAMILY_AFTER"]
        and before["MAXIMUM"] == 313392308
        and before["ALL_MAX_OWNERS"] == [PROFILE_IDS[0]]
        and before["NEXT_DISTINCT_BOUND"] == 313392232
        and before["ALL_NEXT_DISTINCT_OWNERS"] == sorted(PROFILE_IDS[1:])
        and before["CURSOR_MAXIMUM"] == 313391784,
        "reproduce input family and all owners",
    )
    base, authority = fixed_authority(repo)
    caps = {pid: relaxed_cap(pid)["CAP"] for pid in PROFILE_IDS}
    require(max(caps.values()) == SHARED_CAP, "derived shared cap")
    profiles = {}
    after_rows = dict(resolved)
    for pid in PROFILE_IDS:
        floor = authority["S4_FLOOR_BY_PROFILE"][pid]
        full = envelope(pid, profile_facts(pid)["WEDGES"] // 3, floor)
        old_caps = [t[0] for t in full if max(r[1] for r in full[: t[0] - 21]) == resolved[pid]]
        require(len(old_caps) == 1, "unique reconstructed old effective envelope cap")
        old_cap = old_caps[0]
        old_terms = full[: old_cap - 21]
        new_terms = envelope(pid, SHARED_CAP, floor)
        new_bound = max(r[1] for r in new_terms)
        after_rows[pid] = min(resolved[pid], new_bound)
        profiles[pid] = {
            "FACTS": profile_facts(pid),
            "RELAXATION": relaxed_cap(pid),
            "OLD_EFFECTIVE_CAP_COMPARISON_ONLY": old_cap,
            "OLD_BOUND": resolved[pid],
            "OLD_ALL_T_TERMS": old_terms,
            "OLD_ALL_ARGMAX": [r for r in old_terms if r[1] == resolved[pid]],
            "NEW_SHARED_CAP": SHARED_CAP,
            "NEW_BOUND": new_bound,
            "ADOPTED_PROJECTED_BOUND": after_rows[pid],
            "NEW_ALL_T_TERMS": new_terms,
            "NEW_ALL_ARGMAX": [r for r in new_terms if r[1] == new_bound],
            "S4_FLOOR": floor,
            "S5_USED": False,
            "FRACTIONAL_CREDIT_TERMS": sum((4 * r[4]) % 7 != 0 for r in new_terms),
        }
    changed = sorted(p for p in resolved if resolved[p] != after_rows[p])
    require(changed == sorted(PROFILE_IDS), "exact three-profile update")
    after = family_summary(after_rows, cursor)
    caveats = base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    original = caveats["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]["DONOR_STATUS_SNAPSHOTS_VERBATIM"][
        "BASE_AUTHORITY"
    ]["CURSOR"]["PARTITION"]["EXCLUDED_BY_NECESSARY_CONDITION"]
    require(
        original
        == {
            "COUNT": 282,
            "IDS_SHA256": "2c4d5b04cf2d4d89876f9c8721e7b73409bda9fb0711d2f3229807c3080296e0",
            "W_RANGE": [822, 861],
        },
        "original inherited exclusion conditions",
    )
    require(len(resolved) + len(cursor) + original["COUNT"] == 5126, "histogram accounting")

    def code_bytes(p):
        return (
            (ROOT / p).read_bytes() if mode.startswith("INPUT_HEAD") else blob(candidate, p, repo)
        )

    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": (
            "PROVEN_FAMILY_GAIN"
            if after["MAXIMUM"] < before["MAXIMUM"]
            else "NO_PROVEN_FAMILY_GAIN"
        ),
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "PATH": INPUT_RESULT,
            "SHA256": INPUT_SHA,
            "FULL_LEDGER_REAGGREGATED": True,
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
        "PROFILE_ORDER": list(PROFILE_IDS),
        "PROFILES": profiles,
        "SHARED_THEOREM": {
            "T_CAP": SHARED_CAP,
            "PROFILE_RELAXATION_CAPS": caps,
            "UNIVERSALITY": "ALL_LEGAL_REALIZATIONS_OF_THE_THREE_EXACT_PROFILES",
            "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
            "PORTFOLIOS_ENUMERATED": 0,
            "CURSOR_RESEARCH_RERUN": False,
            "RELAXED_STATES_ASSERTED_REALIZABLE": False,
        },
        "S4_S5_AUTHORITY": authority,
        "TERM_COLUMNS": [
            "T",
            "BOUND",
            "K4_LOWER_BOUND_CEILING",
            "CONTAINED_K4_CAP",
            "S4_LOWER_BOUND",
            "S3",
        ],
        "FULL_ENVELOPE_TERM_COUNTS": {
            "NEW_PER_PROFILE": {p: len(profiles[p]["NEW_ALL_T_TERMS"]) for p in PROFILE_IDS},
            "NEW_TOTAL": sum(len(profiles[p]["NEW_ALL_T_TERMS"]) for p in PROFILE_IDS),
            "OLD_PER_PROFILE": {p: len(profiles[p]["OLD_ALL_T_TERMS"]) for p in PROFILE_IDS},
            "OLD_TOTAL": sum(len(profiles[p]["OLD_ALL_T_TERMS"]) for p in PROFILE_IDS),
            "NEW_T_RANGE": [22, SHARED_CAP],
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
        "CURSOR_197_PRESERVED": {
            "COUNT": len(cursor),
            "UNCHANGED": True,
            "ROW_BOUNDS": cursor,
            "ROW_BOUNDS_SHA256": sha(render(cursor)),
        },
        "INHERITED_EXCLUSION_PRESERVED": True,
        "INHERITED_EXCLUSION": {
            "ORIGINAL_CONDITIONS_VERBATIM": original,
            "INPUT_EXCLUSION_VERBATIM": fixed["INHERITED_EXCLUSION"],
            "RECERTIFIED_THIS_ROUND": False,
            "SCOPE": "CONDITIONAL_ON_THE_ORIGINAL_NECESSARY_CONDITION_SCREEN",
        },
        "INHERITED_CAVEATS_REFERENCE": {
            "HEAD": BASE_HEAD,
            "PATH": BASE_RESULT,
            "FILE_SHA256": BASE_SHA,
            "JSON_POINTER": "/INHERITED_CAVEATS_AND_STATUS_VERBATIM",
            "CANONICAL_CONTENT_SHA256": sha(render(caveats)),
            "STATUS_VERBATIM": {
                k: v for k, v in caveats.items() if k != "INHERITED_CAVEATS_AND_STATUS_VERBATIM"
            },
            "PRESERVED_IN_IMMUTABLE_BASE": True,
            "SUPERSEDED_OR_ERASED": False,
        },
        "PRIOR_REVIEW_CAVEAT": {
            "SOURCE": "OWNER_PACKET_C12_C13",
            "PRIOR_FIRST_JUDGE": (
                "REFUTED: fixed-child result-verifier procedural failure reported by Owner"
            ),
            "PRIOR_FAILURE_RECORDS": (
                "RETAINED_IN_EXISTING_AUTHORITY; NOT_REWRITTEN_OR_CLAIMED_AS_PASS"
            ),
            "THIS_ROUND_PREFLIGHT": "REAL_ISOLATED_FIXED_CHILD_VERIFIER_TEST_REQUIRED_BEFORE_JUDGE",
        },
        "WORKER_ATTEMPT_HISTORY": [
            {
                "COMMAND": "ruff check --fix --no-cache <new source> <new test>",
                "EXIT": 1,
                "OBSERVED": "14 lint findings; one fixed; 13 E501/E731 remained",
                "DISPOSITION": "formatting and lambda style repaired before mathematical tests",
                "SCIENTIFIC_TEST_FAILURE": False,
            },
            {
                "COMMAND": "ruff check --no-cache <formatted new source> <formatted new test>",
                "EXIT": 1,
                "OBSERVED": "8 E501 findings remained in long authority hashes and caveat strings",
                "DISPOSITION": "long literal formatting repaired before mathematical tests",
                "SCIENTIFIC_TEST_FAILURE": False,
            },
            {
                "COMMAND": "guarded draft result refresh after rounding-fixture correction",
                "EXIT": 1,
                "OBSERVED": "wrong expected draft SHA; identity guard rejected before any write",
                "ACTUAL_DRAFT_SHA256": (
                    "e1f59c3cbdcdb43e36597a4ab3b8656b600a2bf32ff523f939cc2d22ca279bd9"
                ),
                "DISPOSITION": "refresh retried only with the observed SHA; old history retained",
                "SCIENTIFIC_TEST_FAILURE": False,
            },
        ],
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "INCUMBENT": 313263888,
        "GAP_TO_INCUMBENT": after["MAXIMUM"] - 313263888,
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "FRESH_JUDGE": "REQUIRED_ON_FINAL_COMMITTED_TREE; VERDICT_AND_TREE_EXTERNAL_TO_THIS_JSON",
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NONE",
        "PRODUCTION_MUTATION": "NONE",
    }


def validate_payload(payload, expected):
    """Reject any changed scientific field or missing envelope term, including metadata."""
    require(render(payload) == render(expected), "result differs from complete exact recomputation")


def verify_result(candidate="HEAD", repo=ROOT):
    expected = compute_result(candidate, repo)
    if git("rev-parse", candidate, repo=repo) == INPUT_HEAD:
        data = (ROOT / RESULT).read_bytes()
    else:
        data = blob(candidate, RESULT, repo)
    require(data == render(expected), "stored result differs from complete exact recomputation")


def main():
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify_result()
    result = compute_result()
    if args.write_result:
        path = ROOT / RESULT
        require(not path.exists(), "result already exists; preserve prior attempts")
        path.write_bytes(render(result))
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("TASK_STATUS", "FAMILY_BEFORE", "FAMILY_AFTER", "FAMILY_DELTA")
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
