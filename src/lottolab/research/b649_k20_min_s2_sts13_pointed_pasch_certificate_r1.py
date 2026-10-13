"""Pointed STS(13) certificate for the minimum-S2 profile at t=270.

Domain: twenty six-label tickets on 49 labels, with 22 triple supports and
27 pair supports, partitioning distinct ticket pairs. E_j is the official
any-prize event: at least three hits among the seven selected labels.
An outcome is (D,s), |D|=6, s not in D. Each seven-set D union {s} has seven
special choices. Si=sum_{|Q|=i}|intersection E_j|=sum_outcomes C(r,i).
Projected external triples become pair/singleton labels; they are retained.

Structure (universal, not inferred from the witness). g_v=6+d_v gives
g=(11^12,7^6,6^2), W=sum C(g_v,2)=816 and OW=W-3t=6.
For every edge uv, |N[u] symmetric_difference N[v]| counts open wedges
using that edge, so their sum is 2 OW=12. A high/low edge contributes at
least 11-7=4. If h counts such edges and M missing high/high edges, h=2M,
since all twelve high vertices have degree eleven. Thus h is 0 or 2.
For h=2, M=1 and its nonadjacent high endpoints have ten common high
neighbours, giving ten open wedges, a contradiction. Hence h=0 and the
high component is K12. The remaining degrees force K8 minus the edge
between the two degree-six vertices. It has two disjoint triple supports.
The high component has 60 triple incidences, hence twenty linear triples.
Every high vertex has eleven incident edges, ten covered by its five
triples. The six uncovered edges consequently form a perfect matching.

Unique completion/converse. Introduce infinity and put a block on infinity
and each uncovered matching edge. Every old/new pair is covered once.
Any completion retaining the twenty blocks must cover each uncovered old
pair in a block through infinity, forcing precisely these six blocks.
Conversely an STS(13) has 26 blocks, degree six and 78 pairs. Deleting any
point removes its six blocks, leaving twenty blocks of degree five and
the matching of their old pairs. Thus every legal t=270 presentation is
a point deletion; arbitrary ticket/label permutations preserve events.
All partitions of the six low triple vertices into two triples are
equivalent by low-vertex permutation. No further realization is excluded.

Classification authority: Archdeacon, Dinitz, Stinson, Representing graphs
in Steiner triple systems, Australas. J. Combin. 67(2) (2017), pp.243-258,
p.247, https://ajc.maths.uq.edu.au/pdf/67/ajc_v67_p243.pdf . The published
theorem supplies exactly TWO isomorphism classes; this is not a new census.
We reconstruct the cyclic translates of 014 and 028, and the second design
using the published pair-preserving four-block trade. Both pair partitions
are checked. Every one of their thirteen point deletions is counted.
P is the number of Pasch six-sets in the DELETED design, not the complete
design count. Independent block-quadruple/six-set counts agree. A linear
packing on six points has at most four triples; equality forces degree two
at all six points and is a Pasch. Thus a six-set supports exactly one
four-block Pasch, with no ordering multiplicity. The two complete designs
have different Pasch counts, certifying that their classes are distinct.
Their pointed distributions are 13 times 7 and 9 times 4 plus 4 times 5.
Published exhaustiveness, the bijective completion, and all pointed
deletions therefore prove P>=4 for EVERY legal presentation.

Moments. An outcome with m winners selects three hit labels from each.
Those triples use 3m distinct label pairs by ticket pair-linearity;
therefore C(q,2)>=3m. Label supports cannot span components. The minima
for every mixed split of 4..7 winners sum to more than seven: mixed
intersections vanish. Exact local label-selection DP verifies all K4
weights (no triple:679; one:448), K4-e weight112, K5 weights (0,7,28),
K5-e weights (0,7), and every four-triple six-point packing weight7.
There are 550 K4s, 190 containing a triple, and 15 diamonds:
S4=679*(550-190)+448*190+112*15=331240.
K12 five-sets have triple counts (192,480,120), from twelve degree-five
vertices and twenty blocks; K8-e adds 18 complete and two missing-edge
five-sets containing one triple. Thus S5=7*(480+18+2)+28*120=6860.
For six winners, seven labels give at most 14+b hits with b contained
triples. Since b<=4, eighteen hits force a Pasch; exactly its four triple
and three residual pair labels work, giving seven special choices:
S6=7P. The near clique has b<=2, so cannot contribute.
For seven winners all seven labels must be triple supports, a Fano
subsystem. Its seven vertices would each need two further triples,
each with two of the other five high vertices. Fourteen distinct outside
pairs cannot fit into C(5,2)=10: S7=0. The near clique also fails the
incidence bound. Globally r<=C(7,2)/3=7, so inclusion-exclusion stops.
Consequently Union=S1-S2+S3-S4+S5-S6+S7=313263916-7P<=313263888.

The immutable base is consumed as sealed authority, without executing
its R25/R30, census, or solver code. The base STS13 terms are reconstructed
and digest-matched; only t=270's bound changes. All 248 lower-t terms,
every other resolved certificate, and the entire frontier are retained.
The complete family remains above the incumbent; this certifies ONLY STS13.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

type Support = tuple[int, ...]
type Pair = tuple[int, int]
type Term = tuple[int, int, int, int, int, int]

TASK_ID = "B649_K20_MIN_S2_STS13_POINTED_PASCH_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-sts13-pointed-pasch-certificate-r1"
BASE_HEAD = "a1e5dd3cc32a07f6f5c6e70482578aeb6c950aaf"
BASE_TREE = "a7624329868107f3d77e5bcb91ab9da8cdd5ecc4"
BASE_RESULT_SHA256 = "6a41df1dd018706894d3ea6dba0d22c55d5f5f62239504f93cdc820c2359c622"
PROFILE = "55555555555511111100"
CAP = 270
INCUMBENT = 313263888
OLD_BOUND = 313263916
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIRECTORY = "docs/research/matrix-native-results"
BASE_FILENAME = "b649-k20-min-s2-all-resolved-cursor-refinement-r1-result.json"
RESULT_FILENAME = "b649-k20-min-s2-sts13-pointed-pasch-certificate-r1-result.json"
RESULT_PATH = ROOT / RESULT_DIRECTORY / RESULT_FILENAME
CLASSIFICATION_URL = "https://ajc.maths.uq.edu.au/pdf/67/ajc_v67_p243.pdf"
TRADE_OLD = ((2, 3, 6), (2, 4, 10), (3, 4, 7), (6, 7, 10))
TRADE_NEW = ((2, 3, 4), (2, 6, 10), (3, 6, 7), (4, 7, 10))


def integer(value: object) -> int:
    if type(value) is not int:
        raise AssertionError("expected an exact integer")
    return value


def object_row(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("expected a string-keyed object")
    mapping = cast(dict[object, object], value)
    if any(not isinstance(k, str) for k in mapping):
        raise AssertionError("expected a string-keyed object")
    return cast(dict[str, object], value)


def rows(value: object) -> list[object]:
    if not isinstance(value, list):
        raise AssertionError("expected a list")
    return cast(list[object], value)


def digest(value: object) -> str:
    """The exact canonical hash encoding used by the sealed base."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def pinned_file(relative: str, expected: str) -> bytes:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise AssertionError("invalid immutable input path")
    blob = git("show", f"{BASE_HEAD}:{relative}")
    if hashlib.sha256(blob).hexdigest() != expected:
        raise AssertionError(f"immutable digest mismatch: {relative}")
    if (ROOT / path).read_bytes() != blob:
        raise AssertionError(f"immutable source/result bytes differ: {relative}")
    return blob


