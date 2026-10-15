"""Exact profile bound for 66655555555411110000, below sealed scalar 313391740.

Support model. Twenty tickets carry six distinct labels. Twenty-two labels have
triple support and twenty-seven have pair support. Pair-linearity makes the
overlap graph G simple: two tickets share at most one label, so
g_v = 6 + d_v, sum d = 66, sum g = 186 and E(G) = 93. The target degree
profile is 6^3, 5^8, 4, 1^4, 0^4. Its wedge count is W = 827 and
J = sum C(g_v, 3) = 2320. The other tied owner 66655555555331100000 has
J = 2318 and is not used. Goodman gives T(G) + T(complement G) = 293.

The sealed family result stores the scalar 313391740 for this profile and does
not pin a T, S4 or S5 certificate for it. The W784 Goodman cap T <= 250 and
S4 >= 112 apply to a different cohort. S5 is not pinned. Numerical equality of
the sealed scalar with the Route-B term at total triangle count 265 is recorded
and is not an authority.

New cap. Partition tickets into HI = {d >= 4} (12 vertices) and LO = {d <= 1}
(8 vertices: four degree-1 tickets and four zeros). For an arbitrary simple
graph and an arbitrary bipartition of the vertex set, the two-shore identity
below is an equality T(G) = F - P with P a sum of four cardinalities, hence
P >= 0 and T(G) <= F. Crossing edges are split into triple-label edges b_v and
pair-label edges q_v. Every legal realization has (b_v, q_v) inside the ranges
proved from pair-linearity, the four LO vertices of positive degree, and
nonnegative complement degrees. Degree-class multisets cover every labelling.
The maximum of F on the 66 feasible (beta, pi) cells is 260, so T(G) <= 260.
The same-triple and different-triple placements of the four degree-1 vertices
are the b_v in {0, 1, 2} choices; they are inside the cell set, not a second
family. No state is asserted realizable. The K/Z four-zero T <= 267 recount is
not re-executed and is not the adopted cap.

Route B on 22 <= T <= 260. Open wedges are W - 3T. Each open wedge at v sits in
at most g_v - 2 neighbour triples, so
K4 >= max(0, ceil((J - (g_max - 2) * open) / 4)). A K4 contains at most one
triple support. The number of those K4s is at most floor(sum d_v (g_v - 2) / 3).
Outcome weights 448 and 679 are the pinned four-ticket table, recomputed by the
R2 dynamic program. S4 is at least 448 * contained + 679 * (K4 - contained),
and at least the pinned global floor 112; the two floors are combined by
maximum. At most seven tickets win on one outcome, and for every multiplicity
r = 0..7 the order-three Bonferroni excess is at least (4/7) C(r, 4). Thus
the union is at most ceil(S1 - S2 + S3 - 4 S4 / 7). S5 is not used. Integer
arithmetic and an independent Fraction ceiling agree on every T. The envelope
is strictly increasing, and its maximum is 313346736 at T = 260.

Family. All 4647 resolved rows and 197 cursor rows are replayed from the
SHA-pinned base. Only this profile's resolved bound is replaced, in memory.
The other owner stays at 313391740, so the family maximum does not move.
Legal attainment and the global K20 optimum stay unknown. No solver is run.

Continuation: the entire original T<=260 certificate is reproduced byte for
byte from PRESERVED_HEAD below. The additional K4 theorem and its two finite
enumerations are independent of that triangle relaxation. Both restrictions
are applied on every T in 22..260; the minimum of the proved envelopes is
adopted. The separate T<=265 envelope and A/B family effects are projections,
not a shared Family Authority update.
"""

from __future__ import annotations

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

type Document = dict[str, object]
type Choice = tuple[int, int]
type Cell = tuple[int, int]
type Term = tuple[int, int, int, int, int, int, int]

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_6665555555541111_EXACT_CERT_R1"
OWNER_CONVERSATION_ID = "01a13d88-713e-7db1-938a-af752ceab40a"
STEM = "b649_min_s2_owner_6665555555541111_exact_cert_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-owner-6665555555541111-exact-cert-r1-result.json"
)
BASE_HEAD = "bee6acaaf9d2781e2aae560138d8be99fb4789ed"
BASE_TREE = "7b382a405d8d734763b477aa88efafeba2e1ed9b"
BASE_RESULT = (
    "docs/research/matrix-native-results/b649-min-s2-w784-39-goodman-exact-authority-r1-result.json"
)
BASE_RESULT_SHA256 = "bca4ad19aebb9808c952259d677a4a07381aa43392c38715c8265427960fe6f6"
TARGET_PROFILE = "66655555555411110000"
OTHER_OWNER = "66655555555331100000"
SEALED_SCALAR_BOUND = 313_391_740
INCUMBENT = 313_263_888
OTHER_OWNER_CHOOSE3 = 2318
S1 = 372_228_640
S2 = 63_838_600
GLOBAL_S4_FLOOR = 112
LIGHT_K4 = 448
HEAVY_K4 = 679
HI_MIN_DEGREE = 4
EVALUATOR_PINS = {
    "b649_k20_min_s2_higher_order_closure_r2.py": (
        "6897c974fe9679f2ec567602522bb4c38c996275368b714c6a7fadedd66d6e45"
    ),
    "b649_k20_min_s2_next_active_profile_exact_bound_r8.py": (
        "8b70fbfa9f3cc3cabe0c48956d92b7f81600c474b4331717695de303855d382a"
    ),
    "b649_k20_min_s2_realizable_core_class_bound_r4.py": (
        "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
    ),
}
INITIAL_INDEX_SHA256 = "b68c0d81a387b8aabad1b86d3ad75f624e957fd174a3af52c5dacec0b7c00a7c"
INITIAL_SHARED_REFS_FINGERPRINT = "f9360c15216a48357e954498140dfe3c7d300d67fa54fe3cdab835bd0cfe02e0"
PRESERVED_HEAD = "26c34f19a68e824ff89bc584b8548a5a4186e69e"
PRESERVED_TREE = "0f39c83405c2bff3cb96b6740c12158490704f8b"
PRESERVED_RESULT_SHA256 = "8eac8d5ee451c1f585046eeece62032a3cdf5471f1bf5a63a1ab81e1db456e8f"
CONTINUATION_OWNER = "01a13e0f-c119-70b0-a49c-2acbfb2bf8bb"
OWNER_A_HEAD = "c4c83e6bfed718db133b69aaec4431e9dcd690ce"
OWNER_A_TREE = "b1339e0a35fb3cf40b06ffc4053ba502fc4c76c4"
OWNER_A_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-owner-666555555553311-exact-cert-r1-result.json"
)
OWNER_A_SHA256 = "7709b51fb56bafb90f6370b7e9add76bee29f558f422764a273f3afe1ce6a5ad"
type LowType = tuple[int, int, int]
type ShadowState = tuple[tuple[int, ...], int, int]
LOW_TYPES: tuple[LowType, ...] = (
    (1, 1, 1),
    (1, 1, 4),
    (1, 1, 5),
    (1, 1, 6),
    (1, 4, 5),
    (1, 4, 6),
    (1, 5, 5),
    (1, 5, 6),
    (1, 6, 6),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    return cast(Document, value)


def ledger(value: object) -> dict[str, int]:
    rows = obj(value)
    require(all(type(bound) is int for bound in rows.values()), "integer bounds required")
    return {str(key): cast(int, bound) for key, bound in rows.items()}


def git(*args: str) -> str:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", "-C", str(ROOT), *args],
        env=env,
        text=True,
    ).strip()


