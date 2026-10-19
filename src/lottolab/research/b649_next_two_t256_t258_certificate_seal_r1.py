"""Sealed caps T<=256 for 66655555555331100000 (A) and T<=258 for 66655555555411110000 (B).

The proof was first run in the read-only transcript of the Fresh Judge
B649_NEXT_TWO_T256_T258_FULL_PROFILE_FRESH_JUDGE_R2. This module re-implements it as code.

Support model (r5). Twenty tickets hold six labels each. 22 labels are triple supports and 27
are pair supports, and two tickets share at most one label. G is the triple shadow plus the
pairs: |E(G)|=66+27=93 and deg(v)=2d_v+(6-d_v)=6+d_v, where d_v counts the triples through v.
T=t(G). H is the complement, with 97 edges and deg_H=13-d. Both profiles have sum d^2=328, so
inclusion-exclusion and Goodman both give t(G)+t(H)=293.

Split. K={d>0}, Z={d=0}: A has k=15, z=5 and B has k=16, z=4. A triple through a zero would
give it d>0, so every triple lies in K and a core ticket x reaches Z only by pair labels:
sigma_x=|N(x)&Z|<=min(6-d_x,z). A zero has degree 6, so zeta_u=|N(u)&K|=6-deg_{G[Z]}(u).
Both sums count the K-Z edges, r. Put M=H[K]. Then deg_M(x)=k-7-d_x+sigma_x and
deg_{H[Z]}(u)=zeta_u+z-7. An H triangle lies in K, lies in Z, or has one edge inside a part and
its apex across, and counting apexes by inclusion-exclusion gives
t(H)=z|M|+k|H[Z]|-sum sigma*deg_M-sum zeta*deg_{H[Z]}+P. Hence, for both profiles,

  T = 233 + sum_K sigma(sigma-d-4) + sum_Z zeta^2 - P,
  P = t(M) + t(H[Z]) + sum_{xy in M}|N(x)&N(y)&Z| + sum_x e_{H[Z]}(N_Z(x)) >= 0.

Here 233=293-z(k(k-7)-66)/2-kz(z-7)/2, and the linear terms collapse to -4r because
(k+z)/2-14=-4. P is a sum of four cardinalities.

Zero side. Keep the two Z parts of P and drop P_K=t(M)+sum_M c_Z>=0:

  T <= Phi = 233 + sum zeta^2 - t(H[Z]) + sum_x [sigma_x(sigma_x-d_x-4) - e_{H[Z]}(N_Z(x))].

Phi depends only on G[Z] and the sets N_Z(x). Every realization fixes one G[Z] and one K-Z
incidence whose rows obey the sigma caps and whose column sums are zeta. The maximum of Phi
over all such pairs therefore bounds T. Two codes compute it exactly. One is a DP over residual
column demand for every labelled G[Z]. The other enumerates explicitly over isomorphism classes
of G[Z], and the sigma<=1 class (d=5) absorbs the residual. A gives 253, so T_A<=253<=256.
B gives 274.

B K side. Let L be the four d=1 tickets, c the d=4 ticket and HI={d>=4} (12 tickets).
  - A d=6 ticket has no pair label. A d=5 ticket with sigma=1 spends its only pair label on Z.
    Neither is a pair partner of anything in K.
  - K6 lemma. A d=6 ticket has 12 neighbours, all in K and all through triples. Only 11 other
    HI tickets exist, so it shares a triple with some L ticket. The three d=6 tickets
    therefore fill at least three HI slots of L triples.
The local structure of L is the partition of L by shared triple (blocks<=3), the L-L pair
labels (across blocks, at most 5-sigma per ticket) and the L tickets paired with c (at most
2-sigma_c, never in c's triple). It also fixes the HI members of each L triple by type
{c, d5 at u, d5 with sigma=0, d6}. The remaining pair partners of an L ticket can only be
d5 tickets with sigma=0, and each of those is used once. With the structure fixed:
  - c_Z over L-L non-edges is exact, and over L-HI non-edges it is W_y-covered_y.
  - t_M(y)=C(h_y,2)-(81-r/2)+sum_{N(y)} g-e_G(N(y)), with g=deg_{G[K]} and
    e_G(N(y))<=min(C(n,2)-known L non-edges, floor(sum min(n-1,g-1)/2)).
  - t(M)>=sum_{y in S} t_M(y)-sum_{non-adjacent y,y' in S}(14-max(g_y,g_y')) for every S.
The minimum over every local structure that puts all three d=6 tickets into L triples is a
lower bound LB on P_K, so T<=Phi-LB. Per-block Pareto pruning keeps that minimum exact,
because the bound is monotone in every block coordinate. All 399 states with Phi>258 fall to
at most 239. Every state with Phi>239 also falls to at most 239 or is locally infeasible, so
T_B<=239<=258.

Route B (R32 rule, S4 base 112) on 22..cap gives A 313311276 and B 313328812. Both are
prefixes of the cap-265 envelope 313391740. This module certifies the two row caps only. It
is not a Family authority.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, pairwise, permutations, product
from math import comb
from pathlib import Path
from types import ModuleType
from typing import cast

from . import b649_k20_min_s2_dangerous_core_realizability_r5 as r5
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32

TASK_ID = "B649_NEXT_TWO_T256_T258_CERTIFICATE_SEAL_R1"
BASE_HEAD = "88a37370e6db035d6155190723de8cea646e76b7"
BASE_TREE = "4fede8e927eab43d58b906ce80e7eea10300b4a0"
BASE_RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-triple-t262-31-event-family-integration-r1-result.json"
)
BASE_RESULT_SHA256 = "802cb12eb1b737450c707d55386382e90689a3ff1574b84aa0a7365bb975497d"
TRANSCRIPT_JUDGE_TASK_ID = "B649_NEXT_TWO_T256_T258_FULL_PROFILE_FRESH_JUDGE_R2"
TRANSCRIPT_JUDGE_SESSION_ID = "9c78e699-f3d7-42af-add2-a67565b80762"
PROFILE_A = "66655555555331100000"
PROFILE_B = "66655555555411110000"
CLAIMED_CAPS = {PROFILE_A: 256, PROFILE_B: 258}
OLD_CAP = 265
S4_BASE = 112
TICKETS = 20
TICKET_CAPACITY = 6
TRIPLE_SUPPORTS = 22
PAIR_SUPPORTS = 27
G_EDGES = 93
COMPLEMENT_TOTAL = 293
IDENTITY_CONSTANT = 233
SIGMA_SHIFT = 4
K6_SLOTS = 3
L_TICKETS = 4
NEXT_OWNER = "66665555555321100000"
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIRECTORY = "docs/research/matrix-native-results"
RESULT_STEM = "b649-next-two-t256-t258-certificate-seal-r1"
RESULT_PATH = ROOT / RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"

Pair = tuple[int, int]
Subset = tuple[int, ...]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def render(result: Mapping[str, object]) -> bytes:
    return (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()


def cast_mapping(value: object) -> Mapping[str, object]:
    require(isinstance(value, Mapping), "expected a mapping")
    return cast("Mapping[str, object]", value)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def expect_rejected(action: Callable[[], object]) -> str:
    """Run a negative control; it must raise, and the message is recorded."""
    try:
        action()
    except (AssertionError, ValueError, TypeError) as exc:
        return f"REJECTED: {type(exc).__name__}: {exc}"
    raise AssertionError("negative control was accepted")


# ---------------------------------------------------------------- provenance


def _relative_imports(module: ModuleType) -> list[str]:
    """Sibling modules named by ``from . import x`` or ``from .x import y``."""
    require(module.__file__ is not None, "module has no source")
    tree = ast.parse(Path(str(module.__file__)).read_text())
    package = module.__name__.rsplit(".", 1)[0]
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            if node.module:
                out.append(f"{package}.{node.module}")
            else:
                out.extend(f"{package}.{alias.name}" for alias in node.names)
    return out


def reused_modules() -> list[ModuleType]:
    """The native validators r5 and r32 and every lottolab module they import, transitively."""
    seen: dict[str, ModuleType] = {}
    stack = [r5, r32]
    while stack:
        module = stack.pop()
        if module.__name__ in seen:
            continue
        seen[module.__name__] = module
        stack.extend(sys.modules[name] for name in _relative_imports(module))
    return [seen[name] for name in sorted(seen)]


def module_provenance() -> dict[str, str]:
    """Every reused module equals its blob at the base commit, byte for byte."""
    require(git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE, "base tree")
    out: dict[str, str] = {}
    for module in reused_modules():
        source = Path(str(module.__file__)).resolve()
        require(source.is_relative_to(ROOT), f"reused module outside this worktree: {source}")
        relative = source.relative_to(ROOT).as_posix()
        committed = git("show", f"{BASE_HEAD}:{relative}")
        require(source.read_bytes() == committed, f"reused source changed: {relative}")
        out[relative] = sha256(committed)
    return out


def base_authority() -> dict[str, object]:
    """The 31-event base result, pinned by digest; read only for the old rows and frontier."""
    raw = git("show", f"{BASE_HEAD}:{BASE_RESULT_PATH}")
    require(sha256(raw) == BASE_RESULT_SHA256, "base result digest changed")
    require((ROOT / BASE_RESULT_PATH).read_bytes() == raw, "base result bytes drifted")
    result = json.loads(raw)
    require(isinstance(result, dict), "base result is not an object")
    fields = ("FAMILY_BOUND_AFTER", "MAXIMIZING_OWNERS", "NEXT_DISTINCT_BOUND")
    out: dict[str, object] = {k: result[k] for k in (*fields, "NEXT_DISTINCT_OWNERS")}
    require(
        out["MAXIMIZING_OWNERS"] == [PROFILE_A, PROFILE_B]
        and out["NEXT_DISTINCT_OWNERS"] == [NEXT_OWNER],
        "base frontier owners changed",
    )
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_PATH": BASE_RESULT_PATH,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "FORMAL_FAMILY_AUTHORITY": result["FORMAL_FAMILY_AUTHORITY"],
        **out,
    }


# ---------------------------------------------------------------- premises


def profile_values(profile: str) -> tuple[int, ...]:
    values = tuple(int(c) for c in profile)
    failures = r32.structural_failures(values)
    require(not failures, f"not a K20 min-S2 triple-degree profile {profile}: {failures}")
    return values


def sigma_cap(d: int, zeros: int) -> int:
    """Pair labels are the only route from a core ticket to Z."""
    return min(TICKET_CAPACITY - d, zeros)


def premises(profile: str) -> dict[str, object]:
    """Edge counts, both complement formulas, the identity constant and the variable ranges."""
    d = profile_values(profile)
    core = [v for v in d if v]
    k, z = len(core), d.count(0)
    g = [TICKET_CAPACITY + v for v in d]
    deg_h = [TICKETS - 1 - v for v in g]
    require(sum(g) % 2 == 0, "odd G degree sum")
    g_edges = sum(g) // 2
    h_edges = comb(TICKETS, 2) - g_edges
    inclusion = comb(TICKETS, 3) - (TICKETS - 2) * h_edges + sum(comb(v, 2) for v in deg_h)
    goodman = Fraction(comb(TICKETS, 3)) - Fraction(
        sum(a * b for a, b in zip(g, deg_h, strict=True)), 2
    )
    constant = (
        Fraction(COMPLEMENT_TOTAL)
        - Fraction(z * (k * (k - 7) - sum(core)), 2)
        - Fraction(k * z * (z - 7), 2)
    )
    linear = Fraction(k + z, 2) - 14
    caps = {v: sigma_cap(v, z) for v in sorted(set(core), reverse=True)}
    zeta = (TICKET_CAPACITY - (z - 1), TICKET_CAPACITY)
    require(
        g_edges == 3 * TRIPLE_SUPPORTS + PAIR_SUPPORTS == G_EDGES
        and h_edges == comb(TICKETS, 2) - G_EDGES
        and inclusion == goodman == COMPLEMENT_TOTAL
        and constant == IDENTITY_CONSTANT
        and linear == -SIGMA_SHIFT
        and sum(core) == 3 * TRIPLE_SUPPORTS,
        f"premises fail for {profile}",
    )
    return {
        "PROFILE_ID": profile,
        "CORE_VERTICES": k,
        "ZERO_VERTICES": z,
        "DEGREE_CLASSES": {str(v): n for v, n in sorted(Counter(core).items(), reverse=True)},
        "SUM_D_SQUARED": sum(v * v for v in d),
        "G_EDGES": g_edges,
        "H_EDGES": h_edges,
        "T_G_PLUS_T_H_INCLUSION_EXCLUSION": inclusion,
        "T_G_PLUS_T_H_GOODMAN": int(goodman),
        "IDENTITY_CONSTANT": int(constant),
        "LINEAR_R_COEFFICIENT": int(linear),
        "SIGMA_CAPS": {str(v): c for v, c in caps.items()},
        "ZETA_RANGE": list(zeta),
    }


def raw_objective(profile: str, sigma: Sequence[int], zeta: Sequence[int], p: int) -> Fraction:
    """293 - t(H), with t(H) from the mixed-apex count, before Sum sigma = Sum zeta is used."""
    d = profile_values(profile)
    core = [v for v in d if v]
    k, z = len(core), d.count(0)
    h = [k - 7 - v + s for v, s in zip(core, sigma, strict=True)]
    a = [v + z - 7 for v in zeta]
    t_h = (
        Fraction(z * sum(h), 2)
        + Fraction(k * sum(a), 2)
        - sum(s * x for s, x in zip(sigma, h, strict=True))
        - sum(v * x for v, x in zip(zeta, a, strict=True))
        + p
    )
    return COMPLEMENT_TOTAL - t_h


def closed_objective(profile: str, sigma: Sequence[int], zeta: Sequence[int], p: int) -> int:
    """233 + sum sigma(sigma-d-4) + sum zeta^2 - P."""
    core = [v for v in profile_values(profile) if v]
    return (
        IDENTITY_CONSTANT
        + sum(s * (s - v - SIGMA_SHIFT) for v, s in zip(core, sigma, strict=True))
        + sum(v * v for v in zeta)
        - p
    )


def identity_check(profile: str) -> dict[str, object]:
    """raw - closed = lambda (Sum sigma - Sum zeta) as separable quadratics, so equal on r=r."""
    d = profile_values(profile)
    k, z = len([v for v in d if v]), d.count(0)
    n = k + z + 1
    zero = [0] * n

    def difference(point: Sequence[int]) -> Fraction:
        sigma, zeta, p = point[:k], point[k : k + z], point[-1]
        return raw_objective(profile, sigma, zeta, p) - closed_objective(profile, sigma, zeta, p)

    slope = difference([1, *zero[1:]]) - difference(zero)
    points = [zero] + [[m if j == i else 0 for j in range(n)] for i in range(n) for m in (1, 2)]
    for point in points:
        balance = sum(point[:k]) - sum(point[k : k + z])
        require(difference(point) == slope * balance, f"identity fails at {point}")
    return {
        "FORM": "T=233+sum_K sigma(sigma-d-4)+sum_Z zeta^2-P",
        "P_DEFINITION": ("t(M)+t(H[Z])+sum_{xy in M}|N(x)&N(y)&Z|+sum_x e_{H[Z]}(N_Z(x)), M=H[K]"),
        "RAW_MINUS_CLOSED": f"{slope}*(sum sigma - sum zeta)",
        "SEPARABLE_POINTS_CHECKED": len(points),
        "STATUS": "EXACT_ON_SUM_SIGMA_EQUALS_SUM_ZETA",
    }


# ---------------------------------------------------------------- zero side


def zero_pairs(z: int) -> list[Pair]:
    return list(combinations(range(z), 2))


def all_subsets(z: int) -> list[Subset]:
    return [s for size in range(z + 1) for s in combinations(range(z), size)]


def triangles(vertices: Iterable[int], edges: set[Pair]) -> int:
    return sum(
        1
        for a, b, c in combinations(sorted(vertices), 3)
        if (a, b) in edges and (a, c) in edges and (b, c) in edges
    )


@dataclass(frozen=True)
class ZeroGraph:
    """G[Z] with zeta, the Z-only part of Phi, and e_{H[Z]}(S) for every S."""

    edges: tuple[Pair, ...]
    zeta: tuple[int, ...]
    base: int
    inside: Mapping[Subset, int]


def zero_graph(z: int, edges: Iterable[Pair], *, z_terms: bool = True) -> ZeroGraph:
    g = set(edges)
    pairs = set(zero_pairs(z))
    require(g <= pairs, "G[Z] edge outside Z")
    h = pairs - g
    zeta = tuple(TICKET_CAPACITY - sum(u in e for e in g) for u in range(z))
    inside = {
        s: sum(1 for e in combinations(s, 2) if e in h) if z_terms else 0 for s in all_subsets(z)
    }
    t_h = triangles(range(z), h) if z_terms else 0
    base = IDENTITY_CONSTANT + sum(v * v for v in zeta) - t_h
    return ZeroGraph(tuple(sorted(g)), zeta, base, inside)


def gain(d: int, s: Subset, graph: ZeroGraph) -> int:
    """sigma(sigma-d-4) - e_{H[Z]}(N_Z(x)) for one core ticket with N_Z(x)=s."""
    return len(s) * (len(s) - d - SIGMA_SHIFT) - graph.inside[s]


def zero_side_dp(profile: str, *, z_terms: bool = True) -> dict[str, object]:
    """Implementation 1: every labelled G[Z], DP over residual column demand."""
    d = profile_values(profile)
    z = d.count(0)
    pairs = zero_pairs(z)
    movers = sorted(
        ((v, sigma_cap(v, z)) for v in d if v and sigma_cap(v, z)), key=lambda t: (-t[1], t[0])
    )
    room = [sum(c for _, c in movers[i:]) for i in range(len(movers) + 1)]
    subsets = all_subsets(z)
    done = (0,) * z
    best: dict[int, int] = {}
    for mask in range(1 << len(pairs)):
        graph = zero_graph(
            z, (pairs[i] for i in range(len(pairs)) if mask >> i & 1), z_terms=z_terms
        )
        if sum(graph.zeta) > room[0]:
            continue
        states = {graph.zeta: 0}
        for i, (v, cap) in enumerate(movers):
            options = [(s, gain(v, s, graph)) for s in subsets if len(s) <= cap]
            nxt: dict[tuple[int, ...], int] = {}
            for residual, value in states.items():
                for s, extra in options:
                    if any(residual[u] == 0 for u in s):
                        continue
                    new = list(residual)
                    for u in s:
                        new[u] -= 1
                    if sum(new) > room[i + 1]:
                        continue
                    key = tuple(new)
                    if nxt.get(key, value + extra - 1) < value + extra:
                        nxt[key] = value + extra
            states = nxt
        if done in states:
            best[mask] = graph.base + states[done]
    top = max(best.values())
    return {
        "LABELLED_GRAPHS": 1 << len(pairs),
        "FEASIBLE_GRAPHS": len(best),
        "MAX_PHI": top,
        "ARGMAX_GRAPH_COUNT": sum(1 for v in best.values() if v == top),
        "GRAPHS_ABOVE_CLAIMED_CAP": sum(1 for v in best.values() if v > CLAIMED_CAPS[profile]),
        "PER_GRAPH_MAX_SHA256": digest(sorted(best.items())),
    }


def iso_classes(z: int) -> list[tuple[Pair, ...]]:
    """Canonical (lexicographically least) edge list of every isomorphism class of G[Z]."""
    pairs = zero_pairs(z)
    out: set[tuple[Pair, ...]] = set()
    for mask in range(1 << len(pairs)):
        edges = [pairs[i] for i in range(len(pairs)) if mask >> i & 1]
        out.add(
            min(
                tuple(sorted((min(p[a], p[b]), max(p[a], p[b])) for a, b in edges))
                for p in permutations(range(z))
            )
        )
    return sorted(out)


@dataclass(frozen=True)
class ZeroState:
    """One G[Z] class with N_Z sets for every sigma>=2-capable ticket; d5 absorbs the rest."""

    phi: int
    edges: tuple[Pair, ...]
    zeta: tuple[int, ...]
    choices: tuple[tuple[int, tuple[Subset, ...]], ...]
    residual: tuple[int, ...]

    def sets(self, d: int) -> tuple[Subset, ...]:
        return dict(self.choices)[d]

    def row(self) -> list[object]:
        return [
            self.phi,
            [list(e) for e in self.edges],
            list(self.zeta),
            [[v, [list(s) for s in sets]] for v, sets in self.choices],
            list(self.residual),
        ]


ChoiceOption = tuple[tuple[Subset, ...], list[int], int]


@dataclass(frozen=True)
class Walk:
    """Depth-first choice of N_Z multisets per degree class; the d5 class takes the residual."""

    edges: tuple[Pair, ...]
    zeta: tuple[int, ...]
    multi: list[int]
    options: list[list[ChoiceOption]]
    unit: int
    unit_count: int

    def states(
        self, level: int, residual: list[int], value: int, chosen: list[tuple[Subset, ...]]
    ) -> Iterator[ZeroState]:
        if level == len(self.multi):
            if sum(residual) <= self.unit_count:
                phi = value + sum(residual) * (1 - self.unit - SIGMA_SHIFT)
                choices = tuple(zip(self.multi, chosen, strict=True))
                yield ZeroState(phi, self.edges, self.zeta, choices, tuple(residual))
            return
        for sets, used, extra in self.options[level]:
            rest = [a - b for a, b in zip(residual, used, strict=True)]
            if min(rest) >= 0:
                yield from self.states(level + 1, rest, value + extra, [*chosen, sets])


def zero_side_states(profile: str, *, z_terms: bool = True) -> Iterator[ZeroState]:
    """Implementation 2: explicit states over isomorphism classes of G[Z]."""
    d = profile_values(profile)
    z = d.count(0)
    counts = Counter(v for v in d if v)
    caps = {v: sigma_cap(v, z) for v in counts}
    units = [v for v in counts if caps[v] == 1]
    require(len(units) == 1, "expected exactly one sigma<=1 class to absorb the residual")
    unit = units[0]
    multi = sorted(v for v in counts if caps[v] >= 2)
    subsets = all_subsets(z)
    for edges in iso_classes(z):
        graph = zero_graph(z, edges, z_terms=z_terms)
        options: list[list[ChoiceOption]] = [
            [
                (
                    sets,
                    [sum(u in s for s in sets) for u in range(z)],
                    sum(gain(v, s, graph) for s in sets),
                )
                for sets in combinations_with_replacement(
                    [s for s in subsets if len(s) <= caps[v]], counts[v]
                )
            ]
            for v in multi
        ]

        start = Walk(edges, graph.zeta, multi, options, unit, counts[unit])
        yield from start.states(0, list(graph.zeta), graph.base, [])


def state_text(state: ZeroState, lb: int | None = None, *, k_side: bool = False) -> str:
    """One readable line per state: Phi, G[Z], zeta, N_Z multisets, d5 residual (and LB)."""
    choices = " ".join(
        f"D{v}=" + "|".join("".join(map(str, s)) or "-" for s in sets) for v, sets in state.choices
    )
    text = (
        f"PHI={state.phi} GZ={','.join(f'{a}{b}' for a, b in state.edges) or '-'} "
        f"ZETA={''.join(map(str, state.zeta))} {choices} D5={''.join(map(str, state.residual))}"
    )
    if k_side:
        bound = "ILLEGAL" if lb is None else str(state.phi - lb)
        text = f"BOUND={bound} LB={lb} {text}"
    return text


def separable_maximum(profile: str) -> int:
    """Ablation: drop crossing balance and every Z part; each ticket and zero is independent."""
    d = profile_values(profile)
    z = d.count(0)
    return (
        IDENTITY_CONSTANT
        + z * TICKET_CAPACITY**2
        + sum(max(s * (s - v - SIGMA_SHIFT) for s in range(sigma_cap(v, z) + 1)) for v in d if v)
    )


def certify_a(cap: int = CLAIMED_CAPS[PROFILE_A]) -> tuple[dict[str, object], int]:
    """Both implementations agree on max Phi for A, and no state exceeds the cap."""
    dp = zero_side_dp(PROFILE_A)
    count, top, above = 0, -(10**9), 0
    argmax: list[ZeroState] = []
    for state in zero_side_states(PROFILE_A):
        count += 1
        above += state.phi > cap
        if state.phi > top:
            top, argmax = state.phi, [state]
        elif state.phi == top:
            argmax.append(state)
    require(dp["MAX_PHI"] == top, "zero-side implementations disagree for A")
    require(top <= cap, f"A zero-side maximum {top} exceeds the claimed cap {cap}")
    return {
        "DP_ALL_LABELLED_GRAPHS": dp,
        "EXPLICIT_ISO_CLASSES": len(iso_classes(profile_values(PROFILE_A).count(0))),
        "EXPLICIT_STATES": count,
        "EXPLICIT_MAX_PHI": top,
        "EXPLICIT_STATES_ABOVE_CLAIMED_CAP": above,
        "EXPLICIT_ARGMAX_STATES": sorted(state_text(s) for s in argmax),
        "CERTIFIED_T_MAX": top,
        "CLAIMED_CAP": cap,
        "STATUS": "PROVEN",
    }, top


# ---------------------------------------------------------------- B K side


@dataclass(frozen=True)
class HiType:
    """HI tickets that look alike to every L ticket: count, deg_{G[K]} and N_Z overlaps."""

    name: str
    count: int
    degree: int
    overlap: tuple[int, ...]
    is_c: bool = False
    is_free: bool = False
    is_k6: bool = False


@dataclass(frozen=True)
class BShape:
    """Profile B: |K|, the d=1 tickets L, d5 and d6 counts, and c (d=4)."""

    core: int
    l_count: int
    d5_count: int
    d6_count: int
    c_degree: int


def b_shape() -> BShape:
    counts = Counter(profile_values(PROFILE_B))
    require(
        counts == Counter({6: 3, 5: 8, 4: 1, 1: L_TICKETS, 0: 4}),
        "K-side certificate is stated for profile B only",
    )
    return BShape(TICKETS - counts[0], counts[1], counts[5], counts[6], 4)


def set_partitions(items: Sequence[int]) -> Iterator[list[tuple[int, ...]]]:
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for part in set_partitions(rest):
        for i, block in enumerate(part):
            yield [*part[:i], (first, *block), *part[i + 1 :]]
        yield [(first,), *part]


def hi_types(
    l_sets: Sequence[Subset], c_set: Subset, residual: Sequence[int], shape: BShape
) -> list[HiType]:
    """c, d5 at each zero u, d5 with sigma=0 and d6, with deg_{G[K]}=6+d-sigma."""
    nothing = (0,) * len(l_sets)
    c_degree = TICKET_CAPACITY + shape.c_degree - len(c_set)
    out = [HiType("C", 1, c_degree, tuple(len(set(s) & set(c_set)) for s in l_sets), is_c=True)]
    for u, n in enumerate(residual):
        if n:
            out.append(
                HiType(f"K5@{u}", n, TICKET_CAPACITY + 5 - 1, tuple(int(u in s) for s in l_sets))
            )
    free = shape.d5_count - sum(residual)
    require(free >= 0, "more d5 tickets at Z than exist")
    if free:
        out.append(HiType("K5_FREE", free, TICKET_CAPACITY + 5, nothing, is_free=True))
    out.append(HiType("K6", shape.d6_count, TICKET_CAPACITY + 6, nothing, is_k6=True))
    return out


Option = tuple[int, int, tuple[int, ...]]


def pareto(options: Iterable[Option]) -> list[Option]:
    """Drop o when another option has at least as many d6 slots and no larger c_Z or t_M."""
    unique = sorted(set(options))
    return [
        o
        for o in unique
        if not any(
            q != o
            and q[0] >= o[0]
            and q[1] <= o[1]
            and all(a <= b for a, b in zip(q[2], o[2], strict=True))
            for q in unique
        )
    ]


def k_side_lower_bound_reference(
    l_sets: Sequence[Subset],
    c_set: Subset,
    residual: Sequence[int],
    r: int,
    *,
    k6_slots: int | None = None,
) -> int | None:
    """Reference: min over local L structures of c_Z(L pairs) + Bonferroni t(M); None if none."""
    shape = b_shape()
    slots = K6_SLOTS if k6_slots is None else k6_slots
    z = len(residual)
    nl = len(l_sets)
    require(nl == shape.l_count and r % 2 == 0, "malformed B state")
    sigma = [len(s) for s in l_sets]
    g_l = [TICKET_CAPACITY + 1 - s for s in sigma]
    room = [TICKET_CAPACITY - 1 - s for s in sigma]
    h_l = [shape.core - 1 - g for g in g_l]
    k_edges = G_EDGES - r - (TICKET_CAPACITY * z - r) // 2
    c_room = TICKET_CAPACITY - shape.c_degree - len(c_set)
    types = hi_types(l_sets, c_set, residual, shape)
    c_type = types[0]
    free = sum(t.count for t in types if t.is_free)
    free_degree = TICKET_CAPACITY + 5
    weight = [sum(t.count * t.overlap[y] for t in types) for y in range(nl)]
    l_pairs = list(combinations(range(nl), 2))
    shared = {(a, b): len(set(l_sets[a]) & set(l_sets[b])) for a, b in l_pairs}
    penalty = {(a, b): max(0, shape.core - 2 - max(g_l[a], g_l[b])) for a, b in l_pairs}
    groups = [s for size in range(1, nl + 1) for s in combinations(range(nl), size)]
    combos = {
        need: [
            combo
            for combo in combinations_with_replacement(range(len(types)), need)
            if all(n <= types[t].count for t, n in Counter(combo).items())
        ]
        for need in range(3)
    }
    best: int | None = None
    for part in set_partitions(list(range(nl))):
        if max(len(b) for b in part) > 3:
            continue
        block_of = {y: i for i, b in enumerate(part) for y in b}
        cross = [p for p in l_pairs if block_of[p[0]] != block_of[p[1]]]
        for mask in range(1 << len(cross)):
            ep = [cross[i] for i in range(len(cross)) if mask >> i & 1]
            ep_deg = [sum(y in e for e in ep) for y in range(nl)]
            if any(ep_deg[y] > room[y] for y in range(nl)):
                continue
            adjacent = set(ep) | {p for p in l_pairs if block_of[p[0]] == block_of[p[1]]}
            apart = [p for p in l_pairs if p not in adjacent]
            cz_ll = sum(shared[p] for p in apart)
            partners = {y: [b if a == y else a for a, b in ep if y in (a, b)] for y in range(nl)}
            for cmask in range(1 << nl):
                cp = {y for y in range(nl) if cmask >> y & 1}
                if len(cp) > c_room or any(ep_deg[y] + 1 > room[y] for y in cp):
                    continue
                rest = [room[y] - ep_deg[y] - (y in cp) for y in range(nl)]
                if sum(rest) > free:
                    continue
                per_block: list[tuple[tuple[int, ...], list[Option]]] = []
                for block in part:
                    options: list[Option] = []
                    for combo in combos[3 - len(block)]:
                        members = [types[t] for t in combo]
                        if any(t.is_c for t in members) and cp & set(block):
                            continue
                        n_free = sum(t.is_free for t in members)
                        if any(n_free + rest[y] > free for y in block):
                            continue
                        cz = 0
                        bounds: list[int] = []
                        for y in block:
                            cz += weight[y] - sum(t.overlap[y] for t in members)
                            cz -= c_type.overlap[y] if y in cp else 0
                            l_near = [w for w in block if w != y] + partners[y]
                            degrees = [g_l[w] for w in l_near] + [t.degree for t in members]
                            degrees += [c_type.degree] * (y in cp) + [free_degree] * rest[y]
                            n = len(degrees)
                            require(n == g_l[y], "L neighbourhood size differs from 7-sigma")
                            known = sum(
                                1 for p in combinations(sorted(l_near), 2) if p not in adjacent
                            )
                            inner = min(
                                comb(n, 2) - known, sum(min(n - 1, g - 1) for g in degrees) // 2
                            )
                            bounds.append(comb(h_l[y], 2) - k_edges + sum(degrees) - inner)
                        options.append((sum(t.is_k6 for t in members), cz, tuple(bounds)))
                    if not options:
                        break
                    per_block.append((block, pareto(options)))
                else:
                    for choice in product(*(o for _, o in per_block)):
                        if sum(o[0] for o in choice) < slots:
                            continue
                        local = [0] * nl
                        for (block, _), o in zip(per_block, choice, strict=True):
                            for y, v in zip(block, o[2], strict=True):
                                local[y] = v
                        t_m = max(
                            0,
                            *(
                                sum(local[y] for y in s)
                                - sum(penalty[p] for p in combinations(s, 2) if p in apart)
                                for s in groups
                            ),
                        )
                        value = cz_ll + sum(o[1] for o in choice) + t_m
                        if best is None or value < best:
                            best = value
    return best


def generic_lemma_check(seed: int = 11, trials: int = 300) -> dict[str, object]:
    """Random graphs: the per-vertex t_M identity, the e_G(N) cap and the Bonferroni bound.

    Here the whole random graph plays G[K] and its complement plays M.
    """
    rng = random.Random(seed)
    vertices_checked = 0
    for _ in range(trials):
        n = rng.randint(6, 16)
        density = rng.random()
        g = {e for e in combinations(range(n), 2) if rng.random() < density}
        m = set(combinations(range(n), 2)) - g
        nb = {v: {w for w in range(n) if w != v and edge(v, w) in g} for v in range(n)}
        m_triangles = [t for t in combinations(range(n), 3) if set(combinations(t, 2)) <= m]
        per: dict[int, int] = {}
        for y in range(n):
            near = sorted(nb[y])
            far = [w for w in range(n) if w != y and w not in nb[y]]
            k = len(near)
            inner = sum(1 for e in combinations(near, 2) if e in g)
            non_edges = [e for e in combinations(near, 2) if e not in g]
            known = rng.randint(0, len(non_edges))
            per[y] = sum(1 for t in m_triangles if y in t)
            require(
                per[y] == comb(len(far), 2) - len(g) + sum(len(nb[w]) for w in near) - inner,
                "per-vertex t_M identity fails",
            )
            require(
                inner
                <= min(comb(k, 2) - known, sum(min(k - 1, len(nb[w]) - 1) for w in near) // 2),
                "e_G(N) cap fails",
            )
            vertices_checked += 1
        group = rng.sample(range(n), 4)
        union = sum(1 for t in m_triangles if set(t) & set(group))
        pair_cost = sum(
            max(0, n - 2 - max(len(nb[a]), len(nb[b])))
            for a, b in combinations(group, 2)
            if (a, b) in m or (b, a) in m
        )
        require(union >= sum(per[y] for y in group) - pair_cost, "Bonferroni pair bound fails")
    return {"SEED": seed, "GRAPHS": trials, "VERTICES": vertices_checked, "STATUS": "PASS"}


def canonical_b_key(
    l_sets: Sequence[Subset], c_set: Subset, residual: Sequence[int], r: int
) -> tuple[tuple[Subset, ...], Subset, tuple[int, ...], int]:
    """The K-side bound depends on the state only up to relabelling Z (and r)."""
    z = len(residual)
    keys: list[tuple[tuple[Subset, ...], Subset, tuple[int, ...], int]] = []
    for p in permutations(range(z)):
        inverse = [p.index(i) for i in range(z)]
        keys.append(
            (
                tuple(sorted(tuple(sorted(p[u] for u in s)) for s in l_sets)),
                tuple(sorted(p[u] for u in c_set)),
                tuple(residual[inverse[i]] for i in range(z)),
                r,
            )
        )
    return min(keys)


def k_side_lower_bound(
    l_sets: Sequence[Subset],
    c_set: Subset,
    residual: Sequence[int],
    r: int,
    *,
    k6_slots: int | None = None,
) -> int | None:
    """The reference bound, with block options memoised and a monotone pruning floor.

    Each block's options depend only on its own members' pairing data, so they are cached
    on exactly those inputs. Before the product over blocks, the value is bounded below by
    taking every block coordinate at its minimum; if that floor is not below the best value,
    no choice can improve it. Both steps leave the minimum unchanged.
    """
    shape = b_shape()
    slots = K6_SLOTS if k6_slots is None else k6_slots
    z = len(residual)
    nl = len(l_sets)
    require(nl == shape.l_count and r % 2 == 0, "malformed B state")
    sigma = [len(s) for s in l_sets]
    g_l = [TICKET_CAPACITY + 1 - s for s in sigma]
    room = [TICKET_CAPACITY - 1 - s for s in sigma]
    h_pairs = [comb(shape.core - 1 - g, 2) for g in g_l]
    k_edges = G_EDGES - r - (TICKET_CAPACITY * z - r) // 2
    c_room = TICKET_CAPACITY - shape.c_degree - len(c_set)
    types = hi_types(l_sets, c_set, residual, shape)
    c_type = types[0]
    free = sum(t.count for t in types if t.is_free)
    free_degree = TICKET_CAPACITY + 5
    weight = [sum(t.count * t.overlap[y] for t in types) for y in range(nl)]
    l_pairs = list(combinations(range(nl), 2))
    shared = {(a, b): len(set(l_sets[a]) & set(l_sets[b])) for a, b in l_pairs}
    penalty = {(a, b): max(0, shape.core - 2 - max(g_l[a], g_l[b])) for a, b in l_pairs}
    groups = [s for size in range(1, nl + 1) for s in combinations(range(nl), size)]
    combos = {
        need: [
            (
                sum(types[t].is_k6 for t in combo),
                sum(types[t].is_free for t in combo),
                any(types[t].is_c for t in combo),
                [sum(types[t].overlap[y] for t in combo) for y in range(nl)],
                sum(types[t].degree for t in combo),
                [sum(min(g_l[y] - 1, types[t].degree - 1) for t in combo) for y in range(nl)],
            )
            for combo in combinations_with_replacement(range(len(types)), need)
            if all(n <= types[t].count for t, n in Counter(combo).items())
        ]
        for need in range(3)
    }
    cache: dict[tuple[object, ...], list[Option]] = {}

    def block_options(
        block: tuple[int, ...], cp: set[int], rest: list[int], pre: tuple[tuple[int, int, int], ...]
    ) -> list[Option]:
        key = (block, tuple(y in cp for y in block), tuple(rest[y] for y in block), pre)
        if key in cache:
            return cache[key]
        paired = bool(cp & set(block))
        options: list[Option] = []
        for k6, n_free, has_c, overlap, degree, low in combos[3 - len(block)]:
            if (has_c and paired) or any(n_free + rest[y] > free for y in block):
                continue
            cz = 0
            bounds: list[int] = []
            for y, (base_sum, base_low, known) in zip(block, pre, strict=True):
                cz += weight[y] - overlap[y] - (c_type.overlap[y] if y in cp else 0)
                n = g_l[y]
                inner = min(comb(n, 2) - known, (base_low + low[y]) // 2)
                bounds.append(h_pairs[y] - k_edges + base_sum + degree - inner)
            options.append((k6, cz, tuple(bounds)))
        cache[key] = pareto(options)
        return cache[key]

    best: int | None = None
    for part in set_partitions(list(range(nl))):
        if max(len(b) for b in part) > 3:
            continue
        block_of = {y: i for i, b in enumerate(part) for y in b}
        cross = [p for p in l_pairs if block_of[p[0]] != block_of[p[1]]]
        for mask in range(1 << len(cross)):
            ep = [cross[i] for i in range(len(cross)) if mask >> i & 1]
            ep_deg = [sum(y in e for e in ep) for y in range(nl)]
            if any(ep_deg[y] > room[y] for y in range(nl)):
                continue
            adjacent = set(ep) | {p for p in l_pairs if block_of[p[0]] == block_of[p[1]]}
            apart = [p for p in l_pairs if p not in adjacent]
            cz_ll = sum(shared[p] for p in apart)
            cost = [sum(penalty[p] for p in combinations(s, 2) if p in apart) for s in groups]
            near = {
                y: [w for w in part[block_of[y]] if w != y]
                + [b if a == y else a for a, b in ep if y in (a, b)]
                for y in range(nl)
            }
            known = {
                y: sum(1 for p in combinations(sorted(near[y]), 2) if p not in adjacent)
                for y in range(nl)
            }
            for cmask in range(1 << nl):
                cp = {y for y in range(nl) if cmask >> y & 1}
                if len(cp) > c_room or any(ep_deg[y] + 1 > room[y] for y in cp):
                    continue
                rest = [room[y] - ep_deg[y] - (y in cp) for y in range(nl)]
                if sum(rest) > free:
                    continue
                per_block: list[tuple[tuple[int, ...], list[Option]]] = []
                for block in part:
                    pre: list[tuple[int, int, int]] = []
                    for y in block:
                        base = [g_l[w] for w in near[y]]
                        base += [c_type.degree] * (y in cp) + [free_degree] * rest[y]
                        require(
                            len(base) + 3 - len(block) == g_l[y],
                            "L neighbourhood size differs from 7-sigma",
                        )
                        low = sum(min(g_l[y] - 1, g - 1) for g in base)
                        pre.append((sum(base), low, known[y]))
                    options = block_options(block, cp, rest, tuple(pre))
                    if not options:
                        break
                    per_block.append((block, options))
                else:
                    floor_local = [0] * nl
                    floor_cz = cz_ll
                    for block, options in per_block:
                        floor_cz += min(o[1] for o in options)
                        for i, y in enumerate(block):
                            floor_local[y] = min(o[2][i] for o in options)
                    floor = floor_cz + max(
                        0,
                        *(
                            sum(floor_local[y] for y in s) - c
                            for s, c in zip(groups, cost, strict=True)
                        ),
                    )
                    if best is not None and floor >= best:
                        continue
                    for choice in product(*(o for _, o in per_block)):
                        if sum(o[0] for o in choice) < slots:
                            continue
                        local = [0] * nl
                        for (block, _), o in zip(per_block, choice, strict=True):
                            for y, v in zip(block, o[2], strict=True):
                                local[y] = v
                        t_m = max(
                            0,
                            *(
                                sum(local[y] for y in s) - c
                                for s, c in zip(groups, cost, strict=True)
                            ),
                        )
                        value = cz_ll + sum(o[1] for o in choice) + t_m
                        if best is None or value < best:
                            best = value
    return best


def b_rows(threshold: int, *, k6_slots: int | None = None) -> list[tuple[ZeroState, int | None]]:
    """Every B zero-side state with Phi>threshold and its K-side lower bound (None: illegal)."""
    cache: dict[tuple[object, ...], int | None] = {}
    out: list[tuple[ZeroState, int | None]] = []
    for state in zero_side_states(PROFILE_B):
        if state.phi <= threshold:
            continue
        key = canonical_b_key(state.sets(1), state.sets(4)[0], state.residual, sum(state.zeta))
        if key not in cache:
            cache[key] = k_side_lower_bound(*key, k6_slots=k6_slots)
        out.append((state, cache[key]))
    return out


def worst_bound(rows: Sequence[tuple[ZeroState, int | None]]) -> int:
    return max(state.phi - lb for state, lb in rows if lb is not None)


def b_main_certificate(
    cap: int = CLAIMED_CAPS[PROFILE_B], *, k6_slots: int | None = None
) -> list[tuple[ZeroState, int | None]]:
    """Every state with Phi above the cap drops to the cap or below after the K-side bound."""
    rows = b_rows(cap, k6_slots=k6_slots)
    worst = worst_bound(rows)
    require(worst <= cap, f"B K-side certificate leaves {worst} above the claimed cap {cap}")
    return rows


def histogram(values: Iterable[int], top: int = 10) -> dict[str, int]:
    return {str(v): n for v, n in sorted(Counter(values).items(), reverse=True)[:top]}


def certify_b(
    cap: int = CLAIMED_CAPS[PROFILE_B], extended: int = 239
) -> tuple[dict[str, object], int, int]:
    """Zero side (two implementations), main K-side certificate, and the extended one."""
    dp = zero_side_dp(PROFILE_B)
    phis = [state.phi for state in zero_side_states(PROFILE_B)]
    require(dp["MAX_PHI"] == max(phis), "zero-side implementations disagree for B")
    rows = b_rows(extended)
    main = [(s, lb) for s, lb in rows if s.phi > cap]
    worst_main, worst_all = worst_bound(main), worst_bound(rows)
    require(worst_main <= cap, f"B K-side certificate leaves {worst_main} above {cap}")
    require(worst_all <= extended, f"extended B certificate leaves {worst_all} above {extended}")
    main_rows = sorted(main, key=lambda row: (row[0].phi, row[0].row()))
    bounds = [s.phi - lb for s, lb in rows if lb is not None]
    return (
        {
            "DP_ALL_LABELLED_GRAPHS": dp,
            "EXPLICIT_ISO_CLASSES": len(iso_classes(profile_values(PROFILE_B).count(0))),
            "EXPLICIT_STATES": len(phis),
            "EXPLICIT_MAX_PHI": max(phis),
            "STATES_ABOVE_CLAIMED_CAP": len(main),
            "STATES_AT_CLAIMED_CAP": phis.count(cap),
            "MAIN_LOCALLY_ILLEGAL": sum(1 for _, lb in main if lb is None),
            "MAIN_DISTINCT_K_SIDE_KEYS": len(
                {canonical_b_key(s.sets(1), s.sets(4)[0], s.residual, sum(s.zeta)) for s, _ in main}
            ),
            "MAIN_WORST_BOUND": worst_main,
            "MAIN_BOUND_HISTOGRAM": histogram(s.phi - lb for s, lb in main if lb is not None),
            "MAIN_ROWS": [state_text(s, lb, k_side=True) for s, lb in main_rows],
            "MAIN_ROWS_SHA256": digest([[*s.row(), lb] for s, lb in main_rows]),
            "EXTENDED_THRESHOLD": extended,
            "EXTENDED_STATES": len(rows),
            "EXTENDED_LOCALLY_ILLEGAL": sum(1 for _, lb in rows if lb is None),
            "EXTENDED_WORST_BOUND": worst_all,
            "EXTENDED_BOUND_HISTOGRAM": histogram(bounds),
            "EXTENDED_ROWS_SHA256": digest(sorted([*s.row(), lb] for s, lb in rows)),
            "CERTIFIED_T_MAX": max(extended, worst_all),
            "CLAIMED_CAP": cap,
            "STATUS": "PROVEN",
        },
        max(extended, worst_all),
        max(phis),
    )


def cap_supported(certified: int, cap: int) -> None:
    require(certified <= cap, f"certificate maximum {certified} does not support T<={cap}")


# ---------------------------------------------------------------- realizations


def edge(a: int, b: int) -> Pair:
    return (a, b) if a < b else (b, a)


def build_realization(
    profile: str, rng: random.Random, l_sigma: Sequence[int] = ()
) -> tuple[list[Support], list[Pair]] | None:
    """Greedy random support structure; l_sigma forces sigma for the d=1 tickets."""
    d = profile_values(profile)
    remaining = list(d)
    used: set[Pair] = set()
    triples: list[Support] = []
    while sum(remaining):
        live = [v for v in range(TICKETS) if remaining[v] > 0]
        v = max(live, key=lambda x: (remaining[x], rng.random()))
        others = [w for w in live if w != v and edge(v, w) not in used]
        rng.shuffle(others)
        others.sort(key=lambda x: -remaining[x] + rng.random() * 2)
        for a, b in combinations(others[:12], 2):
            if edge(a, b) not in used:
                triple = tuple(sorted((v, a, b)))
                used.update(edge(x, y) for x, y in combinations(triple, 2))
                for x in triple:
                    remaining[x] -= 1
                triples.append(triple)
                break
        else:
            return None
    spare = [TICKET_CAPACITY - v for v in d]
    pairs: list[Pair] = []
    zeros = [v for v in range(TICKETS) if not d[v]]
    l_tickets = [v for v in range(TICKETS) if d[v] == 1]
    for y, target in zip(l_tickets[: len(l_sigma)], l_sigma, strict=True):
        for u in rng.sample(zeros, target):
            pairs.append(edge(y, u))
            used.add(edge(y, u))
            spare[y] -= 1
            spare[u] -= 1
    while sum(spare):
        live = [v for v in range(TICKETS) if spare[v] > 0]
        v = max(live, key=lambda x: (spare[x], rng.random()))
        others = [w for w in live if w != v and edge(v, w) not in used]
        if not others:
            return None
        w = max(others, key=lambda x: (spare[x], rng.random()))
        pairs.append(edge(v, w))
        used.add(edge(v, w))
        spare[v] -= 1
        spare[w] -= 1
    if len(triples) != TRIPLE_SUPPORTS or len(pairs) != PAIR_SUPPORTS or min(spare) < 0:
        return None
    return triples, pairs


def first_realization(profile: str, seed: int) -> tuple[list[Support], list[Pair]]:
    rng = random.Random(seed)
    for _ in range(200_000):
        built = build_realization(profile, rng)
        if built is not None:
            return built
    raise AssertionError("realization builder did not converge")


def identity_holds(
    profile: str, sigma: Sequence[int], zeta: Sequence[int], parts: Sequence[int], t: int
) -> None:
    """The closed identity on observed data: balance, ranges, P>=0 and T exactly."""
    d = profile_values(profile)
    z = d.count(0)
    core = [v for v in d if v]
    require(sum(sigma) == sum(zeta), "crossing balance fails: sum sigma != sum zeta")
    require(
        all(0 <= s <= sigma_cap(v, z) for v, s in zip(core, sigma, strict=True))
        and all(TICKET_CAPACITY - (z - 1) <= v <= TICKET_CAPACITY for v in zeta),
        "sigma or zeta outside its range",
    )
    require(min(parts) >= 0, "a P term is negative")
    require(t == closed_objective(profile, sigma, zeta, sum(parts)), "identity fails")


@dataclass(frozen=True)
class Observation:
    """What one r5-legal realization shows: T, sigma, zeta, the four P terms and Phi."""

    t: int
    sigma: list[int]
    zeta: list[int]
    parts: list[int]
    phi: int
    local: dict[int, Subset]
    n_z: dict[int, set[int]]


def observe(profile: str, triples: Sequence[Support], pairs: Sequence[Pair]) -> Observation:
    """Validate with r5, then count everything directly and check the complement split."""
    d = profile_values(profile)
    r5.validate_k20_support_realization(triples, pairs, d)
    g = {edge(a, b) for s in (*triples, *pairs) for a, b in combinations(s, 2)}
    h = set(combinations(range(TICKETS), 2)) - g
    nb = {v: {w for w in range(TICKETS) if w != v and edge(v, w) in g} for v in range(TICKETS)}
    core = [v for v in range(TICKETS) if d[v]]
    zero = [v for v in range(TICKETS) if not d[v]]
    ks, zs = set(core), set(zero)
    m = {e for e in h if e[0] in ks and e[1] in ks}
    mz = {e for e in h if e[0] in zs and e[1] in zs}
    n_z = {x: nb[x] & zs for x in core}
    sigma = [len(n_z[x]) for x in core]
    zeta = [len(nb[u] & ks) for u in zero]
    parts = [
        triangles(core, m),
        triangles(zero, mz),
        sum(len(nb[x] & nb[y] & zs) for x, y in m),
        sum(sum(1 for e in combinations(sorted(n_z[x]), 2) if e in mz) for x in core),
    ]
    t_g, t_h = triangles(range(TICKETS), g), triangles(range(TICKETS), h)
    deg_m = [sum(x in e for e in m) for x in core]
    deg_mz = [sum(u in e for e in mz) for u in zero]
    mixed = (
        len(zero) * len(m)
        + len(core) * len(mz)
        - sum(a * b for a, b in zip(sigma, deg_m, strict=True))
        - sum(a * b for a, b in zip(zeta, deg_mz, strict=True))
        + sum(parts)
    )
    require(
        len(g) == G_EDGES
        and t_g + t_h == COMPLEMENT_TOTAL
        and t_h == mixed
        and parts[3] == sum(len(nb[u] & nb[w] & ks) for u, w in mz)
        and all(v == TICKET_CAPACITY - len(nb[u] & zs) for u, v in zip(zero, zeta, strict=True)),
        "complement split fails on a realization",
    )
    index = {u: i for i, u in enumerate(zero)}
    graph = zero_graph(len(zero), [(index[a], index[b]) for a, b in g if a in zs and b in zs])
    local = {x: tuple(sorted(index[u] for u in n_z[x])) for x in core}
    phi = graph.base + sum(gain(d[x], local[x], graph) for x in core)
    return Observation(t_g, sigma, zeta, parts, phi, local, n_z)


def realization_check(
    profile: str, triples: Sequence[Support], pairs: Sequence[Pair]
) -> dict[str, int]:
    """Identity and Phi on a legal structure; for B also the K-side lemmas and P_K>=LB."""
    d = profile_values(profile)
    seen = observe(profile, triples, pairs)
    identity_holds(profile, seen.sigma, seen.zeta, seen.parts, seen.t)
    p_k = seen.parts[0] + seen.parts[2]
    require(seen.t == seen.phi - p_k, "T != Phi - P_K on a realization")
    out = {"T": seen.t, "PHI": seen.phi, "P": sum(seen.parts), "P_K": p_k, "R": sum(seen.zeta)}
    if profile == PROFILE_B:
        core = [v for v in range(TICKETS) if d[v]]
        l_tickets = [v for v in core if d[v] == 1]
        c = next(v for v in core if d[v] == b_shape().c_degree)
        partners = {y: [b if a == y else a for a, b in pairs if y in (a, b)] for y in l_tickets}
        require(
            not any(
                d[x] == 6 or (d[x] == 5 and seen.n_z[x]) for y in l_tickets for x in partners[y]
            ),
            "a d6 ticket or a sigma=1 d5 ticket is a pair partner of an L ticket",
        )
        l_triples = [t for t in triples if set(t) & set(l_tickets)]
        require(
            all(any(x in t for t in l_triples) for x in core if d[x] == 6),
            "a d6 ticket lies in no L triple",
        )
        zero_count = d.count(0)
        residual = [
            sum(1 for x in core if d[x] == 5 and seen.local[x] == (u,)) for u in range(zero_count)
        ]
        key = canonical_b_key(
            [seen.local[y] for y in l_tickets], seen.local[c], residual, sum(seen.zeta)
        )
        lb = k_side_lower_bound(*key)
        if lb is None:
            raise AssertionError("a legal realization has no legal local structure")
        require(p_k >= lb and seen.t <= seen.phi - lb, "K-side bound exceeds P_K")
        out |= {"K_SIDE_LB": lb, "CERTIFIED_BOUND": seen.phi - lb}
    require(seen.t <= CLAIMED_CAPS[profile], "realization exceeds the claimed cap")
    return out


def realization_sample(
    profile: str, seed: int, count: int, *, high_l_sigma: bool = False, min_phi: int | None = None
) -> dict[str, object]:
    """Deterministic sample of legal realizations, each run through realization_check."""
    rng = random.Random(seed)
    checks: list[dict[str, int]] = []
    supports: list[list[list[int]]] = []
    tries = 0
    while len(checks) < count:
        tries += 1
        require(tries <= 200_000, "realization sampler did not converge")
        l_sigma = [rng.choice((3, 4, 4, 4)) for _ in range(L_TICKETS)] if high_l_sigma else []
        built = build_realization(profile, rng, l_sigma)
        if built is None:
            continue
        check = realization_check(profile, *built)
        if min_phi is None or check["PHI"] > min_phi:
            checks.append(check)
            supports.append([list(s) for s in (*built[0], *built[1])])
    ts = [c["T"] for c in checks]
    return {
        "SEED": seed,
        "COUNT": count,
        "TRIES": tries,
        "MIN_PHI_FILTER": min_phi,
        "T_RANGE": [min(ts), max(ts)],
        "ROWS": checks,
        "SUPPORTS_SHA256": digest(supports),
        "STATUS": "ALL_R5_LEGAL_AND_IDENTITY_EXACT",
    }


# ---------------------------------------------------------------- Route B


def integer_term(profile: str, t: int, *, base: int = S4_BASE, choose3: int | None = None) -> Term:
    """R32 rule with integer floors and ceilings written out from the profile alone."""
    d = profile_values(profile)
    g = [TICKET_CAPACITY + v for v in d]
    w = sum(comb(v, 2) for v in g)
    u = sum(comb(v, 3) for v in g) if choose3 is None else choose3
    a_max = sum(v * (x - 2) for v, x in zip(d, g, strict=True)) // 3
    excess = u - (max(g) - 2) * (w - 3 * t)
    k4 = max(0, -(-excess // 4))
    contained = min(k4, a_max)
    s4 = max(base, 679 * k4 - 231 * contained)
    s3 = 2800 * w + 11872 * (t - TRIPLE_SUPPORTS) - 30800
    return t, r32.K20_S1 - r32.K20_S2 + s3 - (4 * s4) // 7, k4, contained, s4, s3


def rational_term(profile: str, t: int) -> Term:
    """The same term from exact rationals, rounding by search rather than by //."""
    d = profile_values(profile)
    g = [TICKET_CAPACITY + v for v in d]
    w = sum(comb(v, 2) for v in g)
    excess = Fraction(sum(comb(v, 3) for v in g) - (max(g) - 2) * (w - 3 * t), 4)
    a_max = Fraction(sum(v * (x - 2) for v, x in zip(d, g, strict=True)), 3)
    k4 = 0
    while k4 < excess:
        k4 += 1
    floor_a = 0
    while floor_a + 1 <= a_max:
        floor_a += 1
    contained = min(k4, floor_a)
    s4 = max(S4_BASE, 448 * contained + 679 * (k4 - contained))
    s3 = 2800 * w + 11872 * (t - TRIPLE_SUPPORTS) - 30800
    exact = Fraction(r32.K20_S1 - r32.K20_S2 + s3) - Fraction(4 * s4, 7)
    bound = exact.numerator // exact.denominator
    require(bound <= exact < bound + 1, "rational floor")
    return t, bound, k4, contained, s4, s3