@dataclass(frozen=True)
class Authority:
    sealed: dict[str, object]
    provenance: dict[str, str]


@cache
def load_authority() -> Authority:
    if git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("immutable base tree mismatch")
    relative = f"{RESULT_DIRECTORY}/{BASE_FILENAME}"
    sealed = object_row(json.loads(pinned_file(relative, BASE_RESULT_SHA256)))
    provenance = {relative: BASE_RESULT_SHA256}
    source = "src/lottolab/research/b649_k20_min_s2_all_resolved_cursor_refinement_r1.py"
    expected = sealed["SOURCE_SHA256"]
    if not isinstance(expected, str):
        raise AssertionError("missing immutable base source digest")
    pinned_file(source, expected)
    provenance[source] = expected
    for key in ("MODULE_PROVENANCE", "RESULT_PROVENANCE"):
        for path, raw in object_row(sealed[key]).items():
            if not isinstance(raw, str):
                raise AssertionError("invalid immutable provenance digest")
            pinned_file(path, raw)
            provenance[path] = raw
    return Authority(sealed, dict(sorted(provenance.items())))


def edges_of(blocks: Sequence[Support]) -> set[Pair]:
    return {pair for block in blocks for pair in combinations(block, 2)}


def validate_blocks(blocks: Sequence[Support], points: Sequence[int], degree: int) -> None:
    if len(set(points)) != len(points) or len(set(blocks)) != len(blocks):
        raise ValueError("duplicate points or blocks")
    universe = set(points)
    if any(len(b) != 3 or b != tuple(sorted(set(b))) or not set(b) <= universe for b in blocks):
        raise ValueError("invalid triple block")
    pairs = [e for b in blocks for e in combinations(b, 2)]
    if len(set(pairs)) != len(pairs):
        raise ValueError("blocks must be pair-linear")
    if any(sum(v in b for b in blocks) != degree for v in points):
        raise ValueError("incorrect point replication")


def validate_sts(blocks: Sequence[Support]) -> None:
    validate_blocks(blocks, tuple(range(13)), 6)
    if len(blocks) != 26 or edges_of(blocks) != set(combinations(range(13), 2)):
        raise ValueError("not an STS(13) pair partition")


def representatives() -> dict[str, tuple[Support, ...]]:
    cyclic = tuple(
        sorted(
            {
                tuple(sorted((v + s) % 13 for v in b))
                for b in ((0, 1, 4), (0, 2, 8))
                for s in range(13)
            }
        )
    )
    validate_sts(cyclic)
    if not set(TRADE_OLD) <= set(cyclic) or edges_of(TRADE_OLD) != edges_of(TRADE_NEW):
        raise AssertionError("published Pasch trade is not pair-preserving")
    noncyclic = tuple(sorted((set(cyclic) - set(TRADE_OLD)) | set(TRADE_NEW)))
    validate_sts(noncyclic)
    return {"CYCLIC": cyclic, "NON_CYCLIC": noncyclic}


def delete_point(blocks: Sequence[Support], point: int) -> tuple[Support, ...]:
    validate_sts(blocks)
    if point not in range(13):
        raise ValueError("point outside STS(13)")
    remaining = [v for v in range(13) if v != point]
    relabel = {v: i for i, v in enumerate(remaining)}
    core = tuple(sorted(tuple(relabel[v] for v in b) for b in blocks if point not in b))
    validate_blocks(core, tuple(range(12)), 5)
    if len(core) != 20 or sum(point in b for b in blocks) != 6:
        raise AssertionError("point deletion count failed")
    return core