def blob(head: str, path: str, expected_sha: str) -> bytes:
    metadata = git("ls-tree", head, "--", path).split()
    require(len(metadata) == 4 and metadata[:2] == ["100644", "blob"], "unsafe blob mode")
    require(metadata[3] == path, "blob path mismatch")
    payload = subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", "-C", str(ROOT), "cat-file", "blob", metadata[2]],
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    require(sha(payload) == expected_sha, "source hash mismatch")
    return payload


def working_bytes(path: str) -> bytes:
    target = (ROOT / path).resolve()
    require(target.is_file() and not target.is_symlink(), "unsafe working path")
    require(target.is_relative_to(ROOT), "working path escaped the worktree")
    return target.read_bytes()


def profile_degrees(pid: str) -> tuple[int, ...]:
    require(len(pid) == 20 and pid.isdecimal() and set(pid) <= set("0123456"), "profile format")
    require(pid == "".join(sorted(pid, reverse=True)), "profile order")
    degrees = tuple(int(part) for part in pid)
    require(sum(degrees) == 66, "profile degree sum")
    return degrees


def profile_facts(pid: str) -> dict[str, int]:
    """Degree, wedge, Goodman and choose-3 facts. J = 2320 on the target."""

    degrees = profile_degrees(pid)
    graph = tuple(6 + value for value in degrees)
    mixed = sum(value * (19 - value) for value in graph)
    require(mixed % 2 == 0, "Goodman sum is not even")
    return {
        "CORE_VERTICES": sum(value > 0 for value in degrees),
        "E": sum(graph) // 2,
        "GOODMAN": comb(20, 3) - mixed // 2,
        "SUM_CHOOSE3": sum(comb(value, 3) for value in graph),
        "SUM_D": sum(degrees),
        "SUM_G": sum(graph),
        "W": sum(comb(value, 2) for value in graph),
        "ZERO_VERTICES": degrees.count(0),
    }


def require_target(pid: str) -> dict[str, int]:
    require(pid == TARGET_PROFILE, "wrong profile")
    facts = profile_facts(pid)
    require(
        facts
        == {
            "CORE_VERTICES": 16,
            "E": 93,
            "GOODMAN": 293,
            "SUM_CHOOSE3": 2320,
            "SUM_D": 66,
            "SUM_G": 186,
            "W": 827,
            "ZERO_VERTICES": 4,
        },
        "target facts changed",
    )
    require(facts["SUM_CHOOSE3"] != OTHER_OWNER_CHOOSE3, "2318/2320 constant swap")
    require(
        Counter(profile_degrees(pid)) == Counter({6: 3, 5: 8, 4: 1, 1: 4, 0: 4}),
        "degree multiset",
    )
    return facts


