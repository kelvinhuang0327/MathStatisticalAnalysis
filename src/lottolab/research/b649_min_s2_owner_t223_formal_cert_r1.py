"""Universal T<=223 certificate for the single profile 66555555554442000000.

Proof from the frozen support model. Each of the 49 labels has a support of
size two or three: 22 triples and 27 pairs on 20 tickets. Pair-linearity
means no ticket pair occurs in two label supports. A ticket with d triple
labels has 6-d pair labels, hence 2d+(6-d)=6+d distinct overlap neighbours.
The overlap graph G is simple, has 93 edges, and has at least the 22 distinct
support triangles. Its complement H has 97 edges and degrees 13-d.

For each vertex triple, inclusion-exclusion of the events that its three
possible edges belong to H gives
 T(G)=C(20,3)-18|E(H)|+sum_v C(deg_H(v),2)-T(H)=291-T(H).
The last constant is evaluated from this exact degree profile, not inferred
from an observed realization.

Let K={d>0}, Z={d=0}; |K|=14, |Z|=6. Put M=H[K], N=H[Z]. Define
sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|. The respective
internal H degrees are h_x=7-d_x+sigma_x and a_u=zeta_u-1. Write
 P=T(M)+T(N)
   +sum_{xy in E(M)} |N_G(x) intersect N_G(y) intersect Z|
   +sum_{uv in E(N)} |N_G(u) intersect N_G(v) intersect K|.
This is an explicit sum of nonnegative cardinalities, so P>=0, independently
of any enumeration or support attainability claim. A mixed H triangle has
exactly one same-part edge. For xy in M its possible zero vertices number
6-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|; for uv in N the
corresponding expression is 14-zeta_u-zeta_v+their common G core neighbours.
Thus
 T(H)=6|E(M)|+14|E(N)|-sum_x sigma_x h_x-sum_u zeta_u a_u+P,
 T(G)=291-3 sum h-7 sum a+sum sigma*h+sum zeta*a-P=F-P.
With C=sum sigma=sum zeta, sum h=32+C and sum a=C-6. Substitution yields
 F=237+sum_x sigma_x(sigma_x+3-d_x)+sum_u zeta_u(zeta_u-7).

Coverage. Z has no triple label, so every cross edge is a pair label and
0<=sigma_x<=6-d_x. Each zero has six neighbours, at most five in Z;
1<=zeta_u<=6. Each legal realization supplies simple graphs of degrees h,
a, 6-d-sigma (the core pair-label graph), and 6-zeta (G[Z]), and a simple
bipartite cross graph with degrees sigma,zeta. Therefore all four graphical
tests and the Gale-Ryser conditions are necessary. Requiring their separate
existence is a relaxation; simultaneous existence is never assumed.

Permutations within each equal-d class and within Z are bijective vertex
relabelings of legal supports. Sorting sigma separately in the 6^2,5^8,4^3,2
classes and sorting zeta therefore retains a representative of every legal
structure. F and every necessary test are invariant under these permutations.
The core choices number 1*9*10*5=450; the zero choices number C(11,6)=462.
Both complete domains are generated twice by different procedures. All
207900 canonical pairs are accounted for; 2420 have equal cross totals.
Erdos-Gallai plus core-side Gale-Ryser retains 498 states, independently
matched state-for-state by Havel-Hakimi plus zero-side Gale-Ryser. Exact
integer evaluation of F on this superset has maximum 223. Every legal
realization maps to a retained state, so T=F-P<=F<=223 universally.
Neither the maximizing degree state nor this upper bound asserts that a
legal support realization attains T=223.

Route B is computed at every integer t=22..223 using integer ceilings and
independently checked with Fractions and the pinned existing bound helpers.
Only this target's bound is replaced in an in-memory copy of the immutable
Base ledger. The complete cursor and all historical caveats remain verbatim.
"""

from __future__ import annotations

