"""Exact T237 profile certificate and joint T257/T237 Family projection.

Frozen model: 20 six-label tickets, 22 triple supports, 27 pair supports,
and pair-linearity. The simple overlap graph G has degree g=6+d. For the
profile 6,5^10,4,3,2,1,0^5, sum(d)=66, E(G)=93, W=sum C(g,2)=821,
J=sum C(g,3)=2265, and Goodman gives T(G)+T(complement G)=287.

Core/zero split. Let K={d>0} (15 vertices), Z={d=0} (5 vertices),
sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|, and
r=sum(sigma)=sum(zeta). Every cross edge is a pair support, so
0<=sigma_x<=6-d_x and 2<=zeta_u<=6. The equality of sums counts the same
cross edges. The complement graphs M=complement(G[K]) and
N=complement(G[Z]) have degrees h_x=8-d_x+sigma_x and mu_u=zeta_u-2.
Thus E(M)=(54+r)/2 and E(N)=(r-10)/2; integrality forces even r, and
10<=r<=24.

For an M-edge xy, its common complement neighbours in Z number
5-sigma_x-sigma_y+c_Z(x,y), where c_Z counts zeros joined in G to both x,y.
For an N-edge uv, its common complement neighbours in K number
15-zeta_u-zeta_v+c_K(u,v). Every mixed complement triangle has exactly one
same-shore edge, so summing by that edge counts it exactly once. The four
remainder terms are P=T(M)+T(N)+sum_M c_Z+sum_N c_K, each a cardinality.
Consequently T(G)=227+sum_K sigma_x(sigma_x-d_x-4)+sum_Z zeta_u^2-P.
The four classes are disjoint: all-core triangles, all-zero triangles,
and mixed triples of types 2K+1Z and 1K+2Z with a complement same-shore
edge and two G cross edges. In each mixed triple its same-shore edge is
unique. Thus no term is subtracted twice. Expanding the mixed complement
triangle count gives 60+10r-sum(sigma*h)-sum(zeta*mu)+P; subtracting from
287 proves the identity for every realization, without assigning P=0.

For a graph F on n vertices with e edges and degrees a_i, summing common
neighbours over edges gives 3T(F)>=sum(a_i^2)-n*e. For a subset L of h
highest-degree vertices, at least
k=ceil((sum_L a-sum_outside min(h,a))/2) internal edges are forced (or zero
if negative). Each internal edge ij has at least max(0,a_i+a_j-n) common
neighbours. Their sum counts 3T(F[L])+T(two vertices in L), at most
T(F)+2*C(h,3). The sum of the k smallest candidate edge weights minus
2*C(h,3) is therefore another triangle floor. Taking the maximum of these
floors and zero proves the T(M), T(N) floors in both algorithms.
For any vertex subset S of F, e_F(S)>=max(0,sum_S a-e). Its minimum degree
sum is at least the sum of the |S| smallest degrees. Summing this floor
over core vertices' G-zero neighbours bounds sum_N c_K; summing over
zero vertices' G-core neighbours bounds sum_M c_Z. These four separate
nonnegative floors yield CORRECTED maxima. RAW is the identity's upper
envelope using P>=0; its computed maximum supplies the conservative final
T cap. Corrected maxima are reported separately, never as legal attainment.

Finite domain. Equal-d core vertices can be permuted without changing any
graph condition, P floor, or objective. Sorting sigma inside each equal-d
class removes only this symmetry; sorting zeta removes only zero-vertex
permutations. The six class sizes/ranges yield 3960 raw sigma signatures.
All 1024 labelled simple graphs on Z are enumerated and grouped by their
zeta degree multiset; these give 31 graphical zero classes among 126 sorted
lists in {2,...,6}. A core signature is retained if at least one zero-degree class matches:
M is graphical and the cross degrees pass Gale-Ryser. Distinct sigma
signatures, (sigma,zeta) matchings, and (sigma,zero-graph-mask) pairs are
different statistical units. Core counts include each sigma once; labelled
core counts include each labelled sigma once, independent of how many zeta
classes match. Matching counts and graph-pair counts retain their full
multiplicity. These are necessary conditions for every
realization, so filtering cannot discard one. Algorithm A enumerates sorted
class signatures with Erdos-Gallai and core-side cross cuts. Algorithm B
independently enumerates every labelled core sigma assignment and every
labelled zero graph mask, with Havel-Hakimi and zero-side cross cuts. It
reconstructs every class field and every r maximum. Neither algorithm assumes
a graph realization or support attainment from a degree list.

The Route-B authority uses the frozen local weights S1=372228640 and
S2=63838600. For every integer T in the full range, exact integer K4 and
contained-K4 lower bounds give S4>=max(112,679q-231 min(q,193)); exact
Fraction arithmetic rounds the final rational outward by ceiling. Every old
and new term is stored and independently compared with the frozen evaluator.
S5 is not used.

Family composition replays the complete pinned 4647 resolved rows and 197
cursor profiles four times from the immutable Base. Only the two specified
rows change. Historical authority caveats remain verbatim; legal attainment
and the global K20 optimum remain UNKNOWN.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import ceil, comb, factorial
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route
from . import b649_min_s2_advanced_11row_exact_adoption_r1 as local
from . import b649_min_s2_owner_ab_exact_family_composition_r1 as common

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_T237_FORMAL_CERTIFICATE_FROM_PATCH_R1"
OWNER_CONVERSATION_ID = "01a148ab-aa84-7763-8592-1eea4a4d1b51"
STEM = "b649_min_s2_t257_t237_joint_exact_authority_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
RESULT = f"docs/research/matrix-native-results/{STEM.replace('_', '-')}-result.json"
BASE_HEAD = "9acea1331e021a9623fa593997d90cfc89a69136"
BASE_TREE = "de577e8d6f3ccbe52e663c96ee1528c95a0ee7ec"
BASE_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-owner-ab-t249-t260k4-composition-r1-result.json"
)
BASE_SHA = "9fbe17d020573835cd69f16296fee224ff4f83aef8b3e7a644f2ffaabdfe92c9"
BASE_UPSTREAM_HEAD = "bee6acaaf9d2781e2aae560138d8be99fb4789ed"
BASE_UPSTREAM_TREE = "7b382a405d8d734763b477aa88efafeba2e1ed9b"
BASE_UPSTREAM_SHA = "bca4ad19aebb9808c952259d677a4a07381aa43392c38715c8265427960fe6f6"
DONOR_HEAD = "bbfee5c20258fe69dbe48f070f86c6afa0020416"
DONOR_TREE = "6925613dda4a93bca22b91d74f5084e21d27f031"
DONOR_RESULT = (
    "docs/research/matrix-native-results/b649-min-s2-666655555553211-t257-formal-r2-result.json"
)
DONOR_SHA = "f2a2a48ff023dbb6a259911fb8b01b9a318b0982b5681f479549d35fdb1c3b42"
PROFILE = "65555555555432100000"
T257_PROFILE = "66665555555321100000"
D = tuple(map(int, PROFILE))
CORE = D[:15]
GROUPS = ((6, 1, 0), (5, 10, 1), (4, 1, 2), (3, 1, 3), (2, 1, 4), (1, 1, 5))
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}
INCUMBENT = 313263888
OLD_BOUND = 313391560
OLD_CAP = 267
NEW_CAP = 237
Document = dict[str, object]
Degrees = tuple[int, ...]
State = tuple[Degrees, Degrees]
Term = tuple[int, int, int, int, int, int]


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def no_duplicate_keys(pairs: list[tuple[str, object]]) -> Document:
    result: Document = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def decode(raw: bytes) -> Document:
    value = json.loads(raw, object_pairs_hook=no_duplicate_keys)
    require(isinstance(value, dict), "expected JSON object")
    return cast(Document, value)


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    return cast(Document, value)


def integer(value: object) -> int:
    require(type(value) is int, "expected integer")
    return cast(int, value)


def ledger(value: object) -> dict[str, int]:
    result = obj(value)
    return {key: integer(bound) for key, bound in result.items()}


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def working_bytes(path: str) -> bytes:
    target = ROOT / path
    require(target.is_file() and not target.is_symlink(), "unsafe working file")
    return target.read_bytes()


def frozen(path: str, digest: str | None = None, head: str = BASE_HEAD) -> bytes:
    require(not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe path")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path, "blob mode/path"
    )
    raw = git("cat-file", "blob", f"{head}:{path}")
    require(digest is None or sha(raw) == digest, "immutable source SHA256")
    require(working_bytes(path) == raw, "working source differs from immutable Base")
    return raw


def immutable_blob(head: str, path: str, digest: str | None = None) -> bytes:
    require(git("cat-file", "-t", head).strip() == b"commit", "pinned source commit")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "immutable blob mode/path",
    )
    raw = git("cat-file", "blob", f"{head}:{path}")
    require(digest is None or sha(raw) == digest, "immutable blob SHA256")
    return raw


def source_closure() -> dict[str, str]:
    pending = [route.__name__, local.__name__, common.__name__]
    pins: dict[str, str] = {}
    while pending:
        module = pending.pop()
        path = "src/" + module.replace(".", "/") + ".py"
        if path in pins:
            continue
        raw = frozen(path)
        imported = importlib.import_module(module)
        require(
            imported.__file__ is not None and Path(imported.__file__).resolve() == ROOT / path,
            "import root",
        )
        pins[path] = sha(raw)
        package = module.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    parts = package.split(".")
                    head = ".".join(parts[: len(parts) + 1 - node.level])
                    prefix = head + ("." + prefix if prefix else "")
                if prefix.startswith("lottolab"):
                    pending.extend(
                        [prefix]
                        if node.module
                        else [prefix + "." + alias.name for alias in node.names]
                    )
            elif isinstance(node, ast.Import):
                pending.extend(
                    alias.name for alias in node.names if alias.name.startswith("lottolab")
                )
    require(not any(module.startswith("ortools") for module in sys.modules), "heavy solver loaded")
    return dict(sorted(pins.items()))


def facts(profile: str = PROFILE, model: Mapping[str, object] = MODEL) -> Document:
    require(profile == PROFILE and dict(model) == MODEL, "wrong profile/model")
    d = tuple(map(int, profile))
    g = tuple(6 + value for value in d)
    a_max = sum(value * (degree - 2) for value, degree in zip(d, g, strict=True)) // 3
    value: Document = {
        "PROFILE": profile,
        "D": list(d),
        "G": list(g),
        "SUM_D": sum(d),
        "CORE_VERTICES": sum(value > 0 for value in d),
        "ZERO_VERTICES": d.count(0),
        "E": sum(g) // 2,
        "W": sum(comb(value, 2) for value in g),
        "SUM_CHOOSE3_DEGREES": sum(comb(value, 3) for value in g),
        "GOODMAN": comb(20, 3) - sum(value * (19 - value) for value in g) // 2,
        "A_MAX": a_max,
    }
    expected = (66, 15, 5, 93, 821, 2265, 287, 193)
    keys = (
        "SUM_D",
        "CORE_VERTICES",
        "ZERO_VERTICES",
        "E",
        "W",
        "SUM_CHOOSE3_DEGREES",
        "GOODMAN",
        "A_MAX",
    )
    require(tuple(value[key] for key in keys) == expected, "frozen degree identities")
    return value


def validate_facts(value: Mapping[str, object]) -> None:
    require(render(value) == render(facts()), "wrong profile/degree identities")


def ceil_div(numerator: int, denominator: int) -> int:
    require(
        type(numerator) is int and type(denominator) is int and denominator > 0,
        "integer ceiling inputs",
    )
    return -(-numerator // denominator)


def graphical_eg(degrees: Degrees) -> bool:
    ordered = sorted(degrees, reverse=True)
    return (
        all(type(value) is int and 0 <= value < len(ordered) for value in ordered)
        and sum(ordered) % 2 == 0
        and all(
            sum(ordered[:h]) <= h * (h - 1) + sum(min(h, value) for value in ordered[h:])
            for h in range(1, len(ordered) + 1)
        )
    )


def graphical_hh(degrees: Degrees) -> bool:
    remaining = list(degrees)
    if any(type(value) is not int or value < 0 or value >= len(remaining) for value in remaining):
        return False
    while remaining:
        remaining.sort(reverse=True)
        degree = remaining.pop(0)
        if degree > len(remaining):
            return False
        for index in range(degree):
            remaining[index] -= 1
            if remaining[index] < 0:
                return False
    return True


@cache
def floors_a(degrees: Degrees) -> tuple[int, int]:
    require(graphical_eg(degrees), "A triangle floor requires a graphical sequence")
    n, edges = len(degrees), sum(degrees) // 2
    square = max(0, ceil_div(sum(value * value for value in degrees) - n * edges, 3))
    ordered = sorted(degrees, reverse=True)
    prefix = square
    for h in range(1, n + 1):
        forced = max(0, ceil_div(sum(ordered[:h]) - sum(min(h, value) for value in ordered[h:]), 2))
        weights = sorted(max(0, ordered[i] + ordered[j] - n) for i, j in combinations(range(h), 2))
        prefix = max(prefix, sum(weights[:forced]) - 2 * comb(h, 3))
    return square, prefix


@cache
def floors_b(degrees: Degrees) -> tuple[int, int]:
    require(graphical_hh(degrees), "B triangle floor requires a graphical sequence")
    ordered = sorted(degrees)
    n, edges = len(ordered), sum(ordered) // 2
    square = max(0, ceil(Fraction(sum(value * value for value in ordered) - n * edges, 3)))
    prefix = square
    for outside in range(n):
        inside = ordered[outside:]
        h = len(inside)
        forced = max(
            0, ceil(Fraction(sum(inside) - sum(min(h, value) for value in ordered[:outside]), 2))
        )
        weights = sorted(max(0, inside[i] + inside[j] - n) for i, j in combinations(range(h), 2))
        prefix = max(prefix, sum(weights[:forced]) - 2 * comb(h, 3))
    return square, prefix


def validate_state(state: State) -> None:
    sigma, zeta = state
    require(len(sigma) == 15 and len(zeta) == 5, "wrong cross degree lengths")
    require(all(type(value) is int for value in (*sigma, *zeta)), "noninteger cross degree")
    require(
        all(0 <= value <= 6 - degree for value, degree in zip(sigma, CORE, strict=True)),
        "sigma capacity",
    )
    require(
        all(2 <= value <= 6 for value in zeta) and zeta == tuple(sorted(zeta)), "zeta range/order"
    )
    start = 0
    for _, count, _ in GROUPS:
        part = sigma[start : start + count]
        require(part == tuple(sorted(part)), "equal degree class order")
        start += count
    r = sum(sigma)
    require(r == sum(zeta) and 10 <= r <= 24 and r % 2 == 0, "cross sum or r range/parity")
    m = tuple(8 - degree + cross for degree, cross in zip(CORE, sigma, strict=True))
    require(graphical_eg(m), "M graphicality")
    require(graphical_eg(tuple(6 - value for value in zeta)), "zero graph graphicality")
    ordered = sorted(sigma, reverse=True)
    require(
        all(sum(ordered[:h]) <= sum(min(h, value) for value in zeta) for h in range(1, 16)),
        "cross Gale-Ryser",
    )


def canonical_sigma(labelled: Degrees) -> Degrees:
    require(len(labelled) == 15, "core length")
    result: list[int] = []
    start = 0
    for _, count, _ in GROUPS:
        result.extend(sorted(labelled[start : start + count]))
        start += count
    return tuple(result)


def orbit_size(sigma: Degrees) -> int:
    result = 1
    start = 0
    for _, count, _ in GROUPS:
        part = sigma[start : start + count]
        ways = factorial(count)
        for frequency in Counter(part).values():
            ways //= factorial(frequency)
        result *= ways
        start += count
    return result


def record_a(state: State) -> Document:
    validate_state(state)
    sigma, zeta = state
    m = tuple(8 - degree + cross for degree, cross in zip(CORE, sigma, strict=True))
    n = tuple(value - 2 for value in zeta)
    r = sum(sigma)
    raw = (
        227
        - 10 * r
        + sum(x * y for x, y in zip(sigma, m, strict=True))
        + sum(x * y for x, y in zip(zeta, n, strict=True))
    )
    ck = sum(max(0, sum(sorted(n)[:size]) - sum(n) // 2) for size in sigma)
    cz = sum(max(0, sum(sorted(m)[:size]) - sum(m) // 2) for size in zeta)
    fm, fn = floors_a(m), floors_a(n)
    parts = (max(fm), max(fn), ck, cz)
    require(all(part >= 0 for part in parts), "nonnegative remainder terms")
    return {
        "SIGMA": list(sigma),
        "ZETA": list(zeta),
        "R": r,
        "M": list(m),
        "N": list(n),
        "RAW": raw,
        "C_K": ck,
        "C_Z": cz,
        "T_M_FLOORS": list(fm),
        "T_N_FLOORS": list(fn),
        "P_PARTS": [max(fm), max(fn), ck, cz],
        "UPPER": raw - sum(parts),
    }


def record_b(labelled_sigma: Degrees, zeta: Degrees) -> Document:
    sigma = canonical_sigma(labelled_sigma)
    require(
        all(0 <= cross <= 6 - degree for cross, degree in zip(sigma, CORE, strict=True)),
        "B sigma capacity",
    )
    require(zeta == tuple(sorted(zeta)) and all(2 <= value <= 6 for value in zeta), "B zeta degree")
    require(sum(labelled_sigma) == sum(zeta) and sum(zeta) % 2 == 0, "B cross sum/parity")
    labelled_m = tuple(
        8 - degree + cross for degree, cross in zip(CORE, labelled_sigma, strict=True)
    )
    require(graphical_hh(labelled_m), "B Havel-Hakimi core graphicality")
    require(
        all(
            sum(sorted(zeta, reverse=True)[:h]) <= sum(min(h, value) for value in labelled_sigma)
            for h in range(1, 6)
        ),
        "B zero-side Gale-Ryser",
    )
    m = tuple(8 - degree + cross for degree, cross in zip(CORE, sigma, strict=True))
    n = tuple(value - 2 for value in zeta)
    r = sum(zeta)
    edges_m, edges_n = (54 + r) // 2, (r - 10) // 2
    complement_triangles = 5 * edges_m + 15 * edges_n
    complement_triangles -= sum(x * y for x, y in zip(sigma, m, strict=True))
    complement_triangles -= sum(x * y for x, y in zip(zeta, n, strict=True))
    raw = 287 - complement_triangles
    ck = sum(max(0, sum(n) // 2 - sum(sorted(n, reverse=True)[: 5 - size])) for size in sigma)
    cz = sum(max(0, sum(m) // 2 - sum(sorted(m, reverse=True)[: 15 - size])) for size in zeta)
    fm, fn = floors_b(m), floors_b(n)
    parts = (max(fm), max(fn), ck, cz)
    require(all(part >= 0 for part in parts), "nonnegative independent remainder terms")
    return {
        "SIGMA": list(sigma),
        "ZETA": list(zeta),
        "R": r,
        "M": list(m),
        "N": list(n),
        "RAW": raw,
        "C_K": ck,
        "C_Z": cz,
        "T_M_FLOORS": list(fm),
        "T_N_FLOORS": list(fn),
        "P_PARTS": [max(fm), max(fn), ck, cz],
        "UPPER": raw - sum(parts),
    }


def zero_masks_a() -> dict[Degrees, list[int]]:
    edges = list(combinations(range(5), 2))
    masks: dict[Degrees, list[int]] = {}
    for mask in range(1 << len(edges)):
        degree = [0] * 5
        for bit, (left, right) in enumerate(edges):
            if mask & (1 << bit):
                degree[left] += 1
                degree[right] += 1
        zeta = tuple(sorted(6 - value for value in degree))
        if graphical_eg(tuple(6 - value for value in zeta)):
            masks.setdefault(zeta, []).append(mask)
    require(sum(map(len, masks.values())) == 1024 and len(masks) == 31, "A zero graph masks")
    require(
        len(tuple(combinations_with_replacement(range(2, 7), 5))) == 126,
        "A raw zero degree classes",
    )
    return masks


def zero_masks_b() -> dict[Degrees, list[int]]:
    adjacency_edges = tuple((left, right) for right in range(1, 5) for left in range(right))
    masks: dict[Degrees, list[int]] = {}
    for mask in range(1024):
        degrees = tuple(
            sum((mask >> bit) & 1 for bit, edge in enumerate(adjacency_edges) if vertex in edge)
            for vertex in range(5)
        )
        zeta = tuple(sorted(6 - value for value in degrees))
        masks.setdefault(zeta, []).append(mask)
    require(
        sum(map(len, masks.values())) == 1024 and len(masks) == 31, "B labelled zero graph masks"
    )
    return masks


def raw_sigma_classes() -> Iterator[Degrees]:
    options = [
        tuple(combinations_with_replacement(range(maximum + 1), count))
        for _, count, maximum in GROUPS
    ]
    require(len(options[0]) == 1 and len(options[1]) == 11, "class ranges")
    for parts in product(*options):
        yield tuple(value for part in parts for value in part)


def labelled_sigma_values() -> Iterator[Degrees]:
    limits = tuple(maximum for _, count, maximum in GROUPS for _ in range(count))
    yield from product(*(range(limit + 1) for limit in limits))


def enumerate_a() -> tuple[dict[State, Document], Document]:
    masks = zero_masks_a()
    states: dict[State, Document] = {}
    raw_classes = 0
    raw_zero_lists = tuple(combinations_with_replacement(range(2, 7), 5))
    require(
        len(raw_zero_lists) == 126 and sum(len(v) for v in masks.values()) == 1024,
        "complete zero domain",
    )
    for sigma in raw_sigma_classes():
        raw_classes += 1
        m = tuple(8 - degree + cross for degree, cross in zip(CORE, sigma, strict=True))
        if not graphical_eg(m):
            continue
        descending = sorted(sigma, reverse=True)
        for zeta in masks:
            if sum(sigma) != sum(zeta):
                continue
            if not all(
                sum(descending[:h]) <= sum(min(h, value) for value in zeta) for h in range(1, 16)
            ):
                continue
            state = (sigma, zeta)
            record = record_a(state)
            require(state not in states, "duplicate class state")
            states[state] = record
    require(raw_classes == 3960, "raw sigma class count")
    compatible_pairs = sum(len(masks[zeta]) for _, zeta in states)
    retained_core = {sigma for sigma, _ in states}
    labeled_core_states = sum(orbit_size(sigma) for sigma in retained_core)
    labeled_matchings = sum(orbit_size(sigma) for sigma, _ in states)
    labeled_core_graph_pairs = sum(orbit_size(sigma) * len(masks[zeta]) for sigma, zeta in states)
    metadata: Document = {
        "RAW_CLASS_STATES": raw_classes,
        "RAW_ZERO_DEGREE_CLASSES": len(raw_zero_lists),
        "GRAPHICAL_ZERO_DEGREE_CLASSES": len(masks),
        "ZERO_GRAPH_MASKS": sum(len(value) for value in masks.values()),
        "RETAINED_CLASS_STATES": len(retained_core),
        "CORE_ZERO_DEGREE_MATCHINGS": len(states),
        "COMPATIBLE_CLASS_GRAPH_PAIRS": compatible_pairs,
        "LABELLED_CORE_STATES": labeled_core_states,
        "LABELLED_CORE_ZERO_DEGREE_MATCHINGS": labeled_matchings,
        "LABELLED_CORE_GRAPH_PAIRS": labeled_core_graph_pairs,
    }
    return states, metadata


def histogram_sequences(
    n: int, upper: int, value: int = 0, prefix: Degrees = ()
) -> Iterator[Degrees]:
    if value == upper:
        yield prefix + (value,) * n
        return
    for count in range(n + 1):
        yield from histogram_sequences(n - count, upper, value + 1, prefix + (value,) * count)


def independent_labelled_recount(
    masks: Mapping[Degrees, Sequence[int]],
) -> tuple[dict[State, Document], Document]:
    require(sum(len(value) for value in masks.values()) == 1024, "independent 1024-mask inventory")
    states: dict[State, Document] = {}
    labelled_states = 0
    labelled_matchings = 0
    labelled_graph_pairs = 0
    class_graph_pairs = 0
    raw_labelled = 0
    zero_classes = tuple(sorted(masks))
    for sigma_labelled in labelled_sigma_values():
        raw_labelled += 1
        m = tuple(8 - degree + cross for degree, cross in zip(CORE, sigma_labelled, strict=True))
        if not graphical_hh(m):
            continue
        sigma = canonical_sigma(sigma_labelled)
        matched = False
        for zeta in zero_classes:
            r = sum(zeta)
            if sum(sigma_labelled) != r:
                continue
            if not all(
                sum(sorted(zeta, reverse=True)[:h])
                <= sum(min(h, value) for value in sigma_labelled)
                for h in range(1, 6)
            ):
                continue
            matched = True
            labelled_matchings += 1
            actual_masks = masks[zeta]
            labelled_graph_pairs += sum(1 for _ in actual_masks)
            state = (sigma, zeta)
            row = record_b(sigma_labelled, zeta)
            previous = states.get(state)
            require(
                previous is None or previous == row,
                "equal degree permutations changed the objective",
            )
            states[state] = row
        labelled_states += int(matched)
    retained_core = {sigma for sigma, _ in states}
    for _, zeta in states:
        class_graph_pairs += sum(1 for _ in masks[zeta])
    metadata: Document = {
        "RAW_LABELLED_SIGMA_STATES": raw_labelled,
        "RETAINED_CLASS_STATES": len(retained_core),
        "CORE_ZERO_DEGREE_MATCHINGS": len(states),
        "COMPATIBLE_CLASS_GRAPH_PAIRS": class_graph_pairs,
        "LABELLED_CORE_STATES": labelled_states,
        "LABELLED_CORE_ZERO_DEGREE_MATCHINGS": labelled_matchings,
        "LABELLED_CORE_GRAPH_PAIRS": labelled_graph_pairs,
        "ZERO_GRAPH_MASKS": sum(len(value) for value in masks.values()),
    }
    return states, metadata


def r_maxima(states: Mapping[State, Mapping[str, object]], field: str = "RAW") -> dict[int, int]:
    require(field in ("RAW", "UPPER"), "unknown maxima field")
    maxima: dict[int, int] = {}
    for (sigma, _), row in states.items():
        r = sum(sigma)
        maxima[r] = max(maxima.get(r, -1), integer(row[field]))
    return dict(sorted(maxima.items()))


@cache
def enumeration() -> Document:
    a, meta_a = enumerate_a()
    masks_b = zero_masks_b()
    b, meta_b = independent_labelled_recount(masks_b)
    require(a == b, "independent finite domain/state fields differ")
    require(meta_a["ZERO_GRAPH_MASKS"] == meta_b["ZERO_GRAPH_MASKS"] == 1024, "zero masks")
    require(
        meta_a["RETAINED_CLASS_STATES"] == meta_b["RETAINED_CLASS_STATES"] == 1491,
        "retained class states",
    )
    require(
        meta_a["COMPATIBLE_CLASS_GRAPH_PAIRS"] == meta_b["COMPATIBLE_CLASS_GRAPH_PAIRS"] == 100834,
        "compatible graph pairs",
    )
    require(
        meta_a["LABELLED_CORE_STATES"] == meta_b["LABELLED_CORE_STATES"] == 154050,
        "labelled core states",
    )
    require(
        meta_a["LABELLED_CORE_GRAPH_PAIRS"] == meta_b["LABELLED_CORE_GRAPH_PAIRS"] == 6727928,
        "labelled core graph pairs",
    )
    for key in ("CORE_ZERO_DEGREE_MATCHINGS", "LABELLED_CORE_ZERO_DEGREE_MATCHINGS"):
        require(meta_a[key] == meta_b[key], "independent matching multiplicities")
    maxima_a, maxima_b = r_maxima(a, "RAW"), r_maxima(b, "RAW")
    corrected_a, corrected_b = r_maxima(a, "UPPER"), r_maxima(b, "UPPER")
    expected = {10: 233, 12: 237, 14: 237, 16: 235, 18: 235, 20: 233, 22: 235, 24: 235}
    require(maxima_a == maxima_b == expected, "r-class RAW maxima / universal T cap")
    require(corrected_a == corrected_b, "independent corrected maxima")
    require(all(corrected_a[r] <= bound for r, bound in maxima_a.items()), "remainder direction")
    rows = [a[key] for key in sorted(a)]
    return {
        **meta_a,
        "INDEPENDENT_RECOUNT": meta_b,
        "INDEPENDENT_STATE_FIELDS_EQUAL": True,
        "MATCHING_STATES_SHA256": sha(render(rows)),
        "STATES": rows,
        "STATE_UNIT": "ONE (SIGMA,ZETA) DEGREE MATCHING PER ROW",
        "R_CLASS_RAW_MAXIMA": {str(key): value for key, value in maxima_a.items()},
        "R_CLASS_CORRECTED_MAXIMA": {str(key): value for key, value in corrected_a.items()},
        "UNIVERSAL_T_CAP": max(maxima_a.values()),
        "CORRECTED_RELAXATION_CAP": max(corrected_a.values()),
        "FINAL_CAP_SOURCE": "COMPUTED RAW IDENTITY ENVELOPE; P>=0, NOT P=0",
        "RAW_ARGMAX": [row for row in rows if integer(row["RAW"]) == max(maxima_a.values())],
        "CORRECTED_ARGMAX": [
            row for row in rows if integer(row["UPPER"]) == max(corrected_a.values())
        ],
        "RELAXATION": (
            "NECESSARY_DEGREE_AND_CROSS_GRAPH CONDITIONS; "
            "SUPPORT ATTAINMENT NOT ASSERTED"
        ),
        "REALIZABILITY": "UNKNOWN",
        "COVERAGE_PROOF": __doc__,
    }


def validate_enumeration(value: Mapping[str, object]) -> None:
    require(
        render(value) == render(enumeration()), "incomplete/mutated finite domain or correction"
    )


def nonnegative_remainder(parts: Sequence[int]) -> int:
    require(
        len(parts) == 4 and all(type(part) is int and part >= 0 for part in parts),
        "wrong P sign/nonnegative cardinality",
    )
    return sum(parts)


def fraction_terms(cap: int) -> list[Term]:
    g = tuple(value + 6 for value in D)
    w = sum(comb(value, 2) for value in g)
    j = sum(comb(value, 3) for value in g)
    a_max = sum(value * (degree - 2) for value, degree in zip(D, g, strict=True)) // 3
    result: list[Term] = []
    for triangles in range(22, cap + 1):
        q = max(0, ceil(Fraction(j - 10 * (w - 3 * triangles), 4)))
        contained = min(q, a_max)
        s4 = max(112, 679 * q - 231 * contained)
        s3 = 2800 * w + 11872 * (triangles - 22) - 30800
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        result.append((triangles, ceil(exact), q, contained, s4, s3))
        require(Fraction(result[-1][1] - 1) < exact <= result[-1][1], "Route-B outward ceiling")
    return result


def validate_route_authority(a_max: int, s5_authority: object) -> None:
    require(type(a_max) is int and a_max == 193, "wrong contained K4 allowance")
    require(s5_authority == "NOT_PINNED / NOT_USED", "unsupported S5 authority")


def validate_rounding(s3: int, s4: int, bound: int) -> None:
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    require(
        type(bound) is int and Fraction(bound - 1) < exact <= bound, "incorrect Route-B ceiling"
    )


def integer_term(
    triangles: int, a_max: int = 193, s5_authority: object = "NOT_PINNED / NOT_USED"
) -> Term:
    validate_route_authority(a_max, s5_authority)
    require(type(triangles) is int and 22 <= triangles <= OLD_CAP, "triangle term range")
    q = max(0, ceil_div(2265 - 10 * (821 - 3 * triangles), 4))
    contained = min(q, a_max)
    s4 = max(112, 679 * q - 231 * contained)
    s3 = 2800 * 821 + 11872 * (triangles - 22) - 30800
    numerator = 7 * (372228640 - 63838600 + s3) - 4 * s4
    bound = ceil_div(numerator, 7)
    require(7 * (bound - 1) < numerator <= 7 * bound, "integer outward ceiling")
    validate_rounding(s3, s4, bound)
    return triangles, bound, q, contained, s4, s3


def integer_terms(cap: int) -> list[Term]:
    require(type(cap) is int and cap in (OLD_CAP, NEW_CAP), "wrong T cap")
    return [integer_term(triangles) for triangles in range(22, cap + 1)]


def envelope(cap: int) -> list[Term]:
    require(type(cap) is int and cap in (OLD_CAP, NEW_CAP), "wrong envelope domain")
    terms = integer_terms(cap)
    require(terms == fraction_terms(cap), "integer/Fraction Route-B term mismatch")
    require(terms == route.route_b_envelope(D, cap, 112), "frozen evaluator Route-B mismatch")
    return terms


def validate_terms(cap: int, terms: Sequence[Sequence[int]]) -> None:
    require(
        [list(term) for term in envelope(cap)] == [list(term) for term in terms],
        "missing/incorrect Route-B term",
    )


def family(rows: Mapping[str, int], cursor: Mapping[str, object]) -> Document:
    projection = ledger(obj(cursor["COARSE_BOUND_PROJECTION"]))
    ids = cast(list[str], cursor["PROFILE_IDS"])
    require(
        len(rows) == 4647 and len(projection) == len(ids) == len(set(ids)) == 197,
        "Family coverage counts",
    )
    require(
        set(ids) == set(projection) and not set(rows) & set(projection), "cursor membership/overlap"
    )
    all_bounds = {**rows, **projection}
    ordered = sorted(all_bounds.items(), key=lambda item: (-item[1], item[0]))
    top = ordered[0][1]
    owners = sorted(profile for profile, value in all_bounds.items() if value == top)
    return {
        "FAMILY_BOUND": top,
        "OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": top - INCUMBENT,
        "STILL_OPEN_PROFILE_COUNT": sum(value > INCUMBENT for value in all_bounds.values()),
        "RESOLVED_MAXIMUM": max(rows.values()),
        "CURSOR_MAXIMUM": max(projection.values()),
    }


def replay(base: Document, updates: Sequence[tuple[str, int]]) -> tuple[dict[str, int], Document]:
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    require(len(rows) == 4647 and base["RESOLVED_ROWS"] == 4647, "resolved row count")
    require(sha(render(base)) == BASE_SHA, "Base result/source hash mismatch")
    require(
        base["CURSOR_PROFILES"] == 197 and len(cast(list[str], cursor["PROFILE_IDS"])) == 197,
        "cursor count",
    )
    require(render(cursor) == render(obj(load_base()["CURSOR"])), "changed cursor")
    require(len(updates) == len(dict(updates)), "duplicate profile update")
    require(set(profile for profile, _ in updates) <= set(rows), "missing profile row")
    after = dict(rows)
    for profile, bound in updates:
        require(type(bound) is int, "integer row bound")
        after[profile] = bound
    changed = sorted(profile for profile in rows if rows[profile] != after[profile])
    require(changed == sorted(profile for profile, _ in updates), "row update mismatch")
    return after, family(after, cursor)


def parse_donor_report_hash(message: str) -> str:
    lines = [line.strip() for line in message.splitlines()]
    prefix = "Sealed precommit report SHA256:"
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            remainder = line[len(prefix) :].strip()
            if remainder:  # noqa: SIM108 - preserve the audited donor hash parser
                report_hash = remainder
            else:
                report_hash = next((item for item in lines[index + 1 :] if item), "")
            require(
                len(report_hash) == 64 and all(char in "0123456789abcdef" for char in report_hash),
                "T257 Judge report hash",
            )
            return report_hash
    require(False, "T257 Judge report hash")
    return ""


def verify_donor(
    head: str = DONOR_HEAD,
    tree: str = DONOR_TREE,
    result_path: str = DONOR_RESULT,
    result_sha: str = DONOR_SHA,
) -> Document:
    require(git("rev-parse", head + "^{tree}").decode().strip() == tree, "T257 donor tree")
    raw = immutable_blob(head, result_path, result_sha)
    donor = decode(raw)
    require(
        donor["TARGET_PROFILE"] == T257_PROFILE and donor["PROVEN_T_CAP"] == 257,
        "T257 donor profile/cap",
    )
    require(
        donor["FULL_PROFILE_BOUND"] == 313329096 and donor["MODEL"] == MODEL,
        "T257 donor bound/model",
    )
    require(
        donor["TASK_STATUS"] == "PROFILE_CERTIFICATE; FRESH_JUDGE_AND_LIFECYCLE_EXTERNAL",
        "T257 donor status",
    )
    source_path = "src/lottolab/research/b649_min_s2_666655555553211_t257_formal_r2.py"
    test_path = "tests/unit/test_b649_min_s2_666655555553211_t257_formal_r2.py"
    immutable_blob(head, source_path, cast(str, donor["SOURCE_SHA256"]))
    immutable_blob(head, test_path, cast(str, donor["TEST_SHA256"]))
    require(
        len(cast(list[object], donor["OLD_T_TERMS"])) == 243
        and len(cast(list[object], donor["NEW_T_TERMS"])) == 236,
        "T257 donor term coverage",
    )
    require(
        max(
            integer(cast(list[object], term)[1])
            for term in cast(list[object], donor["NEW_T_TERMS"])
        )
        == 313329096,
        "T257 donor term maximum",
    )
    message = git("log", "-1", "--format=%B", head).decode()
    require(
        "Fresh-context scientific Judge: VERIFIED_WITH_CAVEATS" in message
        and f"Exact judged tree: {tree}" in message,
        "T257 exact-tree Judge citation",
    )
    report_hash = parse_donor_report_hash(message)
    return {
        "HEAD": head,
        "TREE": tree,
        "RESULT_PATH": result_path,
        "RESULT_SHA256": sha(raw),
        "TARGET_PROFILE": donor["TARGET_PROFILE"],
        "PROVEN_T_CAP": donor["PROVEN_T_CAP"],
        "FULL_PROFILE_BOUND": donor["FULL_PROFILE_BOUND"],
        "OLD_T_TERMS": len(cast(list[object], donor["OLD_T_TERMS"])),
        "NEW_T_TERMS": len(cast(list[object], donor["NEW_T_TERMS"])),
        "FRESH_JUDGE": "VERIFIED_WITH_CAVEATS",
        "JUDGED_TREE": tree,
        "JUDGE_REPORT_SHA256": report_hash,
        "DONOR_RESULT": donor,
    }


def validate_base_upstream(
    base: Document,
    upstream_head: str = BASE_UPSTREAM_HEAD,
    upstream_tree: str = BASE_UPSTREAM_TREE,
    upstream_sha: str = BASE_UPSTREAM_SHA,
) -> None:
    require(
        base.get("BASE_HEAD") == upstream_head
        and base.get("BASE_TREE") == upstream_tree
        and base.get("BASE_RESULT_SHA256") == upstream_sha,
        "Base upstream lineage identity",
    )


def load_base(
    base_head: str = BASE_HEAD,
    base_tree: str = BASE_TREE,
    base_result: str = BASE_RESULT,
    base_sha: str = BASE_SHA,
    upstream_head: str = BASE_UPSTREAM_HEAD,
    upstream_tree: str = BASE_UPSTREAM_TREE,
    upstream_sha: str = BASE_UPSTREAM_SHA,
) -> Document:
    require(
        git("rev-parse", base_head + "^{tree}").decode().strip() == base_tree,
        "Base tree identity",
    )
    raw = frozen(base_result, base_sha, head=base_head)
    base = decode(raw)
    require(render(base) == raw, "canonical immutable Base result")
    validate_base_upstream(base, upstream_head, upstream_tree, upstream_sha)
    require(base["MODEL"] == MODEL and base["INCUMBENT"] == INCUMBENT, "Base model/incumbent")
    require(ledger(base["RESOLVED_ROW_BOUNDS"])[T257_PROFILE] == 313391636, "T257 old row")
    require(ledger(base["RESOLVED_ROW_BOUNDS"])[PROFILE] == OLD_BOUND, "T237 old row")
    require(base["HISTORICAL_R15"] == "NOT_VERIFIED", "preserve historical R15")
    return base


def family_replay(base: Document, bound_257: int, bound_237: int) -> Document:
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    scenarios: Document = {}
    updates = {
        "S0_BASE": (),
        "S1_T257_ONLY": ((T257_PROFILE, bound_257),),
        "S2_T237_ONLY": ((PROFILE, bound_237),),
        "S3_T257_T237_JOINT": ((T257_PROFILE, bound_257), (PROFILE, bound_237)),
    }
    snapshots: dict[str, dict[str, int]] = {}
    for label, changes in updates.items():
        after, result = replay(base, changes)
        snapshots[label] = after
        scenarios[label] = result
    final = snapshots["S3_T257_T237_JOINT"]
    changed = sorted(profile for profile in rows if rows[profile] != final[profile])
    require(changed == sorted((T257_PROFILE, PROFILE)), "only two exact rows may change")
    require(
        sum(rows[profile] == final[profile] for profile in rows) == 4645,
        "other resolved rows changed",
    )
    require(render(cursor) == render(base["CURSOR"]), "cursor mutation")
    expected = (313391636, 313391560, 313391636, 313391172)
    labels = tuple(updates)
    require(
        tuple(integer(obj(scenarios[label])["FAMILY_BOUND"]) for label in labels) == expected,
        "four-scenario Family replay",
    )
    require(obj(scenarios[labels[-1]])["OWNER_IDS"] == ["65555555555511111000"], "joint owner")
    return {
        "SCENARIOS": scenarios,
        "RESOLVED_ROW_BOUNDS": final,
        "CURSOR": cursor,
        "RESOLVED_ROWS": len(final),
        "UPDATED_ROWS": len(changed),
        "OTHER_ROWS_UNCHANGED": 4645,
        "CURSOR_PROFILES": len(cast(list[str], cursor["PROFILE_IDS"])),
        "CURSOR_PRESERVED": True,
        "FINAL_FAMILY_BOUND": integer(obj(scenarios[labels[-1]])["FAMILY_BOUND"]),
        "FAMILY_DELTA": integer(obj(scenarios[labels[0]])["FAMILY_BOUND"])
        - integer(obj(scenarios[labels[-1]])["FAMILY_BOUND"]),
        "GAP_TO_INCUMBENT": integer(obj(scenarios[labels[-1]])["GAP_TO_INCUMBENT"]),
        "STILL_OPEN_PROFILE_COUNT": integer(obj(scenarios[labels[-1]])["STILL_OPEN_PROFILE_COUNT"]),
        "FINAL_OWNER_IDS": obj(scenarios[labels[-1]])["OWNER_IDS"],
        "OTHER_ROWS_SHA256": sha(
            render({p: v for p, v in final.items() if p not in (T257_PROFILE, PROFILE)})
        ),
        "CURSOR_SHA256": sha(render(cursor)),
        "COMPLETE_REPLAY_COUNT": 4,
    }


def compute_result() -> Document:
    pins = source_closure()
    model_facts = facts()
    weights = local.local_weights()
    require(
        obj(weights).get("S1") == 372228640 and obj(weights).get("S2") == 63838600,
        "frozen Route-B local weights",
    )
    domain = enumeration()
    cap = integer(domain["UNIVERSAL_T_CAP"])
    require(cap == NEW_CAP, "T237 universal cap")
    donor = verify_donor()
    base = load_base()
    old, new = envelope(OLD_CAP), envelope(cap)
    require(len(old) == 246 and len(new) == 216, "Route-B complete term counts")
    old_bound, bound = max(term[1] for term in old), max(term[1] for term in new)
    require(old_bound == OLD_BOUND and bound == 313122700, "full-profile bounds")
    require([term[0] for term in new if term[1] == bound] == [237], "unique Route-B maximum")
    require(new[-1][4] == 153685, "T237 endpoint S4 floor")
    composition = family_replay(base, integer(donor["FULL_PROFILE_BOUND"]), bound)
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "DETERMINISTIC_CERTIFICATE_PENDING_FOCUSED_CHECKS_FRESH_JUDGE_AND_LIFECYCLE",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "MODEL": MODEL,
        "T257_DONOR": {key: value for key, value in donor.items() if key != "DONOR_RESULT"},
        "T237_PROFILE": PROFILE,
        "FACTS": model_facts,
        "T237_PROOF": __doc__,
        "ENUMERATION": domain,
        "T237_UNIVERSAL_CAP": cap,
        "CURRENT_T_CAP": OLD_CAP,
        "CURRENT_FULL_PROFILE_BOUND": old_bound,
        "NEW_FULL_PROFILE_BOUND": bound,
        "PROFILE_DELTA": old_bound - bound,
        "STRICT_GAIN_EXCLUDED": bound <= INCUMBENT,
        "ROUTE_B": {
            "OLD_TERMS": [list(term) for term in old],
            "NEW_TERMS": [list(term) for term in new],
            "OLD_TERM_COUNT": len(old),
            "NEW_TERM_COUNT": len(new),
            "OLD_T_RANGE": [22, OLD_CAP],
            "NEW_T_RANGE": [22, cap],
            "UNIQUE_MAXIMIZER_T": 237,
            "A_MAX": 193,
            "K4_FLOOR": new[-1][2],
            "CONTAINED_ALLOWANCE": 193,
            "S4_FLOOR": new[-1][4],
            "S5_AUTHORITY": "NOT_PINNED / NOT_USED",
            "ROUNDING": "OUTWARD_CEILING_OF_EXACT_RATIONAL",
        },
        "LOCAL_WEIGHT_RECOUNT": weights,
        "EVALUATOR_SOURCE_PINS": pins,
        "FAMILY_REPLAY": composition,
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": {
            "BASE": base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
            "T257_DONOR": obj(donor["DONOR_RESULT"])["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
            "POLICY": "Preserved verbatim; no historical disposition is promoted",
        },
        "HISTORICAL_R15": "NOT_VERIFIED",
        "NEW_TASK_R15": "PENDING_TASK_SCOPED_FINAL_LIFECYCLE_AUDIT",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOURCE_SHA256": sha(working_bytes(SOURCE)),
        "TEST_SHA256": sha(working_bytes(TEST)),
    }


def verify_result(candidate: Mapping[str, object]) -> None:
    route_b = obj(candidate["ROUTE_B"])
    validate_route_authority(integer(route_b["A_MAX"]), route_b["S5_AUTHORITY"])
    require(render(candidate) == render(compute_result()), "deterministic source/result mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    value = compute_result()
    raw = render(value)
    path = ROOT / RESULT
    if args.write_result:
        with path.open("xb") as stream:
            stream.write(raw)
    else:
        require(path.is_file() and path.read_bytes() == raw, "deterministic result file differs")
    print(
        json.dumps(
            {
                "PROFILE": PROFILE,
                "T_CAP": value["T237_UNIVERSAL_CAP"],
                "FULL_PROFILE_BOUND": value["NEW_FULL_PROFILE_BOUND"],
                "FAMILY_BOUND": obj(value["FAMILY_REPLAY"])["FINAL_FAMILY_BOUND"],
                "RESULT_SHA256": sha(raw),
            },
            sort_keys=True,
        )
    )