def bonferroni_excess_ok() -> list[str]:
    """1[r > 0] <= r - C(r, 2) + C(r, 3) - (4/7) C(r, 4) for r = 0..7."""

    polynomial: list[str] = []
    for winners in range(8):
        upper = Fraction(winners - comb(winners, 2) + comb(winners, 3)) - Fraction(
            4 * comb(winners, 4), 7
        )
        require(upper >= int(winners > 0), "4/7 multiplicity inequality")
        polynomial.append(str(upper))
    require(comb(7, 2) // comb(3, 2) == 7, "maximum winner count")
    return polynomial


def quartet_weights() -> tuple[int, int]:
    """Recompute the two K4 outcome weights with the pinned R2 dynamic program."""

    def weight(masks: Mapping[int, int]) -> int:
        counts = [0] * 16
        for mask, count in masks.items():
            counts[mask] = count
        counts[0] = r2.BIG_LOTTO_POOL_SIZE - sum(counts)
        return r2.compressed_four_ticket_intersection_count(
            counts,
            pool_size=r2.BIG_LOTTO_POOL_SIZE,
            draw_size=r2.BIG_LOTTO_DRAW_SIZE,
            outright_matches=r2.BIG_LOTTO_OUTRIGHT_MATCHES,
        )

    with_triple = weight({7: 1, 9: 1, 10: 1, 12: 1, 1: 4, 2: 4, 4: 4, 8: 3})
    without_triple = weight({3: 1, 5: 1, 6: 1, 9: 1, 10: 1, 12: 1, 1: 3, 2: 3, 4: 3, 8: 3})
    require((with_triple, without_triple) == (LIGHT_K4, HEAVY_K4), "K4 weights changed")
    return with_triple, without_triple


def global_s4_floor() -> int:
    certificate = r2.k20_min_s2_s4_lower_bound_certificate()
    require(
        (
            certificate.minimum_triple_incidence_square_sum,
            certificate.cross_incidence_lower_bound,
            certificate.core_outside_pair_count,
            certificate.double_incidence_lower_bound_if_no_contribution,
            certificate.core_edge_count,
            certificate.s4_lower_bound,
        )
        == (222, 486, 374, 112, 66, GLOBAL_S4_FLOOR),
        "pinned global S4 certificate changed",
    )
    return certificate.s4_lower_bound


def shore_constant(graph_x: Sequence[int], graph_y: Sequence[int]) -> int:
    """Q in T = B0 - Q - 10 c + sum s (shore - 1 - g + s) - P."""

    x_size, y_size = len(graph_x), len(graph_y)
    require(x_size + y_size == 20 and x_size > 0 and y_size > 0, "two-shore partition")
    twice = y_size * sum(x_size - 1 - value for value in graph_x) + x_size * sum(
        y_size - 1 - value for value in graph_y
    )
    require(twice % 2 == 0, "two-shore constant parity")
    return twice // 2


def hilo_shores(degrees: Sequence[int]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return (
        tuple(value for value in degrees if value >= HI_MIN_DEGREE),
        tuple(value for value in degrees if value < HI_MIN_DEGREE),
    )


def hilo_choices(degree: int, own: Sequence[int], other: Sequence[int]) -> tuple[Choice, ...]:
    """Legal (triple-crossing, pair-crossing) counts at one ticket."""

    blockable = sum(value > 0 for value in other)
    offset = len(own) - 1 - (6 + degree)
    choices = tuple(
        (block, pair)
        for block in range(min(2 * degree, blockable) + 1)
        for pair in range(min(6 - degree, len(other)) + 1)
        if block + pair <= len(other) and offset + block + pair >= 0
    )
    require(bool(choices), "empty crossing choice set")
    return choices


def _score(offset: int, block: int, pair: int) -> int:
    crossing = block + pair
    return crossing * (offset + crossing)


def class_scores_multiset(
    degree: int,
    count: int,
    choices: Sequence[Choice],
    offset: int,
) -> dict[Cell, int]:
    """Maximum score of each (beta, pi) cell by degree-class multisets."""

    best: dict[Cell, int] = {}
    for multiset in combinations_with_replacement(tuple(choices), count):
        key = (sum(block for block, _ in multiset), sum(pair for _, pair in multiset))
        score = sum(_score(offset, block, pair) for block, pair in multiset)
        if score > best.get(key, -(10**9)):
            best[key] = score
    require(bool(best), f"empty multiset table for d={degree}")
    return best


def class_scores_vertex_dp(count: int, choices: Sequence[Choice], offset: int) -> dict[Cell, int]:
    """Same cells by adding one vertex at a time. Independent of the multiset walk."""

    states: dict[Cell, int] = {(0, 0): 0}
    for _ in range(count):
        following: dict[Cell, int] = {}
        for (block_sum, pair_sum), score in states.items():
            for block, pair in choices:
                key = (block_sum + block, pair_sum + pair)
                candidate = score + _score(offset, block, pair)
                if candidate > following.get(key, -(10**9)):
                    following[key] = candidate
        states = following
    return states


def _convolve(tables: Sequence[Mapping[Cell, int]]) -> dict[Cell, int]:
    total: dict[Cell, int] = {(0, 0): 0}
    for table in tables:
        merged: dict[Cell, int] = {}
        for (block_0, pair_0), score_0 in total.items():
            for (block_1, pair_1), score_1 in table.items():
                key = (block_0 + block_1, pair_0 + pair_1)
                candidate = score_0 + score_1
                if candidate > merged.get(key, -(10**9)):
                    merged[key] = candidate
        total = merged
    return total


def hilo_relaxation(pid: str) -> Document:
    """All feasible HI/LO cells. The cap is the maximum of F with P dropped."""

    facts = require_target(pid)
    degrees = profile_degrees(pid)
    high, low = hilo_shores(degrees)
    require((len(high), len(low), facts["GOODMAN"]) == (12, 8, 293), "HI/LO sizes")
    constant = facts["GOODMAN"] - shore_constant(
        tuple(6 + value for value in high), tuple(6 + value for value in low)
    )
    require(constant == 277, "HI/LO constant")
    tables: dict[str, list[dict[Cell, int]]] = {"HI": [], "LO": []}
    choice_record: dict[str, list[dict[str, object]]] = {}
    for shore, own, other in (("HI", high, low), ("LO", low, high)):
        recorded: list[dict[str, object]] = []
        for degree, count in sorted(Counter(own).items(), reverse=True):
            offset = len(own) - 1 - (6 + degree)
            choices = hilo_choices(degree, own, other)
            by_multiset = class_scores_multiset(degree, count, choices, offset)
            by_vertex = class_scores_vertex_dp(count, choices, offset)
            require(by_multiset == by_vertex, "multiset and vertex-DP cell scores differ")
            tables[shore].append(by_multiset)
            recorded.append(
                {
                    "CHOICES": [list(choice) for choice in choices],
                    "COUNT": count,
                    "D": degree,
                    "OFFSET": offset,
                }
            )
        choice_record[shore] = recorded
    high_cells, low_cells = _convolve(tables["HI"]), _convolve(tables["LO"])
    cells = sorted(set(high_cells) & set(low_cells))
    require(bool(cells), "empty HI/LO relaxation")
    values = {
        cell: constant - 10 * (cell[0] + cell[1]) + high_cells[cell] + low_cells[cell]
        for cell in cells
    }
    cap = max(values.values())
    argmax = [cell for cell in cells if values[cell] == cap]
    require(cap == 260 and argmax == [(7, 5), (7, 10)] and len(cells) == 66, "HI/LO cap changed")
    return {
        "ALL_CELLS": [
            [cell[0], cell[1], high_cells[cell], low_cells[cell], values[cell]] for cell in cells
        ],
        "ARGMAX": [[cell[0], cell[1]] for cell in argmax],
        "CAP": cap,
        "CELL_COUNT": len(cells),
        "CHOICES": choice_record,
        "CONSTANT": constant,
        "P_LOWER_BOUND": 0,
        "PARTITION": "HI={d>=4} size 12; LO={d<=1} size 8",
        "REALIZABILITY": "NOT_ASSERTED",
    }


def k4_floor(excess: int) -> int:
    """max(0, ceil(excess / 4)), by integers and by Fraction."""

    rational = Fraction(excess, 4)
    fractional = max(0, ceil(rational))
    integral = -(-excess // 4) if excess >= 0 else 0
    require(fractional == integral, "K4 ceiling disagreement")
    return fractional


def s3_pair(wedges: int, triangles: int) -> tuple[int, int]:
    """Expanded local sum and the compact 11872 form. Both are integers."""

    require(triangles >= 22, "triangle count below the 22 core triangles")
    open_wedges = wedges - 3 * triangles
    require(open_wedges >= 0, "triangle count exceeds the wedge identity")
    expanded = 2800 * open_wedges + 20272 * (triangles - 22) + 7000 * 22
    compact = 2800 * wedges + 11872 * (triangles - 22) - 30800
    require(expanded == compact, "S3 forms differ")
    return expanded, open_wedges


def s4_lower(k4: int, allowance: int, global_floor: int) -> tuple[int, int]:
    """Contained-triple split. The S4 coefficient in the union bound is negative."""

    require(k4 >= 0 and allowance >= 0 and global_floor >= 0, "negative S4 input")
    contained = min(k4, allowance)
    split = LIGHT_K4 * contained + HEAVY_K4 * (k4 - contained)
    rewritten = HEAVY_K4 * k4 - (HEAVY_K4 - LIGHT_K4) * contained
    require(split == rewritten and split >= LIGHT_K4 * k4, "S4 split is not exact")
    return contained, max(global_floor, split)


def envelope_term(
    triangles: int,
    *,
    wedges: int,
    choose3: int,
    degree_max: int,
    allowance: int,
    global_floor: int,
    s4_sign: int = -1,
    s5_upper: int | None = None,
) -> Term:
    """One T term. S5 is refused. The S4 sign must be the upper-bound direction."""

    require(s4_sign == -1, "invalid S4/S5 sign")
    require(s5_upper is None, "unsupported S5 authority")
    s3, open_wedges = s3_pair(wedges, triangles)
    excess = choose3 - (degree_max - 2) * open_wedges
    k4 = k4_floor(excess)
    contained, floor = s4_lower(k4, allowance, global_floor)
    rational = Fraction(S1 - S2 + s3) - Fraction(4 * floor, 7)
    bound = ceil(rational)
    integral = S1 - S2 + s3 - (4 * floor) // 7
    require(bound == integral and 0 <= bound - rational < 1, "rounding disagreement")
    return triangles, bound, k4, contained, floor, s3, open_wedges


def full_envelope(pid: str, cap: int, *, choose3: int | None = None) -> list[Term]:
    """Every integer T from 22 through cap, using J = 2320 unless a test overrides it."""

    facts = require_target(pid) if choose3 is None else profile_facts(pid)
    require(pid == TARGET_PROFILE, "wrong profile")
    used_choose3 = facts["SUM_CHOOSE3"] if choose3 is None else choose3
    require(used_choose3 == 2320, "2318/2320 constant swap")
    degrees = profile_degrees(pid)
    graph = tuple(6 + value for value in degrees)
    allowance = sum(value * (6 + value - 2) for value in degrees) // 3
    require(allowance == 197, "containment allowance")
    floor = global_s4_floor()
    wedge_cap = facts["W"] // 3
    goodman_cap = facts["GOODMAN"]
    require(22 <= cap <= min(wedge_cap, goodman_cap), "cap outside the wedge and Goodman range")
    return [
        envelope_term(
            triangles,
            wedges=facts["W"],
            choose3=used_choose3,
            degree_max=max(graph),
            allowance=allowance,
            global_floor=floor,
        )
        for triangles in range(22, cap + 1)
    ]


def require_complete_envelope(terms: Sequence[Term], cap: int) -> int:
    require(len(terms) == cap - 22 + 1, "incomplete T envelope")
    require([term[0] for term in terms] == list(range(22, cap + 1)), "missing T term")
    increasing = all(terms[index][1] < terms[index + 1][1] for index in range(len(terms) - 1))
    require(increasing, "envelope not increasing")
    bound = max(term[1] for term in terms)
    require(bound == terms[-1][1], "envelope maximum is not the cap term")
    return bound


def minimum_s4_for_term(triangles: int, target: int) -> int:
    """Smallest S4 whose ceiling at this single T is <= target. Not a uniform floor."""

    facts = require_target(TARGET_PROFILE)
    degrees = profile_degrees(TARGET_PROFILE)
    graph = tuple(6 + value for value in degrees)
    allowance = sum(value * (6 + value - 2) for value in degrees) // 3
    _triangles, _bound, _k4, _contained, current, _s3, _open = envelope_term(
        triangles,
        wedges=facts["W"],
        choose3=facts["SUM_CHOOSE3"],
        degree_max=max(graph),
        allowance=allowance,
        global_floor=GLOBAL_S4_FLOOR,
    )
    s3, _open_wedges = s3_pair(facts["W"], triangles)
    base = S1 - S2 + s3
    low, high = current, current + 200_000
    answer = high
    while low <= high:
        mid = (low + high) // 2
        if ceil(Fraction(base) - Fraction(4 * mid, 7)) <= target:
            answer = mid
            high = mid - 1
        else:
            low = mid + 1
    require(
        ceil(Fraction(base) - Fraction(4 * answer, 7)) <= target
        and ceil(Fraction(base) - Fraction(4 * (answer - 1), 7)) > target,
        "S4 threshold is not the first strict integer",
    )
    return answer


def count_triangles(order: int, edges: set[tuple[int, int]]) -> int:
    adjacency = [[False] * order for _ in range(order)]
    for left, right in edges:
        adjacency[left][right] = True
        adjacency[right][left] = True
    return sum(
        adjacency[a][b] and adjacency[a][c] and adjacency[b][c]
        for a, b, c in combinations(range(order), 3)
    )


def shore_split(edges: set[tuple[int, int]], shore: set[int]) -> tuple[int, int, int]:
    """Return T, F and P for any simple graph. The identity is T = F - P."""

    order = 20
    require(shore <= set(range(order)) and len(shore) not in {0, order}, "shore")
    other = set(range(order)) - shore
    adjacency = [[False] * order for _ in range(order)]
    for left, right in edges:
        require(0 <= left < right < order, "edge endpoints")
        adjacency[left][right] = True
        adjacency[right][left] = True
    graph = [sum(adjacency[vertex]) for vertex in range(order)]
    mixed = sum(value * (order - 1 - value) for value in graph)
    require(mixed % 2 == 0, "Goodman parity")
    goodman = comb(order, 3) - mixed // 2
    crossing = [
        sum(adjacency[vertex][mate] for mate in (other if vertex in shore else shore))
        for vertex in range(order)
    ]
    cross_count = sum(crossing[vertex] for vertex in shore)
    require(cross_count == sum(crossing[vertex] for vertex in other), "crossing sum")
    constant = shore_constant(
        [graph[vertex] for vertex in sorted(shore)],
        [graph[vertex] for vertex in sorted(other)],
    )
    # The constant above sorts by vertex id, not by the original shore order.
    # Recompute Q from the labelled shores so the identity does not depend on order.
    x_size, y_size = len(shore), len(other)
    twice = y_size * sum(x_size - 1 - graph[vertex] for vertex in shore) + x_size * sum(
        y_size - 1 - graph[vertex] for vertex in other
    )
    require(
        twice % 2 == 0
        and twice // 2
        == shore_constant(
            [graph[vertex] for vertex in sorted(shore)],
            [graph[vertex] for vertex in sorted(other)],
        ),
        "shore constant depends on order",
    )
    shore_score = sum(
        crossing[vertex] * (x_size - 1 - graph[vertex] + crossing[vertex]) for vertex in shore
    )
    other_score = sum(
        crossing[vertex] * (y_size - 1 - graph[vertex] + crossing[vertex]) for vertex in other
    )
    objective = goodman - constant - 10 * cross_count + shore_score + other_score

    def common_neighbors(left: int, right: int, pool: set[int]) -> int:
        return sum(adjacency[left][vertex] and adjacency[right][vertex] for vertex in pool)

    def induced_triangles(pool: set[int]) -> int:
        return sum(
            not adjacency[a][b] and not adjacency[a][c] and not adjacency[b][c]
            for a, b, c in combinations(sorted(pool), 3)
        )

    complement_x = [
        (left, right)
        for left, right in combinations(sorted(shore), 2)
        if not adjacency[left][right]
    ]
    complement_y = [
        (left, right)
        for left, right in combinations(sorted(other), 2)
        if not adjacency[left][right]
    ]
    remainder = (
        induced_triangles(shore)
        + induced_triangles(other)
        + sum(common_neighbors(left, right, other) for left, right in complement_x)
        + sum(common_neighbors(left, right, shore) for left, right in complement_y)
    )
    triangles = count_triangles(order, edges)
    require(triangles == objective - remainder and remainder >= 0, "two-shore identity failed")
    return triangles, objective, remainder


def load_base() -> Document:
    require(git("rev-parse", BASE_HEAD + "^{commit}") == BASE_HEAD, "base head mismatch")
    require(git("rev-parse", BASE_HEAD + "^{tree}") == BASE_TREE, "base tree mismatch")
    payload = blob(BASE_HEAD, BASE_RESULT, BASE_RESULT_SHA256)
    require(working_bytes(BASE_RESULT) == payload, "base result bytes changed")
    for name, digest in EVALUATOR_PINS.items():
        path = "src/lottolab/research/" + name
        pinned = blob(BASE_HEAD, path, digest)
        require(working_bytes(path) == pinned, "evaluator pin mismatch")
    return obj(json.loads(payload))


def family_state(rows: Mapping[str, int], cursor: Mapping[str, int]) -> Document:
    require(len(rows) == 4647 and len(cursor) == 197, "family coverage")
    require(not set(rows) & set(cursor), "family coverage")
    combined = {**rows, **cursor}
    best = max(combined.values())
    owners = sorted(profile for profile, bound in combined.items() if bound == best)
    ordered = sorted(combined.values(), reverse=True)
    opened = sum(bound > INCUMBENT for bound in combined.values())
    return {
        "CURSOR_MAXIMUM": max(cursor.values()),
        "FAMILY_BOUND": best,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "NEXT_DISTINCT_BOUND": max(bound for bound in combined.values() if bound < best),
        "OWNER_IDS": owners,
        "RESOLVED_MAXIMUM": max(rows.values()),
        "STILL_OPEN_PROFILE_COUNT": opened,
        "TIED_OWNER_COUNT": len(owners),
        "TOP_BOUND_CHECK": ordered[0],
    }


def replay_family(
    rows: Mapping[str, int],
    cursor: Mapping[str, int],
    replacement: Mapping[str, int],
    *,
    cursor_fingerprint: str,
) -> tuple[dict[str, int], Document]:
    require(set(replacement) == {TARGET_PROFILE}, "replacement scope")
    require(TARGET_PROFILE in rows and OTHER_OWNER in rows, "owners missing")
    require(sha(render(dict(sorted(cursor.items())))) == cursor_fingerprint, "cursor mutation")
    updated = dict(rows)
    updated[TARGET_PROFILE] = replacement[TARGET_PROFILE]
    require(updated[OTHER_OWNER] == rows[OTHER_OWNER] == SEALED_SCALAR_BOUND, "other owner changed")
    changed = sorted(profile for profile, bound in rows.items() if updated[profile] != bound)
    require(changed == [TARGET_PROFILE], "row mutation outside the target")
    state = family_state(updated, cursor)
    require(state["TOP_BOUND_CHECK"] == state["FAMILY_BOUND"], "family maximum mismatch")
    return updated, state


def compute_t260_result() -> Document:
    base = load_base()
    require(
        base["MODEL"]
        == {
            "LABELS_PER_TICKET": 6,
            "PAIR_LINEARITY": True,
            "PAIRS": 27,
            "TICKETS": 20,
            "TRIPLES": 22,
        },
        "frozen support model",
    )
    require(base["INCUMBENT"] == INCUMBENT, "incumbent changed")
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    cursor_bounds = ledger(cursor["COARSE_BOUND_PROJECTION"])
    cursor_ids = cast(list[object], cursor["PROFILE_IDS"])
    require(
        len(rows) == 4647
        and len(cursor_ids) == len(cursor_bounds) == 197
        and len(set(str(item) for item in cursor_ids)) == 197
        and set(str(item) for item in cursor_ids) == set(cursor_bounds)
        and not set(rows) & set(cursor_bounds),
        "cursor coverage",
    )
    require(rows[TARGET_PROFILE] == rows[OTHER_OWNER] == SEALED_SCALAR_BOUND, "sealed scalars")
    sealed_family = family_state(rows, cursor_bounds)
    require(obj(base["FAMILY_AFTER"])["FAMILY_BOUND"] == SEALED_SCALAR_BOUND, "base family bound")
    require(
        sealed_family["OWNER_IDS"] == [OTHER_OWNER, TARGET_PROFILE]
        and sealed_family["FAMILY_BOUND"] == SEALED_SCALAR_BOUND
        and sealed_family["STILL_OPEN_PROFILE_COUNT"]
        == obj(base["FAMILY_AFTER"])["STILL_OPEN_PROFILE_COUNT"],
        "sealed family replay",
    )
    facts = require_target(TARGET_PROFILE)
    polynomial = bonferroni_excess_ok()
    weights = quartet_weights()
    relaxation = hilo_relaxation(TARGET_PROFILE)
    cap = cast(int, relaxation["CAP"])
    terms = full_envelope(TARGET_PROFILE, cap)
    new_bound = require_complete_envelope(terms, cap)
    unrestricted = full_envelope(TARGET_PROFILE, facts["W"] // 3)
    unrestricted_bound = require_complete_envelope(unrestricted, facts["W"] // 3)
    at_265 = next(term[1] for term in unrestricted if term[0] == 265)
    require(at_265 == SEALED_SCALAR_BOUND, "T=265 numerical coincidence changed")
    require(new_bound <= SEALED_SCALAR_BOUND - 1, "no strict profile gain")
    require(
        unrestricted_bound > SEALED_SCALAR_BOUND,
        "unrestricted route B is not weaker than the seal",
    )
    s4_at_265 = minimum_s4_for_term(265, SEALED_SCALAR_BOUND - 1)
    current_265 = next(term[4] for term in unrestricted if term[0] == 265)
    require(s4_at_265 == current_265 + 2, "single-term S4 threshold is not +2")
    cursor_fingerprint = sha(render(dict(sorted(cursor_bounds.items()))))
    _updated, family_after = replay_family(
        rows,
        cursor_bounds,
        {TARGET_PROFILE: new_bound},
        cursor_fingerprint=cursor_fingerprint,
    )
    require(family_after["FAMILY_BOUND"] == SEALED_SCALAR_BOUND, "false family gain")
    require(
        family_after["OWNER_IDS"] == [OTHER_OWNER],
        "other owner did not remain sole family owner",
    )
    after_bound = cast(int, family_after["FAMILY_BOUND"])
    before_bound = cast(int, sealed_family["FAMILY_BOUND"])
    require(after_bound - before_bound == 0, "family delta")
    profile_delta = SEALED_SCALAR_BOUND - new_bound
    require(profile_delta == 45004 and new_bound == 313_346_736, "profile bound changed")
    gates = {
        "G01": "PASS",
        "G02": "PASS",
        "G03": "PASS",
        "G04": "PASS",
        "G05": "PASS",
        "G06": "PASS",
        "G07": "PASS",
        "G08": "PASS",
        "G09": "PASS",
        "G10": "PASS",
        "G11": "PASS",
        "G12": "PASS",
        "G13": "PASS",
        "G14": "PASS",
        "G15": "PASS",
        "G16": "NOT_VERIFIED",
        "G17": "NOT_VERIFIED",
        "G18": "NOT_VERIFIED",
    }
    return {
        "BASE_HEAD": BASE_HEAD,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "BASE_TREE": BASE_TREE,
        "BOUND_ROUNDING": "ceil(S1-S2+S3-4*S4/7)=S1-S2+S3-floor(4*S4/7)",
        "CURRENT_S4_AUTHORITY": (
            "GLOBAL_112_PINNED_ON_R2_FOR_THE_FROZEN_SUPPORT_MODEL; "
            "PROFILE_S4_IS_THE_K4_SPLIT_PROVED_HERE; SEALED_ROW_HAS_NO_SEPARATE_S4_PIN"
        ),
        "CURRENT_S5_AUTHORITY": "NOT_PINNED",
        "CURRENT_SEALED_BOUND": SEALED_SCALAR_BOUND,
        "CURRENT_T_AUTHORITY": "NOT_PINNED_IN_SEALED_FAMILY_RESULT",
        "CURSOR_PRESERVED": True,
        "CURSOR_PROFILES": 197,
        "ENUMERATION_DOMAIN": {
            "CELLS": relaxation["CELL_COUNT"],
            "DESCRIPTION": "HI/LO (beta, pi) cells; degree-class multisets; P dropped",
            "T_RANGE": [22, cap],
        },
        "EVALUATOR_SOURCE_PINS": EVALUATOR_PINS,
        "EXACT_ARITHMETIC": {
            "BONFERRONI_POLYNOMIAL_R0_TO_R7": polynomial,
            "K4_WEIGHTS": {"WITH_TRIPLE": weights[0], "WITHOUT_TRIPLE": weights[1]},
            "S5_USED": False,
        },
        "FAMILY_AFTER_SINGLE_ROW": {
            key: family_after[key]
            for key in (
                "CURSOR_MAXIMUM",
                "FAMILY_BOUND",
                "GAP_TO_INCUMBENT",
                "NEXT_DISTINCT_BOUND",
                "OWNER_IDS",
                "RESOLVED_MAXIMUM",
                "STILL_OPEN_PROFILE_COUNT",
            )
        },
        "FAMILY_BEFORE": {
            key: sealed_family[key]
            for key in (
                "CURSOR_MAXIMUM",
                "FAMILY_BOUND",
                "GAP_TO_INCUMBENT",
                "NEXT_DISTINCT_BOUND",
                "OWNER_IDS",
                "RESOLVED_MAXIMUM",
                "STILL_OPEN_PROFILE_COUNT",
            )
        },
        "FAMILY_DELTA": 0,
        "FAMILY_OWNER_IDS": family_after["OWNER_IDS"],
        "G01_TO_G18": gates,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "HI_LO_RELAXATION": {
            "ALL_CELLS": relaxation["ALL_CELLS"],
            "ARGMAX": relaxation["ARGMAX"],
            "CAP": cap,
            "CELL_COUNT": relaxation["CELL_COUNT"],
            "CHOICES": relaxation["CHOICES"],
            "CONSTANT": relaxation["CONSTANT"],
        },
        "INCUMBENT": INCUMBENT,
        "INHERITED_CAVEATS": {
            "ADVANCED_11ROW_AND_DONOR_DISPOSITIONS": "PRESERVED_IN_BASE_RESULT_NOT_UPGRADED",
            "BEE6ACAA_FRESH_JUDGE_CAVEATS": "PRESERVED_IN_BASE_RESULT",
            "EXTERNAL_18526_TERM_REFERENCE": "NOT_VERIFIED",
            "FOUR_ZERO_T_LE_267": "NO_IMPROVEMENT_NOT_RERUN",
            "GLOBAL_K20_OPTIMUM": "UNKNOWN",
            "HISTORICAL_R15": "NOT_VERIFIED",
            "LEGAL_ATTAINMENT": "UNKNOWN",
            "W784_GOODMAN_T_LE_250": "DIFFERENT_COHORT_NOT_THIS_PROFILE",
        },
        "INITIAL_INDEX_SHA256": INITIAL_INDEX_SHA256,
        "INITIAL_SHARED_REFS_FINGERPRINT": INITIAL_SHARED_REFS_FINGERPRINT,
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "MODEL": base["MODEL"],
        "NEW_FULL_PROFILE_BOUND": new_bound,
        "NEW_PROVEN_S4": "MAX(112, 448*contained+679*(K4-contained)) AT EACH T",
        "NEW_PROVEN_S5": "NOT_USED",
        "NEW_PROVEN_T_CAP": cap,
        "OTHER_OWNER": {"BOUND": rows[OTHER_OWNER], "PROFILE": OTHER_OWNER},
        "OTHER_ROWS_UNCHANGED": 4646,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "PREVIOUS_T267_DISPOSITION": (
            "FOUR_ZERO_NECESSARY_CONDITION_RECOUNT_DOES_NOT_TIGHTEN_THE_SEALED_SCALAR; NOT_RERUN"
        ),
        "PROFILE_DELTA": profile_delta,
        "PROFILE_FACTS": facts,
        "REMOTE_WRITE": "NO",
        "RESOLVED_ROWS": 4647,
        "RECONSTRUCTED_ROUTE_B_BOUND": new_bound,
        "RECONSTRUCTED_ROUTE_B_EQUALS_SEALED_SCALAR": False,
        "S4_SINGLE_TERM_THRESHOLD": {
            "CURRENT_S4_AT_T265": current_265,
            "MINIMUM_S4_FOR_T265_TERM_ONLY": s4_at_265,
            "NOTE": (
                "Plus two outcomes drops only the T=265 term to 313391739. "
                "Higher admissible T remain above the sealed scalar unless a "
                "triangle cap excludes them. S4+1 is not sufficient."
            ),
        },
        "SEALED_SCALAR_BOUND": SEALED_SCALAR_BOUND,
        "SEALED_SCALAR_NUMERICALLY_EQUALS_ROUTE_B_AT_T": {
            "AUTHORITY": "NOT_PINNED",
            "BOUND": at_265,
            "T": 265,
        },
        "SELECTED_RESTRICTION": "HI_LO_CROSSING_SPLIT_T_LE_260_THEN_ROUTE_B_ENVELOPE",
        "SOURCE_PINS": {
            "BASE_RESULT": {"HEAD": BASE_HEAD, "SHA256": BASE_RESULT_SHA256, "TREE": BASE_TREE},
            "EVALUATORS": EVALUATOR_PINS,
            "OFF_BASE_1300AE27": {
                "ANCESTOR_OF_BASE": "NO",
                "STATUS": "NOT_PINNED",
                "USE": "NOT_READ_AS_AUTHORITY",
            },
            "S5": "NOT_PINNED",
            "SEALED_PROFILE_T_S4_S5": "NOT_PINNED",
            "W784_T_CAP_250": "NOT_THIS_PROFILE",
        },
        "STRICT_GAIN_EXCLUDED": False,
        "TARGET_PROFILE": TARGET_PROFILE,
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PROFILE_BOUND_PROVED_FAMILY_UNCHANGED; FRESH_JUDGE_EXTERNAL",
        "T_TERMS": [
            {
                "BOUND": term[1],
                "CONTAINED_K4": term[3],
                "K4_FLOOR": term[2],
                "OPEN_WEDGES": term[6],
                "S3": term[5],
                "S4": term[4],
                "T": term[0],
            }
            for term in terms
        ],
        "UNRESTRICTED_WEDGE_ROUTE_B_BOUND": unrestricted_bound,
        "UNRESTRICTED_WEDGE_ROUTE_B_ADOPTED": False,
    }


def partition_shadow_states() -> set[ShadowState]:
    """Method A: restricted-growth set partitions of four labelled d=1 tickets."""

    states: set[ShadowState] = set()
    partitions = assignments = 0
    for word in product(range(4), repeat=4):
        if word[0] != 0 or any(word[i] > 1 + max(word[:i]) for i in range(1, 4)):
            continue
        sizes = [word.count(i) for i in range(max(word) + 1)]
        if max(sizes) > 3:
            continue
        partitions += 1
        choices = [tuple(t for t in LOW_TYPES if t.count(1) == size) for size in sizes]
        for triples in product(*choices):
            assignments += 1
            counts = tuple(triples.count(t) for t in LOW_TYPES)
            c = sum(t.count(4) for t in triples)
            high = sum(t.count(6) for t in triples)
            pairs = sum(comb(t.count(6), 2) for t in triples)
            for all_six in (0, 1):
                if c > 4 or high < 3 or pairs + 3 * all_six > 3:
                    continue
                if 4 - c > 22 - len(triples) - all_six:
                    continue
                states.add((counts, all_six, 194 - 4 * len(triples) + c + all_six))
    require((partitions, assignments) == (14, 1122), "partition coverage changed")
    return states


def histogram_shadow_states() -> set[ShadowState]:
    """Method B: bounded integer histograms; no partition walk or A score call."""

    states: set[ShadowState] = set()

    def visit(index: int, remaining: int, counts: tuple[int, ...]) -> None:
        if index < 9:
            incidence = sum(value == 1 for value in LOW_TYPES[index])
            for count in range(remaining // incidence + 1):
                visit(index + 1, remaining - count * incidence, (*counts, count))
            return
        if remaining:
            return
        blocks = sum(counts)
        fours = sum(n for n, t in zip(counts, LOW_TYPES, strict=True) if 4 in t)
        sixes = sum(n * sum(d == 6 for d in t) for n, t in zip(counts, LOW_TYPES, strict=True))
        used_pairs = sum(n for n, t in zip(counts, LOW_TYPES, strict=True) if t.count(6) == 2)
        if fours > 4 or sixes < 3:
            return
        for q in range(2):
            if used_pairs > 3 * (1 - q) or 22 - blocks - q < 4 - fours:
                continue
            minima = blocks + 4 * (4 - fours) + 5 * (22 - blocks - (4 - fours) - q) + 6 * q
            states.add((counts, q, 88 + minima))

    visit(0, 4, ())
    return states


def validate_shadow_state(state: ShadowState) -> None:
    counts, q, score = state
    require(len(counts) == 9 and all(type(n) is int and n >= 0 for n in counts), "shadow counts")
    require(q in (0, 1), "shadow all-six capacity")
    incidence = sum(n * t.count(1) for n, t in zip(counts, LOW_TYPES, strict=True))
    c = sum(n * t.count(4) for n, t in zip(counts, LOW_TYPES, strict=True))
    h = sum(n * t.count(6) for n, t in zip(counts, LOW_TYPES, strict=True))
    pairs = sum(n * comb(t.count(6), 2) for n, t in zip(counts, LOW_TYPES, strict=True))
    b = sum(counts)
    require(
        incidence == 4 and c <= 4 and h >= 3 and pairs + 3 * q <= 3 and 4 - c <= 22 - b - q,
        "invalid shadow condition",
    )
    require(score == 194 - 4 * b + c + q, "incorrect shadow score")


def k4_certificate() -> Document:
    """Universal coverage proof for the additional cheaper-K4 cap.

    H is the linear 3-uniform hypergraph of 22 triple label supports; P is the
    disjoint set of 27 pair supports; G is their simple shadow union. For an
    unordered four-ticket set Q, a triple-containing K4 means G[Q]=K4 and a
    support tau in H is a subset of Q. Two such tau would share a pair, so
    there is at most one. Its count A equals sum_tau |intersection N_G(v)|.
    Neighbourhoods are open, so these common neighbours lie outside tau.
    Each summand is <= min_v(g_v-2)=4+min_v d_v. The old average bound is
    floor(sum_v d_v*(g_v-2)/3)=197.

    Split the vertices into C (twelve d>=4), L (four d=1), Z (four d=0).
    Every d=6 vertex has twelve DISTINCT H-shadow neighbours; only eleven
    other C vertices exist, so each meets L. Thus triples meeting L have at
    least three d=6 incidences in total. Each L vertex lies in exactly one
    support: these supports partition labelled L into b blocks of size 1..3.
    Their nine degree types are exactly LOW_TYPES. The unique d=4 vertex
    cannot occur twice in one support; c<=4 of its incidences meet L. There
    are 3*b-4 non-L slots, hence 3*b-4-c>=3. It follows that b>=3, and c<=2
    if b=3. The three d=6 vertices support q<=1 all-six triples. Low supports
    consume at most three of their pairs, including 3*q. The remaining 4-c
    d=4 incidences occupy distinct supports not meeting L or all-six, so
    4-c<=22-b-q. These are NECESSARY conditions only.

    Minima sum exactly to b+4*(4-c)+5*(22-b-(4-c)-q)+6*q. Adding 4*22 gives
    A<=194-4*b+c+q<=185 (b=3); for b=4 it is <=183. Both enumerators retain
    the complete 73-state necessary relaxation, including impossible states.
    Every legal H maps to A's labelled partition and degree-class partners,
    then to B's histogram. Conversely every histogram has a partition of its
    four L slots. Forgetting partner identities admits extra configurations;
    it cannot omit a legal one. There is no sufficiency or attainment claim.

    Z has H-degree zero, P-degree six, and no H-shadow edge. All of its 24
    pair-ends may be placed in any compatible simple residual P. No G[Z]
    or C/Z pair-placement restriction is imposed by this relaxation. Common
    neighbours in Z remain counted in the FULL G, so the argument covers
    every compatible residual graph. Z is never silently deleted.
    """

    expected = tuple(
        t for t in combinations_with_replacement((1, 4, 5, 6), 3) if 1 in t and t.count(4) <= 1
    )
    require(expected == LOW_TYPES, "shadow type domain changed")
    first, second = partition_shadow_states(), histogram_shadow_states()
    for state in first | second:
        validate_shadow_state(state)
    require(first == second and len(first) == 73, "incomplete necessary state set")
    cap = max(score for _, _, score in first)
    require(cap == 185, "incorrect K4 cap")
    old = sum(d * (4 + d) for d in profile_degrees(TARGET_PROFILE)) // 3
    require(old == 197, "old K4 cap changed")
    return {
        "OLD_CAP": old,
        "CAP": cap,
        "STATE_COUNT": len(first),
        "LOW_TYPES": [list(t) for t in LOW_TYPES],
        "STATES": [
            {"LOW_TYPE_COUNTS": list(n), "ALL_SIX": q, "CAP": score}
            for n, q, score in sorted(first)
        ],
        "METHOD_A": "14 labelled set partitions; 1122 degree-class assignments",
        "METHOD_B": "nine-type incidence histogram recursion; category-minimum sum",
        "INDEPENDENT_SETS_EQUAL": True,
        "COVERAGE": "Every legal H maps to a retained state; all compatible residual P included",
        "LEGAL_ATTAINMENT": "UNKNOWN",
    }


def refined_envelope(cap: int, allowance: int) -> list[Term]:
    facts = require_target(TARGET_PROFILE)
    floor = global_s4_floor()
    return [
        envelope_term(
            t,
            wedges=facts["W"],
            choose3=facts["SUM_CHOOSE3"],
            degree_max=12,
            allowance=allowance,
            global_floor=floor,
        )
        for t in range(22, cap + 1)
    ]


def checked_envelope(terms: Sequence[Term], cap: int, allowance: int) -> int:
    bound = require_complete_envelope(terms, cap)
    # Independent direct formula validates every shipped term, including rounding.
    for t, upper, k4, contained, floor, s3, opened in terms:
        q = max(0, ceil(Fraction(2320 - 10 * (827 - 3 * t), 4)))
        lower = max(112, 679 * q - 231 * min(q, allowance))
        third = 2800 * (827 - 3 * t) + 20272 * (t - 22) + 154000
        require(
            (k4, contained, floor, s3, opened) == (q, min(q, allowance), lower, third, 827 - 3 * t),
            "incorrect Route-B term",
        )
        require(
            upper == ceil(Fraction(372228640 - 63838600 + third) - Fraction(4 * lower, 7)),
            "wrong Route-B sign or rounding",
        )
    return bound


def term_records(terms: Sequence[Term]) -> list[dict[str, int]]:
    return [
        dict(
            zip(
                ("T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4", "S3", "OPEN_WEDGES"),
                term,
                strict=True,
            )
        )
        for term in terms
    ]


def project_family(
    rows: Mapping[str, int],
    cursor: Mapping[str, int],
    updates: Sequence[tuple[str, int]],
    expected: Sequence[str],
    cursor_fingerprint: str,
) -> Document:
    ids = [pid for pid, _ in updates]
    require(
        len(ids) == len(set(ids)) == len(expected) and set(ids) == set(expected),
        "missing/duplicate ledger update",
    )
    require(sha(render(dict(sorted(cursor.items())))) == cursor_fingerprint, "cursor mutation")
    updated = dict(rows)
    for pid, upper in updates:
        require(pid in rows and 0 <= upper < rows[pid], "invalid projection update")
        updated[pid] = upper
    require({p for p in rows if rows[p] != updated[p]} == set(expected), "projection scope")
    state = family_state(updated, cursor)
    state["CHANGED_PROFILES"] = sorted(expected)
    state["OTHER_ROWS_PRESERVED"] = len(rows) - len(expected)
    state["CURSOR_SHA256"] = cursor_fingerprint
    return state


def compute_result(pid: str = TARGET_PROFILE) -> Document:
    require_target(pid)
    legacy = compute_t260_result()
    require(git("rev-parse", PRESERVED_HEAD + "^{tree}") == PRESERVED_TREE, "preserved tree")
    preserved = blob(PRESERVED_HEAD, RESULT, PRESERVED_RESULT_SHA256)
    require(render(legacy) == preserved, "original T260 certificate changed")
    k4 = k4_certificate()
    allowance = cast(int, k4["CAP"])
    require(allowance == 185, "incorrect K4 cap")
    joint = refined_envelope(260, allowance)
    joint_bound = checked_envelope(joint, 260, allowance)
    projection = refined_envelope(265, allowance)
    projected_bound = checked_envelope(projection, 265, allowance)
    old265 = full_envelope(TARGET_PROFILE, 265)
    checked_envelope(old265, 265, 197)
    require((old265[-1][4], projection[-1][4]) == (293993, 296765), "S4 correction changed")
    require(
        231 * (197 - allowance) == 2772 and Fraction(4 * 2772, 7) == 1584, "correction arithmetic"
    )
    require(projected_bound == 313390156, "T265 full envelope changed")
    old_bound = cast(int, legacy["NEW_FULL_PROFILE_BOUND"])
    adopted = min(old_bound, joint_bound, projected_bound)
    require(adopted <= old_bound, "T260 certificate downgraded")
    require(adopted == joint_bound == 313345152, "joint full envelope changed")

    require(git("rev-parse", OWNER_A_HEAD + "^{tree}") == OWNER_A_TREE, "Owner A tree")
    donor = obj(json.loads(blob(OWNER_A_HEAD, OWNER_A_RESULT, OWNER_A_SHA256)))
    require(
        donor["BASE_HEAD"] == BASE_HEAD
        and donor["BASE_TREE"] == BASE_TREE
        and donor["BASE_RESULT_SHA256"] == BASE_RESULT_SHA256
        and obj(donor["FACTS"])["PROFILE"] == OTHER_OWNER
        and donor["NEW_FULL_PROFILE_BOUND"] == 313248348,
        "Owner A authority mismatch",
    )
    base = load_base()
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = ledger(obj(base["CURSOR"])["COARSE_BOUND_PROJECTION"])
    fingerprint = sha(render(dict(sorted(cursor.items()))))
    s0 = family_state(rows, cursor)
    s1 = project_family(rows, cursor, [(TARGET_PROFILE, adopted)], [TARGET_PROFILE], fingerprint)
    s2 = project_family(
        rows,
        cursor,
        [(OTHER_OWNER, 313248348), (TARGET_PROFILE, adopted)],
        [OTHER_OWNER, TARGET_PROFILE],
        fingerprint,
    )
    require(
        s0["FAMILY_BOUND"] == s1["FAMILY_BOUND"] == 313391740
        and s2["FAMILY_BOUND"] == 313391636
        and s2["OWNER_IDS"] == ["66665555555321100000"],
        "Family projection mismatch",
    )
    result = dict(legacy)
    result.update(
        {
            "PRESERVED_T260_CERTIFICATE": legacy,
            "PRESERVED_CERTIFICATE_PIN": {
                "HEAD": PRESERVED_HEAD,
                "TREE": PRESERVED_TREE,
                "RESULT_SHA256": PRESERVED_RESULT_SHA256,
            },
            "CONTINUATION_OWNER_CONVERSATION_ID": CONTINUATION_OWNER,
            "K4_CERTIFICATE": k4,
            "T265_K4_ONLY_PROJECTION": {
                "BOUND": projected_bound,
                "T_CAP": 265,
                "CAP_AUTHORITY": "WEAKENING_OF_PROVEN_T260",
                "OLD_TERMS": term_records(old265),
                "NEW_TERMS": term_records(projection),
            },
            "JOINT_T260_K4_BOUND": joint_bound,
            "NEW_FULL_PROFILE_BOUND": adopted,
            "PROFILE_DELTA": SEALED_SCALAR_BOUND - adopted,
            "GAIN_OVER_PRESERVED_T260": old_bound - adopted,
            "RECONSTRUCTED_ROUTE_B_BOUND": adopted,
            "T_TERMS": term_records(joint),
            "NEW_PROVEN_S4": "MAX(112, 679*q(T)-231*MIN(q(T),185))",
            "SELECTED_RESTRICTION": "PRESERVED_HILO_T260_AND_UNIVERSAL_CONTAINED_K4_CAP185",
            "FAMILY_PROJECTIONS": {"S0": s0, "S1_B_ONLY": s1, "S2_A_AND_B": s2},
            "FAMILY_AUTHORITY_STATUS": "PROJECTIONS_ONLY; SHARED_LEDGER_NOT_CHANGED",
            "OWNER_A_AUTHORITY": {
                "HEAD": OWNER_A_HEAD,
                "TREE": OWNER_A_TREE,
                "RESULT_SHA256": OWNER_A_SHA256,
                "BOUND": 313248348,
                "INHERITED_CAVEATS": {
                    key: donor[key]
                    for key in (
                        "BASE_JUDGE_CAVEATS",
                        "BASE_JUDGE_REPORT_SHA256",
                        "HISTORICAL_R15",
                        "INHERITED_AUTHORITY_VERBATIM",
                        "INHERITED_BASE_FRESH_JUDGE",
                        "LEGAL_ATTAINMENT",
                        "GLOBAL_K20_OPTIMUM",
                    )
                },
            },
            "SOURCE_SHA256": sha(working_bytes(SOURCE)),
            "TEST_SHA256": sha(working_bytes(TEST)),
            "TASK_STATUS": "JOINT_PROFILE_BOUND_PROVED; FAMILY_PROJECTIONS; LIFECYCLE_EXTERNAL",
            # Runtime and lifecycle outcomes are recorded externally on the exact sealed tree.
            "G01_TO_G18": {
                f"G{i:02d}": "PASS" if i not in (2, 16, 17, 18) else "NOT_VERIFIED"
                for i in range(1, 19)
            },
        }
    )
    return result


def verify_result(value: object) -> None:
    require(render(value) == render(compute_result()), "deterministic result mismatch")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    payload = render(compute_result())
    path = ROOT / RESULT
    if args.write_result:
        require(
            not path.exists()
            or path.read_bytes() == payload
            or sha(path.read_bytes()) == PRESERVED_RESULT_SHA256,
            "result rewrite would overwrite an unexplained candidate",
        )
        if not path.exists() or path.read_bytes() != payload:
            path.write_bytes(payload)
    require(path.is_file() and path.read_bytes() == payload, "sealed result mismatch")
    sys.stdout.buffer.write(payload)


if __name__ == "__main__":
    main()
