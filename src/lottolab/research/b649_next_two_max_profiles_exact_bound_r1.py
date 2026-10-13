"""Universal triangle caps for exactly two minimum-S2 profiles, A and B.

A = 66655555555332000000 and B = 66655555555421100000 are the two maximum rows
(313395060, triangle cap 265) after the pinned three-profile R2 certificate.

Model, as in R2. Twenty tickets, each holding six DISTINCT labels, use exactly
49 labels: 22 lie in exactly three tickets (triples) and 27 in exactly two
(pairs). Pair-linearity means two tickets share at most one label. d_v is the
number of triples on ticket v, and the profile is d sorted in descending order.
The support graph G joins two tickets that share a label. By linearity the
3*22+27 = 93 support pairs are distinct edges. Ticket v has 2d_v triple
neighbours and 6-d_v pair neighbours, all distinct, so g_v = deg_G(v) = 6+d_v.
T(G) is the triangle count that the Route-B evaluator needs capped.

Profile facts, derived separately for each profile and never copied.
A has histogram (6^3,5^8,3^2,2^1,0^6), sum d = 18+40+6+2 = 66.
B has histogram (6^3,5^8,4^1,2^1,1^2,0^5), sum d = 18+40+4+2+2 = 66.
For A, W = sum C(g,2) = 3*66+8*55+2*36+28+6*15 = 828.
For B, W = 3*66+8*55+45+28+2*21+5*15 = 828.
In both, sum g = 186 = 2*93 and sum g^2 = 2W+186 = 1842.
Goodman: a 3-set holding one or two G edges contributes exactly 2 to
sum_v g_v(19-g_v), once from each vertex incident to one edge and one non-edge;
a homogeneous 3-set contributes 0. So T(G)+T(H) = C(20,3)-sum g(19-g)/2 =
1140-(19*186-1842)/2 = 294 for both, where H is the complement of G.
Z = {d=0} and K is the rest. A has |K| = 3+8+2+1 = 14 and |Z| = 6. B has
|K| = 3+8+1+1+2 = 15 and |Z| = 5. Inside K, L = {d<=4} (A: d=3,3,2; B:
d=4,2,1,1), H5 = {d=5} (8 vertices) and H6 = {d=6} (3 vertices).

Necessary conditions. A label shared by x in K and z in Z is a label of z,
hence a pair label. Distinct Z-neighbours of x therefore use distinct pair
labels of x. So sigma_x = |Z_x| <= 6-d_x, where Z_x = N_G(x) & Z. In
particular H6 has sigma = 0 and H5 has sigma in {0,1}. For z in Z, g_z = 6 and
z has at most |Z|-1 neighbours in Z, so zeta_z = |N_G(z) & K| lies in
[max(0,7-|Z|), 6]; that is [1,6] for A and [2,6] for B. G[Z] is a simple graph
with degrees 6-zeta_z, and sum_K sigma = sum_Z zeta = r.

Exact split. Let M = H[K], N = H[Z] and k = |K|. Then
m_x = deg_M(x) = (k-1)-(g_x-sigma_x) = k-7-d_x+sigma_x and
n_z = deg_N(z) = (|Z|-1)-(6-zeta_z) = zeta_z+13-k.
An H triangle has 0, 1, 2 or 3 vertices in Z. With exactly one Z vertex it
holds exactly one M edge xy, and that vertex avoids N_G(x)|N_G(y): there are
|Z|-sigma_x-sigma_y+c_Z(xy) choices, where c_Z(xy) = |N_G(x)&N_G(y)&Z|. The
case of two Z vertices is symmetric. Hence
  T(H) = |Z|e(M)+k e(N)-sum_K sigma m-sum_Z zeta n+P,
  P = T(M)+T(N)+sum_{xy in E(M)} c_Z(xy)+sum_{uv in E(N)} c_K(uv).
Here 2e(M) = k(k-7)-66+r and 2e(N) = |Z|(|Z|-7)+r. Since |Z|+k = 20 and
sum d = 66, |Z|e(M)+k e(N) = 3|Z|(k-11)+10r. Goodman then gives exactly
  T(G) = C-10r+sum_K sigma_x(sigma_x+k-7-d_x)+sum_Z zeta_z(zeta_z+13-k)-P,
  C = 294-3|Z|(k-11).
For A: C = 294-54 = 240, m = 7-d+sigma, n = zeta-1.
For B: C = 294-60 = 234, m = 8-d+sigma, n = zeta-2.
The 237 of R2 came from W=825 and Goodman 291 with a 14/6 split, so it is not
reused. Each of the four parts of P counts an explicitly defined finite set,
so each is a non-negative integer.

Lower bounds on parts of P. Each holds for every realization, and dropping one
only weakens the bound.
(Z) T(N) is a function of G[Z]. For uv in E(N), c_K(uv) = #{x in K: u,v in
    Z_x}; only L vertices can have sigma >= 2, so this is exactly
    #{x in L: u,v in Z_x}.
(O) An L pair xy that is not a G edge is an M edge contributing |Z_x & Z_y|.
(D) Let D5 = {y in H5: sigma_y = 1} and delta_x = #{y in D5: Z_y <= Z_x} for
    x in L. The neighbours of x in K split into a_x neighbours in L and the
    rest in H, and number q_x = g_x-sigma_x = 6+d_x-sigma_x. At most q_x-a_x of
    those y are G-adjacent to x; every other one is an M edge with
    c_Z(xy) >= 1. These L-D5 pairs are disjoint from the L-L pairs in (O).
(C) For an M edge xy, N_M(x)-{y} and N_M(y)-{x} lie in K-{x,y}, so
    codeg_M(xy) >= m_x+m_y-k. Summing over the M edges inside L counts each M
    triangle with exactly two L vertices once and each triangle inside L three
    times. So T(M) >= max(T(M[L]), sum_{E(M[L])} (m_x+m_y-k)^+ - 2T(M[L])).
(F) Feasibility: a_x <= q_x. Degree budget: an H vertex y has at most m_y
    M-neighbours in L, so sum_L m-2e(M[L]) = e_M(L,H) <= sum_H m_y =
    |H6|(k-13)+|H5|(k-12)+|D5|.
(Z), (O) and (D) bound disjoint pieces of P, and (C) bounds T(M), so
P >= Z+O+D+C.

Relaxation. Every realization determines a state:
- for each z, the membership set b_z = {x in L: z in Z_x};
- tau_z = #{y in D5: Z_y = {z}};
- the labelled graph G[Z];
- the pattern A = E(G[L]).
The state satisfies sigma_x = #{z: x in b_z} <= 6-d_x, |D5| = sum tau <= 8,
the zeta range, deg_G[Z](z) = 6-zeta_z with zeta_z = |b_z|+tau_z, and (F).
It also satisfies
  T(G) <= U = C-10r+sum_L sigma(sigma+k-7-d)+(k-11)|D5|
              +sum_Z zeta(zeta+13-k)-Z-O-D-C.
A D5 vertex adds 1*(1+k-12) = k-11 and other H vertices add 0. The cap is the
maximum of U over EVERY state allowed by these necessary conditions:
- every multiset {b_z} (U is invariant under permuting Z, so b is taken
  ascending and tau non-increasing inside each block of equal b);
- every tau vector;
- the minimum of Z over every labelled simple graph on Z with the forced
  degrees;
- the minimum of O+D+C over every feasible pattern A.
Branch and bound skips a state only when a bound obtained by dropping
non-negative penalties is strictly below the running maximum. So the maximum
and all of its argmax states are exact for the relaxation. No support graph,
portfolio or outcome is enumerated, and no relaxation state is claimed to be
realizable.
Result: A <= 228, where no P part is load-bearing (graphicality of G[Z] alone
gives 228). B <= 252, where the leave-one-out ablation is recorded.

Old caps are both 265. Each is the minimum of the exact profile's own R30
INFEASIBLE refutation (at 266, accepted by the Base), NB 266 and class 274.
The new cap is min(old, analytic). The Route-B envelope keeps every integer T
in 22..cap; that is a necessary interval, not a claim that each T is
realizable. S4 is max(inherited, Route-B floor), never their sum; the
inherited floor is queried for each exact profile. Its credit is
floor(4*S4/7), so the final bound is rounded UP. Neither profile has an
adopted S5: the Base's PROFILE_CERTIFICATES, INHERITED_TARGET_BONFERRONI_5
and CERTIFICATES_ADOPTED scopes are checked, and S5 stays unused.

The R2 certificate is re-executed and must reproduce its stored result byte
for byte. Its after-ledger is the fixed input: the Base plus the donor A/B
numeric rows plus the three R2 rows. On it, the family maximum 313395060 and
the two owners A and B are reproduced before aggregation. All 4647 resolved
rows and all 197 cursor rows are then scanned, and only A and B change. This
is a CONDITIONAL_PROJECTION. It does not change canonical authority, claim a
global optimum or claim a prediction gain. One fresh focused scientific
review is requested.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, fields, replace
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from typing import cast

from . import b649_three_max_profiles_shared_certificate_r2 as r2

route, nb = r2.route, r2.nb
require, obj, integer, string, sha = r2.require, r2.obj, r2.integer, r2.string, r2.sha
render, git, identity, blob, decode = r2.render, r2.git, r2.identity, r2.blob, r2.decode

ROOT = r2.ROOT
TASK_ID = "B649_NEXT_TWO_MAX_PROFILES_EXACT_BOUND_R1"
IMPLEMENTATION_HEAD = "61bad6d9ed4bdb6977d076d6b7fa28ac7b05f82a"
IMPLEMENTATION_TREE = "78f4a11e774c3c6fe3a13d0f1ab10f7e7d8c7ed0"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
CERTIFICATE_HEAD = "ef69e3fb4a2fdb171c4bc6944a3672706506beac"
CERTIFICATE_TREE = "bb8615cfe4af6d78bf55756b37a3f8530b05a304"
DIRECTORY = r2.DIRECTORY
R2_PINS = {
    r2.SOURCE: "ac4890aba8f8524fb705fead03d4e36608c3ab299cd02f870db06f1a3848ba9d",
    r2.TEST: "d5d0d23543721fe918fd551d6756921d19e6c6cb89d4cec363edb7acd1973fac",
    f"{DIRECTORY}/b649-three-max-profiles-shared-certificate-r2-result.json": (
        "dc28b0f4e3bfb14be8a39a3d3148f1d27aadf3e060c89a8e6e695dfea55babcc"
    ),
}
R2_RESULT = f"{DIRECTORY}/b649-three-max-profiles-shared-certificate-r2-result.json"
TARGETS = ("66655555555332000000", "66655555555421100000")
HISTOGRAMS = ({6: 3, 5: 8, 3: 2, 2: 1, 0: 6}, {6: 3, 5: 8, 4: 1, 2: 1, 1: 2, 0: 5})
BASELINE_FAMILY = 313395060
SOURCE = "src/lottolab/research/b649_next_two_max_profiles_exact_bound_r1.py"
TEST = "tests/unit/test_b649_next_two_max_profiles_exact_bound_r1.py"
RESULT = ROOT / DIRECTORY / "b649-next-two-max-profiles-exact-bound-r1-result.json"
type Term = tuple[int, int, int, int, int, int]
type Pair = tuple[int, int]
MODEL = r2.MODEL


@dataclass(frozen=True)
class Claim:
    """Constants a profile must re-derive exactly; a mismatch rejects the theorem."""

    wedges: int
    goodman: int
    core: int
    zeros: int
    split_constant: int
    zeta_floor: int


CLAIMS = {
    TARGETS[0]: Claim(wedges=828, goodman=294, core=14, zeros=6, split_constant=240, zeta_floor=1),
    TARGETS[1]: Claim(wedges=828, goodman=294, core=15, zeros=5, split_constant=234, zeta_floor=2),
}


def theorem(
    pid: str, claim: Claim | None = None, assumptions: r2.Assumptions = MODEL
) -> dict[str, object]:
    """Re-derive every profile constant from the exact degree tuple alone."""
    require(
        assumptions == MODEL
        and assumptions.pair_linearity is True
        and assumptions.support_sizes == (2, 3),
        "wrong support assumptions",
    )
    require(pid in TARGETS, "wrong exact profile")
    d = tuple(map(int, pid))
    require(dict(Counter(d)) == HISTOGRAMS[TARGETS.index(pid)], "profile histogram mismatch")
    expected = CLAIMS[pid] if claim is None else claim
    g = tuple(6 + v for v in d)
    edges = assumptions.triples * comb(3, 2) + assumptions.pairs
    w = sum(comb(v, 2) for v in g)
    squares = sum(v * v for v in g)
    goodman = Fraction(comb(len(d), 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    via_w = Fraction(comb(20, 3)) - Fraction(19 * sum(g) - (2 * w + sum(g)), 2)
    require(
        len(d) == assumptions.tickets == 20
        and sum(d) == 3 * assumptions.triples == 66
        and assumptions.triples + assumptions.pairs == assumptions.labels
        and edges == 93
        and sum(g) == 2 * edges
        and squares == 2 * w + sum(g)
        and goodman == via_w
        and goodman.denominator == 1,
        "theorem degree/edge hypotheses fail",
    )
    require(w == expected.wedges, "wedge sum mismatch")
    require(goodman == expected.goodman, "Goodman identity mismatch")
    core, zeros = sum(1 for v in d if v > 0), d.count(0)
    require((core, zeros) == (expected.core, expected.zeros), "K/Z partition mismatch")
    # |Z|e(M)+k e(N) at r=0, from the two degree sums, must equal 3|Z|(k-11).
    twice = zeros * (core * (core - 7) - sum(d)) + core * zeros * (zeros - 7)
    require(twice == 6 * zeros * (core - 11), "split derivation")
    constant = integer(goodman.numerator) - 3 * zeros * (core - 11)
    require(constant == expected.split_constant, "split constant mismatch")
    floor = max(0, 7 - zeros)
    require(floor == expected.zeta_floor, "zeta range mismatch")
    low = [v for v in d if 1 <= v <= 4]
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "HISTOGRAM": {str(k): v for k, v in sorted(Counter(d).items(), reverse=True)},
        "VERTICES": len(d),
        "SUPPORT_EDGES": edges,
        "DEGREE_SUM_OF_D": sum(d),
        "DEGREE_SUM_OF_G": sum(g),
        "SUM_G_SQUARED": squares,
        "WEDGES": w,
        "GOODMAN_SUM": constant + 3 * zeros * (core - 11),
        "CORE_K": core,
        "ZERO_Z": zeros,
        "LOW_L_DEGREES": low,
        "H5_COUNT": d.count(5),
        "H6_COUNT": d.count(6),
        "SPLIT_CONSTANT": constant,
        "M_DEGREE": f"{core - 7}-d+sigma",
        "N_DEGREE": f"zeta-{core - 13}",
        "SIGMA_RANGE": "0..6-d_x for x in K",
        "ZETA_RANGE": [floor, 6],
        "IDENTITY": (
            f"T = {constant} - 10r + sum_K sigma(sigma+{core - 7}-d)"
            f" + sum_Z zeta(zeta-{core - 13}) - P"
        ),
        "ASSUMPTIONS": asdict(assumptions),
        "COMPLETENESS": "NOT_APPLICABLE — ANALYTIC_BOUND",
        "ATTAINABILITY": "NOT_ASSERTED",
    }


@dataclass(frozen=True)
class Ingredients:
    """Lower bounds on parts of P; each can be dropped for the ablation."""

    zero_triangles: bool = True  # (Z): T(N) + sum c_K, exact for the state
    low_pair_overlap: bool = True  # (O): L-L M edges
    d5_overlap: bool = True  # (D): L-D5 M edges
    codegree: bool = True  # (C): M triangles with at least two L vertices
    degree_budget: bool = True  # (F): e_M(L,H) <= sum_H m


FULL = Ingredients()
NO_PENALTY = Ingredients(False, False, False, False, False)


@dataclass(frozen=True)
class Shape:
    """K/Z data of any minimum-S2 degree tuple (targets and test realizations)."""

    core: int
    zeros: int
    low: tuple[int, ...]
    fives: int
    sixes: int
    constant: int
    zeta_floor: int


def shape(profile: Sequence[int]) -> Shape:
    d = tuple(sorted(profile, reverse=True))
    require(len(d) == 20 and sum(d) == 66 and all(0 <= v <= 6 for v in d), "not a min-S2 tuple")
    g = [6 + v for v in d]
    mixed = sum(v * (19 - v) for v in g)
    require(mixed % 2 == 0, "Goodman parity")
    zeros = d.count(0)
    core = 20 - zeros
    constant = comb(20, 3) - mixed // 2 - 3 * zeros * (core - 11)
    low = tuple(v for v in d if 1 <= v <= 4)
    return Shape(core, zeros, low, d.count(5), d.count(6), constant, max(0, 7 - zeros))


def head(sh: Shape, sigma: Sequence[int], d5: int, zeta: Sequence[int]) -> int:
    """C - 10r + sum_K sigma(sigma+k-7-d) + sum_Z zeta(zeta+13-k) for one state."""
    k = sh.core
    low = sum(s * (s + k - 7 - v) for s, v in zip(sigma, sh.low, strict=True))
    zero = sum(z * (z + 13 - k) for z in zeta)
    return sh.constant - 10 * (sum(sigma) + d5) + low + (k - 11) * d5 + zero


def triangles(vertices: int, edges: Collection[Pair]) -> int:
    return sum(
        1
        for a, b, c in combinations(range(vertices), 3)
        if (a, b) in edges and (a, c) in edges and (b, c) in edges
    )


def zero_penalty(bits: Sequence[int], nonedges: Sequence[Pair]) -> int:
    """(Z): T(N) + sum over N edges uv of #{x in L: u, v in Z_x}, for one G[Z]."""
    return triangles(len(bits), set(nonedges)) + sum(
        (bits[u] & bits[v]).bit_count() for u, v in nonedges
    )