def route_b_terms(profile: str, cap: int, *, choose3: int | None = None) -> list[Term]:
    """R32's envelope, matched term by term by the integer and rational rewrites."""
    p = profile_values(profile)
    native = [tuple(term) for term in r32.route_b_envelope(p, cap, S4_BASE)]
    domain = range(TRIPLE_SUPPORTS, cap + 1)
    ints = [integer_term(profile, t, choose3=choose3) for t in domain]
    rats = [rational_term(profile, t) for t in domain]
    require(len(native) == len(domain), "Route-B domain differs")
    rows = zip(domain, native, ints, rats, strict=True)
    mismatched = [t for t, a, b, c in rows if not a == b == c]
    require(not mismatched, f"Route-B terms differ at {len(mismatched)} t, first {mismatched[:3]}")
    return [(t, b, k4, c, s4, s3) for t, b, k4, c, s4, s3 in native]


def route_b_summary(profile: str, cap: int) -> dict[str, object]:
    new, old = route_b_terms(profile, cap), route_b_terms(profile, OLD_CAP)
    bounds = [term[1] for term in new]
    require(
        new == old[: len(new)]
        and all(a < b for a, b in pairwise(bounds))
        and new[-1][1] == max(bounds),
        "Route-B envelope is not an increasing prefix of the cap-265 envelope",
    )
    g = [TICKET_CAPACITY + v for v in profile_values(profile)]
    return {
        "CAP": cap,
        "DOMAIN": f"{TRIPLE_SUPPORTS}..{cap}",
        "TERM_COUNT": len(new),
        "W": sum(comb(v, 2) for v in g),
        "U": sum(comb(v, 3) for v in g),
        "G_MAX": max(g),
        "A_MAX": r32.contained_triple_k4_cap(profile_values(profile)),
        "ARGMAX_TERM": list(new[-1]),
        "BOUND": new[-1][1],
        "TERMS_SHA256": digest(new),
        "OLD_CAP": OLD_CAP,
        "OLD_TERM_COUNT": len(old),
        "OLD_ARGMAX_TERM": list(old[-1]),
        "OLD_BOUND": old[-1][1],
        "PREFIX_OF_OLD": True,
        "STRICTLY_INCREASING_IN_T": True,
        "NATIVE_INTEGER_RATIONAL_MATCH": len(new) + len(old),
    }


