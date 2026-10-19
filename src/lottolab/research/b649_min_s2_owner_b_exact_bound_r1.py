"""Exact-profile split certificate for 66665555554431000000: T <= 243.

Assume exactly 20 six-label tickets, 22 triple supports, 27 pair supports,
and distinct ticket pairs across all supports. Each vertex of triple degree
d has 2d shadow neighbours and 6-d pair neighbours, hence degree_G=6+d.
Thus E(G)=93, W=831 and Goodman gives T(G)+T(H)=297.

Let K be the 14 positive-degree vertices and Z the six zeros. Every K-Z
edge uses a pair label, so 0<=sigma_x<=6-d_x. Every zero has six neighbours
and only five possible zero neighbours, so 1<=zeta_u<=6. Both sums equal r.
The four d=6 vertices have sigma=0 and all twelve shadow neighbours in K;
each has precisely one nonneighbour in K. Put M=H[K], MZ=H[Z]. Their degrees
are h=7-d+sigma and a=zeta-1, and their edge counts are (32+r)/2,(r-6)/2.
Mixed complement triangles, by inclusion-exclusion over their same-part
edge, give the universal identity T(G)=F-P, where
 F=243-10r+sum sigma(7-d+sigma)+sum zeta(zeta-1)
  =243+sum sigma(sigma+3-d)+sum zeta(zeta-7),
 P=t(M)+t(MZ)+sum_M common_G_zero_neighbours
              +sum_MZ common_G_core_neighbours >= 0.

Necessary lists h,a,6-d-sigma,6-zeta must each be graphical, and sigma,zeta
must be bipartite graphical. Exhaust all coordinate ranges, sort sigma only
within equal-d classes and zeta within Z, retain equal sums, then apply these
necessary tests. Every legal support structure maps to a retained state:
vertex permutations preserve the constraints and F. The 5113 balanced range
states reduce to 957 necessary states; their maximum F is 243. No simultaneous
realizability is inferred from these tests. The reused generic split theorem
was originally SELF_CHECK_ONLY and did not adopt this target row; this exact
certificate is separately subject to a Fresh-context scientific Judge.

A degree/capacity graph with T=243 and P=0 is provided solely as a relaxation
counterexample to a stronger P floor. It is not asserted to have a support
decomposition or to attain the legal support maximum. We enumerate degrees,
not portfolios or full graphs. Owner A's low-degree theorem is not used.

The unchanged Route-B S4 theorem subtracts a lower bound with ceiling rounding.
The target has no adopted Bonferroni-5/S5 certificate. Recompute every integer
T from 22 to 243 with exact rational cross-checks: maximum 313206948, below
incumbent 313263888. Only this target row changes in a copy of the 4647-row
ledger; all 197 cursor profiles and the other tied owner stay unchanged.
Existing source dispositions and caveats are preserved. Global optimum unknown.
"""

from __future__ import annotations

import argparse
import json
import stat
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_min_s2_two_bonf5_owners_exact_composition_r1 as base

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_B_666655555544310_EXACT_BOUND_R1"
OWNER_CONVERSATION_ID = "01a132ff-6fcd-79f3-b250-ee68944ab94b"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
BASE_SHA = "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632"
DIRECTORY = base.prior.DIRECTORY
BASE_RESULT = (
    f"{DIRECTORY}/b649-min-s2-two-bonf5-owners-exact-composition-r1-result-{BASE_SHA}.json"
)
SOURCE = "src/lottolab/research/b649_min_s2_owner_b_exact_bound_r1.py"
TEST_SOURCE = "tests/unit/test_b649_min_s2_owner_b_exact_bound_r1.py"
RESULT_PREFIX = "b649-min-s2-owner-b-exact-bound-r1-result-"
TARGET = "66665555554431000000"
OTHER_OWNER = "66655555555511100000"
CURRENT_CAP = 264
CURRENT_BOUND = 313_395_344
PROVEN_CAP = 243
S4_BASE = 112
INCUMBENT = 313_263_888
split = base.prior.base.inherited.split
official = base.prior.base.inherited.official
require, obj, items, integer, string = base.require, base.obj, base.items, base.integer, base.string
sha, render, projection, git, blob, decode = (
    base.sha,
    base.render,
    base.projection,
    base.git,
    base.blob,
    base.decode,
)
type Term = tuple[int, int, int, int, int, int]
type Pair = tuple[int, int]