@cache
def zero_graphs(zeros: int) -> dict[tuple[int, ...], tuple[tuple[Pair, ...], ...]]:
    """Every labelled simple graph on the Z positions, keyed by its degree tuple."""
    pairs = list(combinations(range(zeros), 2))
    groups: dict[tuple[int, ...], list[tuple[Pair, ...]]] = {}
    for mask in range(1 << len(pairs)):
        degree = [0] * zeros
        for i, (u, v) in enumerate(pairs):
            if mask >> i & 1:
                degree[u] += 1
                degree[v] += 1
        nonedges = tuple(p for i, p in enumerate(pairs) if not mask >> i & 1)
        groups.setdefault(tuple(degree), []).append(nonedges)
    require(sum(len(v) for v in groups.values()) == 1 << len(pairs), "graph census")
    return {key: tuple(value) for key, value in groups.items()}


@cache
def min_zero_penalty(column: tuple[tuple[int, int], ...], ingredients: Ingredients) -> int | None:
    """Minimum of (Z) over all G[Z] with degrees 6-zeta; None when none exists."""
    bits = [b for b, _ in column]
    graphs = zero_graphs(len(column)).get(tuple(6 - z for _, z in column), ())
    if not graphs:
        return None
    if not ingredients.zero_triangles:
        return 0
    return min(zero_penalty(bits, nonedges) for nonedges in graphs)