# ---------------------------------------------------------------- result


EXPECTED: dict[str, object] = {
    "A_DP_FEASIBLE_GRAPHS": 968,
    "A_EXPLICIT_ISO_CLASSES": 34,
    "A_EXPLICIT_STATES": 1_135_147,
    "A_CERTIFIED_T_MAX": 253,
    "B_EXPLICIT_ISO_CLASSES": 11,
    "B_EXPLICIT_STATES": 167_576,
    "B_ZERO_SIDE_MAX": 274,
    "B_STATES_ABOVE_258": 399,
    "B_STATES_AT_258": 197,
    "B_MAIN_WORST_BOUND": 239,
    "B_MAIN_LOCALLY_ILLEGAL": 0,
    "B_EXTENDED_STATES": 11_053,
    "B_EXTENDED_LOCALLY_ILLEGAL": 294,
    "B_EXTENDED_WORST_BOUND": 239,
    "ABLATION_A_DROP_CROSSING_BALANCE": 413,
    "ABLATION_A_DROP_ZERO_SIDE_P_TERMS": 265,
    "ABLATION_B_DROP_CROSSING_BALANCE": 377,
    "ABLATION_B_NO_K_SIDE": 274,
    "ABLATION_B_NO_K6_LEMMA": 261,
    "ROUTE_B_A": [235, 313_311_276, [256, 313_311_276, 432, 197, 247_821, 5_062_848]],
    "ROUTE_B_B": [237, 313_328_812, [258, 313_328_812, 448, 197, 258_685, 5_086_592]],
    "ROUTE_B_OLD": [244, 313_391_740, [265, 313_391_740, 500, 197, 293_993, 5_169_696]],
    "ROUTE_B_TERM_POSITIONS": 960,
    "FAMILY_PROJECTION_AFTER": 313_391_636,
    "FAMILY_PROJECTION_GAIN": 104,
}


