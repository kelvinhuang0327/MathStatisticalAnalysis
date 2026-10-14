"""Reproducible universal T<=228 certificate for 66655555555332000000.

Frozen model: 20 tickets each use six distinct labels; 22 labels have triple
supports and 27 have pair supports. Pair-linearity makes the 3*22+27=93
support edges distinct, and g_x=6+d_x. The exact triple-degree histogram is
6^3,5^8,3^2,2,0^6, hence sum(g)=186, W=828 and sum C(g,3)=2324.
Goodman's double count of mixed triples gives T(G)+T(complement G)=294.

Let K be the 14 positive-degree vertices and Z the six zero-degree vertices.
Write M=(complement G)[K], N=(complement G)[Z], sigma_x=|N_G(x)&Z|,
zeta_z=|N_G(z)&K|, r=sum sigma=sum zeta. Then m_x=7-d_x+sigma_x,
n_z=zeta_z-1, 2e(M)=32+r and 2e(N)=r-6. Sorting complement triangles
by the number of Z vertices gives
 T(complement G)=6e(M)+14e(N)-sum sigma*m-sum zeta*n+P,
 P=T(M)+T(N)+sum_{xy in E(M)}|N_G(x)&N_G(y)&Z|
              +sum_{uv in E(N)}|N_G(u)&N_G(v)&K| >= 0.
Each summand of P counts a finite set. Since 6e(M)+14e(N)=54+10r,
Goodman and distributing -10r as -4sum sigma-6sum zeta give exactly
 T(G)=240+sum_K sigma_x(sigma_x+3-d_x)
             +sum_Z zeta_z(zeta_z-7)-P.

Every K-Z edge uses a pair label: a zero-triple-degree ticket has no triple
label. Distinct Z neighbours use distinct pair labels at x, so sigma<=6-d.
Thus d=6 contributes zero; each d=5 has sigma in {0,1}, contributing -1
exactly when sigma=1. For the d=3,3,2 vertices use a,b,c, respectively,
and let f be the number of d=5 vertices with sigma=1. Universally,
0<=a,b<=3, 0<=c<=4, 0<=f<=8 and r=a+b+c+f. Dropping P is therefore valid:
 T(G)<=240+a*a+b*b+c(c+1)-f+sum_Z zeta(zeta-7).

Every legal realization maps into this necessary-condition relaxation.
All 4*4*5*9=720 ordered core states are covered (a,b remain labelled).
G[Z] is one of the 2^15=32768 labelled simple six-vertex graphs. Its degrees
are 6-zeta, with 1<=zeta<=6, and r=36-2e(G[Z]) is even. Core capacity gives
r<=18, hence the only feasible r values are 6,8,10,12,14,16,18.
Permuting Z leaves the relaxed objective invariant, so its sorted zeta
histogram loses no realizations. Enumeration yields 102 histograms; a second
enumeration of all C(11,6)=462 candidate histograms followed by the full
Erdos-Gallai inequalities gives exactly the same set. Of these, 38 have
r<=18. Maximizing over every compatible core/histogram pair gives respectively
228,226,228,222,218,216,210. Therefore T<=228 for every legal realization.
No relaxed maximizing state is claimed to be a legal realization.

For the official Route-B envelope W=828, sum C(g,3)=2324 and g_max=12 yield
k(t)=max(0,ceil((30t-5956)/4)); A_max=floor(sum d(4+d)/3)=198.
S4=max(112,679k-231min(k,198)), and S3=2800(828-3t)+20272(t-22)+154000.
Every integer t from 22 through the cap is kept. The final upper bound is
ceil(372228640-63838600+S3-4S4/7), using exact rational rounding. At t=228,
k=221, S4=104321 and the complete profile bound is 313063660. This improves
the old 313395060 by 331400 and lies 200228 below incumbent 313263888.
This is certification of existing prior art, with no novelty or attainment
claim. Only the target row is updated in memory; all other resolved rows and
all cursor profiles retain their immutable authority and inherited caveats.
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
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_T228_EXACT_FORMAL_HANDOFF_R2"
OWNER = "01a138c9-0a10-7140-9c59-83b513e6394f"
SOURCE = "src/lottolab/research/b649_min_s2_t228_exact_formal_handoff_r2.py"
TEST = "tests/unit/test_b649_min_s2_t228_exact_formal_handoff_r2.py"
DIRECTORY = "docs/research/matrix-native-results"
RESULT = ROOT / DIRECTORY / "b649-min-s2-t228-exact-formal-handoff-r2-result.json"
BASE_HEAD = "64c4c6b66640616c44c6cab14d359ba81aacad22"
BASE_TREE = "f406bf732ebcd7c962162e27d4f6a4b6c1c9c961"
BASE_SHA = "ab4711dc900e529dddfbf27606155c267075d6d854360a28682cc70b947adb7c"
BASE_RESULT = f"{DIRECTORY}/b649-min-s2-three-max-owners-exact-authority-r1-result-{BASE_SHA}.json"
PRIOR_HEAD = "e744534a3475d77aa192bf67733ade00b11c2ea3"
PRIOR_TREE = "e6f053dc966194a1a89474fc4591bd74cb6e00fd"
PRIOR_SOURCE = "src/lottolab/research/b649_next_two_max_profiles_exact_bound_r1.py"
PRIOR_TEST = "tests/unit/test_b649_next_two_max_profiles_exact_bound_r1.py"
PRIOR_RESULT = f"{DIRECTORY}/b649-next-two-max-profiles-exact-bound-r1-result.json"
PRIOR_SHA = "f538210b9719aa09639c3faf81c378f12658a2a2be865bbc5acdbe088fb74f44"
PRIOR_SOURCE_SHA = "9ca78ac773221a7747f62015c1b7db9d0726cc9949635f72a42076ded71f694d"
PRIOR_TEST_SHA = "411660997fd166d27bfa8a1b0f52d94c6fdba98cecdd7b6f35e7efced1d9279f"
PROFILE = "66655555555332000000"
OTHER_OWNER = "66655555555421100000"
DEGREES = tuple(map(int, PROFILE))
MODEL: dict[str, object] = {
    "tickets": 20,
    "labels_per_ticket": 6,
    "labels": 49,
    "triples": 22,
    "pairs": 27,
    "support_sizes": [2, 3],
    "pair_linearity": True,
}
R_MAXIMA = {6: 228, 8: 226, 10: 228, 12: 222, 14: 218, 16: 216, 18: 210}
type Document = dict[str, object]
type Core = tuple[int, int, int, int]
type Histogram = tuple[int, ...]
type Term = tuple[int, int, int, int, int, int]
ZERO_EDGES = tuple(combinations(range(6), 2))


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    result = cast(dict[object, object], value)
    require(all(isinstance(k, str) for k in result), "non-string key")
    return cast(Document, result)


def integer(value: object) -> int:
    require(type(value) is int, "expected exact integer")
    return cast(int, value)


def string(value: object) -> str:
    require(isinstance(value, str), "expected string")
    return cast(str, value)


def items(value: object) -> list[object]:
    require(isinstance(value, list), "expected list")
    return cast(list[object], value)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def decode(raw: bytes) -> Document:
    def unique(pairs: list[tuple[str, object]]) -> Document:
        require(len(pairs) == len(dict(pairs)), "duplicate JSON key")
        return dict(pairs)

    return obj(json.loads(raw, object_pairs_hook=unique))


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=ROOT)


def identity(head: str, tree: str) -> None:
    require(git("cat-file", "-t", head).strip() == b"commit", "source commit mismatch")
    require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "source tree mismatch")


def blob(head: str, path: str, digest: str | None = None) -> bytes:
    require(not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe source path")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "missing or unsafe source blob",
    )
    raw = git("cat-file", "blob", f"{head}:{path}")
    require(digest is None or sha(raw) == digest, "source SHA256 mismatch")
    return raw


def local_matches(path: str, raw: bytes) -> None:
    local = ROOT / path
    require(
        stat.S_ISREG(local.lstat().st_mode) and local.read_bytes() == raw,
        f"local source mismatch: {path}",
    )


@cache
def evaluator_pins() -> dict[str, str]:
    """Pin the complete static local import closure BEFORE importing the evaluator."""
    queue = ["src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py"]
    pins: dict[str, str] = {}
    available = set(git("ls-tree", "-r", "--name-only", BASE_HEAD).decode().splitlines())
    while queue:
        path = queue.pop()
        if path in pins:
            continue
        raw = blob(BASE_HEAD, path)
        local_matches(path, raw)
        pins[path] = sha(raw)
        for node in ast.walk(ast.parse(raw)):
            if not isinstance(node, ast.ImportFrom):
                continue
            names = [node.module] if node.module else [a.name for a in node.names]
            for name in names:
                if node.level:
                    prefix = Path(path).parent
                    for _ in range(node.level - 1):
                        prefix = prefix.parent
                    candidate = str(prefix / (name.replace(".", "/") + ".py"))
                elif name.startswith("lottolab."):
                    candidate = "src/" + name.replace(".", "/") + ".py"
                else:
                    continue
                if candidate in available:
                    queue.append(candidate)
    path = "src/lottolab/__init__.py"
    raw = blob(BASE_HEAD, path)
    local_matches(path, raw)
    pins[path] = sha(raw)
    return dict(sorted(pins.items()))


def load_inputs() -> tuple[Document, Document, dict[str, str]]:
    identity(BASE_HEAD, BASE_TREE)
    identity(PRIOR_HEAD, PRIOR_TREE)
    base_raw = blob(BASE_HEAD, BASE_RESULT, BASE_SHA)
    local_matches(BASE_RESULT, base_raw)
    prior = decode(blob(PRIOR_HEAD, PRIOR_RESULT, PRIOR_SHA))
    source = blob(PRIOR_HEAD, PRIOR_SOURCE, PRIOR_SOURCE_SHA)
    blob(PRIOR_HEAD, PRIOR_TEST, PRIOR_TEST_SHA)
    require(
        prior["SOURCE_SHA256"] == PRIOR_SOURCE_SHA and prior["TEST_SHA256"] == PRIOR_TEST_SHA,
        "prior result/source mismatch",
    )
    require(
        ast.get_docstring(ast.parse(source), clean=False) == prior["PROOF"],
        "prior proof/source mismatch",
    )
    require(
        prior["TASK_STATUS"] == "PROVEN_IMPROVEMENT; PENDING_ONE_FRESH_FOCUSED_SCIENTIFIC_REVIEW"
        and prior["PROJECTION_STATUS"] == "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "prior original disposition changed",
    )
    pins = evaluator_pins()
    for path, digest in pins.items():
        local_matches(path, blob(BASE_HEAD, path, digest))
    return decode(base_raw), prior, pins


def model_facts(pid: str = PROFILE, model: Mapping[str, object] = MODEL) -> Document:
    require(pid == PROFILE and render(model) == render(MODEL), "wrong degree profile/model")
    d = tuple(map(int, pid))
    require(Counter(d) == Counter({6: 3, 5: 8, 3: 2, 2: 1, 0: 6}), "wrong degree profile")
    g = tuple(6 + x for x in d)
    edges = 22 * comb(3, 2) + 27
    w = sum(comb(x, 2) for x in g)
    third = sum(comb(x, 3) for x in g)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * (19 - x) for x in g), 2)
    a_max = sum(x * (4 + x) for x in d) // 3
    require(
        (sum(d), edges, sum(g), w, third, goodman, a_max) == (66, 93, 186, 828, 2324, 294, 198),
        "graph identity differs",
    )
    require(10 * w - third == 5956, "wrong K4 constant")
    require(6 * (14 * 7 - 66) + 14 * 6 * (6 - 7) == 108, "split constant differs")
    # Check each coefficient of the -10r redistribution independently of enumeration.
    require(
        all(s * (s + 7 - x) - 4 * s == s * (s + 3 - x) for x in d if x for s in range(7 - x)),
        "core algebra differs",
    )
    require(all(z * (z - 1) - 6 * z == z * (z - 7) for z in range(1, 7)), "zero algebra differs")
    return {
        "MODEL": dict(model),
        "D": list(d),
        "G": list(g),
        "E": edges,
        "W": w,
        "SUM_CHOOSE3_DEGREES": third,
        "GOODMAN_SUM": goodman.numerator,
        "CORE_VERTICES": 14,
        "ZERO_VERTICES": 6,
        "SPLIT_CONSTANT": 240,
        "A_MAX": a_max,
        "K4_CONSTANT": 5956,
    }


def drop_penalty(head: int, parts: Sequence[int], direction: int = -1) -> int:
    require(
        direction == -1 and all(type(x) is int and x >= 0 for x in parts),
        "invalid P direction or nonnegative-count premise",
    )
    require(head + direction * sum(parts) <= head, "invalid P upper-bound direction")
    return head


def partition_audit(neighbours: Sequence[set[int]], core_size: int = 14) -> Document:
    """Independent triangle classification, for arbitrary simple graphs (no solver)."""
    v = set(range(len(neighbours)))
    require(
        0 < core_size < len(v)
        and all(i not in n and n <= v for i, n in enumerate(neighbours))
        and all(i in neighbours[j] for i, n in enumerate(neighbours) for j in n),
        "invalid simple graph",
    )
    k, z = set(range(core_size)), v - set(range(core_size))
    complement = [v - {i} - n for i, n in enumerate(neighbours)]
    m = [(i, j) for i, j in combinations(sorted(k), 2) if j in complement[i]]
    n = [(i, j) for i, j in combinations(sorted(z), 2) if j in complement[i]]

    def triangles(vertices: set[int], graph: Sequence[set[int]]) -> int:
        return sum(
            b in graph[a] and c in graph[a] and c in graph[b]
            for a, b, c in combinations(sorted(vertices), 3)
        )

    parts = (
        triangles(k, complement),
        triangles(z, complement),
        sum(len(neighbours[i] & neighbours[j] & z) for i, j in m),
        sum(len(neighbours[i] & neighbours[j] & k) for i, j in n),
    )
    head = (
        len(z) * len(m)
        + len(k) * len(n)
        - sum(len(neighbours[i] & z) * len(complement[i] & k) for i in k)
        - sum(len(neighbours[i] & k) * len(complement[i] & z) for i in z)
    )
    t, tc = triangles(v, neighbours), triangles(v, complement)
    goodman = Fraction(comb(len(v), 3)) - Fraction(
        sum(len(g) * (len(v) - 1 - len(g)) for g in neighbours), 2
    )
    require(tc == head + sum(parts) and t + tc == goodman, "partition/Goodman identity")
    drop_penalty(int(goodman) - head, parts)
    return {"T": t, "COMPLEMENT_T": tc, "P_PARTS": list(parts), "P": sum(parts)}


def core_states() -> tuple[Core, ...]:
    return tuple(product(range(4), range(4), range(5), range(9)))


def check_core_coverage(states: Sequence[Core]) -> None:
    expected = {
        (a, b, c, f) for a in range(4) for b in range(4) for c in range(5) for f in range(9)
    }
    require(
        len(states) == len(set(states)) == 720 and set(states) == expected,
        "omitted, duplicate or invalid core states",
    )


def zero_histogram(mask: int) -> Histogram:
    require(type(mask) is int and 0 <= mask < 32768, "invalid zero graph mask")
    degrees = [0] * 6
    for bit, (a, b) in enumerate(ZERO_EDGES):
        if mask & (1 << bit):
            degrees[a] += 1
            degrees[b] += 1
    return tuple(sorted(6 - d for d in degrees))


def zero_histograms(masks: Iterable[int] = range(32768)) -> Counter[Histogram]:
    seen: set[int] = set()
    counts: Counter[Histogram] = Counter()
    for mask in masks:
        require(mask not in seen, "duplicate zero graph")
        seen.add(mask)
        counts[zero_histogram(mask)] += 1
    require(seen == set(range(32768)), "omitted zero graphs")
    require(sum(counts.values()) == 32768 and len(counts) == 102, "zero histogram coverage")
    return counts


def erdos_gallai(zeta: Histogram) -> bool:
    d = sorted((6 - z for z in zeta), reverse=True)
    return (
        len(d) == 6
        and all(0 <= x <= 5 for x in d)
        and sum(d) % 2 == 0
        and all(sum(d[:k]) <= k * (k - 1) + sum(min(k, x) for x in d[k:]) for k in range(1, 7))
    )


def relaxation(
    states: Sequence[Core] | None = None, counts: Mapping[Histogram, int] | None = None
) -> Document:
    core = core_states() if states is None else states
    check_core_coverage(core)
    graphs = zero_histograms() if counts is None else counts
    # Independently reconcile all graphical histograms, then the r<=18 subset.
    candidates = tuple(combinations_with_replacement(range(1, 7), 6))
    graphical = {z for z in candidates if erdos_gallai(z)}
    require(
        len(candidates) == 462
        and len(graphical) == 102
        and set(graphs) == graphical
        and sum(graphs.values()) == 32768
        and all(n > 0 for n in graphs.values()),
        "histogram/Erdos-Gallai disagreement",
    )
    retained = {z for z in graphical if sum(z) <= 18}
    require(
        retained == {z for z in graphs if sum(z) <= 18} and len(retained) == 38,
        "retained histogram disagreement",
    )
    maxima: dict[int, int] = {}
    witnesses: dict[str, object] = {}
    pairs = 0
    for a, b, c, f in core:
        r = a + b + c + f
        for z in sorted(retained):
            if sum(z) != r:
                continue
            pairs += 1
            value = drop_penalty(
                240 + a * a + b * b + c * (c + 1) - f + sum(x * (x - 7) for x in z), ()
            )
            if value > maxima.get(r, -1000):
                maxima[r] = value
                witnesses[str(r)] = {"CORE": [a, b, c, f], "ZETA": list(z), "VALUE": value}
    require(maxima == R_MAXIMA and max(maxima.values()) == 228, "r-class maxima differ")
    return {
        "CORE_STATE_COUNT": len(core),
        "CORE_STATES": [list(x) for x in core],
        "ZERO_GRAPH_COUNT": sum(graphs.values()),
        "ZERO_GRAPH_HISTOGRAM_COUNT": len(graphs),
        "ERDOS_GALLAI_CANDIDATE_COUNT": len(candidates),
        "RETAINED_HISTOGRAM_COUNT": 38,
        "HISTOGRAM_SETS_AGREE": True,
        "HISTOGRAMS": [
            {
                "ZETA": list(z),
                "LABELLED_GRAPH_COUNT": graphs[z],
                "R": sum(z),
                "RETAINED": z in retained,
            }
            for z in sorted(graphs)
        ],
        "COMPATIBLE_STATE_HISTOGRAM_PAIRS": pairs,
        "R_CLASS_MAXIMA": {str(r): value for r, value in sorted(maxima.items())},
        "MAXIMIZING_RELAXED_STATES": witnesses,
        "UNIVERSAL_T_CAP": 228,
        "LEGAL_REALIZATION_ATTAINMENT": "UNKNOWN",
    }


def independent_envelope(cap: int, k4_constant: int = 5956) -> list[Term]:
    require(type(cap) is int and 22 <= cap <= 265, "wrong cap")
    require(k4_constant == 5956, "wrong K4 constant (T248's 5954 is invalid here)")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        k4 = max(0, -(-(30 * t - k4_constant) // 4))
        contained = min(k4, 198)
        s4 = max(112, 679 * k4 - 231 * contained)
        s3 = 2800 * (828 - 3 * t) + 20272 * (t - 22) + 7000 * 22
        total = 372228640 - 63838600 + s3
        exact = Fraction(total) - Fraction(4 * s4, 7)
        bound = (7 * total - 4 * s4 + 6) // 7
        require(bound == -(-exact.numerator // exact.denominator), "rational ceiling differs")
        terms.append((t, bound, k4, contained, s4, s3))
    return terms


def check_envelope(terms: Sequence[Term], cap: int) -> None:
    require(all(type(v) is int for term in terms for v in term), "noninteger envelope")
    require(list(terms) == independent_envelope(cap), "incomplete/wrong envelope or rounding error")


def projection(rows: Mapping[str, int]) -> bytes:
    return json.dumps(
        [{"PROFILE_ID": p, "CURRENT_BOUND": rows[p]} for p in sorted(rows)], sort_keys=True
    ).encode()


def profile(pid: str) -> tuple[int, ...]:
    require(len(pid) == 20 and set(pid) <= set("0123456"), "invalid family profile")
    d = tuple(map(int, pid))
    require(sum(d) == 66 and tuple(sorted(d, reverse=True)) == d, "invalid family degree tuple")
    return d


def family(rows: Mapping[str, int], cursor: Mapping[str, object]) -> tuple[int, list[str]]:
    all_rows = {
        **rows,
        **{p: integer(b) for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()},
    }
    maximum = max(all_rows.values())
    return maximum, sorted(p for p, b in all_rows.items() if b == maximum)


def replay_family(base: Document, bound: int) -> Document:
    from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route

    require(sha(render(base)) == BASE_SHA, "altered Base authority")
    rows = {p: integer(b) for p, b in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    coarse = obj(cursor["COARSE_BOUND_PROJECTION"])
    require(
        len(rows) == integer(base["ROWS_TOTAL"]) == 4647
        and len(coarse) == 197
        and len(items(cursor["PROFILE_IDS"])) == 197
        and set(items(cursor["PROFILE_IDS"])) == set(coarse)
        and not set(rows).intersection(coarse),
        "row/cursor coverage differs",
    )
    for pid in [*rows, *coarse]:
        profile(pid)
    require(sha(projection(rows)) == base["BOUNDS_SHA256_AFTER"], "row projection digest")
    require(sha(render(cursor)) == base["CURSOR_SHA256"], "cursor digest")
    for pid, value in coarse.items():
        require(
            route.r28.coarse_profile_envelope(profile(pid)).family_upper_bound == value,
            "cursor evaluator mismatch",
        )
    require(max(integer(v) for v in coarse.values()) == cursor["BOUND"], "cursor maximum")
    first, old_owners = family(rows, cursor)
    require(
        first == base["FAMILY_BOUND_AFTER"] == 313395060
        and old_owners == base["FAMILY_OWNER_IDS"] == sorted([PROFILE, OTHER_OWNER]),
        "baseline family differs",
    )
    require(
        rows[PROFILE] == max(t[1] for t in independent_envelope(265)) and bound == 313063660,
        "target row envelope mismatch",
    )
    require(
        PROFILE not in obj(base["PROFILE_CERTIFICATES"])
        and PROFILE not in obj(base["INHERITED_CERTIFICATES_ADOPTED_UNCHANGED"])
        and obj(base["INHERITED_TARGET_BONFERRONI_5_UNCHANGED"])["PROFILE_ID"] != PROFILE,
        "unexpected target S5 authority",
    )
    after = dict(rows)
    after[PROFILE] = bound
    require([p for p in rows if rows[p] != after[p]] == [PROFILE], "wrong changed rows")
    others = {p: b for p, b in rows.items() if p != PROFILE}
    require(others == {p: b for p, b in after.items() if p != PROFILE}, "other rows changed")
    last, owners = family(after, cursor)
    require(
        last == first and owners == [OTHER_OWNER] and after[OTHER_OWNER] == 313395060,
        "tied owner/family altered",
    )
    require(base["INCUMBENT"] == 313263888, "incumbent differs")
    return {
        "ROWS_REPLAYED": len(rows),
        "CURSOR_PROFILES_REEVALUATED": len(coarse),
        "ROW_UPDATES": {PROFILE: {"BEFORE": rows[PROFILE], "AFTER": bound}},
        "OTHER_ROWS_PRESERVED": len(others),
        "OTHER_ROWS_SHA256": sha(projection(others)),
        "BOUNDS_SHA256_BEFORE": sha(projection(rows)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "CURSOR": cursor,
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_PRESERVED": True,
        "FAMILY_BEFORE": first,
        "FAMILY_AFTER_SINGLE_ROW": last,
        "OWNERS_BEFORE": old_owners,
        "OWNERS_AFTER": owners,
        "SINGLE_ROW_FAMILY_DELTA": 0,
        "FORMAL_FAMILY_LEDGER_MUTATED": False,
        "S5_ADOPTED_FOR_TARGET": False,
    }


def compute_result() -> Document:
    base, prior, pins = load_inputs()
    facts, enumeration = model_facts(), relaxation()
    from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route

    old, new = independent_envelope(265), independent_envelope(228)
    require(
        route.k4_premises(DEGREES) == (828, 2324, 12)
        and route.r28.profile_s4_floor(DEGREES) == 112,
        "official premises mismatch",
    )
    for cap, terms in [(265, old), (228, new)]:
        official = route.route_b_envelope(DEGREES, cap, 112)
        check_envelope(official, cap)
        require(official == terms, "official all-T envelope mismatch")
    bound, previous = max(t[1] for t in new), max(t[1] for t in old)
    require(
        (len(old), len(new), previous, bound, new[-1][2], new[-1][4])
        == (244, 207, 313395060, 313063660, 221, 104321),
        "profile bounds differ",
    )
    require(bound < integer(base["INCUMBENT"]), "strict-gain exclusion fails")
    inherited = {
        k: v
        for k, v in base.items()
        if any(x in k for x in ["STATUS", "CAVEAT", "PROVENANCE", "GATE", "INHERITED"])
    }
    require(not any(name.startswith("ortools") for name in sys.modules), "solver imported")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LOCAL_COMMIT",
        "OWNER_CONVERSATION_ID": OWNER,
        "PROOF": __doc__,
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "BASE_RESULT_PATH": BASE_RESULT,
        "PRIOR_ART_HEAD": PRIOR_HEAD,
        "PRIOR_ART_TREE": PRIOR_TREE,
        "PRIOR_ART_RESULT_SHA256": PRIOR_SHA,
        "PRIOR_ART_SOURCE_SHA256": PRIOR_SOURCE_SHA,
        "PRIOR_ART_TEST_SHA256": PRIOR_TEST_SHA,
        "PRIOR_ART_ORIGINAL_STATUS": prior["TASK_STATUS"],
        "PRIOR_ART_ORIGINAL_PROJECTION_STATUS": prior["PROJECTION_STATUS"],
        "PRIOR_ART_STATUS_SNAPSHOT_VERBATIM": {
            k: v
            for k, v in prior.items()
            if any(x in k for x in ["STATUS", "PROJECTION", "GLOBAL", "AUTHORITY"])
        },
        "INHERITED_BASE_CAVEATS_AND_STATUS_VERBATIM": inherited,
        "SOURCE_PINS": pins,
        "MODEL_FACTS": facts,
        "ENUMERATION": enumeration,
        "TARGET_PROFILE": PROFILE,
        "CURRENT_CAP": 265,
        "NEW_PROVEN_CAP": 228,
        "FULL_PROFILE_BOUND": bound,
        "PROFILE_DELTA": previous - bound,
        "INCUMBENT": base["INCUMBENT"],
        "STRICT_GAIN_EXCLUDED": True,
        "BELOW_INCUMBENT_BY": integer(base["INCUMBENT"]) - bound,
        "ENVELOPE": {
            "TERM_COLUMNS": ["T", "BOUND", "K4", "CONTAINED_K4", "S4", "S3"],
            "OLD_TERMS": [list(t) for t in old],
            "NEW_TERMS": [list(t) for t in new],
            "OLD_T_TERMS": len(old),
            "NEW_T_TERMS": len(new),
            "ENVELOPE_MAX_T": [t[0] for t in new if t[1] == bound],
            "ROUNDING": "K4_CEILING; A_MAX_FLOOR; FINAL_EXACT_RATIONAL_CEILING",
        },
        "FAMILY": replay_family(base, bound),
        "HISTORICAL_R14": {
            "SHARED_REFS_DRIFT": "REPORTED_IN_PACKET; RETAINED; NOT_REATTRIBUTED_OR_REPAIRED",
            "LIMIT": "Historical shared-ref changes are not claimed to be task-owned.",
            "IMMUTABLE_R14_RESULT_SHA256": sha(
                blob(
                    BASE_HEAD,
                    f"{DIRECTORY}/b649-k20-min-s2-successive-class-dominance-r14-result.json",
                )
            ),
        },
        "G01_TO_G18_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 19)},
        "GATE_STATUS_SCOPE": "Exact sealed tree reviewed externally; lifecycle in commit/handoff",
        "LEGAL_SUPPORT_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "NOVELTY_CLAIMED": False,
        "SOLVER_CALLS": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "REMOTE_WRITE": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "RUN1_MUTATED": False,
    }


def verify_result(stored: Mapping[str, object]) -> None:
    require(render(stored) == render(compute_result()), "stored result not exactly reproducible")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    raw = render(compute_result())
    if RESULT.exists():
        require(
            stat.S_ISREG(RESULT.lstat().st_mode) and RESULT.read_bytes() == raw,
            "stored result differs",
        )
    else:
        require(not args.verify, "missing exact result")
        with RESULT.open("xb") as output:
            output.write(raw)
    print(
        json.dumps(
            {
                "RESULT": str(RESULT),
                "SHA256": sha(raw),
                "T_CAP": 228,
                "FULL_PROFILE_BOUND": 313063660,
                "SINGLE_ROW_FAMILY_DELTA": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