def complete_deleted(core: Sequence[Support]) -> tuple[tuple[Support, ...], tuple[Pair, ...]]:
    validate_blocks(core, tuple(range(12)), 5)
    if len(core) != 20:
        raise ValueError("completion requires twenty blocks")
    matching = tuple(sorted(set(combinations(range(12), 2)) - edges_of(core)))
    if len(matching) != 6 or any(sum(v in e for e in matching) != 1 for v in range(12)):
        raise AssertionError("uncovered edges are not a perfect matching")
    complete = tuple(sorted((*core, *(tuple((*e, 12)) for e in matching))))
    validate_sts(complete)
    return complete, matching


def structural_proof() -> dict[str, object]:
    d = tuple(map(int, PROFILE))
    g = tuple(6 + v for v in d)
    w, ow = sum(comb(v, 2) for v in g), sum(comb(v, 2) for v in g) - 3 * CAP
    table: list[list[int]] = []
    universe = tuple(combinations(range(3), 2))
    for mask in range(8):
        edges = {e for i, e in enumerate(universe) if mask & (1 << i)}
        closed = [{v} | {u for u in range(3) if tuple(sorted((u, v))) in edges} for v in range(3)]
        local_ow = sum(
            a in closed[v] and b in closed[v] and (a, b) not in edges
            for v in range(3)
            for a, b in combinations([u for u in range(3) if u != v], 2)
        )
        differences = sum(len(closed[u] ^ closed[v]) for u, v in edges)
        if differences != 2 * local_ow:
            raise AssertionError("edge/open-wedge incidence identity failed")
        table.append([mask, local_ow, differences])
    crossing_max = 2 * ow // (max(g) - max(g[12:]))
    crossing_candidates = list(range(0, crossing_max + 1, 2))
    rejected = [[h, h // 2, 12 - 2] for h in crossing_candidates if h]
    if (w, ow, crossing_candidates) != (816, 6, [0, 2]) or any(r[2] <= ow for r in rejected):
        raise AssertionError("high-component isolation proof failed")
    if comb(12, 3) + comb(8, 3) - 6 != CAP:
        raise AssertionError("isolated graph triangle count failed")
    return {
        "STATUS": "PROVED_UNIVERSAL_UNIQUE_COMPLETION_AND_CONVERSE",
        "D": d,
        "G": g,
        "W": w,
        "T": CAP,
        "W_MINUS_3T": ow,
        "EDGE_OPEN_WEDGE_IDENTITY": "sum_edges |N[u] xor N[v]| = 2*(W-3t)",
        "LOCAL_IDENTITY_TABLE": table,
        "HIGH_LOW_EDGE_MIN_DIFFERENCE": 4,
        "HIGH_LOW_EDGE_MAX": crossing_max,
        "EVEN_CROSSING_CANDIDATES": crossing_candidates,
        "REJECTED_H_M_OW_LOWER_BOUND": rejected,
        "GRAPH": "K12 disjoint union (K8-e)",
        "HIGH_TRIPLE_INCIDENCES": sum(d[:12]),
        "HIGH_TRIPLE_COUNT": sum(d[:12]) // 3,
        "UNCOVERED_HIGH_DEGREE": 11 - 2 * 5,
        "MATCHING_EDGE_COUNT": 6,
        "COMPLETION_NEW_POINT_COUNT": 1,
        "COMPLETION_FORCED_BLOCK_COUNT": 6,
        "CONVERSE_DELETED_BLOCK_COUNT": 6,
        "RELABEL_INVARIANCE": "ticket and label bijections preserve every event and moment",
        "LOW_COMPONENT_COVERAGE": "all two-triple partitions are equivalent by vertex bijection",
    }


@dataclass(frozen=True)
class Pasch:
    points: Support
    blocks: tuple[Support, ...]


def pasches(blocks: Sequence[Support], points: Sequence[int]) -> tuple[Pasch, ...]:
    """Count both ways; the six-set key removes all configuration multiplicity."""
    by_points: dict[Support, tuple[Support, ...]] = {}
    for q in combinations(points, 6):
        inside = tuple(sorted(b for b in blocks if set(b) <= set(q)))
        if len(inside) == 4:
            if any(sum(v in b for b in inside) != 2 for v in q):
                raise AssertionError("four-triple six-set is not a Pasch")
            by_points[q] = inside
    by_blocks: dict[Support, tuple[Support, ...]] = {}
    for four in combinations(sorted(blocks), 4):
        incidence = Counter(v for b in four for v in b)
        if len(incidence) == 6 and set(incidence.values()) == {2}:
            q = tuple(sorted(incidence))
            if q in by_blocks:
                raise AssertionError("Pasch six-set counted more than once")
            by_blocks[q] = four
    if by_points != by_blocks:
        raise AssertionError("independent Pasch counts differ")
    return tuple(Pasch(q, bs) for q, bs in sorted(by_points.items()))


def local_profile(n: int, edges: set[Pair], triples: Sequence[Support]) -> tuple[int, ...]:
    """Exact projection of all 49 labels, including partial external supports."""
    if not 1 <= n <= 7 or not edges <= set(combinations(range(n), 2)):
        raise ValueError("invalid induced graph")
    remaining = set(edges)
    masks: list[int] = []
    for block in triples:
        if len(block) != 3 or block != tuple(sorted(set(block))):
            raise ValueError("invalid contained triple")
        shadow = set(combinations(block, 2))
        if not shadow <= remaining:
            raise ValueError("nonlinear or unsupported triple")
        remaining -= shadow
        masks.append(sum(1 << v for v in block))
    masks.extend(sum(1 << v for v in pair) for pair in sorted(remaining))
    for v in range(n):
        used = sum(bool(m & (1 << v)) for m in masks)
        if used > 6:
            raise ValueError("ticket capacity exceeded")
        masks.extend([1 << v] * (6 - used))
    if len(masks) > 49:
        raise ValueError("pool capacity exceeded")
    counts = Counter(masks)
    counts[0] = 49 - len(masks)
    return tuple(counts[m] for m in range(1 << n))


@cache
def intersection_count(profile: tuple[int, ...]) -> int:
    """Select seven labels by mask multiplicities; do not enumerate outcomes."""
    n = len(profile).bit_length() - 1
    if not 1 <= n <= 7 or len(profile) != 1 << n:
        raise ValueError("invalid intersection dimension")
    if any(type(c) is not int or c < 0 for c in profile) or sum(profile) != 49:
        raise ValueError("invalid projected label counts")
    if any(c and m.bit_count() > 3 for m, c in enumerate(profile)):
        raise ValueError("support size exceeds three")
    if any(sum(c for m, c in enumerate(profile) if m & (1 << v)) != 6 for v in range(n)):
        raise ValueError("ticket capacity must be six")
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, (0,) * n): 1}
    for mask in sorted(range(len(profile)), key=int.bit_count, reverse=True):
        count = profile[mask]
        if not count:
            continue
        following: dict[tuple[int, tuple[int, ...]], int] = {}
        for (used, hits), ways in states.items():
            for take in range(min(count, 7 - used) + 1):
                new_hits = tuple(
                    min(3, h + take * bool(mask & (1 << v))) for v, h in enumerate(hits)
                )
                if sum(3 - h for h in new_hits) > 3 * (7 - used - take):
                    continue
                key = (used + take, new_hits)
                following[key] = following.get(key, 0) + ways * comb(count, take)
        states = following
    return 7 * states.get((7, (3,) * n), 0)


