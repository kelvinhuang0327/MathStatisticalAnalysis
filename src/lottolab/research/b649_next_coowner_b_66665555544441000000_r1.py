"""Full-profile certificate T<=246 for d=(6^4,5^5,4^4,1,0^6).

Scope and support premises. There are twenty tickets, each carrying six labels;
22 labels have triple supports and 27 have pair supports. Every pair of tickets
occurs in at most one support. Thus their shadow-plus-pair graph G is simple,
has 93 edges, and has degree g_v=6+d_v. No zero-degree ticket belongs to a triple.
These are the frozen min-S2 support premises, not assumptions about a special
construction. T denotes t(G), not the number (22) of triple supports.

Goodman, independently for THIS profile. H=complement(G) has 97 edges and
degrees 13-d. Inclusion-exclusion on three vertices gives
 T=C(20,3)-18*97+sum_v C(13-d_v,2)-t(H)=1140-1746+902-t(H)=296-t(H).
Alternatively t(G)+t(H)=C(20,3)-sum_v(6+d_v)(13-d_v)/2=1140-844=296.

Core/zero decomposition. K={d>0} has 14 vertices and Z has six. Set
 sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|,
 M=H[K], MZ=H[Z], h_x=deg_M(x)=7-d_x+sigma_x,
 b_u=deg_MZ(u)=zeta_u-1. Both cross-degree sums equal r.
Only pair labels can reach a zero, so 0<=sigma_x<=6-d_x. Since a zero
has six distinct neighbours but only five other zeros, 1<=zeta_u<=6.
Consequently |M|=16+r/2, |MZ|=(r-6)/2 and r is even.

For an edge xy of M, its H-neighbours in Z number
 6-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|.
The analogous count for an edge uw of MZ is
 14-zeta_u-zeta_w+|N_G(u) intersect N_G(w) intersect K|.
Each mixed triangle has exactly one same-part edge. Therefore EXACTLY
 t(H)=6|M|+14|MZ|-sum sigma_x*h_x-sum zeta_u*b_u+P,
 P=t(M)+t(MZ)+sum_{xy in M}|N_G(x) intersect N_G(y) intersect Z|
                   +sum_{uw in MZ}|N_G(u) intersect N_G(w) intersect K| >= 0.
Every summand is a cardinality; no discarded term has an unknown sign.

Let a=sum sigma over the five d=5 vertices, q_1,...,q_4 be the d=4
cross-degrees, Q=sum q_i, and p be the single d=1 cross-degree. The d=6
cross-degrees vanish, the d=5 ones are binary, and
 0<=a<=5, 0<=q_i<=2, 0<=p<=5, r=a+Q+p=sum zeta, r even.
Now sum sigma*h=3r+sum q_i^2+3p+p^2, so the exact identities are
 t(H)=54+8r-3p-p^2-sum q_i^2-sum zeta_u^2+P,
 T=F-P, F=242-8r+3p+p^2+sum q_i^2+sum zeta_u^2.

Load-bearing inequality (analytic). Put
 D=a+(8-Q)+7(5-p)+p(5-p)+sum q_i(2-q_i)
                              +sum (zeta_u-1)(6-zeta_u).
Using the equal cross sums, expansion gives F=249-D. Every displayed
term of D is a nonnegative integer, already proving T<=249. If D<=2,
then p=5; any interior zeta has (zeta-1)(6-zeta)>=4, so every zeta is
1 or 6. Also a+(8-Q)<=2, whence 11<=r=a+Q+5<=15. But six entries in
{1,6} have sum 6+5j, and an even such sum is in {6,16,26,36}. This is
impossible. Thus D>=3 and T=249-D-P<=246 for EVERY legal realization.
Attainment by supports is not asserted.

Finite necessary-condition crosscheck, not a sample. Enumerate a=0..5,
the sorted four q entries from 0..2, p=0..5, and the sorted six zeta
entries from 1..6, retaining equal sums and even r. Each legal support
maps to one of these states: permute only equal-degree core vertices
and zeros. a encodes every binary d=5 multiset. The objective and D are
invariant under those permutations. No graphicality or simultaneous
realizability filter is imposed. Hence all 1,453 states are a complete
SUPERSET of legal realizations, and their maximum F=246 is an independent
finite check of the inequality. The maximizing abstract state need not
be realizable. Widened-premise countermodels are abstract, not supports.

Route B. For every integer 22<=t<=cap, W=830, U=sum C(g,3)=2340,
g_max=12 and A_max=floor(sum d(g-2)/3)=floor(598/3)=199. Count
 K4>=max(0,ceil((U-(g_max-2)(W-3t))/4))=:L,
 C=min(L,A_max), S4>=max(112,448*C+679*(L-C)),
 S3=2800*W+11872*(t-22)-30800.
The 22 distinct support triples are G-triangles, proving the lower endpoint.
For the K4 inequality, let o_v be the number of missing edges in G[N(v)].
At most (g_v-2)o_v neighbour triples fail to be triangles (union bound).
Thus 4*K4=sum_v t(G[N(v)])>=U-sum_v(g_v-2)o_v
>=U-(g_max-2)(W-3t), since sum o_v=W-3t. Apply the integer ceiling.
For the contained allowance, a common outside neighbour of a support triple
uses three incidences among its vertices' sum(g_v-2) outside neighbours.
Summing over the support triples gives at most floor(sum d_v(g_v-2)/3).
Pair linearity prevents two support triples from belonging to one quartet.
The fourth-order weights 448 and 679, the base 112 and the S3 expression
are the frozen Route-B primitives. The weighted floor is increasing in K4,
so it is valid to substitute L; overlapping S4 floors are combined by MAX.
The contained allowance C is used to minimize the fourth-order floor;
it is not a lower bound on the actual number of contained quartets.
Frozen Bonferroni gives S1-S2+S3-4*S4/7, with S1=372228640 and
S2=63838600. The admissible INTEGER bound is its ceiling, equivalently
S1-S2+S3-floor(4*S4/7). All terms are checked with Fractions and against
the frozen Route-B implementation. Take the maximum over the entire
domain, rather than assuming its final term is the maximum.

Authority. Verify the requested frozen commit/tree/result digest and
read-only replay its ledger; extract only this profile. Later frozen
row updates are copied as recorded metadata, without new research on
other profiles. No family integration, solver, sampling proof, remote
write, or production mutation is performed. SELF_CHECK_ONLY.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from math import comb
from pathlib import Path
from typing import cast

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as frozen

TASK_ID = "B649_NEXT_COOWNER_B_66665555544441000000_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
PROFILE_ID = "66665555544441000000"
DEGREES = tuple(map(int, PROFILE_ID))
CORE = DEGREES[:14]
GOODMAN = 296
PROVED_CAP = 246
S4_BASE = 112
OLD_BOUND = 313_392_412
RESULT_STEM = "b649-next-coowner-b-66665555544441000000-r1"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = ROOT / "docs/research/matrix-native-results" / f"{RESULT_STEM}-result.json"
FROZEN_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
)
Term = tuple[int, int, int, int, int, int]
Edge = tuple[int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def profile_facts(profile: Sequence[int] = DEGREES) -> dict[str, object]:
    require(tuple(profile) == DEGREES, "wrong profile: theorem is profile-specific")
    g, h = [6 + d for d in profile], [13 - d for d in profile]
    phi = comb(20, 3) - 18 * (sum(h) // 2) + sum(comb(v, 2) for v in h)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    require(phi == goodman == GOODMAN, "Goodman constant mismatch")
    require(Counter(profile) == {6: 4, 5: 5, 4: 4, 1: 1, 0: 6}, "degree classes")
    require((sum(profile), sum(d * d for d in profile)) == (66, 334), "degree moments")
    require(sum(g) == 186 and sum(h) == 194, "graph edge counts")
    return {
        "PROFILE_ID": PROFILE_ID,
        "DEGREE_DISTRIBUTION": "6^4,5^5,4^4,1^1,0^6",
        "DEGREE_SUM": sum(profile),
        "DEGREE_SQUARE_SUM": sum(d * d for d in profile),
        "CORE_COUNT": 14,
        "ZERO_COUNT": 6,
        "GOODMAN_CONSTANT": phi,
        "GOODMAN_RATIONAL_CROSSCHECK": str(goodman),
        "H_WEDGES": sum(comb(v, 2) for v in h),
        "G_EDGES": sum(g) // 2,
        "H_EDGES": sum(h) // 2,
    }


@dataclass(frozen=True, order=True)
class State:
    a: int
    q: tuple[int, ...]
    p: int
    zeta: tuple[int, ...]

    @property
    def r(self) -> int:
        return self.a + sum(self.q) + self.p

    @property
    def sigma(self) -> tuple[int, ...]:
        return (0,) * 4 + (0,) * (5 - self.a) + (1,) * self.a + self.q + (self.p,)


def premise_failures(s: State) -> list[str]:
    failures: list[str] = []
    if not 0 <= s.a <= 5:
        failures.append("DEGREE_5_BINARY_CAPACITY")
    if len(s.q) != 4 or any(not 0 <= q <= 2 for q in s.q):
        failures.append("DEGREE_4_PAIR_CAPACITY")
    if not 0 <= s.p <= 5:
        failures.append("DEGREE_1_PAIR_CAPACITY")
    if len(s.zeta) != 6 or any(not 1 <= z <= 6 for z in s.zeta):
        failures.append("ZERO_DISTINCT_NEIGHBOUR_CAPACITY")
    if s.r != sum(s.zeta):
        failures.append("EQUAL_CROSS_EDGE_SUMS")
    if s.r % 2:
        failures.append("INTERNAL_EDGE_PARITY")
    return failures


def objective(s: State) -> int:
    return 242 - 8 * s.r + 3 * s.p + s.p**2 + sum(q * q for q in s.q) + sum(z * z for z in s.zeta)


def deficit(s: State) -> int:
    return (
        s.a
        + 8
        - sum(s.q)
        + 7 * (5 - s.p)
        + s.p * (5 - s.p)
        + sum(q * (2 - q) for q in s.q)
        + sum((z - 1) * (6 - z) for z in s.zeta)
    )


def generic_split_objective(s: State) -> Fraction:
    h = [7 - d + v for d, v in zip(CORE, s.sigma, strict=True)]
    b = [v - 1 for v in s.zeta]
    return (
        Fraction(GOODMAN)
        - 3 * sum(h)
        - 7 * sum(b)
        + sum(v * w for v, w in zip(s.sigma, h, strict=True))
        + sum(v * w for v, w in zip(s.zeta, b, strict=True))
    )


def configurations(
    *,
    q_max: int = 2,
    p_max: int = 5,
    z_min: int = 1,
    z_max: int = 6,
    even: bool = True,
) -> Iterator[State]:
    """Complete class-multiset Cartesian product; optional widening is for negatives."""
    by_sum: dict[int, list[tuple[int, ...]]] = {}
    for z in combinations_with_replacement(range(z_min, z_max + 1), 6):
        by_sum.setdefault(sum(z), []).append(z)
    for a in range(6):
        for q in combinations_with_replacement(range(q_max + 1), 4):
            for p in range(p_max + 1):
                r = a + sum(q) + p
                if even and r % 2:
                    continue
                for z in by_sum.get(r, []):
                    yield State(a, q, p, z)


def certify_state(s: State) -> None:
    require(not premise_failures(s), ",".join(premise_failures(s)))
    require(generic_split_objective(s) == objective(s) == 249 - deficit(s), "identity")
    # This is the analytic contradiction in the docstring, checked from its premises.
    if deficit(s) <= 2:
        require(s.p == 5 and set(s.zeta) <= {1, 6}, "small-deficit implication")
        require(11 <= s.r <= 15, "small-deficit cross-sum interval")
        require(s.r in {6, 16, 26, 36}, "endpoint sums and parity")
        raise AssertionError("contradictory small-deficit state")
    require(objective(s) <= PROVED_CAP, "cap exceeds analytic certificate")


def theorem() -> dict[str, object]:
    table: list[list[object]] = []
    states = list(configurations())
    for s in states:
        certify_state(s)
        table.append([*asdict(s).values(), objective(s), deficit(s)])
    peak = max(objective(s) for s in states)
    require(len(states) == 1453 and peak == PROVED_CAP, "complete relaxation changed")
    return {
        "EXACT_TRIANGLE_IDENTITY": "T=296-t(H)=242-8r+3p+p^2+sum(q_i^2)+sum(zeta_u^2)-P",
        "CORE_ZERO_DECOMPOSITION": "h_x=7-d_x+sigma_x; b_u=zeta_u-1; |M|=16+r/2; |MZ|=(r-6)/2",
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K; four cardinality sums",
        "SUPPORT_PREMISES": [
            "20 tickets, six labels each, 22 triple supports, 27 pair supports",
            "each ticket pair occurs in at most one support; G simple, deg_G=6+d",
            "zeros are in no triple; sigma_x<=6-d_x",
            "zero has six distinct neighbours and at most five zero neighbours",
            "a in 0..5, four q_i in 0..2, p in 0..5, six zeta_u in 1..6",
            "r=a+sum(q)+p=sum(zeta); r even by the internal edge handshake",
        ],
        "LOAD_BEARING_INEQUALITY": "D>=3 and P>=0; T=249-D-P<=246",
        "ANALYTIC_PROOF": (
            "D<=2 forces p=5, zeta in {1,6}, 11<=r<=15, and r in {6,16,26,36}; contradiction"
        ),
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROVED_T_CAP": PROVED_CAP,
        "RELAXATION_SUPERSET_COMPLETENESS": (
            "All legal supports map to enumerated multisets; "
            "only necessary ranges, equal sums and parity; no graphicality filters"
        ),
        "RELAXATION_STATE_COUNT": len(states),
        "RELAXATION_TABLE_SHA256": digest(render(table)),
        "RELAXATION_MAX_F": peak,
        "RELAXATION_ARGMAX": [asdict(s) for s in states if objective(s) == peak],
        "COUNTEREXAMPLE_STATUS": "NONE_ABOVE_246_IN_COMPLETE_NECESSARY_CONDITION_SUPERSET",
        "UNPROVED_ASSUMPTIONS": [],
        "ATTAINMENT": "NOT_ASSERTED",
        "PROOF": __doc__,
    }


def graph_decomposition(n: int, k: int, edges: set[Edge]) -> dict[str, object]:
    """Generic cardinality identity; small-graph tests do not replace the proof."""
    require(0 <= k <= n and edges <= set(combinations(range(n), 2)), "graph domain")
    core, zeros = set(range(k)), set(range(k, n))
    h = set(combinations(range(n), 2)) - edges
    ng = [{w for e in edges if v in e for w in e if w != v} for v in range(n)]
    m = {e for e in h if set(e) <= core}
    mz = {e for e in h if set(e) <= zeros}

    def triangles(vertices: set[int], graph: set[Edge]) -> int:
        return sum(
            all(e in graph for e in combinations(t, 2)) for t in combinations(sorted(vertices), 3)
        )

    sigma = [len(ng[x] & zeros) for x in range(k)]
    zeta = [len(ng[u] & core) for u in range(k, n)]
    hm = [sum(x in e for e in m) for x in range(k)]
    bm = [sum(u in e for e in mz) for u in range(k, n)]
    parts = [
        triangles(core, m),
        triangles(zeros, mz),
        sum(len(ng[x] & ng[y] & zeros) for x, y in m),
        sum(len(ng[u] & ng[v] & core) for u, v in mz),
    ]
    tg, th = triangles(core | zeros, edges), triangles(core | zeros, h)
    split = (
        (n - k) * len(m)
        + k * len(mz)
        - sum(x * y for x, y in zip(sigma, hm, strict=True))
        - sum(x * y for x, y in zip(zeta, bm, strict=True))
        + sum(parts)
    )
    require(th == split and min(parts) >= 0, "nonnegative remainder identity")
    require(
        2 * (tg + th) == 2 * comb(n, 3) - sum(len(nb) * (n - 1 - len(nb)) for nb in ng),
        "generic Goodman identity",
    )
    return {"T_G": tg, "T_H": th, "P_PARTS": parts, "P": sum(parts)}


def route_b(cap: int) -> list[Term]:
    require(22 <= cap <= 264, "Route-B domain")
    g = [6 + d for d in DEGREES]
    w, u, top = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g), max(g)
    a = sum(d * (v - 2) for d, v in zip(DEGREES, g, strict=True)) // 3
    require((w, u, top, a) == (830, 2340, 12, 199), "Route-B premises")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        excess = u - (top - 2) * (w - 3 * t)
        k4 = max(0, -(-excess // 4))
        contained = min(k4, a)
        s4 = max(S4_BASE, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372_228_640 - 63_838_600 + s3 - (4 * s4) // 7
        # Independent rational ceilings and split form, including negative excess.
        k4_rational = max(0, -((-Fraction(excess, 4).numerator) // Fraction(excess, 4).denominator))
        floor_rational = max(S4_BASE, 679 * k4_rational - 231 * min(k4_rational, a))
        exact = Fraction(372_228_640 - 63_838_600 + s3) - Fraction(4 * floor_rational, 7)
        require(k4 == k4_rational and s4 == floor_rational, "K4/S4 rational crosscheck")
        require(bound == -((-exact.numerator) // exact.denominator), "exact ceiling")
        require(0 <= bound - exact < 1, "rounding interval")
        terms.append((t, bound, k4, contained, s4, s3))
    require(
        terms == frozen.r32.route_b_envelope(DEGREES, cap, S4_BASE), "frozen Route-B crosscheck"
    )
    return terms


def authority() -> dict[str, object]:
    require(
        git("rev-parse", f"{FROZEN_HEAD}^{{tree}}").decode().strip() == FROZEN_TREE, "frozen tree"
    )
    raw = git("show", f"{FROZEN_HEAD}:{FROZEN_RESULT_PATH}")
    require(digest(raw) == FROZEN_RESULT_SHA256, "frozen result digest")
    require((ROOT / FROZEN_RESULT_PATH).read_bytes() == raw, "local frozen result changed")
    path = Path(frozen.__file__).resolve()
    require(path.is_relative_to(ROOT), "frozen module outside worktree")
    relative = path.relative_to(ROOT).as_posix()
    require(path.read_bytes() == git("show", f"{FROZEN_HEAD}:{relative}"), "frozen module changed")
    sealed = cast(dict[str, object], json.loads(raw))
    _six_result, ledger = frozen.six_row_authority()
    # Reconstruct only the recorded metadata delta of the frozen seventh row.
    update = frozen.object_row(sealed["ROW_UPDATE"])
    pid = frozen.text(update["PROFILE_ID"])
    require(pid != PROFILE_ID, "frozen update unexpectedly touches target")
    require(json.loads(json.dumps(asdict(ledger[pid]))) == update["BEFORE"], "frozen before row")
    after = frozen.object_row(update["AFTER"])
    ledger[pid] = replace(
        ledger[pid],
        bound=frozen.integer(after["bound"]),
        cap=frozen.integer(after["cap"]),
        source=frozen.text(after["source"]),
    )
    # JSON normalizes tuple-valued realizations; compare canonical JSON for that row.
    require(json.loads(json.dumps(asdict(ledger[pid]))) == after, "frozen after row")
    require(
        frozen.two.full_digest(ledger) == sealed["FULL_ROWS_SHA256_AFTER"], "frozen ledger digest"
    )
    row = ledger[PROFILE_ID]
    require((row.cap, row.s4_base, row.bound) == (264, 112, OLD_BOUND), "source row mismatch")
    locator = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[912]"
    require(row.source == locator, "source locator mismatch")
    # Re-derive this profile's existing NB authority without searching another profile.
    g = [6 + d for d in DEGREES]
    nb_open = sum(
        comb(v, 2)
        - sum(min(v - 1, u - 1) for u in sorted(g[:i] + g[i + 1 :], reverse=True)[:v]) // 2
        for i, v in enumerate(g)
    )
    require(nb_open == 38 and (830 - nb_open) // 3 == row.cap, "old NB cap authority")
    return {
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": "MATCH",
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_RESULT_DIGEST": digest(raw),
        "FROZEN_RESULT_LOCATOR": FROZEN_RESULT_PATH,
        "FROZEN_LEDGER_SHA256": sealed["FULL_ROWS_SHA256_AFTER"],
        "FROZEN_LEDGER_ROWS": len(ledger),
        "SOURCE_T_CAP": row.cap,
        "SOURCE_S4_BASE": row.s4_base,
        "SOURCE_ROW_BOUND": row.bound,
        "SOURCE_LOCATOR": locator,
        "SOURCE_ROW": asdict(row),
        "SOURCE_CAP_AUTHORITY": "NB neighbourhood capacity: OW>=38, T<=floor((830-38)/3)=264",
        "RECORDED_SUPPORT_REALIZATION": "NONE_IN_SOURCE_ROW; not required for universal theorem",
        "FROZEN_MODULE_SHA256": digest(path.read_bytes()),
    }


def negative_cases() -> list[dict[str, object]]:
    cases = [
        ("DEGREE_4_PAIR_CAPACITY", State(0, (2, 3, 3, 3), 5, (1, 1, 1, 1, 6, 6))),
        ("DEGREE_1_PAIR_CAPACITY", State(2, (2, 2, 2, 2), 6, (1, 1, 1, 1, 6, 6))),
        ("ZERO_DISTINCT_NEIGHBOUR_CAPACITY", State(0, (0, 0, 0, 1), 5, (0, 0, 0, 0, 0, 6))),
        ("ZERO_DISTINCT_NEIGHBOUR_CAPACITY", State(5, (2, 2, 2, 2), 5, (1, 1, 1, 1, 7, 7))),
        ("INTERNAL_EDGE_PARITY", State(0, (0, 2, 2, 2), 5, (1, 1, 1, 1, 1, 6))),
    ]
    out: list[dict[str, object]] = []
    for premise, s in cases:
        failures = premise_failures(s)
        require(failures == [premise] and objective(s) > PROVED_CAP, "negative is not focused")
        out.append(
            {"REMOVED_PREMISE": premise, "STATE": asdict(s), "F": objective(s), "REJECTED": True}
        )
    return out


def compute_result() -> dict[str, object]:
    facts, proof = profile_facts(), theorem()
    old_terms, new_terms = route_b(264), route_b(PROVED_CAP)
    require(new_terms == old_terms[: len(new_terms)], "Route-B prefix")
    peak = max(new_terms, key=lambda t: (t[1], t[0]))
    require(max(t[1] for t in old_terms) == OLD_BOUND, "old Route-B bound")
    cap263 = max(t[1] for t in old_terms if t[0] <= 263)
    require(cap263 == 313_383_256, "requested cap-263 threshold")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        **authority(),
        **facts,
        **proof,
        "TARGET_T_CAP": 263,
        "OLD_BOUND": OLD_BOUND,
        "EXPECTED_BOUND_AT_CAP_263": cap263,
        "NEW_ADMISSIBLE_BOUND": peak[1],
        "OWNER_BOUND_DELTA": OLD_BOUND - peak[1],
        "NEXT_COMPETITOR": 313_392_308,
        "BELOW_NEXT_COMPETITOR": peak[1] < 313_392_308,
        "W": 830,
        "U": 2340,
        "A_MAX": 199,
        "A_MAX_EXACT": "floor(598/3)",
        "ROUTE_B_INTEGER_RECOUNT": "PASS_ALL_TERMS_22_TO_264",
        "EXACT_RATIONAL_CROSSCHECK": "PASS_ALL_TERMS",
        "ROUNDING_CHECK": "CEILING_OF_RATIONAL_EQUALS_INTEGER_MINUS_FLOOR_CREDIT",
        "ARGMAX_TERM": peak,
        "ARGMAX_TERM_COLUMNS": ["T", "BOUND", "K4_LOWER", "CONTAINED_ALLOWANCE", "S4_LOWER", "S3"],
        "ROUTE_B": {
            "ALL_T_TERMS": new_terms,
            "TERM_COUNT": len(new_terms),
            "S1": 372_228_640,
            "S2": 63_838_600,
            "S4_BASE": S4_BASE,
            "BONFERRONI_CORRECTION": "-4*S4/7",
            "PREFIX_OF_FROZEN_CAP_264": True,
        },
        "NEGATIVE_CASE_RESULTS": negative_cases(),
        "CPU_PROCESS_COUNT_MAX": 1,
        "CPU_SECONDS_LIMIT_PER_PROCESS": 120,
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "FROZEN_LEDGER_MUTATED": "NO",
    }


def main() -> None:
    payload = render(compute_result())
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    result = json.loads(payload)
    print(
        json.dumps(
            {k: result[k] for k in ("PROVED_T_CAP", "NEW_ADMISSIBLE_BOUND", "OWNER_BOUND_DELTA")}
        )
    )
    print(f"RESULT_SHA256: {digest(payload)}")


if __name__ == "__main__":
    main()