def exact_profile(pid: str) -> tuple[int, ...]:
    require(pid == TARGET, "wrong exact profile")
    p = split.profile_values(pid)
    require(p == (6,) * 4 + (5,) * 6 + (4,) * 2 + (3, 1) + (0,) * 6, "profile drift")
    return p


def checked_source(path: str, digest: str) -> bytes:
    file = ROOT / path
    require(stat.S_ISREG(file.lstat().st_mode), "unsafe input")
    raw = file.read_bytes()
    require(sha(raw) == digest, "tampered source hash")
    require(raw == blob(BASE_HEAD, path, digest), "source differs from immutable Base")
    return raw


def source_pins() -> dict[str, str]:
    paths = [
        "src/lottolab/research/b649_min_s2_two_bonf5_owners_exact_composition_r1.py",
        "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py",
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
        "src/lottolab/research/b649_k20_min_s2_current_cursor_dynamic_family_max_r30.py",
        "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py",
    ]
    pins = {p: sha(git("show", f"{BASE_HEAD}:{p}")) for p in paths}
    for path, digest in pins.items():
        checked_source(path, digest)
    return pins


def prior_art() -> dict[str, object]:
    """Bind relevant historical proofs without rerunning their searches or changing status."""
    records: dict[str, tuple[str, str, str, str, str]] = {
        "GENERIC_SPLIT": (
            "b649_k20_min_s2_topw12_split_cap_certificate_r1.py",
            "e44a635f1932166734aaa3f64f9469c0e63c7520",
            "8d1b5d168157e8cea47ac44f9ca7537ace053c31",
            "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784",
            "COMPLETE_SELF_CHECK_ONLY; original Fresh Judge not claimed",
        ),
        "GOODMAN_FORMAL_OTHER_PROFILE": (
            "b649_min_s2_goodman_r2_t249_formal_cert_r1.py",
            "42b8b74f3d4110a8ab4e51544f7756e0701c5e95",
            "4f61bfa8ce7f4afdd2800e654ed7fae89599228c",
            "38ae72a6ca8b7d8dfc7bfd93cb89ea82731c6975dc53218629a91da7ea73c643",
            "VERIFIED_WITH_CAVEATS; 15-core/5-zero low(2,1,1) lemma NOT_APPLICABLE",
        ),
        "OPEN_WEDGE_R30": (
            "b649_k20_min_s2_current_cursor_dynamic_family_max_r30.py",
            "6ba4811304ec6528738a0c0b38969901b264d241",
            "7a5cd4e3305231d30eadd4bdc433c28364a93429",
            "230cb455bb162f6c8ab428afbbc8e7d9cbc7ee3c88575ef247e8d57ae925acb5",
            "JUDGE_MODE NOT_APPLICABLE; JUDGE_DISPATCH SUPPRESSED",
        ),
        "ROUTE_B_S4": (
            "b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
            "65f4e9e50d74db9a11e71b8bdef30b25e87bf15b",
            "3876916d2185c9566642e4af8c7e9d576077d1cc",
            "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d",
            "JUDGE_MODE NOT_APPLICABLE; JUDGE_DISPATCH SUPPRESSED",
        ),
        "QUARTET_INCIDENCE": (
            "b649_k20_min_s2_current_owner_motif_exact_refinement_r1.py",
            "f2ad83b4e07571a6842ac301d336360cec805a6a",
            "0b089eb90884f14283679528be40295098a5d3ef",
            "1621262ae38fefcad112c30788c791e258be1eb5f8f2eea3dc328e3e7d6e8f09",
            "COMPLETE_SELF_CHECK_ONLY; target not an adopted row; not used",
        ),
        "ORIGINAL_BONF5": (
            "b649_k20_min_s2_three_competing_profiles_bonferroni5_r1.py",
            "e3a9843db4339167bffcdc92fb782ff6bb663ed8",
            "f63545acbc883f13ec9c50eea0b3a7e6a2190d3b",
            "c1813625148b95e0728c54b5e88f844640705575e1d969a14909d0e8f0033bf0",
            "COMPLETE_SELF_CHECK_ONLY; target not included; not used",
        ),
    }
    out: dict[str, object] = {}
    for tag, (name, head, tree, digest, status) in records.items():
        path = f"src/lottolab/research/{name}"
        require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "prior tree")
        blob(head, path, digest)
        out[tag] = {
            "SOURCE": path,
            "HEAD": head,
            "TREE": tree,
            "SOURCE_SHA256": digest,
            "ORIGINAL_DISPOSITION": status,
        }
    result_pins = {
        "GENERIC_SPLIT": (
            "b649-k20-min-s2-topw12-split-cap-certificate-r1-result.json",
            "e6bab2ae892cfccd5dcea97781e99ad1a664029e55a80c374e3441a586ba5f9d",
        ),
        "OPEN_WEDGE_R30": (
            "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json",
            "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe",
        ),
        "ROUTE_B_S4": (
            "b649-k20-min-s2-route-b-current-owner-refinement-r32-result.json",
            "f196262ea032eaccd1cc9e1f7bbc408023900d87fcdf33ad1d576de878057cd5",
        ),
    }
    for tag, (name, digest) in result_pins.items():
        path = f"{DIRECTORY}/{name}"
        result = decode(blob(BASE_HEAD, path, digest))
        obj(out[tag]).update(
            {
                "RESULT": path,
                "RESULT_SHA256": digest,
                "RESULT_STATUS_FIELDS_VERBATIM": {
                    k: result[k]
                    for k in ("TASK_STATUS", "JUDGE_MODE", "JUDGE_DISPATCH")
                    if k in result
                },
            }
        )
        if tag == "GENERIC_SPLIT":
            require(result["TASK_STATUS"] == "COMPLETE_SELF_CHECK_ONLY", "original split status")
        if tag == "OPEN_WEDGE_R30":
            row = obj(items(result["GROUP_ATTEMPTS"])[3414])
            require(row["PROFILE_IDS"] == [TARGET], "current cap proof profile")
            digest = sha(json.dumps(row, sort_keys=True).encode())
            require(
                digest == "eaca04bb815f5f59eab06d29a07140a1e9042fd21666fbda7a4064fa7cc02205",
                "current cap proof object",
            )
            obj(out[tag]).update(
                {
                    "TARGET_ORIGINAL_PROOF": row,
                    "PROOF_OBJECT_SHA256": digest,
                    "REPLAYED_HISTORICAL_SOLVER": False,
                }
            )
    return out