def family_projection(
    base: Mapping[str, object], bounds: Mapping[str, int], claimed_gain: int | None = None
) -> dict[str, object]:
    """Read-only projection from the base's sealed frontier fields; not a ledger replay."""
    before, after = base["FAMILY_BOUND_AFTER"], base["NEXT_DISTINCT_BOUND"]
    if not isinstance(before, int) or not isinstance(after, int):
        raise AssertionError("base frontier is not integral")
    require(all(b < after for b in bounds.values()), "a new row bound does not drop below next")
    gain = before - after
    owner_delta = sum(before - b for b in bounds.values())
    if claimed_gain is not None:
        require(claimed_gain == gain, "owner delta misreported as family gain")
    return {
        "BASE_FAMILY_BOUND": before,
        "BASE_OWNERS": base["MAXIMIZING_OWNERS"],
        "NEW_ROW_BOUNDS": dict(bounds),
        "PROJECTED_FAMILY_BOUND": after,
        "PROJECTED_OWNERS": base["NEXT_DISTINCT_OWNERS"],
        "PROJECTED_FAMILY_GAIN": gain,
        "OWNER_DELTA_TOTAL": owner_delta,
        "METHOD": "BASE_SEALED_FRONTIER_FIELDS_ONLY_NO_LEDGER_REPLAY",
        "FORMAL_FAMILY_AUTHORITY": "NOT_CLAIMED",
    }