def low_parts(
    sh: Shape,
    sigma: Sequence[int],
    inter: Sequence[int],
    delta: Sequence[int],
    d5: int,
    adjacent: Collection[Pair],
    ingredients: Ingredients,
) -> tuple[int, int, int] | None:
    """(O), (D), (C) for one adjacency pattern A on L; None when (F) fails."""
    n, k = len(sh.low), sh.core
    pairs = list(combinations(range(n), 2))
    m = [k - 7 - v + s for v, s in zip(sh.low, sigma, strict=True)]
    room = [6 + v - s for v, s in zip(sh.low, sigma, strict=True)]
    a = [sum(1 for p in adjacent if x in p) for x in range(n)]
    if any(a[x] > room[x] for x in range(n)):
        return None
    loose = [i for i, p in enumerate(pairs) if p not in adjacent]
    budget = sh.sixes * (k - 13) + sh.fives * (k - 12) + d5
    if ingredients.degree_budget and sum(m) - 2 * len(loose) > budget:
        return None
    overlap = sum(inter[i] for i in loose) if ingredients.low_pair_overlap else 0
    d5_part = 0
    if ingredients.d5_overlap:
        d5_part = sum(max(0, delta[x] - (room[x] - a[x])) for x in range(n))
    codegree = 0
    if ingredients.codegree:
        inside = triangles(n, {pairs[i] for i in loose})
        forced = sum(max(0, m[pairs[i][0]] + m[pairs[i][1]] - k) for i in loose)
        codegree = max(inside, forced - 2 * inside)
    return overlap, d5_part, codegree