import argparse
import ast
import json
import stat
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split
from . import b649_min_s2_owner_ab_exact_family_composition_r1 as inherited

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_T223_FORMAL_CERT_R1"
OWNER_CONVERSATION_ID = "01a1335a-c605-7742-a1f8-0689d25a8bc5"
BASE_HEAD = "b1145036c33230d09de0f9c29f831ab1053188a2"
BASE_TREE = "12490e36b382081b7ec07be84676644cd0897a3d"
BASE_LS_TREE_SHA256 = "a27cdc24af6f3de3331e72c0aad813cb9c419f2f4b0fcfd9956825c360b47fba"
DIRECTORY = "docs/research/matrix-native-results"
BASE_RESULT_SHA256 = "f86b27c0481dda62ef25ff390ba2f4b58987faf7aa2d8b4c4a8302cb83ddb643"
BASE_RESULT = (
    f"{DIRECTORY}/b649-min-s2-owner-ab-exact-family-composition-r1-result-{BASE_RESULT_SHA256}.json"
)
SOURCE = "src/lottolab/research/b649_min_s2_owner_t223_formal_cert_r1.py"
TEST = "tests/unit/test_b649_min_s2_owner_t223_formal_cert_r1.py"
RESULT = f"{DIRECTORY}/b649-min-s2-owner-t223-formal-cert-r1-result.json"
SPLIT_SOURCE = "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py"
SPLIT_SHA256 = "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784"
R30_RESULT = f"{DIRECTORY}/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
R30_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
TARGET = "66555555554442000000"
D = (6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4, 4, 2, 0, 0, 0, 0, 0, 0)
MODEL: dict[str, object] = {
    "TICKETS": 20,
    "LABELS_PER_TICKET": 6,
    "TRIPLES": 22,
    "PAIRS": 27,
    "PAIR_LINEARITY": True,
}
type Document = dict[str, object]
type Degrees = tuple[int, ...]
type State = tuple[Degrees, Degrees, int]
type Term = tuple[int, int, int, int, int, int]
require = inherited.require
obj = inherited.obj
items = inherited.items
integer = inherited.integer
string = inherited.string
sha = inherited.sha
render = inherited.render
git = inherited.git


def model_facts(pid: str = TARGET, model: Mapping[str, object] | None = None) -> Document:
    frozen = MODEL if model is None else model
    require(pid == TARGET and inherited.profile(pid) == D, "wrong target profile")
    require(
        dict(frozen) == MODEL
        and frozen["PAIR_LINEARITY"] is True
        and all(type(frozen[k]) is int for k in MODEL if k != "PAIR_LINEARITY"),
        "weakened frozen support model",
    )
    require(
        (split.prior.K20_TICKET_COUNT, split.prior.K20_TICKET_CAPACITY) == (20, 6)
        and split.prior.K20_TRIPLE_SUPPORT_COUNT == 22
        and split.prior.r5.K20_DOUBLE_SUPPORT_COUNT == 27,
        "pinned model constants differ",
    )
    g = tuple(6 + d for d in D)
    return {
        "MODEL": dict(frozen),
        "D": list(D),
        "CORE": 14,
        "ZEROS": 6,
        "G_EDGES": sum(g) // 2,
        "H_EDGES": comb(20, 2) - sum(g) // 2,
        "PHI": comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in D),
        "WEDGES": sum(comb(v, 2) for v in g),
        "THIRD_DEGREES": sum(comb(v, 3) for v in g),
        "CONTAINED_K4_CAP": sum(d * (4 + d) for d in D) // 3,
    }


def pinned_sources() -> dict[str, str]:
    """Pin the actual relative-import closure of the two reused helper roots."""
    pending = [SPLIT_SOURCE, inherited.SOURCE]
    pins: dict[str, str] = {}
    while pending:
        path = pending.pop()
        if path in pins:
            continue
        raw = git("cat-file", "blob", f"{BASE_HEAD}:{path}")
        digest = sha(raw)
        inherited.checked_blob(BASE_HEAD, path, digest)
        local = ROOT / path
        require(stat.S_ISREG(local.lstat().st_mode), "unsafe reused source")
        require(local.read_bytes() == raw, f"reused source drift: {path}")
        pins[path] = digest
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.ImportFrom) and node.level:
                require(node.level == 1, "unexpected relative helper import")
                names = [node.module] if node.module else [a.name for a in node.names]
                pending.extend(f"src/lottolab/research/{name}.py" for name in names)
    require(pins[SPLIT_SOURCE] == SPLIT_SHA256, "split source SHA256 differs")
    return dict(sorted(pins.items()))


