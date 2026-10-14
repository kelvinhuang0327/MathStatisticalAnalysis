"""Universal T<=248 certificate for exactly 66655555555421100000.

Frozen model: 20 tickets, six DISTINCT labels each, exactly 22 triple supports
and 27 pair supports, with no other support sizes and no repeated ticket pair
across supports. The triple degree histogram is 6^3,5^8,4,2,1^2,0^5.
The simple overlap graph G has g_x=6+d_x and E=3*22+27=93, W=828.
Counting mixed triples gives Goodman T(G)+T(H)=C(20,3)-sum g(19-g)/2=294.
Write K={d>0}, Z={d=0}, M=H[K], N=H[Z], |K|=15, |Z|=5.
Let sigma_x=|G(x) intersect Z|, zeta_u=|G(u) intersect K|, r=sum sigma=sum zeta.
All cross edges are pair supports: 0<=sigma<=6-d; 2<=zeta<=6.
Internal H degrees are h_x=8-d_x+sigma_x, a_u=zeta_u-2.
Thus |E(M)|=(54+r)/2, |E(N)|=(r-10)/2, 10<=r<=24, r even.

For xy in M, its common H zero neighbours number
5-sigma_x-sigma_y+c_Z(xy), where c_Z counts common G zero neighbours.
For uv in N the analogous number is 15-zeta_u-zeta_v+c_K(uv).
Every mixed H triangle has exactly one same-part edge, so
 T(H)=5|E(M)|+15|E(N)|-sum sigma*h-sum zeta*a+P,
 P=T(M)+T(N)+sum_{xy in M} c_Z(xy)+sum_{uv in N} c_K(uv)>=0.
Each of these FOUR summands is a count of explicitly specified sets, hence
nonnegative. Since 5|E(M)|+15|E(N)|=60+10r, substitution gives the identity
 T(G)=234+sum_K sigma_x(sigma_x-d_x-4)+sum_Z zeta_u^2-P.
All later corrections bound P FROM BELOW; dropping its uncounted terms
increases the upper bound. In particular no zero-side correction is adopted.

Shadow exclusion, independent of sigma. The triple shadow S has degree 2d.
Let u,v be the two d=1 vertices. If their unique triple is {u,v,c}, every
d=6 vertex x is outside it when d_c=2, and cannot be shadow-adjacent to u or v.
It has exactly 12 possible other core neighbours and needs all 12, including c.
Then c has u,v and all three d=6 neighbours, exceeding its shadow degree four.
If the unique triples are {u,a,c},{v,b,c}, pair-linearity forces a!=b.
When d_c=2, c's four shadow neighbours are exactly u,v,a,b. Each d=6 vertex
is shadow-adjacent to c: if it is a or b, the displayed triple proves this;
otherwise it cannot be adjacent to u or v and must use all other 12 neighbours.
Three distinct d=6 vertices cannot all fit in {a,b}, contradiction.
Therefore a COMMON companion cannot be d=2 in either case. A d=2 companion
in only one of two distinct triples is NOT excluded.

Relabel u,v so alpha=sigma_u<=beta=sigma_v; R=K minus {u,v}, |R|=13.
Branch A, beta<5: use the valid correction p=0.
Branch B, alpha<beta=5: v's only two G core neighbours are its triple partners.
If u and v are adjacent in M (hence nonadjacent in G), at least
h_u-1-2=4+alpha other vertices form M triangles with their edge; that edge
also has alpha common G zero neighbours. Thus p>=4+2alpha.
If u,v share their unique triple {u,v,c}, c is in R and d_c!=2.
Put R'=R minus {c}. No M edge joins u,v,c to each other. Its induced edge
count is e_R=|E(M)|-h_u-h_v-h_c=r/2+d_c-alpha-sigma_c.
Necessarily e_R>=0 and e_R>=max_{x in R'}(h_x-3), since removing three
vertices removes at most three incident M edges. Also e_R<=C(12,2).
All R' vertices are M neighbours of v, giving e_R triangles and
sum_{R'} sigma=r-alpha-5-sigma_c common-zero contributions. Thus
p>=e_R+r-alpha-5-sigma_c. These two cases are exhaustive and disjoint.

Branch C, alpha=beta=5. Same triple: the same e_R constraints apply;
both lows are M-adjacent to all R', yielding p>=2e_R+2(r-10-sigma_c).
Distinct triples: their companion pairs A,B lie in R. A=B is forbidden by
pair-linearity; k=|A intersect B| is 0 or 1. A common d=2 is forbidden above.
The lows are M-adjacent. Put e=|E(M[R])|=|E(M)|-(12+12-1)=4+r/2.
Internal residual degrees are m_x=h_x-2+1_A(x)+1_B(x).
Each companion pair is a G edge, hence is absent in M. Therefore
 tau_A=|E(M[R minus A])|=e-sum_A h+2-k>=0,
 tau_B=|E(M[R minus B])|=e-sum_B h+2-k>=0.
Triangles with only u, only v, and both lows are disjoint categories;
their counts are tau_A, tau_B, 13-|A union B|=9+k respectively.
Common-zero contributions from uv, u--(R minus A), v--(R minus B)
are respectively 5, r-10-sum_A sigma, r-10-sum_B sigma. Hence
 p>=tau_A+tau_B+9+k+2r-15-sum_A sigma-sum_B sigma.
The k corrections include both degree overlap and triangle overlap; none
may be omitted or reversed. All uncounted triangles/contributions are >=0.
For each sigma, minimize these LOWER corrections over its possible cases.
Every legal realization's case is included, so this minimum remains a lower
bound for its P. Then subtract it, never add it, in the upper bound.

Coverage and complete enumeration. Sorting sigma within equal-d classes and
sorting alpha,beta are bijective relabelings, preserving all necessary tests.
Three d=6 sigma entries are zero. The eight d=5 entries have 9 sorted choices,
the d=4 entry 3, d=2 entry 5, the sorted low pair 21: 2835 canonical sigmas.
Equal cross totals and parity retain 1087, partitioned A/B/C=705/314/68.
Every legal G[Z] is one of the 2^10=1024 labelled simple zero graphs. Its
zeta is 6 minus its degree; retain max sum zeta^2 per r. Independent
maximization relaxes simultaneous core/cross/zero existence, never restricts it.
For beta=5 all 13 shared companions are considered; exclude d=2 and the
necessary e_R inequality, accounting for 4966=382+11+4573 candidates.
For C all 78^2 ordered pairs per sigma are considered, accounting for
413712=5304 equal-pair+8976 common-d2+1452 negative-tau+397980 retained.
No extra graphical, solver, or support-attainment assumptions are imposed.
Thus every legal realization maps to a retained sigma, a represented zero
graph and an admitted case. Two generators (CWR/product vs recursive counts,
G bit subsets vs H combinations, formulas vs residual degree counting)
independently match all records and counts. Exact r=10,12,...,24 maxima are
246,248,248,246,246,244,246,228. It follows universally T(G)<=248.
Legal attainment of this relaxed maximum is UNKNOWN, not asserted.

Route B uses the existing pinned K4 theorem: W=828, sum C(g,3)=2326,
g_max-2=10, A_max=floor(sum d(g-2)/3)=198. Consequently
q(t)=max(0,ceil((2326-10*(828-3t))/4))=max(0,ceil((30t-5954)/4)).
The 5956 constant belongs to another profile and is rejected here.
S4>=max(112,679q-231min(q,198)); the floors are maximized, never summed.
Every old t=22..265 and new t=22..248 is checked by integers, Fractions,
and the pinned Base Route-B evaluator. S3=2800(W-3t)+20272(t-22)+7000*22.
At t=248, q=372, S4=206850, S3=4970672; the FULL envelope maximum is
313242512. The final upper bound rounds UP after subtracting 4*S4/7.
Only an in-memory copy of one Base row changes. All 4647 rows and 197 cursor
profiles are replayed read-only. The other owner stays at 313395060:
profile delta=152548, single-row family delta=0, strict gain excluded YES.
No family authority update, global K20 optimality or prediction gain is claimed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import stat
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_T248_EXACT_FORMAL_HANDOFF_R2"
OWNER_CONVERSATION_ID = "01a138c8-b987-7123-ace1-15150589e708"
BASE_HEAD = "64c4c6b66640616c44c6cab14d359ba81aacad22"
BASE_TREE = "f406bf732ebcd7c962162e27d4f6a4b6c1c9c961"
BASE_SHA = "ab4711dc900e529dddfbf27606155c267075d6d854360a28682cc70b947adb7c"
DIRECTORY = "docs/research/matrix-native-results"
BASE_RESULT = f"{DIRECTORY}/b649-min-s2-three-max-owners-exact-authority-r1-result-{BASE_SHA}.json"
SOURCE = "src/lottolab/research/b649_min_s2_t248_exact_formal_handoff_r2.py"
TEST = "tests/unit/test_b649_min_s2_t248_exact_formal_handoff_r2.py"
RESULT = f"{DIRECTORY}/b649-min-s2-t248-exact-formal-handoff-r2-result.json"
TARGET = "66655555555421100000"
D = (6,) * 3 + (5,) * 8 + (4, 2, 1, 1)
CAP = 248
LEGACY_RESEARCH_DIGEST = "1bc95413d36a88dec3ef5e8ea61eebfb72a6d60ba276aaa59c3f576495978230"
MODEL: dict[str, object] = {
    "TICKETS": 20,
    "DISTINCT_LABELS_PER_TICKET": 6,
    "TRIPLES": 22,
    "PAIRS": 27,
    "SUPPORT_SIZES": [2, 3],
    "PAIR_LINEARITY": True,
}
PINS = (
    (BASE_HEAD, BASE_TREE, BASE_RESULT, BASE_SHA),
    (
        "ef69e3fb4a2fdb171c4bc6944a3672706506beac",
        "bb8615cfe4af6d78bf55756b37a3f8530b05a304",
        f"{DIRECTORY}/b649-three-max-profiles-shared-certificate-r2-result.json",
        "dc28b0f4e3bfb14be8a39a3d3148f1d27aadf3e060c89a8e6e695dfea55babcc",
    ),
    (
        "e3c650d1b298f3df7f2ecaeccca63305653b3bba",
        "fe1d00b3b842cdd9494af7e6a4082f0dcf580f91",
        f"{DIRECTORY}/b649-min-s2-owner-t223-formal-cert-r1-result.json",
        "7425b8826e8eddb3d4b930a9f8b1579fc96dbfbdd9c2014a0a34aaf2ef69c48d",
    ),
)
EXPECTED_COUNTS = {
    "RAW_SIGMA": 2835,
    "RETAINED_SIGMA": 1087,
    "ZERO_GRAPHS": 1024,
    "BRANCH_A": 705,
    "BRANCH_B": 314,
    "BRANCH_C": 68,
    "SAME_CANDIDATES": 4966,
    "SAME_D2_EXCLUDED": 382,
    "SAME_ER_EXCLUDED": 11,
    "SAME_RETAINED": 4573,
    "DISTINCT_CANDIDATES": 413712,
    "DISTINCT_EQUAL_EXCLUDED": 5304,
    "DISTINCT_D2_EXCLUDED": 8976,
    "DISTINCT_TAU_EXCLUDED": 1452,
    "DISTINCT_RETAINED": 397980,
}
EXPECTED_MAXIMA = dict(zip(range(10, 25, 2), (246, 248, 248, 246, 246, 244, 246, 228), strict=True))
HISTORICAL_R14 = (
    "Inherited historical R14 shared-refs drift caveat retained. Shared Git refs can be "
    "updated by other sessions. This task claims only its own new branch/worktree, "
    "index/object/lock writes and one accepted local commit; it does not claim global "
    "shared-repository ref immutability. No historical drift is attributed to this task."
)
type Document = dict[str, object]
type Sigma = tuple[int, ...]
type Term = tuple[int, int, int, int, int, int]


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def obj(value: object) -> Document:
    require(isinstance(value, dict), "object required")
    return cast(Document, value)


def integer(value: object) -> int:
    require(type(value) is int, "exact integer required")
    return cast(int, value)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def checked_blob(head: str, path: str, digest: str) -> bytes:
    metadata = git("ls-tree", head, "--", path).split()
    require(len(metadata) == 4 and metadata[0] == b"100644", "unsafe/missing pinned blob")
    raw = git("cat-file", "blob", f"{head}:{path}")
    require(sha(raw) == digest, "source/result hash mismatch")
    return raw


def model_facts(pid: str = TARGET, model: Mapping[str, object] | None = None) -> Document:
    frozen = MODEL if model is None else model
    require(pid == TARGET and tuple(map(int, pid)) == (*D, 0, 0, 0, 0, 0), "wrong profile")
    require(render(dict(frozen)) == render(MODEL), "wrong frozen support model")
    g = [6 + d for d in (*D, 0, 0, 0, 0, 0)]
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    require(sum(D) == 66 and sum(g) == 186 and goodman == 294, "degree/Goodman identity")
    return {
        "MODEL": dict(frozen),
        "D": [*D, 0, 0, 0, 0, 0],
        "G_EDGES": 3 * 22 + 27,
        "W": sum(comb(v, 2) for v in g),
        "GOODMAN_SUM": int(goodman),
        "SUM_CHOOSE3_DEGREES": sum(comb(v, 3) for v in g),
        "A_MAX": sum(d * (4 + d) for d in D) // 3,
        "SPLIT_CONSTANT": 294 - 60,
        "CORE": 15,
        "ZEROS": 5,
    }


def validate_sigma(s: Sigma) -> None:
    require(len(s) == 15 and all(type(v) is int for v in s), "sigma shape/integer")
    require(all(0 <= v <= 6 - d for v, d in zip(s, D, strict=True)), "sigma capacity")
    require(tuple(sorted(s[3:11])) == s[3:11] and s[13] <= s[14], "sigma ordering")
    require(10 <= sum(s) <= 24 and sum(s) % 2 == 0, "cross sum/parity")


def primary_sigmas() -> list[Sigma]:
    return [
        (0, 0, 0, *ones, four, two, *lows)
        for ones, four, two, lows in product(
            combinations_with_replacement(range(2), 8),
            range(3),
            range(5),
            combinations_with_replacement(range(6), 2),
        )
    ]


def independent_sigmas() -> list[Sigma]:
    def visit(prefix: Sigma) -> Iterator[Sigma]:
        pos = len(prefix)
        if pos == 15:
            yield prefix
            return
        low = prefix[-1] if pos and D[pos] == D[pos - 1] else 0
        for value in range(low, 7 - D[pos]):
            yield from visit((*prefix, value))

    return list(visit(()))


def zero_domain(independent: bool = False) -> tuple[dict[int, int], str]:
    edges = list(combinations(range(5), 2))
    graphs = (
        (tuple(c) for n in range(11) for c in combinations(edges, n))
        if independent
        else (tuple(e for i, e in enumerate(edges) if mask & (1 << i)) for mask in range(1024))
    )
    maximum: dict[int, int] = {}
    signatures: list[tuple[int, ...]] = []
    for graph in graphs:
        degrees = [sum(v in e for e in graph) for v in range(5)]
        # Independent generator enumerates H[Z], primary enumerates G[Z].
        zeta = [2 + v if independent else 6 - v for v in degrees]
        r = sum(zeta)
        maximum[r] = max(maximum.get(r, -1), sum(v * v for v in zeta))
        mask = sum(1 << edges.index(e) for e in graph)
        signatures.append((1023 ^ mask if independent else mask, *zeta))
    require(len(signatures) == 1024, "incomplete zero graph domain")
    return maximum, sha(render(sorted(signatures)))


def branch(s: Sigma) -> str:
    return "A" if s[-1] < 5 else "B" if s[-2] < 5 else "C"


def corrections(s: Sigma, counts: Counter[str]) -> list[int]:
    r, alpha, beta = sum(s), s[-2], s[-1]
    h = [8 - d + v for d, v in zip(D, s, strict=True)]
    if beta < 5:
        return [0]
    options = [4 + 2 * alpha] if alpha < 5 else []
    for c in range(13):
        counts["SAME_CANDIDATES"] += 1
        if D[c] == 2:
            counts["SAME_D2_EXCLUDED"] += 1
            continue
        remaining = [v for v in range(13) if v != c]
        e_r = r // 2 + D[c] - alpha - s[c]
        if e_r < max(0, *(h[v] - 3 for v in remaining)) or e_r > comb(12, 2):
            counts["SAME_ER_EXCLUDED"] += 1
            continue
        counts["SAME_RETAINED"] += 1
        cross = r - alpha - 5 - s[c]
        options.append((1 if alpha < 5 else 2) * (e_r + cross))
    if alpha < 5:
        return options
    pairs = list(combinations(range(13), 2))
    for a in pairs:
        for b in pairs:
            counts["DISTINCT_CANDIDATES"] += 1
            intersection = set(a) & set(b)
            if len(intersection) == 2:
                counts["DISTINCT_EQUAL_EXCLUDED"] += 1
                continue
            if any(D[v] == 2 for v in intersection):
                counts["DISTINCT_D2_EXCLUDED"] += 1
                continue
            k, edges = len(intersection), 4 + r // 2
            taus = [edges - sum(h[v] for v in pair) + 2 - k for pair in (a, b)]
            triangles = 9 + k
            cross = 2 * r - 15 - sum(s[v] for v in a) - sum(s[v] for v in b)
            if min(taus) < 0:
                counts["DISTINCT_TAU_EXCLUDED"] += 1
                continue
            counts["DISTINCT_RETAINED"] += 1
            options.append(sum(taus) + triangles + cross)
    require(bool(options) and min(options) >= 0, "invalid lower correction")
    return options


@dataclass(frozen=True)
class Record:
    sigma: Sigma
    r: int
    branch: str
    core: int
    zero: int
    correction: int
    bound: int


def records_bytes(records: Sequence[Record], independent: bool = False) -> bytes:
    """v1|15 comma-separated sigmas|r|branch|core|zero|correction|bound LF UTF-8."""
    ordered = sorted(records, key=lambda record: record.sigma)
    if independent:
        return "".join(
            f"v1|{','.join(map(str, v.sigma))}|{v.r}|{v.branch}|{v.core}|{v.zero}|"
            f"{v.correction}|{v.bound}\n"
            for v in ordered
        ).encode("utf-8")
    lines = [
        "|".join(
            (
                "v1",
                ",".join(str(s) for s in v.sigma),
                str(v.r),
                v.branch,
                str(v.core),
                str(v.zero),
                str(v.correction),
                str(v.bound),
            )
        )
        for v in ordered
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def enumerate_records(independent: bool = False) -> tuple[list[Record], dict[str, int], str]:
    if independent:
        return independent_records()
    raw = primary_sigmas()
    zero, zero_hash = zero_domain()
    counts: Counter[str] = Counter({"RAW_SIGMA": len(raw), "ZERO_GRAPHS": 1024})
    records: list[Record] = []
    for s in sorted(raw):
        r = sum(s)
        if not 10 <= r <= 24 or r % 2:
            continue
        validate_sigma(s)
        counts["RETAINED_SIGMA"] += 1
        label = branch(s)
        counts[f"BRANCH_{label}"] += 1
        core = 234 + sum(v * (v - d - 4) for v, d in zip(s, D, strict=True))
        correction = min(corrections(s, counts))
        records.append(Record(s, r, label, core, zero[r], correction, core + zero[r] - correction))
    return records, dict(sorted(counts.items())), zero_hash


def independent_records() -> tuple[list[Record], dict[str, int], str]:
    """Separate recount using bit sets and residual edge/degree incidence identities."""
    domain = independent_sigmas()
    zero, zero_hash = zero_domain(True)
    counts: Counter[str] = Counter({"RAW_SIGMA": len(domain), "ZERO_GRAPHS": 1024})
    result: list[Record] = []
    pair_masks = [mask for mask in range(8192) if mask.bit_count() == 2]
    for s in domain:
        r = sum(s)
        if r not in range(10, 25, 2):
            continue
        h = [8 - D[i] + s[i] for i in range(15)]
        counts["RETAINED_SIGMA"] += 1
        beta, alpha = s[14], s[13]
        label = "C" if alpha == 5 else "B" if beta == 5 else "A"
        counts[f"BRANCH_{label}"] += 1
        lower = 0 if label == "A" else 4 + 2 * alpha if label == "B" else sys.maxsize
        if label != "A":
            for removed in range(13):
                counts["SAME_CANDIDATES"] += 1
                if 2 * D[removed] == 4:
                    counts["SAME_D2_EXCLUDED"] += 1
                    continue
                vertices = [v for v in range(13) if v != removed]
                edges = sum(h) // 2 - h[13] - h[14] - h[removed]
                if edges < 0 or edges > 66 or any(h[v] > edges + 3 for v in vertices):
                    counts["SAME_ER_EXCLUDED"] += 1
                    continue
                counts["SAME_RETAINED"] += 1
                low_vertices = [14] if label == "B" else [13, 14]
                candidate = sum(edges + sum(s[v] for v in vertices) for _ in low_vertices)
                lower = min(lower, candidate)
        if label == "C":
            for first in pair_masks:
                for second in pair_masks:
                    counts["DISTINCT_CANDIDATES"] += 1
                    if first == second:
                        counts["DISTINCT_EQUAL_EXCLUDED"] += 1
                        continue
                    if first & second & (1 << 12):
                        counts["DISTINCT_D2_EXCLUDED"] += 1
                        continue
                    residual = [
                        h[v] - int(not first & (1 << v)) - int(not second & (1 << v))
                        for v in range(13)
                    ]
                    edges = sum(residual) // 2
                    first_tau = edges - sum(residual[v] for v in range(13) if first & (1 << v))
                    second_tau = edges - sum(residual[v] for v in range(13) if second & (1 << v))
                    if first_tau < 0 or second_tau < 0:
                        counts["DISTINCT_TAU_EXCLUDED"] += 1
                        continue
                    counts["DISTINCT_RETAINED"] += 1
                    both_low_triangles = sum(not (first | second) & (1 << v) for v in range(13))
                    common_zeros = 5
                    for mask in (first, second):
                        common_zeros += sum(s[v] for v in range(13) if not mask & (1 << v))
                    lower = min(lower, first_tau + second_tau + both_low_triangles + common_zeros)
        require(0 <= lower < sys.maxsize, "independent case coverage")
        core = 294 - 5 * (sum(h) // 2) - 15 * ((r - 10) // 2)
        core += sum(s[i] * h[i] for i in range(15)) - 2 * r
        result.append(Record(s, r, label, core, zero[r], lower, core + zero[r] - lower))
    return result, dict(sorted(counts.items())), zero_hash


def validate_records(records: Sequence[Record], expected: Sequence[Record]) -> None:
    require(len(records) == len({v.sigma for v in records}) == 1087, "record coverage/duplicates")
    for v in records:
        validate_sigma(v.sigma)
        require(v.r == sum(v.sigma) and v.branch == branch(v.sigma), "wrong branch/r")
        require(v.bound == v.core + v.zero - v.correction, "wrong correction sign")
    require(list(records) == list(expected), "independent record/correction mismatch")


def certification() -> Document:
    first, counts, zero_hash = enumerate_records()
    second, independent_counts, independent_zero_hash = enumerate_records(True)
    require(primary_sigmas() == independent_sigmas(), "raw sigma domain differs")
    validate_records(first, second)
    require(counts == independent_counts == EXPECTED_COUNTS, "independent recount mismatch")
    require(zero_hash == independent_zero_hash, "independent zero graph set differs")
    raw = records_bytes(first)
    require(raw == records_bytes(second, True), "independent canonical encoding differs")
    maxima = {r: max(v.bound for v in first if v.r == r) for r in range(10, 25, 2)}
    require(maxima == EXPECTED_MAXIMA and max(maxima.values()) == CAP, "T cap/r maxima mismatch")
    return {
        "COUNTS": counts,
        "INDEPENDENT_COUNTS": independent_counts,
        "INDEPENDENT_RECOUNT": "PASS",
        "MAXIMA_BY_R": maxima,
        "RECORDS_SCHEMA": {
            "VERSION": "v1",
            "ORDER": "lexicographic numeric sigma tuple, strictly increasing",
            "FIELDS": ["v1", "sigma[15]", "r", "branch", "core", "zero", "correction", "bound"],
            "ENCODING": "UTF-8; decimal integers, no plus/leading zero; sigma comma delimiter; "
            "fields pipe delimiter; LF after every row including last; no header/BOM",
        },
        "RECORDS": [asdict(v) for v in first],
        "RECORDS_SHA256": sha(raw),
        "ZERO_GRAPH_RECORDS_SHA256": zero_hash,
        "COVERAGE_PROOF": __doc__,
        "LEGAL_T248_ATTAINMENT": "UNKNOWN",
        "NEW_PROVEN_T_CAP": CAP,
        "LEGACY_RESEARCH_DIGEST": LEGACY_RESEARCH_DIGEST,
        "LEGACY_DIGEST_MATCH": "NOT_VERIFIED",
        "LEGACY_DISPOSITION": "Original encoding unavailable; new schema and digest authoritative",
    }


def envelope(pid: str, cap: int, constant: int = 5954) -> list[Term]:
    model_facts(pid)
    require(type(cap) is int and cap in (248, 265), "wrong cap")
    require(type(constant) is int and constant == 10 * 828 - 2326, "wrong profile K4 constant")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        q = max(0, -(-(30 * t - constant) // 4))
        contained = min(q, 198)
        s4 = max(112, 679 * q - 231 * contained)
        s3 = 2800 * (828 - 3 * t) + 20272 * (t - 22) + 7000 * 22
        bound = (7 * (372228640 - 63838600 + s3) - 4 * s4 + 6) // 7
        terms.append((t, bound, q, contained, s4, s3))
    validate_terms(pid, cap, terms)
    return terms


def validate_terms(pid: str, cap: int, terms: Sequence[Term]) -> None:
    model_facts(pid)
    require(type(cap) is int and cap in (248, 265), "wrong cap")
    require([term[0] for term in terms] == list(range(22, cap + 1)), "incomplete envelope")
    for t, bound, q, contained, s4, s3 in terms:
        require(all(type(v) is int for v in (t, bound, q, contained, s4, s3)), "noninteger term")
        excess = Fraction(2326 - 10 * (828 - 3 * t), 4)
        expected_q = max(0, -(-excess.numerator // excess.denominator))
        expected_s4 = max(112, 448 * min(expected_q, 198) + 679 * max(0, expected_q - 198))
        expected_s3 = 7000 * 22 + 20272 * (t - 22) + 2800 * (828 - 3 * t)
        exact = Fraction(372228640 - 63838600 + expected_s3) - Fraction(4 * expected_s4, 7)
        require(q == expected_q and contained == min(q, 198), "K4 ceiling/containment rounding")
        require(s4 == expected_s4 and s3 == expected_s3, "S4 floor/S3 mismatch")
        require(bound == -(-exact.numerator // exact.denominator), "final upper ceiling rounding")
    require(
        list(terms) == route.route_b_envelope(tuple(map(int, pid)), cap, 112),
        "pinned Route-B complete envelope differs",
    )


def pinned_sources() -> dict[str, str]:
    pending = ["src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py"]
    pins: dict[str, str] = {}
    while pending:
        path = pending.pop()
        if path in pins:
            continue
        raw = git("cat-file", "blob", f"{BASE_HEAD}:{path}")
        checked_blob(BASE_HEAD, path, sha(raw))
        local = ROOT / path
        require(
            stat.S_ISREG(local.lstat().st_mode) and local.read_bytes() == raw,
            f"reused evaluator source drift: {path}",
        )
        pins[path] = sha(raw)
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.ImportFrom) and node.level:
                require(node.level == 1, "unexpected helper import")
                names = [node.module] if node.module else [v.name for v in node.names]
                pending.extend(f"src/lottolab/research/{name}.py" for name in names)
    require(not any(name.startswith("ortools") for name in sys.modules), "solver imported")
    return dict(sorted(pins.items()))


def unique_object(pairs: list[tuple[str, object]]) -> Document:
    require(len(pairs) == len({k for k, _ in pairs}), "duplicate JSON key")
    return dict(pairs)


def load_authority() -> tuple[Document, list[Document], dict[str, str]]:
    documents: list[Document] = []
    provenance: list[Document] = []
    for head, tree, path, digest in PINS:
        require(git("cat-file", "-t", head).strip() == b"commit", "wrong source commit")
        require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "wrong source tree")
        raw = checked_blob(head, path, digest)
        document = obj(json.loads(raw, object_pairs_hook=unique_object))
        require(render(document) == raw, "noncanonical immutable JSON")
        documents.append(document)
        provenance.append(
            {
                "HEAD": head,
                "TREE": tree,
                "RESULT": path,
                "RESULT_SHA256": sha(raw),
                "ORIGINAL_TASK_STATUS": document["TASK_STATUS"],
            }
        )
    base = documents[0]
    for path, key in (
        (
            "src/lottolab/research/b649_min_s2_three_max_owners_exact_authority_r1.py",
            "IMPLEMENTATION_SHA256",
        ),
        ("tests/unit/test_b649_min_s2_three_max_owners_exact_authority_r1.py", "TEST_SHA256"),
    ):
        digest = base[key]
        require(isinstance(digest, str), "missing Base source/test hash")
        checked_blob(BASE_HEAD, path, cast(str, digest))
    require(
        (ROOT / BASE_RESULT).read_bytes() == checked_blob(BASE_HEAD, BASE_RESULT, BASE_SHA),
        "local Base result drift",
    )
    message = git("cat-file", "commit", BASE_HEAD).split(b"\n\n", 1)[1].decode()
    require(
        "Fresh-context Judge: VERIFIED_WITH_CAVEATS\n" in message
        and f"Judged-tree: {BASE_TREE}\n" in message,
        "Base acceptance tree binding",
    )
    provenance[0]["ACCEPTANCE_MESSAGE_VERBATIM"] = message
    provenance[1]["ROLE"] = "Inherited model/evaluator provenance; NOT T248 shadow proof"
    provenance[2]["ROLE"] = "Inherited certificate provenance; T223 theorem NOT reexecuted"
    return base, provenance, pinned_sources()


def projection(rows: Mapping[str, int]) -> bytes:
    return json.dumps(
        [{"PROFILE_ID": p, "CURRENT_BOUND": rows[p]} for p in sorted(rows)], sort_keys=True
    ).encode()


def project_one(base: Document, cursor: Document, pid: str, cap: int, bound: int) -> Document:
    require(sha(render(base)) == BASE_SHA, "altered Base result")
    model_facts(pid)
    require(type(cap) is int and cap == CAP, "wrong projected cap")
    require(
        type(bound) is int and bound == max(t[1] for t in envelope(pid, cap)),
        "wrong projected full bound",
    )
    require(render(cursor) == render(base["CURSOR"]), "cursor mutation")
    before = {p: integer(b) for p, b in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    require(
        len(before) == 4647 and sha(projection(before)) == base["BOUNDS_SHA256_AFTER"],
        "resolved ledger coverage/hash",
    )
    coarse = {p: integer(b) for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(
        len(coarse) == 197
        and set(coarse) == set(cast(list[str], cursor["PROFILE_IDS"]))
        and not set(before).intersection(coarse),
        "cursor coverage",
    )
    require(sha(render(cursor)) == base["CURSOR_SHA256"], "cursor SHA mismatch")
    for p, b in coarse.items():
        require(
            route.r28.coarse_profile_envelope(tuple(map(int, p))).family_upper_bound == b,
            "cursor Base evaluator mismatch",
        )
    require(
        before[pid] == max(t[1] for t in envelope(pid, 265)) == 313395060, "old target full bound"
    )
    after = {**before, pid: bound}
    require([p for p in before if before[p] != after[p]] == [pid], "other row mutation")
    original_family, projected_family = before | coarse, after | coarse
    first, last = max(original_family.values()), max(projected_family.values())
    require(
        first == last == 313395060 and after["66655555555332000000"] == last,
        "single-row family/tied owner mismatch",
    )
    return {
        "RESOLVED_ROWS": len(before),
        "CURSOR_ROWS": len(coarse),
        "BOUNDS_SHA256_BEFORE": sha(projection(before)),
        "PROJECTED_BOUNDS_SHA256": sha(projection(after)),
        "OTHER_4646_BOUNDS_SHA256": sha(projection({p: b for p, b in before.items() if p != pid})),
        "FAMILY_BEFORE": first,
        "FAMILY_AFTER_SINGLE_ROW": last,
        "SINGLE_ROW_FAMILY_DELTA": first - last,
        "FAMILY_OWNERS_AFTER": sorted(p for p, b in projected_family.items() if b == last),
        "CURSOR_PRESERVED": "PASS",
        "AUTHORITY_UPDATED": False,
    }


def compute_result() -> Document:
    base, provenance, sources = load_authority()
    cert = certification()
    old, new = envelope(TARGET, 265), envelope(TARGET, CAP)
    bound = max(t[1] for t in new)
    require(
        bound == 313242512 and new[-1] == (248, 313242512, 372, 198, 206850, 4970672),
        "new full-profile bound mismatch",
    )
    incumbent = integer(base["INCUMBENT"])
    require(
        incumbent == 313263888 and max(t[1] for t in old) - bound == 152548,
        "incumbent/profile delta mismatch",
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_SINGLE_COMMIT",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "IMPLEMENTATION_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "SOURCE_PINS": sources,
        "PROVENANCE": provenance,
        "TARGET_PROFILE": TARGET,
        "MODEL_FACTS": model_facts(),
        "PROOF": __doc__,
        "ENUMERATION": cert,
        "OLD_T_CAP": 265,
        "NEW_PROVEN_T_CAP": CAP,
        "OLD_TERMS": old,
        "NEW_TERMS": new,
        "OLD_TERM_COUNT": len(old),
        "NEW_TERM_COUNT": len(new),
        "ROUTE_B_TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED", "S4_FLOOR", "S3"],
        "K4_CONSTANT": 5954,
        "S4_BOUND_AT_MAX": 206850,
        "FULL_PROFILE_BOUND": bound,
        "PROFILE_DELTA": max(t[1] for t in old) - bound,
        "INCUMBENT": incumbent,
        "MARGIN_BELOW_INCUMBENT": incumbent - bound,
        "STRICT_GAIN_EXCLUDED": "YES",
        "FAMILY_PROJECTION": project_one(base, obj(base["CURSOR"]), TARGET, CAP, bound),
        "INHERITED_BASE_RESULT_VERBATIM": base,
        "HISTORICAL_R14": HISTORICAL_R14,
        "G01_TO_G18_AT_SEAL": {
            f"G{i:02}": "PASS" if i <= 14 or i == 18 else "NOT_VERIFIED" for i in range(1, 19)
        },
        "GATE_STATUS_SCOPE": "Worker science; G15 checks, G16 Judge and G17 lifecycle external",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "FAMILY_AUTHORITY_MUTATED": "NO",
        "PRODUCTION_DB_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "TASK_OWNED_GIT_WRITES": [
            "new isolated worktree and codex branch",
            "worktree ownership lock",
            "task index and Git objects",
            "one post-acceptance local commit",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce the exact T248 profile certificate")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = ROOT / RESULT
    require(not args.verify or path.is_file(), "missing sealed result")
    result = compute_result()
    raw = render(result)
    if args.verify:
        require(path.read_bytes() == raw, "sealed result replay differs")
    else:
        with path.open("xb") as output:
            output.write(raw)
    print(
        json.dumps(
            {
                "FULL_PROFILE_BOUND": result["FULL_PROFILE_BOUND"],
                "NEW_PROVEN_T_CAP": CAP,
                "RESULT_SHA256": sha(raw),
                "RECORDS_SHA256": obj(result["ENUMERATION"])["RECORDS_SHA256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