@cache
def min_low_penalty(
    sh: Shape,
    sigma: tuple[int, ...],
    inter: tuple[int, ...],
    delta: tuple[int, ...],
    d5: int,
    ingredients: Ingredients,
) -> int | None:
    """Minimum of (O)+(D)+(C) over every feasible G-adjacency pattern on L."""
    pairs = list(combinations(range(len(sh.low)), 2))
    best: int | None = None
    for mask in range(1 << len(pairs)):
        adjacent = {p for i, p in enumerate(pairs) if mask >> i & 1}
        parts = low_parts(sh, sigma, inter, delta, d5, adjacent, ingredients)
        if parts is not None and (best is None or sum(parts) < best):
            best = sum(parts)
    return best


def multisets(sh: Shape) -> Iterator[tuple[int, tuple[int, ...]]]:
    """Every b-multiset within the sigma caps, with a penalty-free upper bound."""
    n, k = len(sh.low), sh.core
    for bits in combinations_with_replacement(range(1 << n), sh.zeros):
        sigma = [sum(b >> i & 1 for b in bits) for i in range(n)]
        if any(s > 6 - v for s, v in zip(sigma, sh.low, strict=True)):
            continue
        bound = head(sh, sigma, 0, [0] * sh.zeros)
        for b in bits:
            lam = b.bit_count()
            bound += max(
                (lam + t) * (lam + t + 13 - k) + (k - 21) * t
                for t in range(max(0, sh.zeta_floor - lam), 7 - lam)
            )
        yield bound, bits