def base_judge_report() -> str:
    digest = "8f6700516281e9ec4d8962379d737fcdaa84c713e386467742580d5cba0ba42c"
    existing = result_path()
    if existing:
        report = string(decode(existing.read_bytes())["BASE_FRESH_JUDGE_REPORT_VERBATIM"])
    else:
        path = ROOT.parent / "B649_MIN_S2_TWO_BONF5_OWNERS_EXACT_COMPOSITION_R1" / ".task-data"
        path /= "B649_MIN_S2_TWO_BONF5_OWNERS_EXACT_FAMILY_COMPOSITION_R1/fresh-judge-report.md"
        report = path.read_text()
    require(sha(report.encode()) == digest, "Base Judge report hash")
    require(
        BASE_HEAD in report and BASE_TREE in report and BASE_SHA in report, "Base Judge binding"
    )
    require("VERIFIED_WITH_CAVEATS" in report, "Base caveats disposition")
    return report


def load_base() -> dict[str, object]:
    require(git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE, "Base tree")
    raw = checked_source(BASE_RESULT, BASE_SHA)
    sealed = decode(raw)
    require(render(base.compute_result()) == raw, "complete sealed Base replay differs")
    bounds = obj(sealed["RESOLVED_ROW_BOUNDS"])
    require(len(bounds) == 4647 and bounds[TARGET] == CURRENT_BOUND, "current target row differs")
    require(bounds[OTHER_OWNER] == CURRENT_BOUND, "other tied owner differs")
    require(not any(name.startswith("ortools") for name in sys.modules), "solver imported")
    return sealed


