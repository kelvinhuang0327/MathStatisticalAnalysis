"""Goodman certificates for exactly B=66655555554441000000 and C=66655555555422000000.

Premises: 20 tickets of six distinct labels, 22 labels supported on three tickets,
27 on two, and distinct ticket pairs across all supports. The overlap graph G is
simple, has E=3*22+27=93 edges, and g_i=2d_i+(6-d_i)=6+d_i. Both profiles have
sum d_i=66, six zeros, W=sum C(g_i,2)=829. If N_j counts vertex triples with
j edges, W=N_2+3N_3 and 18E=N_1+2N_2+3N_3. Hence I+T=C(20,3)-18E+W=295,
where I=N_0=t(complement G), T=N_3. Independently Goodman gives the same
constant C(20,3)-sum g_i(19-g_i)/2. Open wedges are N_2=W-3T.

Core C consists of the 14 d_i>0 tickets; Z contains the six zeros. All triple
supports lie in C and occupy 66 distinct edges. Let r_i=6-d_i, b_i the number
of C-Z edges at i, a_i=r_i-b_i, and m the number of C-internal pair edges.
sum r_i=18, sum a_i=2m, sum b_i=18-2m. Since each zero has graph degree six,
G[Z] has 9+m edges. The complement graphs H on C and F on Z therefore have
25-m and 6-m edges. Thus 0<=m<=6. Their degrees are h_i=7-d_i+b_i and f_z;
the cross degrees of zeros are c_z=1+f_z. Every legal support structure maps
to one labelled vector b_i in 0..r_i. The internal pair graph with degrees a
and H with degrees h must each pass integer Erdos-Gallai. These are necessary
conditions only; simultaneous or support realizability is never asserted.

Complement triangles split into CCC, CCZ, CZZ, ZZZ. For each H edge ij, at
least 6-b_i-b_j zero vertices are non-neighbours of both endpoints in G.
Therefore I_CCZ>=max(0,6|H|-sum h_i*b_i). For each F edge zw at least
14-c_z-c_w=12-f_z-f_w core vertices are non-neighbours of both endpoints.
Thus I_CZZ+I_ZZZ>=12|F|-sum f_z^2+t(F). All 2^15 labelled six-vertex F
graphs are checked; minima are taken separately at |F|=6-m. This includes
every possible F and deliberately relaxes compatibility with b.

For a core vertex i, put q=13-h_i. Of the |H|-h_i edges not incident with i,
edges outside H[N_H(i)] touch the q vertices outside its neighbour set.
There are at most the sum of the q largest other degrees such edges.
Consequently ell_i=max(0,|H|-h_i-top_q(h_without_i)) counts a lower bound on
triangles through i. I_CCC>=max(max ell_i,ceil(sum ell_i/3)). Summing the four
disjoint triangle types and minimizing over all necessary b vectors gives
I>=56 for B and I>=58 for C, so T<=239 and T<=237 respectively. These numbers
are outputs of the finite verification, not imported premises. It follows
that G has at least 112 and 118 open wedges respectively. Attainment is unknown.

For every integer 22<=T<=cap, retain R32's S4 base and contained-triple rules:
K4>=max(0,ceil((sum C(g_i,3)-(g_max-2)(W-3T))/4)),
A_max=floor(sum d_i(g_i-2)/3), a=min(K4,A_max),
S4>=max(base,448a+679(K4-a)). The complete Route-B envelope is checked against
both existing implementations and independent integer/rational arithmetic.
Exactly B and C are replaced in a copy of the pinned T248 4647-row ledger.
Owner A and the unresolved cursor stay in the family maximum. All inherited
Judge statuses and source caveats stay verbatim. No solver, portfolio/outcome
enumeration, shared ledger write, RUN1 mutation, or remote action is performed.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from itertools import combinations, product
from math import comb, prod
from pathlib import Path

from . import b649_min_s2_post_t256_next_owner_cap248_cert_r1 as prior

TASK_ID = "B649_MIN_S2_TIED_OWNERS_BC_GOODMAN239_237_CERT_R1"
BASE_HEAD = "8d2411474c721264697438428b09a2ff00ea6802"
BASE_TREE = "e7b2717e4f31d40bc213d6918a58b86a486f0375"
T248_RESULT_SHA256 = "28fe692403cb193ee908708c7775b45bd80a2e4cf731b4d4e015d71c5558aabe"
T248_JUDGE_RECORD = f"Fresh-context Judge: VERIFIED_WITH_CAVEATS on tree {BASE_TREE}."
PROFILE_B = "66655555554441000000"
PROFILE_C = "66655555555422000000"
TARGETS = (PROFILE_B, PROFILE_C)
OWNER_A = "66555555555531000000"
FAMILY_BOUND = 313_398_248
INCUMBENT = prior.INCUMBENT
GOODMAN_CONSTANT = 295
TICKET_CAPACITY = 6
TRIPLE_SUPPORTS = 22
PAIR_SUPPORTS = 27
RESULT_STEM = "b649-min-s2-tied-owners-bc-goodman-cert-r1"
ROOT = prior.ROOT
RESULT_DIRECTORY = prior.two.RESULT_DIRECTORY
T248_RESULT_PATH = f"{RESULT_DIRECTORY}/{prior.RESULT_STEM}-result.json"
require, sha256 = prior.require, prior.sha256
integer, object_row, rows, text = prior.integer, prior.object_row, prior.rows, prior.text
two, three, chase, split, r32, r5 = (
    prior.two,
    prior.three,
    prior.chase,
    prior.split,
    prior.r32,
    prior.r5,
)
Row, Support, Term = prior.Row, prior.Support, prior.Term
PRESERVED_T248_FIELDS = (
    "TASK_ID",
    "TASK_STATUS",
    "T256_JUDGE_RECORD",
    "PRESERVED_T256_STATUS",
    "INHERITED_STATUS_SOURCE",
    "PRIOR_ART",
    "GLOBAL_K20_OPTIMUM",
)
HISTORICAL_SOURCE = {
    "PATH": "/Users/kelvin/.codex/worktrees/b649-k20-goodman-next-three-r1/"
    "MathStatisticalAnalysis/goodman_next_three_verifier.py",
    "STATUS": "SCIENTIFIC_PASS_RESOURCE_CONFORMANCE_FAIL",
    "ROLE": "METHOD_REFERENCE_ONLY_NOT_CERTIFICATE_AUTHORITY_NOT_EXECUTED_BY_VERIFIER",
    "HISTORICAL_CAPS": {PROFILE_B: 239, PROFILE_C: 237},
    "HISTORICAL_I_FLOORS": {PROFILE_B: 56, PROFILE_C: 58},
    "USE": "PROFILE_IDENTITY_GOODMAN_AND_FINITE_DOMAINS_REVERIFIED_HERE",
}


@dataclass(frozen=True)
class ZeroProof:
    """Complete six-vertex graph domain; the three fields use the core-pair count m."""

    floors: tuple[int, ...]
    counts: tuple[int, ...]
    witnesses: tuple[dict[str, object], ...]
    graphs_checked: int


def profile_degrees(profile: str) -> tuple[int, ...]:
    require(profile in TARGETS, "theorem handles exactly B and C")
    d = split.profile_values(profile)
    require(chase.profile_id(d) == profile, "profile identity differs")
    return d


def premises(profile: str) -> dict[str, object]:
    d = profile_degrees(profile)
    model = three.support_model()
    g = [TICKET_CAPACITY + v for v in d]
    core = [v for v in d if v]
    edges = sum(g) // 2
    wedges = sum(comb(v, 2) for v in g)
    constant = comb(20, 3) - 18 * edges + wedges
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    classes = Counter(core)
    expected = {6: 3, 5: 7, 4: 3, 1: 1} if profile == PROFILE_B else {6: 3, 5: 8, 4: 1, 2: 2}
    require(
        (TICKET_CAPACITY, TRIPLE_SUPPORTS, PAIR_SUPPORTS) == (6, 22, 27)
        and model["TICKET_CAPACITY"] == TICKET_CAPACITY
        and model["TRIPLE_SUPPORTS"] == TRIPLE_SUPPORTS
        and model["PAIR_SUPPORTS"] == PAIR_SUPPORTS
        and len(core) == 14
        and d.count(0) == 6
        and sum(d) == 3 * TRIPLE_SUPPORTS
        and classes == expected
        and sum(TICKET_CAPACITY - v for v in core) == 18
        and sum(g) == 2 * edges
        and edges == 3 * TRIPLE_SUPPORTS + PAIR_SUPPORTS == 93
        and wedges == 829
        and constant == goodman == GOODMAN_CONSTANT,
        "profile/support/Goodman premises fail",
    )
    return {
        "PROFILE_ID": profile,
        "TRIPLE_DEGREES": list(d),
        "GRAPH_DEGREES": g,
        "CORE_DEGREE_CLASSES": {str(k): v for k, v in sorted(classes.items(), reverse=True)},
        "CORE_VERTICES": len(core),
        "ZERO_VERTICES": d.count(0),
        "G_EDGES": edges,
        "H_EDGES": comb(20, 2) - edges,
        "W": wedges,
        "GOODMAN_INCLUSION_EXCLUSION": constant,
        "GOODMAN_DEGREE_PRODUCT": int(goodman),
        "GOODMAN_IDENTITY": "T+I=295",
        "SUPPORT_MODEL": model,
    }


def core_triangle_floor(degrees: Sequence[int], edge_count: int) -> int:
    """Universal t(H) floor for a simple 14-vertex H with these degrees."""
    require(len(degrees) == 14 and sum(degrees) == 2 * edge_count, "core degree sum differs")
    require(split.graphical(degrees), "core complement degrees not graphical")
    vertex: list[int] = []
    for i, degree in enumerate(degrees):
        outside = sorted((*degrees[:i], *degrees[i + 1 :]), reverse=True)
        vertex.append(max(0, edge_count - degree - sum(outside[: 13 - degree])))
    return max(max(vertex), (sum(vertex) + 2) // 3)


def zero_graphs() -> ZeroProof:
    """Every labelled F, including direct Goodman and open-wedge counts on six vertices."""
    slots = list(combinations(range(6), 2))
    triples = list(combinations(range(6), 3))
    floors: dict[int, int] = {}
    counts = [0] * 7
    witnesses: dict[int, dict[str, object]] = {}
    for mask in range(1 << len(slots)):
        f, adjacency = [0] * 6, [0] * 6
        for index, (u, v) in enumerate(slots):
            if mask >> index & 1:
                f[u] += 1
                f[v] += 1
                adjacency[u] |= 1 << v
                adjacency[v] |= 1 << u
        n = [0] * 4
        for u, v, w in triples:
            edge_total = ((adjacency[u] >> v) & 1) + ((adjacency[u] >> w) & 1)
            edge_total += (adjacency[v] >> w) & 1
            n[edge_total] += 1
        edge_count = mask.bit_count()
        wedges = sum(comb(v, 2) for v in f)
        require(
            split.graphical(f)
            and sum(f) == 2 * edge_count
            and n[2] == wedges - 3 * n[3]
            and n[0] + n[3] == comb(6, 3) - 4 * edge_count + wedges,
            "six-vertex graph count/Goodman/open-wedge identity fails",
        )
        if edge_count > 6:
            continue
        m = 6 - edge_count
        counts[m] += 1
        floor = 12 * edge_count - sum(v * v for v in f) + n[3]
        if m not in floors or floor < floors[m]:
            floors[m] = floor
            witnesses[m] = {"F_MASK": mask, "F_DEGREES": f, "F_TRIANGLES": n[3]}
    require(counts == [comb(15, 6 - m) for m in range(7)], "zero graph domain incomplete")
    return ZeroProof(
        tuple(floors[m] for m in range(7)),
        tuple(counts),
        tuple(witnesses[m] for m in range(7)),
        1 << len(slots),
    )


def core_reduction(profile: str, zero: ZeroProof) -> dict[str, object]:
    """Stream the entire labelled b domain; exclude only necessary-condition failures."""
    d = [v for v in profile_degrees(profile) if v]
    capacities = [TICKET_CAPACITY - v for v in d]
    counts = [0] * 7
    floors: dict[int, int] = {}
    witnesses: dict[int, dict[str, object]] = {}
    raw_count = 0
    for b in product(*(range(v + 1) for v in capacities)):
        raw_count += 1
        cross = sum(b)
        if not 6 <= cross <= 18 or cross % 2:
            continue
        m = (18 - cross) // 2
        a = [v - x for v, x in zip(capacities, b, strict=True)]
        h = [7 - v + x for v, x in zip(d, b, strict=True)]
        if not split.graphical(a) or not split.graphical(h):
            continue
        edges = 25 - m
        require(sum(a) == 2 * m and sum(h) == 2 * edges, "core reduction identity fails")
        counts[m] += 1
        ccz = max(0, 6 * edges - sum(v * x for v, x in zip(h, b, strict=True)))
        ccc = core_triangle_floor(h, edges)
        floor = ccz + ccc + zero.floors[m]
        if m not in floors or floor < floors[m]:
            floors[m] = floor
            witnesses[m] = {
                "B": list(b),
                "A": a,
                "H_DEGREES": h,
                "H_EDGES": edges,
                "CCZ_FLOOR": ccz,
                "CCC_FLOOR": ccc,
                "CZZ_ZZZ_FLOOR": zero.floors[m],
            }
    require(raw_count == prod(v + 1 for v in capacities), "labelled core domain incomplete")
    require(all(counts), "empty core-pair stratum")
    return {
        "PAIR_CAPACITIES": capacities,
        "RAW_LABELLED_VECTORS_CHECKED": raw_count,
        "ACCEPTED_NECESSARY_VECTORS_BY_M": counts,
        "I_FLOORS_BY_M": [floors[m] for m in range(7)],
        "MINIMIZERS_BY_M": [witnesses[m] for m in range(7)],
        "I_LOWER_BOUND": min(floors.values()),
        "DOMAIN": "ALL_LABELLED_B_IN_0_TO_6_MINUS_D_EG_ON_A_AND_H_NECESSARY_ONLY",
        "RELAXED_MINIMIZERS_REALIZABLE": "NOT_ASSERTED",
    }


def theorem(profile: str, zero: ZeroProof) -> dict[str, object]:
    facts = premises(profile)
    reduced = core_reduction(profile, zero)
    floor = integer(reduced["I_LOWER_BOUND"])
    cap = integer(facts["GOODMAN_INCLUSION_EXCLUSION"]) - floor
    require(22 <= cap < 265, "Goodman proof does not tighten the triangle cap")
    return {
        **facts,
        **reduced,
        "TRIANGLE_CAP": cap,
        "OPEN_WEDGE_LOWER_BOUND": integer(facts["W"]) - 3 * cap,
        "LEGAL_M": list(range(7)),
        "G_CORE_PAIR_EDGES": "m",
        "CROSS_EDGES": "18-2m",
        "G_ZERO_EDGES": "9+m",
        "H_CORE_EDGES": "25-m",
        "H_ZERO_EDGES": "6-m",
        "H_CORE_DEGREES": "7-d+b",
        "ZERO_CROSS_DEGREES": "1+f",
        "I_DECOMPOSITION": "I_CCC+I_CCZ+I_CZZ+I_ZZZ",
        "CCC_RULE": "max(max ell_i,ceil(sum ell_i/3))",
        "ELL_RULE": "max(0,|H|-h_i-sum_largest_(13-h_i)_other_degrees)",
        "CCZ_RULE": "max(0,6|H|-sum h_i*b_i)",
        "CZZ_ZZZ_RULE": "12|F|-sum f_z^2+t(F)",
        "STATUS": "PROVEN",
        "ATTAINMENT": "NOT_ASSERTED",
    }


def realization_check(
    profile: str, triples: Sequence[Support], pairs: Sequence[Support], cap: int
) -> dict[str, object]:
    """Check each stored support witness, then directly count every complement triangle type."""
    d = three.legal_degrees(triples, pairs)
    r5.validate_k20_support_realization(triples, pairs, d)
    require(tuple(sorted(d, reverse=True)) == profile_degrees(profile), "wrong realization profile")
    g = {prior.t256.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    core, zero = [v for v in range(20) if d[v]], [v for v in range(20) if not d[v]]
    seen = prior.t256.complement_split(core, zero, g)
    h = set(combinations(range(20), 2)) - g
    by_core_count = [0] * 4
    for q in combinations(range(20), 3):
        if all(e in h for e in combinations(q, 2)):
            by_core_count[sum(v in core for v in q)] += 1
    b = [integer(v) for v in rows(seen["SIGMA"])]
    hd = [integer(v) for v in rows(seen["H_CORE"])]
    f = [integer(v) for v in rows(seen["A_ZERO"])]
    m = (18 - sum(b)) // 2
    edge_count = integer(seen["M_EDGES"])
    ccc_floor = core_triangle_floor(hd, edge_count)
    ccz_floor = max(0, 6 * edge_count - sum(x * v for x, v in zip(b, hd, strict=True)))
    czz_zzz_floor = 12 * (6 - m) - sum(v * v for v in f) + by_core_count[0]
    t, independent = integer(seen["T_G"]), integer(seen["T_H"])
    open_wedges = sum(
        sum(e in g for e in combinations(q, 2)) == 2 for q in combinations(range(20), 3)
    )
    require(
        len(g) == 93
        and sum(by_core_count) == independent
        and t + independent == GOODMAN_CONSTANT
        and [sum(v in e for e in g) for v in range(20)] == [6 + v for v in d]
        and all(0 <= x <= 6 - d[v] for v, x in zip(core, b, strict=True))
        and 0 <= m <= 6
        and edge_count == 25 - m
        and integer(seen["MZ_EDGES"]) == 6 - m
        and rows(seen["ZETA"]) == [1 + v for v in f]
        and by_core_count[3] >= ccc_floor
        and by_core_count[2] >= ccz_floor
        and by_core_count[0] + by_core_count[1] >= czz_zzz_floor
        and open_wedges == 829 - 3 * t
        and t <= cap,
        "realization violates the Goodman/core-zero/open-wedge chain",
    )
    return {
        "PROFILE_ID": profile,
        **seen,
        "I_BY_CORE_COUNT_0_TO_3": by_core_count,
        "I_FLOOR_PARTS_CCC_CCZ_CZZ_ZZZ": [ccc_floor, ccz_floor, czz_zzz_floor],
        "OPEN_WEDGES": open_wedges,
        "STATUS": "PASS",
    }


def route_b(profile: str, cap: int, base: int) -> tuple[list[Term], int]:
    """Complete R32 envelope, with its existing S4 base and independent exact arithmetic."""
    require(type(cap) is int and 22 <= cap <= 265, "invalid triangle cap")
    require(type(base) is int and base >= 0, "invalid S4 base")
    d = profile_degrees(profile)
    terms = r32.route_b_envelope(d, cap, base)
    require(terms == split.route_b_terms(d, cap, base), "Route-B implementations differ")
    require([t[0] for t in terms] == list(range(22, cap + 1)), "Route-B triangle domain differs")
    g = [6 + v for v in d]
    wedges, choose3 = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a_numerator = sum(v * (degree - 2) for v, degree in zip(d, g, strict=True))
    for t, bound, k4, contained, s4, s3 in terms:
        numerator = choose3 - (max(g) - 2) * (wedges - 3 * t)
        k4_exact = max(0, -((-numerator) // 4))
        a_exact = min(k4_exact, a_numerator // 3)
        s4_exact = max(base, 448 * a_exact + 679 * (k4_exact - a_exact))
        s3_exact = 2800 * wedges + 11872 * (t - 22) - 1400 * 22
        integer_bound = 372_228_640 - 63_838_600 + s3_exact - 4 * s4_exact // 7
        rational_bound = Fraction(372_228_640 - 63_838_600 + s3_exact) - Fraction(4 * s4_exact, 7)
        require(
            (k4, contained, s4, s3, bound) == (k4_exact, a_exact, s4_exact, s3_exact, integer_bound)
            and 0 <= bound - rational_bound < 1,
            f"Route-B term {t} fails exact arithmetic",
        )
    return terms, max(term[1] for term in terms)


def module_provenance() -> dict[str, str]:
    out = prior.module_provenance()
    for module in (prior,):
        require(module.__file__ is not None, "reused module has no source")
        path = Path(text(module.__file__)).resolve()
        require(path.is_relative_to(ROOT), "reused module outside this worktree")
        relative = path.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        require(path.read_bytes() == committed, "T248 module changed")
        out[relative] = sha256(committed)
    return dict(sorted(out.items()))


def frozen_authority() -> tuple[dict[str, object], dict[str, Row]]:
    """Rebuild the frozen T248 ledger, without calling its scientific/search entrypoints."""
    require(three.git_tree(BASE_HEAD) == BASE_TREE, "T248 base tree mismatch")
    raw = two.blob(BASE_HEAD, T248_RESULT_PATH, T248_RESULT_SHA256)
    require((ROOT / T248_RESULT_PATH).read_bytes() == raw, "T248 result changed")
    stem = prior.__name__.rsplit(".", 1)[1]
    for path in (f"src/lottolab/research/{stem}.py", f"tests/unit/test_{stem}.py"):
        require(
            (ROOT / path).read_bytes() == chase.git("show", f"{BASE_HEAD}:{path}"),
            "T248 source/test changed",
        )
    message = chase.git("log", "-1", "--format=%B", BASE_HEAD).decode()
    require(T248_JUDGE_RECORD in message.splitlines(), "T248 Judge record missing")
    result = object_row(json.loads(raw))
    seven_result, seven = prior.seven_row_authority()
    update = object_row(object_row(result["ROW_UPDATE"])["AFTER"])
    ledger = prior.apply_eighth(
        seven, integer(update["bound"]), integer(update["cap"]), text(update["source"])
    )
    require(
        len(ledger) == result["LEDGER_ROWS"] == 4647
        and two.full_digest(seven) == result["FULL_ROWS_SHA256_BEFORE"]
        and two.full_digest(ledger) == result["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(ledger) == result["BOUNDS_SHA256_AFTER"]
        and json.loads(json.dumps(asdict(ledger[prior.TARGET_PROFILE]))) == update
        and list(three.family(ledger))
        == [result[k] for k in ("FAMILY_BOUND_AFTER", "NEXT_OWNER_IDS", "NEXT_COMPETING_BOUND")]
        and result["FAMILY_BOUND_AFTER"] == FAMILY_BOUND
        and result["NEXT_OWNER_IDS"] == sorted([OWNER_A, *TARGETS])
        and result["PRESERVED_T256_STATUS"]
        == {
            k: seven_result[k]
            for k in ("TASK_ID", "TASK_STATUS", "PRESERVED_SIX_ROW_STATUS", "GLOBAL_K20_OPTIMUM")
        },
        "frozen T248 ledger does not reproduce its exact result",
    )
    return result, ledger


def apply_bc(ledger: Mapping[str, Row], updates: Mapping[str, tuple[int, int]]) -> dict[str, Row]:
    """Exactly two stricter (bound, cap) pairs, preserving every other row field and row."""
    require(set(updates) == set(TARGETS), "updates must be exactly B and C")
    before = two.full_digest(ledger)
    after = dict(ledger)
    for profile in TARGETS:
        old = ledger[profile]
        bound, cap = updates[profile]
        require(type(bound) is int and type(cap) is int, "update must use exact integers")
        require(
            (old.bound, old.cap, old.s4_base) == (FAMILY_BOUND, 265, 112)
            and bound < old.bound
            and 22 <= cap < old.cap,
            "BC update does not tighten the frozen row",
        )
        after[profile] = replace(
            old, bound=bound, cap=cap, source=f"{TASK_ID}:{profile}:GOODMAN_THEOREM"
        )
    require(
        set(after) == set(ledger)
        and sorted(p for p in ledger if ledger[p] != after[p]) == sorted(TARGETS)
        and two.full_digest(ledger) == before
        and after[OWNER_A] == ledger[OWNER_A],
        "BC update changed another row or the frozen ledger",
    )
    return after


def compute_result() -> dict[str, object]:
    provenance = module_provenance()
    frozen, ledger = frozen_authority()
    zero = zero_graphs()
    certificates: list[dict[str, object]] = []
    updates: dict[str, tuple[int, int]] = {}
    for profile in TARGETS:
        proof = theorem(profile, zero)
        row = ledger[profile]
        cap = min(row.cap, integer(proof["TRIANGLE_CAP"]))
        old_terms, old_bound = route_b(profile, row.cap, row.s4_base)
        terms, bound = route_b(profile, cap, row.s4_base)
        require(old_bound == row.bound == FAMILY_BOUND, "old Route-B bound differs from frozen row")
        require(
            terms == old_terms[: len(terms)],
            "new envelope is not a prefix of the frozen cap envelope",
        )
        seen = (
            realization_check(profile, row.realization[0], row.realization[1], cap)
            if row.realization is not None
            else {
                "PROFILE_ID": profile,
                "STATUS": "NOT_AVAILABLE_FROZEN_ROW_HAS_NO_REALIZATION",
                "PROOF_ROLE": "UNIVERSAL_NECESSARY_CONDITION_PROOF_DOES_NOT_REQUIRE_A_WITNESS",
            }
        )
        updates[profile] = (bound, cap)
        certificates.append(
            {
                "PROFILE_ID": profile,
                "THEOREM": proof,
                "THEOREM_STATUS": "PASS",
                "CERTIFIED_T_CAP": cap,
                "NEW_BOUND": bound,
                "STRICT_GAIN_EXCLUDED": bound <= INCUMBENT,
                "MARGIN_TO_INCUMBENT": INCUMBENT - bound,
                "RECORDED_REALIZATION": seen,
                "ROUTE_B": {
                    "STATUS": "PASS_INTEGER_AND_RATIONAL",
                    "S4_BASE": row.s4_base,
                    "BOUND_RULE": r32.BOUND_RULE,
                    "CAP_BEFORE": row.cap,
                    "BOUND_BEFORE": old_bound,
                    "TERM_COUNT": len(terms),
                    "ALL_T_TERMS": [list(t) for t in terms],
                    "ALL_T_MAX_BOUND": bound,
                    "ARGMAX_TERMS": [list(t) for t in terms if t[1] == bound],
                    "PREFIX_OF_FROZEN_CAP_ENVELOPE": True,
                },
            }
        )
    after = apply_bc(ledger, updates)
    before, before_owners, _ = three.family(ledger)
    best, owners, next_level = three.family(after)
    previous = [text(p) for p in rows(frozen["CERTIFICATE_PROFILE_IDS"])]
    require(
        all(after[p] == ledger[p] for p in previous)
        and not set(previous).intersection(TARGETS)
        and (before, before_owners) == (FAMILY_BOUND, sorted([OWNER_A, *TARGETS]))
        and (best, owners) == (FAMILY_BOUND, [OWNER_A])
        and after[OWNER_A].bound == FAMILY_BOUND,
        "prior certificates, Owner A, or family maximum were not preserved",
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "BC_CERTIFICATES_PENDING_FRESH_JUDGE",
        "PROOF": __doc__,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "T248_RESULT_SHA256": T248_RESULT_SHA256,
        "T248_JUDGE_RECORD": T248_JUDGE_RECORD,
        "T248_AUTHORITY_COMMIT_MESSAGE": chase.git("log", "-1", "--format=%B", BASE_HEAD).decode(),
        "PRESERVED_T248_STATUS": {k: frozen[k] for k in PRESERVED_T248_FIELDS},
        "INHERITED_STATUS_SOURCE": "VERBATIM_T248_FIELDS_NOT_UPGRADED",
        "HISTORICAL_SOURCE": HISTORICAL_SOURCE,
        "MODULE_PROVENANCE": provenance,
        "ZERO_GRAPH_PROOF": asdict(zero),
        "PROFILES": certificates,
        "INCUMBENT": INCUMBENT,
        "STRICT_GAIN_THRESHOLD": INCUMBENT + 1,
        "LEDGER_ROWS": len(after),
        "ROWS_CHANGED": sorted(updates),
        "ROW_UPDATES": {
            p: {"BEFORE": asdict(ledger[p]), "AFTER": asdict(after[p])} for p in TARGETS
        },
        "CERTIFICATES_COMPOSED": len(previous) + 2,
        "PRIOR_CERTIFICATE_IDS": previous,
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_BOUND_AFTER_BC_ONLY": best,
        "FAMILY_DELTA_BC_ONLY": before - best,
        "FAMILY_OWNER_IDS_AFTER": owners,
        "NEXT_COMPETING_BOUND": next_level,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "OWNER_A_UNMODIFIED": "YES",
        "OWNER_A_ROW": asdict(after[OWNER_A]),
        "CURSOR_ID": chase.prior.CURSOR_ID,
        "CURSOR_BOUND": chase.prior.CURSOR_BOUND,
        "CURSOR_STATUS": "UNRESOLVED_AUTHORITY_UNCHANGED",
        "FULL_ROWS_SHA256_BEFORE": two.full_digest(ledger),
        "FULL_ROWS_SHA256_AFTER": two.full_digest(after),
        "BOUNDS_SHA256_BEFORE": two.bounds_digest(ledger),
        "BOUNDS_SHA256_AFTER": two.bounds_digest(after),
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SEARCH_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "PORTFOLIO_ENUMERATIONS": 0,
        "RESOURCE_POLICY": "SINGLE_PROCESS_STREAMING_FINITE_GRAPH_AND_DEGREE_DOMAINS",
    }


def main() -> None:
    result = compute_result()
    payload = two.render(result)
    digest = sha256(payload)
    target = ROOT / RESULT_DIRECTORY / f"{RESULT_STEM}-{digest}.json"
    if target.exists():
        require(target.read_bytes() == payload, "existing content-addressed result differs")
    else:
        require(
            not list(target.parent.glob(f"{RESULT_STEM}-*.json")), "only one result is authorized"
        )
        with target.open("xb") as output:
            output.write(payload)
    summary_keys = ("PROFILE_ID", "CERTIFIED_T_CAP", "NEW_BOUND", "STRICT_GAIN_EXCLUDED")
    profile_rows = [object_row(v) for v in rows(result["PROFILES"])]
    print(
        json.dumps(
            {
                "RESULT": str(target),
                "SHA256": digest,
                "PROFILES": [{k: r[k] for k in summary_keys} for r in profile_rows],
                "FAMILY_BOUND_AFTER_BC_ONLY": result["FAMILY_BOUND_AFTER_BC_ONLY"],
            }
        )
    )


if __name__ == "__main__":
    main()