@cache
def relaxation(pid: str, ingredients: Ingredients = FULL) -> dict[str, object]:
    """Exact maximum of U over the necessary-condition state space, with all argmax."""
    sh = shape(tuple(map(int, pid)))
    n, k, zeros = len(sh.low), sh.core, sh.zeros
    pairs = list(combinations(range(n), 2))
    entries = sorted(multisets(sh), key=lambda e: (-e[0], e[1]))
    best: int | None = None
    argmax: list[dict[str, object]] = []
    evaluated = states = 0
    for bound, bits in entries:
        if best is not None and bound < best:
            break
        evaluated += 1
        sigma = tuple(sum(b >> i & 1 for b in bits) for i in range(n))
        inter = tuple(sum(b >> x & b >> y & 1 for b in bits) for x, y in pairs)
        lam = [b.bit_count() for b in bits]
        ranges = [range(max(0, sh.zeta_floor - x), 7 - x) for x in lam]
        base = head(sh, sigma, 0, [0] * zeros)
        for tau in product(*ranges):
            # Permuting Z fixes U: inside a block of equal b, tau is non-increasing.
            if any(bits[i] == bits[i - 1] and tau[i] > tau[i - 1] for i in range(1, zeros)):
                continue
            d5 = sum(tau)
            if d5 > sh.fives:
                continue
            zeta = tuple(x + t for x, t in zip(lam, tau, strict=True))
            upper = base + (k - 21) * d5 + sum(z * (z + 13 - k) for z in zeta)
            if best is not None and upper < best:
                continue
            states += 1
            zero = min_zero_penalty(tuple(sorted(zip(bits, zeta, strict=True))), ingredients)
            if zero is None or (best is not None and upper - zero < best):
                continue
            delta = tuple(
                sum(t for b, t in zip(bits, tau, strict=True) if b >> x & 1) for x in range(n)
            )
            low = min_low_penalty(sh, sigma, inter, delta, d5, ingredients)
            if low is None:
                continue
            value = upper - zero - low
            if best is None or value > best:
                best, argmax = value, []
            if value == best:
                argmax.append(
                    {
                        "Z_MEMBERSHIP_OF_LOW": [[x for x in range(n) if b >> x & 1] for b in bits],
                        "TAU": list(tau),
                        "ZETA": list(zeta),
                        "SIGMA_LOW": list(sigma),
                        "D5": d5,
                        "R": sum(sigma) + d5,
                        "UPPER_WITHOUT_PENALTIES": upper,
                        "MIN_ZERO_PENALTY": zero,
                        "MIN_LOW_PENALTY": low,
                        "VALUE": value,
                    }
                )
    require(best is not None, "empty relaxation")
    return {
        "CAP": cast(int, best),
        "LOW_ORDER_D": list(sh.low),
        "ALL_ARGMAX_STATES": argmax,
        "MULTISETS_IN_DOMAIN": len(entries),
        "MULTISETS_EVALUATED": evaluated,
        "STATES_REACHING_PENALTIES": states,
        "INGREDIENTS": asdict(ingredients),
    }


def ablation(pid: str) -> dict[str, int]:
    """Leave-one-out caps; NO_PENALTY keeps only identity, ranges and graphicality."""
    caps = {"ALL": integer(relaxation(pid)["CAP"])}
    for item in fields(Ingredients):
        caps[f"WITHOUT_{item.name.upper()}"] = integer(
            relaxation(pid, replace(FULL, **{item.name: False}))["CAP"]
        )
    caps["NO_PENALTY"] = integer(relaxation(pid, NO_PENALTY)["CAP"])
    return caps


@dataclass(frozen=True)
class Realization:
    """One concrete support system: 22 triple and 27 pair supports on tickets 0..19."""

    triples: tuple[tuple[int, int, int], ...]
    pairs: tuple[Pair, ...]


