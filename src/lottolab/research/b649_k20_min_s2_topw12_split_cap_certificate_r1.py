"""Split-cap proof for the twelve top-W profiles, extending d316's complete coverage.

Proof (universal identities, then a necessary-condition relaxation).
There are 22 linear triple supports and 27 unused pair supports on 20 tickets,
each with six labels. The shadow-plus-pair graph G has deg(v)=6+d_v and 93
edges. Its complement H has degree 13-d_v and 97 edges. Inclusion-exclusion
on each vertex triple gives t(G)=C(20,3)-18*97+sum C(13-d_v,2)-t(H)
=Phi-t(H), where Phi=sum C(13-d_v,2)-606.

Partition into core K={d>0} and zeros Z, of sizes k,z. Write M=H[K],
MZ=H[Z], sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|,
h_x=13-z-d_x+sigma_x and a_u=z-7+zeta_u. Each mixed H triangle has
exactly one same-part edge. Summing common complement neighbours across
that edge gives the exact identity
 t(G)=Phi-z*sum(h)/2-k*sum(a)/2+sum(sigma*h)+sum(zeta*a)-P = F-P,
where P is the sum of t(M), t(MZ), common G zero-neighbours of M edges,
and common G core-neighbours of MZ edges. All four terms are nonnegative.

Necessary conditions: 0<=sigma<=6-d (only pair labels can reach Z),
max(0,7-z)<=zeta<=min(6,k) (a zero has six neighbours and at most z-1
inside Z). The degree lists h,a,6-zeta,6-d-sigma must be graphical,
and sigma,zeta must be bipartite graphical. Erdős-Gallai and Gale-Ryser
are evaluated in integers. Enumerate sigma sorted within equal-d groups
and zeta sorted within Z: these are vertex symmetries preserving F and
all necessary inequalities. The resulting finite set is a superset of
every legal realization, even though the separate graphs need not admit
a simultaneous realization. Hence max F bounds t(G) without a solver.

Conditional special-profile lemma: d=(6^4,5^8,1^2,0^6). Each d=6
vertex has 12 shadow neighbours among 13 other core vertices, so meets
at least one of the two d=1 vertices A,B. Their total shadow capacity
is four, forcing exactly two high neighbours each and no other shadow
neighbours. Each high vertex misses precisely A or B and meets all eight
d=5 vertices D. Each D has six shadow neighbours among the other seven D,
so the four missing D edges form a perfect matching. A-D,B-D,A-B are
all shadow nonedges. IF sigma_A=sigma_B=5, neither A nor B has a core
pair label. Each D has one pair label, which, unless it reaches Z, must
fill its missing matching edge. Let r=sum_D sigma. Exactly r/2 matching
edges remain in M, giving 8+r triangles in M (eight A-B-D, and two per
remaining matching edge). The M edge A-B has at least 5+5-6=4 common
zero neighbours, so P>=12+r. This lemma is NOT unconditional.

Branch A uses P>=0 when F<=256. Branch B is entered only when F>256;
enumeration must then establish sigma_A=sigma_B=5 before invoking the
lemma. If a prerequisite fails, certification fails. All branch bounds
are maximized; neither an expected count nor an expected cap is evidence.

Route B is reused from d316 with its exact rational all-t checker, and
also independently evaluated here with integer floors/ceilings. Coverage
and the W<=834 ledger/cursor are inherited from the SHA-pinned d316 result;
only its twelve top rows are replaced. No coverage repair is rerun.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_topw12_coverage_repair_r1 as prior

TASK_ID = "B649_K20_MIN_S2_TOPW12_SPLIT_CAP_CERTIFICATE_R1"
BASE_HEAD = "d3161548b66f6243c4825d1247d909fb1d2adaea"
BASE_TREE = "8a95512a8427a605f088846f7c0f1d5b6b899052"
BASE_RESULT_SHA256 = "b49eae19b944e3b631933b26bb9aa707e750b14ae36049dd2744d51f6357595b"
SPECIAL = "66665555555511000000"
TOP = "66665555555520000000"
SPECIAL_THRESHOLD = 256
RESULT_FILENAME = "b649-k20-min-s2-topw12-split-cap-certificate-r1-result.json"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = ROOT / prior.RESULT_DIRECTORY / RESULT_FILENAME
Profile = tuple[int, ...]
Pair = tuple[int, int]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
integer = prior.integer
object_row = prior.object_row
rows = prior.rows
text = prior.text


def pinned_authority() -> dict[str, object]:
    """Read the existing coverage proof at its immutable commit, without replaying it."""

    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=ROOT)

    if git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    path = f"{prior.RESULT_DIRECTORY}/{prior.RESULT_FILENAME}"
    blob = git("show", f"{BASE_HEAD}:{path}")
    if hashlib.sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("coverage authority digest mismatch")
    # Pin the reused helpers and the research modules named by the coverage authority.
    modules = (prior, *prior.PROVENANCE_MODULES)
    for module in modules:
        if module.__file__ is None:
            raise AssertionError("reused module has no source")
        source = Path(module.__file__).resolve()
        relative = source.relative_to(ROOT).as_posix()
        if source.read_bytes() != git("show", f"{BASE_HEAD}:{relative}"):
            raise AssertionError(f"reused source changed: {relative}")
    return object_row(json.loads(blob))


def profile_values(profile: str | Sequence[int]) -> Profile:
    d = tuple(map(int, profile)) if isinstance(profile, str) else tuple(profile)
    if len(d) != 20 or any(type(v) is not int or not 0 <= v <= 6 for v in d):
        raise ValueError("expected twenty integer degrees in 0..6")
    if sum(d) != 66 or 0 not in d:
        raise ValueError("split cap requires sum 66 and a nonempty zero part")
    return tuple(sorted(d, reverse=True))


def graphical(degrees: Sequence[int]) -> bool:
    d = sorted(degrees, reverse=True)
    n = len(d)
    return (
        all(0 <= v < n for v in d)
        and sum(d) % 2 == 0
        and all(sum(d[:j]) <= j * (j - 1) + sum(min(j, v) for v in d[j:]) for j in range(1, n + 1))
    )


def bipartite_graphical(sigma: Sequence[int], zeta: Sequence[int]) -> bool:
    d = sorted(sigma, reverse=True)
    return sum(d) == sum(zeta) and all(
        sum(d[:j]) <= sum(min(j, v) for v in zeta) for j in range(1, len(d) + 1)
    )


@dataclass(frozen=True)
class Configuration:
    profile: Profile
    sigma: Profile
    zeta: Profile
    h: Profile
    a: Profile
    f: int


def configuration(profile: Profile, sigma: Profile, zeta: Profile) -> Configuration:
    """Validate every relaxation premise before evaluating its objective."""
    d = tuple(v for v in profile_values(profile) if v)
    z, k = profile.count(0), len(d)
    if len(sigma) != k or len(zeta) != z:
        raise ValueError("split degree lengths mismatch")
    if any(not 0 <= s <= 6 - v for s, v in zip(sigma, d, strict=True)):
        raise ValueError("core cross-degree exceeds pair capacity")
    if any(not max(0, 7 - z) <= v <= min(6, k) for v in zeta):
        raise ValueError("zero cross-degree outside necessary limits")
    h = tuple(13 - z - v + s for v, s in zip(d, sigma, strict=True))
    a = tuple(z - 7 + v for v in zeta)
    residual = tuple(6 - v - s for v, s in zip(d, sigma, strict=True))
    if not all(graphical(seq) for seq in (h, a, residual, tuple(6 - v for v in zeta))):
        raise ValueError("nongraphical necessary degree list")
    if not bipartite_graphical(sigma, zeta):
        raise ValueError("cross degree lists fail Gale-Ryser")
    phi = sum(comb(13 - v, 2) for v in profile) - 606
    f = (
        phi
        - z * (sum(h) // 2)
        - k * (sum(a) // 2)
        + sum(s * v for s, v in zip(sigma, h, strict=True))
        + sum(s * v for s, v in zip(zeta, a, strict=True))
    )
    return Configuration(profile, sigma, zeta, h, a, f)


def degree_configurations(profile: str | Sequence[int]) -> Iterator[Configuration]:
    """Exhaust only the small degree relaxation, modulo equal-degree symmetries."""
    p = profile_values(profile)
    d = tuple(v for v in p if v)
    z, k = p.count(0), len(d)
    zero_by_sum: dict[int, list[Profile]] = {}
    for zz in combinations_with_replacement(range(max(0, 7 - z), min(6, k) + 1), z):
        if graphical(tuple(6 - v for v in zz)) and graphical(tuple(z - 7 + v for v in zz)):
            zero_by_sum.setdefault(sum(zz), []).append(zz)
    options = [
        tuple(combinations_with_replacement(range(7 - v), count))
        for v, count in sorted(Counter(d).items(), reverse=True)
    ]
    for pieces in product(*options):
        sigma = tuple(v for piece in pieces for v in piece)
        h = tuple(13 - z - v + s for v, s in zip(d, sigma, strict=True))
        residual = tuple(6 - v - s for v, s in zip(d, sigma, strict=True))
        if not graphical(h) or not graphical(residual):
            continue
        for zeta in zero_by_sum.get(sum(sigma), []):
            if bipartite_graphical(sigma, zeta):
                yield configuration(p, sigma, zeta)


def conditional_p_floor(c: Configuration) -> int:
    """P>=12+r only for the special profile with both low vertices saturated to Z."""
    if c != configuration(c.profile, c.sigma, c.zeta):
        raise ValueError("configuration objective or degrees changed")
    if prior.profile_id(c.profile) != SPECIAL or c.sigma[-2:] != (5, 5):
        raise ValueError("conditional P12 requires special profile and sigma_A=sigma_B=5")
    r = sum(c.sigma[4:12])
    if r % 2:
        raise ValueError("remaining D matching edges require even cross incidence")
    return 8 + r + max(0, 5 + 5 - c.profile.count(0))


def branch_bound(c: Configuration) -> tuple[int, int, str]:
    if prior.profile_id(c.profile) == SPECIAL and c.f > SPECIAL_THRESHOLD:
        floor = conditional_p_floor(c)
        return c.f - floor, floor, "B_CONDITIONAL_P12"
    return c.f, 0, "A_NONNEGATIVE_P"


def split_certificate(profile: str | Sequence[int]) -> dict[str, object]:
    p = profile_values(profile)
    count, p0_cap, cap = 0, -1, -1
    branch_counts: Counter[str] = Counter()
    branch_maxima: dict[str, int] = {}
    conditional: list[dict[str, object]] = []
    maximizing: dict[str, object] = {}
    for c in degree_configurations(p):
        count += 1
        bound, floor, branch = branch_bound(c)
        branch_counts[branch] += 1
        branch_maxima[branch] = max(branch_maxima.get(branch, -1), bound)
        p0_cap = max(p0_cap, c.f)
        row: dict[str, object] = {
            "SIGMA": list(c.sigma),
            "ZETA": list(c.zeta),
            "F": c.f,
            "P_FLOOR": floor,
            "BOUND": bound,
            "BRANCH": branch,
        }
        if branch == "B_CONDITIONAL_P12":
            conditional.append(row)
        if bound > cap:
            cap, maximizing = bound, row
    if count == 0:
        raise AssertionError("no necessary degree configuration; cannot issue a cap")
    if prior.profile_id(p) == SPECIAL and cap > SPECIAL_THRESHOLD:
        raise AssertionError("conditional split cap did not establish T<=256")
    return {
        "PROFILE_ID": prior.profile_id(p),
        "DEGREE_CONFIGURATION_COUNT": count,
        "P0_TRIANGLE_CAP": p0_cap,
        "TRIANGLE_CAP": cap,
        "BRANCH_COUNTS": dict(branch_counts),
        "BRANCH_MAXIMA": branch_maxima,
        "CONDITIONAL_CONFIGURATIONS": conditional,
        "MAXIMIZER": maximizing,
    }


def route_b_terms(p: Profile, cap: int, base: int) -> list[Term]:
    g = tuple(6 + d for d in p)
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a = sum(d * (v - 2) for d, v in zip(p, g, strict=True)) // 3
    terms: list[Term] = []
    for t in range(22, cap + 1):
        k4 = max(0, -(-(u - (max(g) - 2) * (w - 3 * t)) // 4))
        contained = min(k4, a)
        s4 = max(base, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372228640 - 63838600 + s3 - (4 * s4) // 7
        terms.append((t, bound, k4, contained, s4, s3))
    if terms != prior.w8.exact_route_b_terms(p, cap, base):
        raise AssertionError("Route B integer and rational terms disagree")
    return terms


def top_certificate(old: Mapping[str, object]) -> dict[str, object]:
    p = profile_values(text(old["PROFILE_ID"]))
    cert = split_certificate(p)
    cap = integer(cert["TRIANGLE_CAP"])
    terms = route_b_terms(p, cap, integer(old["S4_BASE"]))
    old_terms = rows(old["ALL_T_TERMS"])
    if [list(term) for term in terms] != old_terms[: len(terms)]:
        raise AssertionError("new envelope differs from the pinned all-t formula")
    best = max(terms, key=lambda term: (term[1], term[0]))
    return cert | {
        "STATUS": "PASS",
        "S4_BASE": old["S4_BASE"],
        "PREVIOUS_CAP": old["TRIANGLE_CAP"],
        "PREVIOUS_BOUND": old["ALL_T_MAX_BOUND"],
        "ALL_T_TERMS": [list(term) for term in terms],
        "TERM_COUNT": len(terms),
        "ALL_T_MAX_BOUND": best[1],
        "ARGMAX_TRIANGLES": best[0],
        "ROUTE": "SPLIT_CAP_ROUTE_B_ALL_T",
        "ALL_T_STATUS": "PASS_INTEGER_AND_RATIONAL",
    }


def family_recompute(
    base: Mapping[str, object],
    certificates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Replace exactly twelve rows within the immutable complete coverage partition."""
    old = [object_row(raw) for raw in rows(base["TOP_W_CERTIFICATES"])]
    expected = [text(c["PROFILE_ID"]) for c in old]
    actual = [text(c["PROFILE_ID"]) for c in certificates]
    partition = object_row(base["PROFILE_PARTITION_BEFORE_REPAIR"])
    counts = {name: integer(object_row(raw)["COUNT"]) for name, raw in partition.items()}
    coverage = object_row(base["COVERAGE_AFTER_REPAIR"])
    if actual != expected or len(set(actual)) != 12 or counts[prior.PART_TOP] != len(actual):
        raise AssertionError("replacement certificates are not exactly the twelve top rows")
    covered = sum(count for name, count in counts.items() if name != prior.PART_EXCLUDED)
    if (
        base["PROFILE_COVERAGE_STATUS"] != "COMPLETE"
        or covered != 4844
        or coverage["COVERED_PROFILE_COUNT"] != covered
        or coverage["UNCOVERED_PROFILE_COUNT"] != 0
        or counts[prior.PART_FRONTIER] + integer(base["FINAL_LEDGER_COUNT"]) != covered
    ):
        raise AssertionError("inherited complete coverage partition mismatch")
    top_bounds = {text(c["PROFILE_ID"]): integer(c["ALL_T_MAX_BOUND"]) for c in certificates}
    old_top = max(integer(c["ALL_T_MAX_BOUND"]) for c in old)
    inherited = object_row(base["FAMILY_TERMS"])
    ledger, cursor = (
        integer(inherited["RESOLVED_LEDGER_W786_834"]),
        integer(inherited["UNRESOLVED_CURSOR_W785_COARSE"]),
    )
    if base["FINAL_COMPLETE_FAMILY_UPPER_BOUND"] != max(ledger, old_top, cursor):
        raise AssertionError("base family aggregate mismatch")
    top_max = max(top_bounds.values())
    family = max(ledger, top_max, cursor)
    owners = [i for i, bound in top_bounds.items() if bound == family]
    if ledger == family:
        owners.extend(text(i) for i in rows(base["LEDGER_DEFINED_OWNER_IDS"]))
    if cursor == family:
        owners.append(prior.CURSOR_ID)
    return {
        "PROFILE_COVERAGE_COUNT": covered,
        "PROFILE_COVERAGE_STATUS": "COMPLETE_INHERITED_D316",
        "UNCOVERED_PROFILE_COUNT": 0,
        "FINAL_LEDGER_COUNT": base["FINAL_LEDGER_COUNT"],
        "INHERITED_PARTITION": partition,
        "INHERITED_LEDGER_SHA256": base["PREVIOUS_LEDGER_ROWS_SHA256"],
        "FAMILY_TERMS": {
            "RESOLVED_LEDGER_W786_834": ledger,
            "TOP_W835_837": top_max,
            "UNRESOLVED_CURSOR_W785_COARSE": cursor,
        },
        "BASE_COMPLETE_FAMILY_UB": max(ledger, old_top, cursor),
        "TOPW12_CERTIFIED_COUNT": len(certificates),
        "TOPW12_MAX": top_max,
        "FINAL_COMPLETE_FAMILY_UB": family,
        "FINAL_BOUND_OWNER_IDS": sorted(owners, reverse=True),
        "CURRENT_INCUMBENT": base["CURRENT_INCUMBENT"],
        "REMAINING_GAP": family - integer(base["CURRENT_INCUMBENT"]),
    }


