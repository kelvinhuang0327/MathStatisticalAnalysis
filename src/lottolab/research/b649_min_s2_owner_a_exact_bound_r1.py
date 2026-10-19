"""Exact-profile shadow certificate: T(H)>=48, hence T(G)<=249.

Only d=6^3,5^9,1^3,0^5 is covered. Twenty six-label tickets have 22
triple and 27 pair supports, with every support pair distinct. Thus G has
93 edges, degrees 6+d, W=831, and Goodman gives T(G)+T(H)=297.

Write K=A union B union L (sizes 3,9,3) and Z (size5). A d6 vertex has
12 DISTINCT triple-shadow neighbours in K, but only11 outside L; every
A meets L. Therefore L cannot itself be a triple support. Two shadow
edges within L would share a vertex of triple degree1 and must belong
to the same LLL support. Hence G[L] has at most ONE shadow edge q.

Let sigma be G cross degrees on K, zeta on Z. A has sigma0, B has
sigma in {0,1}, and L has s_i in 0..5. Put n=sum_B sigma and r=n+sum s.
For M=H[K], N=H[Z], h_x=8-d_x+sigma_x, a_z=zeta_z-2. In particular
|M|=(54+r)/2, |N|=(r-10)/2, and 10<=r<=24 is even. For each M edge
xy its zero apices number 5-sigma_x-sigma_y+c_Z(xy), where c_Z counts
common G neighbours in Z; the analogous N edge expression is
15-zeta_u-zeta_v+c_K(uv). These expressions are EXACT, including
nonnegative intersections. Consequently
 T(H)=60+10r-sum_K sigma*h-sum_Z zeta*(zeta-2)+P,
 P=t(M)+t(N)+sum_M c_Z+sum_N c_K >=0,
 T(G)=F-P, F=237+sum_i s_i*(s_i-5)-8n+sum_Z zeta^2.

Put D=M[L], ell_i=deg_D(i), with pairs ordered 01,02,12. Every legal
realization has q=None or one edge of the complement of D. Its internal
G pair degree 2-ell_i-1{i in q} is at most remaining pair capacity5-s_i.
An edge ij in D has at least max(0,2+s_i+s_j-ell_i-ell_j) common M
neighbours in K\\L, by intersection of two subsets of a12-element set.
These triangles have exactly two L vertices, so none is counted twice.
The LLL triangle adds1 exactly when D is complete. Also
c_Z(ij)>=max(0,s_i+s_j-5). Thus
 P>=P_L=1{D complete}+sum_D (max(0,2+s_i+s_j-ell_i-ell_j)
                                      +max(0,s_i+s_j-5)).

For each zero graph N define m_a(N)=min_{S subset Z, |S|=a} e_N(S).
Double counting gives sum_N c_K=sum_{x in K} e_N(N_G(x) intersect Z),
so the three low vertices contribute at least sum_i m_{s_i}(N).
This is a different term of P from all the P_L contributions. Hence
 P>=P_L+t(N)+sum_i m_{s_i}(N).
Exhaust all1024 labelled graphs N on5 vertices and all32 subsets per N.
For e=0..7 define Q_e(s)=max_{|N|=e} [sum(2+deg_N)^2-t(N)-sum_i m_{s_i}(N)].
No graphicality or cross-edge feasibility exclusions are used. Enumerate all56 sorted s vectors,
all n=0..9, all8 labelled D masks; retain only the necessary r and q
conditions above. Sorting s merely relabels L, while all D and q remain
covered. Every legal realization maps into this relaxation; unused P
terms remain nonnegative. The1405 reduced configurations (90879 expanded
N configurations) give max(237+sum s_i(s_i-5)-8n+Q_e(s)-P_L)=249.
No attainment is asserted.

Use the accepted Route-B S4 authority unchanged on every integer T22..249.
Its exact ceiling bound peaks at313260720, a drop134624 from313395344.
This excludes strict gain over313263888 for this profile. The other tied owner and
all197 cursor profiles leave the one-row family maximum313395344.
Historical solver/resource caveats and SELF_CHECK_ONLY dispositions are
retained through their immutable Base bytes; no historical solver is run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as official

ROOT = Path(__file__).resolve().parents[3]
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
BASE_SHA = "42f6a5ea0e0a5c31bcd67c179ceb40d7599740daf511b57ab29e39bdd1bb4632"
DIRECTORY = "docs/research/matrix-native-results"
BASE_RESULT = (
    f"{DIRECTORY}/b649-min-s2-two-bonf5-owners-exact-composition-r1-result-{BASE_SHA}.json"
)
SOURCE = "src/lottolab/research/b649_min_s2_owner_a_exact_bound_r1.py"
TEST = "tests/unit/test_b649_min_s2_owner_a_exact_bound_r1.py"
RESULT = ROOT / DIRECTORY / "b649-min-s2-owner-a-exact-bound-r1-result.json"
TARGET = "66655555555511100000"
OTHER = "66665555554431000000"
OWNER = "01a132fd-fd5c-7250-b050-1a000c07f356"
MODEL: dict[str, object] = {
    "TICKETS": 20,
    "LABELS_PER_TICKET": 6,
    "TRIPLES": 22,
    "PAIRS": 27,
    "PAIR_LINEARITY": True,
}
LP = tuple(combinations(range(3), 2))
obj, integer = official.r28.object_row, official.r28.integer
type Term = tuple[int, int, int, int, int, int]
R30_HEAD = "6ba4811304ec6528738a0c0b38969901b264d241"
R30_TREE = "7a5cd4e3305231d30eadd4bdc433c28364a93429"
R30_SHA = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
PRIOR_ART: list[dict[str, str]] = [
    {
        "HEAD": "e44a635f1932166734aaa3f64f9469c0e63c7520",
        "TREE": "8d1b5d168157e8cea47ac44f9ca7537ace053c31",
        "RESULT": f"{DIRECTORY}/b649-k20-min-s2-topw12-split-cap-certificate-r1-result.json",
        "SHA256": "e6bab2ae892cfccd5dcea97781e99ad1a664029e55a80c374e3441a586ba5f9d",
        "STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "APPLICABILITY": "Universal split re-derived; conditional two-low cap does not apply.",
    },
    {
        "HEAD": "2f70925698cb28758fdf29a62bc5e91028c03a81",
        "TREE": "216bd91dee0afa58f8186a38aec52b1d47781ef8",
        "RESULT": f"{DIRECTORY}/b649-k20-min-s2-split-cap-current-owner-chase-r1-result.json",
        "SHA256": "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3",
        "STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "APPLICABILITY": "No target-specific stronger certificate.",
    },
    {
        "HEAD": "8fac3d41b2d519d92b06d6ceb933fe31072c6409",
        "TREE": "62f80eecf3f1045c905d345a3e68fb2ad078eaec",
        "RESULT": f"{DIRECTORY}/b649-min-s2-bonferroni5-target-cert-r1-result.json",
        "SHA256": "dc0ffab7c48e5a651375f7773e495d869d4211273ff3ff3b1423c5b10c1f7d9b",
        "STATUS": "VERIFIED",
        "ORIGINAL_STATUS": "SELF_CHECK_ONLY",
        "APPLICABILITY": "General moment theorem; numeric S5 cap not adopted for this profile.",
    },
]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def pinned(head: str, path: str, digest: str) -> bytes:
    check(bool(head and path and digest), "missing source identity")
    raw = git("show", f"{head}:{path}")
    check(sha(raw) == digest, "source digest differs")
    return raw


def premises(pid: str, model: Mapping[str, object]) -> dict[str, object]:
    check(pid == TARGET, "wrong profile")
    check(
        dict(model) == MODEL
        and model["PAIR_LINEARITY"] is True
        and all(
            type(model[k]) is int for k in ("TICKETS", "LABELS_PER_TICKET", "TRIPLES", "PAIRS")
        ),
        "invalid support assumptions",
    )
    d = tuple(map(int, pid))
    g = tuple(6 + x for x in d)
    h = tuple(19 - x for x in g)
    edges = 22 * comb(3, 2) + 27
    w = sum(comb(x, 2) for x in g)
    phi = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    alt = comb(20, 3) - 18 * (comb(20, 2) - edges) + sum(comb(x, 2) for x in h)
    check(
        (len(d), sum(d), edges, sum(g), w, phi, alt) == (20, 66, 93, 186, 831, 297, 297),
        "invalid graph identities",
    )
    return {
        "D": list(d),
        "G_DEGREES": list(g),
        "H_DEGREES": list(h),
        "G_EDGES": edges,
        "W": w,
        "GOODMAN": int(phi),
        "K": 15,
        "Z": 5,
        "L": 3,
    }


def zero_graphs() -> tuple[dict[tuple[int, tuple[int, ...]], int], dict[int, int]]:
    maxima: dict[tuple[int, tuple[int, ...]], int] = {}
    counts: dict[int, int] = {}
    pairs = tuple(combinations(range(5), 2))
    triples = tuple(combinations(range(5), 3))
    lows = tuple(combinations_with_replacement(range(6), 3))
    for mask in range(1 << len(pairs)):
        deg = [0] * 5
        for k, (i, j) in enumerate(pairs):
            if mask & (1 << k):
                deg[i] += 1
                deg[j] += 1
        e = mask.bit_count()
        edges = [ij for k, ij in enumerate(pairs) if mask & (1 << k)]
        triangles = sum(all(ij in edges for ij in combinations(t, 2)) for t in triples)
        minima = [
            min(
                sum(i in subset and j in subset for i, j in edges)
                for subset in combinations(range(5), a)
            )
            for a in range(6)
        ]
        for s in lows:
            value = sum((v + 2) ** 2 for v in deg) - triangles - sum(minima[v] for v in s)
            maxima[e, s] = max(maxima.get((e, s), -1000), value)
        counts[e] = counts.get(e, 0) + 1
    return maxima, counts


def low_allowed(s: Sequence[int], mask: int) -> bool:
    edges = [ij for k, ij in enumerate(LP) if mask & (1 << k)]
    ell = [sum(i in ij for ij in edges) for i in range(3)]
    candidates: list[tuple[int, int] | None] = [None, *(ij for ij in LP if ij not in edges)]
    return any(
        all(2 - ell[i] - int(q is not None and i in q) <= 5 - s[i] for i in range(3))
        for q in candidates
    )


def correction(s: Sequence[int], mask: int) -> int:
    edges = [ij for k, ij in enumerate(LP) if mask & (1 << k)]
    ell = [sum(i in ij for ij in edges) for i in range(3)]
    return int(mask == 7) + sum(
        max(0, 2 + s[i] + s[j] - ell[i] - ell[j]) + max(0, s[i] + s[j] - 5) for i, j in edges
    )


def certify(pid: str = TARGET, model: Mapping[str, object] = MODEL) -> dict[str, object]:
    premises(pid, model)
    zmax, zcount = zero_graphs()
    domain: list[list[object]] = []
    branches: dict[str, int] = {}
    expanded = 0
    for s in combinations_with_replacement(range(6), 3):
        for n in range(10):
            r = sum(s) + n
            if not 10 <= r <= 24 or r % 2:
                continue
            e = (r - 10) // 2
            for mask in range(8):
                if not low_allowed(s, mask):
                    continue
                ell = [sum(i in ij for k, ij in enumerate(LP) if mask & (1 << k)) for i in range(3)]
                p = correction(s, mask)
                f = 237 + sum(v * (v - 5) for v in s) - 8 * n + zmax[e, s]
                # Algebraic split polynomial after combining the zero corrections.
                sig_h = 4 * n + sum(v * (7 + v) for v in s)
                raw = 297 - (60 + 10 * r - sig_h - (zmax[e, s] - 2 * r))
                check(raw == f, "split polynomial differs")
                domain.append([list(s), n, r, mask, ell, p, f, f - p])
                branches[str(mask)] = max(branches.get(str(mask), -1000), f - p)
                expanded += zcount[e]
    cap = max(integer(row[-1]) for row in domain)
    table = [
        [e, list(s), zmax[e, s]]
        for e in range(8)
        for s in combinations_with_replacement(range(6), 3)
    ]
    return {
        "NEW_T_CAP": cap,
        "H_TRIANGLE_FLOOR": 297 - cap,
        "ZERO_GRAPH_COUNT": sum(zcount.values()),
        "Q_TABLE": table,
        "Q_TABLE_SHA256": sha(json.dumps(table, separators=(",", ":")).encode()),
        "REDUCED_COUNT": len(domain),
        "EXPANDED_COUNT": expanded,
        "DOMAIN_SHA256": sha(json.dumps(domain, separators=(",", ":")).encode()),
        "BRANCH_MAXIMA": branches,
        "MAXIMIZERS": [r for r in domain if r[-1] == cap],
        "COVERAGE": "All legal realizations project to (sorted s,n,D,q,N); necessary filters only.",
        "ATTAINABILITY": "NOT_ASSERTED",
    }


def rounded_bound(s3: int, s4: int) -> int:
    return 372228640 - 63838600 + s3 - (4 * s4) // 7


def envelope(cap: int) -> list[Term]:
    # Actual target S4 terms divide by7. This arithmetic-only probe guards
    # ceiling semantics without extending the scientific profile domain.
    check(rounded_bound(0, 1) == 308390040, "incorrect bound rounding")
    d = tuple(map(int, TARGET))
    g = [6 + v for v in d]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    amax = sum(v * (4 + v) for v in d) // 3
    terms: list[Term] = []
    for t in range(22, cap + 1):
        k4 = max(0, -(-(j - (max(g) - 2) * (w - 3 * t)) // 4))
        contained = min(k4, amax)
        s4 = max(112, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = rounded_bound(s3, s4)
        rational = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        check(bound - 1 < rational <= bound, "incorrect bound rounding")
        terms.append((t, bound, k4, contained, s4, s3))
    check(terms == official.route_b_envelope(d, cap, 112), "official envelope differs")
    return terms


def project(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    sealed: Mapping[str, object],
    bound: int,
) -> dict[str, int]:
    check(len(rows) == len(dict(rows)) == 4647, "duplicate or missing ledger rows")
    before = dict(rows)
    check(all(type(v) is int for _, v in rows), "noninteger ledger bound")
    check(before == obj(sealed["RESOLVED_ROW_BOUNDS"]), "ledger drift")
    check(dict(cursor) == obj(sealed["CURSOR"]), "cursor drift")
    check(before[TARGET] == before[OTHER] == 313395344, "wrong current owner bound")
    check(
        type(bound) is int
        and bound == max(t[1] for t in envelope(integer(certify()["NEW_T_CAP"]))),
        "wrong new profile bound",
    )
    return {**before, TARGET: bound}


def load_base() -> tuple[dict[str, object], dict[str, object]]:
    check(
        git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE, "base tree differs"
    )
    sealed = obj(json.loads(pinned(BASE_HEAD, BASE_RESULT, BASE_SHA)))
    check((ROOT / BASE_RESULT).read_bytes() == render(sealed), "local Base result changed")
    pins: dict[str, object] = {}
    names = {
        official.__name__,
        official.r28.__name__,
        official.r30.__name__,
        official.bound_from_cap.__module__,
        official.overlap_wedge_count.__module__,
    }
    for name in sorted(names):
        module = sys.modules[name]
        path = getattr(module, "__file__", None)
        if not isinstance(path, str) or not path.endswith(".py"):
            continue
        source = Path(path).resolve()
        check(source.is_relative_to(ROOT), "import outside isolated worktree")
        relative = source.relative_to(ROOT).as_posix()
        raw = git("show", f"{BASE_HEAD}:{relative}")
        check(source.read_bytes() == raw, "inherited source changed")
        pins[relative] = sha(raw)
    check(not any(n.startswith("ortools") for n in sys.modules), "solver imported")
    check(
        b"Fresh-context Judge: VERIFIED_WITH_CAVEATS"
        in git("show", "-s", "--format=%B", BASE_HEAD),
        "missing Base acceptance identity",
    )
    return sealed, pins


def prior_authorities() -> dict[str, object]:
    for entry in PRIOR_ART:
        check(
            git("rev-parse", f"{entry['HEAD']}^{{tree}}").decode().strip() == entry["TREE"],
            "prior-art tree differs",
        )
        data = obj(json.loads(pinned(entry["HEAD"], entry["RESULT"], entry["SHA256"])))
        if entry["STATUS"] == "COMPLETE_SELF_CHECK_ONLY":
            check(data["TASK_STATUS"] == entry["STATUS"], "historical status differs")
    check(
        git("rev-parse", f"{R30_HEAD}^{{tree}}").decode().strip() == R30_TREE,
        "cap source tree differs",
    )
    path = f"{DIRECTORY}/{official.CAP_SOURCE_RESULT}"
    data = obj(json.loads(pinned(R30_HEAD, path, R30_SHA)))
    attempts = official.r28.rows(data["GROUP_ATTEMPTS"])
    record = obj(attempts[3415])
    d = tuple(map(int, TARGET))
    check(
        record["PROFILE_IDS"] == [TARGET]
        and official.r28.r26.accepted_cap(record, (d,), 264) == 264,
        "current cap authority differs",
    )
    return {
        "PRIOR_ART": PRIOR_ART,
        "PRIOR_ART_STATUS": "NO_ACCEPTED_STRONGER_TARGET_CERTIFICATE_FOUND",
        "CURRENT_CAP_AUTHORITY": {
            "HEAD": R30_HEAD,
            "TREE": R30_TREE,
            "RESULT": path,
            "SHA256": R30_SHA,
            "ROW": "GROUP_ATTEMPTS[3415]",
            "RECORD": record,
            "ORIGINAL_JUDGE_MODE": "NOT_APPLICABLE",
            "ORIGINAL_JUDGE_DISPATCH": "SUPPRESSED",
            "LIMITATION": "Historical solver; configured workers8 caveat preserved; not rerun.",
        },
    }


def compute_result() -> dict[str, object]:
    sealed, pins = load_base()
    proof = certify()
    old, new = envelope(264), envelope(integer(proof["NEW_T_CAP"]))
    check(old[: len(new)] == new, "lower-T terms changed")
    before = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(sealed["CURSOR"])
    coarse = {p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    check(
        len(coarse) == cursor["PROFILE_COUNT"] == 197 and not set(before) & set(coarse),
        "invalid cursor domain",
    )
    bound = max(t[1] for t in new)
    after = project(list(before.items()), cursor, sealed, bound)
    check({p for p in before if before[p] != after[p]} == {TARGET}, "non-target row changed")
    family = max([*after.values(), *coarse.values()])

    def projection(x: Mapping[str, int]) -> bytes:
        return json.dumps(dict(sorted(x.items())), sort_keys=True).encode()

    gates = {f"A{i:02}": "PASS" for i in range(1, 17)}
    gates.update(A14="NOT_VERIFIED", A15="NOT_VERIFIED")
    inherited = sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"]
    return {
        "TASK_ID": "B649_MIN_S2_OWNER_A_666555555555111_EXACT_BOUND_R1",
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": BASE_RESULT,
        "BASE_RESULT_SHA256": BASE_SHA,
        "SOURCE_PINS": pins,
        "MODEL": MODEL,
        "PRIOR_AUTHORITIES": prior_authorities(),
        "TARGET_PROFILE": TARGET,
        "DEGREE_PROFILE": "6^3,5^9,1^3,0^5",
        "PREMISES": premises(TARGET, MODEL),
        "PROOF": __doc__,
        "CERTIFICATE": proof,
        "CURRENT_T_CAP": 264,
        "CURRENT_S4_FLOOR": 112,
        "CURRENT_S5": "NO_TARGET_CERTIFICATE_ADOPTED",
        "CURRENT_PROFILE_BOUND": max(t[1] for t in old),
        "CURRENT_ROUTE_BOUND_TERMS": [list(t) for t in old],
        "NEW_ROUTE_BOUND_TERMS": [list(t) for t in new],
        "NEW_PROVEN_T_CAP": proof["NEW_T_CAP"],
        "NEW_PROVEN_S4_FLOOR": 112,
        "NEW_PROVEN_S5_CAP": "NOT_ADOPTED",
        "NEW_FULL_PROFILE_BOUND": bound,
        "MAX_T": max(t[0] for t in new if t[1] == bound),
        "EXACT_PROFILE_DELTA": before[TARGET] - bound,
        "MINIMAL_SUFFICIENT_T_CAP": 263,
        "MINIMAL_T263_BOUND": max(t[1] for t in envelope(263)),
        "STRICT_GAIN_EXCLUDED": "YES" if bound <= 313263888 else "NO",
        "GAP_TO_INCUMBENT": bound - 313263888,
        "LEDGER_ROWS": len(after),
        "OTHER_TIED_OWNER_PRESERVED": "PASS",
        "OTHER_OWNER_BOUND": after[OTHER],
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_PROFILE_COUNT": len(coarse),
        "CURSOR_BOUND": max(coarse.values()),
        "CURSOR_SHA256": sha(render(cursor)),
        "OTHER_4646_ROWS_SHA256": sha(projection({p: b for p, b in after.items() if p != TARGET})),
        "PROJECTED_LEDGER_SHA256": sha(projection(after)),
        "FAMILY_AFTER_SINGLE_ROW": family,
        "SINGLE_ROW_FAMILY_DELTA": max([*before.values(), *coarse.values()]) - family,
        "FAMILY_OWNER_IDS": sorted(p for p, b in {**after, **coarse}.items() if b == family),
        "INHERITED_CAVEATS_REFERENCE": {
            "HEAD": BASE_HEAD,
            "PATH": BASE_RESULT,
            "KEY": "INHERITED_CAVEATS_AND_STATUS_VERBATIM",
            "VALUE_SHA256": sha(render(inherited)),
            "DISPOSITION": "Preserved verbatim in immutable Base; no status upgraded.",
        },
        "ORIGINAL_BONF5_STATUS_VERBATIM": sealed["DONOR_ORIGINAL_STATUS_VERBATIM"],
        "BASE_ACCEPTANCE": "VERIFIED_WITH_CAVEATS",
        "A01_TO_A16_AT_SEAL": gates,
        "GATE_SCOPE": "A14 Judge and A15 commit/clean/release remain external lifecycle.",
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "EXISTING_SOURCE_MUTATED": "NO",
        "OTHER_WORKTREE_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    raw = render(compute_result())
    if args.verify:
        check(RESULT.read_bytes() == raw, "exact result differs")
    else:
        with RESULT.open("xb") as output:
            output.write(raw)
    print(json.dumps({"T_CAP": certify()["NEW_T_CAP"], "RESULT_SHA256": sha(raw)}))


if __name__ == "__main__":
    main()