def audit(real: Realization) -> dict[str, int]:
    """Check the exact split and every penalty inequality on one realization."""
    supports = [tuple(sorted(s)) for s in (*real.triples, *real.pairs)]
    require(
        len(real.triples) == MODEL.triples
        and len(real.pairs) == MODEL.pairs
        and all(len(set(s)) == len(s) and all(0 <= v < 20 for v in s) for s in supports),
        "realization supports",
    )
    load = Counter(v for s in supports for v in s)
    require(all(load[v] == MODEL.labels_per_ticket for v in range(20)), "six labels per ticket")
    covered = [p for s in supports for p in combinations(s, 2)]
    require(len(covered) == len(set(covered)) == 93, "pair-linearity")
    nbr: list[set[int]] = [set() for _ in range(20)]
    for u, v in covered:
        nbr[u].add(v)
        nbr[v].add(u)
    d = [sum(1 for s in real.triples if v in s) for v in range(20)]
    sh = shape(d)
    zs = [v for v in range(20) if d[v] == 0]
    ks = [v for v in range(20) if d[v] > 0]
    zset, kset = set(zs), set(ks)
    low = sorted((v for v in ks if d[v] <= 4), key=lambda v: (-d[v], v))
    heavy = [v for v in ks if d[v] >= 5]
    total = sum(
        1 for a, b, c in combinations(range(20), 3) if b in nbr[a] and c in nbr[a] and c in nbr[b]
    )
    sigma = {x: len(nbr[x] & zset) for x in ks}
    zeta = {z: len(nbr[z] & kset) for z in zs}
    require(all(sigma[x] <= 6 - d[x] for x in ks), "sigma range")
    require(all(sh.zeta_floor <= zeta[z] <= 6 for z in zs), "zeta range")
    m_pairs = {(x, y) for x, y in combinations(ks, 2) if y not in nbr[x]}
    n_pairs = {(u, v) for u, v in combinations(zs, 2) if v not in nbr[u]}
    t_m = sum(1 for a, b, c in combinations(ks, 3) if {(a, b), (a, c), (b, c)} <= m_pairs)
    t_n = sum(1 for a, b, c in combinations(zs, 3) if {(a, b), (a, c), (b, c)} <= n_pairs)
    c_z = sum(len(nbr[x] & nbr[y] & zset) for x, y in m_pairs)
    c_k = sum(len(nbr[u] & nbr[v] & kset) for u, v in n_pairs)
    k = sh.core
    exact = (
        sh.constant
        - 10 * sum(sigma.values())
        + sum(sigma[x] * (sigma[x] + k - 7 - d[x]) for x in ks)
        + sum(zeta[z] * (zeta[z] + 13 - k) for z in zs)
    )
    require(total == exact - (t_m + t_n + c_z + c_k), "exact split identity")
    d5 = [y for y in heavy if sigma[y] == 1]
    require(all(sigma[y] == 0 for y in heavy if d[y] == 6), "H6 sigma")
    bits = [sum(1 << i for i, x in enumerate(low) if z in nbr[x]) for z in zs]
    tau = [sum(1 for y in d5 if nbr[y] & zset == {z}) for z in zs]
    sig_low = [sigma[x] for x in low]
    require(head(sh, sig_low, len(d5), [zeta[z] for z in zs]) == exact, "state head")
    require(
        [b.bit_count() + t for b, t in zip(bits, tau, strict=True)] == [zeta[z] for z in zs], "zeta"
    )
    index = {z: i for i, z in enumerate(zs)}
    zero = zero_penalty(bits, sorted((index[u], index[v]) for u, v in n_pairs))
    require(zero == t_n + c_k, "(Z) is not exact")
    lpairs = list(combinations(range(len(low)), 2))
    adjacent = {(i, j) for i, j in lpairs if low[j] in nbr[low[i]]}
    inter = [len(nbr[low[i]] & nbr[low[j]] & zset) for i, j in lpairs]
    delta = [sum(1 for y in d5 if nbr[y] & zset <= nbr[x]) for x in low]
    parts = low_parts(sh, sig_low, inter, delta, len(d5), adjacent, FULL)
    require(parts is not None, "(F) fails on a realization")
    overlap, d5_part, codegree = cast(tuple[int, int, int], parts)
    lset = set(low)
    actual_o = sum(
        len(nbr[low[i]] & nbr[low[j]] & zset) for i, j in lpairs if (i, j) not in adjacent
    )
    actual_d = sum(1 for x in low for y in d5 if y not in nbr[x] and nbr[y] & zset <= nbr[x])
    actual_c = sum(
        1
        for a, b, c in combinations(ks, 3)
        if {(a, b), (a, c), (b, c)} <= m_pairs and len({a, b, c} & lset) >= 2
    )
    require(overlap == actual_o and d5_part <= actual_d and codegree <= actual_c, "(O)/(D)/(C)")
    require(actual_o + actual_d <= c_z and actual_c <= t_m, "penalty pieces overlap")
    m_heavy = sum(k - 1 - len(nbr[y] & kset) for y in heavy)
    require(m_heavy == sh.sixes * (k - 13) + sh.fives * (k - 12) + len(d5), "(F) H degree sum")
    bound = exact - zero - overlap - d5_part - codegree
    require(total <= bound, "state bound below realized T")
    return {
        "T": total,
        "STATE_BOUND": bound,
        "P": t_m + t_n + c_z + c_k,
        "T_M": t_m,
        "T_N": t_n,
        "C_Z": c_z,
        "C_K": c_k,
        "LOWER_Z": zero,
        "LOWER_O": overlap,
        "LOWER_D": d5_part,
        "LOWER_C": codegree,
        "SPLIT_CONSTANT": sh.constant,
    }