def linear_packings(n: int) -> tuple[tuple[Support, ...], ...]:
    """Only bounded local packings, not a census of designs or portfolios."""
    if n not in (4, 5, 6):
        raise ValueError("local scope must be four, five or six points")
    candidates = tuple(combinations(range(n), 3))
    return tuple(
        p
        for b in range(n * ((n - 1) // 2) // 3 + 1)
        for p in combinations(candidates, b)
        if len(edges_of(p)) == 3 * b
    )


@cache
def moment_identity_proof() -> dict[str, object]:
    table: list[list[int]] = []
    for n, weights in ((4, (679, 448)), (5, (0, 7, 28)), (6, (0, 0, 0, 0, 7))):
        for packing in linear_packings(n):
            value = intersection_count(local_profile(n, set(combinations(range(n), 2)), packing))
            if value != weights[len(packing)]:
                raise AssertionError("exact local event weight failed")
            table.append([n, len(packing), value])
    for n, packing, expected in ((4, (), 112), (5, (), 0), (5, ((2, 3, 4),), 7)):
        edges = set(combinations(range(n), 2)) - {(0, 1)}
        value = intersection_count(local_profile(n, edges, packing))
        if value != expected:
            raise AssertionError("near-clique event weight failed")
        table.append([-n, len(packing), value])
    minima = [0] + [next(q for q in range(3, 8) if comb(q, 2) >= 3 * m) for m in range(1, 7)]
    mixed = [[k, j, minima[j] + minima[k - j]] for k in range(4, 8) for j in range(1, k)]
    if any(r[2] <= 7 for r in mixed):
        raise AssertionError("mixed-component intersection exclusion failed")
    n2 = 12 * comb(5, 2)
    n1 = 20 * comb(9, 2) - 2 * n2
    n0 = comb(12, 5) - n1 - n2
    s4 = 679 * (550 - 190) + 448 * 190 + 112 * 15
    s5 = 7 * (n1 + 18 + 2) + 28 * n2
    pointwise: list[list[int]] = []
    for r in range(8):
        value = sum((-1) ** (i + 1) * comb(r, i) for i in range(1, 8))
        if value != int(r > 0):
            raise AssertionError("exact inclusion-exclusion failed")
        pointwise.append([r, value])
    if (s4, s5, n0, n1, n2) != (331240, 6860, 192, 480, 120):
        raise AssertionError("universal S4/S5 arithmetic failed")
    if comb(12 - 7, 2) >= 7 * (5 - 3):
        raise AssertionError("Fano subsystem exclusion failed")
    return {
        "STATUS": "PROVED_UNIVERSAL_ALL_LEGAL_T270_PRESENTATIONS",
        "EVENT": "E_j = {|ticket_j intersection (D union {s})| >= 3}, |D|=6, s not in D",
        "S_DEFINITION": "Si = sum_{|Q|=i}|intersection_{j in Q} E_j| = sum_outcomes C(r,i)",
        "OFFICIAL_OUTCOMES_PER_SEVEN_SET": 7,
        "R_CAP": comb(7, 2) // comb(3, 2),
        "LOCAL_WEIGHT_TABLE": table,
        "LOCAL_WEIGHT_TABLE_SHA256": digest(table),
        "LOCAL_PACKING_COUNTS": {str(n): len(linear_packings(n)) for n in (4, 5, 6)},
        "MIXED_COMPONENT_MIN_SELECTED_LABELS": mixed,
        "K4_COUNT": 550,
        "CONTAINED_TRIPLE_K4_COUNT": 190,
        "DIAMOND_COUNT": 15,
        "K12_FIVE_SET_COUNTS_0_1_2": [n0, n1, n2],
        "NEAR_COMPLETE_FIVE_SET_COUNTS_0_1": [18, 18],
        "NEAR_MISSING_FIVE_SET_COUNTS_0_1": [18, 2],
        "S4": s4,
        "S5": s5,
        "S6": "7*P",
        "S7": 0,
        "SIX_WINNER_REQUIRED_HITS": 18,
        "SIX_WINNER_HIT_CAP": "14+b, b<=4",
        "FANO_REQUIRED_CROSSING_TRIPLES": 14,
        "FANO_AVAILABLE_OUTSIDE_PAIRS": 10,
        "EXACT_INCLUSION_EXCLUSION_TABLE": pointwise,
        "PASCH_MULTIPLICITY": "one six-set = one unordered four-block configuration",
    }


def first_three_moments() -> tuple[int, int, int]:
    single = intersection_count(local_profile(1, set(), ()))
    disjoint = intersection_count(local_profile(2, set(), ()))
    shared = intersection_count(local_profile(2, {(0, 1)}, ()))
    wedge = intersection_count(local_profile(3, {(0, 1), (0, 2)}, ()))
    triangle = intersection_count(local_profile(3, set(combinations(range(3), 2)), ()))
    common = intersection_count(local_profile(3, set(combinations(range(3), 2)), ((0, 1, 2),)))
    if (wedge, triangle, common) != (2800, 20272, 7000):
        raise AssertionError("exact S3 event weights failed")
    s1 = 20 * single
    s2 = 93 * shared + (comb(20, 2) - 93) * disjoint
    s3 = wedge * (816 - 3 * CAP) + triangle * (CAP - 22) + common * 22
    if (s1, s2, s3) != (372228640, 63838600, 5198256):
        raise AssertionError("exact S1/S2/S3 identity failed")
    return s1, s2, s3


def realization(core: Sequence[Support]) -> tuple[tuple[Support, ...], tuple[Pair, ...]]:
    complete_deleted(core)
    triples = tuple((*core, (12, 13, 14), (15, 16, 17)))
    graph = set(combinations(range(12), 2)) | (set(combinations(range(12, 20), 2)) - {(18, 19)})
    pairs = tuple(sorted(graph - edges_of(triples)))
    return triples, pairs


def tickets_from_supports(triples: Sequence[Support], pairs: Sequence[Pair]) -> tuple[Support, ...]:
    supports = tuple((*triples, *pairs))
    if len(triples) != 22 or len(pairs) != 27 or len(set(supports)) != 49:
        raise ValueError("expected 22 triple and 27 pair supports")
    if any(len(s) != 3 for s in triples) or any(len(s) != 2 for s in pairs):
        raise ValueError("incorrect support sizes")
    shadow = [e for s in supports for e in combinations(s, 2)]
    if len(shadow) != len(set(shadow)):
        raise ValueError("ticket pairs must be linear")
    if any(s != tuple(sorted(set(s))) or not set(s) <= set(range(20)) for s in supports):
        raise ValueError("invalid ticket support")
    tickets = tuple(tuple(i for i, s in enumerate(supports, 1) if v in s) for v in range(20))
    if len(set(tickets)) != 20 or any(len(t) != 6 for t in tickets):
        raise ValueError("expected twenty distinct six-label tickets")
    if set().union(*(set(t) for t in tickets)) != set(range(1, 50)):
        raise ValueError("expected all 49 labels")
    return tickets


def exact_moments(triples: Sequence[Support], pairs: Sequence[Pair]) -> dict[str, object]:
    tickets_from_supports(triples, pairs)
    d = tuple(sum(v in b for b in triples) for v in range(20))
    if "".join(map(str, sorted(d, reverse=True))) != PROFILE:
        raise ValueError("wrong STS13 profile")
    order = sorted(range(20), key=lambda v: (-d[v], v))
    relabel = {v: i for i, v in enumerate(order)}
    triples = tuple(tuple(sorted(relabel[v] for v in b)) for b in triples)
    pairs = tuple(
        sorted((min(relabel[a], relabel[b]), max(relabel[a], relabel[b])) for a, b in pairs)
    )
    graph = edges_of(triples) | set(pairs)
    expected = set(combinations(range(12), 2)) | (set(combinations(range(12, 20), 2)) - {(18, 19)})
    if graph != expected:
        raise ValueError("not the isolated overlap graph")
    if (
        sum(
            set(q) <= graph for q in (set(combinations(vs, 2)) for vs in combinations(range(20), 3))
        )
        != CAP
    ):
        raise AssertionError("realization triangle count failed")
    core = tuple(b for b in triples if set(b) <= set(range(12)))
    complete_deleted(core)
    proof = moment_identity_proof()
    histograms: dict[str, dict[str, int]] = {}
    values: dict[int, int] = {}
    for n, weight in (
        (4, {(0, 0): 679, (0, 1): 448, (1, 0): 112}),
        (5, {(0, 0): 0, (0, 1): 7, (0, 2): 28, (1, 0): 0, (1, 1): 7}),
    ):
        histogram: Counter[tuple[int, int]] = Counter()
        for component in (range(12), range(12, 20)):
            for q in combinations(component, n):
                missing = int(18 in q and 19 in q)
                contained = sum(set(b) <= set(q) for b in triples)
                histogram[missing, contained] += 1
        if not set(histogram) <= set(weight):
            raise AssertionError("unsupported local component presentation")
        values[n] = sum(count * weight[key] for key, count in histogram.items())
        histograms[str(n)] = {f"{m},{b}": count for (m, b), count in sorted(histogram.items())}
    configs = pasches(core, tuple(range(12)))
    if any(sum(set(b) <= set(q) for b in core) >= 7 for q in combinations(range(12), 7)):
        raise AssertionError("illegal Fano subsystem")
    s1, s2, s3 = first_three_moments()
    s4, s5, s6, s7 = values[4], values[5], 7 * len(configs), 0
    if (s4, s5) != (proof["S4"], proof["S5"]):
        raise AssertionError("realized S4/S5 differ from universal identities")
    union = s1 - s2 + s3 - s4 + s5 - s6 + s7
    if union != OLD_BOUND - 7 * len(configs):
        raise AssertionError("exact union identity failed")
    return {
        "S1": s1,
        "S2": s2,
        "S3": s3,
        "S4": s4,
        "S5": s5,
        "S6": s6,
        "S7": s7,
        "P": len(configs),
        "PASCH_SIX_SETS": [p.points for p in configs],
        "PASCH_BLOCKS": [p.blocks for p in configs],
        "LOCAL_HISTOGRAMS": histograms,
        "EXACT_UNION": union,
    }


def pointed_deletions() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for name, blocks in representatives().items():
        for point in range(13):
            core = delete_point(blocks, point)
            complete, matching = complete_deleted(core)
            remaining = [v for v in range(13) if v != point]
            relabel = {v: i for i, v in enumerate((*remaining, point))}
            expected = tuple(sorted(tuple(sorted(relabel[v] for v in b)) for b in blocks))
            if complete != expected:
                raise AssertionError("unique completion does not recover deleted design")
            moments = exact_moments(*realization(core))
            records.append(
                {
                    "CLASS": name,
                    "DELETED_POINT": point,
                    "CORE_BLOCKS": core,
                    "DELETED_BLOCK_COUNT": 6,
                    "CORE_BLOCK_COUNT": len(core),
                    "UNCOVERED_MATCHING": matching,
                    "UNIQUE_COMPLETION_SHA256": digest(complete),
                    "STRUCTURAL_CLASS_STATUS": "PASS",
                    **moments,
                }
            )
    return records


def validate_pointed_coverage(records: Sequence[Mapping[str, object]]) -> int:
    keys = [(r["CLASS"], integer(r["DELETED_POINT"])) for r in records]
    expected = {(name, point) for name in ("CYCLIC", "NON_CYCLIC") for point in range(13)}
    if len(keys) != 26 or len(set(keys)) != 26 or set(keys) != expected:
        raise AssertionError("incomplete pointed deletion coverage")
    distributions = {
        name: Counter(integer(r["P"]) for r in records if r["CLASS"] == name)
        for name in ("CYCLIC", "NON_CYCLIC")
    }
    if distributions != {"CYCLIC": Counter({7: 13}), "NON_CYCLIC": Counter({4: 9, 5: 4})}:
        raise AssertionError("incorrect pointed Pasch counts")
    for record in records:
        p = integer(record["P"])
        if (record["S4"], record["S5"], record["S6"], record["S7"]) != (331240, 6860, 7 * p, 0):
            raise AssertionError("incorrect pointed moment identity")
        if record["EXACT_UNION"] != OLD_BOUND - 7 * p:
            raise AssertionError("incorrect pointed union identity")
    return min(integer(r["P"]) for r in records)


def reconstruct_incumbent(auth: Authority) -> dict[str, object]:
    """Rebuild the sealed support witness without invoking predecessor helpers."""
    sts = tuple(
        tuple(sorted((v + shift) % 13 for v in block))
        for block in ((0, 1, 4), (0, 2, 7))
        for shift in range(13)
    )
    validate_sts(sts)
    core = tuple(tuple(v - 1 for v in b) for b in sts if 0 not in b)
    q = {0, 1, 2, 4, 7, 9}
    old = {b for b in core if set(b) <= q}
    shadow = edges_of(tuple(old))
    new = {b for b in combinations(sorted(q), 3) if set(combinations(b, 2)) <= shadow} - old
    if len(old) != 4 or len(new) != 4 or edges_of(tuple(new)) != shadow:
        raise AssertionError("incumbent Pasch trade is invalid")
    triples, pairs = realization(tuple(sorted((set(core) - old) | new)))
    triples = tuple(sorted(triples))
    tickets = tickets_from_supports(triples, pairs)
    sealed = object_row(object_row(auth.sealed["WITNESS_SOUNDNESS"])["TRADED_STS13_EXACT_UNION"])
    moments = exact_moments(triples, pairs)
    supports_hash = digest([triples, pairs])
    if supports_hash != sealed["SUPPORTS_SHA256"]:
        raise AssertionError("sealed incumbent support identity differs")
    for key in ("S5", "S6", "S7", "PASCH_SIX_SETS"):
        if digest(moments[key]) != digest(sealed[key]):
            raise AssertionError("sealed incumbent moment/configuration differs")
    if (
        moments["EXACT_UNION"] != sealed["EXACT_ANY_PRIZE_UNION"]
        or moments["EXACT_UNION"] != INCUMBENT
    ):
        raise AssertionError("legal incumbent exact union differs")
    frequencies = Counter(label for ticket in tickets for label in ticket)
    if Counter(frequencies.values()) != Counter({3: 22, 2: 27}):
        raise AssertionError("incumbent label frequencies differ")
    return {
        "STATUS": "PASS_INDEPENDENTLY_RECONSTRUCTED_SEALED_LEGAL_WITNESS",
        "TICKETS": tickets,
        "TICKET_COUNT": len(tickets),
        "LABEL_COUNT": len(frequencies),
        "TRIPLE_SUPPORTS": triples,
        "PAIR_SUPPORTS": pairs,
        "TRIPLE_SUPPORT_COUNT": len(triples),
        "PAIR_SUPPORT_COUNT": len(pairs),
        "SUPPORTS_SHA256": supports_hash,
        **moments,
    }


def profile_certificate(auth: Authority, p_min: int) -> dict[str, object]:
    base = auth.sealed
    cert = object_row(object_row(base["RESOLVED_CERTIFICATES"])[PROFILE])
    special = object_row(object_row(base["SPECIAL_PER_T_CERTIFICATES"])[PROFILE])
    if (
        cert["PROFILE_ID"],
        cert["T_RANGE"],
        cert["CERTIFIED_PROFILE_BOUND"],
        object_row(cert["CAP_AUTHORITY"])["TRIANGLE_CAP"],
        special["LOAD_BEARING_T"],
    ) != (PROFILE, [22, CAP], OLD_BOUND, CAP, CAP):
        raise AssertionError("sealed STS13 profile/t authority differs")
    old: list[Term] = []
    for raw in rows(special["ALL_T_TERMS"]):
        fields = tuple(integer(x) for x in rows(raw))
        if len(fields) != 6:
            raise AssertionError("incorrect sealed term shape")
        old.append(fields)
    if digest(old) != cert["AUTHORITATIVE_TERMS_SHA256"]:
        raise AssertionError("sealed authoritative terms differ")
    g = [6 + int(v) for v in PROFILE]
    j = sum(comb(v, 3) for v in g)
    for t, _b, k, a, s4, s3 in old:
        if s3 != 2800 * 816 + 11872 * (t - 22) - 30800:
            raise AssertionError("sealed term S3 identity differs")
        if t != CAP:
            k_min = max(0, -(-(j - 9 * (816 - 3 * t)) // 4))
            a_max = min(k_min, 190)
            if (k, a, s4) != (k_min, a_max, max(112, 448 * a_max + 679 * (k_min - a_max))):
                raise AssertionError("special S4 leaked outside t270")
        elif (k, a, s4) != (550, 190, 331240):
            raise AssertionError("sealed t270 S4 identity differs")
    terms = [
        (t, min(b, 372228640 - 63838600 + s3 - s4 + 6860), k, a, s4, s3)
        for t, b, k, a, s4, s3 in old
    ]
    if (
        [r[0] for r in terms] != list(range(22, CAP + 1))
        or digest(terms) != cert["ALL_T_TERMS_SHA256"]
        or max(r[1] for r in terms) != OLD_BOUND
    ):
        raise AssertionError("sealed base STS13 envelope differs")
    bound = OLD_BOUND - 7 * p_min
    new = [(t, bound if t == CAP else b, k, a, s4, s3) for t, b, k, a, s4, s3 in terms]
    validate_term_scope(terms, new, bound)
    return {
        "PROFILE_ID": PROFILE,
        "LOAD_BEARING_T": CAP,
        "CAP_AUTHORITY": cert["CAP_AUTHORITY"],
        "OLD_PROFILE_BOUND": OLD_BOUND,
        "NEW_T270_BOUND": bound,
        "CERTIFIED_PROFILE_BOUND": max(r[1] for r in new),
        "BASE_TERMS_SHA256": digest(terms),
        "ALL_T_TERMS": new,
        "ALL_T_TERMS_SHA256": digest(new),
        "RETAINED_LOWER_T_COUNT": len(new) - 1,
        "RETAINED_LOWER_T_MAX": max(r[1] for r in new[:-1]),
        "RETAINED_LOWER_T_SHA256": digest(new[:-1]),
        "OTHER_T_PRESERVATION": "PASS_ALL_248_TERMS_BYTE_EQUIVALENT_CANONICAL_JSON",
    }


def validate_term_scope(old: Sequence[Term], new: Sequence[Term], bound: int) -> None:
    if len(old) != 249 or len(new) != 249 or [r[0] for r in new] != list(range(22, 271)):
        raise AssertionError("incomplete legal t envelope")
    if new[:-1] != old[:-1] or new[-1][0] != CAP or new[-1][2:] != old[-1][2:]:
        raise AssertionError("t270 certificate misplaced t scope")
    if new[-1][1] != bound or max(r[1] for r in new[:-1]) != 313261872:
        raise AssertionError("lower-t maximum or cap bound differs")


def family_certificate(auth: Authority, new_bound: int) -> dict[str, object]:
    base = auth.sealed
    resolved = object_row(base["RESOLVED_CERTIFICATES"])
    frontier = object_row(base["FRONTIER_CERTIFICATES"])
    coverage = object_row(object_row(base["FINAL_FAMILY"])["COVERAGE"])
    if (len(resolved), len(frontier), len(set(resolved) | set(frontier))) != (4647, 197, 4844):
        raise AssertionError("base family coverage is incomplete")
    ids_hash = digest(sorted(set(resolved) | set(frontier), reverse=True))
    if set(resolved) & set(frontier) or ids_hash != coverage["ADMISSIBLE_IDS_SHA256"]:
        raise AssertionError("base family partition digest differs")
    bounds = {
        p: integer(object_row(c)["CERTIFIED_PROFILE_BOUND"])
        for p, c in {**resolved, **frontier}.items()
    }
    before = max(bounds.values())
    if before != base["FINAL_COMPLETE_FAMILY_UB"] or before != 313283936:
        raise AssertionError("sealed base family maximum differs")
    other = {p: c for p, c in resolved.items() if p != PROFILE}
    bounds[PROFILE] = new_bound
    after = max(bounds.values())
    owners = sorted(p for p, b in bounds.items() if b == after)
    if after != 313283936 or owners != ["66555555555540000000"]:
        raise AssertionError("STS13-only family maximum differs")
    return {
        "BASE_COMPLETE_FAMILY_UB": before,
        "COMPLETE_FAMILY_UB_WITH_STS13_ONLY": after,
        "OWNER_IDS": owners,
        "REMAINING_GAP": after - INCUMBENT,
        "PRESERVED_OTHER_RESOLVED_COUNT": len(other),
        "OTHER_CERTIFICATES_SHA256": digest(other),
        "PRESERVED_FRONTIER_COUNT": len(frontier),
        "FRONTIER_CERTIFICATES_SHA256": digest(frontier),
        "FRONTIER_BOUND": max(bounds[p] for p in frontier),
        "PROFILE_COVERAGE": coverage,
        "SCOPE": "only STS13 profile replaced; all other sealed base bounds retained",
        "NEIGHBOR_DEFICIT_CERTIFICATES_INCLUDED": False,
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    structure, moments = structural_proof(), moment_identity_proof()
    records = pointed_deletions()
    p_min = validate_pointed_coverage(records)
    representatives_evidence = {
        name: {
            "BLOCKS": blocks,
            "BLOCK_COUNT": len(blocks),
            "PAIR_COUNT": len(edges_of(blocks)),
            "COMPLETE_DESIGN_PASCH_COUNT": len(pasches(blocks, tuple(range(13)))),
        }
        for name, blocks in representatives().items()
    }
    counts = [integer(r["COMPLETE_DESIGN_PASCH_COUNT"]) for r in representatives_evidence.values()]
    if counts != [13, 8]:
        raise AssertionError("non-isomorphism Pasch invariant failed")
    cert = profile_certificate(auth, p_min)
    bound = integer(cert["CERTIFIED_PROFILE_BOUND"])
    witness = reconstruct_incumbent(auth)
    if p_min != 4 or bound != INCUMBENT or integer(witness["EXACT_UNION"]) > bound:
        raise AssertionError("universal profile bound/witness soundness failed")
    family = family_certificate(auth, bound)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "IMMUTABLE_INPUT_PROVENANCE": auth.provenance,
        "EXACT_SOURCE_IDENTITIES_STATUS": "PASS",
        "PROOF": __doc__,
        "STS13_STRUCTURE_STATUS": structure["STATUS"],
        "STRUCTURE_PROOF": structure,
        "CLASSIFICATION_REFERENCE": {
            "URL": CLASSIFICATION_URL,
            "PAGE": 247,
            "AUTHORITY": "published exactly-two-isomorphism-class theorem",
        },
        "FINITE_CLASSIFICATION_STATUS": "PASS_PUBLISHED_EXHAUSTIVENESS_TWO_RECONSTRUCTED_CLASSES",
        "REPRESENTATIVES": representatives_evidence,
        "POINTED_DELETIONS": records,
        "POINTED_DELETION_COUNT": len(records),
        "PASCH_COUNT_DISTRIBUTION": {"CYCLIC": {"7": 13}, "NON_CYCLIC": {"4": 9, "5": 4}},
        "P_UNIVERSAL_LOWER_BOUND": p_min,
        "S6_S7_IDENTITY_STATUS": "PASS_UNIVERSAL_EXACT_EVENTS",
        "MOMENT_IDENTITY_PROOF": moments,
        "UNION_IDENTITY": "313263916-7P",
        "INCUMBENT_WITNESS": witness,
        "WITNESS_SOUNDNESS_STATUS": witness["STATUS"],
        "OLD_STS13_PROFILE_BOUND": OLD_BOUND,
        "NEW_STS13_PROFILE_BOUND": bound,
        "STS13_PROFILE_BOUND": bound,
        "PROFILE_CERTIFICATE": cert,
        "OTHER_T_PRESERVATION": cert["OTHER_T_PRESERVATION"],
        "BASE_COMPLETE_FAMILY_UB": family["BASE_COMPLETE_FAMILY_UB"],
        "COMPLETE_FAMILY_UB_WITH_STS13_ONLY": family["COMPLETE_FAMILY_UB_WITH_STS13_ONLY"],
        "FAMILY_CERTIFICATE": family,
        "NO_LEGITIMATE_REALIZATION_EXCLUDED": True,
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "NEW_PROFILE_CENSUS_STARTED": "NO",
        "OUTCOME_ENUMERATIONS": 0,
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def verify_result(result: Mapping[str, object], authority: Authority | None = None) -> None:
    if render(result) != render(compute_result(authority)):
        raise AssertionError("tampered pointed STS13 result")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", action="store_true", help="replay the sealed result byte-for-byte"
    )
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if args.verify:
        if RESULT_PATH.read_bytes() != raw:
            raise AssertionError("pointed STS13 result byte replay differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(
        json.dumps(
            {
                "RESULT_REPLAY_STATUS": "PASS" if args.verify else "CREATED",
                "STS13_PROFILE_BOUND": result["STS13_PROFILE_BOUND"],
                "COMPLETE_FAMILY_UB_WITH_STS13_ONLY": result["COMPLETE_FAMILY_UB_WITH_STS13_ONLY"],
                "POINTED_DELETION_COUNT": result["POINTED_DELETION_COUNT"],
            }
        )
    )


if __name__ == "__main__":
    main()
