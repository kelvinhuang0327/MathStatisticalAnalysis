"""Universal T208 certificate for exactly 55555555555443000000.

Frozen model: 20 six-label tickets, 22 triple and 27 pair supports, with
pair-linearity. Every overlap degree is g=2d+(6-d)=6+d. The supports give
93 graph edges and at least 22 distinct graph triangles. No realization,
support attainment, global optimum, S5 authority or Family adoption is claimed.

UNIVERSAL COVERAGE. Split the vertices into K={d>0} and Z={d=0}; let
M=complement(G)[K], N=complement(G)[Z]. Write sigma_x=|NG(x) intersect Z|,
zeta_u=|NG(u) intersect K| and r=sum(sigma)=sum(zeta). Triple supports lie
entirely in K, so sigma_x<=6-d_x. A zero vertex has degree six and at most
five neighbours in Z, so 1<=zeta_u<=6. Thus 6<=r<=18. Degree balance gives
deg_M(x)=13-(6+d_x-sigma_x)=7-d_x+sigma_x and
deg_N(u)=5-(6-zeta_u)=zeta_u-1. Consequently
2e(M)=32+r, 2e(N)=r-6, and r is even.

EXACT TRIANGLE IDENTITY. Goodman gives T(G)+T(complement(G))=287. For an
edge xy of M, the number of common H-neighbours in Z is
6-sigma_x-sigma_y+c_Z(x,y), where c_Z=|NG(x) intersect NG(y) intersect Z|.
For an edge uv of N the analogous number in K is
14-zeta_u-zeta_v+c_K(u,v). Summing yields
T(H)=T(M)+T(N)+6e(M)-sum_K sigma*deg_M
                    +14e(N)-sum_Z zeta*deg_N+sum_EM c_Z+sum_EN c_K.
The four remainder sums count, respectively, H-triangles wholly in K,
wholly in Z, G-two-edge paths centred in Z whose endpoints form an M edge,
and G-two-edge paths centred in K whose endpoints form an N edge. These
objects have distinct vertex compositions (KKK, ZZZ, KKZ, KZZ), so no object
is counted in two remainder classes. Each common-neighbour cardinality and
triangle count is nonnegative. Substituting the degree/edge identities gives

 T(G)=233+sum_K sigma*(sigma-d-4)+sum_Z zeta**2-P,
 P=T(M)+T(N)+sum_EM c_Z+sum_EN c_K>=0.

Dropping P therefore gives an upper bound, without asserting P=0 or joint
attainment of any relaxed extrema. Every legal realization maps into the
enumerated domain: eleven binary sigma values, two ternary sigma values,
one quaternary sigma value, and one of all 2**15 labelled simple graphs N.
The 432 core classes aggregate only the eleven exchangeable d=5 vertices;
the two d=4 vertices remain labelled (12*3*3*4=432). A separate labelled
vertex max-plus/counting DP checks every r/score multiplicity after binomial
expansion of those classes. Independent Erdos-Gallai enumeration checks the
entire set of graphical sorted degree sequences found by the edge masks.
Only necessary conditions are used; relaxation extrema do not certify legal
support attainment. The per-r relaxation bounds have maximum 208.

ROUTE B APPLICABILITY. The frozen R2/R4/R30/R32 authority applies to this
same minimum-S2 model. A winning ticket hits at least three of the seven
main-plus-special labels. Chosen hit triples from distinct winning tickets
have disjoint label pairs by pair-linearity, hence at most C(7,2)/3=7 tickets
can win. For 0<=m<=7, the third Bonferroni sum minus (4/7)C(m,4) majorizes
the union indicator. Summing gives U<=S1-S2+S3-4*S4/7; all omitted S4
quartets are nonnegative and no S5 term is needed. R2 gives the exact local
quartet weights 448 (one contained triple), 679 (no contained triple), and
the universal S4 floor 112. R4 gives the exact S3 local-profile identity.

The open-wedge count is w=W-3t. At vertex v, every nonclique triple of its
neighbours contains a missing pair, and each such pair is in at most g_v-2
neighbour triples. Clique neighbour triples count each K4 four times. Thus
J<=4*K4+(g_max-2)*w. Here g_max=11, so the applicable multiplier is NINE,
not the weaker reference multiplier ten. This proves
q=max(0,ceil((J-9*w)/4)). A K4 contains at most one triple support, since
two triples in four vertices share a pair. For each triple S, its outside
common neighbours number at most sum_{v in S}(g_v-2)/3. Summing over S gives
A_max=floor(sum d_v*(g_v-2)/3)=193. Hence
S4>=max(112,679*q-231*min(q,193)). The right side increases with the true
K4 count, so substituting its lower bound is valid. The negative S4 sign is
essential. All integer t in 22..208 are checked against the formal evaluator
and an independent Fraction implementation, including exact ceilings and
all maximizing t. The weaker multiplier-ten reference is retained separately.

Historical caveats: original research was bounded symbolic work, not a sealed
certificate; the previous certificate task stopped before implementation.
The original research's conditional Family projection is not adopted here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import ceil, comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_higher_order_closure_r2 as r2
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32

type Document = dict[str, object]
ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_S3_T208_EXACT_PROFILE_CERTIFICATE_COMMITTED_R2"
PROFILE = "55555555555443000000"
STEM = "b649_s3_t208_exact_profile_certificate_r2"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
RESULT = "docs/research/matrix-native-results/" + STEM.replace("_", "-") + "-result.json"
BASE_HEAD = "9acea1331e021a9623fa593997d90cfc89a69136"
BASE_TREE = "de577e8d6f3ccbe52e663c96ee1528c95a0ee7ec"
BASE_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-owner-ab-t249-t260k4-composition-r1-result.json"
)
BASE_SHA256 = "9fbe17d020573835cd69f16296fee224ff4f83aef8b3e7a644f2ffaabdfe92c9"
RESEARCH_THREAD = "01a143f5-0ccd-7f81-8a69-b748cd481c8f"
RESEARCH_TURN = "01a143f5-18d7-7df3-81f1-6404044aa724"
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}
R_DOMAIN = tuple(range(6, 19, 2))


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected JSON object")
    return cast(Document, value)


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", "--no-optional-locks", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def working(path: str) -> bytes:
    target = ROOT / path
    require(target.is_file() and not target.is_symlink(), f"unsafe working path: {path}")
    return target.read_bytes()


def frozen(path: str) -> bytes:
    meta = git("ls-tree", BASE_HEAD, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        f"unsafe immutable path: {path}",
    )
    return git("cat-file", "blob", f"{BASE_HEAD}:{path}")


def base_identity() -> Document:
    for kind, identity in (("commit", BASE_HEAD), ("tree", BASE_TREE)):
        raw = git("cat-file", kind, identity)
        digest = hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw)
        require(digest.hexdigest() == identity, "immutable Git object identity")
    require(git("rev-parse", BASE_HEAD + "^{tree}").decode().strip() == BASE_TREE, "Base tree")
    raw = frozen(BASE_RESULT)
    require(sha(raw) == BASE_SHA256, "wrong Base SHA256")
    require(working(BASE_RESULT) == raw, "working Base bytes changed")
    base = obj(json.loads(raw))
    require(base["MODEL"] == MODEL, "Base model")
    old = obj(base["RESOLVED_ROW_BOUNDS"])[PROFILE]
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_PATH": BASE_RESULT,
        "RESULT_SHA256": sha(raw),
        "OLD_PROFILE_BOUND": old,
        "FAMILY_BOUND": obj(base["FAMILY_AFTER"])["FAMILY_BOUND"],
        "S5_AUTHORITY": base["S5_AUTHORITY"],
        "HISTORICAL_R15": base["HISTORICAL_R15"],
    }


def authority_pins() -> dict[str, str]:
    """Bind the actual imported research-module closure to the immutable Base."""
    pins: dict[str, str] = {}
    prefix = ROOT / "src/lottolab/research"
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not isinstance(filename, str):
            continue
        path = Path(filename).resolve()
        if path.parent != prefix or path == Path(__file__).resolve():
            continue
        relative = path.relative_to(ROOT).as_posix()
        require(working(relative) == frozen(relative), f"authority source changed: {relative}")
        pins[relative] = sha(working(relative))
    require(any(p.endswith("refinement_r32.py") for p in pins), "formal evaluator not loaded")
    return dict(sorted(pins.items()))


def facts() -> Document:
    ds = tuple(int(x) for x in PROFILE)
    histogram = {str(d): ds.count(d) for d in sorted(set(ds), reverse=True)}
    gs = tuple(6 + d for d in ds)
    total, squares = sum(ds), sum(d * d for d in ds)
    edges = sum(gs) // 2
    w, j = sum(comb(g, 2) for g in gs), sum(comb(g, 3) for g in gs)
    goodman = comb(len(ds), 3) - sum(g * (len(ds) - 1 - g) for g in gs) // 2
    capacities = [6 - d for d in ds if d > 0]
    require(total == 3 * MODEL["TRIPLES"] and edges == 3 * 22 + 27, "model incidence")
    return {
        "PROFILE": PROFILE,
        "DEGREE_HISTOGRAM": histogram,
        "SUM_D": total,
        "SUM_D2": squares,
        "E_G": edges,
        "W": w,
        "J": j,
        "GOODMAN": goodman,
        "A_MAX": sum(d * (g - 2) for d, g in zip(ds, gs, strict=True)) // 3,
        "G_MAX": max(gs),
        "CORE_VERTICES": sum(d > 0 for d in ds),
        "ZERO_VERTICES": ds.count(0),
        "RESIDUAL_CAPACITIES": capacities,
        "R_DOMAIN": list(range(ds.count(0), sum(capacities) + 1, 2)),
    }


def core_recount() -> Document:
    classes: list[list[int]] = []
    class_scores: dict[int, Counter[int]] = {}
    for ones, a, b, c in product(range(12), range(3), range(3), range(4)):
        r = ones + a + b + c
        score = -8 * ones + a * (a - 8) + b * (b - 8) + c * (c - 7)
        classes.append([ones, a, b, c, r, score, comb(11, ones)])
        class_scores.setdefault(r, Counter())[score] += comb(11, ones)
    require(len(classes) == 432, "missing core class")
    # Independent labelled-vertex DP: no histogram classes or class score formula.
    dp: dict[int, Counter[int]] = {0: Counter({0: 1})}
    maxplus = {0: 0}
    for degree in (5,) * 11 + (4,) * 2 + (3,):
        next_dp: dict[int, Counter[int]] = {}
        next_max: dict[int, int] = {}
        for r, scores in dp.items():
            for sigma in range(7 - degree):
                delta = sigma * (sigma - degree - 4)
                target = next_dp.setdefault(r + sigma, Counter())
                for score, count in scores.items():
                    target[score + delta] += count
        for r, best in maxplus.items():
            for sigma in range(7 - degree):
                score = best + sigma * (sigma - degree - 4)
                next_max[r + sigma] = max(next_max.get(r + sigma, score), score)
        dp, maxplus = next_dp, next_max
    require(class_scores == dp, "core r/score/multiplicity independent recount")
    require(maxplus == {r: max(scores) for r, scores in class_scores.items()}, "max-plus DP")
    spectrum = {str(r): [[s, n] for s, n in sorted(v.items())] for r, v in sorted(dp.items())}
    return {
        "CLASS_COUNT": len(classes),
        "CLASS_ROWS": classes,
        "LABELLED_ASSIGNMENT_COUNT": sum(sum(v.values()) for v in dp.values()),
        "R_SCORE_MULTIPLICITIES": spectrum,
        "DP_AGREEMENT": True,
        "MAXIMA": {str(r): maxplus[r] for r in R_DOMAIN},
    }


def graphical(degrees: Sequence[int]) -> bool:
    """Erdos-Gallai, independently of the mask enumeration."""
    ds = sorted(degrees, reverse=True)
    if sum(ds) % 2:
        return False
    return all(
        sum(ds[:k]) <= k * (k - 1) + sum(min(d, k) for d in ds[k:]) for k in range(1, len(ds) + 1)
    )


def zero_recount() -> Document:
    edges = tuple(combinations(range(6), 2))
    mask_sequences: dict[int, set[tuple[int, ...]]] = {r: set() for r in R_DOMAIN}
    mask_counts = dict.fromkeys(R_DOMAIN, 0)
    maxima: dict[int, int] = {}
    digest = hashlib.sha256()
    for mask in range(1 << len(edges)):
        digest.update(mask.to_bytes(2, "big"))
        degrees = [0] * 6
        for i, (u, v) in enumerate(edges):
            if mask & (1 << i):
                degrees[u] += 1
                degrees[v] += 1
        r = 6 + sum(degrees)
        if r not in mask_sequences:
            continue
        mask_counts[r] += 1
        mask_sequences[r].add(tuple(sorted(degrees)))
        score = sum((d + 1) ** 2 for d in degrees)
        maxima[r] = max(maxima.get(r, score), score)
    eg_sequences: dict[int, set[tuple[int, ...]]] = {r: set() for r in R_DOMAIN}
    eg_maxima: dict[int, int] = {}
    for ds in combinations_with_replacement(range(6), 6):
        r = 6 + sum(ds)
        if r in eg_sequences and graphical(ds):
            eg_sequences[r].add(ds)
            score = sum(d * d for d in ds) + 2 * (r - 6) + 6
            eg_maxima[r] = max(eg_maxima.get(r, score), score)
    require(mask_sequences == eg_sequences, "zero complete degree-sequence recount")
    require(maxima == eg_maxima, "zero per-r independent maxima")
    return {
        "MASK_COUNT": 1 << len(edges),
        "MASK_DOMAIN_SHA256": digest.hexdigest(),
        "FEASIBLE_MASK_COUNTS": {str(r): mask_counts[r] for r in R_DOMAIN},
        "GRAPHICAL_SEQUENCES": {str(r): sorted(mask_sequences[r]) for r in R_DOMAIN},
        "ERDOS_GALLAI_AGREEMENT": True,
        "MAXIMA": {str(r): maxima[r] for r in R_DOMAIN},
    }


def independent_terms(multiplier: int) -> list[list[int]]:
    """Fraction implementation, independent of all formal evaluator helpers."""
    degrees = [6 + int(d) for d in PROFILE]
    wedges = sum(g * (g - 1) // 2 for g in degrees)
    triples = sum(g * (g - 1) * (g - 2) // 6 for g in degrees)
    allowance = sum(int(d) * (4 + int(d)) for d in PROFILE) // 3
    terms: list[list[int]] = []
    for t in range(22, 209):
        opened = wedges - 3 * t
        q = max(0, ceil(Fraction(triples - multiplier * opened, 4)))
        contained = min(q, allowance)
        s4 = max(112, 448 * contained + 679 * (q - contained))
        s3 = 2800 * wedges + 11872 * (t - 22) - 30800
        bound = ceil(Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7))
        terms.append([t, bound, q, contained, s4, s3])
    return terms


def route_b() -> Document:
    ds = tuple(map(int, PROFILE))
    require(r32.structural_failures(ds) == [], "formal profile applicability")
    global_floor = r32.r28.profile_s4_floor(ds)
    require(
        global_floor == r2.k20_min_s2_s4_lower_bound_certificate().s4_lower_bound,
        "global S4 authority",
    )
    formal = [list(term) for term in r32.route_b_envelope(ds, 208, global_floor)]
    independent = independent_terms(max(6 + d for d in ds) - 2)
    require(formal == independent and len(formal) == 187, "all exact Route-B terms")
    require(r32.r30.k4_quartet_weights() == r32.K4_WEIGHTS, "formal quartet weights")
    # Finite pointwise proof of the precise coefficient and its direction.
    bonferroni: list[list[int]] = []
    for winners in range(8):
        lhs = Fraction(winners - comb(winners, 2) + comb(winners, 3))
        lhs -= Fraction(4 * comb(winners, 4), 7)
        require(lhs >= int(winners > 0), "wrong S4 correction sign/coefficient")
        bonferroni.append([winners, lhs.numerator, lhs.denominator])
    bound = max(row[1] for row in formal)
    reference = independent_terms(10)
    return {
        "AUTHORITY": "R2 local intersections and Bonferroni; R4 exact S3; R30/R32 Route B",
        "S5": "NONE; NOT_USED",
        "S4_SIGN": -1,
        "GLOBAL_S4_FLOOR": global_floor,
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_ALLOWANCE", "S4", "S3"],
        "T_RANGE": [22, 208],
        "TERM_COUNT": len(formal),
        "TERMS": formal,
        "FRACTION_AGREEMENT": True,
        "BONFERRONI_POINTWISE": bonferroni,
        "ARGMAX": [row[0] for row in formal if row[1] == bound],
        "FULL_BOUND": bound,
        "REFERENCE_MULTIPLIER_10_TERMS": reference,
        "REFERENCE_FULL_BOUND": max(row[1] for row in reference),
        "STRONGER_BOUND_EVIDENCE": {
            "PROVEN": True,
            "G_MAX": max(6 + d for d in ds),
            "OPEN_WEDGE_MULTIPLIER": max(6 + d for d in ds) - 2,
            "THEOREM": "J <= 4*K4 + (g_max-2)*(W-3*T); see module proof",
            "S4_AT_208": formal[-1][4],
            "REFERENCE_DIFFERENCE": max(row[1] for row in reference) - bound,
        },
    }


def compute_result() -> Document:
    base = base_identity()
    invariants = facts()
    core, zero = core_recount(), zero_recount()
    cm, zm = obj(core["MAXIMA"]), obj(zero["MAXIMA"])
    table = [
        [
            r,
            cast(int, cm[str(r)]),
            cast(int, zm[str(r)]),
            233 + cast(int, cm[str(r)]) + cast(int, zm[str(r)]),
        ]
        for r in R_DOMAIN
    ]
    cap = max(row[3] for row in table)
    require(cap == 208, "universal T relaxation cap")
    route = route_b()
    require(route["FULL_BOUND"] == 312835000, "target stronger bound not established")
    return {
        "TASK_ID": TASK_ID,
        "MODEL": MODEL,
        "BASE": base,
        "FACTS": invariants,
        "PROOF": __doc__,
        "CORE": core,
        "ZERO": zero,
        "R_CLASS_MAXIMA": table,
        "REMAINDER_TERMS": {"T(M)": 1, "T(N)": 1, "SUM_EM_C_Z": 1, "SUM_EN_C_K": 1},
        "REMAINDER_NONNEGATIVE": True,
        "UNIVERSAL_T_CAP": cap,
        "ROUTE_B": route,
        "FULL_PROFILE_BOUND": route["FULL_BOUND"],
        "SOURCE_SHA256": sha(working(SOURCE)),
        "TEST_SHA256": sha(working(TEST)),
        "EVALUATOR_SOURCE_PINS": authority_pins(),
        "ORIGINAL_RESEARCH_TASK": "B649_S3_NEXT_OWNER_INDEPENDENT_SYMBOLIC_R1",
        "RESEARCH_SOURCE": {"THREAD_ID": RESEARCH_THREAD, "TURN_ID": RESEARCH_TURN},
        "CANDIDATE_ZIP": "NOT_USED; independent implementation from original research",
        "PROFILE_DELTA": cast(int, base["OLD_PROFILE_BOUND"]) - cast(int, route["FULL_BOUND"]),
        "CONDITIONAL_FAMILY_EFFECT": {"REPORTED_DELTA": 1096, "DISPOSITION": "NOT_ADOPTED"},
        "FAMILY_AUTHORITY_MUTATED": False,
        "OTHER_PROFILE_CERTIFICATES_CHANGED": False,
        "HEAVY_SOLVER_STARTED": False,
        "REMOTE_WRITE": False,
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
    }


def verify_result(candidate: Mapping[str, object]) -> None:
    """The production verifier: every negative test invokes this entry point."""
    require(candidate.get("TASK_ID") == TASK_ID, "task identity")
    require(candidate == json.loads(render(compute_result())), "candidate/result inconsistency")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    payload = render(result)
    if args.write_result:
        require(not (ROOT / RESULT).exists(), "result already exists; read before replacement")
        (ROOT / RESULT).write_bytes(payload)
    else:
        require(working(RESULT) == payload, "committed result bytes inconsistent")
        verify_result(obj(json.loads(payload)))
    print(
        json.dumps(
            {
                "TASK_ID": TASK_ID,
                "UNIVERSAL_T_CAP": result["UNIVERSAL_T_CAP"],
                "FULL_PROFILE_BOUND": result["FULL_PROFILE_BOUND"],
                "RESULT_SHA256": sha(payload),
            }
        )
    )


if __name__ == "__main__":
    main()