def validate_envelope(pid: str, cap: int, floor: int, terms: Sequence[Term]) -> None:
    """Check every position and exact rational term, including both endpoints."""
    require(pid in TARGETS and type(cap) is int and 22 <= cap <= 275, "wrong profile/cap")
    require(type(floor) is int and floor >= 0, "wrong S4 floor")
    require([t[0] for t in terms] == list(range(22, cap + 1)), "incomplete T envelope")
    d = tuple(map(int, pid))
    w, choose3, top = route.k4_premises(d)
    require(w == CLAIMS[pid].wedges, "evaluator wedge premise")
    a_max = sum(v * (6 + v - 2) for v in d) // 3
    for t, bound, k4, contained, s4, s3 in terms:
        require(all(type(v) is int for v in (t, bound, k4, contained, s4, s3)), "noninteger term")
        open_wedges = w - 3 * t
        excess = choose3 - (top - 2) * open_wedges
        expected_k4 = max(0, -(-excess // 4))
        require(k4 == expected_k4 and contained == min(k4, a_max), "K4 rounding/containment")
        require(s4 == max(floor, 679 * k4 - 231 * contained), "S4 direction/floor")
        # Independent expansion of Base R4's exact local S3 identity.
        expected_s3 = 2800 * open_wedges + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(route.K20_S1 - route.K20_S2 + expected_s3) - Fraction(4 * s4, 7)
        require(
            s3 == expected_s3 and bound == -(-exact.numerator // exact.denominator),
            "S3 or final ceiling rounding",
        )


def envelope(pid: str, cap: int, floor: int) -> list[Term]:
    terms = route.route_b_envelope(tuple(map(int, pid)), cap, floor)
    validate_envelope(pid, cap, floor, terms)
    return terms


def r2_fixed_input() -> dict[str, object]:
    """Re-execute R2 unmodified; it must reproduce its pinned stored result exactly."""
    identity(CERTIFICATE_HEAD, CERTIFICATE_TREE)
    parent = git("rev-parse", f"{CERTIFICATE_HEAD}^").decode().strip()
    require(parent == IMPLEMENTATION_HEAD, "certificate is not on the implementation base")
    require(
        (r2.IMPLEMENTATION_HEAD, r2.IMPLEMENTATION_TREE, r2.BASE_HEAD, r2.BASE_TREE)
        == (IMPLEMENTATION_HEAD, IMPLEMENTATION_TREE, BASE_HEAD, BASE_TREE),
        "R2 pins drift",
    )
    for path, digest in R2_PINS.items():
        require(
            (ROOT / path).read_bytes() == blob(CERTIFICATE_HEAD, path, digest),
            f"R2 changed: {path}",
        )
    fixed = r2.compute_result()
    require(render(fixed) == (ROOT / R2_RESULT).read_bytes(), "R2 result not reproduced")
    return fixed


def compute_result() -> dict[str, object]:
    identity(IMPLEMENTATION_HEAD, IMPLEMENTATION_TREE)
    identity(BASE_HEAD, BASE_TREE)
    fixed = r2_fixed_input()
    pins = r2.source_pins()
    sealed = decode(blob(BASE_HEAD, r2.BASE_RESULT, r2.BASE_SHA))
    before = {p: integer(b) for p, b in obj(fixed["RESOLVED_ROW_BOUNDS_AFTER"]).items()}
    r2.checked_rows(list(before.items()), before)
    require(sha(r2.projection(before)) == fixed["BOUNDS_SHA256_AFTER"], "R2 ledger digest")
    cursor = obj(fixed["CURSOR"])
    require(cursor == sealed["CURSOR"] and sha(render(cursor)) == sealed["CURSOR_SHA256"], "cursor")
    coarse = {p: integer(b) for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(
        len(coarse) == 197 and set(coarse) == set(cast(list[str], cursor["PROFILE_IDS"])),
        "cursor ID partition mismatch",
    )
    for pid, bound in coarse.items():
        require(
            route.r28.coarse_profile_envelope(tuple(map(int, pid))).family_upper_bound == bound,
            "cursor row bound differs from Base evaluator",
        )
    first = r2.family(before, coarse)
    require(first == fixed["PROJECTED_FAMILY_AFTER"], "R2 family not reproduced")
    require(
        first["MAXIMUM"] == BASELINE_FAMILY and first["ALL_MAX_OWNERS"] == sorted(TARGETS),
        "baseline family bound or owners not reproduced",
    )
    adopted_s5 = set(obj(sealed["PROFILE_CERTIFICATES"])) | {
        string(obj(sealed["INHERITED_TARGET_BONFERRONI_5"])["PROFILE_ID"])
    }
    adopted_caps = set(obj(sealed["CERTIFICATES_ADOPTED"]))
    require(not (set(TARGETS) & (adopted_s5 | adopted_caps)), "target has adopted authority")
    require(sealed["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED", "all-t S5 scope changed")
    r30 = decode(blob(BASE_HEAD, r2.R30_PATH, r2.R30_SHA))
    attempts = cast(list[dict[str, object]], r30["GROUP_ATTEMPTS"])
    after = dict(before)
    certificates: list[dict[str, object]] = []
    for pid in TARGETS:
        proof = theorem(pid)
        d = tuple(map(int, pid))
        references = [
            a for a in attempts if a.get("PROFILE_IDS") == [pid] and a.get("STATUS") == "INFEASIBLE"
        ]
        require(bool(references), "missing target cap authority")
        refutation = min(
            references, key=lambda a: integer(a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        )
        sealed_cap = integer(refutation["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
        require(
            route.r28.r26.accepted_cap(refutation, (d,), sealed_cap) == sealed_cap,
            "target refutation not accepted by Base",
        )
        nb_cap, class_cap = nb.profile_nb_cap(d)[2], nb.r18_cap(d)
        old_cap = min(sealed_cap, nb_cap, class_cap)
        s4 = route.r28.profile_s4_floor(d)  # Queried for this exact row, no copied constant.
        old = envelope(pid, old_cap, s4)
        old_bound = max(t[1] for t in old)
        require(before[pid] == old_bound, "target old envelope differs from fixed ledger row")
        relax = relaxation(pid)
        analytic = integer(relax["CAP"])
        new_cap = min(old_cap, analytic)
        new = envelope(pid, new_cap, s4)
        new_bound = max(t[1] for t in new)
        after[pid] = new_bound
        certificates.append(
            {
                "PROFILE_ID": pid,
                "THEOREM": proof,
                "RELAXATION": relax,
                "ABLATION_CAPS": ablation(pid),
                "ANALYTIC_CAP": analytic,
                "OLD_T_CAP": old_cap,
                "NEW_T_CAP": new_cap,
                "CAP_STATUS": "PROVEN_IMPROVEMENT" if new_cap < old_cap else "NO_PROVEN_GAIN",
                "OLD_CAP_AUTHORITY": {
                    "PATH": r2.R30_PATH,
                    "SHA256": r2.R30_SHA,
                    "REFUTATION": refutation,
                    "NB_CAP": nb_cap,
                    "CLASS_CAP": class_cap,
                },
                "S4_AUTHORITY": {
                    "BASE_HEAD": BASE_HEAD,
                    "FUNCTION": (
                        "b649_k20_min_s2_current_cursor_class_owner_chase_r28.profile_s4_floor"
                    ),
                    "EXACT_PROFILE": pid,
                    "INHERITED_FLOOR": s4,
                    "RULE": "MAX(INHERITED, ROUTE_B); LOWER_BOUND_SUBTRACTED",
                },
                "S5_AUTHORITY": {
                    "ADOPTED_S5_SCOPE_IN_BASE": sorted(adopted_s5),
                    "ADOPTED_CAP_CERTIFICATES_IN_BASE": sorted(adopted_caps),
                    "ALL_T_BONFERRONI_5_ADOPTION": sealed["ALL_T_BONFERRONI_5_ADOPTION"],
                    "VALUE": None,
                    "USED": False,
                    "STATUS": "NO_ADOPTED_TARGET_CERTIFICATE",
                },
                "OLD_T_RANGE": [22, old_cap],
                "NEW_T_RANGE": [22, new_cap],
                "OLD_TERM_COUNT": len(old),
                "NEW_TERM_COUNT": len(new),
                "OLD_ALL_T_TERMS": old,
                "NEW_ALL_T_TERMS": new,
                "OLD_BOUND": old_bound,
                "NEW_BOUND": new_bound,
                "ROW_DELTA": old_bound - new_bound,
                "OLD_ALL_ARGMAX": [t for t in old if t[1] == old_bound],
                "NEW_ALL_ARGMAX": [t for t in new if t[1] == new_bound],
            }
        )
    changed = sorted(p for p in before if before[p] != after[p])
    require(set(changed) <= set(TARGETS), "projection changed non-target row")
    r2.checked_rows(list(after.items()), {p: after[p] for p in before})
    others = {p: b for p, b in before.items() if p not in TARGETS}
    require(others == {p: b for p, b in after.items() if p not in TARGETS}, "other rows changed")
    last = r2.family(after, coarse)
    incumbent = integer(sealed["INCUMBENT"])
    improved = [c for c in certificates if c["CAP_STATUS"] == "PROVEN_IMPROVEMENT"]
    status = "PROVEN_IMPROVEMENT" if improved else "NO_PROVEN_GAIN"
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": f"{status}; PENDING_ONE_FRESH_FOCUSED_SCIENTIFIC_REVIEW",
        "IMPLEMENTATION_BASE": {"HEAD": IMPLEMENTATION_HEAD, "TREE": IMPLEMENTATION_TREE},
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": r2.BASE_RESULT,
            "RESULT_SHA256": r2.BASE_SHA,
        },
        "INPUT_CERTIFICATE": {
            "HEAD": CERTIFICATE_HEAD,
            "TREE": CERTIFICATE_TREE,
            "FILE_SHA256": R2_PINS,
            "REPRODUCED_BYTE_FOR_BYTE": True,
            "PACKET_REPORTED_VERDICT": "VERIFIED_WITH_CAVEATS",
            "USE": "FIXED_CONDITIONAL_INPUT; READ_ONLY; NOT_MODIFIED",
        },
        "SOURCE_PINS": pins,
        "PROOF": __doc__,
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4_FLOOR", "S3"],
        "ROUNDING": "K4_CEILING; A_MAX_FLOOR; FINAL_RATIONAL_CEILING = BASE - FLOOR(4*S4/7)",
        "CERTIFICATES": certificates,
        "ROW_CHANGES": {p: {"BEFORE": before[p], "AFTER": after[p]} for p in changed},
        "OTHER_ROWS_UNCHANGED": len(others),
        "RESOLVED_ROWS": len(after),
        "BOUNDS_SHA256_BEFORE": sha(r2.projection(before)),
        "BOUNDS_SHA256_AFTER": sha(r2.projection(after)),
        "RESOLVED_ROW_BOUNDS_AFTER": after,
        "PROJECTED_FAMILY_BEFORE": first,
        "PROJECTED_FAMILY_AFTER": last,
        "FAMILY_DELTA": integer(first["MAXIMUM"]) - integer(last["MAXIMUM"]),
        "ALL_NEW_MAX_OWNERS": last["ALL_MAX_OWNERS"],
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": integer(last["MAXIMUM"]) - incumbent,
        "CURSOR": cursor,
        "CURSOR_COUNT": len(coarse),
        "CURSOR_MAXIMUM": max(coarse.values()),
        "CURSOR_PRESERVED": "PASS — ALL_197_IDS_AND_BOUNDS_UNCHANGED_AND_REEVALUATED",
        "CURSOR_SHA256": sha(render(cursor)),
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "GRAPH_ENUMERATION_COMPLETENESS": "NOT_APPLICABLE — ANALYTIC_BOUND",
        "RELAXATION_STATE_SEARCH": (
            "EXACT_FINITE_MAXIMIZATION_OVER_NECESSARY_CONDITION_STATES; NOT_REALIZATIONS"
        ),
        "SOLVER_CALLS": 0,
        "REALIZATIONS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def verify_result(stored: Mapping[str, object]) -> None:
    require(
        render(stored) == render(compute_result()), "stored certificate not exactly reproducible"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce the two-profile triangle-cap certificate"
    )
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if RESULT.exists():
        require(RESULT.read_bytes() == raw, "stored certificate differs")
    else:
        require(not args.verify, "missing certificate")
        with RESULT.open("xb") as out:
            out.write(raw)
    print(
        json.dumps(
            {
                "RESULT": str(RESULT),
                "SHA256": sha(raw),
                "FAMILY_BEFORE": result["PROJECTED_FAMILY_BEFORE"],
                "FAMILY_AFTER": result["PROJECTED_FAMILY_AFTER"],
                "GAP": result["GAP_TO_INCUMBENT"],
            }
        )
    )


if __name__ == "__main__":
    main()