def edges_of(supports: Sequence[Support]) -> set[Pair]:
    return {(a, b) for support in supports for a, b in combinations(sorted(support), 2)}


def triangle_count(vertices: Sequence[int], edges: set[Pair]) -> int:
    return sum(
        all((a, b) in edges for a, b in combinations(triple, 2))
        for triple in combinations(sorted(vertices), 3)
    )


def analyze_realization(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """Accept legal witnesses, count graph motifs, and verify both exact identities."""
    d = tuple(sum(v in triple for triple in triples) for v in range(20))
    prior.r5.validate_k20_support_realization(triples, pairs, d)
    edges = edges_of((*triples, *pairs))
    neighbours = [{w for w in range(20) if tuple(sorted((v, w))) in edges} for v in range(20)]
    core = tuple(v for v in range(20) if d[v])
    zero = tuple(v for v in range(20) if not d[v])
    m, mz = set(combinations(core, 2)) - edges, set(combinations(zero, 2)) - edges
    sigma = tuple(len(neighbours[v] & set(zero)) for v in core)
    zeta = tuple(len(neighbours[v] & set(core)) for v in zero)
    h = tuple(sum(v in e for e in m) for v in core)
    a = tuple(sum(v in e for e in mz) for v in zero)
    parts = (
        triangle_count(core, m),
        triangle_count(zero, mz),
        sum(len(neighbours[x] & neighbours[y] & set(zero)) for x, y in m),
        sum(len(neighbours[x] & neighbours[y] & set(core)) for x, y in mz),
    )
    phi = sum(comb(13 - v, 2) for v in d) - 606
    f = (
        phi
        - len(zero) * len(m)
        - len(core) * len(mz)
        + sum(x * y for x, y in zip(sigma, h, strict=True))
        + sum(x * y for x, y in zip(zeta, a, strict=True))
    )
    t = triangle_count(tuple(range(20)), edges)
    independent = triangle_count(tuple(range(20)), set(combinations(range(20), 2)) - edges)
    if t != phi - independent or t != f - sum(parts):
        raise AssertionError("exact split/complement identity failed")
    p = profile_values(d)
    canonical_sigma = tuple(
        s
        for degree in sorted(set(d) - {0}, reverse=True)
        for s in sorted(sigma[i] for i, v in enumerate(core) if d[v] == degree)
    )
    c = configuration(p, canonical_sigma, tuple(sorted(zeta)))
    bound, floor, branch = branch_bound(c)
    if c.f != f or sum(parts) < floor or t > bound:
        raise AssertionError("witness violates a proved conditional branch")
    return {
        "PROFILE_ID": prior.profile_id(p),
        "TRIANGLES": t,
        "P_TERMS": list(parts),
        "P_TOTAL": sum(parts),
        "F": f,
        "PHI": phi,
        "INDEPENDENT_TRIPLES": independent,
        "SIGMA": list(c.sigma),
        "ZETA": list(c.zeta),
        "P_FLOOR_USED": floor,
        "BRANCH": branch,
        "TRIPLES": [list(s) for s in triples],
        "PAIRS": [list(s) for s in pairs],
        "STATUS": "PASS",
    }


SPECIAL_TRIPLES: tuple[Support, ...] = (
    (0, 1, 12),
    (0, 2, 11),
    (0, 3, 7),
    (0, 4, 8),
    (0, 5, 9),
    (0, 6, 10),
    (1, 2, 6),
    (1, 3, 4),
    (1, 5, 7),
    (1, 8, 11),
    (1, 9, 10),
    (2, 3, 13),
    (2, 4, 10),
    (2, 5, 8),
    (2, 7, 9),
    (3, 5, 10),
    (3, 6, 11),
    (3, 8, 9),
    (4, 5, 11),
    (4, 6, 9),
    (6, 7, 8),
    (7, 10, 11),
)
TOP_TRIPLES: tuple[Support, ...] = (
    (0, 1, 8),
    (0, 2, 12),
    (0, 3, 6),
    (0, 4, 9),
    (0, 5, 11),
    (0, 7, 10),
    (1, 2, 9),
    (1, 3, 12),
    (1, 4, 5),
    (1, 6, 10),
    (1, 7, 11),
    (2, 3, 5),
    (2, 4, 11),
    (2, 6, 7),
    (2, 8, 10),
    (3, 4, 7),
    (3, 8, 9),
    (3, 10, 11),
    (4, 6, 8),
    (5, 7, 8),
    (5, 9, 10),
    (6, 9, 11),
)


def witness_supports(kind: str) -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    if kind in ("P2", "CONDITIONAL"):
        triples = SPECIAL_TRIPLES
        fixed = ((4, 7), (5, 6), (8, 10), (9, 11))
        if kind == "P2":
            pairs = (
                *fixed,
                (12, 13),
                *(e for e in combinations(range(14, 20), 2) if e != (14, 15)),
                (12, 14),
                (12, 15),
                (12, 16),
                (12, 17),
                (13, 14),
                (13, 15),
                (13, 18),
                (13, 19),
            )
        else:
            pairs = (
                *fixed,
                *(e for e in combinations(range(14, 20), 2) if e not in ((14, 15), (16, 17))),
                *((12, v) for v in range(14, 19)),
                *((13, v) for v in (14, 15, 16, 17, 19)),
            )
    elif kind == "TOP":
        triples = TOP_TRIPLES
        pairs = (
            (4, 12),
            (5, 12),
            (6, 12),
            (10, 12),
            (7, 9),
            (8, 11),
            *combinations(range(13, 20), 2),
        )
    elif kind == "STS13":
        # The 26 cyclic blocks partition all pairs of 13 points exactly once.
        sts = tuple(
            tuple(sorted((v + shift) % 13 for v in block))
            for block in ((0, 1, 4), (0, 2, 7))
            for shift in range(13)
        )
        if len(edges_of(sts)) != comb(13, 2) or sum(comb(len(s), 2) for s in sts) != comb(13, 2):
            raise AssertionError("cyclic STS13 is not a pair partition")
        triples = (
            *(tuple(v - 1 for v in s) for s in sts if 0 not in s),
            (12, 13, 14),
            (15, 16, 17),
        )
        shadow = edges_of(triples)
        pairs = (
            *(e for e in combinations(range(12), 2) if e not in shadow),
            *(e for e in combinations(range(12, 20), 2) if e not in shadow and e != (18, 19)),
        )
    else:
        raise ValueError("unknown witness")
    return tuple(triples), tuple(pairs)


def compute_result() -> dict[str, object]:
    base = pinned_authority()
    certificates = [top_certificate(object_row(raw)) for raw in rows(base["TOP_W_CERTIFICATES"])]
    family = family_recompute(base, certificates)
    witnesses = {
        kind: analyze_realization(*witness_supports(kind))
        for kind in ("P2", "CONDITIONAL", "TOP", "STS13")
    }
    if integer(witnesses["P2"]["P_TOTAL"]) >= 12:
        raise AssertionError("counterexample no longer refutes unconditional P12")
    sts_cap = split_certificate(text(witnesses["STS13"]["PROFILE_ID"]))
    if integer(sts_cap["TRIANGLE_CAP"]) < integer(witnesses["STS13"]["TRIANGLES"]):
        raise AssertionError("STS13 witness excluded by relaxation")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": prior.RESULT_FILENAME,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "PROOF": __doc__,
        "COVERAGE_REPAIR_RERUN": False,
        "COUNTEREXAMPLE_P2_ACCEPTED": True,
        "UNCONDITIONAL_P12_REJECTED": True,
        "CONDITIONAL_P12_LEMMA_STATUS": "PROVED_WITH_EXPLICIT_SATURATION_PREMISES",
        "TOP_W_CERTIFICATES": certificates,
        "WITNESSES": witnesses,
        "STS13_RELAXATION": sts_cap,
        "DEGREE_CONFIGURATION_COUNT": sum(
            integer(c["DEGREE_CONFIGURATION_COUNT"]) for c in certificates
        ),
        "ALL_T_INTEGER_TERMS_CHECKED": sum(integer(c["TERM_COUNT"]) for c in certificates),
        "SPECIAL_PROFILE_CAP": next(
            c["TRIANGLE_CAP"] for c in certificates if c["PROFILE_ID"] == SPECIAL
        ),
        "TOP_PROFILE_CAP": next(c["TRIANGLE_CAP"] for c in certificates if c["PROFILE_ID"] == TOP),
        **family,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    result = compute_result()
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "DEGREE_CONFIGURATION_COUNT",
                    "ALL_T_INTEGER_TERMS_CHECKED",
                    "TOPW12_MAX",
                    "PROFILE_COVERAGE_COUNT",
                    "FINAL_COMPLETE_FAMILY_UB",
                    "REMAINING_GAP",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