def model_facts(pid: str = TARGET) -> dict[str, object]:
    p = exact_profile(pid)
    g = [6 + d for d in p]
    e = 22 * comb(3, 2) + 27
    w = sum(comb(v, 2) for v in g)
    phi = comb(20, 3) - 18 * (comb(20, 2) - e) + sum(comb(13 - d, 2) for d in p)
    require((sum(p), sum(g), e, w, phi) == (66, 186, 93, 831, 297), "model identities")
    require(2 * phi == 2 * comb(20, 3) - sum(v * (19 - v) for v in g), "Goodman identity")
    return {
        "MODEL": {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "TRIPLES": 22,
            "PAIRS": 27,
            "PAIR_LINEARITY": True,
        },
        "D": list(p),
        "G": g,
        "E_G": e,
        "W": w,
        "GOODMAN_SUM": phi,
        "CORE": 14,
        "ZEROS": 6,
        "HIGH_D6": 4,
        "SIGMA_RANGES": {str(d): list(range(7 - d)) for d in sorted(set(p[:14]), reverse=True)},
        "ZETA_RANGE": list(range(1, 7)),
        "H_CORE_DEGREE": "7-d+sigma",
        "H_ZERO_DEGREE": "zeta-1",
        "HIGH_VERTEX_RESTRICTION": "sigma=0; 12 distinct core shadow neighbours; h=1",
    }


def balanced_states(pid: str = TARGET) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    p = exact_profile(pid)
    by_sum: dict[int, list[tuple[int, ...]]] = {}
    for zz in combinations_with_replacement(range(1, 7), 6):
        by_sum.setdefault(sum(zz), []).append(zz)
    options = [
        tuple(combinations_with_replacement(range(7 - d), n))
        for d, n in sorted(Counter(p[:14]).items(), reverse=True)
    ]
    return [
        (sigma, zz)
        for pieces in product(*options)
        for sigma in [tuple(v for piece in pieces for v in piece)]
        for zz in by_sum.get(sum(sigma), [])
    ]


def split_value(sigma: Sequence[int], zeta: Sequence[int]) -> int:
    p = exact_profile(TARGET)
    require(len(sigma) == 14 and len(zeta) == 6, "cross degree lengths")
    require(
        all(type(s) is int and 0 <= s <= 6 - d for s, d in zip(sigma, p[:14], strict=True)),
        "invalid core cross-degree capacity",
    )
    require(all(type(v) is int and 1 <= v <= 6 for v in zeta), "invalid zero cross-degree capacity")
    require(sum(sigma) == sum(zeta), "unbalanced cross degrees")
    return (
        243
        + sum(s * (s + 3 - d) for s, d in zip(sigma, p[:14], strict=True))
        + sum(v * (v - 7) for v in zeta)
    )


def theorem(pid: str = TARGET) -> dict[str, object]:
    p = exact_profile(pid)
    balanced = balanced_states(pid)
    retained: list[split.Configuration] = []
    for sigma, zeta in balanced:
        try:
            c = split.configuration(p, sigma, zeta)
        except ValueError:
            continue
        require(c.f == split_value(sigma, zeta), "split identity differs")
        retained.append(c)
    reused = list(split.degree_configurations(p))
    require(retained == reused and bool(retained), "necessary configuration coverage differs")
    cap = max(c.f for c in retained)
    require((len(balanced), len(retained), cap) == (5113, 957, PROVEN_CAP), "incorrect proven cap")
    states = [[list(c.sigma), list(c.zeta), list(c.h), list(c.a), c.f] for c in retained]
    return {
        "PROFILE_ID": pid,
        "BALANCED_RANGE_COUNT": len(balanced),
        "NECESSARY_COUNT": len(retained),
        "ALL_NECESSARY_CONFIGURATIONS": states,
        "CONFIGURATIONS_SHA256": sha(render(states)),
        "MAX_F": cap,
        "T_CAP": cap,
        "COMPLEMENT_TRIANGLE_FLOOR": 297 - cap,
        "MAXIMIZERS": [row for row in states if row[-1] == cap],
        "F": "243+sum sigma(sigma+3-d)+sum zeta(zeta-7)",
        "P": "t(M)+t(MZ)+sum_M common_G_Z+sum_MZ common_G_K >= 0",
        "COVERAGE": "All legal supports map to retained states modulo equal-d/zero permutations",
        "RELAXATION": "NECESSARY_ONLY; simultaneous graph or support realizability not asserted",
        "LEGAL_SUPPORT_ATTAINMENT": "UNKNOWN",
    }