def negative_controls(a_max: int, b_certified: int, b_zero_max: int) -> dict[str, str]:
    """Each control feeds a wrong input to a real check, which must reject it."""
    triples, pairs = first_realization(PROFILE_A, 1)
    d_a = profile_values(PROFILE_A)
    seen = observe(PROFILE_A, triples, pairs)
    sigma, zeta, parts, t = seen.sigma, seen.zeta, seen.parts, seen.t
    identity_holds(PROFILE_A, sigma, zeta, parts, t)
    shifted = [-1, *parts[1:]]
    return {
        "WRONG_PROFILE_DIGIT_SUM": expect_rejected(lambda: profile_values("66655555555331100001")),
        "WRONG_PROFILE_SUM_D_SQUARED": expect_rejected(lambda: premises(NEXT_OWNER)),
        "WRONG_DEGREE_HISTOGRAM": expect_rejected(
            lambda: r5.validate_k20_support_realization(triples, pairs, profile_values(PROFILE_B))
        ),
        "WRONG_TRIPLE_SUPPORT_COUNT": expect_rejected(
            lambda: r5.validate_k20_support_realization(triples[:-1], pairs, d_a)
        ),
        "WRONG_PAIR_SUPPORT_COUNT": expect_rejected(
            lambda: r5.validate_k20_support_realization(triples, pairs[:-1], d_a)
        ),
        "PAIR_REUSES_TRIPLE_PAIR": expect_rejected(
            lambda: r5.validate_k20_support_realization(triples, [triples[0][:2], *pairs[1:]], d_a)
        ),
        "CROSSING_IMBALANCE": expect_rejected(
            lambda: identity_holds(PROFILE_A, sigma, [zeta[0] + 1, *zeta[1:]], parts, t)
        ),
        "D6_SIGMA_OUT_OF_RANGE": expect_rejected(
            lambda: identity_holds(
                PROFILE_A, [sigma[0] + 1, *sigma[1:]], [zeta[0] + 1, *zeta[1:]], parts, t
            )
        ),
        "NEGATIVE_P_TERM": expect_rejected(
            lambda: identity_holds(PROFILE_A, sigma, zeta, shifted, t + sum(parts) - sum(shifted))
        ),
        "WRONG_TRIANGLE_COUNT": expect_rejected(
            lambda: identity_holds(PROFILE_A, sigma, zeta, parts, t + 1)
        ),
        "UNSUPPORTED_CAP_A_252": expect_rejected(lambda: cap_supported(a_max, 252)),
        "UNSUPPORTED_CAP_B_238": expect_rejected(lambda: cap_supported(b_certified, 238)),
        "B_WITHOUT_K_SIDE": expect_rejected(lambda: cap_supported(b_zero_max, 258)),
        "B_WITHOUT_K6_LEMMA": expect_rejected(lambda: b_main_certificate(k6_slots=0)),
        "A_WITHOUT_CROSSING_BALANCE": expect_rejected(
            lambda: cap_supported(separable_maximum(PROFILE_A), 256)
        ),
        "WRONG_U_IN_ROUTE_B": expect_rejected(
            lambda: route_b_terms(PROFILE_A, CLAIMED_CAPS[PROFILE_A], choose3=2319)
        ),
        "OWNER_DELTA_AS_FAMILY_GAIN": expect_rejected(
            lambda: family_projection(
                base_authority(),
                {PROFILE_A: 313_311_276, PROFILE_B: 313_328_812},
                claimed_gain=143_392,
            )
        ),
    }