def load_authority() -> Document:
    require(git("cat-file", "-t", BASE_HEAD).strip() == b"commit", "missing Base commit")
    require(
        git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE,
        "Base tree mismatch",
    )
    tree = git("ls-tree", "-rz", BASE_HEAD)
    require(sha(tree) == BASE_LS_TREE_SHA256, "complete Base tree inventory differs")
    raw = inherited.checked_blob(BASE_HEAD, BASE_RESULT, BASE_RESULT_SHA256)
    base = inherited.decode(raw)
    require(render(base) == raw, "noncanonical Base result")
    pins = pinned_sources()
    require(base["IMPLEMENTATION_SHA256"] == pins[inherited.SOURCE], "Base source binding")
    inherited.checked_blob(BASE_HEAD, inherited.TEST, string(base["TEST_SHA256"]))
    for path in (BASE_RESULT, inherited.TEST):
        local = ROOT / path
        require(stat.S_ISREG(local.lstat().st_mode), "unsafe inherited file")
        require(local.read_bytes() == git("cat-file", "blob", f"{BASE_HEAD}:{path}"), "Base drift")
    message = git("cat-file", "commit", BASE_HEAD).split(b"\n\n", 1)[1].decode()
    require(
        "Fresh-context Judge: VERIFIED_WITH_CAVEATS\n" in message
        and f"Judged-tree: {BASE_TREE}\n" in message
        and BASE_RESULT_SHA256 in message,
        "Base accepted Judge binding differs",
    )
    r30 = inherited.decode(inherited.checked_blob(BASE_HEAD, R30_RESULT, R30_SHA256))
    cap = obj(items(r30["GROUP_ATTEMPTS"])[2740])
    require(
        cap["ATTEMPT_INDEX"] == 2740
        and cap["PROFILE_IDS"] == [TARGET]
        and cap["STATUS"] == "INFEASIBLE"
        and cap["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 266
        and cap["WEDGE_COUNT"] == 825,
        "wrong inherited target cap authority",
    )
    model_facts()
    return {
        "BASE_DOCUMENT": base,
        "BASE_ACCEPTANCE_MESSAGE_VERBATIM": message,
        "BASE_ACCEPTANCE_MESSAGE_SHA256": sha(message.encode()),
        "BASE_TREE_ENTRY_COUNT": len(tree.split(b"\0")) - 1,
        "SOURCE_PINS": pins,
        "R30_CAP_RECORD_VERBATIM": cap,
    }


def primary_domains() -> tuple[list[Degrees], list[Degrees]]:
    groups = ((6, 2), (5, 8), (4, 3), (2, 1))
    options = [tuple(combinations_with_replacement(range(7 - d), n)) for d, n in groups]
    core = [tuple(s for group in groups_ for s in group) for groups_ in product(*options)]
    zero = list(combinations_with_replacement(range(1, 7), 6))
    return core, zero


def independent_domains() -> tuple[list[Degrees], list[Degrees]]:
    """Generate by recursive per-position capacities, without the product/CWR code."""

    def visit(prefix: Degrees, core: bool) -> Iterator[Degrees]:
        pos = len(prefix)
        stop = 14 if core else 6
        if pos == stop:
            yield prefix
            return
        low = 0 if core else 1
        if pos and (not core or D[pos] == D[pos - 1]):
            low = prefix[-1]
        high = 6 - D[pos] if core else 6
        for value in range(low, high + 1):
            yield from visit((*prefix, value), core)

    return list(visit((), True)), list(visit((), False))


def split_f(sigma: Degrees, zeta: Degrees) -> int:
    require(len(sigma) == 14 and len(zeta) == 6, "wrong split degree lengths")
    require(all(type(v) is int for v in (*sigma, *zeta)), "noninteger split degree")
    require(
        all(0 <= s <= 6 - d for s, d in zip(sigma, D[:14], strict=True))
        and all(1 <= z <= 6 for z in zeta),
        "cross degree capacity violation",
    )
    require(sum(sigma) == sum(zeta), "unequal cross totals")
    h = tuple(7 - d + s for d, s in zip(D[:14], sigma, strict=True))
    a = tuple(z - 1 for z in zeta)
    general = (
        291
        - 3 * sum(h)
        - 7 * sum(a)
        + sum(s * v for s, v in zip(sigma, h, strict=True))
        + sum(z * v for z, v in zip(zeta, a, strict=True))
    )
    polynomial = (
        237
        + sum(s * (s + 3 - d) for s, d in zip(sigma, D[:14], strict=True))
        + sum(z * (z - 7) for z in zeta)
    )
    require(general == polynomial, "split identity polynomial mismatch")
    return polynomial


def havel_hakimi(degrees: Degrees) -> bool:
    """Independent simple-graph test, used only on this certificate's four lists."""
    if any(type(v) is not int or not 0 <= v < len(degrees) for v in degrees):
        return False
    residual = list(degrees)
    while residual:
        residual.sort(reverse=True)
        top = residual.pop(0)
        if top > len(residual):
            return False
        for i in range(top):
            residual[i] -= 1
            if residual[i] < 0:
                return False
    return True


def independently_necessary(sigma: Degrees, zeta: Degrees) -> bool:
    if sum(sigma) != sum(zeta):
        return False
    h = tuple(7 - d + s for d, s in zip(D[:14], sigma, strict=True))
    residual = tuple(6 - d - s for d, s in zip(D[:14], sigma, strict=True))
    a = tuple(z - 1 for z in zeta)
    if not all(havel_hakimi(seq) for seq in (h, residual, a, tuple(6 - z for z in zeta))):
        return False
    # The transpose Gale-Ryser inequalities use the six zero rows, not 14 core rows.
    right = sorted(zeta, reverse=True)
    return all(sum(right[:j]) <= sum(min(j, s) for s in sigma) for j in range(1, 7))


def enumerate_certificate() -> Document:
    core, zero = primary_domains()
    other_core, other_zero = independent_domains()
    require(core == other_core and zero == other_zero, "omitted or altered canonical domain")
    require(len(core) == 1 * 9 * comb(5, 3) * 5 == 450, "core domain coverage")
    require(len(zero) == comb(11, 6) == 462, "zero domain coverage")
    primary: list[State] = []
    secondary: list[State] = []
    equal = 0
    for sigma, zeta in product(core, zero):
        if sum(sigma) != sum(zeta):
            continue
        equal += 1
        value = split_f(sigma, zeta)
        try:
            c = split.configuration(D, sigma, zeta)
        except ValueError:
            pass
        else:
            require(c.f == value, "pinned split formula disagrees")
            primary.append((sigma, zeta, value))
        if independently_necessary(sigma, zeta):
            secondary.append((sigma, zeta, value))
    require(primary == secondary, "independent necessary-state verification differs")
    require(equal == 2420 and len(primary) == 498, "complete necessary-state counts differ")
    maximum = max(f for _, _, f in primary)
    rows = [{"SIGMA": list(s), "ZETA": list(z), "F": f} for s, z, f in primary]
    return {
        "CORE_CLASSES": len(core),
        "ZERO_CLASSES": len(zero),
        "TOTAL_CANONICAL_PAIRS": len(core) * len(zero),
        "EQUAL_CROSS_TOTAL_PAIRS": equal,
        "FEASIBLE_NECESSARY_STATES": len(primary),
        "MAX_F": maximum,
        "MAXIMIZERS": [row for row in rows if row["F"] == maximum],
        "STATES": rows,
        "STATES_SHA256": sha(render(rows)),
        "CORE_DOMAIN_SHA256": sha(render(core)),
        "ZERO_DOMAIN_SHA256": sha(render(zero)),
        "INDEPENDENT_STATE_COMPARISON": "PASS_EG_CORE_GR_VS_HH_ZERO_GR",
        "COVERAGE": "EVERY_LEGAL_REALIZATION; necessary-condition superset",
        "LEGAL_SUPPORT_ATTAINMENT": "UNKNOWN",
    }


def audit_graph(edges: set[tuple[int, int]], degrees: Degrees = D) -> Document:
    """Observe the exact identity on a target graph; no support witness is inferred."""
    require(tuple(sorted(degrees, reverse=True)) == D, "wrong graph profile")
    require(
        all(type(x) is int and type(y) is int and 0 <= x < y < 20 for x, y in edges),
        "not a simple canonical overlap graph",
    )
    neighbours = [{y if x == v else x for x, y in edges if v in (x, y)} for v in range(20)]
    require(tuple(len(n) for n in neighbours) == tuple(6 + d for d in degrees), "wrong G degrees")
    core = tuple(v for v, d in enumerate(degrees) if d)
    zero = tuple(v for v, d in enumerate(degrees) if not d)
    m = set(combinations(core, 2)) - edges
    n = set(combinations(zero, 2)) - edges
    sigma = tuple(len(neighbours[x].intersection(zero)) for x in core)
    zeta = tuple(len(neighbours[u].intersection(core)) for u in zero)
    canonical = tuple(
        s
        for d in (6, 5, 4, 2)
        for s in sorted(sigma[i] for i, v in enumerate(core) if degrees[v] == d)
    )
    f = split_f(canonical, tuple(sorted(zeta)))
    parts = (
        split.triangle_count(core, m),
        split.triangle_count(zero, n),
        sum(len(neighbours[x].intersection(neighbours[y], zero)) for x, y in m),
        sum(len(neighbours[u].intersection(neighbours[v], core)) for u, v in n),
    )
    complement = set(combinations(range(20), 2)) - edges
    t = split.triangle_count(tuple(range(20)), edges)
    th = split.triangle_count(tuple(range(20)), complement)
    require(all(v >= 0 for v in parts), "negative cardinality remainder")
    require(t == 291 - th == f - sum(parts), "observed split/complement identity fails")
    split.configuration(D, canonical, tuple(sorted(zeta)))
    return {
        "T": t,
        "F": f,
        "P": sum(parts),
        "P_TERMS": list(parts),
        "SIGMA": list(canonical),
        "ZETA": sorted(zeta),
        "SUPPORT_REALIZATION": "NOT_ASSERTED",
    }


def audit_supports(triples: Sequence[Degrees], pairs: Sequence[Degrees]) -> Document:
    d = tuple(sum(v in triple for triple in triples) for v in range(20))
    split.prior.r5.validate_k20_support_realization(triples, pairs, d)
    observed = audit_graph(split.edges_of((*triples, *pairs)), d)
    require(integer(observed["T"]) <= 223, "legal witness exceeds proved cap")
    return observed | {"SUPPORT_REALIZATION": "VALIDATED", "T223_ATTAINMENT": "NOT_ASSERTED"}


def route_terms(cap: int) -> list[Term]:
    require(type(cap) is int and 22 <= cap <= 266, "wrong Route-B cap domain")
    facts = model_facts()
    w, u, a = (integer(facts[k]) for k in ("WEDGES", "THIRD_DEGREES", "CONTAINED_K4_CAP"))
    require((w, u, a) == (825, 2296, 196), "wrong target Route-B constants")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        excess = u - 10 * (w - 3 * t)
        require(excess == 30 * t - 5954, "K4 excess derivation differs")
        q = max(0, -(-excess // 4))
        c = min(q, a)
        s4 = max(112, 448 * c + 679 * (q - c))
        s3 = 2_279_200 + 11_872 * (t - 22)
        total = 308_390_040 + s3
        bound = (7 * total - 4 * s4 + 6) // 7
        rational = Fraction(total) - Fraction(4 * s4, 7)
        require(bound - 1 < rational <= bound, "Route-B exact ceiling violated")
        terms.append((t, bound, q, c, s4, s3))
    require(terms == split.route_b_terms(D, cap, 112), "pinned Route-B terms differ")
    return terms


def replay_base(base: Document) -> tuple[dict[str, int], Document]:
    require(sha(render(base)) == BASE_RESULT_SHA256, "altered Base result")
    rows = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    cursor = obj(base["CURSOR"])
    coarse = {p: integer(v) for p, v in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    ids = [string(p) for p in items(cursor["PROFILE_IDS"])]
    require(len(rows) == base["ROWS_TOTAL"] == 4647, "incomplete Base ledger")
    require(
        len(ids) == len(set(ids)) == len(coarse) == cursor["PROFILE_COUNT"] == 197
        and set(ids) == set(coarse)
        and not set(rows).intersection(coarse),
        "cursor coverage differs",
    )
    for p in (*rows, *coarse):
        inherited.profile(p)
    require(sha(inherited.projection(rows)) == base["BOUNDS_SHA256_AFTER"], "Base row digest")
    require(sha(render(cursor)) == base["CURSOR_SHA256"], "Base cursor digest")
    for p, bound in coarse.items():
        d = inherited.profile(p)
        w = sum(comb(6 + v, 2) for v in d)
        require(bound == split.prior.w8.coarse_bound_at_wedges(w), "cursor bound differs")
    before, owners = inherited.family(rows, cursor)
    require(
        before == base["FAMILY_BOUND_AFTER"] == 313_395_164
        and owners == base["FAMILY_OWNER_IDS"]
        and integer(base["INCUMBENT"]) == 313_263_888
        and before - integer(base["INCUMBENT"]) == base["GAP_TO_INCUMBENT"] == 131276
        and sum(b > 313_263_888 for b in (*rows.values(), *coarse.values()))
        == base["STILL_OPEN_PROFILE_COUNT"],
        "complete Base family authority differs",
    )
    require(rows[TARGET] == max(t[1] for t in route_terms(266)), "wrong target existing bound")
    return rows, cursor


def compose(
    base: Document,
    rows: Sequence[tuple[str, int]],
    cursor: Mapping[str, object],
    updates: Sequence[tuple[str, int]],
) -> dict[str, int]:
    frozen, frozen_cursor = replay_base(base)
    before = dict(rows)
    require(
        len(rows) == len(before) == len(frozen)
        and all(type(v) is int for _, v in rows)
        and before == frozen,
        "wrong, duplicate, omitted or modified ledger row",
    )
    require(render(cursor) == render(frozen_cursor), "cursor modification")
    bound = max(t[1] for t in route_terms(223))
    require(
        list(updates) == [(TARGET, bound)] and type(updates[0][1]) is int, "wrong single update"
    )
    after = {**before, TARGET: bound}
    require(sum(after[p] != before[p] for p in before) == 1, "must change exactly one row")
    return after


def compute_result(authority: Document | None = None) -> Document:
    loaded = load_authority() if authority is None else authority
    base = obj(loaded["BASE_DOCUMENT"])
    before, cursor = replay_base(base)
    enumeration = enumerate_certificate()
    cap = integer(enumeration["MAX_F"])
    require(cap == 223, "universal T223 cap not proved")
    old, terms = route_terms(266), route_terms(cap)
    require(old[: len(terms)] == terms and len(terms) == 202, "incomplete target envelope")
    bound = max(t[1] for t in terms)
    best = [list(t) for t in terms if t[1] == bound]
    after = compose(base, list(before.items()), cursor, [(TARGET, bound)])
    family_before, owners_before = inherited.family(before, cursor)
    family_after, owners_after = inherited.family(after, cursor)
    incumbent = integer(base["INCUMBENT"])
    require(bound == 313_008_408 and bound < incumbent, "strict gain not excluded")
    require(family_before == family_after, "single target changed family maximum")
    a = obj(obj(obj(base["PROVENANCE"])["A"])["ACCEPTANCE"])
    source = (ROOT / SOURCE).read_bytes()
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": BASE_RESULT,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "BASE_LS_TREE_SHA256": BASE_LS_TREE_SHA256,
        "BASE_TREE_ENTRY_COUNT": loaded["BASE_TREE_ENTRY_COUNT"],
        "BASE_ACCEPTANCE_MESSAGE_VERBATIM": loaded["BASE_ACCEPTANCE_MESSAGE_VERBATIM"],
        "BASE_ACCEPTANCE_MESSAGE_SHA256": loaded["BASE_ACCEPTANCE_MESSAGE_SHA256"],
        "SOURCE_PINS": loaded["SOURCE_PINS"],
        "IMPLEMENTATION_SHA256": sha(source),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROOF": ast.get_docstring(ast.parse(source), clean=False),
        "MODEL_FACTS": model_facts(),
        "TARGET_PROFILE": TARGET,
        "CURRENT_T_CAP": 266,
        "NEW_PROVEN_T_CAP": cap,
        "R30_CAP_RECORD_VERBATIM": loaded["R30_CAP_RECORD_VERBATIM"],
        "R30_RESULT_SHA256": R30_SHA256,
        "SPLIT_IDENTITY": "T=F-P",
        "NONNEGATIVE_REMAINDER": "SUM_OF_FOUR_CARDINALITY_COUNTS",
        "ENUMERATION": enumeration,
        "ROUTE_B_TERMS": [list(t) for t in terms],
        "ROUTE_B_TERMS_VERIFIED": len(terms),
        "MAXIMIZING_ROUTE_B_TERMS": best,
        "ENVELOPE_MAX_T": [t[0] for t in terms if t[1] == bound],
        "FULL_PROFILE_BOUND_BEFORE": before[TARGET],
        "FULL_PROFILE_BOUND_AFTER": bound,
        "PROFILE_BOUND_DELTA": before[TARGET] - bound,
        "MARGIN_BELOW_INCUMBENT": incumbent - bound,
        "STRICT_GAIN_EXCLUDED": "YES",
        "LEDGER_ROWS": len(before),
        "ROWS_CHANGED": 1,
        "ROW_UPDATES": {TARGET: {"BEFORE": before[TARGET], "AFTER": bound}},
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4646_BOUNDS_SHA256": sha(
            inherited.projection({p: v for p, v in before.items() if p != TARGET})
        ),
        "BOUNDS_SHA256_BEFORE": sha(inherited.projection(before)),
        "BOUNDS_SHA256_AFTER": sha(inherited.projection(after)),
        "CURSOR": cursor,
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_PROFILE_COUNT": cursor["PROFILE_COUNT"],
        "CURSOR_BOUND": cursor["BOUND"],
        "FAMILY_BOUND_BEFORE": family_before,
        "FAMILY_BOUND_AFTER": family_after,
        "FAMILY_DELTA": family_before - family_after,
        "FAMILY_OWNER_IDS_BEFORE": owners_before,
        "FAMILY_OWNER_IDS": owners_after,
        "INCUMBENT": incumbent,
        "GAP_TO_INCUMBENT": family_after - incumbent,
        "STILL_OPEN_PROFILE_COUNT": sum(
            v > incumbent
            for v in (
                *after.values(),
                *(integer(b) for b in obj(cursor["COARSE_BOUND_PROJECTION"]).values()),
            )
        ),
        "INHERITED_BASE_RESULT_VERBATIM": base,
        "OWNER_A_HISTORICAL_REPORT_DIGEST_CAVEAT": {
            "DECLARED_SHA256": a["REPORT_DECLARED_SHA256"],
            "COMMITTED_MARKER_TEXT_SHA256": a["REPORT_COMMITTED_TEXT_SHA256"],
            "ORIGINAL_DISPOSITION": a["REPORT_HASH_DISPOSITION"],
            "REPAIR_CLAIM": "NONE; inherited discrepancy preserved",
        },
        "INHERITED_CAVEATS": "PRESERVED_VERBATIM",
        "LEGAL_SUPPORT_T223_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "G01_TO_G18_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 19)},
        "GATE_STATUS_SCOPE": (
            "External exact-tree Fresh Judge and subsequent single-commit/clean/release lifecycle"
        ),
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "REMOTE_WRITE": "NO",
    }


def verify_result(document: Document) -> None:
    require(
        render(document) == render(compute_result()), "sealed certificate differs from exact replay"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    path = ROOT / RESULT
    document = compute_result()
    if args.write:
        require(not path.exists(), "result already exists; refuse to overwrite")
        with path.open("xb") as output:
            output.write(render(document))
    else:
        require(stat.S_ISREG(path.lstat().st_mode), "unsafe sealed certificate")
        require(
            path.read_bytes() == render(document), "sealed certificate differs from exact replay"
        )
    print(
        json.dumps(
            {
                "STATUS": "PASS",
                "T_CAP": document["NEW_PROVEN_T_CAP"],
                "PROFILE_BOUND": document["FULL_PROFILE_BOUND_AFTER"],
                "FAMILY_BOUND": document["FAMILY_BOUND_AFTER"],
                "RESULT_SHA256": sha(path.read_bytes()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
