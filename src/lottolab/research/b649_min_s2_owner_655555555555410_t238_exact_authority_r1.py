"""Universal T238 for one exact profile, adopted into the accepted Family.

Model. Twenty six-label tickets have exactly 22 triple supports and 27 pair
supports, pair-linear across all supports. A ticket of triple degree d has
2d+(6-d)=6+d distinct neighbours in the simple overlap graph G. Thus
sum d=66, sum g=186, E=93. For d=(6,5^11,4,1,0^6), W=sum C(g,2)=827 and
J=sum C(g,3)=2310. Every mixed three-set contributes twice to sum g(19-g),
so T(G)+T(complement G)=C(20,3)-sum g(19-g)/2=293.

Split. K={d>0} has 14 vertices; Z has six. Let M=complement G[K],
N=complement G[Z], sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|,
r=sum sigma=sum zeta. Then m_x=7-d_x+sigma_x, n_u=zeta_u-1,
2e(M)=32+r, 2e(N)=r-6. A complement triangle crossing an M edge xy has
6-sigma_x-sigma_y+c_Z(x,y) possible zero vertices, where
c_Z(x,y)=|N_G(x) intersect N_G(y) intersect Z|. A complement triangle crossing
an N edge uv similarly has 14-zeta_u-zeta_v+c_K(u,v), with c_K defined using K.
Summing by the unique within-part edge of each mixed triangle gives exactly
T(G)=239-10r+sum_K sigma_x m_x+sum_Z zeta_u n_u-P=F-P,
P=T(M)+T(N)+sum_{xy in M}c_Z(x,y)+sum_{uv in N}c_K(u,v).
All four P terms are explicit nonnegative cardinalities; only P>=0 is used.

Capacities. Edges meeting a zero arise from pair labels, hence
0<=sigma_x<=6-d_x. The d=6 vertex has sigma=0, each of eleven d=5 vertices
has sigma in {0,1}, the d=4 vertex x has sigma in 0..2, and the d=1 vertex y
in 0..5. A zero has six neighbours and at most five in Z, so 1<=zeta<=6.
Equal cross-incidence totals are mandatory. In addition m,n,6-d-sigma and
6-zeta must be graphical: the residual list is the simple core pair-support
graph after cross pairs are removed. Sigma and zeta must be bipartite graphical.
Erdos-Gallai follows by bounding incidences of the largest j vertices by
j(j-1)+sum_outside min(j,degree); evenness and degree bounds are necessary.
Gale-Ryser prefixes follow by bounding edges into each opposite column by
min(j,column degree). These necessary filters are independently classified
using Havel-Hakimi and the opposite orientation of the cross-prefix cuts.

Coverage and symmetry. Permuting equal-d vertices in K and independently
permuting Z leaves F and every degree-list condition unchanged. Therefore
sort sigma within the eleven d=5 vertices, and sort zeta in Z. No relation
between the actual cross neighbours is imposed by sorting their degrees:
the degree-list relaxation deliberately forgets the incidence matrix.
There are 12 choices q for the count of H5 sigma=1, three x choices and six
y choices. For each, enumerate every sorted six-entry zeta in 1..6 with
sum zeta=q+x+y. These 1296 raw configurations contain every legal realization.
Their full maximum F is 238, even before graphical filtering; the 225 states
passing all filters also have maximum 238. An independent six-bin histogram
recursion generates zeta first, then solves q=sum zeta-x-y, and independently
recomputes F and the filters. It agrees on every complete row, not just counts.
The pinned split theorem's own filtered enumeration also agrees on all 225.
For each legal realization, T=F-P<=F<=max_raw F=238. Relaxation extremizers
need not be support-realizable. Legal attainment remains UNKNOWN.

Complete Route B. Each seven-label outcome has at most seven winning tickets:
three chosen hits of each winner use three distinct pairs, and pair-linearity
makes these pairs disjoint. For r=0..7, r-C(r,2)+C(r,3)-1[r>0] is at least
(4/7)C(r,4). Summing yields ceil(S1-S2+S3-4S4/7). S1=372228640,
S2=63838600; S3=2800(W-3T)+20272(T-22)+7000*22. The 22 support triangles
are distinct, so T starts at 22. Noncomplete neighbour triples contain an open
wedge, each extending at most gmax-2 ways; complete triples count K4 four times.
Hence K4>=max(0,ceil((J-(gmax-2)(W-3T))/4)). At most one triple support lies
in a K4, by pair-linearity. Each triple's common outside neighbours are at most
one third of the sum of its vertices' g-2; summing gives containment allowance
floor(sum d(g-2)/3)=197. K4 weights are 448 with a triple, 679 otherwise.
The increasing function 679k-231min(k,197) gives a valid S4 lower bound;
combine with the inherited S4>=112 by maximum. This inherited floor's argument
uses cross incidences>=4*66+222=486 across 22*17=374 support/outside pairs:
absence of contributing quartets would force >=112 double incidences into
only 66 core edges, a contradiction. The positive local weight is at least 112.
Integer arithmetic and a separately derived Fraction ceiling evaluate every
old T=22..265 and new T=22..238. No S5 data are introduced. The exact old cap
is read from Base's historical R30 refutation at 266; that solver is not rerun.

Family. Copy all 4647 resolved rows and the full 197-profile cursor from the
SHA-pinned accepted Base. Replace exactly this target bound in memory. The
other 4646 rows, all cursor bounds/identities/coverage, T245 certificate and
41-profile cohort, and every inherited caveat/disposition remain unchanged.
Two complete scans independently derive the maximum, every tied owner and
open count. Historical R15 stays NOT_VERIFIED. This task's lifecycle audit and
fresh Judge acceptance are external to the deterministic sealed result.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from functools import cache
from itertools import combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split
from . import b649_min_s2_owner_ab_exact_family_composition_r1 as common

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_655555555555410_T238_EXACT_AUTHORITY_R1"
OWNER_CONVERSATION_ID = "01a139eb-7d02-7be0-a5aa-41833d3f7688"
STEM = "b649_min_s2_owner_655555555555410_t238_exact_authority_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
RESULT = f"docs/research/matrix-native-results/{STEM.replace('_', '-')}-result.json"
BASE_HEAD = "2bdf3a6843800b1a1c818bd4e168585a7971611a"
BASE_TREE = "eebc232eb696a45e766c72f372c05766eac54ac1"
BASE_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-min-s2-t245-cursor41-joint-formal-authority-r1-result.json"
)
BASE_SHA = "cb31efaa152f1fda276975f111cbc56134c71426edbbad071865863d4b58c472"
SPLIT_SOURCE = "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py"
SPLIT_SHA = "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784"
CAP_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
CAP_SHA = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
TARGET = "65555555555541000000"
D = (6,) + (5,) * 11 + (4, 1) + (0,) * 6
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}
type Document = dict[str, object]
type Term = tuple[int, int, int, int, int, int]
type Record = tuple[int, ...]
require, obj, integer, render, decode, sha = (
    common.require,
    common.obj,
    common.integer,
    common.render,
    common.decode,
    common.sha,
)


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def immutable(head: str, path: str, digest: str) -> bytes:
    require(bool(re.fullmatch("[0-9a-f]{40}", head)), "wrong source commit")
    require(git("cat-file", "-t", head).strip() == b"commit", "wrong source type")
    require(not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe path")
    meta = git("ls-tree", head, "--", path).decode().strip().split("\t")
    require(
        len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path,
        "missing or unsafe source",
    )
    raw = git("cat-file", "blob", head + ":" + path)
    require(sha(raw) == digest, "source SHA256 mismatch")
    require((ROOT / path).read_bytes() == raw, "frozen working source drift")
    return raw


def load_base() -> Document:
    require(
        git("rev-parse", BASE_HEAD + "^{tree}").decode().strip() == BASE_TREE, "wrong Base tree"
    )
    raw = immutable(BASE_HEAD, BASE_RESULT, BASE_SHA)
    base = decode(raw)
    require(render(base) == raw, "noncanonical Base")
    require(
        obj(obj(base["FOUR_SCENARIO_REPLAY"])["S3"])["FAMILY_BOUND"] == 313392516
        and base["RESOLVED_ROWS"] == 4647
        and base["CURSOR_PROFILES"] == 197,
        "wrong Base family",
    )
    require(
        obj(base["T245_PROOF"])["UNIVERSAL_T_CAP"] == 245
        and obj(base["COHORT_PROOF"])["COUNT"] == 41
        and obj(base["COHORT_PROOF"])["NEW_BOUND"] == 313275864,
        "missing inherited certificates",
    )
    return base


def source_authority() -> Document:
    immutable(BASE_HEAD, SPLIT_SOURCE, SPLIT_SHA)
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
        and BASE_TREE in report
        and BASE_SHA in report
        and "Fresh-context Judge: VERIFIED_WITH_CAVEATS" in message,
        "Base Judge binding",
    )
    pending = [route.__name__, split.__name__, common.__name__]
    pins: dict[str, str] = {}
    while pending:
        module = pending.pop()
        relative = "src/" + module.replace(".", "/") + ".py"
        if relative in pins:
            continue
        raw = git("cat-file", "blob", BASE_HEAD + ":" + relative)
        immutable(BASE_HEAD, relative, sha(raw))
        pins[relative] = sha(raw)
        package = module.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(raw)):
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
                        pending.extend(prefix + "." + a.name for a in node.names)
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name.startswith("lottolab"))
    require(not any(m.startswith("ortools") for m in sys.modules), "solver loaded")
    cap = decode(immutable(BASE_HEAD, CAP_RESULT, CAP_SHA))
    attempts = [obj(x) for x in common.items(cap["GROUP_ATTEMPTS"])]
    applicable = [
        x for x in attempts if x["PROFILE_IDS"] == [TARGET] and x["STATUS"] == "INFEASIBLE"
    ]
    old = min(integer(x["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]) for x in applicable)
    witness = next(x for x in applicable if x["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == old)
    require(
        old == 265
        and witness["REFUTED_GRAPH_TRIANGLE_COUNT"] == old + 1
        and witness["CERTIFICATE_KIND"] == "CP_SAT_INFEASIBLE",
        "wrong current cap",
    )
    return {
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_PATH": BASE_RESULT,
        "BASE_RESULT_SHA256": BASE_SHA,
        "BASE_JUDGE_VERDICT": "VERIFIED_WITH_CAVEATS",
        "BASE_JUDGE_REPORT_SHA256": declared[0],
        "BASE_COMMIT_MESSAGE_SHA256": sha(message.encode()),
        "SPLIT_SOURCE": SPLIT_SOURCE,
        "SPLIT_SOURCE_SHA256": SPLIT_SHA,
        "SPLIT_SOURCE_HEAD": BASE_HEAD,
        "SOURCE_PINS": dict(sorted(pins.items())),
        "CURRENT_T_CAP": old,
        "CURRENT_S4_FLOOR": 112,
        "CURRENT_S5_AUTHORITY": "NOT_ADOPTED",
        "OLD_CAP_RESULT": CAP_RESULT,
        "OLD_CAP_RESULT_SHA256": CAP_SHA,
        "OLD_CAP_ROW": witness,
        "HISTORICAL_SOLVER_RERUN": False,
        "HISTORICAL_R15": "NOT_VERIFIED",
        "INHERITED_DISPOSITIONS": "Preserved verbatim through immutable Base reference",
    }


def facts(pid: str = TARGET, model: Mapping[str, object] = MODEL) -> Document:
    require(pid == TARGET and dict(model) == MODEL, "wrong target or frozen model")
    d = common.profile(pid)
    require(d == D, "incorrect degree identity")
    g = tuple(6 + x for x in d)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * (19 - x) for x in g), 2)
    actual: Document = {
        "D": list(d),
        "G": list(g),
        "SUM_D": sum(d),
        "CORE_VERTICES": sum(x > 0 for x in d),
        "ZERO_VERTICES": d.count(0),
        "OVERLAP_GRAPH_VERTICES": len(g),
        "E": sum(g) // 2,
        "W": sum(comb(x, 2) for x in g),
        "SUM_CHOOSE3_DEGREES": sum(comb(x, 3) for x in g),
        "GOODMAN_SUM": goodman.numerator,
        "CONTAINMENT_ALLOWANCE": sum(x * (x + 4) for x in d) // 3,
    }
    require(
        goodman.denominator == 1
        and tuple(
            actual[k]
            for k in (
                "SUM_D",
                "CORE_VERTICES",
                "ZERO_VERTICES",
                "OVERLAP_GRAPH_VERTICES",
                "E",
                "W",
                "SUM_CHOOSE3_DEGREES",
                "GOODMAN_SUM",
                "CONTAINMENT_ALLOWANCE",
            )
        )
        == (66, 14, 6, 20, 93, 827, 2310, 293, 197),
        "incorrect degree identity",
    )
    return actual


def validate_facts(value: Mapping[str, object]) -> None:
    require(render(value) == render(facts()), "incorrect degree identity")


def remainder(parts: Sequence[int]) -> int:
    require(
        len(parts) == 4 and all(type(x) is int and x >= 0 for x in parts),
        "incorrect nonnegative correction sign",
    )
    return sum(parts)


def havel_hakimi(degrees: Sequence[int]) -> bool:
    a = list(degrees)
    if any(d < 0 or d >= len(a) for d in a):
        return False
    while a:
        a.sort(reverse=True)
        need = a.pop(0)
        if need == 0:
            return True
        if need > len(a):
            return False
        for i in range(need):
            a[i] -= 1
            if a[i] < 0:
                return False
    return True


def record(q: int, x: int, y: int, zeta: tuple[int, ...], *, independent: bool = False) -> Record:
    require(
        all(type(a) is int for a in (q, x, y, *zeta))
        and 0 <= q <= 11
        and 0 <= x <= 2
        and 0 <= y <= 5
        and len(zeta) == 6
        and all(1 <= z <= 6 for z in zeta)
        and zeta == tuple(sorted(zeta)),
        "invalid capacity or symmetry representative",
    )
    sigma = (0,) + (0,) * (11 - q) + (1,) * q + (x, y)
    d = D[:14]
    m = tuple(7 - v + s for v, s in zip(d, sigma, strict=True))
    n = tuple(z - 1 for z in zeta)
    residual = tuple(6 - v - s for v, s in zip(d, sigma, strict=True))
    require(sum(sigma) == sum(zeta), "unequal cross incidence")
    if independent:
        f = (
            293
            - 6 * sum(m) // 2
            - 14 * sum(n) // 2
            + sum(a * b for a, b in zip(sigma, m, strict=True))
            + sum(a * b for a, b in zip(zeta, n, strict=True))
        )
        checks = [havel_hakimi(seq) for seq in (m, n, residual, tuple(6 - z for z in zeta))]
        ordered = sorted(zeta, reverse=True)
        cross = all(sum(ordered[:j]) <= sum(min(j, a) for a in sigma) for j in range(1, 7))
    else:
        f = 239 - 7 * q + x * (x - 7) + y * (y - 4) + sum(z * (z - 1) for z in zeta)
        checks = [split.graphical(seq) for seq in (m, n, residual, tuple(6 - z for z in zeta))]
        cross = split.bipartite_graphical(sigma, zeta)
    mask = sum(int(ok) << i for i, ok in enumerate([*checks, cross]))
    return (q, x, y, *zeta, f, mask)


def histogram_zeros() -> Iterator[tuple[int, ...]]:
    def visit(value: int, left: int, prefix: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
        if value == 7:
            if left == 0:
                yield prefix
            return
        for count in range(left + 1):
            yield from visit(value + 1, left - count, prefix + (value,) * count)

    yield from visit(1, 6, ())


@cache
def enumeration() -> Document:
    rows = [
        record(q, x, y, z)
        for q, x, y in product(range(12), range(3), range(6))
        for z in combinations_with_replacement(range(1, 7), 6)
        if sum(z) == q + x + y
    ]
    other = sorted(
        record(sum(z) - x - y, x, y, z, independent=True)
        for z in histogram_zeros()
        for x in range(3)
        for y in range(6)
        if 0 <= sum(z) - x - y <= 11
    )
    require(
        sorted(rows) == other and len(rows) == len(set(rows)) == 1296,
        "missing enumeration configurations or invalid symmetry reduction",
    )
    feasible = [r for r in rows if r[-1] == 31]
    pinned = sorted(
        (
            c.sigma.count(1) - int(c.sigma[-2] == 1) - int(c.sigma[-1] == 1),
            c.sigma[-2],
            c.sigma[-1],
            *c.zeta,
            c.f,
            31,
        )
        for c in split.degree_configurations(TARGET)
    )
    require(sorted(feasible) == pinned and len(feasible) == 225, "pinned graphical domain mismatch")
    maximum = max(r[-2] for r in rows)
    require(maximum == max(r[-2] for r in feasible) == 238, "wrong universal maximum")
    return {
        "CONFIGURATION_COUNT": len(rows),
        "INDEPENDENT_RECOUNT": len(other),
        "INDEPENDENT_DOMAIN_AND_VALUES_EQUAL": True,
        "ALL_GRAPHICAL_CONFIGURATIONS": len(feasible),
        "MAX_RAW_F": maximum,
        "MAX_GRAPHICAL_F": max(r[-2] for r in feasible),
        "UNIVERSAL_T_CAP": maximum,
        "STATES_PRUNED": 0,
        "COLUMNS": [
            "H5_ONES",
            "SIGMA_D4",
            "SIGMA_D1",
            *[f"ZETA_{i}" for i in range(6)],
            "F",
            "GRAPHICAL_MASK_M_N_RESIDUAL_ZERO_CROSS",
        ],
        "COMPLETE_DOMAIN": [list(r) for r in rows],
        "DOMAIN_SHA256": sha(render(rows)),
        "ARGMAX_CONFIGURATIONS": [list(r) for r in rows if r[-2] == maximum],
        "LEGAL_ATTAINMENT": "UNKNOWN",
    }


def validate_enumeration(value: Mapping[str, object]) -> None:
    require(render(value) == render(enumeration()), "incomplete enumeration or invalid symmetry")


def fraction_terms(cap: int) -> list[Term]:
    """Separate direct Fraction evaluator, including both floor directions."""
    g = [d + 6 for d in D]
    w, j = sum(gv * (gv - 1) // 2 for gv in g), sum(comb(gv, 3) for gv in g)
    allowance = sum(d * (gv - 2) for d, gv in zip(D, g, strict=True)) // 3
    result: list[Term] = []
    for t in range(22, cap + 1):
        need = Fraction(j - (max(g) - 2) * (w - 3 * t), 4)
        k4 = max(0, -(-need.numerator // need.denominator))
        contained = min(k4, allowance)
        s4 = max(112, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * (w - 3 * t) + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        result.append((t, -(-exact.numerator // exact.denominator), k4, contained, s4, s3))
    return result


def validate_rounding(s3: int, s4: int, bound: int) -> None:
    exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
    require(bound == -(-exact.numerator // exact.denominator), "incorrect rational ceiling")


def envelope(cap: int) -> list[Term]:
    require(type(cap) is int and cap in (265, 238), "incorrect T-domain")
    require(route.r28.profile_s4_floor(D) == 112, "inherited S4 drift")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        k4 = max(0, -(-(2310 - 10 * (827 - 3 * t)) // 4))
        contained = min(k4, 197)
        s4 = max(112, 679 * k4 - 231 * contained)
        s3 = 2800 * 827 + 11872 * (t - 22) - 30800
        bound = common.rounded_bound(s3, s4)
        validate_rounding(s3, s4, bound)
        terms.append((t, bound, k4, contained, s4, s3))
    require(
        terms == fraction_terms(cap) == route.route_b_envelope(D, cap, 112),
        "incorrect integer rounding or evaluator drift",
    )
    return terms


def validate_terms(cap: int, terms: Sequence[Sequence[int]]) -> None:
    require(
        [list(t) for t in envelope(cap)] == [list(t) for t in terms],
        "incomplete T-domain or incorrect integer rounding",
    )


def replay_base(base: Mapping[str, object]) -> tuple[dict[str, int], Document]:
    require(sha(render(base)) == BASE_SHA, "wrong Base result SHA256")
    rows = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    bounds = obj(cursor["COARSE_BOUND_PROJECTION"])
    ids = cast(list[str], cursor["PROFILE_IDS"])
    require(
        len(rows) == 4647
        and len(bounds) == len(ids) == len(set(ids)) == 197
        and set(ids) == set(bounds)
        and not set(rows) & set(bounds),
        "coverage mismatch",
    )
    require(
        rows[TARGET] == 313392516 and common.family(rows, cursor) == (313392516, [TARGET]),
        "wrong target row or family",
    )
    return rows, cursor


def apply_update(
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    base: Document,
    updates: Sequence[tuple[str, int]],
) -> dict[str, int]:
    before, frozen = replay_base(base)
    require(
        len(rows) == len(dict(rows)) == len(before) and dict(rows) == before,
        "duplicate or missing ledger row",
    )
    require(render(cursor) == render(frozen), "cursor cohort tampering")
    bound = max(t[1] for t in envelope(238))
    require(list(updates) == [(TARGET, bound)], "duplicate or missing ledger update")
    after = {**before, TARGET: bound}
    require([p for p in before if before[p] != after[p]] == [TARGET], "wrong replacement")
    return after


def family(rows: Mapping[str, int], cursor: Mapping[str, object], incumbent: int) -> Document:
    top, owners = common.family(rows, cursor)
    ordered = sorted(
        [
            *rows.items(),
            *((p, integer(v)) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()),
        ],
        key=lambda item: (-item[1], item[0]),
    )
    require(
        (top, owners) == (ordered[0][1], sorted(p for p, b in ordered if b == ordered[0][1])),
        "independent family scan mismatch",
    )
    return {
        "FAMILY_BOUND": top,
        "OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": top - incumbent,
        "STILL_OPEN_PROFILE_COUNT": sum(b > incumbent for _, b in ordered),
    }


def compute_result() -> Document:
    provenance = source_authority()
    base = load_base()
    before, cursor = replay_base(base)
    old, new = envelope(integer(provenance["CURRENT_T_CAP"])), envelope(238)
    old_bound, bound = max(t[1] for t in old), max(t[1] for t in new)
    require(old_bound == before[TARGET] and bound == 313150736, "complete envelope mismatch")
    after = apply_update(list(before.items()), cursor, base, [(TARGET, bound)])
    incumbent = integer(base["INCUMBENT"])
    baseline, adopted = family(before, cursor, incumbent), family(after, cursor, incumbent)
    require(
        (adopted["FAMILY_BOUND"], adopted["GAP_TO_INCUMBENT"], adopted["STILL_OPEN_PROFILE_COUNT"])
        == (313392412, 128524, 1560),
        "Family replay",
    )
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_SINGLE_LOCAL_COMMIT",
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROOF": __doc__,
        "PROVENANCE": provenance,
        "TARGET_PROFILE": TARGET,
        "MODEL": MODEL,
        "FACTS": facts(),
        "T238_PROOF": enumeration(),
        "ENVELOPE": {
            "CURRENT_T_CAP": provenance["CURRENT_T_CAP"],
            "NEW_PROVEN_T_CAP": 238,
            "OLD_TERMS": [list(t) for t in old],
            "NEW_TERMS": [list(t) for t in new],
            "OLD_TERM_COUNT": len(old),
            "NEW_TERM_COUNT": len(new),
            "FULL_PROFILE_BOUND_BEFORE": old_bound,
            "FULL_PROFILE_BOUND_AFTER": bound,
            "PROFILE_DELTA": old_bound - bound,
            "STRICT_GAIN_EXCLUDED": bound <= incumbent,
            "MARGIN_BELOW_INCUMBENT": incumbent - bound,
            "S4_FLOOR": 112,
            "S5_ADOPTED": False,
            "OFFICIAL_ROUNDING": "CEILING_OF_EXACT_RATIONAL",
            "MAXIMIZING_TERMS": [list(t) for t in new if t[1] == bound],
        },
        "FAMILY_BEFORE": baseline,
        "FAMILY_AFTER": adopted,
        "FAMILY_DELTA": integer(baseline["FAMILY_BOUND"]) - integer(adopted["FAMILY_BOUND"]),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "CURSOR": cursor,
        "RESOLVED_ROWS": len(after),
        "RESOLVED_ROWS_UPDATED": 1,
        "OTHER_RESOLVED_ROWS_UNCHANGED": sum(before[p] == after[p] for p in before),
        "OTHER_RESOLVED_SHA256": sha(
            common.projection({p: b for p, b in before.items() if p != TARGET})
        ),
        "CURSOR_ROWS": len(obj(cursor["COARSE_BOUND_PROJECTION"])),
        "CURSOR_BOUNDS_CHANGED": 0,
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_PRESERVED": True,
        "INHERITED_COHORT_SHA256": sha(render(base["COHORT_PROOF"])),
        "INHERITED_T245_SHA256": sha(render(base["T245_PROOF"])),
        "INHERITED_CAVEATS": "PRESERVED_BY_IMMUTABLE_REFERENCE",
        "HISTORICAL_R15": "NOT_VERIFIED",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "INCUMBENT": incumbent,
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "G01_TO_G18_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 19)},
        "GATE_SCOPE": "Fresh Judge and post-acceptance lifecycle recorded externally",
    }


def verify_result(value: Mapping[str, object]) -> None:
    require(render(value) == render(compute_result()), "deterministic result mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact T238 certificate and Family authority")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = compute_result()
    raw, path = render(value), ROOT / RESULT
    if args.verify or path.exists():
        require(path.is_file() and path.read_bytes() == raw, "sealed result differs")
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    print(
        render(
            {
                "PROFILE_BOUND": obj(value["ENVELOPE"])["FULL_PROFILE_BOUND_AFTER"],
                "FAMILY_AFTER": value["FAMILY_AFTER"],
            }
        )
        .decode()
        .strip()
    )


if __name__ == "__main__":
    main()