def compute_result() -> dict[str, object]:
    provenance = module_provenance()
    base = base_authority()
    profiles = (PROFILE_A, PROFILE_B)
    facts = {p: {**premises(p), "IDENTITY": identity_check(p)} for p in profiles}
    cert_a, a_max = certify_a()
    cert_b, b_certified, b_zero_max = certify_b()
    route = {p: route_b_summary(p, CLAIMED_CAPS[p]) for p in profiles}
    bounds = {p: route_b_terms(p, CLAIMED_CAPS[p])[-1][1] for p in profiles}
    old = {p: route_b_terms(p, OLD_CAP)[-1][1] for p in profiles}
    require(
        old[PROFILE_A] == old[PROFILE_B] == base["FAMILY_BOUND_AFTER"],
        "cap-265 Route-B bound differs from the base family bound",
    )
    realizations = {
        "A": realization_sample(PROFILE_A, 1, 12),
        "B": realization_sample(PROFILE_B, 2, 12),
        "B_PHI_ABOVE_258": realization_sample(PROFILE_B, 3, 12, high_l_sigma=True, min_phi=258),
    }
    no_k6 = b_rows(CLAIMED_CAPS[PROFILE_B], k6_slots=0)
    ablations: dict[str, object] = {
        "A_DROP_CROSSING_BALANCE": separable_maximum(PROFILE_A),
        "A_DROP_ZERO_SIDE_P_TERMS": zero_side_dp(PROFILE_A, z_terms=False)["MAX_PHI"],
        "B_DROP_CROSSING_BALANCE": separable_maximum(PROFILE_B),
        "B_DROP_ZERO_SIDE_P_TERMS": zero_side_dp(PROFILE_B, z_terms=False)["MAX_PHI"],
        "B_NO_K_SIDE": b_zero_max,
        "B_NO_K6_LEMMA": worst_bound(no_k6),
        "B_NO_K6_LEMMA_STATES_ABOVE_258": sum(
            1 for s, lb in no_k6 if lb is not None and s.phi - lb > CLAIMED_CAPS[PROFILE_B]
        ),
    }
    projection = family_projection(base, bounds)
    lemmas = generic_lemma_check()
    negatives = negative_controls(a_max, b_certified, b_zero_max)
    dp_a = cert_a["DP_ALL_LABELLED_GRAPHS"]
    require(isinstance(dp_a, dict), "A DP summary")

    def envelope(p: str, key: str) -> list[object]:
        return [
            route[p][f"{key}TERM_COUNT"],
            route[p][f"{key}BOUND"],
            route[p][f"{key}ARGMAX_TERM"],
        ]

    actual: dict[str, object] = {
        "A_DP_FEASIBLE_GRAPHS": cast_mapping(dp_a)["FEASIBLE_GRAPHS"],
        "A_EXPLICIT_ISO_CLASSES": cert_a["EXPLICIT_ISO_CLASSES"],
        "A_EXPLICIT_STATES": cert_a["EXPLICIT_STATES"],
        "A_CERTIFIED_T_MAX": a_max,
        "B_EXPLICIT_ISO_CLASSES": cert_b["EXPLICIT_ISO_CLASSES"],
        "B_EXPLICIT_STATES": cert_b["EXPLICIT_STATES"],
        "B_ZERO_SIDE_MAX": b_zero_max,
        "B_STATES_ABOVE_258": cert_b["STATES_ABOVE_CLAIMED_CAP"],
        "B_STATES_AT_258": cert_b["STATES_AT_CLAIMED_CAP"],
        "B_MAIN_WORST_BOUND": cert_b["MAIN_WORST_BOUND"],
        "B_MAIN_LOCALLY_ILLEGAL": cert_b["MAIN_LOCALLY_ILLEGAL"],
        "B_EXTENDED_STATES": cert_b["EXTENDED_STATES"],
        "B_EXTENDED_LOCALLY_ILLEGAL": cert_b["EXTENDED_LOCALLY_ILLEGAL"],
        "B_EXTENDED_WORST_BOUND": cert_b["EXTENDED_WORST_BOUND"],
        "ABLATION_A_DROP_CROSSING_BALANCE": ablations["A_DROP_CROSSING_BALANCE"],
        "ABLATION_A_DROP_ZERO_SIDE_P_TERMS": ablations["A_DROP_ZERO_SIDE_P_TERMS"],
        "ABLATION_B_DROP_CROSSING_BALANCE": ablations["B_DROP_CROSSING_BALANCE"],
        "ABLATION_B_NO_K_SIDE": ablations["B_NO_K_SIDE"],
        "ABLATION_B_NO_K6_LEMMA": ablations["B_NO_K6_LEMMA"],
        "ROUTE_B_A": envelope(PROFILE_A, ""),
        "ROUTE_B_B": envelope(PROFILE_B, ""),
        "ROUTE_B_OLD": envelope(PROFILE_A, "OLD_"),
        "ROUTE_B_TERM_POSITIONS": sum(
            len(route_b_terms(p, cap)) for p in profiles for cap in (CLAIMED_CAPS[p], OLD_CAP)
        ),
        "FAMILY_PROJECTION_AFTER": projection["PROJECTED_FAMILY_BOUND"],
        "FAMILY_PROJECTION_GAIN": projection["PROJECTED_FAMILY_GAIN"],
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFICATE_SEALED_LOCAL_PENDING_FRESH_JUDGE",
        "PROOF": __doc__,
        "BASE": base,
        "TRANSCRIPT_SOURCE": {
            "JUDGE_TASK_ID": TRANSCRIPT_JUDGE_TASK_ID,
            "JUDGE_SESSION_ID": TRANSCRIPT_JUDGE_SESSION_ID,
            "JUDGE_VERDICT": "VERIFIED_WITH_CAVEATS",
            "EVIDENCE_KIND_BEFORE": "TRANSCRIPT_ONLY",
            "EVIDENCE_KIND_AFTER": "COMMITTED_VERIFIER_AND_SEALED_RESULT",
            "METHOD_LINEAGE": (
                "The K-side enumeration follows the Judge's transcript algorithm. Its optimised "
                "and reference implementations here share that method, so they are not "
                "independent of it."
            ),
        },
        "PROFILES": {
            "A": {**facts[PROFILE_A], "CERTIFICATE": cert_a, "ROUTE_B": route[PROFILE_A]},
            "B": {**facts[PROFILE_B], "CERTIFICATE": cert_b, "ROUTE_B": route[PROFILE_B]},
        },
        "CAPS": {
            p: {
                "CLAIMED": CLAIMED_CAPS[p],
                "CERTIFIED_T_MAX": c,
                "ROW_BOUND": bounds[p],
                "STATUS": "PROVEN",
            }
            for p, c in ((PROFILE_A, a_max), (PROFILE_B, b_certified))
        },
        "REALIZATIONS": realizations,
        "GENERIC_K_SIDE_LEMMAS": lemmas,
        "ABLATIONS": ablations,
        "NEGATIVE_CONTROLS": negatives,
        "FAMILY_PROJECTION": projection,
        "EXPECTED_VALUES_MATCH": actual == EXPECTED,
        "EXPECTED_VALUE_DIFFERENCES": {
            k: {"EXPECTED": EXPECTED.get(k), "ACTUAL": actual.get(k)}
            for k in sorted(set(EXPECTED) | set(actual))
            if EXPECTED.get(k) != actual.get(k)
        },
        "MODULE_PROVENANCE": provenance,
        "FORMAL_FAMILY_AUTHORITY": "NOT_CLAIMED",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "SOLVER_CALLS": 0,
        "PRODUCTION_MUTATION": "NONE",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
    }


def main() -> None:
    result = compute_result()
    require(result["EXPECTED_VALUES_MATCH"] is True, "refusing to seal: expected values differ")
    payload = render(result)
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing sealed result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    caps = result["CAPS"]
    print(json.dumps({"CAPS": caps, "RESULT": str(RESULT_PATH), "SHA256": sha256(payload)}))


if __name__ == "__main__":
    main()