def relaxation_graph() -> dict[str, object]:
    """Observe both complement identities on a capacity graph attaining F=243."""
    p = exact_profile(TARGET)
    m: set[Pair] = {(x, 13) for x in (*range(10), 11)}
    m |= {(x, 12) for x in (4, 5, 6, 7, 11)}
    m |= {(min(x, 10), max(x, 10)) for x in (8, 9, 11)}
    g = set(combinations(range(14), 2)) - m
    g |= set(combinations(range(14, 20), 2))
    g |= {(13, u) for u in range(14, 19)} | {(12, 19)}
    h = set(combinations(range(20), 2)) - g
    nb = [{u for u in range(20) if (min(v, u), max(v, u)) in g} for v in range(20)]
    sigma = [len(nb[x] & set(range(14, 20))) for x in range(14)]
    zeta = [len(nb[u] & set(range(14))) for u in range(14, 20)]

    def triangles(vs: Sequence[int], edges: set[Pair]) -> int:
        return sum(
            (a, b) in edges and (a, c) in edges and (b, c) in edges
            for a, b, c in combinations(vs, 3)
        )

    mz = h & set(combinations(range(14, 20), 2))
    parts = [
        triangles(list(range(14)), m),
        triangles(list(range(14, 20)), mz),
        sum(len(nb[x] & nb[y] & set(range(14, 20))) for x, y in m),
        sum(len(nb[u] & nb[v] & set(range(14))) for u, v in mz),
    ]
    tg, th = triangles(list(range(20)), g), triangles(list(range(20)), h)
    require([len(n) for n in nb] == [6 + d for d in p] and len(g) == 93, "graph degrees")
    split.configuration(p, tuple(sigma), tuple(zeta))
    require(tg == split_value(sigma, zeta) - sum(parts) == 297 - th == 243, "graph identities")
    require(parts == [0, 0, 0, 0], "graph P parts")
    return {
        "G_EDGES": [list(e) for e in sorted(g)],
        "SIGMA": sigma,
        "ZETA": zeta,
        "T_G": tg,
        "T_H": th,
        "P_TERMS": parts,
        "STATUS": "NECESSARY_RELAXATION_GRAPH_ONLY",
        "SUPPORT_REALIZATION": "NOT_ASSERTED",
        "IMPLICATION": "Selected degree/cross constraints alone cannot prove cap below 243",
    }


