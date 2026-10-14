"""Independent T245 and cursor-cohort certificates with exact family replay.

Frozen model: 20 tickets of six distinct labels, 22 triple labels and 27 pair
labels, with pair-linearity. Thus G is simple, E=93, d sums to 66 and g=6+d.
For any simple graph, each mixed three-set contributes twice to
sum g(19-g); homogeneous three-sets contribute zero. Hence
T(G)+T(complement G)=C(20,3)-sum g(19-g)/2.

T245: d=(6,6,5^9,4,3,1,1,0^5), K={d>0}, Z={d=0}; k=15,z=5.
L=(4,3,1,1); H5 has nine vertices and H6 two. Let sigma_x=|N_G(x)&Z|
and zeta_u=|N_G(u)&K|, r=sum sigma=sum zeta. Cross edges at a zero
vertex use pair labels; therefore sigma<=6-d, H6 sigma=0, H5 sigma<=1,
and 2<=zeta<=6. For M=complement G[K], N=complement G[Z],
m=8-d+sigma, n=zeta-2, 2e(M)=54+r, 2e(N)=r-10.
Counting complement triangles by the number of Z vertices gives exactly
T(G)=231-10r+sum sigma(8-d+sigma)+sum zeta(zeta-2)-P,
P=T(M)+T(N)+sum_M c_Z+sum_N c_K. Every part counts a finite set and is
nonnegative. The constant follows from Goodman 291 and
z*e(M)+k*e(N)=60+10r.

For a state, b_u is the four-bit L-neighbour set of u in Z and tau_u counts
H5 vertices whose single Z neighbour is u; zeta=popcount(b)+tau. Exhaust
all five-column b multisets within sigma caps (2,3,5,5), all tau within
max(0,2-popcount(b))..6-popcount(b), sum tau<=9. Permuting Z preserves
all bounds, so b is ascending and tau is descending inside equal-b blocks.
No symmetry of the two d=1 L vertices is assumed. Every legal realization
has a representative; singleton H5 cross rows can be assigned distinctly
because sum tau<=9. Thus the bipartite cross degrees are constructible for
every enumerated state, without claiming the full support system exists.

Exhaust every labelled G[Z] (1024 graphs) with degrees 6-zeta. For each,
Zpen=T(N)+sum_N popcount(b_u & b_v), exactly the corresponding P parts.
Exhaust all 64 labelled G[L] patterns. If a_x is its degree, q_x=6+d-sigma,
m_x=8-d+sigma, require a_x<=q_x and sum_L m-2e(M[L])<=31+sum tau.
These follow from G-degree availability and e_M(L,H)<=sum_H m=31+sum tau.
O=sum over M[L] pairs popcount(b_u & b_v) counts L-L overlap.
D=sum_x max(0,delta_x-(q_x-a_x)), delta_x=sum_{u:x in b_u} tau_u,
counts forced nonadjacent L-H5 overlap, disjoint from O.
Also require M to be graphical by every Erdos-Gallai prefix inequality.
Necessity follows by counting edges incident to the j largest-degree vertices:
their internal edges contribute at most j(j-1), and every outside vertex
contributes at most min(its degree,j). No sufficiency is needed for this filter.
For e_x=m_x-deg_M[L](x), the L-H bipartite cut requires e_x>=0 and
sum of its largest j rows <= sum_H min(m_y,j), j=1..4. This is necessary
by counting edges into each H column, whose capacity is m_y. For j<=3
the right side is 11j (j=1,2) or 31 (j=3); for j=4 it is 31+sum tau.
No sufficiency for the full support realization is inferred.
C=max(T(M[L]),sum_{xy in M[L]} max(0,m_x+m_y-15)-2T(M[L]))
is a lower bound on T(M): edge common neighbours are at least m_x+m_y-15;
the sum counts triangles with exactly two L vertices once, and all-L
triangles three times. Subtracting twice the latter corrects overcounting.
Refine C by counting triangle classes separately. Let e_x=m_x-deg_M[L](x),
h=11, eHH=(31+sum tau-sum e_x)/2. Triangles with at least two L vertices
are at least T(M[L])+sum_M[L] max(0,e_x+e_y-h); use the maximum of this and
the preceding C bound. For each x, at most (h-e_x)*mHmax of the eHH edges
have an endpoint outside its H neighbourhood, with mHmax=3 if sum tau=0,
otherwise 4. Thus triangles with exactly one L vertex are at least
sum_x max(0,eHH-(h-e_x)*mHmax). These classes are disjoint, so their bounds
add. This refinement is necessary at the formerly loose 249 state.
Zpen+O+D+the refined C therefore bounds disjoint parts of P. Minimizing the two
penalties independently only enlarges the domain. All 2196583 states are
visited, with no branch-and-bound omission. Its maximum is 245. This is a
necessary-condition maximum, never a legal support construction.
An independent generating-function recurrence recounts every multiset's
tau states, using bounded partitions inside each equal-b block.

Route B: O=W-3T and J=sum C(g,3). Non-triangular neighbour triples contain
an open wedge; each wedge extends within that neighbourhood in at most
gmax-2 ways. Consequently J<=(gmax-2)O+4K4. The K4 floor is the nonnegative
ceiling of (J-(gmax-2)O)/4. A K4 contains at most one triple label by
pair-linearity, with weight 448; others weigh 679. Contained K4 count is at
most floor(sum d(g-2)/3). Use max(112,679K4-231min(K4,Amax)), never a sum
of floors. All T in 22..266 and 22..245 are evaluated by exact Fraction and
integer ceilings; the frozen validated evaluator independently agrees.

Cohort: two enumerations of sorted twenty-digit degrees with sum 66 and
square sum 244 give exactly the sealed cursor's 41 IDs. They have W=785,
sum g=186, sum g^2=1756, so Goodman gives 251 universally, regardless of
attainment. T<=251 implies open wedges>=32. S3=2800W+11872(T-22)-30800
increases with T. The inherited S4>=112 gives credit floor(448/7)=64.
The resulting bound is 313275864. Only the exact identified cohort changes.

Multiplicity premise: for any seven-label outcome, choose three hit labels
from each winning ticket. Pair-linearity makes their three pairs disjoint,
so at most C(7,2)/C(3,2)=7 tickets win. For r=0..7 the order-three
Bonferroni excess r-C(r,2)+C(r,3)-1[r>0] is at least (4/7)C(r,4).
Summing and rounding up yields UB=ceil(S1-S2+S3-4S4/7). No S5 is used.

The whole 4647-row ledger and 197-profile cursor are scanned in four
scenarios. Historical acceptance, pending/conditional/self-check caveats and
historical R15 NOT_VERIFIED remain separate from this new certificate.
Legal attainment and the global K20 optimum remain UNKNOWN.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route
from . import b649_min_s2_owner_ab_exact_family_composition_r1 as common

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_T245_CURSOR41_JOINT_FORMAL_AUTHORITY_R1"
OWNER_CONVERSATION_ID = "01a13943-493d-7503-81fb-1ea22b0c4129"
SOURCE = "src/lottolab/research/b649_min_s2_t245_cursor41_joint_formal_authority_r1.py"
TEST = "tests/unit/test_b649_min_s2_t245_cursor41_joint_formal_authority_r1.py"
RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-t245-cursor41-joint-formal-authority-r1-result.json"
)
BASE_HEAD = "ea62dc28a0334b4d79a10279a1f9d7ae47f26679"
BASE_TREE = "98449e22498d6564c1f471c1b0ab7ee76ee3b70b"
BASE_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-t248-t228-exact-family-composition-r1-result.json"
)
BASE_SHA = "7fb94231b2898a8a0f2d99187d9f15e37656abcad5bccd6a01693cf5f33f6469"
PRIOR_HEAD = "e744534a3475d77aa192bf67733ade00b11c2ea3"
PRIOR_SOURCE = "src/lottolab/research/b649_next_two_max_profiles_exact_bound_r1.py"
PRIOR_SHA = "9ca78ac773221a7747f62015c1b7db9d0726cc9949635f72a42076ded71f694d"
R8_HEAD = "5ac18ded3f2bc61449baa4d5e00ac0c1c8b247d1"
R8_SOURCE = "src/lottolab/research/b649_k20_min_s2_next_active_profile_exact_bound_r8.py"
R8_SHA = "8b70fbfa9f3cc3cabe0c48956d92b7f81600c474b4331717695de303855d382a"
COHORT_SHA = "cb2bc3dbc8ae8392a33ee7d9b609aa737485b6bf8a149f69a853da83730e8be6"
TARGET = "66555555555431100000"
LOW = (4, 3, 1, 1)
PAIRS = tuple(combinations(range(4), 2))
ZPAIRS = tuple(combinations(range(5), 2))
MODEL: dict[str, object] = {
    "tickets": 20,
    "labels_per_ticket": 6,
    "labels": 49,
    "triples": 22,
    "pairs": 27,
    "support_sizes": [2, 3],
    "pair_linearity": True,
}
type Document = dict[str, object]
type Term = tuple[int, int, int, int, int, int]
type State = tuple[tuple[int, ...], tuple[int, ...]]
require, obj, integer, render, decode = (
    common.require,
    common.obj,
    common.integer,
    common.render,
    common.decode,
)
sha = common.sha


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def immutable(head: str, path: str, digest: str) -> bytes:
    require(bool(re.fullmatch("[0-9a-f]{40}", head)), "wrong source commit")
    require(git("cat-file", "-t", head).strip() == b"commit", "wrong source type")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "missing or unsafe source",
    )
    raw = git("cat-file", "blob", head + ":" + path)
    require(sha(raw) == digest, "source SHA256 mismatch")
    return raw


def load_base() -> Document:
    require(
        git("rev-parse", BASE_HEAD + "^{tree}").decode().strip() == BASE_TREE, "wrong Base tree"
    )
    raw = immutable(BASE_HEAD, BASE_RESULT, BASE_SHA)
    require((ROOT / BASE_RESULT).read_bytes() == raw, "local Base drift")
    base = decode(raw)
    require(render(base) == raw, "noncanonical Base")
    return base


def source_authority() -> Document:
    immutable(PRIOR_HEAD, PRIOR_SOURCE, PRIOR_SHA)
    immutable(R8_HEAD, R8_SOURCE, R8_SHA)
    # Bind the entire internal import closure actually used, without executing donors.
    pending = [route.__name__, common.__name__]
    pins: dict[str, str] = {}
    while pending:
        module = pending.pop()
        path = module.replace(".", "/") + ".py"
        relative = "src/" + path
        if relative in pins:
            continue
        raw = git("cat-file", "blob", BASE_HEAD + ":" + relative)
        require((ROOT / relative).read_bytes() == raw, "frozen evaluator drift")
        pins[relative] = sha(raw)
        tree = ast.parse(raw)
        package = module.rsplit(".", 1)[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    parts = package.split(".")
                    prefix = ".".join(parts[: len(parts) + 1 - node.level]) + (
                        "." + prefix if prefix else ""
                    )
                if prefix.startswith("lottolab"):
                    if node.module:
                        pending.append(prefix)
                    else:
                        pending.extend(prefix + "." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name.startswith("lottolab"))
    message = git("cat-file", "commit", BASE_HEAD).split(b"\n\n", 1)[1].decode()
    report = (
        message.split("FRESH_JUDGE_REPORT_VERBATIM_BEGIN\n", 1)[1].split(
            "\nFRESH_JUDGE_REPORT_VERBATIM_END", 1
        )[0]
        + "\n"
    )
    declared = re.findall(r"(?m)^Judge-report-SHA256: ([0-9a-f]{64})$", message)
    require(
        declared == [sha(report.encode())]
        and "Fresh-context Judge: VERIFIED_WITH_CAVEATS" in message
        and BASE_TREE in report
        and BASE_SHA in report,
        "Base Judge binding",
    )
    require(not any(n.startswith("ortools") for n in sys.modules), "solver loaded")
    return {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "BASE_FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
        "BASE_REPORT_SHA256": declared[0],
        "BASE_COMMIT_MESSAGE_SHA256": sha(message.encode()),
        "BASE_CAVEATS": "Immutable Base result and accepted commit preserved verbatim by reference",
        "R8_HEAD": R8_HEAD,
        "R8_SOURCE_SHA256": R8_SHA,
        "T245_PRIOR_ART_HEAD": PRIOR_HEAD,
        "T245_SOURCE_SHA256": PRIOR_SHA,
        "HISTORICAL_T245_REVIEW": {
            "KIND": "READ_ONLY_INDEPENDENT_MATHEMATICAL_PROOF",
            "R01_R17": "PASS",
            "R15": "NOT_VERIFIED",
            "EVIDENCE_CLASS": "OWNER_PACKET_HISTORICAL_RECORD",
        },
        "HISTORICAL_COHORT_REVIEW": {
            "KIND": "READ_ONLY_MATHEMATICAL_PROOF",
            "R01_R14": "PASS",
            "R15": "NOT_VERIFIED",
            "EVIDENCE_CLASS": "OWNER_PACKET_HISTORICAL_RECORD",
        },
        "PRIOR_ART_SCIENTIFIC_STATUS": "PENDING/CONDITIONAL; unchanged immutable source",
        "HISTORICAL_R15": "NOT_VERIFIED",
        "SOURCE_PINS": dict(sorted(pins.items())),
    }


def facts(pid: str, model: Mapping[str, object] = MODEL) -> Document:
    require(dict(model) == MODEL, "wrong frozen model")
    d = common.profile(pid)
    g = tuple(6 + x for x in d)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * (19 - x) for x in g), 2)
    require(sum(g) == 186 and goodman.denominator == 1, "degree identity")
    return {
        "D": list(d),
        "G": list(g),
        "E": 93,
        "W": sum(comb(x, 2) for x in g),
        "SUM_CHOOSE3_DEGREES": sum(comb(x, 3) for x in g),
        "SUM_D": sum(d),
        "SUM_D_SQUARED": sum(x * x for x in d),
        "GRAPH_DEGREE_SUM": sum(g),
        "GRAPH_DEGREE_SQUARED_SUM": sum(x * x for x in g),
        "GOODMAN_SUM": goodman.numerator,
    }


def bounded_partition(length: int, low: int, high: int) -> tuple[int, ...]:
    """Coefficient of each total in multiset partitions, independent of tau products."""
    table = [[0] * 10 for _ in range(length + 1)]
    table[0][0] = 1
    for value in range(low, high + 1):
        for size in range(1, length + 1):
            for total in range(value, 10):
                table[size][total] += table[size - 1][total - value]
    return tuple(table[length])


def independent_count(bits: tuple[int, ...]) -> int:
    polynomial = [1] + [0] * 9
    for bit, count in Counter(bits).items():
        pop = bit.bit_count()
        part = bounded_partition(count, max(0, 2 - pop), 6 - pop)
        polynomial = [sum(polynomial[j] * part[i - j] for j in range(i + 1)) for i in range(10)]
    return sum(polynomial)


def histogram_multisets() -> Iterator[tuple[int, ...]]:
    """Independent 16-bin occupancy recursion, rather than combinations iterator."""

    def visit(
        bit: int, slots: int, caps: tuple[int, ...], prefix: tuple[int, ...]
    ) -> Iterator[tuple[int, ...]]:
        if bit == 16:
            if slots == 0:
                yield prefix
            return
        for count in range(slots + 1):
            remaining = tuple(caps[i] - count * (bit >> i & 1) for i in range(4))
            if min(remaining) >= 0:
                yield from visit(bit + 1, slots - count, remaining, prefix + (bit,) * count)

    yield from visit(0, 5, (2, 3, 5, 5), ())


def multisets() -> tuple[tuple[int, ...], ...]:
    entries = tuple(
        b
        for b in combinations_with_replacement(range(16), 5)
        if all(sum(x >> i & 1 for x in b) <= 6 - d for i, d in enumerate(LOW))
    )
    require(set(entries) == set(histogram_multisets()), "incomplete multiset domain")
    require(len(entries) == 6036, "wrong multiset census")
    return entries


def states(bits: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
    ranges = [range(max(0, 2 - b.bit_count()), 7 - b.bit_count()) for b in bits]
    for tau in product(*ranges):
        if sum(tau) <= 9 and all(
            bits[i] != bits[i - 1] or tau[i] <= tau[i - 1] for i in range(1, 5)
        ):
            yield tau


def triangle_count(n: int, edges: Sequence[tuple[int, int]]) -> int:
    edge_set = set(edges)
    return sum({(a, b), (a, c), (b, c)} <= edge_set for a, b, c in combinations(range(n), 3))


@cache
def zero_graphs() -> dict[tuple[int, ...], tuple[tuple[tuple[int, int], ...], ...]]:
    groups: dict[tuple[int, ...], list[tuple[tuple[int, int], ...]]] = {}
    for mask in range(1024):
        edges = [p for i, p in enumerate(ZPAIRS) if mask >> i & 1]
        deg = tuple(sum(v in p for p in edges) for v in range(5))
        missing = tuple(p for p in ZPAIRS if p not in edges)
        groups.setdefault(deg, []).append(missing)
    require(sum(map(len, groups.values())) == 1024, "incomplete zero graph domain")
    return {d: tuple(v) for d, v in groups.items()}


def zero_minimum(bits: tuple[int, ...], zeta: tuple[int, ...]) -> int | None:
    graphs = zero_graphs().get(tuple(6 - z for z in zeta), ())
    if not graphs:
        return None
    return min(
        triangle_count(5, missing) + sum((bits[u] & bits[v]).bit_count() for u, v in missing)
        for missing in graphs
    )


@cache
def graphical(degrees: tuple[int, ...]) -> bool:
    if sum(degrees) % 2 or any(d < 0 or d >= len(degrees) for d in degrees):
        return False
    ordered = sorted(degrees, reverse=True)
    return all(
        sum(ordered[:j]) <= j * (j - 1) + sum(min(d, j) for d in ordered[j:])
        for j in range(1, len(ordered) + 1)
    )


def low_patterns(
    bits: tuple[int, ...],
) -> tuple[tuple[int, tuple[int, ...], int, tuple[int, ...]], ...]:
    sigma = tuple(sum(b >> i & 1 for b in bits) for i in range(4))
    m = tuple(8 - d + s for d, s in zip(LOW, sigma, strict=True))
    room = tuple(6 + d - s for d, s in zip(LOW, sigma, strict=True))
    inter = tuple(sum(b >> x & b >> y & 1 for b in bits) for x, y in PAIRS)
    patterns: list[tuple[int, tuple[int, ...], int, tuple[int, ...]]] = []
    for mask in range(64):
        adjacent = tuple(p for i, p in enumerate(PAIRS) if mask >> i & 1)
        missing = tuple(p for i, p in enumerate(PAIRS) if not mask >> i & 1)
        a = tuple(sum(x in p for p in adjacent) for x in range(4))
        if any(a[x] > room[x] for x in range(4)):
            continue
        cross_rows = tuple(m[x] - sum(x in p for p in missing) for x in range(4))
        cross = sorted(cross_rows, reverse=True)
        if min(cross) < 0 or any(
            sum(cross[:j]) > limit for j, limit in ((1, 11), (2, 22), (3, 31))
        ):
            continue
        inside = triangle_count(4, missing)
        codegree = max(inside, sum(max(0, m[x] + m[y] - 15) for x, y in missing) - 2 * inside)
        codegree = max(
            codegree, inside + sum(max(0, cross_rows[x] + cross_rows[y] - 11) for x, y in missing)
        )
        overlap = sum(inter[i] for i in range(6) if not mask >> i & 1)
        patterns.append(
            (
                overlap + codegree,
                tuple(room[x] - a[x] for x in range(4)),
                sum(m) - 2 * len(missing) - 31,
                cross_rows,
            )
        )
    return tuple(patterns)


def low_minimum(
    patterns: Sequence[tuple[int, tuple[int, ...], int, tuple[int, ...]]],
    delta: tuple[int, ...],
    d5: int,
) -> int | None:
    values = [
        base
        + sum(max(0, delta[x] - room[x]) for x in range(4))
        + sum(max(0, (31 + d5 - sum(cross)) // 2 - (11 - e) * (4 if d5 else 3)) for e in cross)
        for base, room, needed, cross in patterns
        if d5 >= needed and (31 + d5 - sum(cross)) % 2 == 0
    ]
    return min(values) if values else None


def correction(parts: Sequence[int]) -> int:
    require(
        len(parts) == 4 and all(type(x) is int and x >= 0 for x in parts),
        "invalid nonnegative correction",
    )
    return sum(parts)


@cache
def enumerate_t245() -> Document:
    derived = facts(TARGET)
    require(
        (derived["W"], derived["SUM_CHOOSE3_DEGREES"], derived["GOODMAN_SUM"]) == (825, 2299, 291),
        "T245 facts",
    )
    records: list[list[int]] = []
    digest = hashlib.sha256()
    count = recurrence_count = feasible = maxima = 0
    best: int | None = None
    witness: Document = {}
    for bits in multisets():
        sigma = tuple(sum(b >> i & 1 for b in bits) for i in range(4))
        base = 231 + sum(s * (8 - d + s) for s, d in zip(sigma, LOW, strict=True)) - 10 * sum(sigma)
        patterns = low_patterns(bits)
        local_count = local_feasible = 0
        local_max: int | None = None
        for tau in states(bits):
            count += 1
            local_count += 1
            d5 = sum(tau)
            zeta = tuple(b.bit_count() + t for b, t in zip(bits, tau, strict=True))
            upper = base - 6 * d5 + sum(z * (z - 2) for z in zeta)
            m_degrees = (
                tuple(8 - d + s for d, s in zip(LOW, sigma, strict=True))
                + (2,) * 2
                + (3,) * (9 - d5)
                + (4,) * d5
            )
            if not graphical(m_degrees):
                continue
            zero = zero_minimum(bits, zeta)
            if zero is None:
                continue
            delta = tuple(
                sum(t for b, t in zip(bits, tau, strict=True) if b >> x & 1) for x in range(4)
            )
            low = low_minimum(patterns, delta, d5)
            if low is None:
                continue
            feasible += 1
            local_feasible += 1
            value = upper - correction((zero, low, 0, 0))
            local_max = value if local_max is None else max(local_max, value)
            digest.update(bytes(bits + tau) + (str(value) + "\n").encode())
            if best is None or value > best:
                best, maxima = value, 0
                witness = {
                    "B": list(bits),
                    "TAU": list(tau),
                    "SIGMA": list(sigma),
                    "ZETA": list(zeta),
                    "UPPER_WITHOUT_CORRECTIONS": upper,
                    "MIN_ZERO_PENALTY": zero,
                    "MIN_LOW_PENALTY": low,
                    "VALUE": value,
                }
            if value == best:
                maxima += 1
        recounted = independent_count(bits)
        require(local_count == recounted, "independent state recount mismatch")
        recurrence_count += recounted
        records.append([*bits, local_count, local_feasible, -1 if local_max is None else local_max])
    require(count == recurrence_count == 2196583 and best == 245, "incomplete domain or wrong cap")
    return {
        "FACTS": derived,
        "REDUCED_MULTISETS": len(records),
        "NECESSARY_STATES": count,
        "INDEPENDENT_RECOUNT": recurrence_count,
        "GRAPH_AND_LOW_FEASIBLE_STATES": feasible,
        "UNIVERSAL_T_CAP": best,
        "ARGMAX_COUNT": maxima,
        "FIRST_RELAXATION_ARGMAX": witness,
        "COVERAGE_COLUMNS": ["B0", "B1", "B2", "B3", "B4", "STATES", "FEASIBLE", "MAX"],
        "COMPLETE_MULTISET_COVERAGE": records,
        "STATE_VALUE_SHA256": digest.hexdigest(),
        "ZERO_GRAPHS": 1024,
        "LOW_PATTERNS": 64,
        "STATES_PRUNED": 0,
        "DOMAIN": "Necessary conditions; all states visited; no legal attainment claimed",
        "LEGAL_ATTAINMENT": "UNKNOWN",
    }


def validate_t245(proof: Mapping[str, object]) -> None:
    require(
        render(proof) == render(enumerate_t245()), "incomplete finite domain or invalid correction"
    )


def cohort_histograms() -> set[str]:
    result: set[str] = set()

    def visit(degree: int, slots: int, total: int, square: int, counts: tuple[int, ...]) -> None:
        if degree < 0:
            if (slots, total, square) == (0, 0, 0):
                result.add("".join(str(6 - i) * n for i, n in enumerate(counts)))
            return
        for n in range(slots + 1):
            if n * degree <= total and n * degree * degree <= square:
                visit(
                    degree - 1,
                    slots - n,
                    total - n * degree,
                    square - n * degree * degree,
                    (*counts, n),
                )

    visit(6, 20, 66, 244, ())
    return result


def cohort_recurrence() -> set[str]:
    @cache
    def tails(slots: int, cap: int, total: int, square: int) -> tuple[str, ...]:
        if slots == 0:
            return ("",) if total == square == 0 else ()
        if total < 0 or square < 0 or total > slots * cap or square > slots * cap * cap:
            return ()
        return tuple(
            str(x) + tail
            for x in range(cap + 1)
            for tail in tails(slots - 1, x, total - x, square - x * x)
        )

    return set(tails(20, 6, 66, 244))


def cohort_ids(cursor: Mapping[str, object]) -> list[str]:
    ids = cast(list[str], cursor["PROFILE_IDS"])
    require(len(ids) == len(set(ids)) == 197, "cursor identity count")
    selected = sorted(p for p in ids if sum(x * x for x in common.profile(p)) == 244)
    require(set(selected) == cohort_histograms() == cohort_recurrence(), "wrong cohort membership")
    require(
        len(selected) == 41 and sha(("\n".join(selected) + "\n").encode("ascii")) == COHORT_SHA,
        "wrong cohort ID serialization",
    )
    return selected


def multiplicity_premise() -> Document:
    margins = [
        Fraction(r - comb(r, 2) + comb(r, 3) - int(r > 0)) - Fraction(4 * comb(r, 4), 7)
        for r in range(8)
    ]
    require(
        all(x >= 0 for x in margins) and comb(7, 2) // comb(3, 2) == 7,
        "invalid fourth order multiplicity premise",
    )
    s1 = 20 * 7 * sum(comb(6, k) * comb(43, 7 - k) for k in range(3, 7))
    s2 = 93 * 574000 + 97 * 107800
    require((s1, s2) == (372228640, 63838600), "model S1/S2")
    return {
        "MAX_WINNING_TICKETS": 7,
        "OUTCOME_LABELS": 7,
        "PAIR_LINEARITY": True,
        "POINTWISE_MARGINS": [[x.numerator, x.denominator] for x in margins],
        "S1": s1,
        "S2": s2,
        "INHERITED_S4_FLOOR": 112,
        "S5_ADOPTED": False,
    }


def envelope(cap: int) -> list[Term]:
    require(type(cap) is int and cap in (266, 245), "wrong T cap")
    d = common.profile(TARGET)
    g = tuple(6 + x for x in d)
    w, j, top = sum(comb(x, 2) for x in g), sum(comb(x, 3) for x in g), max(g)
    a = sum(x * (4 + x) for x in d) // 3
    require(route.r28.profile_s4_floor(d) == 112, "inherited S4 drift")
    result: list[Term] = []
    for t in range(22, cap + 1):
        k4 = max(0, -(-(j - (top - 2) * (w - 3 * t)) // 4))
        contained = min(a, k4)
        s4 = max(112, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        raw = 372228640 - 63838600 + s3
        exact = Fraction(raw) - Fraction(4 * s4, 7)
        bound = -(-exact.numerator // exact.denominator)
        require(bound == (7 * raw - 4 * s4 + 6) // 7, "incorrect rounding")
        result.append((t, bound, k4, contained, s4, s3))
    require(result == route.route_b_envelope(d, cap, 112), "frozen Route-B mismatch")
    return result


def validate_terms(cap: int, terms: Sequence[Sequence[int]]) -> None:
    require(
        [list(t) for t in envelope(cap)] == [list(t) for t in terms],
        "incomplete terms or incorrect rounding",
    )


def cohort_theorem(cursor: Mapping[str, object]) -> Document:
    ids = cohort_ids(cursor)
    model = multiplicity_premise()
    for pid in ids:
        f = facts(pid)
        require(
            (
                f["SUM_D"],
                f["SUM_D_SQUARED"],
                f["W"],
                f["GRAPH_DEGREE_SUM"],
                f["GRAPH_DEGREE_SQUARED_SUM"],
                f["GOODMAN_SUM"],
            )
            == (66, 244, 785, 186, 1756, 251),
            "cohort degree or Goodman identity",
        )
        old = route.coarse_profile_envelope(common.profile(pid))
        require(
            old.graph_triangle_upper_bound == 261
            and old.family_upper_bound == 313394584
            and old.fourth_order_credit == 64
            and old.wedge_count == 785,
            "old cohort evaluator",
        )
        require(route.r28.profile_s4_floor(common.profile(pid)) >= 112, "inherited S4 premise")
    s3 = 2800 * 785 + 11872 * (251 - 22) - 30800
    bound = integer(model["S1"]) - integer(model["S2"]) + s3 - 4 * 112 // 7
    require((s3, bound) == (4885888, 313275864), "cohort bound")
    return {
        "PROFILE_IDS": ids,
        "COUNT": len(ids),
        "IDS_SHA256": COHORT_SHA,
        "MEMBERSHIP_METHODS": ["degree histogram", "memoized sorted-degree recurrence"],
        "GOODMAN_IDENTITY": 251,
        "UNIVERSAL_T_CAP": 251,
        "OLD_COARSE_T_CAP": 261,
        "OPEN_WEDGES_MIN": 785 - 3 * 251,
        "S3_UPPER_BOUND": s3,
        "INHERITED_S4_FLOOR": 112,
        "FOURTH_ORDER_CREDIT": 4 * 112 // 7,
        "OLD_BOUND": 313394584,
        "NEW_BOUND": bound,
        "DELTA": 313394584 - bound,
        "LEGAL_ATTAINMENT": "UNKNOWN",
    }


def replay_base(base: Mapping[str, object]) -> tuple[dict[str, int], Document]:
    require(sha(render(base)) == BASE_SHA, "altered Base authority")
    rows = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    coarse = {p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    ids = cast(list[str], cursor["PROFILE_IDS"])
    require(
        len(rows) == 4647
        and len(coarse) == len(set(ids)) == len(ids) == 197
        and set(ids) == set(coarse)
        and not set(rows) & set(coarse),
        "missing rows or cursor coverage",
    )
    require(
        sha(common.projection(rows)) == base["BOUNDS_SHA256_AFTER"]
        and sha(render(cursor)) == base["CURSOR_SHA256"],
        "projection identity",
    )
    for pid, bound in coarse.items():
        require(
            bound == route.coarse_profile_envelope(common.profile(pid)).family_upper_bound,
            "cursor bound drift",
        )
    require(
        common.family(rows, cursor)
        == (integer(base["FAMILY_BOUND_AFTER"]), base["FAMILY_OWNER_IDS"]),
        "Base family replay",
    )
    return rows, cursor


def apply_updates(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    base: Document,
    row_updates: Sequence[tuple[str, int, int]],
    cursor_updates: Sequence[tuple[str, int, int]],
) -> tuple[dict[str, int], Document]:
    before, frozen = replay_base(base)
    require(
        len(rows) == len(dict(rows)) == len(before) and dict(rows) == before,
        "missing, duplicate or altered row",
    )
    require(render(cursor) == render(frozen), "cursor identities or coverage changed")
    cohort = cohort_theorem(cursor)
    ids = cast(list[str], cohort["PROFILE_IDS"])
    bound = max(t[1] for t in envelope(245))
    require(
        list(row_updates) == [(TARGET, 245, bound)], "duplicate row updates, wrong cap or bound"
    )
    require(
        len(cursor_updates) == len({p for p, _, _ in cursor_updates}) == 41
        and set(cursor_updates) == {(p, 251, integer(cohort["NEW_BOUND"])) for p in ids},
        "duplicate cursor updates, wrong cohort, cap or bound",
    )
    after = {**before, TARGET: bound}
    new_coarse = {p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    for p, _, b in cursor_updates:
        new_coarse[p] = b
    revised: Document = {
        **cursor,
        "COARSE_BOUND_PROJECTION": new_coarse,
        "BOUND": max(new_coarse.values()),
    }
    require({p for p in before if before[p] != after[p]} == {TARGET}, "unexpected resolved update")
    require(
        {p for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items() if v != new_coarse[p]}
        == set(ids),
        "unexpected cursor update",
    )
    return after, revised


def scenario(rows: Mapping[str, int], cursor: Mapping[str, object], incumbent: int) -> Document:
    maximum, owners = common.family(rows, cursor)
    all_bounds = [
        *rows.values(),
        *(integer(v) for v in obj(cursor["COARSE_BOUND_PROJECTION"]).values()),
    ]
    return {
        "FAMILY_BOUND": maximum,
        "OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": maximum - incumbent,
        "STILL_OPEN_PROFILE_COUNT": sum(b > incumbent for b in all_bounds),
    }


def compute_result() -> Document:
    provenance = source_authority()
    base = load_base()
    before, cursor = replay_base(base)
    proof = enumerate_t245()
    old, new = envelope(266), envelope(245)
    bound = max(t[1] for t in new)
    require(
        (len(old), len(new), max(t[1] for t in old), bound)
        == (245, 224, before[TARGET], 313206768),
        "T245 complete envelope",
    )
    cohort = cohort_theorem(cursor)
    ids = cast(list[str], cohort["PROFILE_IDS"])
    updates = [(p, 251, integer(cohort["NEW_BOUND"])) for p in ids]
    after, revised = apply_updates(
        list(before.items()), cursor, base, [(TARGET, 245, bound)], updates
    )
    incumbent = integer(base["INCUMBENT"])
    scenarios = {
        "S0": scenario(before, cursor, incumbent),
        "S1": scenario(before, revised, incumbent),
        "S2": scenario(after, cursor, incumbent),
        "S3": scenario(after, revised, incumbent),
    }
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_SINGLE_LOCAL_COMMIT",
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROOF": __doc__,
        "PROVENANCE": provenance,
        "MODEL": MODEL,
        "MULTIPLICITY_PREMISE": multiplicity_premise(),
        "T245_PROOF": proof,
        "T245_ENVELOPE": {
            "OLD_TERMS": [list(t) for t in old],
            "NEW_TERMS": [list(t) for t in new],
            "OLD_TERM_COUNT": len(old),
            "NEW_TERM_COUNT": len(new),
            "OLD_BOUND": max(t[1] for t in old),
            "NEW_BOUND": bound,
            "STRICT_GAIN_MARGIN": incumbent - bound,
            "STRICT_GAIN_EXCLUDED": bound <= incumbent,
            "S5_ADOPTED": False,
            "MAXIMIZING_TERMS": [list(t) for t in new if t[1] == bound],
        },
        "COHORT_PROOF": cohort,
        "FOUR_SCENARIO_REPLAY": scenarios,
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "CURSOR": revised,
        "RESOLVED_ROWS": len(before),
        "CURSOR_PROFILES": len(obj(cursor["COARSE_BOUND_PROJECTION"])),
        "RESOLVED_ROWS_UPDATED": sum(before[p] != after[p] for p in before),
        "CURSOR_BOUNDS_UPDATED": len(updates),
        "OTHER_RESOLVED_ROWS_UNCHANGED": sum(before[p] == after[p] for p in before),
        "OTHER_CURSOR_BOUNDS_UNCHANGED": len(obj(cursor["COARSE_BOUND_PROJECTION"])) - len(updates),
        "OTHER_RESOLVED_SHA256": sha(
            common.projection({p: b for p, b in before.items() if p != TARGET})
        ),
        "OTHER_CURSOR_SHA256": sha(
            common.projection(
                {
                    p: integer(b)
                    for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()
                    if p not in ids
                }
            )
        ),
        "CURSOR_IDENTITIES_AND_COVERAGE_UNCHANGED": {
            k: v for k, v in cursor.items() if k not in ("BOUND", "COARSE_BOUND_PROJECTION")
        },
        "FAMILY_DELTA": integer(obj(scenarios["S0"])["FAMILY_BOUND"])
        - integer(obj(scenarios["S3"])["FAMILY_BOUND"]),
        "INCUMBENT": incumbent,
        "INHERITED_CAVEATS": "PRESERVED_BY_IMMUTABLE_REFERENCE",
        "HISTORICAL_PROJECTED_RESULT": (
            "Earlier conditional projections remain historical; "
            "this replay is new exact authority pending Judge"
        ),
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "PRODUCTION_DB_RUNTIME_RUN1_MUTATED": "NO",
        "G01_TO_G20_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 21)},
        "GATE_SCOPE": (
            "Exact-tree independent Judge externally; "
            "post-acceptance lifecycle in local commit and audit"
        ),
    }


def verify_result(stored: Mapping[str, object]) -> None:
    require(render(stored) == render(compute_result()), "exact result replay mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce T245/cohort proof and exact family authority"
    )
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = ROOT / RESULT
    value = compute_result()
    raw = render(value)
    if args.verify or path.exists():
        require(path.is_file() and path.read_bytes() == raw, "sealed result differs")
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    print(render(value["FOUR_SCENARIO_REPLAY"]).decode().strip())


if __name__ == "__main__":
    main()