def validate_term(p: Sequence[int], term: Term) -> None:
    t, bound, k4, contained, s4, s3 = term
    g = [6 + d for d in p]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    excess = Fraction(j - (max(g) - 2) * (w - 3 * t), 4)
    fourths = max(0, -(-excess.numerator // excess.denominator))
    amax = sum(d * (g_v - 2) for d, g_v in zip(p, g, strict=True)) // 3
    cheaper = min(fourths, amax)
    floor = max(S4_BASE, 448 * cheaper + 679 * (fourths - cheaper))
    third = 2800 * w + 11872 * (t - 22) - 30800
    exact = 372_228_640 - 63_838_600 + third - Fraction(4 * floor, 7)
    ceil = -(-exact.numerator // exact.denominator)
    require(
        (bound, k4, contained, s4, s3) == (ceil, fourths, cheaper, floor, third),
        "wrong cap term, bound direction or rounding",
    )


def envelope(cap: int, pid: str = TARGET) -> list[Term]:
    p = exact_profile(pid)
    require(type(cap) is int and 22 <= cap <= CURRENT_CAP, "invalid triangle cap")
    terms = split.route_b_terms(p, cap, S4_BASE)
    require(terms == official.route_b_envelope(p, cap, S4_BASE), "official envelope differs")
    require([t[0] for t in terms] == list(range(22, cap + 1)), "entire T domain differs")
    for term in terms:
        validate_term(p, term)
    return terms


def apply_one(sealed: Mapping[str, object], pid: str, cap: int, bound: int) -> dict[str, int]:
    exact_profile(pid)
    require(
        cap == PROVEN_CAP and bound == max(t[1] for t in envelope(cap)), "incorrect cap or bound"
    )
    before = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    require(len(before) == 4647 and before[pid] == CURRENT_BOUND, "ledger target identity")
    require(sha(projection(before)) == sealed["BOUNDS_SHA256_AFTER"], "ledger digest")
    after = {**before, pid: bound}
    require([p for p in before if before[p] != after[p]] == [pid], "not exactly one row")
    require(after[OTHER_OWNER] == CURRENT_BOUND, "other owner changed")
    return after


def compute_result() -> dict[str, object]:
    sealed = load_base()
    pins = source_pins()
    art = prior_art()
    judge = base_judge_report()
    proof = theorem()
    graph = relaxation_graph()
    old, new = envelope(CURRENT_CAP), envelope(PROVEN_CAP)
    old_max, new_max = max(t[1] for t in old), max(t[1] for t in new)
    require(old_max == CURRENT_BOUND and new == old[: len(new)], "current/full envelope differs")
    after = apply_one(sealed, TARGET, PROVEN_CAP, new_max)
    before = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(sealed["CURSOR"])
    base.prior.base.validate_cursor(cursor, cursor)
    coarse = {p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(len(coarse) == 197 and max(coarse.values()) == 313_394_584, "cursor coverage")
    require(not set(before) & set(coarse), "cursor overlaps ledger")
    merged_before, merged_after = {**before, **coarse}, {**after, **coarse}
    family_before, family_after = max(merged_before.values()), max(merged_after.values())
    require(family_before == sealed["FAMILY_BOUND_AFTER"] == CURRENT_BOUND, "Base family maximum")
    next_level = max(b for b in merged_before.values() if b < family_before)
    threshold_caps = {
        str(threshold): max(
            cap
            for cap in range(22, CURRENT_CAP + 1)
            if max(t[1] for t in old[: cap - 21]) <= threshold
        )
        for threshold in (CURRENT_BOUND - 1, next_level)
    }
    peak = max(old, key=lambda t: t[1])
    needed_s4 = {
        str(threshold): max(
            S4_BASE, (7 * (372_228_640 - 63_838_600 + peak[5] - threshold) + 3) // 4
        )
        for threshold in (CURRENT_BOUND - 1, next_level)
    }
    others = {p: b for p, b in before.items() if p != TARGET}
    require(others == {p: b for p, b in after.items() if p != TARGET}, "other rows changed")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SCIENTIFIC_CANDIDATE_PENDING_FRESH_JUDGE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "WRITE_OWNERSHIP": "NEW_ISOLATED_WORKTREE_ONLY",
        "PROOF": __doc__,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": BASE_RESULT,
        "BASE_RESULT_SHA256": BASE_SHA,
        "SOURCE_PINS": pins,
        "PRIOR_ART": art,
        "BASE_FRESH_JUDGE_REPORT_VERBATIM": judge,
        "BASE_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST_SOURCE).read_bytes()),
        "TARGET_PROFILE": TARGET,
        "MODEL_FACTS": model_facts(),
        "THEOREM": proof,
        "GRAPH_COUNTEREXAMPLE_CHECK": graph,
        "CURRENT_T_CAP": CURRENT_CAP,
        "CURRENT_S4_FLOOR": S4_BASE,
        "CURRENT_S5_CAP": None,
        "CURRENT_S5_STATUS": "NO_ADOPTED_CERTIFICATE_FOR_TARGET",
        "BOUND_SOURCE": (
            "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[881]"
        ),
        "NEW_PROVEN_T_CAP": PROVEN_CAP,
        "NEW_PROVEN_S4_FLOOR": S4_BASE,
        "NEW_PROVEN_S5_CAP": None,
        "S5_USED": False,
        "BOUND_DIRECTIONS": {"S4": "LOWER_BOUND_SUBTRACTED", "S5": "NOT_USED"},
        "CURRENT_PROFILE_BOUND": old_max,
        "NEW_FULL_PROFILE_BOUND": new_max,
        "EXACT_PROFILE_DELTA": old_max - new_max,
        "STRICT_GAIN_EXCLUDED": new_max <= INCUMBENT,
        "INCUMBENT": INCUMBENT,
        "OLD_FULL_T_ENVELOPE": [list(t) for t in old],
        "NEW_FULL_T_ENVELOPE": [list(t) for t in new],
        "TERM_COUNT": len(new),
        "NEW_MAXIMIZING_TERMS": [list(t) for t in new if t[1] == new_max],
        "MINIMUM_IMPROVEMENT": {
            "CAP_THRESHOLDS": threshold_caps,
            "PEAK_S4_THRESHOLDS": needed_s4,
            "CURRENT_PEAK": list(peak),
            "NEXT_VERIFIED_LEVEL": next_level,
            "S4_THRESHOLDS_REQUIRE_A_NEW_VALID_PROOF": True,
        },
        "PRIOR_GENERIC_SPLIT_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "PRIOR_GENERIC_SPLIT_TARGET_ADOPTION": "NOT_ADOPTED_IN_BASE_LEDGER",
        "ORIGINAL_BONF5_STATUS": sealed["DONOR_ORIGINAL_STATUS_VERBATIM"],
        "BASE_PROVENANCE_VERBATIM": sealed["PROVENANCE"],
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "CERTIFICATES_ADOPTED_UNCHANGED": sealed["CERTIFICATES_ADOPTED"],
        "INHERITED_TARGET_BONFERRONI_5_UNCHANGED": sealed["INHERITED_TARGET_BONFERRONI_5"],
        "LEDGER_ROWS": len(after),
        "ROWS_UPDATED": 1,
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "OTHER_4646_ROWS_SHA256": sha(projection(others)),
        "BOUNDS_SHA256_BEFORE": sha(projection(before)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "OTHER_TIED_OWNER_PRESERVED": "PASS",
        "CURSOR": cursor,
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_PROFILE_COUNT": len(coarse),
        "CURSOR_PRESERVED": "PASS",
        "FAMILY_BOUND_BEFORE": family_before,
        "FAMILY_AFTER_SINGLE_ROW": family_after,
        "SINGLE_ROW_FAMILY_DELTA": family_before - family_after,
        "FAMILY_OWNER_IDS": sorted(p for p, b in merged_after.items() if b == family_after),
        "B01_TO_B16_AT_SEAL": {f"B{i:02}": "NOT_VERIFIED" for i in range(1, 17)},
        "GATE_STATUS_SCOPE": "External exact-tree scientific Judge plus subsequent local lifecycle",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "EXISTING_SOURCE_MUTATED": "NO",
        "OTHER_WORKTREE_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
        "PORTFOLIOS_ENUMERATED": 0,
    }


def result_path() -> Path | None:
    paths = sorted((ROOT / DIRECTORY).glob(f"{RESULT_PREFIX}*.json"))
    require(len(paths) <= 1, "duplicate result")
    if not paths:
        return None
    path = paths[0]
    require(stat.S_ISREG(path.lstat().st_mode), "unsafe result")
    require(path.name == f"{RESULT_PREFIX}{sha(path.read_bytes())}.json", "result SHA differs")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = result_path()
    require(not args.verify or path is not None, "missing sealed result")
    result = compute_result()
    raw = render(result)
    if path:
        require(path.read_bytes() == raw, "sealed result differs")
    else:
        path = ROOT / DIRECTORY / f"{RESULT_PREFIX}{sha(raw)}.json"
        with path.open("xb") as out:
            out.write(raw)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "NEW_PROVEN_T_CAP",
                    "NEW_FULL_PROFILE_BOUND",
                    "EXACT_PROFILE_DELTA",
                    "STRICT_GAIN_EXCLUDED",
                    "FAMILY_AFTER_SINGLE_ROW",
                    "SINGLE_ROW_FAMILY_DELTA",
                )
            }
            | {"RESULT": str(path), "SHA256": sha(raw)}
        )
    )


if __name__ == "__main__":
    main()
